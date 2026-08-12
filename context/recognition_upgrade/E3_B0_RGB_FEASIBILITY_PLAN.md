# E3-B0 RGB Feasibility Plan

## Purpose

Define the first executable step after the C0 route decision: verify that AppHear can build a small
signer-disjoint upper-body/full-frame RGB pilot from existing raw videos before any full extraction
or training.

## Scope

This is preflight-only. It does not authorize RGB tensor extraction, model training, detector
training, Android integration, feature-schema changes, or production recognizer replacement.

## Current Status

PREFLIGHT AND TENSOR SMOKE PASSED / PILOT 02 COMPLETE / FULL-FRAME RGB TINY-CNN NO-GO.

Last updated: 2026-07-28.

## Verified Project References

- Route decision: `C0_ROUTE_DECISION_REPORT.md`.
- Script: `pipeline/rgb/e3_b0_preflight.py`.
- Default ASL Citizen root: `F:/ASL DATASET/ASL CITIZEN/ASL_Citizen`.
- Default local root: `F:/ASL DATASET/local`.
- Default output root: `artifacts/recognition_upgrade/e3_rgb_b0`.
- Passed run: `artifacts/recognition_upgrade/e3_rgb_b0/preflight_02`.

## Preflight Contract

The preflight may:

- read ASL Citizen split CSV files;
- read local Stage-E JSON sidecars;
- count classes, clips, signers, and split support;
- probe a small sample of videos with OpenCV;
- write reports under `artifacts/recognition_upgrade/e3_rgb_b0/<run_id>/`.

The preflight must not:

- extract frame tensors;
- train any model;
- write Android assets;
- modify production recognizer files;
- reuse frozen P0/N0/P1 detector-gate data for training.

## Proposed Pilot Policy

Start with ASL Citizen official signer-disjoint splits because the first question is whether RGB
video has enough isolated-sign signal without relying on hand boxes. Local clips are counted as
overlap/diagnostic data, not automatically merged into training, because local signer and capture
conditions can skew a small pilot.

Strict selection attempted:

- each selected class must have at least 20 train clips, 4 validation clips, and 4 test clips;
- only 7 classes passed, so this is too strict for the first RGB feasibility pilot.

Selected feasibility policy:

- 50 classes;
- each selected class must have at least 10 train clips, 2 validation clips, and 2 test clips;
- probe 12 videos for readability;
- record the complete candidate manifest but do not extract frames.

## Verified Preflight Results

### `preflight_01`

- Command: default strict policy.
- Result: no-go for full feasibility because only 7 classes satisfied 20/4/4 split support.
- Output: `artifacts/recognition_upgrade/e3_rgb_b0/preflight_01`.

### `preflight_02`

- Command: relaxed feasibility policy, `--min-train 10 --min-val 2 --min-test 2`.
- Result: pass.
- Output: `artifacts/recognition_upgrade/e3_rgb_b0/preflight_02`.
- Selected classes: 50.
- Pilot manifest records: 1,870 ASL Citizen clips.
- ASL Citizen inventory: 83,399 records, 2,731 glosses, 52 signers, 0 missing videos.
- Local inventory: 4,035 metadata records, 87 glosses, 4 signers, 1,266 missing paired videos.
- Selected-class local overlap: `EAT1` and `THEY1` only, 20 local clips each.
- Signer leakage across selected ASL Citizen train/val/test splits: none.
- Video readability smoke: 12/12 videos opened and returned a first frame.


## Verified Tensor Smoke Result

### `tensor_smoke_01`

- Script: `pipeline/rgb/e3_b0_tensor_smoke.py`.
- Output: `artifacts/recognition_upgrade/e3_rgb_b0/tensor_smoke_01`.
- Source preflight: `artifacts/recognition_upgrade/e3_rgb_b0/preflight_02`.
- Classes: `DOG1`, `HURDLE/TRIP1`, `BITE1`.
- Rows: 12 clips, using 2 train, 1 validation, and 1 test clip per class.
- Tensor shape: `[12, 8, 112, 112, 3]`.
- Tensor range: `[0.0, 1.0]`, dtype `float32`.
- Tiny model forward output shape: `[4, 3]`.
- One tiny epoch completed and saved `models/tiny_rgb_smoke.keras`.
- Check command passed with no errors.
- This is a plumbing result only, not an accuracy result.

