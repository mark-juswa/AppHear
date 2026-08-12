# E2e MediaPipe Reliability And Hand-ROI Plan

## Purpose

Define the next bounded investigation after E2b, E2c, and E2d failed: separate hand detection
from anatomical hand identity, verify camera/mirror semantics, and select the least expensive
reliable hand-ROI architecture before RGB extraction or hybrid training.

## Scope

This is an architecture and experiment contract only. It does not authorize changes to production
Android, schema 3.0, MediaPipe settings, model assets, datasets, E3 training, or the recognizer.

## Current Status

ALL-HAND DETECTION ARM COMPLETE / MEDIAPIPE-SOLE-SOURCE NO-GO. The corrected 150-frame audit measured 66.30% visible hand-instance recall, 58.33% on blurred hands, and 46.27% complete two-hand recall. Coordinate and identity semantics remain unresolved but cannot recover missing instances. E3 remains blocked.

## Verified Project Evidence

- E2b: pose fallback raised availability from 53.3% to 79.2%, but the best recovered-crop
  usability was only 23.7%. See `E2B_PHASE_A_RESULT.md`.
- E2c: MediaPipe VIDEO improved target-hand availability by only 11.1, 4.5, and 7.5 percentage
  points at native, k4, and k8 cadence. See `E2C_TEMPORAL_TRACKING_RESULT.md`.
- E2d: no IMAGE/VIDEO threshold passed. VIDEO 0.3 reached 61.1%, 56.8%, and 62.5% target-hand
  recall but produced 7.5%, 12.5%, and 2.5% false target-hand ROIs. Latency passed. See
  `E2D_DETECTOR_OPERATING_POINT_RESULT.md`.
- `android/app/src/main/java/com/example/apphear/pipeline/FrameAnalyzer.kt` rotates the analysis
  bitmap and records front-camera state, but does not horizontally mirror the inference bitmap.
- `android/app/src/main/java/com/example/apphear/pipeline/recognition/LandmarkAdapter.kt`,
  `pipeline/extract/landmarks.py`, and `pipeline/tracking/e2c.py` directly map MediaPipe handedness
  labels into fixed Left/Right slots.
- MediaPipe's documented handedness convention assumes mirrored/selfie input and requires swapping
  output labels for unmirrored input. The exact CameraX/Tasks behavior must be verified with
  labeled fixtures before changing any feature contract.

## Engineering Interpretation

E2d proves that threshold and running-mode tuning alone is insufficient. It does not prove that
every target-hand miss is a palm-detector miss: a detected hand can be counted as unavailable when
handedness, camera mirroring, or anatomical slot assignment is wrong. The E2d no-go remains valid,
but anatomical left/right conclusions are provisional until the coordinate contract is audited.

## Selected Architecture

Use a detector-agnostic Hand ROI Manager:

`timestamped frame -> MediaPipe hand instances + pose -> camera-coordinate mapping -> anatomical
association -> causal tracking -> bounded pose fallback -> optional independent detector ->
left/right ROI records`

Each ROI record must eventually carry:

- anatomical side and assignment confidence;
- box coordinates in a declared coordinate space;
- source (`mediapipe`, `tracked`, `pose_refined`, `independent_detector`, or `upper_body`);
- source timestamp and age;
- detector/tracker confidence when available;
- visible/missing/stale/occluded/blur validity flags.

MediaPipe remains the preferred landmark provider when available. It is not the sole authority for
anatomical identity or crop availability.

## Ordered Experiments

### E2e-A - Coordinate And Identity Audit

Create a 120-200-frame gold set balanced across anatomical side, one/two hands, crossing,
occlusion, motion blur, native/k4/k8 cadence, front-camera clips, and unmirrored ASL Citizen
footage. Annotate every visible hand box, anatomical side, blur, occlusion, and coordinate
convention.

Compare without retraining:

1. current direct MediaPipe label;
2. swapped MediaPipe label;
3. pose-wrist/forearm assignment;
4. pose assignment plus causal temporal continuity.

Measure hand-box recall at IoU 0.50/0.75, identity accuracy, both-hands recall, ID switches,
crop containment, false/wrong/stale ROI rates, and p50/p95 latency.

Go gates:

- all camera/mirror coordinate fixtures correct;
- identity accuracy at least 98% overall and 95% in every side/camera subgroup;
- visible target-hand recall at least 95% overall and 90% in every cadence/blur subgroup;
- false ROI at most 2%;
- stale or wrong-hand ROI at most 1%.

If pose plus temporal assignment passes, retain MediaPipe and do not train another detector.

### E2e-B - Learned Pose ROI Refiner

