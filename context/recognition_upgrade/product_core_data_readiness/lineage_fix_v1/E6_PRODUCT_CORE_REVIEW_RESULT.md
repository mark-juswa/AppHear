# E6 Product-Core Review Result

**Purpose:** Record completed human review/adjudication of manual-review rows from the product-core raw-video lineage manifest.

**Scope:** Review and data-readiness only. No feature extraction, model training, schema change, RGB, specialists, TFLite export, Android change, or production recognizer replacement was performed.

**Current status:** COMPLETE / MORE DATA REQUIRED BEFORE BASELINE TRAINING.

**Last updated:** 2026-08-03.

## Verified Run

- Review run: `artifacts/recognition_upgrade/product_core_data_readiness/e6_product_core_review_01`.
- Review manifest: `artifacts/recognition_upgrade/product_core_data_readiness/e6_product_core_review_01/review_manifest.csv`.
- Summary: `artifacts/recognition_upgrade/product_core_data_readiness/e6_product_core_review_01/reports/review_summary.json`.
- Gap table: `artifacts/recognition_upgrade/product_core_data_readiness/e6_product_core_review_01/reports/post_review_gap_summary.csv`.
- Completion check: passed with `486/486` rows reviewed and `0` errors.

## Review Summary

- Rows reviewed: `486`.
- Accepted: `329`.
- Rejected: `157`.
- Needs expert / diagnostic rows: `0`.

Decision reasons:

- `accepted_by_manual_review`: `222`
- `incomplete_or_partial_sign`: `148`
- `low_motion_but_valid_sign`: `107`
- `bad_visibility_framing_or_quality`: `9`

## Final Accepted Counts And Gaps

| Sign | Accepted Total | Accepted Local | Total Signers | Local Signers | Remaining Total Gap | Remaining Local Gap | Remaining Local Signer Gap | Rejected/Diagnostic |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `GOOD` | 81 | 50 | 32 | 2 | 69 | 25 | 3 | 59 |
| `HELLO` | 151 | 119 | 32 | 3 | 0 | 0 | 2 | 31 |
| `SORRY` | 81 | 51 | 31 | 3 | 69 | 24 | 2 | 59 |
| `HAVE` | 80 | 50 | 31 | 2 | 70 | 25 | 3 | 0 |
| `KNOW` | 74 | 50 | 24 | 2 | 76 | 25 | 3 | 7 |
| `THINK` | 51 | 20 | 28 | 1 | 99 | 55 | 4 | 0 |
| `TAKE` | 49 | 20 | 29 | 1 | 101 | 55 | 4 | 1 |
| `SELL` | 49 | 20 | 29 | 1 | 101 | 55 | 4 | 0 |

Aggregate remaining gaps after review:

- Total clip gap: `585`.
- Local/app-domain clip gap: `264`.
- Local signer-slot gap: `25`.
- No-sign/OOV/transition gap remains `1,000` reviewed windows because this review covered positive product-core/control clips only.

## Interpretation

- `HELLO` is the only selected sign that reaches the `150` total clip target after review, but it still has only `3` local signers and therefore fails the local-signer gate.
- `GOOD`, `SORRY`, `HAVE`, and `KNOW` have useful data but still need many total/local clips and more local signers.
- `THINK`, `TAKE`, and `SELL` remain especially local-data limited: each has only `20` or fewer local accepted clips and only `1` local signer.
- The largest failure pattern from review was incomplete/partial signing, especially in local supplementary rows for `GOOD` and `SORRY`.
- The selected vocabulary remains valid for now, but no sign is ready for a training-grade signer-disjoint baseline dataset yet.

## Vocabulary Decision

- Keep `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`, `THINK`, `TAKE`, and `SELL` as the product-core data-readiness vocabulary.
- Keep `WASH2` as control only. It was not part of the accepted-gap summary because it is not product-core v0.
- Do not add more signs until these selected signs meet lineage, count, signer, split, and no-sign/OOV gates.

## Remaining Collection Checklist

- `GOOD`: collect at least `69` more accepted total clips, `25` more accepted local clips, and `3` local signer slots.
- `HELLO`: collect at least `0` more accepted total clips, `0` more accepted local clips, and `2` local signer slots.
- `SORRY`: collect at least `69` more accepted total clips, `24` more accepted local clips, and `2` local signer slots.
- `HAVE`: collect at least `70` more accepted total clips, `25` more accepted local clips, and `3` local signer slots.
- `KNOW`: collect at least `76` more accepted total clips, `25` more accepted local clips, and `3` local signer slots.
- `THINK`: collect at least `99` more accepted total clips, `55` more accepted local clips, and `4` local signer slots.
- `TAKE`: collect at least `101` more accepted total clips, `55` more accepted local clips, and `4` local signer slots.
- `SELL`: collect at least `101` more accepted total clips, `55` more accepted local clips, and `4` local signer slots.
- Collect and review `1,000` no-sign/OOV/transition windows with subtype coverage: no-hand, idle hands, face-adjacent non-signing, accidental motion, unsupported signs, transitions, and partial signs.
- Use completely fresh held-out local signers for validation/test assignment; do not use previously reviewed local clips as the fresh test set.

## Final Decision

**More data is required.**

Do not start feature extraction or model training. The next concrete work is targeted recording/collection to fill the sign-specific gaps above and to build the no-sign/OOV/transition manifest. The first future model experiment remains a clean v3.0 `[96,258]` baseline only after the data gates pass.

## Architecture Decisions

- Completed human review decisions supersede the earlier potential-after-review estimates.
- Accepted clips are not automatically split into train/val/test; signer-disjoint split construction remains blocked until data gaps are filled.
- Richer landmarks, prototype rejection, specialists, and RGB remain blocked.

## Risks

- Collecting only more clips from the same local signers will not satisfy the signer-independent gate.
- Reducing the signer target would speed progress but weaken the evidence and risk repeating E4/E5 failures.
- Training before no-sign/OOV/transition data is added would ignore the previous routed/open-set failures.