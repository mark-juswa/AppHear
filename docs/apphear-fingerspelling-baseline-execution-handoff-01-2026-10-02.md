# APPHEAR_FINGERSPELLING_BASELINE_EXECUTION_HANDOFF_01

2026-10-02. **Bounded TRAIN and DEV pipelines pass; resumable bulk preparation is ready for
the user to run locally.** Actual inventory is **22 TRAIN / 16 DEV**, with **1,242 pending**.
No bulk tranche run, optimizer step, trained checkpoint, TEST RGB access or Android change
occurred. Reflection remains the accepted research limitation; it was not reopened.

## 1. Preserved foundation — VERIFIED

Branch `codex/current-working-text-to-asl-baseline-2026-09-29`; HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358`.
Protected WORD baseline `76d93cecd85bf9f76064d320aa4a5791b5f0704a`.
The same pre-existing dirty/untracked work remains. No reset, branch switch, merge, discard,
staging or commit. Preservation evidence is under
`datasets/fingerspelling/foundation_01/execution_handoff_01/`.

| Frozen identity | SHA-256 |
|---|---|
| adapter Python | `256d8e82301fa9e6dd039a1c6d94dc5cc717b22c27e7b8bd9661ba32ee4394cd` |
| adapter config | `5ed7f766154b558ea2bebd095804ca788dc7ee5b91cc001ca96a40133edb9b67` |
| column order | `f3f5f93cd590111e60a1078c032ada7a756be72d633ff53900ae9a353f084fcb` |
| tranche manifest | `6b4f152c6bd51eae7af697a58c88c6e20cb0b5e537e272a1a84a897aec54ae6e` |

`[T,405]`, original sequence/CTC contracts, all 80 frozen batches, DEV phrase policy and
reflection policy are unchanged. Original 12 feature arrays/receipts remain byte-identical.
Protected Candidate01/preprocessing/raw-v1, Android/WORD/Context Assist assets and source
remain unchanged. Only new offline tooling/tests/config and append-only context notes change.

## 2. Bounded real TRAIN batch — VERIFIED

First pending frozen batch: TRAIN start 0, count 16, expected batch source bytes 85,179,632.
Six already-prepared clips reuse their original source/raw/features; **ten new clips** were
downloaded and extracted. No existing clip was re-extracted or replaced.

All 16 batch entries pass official size/MD5/SHA, frozen Candidate01 extraction lineage,
chronological raw-v1, adapter generation, receipt and sequence validation. The batch has
16 official TRAIN signers, 2,091 native frames / 431 genuine sparse-view frames. All 16
native and phone-view sequences satisfy the CTC minimum. These are structural diagnostics,
not recognition-accuracy results. New TRAIN acquisitions are DAUN; existing MacKenzie
evidence is retained in the actual package.

## 3. Bounded real DEV batch — VERIFIED

First frozen DEV batch: DEV start 0, count 16, expected source bytes 84,246,654.
**Sixteen new clips** completed official acquisition → integrity → frozen Candidate01 →
raw-v1 → adapter-v1 → feature receipt → validation. All are official DAUN validation/DEV;
15 governed DEV signers remain disjoint from TRAIN, and the frozen DEV/TEST phrase-exclusion
policy passes. No TEST RGB was acquired or opened.

2,070 native frames / 430 sparse-view frames; all 16 pass native and phone-view CTC bounds.
No frame-level character boundaries or new labels were invented.

All 26 new clips' actual decoded frame counts equal their container-reported frame counts.
Encoded resolution, FPS and rotation metadata are independently recorded in
`bounded_source_decode_properties.json`. Upright handling remains frozen; no horizontal flip.
Source integrity, raw/features hashes and per-sequence CTC/missing-hand evidence are in
`bounded_batch_results.json` and individual feature receipts.

## 4. Actual package after bounded work — VERIFIED

| Actual prepared inventory | TRAIN | DEV |
|---|---:|---:|
| sequences | 22 | 16 |
| official humans | 21 | 15 |
| DAUN / MacKenzie sequences | 16 / 6 | 16 / 0 |
| native frames | 3,447 | 2,070 |
| sparse phone-view frames | 713 | 430 |
| native CTC feasible / infeasible | 22 / 0 | 16 / 0 |
| phone CTC feasible / infeasible | 22 / 0 | 16 / 0 |
| J / Z / adjacent-repeat sequences | 12 / 3 / 10 | 14 / 2 / 6 |
| remaining target sequences | 1,002 | 240 |

A source-group/session does not create a new human. The combined TRAIN inventory has 21
official human IDs across 22 clips. Missing evidence stays masked; low-coverage clips are not
replaced, retargeted as OTHER or silently excluded. Complete class coverage is still pending.

## 5. Bugs and short preparation fixes

- The old downloader stopped permanently on interrupted `.download` files. The new flow
  preserves incomplete staging files under `recovery/` and restarts only the missing source.
  Original bytes are verified **before** publishing the final MP4; failed integrity checks
  never leave a bad download presented as a finalized original.
- An interrupted raw/receipt or feature/receipt write previously required manual cleanup.
  Staged writes and atomic JSON publication now allow recovery of uncommitted pairs; complete
  verified artifacts are reused unchanged. Interrupted files are preserved, not discarded.
  Corrupt completed artifacts stop preflight for inspection; they are not auto-overwritten.
- JSON report publication needed to create its parent directory. Fixed in the shared offline
  package I/O helper; the training entry-point check subsequently passed.
- Future new-video extraction now records container resolution/FPS/frame count and refuses a
  shorter decoded result when an expected frame count is available. All 26 bounded clips
  independently passed that equality check; their existing receipts were not rewritten.
- Disk space was initially insufficient (~3.18 GB free). The user agreed to free space;
  final preflight has sufficient room. No agent cleanup/deletion of existing data occurred.

No adapter geometry, masks, ordering, schema or Candidate01 threshold/model was changed.

## 6. Validator and engineering evidence

Full foundation validator: **0 structural errors**, 38 actual validated sequences, 1,242
pending. It verifies official roles/signers/phrase policy, duplicate source exclusion,
source → raw → features/receipts hashes, frozen models/preprocessing, adapter identity,
finite deterministic features, upstream masks, timestamps and per-view CTC statuses.
It correctly reports `ready_to_train=false` until the complete governed tranche exists.

Regression: **83 tests + 5 subtests passed**; Ruff and mypy passed; PowerShell
command-sheet parser reports 0 errors. Preservation checks verified 883 protected files, 1767 unchanged snapshot entries and original byte prefixes
for all three appended context/memory files. Review passes plan alignment, system integrity
and offline handoff readiness; production rollout is out of scope.

Regression evidence: `engineering_checks.json`, pytest logs and preservation report in
`execution_handoff_01/`. Tests cover interrupted download recovery, verify-before-publish,
atomic nested reports, explicit failures, serial resume without duplicate processing,
no Candidate01 initialization for completed features, disk guards, CTC decoder/edit counts
and the incomplete-dataset training refusal. Existing AZ/download/adapter tests remain active.
Ruff and mypy cover new/changed offline files. No production runtime test/build was needed.

## 7. Resumable serial preparation workflow

`tools/fingerspelling/tranche.py` adds `preflight`, `prepare-tranche`, `status`, `final-validate`.
`pipeline/config/fingerspelling_execution_v1.json` pins the exact manifest and adapter hashes.
`prepare-tranche` walks only the original 1,024 TRAIN / 256 DEV inventory and frozen batch IDs:

1. Full preflight: environment, frozen identities, current package, model/source hashes,
   destination writability and estimated remaining disk space.
2. Exclusive local writer lock; serial acquisition/extraction only. One frozen Candidate01
   instance is reused; no second camera or parallel perception execution.
3. Skip completed artifacts only after full validation; reuse valid existing source/raw.
   Download only absent, exact v13 manifest-listed sources. Up to three bounded network
   attempts; interruptions preserve staging bytes. No search, recursive download or TEST path.
4. Verify source before perception, build raw-v1 and receipts, generate unchanged native/sparse
   adapter features. No letter segmentation or final-dataset resampling.
5. Explicit per-source failures, progress and batch validation. Three consecutive failures
   stop the runner for review instead of repeatedly failing the entire corpus. Failed samples
   remain pending/in inventory; counts are never silently reduced.
6. Final full validation and summary; nonzero exit for incomplete/failed preparation.

Ctrl+C stops safely; rerun the identical command. Verified completed source/raw/features are
not restarted. Recovery is at **source granularity**: an interrupted incomplete source may be
redownloaded or re-extracted; individual network byte ranges/half-extracted frames are not
resumed. A complete raw/receipt pair is reused even when feature generation was interrupted.
Running two preparation writers concurrently is refused; `status` remains available separately.

Reports under `datasets/fingerspelling/foundation_01/execution/`:

- `preflight.json`: identities, environment, free/required space.
- `events.jsonl`: durable run/batch/source/retry/failure/interruption events.
- `progress.json`: last progress inventory.
- `failures.json`: explicit unresolved source errors.
- `final_summary.json`: actual counts, pending/failures and final validation.
- Root `validation.json` / `ctc_views.json`: full structural/readiness and view-feasibility results.

Fast status counts receipts and artifact presence; its output explicitly states that it is not
a fresh hash/recompute check. `final-validate` performs the full check and exits zero only when
the actual full package is ready. No command automatically launches training.

## 8. Exact PowerShell commands

Run from a normal local PowerShell terminal. No source edits or batch enumeration required.
Equivalent run sheet: `tools/fingerspelling/USER_RUN_01.ps1`; training is commented out there.

**A — preflight:**

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m tools.fingerspelling.tranche preflight
```

