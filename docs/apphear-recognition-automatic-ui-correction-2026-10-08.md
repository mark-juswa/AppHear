# Automatic recognition UI correction — 2026-10-08

Active application: `C:/Users/Gigabyte/.codex/worktrees/fingerspell-continuous-oct05/5. Apphear3`.
Approved October 5 base: `b48594c4942d9e9ac0d94ff96396e80b9f049c0a`.

## Problem and decision

The coordination implementation had working automatic context routing but also placed WORD,
Spell and Finish spelling buttons on the camera screen. The supervisor rejected that chooser.
Remove those buttons and retain a small active-mode status. Context supplies an exclusive owner
command; it never supplies or corrects recognized letters. Existing Settings remains the manual
fallback. No change to the context matching rules or recognition timing thresholds.

The intended demonstrated input flow is **Text-to-ASL → type “What is your name?” → Sign It →
Reply → recognition camera**. Before signing starts, a supported fresh question, idle WORD
state and no usable hand allow automatic FINGERSPELL entry. Unsupported/compound questions
remain outside the six frozen English rules. Do not claim general semantic understanding.

The existing top speaker/Hear icon reviews accumulated actual spelling. Confirm and hear returns
to WORD without altering its sentence buffer. The bottom SPEAK button starts hearing speech input;
it is not spelling confirmation. Cancel leaves the draft in FINGERSPELL. No silence-based finish
or mode chooser was introduced.

## Two-letter complaint

The supplied screenshot shows RECOGNIZED “AM” and CURRENT SIGN dots. That does not establish a
two-letter rendering limit. The current held-letter policy and layout have no two-letter cap.
Both the current host test and Xiaomi test accumulate/display 104 characters; all five rendered
lines fit, last line ends at character 104 and no text is ellipsized.

Before testing, the phone's current and last-active JSON files were archived. Both contained an
empty draft, two Y decode events and three B events. They did **not** retain the screenshot's AM
episode. Their events did not include request epoch, current absence/candidate state or rejection
reason. Those logs cannot determine why Y was not added in the AM episode. Do not reconstruct it
or blame a specific gate without evidence.

Added read-only acceptance diagnostics: request/current epochs, latest missing-hand state,
candidate letter/count/span, latch and exact rejection/append reason. The `accept()` Boolean,
letter stabilization, model, singleton decoder and operational thresholds remain equivalent.
Existing diagnostic output retains its v1 schema and adds
`apphear.fingerspelling.acceptance_diagnostic.v1` metadata.

Also fixed a diagnostic persistence bug: flushing based on bounded `events.size % 10` stopped
periodic writes when that deque reached its maximum size of 64. It now uses an unbounded completed
decode counter. This fixes evidence freshness, **not recognition accuracy**. Stop/pause and accepted
letter writes retain the existing behavior. No RGB, landmarks or additional logits are retained.

## Exact application changes

- `android/app/src/main/java/com/example/apphear/coordination/RecognitionCoordinationBridge.kt`:
  remove three button views/listeners; retain mode status and existing Hear review/confirmation.
- `android/app/src/main/java/com/example/apphear/fingerspelling/HeldLetterPolicy.kt`:
  additive read-only acceptance state and explicit diagnostic reason for each existing branch.
- `android/app/src/main/java/com/example/apphear/fingerspelling/ContinuousFingerspell.kt`:
  save before/after acceptance state; fix bounded-deque persistence counter.
- `android/app/src/test/java/com/example/apphear/fingerspelling/HeldLetterPolicyTest.kt`:
  verify every diagnostic reason, state reads do not mutate acceptance, existing long buffer tests.
- `android/app/src/androidTest/java/com/example/apphear/coordination/RecognitionCoordinationInstrumentedTest.kt`:
  assert chooser absent; actual Hear confirmation records BELLA and restores WORD HELLO; intercept
  speech callback to avoid a remote TTS request. Existing internal veto/stale-context cases remain.
- `android/app/src/androidTest/java/com/example/apphear/coordination/RecognitionContextUiFlowInstrumentedTest.kt`:
  actual typed Text-to-ASL/Sign It/Reply flow automatically routes to FINGERSPELL without chooser;
  empty Hear cannot finish, repeated observations do not bounce and Settings preference is unchanged.

## Verification

- Fake and private host builds passed. Final private host suite: **181 tests, zero failures**.
- Xiaomi fake-provider test group: **6/6 passed**, 25.438 seconds. Includes actual typed UI flow,
  synthetic exclusive-owner/confirmation, two ready-camera WORD/Context regressions and two
  continuous/layout/Settings checks. Fake provider avoids remote provider calls.
- Final private APK Xiaomi group: **3/3 passed**, 8.349 seconds. Chooser absent, speaker confirmation,
  long draft display, repeats, no-hand refusal, zero F inference in WORD, unchanged WORD storage.
