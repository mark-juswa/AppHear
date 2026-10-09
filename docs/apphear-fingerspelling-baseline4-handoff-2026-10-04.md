# AppHear Fingerspelling Baseline 4 — capacity gate and execution handoff

**BASELINE4_USER_RUN_READY.** The controlled capacity gate passed; the complete dataset preflight and engineering smoke passed. Full Baseline-4 training has **not** started. The larger TCN fits the fixed TRAIN subset substantially better, supporting one full experiment. Held-out generalization and phone recognition remain untested for this model.

## Preserved starting state

- Branch: `codex/current-working-text-to-asl-baseline-2026-09-29`.
- HEAD: `cc1f3949114d0ed1dab38d4428191151b37df358`.
- Protected WORD ref: `baseline/apphear-s2-r2-integration-complete-2026-09-26`, SHA `76d93cecd85bf9f76064d320aa4a5791b5f0704a`.
- Existing dirty context/memory/root readiness report, untracked fingerspelling code/configs/data/docs/runs and historical phone evidence were preserved. Starting inventory: `artifacts/fingerspelling_baseline4/git_start.txt`.
- Hash comparison: **1,265 pre-existing protected/research files unchanged**, including old B1/B2/B3 code/configs/runs and the frozen tranche manifest. The historical 883-file protected WORD/Candidate01 snapshot also matches. No reset, branch switch, merge, staging, deletion or runtime modification.
- Tranche SHA: `6b4f152c6bd51eae7af697a58c88c6e20cb0b5e537e272a1a84a897aec54ae6e`. Complete 1,024 TRAIN / 256 DEV; official signer separation and DEV phrase exclusion remain unchanged. TEST sealed; no RGB acquisition or Candidate01 execution.
- Adapter v1 width405: implementation `256d8e82301fa9e6dd039a1c6d94dc5cc717b22c27e7b8bd9661ba32ee4394cd`, config `5ed7f766154b558ea2bebd095804ca788dc7ee5b91cc001ca96a40133edb9b67`, columns `f3f5f93cd590111e60a1078c032ada7a756be72d633ff53900ae9a353f084fcb`.
- B4 config SHA: `eb38927d42ca682f785138d07bbc27612fe52c9753e6258d0fa104ef4f547df6`. Full source/raw/feature lineage digest: `a330c41c7e9b57f4be201ac7c8f281164a0cc3e73f9ba1578e06c2213a7a130d`.

## Architecture decision

The B2 encoder uses four residual blocks, each two causal kernel-3 convolutions with dilations1/2/4/8, LayerNorm/ReLU/dropout0.1, first-block residual projection and a28-logit head. Receptive field is `1 + 2*(3-1)*(1+2+4+8) = 61` observations. The first temporal convolution maps405 input columns to64 hidden channels; no separate input embedding exists.

One candidate doubles width to128 throughout. Temporal depth, dilation layout and receptive field stay unchanged, isolating capacity from history length. The61-observation context spans approximately2seconds at30Hz and9.6seconds at6.23Hz; actual selected timestamps govern each view. This already covers considerable causal motion history, so depth expansion was deferred.

| Parameter block | B2 width64 | B4 width128 |
|---|---:|---:|
| First 405-input temporal convolution | 77,824 | 155,648 |
| Remaining seven temporal convolutions | 86,464 | 344,960 |
| First residual projection | 25,984 | 51,968 |
| Eight LayerNorm layers | 1,024 | 2,048 |
| Character head | 1,820 | 3,612 |
| Total | **193,116** | **558,236** |

B4 has2.89× parameters, approximately2.23MB FP32 parameter bytes and555,008 convolution/dense MACs per output observation before normalization/nonlinearity overhead. It remains a moderate causal stride1 TCN using the same operations. TFLite conversion, streaming buffers, activation memory and phone p50/p95 latency are future gates; these estimates do not certify device deployment.

All supporting training choices stay B2: seed20261002, batch8, Adam0.001, clipnorm5, dropout0.1, original CTC loss/targets and real native/intermediate/phone views with nearest-denser feasible fallback. No new observations, feature columns, input canonicalization, language priors or decoder heuristics. Reflection remains `USE_RELEASED_PIXELS_AS_IS` with historical attribution explicitly limited.