Stop if this returns nonzero. Preflight currently passes. The remaining RGB estimate is
8,403,978,625 bytes; estimated derived storage plus a 1-GiB reserve brings required free space
to ~10.18 GB. Recheck before launch; do not delete originals/raw for convenience.

**B — bulk preparation; rerun this same command to resume:**

```powershell
& .\.venv\Scripts\python.exe -u -m tools.fingerspelling.tranche prepare-tranche
```

**C — progress/status, including from another PowerShell window:**

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m tools.fingerspelling.tranche status
```

**D — complete-tranche validation after preparation finishes:**

```powershell
& .\.venv\Scripts\python.exe -m tools.fingerspelling.tranche final-validate
```

If Kaggle access/network fails, inspect the reported errors. This bounded run used the official
public per-file URLs without credentials. No permission/authentication bypass is implemented.

## 9. Exact success output

Bulk final summary must report:

```json
{
  "status": "TRANCHE_MATERIALIZED_READY_TO_TRAIN",
  "actual_counts": {"TRAIN": 1024, "DEV": 256},
  "pending": 0,
  "failures": {},
  "training_started": false
}
```

Nested validation must report `structural_errors=[]`, `structural_pass=true`,
`validated_sequences=1280`, `selected_sequences=1280`, `readiness_blockers=[]`,
`ready_to_train=true`. `final-validate` then exits zero. Both source strata and governed
signer/class coverage must pass; no count reduction or gate weakening.

Some native/phone views in the full tranche may legitimately fail the CTC length bound.
Their sources remain in inventory and their explicit feasibility lists remain visible.
Readiness checks eligible native character coverage; it does not pretend all sparse views
are feasible. No infeasible view enters CTC loss; later DEV decoding still evaluates all
sequences, and reports eligible-loss counts separately from greedy metrics.

Return `execution/final_summary.json`, `validation.json`, `ctc_views.json` and, if incomplete,
`execution/failures.json` plus the relevant tail of `execution/events.jsonl`. Stop for review
before training.

## 10. First-model entry point — IMPLEMENTED, UNTRAINED

`model/fingerspelling_ctc.py`, config `model/config/fingerspelling_ctc_baseline_01.json`:
one 193,116-parameter causal TCN, 64 channels, kernel 3, dilations 1/2/4/8, two convolutions per
residual block, per-timestep LayerNorm, dropout 0.1. Input `[T,405]` retains explicit evidence
masks; a separate batch-padding mask is applied in the model. No hand-missing timestep is
deleted. Output `[T,28]` logits with temporal stride 1; blank index 27, greedy CTC decoder.

Fixed first-run budget: seed 20261002, batch 8, 30 epochs, Adam 0.001, clip norm 5, CPU by
default. These are one engineering baseline, not architecture selection or an accuracy promise.
Native feasible TRAIN sequences fit; governed signer-disjoint DEV is decoded at native and
genuine phone sensitivity cadence, with all DEV sequences retained in metrics. No TEST,
language model, Gemini, horizontal augmentation or feature redesign.

Verified **forward-only** check on two real TRAIN and two real DEV sequences: finite CTC loss,
28-logit output, zero padded logits and causal prefix invariance. No optimizer was instantiated
by `--check`, no gradient/weight update or training checkpoint was run. Report:
`execution/training_entrypoint_check.json`. The model is still untrained; optimizer convergence,
full epoch execution and trained-checkpoint restore remain future user-run evidence.

The runner refuses training until full tranche validation is ready and exact frozen manifest
identity matches. Checkpoints include model/optimizer/epoch; rerunning the same command resumes
from `committed_epoch.json`. An interrupted epoch is repeated. Seed/config/data/code identities
must match; no bit-exact cross-process resume claim. Best candidates are immutable epoch files
selected by lowest **native DEV CER**, first tie. Checkpoint retention is bounded; epoch reports
and failure artifacts remain preserved.

Metrics: DEV micro CER with substitutions/deletions/insertions; exact-sequence accuracy;
per-signer metrics; J/Z-containing sequence metrics and aligned-character recall; repeated-letter
sequence metrics with sample counts and small-group caveats. Character edit alignment is
evaluation text alignment, **not video letter boundaries**. Greedy decode preserves repeated
letters separated by blank. See official [CTC loss](https://www.tensorflow.org/api_docs/python/tf/nn/ctc_loss)
and [decoder](https://www.tensorflow.org/api_docs/python/tf/nn/ctc_greedy_decoder) API semantics.

Artifacts: `run_identity.json` (config/seed/adapter/manifest/data/code hashes), `environment.json`,
`ctc_training_inventory.json`, `checkpoints/`, `committed_epoch.json`, `best_candidates/`,
`epochs/epoch_NNN.json` with predictions and metrics, `metrics.jsonl`, `completion.json` or
`failure.json`. No TFLite export or production integration is implemented.

## 11. Future user-run training command — SEPARATE, DO NOT RUN YET

After complete dataset validation and return/review of preparation reports:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_ctc --dataset 'datasets/fingerspelling/foundation_01' --run-dir 'runs/fingerspelling_ctc_baseline_01'
```

That exact command resumes an identity-matching committed epoch. No seed/config/view sweep
or automatic post-preparation training is performed. A stale/different run identity fails
explicitly rather than mixing experiments. To repeat only the short forward check:
`python -m model.fingerspelling_ctc --check` (still no training).

## 12. Genuine remaining work

Only the intentionally user-run 1,002 TRAIN + 240 DEV preparation and review of its reports
remain before a first training experiment. Disk preflight presently passes but must be checked
again at launch. Network/disk/integrity failures, if encountered, will be explicit bounded
operational issues, not reasons to redesign the frozen adapter or relax governance.
Later phone-domain accuracy, Android adapter parity, inference cadence and runtime integration
remain future gates; they do not prevent this offline data-preparation handoff.

FINGERSPELLING_DATA_PREPARATION_USER_RUN_READY
