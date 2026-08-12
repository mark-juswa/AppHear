# Dynamic Mixed Recognition Roadmap

**Purpose:** Define the production-quality recognition architecture and research roadmap for a landmark-primary, confusion-aware AppHear recognizer.

**Scope:** Architecture, research planning, experiment sequencing, and documentation governance only. This document does not authorize Android implementation, TFLite export, production asset replacement, dataset mutation, or UI changes.

**Current status:** APPROVED DIRECTION / E5-H AND E5-I OPEN-SET ROUTING NO-GO. The roadmap remains landmark-primary and dynamic, but execution now moves to the E6 production-recognition architecture plan. Android integration remains blocked.

**Last updated:** 2026-08-03.

## Executive Decision

AppHear should move to a **dynamic mixed recognizer**:

`CameraX + MediaPipe landmarks -> primary landmark recognizer -> calibrated confusion router -> stable-sign commit OR specialist resolver OR reject/unknown -> sentence/UI`

The system remains landmark-primary because the completed experiments show the landmark path is not globally broken. The failures are concentrated in signer generalization, source/provenance mismatch, label/variant ambiguity, and specific similar-looking signs.

The system should not become hybrid everywhere yet. RGB/visual evidence should be introduced only where experiments prove that landmarks are insufficient, starting with registered confusion groups such as `SORRY/BECOME/HELP`.

## Evidence From Completed Experiments

### Landmark Path Still Has Value

- E4-J showed a limited 3-sign local core with `GOOD`, `HELLO`, and `SORRY` could reach strong latest-policy results: Conv1D latest mean test `0.9741`, min class `0.9333`.
- E4-N added `HAVE` and `KNOW` using dual-source existing features and passed: mean latest test `0.9774`, min core `0.9667`, min candidate `0.9286`.
- E3-C showed landmark features remained stronger than the attempted upper-body RGB and naive fusion design. Mean best validation/test: landmark augmented `0.5117/0.3867`, RGB-only `0.1500/0.0750`, fusion `0.2617/0.1867`.

### Landmark Path Has Clear Failure Modes

- E4-B strict 7-sign signer-disjoint training failed because train fit did not transfer to held-out data.
- E4-D/E4-F same-provenance diagnostics improved collapse but left `BYE`, `NO`, and `THANKYOU` weak.
- E4-G showed `BYE/NO/YES` target separability remained poor; `BYE -> YES` dominated.
- E4-L showed one-sign expansion with `MAKE` failed: held-out `MAKE` collapsed mostly into `GOOD`.
- E4-O showed `GET` failed when extracted and added: local `GET` collapsed mostly into `GOOD`; `WELCOME2` could not be promoted together with unstable `GET`.
- E4-P showed 20-sign expansion failed: mean latest test `0.6643`; `SORRY` collapsed mostly into `BECOME` and sometimes `HELP`.
- E4-Q reduced the problem to `GOOD/SORRY/HELP/BECOME`, but a landmark-only resolver still failed. Best mean latest test was `0.7137`, and best minimum latest `SORRY` was only `0.2333`.

### Architectural Inference

The correct inference is not “landmarks are useless.” The evidence says:

- Some signs are sufficiently separable with the current landmark representation and fixed/latest Conv1D policy.
- Some signs are not signer-independent or source-robust under `[96,258]`.
- Similar signs require group-specific treatment.
- Broad expansion should be gated by per-class reliability, not by aggregate accuracy.
- RGB/hand-shape evidence should be introduced selectively, because the previous broad RGB/fusion attempts were weak and expensive.

## Target Runtime Architecture

```text
CameraX frame + timestamp
  -> MediaPipe hand/pose landmarks using protected v3.0 path
  -> v3.0 feature builder [96,258]
  -> Primary landmark recognizer
  -> Calibration + stability policy
  -> Confusion router
      -> Stable class: commit if calibrated evidence is sufficient
      -> Registered confusion group: run specialist resolver
      -> Low confidence / unknown / no-sign: reject
  -> Optional specialist resolver output
  -> Final acceptance policy
  -> Existing sentence/UI layer
```

This design preserves the working recognizer shape while adding modular decision points.

## Component Design

| Component | Input | Output | Runs On | Purpose | Keep/Improve/Replace |
|---|---|---|---|---|---|
| CameraX frame acquisition | Camera frames | Timestamped analysis image | Android | Preserve current real-time input | Keep |
| MediaPipe hand/pose extraction | Image frame | Landmarks, handedness, pose | Android | Preserve known feature source | Keep, improve only after gated evidence |
| v3.0 feature builder | Landmarks | `[96,258]` sequence | Android/offline | Current stable landmark contract | Keep immutable |
| Primary recognizer | `[1,96,258]` | Class probabilities | Android | Main fast path for stable signs | Improve with better selected vocabulary/calibration |
| Calibration layer | logits/history | calibrated confidence | Android/offline-fitted | Prevent false commits | Add before production upgrade |
| Confusion registry | candidate class + probabilities | route decision | Android config | Knows which signs need specialists | Add |
| Specialist resolver | group-specific evidence | group probabilities/reject | Android only after gate | Resolve known hard signs | Add experimentally |
| Unknown/reject policy | calibrated scores, entropy, disagreement | accept/reject | Android | Avoid hallucinated translation | Add |
| Sentence/UI | accepted glosses | user-facing text | Android | Existing output path | Keep initially |

