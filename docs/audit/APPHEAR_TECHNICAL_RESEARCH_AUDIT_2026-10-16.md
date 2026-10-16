# AppHear — Technical and Research Audit Report

> **Correction (2026-10-16, later the same day):** the S2 mechanism in §1, §8.1–8.3 and R1 is
> superseded by [S2_HISTORY_DEPENDENCE_VERIFICATION_2026-10-16.md](S2_HISTORY_DEPENDENCE_VERIFICATION_2026-10-16.md).
> The missed-sign effect is reproduced, but history *length* is rejected as the primary cause.
> The supported mechanism is that S2 never learned to leave POST, plus phantom hand proposals at
> rest. The recommended retrain must teach sign→sign and POST-exit transitions, not just use
> longer sequences.

Date: 2026-10-16 (Asia/Manila). Auditor: Claude (independent onboarding audit).
Scope: whole repository and its local worktrees, the research artifacts on `F:`, and the
Sign-Speak harness in `F:/ASL DATASET/AppHear-External-Benchmarks`. The audit made no change to
any branch, worktree, model, dataset, app install, or artifact. New work consists only of this
report and four read-only probe scripts in `docs/audit/probes/`. Their outputs are reproduced
here and the commands are in Appendix A.

Evidence labels used throughout:

- **CONFIRMED**: directly supported by inspected code, data or a reproduced computation.
- **LIKELY**: strong explanation supported by several independent findings, but not proven.
- **HYPOTHESIS**: plausible, needs a test.
- **UNKNOWN**: the available evidence cannot answer it.

Code references point to the newest commit, `codex/recognition-v3-stage2@4503b55`. Its
read-only checkout is `C:/Users/Gigabyte/.codex/worktrees/recognition-v3-stage2/5. Apphear3`.
This audit worktree is on `main@1e215ae`, which does not contain most of the files cited.

---

## 1. Executive summary and overall assessment

**What AppHear is today.** AppHear is a native Kotlin/CameraX Android app with five integrated
features:

- WORD: isolated-sign recognition of 236 glosses, with automatic sign segmentation.
- FINGERSPELL: A–Z recognition of letters the signer holds, one at a time.
- Context Assist: conversational phrase suggestions shown alongside recognition.
- Hear/TTS: speech in and spoken output.
- Text-to-ASL: playback of avatar animations for typed text.

The most complete integrated version is the canonical debug build at `4c99ac24`. The six later
V3 commits (`5d73b41`…`4503b55`) add only default-off experiments, diagnostics and evidence.
Engineering discipline is unusually strong. It includes bit-exact train/serve parity checks,
hash-pinned assets, signer-disjoint splits, a sealed TEST set and explicit claim limits.
Recognition reliability is weak. The verified evidence supports this sentence: *WORD can work for
a well-executed sign once the signer has lowered their hands and waited for READY. It fails to
start, or merges, most consecutive signs. When it fires, it misclassifies roughly half of unseen
signers' signs. It also produces words from ordinary movement.*

**Three compounding limits (in causal order for the user-visible "hands down and wait" symptom):**

1. **The S2 segmenter misses most sign onsets under live conditions.** A key finding of this
   audit:
   - **CONFIRMED (saved inputs):** across both human-reviewed phone captures, 10 of 12 reviewed
     sign intervals produce zero S2 ACTIVE observations with the live rolling 61-observation
     history. All 12 produce ACTIVE when the history starts fresh 4 observations before the
     reviewed onset. The inputs are the exact Android-normalized features (§8.3).
   - **CONFIRMED:** the S2-R2 training set has a length confound. Sign sequences have a median
     length of 14–16 observations, and only 14 of 265 are ≥61 observations long. No-sign
     sequences have a median of 73, and 22 of 37 are ≥61.
   - **LIKELY:** S2 learned a shortcut tied to history length and padding, rather than robust
     motion semantics. This is the dominant reason the second sign is not detected. The 400 ms
     re-arm timer is not.
2. **The WORD classifier's generalization ceiling (CONFIRMED).** Governed signer-disjoint DEV
   Top-1 is 50.25% dense and 39.95% at phone cadence, over 236 closed-set classes. ASL Citizen
   is effectively exhausted for this vocabulary: 3,558 TRAIN clips from 35 signers, about 15
   clips per class (§9.1). Even perfect segmentation leaves roughly 1 in 2 words wrong.
3. **Perception loses hand evidence exactly when the hands move.**
   - **LIKELY:** given an accepted hand in the previous observation, acceptance drops from 95.8%
     for near-static ROIs to 50% at moderate speed and about 0% at higher speed.
   - **CONFIRMED:** the front camera runs a fixed 15 fps auto-exposure range, and measured
     exposure is 50 ms (p50).
   - **LIKELY (partial):** hand crops are axis-aligned, which suits the MediaPipe landmark model
     poorly for horizontal hands. TABLE had 0 of 48 hand-slot instances accepted live.

**Assessment of the V3 plan (Stage 1 perception → Stage 2 segmentation → Stage 3 accuracy).**
The ordering is reasonable, but the content of each stage needs to change:

- Stage 1 optimized compute scheduling, while the bigger perception problem is evidence quality
  during motion.
- Stage 2 has been searching lifecycle timers and history resets, while the evidence points to
  how S2 was trained.
- Stage 3 cannot be "later polish". The recognizer ceiling bounds everything.
- Perception changes invalidate all three downstream models (S2, WORD, FINGERSPELL). Perception
  decisions should therefore be batched and made before any expensive retraining (§12, §14).

**Most important next actions (details in §13):**

- R1: confirm and fix the S2 length/context shortcut by retraining S2 offline on length-balanced,
  stitched long sequences. Do not deploy timer changes.
- R2: add abstention (confidence rejection) for WORD events, calibrated offline.
- R3: build a phone-domain replay benchmark with qualified signers, recorded at full frame rate.
  This lets most future experiments run offline.
- R4/R5: make the camera-exposure and perception decisions once, then re-extract features and
  retrain.
- Longer term, scale both WORD and FINGERSPELL data with external, signer-diverse corpora.
  The team's own attribution already found signer diversity to be the strongest correlate of
  generalization.

---

## 2. Current verified codebase and integrated version

### 2.1 Repository state (CONFIRMED, `git log --all`, `git worktree list`, `git status`)

History is linear: 44 commits from `67afa5f` (2026-07-25) to `4503b55` (2026-10-16).