## Fixed fit-capacity gate

Plan was written before training: `docs/apphear-fingerspelling-baseline4-plan-2026-10-04.md`. Exact historical64 TRAIN diagnostic IDs were reused (32DAUN/32MacKenzie,42 unique official signers,1,134 reference characters); manifest SHA `fff5c54beac8ad14940eb48d7626f75eec1d45c76ca4d5b7612020a3b6015dd9`.

Both architectures started fresh and received60 subset epochs/480 updates each. Seed, sample order, per-source requested/actual cadence/fallback and update counts match at every epoch, verified by recorded hashes. No DEV selection/calibration. Decision required at both45 and60: ≥5percentage-point balanced TRAIN CER reduction, each view's CER lower, and aligned correct/reference fraction higher. This is a fit-effect rule, not a production threshold.

| Gate epoch | Control balanced CER | Wider balanced CER | Improvement |
|---|---:|---:|---:|
| 45 | 90.61% | 51.32% | 39.29points |
| 60 | 75.97% | 34.88% | 41.09points |

Final raw decoding:

| Arm / view | CER | Substitutions | Deletions | Insertions | Exact strings | Correct/reference characters |
|---|---:|---:|---:|---:|---:|---:|
| Control native | 82.01% | 66 | 863 | 1 | 0/64 | 18.08% |
| Wider native | 46.83% | 64 | 459 | 8 | 0/64 | 53.88% |
| Control phone view | 69.93% | 96 | 695 | 2 | 0/64 | 30.25% |
| Wider phone view | 22.93% | 44 | 204 | 12 | 5/64 | 78.13% |

Per-character recall improved for25 of26 represented characters in native view (one tied) and all26 in phone view; none worsened. Full character confusion/recall tables, predictions, exact strings, loss/headroom and convergence reports are retained. Final training loss: control43.162, candidate22.516. Gate update/checkpoint/scheduled-evaluation time:126.17seconds control,148.47seconds candidate; initialization/zero-epoch evaluation/registration and resume-probe time are additional.

**Interpretation:** strong evidence supporting the chosen capacity intervention. This does not show that the full1,024-source training distribution will fit as well, or that DEV will improve. These fresh repeated-subset runs differ from the completed B2 full-tranche checkpoint; compare them directly to their equal-update control, not as a fair superiority claim over the completed B2 model. Initialization tensors differ with shape; one seed and a fixed42-signer subset do not establish a universal capacity law.

The control resumed after epoch1 in a fresh process with exact model/Adam/epoch restoration; random/dropout continuation is not claimed bit-exact. An earlier one-epoch engineering probe was retained separately after a typing-only correction; its updates are excluded from the paired comparison. No numerical feature/perception correction or optimization sweep occurred.

Evidence: `artifacts/fingerspelling_baseline4/fit_gate.json`, `fit_summary.json`, and `runs/fingerspelling_ctc_baseline_04_fit_gate/{control,candidate}/`. Keep these admission artifacts immutable during the full run.

## Completed engineering validation

- Candidate causal-prefix equality; padded input leaves valid outputs within1e-5 and padded logits zero; finite loss and every gradient; output `[B,T,28]`; correct parameter count.
- Existing temporal tests cover real observation selection, native equivalence, selected dt/motion recomputation, missingness, deterministic cadence rotation, CTC fallback and calibration. Cached/compiled execution tests also pass. **23 distinct relevant tests passed** across the capacity, temporal and compiled suites; new module strict typing checks pass.
- Full foundation validator:1,280/1,280 actual artifacts, no structural errors/readiness blockers, source/raw/feature lineage valid, official roles unchanged. `artifacts/fingerspelling_baseline4/preflight.json` records current identities.
- Three-update smoke:8TRAIN/8DEV, native/phone bit-exact adapter parity and intermediate raw rederivation verified on all16. All three regimes requested8times each, one genuine sparse→denser fallback, no negative training headroom, no lost sources.
- Separate-process pause/resume after update1 and second restoration after update2: model weights, Adam state/iterations, committed epoch and patience state verified. Resume history retained; interrupted epochs repeat, stochastic continuation need not match an uninterrupted run bit-for-bit.
- Native/phone DEV and TRAIN diagnostic reports, per-character metrics, best model save/restore, final evaluation, bounded calibration, progress/completion and identities all function. Smoke is engineering-only, not a recognition result.
- 883 protected historical files and1,265 pre-existing research/protected files unchanged. No TEST access or Android/Candidate01/WORD/Context Assist modification.

