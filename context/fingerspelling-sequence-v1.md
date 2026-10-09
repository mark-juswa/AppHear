# Fingerspelling sequence research contract v1

Status: frozen offline research contract, 2026-10-02. No model is trained or pinned to it.
The user's development decision permits released FSboard pixels as-is despite incomplete
historical reflection attribution. This contract supersedes isolated A–Z + OTHER **only for
this continuous sequence experiment**. AZ-1 and all WORD contracts remain unchanged.

## Observation and feature dialect

`FingerspellingFeatureAdapter.v1`: variable `[T,405]`, float32, chronological actual observations.
Implementation: `pipeline/fingerspelling/adapter.py`; parameters and target order:
`pipeline/config/fingerspelling_features_v1.json`. No T=96, resampling, lookahead, session fit,
forward fill, rotation normalization, slot merging, handedness, Z or world coordinates.
Source RGB is upright through the existing frozen decoder rotation; it is never horizontally
flipped. Absolute clip position/duration and publisher annotation bounds are not model inputs.

Exact zero-based ordering (full column names in generated `feature_columns.json`):

| Columns | Component | Ordering |
|---|---|---|
| 0–1 | time | dt_seconds, dt_valid |
| 2–169 | slot 0 joints | joints 0..20, eight columns each, below |
| 170–182 | slot 0 extras | thirteen columns, below |
| 183–350 | slot 1 joints | same joint order |
| 351–363 | slot 1 extras | same extra order |
| 364–403 | body points | indices 5,6,7,8,9,10,11,12; five columns each |
| 404 | body_available | upstream flag; not a gate on individual body points |

Joint columns: `source_x, source_y, local_x, local_y, source_valid, local_valid,
proposal_support, support_valid`.

Extra columns: `presence, presence_valid, observed, proposal_present, roi_x, roi_y,
roi_side, roi_valid, palm_scale, scale_valid, wrist_dx, wrist_dy, motion_valid`.

Body columns: `source_x, source_y, support, xy_valid, support_valid`.

## Numerical and missingness rules

- Source XY divides pixel x by upright width and y by upright height. Source validity is
  upstream joint_valid AND hand_observed; finite geometry is required when valid.
- Current hand scale is the mean of four wrist-to-MCP Euclidean distances, joints 5/9/13/17.
  All five joints must be valid. Scale must be finite and exceed `short_side * 1e-6`, a
  numerical degeneracy guard, not a Candidate01 operating threshold. Hand-local XY is
  `(joint - wrist) / scale`. Do not rotate or normalize away letter orientation.
- Missing scale invalidates local geometry only; source-relative valid joints remain.
- Presence/support validity means **finite numeric value available**, not accepted hand,
  confidence calibration, or physical joint truth. Upstream support has proposal semantics.
  Finite scores remain available even when the refiner does not accept a hand; masks expose
  this distinction. Do not invent per-joint refiner confidence.
- ROI validity requires proposal_present, all three finite values, positive side. Normalize
  center by width/height and side by short_side. Palm scale divides by short_side.
- Wrist displacement is current minus immediately previous selected wrist, divided by
  current short_side. Both wrists must be observed/valid, dimensions equal, dt <= 1 second.
  It is **slot displacement**, not tracked physical-hand velocity. No previous non-missing
  observation is searched for. Resolution changes/large gaps suppress motion only.
- dt uses consecutive selected float64 millisecond timestamps / 1000, cast once to float32.
  First dt=0, dt_valid=0; later deltas stay real, positive and unclipped. No whole-clip fit.
- Body XY uses each upstream body_valid independently, including when body_available=false.
  No full torso requirement or body fallback geometry. Support retains its own finite mask.
- Float32 arithmetic for geometry, explicit fixed sum order for hand scale, sqrt of squared
  float32 differences. Invalid numeric components are zero with their validity flag zero.
  Do not infer validity from a zero value. Non-finite **valid** geometry is an intake error.
- Retain both Candidate01 slots, including overlapping/duplicated proposals. No anatomical
  dominant/non-dominant identity is assumed. Every sequence/reset starts with no predecessor.

## Python ↔ Android contract

Common fields are exactly timestampMs, sourceWidth/Height, handXy, handJointValid,
handProposalSupport, handPresence, handObserved, handProposalPresent, handRoiCenterSide,
bodyXy, bodySupport, bodyValid, bodyAvailable in `PhoneRawObservation` of
`android/app/src/main/java/com/example/apphear/perceptionvnext/PhoneCausalCore.kt`.
sourceIndex is lineage, not an input column; optional profiling fields are excluded.
Python-only handedness stays in raw cache but is never read by the adapter.

`tools/fingerspelling/FoundationParity.kt` is an unused JVM reference **outside Android**.
Its CommonObservation is a serialization of the fields above, not another perception stack.
Parity compares float32 values at atol/rtol 1e-6 and reports bit equality separately.
Android app compilation, wiring, lifecycle ownership, installed-phone adapter parity and
inference latency are future gates. Nothing in Android is changed in this foundation.

## Sequence package

