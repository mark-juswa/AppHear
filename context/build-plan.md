# Build Plan

## Core Principle

**Prove it offline, cross-signer, before it touches a device.** The offline pipeline + eval
harness are built first because they are what validate the whole thesis. Every feature is
validated by the offline eval gate before any on-device work. No invisible phases â€” each
feature produces a measurable metric. Mirrors JobPilot's "UI-first, verify before logic" â€”
here it's "offline-validated before device."

Phase mapping to the model migration: Phase 0 = isolated classifier, Phase 1 = streaming,
Phase 2 = CTC, Phase 3 = Android runtime. See
[`../docs/03-model-architecture.md`](../docs/03-model-architecture.md).

---

## Phase 0 â€” Offline foundation & isolated recognition

Goal: a clean, cross-signer-validated isolated classifier + the versioned feature contract.
This is the flattering regime whose job is to prove the pipeline (eval-protocol.md).

### 01 Landmark extraction (E)
MediaPipe hand+pose (face off) over ASL Citizen + ASLRecorder2 at native fps â†’ raw landmark
sequences + visibility. Signer_id carried through.

### 02 Signing detection + dead-time trim (D1, D2)
Motion-energy + spatial-gate hysteresis â†’ `[onset, release]`. Thresholds fit on a labelled
subset (maximize span IoU), stored in config. Metric: span IoU vs. labels.

### 03 Normalization stack (N1â€“N3)
Scale (shoulder-width), orientation (roll default-on; yaw flagged), handedness (mirror to one
convention). Each records its params to the sample sidecar. Unit-tested against golden vectors.

### 04 Duration normalization (N4) + Quality gate (Q)
Resample to fixed `T` (isolated path, N4 **on**). Quality gate rejects low-coverage/
low-confidence/short-span samples and emits the dataset-health report.

### 05 Feature extraction (F) + contract v3.0
Emit v3.0 "normalized 258". Establish `schema_version` checking everywhere.

### 06 Signer-level split tooling
Partition by `signer_id` (train/val/test, no signer in two splits). This gates all eval.

### 07 Isolated TCN classifier (Keras)
Causal TCN encoder + global-poolâ†’softmax head. Train on v3.0.

### 08 Cross-signer eval harness
Per-signer + aggregate accuracy, calibration/reliability. **First real cross-signer number.**
Ship gate: clears target + calibration check.

### 09 (Optional) v3.1 kinematic ablation
Add velocity + duration scalar; adopt only on a cross-signer, end-to-end win over v3.0.

---

## Phase 1 â€” Streaming isolated (kill the window)

### 10 Real-timed data regime (N4 off)
Feed trimmed but **non-resampled** spans; model handles duration itself.

### 11 Per-frame emission head
Swap poolâ†’softmax for per-frame softmax; fine-tune the shared encoder.

### 12 Confirmation policy (S7) â€” offline
Temperature calibration + evidence accumulation + margin/stability gate. Sweep the operating
curve on held-out signers; select `confirm.operating_point`. Track correct-but-dropped rate.
This is the direct fix for v2 lesson e.

### 13 Streaming eval
Measure incremental emission within the sign's ~1 s lifetime; end-to-end on connected-ish
sequences where available.

---

## Phase 2 â€” CTC continuous recognition

### 14 Connected-sequence data + CTC head
Gloss-sequence labels (no frame alignment); linearâ†’CTC over `{vocab âˆª blank}`. Reuse encoder.

### 15 Streaming CTC decode + confirmation
Greedy / small beam with a gloss-level LM (shared with S8). Commit on posterior peaks past the
confirmation gate. Blank replaces the hand-tuned "none".

### 16 Sentence builder (S8)
Modes: raw passthrough â†’ smoothing/dedup (min inter-gloss spacing from the timing budget) â†’
LM-assisted glossâ†’text. Metric: **end-to-end phrase accuracy** (top-line). Guard insertion rate.

---

## Phase 3 â€” Android runtime integration

### 17 Capture + landmarkers (S0, S1, S2)
CameraX ImageAnalysis; parallel hand+pose; establish the â‰¥15 fps measurement + degraded mode.

### 18 Tracking + Feature parity (S3, S4)
One-Euro smoothing; **S4 as a verified port of pipeline/features** with a passing skew test.

### 19 TFLite recognition + gating (S6, S5)
INT8 model, CPU/XNNPACK, async load. S5 run-gate skips inference on uninformative ticks.

### 20 Confirmation + sentence builder on-device (S7, S8)
Port the Phase-1/2 policy; operating point from config asset.

