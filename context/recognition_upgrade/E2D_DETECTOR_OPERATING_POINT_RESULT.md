# E2d Detector Operating-Point Result

## Purpose

Record the verified result and decision for the final bounded MediaPipe Hand Landmarker
detection/presence threshold sweep.

## Scope

This result covers offline detector behavior on the registered E2d positive/negative engineering
set. It does not authorize a production threshold, Android running-mode change, RGB model training,
or replacement of the active recognizer.

## Current Status

COMPLETE / NO-GO. No IMAGE or VIDEO operating point passed every registered cadence,
anatomical-hand, false-ROI, and latency gate.

## Verified Run

- Run ID: `engineering_e2d_01`
- Experiment: `e2d.detector_operating_point.v0.1`
- MediaPipe: `0.10.35`
- Hand model SHA-256:
  `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`
- Runner SHA-256:
  `4a18537fab4fa1413740abc2eaeaa3636d82bff28ac8aaa821a0ec9770c39106`
- Config hash: `cbedc7d0d368`
- Items: 120 known-visible positives and 120 target-hand-absent negatives
- Candidates: IMAGE and VIDEO at detection/presence 0.5, 0.4, and 0.3
- Calls: 32,376
- Integrity: 1,440 item rows, 240 rows per candidate, 240 unique items, no duplicate
  item/candidate pairs, and identical item sets for all candidates

## Artifact Hashes

- `generation_summary.json`:
  `6424364d655f0668bb2e0b7f948ef03d87b067d58c9f496c345594b527ffa88e`
- `item_index.csv`:
  `f146a300d37968607da78d43c2a37d34fdae2716d98b9d87828728400a069ad9`
- `latency.csv`:
  `137a86e84fe07ff3dc31e1b1631359a153ec38d9e2b50af3af3744a3f880d5d6`
- `run_config.json`:
  `a99a8785913bb003d4094e915712dd21c412de77d92c6f35ea8d46e8a64b431d`

## Verified Metrics

The IMAGE 0.5 control positive recall was 41.7% native, 50.0% k4, and 50.0% k8.
Its target-hand false-ROI rates were 0%, 2.5%, and 0%.

| Candidate | Recall native / k4 / k8 | Gain vs control | False ROI native / k4 / k8 | Hand result | Decision |
|---|---|---|---|---|---|
| IMAGE 0.4 | 50.0 / 50.0 / 52.5 | +8.3 / 0.0 / +2.5 | 0.0 / 2.5 / 0.0 | left +6.3; right 0.0 | fail recall |
| IMAGE 0.3 | 55.6 / 50.0 / 55.0 | +13.9 / 0.0 / +5.0 | 0.0 / 7.5 / 0.0 | left +12.5; right -1.8 | fail recall, false ROI, right |
| VIDEO 0.5 | 52.8 / 54.5 / 57.5 | +11.1 / +4.5 / +7.5 | 0.0 / 2.5 / 0.0 | left +17.2; right -3.6 | fail recall and right |
| VIDEO 0.4 | 58.3 / 52.3 / 60.0 | +16.7 / +2.3 / +10.0 | 0.0 / 5.0 / 0.0 | left +20.3; right -3.6 | fail cadence, false-ROI increase, and right |
| VIDEO 0.3 | 61.1 / 56.8 / 62.5 | +19.4 / +6.8 / +12.5 | 7.5 / 12.5 / 2.5 | left +25.0; right -1.8 | fail recall, false ROI, right |

All p95 latency ratios were between 0.968 and 1.014 of the IMAGE 0.5 control, well within
the 1.20 limit. Compute was not the reason for rejection.

Paired positives confirm the trade-off. VIDEO 0.4 recovered 14 control misses but lost 3
control detections. VIDEO 0.3 recovered 17 and lost 2, but produced 9 false target-hand ROIs
among the 120 negatives. Gains were concentrated on the left-hand subset; no VIDEO threshold
improved aggregate right-hand recall.

## Registered Gate Decision

`promoted_candidates` is empty. Every candidate failed the requirement for at least a
20-percentage-point positive-recall gain at every cadence and anatomical hand. IMAGE 0.3 and
VIDEO 0.3 additionally exceeded false-ROI limits, while VIDEO candidates regressed right-hand
recall.

E2d is therefore NO-GO. Do not lower the production MediaPipe thresholds and do not promote
VIDEO mode as the RGB crop source.

## Engineering Interpretation

Verified: lower thresholds recover some detections, especially for left-hand targets, and have
acceptable latency. They do not make the current Hand Landmarker a sufficiently reliable,
balanced hand-ROI source.

Inference: the remaining problem is not primarily detector threshold or compute. It is more
consistent with model/ROI-source limitations plus handedness instability under difficult hand
appearance and motion. The E2b, E2c, and E2d sequence of failures supports this conclusion.

MediaPipe may remain useful for the structured landmark stream when landmarks are available.
It should not be treated as the sole dependable RGB hand-crop generator unless a future,
separately gated ROI source solves the missing/incorrect hand cases.

## Architecture Decision

Apply the registered stop rule:

- stop MediaPipe threshold and running-mode tuning for RGB crop recovery;
- do not perform E2d human crop review;
- keep E3 hybrid training blocked because its RGB input would be systematically missing;
- keep the production Android recognizer, IMAGE 0.5 behavior, and model contract unchanged;
- architect the next bounded ROI-source feasibility experiment around an alternative hand-box
  detector and/or an upper-body RGB fallback that does not depend on reliable hand landmarks.

## Assumptions

- Corrected E2 negative labels and E2b known-visible positives remain valid engineering truth.
- Anatomical left/right canonicalization used by the paired runner is consistent across
  candidates.
- This engineering set diagnoses crop-source feasibility; it is not a recognition-accuracy test.

## Unknowns And Open Questions

- Whether right-hand regressions originate mainly from MediaPipe handedness assignment,
  occlusion, motion blur, or source-label/canonicalization edge cases.
- Whether a mobile hand-box detector can materially improve recall without requiring excessive
  annotation or compute.
- Whether upper-body RGB plus learned spatial attention can preserve enough hand-shape detail on
  Android.
- Whether a detector-assisted box stream and a landmark-independent fallback should coexist.

## Risks

- Repeating small MediaPipe tuning variants would overfit this engineering set without addressing
  the failed foundation.
- A new detector may improve box recall but add latency, false boxes, annotation cost, and export
  risk.
- Upper-body inputs avoid missing crops but may lose finger detail at mobile resolutions.

## Rollback And Compatibility

E2d created only a separate derived output directory and planning records. Ignore or archive that
directory to roll back the experiment. No production asset or runtime contract changed.

## Source Of Truth

- Run:
  `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/e2d_detector_operating_point_v0/engineering_e2d_01`
- Plan: `E2D_DETECTOR_OPERATING_POINT_PLAN.md`
- Config: `pipeline/config/detector_e2d.yaml`
- Runner: `pipeline/tracking/e2d.py`

## Related Context Files

- `E2B_PHASE_A_RESULT.md`
- `E2C_TEMPORAL_TRACKING_RESULT.md`
- `EXPERIMENT_MATRIX.md`
- `HYBRID_FUSION_DESIGN.md`
- `ANDROID_DEPLOYMENT_PLAN.md`
- `RISK_REGISTER.md`

## Next Required Action

Create an architecture-only E2e ROI-source feasibility plan. Compare a mobile-compatible
alternative hand-box detector against a landmark-independent upper-body RGB fallback before
writing another extractor or training E3.

## Last Updated

2026-07-26
