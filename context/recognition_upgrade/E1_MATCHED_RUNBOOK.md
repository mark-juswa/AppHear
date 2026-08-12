# E1 Matched TCN-versus-GCN Runbook

## Purpose

Provide the exact, resumable procedure for the three-seed full-vocabulary comparison that decides
whether the corrected GCN or the TCN becomes the landmark branch for the hybrid pilot.

## Scope

Offline training and held-out evaluation only. No Android, dataset, feature-schema, production
asset, confirmation, or UI change is authorized by this runbook.

## Current Status

**Prepared and preflight-passed; full training not started.** Last updated: 2026-07-25.

## Source of Truth

- Configs: `model/config/recognition_upgrade/e1_matched/{tcn,gcn}_seed{0,1,2}.yaml`
- Trainer/resume: `model/train_streaming.py`
- Evaluation: `eval/streaming.py`
- Preflight/evaluate/summary: `model/experiments/e1_matched.py`
- Frozen hashes and checks: `artifacts/recognition_upgrade/e1_matched/preflight.json`
- Gates: `EXPERIMENT_MATRIX.md` and `EVALUATION_AND_ACCEPTANCE_GATES.md`

## Related Context Files

`README.md`, `CURRENT_PIPELINE_AUDIT.md`, `MODEL_RESEARCH_PLAN.md`, `EXPERIMENT_MATRIX.md`,
`EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent
`../encoder-upgrade.md` and `../progress-tracker.md`.

## Architecture Decisions

- Both candidates train fresh on identical data; no warm start may advantage one architecture.
- Seeds 0/1/2 and output directories are fixed before training.
- Resume is explicit and checkpoint-safe; fresh commands cannot overwrite evidence.
- Native, k4, and k8 reports are separate and include provenance.
- Production Android and model assets remain untouched regardless of outcome.

## Verified Preflight

- Six unique fresh output directories; no warm starts and no existing outputs.
- Same FPS-expanded train/validation tensors for both architectures.
- 13,236 training clips, 3,264 validation clips, and 236 classes.
- 35 train signers, 5 validation signers, and 11 held-out test signers; no signer overlap.
- Native, k4, and k8 test sets each contain the same 2,620 held-out clips.
- TCN contract: `[B,96,258] -> [B,96,236]`, 169,004 parameters.
- GCN contract: `[B,96,258] -> [B,96,236]`, 2,751,078 parameters.

## Environment Gate

From the project root, run:

```powershell
python -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))"
```

Do not begin GCN training if the result is `[]`. Current native-Windows TensorFlow 2.21 reports no
GPU. Use a GPU-capable Linux/WSL2 environment or another approved machine. The relative config
paths work from the repository root on Windows or a mounted copy with the same sibling layout.

Reserve at least 2 GB free for checkpoints and reports. Run one job at a time on a single GPU.

## Re-run Preflight

```powershell
python -m model.experiments.e1_matched preflight --build-models
```

Require `status: preflight_passed`, all six `output_exists: false` before the first run, and a
non-empty GPU list from the environment gate.

## One-Epoch Runtime Benchmark

Run only GCN seed 0 first:

```powershell
python -m model.train_streaming --config model/config/recognition_upgrade/e1_matched/gcn_seed0.yaml --epochs 1
```

Record epoch wall time, peak GPU memory, and GPU utilization. Stop and review if one epoch is
impractically slow, the process uses CPU, memory is exhausted, loss is non-finite, or checkpoints
are missing. Do not alter one seed's batch size independently.

## Full Training

Continue benchmarked GCN seed 0 to the configured total of 60 epochs:

```powershell
python -m model.train_streaming --config model/config/recognition_upgrade/e1_matched/gcn_seed0.yaml --epochs 60 --resume
```

Then run the remaining fresh jobs sequentially:

```powershell
python -m model.train_streaming --config model/config/recognition_upgrade/e1_matched/tcn_seed0.yaml
python -m model.train_streaming --config model/config/recognition_upgrade/e1_matched/tcn_seed1.yaml
python -m model.train_streaming --config model/config/recognition_upgrade/e1_matched/tcn_seed2.yaml
python -m model.train_streaming --config model/config/recognition_upgrade/e1_matched/gcn_seed1.yaml
python -m model.train_streaming --config model/config/recognition_upgrade/e1_matched/gcn_seed2.yaml
```

If interrupted, rerun that exact command with `--resume`. Never use `--resume` for a different
config. A fresh command refuses to overwrite an existing `history.csv`, `latest.keras`, or
`best.keras`. Resume loads `latest.keras`, validates the tensor contract, and appends history.

## Evaluation

After each seed has `best.keras`, run its three conditions using the matching config:

```powershell
python -m model.experiments.e1_matched evaluate --config model/config/recognition_upgrade/e1_matched/tcn_seed0.yaml
```

Repeat for `tcn_seed1`, `tcn_seed2`, `gcn_seed0`, `gcn_seed1`, and `gcn_seed2`. Each command writes
separate `eval_native_test.json`, `eval_k4_test.json`, and `eval_k8_test.json` files, including
model/config/feature provenance. Existing reports are not reused.

Then aggregate:

```powershell
python -m model.experiments.e1_matched summarize
```

## Decision Gates

The GCN advances only if all are true:

- Three-seed mean native top-1 is at least 5 percentage points above matched fresh TCN.
- Three-seed mean k8 top-1 is at least 3 percentage points above matched fresh TCN.
- GCN mean native top-1 is at least 0.66 and k8 top-1 is at least 0.56.
- No severe signer or confusion-group regression.
- Results are finite, reproducible, signer-independent, and supported by saved provenance.

The generated summary's `provisional_gate_pass` covers only the two relative mean gates. A manual
per-class/signer review is still mandatory.

## Outcome

- **Pass:** select corrected GCN as the landmark candidate and proceed to E2 hand-crop quality.
- **Fail:** stop GCN work, select the matched TCN landmark branch, and still proceed to E2/E3.

## Assumptions

- Commands run from the repository root.
- Dataset files and hashes remain equal to `preflight.json`.
- One GPU job runs at a time.

## Risks

- GPU environment may not support the installed TensorFlow build.
- Full GCN may remain too slow or run out of memory.
- Clip-level GCN supervision may underperform causal per-frame TCN despite the capacity pass.
- Mean gains may hide signer or class regressions.

## Open Questions

- Which GPU/machine will run the benchmark?
- What epoch time and peak GPU memory does GCN seed 0 report?

## Next Required Action

Select the GPU environment and run only the environment gate, preflight, and one-epoch GCN seed-0
benchmark. Report those results before launching the other five jobs.
## Host Environment Check - 2026-07-25

- WSL2 is installed with Ubuntu as the default distribution.
- Windows reports only `AMD Radeon(TM) Graphics`; `nvidia-smi` is unavailable.
- TensorFlow 2.21 under native Windows reports no GPU devices.
- Decision: do not run the full GCN or its benchmark on this host. Use another compatible GPU
  machine or a cloud GPU while preserving the repository/dataset sibling layout and frozen hashes.

## CPU Benchmark Result - 2026-07-25

- The environment gate failed: TensorFlow 2.21 reported no GPU devices (`[]`).
- The matched preflight passed with the frozen datasets, signer splits, schema, and configurations.
- A one-epoch `gcn_seed0` CPU benchmark nevertheless completed in 3,505 seconds (58 minutes
  25 seconds): 13,236 training clips, 3,264 validation clips, 236 classes, and 2,751,078
  parameters.
- Epoch-0 metrics were `pf_acc=0.0096943` and `val_pf_acc=0.0068280`. These near-random initial
  values are not an accuracy result and do not support an architecture decision.
- `best.keras`, `latest.keras`, and `final.keras` were written. `latest.keras` reloads with the
  expected `[None,96,258] -> [None,96,236]` contract, AdamW optimizer, and 207 optimizer
  iterations, confirming that checkpoint/resume works.
- Decision: classify this directory as CPU benchmark evidence only. Do not resume it on this host
  and do not combine its first CPU epoch with a GPU run used for the matched comparison.
- Estimated worst-case cost at the observed rate is about 58.4 hours for one 60-epoch GCN seed and
  about 7.3 days for three GCN seeds, excluding evaluation and the three TCN jobs.
- Before a fresh GPU seed-0 run, preserve the existing output directory under a clearly named CPU
  benchmark archive. Do not delete or overwrite it. The archive/move requires explicit approval.

## Revised Next Required Action

Select a compatible NVIDIA/CUDA or managed cloud GPU environment. Preserve the CPU benchmark,
re-run the environment gate and preflight there, then run a fresh one-epoch GCN seed-0 benchmark.
Do not launch full matched training until its GPU epoch time, memory use, and expected cost have
been reviewed.

## RTX 3050 Handoff Package - 2026-07-25

- Prepared `classmate_e1_matched_rtx3050_package/` as a separate, self-contained E1 handoff.
- The package includes the frozen train/validation/native/k4/k8 NPZ tensors and vocabulary with a
  SHA-256 manifest; no extraction or raw-video preprocessing is required on the classmate machine.
- Normal execution requires Ubuntu/WSL2 or Linux and fails when TensorFlow cannot see CUDA. Native
  Windows and silent CPU fallback are prohibited.
- RTX 3050 4 GB settings: mixed float16 with float32 probabilities, GCN micro-batch 4 x accumulation
  16, TCN micro-batch 16 x accumulation 4, effective batch 64, one data worker, prefetch 1, and GPU
  memory growth.
- One command runs preflight, smoke, six resumable training jobs, 18 evaluations, and summary.
  All artifacts remain under the package `outputs/` directory.
- Local CPU validation passed compilation, tests, checksums, signer-disjoint preflight, both model
  builds, full-GCN batch-4 forward/train step, checkpoint reload, evaluation aggregation, resume
  serialization, and WSL shell syntax. No real training was started.
- Approval remains conditional: the classmate must run `./VERIFY_SETUP.sh`; full training is a
  no-go unless CUDA is visible and the full-GCN 4 GB smoke test passes.
