#import <React/RCTBridgeModule.h>

@interface RCT_EXTERN_MODULE(RN02HandBenchmarkModule, NSObject)

RCT_EXTERN_METHOD(startHandBenchmark:(RCTPromiseResolveBlock)resolve
                  rejecter:(RCTPromiseRejectBlock)reject)

RCT_EXTERN_METHOD(stopHandBenchmark:(RCTPromiseResolveBlock)resolve
                  rejecter:(RCTPromiseRejectBlock)reject)

RCT_EXTERN_METHOD(getLatestHandBenchmark:(RCTPromiseResolveBlock)resolve
                  rejecter:(RCTPromiseRejectBlock)reject)

@end
