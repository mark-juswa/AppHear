# Recognition Accuracy & Detection Quality

*Why on-device detection is hard even when the offline numbers look good â€” the verified root
cause, the secondary contributors, and the real levers. This file exists because the build-plan
was an ARCHITECTURE plan; it has no dedicated "make recognition accurate" feature, and
`eval-protocol.md` explicitly labels the isolated/offline accuracy "the flattering regime whose
job is to validate plumbing â€” not the product." So accuracy is a separate, ongoing effort tracked
here.*

**Discipline for this file (the project's core rule): every claim here is MEASURED, not assumed.
When a new accuracy idea comes up, verify it against data before acting.**

---

## The gap that started this

- **Offline (cross-signer test):** the 250-class reduced streaming model gets **top-1 0.626 /
  top-5 0.865**, and when it commits it is right **~71%** of the time.
- **On the developer's phone (old Snapdragon/Adreno, Xiaomi):** "hard to detect" â€” a sign has to
  be held for many seconds to get a single commit, and most attempts drop.

A ~2Ã— offline accuracy win (below) did NOT translate to the device. The reason is not the model's
accuracy â€” it's a train/serve **frame-rate** mismatch.

---

## What has been done for accuracy (so far)

**Vocabulary reduction (biggest lever tried).** The full model distinguishes ALL 2,731 ASL Citizen
signs from ~13 clips each â†’ ~31% top-1 (data-limited baseline). Retraining on the **top-250
data-richest signs** (`pipeline/features/reduce_vocab.py`, no re-extraction) ~doubled offline
accuracy: 0.31â†’**0.626** top-1, 0.60â†’**0.865** top-5. Pilots confirmed the trend (100 classes â‰ˆ
41%/74%, 20 â‰ˆ 54%/87%). Tooling: `train_streaming_reduced.yaml`, `confirm_reduced.yaml`,
`export_reduced.yaml`. The 250-class INT8 model is deployed in the app.

This was necessary and real â€” but it improves the OFFLINE (30 fps) accuracy, which the device
can't realize yet because of the issue below.

---

## â˜… VERIFIED ROOT CAUSE â€” frame-rate / temporal mismatch (~12Ã—)

**The model was trained on ~30 fps native-timed features (N4 OFF = real timing preserved). The
phone sustains only ~2.5 fps through the full recognition pipeline. So the on-device input is ~12Ã—
temporally undersampled vs training â€” every sign is far outside the model's training distribution.**

Measured evidence (not assumed):
- **Training fps ~30** â€” from clip sidecars (`derived/apphear3/spans/*/*.span.json` `native_fps`:
  cluster at 25â€“30, median ~30).
- **Training sign length = median 33 frames** (p10 14, p90 60) â€” from
  `features_streaming_reduced/test.npz` `lengths`. That's ~1.1 s per sign at 30 fps.
- **Device rate ~2.5 fps** â€” from the on-device logcat: `S5 ONSET 10:03:43.042` â†’
  `COMMIT 'DOG1' at frame 31` at `10:03:55.342` = 31 frames in 12.3 s â‰ˆ 2.5 fps.
- **Consequence:** the same 1.1 s sign that is ~33 frames in training is only **~2.8 frames** on
  the phone. The causal-TCN's temporal receptive field (~15â€“25 frames â‰ˆ 0.5â€“0.8 s at 30 fps) has no
  meaningful signal in ~3 coarse frames where the hand jumps ~12Ã— farther between samples.
- This is also why a commit needed ~12 s of held signing: at 2.5 fps it takes that long to
  accumulate the frame count a 1 s sign should have delivered instantly, so normal-speed signs
  (~3 frames) never accumulate enough evidence â†’ drop.

**Why the phone is that slow (fixed facts, runtime-constraints.md):** ~70% of every frame is the
two MediaPipe landmarker models; on an old CPU that alone is ~8â€“15 fps (F17 settled at Low/Minimum
pose cadence). Recognition then forces full-rate pose + runs the TCN every frame â†’ ~2.5 fps.

**The offline eval never showed this because the offline test IS 30 fps.** The mismatch only appears
on-device.

---

## Secondary contributors (honest, smaller than fps)

- **SessionNormalizer deployment path is NOT skew-tested.** The `S4SkewTest` proved `clipFeaturesCausal`
  (per-clip) matches Python byte-exact, but the DEPLOYED `SessionNormalizer` (session-level running
  scale/roll over a bounded 256-frame window) has no golden-vector test. Likely minor (scale/roll are
  stable), but it is an unverified surface â€” add a skew test before trusting it.
- **Onset backoff loss, amplified by low fps.** On-device the recognition buffer starts at the S5
  onset (detected k_on frames late) with no pre-onset backoff, so the sign's first frames are lost.
  Offline features include a `backoff` extension. At 30 fps losing ~2â€“5 frames is minor; at 2.5 fps it
  can remove a large fraction of the already-tiny ~3-frame sign.
- **Confirmation temperature = 1.0 placeholder** (not the harness-fitted calibration T). Self-consistent
  with the confirm run (works, precision 0.71 offline), but not optimally calibrated.

## What is NOT the cause (ruled out)

- Not the 250-class model's accuracy â€” 0.626 offline is fine; the device just can't feed it 30 fps input.
- Not the handedness mirror-lock â€” that was a real logic bug, already fixed (default no-mirror).
- Not a build/compile error â€” clean build, lint, and unit tests all pass (verified repeatedly).
- Not garbage features â€” the model committed `DOG1` with confidence, so features are coherent, just
  temporally undersampled.

---

## Levers to fix it (ranked; verify each before/after)

1. **Retrain fps-robust (highest value, reuses the pipeline).** Add temporal/fps augmentation to the
   streaming trainer â€” randomly subsample training frames to simulate ~3â€“15 fps â€” so the model learns
   to recognize signs from few, coarse frames matching the device. Directly closes the temporal skew.
   Caveat: at ~2.5 fps there is very little information (~3 frames); this raises the floor but a faster
   device still helps.
2. **Raise device fps.** Faster/lighter landmarkers, lower analysis resolution, or simply a faster
   phone. The landmarkers are the bottleneck, not the TCN. A mid/high-end phone should reach the fps
   the current model already needs.
3. **Verify on a faster phone first** â€” cheapest diagnostic: if recognition works well at higher fps,
   it confirms fps is the dominant cause and de-risks the retrain.
4. **(Later) On-device resample-to-fixed-frames (N4-style) + matching training regime.** Buffer the
   sign and resample to a fixed frame count so frame-count matches training regardless of fps. Tension:
   N4 needs the full sign, which fights per-frame streaming emission; design carefully if pursued.

**Recommended next step:** option 1 (fps-augmented retrain of the 250-class model) plus option 3
(test on a faster phone to confirm the fps hypothesis end-to-end).

---

## How this was diagnosed (method to reuse)

Measured training fps from sidecars, measured training sign length from the feature npz, and derived
the device fps from the logcat commit timestamp + frame index â€” then compared. No guessing: the 12Ã—
ratio falls straight out of `~30 fps / ~2.5 fps`. Apply the same "measure both sides, compare" method
to any future accuracy hypothesis.

---

## â˜… UPDATE 2026-07-07 â€” fps-aug shipped, ceiling profiled, vocabulary rebuilt

Everything below is measured. This section supersedes the "recommended next step" above (option 1 is
now DONE, option 2 is the remaining lever, VIDEO-mode is evaluated-and-parked).

### 1. fps-augmented retrain â€” DONE, clean win, deployed (option 1)
`pipeline/features/fps_augment.py` (temporal subsampling: keep every k-th frame â†’ simulate low fps;
faithful because v3.0 features are POSITIONS). Retrained the 250-class model on fps-EXPANDED features.
Result at every frame rate: native **0.626â†’0.645**, k4(~7fps) **0.549â†’0.597**, k8(~4fps phone)
**0.496â†’0.547** â€” better everywhere, no tradeoff. Confirm @ phone-fps: precision-when-committed **0.73**.
INT8 exported + deployed. So the temporal skew is now handled on the MODEL side.

### 2. Device polish (both fixed real felt problems)
- **GPU delegate** (`FeatureFlags.LANDMARKER_TRY_GPU`, GPU-with-CPU-fallback) â€” lifted the phone
  **~3 â†’ 5-7 fps (~2Ã—)**. A deliberate sub-pixel landmark parity divergence, accepted for the fps win.
- **Commit spam fixed** â€” `RecognitionPipeline.awaitingRelease` = ONE commit per signing bout (was
  re-committing the still-held sign every frame â†’ `ROAST` x10). Cleaner UX, not accuracy.
- **No-hands false commits fixed** â€” S5 is pose-motion-primary, so arm motion with NO hands tripped
  onsets â†’ random commits. Fix: hand-presence gate (`signing.require_hands`, `LandmarkAdapter.handsPresent`)
  â€” onset needs a detected hand; losing hands for k_off frames ends the sign. Pure S5 gate, no parity cost.

### 3. â˜… fps ceiling is SYSTEMIC, not one weak phone â€” PROFILED
The app caps at **5-8 fps on MULTIPLE different phones** â†’ the ceiling is the PIPELINE, not the old
Xiaomi. Profiled on device (`FrameAnalyzer` `StageTimer`, tag `AppHearPerf`, now behind
`FeatureFlags.PROFILE_STAGES`): `convâ‰ˆ1.7 rotateâ‰ˆ14 handâ‰ˆ100 poseâ‰ˆ110 recogâ‰ˆ0.5 wallâ‰ˆ130 (~7.6fps)`.
**The two MediaPipe landmarkers are ~95% of every frame, ~100ms EACH even on the GPU delegate** â€” the
IMAGE-mode "detector-every-frame" tax, the same ~100ms on every phone. **Recognition (the 96-frame
TCN re-run) is FREE (0.5ms)** â†’ the F19 re-run design is vindicated; no model-side compute problem.

### 4. VIDEO/tracking mode â€” EVALUATED + DEFERRED (see memory `project-video-mode-deferred`)
The only lever that cuts a ~100ms landmarker is MediaPipe VIDEO/LIVE_STREAM (tracked) mode. Decided
NOT to pursue now: (a) it only skips the DETECTOR, not the landmark models (the bulk), so realistic
gain is ~10-11 fps â€” still under the 15 fps floor; (b) it re-opens the exact IMAGE-vs-tracked parity
wound v3 was built to avoid (F01 chose IMAGE deliberately; the model trained on stateless un-smoothed
landmarks); (c) v2 lesson g â€” device optimizations here don't reliably engage; (d) fps-aug made the
model robust to low FRAME RATE, NOT to tracked/smoothed landmarks. If revisited: throwaway on-device
fps measurement FIRST (flag, IMAGE default, reversible), then a VIDEO-mode skew eval before trusting it.

### 5. â˜… The vocabulary was USELESS for communication â†’ rebuilt on everyday words
Separate from accuracy: the deployed 250 vocab was DATA-RICHEST (CHEESEGRATER, OSTRICH, TRACTOR) â€”
useless for talking. Verified ASL Citizen's full 2,731 vocab CONTAINS **~89% of everyday English
words** (the missing ones are pronouns I/she/it = ASL *pointing*, not lexical signs, + grammar
particles ASL doesn't sign). So it was pure SELECTION. Curated a **236-word everyday vocab**
(`model/config/vocab_conversational.txt`, chosen by clip-count quality) via new `reduce_vocab --wordlist`.
Cross-signer results: baseline **0.606/0.885**, fps-aug **native 0.612 / k4 0.576 / k8(phone) 0.527/0.825**
â€” only ~2pt below the data-richest model at every fps, for a genuinely usable vocabulary. Confusions
are sensible near-synonyms (SITâ†”CHAIR identical handshape, PERSONâ†”PEOPLE, NOWâ†”TODAY), NOT random; the
feared question-word cluster did not materialize. **DEPLOYED** (Î¸_conf âˆ’1.2, temperature 0.647,
precision-when-committed 0.73). Revert path: `android/app/src/main/assets/_backup_250fps/`.

### Current accuracy picture (what's deployed now)
Conversational fps-aug 236-word INT8 model. On the phone (~7 fps â‰ˆ between k4 and k8): expect **top-1
~0.55-0.58, top-5 ~0.83-0.86, top-3 ~0.72-0.75**; when it commits, right **~73%**. The top-3 UI +
one-commit-per-bout + no-hands gate make this usable despite the fps ceiling.

### The binding constraint is now HARDWARE, not the model
Model side is well-optimized (fps-aug + useful vocab + calibrated confirm). The remaining dominant
lever is **raise device fps** (option 2) â€” faster phone or a genuinely lighter landmarker; VIDEO-mode
is the only software option and it's parked. Do NOT expect more from model retraining alone.

### Open / smaller items still true
- `SessionNormalizer` deployment path still has no skew test (unverified S4 surface).
- Onset backoff loss at low fps (first frames of the tiny sign lost) â€” unaddressed.
- Optional polish: trim a confused near-synonym pair (drop CHAIR keep SIT) to lift top-1.

### Environment gotcha (bit the developer twice â€” flag it)
Run all training/eval/export with **`.venv\Scripts\python.exe`** (Keras 3.15.0). System Python
(3.13.2) CANNOT deserialize models saved by 3.15 â†’ `GlorotUniform ... input_axes` error at
`load_model`. Prefer the full venv path over `Activate` (a fresh shell isn't activated).

---

## â˜… RESEARCHED ACCURACY ROADMAP (2026-07-07) â€” the next model-side effort

*Web-researched and verified against published benchmarks on OUR dataset. This section corrects an
earlier assumption and defines the staged plan for when accuracy work resumes.*

**â†’ The full build contract for this experiment (frozen I/O interface, prefix-augmentation spec,
ordered steps, pre-registered gates, kill criteria, and the one-step revert procedure) lives in
[`encoder-upgrade.md`](encoder-upgrade.md). That file is the source of truth for BUILDING it; this
section is the research trail behind it.**

### The correcting finding: we are ARCHITECTURE-limited, not (only) data-limited

The ASL Citizen paper itself ([arXiv:2304.05934](https://arxiv.org/abs/2304.05934), NeurIPS 2023)
reports baselines on the SAME 2,731-class, cross-signer protocol we use:

| Model | Input | Params | Top-1 | R@5 |
|---|---|---|---|---|
| **Our causal TCN (v3.0)** | MediaPipe landmarks (258) | 169K | **31.4%** | 59.8% |
| **ST-GCN** (their pose baseline) | MediaPipe landmarks (27 keypoints) | ~3M | **59.5%** | 82.7% |
| I3D (their video baseline) | raw RGB video | ~12M | 63.1% | 86.1% |

Same landmark input â†’ **~2Ã— our accuracy**. Our "data-limited (~13 clips/class)" story explained the
train/val overfit gap but NOT this gap: ST-GCN reaches 59.5% on the same ~13 clips/class. The tiny
TCN under-fits the task. Corroborating scale: on WLASL, Pose-GRU 46.5% < Pose-TGCN (graph) 55.4% <
transformer approaches (SPOTER ~64%, ensembles 73.8% on WLASL300/AUTSL); SignBart
([arXiv:2506.21592](https://arxiv.org/abs/2506.21592)) shows a **750K-param** BART-style encoder over
skeleton coordinates is competitive across WLASL/ASL-Citizen â€” small attention/graph models work.

### Why this is deployable on OUR device (VERIFIED against the actual system, 2026-07-07)

- **Compute headroom â€” computed from our own measurement, not assumed.** Our TCN â‰ˆ 25 MFLOPs per
  96-frame window and measures **0.5 ms/tick on device** â†’ effective ~50 GFLOPS (INT8/XNNPACK).
  A full-size ST-GCN at our window (96 f, 27 kp, 1 person, scaled from the published ~3.5 GFLOPs)
  â‰ˆ **0.6 GFLOPs â†’ ~12 ms/tick â†’ fps 7.7 â†’ ~7.1**. Realistic worst case (INT8 GCN kernels 2â€“3Ã—
  less efficient than the conv path): 25â€“40 ms â†’ fps ~6 â€” recoverable with a slim variant (1/4
  channels â‰ˆ 1 ms) or running recognition every 2nd tick. A SignBart-class 750K encoder â‰ˆ ~3 ms.
  The â‰¤20 ms/tick gate is realistic, not aspirational.
- **Data is ready â€” no re-extraction.** Verified on disk: per-clip raw stage-E landmarks exist for
  ALL splits (train 40,154 / val 10,304 / test 32,941 clips' npz+json under `derived/apphear3/
  landmarks/`), each with full `pose_image (T,33,4)` + `hands_image (T,2,21,3)`. Any keypoint
  subset (27-kp OpenHands), bone/velocity streams, or new layout is derivable offline from these.
- **Protocol is apples-to-apples.** Our test = 29,770 clips / 11 signers = the official 32,941-clip
  test (same held-out signers the paper evaluated on) minus extraction/quality dropouts (90.4%
  coverage). Our 31.4% used the SAME landmarks (a superset of their 27 kp) â€” the 59.5-vs-31.4 gap
  is not an input or protocol artifact.
- **Runtime slot verified in code.** `Recognizer.infer` re-runs a fixed `[1,96,258]` window every
  tick and `RecognitionPipeline` buffers from S5 onset; S7 consumes a posterior per tick. A
  clip-level (non-causal) model drops into the same slot; the confirmation machinery is unchanged.
- **Causality is NOT required anymore:** the F19 runtime re-runs the full `[onset..t]` buffer every
  tick, so a bidirectional/graph encoder over already-seen frames deploys unchanged (bidirectional
  only within the past window â€” no future leakage). Requirement it adds: **prefix-augmented
  training** (train on truncated sign prefixes) so mid-sign commits still work â€” analogous to what
  per-frame supervision gave the TCN.
- **No contract/parity impact:** same landmarks, same 258 features (or a measured keypoint subset â€”
  see below), same S4. Only S6 (the model) swaps â†’ existing INT8 export gate + confirm pipeline
  reuse as-is. TFLite supports the needed ops (graph convs = matmuls/convs; MHA supported).

### Ranked plan (staged, each gate = cross-signer eval, past runs preserved)

1. **A â€” ST-GCN-class skeleton model on the conversational 236** (primary). Recipe details from the
   paper worth copying: 27-keypoint OpenHands subset (vs our full 75 landmarks â€” measured ablation),
   â‰¤128-frame window, shear+rotation augmentation, cosine-annealing schedule. GATE: beat native
   0.612 by â‰¥5pt AND k8 0.527 by â‰¥3pt; INT8 export gate; per-tick latency â‰¤20 ms on device.
   Expected from the evidence: **native ~0.75â€“0.85 top-1** on the 236 vocab.
2. **B â€” small transformer/BART-style encoder (SignBart-like, ~0.7â€“2M params)** as the competing
   candidate; same gates; pick the winner by cross-signer eval (not preference).
3. **C â€” training-recipe upgrades** (apply to whichever wins): shear aug, cosine annealing, longer
   schedule, fps-aug (keep), prefix-aug (new, required), label smoothing (keep).
4. **D â€” multi-stream (joint+bone+motion) / light ensemble**: classic +3â€“5pt in the literature
   (SL-GCN-style); ~2Ã— recognizer compute (still trivial vs landmarkers). Only after A/B lands.
5. **E â€” self-supervised skeleton pretraining** (SignBERT+/Sigma/OpenHands-style): biggest published
   gains but a heavy lift (pretraining corpus + infra). Defer until Aâ€“D plateau.
6. **NOT chosen â€” LSTM/BiLSTM:** measured weakest of the modern pose options (see WLASL numbers);
   no on-device advantage over GCN/transformer at this scale. **NOT chosen â€” video CNN (I3D-class):**
   +3.6pt over ST-GCN in the paper but needs raw-video compute we demonstrably don't have.

### Foundation models (SignGemma etc.) â€” verified status 2026-07

**SignGemma** (Google DeepMind, announced 2025-05): ASLâ†’English *sentence translation* on a Gemma-3n
base. As of 2026-07 it is **still not listed** on the official
[Gemma models page](https://deepmind.google/models/gemma/) (Gemma 4 / MedGemma / TranslateGemma etc.
are; SignGemma is not) â€” availability = announcement + waitlist, third-party claims unverified.
Even when released: GB-scale memory vs our 227 KB model, and it solves a different task (continuous
translation, not gloss commit). **Decision: monitor, do not build on it.** Two legitimate future
uses: (a) **offline teacher** â€” distill/pseudo-label to strengthen our small on-device model;
(b) a future opt-in cloud-assist mode â€” which would contradict the "no cloud in critical path"
non-negotiable and is therefore a product decision, not a default.

### Honest expectations â€” what is VERIFIED vs still an ESTIMATE

**Verified (measure-both-sides discipline):** the 59.5%-same-input benchmark; our 50-GFLOPS device
budget and the ~12 ms ST-GCN tick cost derived from it; raw landmarks on disk for any feature
layout; protocol match; the runtime slot. **Still estimates until the retrain runs:** (a) the
~0.75â€“0.85 native top-1 on the 236 vocab is an extrapolation (59.5% full-vocab + the ~+29pt lift we
measured when narrowing 2731â†’236 for the TCN) â€” the â‰¥+5pt gate decides, not the estimate; (b)
ST-GCN behavior at LOW fps â€” the paper number is ~30 fps native; our fps-aug + k8 eval must confirm
the gain survives the phone regime; (c) TFLite INT8 conversion of graph-conv ops â€” engineering
risk (mitigation: implement graph conv as fixed-adjacency matmul + conv2d; smoke-test the export
FIRST, before any long training run).

A stronger encoder lifts accuracy at EVERY fps, but the **~7â€“8 fps hardware ceiling still caps the
device**: at ~4 fps a short sign is still ~3 frames. Expect the offline gain to translate into a
large but not 1:1 on-device gain. The fps lever remains hardware (see VIDEO-mode deferral above).

Sources: [ASL Citizen paper](https://arxiv.org/abs/2304.05934) Â·
[baseline details](https://arxiv.org/html/2304.05934) Â·
[SignBart](https://arxiv.org/abs/2506.21592) Â·
[WLASL baselines](https://arxiv.org/pdf/1910.11006) Â·
[GCN+BERT pose SLR](https://arxiv.org/abs/2012.00781) Â·
[Sigma skeleton pretraining](https://arxiv.org/pdf/2509.21223) Â·
[SignBERT+](https://arxiv.org/pdf/2305.04868) Â·
[Gemma models page](https://deepmind.google/models/gemma/) Â·
[SignGemma announcement](https://x.com/GoogleDeepMind/status/1927375853551235160)

---

## UPDATE 2026-07-18 - low-FPS runtime pass and controlled sign confusion

This update is based on Android logcat device runs after the profiling and low-FPS tolerance work. It supersedes the older unknown-bottleneck question but does not replace the deployed model or feature contract.

### What is now measured

- The bottleneck is still MediaPipe hand + pose landmarking, not TFLite recognition. Latest controlled log averages: hand about 62.8 ms, pose about 51.1 ms with pose cadence, recognition about 1.9 ms, total wall about 95.0 ms.
- `pose_every_n=2` with held last pose improved the processed rate compared with the fresh-pose-every-frame baseline, but the device still dips to about 5.5 FPS and averages about 8.8 processed FPS. This is below the preferred recognition floor and explains why short signs degrade on low-end devices.
- Camera buffering is not the current suspect. Camera input remains higher than processed FPS and the analyzer skips stale frames rather than building a raw-frame queue.
- Confirmation is no longer committing at frame 1 after the low-FPS `min_commit_frame=2` guard. Latest run had `Frame1Commits=0`.
- The UI stale-word issue was app-side behavior: idle/null states intentionally kept the previous committed gloss. That has been changed so release/idle clears the display.

### Controlled sign observations

Good or excellent in the latest user test:

- `CUT`
- `IMPORTANT`
- `SELL` mostly good
- `WANT2` mostly good when FPS is not collapsing

Confusion clusters that need model/data investigation:

- `KNOW` was predicted as `STRONG` / `SELL` / `STRONG`.
- `STREET` and `MUCH` confuse with each other and sometimes `ROAD` / `IMPORTANT`.
- `START` is near `THEN`; the model sometimes ranks `START` second but commits `THEN` first.
- Later signs became hard to detect when FPS dropped around 5-6 FPS, likely thermal or sustained-load degradation layered on top of class confusion.

### Current interpretation

The runtime is now measurable and more low-FPS tolerant, but the remaining accuracy problems are not a single app bug. They are a combination of:

1. Low processed FPS from MediaPipe, especially under sustained device load.
2. Very short effective sign clips at 5-9 processed FPS.
3. Specific model/dataset confusion clusters in visually similar or temporally similar signs.
4. Confirmation tradeoffs: aggressive confirmation reduces delay but can commit the wrong nearby class; stricter confirmation drops or delays signs.

### Recommended next accuracy work

- Do not loosen thresholds blindly. The current logs already show plausible top-2/top-3 neighbors; lowering gates may increase wrong commits.
- Build a controlled confusion report for the tested words and compare it to offline validation/test confusion for the same labels.
- Inspect training examples for `KNOW`, `STRONG`, `SELL`, `STREET`, `MUCH`, `ROAD`, `IMPORTANT`, `START`, and `THEN` before deciding whether to collect local signer examples or retrain.
- Keep pose cadence and low-FPS confirmation flags available for A/B tests, but treat model/data work as the next accuracy lever.
- If runtime testing continues, run the same sign list at the start of a fresh/cool session and after several minutes to separate model confusion from thermal FPS collapse.

## 2026-07-22 Local supplementary 236-class TCN candidate

A 236-class local supplementary TCN candidate was trained and export-gated from F:/ASL DATASET/local. It improved normal ASL Citizen test top1 to 0.6172 but only marginally improved low-FPS k8 top1 to 0.5290 vs current deployed 0.5271, while k4/top5 and confirmation precision were weaker. Confirmation on k8 chose theta_conf -1.2 with test precision-when-committed 0.686 and false commit 0.047. INT8 export passed and candidate assets live under the run's ndroid_candidate_assets/ folder. Treat this as a cautious A/B candidate, not a default replacement.

## 2026-07-22 Android low-FPS bottleneck architecture plan

Latest candidate-model device log shows the camera can still deliver more frames than the recognition
pipeline can consume: camera input is roughly 14-17 FPS, while processed recognition FPS often falls
to 3-4 FPS. This is not stale camera buffering and not TFLite inference. The analyzer drops/skips old
camera frames while the current frame is still being processed, which is the correct backpressure
behavior for real-time recognition.

Measured cause:

- MediaPipe hand + pose landmarking remains the dominant frame cost.
- Recognition inference is usually only a few milliseconds and is not the bottleneck.
- At 3-4 processed FPS, a normal short sign may produce only 2-4 usable landmark samples before
  confirmation. The current low-FPS confirmation mode can commit as early as frame 2, so visually
  similar early partial signs can win with high margin before the full motion is observed.
- The local supplementary candidate improved some signs (`KNOW`, `WANT`) but regressed or destabilized
  others on-device (`CUT` -> `WE`, `IMPORTANT` -> `FAMILY`/`TEACH`, `SELL` -> `PUT`). This matches its
  weaker offline confirmation precision and means it should not become the default without more A/B
  evidence.

Current revert point:

- Android assets were replaced with the local 236-class candidate for device A/B testing.
- The prior deployed asset backup is under
  `android/app/src/main/assets/_backup_before_local_pc_236_candidate_20260722-075734/`.
- The candidate source assets are under
  `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/runs/tcn_streaming_conversational_plus_local_pc_236_rtx3050_v30/android_candidate_assets/`.

Architecture plan for the bottleneck, in safe order:

1. **Lock the baseline and run measured A/B only.** Keep the current candidate state documented, but
   be ready to restore the pre-candidate assets if stricter confirmation does not improve device
   behavior.
2. **Strict low-FPS confirmation experiment.** Behind config only, test raising
   `low_fps_confirmation.min_commit_frame` from 2 to about 4 and requiring more stability. Expected:
   fewer early wrong commits, more delay/dropped signs. This diagnoses confirmation timing; it is not
   an FPS fix.
3. **MediaPipe delegate A/B.** Compare current GPU delegate against CPU/XNNPACK on the same phone and
   sign list. GPU is active now, but on low-end Android devices GPU delegate can lose to CPU because
   of synchronization and driver overhead.
4. **Analyzer resolution experiment.** Lower the analysis resolution while keeping preview usable.
   Measure hand/pose latency, processed FPS, and landmark quality. This is the first real FPS lever
   because it reduces the image cost before MediaPipe.
5. **Pose cadence sweep.** Keep the 258-feature contract intact; run hands every processed frame and
   pose every 2 or 3 processed frames with last-valid-pose hold. Measure FPS and recognition behavior
   for each mode.
6. **Only after runtime evidence, targeted data/model work.** If the same confusion groups remain at
   improved FPS, collect or curate targeted supplementary clips for `CUT/WE`, `IMPORTANT/FAMILY/TEACH`,
   `SELL/PUT`, and other observed clusters. Do not treat broad local retraining as automatically
   better.

Constraints for this plan:

- Do not migrate to React Native to solve this bottleneck.
- Do not replace the TCN or feature contract during the runtime bottleneck experiments.
- Do not drop hand or pose features from the 258-feature schema.
- Do not loosen thresholds blindly; every risky behavior change must be config-gated and compared
  against the same controlled sign list.

## 2026-07-22 CPU delegate A/B result

The CPU delegate A/B was measured on Xiaomi `M2101K7AG` after the strict low-FPS confirmation config.
Startup logs confirmed `mediapipe_delegate.mode=cpu` and `landmarkers on CPU delegate`.

Result:

- CPU improves raw MediaPipe speed on this phone. Processed FPS commonly reached about 6-8 FPS, with
  hand landmark time often around 65-90 ms and pose p95 often around 120-150 ms.
- The previous GPU strict-confirmation run was usually slower, often around 4-6 processed FPS with
  higher hand/pose p95 spikes.
- Recognition quality did not improve enough. `CUT` could still commit as `WE`; `IMPORTANT` still
  committed as `FAMILY`; `SELL` remained unstable and moved toward `TEACH2`/`PUT`; `KNOW` sometimes
  first committed as `HELLO` before later correct `KNOW` commits.

Interpretation:

CPU is a device-specific performance win, but not yet a recognition-quality win. The remaining errors
are mostly class confusion under low-FPS/short-evidence conditions, not simply inference latency. Keep
CPU/GPU as a measured runtime option, but do not assume CPU should become the default for all devices.

Next runtime lever:

Restore GPU for the next controlled experiment and test analyzer-resolution reduction. The goal is to
reduce MediaPipe input cost while preserving the landmark behavior that felt better in the earlier GPU
run. Compare against both GPU strict-confirmation and CPU strict-confirmation logs.

## 2026-07-22 Analyzer resolution A/B result - GPU 480x360

The GPU analyzer-resolution run was confirmed by logcat: `landmarker delegate mode=gpu`, `landmarkers on
GPU delegate`, and `camera_analysis target=480x360`.

Result:

- Lowering the analyzer target to 480x360 reduced image conversion/rotation cost sharply. Rotation
  dropped to about 3 ms from the earlier ~12-14 ms range.
- The main processed FPS did not improve enough because MediaPipe hand/pose remained dominant. The
  run stayed mostly around 5-6 processed FPS, with hand p95 still reaching about 280-300 ms and pose
  p95 often around 180-270 ms.
- Recognition stayed good for `CUT`, `WANT`, `KNOW`, `FAMILY`, `TEACH`, `PUT`, and `WE`, but the key
  confusion clusters remained: `IMPORTANT` -> `FAMILY`, and `SELL` -> `PUT`/`TEACH2`.

Interpretation:

Analyzer resolution reduction is useful for conversion cost, but it is not enough by itself because
MediaPipe landmark execution still dominates the wall time. The next runtime lever should be pose
cadence: keep hands fresh, keep the 258-feature contract intact, hold last valid pose, and test
`pose_every_n=3` against the current `pose_every_n=2`.

## 2026-07-22 - Android Low-FPS Runtime A/B: pose_every_n=3 Reverted

- Tested local supplementary 236-class candidate on Xiaomi M2101K7AG with GPU MediaPipe, camera_analysis=480x360, strict low-FPS confirmation, and pose_cadence_experiment pose_every_n=3.
- User observations from logcat run 24302: CUT good; IMPORTANT good but sometimes MORE; SELL still PUT; WANT degraded to MEET; KNOW degraded to SELL/SHOP; FAMILY, TEACH, PUT, WE good.
- Log confirmed processed FPS usually ~6-7 FPS with dips to ~3.9-5.0 FPS. This was only a modest gain over pose_every_n=2, while recognition stability got worse for WANT/KNOW and SELL remained unresolved.
- Decision: pose_every_n=3 is not a keeper for the current model/runtime profile. Reverted recognition_config.json to pose_every_n=2 while preserving GPU delegate, 480x360 analyzer resolution, strict low-FPS confirmation, hold_last_pose=true, and the 258-feature contract.
- Backup before revert: android/app/src/main/assets/_backup_before_revert_pose_every_2_20260722-095204/recognition_config.json
- Build verification after revert: ./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2 passed.
- Current best runtime test profile after revert: local 236-class candidate assets + GPU MediaPipe + camera_analysis=480x360 + pose_every_n=2 + strict low-FPS confirmation. Remaining recurring errors appear to be model/data confusion groups more than runtime confirmation: IMPORTANT/MORE/FAMILY, SELL/PUT/TEACH2/SHOP, WANT/MANY/MEET, KNOW/HELLO/SELL/SHOP.

## 2026-07-22 - Old Model A/B Prepared After Controlled Low-FPS Test

- Controlled test on Xiaomi M2101K7AG with local supplementary 236-class candidate + GPU + camera_analysis=480x360 + pose_every_n=2 showed: CUT good; IMPORTANT often FAMILY/INTRODUCE/delayed; SELL consistently PUT; WANT WAIT/WANT2/MANY; KNOW correct/delayed/HELLO; FAMILY, TEACH, PUT, WE good.
- Log confirmed runtime profile: GPU delegate, camera_analysis=480x360, pose_every=2, processed FPS mostly ~5-6 FPS with dips near ~3.6-4.0, always low_fps=true.
- Key interpretation: remaining failures are not mainly confirmation thresholds. SELL->PUT commits had high margins and true SELL was often absent from top-3; IMPORTANT appeared in FAMILY/MORE/IMPORTANT top-3; WANT and KNOW stayed in known confusion groups. This points to model/data class confusion under low-FPS streaming.
- Prepared a reversible old-model A/B APK: restored streaming.tflite, model_manifest.json, and vocab.json from android/app/src/main/assets/_backup_before_local_pc_236_candidate_20260722-075734 while preserving current runtime recognition_config.json profile.
- Backup before this A/B swap: android/app/src/main/assets/_backup_before_old_model_ab_20260722-100247/
- Build verification: ./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2 passed.
- Next test: install app-debug.apk and run the same controlled 3-attempt set (CUT, IMPORTANT, SELL, WANT, KNOW, FAMILY, TEACH, PUT, WE). Compare old deployed model against local supplementary candidate before deciding whether to keep candidate, revert model, or start targeted retraining for confusion groups.

## 2026-07-22 - Old Model A/B Result: Reject Old Model, Restore Local Candidate

- Old-model A/B log 30136 was tested with the same runtime profile: GPU MediaPipe, camera_analysis=480x360, pose_every_n=2, strict low-FPS confirmation, low_fps=true throughout, processed FPS mostly ~5-6 FPS with dips near ~4 FPS.
- User results for old model: CUT 3/3; IMPORTANT 2/3; SELL mostly delayed/DECIDE1; WANT 2/3; KNOW 0/3; FAMILY 2/3; TEACH 3/3; PUT 0/3; WE 0/3.
- Commit sequence confirmed the regression: PUT attempts committed INTRODUCE/IMPORTANT, WE attempts committed SELL/LIVE2/STRONG, KNOW committed SELL/DONTKNOW or delayed. Old model improved IMPORTANT compared with the local candidate but damaged previously stable classes.
- Decision: reject old model as current baseline. Restore the local supplementary 236-class candidate because it is better overall for controlled signs, especially PUT, WE, FAMILY, TEACH, CUT.
- Restored local candidate model/vocab/manifest from android/app/src/main/assets/_backup_before_old_model_ab_20260722-100247/ while preserving runtime config.
- Backup of rejected old-model A/B state before restore: android/app/src/main/assets/_backup_before_restore_local_candidate_20260722-101227/
- Build verification after restore: ./gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=2 passed.
- Next direction: stop broad runtime/model A/B for now. Remaining problem is targeted model/data confusion under low-FPS streaming: IMPORTANT/FAMILY/MORE/INTRODUCE, SELL/PUT/DECIDE1/SHOP/TEACH2, WANT/MANY/WAIT/MEET, KNOW/HELLO/SELL/DONTKNOW, plus possible WE/LIVE2/STRONG in old model only. Recommended next step is targeted confusion audit/retraining plan using ASL Citizen plus supplementary local data, not threshold tuning.

## 2026-07-22 - Targeted Confusion Audit Completed

- Ran targeted confusion audit for current restored local supplementary 236-class candidate: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_rtx3050_v30\best.keras
- Report artifacts written:
  - artifacts/targeted_confusion_audit_20260722/targeted_confusion_audit.md
  - artifacts/targeted_confusion_audit_20260722/targeted_confusion_audit.json
- Headline held-out test metrics: mean aggregation top1=0.617/top3=0.817/top5=0.868; last-frame top1=0.571/top3=0.790/top5=0.853; early4 top1=0.081; early6 top1=0.137.
- Interpretation: the phone's low-FPS early commits are consistent with offline weakness. The model is not reliable at very early frames; min_commit_frame=4 can be correct for easy signs but is too early for many signs if the wrong class has high confidence.
- Most problematic held-out last-frame classes in observed groups: KNOW top1=0.15, HELLO top1=0.30, SELL top1=0.27, WANT2 top1=0.36, PUT top1=0.45. Stable/current-good classes: WE top1=1.00, TEACH2 top1=0.91, MORE top1=1.00, FAMILY top1=0.75, IMPORTANT top1=0.67.
- Dataset count issue: many target classes have very small base train counts (e.g. SELL 23, KNOW 21, IMPORTANT 14, MANY 13, WAIT 12, WE 15, STRONG 15). FPS augmentation multiplies existing clips but does not add signer/style diversity.
- Next recommended model/data step: no more broad runtime threshold tuning. Prepare targeted retraining/eval experiment focused on weak confusion groups, with stronger per-class/early-frame eval gates before any Android deployment.

## 2026-07-22 - Targeted 236-Class Retrain v1 Verified

- User ran 08_TRAIN_TARGETED_236_CPU.ps1 successfully. Output run: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v1
- Training completed through epoch 24/40 with early stopping. Best val_pf_acc in log was ~0.4741 at epoch 16; final artifacts best.keras, final.keras, history.csv exist.
- Targeted audit written: artifacts/targeted_confusion_audit_20260722/targeted_v1/targeted_confusion_audit.md and .json
- Overall held-out test deltas vs baseline: mean top1 0.617 -> 0.613 (-0.005), last top1 0.571 -> 0.587 (+0.017), early4 top1 0.081 -> 0.077 (-0.004), early6 top1 0.137 -> 0.140 (+0.002).
- FPS-val stress deltas improved across views: mean top1 0.640 -> 0.663, last top1 0.588 -> 0.603, early4 top1 0.326 -> 0.339, early6 top1 0.430 -> 0.441.
- Major held-out last-frame improvements: KNOW 0.15 -> 0.54, HELLO 0.30 -> 0.50, SELL 0.27 -> 0.45, WANT2 0.36 -> 0.73, PUT 0.45 -> 0.55, TEACH2 0.91 -> 1.00.
- Regressions: WE 1.00 -> 0.83, WAIT 0.64 -> 0.36, MANY 0.73 -> 0.55, FAMILY 0.75 -> 0.67, SHOP1 0.60 -> 0.50, MEET top3 1.00 -> 0.89.
- Decision: targeted_v1 is promising but not deployable yet. It fixes several weak classes while moving errors into previously stable classes. Next step should be targeted_v2 with safer weights / guardrails before Android A/B.

## 2026-07-22 - Targeted 236-Class Retrain v2 Prepared

- Prepared v2 targeted retraining config and runner, but did not run full training in Codex because user will execute commands manually.
- New config: model/config/train_streaming_conversational_plus_local_pc_236_targeted_v2.yaml
- New runner: 09_TRAIN_TARGETED_236_V2_CPU.ps1
- v2 rationale: targeted_v1 improved KNOW/HELLO/SELL/WANT2/PUT but regressed WE/WAIT/MANY/FAMILY/SHOP1. v2 starts again from the current local-candidate baseline and uses softer weak-class weights plus guardrail weights.
- v2 weights: KNOW 2.5, HELLO 2.0, SELL 2.0, WANT2 1.6, PUT 1.6, WAIT 1.6, MANY 1.5, SHOP1 1.5, FAMILY 1.3, WE 1.3, IMPORTANT 1.3. TEACH2 and other stable classes remain 1.0.
- v2 output dir: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v2
- v2 audit dir after run: artifacts/targeted_confusion_audit_20260722/targeted_v2/
- Validation performed: config loads in project .venv and class weights resolve against the 236-class vocab.
- Deployment gate: do not export/deploy v2 unless it improves weak classes while avoiding v1 regressions, especially WE, WAIT, MANY, FAMILY, SHOP1.

## 2026-07-22 - Targeted 236-Class Retrain v2 Verified

- User ran 09_TRAIN_TARGETED_236_V2_CPU.ps1 successfully. Output run: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v2
- Training completed through epoch 25/40 with early stopping. Best val_pf_acc in log was ~0.4762 at epoch 17. Artifacts best.keras, final.keras, history.csv exist.
- Targeted audit written: artifacts/targeted_confusion_audit_20260722/targeted_v2/targeted_confusion_audit.md and .json
- Overall held-out test top1 baseline -> v1 -> v2: mean 0.617 -> 0.613 -> 0.623; last 0.571 -> 0.587 -> 0.583; early4 0.081 -> 0.077 -> 0.081; early6 0.137 -> 0.140 -> 0.139.
- FPS-val stress top1 baseline -> v1 -> v2: mean 0.640 -> 0.663 -> 0.659; last 0.588 -> 0.603 -> 0.598; early4 0.326 -> 0.339 -> 0.338; early6 0.430 -> 0.441 -> 0.435.
- Held-out last-frame class deltas baseline -> v1 -> v2: KNOW 0.15 -> 0.54 -> 0.54; SELL 0.27 -> 0.45 -> 0.45; PUT 0.45 -> 0.55 -> 0.55; WANT2 0.36 -> 0.73 -> 0.55; HELLO 0.30 -> 0.50 -> 0.30; WE 1.00 -> 0.83 -> 0.92; FAMILY 0.75 -> 0.67 -> 0.75; MANY 0.73 -> 0.55 -> 0.64; WAIT 0.64 -> 0.36 -> 0.36.
- Decision: v2 is safer than v1 for WE/FAMILY and has the best mean top1, but it is still not a clean deploy candidate. It preserves important improvements on KNOW/SELL/PUT while still regressing WAIT and some WANT2/HELLO gains compared with v1. Next step should be either v3 with more focused weights/guardrails or a temporary Android A/B only if we explicitly accept risk and keep rollback ready.

## 2026-07-22 - Targeted 236-Class Retrain v3 Prepared

- Prepared v3 targeted retraining config and runner for manual execution by the user.
- New config: model/config/train_streaming_conversational_plus_local_pc_236_targeted_v3.yaml
- New runner: 10_TRAIN_TARGETED_236_V3_CPU.ps1
- v3 rationale: v2 preserved KNOW/SELL/PUT gains better than baseline and recovered WE/FAMILY versus v1, but WAIT remained badly regressed and HELLO/WANT2 lost some v1 gains. v3 removes weights from WAIT/MANY/SHOP1 because weighting those classes in v1/v2 coincided with regressions, while keeping targeted pressure on KNOW/HELLO/SELL/WANT2/PUT plus light guardrails for FAMILY/WE.
- v3 weights: KNOW 2.5, HELLO 2.4, SELL 2.3, WANT2 1.9, PUT 1.6, FAMILY 1.3, WE 1.3. WAIT/MANY/SHOP1/TEACH2 remain 1.0.
- v3 output dir: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v3
- v3 audit dir after run: artifacts/targeted_confusion_audit_20260722/targeted_v3/
- Validation performed: config loads in project .venv and class weights resolve against the 236-class vocab.
- Deployment gate: compare v3 against baseline, v1, and v2. Do not export/deploy unless weak-class gains hold and WAIT/MANY/SHOP1/WE/FAMILY regressions are acceptable or improved.

## 2026-07-22 - Targeted 236-Class Retrain v3 Verified

- User ran 10_TRAIN_TARGETED_236_V3_CPU.ps1 successfully. Output run: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v3
- Training completed through epoch 20/40 with early stopping. Best val_pf_acc in log was ~0.4735 at epoch 12. Artifacts best.keras, final.keras, history.csv exist.
- Targeted audit written: artifacts/targeted_confusion_audit_20260722/targeted_v3/targeted_confusion_audit.md and .json
- Overall held-out top1 baseline -> v1 -> v2 -> v3: mean 0.617 -> 0.613 -> 0.623 -> 0.627; last 0.571 -> 0.587 -> 0.583 -> 0.587; early4 0.081 -> 0.077 -> 0.081 -> 0.083; early6 0.137 -> 0.140 -> 0.139 -> 0.139.
- FPS-val top1 baseline -> v1 -> v2 -> v3: mean 0.640 -> 0.663 -> 0.659 -> 0.658; last 0.588 -> 0.603 -> 0.598 -> 0.608; early4 0.326 -> 0.339 -> 0.338 -> 0.331; early6 0.430 -> 0.441 -> 0.435 -> 0.438.
- Major held-out last-frame changes baseline -> v3: KNOW 0.15 -> 0.54, SELL 0.27 -> 0.55, WANT2 0.36 -> 0.73, PUT 0.45 -> 0.55, HELLO 0.30 -> 0.40, FAMILY 0.75 -> 0.83, DECIDE1 0.79 -> 0.86, WE 1.00 -> 0.92.
- Serious regressions baseline -> v3: SHOP1 0.60 -> 0.20, INTRODUCE 0.67 -> 0.50, WAIT 0.64 -> 0.36, MANY 0.73 -> 0.64, LIVE2 0.75 -> 0.67.
- Decision: v3 is the best overall offline candidate so far and strongest for the observed Android pain points, but not clean enough to deploy as final. The biggest blocker is SHOP1 collapsing into SELL; next step should be v4 with a small SHOP1 guardrail and slightly lower SELL weight, or Android A/B only if SHOP1 is outside current controlled target words and rollback is kept ready.

## 2026-07-22 - Targeted 236-Class Retrain v4 Prepared

- Prepared v4 targeted retraining config and runner for manual execution by the user.
- New config: model/config/train_streaming_conversational_plus_local_pc_236_targeted_v4.yaml
- New runner: 11_TRAIN_TARGETED_236_V4_CPU.ps1
- v4 rationale: v3 is the strongest overall candidate so far but SHOP1 collapsed into SELL (SHOP1 last top1 0.60 baseline -> 0.20 v3). v4 is a minimal correction from v3: reduce SELL weight and add a small SHOP1 guardrail.
- v4 weights: KNOW 2.5, HELLO 2.4, SELL 2.0, WANT2 1.9, PUT 1.6, SHOP1 1.3, FAMILY 1.3, WE 1.3. WAIT/MANY/TEACH2 remain 1.0.
- v4 output dir: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v4
- v4 audit dir after run: artifacts/targeted_confusion_audit_20260722/targeted_v4/
- Validation performed: config loads in project .venv and class weights resolve against the 236-class vocab.
- Deployment gate: compare v4 against baseline and v1-v3. Key pass/fail checks: keep v3 gains on SELL/KNOW/WANT2/PUT, recover SHOP1 meaningfully, avoid further regressions on WE/FAMILY/WAIT/MANY/INTRODUCE.

## 2026-07-22 - Targeted 236-Class Retrain v4 Verified

- User ran 11_TRAIN_TARGETED_236_V4_CPU.ps1 successfully. Output run: F:\ASL DATASET\ASL CITIZEN\derived\apphear3\runs\tcn_streaming_conversational_plus_local_pc_236_targeted_v4
- Training completed through epoch 12/40 with early stopping. Best val_pf_acc in log was ~0.4758 at epoch 4. Artifacts best.keras, final.keras, history.csv exist.
- Targeted audit written: artifacts/targeted_confusion_audit_20260722/targeted_v4/targeted_confusion_audit.md and .json
- Overall held-out top1 baseline -> v1 -> v2 -> v3 -> v4: mean 0.617 -> 0.613 -> 0.623 -> 0.627 -> 0.621; last 0.571 -> 0.587 -> 0.583 -> 0.587 -> 0.584; early4 0.081 -> 0.077 -> 0.081 -> 0.083 -> 0.080; early6 0.137 -> 0.140 -> 0.139 -> 0.139 -> 0.137.
- FPS-val top1 baseline -> v1 -> v2 -> v3 -> v4: mean 0.640 -> 0.663 -> 0.659 -> 0.658 -> 0.656; last 0.588 -> 0.603 -> 0.598 -> 0.608 -> 0.602; early4 0.326 -> 0.339 -> 0.338 -> 0.331 -> 0.336; early6 0.430 -> 0.441 -> 0.435 -> 0.438 -> 0.438.
- Held-out last-frame key classes baseline -> v4: KNOW 0.15 -> 0.62, SELL 0.27 -> 0.55, PUT 0.45 -> 0.55, HELLO 0.30 -> 0.40, WE 1.00 -> 1.00, FAMILY 0.75 -> 0.83, INTRODUCE 0.67 -> 0.58, SHOP1 0.60 -> 0.40, WANT2 0.36 -> 0.55, MANY 0.73 -> 0.55, WAIT 0.64 -> 0.27.
- Decision: v4 is not a strict winner over v3. It improves KNOW/WE/INTRODUCE and partially recovers SHOP1, but hurts WAIT/MANY/WANT2 and has lower overall mean/last top1 than v3. Continuing weight tweaks risks overfitting the tiny target counts. Recommended stop point: do not deploy v4 as final. If doing Android A/B, v3 or v4 can be tested behind rollback, but a full 236-class regression audit should be added before any final model replacement.

## 2026-07-22 - Full 236-Class Regression Audit Prepared

- Added a full 236-class regression audit before any model deployment.
- New module: eval/full_regression.py
- New runner: 12_FULL_236_REGRESSION_AUDIT.ps1
- Purpose: compare baseline and v1-v4 across every class, not only targeted confusion groups. Reports overall metrics by view (mean/last/early4/early6), focus-word table, and worst per-class regressions/improvements against the baseline.
- Output after run: artifacts/targeted_confusion_audit_20260722/full_236_regression/full_regression_audit.md and .json
- Validation performed: `python -m eval.full_regression --help` succeeds with project .venv.
- Deployment gate: do not export/deploy v3/v4 until full_236_regression audit is reviewed, especially worst regressions across all 236 classes.

## 2026-07-24 - Recognition Architecture Research Decision

Research/planning only. No code, feature schema, model, dataset, Android asset, or runtime config changed.

### Verified project findings

- Production remains `CameraX -> MediaPipe Hands + Pose (IMAGE) -> 258 features -> signing gate -> [1,96,258] TCN -> confirmation -> sentence/UI`.
- The 258 values are 126 hand xyz coordinates plus 132 pose xyz/visibility values. They omit RGB appearance, face/non-manual cues, hand confidence/missing masks, timestamps, explicit velocity, acceleration, angles, contact, and relational features. Missing landmarks become zero.
- Current local 236-class held-out top-1 is 0.617 mean / 0.571 last. Targeted v3 reached 0.627 / 0.587, but early4/early6 remained 0.083/0.139 and serious per-class regressions remained.
- Several weak classes have only 12-23 original train clips. FPS/prefix augmentation adds transformed examples, not signer/style diversity.
- Same-protocol ASL Citizen evidence: AppHear 169K TCN 31.4%, published landmark ST-GCN 59.5%, RGB I3D 63.1%. The TCN is underpowered; the RGB margin also shows that landmarks discard useful visual evidence.

### External evidence retained

- How2Sign documents manual/non-manual channels and continuous-sign coarticulation: https://openaccess.thecvf.com/content/CVPR2021/html/Duarte_How2Sign_A_Large-Scale_Multimodal_Dataset_for_Continuous_American_Sign_Language_CVPR_2021_paper.html
- ST-GCN supplies an anatomical spatial-temporal prior: https://ojs.aaai.org/index.php/aaai/article/view/12328
- Pose-guided RGB and RGB+keypoint research supports multi-stream fusion: https://openaccess.thecvf.com/content/WACV2021/html/Hosain_Hand_Pose_Guided_3D_Pooling_for_Word-Level_Sign_Language_Recognition_WACV_2021_paper.html and https://openreview.net/forum?id=hSxK-4KGLbI
- MoViNet is a credible causal mobile RGB backbone with bounded streaming memory: https://research.google/pubs/movinets-mobile-video-networks-for-efficient-video-recognition/
- CTC supports timing-free monotonic video-to-gloss alignment; translation needs a separate language decoder because ASL and English grammar differ: https://openaccess.thecvf.com/content_CVPR_2020/html/Camgoz_Sign_Language_Transformers_Joint_End-to-End_Sign_Language_Recognition_and_Translation_CVPR_2020_paper.html

### Selected target architecture

Choose a **major hybrid redesign**:

`timestamped CameraX frames -> MediaPipe VIDEO/LIVE_STREAM tracking and hand/body/face ROIs -> structured landmark/motion + RGB hand appearance + sparse non-manual streams -> region-aware ST-GCN + small causal temporal fusion encoder with streaming cache -> learned idle/onset/active/release head + isolated gloss head initially -> calibrated reject/unknown policy -> optional constrained LM -> UI`

- Keep CameraX, MediaPipe initially, schema/version enforcement, signer-disjoint evaluation, calibration discipline, rollback tooling, and raw-data preservation.
- Replace the flat 258-only representation, fixed 96-frame timing assumption, tiny TCN, and reliance on hand-authored confirmation to compensate for weak evidence.
- Add real timestamps, confidence/missing masks, hand-local and body-relative coordinates, bones, angles, velocity/acceleration, RGB hand crops, and vocabulary-gated mouth/eyebrow/head/torso cues.
- Use a bounded variable-duration causal cache, prefix/partial-sign training, and a jointly learned boundary head.
- Keep MediaPipe as tracker/ROI generator, not the sole input. Switch IMAGE to VIDEO/LIVE_STREAM only after measured throughput, output-drift, retraining, and accuracy gates. Do not require depth.

### Scope and data decision

1. First production target: accurate isolated signs for a controlled vocabulary.
2. Design the encoder/data contract for a later CTC gloss head.
3. Start continuous recognition only with natural sentence-level signing and gloss/boundary labels.
4. Never describe concatenated isolated glosses as full ASL-to-English translation.

- Current data is sufficient for experiments, not reliable 236-sign consumer use.
- Pilot: at least 30 signers over about 50 signs. Production target: 50 signers minimum, preferably 75-100, with 100-300 valid clips/sign and 2-5 repetitions/signer.
- Cover handedness, age, body size, signing style/speed, skin tone, clothing, distance, angle, lighting, background, camera/device, hard negatives, idle motion, and partial signs.
- Preserve raw video, timestamps, signer/device metadata, gloss variants, boundaries, landmarks, crops, and extraction version. Split by signer before preprocessing and deduplicate identities.
- Public ASL data is for provenance-checked pretraining/domain adaptation; augmentation and synthetic data cannot replace real signer diversity.

### Android and real-user gates

- Mid-range target: 12-20 processed FPS, 8-20 MB INT8 recognizer, p95 processing <80 ms/frame, p95 commit latency <750 ms after sufficient evidence. CPU/XNNPACK baseline; delegates are optional/device-gated.
- Isolated 236-sign release: top-1 >=0.85 (0.90 preferred), macro-F1 >=0.85, worst-decile F1 >=0.75, accepted precision >=0.95 at >=0.80 coverage, ECE <=0.05, 8-FPS drop <=5 points, boundary F1 >=0.85, false commits <=1/30 minutes, and <20% throughput decay over 20 thermal minutes.
- Continuous evaluation adds gloss WER, insertion/deletion/substitution, boundary IoU, sentence metrics, and fluent-ASL-user evaluation.

### Ordered experiments and go/no-go gates

1. Reproduce/freeze the baseline; audit labels, variants, signers, raw video, and rights.
2. Run the existing ST-GCN experiment. Go for >=5-point native and >=3-point low-FPS top-1 gains without severe regressions.
3. Identical-split landmark graph vs RGB hand crops vs hybrid. Continue hybrid for >=5 points or material resolution of priority confusion groups.
4. IMAGE vs VIDEO/LIVE_STREAM: switch only for >=1.5x throughput, <1-point retrained accuracy loss, and acceptable landmark/missingness drift.
5. Collect the >=30-signer pilot; continue for >=0.85 held-out top-1 and improving signer learning curves.
6. Quantized hybrid Android must pass parity, FPS, latency, calibration, false-positive, memory, and thermal gates before expanding 50 -> 100 -> 236 signs.
7. Add CTC only after natural continuous data exists.

### Open experimental unknowns

- VIDEO/LIVE_STREAM speed and landmark dialect on the reference Xiaomi device.
- Marginal accuracy/cost of RGB hands, upper-body RGB, and sparse facial cues.
- Required crop resolution/FPS and quantization-compatible graph/fusion operators.
- Signer/sample learning curves for the exact 236-sign vocabulary.
- Sustainable low/mid-range battery, thermal, memory, and latency behavior.
- Ability to obtain enough correctly annotated natural continuous ASL.

Strategy verdict: A/258 remains a baseline (estimated 65-75% ceiling); B/hybrid is selected (estimated 80-90% for a well-collected isolated 100-236-sign vocabulary); C/raw continuous is a later high-end/cloud research path. These are engineering forecasts, not accuracy claims.

Shortest credible path: `ST-GCN benchmark -> hand-crop fusion ablation -> 30-signer pilot -> quantized hybrid Android -> vocabulary expansion`.
