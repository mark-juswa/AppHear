# C0-B0 AppHear-Domain Hand-ROI Detector Feasibility Plan

**Purpose:** Determine whether AppHear can create a reliable, Android-compatible hand-box source
without repeating MediaPipe tuning, HaGRID transfer smoke, or crop-free RGB experiments.

**Scope:** One gated detector experiment. It does not alter the recognizer, feature schema,
datasets in place, Android app, or production assets.

**Current status:** STAGE 1 INVENTORY, 24-FRAME REVIEW, AND PYTHON 3.10 LINUX
TRAIN/EXPORT/RELOAD SMOKE PASSED / CONDITION-BALANCED TRAINING DATA NOT READY / NOT APPROVED FOR
DETECTOR PILOT TRAINING. See
`C0B_STAGE1_READINESS_RESULT.md`.

**Last updated:** 2026-08-09.

## Closest Previous Experiments

| Previous work | Similarity | Meaningful difference in C0-B0 |
|---|---:|---|
| E2c/E2d MediaPipe mode and threshold sweeps | 35% | C0-B0 uses an independent appearance detector and does not alter Hand Landmarker thresholds |
| E2b pose ROI recovery | 20% | C0-B0 predicts hand boxes from RGB instead of extrapolating pose/old ROIs |
| C0-A HaGRID YOLOv10n smoke | 60% | C0-B0 is AppHear-domain fine-tuning with training-only positives/hard negatives and a production-compatible TFLite contract |
| E3-B0/B1/B2 upper-body RGB | 15% | C0-B0 detects boxes only; it does not classify signs from center crops |
| E3-B3/E3-C fusion | 10% | No sign-recognition or fusion model is trained |

## Exact Question

Can one small, single-class hand detector trained on independent AppHear-domain frames satisfy the
registered ROI availability and false-ROI gates after TFLite/INT8 export, with a credible Android
CPU cost?

## Inputs

### Training-only candidates

- Raw ASL Citizen and local/AppHear videos with traceable signer/source/video identity.
- Dedicated no-visible-hand and hand-like hard-negative frames that are not in frozen N0.
- Frames containing blur, edge clipping, occlusion, two-hand interaction, near-face hands, varied
  scale, lighting, background, device, and signer.
- Human-reviewed boxes for every visible hand; empty annotations for true no-hand frames.

### Frozen evaluation fixtures

- P0: corrected 150-frame all-hand gold set, including 184 visible hand instances.
- N0: `n0_capture_06`, 613 eligible no-visible-hand frames.
- P1: `p1_capture_03`, 108 eligible visible-hand/non-sign frames and 172 hand instances.

P0/N0/P1 may be read only for final evaluation. They must not be used for training, augmentation,
threshold fitting, early stopping, or model selection.

## Internal Stage 1: Data And Toolchain Readiness

Produce a versioned, hash-locked manifest with source video, frame timestamp, signer, device,
environment, split, box list, visibility attributes, reviewer status, and exclusion reason.

The readiness gate passes only if:

- every training frame traces to a raw video and file hash;
- no source video, signer-held-out evaluation unit, or extracted frame overlaps P0/N0/P1;
- positive and negative frames are both present;
- two-hand, blur, edge, occlusion, near-face, and small-hand cases are represented and counted;
- all boxes and empty-frame labels pass human review;
- a clean environment can train one tiny batch, export a metadata-bearing TFLite detector, reload
  it with MediaPipe Object Detector, and reproduce boxes within the declared tolerance;
- model and dataset licenses permit the intended use.

No universal minimum image count is asserted. Dataset sufficiency will be judged from diversity,
independence, and a preregistered learning curve, not an invented fixed number. If any readiness
condition fails, stop and report the exact annotation or toolchain gap.

## Internal Stage 2: Controlled Detector Pilot

Only after Stage 1 approval:

- train the documented MobileNetV2 256 detector as the latency branch;
- train MobileNetV2 I320 only as the resolution branch under the same data and budget;
- use signer/source-disjoint train and development partitions;
- fit confidence thresholds on development data only;
- measure a 25/50/100-percent learning curve using nested training subsets;
- export float and INT8 artifacts with metadata;
- run one locked evaluation on P0/N0/P1 after model and threshold selection.

Google documents these detector architectures and TFLite/INT8 export, but also marks MediaPipe
Model Maker as no longer actively maintained. Environment reproducibility and export are therefore
hard gates. A maintained compatible training stack may replace Model Maker only through a separate
architecture amendment proving identical MediaPipe Object Detector output and metadata contracts.

