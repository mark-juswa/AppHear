# APPHEAR_FINGERSPELLING_BASELINE_02_EXECUTION_HANDOFF

2026-10-04. Cadence-aware CTC and emission robustness. Ready for the user's single full
Baseline-2 run; the agent ran only diagnostic inference and a bounded engineering smoke.

## Preserved state

Branch `codex/current-working-text-to-asl-baseline-2026-09-29`;
HEAD `cc1f3949114d0ed1dab38d4428191151b37df358`.
Protected WORD baseline `baseline/apphear-s2-r2-integration-complete-2026-09-26` at
`76d93cecd85bf9f76064d320aa4a5791b5f0704a`.
The existing tracked changes to the readiness report, feature schema, progress tracker and
memory, and all existing untracked datasets/tools/reports/phone pulls were preserved.
No reset, merge, branch change, staging or commit. Start inventory is
`artifacts/fingerspelling_baseline2/git_status_before.txt`.

Before documentation append, 70 foundation/Baseline-1 files matched their start hashes;
all 883 protected-file hashes matched the retained protection snapshot. Candidate01,
raw-v1, `[T,405]`, manifests, official roles, DEV exclusion policy, existing raw/features,
Baseline-1 trainers/models and Android/WORD/Context Assist are unchanged. Full package
validation was rerun; its derived validation report was refreshed. No RGB download,
Candidate01 extraction, TEST payload access, device change, language model or architecture sweep.

Frozen dataset is 1,024 TRAIN /256 DEV; 117 TRAIN /15 DEV signers, disjoint. TRAIN contains
512 DAUN /512 MacKenzie; the selected DEV is DAUN. Both strata are represented in training;
this tranche does not establish held-out MacKenzie performance. TEST remains sealed.

## Baseline-1 emission diagnosis

Selection was fixed from metadata before inference: eight TRAIN examples, four from each
stratum and different signers; 17 DEV examples covering all 15 DEV signers plus the two
structurally impossible sparse examples. IDs and checkpoint hash were written to
`artifacts/fingerspelling_baseline2/diagnostic_manifest.json` before inference.

| Fixed subset | Blank argmax | Predicted/reference characters | CER |
|---|---:|---:|---:|
| TRAIN native, 8 | 87.33% | 58.74% | 44.76% |
| TRAIN sparse, 8 | 94.24% | 9.79% | 91.61% |
| DEV native, 17 | 92.68% | 41.38% | 63.79% |
| DEV sparse, 17 | 96.61% | 6.90% | 95.26% |

These are sequence diagnostics, including TRAIN diagnostics, not cross-signer phone accuracy.
Blanks are normal in CTC; the combination of sparse blank dominance and extreme output-length
deficit supports testing emission calibration. It does not establish the cause of cadence loss.

Full 256-DEV restored inference exactly reproduced Baseline-1 saved CER. The predetermined
penalties `{0, 0.5, 1, 1.5, 2}` were evaluated on cached logits, without training or extra
inference per penalty. A penalty subtracts from blank logit index 27 before greedy collapse.

| Baseline-1 DEV diagnostic | No penalty | Selected penalty 1.5 |
|---|---:|---:|
| Native CER | 60.83% | 55.02% |
| Sparse CER | 94.68% | 87.39% |
| Mean native/sparse CER | 77.76% | 71.20% |
| Native deletions /insertions | 1,716 /21 | 662 /318 |
| Sparse deletions /insertions | 3,210 /0 | 2,729 /1 |
| Sparse predicted characters | 247 | 729 |
| Sparse empty predictions | 106 | 24 |

Calibration improves emission but increases native insertions and leaves severe sparse error.
Penalty 2 failed the frozen insertion safeguard. This is a DEV-tuned symptom test, not
production improvement or independent TEST evidence. The B1 penalty is not hard-coded into
B2: the same range and acceptance policy are frozen now; one B2-specific value is selected
after uncalibrated best-checkpoint selection. Detailed evidence:
`artifacts/fingerspelling_baseline2/baseline1_diagnosis.json`.

## Temporal View Layer and input parity

`pipeline/fingerspelling/temporal_views.py` defines
`apphear.fingerspelling.temporal_views.v1`. Input is pinned chronological Candidate01 raw-v1;
output is strictly increasing indices of real observations. It imports no model code.

Three regimes are native, an intermediate 12-Hz minimum-gap gate, and the existing
6.231166-Hz phone-rate minimum-gap gate. First observation is retained; subsequent observations
are the first actual frame at least one requested period after the last selected frame.
No interpolation, duplicate frames, mirroring or forward fill. On ~30-Hz data the effective
selected rates are quantized and often lower than the nominal requested rate. This preserves
the Baseline-1 phone comparison and approximates sparse delivery; it does not simulate
CameraX jitter, dropped-frame selection or measured live hand-tracking accuracy.

