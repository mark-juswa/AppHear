# Open Questions

**Purpose:** Record decisions that cannot be answered honestly without experiments or product input.
**Status:** OPEN / DYNAMIC MIXED ROADMAP CURRENT. **Last updated:** 2026-07-31.

## Technical Measurements

1. Why did the slim ST-GCN score 0.1588: architecture shortcuts, target/aggregation, masks, data,
   optimization, or implementation?
2. Can the full-capacity GCN overfit a small balanced slice and beat the TCN fairly?
3. Which independent single-class hand detector can materially close the corrected 66.30% MediaPipe instance-recall gap while preserving <=2% false ROI and Android export/cost feasibility?
4. If RGB returns later, does detector-derived hand-crop evidence outperform upper-body frozen-MobileNet features enough to justify mobile cost?
5. How many valid clips and signer-disjoint examples remain after validating the revised `E:\local` 12-sign supplementary set?
6. What reliable-first vocabulary size should E4-B use after E4-C, and what signs are product-critical despite weak current evidence?
7. Which classes need non-manual cues, and can sparse pose/head features solve them without face?
8. What right-context, if any, is acceptable for boundary accuracy?
9. Which TFLite ops/delegates sustain INT8 performance and calibration?

## Data/Product

10. Are all ASL Citizen/local/raw-video rights sufficient for RGB training and redistribution?
11. What demographics, fluency, handedness, and device metadata exist for local batches?
12. Which exact 50 signs form the pilot, including variants and unknown/confusion negatives?
13. Who provides fluent-ASL label/boundary review and user acceptance testing?
14. Is offline-only mandatory, or may a future opt-in cloud mode exist?
15. What coverage/latency tradeoff is acceptable to target users?
16. Can sufficient natural continuous ASL with gloss/text annotation be collected?

## Assumptions, Risks, Decisions, Next Action

- **Assumption:** none of these is silently resolved by this plan.
- **Risk:** future agents guess values and hardcode them.
- **Decision:** each answer must cite an experiment, source, or named product owner.
- **Decision:** user approved evaluating whether `E:\local` can replace the original E4-C recording words; metadata audit recommends `HELLO`, `YES`, `NO`, `SORRY`, `GOOD`, `BYE`, `HAVE`, `GET`, `GO`, `KNOW`, `MAKE`, and `WELCOME2` pending validation.
- **Next action:** answer the Phase 1 stable-candidate tiering questions in `DYNAMIC_MIXED_RECOGNITION_ROADMAP.md`; do not continue blind expansion.


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-018 apply; component-specific decisions in this document apply only after their experiment gate passes.
- **Assumptions:** Any forecast or unmeasured dimension remains a hypothesis, not a project fact.
- **Open questions:** Unresolved items are tracked in this document and `OPEN_QUESTIONS.md`.
- **Risks:** Applicable failure modes and fallbacks are tracked in this document and `RISK_REGISTER.md`.
- **Next required action:** Follow the explicit next action above and the ordering in `EXPERIMENT_MATRIX.md`; do not skip gates.








## Added After E4-L - 2026-07-30

17. Which overlapping ASL Citizen/local labels represent the same lexical variant versus different variants under the same English gloss?
18. Which source root is authoritative for local supplementary data if `E:\local` and `F:\ASL DATASET\local` differ?
19. What batch size of candidate signs can be screened on the user's CPU-only machine without turning the process into another long manual loop?
20. Should the first dual-source screen test only labels that exist in both sources, or rank overlapping and source-specific signs separately?
21. What minimum signer count per source is required before a candidate is called reliable rather than diagnostic?

## Added After E4-M - 2026-07-30

22. Can `HAVE` and `KNOW` improve vocabulary coverage without reducing held-out performance for the reliable core `GOOD`/`HELLO`/`SORRY`?
23. Are existing local feature counts for `HAVE` and `KNOW` enough for a fair source-aware screen, or do they only support a diagnostic preflight?
24. Should `GET` and `WELCOME2` be extracted immediately after E4-N, or only if E4-N shows dual-source training can preserve the core?


## Added After E4-Q And Dynamic Mixed Roadmap - 2026-07-31

25. What is the exact Tier-A stable candidate list after applying E4-N, E4-O, E4-P, and E4-Q evidence?
26. Should `SORRY` remain in the stable primary vocabulary, or should it be routed only through the `SORRY/BECOME/HELP` confusion group?
27. Can existing raw videos provide usable hand/body crops for `SORRY/BECOME/HELP`, or is new collection required?
28. What router threshold gives the best accepted precision/coverage tradeoff without user confirmation?
29. What no-sign/OOV dataset is sufficient for the first mixed recognizer simulation?
30. What is the smallest product vocabulary that is still useful while meeting strict accuracy gates?
31. Does the existing ASL Citizen + local inventory contain enough signer-disjoint data for a product-core batch, or is new collection mandatory before more model work?
32. Does the bounded E6-2 `[96,444]` hand-local shape, joint-angle, palm-orientation,
    head/body-relation, and mask contract improve fresh/stress `KNOW` over the frozen v3.0 control?
    Naive velocity/acceleration are excluded because E3-B6/B7 already tested them; true
    timestamp-aware motion remains deferred until authoritative timestamps are retained.
