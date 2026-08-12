# E3-B6 Landmark Feature Augmentation Result

**Purpose:** Record the completed frozen-split landmark derived-feature experiment and its
architecture decision.

**Scope:** Offline isolated-sign experiment only. This does not authorize Android integration,
production model replacement, dataset changes, or a v3.0 runtime feature-contract change.

**Current status:** COMPLETE. Derived features improved test accuracy, but the promotion gate did
not pass.

**Last updated:** 2026-07-29.

## Verified Project References

- Runner: `pipeline/rgb/e3_b6_feature_augmentation.py`.
- Run directory: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_03_feature_augmented`.
- Metrics: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_03_feature_augmented/metrics/metrics.json`.
- Check report: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_03_feature_augmented/check_report.json`.
- Feature schema: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_03_feature_augmented/feature_schema.json`.
- Source run: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed`.
- Baseline result: `E3_B5_RESULT.md`.

## Experiment Contract

- Source split: frozen E3-B5 50-class signer-disjoint split.
- Rows: `1,200`.
- Split: `800` train, `200` validation, `200` test.
- Input: `[96,728]`.
- Feature layout:
  - base v3.0 landmarks: `258`;
  - xyz velocity: `225`;
  - xyz acceleration: `225`;
  - relationship/presence features: `20`.
- Branches:
  - `aug_conv1d_baseline`;
  - `aug_tcn_pool`;
  - `aug_tcn_masked_pool`.
- Seeds: `101`, `202`, `303`.
- Epochs completed: `24` total per branch/seed after resume.
- Validation rule: checkpoint and branch selection use validation metrics only; test is reporting-only.

## Structural Result

- Final check passed with no errors.
- Metrics were generated for all three branches and all three seeds.
- Smoke had previously passed for model creation, forward pass, one train step, and weight save/reload.

## Accuracy Summary

| Branch | Mean Best Train | Mean Best Validation | Mean Best Test | Train-Val Gap | Val-Test Gap |
|---|---:|---:|---:|---:|---:|
| `aug_conv1d_baseline` | `0.8154` | `0.5033` | `0.3883` | `0.3121` | `0.1150` |
| `aug_tcn_pool` | `0.6592` | `0.4767` | `0.3683` | `0.1825` | `0.1083` |
| `aug_tcn_masked_pool` | `0.8258` | `0.5117` | `0.3867` | `0.3142` | `0.1250` |

E3-B5 reference:

| Branch | Mean Best Validation | Mean Best Test |
|---|---:|---:|
| `conv1d_baseline` | `0.4750` | `0.3400` |
| `tcn_pool` | `0.4733` | `0.3433` |
| `tcn_masked_pool` | `0.4900` | `0.3433` |

Seed winners by E3-B6 best validation:

- Seed `101`: `aug_tcn_masked_pool`.
- Seed `202`: `aug_conv1d_baseline`.
- Seed `303`: `aug_conv1d_baseline`.

## Decision

**No promotion yet.**

The best mean-validation branch was `aug_tcn_masked_pool`, but its validation gain over E3-B5 masked
TCN was only `+0.0217`, below the registered `+0.03` threshold. It did improve mean test accuracy by
about `+0.0434`, but the train-validation gap remained large and seed winners were not stable.

This is a useful result, not a failed run:

- derived features improved held-out test performance for the best branches;
- the improvement did not clearly select a stable architecture;
- the larger feature tensor increased overfitting risk, especially for the augmented Conv1D and
  masked TCN branches.

## Error/Behavior Findings

- `aug_tcn_masked_pool` improved test accuracy from E3-B5 masked TCN `0.3433` to `0.3867`.
- `aug_conv1d_baseline` had the best mean test accuracy at `0.3883`, with very low test variance.
- `aug_tcn_pool` had the smallest train-validation gap, but did not improve validation enough.
- The largest overfit remains in `aug_tcn_masked_pool` and `aug_conv1d_baseline`.
- Useful class gains from augmentation include examples such as `BOTH`, `LETTUCE1`, `BUY`,
  `SWITZERLAND`, `BEE1`, `SHARK1`, and `DEMAND1`, depending on branch.
- Regressed classes include examples such as `LAND`, `SHAVE1`, `TWINS1`, `CHEESEGRATER`,
  `EVERYYEAR`, and `TYPE1`.
- Persistent confusion groups remain, including `TAKECARE -> EVERYYEAR`, `CROSS3 -> WHALE`,
  `ROCKINGCHAIR1 -> TRACTOR`, `EDIT1 -> INDEPENDENT`, `SINK/RIVER1 -> DEMAND1`, and
  `DEAF1 -> TWINS1`.

## Engineering Interpretation

The derived motion/relationship features are useful, especially for test generalization, but the
full `[96,728]` tensor is probably too broad for the current small models and 50-class sample size.
The result suggests that motion/relationship features should not be discarded, but the next step
should be a smaller ablation rather than promoting the full augmented schema.

The strongest practical conclusion is:

- keep the frozen E3-B5 split;
- keep augmentation as a candidate;
- test which derived feature group caused the benefit;
- reduce overfitting before returning to RGB/fusion.

## Recommended Next Experiment

Prepare **E3-B7 derived-feature ablation** on the same frozen split:

1. base `258` only control from E3-B5 reference;
2. base + velocity only;
3. base + velocity + relationship/presence;
4. base + relationship/presence only;
5. optionally base + velocity + acceleration if needed.

Use the most stable branches from E3-B6:

- `aug_conv1d_baseline` as the simple high-test comparator;
- `aug_tcn_masked_pool` as the highest-validation comparator;
- optionally omit ordinary `aug_tcn_pool` unless runtime allows, because it did not win.

Gate:

- retain or improve the E3-B6 test gain;
- reduce train-validation gap compared with full `[96,728]`;
- produce a clearer feature-group winner;
- avoid worse prediction bias/confusion concentration.

## Architecture Decisions

- Do not promote full `[96,728]` as the next landmark schema.
- Do not port derived features to Android yet.
- Do not start RGB/fusion scaling until E3-B7 clarifies whether the E3-B6 gain is robust and which
  feature group is responsible.
- Keep the E3-B5 split frozen for the next ablation.

## Assumptions

- The test gain is meaningful enough to investigate, even though the promotion gate failed.
- Full feature augmentation may be over-parameterized for the current branch/model capacity.
- A smaller derived-feature set may retain test gains with less overfitting.

## Open Questions

- Is velocity the main useful signal, or are relationship/presence features responsible?
- Does acceleration help or mostly amplify jitter/noise?
- Would smaller feature sets stabilize seed winners?
- Can a derived-feature branch reduce the persistent confusion groups?

## Risks

- Repeated experiments on the same frozen split can overfit experiment design to that split.
- Smaller ablations may lose the test gain seen in full E3-B6.
- Some classes may require RGB hand-shape features regardless of landmark improvements.

## Next Required Action

Architect and prepare E3-B7 derived-feature ablation. Do not run full training until the branch list,
feature subsets, and gate are reviewed.
