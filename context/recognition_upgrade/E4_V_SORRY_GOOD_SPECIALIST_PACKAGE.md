# E4-V GOOD/SORRY Specialist Proof Package

**Purpose:** Prepare a bounded proof-of-value experiment for the reusable confusion-group resolver path by comparing a landmark-only binary control against an upper-body RGB specialist for `SORRY -> GOOD`.
**Scope:** Offline experiment package only. No Android integration, TFLite export, production recognizer replacement, broad vocabulary expansion, or global RGB/fusion rollout is authorized.
**Current status:** PREPARED / SMOKE PASSED / STRUCTURAL CHECK PASSED / FULL TRAINING NOT YET RUN.
**Last updated:** 2026-08-02.

## Verified Project References

- Runner: `pipeline/rgb/e4_v_sorry_good_specialist.py`
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01`
- Evidence package: `artifacts/recognition_upgrade/e4_generalization/e4_u_sorry_good_evidence_01`
- Raw-video/landmark source run: `artifacts/recognition_upgrade/e4_generalization/e4_j_reliable_core_3sign_pilot_01`
- Prior router result: `E4_T_ROUTER_SIMULATION_RESULT.md`
- Prior evidence package: `E4_U_CONFUSION_EVIDENCE_PACKAGE.md`

## Why This Experiment Exists

E4-S proved `GOOD`, `HELLO`, `HAVE`, and `KNOW` are strong closed-set primary candidates. E4-T then showed simple confidence/margin routing cannot reject `SORRY`, because held-out `SORRY` is predicted as high-confidence `GOOD`. The user reviewed E4-U contact sheets and confirmed `SORRY` is visibly different from `GOOD`.

Therefore E4-V tests whether RGB evidence can separate this confusion group better than landmarks alone.

This is not a one-word loop. It is the first proof of the specialist resolver pattern:

`stable primary -> registered confusion group -> conditional specialist -> accept/reject`

## Dataset Contract

Classes:

- `GOOD`
- `SORRY`

Rows:

- Total rows: `100`
- Train: `30`
- Validation: `10`
- Test: `60`

Class counts:

- Train: `GOOD 15`, `SORRY 15`
- Validation: `GOOD 5`, `SORRY 5`
- Test: `GOOD 30`, `SORRY 30`

Split source:

- Inherited from E4-J.
- Signer-disjoint: train/validation and test use different signer ids as recorded in E4-J.

## Branches

1. `landmark_binary_control`
   - Input: schema `3.0` `[96,258]` landmark features.
   - Purpose: prove whether the existing landmark representation alone can solve the binary group.

2. `rgb_upper_body`
   - Input: raw local videos sampled to `8` frames.
   - Crop: `upper_body_center`.
   - Image size: `160`.
   - Encoder: frozen `MobileNetV3Small` with ImageNet weights.
   - Temporal head: small Conv1D head over frame embeddings.
   - Purpose: test whether visual hand/body/chest evidence separates `GOOD` from `SORRY`.

Seeds:

- `101`
- `202`
- `303`

Training defaults:

- Epochs: `20`
- Batch size: `8`
- Learning rate: `5e-4`

## Gate

E4-V is promising only if the RGB branch satisfies:

- Mean test accuracy >= `0.90`
- Mean `GOOD` recall >= `0.90`
- Mean `SORRY` recall >= `0.90`
- Mean RGB test accuracy improves over landmark control by at least `0.05`

Passing E4-V would authorize a broader specialist/router simulation. It would not authorize Android integration by itself.

## Commands Already Run

Prepare:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_v_sorry_good_specialist prepare --output "artifacts\recognition_upgrade\e4_generalization\e4_v_sorry_good_specialist_01"
```

Smoke:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_v_sorry_good_specialist smoke --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_v_sorry_good_specialist_01"
```

Structural check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_v_sorry_good_specialist check --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_v_sorry_good_specialist_01" --require-smoke
```

Result:

- Prepare passed.
- Smoke passed for `landmark_binary_control` and `rgb_upper_body`.
- Structural check passed.

## User-Run Full Training

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_v_sorry_good_specialist run --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_v_sorry_good_specialist_01"
```

Resume if interrupted:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_v_sorry_good_specialist run --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_v_sorry_good_specialist_01" --resume
```

Final check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_v_sorry_good_specialist check --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_v_sorry_good_specialist_01" --require-smoke --require-metrics
```

## Assumptions

- The user's visual review is accepted as evidence that `SORRY` and `GOOD` are visibly separable.
- Upper-body RGB is a reasonable first specialist input because `SORRY` may require chest/body contact and hand-shape cues.
- The small local signer-disjoint split is sufficient for proof-of-value, not production readiness.

## Risks

- The split is small and may overstate or understate true generalization.
- RGB may overfit background, signer clothing, or camera setup.
- Frozen ImageNet MobileNet features may not capture ASL-specific hand detail.
- Clips are short, so temporal evidence may be limited.
- Passing this binary screen would still require a larger router/specialist simulation before Android.

## Next Required Action

User runs full E4-V training and final check. After metrics are available, evaluate whether RGB specialist evidence is actually better than the landmark binary control.