33. Can prototype/distance or one-vs-rest open-set rejection beat E5-I without overfitting to the current unsupported/no-sign rows?
34. Which E5 confusion groups are stable across seeds and sources, and which are artifacts of the current small splits?
35. Which confusion groups truly require RGB/visual evidence after landmark controls fail, and which require label/variant/data repair instead?

## Added After E6-2 And E6-3 Architecture Review - 2026-08-09

36. Does the frozen v3.0 `tcn3_add` embedding separate unsupported/no-sign inputs from the
    predicted class when softmax is overconfident?
37. Are variant-stress `KNOW` clips distant from the genuine `HELLO` class distribution, or
    embedded inside it?
38. Can one pooled shrinkage covariance remain stable across all three seeds and five classes?
39. Can frame-index negative assignments be reconstructed into causal 96-frame v3.0 windows
    without train/serve ambiguity?
40. What additional untouched negative signers and long streaming sessions are required if the
    diagnostic E6-3 gate passes?

Questions 36-39 are bounded by `E6_3_OPEN_SET_REJECTION_PLAN.md`. No production conclusion is
permitted from the current one-signer fresh negative set.

## Added After E6-4 / E6-5 Preparation - 2026-08-09

41. Does pair-restricting the frozen five-way primary already recover `KNOW`, indicating head
    competition rather than a missing representation?
42. Can the seed-matched v3.0 binary TCN recover both fresh and stress `KNOW` while preserving
    `HELLO` and historical ASL Citizen performance?
43. Does E6-2 geometry materially beat the simpler v3.0 specialist, rather than merely tying it?
44. Which completely untouched AppHear signer can validate a provisional E6-5 pass before any
    production claim?

Questions 41-43 are bounded by `E6_5_KNOW_HELLO_SPECIALIST_PLAN.md`. RGB, routing, export, and
Android remain out of scope for E6-5.

## Resolved By E6-5 - 2026-08-09

- Question 41: pair restriction did not recover `KNOW`; stress recall changed only `0.0222` to
  `0.0444`, and fresh/historical results were unchanged.
- Question 42: no. The v3 specialist failed fresh and stress `KNOW` gates.
- Question 43: no. Geometry improved fresh evidence but failed stress, minimum-seed, gain, and
  stability gates, so it did not justify complexity.
- Question 44 remains open and is required before any future production claim.

Current architecture question: after E6-2/E6-3/E6-5 no-go results, which future direction serves
the translator goal without repeating exhausted experiments? This requires explicit review; it is
not answered by E6.

## Post-E6 Architecture Review Resolution - 2026-08-09

The current architecture question is resolved by `POST_E6_ARCHITECTURE_REVIEW.md`: the only
materially unfinished prerequisite from the original hybrid plan is an AppHear-domain,
production-compatible hand detector. Crop-free upper-body RGB, landmark feature variants,
threshold/distance rejection, and the E6 specialist route must not be repeated.

45. How many independent training-only hand-box frames remain after excluding P0/N0/P1 and all
    overlapping source videos?
46. Can the deprecated-but-available MediaPipe Model Maker detector path be reproduced, exported
    to metadata-bearing INT8 TFLite, and reloaded through MediaPipe Object Detector?
47. Can an AppHear-domain MobileNetV2 detector pass the frozen recall, two-hand, blur, edge, IoU,
    and N0 false-ROI gates without exceeding a credible Android CPU budget?
48. If C0-B0 fails, what product scope can be honestly supported by the frozen v3.0 recognizer?

Questions 45-47 are bounded by `C0B_APPHEAR_HAND_ROI_FEASIBILITY_PLAN.md`. Question 48 is asked
only after a C0-B0 no-go.

## C0-B0 Stage 1 Partial Resolution - 2026-08-09

- Question 45 inventory portion is resolved: `42,251` independent candidate videos remain after
  registered protected exclusions. Accepted hand-box frame count remains unknown until annotation.
- Question 46 float wiring portion is resolved: `c0b_toolchain_smoke_03` completed one-epoch
  training, TFLite export, MediaPipe reload, and CPU/XNNPACK inference in the pinned Linux/Python
  3.10 environment. Reproducible INT8 export remains part of Stage 2.
- Question 47 remains fully open. The smoke made no detector-accuracy, threshold, quantization,
  latency, or Android-cost claim.
- Immediate open data question: does the 300-frame source/signer-balanced review contain enough
  two-hand, blur, edge, occlusion, near-face, small-hand, partial, and true-negative cases, and what
  targeted top-up is required?

## Phase 2 Preparation Open Questions - 2026-08-12

49. Can any registered R0-R3 route pass pilot-specific pixel crop availability, two-hand,
    usability, and wrong/stale/side-swap gates?
50. Are 550 synchronized ASL training clips across 40 signs sufficient for a shared pretrained hand
    encoder without repeating E3 RGB overfitting?
51. Which AppHear/local pilot rows can be re-extracted into a versioned timestamped RGB/landmark
    contract without contaminating protected or diagnostic roles?
52. Can RGB convert top-5 rescue into top-1 gains for `HAVE`, `MONEY1`, `PERSON`, `NOW`, `MOST`,
    `PAPER`, and `KNOW` while preserving the six stable controls?
53. Does quality-gated intermediate fusion beat top-k reranking, or does reranking provide the
    smaller and safer Android path?
54. Which genuinely fresh signers/domain recordings can support the Phase 2 scale-up claim now that
    the historical ASL test informed pilot selection?

