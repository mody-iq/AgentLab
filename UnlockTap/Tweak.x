#import <UIKit/UIKit.h>
#import <Foundation/Foundation.h>
#import <notify.h>

%ctor {
    if (!NSClassFromString(@"SpringBoard")) {
        return;
    }

    static uint64_t previousState = UINT64_MAX;
    int token = 0;
    notify_register_dispatch("com.apple.springboard.lockstate", &token, dispatch_get_main_queue(), ^(int tokenOut) {
        uint64_t state = 0;
        if (notify_get_state(tokenOut, &state) == NOTIFY_STATUS_OK) {
            if (previousState == 1 && state == 0) {
                UIImpactFeedbackGenerator *generator = [[UIImpactFeedbackGenerator alloc] initWithStyle:UIImpactFeedbackStyleLight];
                [generator prepare];
                [generator impactOccurred];
            }
            previousState = state;
        }
    });
}
