# C0 Route Decision Report

## Purpose

Compare the next recognition-upgrade routes after the HaGRID smoke no-go and select the highest-value
next experiment before any long extraction, training, or Android work.

## Scope

This is a decision report and experiment plan only. It does not authorize detector training, RGB
training, feature-schema changes, Android integration, production recognizer replacement, or reuse
of frozen evaluation fixtures for training.

## Current Status

COMPLETE - TWO-BRANCH COMPARISON APPROVED AS THE BEST VALUE PATH.

Last updated: 2026-07-28.

## Verified Inputs

- MediaPipe all-hand audit: `E2E_ALL_HAND_GOLD_RESULT.md`.
- C0 detector screening plan: `E2E_C0_DETECTOR_SCREENING_PLAN.md`.
- HaGRID smoke no-go: `C0A_HAGRID_SMOKE_RESULT.md`.
- Route inventory: `artifacts/recognition_upgrade/e2e_c0/c0_route_inventory_01/inventory.json`.
- P0 positive gold: 150 accepted frames, 117 visible-hand frames, 184 hand boxes, 41 signer IDs,
  150 unique clips.
- N0 no-hand fixture: 613 eligible no-hand rows from 57 clips, 6 participants, 5 devices, 5
  environments.
- P1 visible non-sign fixture: 108 eligible rows, 172 hand boxes, 30 clips, 2 participants, 2
  devices, 1 environment.
- Available raw roots: ASL Citizen and local video roots exist and contain large video collections.

## Current Evidence

MediaPipe is not reliable enough as the sole hand ROI source:

- aggregate hand-instance recall: 122/184 = 66.30%;
- complete two-hand recall: 31/67 = 46.27%;
- motion-blur recall: 70/120 = 58.33%;
- edge-clipped recall: 8/31 = 25.81%;
- occluded recall: 13/25 = 52.00%.

HaGRID YOLOv10n is not a direct replacement:

- at confidence 0.01: 5/6 positives detected, but 15/20 N0 false positives;
- at confidence 0.50: 4/6 positives detected, but 4/20 N0 false positives;
- at confidence 0.90: 0/20 N0 false positives, but only 1/6 positives detected.

The frozen P0/N0/P1 annotations are evaluation and diagnostic evidence. They are not enough to
approve detector training by themselves because training on them would contaminate the very gates
needed to judge the detector.

## Compared Routes

### Route A: AppHear-Domain Hand Detector Pilot

Train a production-compatible single-class `hand` detector using AppHear-domain positives and hard
negatives.

**Value:** High if it works. It directly targets the known MediaPipe missing-hand failure and could
restore reliable hand crops for the planned hybrid model.

**Blocking issue:** training data is not ready. Current high-quality boxes are mostly frozen gate
or diagnostic fixtures, not a training set.

**Development cost:** medium to high. Requires annotation inventory, additional boxes, training
pipeline, threshold protocol, export checks, and Android cost gates.

**Android fit:** potentially good if the Google/MediaPipe MobileNetV2 detector path works as INT8
TFLite, but unproven on AppHear data.

**Main risk:** after annotation and training, it may still fail edge/blur recall, false ROI, or
mobile latency.

**Decision:** do not start training yet. Keep this as Branch A, gated by a training-only annotation
inventory.

### Route B: Upper-Body / Full-Frame RGB Fallback

Evaluate an RGB stream that does not require reliable hand boxes. The input is signer-centered
upper-body or full-frame clips sampled from existing raw videos.

**Value:** High as an information-ceiling and bottleneck test. It answers whether RGB can improve
recognition without depending on MediaPipe or a new detector.

**Blocking issue:** needs a careful split and lightweight extraction package, but not hand-box
annotation before the first feasibility test.

**Development cost:** medium. Requires frame sampling, RGB tensor storage, small model smoke, and
strict signer-disjoint evaluation.

**Android fit:** uncertain. Full-frame RGB is likely heavier than a hand detector, so this is first
an offline feasibility branch, not an Android promise.

**Main risk:** overfitting signer/background cues instead of learning signs.

**Decision:** prepare this first because it can run from existing videos and answers the largest
architecture question quickly.

### Route C: Two-Branch E3 Comparison

Prepare Branch A and Branch B as controlled branches, then compare:

1. landmark-only TCN control;
2. upper-body/full-frame RGB branch;
3. detector/crop branch only if training-only detector data becomes available;
4. hybrid fusion only after a branch proves value.

**Value:** highest overall. It avoids betting the project on one ROI source and keeps every path
measurable.

**Blocking issue:** must be staged so complexity does not explode.

**Development cost:** medium now, high later if both branches advance.

