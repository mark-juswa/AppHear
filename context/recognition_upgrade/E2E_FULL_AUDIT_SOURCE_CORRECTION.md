# E2e Full-Audit Source-Pool Correction

## Purpose

Record why the first 150-frame generation command failed, reject an unsafe relaxation of clip independence, and register the corrected source-pool contract.

## Scope

This correction changes only experimental audit sampling. It does not change human gold, MediaPipe settings, Android, the production recognizer, datasets, or model assets.

## Current Status

COMPLETE / 150 UNIQUE-CLIP AUDIT SCORED / MEDIAPIPE-SOLE-SOURCE NO-GO.

## Failed Source Contract

The first command requested 150 frames from the frozen E2d positive-control index with `max_per_clip=1`. The source contains:

- 120 eligible positive rows;
- 108 unique `(clip_id, frame_index)` pairs;
- 47 unique clips;
- 28 signers;
- 35/39/34 unique frames carrying native/k4/k8 provenance.

The request was mathematically impossible and correctly stopped before creating the output directory. The exact error was `only 47 unique frames satisfy max_per_clip=1`.

Increasing `max_per_clip` would not satisfy the intended independence contract and 150 frames remain impossible because the source has only 108 unique frames. That workaround is rejected.

## Corrected Source Contract

The audit now selects directly from the existing ASL Citizen train/validation clips eligible under `pipeline/config/crops_e2.yaml`:

- 150 unique clips;
- one frame per clip;
- 41 unique signers;
- 120 train and 30 validation clips;
- balanced prior hand-coverage strata: 48 low, 53 medium, 49 high;
- 50 frames each at 25%, 50%, and 75% through the annotated sign span;
- no current selected-frame MediaPipe result is consulted during selection.

The 25/50/75 positions replace misleading static-frame cadence balancing. FPS cadence is not a property of IMAGE-mode inference on one decoded frame and must be evaluated in a separate chronological sequence experiment.

## Known Limitation

Eligibility requires existing valid span, landmark, video, and split artifacts because this pool reuses the established E2 sampling infrastructure. The audit therefore estimates MediaPipe hand-instance reliability on AppHear's pipeline-eligible ASL Citizen corpus. It does not measure raw clips that failed all earlier preprocessing. Low/medium/high prior hand-coverage balancing mitigates, but does not eliminate, this eligibility bias.

## Smoke Verification

`scratchpad/e2e_balanced_clip_source_smoke_20260726` passed:

- six rows, six unique clips, and six unique signers;
- two samples at each sign-span position;
- all images, context panels, internal fields, and 21-landmark prediction payloads present;
- review contract check reported zero structural errors;
- output provenance identifies `asl_citizen_balanced_unique_clips_v1`.

The complete 150-item selection was evaluated without image generation and produced exactly 150 unique clips/frames, 41 signers, and 50 samples per span position. The full project suite passed 170 tests; Ruff and mypy passed.

## Architecture Decisions

- Use `balanced-clips` as the default full-audit source.
- Preserve the E2d source option only for bounded historical/smoke reproduction.
- Do not allow multiple frames per clip in this audit.
- Do not interpret sign-span position as FPS cadence.
- Keep non-signing false-positive evaluation as a separate negative audit.

## Source Of Truth Files

- `pipeline/tracking/e2e_gold.py`
- `pipeline/crops/sampling.py`
- `pipeline/config/crops_e2.yaml`
- `E2E_GOLD_AUDIT_WORKFLOW.md`
- `E2E_LANDMARK_ASSOCIATION_RESULT.md`
- `scratchpad/e2e_balanced_clip_source_smoke_20260726/provenance.json`

## Assumptions

- One frame per clip provides the cleanest available independence for this bounded audit.
- Balanced span positions provide more temporal coverage than selecting every clip midpoint.
- Train/validation source membership is metadata only; no recognition model is trained or evaluated here.

## Open Questions

- How many selected frames contain zero, one, and two visible hands after human review?
- Does prior low hand coverage predict missing MediaPipe instances?
- How many unmatched cases are partial, edge-clipped, blurred, occluded, or near-face?
- Is a separate raw-preprocessing-failure audit required before detector replacement?

## Risks

- Pipeline eligibility excludes raw clips without valid prior artifacts.
- One frame cannot measure temporal dropout or identity switching.
- Sign-span annotations may contain boundary noise.
- Manual review remains the dominant time cost.

## Next Required Action

Use `E2E_ALL_HAND_GOLD_RESULT.md` as the authoritative corrected result. Preserve this source contract for detector-candidate comparisons; next run E2e-C0 with a separate negative set.

## Last Updated

2026-07-26