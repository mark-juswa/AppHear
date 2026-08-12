# C0-A HaGRID Preflight

## Purpose

Record the checkpoint, licensing, dependency, and smoke-test boundary for the C0-A no-training
HaGRID hand-detector transfer screen.

## Scope

This is offline research tooling only. It does not authorize Android integration, detector
training, recognizer retraining, feature-schema changes, or production model replacement.

## Current Status

COMPLETE / SMOKE RESULT RECORDED IN `C0A_HAGRID_SMOKE_RESULT.md`.

Last updated: 2026-07-28.

## Verified Project References

- Positive fixture: `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/e2e_all_hand_gold_v1/engineering_01`.
- N0 fixture: `artifacts/recognition_upgrade/e2e_c0/n0_capture_06`.
- P1 fixture: `artifacts/recognition_upgrade/e2e_c0/p1_capture_03`.
- C0-A script: `pipeline/tracking/e2e_c0_hagrid.py`.
- Isolated dependency list: `model/config/recognition_upgrade/c0a_hagrid_requirements.txt`.

## External Evidence

- HaGRIDv2 publishes hand-detector weights in the repository README. The listed hand-detector
  options include `YOLOv10x` and `YOLOv10n`; `YOLOv10n` is the small reference candidate.
- The HaGRID repository states that it provides pretrained models and that the hand detector
  `YOLOv10n` reaches 87.9 mAP on HaGRIDv2.
- HaGRID's repository dependency file pins a PyTorch-based environment (`torch==2.0.0`,
  `torchvision==0.15.1`) for its own codebase.
- Ultralytics' licensing page states that YOLO code and trained models are AGPL-3.0 by default
  unless an enterprise license is obtained.
- Google MediaPipe Model Maker object detection remains the production-candidate direction if
  C0-A passes; Google's current docs list MobileNetV2 and MobileNet MultiHW AVG detector variants,
  COCO/PASCAL loading, TFLite export, and INT8 QAT for CPU.

Sources:

- HaGRID repository: https://github.com/hukenovs/hagrid
- Ultralytics licensing: https://www.ultralytics.com/license
- Google detector customization: https://developers.google.com/edge/mediapipe/solutions/customization/object_detector
- Google Android Object Detector: https://developers.google.com/edge/mediapipe/solutions/vision/object_detector/android

## Architecture Decisions

- Use `YOLOv10n_hands.pt` only as a research transfer reference.
- Do not treat HaGRID/YOLO as a production Android candidate unless licensing and export are
  explicitly approved.
- First prepare a bounded six-positive/twenty-negative smoke manifest before full C0-A inference.
- Include P1 only as a diagnostic manifest; P1 is not a false-positive negative set.
- Keep all outputs under `artifacts/recognition_upgrade/e2e_c0/<run_id>/`.

## Assumptions

- The HaGRID `YOLOv10n_hands.pt` link remains accessible at run time.
- Ultralytics can load the downloaded `.pt` weight on the developer machine after installing the
  isolated requirements.
- C0-A smoke runtime is short enough for the developer to run manually.

## Open Questions

- Whether the persistent N0 false positives are true detector hallucinations or review edge cases still requires hard-case inspection.
- Whether an AppHear-domain mobile detector can avoid the same threshold tradeoff remains untested.
- Whether an upper-body/full-frame RGB fallback is a better next E3 route remains untested.
- Whether any YOLO/HaGRID result can legally move beyond research evidence remains unresolved.

## Risks

- Installing Ultralytics into the main AppHear `.venv` can disturb the TensorFlow/Keras pipeline.
- AGPL/licensing constraints can make technically good results unusable for proprietary production.
- Smoke detections can look promising but fail the full 150-frame positive and N0 false-ROI gate.
- Low thresholds can create false ROIs; threshold tuning on frozen confirmation rows would
  invalidate evaluation.

## Next Required Action

Read `C0A_HAGRID_SMOKE_RESULT.md` and `C0_DECISION_PACKAGE_PLAN.md`. Do not promote HaGRID YOLOv10n directly. Prepare the C0 route decision from the inventory results before any detector training, E3 training, or Android integration.

