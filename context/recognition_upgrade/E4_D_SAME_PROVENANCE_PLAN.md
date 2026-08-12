# E4-D Same-Provenance Stage-E Diagnostic Plan

- **Purpose:** Define the next diagnostic benchmark after E4-B failed because train and held-out splits used different feature provenance.
- **Scope:** Offline manifest/package planning only. This does not authorize Android changes, production recognizer replacement, model export, feature-schema promotion, or source-dataset mutation.
- **Current status:** Manifest and runner package prepared and smoke-tested on 2026-07-30. Long extraction/training are user-run steps.
- **Verified project references:** `pipeline/rgb/e4_d_same_provenance_manifest.py`, `pipeline/rgb/e4_b_strict_runner.py`, `E4_B_STRICT_7_TRAINING_RESULT.md`, and `artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_*`.
- **Source-of-truth files:** `artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_manifest_01/manifest_report.json`, `artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_pilot_01/pilot_config.json`, `README_RUN.md`, `EXPERIMENT_MATRIX.md`, and parent `../eval-protocol.md`.
- **Related context files:** `README.md`, `E4_C_LOCAL_SUPPLEMENTARY_AUDIT_RESULT.md`, `E4_B_STRICT_7_TRAINING_RESULT.md`, `RISK_REGISTER.md`, `OPEN_QUESTIONS.md`, and parent `../progress-tracker.md`.

## Why E4-D Exists

E4-B pilot 02 was structurally valid but scientifically confounded:

- Train rows were all `legacy_embedded_accepted_258`.
- Validation/test rows were all `stage_e_mediapipe_extracted_258`.
- Train feature magnitude and sequence length differed by roughly an order of magnitude from validation/test.
- Models fit train strongly but collapsed on held-out rows.

E4-D removes that specific confound by using only Stage-E/current-pipeline local supplementary clips.

## Manifest

Manifest builder:

`pipeline/rgb/e4_d_same_provenance_manifest.py`

Manifest output:

`artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_manifest_01`

Selected signs:

`BYE`, `GOOD`, `HELLO`, `NO`, `SORRY`, `THANKYOU`, `YES`.

Policy:

- Same provenance: `stage_e_only`.
- Train/validation source folder: `2`.
- Test source folder: `1`.
- Validation policy: last 25 percent of train-source rows per class.
- Diagnostic, not production-grade.

Counts:

| Split | Rows | Signer/source |
|---|---:|---|
| Train | 165 | folder `2`, signers `3B96F6-S001`, `3B96F6-S002` |
| Validation | 55 | folder `2`, signers `3B96F6-S001`, `3B96F6-S002` |
| Test | 210 | folder `1`, signer `6F7328-S001` |

Per-class rows:

| Gloss | Train | Validation | Test |
|---|---:|---:|---:|
| `BYE` | 45 | 15 | 30 |
| `GOOD` | 15 | 5 | 30 |
| `HELLO` | 45 | 15 | 30 |
| `NO` | 15 | 5 | 30 |
| `SORRY` | 15 | 5 | 30 |
| `THANKYOU` | 15 | 5 | 30 |
| `YES` | 15 | 5 | 30 |

Warnings:

- `low_hand_hit_rate`: 204 rows.

## Runner

Runner:

`pipeline/rgb/e4_b_strict_runner.py`

Runner output:

`artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_pilot_01`

Branches:

- `conv1d_baseline`.
- `tcn_masked_pool`.

Seeds:

`101`, `202`, `303`.

Training defaults:

- Batch size: 8.
- Epochs per run command: 20.
- Learning rate: 0.0005.
- Resume supported by `--resume`.

## Local Validation

Completed checks:

```powershell
.\.venv\Scripts\python.exe -m py_compile pipeline\rgb\e4_d_same_provenance_manifest.py
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_d_same_provenance_manifest prepare --overwrite
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_d_same_provenance_manifest check --run-dir artifacts\recognition_upgrade\e4_generalization\e4_d_stage_e_same_provenance_manifest_01
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner check --run-dir artifacts\recognition_upgrade\e4_generalization\e4_d_stage_e_same_provenance_pilot_01
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner smoke --run-dir artifacts\recognition_upgrade\e4_generalization\e4_d_stage_e_same_provenance_pilot_01 --rows 4
```

Smoke result:

- Extracted 4 clips into `[4,96,258]`.
- Built both branches.
- Ran forward pass for both branches.
- Ran one train batch for both branches.
- Saved smoke weights for both branches.

Observed warning:

- One smoke clip produced a normalization `Mean of empty slice` warning from missing pose shoulder data. This does not block the diagnostic, but full extraction quality must be inspected before training interpretation.

## User Commands

Full extraction:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner extract-features --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_d_stage_e_same_provenance_pilot_01" --require-full
```

Dataset check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner check --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_d_stage_e_same_provenance_pilot_01" --require-full-dataset
```

Training:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner run --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_d_stage_e_same_provenance_pilot_01"
```

Resume interrupted training:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner run --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_d_stage_e_same_provenance_pilot_01" --resume
```

Final check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner check --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_d_stage_e_same_provenance_pilot_01" --require-full-dataset --require-metrics
```

## Interpretation Rules

If E4-D no longer collapses:

- The E4-B failure was mainly benchmark construction/provenance mismatch.
- Next step should be same-provenance collection with more signers before model scaling.

If E4-D still collapses:

- Investigate label quality, MediaPipe missingness, class imbalance, signer variation, and normalization before architecture changes.
- Do not conclude from this diagnostic alone that TCN is unusable.

If E4-D performs well on validation but poorly on test:

- Treat it as signer/generalization weakness.
- Collect more Stage-E/current-pipeline signer data.

## Decision

E4-D is approved as the next diagnostic package, but not as a production benchmark.

## Risks

- Validation is not signer-independent.
- Test has only one signer/source folder.
- 204 rows have low hand-hit warnings.
- Stage-E-only data volume is small for five of seven classes.
- The runner name still reuses `e4_b_strict_runner.py`; interpret by run directory and config, not by module name.

## Next Required Action

User runs full extraction for `e4_d_stage_e_same_provenance_pilot_01`, then checks the dataset before training.

## Document Control

- **Architecture decisions:** Continue landmark-first diagnostics before RGB/fusion or Android integration.
- **Assumptions:** Stage-E-only rows remove the dominant E4-B provenance confound.
- **Open questions:** Whether low hand-hit rows will dominate the diagnostic result.
- **Risks:** Same-provenance data may still be too small or too noisy to produce useful generalization evidence.
- **Next required action:** Run extraction and dataset check only; do not train until extraction quality is reviewed if errors or severe missingness appear.
