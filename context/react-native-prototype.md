# React Native iPhone Prototype Experiment

Status: **RN01 ANDROID BENCHMARK PASS / IPHONE PENDING**. This is a separate prototype under
`apphear-react/`, not a replacement for the native Android runtime under `android/`.

This file is the source of truth for any React Native or iPhone experiment. Read it before
creating files under `apphear-react/`, before proposing iOS changes, and before comparing phone
performance. Do not re-derive the plan from memory.

---

## Implementation Status

As of 2026-07-18, RN01 has a separate `apphear-react/` scaffold with React Native 0.86,
VisionCamera frame-output instrumentation, benchmark-session export, TypeScript, linting, and
generated native `android/` + `ios/` project shells. `npm run typecheck`, `npm run lint`, a Metro
Android bundle check, and a one-ABI Android debug build are green. The APK exists at `apphear-react/android/app/build/outputs/apk/debug/app-debug.apk`. Android physical-device RN01 benchmark has passed on Xiaomi M2101K7AG: 1-min 30.02 FPS avg / 0 drops, 3-min 30.00 FPS avg / 0 drops, 5-min 30.01 FPS avg / 0 drops, actual frame 800x480. iOS still needs CocoaPods/Xcode validation and physical iPhone benchmarking on macOS. RN02 scaffold/protocol/assets are prepared, but RN02 is not implemented or passed.


## RN01 Android Benchmark Result

Status: **PASS for Android camera-callback smoke only**. Device: Xiaomi `M2101K7AG` /
`sunny_global`, front camera, requested 60 FPS, target `480x854`, actual frame `800x480`.
Raw exports and summary are stored under
`apphear-react/benchmark/device-results/android-m2101k7ag-rn01-2026-07-19/`.

| Run | Elapsed | Frames | Avg FPS | FPS Range | Drops |
|---|---:|---:|---:|---:|---:|
| 1 min | 62.1s | 1,864 | 30.02 | 29.76-30.88 | 0 |
| 3 min | 186.0s | 5,580 | 30.00 | 29.00-30.94 | 0 |
| 5 min | 307.8s | 9,237 | 30.01 | 29.53-31.01 | 0 |

Interpretation: React Native plus VisionCamera frame output is stable on this Android phone for
RN01. Requested 60 FPS negotiated to stable 30 FPS. This is **not** MediaPipe, landmark, feature, or
recognition FPS. The full RN01 gate remains incomplete until physical iPhone logs exist.
## Purpose

The current Android runtime is correct enough to measure, but tested Android phones are only
processing roughly **5-9 FPS** through the full hand+pose recognition path. Recent controlled
profiling shows:

- camera input is higher than processed FPS, so camera buffering is not the main suspect;
- MediaPipe hand + pose landmarking dominates wall time;
- TFLite recognition is cheap, about 1-2 ms/tick;
- low FPS plus thermal/sustained-load dips make short signs hard to resolve.

The experiment asks one narrow question:

**Can an iPhone-capable React Native prototype, with native vision processing underneath, sustain
materially better landmark FPS and recognition behavior than the current Android baseline while
preserving the same AppHear 3 feature contract?**

React Native is being evaluated as an app shell and cross-platform wrapper, not as a real-time
vision engine.

---

## Non-Goals

- Do not migrate, rewrite, or replace the native Android Studio project.
- Do not modify `android/` as part of this prototype unless explicitly requested.
- Do not change the deployed model, vocabulary, feature contract, dataset, or training pipeline.
- Do not process camera frames through normal JavaScript state or the React Native bridge.
- Do not send raw frames or per-frame landmark arrays to React Native except in a throttled debug
  mode.
- Do not start with ONNX conversion, raw RGB models, CTC, ST-GCN, or a new feature schema.
- Do not claim React Native solves FPS. Only device measurements can show that.

---

## Current Baseline To Preserve

Production Android path:

```text
CameraX frame
  -> MediaPipe HandLandmarker + PoseLandmarker
  -> SessionNormalizer / S4 features
  -> S5 signing detector
  -> [1, 96, 258] TFLite recognizer
  -> S7 confirmation
  -> S8 sentence/UI
```

Current deployed contract:

| Item | Value |
|---|---|
| schema_version | `3.0` |
| feature_dim | `258` |
| time_window | `96` |
| classes | `236` |
| model I/O | float32 input/output, INT8 internals |
| model file | `streaming.tflite` |
| manifest | `model_manifest.json` |
| config | `recognition_config.json` |
| landmark blocks | hand L 63, hand R 63, pose 132 |
| runtime principle | pose and hand blocks are never dropped |

