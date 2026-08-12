# E2e All-Hand-Box Gold Audit Workflow

## Purpose

Measure MediaPipe hand-box reliability without confusing detector absence with handedness, target-slot, or source-mirroring errors.

## Scope

This workflow is experiment-only. It generates a blinded ASL Citizen review set, records human boxes for every visible hand, and scores raw MediaPipe IMAGE-mode outputs. It does not change Android, MediaPipe thresholds, schema 3.0, model assets, extracted data, or recognition behavior.

## Current Status

LANDMARK-ASSOCIATION SMOKE PASSED / FULL 150-FRAME AUDIT AUTHORIZED.

The bounded package is `scratchpad/e2e_gold_audit_smoke_20260726`. Do not generate the 120-200-frame engineering audit until the developer completes and returns this six-frame GUI smoke.

## Source Of Truth Files

- Generator: `pipeline/tracking/e2e_gold.py`
- Reviewer: `pipeline/tracking/e2e_gold_review.py`
- Scorer: `pipeline/tracking/e2e_gold_audit.py`
- Tests: `tests/test_tracking_e2e_gold.py`
- Parent result: `E2E_ASL_CITIZEN_PILOT_RESULT.md`
- Audit contract: `E2E_COORDINATE_IDENTITY_AUDIT_PLAN.md`

## Sampling Contract

Eligible frames are human-visible positive controls from the frozen E2d item index at candidate `image_d50_p50`. Selection does not condition on MediaPipe success or failure, balances native/k4/k8 cadence groups, permits at most one frame per clip, enforces unique `(clip_id, frame_index)` pairs, and is deterministic for a recorded seed. Old E2 target-hand fields are sampling provenance only, not gold labels.

## Blinding Contract

Review only `center_images/`, `context_panels/`, and the GUI. `diagnostic_panels_do_not_review/` and `internal_index.csv` contain MediaPipe predictions and must remain hidden until annotation is complete.

## Annotation Contract

For every accepted center frame, the required workflow is only:

1. Choose `NO HANDS`, `ONE HAND`, or `TWO HANDS` for the large center frame.
2. If hands are visible, drag one tight box around each hand, including visible fingertips.
3. Check a quality problem only when it is present.
4. Click `SAVE AND NEXT`.

The GUI defaults source mirroring and anatomical hand identity to `unknown`; those optional fields are hidden because detector scoring does not require them. Open the optional section only when independent evidence exists. Never infer mirroring from MediaPipe output. Use `Cannot judge - skip` instead of guessing when visible count or box placement is ambiguous.

The GUI displays numbered instructions, blocks extra boxes beyond the selected count, previews the box while dragging, saves atomically, and creates a pre-review backup.

## Smoke Command

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.e2e_gold_review `
  --run-dir scratchpad/e2e_gold_audit_smoke_20260726
```

After all six frames:

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.e2e_gold_review `
  --run-dir scratchpad/e2e_gold_audit_smoke_20260726 `
  --check
```

Expected: `completed=6 remaining=0 errors=0`. Do not use six smoke frames for an accuracy claim.

## Full Audit Commands

These commands are registered but not yet authorized. After the GUI smoke is accepted, generate a 150-frame audit:

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.e2e_gold `
  --count 150 `
  --seed 260726 `
  --max-per-clip 1 `
  --source-pool balanced-clips `
  --output "F:\ASL DATASET\ASL CITIZEN\derived\apphear3\recognition_upgrade\e2e_all_hand_gold_v1\engineering_01"
```

Review it with the same reviewer module, then score only after `--check` reports no incomplete rows:

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.e2e_gold_audit `
  --run-dir "F:\ASL DATASET\ASL CITIZEN\derived\apphear3\recognition_upgrade\e2e_all_hand_gold_v1\engineering_01"
```

## Metrics

Primary metrics are visible-hand instance recall at IoU 0.50/0.75, any-hand frame recall, both-hands-complete recall, false-box rate, and cadence/blur/mirror subgroups. Identity accuracy is separate and uses only geometrically matched detections with independently adjudicated mirror status and known anatomical side.

## Architecture Decisions

- Keep raw predictions internal and blinded during annotation.
- Do not use E2 target-slot correctness as detector recall.
- Do not infer source mirroring from Hand or Pose labels.
- Do not authorize detector changes from a smoke set.
- Require at least 120 accepted frames before a gate decision.

## Assumptions

- E2 positive controls contain at least one human-visible hand.
- Chronological context supports most visibility decisions.
- This is an AppHear ASL Citizen diagnostic set, not a universal benchmark.

## Open Questions

- Can the box GUI be used without coordinate or identity ambiguity?
- How many full-audit frames require quarantine?
- What independent metadata can adjudicate source mirroring?
- Does an exact CameraX `ImageAnalysis` fixture confirm runtime behavior?

## Risks

- Viewing diagnostic panels would bias gold boxes.
- Treating unknown identity as an error would contaminate detector metrics.
- One reviewer may introduce box-boundary variance.
- Positive controls do not measure non-signing false positives; that needs a separate negative audit.

## Next Required Action

The corrected 150-frame audit is complete and authoritative. Proceed only to E2e-C0 independent hand-detector screening with a registered non-signing negative set. See `E2E_ALL_HAND_GOLD_RESULT.md`; do not begin E3 or Android integration.

## Last Updated

2026-07-26