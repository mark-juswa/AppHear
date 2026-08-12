# E4-AB Conservative Gate Policy Result

Last updated: 2026-08-02

## Purpose

E4-AB tests whether E4-AA failed mainly because of threshold policy. It reuses the E4-AA trained temporal gate models and no-sign dataset, then sweeps lower/conservative thresholds selected to protect `SORRY` and positive coverage before minimizing no-sign false commits.

## Verified Project References

- Runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_ab_conservative_gate_policy.py`
- Run directory: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_ab_conservative_gate_policy_01`
- Metrics: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_ab_conservative_gate_policy_01\metrics\conservative_gate_policy_metrics.json`
- Threshold grid: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_ab_conservative_gate_policy_01\metrics\threshold_policy_grid.csv`
- Predictions: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_ab_conservative_gate_policy_01\predictions\test_predictions.csv`

## Result Summary

- Structural check passed.
- Experiment gate failed.
- Mean accepted precision: `0.9632`
- Minimum accepted precision: `0.9573`
- Mean positive coverage: `0.8983`
- Minimum positive coverage: `0.7542`
- Maximum no-sign false commit rate: `0.0441`
- Mean/min GOOD recall: `0.9667` / `0.9667`
- Mean/min SORRY recall: `0.6778` / `0.1000`

## Key Finding

Threshold policy improves E4-AA substantially: mean SORRY recall rises from `0.1222` to `0.6778`, mean positive coverage rises from `0.7345` to `0.8983`, and no-sign false commits remain acceptable at `0.0441`. But the policy is unstable across seeds, especially seed `202`, where test SORRY recall remains `0.1000`.

Probability inspection showed that seed `202` assigns most true SORRY test windows extremely low signing probabilities: median about `0.0025`, with p75 about `0.0062`. Those values overlap with no-sign probabilities. Therefore, no single threshold can reliably preserve SORRY and reject no-sign for all seeds.

## Decision

E4-AB is a no-go for production but a useful diagnostic. Do not keep tuning thresholds as the main path. The next experiment must improve the gate training objective/data or input representation so low-motion positives are explicitly protected.

## Recommended Next Action

Prepare E4-AC: a low-motion-aware signing gate experiment. It should keep E4-AA no-sign data, add class-aware positive weighting or oversampling for low-motion signs (`SORRY`, and later other low-motion signs), evaluate per-class positive recall in threshold selection, and compare binary rejection with an uncertainty/abstain band. No Android/export until E4-AC passes.
