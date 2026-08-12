# E4-B Strict 7-Sign Training Result

- **Purpose:** Record the completed E4-B strict 7-sign training result on the corrected local supplementary landmark dataset.
- **Scope:** Offline experiment analysis only. This does not authorize Android changes, production recognizer replacement, model export, feature-schema promotion, or source-dataset mutation.
- **Current status:** Training completed and checked on 2026-07-30. Result is a no-go for promotion and a no-go for repeating this exact mixed-provenance benchmark.
- **Verified project references:** `pipeline/rgb/e4_b_strict_runner.py`, `E4_B_STRICT_7_CORRECTED_DATASET_RESULT.md`, and `artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_02_corrected/*`.
- **Source-of-truth files:** `metrics/metrics.json`, `logs/*_history.csv`, `logs/corrected_dataset_summary.json`, `logs/corrected_feature_manifest.csv`, `dataset/landmark_features.npz`, `EXPERIMENT_MATRIX.md`, and parent `../eval-protocol.md`.
- **Related context files:** `README.md`, `E4_B_STRICT_7_RUNNER_PACKAGE.md`, `E4_C_LOCAL_SUPPLEMENTARY_AUDIT_RESULT.md`, `RISK_REGISTER.md`, `OPEN_QUESTIONS.md`, and parent `../progress-tracker.md`.

## Run

Run directory:

`artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_02_corrected`

Final check:

```json
{
  "passed": true,
  "errors": []
}
```

Dataset:

- Classes: 7 (`BYE`, `GOOD`, `HELLO`, `NO`, `SORRY`, `THANKYOU`, `YES`).
- Random baseline: `0.1429`.
- Tensor shape: `[840,96,258]`.
- Train/validation/test: `410/220/210`.
- Branches: `conv1d_baseline`, `tcn_masked_pool`.
- Seeds: `101`, `202`, `303`.
- Epoch count per branch/seed after resume: `40`.

## Metrics Summary

Best checkpoint means:

| Branch | Mean best train | Mean best validation | Mean best test |
|---|---:|---:|---:|
| `conv1d_baseline` | 0.9244 | 0.0924 | 0.1429 |
| `tcn_masked_pool` | 0.9943 | 0.0909 | 0.1429 |

Latest checkpoint behavior:

- Conv1D seeds 101/202 reached train `0.9805/0.9829`, validation `0.0909`, test `0.1429`.
- Conv1D seed 303 reached train `0.9390`, validation `0.0955`, test `0.1381`.
- Masked TCN seeds 101/202/303 reached train `1.0000`, validation `0.0909`, test `0.1429`.

Best validation checkpoint:

- Branch/seed: `conv1d_baseline`, seed `303`.
- Best validation: `0.0955`.
- Best test: `0.1429`.
- Validation predictions collapsed mostly to `NO`: `NO=187`, `THANKYOU=25`, `YES=7`, `SORRY=1`.
- Test predictions collapsed to `NO=148`, `YES=51`, `THANKYOU=11`.

Most other runs predicted almost every held-out item as `YES`.

## Interpretation

Verified findings:

- The models learned the training signer very strongly.
- Held-out validation/test performance was at or below random baseline.
- Prediction collapse was severe and high-confidence.
- The masked TCN did not improve generalization; it overfit the training split even more than Conv1D.
- No branch passed the registered gate.

Engineering inference:

- This result should not be interpreted as evidence that TCN is useless.
- It is stronger evidence that the benchmark is not technically fair: split, signer, and feature provenance are confounded.
- The corrected dataset solved the pilot 01 temporal extraction bug, but it still mixed train and held-out preprocessing sources.

## Root Cause Evidence

Feature provenance by split:

- Train: 410 rows, all `legacy_embedded_accepted_258`, signer `93EB89-S001`, source folder `3`, legacy accepted sidecars.
- Validation: 220 rows, all `stage_e_mediapipe_extracted_258`, signer sources `3B96F6-S002` and `3B96F6-S001`, source folder `2`.
- Test: 210 rows, all `stage_e_mediapipe_extracted_258`, signer `6F7328-S001`, source folder `1`.

Tensor distribution shift:

| Split | Mean length | Mean abs feature value | Nonzero fraction |
|---|---:|---:|---:|
| Train | 30.00 | 0.0390 | 0.1161 |
| Validation | 88.49 | 0.4987 | 0.6977 |
| Test | 85.82 | 0.4918 | 0.6554 |

The held-out tensors have roughly an order-of-magnitude larger feature magnitude and far more nonzero frames than the training tensors. This makes the experiment a provenance/domain-shift test more than a clean signer-independent sign-recognition test.

## Decision

E4-B strict 7-sign corrected training is **NO-GO** for:

- model promotion;
- Android integration;
- production recognizer replacement;
- claiming reliable signer-independent recognition;
- repeating the same mixed-provenance setup with more epochs.

## Recommended Next Action

Do not tune the TCN on this dataset. The highest-value next step is to build an apples-to-apples benchmark where train, validation, and test use the same capture/preprocessing provenance.

Recommended route:

1. Prefer a small same-provenance Stage-E collection for the same practical signs, adding at least one more current-pipeline signer so train/validation/test can all use current Stage-E extracted features.
2. If new recording is not possible, create a diagnostic two-way Stage-E-only experiment using folders `1` and `2` only, but label it diagnostic because it cannot support train/validation/test signer-disjoint evaluation.
3. Avoid training on legacy embedded features against Stage-E extracted held-out tensors unless the explicit goal is domain-adaptation research.

## Risks

- **Dataset insufficiency:** the local supplementary set does not currently support production-grade signer-disjoint training with same-provenance features.
- **False negative model conclusion:** model architecture may look bad because the benchmark is confounded.
- **False confidence from train accuracy:** near-perfect train accuracy is memorization of one signer/provenance, not recognition reliability.
- **Calibration failure:** validation/test confidence was extremely high despite wrong predictions.

## Next Required Action

Plan a same-provenance local benchmark before any more model tuning. The safest candidate is a Stage-E/current-pipeline collection for the same 7 practical signs with enough signer coverage for train/validation/test.

## Document Control

- **Architecture decisions:** Landmark-first remains the active branch, but E4-B strict 7 local is not a valid promotion benchmark.
- **Assumptions:** The feature-scale shift is caused by provenance/preprocessing differences; exact feature math drift requires a focused parity audit if we want to reuse legacy accepted features.
- **Open questions:** Whether legacy embedded features can be transformed into current Stage-E normalized feature space, and whether enough same-provenance local signers can be collected quickly.
- **Risks:** Same-provenance data collection may still fail if labels, signer diversity, or MediaPipe missingness are poor.
- **Next required action:** Prepare a same-provenance benchmark plan; do not rerun E4-B pilot 02 with more epochs.
