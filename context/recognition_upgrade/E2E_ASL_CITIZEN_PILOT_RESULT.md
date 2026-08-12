# E2e-A Android Convention And ASL Citizen Pilot Result

## Purpose

Record the measured MediaPipe Tasks handedness convention and the bounded ASL Citizen visual pilot
used to separate true hand-box failures from target-side/mirroring conflicts.

## Scope

This result covers one controlled mirrored Android camera-app recording, its horizontally
unmirrored counterpart, and 18 unique ASL Citizen diagnostic frames. It is not a production
CameraX analysis capture, a representative accuracy sample, or authorization for Android/model
changes.

## Current Status

COMPLETE / CONTRACT CORRECTED / FULL GOLD AUDIT REQUIRED.

The earlier legacy-document assumption that this Tasks bundle expects mirrored pixels is rejected
for AppHear. The exact bundled model was measured directly.

## Android Paired-Pixel Result

The developer confirmed that the first raised hand in
`scratchpad/e2e_android_fixtures/android_front_identity_01.mp4` was anatomical left and the second
was anatomical right.

| Time | Pixel variant | Gold hand | Hand Landmarker label |
|---:|---|---|---|
| 2.5 s | saved mirrored pixels | left | Right, 0.9778 |
| 2.5 s | horizontally unmirrored | left | Left, 0.9729 |
| 5.0 s | saved mirrored pixels | right | Left, 0.9638 |
| 5.0 s | horizontally unmirrored | right | Right, 0.9754 |

Pose wrist identities reverse in the same mirrored source. Correct canonicalization therefore
requires both horizontal coordinate transformation and symmetric pose-side permutation.

## Runtime Interpretation

- The current MediaPipe Tasks model reports anatomical handedness correctly on the measured
  unmirrored pixels.
- `FrameAnalyzer.kt` rotates but does not mirror the bitmap sent to inference.
- `PreviewView` mirroring is display-only and does not establish inference mirroring.
- ASL Citizen videos are decoded without an AppHear-added horizontal flip.
- The current direct slot mapping is therefore plausible for unmirrored sources and must not be
  changed globally.
- The phone camera application's saved video is mirrored and is not an exact CameraX
  `ImageAnalysis` fixture.

The corrected experiment rule is: preserve direct labels for verified unmirrored inputs and swap
hand plus symmetric pose sides only for verified mirrored inputs.

## Corrected Synthetic Smoke

The rebuilt six-fixture smoke passed:

- current direct: 8/10, failing only the deliberately mirrored two-hand fixture;
- swap only mirrored: 10/10;
- pose only: 8/10 because of the deliberate pose-dropout frame;
- pose plus bounded temporal state: 10/10.

These remain known-answer plumbing results, not accuracy claims.

## ASL Citizen Pilot Contract

Run:

`scratchpad/e2e_asl_citizen_pilot_v2_unique_20260726`

The selector produced 18 unique source frames:

- one target-miss/other-hand-detected item;
- one no-hand-detected item;
- one successful control;
- for each native/k4/k8 and left/right E2 target cell.

Each panel contains the center frame plus four chronological context frames, raw Hand Landmarker
boxes/labels, and Pose wrist labels. The first generated pilot is invalid for scoring because it
reused source frames across cadence cells; v2 enforces unique `(clip_id, frame_index)` pairs.

## Verified Visual Findings

The 12 failure-focused frames separate into:

- six genuine zero-box detector failures;
- two incomplete two-hand detections where one of two visible hands receives a box;
- four single-visible-hand cases where a box exists and Hand/Pose agree, but both conflict with the
  old E2 target side.

The genuine failures include small hands, hands near the face, motion blur, low or partly
out-of-frame hands, and rapid two-hand motion. The four conflicts are consistent with per-video
mirroring or target-side convention drift; the pilot cannot distinguish those causes without
per-video mirror gold.

The pilot was deliberately stratified by failure type. Its counts must not be converted into an
overall recall estimate.

## Architecture Decision