| Ref | Commit, date | What it is |
|---|---|---|
| `main` / `origin/main` | `1e215ae`, Aug 12 | **Stale.** Two months behind; contains none of the current app (TEAM_HANDOFF.md says the same). |
| `checkpoint` | `7dd4fa0`, Aug 16 | RU-D10 recognition stabilization (old MediaPipe path). |
| Protected recognition baseline | `76d93ce`, Sep 26 | First real-app S2-R2 + Candidate01 integration (tag `apphear-s2-r2-integration-complete-2026-09-26`). |
| `dev/continuous-transition-diagnostics` | `befa94a`/`f5a6cb4`, Sep 28 | Debug-only transition A/B observer. It is an ancestor of the canonical app. **Diagnostics only, not a fix.** |
| `feature/conversation-phrase-assist-mvp` | `75f5959`, Oct 1 | Side branch; Context Assist was later migrated onto the Text-to-ASL baseline (`7eb854e`). |
| Integrated WORD+FS+Context baseline | `34f24ab`, Oct 9 | Tag `apphear-word-fingerspell-context-assist-2026-10-09`. |
| Original Character batch | `5cf2807`, Oct 9 | 273-entry avatar catalog behind a flag. |
| **Canonical integrated** | **`4c99ac2`**, Oct 9 | `5cf2807` plus team handoff docs and research imports (`042dc8b`, 1.46 M inserted lines). Same app code as `5cf2807`. |
| `codex/recognition-v3-stage1` | `5d73b41` → `e196a8d`, Oct 15 | Default-off concurrent hand refinement, plus partial device evaluation. |
| `codex/recognition-v3-stage2` | `1422cad` → `6dbb2d3` → `1727796` → **`4503b55`**, Oct 15–16 | Offline S2 audit, rejected history-reset probe, compact capture profile, Oct 15 device capture, human-review analysis. **Newest work. No default runtime change.** |

Worktrees:

- Seven worktrees are clean.
- The original checkout `F:/ASL DATASET/5. Apphear3` is on `cc1f394` with **181 uncommitted
  entries**. TEAM_HANDOFF.md states these "stale Android edits were NOT merged". They are a
  preservation hazard, not newer work.
- `fingerspell-oct04-integration` is a detached HEAD with 14 uncommitted entries. They are
  superseded by the committed fingerspelling work.
- No newer work exists outside `codex/recognition-v3-stage2`. The remote branch for Stage 1/2
  does not exist; that work is local only. **UNKNOWN:** whether PR #1 (team handoff) has merged;
  GitHub was not queried.

### 2.2 What is integrated, experimental and disabled (CONFIRMED, `android/app/build.gradle.kts`)

- **Debug "integrated preset"** (`tools/android/build_working_baseline.ps1`) enables these on top
  of WORD:
  - FINGERSPELL with continuous held-letter mode
  - recognition coordination
  - Context Assist (fake or Gemini provider)
  - rear camera
  - Original words
- **Release** hard-codes all of those false. A release build is WORD-only, plus Hear/TTS and
  Text-to-ASL basics.
- **Default-off V3 flags:** `recognitionV3ParallelHands` and `recognitionV3Profile`. The release
  build forces both false.
- **Dead code:** the legacy MediaPipe/258 path (`FrameAnalyzer`, `IndependentClockFrameAnalyzer`,
  `RecognitionPipeline`, `SigningDetector`, `Phase1ShadowRecognizer`, RU-D1 diagnostics) is still
  compiled. It is unreachable in practice, because `start()` always loads `PhoneProductionSession`
  and shows an error, rather than falling back, if that fails. Eleven `_backup_*` asset folders and
  the old MediaPipe/phase-1 shadow assets still ship in `src/main/assets`.

---

## 3. Recognition architecture and data flow (as implemented)

```
CameraX ImageAnalysis 480x360 target → actual 640x480, RGBA, KEEP_ONLY_LATEST
  front: AE fixed 15–15 fps (RecognitionActivity.kt:671); rear: 30–30 if advertised
  └─ single camera executor thread ───────────────────────────────────────────────
     Candidate01FrameAnalyzer.analyze()          (synchronized; whole pipeline inline)
       native preprocess (rotation → upright, unmirrored) ............ ~2.6 ms p50
       DWPose-t ONNX Runtime, FP32, 2 intra threads, 256x192 .......... ~81–107 ms live p50
       hand ROI per anatomical slot: DWPose hand kps (support ≥ 0.10, ≥5 pts),
         axis-aligned square, side = 1.8 × 5–95% extent (PerceptionVNextMath.kt:100–133)
       MediaPipe hand_landmarks_detector.tflite FP32, XNNPACK 2 threads, 224×224
         accepted iff presence ≥ 0.5 AND ≥ 18/21 in-crop joints (PerceptionVNextRunners.kt:156)
         serial L then R (~31 ms each replay; ~50 ms each live); V3 flag: concurrent
       body: COCO-WB 5–12 (shoulders, elbows, wrists, hips); bodyAvailable = ≥ 6 valid
       → PhoneRawObservation (raw-v1)
       ownsObservation seam → exactly one owner per observation
       ├─ WORD: PhoneProductionSession.consume()
       │    378 segmentation features (absolute image-normalized coords, raw per-step deltas, dt)
       │    S2-R2 causal TCN, FP32, re-runs a rolling 61-observation prefix each step (~7 ms)
       │    PhoneCausalEventProducer (CONFIG_01): IDLE→ACTIVE_CANDIDATE→(PRE_GAP)→POST_CANDIDATE
       │       min ACTIVE 133 ms; POST must persist 267 ms; ACTIVE in POST cancels (merge);
       │       commit → EVENT_EMITTED_WAIT_REARM; IDLE after 400 ms stable PRE/POST;
       │       ACTIVE during WAIT resets re-arm and can never open a candidate
       │    ring buffer → materializer (±250 ms outward-bracketed genuine observations)
       │    Recognition V2 features [96,350]+mask (body-frame from shoulders/hips)
       │    ordinary V2 TCN 4×64, 236-way softmax, FP32
       │    SentenceBuilder.add(top-1)  ← always; no confidence gate; adjacent-duplicate dropped
       └─ FINGERSPELL: ContinuousFingerspell (one worker thread, generation-guarded)
            Adapter.v1 [T,405] → V2.1 epoch034 masked TCN → 28 logits
            exact singleton CTC (blank penalty 0.5) on a ≤4 s window every 500 ms
            HeldLetterPolicy: 3 equal decodes over ≥1 s → append; same-letter repeat needs
            ~800 ms / ≥3 missing observations (hand lowering)
UI (main thread): CURRENT SIGN / RECOGNIZED / sentence; READY = decoder IDLE
Context Assist: ConversationPhraseAssist (hearing turns → provider phrase suggestions; shadow /
  advisory only; never edits recognized text) + RecognitionCoordinationBridge (6 English
  full-match rules may route a fresh turn to FINGERSPELL)
Hear: Android speech input; TTS: Android TextToSpeech, optional ElevenLabs
Text-to-ASL: GLB avatar catalogs (Original 273 / New 122 entries) with alphabet fallback
```

All WORD stages run synchronously on the camera thread. A frame is only accepted after the
previous frame's full pipeline, including the classifier on commit frames, has finished. Under
KEEP_ONLY_LATEST with a 15 fps sensor, observation spacing is quantized to multiples of
66.7 ms. The p50/p95 spacing of 200/267 ms that was observed is exactly 3 or 4 sensor frames.

