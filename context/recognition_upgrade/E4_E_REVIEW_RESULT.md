# E4-E Focused Error Review Result

**Purpose:** Record the completed manual review of E4-D weak-class predictions and define the next
data/model action.

**Scope:** Experiment result only. This does not authorize Android integration, model export,
production-recognizer replacement, or dataset mutation.

**Current status:** Manual review complete; result analyzed.

**Last updated:** 2026-07-30.

## Verified Project References

- Review package:
  `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_e_error_review_01`
- Review queue:
  `review_queue.csv`
- Summary:
  `manual_review_summary.json`
- Source E4-D run:
  `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_d_stage_e_same_provenance_pilot_01`
- Source checkpoint:
  `models\tcn_masked_pool\seed_303\best.weights.h5`

## Completion Evidence

The user completed the GUI review and ran the required checks:

```json
{
  "rows": 156,
  "review_status_counts": {
    "done": 156
  },
  "recommended_action_counts": {
    "keep": 140,
    "relabel": 16
  },
  "passed": true
}
```

Final required check passed:

```json
{
  "rows": 156,
  "passed": true,
  "errors": []
}
```

## Review Findings

- All 156 reviewed rows had visible hands.
- No reviewed row was marked blurry or occluded.
- 140 rows were marked `keep`.
- 16 rows were marked `relabel`.
- No rows were marked `recollect`, `quarantine`, `merge_variant`, or `needs_second_review`.

Target-class action counts:

- `BYE`: 45 keep, 1 relabel.
- `NO`: 43 keep, 0 relabel.
- `THANKYOU`: 30 keep, 13 relabel.

The remaining two relabel rows were `YES` confusion-class references.

## Detailed Interpretation

The review changes the interpretation of E4-D:

- `THANKYOU` has a substantial label/variant-data problem in the held-out source. Of its 20
  held-out test errors, 13 were marked relabel. If those rows are removed from the diagnostic test
  set, the kept `THANKYOU` rows would be 10 correct out of 17 kept rows, approximately `0.588`.
  That is still not production-grade, but it is much better than the raw `0.333`.
- `BYE` remains a real model/data generalization failure. Only 1 of the 30 held-out `BYE` errors was
  marked relabel; 29 errors were kept as valid data, including 28 `BYE -> YES` confusions.
- `NO` remains a real model/data generalization failure. All 18 held-out `NO` errors were kept as
  valid data, mostly `NO -> YES`.
- Visibility, blur, and obvious MediaPipe failure were not the primary cause for the reviewed weak
  classes.

## Architecture Decisions

- Do not rerun the same E4-D training unchanged.
- Do not promote E4-D to Android or production.
- Use E4-E to build a cleaned diagnostic manifest before any further training.
- Treat `THANKYOU` as partially label-confounded.
- Treat `BYE` and `NO` as genuine separability/generalization failures that need either more
  signer-balanced data, better features, stronger temporal modeling, or removal from a small
  production vocabulary until they pass.

## Assumptions

- The manual review is correct enough for first-pass diagnostic cleanup.
- Relabel decisions indicate rows should not remain under their current class in the next cleaned
  benchmark.
- Because relabel decisions were made after viewing E4-D predictions, any cleaned benchmark must be
  reported as a cleaned diagnostic, not a pristine untouched test result.

## Risks

- A single reviewer may misclassify subtle ASL variants.
- Removing/relabeling test rows after seeing predictions can bias future accuracy if not documented.
- If `BYE` and `NO` are similar in the available recordings, more epochs or small architecture
  tweaks may overfit rather than solve the real generalization issue.

## Next Required Action

Prepare an E4-F cleaned-diagnostic manifest/run package that excludes or quarantines the 16 relabel
rows, keeps source-provenance constraints explicit, and reruns the same Conv1D vs masked-TCN
comparison as a bounded diagnostic. The go/no-go question is whether cleanup alone improves weak
classes enough to justify targeted recollection or whether `BYE`/`NO` need different features or
should be deferred from the first reliable vocabulary.
