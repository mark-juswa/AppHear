# E4-J Reliable-Core 3-Sign Package

**Purpose:** Define and preserve the E4-J reliable-core benchmark package prepared after E4-I failed the 4-sign gate.

**Scope:** Experiment package only. This does not authorize Android integration, model export, production-recognizer replacement, source-video mutation, dataset relabeling, or feature-schema changes.

**Current status:** Prepared; smoke test passed; structural check passed without metrics. Full training is the next user-run step.

**Last updated:** 2026-07-30.

## Verified Project References

- Runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_j_reliable_core_3sign.py`
- Run directory: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_j_reliable_core_3sign_pilot_01`
- Source tensor: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_f_cleaned_diagnostic_pilot_01\dataset\landmark_features.npz`
- Source result context: `E4_I_RELIABLE_CORE_RESULT.md`
- Package config: `pilot_config.json`
- Dataset tensor: `dataset\landmark_features.npz`
- Smoke summary: `smoke\smoke_summary.json`
- Check report: `check_report.json`

## Why E4-J Exists

E4-I tested `GOOD`, `HELLO`, `SORRY`, and `YES`. It completed structurally but failed the reliability gate:

- Best Conv1D mean test: `0.8249`, below the `0.85` 4-sign gate.
- Validation-selected checkpoint test: `0.6780`.
- Validation-selected `SORRY`: `3/30`.
- Validation-selected `YES`: `18/28`.
- Latest Conv1D was better, but `YES` still stayed around `0.7143` to `0.7500` on test.

The engineering decision is to stop rescuing weak signs temporarily and prove whether the current `[96,258]` landmark path can produce a tiny stable signer-held-out core first.

## Selected Classes

E4-J keeps only:

- `GOOD`
- `HELLO`
- `SORRY`

E4-J excludes:

- `BYE`
- `NO`
- `THANKYOU`
- `YES`

## Prepared Dataset

Verified from `prepare` output:

- Active rows: `190`
- Input shape: `[96,258]`
- Random baseline: `0.3333`
- Train rows: `75`
- Validation rows: `25`
- Test rows: `90`

Class counts:

| Split | GOOD | HELLO | SORRY |
|---|---:|---:|---:|
| train | 15 | 45 | 15 |
| validation | 5 | 15 | 5 |
| test | 30 | 30 | 30 |

Signer split remains held-out at test:

| Gloss | Train/Val Signer | Test Signer |
|---|---|---|
| GOOD | `3B96F6-S001` | `6F7328-S001` |
| HELLO | `3B96F6-S002` | `6F7328-S001` |
| SORRY | `3B96F6-S002` | `6F7328-S001` |

Known limitation: validation is still small and partly same signer as training. E4-J is a reliability-core diagnostic, not a final production benchmark.

## Models

Branches:

- `conv1d_baseline`
- `tcn_masked_pool`

Seeds:

- `101`
- `202`
- `303`

Training settings:

- Epochs per run command: `20`
- Batch size: `8`
- Learning rate: `0.0005`
- Resume support: yes, via `--resume`

## Added Reporting

E4-J adds a `stability_summary` to `metrics\metrics.json` and writes `metrics\metrics.md` after training.

The summary reports best-vs-latest checkpoint behavior, mean test accuracy by branch/checkpoint family, test standard deviation across seeds, minimum seed test accuracy, minimum per-class test accuracy, validation-selected checkpoint, and gate decision.

This directly addresses the E4-I problem where the validation-selected checkpoint looked perfect on validation but collapsed on the held-out signer.

## Gate

E4-J should be treated as a go only if all are true:

- Validation-selected test accuracy `>= 0.90`.
- Every selected class test accuracy `>= 0.90`.
- Latest and best checkpoint families are stable across seeds.
- No predicted-class collapse.

No-go if any selected class falls below `0.90`, validation is near-perfect while held-out test is materially lower, or one/two classes dominate predictions.

## Validation Already Completed

Prepare completed successfully and created the isolated package.

Smoke test completed successfully:

- Rows: `8`
- Tensor shape: `[8,96,258]`
- Conv1D forward output: `[8,3]`
- Masked TCN forward output: `[8,3]`
- One training step ran for both branches
- Smoke weights were saved under `smoke\`

Structural check completed successfully:

```json
{
  "passed": true,
  "errors": []
}
```

## User Command For Full Training

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_j_reliable_core_3sign run `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_j_reliable_core_3sign_pilot_01"
```

If interrupted:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_j_reliable_core_3sign run `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_j_reliable_core_3sign_pilot_01" `
  --resume
```

After training:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_j_reliable_core_3sign check `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_j_reliable_core_3sign_pilot_01" `
  --require-full-dataset `
  --require-metrics
```

## Architecture Decisions

- Keep current `[96,258]` feature contract for E4-J to isolate vocabulary reliability from feature redesign.
- Do not rerun MediaPipe extraction; reuse E4-F cleaned tensor.
- Do not use RGB for this step; the purpose is to prove or reject the existing landmark path on a tiny reliable local core.
- Do not integrate with Android unless E4-J passes and a separate deployment experiment is approved.

## Assumptions

- E4-F cleaned labels are the current best available local labels.
- `GOOD`, `HELLO`, and `SORRY` are the strongest currently available local signs.
- E4-J is a diagnostic stepping stone, not the desired final vocabulary.

## Open Questions

- Does `SORRY` remain stable once `YES` is removed?
- Does Conv1D continue to outperform masked TCN on this small local core?
- Is validation still too small to select checkpoints reliably?
- If E4-J passes, should the next expansion add one new local sign at a time or recollect more balanced data first?

## Risks

- A 3-sign core may pass but still not scale.
- HELLO has more train/validation rows than GOOD/SORRY, so the training split remains imbalanced.
- The held-out test signer is still a small benchmark and can be overfit by repeated experiment choices.

## Next Required Action

User runs the full E4-J training and check commands, then Codex analyzes `metrics\metrics.json`, `metrics\metrics.md`, and `check_report.json`.