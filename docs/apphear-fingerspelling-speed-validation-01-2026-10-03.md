# AppHear fingerspelling execution optimization 01

2026-10-03: separate optimized execution tooling is prepared and bounded parity passes.
**Keep the current first baseline running unchanged.** No optimized epoch, optimizer update,
checkpoint migration, new dataset or Android/WORD change was executed by this work.

## Scope and implementation

User approved the safest option: finish the original reference run while validating a
separate runner. Plan: `docs/apphear-fingerspelling-speed-plan-01.md`.
Branch `codex/current-working-text-to-asl-baseline-2026-09-29`; HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358` remains unchanged.

- `model/fingerspelling_fast_execution.py`: immutable hash/schema-checked feature cache;
  dynamic-signature `tf.function` loss/gradient/update/inference; batched DEV with true
  lengths and sequence-weighted eligible CTC loss.
- `model/fingerspelling_ctc_fast.py`: separate opt-in orchestration, reusing the original
  model builder/config/metrics. Records optimized execution and reference code hashes,
  timings for fitting, each DEV view, reports/checkpoints and each complete epoch.
- `tools/fingerspelling/check_fast_execution.py`: bounded gradients-only parity/speed check.
- `tests/test_fingerspelling_fast_execution.py`: cache immutability/hash/schema/role guards,
  repeated-target retention and refusal to write the named reference run directory.

Architecture, `[T,405]`, native TRAIN policy, batch size 8, seed, shuffle order, Adam/LR,
gradient clipping, dropout, 2 CPU threads, evaluation every epoch, 28 logits, greedy decoder,
best-native-DEV-CER selection, splits and reflection policy are unchanged. No GPU migration,
mixed precision, length bucketing, subsampling, dropped features or less frequent evaluation.
Expected full float-array cache is approximately 424 MB plus targets/metadata/batches and
TensorFlow memory. Cache is lazy: one file decompression per sequence, both views retained.

The optimized runner has its own identity; it refuses the original named output directory.
Any other existing run also requires exact identity match. Original checkpoints are only
copied read-only for the diagnostic; no migration or bypass of resume guards is implemented.
The orchestration mirrors the original loop; reference architecture and metrics are imported,
not recreated. Future changes to either loop need corresponding contract/review checks.

## Bounded validation — VERIFIED

Evidence: `artifacts/fingerspelling_speed_01/check.json`.
Two real TRAIN examples and sixteen governed DEV examples, deliberately including both
CTC-infeasible phone DEV views. Frozen-manifest hash and bounded feature hashes verified;
this did not rerun the entire 1,280-sequence validator.

- Cached TRAIN features, targets, lengths and padding were array-identical to reference.
- Compiled/eager inference agreed at atol/rtol 1e-5; padded logits remained zero.
- Loss/gradient agreement at atol/rtol 1e-4 with dropout disabled. Maximum absolute gradient
  difference was 4.375e-5. Dropout-enabled gradients and loss were finite.
- Native and phone batched evaluation gave **identical text, edit counts and metrics** to
  scalar reference evaluation. Eligible CTC mean loss agreed within 1e-4 tolerance.
- Native loss included 16/16 DEV examples; phone loss included 14/16. Both infeasible phone
  views remained in decoded sequence/character metrics, unchanged.
- Epoch-3 checkpoint snapshot restored model weights, Adam variables/iteration and epoch
  into matching objects; second restoration was array-identical. No weight/optimizer updates
  occurred. The actual compiled optimizer graph traced without execution.

Latest bounded timings while the original trainer was running:

| DEV view, 16 sequences | Scalar reference | Cached/batched | Ratio |
|---|---:|---:|---:|
| native | 10.139 s | 2.002 s | 5.07x |
| phone | 2.967 s | 0.440 s | 6.74x |

Initial inference graph tracing took 0.606 s. This is a small warm microbenchmark with
concurrent CPU activity, not a whole-epoch speed claim or measured training-step speedup.
Tracing, initial cache filling and full CTC backpropagation still have costs.

Nineteen safety/regression tests passed in 2.46 s. Two unrelated slow local-package/disk
checks were intentionally deselected. Ruff passed; mypy passed three files with imported
modules skipped. Black CLI twice stalled after rewriting target files; recover classified
an isolated formatter issue (CLI root cause UNKNOWN). Targeted Black API formatting with
AST-equivalence checks completed. No dependency/environment replacement was made.

An old incomplete-dataset guard test would become unsafe after the real tranche completed.
It now mocks an explicitly incomplete validator result; it cannot accidentally call training.
No frozen trainer behavior was changed to fix that test.

## Preservation and review

Original trainer/metrics/config/adapter/tranche hashes match their pre-work snapshot, and
original trainer/metrics match the active run identity. Context changes are append-only.
Protected-path audit is recorded in `artifacts/fingerspelling_speed_01/preservation.json`.
The original user-run training continued and was at epoch 4 at the final check; its evolving
checkpoints/metrics are not classified as agent modifications. No TEST data was loaded.

Review: plan alignment PASS; protected-system integrity PASS; bounded optimization gate PASS.
No critical/important issues identified for this isolated preparation handoff. **Full optimized
epoch/update/checkpoint-resume execution and final training quality remain untested.**
The current baseline is the fallback and quality reference. A compiled stochastic step may
change rounding/dropout draws; neither bit-exact trajectories nor equal eventual CER are
promised by these bounded checks.

## Commands and next action

**Now:** let the current original command finish. Return its completion and DEV metrics.
Do not switch it to the new module or copy its run identity into another directory.

To repeat only the bounded no-update diagnostic (not needed now):

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -u -m tools.fingerspelling.check_fast_execution
```

Future separate optimized training command, **only after review and authorization for that
run**; do not launch it alongside this first baseline:

```powershell
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_ctc_fast --dataset 'datasets/fingerspelling/foundation_01' --run-dir 'runs/fingerspelling_ctc_fast_01'
```

That command starts an independent run; it does not import the original checkpoint.
Rerunning it resumes only its own identity-matching completed epochs. No long operation was
executed here. Once a future run is authorized, stage timers will establish actual speed and
the ordinary full held-out DEV metrics will show training behavior.

OPTIMIZED_EXECUTION_BOUNDED_VALIDATION_PASSED
