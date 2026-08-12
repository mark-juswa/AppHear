# E4-X Routed System Validation Result

**Purpose:** Test the E4-S primary recognizer plus E4-V GOOD/SORRY landmark specialist as a routed decision system with explicit accept/reject policy and no-hand N0 false-commit probing.
**Scope:** Offline window-level validation only. No Android integration, TFLite export, production asset replacement, dataset mutation, or training is authorized.
**Current status:** COMPLETE / PASSED ZERO-LANDMARK N0 PROBE / REAL N0 FEATURE EXTRACTION STILL REQUIRED.
**Last updated:** 2026-08-02.

## Verified Project References

- Runner: `pipeline/rgb/e4_x_routed_system_validation.py`
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_x_routed_system_validation_01`
- Primary source run: `artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01`
- Specialist source run: `artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01`
- N0 source run: `artifacts/recognition_upgrade/e2e_c0/n0_capture_06`
- Metrics: `artifacts/recognition_upgrade/e4_generalization/e4_x_routed_system_validation_01/metrics/routed_system_metrics.json`
- Policy grid: `artifacts/recognition_upgrade/e4_generalization/e4_x_routed_system_validation_01/metrics/validation_policy_grid.csv`
- Test predictions: `artifacts/recognition_upgrade/e4_generalization/e4_x_routed_system_validation_01/predictions/test_predictions.csv`
- Structural check: passed with `--require-metrics --require-predictions`.

## Experiment Design

E4-X simulates this decision path:

`E4-S primary -> conditional GOOD/SORRY specialist -> confidence policy -> accept gloss or reject as NO_SIGN`

Inputs:

- E4-S active rows for `GOOD`, `HELLO`, `HAVE`, and `KNOW`
- E4-S withheld `SORRY` rows
- reviewed E2e-C0 N0 rows represented as all-zero `[96,258]` features with all-false frame masks

The selected policy was fitted on validation rows:

- primary confidence threshold: `0.95`
- specialist confidence threshold: `0.50`

Dataset summary:

- total rows: `451`
- validation rows: `97`
- test rows: `238`
- source counts: `221` E4-S active, `50` E4-S OOV/SORRY, `180` N0 zero-landmark probe rows

## Results

Test summary across seeds:

- mean accepted precision: `0.9798`
- minimum accepted precision: `0.9739`
- mean positive coverage: `0.9746`
- minimum positive coverage: `0.9661`
- maximum N0 false-commit rate: `0.0000`
- mean/min `SORRY` recall: `0.9667`
- mean/min `GOOD` recall: `0.9667`
- gate result: passed.

Per-seed test notes:

- seed `101`: accepted precision `0.9912`, positive coverage `0.9661`, N0 false commits `0/120`
- seed `202`: accepted precision `0.9741`, positive coverage `0.9831`, N0 false commits `0/120`
- seed `303`: accepted precision `0.9739`, positive coverage `0.9746`, N0 false commits `0/120`

## Interpretation

E4-X strengthens the E4-W result by adding an explicit accept/reject policy and a no-hand false-commit probe. It shows that the routed primary-plus-specialist architecture can preserve high positive coverage while rejecting all synthetic no-hand zero-feature rows under the selected policy.

However, the N0 representation is intentionally conservative and incomplete. The reviewed N0 videos have not yet been converted through the same MediaPipe landmark extraction and feature-normalization path used by real runtime inference. Therefore, this result does not prove real no-sign behavior on Android or even real offline MediaPipe N0 features.

## Architecture Decision

The routed landmark-primary architecture remains the best current path:

`primary [96,258] recognizer -> confusion registry/router -> GOOD/SORRY landmark specialist -> calibrated accept/reject -> sentence/UI`

E4-X authorizes the next offline validation step: extract real N0/no-sign `[96,258]` feature windows through the same landmark pipeline and rerun the routed-system false-commit gate. It does not authorize Android export or production integration.

## Assumptions

- Zero-landmark N0 windows are a useful first sanity check because missing landmarks are represented as zeros in schema 3.0.
- All-false `frame_mask` is acceptable for this probe, but the current Conv1D primary does not consume frame masks.
- The E4-S/E4-V latest fixed-epoch checkpoints remain the current evaluated policy.

## Open Questions

- What does the routed system do on real MediaPipe-extracted N0 and P1 no-sign/non-signing windows?
- Does the selected confidence policy remain stable with source-disjoint GOOD/SORRY rows?
- Should the specialist confidence threshold remain low because the primary confidence threshold does most of the rejection, or should specialist calibration be fitted separately?
- How should a runtime signing gate interact with the routed recognizer's reject state?

## Risks

- Zero-feature N0 can understate false commits if real no-sign frames produce partial pose or hand landmarks.
- The selected threshold may be overfit to small validation evidence.
- Positive coverage remains window-level, not continuous sentence-level coverage.
- Passing E4-X too aggressively could cause premature Android integration before real no-sign and device gates.

## Next Required Action

Prepare a real N0/P1 feature-extraction validation package. It should:

- process reviewed N0/P1 videos or sampled frames through MediaPipe and schema v3.0 feature construction;
- build no-sign/non-signing windows that match runtime sequence construction as closely as possible;
- rerun E4-X-style routed-system accept/reject metrics;
- report false commits separately for N0 no-visible-hands and P1 visible-idle-hands;
- remain offline and isolated from Android production assets.
