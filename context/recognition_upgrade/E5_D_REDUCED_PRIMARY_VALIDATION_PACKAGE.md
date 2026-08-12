# E5-D Reduced Primary Validation Package

**Purpose:** Validate whether the E5-C reduced-primary vocabulary performs better than the E5-B 50-class diagnostic while keeping known hard/confusion signs out of the primary recognizer.

**Scope:** Offline landmark-only experiment package. No MediaPipe extraction, Android integration, TFLite export, production recognizer replacement, source dataset mutation, or runtime behavior change.

**Current status:** PREPARED / DATASET CHECK PASS / SMOKE PASS / USER FULL TRAINING NEXT.

**Last updated:** 2026-08-03.

## Verified Project References

- Runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e5_d_reduced_primary_validation.py`
- Source E5-C run: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_c_50class_tiering_01`
- E5-D run directory: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_d_reduced_primary_15sign_01`
- Dataset tensor: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_d_reduced_primary_15sign_01\dataset\landmark_features.npz`
- Run guide: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_d_reduced_primary_15sign_01\README_RUN.md`
- Smoke summary: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_d_reduced_primary_15sign_01\smoke\smoke_summary.json`
- Check report: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_d_reduced_primary_15sign_01\check_report.json`

## Selected Vocabulary

E5-D uses the E5-C reduced-primary hypothesis:

`WASH2`, `TAKE`, `MEET`, `HAVE`, `WANT2`, `WORK`, `GOOD`, `MORNING`, `STAND2`, `SELL`, `THINK`, `DRIVE`, `RUN2`, `USE`, `SLEEP`.

`HELLO` and `KNOW` are intentionally excluded because E5-C showed they regressed in the 50-class context and were primarily confused as `SEEM`.

`SORRY` remains outside the primary model and should be evaluated later through the existing GOOD/SORRY landmark specialist route.

## Dataset Summary

- Shape: `[695,96,258]`
- Schema: `3.0`
- Class count: `15`
- Train/validation/test rows: `483/49/163`
- Sources: `422` ASL Citizen rows, `273` local supplementary rows
- No new MediaPipe extraction was performed.

## Smoke Result

Smoke passed locally:

- Loaded the reduced dataset tensor.
- Built `conv1d_baseline`.
- Ran one forward pass with output shape `[32,15]`.
- Ran one training step.
- Saved smoke weights under the run directory.

Structural check passed with `--require-dataset --require-full-dataset`.

## Full Training Command

The user should run full training:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e5_d_reduced_primary_validation run --run-dir "artifacts\recognition_upgrade\e5_batch_screening\e5_d_reduced_primary_15sign_01"
```

Resume if interrupted:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e5_d_reduced_primary_validation run --run-dir "artifacts\recognition_upgrade\e5_batch_screening\e5_d_reduced_primary_15sign_01" --resume
```

Check after training:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e5_d_reduced_primary_validation check --run-dir "artifacts\recognition_upgrade\e5_batch_screening\e5_d_reduced_primary_15sign_01" --require-dataset --require-full-dataset --require-metrics
```

## Evaluation Purpose

E5-D answers whether reducing the primary vocabulary improves reliability enough to continue the landmark-primary path.

Compare E5-D against E5-B:

- E5-B mean latest test accuracy: `0.4897`
- E5-D should materially improve mean test accuracy.
- E5-D should avoid class collapse.
- `GOOD` and `HAVE` should remain strong.
- Weak signs should be identified before any routed/no-sign integration.

## Go / No-Go Criteria

Go if:

- Mean latest test accuracy improves materially over E5-B.
- Minimum per-class results are acceptable for most selected signs.
- No dominant-class prediction collapse appears.
- `GOOD` and `HAVE` do not degrade.
- The result gives a credible small primary vocabulary for later routed-system validation.

No-go if:

- The E5-B confusion pattern persists even after reduction.
- Guarded signs collapse or dominate false predictions.
- Aggregate accuracy improves but multiple classes still fail badly.
- A smaller primary set is needed before adding the no-sign gate and `SORRY` specialist.

## Next Required Action

Run E5-D full training, then check and analyze metrics before any further architecture or Android decision.
