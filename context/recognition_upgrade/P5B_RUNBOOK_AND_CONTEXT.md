# P5-B Runbook and Context

Created as a new file on 2026-08-25. No historical context file was modified. `context/progress-tracker.md` is protected and must remain untouched. P5-A is accepted as `P5A_REPRESENTATION_READY`; its historical line-ending provenance exception is accepted and must not be repaired.

P5-B uses only `DWPOSE_REPRESENTATION_V2_238`, shape `[96,238]`, contract SHA-256 `0c94e9c885f331164d8ab1f7f0915eb89de43101394bd0949fae033b57f76d8b`. Full extraction and training are user-run jobs.

## 1 — Full extraction command

Run in PowerShell from any directory:

```powershell
wsl.exe bash -lc "cd '/mnt/f/ASL DATASET/5. Apphear3' && ~/apphear_p2a_dwpose/env/bin/python -m eval.runtime_diagnostics.p5b_dataset_migration extract"
```

Expected output root:

`F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\p5_representation_v2\p5b_migration_01`

Expected canonical samples: **8,131**. Restart with the exact same command. Verified completed samples are skipped; failures are recorded under `failures/`. Atomic writes prevent half-written samples from becoming completed.

## 2 — Monitor command

```powershell
$root='F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\p5_representation_v2\p5b_migration_01'; [pscustomobject]@{completed=(Get-ChildItem -LiteralPath "$root\completed" -Filter *.json -ErrorAction SilentlyContinue).Count; failed=(Get-ChildItem -LiteralPath "$root\failures" -Filter *.json -ErrorAction SilentlyContinue).Count; expected=8131}
```

The running extractor also prints position, completed, failed, remaining, and ETA.

## 3 — Validation and assembly commands

After extraction reports completion:

```powershell
Set-Location 'F:\ASL DATASET\5. Apphear3'
& '.\.venv\Scripts\python.exe' -m eval.runtime_diagnostics.p5b_dataset_migration validate --require-complete --verify-checkpoint
```

Only after validation says `passed: true`:

```powershell
Set-Location 'F:\ASL DATASET\5. Apphear3'
& '.\.venv\Scripts\python.exe' -m eval.runtime_diagnostics.p5b_dataset_migration assemble
```

Then run the training preflight:

```powershell
Set-Location 'F:\ASL DATASET\5. Apphear3'
& '.\.venv\Scripts\python.exe' -m model.p5b_temporal_baseline preflight
```

Do not train unless every command succeeds. Expected assembled counts are train 3,926, validation 816, and test 2,620. Diagnostic/stress/replay roles remain separate and never enter fitting.

## 4 — Full training command

```powershell
Set-Location 'F:\ASL DATASET\5. Apphear3'
& '.\.venv\Scripts\python.exe' -m model.p5b_temporal_baseline train
```

Expected checkpoint/log directory:

`F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\p5_representation_v2\p5b_baseline_01`

Files include `history.csv`, `latest.keras`, `best.keras`, and `final.keras`. Monitor `history.csv` while training.

If safely interrupted after a checkpoint, resume with:

```powershell
Set-Location 'F:\ASL DATASET\5. Apphear3'
& '.\.venv\Scripts\python.exe' -m model.p5b_temporal_baseline train --resume
```

Completion means training exits successfully and `best.keras`, `final.keras`, and `history.csv` exist. Do not restart from scratch in the same directory; the trainer refuses overwrite.

## 5 — Evaluation command

Run only after training completes:

```powershell
Set-Location 'F:\ASL DATASET\5. Apphear3'
& '.\.venv\Scripts\python.exe' -m model.p5b_temporal_baseline evaluate
```

Expected evaluation outputs are `evaluation_summary.json`, `test_predictions.csv`, and `confusion_matrix.npy` in the baseline directory, alongside the training history. Missingness strata use only feature masks and were frozen before test access.

## 6 — Files to send back

After extraction/validation, send:

- `p5b_migration_01/validation_summary.json`
- `p5b_migration_01/dataset/assembly_summary.json`
- the final extraction console summary or screenshot

After training/evaluation, send:

- `p5b_baseline_01/history.csv`
- `p5b_baseline_01/evaluation_summary.json`
- `p5b_baseline_01/test_predictions.csv`
- `p5b_baseline_01/confusion_matrix.npy`
- the training/evaluation console output

Do not start P5-C or reopen P4 automatically. The first valid frozen run is canonical.
