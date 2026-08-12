# E2b Paired ROI-Recovery Plan

## Purpose

Define the controlled experiment required after E2 showed that RGB hand-crop availability,
not crop output resolution, is the first blocking issue.

## Scope

This document covers E2b Phase A only: compare the frozen E2 control ROI against causal
pose-hand-anchor recovery on exactly paired frame-hand-cadence items. It does not authorize E3
training, production Android changes, MediaPipe replacement, or crop-size selection.

## Current Status

COMPLETE - NO-GO. E2 is an engineering no-go: 167/358 visible-hand panels were
usable (46.65%), and ROI availability was 224/358 (62.57%). The E2 98% parent gate remains
unchanged.

## Verified Project References

- `pipeline/crops/roi.py`: direct hand-landmark square ROI plus 100 ms causal static hold.
- `pipeline/crops/run.py`: E2 panel generation from existing IMAGE-mode landmarks.
- `pipeline/config/crops_e2.yaml`: frozen E2 crop candidates and parent gate.
- E2 Run 02 corrected audit: 600 panels; 358 target hands visible; 135 missing ROI,
  38 source-motion-blur, 7 clipped, 6 low-detail, and 5 wrong-hand failures.
- The Run 02 design is not sufficiently paired to select 80/96/112 pixels or
  1.5/1.75/2.0 expansion.

## Source Of Truth

- Experiment config: `pipeline/config/crops_e2b.yaml`
- ROI algorithms: `pipeline/crops/roi.py`
- Generator: `pipeline/crops/e2b.py`
- Audit analysis: `pipeline/crops/e2b_audit.py`
- Parent decision and rollback: `context/recognition_upgrade/E2_CROP_QUALITY_RUNBOOK.md`

## Architecture Decision

Phase A compares four strategies on each selected base item:

1. `control_hold_100`: current direct ROI plus static hold for at most 100 ms.
2. `pose_track_150`: direct ROI, otherwise causal pose-hand-anchor translation for at most
   150 ms since the last direct hand ROI, then a current-pose hand-anchor fallback.
3. `pose_track_250`: same with a 250 ms tracking age.
4. `pose_track_350`: same with a 350 ms tracking age.

Every strategy uses the same source frame, target hand, cadence, 112-pixel output, and
1.75 expansion. The crop geometry is diagnostic and is not an approved production choice.
Pose fallback size is fit from direct hand boxes in E2 training-split clips only, using the
configured robust quantile of hand-box-side/shoulder-width. Test data is not used.

All operations are causal. An unsampled frame cannot refresh hand or pose state. The panel
is unmirrored; `left` and `right` are the signer's anatomical sides.

## Evaluation And Gates

The unchanged parent E2 gate is 98% usable among frames where the target hand is visibly
present. E2b adds a diagnostic promotion gate, not a replacement acceptance gate:

- paired ROI-availability gain of at least 20 percentage points over control at every
  cadence;
- stale plus wrong-hand failures no greater than 2% of visible target-hand panels;
- no strategy is selected from unpaired aggregate rates;
- source-motion-blurred frames are reported separately but remain failures under the
  unchanged parent gate.

Passing the diagnostic gate permits Phase B, where the winning ROI strategy is frozen and
all crop-size/expansion candidates are compared on paired items. It does not permit E3.

## Assumptions

- E2 corrected human visibility labels are sufficiently accurate to define known-visible
  base items.
- Pose hand-anchor identity agrees with canonical hand slots often enough to test recovery.
- A 120-base-item paired audit is sufficient for an engineering decision, not a final
  accuracy claim.

## Open Questions

- Does pose fallback contain fingers during rapid depth motion and two-hand interaction?
- Which maximum tracking age best balances cadence recovery against stale crops?
- Is the E2 human visibility audit consistent enough across duplicate base items?
- After recovery, can any strategy meet the unchanged 98% parent usability gate?

## Risks

- Pose hand anchors may lag, swap, or be absent when hands cross.
- A current-pose hand-anchor fallback may improve availability while producing clipped or wrong crops.
- Source motion blur creates an upper bound that ROI recovery alone cannot remove.
- The 112-pixel diagnostic rendering may hide differences relevant to a future RGB encoder.

## Rollback

Delete or ignore the separate E2b output directory. No production source, schema, model,
asset, or Android behavior is changed. E2 Run 02 remains immutable.

## Next Required Action

The project owner runs the 120-base-item generation and 480-panel blinded review, then
runs paired analysis. Do not promote a strategy from smoke evidence.

## Related Context Files

- `README.md`
- `E2_CROP_QUALITY_RUNBOOK.md`
- `EXPERIMENT_MATRIX.md`
- `HYBRID_FUSION_DESIGN.md`
- `ROLLBACK_AND_COMPATIBILITY_PLAN.md`

## Last Updated

2026-07-26

## Validated Tooling And Commands

The final bounded smoke is `smoke_validation_03`: six paired base items, both hands at native,
k4, and k8 cadence, four strategies per item, and 24/24 panels present. Pose fallback recovered
four of six deliberately missing control ROIs; two remained explicit missing ROIs. The train-only
fallback fit used 2,334 direct observations and selected raw-side/shoulder-width ratio
`0.7222874915`. A separate 2,268-observation geometry check measured 95.55% direct-landmark
containment for the pose hand anchor versus 73.68% for wrist center.

Full paired generation (short preprocessing, no MediaPipe extraction or training):

```powershell
.\.venv\Scripts\python.exe -m pipeline.crops.e2b `
  --run-id engineering_e2b_01
```

Reviewer preflight and launch:

```powershell
$run = "F:\ASL DATASET\ASL CITIZEN\derived\apphear3\recognition_upgrade\e2b_roi_recovery_v0\engineering_e2b_01"
.\.venv\Scripts\python.exe -m pipeline.crops.review --run-dir $run --check
.\.venv\Scripts\python.exe -m pipeline.crops.review --run-dir $run
```

For E2b, reviewer key `4` means source-frame motion blur: use it only when the visible target hand
is already blurred in the full-frame panel. Key `7` means the ROI exists but crop detail is
insufficient. The panels are unmirrored and hand labels are the signer's anatomical side.

After all rows are reviewed:

```powershell
.\.venv\Scripts\python.exe -m pipeline.crops.e2b_audit `
  --audit-csv "$run\audit_template.csv" `
  --index-csv "$run\internal_index.csv" `
  --output "$run\audit_summary.json"
```