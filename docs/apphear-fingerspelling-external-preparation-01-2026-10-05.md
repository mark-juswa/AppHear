# AppHear managed I: preparation and overhead reduction — 2026-10-05

Status: EXTERNAL_PREPARATION_READY. User requested faster preparation and selected I:.
No new RGB download, Candidate01 extraction, inference evaluation or training was run.
Only metadata/manifests were copied to the managed destination during preflight.

## Destination and preservation

New package root: `I:\AppHearData\FSboard_TRAIN4096_01`.
Subpackages: `train_additions` (3,072) and `dev_b` (256).
Original 1,024 TRAIN /256 DEV-A sources/raw/features stay on F: unchanged.
Frozen logical TRAIN4096 selection, DEV-B selection and all manifest hashes remain exact.
The copied subpackage manifests are byte-identical to their F: counterparts.

Actual I: metadata-only preflight passed, with379,677,003,776 bytes free and a conservative
25,486,435,266-byte requirement. Space check uses the destination volume, not F:.
The one-byte difference from the earlier combined estimate comes from rounding separate
per-package archive estimates. No cleanup, move or deletion of existing data was performed.

## Safe overhead changes

The older PowerShell workflow starts a Python process and reloads Candidate01 for each
pending batch, and repeatedly validates every completed sequence on acquisition, extraction
and after each batch. This adds startup overhead and quadratic cumulative array rereads.

The new opt-in runner:

- reuses the existing frozen acquire/extract functions, with their original CPU backend,
  thread settings, preprocessing, model hashes, whole-video decoding and timestamps;
- keeps one serial Candidate01 runtime cache across all pending batches/packages;
- does a full artifact integrity/recompute check on resume before skipping completed receipts;
- retains global manifest/official-role/phrase/duplicate validation every batch;
- fully hashes/recomputes only the completed batch's source/raw/features during batch checks;
- performs final full-package validation, and never marks scoped validation as admission;
- retains official size/MD5, SHA lineage, chronological masks/geometry and CTC status;
- records explicit failures and stops on failure; rerunning the same command resumes;
- uses the original retry settings and single-writer mechanism; no parallel Candidate01;
- closes the runtime at exit and retains interrupted staging via existing recovery tooling.

No frame dropping, cadence change, precision change, GPU switch, interpolation, model
change or tensor-math change. Quality is not traded for speed. The 13.36-hour Candidate01
processing estimate still applies; startup/revalidation overhead is reduced, but no new
end-to-end speedup measurement is claimed. I: SSD/HDD type was not verified; another drive
provides capacity and is not itself proof of faster inference.

## Explicit external path contract

`pipeline/fingerspelling/storage.py`: new opt-in marker schema
`apphear.fingerspelling.external_storage.v1`. Every managed package declares its exact
resolved package root and frozen manifest SHA in `storage.json`. External receipt paths
are absolute and confined to that declared package. Each external receipt binds the
marker SHA/schema. Repository-relative legacy paths stay unchanged.

`sequence_package.py`: only path handling and optional scoped validation scheduling
changed; geometry, feature order, masks, dtype, adapter identity, CTC targets and raw-v1
are unchanged. Default validation remains full. Scoped checks require a separate report
path and cannot overwrite the global report. Unexpected artifacts, unknown scope IDs,
source escapes, marker tampering and tensor corruption are rejected.

Keep this destination stable for resume. Moving prepared external packages needs an
explicit relocation/rebinding procedure; do not hand-edit receipt paths or markers.
The original bounded foundation CLI still restricts its --output to F:; use the new
managed runner for I:. Original PowerShell runner remains available unchanged for F:.

## Tests and preservation

- 48 pytest tests pass:12 new external/storage/runner tests and36 existing foundation/selection
 regressions. The original test that rewrites foundation validation.json was excluded.
- Actual saved TRAIN source/raw from the original package was copied to temporary test
 fixtures only; all arrays, including native/phone features and metadata, reproduce exactly.
 No Candidate01 extraction was involved in that parity test.
