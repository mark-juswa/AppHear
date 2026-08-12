# E6 v3.0 Five-Sign Warm-Start Transfer Result

Last updated: 2026-08-09

## Purpose

Record the completed one-variable transfer experiment and determine whether broad 236-class
encoder pretraining repairs the from-scratch five-sign generalization failure.

## Scope And Status

Status: **complete; accuracy gate failed, transfer mechanism supported**.

No Android assets, production models, feature schemas, raw data, or extraction outputs changed.

Run directory:

`artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_transfer_01`

## Verified Project Evidence

All three seeds completed 40 epochs. The primary latest-checkpoint results are:

| Metric | From scratch | Warm start | Change |
|---|---:|---:|---:|
| Mean fresh top-1 | 0.7344 | 0.9044 | +0.1700 |
| Minimum-seed fresh top-1 | 0.7233 | 0.8467 | +0.1234 |
| Mean historical top-1 | not primary | 0.9683 | strong |

Mean fresh recall:

- `GOOD`: `0.9833`
- `HELLO`: `1.0000`
- `SORRY`: `1.0000`
- `HAVE`: `0.9500`
- `KNOW`: `0.5889`

Fresh results by seed:

- seed 101: top-1 `0.9100`, `KNOW 0.6833`, `HAVE 0.8833`;
- seed 202: top-1 `0.9567`, `KNOW 0.8000`, `HAVE 1.0000`;
- seed 303: top-1 `0.8467`, `KNOW 0.2833`, `HAVE 0.9667`.

The preregistered gate failed because mean `KNOW` recall is below `0.70` and seed 303 `KNOW`
recall is below `0.50`. Seed 202 must not be selected using fresh-test performance because that
would be test-set tuning.

Validation does not rank fresh behavior correctly:

- validation top-1 is tightly grouped at `0.7263-0.7542`;
- validation `KNOW` recall is only `0.0323-0.0968` for all seeds;
- current deployed restricted-five evaluation also classifies 30/31 validation `KNOW` clips as
  `HELLO`;
- validation `HAVE` contains only four clips, all from ASL Citizen;
- 30/31 validation `KNOW` clips come from one AppHear signer.

## Interpretation

### Verified Conclusion

Broad encoder pretraining is materially better than training the same TCN from scratch. It repairs
`HAVE`, raises mean fresh accuracy by 17 percentage points, and produces one seed that matches the
deployed control's fresh `KNOW` recall.

### Engineering Inference

The remaining blocker is no longer whether transfer helps. It is that the current validation set
cannot reliably select or reject a signer-robust checkpoint. The extreme validation `KNOW` behavior
is shared by both the new models and deployed control, while the fresh and historical splits behave
substantially better.

### Hypothesis Requiring Experimentation

A signer-complete, source-aware validation assignment assembled from existing accepted clips may
provide a checkpoint-selection signal that agrees better with held-out behavior. This must be tested
without changing model architecture or class weights.

## Decision

The warm-start model is **not deployable** and must not be exported. The transfer strategy is
**retained** as the current model-training foundation.

Do not:

- choose seed 202 because it wins on the inspected fresh set;
- tune class weights or thresholds;
- add RGB, richer features, specialists, or a negative gate;
- expand vocabulary using the current validation assignment;
- modify Android.

## Single Next Action

Create one automated E6 validation-repair package using only existing accepted rows and extracted
v3.0 tensors:

1. preserve the current validation set as a named `validation_variant_stress` diagnostic;
2. hold out complete signer groups from training so each selected class has meaningful validation
   support;
3. keep source and signer IDs explicit and prohibit overlap;
4. leave the current fresh and historical tests unchanged;
5. publish counts and leakage checks before any retraining;
6. rerun only the warm-start transfer after the repaired split passes its data gate.

This is automated data reassignment, not new collection or extraction. If a valid signer-complete
split cannot be formed from current data, modeling stops and the exact missing signer/class cells are
reported.

## Success And Failure Gates

The repaired validation package must have:

- zero signer or raw-video hash overlap between train and validation;
- at least one complete held-out recorder signer covering all five classes;
- at least 20 validation clips per class from recorder/AppHear-domain data where available;
- the existing ASL Citizen signer-disjoint rows retained as cross-source evidence;
- the old problematic validation signer preserved separately as stress evidence, not silently
  discarded.

Failure to meet these gates means the present data cannot support trustworthy model selection.

## Risks

- Current recorder signer IDs may represent sessions rather than independently verified people.
- Holding out a complete signer will reduce the already small training set.
- The fresh test contains one signer and has been inspected, so a later production claim still
  requires untouched signers.
- Better validation correlation is not guaranteed.

## Source-Of-Truth Files

- `artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_transfer_01/metrics/metrics.json`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_transfer_01/source_checkpoint_lineage.json`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_transfer_01/smoke/smoke_summary.json`
- `pipeline/rgb/e6_v30_five_sign_transfer.py`

## Related Context

- `E6_V30_FIVE_SIGN_TRANSFER_PACKAGE.md`
- `E6_V30_CONFUSION_ROOT_CAUSE_RESULT.md`
- `E6_V30_FIVE_SIGN_BASELINE_PACKAGE.md`
- `../../../EVALUATION_AND_ACCEPTANCE_GATES.md`
- `../../../ROLLBACK_AND_COMPATIBILITY_PLAN.md`

## Architecture Decisions

- Retain broad encoder pretraining for the next controlled run.
- Repair evaluation before changing representation or recognition architecture.
- Keep the production 236-class Android recognizer protected.

## Assumptions And Open Questions

- Can a complete held-out recorder signer be formed without unacceptably shrinking training?
- Do recorder signer IDs correspond to distinct people rather than recording sessions?
- Will repaired validation ranking agree with historical and fresh diagnostic behavior?

## Next Required Action

The automated signer-complete validation reassignment passed and is documented in
`E6_V30_VALIDATION_REPAIR_RESULT.md`. The repaired transfer package is smoke-validated. The user
runs that package next; no other experiment is authorized first.
