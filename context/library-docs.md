# Library Docs

Project-specific usage for every third-party library. This covers **how AppHear 3 uses each
tool**, not generic documentation.

## Order of Authority

```
Installed skill / MCP (real-time docs) → this file (project rules) → general knowledge
```

Never rely on training knowledge alone for these APIs — they change, and MediaPipe/TFLite/
Keras all have version-sensitive behavior. Load the library's skill first (see AGENTS.md).

---

## MediaPipe Tasks — Hand + Pose Landmarkers

Used in **both** offline extraction (Python) and runtime (Kotlin). Same models both sides so
features match.

- **HandLandmarker:** 2 hands, 21 landmarks × (x, y, z). Keep presence/handedness scores.
- **PoseLandmarker:** 33 landmarks × (x, y, z, visibility). Use **world landmarks** for yaw
  normalization (N2); image landmarks for the rest.
- **Face landmarker: never enabled** (v2 lesson a — it was the fps killer).
- Run hand + pose **in parallel** (v2 lesson a: parallelizing + face-off was the +85% win).
- **Offline:** extract at the clip's native fps (max temporal resolution to resample down).
- **Runtime:** LIVE_STREAM mode; decouple inference cadence from capture; `pose.cadence`
  allows running pose less often (A/B-gated only).
- Carry per-landmark visibility/presence forward — the quality gate (Q) and missing-data
  convention need them.

**Rule:** the offline and runtime landmarker configs (model variant, num_hands, min
confidences) must match, or features won't match. Pin them in config.

---

## TensorFlow / Keras — model + training

- **Encoder:** causal TCN — stacked **dilated `Conv1D` with causal padding** (dilations
  `1,2,4,8`), residual blocks, ~64–128 channels, receptive field ≈ one sign (~15–25 frames).
  Shared across all phases; only the head changes.
- **Heads:** Phase 0 = global-pool → softmax; Phase 1 = per-frame softmax; Phase 2 = CTC
  (`tf.nn.ctc_loss`, blank = "no sign").
- **Streaming:** design the encoder so causal conv state can be carried frame-by-frame at
  inference (ring buffer) — no full-window dependency.
- **Determinism:** set `tf.keras.utils.set_random_seed`; log it.
- **Never** put dataset normalization inside the model graph — that lives in `pipeline/`.
  The model consumes already-normalized features (the versioned contract).

**Rule:** anything that must run identically on-device (normalization) stays in `pipeline/`,
not in Keras preprocessing layers, so the Kotlin S4 port can match it.

---

## TFLite — on-device export & inference

- Convert with the **native TFLite converter**; target **INT8** (post-training quantization
  with a representative dataset drawn from real normalized features).
- **CPU / XNNPACK delegate baseline. Do NOT use the GPU delegate** (v2 lesson g: ANR on
  `createFromOptions`). GPU only as a flagged, off-main-thread, device-measured experiment.
- **Load async, off the main thread** (v2 lesson h).
- Verify the exported model against the Keras model on a held-out batch (quantization drift
  check) before it counts as passing the eval gate.
- Ship a **schema manifest** with each model artifact: `schema_version`, input shape,
  operating-point config. The runtime refuses a mismatched contract.

---

## CameraX (Android, S0)

- Use **ImageAnalysis** with a dedicated executor; `STRATEGY_KEEP_ONLY_LATEST` so inference
  never queues stale frames.
- **Do not assume rotation offload engages** (v2 lesson g) — verify on-device; handle
  rotation explicitly if it doesn't.
- Timestamp frames on a monotonic clock; expose `capture_fps`.
- Capture cadence is decoupled from inference cadence — capture as fast as the device allows,
  gate inference in S5.

---

## Datasets

### ASL Citizen (primary)
- Isolated citation-form clips, signer-diverse. Load video + gloss label + `signer_id`.
- **`signer_id` is mandatory metadata** — splits depend on it. If a clip lacks it, quarantine.
- Clips contain lead-in/lead-out → always run D1/D2 (signing detection + dead-time trim).

### ASLRecorder2 (aux)
- 258-float / 10-field JSON schema lineage. Schema-controlled captures for vocabulary
  gap-filling and on-device-matched samples.
- Map its fields onto the versioned sidecar in [`feature-schema.md`](feature-schema.md).

**Rule:** never mix sources without recording `source` per sample; never build a split that
puts one signer in two partitions.

---

## Testing (pytest)

- Every normalization stage has a unit test with a known input → expected normalized output.
- The **skew test** is mandatory: same clip through `pipeline/features` (Python) and the
  `android/features` port (via a golden-vector fixture) must match within tolerance.
- Eval-harness metrics have regression tests on a tiny fixture dataset.