## Full-run policy and isolation

`model/fingerspelling_baseline4.py` reuses B2 data/cache, temporal selection, compiled updates, CTC, metrics, stopping and calibration. An isolated epoch/commit orchestrator is derived from the B2 runner to preserve the historical implementation; its changes are the width-selected builder, B4 identities and additional TRAIN/character diagnostics. No second feature implementation exists.

Full B4 starts **fresh**, not from either fit-gate checkpoint. Same1,024TRAIN/256DEV, same frozen policy: balanced raw native/phone DEV CER, first tie retained, max90epochs, min30, patience15, minimum-improvement0.002. TRAIN64 diagnostics are reported each epoch but never select checkpoints. Existing bounded blank calibration occurs only after checkpoint selection on DEV. TEST remains sealed.

Best model, model/Adam/epoch/patience checkpoint state and current code/config/data identities are checked on resume. Single-writer guard prevents two trainers in the same run. Old B1/B2/B3 and gate directories are refused. A matching passed capacity gate and engineering smoke are mandatory for full training.

## Exact PowerShell commands

Use the project environment. Preflight performs full hash validation and may take a few minutes. Run each stage only after the preceding command succeeds.

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m model.fingerspelling_baseline4 preflight
```

Expected `BASELINE4_PREFLIGHT_PASS`, TRAIN1024/DEV256 and405-column adapter.

Full training (user-run):

```powershell
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_baseline4 train
```

Resume after interruption: rerun **the identical training command**. Completed epochs restore; an incomplete epoch repeats. Do not edit code/config/data or rerun the capacity gate during an active full run. Full-training directory: `F:\ASL DATASET\5. Apphear3\runs\fingerspelling_ctc_baseline_04`. It is currently unstarted.

Progress from another PowerShell terminal:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m model.fingerspelling_baseline4 status
```

After training reports `BASELINE4_TRAINING_COMPLETE`:

```powershell
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_baseline4 evaluate
```

Expected `BASELINE4_FINAL_EVALUATED`, best epoch, raw/calibrated combined CER and the report path. Return that JSON and `final_evaluation.json` for results review. Do not infer success from training loss alone.

Outputs beneath the full-run directory:

- `run_identity.json`, `environment.json`: configuration, seed, feature/data/code identities, model size.
- `epochs/epoch_NNN.json`: TRAIN loss/64-source diagnostic, full DEV native/sparse CER, S/D/I, exact strings, output ratio, empty/blank diagnostics, per-character recall/confusions, signer/J/Z/repeat/length-stratum metrics and source-level cadence/fallback choices.
- `progress.json`, `completion.json`, `failure.json` when applicable: live status, early stopping, explicit errors.
- `checkpoints/`, `committed_epoch.json`, `resume_history.jsonl`, `resume_verification.json`: resumable state.
- `best_candidates/`, `final_evaluation.json`, `decoder_calibration.json`: selected checkpoint, B2 comparison and final diagnostics/calibration.

Do not extrapolate full-runtime duration from the fit subset or tiny smoke: full sequence lengths, cache warmup and256DEV evaluation dominate. The full job is deliberately delegated; no long training was executed in this session.

## Review and next decision

Plan alignment, system boundaries and offline engineering readiness: PASS; no critical/important findings. Type annotations were corrected before the relevant run identities were frozen; no perception/feature/loss bug was discovered. Production readiness is deliberately deferred: no export, streaming runtime, device latency or end-to-end phone accuracy evidence exists for B4.

Next action is exactly one full user-run B4 experiment. Compare TRAIN64 and held-out DEV native/sparse against B2, edits/recalls/exacts and signer distribution together. If TRAIN and DEV improve, consider later governed diversity expansion; if only TRAIN improves, generalization becomes the problem; if full TRAIN remains poor, return to information/optimization evidence rather than scaling the TCN again. No follow-on experiment or integration starts automatically.

BASELINE4_USER_RUN_READY
