# E3-B7 Derived-Feature Ablation Plan

**Purpose:** Identify which derived landmark feature group caused the useful E3-B6 test gain while
reducing overfitting risk.

**Scope:** Offline isolated experiment only. This does not change Android, production recognizer
assets, datasets, or the v3.0 runtime feature contract.

**Current status:** Prepared and smoke-tested locally on 2026-07-29. Full training is pending and
belongs to the developer because it is the long step.

**Last updated:** 2026-07-29.

## Verified Project References

- Runner: `pipeline/rgb/e3_b7_feature_ablation.py`.
- Prepared run: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_04_feature_ablation`.
- Source run: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed`.
- Prior result: `E3_B6_RESULT.md`.
- Baseline result: `E3_B5_RESULT.md`.
- Experiment feature schema: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_04_feature_ablation/feature_schema.json`.

## Why This Comes Next

E3-B6 improved test accuracy but did not pass the promotion gate. It mixed velocity, acceleration,
relationships, and presence features into one `[96,728]` tensor, so the result does not tell us
which part helped or whether acceleration mostly added noise.

E3-B7 keeps the frozen E3-B5 split and trains smaller feature subsets. This avoids changing the
benchmark again while isolating the useful signal.

## Dataset Contract

- Source: frozen E3-B5 50-class split.
- Rows: `1,200`.
- Split: `800` train, `200` validation, `200` test.
- Class order and labels: identical to E3-B5/E3-B6.
- Signer split: inherited and signer-disjoint.

## Variants

| Variant | Components | Shape |
|---|---|---:|
| `base_velocity` | base 258 + velocity | `[96,483]` |
| `base_relations` | base 258 + relationship/presence | `[96,278]` |
| `base_velocity_relations` | base 258 + velocity + relationship/presence | `[96,503]` |
| `base_velocity_acceleration` | base 258 + velocity + acceleration | `[96,708]` |

The full E3-B6 `[96,728]` tensor is not rerun here because it is already measured.

## Branches

E3-B7 uses the two branch families that mattered most in E3-B6:

- `conv1d`: simple high-test comparator.
- `masked_tcn`: high-validation temporal comparator.

Omitted:

- ordinary `tcn_pool`, because it did not win E3-B6 and keeping it would increase training cost
  without improving the main ablation question.

Seeds: `101`, `202`, `303`.

## Baseline References

| Reference | Mean Best Validation | Mean Best Test |
|---|---:|---:|
| E3-B5 masked TCN | `0.4900` | `0.3433` |
| E3-B6 full augmented masked TCN | `0.5117` | `0.3867` |
| E3-B6 full augmented Conv1D | `0.5033` | `0.3883` |

## Gate

Go if a reduced variant:

- retains E3-B6 mean best-test performance, target `>=0.3867`;
- has mean best-validation at least E3-B5 masked TCN, target `>=0.4900`;
- reduces train-validation gap compared with full E3-B6;
- gives a clearer feature-group winner and does not worsen prediction bias.

No-go if:

- the E3-B6 test gain disappears;
- only training accuracy improves;
- reduced variants overfit like the full `[96,728]` tensor;
- no subset identifies a clear useful feature group.

## Local Validation Completed

- Syntax compile passed.
- Prepare passed.
- Structural check passed.
- Smoke test passed for all four variants and both branches:
  - model construction,
  - forward pass,
  - one training batch,
  - checkpoint save/reload,
  - smoke output writing.

## Commands

Full run:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b7_feature_ablation run --run-dir "artifacts\recognition_upgrade\e3_landmark_temporal\pilot_04_feature_ablation"
```

Resume:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b7_feature_ablation run --run-dir "artifacts\recognition_upgrade\e3_landmark_temporal\pilot_04_feature_ablation" --resume
```

Check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b7_feature_ablation check --run-dir "artifacts\recognition_upgrade\e3_landmark_temporal\pilot_04_feature_ablation" --require-metrics
```

## Architecture Decisions

- Keep the E3-B5 split frozen.
- Do not promote full E3-B6 `[96,728]`.
- Do not port derived features to Android until E3-B7 identifies a smaller stable subset.
- Do not start RGB/fusion scaling until this ablation is evaluated.

## Assumptions

- E3-B6 test gain may be reproducible with fewer features.
- Acceleration may amplify jitter and should be tested separately from relationship features.
- A smaller feature set may retain useful signal with less overfitting.

## Open Questions

- Is velocity enough to explain the E3-B6 gain?
- Are hand/body relationships more useful than acceleration?
- Does acceleration help any branch, or does it mainly add noise?
- Can a smaller subset reduce persistent confusions?

## Risks

- Repeated use of the same frozen split can overfit experiment decisions.
- The reduced variants may lose the E3-B6 test gain.
- Landmark-only improvements may plateau and still require RGB hand-shape evidence.

## Next Required Action

Developer runs the full E3-B7 command, then final check. After metrics are available, compare
candidate summaries against E3-B5 and E3-B6 before deciding whether to keep landmark feature
engineering or return to RGB/fusion.
