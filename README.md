# AppHear 3

A ground-up re-architecture of a real-time, on-device ASL recognition system, built on
the measured lessons of AppHear v2 and ASLRecorder2. **This is not a retrain — it is a
re-architecture.** Recognition is one stage of nine.

> The system metric is **end-to-end signed-phrase accuracy, cross-signer, under streaming
> conditions.** Per-window accuracy on a training signer is explicitly *not* the metric
> (see [v2 lesson f](docs/05-v2-lessons-map.md)).

## Target runtime

Same class of target as v2: **budget Android SoC, on-device, real-time.** MediaPipe Tasks
hand + pose landmarkers → feature contract → temporal model → TFLite inference. No cloud in
the critical path. The landmarker backend is treated as the fixed compute floor
([lesson a](docs/05-v2-lessons-map.md)).

## The four anchor numbers (everything is downstream of these)

| # | Fact | Source | Design consequence |
|---|------|--------|--------------------|
| 1 | Citation-form sign ≈ **851 ms** mean (SD 301); shortest ~170–200 ms | ASL-LEX 2.0 | Decision window must ≈ one sign, not 4× |
| 2 | Fluent signing = **1.5–2.5 signs/sec** (new sign every ~400–650 ms) | — | Must emit incrementally; can't wait 3.7 s |
| 3 | v2 window = 30 frames @ ~8 fps = **~3.7 s ≈ 4× a sign** | v2 measured | ~75% of window is non-sign → trim + normalize |
| 4 | fps is a **temporal-resolution floor** | derived | Below ~15 fps short signs are unresolvable |

## Document set (the §8 deliverables)

| Doc | Deliverable | §8 item |
|-----|-------------|---------|
| [01 — System Architecture](docs/01-system-architecture.md) | The 9-stage pipeline: responsibility, I/O, and metric per stage | 1 |
| [02 — Data Pipeline](docs/02-data-pipeline.md) | Concrete mechanism for every normalization/gating stage | 2 |
| [03 — Model Architecture](docs/03-model-architecture.md) | Temporal model choice + migration path to streaming/CTC | 3 |
| [04 — Confirmation & Sentence Builder](docs/04-confirmation-and-sentence-builder.md) | FP-guarded commit + gloss→text, so the v2 leak can't recur | 4 |
| [05 — v2 Lessons Map](docs/05-v2-lessons-map.md) | Every place a v2 lesson forces a specific design decision | 5 |
| [06 — Feature / Schema Contract](docs/06-feature-schema-contract.md) | Explicit, versioned feature contract (v2 was 258-float / 10-field) | 1, constraints |

## Working method — the Context System

Day-to-day development runs on an adapted version of the JS-Mastery Context System. Start
every session by reading [AGENTS.md](AGENTS.md), which fixes the reading order of the nine
[`context/`](context/) files (the operational contracts) and lists the workflow skills.

- **`context/`** — what the agent must know before building, so it never guesses. The three
  web-UI files from the original convention are replaced by ML-relevant ones:
  `runtime-constraints.md`, `eval-protocol.md`, `feature-schema.md`.
- **`docs/`** — the deep design rationale below. If `context/` and `docs/` ever disagree,
  `context/` wins and the drift is flagged.

## Non-negotiables (from §7)

- On-device, real-time, budget-Android. No cloud inference in the critical path.
- Every stage is measurable and independently ablatable. No monolith.
- **All accuracy claims are cross-signer, end-to-end, on held-out signers.**
- Changes ship behind feature flags with rollback; validated offline before device rollout.
- The feature/schema contract is explicit and versioned.

## Status — built & running on-device (2026-07)

The design is fully realized: every phase through the Android runtime is built, and the app
recognizes everyday ASL on a budget phone. Per-feature detail lives in
[`context/progress-tracker.md`](context/progress-tracker.md).

| Phase | Scope | State |
|-------|-------|-------|
| 0 — Offline foundation | Extraction → detection → normalization → feature contract v3.0 → isolated TCN + cross-signer eval | ✅ Complete |
| 1 — Streaming isolated | Per-frame emission head + S7 confirmation policy + emission-dynamics eval | ✅ Complete |
| 2 — CTC continuous | Connected-sequence CTC decode | ⏸ Deferred — ASL Citizen is isolated-sign only (no continuous data) |
| 3 — Android runtime | CameraX + MediaPipe → causal S4 features (skew-tested) → INT8 TFLite → confirmation → UI | ✅ Code-complete, device-verified |

**What runs on the phone today:** front-camera capture → MediaPipe hand+pose (GPU delegate, CPU
fallback) → byte-exact on-device S4 features → INT8 streaming causal-TCN → S7 confirmation → a UI
showing the **top-3 candidate glosses**, a **left/right handedness toggle**, and a **running
sentence** of committed signs. Recognition runs behind a feature flag with an automatic
camera-only fallback.

**The deployed model recognizes a 236-word everyday vocabulary** (greetings, common verbs,
question words, people, places, time) — deliberately curated for *conversation* rather than the
data-richest signs. Cross-signer (held-out signers) test: **top-1 0.61 / top-5 0.89** at native
frame rate; **top-1 ~0.53 / top-5 0.83** at the phone's low-fps regime, precision-when-committed
**~0.73**, with the top-3 UI surfacing the right word most of the time.

**The honest limit is hardware, not the model.** The two MediaPipe landmarkers are ~95% of every
frame and cap a budget phone at ~7–8 fps — below the ≥15 fps floor short signs need (anchor #4).
Frame-rate-augmented training recovers much of the gap; the remaining lever is faster hardware / a
lighter landmarker. The full measured story is in
[`context/recognition-accuracy.md`](context/recognition-accuracy.md).

**Deferred (future work):** Phase-2 CTC for connected signing, LM-assisted gloss→text, further
detection/recognition accuracy, and on-device frame-rate gains. AppHear v2 (sibling `../AppHear`)
remains **untouched** throughout.
