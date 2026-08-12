# Evaluation And Acceptance Gates

**Purpose:** Define what â€œbetterâ€ and â€œreadyâ€ mean.
**Status:** PRE-REGISTERED PLAN. **Last updated:** 2026-07-25.

## Protocol

Signer-disjoint train/val/test; identity deduplication; val selects models/calibration/thresholds;
test is promotion-only. Report aggregate and per-signer with confidence intervals and three-seed
variation. The top-line remains end-to-end signed-phrase/gloss accuracy, not window accuracy.

## Required Metrics

- Top-1/top-3/top-5, macro precision/recall/F1, per-class support, worst-decile F1.
- Registered confusion groups and full confusion matrix.
- Prefix accuracy/coverage at 25/50/75/100%; early4/early6 for continuity with current reports.
- 4/6/8/12/15/native FPS; timestamp jitter; missing hand/pose/crop and modality dropout.
- Boundary frame F1, onset/release error in ms, segment IoU.
- Unknown/no-sign AUROC/AUPR, false commits per 30 minutes, accepted precision and coverage.
- NLL/Brier/ECE/reliability; temperature is fitted only on val. Temperature scaling evidence:
  https://proceedings.mlr.press/v70/guo17a/guo17a.pdf
- Device p50/p95 latency, processed FPS, memory, model size, battery, thermal decay, commit latency.
- Continuous phase: gloss WER and insertion/deletion/substitution; translation metrics only with
  human fluent-ASL review.

## Real-User Isolated Release Gates

- top-1 >=0.85 (0.90 preferred), macro-F1 >=0.85, worst-decile F1 >=0.75;
- accepted precision >=0.95 at coverage >=0.80; ECE <=0.05;
- 8-FPS top-1 drop <=5 points relative to native;
- boundary F1 >=0.85 and median onset/release error <=150 ms;
- no-sign/OOV false commits <=1 per 30 minutes;
- p95 commit latency <=750 ms after sufficient evidence;
- mid-range Android 12-20 FPS, p95 <80 ms, <20% throughput decay over 20 minutes;
- no signer subgroup collapse >10 points below aggregate without documented mitigation.

## Promotion Rules

Stage gates are conjunctive. Aggregate improvement cannot excuse a severe class, signer, unknown,
calibration, or thermal regression. A candidate that misses a gate stays experimental; vocabulary
may ship smaller rather than lower the gate.

## Decisions, Assumptions, Risks, Open Questions, Next Action

- **Decision:** precision and false commits outweigh raw coverage for real users.
- **Assumption:** 30-minute negative sessions can be collected.
- **Risk:** test overuse and underpowered signer confidence intervals.
- **Open question:** product-acceptable coverage/latency tradeoff with Deaf/HoH users.
- **Next action:** add user-reviewed operating-point requirements before release, not before E1.


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-018 apply; component-specific decisions in this document apply only after their experiment gate passes.
- **Assumptions:** Any forecast or unmeasured dimension remains a hypothesis, not a project fact.
- **Open questions:** Unresolved items are tracked in this document and `OPEN_QUESTIONS.md`.
- **Risks:** Applicable failure modes and fallbacks are tracked in this document and `RISK_REGISTER.md`.
- **Next required action:** Follow the explicit next action above and the ordering in `EXPERIMENT_MATRIX.md`; do not skip gates.


## Dynamic Mixed Acceptance Gates - 2026-07-31

The mixed recognizer must be evaluated as a routed decision system, not only as a classifier.

Additional gates:

- **Stable Tier-A sign gate:** each primary-path sign must pass per-class threshold, source-aware checks, and confusion checks before inclusion.
- **Router gate:** routing must improve accepted precision or reduce severe confusions without causing unacceptable coverage loss.
- **Specialist gate:** a specialist must beat the landmark-only group control and pass per-member thresholds; aggregate group accuracy alone is insufficient.
- **Reject gate:** uncertain hard signs must be rejected instead of committed when resolver confidence is insufficient.
- **No-sign/OOV gate:** false commits remain release blockers even if stable-sign accuracy is high.
- **System gate:** final reported metric is accepted end-to-end gloss precision/coverage on held-out signers, with no-sign sessions included.

