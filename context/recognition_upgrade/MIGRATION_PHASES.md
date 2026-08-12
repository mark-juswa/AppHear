# Migration Phases

**Purpose:** Move from research to production without replacing the working recognizer prematurely.
**Status:** PLANNED. **Last updated:** 2026-07-25.

| Phase | Work | Exit gate |
|---|---|---|
| RU0 Baseline lock | E0 manifests, hashes, splits, metrics, Git tag, untouched asset backup | reproducible within 1 point |
| RU1 Structured baseline | E1 graph sanity/fairness; select graph or TCN landmark branch | pre-registered gain or documented fallback |
| RU2 Offline RGB data | versioned crop extractor, parity fixtures, crop-quality audit | E2 >=98% usable visible-hand crops |
| RU3 Hybrid offline | E3 single-stream/fusion ablation on a screened vocabulary | hybrid or winning stream meets gain/data gates after source-aware data screening |
| RU4 Temporal/reject | boundary, prefix, no-sign/OOV, calibration | E5 false-commit/boundary/latency gates |
| RU5 Android shadow | separate assets/schema/runtime flag; no UI commits | E4/E7 performance, parity, thermal |
| RU6 Pilot | 30-signer/50-sign collection and learning curve from screened candidate signs | >=0.85 held-out top-1, per-class floors, and release gates |
| RU7 Controlled rollout | opt-in hybrid, telemetry/log export, instant fallback | multi-device smoke and user evaluation |
| RU8 Vocabulary | 100 then 236 signs | every tier independently passes |
| RU9 Continuous research | natural sentence data, CTC, gloss WER | separately approved product/research gate |

No phase may silently modify the production model, schema, confirmation, lifecycle, or UI. Each
phase gets a branch, new artifact names, default-off feature flag, report directory, and rollback.

## Approved Long-Term Research Roadmap - 2026-08-11

This roadmap supersedes the earlier execution order above while preserving its evidence and safety
rules. It is not an Android production-migration authorization.

| Phase | Current scope | Exit gate |
|---|---|---|
| Phase 1 | Rebuild a lineage-complete 236-sign v3.0 landmark dataset; compare production TCN with mask-aware TCN | signer-disjoint manifest passes; both branches use identical data/budget; protected test is accessed once; full per-class, low-FPS, missing-landmark, and streaming reports exist |
| Phase 2 | Isolated hybrid landmark + synchronized left/right RGB hand crops, guided only by Phase 1 failures | hybrid materially beats Phase 1 on preregistered held-out confusion groups and aggregate metrics within Android cost limits |
| Phase 3 | Continuous gloss/boundary recognition | natural phrase data, gloss sequences, transitions, and boundary annotations exist before modeling |
| Phase 4 | Sentence/language intelligence | visual gloss/boundary performance is reliable and language processing cannot silently overwrite uncertain visual evidence |

Only Phase 1 preparation is active. Full hash verification of the canonical manifest is the next
gate; feature assembly and training remain downstream of that gate.

## Related Sources, Decisions, Assumptions, Risks, Open Questions, Next Action

- **Sources:** parent `build-plan.md`, `progress-tracker.md`, `device-smoke.md`.
- **Decision:** offline evidence before device, 50 signs before 236, isolated before CTC.
- **Assumption:** production and experiment can coexist within app/package limits.
- **Risk:** prototype branches drift from production CameraX behavior.
- **Open question:** release channel/telemetry consent design.
- **Next action:** complete dual-source candidate screening before expanding the reliable vocabulary, retrying hybrid fusion at scale, or entering Android shadow deployment.


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-016 apply; component-specific decisions in this document apply only after their experiment gate passes.
- **Assumptions:** Any forecast or unmeasured dimension remains a hypothesis, not a project fact.
- **Open questions:** Unresolved items are tracked in this document and `OPEN_QUESTIONS.md`.
- **Risks:** Applicable failure modes and fallbacks are tracked in this document and `RISK_REGISTER.md`.
- **Next required action:** Follow the explicit next action above and the ordering in `EXPERIMENT_MATRIX.md`; do not skip gates.

## E4-L Migration Constraint - 2026-07-30

E4-L showed that a candidate can pass extraction and validation while failing held-out signer testing. Therefore, vocabulary expansion is now a required data-screening step before RU3/RU6 scale-up. The current production recognizer remains protected, and the reliable experimental core remains `GOOD`/`HELLO`/`SORRY` until a source-aware batch screen identifies safer expansion signs.

## Dynamic Mixed Migration Constraint - 2026-07-31

E4-N proved a small stable landmark path can work, while E4-O/E4-P/E4-Q proved broad expansion and landmark-only specialist resolution can fail badly. Migration therefore changes as follows:

- RU3 is no longer "global hybrid offline" as the immediate target. It becomes "mixed recognizer offline": stable landmark primary model, confusion registry, optional specialists, and reject behavior.
- RU5 Android shadow cannot start until the mixed recognizer passes offline end-to-end simulation and no-sign/OOV false-commit gates.
- Specialist models must be optional assets and must fail closed.
- The current production recognizer remains protected until the full mixed system passes device gates.