## Confusion Registry

The confusion registry is a versioned config, not hard-coded scattered logic.

Each entry should include:

- `group_id`
- member glosses
- trigger condition from primary recognizer, for example top-1 or top-k contains a member
- required primary confidence range
- resolver asset name and schema version if a resolver exists
- reject thresholds
- fallback behavior if resolver is unavailable
- telemetry fields to log offline during device tests

Initial known groups from completed experiments:

| Group | Status | Evidence | Default Action |
|---|---|---|---|
| `SORRY/BECOME/HELP` | Active research group | E4-P and E4-Q | Build hybrid or data-repair resolver before promotion |
| `GOOD/MAKE/GET` | Active exclusion group | E4-L and E4-O | Do not promote `MAKE` or `GET`; require new evidence |
| `BYE/NO/YES` | Deferred hard group | E4-G/E4-H | Keep out of stable vocabulary; needs visual/data intervention |
| `THANKYOU` variants | Deferred label group | E4-E/E4-F | Requires label/variant cleanup before modeling |

## Stable Vocabulary Track

Stable signs are signs that can use the primary landmark recognizer without a specialist.

Promotion requirements for a stable sign:

- signer-disjoint test performance passes per-class threshold;
- no severe confusion with an existing stable sign;
- source-aware metrics do not reveal source/provenance shortcuts;
- fixed/latest checkpoint policy remains stable across seeds;
- no-sign/unknown evaluation does not create false commits;
- Android latency and quantized parity pass before release.

Current provisional stable signs:

- `GOOD`
- `HELLO`
- `HAVE`
- `KNOW`

`SORRY` is not fully stable anymore after E4-P/E4-Q. It can remain in research, but production routing should treat it as a confusion-group member until the `SORRY/BECOME/HELP` group is resolved.

## Specialist Resolver Track

Specialist resolvers are allowed only for registered confusion groups. They must be small, isolated, and optional.

Recommended resolver order:

1. Landmark-only group resolver using the same `[96,258]` control.
2. Derived landmark/motion resolver only if it improves the group and has a realistic Kotlin parity path.
3. Hand/body crop visual resolver for groups where landmarks fail.
4. Hybrid group resolver only if visual evidence beats both branch-only controls.
5. Reject/unknown if no resolver passes.

E4-Q completed steps 1 and 2 for `SORRY/BECOME/HELP` and failed. Therefore that group should move to step 3: targeted visual evidence or data/variant repair.

## Data Strategy

The dataset should be managed by sign tier, not treated as one undifferentiated pool.

### Tier A: Stable Landmark Candidates

Use existing ASL Citizen and local features where source-aware gates pass. Expand in batches, not one word at a time, but every sign still needs per-class promotion evidence.

Required minimum for pilot promotion:

- at least 3 signer-disjoint splits;
- at least 5 held-out signers preferred for test if available;
- source-aware counts for ASL Citizen and local data;
- no signer/session leakage;
- raw videos preserved for future RGB/resolver work.

### Tier B: Confusion Groups

For confusing signs, store and evaluate:

- raw video;
- landmark tensors;
- crop tensors or crop metadata;
- variant notes;
- body-contact and handshape visibility notes when applicable;
- group-specific confusion matrices.

Do not force these signs into the global model until the group resolver or data repair passes.

### Tier C: Deferred/Rejected Signs

Signs remain deferred when:

- labels are inconsistent;
- variants are mixed under one gloss;
- held-out signer performance collapses;
- the required visual cue is not available from current capture conditions;
- the sign causes unacceptable false positives.

Deferred does not mean impossible. It means not product-ready under the current evidence.

## Model Strategy

### Primary Model

Use a simple landmark model as the first production candidate for stable signs:

- input: `[1,96,258]`
- architecture family: Conv1D or small temporal model selected by latest/fixed policy
- output: stable-vocabulary logits plus unknown/reject support where available
- reason: E4-K and E4-N support latest/fixed Conv1D policy more than validation-selected best checkpoints or unstable TCN variants

TCN remains a research alternative, not automatically the next production model. It can be tested again only if it beats the Conv1D latest/fixed control under the same stable vocabulary and source-aware gates.

### Specialist Models

Specialists should be smaller than the primary model and loaded conditionally only after the primary recognizer triggers their group.

Candidate specialist types:

- landmark-only Conv1D control;
- hand/body crop CNN embeddings plus small temporal head;
- late fusion between primary landmark embedding/logits and crop embedding;
- reject-only classifier for known ambiguous cases.

