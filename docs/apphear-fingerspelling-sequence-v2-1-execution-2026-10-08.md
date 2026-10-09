# AppHear Fingerspell V2.1 — local-letter correction execution record

## Active execution

One authorized hidden controller (PID6260) was started at2026-10-07T16:18:27Z.
Last verified stage: `WAITING_FOR_CURRENT_FULL_PREFLIGHT`; fitting has not started
yet at this checkpoint. It waits for preflight PID20352, verifies a full PASS,
then performs the one training run and post-lock final evaluation. Do not launch
the manual wrapper while this controller is active. Status is in
`artifacts/fingerspelling_sequence_v2_1_gate_01/user_run_status.json`; controller
identity in `controller_process.json`. Subsequent actual stage is authoritative.

## Scope and implementation decision

One training-only correction to the existing V2 graph. No new architecture family,
visual input, dataset, decoder setting, Android change or WORD change.
Full quality decision is pending the one authorized run and post-lock evaluation.
The three requested final outcome states must not be inferred from the smoke gate.

Initialize the shared graph from frozen V2 epoch046, SHA256
`88a92131eb07ce97b18f2ad4b9ea8d927858c1582177b5a04105a361e071c96a`.
Use fresh Adam with the original V2 fixed LR0.001, clipnorm5 and original seeds.
This preserves learned V2 context rather than throwing it away and fitting a new
encoder from scratch. No optimizer/LR/lambda sweep was conducted.

## Exact architecture delta

- Main graph: unchanged symmetric masked TCN64/kernel3, eight residual blocks,
  dilations1/2/4/8/16/32/64/128, RF1021, stride1,292956 parameters.
- Local tap after block4 (`v2_block3_mask`), RF61 observations (30 before/30 after).
- Dense64→27 plus time mask: **1755 additional training parameters**.
- Local vocabulary A–Z plus blank26; no SPACE output. Remove only SPACE tokens
  from authoritative valid target positions; repeated letters remain intact.
- Training graph294711 parameters, output dictionary `main`28/`local`27 logits.
- Main-only inference view292956 parameters, `[B,T,405]+mask->[B,T,28]`, exact
  original V2 layer topology. Auxiliary head absent from inference-only Keras files.
- Loss = mean mainCTC + **0.5**×mean localCTC. Lambda retained unchanged because
  both objectives were finite, received useful gradients and could overfit together.
  No numerical normalization or class-specific weighting was introduced.

The61-observation head is shorter-context than the full graph, not a per-letter
temporal classifier. No letter timing or pseudo boundary is created.

## Engineering evidence — TRAIN only, not recognition accuracy

Same six-sequence/six-signer tiny subset as the V2 gate: both source strata, J/Z,
repeats, SPACE, short/long transcripts and existing missing evidence. Exact IDs,
receipts and metadata: `artifacts/fingerspelling_sequence_v2_1_gate_01/tiny_subset.json`.

| Check | Observed result |
|---|---|
| Main CTC |28.9508→0.01641|
| Local letters CTC |164.4418→0.51267|
| Total loss |111.1717→0.27275|
| Tiny native exact decoding |6/6 main and6/6 local after175 updates|
| Main/local head gradient norms initially |16.8738/70.3422, finite and nonzero|
| Shared initial total gradient norm |155.7532, finite/nonzero|
| Warm-start normal logits vs exact V2 checkpoint |0 error|
| Padding difference, both heads |max5.7220e-6; padded logits zero|
| Inference-only reload vs compiled main logits |max6.6757e-6|
| Local dependence on blocks5–8 |none: perturbing their weights leaves local logits exact|
| Local receptive support |gradient zero outside61-observation window, nonzero within|
| Training-loop/resume |pause epoch2, exact model/Adam restore, complete epoch4|
| Temporal regimes |all four; deterministic raw robustness, retained real timesteps/fallback|
| Focused/regression tests |59 passed|
| Ruff / mypy |pass /6 modules pass|
| Protected inventory |1598 files, zero changed|
| DEV/TEST inference in engineering |none|

Only an engineering validator summation assertion needed1e-15 tolerance for
floating-point order of addition; trainer selection semantics were unchanged.
The formatter CLI stalled, so the installed Black library was used directly.
Pyreadline emitted a console-finalizer warning after pytest exit0; no tests failed.

## Frozen full-run contract

Existing4096 TRAIN,256 DEV-A, same Adapter.v1, same receipts/raw/cadence/missingness.
No video download, extraction or data expansion. Current full cached-data preflight
checks source/raw/feature integrity and recomputed Adapter values; this can be quiet
while reading files. No DEV-B feature access in training or checkpoint selection.

