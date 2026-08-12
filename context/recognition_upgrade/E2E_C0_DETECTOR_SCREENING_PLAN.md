# E2e-C0 Independent Hand-Detector Screening Plan

## Purpose

Define the smallest defensible experiment that determines whether an independent single-class
hand detector can recover the visible hands that MediaPipe misses, without first training another
recognizer or changing Android.

## Scope

This plan governs offline detector screening only. It does not authorize production Android
changes, recognizer training, schema 3.0 changes, replacement of MediaPipe landmarks, or detector
fine-tuning before the transfer-screen gate passes.

## Current Status

APPROVED / N0-P1 CAPTURE COMPLETE / C0-A PREFLIGHT NEXT.

Last updated: 2026-07-27.

## Verified AppHear Evidence

- The corrected positive gold run is
  `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/`
  `e2e_all_hand_gold_v1/engineering_01`.
- It contains 150 unique ASL Citizen clips, 41 signers, 184 visible hand instances, 117
  hand-visible frames, and 67 two-hand frames.
- MediaPipe IMAGE achieved 122/184 = 66.30% hand-instance recall and 31/67 = 46.27% complete
  two-hand recall.
- Recall was 70/120 = 58.33% for motion-blurred hands, 8/31 = 25.81% for edge-clipped hands,
  and 13/25 = 52.00% for occluded hands.
- The gold review and raw center images already contain normalized hand boxes and do not depend on
  MediaPipe handedness.
- The 33 zero-hand frames inside sign spans are not a representative non-signing negative set.
- The project environment currently has Python 3.11.5, TensorFlow 2.21.0, MediaPipe 0.10.35, and
  no PyTorch, torchvision, ONNX, LiteRT conversion, or detector-training packages.
- Existing AppHear Android processing is already perception-bound. Any promoted detector must be
  sparse/asynchronous and cannot assume a GPU delegate.

Source result: `E2E_ALL_HAND_GOLD_RESULT.md`.

## External Evidence And Plan Correction

The older `E2E_MEDIAPIPE_RELIABILITY_PLAN.md` named EfficientDet-Lite0/Lite1 as the deployment
baseline. Current Google documentation instead lists MediaPipe Model Maker detector variants based
on MobileNetV2 and MobileNet MultiHW AVG. The official path supports COCO/PASCAL input, direct
`.tflite` export, INT8 quantization-aware training for CPU, and Android MediaPipe Object Detector
integration.

Google's published Pixel 6 example benchmark is dataset-specific and is not an AppHear latency
claim:

| Official Model Maker variant | Input | Example INT8 CPU latency | Example INT8 size |
|---|---:|---:|---:|
| MobileNetV2 | 256x256 | 16 ms | 3.2 MB |
| MobileNetV2 I320 | 320x320 | 33.38 ms | 3.3 MB |
| MobileNet MultiHW AVG | 256x256 | 19 ms | 3.6 MB |
| MobileNet MultiHW AVG I384 | 384x384 | 41 ms | 3.6 MB |

These numbers justify screening the 256 and 320 variants, but AppHear must measure its own models
and devices.

HaGRIDv2 provides hand boxes across a large subject set and publishes a YOLOv10n hand detector. It
is useful as a no-training transfer reference. Its static-gesture domain differs from ASL Citizen,
so AppHear results decide whether it transfers.

Ultralytics states that its code and trained models are AGPL-3.0 by default. A YOLO checkpoint may
therefore be used only as a technical research reference unless AppHear's distribution and
licensing are explicitly resolved. It is not the default production choice.

NanoDet-Plus is Apache-2.0 and publishes small mobile/Android ncnn paths. It remains a fallback,
not the first candidate, because it introduces a second Android runtime and an older training
environment.

Primary sources:

- Google detector customization:
  https://developers.google.com/edge/mediapipe/solutions/customization/object_detector
- Google Android Object Detector:
  https://developers.google.com/edge/mediapipe/solutions/vision/object_detector/android
- HaGRID WACV paper:
  https://openaccess.thecvf.com/content/WACV2024/html/Kapitanov_HaGRID_--_HAnd_Gesture_Recognition_Image_Dataset_WACV_2024_paper.html
