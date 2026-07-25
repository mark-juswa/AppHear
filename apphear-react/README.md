# AppHear React Prototype

Separate React Native/iPhone prototype for AppHear 3. This project is governed by
`../context/react-native-prototype.md`.

## Scope

Current milestone: **RN02 iOS hand-only scaffold prep**. Android RN01 passed; iPhone RN01 is intentionally skipped for now by developer direction.

This prototype must not replace or modify the production Android app under `../android/`. React
Native owns the UI shell and benchmark display. Real-time vision work in later phases stays native.

## RN01 Goals

- Open a camera preview on a physical iPhone and Android device.
- Count lightweight frame-output callbacks without reading pixels.
- Measure capture/frame callback FPS and dropped frames.
- Export a benchmark session as JSON.
- Do not add MediaPipe, TFLite, recognition, or feature extraction yet.

## Setup

Dependencies are installed for this scaffold:

```powershell
npm install
```

Native `android/` and `ios/` project shells are generated. iOS testing still requires macOS + Xcode + CocoaPods + a physical iPhone.

```powershell
npm run start
npm run android
npm run ios
```


## Build Status

Validated on 2026-07-18:

```powershell
npm run typecheck
npm run lint
npx react-native bundle --platform android --dev true --entry-file index.js --bundle-output .tmp\index.android.bundle --assets-dest .tmp\assets --reset-cache
cd android
.\gradlew.bat assembleDebug -PreactNativeArchitectures=arm64-v8a --console=plain --no-daemon --max-workers=2
```

The Android debug APK is generated at `android/app/build/outputs/apk/debug/app-debug.apk`.
The local shell does not have `adb` on PATH, so device install/run was not performed here.

## Architecture Notes

- VisionCamera v5 is used for RN01 because its Frame Output gives a measurable frame callback.
- The frame callback disposes frames immediately and schedules only tiny metadata updates to RN.
- Later phases must replace JS frame counting with native modules for MediaPipe/TFLite work.
- Benchmark logs live under `benchmark/device-results/` when exported from device.


## RN01 Android Result

Physical Android smoke passed on Xiaomi `M2101K7AG` / `sunny_global`:

| Run | Avg callback FPS | Dropped frames | Actual frame |
|---|---:|---:|---|
| 1 min | 30.02 | 0 | 800x480 |
| 3 min | 30.00 | 0 | 800x480 |
| 5 min | 30.01 | 0 | 800x480 |

Results are stored under `benchmark/device-results/android-m2101k7ag-rn01-2026-07-19/`.
This is camera callback FPS only, not MediaPipe or recognition FPS.

## RN02 Scaffold

RN02 source wiring is present but not validated on iOS:

- `benchmark/protocols/rn02-ios-hand-only.md`
- `src/types/rn02HandBenchmark.ts`
- `src/screens/Rn02HandSmokeScreen.tsx` and the RN01/RN02 switch in `App.tsx`\r\n- `src/native/AppHearVisionModule.ts` typed native-module wrapper\r\n- `ios/AppHearReactPrototype/RN02HandBenchmarkModule.m`\r\n- `ios/AppHearReactPrototype/RN02HandBenchmarkModule.swift`\r\n- `ios/AppHearReactPrototype/RN02HandLandmarkerBenchmark.swift`\r\n- `ios/AppHearReactPrototype/hand_landmarker.task` copied into the app target resources\r\n- `assets/mediapipe/hand_landmarker.task` canonical prototype copy\r\n- `ios/Podfile` includes `MediaPipeTasksVision`

RN02 is not complete until it runs on a physical iPhone and exports hand-only latency logs. It still
must not include pose, features, TFLite, or recognition.
## Phase Gate

RN01 is complete only when benchmark logs exist for:

- one physical iPhone;
- one Android device;
- 1-minute, 3-minute, and 5-minute sustained runs;
- same requested FPS/resolution settings.


## RN02 Android Model-Load Slice

Because iPhone hardware is not currently available, RN02 now has an Android-only model-load slice for the separate React Native prototype.

Added:

- Android native module `RN02HandBenchmarkModule`.
- Android React package registration `AppHearVisionPackage`.
- `hand_landmarker.task` in `android/app/src/main/assets/`.
- MediaPipe Tasks Vision dependency in the RN prototype Android Gradle app module.
- RN02 screen support on Android.

Validated:

```powershell
npm run typecheck
npm run lint
cd android
.\gradlew.bat assembleDebug -PreactNativeArchitectures=arm64-v8a --console=plain --no-daemon --max-workers=2
```

This slice only verifies native module and model-load plumbing. It does not measure MediaPipe FPS yet.
## RN02 Android Hand-Only CameraX Slice

RN02 now has native Android hand-only frame processing for benchmark use only.

The native module starts CameraX `ImageAnalysis`, converts `ImageProxy` frames to MediaPipe `MPImage`, runs `HandLandmarker.detect()` on a background executor, and accumulates compact benchmark samples. React Native polls those samples once per second. It does not receive raw frames or per-frame landmarks.

Validate on device after reinstalling the APK:

- tap `RN02`
- tap `Start`
- wait for samples to increment
- run 1-minute, 3-minute, and 5-minute sustained tests
- tap `Export` after each run

This is still hand-only. It is not pose, features, TFLite, or recognition.