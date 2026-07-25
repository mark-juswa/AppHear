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
