# E6 v3.0 Repaired-Validation Transfer Result

Last updated: 2026-08-09

## Purpose

Record the final five-sign v3.0 control after broad encoder transfer and signer-complete validation
repair, then decide whether the project can leave repeated baseline tuning and enter planned E6-2.

## Scope And Status

Status: **complete; v3.0 control established, positive gate no-go, E6-2 feature control unblocked**.

No production or Android assets changed.

Run:

`artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_transfer_repaired_val_01`

## Verified Project Evidence

All three seeds completed. Primary latest-checkpoint means:

| View | Mean top-1 | Seed standard deviation |
|---|---:|---:|
| repaired validation | 0.9940 | 0.0049 |
| preserved AppHear variant stress | 0.6973 | 0.0126 |
| unchanged fresh AppHear test | 0.8889 | 0.0063 |
| unchanged historical ASL test | 0.9630 | 0.0198 |

Fresh mean recall:

- `GOOD 0.9833`
- `HELLO 1.0000`
- `SORRY 0.9667`
- `HAVE 0.9333`
- `KNOW 0.5611`

Fresh minimum-seed `KNOW` recall is `0.50`; the mean remains below the required `0.70`. Therefore,
the preregistered positive gate fails.

The repaired validation split is stable and nearly perfect, including `KNOW 0.9677-1.0`. It does
not represent the difficult AppHear variant: on the preserved stress signer, `KNOW` recall is
`0.0-0.0333` and overall accuracy is about `0.70`. Historical `KNOW` remains strong at
`0.8462-0.9231`.

## Conclusions

### Verified Project Evidence

- Broad encoder transfer is materially superior to from-scratch training.
- Validation repair removes seed instability and supplies a valid complete-class model-selection
  split.
- The v3.0 transfer model generalizes well to local and historical ASL evidence.
- A reproducible AppHear signer/variant gap remains, concentrated in `KNOW` and stress `SORRY`.

### Engineering Inference

- More checkpoint selection, split reshuffling, threshold tuning, or class weighting is unlikely to
  resolve the AppHear variant gap.
- The current `[96,258]` representation and learned encoder form a valid control, but do not provide
  enough invariant evidence for the difficult `KNOW` executions.

### Hypothesis Requiring Experimentation

- Explicit hand-local geometry, hand shape/bone/angle descriptors, real-time motion derivatives,
  presence masks, and hand-to-head/body relations may make the difficult executions more invariant
  across signers. This is the planned E6-2 hypothesis, not a confirmed solution.

## Decision

Close the repeated five-sign v3.0 baseline loop. Do not run another v3.0 TCN seed, validation split,
class-weight adjustment, or threshold experiment.

The established E6-2 control is:

- architecture: broad-warm-start 4-block/64-channel causal TCN;
- schema: immutable v3.0 `[96,258]`;
- train/validation: repaired split package;
- required reports: repaired validation, preserved variant stress, fresh AppHear, historical ASL;
- primary latest-checkpoint fresh top-1: `0.8889`;
- primary failure target: fresh `KNOW 0.5611`, stress `KNOW approximately 0.0222`.

Proceed next to **E6-2 richer landmark-feature control planning and independent validation**. This
does not authorize E6-3 rejection, E6-5 RGB/specialists, vocabulary expansion, TFLite export, or
Android integration.

## E6-2 Gate

The experiment-only feature candidate must use the same raw clips, assignments, seeds, encoder
capacity budget, and evaluation views. It must materially improve fresh and stress `KNOW` without
regressing the stable classes or creating train/serve ambiguity. If it does not, retain v3.0 and
move the verified confusion group toward E6-5 specialist/RGB evaluation only after E6-3/E6-4 rules
are satisfied.

## Risks

- The difficult AppHear signer may use a label variant that no geometric feature can reconcile.
- Derived motion/angle features may amplify landmark jitter or missing-hand errors.
- The one inspected fresh signer cannot support a production confidence interval.
- Strong local validation may still overstate real AppHear-domain performance.

## Source-Of-Truth Files

- `artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_transfer_repaired_val_01/metrics/metrics.json`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_validation_repair_01/validation_repair_report.json`
- `pipeline/rgb/e6_v30_five_sign_transfer.py`
- `pipeline/rgb/e6_v30_validation_repair.py`

## Related Context

- `E6_V30_VALIDATION_REPAIR_RESULT.md`
- `E6_V30_FIVE_SIGN_TRANSFER_RESULT.md`
- `../../../E6_PRODUCTION_RECOGNITION_ARCHITECTURE_PLAN.md`
- `../../../FEATURE_SCHEMA_PLAN.md`
- `../../../EXPERIMENT_MATRIX.md`
- `../../../ROLLBACK_AND_COMPATIBILITY_PLAN.md`

## Architecture Decisions

- Freeze this run as the E6-2 v3.0 control.
- Preserve broad pretraining in the comparison.
- Introduce any richer schema under a new experiment-only identifier; never mutate schema v3.0.
- Keep all later stages blocked until their predecessor gates pass.

## Assumptions And Open Questions

- Which smallest feature additions isolate hand shape and hand-to-face position without unnecessary
  dimensional growth?
- Can the new features be derived from existing raw MediaPipe outputs, or is re-extraction required
  to recover confidence/presence data?
- Can an Android-equivalent causal implementation be specified before training?

## Next Required Action

Architect E6-2 against the frozen control before implementation. Define the exact feature schema,
causal math, data availability, ablations, train/serve parity test, cost budget, and go/no-go gates.
