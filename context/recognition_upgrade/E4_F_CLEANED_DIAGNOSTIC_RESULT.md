# E4-F Cleaned Diagnostic Result

**Purpose:** Record the completed cleaned diagnostic after E4-E relabel-row removal.

**Scope:** Experiment result only. This does not authorize Android integration, model export,
production-recognizer replacement, or dataset mutation.

**Current status:** Completed; diagnostic improved but remains production no-go.

**Last updated:** 2026-07-30.

## Verified Project References

- Run directory:
  `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_f_cleaned_diagnostic_pilot_01`
- Runner:
  `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_f_cleaned_diagnostic.py`
- Metrics:
  `metrics\metrics.json`
- Check report:
  `check_report.json`
- Cleanup summary:
  `logs\cleanup_summary.json`

## Completion Evidence

Final check passed:

```json
{
  "passed": true,
  "errors": []
}
```

Dataset:

- Source rows: 430
- Removed relabel rows: 16
- Kept rows: 414
- Split counts: train 165, validation 55, test 194

## Main Result

Branch mean best validation/test:

- `conv1d_baseline`: validation `0.9818`, test `0.6065`
- `tcn_masked_pool`: validation `0.9758`, test `0.6581`

Best checkpoint by validation then test:

- Branch: `tcn_masked_pool`
- Seed: `303`
- Best validation: `0.9818`
- Best test: `0.6856`

E4-D comparator:

- E4-D best selected masked TCN seed `303`: validation `0.9818`, test `0.6333`
- E4-F selected masked TCN seed `303`: validation `0.9818`, test `0.6856`
- Net selected-test change: `+0.0523`

## Best Selected Test Per-Class Accuracy

For `tcn_masked_pool` seed `303` best checkpoint:

- `BYE`: `0/29`, `0.0000`
- `GOOD`: `29/30`, `0.9667`
- `HELLO`: `28/30`, `0.9333`
- `NO`: `12/30`, `0.4000`
- `SORRY`: `29/30`, `0.9667`
- `THANKYOU`: `10/17`, `0.5882`
- `YES`: `25/28`, `0.8929`

Selected checkpoint predicted-class counts:

- `GOOD`: 33
- `HELLO`: 30
- `NO`: 15
- `SORRY`: 36
- `THANKYOU`: 10
- `YES`: 70
- `BYE`: 0

Key confusions:

- `BYE -> YES`: 28 of 29
- `NO -> YES`: 17 of 30
- `THANKYOU -> SORRY`: 4 of 17
- `THANKYOU -> GOOD`: 3 of 17

## Interpretation

E4-F answered the cleanup question:

- Removing relabel rows improved the selected masked-TCN test score from `0.6333` to `0.6856`.
- The improvement is real enough to confirm that label cleanup matters.
- The improvement is not enough to make the system reliable.
- `THANKYOU` improved from E4-D `10/30` (`0.3333`) to E4-F `10/17` (`0.5882`), confirming the
  E4-E finding that its held-out failures were partly label-confounded.
- `BYE` did not improve. It remains `0/29` and is almost always predicted as `YES`.
- `NO` did not improve. It remains `12/30` and is often predicted as `YES`.
- The model still overfits the train/validation source: train reaches `1.0`, validation is near
  `0.98`, but held-out test is far lower and class failures are severe.

## Decision

E4-F is a diagnostic pass but a production no-go.

Do not:

- export this model,
- integrate it into Android,
- present this as production accuracy,
- rerun the same small cleaned benchmark hoping for a fundamentally different result,
- keep adding epochs as the next action.

The result supports this conclusion:

- Data cleanup is necessary.
- Data cleanup alone is insufficient.
- `BYE` and `NO` require targeted intervention before they can be part of a reliable vocabulary.

## Recommended Next Action

Prepare an E4-G targeted separability package for `BYE`, `YES`, and `NO`.

The goal is to determine whether the `BYE/YES/NO` failures are caused by:

- inconsistent sign variants,
- signer/source style mismatch,
- insufficient signer coverage,
- inadequate landmark features for these signs,
- the current model not using the relevant temporal/finger-shape cue,
- or a class-selection problem where `BYE`/`NO` should be deferred from the first reliable release.

The next experiment should not train another full 7-class benchmark first. It should focus on the
specific confusion group that blocks reliability.

## Assumptions

- The E4-E relabel review is correct enough to justify a cleaned diagnostic.
- Because relabel rows were removed after inspecting prediction failures, E4-F is not a pristine
  held-out benchmark.
- The strong `GOOD`, `HELLO`, `SORRY`, and `YES` classes show the pipeline can learn some classes
  under the current data, but this does not generalize to the weak classes.

## Risks

- The E4-F improvement may partly reflect a smaller/easier test set.
- `BYE` and `NO` may require raw RGB hand-shape evidence or more signer variation, not just a
  cleaned landmark TCN.
- If future work keeps optimizing on this same tiny held-out set, results will become biased.

## Next Required Action

Prepare E4-G as a bounded analysis/experiment package for the `BYE`, `YES`, and `NO` confusion group.
It should include targeted visual review, feature-distance/prototype analysis, and a small binary or
three-class diagnostic before collecting more data or changing Android.
