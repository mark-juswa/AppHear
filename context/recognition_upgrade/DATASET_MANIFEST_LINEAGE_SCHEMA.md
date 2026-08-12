# Dataset Manifest And Raw-Video Lineage Schema

**Purpose:** Define the strict row-level manifest format required before AppHear recognition modeling resumes.

**Scope:** Dataset metadata contract only. This document does not change the current feature schema, Android runtime, production model, or training pipeline.

**Current status:** PROPOSED / REQUIRED FOR PRODUCT-CORE DATA READINESS.

**Last updated:** 2026-08-03.

## Rule

Raw video plus manifest is canonical. Features, crops, tensors, predictions, and model inputs are rebuildable artifacts.

No future model experiment may claim data-readiness unless every positive, no-sign, OOV, and transition row can be traced to its source video and extraction configuration.

## Required Row Fields

| Field | Required | Description |
|---|---|---|
| `manifest_version` | yes | Dataset-manifest schema version, starting at `apphear_dataset_manifest_v1`. |
| `row_id` | yes | Stable row ID unique within the manifest. |
| `clip_id` | yes | Stable source clip ID. |
| `source` | yes | Example: `asl_citizen`, `local`, `apphear_capture`, `nosign_capture`, `oov_capture`. |
| `source_manifest_path` | yes | Original split CSV, local audit CSV, or capture manifest path. |
| `source_row_index` | yes if available | Row number in the source manifest. Use empty only for raw-folder-only local rows pending repair. |
| `raw_video_path` | yes | Absolute path to the source video at audit time. |
| `raw_video_sha256` | yes | SHA256 of the raw video file. |
| `raw_video_bytes` | yes | Raw video byte size. |
| `raw_video_width` | yes | Decoded video width. |
| `raw_video_height` | yes | Decoded video height. |
| `raw_video_fps` | yes | Native FPS if available. |
| `raw_video_frame_count` | yes | Decoded frame count if available. |
| `decode_status` | yes | `ok`, `missing`, `zero_byte`, `decode_failed`, or `needs_review`. |
| `canonical_gloss` | yes for positive/OOV sign rows | AppHear canonical gloss. |
| `label_variant` | yes | Dataset/source variant, lexical alias, or `none`. |
| `label_status` | yes | `verified`, `needs_adjudication`, `relabel`, `exclude`, or `unknown`. |
| `sample_kind` | yes | `positive`, `no_sign`, `oov_sign`, `transition`, `partial_sign`, or `quality_probe`. |
| `negative_subtype` | yes for negatives | `N0_NO_HAND`, `P1_IDLE_HANDS`, `P1_FACE_ADJACENT`, `P1_ACCIDENTAL_MOTION`, `TRANSITION`, `OOV_SIGN`, etc. |
| `signer_id` | yes | Stable signer/participant ID. |
| `signer_source_id` | yes | Original signer ID from ASL Citizen, local filename, or capture folder. |
| `signer_group_id` | yes if known | Household/session/device grouping to prevent leakage. |
| `device_id` | yes if known | Phone/camera source. |
| `environment_id` | yes if known | Room/outdoor/background/lighting label. |
| `camera_facing` | yes if known | `front`, `back`, or `unknown`. |
| `handedness` | optional | `left`, `right`, `both`, `unknown`; only if reviewed or reliable. |
| `split` | yes | `train`, `val`, `test_fresh`, `test_source_holdout`, `audit_only`, or `exclude`. |
| `split_reason` | yes | Why this row belongs to the split. |
| `onset_frame` | optional for isolated; required when boundary modeling starts | Start of active sign. |
| `release_frame` | optional for isolated; required when boundary modeling starts | End of active sign. |
| `quality_status` | yes | `usable`, `needs_review`, `exclude`. |
| `quality_flags` | yes | Pipe-separated flags: `blur`, `occlusion`, `hands_missing`, `wrong_label`, `variant_mismatch`, `bad_crop`, etc. |
| `extraction_schema_version` | yes after extraction | Example: `3.0`; blank before extraction. |
| `extractor_version` | yes after extraction | Git commit or package version of extractor. |
| `mediapipe_mode` | yes after extraction | `IMAGE`, `VIDEO`, or `LIVE_STREAM`. |
| `normalizer_version` | yes after extraction | Normalization implementation/version. |
| `feature_row_id` | yes after extraction | Stable derived feature row ID. |
| `feature_artifact_path` | yes after extraction | Path to `.npz`/shard containing derived feature row. |
| `feature_artifact_sha256` | yes after extraction | Hash of derived artifact or shard. |
| `reviewer_id` | yes for reviewed labels | Reviewer/adjudicator ID or `unreviewed`. |
| `reviewed_at` | yes for reviewed labels | ISO date/time. |
| `notes` | optional | Free-form audit note. |