Any prototype that reaches recognition must load and validate the same manifest before inference.
If it cannot produce this contract, it is not testing the same recognition idea.

---

## Architecture Decision

Use React Native only for:

- app shell;
- camera permission/start/stop controls;
- settings such as handedness, mode, and profiling flags;
- result display;
- benchmark log display/export.

Keep the hot path native:

- camera frame access;
- frame throttling and busy/drop policy;
- MediaPipe hand and pose landmarking;
- landmark slot ordering and missing-data handling;
- S4 feature construction;
- S5 signing detector;
- `[96,258]` ring buffer;
- TFLite inference;
- S7 confirmation;
- profiling.

React Native receives compact snapshots only:

```text
processed_fps, capture_fps, dropped_frames, low_fps,
hand_ms_p50/p95, pose_ms_p50/p95, wall_ms_p50/p95,
top_candidates, committed_gloss, sentence_text
```

---

## Proposed Folder Structure

Prototype root:

```text
apphear-react/
  README.md
  package.json
  app.json or react-native.config.js
  src/
    app/
    screens/
    components/
    stores/
    native/
      AppHearVisionModule.ts
    types/
      recognition.ts
  native/
    shared/
      FeatureContract.h
      RingBuffer.h
      RecognitionTypes.h
    ios/
      AppHearVisionEngine.swift
      MediaPipeHandPoseService.swift
      TfliteRecognizer.swift
      SessionNormalizerSwift.swift
      SigningDetectorSwift.swift
      ConfirmationSwift.swift
      Profiler.swift
    android/
      AppHearVisionEngine.kt
      MediaPipeHandPoseService.kt
      TfliteRecognizer.kt
  assets/
    mediapipe/
      hand_landmarker.task
      pose_landmarker_lite.task
    model/
      streaming.tflite
      model_manifest.json
      vocab.json
      recognition_config.json
  benchmark/
    protocols/
    device-results/
```

Keep this structure separate. Shared logic may be copied or ported from `android/` only with a
clear parity test; do not import production Android source in a way that makes the prototype a
hidden dependency of the production app.

---

## Recommended Libraries

Use current documentation at build time; these libraries change quickly.

Initial choices:

- React Native with TypeScript, preferably new architecture enabled.
- `react-native-vision-camera` for Phase 1 camera preview and FPS smoke test.
- Native iOS `MediaPipeTasksVision` for HandLandmarker and PoseLandmarker.
- Native Android `com.google.mediapipe:tasks-vision` if the prototype adds Android parity.
- Native TFLite first for inference; keep the deployed `.tflite` model.

Deferred or fallback choices:

- `react-native-fast-tflite` only for experiments where inference is inside a frame processor and
  parity is still checked. The deployed recognizer is already cheap, so this is not the first lever.
- ONNX Runtime only if TFLite on iOS is blocked. ONNX conversion creates a new parity surface and
  does not address the MediaPipe bottleneck.
- Core ML / Metal / GPU delegates only behind flags after CPU/TFLite baseline numbers exist.

---


## RN02 Scaffold Status

Developer direction on 2026-07-19 skipped the iPhone RN01 benchmark for now and proceeded to RN02
preparation. This is a conscious deviation from the original RN01 pass condition. RN02 may be
scaffolded, but it is **not passed** until it runs on a physical iPhone.

Prepared scaffold:

- `apphear-react/benchmark/protocols/rn02-ios-hand-only.md`
- `apphear-react/src/types/rn02HandBenchmark.ts`
- `apphear-react/native/ios/RN02HandLandmarkerBenchmark.swift`
- `apphear-react/assets/mediapipe/hand_landmarker.task`
- `apphear-react/ios/Podfile` includes `pod 'MediaPipeTasksVision'`

Current library guidance checked on 2026-07-19: Google MediaPipe iOS Hand Landmarker docs specify
`MediaPipeTasksVision` via CocoaPods, `HandLandmarkerOptions`, `BaseOptions.modelAssetPath`,
`numHands`, confidence thresholds, and running modes `.image`, `.video`, and `.liveStream`.
Baseline RN02 remains `.image`; video/live stream are later logged sub-experiments because they can
introduce tracking behavior.
## MediaPipe Integration Approach

First benchmark with MediaPipe Tasks **IMAGE** mode because it best matches the current offline and
Android landmark dialect.

Allowed later as explicit sub-experiments:

- `VIDEO` mode;
- `LIVE_STREAM` mode;
- pose cadence with held pose.

These modes must be logged as separate benchmark modes because they can introduce hidden tracking
or smoothing. If they improve FPS but alter landmark behavior, run a parity/skew check before using
them for recognition.

