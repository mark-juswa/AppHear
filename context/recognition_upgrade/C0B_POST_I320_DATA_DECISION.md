# C0-B0 Post-I320 Architecture And Data Decision

**Purpose:** Close the required post-I320 evidence review and decide whether the existing
independent hard-negative inventory justifies another bounded detector training round.

**Scope:** Context and experiment governance only. No extraction, annotation, training,
quantization, frozen evaluation, Android integration, or production replacement.

**Status:** Complete. **Do not retrain I320 with the currently available data. Retire
detector-derived hand-crop RGB as the immediate AppHear mobile route.**

**Last updated:** 2026-08-11.

## Verified Project Evidence

- The C0-B0 Stage 2 manifest contains `400` reviewed frames: `312` train and `88` development,
  with no signer or protected P0/N0/P1 path/hash overlap.
- The training split contains `53` no-hand frames; development contains `14`. These are primarily
  incidental no-visible-hand frames sampled from sign videos, not a dedicated diverse corpus of
  false-positive hand-like scenes.
- I320 is the stronger detector candidate, but at its valid development threshold it achieved
  `67.26%` hand availability, `41.03%` complete two-hand recall, and `63.72%` IoU50 recall.
- Lowering the threshold to recover at least `85%` availability produced `78.57%` no-hand frame
  false positives. This is a data/decision-boundary failure, not a small threshold error.
- The independent C0-B0 hard-condition scan examined the existing E6 negative manifest and found
  `547` development-negative rows, `0` independent rows, and `547` rows excluded because their
  lineage overlaps protected evaluation usage.
- Those `547` rows resolve to `244` present raw videos across `37` signer groups. Their existence
  does not make them training-eligible for C0-B0 because their prior protected roles must remain.
- The fresh provisional negative set contains `560` present raw videos but only one signer. It is
  reserved as `test_negative_fresh_provisional`, supplies zero development-gap credit, and cannot
  become detector training data without destroying its independent evaluation role.
- Frozen P0/N0/P1 fixtures have not been accessed by the I320 threshold evaluation.

## Decision

No bounded I320 retraining is authorized from existing data. Reusing protected E6 negatives would
create evaluation leakage; consuming the one-signer fresh set would remove the only fresh negative
control and still would not provide signer-diverse hard-negative training evidence. A generic
threshold, hyperparameter, or architecture sweep would repeat the failed C0-B0 question.

Per ADR-RU-058 and the registered C0-B0 stop rule:

- stop C0-B0 promotion;
- keep I320 and MobileNetV2-256 as research artifacts only;
- do not run QAT/INT8 or frozen P0/N0/P1 evaluation;
- do not integrate a detector or RGB branch into Android;
- retire detector-derived hand-crop hybrid as the immediate mobile route;
- preserve the frozen schema v3.0 `[96,258]` production recognizer unchanged.

This does **not** prove that detector-derived hand crops or RGB can never work. It proves that the
current independent data does not justify another controlled detector round. Reopening C0-B0
requires a separately approved collection with new raw-video lineage, multiple signers/devices,
dedicated hand-like hard negatives, and no overlap with any protected evaluation set.

## Acceptance Gate For Any Future Reopening

A future proposal must first demonstrate, before training:

- a new training-only hard-negative manifest with zero protected lineage overlap;
- multiple independent signers, devices, backgrounds, and lighting conditions;
- explicit no-hand, face/skin-like distractor, idle-hand, accidental-motion, edge, blur, occlusion,
  near-face, partial-hand, and two-hand coverage;
- a separate signer-disjoint development-negative set large enough for a meaningful `<=2%` false
  positive estimate;
- unchanged frozen P0/N0/P1 and fresh-negative evaluation roles;
- a preregistered single retraining round and stop rule.

No fixed sample count is asserted without a design and statistical justification.

## Assumptions And Unknowns

- **Verified project evidence:** the current I320 detector and current independent-data inventory
  fail the registered progression conditions.
- **Engineering inference:** materially broader hard-negative data could improve separation, but
  the likely gain and collection cost are unknown.
- **Hypothesis requiring experimentation:** a future detector trained on new hard negatives could
  pass both recall and false-positive gates.
- **Unknown:** even a passing detector may not improve sign recognition or meet Android thermal
  and latency limits.

## Source Of Truth

- `C0B_STAGE2_DEVELOPMENT_RESULT.md`
- `C0B_APPHEAR_HAND_ROI_FEASIBILITY_PLAN.md`
- `POST_E6_ARCHITECTURE_REVIEW.md`
- `ARCHITECTURE_DECISIONS.md`
- `artifacts/recognition_upgrade/e2e_c0/c0b_stage2_research_manifest_01/manifest_summary.json`
- `artifacts/recognition_upgrade/e2e_c0/c0b_stage2_detector_01/package_summary.json`
- `artifacts/recognition_upgrade/e2e_c0/c0b_stage2_detector_01/development_evaluation/comparison_summary.json`
- `artifacts/recognition_upgrade/e2e_c0/c0b_condition_topup_scan_01/scan_summary.json`
- `artifacts/recognition_upgrade/e6_rejection/e6_3_frozen_embedding_01/dataset/negative_window_manifest.csv`
- `artifacts/recognition_upgrade/product_core_data_readiness/e6_negative_upload_review_01/review_summary.json`

## Next Required Action

Make an explicit product-scope/architecture decision while keeping the v3.0 baseline protected.
Do not start another recognition or detector model automatically.
