# Android Deployment Plan

**Purpose:** Define a deployable experiment without destabilizing production.
**Status:** PLANNED / E2e-C0 OFFLINE SCREENING BLOCKS DEVICE WORK. **Last updated:** 2026-07-26.

## Runtime Shape

Create experimental stages beside current S0-S7, guarded by one default-off recognizer flag.
Frames stay native; no raw pixels cross React Native or UI state. Use bounded pools/ring buffers,
single-owner inference state, `KEEP_ONLY_LATEST`, monotonic timestamps, async load, and explicit
backpressure. Production CameraX lifecycle and assets remain unchanged until final rollout.

## Runtime Choices

- **Baseline runtime:** LiteRT/TFLite with CPU/XNNPACK and INT8. GPU/NNAPI are device-profiled
  optional delegates, never assumptions.
- **Perception:** retain MediaPipe for landmarks when present. Do not repeat IMAGE/VIDEO/LIVE_STREAM mode tuning as the primary ROI fix; E2c failed coverage gates. Screen an independent single-class hand detector offline first, then measure sparse asynchronous inference and causal tracking only for a promoted candidate.
- **RGB encoder:** shared MobileNetV3-Small first. Run at measured 8-12 Hz if every-frame cost fails;
  landmark/time cache remains timestamped.
- **Model package:** new filenames, manifest, vocab, calibration, schema, and hashes.

## Device Gates

On low-end Xiaomi M2101K7AG and at least one current mid-range Android:

- p50/p95 per stage and end-to-end; camera/processed/effective modality FPS;
- 1, 5, and 20 minute thermal runs; throughput decay <20%;
- mid-range 12-20 processed FPS and p95 <80 ms; low-end must explicitly enter degraded mode;
- model 8-20 MB INT8 target, peak incremental memory <150 MB, no ANR/crash;
- quantized accuracy loss <=1 point and calibrated behavior re-fitted after quantization;
- battery/thermal report, not a single cool-device sample.

Official full-integer quantization requires representative data:
https://www.tensorflow.org/model_optimization/guide/quantization/post_training

## Fallback

Flag off loads current `streaming.tflite` and v3.0 pipeline. A landmark-only hybrid model is the
degraded multimodal fallback only if separately evaluated. Cloud inference is not required and is
outside the current product contract.

## Decisions, Assumptions, Risks, Unknowns, Next Action

- **Decision:** native Android, TFLite/LiteRT, CPU fallback, no silent asset replacement.
- **Assumption:** selected ops convert without Select TF Ops.
- **Risks:** crop copies, unsupported ops, delegate variance, thermal throttling.
- **Open question:** whether VIDEO or LIVE_STREAM integrates more predictably with parallel pose.
- **Next action:** complete E2e-C0 offline detector screening and export feasibility. Android detector integration remains blocked until a candidate passes recall, false-ROI, and model-cost gates.


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-016 apply; component-specific decisions in this document apply only after their experiment gate passes.
- **Assumptions:** Any forecast or unmeasured dimension remains a hypothesis, not a project fact.
- **Open questions:** Unresolved items are tracked in this document and `OPEN_QUESTIONS.md`.
- **Risks:** Applicable failure modes and fallbacks are tracked in this document and `RISK_REGISTER.md`.
- **Next required action:** Follow the explicit next action above and the ordering in `EXPERIMENT_MATRIX.md`; do not skip gates.

## Dynamic Mixed Android Revision - 2026-07-31

The next deployable architecture is not an always-on global hybrid recognizer. It is a default-off experimental recognizer with this runtime policy:

- Always-on path: current CameraX + MediaPipe + `[96,258]` landmark feature builder + primary landmark model.
- Conditional path: specialist resolver only when the confusion registry routes to a registered group.
- Fail-closed behavior: if a resolver is unavailable, slow, mismatched, or uncertain, reject rather than commit a hard sign.

### Android Constraints