Avoid a large universal hybrid model until at least one specialist proves that visual evidence solves a registered confusion group.

## Android Feasibility

The dynamic strategy is Android-feasible because the default path stays cheap:

- MediaPipe + `[96,258]` feature builder remains the always-on path.
- Specialist resolvers run only when triggered by a known confusion group.
- RGB crops are not processed continuously for every sign unless a future device test proves they are cheap enough.
- Every resolver is behind a feature flag and separate model manifest.
- If a specialist is unavailable, the system rejects or falls back to the primary stable-vocabulary behavior rather than guessing.

Runtime constraints:

- no GPU delegate assumption;
- CPU/XNNPACK/INT8 remains baseline;
- no silent replacement of `streaming.tflite`;
- no schema mutation of v3.0;
- model loading remains async;
- device gates from `ANDROID_DEPLOYMENT_PLAN.md` still apply.

## Calibration And Rejection

The product goal is silent translation of another person signing, so the app cannot rely on the hearing user to confirm whether the sign is correct.

Therefore confirmation must be algorithmic:

- calibrated probability threshold;
- temporal stability over multiple frames/windows;
- entropy or margin threshold;
- confusion-group disagreement handling;
- unknown/no-sign rejection;
- optional resolver agreement before commit.

A difficult sign should be rejected or left uncommitted rather than confidently translated wrong.

## Roadmap

### Phase 0: Freeze Current Evidence

Status: mostly complete, but documentation must be cleaned up.

Tasks:

- Record E4-Q as completed no-go.
- Mark E4-O/E4-P next-action text as historical.
- Make this dynamic roadmap the current source of truth.

Gate: context docs clearly say no Android/export/large expansion is authorized yet.

### Phase 1: Build The Stable Landmark Candidate List

Goal: identify the largest realistic stable-vocabulary batch that can use the primary landmark path.

Experiment:

- Re-run or extend dual-source screening to classify all available signs into stable, confusion, data-repair, and deferred tiers.
- Use existing features first; avoid extraction unless a sign is high-value and otherwise ready.
- Include source-aware and per-class metrics.

Go:

- produce a ranked stable candidate list with per-sign evidence;
- at least a small batch beyond E4-N is ready for training without known hard groups.

No-go:

- if most signs are source-confounded or under-supported, stop expansion and plan data collection.

### Phase 2: Train Stable Landmark Primary Model

Goal: produce the first controlled primary recognizer candidate.

Experiment:

- train only stable Tier-A signs;
- compare Conv1D latest/fixed against TCN only as a controlled alternative;
- keep `[96,258]` contract;
- use three seeds, source-aware metrics, per-class gates, and no-sign/OOV diagnostics.

Go:

- aggregate top-1 and macro-F1 pass;
- every included class passes minimum threshold;
- no prediction concentration;
- calibration feasible;
- no-sign false commits controlled offline.

No-go:

- reduce vocabulary or repair data; do not add specialists to compensate for a weak global stable model.

### Phase 3: Confusion Registry And Router Design

Goal: define the routing policy offline before Android work.

Experiment:

- replay primary-model predictions;
- identify top-k confusion groups;
- simulate router thresholds and reject behavior;
- measure accepted precision/coverage tradeoff.

Go:

- router improves accepted precision without unacceptable coverage loss;
- registered groups are stable across seeds;
- false-positive behavior is measurable.

No-go:

- keep primary model restricted and reject uncertain cases.

### Phase 4: First Hybrid Specialist Resolver

Goal: test whether visual evidence fixes the highest-value failed group.

First group: `SORRY/BECOME/HELP`.

Recommended experiment:

- build synchronized hand/body crop dataset for the group from existing raw videos where possible;
- include landmark-only control, RGB-only crop resolver, and late-fusion resolver;
- use crop quality gates and source-aware splits;
- keep the resolver separate from the primary model.

Go:

- specialist beats landmark-only resolver by a meaningful margin;
- `SORRY` reaches the group threshold;
- false accepts are controlled;
- Android crop cost appears feasible.

No-go:

- perform data/variant repair or defer the group. Do not force it into production.

### Phase 5: Offline End-To-End Simulation

Goal: test the mixed recognizer as a product-like decision system.

Pipeline:

`primary recognizer -> calibration -> router -> specialist/reject -> final accepted gloss`

Metrics:

- accepted precision;
- coverage;
- per-class F1;
- confusion groups;
- false commits on N0/no-sign;
- latency simulation;
- low-FPS robustness.

Go:

- passes release-style offline gates on held-out signers and no-sign data.

No-go:

- adjust thresholds, reduce vocabulary, or defer specialists.

### Phase 6: Android Experimental Integration

Goal: integrate behind a default-off feature flag only after offline gates pass.

Rules:

- new model filenames;
- new manifests;
- no replacement of production `streaming.tflite`;
- v3.0 path preserved;
- resolver optional and fail-closed;
- telemetry/debug output for device smoke.

