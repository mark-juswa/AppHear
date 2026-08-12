# E5-B ASL-Led Primary Batch Package

**Purpose:** Prepare the next vocabulary-scale diagnostic using ASL Citizen as the broad primary source and local supplementary data only where available.

**Scope:** Offline landmark-only experiment package. No MediaPipe extraction, Android integration, TFLite export, production recognizer replacement, source dataset mutation, or runtime behavior change.

**Current status:** PREPARED / DATASET CHECK PASS / SMOKE PASS / USER FULL TRAINING NEXT.

**Last updated:** 2026-08-02.

## Verified Project References

- Runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e5_b_asl_led_primary_batch.py`
- Run directory: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_b_asl_led_50_primary_01`
- Source screen: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_a_dual_source_batch_screen_01`
- Combined feature source: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_pc_236`
- Dataset tensor: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_b_asl_led_50_primary_01\dataset\landmark_features.npz`
- Run guide: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_b_asl_led_50_primary_01\README_RUN.md`
- Smoke summary: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_b_asl_led_50_primary_01\smoke\smoke_summary.json`
- Structural check: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e5_batch_screening\e5_b_asl_led_50_primary_01\check_report.json`

## Architecture Decision

E5-B corrects the earlier strict dual-source interpretation.

- ASL Citizen is the broad vocabulary training source.
- Local supplementary data is used when available to strengthen, repair, or validate signs.
- Local support is not required for every selected class.
- Known hard/confusion signs are excluded from this primary model instead of being hidden inside aggregate accuracy.

This keeps the project moving toward batch-scale vocabulary evidence without pretending every sign already has production-grade local signer diversity.

## Selected Primary Classes

E5-B selected `50` primary classes:

`GOOD`, `HELLO`, `HAVE`, `KNOW`, `WANT2`, `WHAT1`, `MEET`, `NICE`, `START`, `GIVE`, `KEEP`, `STAND2`, `CLOSE`, `TALK1`, `WASH2`, `LEAVE`, `CLEAN`, `GO`, `OPEN`, `COOK`, `PAY`, `BUY`, `READ`, `PUT`, `US`, `SIT`, `MORNING`, `MEAN2`, `WRITE`, `WATCH`, `USE`, `CONGRATULATIONS`, `SHOW`, `SELL`, `CALL1`, `WORK`, `RUN2`, `MOVE`, `TAKE`, `TURN`, `PLAY`, `THINK`, `FIND`, `WE`, `FEEL`, `TRY`, `SEEM`, `YOU`, `SLEEP`, `DRIVE`.

Excluded primary-confusion or blocked signs include:

`SORRY`, `HELP`, `BECOME`, `MAKE`, `GET`, `WELCOME2`, `BYE`, `NO`, `YES`, `THANKYOU`.

`SORRY` remains handled by the GOOD/SORRY landmark specialist path proven in E4-V/E4-W/E4-X.

## Dataset Summary

- Shape: `[2206,96,258]`
- Schema: `3.0`
- Train/validation/test rows: `1482/174/550`
- Sources: `1413` ASL Citizen rows, `793` local supplementary rows
- Random baseline for 50 classes: `0.02`

The package reuses existing extracted features, so it avoids another long MediaPipe extraction cycle.

## Smoke Result

Smoke passed locally:

- Loaded the dataset tensor.
- Built `conv1d_baseline`.
- Ran one forward pass with output shape `[32,50]`.
- Ran one training step.
- Saved smoke weights to the package `smoke/` directory.

Structural check passed with `--require-dataset --require-full-dataset`.

## Full Training Command

The user should run full training because it is the longer step:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e5_b_asl_led_primary_batch run --run-dir "artifacts\recognition_upgrade\e5_batch_screening\e5_b_asl_led_50_primary_01"
```

Resume if interrupted:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e5_b_asl_led_primary_batch run --run-dir "artifacts\recognition_upgrade\e5_batch_screening\e5_b_asl_led_50_primary_01" --resume
```

Check after training:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e5_b_asl_led_primary_batch check --run-dir "artifacts\recognition_upgrade\e5_batch_screening\e5_b_asl_led_50_primary_01" --require-dataset --require-full-dataset --require-metrics
```

## Evaluation Purpose

E5-B answers one high-value question:

Can the landmark-primary model scale from the small stable set to a 50-class ASL-led vocabulary when known hard/confusion signs are excluded and local data supplements where available?

## Go / No-Go Criteria

Go if:

- Test accuracy is materially above the `0.02` random baseline.
- No prediction collapse into one or a few dominant classes.
- Stable controls `GOOD`, `HELLO`, `HAVE`, and `KNOW` remain strong.
- Per-class results identify a meaningful batch of keep/promote signs.
- Weak classes are cleanly tiered for specialist, repair, or deferral.

No-go if:

- E4-P-style broad collapse repeats.
- Stable controls degrade.
- ASL-only signs dominate training but fail held-out test.
- Aggregate accuracy hides severe per-class failures.

## Assumptions

- Existing combined feature tensors were created with schema v3.0 and remain train/runtime compatible for offline diagnostic use.
- E5-A inventory remains a valid source for selecting candidates.
- This is a diagnostic package, not production model training.

## Open Questions

- How many of the 50 classes survive signer-independent held-out testing?
- Are failures concentrated by provenance, signer, label variant, or landmark quality?
- Should the next production candidate set be 10-20 strong signs rather than all 50?
- Which failed signs require specialist routing versus data repair?

## Risks

- ASL Citizen labels may include variants not aligned with local app usage.
- Local supplementary rows may improve some signs while creating provenance shortcuts.
- The validation split is small for some signs.
- A 50-class aggregate metric can look acceptable while many individual signs fail.

## Next Required Action

Run E5-B full training, then analyze metrics per class, confusion groups, and stable-control retention. Do not export or integrate with Android after training until the result is reviewed.
## Session Save - 2026-08-02 23:54 +08:00

Saved handoff state:

- E5-B package is prepared and validated structurally.
- Smoke passed locally: dataset load, model build, `[32,50]` forward pass, one training step, and smoke weight save.
- Full training has not been run yet.
- The next user-run command is the full E5-B training command in this document.
- After training, run the check command with `--require-metrics` and review `metrics/metrics.json` before any Android/export decision.
- Current strategy remains ASL Citizen-led broad vocabulary with local supplementary support where available.
- No Android integration, TFLite export, production recognizer replacement, or runtime pipeline change is authorized.