For each TRAIN source, a sample-ID/seed SHA-256 offset plus epoch modulo three chooses the
requested regime. Each source requests each regime exactly once per three epochs; it enters
one optimizer batch per epoch. Views are cached in RAM, without making new corpus copies.

`model/fingerspelling_temporal_execution.py` extends the existing verified feature cache.
Intermediate views are selected from raw and then passed through the original adapter.
Native/phone stored arrays are reused only after their schema/adapter/hash checks; raw receipt
and raw lineage are checked on temporal registration. The smoke recomputed all three views
and verified bit-exact native/phone equality with stored data for all 16 smoke sources.

The frozen adapter recomputes `dt` and wrist displacement from selected neighbors, honors its
existing motion-gap rule, retains both potentially overlapping hand slots and all embedded
missingness masks, and requires no full-body observation. Padding uses a separate time mask.
No columns, normalization constants, feature width or JVM reference implementation changed.
This phase establishes offline temporal parity; installed Android integration/parity remains
a later gate.

CTC requires `T >= transcript length + adjacent-repeat count`; encoder stride remains one.
An infeasible requested sparse regime falls back to the nearest denser feasible real view
(phone -> intermediate -> native), retaining the source and target. Every choice records the
requested/actual regime, fallback, selected-index hashes, frame count, effective cadence and
headroom. Native impossibility refuses training. The complete corpus has 1,280 feasible native
views; 19 TRAIN and two DEV phone views are infeasible. DEV decoding retains all 256 examples;
only the 254 feasible phone examples enter sparse CTC loss. Impossible sources are not hidden.

## Frozen training and selection policy

Policy: `model/config/fingerspelling_ctc_baseline_02.json`, SHA-256
`b3dddb294823f04ef28d975d7e98791c35de50a290463b8ee81bf349b1a2f602`.
Plan was written before diagnostic inference:
`docs/apphear-fingerspelling-baseline2-plan-2026-10-04.md`.

`model/fingerspelling_baseline2.py` is opt-in orchestration of the existing encoder, feature
cache, compiled updates and text metrics, not a new encoder family. Preserving B1's pinned
source files avoids breaking its checkpoint identity/resumability. The encoder is unchanged:
193,116 parameters, causal dilations 1/2/4/8, channels 64, 28 logits, dropout 0.1, Adam 0.001,
clip norm 5, batch 8, CPU threads 2. B2 starts from the original random initialization seed
20261002, rather than fine-tuning B1. Reflection policy stays `USE_RELEASED_PIXELS_AS_IS`.

Checkpoint selection is the **mean of uncalibrated native and sparse DEV CER**, with the first
checkpoint retained on an exact tie. Both scores and all predictions remain visible.
Maximum 90 epochs; no early stop before epoch 30; stop after 15 epochs without a meaningful
0.002 decrease from the patience anchor. Exact best-checkpoint selection and patience-anchor
updates are distinct. These settings were frozen before any B2 optimizer update.

Emission calibration is DEV-only, after choosing the raw best checkpoint. Nonzero penalty
requires combined CER improvement >=0.005, lower mean deletion rate, native CER increase
<=0.02 and mean insertion-rate increase <=0.05. Choose lowest combined CER, smallest penalty
on ties; otherwise zero. No calibrated score changes checkpoint selection or training loss.

Each epoch reports native/sparse CER, substitutions/deletions/insertions, exact-sequence count,
predicted/reference ratio, empty predictions, blank/nonblank argmax fractions, mean blank
posterior, average decoded length, eligible CTC loss, headroom and infeasible IDs. Signer,
J/Z/repetition and transcript-length strata accompany the aggregate. Subgroup sample counts
are retained; insufficient counts are marked. Padding timesteps never enter diagnostics.

Comparison limitation: B2 has a longer permitted training budget and different selection
criterion than B1, so improvement cannot be attributed exclusively to cadence sampling.
Raw and calibrated results must be compared separately. Sparse failure alone will not prove
irrecoverable perception information loss; learning and discrimination must still be checked.

## Validation and smoke evidence

- 46 focused new/foundation/cache tests passed; lint and four-module strict type checks passed.
- Full source/raw/features/official-metadata validator and environment preflight passed:
  1,280/1,280 actual sequences, no structural errors/readiness blockers, adapter unchanged.
- Smoke: eight TRAIN /eight DEV, three epochs, exactly three optimizer updates. Each TRAIN
  sample requested all three regimes: eight native/eight intermediate/eight phone total.
  One requested phone view fell back; all training views were CTC-feasible.
