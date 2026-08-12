# E4-B Local Supplementary Manifest Result

- **Purpose:** Record the reviewed manifest/split package prepared from the validated E4-C local supplementary 12-sign dataset.
- **Scope:** Manifest and split packaging only. This result does not authorize feature extraction, model training, Android changes, production recognizer replacement, feature-schema promotion, or source-dataset mutation.
- **Current status:** Manifest package complete on 2026-07-30. Package is ready for review before a bounded E4-B extraction/training runner is prepared.
- **Verified project references:** `pipeline/rgb/e4_b_local_manifest.py`, `E4_C_LOCAL_SUPPLEMENTARY_VALIDATION_RESULT.md`, and `artifacts/recognition_upgrade/e4_generalization/e4_b_local_supplementary_manifest_01/*`.
- **Source-of-truth files:** This document, `E4_C_LOCAL_SUPPLEMENTARY_VALIDATION_RESULT.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `EXPERIMENT_MATRIX.md`, and parent `../eval-protocol.md`.
- **Related context files:** `README.md`, `OPEN_QUESTIONS.md`, `RISK_REGISTER.md`, and parent `../progress-tracker.md`.

## Run

Commands executed:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_local_manifest prepare --overwrite
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_local_manifest check --run-dir artifacts\recognition_upgrade\e4_generalization\e4_b_local_supplementary_manifest_01
```

Run directory:

`artifacts/recognition_upgrade/e4_generalization/e4_b_local_supplementary_manifest_01`

Outputs:

- `pilot_manifest.csv`
- `class_split_summary.csv`
- `manifest_report.json`
- `check_report.json`
- `README_RUN.md`

No tensor extraction or training was run.

## Split Policy

Policy: `two_way_held_out_signer_with_internal_validation`.

- Held-out test signer: `6F7328-S001`.
- Reason: this is the only validated signer with coverage for all 12 selected classes.
- Internal validation: 20% of non-test signer rows per class/signer.
- Low-quality rows: quarantined, not assigned to train/validation/test.
- Seed: `300730`.

This is a practical local pilot split, not a rigorous production-grade three-way signer-disjoint benchmark.

## Manifest Counts

- Total manifest rows: 1,099.
- Train rows: 584.
- Internal validation rows: 146.
- Held-out test rows: 360.
- Quarantined rows: 9.

Warning counts inherited from validation:

- `low_hand_hit`: 86.
- `low_quality_score`: 9.

## Per-Class Split

| Gloss | Train | Val internal | Test | Quarantine | Train-like signers | Test signer |
|---|---:|---:|---:|---:|---|---|
| `BYE` | 96 | 24 | 30 | 0 | `3B96F6-S002`; `93EB89-S001` | `6F7328-S001` |
| `GET` | 32 | 8 | 30 | 0 | `3B96F6-S001` | `6F7328-S001` |
| `GO` | 16 | 4 | 30 | 0 | `3B96F6-S001` | `6F7328-S001` |
| `GOOD` | 56 | 14 | 30 | 9 | `3B96F6-S001`; `93EB89-S001` | `6F7328-S001` |
| `HAVE` | 16 | 4 | 30 | 0 | `3B96F6-S001` | `6F7328-S001` |
| `HELLO` | 96 | 24 | 30 | 0 | `3B96F6-S002`; `93EB89-S001` | `6F7328-S001` |
| `KNOW` | 16 | 4 | 30 | 0 | `3B96F6-S001` | `6F7328-S001` |
| `MAKE` | 32 | 8 | 30 | 0 | `3B96F6-S001` | `6F7328-S001` |
| `NO` | 64 | 16 | 30 | 0 | `3B96F6-S002`; `93EB89-S001` | `6F7328-S001` |
| `SORRY` | 64 | 16 | 30 | 0 | `3B96F6-S002`; `93EB89-S001` | `6F7328-S001` |
| `WELCOME2` | 32 | 8 | 30 | 0 | `3B96F6-S001` | `6F7328-S001` |
| `YES` | 64 | 16 | 30 | 0 | `3B96F6-S002`; `93EB89-S001` | `6F7328-S001` |

## Interpretation

Verified findings:

- The package has a clean held-out test signer with all 12 classes represented.
- There is no signer overlap between train-like rows and held-out test rows.
- Six classes have only one train-like signer: `GET`, `GO`, `HAVE`, `KNOW`, `MAKE`, and `WELCOME2`.
- The internal validation split is not signer-independent from training; it is only for debugging/model-selection inside this local pilot.

Engineering recommendation:

- Use this package for a bounded extraction/training pilot only if the result is interpreted as a local practical-vocabulary experiment.
- Do not compare its accuracy directly against ASL Citizen signer-disjoint E3/E4 results as if the protocol were equivalent.
- If the goal is a stronger generalization claim, either reduce to the six 3-signer classes or collect more signers for the six 2-signer classes before training.

## Decision

The manifest package passes its packaging gate and is ready for user review. It should not be used for training until the user approves the split limitation.

## Risks

- **One-train-signer classes:** six classes may overfit to one training signer and fail on the held-out signer.
- **Internal validation optimism:** validation is carved from training signers, so it may overestimate generalization.
- **Quarantined quality rows:** 9 low-quality `GOOD` rows are excluded; future scripts must respect the `quarantine` split.
- **Protocol drift:** future reports must label this as a two-way local pilot, not as the AppHear release gate.

## Next Required Action

Review and approve or revise the manifest package. If approved, prepare a bounded E4-B local-supplementary extraction/training runner that consumes `pilot_manifest.csv`, writes isolated outputs, supports resume, and keeps Android/production assets untouched.