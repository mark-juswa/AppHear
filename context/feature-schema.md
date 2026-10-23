# Feature / Schema Contract

## Recognition V3 Stage 1 component — 2026-10-15

`CurrentFrameHandPair` (`android/app/src/main/java/com/example/apphear/perceptionvnext/`)
overlaps the two current-frame hand crop/refiner calls only when both existing DWPose proposals
exist. `recognitionV3ParallelHands=true` is debug opt-in; default/release remain serial.
One bounded worker, two distinct CPU/XNNPACK interpreter owners (unchanged two threads each),
and separate 602,112-byte input buffers are mandatory. `run()` drains both operations, including
on failure/interruption, before any observation delivery, buffer reuse, frame close or native
handle destruction. No frame queue, tracking, hold, synthetic landmarks or pose cadence change.

The raw-v1, S2 378, Recognition V2 350 and fingerspelling Adapter v1 405 contracts are unchanged;
no new model representation or compatibility adapter is introduced. Native crop math, DWPose,
hand models, ROI/presence/validity/handedness decisions and all downstream feature math stay frozen.
The optional caller-owned output in `PerceptionVNextNativePreprocessor.crop` must never alias
another concurrently executing crop. The JNI kernel reads the immutable current-frame raw image.

`recognitionV3Profile=true` adds at most 240 genuine-observation timing rows per analyzer under
`apphear.perception_v3_timing.v1`; this is diagnostic metadata, never model input. Capture identity
and completion clock are separate. Phone FPS, full Android parity and recognition accuracy remain
unverified. See `docs/recognition-v3-stage1-2026-10-15.md` and its compact evidence.

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
| Text-to-ASL Original word batch | `domain/texttoasl/OriginalWordBatchCatalog.kt`; `ui/texttoasl/AndroidAssetAslCatalogLoader.kt`; `tools/text_to_asl_assets/import_original_word_batch.py` | Original-only verified catalog overlay with atomic baseline fallback; no retargeting | schema-1 SHA-pinned 32 replacements + 171 additions -> 273-entry Original catalog; idle preserved | Presentation-only debug `aslOriginalWords`, default/release OFF; no recognition contract/S4/F change |

| Text-to-ASL neutral idle derivative / guard | `tools/text_to_asl_assets/new-idle.mjs`; `ui/texttoasl/AslIdlePilotContract.kt` | Adds a full neutral reset and gentle breathing without changing existing signs or resources; permits only the exact flagged idle override | Verified 27-sign shared GLB → 28-animation derivative + schema-2 manifest with optional `idle`; guarded metadata/hash → New POSE replacement with original fallback | Presentation-only; debug `aslNewIdle`, default/release OFF; no recognition schema/version or S4/F parity change |
| Text-to-ASL complete alphabet fallback | `tools/text_to_asl_assets/alphabet-fallback.mjs`; `domain/texttoasl/{AslAnimationCatalog,AslPhrasePlanner}.kt`; `ui/texttoasl/{AslAlphabetPilotContract,AndroidAssetAslCatalogLoader}.kt` | Adds C–Z to the shared New rig; resolves unknown tokens atomically through a letter-only lookup without hijacking the standalone I/Me alias | Verified 28-animation sign/idle bundle + C–Z GLBs → 52-animation derivative/schema-3 manifest; known sign lookup first → complete per-token letters or whole unsupported token | Presentation-only; debug `aslAlphabetFallback` requires idle/character selector, default/release OFF; no recognition schema/version or S4/F parity change |
| Account repository/session store | `android/app/src/main/java/com/example/apphear/data/profile/`; `domain/profile/AccountModels.kt` | Optional Auth account flow, serialized session refresh, encrypted remembered session and profile metadata | User-initiated login/register/edit/logout → Auth user/session; UI receives profile-only StateFlow | Presentation/account-only; debug `profileAccounts`, default/release OFF; no recognition feature schema |
| Continuous-transition diagnostic observer/evaluator | `android/app/src/debug/java/com/example/apphear/perceptionvnext/{PhoneCausalController,PhoneTransitionDiagnosticCohort,PerceptionVNextLiveRecognitionActivity}.kt`; `eval/runtime_diagnostics/continuous_transition_diagnostics.{py,html}` | Debug-only A hands-down/B hands-up whole-sequence navigation plus bounded negative review; records existing lifecycle evidence without modifying it; audits linkage and evaluates human physical transitions | Existing raw-v1/exact 378 + normalized input + S2 output + source originals + shared decoder updates → source-linked logs; human-boundary manifest → transition timing, episode/window association and uncertainty | No feature/model version change; targets `apphear.perception_vnext.raw.v1`, `apphear.perception_vnext.segmentation_features.v1`, Recognition V2 and frozen S2-R2 package; review artifact only is `apphear.continuous_transition.human_boundaries.v1`; PRE_OR_POST 399.924 ms / 533.232 ms gap guard and PASS_THROUGH unchanged. Device A/B evidence pending. |
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
| A1 independent-clock perception scheduler | `android/app/src/main/java/com/example/apphear/pipeline/{IndependentClockFrameAnalyzer,A1Scheduling,CloseableFrameAnalyzer}.kt`, `android/app/src/main/java/com/example/apphear/pipeline/diagnostics/A1Diagnostics.kt` | Default-off, debug-only scheduling experiment: independent long-lived hand and pose workers plus a serialized recognition consumer, each with a capacity-one latest-only mailbox; hand timestamps are authoritative and join only the newest bounded-age causal pose. Immutable upright bitmaps are shared read-only through reference-counted packet ownership, without explicit `Bitmap.recycle()` or `MPImage.close()`. Pause, camera switch, and destruction detach capture immediately and join workers off-main-thread before shared landmarker/recognizer closure. The no-sign benchmark and bounded signing sentinel passed, so A1 is retained as the default-off v2 foundation rather than promoted to production. | CameraX RGBA frame + source timestamp → timestamped direct hand result + newest valid causal pose → unchanged S4/S5/S6/S7 input observation; rejected joins are diagnostic only | schema v3.0 `[96,258]`; scheduling only, no F/S4 math, MediaPipe config/model/mode, threshold, vocabulary, TFLite, or downstream-policy change; phone evaluation complete |
| A2-2R one-observation recovery evaluator | `eval/runtime_diagnostics/a2_recovery_experiment.py`, `model/config/recognition_upgrade/{a2_recovery.json,run_a2_recovery.ps1}` | Frozen offline C0/C1/C2 evaluator for direct-only versus one-observation hold versus bounded causal velocity. Uses raw non-inverted MediaPipe slots, direct-only history, explicit `DIRECT`/`RECOVERED_HOLD`/`RECOVERED_VELOCITY`/`MISSING` provenance, and next-direct re-entry proxy scoring. It never lets recovered data seed history or persist through a second miss. Both candidates were rejected for absence/rest/leaving/stale-gap, velocity-continuity, and downstream wrong-commit failures; do not integrate or tune them. | frozen A1 schema-v3.0 observations + reviewed A2 sidecar labels → candidate feature replay, provenance, geometry/safety metrics, and frozen S5-S7 comparison artifacts | schema v3.0 `[96,258]` consumer only; evaluation provenance is a sidecar, not a contract field; no F/S4, model, Android, threshold, or downstream-policy change |
| NEGATIVE_GOLD governance and blinded top-up reviewer | `pipeline/tracking/{n0_blinded_readjudication,negative_gold_governance}.py`, `model/config/recognition_upgrade/{n0_blinded_readjudication,negative_gold_topup}.json`, `model/config/recognition_upgrade/run_{n0_blinded_readjudication,negative_gold_topup}.ps1` | Freezes human-only strict zero-hand evidence: five-class semantic review, concealed repeat QC, exact-SHA/dHash diversity filtering, immutable seed construction, protected-split/positive-overlap checks, source inventory, and label/model-blind top-up queue preparation. Image similarity may reject redundancy but never supplies semantic truth. Redundant reviewed frames are retained outside the independent denominator. | governed RGB + source metadata + labels actually supplied by a human → hashed canonical labels, QC result, independent `ZERO_HAND` seed, source audit, and neutral review queue | benchmark governance only; no schema-v3.0/S4-F math, detector, model, Android, or recognition-policy change |
| Open Images external NEGATIVE_GOLD candidate preparer/reviewer/finalizer | `pipeline/tracking/negative_gold_open_images.py`, `model/config/recognition_upgrade/negative_gold_open_images_v7.json`, `model/config/recognition_upgrade/run_negative_gold_open_images_v7.ps1` | Builds a bounded, attributable Open Images V7 validation pool using official human image-label metadata only for coarse diversity discovery; requires complete per-image CC BY 2.0 metadata; preserves original URLs/landing page/author/license/download time/hash; filters exact/frozen-dHash redundancy against the 76-frame seed; creates a neutral three-class human queue with concealed byte-identical repeats and display-only rotation/zoom; and formalizes completed canonical/QC evidence with a hard stop on any `ZERO_HAND`/`HAND_VISIBLE` repeat disagreement. Metadata/model absence never establishes zero-hand truth. | official metadata + bounded CVDF source bytes + frozen seed + labels actually supplied by a human → immutable source/license manifest, attribution ledger, hashed independent candidates, neutral review queue, canonical label export, repeat-QC ledger, and gated finalization decision | benchmark governance only; no schema-v3.0/S4-F math, detector/classifier, model, Android, or recognition-policy change |
| NEGATIVE_GOLD external dual-pass confirmation reviewer/finalizer | `pipeline/tracking/negative_gold_external_confirmation.py`, `model/config/recognition_upgrade/negative_gold_external_confirmation.json`, `model/config/recognition_upgrade/run_negative_gold_external_confirmation.ps1` | Verifies immutable first-pass evidence, excludes binary repeat-discordant canonical images, diversity-selects a fixed subset under the unchanged exact/dHash rule, creates an independent label-blind queue with byte-identical repeats, and formalizes canonical labels, repeat QC, dual-pass comparison, diversity diagnostics, and hash provenance. First-pass labels remain internal; a run-level critical binary repeat disagreement blocks every promotion without silent repair. | frozen first-pass canonical/QC/source-license artifacts + 76-frame seed + labels supplied by a human → hashed 160-image confirmation set, neutral 180-row queue, repeat-QC/dual-pass/dedup ledgers, and gated completion or hard-stop result | benchmark governance only; no schema-v3.0/S4-F math, detector/model, training, Android, or recognition-policy change |
| NEGATIVE_GOLD item-level audit/finalizer | `pipeline/tracking/negative_gold_item_level_audit.py`, `model/config/recognition_upgrade/negative_gold_item_level_audit.json`, `model/config/recognition_upgrade/run_negative_gold_item_level_audit.ps1` | Preserves both historical Open Images QC failures, permanently excludes known binary repeat-conflict items, creates a reproducible metadata-stratified and model-blind 40-image actual-human-hand audit, applies the preregistered contamination decisions, and freezes exactly 124 deterministic diversity-ranked additions plus a reserve when the audit passes. The final manifest distinguishes individually audited evidence from dual-confirmed evidence qualified by the random pool audit. | frozen dual-pass/QC/source-license evidence + 76-frame seed + labels supplied by a human → conflict ledger, neutral audit queue, contamination result, frozen 200-row NEGATIVE_GOLD_V1 manifest, reserve, and hash provenance | benchmark governance only; no schema-v3.0/S4-F math, detector/model, training, Android, or recognition-policy change |
| eval metrics + calibration | `eval/metrics.py`, `eval/calibration.py` | Per-signer top-k, ECE, confusion; temperature scaling | probs+labels → numbers | — |
| eval harness + runner | `eval/harness.py`, `eval/run.py` | Cross-signer report (report-only JSON); seeds S7 calibration | model+features → `eval_<split>.json` | — |
| cross-signer pilot | `pipeline/pilot.py` | Gloss-restricted multi-signer slice through E→D→F (de-risk before full run); `extract.run(only=...)` allowlist | splits → small aligned features | — |

## P5-A experimental contract — `DWPOSE_REPRESENTATION_V2_238` (2026-08-25)

P5-A freezes an offline-only DWPose-native contract with canonical shape `[96,238]`. It does not replace active production schema v3.0 and is not input-compatible with the current S6 or Android runtime.

- channels `0..83`: DWPose left-hand indices `91..111`, each `(x_normalized,y_normalized,score,valid_mask)`;
- channels `84..167`: DWPose right-hand indices `112..132`, same channels;
- channels `168..235`: DWPose body indices `0..16`, same channels;
- channels `236..237`: current-frame left/right `hand_observed_mask`;
- normalization: same-frame shoulder midpoint and shoulder distance, with hip/body deterministic fallbacks; the same transform applies to both hands and body;
- invalid point and unobserved-hand padding: exact zeros with explicit masks; no fake Z, carry-forward, interpolation, extrapolation, or human-truth input;
- governed validation: 458/458 frames and 28 sequences converted, normalization 100%, fallback 0%, NaN/Inf 0, stale-hand violations 0.

Frozen contract artifacts and hashes are in `artifacts/recognition_upgrade/perception_backend_replacement/p5a_dwpose_representation_v2_01/`. The next allowed experiment is P5-B temporal recognition training/evaluation using this representation; no Android implementation exists yet.

| Component | Location | Contract | Input → output | Status |
|---|---|---|---|---|
| P5-A DWPose Representation V2 builder | `pipeline/features/dwpose_representation_v2.py`, `eval/runtime_diagnostics/p5a_dwpose_representation.py` | Deterministic current-frame DWPose XY+score+validity representation with embedded geometry-observed masks and body-relative normalization; human V2 truth is evaluation-only | preserved native DWPose 133-keypoint output → frame `[238]`, padded sequence `[96,238]`, diagnostics | `DWPOSE_REPRESENTATION_V2_238`; offline only; P5-A passed; production v3.0 unchanged |

## 2026-09-04 — Contract and component catch-up through P7F-A

Historical sections above are preserved. See [current progress](recognition_upgrade/PROGRESS_THROUGH_P7FA_2026_09_04.md) and frozen P7B/P7C
artifacts before implementation. This imprint records existing contracts, not a new schema version.

| Lane | Shape / meaning | Current boundary |
|---|---|---|
| Production schema3.0 | [96,258] legacy MediaPipe/S4 recognizer input | Unchanged production path |
| Offline V2 | [96,238] DWPOSE_REPRESENTATION_V2_238 | PFCE_MATCHED + EC_P3 offline candidate; not current Android semantics |
| Family-A frame ABI | APPHEAR_FAMILY_A_FRAME_V1:202float32 + metadata | Deterministic adapter, not direct neural targets |
| Family-A native graph | RGB[1,384,384,3]; heatmaps[1,96,96,50]; assignment logits[1,1,1,2] | FA_DS_SPATIAL_V1 random-weight runtime skeleton |

