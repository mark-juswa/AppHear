import Foundation
import React

@objc(RN02HandBenchmarkModule)
final class RN02HandBenchmarkModule: NSObject {
  private let benchmark = RN02HandLandmarkerBenchmark()

  @objc
  static func requiresMainQueueSetup() -> Bool {
    false
  }

  @objc(startHandBenchmark:rejecter:)
  func startHandBenchmark(
    resolve: RCTPromiseResolveBlock,
    rejecter reject: RCTPromiseRejectBlock
  ) {
    do {
      try benchmark.start()
      resolve(nil)
    } catch {
      reject("rn02_start_failed", error.localizedDescription, error)
    }
  }

  @objc(stopHandBenchmark:rejecter:)
  func stopHandBenchmark(
    resolve: RCTPromiseResolveBlock,
    rejecter reject: RCTPromiseRejectBlock
  ) {
    do {
      resolve(try benchmark.stopDictionary())
    } catch {
      reject("rn02_stop_failed", error.localizedDescription, error)
    }
  }

  @objc(getLatestHandBenchmark:rejecter:)
  func getLatestHandBenchmark(
    resolve: RCTPromiseResolveBlock,
    rejecter reject: RCTPromiseRejectBlock
  ) {
    do {
      resolve(try benchmark.latestDictionary())
    } catch {
      reject("rn02_latest_failed", error.localizedDescription, error)
    }
  }
}
