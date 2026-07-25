# RN02 iOS MediaPipe Hand-Only Protocol

Purpose: measure native iOS MediaPipe HandLandmarker latency before adding pose, features, TFLite,
or recognition.

## Status

Planned scaffold only. The developer explicitly chose to skip RN01 iPhone camera baseline for now,
so RN02 work is a conscious deviation from the original gate. RN02 cannot be marked passed until it
runs on a physical iPhone.

## Scope

Allowed:

- Native iOS HandLandmarker only.
- Same `hand_landmarker.task` asset copied from repo `assets/mediapipe/`.
- Native frame processing on iOS; React Native receives compact benchmark snapshots only.
- Metrics: processed FPS, hand latency p50/p95, dropped/skipped frames, hit rate, frame size.

Not allowed:

- Pose Landmarker.
- S4 258-feature construction.
- TFLite or recognition.
- Raw frame or per-frame landmark arrays through React Native state/bridge.
- Accuracy claims.

## iOS Setup

On macOS:

```bash
cd apphear-react/ios
pod install
```

If CocoaPods requires frameworks for `MediaPipeTasksVision`, use the React Native-supported linkage
mode for the project, for example:

```bash
USE_FRAMEWORKS=static pod install
```

Then open the generated `AppHearReactPrototype.xcworkspace` for CocoaPods builds.

## Native Configuration

HandLandmarker baseline configuration:

MediaPipe iOS requires `MPImage` sample-buffer/pixel-buffer inputs to use `kCVPixelFormatType_32BGRA` for HandLandmarker detection. RN02 native camera ingestion must request BGRA output from `AVCaptureVideoDataOutput`; do not send camera frames through React Native.

- library: `MediaPipeTasksVision`
- model: `hand_landmarker.task`
- running mode for first parity-style timing: `.image`
- `numHands = 2`
- min hand detection confidence = `0.5`
- min hand presence confidence = `0.5`
- min tracking confidence = `0.5`

`VIDEO` or `liveStream` modes are later sub-experiments and must be logged separately because they
can introduce tracking behavior that differs from the Android IMAGE-mode baseline.

## Required Output Schema

```json
{
  "schema": "apphear.rn02.ios_hand_landmarker.v1",
  "mode": "rn02_ios_hand_only",
  "devicePlatform": "ios",
  "deviceModel": "...",
  "runningMode": "image",
  "modelAsset": "hand_landmarker.task",
  "samples": [
    {
      "elapsedMs": 1000,
      "processedFrames": 15,
      "skippedFrames": 0,
      "handLatencyMsP50": 12.3,
      "handLatencyMsP95": 18.9,
      "processedFps": 15.0,
      "handHitRate": 0.94,
      "twoHandHitRate": 0.72,
      "frameWidth": 800,
      "frameHeight": 480
    }
  ],
  "notes": []
}
```

## Pass Criteria

- Runs on a physical iPhone with no crash.
- Native hand-only path sustains materially above the current Android full hand+pose bottleneck.
- p50 and p95 hand latency are reported.
- React Native receives only compact snapshots.
- No pose/model/recognition code is present.
