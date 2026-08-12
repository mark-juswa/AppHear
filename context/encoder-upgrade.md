# Encoder Upgrade Experiment (S6 model swap — ST-GCN / small transformer)

*The dedicated contract for the next accuracy effort: replacing the 169K-param causal TCN with a
stronger encoder. Written 2026-07-07 after web research verified against the running system.
Status: **PLANNED / PARKED** — the developer chose to finish the project first; this file exists so
the experiment starts from verified facts, not re-derived guesses.*

**Epistemics discipline for this file:** every claim is tagged **[VERIFIED]** (measured on our
system or read from the cited paper), **[ESTIMATE]** (defensible extrapolation — a gate decides,
never the estimate), or **[CHECK-AT-BUILD]** (must be looked up/tested when building — do NOT
invent it). If a claim here has no tag, treat it as [ESTIMATE].

Related: `recognition-accuracy.md` (why accuracy is an ongoing effort + the full research trail),
`architecture.md` (S6's place in the 9-stage pipeline), `build-plan.md` (post-Phase-3 track),
`eval-protocol.md` (all gates are cross-signer, end-to-end), `feature-schema.md` (untouched here).

---

## 1. Why (the verified case)

| Model | Input | Params | ASL Citizen 2,731-class top-1 (cross-signer test) |
|---|---|---|---|
| Our causal TCN (v3.0) | MediaPipe landmarks (258 feats) | 169K | **31.4%** [VERIFIED — our eval] |
| ST-GCN (paper baseline) | MediaPipe landmarks (27 kp) | ~3M | **59.5%** / R@5 82.7 [VERIFIED — [arXiv:2304.05934](https://arxiv.org/abs/2304.05934)] |
| I3D (paper, raw video) | RGB video | ~12M | 63.1% [VERIFIED — same paper; NOT deployable for us] |

Same landmark input, same official 11 test signers → **the TCN under-fits; the system is
architecture-limited, not (only) data-limited.** [VERIFIED protocol match: our test = 29,770 of the
official 32,941 test clips (90.4% after quality gate), same signers; our features are a superset of
their 27 keypoints.]

Supporting scale (context, not gates): WLASL pose baselines — Pose-GRU 46.5% < Pose-TGCN 55.4% <
transformer approaches ~64–74% [VERIFIED — [WLASL paper](https://arxiv.org/pdf/1910.11006) +
SPOTER line]; SignBart shows a **750K-param** encoder over skeleton coords is competitive
[VERIFIED claim of the paper, [arXiv:2506.21592](https://arxiv.org/abs/2506.21592) — its exact
ASL-Citizen number NOT verified: [CHECK-AT-BUILD]].

**Explicitly rejected (do not re-litigate):** LSTM/BiLSTM (weakest modern pose option — numbers
above); I3D/video CNN (raw-video compute we don't have — landmarkers are 95% of the frame
[VERIFIED, device profiling]); MediaPipe VIDEO mode (parity wound — see
`recognition-accuracy.md` §4); SignGemma (not released as of 2026-07 on the official
[Gemma models page](https://deepmind.google/models/gemma/); GB-scale sentence-translation model —
wrong task/size; future offline-teacher candidate only).

## 2. Device budget (verified, not assumed)

- Our TCN ≈ 25 MFLOPs / 96-frame window; measured **0.5 ms/tick on device** → effective ~50 GFLOPS
  INT8/XNNPACK. [VERIFIED — computed from architecture + the `AppHearPerf` profiling]
- Full-size ST-GCN at our window (96 f / 27 kp / 1 person, scaled from published ~3.5 GFLOPs) ≈
  0.6 GFLOPs → **~12 ms/tick → fps 7.7 → ~7.1**. Worst case (INT8 graph kernels 2–3× less
  efficient): 25–40 ms → fps ~6; mitigations = slim variant (1/4 channels ≈ ~1 ms) or recognize
  every 2nd tick. [VERIFIED arithmetic; kernel-efficiency factor is ESTIMATE]
- SignBart-class 750K encoder ≈ ~3 ms/tick. [ESTIMATE from param ratio]

## 3. What changes and what MUST NOT change

**Changes:** ONLY the S6 model (`streaming.tflite` + `model_manifest.json`) and its offline
training code. That's it.

**Does NOT change (the parity guarantee):**
- Landmarkers (S1/S2), IMAGE mode, GPU-delegate flag — untouched.
- S4 features: same v3.0 258-vector, same `SessionNormalizer`, same skew tests. If candidate A's
  keypoint-subset ablation wins, the subset is taken **inside the model graph** (a fixed gather on
  the 258 input) so the Android feature path still produces the same 258 — **no schema change, no
  S4 edit, no new skew surface.**
- S5 gating, S7 confirmation, top-3 UI, sentence builder, handedness — untouched.
- **The TFLite I/O contract is frozen:** input `[1, 96, 258]` float32, output `[1, 96, num_classes]`
  float32. A clip-level (non-causal) encoder satisfies this by computing its single clip posterior
  and **tiling it across the 96 output frames inside the exported graph**. Result: `Recognizer`,
  `Confirmation`, `ModelContract`, and all Android code run **byte-identically unchanged** — the
  deploy is an asset swap, exactly like the conversational-model deploy.

**One architectural decision this supersedes:** "causal from day one" (Phase-0 decision, made so
the encoder transfers to streaming/CTC). The F19 runtime re-runs the full `[onset..t]` buffer every
tick [VERIFIED in `Recognizer.infer` / `RecognitionPipeline`], so bidirectionality within the
already-seen buffer leaks no future frames. Cost: if Phase 2 (CTC, currently data-blocked) revives,
the encoder choice must be revisited. Accepted trade.

## 4. The two candidates (build A first; B is the fallback and the tiebreaker)

**A — ST-GCN-class skeleton model** (primary; the 59.5% evidence is on our exact benchmark).
Recipe items worth copying from the paper [VERIFIED they used them; exact values CHECK-AT-BUILD]:
27-keypoint OpenHands subset (exact index list: look up the OpenHands repo at build time — do NOT
guess it; fallback ablation = our full 75 landmarks), ≤128-frame window (we keep 96 — contract),
shear + rotation augmentation, Adam + cosine annealing, ~75 epochs. Graph adjacency: hand + upper
body skeleton edges [CHECK-AT-BUILD from OpenHands/ST-GCN reference implementation].
INT8 risk: graph conv ops may quantize/convert badly → implement graph conv as fixed-adjacency
matmul + regular conv2d if needed.

**B — small transformer encoder (SignBart-style, ~0.7–2M params)** — plain dense/MHA/LayerNorm ops
(TFLite-friendly, no graph tricks). Build if A's export fails, or build anyway as the competitor;
**the cross-signer eval picks the winner, not preference.**

**Training regime (both candidates):**
- Data: `features_streaming_conversational[_fps]` (236 classes) — already built. Raw stage-E
  landmarks for ALL splits exist on disk (`derived/apphear3/landmarks/`) [VERIFIED] if a new
  feature layout is ever needed — but the default plan needs none.
- Keep: fps-augmentation (the phone is ~4–8 fps), label smoothing, weight decay, rotation/scale/
  noise augmentation. Add: shear augmentation, cosine annealing.
- **Add prefix augmentation (REQUIRED for non-causal commits):** for each training clip of real
  length L, additionally train on truncated prefixes (draw t uniform in [max(4, ⌈0.3·L⌉), L], keep
  frames [0..t), re-pad to 96) so the model learns to classify PARTIAL signs — mirroring the
  runtime, where S7 asks for a posterior mid-sign. Without this, commits would stall until sign
  end (and F13 showed confidence should peak MID-sign). Combinable with fps-aug in one expanded
  dataset build (extend `pipeline/features/fps_augment.py`).

## 5. Ordered build steps (each independently verifiable; STOP at any failed gate)

1. **INT8 export smoke-test FIRST** — ✅ **DONE 2026-07-07, PASS** (`deploy/smoke_gcn_export.py`,
   through the production `_convert`). Full-size ST-GCN (2.75M params) converts, XNNPACK
   instantiates, contract exact (`[1,96,258]→[1,96,236]`, tiled dev 0.0). The frozen-Dense
   adjacency + Conv2D formulation (`model/model_gcn.py`) needed NO matmul rewrite. [VERIFIED]
   **Latency (desktop-measured, device-projected via the TCN's known 0.5 ms):** full 64-128-256 =
   ~38 ms/tick (OVER gate — the §2 "worst case" band was right, the ~12 ms estimate was
   optimistic); 3/4-width ~23 ms; **half-width 32-64-128 (10 blk, 749K params, 759 KB) ≈ ~11
   ms/tick → SELECTED as candidate A**. Full-size retained as an offline accuracy-ceiling
   reference (affordable via recognize-every-2nd-tick if its accuracy justifies it). [VERIFIED]
2. **On-device latency probe** (reuse `FeatureFlags.PROFILE_STAGES`): measure ms/tick with the
   half-width INT8 model in the app. Gate: **≤20 ms**. NOTE (conscious deviation): since training
   here costs minutes not days, the probe may run with the TRAINED artifact at deploy time; the
   desktop projection (~11 ms, 45% margin) makes pre-training probing low-value.
3. **Train candidate A** on conversational-236 with the §4 regime (fps-aug + prefix-aug). Evaluate
   with the EXISTING harness: native / k4 / k8 (`eval.streaming --features-dir ...`).
   ✅ **TRAINING-SPEED ROUND (2026-07-07, measured):** CPU-only training (TF≥2.11 native Windows
   has no GPU) made the first half-width config **46.6 min/epoch** (≈44 h for 60 epochs) —
   unacceptable. Measured fixes: XLA `jit_compile` = **3× WORSE** on this CPU (REJECTED);
   **early temporal strides {0:2, 4:2} + `UPPER51` keypoint subset** (both hands complete + pose
   nose/shoulders/elbows/wrists/hips; drops face/legs — safe for ASL) = **24.0 min/epoch (~2×)**.
   Candidate A is now: half-width 32-64-128, early strides, upper51 → **719K params, 756 KB INT8,
   predicted ~5 ms/tick device** (re-smoked through the production path incl. the GATHER op —
   PASS, contract exact). Subset is taken INSIDE the graph — input stays 258, no S4 change.
   Realistic wall-clock: ~24 min/epoch × early-stop (~25–35 epochs) ≈ **10–14 h = one overnight
   run**, resumable (see below). Config is SELF-RESUMING: `warm_start_from` points at the run's
   own `best.keras` — first run starts fresh; after Ctrl+C, re-running the same command resumes
   from the best checkpoint (verify: banner shows `warm_started_layers` > 0 on resume; epoch
   counter and optimizer state restart; `history.csv` is overwritten — model never lost).
   **RESUME BUG FIXED (2026-07-10):** the first GCN build used Keras `Lambda` layers, whose
   checkpoints CANNOT be deserialized (safe-mode block + missing output_shape — the developer's
   first overnight attempt hit this on resume). Fix: `model_gcn.py` rewritten **Lambda-free**
   (direct KerasTensor slicing + `keras.ops`); save/load roundtrip verified at DEFAULT safe mode;
   `warm_start_encoder` now loads with `compile=False, safe_mode=False` (own artifacts trusted).
   The unloadable epoch-2 checkpoint (val_pf_acc 0.012, ~untrained) was sidelined as
   `best_lambda_era.keras.bak` — negligible loss. Export smoke re-PASSED with the Lambda-free
   model (756 KB, ~6 ms/tick predicted). RULE going forward: **no `Lambda` layers in any model
   that must checkpoint/resume or export.**
   ✅ **TOOLING READY 2026-07-07:** `pipeline/features/fps_augment.py --prefix-copies` implements
   §4 prefix-aug (t ~ U[max(4,0.3L), L), 75% of prefixes also fps-subsampled); dataset built at
   `features_streaming_conversational_fps_prefix/` (train 3,309→19,574 clips); trainer supports
   `model.type: gcn` (`train_streaming.py`); config `model/config/train_streaming_conversational_gcn.yaml`
   (half-width, NO warm start, 60 epochs); trainer GCN path smoke-tested green; 117 tests pass;
   asset backup `_backup_conversational_tcn/` created (§6). **Developer runs:**
   `.venv\Scripts\python.exe -m model.train_streaming --config model/config/train_streaming_conversational_gcn.yaml`
4. **Accuracy gates (pre-registered, cross-signer test):** native top-1 **≥ 0.66** (current 0.612
   +5pt) AND k8 top-1 **≥ 0.56** (current 0.527 +3pt). [The ~0.75–0.85 ceiling talk is ESTIMATE —
   these gates decide.]
5. **Confirm + export via the existing configs** (clone `confirm_conversational_fps.yaml` /
   `export_conversational_fps.yaml` → `*_gcn.yaml`; re-fit temperature — do NOT reuse 0.647, it is
   the TCN's calibration). Existing INT8 gate applies (top-1 delta ≤0.01, prob-diff ≤0.005).
6. **(Optional in parallel) train candidate B**; winner by the same gates.
7. **Deploy = asset swap with backup** (§6), rebuild, device-verify against
   `context/device-smoke.md`. Watch specifically: commit latency (frame index in `COMMIT` logs)
   must not degrade vs the TCN — the prefix-aug check.
8. Record results in `recognition-accuracy.md` + `progress-tracker.md`, win or lose.

## 6. Safety net (non-negotiable — the system must always be revertible to today)

**Preserved artifacts (never deleted or overwritten):**
- Deployed-today model: `runs/tcn_streaming_conversational_fps_v30/` (+ its configs) — the current
  working system.
- App-asset backups: `android/app/src/main/assets/_backup_250fps/` (the 250 model) — and BEFORE
  this experiment deploys anything, create `_backup_conversational_tcn/` the same way (copy
  `streaming.tflite`, `model_manifest.json`, `vocab.json`, `recognition_config.json`).
- All prior runs (`tcn_isolated_v30`, `tcn_streaming_v30`, `tcn_streaming_reduced_v30`,
  `tcn_streaming_reduced_fps_v30`, `tcn_streaming_conversational_v30`) and all feature dirs.

**New artifacts get NEW names:** runs → `runs/gcn_conversational_fps_v30/` (or
`tfm_...` for candidate B); configs → `*_gcn.yaml`; expanded features →
`features_streaming_conversational_fps_prefix/`. Nothing existing is modified in place.

**Revert procedure (one step):** copy the 4 files from `_backup_conversational_tcn/` back into
`android/app/src/main/assets/`, rebuild (`gradlew assembleDebug`). No code revert needed — the
experiment changes no Android code (§3 contract). If Android code WAS touched for the latency
probe, it is flag-gated (`PROFILE_STAGES`) and defaults off.

**Kill criteria (stop the experiment, keep the TCN):** export unconvertible after the matmul
rewrite AND candidate B also fails gates; or ≥2 training rounds without passing gate 4; or device
latency >20 ms with no slim variant passing; or commit latency visibly degrades on device.

## 6b. oneDNN INT32 crash (FIXED 2026-07-10) — read before debugging a silent training death

**Symptom:** `train_streaming` on the GCN config prints `Epoch 1/60`, then `oneDNN supports DT_INT32
only on platforms with AVX-512. Falling back to the default Eigen-based implementation if present.`,
then **silently exits** — no Python traceback, `history.csv` is 0 bytes (epoch never completed).

**Root cause (VERIFIED, not guessed):** a `faulthandler` repro caught a `Windows fatal exception:
access violation` on the FIRST training step (on a 320-sample subset → NOT OOM). The GCN encoder's
`upper51` **INT32 keypoint-gather** hits oneDNN's INT32 primitive, which on a CPU without **AVX-512**
falls back to a path that **segfaults**. A/B proof: same subset fit crashes with oneDNN ON, runs
clean (`5/5 - 24s`) with `TF_ENABLE_ONEDNN_OPTS=0`.

**Fix:** `os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")` at the TOP of `model/train_streaming.py`
AND `eval/streaming.py` (before any TF import). Verified: the real `python -m model.train_streaming`
path trains without a shell env var. Negligible numeric effect; harmless for the TCN (no INT32
gather). The visible tell it's active: the "oneDNN custom operations are on" startup line disappears.

## 7. Environment

Train/eval/export ONLY with `.venv\Scripts\python.exe` (Keras 3.15.0) — system Python 3.13.2
cannot load 3.15-saved models (`input_axes` deserialization error). [VERIFIED — bit us twice]

## 8. Relationship to the 2026-07-24 Target Architecture Decision

This remains the first controlled architecture baseline, not the selected final production design. Run the frozen-contract ST-GCN experiment to isolate encoder quality. A pass proves graph structure is useful; it does not prove the 258-feature representation is sufficient. The selected long-term direction is the hybrid landmark + RGB hand-appearance architecture recorded in `context/recognition-accuracy.md`. The next gate after ST-GCN is an identical-split comparison of landmark graph, RGB hand crops, and fused hybrid input.

## 2026-07-25 Correction - Existing GCN Result

The slim early-stride `gcn_conversational_fps_v30` run is complete and failed (test top-1 0.1588,
top-5 0.4374). The full-capacity fair-comparison config exists but has no run artifact. Do not
describe ST-GCN as unrun or expected to win. The governing next-step protocol is E1 in
`recognition_upgrade/EXPERIMENT_MATRIX.md`: sanity/overfit checks first, then a matched
full-capacity comparison, with the TCN retained if it fails.
