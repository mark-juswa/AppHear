# P5-B RCA-C User Runbook

This is a new RCA-C-only handoff. Historical context files remain read-only.

## Frozen identity

- Representation: `DWPOSE_REPRESENTATION_V2_238`, `[96,238]`
- Model: production streaming TCN, 4 × 64, dilations `(1,2,4,8)`, kernel 3, dropout 0.3
- Optimizer: AdamW, learning rate `5e-4`, weight decay `1e-4`
- Batch/seed: 32 / 101
- Maximum epochs/patience: 100 / 8
- Warm start: none
- Canonicalization change: none
- Missingness augmentation: none
- Output: `artifacts/recognition_upgrade/p5_representation_v2/p5b_rcac_augmentation_01`

## Full training command

```powershell
Set-Location 'F:\ASL DATASET\5. Apphear3'
& '.\.venv\Scripts\python.exe' -m model.p5b_rcac_augmentation preflight
& '.\.venv\Scripts\python.exe' -m model.p5b_rcac_augmentation train
```

The first command verifies the frozen contract and train/validation tensors. The second starts the
long user-run job. TensorFlow native-Windows GPU warnings are informational; this experiment uses
the recorded CPU backend.

## Monitor

Open another PowerShell in the project root:

```powershell
& '.\.venv\Scripts\python.exe' -m model.p5b_rcac_augmentation status
```

## Safe interruption and resume

Use `Ctrl+C`. The current incomplete epoch is discarded; the preceding completed epoch remains
checkpointed. Resume with:

```powershell
Set-Location 'F:\ASL DATASET\5. Apphear3'
& '.\.venv\Scripts\python.exe' -m model.p5b_rcac_augmentation train --resume
```

Do not delete or manually edit the run directory before resuming.

## After training: validation only

Once status is `EARLY_STOPPED` or `MAX_EPOCH_REACHED`, run:

```powershell
Set-Location 'F:\ASL DATASET\5. Apphear3'
& '.\.venv\Scripts\python.exe' -m model.p5b_rcac_augmentation evaluate-validation
```

Return `run_state.json`, `history.csv`, and `validation_comparison.json` for project-lead review.
Do not run protected-test evaluation. This runner intentionally exposes no protected-test command.
