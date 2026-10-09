# Fingerspelling canonical-hand research contract v2

Frozen for Baseline 3 on 2026-10-04. This is a separate opt-in offline experiment;
the original 405-column adapter, B1/B2 artifacts, WORD contracts and Android remain unchanged.
Governing implementation: `pipeline/fingerspelling/canonical_hand.py`, `adapter_v2.py`,
`package_v2.py`; configuration: `pipeline/config/fingerspelling_features_v2.json`.

## Common observations and causal canonicalization

Inputs are only the common fields listed in `fingerspelling-sequence-v1.md` and
`PhoneRawObservation` in
`android/app/src/main/java/com/example/apphear/perceptionvnext/PhoneCausalCore.kt`:
timestamps, upright source dimensions, both hand XY/joint-valid/proposal-support/presence/
observed/proposal-present/ROI fields and the existing eight body references with masks.
No handedness, Z/world coordinates, transcript, signer, model prediction or future frame.

`SigningHandCanonicalizer.v1` maintains the last observed primary wrist and timestamp.
A candidate requires observed=true, a valid wrist and at least five valid joints.
Quality is 0.5 * valid-joint fraction + 0.3 * finite clamped presence + 0.2 * mean
finite clamped proposal support. This is an association heuristic, not calibrated confidence.
Support summation uses a fixed float32 order shared with the JVM reference.

Two candidates are a **duplicate proxy** when proposals have valid square ROIs with
IoU >= 0.6 and wrist distance <= 0.08 * source short side. This does not prove physical identity.
Otherwise they are **potentially distinct**; secondary context is retained, not full joint geometry.

Prefer the closest spatial association to the last primary within one second, equal source
dimensions and 0.25 * short-side distance. Without an association, prefer higher quality,
then wrist x/y. Exact association/quality/wrist ties use a lexicographic common-evidence key:
for joints 0..20, validity, masked x/y, finite-support flag/value; then proposal-present;
then finite flag/value for presence and each ROI component. A final slot-index tie is allowed
only when these evidence keys are equal, so it cannot alter emitted features. Non-finite
missing values are represented as zero in the key. No transcript-informed choice is possible.

Potentially distinct candidates are ambiguous when no association exists or both accepted
association distances differ by less than 0.03 * short side. These flags expose uncertainty;
the tracker does not prove the selected hand is physically dominant or actively spelling.
Crossing hands or questionable duplicate proposals remain limitations, not relabeling triggers.

No candidate means primary_valid=false, primary geometry/support/presence/ROI zero with
invalid masks. Association memory may span missing observations within the same one-second
limit; **geometry is never copied forward**. Displacement requires an immediately preceding
selected observation with an associated primary and no current ambiguity. Resolution changes,
long gaps, reacquisition and missing neighbors suppress displacement, not timestamps.
Each sequence and temporal view starts with empty canonicalizer state.

## Frozen `[T,255]` layout

Float32 features, variable T, real chronological observations. Exact column-name identity is
generated in `datasets/fingerspelling/canonical_v2_01/feature_columns.json`.

| Zero-based columns | Width | Ordered content |
|---|---:|---|
| 0–1 | 2 | dt_seconds, dt_valid |
| 2–169 | 168 | primary joints 0..20, eight columns each |
| 170–182 | 13 | primary extras, below |
| 183–222 | 40 | body indices 5..12, five columns each |
| 223 | 1 | body_available |
| 224–231 | 8 | canonical state, below |
| 232–239 | 8 | secondary context, below |
| 240–254 | 15 | fingertips 4/8/12/16/20: dx, dy, motion_valid each |

Primary joint order: source_x, source_y, local_x, local_y, source_valid, local_valid,
proposal_support, support_valid. Source XY divides by upright width/height. Local XY is
(joint-wrist)/current-hand scale, where scale is the mean wrist-to-MCP distance at
5/9/13/17; require all these joints valid and scale > 1e-6 * short side. Missing scale
invalidates only local geometry. No hand rotation or reflection normalization.