Family-A ABI offsets: LH0..83, RH84..167, eight BODY joints168..199, observed flags200..201;
each point quartet is(source-pixel x,y,confidence,valid). BODY order is bilateral shoulders,
elbows, wrists, hips. Native FA channels0..20/21..41/42..49 map to DWPose91..111/112..132/5..12.
The50 decoded XY/confidence estimates represent150 scalar meanings, not202 direct targets.
Body validity is independent of hand-observed flags. Hand and body wrist estimates stay distinct.

Upright unmirrored source pixel centers and anatomical hand slots are frozen. Unknown identity
is explicit, never screen-x/order/dominance. Invalid points/unused hands are zeroed with explicit
states; no synthetic Z or temporal repair. Confidence is uncalibrated sigmoid peak evidence,
not DWPose-score equivalence or physical visibility. Validity, observed aggregation and
eight-body normalization policies remain unconfigured; no S5/recognizer payload is authorized.

| Component | Location | Contract | Input → output | Status |
|---|---|---|---|---|
| P7-D reference math | android/app/src/debug/java/com/example/apphear/p7d/P7dMath.kt | P7C_RGB_LETTERBOX384_V1 / P7C_NATIVE_HEATMAP_LOCAL3_V1 | RGBA + transform / logits → FP32 input / raw evidence | Preserved debug reference; not production |
| P7D-R1 JVM path | android/app/src/debug/java/com/example/apphear/p7dr1/P7dr1Math.kt | Same frozen preprocessing/decoder | Reusable buffers → identical semantics | Parity PASS; compute below screen; preserved reference |
| P7D-R2 native path | android/app/src/debug/cpp/p7dr2.cpp; android/app/src/debug/java/com/example/apphear/p7dr2/P7dr2Native.kt | Same P7C semantics through JNI | Coarse frame/tensor buffers → input / decoded evidence | Parity and compute screen PASS; debug-only/default-off |
| P7E cadence harness | android/app/src/debug/java/com/example/apphear/p7e/ | Frozen R2 V3 plus fixed15 AE policy | Live frames → timing/metadata only | Integrated BELOW_SCREEN; no recognizer/S5/S7 |
| P7G01 controlled Family-A utility builder | `artifacts/recognition_upgrade/p7g01_family_a_downstream_recognition_utility_gate/run_p7g01.py` | Experiment-only T50/S1-50/S2-50 body-relative XY + common teacher eligibility + first-order velocity; 96×250 | frozen ASL Citizen internal TRAIN/DEV geometry → parity-locked recognition tensors and a shared causal-TCN gate | Offline-only; production schema v3.0 and Android S4 unchanged; no train/serve claim |
| P7G02 Teacher-50 temporal ceiling builder | `artifacts/recognition_upgrade/p7g02_teacher50_credible_temporal_ceiling_01/run_p7g02.py` | Experiment-only Teacher-50 body-relative XY + point validity + source-frame-delta velocity; unique chronological observations in `[64,250]`, explicit `[64]` frame-validity mask, tail padding, and masked causal-TCN pooling | frozen P7G01 ASL Citizen TRAIN/DEV Teacher-50 geometry → time-faithful masked recognition tensors and one comparable Teacher-50 ceiling run | Offline-only; production schema v3.0, Family-A frame ABI, Android S4, anatomical mapping, and teacher coordinates unchanged; no train/serve or production claim |
| P8-A Student-1 FP32 TFLite exporter/parity packager | `artifacts/recognition_upgrade/p8a_student1_tflite_export_parity_android_readiness_01/run_p8a.py` | Restores the sealed Student-1 `ckpt-23`, exports only the scientifically trained heatmap path, verifies builtin-only TFLite/XNNPACK execution, and packages hashed Android preprocessing/decoder goldens | upright unmirrored RGB → external P7C half-pixel letterbox float32 `[1,384,384,3]` in `[-1,1]` → TFLite heatmap logits `[1,96,96,50]` → external `P7C_NATIVE_HEATMAP_LOCAL3_V1` source XY | Family-A engineering baseline only; channels LH `0..20`, RH `21..41`, BODY `42..49`; no assignment/presence output, production schema v3.0/S4/recognition change, or accuracy claim |
| P8-B Student-1 Android debug perception path | `android/app/src/debug/java/com/example/apphear/p8b/`, `android/app/src/debug/assets/p8b/` | Loads and hash-checks the exact P8-A FP32 model, reproduces the frozen external preprocessing/decoder, draws display-only raw geometry, and records bounded mobile timing/coordinates through an explicit ADB-only activity | CameraX upright unmirrored RGBA → reusable float32 `[1,384,384,3]` → exact Student-1 heatmaps `[1,96,96,50]` → reusable source-plane XY arrays and debug-only overlay/telemetry | Debug source set only; P8-A model hash pinned; anatomical LH/RH coordinates are never display-mirrored internally; no presence semantics, production schema v3.0/S4, S5-S7, sentence, or recognition connection |
| P8-C1 native preprocessing adapter | `android/app/src/debug/java/com/example/apphear/p8c1/P8c1NativePreprocessor.kt`, unchanged `android/app/src/debug/{cpp/p7dr2.cpp,java/com/example/apphear/p7dr2/P7dr2Native.kt,jniLibs/arm64-v8a/libp7dr2.so}` | Reuses the parity-proven P7D-R2 native CameraX preprocessing kernel in the exact P8-B Student-1 debug path, with static fixture and eight-frame same-camera JVM parity hard gates before timing | CameraX strided RGBA + rotation → cached native half-pixel upright/unmirrored letterbox → reused float32 `[1,384,384,3]`; all later P8-B stages unchanged | Debug-only P8-C1 implementation variable; exact zero static/live tensor difference on Xiaomi; no decoder, model, precision, threads, overlay, production schema v3.0/S4, recognition, S5-S7, or sentence change |
| P8-C2 native heatmap-only decoder adapter | `android/app/src/debug/{cpp/p8c2_decoder.cpp,java/com/example/apphear/p8c2/,jniLibs/arm64-v8a/libp8c2decoder.so}` plus the isolated P8-B debug runner adapter | Reuses only the parity-proven P7D-R2 50-heatmap local-3 peak/refinement and inverse-letterbox math, scans the reusable direct TFLite output in one JNI call, and excludes the obsolete auxiliary identity tensor | direct float32 `[1,96,96,50]` heatmaps → reusable input/source XY `[50,2]` + 50 peak cells; zero formal heatmap copy to Kotlin | Debug-only P8-C2 implementation variable; static and eight-frame same-heatmap parity hard gates; no assignment/presence/confidence output, native-preprocessing change, channel swap, production schema v3.0/S4, recognition, S5-S7, or sentence change |
| P8-C3A overlay topology verifier | `android/app/src/main/java/com/example/apphear/p8b/P8bOverlayView.kt`, `android/app/src/androidTest/java/com/example/apphear/p8c3a/` | Exposes the unchanged canonical 23-edge hand and 8-edge BODY visualization topology plus the display-only `FILL_CENTER`/front-preview mirror transform; retains an opt-in zero-edge `POINTS_ONLY` local-index view for the historical debug path | source-plane XY `[50,2]` + upright source geometry + preview mirror flag → display-only LH/RH/BODY points and optional canonical edges | Renderer/transform promoted to main for reuse; historical Student verification remains debug-only. Model coordinates stay unmirrored and semantic labels never swap; no feature ABI, model, preprocessing, decoder, presence, recognition, or sentence change |
| Shared Candidate01 phone overlay renderer | `android/app/src/main/java/com/example/apphear/perceptionvnext/PerceptionVNextOverlayView.kt`, `android/app/src/main/java/com/example/apphear/ui/OverlayView.kt`, `android/app/src/main/java/com/example/apphear/ui/PhoneOverlayFrame.kt` | One validated presentation-only renderer for debug and real-app front-camera views; draws hand/body bones, proposal ROI, and observed-hand presence with fill-center/front-mirror transform; main view clears on stop | existing raw-v1 display copy (hand XY/validity/observation/presence/ROI, body XY/support, source dimensions) → canvas pixels only | Targets current Candidate01 raw-v1 display, not `[378]`/Recognition V2; no data flows back into perception, features, S2, event, materializer, or recognizer. Connected pixel-equivalence and clear tests passed |
| P8-C3B1 synchronized controlled Student capture | `android/app/src/debug/java/com/example/apphear/p8c3b1/P8c3b1CaptureActivity.kt`, `artifacts/recognition_upgrade/p8c3b1_controlled_live_student_geometry_capture_01/analyze_p8c3b1.py` | Operator-confirmed, bounded debug capture copies the exact upright/unmirrored analyzer image and the same-invocation 50-channel Student evidence into a monotonic per-frame record; offline packaging validates hashes, transforms, labels, compactness, location, jitter, crossing continuity and no-hand behavior without Teacher or recognition | one P8-C2 analyzer callback → lossless source PNG + source/model XY `[50,2]` + peak cells/logits + transform/physical-condition metadata; 320 canonical frames | Debug-only observational component; frozen model/preprocessor/decoder/channel order unchanged; raw heatmap maxima are uncalibrated and never become presence; no production schema v3.0/S4, recognition, S5-S7, sentence or training change |
| P8-C3B2 exact-frame Teacher reference comparator | `artifacts/recognition_upgrade/p8c3b2_exact_phone_frame_teacher_reference_01/run_p8c3b2.py` | Runs the frozen governed DWPose-L reference once on each of the 320 canonical P8-C3B1 upright/unmirrored PNGs, maps native 133 points to the immutable Family-A 50 channels, and compares those outputs with preserved same-frame Student records using raw, wrist-aligned and non-reflective similarity-aligned errors plus bounded condition/temporal/visual diagnostics | canonical source PNG + preserved Student source XY `[50,2]` → native Teacher points/scores `[133]`, mapped Teacher-50, eligibility, same-frame diagnostic artifacts | Offline evidence-only component; score is diagnostic and never gates geometry; no Student rerun, mirror counterfactual, MediaPipe, Android, recognition, training, channel remap or production schema v3.0/S4 change |
| P8-C3B3 frozen Student mirror counterfactual | `artifacts/recognition_upgrade/p8c3b3_frozen_student_mirror_counterfactual_01/run_p8c3b3.py` | Applies exactly one source-plane horizontal reflection to each canonical P8-C3B1 frame, runs the unchanged Student-1 TFLite/preprocessing/local-3 decoder, reverses only X back into the original source plane, and performs paired same-frame comparison with preserved B1 Student and B2 Teacher evidence | canonical upright/unmirrored RGB + frozen Student model → mirrored-source Student inference → original-plane counterfactual Family-A XY `[50,2]` and paired diagnostic artifacts | Offline evidence-only component; channels remain LH `0..20`, RH `21..41`, BODY `42..49` with no swap; no feature ABI, Student weights, Teacher, Android, MediaPipe, recognition, presence, S5-S7 or production mirror change |

No production F/S4 update or new production skew test occurred during this context catch-up.
Runtime parity validates implementation math, not landmark correctness. P7F-A found geometry
pseudo-supervision support but unresolved identity/missingness/calibration and Sem-Lex alignment.
No old EC_P3 checkpoint transfer, tensor padding/truncation or automatic production promotion.

## Perception vNext recognition-utility contracts — Candidate 01 (2026-09-13)

These are **experimental recognition-utility contracts**, not a production promotion and not a
replacement for production schema v3.0. Raw schema `apphear.perception_vnext.raw.v1` records the
Candidate 01 evidence. Derived schema `apphear.perception_vnext.recognition.v1` is the sole input
to the utility TCN. They remain milestone-local until full signer-disjoint utility evidence exists.

- Source plane: upright, unmirrored source-pixel coordinates. Front-preview mirroring is display
  only and never changes anatomical slots.
- Hand slots: DWPose-t COCO-WholeBody indices `91..111` are anatomical left and `112..132` are
  anatomical right. The crop refiner cannot reorder or relabel them.
- Each hand slot supplies 21 DWPose proposal-support values. Each accepted hand observation also
  supplies 21 `(x_source,y_source)` refined joints, 21 explicit geometric validity values, one
  current-crop group presence value, one explicit observed state, and its current-frame square ROI.
  MediaPipe handedness is diagnostic only. Its crop-relative Z and world outputs are diagnostic
  only and must not enter a feature vector as global depth.
- Each rejected/unavailable hand has `observed=false`; placeholder coordinates carry no evidence.
  There is no carry-forward, optical flow, pose-wrist recovery, fabricated geometry, or temporal
  imputation.
- Body context exposes DWPose-t whole-body indices `5..12` (bilateral shoulders, elbows, wrists,
  and hips), each with source XY, native support, and explicit point validity. A body point is valid
  only when XY/support are finite, XY is inside the upright source plane, and support is `>=0.30`.
  Group `body_available` requires at least 6/8 valid points. This makes the existing PHONE_01 rule
  explicit; it does not alter its threshold.
- Candidate thresholds are component-local PHONE_01 observation rules, not a production contract:
  a crop proposal needs at least 5/21 current-frame DWPose-t hand points at support `>=0.10`; the
  refiner accepts group presence `>=0.50` with at least 18/21 in-crop XY joints.
- Frame metadata includes increasing source frame index and timestamp, source dimensions/identity,
  timestamp provenance, and the fixed `UPRIGHT_UNMIRRORED_SOURCE_RGB` semantic. The raw artifact
  contains no normalized coordinates, padding, interpolation, carry, or synthetic depth.
- Recognition, S5, S7, sentence generation, and the AppHear conversational UI remain disconnected.

### Derived frame layout — `apphear.perception_vnext.recognition.v1`

The derived width is **208 float32 values**. Invalid XY is zero only in this derived artifact;
validity/observed channels remain authoritative and the raw artifact is preserved separately.

| Offset | Width | Meaning |
|---:|---:|---|
| `0..83` | 84 | anatomical LH: 21 × normalized `(x,y)`, DWPose proposal support, effective validity |
| `84..167` | 84 | anatomical RH: same layout |
| `168..199` | 32 | body indices 5–12: 8 × normalized `(x,y)`, DWPose support, point validity |
| `200..205` | 6 | LH presence/observed, RH presence/observed, body available, body-normalization valid |
| `206..207` | 2 | clipped real-frame delta seconds, elapsed fraction of actual clip duration |

