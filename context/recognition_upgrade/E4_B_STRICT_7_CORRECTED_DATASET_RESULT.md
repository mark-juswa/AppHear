# E4-B Strict 7-Sign Corrected Dataset Result

- **Purpose:** Record the corrected strict 7-sign landmark dataset after discovering that the first full extraction used the wrong temporal source for legacy accepted clips.
- **Scope:** Dataset correction and validation only. This does not authorize model promotion, Android changes, production recognizer replacement, feature-schema promotion, or source-dataset mutation.
- **Current status:** Corrected dataset prepared and checked on 2026-07-30. Training is the next user-run step if this corrected dataset is accepted.
- **Verified project references:** `pipeline/rgb/e4_b_strict_runner.py`, `pipeline/rgb/e4_b_correct_legacy_dataset.py`, `E4_B_STRICT_7_RUNNER_PACKAGE.md`, `E4_B_STRICT_7_SIGNER_DISJOINT_MANIFEST_RESULT.md`, `artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_01/*`, and `artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_02_corrected/*`.
- **Source-of-truth files:** This document, `logs/corrected_dataset_summary.json`, `logs/corrected_feature_manifest.csv`, `dataset/landmark_features.npz`, `EXPERIMENT_MATRIX.md`, and parent `../eval-protocol.md`.
- **Related context files:** `README.md`, `E4_B_STRICT_7_RUNNER_PACKAGE.md`, `OPEN_QUESTIONS.md`, `RISK_REGISTER.md`, and parent `../progress-tracker.md`.

## Why Pilot 01 Must Not Be Trained

The original run directory is:

`artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_01`

Its full feature extraction completed mechanically, but it should be treated as diagnostic-only. The problem was not tensor shape or file integrity; the problem was data meaning.

Verified extraction summary from pilot 01:

- Attempted rows: 840.
- Feature tensor shape: `[840,96,258]`.
- Failed rows: 0.
- Split counts: train 410, validation 220, test 210.
- Average extracted hand-hit rate by split:
  - Train: `0.156`.
  - Validation: `0.901`.
  - Test: `0.838`.

Root cause:

- All train rows came from the legacy accepted local source (`93EB89-S001`, folder `E:\local\3`).
- Those legacy examples include accepted JSON sidecars with embedded curated 258-feature frame arrays.
- Pilot 01 reprocessed the full source videos from timestamp zero instead of consuming the accepted sign-segment features.
- The result was a training split dominated by non-sign/background or wrong temporal regions, while validation/test used newer Stage-E clips.

Decision:

`e4_b_strict_7_landmark_pilot_01` is invalid for training and must remain diagnostic-only.

## Corrected Dataset

Corrected run directory:

`artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_landmark_pilot_02_corrected`

Correction script:

`pipeline/rgb/e4_b_correct_legacy_dataset.py`

Correction rule:

- For `legacy_accepted` rows, use the embedded accepted JSON `frames` array, requiring `feature_size == 258`.
- Pad/truncate those accepted arrays to `[96,258]`.
- For Stage-E rows, reuse the existing per-clip MediaPipe-extracted features from pilot 01.
- Preserve the strict 7-sign manifest, selected classes, and signer-disjoint split.
- Write all corrected outputs into a new run directory; do not overwrite pilot 01.

Source feature counts:

- `legacy_embedded_accepted_258`: 410 rows.
- `stage_e_mediapipe_extracted_258`: 430 rows.

## Validation Result

Commands checked:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_correct_legacy_dataset check --run-dir artifacts\recognition_upgrade\e4_generalization\e4_b_strict_7_landmark_pilot_02_corrected
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner check --run-dir artifacts\recognition_upgrade\e4_generalization\e4_b_strict_7_landmark_pilot_02_corrected --require-full-dataset
```

Result:

- Both checks passed.
- Rows: 840.
- Shape: `[840,96,258]`.
- No NaN values.
- No Inf values.
- Frame mask matches sequence lengths.
- Padded frames are zero.
- Split counts:
  - Train: 410.
  - Validation: 220.
  - Test: 210.
- Length range: min 30, median 84, max 90.

Corrected average hand-hit rate by split:

- Train: `1.000`.
- Validation: `0.901`.
- Test: `0.838`.

Corrected average hand-hit rate by gloss:

| Gloss | Rows | Mean hand-hit |
|---|---:|---:|
| `BYE` | 150 | 0.901 |
| `GOOD` | 100 | 0.939 |
| `HELLO` | 150 | 0.936 |
| `NO` | 110 | 0.982 |
| `SORRY` | 110 | 0.966 |
| `THANKYOU` | 110 | 0.907 |
| `YES` | 110 | 0.914 |

## Interpretation

Verified findings:

- Pilot 02 corrected the main pilot 01 flaw: the training split now contains accepted sign features instead of mostly failed long-video re-extraction.
- The tensor contract is structurally valid for the existing `[96,258]` landmark runner.
- The split remains strict signer-disjoint by the manifest policy.

Engineering inference:

- This corrected dataset is the best current local supplementary E4-B benchmark.
- It is strong enough to justify the next bounded training run.
- It is still not production-grade evidence because it mixes feature provenance: legacy embedded accepted features for train and Stage-E extracted features for validation/test.

## Risks

- **Feature provenance mismatch:** Train rows use embedded legacy accepted features; validation/test rows use current Stage-E extraction. This is better than pilot 01 but still may create train/test preprocessing skew.
- **Limited signer count:** The benchmark remains thin: one train signer source, validation signer sources, and one test signer source.
- **Legacy schema confidence:** Legacy accepted features are 258-wide and pass structural checks, but they do not carry the same explicit provenance as newly extracted Stage-E features.
- **Validation/test MediaPipe missingness:** Validation/test average hand-hit rates remain below 1.0, so some evaluation error may reflect detector/extraction weakness rather than sign classification alone.

## Decision

Use `e4_b_strict_7_landmark_pilot_02_corrected` for the next E4-B training run.

Do not train from `e4_b_strict_7_landmark_pilot_01`.

## Next Required Action

User-run training on the corrected dataset:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner run --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_b_strict_7_landmark_pilot_02_corrected"
```

Resume if interrupted:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner run --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_b_strict_7_landmark_pilot_02_corrected" --resume
```

Final check after training:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_runner check --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_b_strict_7_landmark_pilot_02_corrected" --require-full-dataset --require-metrics
```

## Document Control

- **Architecture decisions:** Continue landmark-first generalization work before any Android production integration or renewed RGB fusion.
- **Assumptions:** Accepted legacy JSON frames are treated as valid v3-compatible 258-feature sequences because they pass shape and hand-coverage checks; exact byte-level parity with current Stage-E extraction is not proven.
- **Open questions:** Whether training on legacy embedded features and evaluating on Stage-E extracted features will inflate or depress held-out signer results.
- **Risks:** Feature provenance mismatch, small signer count, and residual MediaPipe missingness remain active.
- **Next required action:** Run training only on `e4_b_strict_7_landmark_pilot_02_corrected`, then analyze validation-selected metrics and confusion outputs.
