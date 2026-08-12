# Temporal And Boundary Plan

**Purpose:** Replace frame-count timing with real-time streaming semantics.
**Status:** PROPOSED. **Last updated:** 2026-07-25.

## Time Contract

Every frame/landmark/crop carries a monotonic capture timestamp. The cache is bounded by duration
(default candidate 2.0 seconds), not semantic frame count. Models receive valid masks, `dt`, and
freshness. Training randomly evaluates 4, 6, 8, 12, 15, and native FPS views with jitter/dropouts.
Interpolation is an explicit experimental view; it cannot invent handshape detail.

## Isolated Boundary Head

Predict `idle/onset/active/release` per time step. Train from annotated spans plus idle, partial,
aborted, and transition negatives. S5 remains an independent fallback/guard until the learned head
passes boundary and false-commit gates. Commit requires calibrated gloss evidence, boundary state,
unknown rejection, stability in milliseconds, and one-commit-per-bout.

## Partial Signs

Train prefixes sampled from 30-100% of the annotated span, label their observed fraction, and do not
force early prefixes to have full confidence. Evaluate accuracy/coverage curves at 25/50/75/100%
duration. Partial clips from wrong/unknown signs are rejection examples.

## Continuous Path

After natural sentence-level data exists, retain encoders/fusion and add a CTC gloss+blank head.
Use the boundary head as auxiliary supervision, not hard segmentation. Evaluate gloss WER and
insertion/deletion/substitution. Add a separate gloss-to-English decoder only after gloss quality
is sufficient; ASL grammar is not English word order.

Research basis: CTC-based joint recognition/translation:
https://openaccess.thecvf.com/content_CVPR_2020/html/Camgoz_Sign_Language_Transformers_Joint_End-to-End_Sign_Language_Recognition_and_Translation_CVPR_2020_paper.html
and How2Sign continuous data:
https://openaccess.thecvf.com/content/CVPR2021/html/Duarte_How2Sign_A_Large-Scale_Multimodal_Dataset_for_Continuous_American_Sign_Language_CVPR_2021_paper.html

## Decisions, Assumptions, Risks, Unknowns, Next Action

- **Decision:** causal online outputs; variable duration; CTC later.
- **Assumption:** isolated boundary labels can be collected consistently.
- **Risks:** ambiguous boundaries, low-FPS onset loss, coarticulation scope creep.
- **Open question:** right-context allowance; E5 compares 0 versus 100-200 ms lookahead.
- **Next action:** annotation study on 200 pilot clips before training the boundary head.


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-016 apply; component-specific decisions in this document apply only after their experiment gate passes.
- **Assumptions:** Any forecast or unmeasured dimension remains a hypothesis, not a project fact.
- **Open questions:** Unresolved items are tracked in this document and `OPEN_QUESTIONS.md`.
- **Risks:** Applicable failure modes and fallbacks are tracked in this document and `RISK_REGISTER.md`.
- **Next required action:** Follow the explicit next action above and the ordering in `EXPERIMENT_MATRIX.md`; do not skip gates.
