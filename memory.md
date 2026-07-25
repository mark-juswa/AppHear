# Memory - RN02 Android Sustained Hand-Only Verdict

Last updated: 2026-07-19 23:10 +08:00

## Results saved
- Directory: `apphear-react/benchmark/device-results/android-m2101k7ag-rn02-hand-2026-07-19/`
- Files: `rn02-hand-1min-raw.json`, `rn02-hand-3min-raw.json`, `rn02-hand-5min-raw.json`, plus summary JSON files.

## Sustained RN02 hand-only numbers
- 1-min export: 75.424s, 735 frames, 9.74 FPS, p50 71.33ms, p95 97.91ms, skipped 0, 720x1280.
- 3-min export: 151.656s, 1403 frames, 9.25 FPS, p50 80.24ms, p95 126.79ms, skipped 0, 720x1280. Not a full 180s run.
- 5-min export: 302.751s, 2764 frames, 9.13 FPS, p50 79.92ms, p95 132.61ms, skipped 0, 720x1280.

## Verdict
- RN02 Android native hand-only CameraX + MediaPipe path is stable.
- Stop/main-thread unbind fix is confirmed by stopped exports.
- Sustained hand-only FPS is about 9 FPS, below the 15 FPS target.
- Longer runs raise p95 latency before pose or recognition is added.
- CameraX delivers 720x1280 despite requesting 480x854, likely limiting performance.

## Next
- Do not add pose yet.
- First implement a resolution-control experiment for RN02 Android hand-only, then repeat a short benchmark.
- If lower analyzer resolution cannot materially improve FPS/p95, Android RN prototype will not meet the performance goal for full hand+pose recognition on this device.

---# Memory - RN02 Android First Hand-Only Run + Stop Fix

Last updated: 2026-07-19 22:55 +08:00

## Result
- First RN02 Android native hand-only CameraX export saved under `apphear-react/benchmark/device-results/android-m2101k7ag-rn02-hand-2026-07-19/`.
- Xiaomi `M2101K7AG`, 75.424s, 735 processed frames, 9.74 processed FPS, p50 71.33ms, p95 97.91ms, skipped 0, actual frame 720x1280.
- Hand hit rate was 2.59% and two-hand hit rate 0%, but the run was not controlled with visible hands, so this is not a detector-quality conclusion.

## Fix
- Stop errored because CameraX `unbindAll()` requires the Android main thread.
- Fixed `RN02HandBenchmarkModule.closeRuntime()` to run `unbindAll()` through `ContextCompat.getMainExecutor(reactContext)` when called off-main-thread.
- Rebuilt successfully after the fix.

## Verification
- `npm run typecheck` passed.
- `npm run lint` passed.
- Android `assembleDebug` passed.

## Next
- Reinstall rebuilt APK and verify Stop no longer errors.
- Repeat RN02 1-minute test with hands clearly visible to sanity-check hit rate.
- Then run 3-minute and 5-minute hand-only benchmarks.
- Consider a lower CameraX analyzer resolution because device delivered 720x1280 despite requesting 480x854.

---# Memory - RN02 Android Native Hand-Only CameraX Slice

Last updated: 2026-07-19 18:35 +08:00

## What was built
- Advanced RN02 Android from model-load to native hand-only CameraX frame processing inside `apphear-react/`.
- `RN02HandBenchmarkModule.kt` now binds CameraX `ImageAnalysis`, converts RGBA `ImageProxy` frames to `Bitmap`, builds MediaPipe `MPImage`, and runs `HandLandmarker.detect()` in `RunningMode.IMAGE` on a background executor.
- Metrics accumulated natively: processed frames, skipped frames, processed FPS, hand p50/p95 latency, hand hit rate, two-hand hit rate, frame size.
- `Rn02HandSmokeScreen.tsx` polls compact native benchmark state once per second while running.
- Added explicit CameraX dependencies in the RN prototype Android Gradle module.

## Verification
- `npm run typecheck` passed.
- `npm run lint` passed.
- `./gradlew.bat assembleDebug -PreactNativeArchitectures=arm64-v8a --console=plain --no-daemon --max-workers=2` passed.

## Next session starts with
- Reinstall the rebuilt APK on the Android phone.
- Start Metro with reset cache.
- Open RN02 and press Start.
- Confirm `Samples` increments and FPS/P50/P95 become numeric.
- Export 1-minute, 3-minute, and 5-minute RN02 hand-only logs.

## Guardrails
- No production Android app files changed.
- No pose, 258 features, TFLite, recognition, dataset, or training pipeline changes.
- RN02 hand-only FPS cannot be interpreted as full recognition FPS.

---# Memory - RN02 Android Model-Load Slice

Last updated: 2026-07-19 17:58 +08:00

## What was built
- User has no iPhone available today and chose to skip iOS testing for now.
- Advanced RN02 on Android inside the separate `apphear-react/` prototype only.
- Added Android native module/model-load wiring:
  - `android/app/src/main/java/com/apphear/reactprototype/AppHearVisionPackage.kt`
  - `android/app/src/main/java/com/apphear/reactprototype/RN02HandBenchmarkModule.kt`
  - `MainApplication.kt` registers `AppHearVisionPackage()`
  - `android/app/src/main/assets/hand_landmarker.task`
  - RN prototype `android/app/build.gradle` includes `com.google.mediapipe:tasks-vision:latest.release`
- Updated RN02 JS screen and types so Android can run `startHandBenchmark`, `stopHandBenchmark`, and `getLatestHandBenchmark`.

## Current capability
- Android RN02 can compile with MediaPipe Tasks Vision and should load `hand_landmarker.task` natively in `RunningMode.IMAGE`, `numHands=2`, confidence thresholds `0.5`.
- It returns compact session dictionaries only; no raw frames or landmarks cross the bridge.
- It records zero processed frames until native CameraX/ImageAnalysis `ImageProxy` ingestion is added.

## Verification
- `npm run typecheck` passed.
- `npm run lint` passed.
- `./gradlew.bat assembleDebug -PreactNativeArchitectures=arm64-v8a --console=plain --no-daemon --max-workers=2` passed.
- APK exists at `apphear-react/android/app/build/outputs/apk/debug/app-debug.apk`.
- Android asset SHA256 matches `apphear-react/assets/mediapipe/hand_landmarker.task`.

## Next session starts with
- Install/run the rebuilt RN prototype APK on the connected Android device.
- Open RN02 and press Start; expected result is a native model-load session with zero samples and no crash.
- If that passes, implement native CameraX/ImageAnalysis hand-only `ImageProxy` ingestion and p50/p95 latency sampling.

## Guardrails
- No production Android runtime files were touched.
- No pose, 258-feature construction, TFLite, recognition, dataset, or training-pipeline changes yet.
- No FPS or recognition conclusion can be drawn from RN02 until camera-frame MediaPipe detection is implemented and logged.

---# Memory - RN02 iOS Source Wiring

Last updated: 2026-07-19 15:05 +08:00

## What was built
- Continued RN02 after the developer chose to skip iPhone RN01 for now.
- Added source-level iOS native module wiring under `apphear-react/ios/AppHearReactPrototype/`:
  - `RN02HandBenchmarkModule.m`
  - `RN02HandBenchmarkModule.swift`
  - `RN02HandLandmarkerBenchmark.swift`
  - `hand_landmarker.task`
- Updated `ios/AppHearReactPrototype.xcodeproj/project.pbxproj` so RN02 Swift/ObjC files are in Sources and `hand_landmarker.task` is in Resources.
- Updated `ios/Podfile` with `pod 'MediaPipeTasksVision'` for the RN prototype target only.
- Added `src/screens/Rn02HandSmokeScreen.tsx` and an RN01/RN02 switch in `App.tsx`.
- Updated `src/native/AppHearVisionModule.ts` to export a typed `Rn02HandBenchmarkModule` that uses the iOS native module when present and a guarded placeholder elsewhere.

## Current capability
- RN02 can attempt to load the bundled MediaPipe `hand_landmarker.task` through a native iOS module.
- RN02 still records zero processed frames because native camera sample-buffer ingestion has not been implemented.
- React Native receives only compact session dictionaries; no raw frames or per-frame landmarks cross the bridge.

## Verification
- `npm run typecheck` passed.
- `npm run lint` passed.
- SHA256 for `ios/AppHearReactPrototype/hand_landmarker.task` matches `assets/mediapipe/hand_landmarker.task`.
- iOS compile/device validation was not run because this host is Windows, not macOS/Xcode.

## Next session starts with
- On macOS: run CocoaPods for `apphear-react/ios`, build the iOS target, and verify `RN02HandBenchmarkModule.startHandBenchmark()` can load `hand_landmarker.task` on a physical iPhone.
- After that passes, implement native camera `CMSampleBuffer`/`CVPixelBuffer` ingestion and actual hand latency sampling.

## Guardrails
- RN02 is not a passed Phase 2 benchmark yet.
- Do not add pose, 258-feature construction, TFLite, recognition, dataset changes, or training changes until RN02 hand-only iPhone logs exist.

---# Memory - RN02 iOS Hand-Only Scaffold

Last updated: 2026-07-19 14:35 +08:00

## What was built
- Developer explicitly skipped the iPhone RN01 benchmark for now and directed work to continue to the next step.
- Recorded this as a conscious RN01 gate deviation in `context/progress-tracker.md` and `context/react-native-prototype.md`.
- Prepared RN02 scaffold/protocol only:
  - `apphear-react/benchmark/protocols/rn02-ios-hand-only.md`
  - `apphear-react/src/types/rn02HandBenchmark.ts`
  - `apphear-react/native/ios/RN02HandLandmarkerBenchmark.swift`
  - `apphear-react/native/ios/README.md`
  - `apphear-react/assets/mediapipe/hand_landmarker.task`
  - `apphear-react/ios/Podfile` now includes `pod 'MediaPipeTasksVision'`
- Updated `apphear-react/src/native/AppHearVisionModule.ts` with an RN02 hand-benchmark native-module contract placeholder.

## Verification
- Web-checked official Google MediaPipe iOS Hand Landmarker docs on 2026-07-19: use `MediaPipeTasksVision` via CocoaPods, `HandLandmarkerOptions`, `BaseOptions.modelAssetPath`, `.image/.video/.liveStream` running modes, `numHands`, and confidence thresholds.
- Copied `hand_landmarker.task` from repo canonical assets into the RN prototype assets; SHA256 matches the source asset.
- `npm run typecheck` passed.
- `npm run lint` passed.

## Current state
- RN02 is scaffolded but not implemented or validated.
- RN02 cannot be marked passed until it runs on a physical iPhone and exports hand-only latency logs.
- No pose, S4 features, TFLite, recognition, production Android, dataset, or training-pipeline code was changed.

## Next session starts with
- On macOS, install iOS pods for `apphear-react/ios`, add the RN02 Swift scaffold and `hand_landmarker.task` to the Xcode target, then implement the native iOS hand-only benchmark path.

## Open questions
- Which iPhone model/iOS version will be used for RN02 validation?
- Should RN02 baseline use strict `.image` first only, or also run `.video` as a separately logged follow-up after `.image` numbers exist?

---
# Memory - RN01 Android Verdict Saved

Last updated: 2026-07-19 14:15 +08:00

## What was saved
- Saved raw RN01 Android 1/3/5-minute exports and `summary.json` under `apphear-react/benchmark/device-results/android-m2101k7ag-rn01-2026-07-19/`.
- Updated `context/react-native-prototype.md` with the RN01 Android benchmark table and interpretation.
- Updated `context/progress-tracker.md` with the Android benchmark pass and decision that RN02 remains blocked until iPhone RN01 evidence exists.
- Updated `apphear-react/README.md` with the Android RN01 result.

## Verdict
- Android half of RN01: PASS.
- Full RN01: INCOMPLETE until physical iPhone 1/3/5-minute logs exist.
- RN02 MediaPipe hand-only: DO NOT START yet.

## Evidence
- Xiaomi `M2101K7AG` / `sunny_global`, front camera, requested 60 FPS, target `480x854`, actual frame `800x480`.
- 1 min: 62.1s, 1864 frames, avg 30.02 FPS, 0 drops.
- 3 min: 186.0s, 5580 frames, avg 30.00 FPS, 0 drops.
- 5 min: 307.8s, 9237 frames, avg 30.01 FPS, 0 drops.

## Next session starts with
- Run the same RN01 benchmark on a physical iPhone via macOS/Xcode/CocoaPods and export 1-minute, 3-minute, and 5-minute JSON logs.

## Open questions
- Which iPhone model and iOS version will be used?

---
# Memory - React Native Prototype RN01 Android Benchmark

Last updated: 2026-07-19 14:05 +08:00

## What was verified
- RN01 ran on physical Android device `M2101K7AG` / Xiaomi `sunny_global` using the separate `apphear-react/` prototype.
- Camera preview worked after two RN01 fixes: camera-device fallback and YUV frame output at lower 16:9 target.
- Benchmark export worked with schema `apphear.rn01.camera_fps.v1`.

## Results
- 1-minute run: 62.1s, 1864 frames, avg 30.02 FPS, min 29.76, max 30.88, dropped 0, actual frame 800x480.
- 3-minute run: 186.0s, 5580 frames, avg 30.00 FPS, min 29.00, max 30.94, dropped 0, actual frame 800x480.
- 5-minute run: 307.8s, 9237 frames, avg 30.01 FPS, min 29.53, max 31.01, dropped 0, actual frame 800x480.

## Decisions made
- Android RN01 physical smoke is a PASS for camera/frame-output stability.
- Requested 60 FPS negotiates to stable 30 FPS on this device; RN01 should report actual callback FPS, not assume requested FPS.
- This is not landmark FPS and must not be interpreted as MediaPipe or recognition performance.

## Problems solved
- VisionCamera initially crashed when hardcoded to `front`; fixed by selecting from actual `useCameraDevices()` output and falling back safely.
- CameraX rejected `PRIVATE` 640x480 ImageAnalysis; fixed by using `pixelFormat: 'yuv'` and a lower 16:9 target.
- Benchmark session appending caused a React maximum update-depth loop; fixed with a frame-count guard and non-recursive effect dependency.

## Current state
- Android half of RN01 is complete and passed.
- iPhone half of RN01 is still required before RN02 MediaPipe hand-only work.
- No production Android, model, dataset, feature contract, or training pipeline code was changed.

## Next session starts with
- Run RN01 on a physical iPhone via macOS/Xcode/CocoaPods and export 1-minute, 3-minute, and 5-minute logs using the same benchmark schema.

## Open questions
- Which iPhone model and iOS version will be used?
- Will iPhone VisionCamera negotiate 30 FPS, 60 FPS, or another stable callback rate at the chosen frame output?

---
# Memory - React Native Prototype RN01 Native Shell

Last updated: 2026-07-18 16:55 +08:00

## What was built
- Generated native React Native `android/` and `ios/` platform projects inside `apphear-react/` only.
- Added Android and iOS camera permission declarations for RN01.
- Added React Native CLI platform packages and Babel 7 runtime/core support.
- Added the `react-native-worklets/plugin` Babel plugin so VisionCamera frame-output worklets are transformed at runtime.
- Built the prototype Android debug APK for one ABI: `apphear-react/android/app/build/outputs/apk/debug/app-debug.apk`.

