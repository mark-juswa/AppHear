# E6 Product-Core Lineage Fix And Supplementary Validation Result

**Purpose:** Record the first concrete data-readiness phase after E6-1: raw-video lineage repair, supplementary dataset validation, cleaned counts, gap recalculation, and vocabulary reassessment.

**Scope:** Data manifest and audit only. No feature extraction, model training, schema change, rejection testing, RGB, specialist, TFLite export, Android change, or production recognizer replacement was performed.

**Current status:** COMPLETE / MORE DATA REQUIRED BEFORE MODELING.

**Last updated:** 2026-08-03.

## Outputs

- `context/recognition_upgrade/product_core_data_readiness/lineage_fix_v1/canonical_product_core_manifest.csv`
- `context/recognition_upgrade/product_core_data_readiness/lineage_fix_v1/cleaned_counts_by_sign.csv`
- `context/recognition_upgrade/product_core_data_readiness/lineage_fix_v1/recalculated_data_gaps.csv`
- `context/recognition_upgrade/product_core_data_readiness/lineage_fix_v1/vocabulary_reassessment.csv`
- `context/recognition_upgrade/product_core_data_readiness/lineage_fix_v1/nosign_oov_transition_gap.json`
- `context/recognition_upgrade/product_core_data_readiness/lineage_fix_v1/lineage_fix_summary.json`

## Verified Inputs

- ASL Citizen split rows and raw videos under `F:/ASL DATASET/ASL CITIZEN/ASL_Citizen/`.
- Local supplementary audit manifest: `F:/ASL DATASET/ASL CITIZEN/suppliment/audit_manifest.csv`.
- Local raw videos and sidecars under `E:/local`.
- Previous recognition-upgrade artifact CSVs under `artifacts/recognition_upgrade/` for exact raw-video usage where available.

## Manifest Summary

- Manifest rows: `824`.
- Source rows: ASL Citizen `275`, local supplementary `549`.
- Classification counts: Accepted `338`, Manual review required `486`, Rejected `0`.
- Exact duplicate groups: `0`.

The accepted rows are local supplementary rows that passed automated lineage/file/label/sidecar/hand-hit checks without quality warnings. ASL Citizen rows are lineage-valid but marked manual-review-required because they do not include AppHear sidecar quality metrics in this raw manifest.

## Recalculated Gaps

| Sign | Accepted Now | Accepted Local | Accepted Local Signers | Gap Now Total/Local/Signers | Potential After Review | Gap After Review Total/Local/Signers |
|---|---:|---:|---:|---|---:|---|
| `GOOD` | 44 | 44 | 2 | 106 / 31 / 3 | 140 | 10 / 0 / 2 |
| `HELLO` | 84 | 84 | 2 | 66 / 0 / 3 | 182 | 0 / 0 / 2 |
| `SORRY` | 48 | 48 | 2 | 102 / 27 / 3 | 140 | 10 / 0 / 2 |
| `HAVE` | 44 | 44 | 2 | 106 / 31 / 3 | 80 | 70 / 25 / 3 |
| `KNOW` | 43 | 43 | 2 | 107 / 32 / 3 | 81 | 69 / 25 / 3 |
| `THINK` | 18 | 18 | 1 | 132 / 57 / 4 | 51 | 99 / 55 / 4 |
| `TAKE` | 20 | 20 | 1 | 130 / 55 / 4 | 50 | 100 / 55 / 4 |
| `SELL` | 19 | 19 | 1 | 131 / 56 / 4 | 49 | 101 / 55 / 4 |

Aggregate gap using only accepted rows now:

- Remaining total clip gap: `880`.
- Remaining local clip gap: `289`.
- Remaining local signer-slot gap: `27`.

Best-case aggregate gap if all manual-review rows are approved:

- Remaining total clip gap: `459`.
- Remaining local clip gap: `215`.
- Remaining local signer-slot gap: `24`.

These numbers replace the previous rough estimates. They are still not modeling authorization because manual-review rows must be adjudicated before training.

## Vocabulary Reassessment