## Required Dataset-Level Files

Every bounded data package must contain:

- `manifest.csv`: canonical row-level manifest.
- `manifest.schema.json`: machine-readable field/type/required-field definition.
- `manifest_summary.json`: counts by sign, source, signer, split, variant, sample kind, quality status, and lineage status.
- `lineage_audit.csv`: file existence, decode, hash, duplicate, and source-reference checks.
- `split_audit.csv`: signer/source/session leakage checks.
- `label_audit.csv`: label/variant status and adjudication notes.
- `readiness_gate.json`: pass/fail result for every data-readiness gate.

## Split Contract

Required split properties:

- Signer-disjoint by default.
- Session/device burst disjoint where `signer_group_id` is known.
- Fresh test split must not reuse E3-E5 decision rows where avoidable.
- Source-balanced validation and test are preferred when both ASL Citizen and local data are used.
- If source balancing is impossible, create an explicit `test_source_holdout` split.

## Lineage Gate

The manifest fails if any selected row has:

- missing `raw_video_path`;
- missing or unreadable raw file;
- missing `raw_video_sha256`;
- missing `canonical_gloss` for positives;
- missing `sample_kind`;
- missing `signer_id`;
- train/validation/test split leakage;
- unresolved `label_status` outside `verified` for a promoted modeling row;
- derived feature row without matching `extraction_schema_version`, `extractor_version`, and `feature_artifact_path`.

## Relationship To Current v3.0 Features

This document does not replace schema v3.0. It adds the dataset lineage layer needed before any feature extraction.

Current v3.0 `[96,258]` feature rows can remain a frozen baseline artifact, but they are not enough for the next modeling phase unless a manifest can prove per-row lineage and split validity.

## Architecture Decisions

- Raw videos are preserved as canonical input.
- Derived `.npz` files are cache artifacts.
- Manifest versioning is separate from feature schema versioning.
- Every modeling experiment must declare both `manifest_version` and `extraction_schema_version`.

## Assumptions

- Existing raw video roots remain accessible during rebuild.
- Future implementation can create JSONL as well as CSV if streaming row processing is useful.

## Open Questions

- Whether ASL Citizen source indexes in old tensors can be safely joined back to split CSV rows.
- Whether local filename signer IDs should be replaced by a reviewed participant registry.
- Whether labels such as `THANKYOU`/`THANKS`, `BYE`/`GOODBYE`, and `WASH2`/`WASH` should become explicit lexical variants before they re-enter modeling.

## Risks

- A manifest that is too loose will allow E5-style untraceable training rows to return.
- A manifest that is too strict may exclude useful old rows until source mapping is repaired.
- Cross-source signer identity is unknown; conservative split grouping is required.

## Phase 1 Verified Lineage Implementation - 2026-08-11

`pipeline/splits/phase1_full_vocab.py` implements the non-destructive 236-class manifest gate. It
reconstructs ASL Citizen tensor rows from raw Stage-E records, verifies split row identity, attaches
only reviewed E6 rows with raw-video lineage, and writes protected clean replay separately. It does
not extract, train, export, or modify Android.

The structural smoke in `artifacts/recognition_upgrade/phase1_full_vocab/manifest_smoke_01/`
contains `8131` rows and `3926` training-eligible rows, covers all `236` classes and `40` training
signer groups, and has no signer-role, duplicate-ID, or protected-replay overlap. It omitted full
raw-file hashing, so it is not training authorization.

## Next Required Action

`manifest_01` passed `prepare --verify-hashes` and `check` on 2026-08-11: `8131` rows, no missing
files, hash failures, leakage, duplicate IDs, class-coverage loss, or protected replay overlap.

`pipeline/splits/phase1_assemble.py` is now the versioned tensor assembler. Its corrected smoke
`dataset_smoke_02` exercised stacked ASL rows and E6 per-clip rows, validated every `[96,258]`
tensor/mask/length/label contract, wrote separate stress and reused-positive diagnostic tensors,
and did not materialize protected replay. Next action: run the full assembler and checker.
