# Memory - Phase 1 Closed, Phase 2 Preparation Active

Last updated: 2026-08-12

## Verified completed state

- Phase 1 full-vocabulary manifest and v3.0 `[96,258]` dataset assembly passed.
- The frozen production-family streaming TCN won the equal-budget comparison and was evaluated once
  on the protected historical ASL Citizen test. Android production assets were not replaced.
- Three-seed ensemble protected results: top-1 `0.609542`, top-5 `0.886641`, macro-F1
  `0.596434`, worst-decile F1 `0.174134`, ECE `0.218310` across 2,620 clips and 236 signs.
- Four classes had zero recall: `HAVE`, `KNOW`, `LEAVE`, and `WHO`; 58 classes had F1 below
  `0.50`. Fixed degradation probes reduced top-1 by 0.73 points at stride 2, 2.41 points at
  stride 3, and 2.79 points under the tested hand-dropout condition.
- Phase 1 is a trustworthy landmark research baseline and Phase 2 error registry. It is not an
  Android release candidate and must not be retuned against the accessed test set.

## Phase 2 preparation completed

- Added `pipeline/rgb/phase2_prepare.py` and `tests/test_phase2_prepare.py`.
- Preparation artifacts are frozen under
  `artifacts/recognition_upgrade/phase2_preparation/phase2_prep_01/`.
- The error registry covers all 236 signs and records verified performance/confusion categories
  separately from hypotheses about appearance dependence or dataset variants.
- Category counts overlap by design: 48 landmark-stable, 40 landmark-moderate, 150
  confusion-heavy, 21 zero/very-low-recall, and 8 insufficient-evidence signs.
- Important top-5 rescue candidates include `HAVE`, `MONEY1`, `PERSON`, `NOW`, `MOST`, `BUT`,
  `PAPER`, and `KNOW`. Strong observed confusions include `MONEY1 -> BUY`, `NOW -> TODAY`,
  `HAVE -> YOUNG`, `PAPER -> SCHOOL`, `OR -> THEN`, and `TIRED -> YOUNG`.
- The controlled pilot contains 40 signs:
  `TABLE`, `WE`, `WORK`, `CLOTHES`, `DAY`, `VISIT`, `GOOD`, `HELLO`, `SORRY`, `HAVE`,
  `KNOW`, `THINK`, `TAKE`, `SELL`, `MONEY1`, `BUY`, `NOW`, `TODAY`, `PAPER`, `SCHOOL`,
  `YOUNG`, `OR`, `THEN`, `TIRED`, `LEAVE`, `WHO`, `PERSON`, `MOST`, `BUT`, `HERE`,
  `WASH2`, `DONTKNOW`, `TEACH2`, `EAT1`, `HOME`, `BECAUSE`, `SLEEP`, `COMPUTER`, `STAY`,
  and `STILL`.
- Metadata feasibility scanned all 8,131 Phase 1 rows without decoding RGB. All 2,519 pilot raw
  videos exist, but only 1,133 rows have a canonical synchronized raw-video + Stage-E + sign-span
  link. Only 550 of those are current training rows, approximately 10-16 per sign.
- Remaining AppHear/local rows are not eligible for hybrid training yet because Phase 1 assembled
  them from older E6 feature packages without a canonical synchronized Stage-E/span linkage.
- Pixel-level crop visibility, blur, containment, wrong/stale ROI, and left/right assignment remain
  unmeasured. Metadata availability is not proof of usable RGB crops.

## Decisions and protected boundaries

- Do not retrain Phase 1, start full 236-sign RGB extraction, train a hybrid model, retrain a hand
  detector, export TFLite, or modify Android.
- Do not repeat the failed E3 upper-body RGB or naive frozen fusion experiments.
- Intermediate fusion and landmark-top-k RGB reranking are competing hypotheses, not approved
  architecture. Branch A is the frozen Phase 1 control; B is RGB-only; C is quality-gated
  intermediate fusion; D is top-k RGB reranking.
- Candidate ROI routes must be compared before recognition training: direct MediaPipe with a short
  causal hold, pose-tracked recovery, the existing I320 proposal detector as diagnostic evidence,
  and an expanded upper-body availability control. Prior no-go evidence remains attached to each
  route.
- The historical Phase 1 test influenced pilot selection and cannot be used for Phase 2 model
  selection. A fresh signer/domain evaluation set is required before any scale-up claim.

## Next action

P2-P2 is implemented and the corrected final reference package is prepared under
`artifacts/recognition_upgrade/phase2_roi_audit/p2_p2_roi_audit_02`. It contains 120 frames, three
per sign, from 29 signers (99 train and 21 validation). The next action is the human hand-gold
review using `pipeline.rgb.phase2_p2_roi_audit review-gold`. After that, run `build-routes`, perform
the blinded route review, and run `evaluate` for the only valid GO/NO-GO decision.

Do not review `p2_p2_roi_audit_01`; it is superseded because its first selection over-weighted
direct-detection failures. The `_02` package balances one recovery-stress, one articulation-stress,
and one ordinary-control clip per sign while preferring distinct signers.

No recognition model training is authorized until one ROI route passes its preregistered gate and
the limited 550-row synchronized training pool is reassessed. If no route passes, stop Phase 2 model
work and choose between materially new ROI data/labels or retaining the landmark-only baseline.

## P2-P2 completed result

