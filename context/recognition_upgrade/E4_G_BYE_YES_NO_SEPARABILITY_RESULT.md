# E4-G BYE/YES/NO Separability Result

**Purpose:** Record the focused diagnostic that explains the remaining `BYE`, `NO`, and `YES` failure group after E4-F cleanup.

**Scope:** Experiment-only analysis. This does not authorize Android integration, model export, production-recognizer replacement, feature-schema promotion, or source dataset mutation.

**Current status:** Completed; diagnostic pass, production no-go.

**Last updated:** 2026-07-30.

## Verified Project References

- Analysis script: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_g_separability.py`
- Source run: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_f_cleaned_diagnostic_pilot_01`
- E4-G run: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_g_bye_yes_no_separability_01`
- Summary: `diagnostics\separability_summary.json`
- Prediction CSV: `predictions\bye_no_yes_predictions.csv`
- Review panels: `review_panels\`
- Panel index: `review_panel_index.csv`

## Completion Evidence

Final package check passed:

```json
{
  "panel_count": 94,
  "passed": true,
  "errors": []
}
```

The run produced 94 visual review panels and a per-sample prediction CSV for the `BYE`, `NO`, and `YES` target group.

## Target Counts

| Split | BYE | NO | YES | Total |
|---|---:|---:|---:|---:|
| Train | 45 | 15 | 15 | 75 |
| Validation | 15 | 5 | 5 | 25 |
| Test | 29 | 30 | 28 | 87 |

## Model Behavior On Target Group

The selected E4-F model was `tcn_masked_pool` seed `303`.

| Split | Full-model accuracy | Target-restricted accuracy |
|---|---:|---:|
| Train | 1.0000 | 1.0000 |
| Validation | 0.9600 | 0.9600 |
| Test | 0.4253 | 0.4483 |

Held-out test confusions:

- `BYE -> YES`: 28 of 29
- `BYE -> NO`: 1 of 29
- `NO -> YES`: 17 of 30
- `NO -> NO`: 12 of 30
- `YES -> YES`: 25 of 28
- `YES -> NO`: 2 of 28
- `YES -> HELLO`: 1 of 28

This confirms the E4-F result: the model is not merely confused by the other four classes. Even when restricted to only `BYE`, `NO`, and `YES`, the held-out signer still collapses heavily toward `YES`.

## Simple Separability Probes

E4-G used compact landmark sequence embeddings built from valid-frame mean, standard deviation, last-minus-first motion, and mean absolute velocity. These probes are diagnostic only; they are not candidate production models.

Nearest-centroid test result:

- Overall target test accuracy: `0.4713`
- `BYE`: `12/29`, `0.4138`
- `NO`: `28/30`, `0.9333`
- `YES`: `1/28`, `0.0357`

Ridge linear probe test result:

- Overall target test accuracy: `0.5977`
- `BYE`: `0/29`, `0.0000`
- `NO`: `25/30`, `0.8333`
- `YES`: `27/28`, `0.9643`

Interpretation:

- The target group is not cleanly separable with simple landmark summary features.
- A linear probe can separate `NO` and `YES` better than the TCN, but still cannot recover held-out `BYE`.
- The failure is therefore not just TCN versus another classifier. `BYE` likely has a deeper cross-signer, sign-variant, or feature-representation problem in the current data.

## Landmark Reliability Check

Mean hand-hit rates for held-out test rows:

- `BYE`: `0.8520`
- `NO`: `0.8645`
- `YES`: `0.8267`

The failure cannot be explained primarily by missing hands. The held-out `BYE`, `NO`, and `YES` clips usually contain detected hands, but the current `[96,258]` landmark stream still does not represent or learn the distinguishing cues reliably across signers.

## Decision

E4-G is a diagnostic pass and a production no-go.

Do not:

- export the E4-F model,
- promote the 7-sign local benchmark as reliable,
- keep retraining the same small 7-class split as the next step,
- assume more epochs or a different seed will fix `BYE`,
- integrate this recognizer into Android.

## Recommended Next Action

Prepare an E4-H targeted data/variant intervention for `BYE`, `NO`, and `YES` before another full benchmark.

The highest-value next experiment is to create a small, controlled, signer-aware variant set for these three signs:

- visually audit train/validation/test variants side by side,
- explicitly separate `BYE/goodbye` variant style if needed,
- collect or select balanced same-provenance examples from multiple signers,
- preserve raw videos and Stage-E features,
- then rerun a focused three-class held-out-signer diagnostic before returning to the 7-sign benchmark.

If `BYE` remains near zero after controlled same-provenance, multi-signer variant balancing, it should be deferred from the first reliable release vocabulary or require visual hand-shape/crop features before inclusion.

## Assumptions

- E4-E manual labels are accepted for the cleaned E4-F source run.
- E4-G reused the E4-F selected model and dataset without modifying source videos or production assets.
- The simple probes are diagnostic evidence, not final architecture evidence.

## Open Questions

- Are the held-out `goodbye` clips signing the same lexical variant as the training `BYE` clips?
- Is `BYE` too visually/kinematically close to the local `YES` samples under the current signer split?
- Would hand-crop RGB recover the missing distinction, or is the main issue label/variant mismatch?
- How many additional same-provenance signers are available for `BYE`, `NO`, and `YES`?

## Risks

- Continued iteration on the same tiny test split can bias conclusions.
- Without an ASL-fluent reviewer, variant mismatches can be mistaken for model failures.
- If `BYE` remains unstable, including it in the first vocabulary may make the whole product feel unreliable.

## Next Required Action

Prepare E4-H as a controlled `BYE`/`NO`/`YES` variant and data-balance intervention. Do not run another full 7-sign training loop until this confusion group has a clearer data decision.