Normalization is current-frame and isotropic. It prefers bilateral shoulders, then bilateral hips,
then the extent of at least two valid body points. If body evidence cannot define a stable anchor
and scale, source-frame center/minimum dimension is used and `body_normalization_valid=0`.

The temporal tensor is `[96,208]` plus a `[96]` boolean sequence mask. Dense uses chronological
actual observations and selects unique frames nearest to evenly spaced timestamp targets only when
more than 96 exist. PHONE_01 sparse uses unique actual observations nearest to a timestamp grid
derived from the governed completed-FPS evidence (`5.606840672873506` in the pinned audit). Both
post-pad with zero and mask false; neither copies or interpolates an observation. Selected source
indices and timestamps are saved with each view.

### Experimental Representation V2 — `apphear.perception_vnext.recognition.v2`

This contract is the **frozen Phase-2 production-candidate representation** for active Phase 4A.
An exact debug-only Android/Kotlin S4 port now exists and passed Gate 1 on the physical Xiaomi at
`1.1920929e-7` max absolute error with zero discrete mismatches. The frozen ordinary V2 TCN also
passed Gate 2 as an FP32, standard-builtins-only TFLite model on the same phone. Phase 3 is paused,
not solved. V2 derives only from the same immutable
raw-v1 observations and preserves the same dense/sparse source indices, `[96]` sequence mask,
anatomical hand ownership and upright/unmirrored semantics. Its initial representation gate was
`INCONCLUSIVE`; an independent implementation/math audit reproduced every metric, confirmed its
RMS dimension normalization and selected-sparse motion, and classified the evidence
`V2_GATE_VALID_PROMISING`. The single controlled V2 TCN run is now complete and materially improves
signer-disjoint DEV recognition in dense and phone-sparse views. V2 and the ordinary V2 TCN are the
frozen Phase-4A candidates. Android V2 feature parity, recognizer-runtime parity, and known-TRAIN
end-to-end composed replay now pass. Bounded live recognition remains unstarted, and no production
promotion is authorized.

The V2 tensor is `[96,350]` float32 plus `[96]` boolean mask:

| Offset | Width | Meaning |
|---:|---:|---|
| `0..129` | 130 | LH static: 20 palm-local unit bone vectors + validity; 15 signed joint-angle sine/cosine pairs + validity; five palm-local fingertip XY + validity; body-relative wrist/center, body-frame palm axis, presence/observed/mean proposal support/reference-valid |
| `130..259` | 130 | RH static: same anatomical layout |
| `260..295` | 36 | body: six body-frame unit limb vectors + validity, eight native supports, eight point-validity values, group availability and body-frame validity |
| `296..302` | 7 | inter-hand body-frame wrist/center displacement, distances and both-observed state |
| `303..323` | 21 | LH timestamp-aware motion: body-frame wrist/center velocity and five palm-local fingertip velocities + seven validity values |
| `324..344` | 21 | RH timestamp-aware motion: same layout |
| `345..347` | 3 | inter-hand center-delta velocity XY + validity |
| `348..349` | 2 | real selected-observation delta seconds and elapsed clip fraction |

The body frame uses the current shoulder pair, then hip pair; its lateral axis is anatomical
right-to-left, its perpendicular is the down axis, and pair width is scale. Source-frame
center/minimum dimension is the explicit invalid fallback. Each hand frame uses wrist, index,
middle and pinky MCP geometry; palm length/width set scale, finger geometry is expressed in that
local frame, and sign location remains in the body frame. Velocities use actual selected timestamp
deltas and `tanh(v/4)` bounded units/second. Sparse motion is recomputed after sparse selection, so
it never presents a dense-frame delta as a phone observation. Invalid derived values are zero only
beside explicit validity; no Z, stale carry, interpolation or copied evidence exists.

### Phase-5 offline segmentation wrapper — `apphear.segmentation.sign_event.v1`

Phase 5.1 adds an offline-only boundary wrapper around immutable
`apphear.perception_vnext.raw.v1` observations. It does **not** alter raw-v1, Recognition V2,
schema v3.0, Candidate01, the recognizer, or any Android behavior. Segmentation runs before any
future Recognition V2 sequence generation and uses source-timestamp order only; it never
interpolates, duplicates, stale-carries, or manufactures observations.

The reference activity channels are unit-separated and explicitly valid: refined-hand motion in
body-frame units/second, refined-hand image fallback in minimum-image-dimensions/second, proposal
ROI-center fallback in minimum-image-dimensions/second, and upper-limb unit-vector delta/second.
Each hand selects at most one channel through the hierarchy refined-body → refined-image →
proposal-image → unknown. Body articulation is a separate family. Missing evidence is unknown,
never zero or quiet. State persistence, pre/post roll, hard-gap handling, and re-arm use actual
source elapsed time.

A SignEvent contains the event/segmenter/config identities, source session and raw-schema
identities, image semantics and ordering declaration, detected onset/offset identities, padded
start/end identities, observation count, event-local state-transition trace, signal-validity
summary, quality flags, gap summary, re-arm outcome, and an inclusive canonical `raw_sequence`
slice. Each boundary identity records the source observation index, original frame index, and
source timestamp in milliseconds and nanoseconds. The raw slice retains all original raw-v1 arrays
and scalar provenance, including `frame_runtime`; recursive source-slice and JSON-round-trip
equality are required. Recognition V2 is regenerated only after a future promoted SignEvent; this
milestone does not generate V2.

The Phase-5.1 reference is **not promoted**. Exact calibration-only feasibility over attempts
002/003/005/007/009 found zero joint feasible motion patterns under the initial 250 ms start,
500 ms quiet-end, 300 ms pre-roll, 250 ms post-roll, and 700 ms re-arm policy; attempt 009/TABLE
alone had zero feasible end patterns. Status is
`CALIBRATION_INSUFFICIENT_FOR_CURRENT_TEMPORAL_POLICY`; no runnable thresholds were frozen and
offline holdout attempts 004/006/008/010 remain unopened. The schema name therefore documents the
validated wrapper shape only, not a production operating contract.

Phase 5.1R varied only end-quiet persistence over all 49 behaviorally distinct calibration
source-timestamp breakpoints below 500 ms. No breakpoint produced a joint feasible low-threshold
motion pattern across attempts 002/003/005/007/009. The recovery classification is
`END_POLICY_RECOVERY_NO_GLOBAL_FEASIBLE_DURATION`; thresholds remain unfrozen, holdout
004/006/008/010 remains unopened, and the wrapper is still unpromoted. This is a feasibility
finding, not a SignEvent/raw-v1 contract revision.

Phase 5.1S decomposed all 49 duration-specific regions over all 1,028,193 discrete low-threshold
tuples without changing the component. At the largest TABLE-feasible duration, TABLE requires
`H_proposal_image <= 0.09955792507085848`, while the closest conflicting attempt, HOME, requires
`H_proposal_image >= 0.24807557246229403`; every TABLE/non-TABLE pair is disjoint on this dimension.
This absolute-threshold gap is the numerical manifestation of the primary attribution
`RECOVERY_AS_ACTIVITY_CONFLICT_SUPPORTED`: the oracle-only diagnostic that ignores post-oracle
renewed activity makes all five structurally feasible at the TABLE-side anchor, while the three
quiet-fusion counterfactuals do not. This result does not authorize an oracle-dependent runtime
rule, a threshold change, or any repair; holdout remains sealed and the wrapper remains unpromoted.