- All 120 gold frames and 480 blinded route panels were reviewed and evaluated.
- Final decision: `NO_GO_RGB_DATASET`; no current route may create the 40-sign RGB dataset.
- Corrected strict one-to-one R1 is best: 82.63% visible coverage, 68.92% complete two-hand, 76.72% provisional usable,
  0.86% wrong/stale/swap, 100% sync, and 69.17% triplet consistency.
- The developer stated that fine-grained manual route labels were uncertain. Treat usability and
  failure-reason counts as provisional. The no-go remains robust because objective R1 coverage,
  two-hand, and consistency gates fail independently.
- Recovery audit found all 190 gold boxes had anatomical side `unknown`; the first evaluator could
  reuse one ROI for two unknown hands. `p2p2.strict_one_to_one.v2` supersedes that result and blocks
  GO until side evidence exists. A 40-frame/80-hand side-only review across 25 signers is prepared.
- Do not resume the R1/R2 selector until at least 30 side-review frames are resolved. Earlier oracle
  numbers must be recomputed after strict matching and side adjudication.

## Validation

- `python -m pipeline.rgb.phase2_prepare prepare --output artifacts/recognition_upgrade/phase2_preparation/phase2_prep_01` passed.
- `python -m pipeline.rgb.phase2_prepare check --output artifacts/recognition_upgrade/phase2_preparation/phase2_prep_01` passed.
- `pytest tests/test_phase2_prepare.py -q`: 4 passed.
- Ruff and mypy passed for the new preparation module and tests.

No secrets or credentials are stored in this handoff.

---

# Memory - Phase 1 Android Shadow Package Ready

Last updated: 2026-08-12 15:05:18 +08:00

This section supersedes the stale P2-P2 next action above.

## What was built

- Added the hash-guarded offline exporter `model/experiments/phase1_android_shadow.py` and tests.
- Exported frozen Phase 1 TCN seeds 101/202/303 without reading the protected test set.
- Added default-off Android `Phase1ShadowRecognizer`, three separately named float32 TFLite assets,
  a parity manifest, a build-time debug override, and pure ensemble tests.
- Added a named opt-in APK at
  `artifacts/recognition_upgrade/phase1_android_shadow/device_package_01/apphear-phase1-shadow-debug.apk`.
- Updated canonical Android deployment, experiment matrix, migration, and rollback context files.

## Decisions made

- Current P2-P2/P2-P2F ROI routes remain retired. Improved ROI detection is later research that
  requires materially new localization data or methodology.
- Proceed with Option 2: measure the frozen Phase 1 three-seed landmark ensemble in Android shadow
  mode before any production replacement.
- Reject the INT8 shadow export: validation argmax agreement was `0.8828125`, below the `0.98` gate.
- Accept float32 for device profiling: argmax agreement `1.0`, top-1 delta `0.0`, and mean absolute
  probability difference `1.675e-9` on 128 validation rows.
- Do not weaken parity gates. Do not replace active `streaming.tflite` or change v3.0 `[96,258]`.
- Release shadow flag is hard-coded false; checked-in config is false. Shadow cannot commit or
  update sentence/UI, and any shadow load failure falls back to the active recognizer.

## Problems solved

- Diagnosed why the canonical INT8 export failed despite a small aggregate accuracy delta: it
  changed the winning class on 15/128 rows.
- Added a float32 export path that preserves Keras predictions.
- Prevented a malformed or mismatched experimental asset from blocking production recognizer load.
- Preserved a named shadow-enabled APK, then rebuilt the ordinary debug APK with shadow disabled.

## Current state

- Offline exporter check, Python tests, Ruff, mypy, Android unit tests, and debug builds pass.
- Accepted export: `artifacts/recognition_upgrade/phase1_android_shadow/export_float32_01`.
- Rejected INT8 evidence is retained at
  `artifacts/recognition_upgrade/phase1_android_shadow/export_01`.
- Float assets are 713,628 bytes each and all hashes match the manifest.
- Active model SHA-256 remains
  `42575710A4ADB0A1433B58BA9093BC4E9F49401381582CC4AD304FEEB669D4BB`.
- Named shadow APK SHA-256 is
  `91B25B1DEB62CAD5FAFEC33994B5ED71F8F6709FC3550D4AFFE76819FEFA6E53`.
- Device profiling is not complete because ADB/device access was unavailable in the session.
- `context/progress-tracker.md` was not rewritten: it is approximately 5.7 MB and contains embedded
  null bytes. Canonical recognition-upgrade files contain the durable decisions instead.

## Next session starts with

Connect the Android device, install the named shadow APK, clear logcat, perform a short repeated-sign
session, and save `AppHearShadow`, `AppHearPerf`, `AppHearRecog`, and `AppHearRecognition` logs as
`artifacts/recognition_upgrade/phase1_android_shadow/device_package_01/device_run_01.log`. Analyze
active-versus-shadow agreement, ensemble latency, processed FPS, crashes, and any behavioral effect.

## Open questions

- Does the three-model float32 ensemble meet device p50/p95, FPS, memory, and thermal gates?
- Is active-versus-shadow agreement stable across repeated signs on the target phone?
- Can a later quantization-aware export recover INT8 argmax parity without retraining or test reuse?
- What materially new ROI detector/data strategy, if any, should reopen Phase 2 after shadow work?

No secrets or credentials are stored in this handoff.


# Memory - Text-to-Sign preview (2026-10-09)
User approved labeled unreviewed clips. Development-only clone and local branch; no push. See TEXT-TO-SIGN-PREVIEW.md. Existing historical memory preserved. Next session: obtain qualified ASL review and documented media rights for five phrases; physical phone testing remains open.
