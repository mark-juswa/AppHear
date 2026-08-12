# E3-B7 Derived-Feature Ablation Result

**Purpose:** Record the completed reduced derived-feature ablation and its architecture decision.

**Scope:** Offline isolated-sign experiment only. This does not authorize Android integration,
production model replacement, dataset changes, or a v3.0 runtime feature-contract change.

**Current status:** COMPLETE. Reduced subsets did not beat the full E3-B6 result.

**Last updated:** 2026-07-29.

## Verified Project References

- Runner: `pipeline/rgb/e3_b7_feature_ablation.py`.
- Run directory: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_04_feature_ablation`.
- Metrics: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_04_feature_ablation/metrics/metrics.json`.
- Check report: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_04_feature_ablation/check_report.json`.
- Plan: `E3_B7_FEATURE_ABLATION_PLAN.md`.
- Baselines: `E3_B5_RESULT.md`, `E3_B6_RESULT.md`.

## Experiment Contract

- Source split: frozen E3-B5 50-class signer-disjoint split.
- Rows: `1,200`.
- Split: `800` train, `200` validation, `200` test.
- Variants:
  - `base_velocity` `[96,483]`;
  - `base_relations` `[96,278]`;
  - `base_velocity_relations` `[96,503]`;
  - `base_velocity_acceleration` `[96,708]`.
- Branches: `conv1d`, `masked_tcn`.
- Seeds: `101`, `202`, `303`.
- Epochs completed: `24` total per candidate after resume.

## Structural Result

- Final check passed with no errors.
- All variants, branches, and seeds completed.
- The resumed run reached the same 24-epoch budget used for E3-B5 and E3-B6.

## Accuracy Summary

| Candidate | Mean Best Validation | Mean Best Test | Train-Val Gap |
|---|---:|---:|---:|
| `base_velocity_acceleration/masked_tcn` | `0.5150` | `0.3650` | `0.3083` |
| `base_relations/masked_tcn` | `0.5033` | `0.3833` | `0.3200` |
| `base_velocity_relations/masked_tcn` | `0.5000` | `0.3650` | `0.2763` |
| `base_velocity_acceleration/conv1d` | `0.4917` | `0.3733` | `0.2917` |
| `base_velocity/masked_tcn` | `0.4867` | `0.3533` | `0.3096` |
| `base_velocity_relations/conv1d` | `0.4800` | `0.3733` | `0.2558` |
| `base_velocity/conv1d` | `0.4717` | `0.3583` | `0.2517` |
| `base_relations/conv1d` | `0.4717` | `0.3567` | `0.2371` |

Baseline comparison:

| Reference | Mean Best Validation | Mean Best Test |
|---|---:|---:|
| E3-B5 masked TCN | `0.4900` | `0.3433` |
| E3-B6 full augmented masked TCN | `0.5117` | `0.3867` |
| E3-B6 full augmented Conv1D | `0.5033` | `0.3883` |

## Decision

**No promotion of a reduced subset.**

E3-B7 identified useful patterns, but no reduced variant beat the full E3-B6 test result. The
highest-validation reduced candidate was `base_velocity_acceleration/masked_tcn`, but its mean test
accuracy was only `0.3650`. The highest-test reduced candidate was `base_relations/masked_tcn` at
`0.3833`, close to but still below the E3-B6 full augmented masked TCN `0.3867` and E3-B6 full
augmented Conv1D `0.3883`.

The reduced variants also did not solve overfitting. The best reduced masked-TCN candidates still
had train-validation gaps around `0.276` to `0.320`.

## Engineering Interpretation

- Relationship/presence features are the cleanest reduced signal because `base_relations/masked_tcn`
  produced the best reduced test result.
- Velocity alone is weaker than relationships.
- Velocity plus relationships did not beat relationships alone.
- Velocity plus acceleration improved validation but not test, suggesting acceleration may amplify
  noise or overfit validation.
- The full E3-B6 `[96,728]` tensor remains the best measured landmark-feature result, but it is not
  strong enough or stable enough for production promotion.

## Error/Behavior Notes

Persistent confusion groups remained:

- `TAKECARE -> EVERYYEAR`;
- `CROSS3 -> WHALE`;
- `ROCKINGCHAIR1 -> TRACTOR`;
- `EDIT1 -> INDEPENDENT`;
- `RIVER1 -> DEMAND1`;
- `AUTISM1 -> CURLYHAIR` or `AUTISM1 -> INDEPENDENT`.

Class gains and regressions were mixed. Reduced features helped some classes such as `BOTH`,
`BEE1`, `BASEBALLCAP`, `BOXING`, `BUY`, `SPECIAL1`, and `SHARK1`, but regressed classes such as
`NIGHT1`, `DEAF1`, `TWINS1`, `PRESS`, `EVERYYEAR`, and `CURLYHAIR`.

## Recommended Next Step

Stop small landmark-feature engineering for now. The landmark-only branch has reached a practical
plateau on this 50-class split:

- E3-B5 proved landmarks work but TCN masking alone was not stable.
- E3-B6 showed derived features can improve test accuracy.
- E3-B7 showed smaller derived subsets do not cleanly retain or exceed the full E3-B6 gain.

The next highest-value experiment should return to the broader architecture plan: combine the best
landmark stream with RGB hand-shape evidence or use a stronger encoder/fusion strategy. The most
practical next package is **E3-C landmark + RGB fusion on the frozen 50-class split**, using:

- best landmark candidate as the structured stream reference;
- RGB/hand or upper-body crops as the visual stream;
- validation-only selection;
- strict comparison against E3-B6 full augmented references.

## Architecture Decisions

- Do not promote any E3-B7 reduced feature subset.
- Do not port derived subsets to Android.
- Keep E3-B6 full augmented result as the current best landmark-feature reference.
- Move next to RGB/fusion or stronger encoder evidence rather than continuing small handcrafted
  landmark feature tweaks.

## Assumptions

- The repeated frozen-split results are enough to stop this specific feature-engineering branch.
- Remaining confusions likely require visual hand-shape evidence, stronger temporal/fusion modeling,
  more data, or all three.

## Open Questions

- Can RGB hand-shape evidence resolve the persistent landmark confusions?
- Should the next visual stream use hand crops, upper-body crops, or both?
- Is the current 50-class split sufficient for fusion testing, or should fusion be tested after a
  targeted crop-quality gate?

## Risks

- RGB/fusion may overfit unless crop quality and signer split are controlled.
- Fusion may improve validation without improving test, repeating E3-B6 behavior.
- Continuing to reuse the same frozen split can overfit experiment choices.

## Next Required Action

Architect the next fusion/visual-stream experiment before implementation. Do not change Android,
production recognizer assets, or the runtime feature contract.