---

## 4. Development and experimental history

### 4.1 Phases (reconstructed from git, `context/progress-tracker.md` and dated reports)

1. **AppHear v2 lessons → AppHear 3 design (July).** v2 hit three walls:
   - a 3.7 s decision window
   - cross-signer collapse
   - a leaky confirmation policy

   The CNN-LSTM era belongs to AppHear v2 (`../AppHear`). That project is off-limits under
   AGENTS.md and was **not inspected**. AppHear 3 started with MediaPipe hand+pose → normalized
   258 features → streaming TCN on ASL Citizen. Results:
   - Reducing the vocabulary from 2,731 to 250 classes doubled offline Top-1 (0.31 → 0.626).
   - On the phone it failed. The team verified a roughly 12× frame-rate mismatch: about 30 fps in
     training versus about 2.5 fps on device (`context/recognition-accuracy.md`).
   - July 18–22 also included A/B work on low FPS, GPU/CPU delegates, resolution and pose
     cadence, plus a React Native prototype track.
2. **Recognition-upgrade research E1–E6, C0, RU-D (late July – mid August).** Outcomes:
   - RGB and RGB+landmark fusion: no-go.
   - MediaPipe as the sole hand ROI provider: no-go. Hand-instance recall was 66.3% on a
     150-frame gold set (`E2E_ALL_HAND_GOLD_RESULT.md`).
   - Detector screening, masked-TCN landmark temporal models, reliable-core and specialist
     routing, open-set rejection on the old v3.0 model: mostly no-go or partial.
   - Small targeted Sem-Lex and PopSign supplements (RU-D5).
   - RU-D10 stabilization checkpoint `7dd4fa0`.
3. **Perception vNext → Candidate01 (late August – September 13).** DWPose-t whole-body ONNX
   supplies body points and hand proposals; the MediaPipe hand-landmark model refines crops.
   Results:
   - Exact Android parity.
   - About 5.6 observations/s, a model-runtime failure against the 15 FPS floor.
   - The team froze it anyway in order to measure recognition utility.
4. **Recognition utility, 236 classes (September 13–14).**
   - Recognition-v1 TCN: DEV 41.3% / 34.9% (dense / sparse).
   - Attribution: mixed generalization failure; signer diversity is the best correlate.
   - Hierarchical balanced sampling: harmful.
   - **Representation V2 `[96,350]`: 50.25% / 39.95%, the current recognizer.**
   - Signer/cadence-invariant contrastive objective: not supported.
5. **Phase 4A (September 14–15).**
   - Android V2 parity passes.
   - On 10 live attempts, oracle sign boundaries raised Top-1 from 2/10 to 7/10. This made
     automatic segmentation mandatory.
6. **Phases 5–8: learned segmentation (September 15–20).**
   - Human temporal labels on 120 clips.
   - First causal S2 TCN: DEV containment 95.7%, but phone transfer failed because of the
     cadence domain.
   - Phase 7 cadence-aligned S2 retraining.
   - Phase 8A: no streaming decoder configuration passed; cadence-safe materializer passed.
   - Terminal-evidence audit, then the S2-R2 data/objective correction.
7. **S2-R2 and real-app integration (September 21–26).**
   - Exact phone S2 parity.
   - S2-R2 trained once on 302 FIT rows; representative-phone validation 6/6 acquisitions.
   - Normal-app smoke test: HELLO→HOME→TABLE→HELLO, 4/4, with READY waits. Two non-sign words
     (HOSPITAL1, STAND2) also appeared.
   - Protected baseline `76d93ce`.
8. **Continuous-transition diagnostics (September 27–28).**
   - Debug A/B observer (`befa94a`).
   - The September 27 A/B capture (`session_20260927T162103Z`) was completed and human-reviewed.
     The Stage 1 handoff missed it (§11).
9. **Context Assist (September 28 – October 5).**
   - Sidecar phrase assist, with OpenAI then Gemini Flash-Lite in shadow mode.
   - Stage 3 physical pilot: 5 phrases, 7 of 11 words correct, all 4 errors absent from Top-5,
     plus insertions.
   - Advisory UI on the Text-to-ASL baseline.
10. **FINGERSPELL A–Z (October 1–9).**
    - FSboard selection and compatibility.
    - B1–B4: cadence-aware training fixed catastrophic sparse deletions; canonicalization and
      width did not help.
    - Visual residual path: no-go.
    - Beam decoding helped.
    - 4K-sequence training improved broadly.
    - V2 and then V2.1 epoch034 with a letters auxiliary objective.
    - Android parity; single-letter and then automatic held-letter UI; coordination; front/rear
      camera.
    - Baseline `34f24ab`.
11. **Sign-Speak harness (October 10, external folder).** Offline harness only; no live request
    was ever made.
12. **Recognition V3 (October 15–16).**
    - Stage 1: concurrent hands. Real two-hand compute saving, mixed live results.
    - Stage 2: offline audit; the history-reset probe was rejected; compact capture.
    - The October 15 nonexpert capture: 757 observations, 4 events, 1 correct HELLO.

### 4.2 Why the architecture changed

| Change | Driving evidence |
|---|---|
| MediaPipe 258 → Candidate01 (DWPose-t + MP refiner) | MediaPipe hand recall of 66% was judged insufficient |
| Dense windows → cadence-aware sparse views | ~12× fps train/serve mismatch measured on device |
| Recognition v1 → v2 | +9 / +5 points DEV dense / sparse |
| Manual Start/Done → automatic S2 events | 2/10 → 7/10 with oracle boundaries |
| PRE-only → PRE_OR_POST re-arm | Phone lifecycle Stage-A attribution |
| FS phrase decoding → singleton held-letter | Supervisor request; sequence model output unstable for held poses |

### 4.3 What succeeded, failed, was abandoned, or remains useful

| Outcome | Items |
|---|---|
| **Succeeded, kept** | Candidate01 parity/native path; representation V2; cadence-aware training (S2, FS); materializer; S2-R2 integration; FS 4K/V2.1; exclusive owner seam; parity/hash governance; device capture/review tooling |
| **Failed, closed** | RGB fusion (E3), MediaPipe as ROI source, balanced sampling, invariant objective, Episode-V2 decoder, outer-window FS oracle, generic visual FS fusion, S2 history-reset-after-re-arm |
| **Abandoned / dormant** | React Native/iOS prototype; old v3.0 streaming model; open-set rejection (tested only on the old model); specialist routing |
| **Implemented, never validated on Android as an improvement** | Stage 1 concurrency (mixed); compact capture (engineering-only); Gemini/OpenAI phrase providers (shadow); Sign-Speak harness |
| **Demonstrated real-world improvement** | Oracle boundaries (offline replay of live data); S2-R2 vs Phase-7 ACTIVE acquisition on the representative signer (6/6 vs 5/6, containment 6/6 vs 1/6); FS V2.1 vs 4K on governed DEV |

