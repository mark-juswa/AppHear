# E6-3 Frozen-Embedding Open-Set Rejection Plan

**Purpose:** Define one non-duplicative experiment that tests whether the frozen five-sign v3.0
recognizer can reject unsupported/no-sign inputs and unsafe known-class confusions without changing
its classifier, feature schema, training data, or Android behavior.

**Scope:** Offline diagnostic only. No classifier training, schema change, RGB, specialist, TFLite
export, Android integration, production asset replacement, or vocabulary expansion.

**Current status:** ARCHITECTURE REVIEW COMPLETE / PACKAGE AND REAL-DATA SMOKE PASS / FULL RUN PENDING.

**Last updated:** 2026-08-09.

## Decision In One Sentence

Run one frozen-embedding comparison using the three repaired-validation v3.0 TCN seeds: retain
maximum-softmax probability as the historical control, add energy as a post-logit control, and test
one primary candidate, predicted-class shrinkage-Mahalanobis distance over the frozen 64-dimensional
TCN embedding.

Do not retrain a binary gate, shared accept head, one-vs-rest head, primary classifier, or E6-2
geometry model in E6-3.

## Exact Problem

### Verified project evidence

- The frozen five-sign v3.0 control has fresh top-1 `0.8889`, but fresh `KNOW` recall is `0.5611`
  and variant-stress `KNOW` is approximately `0.0222`.
- E6-2 improved fresh recognition but did not resolve variant-stress `KNOW -> HELLO`; `75/90`
  stress `KNOW` predictions remained `HELLO`.
- E4-T and E5-H showed that softmax confidence/margin thresholding cannot provide both safe
  precision and useful coverage.
- E5-I's one shared learned accept head was too blunt: it produced zero-recall supported classes
  and did not pass accepted-precision/coverage gates.
- E4-AG already demonstrated a separate learned temporal signing/no-sign gate on a small captured
  domain. E6-3 must not repeat that experiment.

### Engineering inference

The next unresolved question is not whether another closed-set classifier can improve top-1. It is
whether examples that the classifier maps to a supported label nevertheless lie far from that
label's learned training distribution. This is especially relevant to the stable stress
`KNOW -> HELLO` error.

### Hypothesis requiring experimentation

A class-conditioned distance in the frozen encoder space may reject OOV/no-sign windows and stress
`KNOW` examples that softmax assigns to `HELLO` with high confidence. It will fail if those examples
are embedded inside the genuine `HELLO` distribution.

## Duplicate Experiment Audit

| Proposed E6-3 element | Closest previous work | Similarity | Meaningful difference | Re-run justification | Decision |
|---|---|---:|---|---|---|
| MSP/confidence score | E4-T, E5-H | `95%` | Same score, new frozen five-sign data | Control only; no claim of novelty | include as baseline only |
| Energy score | E4-T, E5-H | `55%` | Uses pre-softmax logit energy rather than normalized probability/margin | Cheap post-hoc comparator; not previously measured in AppHear | proceed as control |
| Predicted-class Mahalanobis | E5-I | `35%` | Frozen penultimate embedding, class-conditioned positive density, no learned shared accept head and no classifier retraining | Directly tests the failure mode E5-I could not represent | proceed as primary candidate |
| Binary temporal signing gate | E4-AA through E4-AG | `100%` | None sufficient | Already exhausted and E4-AG passed its bounded offline gate | skip |
| Shared accept/reject head | E5-I | `100%` | None sufficient | Already failed | skip |
| One-vs-rest learned rejectors | unimplemented E5-J proposal | `50%` | Would be class-conditioned but adds learned parameters and negative-set overfit risk | Not needed until the simpler frozen-distance test fails | postpone |
| OpenMax/EVT tail fitting | no direct AppHear run | `45%` | Class-tail Weibull calibration in activation space | Too data-sensitive for roughly 30 validation positives per class | postpone |
| E6-2 geometry embedding rejection | E6-2 | `70%` | Would use the no-go `[96,444]` model | Confounds representation and rejection; violates independent-stage design | skip in E6-3 |

