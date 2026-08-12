# E4-I Reliable-Core 4-Sign Result

**Purpose:** Record the completed E4-I 4-sign reliable-core benchmark result.

**Scope:** Experiment result only. This does not authorize Android integration, model export, production-recognizer replacement, feature-schema promotion, or source dataset mutation.

**Current status:** Completed; structural check passed, but reliability gate failed.

**Last updated:** 2026-07-30.

## Verified Project References

- Run directory: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_i_reliable_core_4sign_pilot_01`
- Runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_i_reliable_core.py`
- Metrics: `metrics\metrics.json`
- Check report: `check_report.json`
- Package plan: `E4_I_RELIABLE_CORE_PACKAGE.md`

## Completion Evidence

Final structural check passed:

```json
{
  "passed": true,
  "errors": []
}
```

This only means files/metrics exist. It does not mean the recognition gate passed.

## Dataset

- Classes: `GOOD`, `HELLO`, `SORRY`, `YES`
- Rows: `238`
- Split counts: train `90`, validation `30`, test `118`
- Input shape: `[96,258]`
- Source: E4-F cleaned Stage-E tensor
- Excluded from this benchmark: `BYE`, `NO`, `THANKYOU`

## Main Metrics

Best-checkpoint mean by branch:

| Branch | Mean validation | Mean test | Test std |
|---|---:|---:|---:|
| `conv1d_baseline` | `0.9778` | `0.8249` | `0.1041` |
| `tcn_masked_pool` | `0.9778` | `0.6808` | `0.0471` |

Validation-selected checkpoint by validation, then test:

- Branch: `conv1d_baseline`
- Seed: `202`
- Validation: `1.0000`
- Test: `0.6780`

Per-class test for the validation-selected checkpoint:

| Gloss | Correct / count | Accuracy |
|---|---:|---:|
| `GOOD` | `30/30` | `1.0000` |
| `HELLO` | `29/30` | `0.9667` |
| `SORRY` | `3/30` | `0.1000` |
| `YES` | `18/28` | `0.6429` |

Confusions for the validation-selected checkpoint:

- `SORRY -> GOOD`: 27 of 30
- `YES -> HELLO`: 10 of 28

Latest-epoch diagnostic for `conv1d_baseline` looked better but is not the pre-registered selection rule:

- Mean latest test: `0.9124`
- `GOOD` mean/min: `0.9778` / `0.9667`
- `HELLO` mean/min: `0.9444` / `0.9333`
- `SORRY` mean/min: `0.9889` / `0.9667`
- `YES` mean/min: `0.7262` / `0.7143`

## Gate Result

E4-I fails the reliable-core gate.

Reasons:

- Pre-registered branch mean test gate was `>=0.85`; best-checkpoint `conv1d_baseline` mean test was `0.8249`.
- Every-class gate was `>=0.80`; validation-selected `SORRY` was `0.1000` and `YES` was `0.6429`.
- Seed/checkpoint selection is unstable: validation is too small and too optimistic, so it selected a model that collapsed `SORRY` into `GOOD`.
- `YES` remains consistently below `0.80`, even when using latest-epoch Conv1D diagnostics.

## Interpretation

The pivot away from bad signs was correct, but the 4-sign set is still not production reliable.

The current evidence says:

- `GOOD` is strong.
- `HELLO` is strong.
- `SORRY` can be strong, but checkpoint selection can collapse it if validation is too small.
- `YES` is still not reliable enough for the first core.

The biggest remaining issue is no longer `BYE`/`NO`; it is the lack of a robust validation/selection setup and the continued weakness of `YES`.

## Decision

Do not export or integrate E4-I.

Do not call the 4-sign set production reliable.

The next practical step is to prepare a smaller E4-J reliable-core diagnostic with only the strongest three local signs:

- `GOOD`
- `HELLO`
- `SORRY`

For E4-J, use a stricter selection rule that compares latest and best checkpoints and reports seed stability, because the current validation set is too small to be trusted alone.

## Risks

- A 3-sign core is useful for proving pipeline stability but too small for product value.
- `SORRY` may still be vulnerable to checkpoint-selection artifacts.
- Continuing to use the same held-out signer risks overfitting decisions to this small test set.

## Next Required Action

Prepare E4-J as a 3-sign reliable-core benchmark (`GOOD`, `HELLO`, `SORRY`) with explicit seed-stability and latest-vs-best reporting. Do not expand the vocabulary or move to Android until this smaller core passes cleanly.