Go:

- device latency, thermal, memory, and quantized parity gates pass.

No-go:

- keep app on current production recognizer and return to offline work.

### Phase 7: Controlled Vocabulary Expansion

Goal: scale signs in batches using the same tiering process.

Process:

1. screen candidates;
2. train stable-primary batch;
3. identify new confusion groups;
4. add specialists only when justified;
5. reject/defer hard signs;
6. run offline and device gates.

Do not add words one at a time unless the word is high-priority and has strong evidence.

## Go/No-Go Summary

| Decision Point | Go | No-Go |
|---|---|---|
| Stable sign admission | per-class stable, source-aware, no major confusion | defer or assign to confusion group |
| Primary model | all classes pass minimums and calibration | reduce vocabulary or repair data |
| Router | improves accepted precision/coverage | use stricter primary rejection only |
| Specialist resolver | fixes registered group and is mobile-feasible | defer group or collect/clean data |
| Android integration | offline + quantized + device gates pass | no production change |
| Vocabulary expansion | batch meets gates | smaller product vocabulary |

## What Must Not Happen

- Do not train on all available signs and assume aggregate accuracy is enough.
- Do not use validation-perfect results as production proof when held-out test fails.
- Do not promote signs that collapse into stable signs.
- Do not add RGB everywhere because one group is hard.
- Do not replace the Android recognizer silently.
- Do not mutate schema 3.0.
- Do not rely on user confirmation for silent translation.

## Recommended Next Experiment

E4-R stable-candidate tiering is complete, E4-S passed as a closed-set stable-primary candidate, and E4-T showed simple confidence/margin routing cannot safely reject `SORRY`. The next action is a focused `SORRY` specialist/data-repair experiment.

Reason: before building specialists, the system needs a trustworthy primary recognizer and a clean list of signs it can safely handle without specialist complexity. E4-Q already shows that the `SORRY/BECOME/HELP` specialist needs richer evidence, but adding that now without a stable primary/router would create another isolated experiment that does not plug cleanly into the final product.

After the stable-primary package is defined, the first specialist experiment should target `SORRY/BECOME/HELP` using crop-based visual evidence.

## Source-Of-Truth Files

- Current runtime audit: `context/recognition_upgrade/CURRENT_PIPELINE_AUDIT.md`
- Architecture decisions: `context/recognition_upgrade/ARCHITECTURE_DECISIONS.md`
- Feature schema plan: `context/recognition_upgrade/FEATURE_SCHEMA_PLAN.md`
- Android deployment plan: `context/recognition_upgrade/ANDROID_DEPLOYMENT_PLAN.md`
- Evaluation gates: `context/recognition_upgrade/EVALUATION_AND_ACCEPTANCE_GATES.md`
- Risk register: `context/recognition_upgrade/RISK_REGISTER.md`
- Experiment matrix: `context/recognition_upgrade/EXPERIMENT_MATRIX.md`
- E4-Q result: `context/recognition_upgrade/E4_Q_RESULT.md`

## Open Questions

- E4-R identified the current guarded Tier-A set as `GOOD`, `HELLO`, `HAVE`, and `KNOW`; this must be confirmed by E4-S full training.
- E4-S withholds `SORRY` as an OOV/confusion holdout; the remaining question is how router thresholds should handle it.
- Can existing raw videos supply usable hand/body crops for `SORRY/BECOME/HELP`, or is new recording required?
- What no-sign/OOV dataset is sufficient for the first offline end-to-end simulation?
- What minimum product vocabulary is acceptable for the first real-user milestone?

## Risks

- The stable vocabulary may be smaller than product expectations.
- Specialist resolvers can increase complexity faster than the dataset can support.
- RGB crop quality may still be the bottleneck.
- Similar signs may require fluent signer annotation and variant separation, not just better models.
- Overusing the current test artifacts can lead to decisions that do not generalize.

## Next Required Action

Do not implement Android changes yet. E4-T failed as a threshold-only router. Prepare a focused `SORRY` specialist/data-repair experiment using richer evidence or targeted review before any Android export, broad expansion, or production replacement.



## 2026-08-02 E4-W Update

E4-R through E4-W have now established a narrow but positive routed-recognition proof:

- E4-S passed as a closed-set stable primary for `GOOD`, `HELLO`, `HAVE`, and `KNOW`.
- E4-T showed simple softmax confidence/margin routing cannot safely reject withheld `SORRY`.
- E4-V showed a lightweight `[96,258]` GOOD/SORRY landmark specialist is stronger than the current RGB upper-body specialist for that group.
- E4-W showed the E4-S primary plus E4-V landmark specialist recovers withheld `SORRY` while mostly preserving stable signs.

Current next required action: broader offline routed-system validation, not Android export. That validation must add no-sign/N0 windows, source-disjoint checks where available, and explicit accept/reject/calibration metrics before runtime integration.

