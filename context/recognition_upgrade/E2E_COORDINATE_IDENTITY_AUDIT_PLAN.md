# E2e-A Coordinate And Anatomical-Hand Identity Audit

## Purpose

Determine how much of AppHear's E2 target-hand failure is true hand-detection failure versus
camera-coordinate, handedness-label, or temporal identity failure.

## Scope

E2e-A is diagnostic only. It does not change production Android, MediaPipe configuration, schema
3.0, extracted landmarks, model assets, training data, or recognition behavior. It does not train
a detector.

## Current Status

TOOLING SMOKE IN PROGRESS. The synthetic fixture phase validates coordinate and assignment
plumbing only. Real MediaPipe reliability conclusions require the manually labeled engineering set.

## Source Of Truth

- Parent decision: `E2E_MEDIAPIPE_RELIABILITY_PLAN.md`
- Config: `pipeline/config/identity_e2e.yaml`
- Pure assignment logic: `pipeline/tracking/identity.py`
- Smoke entry point: `pipeline/tracking/e2e.py`
- Prior evidence: `E2B_PHASE_A_RESULT.md`, `E2C_TEMPORAL_TRACKING_RESULT.md`,
  `E2D_DETECTOR_OPERATING_POINT_RESULT.md`
- Runtime pixels and slots: `FrameAnalyzer.kt`, `LandmarkAdapter.kt`
- Offline slots: `pipeline/extract/landmarks.py`, `pipeline/tracking/e2c.py`

## Coordinate Contract

Gold boxes use `upright_unmirrored_normalized` space:

- origin is top-left;
- x increases rightward and y increases downward;
- all boxes are normalized to `[0,1]`;
- image rotation has already been applied;
- front-preview mirroring is presentation metadata only;
- `inference_mirrored` records whether pixels entering MediaPipe were horizontally mirrored;
- anatomical `left` and `right` always refer to the signer, never the viewer or screen.

Measured Tasks-bundle rule: direct Hand/Pose sides are retained for verified unmirrored input;
horizontal coordinates and symmetric Hand/Pose identities are both swapped for verified mirrored
input. Unknown source mirror status is never guessed from MediaPipe output.

Every source path must have a known transform into this space. A transform must pass known-point and
double-mirror fixtures before its samples enter metric computation.

## Gold Annotation Schema

One CSV row represents one anatomical hand in one sampled frame. Required columns:

- identity: `sample_id`, `sequence_id`, `frame_index`, `timestamp_ms`;
- provenance: `video_file`, `participant_id`, `split`, `cadence`;
- camera: `camera_facing`, `inference_mirrored`, `display_mirrored`, `rotation_degrees`;
- dimensions: `image_width`, `image_height`;
- truth: `anatomical_side`, `visible`, normalized `x_min/y_min/x_max/y_max`;
- quality: `occlusion`, `motion_blur`, `notes`.

For a visible hand, the box must tightly contain the complete visible hand, including fingertips.
For an absent hand, `visible=no` and coordinates remain empty. Both anatomical sides must therefore
have a row for every frame.

## Sampling Contract

The engineering set contains 120-200 unique frames. Sample adjacent chronological frames only when
needed to measure crossing, dropout, or ID switches; otherwise avoid near-duplicates.

Required coverage:

- left-only and right-only;
- two hands separated and crossing;
- partial occlusion and near-face hands;
- clear and motion-blurred frames;
- native, k4, and k8 conditions;
- front-camera Android inference fixtures;
- unmirrored ASL Citizen frames;
- signer provenance retained and reported.

The E2d engineering set may nominate difficult frames, but its old target-side label is not gold.
An annotator must assign anatomical side using chronological context. Ambiguous samples are
quarantined rather than guessed.

## Compared Strategies

1. `current_direct`: current MediaPipe Left/Right label mapping.
2. `swap_mirrored`: swap Hand and symmetric Pose sides only when input is verified mirrored.
3. `pose`: assign unlabeled hand instances to anatomical pose wrists/forearms.
4. `pose_temporal`: pose assignment plus bounded causal track prediction.

All strategies consume identical hand candidates and timestamps. This experiment tests identity
and continuity; it does not compare different detector thresholds or running modes.

## Metrics

Primary detector metrics are side-independent: visible-hand instance recall at IoU 0.50/0.75,
any-hand frame recall, both-hands-complete recall, and false boxes. Identity metrics below are
computed only on mirror-adjudicated samples.

- visible-hand box recall at IoU 0.50 and 0.75;
- identity accuracy conditional on a geometrically matched detection;
- left/right and camera-path subgroup identity accuracy;
- both-hands recall;
- ID switches per minute during chronological sequences;
- false ROI rate on anatomically absent hands;
- stale or wrong-hand ROI rate;
- complete-hand crop containment;
- p50 and p95 assignment latency.

Report detector presence separately from target-slot recall. Never convert a wrong-side assignment
into a detector miss.

## Registered Gates

- coordinate fixtures: 100% pass;
- identity accuracy: at least 98% overall;
- identity accuracy: at least 95% in every side/camera subgroup;
- visible-hand recall: at least 95% overall;
- visible-hand recall: at least 90% in every cadence/blur subgroup;
- false ROI: at most 2%;
- stale or wrong-hand ROI: at most 1%.

Passing the synthetic smoke does not satisfy these gates.

## Decision Rules

- If `pose_temporal` passes every gate, retain MediaPipe and stop detector-replacement work.
- If identity passes but visible-hand recall fails, proceed to E2e-B pose ROI refinement.
- If E2e-B still fails, proceed to E2e-C single-class mobile hand-detector evaluation.
- If camera fixtures fail, stop and correct the experiment contract before collecting labels.
- No result permits an in-place production slot swap; any semantic change requires schema
  versioning, re-extraction, retraining, and train/serve skew validation.

## Assumptions

- Chronological source video is sufficient to annotate anatomical side in difficult frames.
- Pose wrists/forearms are available often enough to test association; this remains unverified.
- E2d outputs are nomination metadata, not anatomical gold.

## Risks

- Reviewer confusion between viewer-side, screen-side, and signer-side.
- Incorrect assumptions about whether CameraX analysis pixels are mirrored.
- Exact-frame leakage or duplicate frames inflating results.
- Pose failures being silently treated as correct identity.
- Synthetic fixtures being misreported as detector evidence.

## Open Questions

- Which controlled Android front-camera clips will provide the first real coordinate fixtures?
- Is one reviewer sufficient, or should ambiguous/two-hand samples require adjudication?
- Does pose-temporal assignment need elbow direction after wrist-distance baselines are measured?

## Next Required Action

Run the six-fixture smoke and focused tests. If they pass, prepare a very small real-data pilot
containing Android front-camera and ASL Citizen frames for human anatomical-side verification.
Stop before the full 120-200-frame set until the pilot is reviewed.

## Last Updated

2026-07-26
