# E6 Collection Integration Result

**Purpose:** Record canonical lineage integration of the reviewed historical product-core data,
new controlled captures, and the reviewed E2e-C0 N0 footage.

**Scope:** Dataset lineage, technical QC, deduplication, review sampling, and provisional split
assessment only. No landmark/feature extraction, model training, schema change, TFLite export,
Android change, or production recognizer replacement was performed.

**Current status:** INTEGRATED / REVIEW PASSED / DATA-READINESS GATE STILL BLOCKED.

**Last updated:** 2026-08-05.

## Verified Run

- Builder: `pipeline/rgb/e6_collection_integrate.py`.
- Integration run: `artifacts/recognition_upgrade/product_core_data_readiness/e6_collection_integration_01`.
- Spot-review run: `artifacts/recognition_upgrade/product_core_data_readiness/e6_collection_spot_review_01`.
- Manifest version: `apphear_dataset_manifest_v1`.
- Integrated rows: `1,956` (`773` historical, `1,126` presented new positives, `57` N0 clips).
- Lineage check: passed with `0` missing/hash/decode rows.
- Proposed signer split leakage check: passed with `0` leakage groups.
- Utility tests: 5 passed in tests/test_e6_collection_integrate.py.

## Signer Identity And Duplicate Finding

Recorder filename identity is authoritative over a temporary `P_NEWxx` folder name when present.
The genuine new recorder signers are `6CC240-S001`, `87AF81-S001`, and `8A128E-S001`.

The folder named `P_NEW04` contains signer `3B96F6-S001`, which already exists in the local
supplementary lineage. Its 20 `THINK`, 20 `TAKE`, and 20 `SELL` videos are byte-identical copies of
existing local videos. The 60 copied rows are excluded from counts and splits; canonical local rows
are retained. No files were deleted.

## Provisional Positive Readiness

The completed bounded review accepted all sampled clips; the non-duplicate captures are now verified candidates under the batch-review policy.

| Sign | Candidate total | Candidate local | Total signers | Local signers | Strict result |
|---|---:|---:|---:|---:|---|
| `GOOD` | 254 | 223 | 35 | 5 | Pass |
| `HELLO` | 331 | 299 | 35 | 6 | Pass |
| `SORRY` | 218 | 188 | 34 | 6 | Pass |
| `HAVE` | 200 | 170 | 33 | 4 | Fail strict; provisional four-local-signer exception accepted |
| `KNOW` | 224 | 200 | 27 | 5 | Pass |
| `THINK` | 127 | 96 | 30 | 3 | Fail: 23 clips and 2 local signer slots short |
| `TAKE` | 129 | 100 | 31 | 3 | Fail: 21 clips and 2 local signer slots short |
| `SELL` | 199 | 170 | 32 | 4 | Fail: 1 local signer slot short |

The earlier apparent `147` THINK and `149` TAKE counts included copied P_NEW04 rows and are not
valid. The corrected figures above are source-of-truth.

## Bounded Spot Review

The package selected first/middle/last clips from every genuine sign-signer batch rather than
requiring review of all 1,066 non-duplicate candidates.

- Review rows: 63 across 21 sign-signer groups.
- Completion: 63/63.
- Verdict: every sampled clip was accepted; 21/21 batches passed.
- No expanded review is required now.
- This validates batch-level technical and label acceptance; it does not prove model accuracy.

## N0 Reuse Decision

`scratchpad/e2e_c0_capture/raw/n0` is accepted as development/training source evidence:

- 57 raw clips, six participants, five devices, five environments.
- 613 reviewed eligible no-visible-hand frames.
- 50 clips have no contamination in the deterministic 1 FPS audit; seven contaminated clips are
  excluded from automatic development use.

N0 is not fresh evaluation data because E2e-C0 and E4 already used it. It covers only
`N0_NO_HAND`; it does not cover idle visible hands, face-adjacent activity, accidental motion, OOV
signs, or transition/partial signs. Those missing categories retain an engineering target of 850
windows. Reviewed frames are evidence, not materialized `[96,258]` windows.

### Subsequent P1 Reuse Audit

`E6_NEGATIVE_REUSE_AUDIT_RESULT.md` supersedes the pre-audit 850-window estimate without changing
this integration run's historical output. It proves the E4-AG raw videos are aliases of the same 30
P1 videos and identifies 197 unique reviewed development windows: 143 idle-hand and 54
face-adjacent. Combined historical credit is now 347/1,000, leaving a 653-window volume gap and no
fresh-evaluation coverage.

## Gate Decision

Structural package check: **pass**. Overall data readiness: **blocked**.

Blocking conditions:

1. Resolve or explicitly defer THINK, TAKE, and SELL before baseline modeling.
2. Add or validly reuse visible-hand no-sign, OOV, and transition/partial coverage.
3. Preserve fresh evaluation data; historical N0 cannot be the final test set.

The HAVE exception is allowed for a bounded baseline, but HAVE cannot independently support a
production signer-generalization claim. No equivalent exception is approved for THINK, TAKE, or
SELL.

## Source-Of-Truth Outputs

- `manifest.csv`, `manifest.schema.json`, `manifest_summary.json`
- `lineage_audit.csv`, `split_audit.csv`, `label_audit.csv`
- `positive_readiness_by_sign.csv`, `n0_reviewed_frame_evidence.csv`
- `manual_review_queue.csv`, `readiness_gate.json`

## Protected Baseline And Next Action

No Android, production model/config/vocabulary, schema-v3.0 feature code, or historical raw data was
modified. Do not repeat the completed spot review or P1/E4-AG reuse audit. Search other existing sources for independent accidental-motion, OOV, transition/partial, idle-hand, and face-adjacent footage before requesting more recording. Extraction and modeling remain blocked.


