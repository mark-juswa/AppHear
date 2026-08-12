# E6 Negative-Context Reuse Audit Result

**Purpose:** Determine how much existing P1 and E4-AG footage can safely reduce the E6
no-sign/OOV/transition collection gap without double-counting copied videos or reused test data.

**Scope:** Raw-video lineage, prior human-review reuse, conservative subtype assignment, and
coverage accounting only. No feature extraction, training, feature-schema change, TFLite export,
Android change, or production recognizer replacement was performed.

**Current status:** COMPLETE / AUDIT PASS / DEVELOPMENT GAP REDUCED / FRESH EVALUATION MISSING.

**Last updated:** 2026-08-05.

## Verified Project References

- Audit utility: `pipeline/rgb/e6_negative_reuse_audit.py`.
- Tests: `tests/test_e6_negative_reuse_audit.py`.
- Audit run: `artifacts/recognition_upgrade/product_core_data_readiness/e6_negative_reuse_audit_01`.
- Canonical P1 run: `artifacts/recognition_upgrade/e2e_c0/p1_capture_03`.
- E4-AG alias run: `artifacts/recognition_upgrade/e2e_c0/hello_like_p1_capture_01`.
- Canonical raw root: `scratchpad/e2e_c0_capture/raw/p1`.
- Copied alias root: `scratchpad/e4_ag_hello_like_nosign/raw/p1`.

## Verified Lineage Finding

The two raw roots present 60 paths but only 30 unique raw-video hashes. Every E4-AG video is a
byte-identical copy of a canonical E2e-C0 P1 video. E4-AG's `P03` and `P04` participant folders are
stale aliases for the original P1 participants `P02` and `P01`; they are not new signers.

Consequences:

- Count each raw video once.
- Preserve canonical `P01`/`P02` identity.
- Never place windows from one raw hash or signer in different splits.
- Do not treat E4-AG as fresh collection or independent evaluation evidence.
- Do not delete either source; preserve the alias paths as historical experiment lineage.

## Reviewed-Window Reuse

The canonical review contains 108 eligible rows and the E4-AG review contains 116. Joining by
`(raw_video_sha256, frame_index)` produces 197 unique reviewed windows, with 27 exact review
overlaps. Three overlap rows disagree on the binary near-face annotation; the audit conservatively
assigns those rows to face-adjacent.

| Canonical signer | Idle-hand windows | Face-adjacent windows | Allowed role |
|---|---:|---:|---|
| `P01` | 48 | 1 | Historical development/training |
| `P02` | 95 | 53 | Reused diagnostic validation |
| **Total** | **143** | **54** | Never fresh test |

The subtype assignment uses completed prior human review: `near_face=yes` becomes
`P1_FACE_ADJACENT`; other eligible visible-hand/non-sign rows become `P1_IDLE_HANDS`. It does not
infer accidental motion, OOV signing, or sign transitions from still-frame metadata.

## Recalculated Coverage

| Subtype | Target | Historical development credit | Remaining volume gap | Fresh evaluation |
|---|---:|---:|---:|---|
| `N0_NO_HAND` | 150 | 150 | 0 | Missing |
| `P1_IDLE_HANDS` | 200 | 143 | 57 | Missing |
| `P1_FACE_ADJACENT` | 200 | 54 | 146 | Missing |
| `P1_ACCIDENTAL_MOTION` | 150 | 0 | 150 | Missing |
| `OOV_SIGN` | 200 | 0 | 200 | Missing |
| `TRANSITION_PARTIAL` | 100 | 0 | 100 | Missing |
| **Total** | **1,000** | **347** | **653** | **Missing for every subtype** |

The former 850-window value was the post-N0, pre-P1-reuse estimate. The current verified volume gap
is 653. This is not a production-readiness pass because all credited footage is historical and was
already used in E2e-C0/E4/E5 development or diagnostics.

## Risks And Limits

- Only two canonical participants are represented.
- Both participants are indoor/front-camera recordings.
- Face-adjacent coverage is highly imbalanced: 53 of 54 windows come from `P02`.
- Prior experiments reused this footage, so it cannot estimate final generalization.
- Center-frame labels support conservative subtype accounting, not temporal action semantics.
- Additional windows from the same clips may increase volume but not signer/domain diversity and
  must not be used to manufacture a fresh test set.

## Decision And Next Action

Reuse the 197 windows for historical development only. Do not repeat their manual review, count the
E4-AG aliases as new footage, or use them as fresh validation/test evidence.

The next highest-value step is a broader existing-data search for independently recorded footage
that can validly cover accidental motion, OOV signs, transitions/partials, and additional
face-adjacent/idle-hand signers. Only after that search should the remaining recording checklist be
finalized. Positive feature extraction and model training remain blocked.

## Source-Of-Truth Outputs

- `raw_video_lineage.csv`
- `reusable_windows.csv`
- `coverage_recalculation.csv`
- `reuse_audit_summary.json`

## Related Context

- `E6_COLLECTION_INTEGRATION_RESULT.md`
- `E6_TARGETED_COLLECTION_RUNBOOK.md`
- `../../PRODUCT_CORE_DATA_READINESS_PACKAGE.md`
- `../../DATASET_MANIFEST_LINEAGE_SCHEMA.md`
- `../../../progress-tracker.md`
## Subsequent Existing-Source Search

`E6_EXISTING_NEGATIVE_SOURCE_SEARCH_RESULT.md` validates 200 signer-balanced ASL Citizen training
videos as historical OOV development evidence. That later result reduces the remaining development
volume gap from 653 to 453. It does not add fresh-evaluation evidence.