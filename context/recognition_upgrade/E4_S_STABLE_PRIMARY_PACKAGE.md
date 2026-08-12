# E4-S Stable-Primary 4-Sign Landmark Package

**Purpose:** Document the prepared E4-S package for training a guarded primary landmark recognizer using only E4-R Tier-A signs.
**Scope:** Offline experiment package only. No Android integration, TFLite export, production model replacement, source dataset mutation, or specialist resolver work is authorized.
**Current status:** COMPLETE / FULL TRAINING PASSED CLOSED-SET GATES / E4-T ROUTER SIMULATION NO-GO FOR SIMPLE THRESHOLDS.
**Last updated:** 2026-08-02.

## Verified Project References

- Runner: `pipeline/rgb/e4_s_stable_primary.py`
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01`
- Source run: `artifacts/recognition_upgrade/e4_generalization/e4_n_dual_source_5sign_screen_01`
- Source result: `context/recognition_upgrade/E4_N_RESULT.md`
- Tiering result: `context/recognition_upgrade/E4_R_STABLE_CANDIDATE_TIERING_RESULT.md`
- Roadmap: `context/recognition_upgrade/DYNAMIC_MIXED_RECOGNITION_ROADMAP.md`
- Feature contract: `context/feature-schema.md`

## Package Contract

E4-S filters the passed E4-N tensor instead of rerunning MediaPipe extraction.

Active primary classes:

- `GOOD`
- `HELLO`
- `HAVE`
- `KNOW`

Withheld OOV/confusion holdout:

- `SORRY`

The active dataset keeps schema `3.0` and shape `[96,258]`. `SORRY` is not deleted; it is saved separately for later router/OOV simulation because E4-P and E4-Q showed it is not safe as a broad-context primary class.

## Prepared Dataset

- Active rows: `221`
- OOV/confusion holdout rows: `50`
- Active split counts: train `101`, validation `32`, test `88`
- Active class counts:
  - Train: `GOOD 15`, `HELLO 45`, `HAVE 23`, `KNOW 18`
  - Validation: `GOOD 5`, `HELLO 15`, `HAVE 6`, `KNOW 6`
  - Test: `GOOD 30`, `HELLO 30`, `HAVE 14`, `KNOW 14`
- Active source counts:
  - `local_core_e4j`: `140`
  - `local_recorded_features`: `26`
  - `asl_citizen_train`: `24`
  - `asl_citizen_test`: `23`
  - `asl_citizen_val`: `8`
- OOV source counts:
  - `local_core_e4j`: `50`

Generated files:

- `pilot_config.json`
- `pilot_manifest.csv`
- `selected_classes.csv`
- `README_RUN.md`
- `dataset/landmark_features.npz`
- `dataset/oov_confusion_holdout.npz`
- `dataset/source_metadata.npz`
- `oov_confusion_holdout_manifest.csv`
- `logs/prepare_summary.json`
- `smoke/smoke_summary.json`
- `check_report.json`

## Training Contract

- Branches: `conv1d_baseline`
- Seeds: `101`, `202`, `303`
- Epochs per run command: `20`
- Batch size: `8`
- Learning rate: `5e-4`
- Checkpoint policy: latest/fixed epoch is the primary decision policy, consistent with E4-K.
- Resume support: rerun `run` with `--resume`.

E4-S deliberately does not include TCN or derived-feature branches. Prior experiments showed the simple Conv1D/latest policy is the strongest stable baseline for this stage; adding model variants here would obscure whether the stable sign set itself is viable.

## Commands

Smoke test already passed locally:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_s_stable_primary smoke --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_s_stable_primary_4sign_01"
```

Structural check already passed locally:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_s_stable_primary check --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_s_stable_primary_4sign_01" --require-full-dataset
```

User-run full training:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_s_stable_primary run --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_s_stable_primary_4sign_01"
```

Resume if interrupted:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_s_stable_primary run --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_s_stable_primary_4sign_01" --resume
```

Final check after training:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_s_stable_primary check --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_s_stable_primary_4sign_01" --require-full-dataset --require-metrics
```


## Completed Training Result

User completed full E4-S training and final structural check passed.

Latest fixed-epoch closed-set test results:

- Seed `101`: test accuracy `0.9886`, weakest class `KNOW 0.9286`
- Seed `202`: test accuracy `0.9886`, weakest class `KNOW 0.9286`
- Seed `303`: test accuracy `0.9773`, weakest class `KNOW 0.9286`
- Mean latest test accuracy: `0.9848`
- Minimum latest seed test accuracy: `0.9773`
- Minimum latest per-class test accuracy across seeds: `0.9286`
- Maximum latest predicted-class share across seeds: `0.3523`

Closed-set interpretation: E4-S passes as a stable 4-sign primary landmark recognizer candidate for `GOOD`, `HELLO`, `HAVE`, and `KNOW`.

OOV/confusion warning: withheld `SORRY` was predicted as `GOOD` for all 30 test rows in all three seeds, with high confidence. This blocked direct deployment and led to E4-T router simulation.
## Acceptance Gate

E4-S is a go only if full training shows:

- Mean latest test accuracy >= `0.90`
- Minimum seed latest test accuracy >= `0.85`
- Minimum per-class latest test accuracy >= `0.85`
- No predicted-class concentration above `0.45`
- Source-aware interpretation does not show the model relying on provenance shortcuts
- OOV/confusion probe on withheld `SORRY` is reviewed before any router threshold is proposed

E4-S authorized E4-T offline router simulation. E4-T has now completed and found simple confidence/margin routing is not enough to reject `SORRY`. This still does not authorize Android export or production replacement.

## Architecture Decisions

- Use E4-R guarded Tier-A signs for the first stable-primary landmark package.
- Preserve schema `3.0` `[96,258]`.
- Exclude `SORRY` from the primary model and keep it as an explicit OOV/confusion holdout.
- Use Conv1D/latest fixed-epoch policy only for this package.
- Defer RGB/specialist work until the primary package and router simulation have evidence.

## Assumptions

- E4-N's prepared feature tensor is valid input evidence because E4-N passed structural and accuracy gates.
- Filtering E4-N is safer and faster than rerunning extraction, because E4-S is testing vocabulary composition and primary stability, not MediaPipe extraction.
- `SORRY` should be treated as a hard/confusing sign until visual specialist or data/variant repair evidence says otherwise.

## Open Questions

- Will removing `SORRY` stabilize the primary classifier under the E4-N dual-source split?
- Will the model over-predict one of the remaining stable classes for withheld `SORRY` with high confidence?
- Does the active dataset still contain source/provenance shortcuts that are hidden by aggregate accuracy?
- What calibrated threshold is needed before the primary model can safely reject OOV/confusing signs?

## Risks

- The active set is small and may overstate readiness for larger vocabulary expansion.
- `HAVE` and `KNOW` still have fewer test rows than `GOOD` and `HELLO`.
- The OOV holdout contains only local-core `SORRY`; it is useful but not a complete unknown/no-sign dataset.
- High E4-S accuracy would not prove continuous signing or sentence-level translation readiness.

## Next Required Action

Prepare a focused `SORRY` specialist/data-repair experiment. Do not start Android export, broad expansion, or production replacement.


