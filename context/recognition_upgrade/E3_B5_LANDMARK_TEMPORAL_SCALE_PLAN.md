# E3-B5 Landmark Temporal Scale Plan

**Purpose:** Scale the E3-B4 landmark-only temporal finding from a 7-class pilot to a larger,
multi-seed signer-disjoint validation before approving any RGB/fusion scaling or Android work.

**Scope:** Experiment planning and isolated offline runner only. This does not modify Android,
production recognizer assets, training datasets, or the current `[96,258]` runtime contract.

**Current status:** Prepared and smoke-tested locally on 2026-07-29. Full training is pending and
should be run manually by the developer because it is the long step.

**Last updated:** 2026-07-29.

## Verified Project References

- Runner: `pipeline/rgb/e3_b5_landmark_temporal_scale.py`.
- Prepared run: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed`.
- Source features: `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/features_streaming/{train,val,test}.npz`.
- Source vocab: `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/features/vocab.json`.
- Prior result: `context/recognition_upgrade/E3_B4_RESULT.md`.
- Current feature contract: `context/feature-schema.md`.

## Why This Comes Next

E3-B4 showed that `tcn_masked_pool` outperformed the simple Conv1D and ordinary TCN on the small
7-class strict-support pilot, but one held-out clip was 3.57 percentage points. That result is a
positive signal, not enough evidence to approve architecture direction. E3-B5 tests whether the same
masked temporal pooling advantage survives a larger vocabulary and random-seed variation.

## Prepared Dataset Contract

- Input tensor: `[N,96,258]` landmark features, schema `3.0`.
- Frame mask: `[N,96]`, used only by `tcn_masked_pool`.
- Class count: `50`.
- Rows: `1,200`.
- Split counts: `800` train, `200` validation, `200` test.
- Per-class support: `16/4/4` train/validation/test clips.
- Signer split: signer-disjoint, inherited from `features_streaming`.
- Participant overlap: none across train/validation/test.
- Class selection: top supported classes by train/validation/test count, then gloss name.
- Row selection: deterministic random sample within each source split/class using seed `290729`.

Inventory verified before preparation:

- `features_streaming/train.npz`: 36,960 rows, 2,731 classes, 35 participants.
- `features_streaming/val.npz`: 9,575 rows, 2,729 classes, 6 participants.
- `features_streaming/test.npz`: 29,770 rows, 2,731 classes, 11 participants.
- Support threshold `16/4/4`: 99 eligible classes.
- Support threshold `24/6/6`: 0 eligible classes because the validation split has only six signers.

## Model Branches

1. `conv1d_baseline`: simple landmark temporal control.
2. `tcn_pool`: current AppHear TCN-style encoder with ordinary pooling.
3. `tcn_masked_pool`: same temporal encoder with padded frames excluded from pooling.

Each branch runs on seeds `101`, `202`, and `303` with validation-selected best checkpoints.

## Metrics And Gate

Primary selection metric:

- Mean best-validation accuracy across seeds.

Required supporting metrics:

- Best-test accuracy after validation-only checkpoint selection.
- Latest validation/test accuracy.
- Per-class accuracy.
- Confusion matrix.
- Predicted-class distribution.
- Mean confidence.

Go if:

- `tcn_masked_pool` has the highest mean best-validation accuracy across seeds.
- `tcn_masked_pool` wins or ties validation in at least two of three seeds.
- Test accuracy after validation selection is not materially worse than the best comparator.
- Predictions do not collapse into a small group of glosses.

No-go if:

- The masked-TCN advantage disappears on the larger class set.
- All branches are near the 50-class random baseline of `0.02`.
- Training improves while validation/test stay flat.
- Prediction distribution collapses.

## Prepared Commands

Smoke test:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b5_landmark_temporal_scale smoke --run-dir "artifacts\recognition_upgrade\e3_landmark_temporal\pilot_02_50class_multiseed"
```

Full run:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b5_landmark_temporal_scale run --run-dir "artifacts\recognition_upgrade\e3_landmark_temporal\pilot_02_50class_multiseed"
```

Resume:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b5_landmark_temporal_scale run --run-dir "artifacts\recognition_upgrade\e3_landmark_temporal\pilot_02_50class_multiseed" --resume
```

Final check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b5_landmark_temporal_scale check --run-dir "artifacts\recognition_upgrade\e3_landmark_temporal\pilot_02_50class_multiseed" --require-metrics
```

## Local Validation Completed

- Syntax compile passed.
- Inventory inspection passed.
- Prepared dataset check passed.
- Smoke test passed for all three branches:
  - model creation,
  - forward pass,
  - one training batch,
  - checkpoint save,
  - checkpoint reload,
  - smoke output writing.

Native Windows TensorFlow reports CPU-only execution for TensorFlow >=2.11, so full training may be
slow on this machine. The developer should run the full command when ready.

## Architecture Decisions

- Keep the current `[96,258]` feature representation for this validation only.
- Do not approve RGB/fusion scaling until the landmark temporal branch has a stable larger-class
  baseline.
- Select using validation metrics only; test is reporting-only.
- Keep all outputs under the prepared run directory.

## Assumptions

- The existing ASL Citizen `features_streaming` tensors are the correct current source for this
  experiment.
- The inherited signer splits remain the authoritative signer-independent split for this stage.
- A 50-class validation is a useful bridge between the 7-class pilot and any larger production
  training.

## Open Questions

- Does masked pooling remain beneficial when validation has 200 clips instead of 28?
- Are remaining errors dominated by missing/unstable landmarks, similar sign motion, or class
  imbalance?
- Is the current TCN depth enough at 50 classes, or does a stronger temporal encoder become
  necessary after this gate?

## Risks

- The validation split has only six signers; this limits statistical strength.
- Class selection by support may favor signs with easier or more common examples.
- CPU-only training may take long enough that interruption/resume is likely.
- This still cannot measure RGB hand-shape benefit, non-manual cues, or continuous boundaries.

## Next Required Action

Run the full E3-B5 command, then run the final check. After completion, inspect
`metrics/metrics.md`, `metrics/metrics.json`, and `check_report.json` before deciding whether
masked TCN becomes the landmark baseline for the next phase.
