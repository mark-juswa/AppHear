# E2d Detector Operating-Point Plan

## Purpose

Determine whether the current MediaPipe hand model is fundamentally inadequate for AppHear
RGB crops or is merely operating at thresholds that suppress recoverable hands.

## Scope

E2d is the final bounded MediaPipe detector-tuning experiment. It changes no production
extractor, Android running mode, model asset, feature schema, or recognizer. It performs no
recognition training and creates no production crop dataset.

## Current Status

COMPLETE / NO-GO. E2d found no IMAGE or VIDEO threshold that passed all cadence,
anatomical-hand, false-ROI, and latency gates. See
`E2D_DETECTOR_OPERATING_POINT_RESULT.md`.

## Verified Project References

- Positive source: 120 known-visible E2b base items.
- Negative source: 212 unanimously target-hand-not-visible unique E2 Run 02 items are
  available; 120 will be selected without using the two conflicting items.
- Negative strata have at least 29 candidates for every cadence/anatomical-hand cell.
- Current control thresholds are detection 0.5 and presence 0.5.
- The same 7.8 MB Hand Landmarker task and MediaPipe 0.10.35 are used throughout.

## Architecture Decision

Compare six operating points:

- IMAGE at detection/presence 0.5, 0.4, and 0.3;
- VIDEO at detection/presence 0.5, 0.4, and 0.3;
- tracking confidence remains fixed at 0.5.

Every candidate sees identical chronological frames, real timestamps, clip isolation,
cadence, target anatomical hand, and model asset. The 0.5 IMAGE candidate is the registered
production-behavior control.

The engineering set contains:

- 120 fixed known-visible positives from E2b;
- 120 deterministic target-hand-absent negatives from corrected E2;
- all cadence/anatomical-hand cells represented; negatives are balanced at 20 per cell, while`n  frozen positives inherit E2b counts of 14-22 per cell;
- signer/split metadata retained for subgroup analysis.

## Automatic Metrics

For each candidate, cadence, and anatomical hand:

- positive target-slot recall;
- negative target-slot false-ROI rate;
- gains and losses versus the exact control on paired items;
- any-hand and two-hand sequence detection rates;
- p50/p95 inference latency;
- handedness-slot asymmetry.

No human review panels are generated in Stage 1. A shortlisted operating point receives a
separate, deduplicated crop-quality review only after automatic promotion.

## Registered Gates

A candidate must pass every cadence and anatomical-hand subgroup:

- positive recall gain at least 20 percentage points over IMAGE 0.5;
- negative false-ROI rate no greater than 5%;
- negative false-ROI increase no greater than 2 points over IMAGE 0.5;
- p95 latency no greater than 1.20 times IMAGE 0.5 on the same host;
- no cadence or anatomical-hand recall regression.

These gates prevent improved recall from being purchased with false hands, handedness swaps,
or unacceptable compute.

## Stop Rules

- If no candidate passes, stop tuning MediaPipe thresholds.
- Do not manually review crops when the automatic gate fails.
- After no-go, evaluate a different hand-box detector or a full/upper-body RGB stream.
- Do not start E3 or modify Android from threshold-only evidence.

## Smoke Validation

`smoke_validation_01` completed on 2026-07-26:

- 12 unique items: 6 known-visible positives and 6 target-hand-absent negatives;
- 72 item/candidate records across all six operating points;
- 3,852 timed detector calls;
- all expected CSV and JSON outputs were written under the separate E2d derived root;
- the full preflight resolves 240 items across 58 clips and an estimated 32,376 detector calls;
- every negative smoke item remained free of false target-hand ROIs;
- no candidate passed every cadence and anatomical-hand gate, which is expected from this
  deliberately small structural sample and is not an E2d decision.

VIDEO 0.3 recovered one of two positive items at k4 and k8, but native recall and right-hand
recall did not improve. The full balanced engineering sweep is required to determine whether
that partial signal generalizes.

Validation after the smoke: 154 project tests passed; focused Ruff and mypy checks were clean.

## Assumptions

- Corrected E2 visibility labels are adequate positive/negative engineering truth.
- A target anatomical slot on a negative item should remain absent even if the other hand
  is visible.
- Thresholds below 0.3 are too likely to produce false ROIs and are outside this experiment.

## Open Questions

- Does lower presence confidence help more than lower palm-detection confidence?
- Are false target slots caused by hallucination or handedness swaps?
- Would an independently trained hand-box detector be more robust to motion blur?

## Risks

- Engineering-set tuning can overfit the same signers and frames.
- Lower thresholds may improve landmark output while worsening crop containment.
- Negative labels inherit human audit uncertainty.
- Python latency is comparative and does not replace Android measurement.

## Rollback

Delete or ignore the separate E2d derived output. Current IMAGE 0.5 behavior remains frozen.

## Source Of Truth

- Config: `pipeline/config/detector_e2d.yaml`
- Runner: `pipeline/tracking/e2d.py`
- Result: `E2D_DETECTOR_OPERATING_POINT_RESULT.md` plus the immutable run summary.

## Related Context Files

- `E2C_TEMPORAL_TRACKING_RESULT.md`
- `EXPERIMENT_MATRIX.md`
- `ANDROID_DEPLOYMENT_PLAN.md`
- `RISK_REGISTER.md`

## Next Required Action

Create an architecture-only E2e ROI-source feasibility plan. Do not perform E2d human review,
continue MediaPipe threshold tuning, begin E3, or change Android.

## Last Updated

2026-07-26