On iOS, prefer direct native capture to `CMSampleBuffer` / `CVPixelBuffer`, convert to `MPImage`,
and keep conversion on a background/native queue. Do not round-trip frames through JavaScript.

---

## Native Module Responsibilities

### iOS

- Own AVFoundation capture or a VisionCamera native frame processor/plugin.
- Request camera frames in a format MediaPipe accepts efficiently.
- Run hand and pose landmarkers off the main thread.
- Preserve AppHear hand and pose array layout:
  - hands: `(2, 21, 3)`;
  - pose: `(33, 4)`.
- Port or share S4 session normalization.
- Port S5 signing detection and S7 confirmation.
- Load `streaming.tflite` asynchronously.
- Validate `model_manifest.json` before inference.
- Emit compact snapshots to React Native.
- Record p50 and p95 latency for capture, conversion, hand, pose, recognition, and wall time.

### Android Prototype

- If built, mirror the production runtime behavior for comparison, but do not modify `android/`.
- Keep the same stage names and benchmark fields as iOS.
- Use it to check whether React Native shell overhead affects Android relative to the native app.

---

## React Native Responsibilities

- Start/stop camera session.
- Show permission and warm-up states.
- Show FPS, low-FPS state, dropped frames, p50/p95 latencies.
- Show top-3 candidates, committed gloss, and sentence text.
- Expose handedness setting.
- Export benchmark logs.
- Keep render frequency throttled; UI should not update on every camera frame unless the snapshot
  rate is explicitly capped.

---

## Phased Roadmap

### Phase 1 - React Native camera and FPS smoke test

Build only the app shell and camera preview. Measure:

- capture FPS;
- preview FPS;
- dropped frames;
- device model;
- resolution;
- thermal/sustained behavior over 1, 3, and 5 minutes.

No MediaPipe, no model, no recognition.

Pass condition: one physical iPhone and one Android device can produce comparable logs from the
prototype.

### Phase 2 - iOS MediaPipe hand-only landmark test

Add native iOS HandLandmarker only. Measure:

- hand p50/p95 latency;
- processed FPS;
- frame drops;
- conversion cost;
- detection hit rate.

Pass condition: hand-only FPS is clearly above the current full Android bottleneck and has stable
p95 under sustained use.

### Phase 3 - iOS hand + pose landmark test

Add PoseLandmarker and run hand+pose. Measure:

- hand p50/p95;
- pose p50/p95;
- total wall p50/p95;
- processed FPS;
- pose cadence variants only after full-rate baseline.

Pass condition: hand+pose on iPhone is meaningfully better than Android and ideally sustains
`>=15 FPS`.

### Phase 4 - 258-feature construction

Port S4/session normalization and build golden-vector tests against existing AppHear fixtures.

Pass condition: same landmarks produce the same 258-feature vectors within the existing tolerance.

### Phase 5 - same model inference test

Load the deployed TFLite model and manifest. Run inference on a zero-padded `[1,96,258]` window.

Pass condition:

- manifest validation passes;
- output shape is `[1,96,236]`;
- inference latency remains minor relative to landmarking;
- no schema mismatch is tolerated.

### Phase 6 - temporal buffering, onset, confirmation, and UI result display

Port S5, ring buffering, S7, top-3 candidates, committed gloss, handedness, and sentence display.

Pass condition: the prototype can commit known conversational vocabulary signs without JS-frame
processing and logs the same diagnostic fields as Android.

### Phase 7 - side-by-side benchmark against Android baseline

Run the same protocol on:

- current native Android app;
- React Native prototype on Android, if implemented;
- React Native/native iOS prototype on iPhone.

Use the same signer, signs, distance, lighting, front/back camera convention, cool-start run, and
sustained run.

Pass condition: iPhone shows materially better processed FPS and equal-or-better recognition
behavior without contract drift.

---

## Benchmark Protocol

Required metrics:

- capture FPS;
- processed FPS;
- skipped/dropped frames;
- conversion/rotation time;
- hand latency p50/p95;
- pose latency p50/p95;
- recognition latency p50/p95;
- wall latency p50/p95;
- low-FPS enter/exit events;
- thermal/sustained degradation notes;
- sign-level top-3 candidates;
- commit frame;
- commit/drop reason;
- final gloss correctness for the controlled sign list.

Suggested controlled sign list should include:

- signs that currently work well: `CUT`, `IMPORTANT`, `SELL`, `WANT2`;
- known confusion clusters: `KNOW`, `STRONG`, `STREET`, `MUCH`, `ROAD`, `START`, `THEN`.