## Frozen Inputs

- Model family: three latest checkpoints from
  `artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_transfer_repaired_val_01`.
- Seeds: `101`, `202`, `303`; no best-seed selection.
- Primary feature contract: immutable schema v3.0 `[96,258]`.
- Vocabulary order: `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW` from the frozen run manifest.
- Positive train: `535` repaired-assignment clips.
- Positive calibration validation: `166` repaired signer-complete clips.
- Positive variant stress: `163` preserved clips, evaluation-only.
- Fresh positive diagnostic: `300` clips from one inspected AppHear signer, evaluation-only.
- Historical positive diagnostic: `63` reused ASL Citizen clips, reported separately.
- Historical development negatives: `547` lineage-assigned windows.
- Provisional fresh negatives: `560` windows from one signer, evaluation-only.

Negative subtype reporting is mandatory: `N0_NO_HAND`, `P1_IDLE_HANDS`, `P1_FACE_ADJACENT`,
`P1_ACCIDENTAL_MOTION`, `TRANSITION_PARTIAL`, and `OOV_SIGN`.

## Data Role Rules

1. Fit class means and covariance from positive `train` embeddings only.
2. Select score direction, operating threshold, and any fixed temperature using only repaired
   positive `val` plus the `547` historical development negatives.
3. Do not use variant stress, fresh positives, historical positives, or fresh negatives to fit or
   select thresholds.
4. Report variant stress, fresh positive, historical positive, and provisional fresh negative
   results independently; never average them into one headline number.
5. Preserve all sample IDs, raw-video lineage, negative subtype, source, and signer group in every
   prediction row.
6. Because negative assignments identify sampled frames, construct each 96-frame causal window
   using the same v3.0 extraction/resampling contract centered or ended at the recorded timestamp
   as preregistered by the package. Never treat a single still frame as a 96-frame sequence.

## Frozen Embedding Contract

- Source layer: final temporal encoder output immediately before the five-class dense head
  (`tcn3_add` in the frozen model).
- Per-frame shape: `[96,64]`.
- Clip embedding: masked mean across real sequence frames only, output `[64]`.
- Padding mask: derived from the existing sequence lengths/metadata; zero-padded frames must not
  affect the mean.
- Primary class prediction: unchanged existing masked mean of per-frame softmax probabilities.
- Rejection score never changes the predicted class; it only returns `accept` or `reject`.

The package must fail closed if a model lacks the expected layer, has a different vocabulary,
cannot reproduce its original frozen predictions, or lacks reliable sequence-length metadata.

## Scoring Methods

### Historical baseline: maximum softmax probability

`score_msp = max(mean_t(softmax(logits_t)))`

This establishes the E4-T/E5-H analogue on the repaired five-sign benchmark. It is not a new
candidate and cannot be selected merely because a new threshold happens to look better.

### Post-logit control: energy

At fixed `T=1`, compute masked mean logit energy before softmax. No temperature sweep is allowed in
this phase. Energy is included because softmax normalization can remain overconfident for inputs
outside the training distribution.

### Primary candidate: predicted-class shrinkage Mahalanobis

For frozen clip embedding `z`, predicted class `c`, class mean `mu_c`, and pooled within-class
regularized covariance `Sigma`:

`d_c(z) = (z - mu_c)^T Sigma^-1 (z - mu_c)`

- Estimate one pooled covariance from positive training residuals.
- Use deterministic Oracle Approximating Shrinkage (OAS); no covariance grid search or new
  dependency.
- Score only the primary predicted class, not the nearest class, so rejection cannot silently
  rewrite recognition.
- Fit one global standardized operating threshold first. Per-class thresholds are permitted only
  as a preregistered fallback if global calibration fails and each class has adequate validation
  support; they must be reported as a separate result, not substituted silently.

## Threshold Selection

For each method and seed, evaluate a deterministic set of thresholds induced by development-score
values. Select the highest positive coverage subject to all development constraints:

