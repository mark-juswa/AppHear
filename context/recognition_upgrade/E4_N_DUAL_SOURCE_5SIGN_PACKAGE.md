# E4-N Dual-Source 5-Sign Training Screen Package

**Purpose:** Document the bounded E4-N package that tests whether E4-M candidates `HAVE` and `KNOW` can be added to the reliable local core `GOOD`/`HELLO`/`SORRY` without breaking held-out performance.

**Scope:** Experiment-only dataset assembly, smoke validation, training handoff, source-aware metric reporting, and go/no-go criteria. No Android files, TFLite exports, production recognizer assets, source videos, or source datasets are modified.

**Current status:** PREPARED / SMOKE PASS / FULL TRAINING NOT STARTED.

**Last updated:** 2026-07-30.

## Verified Project References

- Runner: `pipeline/rgb/e4_n_dual_source_5sign.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_n_dual_source_5sign_screen_01`.
- Core source: `artifacts/recognition_upgrade/e4_generalization/e4_j_reliable_core_3sign_pilot_01/dataset/landmark_features.npz`.
- E4-M source: `artifacts/recognition_upgrade/e4_generalization/e4_m_dual_source_candidate_screen_01`.
- ASL Citizen source: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational`.
- Local feature source: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_recorded_local_pc_236\recorded.npz`.

## Package Contents

- `pilot_config.json` records the fixed 5-class contract, source roots, split counts, gate, warnings, and known limitations.
- `pilot_manifest.csv` records every row with `source_id`, split, gloss, class id, participant id, source index, and source path.
- `selected_classes.csv` fixes class order: `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`.
- `dataset/landmark_features.npz` contains `[271,96,258]` schema 3.0 features plus `source_ids`.
- `dataset/source_metadata.npz` stores source/sample/participant metadata separately for source-aware checks.
- `smoke/smoke_summary.json` confirms model creation, forward pass, one training batch, and smoke weights.
- `README_RUN.md` contains user-run commands.

## Dataset Assembly

E4-N assembled 271 rows without MediaPipe extraction:

- `local_core_e4j`: 190 rows for `GOOD`/`HELLO`/`SORRY` copied from E4-J.
- `asl_citizen_train`: 24 rows for `HAVE`/`KNOW`.
- `asl_citizen_val`: 8 rows for `HAVE`/`KNOW`.
- `asl_citizen_test`: 23 rows for `HAVE`/`KNOW`.
- `local_recorded_features`: 26 rows for `HAVE`/`KNOW` from the reusable local 236-class tensor.

Split counts are `train=116`, `val=37`, `test=118`. Test counts are balanced for the core signs at 30 each, and candidate test counts are `HAVE=14`, `KNOW=14` after combining ASL Citizen and local candidate test rows.

## Known Limitation

`KNOW` has only one generated local held-out row in the reusable local feature tensor. Therefore local-source `KNOW` accuracy is diagnostic; the stronger held-out evidence for `KNOW` comes from ASL Citizen test rows. This limitation is explicitly recorded in `pilot_config.json` and must be mentioned when interpreting results.

## Validation Completed

- Syntax compile passed: `python -m py_compile pipeline\rgb\e4_n_dual_source_5sign.py`.
- Prepare passed and assembled `[271,96,258]`.
- Smoke passed with `conv1d_baseline`, forward shape `[10,5]`, one train batch, and smoke weights saved.
- Structural check passed with `--require-full-dataset`.

## User-Run Commands

Run full training:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_n_dual_source_5sign run --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_n_dual_source_5sign_screen_01"
```

Resume if interrupted:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_n_dual_source_5sign run --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_n_dual_source_5sign_screen_01" --resume
```

Check after training:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_n_dual_source_5sign check --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_n_dual_source_5sign_screen_01" --require-full-dataset --require-metrics
```

## Gate

E4-N is a go only if all of these hold:

- Latest Conv1D mean test accuracy is at least `0.85`.
- Every core class `GOOD`/`HELLO`/`SORRY` stays at least `0.90` on test.
- Candidate classes `HAVE` and `KNOW` stay at least `0.70` on combined held-out test.
- Source-aware metrics do not show that success comes from one source while the other collapses.
- No Android integration, TFLite export, or production replacement occurs from this package alone.

## Architecture Decisions

- E4-N uses `conv1d_baseline` only, following E4-K fixed/latest checkpoint policy. Earlier E4-J showed this was more stable than TCN for the tiny reliable-core expansion path.
- E4-N does not extract `GET`/`WELCOME2`. Those remain queued until the system proves it can add `HAVE`/`KNOW` without damaging the core.
- E4-N keeps source provenance explicit instead of blindly merging ASL Citizen and local supplementary rows.

## Assumptions

- Existing ASL Citizen and local feature tensors use schema 3.0-compatible `[96,258]` features.
- E4-J core rows remain the best available local reliable-core control.
- E4-M candidate ranking remains the source of truth for why `HAVE` and `KNOW` were selected.

## Open Questions

- Can `HAVE` and `KNOW` generalize across mixed source provenance without damaging the core?
- Does the local `KNOW` limitation require immediate feature extraction from validated raw local `KNOW` videos?
- If E4-N passes, should the next step be `GET`/`WELCOME2` extraction or a stricter source-balanced collection round?

## Risks

- Source/provenance mismatch may dominate over class signal.
- The core may regress because candidates are drawn from different datasets.
- Local `KNOW` evidence is too thin for a production claim.
- Validation may look acceptable while source-aware test results reveal collapse.

## Next Required Action

The developer should run the E4-N full training command, then run the check command and provide the metrics output for analysis. Do not start Android integration, model export, `GET`/`WELCOME2` extraction, or larger vocabulary expansion until E4-N is evaluated.