New open questions:

- Can the E4-W routed approach survive source-disjoint GOOD/SORRY validation, or did same-source local evidence overstate performance?
- What no-sign/OOV dataset size is sufficient for the first routed-system false-commit gate?
- Should the GOOD/SORRY specialist be calibrated as a binary resolver or used only as agreement evidence before final accept/reject?

## 2026-08-02 E4-X Update

E4-X adds a first accept/reject system probe after E4-W. It passed on E4-S active signs, withheld SORRY, and zero-landmark N0 rows, with mean accepted precision `0.9798`, minimum accepted precision `0.9739`, minimum positive coverage `0.9661`, and zero false commits on the zero-landmark N0 probe.

This is not enough for Android. The next required action is a real N0/P1 feature-extraction validation package using MediaPipe-derived schema v3.0 windows, then rerunning the routed accept/reject gate.

## 2026-08-02 E4-Y Update

E4-Y is the first real MediaPipe no-sign feature validation. It failed the false-commit gate badly: real N0/P1 windows generated many confident false gloss commits even though zero-landmark E4-X passed. This updates the current route: before Android/export, the architecture needs an explicit signing/no-sign gate before the primary recognizer commits any gloss.

Current next required action: prepare E4-Z signing/no-sign gate experiment using real E4-Y N0/P1 features and positive E4-S/E4-V windows. Compare rule-based motion/presence gating against a lightweight learned binary gate, then rerun routed recognizer metrics.

## 2026-08-02 E4-Z Update

E4-Z tested rule-based and tiny learned signing/no-sign gates after E4-Y exposed real no-sign false commits. The result is a no-go: strict motion gates remove false commits but reject too many real signs, while the learned summary MLP still fails SORRY. The next required action is E4-AA no-sign dataset expansion plus a stronger temporal signing-gate design with true no-sign train/validation/test splits.

### E4-AA No-Sign Temporal Gate Package Prepared - 2026-08-02

- Package document: `E4_AA_NOSIGN_TEMPORAL_GATE_PACKAGE.md`.
- Runner: `pipeline/rgb/e4_aa_nosign_temporal_gate.py`.
- Smoke run: `artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_smoke_01`.
- E4-AA expands from E4-Z by building real MediaPipe/schema v3.0 no-sign windows from reviewed N0/P1 captures and training a small temporal Conv1D signing/no-sign gate before the E4-S/E4-V routed recognizer.
- Smoke status: prepared `[4,96,258]` no-sign features, trained one seed for one epoch, wrote metrics, and structural check passed. This smoke is wiring-only and is not an accuracy decision.
- Resume controls added: `--prepare-only` and `--train-only`; completed clip caches and completed dataset outputs are reused.
- Next action: user runs full E4-AA at `artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_01`, then checks with `--require-metrics`. No Android/export or production replacement is authorized before full metrics are evaluated.

### E4-AA Full No-Sign Temporal Gate Result - 2026-08-02

- Result document: `E4_AA_NOSIGN_TEMPORAL_GATE_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_01`.
- Structural check passed, but the experiment gate failed.
- E4-AA no-sign dataset: `288` rows shaped `[288,96,258]`, with N0 `180` and P1 `108`.
- E4-AA fixed most no-sign false commits: max test no-sign false commit rate `0.0147`.
- E4-AA failed low-motion sign preservation: mean/min SORRY recall `0.1222/0.0000`, and minimum positive coverage `0.6780`.
- Decision: no Android/export. Test conservative threshold/uncertainty policy before changing gate architecture.

### E4-AB Conservative Gate Policy Result - 2026-08-02

- Result document: `E4_AB_CONSERVATIVE_GATE_POLICY_RESULT.md`.
- Runner: `pipeline/rgb/e4_ab_conservative_gate_policy.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_ab_conservative_gate_policy_01`.
- E4-AB reuses E4-AA trained gate models and sweeps conservative thresholds selected to protect `SORRY`/positive coverage.
- Structural check passed, but the experiment gate failed.
- Compared with E4-AA, mean SORRY recall improved from `0.1222` to `0.6778`, mean positive coverage improved from `0.7345` to `0.8983`, and max no-sign false commit remained acceptable at `0.0441`.
- However, seed `202` still produced test SORRY recall `0.1000`; probability inspection showed true SORRY windows overlapped no-sign under that model.
- Decision: threshold tuning alone is insufficient. Next step is E4-AC low-motion-aware gate training/objective, not Android/export or broad vocabulary expansion.

### E4-AC Low-Motion-Aware Signing Gate Result - 2026-08-02

