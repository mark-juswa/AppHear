# E4-B Strict 7-Sign Signer-Disjoint Manifest Result

- **Purpose:** Record the strict local supplementary manifest that excludes the six two-signer classes and keeps only signs with enough signer coverage for train/validation/test signer-disjoint splits.
- **Scope:** Manifest and split packaging only. This result does not authorize feature extraction, model training, Android changes, production recognizer replacement, feature-schema promotion, or source-dataset mutation.
- **Current status:** Strict 7-sign validation and manifest package complete on 2026-07-30. Ready for review before a bounded E4-B extraction/training runner is prepared.
- **Verified project references:** `pipeline/rgb/e4_c_local_validate.py`, `pipeline/rgb/e4_b_strict_manifest.py`, `E4_C_LOCAL_SUPPLEMENTARY_VALIDATION_RESULT.md`, and `artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_signer_disjoint_manifest_01/*`.
- **Source-of-truth files:** This document, `E4_B_LOCAL_SUPPLEMENTARY_MANIFEST_RESULT.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `EXPERIMENT_MATRIX.md`, and parent `../eval-protocol.md`.
- **Related context files:** `README.md`, `OPEN_QUESTIONS.md`, `RISK_REGISTER.md`, and parent `../progress-tracker.md`.

## Why The 12-Sign Set Was Replaced

The 12-sign local supplementary set contained six classes with only two eligible signers:

`GET`, `GO`, `HAVE`, `KNOW`, `MAKE`, and `WELCOME2`.

Those classes cannot support a production-grade train/validation/test signer-disjoint benchmark. They were excluded from the strict package.

The strict 7-sign set is:

`HELLO`, `BYE`, `YES`, `SORRY`, `NO`, `THANKYOU`, and `GOOD`.

## Runs

Validation command:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_c_local_validate prepare --output artifacts\recognition_upgrade\e4_generalization\e4_c_local_supplementary_validation_strict_7_01 --selected-gloss HELLO --selected-gloss BYE --selected-gloss YES --selected-gloss SORRY --selected-gloss NO --selected-gloss THANKYOU --selected-gloss GOOD --overwrite
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_c_local_validate check --run-dir artifacts\recognition_upgrade\e4_generalization\e4_c_local_supplementary_validation_strict_7_01
```

Manifest command:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_manifest prepare --overwrite
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_b_strict_manifest check --run-dir artifacts\recognition_upgrade\e4_generalization\e4_b_strict_7_signer_disjoint_manifest_01
```

Validation run directory:

`artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_validation_strict_7_01`

Manifest run directory:

`artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_signer_disjoint_manifest_01`

## Validation Result

- Candidate rows checked: 849.
- Eligible rows: 849.
- Readable rows: 849.
- Readable rate: 1.0000.
- Three-way signer-disjoint split possible for every selected class: yes.
- Classes blocking three-way split: none.

## Manifest Result

Split policy: `global_signer_disjoint_train_val_test`.

- Train signer: `93EB89-S001`.
- Validation signers: `3B96F6-S001`, `3B96F6-S002`.
- Test signer: `6F7328-S001`.
- Train rows: 410.
- Validation rows: 220.
- Test rows: 210.
- Quarantined rows: 9.
- Check result: passed with no errors.

## Per-Class Split

| Gloss | Train | Validation | Test | Quarantine |
|---|---:|---:|---:|---:|
| `BYE` | 60 | 60 | 30 | 0 |
| `GOOD` | 50 | 20 | 30 | 9 |
| `HELLO` | 60 | 60 | 30 | 0 |
| `NO` | 60 | 20 | 30 | 0 |
| `SORRY` | 60 | 20 | 30 | 0 |
| `THANKYOU` | 60 | 20 | 30 | 0 |
| `YES` | 60 | 20 | 30 | 0 |

## Interpretation

Verified findings:

- This is cleaner than the 12-sign local pilot because every active split is signer-disjoint.
- There is no signer overlap among train, validation, and test splits.
- The strict package has fewer signs but a stronger evaluation protocol.
- The package still has limited statistical strength because each class effectively has one train signer, one test signer, and one validation signer source.

Engineering recommendation:

- Use this strict 7-sign package as the next E4-B benchmark before training on the weaker 12-sign set.
- Treat this as a protocol-clean local benchmark, not a final production release gate.
- Keep the excluded six signs as collection targets for a later 12-sign upgrade.

## Decision

Prefer the strict 7-sign signer-disjoint package over the 12-sign two-way local pilot for the next E4-B experiment.

## Risks

- **Small signer count:** protocol is clean, but three signers per class is still thin.
- **One training signer:** model may still overfit to `93EB89-S001` signing style.
- **Validation signer asymmetry:** `GOOD` uses `3B96F6-S001` as validation while the other six signs use `3B96F6-S002`.
- **Vocabulary reduction:** reducing to 7 signs makes the task easier and less representative than the desired 12+ sign application.

## Next Required Action

Review and approve this strict 7-sign manifest. If accepted, prepare a bounded E4-B extraction/training runner that consumes `artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_signer_disjoint_manifest_01/pilot_manifest.csv`, writes isolated outputs, supports resume, and does not touch Android or production recognizer assets.