# E4-AA No-Sign Temporal Gate Package

Last updated: 2026-08-02

## Purpose

E4-AA is the next step after E4-Z failed. Its purpose is to test whether a stronger temporal signing/no-sign gate can reduce real MediaPipe no-sign false commits without destroying low-motion signs such as `SORRY`.

## Scope

This is an offline recognition-upgrade experiment only. It does not change Android code, production TFLite files, schema v3.0, datasets, or the current production recognizer.

## Verified Project References

- Runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_aa_nosign_temporal_gate.py`
- Smoke run: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_aa_nosign_temporal_gate_smoke_01`
- E4-S primary source: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_s_stable_primary_4sign_01`
- E4-V specialist source: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_v_sorry_good_specialist_01`
- E4-X routed policy source: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_x_routed_system_validation_01`
- E4-Y real no-sign cache source: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_y_real_nosign_feature_validation_01`
- N0 reviewed capture source: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e2e_c0\n0_capture_06`
- P1 reviewed capture source: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e2e_c0\p1_capture_03`

## Current Status

Package prepared and smoke-checked. The smoke used only `2` N0 rows and `2` P1 rows to validate wiring, not accuracy. It produced schema v3.0 features with shape `[4,96,258]`, trained one tiny temporal gate seed for one epoch, wrote metrics, and passed structural check.

Smoke check command passed:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_aa_nosign_temporal_gate check `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_aa_nosign_temporal_gate_smoke_01" `
  --require-metrics
```

## Architecture Decision

E4-AA tests a temporal binary gate before the E4-S/E4-V routed recognizer:

`real MediaPipe [96,258] window -> temporal signing/no-sign gate -> E4-S primary -> GOOD/SORRY specialist if routed -> accept/reject -> final gloss or NO_SIGN`

The gate is a small Conv1D temporal model over the existing `[96,258]` feature contract. This intentionally keeps schema v3.0 stable while testing whether sequence-level evidence can separate signing from no-sign better than E4-Z summary features.

## Why This Comes Next

E4-Y proved zero-landmark no-sign tests were misleading: real N0/P1 MediaPipe windows caused severe false commits. E4-Z proved simple motion/presence gates were too blunt and rejected low-motion signs. E4-AA is therefore the smallest high-value next experiment: expand real no-sign coverage and train a temporal gate using actual `[96,258]` sequences.

## Commands For Full Run

Prepare/extract and train/evaluate in one command:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_aa_nosign_temporal_gate run `
  --output "artifacts\recognition_upgrade\e4_generalization\e4_aa_nosign_temporal_gate_01"
```

If extraction is interrupted, rerun the same command. It reuses completed clip caches.

For safer long-run control, split it into two commands:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_aa_nosign_temporal_gate run `
  --output "artifacts\recognition_upgrade\e4_generalization\e4_aa_nosign_temporal_gate_01" `
  --prepare-only

.\.venv\Scripts\python.exe -m pipeline.rgb.e4_aa_nosign_temporal_gate run `
  --output "artifacts\recognition_upgrade\e4_generalization\e4_aa_nosign_temporal_gate_01" `
  --train-only
```

Final check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_aa_nosign_temporal_gate check `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_aa_nosign_temporal_gate_01" `
  --require-metrics
```

## Expected Outputs

- `dataset/nosign_features.npz`
- `dataset/nosign_manifest.csv`
- `dataset/stage_e_cache/*.npz`
- `logs/dataset_summary.json`
- `logs/run_summary.json`
- `metrics/temporal_gate_metrics.json`
- `metrics/threshold_grid.csv`
- `check_report.json`

## Acceptance Gate

A full E4-AA result is promising only if it preserves the dynamic mixed recognizer while reducing real no-sign false commits:

- accepted precision >= `0.95`
- positive coverage >= `0.80`
- no-sign false commit rate <= `0.10`
- GOOD recall >= `0.90`
- SORRY recall >= `0.90`

## Risks

- Full MediaPipe extraction can be slow on CPU.
- Current no-sign data may still be too small or too narrow for production.
- A gate can overfit to N0/P1 capture conditions.
- Low-motion signs may still be rejected unless training data includes enough such positives.

## Next Required Action

User should run the full E4-AA command when ready. Do not start Android/export or broaden vocabulary until the full E4-AA metrics are evaluated.