- Result document: `E4_AC_LOW_MOTION_AWARE_GATE_RESULT.md`.
- Runner: `pipeline/rgb/e4_ac_low_motion_aware_gate.py`.
- Best run directory: `artifacts/recognition_upgrade/e4_generalization/e4_ac_low_motion_aware_gate_01`.
- E4-AC retrained the E4-AA temporal signing/no-sign gate with explicit low-motion `SORRY` weighting.
- Structural check passed, but the strict experiment gate failed narrowly.
- Best run metrics: mean/min accepted precision `0.9548/0.9492`, mean/min positive coverage `0.9746/0.9661`, max no-sign false commit `0.0441`, mean/min GOOD recall `0.9667/0.9667`, mean/min SORRY recall `0.9667/0.9667`.
- E4-AC is the first gate result that preserves SORRY while controlling no-sign false commits, but it is not approved for Android/export because min accepted precision is below `0.95` and the no-sign dataset remains small.
- Decision: use E4-AC as the basis for the next gate iteration. Next step should focus on false-commit review/hard-negative expansion, especially P1/N0 windows predicted as `HELLO`, not vocabulary expansion or Android integration.

### E4-AD False-Commit Review Result - 2026-08-02

- Result document: `E4_AD_FALSE_COMMIT_REVIEW_RESULT.md`.
- Runner: `pipeline/rgb/e4_ad_false_commit_review.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_ad_false_commit_review_01`.
- Structural check passed with panels.
- Generated `51` panels: `28` false commits and `23` hard-negative candidates.
- Residual false commits are concentrated as no-sign -> `HELLO`: `test:N0->HELLO=2`, `test:P1->HELLO=7`, `train:P1->HELLO=3`, `val:P1->HELLO=15`; one train P1 row became `KNOW`.
- Decision: the remaining gate error is mostly HELLO-like ordinary-hand no-sign, especially P1. Test false commits are diagnostic only and must not be added to training.

### E4-AE Hard-Negative Weighted Gate Result - 2026-08-02

- Result document: `E4_AE_HARD_NEGATIVE_GATE_RESULT.md`.
- Runner: `pipeline/rgb/e4_ae_hard_negative_gate.py`.
- Corrected run directory: `artifacts/recognition_upgrade/e4_generalization/e4_ae_hard_negative_gate_02`.
- Structural check passed, but experiment gate failed.
- Upweighted `12` train-split hard negatives from E4-AD with hard-negative weight `6.0`.
- Metrics: mean/min accepted precision `0.9605/0.9417`, mean/min positive coverage `0.9746/0.9661`, max no-sign false commit `0.0882`, mean/min GOOD recall `0.9667/0.9667`, mean/min SORRY recall `0.9667/0.9667`.
- Decision: naive hard-negative weighting is not the solution; it worsened minimum precision compared with E4-AC. The best current gate remains E4-AC `01`, but it is still not Android/export approved.

## 2026-08-02 E4-AF To E5 Batch Strategy Update

The roadmap remains landmark-primary dynamic mixed recognition, but the execution strategy is now split into a short safety floor and a larger batch-scaling phase.

Current best immediate path:

1. Run E4-AF as a short offline acceptance-policy experiment around the best E4-AC gate and E4-S/E4-V routed recognizer.
2. If E4-AF passes, move to E5-A large dual-source candidate screening across ASL Citizen and the local supplementary dataset.
3. If E4-AF fails, collect a bounded HELLO-like no-sign expansion set before batch vocabulary scaling.

Reason: E4-AC nearly passes and preserves GOOD/SORRY, while E4-AD shows the remaining no-sign issue is concentrated as NO_SIGN -> HELLO. E4-AE showed naive hard-negative weighting does not improve the minimum precision. The project should not continue one-sign loops as the main path, but it also must not scale vocabulary before the real no-sign false-commit floor is controlled.

Source-of-truth detail: `E4_AF_TO_E5_BATCH_STRATEGY.md`.

## 2026-08-02 E4-AF Result Update

E4-AF completed as a short offline acceptance-policy sweep and failed the strict safety gate. The selected policy remained essentially the E4-AC baseline: min accepted precision `0.9492`, positive coverage `0.9661`, max no-sign false commit `0.0441`, and GOOD/HELLO/SORRY recall above `0.90`. HELLO-specific thresholds could improve precision only by hurting true HELLO recall and coverage.

Decision: policy-only tuning is not enough. The next safety step is E4-AG targeted HELLO-like no-sign expansion. E5-A batch screening remains the next vocabulary-scale mechanism after the safety floor is recovered.

## 2026-08-02 E4-AG Result Update

E4-AG completed and passed the offline safety floor. The targeted HELLO-like no-sign expansion added `116` reviewed P1_HELLO_LIKE rows, expanded the no-sign tensor to `[404,96,258]`, and the rerun low-motion-aware gate achieved min accepted precision `0.9739`, min positive coverage `0.9661`, max no-sign false commit rate `0.0000`, and GOOD/SORRY min recall `0.9667`.

Decision: proceed to E5-A large dual-source candidate screening. Do not continue one-sign loops, generic threshold sweeps, Android export, or production replacement.

## 2026-08-02 E5-A Result Update