| Component | Location | Contract | Input → output | Status |
|---|---|---|---|---|
| Perception vNext DWPose-t exporter/evaluator | `model/perception_vnext/export_dwpose_t.py`, `eval/runtime_diagnostics/perception_vnext_phone_01.py` | Single-pass DWPose-t 256x192 SimCC with frozen ONNX hash and source restoration; compares only against governed P8-C3B1 frames and frozen DWPose-L Teacher evidence | upright source RGB → ONNX NCHW `[1,3,256,192]` → current-frame 133-point source XY/support + body/hand diagnostics | PHONE_01 candidate evidence; no training or production promotion |
| Perception vNext current-frame ROI + crop refiner | `pipeline/perception_vnext/{hand_roi,hand_refiner}.py`, `eval/runtime_diagnostics/perception_vnext_hand_refiner.py` | Same-frame DWPose-t anatomical proposal → direct MediaPipe 224x224 hand-landmark submodel; explicit group presence/validity; Z/world diagnostic only | 21 coarse slot points/support + source RGB → optional square crop → 21 refined source-XY joints + current-frame observed state | Offline viability passed on 320 frozen Xiaomi frames; debug candidate only |
| Perception vNext Android PHONE_01 harness | `android/app/src/debug/java/com/example/apphear/perceptionvnext/`, `android/app/src/debug/assets/perception_vnext/` | Build-flagged and explicit-intent CameraX activity with pinned DWPose-t ONNX and hand-refiner TFLite assets, source-coordinate overlay, runtime profiler, and the governed 14-step/320-frame condition script | CameraX RGBA → upright/unmirrored DWPose input + current-frame hand crops → provisional hand/body observations, overlay, and device evidence JSON | Complete physical Xiaomi run: geometry pass, runtime fail; production v3.0 unchanged |
| Perception vNext native image-to-tensor kernel | `android/app/src/debug/cpp/perception_vnext_preprocess.cpp`, `android/app/src/debug/java/com/example/apphear/perceptionvnext/{PerceptionVNextNativePreprocessor,PerceptionVNextNativeParity}.kt`, `android/app/src/debug/jniLibs/arm64-v8a/libperceptionvnext.so` | Reusable arm64 JNI RGBA rotation/bilinear/normalization and ROI-resampling implementation; four live frames must pass mean `<=1e-6` and max `<=1e-5` against the Kotlin reference before measurement | CameraX direct RGBA buffer + source geometry → direct NCHW DWPose Float32 buffer and direct NHWC hand-crop Float32 buffer | Live parity bit-exact; SHA-256 `4187118fd33512de000056a8070bec85fd50f952da8ab8545552c33f8b85bfc5`; debug-only evidence component |
| Candidate 01 raw/offline extractor | `pipeline/perception_vnext/{offline_candidate01,recognition_schema}.py` | `apphear.perception_vnext.raw.v1`; pinned ONNX/TFLite hashes; explicit hand/body validity and no temporal state | governed isolated video/current RGB → separate per-clip raw current-frame observations | Implemented; exact 16-frame Android parity PASS; full governed 4,742-clip TRAIN+DEV extraction PASS |
| Candidate 01 Android exact-frame fixture | `android/app/src/debug/java/com/example/apphear/perceptionvnext/{PerceptionVNextBitmapPreprocessor,PerceptionVNextFixtureActivity}.kt` | same raw v1 semantics over bounded hashed PNG fixtures using the PHONE_01 native kernel and model runners | upright/unmirrored hashed PNG → Android raw-v1 JSONL | 16/16 structural parity; body max `0 px`, refined-hand max `0.000126 px`; debug-only |
| Candidate 01 recognizer feature/temporal builder | `pipeline/perception_vnext/recognition_schema.py` | `apphear.perception_vnext.recognition.v1`, `[96,208]` plus `[96]` mask | raw v1 chronological observations → separate dense and measured-phone-sparse tensors | Full governed extraction PASS: 4,742 clips, 236 classes, TRAIN 3,926 and DEV 816; protected TEST untouched |
| Perception vNext utility TCN | `model/perception_vnext/recognition_utility_236.py`, `model/config/recognition_upgrade/perception_vnext_recognition_utility_236_01.json` | one established 4-block/64-channel causal TCN with mask-aware pooling; 236 outputs; post-fit save/reload validation targets `final.keras` because early stopping restores best weights while `latest.keras` retains the last epoch | dense+sparse TRAIN only → combined signer-disjoint DEV model selection/evaluation | Full extraction/training/evaluation complete; governed result `GENERALIZATION_LIMITED` with secondary cadence loss: DEV dense/sparse Top-1 `41.30%/34.93%`, TRAIN–DEV gaps `35.45/35.17` points; not promoted to phone/UI |
| Perception vNext generalization attribution analyzer | `eval/runtime_diagnostics/perception_vnext_generalization_attribution.py` | read-only consumer of `apphear.perception_vnext.raw.v1` and `apphear.perception_vnext.recognition.v1`; calls the canonical derived-feature implementation for normalization state and refuses schema, governance, signer-split, class-coverage, checkpoint-hash, or prediction-parity drift | saved raw/features/index + frozen `best.keras`/`evaluation.json` → per-clip, per-signer, class-diversity, source, confusion, normalization-shift, and cadence evidence package | Bounded audit PASS; exact DEV prediction parity; `MIXED_GENERALIZATION_FAILURE`, medium confidence; no extraction/training/schema/runtime change |
| Perception vNext hierarchical TRAIN sampler | `pipeline/perception_vnext/hierarchical_sampler.py`, `model/perception_vnext/recognition_utility_236.py`, `model/config/recognition_upgrade/perception_vnext_sampling_generalization_236_01.json` | versioned `apphear.perception_vnext.training_sampler.v1`; deterministically balances class, then signer within class, then samples a clip uniformly with replacement; seed identity includes run seed and epoch; resume state pins the completed epoch/checkpoint/draw identity | governed TRAIN index rows → exactly 3,926 clip draws/epoch → unchanged dense+sparse pair per draw (7,852 views, 246 batches) | Sampling-only Phase-3 experiment complete and classified `SAMPLING_HARMFUL` (medium confidence): DEV dense/sparse Top-1 `40.07%/34.31%` versus control `41.30%/34.93%`, Top-5 `70.10%/63.48%` versus `73.53%/67.28%`; reduced TRAIN→DEV gaps came from lower TRAIN accuracy, not better DEV. Do not promote or automatically try another sampler; raw-v1/recognition-v1 and all other components remain unchanged |
| Governed corpus relocation resolver | `pipeline/perception_vnext/governance.py` | preserves the pinned TRAIN/DEV manifest identities while resolving only the explicit ASL Citizen root move `F:\ASL DATASET\ASL CITIZEN` → `G:\ASL CITIZEN\ASL CITIZEN`; original manifest path wins when present | immutable manifest video/span path → verified existing current path, with relocation counts in the audit | Governed audit PASS: all 4,742 TRAIN+DEV videos and spans resolve; one-TRAIN/one-DEV Candidate 01 extraction smoke PASS; protected TEST remains undiscovered |
| Experimental recognition-v2 builder/gate | `pipeline/perception_vnext/recognition_schema_v2.py`, `eval/runtime_diagnostics/{perception_vnext_representation_v2_gate,perception_vnext_representation_v2_gate_validation}.py` | `apphear.perception_vnext.recognition.v2`; removes global similarity transform and hand scale from articulation while retaining body-relative sign location, inter-hand geometry, explicit evidence state and selected-timestamp motion | frozen raw-v1 clips → parity-locked dense/sparse `[96,350]` + mask → independently verified no-training shift/signer/class diagnostics | All 4,742 V2 packages finite and V1 source-index/mask-identical. Independent audit reproduced metrics within `1.4e-6`, confirmed RMS dimension normalization and sparse motion, and classified `V2_GATE_VALID_PROMISING`; TRAIN↔DEV distance remains a declared risk. Android port is registered separately below; no production promotion |
| Recognition-v2 Android Gate-1 transformer | `android/app/src/debug/java/com/example/apphear/perceptionvnext/{RecognitionV2,RecognitionV2ParityVerifier}.kt`, `android/app/src/androidTest/java/com/example/apphear/perceptionvnext/RecognitionV2ParityInstrumentedTest.kt` | frozen `apphear.perception_vnext.recognition.v2`; exact Python layout/normalization, dense and PHONE_01 selection, selected-timestamp motion, zero+valid invalid semantics, zero tail padding and false mask | Candidate 01 raw-v1 chronological observations → `[96,350]` FP32 + `[96]` mask + selected indices/timestamps | Gate 1 PASS on physical Xiaomi M2101K7AG. Deterministic 10-clip TRAIN corpus: dense max/p95/mean absolute `1.1920929e-7/0/1.0493871e-10`; sparse `1.1920929e-7/0/2.1365850e-11`; zero selection/timestamp/mask/discrete mismatches. Padding, invalid states and selected-timestamp sparse motion PASS. Debug-only and frozen during Gate 2 |
| Ordinary V2 TCN Android Gate-2 runtime | `deploy/export_v2_tcn_gate2.py`, `android/app/src/debug/java/com/example/apphear/perceptionvnext/RecognitionV2TfliteParityVerifier.kt`, `android/app/src/androidTest/java/com/example/apphear/perceptionvnext/RecognitionV2TfliteParityInstrumentedTest.kt` | source checkpoint SHA `8107accb…340`; explicit schema check for `apphear.perception_vnext.recognition.v2`; standard TFLite builtins-only FP32, no quantization/Select TF Ops; inputs `[1,96,350]` float32 + `[1,96]` bool mask; output `[1,236]` float32 softmax probabilities; vocabulary SHA `a7d7b08d…39b` | exact Gate-1 TRAIN-only V2 tensors and masks → frozen ordinary TCN probabilities/Top-5 | Gate 2 PASS. Keras↔host-TFLite max/p95/mean abs `4.7684e-7/1.4581e-9/1.2949e-9`; Keras↔physical-Xiaomi `3.5763e-7/1.7462e-9/1.4873e-9`; zero Top-1, Top-5 membership, or Top-5 order mismatches across 10 dense + 10 sparse views. Keras/host/Android padded-garbage invariance exact. Android TFLite 2.16.1, CPU 4 threads, XNNPACK requested, no GPU/NNAPI; recognizer-only latency p50/p95/max `1.693/1.823/1.859 ms`. Debug-only parity component; no CameraX/live recognition/Gate 3 |
| Recognition-v2 Android Gate-3 composed replay | `android/app/src/debug/java/com/example/apphear/perceptionvnext/RecognitionV2EndToEndReplayVerifier.kt`, `android/app/src/androidTest/java/com/example/apphear/perceptionvnext/RecognitionV2EndToEndReplayInstrumentedTest.kt`, `eval/runtime_diagnostics/finalize_phase4a_gate3.py` | fail-closed checks for raw-v1, frozen recognition-v2, `[96,350]` + `[96]` mask, 236 outputs, authorized TFLite SHA and vocabulary SHA; fully rewrites reusable feature/mask/output buffers | same 10 Gate-1 TRAIN raw-v1 fixtures → Android V2 dense+sparse tensors → authorized Gate-2 FP32 TFLite → 236 probabilities, Top-5 and canonical gloss | Gate 3 PASS on Xiaomi. V2 max abs `1.1921e-7`; composed probability max abs `4.1723e-7`; zero selection/timestamp/mask/discrete, Top-1, Top-5 membership/order or gloss-map mismatches. Forward/reverse and dense↔sparse order exact across 14,160 comparisons. Debug-only saved-raw replay; no CameraX/live recognition |
| Recognition-v2 Android Gate-4A1 live bounded consumer | `android/app/src/debug/java/com/example/apphear/perceptionvnext/{PerceptionVNextLiveRecognitionActivity,RecognitionV2LiveRecognizer}.kt`, `eval/runtime_diagnostics/{run_phase4a_gate4a1.ps1,finalize_phase4a_gate4a1.py}` | debug-only fail-closed consumer of `apphear.perception_vnext.raw.v1` and frozen `apphear.perception_vnext.recognition.v2`; source-timestamp START/STOP, strictly chronological post-STOP drain sentinel, actual live observations with no PHONE_01 re-simulation, fully rewritten `[96,350]`/mask/output buffers, authorized model/vocabulary identities | warm Candidate 01 CameraX observations inside `T_start <= source_timestamp <= T_stop` → frozen V2 DENSE selection (only 96-step truncation if needed) → authorized FP32 TFLite → 236 probabilities/Top-5 plus replay-complete evidence | Gate 4A-1 PASS on Xiaomi for five manually bounded attempts. Live→offline V2 max/p95/mean abs `1.1921e-7/0/3.6046e-11`; probability `3.8743e-7/1.1671e-9/2.0584e-9`; zero Top-1/Top-5 membership/order mismatches. Technical plumbing only: semantic Top-1 `1/5`, expected-in-Top-5 `2/5`, tester status UNKNOWN and mean LH/RH observed rates `4.15%/24.62%`; no production UI/commit/automatic boundaries |
| Gate-4A1B controlled live-input diagnostics | `android/app/src/debug/java/com/example/apphear/perceptionvnext/Gate4A1bVisualDiagnostics.kt`, `eval/runtime_diagnostics/{phase4a_gate4a1b_controlled_recovery.py,run_phase4a_gate4a1b.ps1}` | debug-only observer around frozen `apphear.perception_vnext.raw.v1`; never changes Candidate 01 inference or frozen V2. Deterministically retains first/every-10th/last and hand-state-transition upright-unmirrored RGB plus DWPose body/proposals, ROIs, refiner state, luminance/sharpness, timestamps, and hashes | live CameraX/Candidate01 result + matching source frame → bounded diagnostic JPEG/JSON and host-retained replay package | Gate 4A-1B technical PASS on 10 valid Xiaomi attempts with V2/probability max abs `1.1920929e-7`/`5.9604645e-7`, zero Top-1/Top-5 mismatches. Attribution `MIXED_OR_INCONCLUSIVE`: 7/10 attempts had 87.5–100% active-interval hand continuity; TABLE contact showed refiner collapse but its exact TRAIN reference also had 0% refined-hand observation; long lead-in/out and incomplete body-reference framing confounded whole-window evidence. No feature-contract change |
| Gate-4A1C oracle temporal-boundary replay | `eval/runtime_diagnostics/phase4a_gate4a1c_oracle_boundary_replay.py` | offline-only causal audit over retained Gate-4A1B raw-v1; boundary lock and SHA occur before inference, use one-observation fixed margins, and every trimmed sequence is rebuilt through frozen recognition-v2 so selected-timestamp motion, dt and elapsed fraction are recomputed rather than sliced | frozen live raw-v1 + blinded oracle bounds → fresh `[96,350]`/mask → frozen ordinary V2 Keras probabilities and full-vs-oracle evidence | Independently validated PASS on 10 retained attempts: Top-1 `2/10→7/10`, expected-in-Top-5 `5/10→8/10`, median expected probability `0.053839→0.585159`, median rank `5→1`; classification `TEMPORAL_BOUNDARY_PRIMARY_EFFECT_SUPPORTED`. Phase-4 causal work closed; no Candidate01, V2, model or temporal-contract change |
| Phase-5.1 offline segmenter reference | `pipeline/perception_vnext/segmentation/`, `eval/runtime_diagnostics/{phase5_1_offline_segmenter,phase5_1r_end_policy_recovery}.py` | offline-only `apphear.segmentation.sign_event.v1`; multi-family unit-safe activity, explicit unknown validity, source-time hysteresis/persistence, pre/post roll, raised-hand re-arm, hard-gap truncation, and canonical raw-v1 slice immutability | retained calibration raw-v1 + locked oracle intervals → exact feasibility proofs, engineering state/gap fixtures, and non-runnable SignEvent contract fixture | Phase 5.1 stopped at 500 ms; Phase 5.1R then evaluated all 49 behaviorally distinct end-quiet timestamp breakpoints below 500 ms and found 0 globally feasible durations. Final recovery classification `END_POLICY_RECOVERY_NO_GLOBAL_FEASIBLE_DURATION`; thresholds not frozen, LOO not run, holdout 004/006/008/010 not accessed, no Android/V2/recognizer/training change |
| Controlled recognition-v2 TCN runner | `model/perception_vnext/recognition_v2_236.py`, `model/config/recognition_upgrade/perception_vnext_representation_v2_236_production_01.json` | Accepts only recognition-v2 `[96,350]` while contract-checking that seed, TCN architecture, optimizer/loss, clip-uniform sampling, dense+sparse weighting, population and validation policy equal the V1 control | V2 dataset → resumable one-run TCN checkpoints and matched TRAIN/DEV dense/sparse evaluation | Controlled full run complete: DEV dense/sparse Top-1 `50.25%/39.95%` vs V1 `41.30%/34.93%`, macro-F1 `48.55%/38.15%` vs `38.70%/32.42%`, zero-recall `34/52` vs `57/73`. Strongest Phase-3 candidate; cadence penalty grows `6.37→10.29` points; not yet Android-promoted |
| Signer/cadence-invariant V2 recognizer runner | `model/perception_vnext/signer_cadence_invariant_236.py`, `model/config/recognition_upgrade/perception_vnext_signer_cadence_invariant_recognizer_236_01.json` | `apphear.perception_vnext.invariant_objective.v1`; unchanged 4×64 causal TCN exposes its L2-normalized 64D masked-pool embedding, retains 236-way CE, and adds batch supervised contrastive positives only for same gloss/different real TRAIN signer plus exact same-clip dense↔sparse cosine consistency | frozen V2 dense+sparse pair for each governed TRAIN clip → deterministic cross-signer pair batches (3,926 anchors/7,852 views/246 steps) → resumable checkpoints and unchanged matched evaluator | Full run/evaluation structurally PASS but scientific result `SIGNER_CADENCE_INVARIANT_NOT_SUPPORTED`: DEV dense/sparse Top-1 `46.32%/39.09%` versus V2 control `50.25%/39.95%`; macro-F1 `43.46%/36.77%` versus `48.55%/38.15%`; zero recall `46/61` versus `34/52`. Alignment improved, but class-centroid margins compressed and recognition worsened. Closed; do not promote or tune this objective automatically |

PHONE_01 completed on Xiaomi M2101K7AG. The governed 320-frame run passed the geometry screen:
visible LH/RH `95.5%/97.0%`, complete two-hand `90.83%`, unilateral anatomical state `99.375%`,
crossing/contact completion `84%`, no-usable-hand false observation `0%`, and person-body
availability `100%`. The original Kotlin tensor construction ran at `2.257` completed FPS and
`438.573 ms` total p50. The parity-gated native component reduced full-frame preprocessing from
`83.960` to `2.693 ms` p50 and final-window crop resampling from `171.705` to `3.324 ms` p50.
Native live throughput reached `5.607` FPS; one-hand total p50 was `142.968 ms`, while the inferred
two-hand serial path remained about `188–192 ms`. DWPose-t (`80.006 ms` p50) plus each hand refiner
(`50.946 ms` p50) is now the exact blocker. Status is
`GEOMETRY_PASS_NATIVE_DATA_PATH_PASS_MODEL_RUNTIME_FAIL`; no production promotion or recognition
connection is authorized.

## Phase-5.1T learned segmentation contract — `apphear.perception_vnext.segmentation_features.v1`

This is an **offline research contract**, not a production S4 or Recognition V2 revision. It is
the input to the first class-agnostic PRE/ACTIVE/POST segmenter and derives only from chronological
`apphear.perception_vnext.raw.v1` observations over the complete source video. Human START/END
timestamps produce labels only and never control extraction. D1, RGB, gloss/class identity,
Recognition V2, recognizer output, future observations, interpolation, and stale carry are absent.

The width is **378 float32 values**. Source-image XY uses current width/height; ROI side uses the
short source dimension. Invalid numeric geometry is zero with explicit validity. Every motion
channel is current-minus-previous and therefore causal. `dt_seconds` is the actual backward source
timestamp delta clipped at one second. Per-dimension mean/std are frozen from the 89 usable
segmentation-TRAIN clips only and remain outside the Keras graph.

| Offset | Width | Meaning |
|---:|---:|---|
| `0..83` | 84 | current refined LH/RH joint source-image XY |
| `84..125` | 42 | refined joint validity including current observed state |
| `126..167` | 42 | current DWPose hand-proposal support |
| `168..175` | 8 | hand presence values + finite flags + observed + proposal-present |
| `176..181` | 6 | current LH/RH ROI center XY and normalized side |
| `182..213` | 32 | body source-image XY, native support, and point validity |
| `214..215` | 2 | body-group availability and actual backward `dt_seconds` |
| `216..341` | 126 | refined-hand backward XY deltas + pairwise delta validity |
| `342..349` | 8 | ROI backward deltas + pairwise proposal validity |
| `350..373` | 24 | body backward XY deltas + pairwise point validity |
| `374..377` | 4 | signed hand-observed and proposal-state transitions |

