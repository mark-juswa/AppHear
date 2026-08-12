# E2c Temporal Hand-Tracking Result

## Purpose

Record the verified automatic result and decision from the paired MediaPipe Hand Landmarker
IMAGE-versus-VIDEO experiment.

## Scope

This result covers E2c automatic detection and latency gates. Human crop review was
intentionally not started because the registered automatic stop rule failed.

## Current Status

COMPLETE - NO-GO. MediaPipe VIDEO mode does not provide enough reliable availability gain
to replace IMAGE mode.

## Verified Project References

- Run:
  `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/e2c_temporal_tracking_v0/engineering_e2c_01`
- 120 known-visible base items, 240 paired mode records, 7,378 inference calls, 120 panels.
- `audit_template.csv` remains empty by design: automatic gate failed before review.
- MediaPipe 0.10.35, identical 0.5 thresholds, identical hand model SHA-256
  `FBC2A30080C3C557093B5DDFC334698132EB341044CCEE322CCF8BCF3607CDE1`.

Artifact SHA-256:

- `internal_index.csv`:
  `C4AC640BE590401332CA6FBD046A33274EAA6D3E477228D82974E96389DB1E5E`
- `latency.csv`:
  `3EA3EF21EA5FA490624A2BCB63518D89A4ACC3D998B9D2C1A96AFB8CAAC148754`
- `generation_summary.json`:
  `818B55E9AD9C8E0AD59F66C04A29F9D44970C934235758CEC96977B2F0DD8579`
- `run_config.json`:
  `B55468878CE26643244FA2E0127963EB02ACE6CC223C999BAD4694C8D22EF9B6`

## Verified Result

| Cadence | IMAGE availability | VIDEO availability | Gain | 20-point gate |
|---|---:|---:|---:|---|
| Native | 15/36 (41.7%) | 19/36 (52.8%) | +11.1 points | FAIL |
| k4 | 22/44 (50.0%) | 24/44 (54.5%) | +4.5 points | FAIL |
| k8 | 20/40 (50.0%) | 23/40 (57.5%) | +7.5 points | FAIL |

Paired transitions:

- native: 4 gains, 0 losses;
- k4: 3 gains, 1 loss;
- k8: 6 gains, 3 losses.

Anatomical-hand result:

- native left +18.2 points; native right 0;
- k4 left +13.6; k4 right -4.5;
- k8 left +20.0; k8 right -5.0.

Across all sampled sequence frames, k8 two-hand presence fell from 10.68% IMAGE to 7.77%
VIDEO. VIDEO tracking therefore introduces real subgroup and two-hand regressions.

## Latency

VIDEO passed the comparative latency gate:

| Cadence | IMAGE p50/p95 ms | VIDEO p50/p95 ms | VIDEO/IMAGE p95 |
|---|---:|---:|---:|
| Native | 18.58 / 27.68 | 16.62 / 26.52 | 0.958 |
| k4 | 18.71 / 27.59 | 17.18 / 27.43 | 0.994 |
| k8 | 18.70 / 27.93 | 18.73 / 27.76 | 0.994 |

This is same-host Python evidence, not Android performance evidence.

## Architecture Decision

- Do not run E2c human review.
- Do not promote MediaPipe VIDEO mode.
- Do not implement VIDEO or LIVE_STREAM in Android from this result.
- Do not start crop-geometry Phase B or E3 hybrid training.
- Preserve IMAGE as the current production behavior.

VIDEO mode is computationally acceptable but does not solve the hand-detection bottleneck.

## Engineering Recommendation

Before replacing the detector, run one final low-cost MediaPipe detector-operating-point
experiment:

- fixed positive known-visible frames from E2/E2b;
- fixed negative target-hand-not-visible frames from E2;
- detection/presence confidence sweep below the current 0.5 operating point;
- IMAGE and VIDEO reported separately;
- positive recall, negative false ROI, handedness stability, two-hand recall, latency, and
  crop containment;
- human review only for the best automatic candidate.

This proposed E2d experiment determines whether the current model is merely over-thresholded.
If no operating point meets recall and false-positive gates, stop tuning MediaPipe and evaluate
a different hand detector or a larger full/upper-body RGB stream.

## Assumptions

- The E2b base set remains known-visible ground truth.
- IMAGE/VIDEO model and threshold parity is verified by `run_config.json`.
- Python p95 ratios are valid only as comparative host measurements.

## Open Questions

- Can lower detection/presence thresholds recover blurred hands without unacceptable false ROIs?
- Is the right-hand regression caused by handedness instability or tracker state?
- Would a detector trained for hand bounding boxes outperform landmark-first localization?
- Is a full/upper-body RGB stream affordable if reliable hand ROIs remain unavailable?

## Risks

- Threshold lowering may create false hands and hand-slot swaps.
- Positive-only optimization would hide false activation; E2d must include negatives.
- Repeated detector tuning can overfit this 120-item engineering set.

## Rollback

No production behavior changed. Preserve E2c evidence and keep current IMAGE mode.

## Next Required Action

Architect E2d as a bounded threshold/operating-point sweep with positive and negative target-hand
frames. No human review or long extraction should start before its automatic design is approved.

## Related Context Files

- `E2C_TEMPORAL_TRACKING_PLAN.md`
- `E2B_PHASE_A_RESULT.md`
- `EXPERIMENT_MATRIX.md`
- `ANDROID_DEPLOYMENT_PLAN.md`
- `RISK_REGISTER.md`

## Last Updated

2026-07-26
