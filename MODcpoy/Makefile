export THEOS_PACKAGE_SCHEME = roothide
ARCHS = arm64e
TARGET := iphone:clang:16.5:16.0
INSTALL_TARGET_PROCESSES = MobileSafari SafariViewService
include $(THEOS)/makefiles/common.mk

TWEAK_NAME = MODcpoy
MODcpoy_FILES = Tweak.x
MODcpoy_CFLAGS = -fobjc-arc -Wno-deprecated-declarations
MODcpoy_FRAMEWORKS = UIKit Foundation WebKit

include $(THEOS_MAKE_PATH)/tweak.mk