| Sign | Recommendation | Reason |
|---|---|---|
| `GOOD` | Keep | Product value and prior GOOD/SORRY evidence; remains confusion-sensitive and needs review/fresh split. |
| `HELLO` | Keep | Product value and enough potential supplementary rows; still needs HELLO-like no-sign protection and fresh signers. |
| `SORRY` | Keep | Product value and binary landmark evidence; broader-context confusion means no promotion without clean baseline. |
| `HAVE` | Keep | Product-useful, but data remains limited; needs more local signers/clips. |
| `KNOW` | Keep | Product-useful, but E5 regression and limited local diversity require clean baseline. |
| `THINK` | Keep | Strong prior reduced-vocabulary evidence; data gap is mainly local signer diversity. |
| `TAKE` | Keep | Strong prior reduced-vocabulary evidence; data gap is mainly local signer diversity. |
| `SELL` | Keep | Useful evidence-backed sign; data gap is mainly local signer diversity. |
| `WASH2` | Control only | Strong control/reserve sign; not part of first product-core vocabulary. |

No selected sign is ready for training solely from accepted rows. `HELLO` is the only sign whose total/local clip gaps could be satisfied after manual review, but it still lacks enough accepted local signers.

## Remaining Collection Work

If manual review approves all review-required rows, the remaining positive collection workload is:

- `GOOD`: total clips `10`, local clips `0`, local signer slots `2`.
- `HELLO`: total clips `0`, local clips `0`, local signer slots `2`.
- `SORRY`: total clips `10`, local clips `0`, local signer slots `2`.
- `HAVE`: total clips `70`, local clips `25`, local signer slots `3`.
- `KNOW`: total clips `69`, local clips `25`, local signer slots `3`.
- `THINK`: total clips `99`, local clips `55`, local signer slots `4`.
- `TAKE`: total clips `100`, local clips `55`, local signer slots `4`.
- `SELL`: total clips `101`, local clips `55`, local signer slots `4`.

Additional required negative/context data remains unchanged for this phase:

- `1,000` reviewed no-sign/OOV/transition windows still need to be integrated into a canonical manifest.
- Include no-hand, idle hands, face-adjacent non-signing, accidental motion, unsupported signs, transitions, partial signs, and fresh held-out signers.

## Decision

**More data is required.**

Do not start feature extraction or model training yet. The next data step should be manual review/adjudication of the `Manual review required` rows in `canonical_product_core_manifest.csv`, especially local supplementary rows with quality warnings and ASL Citizen rows missing sidecar quality metrics. After that, collect only the remaining signer/clip gaps shown in `recalculated_data_gaps.csv`.

The first future model experiment must be a clean v3.0 `[96,258]` baseline using the repaired dataset. Richer landmarks, prototype rejection, specialists, and RGB remain blocked until that baseline produces trustworthy results.

## Architecture Decisions

- Raw videos are now the source of truth for the selected product-core lineage pass.
- Existing `.npz` row indexes are not authoritative.
- Local stale paths from the supplementary audit were repaired to current `E:/local` paths in the manifest.
- Prior exact raw-video usage is recorded where artifact CSVs exposed `video_path`/`raw_video_path`; class-level `.npz` usage is recorded only as inferred usage.
- Accepted rows are not automatically assigned to train/val/test; signer-disjoint split assignment remains a later data step.

## Assumptions

- Automated acceptance is intentionally conservative and does not replace visual/sign-language review.
- `hand_hit_rate >= 0.5` is a data-quality filter for this audit, not a final modeling threshold.
- Sidecar signer IDs are reliable enough for grouping, but not proof of real-world identity.

## Open Questions

- Which reviewer will adjudicate ASL Citizen quality and selected local quality-warning rows?
- Should ASL Citizen rows get a lightweight visual/landmark-quality review before split assignment?
- Which fresh local signers are available for the remaining signer-slot gaps?

## Risks

- Approving all manual-review rows without review can reintroduce low-visibility, low-motion, or variant errors.
- Training on local supplementary clips as validation/test would leak previous E4/E5 decisions for some signs.
- Signer diversity remains the largest remaining positive-data weakness.