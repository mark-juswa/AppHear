# E3-B2 Same-Signer RGB Sanity Plan

**Purpose:** Test whether the improved RGB branch can classify easier same-signer held-out clips
after E3-B1 failed signer-disjoint generalization.

**Scope:** Debugging sanity only. This intentionally allows signer overlap between train,
validation, and test. It is not production evidence and must not be reported as cross-signer
accuracy.

**Current status:** PACKAGE PREPARED / USER RUN PENDING.

**Last updated:** 2026-07-28.

## Verified Project References

- E3-B1 result: `context/recognition_upgrade/E3_B1_RESULT.md`.
- Builder: `pipeline/rgb/e3_b2_same_signer_sanity.py`.
- Runner reused for training/check: `pipeline/rgb/e3_b1_pretrained_rgb.py`.
- Package: `artifacts/recognition_upgrade/e3_rgb_b2/pilot_01_same_signer_mobilenetv3`.
- Same-signer source: `artifacts/recognition_upgrade/e3_rgb_b2/pilot_01_same_signer_mobilenetv3/same_signer_source`.
- Source pool: `artifacts/recognition_upgrade/e3_rgb_b0/preflight_02/pilot_manifest.csv`.
- Summary: `artifacts/recognition_upgrade/e3_rgb_b2/pilot_01_same_signer_mobilenetv3/same_signer_summary.json`.

## Why This Comes Next

E3-B1 showed that MobileNetV3 upper-body RGB can fit the training examples but fails to generalize
to held-out signers. Before building fusion, we need to know whether the RGB branch can solve a much
easier version of the task when signer variation is intentionally removed.

This is a diagnostic split, not a deployment split.

## Prepared Package

- Classes: 7 (`DOG1`, `BITE1`, `DEMAND1`, `WHATFOR1`, `DEAF1`, `PARTY1`,
  `ROCKINGCHAIR1`).
- Clips: 84.
- Split: 56 train, 14 validation, 14 test.
- Per-class support: 8 train, 2 validation, 2 test.
- Held-out signer overlap: every validation/test signer is also present in train for the same class.
- Frames per clip: 16.
- Image size: 160x160.
- Crop mode: `upper_body_center`.
- Encoder: frozen `MobileNetV3Small`.
- Preferred weights: `imagenet`.
- Epochs per command: 8.

## Evaluation Gate

Random baseline for 7 balanced classes is 0.1429.

E3-B2 is useful only if same-signer validation/test accuracy is clearly above random. Suggested
interpretation:

- **Strong pass:** validation and test both >=0.70.
- **Weak pass:** validation and test both >=0.50, with distributed predictions.
- **No-go:** either validation or test remains near random, or predictions collapse to a few labels.

If E3-B2 fails, the RGB branch is not even solving the easy same-signer sanity case and should not
be fused or scaled yet. If E3-B2 passes but E3-B1 fails, the main problem is signer-independent
generalization, not basic visual-branch capacity.

## User Commands

Run:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b1_pretrained_rgb run `
  --run-dir "F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e3_rgb_b2\pilot_01_same_signer_mobilenetv3"
```

Check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b1_pretrained_rgb check `
  --run-dir "F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e3_rgb_b2\pilot_01_same_signer_mobilenetv3"
```

Resume if interrupted:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b1_pretrained_rgb run `
  --run-dir "F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e3_rgb_b2\pilot_01_same_signer_mobilenetv3" `
  --resume
```

## Assumptions

- The same Keras MobileNetV3 ImageNet weights used in E3-B1 remain available.
- The selected repeated signer clips are sufficient for an easy sanity test.
- Because the split is intentionally signer-leaky, high accuracy here does not imply user-ready
  recognition.

## Risks

- The split is small, so results are directional only.
- Same-signer success can still be driven by signer/camera cues rather than sign features.
- Same-signer failure would be a strong warning that the RGB branch or selected classes need
  redesign before fusion.

## Next Required Action

User runs E3-B2, checks it, and sends back the completed run output. Stop after E3-B2; do not start
fusion or full training until the result is evaluated.

