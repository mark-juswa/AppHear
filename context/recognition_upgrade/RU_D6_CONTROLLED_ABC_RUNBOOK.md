# RU-D6 Controlled A/B/C Retraining Runbook

**Status:** PREPARED — manual training pending  
**Date:** 2026-08-14

## Locked branches

- A: frozen Phase-1 baseline, 3,926 rows.
- B: RU-D3 cleanup-only, 3,820 rows.
- C: B plus 32 frozen Sem-Lex exact-target rows, 3,852 rows.

Preparation proves that C's first 3,820 rows equal B for all tensor and lineage arrays. A/B/C share
the same validation hash, vocabulary, production-family TCN recipe, warm start, augmentation,
hyperparameters, and seeds `101/202/303`. The protected test is prohibited.

The bounded one-step smoke passed for all three branches: 169,004 parameters, 17 copied encoder
weights, finite `[32,236]` predictions.

## Manual command

From PowerShell:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& '.\model\config\recognition_upgrade\run_ru_d6_controlled_abc.ps1'
```

The launcher uses `.venv\Scripts\python.exe`, validates the smoke, runs/resumes nine jobs (three
branches x three seeds), evaluates only the shared validation set, and performs a final artifact
check.

During training, expect headings containing branch, seed, row count, and epoch progress including
`val_clip_acc`. Successful completion prints `RU-D6 COMPLETE` and creates:

- `artifacts/recognition_upgrade/ru_d6/controlled_abc_01/models/<branch>/seed_<seed>/`
  with `best.keras`, `latest.keras`, `final.keras`, and `history.csv`;
- `metrics/abc_validation_report.json`;
- `metrics/per_class_comparison.csv`;
- `metrics/target_confusions.csv`;
- `metrics/validation_predictions.npz`;
- `logs/check_report.json` with `passed: true`, no errors, and
  `protected_test_accessed: false`.

The report includes Top-1, Top-5, macro-F1, worst-decile recall/F1, ECE, seed consistency,
unrelated-class regressions, all five target classes, and the locked confusion pairs. Results do
not authorize production deployment; fresh-phone confirmation remains required after evaluation.