---

## 5. Confirmed successes and working functionality

All of the following are **CONFIRMED** from code and recorded evidence.

- **Train/serve parity is solved where it was tested.**
  - Raw→378 features and normalization: max error 0.
  - S2 TFLite versus Android: max probability error 4.8e-7, zero argmax mismatches over 757 and
    1,364 observations.
  - Recognition V2 and FS Adapter/decoder parity fixtures pass.
  - Remaining failures are not serialization bugs.
- **The end-to-end WORD path works when its preconditions are met.** HELLO was classified at
  p = 0.992 (September 27) and p = 0.993 (October 15). The September 23 smoke test committed 4/4
  intended signs with READY waits.
- **The materializer works** once an event exists: DEV containment 88% and no severe cuts.
- **Exclusive WORD/FINGERSPELL ownership and generation guards** pass device tests.
- **Context Assist is architecturally safe.** It is shadow/advisory, never rewrites recognized
  text, and never fuses scores.
- **Governance** is sound: signer-disjoint DEV, sealed TEST never opened, FIT-only normalization,
  one-run policies.
- **Text-to-ASL playback, Hear/TTS, camera switching and the UI shell** have device evidence.
  Their linguistic correctness has not been reviewed.

---

## 6. Consolidated problems and unresolved issues

The severity scale is S1 (blocks the core product) to S4 (hygiene).

| # | Problem | Subsystem / type | Evidence | Status | Tried | Sev | Next |
|---|---|---|---|---|---|---|---|
| P1 | S2 does not acquire ACTIVE under the live rolling history | S2 model / **ML, data** | §8.3 probe: rolling 2/12 vs fresh 12/12 signs with ACTIVE; length confound in training data | CONFIRMED (effect), LIKELY (shortcut) | History reset after re-arm (rejected: events 10→20) | S1 | R1 |
| P2 | Lifecycle dead time and merge/drop of adjacent signs | Decoder / **architecture** | Code (`PhoneCausalCore.kt:273–281, 387, 437`); measured end-of-ACTIVE→commit 467–734 ms, commit→IDLE 401–534 ms in 13/14 events | CONFIRMED | Re-arm policy PRE→PRE_OR_POST | S1 (after P1) | R6 |
| P3 | Non-sign movement commits words; no abstention | S2 + classifier / **ML, product** | 4 fully contained non-sign events (Sep 27), 1 (Oct 15), HOSPITAL1/STAND2/open-hand HELLO (Sep 23); `PhoneProductionSession.kt:66` adds every top-1 | CONFIRMED | None at the current model | S1 | R2 |
| P4 | Recognizer generalization ceiling | WORD classifier / **data** | DEV 50.25 / 39.95% Top-1; TRAIN 86.9%; ~15 clips/class; ASL Citizen exhausted (§9.1) | CONFIRMED | Sampling, invariant loss, representation V2 (only V2 helped) | S1 | L1 |
| P5 | Hand evidence lost during motion | Perception / **CV, camera** | §7.3: 95.8%→50%→~0% acceptance with ROI speed; front exposure p50 50 ms | Effect LIKELY; blur cause HYPOTHESIS | — | S1 | R4 |
| P6 | Axis-aligned hand crops fail horizontal hands | Perception / **CV** | TABLE 0/48 hand slots accepted live; rotation probe 0→11/27 (hands-up) | LIKELY (partial) | — | S2 | R5 |
| P7 | 4–5 observations/s; live inference 2.5× slower than replay | Runtime / **performance** | DWPose 34.8 ms replay vs 81–107 ms live; FP32 ORT | CONFIRMED (numbers), UNKNOWN (cause) | Stage 1 concurrency (mixed) | S2 | R5 |
| P8 | FS letter accuracy; held letters decoded by a phrase-trained model | FS / **ML, data** | Letter recall 63.2%, phone no-SPACE CER 40.2%, 6/512 exact | CONFIRMED (metrics), LIKELY (mismatch) | B1–B4, visual, decoder, 4K, V2/V2.1 | S2 | L2 |
| P9 | Adjacent identical glosses suppressed | SentenceBuilder / **logic** | `SentenceBuilder.kt:16` | CONFIRMED | — | S3 | R7 |
| P10 | Evaluation cannot resolve consecutive-sign behaviour | Methodology | Oct 15: HOME×2, second HELLO and hold labels uncertain; nonexpert signer | CONFIRMED | Compact protocol | S1 (for progress) | R3 |
| P11 | Vocabulary lacks core conversational signs (no I/ME/MY/NAME/THANK-YOU) | Product scope | `phase4a_gate2_recognizer_parity/manifest.json` | CONFIRMED | — | S3 | L1 |
| P12 | Raw gloss IDs shown to users (`WASH2`, `HOSPITAL1`) | UI | No suffix stripping in the main sources | CONFIRMED | — | S4 | quick fix |
| P13 | Any analyzer exception stops recognition until the Activity restarts | Robustness | `Candidate01FrameAnalyzer.kt:182` | CONFIRMED | — | S3 | harden after R1 |
| P14 | Python suite not self-contained | Reproducibility | Clean export of `4503b55`: 852 passed, 125 failed, 38 errors; ~145 are `FileNotFoundError` on private artifacts | CONFIRMED | — | S3 | §10.4 |
| P15 | Repository/doc sprawl and drift | Process | main stale; 206 recognition-upgrade docs; 5,408-line tracker; Stage 1 missed the Sep 27 evidence | CONFIRMED | Current-state notices | S3 | §11 |
| P16 | Phone closure during Stage 1 | Stability | ADB vanished, no crash record | UNKNOWN | Preflight receipts | S3 | sustained soak test |
| P17 | S2 features use absolute image coordinates (framing-sensitive) | S2 features / **design** | `PhoneCausalCore.kt` derive(): coordinates / width,height | CONFIRMED (design), HYPOTHESIS (impact) | — | S2 | fold into R1 |
| P18 | Context Assist cannot repair recognition | Context / **ML limits** | Stage 3: all 4 wrong words absent from Top-5; matcher fails on insertions | CONFIRMED (n = 5 phrases) | Shadow, advisory UI | S3 | after R2/L1 |

Historical issues that are **resolved**:

- The 12× fps mismatch, by cadence-aware training (P-phases, B2).
- Sequence train/serve skew (parity).
- Materializer truncation (8A-M).
- The FS two-letter plateau. Later tests show no cap, although the original episode was never
  diagnosed.
- Manual Start/Done FS (replaced).

---

## 7. Computer vision and perception assessment

### 7.1 Design judgment

Candidate01 is a defensible design. DWPose-t gives anatomical left/right slots from a full
skeleton, which avoids MediaPipe's palm-detector recall problem and hand-identity swaps. The
MediaPipe landmark model then supplies good finger geometry. Two design choices were never
validated against the refiner's training assumptions:

- The crop is an **axis-aligned square**. It has no in-plane rotation and no palm-anchored scale.
- Acceptance is a **hard gate**: presence ≥ 0.5 and ≥ 18 in-crop joints.

### 7.2 Hand-acceptance decomposition inside reviewed sign intervals

Probe `perception_decomp.py`, CONFIRMED on the saved observations. Counts are hand-slot
instances (2 per observation).

| Session | ACCEPTED | ROI present but presence < 0.5 | No ROI proposal | Joints < 18 |
|---|---:|---:|---:|---:|
| Sep 27, all 8 reviewed signs | 50 | 84 | 28 | 0 |
| Oct 15, all 4 reviewed signs | 83 | 40 | 1 | 0 |

- **The dominant rejection is presence < 0.5 with a valid DWPose ROI.** Missing proposals and the
  18-joint rule are minor. One-handed signs legitimately leave one slot empty, so these are upper
  bounds on loss.
- **The Recognition V2 body frame is not the problem.** Shoulders are valid in 1,325 of 1,364
  and 754 of 757 observations, so V2's shoulder-based normalization almost never falls back.
  `body_available = false` comes from hips being out of frame with close framing. That affects
  only the S2 body-availability features, not V2. This audit hypothesis was **tested and
  rejected**.

### 7.3 Motion dependence (probe `motion_acceptance.py`)

The table conditions on a hand accepted in the previous observation and bins by DWPose ROI-centre
speed, measured in ROI widths per second.

| ROI speed (ROI widths/s) | n | Still accepted | Median presence |
|---|---:|---:|---:|
| < 1 | 402 | **95.8%** | 0.985 |
| 1 – 2.5 | 46 | **50.0%** | 0.490 |
| 2.5 – 5 | 9 | 11.1% | 0.156 |
| > 5 | 11 | 0% | ~0.000 |

**LIKELY:** real hands disappear from the evidence stream mainly while they move. That is the
signing itself, and especially the transitions. The front camera's measured exposure is 50 ms
p50 in every front run in `artifacts/camera_input_01/device_timing*`, against 15–33 ms on the
rear camera. That is a strong physical reason (motion blur). Fast-moving ROIs also come from
noisy DWPose proposals, so blur is not proven. The test is R4.

### 7.4 Crop orientation (probe `rotation_probe.py`)

The probe rotates the crop so that the DWPose wrist→middle-MCP axis points up, keeping the same
centre and side. It uses saved JPEGs; the axis-aligned arm reproduces live acceptance (130 vs
125).

| Interval | Live accepted | JPEG axis-aligned | JPEG rotated |
|---|---:|---:|---:|
| TABLE, hands-up (27 ROI slots) | 0 | 0 | **11** |
| TABLE, hands-down (20) | 0 | 0 | 2 |
| All 11 genuine intervals (238) | 125 | 130 | 138 |

The saved TABLE frame (`frame_000385_original.jpg`, September 27) shows two clearly visible
horizontal flat hands with refiner presence 0.001–0.005. **LIKELY:** orientation is a real,
partial cause for horizontal or sideways handshapes. The crude rotation makes some HELLO frames
slightly worse. A proper MediaPipe-style ROI (rotation plus palm-anchored scale and shift) would
need its own evaluation. Any such change alters raw-v1 and requires re-extracting features and
retraining S2, WORD and FINGERSPELL (§12).

### 7.5 Is the model receiving the input it was trained on?

- **Feature semantics: yes** (parity).
- **Input distribution: no**, in at least four ways:
  - Recognizer training was ASL Citizen webcam video, extracted at native frame rate (good
    lighting, full upper body). The live phone uses a close, tilted selfie camera with a 50 ms
    exposure (§7.3).
  - Sparse sampling (handled by cadence views).
  - Motion-dependent hand dropout (§7.3).
  - S2 history-length shift (§8.3).
- Signer proficiency in all phone sessions is nonexpert or unknown.

---

## 8. Temporal segmentation and continuous-recognition assessment

### 8.1 What S2 was trained on (CONFIRMED, `s2_r2_continuous_domain_correction_01/main_candidate/dataset_manifest.json`)

Every positive is an **isolated single-sign clip** with short PRE and POST context. No training
sequence contains two signs, or a sign that begins while the hands are already up after a
previous sign.

| FIT domain | Rows | Median T (obs) | p90 T | Rows with T ≥ 61 | ACTIVE labels |
|---|---:|---:|---:|---:|---:|
| ASL Citizen / LOCAL / capture baseline | 213 | 16 | 32 | 12 | 995 |
| Enrichment | 48 | 14 | 22 | 2 | 294 |
| Phone positives (one signer, rested) | 4 | 38 | 40 | 0 | 42 |
| P1 negatives | 37 | **73** | 99 | **22** | 0 |

At runtime the S2 prefix is always full after about 12 s (61 observations at ~5/s). In training,
a full receptive field filled with real history almost always meant "no sign". Positives were
short sequences whose causal receptive field was mostly zero-padded.

### 8.2 The lifecycle (CONFIRMED by code and the 14 recorded events)

After the last ACTIVE observation:

- commit takes 467–734 ms (POST must persist 267 ms, and observations are about 200 ms apart);
- IDLE takes another 401–534 ms (400 ms stable non-ACTIVE).

So the next sign can open only about **1.0–1.3 s after the previous sign's last ACTIVE
observation**. In between:

- ACTIVE before commit cancels POST and **merges** the next sign into the current event;
- ACTIVE during WAIT resets re-arm and is **discarded**.

The only reliable way to satisfy this is to stop moving. That is the reported "lower hands and
wait".

### 8.3 Oracle-context probe — the strongest new finding (probe `s2_context_probe.py`)

The probe runs the frozen S2-R2 TFLite model on the exact Android-normalized 378 features. It
compares the live rolling 61-observation prefix with a fresh prefix that starts at or shortly
before the reviewed onset. The fresh prefix is an oracle, not deployable.

| Reviewed sign | Rolling-61 ACTIVE obs | Fresh @ onset−4 | Fresh @ onset |
|---|---:|---:|---:|
| Sep 27 A HELLO | 0/6 | 5/6 | 5/6 |
| Sep 27 A HOME | 0/9 | 4/9 | 4/9 |
| Sep 27 A TABLE (0 accepted hands) | 0/10 | 10/10 | 9/10 |
| Sep 27 B HELLO #1 | **11/11** | 5/11 | 0/11 |
| Sep 27 B HOME | 0/15 | 2/15 | 0/15 |
| Sep 27 B TABLE (0 accepted hands) | 0/14 | 7/14 | 7/14 |
| Sep 27 B HELLO #4 | 0/7 | 6/7 | 2/7 |
| Oct 15 A HELLO | 0/7 | 6/7 | 6/7 |
| Oct 15 B HELLO | 0/10 | 8/10 | 7/10 |
| Oct 15 C HELLO #1 | 3/8 | 8/8 | 6/8 |
| Oct 15 D HELLO (+hold) | 0/37 | 8/37 | 5/37 |
| **Signs with any ACTIVE** | **2/12 (incl. uncertain)** | **12/12** | **10/12** |

