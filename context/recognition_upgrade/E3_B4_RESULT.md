# E3-B4 Landmark Temporal Result

**Purpose:** Record the completed E3-B4 landmark-only temporal comparison and its decision impact.

**Scope:** Experiment result only. This does not authorize Android integration, production model
replacement, dataset changes, or modification of the active AppHear `[96,258]` runtime recognizer.

**Current status:** Completed. Pilot passed directionally; larger multi-seed validation required.

**Last updated:** 2026-07-28.

## Verified Project References

- Runner: `pipeline/rgb/e3_b4_landmark_temporal.py`
- Run directory:
  `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_01_tcn_vs_masked`
- Result files:
  - `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_01_tcn_vs_masked/metrics/metrics.json`
  - `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_01_tcn_vs_masked/metrics/metrics.md`
  - `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_01_tcn_vs_masked/check_report.json`
  - `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_01_tcn_vs_masked/logs/*_history.csv`
- Source tensor:
  `artifacts/recognition_upgrade/e3_fusion/pilot_01_landmark_rgb_fusion/dataset/landmark_features.npz`
- Source comparison result: `E3_B3_RESULT.md`

## Input And Split

- Experiment: `e3_b4_landmark_temporal_v1`
- Input shape: `[96,258]`
- Classes: 7
- Clips: 168
- Split: 112 train, 28 validation, 28 test
- Split type: signer-disjoint, inherited from E3-B3
- Classes: `DOG1`, `BITE1`, `DEMAND1`, `WHATFOR1`, `DEAF1`, `PARTY1`,
  `ROCKINGCHAIR1`
- Frame mask: available as `frame_mask` shape `[168,96]`

## Compared Branches

- `conv1d_baseline`: simple landmark temporal Conv1D head comparable to the E3-B3 landmark branch.
- `tcn_pool`: AppHear causal TCN encoder with ordinary global average pooling.
- `tcn_masked_pool`: AppHear causal TCN encoder with frame-mask-aware pooling that excludes padded
  frames.

## Result Summary

| Branch | Checkpoint | Train | Val | Test | Mean Val Confidence |
|---|---|---:|---:|---:|---:|
| `conv1d_baseline` | best/latest | 0.6161 | 0.5714 | 0.6429 | 0.4954 |
| `tcn_pool` | best | 0.5446 | 0.5714 | 0.6071 | 0.5124 |
| `tcn_pool` | latest | 0.5804 | 0.3929 | 0.5000 | 0.5580 |
| `tcn_masked_pool` | best | 0.7768 | **0.6429** | **0.6429** | 0.5238 |
| `tcn_masked_pool` | latest | 0.8571 | 0.5714 | 0.7143 | 0.6579 |

Reference from E3-B3 landmark-only:

- Best validation/test: `0.6071/0.6071`
- Latest validation/test: `0.5714/0.6786`

## Gate Decision

E3-B4 is a **directional pilot pass**.

The selected checkpoint is `tcn_masked_pool` best-validation, not latest-test:

- Best validation accuracy `0.6429` is above the E3-B3 landmark-only best validation reference
  `0.6071`.
- Best test accuracy `0.6429` is above the E3-B3 landmark-only best test reference `0.6071`.
- `tcn_masked_pool` beat ordinary `tcn_pool` on validation.

However, validation and test each contain only 28 clips. One clip changes accuracy by about `3.57%`,
so this is not enough evidence for production or Android integration.

## Interpretation

- The current landmark representation remains the strongest experimental signal.
- RGB-only and naive landmark+RGB fusion remain no-go from E3-B0 through E3-B3.
- Ordinary TCN pooling did not improve over the prior landmark baseline.
- The useful E3-B4 signal is **mask-aware temporal pooling**, not TCN alone.
- The latest `tcn_masked_pool` checkpoint reached test `0.7143`, but it is diagnostic only because
  model selection must be based on validation.

## Architecture Decision

Continue landmark-first. Do not return to RGB-only or naive fusion yet. Do not integrate E3-B4 into
Android and do not replace the production recognizer from this pilot.

The next approved experiment direction is a larger, repeated landmark-temporal validation:

- same `[96,258]` feature path;
- signer-disjoint split;
- more classes/signers if the dataset supports it;
- multiple seeds;
- at least `conv1d_baseline`, `tcn_pool`, and `tcn_masked_pool`;
- confusion and prediction-distribution reporting;
- validation-only model selection.

## Assumptions

- E3-B3 tensor/manifest alignment is valid.
- E3-B4 uses the same 7-class split and therefore should be compared directly to E3-B3.
- No production feature-schema or Android runtime behavior changed.

## Open Questions

- Does `tcn_masked_pool` remain better across seeds?
- Does the result hold with a larger class set?
- Is the gain caused primarily by padded-frame masking, TCN receptive field, or small-split variance?
- How many ASL Citizen classes can support the next larger signer-disjoint landmark-temporal pilot
  without leakage?

## Risks

- Small-sample optimism: one held-out clip changes the reported score noticeably.
- Repeated test-set iteration can bias future decisions.
- Mask-aware pooling may help isolated buffered clips but still require separate streaming/boundary
  validation before Android use.
- Current E3-B4 metrics do not measure false positives during non-signing, low-FPS behavior, or
  end-to-end sentence behavior.

## Next Required Action

Prepare the larger multi-seed landmark-temporal validation package. Keep RGB/fusion scaling,
detector training, Android integration, and production recognizer replacement blocked until that
larger validation is stable.

## Document Control

- **Scope:** Experiment result and next-gate governance only.
- **Verified project references:** Files listed above.
- **Source-of-truth files:** This result document, `E3_B4_LANDMARK_TEMPORAL_PLAN.md`,
  `EXPERIMENT_MATRIX.md`, and `../progress-tracker.md`.
- **Related context files:** `E3_B3_RESULT.md`, `MODEL_RESEARCH_PLAN.md`,
  `TEMPORAL_AND_BOUNDARY_PLAN.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`,
  `ROLLBACK_AND_COMPATIBILITY_PLAN.md`.
- **Architecture decisions:** Landmark-first continuation; mask-aware TCN is promising but not
  production-approved.
- **Assumptions:** Listed above.
- **Open questions:** Listed above.
- **Risks:** Listed above and tracked in `RISK_REGISTER.md`.
- **Next required action:** Prepare larger multi-seed landmark-temporal validation.
