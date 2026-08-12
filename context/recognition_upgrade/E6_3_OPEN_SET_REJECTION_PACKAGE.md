# E6-3 Frozen-Embedding Rejection Package

**Purpose:** Record the implemented offline package, smoke evidence, and user-run handoff for the
approved E6-3 rejection comparison.

**Scope:** Offline extraction and scoring only. No model training, feature-schema change, RGB,
specialist, export, Android change, or production migration.

**Current status:** PREPARED / REAL-DATA SMOKE PASS / FULL NEGATIVE EXTRACTION PENDING.

**Last updated:** 2026-08-09.

## Implemented Package

- Runner: `pipeline/rgb/e6_3_open_set_rejection.py`.
- Tests: `tests/test_e6_3_open_set_rejection.py`.
- Run: `artifacts/recognition_upgrade/e6_rejection/e6_3_frozen_embedding_01`.
- Commands: `prepare`, `smoke`, `extract-negatives`, `evaluate`, and `check`.
- Frozen checkpoints: latest seeds `101`, `202`, and `303` from the repaired-validation v3.0 run.
- Candidate: masked-mean `tcn3_add` embedding plus predicted-class OAS-Mahalanobis score.
- Controls: maximum softmax probability and fixed-temperature energy.

## Verified Preparation

- Assignment hash: `466305B197C039A98EF39FFF7CDDC43CBB33FD317C6B39CE7488354ABCCB10D0`.
- Assigned negatives: `1,107` total, comprising `547` historical development negatives and `560`
  one-signer provisional fresh negatives.
- Negative subtypes: N0 no-hand `150`, OOV sign `520`, idle hands `203`, face-adjacent `114`,
  accidental motion `60`, transition/partial `60`.
- Frozen checkpoint hashes are recorded in `config/experiment.json`.
- Unit tests for causal window bounds, masked pooling, and Mahalanobis direction passed.

## Real-Data Smoke Result

The smoke extracted nine real examples covering every available role/subtype combination and
passed:

- completed windows: `9/9`;
- first run extraction time: approximately `107.1 s` for nine distinct videos;
- cached rerun time: approximately `0.26 s` for extraction;
- frozen embedding shape: `[20,64]`;
- frozen probability shape: `[20,5]`;
- probability normalization: pass;
- OAS shrinkage: `0.467724` on the bounded smoke subset;
- finite Mahalanobis scores: pass;
- projected float32 means/covariance size: `17,664` bytes;
- structural check with required smoke: pass.

MediaPipe Clearcut connection warnings are non-fatal telemetry failures; the smoke artifacts and
checks passed.

## User-Run Commands

From `F:\ASL DATASET\5. Apphear3`:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_3_open_set_rejection extract-negatives `
  --run-dir "artifacts\recognition_upgrade\e6_rejection\e6_3_frozen_embedding_01"
```

This long step completed in approximately `6,502.1 s` (`1 h 48 min`) and processed `1,107`
windows from `804` distinct videos. The earlier pre-run estimate of `707` videos was incorrect;
`804` is the verified canonical-manifest count. Reruns remain resumable through completed per-video
Stage-E caches and per-window tensors.

After extraction passes:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_3_open_set_rejection evaluate `
  --run-dir "artifacts\recognition_upgrade\e6_rejection\e6_3_frozen_embedding_01"

.\.venv\Scripts\python.exe -m pipeline.rgb.e6_3_open_set_rejection check `
  --run-dir "artifacts\recognition_upgrade\e6_rejection\e6_3_frozen_embedding_01" `
  --require-smoke `
  --require-metrics
```

`evaluate` performs frozen forward passes and score calibration; it does not train a model.

## Verified Full Extraction

- attempted/completed windows: `1,107/1,107`;
- unique assignment IDs: `1,107`;
- unique videos and Stage-E caches: `804`;
- missing feature files: `0`;
- invalid lengths, tensor shapes, non-finite values, mask counts, or padded-frame values: `0`;
- zero-hand-feature windows retained as honest negative evidence: `152`;
- extraction errors: `0`;
- result: pass.

## Expected Outputs

- `dataset/stage_e_cache/`: resumable per-video MediaPipe data.
- `dataset/per_window/`: isolated v3.0 negative windows.
- `dataset/negative_window_manifest.csv`: exact lineage and window boundaries.
- `logs/negative_extraction_summary.json`: completeness, subtype counts, timing, and errors.
- `metrics/seed_*_mahalanobis_parameters.npz`: experiment-only class means/covariance.
- `metrics/metrics.json`: all method/seed results and strict gate decision.
- `check_report.json`: package completeness check.

All generated files remain under the E6-3 run directory.

## Limitations

- Fresh negatives have one signer and short-event clips.
- Fresh/stress positive sets have already been inspected in earlier phases.
- A diagnostic pass cannot authorize production or Android.
- Rejection can suppress an unsafe result but cannot correct an accepted wrong label.

## Source-Of-Truth Files

- `E6_3_OPEN_SET_REJECTION_PLAN.md`
- `pipeline/rgb/e6_3_open_set_rejection.py`
- `tests/test_e6_3_open_set_rejection.py`
- `artifacts/recognition_upgrade/e6_rejection/e6_3_frozen_embedding_01/config/experiment.json`
- `artifacts/recognition_upgrade/e6_rejection/e6_3_frozen_embedding_01/smoke/smoke_summary.json`

## Related Context Files

- `E6_2_LANDMARK_GEOMETRY_RESULT.md`
- `E6_PRODUCTION_RECOGNITION_ARCHITECTURE_PLAN.md`
- `EXPERIMENT_MATRIX.md`
- `EVALUATION_AND_ACCEPTANCE_GATES.md`
- `RISK_REGISTER.md`
- `ROLLBACK_AND_COMPATIBILITY_PLAN.md`

## Architecture Decisions

- Frozen v3.0 remains the primary classifier and is never rewritten by this package.
- E6-3 introduces no learned rejector parameters.
- Threshold selection remains development-only.
- All E6-4+ work remains blocked until full E6-3 metrics are reviewed.

## Assumptions And Open Questions

- Full extraction will preserve the structural counts verified at preparation.
- It remains unknown whether Mahalanobis can reject stress `KNOW -> HELLO` without losing useful
  supported-sign coverage.

## Next Required Action

Negative extraction is complete. Run `evaluate`, then the strict `check`. Analyze the complete
metrics before authorizing E6-4 or any alternative rejection method.