Do not report accuracy as a headline from one local signer. This prototype is a performance and
behavior experiment. Any accuracy claim still follows `eval-protocol.md`.

---

## Success Criteria

The experiment is worth continuing if:

- iPhone hand+pose processed FPS is sustained near or above `15 FPS`; or
- iPhone sustains `10-14 FPS` with much better p95 and thermal stability than Android; and
- S4 parity passes; and
- model inference remains cheap; and
- recognition behavior is not worse than Android on the controlled sign list.

Stop or fallback if:

- iPhone hand+pose stays near the same `5-9 FPS` range;
- MediaPipe iOS integration requires tracked/video mode that cannot pass skew checks;
- Swift S4 parity cannot be made reliable;
- React Native bridge/frame transfer becomes part of the hot path;
- native module complexity exceeds the value of the experiment.

---

## Fallback Plan

If React Native cannot meet performance or integration requirements:

1. Keep the production native Android app unchanged.
2. Treat the result as evidence that the bottleneck is MediaPipe/hardware, not UI framework.
3. If iPhone FPS is promising but React Native integration is the problem, build a small native iOS
   Swift prototype instead of forcing React Native.
4. If iPhone FPS is not promising, return to Android-side levers already tracked in
   `recognition-accuracy.md`: better hardware, measured landmarker modes, and model/data work.

---

## First Milestone

Build Phase 1 only:

**`apphear-react` camera preview + FPS dashboard + benchmark log export on one physical iPhone and
one Android device.**

No MediaPipe, no TFLite, no recognition. The result should answer whether the prototype environment
is ready for the real iOS MediaPipe hand-only latency test.

## RN02 Source Wiring Status

As of 2026-07-19, RN02 is wired at source level but is not a passed benchmark.

Implemented in `apphear-react/` only:

- iOS Podfile dependency: `MediaPipeTasksVision`.
- iOS target source files:
  - `ios/AppHearReactPrototype/RN02HandBenchmarkModule.m`
  - `ios/AppHearReactPrototype/RN02HandBenchmarkModule.swift`
  - `ios/AppHearReactPrototype/RN02HandLandmarkerBenchmark.swift`
- Bundled iOS resource: `ios/AppHearReactPrototype/hand_landmarker.task`, copied from `assets/mediapipe/hand_landmarker.task` with matching SHA256.
- JS typed wrapper: `src/native/AppHearVisionModule.ts` exports `Rn02HandBenchmarkModule`.
- UI entry point: `src/screens/Rn02HandSmokeScreen.tsx`, reachable through the RN01/RN02 switch in `App.tsx`.

Current capability:

- loads `hand_landmarker.task` through MediaPipe HandLandmarker in `.image` mode;
- exports only compact session dictionaries to React Native;
- records zero processed frames until native camera sample-buffer ingestion is added.

Still pending:

- native iOS camera frames must be requested as `kCVPixelFormatType_32BGRA` before converting to MediaPipe `MPImage`;

- macOS `pod install` and Xcode compile validation;
- physical iPhone run;
- native `CMSampleBuffer`/`CVPixelBuffer` ingestion;
- p50/p95 hand latency, processed FPS, hit rate, and sustained 1/3/5-minute RN02 logs.

Do not treat RN02 as passing Phase 2 until those pending items are complete.


## RN02 Android Model-Load Status

As of 2026-07-19, iPhone testing is intentionally skipped because no iPhone is available. To keep momentum without guessing about iOS performance, RN02 has an Android native model-load slice in the separate React Native prototype.

Implemented in `apphear-react/` only:

- `android/app/src/main/java/com/apphear/reactprototype/AppHearVisionPackage.kt`
- `android/app/src/main/java/com/apphear/reactprototype/RN02HandBenchmarkModule.kt`
- `android/app/src/main/assets/hand_landmarker.task`
- RN prototype Gradle dependency: `com.google.mediapipe:tasks-vision:latest.release`
- `src/screens/Rn02HandSmokeScreen.tsx` can call the native module on Android or iOS.
- `src/types/rn02HandBenchmark.ts` now allows Android and iOS hand-only benchmark modes.

Current capability:

- creates a native Android `HandLandmarker` in `RunningMode.IMAGE` with `numHands=2` and confidence thresholds `0.5`;
- loads the same `hand_landmarker.task` asset from Android app assets;
- returns compact benchmark session dictionaries to React Native;
- records zero processed frames until native camera `ImageProxy` ingestion is added.

Validated on Windows/Android build host:

- `npm run typecheck` passed;
- `npm run lint` passed;
- Android debug APK build passed for `arm64-v8a`;
- Android model asset SHA256 matches the RN prototype asset copy.

Still pending before any FPS conclusion:

- install/run the rebuilt APK on the physical Android device;
- tap RN02 and confirm native model load succeeds;
- add native camera/ImageAnalysis ingestion and actual HandLandmarker detection timing;
- export 1/3/5-minute hand-only latency logs.
## RN02 Android Native Hand-Only CameraX Status

As of 2026-07-19, RN02 Android has moved beyond model-load and now has a native hand-only CameraX benchmark path. This remains inside `apphear-react/` and is not a production Android migration.

Implemented:

- CameraX `ImageAnalysis` bound from `RN02HandBenchmarkModule.kt` to the active React Activity lifecycle.
- Analyzer settings:
  - `OUTPUT_IMAGE_FORMAT_RGBA_8888`
  - `STRATEGY_KEEP_ONLY_LATEST`
  - target resolution request `480x854`
  - front camera selector
- Native frame path:
  - `ImageProxy` -> `Bitmap` -> MediaPipe `MPImage`
  - `HandLandmarker.detect()` in `RunningMode.IMAGE`
- Aggregated metrics:
  - processed frames
  - skipped frames
  - processed FPS
  - hand latency p50/p95
  - hand hit rate
  - two-hand hit rate
  - frame width/height
- React Native polling:
  - RN polls compact benchmark state once per second while running.
  - Raw frames and per-frame landmarks do not cross the bridge.

Validated locally:

- `npm run typecheck` passed.
- `npm run lint` passed.
- Android debug build passed for `arm64-v8a`.

Still pending before conclusions:

- physical Android device run after APK reinstall;
- 1-minute, 3-minute, and 5-minute RN02 JSON exports;
- interpretation against RN01 camera FPS and native Android recognition FPS;
- pose, 258-feature construction, TFLite inference, temporal buffering, and recognition are still not implemented in RN02.
## RN02 Android First Hand-Only Result

First native Android RN02 hand-only CameraX run, saved at `apphear-react/benchmark/device-results/android-m2101k7ag-rn02-hand-2026-07-19/`:

| Duration | Frames | Processed FPS | P50 hand latency | P95 hand latency | Skipped | Actual frame |
|---:|---:|---:|---:|---:|---:|---|
| 75.424s | 735 | 9.74 | 71.33ms | 97.91ms | 0 | 720x1280 |

Notes:

- This proves the RN02 native Android CameraX -> MediaPipe hand-only path runs on device.
- It does not prove full recognition FPS because pose, feature construction, TFLite, temporal logic, and confirmation are absent.
- Hand hit rate was only 2.59%, but the run was not a controlled hand-visible signing run; do not use it as a detector-quality conclusion.
- The camera delivered 720x1280 despite the 480x854 target request, so a future optimization should explicitly test lower analyzer resolutions before pose is added.
- Stop cleanup was fixed after this run by moving CameraX `unbindAll()` onto the Android main thread.
## RN02 Android Sustained Hand-Only Verdict

RN02 Android hand-only sustained logs, saved at `apphear-react/benchmark/device-results/android-m2101k7ag-rn02-hand-2026-07-19/`:

| Run | Duration | Frames | Processed FPS | P50 hand latency | P95 hand latency | Skipped | Actual frame |
|---|---:|---:|---:|---:|---:|---:|---|
| 1-min export | 75.424s | 735 | 9.74 | 71.33ms | 97.91ms | 0 | 720x1280 |
| 3-min export | 151.656s | 1403 | 9.25 | 80.24ms | 126.79ms | 0 | 720x1280 |
| 5-min export | 302.751s | 2764 | 9.13 | 79.92ms | 132.61ms | 0 | 720x1280 |

Interpretation:

- The native Android RN02 CameraX -> HandLandmarker path is stable over five minutes.
- Stop cleanup is fixed; stopped exports include `endedAtIso`.
- Sustained hand-only processed FPS is about 9 FPS, below the experiment target of 15 FPS.
- Longer runs show higher p95 latency, suggesting thermal/load sensitivity even before pose or recognition.
- CameraX delivered 720x1280 frames despite the lower target request; this is the first optimization target.
- These results are hand-only and cannot be used as full recognition FPS or accuracy evidence.

Next decision:

Before adding pose, run a resolution-control slice that forces or selects a smaller analyzer frame size and repeats a shorter RN02 hand-only benchmark. If 720x1280 remains unavoidable or lower resolution does not improve p95/FPS materially, adding pose is unlikely to meet the 15 FPS gate on this Android device.