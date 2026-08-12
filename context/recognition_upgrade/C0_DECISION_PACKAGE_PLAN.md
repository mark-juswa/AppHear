# C0 Decision Package Plan

## Purpose

Define the immediate next step after the HaGRID smoke no-go: choose whether AppHear should invest
in an AppHear-domain hand detector, shift to an upper-body/full-frame RGB fallback, or keep both as
bounded E3 branches.

## Scope

This is research, architecture, and experiment-planning only. It does not authorize detector
training, RGB recognizer training, Android integration, feature-schema changes, or production model
replacement.

## Current Status

PLANNED - NEXT ACTION AFTER C0-A HAGRID SMOKE NO-GO.

Last updated: 2026-07-28.

## Verified Project References

- MediaPipe all-hand result: `context/recognition_upgrade/E2E_ALL_HAND_GOLD_RESULT.md`.
- C0 screening plan: `context/recognition_upgrade/E2E_C0_DETECTOR_SCREENING_PLAN.md`.
- C0 capture fixtures: `context/recognition_upgrade/E2E_C0_CAPTURE_RESULT.md`.
- HaGRID smoke result: `context/recognition_upgrade/C0A_HAGRID_SMOKE_RESULT.md`.
- Positive gold run:
  `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/e2e_all_hand_gold_v1/engineering_01`.
- N0 run: `artifacts/recognition_upgrade/e2e_c0/n0_capture_06`.
- P1 run: `artifacts/recognition_upgrade/e2e_c0/p1_capture_03`.

## Decision To Make

The project needs one of three next directions:

1. **Detector Pilot:** train a production-compatible single-class hand detector with AppHear-domain
   positives and hard negatives.
2. **RGB Fallback:** avoid hand-box dependence for the next recognition experiment by using an
   upper-body/full-frame RGB stream.
3. **Two-Branch E3:** keep MediaPipe landmarks as the structured stream and evaluate detector crops
   versus upper-body RGB as two separate RGB branches before committing.

The current evidence does not support using HaGRID YOLOv10n directly.

## Candidate A: AppHear-Domain Hand Detector Pilot

### Input

- Training-only hand boxes from AppHear-domain frames.
- Existing P0/N0/P1 fixtures remain evaluation or diagnostic references unless explicitly split
  into development/confirmation according to the C0 contract.
- Additional training data must include ASL motion blur, edge clipping, occlusion, near-face hands,
  two-hand interaction, ordinary visible non-sign hands, and hand-like no-hand negatives.

### Output

- A single-class `hand` detector candidate with normalized boxes, confidence scores, model hash,
  preprocessing record, and export report.

### Recommended Model Family

Start with a Google/MediaPipe-compatible MobileNetV2 object detector path because Android
deployment and TFLite metadata are first-class requirements. Use the 256 input variant as the
latency baseline and 320 only if the 256 model misses small/blurred hands.

### Why It May Help

It directly targets the known ROI failure: MediaPipe IMAGE only reached 66.30% hand-instance recall
and 46.27% complete two-hand recall on the corrected all-hand audit.

### Main Risk

The training set may be too small or biased. A detector can improve hand recall but still create
false crops, cost too much on Android, or fail edge/blur cases after INT8 quantization.

### Approval Gate Before Training

Prepare a training-data inventory first:

- count available annotated AppHear-domain hand boxes;
- separate training-only sources from frozen gate sources;
- identify hard-negative counts;
- confirm signer/device/environment diversity;
- estimate annotation effort required for at least one controlled pilot.

Do not start training until this inventory is reviewed.

## Candidate B: Upper-Body / Full-Frame RGB Fallback

### Input

- Timestamped RGB frames or sampled clips centered on the signer.
- Optional MediaPipe pose/landmark availability masks, but no required hand-box crop.

### Output

- Frame-level or clip-level RGB features for the E3 landmark-vs-RGB-vs-hybrid comparison.

### Recommended Model Family

Use a lightweight mobile video/image backbone as an offline pilot encoder, then distill or replace
with a mobile-compatible model only if the branch shows recognition value. This is not a production
Android candidate until latency/export is measured.

### Why It May Help

It avoids making recognition fully dependent on precise hand boxes. It can preserve hand-shape,
body orientation, and gross motion even when MediaPipe or an independent detector misses a hand.

### Main Risk

Full/upper-body RGB models require more data, are more likely to overfit signer/background cues, and
may be too expensive for on-device real-time inference without compression or server assistance.

### Approval Gate Before Training

Prepare a small E3-style RGB feasibility package:

- exact sampled frame/window contract;
- signer-disjoint split;
- no frozen-gate leakage;
- baseline model size/cost estimate;
- one smoke overfit test and one held-out-signer sanity slice.

Do not train a full model before that package is reviewed.

## Candidate C: Two-Branch E3

### Input

- Current structured landmarks when available.
- Detector/MediaPipe crops when reliable.
- Upper-body or full-frame RGB fallback when crops are missing or low quality.

### Output

- A controlled ablation matrix: landmark-only TCN control, crop-RGB branch, upper-body RGB branch,
  and hybrid fusion.

### Why It May Help

It gives the project evidence instead of betting the whole upgrade on one ROI source.

### Main Risk

It increases experiment complexity and can hide data leakage or preprocessing mismatch if the
contracts are not frozen first.

## Recommended Immediate Next Step

Prepare the **C0 data inventory and route-decision report** before any training:

1. Count all existing AppHear-domain annotated hand boxes by source, signer, condition, and split.
2. Count no-hand and visible-non-sign negatives separately.
3. Identify which sources are frozen evaluation fixtures and must not be trained on.
4. Estimate how many additional boxes are needed for a minimal detector pilot.
5. Estimate the simplest upper-body/full-frame RGB pilot using already available raw videos.
6. Decide whether Candidate A, B, or C should be the next executable experiment.

## Architecture Decisions

- HaGRID YOLOv10n is retained only as a research baseline.
- Detector training is blocked until the data inventory proves enough training-only boxes exist or
  defines a bounded annotation task.
- E3 remains blocked until the ROI/RGB route is chosen.
- Android remains blocked until a candidate has offline metrics, export evidence, and cost bounds.

## Assumptions

- Existing raw frames and annotations are available at recorded paths.
- Additional annotation effort is possible if the inventory shows a shortage.
- The user will run long extraction/training processes manually after command review.

## Open Questions

- How many training-only hand boxes exist outside the frozen 150-frame gold and N0/P1 gate sets?
- Are ASL Citizen raw videos sufficient for an upper-body RGB pilot without MS-ASL?
- Should the detector pilot use local recorded clips, ASL Citizen boxes, or both?
- What is the minimum acceptable data volume before asking a classmate to run training?

## Risks

- Reusing frozen gate frames for training would invalidate C0 evaluation.
- A detector pilot can fail because of limited annotation diversity, not because detectors are
  fundamentally unsuitable.
- A full-frame RGB pilot can appear accurate by learning signer/background leakage unless splits are
  strict.

## Next Required Action

Run a local inventory-only scan over existing C0/P0/P1/N0 artifacts and available ASL Citizen/local
metadata. The scan must not extract frames, train models, or write outside
`artifacts/recognition_upgrade/e2e_c0/`.