- HaGRID repository: https://github.com/hukenovs/hagrid
- NanoDet-Plus: https://github.com/RangiLyu/nanodet
- Ultralytics licensing: https://www.ultralytics.com/license

## Architecture Decision

E2e-C0 is split into two gates.

### C0-A: No-Training Transfer Screen

Run a published HaGRIDv2 single-class hand detector on:

1. the frozen 150-frame AppHear positive gold set;
2. a new, manually verified no-visible-hand negative set;
3. a small diagnostic set containing visible hands during non-sign activities.

Purpose: determine whether an independent appearance detector materially recovers MediaPipe's
misses before AppHear invests in detector training data.

The published checkpoint is a research reference only. It cannot become a production asset unless
its complete code, weight, and dataset licensing is approved.

### C0-B: Production-Candidate Pilot

Run only if C0-A passes its transfer gate. Train two production-compatible candidates on identical
data:

1. MediaPipe Model Maker MobileNetV2 256, INT8;
2. MediaPipe Model Maker MobileNetV2 I320, INT8.

The 256 model is the latency baseline. The 320 model tests whether added hand pixels materially
improve blur, edge, and small-hand recall. MobileNet MultiHW AVG is deferred unless both fail for
an identifiable scale/aspect-ratio reason.

NanoDet-Plus-m 320 through ncnn is the fallback only if the Google path cannot meet recall or export
requirements and the extra runtime is explicitly approved.

## Dataset Contract

### P0: Frozen Positive Gold

- Use the existing 150 center images and final `gold_review.csv`.
- Never train or fine-tune on these images.
- Keep the existing review SHA-256:
  `53e3db0dceeeb4b5a991be132bdce1fe489d82d670daa662023f6707852835d9`.
- Use all 150 only for a threshold-free transfer report.
- If a score threshold is selected, use the 120 source-train frames for development and the 30
  source-validation frames once for confirmation. Report Wilson intervals explicitly.

### N0: Hand-Absent Detector Negatives

Create at least 20 clips of 30 seconds each, totaling at least 10 minutes:

- at least 6 people;
- at least 2 camera devices;
- at least 5 backgrounds/environments;
- front and back camera represented when available;
- ordinary clothing and varied lighting/distance.

Required clip groups:

- person/torso visible with both hands completely outside the image;
- face, hair, sleeves, and moving arms with hands still outside the image;
- empty/background scenes with moving objects;
- clutter and common hand-like objects.

Sample at 1 FPS, producing at least 600 candidate frames. Human review must quarantine every frame
containing any visible hand fragment. Split by whole clip, never by frame: 70% development and 30%
confirmation.

N0 measures detector false ROIs. Frames are correlated within clips, so report both frame-level
false-positive rate and clips-with-any-false-positive.

### P1: Visible Non-Sign Hands

Capture at least 5 additional minutes where hands are visible during ordinary actions such as
resting, holding a phone, pointing, adjusting clothing, or picking up objects. These are detector
positives, not N0 negatives. Sample and annotate a bounded 100-frame diagnostic set.

P1 does not gate detector false positives. It establishes whether the detector only recognizes
formal/static gestures and becomes later unknown/no-sign recognizer data.

## Prediction And Matching Contract

Each candidate emits sample ID, normalized box, confidence, model ID/hash, input size,
preprocessing transform, inference latency, and runtime/version. Anatomical Left/Right is not a
detector class and is not scored in C0.

For each threshold:

1. retain at most four single-class hand detections after registered NMS;
2. associate predictions and gold with exact maximum-cardinality one-to-one matching;
3. an availability match requires the predicted-box center inside the gold box and at least 50%
   of the predicted box area intersecting the gold box;
4. break equal-cardinality assignments by summed IoU;
5. separately report IoU >=0.50, IoU >=0.75, gold-box coverage, and expanded-crop containment.

The availability rule mirrors the existing palm-center-plus-coverage intent. IoU and containment
remain separate so an oversized or poorly localized detector cannot pass merely by finding the
general hand region.