Primary extras: presence, presence_valid, observed, proposal_present, roi_x, roi_y,
roi_side, roi_valid, palm_scale, scale_valid, wrist_dx, wrist_dy, motion_valid.
ROI center divides by width/height, ROI side and scale by short side. Scores preserve
finite availability masks, not invented refiner joint confidence. Body order per point:
source_x, source_y, support, xy_valid, support_valid. Each body mask applies independently;
body_available=false does not require dropping valid individual points.

Canonical order: valid, quality, continuous, ambiguous, duplicate, potentially_distinct,
reset, candidate_fraction. Candidate fraction is count/2, not a Boolean mask.
Secondary order: observed, presence, presence_valid, roi_x, roi_y, roi_side, roi_valid,
context_valid. Entire secondary block is absent for duplicate proxies or missing candidates.
Slot indices appear only in audit arrays, never as model input columns.

Wrist/fingertip dx/dy are selected-neighbor source-pixel displacements divided by the current
short side, **not velocities**. Fingertip masks additionally require both selected joints valid.
dt is actual float64 timestamp difference /1000 cast to float32; first dt and validity zero.
Invalid geometry is zero + explicit mask. No fill, interpolated landmark or duplicated timestep.
Frozen v1 geometry is reused rather than reimplemented; its implementation/config/order hashes
are nested dependencies of v2 identity.

## Temporal views, targets and artifacts

Reuse `apphear.fingerspelling.temporal_views.v1` and the unchanged B2 policy exactly.
Select real native/12-Hz/6.231166-Hz views **before** canonicalization and adapter computation.
Never thin already-derived motion features. Actual effective cadence can be lower due to
source-frame quantization. These views approximate observation density, not CameraX replay.

Targets remain A..Z=0..25, SPACE=26; CTC blank=27, not a transcript character. Retain all
frozen 1024 TRAIN/256 DEV identities, signer isolation and DEV/TEST phrase exclusions;
TEST payloads remain sealed. Reflection policy is USE_RELEASED_PIXELS_AS_IS with no flips;
historical unmirrored attribution remains strongly supported, not formally proven.

Separate NPZ schema `apphear.fingerspelling.canonical_features.v2` stores targets and
features/timestamps/frame indices/canonical audit arrays for each view. Receipt schema
`apphear.fingerspelling.canonical_receipt.v2` binds frozen manifest, official identities,
source SHA, raw SHA and receipt, parent v1 receipt, adapter/config/column/canonicalizer/v1
dependency hashes, temporal implementation/policy, package implementation and NPZ SHA.
Prepared receipts are validated before reuse; interrupted staging is retained under recovery.
Full recomputation checks raw -> indices -> canonical states -> features bit-for-bit.

CTC bound remains target length + adjacent-repeat count. Every source remains in inventory.
TRAIN requests rotate once through all regimes each three epochs with nearest-denser feasible
fallback; native impossibility is an explicit error. Infeasible DEV sparse views still decode
and contribute to CER; only their impossible CTC losses are omitted and counted explicitly.

## Reference parity and rollout boundary

`tools/fingerspelling/CanonicalParity.kt` is an isolated unused JVM reference, outside Android.
Python/JVM bit parity covers fixture and real TRAIN/DEV views, including slot switching,
duplicate/distinct candidates, exact ties, missing/partial validity, long gaps and resolution
changes. This is **not installed-phone parity or production integration**. A future phone
adapter still needs bridge/reset/state tests and device measurements before rollout.

Baseline 3 uses the original B2 encoder layer configuration (64 channels, no strides),
28 logits per real input timestep and the same loss/Adam/padding/selection/early-stop/calibration
policy. Input kernels rebuild for 255 columns; fresh initialization and reduced input parameter
count are unavoidable, so no bit-identical B2 training trajectory or pure causal attribution
is claimed. Long training is user-run through `model.fingerspelling_baseline3` only.
