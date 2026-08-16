# RU-D1 Minimal Runtime Failure Attribution

**Status:** implementation and first 20-attempt device batch complete; consolidated reports generated.

RU-D1 is a default-off, debug-only diagnostic path. It does not retrain a model, alter schema 3.0,
change S4 feature math, tune S5/S7, or feed diagnostic values back into recognition.

## Why each change exists

- `RecognitionActivity`: a hidden long-press on **CLEAR** starts/stops a labeled attempt. This
  avoids a new screen or production UI. Required metadata arrives through debug intent extras.
- `RuD1Diagnostics`: writes one bounded attempt bundle. A 48-frame rolling ring freezes eight
  processed frames after S5 release; if release is missed, it retains the latest 48 frames until
  manual stop. This keeps pre-sign, sign, and post-sign evidence without requiring a rushed start.
  JSON serialization, image scaling, compression, hashing, and file I/O run off the main thread.
- `FrameAnalyzer`: joins MediaPipe presence/pose freshness with the post-recognition trace using the
  same processed frame. This is required to distinguish visible-hand detection loss from later
  stages.
- `RecognitionPipeline` / `SigningDetector`: expose immutable S4-S7 observations and the exact
  source-frame ID occupying each model-window row. These values are output-only.
- `eval/runtime_diagnostics/ru_d1.py`: reconstructs `[96,258]` windows with exact order and zero
  padding, checks their little-endian SHA-256, replays the checked-in TFLite model, verifies argmax
  and S7 commit parity, then compares actual S5 selection with a manually annotated oracle span.
- `ru_d1_pilot.csv`: initial weak/confused signs plus strong controls. It is a capture queue, not a
  fixed signer/sample-count requirement.

## Build and capture

RU-D1 stays disabled in ordinary debug and every release build. Build the explicit diagnostic APK:

```powershell
cd android
.\gradlew.bat assembleDebug -PruD1=true
```

Install it, then launch one labeled attempt (example):

```powershell
adb shell am start -n com.example.apphear/.SplashActivity `
  --es ru_d1_gloss HAVE `
  --es ru_d1_expected_hands two `
  --es ru_d1_signer_id fresh_01 `
  --es ru_d1_variant apphear_target
```

Long-press **CLEAR** immediately before the attempt and again after returning to rest. Pull bundles
from the app-specific external-files `ru_d1/` directory. Review the bounded indexed JPEGs and copy
`ru_d1_annotations_template.csv`; enter the exact processed onset/release frame IDs, whether the
performance/variant was valid, and `true`, `false`, or `unknown` for whether a required hand was
visibly present when MediaPipe missed it.

## Analyze

```powershell
python -m eval.runtime_diagnostics.ru_d1 <pulled-ru_d1-root> <annotations.csv> `
  --output <result-directory>
```

Use `.venv-ru-d1-tf216\Scripts\python.exe` for real device replay so the offline TensorFlow Lite
version matches Android `2.16.1`.

The analyzer writes only:

- `attempt_diagnostics.csv`
- `class_health.csv`

No attempt is trusted when window hash, TFLite argmax, or replayed S7 commit parity fails. When
detection, S4, and S5 are adequate but oracle classification fails, the output is deliberately the
generic `S6_RECOGNITION_FAILURE`; data, confusion, generalization, and representation attribution
belongs to the later repair phase.

Run replay with the workspace-local `.venv-ru-d1-tf216` environment, which matches Android's
TensorFlow Lite `2.16.1`. ARM and x86 quantized kernels can still produce different confidence
values, so RU-D1 reports the maximum probability delta but does not use cross-architecture float
identity as a trust gate. Model/config hashes and reconstructed window bytes must match exactly;
TFLite argmaxes and the replayed S7 commit must also match exactly. S7 replay uses the recorded
Android posterior because that is the exact value consumed on device; using the independently
recomputed x86 posterior here would conflate permitted quantization deltas with policy skew.

## Validation completed

- `python -m pytest tests/test_ru_d1.py`: passed, including the checked-in TFLite contract smoke.
- `python -m ruff check eval/runtime_diagnostics tests/test_ru_d1.py`: passed.
- `android/.\gradlew.bat testDebugUnitTest`: passed.
- `android/.\gradlew.bat assembleDebug`: passed with RU-D1 off.
- Android lint reached two pre-existing `windowLightNavigationBar` min-SDK errors in the theme
  resources; no RU-D1 lint error was reported.

Real behavior/replay parity and the first class-health rows remain device-data gates. They cannot be
claimed from synthetic traces.

## Prepared batch pilot 01

The first consolidated pilot is frozen in `ru_d1_batch_pilot_01.csv`: 10 signs, two natural
attempts each, interleaved to reduce order/carryover bias. `GOOD` uses the observed AppHear target
two-hand citation form; `TABLE` is also labeled two-hand. Every attempt records `session_id`,
`repetition_id`, and `capture_order` in `metadata.json`.

With the RU-D1 APK installed and exactly one authorized device connected, run from the workspace:

```powershell
.\eval\runtime_diagnostics\run_ru_d1_batch.ps1 `
  -SignerId signer_01 `
  -SessionId ru_d1_pilot_01
```

The launcher advances automatically only after `capture_complete.json` appears and verifies that
the saved bundle contains trace rows and visual evidence. It launches the next label into a
persistent **READY: GLOSS • repetition** screen; launching/advancing never begins capture. For each
screen:

1. Confirm the expected gloss/repetition and **READY** state; wait for camera, landmarks, and model
   warm-up.
2. Begin at rest and long-press **CLEAR**.
3. Perform the labeled sign once at a natural speed; do not exaggerate or hold it to help
   recognition.
4. Return to rest, wait about one second, and long-press **CLEAR** to save.
5. Let the script launch the next attempt. There is no default attempt deadline, so resting at the
   READY screen does not interrupt the session. A disconnected device or invalid saved bundle stops
   the launcher; after resolving it, resume with `-StartAt <order>`. Existing bundles remain intact.

The rolling ring means there is no need to sign within the first 48 frames. With a detected S5
release it retains up to 40 evidence frames through release plus eight post-release frames; its unit
gate exercises `rest → preparation → onset → full sign → release → return to rest`. If S5 misses
release, it keeps the latest 48 frames at manual stop. Keep each attempt focused, and stop within a
few seconds after returning to rest so the bounded evidence still contains the complete sequence.
