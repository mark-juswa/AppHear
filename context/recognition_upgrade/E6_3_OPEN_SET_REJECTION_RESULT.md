# E6-3 Frozen-Embedding Rejection Result

**Purpose:** Record the completed extraction and frozen-score comparison, explain the structural
pass versus recognition no-go, and close unsupported threshold/rejector iteration.

**Scope:** Offline five-sign diagnostic only. No classifier training, schema change, RGB,
specialist, export, Android change, or production migration occurred.

**Current status:** COMPLETE / STRUCTURAL PASS / REJECTION GATE NO-GO.

**Last updated:** 2026-08-09.

## Verified Full Extraction

- Run: `artifacts/recognition_upgrade/e6_rejection/e6_3_frozen_embedding_01`.
- Attempted/completed negative windows: `1,107/1,107`.
- Unique videos and Stage-E caches: `804`.
- Development negatives: `547`.
- Provisional fresh negatives: `560` from one signer.
- Missing files, invalid lengths/shapes, non-finite tensors, mask mismatches, or nonzero padding: `0`.
- Zero-hand-feature windows retained: `152`.
- Extraction errors: `0`.
- Extraction time: approximately `6,502.1 s` (`1 h 48 min`).

The earlier package estimate of `707` distinct videos was incorrect. The generated manifest proves
that `804` is the correct count.

## Frozen Methods

All methods used the unchanged latest v3.0 checkpoints for seeds `101`, `202`, and `303`:

- MSP: maximum masked-mean softmax probability, historical control;
- energy: fixed-temperature pre-softmax log-sum-exp score;
- Mahalanobis: predicted-class OAS-shrinkage distance over the masked-mean 64-dimensional
  `tcn3_add` embedding.

No model or rejector was trained. Threshold selection used repaired positive validation plus
historical development negatives only.

## Separation Metrics

| Seed | Method | Development AUROC | Fresh-negative AUROC | Valid operating point |
|---:|---|---:|---:|---|
| 101 | MSP | `0.899` | `0.825` | no |
| 101 | Energy | `0.937` | `0.829` | no |
| 101 | Mahalanobis | `0.843` | `0.887` | no |
| 202 | MSP | `0.814` | `0.762` | no |
| 202 | Energy | `0.876` | `0.759` | no |
| 202 | Mahalanobis | `0.836` | `0.730` | no |
| 303 | MSP | `0.869` | `0.761` | no |
| 303 | Energy | `0.852` | `0.824` | no |
| 303 | Mahalanobis | `0.921` | `0.829` | no |

AUROC shows partial ranking information, but none of the nine seed/method combinations produced a
threshold satisfying all preregistered development constraints.

## Operating-Point Failure

At positive coverage `>=0.80`, the best accepted precision was:

| Seed | MSP | Energy | Mahalanobis |
|---:|---:|---:|---:|
| 101 | `0.571` | `0.841` | `0.496` |
| 202 | `0.443` | `0.556` | `0.479` |
| 303 | `0.508` | `0.549` | `0.675` |

All are below the required `0.95`.

When negative false-accept floors were enforced, the maximum positive coverage was:

| Seed | MSP | Energy | Mahalanobis |
|---:|---:|---:|---:|
| 101 | `0.404` | `0.114` | `0.036` |
| 202 | `0.006` | `0.078` | `0.096` |
| 303 | `0.102` | `0.006` | `0.133` |

Minimum supported-class accepted recall was `0.03` at best in these safety-constrained points and
usually `0.0`. Rejection therefore becomes safe only by suppressing most real signs and effectively
removing at least one supported class.

## Negative Failure Pattern At 80% Coverage

- MSP frequently accepted hands-visible face-adjacent and idle-hand negatives (`0.322-0.667` FAR)
  and also accepted some N0 windows.
- Energy rejected N0 and most OOV better, but face-adjacent FAR remained `0.315-0.519`; idle-hand
  FAR remained seed-sensitive (`0.021-0.559`).
- Mahalanobis rejected face-adjacent and most idle-hand examples, but accepted N0 at `0.173-0.687`
  and OOV at `0.185-0.235`.

The methods fail differently. That is useful architectural evidence, but combining them after
seeing these results would be a new routed experiment and is not authorized as an E6-3 retune.