Run only if identity is reliable but box recall fails. Fit a tiny train-signer-only MLP for ROI
center and scale from shoulder, elbow, wrist, hand anchors, depth, confidence, and motion. It is a
short-age fallback only and must not conceal missing or stale data.

### E2e-C - Independent Hand-Box Detector

Run only if E2e-A/B cannot pass ROI gates. Train a single-class `hand` detector; anatomical identity
must come from body geometry and time, not detector-side Left/Right classes.

Deployment baseline:

- EfficientDet-Lite0 or Lite1, INT8 TFLite;
- sparse asynchronous inference at approximately 5-8 Hz;
- causal tracking between detector calls;
- MediaPipe landmarks retained when available;
- upper-body/arm-hand crop as an explicitly marked final fallback.

Build a signer-disjoint gold set before training. Fine-tune on AppHear hard frames with blur,
occlusion, crossings, near-face hands, one/two hands, and no-hand negatives. Public datasets may
initialize the detector but cannot replace AppHear-domain validation.

## Rejected Immediate Actions

- Do not lower production thresholds: E2d rejected the recall/false-ROI trade-off.
- Do not promote VIDEO/LIVE_STREAM: E2c did not meet availability gates.
- Do not use longer stale holds: E2/E2b showed poor held/recovered crop usability.
- Do not train the hybrid recognizer while crops are systematically missing or wrong.
- Do not replace MediaPipe before E2e-A separates detector recall from identity errors.
- Do not change Android slots alone: a semantic fix requires a versioned offline/runtime contract,
  re-extraction, retraining, and skew tests.

## Android Feasibility

Association and tracking are small numerical operations. If a separate detector is required, it
must run asynchronously and sparsely so the approximately 15 FPS target is not replaced by detector
latency. Device acceptance requires sustained CPU/XNNPACK/INT8 measurement; GPU is not assumed.

## Architecture Decisions

- E2E-ADR-001: Resolve camera coordinates and anatomical identity before detector replacement.
- E2E-ADR-002: Treat MediaPipe hand results as unlabeled instances until association completes.
- E2E-ADR-003: Keep MediaPipe landmarks when valid, but remove it as a single point of failure.
- E2E-ADR-004: Use body geometry and temporal continuity for anatomical side.
- E2E-ADR-005: If needed, use a single-class mobile hand detector plus tracking.
- E2E-ADR-006: Every fallback exposes source, age, confidence, and missingness.

## Assumptions

- E2 known-visible frames are useful evidence but need corrected side/coordinate annotations.
- Pose wrists and elbows may support association; this is not yet proven.
- A sparse INT8 detector may fit Android budgets; device performance remains unverified.

## Open Questions

- What handedness semantics does the exact Tasks model produce for each AppHear camera path?
- How much E2d unavailability is detection failure versus slot-assignment failure?
- Can pose plus temporal association maintain identity during crossing and occlusion?
- If required, which Lite detector passes held-out recall and sustained device cost?

## Risks

- Incorrect gold anatomical labels would invalidate the first experiment.
- Preview mirroring may be confused with inference-pixel mirroring.
- Pose association can fail when wrists overlap or landmarks disappear.
- A detector may improve recall while adding false crops, thermal load, and annotation cost.
- Correcting semantics requires a new schema and retraining; silent slot changes are prohibited.

## Source Of Truth Files

- `E2B_PHASE_A_RESULT.md`
- `E2C_TEMPORAL_TRACKING_RESULT.md`
- `E2D_DETECTOR_OPERATING_POINT_RESULT.md`
- `android/app/src/main/java/com/example/apphear/pipeline/FrameAnalyzer.kt`
- `android/app/src/main/java/com/example/apphear/pipeline/recognition/LandmarkAdapter.kt`
- `pipeline/extract/landmarks.py`
- `pipeline/tracking/e2c.py`
- `../feature-schema.md`
- `../eval-protocol.md`

## Related Context Files

- `README.md`
- `CURRENT_PIPELINE_AUDIT.md`
- `ARCHITECTURE_DECISIONS.md`
- `HYBRID_FUSION_DESIGN.md`
- `ANDROID_DEPLOYMENT_PLAN.md`
- `EVALUATION_AND_ACCEPTANCE_GATES.md`
- `ROLLBACK_AND_COMPATIBILITY_PLAN.md`
- `RISK_REGISTER.md`

## Next Required Action

Architect E2e-C0: screen independent single-class hand-detector candidates on the corrected 150-frame gold set plus a dedicated non-signing negative set. Do not train the recognizer or modify Android. See `E2E_ALL_HAND_GOLD_RESULT.md` for the authoritative no-go metrics and gates.

## Last Updated

2026-07-26