A sign can be excluded from the production vocabulary even if it is part of the long-term product goal. Smaller accurate vocabulary is preferred over a larger misleading translator.

## Phase 1 Full-Vocabulary Evaluation Rules - 2026-08-11

- Select between production TCN and mask-aware TCN using validation only, with identical seeds,
  samples, augmentation, optimizer budget, and stopping rule.
- Supplemental train rows cannot share signer groups or raw hashes with validation, test,
  diagnostic, or replay roles.
- Do not use the `300` reused-positive diagnostic rows or `306` clean replay rows for model or
  threshold selection. Report them separately.
- Access protected test only after branch and checkpoint selection is frozen; never repeatedly tune
  against test after failed runs.
- Report top-1/top-5, macro and per-class F1, worst-decile F1, confusions, low-FPS and missing-data
  degradation, calibration, per-signer metrics, and available negative/replay false commits.
- Phase 1 is a research baseline and Phase 2 error registry, not an automatic release.
- P1-FV1 validation is a separate `evaluate-validation` command. It reports all 236 classes and
  the one-signer stress/reused diagnostics, then freezes a provisional branch winner. A protected
  test command will be added or authorized only after that report is reviewed.

### P1-FV1 Frozen Test Protocol - 2026-08-12

- Validation selected `production_streaming_tcn` before test access (`0.6712` mean top-1 versus
  `0.6614` for the mask-aware branch).
- `config/selection_freeze.json` binds the selected branch, all three best checkpoints, experiment
  config, validation metrics, and the 2,620-row test tensor by SHA-256.
- `evaluate-protected-test` requires `--confirm-protected-test-access`, creates an access receipt,
  and cannot overwrite completed test metrics. `--resume` is only for an interrupted access run.
- Primary reporting is native isolated-clip top-1/top-5, macro/per-class/worst-decile F1,
  calibration, per-signer accuracy, and confusion counts for each seed and the three-seed ensemble.
- Stride-2, stride-3, and deterministic 25% hand-block dropout are degradation proxies. They must
  not be described as measured Android FPS or natural detector-failure performance.
- This test cannot establish no-sign/OOV false commits, sign boundaries, phrase accuracy, device
  latency, or production readiness. Those remain separate blocked gates.

P1-FV1 completed with top-1 `0.6095`, macro-F1 `0.5964`, worst-decile mean F1 `0.1741`, and ECE
`0.2183`; therefore it fails the isolated real-user floors (`0.85`, `0.85`, `0.75`, and `0.05`).
The output remains an offline control and error registry. No recalibration, class weighting,
threshold selection, checkpoint change, or architecture tuning may use this test report. The ASL
Citizen test population has historical project reuse, so Phase 2 must distinguish regression
comparison from genuinely fresh signer/domain evidence.

## Phase 2 Pilot Gates - 2026-08-12

- ROI prerequisite: >=90% known-visible coverage, >=80% complete two-hand coverage, >=85% reviewed
  crop usability, and <=2% wrong/stale/anatomical-side-swap rate.
- Recognition branches A/B/C/D use identical signer folds, vocabulary, crop evidence, seeds
  101/202/303, optimizer budget, and validation selection rules.
- A promoted B/C/D branch must improve mean top-1 and macro-F1 by >=5 absolute points over frozen
  A, beat A on at least two seeds and in the mean, and limit stable-control F1 loss to <=2 points.
- Report top-5-to-top-1 rerank conversion, pre-registered confusion groups, zero/low-recall signs,
  per-signer minimum/spread, crop source/quality strata, model size, and CPU latency projection.
- The accessed Phase 1 ASL test is historical diagnostic evidence only. It cannot select Phase 2
  models or support a globally fresh claim. Fresh signer/domain evidence is required before scale.

