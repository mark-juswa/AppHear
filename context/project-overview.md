> **2026-10-09 current-state notice:** Read [team-current-state-2026-10-09.md](team-current-state-2026-10-09.md) and [TEAM_HANDOFF.md](../TEAM_HANDOFF.md) first. Older design/status/absolute-checkout references below are historical where they conflict with the verified October9 code and current-state inventory. Protection, parity and evaluation rules still apply. Do not treat the old 15-FPS target as a measured achieved cadence, or uninstall/clear app data by default during smoke checks; current updates use `adb install -r`.

# Project Overview

## Current governed product state — 2026-09-15

The current product target is **full 236+ vocabulary isolated-sign recognition**, not fluent
continuous ASL: real phone camera → frozen Candidate 01 perception → automatic isolation of one
sign event → frozen recognition-v2 → improved 236-class recognizer → gloss → the existing AppHear
conversational UI. The future runtime must use a rolling raw-v1 buffer, automatic sign-start/end,
a small controlled pre/post margin, and automatic re-arm for the next isolated sign. Continuous
fluent ASL with coarticulation remains later research and is not solved by this architecture.

Gate 4A-1C is an independently validated causal result. With Candidate01, recognition-v2, the
ordinary V2 TCN and all weights frozen, oracle active-sign isolation improved the same retained
live attempts from Top-1 `2/10` to `7/10` and expected-in-Top-5 `5/10` to `8/10`; five wrong
attempts became correct and none became wrong. Automatic active-sign temporal segmentation is
therefore a required product component, but AT ×2 and one STREET attempt remained wrong. Gate 5
formally classified Phase 4A as **`PHASE_4A_COMPLETE_RETURN_TO_PHASE_3`** and assigned the
separate unresolved unseen-signer/generalization blocker back to Phase 3. Gate 4A-2 is superseded
by a later governed phone
validation after Phase-3 improvement. The next primary boundary is
`PHASE_3_RECOGNIZER_GENERALIZATION_REOPEN` for a new-information/diversity strategy—not same-data
microtuning; this state does not authorize implementation or training.

## About the Project

AppHear 3 is a **real-time, on-device American Sign Language recognition system** for budget
Android hardware. A user signs in front of the phone camera; the app recognizes the signs as
they happen and builds fluent text output — with no cloud in the critical path.

It has two artifacts:

1. **The Android runtime** — Kotlin app: CameraX → MediaPipe Tasks (hand + pose landmarkers)
   → normalized feature vector → TFLite temporal model → confirmation → sentence builder.
2. **The offline pipeline** — Python + TensorFlow/Keras: dataset processing, normalization,
   feature extraction, model training, and **cross-signer** evaluation. It produces the
   TFLite model and the versioned feature contract the runtime consumes.

**This is a re-architecture, not a retrain.** The predecessor, AppHear v2, worked but hit
measured ceilings. AppHear 3 designs those lessons in from frame zero. The model is **one
stage of nine** — recognition is the middle of a pipeline of decisions, not the whole system.

Full design rationale: [`../README.md`](../README.md) and [`../docs/`](../docs/).

---

## The Problem It Solves

ASL recognition demos work "for me" and collapse on new signers and continuous signing.
AppHear v2 proved exactly where and why:

- **Cross-signer generalization** is the real test, and it's where v2 broke.
- **The decision window** (30 frames @ ~8 fps ≈ 3.7 s) was ~4× the length of an actual sign,
  so it could never keep pace with fluent signing and mostly saw non-sign frames.
- **The confirmation policy leaked** — dropping ~50% of *correct* signs as "none".

AppHear 3 solves these structurally: a normalized data pipeline that removes cross-signer
variance, a streaming model that emits within a sign's ~1 s lifetime, and a confirmation
policy tuned on held-out signers.

---

## The Four Anchor Numbers (everything is downstream of these)

| # | Fact | Design consequence |
|---|------|--------------------|
| 1 | Citation-form sign ≈ **851 ms** mean (SD 301); shortest ~170–200 ms | Decision window ≈ one sign, not 4× |
| 2 | Fluent signing = **1.5–2.5 signs/sec** (new sign every ~400–650 ms) | Must emit incrementally |
| 3 | v2 window = 30 frames @ ~8 fps ≈ **3.7 s ≈ 4× a sign** | Trim dead time + normalize duration |
| 4 | fps is a **temporal-resolution floor** | Sustain **≥15 fps** or short signs are unresolvable |

---

## The Pipeline (nine stages)

```
S0 Capture → S1 Hand → S2 Pose → S3 Tracking → S4 Features
   → S5 Temporal Understanding (gating) → S6 Recognition
   → S7 Confirmation → S8 Sentence Builder
```

Each stage is a first-class, independently-swappable component with its own metric and
feature flag. Detailed in [`architecture.md`](architecture.md) and
[`../docs/01-system-architecture.md`](../docs/01-system-architecture.md).

---

## Data Architecture

- **ASL Citizen** — primary corpus. Largest, most signer-diverse resource; signer diversity
  is exactly where v2 broke. Isolated citation-form (matches the ~851 ms target distribution).
- **ASLRecorder2** — custom/targeted, schema-controlled captures (258-float / 10-field JSON
  lineage). Gap-fills vocabulary and provides on-device-matched samples.
- **Splits are by signer, never by clip.** All evaluation is on held-out signers.

---

## Features In Scope

- Offline data pipeline: signing detection, dead-time trim, scale/orientation/handedness/
  duration normalization, quality gate, feature extraction.
- Versioned feature contract (v3.0 normalized-258 → v3.1 kinematic-484).
- Streaming temporal model (causal TCN encoder) with a migration path to CTC continuous
  recognition.
- Cross-signer, end-to-end evaluation harness.
- On-device Android runtime: MediaPipe landmarkers, feature parity, TFLite inference, gating,
  confirmation, sentence builder, minimal recognition UI.
- Feature-flag + offline-eval-gate discipline throughout.

## Features Out of Scope (for now)

- Cloud inference in the critical path.
- Face landmarker (disabled — v2 lesson a).
- A large-vocabulary production sentence LM (start with n-gram / lightweight on-device).
- Multi-user / accounts / analytics dashboards.
- Rebuilding v2's sliding-window state machine.
- Any modification to the AppHear v2 project.

---

## Target User

Deaf/HoH signers and people communicating with them, on affordable Android phones, needing
real-time on-device recognition that works across different signers — not just the developer.

## Success Criteria

- **End-to-end signed-phrase accuracy on held-out signers** clears its target (the top-line
  metric — see [`eval-protocol.md`](eval-protocol.md)).
- The runtime sustains **≥15 fps** on the budget target SoC.
- The model emits incrementally within a sign's ~1 s lifetime (no 3.7 s wait).
- Confirmation's **correct-but-dropped** rate is low and *measured*, not hidden.
- Offline and on-device feature extraction produce identical vectors (no train/serve skew).
- Every stage is independently ablatable and its metric reportable.
