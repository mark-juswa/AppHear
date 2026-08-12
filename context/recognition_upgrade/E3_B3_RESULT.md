# E3-B3 Landmark + RGB Fusion Smoke Result

**Purpose:** Record the completed signer-disjoint landmark/RGB fusion smoke and its architecture
decision impact.

**Scope:** Bounded experiment result only. This does not authorize Android integration, production
model replacement, full E3 training, detector training, or feature-schema changes.

**Current status:** COMPLETE / PIPELINE PASS / FUSION NO-GO / LANDMARK BRANCH STRONGEST.

**Last updated:** 2026-07-28.

## Verified Project References

- Plan: `context/recognition_upgrade/E3_B3_FUSION_SMOKE_PLAN.md`.
- Runner: `pipeline/rgb/e3_b3_fusion_smoke.py`.
- Run directory: `artifacts/recognition_upgrade/e3_fusion/pilot_01_landmark_rgb_fusion`.
- Metrics: `artifacts/recognition_upgrade/e3_fusion/pilot_01_landmark_rgb_fusion/metrics/metrics.json`.
- Check: `artifacts/recognition_upgrade/e3_fusion/pilot_01_landmark_rgb_fusion/check_report.json`.
- Landmark tensor: `artifacts/recognition_upgrade/e3_fusion/pilot_01_landmark_rgb_fusion/dataset/landmark_features.npz`.
- RGB tensor: `artifacts/recognition_upgrade/e3_rgb_b1/pilot_01_mobilenetv3_upper_body/dataset/rgb_frame_features.npz`.

## Run Summary

- Experiment: `e3_b3_landmark_rgb_fusion_smoke_v1`.
- Classes: 7.
- Split counts: 112 train, 28 validation, 28 test.
- Split policy: signer-disjoint, inherited from E3-B0/E3-B1.
- Landmark input shape: `[168, 96, 258]`.
- RGB input shape: `[168, 16, 576]`.
- Branches trained: `rgb_only`, `landmark_only`, `fusion`.
- Total epochs after resume: 16.
- Check result: passed with no reported errors after refresh.
- Random top-1 baseline: 0.1429.

## Metrics

Latest checkpoints:

| Branch | Train | Validation | Test |
|---|---:|---:|---:|
| RGB only | 1.0000 | 0.1786 | 0.1786 |
| Landmark only | 0.7143 | 0.5714 | 0.6786 |
| Fusion | 0.9911 | 0.2857 | 0.2500 |

Best validation checkpoints:

| Branch | Train | Validation | Test |
|---|---:|---:|---:|
| RGB only | 0.9732 | 0.2500 | 0.2500 |
| Landmark only | 0.5804 | 0.6071 | 0.6071 |
| Fusion | 0.9821 | 0.2857 | 0.2500 |

## Interpretation

The result is decisive for this bounded smoke:

- `landmark_only` is the strongest branch by a wide margin.
- `rgb_only` again memorizes training but performs poorly on held-out signers.
- naive `fusion` is worse than `landmark_only`, so the current RGB stream is not adding useful
  complementary signal.

This means the next practical recognition work should focus on the landmark branch: temporal
modeling, feature quality, masks/missingness, confidence calibration, and evaluation. RGB should not
be scaled or integrated until either hand crops become reliably better or a later fusion design shows
clear held-out benefit.

## Gate Decision

Pre-registered gate: fusion is promising only if it beats both `landmark_only` and `rgb_only` on
validation and avoids test regression.

Gate result: **NO-GO**.

Fusion validation/test are far below landmark-only:

- validation: fusion best 0.2857 vs landmark-only best 0.6071;
- test: fusion best 0.2500 vs landmark-only best 0.6071.

## Decision

Do not continue RGB-only scaling, naive RGB fusion, or Android hybrid integration from these
experiments.

Proceed with landmark-first improvements. Keep RGB as a future branch only if the project later
solves reliable hand crops or obtains a much stronger visual dataset/model.

## Recommended Next Action

Prepare a landmark-focused next experiment on the same 7-class subset before scaling:

- compare the current small landmark Conv1D head against the existing TCN-style landmark encoder;
- add frame masks/missingness handling if cheap;
- evaluate whether landmarks alone can reach a reliable held-out result on the 7-class split;
- only then decide whether to scale the landmark experiment to more classes.

## Open Questions

- Would the production-style TCN outperform the small landmark head used in this smoke?
- How much of the 7-class landmark result is due to easy classes versus robust landmark signal?
- Should the next landmark experiment use the full `[96,258]` plus frame mask?
- Is there any value in late-score fusion after calibrating landmark and RGB confidence, or is RGB
  too weak to keep?

## Risks

- The 7-class split is small, so exact percentages are noisy.
- Naive feature concatenation may underperform a better fusion design, but the gap is large enough
  that fusion is not the next best investment.
- Landmark-only success here does not yet prove the full vocabulary will perform well.

## Next Required Action

Stop RGB/fusion work for now. Prepare a bounded landmark-temporal experiment using the same
signer-disjoint 7-class split.

