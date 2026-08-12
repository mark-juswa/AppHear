# E4-P Existing-Feature 20-Sign Pressure Test Package

**Purpose:** Define the first larger batch pressure test after E4-O showed that manually adding `GET/WELCOME2` is unsafe.

**Scope:** Offline landmark-only experiment package. It uses existing feature tensors only. No local video extraction, Android integration, TFLite export, production recognizer replacement, source-video mutation, or source-dataset mutation is authorized.

**Current status:** PREPARED / SMOKE PASS / STRUCTURAL CHECK PASS / FULL TRAINING NOT STARTED.

**Last updated:** 2026-07-31.

## Verified Artifacts

- Runner: `pipeline/rgb/e4_p_existing_feature_20sign_pressure.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_p_existing_feature_20sign_pressure_01`.
- Runbook: `artifacts/recognition_upgrade/e4_generalization/e4_p_existing_feature_20sign_pressure_01/README_RUN.md`.
- Config: `artifacts/recognition_upgrade/e4_generalization/e4_p_existing_feature_20sign_pressure_01/pilot_config.json`.
- Dataset: `artifacts/recognition_upgrade/e4_generalization/e4_p_existing_feature_20sign_pressure_01/dataset/landmark_features.npz`.
- Candidate evidence table: `artifacts/recognition_upgrade/e4_generalization/e4_p_existing_feature_20sign_pressure_01/tables/selected_candidate_evidence.csv`.
- Source candidate screen: `artifacts/recognition_upgrade/e4_generalization/e4_m_dual_source_candidate_screen_01`.
- Core source: `artifacts/recognition_upgrade/e4_generalization/e4_j_reliable_core_3sign_pilot_01`.
- ASL Citizen source: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational`.
- Existing local feature source: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_recorded_local_pc_236\recorded.npz`.

## Selected Classes

E4-P uses 20 signs:

`GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`, `WANT2`, `HELP`, `NICE`, `KEEP`, `START`, `MEET`, `CLOSE`, `GIVE`, `TALK1`, `WHAT1`, `CLEAN`, `LEAVE`, `STAND2`, `BECOME`, `WASH2`.

Excluded signs:

- `GET` and `WELCOME2` because E4-O failed, mainly due local extracted `GET` collapse.
- `MAKE` because E4-L failed.
- `BYE`, `NO`, `YES`, and `THANKYOU` because prior E4 evidence marked them unstable/review-needed.

## Dataset Shape

- Active rows: `1174`.
- Input shape: `[96,258]`.
- Class count: `20`.
- Split counts: train `749`, validation `140`, test `285`.
- Source counts: ASL Citizen train `237`, ASL Citizen validation `61`, ASL Citizen test `190`, local core `190`, local recorded features `496`.

## Important Limitations

This is a pressure test, not a production benchmark. Many added candidates have only one local supplementary feature signer. That means local-source evidence is diagnostic, while ASL Citizen held-out signer performance remains the cleaner large-source signal for those signs.

The purpose is to quickly test whether the landmark-only pipeline collapses when vocabulary grows to 20 classes. If it collapses, the next high-value work is not Android integration; it is class selection, source normalization, local signer collection, or architecture change.

## Completed Validation

- Python compile passed.
- Prepare passed.
- Smoke test passed: shape `[24,96,258]`, forward output `[24,20]`, one train batch completed, smoke weights saved.
- Structural check passed with `--require-full-dataset`.

## User-Run Commands

Full training:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_p_existing_feature_20sign_pressure run `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_p_existing_feature_20sign_pressure_01"
```

Resume if interrupted:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_p_existing_feature_20sign_pressure run `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_p_existing_feature_20sign_pressure_01" `
  --resume
```

Final check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_p_existing_feature_20sign_pressure check `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_p_existing_feature_20sign_pressure_01" `
  --require-full-dataset `
  --require-metrics
```

## Gate

E4-P is a go only if all hold:

- Mean latest test accuracy is at least `0.45` against random baseline `0.05`.
- Minimum core-class latest test accuracy is at least `0.80`.
- Minimum candidate latest test accuracy is at least `0.20`.
- Maximum predicted-class share is at most `0.35`, preventing one-class collapse.

Passing this gate would not authorize Android export. It would authorize a more serious larger-batch dataset strategy, probably with source cleanup and targeted local validation for classes that fail.

## Next Required Action

The developer should run E4-P full training and final check. After metrics are available, inspect per-class and source-aware results before deciding whether to build a 20-sign cleaned benchmark, a 50-sign ASL-only ceiling, or a new data collection/extraction pass.
