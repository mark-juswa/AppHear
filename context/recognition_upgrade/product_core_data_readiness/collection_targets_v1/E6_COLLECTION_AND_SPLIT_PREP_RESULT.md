# E6 Collection And Split Preparation Result

**Purpose:** Record the targeted collection package and signer-disjoint split dry-run prepared after product-core review.

**Scope:** Collection planning, raw-folder validation, and split feasibility only. No feature extraction, model training, schema change, RGB, specialists, TFLite export, Android change, or production recognizer replacement was performed.

**Current status:** SUPERSEDED BY E6_COLLECTION_INTEGRATION_RESULT / SPLIT GATE BLOCKED.

**Last updated:** 2026-08-05.

The collection is now integrated and deduplicated. See E6_COLLECTION_INTEGRATION_RESULT.md for corrected counts, the P_NEW04 duplicate/signer finding, N0 reuse limits, and the current 63-row spot-review action. The historical preparation result below is retained for provenance.

## Created Targets

- `positive_collection_targets.csv`
- `nosign_oov_transition_targets.csv`
- `collection_target_summary.json`
- `E6_TARGETED_COLLECTION_RUNBOOK.md`

Positive collection target: `605` fresh local/app-domain clips across `25` local signer slots.

| Sign | Clips | New local signer slots |
|---|---:|---:|
| `GOOD` | 69 | 3 |
| `HELLO` | 20 | 2 |
| `SORRY` | 69 | 2 |
| `HAVE` | 70 | 3 |
| `KNOW` | 76 | 3 |
| `THINK` | 99 | 4 |
| `TAKE` | 101 | 4 |
| `SELL` | 101 | 4 |

No-sign/OOV/transition target: `1000` reviewed windows across N0 no-hand, idle hands, face-adjacent, accidental motion, OOV signs, and transition/partial subtypes.

## Created Utilities

- `pipeline/rgb/e6_collection_validate.py`
  - `init`: creates raw recording folder scaffold.
  - `validate`: validates folder structure, decode, hashes/duplicates, and target progress.
- `pipeline/rgb/e6_split_dry_run.py`
  - Checks whether accepted data can support signer-disjoint train/validation/test splits.

## Prepared Folders And Smoke Results

Raw recording scaffold:

`scratchpad/e6_product_core_collection/raw`

Initial validator output:

`artifacts/recognition_upgrade/product_core_data_readiness/e6_collection_validation_01`

Empty validation smoke passed and correctly reports:

- videos found: `0`
- remaining positive clips: `605`
- remaining positive signer slots: `25`
- remaining no-sign/OOV/transition windows: `1000`

## Split Dry-Run Result

Run:

`artifacts/recognition_upgrade/product_core_data_readiness/e6_split_dry_run_01`

Result: `split_gate_blocked_more_data_required`.

- Signs feasible now: `0/8`
- Requirement: `150` total clips, `75` local clips, `5` local signers, and enough total signers for `6/2/2` signer-disjoint train/val/test.
- The current reviewed dataset cannot support a baseline training split without violating the data-readiness gate.

## What Can Proceed While Recordings Are Pending

Allowed:

- Improve validators and manifest reports.
- Prepare baseline v3.0 experiment design without running extraction/training.
- Prepare split assignment logic in dry-run mode only.
- Prepare no-sign/OOV review taxonomy.

Blocked:

- Feature extraction.
- Model training.
- Rejection/specialist/RGB experiments.
- TFLite export.
- Android integration.

## Next Required Action

Collect targeted recordings using `E6_TARGETED_COLLECTION_RUNBOOK.md`, then run:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_collection_validate validate `
  --raw-root "scratchpad\e6_product_core_collectionaw" `
  --output "artifactsecognition_upgrade\product_core_data_readiness\e6_collection_validation_01"
```

After validation and review, rerun the split dry-run. Only if the split gate passes should a clean v3.0 `[96,258]` baseline extraction/training package be prepared.