Manifest schema: `apphear.fingerspelling.sequence_manifest.v1`.
Artifact schema: `apphear.fingerspelling.sequence_features.v1`.
Receipt schema: `apphear.fingerspelling.sequence_receipt.v1`.
Canonical files live in `datasets/fingerspelling/foundation_01/`.

Each row stores official v13 group, role, signer, collection/full-video identifiers, raw
transcript, uppercase normalized transcript, exact source-relative path, expected size/MD5,
original publisher timing metadata and deterministic source-based sample ID. Only entire
ASCII letters/spaces with at least one letter are eligible; preserve whitespace exactly.

Targets: indices 0..25 = A..Z, 26 = SPACE. CTC blank index 27 belongs to logits/loss/decoder
only and is forbidden in transcripts. There is no OTHER character or fabricated boundary.
Required unstrided CTC steps = target length + all adjacent equal-character pairs, **including
repeated spaces**. First experiment readiness assumes temporal stride 1. Any later stride
must recalculate feasibility using encoder output lengths before loss.

Per-sequence NPZ stores schema/adapter metadata, features, float64 timestamps, original frame
indices, int32 targets, genuine phone-view selected indices/timestamps/features, and native
upstream joint-valid/observed/proposal/body masks. Embedded feature masks and source masks are
both retained. Receipts preserve source SHA-256, source path, raw SHA/path, raw receipt SHA/path,
manifest SHA, adapter code/config/column hashes, feature SHA/path, frame/target lengths,
repeat/minimum counts and explicit native/phone CTC statuses. Old extraction receipts remain
immutable; their diagnostic restrictions are superseded **for research only** by the new
manifest's user development authorization. This is not formal provenance proof or release.

`reflection_policy = USE_RELEASED_PIXELS_AS_IS`

`reflection_provenance = STRONGLY_SUPPORTED_UNMIRRORED_NOT_FULLY_ATTRIBUTED`

No horizontal flip augmentation, no MediaPipe publisher landmarks, no word ingest or S2/V2
conversion. Frozen Candidate01 model and preprocessing hashes must match extraction receipts.
No transcript, signer or split is included in feature columns.

## Roles and phrase overlap

Preserve official TRAIN/validation/TEST signer roles globally across both source groups.
Map validation to DEV. MacKenzie contributes TRAIN only. TEST RGB/raw/features remain sealed.
Read only already-authorized official TEST metadata to freeze a phrase exclusion list:
uppercase ASCII, spaces unchanged; exclude **all DEV rows** whose normalized phrase occurs
in eligible official TEST metadata. Do not relabel roles or modify TEST. This removes 981
eligible DEV rows over 465 phrases; 1,371 eligible DEV rows and all 15 DEV signers remain.
Hashes and exclusion IDs are frozen in `dev_phrase_policy.json` before any model selection.
No model-performance information affects this policy. TRAIN/DEV copy identities and signer
overlaps are validation errors. Official pseudonymous human identity remains an upstream
dataset assumption; do not create extra people from sessions/files.

## Cadence views and training eligibility

Canonical storage retains actual extracted cadence. Phone sensitivity view: keep the first
observation, then the first real observation at least `1000/6.231166` ms after the last kept
observation. Recompute **all** adapter features from this subset, resetting at sequence start.
Never interpolate/forward-fill. Discrete-frame rounding makes this gate conservative; it is
not a reconstruction of the measured phone's actual gap distribution or image-resolution
domain. Source frames with missing hands still count as masked CTC timesteps.

Every source remains in inventory, including infeasible views. `ctc_views.json` lists eligible
and explicitly infeasible retained IDs per view. Future loss code must choose a feasible view
explicitly; no source may be silently dropped or converted to OTHER. Passing the bound is
necessary, never an accuracy or motion-information guarantee.

## Collection/extraction boundary and readiness

The frozen first tranche is 1,024 TRAIN (512 DAUN + 512 MacKenzie, 117 official signers) and
256 DEV (15 DAUN signers), selected using metadata-only signer round-robin with deterministic
length/J/Z/repetition buckets. Forced inclusion of all 12 previous diagnostic clips prevents
selection based on Candidate01 performance. This challenge-enriched DEV subset is not a
population-accuracy estimate. Learning curves can determine later tranche scale.

CLI `python -m tools.fingerspelling.foundation`: prepare, reuse-fixed, validate, plan-batch,
acquire-batch, extract-batch. Explicit acquisition/extraction commands accept max 16 rows and
TRAIN/DEV only. Reuse original downloaded sources/raw receipts before any new inference.
Future batch extraction calls frozen `iter_video_frames` and Candidate01Offline.process_rgb,
never the word ingest wrapper. Sources/raw caches stay immutable/reusable. Failures leave the
source pending for review; no automatic relabeling, source replacement or silent omission.

Validator checks official metadata identities, schema/order hashes, transcript and repeated
characters, all source/raw/receipt/feature hashes, frozen preprocessing/models, chronological
timestamps, finite input, recomputed features/masks, role/signer isolation, TEST phrase
exclusion and CTC feasibility. Structural success can coexist with pending sources.
`ready_to_train=false` until the governed tranche and eligible character coverage are complete.
No training command or model loader exists in this foundation. A later explicitly authorized
run must use one causal TCN, character CTC, feasible lengths and held-out-signer evaluation.
