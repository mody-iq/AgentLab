#import <UIKit/UIKit.h>
#import <WebKit/WebKit.h>
#import <objc/runtime.h>

static char kMODcpoyInstalledKey;

static NSString * const kMODcpoyUserScriptSource =
    @"(function() {"
    @"  try {"
    @"    if (window.__MODcpoyInstalled) return;"
    @"    window.__MODcpoyInstalled = true;"
    @"    var stopProp = function(e) {"
    @"      if (e && e.stopImmediatePropagation) {"
    @"        e.stopImmediatePropagation();"
    @"      }"
    @"    };"
    @"    var events = ['copy', 'cut', 'contextmenu', 'selectstart', 'dragstart'];"
    @"    for (var i = 0; i < events.length; i++) {"
    @"      window.addEventListener(events[i], stopProp, true);"
    @"    }"
    @"    window.addEventListener('paste', function(e) {"
    @"      if (e && e.target) {"
    @"        var tag = e.target.tagName;"
    @"        if (tag === 'INPUT' || tag === 'TEXTAREA') {"
    @"          if (e.stopImmediatePropagation) {"
    @"            e.stopImmediatePropagation();"
    @"          }"
    @"        }"
    @"      }"
    @"    }, true);"
    @"    var injectStyle = function() {"
    @"      try {"
    @"        if (document.getElementById('__modcpoy_style')) return;"
    @"        var style = document.createElement('style');"
    @"        style.id = '__modcpoy_style';"
    @"        style.textContent = '* { -webkit-user-select: text !important; user-select: text !important; -webkit-touch-callout: default !important; }';"
    @"        var target = document.head || document.documentElement;"
    @"        if (target) {"
    @"          target.appendChild(style);"
    @"        }"
    @"      } catch (err) {}"
    @"    };"
    @"    if (document.head || document.documentElement) {"
    @"      injectStyle();"
    @"    }"
    @"    window.addEventListener('DOMContentLoaded', injectStyle, true);"
    @"    var cleanAttrs = function(node) {"
    @"      try {"
    @"        if (!node || node.nodeType !== 1) return;"
    @"        var attrs = ['oncopy', 'oncut', 'onpaste', 'oncontextmenu', 'onselectstart', 'ondragstart'];"
    @"        for (var i = 0; i < attrs.length; i++) {"
    @"          if (node.hasAttribute && node.hasAttribute(attrs[i])) {"
    @"            node.removeAttribute(attrs[i]);"
    @"          }"
    @"        }"
    @"        var children = node.children;"
    @"        if (children) {"
    @"          for (var j = 0; j < children.length; j++) {"
    @"            cleanAttrs(children[j]);"
    @"          }"
    @"        }"
    @"      } catch (err) {}"
    @"    };"
    @"    var cleanDocument = function() {"
    @"      try {"
    @"        document.oncopy = null;"
    @"        document.oncut = null;"
    @"        document.onpaste = null;"
    @"        document.oncontextmenu = null;"
    @"        document.onselectstart = null;"
    @"        document.ondragstart = null;"
    @"        if (document.documentElement) {"
    @"          cleanAttrs(document.documentElement);"
    @"        }"
    @"      } catch (err) {}"
    @"    };"
    @"    window.addEventListener('DOMContentLoaded', cleanDocument, true);"
    @"    if (typeof MutationObserver !== 'undefined') {"
    @"      var observer = new MutationObserver(function(mutations) {"
    @"        try {"
    @"          cleanDocument();"
    @"        } catch (err) {}"
    @"      });"
    @"      observer.observe(document, { childList: true, subtree: true, attributes: true });"
    @"    }"
    @"  } catch (err) {}"
    @"})();";

static void MODcpoyInstallUserScript(WKUserContentController *userContentController) {
    if (!userContentController) return;

    NSNumber *installed = objc_getAssociatedObject(userContentController, &kMODcpoyInstalledKey);
    if (installed && [installed boolValue]) return;

    objc_setAssociatedObject(userContentController, &kMODcpoyInstalledKey, @YES, OBJC_ASSOCIATION_RETAIN_NONATOMIC);

    WKUserScript *userScript = [[WKUserScript alloc] initWithSource:kMODcpoyUserScriptSource
                                                      injectionTime:WKUserScriptInjectionTimeAtDocumentStart
                                                   forMainFrameOnly:NO];
    [userContentController addUserScript:userScript];
}

%hook WKUserContentController

- (instancetype)init {
    self = %orig;
    if (self) {
        MODcpoyInstallUserScript(self);
    }
    return self;
}

%end

%hook WKWebView

- (instancetype)initWithFrame:(CGRect)frame configuration:(WKWebViewConfiguration *)configuration {
    if (configuration && configuration.userContentController) {
        MODcpoyInstallUserScript(configuration.userContentController);
    }
    return %orig(frame, configuration);
}

%end

%ctor {
    NSLog(@"[MODcpoy] Loaded into process");
    %init;
}