E5-A completed the first vocabulary-scale screen after the no-sign safety floor passed. It inspected all `236` labels and found `67` local-supported labels, but only `WANT2` currently passes strict criteria for the next primary pilot. Most local-supported signs have only one local signer and should be treated as diagnostic/data-collection candidates, not production-ready.

Historical strict decision: proceed to E5-B strict 6-sign routed pilot: primary `GOOD`, `HELLO`, `HAVE`, `KNOW`, `WANT2`; routed `SORRY`; E4-AG no-sign gate. Do not train all labels or export Android.

Corrected scaling decision after user clarification: ASL Citizen should drive broad vocabulary learning, while local data supplements signs when available or fills missing app-priority signs. Therefore E5-B is now an ASL-led 50-class primary diagnostic, not a strict 6-sign pilot. Known blocked/confusion signs remain excluded from the primary model and Android/export remains blocked.

## 2026-08-02 E5-B ASL-Led Package Update

Prepared `pipeline/rgb/e5_b_asl_led_primary_batch.py` and run directory `artifacts/recognition_upgrade/e5_batch_screening/e5_b_asl_led_50_primary_01`.

E5-B selected 50 primary classes from the existing combined ASL Citizen + local schema v3.0 tensor. Dataset shape is `[2206,96,258]`, train/validation/test `1482/174/550`, with source counts `1413` ASL Citizen and `793` local. The selected classes start with stable controls `GOOD`, `HELLO`, `HAVE`, and `KNOW`; `SORRY` and known hard/confusion signs are excluded from the primary model. Smoke passed with output shape `[32,50]`, one training step, and smoke weight saving. Structural check passed with full dataset required.

Next required action: user runs E5-B full training, then metrics are reviewed for collapse, stable-control retention, per-class recall, and tiering. No Android integration, TFLite export, production replacement, or runtime pipeline changes are authorized.
## 2026-08-03 E5-C Tiering Update

E5-C completed as a metrics-only tiering pass over the completed E5-B 50-class ASL-led diagnostic.

Result: E5-B learned real signal but is not exportable. Mean latest test accuracy was `0.4897` versus random `0.0200`. E5-C produced tier counts: `A_primary_candidate_strong=9`, `B_primary_candidate_guarded=6`, `C_regressed_control_repair=2`, `C_confusion_group_candidate=8`, `D_overfit_or_provenance_risk=19`, `D_defer_from_primary=6`.

Recommended reduced-primary hypothesis: `WASH2`, `TAKE`, `MEET`, `HAVE`, `WANT2`, `WORK`, `GOOD`, `MORNING`, `STAND2`, `SELL`, `THINK`, `DRIVE`, `RUN2`, `USE`, `SLEEP`.

Important caution: `HELLO` and `KNOW` regressed in the 50-class model and were both mainly confused as `SEEM`. They must be repaired, routed, or separately validated before returning to the primary recognizer.

Next required action: prepare E5-D reduced-primary validation. No Android integration, TFLite export, production replacement, or runtime pipeline change is authorized.
## 2026-08-03 E5-D Package Update

Prepared `pipeline/rgb/e5_d_reduced_primary_validation.py` and run directory `artifacts/recognition_upgrade/e5_batch_screening/e5_d_reduced_primary_15sign_01`.

E5-D uses the E5-C reduced-primary hypothesis: `WASH2`, `TAKE`, `MEET`, `HAVE`, `WANT2`, `WORK`, `GOOD`, `MORNING`, `STAND2`, `SELL`, `THINK`, `DRIVE`, `RUN2`, `USE`, `SLEEP`. `HELLO` and `KNOW` remain excluded until repaired because E5-C showed they regressed as `SEEM` confusions. `SORRY` remains routed/specialist-only.

Prepared dataset shape is `[695,96,258]`, train/validation/test `483/49/163`, source counts `422` ASL Citizen and `273` local. Smoke passed with `[32,15]` output and one training step; structural check passed with full dataset required.

Next required action: user runs E5-D full training and check. No Android integration, TFLite export, production replacement, or runtime pipeline change is authorized.

## 2026-08-03 E5-D Result Update

E5-D completed the reduced-primary 15-sign validation. The reduced set improved mean latest test accuracy from E5-B's 50-class `0.4897` to `0.6933`, with mean best-checkpoint test `0.7382` and no prediction collapse. Strongest signs were `WASH2`, `THINK`, `TAKE`, `MEET`, `GOOD`, `STAND2`, `SELL`, `MORNING`, and `HAVE`.

The result is not production-ready. Weak or unstable signs remain: `USE`, `WORK`, `DRIVE`, `WANT2`, `RUN2`, and `SLEEP`. Dominant confusion groups include `WORK/USE`, `WANT2/DRIVE/HAVE`, and `SLEEP/USE/MORNING`.

Decision: E5-D supports the reduced-primary landmark strategy, but Android/export remains blocked. The next required action is E5-E reduced-primary tiering/decision to select a smaller safe primary subset and register confusion groups before routed-system simulation.