Selection = equal mean of native-full, phone-full, native-no-SPACE and phone-no-SPACE
DEV-A **uncalibrated main-head greedy** CER, preserving the old framework's raw
greedy selection semantics. No-SPACE reference and prediction are re-aligned after
removing spaces; the local head is never used for selection or final decoding.
First strict minimum/first tie; max90/min30/patience15/anchor improvement0.002.

Final decoder: unchanged beam10, blank27, penalty0.5, Top-1. No tuning.
Selected best checkpoint is saved as main-only Keras plus a separate dual-head
training file; resumable TensorFlow checkpoint includes both heads and fresh Adam.
Code/config/receipt identity mismatches reject resume. An interrupted epoch repeats.
Confirmation lock prohibits further fitting.

## Execution and exact commands

Separate run: `F:\ASL DATASET\5. Apphear3\runs\fingerspelling_sequence_v2_1_01`.
Sources/features remain in their existing F:/I: governed packages.

The wrapper runs/resumes training and then automatically runs final evaluation
after successful completion. It does not export, install or promote a model.
Only start it if no instance is already active:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\tools\fingerspelling\run_sequence_v2_1.ps1
```

Status/log commands (safe while training):

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m model.fingerspelling_sequence_v2_1 status
Get-Content -LiteralPath '.\artifacts\fingerspelling_sequence_v2_1_gate_01\full_run_console.log' -Tail 12
```

If training stopped, rerun the wrapper identically; it resumes verified committed
state. If only evaluation stopped after the confirmation lock, rerun:

```powershell
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_sequence_v2_1 evaluate
```

Do not start a concurrent writer. No new Project Lead approval is required for
this one authorized run, but a final supported/limit/mixed decision still requires
the actual saved evaluation, not the engineering results above.

## Post-lock evaluation / review criteria

Compare against exact epoch038 and V2 epoch046 on DEV-A and DEV-B, normal native/
phone and the identical frozen moderate/heavy/contiguous missingness views.
Output full/no-SPACE CER, S/D/I, correct aligned letters and SPACE separately,
precision, output/reference ratio, exact strings, every signer, every letter and
J/Z/repeat groups. Pooled phone single-word membership must match the same42 IDs
in the completed V2 review. Report original-alignment letter recall separately
from spaces-removed text re-alignment.

Uniform important safeguard: for each letter with≥100 pooled phone references,
flag recall regression>10 absolute percentage points versus epoch038. No S-specific
training or correction. DEV-B is post-lock only, shares15 DEV-A signers and is
already opened historically; not a new independent population test. TEST sealed.

A lower full CER alone is insufficient. Review letter/no-SPACE/single-word gains,
substitution burden, broad signer effect and retained missingness robustness.
If local supervision fails to improve letters materially, stop geometry-only
encoder experiments; no automatic V2.2/V3 or appearance experiment.

## Files created / operational records

- `model/config/fingerspelling_sequence_v2_1_01.json`
- `model/fingerspelling_sequence_v2_1_encoder.py`
- `model/fingerspelling_sequence_v2_1_execution.py`
- `model/fingerspelling_sequence_v2_1.py`
- `model/fingerspelling_sequence_v2_1_review.py`
- `tools/fingerspelling/sequence_v2_1_smoke.py`
- `tools/fingerspelling/sequence_v2_1_validate.py`
- `tools/fingerspelling/run_sequence_v2_1.ps1`
- `tests/test_fingerspelling_sequence_v2_1.py`
- `context/fingerspelling-sequence-v2-1.md`
- this report and separate V2.1 gate/smoke artifacts.

Component imprint/state records appended to `context/feature-schema.md`,
`context/progress-tracker.md`, `memory.md`. Original V2 source/run/config/checkpoint,
epoch038 and rollback packages preserved. Android, WORD, Candidate01, Adapter.v1,
Context Assist and installed model untouched. No Android/TFLite export in this phase.


## Latest verified execution update

The full source/raw/recomputed-feature preflight passed4096TRAIN/256DEV-A with
original data-lineage SHA6c605dced521599ce561582d03e9e52fcd6b01324021a14c1772ca6d1f37a0ce.
The initial waiting controller6260 declined before fitting; its record is retained
in `controller_attempt_01.json`. After directly verifying the completed PASS, the
one training command was started through controller19780 at2026-10-07T16:21:35Z.
Last stage is `TRAINING`; this includes the trainer's entry integrity checks.
No full epoch/checkpoint/held-out V2.1 quality result is claimed at this point.
The controller automatically evaluates after training completes and locks.
Do not run the manual command while this job is active. Read current status first.
