# PERCEPTION_VNEXT_RECOGNITION_UTILITY_236_01 — implementation plan

Status: **PROJECT-LEAD APPROVED FOR BOUNDED IMPLEMENTATION**  
Date: 2026-09-13

## Product anchor

The target remains the existing AppHear application running one isolated-sign recognition path:
real phone camera → reliable current-frame hand/body perception → one of the governed 236 signs →
recognized gloss → existing conversational UI. This milestone tests recognition utility only. It
does not connect the UI, add automatic sign boundaries, optimize runtime, or begin continuous ASL.

## Held-constant perception

Candidate 01 remains DWPose-t 256×192 whole-body/anatomical localization followed by current-frame
MediaPipe 224×224 refinement of each proposed anatomical hand slot. Its weights, thresholds, ROI
policy, topology, anatomical ownership, orientation, source restoration, and native preprocessing
are frozen. The only permitted correction is explicit body point validity.

## Terminology

- **raw observation**: evidence emitted by Candidate 01 for one actual decoded frame. It may contain
  explicit missing values and is never normalized, padded, interpolated, or carried forward.
- **derived frame feature**: finite, body-relative recognition input derived from exactly one raw
  observation, with explicit validity and group-state channels.
- **dense view**: all chronological decoded observations, reduced only if a sequence exceeds the
  fixed tensor length; it never duplicates an observation.
- **PHONE_01-realistic sparse view**: chronological observations selected using a timestamp grid
  whose density comes from the governed PHONE_01 completed-FPS evidence, not a handwritten frame
  stride; it never duplicates or interpolates an observation.
- **sequence mask**: distinguishes real selected observations from zero padding.

## Contract decisions

1. Raw schema `apphear.perception_vnext.raw.v1` stores 21-point anatomical LH/RH source XY,
   DWPose proposal support, refiner validity, refiner presence, observed state, proposal/ROI state,
   body indices 5–12 source XY/support/per-point validity, body availability, frame index,
   timestamp, source dimensions, and upright/unmirrored semantics. It contains no Z, carry,
   interpolation, legacy-258 fields, or Family-A compatibility fields.
2. Body point validity is finite XY inside the upright source frame with finite DWPose support
   `>= 0.30`. Body availability remains at least six valid points out of eight. This makes the
   existing group rule explicit without changing its threshold.
3. Derived schema `apphear.perception_vnext.recognition.v1` is 208 float32 values per real frame:
   LH `21×(x,y,support,valid)` = 84, RH = 84, body
   `8×(x,y,support,valid)` = 32, group state = 6, temporal state = 2.
4. XY is normalized around a current-frame body anchor and scale when valid evidence supports it.
   A source-frame fallback remains explicitly marked by `body_normalization_valid=0`. Invalid
   derived point values are zero; their validity channels remain authoritative.
5. Fixed tensor length is 96. Short sequences are post-padded with zero and masked. Long sequences
   select unique frames nearest to evenly spaced timestamp targets. No observation is copied to
   fill the tensor.
6. The sole recognizer is the repository's established four-block, 64-channel dilated TCN lineage,
   with mask-aware temporal pooling and a 236-class output.

## Parity gate

A bounded exact-frame fixture runs the Android Candidate 01 models and preprocessing over selected
governed P8-C3B1/PHONE_01 source PNGs. The offline extractor processes the same upright,
unmirrored files. Required exact agreement: source identity/dimensions, LH/RH slot ownership,
proposal/observed states, topology, body/hand validity, and ordering. Numerical gates are:

- body source XY: p95 ≤ 2 px and maximum ≤ 5 px on mutually valid points;
- refined hand source XY: p95 ≤ 3 px and maximum ≤ 8 px on mutually valid observed points;
- DWPose support and refiner presence: p95 absolute error ≤ 0.02 and maximum ≤ 0.05.

Any systematic coordinate transform, slot, state, topology, or validity mismatch is a failure even
if aggregate numerical tolerances pass. Full extraction remains forbidden after a parity failure.

## Governed evaluation population

Only the immutable full-vocabulary `dataset_v1/manifests/train.csv` and `val.csv` are eligible.
The protected test manifests/populations are out of scope and must never be opened by the new
commands. Before extraction the runner verifies the vocabulary identity, class coverage, clip and
signer counts, source counts, distributions, file existence, and zero TRAIN/DEV signer overlap.

## Build and validation steps

1. Add explicit Android and offline body point validity and raw-schema serialization.
2. Implement the Android exact-PNG fixture path and offline Candidate 01 frame/video extractor.
3. Run the bounded offline↔Android parity gate on the attached Xiaomi phone; stop if it fails.
4. Implement the 208-wide derived schema plus dense/sparse timestamp-based temporal construction.
5. Verify governed TRAIN/DEV manifests without reading protected test data.
6. Run a small multi-class extraction/save/reload smoke only.
7. Implement one mask-aware TCN training/evaluation pipeline and run a tiny finite-loss,
   checkpoint/reload/evaluation smoke only.
8. Imprint the contracts, review the completed bounded feature, and prepare exact resumable user
   commands for full extraction, full training, and full DEV evaluation.

## Stop conditions

Stop immediately on material parity failure, manifest/signer leakage, vocabulary mismatch,
non-finite derived tensors, label mismatch, or checkpoint reload mismatch. Do not launch full
TRAIN/DEV extraction, full training, long dense/sparse evaluation, Candidate 02, or protected-test
access.
