# Fingerspell Sequence Encoder V2 — architecture and smoke gate

Date: 2026-10-07. Scope: isolated fingerspelling research, architecture/engineering gate only.
No full 4K V2 run, acquisition, Candidate01 extraction, Android deployment, or TEST inference.

## Decision

One symmetric masked TCN is ready for a separately started governed training run. It can
learn the tiny engineering subset, preserves the input/output contract, and exports with
exact decoded-text parity. **Held-out recognition improvement remains untested.**
Epoch038 remains installed and is the rollback/reference candidate. No new model was promoted.

## Repository and preservation

- Research branch: `codex/current-working-text-to-asl-baseline-2026-09-29`.
- Research HEAD: `cc1f3949114d0ed1dab38d4428191151b37df358`.
- Authoritative application: `C:/Users/Gigabyte/.codex/worktrees/fingerspell-oct04-integration/5. Apphear3`.
- Application HEAD: `cee71d9f181695847936eb5f3605ea37eab82a95`, the requested October4 baseline.
- Both checkouts already contain dirty/untracked work. Existing application changes include
  its activity/analyzer/build configuration and isolated fingerspelling integration. None
  was edited by this task. No reset, branch switch, merge, or cleanup was performed.
- All **1,594** inventoried protected files matched before/after SHA-256. Inventory covers
  both Android source/assets, perception, Adapter, previous training/decoder/export code,
  model references and existing deployment evidence. It does not claim a new hash of every
  corpus RGB byte; the previous governed source lineage remains authoritative and full-run
  preflight revalidates source/raw/features.
- Existing epoch038 Keras SHA remains
  `b037e32789f523c043b46c32cdc2ea11f2f600fd35f30ecd672604b6f6947886`.
- Existing Android FP32 model SHA remains
  `38d36c8be71a0217defc63b6614f05c6491fdba618d0fffb02aceea8df4f01ff`.

Evidence: `artifacts/fingerspelling_sequence_v2_gate_01/preservation_before.json`,
`preservation_after.json`, and research working-tree snapshot. Application status was read
with optional Git locks disabled because its checkout is outside the sandbox write root.

## Inspection and implementation plan

Required operational context and recognition-upgrade records were consulted. The user
explicitly authorized choosing and implementing this architecture gate; no additional
architecture approval or unrelated WORD experiment was inferred from older planning records.

| Responsibility | Existing authoritative component reused/inspected |
|---|---|
| Epoch038 construction/reference | `model/fingerspelling_ctc.py:build_model`; epoch038 Keras checkpoint |
| 4K governance, training, resume, selection | `model/fingerspelling_train4096.py`; `pipeline/fingerspelling/expanded_training.py` |
| CTC loss and finite checks | `model/fingerspelling_ctc.py:ctc_loss`; `CompiledSteps` |
| Caching/variable-length batches | `model/fingerspelling_fast_execution.py`; `model/fingerspelling_temporal_execution.py` |
| Real-observation temporal selection | `pipeline/fingerspelling/temporal_views.py`; frozen Adapter `phone_indices` |
| Raw schema and failure semantics | `pipeline/perception_vnext/recognition_schema.py`; `offline_candidate01.py` (read-only) |
| Frozen feature derivation | `pipeline/fingerspelling/adapter.py`; Adapter config/column hashes |
| Selection/final metrics | `model/fingerspelling_emission.py`; `model/fingerspelling_metrics.py`; existing 4K `score` |
| Beam/blank adjustment | `model/fingerspelling_prefix_beam.py` |
| FP32 conversion/inference helper | `tools/fingerspelling/android_export.py:convert/invoke`; current geometry exporter inspected, not run/changed |

Terminology: **padding** is not an observation; **missing hand** is a real observation with
withdrawn/absent evidence; **full-sequence** here means non-causal inference after Done, with
a specified finite symmetric receptive field; **tiny overfit** is engineering evidence,
not held-out accuracy; **ready** means ready to train, not ready to deploy V2.

Plan: inspect TRAIN/phone evidence → choose one non-causal convolution design → add separate
raw robustness views → tiny learnability/mask/resume gate → builtin FP32 parity → freeze
training contract and commands. No family/width/backbone/decoder sweep was performed.

## Chosen architecture

| Property | Current epoch038 | V2 |
|---|---|---|
| Encoder | causal TCN | symmetric masked TCN |
| Channels/kernel | 64 / 3 | 64 / 3 |
| Residual blocks | 4, two convolutions each | 8, two convolutions each |
| Dilations | 1,2,4,8 | 1,2,4,8,16,32,64,128 |
| Parameters | 193,116 | **292,956** |
| Receptive field | 61 observations, past only | **1,021**, up to 510 past + 510 future |
| Time stride | 1 | 1 |
| Input | `[B,T,405]` + `[B,T,1]` | unchanged |
| Output | `[B,T,28]` | unchanged |

