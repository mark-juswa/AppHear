# Feature / Schema Contract

*(This file occupies the `ui-registry.md` slot in the Context System convention. Like the UI
registry, it is a **living document**: it starts with the baseline contract and is updated —
via `/imprint` — every time the feature contract or a reusable pipeline/runtime component
changes. Read it before adding or changing any feature channel; match the existing contract
before inventing a new version.)*

Deep rationale: [`../docs/06-feature-schema-contract.md`](../docs/06-feature-schema-contract.md).

---

## How to Use

Before touching features:

1. Check the current `schema_version` and whether your change fits it.
2. If it fits — conform exactly. If not — it's a **new version**, never a silent reshape.
3. After changing the contract — run `/imprint`, update this file, and re-pin the model.

Nothing in the codebase reads a feature vector without checking `schema_version`. A model
records the version it trained on and the runtime refuses a mismatched contract.

---

## Contract Rules (non-negotiable)

1. No code reads features without checking `schema_version`.
2. Offline extraction (`pipeline/features`, stage F) and on-device extraction
   (`android/features`, S4) share **one implementation** (or a byte-exact port + skew test).
3. Adding channels = a **new version**, never a silent reshape.
4. A model records its trained `schema_version`; the runtime refuses to load against a
   mismatched contract.
5. Pose and hand blocks are never removed to save compute (v2 lesson b).

---

## v2 baseline (reference)

258 floats/frame, 30-frame window, 10-field JSON sidecar. Decomposition inherited:

- Hands: `2 × 21 × 3 (x,y,z)` = 126
- Pose: `33 × 4 (x,y,z,visibility)` = 132
- Face: **off** (v2 lesson a) = 0 → **258 total**

---

## v3.0 — "normalized 258"  ← CURRENT (Phase 0 baseline)

Same 258 layout as v2, but values are **post-normalization** (N1 scale, N2 roll, N3
handedness) then **N4-resampled to T=64**. Chosen so the effect of normalization alone can be
ablated against v2's raw-258, layout held constant. `SCHEMA_VERSION="3.0"` in
`pipeline/features/contract.py`. **REALIZED at stage F (feature 05).**

| Block | Dims | Order | Notes |
|-------|------|-------|-------|
| Hand L | 63 | `21 × 3` | normalized image x,y,z; slot 0 |
| Hand R | 63 | `21 × 3` | slot 1 |
| Pose | 132 | `33 × 4` | normalized x,y,z + visibility |
| **Total** | **258** | | tensor per clip `(T=64, 258)` |

- **Missing hands → NaN imputed to 0** inside the 258; a separate **presence mask** `(T,2)` is
  persisted alongside (aux, **not** part of the contract).
- **Persistence:** one `.npz` per split — `X:[N,64,258] f32`, `mask:[N,64,2] f32`, `y:[N] i32`,
  `participant_ids:[N]`, `schema_version` — plus `vocab.json` (gloss→id, built from train).
- **`clip_features` is the exact N1-N3→N4→258 composition Android S4 must replicate** (parity
  target; determinism unit-tested as the skew-test seed). Realized on val: `X (85,64,258)`,
  NaN-free, range ≈ [−6.7, 6.2].

## v3.0 streaming regime — "real-timed" (Phase 1, N4 OFF)  ← REALIZED (feature 10)

Same 258 layout, but **N4 resample is OFF** — the span keeps its **native frame count** so the
model sees real duration/speed (required for streaming). Post-padded to **`t_max=96`** (covers
span p99 ≈ 3.0s; ~0.7% tail-truncated). `clip_features_realtimed` in `contract.py`.
`features_streaming/<split>.npz`: `X:[N,96,258]`, `frame_mask:[N,96] bool` (True=real frame),
`lengths:[N]`, `y`, `participant_ids`. Reuses the isolated `vocab.json`. This regime is *closer*
to the runtime (never resamples). Val realized: `X (9575,96,258)`, NaN-free, real length median
33 / p90 61 (real timing preserved, not stretched). No new `schema_version` — regime, not layout.