The 12 rows include the Sep 27 uncertain HELLO #4, which is omitted from the table (0/9 rolling,
8/9 fresh).

Interpretation:

- **CONFIRMED:** for these saved inputs, the current observations carry enough evidence for S2 to
  say ACTIVE. This includes TABLE, where no hand was accepted; S2 evidently uses ROI and body
  motion. **What suppresses ACTIVE is the long history, not missing perception evidence and not
  the re-arm timer.**
- **LIKELY:** the mechanism is the length/padding shortcut in §8.1.
- The rejected Stage 2 history-reset probe fits this. Resetting made every window look like a
  short positive clip, so S2 fired on non-sign motion too (non-sign events 4→9). That shows S2's
  motion semantics are weak, not that the context hypothesis is wrong.
- **UNKNOWN:**
  - why B-HELLO #1 succeeds with rolling history but not with a fresh prefix;
  - why the September 23 smoke test acquired 4/4 signs. Plausibly the history content mattered
    after the long idle with hands down, but this was not verified.

### 8.4 What is established about the "hands-down" symptom

| Candidate mechanism | Verdict |
|---|---|
| Re-arm timer blocks the next sign | Real (P2) but **secondary** in the captures: the second signs did not produce ACTIVE at all |
| Missing hand evidence | Contributes (P5/P6), but S2 fires on TABLE without accepted hands when history is fresh |
| S2 history/context dependence | **Primary** in both captures (§8.3) |
| Consecutive signs merge | Possible by design; not observed directly because second-sign ACTIVE was absent |
| Recognition/UI drops | Ruled out: no candidates reached those stages |

### 8.5 SentenceBuilder

It drops a gloss equal to the previous one. This hides duplicate commits from holds, but also
deletes genuine repeats. It should become event-aware only after abstention (R2) exists.

---

## 9. WORD and FINGERSPELL model assessment

### 9.1 WORD classifier

The model is an ordinary V2 4×64 causal TCN, about 192 k parameters, with a 236-way softmax, FP32,
trained on 3,926 clips from 40 signer groups.

Measured accuracy (CONFIRMED):

| Split | Top-1 |
|---|---|
| TRAIN, dense / sparse | 86.9% / 82.3% |
| DEV, dense / sparse (5 signers, 816 clips) | 50.25% / 39.95% |
| DEV Top-5 | 76.2% / 71.0% |

On data availability, CONFIRMED by counting `F:/ASL DATASET/ASL CITIZEN/ASL_Citizen/splits`:

- For the 236 glosses, ASL Citizen has 3,558 TRAIN clips (35 signers), 870 VAL (5 signers, the
  DEV) and 2,899 TEST (11 signers, sealed).
- The project already uses 3,309 of the 3,558. **Same-source data is exhausted.**
- The team's own attribution found signer diversity more associated with recall than clip count.
- Sem-Lex and PopSign were each touched for only about 40 targeted clips.

Weaknesses:

- **Closed-set with no abstention.**
  - The two genuine events in the captures scored 0.992 and 0.993.
  - The 12 non-genuine events (uncertain or non-sign) scored between 0.06 and 0.81. These are
    TURN 0.15, PICK 0.61, HAVE 0.30, SICK 0.37, HELLO 0.70, IF 0.51, TICKET 0.62, TAKE 0.07,
    AND 0.81, FEW 0.16, WASH2 0.24 and LETTER2 0.06.
  - This is too few to set a threshold, but it supports trying calibrated rejection (R2).
- **DEV is also the checkpoint selector** (combined DEV loss), so the reported DEV numbers are
  mildly optimistic.
- **The 11-signer sealed TEST has never been used.** That is good discipline, and it is the
  correct one-time final gate after the next major retraining.

### 9.2 FINGERSPELL

The model is V2.1 epoch034, a symmetric masked TCN with 292,956 inference parameters, trained on
4,096 FSboard TRAIN sequences.

Measured accuracy (CONFIRMED, `docs/team-research-findings.md`):

| Metric | Value |
|---|---|
| Letter recall | 63.2% |
| Pooled phone no-SPACE CER | 40.2% |
| Exact strings | 6/512 |
| Weak letters | M, Y, rare Q/X/F |

The live interaction asks a **phrase-trained CTC model** to decode a singleton letter from a
1–4 s **held** pose. Held static handshapes and setup transitions are rare in fluent FSboard
spelling. **LIKELY:** this is a distribution mismatch on top of the letter-discrimination limit.
Wrong letters can stabilize, and the 10-decode trace of October 9 (A,S,S,E,E,E,A,Y,Y,Y→"EY")
illustrates both.

Levers the team has not used:

- FSboard is a large phone-captured corpus. Public descriptions put it at over 3 million
  characters from about 147 Deaf signers; I did not verify these figures locally. The project
  trained on 4,096 sequences, and scaling from 1K to 4K helped.
- A dedicated per-frame static-letter classifier for held mode, using letter-labelled data,
  instead of singleton CTC from a phrase model (HYPOTHESIS; J/Z need motion handling).

WORD/FINGERSPELL ownership matches the intended design (CONFIRMED by code and device tests):

- one owner per observation;
- separate buffers;
- no score fusion;
- Settings acts as the manual fallback;
- six English context rules may route to FINGERSPELL;
- confirmation returns to WORD.

---

## 10. Android performance and software engineering assessment

### 10.1 Throughput (CONFIRMED numbers; causes as labelled)

| Measurement | Value | Source |
|---|---|---|
| Front delivered observations/s | 4.36–4.93 (Stage 1), 4.70 (Oct 15) | Stage 1/2 reports |
| DWPose, identical-pixel replay on the phone | 34.8 ms p50 | Stage 1 validation |
| DWPose, live front | 81–107 ms p50 | Stage 1/2 |
| One hand refiner, replay | ~31 ms | Stage 1 |
| Two hands, serial vs concurrent (replay) | 61.8 → 38.9 ms | Stage 1 |
| S2 / features | 7.1 / 0.4 ms | Oct 15 |
| Camera exposure, front / rear | 50 / 15–33 ms | `camera_input_01` |

- **UNKNOWN:** why live inference is about 2.5× slower than replay. Hypotheses to test, with
  `simpleperf` and thread affinity:
  - The device is an SM6150-class SoC with 2 performance cores, assuming the published spec for
    M2101K7AG. ORT (2 threads) and TFLite (2 threads, 4 with V3) oversubscribe them while
    CameraX, the ISP and preview compete for CPU.
  - Thermal or governor state differs between live and replay.
  - GC churn: each DWPose call boxes about 119 k floats into `Array<Array<FloatArray>>`.