- Do not globally swap AppHear's current hand slots.
- Do not dismiss E2d as only a handedness bug: genuine box failures are visually confirmed.
- Do not use old E2 target-slot recall as pure detector recall: it mixes box absence, incomplete
  two-hand detection, and side/mirroring conflicts.
- Keep MediaPipe as the current landmark source while running a corrected all-hand-box audit.
- Defer independent-detector training until corrected box recall and both-hand recall are measured.

## Required Gold Audit Revision

Every evaluated frame must annotate:

- all visible hand boxes, not only one target side;
- visible hand count;
- per-video `source_mirrored` status with evidence or `unknown`;
- anatomical side only when mirror status/context makes it reliable;
- blur, occlusion, near-face, edge clipping, and partial visibility;
- Hand and Pose raw outputs before any canonicalization.

Primary detector metrics must be side-independent:

- visible-hand instance recall at IoU 0.50/0.75;
- any-hand frame recall;
- both-hands-complete recall;
- false hand boxes.

Identity metrics are computed separately only on mirror-adjudicated samples.

## Verification

- Corrected E2e-A tests: 6 passed.
- Pilot selector test: passed.
- Ruff: clean.
- Mypy: clean for the three E2e source modules.
- Pilot generation: 18 unique panels completed in approximately eight seconds.

## Assumptions

- The developer's left-then-right recording order is reliable ground truth.
- The visual pilot classifications are diagnostic and require a larger blinded audit.
- ASL Citizen may contain heterogeneous source mirroring; this is supported by conflicts but not
  yet measured as a dataset-wide rate.

## Open Questions

- What fraction of ASL Citizen clips are mirrored, unmirrored, or not adjudicable?
- After side-independent scoring, what is true visible-hand and both-hand box recall?
- Can pose plus temporal continuity recover identity without hiding genuine box absence?
- Does exact CameraX analysis capture confirm the code-derived unmirrored runtime convention?

## Risks

- Inferring source mirroring from MediaPipe itself would make the audit circular.
- Treating the failure-stratified pilot as representative would produce invalid rates.
- A global slot swap would corrupt currently correct unmirrored samples.
- Training a detector before correcting gold labels would optimize against contaminated targets.

## Source Of Truth Files

- `E2E_MEDIAPIPE_RELIABILITY_PLAN.md`
- `E2E_COORDINATE_IDENTITY_AUDIT_PLAN.md`
- `pipeline/config/identity_e2e.yaml`
- `pipeline/tracking/identity.py`
- `pipeline/tracking/e2e.py`
- `pipeline/tracking/e2e_pilot.py`
- `tests/test_tracking_identity_e2e.py`
- `tests/test_tracking_e2e_pilot.py`
- `scratchpad/e2e_asl_citizen_pilot_v2_unique_20260726/pilot_index.csv`
- `scratchpad/e2e_asl_citizen_pilot_v2_unique_20260726/pilot_failure_review.csv`

## Related Context Files

- `E2D_DETECTOR_OPERATING_POINT_RESULT.md`
- `CURRENT_PIPELINE_AUDIT.md`
- `EVALUATION_AND_ACCEPTANCE_GATES.md`
- `ROLLBACK_AND_COMPATIBILITY_PLAN.md`
- `RISK_REGISTER.md`

## Follow-Up Tooling Result

The revised all-visible-hand workflow is implemented in `pipeline/tracking/e2e_gold.py`,
`pipeline/tracking/e2e_gold_review.py`, and `pipeline/tracking/e2e_gold_audit.py`. Its deterministic
six-frame generation smoke and non-GUI contract check passed. The workflow is documented in
`E2E_GOLD_AUDIT_WORKFLOW.md`.

## Next Required Action

Complete the six-frame human GUI smoke in `scratchpad/e2e_gold_audit_smoke_20260726` and validate
the saved annotations. Do not generate the full 150-frame audit until the GUI interaction and
coordinate output are reviewed. Do not train a detector, start E3, or change Android.

## Last Updated

2026-07-26