### 21 Recognition UI
Camera preview + gloss/sentence overlay + confidence indicator + degraded-mode banner.

### 22 End-to-end device smoke + rollout
Cross-signer device validation behind flags; rollback path.

### 24 Dual-camera (back-camera) support (S0) â€” PLANNED (addendum; 23 is the parked encoder upgrade)
Add a back-camera option. **The front camera is the untouched baseline;** the back camera routes
through the identical, unchanged pipeline (MediaPipe / landmark handling / handedness / model all
untouched). **No forced mirroring** â€” the back frame is expected to already match the front's
un-mirrored analysis convention; a back-only capture-layer flip exists only as a contingency,
default OFF, enabled only if a device test proves the chirality differs. Change surface is
capture/UI only: camera toggle, correct `isFrontCamera` overlay flag, `SessionNormalizer.reset()`
on switch. No S4/F parity impact (skew test can't regress). **Fully specified â€” baseline snapshot,
decision, verification gate, and one-step revert â€” in [`back-camera.md`](back-camera.md). Read that
before building.**

---

## Post-Phase-3 â€” Accuracy track (PLANNED, parked)

### 23 Encoder upgrade (S6 model swap)
Replace the 169K causal TCN with an ST-GCN-class / small-transformer encoder. Evidence: the same
landmark input reaches 59.5% vs our 31.4% on the full ASL Citizen benchmark (architecture-limited,
not data-limited). **Fully specified â€” evidence, frozen TFLite I/O contract, prefix-augmentation,
pre-registered gates, kill criteria, and the one-step revert â€” in
[`encoder-upgrade.md`](encoder-upgrade.md). Read that file before building; do not re-derive.**
Order within it: INT8 export smoke-test FIRST, then latency probe, then training. No feature-
contract or S4/parity impact (only the S6 model swaps). Deferred alongside: Phase-2 CTC (data-
blocked), S8 LM-assist, device fps (hardware).

---

## Feature Count

| Phase | Features |
|-------|----------|
| Phase 0 â€” Offline foundation | 9 |
| Phase 1 â€” Streaming isolated | 4 |
| Phase 2 â€” CTC continuous | 3 |
| Phase 3 â€” Android runtime | 6 (+1 addendum: F24 back-camera) |
| **Total** | **22** (+1 addendum) |

Order within a phase is sequential; phases overlap only where a later phase's data regime is
ready. Run `/architect` before each complex feature (any of 02, 03, 07, 12, 14, 18).


## Native Android Full-Application Redesign (PLANNED, assessment complete)

The production `android/` runtime will be expanded into a complete application using AppHear2 only
as the UI/application-flow reference. Full contract and evidence index:
[`android-app-redesign.md`](android-app-redesign.md).

Order: baseline/backup -> discovery/docs (complete) -> design tokens -> navigation shell -> shared
components -> non-camera screens -> dedicated recognition-screen integration -> data/backend/
conversation features -> stabilization. The S0-S8 runtime, feature contract, models, and parity tests
remain protected. Every runtime-affecting phase also runs [`device-smoke.md`](device-smoke.md).

## Experimental Prototype Track - React Native / iPhone (PLANNED, separate)

This track lives outside the production Android runtime. Full contract:
[`react-native-prototype.md`](react-native-prototype.md).

### RN01 React Native camera and FPS smoke test
Create `apphear-react/` as a separate prototype. Build camera preview, permission flow, FPS HUD, and
benchmark export. No MediaPipe and no model yet.

### RN02 iOS MediaPipe hand-only landmark test
Add native iOS HandLandmarker and measure p50/p95 hand latency, processed FPS, frame drops, and
conversion cost.

### RN03 iOS hand + pose landmark test
Add PoseLandmarker and measure full hand+pose throughput. IMAGE mode is the parity baseline; VIDEO
or LIVE_STREAM are separate flagged experiments only after baseline numbers exist.

### RN04 258-feature parity
Port S4/session normalization to Swift and pass a golden-vector parity test before recognition.

### RN05 same model inference
Load the deployed `streaming.tflite` plus `model_manifest.json`, validate schema `3.0`, and verify
`[1,96,258] -> [1,96,236]` inference.

### RN06 buffering, onset, confirmation, and UI
Port S5/S7/ring buffer and emit compact recognition snapshots to React Native.

### RN07 side-by-side benchmark
Compare native Android baseline against the iPhone prototype using the same controlled sign list,
lighting, signer, camera convention, cool-start run, and sustained run.

Non-goal: this track does not migrate or replace `android/`.
