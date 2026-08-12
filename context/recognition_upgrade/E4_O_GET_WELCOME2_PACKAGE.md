# E4-O GET/WELCOME2 7-Sign Expansion Package

**Purpose:** Document the E4-O package that follows the E4-N gate pass by adding the next queued E4-M candidates: `GET` and `WELCOME2`.

**Scope:** Experiment-only local feature extraction, source-aware 7-sign dataset assembly, Conv1D training handoff, and evaluation gates. No Android files, TFLite exports, production recognizer assets, source videos, or source datasets are modified.

**Current status:** PREPARED / TWO-ROW EXTRACTION SMOKE PASS / MODEL SMOKE PASS / FULL EXTRACTION AND TRAINING NOT STARTED.

**Last updated:** 2026-07-30.

## Verified Artifacts

- Runner: `pipeline/rgb/e4_o_get_welcome2_expansion.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_o_get_welcome2_7sign_screen_01`.
- Base run: `artifacts/recognition_upgrade/e4_generalization/e4_n_dual_source_5sign_screen_01`.
- Local validation source: `artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_validation_01/validated_clip_inventory.csv`.
- ASL Citizen source: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational`.

## Package Structure

- `pilot_config.json`: fixed 7-class contract, source roots, gate, and long-step warnings.
- `pilot_manifest.csv`: conventional manifest used by shared checks.
- `pilot_manifest_base_plus_asl.csv`: base E4-N rows plus ASL Citizen `GET`/`WELCOME2` feature rows.
- `candidate_manifest.csv`: 140 local validated `GET`/`WELCOME2` videos queued for MediaPipe extraction.
- `dataset/base_plus_asl_features.npz`: reusable features before local candidate extraction.
- `dataset/per_clip_local_candidates/`: extracted local `GET`/`WELCOME2` per-clip feature files.
- `dataset/landmark_features.npz`: assembled training tensor after extraction. Currently partial from the two-row smoke.
- `README_RUN.md`: developer-run commands.

## Dataset Scope

E4-O starts from the E4-N 5-sign dataset and adds:

- ASL Citizen existing feature rows for `GET` and `WELCOME2`.
- 140 local validated videos queued for `GET` and `WELCOME2` extraction.

After prepare, before full local extraction:

- Base plus ASL rows: `328`.
- Local candidate rows pending extraction: `140`.
- Classes: `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`, `GET`, `WELCOME2`.
- Random baseline: `0.1429`.

A two-row extraction smoke has already run and created a partial `[330,96,258]` tensor with `138` local candidate rows still missing. The developer must run full extraction with `--require-full` before training.

## Validation Completed

- Python compile passed.
- Prepare passed.
- Two-row local extraction smoke passed: 2/2 rows extracted, 0 failures.
- Model smoke passed: `conv1d_baseline`, forward shape `[10,7]`, one train batch, smoke weights saved.
- Structural check passed with `--require-dataset`.

## User-Run Commands

Full local candidate extraction:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_o_get_welcome2_expansion extract-candidates --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_o_get_welcome2_7sign_screen_01" --require-full
```

Smoke after full extraction:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_o_get_welcome2_expansion smoke --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_o_get_welcome2_7sign_screen_01"
```

Full training:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_o_get_welcome2_expansion run --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_o_get_welcome2_7sign_screen_01"
```

Resume if interrupted:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_o_get_welcome2_expansion run --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_o_get_welcome2_7sign_screen_01" --resume
```

Final check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_o_get_welcome2_expansion check --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_o_get_welcome2_7sign_screen_01" --require-full-dataset --require-metrics
```

## Gate

E4-O is a go only if all hold:

- Mean latest test accuracy is at least `0.80`.
- Every core class `GOOD`/`HELLO`/`SORRY` stays at least `0.90`.
- New candidates `GET` and `WELCOME2` stay at least `0.60`.
- Source-aware results do not show collapse on local extracted rows.

If E4-O passes, the next step is not another one-word addition. The next step should be a larger automated source-aware batch screen, likely 20-50 candidate signs. If E4-O fails, inspect whether the failure is extraction quality, source mismatch, or label/variant mismatch before any larger run.

## Next Required Action

The developer should run full E4-O local extraction, smoke, full training, and final check. Do not start Android integration, production export, RGB fusion, or large vocabulary extraction until E4-O is evaluated.