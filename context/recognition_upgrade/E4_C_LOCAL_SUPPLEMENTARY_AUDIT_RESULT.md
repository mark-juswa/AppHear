# E4-C Local Supplementary Audit Result

- **Purpose:** Record the metadata-only audit that evaluates whether the local supplementary dataset at `E:\local` can replace the original E4-C targeted recording word list for a revised practical-vocabulary experiment.
- **Scope:** Audit, planning, and vocabulary selection only. This document does not authorize extraction, training, Android changes, production recognizer replacement, or mutation of source videos.
- **Current status:** Metadata audit complete on 2026-07-30. Local supplementary replacement is plausible after video/readability validation.
- **Verified project references:** `E4_C_TARGETED_COLLECTION_PLAN.md`, `E4_A_RESULT.md`, `artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_audit_01/*`, and local source root `E:\local`.
- **Source-of-truth files:** This document, `E4_C_TARGETED_COLLECTION_PLAN.md`, `DATASET_UPGRADE_PLAN.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, and parent `../eval-protocol.md`.
- **Related context files:** `README.md`, `OPEN_QUESTIONS.md`, `RISK_REGISTER.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.

## Why This Audit Was Created

The originally approved E4-C minimum recording list came from E4-A's 50-class ASL Citizen landmark audit:

`SWITZERLAND`, `COUCH`, `CURLYHAIR`, `DOWNSIZE1`, `PEEKABOO`, `BEE1`, `BOTH`, `SHARK1`, `SENTENCE2`, `LETTUCE1`, `SHAVE1`, `TWINS1`.

The user asked whether this 12-sign experiment could instead use the local supplementary dataset at `E:\local`. The audit checked whether `E:\local` has enough labeled clips, signer support, and practical vocabulary candidates to support a revised E4-C path without requiring immediate new recording.

## Verified Local Dataset Inventory

Audit artifact folder:

`artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_audit_01`

Generated files:

- `local_clip_inventory.csv`
- `local_gloss_support.csv`
- `replacement_candidate_pool.csv`
- `recommended_replacement_12_v1.csv`
- `summary.json`
- `README.md`

Corrected summary:

- Source root: `E:\local`.
- MP4 files found: 4,055.
- JSON sidecars parsed: 4,035.
- Parsed records: 4,035.
- Unique source folders: 3.
- Unique signer IDs observed: 4.
- Mapped conversational clips: 2,984.
- Blank or unmapped clips: 530.
- Original E4-C 12-sign overlap: 0 signs.

The audit found two sidecar dialects:

- Stage-E-style sidecars with `schema_stage`, `gloss`, `hand_hit_rate`, `pose_hit_rate`, and adjacent videos.
- Legacy accepted sidecars with `label`, `quality_score`, embedded `frames`, and a sibling `video` folder.

Legacy accepted sidecars do not expose `hand_hit_rate`; missing hand-hit metrics must not be treated as zero.

## Recommended Replacement 12

The metadata-supported revised E4-C 12-sign set is:

| Gloss | Raw clip count | Signer count | Notes |
|---|---:|---:|---|
| `HELLO` | 150 | 3 | folder words include `Hello`, `hi` |
| `YES` | 110 | 3 | practical conversational sign |
| `NO` | 110 | 3 | practical conversational sign |
| `SORRY` | 110 | 3 | practical conversational sign |
| `GOOD` | 109 | 3 | practical conversational sign |
| `BYE` | 150 | 3 | folder words include `bye`, `Goodbye` |
| `HAVE` | 50 | 2 | lower signer support than top six |
| `GET` | 70 | 2 | lower signer support than top six |
| `GO` | 50 | 2 | lower signer support than top six |
| `KNOW` | 50 | 2 | lower signer support than top six |
| `MAKE` | 70 | 2 | lower signer support than top six |
| `WELCOME2` | 70 | 2 | lower signer support than top six |

This is not the same scientific question as the original E4-C list. It changes E4-C from an E4-A-derived ASL Citizen failure-recovery vocabulary into a local supplementary practical-vocabulary audit.

## Interpretation

Verified findings:

- `E:\local` is large enough to support a metadata-screened 12-sign practical-vocabulary pilot.
- The dataset has only 4 observed signer IDs, so it is not sufficient by itself for strong signer-independent claims.
- The selected 12 signs have much higher local support than the original E4-C signs, which had zero direct overlap in this local root.
- Some records come from legacy accepted sidecars with quality scores but no hand-hit metrics.

Engineering inference:

- Replacing the original E4-C signs with local supplementary signs is reasonable if the goal is to get to a trainable, practical 12-sign pilot sooner.
- This should be treated as supplementary-data validation, not as proof that the model will generalize to new signers.
- The safest next step is video/readability validation for the selected local videos before any extraction/training.

## Required Validation Before Extraction Or Training

A revised E4-C local-supplementary pilot must not proceed directly to training. First validate:

- video paths resolve and are readable;
- selected labels map consistently to the intended glosses;
- clips contain the expected sign, not blank/no-sign segments;
- frame count and duration are sufficient;
- signer IDs are parsed consistently;
- no source clip appears in more than one split;
- train/validation/test split is signer-disjoint where possible;
- legacy accepted sidecars are handled without pretending missing hand-hit metrics are failures;
- clips with poor visibility, wrong labels, or unreadable videos are quarantined.

## Decision

Use `E:\local` as a revised E4-C supplementary-data path only after validation. Do not overwrite or delete the original approved E4-C recording package; keep both paths separate:

- original targeted recording package: `scratchpad/e4_c_targeted_collection/`;
- revised local supplementary audit artifacts: `artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_audit_01/`.

## Risks

- **Low signer diversity:** only 4 observed signer IDs; high risk of overfitting or signer leakage.
- **Label dialect mismatch:** folder names, `label`, and normalized gloss may not always mean the same sign variant.
- **Legacy metadata mismatch:** older sidecars lack hand-hit metrics.
- **Practical-vocabulary drift:** replacing the original list changes the experiment objective.
- **False confidence from clip counts:** many clips can still be weak if signer diversity and label quality are poor.

## Open Questions

- Are the 4 observed signer IDs truly distinct people?
- Which local clips are accepted-quality after visual/video validation?
- Should `WELCOME2` remain as a variant label, or be normalized to `WELCOME` after review?
- Are aliases like `BYE`/`GOODBYE` and `HELLO`/`HI` acceptable as single target classes?
- Can a signer-disjoint split be constructed with enough support for all 12 selected signs?

## Next Required Action

Prepare and run a local video validation/readability audit for `recommended_replacement_12_v1.csv`. This should inspect selected clip paths, label mapping, duration/frame counts, signer distribution, video readability, and split feasibility. Do not extract tensors or train a model until that validation passes.