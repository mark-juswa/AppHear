# E6 Fresh Negative Upload Review Package

**Purpose:** Import and review the 2026-08-08 AppHear Recorder negative-context upload without
moving raw videos or granting invalid training/development credit.

**Scope:** Raw-video/sidecar lineage, hash/decode validation, deterministic session-level spot
review, and provisional fresh-negative evaluation assignment only. No feature extraction, model
training, schema change, TFLite export, Android change, or production replacement is authorized.

**Current status:** COMPLETE / 54-ROW REVIEW PASS / PROVISIONAL FRESH NEGATIVE EVALUATION READY.

**Last updated:** 2026-08-09.

## Verified Project References

- Raw upload: `scratchpad/e6_product_core_collection/raw/nosign/signs`.
- Import/review utility: `pipeline/rgb/e6_negative_upload_review.py`.
- Shared GUI: `pipeline/rgb/e6_product_core_review.py`, invoked in explicit negative-review mode.
- Focused tests: `tests/test_e6_negative_upload_review.py`.
- Prepared run: `artifacts/recognition_upgrade/product_core_data_readiness/e6_negative_upload_review_01`.
- Visual audit thumbnails: `artifacts/recognition_upgrade/product_core_data_readiness/e6_negative_upload_audit_01`.

## Verified Upload State

- 560 videos and 560 matching JSON sidecars.
- One new signer: `0F747C-S001`.
- 18 recorder sessions.
- 560 unique SHA-256 hashes; no exact duplicate videos.
- 560/560 videos passed `ffprobe` probing.
- Category inventory: 60 idle-hand, 60 face-adjacent, 60 accidental-motion, 60
  transition/partial, and 320 OOV clips across 11 labels.
- Clips are approximately 0.5-1.2 seconds, usually 15-35 native frames. They are short-event
  evidence, not complete 96-frame streaming windows.

## Completed Review Result

- Review rows: 54/54 complete.
- Decisions: 54 accept, zero reject, zero diagnostic-only, zero expert-review request.
- Session batches: 18/18 accepted.
- Accepted provisional fresh-evaluation rows: 560/560.
- Accepted by subtype: 60 idle-hand, 60 face-adjacent, 60 accidental-motion, 60
  transition/partial, and 320 OOV.
- Final split: `test_fresh_negative_provisional`.
- Production-ready decision: false. This is bounded single-signer, short-event evidence.
- The historical development gaps remain unchanged by design: 57 idle-hand, 146 face-adjacent,
  150 accidental-motion, and 100 transition/partial windows.

## Architecture Decisions

- The approved first baseline vocabulary is `GOOD`, `HELLO`, `SORRY`, `HAVE`, and `KNOW`.
- Every row from signer `0F747C-S001` is reserved as
  `test_fresh_negative_provisional`. Do not split this signer across development and evaluation.
- This upload receives zero credit toward the remaining 453-window historical development gap.
- A deterministic first/middle/last sample is reviewed for each of 18 sessions: 54 rows total.
- A session batch is accepted only when all three sampled rows are accepted. Any rejection,
  diagnostic-only decision, or expert-review requirement blocks automatic batch acceptance.
- Subtype overlap may be accepted as broad negative evidence, but approved core signs must be
  rejected from the negative set.

## Assumptions And Risks

- **Verified project evidence:** signer `0F747C-S001` does not occur in the audited E6 historical
  manifests.
- **Engineering inference:** one fresh negative signer is enough for a bounded pilot diagnostic,
  not production signer-independent evidence.
- **Risk:** recorder metadata and filenames cannot establish behavioral correctness; temporal human
  review remains required.
- **Risk:** short clips cannot measure long idle periods or full streaming-window false commits.
- **Risk:** accidental-motion samples visibly overlap face-adjacent behavior. This is acceptable for
  a broad negative target but must remain visible in subtype reports.

## Open Questions

- Does the accepted upload expose false commits that historical negative development data misses?
- Can a second independent negative signer be added later for production-strength evaluation?
- Will the approved lean baseline explicitly waive the 1,000-window engineering volume target for
  this pilot while preserving the unchanged gap in reporting?

## Next Required Action

The signer-disjoint assignment is complete and passed; see
`E6_FIVE_SIGN_ASSIGNMENT_RESULT.md`. Next, prepare exactly one clean schema-v3.0 five-sign
extraction/training package from that frozen assignment. Do not start long extraction or training
automatically.

## Source-Of-Truth Outputs

- `prepare_summary.json`
- `source_manifest_snapshot.csv`
- `review_manifest.csv`
- After review: `final_manifest.csv`, `accepted_fresh_negative_manifest.csv`, and
  `review_summary.json`

## Related Context

- `E6_EXISTING_NEGATIVE_SOURCE_SEARCH_RESULT.md`
- `E6_NEGATIVE_REUSE_AUDIT_RESULT.md`
- `E6_TARGETED_COLLECTION_RUNBOOK.md`
- `../../PRODUCT_CORE_DATA_READINESS_PACKAGE.md`
- `../../../progress-tracker.md`
- `E6_FIVE_SIGN_ASSIGNMENT_RESULT.md`