## Post-E6 Migration Constraint - 2026-08-09

E6-2/E6-3/E6-5 failed and E6-6/E6-7 are blocked. RU3 cannot proceed through the dynamic mixed
route with the current components. E3 also exhausted the crop-free upper-body RGB fallback.

Migration returns to the unresolved RU2 prerequisite through one bounded experiment:
`C0B_APPHEAR_HAND_ROI_FEASIBILITY_PLAN.md`. Stage 1 is inventory and detector toolchain readiness;
Stage 2 training requires separate approval after Stage 1. A detector pass authorizes only a new
crop-quality gate, not hybrid recognition or Android integration. A detector no-go retires the
hand-crop hybrid as the immediate path and triggers a product-scope decision while v3.0 remains
frozen.

C0-B0 Stage 1 software readiness passed on 2026-08-09: inventory, annotation mechanics, one-epoch
training, TFLite export, MediaPipe reload, and CPU inference are verified. Stage 1 is not complete
because condition-balanced annotations and license review remain open. The next migration action is
the 300-frame annotation pilot, not RU2 detector training or RU3 hybrid recognition.

## Post-C0 Migration Resolution - 2026-08-11

The Stage 1 work above and the controlled Stage 2 detector comparison are now complete. C0-B0
failed its development progression gate, and the existing inventory contains no independent,
signer-diverse hard-negative set for another controlled round. This section supersedes the stale
next-action sentence above.

RU2/RU3 hand-crop hybrid work is retired as the immediate route. RU4-RU9 remain blocked; they are
not renamed or weakened. The current deliverable is the protected 236-sign isolated-sign research
prototype described in `POST_C0_PRODUCT_SCOPE_DECISION.md`. No migration occurs.

The next executable action is the existing F22 device smoke on the current behavior-preserving
baseline. The model and landmarker hashes match E6-0; the pre-existing `post_commit_rearm` config
block must remain disabled and is explicitly checked because it changes the config hash. Any
future migration proposal requires materially new evidence and must restart at the applicable
offline gate.

## Phase 2 Preparation Reopening - 2026-08-12

Phase 1 is complete as a frozen research control and error registry. Its top-5/top-1 gap is
materially new downstream evidence, so Phase 2 is reopened only as a bounded 40-sign preparation
and crop-quality gate. This does not reverse the C0-B0 no-go or authorize detector retraining.
P2-P3 training remains blocked by pixel-crop reliability, 10-16 synchronized train clips per sign,
and lack of fresh Phase 2 signer/domain evaluation. No Android migration is authorized.

P2-P2 is now implemented and its final 120-frame evidence package is prepared at
`artifacts/recognition_upgrade/phase2_roi_audit/p2_p2_roi_audit_02`. It covers all 40 pilot signs,
29 signers, 99 train clips, and 21 validation clips. Migration remains blocked while the hand-gold
and blinded route reviews are incomplete. Preparing this package does not authorize RGB dataset
creation, recognition training, TFLite export, or Android changes.

P2-P2 subsequently completed with a robust **NO-GO for 40-sign RGB dataset creation**. R1 pose
recovery is the best current route but fails objective hand coverage, two-hand completeness, and
temporal consistency. The uncertain single-reviewer usability labels do not control this decision.
P2-P3 remains blocked. A corrected strict R1/R2 whole-route gold oracle was completed after
anatomical-side adjudication. Even this non-deployable upper bound fails the geometry gates, so the
previous deterministic R1/R2 selector proposal is retired. Do not create the 40-sign RGB dataset
from these routes and do not train a selector against oracle labels. Phase 2 must return to ROI
method selection/data support rather than proceeding to recognition training.

P2-P2F is the single bounded method-selection continuation: causal optical-flow propagation of
direct/pose-initialized hand ROIs on the unchanged 120-frame P2-P2 evidence. It is not another
detector, MediaPipe mode, threshold, or selector experiment. A full objective-gate failure retires
the current hand-crop ROI stack; only an objective pass permits blinded crop review. P2-P3 remains
blocked in either case until crop usability is independently established.

P2-P2F completed with `NO_GO_RETIRE_CURRENT_ROI_STACK`. It improved triplet persistence to
`0.8917` but reduced coverage to `0.8053`, two-hand completeness to `0.6486`, and side accuracy to
`0.7375`; it also emitted stale ROIs on `3/4` no-hand frames. The registered stop rule is active.
No P2-P3 RGB training or further tuning of the current ROI routes is allowed. Phase 2 can reopen
only with materially new, independently gated localization data/methodology. Until then, Phase 1
remains the strongest trustworthy isolated-sign research baseline and protected fallback.

## Protected Phase 1 Shadow Step - 2026-08-12

After retiring the current ROI stack, the selected near-term action is not another ROI variant. A
default-off Android shadow evaluator packages the frozen Phase 1 three-seed landmark ensemble
without replacing `streaming.tflite` or changing confirmation/UI behavior. Float32 passed offline
parity; INT8 did not pass argmax parity and is not the device candidate. The evaluator may advance
only through device performance/behavior measurement. Improved hand ROI detection remains later
research requiring materially new localization data or methodology and an independent gate.