- External full/scoped integrity, report isolation, path/marker/tensor tampering, unknown scope,
 deterministic frozen-copy protection and destination-root guards pass.
- Mocked two-package scheduler proves one runtime cache, batch-specific checks, full resume
 and final checks, and completed-work skipping. This is engineering control-flow evidence,
 not new-video throughput or accuracy evidence.
- DEV-B metadata preflight explicitly forbids Candidate01 construction and passes.
- Ruff and mypy pass for all four touched/new implementation/test modules.
- 8,223 previous files rehashed: only the intended `sequence_package.py` helper changed.
 Original source videos/raw/features, models, adapter, perception source, decoder, Android,
 WORD and Context Assist remain unchanged. Evidence `preservation.json`.
- Actual I: preflight created manifests, markers and reports only; prepared_new=0/0,
 pending_new=3,328. TEST payload remains sealed; DEV-B performance is untouched.

## Exact commands — user-run only

Preflight was already run successfully; rerunning is safe. Preparation is the long-running
operation and has not been launched here. Do not use the older F: PowerShell command for
this external destination.

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m tools.fingerspelling.prepare_expansion preflight --destination 'I:\AppHearData\FSboard_TRAIN4096_01'
& .\.venv\Scripts\python.exe -u -m tools.fingerspelling.prepare_expansion prepare --destination 'I:\AppHearData\FSboard_TRAIN4096_01'
```

Stop with Ctrl+C if needed; rerun the identical `prepare` command to resume after full
integrity validation. A failed integrity check stops without overwriting the source.
Status can be read while the preparation runs:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m tools.fingerspelling.prepare_expansion status --destination 'I:\AppHearData\FSboard_TRAIN4096_01'
```

After preparation finishes, run the complete structural gate:

```powershell
& .\.venv\Scripts\python.exe -m tools.fingerspelling.prepare_expansion validate --destination 'I:\AppHearData\FSboard_TRAIN4096_01'
```

Optional bounded role separation uses `--package TRAIN_ADDITIONS` or `--package DEV_B`
on preflight/prepare/validate. Default ALL walks exactly the208 frozen batches of16.
No TEST or training commands exist in the new runner.

## Success and logs

Expect `SELECTED_PACKAGES_MATERIALIZED_INTEGRITY_PASS`, with3,072 new TRAIN and256DEV-B
validated sequences and zero structural errors. Together with the preserved1,024 TRAIN,
this gives the logical4,096 TRAIN target; DEV-A remains original256.
A fast status report is an inventory, not a substitute for complete final validation.

`I:\AppHearData\FSboard_TRAIN4096_01\execution\`:
`preflight.json`, `implementation_identity.json`, `events.jsonl`, `progress.json`,
`failures.json`, `final_validation.json`.
Each package has full `validation.json` and separately named per-batch reports under
`execution/batches/`. Changes to preparation implementation after initialization fail
resume identity checks rather than silently mixing implementations.

Existing readiness quotas still describe the original1,024/256 foundation and remain
unchanged. Materialized expansion integrity PASS is **not expanded training admission**.
A later authorized expanded loader/readiness check must combine the immutable original
TRAIN, new TRAIN and original DEV-A, keeping DEV-B final-confirmation-only.

## Exact code changes and review

- Added `pipeline/fingerspelling/storage.py`.
- Added `tools/fingerspelling/prepare_expansion.py`.
- Added `tests/test_fingerspelling_external_preparation.py`.
- Updated only path/validation handling in `pipeline/fingerspelling/sequence_package.py`;
 previous source snapshot saved as `artifacts/fingerspelling_external_preparation_01/sequence_package_before.py`.
- Appended registry/progress/memory and this report. No old frozen manifests or wrapper edited.

Review: scope PASS, numerical preservation PASS, managed storage/lineage PASS, preparation
control-flow PASS. Critical0; important0 for this engineering handoff. Limitations:
actual new-video extraction is user-run, speedup unmeasured, relocation unsupported,
expanded training loader/readiness still pending and DEV-B remains confirmation-only.

EXTERNAL_PREPARATION_READY
