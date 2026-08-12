# E4-Y Real No-Sign Feature Validation Result

**Purpose:** Validate the routed E4-S primary plus E4-V GOOD/SORRY specialist on real MediaPipe-derived N0/P1 no-sign features instead of synthetic zero-landmark windows.
**Scope:** Offline window-level validation only. No Android integration, TFLite export, production asset replacement, dataset mutation, or training is authorized.
**Current status:** COMPLETE / STRUCTURAL CHECK PASSED / ACCURACY-FALSE-COMMIT GATE FAILED.
**Last updated:** 2026-08-02.

## Verified Project References

- Runner: `pipeline/rgb/e4_y_real_nosign_feature_validation.py`
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_y_real_nosign_feature_validation_01`
- Primary source run: `artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01`
- Specialist source run: `artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01`
- Policy source run: `artifacts/recognition_upgrade/e4_generalization/e4_x_routed_system_validation_01`
- N0 source run: `artifacts/recognition_upgrade/e2e_c0/n0_capture_06`
- P1 source run: `artifacts/recognition_upgrade/e2e_c0/p1_capture_03`
- Metrics: `artifacts/recognition_upgrade/e4_generalization/e4_y_real_nosign_feature_validation_01/metrics/real_nosign_metrics.json`
- No-sign predictions: `artifacts/recognition_upgrade/e4_generalization/e4_y_real_nosign_feature_validation_01/predictions/nosign_test_predictions.csv`
- Extracted feature tensor: `artifacts/recognition_upgrade/e4_generalization/e4_y_real_nosign_feature_validation_01/dataset/real_nosign_features.npz`
- Structural check: passed with `--require-metrics --require-predictions`.

## Experiment Design

E4-Y uses the same MediaPipe `LandmarkExtractor` and schema v3.0 `clip_features_realtimed` math used by the training pipeline. It extracts real `[96,258]` windows from reviewed E2e-C0 no-sign footage, then evaluates the E4-X routed accept/reject policy:

`E4-S primary -> conditional GOOD/SORRY specialist -> primary confidence 0.95 + specialist confidence 0.50 -> accept gloss or reject as NO_SIGN`

Default bounded probe:

- N0 rows: `24`
- P1 rows: `24`
- validation/test split: `16/32` no-sign rows
- total combined evaluation rows after adding E4-S positives and withheld SORRY: validation `53`, test `150`
- schema: `[96,258]`, `schema_version=3.0`

Feature quality summary:

- N0 mean hand-hit rate: `0.0130`
- P1 mean hand-hit rate: `0.8359`
- N0 mean pose-hit rate: `1.0000`
- P1 mean pose-hit rate: `1.0000`

## Results

The structural package passed, but the recognition gate failed.

Test summary across seeds:

- mean accepted precision: `0.7844`
- minimum accepted precision: `0.7687`
- mean positive coverage: `0.9746`
- minimum positive coverage: `0.9661`
- maximum real no-sign false-commit rate: `0.9688`
- mean/min `SORRY` recall: `0.9667`
- mean/min `GOOD` recall: `0.9667`
- gate result: failed.

False commits by no-sign source:

- Seed `101`: N0 `13/16`, P1 `15/16`
- Seed `202`: N0 `16/16`, P1 `15/16`
- Seed `303`: N0 `14/16`, P1 `13/16`

Main false labels:

- N0 often committed as `SORRY`.
- P1 often committed as `GOOD`, `HELLO`, or `KNOW`.

## Interpretation

E4-X's zero-landmark no-sign pass was not sufficient. Real no-sign footage still produces pose landmarks and sometimes partial hand landmarks. The current classifier/router has no real signing-vs-not-signing model, so it forces many no-sign windows into known glosses with enough confidence to pass the E4-X thresholds.

This is a major blocker for the product goal. A silent translator cannot commit words when nobody is signing or when a person is merely holding visible idle hands.

The positive-sign path is still strong in this probe: GOOD and SORRY recall stayed at `0.9667`, and positive coverage stayed around `0.9746`. The failure is specifically false commits on real no-sign/non-signing windows.

## Architecture Decision

Do not proceed to Android export or production integration. The next architectural component must be a real signing/no-sign gate before the primary recognizer commits any gloss.

The current target path becomes:

`MediaPipe landmarks -> signing/no-sign gate -> primary recognizer -> confusion registry/router -> specialist -> calibrated accept/reject -> sentence/UI`

The signing gate should be trained or calibrated on real N0/P1 features, not synthetic zero vectors.

## Assumptions

- The bounded 24 N0 + 24 P1 probe is enough to expose the failure mode, but not enough for final gate statistics.
- The first rows selected from N0/P1 are acceptable for a smoke/probe; a later larger run should broaden clips/participants.
- Existing E4-X confidence thresholds were intentionally reused to test whether the current routed policy survives real no-sign features.

## Open Questions

- Can a lightweight signing/no-sign detector using `[96,258]` features distinguish active signing from N0/P1 windows?
- Should P1 visible-idle-hands be its own negative class or a hard-negative subset of no-sign?
- Which features best separate signing from no-sign: hand/pose motion energy, hand presence duration, wrist velocity, or a learned binary model?
- Can a simple rule-based motion gate beat a learned gate on this small negative set?
- How many N0/P1 windows are required for a production false-commit estimate?

## Risks

- A weak signing gate can reject real signs while trying to eliminate false commits.
- A rule-only gate may fail on subtle signs with low motion.
- A learned gate may overfit the small N0/P1 fixture unless expanded and split by participant/device/environment.
- The recognizer can look accurate on positive signs while remaining unusable due to false commits.

## Next Required Action

Prepare E4-Z signing/no-sign gate experiment. It should compare:

- rule-based motion/presence gate using existing `[96,258]` features and frame masks;
- lightweight learned binary gate trained on positive E4-S/E4-V windows versus real N0/P1 windows;
- combined gate + routed recognizer metrics.

Go criteria must include low no-sign false commits without destroying GOOD/SORRY/HELLO/HAVE/KNOW coverage. Android/export remains blocked.
