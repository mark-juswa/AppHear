# E4-U Confusion Evidence Package

**Purpose:** Prepare a reusable evidence package for confusion-group specialist/data-repair decisions, using `SORRY -> GOOD` as the first representative case.
**Scope:** Evidence preparation only. No training, Android integration, TFLite export, production recognizer replacement, broad vocabulary expansion, or manual review of every sign is authorized.
**Current status:** PREPARED / STRUCTURAL CHECK PASSED.
**Last updated:** 2026-08-02.

## Verified Project References

- Runner: `pipeline/rgb/e4_u_confusion_evidence.py`
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_u_sorry_good_evidence_01`
- Source primary model run: `artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01`
- Source router run: `artifacts/recognition_upgrade/e4_generalization/e4_t_router_simulation_01`
- Source raw-video manifest run: `artifacts/recognition_upgrade/e4_generalization/e4_j_reliable_core_3sign_pilot_01`
- Prior result: `E4_T_ROUTER_SIMULATION_RESULT.md`
- Roadmap: `DYNAMIC_MIXED_RECOGNITION_ROADMAP.md`

## Why This Exists

E4-T showed that simple confidence/margin routing cannot prevent `SORRY` from being falsely committed as `GOOD`. This is not being handled as a one-word manual loop. It is a representative test case for a reusable class of failures:

- high-confidence false commits;
- confusing signs that collapse into a stable primary sign;
- signs that may require richer evidence, variant repair, or a specialist resolver.

The immediate objective is to decide the correct resolver pattern before scaling it to other confusion groups.

## Prepared Evidence

Target confusion:

- Confusion target: `SORRY`
- False commit: `GOOD`
- Split: `test`

Rows prepared:

- Total rows: `60`
- `primary_reference`: `30` true `GOOD` held-out rows
- `confusion_target`: `30` true `SORRY` held-out rows
- Generated panels: `60`
- Panel failures: `0`

Main outputs:

- `review/confusion_evidence_manifest.csv`
- `contact_sheets/primary_reference_test.jpg`
- `contact_sheets/confusion_target_test.jpg`
- `panels/primary_reference/test/*.jpg`
- `panels/confusion_target/test/*.jpg`
- `pilot_config.json`
- `logs/prepare_summary.json`
- `check_report.json`

## What The Manifest Contains

Each row includes:

- sample id;
- evidence kind: `primary_reference` or `confusion_target`;
- canonical gloss;
- false-commit gloss;
- held-out signer id;
- original raw video path;
- frame count, FPS, hand-hit rate, and warnings when available;
- E4-S/E4-T seed prediction summary;
- generated panel path.

This is intended to support a fast technical decision:

1. If `SORRY` and `GOOD` visibly differ in hand/body/chest evidence, run an RGB or crop specialist.
2. If the labels/variants are mixed, repair/review/recollect before training.
3. If the video evidence is too weak or too short, collect a better targeted confusion set.

## Commands Already Run

Prepare:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_u_confusion_evidence prepare --output "artifacts\recognition_upgrade\e4_generalization\e4_u_sorry_good_evidence_01"
```

Check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_u_confusion_evidence check --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_u_sorry_good_evidence_01" --require-panels
```

Result:

- Structural check passed.
- The image viewer in Codex could not render the sheets because of the Windows sandbox wrapper, but the files exist at the paths listed above.

## Architecture Decisions

- Use confusion groups as reusable resolver units, not individual sign-by-sign manual loops.
- Start with `SORRY -> GOOD` because it is a proven high-confidence false-commit case.
- Do not repeat threshold-only router tuning for this group.
- Do not build RGB/fusion globally; use richer evidence only where a group has demonstrated need.

## Assumptions

- The E4-J raw local video manifest is the correct source for visual inspection of the held-out `GOOD` and `SORRY` rows.
- The first specialist/data-repair decision can be made from held-out test evidence before training another model.
- The pattern should generalize to other registered confusion groups if the evidence package structure is kept.

## Open Questions

- Are the `SORRY` videos label/variant-consistent?
- Does `SORRY` differ from `GOOD` visually in hand placement, chest/body contact, palm orientation, or motion path in these rows?
- Are the clips too short for reliable RGB temporal modeling?
- Should the next experiment be RGB specialist training, targeted relabel/variant repair, or new targeted capture?

## Risks

- If the source videos are too short or too homogeneous, visual inspection may overstate specialist feasibility.
- A specialist trained only on this tiny local held-out set can overfit.
- If `SORRY` is semantically or visually inconsistent, model changes will not solve the issue without data repair.
- The project can lose time if every confusing sign is handled manually; this package must remain a reusable pattern.

## Next Required Action

Review the two contact sheets and evidence manifest to choose the next bounded experiment:

- RGB/crop specialist if visual evidence is clearly separable;
- data/variant repair if labels or signing forms are inconsistent;
- targeted recollection if the clips are too short or weak;
- defer `SORRY` if none of the above is feasible quickly.