### P2-P2 Measurement Contract

- P2-P2 uses 120 detector-independent train/validation frames: exactly three clips per pilot sign,
  balanced over 25/50/75% sign-span positions and preferring distinct signers.
- A human first annotates every visible hand, anatomical side, and blur/occlusion/near-face/edge
  condition. Route generation is blocked until this reference review is complete.
- R0/R1/R2/R3 are then evaluated on those exact frames. Route identity is blinded in the crop GUI.
  The panel shows before/center/after full frames and left/right crop triplets.
- Gold coverage uses normalized boxes and requires at least 90% of the visible gold-hand area inside
  its anatomically assigned ROI. Zero-visible-hand rows are excluded from crop-usability denominators
  but retain a false-ROI diagnostic.
- In addition to the registered gates, synchronization must pass on >=98% of frames at <=50 ms
  error and crop availability must be present on at least five of six route/side triplet cells for
  >=90% of reviewed frames. R3 is an availability control and cannot be promoted.
- A GO/NO-GO result is forbidden until both human reviews are complete and `evaluate` writes
  `p2_p2_final_result.json`.

### P2-P2 Gate Result

P2-P2 completed on 2026-08-12. No promotable route passed all gates:

| Route | Visible coverage | Complete two-hand | Reviewed usable | Wrong/stale/swap | Sync <=50 ms | Triplet consistency | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| R0 direct/hold | 74.74% | 55.41% | 74.14% | 0.86% | 100% | 50.83% | no-go |
| R1 pose recovery | 82.63% | 68.92% | 76.72% | 0.86% | 100% | 69.17% | no-go / best current route |
| R2 I320 | 62.63% | 50.00% | 48.28% | 0% | 100% | 29.17% | no-go |
| R3 upper-body control | 97.37% | 95.95% | 6.03% | 0% | 100% | 100% | non-promotable; availability without hand detail |

The developer reported uncertainty about fine-grained crop verdicts. Those usability values are
therefore provisional single-reviewer evidence, not strict ground truth. The no-go is nevertheless
robust: R1 fails the objective visible-coverage, complete-two-hand, and temporal-consistency gates
without using subjective failure labels. Four zero-hand gold frames were present; some other route
panels were marked `no_visible_hand`, confirming imperfect verdict interpretation.

Recovery correction: all 190 original gold boxes had anatomical side `unknown`, and the first
evaluator allowed an unknown-side ROI to be reused across gold hands. That result is superseded.
Scoring version `p2p2.strict_one_to_one.v2` uses exact one-to-one assignment, stores the prior JSON
as `p2_p2_final_result.superseded_nonunique_matching.json`, and blocks GO when anatomical-side
evidence is absent. At least 60 known-side gold hands and >=98% side accuracy are now required.

The corrected side review resolved all `40` selected frames (`80` hands). Strict route results are:

- R1: coverage `0.8158`, complete two-hand `0.6757`, anatomical-side accuracy `0.7750`;
- R2: coverage `0.6211`, complete two-hand `0.5000`, anatomical-side accuracy `0.6125`.

The strict non-deployable R1/R2 whole-route selector oracle reaches only coverage `0.8632`, complete
two-hand `0.7432`, and side accuracy `0.8000`. It selects R1 for `112/120` frames and R2 for only
`8/120`. It fails the registered `0.90`, `0.80`, and `0.98` geometry/side gates. Therefore no
deterministic selector implementation or 40-sign RGB dataset creation is authorized from P2-P2.
The former claim that the R1/R2 oracle crossed geometry gates is superseded.

A global side-convention counterfactual rejects a simple mirror-fix explanation. Swapping every
left/right route slot reduces R1 coverage from `0.8158` to `0.5316`, complete two-hand coverage from
`0.6757` to `0.3514`, and side accuracy from `0.7750` to `0.1000`. The recorded convention is the
better one for R0, R1, and R2. P2-P2 failure is therefore not repaired by globally reversing sides.