## Outputs

- immutable training/development manifest and overlap report;
- annotation coverage and quality report;
- dependency lock and toolchain preflight;
- float and INT8 model hashes;
- complete precision/recall/false-ROI curves from development;
- one locked P0/N0/P1 result;
- subgroup metrics for blur, edge, occlusion, near-face, small hand, and two-hand cases;
- desktop CPU latency, model size, and peak memory;
- decision report with no post-test threshold changes.

All outputs must live under a new `artifacts/recognition_upgrade/e2e_c0/` run directory.

## Acceptance Gate

Use the previously registered C0-B production-candidate gates:

- aggregate visible hand-instance availability recall `>=95%`;
- complete two-hand frame recall `>=90%`;
- motion-blur recall `>=90%`;
- edge-clipped recall `>=80%`;
- N0 frame false-positive rate `<=2%`;
- IoU50 recall `>=85%`;
- no material regression on P1 ordinary visible hands;
- INT8 export loads successfully with the MediaPipe Android-compatible Object Detector contract;
- projected CPU cost is credible enough to justify a later physical-device benchmark.

Passing these gates does not prove sign-recognition accuracy. It authorizes only the next
detector-derived crop-quality experiment.

## Failure Criteria

- leakage into P0/N0/P1 or missing raw-video lineage;
- insufficient independent training diversity;
- unstable/deprecated toolchain cannot be reproduced or exported;
- no threshold satisfies recall and N0 false-ROI gates;
- INT8 loss breaks a passing float result;
- model size or CPU projection is clearly incompatible with the runtime constraints.

## Rollback And Stop Rules

- The experiment creates new manifests and artifacts only; source videos and frozen fixtures remain
  unchanged.
- No Android asset receives the detector.
- Do not tune on P0/N0/P1 after the locked evaluation.
- Do not run repeated architecture searches after a no-go.
- On no-go, retire detector-derived hand-crop hybrid as the immediate route and preserve the frozen
  v3.0 production baseline.

## Assumptions And Hypotheses

- **Verified project evidence:** MediaPipe and HaGRID did not meet AppHear ROI reliability gates.
- **External research evidence:** Google documents MobileNetV2 detector customization, TFLite/INT8
  export, and Android Object Detector compatibility; the customization tool is deprecated but
  still available.
- **Engineering inference:** domain positives plus explicit hard negatives are the smallest
  meaningful change that directly addresses both missed hands and HaGRID false ROIs.
- **Hypothesis requiring experimentation:** this detector can meet C0-B gates within mobile cost.

## Source-Of-Truth Files

- `POST_E6_ARCHITECTURE_REVIEW.md`
- `E2E_C0_DETECTOR_SCREENING_PLAN.md`
- `E2E_ALL_HAND_GOLD_RESULT.md`
- `E2E_C0_CAPTURE_RESULT.md`
- `C0A_HAGRID_SMOKE_RESULT.md`
- `C0_ROUTE_DECISION_REPORT.md`
- `E6_COMPONENT_DECISION.md`
- `E6_0_BASELINE_FREEZE.md`

## Related Context Files

- `README.md`
- `TARGET_ARCHITECTURE.md`
- `MIGRATION_PHASES.md`
- `EXPERIMENT_MATRIX.md`
- `EVALUATION_AND_ACCEPTANCE_GATES.md`
- `RISK_REGISTER.md`
- `OPEN_QUESTIONS.md`
- `ROLLBACK_AND_COMPATIBILITY_PLAN.md`

## Risks

- Annotation workload may outweigh expected product value.
- The detector may learn background or skin-like false positives.
- Evaluation fixtures may be too small for narrow subgroup certainty.
- Passing ROI quality may still fail to improve sign recognition.
- A deprecated training package may become an ongoing maintenance liability.

## Open Questions

- Exact count and diversity of eligible training-only frames after overlap exclusion.
- Resolved: the pinned Linux/Python 3.10 Model Maker environment completed one-epoch training,
  TFLite export, MediaPipe reload, and CPU inference in `c0b_toolchain_smoke_03`.
- Whether the 256 branch is sufficient or the 320 branch is required for small/blurred hands.

## Next Required Action

Start Docker Desktop and run the Python 3.10 Linux Docker one-epoch TFLite export/reload smoke using
the reviewed `c0b_annotation_smoke_03` package. Stop on dependency/export failure. Do not prepare
annotation at scale or run detector candidate training automatically.