## Threshold Protocol

- Emit raw predictions down to score 0.01.
- Sweep only on development data.
- Choose the highest-recall threshold satisfying N0 development frame false-positive rate <=2%.
- Break ties by complete two-hand recall, then IoU50 recall, then the higher threshold.
- Freeze threshold and NMS before confirmation.
- Do not retune after seeing confirmation results.
- Preserve the complete precision-recall/false-ROI curve.

## Metrics

Primary:

- visible hand-instance availability recall;
- complete two-hand frame recall;
- N0 frame false-positive rate;
- N0 clips with any false ROI.

Required diagnostics:

- any-hand frame recall;
- IoU50 and IoU75 recall;
- unmatched predictions per frame;
- motion-blur, edge-clipped, occluded, partial, near-face, one-hand, two-hand, q25/q50/q75, and
  source-split subgroups;
- confidence distributions for hits, misses, and false ROIs;
- p50/p95 desktop CPU latency, peak memory, model size, runtime, and preprocessing time;
- FP32-to-INT8 metric delta and output parity;
- builtin LiteRT/TFLite operator compatibility and metadata validity.

All proportions include numerator, denominator, and 95% Wilson interval.

## Gates

### C0-A Transfer Go

Advance to production-candidate training only if the locked detector:

- reaches at least 85% aggregate instance availability recall;
- reaches at least 70% complete two-hand recall;
- reaches at least 75% motion-blur recall;
- reaches at least 60% edge-clipped recall;
- keeps N0 confirmation frame false-positive rate <=2%;
- demonstrates usable rather than grossly oversized recovered boxes;
- has a technically credible mobile export path.

These screening gates require gains of approximately 19 points overall and 24 points on complete
two-hand frames over MediaPipe. They are not release gates.

### C0-B Production-Candidate Go

A trained INT8 candidate may advance to an isolated Android detector benchmark only if it:

- reaches at least 95% aggregate instance availability recall;
- reaches at least 90% complete two-hand recall;
- reaches at least 90% motion-blur recall;
- reaches at least 80% edge-clipped recall;
- keeps N0 confirmation frame false-positive rate <=2%;
- reaches at least 85% IoU50 recall;
- loses no more than 1 percentage point from FP32 to INT8;
- uses builtin LiteRT/TFLite operators without Select TF Ops;
- is no larger than 5 MB INT8;
- has deterministic preprocessing and output parsing.

Passing the small source-validation slice is not a production accuracy claim. A larger
signer/device confirmation set is required before Android integration.

## Stop Rules

- If C0-A is below 80% aggregate recall, evaluate an upper-body/full-frame RGB stream instead of
  immediately training a hand detector.
- If C0-A reaches 80-85%, review remaining failure groups before deciding whether AppHear-domain
  fine-tuning is justified.
- If C0-A passes but both C0-B candidates fail after one controlled training round, do not perform
  repeated hyperparameter search on the 150-frame gold set.
- If the only passing candidate has unresolved production licensing, treat the result as evidence
  that detection is feasible, not as permission to ship that model.
- E3 remains blocked until a production-compatible INT8 detector passes C0-B.

## Execution Order

1. Approve this contract and resolve whether AppHear will remain proprietary or can satisfy AGPL
   obligations for research tooling.
2. Capture N0 and P1 raw videos. Preserve originals and metadata.
3. Build a deterministic sampler and simple human review workflow for N0/P1.
4. Freeze reviewed manifests and hashes.
5. Acquire and hash the HaGRID reference checkpoint in a separate experiment environment.
6. Run a six-positive/twenty-negative smoke test.
7. Run C0-A on the fixed positive and negative sets. This is inference-only, not a long training
   process.
8. Review C0-A and make a go/no-go decision.
9. Only after a go, prepare the RTX 3050 detector-training handoff for C0-B.
10. Only after C0-B passes, build a separate default-off Android detector benchmark.

The user runs any long download, extraction, or training command after reviewing its package and
estimated duration.

## Expected Outputs

All files go under `artifacts/recognition_upgrade/e2e_c0/<run_id>/`:

