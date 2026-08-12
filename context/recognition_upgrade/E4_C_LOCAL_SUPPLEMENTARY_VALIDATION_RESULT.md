# E4-C Local Supplementary Validation Result

- **Purpose:** Record the video-readability and split-feasibility validation for the revised E4-C local supplementary 12-sign candidate set from `E:\local`.
- **Scope:** Validation only. This result does not authorize tensor extraction, model training, Android changes, production recognizer replacement, feature-schema promotion, or source-dataset mutation.
- **Current status:** Validation complete on 2026-07-30. Mechanical video-readability gate passed; strong three-way signer-disjoint evaluation is blocked for six classes by signer coverage.
- **Verified project references:** `pipeline/rgb/e4_c_local_validate.py`, `E4_C_LOCAL_SUPPLEMENTARY_AUDIT_RESULT.md`, and `artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_validation_01/*`.
- **Source-of-truth files:** This document, `E4_C_LOCAL_SUPPLEMENTARY_AUDIT_RESULT.md`, `E4_C_TARGETED_COLLECTION_PLAN.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, and parent `../eval-protocol.md`.
- **Related context files:** `README.md`, `OPEN_QUESTIONS.md`, `RISK_REGISTER.md`, and parent `../progress-tracker.md`.

## Run

Command executed:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_c_local_validate prepare --overwrite
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_c_local_validate check --run-dir artifacts\recognition_upgrade\e4_generalization\e4_c_local_supplementary_validation_01
```

Run directory:

`artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_validation_01`

Outputs:

- `validated_clip_inventory.csv`
- `gloss_validation_summary.csv`
- `validation_report.json`
- `check_report.json`
- `README.md`

No frame tensor extraction or training was run.

## Validated Candidate Set

`HELLO`, `YES`, `NO`, `SORRY`, `GOOD`, `BYE`, `HAVE`, `GET`, `GO`, `KNOW`, `MAKE`, and `WELCOME2`.

## Result Summary

- Candidate rows checked: 1,099.
- Eligible rows: 1,099.
- Readable rows: 1,099.
- Readable rate: 1.0000.
- Unique eligible signer IDs: 4.
- Signers: `3B96F6-S001`, `3B96F6-S002`, `6F7328-S001`, and `93EB89-S001`.
- Two-way signer-disjoint split feasibility: yes for every selected class.
- Three-way signer-disjoint train/validation/test feasibility: no for every selected class set.
- Classes blocking three-way split: `GET`, `GO`, `HAVE`, `KNOW`, `MAKE`, and `WELCOME2`.

## Per-Class Support

| Gloss | Eligible rows | Signers | Min per signer | Max per signer | Dialects |
|---|---:|---:|---:|---:|---|
| `BYE` | 150 | 3 | 30 | 60 | legacy + Stage-E |
| `GET` | 70 | 2 | 30 | 40 | Stage-E |
| `GO` | 50 | 2 | 20 | 30 | Stage-E |
| `GOOD` | 109 | 3 | 20 | 59 | legacy + Stage-E |
| `HAVE` | 50 | 2 | 20 | 30 | Stage-E |
| `HELLO` | 150 | 3 | 30 | 60 | legacy + Stage-E |
| `KNOW` | 50 | 2 | 20 | 30 | Stage-E |
| `MAKE` | 70 | 2 | 30 | 40 | Stage-E |
| `NO` | 110 | 3 | 20 | 60 | legacy + Stage-E |
| `SORRY` | 110 | 3 | 20 | 60 | legacy + Stage-E |
| `WELCOME2` | 70 | 2 | 30 | 40 | Stage-E |
| `YES` | 110 | 3 | 20 | 60 | legacy + Stage-E |

## Warnings

Warnings are not hard failures, but they must guide the next manifest/split package:

- 1,004 rows had no warning.
- 86 rows had `low_hand_hit`.
- 9 rows had `low_quality_score`.
- `WELCOME2` had the most low-hand-hit warnings: 24 rows.
- `GOOD` had 9 low-quality-score rows and 6 low-hand-hit rows.
- Legacy accepted sidecars: 359 rows.
- Stage-E sidecars: 740 rows.

## Interpretation

Verified findings:

- The selected local videos are readable and mechanically usable.
- The local supplementary candidate set is much more immediately trainable than the original E4-C list because it already has hundreds of clips for practical signs.
- The selected data is not enough for the same strength of signer-independent claim as ASL Citizen because several signs only have two eligible signers.

Engineering recommendation:

- Proceed to a bounded E4-B local-supplementary manifest/split package, but label it as a practical local pilot, not as a production-ready generalization experiment.
- Use a strict signer-held-out test signer and keep validation internal or cross-validation-style, because a fully independent train/validation/test signer split is impossible for six signs without additional collection.
- Quarantine or downweight warning rows in the next package rather than blindly training on every validated row.

## Decision

The validation gate passes for mechanical video readiness. It does not pass the stronger dataset-readiness bar for a rigorous three-way signer-disjoint experiment.

Approved next action, if the user accepts the limitation: prepare a bounded E4-B local-supplementary manifest/split package with explicit split policy and warning-row handling. Do not train yet.

## Risks

- **Signer coverage ceiling:** six classes have only two eligible signers.
- **Validation-set weakness:** if one signer is held out for test, validation may need to be carved from training signers or done by cross-validation, which weakens model-selection evidence.
- **Warning-row quality:** low hand-hit and low-quality-score rows could harm landmark training unless filtered or tracked.
- **Variant/alias drift:** `HELLO`/`HI`, `BYE`/`GOODBYE`, and `WELCOME2` require consistent label semantics before promotion.

## Next Required Action

Prepare a reviewed manifest/split package only. The package should choose the split policy explicitly, quarantine or flag warning rows, preserve source paths, and write a runbook. Extraction/training remains blocked until that package is reviewed.