This expands context without widening the channels or changing geometry. Eight blocks cost
about 1.52× the old parameter count. Symmetric odd-kernel SAME convolution permits variable T,
uses the existing convolution/operator family, and avoids recurrent TensorList/Flex/custom
operator requirements. It is appropriate for the existing Start→Done bounded session.

The field spans the full deployed 512-observation bound from every valid timestep. For
longer research sequences, it is finite context, not global attention: far endpoints can
be beyond 510 positions of one another. TRAIN native lengths are 31–631 (median181), with
only seven above512; phone views are7–126 (median36). Nothing is truncated to512 in training.
No learned temporal state or future information is needed by Candidate01/Adapter.

Mask input, each convolution's normalized/activated/dropout output, each residual sum, and
the head. LayerNorm operates on channels at each timestep, not across time. This avoids
biased intermediate values at padded positions leaking back into valid non-causal outputs.
Real hand-missing observations retain time-valid=1. Decoder/CTC use actual lengths and
never decode batch-padding logits. Valid padded-input logit difference was at most
`4.76837158203125e-6`; padded logits were zero and valid decoded strings unchanged.
Removing future observations changed earlier outputs, confirming non-causal behavior.

## Missingness evidence and policy

The read-only audit covered all4096 TRAIN raw mask arrays, 117 signers, 2048/2048 strata.
Every audited raw hash matched its frozen receipt. No DEV performance or TEST data was used.

| TRAIN evidence | Native | Phone-like |
|---|---:|---:|
| Observations | 742,306 | 151,901 |
| Median any-hand observed fraction | 69.42% | 67.80% |
| p25–p75 per-sequence observed fraction | 56.91–80.22% | 55.69–79.59% |
| Entirely hand-unobserved sequences | 21 | 41 |

There are6,137 internal phone-view missing-hand runs: median1 observation, p75=2,
p90=4, p95=5, max29. All runs including lead-in/release have median3 and p95=10.
The phone's retained aggregate diagnostics show22/71 and21/51 hand-observed frames in
two sessions. They confirm incomplete evidence but contain no per-observation mask stream;
they cannot establish population rates, slot-loss proportions, or live missing-run distributions.

Separate policy `apphear.fingerspelling.raw_evidence_robustness.v1`:

| Profile | Maximum additional withdrawn observed slots | Candidate contiguous span |
|---|---:|---:|
| Training/moderate stress | 20% of originally observed slots | 1–3 selected observations |
| Heavy stress only | 40% | 1–5 |
| Contiguous stress only | 20% | 2–3 |

These are fixed synthetic budgets, not fitted phone dropout rates. Spans are observation-based
at actual selected cadence (roughly0.16–0.48s at nominalphone rate for1–3 observations; actual
timestamps remain authoritative). Budgets scale with evidence actually present, so poor
sequences are not forced to lose a fixed fraction of every timestep. No evidence is invented
for the21/41 completely missing cases; no corpus sequence is silently dropped.

An independent deterministic choice masks one slot or both (50/50), without assuming two
slots mean two physical hands. Another choice distinguishes proposal-present/refiner loss
from lost proposal (50/50). These mixture weights are explicit experimental defaults, not
measured frequencies. Seeds bind version, seed, sampleID, epoch and profile; transcripts and
model outputs do not choose positions. The audit retains removed frame/slot positions and hashes.

Withdraw accepted geometry by clearing observed/joint-valid and setting invalid XY toNaN.
For a retained proposal, synthetic rejected refiner confidence is0. For no proposal, presence
isNaN/unavailable, ROI isNaN, proposal-present false, support0. Original surviving XY, body,
timestamps/frame indices remain exact. Frozen Adapter produces finite zero/masked invalid
geometry and recomputes motion validity across affected neighbors. No feature columns are
blindly zeroed after derivation; no interpolation, forward filling, flips or timestep deletion.

TRAIN schedule rotates each sample through native/intermediate/phone/phone_robust once in
four epochs using a sample/seed offset. Infeasible phone views fall back to intermediate then
native, keeping every target. Robustness still applies to the chosen denser real observations.
68 TRAIN phone views are structurally infeasible; with the two DEV-A cases, the existing
TRAIN+DEV-A inventory has70. No fabricated observations are used to repair them.

## Frozen stress views

All256 DEV-A inputs validated, three masks each =768 deterministic stress records.
No stress model performance was scored or used for tuning. DEV-B features were not opened.

| DEV-A input | Mean sequence any-hand fraction | CTC-infeasible sequences retained |
|---|---:|---:|
| Normal phone | 62.38% | 2 |
| Moderate | 52.71% | 2 |
| Contiguous | 52.60% | 2 |
| Heavy | 41.72% | 2 |