- No replacement of current `streaming.tflite` or production manifests.
- No mutation of v3.0 feature math.
- New resolver assets must use separate filenames and manifests.
- Router and resolver must be feature-flagged and default-off until offline, quantized, and device gates pass.
- RGB crop work must be measured as conditional cost, not assumed to run every frame.

### Next Android Action

None. Android work remains blocked until the offline mixed recognizer simulation passes accepted precision, coverage, no-sign false-commit, latency projection, and quantized parity gates.

## Phase 1 Landmark Shadow Evaluation - 2026-08-12

**Status:** OFFLINE PARITY PASSED / DEVICE MEASUREMENT PENDING. This is not Phase 2 RGB
integration and does not reopen the retired P2-P2/P2-P2F ROI stack.

The frozen Phase 1 `production_streaming_tcn` three-seed ensemble (101/202/303) has been exported
beside the active recognizer for a default-off Android shadow comparison. The candidate retains the
v3.0 `[96,258] -> [96,236]` contract and the exact active Android vocabulary. It cannot feed S7,
sentence state, or UI state.

| Variant | Mean probability difference | Argmax agreement | Top-1 delta | Decision |
|---|---:|---:|---:|---|
| INT8 / float I/O | `0.000728` | `0.8828125` | `0.0078125` | reject for shadow comparison |
| Float32 | `1.68e-9` | `1.0000` | `0.0000` | proceed to device profiling |

The INT8 aggregate accuracy delta was small, but changing the winner on 15/128 validation rows
violates the registered `>=0.98` argmax-parity gate. The gate was not weakened. The float32 assets
are 713,628 bytes each (2,140,884 bytes total); host timing is not Android evidence.

Source of truth:

- exporter: `model/experiments/phase1_android_shadow.py`;
- accepted export: `artifacts/recognition_upgrade/phase1_android_shadow/export_float32_01`;
- rejected INT8 export: `artifacts/recognition_upgrade/phase1_android_shadow/export_01`;
- runtime: `android/app/src/main/java/com/example/apphear/pipeline/recognition/Phase1ShadowRecognizer.kt`;
- checked-in flag: `recognition_config.json -> phase1_shadow.enabled=false`;
- opt-in research build: `./gradlew :app:assembleDebug -Pphase1Shadow=true`;
- APK: `artifacts/recognition_upgrade/phase1_android_shadow/device_package_01/apphear-phase1-shadow-debug.apk`;
- corrected shadow APK SHA-256: `FEE3F6A325ECF8676BAA698147CEB91978956FAF76D1BF60D95716A3330A1497`;
- matching shadow-off control APK SHA-256: `6923E0E003E9270AD704869504C14126A0E591D3DBAEAFC44A98B00B2F6CF8EA`.

Device GO requires hash-guarded loading, zero shadow-caused crashes/commits/UI changes, measured
ensemble p50/p95, processed FPS with shadow off/on, agreement logs on repeated signs, and a bounded
thermal run. On failure, keep the flag off and remove the candidate assets; `streaming.tflite`
remains unchanged.

### Preliminary Device Run 01

`device_package_01/device_run_01.log` proves the shadow path executed without load/runtime errors
and emitted `may_commit=false`; all 14 observed commits came from the active recognizer. Across 21
logged five-frame checkpoints (approximately 125 shadow-evaluated signing frames), active and
shadow top-1 agreed on 10 (`47.62%`). This is model disagreement, not an accuracy measurement,
because the performed-sign ground truth was not recorded and the checkpoints are not commit events.

Measured shadow three-model ensemble latency was mean `0.683 ms`, median `0.664 ms`, p95 `0.992
ms`, max `0.996 ms`. Overall processed FPS across 29 profiler windows was mean `5.59`, range
`3.5-7.0`; hand/pose inference dominated wall time. A shadow-off control was not captured, so no
causal FPS or latency overhead claim is authorized. Confidence placeholders were printed literally
due to a logging-format defect; the corrected APKs above fix that defect. Next gate is an identical
shadow-off/on A/B with a recorded sign sequence.
