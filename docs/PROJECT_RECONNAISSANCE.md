# AppHear — Project Reconnaissance & Technical Audit

> **Erratum (2026-11-09, added during Phase 1).** This report states that no false-positive rate had been measured and that no cross-signer evidence existed for the commit path (F-001, F-003, §E.4, §I). That is **partly wrong**. My listing of `docs/` was truncated and I did not open `docs/audit/` (dated 2026-10-16…10-23), which contains a whole-event admission study, a held-out-signer-calibrated top-1 gate (0.55 for production S2-R2, 0.75 for Arm A + confirm-boundary) and an event ledger of human-reviewed phone sessions. The mechanism described in F-001 (unconditional top-1 commit, pass-through admission) is unchanged and still correct; the *evidence gap* is narrower than stated (the evidence exists but is small and development-exposed). See `docs/PHASE_1_RECOGNITION_RELIABILITY.md`. Other sections were not re-audited.

Date: 2026-11-09 · Branch audited: `jepjep-claude` @ `1f9e571` (clean working tree, 48 commits ahead of `main`, 0 behind)
Scope: read-only audit. No source, model, configuration, schema or dependency was modified. This file is the only artifact added to the repository.

## How to read this report

Every statement carries one of these evidence labels. Do not treat a lower label as a higher one.

| Label | Meaning |
|---|---|
| **[CONFIRMED-CODE]** | I read the code and the behavior follows from it. Runtime frequency/impact may still be unmeasured. |
| **[CONFIRMED-RUN]** | I executed it in this audit and observed the result. |
| **[REPO-REPORTED]** | A repository document reports a measurement. I did not reproduce it; its method is the repo's, not mine. |
| **[SUSPECTED]** | Plausible from code/doc evidence, not demonstrated. Not a confirmed bug. |
| **[EVIDENCE GAP]** | The data needed to decide does not exist in the repo or in this environment. |

**No on-device measurement was made in this audit** (see §Limitations). Every FPS/latency/memory figure below is `[REPO-REPORTED]`.

---

## A. Executive Summary