| Component | Location | Contract | Input → output | Status |
|---|---|---|---|---|
| Phase-5.1T causal segmentation features | `pipeline/perception_vnext/segmentation/learned_features.py` | `apphear.perception_vnext.segmentation_features.v1`, `[T,378]` float32 at actual raw-v1 timestamps; zero+valid missingness; TRAIN-only z-score sidecar | complete-source Candidate01 raw-v1 → current/backward-only per-observation features | Offline causal and missingness tests PASS; Android parity not implemented or authorized |
| Phase-5.1T first causal TCN | `eval/runtime_diagnostics/phase5_1t_first_segmenter.py` | 64-channel projection, four 2-convolution residual causal blocks at dilations 1/2/4/8, 123,779 parameters, three per-observation logits | normalized segmentation-features v1 → PRE/ACTIVE/POST logits → one fixed decoded active event | Frozen unseen-signer DEV viability result `LEARNED_SEGMENTER_PROMOTED_FOR_LIVE_INTEGRATION`; this authorizes only project-lead consideration of a later live-integration gate, not production readiness |
| Phase-6 frozen phone replay | `eval/runtime_diagnostics/{phase6_freeze_learned_phone_events,phase6_evaluate_phone_replay}.py` | Read-only consumer of the frozen `[T,378]` schema, TRAIN normalization, causal TCN, and sequence-global decoder; hashes learned events before opening oracle/recognizer inputs | retained chronological phone raw-v1 → sparse-phone features/predictions/frozen event → fresh frozen Recognition V2 FULL/LEARNED/ORACLE comparison | Reference reproduction PASS, but transfer not supported: all 10 events ended at the final phone observation, mean window reduction was only `7.79%`, and LEARNED Top-1 remained `2/10`; no Android parity or production promotion |
| Phase-7 cadence-aligned segmenter runner | `eval/runtime_diagnostics/phase7_production_cadence_aligned_segmenter.py` | Reuses `apphear.perception_vnext.segmentation_features.v1` unchanged; deterministically selects genuine observations at 133.308/199.962/266.616 ms grids, recomputes all backward features on the selected sequence, normalizes on FIT sparse views only, and selects one unchanged TCN checkpoint on CAL only | frozen 112 complete-source raw-v1 clips → 336 sparse views → grouped 71 FIT/18 CAL + untouched 23-clip/69-view DEV → guarded known-phone diagnostic | Single run complete. Sparse DEV passed all gates, and phone final-observation endings improved `10/10→0/10`, reduction `7.79%→67.83%`, Top-1 `2/10→6/10`; however only `6/9` HIGH/MEDIUM attempts retained >=80% oracle ACTIVE, so final state is `CADENCE_ALIGNMENT_ALONE_INSUFFICIENT`. No Android parity or production promotion |
| Phase-8A causal streaming SignEvent decoder | `pipeline/perception_vnext/segmentation/streaming_decoder.py`, `eval/runtime_diagnostics/phase8a_causal_streaming_decoder.py` | Reuses frozen S2 `apphear.perception_vnext.segmentation_features.v1` probabilities/argmax unchanged; five causal timestamp states (`IDLE`, `ACTIVE_CANDIDATE`, `PRE_GAP`, `POST_CANDIDATE`, `EVENT_EMITTED_WAIT_REARM`), observed-only 250 ms padding, immutable first emission, and 399.924 ms stable-PRE re-arm | chronological timestamp + PRE/ACTIVE/POST probabilities + argmax at observation `t` → zero or more immutable causal SignEvents without future reads or end-of-input flush | Reusable decoder and causality tests implemented. Exact 27-configuration CAL-only search found zero eligible configurations; best frontier emission/exactly-one was `0.9259`, containment `0.5000`, premature cut `0.5000`, and severe cut `0.1667`. Final state `PHASE8A_NO_ELIGIBLE_CAUSAL_STREAMING_DECODER`; no config frozen, DEV/known-phone unopened, no Android parity or integration |
| Phase-8A-M cadence-safe recognition-window materializer | `pipeline/perception_vnext/recognition_window_materializer.py`, `eval/runtime_diagnostics/{phase8a_m_causal_sparse_window_materialization,phase8a_m2_frozen_sparse_dev_validation}.py` | `apphear.recognition_window_materializer.v1`; no feature-vector change. Uses a committed logical ACTIVE start, first terminal POST anchor, commit-time cap, fixed 250 ms requested context, and outward timestamp bracketing to retain genuine sparse observations without interpolation, duplication, stale carry, or future reads | chronological genuine observation timestamps + logical event/terminal/commit indices → inclusive recognition observation slice, actual delivered context/counts, and explicit left/right censoring metadata | CAL and signer-disjoint sparse DEV support the frozen materializer. DEV emitted-event containment was `52/59` (`88.14%`), premature/severe cuts `11.86%/0%`, mean ACTIVE recall `0.9661`, and mean context reduction `55.47%`. The complete CONFIG_01 pipeline is not supported: emission was `59/69`, driven by LOCAL `2/12` versus ASL_CITIZEN `57/57`; CONFIG_01 remains diagnostic/rejected, phone unopened, Android parity not implemented |
| Phase-8A-T terminal-evidence analyzer | `eval/runtime_diagnostics/terminal_evidence.py`, `eval/runtime_diagnostics/phase8a_t_terminal_evidence_attribution.py` | `apphear.diagnostics.terminal_evidence.v1`; analytical-only control-calibrated comparison of causal S2 POST evidence after the human sign end against successful terminal commits and ordinary intra-sign POST fluctuations | persisted chronological timestamps + frozen S2 PRE/ACTIVE/POST probabilities + human interval + unchanged CONFIG_01/censoring result → interval summaries, view/clip attribution, and model-vs-decoder decision | No feature-vector or runtime-contract change. Reused 54 CAL and 69 DEV streams without inference: six of seven genuine DEV no-event views lacked terminal signal, one was ambiguous, and none matched successful terminal evidence. Supports a training-diversity audit before one targeted S2 ACTIVE→POST correction; does not authorize decoder work, training, phone access, or Android integration |
| Phone causal recognition debug integration | `android/app/src/debug/java/com/example/apphear/perceptionvnext/{PhoneCausalCore,PhoneS2Runner,PhoneCausalController,PerceptionVNextLiveRecognitionActivity}.kt`, `deploy/export_phone_causal_s2.py` | Reuses `apphear.perception_vnext.segmentation_features.v1` `[378]` unchanged; frozen S2 source checkpoint and Phase-7 normalization; unchanged CONFIG_01 timestamp state machine; frozen `apphear.recognition_window_materializer.v1`; frozen Recognition V2 `[96,350]` + mask and 236-class recognizer | genuine continuous Candidate01 raw-v1-equivalent observations → Android causal 378 features → bounded-prefix S2 PRE/ACTIVE/POST → immutable logical event → genuine sparse recognition window → word prediction plus JSONL diagnostics | Debug-only and double opt-in; release hard-disabled. Host and on-device feature/S2 parity pass. Fresh phone attempt 1 emitted one well-contained HELLO and recognized HELLO at `0.9999137`, but CONFIG_01 did not re-arm during 261 subsequent observations / 57.9 s because the stream remained POST-dominant while re-arm requires 399.924 ms stable PRE. State `PHONE_EVENT_PRODUCER_LIMIT_SUPPORTED`; no production promotion or rule change authorized. |
| Phone repeated-recognition lifecycle policy | `android/app/src/debug/java/com/example/apphear/perceptionvnext/{PhoneCausalCore,PhoneCausalController,PerceptionVNextLiveRecognitionActivity,Gate4A1bVisualDiagnostics}.kt`, `eval/runtime_diagnostics/phone_repeated_recognition_integration.py` | No feature/model/window contract change. Separates post-event lifecycle policy from event detection and exposes a `PASS_THROUGH` new-sign admission boundary. `PRE_ONLY` remains control; explicit `PRE_OR_POST_EXPERIMENTAL` requires the same 399.924 ms observed persistence, resets on ACTIVE, and resets across observation gaps over 533.232 ms. | immutable emitted event + chronological S2 argmax/timestamp stream → recovery timer decision → `IDLE/READY`; admitted ACTIVE remains pass-through into unchanged CONFIG_01 episode logic | Debug-only experimental integration; release hard-disabled. JVM tests, APK build, retained-phone replay, and physical-device 378/S2 parity pass. Known HELLO identity/window/result are unchanged; full-session synchronized source images and event-centered overlays are now retained. Awaiting the fixed ten-attempt supervisor phone cohort; no admission filter or production promotion. |
| Phone admission evidence diagnostics | `android/app/src/debug/java/com/example/apphear/perceptionvnext/{PhoneCausalCore,PhoneCausalController,PerceptionVNextLiveRecognitionActivity}.kt`, `eval/runtime_diagnostics/phone_new_sign_admission_and_active_acquisition_validation.py` | No feature/model/lifecycle change. Summarizes the existing raw `segmentation_features.v1` delta/validity blocks into hand, ROI, and body motion magnitudes plus transition counts for debug JSONL only; `PASS_THROUGH` admission remains unchanged. The explicit rested-evidence cohort extra changes only the six prompted/recorded target attempts. | already-derived raw `[378]` observation feature → compact per-observation causal evidence fields in the phone diagnostic log | Design-session audit found no safe admission gate: direct-support rules either lose governed CAL onsets or retain most confirmed phone non-sign events, and the prior phone log omitted motion blocks. JVM tests and debug build pass. Diagnostic-only; no DEV access, production promotion, or admission policy freeze. |
| Phone continuous-visual evidence finalizer | `android/app/src/debug/java/com/example/apphear/perceptionvnext/{PerceptionVNextLiveRecognitionActivity,PhoneVisualEvidenceFinalizer}.kt` | Debug-only session shutdown; no feature/model contract change. On explicit finalization, stops camera admission, drains queued asynchronous visual writes, verifies one original JPEG per recorded observation, then writes the final evidence summary. Back at a completed cohort initiates finalization instead of closing early. | genuine processed-observation visual-write futures + original-image directory + expected observation count → verified count or fail-closed incomplete status | Targets `apphear.perception_vnext.raw.v1` diagnostic capture only; does not alter Candidate01, segmentation features, S2 inference, event/re-arm logic, or recognition. A Recents force-kill before explicit finalization remains outside in-process guarantees; governed captures must wait for `VISUAL EVIDENCE SAVED`. |
| Phone S2 exact-parity recorder | `android/app/src/debug/java/com/example/apphear/perceptionvnext/{PhoneS2ExactParityRecorder,PhoneCausalController,PhoneS2Runner,PerceptionVNextLiveRecognitionActivity}.kt`, `eval/runtime_diagnostics/phone_s2_exact_parity_and_r2_decision.py` | Explicitly opted-in, debug-only `apphear.phone_s2_exact_parity_capture.v1`. Copies the existing `PhoneRawObservation`, already-derived 378 row, exact normalized row consumed by S2, and resulting PRE/ACTIVE/POST probabilities; serializes bounded chronological little-endian arrays asynchronously with hashes and attempt linkage. | same genuine `apphear.perception_vnext.raw.v1` observations consumed live → observation-aligned raw/feature/normalized/probability evidence → governed host feature/normalization/Keras comparison | No feature/model/lifecycle contract change and no alternate inference path. Disabled mode performs no diagnostic copy/allocation. Maximum 3,600 observations. Finalization is fail-closed on file size/hash/count/visual coverage; tolerances are 1e-6 for features/normalization and 1e-4 for Keras-vs-TFLite probabilities. |
| S2-R2 governed continuous-domain trainer | `eval/runtime_diagnostics/{s2_r2_continuous_domain_correction,s2_r2_exact_phone_temporal_review}.py`, `model/config/recognition_upgrade/s2_r2_main_candidate_01_enrichment_correction.json` | Reuses `apphear.perception_vnext.segmentation_features.v1` unchanged. Builds one governed causal-TCN candidate from Phase-7 FIT, current-contract re-extracted enrichment, human-reviewed P1 intervals, and exact Android phone tensors; computes normalization from FIT rows only and applies fixed source-family/state balancing. A deterministic preflight rejects any enrichment sparse view without defensible ACTIVE supervision; the original 17-clip freeze is retained and one 239 ms clip is explicitly excluded in a corrected 16-clip freeze. | governed chronological `[T,378]` rows + PRE/ACTIVE/POST/ignore labels + frozen split roles → one FIT-only normalization package, one causal S2-R2 checkpoint candidate, and acquisition/suppression/completion evidence | Learnability and pipeline smoke PASS; exact-phone tensor review complete. Main extraction/training is supervisor-gated and limited to one run. E6, historical DEV selection, future phone validation, protected TEST, runtime lifecycle, materializer, and recognizer remain untouched. No feature-contract semantic or ordering change. |
| S2-R2 post-run source/cadence evaluator | `eval/runtime_diagnostics/s2_r2_postrun_decomposition.py` | Read-only consumer of the frozen S2-R2 Keras checkpoint and paired FIT-only normalization; verifies hashes before comparing against frozen Phase-7 S2 on the already-open internal-development rows under unchanged CONFIG_01. | existing governed `[T,378]` rows + immutable selected checkpoint/normalization → per-source, cadence, signer, phone-attempt, and P1-participant state/event diagnostics | Selected epoch-7 host candidate passes the preregistered gates but is not production-approved. The evaluator found one APPHEAR_CAPTURE VIEW_A severe-cut regression and persistent VIEW_C weakness; it does not read E6, protected TEST, or future phone validation, and makes no feature-contract change. |
| S2-R3 frozen context suite | `eval/runtime_diagnostics/s2_r3_context_suite.py`, `model/config/recognition_upgrade/s2_r3_context_suite_{01,02,03,04}.json`, `evidence/s2_r3_context_suite_20261016/suite_freeze{,_02,_03,_04}.json` | Read-only gate for any S2 package. Tier 1: the 69 held-out segmentation DEV views under fixed history conditions, concatenated at feature level so the target keeps its no-previous-observation first row, plus CONFIG_01 + materializer isolated containment. Tier 2: four labelled phone sessions through the reference PRE_OR_POST replay. A single `features_for_raw(raw, contract)` dispatch keeps the sources identical across contract versions. | governed raw-v1 (DEV subsets, phone captures) + package Keras/normalization → per-condition acquisition/recall/false-ACTIVE, signs-with-event, non-sign activations, POST dwell → preregistered gate | Suite v04 (current) adds Tier 1c: two held-out IPN Hand subjects (hash-pinned manifest), NOG active rate <= 0.10 and NOG events/min <= 1.0, chunk-fire and gesture-canary diagnostics; tiers 1/1b/2 reproduce v03 exactly. Suite v03 adds Tier 1b: held-out N0 (P05/P06) no-hands streams at VIEW_B cadence with a 1000 ms review-exclusion radius, scored as ACTIVE rate and events/min non-inferiority. Suite v02 adds raw-level held-out HOLD_g and non-sign-session histories, history false-ACTIVE scoring, one-to-one distinct-event matching with merged-event counts, and continuous-only Tier-2 totals; v01 stays reproducible. Targets `segmentation_features.v1` (v2 refused until implemented). The freeze reproduced every S2-R2 baseline, with exact raw→378 recomputation and exact event replay. Never opens TEST, E6 or Tier 3. Development-exposed data is gate-only, never selection. |
| S2-R3 signer-grouped data split | `eval/runtime_diagnostics/s2_r3_data_split.py`, `model/config/recognition_upgrade/s2_r3_data_split_rules_01.json`, `model/config/recognition_upgrade/s2_r3_data_split_01.json` | Freezes FIT/CAL/HELD_OUT_EVAL roles before S2-R3 training: per-source signer ranking by SHA-256(seed:signer) puts round(0.2 x signers) in CAL (sources with <3 signers stay FIT); negatives are participant-grouped by rule. Refuses DEV-signer or participant-role overlap. | Phase-7 sparse manifest + S2-R2 dataset manifest + P1 intervals + N0 capture manifest -> frozen role record with source hashes | Rebuilds byte-exactly from sources (test). Never opens DEV labels, TEST, E6 or Tier 3. |
| S2-R3 N0 raw-v1 extractor | `eval/runtime_diagnostics/s2_r3_n0_extraction.py` | Complete-source Candidate01 extraction (every frame) of the N0 negative clips with the pinned Android assets and the S2-R2 video/raw helpers; carries the 1-FPS human hand-presence review as an exclusion sidecar. Reuses existing outputs; writes only a new artifact directory. | N0 videos (hash-checked against the split) -> raw-v1 npz + manifest (asset hashes, split hash, per-clip raw hash) | 57 clips extracted; re-extraction is bit-identical. |
| S2-R3 hands-visible negative extractor | `eval/runtime_diagnostics/s2_r3_negative_extraction.py` | Pinned-Candidate01 raw-v1 for the 45 reviewed P1 intervals (every frame) and the design-signer phone session 20260920T145710Z from its synchronized JPEGs; labels PRE only inside human-confirmed non-sign windows, IGNORE elsewhere. Roles from the frozen split. | P1 MP4s + phone JPEGs/events + refined event labels -> raw npz + label npy + manifest | E6 and gate sources untouched; approximate sign ranges never used as labels. |
| S2-R3 stream builder and trainer | `eval/runtime_diagnostics/s2_r3_train.py`, `model/config/recognition_upgrade/s2_r3_train_{01,02,03}.json` | Seeded raw-level stitching of FIT/CAL sources at Phase-7 cadences (isolated / direct / via-negative grammar, joins IGNORE), features recomputed over the stitched raw; D6 TCN; D7 CAL-only selection with a pre-registered diagnostic fallback; per-epoch checkpoints; optional non-sign row weight. | frozen split + Phase-7 views + N0/P1/phone raw -> `segmentation_features.v1` package (Keras + FIT normalization) | Contract unchanged (Arm A). Research output only; Android selector untouched. |
| WORD robustness trainer (experimental) | `model/perception_vnext/recognition_v2_robust_aug.py` | Recognition-v2 TCN identical to tcn_v2_run_01 except the per-epoch sparse view: seeded pool of cadence 2.5-7.5 fps, random phase, 0-40% simulated refiner rejection. | raw-v1 TRAIN clips -> `recognition.v2` [96,350] views -> 236-class Keras checkpoint | Contract unchanged; output in a new run directory; Android recognizer untouched. |
| Held-out DEV full-video extractor and continuous benchmark | `eval/runtime_diagnostics/heldout_dev_fullvideo_extraction.py`, `eval/runtime_diagnostics/heldout_dev_e2e.py` | Full-length raw for the 816 signer-disjoint recognizer-DEV clips (hash-verified) with governed spans; per-signer stitched NATURAL/CONTINUOUS streams at phone cadence through S2 -> decoder -> materializer -> WORD, with an oracle-window reference. | DEV videos -> raw npz + manifest -> detection, correct-word, extra-event and oracle rates | Spans are automatic, not human; semi-synthetic joins; comparative benchmark only. |
| Event-separation research decoder | `eval/runtime_diagnostics/event_separation.py` | Subclass of the frozen causal decoder adding optional re-entry, short-POST, maximum-ACTIVE, confirm-boundary and PRE_EXIT_POST (a valid ACTIVE run exiting into PRE gets the POST confirmation instead of the PRE-gap discard) rules, and their combinations (R1_CB70, R2_CB70; REENTRY_2 is the CAL-selected re-arm candidate, 2026-10-17); optional nonactive_peak gates splits on 1 - P(ACTIVE) instead of P(POST) (tested, no effect on Arm I); `use_variant` swaps it into the reference replay so every benchmark sees identical S2 output. BASELINE equals production (tested). | S2 probabilities/argmax -> SignEvent list | Offline only; Android lifecycle untouched. |
| Event reliability ledger (research) | `eval/runtime_diagnostics/event_reliability.py`, `docs/audit/probes/event_reliability/` | Replays any S2 package + decoder variant through the reference lifecycle and runtime materializer; classifies each window with the frozen recognizer (displayed) and WORD v2 (shadow); labels each event only from human review (GENUINE, DUPLICATE, CONFIRMED_NONSIGN, PARTIAL_NONSIGN, UNCERTAIN, UNREVIEWED) and records commit-time evidence (S2 probabilities, accepted-hand fractions, motion, WORD confidence/stability/agreement). | raw-v1 phone captures, CAL and held-out DEV streams + S2/WORD packages -> per-event ledger JSON | Offline only; reads the same `segmentation_features.v1` and `recognition.v2` contracts; no Android or contract change. Unreviewed events are never counted as false words. |
| Paired phone replay comparison (research) | `eval/runtime_diagnostics/phone_replay_compare.py` | Replays exact-parity phone captures (or the reviewed registry) through any set of S2 package + decoder configurations, the runtime materializer and frozen WORD (v2 shadow); attributes each reviewed genuine sign to its earliest failing stage (PERCEPTION, S2_NOT_ACQUIRED, LIFECYCLE_SWALLOWED, LIFECYCLE_DISCARDED, MERGED, WINDOW, CLASSIFIER, CORRECT) using the human-boundary window as the classifier reference; counts non-sign / unreviewed / duplicate events and commit latency; carries label provenance. | capture raw-v1 + human_boundaries.json -> paired per-sign stage matrix | Offline only; offline replay does not establish live latency or UI behaviour. No contract change. |
| S2-R3 Arm A e10 debug phone S2 package | `deploy/export_s2_r3_arm_a_phone.py`, `android/app/src/debug/assets/phone_causal_recognition_01/s2_r3_arm_a_e10_candidate/`, `android/app/src/main/java/com/example/apphear/perceptionvnext/PhoneS2Runner.kt` (enum entry only), `android/app/src/debug/java/com/example/apphear/perceptionvnext/PerceptionVNextLiveRecognitionActivity.kt`, `tests/test_s2_r3_arm_a_phone_package.py` | Third selectable research package `ARM_A_E10_CANDIDATE`, chosen only by the debug `phone_s2_package` intent extra under the same opt-ins as S2-R2 (validation cohort or transition diagnostics, exact evidence, PRE_OR_POST re-arm, declared signer). Reuses `apphear.perception_vnext.segmentation_features.v1` `[378]`, PRE/ACTIVE/POST, receptive field 61, 123,779 params; contract is `research_only` and records the source run status `NO_ELIGIBLE_EPOCH` (epoch 10 = diagnostic fallback). | same chronological 378 rows → Arm A FIT normalization (`754e5e0e…68dc`) → bounded-prefix FP32 TFLite (`e7725ef2…f295`, source `17915b02…1c7c`) → unchanged lifecycle/recognition path, package identity in session evidence | Debug assets only; release keeps hard-coded `S2_R2_CANDIDATE` and the Gradle `apphearPhoneS2Package` property still accepts only S2-R2/Phase-7, so production default and rollback are unchanged. Host Keras-vs-TFLite parity on the same 669 prior-phone observations as S2-R2 (fixture `17ed546b…7618`): max probability difference `1.31e-6`, zero argmax mismatches. Device parity on M2101K7AG: 669 observations, max probability difference `4.77e-7`, zero argmax mismatches; full PhoneS2 parity class `OK (4 tests)`. See `docs/audit/S2_R3_ARM_A_E10_PHONE_PACKAGE_2026-10-17.md`. Live capture pending. |
| Live recognition engine selector (debug) | `android/app/src/main/java/com/example/apphear/perceptionvnext/PhoneRecognitionConfiguration.kt`, `.../data/settings/RecognitionEngineSettings.kt`, `.../perceptionvnext/PhoneProductionSession.kt`, `.../perceptionvnext/PhoneCausalCore.kt` (`confirmBoundaryPostPeak`), `.../ui/settings/SettingsContent.kt`, `android/app/src/test/.../ExperimentalRecognitionConfigurationTest.kt` | Debug-only Settings choice (prefs `recognition_engine`/`selected`) between STABLE (S2-R2 package from BuildConfig, production lifecycle) and EXPERIMENTAL (ARM_A_E10_CANDIDATE + confirm-boundary 0.7 on the POST-probability peak). One PhoneProductionSession per screen open, so only the selected engine commits; Candidate01, materializer, frozen WORD and SentenceBuilder shared. Kotlin lifecycle matches the Python decoder on 46 recorded streams (303 BASELINE / 320 CONFIRM_BOUNDARY_70 events). | S2 probabilities -> lifecycle events -> WORD commits | Release and unknown choices resolve to STABLE; EXPERIMENTAL load failure falls back to STABLE. Device-verified 2026-10-17. Contract unchanged. |
| WORD vocabulary evaluation bank (research) | `eval/runtime_diagnostics/word_vocabulary_eval.py`, `word_vocabulary_report.py`, `docs/audit/probes/word_accuracy/` | Builds every recognition window once (DEV span/cadence/runtime-context/Arm A event windows, Sem-Lex packages 01/02 with ENRICH/EVAL signer roles, phone, TRAIN) and stores Recognition V2 features so any [96,350] recognizer is scored on identical inputs; per-class, per-signer, confusion and clip-level paired statistics. | raw-v1 -> `apphear.perception_vnext.recognition.v2` views -> scores | Feature contract unchanged; protected TEST/E6/Tier 3 never read. |
| WORD blend debug engines | `model/perception_vnext/word_blend.py`, `deploy/export_word_v2_candidate.py` (parameterized), `PhoneRecognitionConfiguration.kt` (EXPERIMENTAL_WORD_BLEND, EXPERIMENTAL_WORD_BLEND_02), debug assets `word_blend_candidate_01/02` | Single-graph weighted average (0.5 frozen + 0.5 mean of three Sem-Lex-enriched TCN members); same [96,350]+[96] -> 236 contract, vocabulary and materialized window; the paired recognizer runs on the identical view and is logged only. | Recognition V2 view -> 236 probabilities | Debug builds only; load failure -> STABLE; Stable/Experimental unchanged. Contract unchanged. |
| Sem-Lex governed review pipeline | `eval/runtime_diagnostics/semlex_review_package.py`, `semlex_review_ingest.py`, `docs/audit/probes/word_accuracy/semlex_review_02_decisions.csv` | Prioritized side-by-side form review (P5-D6 decision set), then only human-accepted forms are streamed from the local Sem-Lex TRAIN archive and run through the unchanged Candidate01; trainer option `--extra semlex2_enrich` (ENRICH signers, cap 2 clips/signer/class). | Sem-Lex video -> raw-v1 -> training rows | English gloss equality is never a decision; EVAL-role signers never trained on. |
| S2-R3 Arm P reviewed-phone option (research) | `eval/runtime_diagnostics/s2_r3_train.py` (`phone_reviewed_fit`, `--holdout`), `model/config/recognition_upgrade/s2_r3_train_03.json` | Adds reviewed phone sessions to FIT (PRE on confirmed non-sign, ACTIVE on genuine signs, IGNORE elsewhere) with leave-one-session-out hold-out. CAL streams additionally keep their raw sequence and negative family (no RNG use; streams unchanged). | reviewed phone raw-v1 + labels -> FIT rows -> `segmentation_features.v1` package | Gate sessions are used for training only in folds that do not score them. Not adopted (2026-10-17). Contract unchanged. |
| IPN Hand external-data loader (research) | `eval/runtime_diagnostics/ipn_hand_feasibility.py`, `model/config/recognition_upgrade/ipn_hand_split_01.json` | Pinned Candidate01 (unchanged offline path) on IPN Hand videos at a 7.5 fps selection; IPN HandS labels mapped by time (ffmpeg fps=30 timeline, 1-based inclusive: frame = round(t*30)+1); NOG rows >= 500 ms from gestures are non-sign candidates; gestures are never ASL labels; frozen hash subject split. | IPN videos + HandS temporal annotations -> raw-v1 npz + per-row class | External, CC BY 4.0, untracked under artifacts/external/ipn_hand. Landmarks are not used as observations. No contract change. |
| S2-R3 Arm B/I/J/K augmentation options (research) | `eval/runtime_diagnostics/s2_r3_train.py` (`augment.body_dropout`, `augment.ipn_streams`), `model/config/recognition_upgrade/s2_r3_train_{04,05,06,07}.json` | Body evidence removed on whole stitched segments with probability p; extra stitched streams with IPN NOG negative blocks (FIT subjects) in domain STITCHED_IPN; optional training-only NON_ACTIVE target (label 3, loss -log(p_PRE + p_POST); train_07). Own RNGs: base FIT and CAL streams stay identical to Arm A (verified). | Arm A sources + IPN raw -> FIT rows -> `segmentation_features.v1` package | Not adopted (2026-10-17). Contract unchanged. |
| Candidate01 d1 span port | `pipeline/detect/candidate01_span.py` | d1 signals (wrist/elbow motion in shoulder widths, hand-wrist aux, raised-wrist gate) from Candidate01 raw-v1 with the unchanged hysteresis rule; theta_scale 0.4 fitted on TRAIN, validated on DEV (IoU median 0.62). | raw-v1 -> Span(onset, release, valid) | For new training sources only; governed spans unchanged. |
| Sem-Lex candidate extractor | `eval/runtime_diagnostics/semlex_candidate_extraction.py` | Pinned-Candidate01 raw-v1 for the 2,425 staged, hash-listed Sem-Lex candidates (65 human-accepted classes, 32 signers); undecodable files logged, never fabricated. | staged webms -> raw npz + manifest | Research enrichment source for WORD; Sem-Lex TRAIN split only. |
| WORD shadow recognizer (debug) | `android/app/src/main/java/com/example/apphear/perceptionvnext/RecognitionV2LiveRecognizer.kt` (RecognizerPackageSpec, frozen default), `android/app/src/debug/java/com/example/apphear/perceptionvnext/{WordShadowPackages,PhoneCausalController,PerceptionVNextLiveRecognitionActivity}.kt`, `android/app/src/debug/assets/word_v2_candidate/`, `deploy/export_word_v2_candidate.py` | Hash-pinned second recognition-v2 package invoked on the identical materialized window and V2 view; its prediction is logged as shadow_* event fields only. Enabled per session with the `word_shadow_package` intent extra. | Recognition V2 view [96,350] + mask -> 236 probabilities (logged) | Debug assets only; frozen Gate-2 remains primary, default and rollback; identity JSON of the frozen package unchanged. |
| Versioned phone S2 debug package selector | `deploy/export_s2_r2_phone.py`, `android/app/src/debug/java/com/example/apphear/perceptionvnext/{PhoneS2Runner,PhoneCausalController,PerceptionVNextLiveRecognitionActivity}.kt` | Reuses `apphear.perception_vnext.segmentation_features.v1` `[378]` unchanged. Explicit `PHASE7_CONTROL` or `S2_R2_CANDIDATE` selection binds a SHA-verified FP32 TFLite model to its matching SHA-verified FIT normalization; state order is PRE/ACTIVE/POST and the causal receptive field remains 61 observations. | chronological genuine 378 rows → package-specific normalization → bounded-prefix S2 probabilities/state → unchanged lifecycle and recognition path, with package identity in session evidence | S2-R2 epoch-7 host export passed Keras/TFLite parity on 669 exact prior-phone observations (max probability difference `8.64e-7`, zero argmax mismatches); Phase-7 assets remain the default rollback. Debug APK and Android-test APK build. Connected Android parity and untouched distinct-signer phone validation remain pending; no production promotion or feature-contract change. |

