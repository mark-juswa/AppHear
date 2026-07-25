# 03 — Model Architecture

*Deliverable §8.3: recommend a temporal model from §5, justified against the three selection
criteria and the on-device constraint, and sketch the migration path toward streaming/CTC.*

---

## The three selection criteria (from §5, in priority order)

1. **Streaming-capable / incremental** — can emit *before* a full window fills. This directly
   attacks the window-latency problem in [lesson d](docs/05-v2-lessons-map.md).
2. **Fits the on-device compute floor** from [lesson a](docs/05-v2-lessons-map.md) — the
   landmarkers already eat ~70% of the frame budget; the temporal model gets the rest.
3. **Models frame order and speed**, not just presence — a *process over time*, not a bag of
   frames (v2's flat `30 frames → classifier` failure).

## Candidate scorecard

| Candidate | Streaming (1) | On-device cost (2) | Order/speed (3) | Verdict |
|-----------|:---:|:---:|:---:|---|
| **Causal TCN** | ✅ native (ring-buffer of dilated conv activations) | ✅ cheap, conv-only, TFLite-friendly | ✅ dilations model multi-scale timing | **Recommended encoder** |
| Efficient GRU | ✅ native (carries hidden state) | ✅ small, well-understood on mobile | ✅ recurrent order | Strong #2 / fallback |
| Lightweight Transformer | ⚠️ needs streaming attention / caching | ⚠️ attention compute + KV memory | ✅ excellent | Later, if budget allows |
| TSM on 2D backbone | ✅ near-zero-cost shift | ✅ cheap temporal add-on | ⚠️ presence-biased | We feed landmarks, not pixels — less fit |
| MobileViT-temporal | ⚠️ | ⚠️ | ✅ | Overkill for a landmark stream |

---

## Recommendation: **Causal TCN encoder + swappable head**

A **causal, dilated Temporal Convolutional Network** as the shared temporal *encoder*, with a
**swappable output head** that changes across the migration phases without retraining the
encoder from scratch.

**Why TCN wins on all three criteria:**
1. **Streaming is native.** Causal convolutions only look *backward*; at inference you keep a
   ring buffer of each layer's recent activations and push one frame at a time — output
   emits every tick with fixed, bounded per-frame cost. No "fill the window then decide."
2. **On-device cost is low and predictable.** Pure 1D convolutions quantize cleanly to
   TFLite INT8, have no recurrent serial dependency (fast, parallel training; deterministic
   inference latency), and the receptive field is set by dilation depth, not by holding a
   long tensor in memory.
3. **Order and speed are modelled explicitly.** Stacked dilations `1,2,4,8,…` give a
   multi-scale temporal receptive field — it sees both the fast finger transition and the
   slow two-handed arc within one sign's ~1 s lifetime (anchors #1–#2).

**Input:** the per-frame normalized feature contract (doc 06) as a `[C, T]` stream
(`C` = feature channels). **Encoder output:** a `[H, T]` sequence of temporal embeddings —
one embedding per input frame, causally computed.

**Why not GRU as primary:** it's the close #2 and the designated fallback (`model.arch=gru`).
TCN is preferred because it parallelizes in training, has deterministic per-frame latency,
and quantizes more predictably — but GRU is kept as a validated alternative because on some
SoCs a small GRU may quantize/run faster, and that's a *device-measured* decision
([lesson g](docs/05-v2-lessons-map.md): validate device assumptions), not a paper decision.

**Sizing:** target a receptive field of ~1 sign (~15–25 frames at the ≥15 fps floor) — e.g.
4–6 residual blocks, dilations `1,2,4,8`, ~64–128 channels. Exact size is fixed by the
compute budget left after S1/S2, measured on-device, not assumed.

---

## Migration path: isolated classifier → streaming → CTC

The whole point is that **the encoder is shared across phases**; only the head and the data
regime change. This is what lets us bootstrap on the easy problem and grow into the hard one
without throwing work away.

### Phase 0 — Isolated classifier (bootstrap & validate the pipeline)
- **Data regime:** duration-normalized (N4 on), trimmed, fully-normalized spans (doc 02).
- **Head:** temporal global-pool over the encoder output → softmax over the gloss vocabulary.
- **Goal:** prove the *data pipeline and features* on the clean, isolated problem, and get a
  first **cross-signer held-out** accuracy number. This is deliberately the flattering
  regime — its job is to validate plumbing, not to be the product ([lesson f](docs/05-v2-lessons-map.md)).
- **Ship gate:** cross-signer per-sign accuracy that clears a threshold *and* a calibration
  check (doc 04 needs calibrated posteriors).

### Phase 1 — Streaming isolated (remove the window)
- **Data regime:** **N4 off** — real-timed spans (doc 02 §N4). The model now must handle
  duration itself.
- **Head:** per-frame softmax (encoder already emits per-frame), consumed by the
  [S7 confirmation](docs/04-confirmation-and-sentence-builder.md) evidence-accumulator.
- **What changes:** we stop pooling the whole span and start emitting incrementally. Same
  encoder weights, fine-tuned. This is where [lesson d](docs/05-v2-lessons-map.md) (the
  ~3.7 s window) is actually killed — decisions now form *within* the sign's lifetime.

### Phase 2 — CTC (continuous / connected signing)
- **Data regime:** connected sequences (multiple glosses per clip); labels are gloss
  *sequences* with no frame-level alignment.
- **Head:** linear → **CTC** over `{vocab ∪ blank}`. CTC's blank symbol *is* the principled
  "no sign / transition" label — the exact thing v2's confirmation policy was faking with a
  conservative threshold ([lesson e](docs/05-v2-lessons-map.md)).
- **Decode:** streaming/online CTC — greedy or a small beam with a gloss-level language model
  (shared with [S8](docs/04-confirmation-and-sentence-builder.md)). Commit on CTC posterior
  peaks past the confirmation gate.
- **Convergence:** this is the CTC-based continuous-recognition direction already scoped in
  the ASLRecorder2 roadmap ([brief §5](../README.md)). We **design toward it from Phase 0**
  (causal encoder, per-frame outputs, blank-aware confirmation) so Phase 2 is a head swap and
  a data-regime change, **not** a rebuild of a sliding-window state machine.

| | Phase 0 | Phase 1 | Phase 2 |
|--|--|--|--|
| Encoder | Causal TCN | same (fine-tuned) | same (fine-tuned) |
| Head | pool → softmax | per-frame softmax | CTC (+ blank) |
| N4 duration resample | **on** | **off** | off |
| Emits | 1 label / span | per-frame | per-frame + alignment-free seq |
| Kills lesson | c, f (pipeline) | d (window latency) | d, e (streaming + no-sign) |

---

## On-device deployment notes (forced by v2 lessons)

- **TFLite, INT8 quantized**, CPU/XNNPACK delegate as the baseline. **The GPU delegate is
  *not* assumed** — v2's GPU delegate caused an ANR (blocking `createFromOptions` on the main
  thread) and was removed ([lesson g](docs/05-v2-lessons-map.md)). If GPU is revisited it is
  a *measured, flagged* experiment off the main thread, not a default.
- **Async model load off the critical path.** Model loading cost v2 ~1 s in `onCreate`
  ([lesson h](docs/05-v2-lessons-map.md)). The TCN loads on a background thread; the UI comes
  up in a "warming up" state and the recognizer attaches when ready.
- **Deterministic per-frame latency** is a first-class requirement: the streaming TCN's
  cost per tick is constant, which is what makes the ≥15 fps floor
  ([S0](docs/01-system-architecture.md)) achievable and *measurable* rather than
  spiky. Report **p50 and p95** per-frame model latency on-device, not the mean.