- accepted precision `>=0.95`;
- positive coverage `>=0.80`;
- development no-sign false-accept rate `<=0.02`;
- development OOV false-accept rate `<=0.05`;
- accepted recall for every supported class `>=0.70`.

If no threshold satisfies all constraints, the method has no valid operating point for that seed.
Do not relax the constraints after seeing fresh evaluation results.

## Required Metrics

- accepted precision and positive coverage;
- accepted recall per supported class and minimum-class accepted recall;
- false-accept rate overall and by negative subtype;
- AUROC, AUPR-in, AUPR-out, and FPR at 95% true-positive rate;
- coverage-risk curve and area under it;
- ECE and Brier score for the frozen closed-set prediction;
- stress `KNOW -> HELLO` count before rejection, accepted false-commit count after rejection, and
  retained correct-stress `KNOW` count;
- per-seed result, mean, minimum, standard deviation, and threshold;
- runtime estimate for score computation and serialized parameter size.

## E6-3 Go/No-Go Gate

E6-3 is promising only if **Mahalanobis**, on all three seeds and without test tuning:

1. has a valid development operating point;
2. reaches mean/min fresh accepted precision `>=0.95/0.93`;
3. reaches mean/min fresh positive coverage `>=0.80/0.75`;
4. keeps mean/min accepted recall for every stable fresh class (`GOOD`, `HELLO`, `SORRY`, `HAVE`)
   `>=0.85/0.75`;
5. keeps mean/min fresh `KNOW` accepted recall `>=0.50/0.40`;
6. keeps fresh OOV false-accept rate `<=0.05` and each non-OOV negative subtype `<=0.02`;
7. reduces accepted stress `KNOW -> HELLO` false commits by at least `70%` relative to the frozen
   classifier while retaining at least `30%` of correctly classified stress `KNOW` examples;
8. improves the precision-at-coverage frontier over MSP and the historical E5-I operating points;
9. adds no more than `25,000` arithmetic operations and `32 KiB` of parameters per window.

These are **diagnostic promotion gates**, not production-release gates. The fresh negative set has
one signer and short clips, so even a pass cannot authorize Android or a real-user claim.

## Stop Conditions And Failure Paths

- If Mahalanobis has no valid operating point in two or more seeds, E6-3 is a no-go.
- If it passes only by rejecting a supported class, E6-3 is a no-go; do not hide zero recall in an
  aggregate metric.
- If stress `KNOW` is close to the `HELLO` prototype and remains accepted, rejection cannot solve
  that confusion. Preserve the evidence for E6-4/E6-5 and stop threshold tuning.
- If only energy improves, preserve it as a diagnostic but do not promote without repeating the
  same gates on another untouched negative signer.
- If every method fails mainly on a negative subtype, specify the missing subtype/signer data and
  return to data collection rather than adding another rejector head.
- Do not run one-vs-rest, OpenMax, deep ensembles, or RGB as an automatic fallback. Each would need
  a separate duplicate audit and approval.

## Android Feasibility

E6-3 does not modify Android. A future Mahalanobis runtime would require only a 64-value mean per
class, one 64x64 inverse covariance, thresholds, and the already-computed encoder embedding. At five
classes this is roughly `20,480` multiply-accumulates and under `20 KiB` of float parameters, before
manifest overhead. This is an engineering estimate; device latency and parity remain unverified.

Future integration, if separately approved after E6-6, must use versioned rejection assets, a
default-off feature flag, fail-closed hash/schema checks, and fallback to the unchanged v3.0 path.

## External Research Evidence

- Bendale and Boult, OpenMax, CVPR 2016: open-set recognition should use activation-space class
  structure rather than relying only on softmax confidence.
  `https://openaccess.thecvf.com/content_cvpr_2016/papers/Bendale_Towards_Open_Set_CVPR_2016_paper.pdf`
- Lee et al., NeurIPS 2018: class-conditional Gaussian feature models and Mahalanobis confidence can
  be applied to pretrained classifiers without retraining the classifier.
  `https://proceedings.neurips.cc/paper_files/paper/2018/hash/abdeb6f575ac5c6676b747bca8d09cc2-Abstract.html`
