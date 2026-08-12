# E6 v3.0 Validation Repair Result

Last updated: 2026-08-09

## Purpose

Replace the unbalanced five-sign model-selection validation split without collecting or extracting
new data, while preserving the former AppHear validation signer as explicit stress evidence.

## Scope And Status

Status: **complete and passed; repaired transfer package smoke-validated**.

No raw videos, per-clip source tensors, models, Android assets, feature schema, labels, or test-set
assignments were changed. Existing tensors were copied by `sample_id` into new split files.

Repair run:

`artifacts/recognition_upgrade/e6_baseline/e6_v30_validation_repair_01`

Prepared transfer run:

`artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_transfer_repaired_val_01`

## Verified Split

| Split | Clips | Purpose |
|---|---:|---|
| train | 535 | warm-start fitting |
| val | 166 | checkpoint selection |
| validation_variant_stress | 163 | former problematic AppHear validation signer |
| test_fresh | 300 | unchanged fresh diagnostic signer |
| test_historical | 63 | unchanged ASL Citizen historical test |

The new validation set contains:

- 150 local clips from complete holdout signer `local_recorder:6F7328-S001`;
- exactly 30 local clips for each of the five classes;
- 16 original signer-disjoint ASL Citizen validation clips;
- totals of `GOOD 34`, `HELLO 34`, `SORRY 33`, `HAVE 34`, and `KNOW 31`.

The former AppHear validation signer is not discarded. Its 163 clips remain under
`validation_variant_stress`, including the known difficult 30-clip `KNOW` subset. It has no `HAVE`
clips and therefore cannot serve as the primary complete validation split.

## Integrity Gates

- Train/validation signer overlap: `0`.
- Train/validation raw-video hash overlap: `0`.
- Fresh-test sample IDs: unchanged.
- Historical-test sample IDs: unchanged.
- Every primary validation class has at least 30 local clips.
- Repair package structural check: passed.
- Repaired transfer smoke: copied `17/17` encoder layers, forward/train/save/reload passed.

## Architecture Decisions

- Use the repaired validation set only for checkpoint selection.
- Report `validation_variant_stress` separately; never average it into normal validation.
- Preserve broad encoder warm start as the only model change.
- Keep class weights disabled and the v3.0 `[96,258]` contract unchanged.
- Do not select a seed using fresh-test results.

## User-Run Commands

From `F:\ASL DATASET\5. Apphear3`:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_v30_five_sign_transfer train `
  --run-dir "artifacts\recognition_upgrade\e6_baseline\e6_v30_five_sign_transfer_repaired_val_01"
```

Resume only if interrupted:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_v30_five_sign_transfer train `
  --run-dir "artifacts\recognition_upgrade\e6_baseline\e6_v30_five_sign_transfer_repaired_val_01" `
  --resume
```

After all three seeds complete:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_v30_five_sign_transfer evaluate `
  --run-dir "artifacts\recognition_upgrade\e6_baseline\e6_v30_five_sign_transfer_repaired_val_01"

.\.venv\Scripts\python.exe -m pipeline.rgb.e6_v30_five_sign_transfer check `
  --run-dir "artifacts\recognition_upgrade\e6_baseline\e6_v30_five_sign_transfer_repaired_val_01" `
  --require-smoke `
  --require-metrics
```

## Acceptance Gate

The existing transfer gates remain unchanged. Additionally:

- validation ranking must no longer depend on the old variant-stress signer;
- report all three seeds on normal validation, variant stress, fresh test, and historical test;
- do not promote a checkpoint that passes normal validation but catastrophically fails the stress
  `KNOW` subset;
- this remains a pilot because the fresh test contains one inspected signer.

## Risks And Assumptions

- The complete local holdout is one dominant recorder signer; the 16 ASL clips add signers but little
  per-signer volume.
- `local_recorder` IDs are treated as signer identities based on existing lineage; independent
  identity verification remains incomplete.
- Removing 150 clips reduces training to 535 clips and may increase variance.
- A repaired validation signal may still disagree with the single fresh AppHear signer.

## Source-Of-Truth Files

- `pipeline/rgb/e6_v30_validation_repair.py`
- `tests/test_e6_v30_validation_repair.py`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_validation_repair_01/repaired_assignment_manifest.csv`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_validation_repair_01/validation_repair_report.json`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_transfer_repaired_val_01/pilot_config.json`
- `artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_transfer_repaired_val_01/smoke/smoke_summary.json`

## Related Context

- `E6_V30_FIVE_SIGN_TRANSFER_RESULT.md`
- `E6_V30_FIVE_SIGN_TRANSFER_PACKAGE.md`
- `E6_V30_CONFUSION_ROOT_CAUSE_RESULT.md`
- `../../../EVALUATION_AND_ACCEPTANCE_GATES.md`
- `../../../ROLLBACK_AND_COMPATIBILITY_PLAN.md`

## Open Questions

- Does repaired validation select stable `KNOW` behavior across seeds?
- Does the stress signer remain an unresolved label/variant domain?
- Is the remaining training volume sufficient after complete-signer holdout?

## Next Required Action

Training and evaluation are complete. See
`E6_V30_REPAIRED_VALIDATION_TRANSFER_RESULT.md`. The v3.0 control is now frozen, repeated baseline
tuning is closed, and E6-2 richer landmark-feature control planning is the next authorized action.
