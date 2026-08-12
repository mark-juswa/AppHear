# E5-D Reduced Primary Validation Result

**Purpose:** Record the completed E5-D reduced-primary training result and its consequence for the dynamic mixed recognition roadmap.

**Scope:** Offline landmark-only experiment analysis only. This document does not authorize Android integration, TFLite export, production recognizer replacement, schema mutation, dataset deletion, or UI changes.

**Current status:** COMPLETE / USEFUL OFFLINE PASS / NOT PRODUCTION-READY.

**Last updated:** 2026-08-03.

## Verified Project References

- Runner: `pipeline/rgb/e5_d_reduced_primary_validation.py`
- Run directory: `artifacts/recognition_upgrade/e5_batch_screening/e5_d_reduced_primary_15sign_01`
- Config: `artifacts/recognition_upgrade/e5_batch_screening/e5_d_reduced_primary_15sign_01/pilot_config.json`
- Metrics: `artifacts/recognition_upgrade/e5_batch_screening/e5_d_reduced_primary_15sign_01/metrics/metrics.json`
- Structural check: passed with `--require-metrics`
- Source experiment: `E5_C_50CLASS_TIERING_RESULT.md`

## Experiment Setup

- Input schema: v3.0 `[96,258]`
- Model branch: `conv1d_baseline`
- Seeds: `101`, `202`, `303`
- Classes: `WASH2`, `TAKE`, `MEET`, `HAVE`, `WANT2`, `WORK`, `GOOD`, `MORNING`, `STAND2`, `SELL`, `THINK`, `DRIVE`, `RUN2`, `USE`, `SLEEP`
- Dataset rows: `695`
- Split counts: train `483`, validation `49`, test `163`
- Source counts: ASL Citizen `422`, local `273`
- Random baseline: `0.0667`
- Excluded by design: `HELLO` and `KNOW` because E5-C showed `SEEM` regression; `SORRY` because it remains routed/specialist-only.

## Results

Latest fixed-epoch test accuracy by seed:

- Seed `101`: train `0.9565`, validation `0.6735`, test `0.6871`
- Seed `202`: train `0.9689`, validation `0.7755`, test `0.7239`
- Seed `303`: train `0.9503`, validation `0.7347`, test `0.6687`

Mean latest test accuracy: `0.6933`.

Best-checkpoint test accuracy by seed:

- Seed `101`: test `0.7301`
- Seed `202`: test `0.7607`
- Seed `303`: test `0.7239`

Mean best-checkpoint test accuracy: `0.7382`.

Prediction concentration was not a collapse: max predicted-class share by seed was `0.1288`, `0.1227`, and `0.1104`.

## Per-Class Latest Test Behavior

Strongest classes:

- `WASH2`: mean `1.0000`, min `1.0000`
- `THINK`: mean `0.9697`, min `0.9091`
- `TAKE`: mean `0.9667`, min `0.9000`
- `MEET`: mean `0.8519`, min `0.7778`
- `GOOD`: mean `0.8148`, min `0.7778`
- `STAND2`: mean `0.7879`, min `0.7273`
- `SELL`: mean `0.7879`, min `0.7273`
- `MORNING`: mean `0.7381`, min `0.7143`
- `HAVE`: mean `0.7333`, min `0.5000`

Weak or unstable classes:

- `SLEEP`: mean `0.5833`, min `0.5000`
- `RUN2`: mean `0.5185`, min `0.3333`
- `WANT2`: mean `0.4545`, min `0.0909`
- `DRIVE`: mean `0.4545`, min `0.2727`
- `WORK`: mean `0.4359`, min `0.3846`
- `USE`: mean `0.3939`, min `0.1818`

## Top Confusions

Aggregated latest-test confusions over the three seeds:

- `WORK -> USE`: `11`
- `USE -> WORK`: `9`
- `WANT2 -> DRIVE`: `8`
- `WORK -> TAKE`: `8`
- `SLEEP -> USE`: `7`
- `DRIVE -> HAVE`: `7`
- `HAVE -> DRIVE`: `6`
- `RUN2 -> WASH2`: `6`
- `USE -> MORNING`: `6`
- `SELL -> WASH2`: `5`

## Interpretation

E5-D confirms that E5-C tiering was directionally correct. Reducing the primary vocabulary from E5-B's 50 classes to 15 classes improved mean latest test accuracy from `0.4897` to `0.6933`, and best-checkpoint mean test accuracy reached `0.7382`. This is a material improvement over the 50-class diagnostic and far above the 15-class random baseline of `0.0667`.

However, E5-D is not production-ready. Several classes still fall below a reasonable product threshold, especially `USE`, `WORK`, `DRIVE`, `WANT2`, `RUN2`, and `SLEEP`. The dominant errors form interpretable confusion groups, especially `WORK/USE`, `WANT2/DRIVE/HAVE`, and `SLEEP/USE/MORNING`.

## Decision

E5-D is a useful offline pass for the reduced-primary strategy, but it should not be exported or integrated into Android.

Recommended next step: create an E5-E reduced-primary tiering/decision pass that splits the 15 signs into immediate primary candidates, guarded primary candidates, confusion-group candidates, and repair/defer signs.

After that, run an offline routed-system simulation using:

`E4-AG no-sign gate -> reduced primary candidate model -> GOOD/SORRY specialist route where applicable -> reject/commit policy`

The weak E5-D signs should not be forced into the first Android candidate.

## Architecture Decisions

- Preserve the landmark-primary direction.
- Keep schema v3.0 `[96,258]` unchanged.
- Do not return to broad always-on RGB based on this result.
- Use per-class tiers and confusion groups instead of treating aggregate accuracy as sufficient.
- Keep `HELLO`, `KNOW`, and `SORRY` outside this primary model until their routed/repair path is explicitly validated.

## Assumptions

- Latest fixed-epoch policy remains the conservative comparison policy unless a later checkpoint-policy experiment proves best-checkpoint selection is safer for this batch.
- Test rows are treated as decision evidence for this offline experiment only, not as training data.

## Open Questions

- Which of the weak E5-D signs can be rescued by calibration or router rejection alone?
- Does a smaller 8-9 sign primary model reach a release-like per-class floor?
- Are `WORK/USE` and `WANT2/DRIVE/HAVE` better handled by specialists, data repair, or exclusion from the first primary release?
- Should best-checkpoint policy be reconsidered for E5-D, given the higher mean test result, or does it risk instability seen in earlier experiments?

## Risks

- Aggregate improvement can hide unacceptable per-class failures.
- Continued test-set iteration can overfit decisions to current artifacts.
- Local supplementary rows may still introduce source/provenance shortcuts.
- Exporting this model prematurely would create confident wrong translations for weak classes.

## Next Required Action

Prepare E5-E reduced-primary tiering/decision from E5-D metrics. Do not start Android integration, TFLite export, production replacement, or broad new extraction before E5-E defines the safe subset and confusion groups.