## v3.1 — "kinematic 484"  (candidate, ships only if it beats v3.0 cross-signer)

Adds per-landmark velocity + a native-duration scalar.

| Block | Dims | Notes |
|-------|------|-------|
| Position (v3.0) | 258 | normalized coords |
| Hand velocity | 126 | Δ of hand coords over normalized time |
| Pose velocity | 99 | Δ of pose x,y,z (visibility not differenced) |
| Duration scalar | 1 | native span length (pre-resample) |
| **Total** | **484** | superset of v3.0 |

**Tradeoff:** ~2× input width → more per-frame compute (competes with the S1/S2 budget) and
more overfitting surface. Adopt only on a proven cross-signer, end-to-end win. v3.0 is the
safe default.

## E6-2 experiment - `apphear.landmark_geometry.v0` (not production)

This separate `[96,444]` contract preserves v3.0 channels `0:258` exactly and appends `186`
deterministic geometry channels: hand-local coordinates `120`, joint cosines `28`, palm normals
`6`, body/head relations `28`, and quality/masks `4`. The implementation is
`pipeline/features/landmark_geometry.py`.

This is not schema v3.1 or a production schema promotion. It deliberately excludes the old
velocity/acceleration candidate tested in E3-B6/B7. It remains offline-only until the gates in
`context/recognition_upgrade/E6_2_RICHER_LANDMARK_CONTROL_PLAN.md` pass and a Kotlin golden-vector
parity implementation is separately approved. Production v3.0 remains current.

---

## Missing-Data Convention (versioned)

- Missing coordinates → filled by S3 tracking gap-fill where possible.
- If still missing → **sentinel value with visibility/presence = 0**, never a bare 0 (which
  looks like the origin).
- The quality gate rejects samples exceeding the missing-data budget, so models rarely train
  on sentinels — but the convention is fixed so it can't be read two ways.

---

## Storage Sidecar (ASLRecorder2 lineage) — required fields

| Field | Purpose |
|-------|---------|
| `schema_version` | pin features + parsing |
| `gloss` | label |
| `signer_id` | **required** — signer-level splits depend on it |
| `source` | `asl_citizen` \| `aslrecorder2` |
| `native_fps` | quality gate + duration handling |
| `span` | trimmed `[onset, release]` frames (after D2) |
| `normalization` | which N-stages applied + params (scale ref, roll angle, mirrored?) |
| `quality` | gate outcomes + coverage/confidence stats |
| `dominant_hand` + `mirrored` | from N3 |
| `mirror_exempt` | true for handedness-lexical glosses |

Recording `normalization` params per sample is what lets S4 reproduce the identical transform
on-device — the train/serve-parity guard.

---

## Stage E — raw landmark arrays (on-disk, pre-normalization)

