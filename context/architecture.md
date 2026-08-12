# Architecture

Operational architecture contract. Deep rationale: [`../docs/01-system-architecture.md`](../docs/01-system-architecture.md).

---

## Stack

| Layer | Tool | Purpose |
|-------|------|---------|
| Android IDE / build | Android Studio + Gradle | Runtime app is an Android Studio (Gradle) project |
| Android language | Kotlin | Runtime app |
| Camera | CameraX (ImageAnalysis) | Frame capture; decouple capture fps from inference fps |
| Landmarkers | MediaPipe Tasks â€” HandLandmarker + PoseLandmarker | Per-frame hands (2Ã—21Ã—3) + pose (33Ã—4). **Face off.** |
| On-device inference | TFLite (CPU / XNNPACK, INT8) | Temporal model. **No GPU delegate assumed.** |
| Training language | Python 3.11+ | Offline pipeline |
| Training framework | TensorFlow / Keras | Model + native, lossless TFLite export |
| Landmark extraction (offline) | MediaPipe Tasks (Python) | Same landmarkers as runtime, native fps |
| Numerics | NumPy | Normalization, feature math |
| Model target | Causal TCN encoder + swappable head (softmax â†’ CTC). **Planned S6 swap to an ST-GCN-class / small-transformer encoder â€” see `encoder-upgrade.md`** (causality no longer required: the runtime re-runs the full buffered window per tick; TFLite I/O contract frozen) | Streaming temporal model |
| Primary dataset | ASL Citizen | Signer-diverse isolated corpus |
| Aux dataset | ASLRecorder2 | Custom schema-controlled captures |

---

## Folder Structure (target)

```
/
â”œâ”€â”€ AGENTS.md
â”œâ”€â”€ README.md                         â†’ project brief + design-doc index
â”œâ”€â”€ context/                          â†’ the 9 context files (this system)
â”œâ”€â”€ docs/                             â†’ Â§8 design deliverables (rationale)
â”œâ”€â”€ pipeline/                         â†’ Python offline pipeline
â”‚   â”œâ”€â”€ extract/                      â†’ MediaPipe landmark extraction
â”‚   â”œâ”€â”€ detect/                       â†’ signing detection + dead-time trim (D1, D2)
â”‚   â”œâ”€â”€ normalize/                    â†’ scale/orientation/handedness/duration (N1â€“N4)
â”‚   â”œâ”€â”€ quality/                      â†’ quality gate (Q)
â”‚   â”œâ”€â”€ features/                     â†’ feature extraction â†’ versioned contract (F)
â”‚   â”œâ”€â”€ splits/                       â†’ signer-level split tooling
â”‚   â””â”€â”€ config/                       â†’ thresholds, flags, schema version pins
â”œâ”€â”€ model/                            â†’ Keras model definitions
â”‚   â”œâ”€â”€ encoder.py                    â†’ causal TCN encoder (shared across phases)
â”‚   â”œâ”€â”€ heads.py                      â†’ softmax classifier / CTC head
â”‚   â”œâ”€â”€ train.py                      â†’ training entrypoints
â”‚   â””â”€â”€ export/                       â†’ TFLite conversion + INT8 quantization
â”œâ”€â”€ eval/                             â†’ cross-signer, end-to-end eval harness
â”‚   â”œâ”€â”€ metrics/                      â†’ per-stage + end-to-end metrics
â”‚   â”œâ”€â”€ calibration/                  â†’ temperature scaling, reliability
â”‚   â””â”€â”€ confirmation/                 â†’ operating-curve sweep
â”œâ”€â”€ android/                          â†’ Kotlin runtime app
â”‚   â”œâ”€â”€ capture/                      â†’ S0 CameraX
â”‚   â”œâ”€â”€ landmark/                     â†’ S1/S2 MediaPipe
â”‚   â”œâ”€â”€ tracking/                     â†’ S3
â”‚   â”œâ”€â”€ features/                     â†’ S4 (byte-parity with pipeline/features)
â”‚   â”œâ”€â”€ gating/                       â†’ S5 temporal understanding
â”‚   â”œâ”€â”€ recognition/                  â†’ S6 TFLite runner
â”‚   â”œâ”€â”€ confirm/                      â†’ S7 confirmation policy
â”‚   â”œâ”€â”€ sentence/                     â†’ S8 sentence builder
â”‚   â””â”€â”€ ui/                           â†’ camera preview + gloss/sentence overlay
├── apphear-react/                    → separate React Native/iPhone prototype (planned)
│   ├── src/                          → RN UI shell, settings, result display
│   ├── native/                       → native iOS/Android vision + recognition engine
│   ├── assets/                       → copied model/task/config assets for prototype
│   └── benchmark/                    → prototype benchmark protocols + device results
â””â”€â”€ artifacts/                        â†’ exported models + schema manifests (versioned)
```

Structure is a target; create directories as phases require (see [`build-plan.md`](build-plan.md)).
The `android/` module is a standard **Android Studio (Gradle)** project â€” open `android/` in
Android Studio; `pipeline/`, `model/`, and `eval/` are plain Python and need no IDE.

---

## System Boundaries