## Conclusions

### Verified project evidence

- Softmax confidence again cannot meet precision and coverage together, confirming E4-T/E5-H.
- Fixed-temperature energy provides useful ranking in some seeds but no safe operating point.
- Frozen class-conditioned Mahalanobis does not solve AppHear open-set rejection.
- No method passed in even one seed; the E6-3 stop condition is met.
- Package `check --require-smoke --require-metrics` passed structurally, while `metrics.json`
  correctly records `passed: false` and `e6_3_no_go_or_more_negative_evidence_required`.

### Engineering inference

- The frozen closed-set embedding does not encode one universal known-versus-unknown boundary.
- N0, OOV, idle-hand, and face-adjacent inputs occupy different score regions; a single scalar
  threshold is structurally too weak for this evidence.
- Rejection cannot fix the underlying supported-class `KNOW -> HELLO` confusion when useful
  positive coverage already collapses before the safety floor is reached.

### Hypotheses still requiring experimentation

- A future staged system could combine a dedicated temporal no-sign gate with class-conditioned
  recognition evidence because E4-AG and E6-3 fail on complementary negative types.
- That combination is not proven and must not be assembled by post-hoc threshold tuning.
- Supported-class confusion specialists may still help a verified group, but E6-4 must first prove
  that the group is stable across seeds and sources.

## Decision

**E6-3 is a no-go. Keep the frozen v3.0 classifier and do not implement MSP, energy, or
Mahalanobis rejection in Android.**

Do not:

- relax the preregistered precision, coverage, subtype FAR, or class-recall gates;
- select the best seed/method using fresh results;
- combine E4-AG and E6-3 scores without a separately approved routed experiment;
- run one-vs-rest, OpenMax, or another rejector automatically;
- export any E6-3 parameters.

## Required-Metric Stop Note

The architecture plan requested downstream accepted fresh/stress metrics only after a valid
development operating point exists. Because all nine combinations failed before that point, those
promotion metrics are undefined rather than silently computed at a test-selected threshold. The
development frontier and subtype diagnostics are sufficient to invoke the preregistered stop rule.

## Source-Of-Truth Files

- `artifacts/recognition_upgrade/e6_rejection/e6_3_frozen_embedding_01/metrics/metrics.json`
- `artifacts/recognition_upgrade/e6_rejection/e6_3_frozen_embedding_01/logs/negative_extraction_summary.json`
- `artifacts/recognition_upgrade/e6_rejection/e6_3_frozen_embedding_01/dataset/negative_window_manifest.csv`
- `artifacts/recognition_upgrade/e6_rejection/e6_3_frozen_embedding_01/check_report.json`
- `E6_3_OPEN_SET_REJECTION_PLAN.md`
- `E6_3_OPEN_SET_REJECTION_PACKAGE.md`

## Related Context Files

- `E6_2_LANDMARK_GEOMETRY_RESULT.md`
- `E4_AG_HELLO_LIKE_NOSIGN_RESULT.md`
- `E4_T_ROUTER_SIMULATION_RESULT.md`
- `E5_H_CLEAN_7_ROUTED_SIM_RESULT.md`
- `E5_I_OPEN_SET_REJECT_HEAD_RESULT.md`
- `EXPERIMENT_MATRIX.md`
- `E6_PRODUCTION_RECOGNITION_ARCHITECTURE_PLAN.md`
- `RISK_REGISTER.md`
- `ROLLBACK_AND_COMPATIBILITY_PLAN.md`

## Architecture Decisions

- Retain schema v3.0 and the frozen five-sign control.
- Close single-score rejection for the current frozen embedding.
- Preserve method-specific negative failure evidence for future staged architecture review.
- Do not advance any rejection component toward Android.

## Assumptions And Open Questions

- Current fresh negatives remain one-signer provisional evidence.
- It remains unknown whether another untouched signer changes exact AUROC values, but development
  failure is already too large to justify production work.
- E6-4 must determine whether supported-class confusions are reproducible enough to justify one
  specialist experiment.

## Next Required Action

Architect and duplicate-audit E6-4 confusion registry mining. It may analyze frozen predictions
only; it must not train a model, add a rejector, combine gates, add RGB, export, or modify Android.
