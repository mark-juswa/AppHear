# E3-B6 Landmark Feature Augmentation Plan

**Purpose:** Test whether deterministic derived landmark-motion and relationship features improve
recognition on the frozen E3-B5 50-class signer-disjoint split.

**Scope:** Offline isolated experiment only. This does not change Android, production recognizer
assets, the v3.0 feature contract, datasets, or model files used by the current app.

**Current status:** Prepared and smoke-tested locally on 2026-07-29. Full training is pending and
belongs to the developer because it is the long step.

**Last updated:** 2026-07-29.

## Verified Project References

- Runner: `pipeline/rgb/e3_b6_feature_augmentation.py`.
- Prepared run: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_03_feature_augmented`.
- Source run: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed`.
- Source result: `E3_B5_RESULT.md`.
- Current production feature contract: `../feature-schema.md`.
- Experiment feature schema: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_03_feature_augmented/feature_schema.json`.

## Why This Comes Next

E3-B5 showed useful landmark signal but did not justify promoting masked TCN. The best mean
validation branch was `tcn_masked_pool`, but it won only one of three seeds and did not improve mean
test accuracy. The next controlled question is whether the landmark representation itself needs
explicit motion and relative-geometry features before returning to RGB/fusion.

E3-B6 keeps the E3-B5 split frozen so all accuracy changes are attributable to the feature
augmentation and model branch, not a new sample or vocabulary.

## Dataset Contract

- Source: frozen E3-B5 prepared tensor.
- Classes: `50`.
- Rows: `1,200`.
- Split: `800` train, `200` validation, `200` test.
- Signer split: inherited from E3-B5; no signer overlap.
- Labels and class order: identical to E3-B5.
- Validation rule: checkpoint and branch selection use validation metrics only; test remains
  reporting-only.

## Experiment Feature Schema

This is **not** a production schema change. It is an experiment-only tensor:

- Base v3.0 landmarks: `258`.
- XYZ velocity: `225`.
  - Hands: `126` x/y/z channels.
  - Pose: `99` x/y/z channels.
  - Pose visibility is not differenced.
- XYZ acceleration: `225`.
- Relationship/presence features: `20`.
- Total: `[96,728]`.

Derived-feature rules:

- Velocity is `x[t] - x[t-1]`.
- Acceleration is `velocity[t] - velocity[t-1]`.
- Deltas require adjacent real frames.
- Padded frames are forcibly zeroed across all channels.
- Relationship features include:
  - left/right hand wrist to pose wrist offsets,
  - left/right hand wrist to shoulder offsets,
  - hand-to-hand wrist vector,
  - hand-to-hand wrist distance,
  - left/right hand-present flags,
  - frame-valid flag,
  - mean pose visibility.

All operations are simple arithmetic and therefore Android-portable if the experiment later passes.

## Branches

E3-B6 trains the same model families on the augmented feature tensor:

- `aug_conv1d_baseline` -> E3-B5 `conv1d_baseline` model family.
- `aug_tcn_pool` -> E3-B5 `tcn_pool` model family.
- `aug_tcn_masked_pool` -> E3-B5 `tcn_masked_pool` model family.

Seeds: `101`, `202`, `303`.

## Baseline Reference

E3-B5 reference:

| Branch | Mean Best Validation | Mean Best Test |
|---|---:|---:|
| `conv1d_baseline` | `0.4750` | `0.3400` |
| `tcn_pool` | `0.4733` | `0.3433` |
| `tcn_masked_pool` | `0.4900` | `0.3433` |

## Gate

Go if:

- the best augmented branch improves mean best-validation over E3-B5 masked TCN by at least `0.03`;
- mean best-test is not below E3-B5 masked TCN;
- train-validation gap does not increase materially;
- worst-class and confusion concentration improve after analysis.

No-go if:

- only train accuracy improves;
- validation/test gap grows;
- prediction bias increases;
- test accuracy regresses.

## Local Validation Completed

- Syntax compile passed.
- Prepare passed.
- Prepared tensor shape: `[1200,96,728]`.
- Structural check passed:
  - required files present,
  - no NaN/Inf,
  - padded frames zeroed,
  - row counts aligned.
- Smoke test passed for all three branches:
  - model construction,
  - forward pass,
  - one training batch,
  - checkpoint save/reload,
  - smoke output writing.

## Commands

Full run:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b6_feature_augmentation run --run-dir "artifacts\recognition_upgrade\e3_landmark_temporal\pilot_03_feature_augmented"
```

Resume:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b6_feature_augmentation run --run-dir "artifacts\recognition_upgrade\e3_landmark_temporal\pilot_03_feature_augmented" --resume
```

Check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b6_feature_augmentation check --run-dir "artifacts\recognition_upgrade\e3_landmark_temporal\pilot_03_feature_augmented" --require-metrics
```

## Architecture Decisions

- Keep E3-B5 split frozen.
- Do not modify production v3.0 feature schema.
- Do not promote derived features without a later Kotlin parity/skew-test plan.
- Do not start RGB/fusion scaling until E3-B6 result is evaluated.

## Assumptions

- Explicit velocity/acceleration can help movement-dependent signs that raw coordinates do not
  separate well.
- Relationship features can help signs where hand-to-body or two-hand geometry matters.
- The larger feature dimension is acceptable for an offline experiment; Android feasibility is
  evaluated only if the result passes.

## Open Questions

- Will the extra features improve validation/test or only train accuracy?
- Are the weak E3-B5 classes caused by missing information or model capacity?
- Does the `[96,728]` tensor make TCN overfit faster?
- Would a smaller derived-feature subset work better if the full set overfits?

## Risks

- Increased feature dimension may overfit the small 50-class split.
- Derived features may amplify landmark jitter.
- Any promoted derived schema later requires exact Kotlin implementation and skew tests.
- Some signs may still require RGB hand-shape features.

## Next Required Action

Developer runs the full E3-B6 command, then the final check. After metrics are available, analyze
E3-B6 against E3-B5 before approving any next architecture branch.