**Purpose.** AppHear is an on-device, real-time American Sign Language (ASL) assistant for Android. A signer faces the phone; the app detects signs, builds a word sentence, speaks it, and supports a conversation loop (hearing person's speech → text → animated ASL avatar; Context Assist predicts likely replies). The repo also holds the offline Python research/training pipeline that produced the models, a text-to-ASL avatar player, a recorder app, and a separate React Native prototype.

**What signs it recognizes (determined from implementation, not assumed).**
- **WORD mode:** *isolated, pause-separated* signs from a closed **236-gloss vocabulary** (`vocab`/`class_index_to_gloss`, 236 outputs). Not fluent continuous ASL. `[CONFIRMED-CODE]` (`RecognitionV2LiveRecognizer.OUTPUTS = 236`; `context/project-overview.md`).
- **FINGERSPELL mode (debug-flag only):** fingerspelled ASL letters, 28 CTC logits, geometry-only. Experimental; not present in release builds. `[CONFIRMED-CODE]` (`FINGERSPELL_EXPERIMENT_ENABLED` is `false` in the release block of `app/build.gradle.kts`).

**Stack.** Kotlin 2.0.21 / AGP 8.11.2 / Gradle 8.13 wrapper / compileSdk+targetSdk 36 / minSdk 26, **arm64-v8a only** · CameraX 1.3.4 · ONNX Runtime Android 1.22.0 · TensorFlow Lite 2.16.1 (XNNPACK, CPU) · MediaPipe Tasks Vision 0.10.14 (**only used by unreachable legacy code**, see F-008) · a prebuilt C++ JNI preprocessor · Python 3.11+/TensorFlow-Keras offline pipeline · WebView-based GLB avatar playback (`androidx.webkit`, `model_viewer.html`).

**Current implementation status.** The recognition path that actually runs in the app is **not** the one the top-level rules document describes (F-007). It is:
`CameraX RGBA 480×360 @ ≤15 fps → native C++ preprocess → DWPose-t (ONNX, 256×192, 133 keypoints) → hand ROI → MediaPipe hand-landmark TFLite (224×224) per hand → S2-R2 segmentation TCN (PRE/ACTIVE/POST) → event decoder → Recognition-v2 TCN ([96,350] → 236 classes) → top-1 gloss → sentence`.

**Overall architectural assessment.** The perception→segmentation→recognition chain is carefully engineered (hash-pinned assets, fail-closed contract checks, parity fixtures, monotonic-timestamp guards, generation-guarded async results). The weaknesses are not in plumbing; they are in **(1) the absence of any reject path before a word is committed, (2) sub-target and unmeasured-in-the-field throughput, (3) no field-grade accuracy evidence, and (4) a large body of stale documentation and dead code that misdescribes the product.**

**Most important findings (details in §I).**

1. **F-001 CRITICAL — Every detected "sign episode" commits its top-1 word with no confidence floor, no open-set rejection and no admission gate** (`PhoneNewSignAdmission` is pass-through; `PhoneProductionSession.consume` takes `top5.first()` unconditionally). The repo's own live smoke recorded **three unwanted committed words** during non-sign behavior (open hand → HELLO; seat adjustment → HOSPITAL1; ordinary movement → STAND2). False-positive *rate* is unmeasured.
2. **F-002 HIGH — Throughput is below the project's own ≥15 fps floor in live use** `[REPO-REPORTED]` (≈11 fps HUD, 5–7 fps in transitions on the target Xiaomi). The pipeline is strictly serial on one analyzer thread.
3. **F-003 HIGH — No cross-signer, end-to-end live accuracy exists for WORD.** FINGERSPELL offline phone CER is ~40% and exact-string success is 6/512.
4. **F-004 HIGH — A single exception in the analyzer permanently stops recognition for the session.**
5. **F-005 HIGH — Third-party service keys are compiled into `BuildConfig`, and the ElevenLabs key is not zeroed for release builds.**
6. **F-006 HIGH — The only native library that ships in release is 4 KB-aligned, prebuilt, and not buildable from the Gradle project.**
7. **F-007 MEDIUM — `AGENTS.md`/`context/` rules describe a MediaPipe-258 pipeline that is dead code.**

---

## B. Repository Inventory

### B.1 Top-level layout (git-tracked: 2,992 files; `.git` 177 MB)

| Path | Tracked files | Responsibility |
|---|---:|---|
| `android/` | 1,115 | The Android app (`:app` single module). Source sets: `main`, `debug`, `test`, `androidTest`, and five avatar-asset overlays (`aslPilot`, `aslShared`, `aslWords`, `aslIdle`, `aslAlphabet`, `aslOriginalWords`). Also `android/tools/` (≈55 Python/Node asset-authoring scripts for the text-to-sign avatar). |
| `docs/` | 339 | Dated experiment plans/results (design rationale + evidence). |
| `context/` | 288 | "Operational contracts" read by agents; includes `recognition_upgrade/` (≈180 dated experiment/result files). |
| `pipeline/` | 227 | Offline Python data pipeline (extract, detect, normalize, quality, features, crops, rgb, perception_vnext, fingerspelling, ingest). |
| `model/` | 191 | Keras model definitions, training and export entry points, many fingerspelling experiment scripts. |
| `tests/` | 164 | Python tests (163 `test_*.py`, 922 test functions). |
| `eval/` | 140 | Metrics, calibration, streaming/confirmation evaluation, runtime diagnostics, sentence-assist evaluation. |
| `evidence/` | 117 | Final evaluations/predictions/histories for fingerspelling work. |
| `tools/` | 101 | Handoff verifier, fingerspelling, FSboard, conversation-flow, sentence-assist, text-to-ASL asset tools. |
| `asl recorder/` | 90 | A separate Android recorder app (`ASLRecorder2`, Java/XML). |
| `apphear-react/` | 79 | Separate React Native / iPhone prototype ("RN01": FPS cadence only; recognizes nothing). |
| `packages/` | 42 | Frozen fingerspelling V2.1 package + research checkpoints. |
| `datasets/`, `artifacts/`, `deploy/` | 40 / 15 / 16 | Dataset manifests; split/audit artifacts; TFLite export scripts. |
| root | 18 | `AGENTS.md`, `README.md`, `TEAM_HANDOFF.md`, `memory.md` (94 KB), 8 Windows `.ps1` training scripts, two handoff/report `.md`, `pyproject.toml`, `requirements.txt`. |

Tracked files by type: `.py` 776 (≈214 k lines), `.json` 445, `.md` 444, `.glb` 318, `.kt` 287, `.xml` 177, `.f32` 114, `.bin` 56, `.ps1` 48.

### B.2 Android module (`android/app/src/main/java/com/example/apphear`, 138 Kotlin files, ≈16.7 k lines)

| Package | Responsibility | Live in production? |
|---|---|---|
| `SplashActivity` → `LoadingActivity` → `MainActivity` | Launcher chain (only exported activity). App shell with navigation fragments. | Yes |
| `RecognitionActivity` (1,512 lines) | Camera binding, preview, recognition UI, fingerspell controls, conversation flow, speech, legacy A1/RU-D1 diagnostics. | Yes |
| `perceptionvnext/` | **The live recognizer**: `Candidate01FrameAnalyzer`, `PerceptionVNextRunners` (DWPose-t, hand refiner), `PerceptionVNextNativePreprocessor` (JNI), `PhoneProductionSession`, `PhoneCausalCore` (feature builder + event decoder), `PhoneS2Runner`, `RecognitionV2`, `RecognitionV2LiveRecognizer`. | **Yes** |
| `pipeline/` (`FrameAnalyzer`, `IndependentClockFrameAnalyzer`, `LandmarkerBundle`, `AdaptiveController`, …) and `pipeline/recognition/`, `pipeline/features/` | The **legacy** MediaPipe + 258-feature path (S0–S8). | **No — unreachable** (F-008) |
| `fingerspelling/`, `coordination/`, `contextassist/` | FINGERSPELL runtime/policies; WORD↔FINGERSPELL routing; Context Assist (reply prediction via Gemini / OpenAI-compatible fallback / fake). | Debug-flag only |
| `sentenceassist/`, `llm/` | Evidence-grounded sentence rendering, grounding validator, hedged LLM calls. | Flag-gated |
| `domain/texttoasl`, `ui/texttoasl` | Text → ASL avatar planner/catalog/player (GLB animations in WebView). | Yes |
| `ui/speech`, `ui/settings`, `ui/profile`, `ui/home`, `data/profile`, `data/settings` | TTS (ElevenLabs → Android TTS), settings, optional Supabase accounts (encrypted session store). | Partly (accounts flag-gated) |
| `camera/CameraTimingProbe`, `p8b/` | Diagnostics. | Flag-gated |

`src/debug` (213 files) holds ~15 debug-only research activities (`p6c`, `p7d`, `p7dr1`, `p7dr2`, `p7e`, `p8b`, `p8c*`, `perceptionvnext/*Activity`), all `exported="true"`, plus the C++ source and two research `.so` files.

### B.3 Entry points

- Launcher: `SplashActivity` (only `exported=true` activity in the main manifest).
- Recognition: `RecognitionActivity.start()` → `PhoneProductionSession.load()` on `Dispatchers.IO` → `bindCamera()` → `bindPhoneCamera()`.
- Debug ADB aliases: `RuD10BenchmarkActivity`, `A1BenchmarkActivity` (→ `RecognitionActivity`), debug research activities.
- Offline: `pipeline/run_pipeline.py`, `model/train*.py`, `deploy/export_*.py`, `eval/run.py`.

### B.4 Models and large assets (main source set, `assets/` = 232 MB)

| Asset | Size | Used by live path? |
|---|---:|---|
| `asl_animations/` (107 files) | 186 MB | Yes (text-to-ASL) |
| `perception_vnext/dwpose_t_singlepass.onnx` | 22.1 MB | **Yes** |
| `perception_vnext/hand_landmarks_detector.tflite` | 5.5 MB | **Yes** |
| `phone_causal_recognition_01/s2_r2_candidate/s2_r2_fp32.tflite` (+ `s2_phase7_fp32.tflite` control) | ≈0.5 MB each | **Yes** |
| `phase4a_gate2_recognizer_parity/ordinary_v2_tcn_fp32.tflite` | 0.8 MB | **Yes** |
| `mediapipe/hand_landmarker.task`, `pose_landmarker_lite.task` | 7.8 + 5.8 MB | **No** (legacy only) |
| `streaming.tflite` (legacy INT8 258→236), 3× `phase1_shadow_seed_*.tflite` | 0.23 + 3×0.71 MB | **No** |
| 10× `_backup_*` directories (old configs/models) | ≈1.7 MB | **No** — shipped in every APK |

### B.5 Build / test / docs inventory

- Build: Gradle Kotlin DSL; version catalog `gradle/libs.versions.toml`; ≈35 Gradle properties are turned into `BuildConfig` flags (debug) with a hand-maintained all-`false` release block. `isMinifyEnabled=false` in release; **no `signingConfig`**. Native code is **not** built by Gradle (no CMake/ndkBuild); `libperceptionvnext.so` is a committed binary under `src/main/jniLibs/arm64-v8a/`.
- Tests: 68 JVM test files / **336** `@Test`; 38 instrumented test files / **64** `@Test`; 163 Python test files / 922 test functions.
- **No CI configuration** (`.github`, `.gitlab`, etc. absent).
- Docs: very large and dated; `TEAM_HANDOFF.md` and `context/team-current-state-2026-10-09.md` are the current-state entry points and explicitly say older docs are partly stale.

---

## C. Architecture Assessment

### C.1 Actual execution flow (live, WORD mode)

```
SplashActivity → LoadingActivity → MainActivity (nav shell) → RecognitionActivity
  start():  Dispatchers.IO: PhoneProductionSession.load()                         [async, off main]
              • System.loadLibrary("perceptionvnext"), arm64-v8a required
              • verify materializer SHA-256, S2 package, Recognition-v2 model/manifest SHA-256
              • (debug) FingerspellModels
            Candidate01FrameAnalyzer(DWPoseTRunner, HandRefinerRunner)
  bindPhoneCamera():
     ImageAnalysis: targetResolution 480×360, KEEP_ONLY_LATEST, RGBA_8888,
                    Camera2Interop AE_TARGET_FPS_RANGE = (15,15) front [(30,30) rear only if advertised AND rear flag]
  per frame, ON THE CAMERA EXECUTOR (single thread), synchronized:
     1. native preprocess (rotate + resample + ImageNet norm) → [1,3,256,192]
     2. DWPose-t ONNX (2 intra-op threads) → SimCC decode → 133 keypoints + support
     3. hand ROI from wrist/hand keypoints (support ≥ 0.10)
     4. HandRefiner TFLite 224×224 (XNNPACK, 2 threads) — LEFT then RIGHT, serial
        (parallel variant exists behind RECOGNITION_V3_PARALLEL_HANDS, default OFF)
        hand "observed" iff presence ≥ 0.50 AND ≥ 18/21 valid joints
     5. FINGERSPELL owner (debug) may consume the observation; otherwise →
     6. PhoneSegmentationFeatureBuilder (378 floats) → S2-R2 TFLite (FP32, ≤61-observation prefix)
        → argmax ∈ {PRE_IDLE, ACTIVE_SIGN, POST_RECOVERY}
     7. PhoneCausalEventProducer state machine (min active 133 ms; post-confirm 267 ms;
        re-arm after 400 ms stable non-ACTIVE; gap guard 533 ms)
     8. on EVENT: materialize window from 256-obs ring → Recognition-v2 [96,350]+mask → TFLite (4 threads)
        → top-5 → commit top-1 → SentenceBuilder
     9. onResult → runOnUiThread (every frame) → overlay, HUD, gloss, sentence
```

### C.2 Component relationships and data flow

- One ordered, single-consumer chain; the "owner" seam (`ownsObservation`) lets FINGERSPELL take an observation instead of WORD. Stale async results are guarded by generation/epoch tickets (`cameraGeneration`, `HeldLetterPolicy.epoch`). Good practice.
- Contract enforcement is strong: `RecognitionV2LiveRecognizer.init` checks schema strings, tensor shapes, tolerance constants and SHA-256 of both manifest and model; `PhoneProductionSession.load` pins the materializer hash. A mismatched asset fails closed. `[CONFIRMED-CODE]`
- Orientation: rotation is applied natively; **no mirroring is introduced in the analysis path** (consistent with the documented invariant). `[CONFIRMED-CODE]`

### C.3 Architectural weaknesses

| # | Weakness | Evidence |
|---|---|---|
| 1 | No reject/abstain stage between segmentation and commit (F-001). | `PhoneCausalCore.kt: PhoneNewSignAdmission` (`PASS_THROUGH` is the only policy); `PhoneProductionSession.consume`. |
| 2 | Whole perception+segmentation+recognition chain on one thread; commit-time inference runs on the same thread (F-002, F-014). | `Candidate01FrameAnalyzer.analyze` is `@Synchronized` on the camera executor. |
| 3 | Fatal latch on first exception (F-004). | `Candidate01FrameAnalyzer`: `failed = true` is never cleared. |
| 4 | Two entire recognition stacks in one module; one is dead (F-008). | `LandmarkerBundle.create`/`RecognitionPipeline.load` have no callers; `RecognitionActivity.landmarkers`/`recognizer` are never assigned. |
| 5 | `RecognitionActivity` is a 1,512-line mixed-concern class (F-010). | Camera, UI, fingerspelling, A1 shutdown choreography, RU-D1, speech, conversation flow in one file. |
| 6 | Build-flag explosion: ≈35 properties → `BuildConfig` with duplicate manual release overrides (F-015). | `app/build.gradle.kts`. |

Circular dependencies: none detected in the packages I read. Unused dependencies: MediaPipe Tasks Vision (only referenced from the four unreachable legacy files `FrameAnalyzer`, `IndependentClockFrameAnalyzer`, `LandmarkerBundle`, `LandmarkAdapter`). `[CONFIRMED-CODE]`

---

## D. Detection Pipeline Assessment

### D.1 Camera → detection

| Item | Finding |
|---|---|
| Camera API | CameraX 1.3.4 `ImageAnalysis` bound with `Preview` via `bindToLifecycle`. |
| Format / size | `OUTPUT_IMAGE_FORMAT_RGBA_8888`; `setTargetResolution(480×360)` (deprecated API; actual delivered size is device-dependent and the native preprocessor *requires* it stay constant — `VNEXT_NATIVE_CAMERA_GEOMETRY_CHANGED` otherwise). |
| Frame rate | Fixed AE range `(15,15)` front. A fixed range can force longer exposure in dim light (motion blur) `[SUSPECTED]`; rear `(30,30)` only when advertised and `RECOGNITION_REAR_CAMERA_ENABLED`. |
| Backpressure | `STRATEGY_KEEP_ONLY_LATEST` — frames arriving while the analyzer is busy are dropped; processed rate = 1 / per-frame latency. Correct for real-time use. |
| Preprocessing | Native C++: rotation by `imageInfo.rotationDegrees`, resample to 256×192, ImageNet mean/std `{123.675,116.28,103.53}/{58.395,57.12,57.375}` for DWPose; hand crop `/255`. One `memcpy` of the frame per call. |
| Lifecycle | `onStop` resets temporal state; CameraX unbinds with the lifecycle; `onDestroy` unbinds, shuts the executor, then closes native runtimes on a separate thread **only after `awaitTermination(10s)`**, deliberately leaking rather than risking use-after-free. This is careful and correct. |
| Permission | Runtime camera permission via `registerForActivityResult`; denial shows a message. `uses-feature camera.any required=true`. |

### D.2 Continuous processing behavior

- **Detection is episodic, not frame-wise.** The S2-R2 network emits a 3-state label per observation; the decoder opens a candidate on the first ACTIVE, bridges PRE gaps < 133 ms, confirms after 267 ms of POST, requires ≥ 133 ms of ACTIVE span, then commits once and waits for 400 ms of stable non-ACTIVE before re-arming. `[CONFIRMED-CODE]` (`PhoneDecoderConfig`).
- **Repeat detection** of the same held sign is suppressed by the re-arm rule; the repo's own transition-diagnostics report states that ACTIVE during WAIT can block a legitimate next sign (`A_REARM_LIFECYCLE_BLOCK`) and that two consecutive signs can merge into one episode (`B_NO_INTERSIGN_S2_BOUNDARY`). Both are `[REPO-REPORTED]` as *plausible, not yet proven on continuous signing* (`APPHEAR_CONTINUOUS_TRANSITION_AND_READINESS_01_REPORT.md`, 2026-09-28).
- **Missed detections — known causal factors:**
  1. Hand ROIs are proposed from DWPose-t keypoints at 256×192 input. Small, distant, fast or blurred hands may yield no ROI → `handProposalPresent=false` → no hand observation. `[SUSPECTED]`; the repo has several ROI-recovery studies (`E2B_ROI_RECOVERY_PLAN`, `E2C_TEMPORAL_TRACKING`, `E2D_DETECTOR_OPERATING_POINT`) that treat this as a real failure mode.
  2. Low sustained fps lengthens inter-observation gaps; a gap > 533 ms resets the re-arm timer. `[CONFIRMED-CODE]`
  3. The refiner requires ≥ 18/21 joints valid *and* presence ≥ 0.50; partial hands are treated as absent. `[CONFIRMED-CODE]` Partial/occluded signs are therefore dropped, not degraded.
- **False detections:** see F-001. There is no hand-count, body-visibility, confidence or class gate before opening a candidate.
- **UI-thread blocking:** none observed in code. Model load is `Dispatchers.IO`; per-frame UI work is `runOnUiThread` posting of a small `FrameResult` + overlay `invalidate`. `[CONFIRMED-CODE]` (A frame object is allocated and a UI post is made on every processed frame.)
- **Overlapping inference:** impossible on the live path (analyzer is `@Synchronized`, one camera thread, KEEP_ONLY_LATEST).
- **Stops after prolonged operation:** a team soak of ≈2 minutes showed PSS ≈272 MB flat (271,982 → 272,143 KB) `[REPO-REPORTED]`. No long-duration (hours) test exists `[EVIDENCE GAP]`. A *different* stop mode is confirmed in code: F-004.

### D.3 Bottlenecks (ranked by evidence)

| Rank | Stage | Evidence |
|---|---|---|
| 1 | Serial chain of 4–5 network invocations per frame on one thread | `Candidate01FrameAnalyzer.analyze`; `[REPO-REPORTED]` integrated 14.88 fps completed vs 15 fps capture failed the project gate (P7E); ≈11 fps HUD / 5–7 fps in transitions in the S2-R2 integration doc. |
| 2 | DWPose-t ONNX full-frame inference (22 MB, 2 threads) | Largest model; `[SUSPECTED]` dominant, no per-stage numbers re-measured here. Repo logs `pose_inference_and_output_ms` under `RECOGNITION_V3_PROFILE_ENABLED`. |
| 3 | Two *serial* 224×224 hand refinements | Parallel variant exists, default off. |
| 4 | Commit-time Recognition-v2 invoke (4 threads) on the camera thread | Stalls the next frames; duration is logged as `wordMs` but not summarized anywhere I found `[EVIDENCE GAP]`. |
| 5 | Per-frame heap churn: ONNX `result.get(...).value` produces nested `Array<Array<FloatArray>>` per frame; per-frame `FrameResult`, `PhoneOverlayFrame`, `FloatArray(42)` ×2 | `[SUSPECTED]` GC pressure; unmeasured. |

---

## E. Recognition Accuracy Assessment

### E.1 Model inventory

| Model | Format / runtime | Input → Output | Quantization | Size | Role |
|---|---|---|---|---:|---|
| DWPose-t single-pass | ONNX, ORT 1.22 CPU, 2 intra / 1 inter thread, `ALL_OPT` | `input [1,3,256,192]` FP32 → `simcc_x`, `simcc_y` (133 keypoints) | FP32 | 22.1 MB | Whole-body pose → hand ROIs + 8 body points |
| Hand landmark detector | TFLite 2.16.1, XNNPACK, 2 threads, NNAPI off | `[1,224,224,3]` → `Identity [1,63]`, presence, handedness, world `[1,63]` | FP32 | 5.5 MB | 21-point hand refinement per ROI |
| S2-R2 segmenter (+ Phase-7 control) | TFLite FP32 | `[1,T,378]` (T ≤ 61 receptive field) → `[1,3]` states | NONE_FP32 | ≈0.5 MB | PRE/ACTIVE/POST per observation |
| Recognition-v2 TCN (`GATE2_FROZEN`) | TFLite, XNNPACK, **4 threads** | `[1,96,350]` FP32 + mask `[1,96]` BOOL → `[1,236]` FP32 | FP32 | 0.8 MB | 236-gloss classifier on the materialized event window |
| Legacy `streaming.tflite` | TFLite | `[1,96,258]` → `[1,96,236]` | INT8 weights+activations, FP32 I/O | 0.23 MB | **Dead path** |
| Fingerspelling V2.1 epoch034 (debug) | TFLite FP32, Adapter.v1 `[T,405]` | → 28 CTC logits | FP32 | (package) | Experimental |

Hardware acceleration: **none used** on the live path (CPU/XNNPACK; `setUseNNAPI(false)`; no GPU delegate). The live path therefore does not violate the repo's "no GPU delegate" rule. The *dead* legacy path would enable the GPU delegate (`FeatureFlags.LANDMARKER_TRY_GPU = true`, `recognition_config.json: mediapipe_delegate.mode = "gpu"`), contradicting the rule — a latent hazard if the legacy path is ever revived.

### E.2 Recognition algorithm and classification logic

1. Event window is materialized from the observation ring (≤ 256 obs / 30 s) → `RecognitionV2.temporalView(DENSE)` → `[96,350]` + mask.
2. Softmax over 236 classes (model output is probabilities).
3. **`top1 = prediction.top5.first()` is committed unconditionally** (`PhoneProductionSession.consume`). There is no probability threshold, margin, calibration, temperature, entropy test or "none/unknown" class on the live path. `[CONFIRMED-CODE]` Top-5 is retained as evidence for Context Assist only.
4. The legacy path *did* have calibrated cumulative-mean evidence + margin + stability (`Confirmation.kt`, `theta_conf=-1.2`, `theta_margin=0.3`, `k_stability=3`, `temperature=0.6262`). **None of this applies to the live path.** `[CONFIRMED-CODE]` — `recognition_config.json` is read only by legacy classes and by `RecognitionActivity.cameraAnalysisSize()` (which is called only from the unreachable legacy `rebindCamera` branch).

### E.3 Preprocessing correctness

- DWPose normalization uses ImageNet mean/std in RGB order on RGBA frames; hand crop divides by 255. These match common DWPose / MediaPipe-hand conventions and are covered by parity fixtures (`PerceptionVNextMathTest`, `RecognitionV2JvmParityTest`, instrumented parity tests). I found **no evidence of a color-order, normalization or orientation error**. I could not independently verify the C++ source against the shipped binary (F-006).
- Coordinates are normalized by source width/height and short side consistently with the Python `raw.v1` contract; deltas use *each frame's own* dimensions (`oldScale`), so a mid-session geometry change would not corrupt deltas — but the native preprocessor would reject it first (F-004).

### E.4 Accuracy evidence — what exists and what does not

| Claim | Evidence | Label |
|---|---|---|
| WORD offline 236-class accuracy | Parity and training docs exist; Gate-4A-1C: with oracle active-sign isolation Top-1 improved **2/10 → 7/10** on 10 retained live attempts (5 became correct, 0 became wrong). Phase 4A formally closed as `RETURN_TO_PHASE_3`; **unseen-signer generalization is recorded as unsolved**. | `[REPO-REPORTED]`, n = 10 |
| WORD live accuracy | A fixed HELLO→HOME→TABLE→HELLO smoke: 4/4 intended signs correct, supervisor-observed, one signer. The same doc states "not independent population accuracy". | `[REPO-REPORTED]`, n = 4 |
| WORD false positives | 3 documented unwanted commits in two short sessions (open-hand→HELLO; HOSPITAL1 while seating; STAND2 during movement); ≈2-minute still-scene soak had 0 commits. **No false-positive rate is estimated** (the doc says so). | `[REPO-REPORTED]` |
| Legacy model quantization drift | `model_manifest.json`: per-frame argmax agreement Keras vs TFLite **0.776**, max |Δp| 0.795, clip top-1 0.63 (this is the dead model). | `[CONFIRMED-CODE]` (file) |
| FINGERSPELL | V2.1 epoch034: pooled phone no-SPACE CER **40.23%**, letter recall **63.16%**, exact full strings **6/512**, frozen-42 single-word phone CER 44.63%. Selection used DEV-A repeatedly; DEV-B shares 15 official DEV signers and is "post-lock confirmation, not a fresh unseen-signer population". TEST sealed. | `[REPO-REPORTED]` |
| Cross-signer, end-to-end, live, phrase-level (the project's own headline metric) | **Does not exist.** Handoff explicitly says "qualified-signer live reliability evaluation" is unfinished. | `[EVIDENCE GAP]` |

**Therefore no claim that WORD or FINGERSPELL accuracy is "high" or "low" in the field can be supported.** What *can* be said: the architecture lacks a reject path, offline fingerspelling error rates are large, and the only live evidence is a handful of supervised attempts.

### E.5 Handling of hard conditions

| Condition | Handling in code |
|---|---|
| Multiple signers / two people | Single-pose network; behavior with two people not specified `[EVIDENCE GAP]`. |
| Both hands | Two hand slots (L/R) handled. |
| Partial / occluded hand | Hand dropped unless ≥18/21 joints valid and presence ≥ 0.50. |
| Distance | Whole-frame 256×192 pose input → small subjects degrade `[SUSPECTED]`. |
| Motion blur / low light | Fixed 15 fps AE target `[SUSPECTED]`; no exposure/lighting quality gate. |
| Different backgrounds | No explicit handling; evidence gap. |

---

## F. Performance Assessment

### F.1 Measured values (all `[REPO-REPORTED]`, target Xiaomi M2101K7AG / SM6150 / Android 12)

| Metric | Value | Source |
|---|---|---|
| Project hard floor | ≥ 15 fps | `runtime-constraints.md` |
| P7D-R2 native compute (perception only) | p95 = 25.13 ms; 40.7 loops/s | `runtime-constraints.md` |
| P7E fixed-15 integrated run | capture 15 fps vs analyzer-completed **14.88 fps → gate failed**; "do not round upward" | same |
| S2-R2 normal app | ≈11 fps instantaneous HUD; **5–7 fps in short transition logs** | `APPHEAR_S2_R2_REAL_APP_INTEGRATION_01.md` |
| Legacy RU-D10 runs | 9.6–12.7 processed fps (legacy path) | `RU_D10_STABILIZATION_PLAN.md` |
| Memory | PSS ≈ 272 MB flat over ≈ 2 min | S2-R2 integration doc |
| Debug APK / asset payload | APK ≈ 789 MiB, payload ≈ 737 MiB (Original-words build) | `docs/team-research-findings.md` |
| Original catalog integrity check | 5.1 s off-UI on the Xiaomi | same |

Not measured anywhere I found: end-to-end latency (camera frame → displayed gloss), CPU utilization, battery/thermal behavior, long-duration (≥ 30 min) stability, p50/p95 of commit-time inference. `[EVIDENCE GAP]`

### F.2 This audit's own measurements

None on a device. See §Limitations.

### F.3 Optimization opportunities (supported by evidence; none implemented)

1. Enable/evaluate the existing **parallel two-hand refinement** (`RECOGNITION_V3_PARALLEL_HANDS`); the repo has a gated A/B harness and a `CurrentFrameHandPair` unit test. Expected benefit: removes one serial 224×224 inference on two-hand frames.
2. **Move commit-time recognition off the camera thread** (post the materialized window to a worker; hold UI state until it returns). The commit stall currently costs frames at exactly the moment the next sign may begin.
3. **Reuse ONNX output buffers / use `OrtValue` direct buffers** to avoid per-frame nested-array allocation `[SUSPECTED benefit]`.
4. Measure before changing: p50/p95 per stage already logged under `RECOGNITION_V3_PROFILE_ENABLED` ("AppHearV3" JSON, first 240 frames).
5. Evaluate INT8 or smaller pose input only with the repo's parity gates; the repo's rule "never drop feature blocks" applies to the *features*, not to model precision.
6. Remove dead code and the legacy MediaPipe dependency to cut APK size (≈ 17 MB of dead model/backup assets — 13.6 MB MediaPipe `.task` files, 0.23 MB `streaming.tflite`, 2.1 MB shadow models, ≈1.7 MB `_backup_*` — plus the MediaPipe native libraries, whose size I did not measure) — size, not fps.

---

## G. Security and Reliability Assessment

### G.1 Positive controls (confirmed)

- No credentials, keystores or key-pattern strings found in tracked text files (regex scan for `AIza…`, `gsk_…`, `sk-…`, JWT, PEM headers: no hits outside code that *reads* a key). `local.properties`/`gradle.properties` for the Android app are untracked (`gradle.properties.example` only).
- Supabase client enforces `https`, rejects userinfo/query/fragment in the base URL, disables redirects ("never forward bearer headers"), bounds response size, validates the publishable-key shape.
- Account session is AES-256-GCM, Android-Keystore-backed, with AAD bound to the backend; excluded from cloud backup and device transfer.
- LLM fallback base URL must be `https` (`require` in Gradle); `LLM_FALLBACK_*` and Gemini keys are blanked in the **release** `BuildConfig`.
- Main manifest exports only the launcher activity; `RecognitionActivity` is `exported=false` (explicit `tools:replace` in debug).
- Camera and recognition teardown is careful (§D.1). Model/asset drift fails closed.

### G.2 Concerns

| # | Concern | Label |
|---|---|---|
| F-005 | `ELEVENLABS_API_KEY/VOICE_ID/MODEL_ID` and Supabase URL/key are set in `defaultConfig` → compiled into **release** `BuildConfig` whenever the property/env var is present. A third-party paid-service key in an APK is recoverable. The repo is **public**, and the handoff itself says "public production builds cannot safely distribute local embedded service keys". (Supabase anon/publishable keys are designed to be public; the ElevenLabs key is not.) | CONFIRMED-CODE |
| F-005b | The signer's recognized sentence is posted to ElevenLabs (TTS) and, in debug flows, to Google/Groq (Context Assist). No consent/disclosure UI was found in the files I read. | CONFIRMED-CODE / UI not exhaustively read |
| F-006b | `android:allowBackup="true"` in the main manifest; only the account prefs are excluded. Debug FINGERSPELL writes `fingerspelling_sessions/session_*.json` (decoded text) and `fingerspell_word_cadence.json` into `filesDir` without a retention bound. Debug-only. | CONFIRMED-CODE |
| — | Release: `isMinifyEnabled=false`; no `signingConfig`; no R8 rules beyond defaults. | CONFIRMED-CODE |
| — | Dependency vulnerabilities not scanned (no network SCA run). | EVIDENCE GAP |
| — | Many debug-only research activities are `exported="true"`; harmless in release (not merged) but they accept intents on any debug build installed on a shared device. | CONFIRMED-CODE |

### G.3 Resource cleanup

- Camera/native resources: correct (§D.1).
- `AppHearSpeechPlayer`: a TTS result that arrives after being superseded (`request != requestId`) is never deleted from `cacheDir` (temp `.mp3` leak). Minor. `[CONFIRMED-CODE]`
- Frame buffers on the live path are native direct buffers reused across frames; `ImageProxy` is closed in `finally`. `[CONFIRMED-CODE]`
- Legacy path (dead) only releases `Bitmap`/`MPImage` when the *default-off* `RU_D10_OBSERVATION_CONTINUITY` flag is set — a latent leak if revived.

### G.4 Error recovery

- Startup failure → explicit error UI; **no** fallback ("No legacy backend fallback").
- Mid-session analyzer exception → unbinds camera and shows "Causal recognition stopped"; no auto-recovery (F-004).
- Network failure → LLM/TTS fall back (hedged calls, Android TTS), but with long waits (F-012).

---

## H. Testing Assessment

### H.1 What exists

| Layer | Count | Notes |
|---|---:|---|
| JVM unit tests | **336** `@Test` in 68 files | Covers S2 decoder (`PhoneCausalCoreTest`), raw→V2 mapping/parity, planners, fingerspell decoders/policies, Context Assist, grounding validator, account security, text-to-ASL manifests. |
| Instrumented tests | 64 `@Test` in 38 files | Device parity for S2/Recognition-v2/hand-refiner/DWPose; camera input/switch; owner/coordination; account security. |
| Python tests | 922 functions / 163 files | Pipeline stages, confirm, causal skew, E6 experiments, fingerspell, handoff verifier. |

**Executed in this audit `[CONFIRMED-RUN]`:** JVM unit tests on an isolated scratch copy of `android/` (so the repository stayed untouched). First run: **336 tests, 332 passed, 4 failed** — all four are `SentenceAssistEvalTest` failing with `NoSuchFileException` because the test reads `../../eval/sentence_assist/cases_v1.jsonl` and my scratch copy omitted `eval/`. After copying that folder, a targeted re-run of the class passed (`BUILD SUCCESSFUL`). Net: **336/336 pass when the repo layout is intact** (the two results come from two Gradle invocations, not one). Python tests, instrumented tests and release builds were **not** run.

### H.2 Critical gaps

1. `Candidate01FrameAnalyzer` (the live analyzer), `PerceptionVNextNativePreprocessor` and the JNI library have **no JVM test** and the analyzer has **no instrumented test**; geometry-change, timestamp-regression and exception paths are untested (cf. F-004).
2. No replay/regression test that feeds recorded frames through the *real* analyzer and asserts commits (the repo has recorded-transition JVM tests at the decoder level only).
3. No test asserts behavior on non-sign input (the F-001 failure mode). Research negatives exist offline (E4/E6 gating studies) but are not wired to the live path.
4. `AppHearSpeechPlayer`, `RecognitionActivity` lifecycle (rotation, background/foreground, camera-switch race) have no JVM test; 11 instrumented tests reference the activity.
5. No CI → none of the above runs automatically. One JVM test depends on the repo-root layout (`../../eval`), which breaks silently if `android/` is built in isolation.
6. No performance regression test (fps/latency/memory) and no long-run soak.

### H.3 Recommended repeatable benchmark suite

Metrics (all reported per signer **and** pooled; latency as p50 **and** p95; cross-signer held-out only, per `context/eval-protocol.md`):

| Layer | Metrics |
|---|---|
| Detection (S2-R2 + decoder) | Sign-onset precision / recall / F1 vs human boundaries; missed-sign rate; **false-event rate per minute of non-sign video** (idle, talking, adjusting seat, gesturing, hand-on-face, drinking); onset/offset error (ms); merged-episode rate across consecutive signs |
| Recognition | Top-1/Top-5 on held-out signers; per-class precision/recall/F1; confusion matrix with the repo's confusable pairs (e.g. BYE/YES/NO, SORRY/GOOD, KNOW/HELLO); calibration (ECE, NLL) |
| End-to-end | Signed-phrase accuracy / WER on scripted phrase lists; false-commit rate; correct-but-dropped rate; commit latency (end of sign → displayed gloss) |
| Open-set | AUROC and FPR@95%TPR for accept/reject using max-prob, margin and entropy on out-of-vocabulary signs + non-sign segments |
| Runtime | Camera fps, processed fps, per-stage ms (p50/p95), commit-time stall, dropped frames, PSS/Java/native heap growth, thermal state, battery %/hour — on ≥ 2 device tiers, ≥ 30 min soak |
| Regression | Frozen recorded corpus replayed through the real `Candidate01FrameAnalyzer` in an instrumented test, asserting exact event/gloss sequences and bounds on false events |

---

## I. Findings and Severity

Ordering is by severity, then impact. Labels per the key at the top.

### CRITICAL

**F-001 — Unconditional top-1 commit; no reject path; false words on non-sign motion**
1. **ID/Severity:** F-001 / CRITICAL (for a product whose stated goal is *minimal false recognition*)
2. **Files:** `perceptionvnext/PhoneCausalCore.kt` (`PhoneNewSignAdmission`, `PhoneSignAdmissionPolicy.PASS_THROUGH`, `PhoneCausalEventProducer`); `perceptionvnext/PhoneProductionSession.kt` (`consume`); `perceptionvnext/PhoneRecognitionConfiguration.kt` (`decoderConfig`).
3. **Observed behavior:** Any ACTIVE run of ≥ 133 ms followed by ≥ 267 ms POST emits an event; the recognizer always returns a class; `top5.first()` is appended to the sentence. Repo-recorded incidents: open raised hand → HELLO; seat adjustment → HOSPITAL1; ordinary movement → STAND2.
4. **Evidence:** Code above `[CONFIRMED-CODE]`; incidents in `context/recognition_upgrade/APPHEAR_S2_R2_REAL_APP_INTEGRATION_01.md` `[REPO-REPORTED]`; the 2026-09-28 report states "No confidence, hand/body or recognized-class gate". Rate over a population: `[EVIDENCE GAP]` (the source doc says it does not estimate one).
5. **Root cause:** A 236-way softmax has no "none" class and the admission seam was deliberately left pass-through ("this milestone remains pass-through").
6. **Impact:** Spurious words appear in the sentence and are spoken by Hear; erodes trust; the correct-commit/false-commit trade-off is currently uncontrolled and unmeasurable.
7. **Recommended solution:** (a) First *measure*: build the non-sign negative corpus + replay harness (§H.3) to get a false-events-per-minute baseline. (b) Then add an **abstain stage** at the existing admission seam and/or after recognition (max-prob/margin/entropy threshold chosen on held-out signers at a fixed FP rate; hand-visibility and minimum-motion gates). The repo already has offline open-set work (E6_3 / E5_I) and a documented confusion registry to start from. Ship behind a flag with a rollback.
8. **Dependencies/risks:** Thresholds tuned on one signer repeat the v2 "confirmation leak" the project already documented (dropping correct signs). Must be calibrated cross-signer. Changing the decoder touches protected components (S2-R2 lifecycle, admission) — needs an explicit, versioned gate per `team-current-state`.

### HIGH

**F-002 — Live throughput is below the ≥15 fps floor; strictly serial pipeline**
1. F-002 / HIGH
2. `perceptionvnext/Candidate01FrameAnalyzer.kt` (`analyze`), `RecognitionActivity.kt` (`bindPhoneCamera`), `PerceptionVNextRunners.kt`.
3. ≈11 fps HUD; 5–7 fps in transitions `[REPO-REPORTED]`; P7E integrated 14.88 fps failed the project gate `[REPO-REPORTED]`.
4. Code: five network invocations (pose, left hand, right hand, S2, and at commit V2) executed sequentially under one `@Synchronized` call on a single-thread executor; AE range fixed at 15.
5. Root cause: sequential architecture + CPU-only budget on SM6150; "runtime debt is parked" per the repo.
6. Impact: Per `runtime-constraints.md`, < 15 fps makes ≈200 ms signs unresolvable; also lengthens observation gaps that reset re-arm timing; fast signs are most affected.
7. Solution: Profile first (existing flags); then evaluate parallel hands, off-thread commit inference, buffer reuse, and lower-cost pose input — each A/B-gated against the parity fixtures. Surface fps honestly (F-009).
8. Risks: Any change that alters the observation stream changes S2/V2 inputs — the repo's train/serve parity rules apply; cadence-sensitive models were trained on specific cadences.

**F-003 — No cross-signer, end-to-end field accuracy evidence; fingerspelling weak**
1. F-003 / HIGH
2. Repo-wide (evidence); `docs/team-research-findings.md`; `context/recognition_upgrade/*`.
3. WORD: n=10 oracle-isolation study and n=4 live smoke. FINGERSPELL: CER 40.2% pooled phone, exact strings 6/512; DEV-B not a fresh signer population; TEST sealed.
4. See §E.4.
5. Root cause: the live evaluation protocol the repo itself mandates has not been executed; no qualified signer available (per handoff).
6. Impact: cannot claim product accuracy; cannot choose thresholds (F-001) defensibly.
7. Solution: Execute the qualified-signer protocol (§H.3) on ≥ 5 held-out signers with the real app build; open the sealed TEST only once, for final reporting.
8. Risks: Recruiting signers; per-device variance; the repo forbids accessing sealed data during development.

**F-004 — One exception permanently stops recognition for the session**
1. F-004 / HIGH
2. `perceptionvnext/Candidate01FrameAnalyzer.kt` (`analyze`, `failed`); `PhoneProductionSession.consume`; `PhoneCausalCore.kt` (`require(...)` guards); `PerceptionVNextNativePreprocessor.kt`.
3. `catch (Throwable) { failed = true; onFailure(error) }`; every later frame returns immediately; `RecognitionActivity` unbinds the camera and shows "Causal recognition stopped".
4. `[CONFIRMED-CODE]`. Triggers include `APP_PHONE_NON_CHRONOLOGICAL_SOURCE_TIMESTAMP`, `APP_PHONE_SOURCE_INDEX_DISCONTINUITY`, `PHONE_SEGMENTATION_NONFINITE_FEATURE`, `VNEXT_NATIVE_CAMERA_GEOMETRY_CHANGED`, any ONNX/TFLite exception. Frequency in the field is `[EVIDENCE GAP]`. Exposure is plausible because `setTargetResolution` does not pin the delivered size across devices/lens switches (`[SUSPECTED]`).
5. Root cause: fail-fast by design, no recovery path or retry/reset policy.
6. Impact: A single transient glitch ends recognition until the user re-enters the screen; poor fit for "continuous operation".
7. Solution: Classify errors; for recoverable ones (timestamp regression, geometry change, non-finite feature) reset the temporal session and continue, with a bounded retry count and telemetry; keep fail-stop for model/asset integrity errors.
8. Risks: Silent recovery could mask real contract violations — keep counters and debug-visible logs.

**F-005 — Service keys compiled into release `BuildConfig`; conversation text sent to third parties**
1. F-005 / HIGH
2. `android/app/build.gradle.kts` (`defaultConfig`: `ELEVENLABS_*`, `SUPABASE_*`); `ui/speech/AppHearSpeechPlayer.kt`.
3. If `APPHEAR_ELEVENLABS_API_KEY` exists at build time, release APKs embed it and send `xi-api-key` from the device.
4. `[CONFIRMED-CODE]`; handoff acknowledges the issue.
5. Root cause: keys injected in `defaultConfig`, only the Gemini/LLM keys are blanked for release.
6. Impact: Extractable paid-service key; unauthorized use/billing; privacy exposure of signed/spoken sentences.
7. Solution: Blank all non-public keys in the release block now; for production, route TTS/LLM through a server you control (short-lived tokens), or use on-device TTS only; add disclosure/consent text.
8. Risks: Product decision (cloud TTS quality vs privacy); needs backend.

**F-006 — Native library: 4 KB-aligned, prebuilt, not reproducible from the Gradle project**
1. F-006 / HIGH (release/distribution)
2. `android/app/src/main/jniLibs/arm64-v8a/libperceptionvnext.so`; `src/debug/cpp/perception_vnext_preprocess.cpp`; `app/build.gradle.kts` (no CMake/`externalNativeBuild`).
3. ELF `PT_LOAD` alignment = 4096 (read directly from the binary: `[4096]`); the source is under `debug/`, not compiled by Gradle. The two debug research `.so` files are also 4096-aligned.
4. `[CONFIRMED-CODE]` for alignment and build-setup absence. Third-party `.so` (TFLite 2.16.1, MediaPipe 0.10.14, ORT 1.22.0) alignment is `[EVIDENCE GAP]` (not inspected); older TFLite/MediaPipe builds are known not to be 16 KB-aligned, but I did not verify these versions.
5. Root cause: binary checked in as an artifact; no reproducible native build.
6. Impact: With `targetSdk 36`, Google Play policy (as I understand it; verify the current rule and dates) requires 16 KB page-size compatibility for apps with native code; there is also no way to rebuild/patch the JNI preprocessor from source with this repo. The binary↔source correspondence is unverifiable (a supply-chain/provenance gap).
7. Solution: Add a Gradle-driven CMake build (NDK r28+, `-Wl,-z,max-page-size=16384`), pin NDK, check the built `.so` hash against the current one for bit-parity of behavior (the repo already has JNI parity fixtures), then bump TFLite→LiteRT / MediaPipe only if needed.
8. Risks: Numeric drift if compiler flags change — gate with the existing exact-parity tests. The repo's "Candidate01 assets are frozen" policy requires an explicit decision.

### MEDIUM

**F-007 — Governing documents describe a pipeline that is not live**
- Files: `AGENTS.md`, `context/architecture.md`, `context/runtime-constraints.md`, `context/project-overview.md` (read). `context/library-docs.md`, `eval-protocol`-adjacent files and the rest of the AGENTS.md reading list were not read in full.
- Observed: These instruct agents to treat MediaPipe + normalized-258 + `streaming.tflite` as production and state rules (e.g., "No GPU delegate", "S4 byte-parity with pipeline/features") whose subject code is unreachable. The October-9 notices partly correct this but leave the original text.
- Evidence: `[CONFIRMED-CODE]` (`start()` loads only `PhoneProductionSession`; "No legacy backend fallback"). The repo's own `team-current-state` says the same.
- Impact: Agents/engineers optimize or "protect" the wrong code; the 662 KB `progress-tracker.md` and 143 KB `feature-schema.md` are unreadable as a current spec.
- Fix: One short, authoritative `CURRENT_ARCHITECTURE.md` and move history to `docs/archive/`.
- Risk: None functional.

**F-008 — Unreachable legacy pipeline ships in the app**
- Files: `pipeline/FrameAnalyzer.kt`, `IndependentClockFrameAnalyzer.kt`, `LandmarkerBundle.kt`, `AdaptiveController.kt`, `LowFpsMonitor.kt`, `pipeline/recognition/*`, `pipeline/features/*`, `pipeline/diagnostics/*` (≈2.5–3 k lines; note `SentenceBuilder` in `pipeline/recognition/` **is** still used by the live session), plus MediaPipe Tasks Vision, `mediapipe/*.task` (13.6 MB), `streaming.tflite`, 3 shadow models (2.1 MB), 10 `_backup_*` asset dirs.
- Evidence: `LandmarkerBundle.create` and `RecognitionPipeline.load` have zero callers; `RecognitionActivity.landmarkers` and `.recognizer` are never assigned, so `rebindCamera` returns at `val bundle = landmarkers ?: return`. `[CONFIRMED-CODE]` (verified with a binary-safe grep because of F-010).
- Impact: APK bloat; maintenance and security surface; 336 unit tests include many for dead code (S4SkewTest, SigningHandGateTest, ConfirmationTopKTest, PostCommitRearmTest…) which gives *false assurance* about the live path.
- Fix: Move to a `legacy/` module or delete after a tagged archive; remove dependency/assets; re-point parity tests to the live path.
- Risk: Some debug research activities (`p6c`, `p7*`) may import shared helpers — check before removal.

**F-009 — No user-visible degraded mode on the live path**
- Files: `Candidate01FrameAnalyzer.kt` (builds `FrameResult(poseEveryN = 1, lowFpsActive` default `false)`); `RecognitionActivity.onFrame`.
- Evidence: `maxedOut = r.poseEveryN >= 4 && …` and `struggling = … r.lowFpsActive` can never be true for live frames. `[CONFIRMED-CODE]`
- Impact: Contradicts `runtime-constraints.md` ("enter degraded mode and report it"); users on slow devices (the repo specifically mentions an "itel" device) get silent misses.
- Fix: Compute low-fps state from `FpsTracker` in the live analyzer and set `lowFpsActive`; show the existing banner.

**F-010 — `RecognitionActivity.kt`: god class, non-UTF-8, CRLF**
- Evidence: 1,512 lines, all CRLF; contains byte `0x85` (CP-1252 "…") making the file invalid UTF-8; `file` reports "Non-ISO extended-ASCII"; the editor/refactor tools used here refuse to edit it. Plain `grep` silently returns **nothing** for any pattern in it unless `-a` is used — I was misled until I diagnosed this. `[CONFIRMED-RUN]`
- Impact: Hidden from search/lint/diff tools; high merge-conflict risk; mixed concerns.
- Fix: Convert to UTF-8/LF in a pure-encoding commit; then split (camera binder, fingerspell UI, conversation flow, legacy A1/RU-D1).

**F-011 — Test and CI gaps on the live path**
- See §H.2. No CI at all. The live analyzer, JNI preprocessor and speech player are untested; no non-sign negative test.

**F-012 — "Hear" can wait up to ~65 s before falling back to on-device TTS; temp-file leak**
- File: `ui/speech/AppHearSpeechPlayer.kt`. `CONNECT_TIMEOUT_MS = 20 s`, `READ_TIMEOUT_MS = 45 s`; fallback only after the exception. A superseded response is never deleted from `cacheDir`.
- Impact: Poor offline/slow-network UX for the core "speak the sentence" action.
- Fix: Race Android TTS vs cloud with a ≈2 s cutoff, or check connectivity; delete orphaned temp files.

**F-013 — Hand-detection fragility from pose-first ROI and fixed 15 fps exposure** `[SUSPECTED]`
- Mechanism: ROI from DWPose-t keypoints at 256×192; refiner requires ≥18/21 valid joints and presence ≥ 0.50; AE locked to 15 fps. The repo's own ROI-recovery studies treat missed ROI as a real failure class. No measured hand-detection hit rate vs distance/blur/lighting exists here. Not a confirmed bug.
- Verify with: hit-rate by distance bins and illumination on the benchmark corpus (§H.3) before any change.

**F-014 — Commit-time inference on the camera thread; shared executor** `[CONFIRMED-CODE] structure / [EVIDENCE GAP] duration`
- Materialize + Recognition-v2 invoke run inside `analyze`; the same single-thread `cameraExecutor` also receives fingerspell control tasks (`pause`, `select`, `clear`, `holdForReview`), which queue behind a full frame.
- Fix: dedicated recognition worker; control-plane tasks on a separate handler thread.

**F-015 — Build-flag matrix and release-config drift risk**
- `app/build.gradle.kts` defines ≈35 properties with chained `require`s and a hand-copied all-false release block; adding a debug flag requires editing two blocks. The default build (no flags) differs materially from the documented "working" build, which needs a long property list (`aslOriginalWords`, `fingerspell`, `fingerspellContinuous`, `contextPhraseAssist`, …). Build reproducibility for a new engineer depends on untracked `gradle.properties` and an artifact path (`../../artifacts/fingerspelling_android_01`). Fresh-clone build without these was **not tested**.
- Fix: a typed `AppFlags` source of truth and a checked-in `gradle.properties.debug-full`.

### LOW

| ID | Finding | Evidence |
|---|---|---|
| F-016 | User-visible string "Initializing recognition**�**" — the source contains an invalid byte (0x85) where `…` was intended, so the compiler substitutes U+FFFD. Not visually confirmed on a device. | `RecognitionActivity.kt` byte 47246 `[CONFIRMED-CODE]` |
| F-017 | Python environment not reproducible: `requirements.txt` unpinned, no lockfile; local interpreter is 3.14.6 (project says ≥ 3.11; TensorFlow support for 3.14 not verified); 8 root `.ps1` scripts hard-code `F:\ASL DATASET\...`; Python tests not run here (no `pytest`/TensorFlow installed). | `requirements.txt`, `pyproject.toml`, `08_…ps1` `[CONFIRMED-CODE]` |
| F-018 | Startup hashes the 22 MB ONNX every launch and copies it to `codeCacheDir` on first run; whole recognizer asset is read into memory twice for hashing. Off main thread; cost unmeasured. | `PerceptionVNextRunners.kt`, `RecognitionV2LiveRecognizer.kt` |
| F-019 | Repo hygiene: large binaries without Git LFS (largest tracked 61.8 MB GLB, 38.7 MB, 37.8 MB, 32.5 MB), 15 remote branches, root clutter (`memory.md` 94 KB, handoff `.md` files, `.ps1`), mixed CRLF/LF with `-text` attributes for byte-identity. `.git` is 177 MB. | `git ls-files`, `.gitattributes` |
| F-020 | `setTargetResolution` is deprecated in CameraX 1.3 (the code already imports `ResolutionSelector`); `FrameResult.isFrontCamera` is hard-coded `true` by the analyzer and patched by the activity. | `RecognitionActivity.kt`, `Candidate01FrameAnalyzer.kt` |
| F-021 | `FeatureFlags.PROFILE_STAGES = true` is a `const` whose comment says "Off by default" (legacy only). | `FeatureFlags.kt` |

---

## J. Prioritized Optimization Roadmap

Complexity: S ≤ 2 d, M ≈ 1–2 wk, L > 2 wk. Nothing below has been started.

### Priority 0 — Critical defects and blockers

| # | Item | Complexity | Expected benefit | Depends on | Verification |
|---|---|---|---|---|---|
| P0-1 | Blank all non-public keys in the release block; document secure provisioning (F-005) | S | Removes extractable-key risk | none | Build release; `unzip -p … BuildConfig` / `apkanalyzer` shows empty strings |
| P0-2 | Build the **non-sign negative corpus + live-analyzer replay harness** and publish a false-events/minute baseline (F-001 measurement) | M | Turns F-001 from anecdote to a number; prerequisite for any threshold | recorded phone video of held-out people | Reproducible metrics table; replay is deterministic across 3 runs |

### Priority 1 — Detection and recognition reliability

| # | Item | Complexity | Benefit | Depends on | Verification |
|---|---|---|---|---|---|
| P1-1 | Abstain/reject stage at the admission seam + post-recognition confidence/margin gate, flagged (F-001) | M–L | Fewer spurious words | P0-2, calibration on held-out signers | FP/min ↓ at fixed correct-commit rate; correct-but-dropped reported |
| P1-2 | Recoverable-error policy in `Candidate01FrameAnalyzer` (F-004) | S–M | Session survives transient glitches | none | Fault-injection tests: timestamp regression, geometry change, NaN |
| P1-3 | Pin analysis geometry (`ResolutionSelector`) and re-verify preprocessor assumptions (F-004/F-020) | S | Removes a latent trigger | device matrix | Instrumented test across ≥ 3 devices/lenses |
| P1-4 | Surface degraded mode from live `FpsTracker` (F-009) | S | Honest UX on slow phones | none | Throttled-CPU test shows banner |
| P1-5 | Quantify hand-detection hit-rate vs distance/blur/light (F-013) | M | Decides whether ROI/exposure work is needed | P0-2 corpus | Hit-rate table with CIs |

### Priority 2 — Accuracy improvements

| # | Item | Complexity | Benefit | Depends on | Verification |
|---|---|---|---|---|---|
| P2-1 | Run the qualified-signer, held-out, end-to-end evaluation (F-003) | L | The first real accuracy number | signers, P0-2 | Per-signer + pooled Top-1/phrase accuracy, open TEST once |
| P2-2 | Targeted work on documented confusable pairs and new-signer generalization per `RETURN_TO_PHASE_3` | L | Cross-signer gain | P2-1 error analysis | Held-out confusion matrix |
| P2-3 | Revisit boundary behavior on consecutive signs (`A_REARM_LIFECYCLE_BLOCK`, `B_NO_INTERSIGN…`) with the already-built A/B diagnostics | M | Fewer merged/blocked signs | A/B capture | Evaluator labels A/B/C/D shrink |

### Priority 3 — Performance and resource optimization

| # | Item | Complexity | Benefit | Depends on | Verification |
|---|---|---|---|---|---|
| P3-1 | Per-stage p50/p95 on 2 device tiers using existing profile flag (baseline) | S | Evidence for all below | device | Table in repo |
| P3-2 | Off-thread commit inference; separate control executor (F-014) | M | Removes post-commit frame stall | P3-1 | Frame gap p95 around commits |
| P3-3 | Parallel hand refinement A/B (existing flag) (F-002) | S–M | Up to one fewer serial inference on 2-hand frames | P3-1 | fps ↑ with parity unchanged |
| P3-4 | ONNX buffer reuse / allocation audit (Android Studio profiler) | M | Lower GC pauses | P3-1 | Allocation rate ↓, no output drift |
| P3-5 | Soak + thermal + battery test (≥ 30 min) | S | Fills F.1 gaps | device | PSS slope, throttling timeline |
| P3-6 | TTS race/timeout, orphan-file cleanup (F-012) | S | Faster, offline-friendly Hear | none | Airplane-mode latency < 2 s |

### Priority 4 — Architecture and maintainability

| # | Item | Complexity | Benefit | Depends on | Verification |
|---|---|---|---|---|---|
| P4-1 | Convert `RecognitionActivity.kt` to UTF-8/LF (encoding-only commit), then split (F-010) | S then M | Tool-visible, reviewable code | none | `git diff --ignore-all-space` empty for logic; `grep` finds strings |
| P4-2 | Archive/remove the legacy MediaPipe path, assets, dependency (F-008) | M | −≈17 MB assets (plus MediaPipe native libs), smaller attack surface | P4-1 | APK size ↓; all remaining tests green |
| P4-3 | Write `CURRENT_ARCHITECTURE.md`; archive stale context (F-007) | S | Correct onboarding | none | New engineer reproduces flow from doc |
| P4-4 | Reproducible native build with 16 KB alignment (F-006) | M | Play-ready, auditable | NDK, parity tests | `readelf`: align 0x4000; parity fixtures identical |
| P4-5 | Typed flag source of truth; release flag generator (F-015) | M | Fewer drift bugs | none | Single place to add a flag |

### Priority 5 — Additional testing and long-term improvements

| # | Item | Complexity | Benefit | Verification |
|---|---|---|---|---|
| P5-1 | Add CI: JVM tests + lint + build debug/release on every PR (make the `eval/` path layout explicit) | S–M | Regressions caught | Green pipeline |
| P5-2 | Instrumented tests for the live analyzer/preprocessor/speech player/lifecycle | M | Closes H.2 | Device farm or local emulator runs |
| P5-3 | Python env lockfile + container/`uv`; replace `.ps1` abs paths with a configurable root | S–M | Reproducible training | Fresh-machine run |
| P5-4 | Dependency vulnerability scan (OSV/Gradle dependency-check) | S | Closes G.2 gap | Report |
| P5-5 | Decide the future of `apphear-react/` (RN01 recognizes nothing) | S | Scope clarity | Written decision |

---

## Limitations and unverified areas

- **No device was used.** One arm64 emulator (`sdk_gphone16k_arm64`, Android 17, 16 KB-page image) was connected; AppHear was **not** installed and no fps/latency was measured. An emulator with a virtual camera is not representative of the SM6150 target, so I did not fabricate numbers from it. (It would be a convenient place to check the 16 KB behavior from F-006 once a build is installed.)
- **Not read in depth** (read at survey level or not at all): `ui/texttoasl/*` (avatar player), `domain/texttoasl/*`, `sentenceassist/*` internals, `conversation/*`, `contextassist/*` beyond the Gemini client, `ui/profile/*`, `ui/settings/*`, fragments/navigation XML, `p6c/p7*/p8*` debug activities, `FingerspellRuntime`/`ContinuousFingerspell` beyond threading/policies, the entire `pipeline/`, `model/`, `eval/`, `tools/` Python bodies, `asl recorder/`, `apphear-react/`, and ~660 KB of `progress-tracker.md`. The repo has ≈287 Kotlin and ≈776 Python files; this audit traced the live camera→commit path and the highest-risk surfaces rather than every file.
- **Tests:** only JVM unit tests were executed (on a scratch copy; see §H.1). Python, instrumented and release builds were not run; no dependency vulnerability scan was run.
- All FPS/latency/memory/accuracy figures are the repository's own measurements; I did not verify their methodology.
- Third-party native libraries' 16 KB alignment, the C++ source↔binary correspondence, and what a fresh clone needs to build were not verified.
- Git history is short (50 commits; history appears squashed), so "recent implementation history" is limited to that.

## Positive observations (to keep)

Hash-pinned model/asset contracts with fail-closed loading; exact-parity fixtures from Python to JVM to device; monotonic-timestamp and generation guards against stale async results; careful native-teardown ordering; `KEEP_ONLY_LATEST` backpressure; native (not Bitmap) preprocessing; encrypted account storage and HTTPS/redirect hardening; honest documentation of negative results and open limitations in the experiment reports.