## Prepared Bounded Pilot Package

### `pilot_01`

- Script: `pipeline/rgb/e3_b0_pilot.py`.
- Output: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_01`.
- Source preflight: `artifacts/recognition_upgrade/e3_rgb_b0/preflight_02`.
- Classes: 10 (`DOG1`, `HURDLE/TRIP1`, `BITE1`, `DEMAND1`, `BREAKFAST1`, `DARK1`, `WHATFOR1`, `DEAF1`, `PARTY1`, `ROCKINGCHAIR1`).
- Clips: 120 total, 80 train, 20 validation, 20 test.
- Frames per clip: 16.
- Image size: 112x112 RGB.
- Estimated float32 tensor size: 275.62 MiB before compression.
- Epochs per command: 3.
- Resume support: rerun with `--resume` after `models/latest.keras` exists.
- Overwrite protection: `prepare` refuses an existing run unless `--overwrite` is provided; `run` refuses an existing latest model unless `--resume` is provided.
- Runbook: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_01/README_RUN.md`.

This package completed as a pipeline pass but did not validate accuracy; see `E3_B0_PILOT_01_RESULT.md`.

### `pilot_02_strict_support`

- Script: `pipeline/rgb/e3_b0_pilot.py`.
- Output: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support`.
- Source preflight: `artifacts/recognition_upgrade/e3_rgb_b0/preflight_01`.
- Classes: 7 (`DOG1`, `BITE1`, `DEMAND1`, `WHATFOR1`, `DEAF1`, `PARTY1`, `ROCKINGCHAIR1`).
- Clips: 168 total, 112 train, 28 validation, 28 test.
- Per-class support: 16 train, 4 validation, 4 test.
- Signer leakage check: none across train/validation/test.
- Frames per clip: 16.
- Image size: 112x112 RGB.
- Estimated float32 tensor size: 385.88 MiB before compression.
- Epochs per command: 3.
- Purpose: reduce `pilot_01` validation/test noise by using fewer classes with more held-out clips per class.
- Runbook: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support/README_RUN.md`.

This package is ready for user review. The run has not been started.
## Outputs

Each run writes:

- `preflight_report.json`;
- `preflight_report.md`;
- `selected_classes.csv`;
- `pilot_manifest.csv`;
- `local_overlap.csv`;
- `check_report.json` after the check command.

## User Commands

Prepare:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b0_preflight prepare `
  --run-id preflight_02 `
  --class-count 50 `
  --min-train 10 `
  --min-val 2 `
  --min-test 2 `
  --probe-videos 12
```

Check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b0_preflight check `
  --run-dir artifacts\recognition_upgrade\e3_rgb_b0\preflight_02
```

## Go Criteria

The preflight is good enough to prepare a later tensor smoke only if:

- at least 25 classes pass the class-count policy;
- no signer leakage exists across selected ASL Citizen splits;
- all sampled videos open and return a first frame;
- all outputs stay under the E3-B0 artifact directory.

`preflight_02` satisfies these criteria.

## Assumptions

- ASL Citizen split CSVs provide the authoritative signer-disjoint split for this first RGB pilot.
- Local data is not merged into training until its missing paired-video count and signer/capture
  imbalance are reviewed.
- A 50-class relaxed pilot is sufficient for a feasibility smoke but not a production claim.

## Open Questions

- Should tensor smoke use 16 or 32 frames per clip first?
- Should the first RGB transform be full-frame resize or center-crop/letterbox upper-body framing?
- Can CPU extraction on the user's machine finish quickly enough, or should the tensor smoke be sent
  to the RTX 3050 laptop?
- Should local `EAT1` and `THEY1` be reserved as diagnostics rather than training data?

## Risks

- RGB can overfit signer, background, clothing, or camera style despite signer-disjoint splits.
- The relaxed class policy gives some classes only two validation examples, so full pilot metrics
  will be noisy.
- Full-frame RGB may prove useful offline but too costly for Android without later compression.

## Next Required Action

Do not scale standalone full-frame 112x112 RGB with the tiny temporal CNN. Next, choose between a bounded pretrained/crop-aware visual experiment and landmark temporal/feature improvements. Do not start detector training, full E3 training, or Android integration until the next branch is explicitly approved.