**Android fit:** not decided until offline value and export/cost are measured.

**Main risk:** too many parallel experiments without tight gates.

**Decision:** selected, but staged. Start with RGB feasibility package while separately preparing
the detector training-data inventory.

## Final Decision

Use **Route C: staged two-branch comparison**.

The immediate executable path is:

1. **Branch B first:** prepare a no-training upper-body/full-frame RGB feasibility package using
   existing ASL Citizen/local videos.
2. **Branch A in parallel as inventory only:** count or prepare training-only hand-box annotation
   candidates, explicitly excluding frozen P0/N0/P1 gate frames.
3. Compare the first RGB feasibility result against the current landmark-only control before any
   detector training.

This is the best value path because it answers whether RGB can bypass the hand-ROI bottleneck while
not discarding the detector route. It also respects the current evidence: generic HaGRID detection
failed the smoke, but MediaPipe alone also remains below the ROI reliability needed for hand-crop
hybrid recognition.

## Next Executable Experiment

Prepare **E3-B0 Upper-Body RGB Feasibility Smoke**.

### Goal

Determine whether RGB video contains enough signer-independent signal to justify a full RGB or
hybrid branch before investing in detector training.

### Dataset

Use existing raw ASL Citizen/local videos only after verifying labels, signer IDs, and split
availability. MS-ASL remains optional and can be skipped for this first feasibility package.

### Minimum Package

- signer-disjoint train/validation/test split;
- small pilot vocabulary, preferably 25-50 signs with enough clips per sign;
- deterministic frame sampling, e.g. 16 or 32 frames per clip;
- upper-body/full-frame crop policy recorded in metadata;
- no use of frozen P0/N0/P1 detector gate frames for training;
- lightweight smoke model and one forward/training-step validation;
- output-only experiment folder under `artifacts/recognition_upgrade/e3_rgb_b0/`;
- user-run commands for any long extraction or training.

### First Gate

Before any full training, the package must pass:

- data paths resolve;
- signer split has no leakage;
- labels/classes are balanced enough for a pilot;
- frame sampler produces expected tensor shapes;
- one batch loads;
- one model forward pass works;
- one tiny training step writes outputs.

### Go Criteria For Full Pilot Training

Proceed to a bounded full pilot only if:

- at least 25 signs have enough signer-disjoint clips for a meaningful split;
- the smoke package is reproducible;
- the expected extraction/training duration is acceptable to the user;
- outputs stay isolated under the E3-B0 artifact directory.

## Detector Branch Hold Criteria

Do not train a detector until:

- training-only hand-box sources are identified;
- frozen P0/N0/P1 evaluation data is excluded or explicitly split by a new approved protocol;
- there are enough hard positives for blur, edge clipping, occlusion, two-hand interaction, and
  ordinary visible non-sign hands;
- there are enough hard negatives for N0-like no-hand false ROI control;
- the production runtime/export target is selected before training.

## Files That Must Remain Untouched

- Android production recognizer code and assets.
- Current `streaming.tflite`, vocab, manifest, and schema 3.0 assets.
- Frozen P0/N0/P1 review manifests except for read-only evaluation.
- Existing training/evaluation outputs outside new experiment directories.

## Architecture Decisions

- The next value experiment is staged two-branch comparison, not immediate detector training.
- Upper-body/full-frame RGB feasibility runs first because it can use existing videos and bypasses
  the current hand-box bottleneck.
- Detector training remains blocked until a separate training-only annotation inventory is approved.
- Hybrid fusion remains blocked until at least one RGB branch shows signer-independent value.

## Assumptions

- ASL Citizen/local videos contain enough labeled clips for a small signer-disjoint RGB pilot.
- A small pilot can reveal whether RGB helps before larger training is justified.
- Long extraction/training will be run by the user only after reviewing commands and estimated
  duration.

## Open Questions

- Which 25-50 signs have the best signer-disjoint support in the available local/ASL Citizen data?
- Should the first RGB input be full frame or simple signer-centered upper-body crop?
- What frame count and resolution fit the user's CPU-only machine and classmate RTX 3050 option?
- How much local data can be included without causing signer or label mismatch?

## Risks

- RGB feasibility may overfit backgrounds, clothing, camera style, or signer identity.
- Full-frame RGB may show value offline but be too expensive for Android.
- Detector training may still be required if RGB helps only when hands are visible and centered.
- A too-large pilot could become a long training task before the data contract is proven.

## Next Required Action

Prepare the E3-B0 RGB feasibility package plan and preflight script. The script should inspect class
counts, signer splits, video readability, estimated extraction cost, and a tiny tensor smoke. It
must not begin full extraction or training.

