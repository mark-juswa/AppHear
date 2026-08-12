# E2e-C0 N0/P1 Capture Runbook

## Purpose

Tell the developer exactly how to record, arrange, sample, review, and validate the two local
fixture sets required before the independent hand-detector transfer screen.

## Scope

This runbook prepares detector evaluation data only. It does not download a detector, train a
model, modify Android, or change the production recognizer.

## Current Status

COMPLETE / FINAL N0-P1 FIXTURES FROZEN.

Last updated: 2026-07-27.

## What You Are Recording

### N0: No Visible Hands

N0 measures false hand detections. A valid N0 frame contains no visible hand pixels, including
fingertips at an edge.

Record at least:

- 20 clips;
- 30 seconds per clip;
- 10 total minutes;
- 6 people;
- 2 camera devices;
- 5 environments/backgrounds.

Include:

- a person facing the camera with both hands below/outside the image;
- face, hair, sleeves, and torso close to the camera;
- moving shoulders/arms while hands remain outside the image;
- empty rooms and clutter;
- moving objects that might look hand-like.

Do not intentionally show a hand. If one appears accidentally, the review step will exclude that
frame.

### P1: Visible Hands, Not Signing

P1 checks whether a hand detector works on ordinary hands rather than only formal gestures.

Record at least 5 total minutes. Show ordinary actions:

- hands resting;
- holding a phone, cup, pen, bag, or book;
- pointing casually;
- adjusting clothing or hair;
- picking up and putting down objects;
- hands crossing or partially hiding each other.

Do not perform the AppHear sign vocabulary during these clips.

## Privacy And Consent

- Every recorded person must agree that the video can be used for this AppHear research.
- Do not record unrelated people in the background.
- Avoid private documents, screens, addresses, IDs, or conversations.
- Keep the raw videos local. Do not send or upload them unless the participant approved that use.

## Folder Layout

Create this structure:

```text
scratchpad/e2e_c0_capture/
  raw/
    n0/
      P01/
        phoneA/
          home_day/
            front/
              n0_p01_home_front_01.mp4
    p1/
      P01/
        phoneA/
          home_day/
            front/
              p1_p01_home_front_01.mp4
```

The five levels under `n0` or `p1` are mandatory:

```text
<participant>/<device>/<environment>/<front-or-back>/<video>
```

Use anonymous participant IDs such as `P01`, not personal names. Use stable device and environment
IDs. Every video filename/stem must be unique across that capture kind.

## Step 1: Place The Videos

From the project root:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
mkdir scratchpad\e2e_c0_capture\raw\n0 -Force
mkdir scratchpad\e2e_c0_capture\raw\p1 -Force
```

Place the videos into the required metadata folders.

## Step 2: Prepare N0

This extracts 600 frames at 1 FPS, balanced across clips. It also writes five-frame chronological
context panels and hashes every source video.

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.e2e_c0_capture prepare `
  --raw-root "scratchpad\e2e_c0_capture\raw" `
  --kind n0 `
  --output "artifacts\recognition_upgrade\e2e_c0\n0_capture_01"
```

The command refuses to overwrite an existing output directory.

## Step 3: Review N0

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.e2e_c0_capture review `
  --run-dir "artifacts\recognition_upgrade\e2e_c0\n0_capture_01"
```

For every center frame:

1. If absolutely no hand pixel is visible, click `NO HANDS`, then `SAVE AND NEXT`.
2. If any hand or fingertip is visible, select `ONE HAND` or `TWO HANDS`, draw tight boxes, then
   save. The validator will mark the frame as N0 contamination and exclude it.
3. If the frame cannot be judged, use `Cannot judge - skip`.

Progress saves automatically. Closing and reopening resumes at the first incomplete frame.

## Step 4: Validate N0

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.e2e_c0_capture check `
  --run-dir "artifacts\recognition_upgrade\e2e_c0\n0_capture_01"
