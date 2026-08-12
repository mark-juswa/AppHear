# E4-B Strict 7-Sign Runner Package

- **Purpose:** Record the prepared extraction/training runner for the strict 7-sign local supplementary signer-disjoint benchmark.
- **Scope:** Experiment package preparation, smoke validation, and corrected dataset handoff only. This does not authorize Android changes, production recognizer replacement, feature-schema promotion, or source-dataset mutation.
- **Current status:** Runner prepared and smoke-tested on 2026-07-30. Pilot 01 full extraction later passed structurally but was invalid for training because legacy accepted rows were extracted from the wrong temporal source. Pilot 02 corrected dataset is ready for user-run training.
- **Verified project references:** `pipeline/rgb/e4_b_strict_runner.py`, `pipeline/rgb/e4_b_correct_legacy_dataset.py`, `E4_B_STRICT_7_SIGNER_DISJOINT_MANIFEST_RESULT.md`, `E4_B_STRICT_7_CORRECTED_DATASET_RESULT.md`, and `artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_02_corrected/*`.
- **Source-of-truth files:** This document, `E4_B_STRICT_7_SIGNER_DISJOINT_MANIFEST_RESULT.md`, `E4_B_STRICT_7_CORRECTED_DATASET_RESULT.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `EXPERIMENT_MATRIX.md`, and parent `../eval-protocol.md`.
- **Related context files:** `README.md`, `OPEN_QUESTIONS.md`, `RISK_REGISTER.md`, and parent `../progress-tracker.md`.

## Runner

Tooling:

`pipeline/rgb/e4_b_strict_runner.py`

Approved corrected run directory:

`artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_02_corrected`

Diagnostic-only original run directory:

`artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_01`

Prepared files in the corrected run:

- `pilot_config.json`
- `pilot_manifest.csv`
- `selected_classes.csv`
- `README_RUN.md`
- `dataset/landmark_features.npz`
- `logs/corrected_dataset_summary.json`
- `logs/corrected_feature_manifest.csv`
- `check_report.json`

## Experiment Scope

Classes:

`BYE`, `GOOD`, `HELLO`, `NO`, `SORRY`, `THANKYOU`, and `YES`.

Input contract:

- `[96,258]` landmark tensor.
- Legacy accepted rows use embedded accepted 258-feature frame arrays.
- Stage-E rows use current MediaPipe-extracted per-clip features from pilot 01.
- This is experiment-only and does not change the production feature schema or Android recognizer.

Split counts:

- Train: 410.
- Validation: 220.
- Test: 210.
- Quarantine: 9.

Branches:

- `conv1d_baseline`.
- `tcn_masked_pool`.

Seeds:

`101`, `202`, and `303`.

Training defaults:

- Batch size: 8.
- Epochs per run command: 20.
- Learning rate: 0.0005.
- Resume supported by `--resume`.

## Smoke Result

Original smoke command executed before full extraction:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner smoke --run-dir artifacts\recognition_upgrade\e4_generalization\e4_b_strict_7_landmark_pilot_01 --rows 4
```

Result:

- Extracted 4 clips into shape `[4,96,258]`.
- `conv1d_baseline` forward output shape: `[4,7]`.
- `tcn_masked_pool` forward output shape: `[4,7]`.
- One training batch ran for both branches.
- Smoke weights were saved for both branches.

## Pilot 01 Correction Finding

Pilot 01 full extraction completed mechanically, but it must not be used for training.

Verified pilot 01 issue:

- Tensor shape was `[840,96,258]` and failed rows were `0`.
- Train split average hand-hit rate was only `0.156`.
- Validation and test hand-hit rates were much higher: `0.901` and `0.838`.
- The train split consisted of legacy accepted local rows. Those examples had accepted JSON sidecars containing curated 258-feature sign-segment frames, but pilot 01 reprocessed the full raw videos from timestamp zero.

Corrected run:

`artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_02_corrected`

Correction result:

- Rows: 840.
- Shape: `[840,96,258]`.
- Split counts: train 410, validation 220, test 210.
- No NaN/Inf values.
- Masks and padded frames valid.
- Source feature counts: 410 legacy embedded accepted rows and 430 Stage-E extracted rows.
- Average hand-hit rates: train `1.000`, validation `0.901`, test `0.838`.

See `E4_B_STRICT_7_CORRECTED_DATASET_RESULT.md` for the source-provenance caveat and validation details.

## Commands For The User

Approved training command:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner run --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_b_strict_7_landmark_pilot_02_corrected"
```

Resume interrupted training:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner run --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_b_strict_7_landmark_pilot_02_corrected" --resume
```

Final check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner check --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_b_strict_7_landmark_pilot_02_corrected" --require-full-dataset --require-metrics
```

## Interpretation Rules

- This is a protocol-clean local benchmark because train, validation, and test signers are disjoint.
- It is not a production-release benchmark because there are only three signer sources per class.
- Accuracy must be reported as strict local held-out-signer evidence, not AppHear production readiness.
- If test predictions collapse to a few classes, the next step is data/label review, not Android integration.
- If validation/test are low, do not conclude that TCN is useless until feature-provenance mismatch and signer scarcity are considered.

## Risks

- The corrected dataset mixes feature provenance: legacy embedded accepted 258-feature frames for train and Stage-E extracted features for validation/test.
- One training signer may still cause style overfitting.
- Validation/test MediaPipe missingness remains below perfect hand coverage.
- TensorFlow native Windows does not use CUDA GPU for TF >=2.11; GPU training would need WSL2/other runtime.

## Next Required Action

The user runs training from `e4_b_strict_7_landmark_pilot_02_corrected`, then the final metrics check. Do not train from pilot 01.

## Document Control

- **Architecture decisions:** Continue landmark-first local generalization measurement before Android integration or renewed RGB fusion.
- **Assumptions:** Legacy embedded accepted rows are compatible enough for this bounded benchmark because they are 258-wide and pass structural checks.
- **Open questions:** Whether the mixed provenance will help or hurt held-out signer accuracy.
- **Risks:** Feature provenance mismatch, limited signer count, and residual MediaPipe missingness remain active.
- **Next required action:** Run the approved training command above.