- `provenance.json`;
- `positive_manifest.csv`;
- `negative_manifest.csv`;
- `predictions/<candidate>.jsonl`;
- `threshold_curve.csv`;
- `metrics.json` and `metrics.md`;
- `failure_panels/`;
- `latency.json`;
- `export_report.json`;
- `decision.md`.

No output may be written into Android assets, production run folders, or the frozen gold source.

## Risks And Fallbacks

- **Domain transfer failure:** HaGRID is primarily static gesture imagery. Inspect whether misses
  are ASL-specific blur/edge/crossing cases before training.
- **Gold-set reuse:** repeated tuning would invalidate it. Use the development/confirmation split.
- **Negative contamination:** a visible fingertip makes an N0 frame positive. Human review must
  quarantine it.
- **Licensing:** research weights may be unusable in production. Production candidates use the
  approved Google path and preserve third-party manifests.
- **Mobile cost:** detector gains may erase application FPS. Fallback to sparse detection plus
  tracking, smaller input, or full/upper-body RGB redesign.
- **Box localization:** independent IoU and crop-containment gates prevent oversized-box passes.
- **Small confirmation split:** treat C0 as screening and expand confirmation before deployment.

## Architecture Decisions

- E2E-C0-ADR-001: Run a no-training transfer screen before detector fine-tuning.
- E2E-C0-ADR-002: Keep detector class side-independent (`hand` only).
- E2E-C0-ADR-003: Separate true hand-absent negatives from visible non-sign hands.
- E2E-C0-ADR-004: Use current Google MobileNetV2 detector variants as production candidates.
- E2E-C0-ADR-005: Use published YOLO hand weights only as a license-constrained reference.
- E2E-C0-ADR-006: Keep NanoDet/ncnn as a fallback requiring an explicit runtime decision.
- E2E-C0-ADR-007: Do not train or tune on the frozen 150-frame positive gold set.
- E2E-C0-ADR-008: Do not unblock E3 until a production-compatible INT8 detector passes.

## Assumptions

- Raw videos and gold annotations remain available at their recorded paths.
- The HaGRID reference checkpoint can be obtained with acceptable research-use terms.
- At least six people and two devices can contribute bounded N0/P1 fixtures.
- Current gold boxes are accurate enough for screening after adjudication.

## Open Questions

- Is AppHear intended to remain proprietary, making AGPL artifacts unsuitable for production?
- Who can contribute N0/P1 recordings and approve their research use?
- Does the HaGRID checkpoint expose stable hand-only boxes and confidence scores?
- How much AppHear-domain detector training data is required after transfer screening?
- Will Model Maker 256 or 320 preserve small/blurred hand detail after INT8 QAT?
- Can a promoted detector run sparsely without losing hands between calls?

## Source-Of-Truth Files

- `E2E_ALL_HAND_GOLD_RESULT.md`
- `E2E_MEDIAPIPE_RELIABILITY_PLAN.md`
- `EXPERIMENT_MATRIX.md`
- `EVALUATION_AND_ACCEPTANCE_GATES.md`
- `ANDROID_DEPLOYMENT_PLAN.md`
- `ROLLBACK_AND_COMPATIBILITY_PLAN.md`
- `pipeline/tracking/e2e_gold.py`
- `pipeline/tracking/e2e_gold_review.py`
- `pipeline/tracking/e2e_gold_audit.py`

## Related Context Files

- `README.md`
- `E2E_C0_CAPTURE_RUNBOOK.md`
- `E2E_C0_CAPTURE_RESULT.md`
- `ARCHITECTURE_DECISIONS.md`
- `RISK_REGISTER.md`
- `OPEN_QUESTIONS.md`
- `IMPLEMENTATION_READINESS_CHECKLIST.md`
- `../eval-protocol.md`
- `../runtime-constraints.md`
- `../progress-tracker.md`

## Next Required Action

Freeze the passed N0/P1 manifests, resolve the HaGRID reference checkpoint licensing and exact
artifact, then prepare the isolated six-positive/twenty-negative C0-A smoke. Do not train
detectors, start E3, or modify Android.
