# E4-E Focused Error Review Package

**Purpose:** Freeze the next AppHear recognition-upgrade step after E4-D by preparing a manual
error-review package for the weak held-out signs before collecting more data or training again.

**Scope:** Experiment documentation and review artifacts only. This does not authorize Android
integration, model export, production-recognizer replacement, or dataset mutation.

**Current status:** Package prepared and structurally checked.

**Last updated:** 2026-07-30.

## Verified Project References

- Source E4-D run:
  `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_d_stage_e_same_provenance_pilot_01`
- Source checkpoint:
  `models\tcn_masked_pool\seed_303\best.weights.h5`
- Source config:
  `pilot_config.json`
- Source dataset:
  `dataset\landmark_features.npz`
- E4-E script:
  `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_e_error_review.py`
- E4-E package:
  `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_e_error_review_01`

## Why This Step Exists

E4-D proved that the E4-B collapse was largely caused by a feature-provenance mismatch, because
same-provenance Stage-E features reached materially above-random held-out accuracy. It still failed
production readiness because the best masked TCN had weak held-out class accuracy on:

- `BYE`: `0/30`, mostly predicted as `YES`
- `NO`: `12/30`, mostly confused with `YES`
- `THANKYOU`: `10/30`, mostly confused with `SORRY`

The next highest-value action is not another training run. The next action is to determine whether
those failures are caused by label/variant problems, insufficient signer coverage, visual ambiguity,
landmark extraction quality, or actual model limitations.

## Prepared Artifacts

The package contains:

- `summary.json`: automatic prediction and review-package summary.
- `README_REVIEW.md`: manual review instructions.
- `review_queue.csv`: 156 rows to review.
- `predictions\all_predictions.csv`: recreated predictions for all 430 E4-D samples.
- `review_panels\*.jpg`: 156 five-frame visual panels with true label, prediction, confidence,
  source split, and source video path.
- `check_report.json`: structural validation result.
- GUI reviewer command: `python -m pipeline.rgb.e4_e_error_review review --run-dir <E4-E run dir>`.

Package check passed:

```json
{
  "rows": 156,
  "passed": true,
  "errors": []
}
```

## Review Queue Composition

- 68 target held-out errors.
- 22 target held-out correct examples.
- 24 held-out confusion-class references from `YES`, `SORRY`, and `GOOD`.
- 24 train target references.
- 18 validation target references.

Target error confusions:

- `BYE -> YES`: 28
- `BYE -> NO`: 1
- `BYE -> SORRY`: 1
- `NO -> YES`: 17
- `NO -> HELLO`: 1
- `THANKYOU -> SORRY`: 15
- `THANKYOU -> GOOD`: 3
- `THANKYOU -> BYE`: 2

## Manual Review Contract

For each row in `review_queue.csv`, open `panel_path` and fill:

- `review_status`: `done`, `skip`, or `needs_second_review`
- `label_correct`: `yes`, `no`, or `unsure`
- `sign_variant_matches_target`: `yes`, `no`, or `unsure`
- `hands_visible`: `yes`, `partial`, or `no`
- `landmark_problem_visible`: `yes`, `no`, or `unsure`
- `too_blurry_or_occluded`: `yes`, `no`, or `unsure`
- `ambiguous_even_to_reviewer`: `yes`, `no`, or `unsure`
- `recommended_action`: `keep`, `relabel`, `quarantine`, `recollect`, `merge_variant`, or
  `needs_second_review`
- `review_notes`: short evidence when useful

After review:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_e_error_review summarize --run-dir "F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_e_error_review_01" --require-reviewed
```

Then verify:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_e_error_review check --run-dir "F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_e_error_review_01" --require-reviewed
```

## Architecture Decisions

- E4-E is a data/label diagnostic, not a model experiment.
- The selected checkpoint is E4-D `tcn_masked_pool` seed `303`, because it was the best validation
  TCN checkpoint and its held-out confusion pattern was already analyzed.
- E4-E does not modify E4-D tensors, local videos, Android assets, production model files, or the
  active `[96,258]` recognizer.
- Another E4 training run should wait until manual review decides which rows/classes to keep,
  relabel, quarantine, recollect, or merge.

## Assumptions

- The five sampled frames per panel are sufficient for first-pass review. If a row is ambiguous, the
  original `video_path` must be opened.
- The reviewer can judge whether the intended sign label and variant are plausible.
- The E4-D predictions are valid for diagnosis because the E4-D extraction and training checks
  passed and the source checkpoint exists.

## Open Questions

- Are `BYE` and `YES` visually/variant-confounded in the local supplementary recordings?
- Is `THANKYOU` being recorded with a variant closer to `SORRY`, or are landmarks missing critical
  contact/direction cues?
- Is `NO` insufficiently separable with the current landmark-only feature schema, or is the held-out
  source recording style different from train/validation?
- Which rows should be quarantined before the next cleaned benchmark?

## Risks

- Manual review may be inconsistent without a fluent ASL reviewer.
- Panels may hide a motion cue that only appears when watching the video.
- If rows are removed after seeing test predictions, the next benchmark must use a newly frozen
  split or clearly mark itself as cleaned-diagnostic only.

## Next Required Action

Complete `review_queue.csv` with the E4-E GUI reviewer, then run `summarize --require-reviewed` and
`check --require-reviewed`. The resulting `manual_review_summary.json` determines whether the next
step is cleaned same-provenance retraining, targeted recollection, variant relabeling/merging, or
class removal.


