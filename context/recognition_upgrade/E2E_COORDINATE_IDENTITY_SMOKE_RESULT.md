# E2e-A Coordinate And Identity Fixture Smoke Result

## Purpose

Record the bounded synthetic-fixture validation for E2e-A coordinate transforms and anatomical
hand-assignment plumbing.

## Scope

This result validates code behavior on six known-answer synthetic frames only. It is not evidence
of MediaPipe detector recall, real handedness accuracy, crop quality, or Android performance.

## Current Status

COMPLETE / SMOKE PASS. Real-data pilot and engineering audit remain unstarted.

## Verified Result

- Experiment contract: `e2e.coordinate_identity.v0.1`
- Fixture frames: 6
- Gold anatomical assignments: 10
- Double-mirror coordinate fixture: PASS
- Current direct MediaPipe labels: 2/10 correct (20%)
- Camera-aware swap on unmirrored input: 10/10 correct (100%)
- Pose-only assignment: 8/10 correct (80%)
- Pose plus bounded temporal state: 10/10 correct (100%)

Pose-only missed the two assignments in the deliberate pose-dropout frame. The temporal strategy
recovered both from 67 ms-old causal state, within the configured 250 ms maximum age.

These numbers are fixture expectations, not accuracy measurements. The direct-label fixtures were
deliberately constructed to expose the documented mirrored/unmirrored convention.

## Artifacts

Run directory:

`scratchpad/e2e_coordinate_identity_smoke_20260726`

- `fixture_summary.json` SHA-256:
  `0FB5666D27893CB6A29F76CBA94F7A4BA842725843C01BD1CD9ADA4E75FE7063`
- `run_config.json` SHA-256:
  `11FD194B1CC05B24DA951983B12FDCDD6321D232E8A0B06A9C7F4D15DA314321`
- `annotation_template.csv` SHA-256:
  `8C1D68EF35D77D10FBFD4120E53329AA26F0A255A6E1827BE3679D2BA7386C62`

## Verification

- Focused E2e-A tests: 5 passed.
- E2c/E2d regression tests: 8 passed.
- Full Python suite: 159 passed.
- Ruff: clean for new source and tests.
- Mypy: clean for both new source modules.

The full suite emitted existing Keras/NumPy deprecation warnings only.

## Architecture Decisions

- Keep the real-data comparison of direct, camera-aware swapped, pose, and pose-temporal strategies.
- Keep all annotation boxes in upright unmirrored normalized space.
- Do not infer a MediaPipe failure rate from the synthetic result.
- Do not start the full 120-200-frame audit until a small real Android/ASL Citizen pilot confirms
  that humans can label anatomical side and that every transform is visually correct.

## Assumptions

- Synthetic coordinates accurately exercise the intended transform and assignment interfaces.
- Real CameraX and offline source conventions still require observed fixtures.

## Open Questions

- Which controlled Android front-camera clips will be used for the first real pilot?
- Can the pilot reuse existing device recordings, or must a short explicit left/right calibration
  clip be recorded?
- Does pose-temporal identity remain stable during real two-hand crossing and blur?

## Risks

- Treating a synthetic pass as real detector evidence would be invalid.
- Incorrectly labeled real anatomical sides would contaminate every later conclusion.
- A camera-aware label swap may solve simple frames but remain unstable during occlusion; pose and
  time must still be measured.

## Source Of Truth Files

- `E2E_MEDIAPIPE_RELIABILITY_PLAN.md`
- `E2E_COORDINATE_IDENTITY_AUDIT_PLAN.md`
- `pipeline/config/identity_e2e.yaml`
- `pipeline/tracking/identity.py`
- `pipeline/tracking/e2e.py`
- `tests/test_tracking_identity_e2e.py`

## Related Context Files

- `README.md`
- `E2D_DETECTOR_OPERATING_POINT_RESULT.md`
- `EVALUATION_AND_ACCEPTANCE_GATES.md`
- `ROLLBACK_AND_COMPATIBILITY_PLAN.md`

## Next Required Action

Prepare a tiny real-data pilot, not the engineering set:

1. one controlled Android front-camera clip with explicit left-only, right-only, and both-hand
   poses;
2. a few unmirrored ASL Citizen frames from E2d with chronological context;
3. rendered unmirrored-inference and mirrored-preview views that state their coordinate space;
4. human anatomical-side and tight-box annotation;
5. strategy comparison and transform sanity report.

This pilot must remain small and quick. Stop for developer review before creating the full gold set.

## Last Updated

2026-07-26
