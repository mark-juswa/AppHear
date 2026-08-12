# E4-F Cleaned Diagnostic Plan

**Purpose:** Prepare the next bounded diagnostic after E4-E by removing manually identified relabel
rows and rerunning the same landmark-temporal comparison.

**Scope:** Experiment package only. This does not authorize Android integration, model export,
production-recognizer replacement, or dataset mutation.

**Current status:** Package prepared; smoke and structural checks passed; full training pending.

**Last updated:** 2026-07-30.

## Verified Project References

- Runner:
  `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_f_cleaned_diagnostic.py`
- Prepared run:
  `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_f_cleaned_diagnostic_pilot_01`
- Source E4-D run:
  `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_d_stage_e_same_provenance_pilot_01`
- Source E4-E review:
  `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_e_error_review_01`
- Cleaned tensor:
  `dataset\landmark_features.npz`
- Cleanup summary:
  `logs\cleanup_summary.json`

## Prepared Dataset

E4-F reuses the existing E4-D extracted MediaPipe `[96,258]` tensor and excludes rows whose E4-E
`recommended_action` is `relabel`.

Counts:

- Source rows: 430
- Removed rows: 16
- Kept rows: 414
- Split counts: train 165, validation 55, test 194

Test class counts after cleanup:

- `BYE`: 29
- `GOOD`: 30
- `HELLO`: 30
- `NO`: 30
- `SORRY`: 30
- `THANKYOU`: 17
- `YES`: 28

The test split is now intentionally imbalanced because the removed rows were concentrated in
`THANKYOU`, `BYE`, and `YES`. This is acceptable for a cleaned diagnostic, but it must not be
reported as a pristine untouched benchmark.

## Validation Completed

Python compile passed.

Smoke test passed:

- Rows: 8
- Shape: `[8,96,258]`
- `conv1d_baseline`: forward shape `[8,7]`, one train batch, weights saved
- `tcn_masked_pool`: forward shape `[8,7]`, one train batch, weights saved

Structural check passed:

```json
{
  "passed": true,
  "errors": []
}
```

## Training Command

This is the long step and should be run manually by the user:

```powershell
cd "F:\ASL DATASET\5. Apphear3"

.\.venv\Scripts\python.exe -m pipeline.rgb.e4_f_cleaned_diagnostic run `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_f_cleaned_diagnostic_pilot_01"
```

Resume if interrupted:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_f_cleaned_diagnostic run `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_f_cleaned_diagnostic_pilot_01" `
  --resume
```

After training:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_f_cleaned_diagnostic check `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_f_cleaned_diagnostic_pilot_01" `
  --require-full-dataset `
  --require-metrics
```

## Architecture Decisions

- Reuse E4-D extracted features instead of rerunning MediaPipe extraction.
- Keep the same branches as E4-D: `conv1d_baseline` and `tcn_masked_pool`.
- Keep the same seeds as E4-D: `101`, `202`, `303`.
- Keep the same learning rate and epoch count: `0.0005`, 20 epochs per command.
- The only intended variable is removal of E4-E relabel rows.

## Go / No-Go Criteria

Go if:

- Masked TCN remains at least as strong as Conv1D after validation selection.
- Overall held-out test accuracy improves meaningfully without prediction collapse.
- `THANKYOU` improves after removing relabel rows.
- `BYE` and `NO` are no longer severe weak classes.

No-go if:

- `BYE` and `NO` remain weak after cleanup.
- Validation remains near-perfect while held-out test is much lower.
- Predictions still collapse into `YES`, `SORRY`, or another small set.
- Improvements appear only because the test set was made easier by removing relabel rows.

## Assumptions

- E4-E relabel markings are accurate enough for a first-pass cleaned diagnostic.
- Removing relabel rows is preferable to silently training/evaluating on suspect labels.
- This diagnostic answers whether data cleanup alone changes the conclusion.

## Risks

- Cleaning after inspecting prediction failures can bias the measured result.
- The cleaned test set is imbalanced, especially `THANKYOU` with only 17 rows.
- If `BYE` and `NO` remain weak, more small landmark-TCN training will likely not solve the issue.

## Next Required Action

User runs the E4-F training command and final check. After completion, analyze
`metrics\metrics.json` with special attention to `BYE`, `NO`, `THANKYOU`, prediction distribution,
and the Conv1D-vs-masked-TCN comparison.
