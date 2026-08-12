# E4-Q Confusion Resolver Result

**Purpose:** Record the completed E4-Q result and the architectural consequence for the mixed/dynamic recognizer strategy.

**Scope:** Experiment result and planning decision only. This does not authorize Android integration, TFLite export, production recognizer replacement, or dataset mutation.

**Current status:** COMPLETE / GATE FAILED. Use this result as evidence that a landmark-only specialist resolver is not sufficient for the `SORRY/BECOME/HELP` group.

**Last updated:** 2026-07-31.

## Verified Project References

- Package: `context/recognition_upgrade/E4_Q_CONFUSION_RESOLVER_PACKAGE.md`
- Runner: `pipeline/rgb/e4_q_confusion_resolver.py`
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_q_confusion_resolver_sorry_become_help_01`
- Metrics summary: `artifacts/recognition_upgrade/e4_generalization/e4_q_confusion_resolver_sorry_become_help_01/metrics/metrics.md`
- Full metrics: `artifacts/recognition_upgrade/e4_generalization/e4_q_confusion_resolver_sorry_become_help_01/metrics/metrics.json`
- Final check: `artifacts/recognition_upgrade/e4_generalization/e4_q_confusion_resolver_sorry_become_help_01/check_report.json`

## Experiment Question

Can a focused landmark-only resolver separate the E4-P confusion group better than the broad 20-sign model?

Target group:

- `GOOD`
- `SORRY`
- `HELP`
- `BECOME`

Variants:

- `base_conv1d`: original `[96,258]` schema 3.0 feature representation
- `derived_conv1d`: `[96,728]` derived motion/relation feature representation
- `derived_balanced_conv1d`: `[96,728]` plus class-weighted training

## Prepared Dataset

- Total rows: `219`
- Train/validation/test: `108 / 26 / 85`
- Base input: `[96,258]`
- Derived input: `[96,728]`
- Seeds: `101`, `202`, `303`
- Epochs completed per variant/seed: `50`

Class counts:

| Split | GOOD | SORRY | HELP | BECOME |
|---|---:|---:|---:|---:|
| Train | 15 | 15 | 52 | 26 |
| Validation | 5 | 5 | 10 | 6 |
| Test | 30 | 30 | 13 | 12 |

Important source limitation: held-out `HELP/BECOME` test rows are ASL Citizen only. Held-out `GOOD/SORRY` rows are from the E4-J local core. This is sufficient for diagnosing the `SORRY` collapse but not enough for production approval of `HELP/BECOME`.

## Gate Result

Gate: failed.

Required:

- Mean latest test accuracy >= `0.85`
- Minimum latest `SORRY` accuracy >= `0.85`
- Minimum core latest test accuracy >= `0.85`
- Minimum candidate latest test accuracy >= `0.70`
- Maximum predicted-class share <= `0.45`

Observed summary:

| Variant | Mean Latest Test | Min Latest SORRY | Min Core Latest | Min Candidate Latest | Max Predicted-Class Share | Gate |
|---|---:|---:|---:|---:|---:|---|
| `base_conv1d` | `0.7137` | `0.2333` | `0.2333` | `0.6923` | `0.4471` | Fail |
| `derived_conv1d` | `0.6941` | `0.1000` | `0.1000` | `0.7692` | `0.5412` | Fail |
| `derived_balanced_conv1d` | `0.6471` | `0.1000` | `0.1000` | `0.7692` | `0.4471` | Fail |

Best mean latest-test variant: `base_conv1d`.

Decision emitted by metrics: `landmark_resolver_failed_try_rgb_or_data_review`.

## Per-Class Interpretation

Latest-policy mean per-class accuracy:

| Variant | GOOD | SORRY | HELP | BECOME |
|---|---:|---:|---:|---:|
| `base_conv1d` | `0.9667` | `0.4111` | `0.7436` | `0.8056` |
| `derived_conv1d` | `0.9333` | `0.3111` | `0.8462` | `0.8889` |
| `derived_balanced_conv1d` | `0.9889` | `0.1556` | `0.7949` | `0.8611` |

The derived `[96,728]` features helped `HELP/BECOME` somewhat, but hurt `SORRY`. Class weighting made `SORRY` worse.

Aggregated latest-policy `SORRY` confusion across three seeds:

| Variant | True SORRY -> GOOD | True SORRY -> SORRY | True SORRY -> HELP | True SORRY -> BECOME |
|---|---:|---:|---:|---:|
| `base_conv1d` | `9` | `37` | `0` | `44` |
| `derived_conv1d` | `26` | `28` | `0` | `36` |
| `derived_balanced_conv1d` | `13` | `14` | `0` | `63` |

The main unresolved failure is still `SORRY -> BECOME`.

## Model-Selection Warning

Several variants reached perfect or near-perfect train/validation accuracy while failing on test. Example patterns:

- `base_conv1d` seeds 101 and 202: train `1.0`, validation `1.0`, but test `0.7882` and `0.6471`.
- `derived_conv1d` seed 101: train `1.0`, validation `1.0`, but test `0.6235` and `SORRY=0.1000`.
- `derived_balanced_conv1d` seed 303: train `1.0`, validation `1.0`, but test `0.6353` and `SORRY=0.1000`.

This means the validation subset for this resolver is too easy or too small to select a production candidate. A high validation score must not be treated as a release signal.

## Architecture Consequence

E4-Q does not invalidate the dynamic/mixed strategy. It invalidates only the first attempted specialist design:

`global landmark model -> landmark-only confusion resolver`

The approved next architecture direction is:

`global landmark recognizer -> confusion registry/router -> specialist resolver with richer evidence or reject`

For the `SORRY/BECOME/HELP` group, richer evidence likely means hand/body RGB crops and/or targeted data/variant repair, not more epochs on the current landmark-only representation.

## Decisions

- Do not promote E4-Q.
- Do not add `[96,728]` derived features to Android from this result.
- Do not retry this exact resolver with more epochs.
- Keep `[96,258]` as the primary landmark-control representation for stable signs.
- Use E4-Q as evidence for a confusion-aware routed architecture.
- Require a hybrid or data-repair resolver for the `SORRY/BECOME/HELP` group before these signs can be confidently used in a larger vocabulary.

## Assumptions

- `GOOD`, `HELLO`, `HAVE`, and `KNOW` remain provisionally stable only under the E4-N/E4-P evidence already recorded.
- `SORRY` is not removed from the product goal, but it is no longer treated as a simple globally separable landmark-only class.
- `HELP/BECOME` require local held-out validation before production claims.

## Open Questions

- Does a hand/body RGB-crop resolver separate `SORRY` from `BECOME` better than landmarks alone?
- Is `SORRY` label/variant consistency sufficient across current sources?
- Are chest-contact and hand-shape cues recoverable from existing raw videos at Android-realistic crop sizes?
- What is the lowest-cost resolver that improves this group without hurting device latency?

## Risks

- The group may need more data rather than more model architecture.
- A specialist resolver can look good offline but create false accepts if router confidence is weak.
- Hybrid crops may fail if MediaPipe/ROI quality is not fixed or if hand/body context is cropped incorrectly.
- Test-set iteration can overfit architectural decisions unless the next resolver uses fresh validation and a held-out promotion test.

## Next Required Action

Architect the dynamic/mixed recognition roadmap as the source-of-truth plan, then prepare the next experiment only after the roadmap is approved. The next likely experiment is a bounded confusion-group visual evidence test for `SORRY/BECOME/HELP`, not another broad vocabulary expansion.
