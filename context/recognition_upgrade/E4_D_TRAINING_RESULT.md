# E4-D Same-Provenance Training Result

- **Purpose:** Record the completed E4-D Stage-E-only same-provenance diagnostic training result.
- **Scope:** Offline diagnostic analysis only. This does not authorize Android changes, production recognizer replacement, model export, feature-schema promotion, or source-dataset mutation.
- **Current status:** Training completed and checked on 2026-07-30. Diagnostic objective passed: removing the E4-B provenance mismatch stopped held-out prediction collapse. Result is not production-grade.
- **Verified project references:** `pipeline/rgb/e4_b_strict_runner.py`, `E4_D_EXTRACTION_RESULT.md`, and `artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_pilot_01/*`.
- **Source-of-truth files:** `metrics/metrics.json`, `logs/*_history.csv`, `dataset/landmark_features.npz`, `check_report.json`, `EXPERIMENT_MATRIX.md`, and parent `../eval-protocol.md`.
- **Related context files:** `README.md`, `E4_B_STRICT_7_TRAINING_RESULT.md`, `E4_D_SAME_PROVENANCE_PLAN.md`, `E4_D_EXTRACTION_RESULT.md`, `RISK_REGISTER.md`, `OPEN_QUESTIONS.md`, and parent `../progress-tracker.md`.

## Run

Run directory:

`artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_pilot_01`

Final check:

```json
{
  "passed": true,
  "errors": []
}
```

Dataset:

- Classes: 7 (`BYE`, `GOOD`, `HELLO`, `NO`, `SORRY`, `THANKYOU`, `YES`).
- Random baseline: `0.1429`.
- Tensor shape: `[430,96,258]`.
- Train/validation/test: `165/55/210`.
- Branches: `conv1d_baseline`, `tcn_masked_pool`.
- Seeds: `101`, `202`, `303`.
- Epoch count per branch/seed after resume: `40`.

## Metrics Summary

Best-checkpoint means:

| Branch | Mean best train | Mean best validation | Mean best test | Test range |
|---|---:|---:|---:|---:|
| `conv1d_baseline` | 1.0000 | 0.9818 | 0.5651 | 0.4905-0.6095 |
| `tcn_masked_pool` | 1.0000 | 0.9758 | 0.6286 | 0.6095-0.6429 |

Best global checkpoint by validation then test:

- Branch: `tcn_masked_pool`.
- Seed: `303`.
- Best validation: `0.9818`.
- Best test: `0.6333`.
- Latest test for the same seed: `0.5714`.

## Comparison Against E4-B

E4-B corrected pilot 02:

- `conv1d_baseline` mean best validation/test: `0.0924/0.1429`.
- `tcn_masked_pool` mean best validation/test: `0.0909/0.1429`.
- Prediction collapse mostly to `YES` or `NO`.

E4-D same-provenance pilot:

- `conv1d_baseline` mean best validation/test: `0.9818/0.5651`.
- `tcn_masked_pool` mean best validation/test: `0.9758/0.6286`.
- Prediction collapse is no longer the dominant failure mode.

Decision from comparison:

The E4-B failure was primarily a benchmark/data-provenance problem, not evidence that the landmark branch or TCN cannot learn.

## Best TCN Test Behavior

Best TCN (`tcn_masked_pool`, seed `303`) test per-class accuracy:

| Gloss | Correct / Count | Accuracy |
|---|---:|---:|
| `BYE` | 0 / 30 | 0.0000 |
| `GOOD` | 29 / 30 | 0.9667 |
| `HELLO` | 28 / 30 | 0.9333 |
| `NO` | 12 / 30 | 0.4000 |
| `SORRY` | 29 / 30 | 0.9667 |
| `THANKYOU` | 10 / 30 | 0.3333 |
| `YES` | 25 / 30 | 0.8333 |

Major confusions:

- `BYE` -> mostly `YES` (`28/30`).
- `NO` -> often `YES` (`17/30`).
- `THANKYOU` -> often `SORRY` (`15/30`).

## Interpretation

Verified findings:

- Same-provenance training works much better than mixed-provenance E4-B.
- Masked TCN is the stronger branch in this diagnostic: mean best test `0.6286` vs Conv1D `0.5651`.
- Validation is very high, but validation is not signer-independent; it is same-source and should not be treated as production evidence.
- Held-out test is far above random, but class reliability is uneven.

Engineering inference:

- Landmark-only recognition is still technically viable for a small practical vocabulary when preprocessing provenance is consistent.
- Current data is not enough for production because some signs fail completely or partially on the held-out source.
- The next bottleneck is data quality/sign consistency for specific classes, not the basic ability of the TCN to learn.

## Decision

E4-D is a **diagnostic pass** and a **production no-go**.

Approved conclusions:

- Continue landmark-first same-provenance work.
- Use `tcn_masked_pool` as the preferred small landmark-temporal branch for the next diagnostic.
- Do not integrate this model into Android.
- Do not claim production signer-independent accuracy from this result.

Rejected actions:

- Do not rerun E4-B pilot 02.
- Do not scale mixed-provenance training.
- Do not export E4-D to production.
- Do not treat validation `0.98` as real held-out accuracy.

## Recommended Next Action

Prepare an E4-E error-review/data-cleaning package focused on the failed held-out classes:

- `BYE`
- `THANKYOU`
- `NO`

The package should inspect clips, labels, hand-hit rates, and visual/landmark quality for these signs before more training. If labels/variants are correct, collect more same-provenance signer data for these signs. If labels/variants are inconsistent, split or relabel before training again.

## Risks

- **Validation leakage by source:** validation is from the same source folder/signers as train, so it is optimistic.
- **Single test signer/source:** test may overrepresent one signing style.
- **Low hand-hit rows:** weak MediaPipe hands may still distort failed classes.
- **Class ambiguity:** `BYE` may overlap with `YES` or source labels may not match the intended sign variant.
- **Small per-class training volume:** five classes have only 15 train examples.

## Next Required Action

Build a focused E4-E review package for held-out failures before another training run.

## Document Control

- **Architecture decisions:** Landmark-first and masked TCN remain active for diagnostics; production replacement remains blocked.
- **Assumptions:** E4-D improvement is caused by removing feature provenance mismatch and using consistent Stage-E features.
- **Open questions:** Whether failed classes are caused by labels, signer variation, low hand-hit, class ambiguity, or model limitations.
- **Risks:** More training without label/quality review could overfit to noisy classes.
- **Next required action:** Review failed classes and decide whether to clean labels, collect more same-provenance data, or remove weak classes from the next benchmark.
