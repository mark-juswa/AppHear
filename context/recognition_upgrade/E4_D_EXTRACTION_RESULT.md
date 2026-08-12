# E4-D Same-Provenance Extraction Result

- **Purpose:** Record the completed feature extraction result for the E4-D Stage-E-only same-provenance diagnostic benchmark.
- **Scope:** Offline extraction analysis only. This does not authorize model promotion, Android changes, production recognizer replacement, model export, feature-schema promotion, or source-dataset mutation.
- **Current status:** Full extraction completed and checked on 2026-07-30. Diagnostic training is approved as the next user-run step.
- **Verified project references:** `pipeline/rgb/e4_d_same_provenance_manifest.py`, `pipeline/rgb/e4_b_strict_runner.py`, `E4_D_SAME_PROVENANCE_PLAN.md`, and `artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_pilot_01/*`.
- **Source-of-truth files:** `logs/feature_extraction_summary.json`, `logs/feature_extraction_manifest.csv`, `dataset/landmark_features.npz`, `check_report.json`, `EXPERIMENT_MATRIX.md`, and parent `../eval-protocol.md`.
- **Related context files:** `README.md`, `E4_B_STRICT_7_TRAINING_RESULT.md`, `E4_D_SAME_PROVENANCE_PLAN.md`, `RISK_REGISTER.md`, `OPEN_QUESTIONS.md`, and parent `../progress-tracker.md`.

## Run

Run directory:

`artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_pilot_01`

Final dataset check:

```json
{
  "passed": true,
  "errors": []
}
```

Extraction summary:

- Attempted rows: 430.
- OK/cached rows: 430.
- Failed rows: 0.
- Dataset rows: 430.
- Tensor shape: `[430,96,258]`.
- Missing rows: 0.
- Split counts: train 165, validation 55, test 210.
- Elapsed seconds: `1728.61`.

## Tensor Integrity

- No NaN values.
- No Inf values.
- Frame mask matches sequence lengths.
- Padded frames are zero.

## Extraction Quality

Average extracted hand-hit rate:

| Split | Rows | Min | Mean | Median | Max |
|---|---:|---:|---:|---:|---:|
| Train | 165 | 0.4545 | 0.9042 | 0.9213 | 1.0000 |
| Validation | 55 | 0.0000 | 0.8919 | 0.9888 | 1.0000 |
| Test | 210 | 0.0698 | 0.8376 | 0.9123 | 1.0000 |

Average pose-hit rate:

- Train: `0.9999`.
- Validation: `1.0000`.
- Test: `1.0000`.

Average hand-hit by test gloss:

| Gloss | Test mean hand-hit |
|---|---:|
| `BYE` | 0.782 |
| `GOOD` | 0.901 |
| `HELLO` | 0.730 |
| `NO` | 0.981 |
| `SORRY` | 0.942 |
| `THANKYOU` | 0.716 |
| `YES` | 0.812 |

## Feature Distribution Check

The E4-B provenance mismatch is removed. E4-D train and validation are both Stage-E/current-pipeline folder `2`, and test is Stage-E/current-pipeline folder `1`.

Tensor statistics:

| Split | Mean length | Mean abs feature | Nonzero fraction | Mask fraction |
|---|---:|---:|---:|---:|
| Train | 88.48 | 0.5011 | 0.6980 | 0.9217 |
| Validation | 88.49 | 0.4916 | 0.6969 | 0.9218 |
| Test | 85.82 | 0.4918 | 0.6554 | 0.8940 |

Train-vs-validation feature shift:

- Mean feature-difference: `0.02031`.
- Median feature-magnitude ratio: `0.995`.

Train-vs-test feature shift:

- Mean feature-difference: `0.08607`.
- Median feature-magnitude ratio: `0.877`.

Compared with E4-B pilot 02, the order-of-magnitude train/held-out feature mismatch is gone.

## Interpretation

Verified findings:

- Extraction completed cleanly for every row.
- The same-provenance goal was achieved: all active rows are Stage-E/current-pipeline features.
- Train and validation feature distributions are closely aligned.
- Test remains different because it is a held-out signer/source folder, but it is no longer in a different feature provenance domain.

Engineering inference:

- This is now a useful diagnostic training benchmark.
- It is still not production-grade because validation is not signer-independent and only one test signer/source folder is available.
- Low hand-hit rows may still reduce accuracy, especially `HELLO` and `THANKYOU` in test.

## Decision

Proceed to E4-D diagnostic training using:

`artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_pilot_01`

Do not interpret the result as production readiness. Use it only to test whether the E4-B prediction collapse disappears after fixing feature provenance.

## Next Required Action

User-run diagnostic training:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner run --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_d_stage_e_same_provenance_pilot_01"
```

Resume if interrupted:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner run --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_d_stage_e_same_provenance_pilot_01" --resume
```

Final check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner check --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_d_stage_e_same_provenance_pilot_01" --require-full-dataset --require-metrics
```

## Document Control

- **Architecture decisions:** E4-D remains landmark-first and diagnostic only.
- **Assumptions:** Removing feature provenance mismatch is sufficient to test whether E4-B collapse was primarily a benchmark-construction failure.
- **Open questions:** Whether low hand-hit rows or held-out signer variation will still dominate test performance.
- **Risks:** Validation is same-source and may overestimate held-out test performance.
- **Next required action:** Run training and evaluate prediction collapse, per-class accuracy, and test behavior.
