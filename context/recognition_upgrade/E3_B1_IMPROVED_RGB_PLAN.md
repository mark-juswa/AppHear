# E3-B1 Improved RGB Pilot Plan

**Purpose:** Give RGB a fairer bounded test after E3-B0 showed that full-frame 112x112 RGB with a
tiny CNN trained from scratch does not generalize.

**Scope:** Experiment-only package and user-run plan. This does not authorize Android integration,
production model replacement, detector training, full E3 training, or hybrid fusion.

**Current status:** PACKAGE PREPARED / USER RUN PENDING.

**Last updated:** 2026-07-28.

## Verified Project References

- Failed comparator: `context/recognition_upgrade/E3_B0_PILOT_02_RESULT.md`.
- New runner: `pipeline/rgb/e3_b1_pretrained_rgb.py`.
- Package: `artifacts/recognition_upgrade/e3_rgb_b1/pilot_01_mobilenetv3_upper_body`.
- Source split: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support/pilot_manifest.csv`.
- Source classes: `BITE1`, `DEAF1`, `DEMAND1`, `DOG1`, `PARTY1`, `ROCKINGCHAIR1`,
  `WHATFOR1`.

## Why E3-B1 Exists

E3-B0 tested the weakest RGB variant:

`full-frame 112x112 RGB -> tiny CNN from scratch -> small temporal head`

That setup failed below random baseline on held-out signers. The failure should not be interpreted
as "RGB is useless." It should be interpreted as "full-frame low-resolution RGB with a tiny
from-scratch encoder is not a useful branch."

E3-B1 tests the direct improvement:

`upper-body center crop 160x160 RGB -> frozen MobileNetV3Small frame encoder -> temporal head`

## Prepared Package

- Run directory: `artifacts/recognition_upgrade/e3_rgb_b1/pilot_01_mobilenetv3_upper_body`.
- Script: `pipeline/rgb/e3_b1_pretrained_rgb.py`.
- Clips: 168.
- Split: 112 train, 28 validation, 28 test.
- Per-class support: 16 train, 4 validation, 4 test.
- Signer leakage: none, inherited from E3-B0 `pilot_02_strict_support`.
- Crop mode: `upper_body_center`.
- Frames per clip: 16.
- Image size: 160x160.
- Encoder: `MobileNetV3Small`.
- Preferred weights: `imagenet`.
- Training: frozen frame embeddings plus small temporal Conv1D head.
- Estimated uint8 frame tensor size: 196.88 MiB before compression.

## Expected Improvement Mechanism

- 160x160 preserves more hand/upper-body detail than 112x112.
- Upper-body cropping reduces background dominance without depending on MediaPipe hand detection.
- ImageNet MobileNetV3 provides pretrained low/mid-level visual features instead of learning all
  visual filters from the small ASL pilot.
- Freezing the encoder reduces overfitting and keeps the user-run feasible on CPU.
- Precomputing frame embeddings avoids repeatedly running MobileNetV3 during temporal-head epochs.

## Evaluation Gate

Random baseline for 7 balanced classes is 0.1429. E3-B0 strict-support comparator was:

- validation accuracy: 0.0714;
- test accuracy: 0.1071.

E3-B1 should be treated as promising only if:

- validation accuracy is clearly above 0.1429;
- test accuracy improves meaningfully over 0.1071;
- predictions are not concentrated in one or two labels;
- incorrect predictions are not more confident than correct predictions;
- training accuracy improves without validation collapse.

If E3-B1 fails these gates, do not scale RGB. Move to landmark temporal/feature improvements or a
more explicit hand-crop/pretrained experiment after the crop reliability risk is addressed.

## Assumptions

- The user environment can load MobileNetV3Small. If `weights=imagenet` is not cached, the first run
  may need internet access to download Keras weights.
- If ImageNet weights cannot be loaded, `weights=none` is only a plumbing fallback and should not be
  used for architecture judgment.
- ASL Citizen official splits remain the signer-disjoint authority for this bounded test.

## Open Questions

- Are ImageNet weights already cached or downloadable on the user's machine?
- Is upper-body center crop enough, or do we need a hand-aware crop once ROI reliability improves?
- Would 192x192 materially improve hand detail without making CPU extraction too slow?
- Would a two-stream frame encoder, full-frame context plus hand crop, outperform upper-body-only?

## Risks

- ImageNet features may not represent fine hand-shape differences well enough.
- Center upper-body crop may still waste pixels when the signer is far from the camera.
- The validation/test support is better than E3-B0 `pilot_01`, but still small.
- CPU runtime may be slower during first feature extraction.

## Next Required Action

User runs the package command in `README_RUN.md`, then runs `check`, and sends back the completed
run directory. Stop immediately if MobileNetV3 ImageNet weights fail to load.

