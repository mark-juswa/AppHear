# E4-AC Low-Motion-Aware Signing Gate Result

Last updated: 2026-08-02

## Purpose

E4-AC tests whether the E4-AA signing/no-sign gate can be improved by changing the training objective, not only the threshold. It retrains the same small temporal gate on the E4-AA dataset while weighting low-motion `SORRY` positives more heavily.

## Verified Project References

- Runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_ac_low_motion_aware_gate.py`
- Best run: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_ac_low_motion_aware_gate_01`
- Comparison runs: `e4_ac_low_motion_aware_gate_02`, `e4_ac_low_motion_aware_gate_03`, `e4_ac_low_motion_aware_gate_04`
- Best metrics: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_ac_low_motion_aware_gate_01\metrics\low_motion_gate_metrics.json`
- Check report: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_ac_low_motion_aware_gate_01\check_report.json`

## Result Summary

Best run: `e4_ac_low_motion_aware_gate_01`

Training weights:

- positive weight: `1.0`
- SORRY weight: `8.0`
- no-sign weight: `1.0`

Metrics:

- Structural check passed.
- Strict experiment gate failed narrowly.
- Mean accepted precision: `0.9548`
- Minimum accepted precision: `0.9492`
- Mean positive coverage: `0.9746`
- Minimum positive coverage: `0.9661`
- Maximum no-sign false commit rate: `0.0441`
- Mean/min GOOD recall: `0.9667` / `0.9667`
- Mean/min SORRY recall: `0.9667` / `0.9667`

## Comparison To Previous Gate Experiments

| Experiment | Mean accepted precision | Min accepted precision | Mean positive coverage | Max no-sign false commit | Mean SORRY recall | Min SORRY recall | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| E4-AA temporal gate | `0.9690` | `0.9630` | `0.7345` | `0.0147` | `0.1222` | `0.0000` | no-go, over-rejects SORRY |
| E4-AB conservative policy | `0.9632` | `0.9573` | `0.8983` | `0.0441` | `0.6778` | `0.1000` | no-go, threshold-only unstable |
| E4-AC low-motion weighted | `0.9548` | `0.9492` | `0.9746` | `0.0441` | `0.9667` | `0.9667` | near-pass, not production-ready |

## Interpretation

E4-AC is the first signing/no-sign gate experiment that preserves `SORRY` while still reducing real no-sign false commits. This strongly supports the architectural direction: a learned temporal gate can work if low-motion positives are explicitly protected.

However, the strict production gate still fails because minimum accepted precision is `0.9492`, just below the `0.95` requirement. Since the miss is small but the dataset is also small, this should be treated as promising evidence, not as an Android/export approval.

The failed variants show the trade-off:

- `e4_ac_low_motion_aware_gate_02` increased no-sign weight and hurt precision in seed `202`.
- `e4_ac_low_motion_aware_gate_03` increased SORRY weight to `12`, improved precision, but reduced mean/min SORRY recall to `0.8778/0.7000`.
- `e4_ac_low_motion_aware_gate_04` used SORRY weight `10`, preserved SORRY but reduced minimum precision to `0.9417`.

## Decision

No Android export or production integration yet. E4-AC is a near-pass and should become the basis for the next gate iteration, but it must be validated with more no-sign/P1 diversity and a cleaner validation policy before runtime promotion.

## Recommended Next Action

Prepare E4-AD focused false-commit review and gate hard-negative expansion. The current residual false commits are mostly P1/N0 windows routed as `HELLO`; the next step should inspect those false commits, add hard-negative training rows, and rerun E4-AC with the same low-motion weighting. Do not broaden vocabulary until the signing gate passes.
