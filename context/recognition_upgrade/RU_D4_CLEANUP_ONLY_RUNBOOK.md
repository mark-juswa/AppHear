# RU-D4 Cleanup-Only Controlled Retraining

## Purpose

RU-D4 measures only the effect of the RU-D3 cleanup. It compares the frozen
3,926-row baseline (A) with the 3,820-row repaired candidate (B). It does not
add data, change the feature contract, alter the production TCN recipe, or
access the protected test set.

## Frozen comparison

- Branch A: `artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1`
- Branch B: `artifacts/recognition_upgrade/ru_d3/repair_candidate_01/dataset`
- Shared validation SHA-256:
  `79FDEA39457FC1F3068AAD1F16603A83E3BD69D6469F96AF40C924379974AF59`
- Seeds: `101`, `202`, `303`
- Model: canonical `production_streaming_tcn`
- Recipe: canonical Phase-1 augmentation, optimizer, schedule, epochs,
  batching, validation checkpoint selection, and encoder-only warm start
- Model selection and RU-D4 metrics: shared validation only
- Protected test: prohibited and not materialized in the RU-D3 candidate

The generated contract is frozen at
`artifacts/recognition_upgrade/ru_d4/cleanup_only_ab_01/config/experiment.json`.

## Developer-run command

From PowerShell:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& '.\model\config\recognition_upgrade\run_ru_d4_cleanup_only_ab.ps1'
```

The launcher deliberately uses `.venv\Scripts\python.exe`. The system Python
must not be substituted because it cannot deserialize the Keras 3.15 warm-start
artifact.

The command first checks the prepared contract and paired smoke, then trains A
and B for each seed. Each run permits at most 40 epochs with the canonical
early-stop patience of 8. It then evaluates all six selected checkpoints on the
shared validation set and checks that every required artifact exists. Training
is resumable: after a normal interruption, run the same command again.

## Expected console progress

The launcher prints the repository, run directory, pinned interpreter, and the
six-run declaration. Training then identifies the branch and seed and prints
ordinary Keras epoch metrics plus validation clip accuracy. Runs proceed as
paired A/B comparisons for seeds 101, 202, and 303. Evaluation and the final
artifact check follow after all six models are present.

Successful completion ends with:

```text
RU-D4 COMPLETE
```

The final check must also report `passed: true` and
`protected_test_accessed: false`.

## Required outputs

Under `artifacts/recognition_upgrade/ru_d4/cleanup_only_ab_01`:

- `models/<branch>/seed_<seed>/best.keras`
- `models/<branch>/seed_<seed>/latest.keras`
- `models/<branch>/seed_<seed>/final.keras`
- `models/<branch>/seed_<seed>/history.csv`
- `logs/train_progress.json`
- `logs/train_summary.json`
- `metrics/ab_validation_report.json`
- `metrics/per_class_comparison.csv`
- `metrics/target_confusions.csv`
- `metrics/validation_predictions.npz`

The report includes seed-level and aggregate Top-1, Top-5, macro-F1,
worst-decile recall, ECE, per-class recall/F1, full-vocabulary deltas, and
focused KNOW, WHO, WE, and LEAVE confusion behavior. It is an offline
validation comparison, not a deployment decision. The selected foundation
still requires a separately approved fresh-phone confirmation.

## Stop boundary

After the command completes, stop and return the console result for A/B
analysis. Do not ingest external data, collect local data, change S5/S7,
change `[96,258]`, export a model, or modify Android production assets during
RU-D4.