- Liu et al., NeurIPS 2020: energy scores address failure modes of maximum softmax probability for
  OOD detection.
  `https://proceedings.neurips.cc/paper/2020/hash/f5496252609c43eb8a3d147ab9b9c006-Abstract.html`
- Hendrycks et al., ICLR 2019: diverse outlier exposure can improve OOD behavior, but AppHear E5-I
  shows that the current shared learned head is not sufficient evidence for that route.
  `https://openreview.net/references/pdf?id=S1V5wka7N`
- CrossMax, AAAI 2024: open-set skeleton action recognition remains difficult and benefits from
  explicit open-set evaluation; its multi-stream model is not adopted here because E6-2 did not
  justify that added complexity.
  `https://doi.org/10.1609/aaai.v38i5.28247`

External papers support testing these methods; they do not prove they will work on AppHear.

## Risks

- Fresh negative evaluation has one signer, so score separation may be person-specific.
- Historical development negatives and historical positives have been used in prior decisions.
- The 64-dimensional embedding was optimized for closed-set classification, not metric structure.
- Pooled Gaussian covariance may be a poor model of multimodal sign variants.
- Rejection can reduce false commits but cannot correct an accepted wrong class.
- Frame-index negative assignments require deterministic causal window reconstruction.
- Repeated inspection of stress/fresh results risks turning diagnostics into tuning sets.

## Protected Files

Do not modify:

- `pipeline/features/contract.py` or schema v3.0 extraction math;
- frozen E6 five-sign checkpoints and split artifacts;
- E6-2 geometry artifacts;
- production Android models, manifests, vocabularies, configuration, confirmation logic, or UI;
- raw ASL Citizen, local, AppHear, no-sign, and OOV videos.

## Source-Of-Truth Files

- `E6_2_LANDMARK_GEOMETRY_RESULT.md`
- `E4_T_ROUTER_SIMULATION_RESULT.md`
- `E5_H_CLEAN_7_ROUTED_SIM_RESULT.md`
- `E5_I_OPEN_SET_REJECT_HEAD_RESULT.md`
- `product_core_data_readiness/collection_targets_v1/E6_V30_REPAIRED_VALIDATION_TRANSFER_RESULT.md`
- `product_core_data_readiness/collection_targets_v1/E6_FIVE_SIGN_ASSIGNMENT_RESULT.md`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_validation_repair_01/repaired_assignment_manifest.csv`
- `artifacts/recognition_upgrade/product_core_data_readiness/e6_five_sign_assignment_01/assignment_manifest.csv`

## Related Context Files

- `README.md`
- `E6_PRODUCTION_RECOGNITION_ARCHITECTURE_PLAN.md`
- `EXPERIMENT_MATRIX.md`
- `EVALUATION_AND_ACCEPTANCE_GATES.md`
- `RISK_REGISTER.md`
- `ROLLBACK_AND_COMPATIBILITY_PLAN.md`
- `OPEN_QUESTIONS.md`

## Architecture Decisions

- Keep v3.0 as the frozen primary classifier.
- Test one frozen class-conditioned distance method before any learned rejection head.
- Use MSP and energy only as controls.
- Keep E6-2 geometry out of E6-3 to preserve independent attribution.
- Keep all fresh and stress views evaluation-only.
- Treat any result as diagnostic until additional untouched negative signers and long streaming
  sessions exist.

## Assumptions And Open Questions

- The frozen models expose a stable 64-dimensional `tcn3_add` tensor.
- Reconstructed negative windows can match v3.0 causal extraction semantics.
- It is unknown whether stress `KNOW` lies far from the genuine `HELLO` embedding distribution.
- It is unknown whether a shared covariance is adequate across all five signs.

## Next Required Action

The separate package and smoke are complete; see `E6_3_OPEN_SET_REJECTION_PACKAGE.md`. The user
runs the long negative extraction, frozen evaluation, and strict check next. Do not train any model
or modify production assets.