Stage E (`schema_stage: "E"`) stores **raw MediaPipe landmarks**, before any trimming or
normalization. One `.npz` (arrays) + one `.json` (sidecar) per clip. Extraction runs in
MediaPipe **IMAGE mode** (stateless per-frame; tracking is deferred to an explicit S3 stage so
it's replicable on both sides). Hand slots are canonical: index 0 = Left, 1 = Right.

| Array | Shape | Notes |
|-------|-------|-------|
| `hands_image` | `(T, 2, 21, 3)` | normalized image coords (x,y,z); **NaN if absent** |
| `hands_world` | `(T, 2, 21, 3)` | metric world coords; NaN if absent (kept for N2 yaw) |
| `hand_score` | `(T, 2)` | per-slot detection score (0 if absent) |
| `pose_image` | `(T, 33, 4)` | image coords + visibility (x,y,z,vis) |
| `pose_world` | `(T, 33, 3)` | metric world coords |
| `pose_score` | `(T,)` | mean pose visibility (0 if absent) |
| `timestamps_ms` | `(T,)` int64 | from native fps; not fed to MediaPipe |

The E sidecar realizes the storage sidecar below **plus**: `schema_stage`,
`extraction_version`, `model_config_hash` (hashes model variant + confidences + running mode
→ config-driven re-extraction on any change), `mediapipe_version`, `frame_width/height`, and
the three hit-rates (`hand_hit_rate`, `two_hand_hit_rate`, `pose_hit_rate`).

## Stage D1/D2 — signing span (non-destructive metadata)

Stages D1 (signing detection) + D2 (dead-time trim) do **not** modify the raw stage-E `.npz`.
They write a per-clip `*.span.json` + `manifest_spans_<split>.csv` recording the
`[onset, release]` signing span; downstream stages read raw landmarks + span.

Signal = **pose-wrist/elbow motion** (present ~100% of frames) in shoulder-width units, with
**hand motion as an additive auxiliary** (never required — NaN hands can't block detection) +
a "hands raised above the hip line" signing-space gate. Span found by hysteresis
(`theta_on`/`theta_off` + `k_on`/`k_off`), longest run, extended by `backoff`.

Span sidecar fields: `onset`, `release` (inclusive frame indices; -1 if none), `valid`,
`reason`, `n_signing_frames`, `span_duration_s`, `shoulder_scale`, `in_span_hand_rate`,
`out_span_hand_rate`, `motion_p50`/`motion_p90` (tuning diagnostics), plus `detect_version`,
`params_hash`, and clip identity. `valid=False` clips are quality-gate candidates (feature 04).

**Tuned (val, 6 signers):** `theta_on=0.12` → 97.8% coverage, median span ~1.06s (raw clips
~3.5s). Re-tune if the stage-E config changes.

## Stage N1/N2/N3 — canonical space (normalization)

Pure geometric transforms of image-space landmarks into **canonical space**, derived from the
D2 span. **This is the #1 train/serve-parity surface** — Android S4 must port this math exactly.

Order: **center** (per-frame → torso/shoulder midpoint) → **scale** (per-clip span-median
shoulder width) → **roll** (per-clip shoulder-line tilt, folded to ±90°) → **mirror**
(handedness). Basis = image x,y,z (v2's 258 basis). z scaled but not centered/rotated;
visibility passthrough. World landmarks reserved for the deferred N2 yaw experiment.

Recorded per clip (`normalization` in the eventual sidecar; `manifest_norm_<split>.csv` now):
`scale`, `roll_deg`, `dominant` hand, `mirrored`, `normalize_version`, `params_hash`.

**Invariance (val):** normalized shoulder width 1.000 ± 0.000; residual roll ≈ 0.02° (max
0.14°); handedness 100% canonical after norm (12% of clips mirrored). Flags `n1_scale`,
`n2_roll`, `n2_yaw`(off), `n3_handedness`, each a no-op fallback.

## Stage N4 + Q — duration normalization & quality gate

**N4 (duration normalization):** resample the normalized span to a fixed **T=64** frames by
per-channel **linear** interpolation over normalized time [0,1] (NaN gaps filled when endpoints
exist, else NaN; n=1 replicates; n=0 all-NaN). **Isolated-path / training-only** — OFF in
streaming/CTC (the model then handles real timing). T is a tensor length, not runtime fps.
Native duration retained as a scalar side feature (reuse `span_duration_s`).

**Q (quality gate):** **advisory** per-clip accept/reject with itemized reasons — nothing is
deleted; F/training consults `manifest_quality_<split>.csv`. Gates (in `quality.yaml`): valid
span, min coverage (in-span hand-present fraction), min confidence (mean pose visibility), fps
floor, min span frames. Thresholds lenient, tuned on the rejection-distribution report to
protect signer coverage.

Neither N4 nor Q is an Android **S4 parity surface** (N4 off at runtime; runtime gating is S5).

**Val health:** 94.4% accepted; rejections = invalid_span (2) + low_coverage (3), attributable.

## Phase 1 Full-Vocabulary Contract Lock - 2026-08-11

Phase 1 retains schema v3.0 exactly: sequences are padded to `96` frames with `258` values per
frame, and `frame_mask`/`lengths` remain auxiliary sequence metadata. Production TCN and mask-aware
TCN consume the same base tensor; mask awareness is model behavior, not a feature-schema change.
No face landmarks, RGB values, derived geometry, or detector outputs are added in Phase 1. Android
S4 and the golden skew tolerance remain unchanged.

`pipeline/splits/phase1_full_vocab.py` is a dataset-lineage component, not feature math. It requires
`schema_version=3.0`; its existence does not change train/serve parity.

`pipeline/splits/phase1_assemble.py` materializes only manifest-authorized existing v3.0 features.
Each NPZ preserves `X`, `y`, `frame_mask`, `lengths`, signer/sample/source/hash metadata, and an
explicit `schema_version`. It validates but never recalculates feature values. Protected replay is
not emitted as a model tensor.

`model/experiments/phase1_full_vocab_baseline.py` applies low-FPS training augmentation by selecting
real frames at a bounded stride, compacting them to the front, regenerating `frame_mask`, and
zero-padding to 96. It does not change the 258 values of retained frames or the schema version.

## Component Registry (reusable pipeline/runtime pieces)

*Living list, appended via `/imprint`. Each entry: name, path, purpose, I/O, and the contract
stage/version it targets — so new components match existing ones instead of drifting.*

| Component | Path | Purpose | I/O | Targets |
|-----------|------|---------|-----|---------|
| `LandmarkExtractor` | `pipeline/extract/landmarks.py` | Stage E: video → raw hand+pose landmarks (MediaPipe IMAGE mode, face off) | video path → `ClipLandmarks` + meta | stage E |
| `ClipLandmarks` | `pipeline/extract/schema.py` | Typed raw-landmark arrays + `.npz` I/O + shape validation | arrays ↔ `.npz` | stage E |
| `ClipSidecar` | `pipeline/extract/schema.py` | Per-clip metadata + `.json` I/O | fields ↔ `.json` | stage E |
| `ExtractConfig` / `load_config` | `pipeline/extract/config.py` | Typed `extract.yaml` loader + `model_config_hash` | yaml → config | stage E |
| extraction runner | `pipeline/extract/run.py` | Resumable split runner + dataset-health manifest | split CSV → npz/json + manifest | stage E |
| health sampler | `pipeline/extract/health.py` | Cross-signer detection health check (no files written) | split CSV → per-signer hit-rate report | stage E |
| `clip_scale` / `shoulder_width_frame` | `pipeline/normalize/scale.py` | Body-scale reference (shoulder width); shared by D1 + N1 | pose_image → scalar | shared |
| `compute_signals` | `pipeline/detect/signals.py` | D1 motion energy + hands-raised gate (pose primary, hand aux) | `ClipLandmarks` → `Signals` | stage D1 |
| `detect_span` | `pipeline/detect/span.py` | D2 hysteresis span state machine → `[onset, release]` | `Signals` → `Span` | stage D2 |
| `SpanSidecar` / `DetectConfig` | `pipeline/detect/schema.py`, `config.py` | Span sidecar I/O + typed `detect.yaml` + `params_hash` | fields ↔ json / yaml | stage D1/D2 |
| detect runner | `pipeline/detect/run.py` | Resumable span runner + label-free validation report | npz → span json + manifest | stage D1/D2 |
| `pipeline/topology.py` | `pipeline/topology.py` | Named MediaPipe landmark indices + mirror pairs | — | shared |
| `normalize_clip` | `pipeline/normalize/transforms.py` | N1/N2/N3 → canonical space (center/scale/roll/mirror), pure | hands+pose+span → normalized + `NormParams` | stage N1-N3 |
| `decide_handedness` | `pipeline/normalize/handedness.py` | Dominant hand (pose-wrist motion) + mirror decision | pose+span → `HandednessDecision` | stage N3 |
| `NormalizeConfig` | `pipeline/normalize/config.py` | Typed `normalize.yaml` + `params_hash` | yaml → config | stage N1-N3 |
| normalize runner | `pipeline/normalize/run.py` | Applies N1-N3 + cross-signer invariance report + norm manifest | npz+span → manifest | stage N1-N3 |
| `resample_clip` / `resample_block` | `pipeline/normalize/resample.py` | N4 linear resample of a span to fixed T (NaN-safe) | span landmarks → (T,...) | stage N4 |
| `evaluate_quality` | `pipeline/quality/gate.py` | Q advisory accept/reject with itemized reasons | scores+span → `QualityResult` | stage Q |
| `QualityConfig` | `pipeline/quality/config.py` | Typed `quality.yaml` (N4 + Q) + `params_hash` | yaml → config | stage N4/Q |
| quality runner | `pipeline/quality/run.py` | Q gate + N4 sanity + dataset-health report + accept manifest | npz+span → manifest | stage N4/Q |
| `clip_features` / `build_feature_vector` | `pipeline/features/contract.py` | v3.0 contract: N1-N3→N4→258 vector + presence mask (S4 parity target) | landmarks+span → `(T,258)`+mask | **v3.0** |
| features builder | `pipeline/features/run.py` | Compose accepted clips → stacked per-split `.npz` + vocab | npz+span → `X,mask,y` + vocab | **v3.0** |
| `clip_features_realtimed` | `pipeline/features/contract.py` | Phase-1 N4-off compose: real-timed span → padded `(t_max,258)` + frame_mask + length | landmarks+span → padded seq | v3.0 streaming |
| streaming builder | `pipeline/features/streaming.py` | Build real-timed padded features per split (reuses vocab) | npz+span → `X,frame_mask,lengths,y` | v3.0 streaming |
| `build_streaming_classifier` | `model/model.py` | Shared causal encoder + PER-FRAME softmax → `(T,num_classes)` | streaming X → per-frame probs | Phase 1 |
| `build_stgcn` | `model/model_gcn.py` | Experimental E1 graph encoder; legacy behavior is default, while config can opt into MediaPipe pose topology, inferred hand presence, and padded-frame-masked pooling | `(T,258)` → tiled `(T,num_classes)` clip posterior | v3.0 experimental S6; no feature-contract change |
| streaming trainer | `model/train_streaming.py` | Per-frame train with explicit overwrite refusal and `latest.keras`/`--resume`; optional warm start only into a fresh output | streaming features → resumable model run | Phase 1 / E1 |
| `augment_batch` | `model/augment.py`, `model/data.py` | Train-only geometric/noise augmentation; streaming caller supplies `frame_mask`, and padded frames are forcibly restored to exact zero | `(B,T,258)` + optional `(B,T)` valid mask → augmented `(B,T,258)` | v3.0 training; no schema change |
| `build_landmark_geometry` | `pipeline/features/landmark_geometry.py` | E6-2 experiment-only deterministic hand-local shape, angle, palm, head/body relation, and mask builder; preserves channels `0:258` | `(N,T,258)` + `(N,T)` frame mask → `(N,T,444)` + schema manifest | `apphear.landmark_geometry.v0`; offline only |
| `augment_landmark_geometry_batch` | `pipeline/features/landmark_geometry.py`, opt-in dispatch in `model/train_streaming.py` | Augments the v3.0 base block then rebuilds all derived channels so training never mixes transformed landmarks with stale geometry | `(B,T,444)` + frame mask → consistent augmented `(B,T,444)` | E6-2 only; selected by `augment.contract` |
| E6-2 geometry runner | `pipeline/rgb/e6_2_landmark_geometry.py` | Derives isolated tensors, creates zero-extended broad-warm-start initializers, smoke-tests, trains on explicit command, and evaluates frozen gates | repaired v3.0 split package → isolated E6-2 artifacts | E6-2 offline; no Android/export |
| streaming eval | `eval/streaming.py` | Mean-over-real aggregation plus per-frame/last-frame diagnostics; caller supplies a safe unique report name with model/config/feature provenance | streaming model → named eval JSON | Phase 1 / E1 |
| `SplitManifest` / `build_manifest` / `verify_disjoint` | `pipeline/splits/registry.py` | Frozen signer→split map + disjointness leakage guard + content hash | official CSVs → `artifacts/splits.json` | shared |
| splits runner | `pipeline/splits/run.py` | Build/verify the pinned split manifest (`--verify` = drift guard) | CSVs ↔ manifest | shared |
| RU-D3 repair-candidate builder | `pipeline/splits/ru_d3_repair_candidate.py` | Builds an isolated, fully hashed training candidate from audited raw-video lineage: reuses locked Stage E and Stage F, applies existing D1/D2 where valid, uses a bounded rest-to-temple-to-rest override only for manually reviewed low-motion KNOW captures, enforces target-variant exclusions and a deterministic per-signer cap, and proves every non-target row unchanged | frozen Phase-1 train tensor/manifest + audit decisions + hashed raw videos → isolated Stage-E/span/per-clip artifacts + candidate `train.npz`/manifest/lineage reports | schema v3.0 `[96,258]`; dataset-lineage component only, no S4/F math or runtime change |
| RU-D5 Sem-Lex selector/screener/extractor/finalizer | `pipeline/splits/ru_d5_semlex_candidate.py`, `pipeline/splits/ru_d5_semlex_screening.py`, `pipeline/splits/ru_d5_semlex_apphear_extract.py`, `pipeline/splits/ru_d5_semlex_replacements.py`, `pipeline/splits/ru_d5_semlex_finalize.py` | Selects only target-class Sem-Lex TRAIN rows, selectively extracts archive members, creates bounded visual/landmark evidence, rejects supplied-pose reuse, and uses the shared RU-D3 Stage-E/offline-D1-D2/Stage-F implementation. Visually verified boundaries may replace wrong D1/D2 spans only when unchanged class-specific landmark gates pass; MediaPipe/domain and variant failures remain excluded. The finalizer processes only the bounded replacement set, freezes exact-target rows with full video/Stage-E/span/feature lineage, and proves Candidate C is the unchanged RU-D3 prefix plus accepted external rows. | Sem-Lex TRAIN metadata/videos + frozen RU-D3 dataset + reviewed Stage-E artifacts → review/extraction/manual-span manifests and isolated Candidate-C dataset/lineage | schema v3.0 `[96,258]` dataset lineage only; acceptable variants and supplied poses excluded; no S4/F math, threshold, model, or runtime change |
| `build_encoder` / `build_classifier` | `model/model.py` | Causal-TCN encoder (shared across phases) + Phase-0 softmax classifier | `(T,258)` → embeddings / logits | v3.0 |
| trainer + data | `model/train.py`, `model/data.py` | Config-driven training (`--smoke`) + v3.0 `.npz` → `tf.data` | features → checkpoints | v3.0 |
| pipeline orchestrator | `pipeline/run_pipeline.py` | One-command E→D→F for a split (+ run recipe) | split → features | — |
| golden exporter | `pipeline/features/export_golden.py` | F18 skew-test fixtures: real val clips → JSON (raw landmarks+span+expected 258+params) for the Kotlin S4 test | clips → `android/.../test/resources/golden/s4_golden.json` | **v3.0 parity** |
| **Kotlin S4 port** | `android/app/src/main/java/com/example/apphear/pipeline/features/{Topology,S4Features}.kt` | On-device S4: byte-exact port of N1-N3 normalize + 258-vector (N4 off). Flat frames: pose`[k*4+c]`, hands`[(s*21+l)*3+c]` | landmarks+span → `List<FloatArray(258)>`+params | **v3.0 (S4 parity)** |
| S4 skew test | `android/app/src/test/java/com/example/apphear/S4SkewTest.kt` | JVM gate: Kotlin S4 vs Python golden, max abs diff ≤ 1e-4 (the train/serve-parity guard) | golden json → pass/fail | **v3.0 parity** |
| `PostCommitRearm` | `android/app/src/main/java/com/example/apphear/pipeline/recognition/PostCommitRearm.kt` | Default-off S5/S7 bridge: establishes a configurable, candidate-stable departure from the last commit, then requires candidate-matched confirmation through unchanged S7; reads `post_commit_rearm.enabled` + measured `departure_frames` | post-commit per-frame top-1 + last committed class → departure/re-arm state; never emits a word | v3.0 runtime policy; no feature-contract change |
| RU-D1/RU-D2 runtime diagnostics + replay | `android/app/src/main/java/com/example/apphear/pipeline/diagnostics/{RuD1Diagnostics,RollingEvidenceBuffer}.kt`, `android/app/src/main/java/com/example/apphear/pipeline/recognition/RuD1PipelineTrace.kt`, `eval/runtime_diagnostics/{ru_d1.py,run_ru_d1_batch.ps1}` | Default-off, debug-only failure attribution: retains a bounded 48-frame rolling visual ring that freezes eight processed frames after S5 release (latest 48 at manual stop when release is missed), records synchronized S1-S7 observations and batch labels, reconstructs every exact fixed window from source-frame IDs, verifies SHA-256/TFLite-argmax/S7 decision parity, reports cross-architecture probability delta, and compares actual S5 windows with a manually annotated oracle span. S7 parity is replayed from the recorded Android posterior (its authoritative input), while offline TFLite remains the independent window/argmax gate. The generic CSV launcher supports bounded labeled queues and optional per-attempt READY instructions; display-only READY/RECORDING/SAVING/SAVED states never start capture, which still requires an explicit long-press. | labeled attempt + immutable runtime observations → trace/evidence bundle → attempt/class-health CSV; never feeds a value back into S1-S8 | schema v3.0 `[96,258]`; observational only, no feature-contract or S4/F math change |
| RU-D10 observation-continuity candidate + profiler | `android/app/src/main/java/com/example/apphear/pipeline/{FrameAnalyzer,RuntimeProfiler}.kt` | Debug-only `ruD10A` candidate closes per-frame MediaPipe image wrappers and recycles converted/rotated bitmaps only after S1/S2 and bounded diagnostic copying complete; profiler adds processed-start inter-frame gap mean/p50/p95. It does not alter pixels, rotation, IMAGE-mode MediaPipe, pose cadence, landmarks, S4, S5-S7, or model inputs. Device evaluation produced an AppHear native `SIGSEGV` in `libhwui BitmapWrapper::freePixels` in both A modes, so the lifetime candidate is rejected; only the non-semantic gap profiler remains reusable. | identical CameraX analysis bitmap → identical S1/S2 results, with bounded resource lifetime + timing logs | schema v3.0 `[96,258]`; no F/S4 or feature-contract change; rejected flag remains off and release/default debug build remains off |
| RU-D10 S5 one-short-gap candidate | `android/app/src/main/java/com/example/apphear/pipeline/recognition/SigningDetector.kt` | Debug-only `ruD10B` onset-state experiment: preserves existing `theta_on`, `theta_off`, and `k_on`, while allowing at most one non-candidate processed frame only after onset accumulation starts and only while S5-observable hands remain present, the raised gate remains open, and motion has not returned below `theta_off`. Missing hands, clear rest, a second interruption, reset, or release clears the bridge. Frozen replay recovered two evaluable onsets with no added off-span onsets but changed three attempts from no commit to wrong diagnostic commits, so the candidate is rejected. | existing pose/hand S5 signals → unchanged event stream when off; bounded alternative onset state when on | v3.0 runtime gate only; no `[96,258]`, S6, S7, threshold, or model change; rejected flag remains off and release/default debug build remains off |
| eval metrics + calibration | `eval/metrics.py`, `eval/calibration.py` | Per-signer top-k, ECE, confusion; temperature scaling | probs+labels → numbers | — |
| eval harness + runner | `eval/harness.py`, `eval/run.py` | Cross-signer report (report-only JSON); seeds S7 calibration | model+features → `eval_<split>.json` | — |
| cross-signer pilot | `pipeline/pilot.py` | Gloss-restricted multi-signer slice through E→D→F (de-risk before full run); `extract.run(only=...)` allowlist | splits → small aligned features | — |
