# P5-B RCA-B User Runbook

This is a new RCA-B-only handoff file. Historical context files are protected and unchanged.

## Frozen state

- Selected path: `PATH_B_FRESH100`
- Reason: the original `.keras` checkpoint preserves model and AdamW state but not exact dropout
  and shuffled-iterator state; it cannot support a scientifically exact PATH A continuation.
- Representation: `[96,238]`
- Architecture: production streaming causal TCN, 4×64, dilations 1/2/4/8, kernel 3, dropout 0.3
- Seed: 101
- Epochs: 0 through at most 99 (100 total)
- Patience: 8 on maximum validation per-frame accuracy
- Augmentation/warm start: none/none
- Output: `artifacts/recognition_upgrade/p5_representation_v2/p5b_rcab_horizon_01`

## 1. Working directory

```powershell
Set-Location 'F:\ASL DATASET\5. Apphear3'
```

## 2. Preflight command

```powershell
& '.\.venv\Scripts\python.exe' -m model.p5b_rcab_horizon preflight
```

Expected: `passed: true`, path `PATH_B_FRESH100`, train 3926, validation 816.

## 3. P5B_RCAB_FULL_TRAINING_COMMAND

```powershell
& '.\.venv\Scripts\python.exe' -m model.p5b_rcab_horizon train
```

Run this command yourself. The AI did not execute it.

## 4. Monitor progress

In another PowerShell window:

```powershell
Set-Location 'F:\ASL DATASET\5. Apphear3'
& '.\.venv\Scripts\python.exe' -m model.p5b_rcab_horizon status
```

To follow epoch rows continuously:

```powershell
Get-Content -LiteralPath 'F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\p5_representation_v2\p5b_rcab_horizon_01\history_extended.csv' -Tail 10 -Wait
```

## 5. Safe interruption

Press `Ctrl+C` once. An incomplete current epoch is discarded; the most recent fully completed
epoch checkpoint remains canonical. Do not delete or edit the output directory.

## 6. Resume-after-interruption command

```powershell
Set-Location 'F:\ASL DATASET\5. Apphear3'
& '.\.venv\Scripts\python.exe' -m model.p5b_rcab_horizon train --resume
```

The command refuses to resume without the full TensorFlow checkpoint and matching state record. It
does not silently reset AdamW, dropout RNG, shuffle iterator, best metric, or early-stop wait.

## 7. Completion condition

Training is complete when `status` reports either:

- `EARLY_STOPPED`, or
- `MAX_EPOCH_REACHED` with `completed_epochs: 100`.

Expected key files:

- `history_extended.csv`
- `run_state.json`
- `best.keras`
- `latest.keras`
- `resume_state/checkpoint`
- TensorFlow checkpoint data/index files

Do not select a checkpoint from test results. `best.keras` is selected only by validation PF
accuracy.

## 8. Final evaluation command — run only after training completes

```powershell
& '.\.venv\Scripts\python.exe' -m model.p5b_rcab_horizon evaluate
```

This refuses to run unless the governed training state is complete. Send back:

- console output from `status`;
- console output from `evaluate`;
- `history_extended.csv`;
- `run_state.json`;
- `evaluation_summary.json`.

Do not begin P5-C, canonicalization, augmentation, warm-start, architecture, perception, or Android
work from this runbook.