`dev_a_stress_manifest.json` retains positions, raw identity, selected-frame lineage,
adapter identity, profile, mask hashes, and derived-feature hash. It changes no original
DEV array or timestamp. Its final SHA is recorded in `execution_validation.json`.

## Tiny engineering gate

Deterministic metadata selection: six official TRAIN sequences, six signers, three per
stratum, all with some original missing evidence. Shortest qualifying native duration per
category bounds engineering time; it is deliberately not a performance sample. There are
five distinct transcripts, one repeated across two independent signers.

| Signer | Stratum | Transcript | Native T | Coverage |
|---|---|---|---:|---|
| f9ea | DAUN | JOSIE LYONS | 61 | J |
| d478 | MacKenzie | ZERO IN ON THE FACTS | 61 | Z |
| bc24 | DAUN | DONNELL CURRY | 61 | repeated NN/RR |
| d3ab | MacKenzie | TOSS THE BALL AROUND | 91 | SPACE/repeats |
| d8ef | DAUN | PIZZERIA | 61 | short8/repeatedZZ |
| 812c | MacKenzie | ZERO IN ON THE FACTS | 91 | longer20 characters |

Tiny-overfit gate uses a fixed native batch and one optimizer/config, no DEV selection.
The longer20-character example is longer than the short example; it is not claimed to be
in the historical >20-character length bucket. Threshold locked in config: all6 decoded
TRAIN strings exact and meanCTC<1, maximum1000 updates/600s; stop on pass.

- Initial meanCTC350.642334; final0.0204397 after125 updates.
- Initial finite global gradient norm1349.45984; finite loss/gradients throughout.
- All6 native TRAIN strings exact. Learnability loop reached pass in13.76s; whole initial
  post-start smoke including export/parity took about21.45s, excluding process startup.
- Geometry masks/padding, repeated-symbol blanks, SPACE, native equivalence and deterministic
  withdrawal verified. Sparse target infeasibility remains explicit, not counted as success.
- Separate four-epoch TRAIN-only execution smoke exercised six instances of every regime,
  eight feasible denser fallbacks, checkpoints and exact model/Adam/epoch restoration.
- TRAIN engineering proxy loss decreased275.8877→137.8253 over four rotating-view updates;
  its CER is **not** a held-out performance result and does not select the architecture.

## FP32 export and runtime feasibility

Smoke checkpoint: `runs/fingerspelling_sequence_v2_01_smoke/smoke.keras`.
SHA: `6af91160c6e8b564e5c7800a08ebe49da3319ae2f12520e70cae3123b0e3e6ec`.
This is a tiny-overfit smoke model, not an accuracy or Android candidate.

FP32 export: `artifacts/fingerspelling_sequence_v2_gate_01/smoke_sequence_v2_fp32.tflite`.
SHA: `3c38d191a9183d5e4839824609ac1bd9b301915d2e522dbde7afaf2dcbef33c1`.
Size:1,298,800 bytes. Variable signatures `[1,-1,405]`, `[1,-1,1]` → `[1,-1,28]`.
No quantization or Flex/custom operators. All20 operator name/version pairs are already
present in the deployed epoch038 graph (including SPACE/BATCH transforms v3; other ops v1).
The same installed Android TFLite runtime has therefore already executed those requirements.
No architecture fallback was necessary.

Finalized-policy Keras/TFLite parity:30 cases (six×native/phone/three stress profiles),
all greedy and fixed-beam strings exact; max absolute logit error`9.5367431640625e-6`.
Additional dynamic-T checks at1,17,51,128,512 pass, including short inputs below the largest
dilation. Beam receives unchanged `[T,28]`, blank27, penalty0.5 once, width10, Top1.

Host CPU2 warm inference p50/p95 is recorded perT in `execution_validation.json`; around
0.5ms at51 observations and2–3ms at512. It excludes allocation and is **not Xiaomi timing**.
V2 itself was not installed or profiled on Xiaomi. Operator viability is established; actual
V2 phone numerical/latency/memory checks remain the later export/device gate after useful
held-out training. No GPU delegate or real-time per-frame V2 inference is assumed.

## Future full-run contract — not executed

- Opt-in separate module/model/run; installed epoch038 stays authoritative.
- Exact4096 TRAIN/256 DEV-A, frozen manifests/117 TRAIN and15 DEV signers, no new data.
- Adapter v1 config/implementation/columns unchanged; source/raw/feature receipts rechecked.
- Fresh initialization/Adam because the convolution structure/context changed. LR0.001,
  clipnorm5/dropout0.1/batch8/CPU2, seed20261007. No optimizer schedule or LR sweep.
  Contrast: old4K warm-started B2 at0.0003. This supporting change is explicit, and eventual
  gains cannot be attributed to future context alone.
