# APPHEAR_FINGERSPELLING_QUALITY_GATED_RESIDUAL_VISUAL_01

The quality-gated residual experiment is implemented and engineering-validated.
**Full visual materialization and full adapter training have not been run.**
B2 remains the best completed research recognizer. This task establishes a reliable
user-run experiment, not an accuracy improvement.

## Preserved state

Branch `codex/current-working-text-to-asl-baseline-2026-09-29`, HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358`.
WORD baseline `baseline/apphear-s2-r2-integration-complete-2026-09-26` at
`76d93cecd85bf9f76064d320aa4a5791b5f0704a`.
Existing dirty context/memory/readiness-report changes and untracked datasets/runs/tools
were preserved. No reset, switch, merge or staging. Preservation check compares2,057
pre-existing files, including previous visual artifacts and B1–B4 model/code evidence.
See `artifacts/fingerspelling_residual_visual_01/preservation_after.json`.

Frozen manifest SHA `6b4f152c6bd51eae7af697a58c88c6e20cb0b5e537e272a1a84a897aec54ae6e`.
Geometry remains actual1,024TRAIN/256DEV, 117TRAIN/15DEV signers, Adapter.v1 `[T,405]`.
All1,280 local RGB sources exist; no acquisition, Candidate01 inference or TEST RGB access.
The user superseded the failed naive-fusion gate with this single residual experiment.
The old failed gate and every checkpoint remain intact.

## Crop reliability evidence

Current-frame deterministic quality uses accepted refiner, presence, joint/support
coverage, source intersection and joint containment. Appearance-only obvious-duplicate
suppression leaves geometry untouched. Exact rules/bit meanings/ordering are in
`context/fingerspelling-residual-visual-v1.md` and the pinned config.

Audit81 existing sequences /13,792 frames; old proposal-only path had24,218 valid slot
crops, including10,401 refiner-rejected crops. New filter retains9,063 slot crops after
suppressing1,318 duplicate slot observations. No refiner-rejected slot contributes.

| Audited group | Frames | Any retained crop | Retained slots | Duplicate frames |
|---|---:|---:|---:|---:|
| TRAIN DAUN | 4,593 | 2,291 (49.88%) | 2,693 | 463 |
| TRAIN MacKenzie | 6,782 | 4,272 (62.99%) | 5,149 | 672 |
| DEV DAUN | 2,417 | 1,074 (44.44%) | 1,221 | 183 |

Twelve retained examples span4 independent signers each in TRAIN DAUN, TRAIN MacKenzie
and DEV, selected across sequence reliability rather than only the highest quality.
All12 visibly contain a real hand. Nine further examples cover duplicate slots,
refiner-rejected proposals and low-coverage clips. Contact sheets and individual source
identities are in `artifacts/fingerspelling_residual_visual_01/crop_audit/` and
`crop_audit.json`. Codex visually inspected these sheets; this is not a human annotation
campaign or a population false-positive estimate. Some face/arm/background context and
blur remain even in hand-containing crops. Some usable hands are rejected. DEV retained
coverage is lower than audited TRAIN; the full preparation report exposes this by group.
The filter is not a new hand detector or a claim that every retained crop is correct.

Decision: bounded crop reliability passes, allowing the single frozen-B2 residual run.
No appearance/geometry performance probe or64/17 model-selection experiment was repeated.

## Residual implementation and validation

Actual B2 checkpoint epoch076 SHA
`64f425358ef30e21a4aca18795226854f7aa44a34c3bc3e54a8c06366cb61397`.
The residual has10,401 trainable parameters; all193,116 B2 parameters remain frozen.
One shared576→16 projection, quality pooling, small learned gate and zero-initialized
16→64 bounded delta correct B2's final64 state. The existing frozen CTC head is reused.
No larger temporal model, new backbone, representation redesign or language correction.

Engineering fixes discovered before handoff:

- Keras3 nested functional calls propagated training mode into frozen B2 Dropout.
  The private inference copy sets Dropout rate0, preserving exact inference while
  the original model/checkpoint remains untouched. Freezing variables alone does not
  disable training-time behavior. [Official Keras transfer-learning guide](https://keras.io/guides/transfer_learning/).
- A head shared inside/outside a nested model failed `.keras` loading. Exposing only
  the pre-head state puts the unchanged head at one serialization scope.
- Existing socket-based writer exclusion hit a Windows forbidden local port. New
  residual-only OS file locking avoids port ownership; locks release on process exit.
- Convert NumPy boolean decision checks to Python booleans before JSON reporting.

Six new focused tests pass: nuisance/missing/partial/border rejection, stronger-only
duplicates without geometry mutation, causality/gradients/frozen weights/serialization,
real native/intermediate/phone alignment, emission-only outcome rejection and process
writer exclusion/release. All18 tests including B2 temporal/CTC regressions pass.
Seven-module mypy and lint pass.
Final smoke `runs/fingerspelling_residual_visual_smoke_03` uses8TRAIN/8DEV, one update
per epoch for3epochs, explicit pause/resume after epoch1. B2 frozen weights unchanged;
Adam/model/epoch restore verified; each TRAIN sequence sees all three requested cadences,
2 valid CTC fallbacks recorded. Zero-quality max logit difference=0 in all3 views after
training. Loss/gradients finite, only the six adapter variables trainable. Native/sparse
metrics, paired actual-B2 comparison and per-character reports serialize correctly.
Smoke CER is **not** a performance result. Development smoke01/02 are retained history;
03 and `artifacts/fingerspelling_residual_visual_01/smoke.json` are the final evidence.

Eight TRAIN/eight DEV sidecars reused historical verified crops/embeddings, then applied
new masks. One additional pending TRAIN and DEV source tested the actual new RGB→crop→
frozen-CNN→receipt path (first pending manifest row per role, no performance selection):

- TRAIN `fsboard-v13-train-0096a95955d86a2bf0e3`,181frames.
- DEV `fsboard-v13-validation-0996dc9c881463a3f8fd`,151frames.

Both source bytes, hashes, raw orientation/dimensions/frame indices/timestamps and
new embedding receipts validate. Current residual inventory9TRAIN/9DEV,2,808frames,
1,685retained slots;1,262 sequences pending. Original full geometry validation remains
1280/1280ready; this does not imply full residual data is ready yet.

## Long preparation and training commands

Use the existing Windows environment. Each command is directly copy-pasteable.
Preparation is serial, downloads nothing, reuses verified completed sidecars, and checks
source integrity before new encoding. A failed clip is recorded under `failures/` and
stops execution; rerunning retries it and keeps verified completions. Ctrl+C is safe:
an incomplete artifact without a final receipt is rebuilt. Do not edit config/code after
starting a run; identities deliberately refuse mixed artifacts/checkpoints.

First materialize the remaining visual package:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m tools.fingerspelling.residual_visual preflight
if ($LASTEXITCODE -ne 0) { throw 'Residual visual preflight failed' }
& .\.venv\Scripts\python.exe -u -m tools.fingerspelling.residual_visual prepare-tranche
if ($LASTEXITCODE -ne 0) { throw 'Preparation interrupted/failed; inspect the recorded failure and rerun prepare-tranche' }
& .\.venv\Scripts\python.exe -m tools.fingerspelling.residual_visual validate
```

