import Foundation
import UIKit

#if canImport(MediaPipeTasksVision)
import MediaPipeTasksVision
#endif

private let rn02Schema = "apphear.rn02.ios_hand_landmarker.v1"
private let rn02Mode = "rn02_ios_hand_only"

final class RN02HandLandmarkerBenchmark {
  private let modelAssetName = "hand_landmarker"
  private let modelAssetExtension = "task"
  private let startedAtFormatter = ISO8601DateFormatter()
  private var startedAt: Date?
  private var latest: [String: Any]?

  #if canImport(MediaPipeTasksVision)
  private var handLandmarker: HandLandmarker?
  #endif

  func start() throws {
    #if canImport(MediaPipeTasksVision)
    guard let modelPath = Bundle.main.path(forResource: modelAssetName, ofType: modelAssetExtension) else {
      throw rn02Error("Missing hand_landmarker.task in the iOS app bundle")
    }

    let options = HandLandmarkerOptions()
    options.baseOptions.modelAssetPath = modelPath
    options.runningMode = .image
    options.numHands = 2
    options.minHandDetectionConfidence = 0.5
    options.minHandPresenceConfidence = 0.5
    options.minTrackingConfidence = 0.5

    handLandmarker = try HandLandmarker(options: options)
    let now = Date()
    startedAt = now
    latest = makeSession(startedAt: now, endedAt: nil, notes: [
      "RN02 native module loaded MediaPipe hand_landmarker.task.",
      "Camera sample-buffer processing is intentionally not implemented yet.",
      "This is not a recognition result and does not exercise the 258-feature contract."
    ])
    #else
    throw rn02Error("MediaPipeTasksVision is not available. Run pod install on macOS first.")
    #endif
  }

  func stopDictionary() throws -> [String: Any] {
    guard let startedAt else {
      throw rn02Error("RN02 hand benchmark has not been started")
    }

    #if canImport(MediaPipeTasksVision)
    handLandmarker = nil
    #endif

    let session = makeSession(startedAt: startedAt, endedAt: Date(), notes: [
      "RN02 stopped after verifying native module/model-load path.",
      "Processed frame count is zero until native camera sample-buffer ingestion is added."
    ])
    latest = session
    self.startedAt = nil
    return session
  }

  func latestDictionary() throws -> [String: Any]? {
    latest
  }

  private func makeSession(startedAt: Date, endedAt: Date?, notes: [String]) -> [String: Any] {
    var session: [String: Any] = [
      "schema": rn02Schema,
      "mode": rn02Mode,
      "startedAtIso": startedAtFormatter.string(from: startedAt),
      "devicePlatform": "ios",
      "deviceModel": UIDevice.current.model,
      "runningMode": "image",
      "modelAsset": "\(modelAssetName).\(modelAssetExtension)",
      "samples": [],
      "notes": notes
    ]
    if let endedAt {
      session["endedAtIso"] = startedAtFormatter.string(from: endedAt)
    }
    return session
  }

  private func rn02Error(_ message: String) -> NSError {
    NSError(domain: "AppHearRN02", code: 1, userInfo: [NSLocalizedDescriptionKey: message])
  }
}
