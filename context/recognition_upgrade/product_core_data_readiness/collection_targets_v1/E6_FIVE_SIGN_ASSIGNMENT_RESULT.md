# E6 Five-Sign Assignment Result

Last updated: 2026-08-09

## Purpose

Record the reproducible, signer-disjoint data assignment for the approved bounded baseline:
`GOOD`, `HELLO`, `SORRY`, `HAVE`, and `KNOW`.

## Scope And Status

- **Status:** COMPLETE / STRUCTURAL GATE PASS / PILOT LIMITATIONS REMAIN.
- **Scope:** lineage-preserving role assignment and leakage validation only.
- **Not performed:** feature extraction, model training, schema changes, rejection experiments,
  specialists, RGB, TFLite export, or Android changes.

## Verified Project References

- Builder: `pipeline/rgb/e6_five_sign_assignment.py`
- Tests: `tests/test_e6_five_sign_assignment.py`
- Positive source: `artifacts/recognition_upgrade/product_core_data_readiness/e6_collection_integration_01/manifest.csv`
- Historical N0 source: `artifacts/recognition_upgrade/e2e_c0/n0_capture_06/`
- Historical P1 source: `artifacts/recognition_upgrade/product_core_data_readiness/e6_negative_reuse_audit_01/reusable_windows.csv`
- Historical OOV source: `artifacts/recognition_upgrade/product_core_data_readiness/e6_existing_negative_source_search_01/asl_citizen_oov_manifest.csv`
- Fresh negative source: `artifacts/recognition_upgrade/product_core_data_readiness/e6_negative_upload_review_01/accepted_fresh_negative_manifest.csv`

## Source-Of-Truth Outputs

Directory:
`artifacts/recognition_upgrade/product_core_data_readiness/e6_five_sign_assignment_01/`

- `assignment_summary.json`
- `assignment_manifest.csv`
- `positive_assignment.csv`
- `development_negative_assignment.csv`
- `fresh_negative_evaluation_assignment.csv`

## Verified Result

The assignment gate passed with no errors:

| Role | Rows |
|---|---:|
| Positive training | 685 |
| Positive validation | 179 |
| Positive fresh test | 300 |
| Positive historical diagnostic test | 63 |
| Historical development negative | 547 |
| Provisional fresh negative test | 560 |
| **Total** | **2,334** |

No signer group crossed an incompatible role. No raw-video hash crossed roles. All assigned raw
video paths existed when the gate ran. The positive vocabulary exactly matched the approved five
signs.

Positive counts by sign are:

| Sign | Train | Validation | Fresh test | Historical diagnostic test |
|---|---:|---:|---:|---:|
| GOOD | 125 | 57 | 60 | 12 |
| HELLO | 193 | 64 | 60 | 14 |
| SORRY | 123 | 23 | 60 | 12 |
| HAVE | 124 | 4 | 60 | 12 |
| KNOW | 120 | 31 | 60 | 13 |

## Architecture Decisions

- The existing schema v3.0 `[96,258]` contract remains unchanged.
- Historical negative evidence is development-only.
- The 560 new negative clips from `0F747C-S001` remain provisional fresh evaluation-only and
  receive zero development-gap credit.
- Historical ASL Citizen source holdout is reported separately from the genuinely fresh positive
  signer. It must not be described as fresh after E3-E5 reuse.
- The lean pilot explicitly waives the unverified 1,000-development-negative engineering target.
  It uses the verified 547 rows and carries the 453-row shortfall as a limitation.
- Negatives are assigned as gate/evaluation evidence. This result does not authorize treating
  `NO_SIGN` or `UNKNOWN_SIGN` as an extra softmax class without a separate architecture decision.

## Assumptions And Limitations

- `HAVE` has only four validation clips across four ASL Citizen validation signers. Its
  class-level validation metric will be noisy and cannot support a production claim.
- Fresh negative evaluation has one signer and short-event clips, not full streaming sessions.
- Source-scoped signer IDs prevent detected within-source leakage, but current metadata cannot
  prove that differently named people across sources are never the same human.
- The 1,000-negative target was an engineering target, not an experimentally established minimum.

## Risks

- Model selection may overreact to the small `HAVE` validation set.
- Short-event negative clips may underestimate false commits during long live-camera sessions.
- A one-signer fresh negative result may not generalize.
- Feature extraction can still fail MediaPipe quality gates even though raw-data assignment passed.

## Open Questions

- Does the unchanged v3.0 baseline generalize on the one fresh positive signer without repeating
  the E4/E5 source-confound failures?
- Can `HAVE` be evaluated primarily on its 60 fresh-test clips while keeping the four-clip
  validation metric explicitly secondary?
- Should a later production gate require another fresh negative signer and long streaming
  sessions? Current evidence says yes, but the amount remains unverified.

## Next Required Action

Architect and prepare exactly one clean v3.0 `[96,258]` five-sign extraction/training package from
this frozen assignment. The preparation must define extraction parity, train/validation selection,
historical-versus-fresh reporting, negative-gate evaluation, checkpoints, and stop conditions.
Do not start the long extraction or training run automatically.

## Related Context

- `E6_NEGATIVE_UPLOAD_REVIEW_PACKAGE.md`
- `E6_EXISTING_NEGATIVE_SOURCE_SEARCH_RESULT.md`
- `E6_NEGATIVE_REUSE_AUDIT_RESULT.md`
- `E6_COLLECTION_INTEGRATION_RESULT.md`
- `../../EVALUATION_AND_ACCEPTANCE_GATES.md`
- `../../ROLLBACK_AND_COMPATIBILITY_PLAN.md`
- `../../../feature-schema.md`