- Maximum90/minimum30 epochs, patience15, minimum patience-anchor improvement0.002.
- Epoch selection remains mean **uncalibrated raw-greedy** native/phone DEV-A CER, first tie,
  matching previous training selection. Stress/DEV-B/blank tuning cannot select checkpoints.
- Final-only beam10/penalty0.5 comparison against exact epoch038, normal and three stress
  views; error composition, correct characters, precision, per-character recall, exact
  strings, signer spread and J/Z/repeats retained. Infeasible stress views still decoded,
  excluded only from undefined CTC loss with IDs retained.
- DEV-B opens only after immutable completion/checkpoint/decoder lock. Further train refuses
  locked runs. DEV-B shares DEV-A's humans and was opened before; it is post-lock confirmation,
  not an untouched independent signer population. TEST remains sealed.
- Resume exact model/optimizer at committed epoch; interrupted epoch repeats. No bit-exact
  dropout continuation promise. Mismatched code/config/data identities are refused.

Full quality decision must compare against epoch038 DEV-A42.75%/46.98% and
DEV-B41.88%/46.24% native/phone. Lower CER alone or extra emitted characters is insufficient.
The present smoke does not establish that V2 improves discrimination or missingness robustness.

Proposed PowerShell commands, **for a later explicitly started full run**:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_sequence_v2 preflight
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_sequence_v2 train
```

Preflight performs full source→raw→Adapter lineage validation; allow it time to read the
cached corpus before training output appears. It does not acquire or extract new files.
Success: `V2_PREFLIGHT_PASS`, TRAIN4096/DEV256. Default additions stay
`I:\AppHearData\FSboard_TRAIN4096_01`; existing foundation staysF:.

Resume: rerun the identical `train` command. Status and locked final evaluation:

```powershell
& .\.venv\Scripts\python.exe -m model.fingerspelling_sequence_v2 status
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_sequence_v2 evaluate
```

Expected run: `F:\ASL DATASET\5. Apphear3\runs\fingerspelling_sequence_v2_01\`.
Writes run_identity/environment, epochs with augmentation choices and mask hashes,
progress, checkpoints, best_candidates, committed_epoch/resume verification, completion,
failures if any, confirmation_lock, dev_a_final/dev_b_final and final_evaluation.json.
No run exists there yet; only distinctly suffixed smoke directories were used.

## Files created and operational records updated

New implementation:

- `model/config/fingerspelling_sequence_v2_01.json`
- `model/fingerspelling_sequence_v2_encoder.py`
- `model/fingerspelling_sequence_v2_execution.py`
- `model/fingerspelling_sequence_v2.py`
- `pipeline/fingerspelling/evidence_robustness.py`
- `tools/fingerspelling/sequence_v2_evidence.py`
- `tools/fingerspelling/sequence_v2_smoke.py`
- `tools/fingerspelling/sequence_v2_validate.py`
- `tests/test_fingerspelling_sequence_v2.py`

New report: this file. New evidence: `artifacts/fingerspelling_sequence_v2_gate_01/`.
New smoke runs: `_smoke`, `_smoke_execution`, `_smoke_execution_checked`,
`_smoke_execution_final`; earlier engineering iterations preserved. No old run overwritten.
Appended operational records: `context/feature-schema.md`, `context/progress-tracker.md`,
`memory.md`. No previous trainer/exporter, Android, Candidate01 or Adapter file changed.

## Validation, corrections and review

-84 focused/new/legacy governance, temporal, feature and prefix-beam tests passed with a
  workspace temporary directory; finalized robustness test file also passed7/7 after correction.
- Ruff passes; mypy passes7 new implementation/helper modules with explicit package bases.
- Synthetic test receipt initially omitted schema identity; fixture corrected, production
  schema validation preserved. No-proposal presence masking corrected to Candidate01's
  unavailable convention; finalized stress inputs/parity and resume smoke rerun.
- Sandbox temporary-folder rename denial affected existing fixture setup; reran in a new
  workspace temp directory. No protected I/O code changed. Black CLI worker startup stalled;
  recover classified isolated tooling trouble and direct serial formatter completed. The
  harmless existing pyreadline console cleanup warning can follow a passing pytest exit0.
- Review: plan alignmentPASS, system boundariesPASS, engineering gatePASS. Critical0,
  important0; deferred quality/device measurements remain explicitly outside this gate.
- Frozen Adapter native/phone math untouched; new raw-derived training/stress views are a
  research-only input policy, not a train/serve feature-schema version change. No additional
  Android Adapter implementation or phone attempt was required.

FINGERSPELL_V2_ARCHITECTURE_READY_FOR_4K_TRAINING
