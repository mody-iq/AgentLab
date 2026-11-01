#!/usr/bin/env python3
"""Tweak agent: Gemini writes files, Theos builds them, build errors go back to Gemini."""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

KEY = os.environ.get("GEMINI_KEY", "").strip()
PROJECT = os.environ.get("PROJECT", "").strip()
TASK = os.environ.get("TASK", "").strip()
MODELS = [m.strip() for m in os.environ.get("MODELS", "gemini-3.8-flash,gemini-3.5-flash").split(",") if m.strip()]

try:
    MAX_ITERS = max(1, min(8, int(os.environ.get("MAX_ITERS", "4") or "4")))
except ValueError:
    MAX_ITERS = 4

SYSTEM = """You are a strict senior iOS tweak engineer (Objective-C, Logos, Theos) working inside an automated build loop.

TARGET
- Device: iPhone XS Max (A12, arm64e), iOS 18.7, RootHide rootless jailbreak (ElleKit). The tweak must also work on iOS 16 to 18.7, so check versions at runtime.
- Build: Theos (RootHide fork) with the iOS 16.5 SDK. Command: gmake clean package FINALPACKAGE=1 THEOS_PACKAGE_SCHEME=roothide TARGET=iphone:clang:16.5:16.0
- Because the SDK is 16.5, newer or private APIs are NOT in the headers. Declare private classes and methods yourself with @interface or @protocol forward declarations (never import private headers), or reach them at runtime with NSClassFromString, NSSelectorFromString and objc_msgSend casts.

OUTPUT FORMAT (strict)
- Reply with files only, each in exactly this form, with no markdown fences around or inside the blocks:
=== FILE: relative/path/inside/project ===
<complete file content>
=== END FILE ===
- Paths are relative to the project folder (for example Makefile, control, Tweak.x). Never use absolute paths or "..".
- Every file you output must be COMPLETE. No placeholders, no TODO, no "rest unchanged", no ellipsis.
- On the first reply output all files needed. When fixing a build error or changing an existing project, output only the files you change, each one complete.
- After the last file block write a short NOTES paragraph in Arabic (max 4 lines): what was built and what the user should know.

PROJECT RULES
- Makefile must follow this shape (replace MyTweak with the real name, keep the same name in the plist file name):
export THEOS_PACKAGE_SCHEME = roothide
ARCHS = arm64e
TARGET := iphone:clang:16.5:16.0
INSTALL_TARGET_PROCESSES = SpringBoard
include $(THEOS)/makefiles/common.mk
TWEAK_NAME = MyTweak
MyTweak_FILES = Tweak.x
MyTweak_CFLAGS = -fobjc-arc -Wno-deprecated-declarations
MyTweak_FRAMEWORKS = UIKit Foundation
include $(THEOS_MAKE_PATH)/tweak.mk
- control file fields: Package (reverse-DNS, lowercase, com.mody.xxx), Name, Version, Architecture: iphoneos-arm64e, Description, Maintainer: mody, Author: mody, Section: Tweaks, Depends: firmware (>= 16.0).
- MyTweak.plist is the injection filter, for example { Filter = { Bundles = ( "com.apple.springboard" ); }; } in old-style plist syntax. Filter only the processes the task needs.
- Use Logos (Tweak.x). Guard every hook: check classes exist with NSClassFromString before %init, check nil, never throw or crash in %ctor, keep %ctor light. A crash in SpringBoard causes a respring loop, so be defensive.
- For iOS-version-specific hooks use %group and call %init(Group) only after a runtime check with NSProcessInfo isOperatingSystemAtLeastVersion.
- Filesystem paths must be rootless: use jbroot() from <roothide.h> only when the code touches a jailbreak path.
- Use ARC. Prefix logs with the tweak name in NSLog.
- Do not add features the task did not ask for. Keep the code compact so the full answer fits in one reply.
"""

FILE_RE = re.compile(r"^=== FILE: (.+?) ===[ \t]*\n(.*?)\n=== END FILE ===[ \t]*$", re.S | re.M)
SKIP_DIRS = {".theos", "packages", ".git", "obj"}


def log(msg):
    print("[agent] " + msg, flush=True)


def call_gemini(contents):
    body = json.dumps({
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 32768},
    }).encode()
    last_err = "no attempt made"
    for attempt in range(2):
        for model in MODELS:
            url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model
            req = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers={"Content-Type": "application/json", "x-goog-api-key": KEY},
            )
            try:
                with urllib.request.urlopen(req, timeout=150) as resp:
                    data = json.loads(resp.read().decode())
                cand = data["candidates"][0]
                parts = cand.get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                if not text.strip():
                    last_err = "%s: empty reply (%s)" % (model, cand.get("finishReason"))
                    log(last_err)
                    continue
                log("model=%s finish=%s" % (model, cand.get("finishReason")))
                return text
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:200]
                last_err = "%s: HTTP %s %s" % (model, e.code, detail)
            except Exception as e:
                last_err = "%s: %s %s" % (model, type(e).__name__, e)
            log(last_err)
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(last_err)


