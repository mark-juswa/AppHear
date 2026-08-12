# E6-2 Landmark Geometry Package

**Purpose:** Record the implemented and smoke-validated E6-2 package before full training.

**Scope:** Offline five-sign experiment only. No Android assets, production recognizer behavior,
source datasets, v3.0 feature files, rejection logic, RGB, specialists, or exports were changed.

**Current status:** PREPARED AND SMOKE-PASSED / FULL TRAINING NOT STARTED.

**Last updated:** 2026-08-09.

## Verified Implementation

- Feature builder: `pipeline/features/landmark_geometry.py`.
- Experiment runner: `pipeline/rgb/e6_2_landmark_geometry.py`.
- Opt-in augmentation dispatch: `model/train_streaming.py` using
  `augment.contract: apphear.landmark_geometry.v0`.
- Tests: `tests/test_landmark_geometry.py` and `tests/test_e6_2_landmark_geometry.py`.
- Run directory:
  `artifacts/recognition_upgrade/e6_landmark_geometry/e6_2_geometry_01`.
- Input: `[96,444]`; the first 258 channels are exact copies of v3.0.
- Source splits: repaired five-sign train, validation, AppHear variant stress, fresh AppHear test,
  and historical ASL test.
- Source checkpoint: verified broad 236-class Keras encoder recorded in the run manifest.

## Validation Result

- Focused unit tests: `21 passed`.
- All five actual-data splits derived with finite values, exact zero padding, and unchanged v3.0
  base channels.
- Three seed-specific initializers passed.
- Broad encoder layers copied into each control: `17`.
- Candidate weighted layers initialized: `18`, including the matched five-class head.
- Zero-extended layers: only `tcn0_conv1` and `tcn0_proj`.
- Candidate parameter increase: `47,616` (`186 * (3 + 1) * 64`).
- Maximum initial control/candidate output difference: `0.0` for all seeds.
- Actual-data smoke input/output: `[2,96,444] -> [2,96,5]`.
- One training step, checkpoint save, checkpoint reload, augmentation consistency, and output
  writing passed.
- Structural check with `--require-smoke`: passed with zero errors.

The first prepare attempt reported `passed: false` because the plan incorrectly expected `48,128`
new parameters. The tensor adds `186`, not `188`, channels; the correct increase is `47,616`.
The gate exposed this bookkeeping error. The code and architecture plan were corrected, and the
second preparation passed. Weight parity was exact in both attempts.

## Full User-Run Command

```powershell
cd "F:\ASL DATASET\5. Apphear3"

.\.venv\Scripts\python.exe -m pipeline.rgb.e6_2_landmark_geometry train `
  --run-dir "artifacts\recognition_upgrade\e6_landmark_geometry\e6_2_geometry_01"
```

Resume after interruption:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_2_landmark_geometry train `
  --run-dir "artifacts\recognition_upgrade\e6_landmark_geometry\e6_2_geometry_01" `
  --resume
```

After training:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_2_landmark_geometry evaluate `
  --run-dir "artifacts\recognition_upgrade\e6_landmark_geometry\e6_2_geometry_01"

.\.venv\Scripts\python.exe -m pipeline.rgb.e6_2_landmark_geometry check `
  --run-dir "artifacts\recognition_upgrade\e6_landmark_geometry\e6_2_geometry_01" `
  --require-smoke `
  --require-metrics
```

## Expected Outputs

- `models/seed_101`, `models/seed_202`, `models/seed_303` with `latest.keras`, `best.keras`,
  `final.keras`, and history.
- `logs/training_summary.json`.
- `metrics/metrics.json` with every frozen E6-2 gate and per-seed evaluation details.
- `check_report.json`.

## Architecture Decisions

- Keep v3.0 immutable and use a separate schema/run directory.
- Recompute derived geometry after every train-time base augmentation.
- Require exact control/candidate equality before training.
- Full training remains user-run because it is the long step.
- E6-3+ remain blocked until this result is reviewed.

## Assumptions

- Existing repaired tensors correctly encode canonical left/right ordering.
- This bounded five-sign experiment diagnoses representation value but cannot establish
  large-vocabulary production accuracy.

## Open Questions

- Does geometry improve `KNOW` on both fresh and variant-stress views?
- Does the 47,616-parameter increase overfit despite exact warm initialization?
- Which feature group matters if the combined candidate passes?

## Risks

- Existing fresh and historical tests have already influenced project decisions.
- The AppHear `KNOW` difference may be a semantic variant that geometry cannot repair.
- No Kotlin implementation exists; any offline pass still requires a future parity gate.

## Source-Of-Truth Files

- `E6_2_RICHER_LANDMARK_CONTROL_PLAN.md`
- `artifacts/recognition_upgrade/e6_landmark_geometry/e6_2_geometry_01/pilot_config.json`
- `artifacts/recognition_upgrade/e6_landmark_geometry/e6_2_geometry_01/feature_schema.json`
- `artifacts/recognition_upgrade/e6_landmark_geometry/e6_2_geometry_01/initialization/zero_extension_report.json`
- `artifacts/recognition_upgrade/e6_landmark_geometry/e6_2_geometry_01/smoke/smoke_summary.json`

## Related Context Files

- `README.md`
- `FEATURE_SCHEMA_PLAN.md`
- `EXPERIMENT_MATRIX.md`
- `EVALUATION_AND_ACCEPTANCE_GATES.md`
- `ROLLBACK_AND_COMPATIBILITY_PLAN.md`
- `../feature-schema.md`

## Next Required Action

The user runs the full training command, then evaluation and final check. Analyze the complete
metrics before approving any ablation, E6-3 work, export, or Android integration.
