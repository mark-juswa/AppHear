# E3-B5 Landmark Temporal Scale Result

**Purpose:** Record the completed 50-class, three-seed landmark-temporal validation and its
architecture decision.

**Scope:** Offline isolated-sign experiment only. This does not authorize Android integration,
production model replacement, dataset deletion, or runtime feature-contract changes.

**Current status:** COMPLETE. Masked TCN is directional but not stable enough to promote.

**Last updated:** 2026-07-29.

## Verified Project References

- Runner: `pipeline/rgb/e3_b5_landmark_temporal_scale.py`.
- Analysis script: `pipeline/rgb/e3_b5_analyze.py`.
- Run directory: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed`.
- Metrics: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed/metrics/metrics.json`.
- Analysis report: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed/analysis/analysis.md`.
- Source features: `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/features_streaming/{train,val,test}.npz`.
- Source vocab: `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/features/vocab.json`.
- Plan: `E3_B5_LANDMARK_TEMPORAL_SCALE_PLAN.md`.

## Experiment Contract

- Feature schema: `3.0`.
- Input: `[96,258]` landmark features plus `[96]` frame mask for the masked branch.
- Classes: `50`.
- Rows: `1,200`.
- Split: `800` train, `200` validation, `200` test.
- Per class: `16/4/4` train/validation/test.
- Branches: `conv1d_baseline`, `tcn_pool`, `tcn_masked_pool`.
- Seeds: `101`, `202`, `303`.
- Epochs completed: `24` total per branch/seed after resume.
- Validation rule: select best checkpoints by validation only; test is reporting-only.

## Structural Result

- Final check passed: no missing required outputs.
- Metrics were generated for all three branches and all three seeds.
- Error-analysis outputs were generated under `analysis/`.

## Accuracy Summary

| Branch | Mean Best Validation | Mean Best Test | Validation Std | Test Std |
|---|---:|---:|---:|---:|
| `tcn_masked_pool` | `0.4900` | `0.3433` | `0.0319` | `0.0062` |
| `conv1d_baseline` | `0.4750` | `0.3400` | `0.0147` | `0.0216` |
| `tcn_pool` | `0.4733` | `0.3433` | `0.0249` | `0.0262` |

Seed winners by best validation:

- Seed `101`: `conv1d_baseline`.
- Seed `202`: `tcn_pool`.
- Seed `303`: `tcn_masked_pool`.

## Decision

**No promotion.** `tcn_masked_pool` had the best mean validation score but won only one of three
seeds. The registered gate required masked TCN to win or tie at least two of three seeds and avoid
being merely a noisy average winner.

This result does not invalidate landmarks. All branches are far above the 50-class random baseline
of `0.0200`. The result means the current temporal-head change alone is not strong enough to become
the next architecture foundation.

## Error Analysis Findings

- The largest generalization gaps belong to `tcn_masked_pool`; its train accuracy reached
  approximately `0.75` to `0.83` while validation stayed `0.465` to `0.535`.
- Mean test accuracy stayed around `0.34` for every branch despite validation near `0.47` to `0.49`.
- This points to signer/generalization and class-confusion limits, not a simple training-run failure.
- Prediction distribution did not totally collapse, but several seeds over-predicted classes such as
  `EVERYYEAR`, `LOCK1`, `TAKECARE`, `TWINS1`, `COUCH`, and `SWITZERLAND`.
- Weak classes include repeated failures around `DEMAND1`, `RIVER1`, `SINK`, `LOCK1`, `DEAF1`,
  `DINNER1`, `BASEBALLCAP`, `NOON1`, `SPECIAL1`, and `SHAVE1`.
- Stronger classes include `SWITZERLAND`, `WHALE`, `COUCH`, `CURLYHAIR`, `EVERYYEAR`, and `BOXING`.
- High confusion pairs include `TAKECARE -> EVERYYEAR`, `DEAF1 -> TWINS1`,
  `CROSS3 -> WHALE`, `ROCKINGCHAIR1 -> TRACTOR`, and `EDIT1 -> INDEPENDENT`.

## Engineering Interpretation

The current `[96,258]` landmark representation is useful but incomplete. Mask-aware pooling helps
sometimes, especially on validation seed `303`, but it also overfits and does not consistently
improve held-out test signers.

The next experiment should keep the same 50-class split so progress is comparable. The safest next
technical question is whether the landmark stream improves when it receives explicit motion and
relative-geometry features rather than only changing the temporal head.

## Recommended Next Experiment

Prepare **E3-B6 landmark feature augmentation on the frozen E3-B5 split**:

- Keep the same 50 classes, source rows, signer split, and evaluation protocol.
- Add experiment-only derived features from the existing landmark tensor:
  - velocity,
  - acceleration or delta velocity,
  - valid-frame mask,
  - hand-to-hand distances,
  - hand-to-pose/body-relative offsets,
  - optional bone vectors or joint-angle summaries if derivable safely.
- Compare against the exact E3-B5 controls:
  - current `conv1d_baseline`,
  - current `tcn_pool`,
  - current `tcn_masked_pool`.
- Use validation-only selection and report test once.

Go if the augmented landmark branch improves mean best-validation accuracy by at least `0.03`, does
not reduce mean best-test accuracy, and reduces the worst-class/confusion concentration. No-go if it
only improves train accuracy or increases validation/test gap.

## Architecture Decisions

- Do not promote masked TCN as the landmark baseline yet.
- Do not start RGB/fusion scaling from this result alone.
- Do not change Android, production model files, or the runtime feature contract.
- Keep the E3-B5 split as the next controlled benchmark.

## Assumptions

- The validation/test gap is meaningful despite small per-class validation/test counts.
- The weak classes are affected by representation and signer variation, not only random class
  sampling noise.
- Motion/relative features can be computed from the existing tensor without requiring video
  re-extraction.

## Open Questions

- Which weak classes are failures of landmark extraction versus failures of the temporal model?
- Would explicit motion features reduce confusion among similar movement signs?
- Would RGB hand-shape features improve the weak classes that landmarks cannot separate?
- How much of the test gap is caused by signer style versus camera/environment variation?

## Risks

- Feature augmentation may overfit the same 50-class benchmark.
- Derived features may introduce train/runtime skew unless later mirrored exactly in Kotlin.
- Some confusing signs may require RGB hand shape or non-manual cues; landmark-only improvements may
  plateau.

## Next Required Action

Architect and prepare E3-B6 as an isolated experiment on the frozen E3-B5 split. Do not run full
training until the derived feature schema, branch controls, and gate are reviewed.