- Frozen inventory: **670 existing source/config files; 664 unchanged; exactly six scoped files
  changed; no source files added/deleted**. All **162 main asset files** unchanged. This includes
  Candidate01, WORD, Context provider/matcher, Adapter v1, timing asset and model assets. Activity,
  camera and recognition model/decoder code are unchanged in this correction.
- Installed FP32 model SHA remains
  `e78de274b967acf0ea9d30bd3f3ac4422a1ef8ebdd95c8676b57dd05fed75c4c`;
  model manifest SHA remains
  `8edc998728fa41883abacbc8382359d6d61621bc259da78ca7c2ab6f8126d01e`.
- Private APK SHA:
  `9501dbb1c91d08052338d66515cc56f115aabe6f6a3d81030485a533c1eafca8`.
  Installed with `adb install -r`, preserving app data. Local phone-only; do not distribute it.
- Previous private coordination APK SHA `6f56dc583148a3725ddc7ed973b633c34528eac2f71d363a9bfb04d96a4b3591`
  and all before-source snapshots remain available for rollback.

These are engineering tests, not held-out signer accuracy. No model training, feature math,
decoder/threshold tuning, test corpus access or protected WORD component changes occurred.

## Live verification status

One bounded supervisor check was requested using the intended typed Text-to-ASL → Reply flow,
followed by held A, M and Y. Await actual RECOGNIZED/CURRENT SIGN and new acceptance diagnostics.
Until those are read, the original AM plateau remains unresolved. Do not present the diagnostic
changes or synthetic 104-character test as proof of a live recognition fix.

## Evidence paths

All new evidence is under `artifacts/recognition_coordination_01/automatic_ui_fix_01/`:
`before.json`, original two phone JSON snapshots, `before_sources/`, `sources/`, `targets.json`,
`build_fake.log`, `build_private.log`, `host_tests_private/`, device test logs,
`device_fake/`, `device_private/`, `validation.json`, `package_identity.json`, versioned private APK.
Historical coordination, model parity and long spelling reports are preserved.


## Follow-up — empty RECOGNIZED container, 2026-10-09

During the live check, the supervisor reported RECOGNIZED missing. The inspected phone hierarchy
was on Text-to-ASL, where that component does not exist; Reply opens the recognition camera.
Separately, inspected `renderFingerspell()` delegated empty-draft card visibility to the original
WORD helper, which hides the `...` placeholder. This is now corrected ONLY in the active continuous
FINGERSPELL renderer: sentenceCard stays visible with the existing placeholder. WORD helper and
its callers outside this branch remain unchanged. Accessibility describes empty state as waiting
for letters. No model/acceptance rule change.

Two additional application files changed: RecognitionActivity.kt (only the active F rendering
branch) and ContinuousFingerspellInstrumentedTest.kt (empty-card regression). Prior six-file evidence
and APK are preserved. Follow-up build/device/hash evidence belongs to the separate child folder
`artifacts/recognition_coordination_01/automatic_ui_fix_01/empty_card_fix_01/`.


Follow-up verification passed: 181 host tests, zero failures; 3/3 final private Xiaomi tests,
11.193 seconds. Empty card visibility specifically asserted; long buffer still 104 characters.
Exactly two changes since the prior UI build; 668/670 files unchanged in this follow-up. Across
the complete correction, 662/670 unchanged and eight narrowly scoped UI/diagnostic/test files
changed. A byte-preserving seam check proves RecognitionActivity differs only in its active
continuous FINGERSPELL display branch. All WORD logic and model/decoder contracts preserved.
Latest installed private APK SHA:
`1d38ce947fbcc8c8148b0d8037b60a7c809c6203bf86caa7bd3d2f7a0e9278c8`.
No live letter accuracy or AM plateau fix established yet.


## Bounded live outcome — 2026-10-09

Supervisor replied “it is now good” after the corrected typed-question/camera check. This confirms
UI usability, not accurate AMY recognition. Retrieved current and last-active JSON agree:
FINGERSPELL, ten completed decodes, preview EY, zero stale owner results, measured last-window
cadence 5.136 observations/s. Raw decode sequence: A, S, S, E, E, E, A, Y, Y, Y.
Seven results needed more matching decodes; one S result was rejected because the latest hand
was missing; E and Y each stabilized and appended. A never accumulated three matching results.

Thus this latest two-character output is **acceptance/recognition behavior, not a two-character
container cap**. The original AM screenshot episode was not retained, so its exact failure is
still not reconstructable. No lowering of stabilization, transcript-conditioned guessing, model
change or new training was performed. The latest trace still does not recognize the requested
AMY reliably, and no competent signing ground truth was verified. Do not claim this fixes letter
accuracy. Context selects the owner, never the expected letters.

Live evidence: child-folder live_after_fingerspell_continuous.json,
live_after_fingerspell_continuous_last_active.json and live_analysis.json. No new video,
landmarks or per-timestep logits retained. Live UI-hierarchy capture did not produce usable XML while the camera was active; no live pixel/layout
claim is based on that failed capture. Visibility has supervisor confirmation plus the passing
empty-card and 104-character device assertions.
