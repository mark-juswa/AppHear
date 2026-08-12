# Current Pipeline Audit

**Purpose:** Evidence-based record of the recognizer that exists on 2026-07-25.
**Scope:** Production Android, offline data/training, deployed assets, measured results.
**Status:** VERIFIED AUDIT. **Last updated:** 2026-07-25.

## Verified End-To-End Path

| Stage | Current implementation and I/O | Limitation | Disposition |
|---|---|---|---|
| S0 capture | `RecognitionActivity.kt`: CameraX `ImageAnalysis`, RGBA8888, target 480x360, `KEEP_ONLY_LATEST`; `FrameAnalyzer.kt` converts to bitmap, rotates upright, drops while busy | Bitmap conversion/rotation; timestamps are not passed into recognition | Keep CameraX; replace frame envelope |
| S1/S2 | `LandmarkerBundle.kt`: Hand + pose Tasks in parallel, `RunningMode.IMAGE`; GPU selected in current config; hand every processed frame, pose every 2 with last-pose hold | Stateless detector cost dominates; held pose is temporally stale | Evaluate VIDEO/LIVE_STREAM and explicit timestamped cadence |
| adapter | `LandmarkAdapter.kt`: pose `[33,4]`, hands `[2,21,3]`, handedness-slotted, absent = NaN | Hand score/mask and timestamps are discarded before model | Replace experimental contract |
| S4 | `SessionNormalizer.kt` + `S4Features.kt`: torso-center, shoulder-scale, roll, manual/session handedness; NaN -> 0 | Zero conflates missing with valid zero; no motion/bones/angles/relations | Keep v3.0 frozen; create new multimodal schema |
| S5 | `SigningDetector.kt`: wrist/elbow motion + raised-space + hand-presence hysteresis | Hand-authored boundary; frame-count thresholds vary in time at low FPS | Keep as fallback/safety gate; add learned boundary head |
| sequence | `RecognitionPipeline.kt`: 3 pre-onset frames, then append to zero-padded 96-frame array; stops accepting after 96 | No real timestamps; fixed buffer; no adaptive temporal cache | Replace for experiment, preserve production |
| S6 | `Recognizer.kt`: `[1,96,258] -> [1,96,236]`, full-window TFLite inference each tick, current INT8 TCN | 169K TCN underfits full task; landmarks omit appearance | Replace after ablation |
| S7 | `Confirmation.kt`: temperature-scaled cumulative mean log posterior, margin, streak, low-FPS minimum frame | Calibrated only in-domain; early partial signs remain weak; no explicit unknown class | Retain as baseline; redesign acceptance after model heads |
| S8 | `SentenceBuilder.kt`: ordered gloss passthrough, consecutive dedup, max 20 | Not ASL-to-English translation | Keep for isolated/gloss scope |

## Exact v3.0 Feature Contract

Per frame: left hand `21 x (x,y,z)` = 63, right hand = 63, pose
`33 x (x,y,z,visibility)` = 132; total **258 float32** in that order. Offline source:
`pipeline/features/contract.py`; Android port: `S4Features.kt`; expected schema:
`ModelContract.EXPECTED_SCHEMA = "3.0"`. Offline has a separate `(T,2)` hand-presence mask, but the
runtime model does not consume it. N4 resamples isolated training to 64; streaming training keeps
native timing and pads/truncates to 96.

## Current Assets And Recognition Logic

- `model_manifest.json`: schema 3.0, 258 features, window 96, 236 classes, INT8 internals with
  float I/O. TFLite parity report: clip top-1 0.630 versus Keras 0.629.
- `recognition_config.json`: GPU MediaPipe, 480x360, pose cadence 2, pre-onset 3, strict low-FPS
  confirmation (`min_commit_frame=4`, margin 0.9, streak 3).
- One commit is allowed per S5 signing bout; the recognizer then waits for release.
- Handedness is manually selected and persisted. Device evidence shows the wrong setting can cause
  systematic garbage predictions.

## Data And Model Evidence

- `artifacts/splits.json`: train 40,154 clips/35 signers; val 10,304/6; test 32,941/11; no signer
  overlap. ASL Citizen has 2,731 classes before vocabulary reduction.
- Current local-supplementary candidate: held-out mean top-1 0.6172, top-5 0.8683; last-frame top-1
  0.5706; k4 0.5702; k8 0.5290.
- Early prediction is weak: targeted audit baseline early4 0.081 and early6 0.137.
- Weak original train counts include SELL 23, KNOW 21, IMPORTANT 14, MANY 13, WAIT 12, WE 15,
  STRONG 15. Local data adds 3,654 usable clips but only one to three signers per class.
- Targeted v3 reached mean/last 0.627/0.587 but moved errors into SHOP1, WAIT, INTRODUCE, and others.
- Slim early-stride ST-GCN artifact
  `runs/gcn_conversational_fps_v30/eval_streaming_test.json` scored only **0.1588 top-1** and
  0.4374 top-5. A fair full-capacity config exists, but no corresponding run directory exists.

## Device Evidence

- Camera callbacks have been observed around 14-17 FPS while full processed recognition commonly
  runs 3-8 FPS, with thermal dips.
- Typical profiled cost is dominated by hand and pose landmarking; TFLite recognition is roughly
  0.5-2 ms/tick.
- The current best tested profile is GPU, 480x360, pose cadence 2; cadence 3 slightly increased FPS
  but worsened recognition and was reverted.
- This fails the stated 15-FPS target. Accuracy at 3-8 FPS is information-limited for short signs.

## Unsupported Or Poorly Represented Factors

Hand texture/finger occlusion, contact, fine handshape pixels, facial grammar, mouth/eyebrow cues,
true time deltas, per-landmark/hand confidence, missingness, velocity/acceleration, bones/angles,
two-hand relations, hand-to-face/body relations, learned sign boundaries, coarticulation, unknown
signs, hard negatives, and natural sentence context.

## References, Decisions, Assumptions, Risks, Next Action

- **Source files:** paths above plus `recognition-accuracy.md`, `encoder-upgrade.md`, and targeted
  audit artifacts.
- **Decision:** preserve production; use this pipeline as the experimental control.
- **Assumption:** July 22 device profile remains representative; rerun before deployment.
- **Risk:** older context still describes CPU/IMAGE/15 FPS as a baseline target; source/config wins.
- **Open question:** current sustained performance on a modern mid-range target device.
- **Next action:** freeze a reproducible E0 baseline manifest and execute E1.


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-016 apply; component-specific decisions in this document apply only after their experiment gate passes.
- **Assumptions:** Any forecast or unmeasured dimension remains a hypothesis, not a project fact.
- **Open questions:** Unresolved items are tracked in this document and `OPEN_QUESTIONS.md`.
- **Risks:** Applicable failure modes and fallbacks are tracked in this document and `RISK_REGISTER.md`.
- **Next required action:** Follow the explicit next action above and the ordering in `EXPERIMENT_MATRIX.md`; do not skip gates.