def parse_files(text):
    files = {}
    for m in FILE_RE.finditer(text):
        path = m.group(1).strip().strip("`")
        lines = m.group(2).split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        files[path] = "\n".join(lines) + "\n"
    return files


def safe_path(rel):
    rel = rel.replace("\\", "/").lstrip("/")
    if rel.startswith(PROJECT + "/"):
        rel = rel[len(PROJECT) + 1:]
    parts = rel.split("/")
    if not rel or any(p in ("", ".", "..") or p.startswith(".git") for p in parts):
        return None
    return os.path.join(PROJECT, *parts)


def write_files(files):
    written = []
    for rel, body in files.items():
        path = safe_path(rel)
        if path is None:
            log("skipped unsafe path: %s" % rel)
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        written.append(os.path.relpath(path, PROJECT))
    return written


def read_existing():
    if not os.path.isdir(PROJECT):
        return ""
    chunks = []
    total = 0
    for root, dirs, names in os.walk(PROJECT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(names):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, PROJECT).replace(os.sep, "/")
            try:
                if os.path.getsize(full) > 100000:
                    continue
                with open(full, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception:
                continue
            if total + len(text) > 150000:
                continue
            total += len(text)
            chunks.append("=== FILE: %s ===\n%s\n=== END FILE ===" % (rel, text))
    return "\n\n".join(chunks)


def build():
    cmd = [
        "gmake", "clean", "package",
        "FINALPACKAGE=1",
        "THEOS_PACKAGE_SCHEME=roothide",
        "TARGET=iphone:clang:16.5:16.0",
    ]
    try:
        p = subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True, timeout=900)
        out = (p.stdout or "") + (p.stderr or "")
        code = p.returncode
    except subprocess.TimeoutExpired:
        out, code = "build timed out after 900 seconds", 1
    except FileNotFoundError as e:
        out, code = "build tool missing: %s" % e, 1
    debs = glob.glob(os.path.join(PROJECT, "packages", "*.deb"))
    return (code == 0 and bool(debs)), out, debs


def add_summary(text):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def main():
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", PROJECT):
        log("invalid project name (use letters, digits, - and _ only)")
        return 2
    if not KEY or not TASK:
        log("missing GEMINI_KEY or TASK")
        return 2

    os.makedirs("out", exist_ok=True)
    existing = read_existing()
    first = "TASK:\n%s\n\nProject folder name: %s\n" % (TASK, PROJECT)
    if existing:
        first += "\nThese are the files already in the project:\n\n" + existing
    else:
        first += "\nThe project folder is empty. Create every file needed from scratch."
    contents = [{"role": "user", "parts": [{"text": first}]}]

    try:
        for it in range(1, MAX_ITERS + 1):
            log("attempt %d of %d" % (it, MAX_ITERS))
            reply = call_gemini(contents)
            contents.append({"role": "model", "parts": [{"text": reply}]})
            files = parse_files(reply)
            if not files:
                contents.append({"role": "user", "parts": [{"text": "Your reply had no files in the required format. Reply again with every file as === FILE: path === ... === END FILE === blocks."}]})
                continue
            written = write_files(files)
            log("wrote: " + ", ".join(written))
            ok, out, debs = build()
            print(out[-4000:], flush=True)
            with open("out/build.log", "w", encoding="utf-8") as f:
                f.write(out[-20000:])
            if ok:
                for deb in debs:
                    shutil.copy(deb, "out/")
                notes = FILE_RE.sub("", reply).strip()[:3000]
                summary = "## Agent: build succeeded after %d attempt(s)\n\nProject: %s\n\n%s\n" % (it, PROJECT, notes)
                with open("out/agent_summary.md", "w", encoding="utf-8") as f:
                    f.write(summary)
                add_summary(summary)
                return 0
            contents.append({"role": "user", "parts": [{"text": "The build FAILED. Fix the errors. Output only the files you change, each one complete, in the same format.\n\nBUILD LOG (tail):\n" + out[-6000:]}]})
        add_summary("## Agent: build still failing after %d attempt(s)\n\nSee out/build.log in the artifact." % MAX_ITERS)
        return 1
    except Exception as e:
        log("stopped: %s" % e)
        with open("out/agent_error.txt", "w", encoding="utf-8") as f:
            f.write(str(e))
        add_summary("## Agent stopped\n\n%s" % e)
        return 1
    finally:
        shutil.rmtree(os.path.join(PROJECT, ".theos"), ignore_errors=True)
        shutil.rmtree(os.path.join(PROJECT, "packages"), ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
