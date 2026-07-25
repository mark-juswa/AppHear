// RN02 scaffold: native iOS hand-only benchmark for AppHear React Prototype.
// This file documents the intended implementation surface. It is not wired into
// the Xcode project until macOS/CocoaPods validation is available.

#if canImport(MediaPipeTasksVision)
import Foundation
import MediaPipeTasksVision

struct RN02HandBenchmarkSample: Codable {
  let elapsedMs: Int
  let processedFrames: Int
  let skippedFrames: Int
  let handLatencyMsP50: Double
  let handLatencyMsP95: Double
  let processedFps: Double
  let handHitRate: Double
  let twoHandHitRate: Double
  let frameWidth: Int?
  let frameHeight: Int?
}

struct RN02HandBenchmarkSession: Codable {
  let schema: String
  let mode: String
  let startedAtIso: String
  var endedAtIso: String?
  let devicePlatform: String
  let deviceModel: String?
  let runningMode: String
  let modelAsset: String
  var samples: [RN02HandBenchmarkSample]
  var notes: [String]
}

final class RN02HandLandmarkerBenchmark {
  private let modelAssetName = "hand_landmarker"
  private let modelAssetExtension = "task"
  private var handLandmarker: HandLandmarker?

  func loadImageModeHandLandmarker() throws {
    guard let modelPath = Bundle.main.path(forResource: modelAssetName, ofType: modelAssetExtension) else {
      throw NSError(domain: "AppHearRN02", code: 1, userInfo: [NSLocalizedDescriptionKey: "Missing hand_landmarker.task in app bundle"])
    }

    let options = HandLandmarkerOptions()
    options.baseOptions.modelAssetPath = modelPath
    options.runningMode = .image
    options.numHands = 2
    options.minHandDetectionConfidence = 0.5
    options.minHandPresenceConfidence = 0.5
    options.minTrackingConfidence = 0.5
    handLandmarker = try HandLandmarker(options: options)
  }

  // Planned hot path:
  // 1. Receive native CVPixelBuffer/CMSampleBuffer from AVFoundation or a native camera module.
  // 2. Convert to MPImage on a native background queue.
  // 3. Call handLandmarker.detect(image:) in IMAGE mode for baseline timing.
  // 4. Record p50/p95 latency, hit rate, two-hand hit rate, processed FPS, skipped frames.
  // 5. Emit only compact RN02HandBenchmarkSession snapshots to React Native.
  func detectPlaceholder() throws {
    guard handLandmarker != nil else {
      throw NSError(domain: "AppHearRN02", code: 2, userInfo: [NSLocalizedDescriptionKey: "HandLandmarker not loaded"])
    }
  }
}
#endif