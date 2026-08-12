# E4-H BYE/NO/YES Variant Intervention Package

**Purpose:** Prepare a controlled manual-review package for the `BYE`, `NO`, and `YES` confusion group before any further full benchmark training.

**Scope:** Experiment package only. This does not authorize Android integration, model export, production-recognizer replacement, feature-schema promotion, source-video mutation, or dataset deletion.

**Current status:** Prepared and structurally checked.

**Last updated:** 2026-07-30.

## Verified Project References

- Package script: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_h_variant_intervention.py`
- Source diagnostic: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_g_bye_yes_no_separability_01`
- E4-H package: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_h_bye_no_yes_variant_review_01`
- Review queue: `variant_review_queue.csv`
- Browser review page: `review.html`
- User guide: `USER_REVIEW_GUIDE.md`
- Contact sheets: `contact_sheets\`
- Copied panels: `panels\`
- Structural check: `check_report.json`

## Completion Evidence

The package was generated with:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_h_variant_intervention prepare --overwrite
```

Structural check passed:

```json
{
  "rows": 94,
  "panels": 94,
  "contact_sheets": 9,
  "passed": true,
  "errors": []
}
```

## Package Contents

- 94 review rows copied from E4-G target-group evidence.
- 94 per-sample visual panels under `panels\`.
- 9 contact sheets under `contact_sheets\`:
  - `BYE_test.jpg`, `BYE_train.jpg`, `BYE_val.jpg`
  - `NO_test.jpg`, `NO_train.jpg`, `NO_val.jpg`
  - `YES_test.jpg`, `YES_train.jpg`, `YES_val.jpg`
- `review.html` for browser-based visual comparison.
- `variant_review_queue.csv` for recording review decisions.
- `USER_REVIEW_GUIDE.md` with allowed values and review instructions.

## Why This Step Exists

E4-F and E4-G showed that another full 7-sign landmark training loop is unlikely to answer the real blocker:

- `BYE` is almost always predicted as `YES` on the held-out signer.
- `NO` is often predicted as `YES` on the held-out signer.
- Hand-hit rates are not low enough to explain the failure.
- Simple probes still fail on `BYE`, so this is not only a TCN classifier problem.

E4-H is therefore a data/variant decision gate. It asks whether the examples should be kept as one class, split by variant, recollected, relabeled, quarantined, or deferred from the initial reliable vocabulary.

## Review Columns

The user should fill these fields in `variant_review_queue.csv`:

- `review_status`: `done`, `skip`, or `needs_second_review`
- `label_correct`: `yes`, `no`, or `unsure`
- `variant_group`: short consistent name such as `standard`, `wave`, `shake`, `fist`, `point`, or `unknown`
- `variant_matches_train_reference`: `yes`, `no`, or `unsure`
- `hands_visible`: `yes`, `partial`, or `no`
- `motion_visible_enough`: `yes`, `no`, or `unsure`
- `recommended_action`: `keep`, `split_variant`, `relabel`, `quarantine`, `recollect_same_variant`, `defer_sign`, or `needs_second_review`
- `review_notes`: short explanation when useful

## User Commands After Review

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_h_variant_intervention summarize `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_h_bye_no_yes_variant_review_01" `
  --require-reviewed
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_h_variant_intervention check `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_h_bye_no_yes_variant_review_01" `
  --require-reviewed
```

## Decision Gate

Go to a focused three-class rerun only if review shows enough variant consistency:

- Most `BYE`, `NO`, and `YES` rows are label-correct.
- Test variants mostly match train/validation references.
- Hands and motion are visible enough.
- No class requires broad relabeling or quarantine.

No-go/fallback:

- If `BYE` test examples are a different variant from train/validation, split the variant or recollect same-variant examples.
- If labels are inconsistent, relabel/quarantine first.
- If `BYE` remains unstable after controlled data, defer it from the first reliable vocabulary or require RGB hand-shape evidence before inclusion.

## Assumptions

- E4-G panels and predictions are trusted diagnostic inputs.
- The reviewer can judge whether clips visibly match the intended sign and variant well enough for this engineering decision.
- This is not a substitute for fluent-ASL review if the team needs production-level label authority.

## Risks

- Variant decisions may still be wrong without an ASL-fluent reviewer.
- Reviewing only panels may miss motion details visible in the original videos.
- Iterating too much on this same held-out split can bias future benchmark claims.

## Next Required Action

The user reviews `variant_review_queue.csv` using `review.html` and the contact sheets, then runs `summarize --require-reviewed` and `check --require-reviewed`. Do not run another full 7-sign benchmark before E4-H is summarized.

## Conservative Autofill Result - 2026-07-30

The queue was auto-filled using `pipeline.rgb.e4_h_variant_intervention autofill --overwrite`.
This is an engineering triage, not ASL-fluent semantic review.

Autofill summary:

```json
{
  "rows": 94,
  "mode": "conservative_auto_triage",
  "review_status_counts": {
    "needs_second_review": 24,
    "done": 70
  },
  "recommended_action_counts": {
    "needs_second_review": 24,
    "keep": 70
  }
}
```

Required-review summary passed structurally:

```json
{
  "reviewed": 94,
  "remaining": 0,
  "passed": true
}
```

Action counts by true gloss:

- `BYE:needs_second_review`: 12
- `NO:needs_second_review`: 11
- `YES:needs_second_review`: 1
- `BYE:keep`: 24
- `NO:keep`: 18
- `YES:keep`: 28

Interpretation:

- The auto-triage can safely keep reference rows for engineering comparison.
- It cannot resolve the core semantic/variant question for the collapse rows.
- The 24 `needs_second_review` rows are exactly the high-value rows that block another benchmark.

Updated next action:

Review only the 24 `needs_second_review` rows, not all 94 rows. If the team wants to avoid manual review entirely, the conservative engineering decision is to exclude or defer `BYE` and treat `NO` as unstable until controlled data is available.
