# Recognition mode header — 2026-10-09

Requested presentation-only correction: move the existing camera mode indicator to the top and
show only Fingerspell or Word. The existing coordinator is retained; no chooser is reintroduced.

Active app: C:/Users/Gigabyte/.codex/worktrees/fingerspell-continuous-oct05/5. Apphear3.
Base October5 b48594c4942d9e9ac0d94ff96396e80b9f049c0a.

## Implementation

RecognitionCoordinationBridge uses the existing bg_glass_pill drawable and Inter semibold font,
a centered single-line label, and constraints between btnBack and cameraToggle, vertically centered
within the Back button's row. It is no longer anchored above RECOGNIZED. Rendering reads the
existing active recognition owner and emits only the localized Fingerspell/Word string. Context
reason, finish instructions and last-spelling text are removed from the indicator as requested.
Recognition state/confirmation/history itself is preserved.

Four application files changed:
- android/app/src/main/java/com/example/apphear/coordination/RecognitionCoordinationBridge.kt
- android/app/src/main/res/values/recognition_coordination.xml (two label strings only)
- android/app/src/androidTest/java/com/example/apphear/coordination/RecognitionCoordinationInstrumentedTest.kt
- android/app/src/androidTest/java/com/example/apphear/coordination/RecognitionContextUiFlowInstrumentedTest.kt

No Activity/XML camera layout change, no feature/model/decoder/threshold/camera change.
Bridge methods from started through confirmation are byte-identical; only label construction,
position and rendering differ. Existing Context/WORD processing unchanged.

## Validation and rollout

181 host tests passed with zero failures. Final private Xiaomi test group 3/3 passed, 10.303 seconds.
Checks include exact Fingerspell label at automatic entry, exact Word label after confirmation,
header bounds between top navigation controls, absence of chooser, stored WORD sentence preserved,
continuous ownership/no F inference in WORD, missing-hand refusal, Settings and 104-character
spelling rendering. Existing typed-flow test expectations updated; that fake-only test was not
rerun under this private configuration. Automatic routing policy was not edited.

670 existing source/config files frozen; 666 unchanged, precisely the four scoped files changed.
No additional source files or dependencies. Candidate01/Adapter/model assets/WORD and Context core
remain hash-identical. Before-live phone JSON saved before synthetic checks. No accuracy claim.

Private phone-only APK installed with adb install -r, data retained:
artifacts/recognition_mode_header_01/app-debug-private-mode-header.apk
SHA256 f3a6aed9394f8c1d23c7a1e3a657dce6034176568da79e5e983e429423a3ee6b.
Previous empty-card private APK and all model rollback artifacts preserved.

Evidence: artifacts/recognition_mode_header_01/validation.json, build_private.log,
device_private_tests.log, host_tests_private/, before.json, before_sources/, sources/ and targets.json.

## Review

Presentation request met. No recognition/routing behavior change. Existing empty FINGERSPELL
RECOGNIZED container and CURRENT SIGN behavior preserved. Recognition quality remains imperfect
as already established; this change makes no recognition accuracy claim.


## 2026-10-09 — recognition mode pill hugs content

Supervisor requested content-sized mode indicator. Single presentation change: bridge's panel
ConstraintLayout width 0 -> WRAP_CONTENT. Existing 12dp horizontal padding, top-row centering,
labels and owner/routing behavior preserved. No new tests/dependencies or recognition changes.
181 existing host tests and 1 existing Xiaomi header/confirmation/WORD-preservation test pass
(5.416s). Exactly1/670 source/config files changed;669 unchanged. Current private phone-only APK:
artifacts/recognition_mode_header_01/hug_content_01/app-debug-private-hug-content.apk
SHAcd92a856a86a078f79e6b1a40182587e1737a213dba6c0d3baa754c25d36d4c0. Installed with adb install -r, app data retained.
Previous full-width header/private candidates preserved. Evidence child validation.json;
report docs/apphear-recognition-mode-header-2026-10-09.md. No further accuracy work authorized.
