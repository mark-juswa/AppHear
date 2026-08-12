# C0-B0 Stage 2 Development Threshold Result

**Purpose:** Record the locked development-only comparison of the full-data MobileNetV2-256 and
MobileNetV2-I320 AppHear-domain hand detectors.

**Scope:** Internal research/development only. No frozen P0/N0/P1 access, quantization, Android
integration, production claim, or production recognizer replacement.

**Status:** Complete. Structural execution passed; detector acceptance is **NO-GO**.

**Last updated:** 2026-08-11.

## Verified Inputs

- Run: `artifacts/recognition_upgrade/e2e_c0/c0b_stage2_detector_01/development_evaluation`.
- Locked development split: `88` frames, `113` visible hand instances, `39` two-hand frames, and
  `14` no-hand frames.
- Candidates: full-data float `mobilenet_v2_100` and `mobilenet_v2_i320_100`.
- Raw score floor: `0.01`; maximum four detections per frame.
- Matching: exact maximum-cardinality one-to-one; prediction center inside gold and at least 50%
  predicted-area intersection; ties by summed IoU.
- Threshold rule: maximize availability recall while development no-hand frame FPR is `<=2%`.

## Selected Development Operating Points

| Metric | MobileNetV2-256 | MobileNetV2-I320 |
|---|---:|---:|
| Selected confidence | 0.7976 | **0.5517** |
| Hand availability recall | 57/113 = 50.44% | **76/113 = 67.26%** |
| Any-hand frame recall | 48/74 = 64.86% | **60/74 = 81.08%** |
| Complete two-hand recall | 9/39 = 23.08% | **16/39 = 41.03%** |
| IoU50 recall | 57/113 = 50.44% | **72/113 = 63.72%** |
| IoU75 recall | 41/113 = 36.28% | **48/113 = 42.48%** |
| Development no-hand FPR | 0/14 = 0% | 0/14 = 0% |
| Expanded crop containment | 49.56% | **62.83%** |
| Inference p50 / p95 | **29.9 / 34.7 ms** | 46.6 / 51.2 ms |

I320 is the stronger development candidate but does not pass the registered C0-A screening gates:
availability `>=85%`, complete two-hand `>=70%`, blur `>=75%`, and edge `>=60%`. I320 blur
availability is `13/17 = 76.47%`, but aggregate, two-hand, edge (`0/4`), and IoU metrics remain
insufficient. Sparse edge, near-face, partial, and no-hand denominators prohibit strong subgroup
claims.

## Threshold Tradeoff Diagnosis

The current failure is not solved by choosing a lower threshold:

- MobileNetV2-256 reaches maximum availability `91.15%` only with `92.86%` no-hand frame FPR.
- MobileNetV2-I320 reaches maximum availability `85.84%` only with `85.71%` no-hand frame FPR.
- Allowing one false-positive no-hand frame (`1/14 = 7.14%`, already above the gate) raises I320
  availability only to `75.22%`.
- At the first threshold where I320 reaches at least 85% availability, no-hand FPR is `78.57%`.

Verified interpretation: the detector can emit boxes for many missed hands at low confidence, but
the present training data/model cannot separate them from false hand-like detections. The gap is
therefore data/decision-boundary reliability, not a small threshold adjustment.

## Decision

- Keep I320 only as a research artifact and 256 as its latency control.
- Do not run QAT/INT8, frozen P0/N0/P1 evaluation, Android benchmarking, or integration.
- Do not perform a generic hyperparameter or threshold sweep; the registered controlled round has
  failed.
- Before any detector retraining, require a separately approved evidence review of independent
  hard-negative availability and whether a bounded new-data experiment is worth the cost.
- The original upper-body/full-frame RGB bypass was already exhausted by E3-B0/B1/B2/B3/C, so it
  must not be renamed and repeated as the automatic fallback.

## Risks And Unknowns

- Only `14` development no-hand frames: observed `0%` has a Wilson upper bound of about `21.5%`.
- No COCO small-object metric and too few edge/near-face/partial examples.
- Desktop CPU preprocessing and inference are not Android latency measurements.
- Better ROI detection still would not prove improved sign recognition without a later paired
  downstream experiment.

## Next Required Action

Completed in `C0B_POST_I320_DATA_DECISION.md`. The existing inventory does not contain an
independent, signer-diverse hard-negative set that justifies retraining. Stop C0-B0 promotion and
retire detector-derived hand-crop RGB as the immediate mobile route. Do not start another model
automatically.
