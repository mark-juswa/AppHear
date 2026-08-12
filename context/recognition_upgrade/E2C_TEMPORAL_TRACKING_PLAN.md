# E2c Temporal Hand-Tracking Plan

## Purpose

Test whether MediaPipe Hand Landmarker VIDEO mode provides materially better chronological
hand detection and crop continuity than the current stateless IMAGE mode.

## Scope

E2c is an offline, paired preprocessing experiment. It does not change production Stage E,
Android `RunningMode.IMAGE`, the 258-feature schema, any model asset, or recognition behavior.
It does not train a recognition model.

## Current Status

COMPLETE - NO-GO. E2 and E2b are no-go. E2b showed that pose recovery improved
availability at low cadence but produced usable recovered crops in only 8-9/38 cases.

## Verified Project References

- `pipeline/extract/landmarks.py` uses Hand Landmarker `RunningMode.IMAGE` and `detect`.
- `android/app/src/main/java/com/example/apphear/pipeline/LandmarkerBundle.kt` also uses
  `RunningMode.IMAGE`.
- Installed MediaPipe version is 0.10.35. Its installed API exposes
  `detect_for_video(image, timestamp_ms)`.
- Hand model: `assets/mediapipe/hand_landmarker.task`, approximately 7.8 MB.
- Current thresholds in `pipeline/config/extract.yaml`: two hands and 0.5 detection,
  presence, and tracking confidence.
- E2b source: 120 known-visible paired base items at native/k4/k8 cadence.

## Architecture Decision

For each base item's complete source clip and registered cadence:

1. Decode chronological raw frames once.
2. Feed sampled frames to a fresh IMAGE landmarker.
3. Feed the same sampled frames and original monotonic timestamps to a fresh VIDEO
   landmarker.
4. Recreate VIDEO state for every clip/cadence; state must never cross clip boundaries.
5. Preserve current anatomical Left/Right slot mapping.
6. Create one blinded paired panel per base item: full frame, crop A, crop B. A/B mapping is
   deterministic and stored only in the internal map.
7. Record per-call p50/p95 latency, detection availability, scores, boxes, padding, and
   sharpness.

IMAGE and VIDEO use the exact same model, thresholds, frames, timestamps, crop geometry, and
target hand. Running mode is the only independent variable.

## Review Contract

The source frame is reviewed once, not once per strategy. The reviewer records:

- source clear or source motion blur;
- A crop: usable, missing, clipped, stale, wrong hand, low detail, or other;
- B crop: the same outcomes.

Exact strategy panels are therefore not duplicated, avoiding the E2b consistency defect.
The target hand is already known-visible from corrected E2 evidence and is not relabeled.

## Registered Gates

VIDEO promotion requires all of:

- paired known-visible ROI-availability gain at least 20 percentage points over IMAGE at
  native, k4, and k8;
- wrong-hand plus stale-crop rate no greater than 2%;
- VIDEO p95 Python hand-inference latency no greater than 1.20 times IMAGE p95 on the same
  host and frames;
- no cadence or anatomical-hand subgroup regression;
- the unchanged parent crop-usability gate remains 98%.

The Python timing result is comparative only. Android performance still requires a later
device benchmark.

## Stop Rules

- Run automatic generation and inspect `generation_summary.json` before human review.
- If availability or latency decisively fails, stop without reviewing all panels.
- If diagnostics pass, complete the paired human review and run the E2c analyzer.
- Do not start crop-geometry Phase B or E3 unless the complete gate passes.

## Assumptions

- E2b base items remain known-visible.
- Raw video frame order and timestamps match MediaPipe chronological requirements.
- Recreating the landmarker per clip prevents hidden state leakage.

## Open Questions

- Does VIDEO mode recover detections or mostly smooth already-detected hands?
- Does handedness remain stable during crossings and occlusion?
- Does k8 tracking help when observations are approximately 267 ms apart?
- Is VIDEO-mode behavior reproducible in Android LIVE_STREAM mode?

## Risks

- Tracking can preserve stale or wrong-hand state.
- IMAGE/VIDEO may produce identical output if detector confidence dominates.
- Python latency does not predict Android latency directly.
- Source blur can cap crop usability even when tracking succeeds.

## Rollback

Delete or ignore the separate E2c derived-output directory. No production file is replaced.

## Source Of Truth

- Config: `pipeline/config/tracking_e2c.yaml`
- Generator: `pipeline/tracking/e2c.py`
- Reviewer: `pipeline/tracking/review.py`
- Analyzer: `pipeline/tracking/audit.py`
- Result decision: this document plus a future E2c result file.

## Related Context Files

- `E2B_PHASE_A_RESULT.md`
- `EXPERIMENT_MATRIX.md`
- `ANDROID_DEPLOYMENT_PLAN.md`
- `EVALUATION_AND_ACCEPTANCE_GATES.md`
- `ROLLBACK_AND_COMPATIBILITY_PLAN.md`

## Next Required Action

The project owner runs the 120-base-item engineering generation and returns
`generation_summary.json` before manual review. Review starts only if the automatic gate warrants it.

## Last Updated

2026-07-26

## Validated Smoke And User Commands

`smoke_validation_01` completed six known-visible base items covering both anatomical hands at
native/k4/k8. It produced six paired panels, 12 mode records, 756 inference calls, complete
provenance, and no missing review panels. VIDEO recovered one deliberately missing k8 target.
The smoke is structural, not a promotion result. Full validation: 151 tests passed; focused Ruff
and mypy passed.

### Stage 1 - Engineering Generation

From `F:\ASL DATASET\5. Apphear3`:

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.e2c `
  --run-id engineering_e2c_01
```

Expected CPU duration is approximately 4-8 minutes. No GPU, extraction of pose landmarks, or
training is involved. The run is non-resumable but refuses to overwrite an existing run directory.
Output is written only under:

`F:/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/e2c_temporal_tracking_v0/engineering_e2c_01`

After completion, inspect or return this file before reviewing:

```powershell
$run = "F:\ASL DATASET\ASL CITIZEN\derived\apphear3\recognition_upgrade\e2c_temporal_tracking_v0\engineering_e2c_01"
Get-Content "$run\generation_summary.json"
```

### Stage 2 - Conditional Human Review

Run this only after automatic-result approval:

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.review --run-dir $run --check
.\.venv\Scripts\python.exe -m pipeline.tracking.review --run-dir $run
```

Each of 120 panels is reviewed once in three steps:

1. `C` source hand is clear, or `M` source hand has motion blur.
2. Judge crop A with `1` usable, `2` missing, `3` clipped, `4` stale, `5` wrong hand,
   `6` low detail, or `7` other.
3. Judge crop B with the same keys. The decision saves and advances automatically.

`P` moves to the previous panel; `Esc` saves and exits. A/B identities stay blinded.

After all 120 panels are complete:

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.audit --run-dir $run
```