| Folder | Owns | Never |
|--------|------|-------|
| `pipeline/` | All offline data transforms up to feature extraction | Never trains or evaluates models |
| `model/` | Keras architectures, training, TFLite export | Never does dataset normalization (imports from `pipeline/`) |
| `eval/` | All metrics, calibration, operating curves | Never mutates data or model weights |
| `android/` | On-device runtime, one folder per stage S0â€“S8 | Never re-derives normalization math independently â€” it mirrors `pipeline/features` |
| `apphear-react/` | Separate RN/iPhone experiment; UI shell plus native prototype modules | Never replaces `android/`; never changes model/schema/pipeline unless explicitly approved |
| `context/` + `docs/` | Knowledge | Never contain code |

**The critical boundary:** `android/features/` (S4) and `pipeline/features/` (F) implement
the *same* normalization + feature math. One is the source of truth (Python), the other is a
verified port (Kotlin) guarded by a skew test. This boundary is the train/serve-parity
guarantee.

---

## Data Flow â€” Offline (training)

```
video (ASL Citizen / ASLRecorder2)
  â†’ extract landmarks (MediaPipe, native fps)
  â†’ detect signing (D1) â†’ trim dead time (D2)
  â†’ normalize scale (N1) â†’ orientation (N2) â†’ handedness (N3) â†’ duration (N4, isolated only)
  â†’ quality gate (Q)
  â†’ feature extraction (F) â†’ versioned contract
  â†’ signer-level split â†’ train (Keras) â†’ cross-signer eval â†’ export TFLite
```

Details: [`../docs/02-data-pipeline.md`](../docs/02-data-pipeline.md).

## Data Flow â€” Runtime (on-device)

S0 is **camera-agnostic to the pipeline**: the analysis frame is rotate-only (no mirror), and the
model consumes the raw **un-mirrored** convention it was trained on. Adding the back camera (F24,
[`back-camera.md`](back-camera.md)) normalizes the back source to the *front* convention in the
capture layer and leaves everything downstream untouched â€” no forced mirroring; a back-only flip
only if a device test proves the chirality differs.

```
CameraX frame (S0)
  â†’ HandLandmarker + PoseLandmarker in parallel (S1/S2, face off)
  â†’ tracking: identity + One-Euro smoothing (S3)
  â†’ feature processing: same normalization as pipeline (S4)
  â†’ temporal understanding: signing? phase? motion? run-gate? (S5)
  â†’ recognition: streaming per-frame posteriors from TFLite (S6)
  â†’ confirmation: calibrated, accumulated, margin-gated commit (S7)
  â†’ sentence builder: gloss â†’ fluent text (S8)
```

---

## Feature / Schema Contract

The interface between perception and model is versioned and explicit. See
[`feature-schema.md`](feature-schema.md). Current: **v3.0 "normalized 258"** (Phase 0
baseline). Nothing reads a feature vector without checking `schema_version`.

---

## Invariants (never violate)

- `android/features` (S4) never diverges from `pipeline/features` (F). Parity is tested.
- Pose and hand feature blocks are never dropped to save compute (v2 lesson b).
- No stage of the runtime blocks the main thread on model load or inference (v2 lessons g, h).
- Every stage exposes a feature flag and a fallback (see [`../docs/01`](../docs/01-system-architecture.md)).
- All thresholds/operating points live in `config/` â€” never hardcoded in stage code.
- Face landmarker is never enabled (v2 lesson a).
- Dataset splits are always by `signer_id` â€” never by clip.
- No camera introduces mirroring into the **analysis** path â€” the model consumes the un-mirrored
  training convention. Per-camera differences (F24) live in the capture/UI layer only; the shared
  pipeline never learns which camera produced a frame. (Preview mirroring is display-only, never a
  correctness lever.)

## Data Flow - React Native Prototype (experimental)

See [`react-native-prototype.md`](react-native-prototype.md). The intended prototype flow keeps
real-time processing native and sends only compact snapshots to React Native:

```text
iOS/Android native camera frame
  -> native MediaPipe hand + pose landmarkers
  -> native S4 258-feature construction
  -> native S5/S6/S7 recognition path
  -> compact FPS/candidate/commit snapshot
  -> React Native UI
```

React Native must not receive raw camera frames or per-frame landmark arrays on the hot path.

## Native Android Full-Application Redesign

The planned AppHear2-inspired redesign of the production native Android application is governed by
[`android-app-redesign.md`](android-app-redesign.md) and its linked inventory, screen map, UI
architecture, design-system, and migration-plan documents. This work is separate from the React
Native prototype.

The target boundary is a non-camera app shell for ordinary destinations plus a dedicated recognition
activity. UI code consumes a documented recognition-state adapter; it never duplicates or directly
owns S4 feature math, S5 gating, S6 inference, S7 confirmation, or S8 sentence behavior. Until the
recognition integration phase, the existing `android/` runtime and its launcher remain the baseline.

## Planned Hybrid Recognition Upgrade

The research-only transition from v3.0 landmark-only recognition to a hybrid landmark + RGB
architecture is governed by [`recognition_upgrade/README.md`](recognition_upgrade/README.md).
Production remains the current schema-3.0 `[1,96,258]` path until that plan's signer-disjoint,
quantization, Android, calibration, false-positive, and rollback gates pass. Hybrid work uses new
schema/model/config/artifact names and a default-off feature flag; it never silently replaces S4-S7.

As approved on 2026-08-11, execution order is: (1) a trustworthy 236-sign landmark baseline,
(2) an isolated landmark + RGB hand-crop hybrid guided by baseline errors, (3) continuous
boundary/gloss recognition after phrase-level data exists, and (4) language intelligence after
visual reliability. Only Phase 1 preparation is active; Android serving remains unchanged.