The phone causal debug integration is an authorized parity/capture harness, not production promotion.
The first marked live attempt verifies the full contract through correct word output, but isolated-sign
repetition is blocked by CONFIG_01's PRE-only re-arm against a post-sign stream that remains strongly
POST. This is a lifecycle/interface result, not authorization to retrain S2 or change the decoder.

The repeated-recognition lifecycle component changes only post-event readiness. It does not change
the `[378]` feature order/math, S2 probabilities, event-completion rules, materialized observation
identity, Recognition V2 `[96,350]` construction, or recognizer output. The experimental policy is
selected explicitly at harness launch; an omitted policy remains fail-safe PRE-only control.

## Real-app causal runtime ownership (2026-09-23)

`RecognitionActivity` owns exactly one front-camera `Candidate01FrameAnalyzer` in the normal app.
The validated Candidate01 native preprocessor, DWPose-t ONNX and hand-refiner TFLite runners,
`PhoneSegmentationFeatureBuilder`, `PhoneS2Runner`, causal lifecycle, materializer,
`RecognitionV2`, and frozen 236-class recognizer live in the main `perceptionvnext` source set.
`PhoneProductionSession` composes them and emits only product-level recognition state/sentence
to the existing UI. The diagnostic activity remains in the debug source set and retains its
attempt/evidence capture; the normal analyzer never records source frames or parity tensors.