```

Pass requires:

- 600 reviewed, eligible zero-hand frames;
- 20 clips and 600 seconds;
- 6 participants;
- 2 devices;
- 5 environments;
- no incomplete or missing files.

If contaminated/quarantined frames reduce the eligible count below 600, record more N0 video and
prepare a new run ID. Do not overwrite `n0_capture_01`.

## Step 5: Prepare P1

The P1 review is intentionally limited to 100 frames because every eligible frame needs hand boxes.

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.e2e_c0_capture prepare `
  --raw-root "scratchpad\e2e_c0_capture\raw" `
  --kind p1 `
  --output "artifacts\recognition_upgrade\e2e_c0\p1_capture_01"
```

## Step 6: Review P1

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.e2e_c0_capture review `
  --run-dir "artifacts\recognition_upgrade\e2e_c0\p1_capture_01"
```

For every center frame:

1. Count every visible hand, including blurred, clipped, or partly blocked hands.
2. Draw one tight box around each visible hand extent.
3. Leave anatomical side as `unknown`; E2e-C0 is side-independent.
4. Mark blur, occlusion, near-face, edge-clipped, and partial visibility when applicable.
5. Save and continue.

Frames with no visible hand are excluded from P1 automatically.

## Step 7: Validate P1

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.e2e_c0_capture check `
  --run-dir "artifacts\recognition_upgrade\e2e_c0\p1_capture_01"
```

Pass requires 100 reviewed frames with at least one visible hand and valid boxes.

## Generated Files

Each run contains:

- `capture_manifest.csv`: clip metadata and source hashes;
- `provenance.json`: sampling contract and commands;
- `center_images/`: exact frames used for detector evaluation;
- `context_panels/`: motion context shown during review;
- `internal_index.csv`: frame/source metadata;
- `gold_review.csv`: resumable human annotations;
- `gold_review.pre_review_backup.csv`: original review backup;
- `reviewed_manifest.csv`: final eligible/excluded rows;
- `capture_summary.json`: validation result and diversity counts.

All generated outputs remain under `artifacts/recognition_upgrade/e2e_c0/`.

## Common Errors

### Expected folder structure

The video is not exactly five levels below `n0` or `p1`. Move it to:

```text
kind/person/device/environment/front-or-back/video.mp4
```

### Duplicate video stem

Two videos have the same filename without extension. Rename each clip uniquely.

### Only N frames available

The recordings do not contain enough duration for the requested 1 FPS sample. Add more clips or
longer clips. Do not lower the registered 600/100 targets.

### Output directory already exists

Use a new run ID such as `n0_capture_02`. Existing evidence is intentionally overwrite-protected.

### Eligible frames below target

Some N0 frames contained hands, or some P1 frames contained no hands. Add more raw recordings and
prepare a new run.

## Source-Of-Truth Files

- `E2E_C0_DETECTOR_SCREENING_PLAN.md`
- `pipeline/tracking/e2e_c0_capture.py`
- `pipeline/tracking/e2e_gold_review.py`
- `E2E_ALL_HAND_GOLD_RESULT.md`

## Related Context Files

- `README.md`
- `EXPERIMENT_MATRIX.md`
- `RISK_REGISTER.md`
- `IMPLEMENTATION_READINESS_CHECKLIST.md`
- `../eval-protocol.md`
- `../runtime-constraints.md`

## Assumptions

- Videos can be decoded by the project OpenCV installation.
- Capture participants consent to local research use.
- Participant/device/environment folder IDs are truthful and stable.

## Open Questions

- Back-camera robustness is unmeasured because the final fixtures use front-camera capture.
- Whether P1 needs broader participant/environment coverage after the first detector transfer result.
- Whether the HaGRID checkpoint transfers to the frozen fixture domains.

## Risks

- Accidental visible hands can contaminate N0.
- Adjacent sampled frames remain correlated within a clip.
- Metadata folder mistakes can create false diversity.
- Poor consent handling can make otherwise useful recordings unusable.

## Architecture Decisions

- Reuse the proven gold-review GUI and schema.
- Sample deterministically at 1 FPS with whole-video provenance.
- Keep N0 and P1 separate because visible idle hands are real detector positives.
- Never overwrite prior run directories.

## Next Required Action

Use the frozen runs and hashes in `E2E_C0_CAPTURE_RESULT.md`. Resolve and freeze the exact
HaGRID checkpoint/license/preprocessing contract, then prepare the registered C0-A smoke. Do not
record replacement fixtures or start full inference without a new approved reason.