## Decisions made
- Keep the Android prototype build constrained to `arm64-v8a` for RN01 smoke testing to avoid expensive four-ABI debug builds.
- Keep New Architecture enabled because the selected VisionCamera/Nitro stack uses that path.
- Do not start RN02 MediaPipe work until RN01 runs on physical devices and exports benchmark logs.

## Verification
- `npm run typecheck` passed.
- `npm run lint` passed.
- `npx react-native config` detects both `ios/` and `android/` projects with package/application ID `com.apphear.reactprototype`.
- Metro Android bundle check passed after sandbox escalation for worker spawn.
- Android debug build passed with `.\gradlew.bat assembleDebug -PreactNativeArchitectures=arm64-v8a --console=plain --no-daemon --max-workers=2` after Maven dependency access was allowed.

## Current state
- Android APK exists, but was not installed because `adb` is not on PATH in this shell.
- iOS project exists, but pods/Xcode build were not run because this machine is Windows.
- No physical RN01 benchmark logs exist yet.

## Next session starts with
- Put Android SDK platform-tools/`adb` on PATH or open `apphear-react/android/` in Android Studio, install `app-debug.apk`, start Metro, and run a real-device RN01 smoke test.
- On macOS, run `pod install` in `apphear-react/ios`, open the generated Xcode workspace, deploy to a physical iPhone, and export 1-minute, 3-minute, and 5-minute RN01 JSON logs.

## Open questions
- Which iPhone model/iOS version is the first benchmark target?
- Should Android RN01 be tested on the same low-end phone as the native Android baseline, or only used as a sanity check after iPhone?

---
# Memory - React Native Prototype RN01 Scaffold

Last updated: 2026-07-18 16:10 +08:00

## What was built
- Created the separate `apphear-react/` React Native prototype scaffold for RN01 only.
- Added TypeScript app shell, RN01 camera/FPS smoke screen, benchmark controls, rolling FPS tracker, JSON benchmark export, typed native-module placeholder, benchmark protocol, and native iOS/Android/shared placeholders.
- Added `ARCHITECTURE.md`, `README.md`, RN config files, ESLint, TypeScript, VisionCamera, VisionCamera Worklets, React Native Worklets, AsyncStorage, and Reanimated dependencies.

## Decisions made
- RN01 remains a camera/FPS smoke test only. It does not include MediaPipe, feature construction, TFLite, recognition, temporal buffering, or confirmation.
- VisionCamera frame output is used only to count/dispose frames and measure callback cadence. Pixel buffers are not read in JavaScript and raw frames are not bridged through React Native state.
- No production Android, model, feature contract, dataset, or training-pipeline files were changed.

## Verification
- `npm install` completed with 0 vulnerabilities.
- `npm run typecheck` passed.
- `npm run lint` passed.

## Current state
- RN01 scaffold is code-complete for static validation.
- Physical-device smoke testing is pending on one iPhone and one Android device.
- Native iOS/Android platform projects are not generated yet, so Metro/device run was not started in this session.

## Next session starts with
- Generate or attach the RN native platform projects for `apphear-react/`, then run RN01 on a physical iPhone first and export 1-minute, 3-minute, and 5-minute benchmark JSON logs.

## Open questions
- Which exact iPhone model and iOS version will be used for the first RN01 benchmark?
- Should native project generation happen on this Windows machine for Android only, or on a Mac so iOS can be created and tested immediately?

---
# Memory - React Native Prototype Context Wiring

Last updated: 2026-07-18 00:00 +08:00

## What was built
- Added `context/react-native-prototype.md`, the source-of-truth plan for the separate `apphear-react/` experiment.
- Wired the context file into `AGENTS.md`, `context/architecture.md`, `context/build-plan.md`, `context/progress-tracker.md`, `.agents/skills/architect/SKILL.md`, and `.agents/skills/review/SKILL.md`.

## Decisions made
- React Native/iPhone work is a separate prototype only, not a migration or replacement for `android/`.
- React Native owns UI/settings/result display; native code owns camera frames, MediaPipe, S4 features, buffering, TFLite, S5/S7, and profiling.
- The first milestone is Phase 1 only: camera preview, FPS dashboard, and benchmark export on one physical iPhone and one Android device.

## Problems solved
- Future agents now have an explicit context file, operating-guide wiring, skill wiring, and memory handoff, reducing guessing around RN/iOS scope, phases, and non-goals.

## Current state
- No prototype implementation has started. No production Android, model, dataset, or pipeline code was changed for this context pass.

## Next session starts with
- If the developer approves implementation, start RN01 under `apphear-react/` only.

## Open questions
- Which physical iPhone model will be used for the first smoke test?
- Will Phase 1 use bare React Native CLI or an Expo dev client/prebuild setup?

---
# Memory - AppHear 3 Low-FPS Runtime Profiling and Controlled Accuracy Test

Last updated: 2026-07-18 11:50 +08:00

Session handoff for `/remember restore`. This entry preserves the current Android runtime state after the low-FPS profiling/tolerance pass and controlled sign testing.

## What was built
- Structured Android runtime profiling is active and configurable: camera/analyzer input rate, processed FPS, skipped frames, conversion/rotation, hand time, pose time, recognition time, total wall time, low-FPS state, and device/battery context logging.
- Profiling modes are available through `FeatureFlags.PROFILING_MODE`: `CAMERA_ONLY`, `HAND_ONLY`, `POSE_ONLY`, `HAND_AND_POSE`, and `FULL_RECOGNITION`.
- Low-FPS detection is active around the 10 FPS recognition floor, with enter/exit logs and runtime state available to the recognizer.
- Pre-onset processed-landmark buffering is enabled through config, currently `pre_onset.enabled=true` and `frames=3`; this stores recent feature frames only, not raw camera frames.
- S5 diagnostics were added for onset timing, candidate/motion timing, release/dropout, and commit/drop confidence evidence.
- Low-FPS S5 tuning is behind config and currently enabled: `k_on=2`, `k_off=6`, `smoothing_window=3` for low-FPS mode while preserving the normal-FPS baseline config.
- Low-FPS confirmation is behind config and currently enabled: `theta_conf=-1.2`, `theta_margin=0.75`, `k_stability=2`, `min_commit_frame=2`. The min-frame guard prevents frame-1 commits.
- Pose cadence experiment is behind config and currently enabled for testing: `pose_every_n=2`, `hold_last_pose=true`; hand landmarks remain fresh and the 258-feature contract is unchanged.
- UI stale-word behavior was fixed: when S5 releases/returns idle, `MainActivity` now clears the live gloss and candidates back to the placeholder instead of keeping the previous word stuck on screen.
- `SessionNormalizer` train/serve parity has a golden-vector JVM test for the deployed causal S4 path.

## Decisions made
- The main runtime bottleneck remains MediaPipe hand + pose landmarking, not TFLite recognition inference. Recognition is consistently around 1-2 ms and is not worth optimizing first.
- Keep the native Android baseline. Do not migrate to React Native for FPS. Do not use the failed ST-GCN result. Do not replace the deployed TCN yet.
- Keep the v3.0 258-feature schema exactly intact. Hand and pose features must not be dropped.
- Pose cadence every 2 frames is acceptable as a reversible test setting because it holds the last valid pose and keeps the feature vector shape intact.
- Do not loosen thresholds blindly. After the latest controlled test, remaining recognition errors look more like model/data confusion clusters plus low-FPS/thermal degradation than a simple confirmation-threshold problem.

## Problems solved
- Earlier crashes/logcat issues were fixed and the app builds/tests successfully.
- Frame-1 low-FPS commits were stopped by `lowFpsMinCommitFrame`.
- Stale S5 candidate timing was cleaned up so old candidate frames do not carry across long idle gaps.
- The UI no longer intentionally keeps the last committed word during idle/null recognition states.
- Pose cadence reduced pose cost substantially compared with the fresh-pose-every-frame baseline while preserving the feature contract.

## Current state
- Verification after the last runtime edits: `.\gradlew.bat testDebugUnitTest` passed and `.\gradlew.bat assembleDebug` passed.
- Latest controlled-device log had no fatal crash: `PerfLines=132`, `PoseEvery2=132`, `Frame1Commits=0`, `Onsets=27`, `Releases=27`, `Commits=25`, `RecognitionDrops=2`.
- Latest measured averages: camera input about 14.7 FPS, processed about 8.8 FPS, minimum processed about 5.5 FPS, hand about 62.8 ms, pose about 51.1 ms with pose cadence, recognition about 1.9 ms, total wall about 95.0 ms.
- Controlled sign behavior: `CUT` and `IMPORTANT` were excellent; `SELL` and `WANT2` were mostly good; `KNOW` confused with `STRONG`/`SELL`; `STREET` and `MUCH` confuse with each other and `ROAD`/`IMPORTANT`; `START` confused with `THEN`; later signs degraded when FPS fell to about 5-6 FPS.
- The current problem is no longer an unknown runtime pipeline bug. It is a measured low-FPS MediaPipe ceiling plus specific model/data confusion clusters under low-end Android conditions.

## Next session starts with
Build a controlled confusion report from the latest log and decide the next accuracy experiment: targeted dataset review/collection or retraining/fine-tuning for the observed clusters (`KNOW`/`STRONG`/`SELL`, `STREET`/`MUCH`/`ROAD`/`IMPORTANT`, `START`/`THEN`). Do not do more threshold tuning until those clusters are quantified.

## Open questions
- Should the next accuracy pass collect local signer examples for the confused words, or first inspect existing training examples for those labels?
- Should profiling stay enabled for the next device test, or be disabled for normal UX after enough timing evidence is captured?
- Is a cooler/faster Android device available for a comparison run to separate model confusion from thermal/FPS collapse?
- When model work resumes, should the next approved path be targeted TCN retraining/fine-tuning first, before any encoder-swap experiment?

---
# Memory ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â AppHear 3, Phase 3 CODE-COMPLETE (Android runtime; conversational model deployed)

Last updated: 2026-07-17 22:16 +08:00

Session handoff for `/remember restore`. Durable per-feature detail lives in
`context/progress-tracker.md`; this is the fast-start summary.

## SESSION HANDOFF (2026-07-17) - FPS bottleneck and React Native assessment

**Scope:** Read-only architecture assessment. No app, model, pipeline, or configuration code was
changed. The returned ST-GCN artifacts were valid, but the experiment failed its pre-registered
accuracy gates and must not replace the deployed conversational TCN.

**Bottleneck conclusion:** MediaPipe hand and pose extraction in stateless IMAGE mode dominates the
processed-frame ceiling, not CameraX buffering or TFLite. Recorded averages: conversion 1.7 ms,
rotation 14 ms, hand 100 ms, pose 110 ms, recognition 0.5 ms, effective wall 130 ms (~7.6 fps).
CameraX KEEP_ONLY_LATEST plus the analyzer busy guard drops stale frames instead of queueing them.

**Important implementation finding:** `FrameAnalyzer` forces fresh pose on every frame whenever
recognition is loaded (`recognizer != null || ...`). Adaptive pose cadence therefore does not reduce
pose work in recognition mode, although its displayed tier can still change. This preserves feature
fidelity but removes cadence as a current recognition-mode FPS lever. RGBA conversion and physical
rotation are secondary and cannot alone close the gap to 15 fps.

**React Native decision:** React Native is feasible only as a hybrid shell. Camera, MediaPipe, S4
normalization, signing detection, buffering, TFLite, and confirmation must stay in native
Kotlin/Swift/C++ worker code; JavaScript receives compact UI state only. React Native will not solve
the MediaPipe bottleneck and can perform worse if frames or per-frame arrays cross the JS boundary.
Keep native Android as production baseline. Use a separate prototype only if iPhone support becomes
a real requirement; do not migrate or modify the existing Android project for that experiment.

**Prototype model/runtime:** Reuse the deployed conversational 236-class fps-augmented TCN `.tflite`,
manifest, vocabulary, recognition config, and MediaPipe task assets. Do not use the failed ST-GCN.
Keep TFLite initially; ONNX adds parity and maintenance risk without addressing the bottleneck. iOS
needs native Swift MediaPipeTasksVision integration and verified S4-S7 parity (or later shared C++).

**Next session starts with:** Run a native Android p50/p95 ablation on the same physical devices:
camera-only, hand-only, pose-only, hand+pose, and full recognition. Measure true wall latency,
processed fps, dropped-frame rate, and camera cadence. If cross-platform support remains desired,
then specify an isolated prototype with gates: Android within 5% of native, golden feature/model
parity, and iPhone sustained >=15 fps.

**Open questions:** Is iPhone support committed or exploratory? Are a Mac, Xcode, and physical
iPhone available? Should the prototype use a custom native camera component or VisionCamera plus a
native plugin? No implementation plan is confirmed yet.

## ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¡ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ SESSION HANDOFF (2026-07-07) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â start here

**Where we are:** Phase 3 (Android runtime) **CODE-COMPLETE**. F17ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œF22 built; F17/F18/F19/F21
device-verified, F20 (S8 sentence builder ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â passthrough+dedup) done, F22 (device-smoke checklist
`context/device-smoke.md`) done. Full chain works on the phone: capture ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ landmarks ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ causal S4
features ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ INT8 TFLite ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ S7 confirmation ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ UI (top-3 candidates + handedness toggle + sentence band).

**Deployed model = CONVERSATIONAL 236-word everyday vocab (fps-augmented).** Replaced the useless
data-richest 250 (CHEESEGRATER/OSTRICH/TRACTOR). Cross-signer test: native 0.612/0.887, phone-fps
(k8) 0.527/0.825; precision-when-committed 0.73, ÃƒÆ’Ã…Â½Ãƒâ€šÃ‚Â¸_conf ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢1.2, temp 0.647. **DEVICE-VERIFIED** ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â
commits real everyday words (HELLO/HOUSE/WHERE/NEED/WANT/WALK). Revert path preserved at
`android/app/src/main/assets/_backup_250fps/` (+ source `runs/tcn_streaming_reduced_fps_v30`).
Full story: memory `project-conversational-vocab`, `context/recognition-accuracy.md`.

**This session's work:** GPU delegate (3ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢7fps), one-commit-per-bout (kill spam), no-hands gate
(`require_hands`), F21 (top-3 + handedness toggle), F20/S8 sentence builder, VIDEO-mode fps lever
evaluated+DEFERRED (memory `project-video-mode-deferred`), the whole conversational-vocab rebuild +
deploy, and a handedness-visibility toast (stale/inherited handedness silently wrecked recognition).

**Accuracy ceiling is HARDWARE now (~7ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ8fps; landmarkers = 95% of the frame).** Model side is
well-optimized (fps-aug + useful vocab + calibrated confirm). Further recognition gains need a
faster phone / lighter landmarker ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â DEFERRED by developer decision.

**NEXT ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â FINISH THE PROJECT (accuracy work parked):** (a) F22 cross-signer device smoke ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â 2ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ3
signers, each sets handedness first (Phase-3 sign-off); (b) final docs/README pass to reflect the
shipped conversational app. Later (come back to): detection/recognition improvements, Phase 2 CTC
(needs continuous data), S8 LM-assist, higher fps.