Success must report `RESIDUAL_VISUAL_VALID`, prepared TRAIN1024/DEV256, pending0,
failures[], validation_performed=true, test_accessed=false. No source may silently drop.
The actual prepared inventory is checked; a metadata-only manifest does not pass.
Progress/resume:

```powershell
& .\.venv\Scripts\python.exe -m tools.fingerspelling.residual_visual status
& .\.venv\Scripts\python.exe -u -m tools.fingerspelling.residual_visual prepare-tranche
```

Preparation progress: `artifacts/fingerspelling_residual_visual_01/preparation_progress.json`.
Final full validation: same folder `validation.json`. Embeddings:
`datasets/fingerspelling/residual_visual_01/features/`. Full uncompressed embeddings
upper bound1,000,954,368bytes; zeroed invalid crops compress. Initial F: free≈4.13GB.
No all-frame image cache is created. Prior preparation throughput≈23source frames/s
suggests order-hours for remaining RGB; stricter filtering may reduce CNN work. This is
an estimate, not a promise. Bounded fresh-path timings are preserved in each receipt.
The full in-memory geometry/visual/packed temporal cache is roughly3.7GB plus TensorFlow
and report/model overhead. Embeddings are precomputed once; the CNN does not train.

Only after full appearance validation passes, run the one residual experiment:

```powershell
& .\.venv\Scripts\python.exe -m model.fingerspelling_residual_visual preflight
if ($LASTEXITCODE -ne 0) { throw 'Actual full residual dataset is not ready' }
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_residual_visual train
```

Resume with the **same** `train` command; committed epochs restore weights/Adam/selection/
patience. Interrupted epochs repeat with fixed seeded order/views. No bit-exact cross-process
training continuation claim. Status and final evaluation:

```powershell
& .\.venv\Scripts\python.exe -m model.fingerspelling_residual_visual status
& .\.venv\Scripts\python.exe -m model.fingerspelling_residual_visual evaluate
```

Run artifacts `runs/fingerspelling_residual_visual_01/`: run_identity/config/seed,
environment, checkpoints, committed_epoch, progress, per-epoch native/sparse DEV + TRAIN
diagnostics, frozen_b2_reference, failure/resume evidence and final_evaluation.json.
Maximum60epochs/minimum10/patience12; frozen selection is mean native/sparse CER at
the existing B2 penalty0.5. Raw0 metrics also retained. No penalty search or retraining B2.
Every epoch compares actual B2, and final evaluation reloads the pinned B2 checkpoint
directly across all256DEV. Metrics include correct aligned chars, S/D/I, precision,
CER, per-char recall, signer spread, J/Z/repeats, exact strings and emission/headroom.

## Decision and limits

Frozen support rule requires both CERs lower, both correct counts higher, both substitutions
lower, mean precision no worse, and≥8/15DEV signers improving. Otherwise the report says
`RESIDUAL_VISUAL_NOT_SUPPORTED_STOP_VISUAL_PATH`: keep B2, stop visual development;
do not automatically try a backbone, crop-size sweep, attention fusion or another full run.
Full performance remains untested; sparse sampling is still a phone approximation, image
embeddings may retain identity/background, quality rejection is conservative, and Android
crop/encoder parity/export/latency remain future gates. No production change or accuracy claim.

**QUALITY_GATED_RESIDUAL_VISUAL_USER_RUN_READY**
