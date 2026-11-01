#import <UIKit/UIKit.h>
#import <Foundation/Foundation.h>

@interface SpringBoard : UIApplication
@end

%hook SpringBoard

- (void)applicationDidFinishLaunching:(id)application {
    %orig;
    NSLog(@"[HelloMody] loaded");
}

%end

%ctor {
    if (NSClassFromString(@"SpringBoard")) {
        %init;
    }
}