**GOTCHA:** always run training/eval/export with `.venv\Scripts\python.exe` (Keras 3.15.0); system
Python 3.13.2 can't load 3.15-saved models (`input_axes` error).

---

## ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¡ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ EARLIER HANDOFF (2026-07-05) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â history

**Where we are:** Phases 0+1 complete (offline pipeline, streaming model, confirmation, dynamics,
INT8 TFLite export all done/verified). **Phase 2 (CTC) DEFERRED** ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â no continuous data. **Phase 3
(Android) in progress:** Android project at `android/` (pkg `com.example.apphear`, AGP 8.11.2 /
Kotlin 2.0.21 / minSdk 26).
- **F17 ÃƒÆ’Ã‚Â¢Ãƒâ€¦Ã¢â‚¬Å“ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ device-verified** ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â CameraX + MediaPipe hand+pose (IMAGE mode) + adaptive pose-cadence
  safety net (settles LowÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂMinimum on the dev's old Xiaomi; fps ceiling = hardware, accepted).
- **F18 ÃƒÆ’Ã‚Â¢Ãƒâ€¦Ã¢â‚¬Å“ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ (full-span S4 exact port) skew-test GREEN** ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Kotlin S4 == Python byte-exact (ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°Ãƒâ€šÃ‚Â¤1e-4).
- **F18b ÃƒÆ’Ã‚Â¢Ãƒâ€¦Ã¢â‚¬Å“ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ (causal online-param estimator, Python) developer-run PASS** ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â commit-accuracy gate 0.0107
  ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°Ãƒâ€šÃ‚Â¤ 0.02; but per-signer breakdown found the ~1pt cost is CONCENTRATED on left-dominant signers
  (~4pt) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ decision: F19 uses SESSION-level handedness (memory `project-handedness-user-property`).
- **F19a ÃƒÆ’Ã‚Â¢Ãƒâ€¦Ã¢â‚¬Å“ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ (causal Kotlin S4 port) JVM-verified** ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â `clipFeaturesCausal` == Python `clip_features_causal`
  byte-exact; `gradlew testDebugUnitTest` BUILD SUCCESSFUL. The streaming train/serve-parity surface is proven.

**ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ F19b DEVICE-VERIFIED (2026-07-06) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â THE PHASE-3 CORE MILESTONE.** Full 9-stage pipeline fires on the
phone: logcat `AppHearRecog` showed `recognizer loaded` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ `S5 ONSET` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ `COMMIT 'HEAD' (id=1115) at frame 2`
ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ `S5 RELEASE`. cameraÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢landmarksÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢causal SESSION featuresÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢INT8 TFLiteÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢S7 confirmationÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢committed gloss all
work on real hardware. Built all of `android/.../pipeline/recognition/` (Recognizer, Vocab, ModelContract,
SessionNormalizer, SigningDetector, Confirmation, LandmarkAdapter, RecognitionPipeline, FeatureFlags) +
assets (streaming.tflite, model_manifest.json, vocab.json, recognition_config.json) + wired into
FrameAnalyzer/MainActivity/layout. `org.tensorflow:tensorflow-lite:2.16.1`. Commits are conservative
(most drop ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ~9% rate @ ÃƒÆ’Ã…Â½Ãƒâ€šÃ‚Â¸_conf ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢1.2); correctness is the KNOWN model-data limit (~31%), not wiring.

**ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ FPS-AUGMENTATION deployed (2026-07-06) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â fixes the train-30fps/phone-~4fps mismatch.** Retrained
the 250-class model on fps-EXPANDED features (`pipeline/features/fps_augment.py`, offline subsample copies).
Cleanly BETTER at every fps: top-1 native 0.626ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢0.645, k8(phone ~4fps) 0.496ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢0.547 (+5pt); precision-when-
committed 0.73 @ phone-fps. INT8-exported (parity_batch 3000 to beat benign near-tie noise), deployed to app
(`runs/tcn_streaming_reduced_fps_v30`, theta_conf ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢1.6 tuned on low-fps val). configs: train/confirm/export
_reduced_fps.yaml. `eval/streaming.py` +`--features-dir`. ALL past runs preserved. Reinstall APK to test.

**ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ ACCURACY ~DOUBLED via vocabulary reduction (2026-07-06).** Retrained streaming model on top-250
data-richest signs (no re-extraction ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â `pipeline/features/reduce_vocab.py` filtered existing features).
Cross-signer test **top1 0.626 / top5 0.865** (vs full 2731: 0.314/0.598); precision-when-committed **0.71**
(was ~0.36). DEPLOYED to app: reduced streaming.tflite (250-class, 228KB) + manifest + 250-gloss vocab.json
in assets; `recognition_config.json` set theta_conf ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢1.0 + temperature 1.0 (consistent with the confirm run).
assembleDebug green. Tooling: `train_streaming_reduced.yaml`, `confirm_reduced.yaml`, `export_reduced.yaml`,
`train_streaming.py` +vocab_dir, `eval/streaming.py` +--config. The 250 glosses = top-by-train-count (see
`features_reduced/vocab.json`; e.g. BUY, CAKE, CAT3, CLOSE, COUNT, CUT, ...). **DEVELOPER: rebuild+run on
phone, sign a gloss from the 250-set, expect far better/more frequent commits.**

**NEXT SESSION STARTS WITH:** **F20 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â sentence builder (S8)** (accumulate committed glosses into a phrase
with smoothing/dedup) + **F21 recognition UI** (handedness setting exposing `SessionNormalizer.handedness`,
cleaner gloss display) + **F22 device smoke**. Separately, recognition ACCURACY is a model/data effort
(the plumbing is done). WATCH: F19b committed at frame 2 (very early) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â monitor whether on-device confidence
ramps faster than offline. Below: older handoffs.

**(F18b context)** the **causal online-param estimator** (code-complete +
smoke-verified). Built `pipeline/normalize/causal.py` (running-median scale/roll + margin+abs-guarded
MirrorStabilizer), `clip_features_causal`, `pipeline/features/streaming_causal.py`, `eval/causal_skew.py`.
scale/roll converge fine; MIRROR needed two investigation rounds (freeze-when-stable locked wrong ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢
swept policies ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ decisive ratio 0.30 + abs-lead 0.15 + k4 reproduces offline 21% mirror rate @ ~88%
agreement = causal ceiling). GATE REFRAMED to **top-1 delta ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°Ãƒâ€šÃ‚Â¤ 0.01** (deployment metric, INT8 precedent);
commit-agreement + late-mirror-flip are DIAGNOSTICS (late flip is post-commit ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ can't change the
committed gloss since confirmation commits once). **DEVELOPER must REBUILD FULL features_causal (a 500-clip
sample build clobbered test.npz), then run `eval.causal_skew` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â expect PASS.** Then **F19**: port the
causal estimator + MirrorStabilizer to Kotlin S4, wire `streaming.tflite` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ live recognition + S5 gating.
Then F20 confirmation/sentence on-device, F21 UI, F22 device smoke.

**Open threads:** held-pose adaptive-cadence parity caveat (memory `project-adaptive-pose-cadence`);
S3 One-Euro smoothing deferred (add later as measured A/B, needs re-extraction); confirmation
operating point is a deferred product decision (memory `project-confirmation-operating-point`).

---

## What was built

**Context System (setup):** 9 `context/` files + `AGENTS.md` + 5 skills in `.claude/skills/`
(architect/imprint/review/recover/remember) + `docs/` design rationale. Adapted from the
JS-Mastery skills repo; the UI trio was replaced by `runtime-constraints.md` /
`eval-protocol.md` / `feature-schema.md`.

**Phase 0 offline pipeline ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â 6 of 9 features done.** Raw video ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ model-ready v3.0 tensors:
- `pipeline/extract/` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â E: MediaPipe hand+pose (IMAGE mode, face off) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ raw landmark `.npz` +
  sidecar. Resumable runner + cross-signer health sampler.
- `pipeline/detect/` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â D1/D2: pose-primary motion + hands-raised gate ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ hysteresis signing
  span (`*.span.json`). Tuned on val.
- `pipeline/normalize/` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â N1/N2/N3: centerÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢scaleÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢rollÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢mirror to canonical space (pure); plus
  N4 `resample.py` (linear ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ T=64). Shared `scale.py`, `topology.py`.
- `pipeline/quality/` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Q: advisory accept/reject + dataset-health report.
- `pipeline/features/` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â F: **v3.0 contract minted** (258-float, T=64) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ per-split `.npz`
  (`X,mask,y,participant_ids`) + `vocab.json`.
- `pipeline/splits/` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â frozen `artifacts/splits.json` (52 signers 35/6/11, disjoint, hashed) +
  `--verify` drift/leakage guard.
- `model/` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â causal-TCN classifier (`model.py`, ~154K params, 4 blocks/64ch/dil[1,2,4,8]),
  `data.py` (v3.0 npzÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢tf.data), `train.py` (config-driven, `--smoke`, checkpoints). Smoke-tested.
- `pipeline/run_pipeline.py` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â one-command EÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢DÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢F per split (+ recipe).
- `eval/` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â cross-signer harness: per-signer top-1/top-5 + temperature calibration (ECE) +
  confusion summary ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ report-only `eval_<split>.json`. Smoke-tested. Real eval = `python -m eval.run`.
- 69 tests, all green; ruff/mypy clean. `.venv` (Python 3.11); **TensorFlow 2.21 installed**.
- **Phase 0 offline build is code-complete: 8/9** (09 v3.1 kinematic ablation is optional).

## Decisions made (see progress-tracker [F01]ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ[F05] for full list)

- Extraction runs MediaPipe **IMAGE mode** (stateless, per-clip isolation, better S4 parity
  than hidden VIDEO tracking).
- Landmarkers pinned **Pose Lite + Hand**, store image + world landmarks.
- Signer detection is **pose-primary** (pose hit-rate ~1.0; hand ~0.3). Thresholds tuned
  label-free: `theta_on=0.12` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ 97.8% coverage, median span ~1.06s.
- N2 roll uses **shoulder-LINE tilt folded to ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â±90ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â°** (camera mirrors the view).
- **v3.0 contract:** 258 = [handL 63, handR 63, pose 132]; NaNÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢0 + separate `(T,2)` presence
  mask; N4 ON for isolated Phase 0 (OFF in streaming/CTC). `clip_features` is the S4 parity
  target.
- Splits: **official ASL Citizen splits are signer-disjoint** (train 35 / val 6 / test 11
  signers, zero overlap) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â feature 06 just verifies/adopts.

## Problems solved

- MediaPipe VIDEO-mode monotonic-timestamp error across clips ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ switched to IMAGE mode.
- N2 roll 178ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â° residual (camera-mirror shoulder-vector wrap) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ line-tilt fold, residual ~0.02ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â°.
- Several Windows/mypy/ruff papercuts (cp1252 arrow in prints, `float(object)`, unused ignores).

## Current state

Phase 0 pipeline complete EÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢F and validated on val (mostly one signer, P5). v3.0 `val.npz`
built: `X (85,64,258)`, NaN-free. Nothing on-device yet (Android is Phase 3).

## Latest (full-scale, in progress)

Full corpus extracted (train 40k, val 10k done; **test extraction pending ~9hr**). Full features
built: train `(36960,64,258)` / val `(9575,...)`, vocab=2731. Parallel extraction added
(`--workers`, 12 cores; user runs at `--workers 4` for heat).

**First full-scale cross-signer numbers (2,731 classes, held-out val signers):**
- Baseline (no reg): val_top1 0.328 / top5 0.608, overfit gap 0.45.
- **+Regularization+Augmentation** (dropout 0.3, AdamW wd 1e-4, label-smoothing 0.1, `model/augment.py`
  rotation/scale/noise/frame-mask): **val_top1 0.360 / top5 0.629, gap 0.34.** Regularization confirmed
  working; val plateaued ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ near ceiling for this model on ~13 clips/class (DATA-limited).
- Thesis fully validated at full scale: pipeline works end-to-end, cross-signer-uniform, class-scaling
  graceful, calibrated. Isolated classifier = plumbing-validation step (per eval-protocol), done.

**ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ PHASE 0 COMPLETE ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â OFFICIAL BASELINE:** ASL Citizen test, 2,731 classes, 11 held-out signers,
29,770 clips ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ **top1=0.291 / top5=0.552**, per-signer uniform 0.25ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ0.37, calibration ECE 0.126ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢0.041.
Cross-signer generalization confirmed on official test (the v2 failure point). Confusions are semantic
near-synonyms. Data-limited (~13 clips/class); isolated classifier's plumbing-validation role is done.
All full features on disk (train 36960 / val 9575 / test 29770, vocab 2731). best.keras = reg+aug model.

**PHASE 1 IN PROGRESS.**
- **[F10] DONE ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â real-timed regime (N4 OFF):** `pipeline/features/streaming.py` + `clip_features_realtimed`
  build `features_streaming/<split>.npz` from EXISTING landmarks/spans (pure numpy, ~15min all splits,
  NO re-extraction). Same 258 layout; native frame timing preserved; padded t_max=96 + `frame_mask` +
  `lengths`; reuses vocab. val `(9575,96,258)` + train + test built. Regime is closer to runtime.
- **[F11] DONE (code+smoke) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â per-frame emission head:** `build_streaming_classifier` (encoderÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢per-frame
  softmax), `model/train_streaming.py` (warm-start encoder from isolated best.keras; every real frame targets
  the gloss, padded frames masked via sample_weight; `train_streaming.yaml`, geometric aug only), `eval/streaming.py`
  (mean-over-real-frames ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ feature-08 harness + per-frame/last-frame diagnostics). 90 tests green.
- **[F11] DONE + evaluated.** Streaming model trained (warm-started). Cross-signer test (2731 classes, 11 signers):
  clip mean-agg **top1=0.314 / top5=0.598** ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â SLIGHTLY BEATS isolated (0.291/0.552): streaming gained at no
  accuracy cost. Per-signer uniform 0.25ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ0.38. Calibration T=0.715 ECE 0.132ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢0.061. Shape per-frame 0.208 <
  last-frame 0.268 < accumulated 0.314 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ evidence accumulation works (validates confirmation).
  **eval/streaming had an OOM bug (per-frame NÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ÂTÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â2731 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°Ãƒâ€¹Ã¢â‚¬Â  31GB) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â FIXED** via `predict_aggregate` (batched, ~5GB peak).
- **[F12] DONE (code+smoke) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â confirmation policy (S7):** `eval/confirm.py` + `model/config/confirm.yaml` +
  `tests/test_confirm.py`. Accumulate CALIBRATED (T=0.715) per-frame evidence as cumulative-MEAN log-posterior
  (length-invariant); commit at first frame where evidence (A1ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°Ãƒâ€šÃ‚Â¥ÃƒÆ’Ã…Â½Ãƒâ€šÃ‚Â¸_conf) + margin (A1ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢A2ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°Ãƒâ€šÃ‚Â¥0.30) + stability (kÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°Ãƒâ€šÃ‚Â¥3)
  all hold, else drop. Reports `correct_but_dropped` (the v2 leak) as a first-class metric + commit latency.
  Memory-safe (batched predict ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ (N,T,3) summary, never NÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ÂTÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â2731; val/test sequential). ÃƒÆ’Ã…Â½Ãƒâ€šÃ‚Â¸_conf chosen on val
  operating curve @ false-commit ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°Ãƒâ€šÃ‚Â¤ 0.05, applied to test. 97 tests green, ruff/mypy clean, `--smoke` verified.
  **DEVELOPER-RUN next:** `python -m eval.confirm` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ `runs/tcn_streaming_v30/confirm_report.json` (offline+fast).
- **[F13] DONE (code+smoke) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â streaming eval, within-sign emission dynamics:** `eval/streaming_dynamics.py` +
  `model/config/streaming_dynamics.yaml` + `tests/test_streaming_dynamics.py`. Diagnostic-only. 4 cross-signer
  metrics from sign onset (frame 0 = span start): time-to-first-correct + time-to-stable-correct (p50/p95, frames
  + fraction-of-sign), flicker (argmax-switches/sign) + settled-fraction, and calibrated top-1 confidence over 10
  sign-time deciles. Never-correct% + never-settles% surfaced separately. Memory-safe (batched ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ per-clip summaries).
  104 tests green, ruff/mypy clean. **RESULT (official test, 29,770 clips/11 signers):** calibrated confidence
  RAMPS then DECAYS (deciles .06ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢.52 peak ~60ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ70%, ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢.47 at end) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ evidence-accumulation VALIDATED; commit MID-SIGN
  not at end. never-correct 48% / never-settles 73% (27% settle = matches last-frame 0.268); TTFC p50 0.39, TTSC
  p50 0.71 of sign; flicker 13.5/sign. Bottleneck = SUSTAINED accuracy (touches 52% vs sustains 27%), model/data-
  limited not architecture. See memory `project-mid-sign-confidence-peak`. (Note: config strÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢Path bug fixed post-smoke.)
- **ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ PHASE 1 CODE-COMPLETE (F10ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œF13):** streaming features + per-frame head + confirmation (S7) + dynamics eval,
  all built/tested/developer-run on official test. Architecture validated; model/data-limited as expected.
- **ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ PHASE 2 (CTC) DEFERRED ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ PHASE 3 (Android) STARTED (developer decision 2026-07-05):** Phase 2 needs continuous
  data ASL Citizen lacks; jump to on-device runtime with the current streaming+confirmation model. CTC returns when
  continuous data exists. **Phase-3 verification = developer runs Android Studio on a device** (agent writes Kotlin
  but can't compile/run Android here); only Python artifacts are agent-smoke-testable. **Landmarker mode = IMAGE**
  (per-frame stateless) to match offline extraction for train/serve parity ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â temporal continuity is ours (streaming
  TCN + S3 One-Euro), NOT MediaPipe's tracker. IMAGE mode ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°Ãƒâ€šÃ‚Â  snapshot; app is still fully continuous/real-time.
- **[P3-bridge] DONE (code+smoke, agent-run) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â TFLite INT8 export:** `deploy/export_tflite.py` + `deploy/config/export.yaml`
  + `tests/test_export.py`. `best.keras`ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢INT8 `streaming.tflite` (~200KB), PTQ calibrated on real train features,
  float32 in/out + INT8 internals, fixed 96-frame window (ring-buffer streaming = F19). Ships `model_manifest.json`
  (schema 3.0 + shapes + T=0.715 + operating point + SHAs + parity). Drift GATE: per-frame argmax agreement ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°Ãƒâ€šÃ‚Â¥0.98 AND
  clip top1 delta ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°Ãƒâ€šÃ‚Â¤0.01. RAM-safe mmap-slice (no full-split load). 108 tests green.
- **ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ P3-bridge DONE (agent-run): INT8 export PASSES.** `streaming.tflite` (415KB) + `model_manifest.json` written.
  GATE = canonical PTQ acceptance: top-1 delta **0.002** + mean abs prob diff **0.00016**. A quant SCARE was
  investigated & resolved (memory `project-int8-quant-nearties`): ~15% clip-argmax disagreement / ~6% churn are
  PROVEN-BENIGN sub-1%-margin near-tie reshuffle (FLOAT/FLOAT16 = 1.000; INT8 exact for confÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°Ãƒâ€šÃ‚Â¥0.4; calib sampling
  ruled out). Kept INT8 (v2 lesson g; float16=GPU-only win, GPU banned). Lesson: investigate alarming parity metrics,
  don't tune thresholds. Committable/retention/argmax = diagnostics, gate = accuracy+fidelity.
- **[F17] DONE (code, DEVICE-VERIFY PENDING) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Android capture + landmarkers (S0/S1/S2).** Android project at `android/`
  (dev-created skeleton: Empty Views Activity, Kotlin, AGP 8.11.2/Kotlin 2.0.21/compileSdk36/minSdk26, pkg `com.example.apphear`).
  Agent wrote all code: CameraX 1.3.4 + MediaPipe tasks-vision 0.10.14 + coroutines; `LandmarkerConfig.kt` (parity mirror of
  pipeline/extract ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â IMAGE mode, 2 hands/1 pose/conf 0.5, MIN_FPS 15), `LandmarkerBundle`, `FrameAnalyzer` (hand+pose PARALLEL,
  busy-guard, fps), `FpsTracker`, `ui/OverlayView`, `MainActivity` (perm, async model load off-main-thread, CameraX KEEP_ONLY_LATEST
  + RGBA_8888, fps HUD + degraded banner). Model .task files copied byte-identical into app assets. No S4/S6/S7 yet.
  **VERIFICATION = developer builds+runs on PHYSICAL phone in Android Studio** (agent can't compile Android). Gradle may flag a dep
  version ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ paste error, agent bumps. **Android feature verification is device-side, not agent-smoke-testable.**
- **ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ F17 DEVICE-VERIFIED + DONE (2026-07-05):** ran on dev's old Xiaomi/Adreno ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â camera streaming, both landmarkers on
  XNNPACK-CPU, live overlay, no crash. Added ADAPTIVE safety net (`AdaptiveController`: hands every frame, pose cadence
  1ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢4 held-between, quality tier in HUD; res capped 640ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â480) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â settles LowÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂMinimum on that phone, accepted (fps ceiling =
  hardware). Held-pose parity caveat recorded for F18/F19 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ memory `project-adaptive-pose-cadence`.
- **[F18] DONE (code + port-logic-validated, developer JVM-test pending) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â S3/S4 feature port.** `/architect`: (1) exact-port
  + skew test FIRST (causal online-param estimation deferred), (2) DEFER S3 One-Euro (training is un-smoothed ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ S3=identity now).
  Key realization: runtime can't compute the non-causal params (scale/roll/mirror use future frames) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ F18 proves the MATH ports
  byte-exact (full span fed), causal skew measured later. Built: `export_golden.py` (ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ 8 val clips JSON golden, in android test
  resources), Kotlin `Topology.kt`+`S4Features.kt` (full N1-N3+258 port, flat frames pose[k*4+c]/hands[(s*21+l)*3+c]),
  `S4SkewTest.kt` (JVM, gson, tol 1e-4). **Pre-validated the port ALGORITHM in Python vs golden ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ worst diff 1.11e-6 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°Ãƒâ€šÃ‚Âª 1e-4**
  (logic proven; only Kotlin compile issues could remain). **ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã…â€œÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ SKEW TEST GREEN (developer, `.\gradlew testDebugUnitTest` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢
  BUILD SUCCESSFUL): Kotlin S4 == Python byte-exact ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â°Ãƒâ€šÃ‚Â¤1e-4. #1 train/serve-parity surface PROVEN. F18 exact-port DONE.**
- **NEXT after F18 green:** causal online-param estimator (scale/roll/mirror from past frames) + measure causal skew; then F19
  (TFLite recognition + S5 gating, uses `streaming.tflite`+manifest), F20 confirmation+sentence on-device, F21 UI, F22 device smoke.
  Held-pose cadence caveat open (memory `project-adaptive-pose-cadence`).

## Next session starts with

**BOTH PILOTS DONE ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â both risks retired; committing to the full corpus.**
- 20-class: test top1=0.54 / top5=0.87 (per-signer 0.48ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ0.64, uniform).
- 100-class: test top1=0.414 / top5=0.744 (per-signer 0.33ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ0.49, uniform, no collapse; T=1.23, ECE 0.06).
- Findings: class scaling GRACEFUL (5ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â classes ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ ÃƒÆ’Ã‚Â¢Ãƒâ€¹Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢13 top-1 pts, 41ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â chance; cross-signer holds);
  model DATA-STARVED (100-class overfit train0.91/val0.48 at ~18 clips/class) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ full corpus is the fix.
**Next:** the full ~83k extraction is the bottleneck (single-process ~many hours). Decision pending:
build PARALLEL (multiprocess) extraction first so it's ~hours, then developer runs full extraction ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢
`python -m model.train` (60ep+earlystop) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ `python -m eval.run`. Consider more regularization at full scale.

**Two DEVELOPER-RUN long jobs (user does these; training is slow):**
1. Full extraction: `python -m pipeline.run_pipeline --split train --build-vocab`, then
   `--split val`, `--split test` (MediaPipe over ~83k videos ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ v3.0 features per split).
2. Real training: `python -m model.train` (multi-epoch; checkpoints to the runs dir).

3. First real cross-signer number: `python -m eval.run` (harness is built; reads the trained
   checkpoint + test split, fits temperature on val, writes `eval_test.json`).

After that: optional **feature 09 (v3.1 kinematic ablation)** ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â adopt only on a cross-signer
win over v3.0 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â else move to **Phase 1 (streaming: N4 off, per-frame emission, confirmation)**.

Caveat still open: features extracted so far are 1 signer (P5); the full run above fixes that.
Re-check D1/D2 thresholds + N3 handedness-label finding once multi-signer features exist.

## Open questions / caveats

- Detect thresholds tuned on val's **6 signers only**; re-validate broader before full run.
- Extracted clips so far are **one signer (P5)** ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â cross-signer distributional checks (N1-N3
  variance collapse, N3 handedness labeling: mask L=100%/R=62%) pending multi-signer features.
- `mirror_exempt` per-gloss list for handedness-lexical signs deferred (empty).
- N4/Q thresholds lenient starting values; tune on rejection distribution.







---

# Memory - Native Android Full-Application Redesign Assessment

Last updated: 2026-07-21 14:32 +08:00

## What was built
- Inspected production `android/` and the external AppHear2 UI/flow reference without changing application source.
- Baseline `android` unit tests and debug assemble passed.
- Added six linked Android redesign context documents and wired them into AGENTS, architecture, build plan, and progress tracker.

## Decisions made
- AppHear3 remains the runtime, dependency, camera, model, and recognition source of truth.
- Target architecture is a non-camera navigation shell plus a dedicated recognition activity behind a UI-state adapter.
- Tokenize/rebuild AppHear2 UI; guest/offline first; defer Supabase/cloud/conversation; exclude old ML, face, batch, and settings logic.

## Problems solved
- Documented same-package/resource conflicts, unsafe auth/session characteristics, obsolete runtime settings, unreachable conversation route, and asset/APK-size risks.
- Established phased build, testing, rollback, dependency, resource, and protected-file gates before implementation.

## Current state
- Assessment is complete; no file under `android/app/src` changed.
- Phase 2 design-system foundation is next, but implementation has not started.

## Next session starts with
- Establish a recoverable source-control/backup point and verify license approval for the first asset/font slice, then implement only the Phase 2 token files listed in `context/android-migration-plan.md`.

## Open questions
- Source-control root/backup destination.
- Release scope for auth, cloud TTS, GLB avatar, history, and the currently unreachable conversation feature.
- Licensing/provenance for Inter, mascot/icon art, launcher art, and GLB animations.

---
# Memory - Native Android Redesign Phase 2 Token Foundation

Last updated: 2026-07-21 14:55 +08:00

## What was built
- Proceeded from assessment into the first narrow development phase for `F:/ASL DATASET/5. Apphear3/android/`.
- Created rollback copy: `C:/tmp/apphear3-android-backup-20260721-uidesign-phase2/` because the workspace root is still not a Git worktree.
- Added semantic design-system resources only:
  - `android/app/src/main/res/values/colors.xml`
  - `android/app/src/main/res/values/dimens.xml`
  - `android/app/src/main/res/values/typography.xml`
  - `android/app/src/main/res/values/styles.xml`
  - `android/app/src/main/res/values/themes.xml`
  - `android/app/src/main/res/values-night/themes.xml`
- Updated `context/android-design-system.md`, `context/android-migration-plan.md`, and `context/progress-tracker.md`.

## Decisions made
- No AppHear2 fonts or visual assets were imported because licensing/provenance remains unresolved.
- No recognition pipeline, camera, model, temporal, confirmation, layout, manifest, Gradle, or asset files were changed.
- Shared styles use conservative Material3 parents verified against local Material 1.14.0 resources.

## Problems solved
- Initial build failed because `Widget.Material3.MaterialCardView.Filled` was not a valid local Material style and an unparented dotted custom style implicitly referenced `Widget.AppHear`; fixed with `Widget.Material3.CardView.Filled` and an explicit status-chip parent.

## Current state
- Android `testDebugUnitTest assembleDebug` passes.
- Phase 2 no-asset token foundation is complete.
- Navigation shell, screens, shared components, fonts/assets, and recognition restyling are not started.

## Next session starts with
- Proceed to Phase 3 navigation shell placeholders, or first approve/import a small licensed font/asset slice if visual fidelity is prioritized.

## Open questions
- Source-control root/branch remains unavailable.
- Inter/mascot/launcher/GLB asset licensing remains unresolved.
- First-release scope for auth, cloud TTS, history, text-to-ASL, and conversation remains unresolved.

---
# Memory - Native Android Redesign Phase 3 Navigation Placeholders

Last updated: 2026-07-21 15:20 +08:00

## What was built
- Added Phase 3 navigation shell scaffolding in the production native Android app.
- Added AndroidX Navigation stable `2.9.8` to the version catalog and app dependencies.
- Added non-exported `ui.shell.AppShellActivity` with `activity_app_shell.xml`.
- Added placeholder fragments/layouts for Home, Text-to-ASL, Profile, and Settings.
- Added `res/navigation/app_shell_nav.xml` and `res/menu/app_shell_bottom_nav.xml`.
- Home placeholder starts the existing `MainActivity` recognition baseline explicitly.
- Updated Android redesign context files and progress tracker.

## Decisions made
- Existing `MainActivity` remains the launcher and recognition baseline.
- `AppShellActivity` is non-exported and not a primary entry point until a later launcher-switch phase.
- No recognition runtime ownership was moved into fragments or the shell.

## Problems solved
- PowerShell initially wrote UTF-8 BOMs into TOML/XML files; Gradle/resource parsing failed. Rewrote touched files as UTF-8 without BOM.
- Navigation dependency insertion initially missed due line-ending mismatch; added catalog and dependency entries explicitly.

## Current state
- `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passes.
- Protected recognition files and model/MediaPipe assets hash-match the rollback copy.
- Shell placeholders build, but are not launcher-visible yet except via explicit activity launch/development route.

## Next session starts with
- Phase 4 shared components, or a single Phase 5 non-camera screen refinement. Do not switch the launcher or move recognition until the shell route and recognition route have device/navigation verification.

## Open questions
- Source-control root/branch remains unavailable.
- Font/art/GLB provenance remains unresolved.
- Product scope for auth, cloud TTS, history, text-to-ASL asset coverage, and conversation remains unresolved.
---
# Memory - Native Android Redesign Phase 4 Shared Components

Last updated: 2026-07-21 15:45 +08:00

## What was built
- Added passive shared UI component resources in the native Android app:
  - `component_status_chip.xml`
  - `component_feature_card.xml`
  - `component_settings_row.xml`
  - `component_bottom_panel.xml`
  - `component_loading_state.xml`
  - `component_empty_state.xml`
  - `component_error_state.xml`
  - `apphear_status_chip_bg.xml`, `apphear_status_dot_ready.xml`, `apphear_icon_circle_bg.xml`, `apphear_bottom_panel_bg.xml`, `apphear_drag_handle_bg.xml`
- Added component string resources.
- Updated Android redesign context files and progress tracker.

## Decisions made
- Components are XML/resource-only scaffolds; they do not contain runtime, backend, WebView, auth, history, or recognition logic.
- The existing recognition launcher and AppHear3 S0-S8 runtime remain untouched.

## Problems solved
- `strings.xml` remained valid but became hard to read after appending component strings; normalized formatting and rebuilt.

## Current state
- `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passes.
- Protected recognition files and model/MediaPipe assets hash-match the rollback copy.
- Phase 5 can begin with Home/dashboard or another single non-camera screen group.

## Next session starts with
- Start Phase 5 Home/dashboard migration using the shell placeholders and `component_feature_card.xml`; keep `MainActivity` recognition as launcher until launcher-switch verification is explicitly planned.

## Open questions
- Source-control root/branch remains unavailable.
- Font/art/GLB provenance remains unresolved.
- First-release scope for auth, cloud TTS, local history, text-to-ASL asset coverage, and conversation remains unresolved.
---
# Memory - Native Android Redesign Phase 5 Home Dashboard

Last updated: 2026-07-21 16:05 +08:00

## What was built
- Migrated the shell Home/dashboard screen from placeholder to build-green UI.
- Rebuilt AppHear2 reference structure with AppHear3 resources: header, status chip, hero copy, recent activity chip, recognition feature card, and Text-to-ASL card.
- Updated `HomeFragment.kt` click handling: Recognition opens the existing `MainActivity`; Text-to-ASL navigates to `textToAslFragment`.
- Added `home_feature_recognition_bg.xml`, `home_feature_translator_bg.xml`, `home_recent_chip_bg.xml`, and Home string resources.
- Updated Android migration plan, screen mapping, progress tracker, and memory.

## Decisions made
- No AppHear2 ViewPager2 carousel was added; simple stacked cards are sufficient until visual QA demands a carousel.
- Recent activity is shown honestly as empty local history; AppHear2 `RecentSignsStore` was not copied because it stores text-input words, not detected signs.
- No AppHear2 fonts, mascot images, auth manager, profile data, old SignDetect activity, or runtime code was imported.

## Problems solved
- Kept Home connected to the protected recognition baseline without switching launcher or moving camera/runtime ownership.

## Current state
- `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passes.
- Protected recognition files and model/MediaPipe assets hash-match the rollback copy.
- Home/dashboard is BUILD GREEN; Text-to-ASL/Profile/Settings remain placeholders.

## Next session starts with
- Continue Phase 5 with one non-camera screen group: recommended next is guest Profile/settings, or Text-to-ASL shell refinement if translator UX is higher priority.

## Open questions
- Source-control root/branch remains unavailable.
- Font/art/GLB provenance remains unresolved.
- Product scope for auth, cloud TTS, local history, text-to-ASL asset coverage, and conversation remains unresolved.
---
# Memory - Native Android Redesign Phase 5 Guest Profile Settings

Last updated: 2026-07-21 16:35 +08:00

## What was built
- Migrated the shell Profile and Settings placeholders to build-green native XML/Kotlin screens.
- Added guest/local profile UI, status copy, Settings navigation, selective settings rows, and tokenized profile/settings drawables.
- Updated Android migration plan, screen mapping, and progress tracker.

## Decisions made
- AppHear2 ProfileActivity was used only as a visual/flow reference.
- Supabase auth/profile editing/avatar upload remain deferred until a backend/security contract exists.
- Old AppHear2 AppSettings detector/model toggles are excluded; AppHear3 recognition runtime remains the only source of truth.

## Problems solved
- Replaced vague Profile/Settings placeholders with truthful local/deferred states without coupling settings UI to low-level camera/inference classes.

## Current state
- `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passes.
- Protected recognition activity/layout/model config/vocab/TFLite/MediaPipe task assets hash-match the rollback copy.
- Home/dashboard and guest Profile/settings are BUILD GREEN in the shell; Text-to-ASL remains scaffolded.

## Next session starts with
- Continue Phase 5 with Text-to-ASL shell refinement. Do not add WebView/GLB assets or speech behavior until the asset/provenance and data-contract gates are documented.

## Open questions
- Source-control root/branch remains unavailable.
- Font/art/GLB provenance remains unresolved.
- Product scope for auth, cloud TTS, local history, text-to-ASL asset coverage, and conversation remains unresolved.
---
# Memory - Native Android Redesign Phase 5 Text To ASL Shell

Last updated: 2026-07-21 16:55 +08:00

## What was built
- Migrated the shell Text-to-ASL placeholder to build-green native XML/Kotlin UI.
- Added avatar-stage placeholder, sign overlay, bottom translator panel, text/speech toggle, local text preview, replay/clear controls, and route to existing protected recognition `MainActivity`.
- Added translator-specific `apphear_*` drawables and Text-to-ASL string resources.
- Updated Android migration plan, screen mapping, and progress tracker.

## Decisions made
- AppHear2 `TextToAslActivity` was used only for visual/flow reference.
- WebView/avatar playback, GLB assets, speech recognition, phrase planning, TTS/cloud speech, and recent-store behavior remain deferred.
- The screen is honest local UI state only until asset provenance, size budget, WebView security, vocabulary mapping, privacy, and data contracts are documented.

## Problems solved
- Text-to-ASL is no longer a vague placeholder; it has production-shell navigation and truthful deferred-state copy without adding risky dependencies or assets.

## Current state
- `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passes.
- Protected recognition activity/layout/model config/vocab/TFLite/MediaPipe task assets hash-match the rollback copy.
- Home/dashboard, guest Profile/settings, and Text-to-ASL shell are BUILD GREEN in the shell.

## Next session starts with
- Choose either onboarding/startup shell work or a documented recognition-screen integration plan. Do not add Text-to-ASL WebView/GLB/speech behavior until the gates are closed.

## Open questions
- Source-control root/branch remains unavailable.
- Font/art/GLB provenance remains unresolved.
- Product scope for auth, cloud TTS, local history, text-to-ASL asset coverage, onboarding, launcher switch, and conversation remains unresolved.
---
# Memory - Native Android Redesign MainActivity Homepage Decision

Last updated: 2026-07-21 17:05 +08:00

## What was built
- No app code changed in this note.
- Updated durable context docs to clarify final app architecture.

## Decisions made
- Final `MainActivity` is the homepage/shell entry point.
- A dedicated `RecognitionActivity` must own the AppHear3 camera/recognition runtime, similar to AppHear2's separate sign-detection screen structure.
- Current recognition-bearing `MainActivity` is temporary baseline only; Phase 6 should create and verify `RecognitionActivity` first, then convert `MainActivity` into the shell/homepage.

## Problems solved
- Removed ambiguity caused by the temporary `AppShellActivity` scaffold and the current recognition-bearing `MainActivity`.

## Current state
- Home/dashboard, guest Profile/settings, and Text-to-ASL shell are build-green in the temporary shell scaffold.
- Recognition still runs from current `MainActivity` until `RecognitionActivity` migration is implemented and verified.

## Next session starts with
- Phase 6: create a dedicated `RecognitionActivity` from the current AppHear3 recognition behavior without changing camera, inference, temporal, confirmation, model, or sentence logic. After verification, fold shell/homepage behavior into `MainActivity`.

## Open questions
- Source-control root/branch remains unavailable.
- Physical-device F22 smoke will be required for the recognition activity migration.
---
# Memory - Native Android Redesign Phase 6 RecognitionActivity Parity Scaffold

Last updated: 2026-07-21 17:25 +08:00

## What was built
- Added `android/app/src/main/java/com/example/apphear/RecognitionActivity.kt` as a non-launcher parity activity using current AppHear3 recognition behavior.
- Added `android/app/src/main/res/layout/activity_recognition.xml` copied from the current baseline recognition layout with `tools:context` updated.
- Registered `.RecognitionActivity` as `android:exported="false"` in `AndroidManifest.xml`.
- Updated Home and Text-to-ASL recognition actions to start `RecognitionActivity`.
- Updated Android migration plan, screen mapping, UI architecture doc, and progress tracker.

## Decisions made
- Existing `MainActivity` remains the launcher and protected baseline until `RecognitionActivity` passes device smoke.
- This slice is behavioral parity only; no AppHear2 recognition code, visual redesign, model/config change, camera behavior change, or pipeline refactor was introduced.
- Final `MainActivity` homepage/shell conversion comes after `RecognitionActivity` is verified.

## Problems solved
- Created the safe bridge needed before turning `MainActivity` into the homepage.
- During routing, `HomeFragment.kt` was briefly overwritten by the PowerShell `$HOME` variable after a reserved-variable collision; it was immediately restored to the intended source and build-verified.

## Current state
- `./gradlew.bat assembleDebug --console=plain --no-daemon --max-workers=2` passes.
- `./gradlew.bat testDebugUnitTest --console=plain --no-daemon --max-workers=2` passes.
- Protected `MainActivity.kt`, `activity_main.xml`, model config, vocab, TFLite model, and MediaPipe task assets hash-match the rollback copy.
- `RecognitionActivity` is build-green but not device-smoke verified.

## Next session starts with
- Run/prepare F22 physical-device smoke for `RecognitionActivity`: launch from shell route, camera permission, front/back camera, handedness toggle, overlay alignment, top candidates, sentence/clear, low-FPS banner, navigation away/back, screen-off/on, and repeated open/close resource release.
- After device parity is confirmed, convert `MainActivity` into the homepage/shell and keep `RecognitionActivity` as the recognition destination.

## Open questions
- Source-control root/branch remains unavailable.
- Physical-device verification is pending.
---
# Memory - Native Android Phase 6 RecognitionActivity Automated Device Smoke

Last updated: 2026-07-21 20:30 +08:00

## What was built
- Added `android/app/src/debug/AndroidManifest.xml` to export `.RecognitionActivity` only for debug builds so ADB can launch it directly for smoke testing.
- No production/main manifest export change was made.
- Updated migration plan and progress tracker with smoke evidence.

## Decisions made
- Keep debug-only ADB smoke hook for now because both `RecognitionActivity` and temporary `AppShellActivity` are correctly non-exported in the main manifest.
- Do not treat automated startup/log smoke as full F22 pass; manual interaction/signing checks are still required.

## Problems solved
- Located ADB at `D:/AndroidStudio/Android/Sdk/platform-tools/adb.exe` from `local.properties`.
- Installed and launched debug APK on attached Xiaomi `M2101K7AG`.
- Verified `RecognitionActivity` startup, GPU landmarker load, recognizer load, CameraX stream, perf logging, and repeated direct launch without captured AndroidRuntime crash.

## Current state
- Automated smoke partial PASS on Xiaomi `M2101K7AG`, Android 12 SDK 31.
- Evidence from logs: `landmarkers on GPU delegate`, `recognizer loaded: window=96 classes=236`, CameraX Preview STREAMING, processed FPS roughly 9.6-12.7, camera FPS roughly 20, `low_fps=false` in captured window.
- ADB input injection is denied by this MIUI build, so manual tapping/signing is still required.
- `assembleDebug` and `testDebugUnitTest` pass after debug-only manifest override.
- Protected baseline files/assets still hash-match rollback.

## Next session starts with
- Manual device smoke on the attached phone: tap handedness, tap camera toggle, tap Clear, sign known glosses, verify one-commit-per-bout, no-hands gate, sentence accumulation, and cross-signer behavior.
- After manual smoke passes, convert `MainActivity` into homepage/shell while keeping `RecognitionActivity` as the recognition destination.

## Open questions
- Manual signing/interaction smoke results are pending.
- Source-control root/branch remains unavailable.
---
# Memory - Native Android Phase 6 MainActivity Homepage Shell Conversion

Last updated: 2026-07-21 20:35 +08:00

## What was built
- Converted `android/app/src/main/java/com/example/apphear/MainActivity.kt` into the final homepage/shell host using `ActivityAppShellBinding`.
- Kept `RecognitionActivity` as the dedicated AppHear3 recognition runtime screen.
- Left temporary `AppShellActivity` in place for now as a cleanup candidate.
- Updated migration plan, UI architecture, screen mapping, progress tracker, and memory.

## Decisions made
- Final architecture is now active: `MainActivity` is homepage/shell, `RecognitionActivity` owns recognition runtime.
- Do not remove `AppShellActivity` until route/dependency checks confirm nothing still needs it.
- Manual signing/interaction smoke remains required before calling Phase 6 fully device-verified.

## Problems solved
- Removed recognition runtime ownership from launcher `MainActivity` without touching pipeline/model/assets.
- Verified launcher no longer starts camera/runtime logs, while `RecognitionActivity` still starts runtime successfully.

## Current state
- `./gradlew.bat assembleDebug --console=plain --no-daemon --max-workers=2` passes.
- `./gradlew.bat testDebugUnitTest --console=plain --no-daemon --max-workers=2` passes.
- Device startup check on Xiaomi `M2101K7AG`: `MainActivity` opens shell; `RecognitionActivity` opens recognition and logs GPU landmarkers, recognizer load, and perf metrics.
- Model config, vocab, TFLite, and MediaPipe task assets hash-match rollback.
- Temporary debug manifest exports `RecognitionActivity` only for debug ADB smoke.

## Next session starts with
- Manual interaction/signing smoke for `RecognitionActivity`: hand toggle, camera toggle, Clear, no-hands gate, real sign commits, one-commit-per-bout, sentence accumulation, and cross-signer checks.
- Then remove/retire temporary `AppShellActivity` if no longer referenced.

## Open questions
- Manual device interaction/signing results are pending.
- Source-control root/branch remains unavailable.
---
# Memory - Android UI Reference Correction Home Pass

Last updated: 2026-07-21 00:00 +08:00

## What was built
- Paused later Android migration work to correct UI drift against AppHear2 screenshots and XML.
- Added `context/android-ui-reference-correction.md` as the active screenshot/XML fidelity tracker.
- Corrected Home/dashboard against AppHear2 `activity_main.xml`, `item_feature_card_detect.xml`, `item_feature_card_project.xml`, and `nav_bottom.xml`.
- Imported only selected non-conflicting AppHear2 Home/nav fonts, mascots, icons, chips, dots, buttons, and nav drawables.
- Added `FeatureCardAdapter.kt` in Kotlin and `androidx.viewpager2:viewpager2:1.1.0` for the AppHear2-style Home carousel.
- Replaced shell Material BottomNavigationView with AppHear2-style custom `nav_bottom.xml`.

## Decisions made
- AppHear3 recognition remains source of truth. Home detection actions route to `RecognitionActivity`, not AppHear2 `SignDetectActivity`.
- AppHear2 Java auth/recent-store/runtime logic was not copied.
- Card XML was adapted to existing Material Components instead of adding AppHear2 CardView dependency.
- Remaining screenshot pages must be corrected one group at a time before later feature migration resumes.

## Problems solved
- Current Home screen no longer uses the earlier generic Material-card approximation.
- Build stayed green after the Home/nav UI resource import and ViewPager2 addition.

## Current state
- Verification passed: `assembleDebug`, `testDebugUnitTest`, and protected AppHear3 model/config/MediaPipe asset hash check.
- ADB listed no attached device during the final check, so visual/device smoke remains pending.
- Remaining UI screenshot corrections: Recognition collapsed/expanded, Text-to-ASL collapsed/expanded, Settings/preferences, Splash, and Loading.

## Next session starts with
- Correct the next screenshot group. Recommended order: Recognition UI if addressing the highest-value visible surface, or Text-to-ASL if choosing the safer non-camera screen first.
- For Recognition UI, inspect AppHear2 `activity_sign_detect.xml` but preserve AppHear3 `RecognitionActivity` runtime bindings and behavior.

## Open questions
- Confirm visual fidelity on a physical device once ADB detects a device.
- Confirm provenance/license for imported Inter fonts and AppHear2 raster assets before release.
---
# Memory - Android UI Reference Correction Recognition Pass

Last updated: 2026-07-21 21:20 +08:00

## What was built
- Corrected `RecognitionActivity` visual layout against AppHear2 `activity_sign_detect.xml` and recognition collapsed/uncollapsed screenshots.
- Imported selected non-conflicting AppHear2 sign-detect visual resources only.
- Preserved AppHear3 recognition binding IDs and runtime behavior.
- Added UI-only back and bottom-sheet expand/collapse handlers.

## Decisions made
- AppHear3 remains source of truth for camera, MediaPipe, model inference, temporal logic, confirmation, sentence building, and runtime state.
- AppHear2 START/STOP and old detection lifecycle were not copied. The bottom-sheet control is a passive LIVE indicator because AppHear3 starts recognition automatically.
- AppHear2 face landmark UI/logic was not imported.

## Problems solved
- Recognition screen no longer uses the plain debug/prototype overlay UI.
- Recognition runtime still starts after the visual correction.

## Current state
- `assembleDebug` passed.
- `testDebugUnitTest` passed.
- Protected AppHear3 model/config/MediaPipe asset hashes matched rollback backup.
- Device smoke on Xiaomi `M2101K7AG` passed startup: GPU landmarkers loaded, recognizer loaded `window=96 classes=236`, AppHearPerf streamed frames.
- Device screenshot saved at `C:/Users/Gigabyte/.codex/visualizations/2026/07/21/019f834f-c7cd-7053-89a4-245ab1a0b669/apphear-device-smoke/recognition_ui.png`.

## Next session starts with
- Continue UI correction with Text-to-ASL collapsed/expanded screenshots against AppHear2 `activity_text_to_asl.xml`, or settings/preferences if prioritizing profile/settings.

## Open questions
- Manual visual QA is still needed because automated screenshot inspection is unavailable in this Windows sandbox.
- Asset/font provenance and APK-size impact remain release gates.
---
# Memory - Android UI Reference Correction Text-to-ASL Pass

Last updated: 2026-07-21 21:30 +08:00

## What was built
- Corrected `TextToAslFragment` visual layout against AppHear2 `activity_text_to_asl.xml` and Text-to-ASL collapsed/uncollapsed screenshots.
- Imported selected non-conflicting AppHear2 Text-to-ASL toggle/mic resources only.
- Preserved local preview/deferred behavior and recognition routing to AppHear3 `RecognitionActivity`.

## Decisions made
- Did not enable AppHear2 WebView/avatar playback, GLB assets, speech recognition, ElevenLabs, Android TTS, recent-store, backend, or old Java behavior.
- Kept the avatar area as a native placeholder until asset/provenance/lifecycle/security gates are documented.

## Problems solved
- Text-to-ASL no longer uses the earlier rough AppHear3 approximation; it now follows AppHear2 screen structure and controls.

## Current state
- `assembleDebug` passed.
- `testDebugUnitTest` passed.
- Protected AppHear3 model/config/MediaPipe asset hashes matched rollback backup.
- Device install/MainActivity launch passed, but MIUI blocked ADB tap injection, so Text-to-ASL visual device screenshot remains pending.

## Next session starts with
- Continue UI correction with settings/preferences screenshots, then splash/loading.

## Open questions
- Manual visual QA still needed for Text-to-ASL collapsed/uncollapsed states.
- Decide whether to add a debug-only route/deep link for direct fragment smoke screenshots, or rely on manual navigation.---
# Memory - Android UI Reference Correction Settings/Profile Pass

Last updated: 2026-07-22 00:00 +08:00

## What was built
- Corrected `ProfileFragment` and `SettingsFragment` visually against AppHear2 `activity_profile.xml`, AppHear2 `row_setting_*.xml`, and the settings/preference screenshots.
- Imported selected AppHear2 profile/settings drawables and row layouts into AppHear3.
- Kept AppHear3 shell/navigation and recognition runtime unchanged.

## Decisions made
- AppHear2 auth/profile Java logic, Supabase behavior, preference persistence, backend calls, and runtime-setting mutations were not copied.
- AppHear2 switch rows are visual/passive only and cannot control AppHear3 recognition.
- `EDIT PROFILE` remains an AppHear2 visual affordance but routes to the AppHear3 Settings/Preferences fragment.

## Problems solved
- Profile/Settings no longer use the earlier generic Material approximation.
- Fixed a BOM/invalid-leading-byte XML write issue in `fragment_settings.xml`.
- Avoided treating a parallel Gradle output-cleanup collision as a code failure; sequential test rerun passed.

## Current state
- `assembleDebug` passed.
- `testDebugUnitTest` passed sequentially.
- Protected AppHear3 model/config/MediaPipe asset hashes matched rollback backup.
- Manual visual QA remains pending.

## Next session starts with
- Correct the remaining splash and loading screenshots against AppHear2 `activity_splash.xml`, `bg_splash_screen.xml`, `splash.png`, `activity_loading.xml`, and loading logo/drawables.

## Open questions
- Manual screenshot/device QA remains pending for Settings/Profile and Text-to-ASL route states.
- Asset/font provenance and APK-size impact remain release gates.---
# Memory - Recognition Page Model-Test Architecture Pass

Last updated: 2026-07-22 08:10 +08:00

## What was built
- Added a pure `RecognitionUiSnapshot` adapter and unit tests for recognition display state.
- Updated `RecognitionActivity` to render AppHear3 `RecognitionState` through the adapter.
- Added persistent model-load failure UI for candidate-model testing.
- Wired the AppHear2-style SPEAK visual to a deferred-message toast only.

## Decisions made
- AppHear3 remains the only source of truth for CameraX, MediaPipe, TFLite, temporal buffering, confirmation, sentence building, and model contract validation.
- AppHear2 detection pipeline, old runtime classes, face landmarks, START/STOP lifecycle, and old model assets remain excluded.
- Current candidate model/config assets were not reverted even though they differ from the old UI-phase backup.

## Problems solved
- Recognition UI rendering is now separated from low-level pipeline behavior enough to support safer model-test UI changes.
- Model-load failure is no longer only a transient toast.

## Current state
- `testDebugUnitTest assembleDebug` passed.
- No phone was attached during ADB check, so device launch/manual recognition QA is pending.
- Current assets indicate a 236-class candidate model/config state written before this pass.

## Next session starts with
- Attach phone and run RecognitionActivity smoke against the current candidate model: launch, confirm model load log, sign controlled glosses, verify top candidates/commit/sentence/clear/camera/hand controls.

## Open questions
- Confirm whether the current candidate model/config is the intended one for the next device test.
- Manual visual QA for the redesigned recognition page remains pending.---
# Memory - Android Encoding Cleanup

Last updated: 2026-07-22 08:20 +08:00

## What was built
- Cleaned corrupted/mojibake Android text in `strings.xml` and `S4SkewTest.kt`.

## Decisions made
- Use plain ASCII for runtime control labels where possible to avoid repeat encoding damage.

## Problems solved
- Removed visible corrupted symbols from Android UI resources.

## Current state
- Broad scan for common mojibake patterns under Android main resources/source and unit-test source is clean.
- `testDebugUnitTest assembleDebug` passed.

## Next session starts with
- Continue recognition-page/device smoke or model test setup.

## Open questions
- None for encoding cleanup.

---
# Memory - Android Low-FPS Bottleneck Architecture Checkpoint

Last updated: 2026-07-22

## What was built
- No app/source/model changes were made in this checkpoint.
- Saved the current candidate-model A/B state and bottleneck plan into `context/progress-tracker.md` and `context/recognition-accuracy.md`.

## Decisions made
- The current Android assets are a local supplementary 236-class candidate for device A/B testing, not a proven default replacement.
- The real runtime bottleneck remains MediaPipe hand + pose landmarking. Camera input is higher than processed recognition FPS because stale camera frames are intentionally skipped while landmarking is busy.
- TFLite recognition is not the FPS bottleneck.
- React Native is not the fix for this bottleneck; continue native Android runtime experiments.
- Do not change the 258-feature contract, drop hand/pose features, replace the TCN, or loosen thresholds without logs.

## Problems solved
- Clarified why camera input can be about 14-17 FPS while processed recognition is only about 3-4 FPS: MediaPipe frame processing takes too long, so CameraX/backpressure keeps only fresh frames and drops older ones.
- Clarified the candidate model's device behavior: `KNOW` and `WANT` improved, but `CUT` can commit as `WE`, `IMPORTANT` can commit as `FAMILY`/`TEACH`, and `SELL` can commit as `PUT` at very low FPS.

## Current state
- Android app assets currently point to the local supplementary 236-class candidate copied from `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/runs/tcn_streaming_conversational_plus_local_pc_236_rtx3050_v30/android_candidate_assets/`.
- Revert backup for the previous deployed assets is preserved at `android/app/src/main/assets/_backup_before_local_pc_236_candidate_20260722-075734/`.
- Latest observed device state: low-FPS mode active; processed recognition FPS can fall to about 3-4 FPS while camera input remains higher; wrong early commits are likely amplified by `low_fps_confirmation.min_commit_frame=2`.

## Next session starts with
- Architect/implement the first reversible runtime experiment: strict low-FPS confirmation config A/B, likely raising `low_fps_confirmation.min_commit_frame` from 2 to about 4 and requiring more stability, then rebuild and test the same controlled signs.
- If strict confirmation reduces wrong commits but delays/drops too much, proceed to the real FPS levers: MediaPipe GPU-vs-CPU delegate A/B, lower analyzer resolution, and pose cadence sweep.

## Open questions
- Should the next test keep the local candidate and make confirmation stricter, or first revert to the previous deployed assets and run the same bottleneck experiments there?
- Which exact analyzer resolutions should be tested first on the low-FPS phone?

---
# Memory - Strict Low-FPS Confirmation A/B Config

Last updated: 2026-07-22 08:50 +08:00

## What was built
- Config-only strict low-FPS confirmation A/B for the current local supplementary 236-class Android candidate.
- Changed only `android/app/src/main/assets/recognition_config.json`.

## Decisions made
- First experiment targets early wrong commits, not FPS itself.
- New low-FPS confirmation settings: `min_commit_frame=4`, `k_stability=3`, `theta_margin=0.9`.
- This is intentionally stricter than the previous candidate settings `min_commit_frame=2`, `k_stability=2`, `theta_margin=0.75`.

## Problems solved
- Preserved a clean rollback point before changing the candidate config: `android/app/src/main/assets/_backup_before_strict_lowfps_confirm_20260722-084845/`.
- Built a debug APK with the strict config.

## Current state
- `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed.
- APK for testing: `android/app/build/outputs/apk/debug/app-debug.apk`.
- No ADB device was attached, so install/manual test is pending.

## Next session starts with
- Install the debug APK on the Android phone and test the same controlled signs: CUT, IMPORTANT, SELL, WANT, KNOW, FAMILY, TEACH, PUT, WE.
- Compare against the previous log: fewer wrong early commits is good; too many delayed/missed commits means the strict setting is too conservative.

## Open questions
- Does `min_commit_frame=4` reduce `CUT` -> `WE`, `IMPORTANT` -> `FAMILY`/`TEACH`, and `SELL` -> `PUT` without making confirmation unusably slow?
- If confirmation remains wrong at 3-4 FPS, should we revert model assets first or move immediately to MediaPipe CPU/GPU and resolution A/B?

---
# Memory - MediaPipe Delegate CPU/GPU A/B Switch

Last updated: 2026-07-22 09:25 +08:00

## What was built
- Added config-selected MediaPipe landmarker delegate support to `LandmarkerBundle`.
- Added `mediapipe_delegate.mode` to current `recognition_config.json` and set it to `cpu` for the next A/B test.

## Decisions made
- The previous strict-confirmation GPU log is the comparison baseline.
- This build is a CPU landmarker test only; it keeps the same candidate model, same strict low-FPS confirmation, same pose cadence, and same 258-feature contract.
- If CPU is worse or equal, revert the config to `gpu` and proceed to analyzer resolution reduction.

## Problems solved
- CPU/GPU landmarker comparison no longer requires changing Kotlin constants each time.
- Startup logs now expose the selected delegate mode so logcat can prove which path ran.

## Current state
- `recognition_config.json` contains `mediapipe_delegate.mode=cpu`.
- Rollback/config backup: `android/app/src/main/assets/_backup_before_cpu_delegate_ab_20260722-091958/`.
- `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed.
- APK for CPU test: `android/app/build/outputs/apk/debug/app-debug.apk`.

## Next session starts with
- Install the CPU test APK and run the same controlled signs. Confirm logcat contains `landmarker delegate mode=cpu` and `landmarkers on CPU delegate`.
- Compare against the GPU strict-confirmation run: camera FPS, processed FPS, hand_ms median/p95, pose_ms median/p95, wall_ms, and the remaining confusion cases.

## Open questions
- Is CPU faster or more stable than GPU on this phone?
- If CPU is worse, should analyzer resolution A/B start at 640x480, 480x360, or another CameraX-supported size?

---
# Memory - CPU Delegate A/B Device Result

Last updated: 2026-07-22 09:40 +08:00

## What was built
- No new code/config changes were made in this save step.
- Saved the CPU delegate A/B device result into `context/progress-tracker.md`, `context/recognition-accuracy.md`, and memory.

## Decisions made
- CPU delegate is faster on the tested Xiaomi `M2101K7AG`, but not a clear recognition-quality win.
- Do not assume CPU should become the default across devices.
- Next experiment should restore `mediapipe_delegate.mode=gpu` and test analyzer-resolution reduction.

## Problems solved
- Confirmed that GPU is not always faster for MediaPipe on this low-end Android phone.
- Clarified that the current remaining errors are not solved by more FPS alone: class confusions remain for `CUT/WE`, `IMPORTANT/FAMILY`, `SELL/PUT/TEACH2`, and sometimes `KNOW/HELLO`.

## Current state
- Current working config is still CPU-forced: `recognition_config.json` has `mediapipe_delegate.mode=cpu`.
- Strict low-FPS confirmation remains active: `min_commit_frame=4`, `k_stability=3`, `theta_margin=0.9`.
- Revert points:
  - Strict GPU config before CPU A/B: `android/app/src/main/assets/_backup_before_cpu_delegate_ab_20260722-091958/`
  - Pre-strict candidate config/assets: `android/app/src/main/assets/_backup_before_strict_lowfps_confirm_20260722-084845/`
  - Pre-local-candidate deployed assets: `android/app/src/main/assets/_backup_before_local_pc_236_candidate_20260722-075734/`

## Next session starts with
- Set `mediapipe_delegate.mode` back to `gpu` for the next experiment.
- Add a configurable CameraX analyzer-resolution A/B and build a first lower-resolution GPU test APK.
- Test the same controlled signs and compare against both the strict GPU and strict CPU logs.

## Open questions
- Which analyzer resolution should be tried first on this phone?
- If lower GPU analyzer resolution improves FPS but worsens landmark quality, should CPU remain available as a per-device fallback setting?

---
# Memory - Analyzer Resolution A/B GPU 480x360 Build

Last updated: 2026-07-22 09:35 +08:00

## What was built
- Added config-driven CameraX analyzer resolution to `RecognitionActivity`.
- Current APK requests GPU MediaPipe landmarking with analyzer target 480x360.

## Decisions made
- Keep strict low-FPS confirmation unchanged so this test isolates analyzer resolution.
- Restore `mediapipe_delegate.mode=gpu` for this run because CPU was faster but did not feel better for recognition quality.

## Problems solved
- Analyzer resolution is no longer hardcoded to 640x480.
- Logcat now reports the requested analyzer target with `camera_analysis target=...`.

## Current state
- `recognition_config.json` has `mediapipe_delegate.mode=gpu` and `camera_analysis.target_width=480`, `target_height=360`.
- Rollback backup: `android/app/src/main/assets/_backup_before_analysis_480x360_gpu_20260722-093440/`.
- `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed.
- APK for test: `android/app/build/outputs/apk/debug/app-debug.apk`.

## Next session starts with
- Install/test this APK on the Android phone.
- Confirm logcat contains `landmarker delegate mode=gpu`, `landmarkers on GPU delegate`, and `camera_analysis target=480x360`.
- Test CUT, IMPORTANT, SELL, WANT, KNOW, FAMILY, TEACH, PUT, WE and compare against strict GPU 640x480 and strict CPU 640x480 logs.

## Open questions
- Does CameraX honor 480x360 on this device, or does it choose a nearby supported size?
- Does lower GPU analyzer resolution improve FPS without degrading hand/pose landmark quality and recognition?

---
# Memory - Analyzer Resolution A/B Result GPU 480x360

Last updated: 2026-07-22 09:45 +08:00

## What was built
- No new code/config changes were made in this save step.
- Saved the GPU 480x360 analyzer-resolution device result into progress, accuracy, and memory context.

## Decisions made
- Keep the config-driven analyzer-resolution support.
- GPU 480x360 is not enough to solve the bottleneck by itself.
- Next experiment should keep GPU + 480x360 and test `pose_every_n=3`.

## Problems solved
- Verified CameraX requested the lower analyzer target and logged it.
- Verified conversion/rotation cost dropped significantly, but MediaPipe landmarking still dominates.

## Current state
- Current working config: `mediapipe_delegate.mode=gpu`, `camera_analysis.target_width=480`, `camera_analysis.target_height=360`.
- Strict low-FPS confirmation remains active: `min_commit_frame=4`, `k_stability=3`, `theta_margin=0.9`.
- Pose cadence remains `pose_every_n=2`.
- Rollback backup before the 480x360 config: `android/app/src/main/assets/_backup_before_analysis_480x360_gpu_20260722-093440/`.

## Next session starts with
- Change only `pose_cadence_experiment.pose_every_n` from 2 to 3, keeping `hold_last_pose=true`, GPU delegate, and 480x360 analyzer target.
- Build and test the same controlled signs.

## Open questions
- Does `pose_every_n=3` raise processed FPS without worsening `IMPORTANT/FAMILY`, `SELL/PUT`, or hand-dropout behavior?
- If pose cadence worsens accuracy, should the runtime settle on GPU 480x360 pose_every_n=2 or CPU 640x480 as the better device-specific profile?

---
# Memory - Pose Cadence A/B GPU 480x360 Pose Every 3 Build

Last updated: 2026-07-22 09:45 +08:00

## What was built
- Config-only pose cadence A/B build.
- Changed `pose_cadence_experiment.pose_every_n` from 2 to 3 in `recognition_config.json`.

## Decisions made
- Keep GPU delegate and 480x360 analyzer target for this run.
- Keep strict low-FPS confirmation unchanged so pose cadence is isolated.
- Keep `hold_last_pose=true` to preserve the 258-feature contract while running pose less frequently.

## Problems solved
- Prepared the next reversible test for reducing pose-side MediaPipe cost without dropping pose features.

## Current state
- `mediapipe_delegate.mode=gpu`
- `camera_analysis=480x360`
- `pose_every_n=3`
- `hold_last_pose=true`
- strict low-FPS confirmation remains active: `min_commit_frame=4`, `k_stability=3`, `theta_margin=0.9`
- Rollback backup: `android/app/src/main/assets/_backup_before_pose_every_3_20260722-094412/`
- `./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2` passed.
- APK for test: `android/app/build/outputs/apk/debug/app-debug.apk`.

## Next session starts with
- Install/test this APK on the Android phone.
- Confirm logcat contains `pose_every=3`, `landmarker delegate mode=gpu`, `landmarkers on GPU delegate`, and `camera_analysis target=480x360`.
- Test CUT, IMPORTANT, SELL, WANT, KNOW, FAMILY, TEACH, PUT, WE.

## Open questions
- Does pose every 3 improve processed FPS or reduce wall time enough to matter?
- Does holding pose longer worsen `IMPORTANT/FAMILY`, `SELL/PUT`, hand-dropout, or commit delay?

## 2026-07-22 - Android Low-FPS Runtime A/B: pose_every_n=3 Reverted

- Tested local supplementary 236-class candidate on Xiaomi M2101K7AG with GPU MediaPipe, camera_analysis=480x360, strict low-FPS confirmation, and pose_cadence_experiment pose_every_n=3.
- User observations from logcat run 24302: CUT good; IMPORTANT good but sometimes MORE; SELL still PUT; WANT degraded to MEET; KNOW degraded to SELL/SHOP; FAMILY, TEACH, PUT, WE good.
- Log confirmed processed FPS usually ~6-7 FPS with dips to ~3.9-5.0 FPS. This was only a modest gain over pose_every_n=2, while recognition stability got worse for WANT/KNOW and SELL remained unresolved.
- Decision: pose_every_n=3 is not a keeper for the current model/runtime profile. Reverted recognition_config.json to pose_every_n=2 while preserving GPU delegate, 480x360 analyzer resolution, strict low-FPS confirmation, hold_last_pose=true, and the 258-feature contract.
- Backup before revert: android/app/src/main/assets/_backup_before_revert_pose_every_2_20260722-095204/recognition_config.json
- Build verification after revert: ./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2 passed.
- Current best runtime test profile after revert: local 236-class candidate assets + GPU MediaPipe + camera_analysis=480x360 + pose_every_n=2 + strict low-FPS confirmation. Remaining recurring errors appear to be model/data confusion groups more than runtime confirmation: IMPORTANT/MORE/FAMILY, SELL/PUT/TEACH2/SHOP, WANT/MANY/MEET, KNOW/HELLO/SELL/SHOP.

## 2026-07-22 - Old Model A/B Prepared After Controlled Low-FPS Test

- Controlled test on Xiaomi M2101K7AG with local supplementary 236-class candidate + GPU + camera_analysis=480x360 + pose_every_n=2 showed: CUT good; IMPORTANT often FAMILY/INTRODUCE/delayed; SELL consistently PUT; WANT WAIT/WANT2/MANY; KNOW correct/delayed/HELLO; FAMILY, TEACH, PUT, WE good.
- Log confirmed runtime profile: GPU delegate, camera_analysis=480x360, pose_every=2, processed FPS mostly ~5-6 FPS with dips near ~3.6-4.0, always low_fps=true.
- Key interpretation: remaining failures are not mainly confirmation thresholds. SELL->PUT commits had high margins and true SELL was often absent from top-3; IMPORTANT appeared in FAMILY/MORE/IMPORTANT top-3; WANT and KNOW stayed in known confusion groups. This points to model/data class confusion under low-FPS streaming.
- Prepared a reversible old-model A/B APK: restored streaming.tflite, model_manifest.json, and vocab.json from android/app/src/main/assets/_backup_before_local_pc_236_candidate_20260722-075734 while preserving current runtime recognition_config.json profile.
- Backup before this A/B swap: android/app/src/main/assets/_backup_before_old_model_ab_20260722-100247/
- Build verification: ./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2 passed.
- Next test: install app-debug.apk and run the same controlled 3-attempt set (CUT, IMPORTANT, SELL, WANT, KNOW, FAMILY, TEACH, PUT, WE). Compare old deployed model against local supplementary candidate before deciding whether to keep candidate, revert model, or start targeted retraining for confusion groups.

## 2026-07-22 - Old Model A/B Result: Reject Old Model, Restore Local Candidate

- Old-model A/B log 30136 was tested with the same runtime profile: GPU MediaPipe, camera_analysis=480x360, pose_every_n=2, strict low-FPS confirmation, low_fps=true throughout, processed FPS mostly ~5-6 FPS with dips near ~4 FPS.
- User results for old model: CUT 3/3; IMPORTANT 2/3; SELL mostly delayed/DECIDE1; WANT 2/3; KNOW 0/3; FAMILY 2/3; TEACH 3/3; PUT 0/3; WE 0/3.
- Commit sequence confirmed the regression: PUT attempts committed INTRODUCE/IMPORTANT, WE attempts committed SELL/LIVE2/STRONG, KNOW committed SELL/DONTKNOW or delayed. Old model improved IMPORTANT compared with the local candidate but damaged previously stable classes.
- Decision: reject old model as current baseline. Restore the local supplementary 236-class candidate because it is better overall for controlled signs, especially PUT, WE, FAMILY, TEACH, CUT.
- Restored local candidate model/vocab/manifest from android/app/src/main/assets/_backup_before_old_model_ab_20260722-100247/ while preserving runtime config.
- Backup of rejected old-model A/B state before restore: android/app/src/main/assets/_backup_before_restore_local_candidate_20260722-101227/
- Build verification after restore: ./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2 passed.
- Next direction: stop broad runtime/model A/B for now. Remaining problem is targeted model/data confusion under low-FPS streaming: IMPORTANT/FAMILY/MORE/INTRODUCE, SELL/PUT/DECIDE1/SHOP/TEACH2, WANT/MANY/WAIT/MEET, KNOW/HELLO/SELL/DONTKNOW, plus possible WE/LIVE2/STRONG in old model only. Recommended next step is targeted confusion audit/retraining plan using ASL Citizen plus supplementary local data, not threshold tuning.

## 2026-07-22 - Targeted Confusion Audit Completed

- Ran targeted confusion audit for current restored local supplementary 236-class candidate: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_rtx3050_v30\best.keras
- Report artifacts written:
  - artifacts/targeted_confusion_audit_20260722/targeted_confusion_audit.md
  - artifacts/targeted_confusion_audit_20260722/targeted_confusion_audit.json
- Headline held-out test metrics: mean aggregation top1=0.617/top3=0.817/top5=0.868; last-frame top1=0.571/top3=0.790/top5=0.853; early4 top1=0.081; early6 top1=0.137.
- Interpretation: the phone's low-FPS early commits are consistent with offline weakness. The model is not reliable at very early frames; min_commit_frame=4 can be correct for easy signs but is too early for many signs if the wrong class has high confidence.
- Most problematic held-out last-frame classes in observed groups: KNOW top1=0.15, HELLO top1=0.30, SELL top1=0.27, WANT2 top1=0.36, PUT top1=0.45. Stable/current-good classes: WE top1=1.00, TEACH2 top1=0.91, MORE top1=1.00, FAMILY top1=0.75, IMPORTANT top1=0.67.
- Dataset count issue: many target classes have very small base train counts (e.g. SELL 23, KNOW 21, IMPORTANT 14, MANY 13, WAIT 12, WE 15, STRONG 15). FPS augmentation multiplies existing clips but does not add signer/style diversity.
- Next recommended model/data step: no more broad runtime threshold tuning. Prepare targeted retraining/eval experiment focused on weak confusion groups, with stronger per-class/early-frame eval gates before any Android deployment.

## 2026-07-22 - Targeted 236-Class Retrain v1 Verified

- User ran 08_TRAIN_TARGETED_236_CPU.ps1 successfully. Output run: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v1
- Training completed through epoch 24/40 with early stopping. Best val_pf_acc in log was ~0.4741 at epoch 16; final artifacts best.keras, final.keras, history.csv exist.
- Targeted audit written: artifacts/targeted_confusion_audit_20260722/targeted_v1/targeted_confusion_audit.md and .json
- Overall held-out test deltas vs baseline: mean top1 0.617 -> 0.613 (-0.005), last top1 0.571 -> 0.587 (+0.017), early4 top1 0.081 -> 0.077 (-0.004), early6 top1 0.137 -> 0.140 (+0.002).
- FPS-val stress deltas improved across views: mean top1 0.640 -> 0.663, last top1 0.588 -> 0.603, early4 top1 0.326 -> 0.339, early6 top1 0.430 -> 0.441.
- Major held-out last-frame improvements: KNOW 0.15 -> 0.54, HELLO 0.30 -> 0.50, SELL 0.27 -> 0.45, WANT2 0.36 -> 0.73, PUT 0.45 -> 0.55, TEACH2 0.91 -> 1.00.
- Regressions: WE 1.00 -> 0.83, WAIT 0.64 -> 0.36, MANY 0.73 -> 0.55, FAMILY 0.75 -> 0.67, SHOP1 0.60 -> 0.50, MEET top3 1.00 -> 0.89.
- Decision: targeted_v1 is promising but not deployable yet. It fixes several weak classes while moving errors into previously stable classes. Next step should be targeted_v2 with safer weights / guardrails before Android A/B.

## 2026-07-22 - Targeted 236-Class Retrain v2 Prepared

- Prepared v2 targeted retraining config and runner, but did not run full training in Codex because user will execute commands manually.
- New config: model/config/train_streaming_conversational_plus_local_pc_236_targeted_v2.yaml
- New runner: 09_TRAIN_TARGETED_236_V2_CPU.ps1
- v2 rationale: targeted_v1 improved KNOW/HELLO/SELL/WANT2/PUT but regressed WE/WAIT/MANY/FAMILY/SHOP1. v2 starts again from the current local-candidate baseline and uses softer weak-class weights plus guardrail weights.
- v2 weights: KNOW 2.5, HELLO 2.0, SELL 2.0, WANT2 1.6, PUT 1.6, WAIT 1.6, MANY 1.5, SHOP1 1.5, FAMILY 1.3, WE 1.3, IMPORTANT 1.3. TEACH2 and other stable classes remain 1.0.
- v2 output dir: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v2
- v2 audit dir after run: artifacts/targeted_confusion_audit_20260722/targeted_v2/
- Validation performed: config loads in project .venv and class weights resolve against the 236-class vocab.
- Deployment gate: do not export/deploy v2 unless it improves weak classes while avoiding v1 regressions, especially WE, WAIT, MANY, FAMILY, SHOP1.

## 2026-07-22 - Targeted 236-Class Retrain v2 Verified

- User ran 09_TRAIN_TARGETED_236_V2_CPU.ps1 successfully. Output run: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v2
- Training completed through epoch 25/40 with early stopping. Best val_pf_acc in log was ~0.4762 at epoch 17. Artifacts best.keras, final.keras, history.csv exist.
- Targeted audit written: artifacts/targeted_confusion_audit_20260722/targeted_v2/targeted_confusion_audit.md and .json
- Overall held-out test top1 baseline -> v1 -> v2: mean 0.617 -> 0.613 -> 0.623; last 0.571 -> 0.587 -> 0.583; early4 0.081 -> 0.077 -> 0.081; early6 0.137 -> 0.140 -> 0.139.
- FPS-val stress top1 baseline -> v1 -> v2: mean 0.640 -> 0.663 -> 0.659; last 0.588 -> 0.603 -> 0.598; early4 0.326 -> 0.339 -> 0.338; early6 0.430 -> 0.441 -> 0.435.
- Held-out last-frame class deltas baseline -> v1 -> v2: KNOW 0.15 -> 0.54 -> 0.54; SELL 0.27 -> 0.45 -> 0.45; PUT 0.45 -> 0.55 -> 0.55; WANT2 0.36 -> 0.73 -> 0.55; HELLO 0.30 -> 0.50 -> 0.30; WE 1.00 -> 0.83 -> 0.92; FAMILY 0.75 -> 0.67 -> 0.75; MANY 0.73 -> 0.55 -> 0.64; WAIT 0.64 -> 0.36 -> 0.36.
- Decision: v2 is safer than v1 for WE/FAMILY and has the best mean top1, but it is still not a clean deploy candidate. It preserves important improvements on KNOW/SELL/PUT while still regressing WAIT and some WANT2/HELLO gains compared with v1. Next step should be either v3 with more focused weights/guardrails or a temporary Android A/B only if we explicitly accept risk and keep rollback ready.

## 2026-07-22 - Targeted 236-Class Retrain v3 Prepared

- Prepared v3 targeted retraining config and runner for manual execution by the user.
- New config: model/config/train_streaming_conversational_plus_local_pc_236_targeted_v3.yaml
- New runner: 10_TRAIN_TARGETED_236_V3_CPU.ps1
- v3 rationale: v2 preserved KNOW/SELL/PUT gains better than baseline and recovered WE/FAMILY versus v1, but WAIT remained badly regressed and HELLO/WANT2 lost some v1 gains. v3 removes weights from WAIT/MANY/SHOP1 because weighting those classes in v1/v2 coincided with regressions, while keeping targeted pressure on KNOW/HELLO/SELL/WANT2/PUT plus light guardrails for FAMILY/WE.
- v3 weights: KNOW 2.5, HELLO 2.4, SELL 2.3, WANT2 1.9, PUT 1.6, FAMILY 1.3, WE 1.3. WAIT/MANY/SHOP1/TEACH2 remain 1.0.
- v3 output dir: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v3
- v3 audit dir after run: artifacts/targeted_confusion_audit_20260722/targeted_v3/
- Validation performed: config loads in project .venv and class weights resolve against the 236-class vocab.
- Deployment gate: compare v3 against baseline, v1, and v2. Do not export/deploy unless weak-class gains hold and WAIT/MANY/SHOP1/WE/FAMILY regressions are acceptable or improved.

## 2026-07-22 - Targeted 236-Class Retrain v3 Verified

- User ran 10_TRAIN_TARGETED_236_V3_CPU.ps1 successfully. Output run: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v3
- Training completed through epoch 20/40 with early stopping. Best val_pf_acc in log was ~0.4735 at epoch 12. Artifacts best.keras, final.keras, history.csv exist.
- Targeted audit written: artifacts/targeted_confusion_audit_20260722/targeted_v3/targeted_confusion_audit.md and .json
- Overall held-out top1 baseline -> v1 -> v2 -> v3: mean 0.617 -> 0.613 -> 0.623 -> 0.627; last 0.571 -> 0.587 -> 0.583 -> 0.587; early4 0.081 -> 0.077 -> 0.081 -> 0.083; early6 0.137 -> 0.140 -> 0.139 -> 0.139.
- FPS-val top1 baseline -> v1 -> v2 -> v3: mean 0.640 -> 0.663 -> 0.659 -> 0.658; last 0.588 -> 0.603 -> 0.598 -> 0.608; early4 0.326 -> 0.339 -> 0.338 -> 0.331; early6 0.430 -> 0.441 -> 0.435 -> 0.438.
- Major held-out last-frame changes baseline -> v3: KNOW 0.15 -> 0.54, SELL 0.27 -> 0.55, WANT2 0.36 -> 0.73, PUT 0.45 -> 0.55, HELLO 0.30 -> 0.40, FAMILY 0.75 -> 0.83, DECIDE1 0.79 -> 0.86, WE 1.00 -> 0.92.
- Serious regressions baseline -> v3: SHOP1 0.60 -> 0.20, INTRODUCE 0.67 -> 0.50, WAIT 0.64 -> 0.36, MANY 0.73 -> 0.64, LIVE2 0.75 -> 0.67.
- Decision: v3 is the best overall offline candidate so far and strongest for the observed Android pain points, but not clean enough to deploy as final. The biggest blocker is SHOP1 collapsing into SELL; next step should be v4 with a small SHOP1 guardrail and slightly lower SELL weight, or Android A/B only if SHOP1 is outside current controlled target words and rollback is kept ready.

## 2026-07-22 - Targeted 236-Class Retrain v4 Prepared

- Prepared v4 targeted retraining config and runner for manual execution by the user.
- New config: model/config/train_streaming_conversational_plus_local_pc_236_targeted_v4.yaml
- New runner: 11_TRAIN_TARGETED_236_V4_CPU.ps1
- v4 rationale: v3 is the strongest overall candidate so far but SHOP1 collapsed into SELL (SHOP1 last top1 0.60 baseline -> 0.20 v3). v4 is a minimal correction from v3: reduce SELL weight and add a small SHOP1 guardrail.
- v4 weights: KNOW 2.5, HELLO 2.4, SELL 2.0, WANT2 1.9, PUT 1.6, SHOP1 1.3, FAMILY 1.3, WE 1.3. WAIT/MANY/TEACH2 remain 1.0.
- v4 output dir: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v4
- v4 audit dir after run: artifacts/targeted_confusion_audit_20260722/targeted_v4/
- Validation performed: config loads in project .venv and class weights resolve against the 236-class vocab.
- Deployment gate: compare v4 against baseline and v1-v3. Key pass/fail checks: keep v3 gains on SELL/KNOW/WANT2/PUT, recover SHOP1 meaningfully, avoid further regressions on WE/FAMILY/WAIT/MANY/INTRODUCE.

## 2026-07-22 - Targeted 236-Class Retrain v4 Verified

- User ran 11_TRAIN_TARGETED_236_V4_CPU.ps1 successfully. Output run: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v4
- Training completed through epoch 12/40 with early stopping. Best val_pf_acc in log was ~0.4758 at epoch 4. Artifacts best.keras, final.keras, history.csv exist.
- Targeted audit written: artifacts/targeted_confusion_audit_20260722/targeted_v4/targeted_confusion_audit.md and .json
- Overall held-out top1 baseline -> v1 -> v2 -> v3 -> v4: mean 0.617 -> 0.613 -> 0.623 -> 0.627 -> 0.621; last 0.571 -> 0.587 -> 0.583 -> 0.587 -> 0.584; early4 0.081 -> 0.077 -> 0.081 -> 0.083 -> 0.080; early6 0.137 -> 0.140 -> 0.139 -> 0.139 -> 0.137.
- FPS-val top1 baseline -> v1 -> v2 -> v3 -> v4: mean 0.640 -> 0.663 -> 0.659 -> 0.658 -> 0.656; last 0.588 -> 0.603 -> 0.598 -> 0.608 -> 0.602; early4 0.326 -> 0.339 -> 0.338 -> 0.331 -> 0.336; early6 0.430 -> 0.441 -> 0.435 -> 0.438 -> 0.438.
- Held-out last-frame key classes baseline -> v4: KNOW 0.15 -> 0.62, SELL 0.27 -> 0.55, PUT 0.45 -> 0.55, HELLO 0.30 -> 0.40, WE 1.00 -> 1.00, FAMILY 0.75 -> 0.83, INTRODUCE 0.67 -> 0.58, SHOP1 0.60 -> 0.40, WANT2 0.36 -> 0.55, MANY 0.73 -> 0.55, WAIT 0.64 -> 0.27.
- Decision: v4 is not a strict winner over v3. It improves KNOW/WE/INTRODUCE and partially recovers SHOP1, but hurts WAIT/MANY/WANT2 and has lower overall mean/last top1 than v3. Continuing weight tweaks risks overfitting the tiny target counts. Recommended stop point: do not deploy v4 as final. If doing Android A/B, v3 or v4 can be tested behind rollback, but a full 236-class regression audit should be added before any final model replacement.

## 2026-07-22 - Full 236-Class Regression Audit Prepared

- Added a full 236-class regression audit before any model deployment.
- New module: eval/full_regression.py
- New runner: 12_FULL_236_REGRESSION_AUDIT.ps1
- Purpose: compare baseline and v1-v4 across every class, not only targeted confusion groups. Reports overall metrics by view (mean/last/early4/early6), focus-word table, and worst per-class regressions/improvements against the baseline.
- Output after run: artifacts/targeted_confusion_audit_20260722/full_236_regression/full_regression_audit.md and .json
- Validation performed: `python -m eval.full_regression --help` succeeds with project .venv.
- Deployment gate: do not export/deploy v3/v4 until full_236_regression audit is reviewed, especially worst regressions across all 236 classes.
---
# Memory - Android UI Reference Correction Splash/Loading Pass

Last updated: 2026-07-22 10:30 +08:00

## What was built
- Added native Kotlin `SplashActivity` and `LoadingActivity`.
- Added AppHear2-style `activity_splash.xml` and `activity_loading.xml` adapted to AppHear3.
- Imported selected splash/loading visual assets.
- Made `SplashActivity` the launcher and kept `MainActivity` as the homepage/shell destination.

## Decisions made
- Loading is visual only; it does not preload recognition or signal model readiness.
- No AppHear2 detection, backend, model, MediaPipe, auth, or recognition logic was copied.

## Problems solved
- The remaining splash/loading screenshot-reference pages are now implemented.
- Android source/resource mojibake scan is clean after cleaning one remaining source comment.

## Current state
- `testDebugUnitTest assembleDebug` passed.
- Manual launch visual QA remains pending.

## Next session starts with
- Device/emulator smoke: clear onboarding preference if needed, launch app, verify Splash -> Loading -> MainActivity shell, then open RecognitionActivity for candidate-model smoke.

## Open questions
- Confirm imported splash/loading raster asset provenance and APK-size impact before release.---
# Memory - Android UI Shell Navigation Cleanup

Last updated: 2026-07-22 10:45 +08:00

## What was built
- Removed temporary `AppShellActivity` from the main manifest.
- Updated `MainActivity` bottom-tab navigation to avoid duplicate fragment stacking.

## Decisions made
- Do not delete `AppShellActivity.kt` until a safer source-control/backup cleanup pass.
- Recognition remains a dedicated `RecognitionActivity`; no AppHear2 detection/runtime logic was introduced.

## Problems solved
- Temporary shell is no longer registered as an app activity.
- Repeated bottom-nav taps no longer stack duplicate shell destinations.

## Current state
- `testDebugUnitTest assembleDebug` passed.
- Device visual/navigation QA remains pending.

## Next session starts with
- Device/emulator smoke for Splash -> Loading -> MainActivity, bottom tabs, and RecognitionActivity launch.

## Open questions
- Whether to delete the now-unregistered `AppShellActivity.kt` during a later cleanup pass once backup/source-control is clear.
---
# Memory - Sign Recognition Architecture Research

Last updated: 2026-07-24 23:59 +08:00

## What was built

- Research/documentation only; no implementation.
- Saved the architecture decision in `context/recognition-accuracy.md`, its relationship to ST-GCN in `context/encoder-upgrade.md`, and project status in `context/progress-tracker.md`.

## Decisions made

- Partially replace the current `IMAGE -> 258 -> [1,96,258] TCN` foundation.
- Primary target: hybrid landmarks/motion + RGB hand appearance + sparse non-manual cues, region-aware graph encoding, causal temporal fusion, learned boundary head, and calibrated reject/unknown policy.
- MediaPipe remains initially as tracker/ROI generator, not the sole information source.
- Isolated signs first; continuous CTC gloss recognition only after natural sentence data; full translation is a separate later phase.
- Frozen-contract ST-GCN remains Experiment 1 and a controlled baseline.

## Problems solved

- Separated demonstrable TCN underfitting from representation and dataset limitations.
- Reconciled the existing encoder plan with the selected hybrid long-term direction.
- Defined measurable dataset, accuracy, low-FPS, calibration, false-positive, latency, and thermal gates.

## Current state

- Research decision saved; no code/model/data changes pending from this session.
- Production remains the restored local 236-class candidate with GPU MediaPipe, 480x360 analysis, pose every 2 frames, and strict low-FPS confirmation.
- Current data remains too sparse for a reliable 236-sign consumer system.

## Next session starts with

- Review the saved architecture and choose between auditing/executing the existing ST-GCN experiment or writing the detailed hybrid experiment specification.
- Before ST-GCN training, correct the placeholder graph adjacency in `model/model_gcn.py` against the chosen reference.

## Open questions

- IMAGE versus VIDEO/LIVE_STREAM speed and landmark drift on the reference Android.
- Accuracy/cost of RGB hand, upper-body RGB, and sparse facial streams.
- Crop resolution, sustainable FPS, model size, and quantization-compatible fusion operators.
- Ability to collect 30+ pilot signers and eventually 50-100 signers with reviewed labels.
- Availability of correctly annotated natural continuous ASL.
