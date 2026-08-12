# E6 v3.0 Five-Sign Warm-Start Transfer Package

Last updated: 2026-08-09

## Purpose

Test one explanation for the failed from-scratch five-sign baseline: whether the broader 236-class
causal encoder contains signer-robust landmark representations that the 685-clip five-sign dataset
cannot relearn reliably from zero.

## Scope And Status

Status: **training and evaluation complete; result is no-go for deployment**. See
`E6_V30_FIVE_SIGN_TRANSFER_RESULT.md`.

This is a diagnostic experiment. It does not change the feature schema, data assignments, model
architecture, class weights, Android runtime, production assets, or confirmation logic.

Run directory:

`artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_transfer_01`

## Controlled Change

The only training change is:

`warm_start_from = broader 236-class best.keras`

Seventeen weighted causal-TCN encoder layers are copied. The incompatible 236-class output head is
skipped and a new five-class per-frame head is initialized. Everything else matches the
from-scratch baseline: data, splits, v3.0 `[96,258]` tensors, four TCN blocks, 64 channels,
augmentation, optimizer, 40-epoch maximum, and seeds `101`, `202`, and `303`.

## Verified Lineage

- Keras source:
  `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/runs/tcn_streaming_conversational_plus_local_pc_236_rtx3050_v30/best.keras`
- Keras SHA-256:
  `FC7A3884430873DDCA6A24E4D29DFF70DD78ACEB961B05A393EAF8C893E353E5`
- Source contract: `[None,96,258] -> [None,96,236]`.
- Source TFLite and current Android TFLite both hash to
  `42575710A4ADB0A1433B58BA9093BC4E9F49401381582CC4AD304FEEB669D4BB`.
- Smoke copied all `17/17` expected weighted encoder layers with exact pre-training weight equality.
- Actual-data forward pass, one training step, checkpoint save, and checkpoint reload passed.

## User-Run Commands

Run from `F:\ASL DATASET\5. Apphear3`.

Start the complete three-seed training:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_v30_five_sign_transfer train `
  --run-dir "artifacts\recognition_upgrade\e6_baseline\e6_v30_five_sign_transfer_01"
```

If interrupted, rerun with resume:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_v30_five_sign_transfer train `
  --run-dir "artifacts\recognition_upgrade\e6_baseline\e6_v30_five_sign_transfer_01" `
  --resume
```

After all three seeds finish:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_v30_five_sign_transfer evaluate `
  --run-dir "artifacts\recognition_upgrade\e6_baseline\e6_v30_five_sign_transfer_01"

.\.venv\Scripts\python.exe -m pipeline.rgb.e6_v30_five_sign_transfer check `
  --run-dir "artifacts\recognition_upgrade\e6_baseline\e6_v30_five_sign_transfer_01" `
  --require-smoke `
  --require-metrics
```

Do not use `--resume` for the first run. Do not run multiple training commands concurrently.

## Acceptance And Failure Gates

The latest checkpoint remains primary. The transfer test passes only if:

- mean fresh top-1 is at least `0.80`;
- minimum-seed fresh top-1 is at least `0.70`;
- every class has mean fresh recall at least `0.70`;
- every class has minimum-seed fresh recall at least `0.50`;
- `GOOD`, `HELLO`, and `SORRY` do not materially regress;
- all three seeds complete and remain structurally valid.

A pass supports broad encoder pretraining as the next scalable training foundation. It does not
authorize Android deployment or prove population-level signer independence.

A failure stops the five-sign model path. The next action would be split/variant repair, not class
weight tuning, thresholds, RGB, specialists, or vocabulary expansion.

## Previous Experiment Difference

The July targeted 236-class v1-v4 experiments changed class weights on a 236-class model and moved
errors between classes. This experiment uses no class weighting and does not try to repair the
236-class model. It isolates encoder transfer into a new five-class head on the repaired E6 data.

## Risks And Assumptions

- The fresh set contains only one signer and has already been inspected; it is now a development
  diagnostic, not a final unbiased test.
- Validation `HAVE` has only four ASL Citizen clips, so checkpoint selection for that class is weak.
- A transfer gain could inherit source-specific behavior from the broader checkpoint.
- A five-class pass does not guarantee that a retrained 236-class model will avoid regressions.

## Source-Of-Truth Files

- `pipeline/rgb/e6_v30_five_sign_transfer.py`
- `tests/test_e6_v30_five_sign_transfer.py`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_transfer_01/pilot_config.json`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_transfer_01/source_checkpoint_lineage.json`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_transfer_01/smoke/smoke_summary.json`

## Related Context

- `E6_V30_FIVE_SIGN_BASELINE_PACKAGE.md`
- `E6_V30_CONFUSION_ROOT_CAUSE_RESULT.md`
- `../../../E6_1_CONSOLIDATED_EVIDENCE_DATASET_AUDIT.md`
- `../../../EVALUATION_AND_ACCEPTANCE_GATES.md`
- `../../../ROLLBACK_AND_COMPATIBILITY_PLAN.md`

## Architecture Decisions

- Preserve schema v3.0 and the causal TCN for this one-variable diagnostic.
- Copy encoder weights only; never reuse the 236-class output head.
- Keep all artifacts isolated and prohibit Android export.

## Open Questions

- Will broad initialization recover fresh `KNOW` without harming the three stable classes?
- Will the validation-dominant signer remain a separate `KNOW` variant failure?
- If transfer passes, what grouped-validation design is required before larger batch training?

## Next Required Action

The result is recorded in `E6_V30_FIVE_SIGN_TRANSFER_RESULT.md`. Transfer improved fresh top-1 from
`0.7344` to `0.9044`, but failed the `KNOW` stability gate. Prepare the automated validation-split
repair before any retraining or vocabulary expansion.
