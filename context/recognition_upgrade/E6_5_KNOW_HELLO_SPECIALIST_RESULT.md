# E6-5 KNOW/HELLO Specialist Result

**Purpose:** Record the completed E6-5 specialist result and its consequence for the approved E6
roadmap.

**Scope:** Offline experiment result and architecture decision only. This does not authorize
routing, RGB, fusion, TFLite export, Android integration, production-model replacement, raw-data
mutation, or feature-schema promotion.

**Current status:** COMPLETE / STRUCTURAL PASS / RECOGNITION GATE FAILED / NO SPECIALIST SELECTED.

**Last updated:** 2026-08-09.

## Verified Project References

- Plan: `E6_5_KNOW_HELLO_SPECIALIST_PLAN.md`
- Package: `E6_5_KNOW_HELLO_SPECIALIST_PACKAGE.md`
- Runner: `pipeline/rgb/e6_5_know_hello_specialist.py`
- Run: `artifacts/recognition_upgrade/e6_specialists/e6_5_know_hello_specialist_01`
- Metrics: `artifacts/recognition_upgrade/e6_specialists/e6_5_know_hello_specialist_01/metrics/metrics.json`
- Training summary: `artifacts/recognition_upgrade/e6_specialists/e6_5_know_hello_specialist_01/logs/training_summary.json`
- Structural check: `artifacts/recognition_upgrade/e6_specialists/e6_5_know_hello_specialist_01/check_report.json`

## Completion Versus Recognition

`check_report.json` reports `passed: true` because all six training runs completed and every
required checkpoint, metric, and package artifact exists. That is a structural result.

The authoritative recognition decision inside `metrics/metrics.json` is:

```text
selected_branch: null
passed: false
decision: e6_5_no_go_data_or_variant_repair
```

No branch passed the preregistered recognition gate.

## Frozen Primary Controls

| View | Five-way pair accuracy | Pair-restricted accuracy | Mean route coverage |
|---|---:|---:|---:|
| Validation | `0.9897` | `0.9949` | `0.9949` |
| Variant stress | `0.6741` | `0.6815` | `0.9630` |
| Fresh AppHear | `0.7806` | `0.7806` | `0.9972` |
| Historical ASL Citizen | `0.9506` | `0.9506` | `1.0000` |

Pair restriction changed stress `KNOW` recall only from `0.0222` to `0.0444` and did not change
fresh or historical `KNOW`. The failure is therefore not primarily caused by competition from the
other three output classes.

## Latest-Checkpoint Results

The preregistered policy uses `latest.keras`. `best` and `final` are diagnostic only.

| Metric | Frozen primary | v3 TCN specialist | Geometry TCN specialist | Required |
|---|---:|---:|---:|---:|
| Mean fresh pair accuracy | `0.7806` | `0.7972` | `0.8444` | `>=0.90` |
| Minimum-seed fresh pair accuracy | n/a | `0.7583` | `0.7417` | `>=0.85` |
| Mean fresh `HELLO` recall | `1.0000` | `1.0000` | `1.0000` | `>=0.85` |
| Mean fresh `KNOW` recall | `0.5611` | `0.5944` | `0.6889` | `>=0.85` |
| Minimum-seed fresh `KNOW` recall | n/a | `0.5167` | `0.4833` | `>=0.75` |
| Mean stress pair accuracy | `0.6741` | `0.6852` | `0.6889` | `>=0.85` |
| Mean stress `HELLO` recall | `1.0000` | `1.0000` | `1.0000` | `>=0.95` |
| Mean stress `KNOW` recall | `0.0222` | `0.0556` | `0.0667` | `>=0.70` |
| Mean historical pair accuracy | `0.9506` | `0.9630` | `0.9630` | `>=0.90` |
| Mean historical `KNOW` recall | `0.8974` | `0.9231` | `0.9231` | `>=0.80` |
| Fresh gain over primary | n/a | `+0.0167` | `+0.0639` | `>=+0.10` |
| Stress gain over primary | n/a | `+0.0111` | `+0.0148` | `>=+0.15` |
| Fresh seed standard deviation | n/a | `0.0307` | `0.0765` | `<=0.05` |

The v3 specialist passed only stress `HELLO`, historical pair/`KNOW`, and seed-stability checks.
The geometry specialist passed only stress `HELLO` and historical pair/`KNOW` checks. Geometry
also failed the seed-stability gate.

Across all three latest checkpoints, the v3 specialist recognized only `5/90` stress `KNOW`
samples and geometry recognized only `6/90`. This is the decisive failure.

## Checkpoint Robustness

Selecting `best` or `final` would not change the decision:

- v3 best/final stress `KNOW` recall: `0.1111`; fresh `KNOW`: `0.5889`;
- geometry best/final stress `KNOW` recall: `0.0778`; fresh `KNOW`: `0.6333`.

Validation accuracy remained approximately `0.98-1.00` while difficult AppHear stress `KNOW`
collapsed. The result is not explained by one bad final epoch.

## Verified Findings

- Binary output restriction does not solve the registered confusion.
- A seed-matched v3 binary TCN specialist produces only marginal fresh/stress gains.
- Geometry produces a larger fresh gain, but remains below gate, is seed-unstable, and does not
  transfer to the stress signer.
- Both specialists preserve historical ASL Citizen behavior and `HELLO` recall.
- The failure is concentrated in AppHear-domain `KNOW`, especially the variant-stress signer.

## Engineering Inference

The evidence is more consistent with signer/domain/variant coverage or extraction-quality mismatch
than with a five-way-head problem. This is not yet proof of which one is causal; a video/lineage
audit would be required to separate those causes.

## Decision

- Reject both E6-5 specialists.
- Do not select one seed or checkpoint as a shortcut.
- Do not repeat binary TCN training, pair restriction, geometry subsets, class weighting, more
  epochs, or threshold tuning for this pair.
- Defer `KNOW` from an E6 routed candidate unless a separately approved data/variant repair is
  completed.
- Keep `HELLO` in the supported primary evidence set.
- Preserve schema v3.0 and the current production recognizer.
- E6-6 routed simulation and E6-7 Android shadow integration remain blocked.

## Assumptions, Risks, And Open Questions

- **Verified limitation:** fresh and stress views were already used for architecture decisions;
  even a later improvement on them cannot establish production readiness.
- **Unknown:** whether the difficult performances are a compatible ASL variant, a label problem,
  an extraction failure, or underrepresented signer style.
- **Risk:** repeatedly adapting to these inspected signers would create test-set overfitting.
- **Fallback:** defer `KNOW`; retain the frozen baseline and no production migration.

## Next Required Action

Record the consolidated E6 component decision. Do not start E6-6, E6-7, RGB, another specialist,
or another `KNOW` model automatically.
