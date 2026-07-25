# 01 — System Architecture

*Deliverable §8.1: the full AppHear 3 architecture, stage by stage, with the
responsibility, input/output, and success metric of each component.*

---

## Design principle

Every stage is a **first-class, independently-swappable component with its own metric and
its own feature flag.** Recognition accuracy is not the system metric; end-to-end
signed-phrase accuracy under cross-signer, streaming conditions is. Each stage can be
measured, tuned, and ablated in isolation, and each has a defined fallback when disabled.

```
Camera
  ↓ [S0] Capture
  ↓ [S1] Hand Detection
  ↓ [S2] Pose Detection
  ↓ [S3] Tracking            (identity + smoothing across frames)
  ↓ [S4] Feature Processing  (normalized feature vector — the versioned contract)
  ↓ [S5] Temporal Understanding (gating: signing? phase? motion? informativeness?)
  ↓ [S6] Recognition
  ↓ [S7] Confirmation        (confidence + FP-guarded commit policy)
  ↓ [S8] Sentence Builder    (gloss → fluent output)
```

The nine stages below are numbered S0–S8. S0 (Capture) is added explicitly because
**frame rate is a temporal-resolution floor, not a background detail** (anchor #4) — it
must be a measured, budgeted stage, not an assumption.

---

## S0 — Capture

| | |
|---|---|
| **Responsibility** | Deliver frames at a known, stable rate; decouple *capture* cadence from *inference* cadence so the two can be tuned independently. |
| **Input** | CameraX image stream. |
| **Output** | Timestamped frames (monotonic clock) at the highest sustainable rate, plus a `capture_fps` telemetry signal. |
| **Metric** | Sustained end-to-end pipeline fps, and its **variance** (jitter). Hard requirement: pipeline must sustain **≥ 15 fps** (derived from the ~170–200 ms shortest signs — see anchor #4). Below that, short signs are physically unresolvable and no model can recover them. |
| **Flag / fallback** | `capture.target_fps`. If the device cannot sustain the floor, the app reports "degraded mode" rather than silently producing garbage windows. |

**v2 lessons forcing this design:** [g] (CameraX rotation offload didn't engage on the
device — validate device-level assumptions), [a] (fps is hardware-floored). Capture is
where we *measure* the floor rather than assume it.

---

## S1 — Hand Detection & S2 — Pose Detection

Grouped because they share the same compute-floor reality and must run **in parallel**.

| | |
|---|---|
| **Responsibility** | Produce per-frame hand landmarks (2 × 21 × 3) and pose landmarks (33 × {x,y,z,visibility}) from the frame. |
| **Input** | A single timestamped frame from S0. |
| **Output** | Raw landmark sets + per-landmark presence/visibility confidences. Face is **not** run (disabled per lesson a). |
| **Metric** | Per-model inference latency (ms) and detection-hit rate. Combined S1+S2 latency is the dominant per-frame cost. |
| **Flag / fallback** | `landmarker.backend` (MediaPipe Tasks default, but swappable per lesson a), `pose.cadence` (see below), `hands.model_complexity`. |

**Load-bearing facts:**
- **~70% of every frame's time is these two models** ([lesson a](docs/05-v2-lessons-map.md)).
  Parallelizing pose+hands and disabling face took v2 from 4.37 → 8.10 fps (+85%), and that
  was ~the software ceiling. **Do not plan performance around "optimizing the code."** The
  only real levers are: lighter landmarker models, asymmetric cadence (below), or different
  hardware.
- **Neither can be dropped for features** ([lesson b](docs/05-v2-lessons-map.md)): ablating
  pose collapsed accuracy 35–83 points. Feature reduction is not a latency lever.

**Proposed new lever — asymmetric pose cadence (tradeoff, flagged):** hand landmarks change
fast (fingers); pose landmarks (shoulders, torso) change slowly. Run pose every N frames and
hold/interpolate between, spending the saved budget on hand fps. **Tradeoff:** lesson b says
pose *features* are load-bearing — but that's about feature *presence*, not sample *rate*.
Subsampling pose position while keeping it present is a different axis. This must be
**A/B-validated offline against the cross-signer set before shipping**; if accuracy drops it
is reverted via `pose.cadence = 1`.

---

## S3 — Tracking

| | |
|---|---|
| **Responsibility** | Maintain stable hand identity (left/right, and the same hand across frames) and smooth landmark jitter without adding latency. |
| **Input** | Per-frame raw landmark sets from S1/S2 (unordered, occasionally dropped). |
| **Output** | Identity-stable, gap-filled, lightly-smoothed landmark trajectories. |
| **Metric** | Identity-swap rate (how often L/R flips erroneously), and post-smoothing trajectory noise vs. lag tradeoff. |
| **Flag / fallback** | `tracking.smoothing` (One-Euro filter params), `tracking.max_gap_fill`. Disabled → raw passthrough. |

**Mechanism:** hand identity assigned by handedness label + nearest-neighbour association to
the previous frame's wrist position; short dropouts (≤ `max_gap_fill` frames) linearly
interpolated; smoothing via a **One-Euro filter** (low lag at speed, strong smoothing at
rest — matters because we're resolving 200 ms signs and cannot afford a laggy smoother).

---

## S4 — Feature Processing

| | |
|---|---|
| **Responsibility** | Turn identity-stable landmarks into the **normalized, versioned feature vector** that is the contract between perception and model. This is the *runtime* mirror of the offline data pipeline (doc 02) — the exact same normalization math must run in both places. |
| **Input** | Tracked landmark trajectories. |
| **Output** | One feature vector per frame conforming to the [feature/schema contract](docs/06-feature-schema-contract.md) (scale-, orientation-, handedness-normalized). |
| **Metric** | Train/serve skew: numerical divergence between offline-extracted and on-device-extracted features on the same clip must be ~0. This is a *correctness* metric, not accuracy. |
| **Flag / fallback** | `features.schema_version`, and per-normalization toggles mirrored from doc 02. |

**Critical constraint:** the normalizations in doc 02 (scale, orientation, handedness) are
**not** training-only. Whatever is applied to training data must be applied *identically*
here, frame by frame, or the model sees a distribution it never trained on. Train/serve skew
is the classic silent killer and gets a dedicated test harness.

---

## S5 — Temporal Understanding (the gating brain)

This single stage answers five of the pipeline-of-questions from the brief. It is the
cheap, fast front-end that decides **whether the expensive recognizer should run at all.**

| | |
|---|---|
| **Responsibility** | (a) *Is the person signing?* (b) *What phase — onset / hold / release?* (c) *How much motion now?* (d) *How informative is this frame?* (e) *Should inference run this tick?* |
| **Input** | Rolling buffer of normalized feature vectors from S4. |
| **Output** | A per-tick decision object: `{signing: bool, phase, motion_energy, informativeness, run_inference: bool}` plus the trimmed active span when a sign completes. |
| **Metric** | (1) Signing-detection precision/recall against labelled onset/release; (2) compute saved (fraction of ticks where recognition is *skipped*) vs. missed-sign rate. |
| **Flag / fallback** | `gating.enabled` (off → run recognition every tick, the v2 behaviour). |

**Mechanisms** (detailed in doc 02 §Signing detection / §Dead-time trimming):
- **Signing detector:** hysteresis thresholding on normalized wrist/hand **motion energy** +
  a "hands in signing space" spatial gate → 2-state (idle / signing) with min-hold to
  prevent chatter.
- **Phase (onset/hold/release):** derived from the motion-energy envelope — rising edge =
  onset, plateau = hold, falling edge = release.
- **Informativeness / run-gate:** skip inference on near-duplicate low-motion frames; always
  run during onset and hold. This is the "should inference run this tick?" lever and is what
  buys back compute for the higher hand fps in S1.

**Why this stage exists (anchor #3):** ~75% of a naive window is non-sign. S5 is what stops
the recognizer from spending its budget on transition/rest frames.

---

## S6 — Recognition

| | |
|---|---|
| **Responsibility** | Given the active temporal span, emit a **stream of per-class posteriors** — incrementally, within the sign's ~1 s lifetime. Not a single argmax over a fixed window. |
| **Input** | Streaming normalized features for the active span (gated by S5). |
| **Output** | Time-indexed posterior distribution over the gloss vocabulary (+ a blank/no-sign symbol). |
| **Metric** | Cross-signer, held-out **per-frame / per-emission** accuracy AND its calibration (reliability diagram). Reported alongside — never instead of — the end-to-end number. |
| **Flag / fallback** | `model.version`, `model.head` (softmax-classifier vs. CTC — see doc 03). |

**v2 lesson forcing this design:** [d] — the temporal *window* is the dominant remaining
latency, ~4× the sign, and `MIN_FRAMES` can't just be lowered (confidence doesn't stabilize
before ~frame 15). The only fix is an architecture that **emits incrementally**. S6 is
therefore specified as a streaming emitter from day one (doc 03), not a window classifier.

---

## S7 — Confirmation

| | |
|---|---|
| **Responsibility** | Decide *when* the streaming posteriors constitute enough evidence to **commit** a gloss — with a false-positive guard — and when to **wait for more evidence** instead. |
| **Input** | Time-indexed posteriors from S6. |
| **Output** | Committed gloss tokens with timestamps, or silence. |
| **Metric** | On held-out signers: **correct-commit rate at a fixed false-positive rate** (the full operating curve). Explicitly tracks the v2 failure: fraction of *correct* signs silently dropped as "none". |
| **Flag / fallback** | `confirm.operating_point`, `confirm.margin`, `confirm.stability_k`. |

**v2 lesson forcing this design:** [e] — v2's confirmation dropped ~50% of *correct* signs
as "none" cross-signer (~42% confirmed / ~50% silently dropped). The recognizer was fine; the
commit policy leaked. Confirmation is therefore a **tuned, FP-guarded component with its own
offline evaluation** (doc 04), not a threshold constant.

---

## S8 — Sentence Builder

| | |
|---|---|
| **Responsibility** | Turn the stream of committed glosses into fluent, de-duplicated, ordered output. |
| **Input** | Committed gloss token stream from S7. |
| **Output** | Human-readable phrase / sentence. |
| **Metric** | **End-to-end phrase-level accuracy** (gloss error rate / WER-style) on held-out signers signing real phrases — *this is the top-line system metric.* |
| **Flag / fallback** | `sentence.mode` (raw gloss passthrough ↔ smoothed ↔ LM-assisted). |

Detailed in doc 04.

---

## Cross-cutting: telemetry, flags, and ablation

Because the top-line metric is end-to-end, every stage emits structured telemetry keyed to a
frame/utterance id, so any stage can be ablated (via its flag) and the **end-to-end** number
re-measured on the held-out cross-signer set. That closed loop — flag → offline eval →
device smoke test → rollout/rollback — is the v2 discipline (§7) made structural.

| Stage | Flag key | Off-behaviour (fallback) |
|-------|----------|--------------------------|
| S0 Capture | `capture.target_fps` | Max sustainable, report degraded mode |
| S1/S2 Landmarkers | `landmarker.backend`, `pose.cadence` | MediaPipe, cadence=1 |
| S3 Tracking | `tracking.smoothing` | Raw passthrough |
| S4 Features | `features.schema_version` | Pinned contract version |
| S5 Gating | `gating.enabled` | Run recognition every tick |
| S6 Recognition | `model.version`, `model.head` | Last-good model |
| S7 Confirmation | `confirm.operating_point` | Conservative default (measured, not guessed) |
| S8 Sentence | `sentence.mode` | Raw gloss passthrough |