- Finite gradients/loss, fixed native/sparse DEV evaluation, best checkpoint serialization and
  final bounded calibration/evaluation passed. All native/phone arrays matched adapter
  recomputation exactly; intermediate was recomputed from raw.
- Paused after epoch one; restored weights, Adam iterations/state, epoch and patience state,
  then completed epochs two/three. A separate Python process restored epoch three with an
  identical committed model/optimizer digest and zero extra updates. Interrupted epochs are
  repeated from the last committed epoch; bit-exact stochastic continuation is not claimed.
- Smoke output is `runs/fingerspelling_ctc_baseline2_smoke_01`; it cannot be resumed as full
  training because its sample identity and smoke mode differ. Smoke CER is engineering only.
- Full `runs/fingerspelling_ctc_baseline_02` status is **started=false**.

Evidence is under `artifacts/fingerspelling_baseline2/`: `smoke.json`,
`fresh_process_resume.json`, `preflight.json`, `validation_checks.json`,
`preservation_before.json`, `preservation_after.json` and the diagnostic files above.

## Exact user-run PowerShell commands

Run from the AppHear repository. Do not launch two trainers against the same run directory.
These commands do not download or extract videos, and never train on TEST.

Environment/data preflight (checks actual source/raw/features integrity and can take longer
than a simple Python import check):

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_baseline2 preflight
if ($LASTEXITCODE -ne 0) { throw 'Baseline-2 preflight failed; do not start training.' }
```

One full training run (also runs preflight and checks matching engineering-smoke identities):

```powershell
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_baseline2 train
```

Resume after interruption: **rerun the identical command**. It restores the last committed
epoch, Adam and early-stop state and repeats only an interrupted uncommitted epoch:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_baseline2 train
```

Read progress from another PowerShell window:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m model.fingerspelling_baseline2 status
```

After `BASELINE2_TRAINING_COMPLETE`, evaluate the selected checkpoint and freeze its one
DEV-calibrated global blank penalty:

```powershell
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_baseline2 evaluate
```

No source edits, batch enumeration, config changes or data preparation are required. Do not
reuse either Baseline-1 run directory. The default run is
`F:\ASL DATASET\5. Apphear3\runs\fingerspelling_ctc_baseline_02`.

## Expected outputs and next review

Preflight prints `BASELINE2_PREFLIGHT_PASS`, TRAIN 1024, DEV 256, native feasible 1280,
phone-infeasible TRAIN 19 /DEV 2. Training prints epoch, both CERs, combined/best CER,
patience, timings, requested-view counts and fallback count. First epoch includes raw/cache
initialization costs; full-run speed is not yet measured. Training stops at the frozen early
stop or maximum, rather than promising convergence at a particular epoch.

The run writes:

- `run_identity.json`: seed, configs, code/data/adapter/diagnostic hashes and sample IDs.
- `environment.json`: TensorFlow/Keras, CPU configuration, parameter count and resume scope.
- `epochs/epoch_NNN.json`: losses, full diagnostics, fixed DEV predictions and view choices.
- `progress.json`: most recent committed epoch summary.
- `checkpoints/` and `committed_epoch.json`: epoch-level model/Adam and selection/patience state.
- `best_candidates/epoch_NNN.keras`: exact selected best model with recorded SHA-256.
- `completion.json`: `BASELINE2_TRAINING_COMPLETE`, best epoch, score/hash, stop reason.
- `resume_verification.json` on resume, and `failure.json` if an operation fails. Historical
  failure files are retained; completion/current progress indicate recovery.
- After evaluate: `final_evaluation.json` with raw and every bounded calibration candidate,
  and `decoder_calibration.json` with the chosen penalty bound to checkpoint/policy hashes.

Return `completion.json`, `final_evaluation.json` and `decoder_calibration.json` after the run,
or `failure.json` on error. Review raw native/sparse CER and deletion/empty/length metrics
against B1, then calibrated scores with insertion safeguards. Inspect signer and subgroup
counts, not just the mean selection score. No production promotion is implied. Rollback is
simply using the preserved B1 artifacts; no runtime was installed or modified.

## Review and remaining limits

Project review: plan alignment PASS; architecture/data integrity PASS; offline user-run
readiness PASS. Critical/important/minor implementation findings: 0/0/0. Production
readiness is deliberately **not claimed**: no full B2 result or on-phone alphabet evaluation,
no installed adapter/ABC mode, and the established reflection attribution limitation remains.
No demonstrated correctness issue required changing the 405-column contract. No preparation
blocker remains; full training/evaluation is intentionally handed to the user.

FINGERSPELLING_BASELINE2_USER_RUN_READY