## 2026-08-03 E5-E Result Update

E5-E completed as a metrics-only decision pass over E5-D. It selected a smaller 7-sign primary candidate: `WASH2`, `THINK`, `TAKE`, `MEET`, `GOOD`, `SELL`, and `STAND2`. It registered remaining weak/confusing signs into groups, especially `USE/WORK`, `DRIVE/HAVE`, `DRIVE/WANT2`, `MORNING/USE`, `SLEEP/USE`, and `RUN2/WASH2`.

Decision: use the 7-sign subset for E5-F offline routed simulation. Do not export the full E5-D 15-sign model. Android/export remains blocked.

## 2026-08-03 E5-F Result Update

E5-F completed as an offline replay simulation. It used the E5-D 15-class model, allowed commits only for the E5-E 7-sign subset, placed the E4-AG no-sign gate in front, and treated non-selected E5-D signs as unsupported/OOV pressure.

Strict policy `0.99` was safe but unusable: mean/min accepted precision `0.9642/0.9310`, mean/min positive coverage `0.3611/0.3333`, max unsupported false commit `0.0110`, max no-sign false commit `0.0000`, and min class recall `0.0000`.

Relaxed diagnostic policy `0.80` improved coverage but still failed: mean/min accepted precision `0.9081/0.8689`, mean/min positive coverage `0.7870/0.7639`, max unsupported false commit `0.0659`, max no-sign false commit `0.0000`, and min class recall `0.4545`.

Decision: E5-F is no-go for Android/export. The next action is E5-G clean 7-class retrain using the E5-E subset, then rerun no-sign/OOV routed simulation. Do not rely on post-hoc rejection over the 15-class E5-D model.


## 2026-08-03 - E5-G/E5-H Reduced Primary Routed Evidence
- E5-G clean 7-class closed-set primary training passed structurally and improved mean latest test accuracy to `0.8472`, with strong `WASH2`, `THINK`, and `TAKE` but weaker `MEET` and `STAND2`. See `E5_G_CLEAN_7_PRIMARY_RESULT.md`.
- E5-H routed simulation was no-go for both full 7-sign and stable-3 commit subsets. Confidence thresholds could not preserve recall while rejecting unsupported signs. See `E5_H_CLEAN_7_ROUTED_SIM_RESULT.md`.
- Decision: do not export to Android. Next required action is E5-I explicit open-set/rejection training or auxiliary accept/reject modeling, not more vocabulary shrinking or softmax threshold tuning.


## 2026-08-03 - E5-I Open-Set Reject Head Result
- E5-I added a two-head landmark model: sign softmax plus supported-vs-unsupported/no-sign accept head. See `E5_I_OPEN_SET_REJECT_HEAD_RESULT.md`.
- Full 7-sign routed result remained no-go: mean/min accepted precision `0.8985/0.8333`, mean/min positive coverage `0.2778/0.2083`, max unsupported false commit `0.0220`, max no-sign false commit `0.0110`, min class recall `0.0000`.
- Stable-3 diagnostic remained no-go but improved coverage: mean/min accepted precision `0.7129/0.5532`, mean/min positive coverage `0.5833/0.4375`, max unsupported false commit `0.1170`, max no-sign false commit `0.0220`.
- Decision: shared accept/reject is useful but too blunt. Next required action is E5-J class-conditioned rejection/per-class accept policy before Android/export.

## 2026-08-03 - E6 Architecture Reset After E5-H/E5-I

E5-H and E5-I changed the next step. The previous E5-J class-conditioned rejection idea remains a hypothesis, but it is no longer the sole next action or an assumed fix.

Verified project evidence:

- E5-G showed a clean 7-class landmark model can learn selected signs in closed-set mode: mean latest test `0.8472`.
- E5-H showed softmax confidence thresholds cannot safely reject unsupported signs while preserving useful coverage.
- E5-I showed explicit negative pressure helps, but a shared accept/reject head still fails routed safety: full 7-sign accepted precision `0.8985/0.8333` mean/min and positive coverage `0.2778/0.2083`.

Engineering inference:

- The blocker is not only threshold selection. It is a combined dataset-scale, feature-representation, and open-set decision problem.
- More E5-style threshold sweeps risk repeating the same no-go loop.
- The dynamic mixed architecture remains valid, but the next work must be modular E6 validation: freeze baseline, audit dataset/splits/representation, test richer landmark features, test unknown/no-sign rejection families, mine confusion groups, and only then add specialists or RGB where evidence supports them.

Current source of truth: `E6_PRODUCTION_RECOGNITION_ARCHITECTURE_PLAN.md`.

Next required action: prepare E6-0/E6-1 baseline freeze and dataset/representation audit. Do not implement Android, export TFLite, mutate schema v3.0, or run another rejection-model experiment until the audit defines the feasible product-core vocabulary and data gaps.
