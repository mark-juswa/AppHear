# Hybrid Fusion Design

**Purpose:** Define how landmarks and RGB combine and degrade safely.
**Status:** ACTIVE PREPARATION; TRAINING BLOCKED BY ROI/DATA GATES. **Last updated:** 2026-08-12.

## Primary Design

At each timestamp:

1. Region graph encoder emits `z_landmark[128]`.
2. One shared hand CNN emits `z_left[96]`, `z_right[96]`.
3. Quality vector contains modality presence, crop coverage/blur, hand scores, pose freshness, and
   `dt`.
4. Each embedding is projected and multiplied by a learned gate constrained by its validity mask.
5. Concatenate gated embeddings, relations, and time encoding; project to `z_fused[128]`.
6. Feed a causal temporal encoder and multitask heads.

The model must train with modality dropout so landmark-only operation is a measured degraded mode,
not accidental behavior. RGB-only and landmark-only logits remain available in evaluation builds
for attribution.

## Alternatives

- **Late fusion:** weighted calibrated logits. Cheapest and easiest diagnostic; weaker interaction.
- **Cross-attention:** potentially stronger, but higher export/data risk; test only if concatenation
  plateaus.
- **Early raw fusion:** rejected because pixel and graph tensors have incompatible structure and
  missingness.

## Crop Policy

ROI comes from current tracked hand landmarks, expanded 1.5-2.0x, stabilized in image coordinates,
clipped, and resized with an explicitly versioned method/color order. If a hand vanishes briefly,
predict ROI from wrist motion for a short timestamp-bounded gap; mark it predicted. Never reuse an
old crop without a freshness feature. Shared weights reduce size; side/chirality embedding handles
asymmetry.

Phase 2 evidence amendment: the policy above is a hypothesis, not a verified route. Prior direct,
pose-recovery, VIDEO-mode, and I320 evidence all failed at least one availability, two-hand,
usability, false-ROI, or balance gate. `PHASE2_PREPARATION_RESULT.md` therefore registers four
competing routes and requires a pilot-specific crop audit before training. Pose fallback metadata
must never be equated with a usable hand crop.

## Benefit, Cost, Dataset, Risk

- **Benefit hypothesis:** RGB resolves finger occlusion, contact, and similar geometry; landmarks
  stabilize motion/body relations and reduce background dependence.
- **Cost target:** RGB branch under 15 ms at its chosen cadence; complete fusion under 30 ms beyond
  perception.
- **Dataset:** requires raw videos, synchronized crops, signer diversity, and crop-failure negatives.
- **Risks:** ROI misses, RGB background leakage, one modality dominating, quantization drift.

## Gate

On identical signer splits, hybrid must beat the best single stream by at least 5 absolute top-1
points **or** materially fix pre-registered confusion groups while meeting macro/worst-decile,
calibration, and cost gates. Otherwise keep the winning single stream.

## References, Decisions, Assumptions, Open Questions, Next Action

- **Research:** hand-pose-guided RGB and multi-stream sources in `MODEL_RESEARCH_PLAN.md`.
- **Decision:** intermediate mask-aware fusion; late fusion is fallback.
- **Assumption:** hand crops carry most useful RGB signal for the 50-sign pilot.
- **Open questions:** crop size, RGB cadence, shared versus separate encoders.
- **Next action:** run P2-P2, the bounded 40-sign ROI crop-quality smoke. Do not start P2-P3 until
  one route passes and synchronized training/evaluation sufficiency is explicitly approved.


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-016 apply; component-specific decisions in this document apply only after their experiment gate passes.
- **Assumptions:** Any forecast or unmeasured dimension remains a hypothesis, not a project fact.
- **Open questions:** Unresolved items are tracked in this document and `OPEN_QUESTIONS.md`.
- **Risks:** Applicable failure modes and fallbacks are tracked in this document and `RISK_REGISTER.md`.
- **Next required action:** Follow the explicit next action above and the ordering in `EXPERIMENT_MATRIX.md`; do not skip gates.