The normal runtime selects `S2_R2_CANDIDATE` by default. The internal debug Gradle property
`apphearPhoneS2Package=PHASE7_CONTROL` selects the rollback package, never a second live model.
`PhoneS2Runner` verifies the selected package's feature schema, state order, model hash, and
matching normalization hash together before inference. S2-R2 TFLite SHA-256 is
`7d26c896db1a00e7a41ff3e02b02033428cbd2ae4b5cbf3e4d279d45f529d3d7`; its source
checkpoint and FIT normalization identities remain `b6f8b52c…c151` and `65d885f6…c005`.
The Phase-7 model/normalization pair remains available only for internal rollback.

No raw-v1, 378-feature, normalization-algorithm, PRE/ACTIVE/POST, CONFIG01, re-arm,
Admission, materializer, or Recognition V2 semantic contract changed in this promotion.
`phoneRecognitionRawSequence` is the shared lossless raw-v1 → Recognition V2 adapter used by
both debug replay and real-app inference; the older debug-local duplicate was removed.
The real-app Candidate01 native library is currently arm64-v8a only; unsupported devices fail
closed with an explicit error and never silently switch to the legacy 258-feature backend.

## Shared Candidate01 overlay renderer (2026-09-23)

`PerceptionVNextOverlayRenderer` and `P8bOverlayContract.displayTransform` now live in the
main Android source set and are called by both the existing `PerceptionVNextOverlayView` and
the real app's `OverlayView`. The phone frame adapter passes the already-produced hand XY,
joint validity, hand observation/presence, proposal ROI, body XY, and body support to this
presentation-only renderer. The renderer applies the validated fill-center source-to-view
transform with one front-camera mirror, then draws the same hand/body skeletons, ROI outlines,
and presence labels in both views. The real UI clears its overlay on stop/navigation.

This is **not** a feature contract or inference change: no pixels, coordinates, validity,
features, model inputs, probabilities, or event decisions are fed back from drawing. The
instrumented `PhoneOverlayIntegrationInstrumentedTest` compares real-app and validated-debug
rendering pixel-for-pixel and checks full-frame clear behavior; the existing P8c3a overlay
test protects the display transform. Normal runtime still records no review images/tensors.

## Offline Text-to-ASL asset batch utility (2026-09-28)

`tools/text_to_asl_assets/Optimize-Characters.ps1` / `batch.mjs` prepares GLB derivatives from
the assessed G-drive inventory. Inputs are SHA-256-pinned original GLBs and the accepted pilot's
shared KTX2 texture template. Outputs are compact KTX2/Meshopt GLBs, per-file validation reports,
and `apphear.text_to_asl.asset_batch.v1` summary/checksums under a separate output directory.
It performs exact decoded rig/transform/animation/non-index data checks and oriented triangle
topology checks, refuses unknown output overwrites, and resumes verified completions. Older
textures, ambiguous sources and SORRY recovery candidates are excluded. Source hashes are checked
before/after generation. Sequential processing and shared texture reuse bound preparation cost.

This utility does not consume recognition feature vectors or change their `schema_version`,
training/serving math, Android catalog, semantic sign mappings or playback behavior. It requires
the existing machine-local pinned pilot dependencies and assessment artifacts. Production rollout
still requires separate flagged integration, per-sign visual/semantic review and phone measurement.

## Text-to-ASL replacement pilot runtime (2026-09-28)

`AslAnimationAsset.Replacement` optionally carries original fallback path, animation name and
duration for the presentation player. `AndroidAssetAslCatalogLoader` validates schema-1 override
metadata/content hashes on an IO dispatcher and overlays only exact-ID replacements, preserving aliases,
types, planner order and vocabulary. `ASL_ASSET_PILOT_ENABLED` is debug-only and defaults false;
release/default builds exclude `src/aslPilot/assets` entirely. Original catalog/player/assets remain.

Pilot `TextToAslPlaybackController` and `pilot_player.js` use matching URL/request tokens, actual
per-viewer loaded source, local Basis/Meshopt decoders, one-shot signs, looping old idle, zero
global cache and at most active/next models. Load failure retries original assets. Load timeout
is separate from duration-based completion watchdog. Lifecycle stop clears pilot models/timers;
resume replays the current sign. Six deterministic player tests and both ON/OFF Android builds
protect behavior. Phone rendering/residency/performance and F22 smoke remain deferred by the user.
No recognition feature-vector schema, train/serve math, vocabulary or inference contract changed.

The expanded pilot has seven replacements: A, B, ALL, BROTHER, CHILD, CITY, FAMILY. Schema-1
overrides now also require `sourceId` equal to the existing catalog ID in uppercase and WORD/LETTER
type. `tools/text_to_asl_assets/stage_pilot.py` stages only these exact source/catalog matches from
hash-validated batch outputs; it adds no aliases or vocabulary. Semantic near-matches (e.g. COME
versus COME TO HERE), unmatched source words, other letters and pronoun-I mapping remain unchanged.


Text-to-ASL pilot completion refinement (2026-09-28): after setting animationName, await
model-viewer.updateComplete before one-shot play. Pinned4.3.1 lacks reliable DOM finished events
because mixer subscriptions occur before loading; public currentTime>=duration monitor supplies
exactly-once completion for the active URL/request. Event and monitor share one guard; new input,
Clear and lifecycle stop cancel the monitor. Watchdog remains separate. Seven player regressions
and99 JVM tests each ON/OFF pass. Phone functional pilot passes with user-confirmed shorter pauses;
memory/decode, semantic and fullF22 gates remain pending. No recognition schema/parity changes.


Text-to-ASL shared-character derivative (2026-09-28): `shared-character.mjs` verifies identical
decoded meshes/textures/skins/hierarchy and all original animation channel data, bundles seven
named clips on one character, and adds3 constant hair-node tracks per clip to preserve the sole
source-specific rest transform. Schema1 metadata uses balanced-ktx2mixed-meshopt-shared-v1 and
asl_animations/vnext/shared-character.glb only when debug ASL_SHARED_CHARACTER_ENABLED is true
(-PaslSharedCharacter=true requires -PaslAssetPilot=true). Shared/default/separate variants retain
original102 fallback GLBs; release/default exclude experimental assets. Loader hashes once per
unique path on IO; existing player switches named clips with unchanged completion/cancellation.
No recognition schema, vocabulary or train/serve changes. Eight player and99 JVM tests pervariant
pass. Details: docs/text-to-asl-shared-character-results-2026-09-28.md.

Text-to-ASL word expansion (2026-09-28): `tools/text_to_asl_assets/more-words.mjs` is the
repeatable, source-hash-pinned builder for one 27-animation shared-character GLB. It preserves
the seven existing replacement clips and adds 20 approved word clips with exact decoded source
animation channels and source-specific hair rest transforms. The separate schema-2 presentation
manifest contains seven original-ID overrides with original-file fallback plus 20 new entries
with no original-file fallback. `AndroidAssetAslCatalogLoader` validates the approved source ID,
alias, type, animation name, rig/profile, duration and one shared-file SHA-256 on its IO path.
The four meaning-specific aliases are `big horizontally`, `call by phone`,
`call someones name`, and `pay me`; plain `big`, `call`, and `pay` remain unmapped. This
manifest version is a Text-to-ASL asset/catalog contract only: recognition feature-vector
`schema_version`, training/serving math, model I/O and recognition vocabulary are unchanged.
Debug `aslMoreWords=true` requires both existing pilot flags and is false in default/release
builds. The original 102-file catalog and phone-tested seven-clip shared package remain rollback.
Offline compatibility and APK gates pass; physical load, memory, frame and semantic gates await
the user's later phone test. Details: docs/text-to-asl-more-words-results-2026-09-28.md.

## Text-to-ASL character preference (2026-09-28)

`domain/texttoasl/AslCharacterChoice` resolves stable local IDs `original` and `new`;
`data/settings/AslCharacterSettings` stores them in SharedPreferences `text_to_asl` / `character`.
With selection enabled, missing/invalid values select Original. When the selection experiment
is disabled, existing asset-pilot behavior is preserved and the preference is ignored. Without
pilot assets, New can never be selected. Debug `aslCharacterSelection=true` requires all three
existing expanded-pilot properties; release/default selection is OFF and its Settings row hidden.

Shared `SettingsContent` renders the existing configuration statuses and character preference
on Settings and, in the selector pilot, directly on Profile below its account form. Dialogs are
dismissed with their owning view; resume refreshes the saved value. `TextToAslFragment` resolves it
before async catalog loading and on return; a changed choice cancels the old queue/job, clears
playback metadata and releases the prior player document before rebuilding one catalog/player.
Typed input is retained; an old queue does not resume under the new choice. The Original catalog
has 102 unmodified entries; New has 122 entries with the same seven replacements and 20 approved
new aliases. Other signs and idle retain their original character; selection does not promise
all-sign character coverage. Runtime load failure keeps the existing fallback policy.
The existing pilot completion player is used for both choices in this flagged build, retaining
its timeline and cancellation fixes. No recognition schema, feature math or vocabulary changes.

## Established Profile account contract (2026-09-28)

User approved restoration after inspecting the actual reference. The Profile order is Your/Profile,
user card, then Preference/Your Setting. Guest sees the card and preferences; its Sign in/Register
action opens the reference auth panel. Signed-in Edit Profile enables full name/username inline,
switches to Save Profile, offers Cancel and avatar picking, and always keeps email read-only.
No Edit button routes to Settings. Character preference remains local and independent of accounts.

`AccountRepository` serializes IO through Mutex; session refresh/save/logout finish their critical
commit despite view cancellation. UI observes profile-only state; tokens are private and redacted.
Remembered sessions use backend-bound AES/GCM Android Keystore encryption in apphear_account_secure,
excluded from cloud/device backup. Unchecked login stays memory-only. Passwords are never saved.
Auth v1 user_metadata keys username/full_name/avatar_url match the reference; no public users-table
writes or authorization from metadata. Avatar JPEGs are bounded (8 MiB source, 1024 px decode,
2 MiB upload) and written to authenticated user-ID-scoped profile-images paths. Remote image loading
is restricted to the configured backend's public profile-images URL with redirects disabled.
Signup email confirmation is a normal outcome. Logout uses scope=local, clears local identity even
offline and reports incomplete server revocation. Invalid sessions clear; network failures retain
cached identity. UI, images, network and secure storage never enter the recognition critical path.

Independent debug-only `profileAccounts=true`, release/default false. No S4/F schema, parity,
recognition vocabulary/model or player changes. Backend became reachable on the final read-only
probe; live auth, avatar policy/public delivery and signed-in device acceptance remain gates before
promotion. User passed guest/auth visual acceptance and explicitly deferred live account testing.

## Text-to-ASL New idle (2026-09-28)

With default-off debug aslNewIdle=true (requires aslMoreWords and its prerequisites),
New replaces the existing idle POSE with IDLE_NEUTRAL_FEMALEASL in shared-words-idle.glb.
Original still uses asl_idle.glb; counts remain Original102/New122. This supersedes the
prior “idle remains original” note only for this new flagged variant. The schema-2
manifest gains an optional idle object; prior shared manifests remain compatible.

The derivative contains the same 27 signs plus a six-second authored neutral loop.
Every 4,677 animated TRS properties reset to the verified first frame of A, including
hands, fingers, face and hair. Two chest bones per each of three skins expand gently
and synchronously; root/feet stay fixed. Existing channel data, resources, hierarchy
and compressed binary prefix are exact. This is an authored compatible idle, not an
old-rig retarget and not a source sign or recognition label.

