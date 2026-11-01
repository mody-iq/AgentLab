export THEOS_PACKAGE_SCHEME = roothide
ARCHS = arm64e
TARGET := iphone:clang:16.5:16.0
INSTALL_TARGET_PROCESSES = SpringBoard

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = UnlockTap
UnlockTap_FILES = Tweak.x
UnlockTap_CFLAGS = -fobjc-arc -Wno-deprecated-declarations
UnlockTap_FRAMEWORKS = UIKit Foundation

include $(THEOS_MAKE_PATH)/tweak.mk
