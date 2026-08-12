# E6 Product-Core Review Runbook

**Purpose:** Human review workflow for the manual-review rows from the product-core raw-video lineage manifest.

**Scope:** Review only. Do not extract features, train models, change schema, export TFLite, or modify Android from this workflow.

**Current status:** Prepared / user review next.

**Last updated:** 2026-08-03.

## Source Manifest

`context/recognition_upgrade/product_core_data_readiness/lineage_fix_v1/canonical_product_core_manifest.csv`

## Prepared Full Review Run

`artifacts/recognition_upgrade/product_core_data_readiness/e6_product_core_review_01`

Rows:

- Total manual-review rows: `486`
- Local supplementary: `211`
- ASL Citizen: `275`

Sign counts:

- `GOOD`: `96`
- `HELLO`: `98`
- `SORRY`: `92`
- `HAVE`: `36`
- `KNOW`: `38`
- `THINK`: `33`
- `TAKE`: `30`
- `SELL`: `30`
- `WASH2`: `33`

## Commands

Open the review GUI:

```powershell
cd "F:\ASL DATASET. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_product_core_review review `
  --run-dir "artifacts
ecognition_upgrade\product_core_data_readiness\e6_product_core_review_01"
```

Check progress:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_product_core_review check `
  --run-dir "artifacts
ecognition_upgrade\product_core_data_readiness\e6_product_core_review_01"
```

Summarize current decisions and recalculate gaps:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_product_core_review summarize `
  --run-dir "artifacts
ecognition_upgrade\product_core_data_readiness\e6_product_core_review_01"
```

Final completion check after all rows are reviewed:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_product_core_review check `
  --run-dir "artifacts
ecognition_upgrade\product_core_data_readiness\e6_product_core_review_01" `
  --require-reviewed
```

## GUI Controls

The improved review window has three main areas:

- Top header: current sign, source, row ID, reviewed count, and remaining count.
- Left side: larger 8-frame video strip plus sign/source, quality signals, previous experiment usage, and raw video path.
- Right side: color-coded decision buttons, notes box, navigation buttons, and short reminders.

Buttons/keys:

- `1` Accept: usable training candidate
- `2` Accept: low motion but valid
- `3` Reject: wrong label / variant
- `4` Reject: hands/framing/quality bad
- `5` Reject: incomplete performance
- `6` Needs expert ASL review
- `7` Diagnostic only, not training
- Left arrow: previous row
- Right arrow: next row
- `Ctrl+S`: save current note/position
- Save: save without deciding
- Quit: close safely; progress is saved automatically

## Review Meaning

Use `Accept` only when the shown sign appears to match the target label/variant and the hands/sign performance are usable enough for training.

Use `Accept: low motion but valid` for signs such as `SORRY` or face/torso signs where the movement is subtle but the performance is valid.

Use `Reject` for wrong labels, incompatible variants, poor visibility, incomplete signs, or unusable framing.

Use `Needs expert ASL review` when you cannot confidently decide the label or variant.

Use `Diagnostic only` for clips that may help debugging but should not train the baseline model.

## Output Files

The review writes:

- `review_manifest.csv`: review decisions and notes
- `review_manifest.pre_review_backup.csv`: backup before GUI edits
- `reports/review_summary.json`: decision counts and recalculated gaps
- `reports/post_review_gap_summary.csv`: accepted counts and remaining gaps by sign

## Next Required Action

Complete the review, then run `summarize` and `check --require-reviewed`. Only after the reviewed gap summary is evaluated should collection or baseline feature extraction be planned.
