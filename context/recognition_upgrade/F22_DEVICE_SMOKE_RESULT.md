# F22 Physical-Device Smoke Result

**Purpose:** Record physical-device validation of the protected 236-class Android recognizer after
C0-B0 was closed.

**Scope:** Baseline verification only. This run did not integrate C0-B0, replace MediaPipe, change
schema v3.0, modify model assets, or authorize a production claim.

**Status:** Partial pass. Startup, camera lifecycle, inference wiring, bounded no-hands behavior,
commit/release behavior, sentence clear, and camera switching passed. Full F22 sign-off is blocked
by configuration drift, missing cross-signer coverage, unverified handedness mirroring, and
untested rollback paths.

**Last updated:** 2026-08-11.

## Verified Environment

- Device: Xiaomi M2101K7AG (`sunny_global`).
- Android: 12, SDK 31.
- APK: `android/app/build/outputs/apk/debug/app-debug.apk`.
- Validation build: `testDebugUnitTest assembleDebug` passed.
- Installation: previous `com.example.apphear` uninstalled; debug APK installed successfully.
- Current recognizer: schema v3.0 `[96,258]`, window `96`, vocabulary `236`.
- Runtime delegate: MediaPipe landmarkers loaded on GPU; TFLite used the protected recognizer.
- Observed processed cadence: approximately `6.2-8.2 fps`, with low-FPS mode active.

## Preflight Result

- `RECOGNITION_ENABLED=true`: pass.
- `post_commit_rearm.enabled=false`: confirmed; the disabled block is behavior-preserving but
  remains recorded configuration-hash drift from E6-0.
- `PROFILE_STAGES=true`: deviation from the F22 requirement of `false`. Performance observations
  from this run are diagnostic and are not a clean benchmark.

## Check Results

| Check | Result | Evidence and limitation |
|---|---|---|
| Build and clean installation | Pass | Unit tests and debug assembly passed; clean reinstall succeeded. |
| Startup/model wiring | Pass | Camera preview opened; GPU landmarkers loaded; recognizer reported `window=96 classes=236`; no fatal exception. |
| Controlled no-hands window | Pass, bounded | No onset, commit, or fatal log during an approximately 20-second empty-wall interval. This is not a full OOV/no-sign evaluation. |
| Controlled isolated signing | Mixed | `GOOD` committed correctly. An intended `HELLO` committed as `GOOD`; this is a protected-baseline accuracy failure. |
| One commit per bout | Pass | Each accepted bout produced one commit followed by release/rearm. |
| Sentence clear | Pass | Manual Clear returned the sentence display to the empty placeholder. |
| Handedness control | Partial | UI changed to `Left hand` and left-hand signing produced commits. Correct mirroring/normalization was not independently proven; edge tracking was intermittent. |
| Edge tracking | Unstable | Logs repeatedly showed hand loss/reacquisition and hand-dropout releases near the frame boundary. |
| Front/back camera switch | Pass | CameraX closed camera 1 and opened camera 0, then later closed camera 0 and reopened camera 1 without a fatal error. |
| Back-camera recognition | Inconclusive | Mirror-assisted, one-handed phone setup produced multiple short bouts. These are not scored because capture conditions were uncontrolled. |
| Background/resume | Pass | HOME closed the camera; warm resume reloaded GPU landmarkers, the 236-class recognizer, analysis, and camera without a fatal error. |
| Cross-signer check | Not run | Only one available signer participated; F22 requires at least two. |
| Recognition kill-switch | Not run | Requires a separate rebuild with recognition disabled. The current working configuration was not modified. |
| Load-failure fallback | Not run | Requires a deliberately invalid or missing model contract in a separate build. Protected assets were not modified. |

## Interpretation

This smoke verifies that the protected Android pipeline remains wired and operational. It does not
show that the 236-class recognizer is accurate or production-ready. The controlled `HELLO -> GOOD`
error, intermittent edge-hand tracking, and low device cadence are consistent with the documented
baseline limitations.

The C0-B0 I320 detector was not integrated into this APK. This run therefore does not validate or
invalidate I320 on Android; C0-B0 remains a development NO-GO under
`C0B_STAGE2_DEVELOPMENT_RESULT.md`.

## Decision

- Do not claim a full F22 pass.
- Do not promote, replace, or modify the protected recognizer from this smoke.
- No more constrained one-person signing trials are required for this checkpoint.
- Complete F22 only when a second signer and isolated rollback test builds are available.
- The next accuracy evidence remains a separately approved, held-out end-to-end baseline
  evaluation using fresh signer-separated positive phrases and no-sign/OOV sessions.

## Source Of Truth

- `../device-smoke.md`
- `POST_C0_PRODUCT_SCOPE_DECISION.md`
- `C0B_STAGE2_DEVELOPMENT_RESULT.md`
- `E6_0_BASELINE_FREEZE.md`
- `../progress-tracker.md`