- **LIKELY:** the WORD regression from V3 concurrency (4.64→4.36 obs/s, worse p95) is thread
  oversubscription. The FS gain (4.93→6.07) shows a scene-dependent benefit.
- `context/runtime-constraints.md` names CPU/XNNPACK/**INT8** as the baseline. Every perception
  model is FP32, and DWPose runs on ORT's default CPU provider. This is the largest unexploited
  compute lever, and it changes perception outputs, so it needs parity work (R5).
- Even at a 66 ms analysis time, a front sensor at a fixed 15 fps caps delivery at 15/s. The rear
  path already uses 30 fps.

### 10.2 Software engineering

**Good:**

- single-owner threading with no shared interpreters;
- generation and epoch guards;
- hash-verified assets;
- fail-closed load;
- 194–200 JVM tests;
- parity fixtures on device.

**Risks:**

- **P13:** a single exception permanently disables recognition until the Activity restarts.
- **Dead legacy code and backup assets ship in the APK.** The debug APK with Original words is
  about 822 MB.
- Release and debug feature sets diverge sharply. Any user study must state which build it ran.
- Cloud keys can be compiled into debug builds. This is documented, and release blanks them.

### 10.3 Tests run in this audit

- **Python suite.** A clean `git archive` export of `4503b55` (pipeline, eval, tests, tools,
  model, deploy, packages) was run against the project venv: **852 passed, 125 failed,
  38 errors, 13 skipped**. Almost all failures are `FileNotFoundError` or identity guards for
  private artifacts and Android assets not present in the export. The suite therefore depends on
  local data. The team's 119/141 "host test" counts are only reproducible on the original
  machine layout.
- **JVM and Android tests:** not run. They need a Gradle/SDK build that writes into other
  worktrees, plus an attached device.

### 10.4 Recommendation

Mark artifact-dependent tests with a pytest marker such as `requires_private_artifacts`, so
that a clean clone has a green, meaningful default suite.

---

## 11. Research methodology and evaluation weaknesses

**Strengths:**

- predeclared gates;
- one-run policies;
- sealed TEST;
- blinded human-boundary review tooling;
- exact replay;
- explicit claim limits.

These have prevented many false wins.

**Weaknesses (CONFIRMED examples):**

1. **Tiny, single-signer, nonexpert phone cohorts.**
   - n is between 4 and 10 signs per experiment.
   - The October 15 capture has 4 confident positive intervals.
   - Three of the seven intended signs, and the hold, are "UNCERTAIN".
   - None can estimate a rate. The design signer is the developer, whose proficiency is unknown.
2. **Recordings keep only processed observations** (about 5/s, saved as JPEG). Counterfactuals
   (denser cadence, other perception) cannot be replayed. Re-processing JPEGs is known to change
   S2 behaviour (12/62 → 42/62 ACTIVE recall in S2-R2 prep).
3. **The metrics do not measure the user's problem.** There is no tracked:
   - sign error rate over natural phrases;
   - false words per minute of non-signing;
   - time-to-ready between signs.

   Most results are containment, emission and parity measures.
4. **Mechanism hypotheses were tested by changing runtime policy** (the history reset) before
   cheap offline ablations on existing data. The §8.3 probe took minutes on data that already
   existed.
5. **Documentation drift costs real knowledge.**
   - The Stage 1 handoff claimed the A/B evidence was pending, while the reviewed September 27
     capture existed.
   - 206 recognition-upgrade documents and a 5,408-line tracker make the current state hard to
     find.
6. **DEV doubles as the selection set.** DEV-B shares signers with DEV-A, and FS selection used
   DEV-A.
7. **Engineering smoke tests are sometimes read as accuracy evidence.** Examples are "4/4 with
   READY waits" and "S→SM→SMY". The reports themselves usually caveat this correctly.

**Making future experiments decisive:**

- Build the phone replay benchmark (R3) **once**:
  - 3–5 ASL-proficient signers;
  - full-rate 30 fps video at high quality, plus device metadata;
  - 20–40 natural 2–5-sign phrases each, plus repeats, holds and non-sign activity;
  - gloss sequences and boundaries labelled by a qualified reviewer;
  - a 50/50 split into a tuning set and a sealed set.
- Then every perception, segmentation and recognizer change is an offline replay at simulated
  cadences, with device runs needed only for timing and parity.
- Pre-register three product metrics:
  - **SER**: sign error rate (substitutions + deletions + insertions) over phrases;
  - **FWPM**: false words per minute of non-signing;
  - **TTR**: median time from the end of a sign to readiness.

---

## 12. Technical risks and architectural limitations

1. **Cascade coupling.** raw-v1 is the input to S2, Recognition V2 and the FS Adapter. Any
   perception change requires re-extracting about 4.7 k WORD clips, the S2 data and 4 k+ FS
   sequences, then retraining three models. Perception changes must be batched and decided with
   offline evidence first, and the extraction→train→evaluate pipeline must become a one-command
   rebuild.
2. **An isolated-sign paradigm for a continuous-signing product.** The S2 + FSM + closed-set
   classifier design can at best support a sequence of isolated signs. Coarticulated fluent
   signing needs continuous gloss recognition (CTC or similar), trained on phrase-level data the
   project does not have.
3. **The data ceiling.** About 15 clips per class from about 35 signers cannot support 236-way
   unseen-signer recognition at a product level. This is a data problem first, then a model
   problem; the project's own experiments closed the cheap model levers.
4. **Hardware ceiling.** On a 2-performance-core SoC with FP32 models, about 5 obs/s is the
   current reality. The 15-FPS target is not plausible without INT8 or lighter models and ROI
   tracking.
5. **Process throughput.** Heavy governance per experiment, combined with tiny cohorts, slows
   learning. The governance should stay, but be spent on fewer and more informative experiments.

---

## 13. Prioritized recommendations

### Immediate engineering (offline-first, each behind a flag and an offline gate)

**R1 — Fix the S2 context shortcut (highest value).**

- *Why:* P1 is the primary blocker of consecutive signing (§8.3).
- *Verify first, about 1 day:*
  1. Rerun §8.3 with the Phase-7 control S2 to see whether both models show the effect.
  2. Run frozen S2 on governed DEV clips prepended with real idle or negative history, so the
     receptive field is full. If DEV ACTIVE recall collapses, the shortcut is confirmed without
     any phone.
- *Implement:* retrain S2 once on **length-balanced long sequences**:
  - stitch real raw-v1 observations from several isolated clips and negatives into 30–120 s
    streams;
  - recompute the per-step deltas at each join and mark the joins as ignore labels;
  - include sign→sign joins without rest;
  - train on random full-length (≥61) windows so positives and negatives see the same padding
    statistics;
  - consider body-relative coordinates (P17) only as a separate, versioned ablation.
- *Gate:*
  - DEV containment no worse than today;
  - stitched-stream ACTIVE recall on second signs;
  - FWPM on the P1 and capture negatives;
  - then both reviewed captures as a diagnostic, not a tuning target;
  - then a new capture.
- *Risk:* stitched transitions are unnatural, so validate on real phrases from R3.

**R2 — WORD abstention.**

- *Why:* P3. Every event currently becomes a word.
- *Verify:* a risk–coverage curve of top-1 probability (and margin) on DEV sparse views, plus the
  12 non-genuine capture events. Choose an operating point that maximizes useful words per false
  word, and pre-register it.
- *Benefit:* a large drop in false words for a moderate recall cost.
- *Risk:* rejecting correct low-confidence signs. Show "?" or a Top-3 picker instead of dropping
  silently.

**R3 — Phone replay benchmark and product metrics.** See §11. This is a prerequisite for credible
R1/R5/R6 and L1 claims.

**R4 — Camera exposure A/B (cheap, device).**

- Front camera at AE (30,30) or with an exposure cap, against the current (15,15), with the same
  scene and lighting.
- Metric: hand-acceptance-given-previous across motion bins (§7.3), plus delivered obs/s.
- Exposure changes image statistics rather than raw-v1 semantics. Still re-check S2 and
  recognizer behaviour on replay.

**R5 — Perception decision batch: one "Candidate01.1" decision, offline on R3 data.**

Candidates:

- MediaPipe-style rotated and palm-anchored crops (§7.4);
- ROI tracking from previous refined landmarks, so DWPose runs every N frames;
- INT8/FP16 DWPose-t and refiner via TFLite/XNNPACK;
- one thread per concurrent interpreter.

Gate on recall-in-motion, landmark error against a small labelled set, and obs/s on device.
Only then re-extract and retrain (§12.1).

**R6 — Lifecycle for sign-to-sign transitions (after R1).**

- Allow ACTIVE→ACTIVE boundaries, for example with a learned boundary or "change" class, or by
  splitting on a sustained ACTIVE dip.
- Replace "ACTIVE during WAIT is discarded" with "ACTIVE after a minimal refractory period opens
  a new candidate".
- Evaluate TTR, merges and duplicates on R3.

**R7 — Sentence repeats.** After R2, replace gloss dedup with event-based suppression: suppress
duplicates only when two events overlap or a hold is detected.

**Quick fixes:**

- display-normalize gloss IDs (P12);
- recover from analyzer exceptions by restarting the analyzer generation (P13);
- remove `_backup_*` assets.

### Longer-term model and architecture research

**L1 — WORD data scale and scope.**

- Add signer-diverse external clips for the in-vocabulary glosses: Sem-Lex (TRAIN), PopSign
  (phone selfie, Deaf signers) and others. Run every source through Candidate01(.1) with
  provenance and signer-disjoint governance.
- Separately, revisit the vocabulary with a product owner: add core conversational signs, and
  consider a smaller high-accuracy tier.
- Evaluate once on the sealed ASL Citizen TEST.

**L2 — FINGERSPELL.**

- Scale FSboard training beyond 4 K sequences.
- Build a held-letter classifier from letter-labelled data, either reviewed or public static
  letter sets. Check licences first.

**L3 — Continuous recognition.** CTC/gloss-sequence models only after phrase-level labelled data
exists (from R3, scaled).

**L4 — External recognizers** (Sign-Speak, SONAR, Uni-Sign). The repository contains **no** SONAR
or Uni-Sign experiment, only mentions; Sign-Speak is an offline harness only. Use them, if at
all, as an upper-bound baseline on R3, under consent and cost controls. They are not a drop-in
replacement for on-device recognition.

---

## 14. Proposed next-stage roadmap

| Stage | Content | Exit gate |
|---|---|---|
| **0. Measure** (1–2 weeks, parallel) | R3 benchmark capture and labels; product metrics; probe reproducibility (Appendix A); test-suite markers | Benchmark sealed; baseline SER/FWPM/TTR on current app via replay |
| **A. Segmentation and abstention** (2–3 weeks) | R1 verification → one S2 retrain; R2 calibration | Second-sign acquisition and FWPM improve on the tuning set, then on the sealed set; no DEV regression |
| **B. Perception decision** (2–4 weeks) | R4 on device; R5 offline; choose Candidate01.1 or keep 01 | Motion-bin recall and obs/s improve with parity; decision documented |
| **C. Rebuild on the chosen perception** (3–6 weeks) | Re-extract; retrain S2 (R1 recipe), WORD with L1 data, FS with more FSboard | WORD sealed-TEST Top-1 and benchmark SER; FS letter recall |
| **D. Continuous lifecycle** | R6, R7 | TTR < ~0.5 s with no FWPM regression |
| **E. Research track** | L2 held-letter classifier, L3 continuous models | Separate gates |

This revises the V3 sequence in three ways:

- Stage 2's next step is a **model retrain plus abstention**, not timers.
- Stage 1's next step is **evidence quality during motion** (exposure, crops), not scheduling.
- Stage 3 is **data-driven** and starts as soon as the perception decision is made, rather than
  after Stage 2 "completes".

Do not repeat:

- timer or history-reset sweeps;
- same-data sampler, loss or seed loops;
- generic RGB fusion;
- small single-signer smoke tests presented as accuracy.

---

## Appendix A — Probes run in this audit (read-only)

The probes run with the project venv: `F:/ASL DATASET/5. Apphear3/.venv/Scripts/python.exe -I`.
They take the stage-2 checkout and session directories as arguments:

- `docs/audit/probes/perception_decomp.py <sessions…>`: §7.2.
- `docs/audit/probes/motion_acceptance.py <sessions…>`: §7.3. This copy has the
  "accepted in the previous observation" condition built in.
- `docs/audit/probes/rotation_probe.py <stage2 checkout> <sessions…>`: §7.4. It uses saved JPEGs,
  not live RGBA.
- `docs/audit/probes/s2_context_probe.py <s2_r2_fp32.tflite> <sessions…>`: §8.3.

Sessions:

- `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/continuous_transition_readiness_01/device_capture/session_20260927T162103Z`
- `artifacts/recognition_v3_stage2_compact_device/finalized/session_20261015T155027Z`

Both are under the `F:` research checkout.

## Appendix B — Limitations of this audit

- **No device.** No live measurement, no JVM or instrumented tests, and no GitHub check.
- **AppHear v2 was not inspected.** AGENTS.md forbids touching it, so v2 and CNN-LSTM details come
  only from v3 documents.
- **Private bulk artifacts were sampled, not exhaustively re-verified.** The audit used the two
  reviewed captures, the S2-R2 manifest, camera timing and ASL Citizen splits.
- **The probe results come from 12 reviewed signs from 1–2 nonexpert signers.** They establish a
  mechanism, not a population rate.
- FSboard corpus figures are from public descriptions and were not verified locally.