AslIdlePilotContract accepts only the approved path/profile/rig/name, six-second duration,
POSE/id/source identity, original fallback and matching SHA-256. Missing/invalid idle
metadata retains Original idle; model/clip load failure uses existing originalFallback.
Pilot player suppresses finished callbacks for all loops. Signs and idle reuse the same
loaded source; a cold shared-model load now occurs at the initial New idle. No new
runtime dependency, recognition schema_version or S4/F math/parity change. Default/release
exclude the derivative. Offline/APK gates and targeted phone playback passed;
controlled frame/memory/thermal/low-RAM and broad F22 checks remain pending.

The first phone attempt exposed mixed-catalog model eviction: after an original-only
sign, a 20-second reload timeout rejected the shared New path. The optional New idle
variant now pins its large source in the inactive model-viewer while original signs
play; successive original-only signs reuse the active viewer. The most recent
original source stays loaded in the second viewer for Replay. Residency remains
bounded to two model-viewers. Pause/destroy and load failure clear the pin.
Original and earlier pilot variants do not request pinning.
Initial loading remains asynchronous, with a visible loading message until playback.

## Text-to-ASL complete alphabet fallback (2026-09-29)

The default-off `aslAlphabetFallback` debug flag requires the New idle and character
selector pilots. The schema-3 alphabet manifest points its 27 existing signs, idle,
and 24 added C–Z letters to a single 52-animation GLB. The builder verifies the
existing 28 animation JSON records and binary prefix unchanged, exact decoded
rendering resources, and each added source animation's channels. The loader checks
the fixed path/profile/rig/name/identity, duration and shared SHA-256 before
exposing C–Z through a separate letter lookup; it never adds letter I as alias `i`.

With the flag on, the selected catalog's known whole-word or phrase sign wins.
New keeps inherited Original-only signs, including HELLO. A token with no sign
is then spelled only if every A–Z letter exists for that character; otherwise
the whole token is reported unsupported. New has A–Z, while Original still has
only A/B and never borrows New letter assets. Standalone `I` remains I/Me; an I
inside an unknown word uses the New letter-I clip. The flag-off planner retains
its prior character-by-character behavior. The 102 original GLBs and recognition
contract are unchanged; no new runtime library or S4/F parity change is involved.

## Conversation-aware phrase assistance sidecar on Text-to-ASL baseline (2026-10-04)

The sidecar is based on `apphear-text-to-asl-working-alphabet-2026-09-29` (`cc1f394`).
`TextToAslFragment` records one completed typed or speech Hearing turn after a successful
phrase plan; deferred New-character submissions retain their source until the avatar is ready.
Replay does not add another turn. `ConversationPhraseAssist` holds a bounded in-memory
conversation and predicts reply phrases asynchronously behind the debug-only
`contextPhraseAssist` flag; release remains disabled. The prediction cache is keyed to the
latest Hearing turn, so late results cannot replace newer candidates.

`PhoneProductionSession` copies the already computed Top-5 labels/scores for a guarded
committed event into `RecognitionEvidence`. `RecognitionActivity` buffers that lightweight
evidence. The cached natural-language predictions stay hidden until the decoder reports
signing activity, when they appear in a separate prediction strip with an accessibility
description. After each committed event, `EvidenceAwareReplies` uses the existing matcher
rules to promote hypotheses with supported signed-concept prefixes and to mark a partial
one-concept anchor cue for presentation. The leading prediction is centered and may briefly
pulse on that partial cue; all cached hypotheses remain available even when none is supported.
This visual cue does not assert that a full phrase was signed. `ConversationPhraseAssist.previewSupportedTurn`
shows a separate interpretation only if the unchanged full matcher supports the accumulated
sequence. This preview does not finalize a conversation turn or change raw state. Hear still
finalizes the shadow evaluation and speaks the raw sentence. The reply window closes when
Sign Detection stops; the bounded conversation clears when the whole app backgrounds, so
Back/Home cannot resurrect old possibilities. A later signing response cannot reuse the
closed prediction window.
Raw `SentenceBuilder` text remains the displayed and spoken result and becomes the Deaf
conversation turn; event-level evidence remains separate for matching and bounded
diagnostics. No camera images, landmarks, feature vectors or recognizer tensors enter the
sidecar. The 378-feature layout, Recognition V2 input, frozen 236-class model, label order,
Top-1 decision, and their schema versions are unchanged.


## Automatic held-letter Fingerspell v1 — 2026-10-08

Authoritative app source is the October5-based `fingerspell-continuous-oct05` worktree,
branch `codex/fingerspell-continuous-oct05`; base b48594c4942d9e9ac0d94ff96396e80b9f049c0a.
Contract: research `context/fingerspelling-continuous-v1.md`; Adapter.v1 `[T,405]` unchanged.

| Component | Source | Input -> output | Contract / preservation |
|---|---|---|---|
| Automatic held-letter policy | new app `fingerspelling/HeldLetterPolicy.kt` | independent chronological raw observations -> bounded window/stable unconfirmed letters | apphear.fingerspelling.held_letter_policy.v1; operational timing asset, no confidence claim; same-letter latch/missingness rearm; no fabricated frames |
| Continuous inference owner | new app `fingerspelling/ContinuousFingerspell.kt`, existing runtime delegate | raw window -> fresh frozen Adapter.v1 -> frozen V2.1 logits -> exact singleton CTC | one worker/no backlog; callback on camera executor; generation/epoch guard; WORD transition waits; no protected WORD/perception/model change |
| Persisted recognition mode | new app `data/settings/RecognitionModeSettings.kt`, shared Settings/Profile row | explicit user setting -> exactly one recognition owner | default WORD; debug opt-in continuous; no Start/Done; spelling draft + Use confirmation; no WORD SentenceBuilder use |
| Practical fingerspelling correction UI | `fingerspelling/FingerspellPracticalControls.kt`, `RecognitionActivity.renderFingerspellPractical` | existing `FingerspellSnapshot` -> DELETE LAST LETTER above CLEAR; camera-executor delete action | debug `fingerspellPractical` requires continuous fingerspelling; hidden in WORD, disabled while reviewing; no Repeat/Done controls in RECOGNIZED; existing Hear owns confirmation; Adapter.v1 `[T,405]` unchanged |

2026-10-23 practical UI decision: keep DELETE LAST LETTER in the lower panel and remove the
Repeat/Done row from RECOGNIZED. Portrait lock remains a separate debug `recognitionPortrait`
flag. Draft retention, fresh word on entry, review hold and explicit confirmation remain in the
existing fingerspelling runtime/coordinator. This is presentation/interaction only: no feature
layout/version, policy thresholds, normalization, model weights or WORD recognition change.

169 unit/54 singleton/14 model parity checks,2 Settings/owner Xiaomi tests and3local Context Assist
checks pass. Supervisor confirms automatic flow and WORD restoration, not A–Z accuracy. Tracking
loss can falsely rearm; incorrect letters can stabilize. Manual worktree/APK remain rollback.
Full gate/evidence: research docs/apphear-fingerspelling-continuous-gate-2026-10-08.md and
artifacts/fingerspelling_continuous_01. No training/data/model/decoder tuning.


## Shared front/rear camera input — 2026-10-08

Active app: October5 `fingerspell-continuous-oct05` checkout, baseline b48594c.
Input remains `UPRIGHT_UNMIRRORED_SOURCE_RGB`; Adapter.v1 [T,405] and WORD contracts unchanged.

| Component | Source | Input -> output | Contract / preservation |
|---|---|---|---|
| Shared camera binding | RecognitionActivity.bindPhoneCamera | either CameraX lens RGBA + rotation/strides -> existing Candidate01 analyzer | same native rotation/pose/ROI math; front baseline untouched; no horizontal pixel flip; generation reset/drain and stale UI guard |
| Lens-aware overlay presentation | ui/OverlayView, PerceptionVNextOverlayRenderer | unchanged source XY -> lens preview coordinates | front mirror display unchanged; rear natural display; no reflection fed to model |
| Bounded camera diagnostics | camera/CameraTimingProbe | capture/analysis clocks -> timing JSON | no pixel/model/feature modifications; sensor FPS differs from actual screen presentation FPS |

Debug opt-in `recognitionRearCamera=true`; default/release front-only. Front AE range remains15/15;
rear requests30/30 only when advertised, otherwise15/15; KEEP_ONLY_LATEST unchanged. Genuine
observation timestamps drive existing Adapter timing/motion; recognition is not forced to30Hz.
Xiaomi front270/rear90 rotations both yield480x640 source from640x480 raw. Eight native asymmetric
rotation/stride cases byte-identical.169host/7device tests pass; WORD nonempty sentence preserved.
Supervisor confirms both work and rear is smoother after measured15.1->29.6FPS; front unchanged.
Report docs/apphear-front-back-camera-input-2026-10-08.md; artifacts/camera_input_01/summary.json.


## Fingerspell presentation clarification — 2026-10-08

CURRENT SIGN = presentation-only latest valid singleton decode (`currentLetter`); RECOGNIZED =
confirmed + stabilized draft spelling. Tentative letter does not change accumulation. No new feature
schema, threshold or decoding policy. Missing/empty/reset clears current display; stale results
cannot overwrite it. This supersedes earlier hiding of CURRENT SIGN. Controls remain hidden.
Source: HeldLetterPolicy / FingerspellSnapshot / ContinuousFingerspell.emit / Activity renderer,
active October5 checkout.170host and5Xiaomi checks pass. WORD/model/camera contracts unchanged.


## Recognition coordination v1 — 2026-10-08

Adapter.v1 `[T,405]` and WORD feature contracts unchanged. Operational contract:
`context/recognition-coordination-v1.md`; authoritative source is the October5 app worktree.

| Component | Source | Input -> output | Contract / preservation |
|---|---|---|---|
| Recognition coordinator | coordination/RecognitionCoordinator.kt + recognition_coordination_policy.json | actual hearing text/turn + existing idle/current hand evidence -> exclusive owner command | apphear.recognition.coordination.v1; bounded English prompts; once per turn; manual veto; no prediction/confidence fusion |
| UI/lifecycle bridge | coordination/RecognitionCoordinationBridge.kt + Activity seams | owner command / actual spelling -> existing select/confirm + stale-turn-checked history | no inference/feature math; explicit Finish; original WORD sentence unchanged; no Start/Done; generation guards |
| Confirmed spelling context seam | additive ConversationPhraseAssist methods | explicit confirmed A–Z/SPACE + bound hearing ID -> actual DEAF conversation turn | no WORD matcher/provider modification; stale question rejects attribution; never generates recognized text |

180 private/180 flag-off host tests; synthetic Xiaomi routing/confirmation plus existing owner,
WORD/Context/camera gates. 659/662 existing app files and all281 assets unchanged. Default/release
flag off; private APK retained. Existing cold-camera synthetic tests need readiness; initial
failure logs retained and equivalent ready-camera replays pass. No recognition accuracy claim.
Report/evidence: docs/apphear-recognition-coordination-2026-10-08.md;
artifacts/recognition_coordination_01/validation.json.



## Automatic orchestration UI / acceptance observability — 2026-10-08

- RecognitionCoordinationBridge: status only, no camera-screen mode chooser. Context routing
  policy unchanged; existing speaker/Hear confirmation completes spelling and restores WORD.
  Bottom SPEAK retains hearing input; manual fallback remains in Settings.
- HeldLetterPolicy.acceptanceState / lastAcceptanceReason: read-only acceptance evidence for
  epoch, missingness, candidate count/span and latch; does not change acceptance/model input.
- ContinuousFingerspell diagnostic adds apphear.fingerspelling.acceptance_diagnostic.v1 metadata;
  bounded event storage remains 64, periodic flushing uses completed decode count instead of
  capped deque size. No RGB/landmarks retained. Parent report v1 and Adapter.v1 [T,405] unchanged.
- Xiaomi synthetic test: 104 draft characters fully displayed; original AM live plateau remains
  unproven until actual acceptance evidence is available. No accuracy/threshold change claimed.

Evidence: artifacts/recognition_coordination_01/automatic_ui_fix_01/validation.json.


### Empty FINGERSPELL card visibility — 2026-10-09

RecognitionActivity.renderFingerspell: active continuous F renders sentenceCard visible even with
an empty stabilized buffer, using existing placeholder and waiting-for-letters accessibility text.
WORD updateSentenceCardVisibility and all WORD render branches unchanged. 181 host +3 final Xiaomi
checks pass; 104-character display remains untruncated. No acceptance/feature contract change.


### Compact mode header — 2026-10-09
Existing coordination status is now a glass pill between Back and Camera, labeled only Fingerspell
or Word. Owner/routing/confirmation/recognition unchanged; no feature contract change. 181host
+3Xiaomi engineering checks pass; docs/apphear-recognition-mode-header-2026-10-09.md.


## Compact WORD transition diagnostics — 2026-10-15

Debug-only protocol asset `phone_causal_recognition_01/stage2_transition_protocol.json`
(`apphear.word_transition_protocol.v1`, profile `V3_STAGE2_COMPACT_01`) is the shared Android/host
capture/review specification. `PhoneStage2TransitionProtocol` loads and validates it; the existing
`PerceptionVNextLiveRecognitionActivity` selects it only with the explicit Stage2 extra plus the
existing causal/transition flags. Parallel hands must remain disabled. No block marker resets
perception, S2, candidate lifecycle, recovery or the genuine observation ring.

The five-block cohort covers hands-down HELLO→HOME, hands-up HELLO→HOME, adjacent HELLO→HELLO,
HELLO then a held final position, and ordinary movement. Capture identity binds protocol SHA,
comparison baseline e196a8d, S2-R2 hashes and declared signer proficiency (UNKNOWN is permitted
and makes no qualified-signer claim). The historical seven-block profile and v1 reviews retain
their behavior and analysis outputs.

Host `transition_protocols.py` and `continuous_transition_diagnostics.py` bind compact review
labels to `apphear.continuous_transition.human_boundaries.v2`, protocol hash and evidence hash.
Physical sign bounds and bounded held/movement negatives require separate human judgments;
negative intervals cannot overlap genuine signs. Event, merge/miss, lexical outcome and normal
sentence delivery are distinct; diagnostic UI does not measure normal-app sentence delivery.
This is metadata/annotation schema only. Raw-v1, segmentation_features.v1[378], normalization,
recognition.v2[96,350]+mask, all model weights and FINGERSPELL Adapter405 remain unchanged.
Neither protocol documents nor human labels are model inputs. No feature schema upgrade or
frozen-model validation exemption is implied. Device capture/accuracy remains pending.
