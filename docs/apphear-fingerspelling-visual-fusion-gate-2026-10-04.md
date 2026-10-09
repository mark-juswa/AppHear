# AppHear fingerspelling visual fusion — implementation and information gate

**Decision: VISUAL_INFORMATION_GATE_NOT_SUPPORTED.** Stop before full-tranche visual
preprocessing or fusion training. Appearance greatly improves fitting on the fixed
TRAIN subset, but combined input worsens held-out DEV discrimination. This is a
negative result for this frozen ImageNet embedding/simple-fusion/short-probe choice,
not proof that RGB lacks useful information. B2 remains the completed research reference.

## Preserved state

Branch `codex/current-working-text-to-asl-baseline-2026-09-29`, HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358`. Protected WORD baseline
`baseline/apphear-s2-r2-integration-complete-2026-09-26` →
`76d93cecd85bf9f76064d320aa4a5791b5f0704a`.

Dirty/untracked work already existed, including the continuous-transition report,
context/memory and previous fingerspelling datasets/code/runs. No reset, switch, merge,
staging or cleanup. Preservation snapshot checks **1538 pre-existing files**, including
protected Android/Candidate01/WORD assets and B1–B4 code/config/checkpoints/reports:
**zero changes**. Only new visual components/artifacts and appended documentation were
created. No TEST RGB, new download, Candidate01 inference, Android/ABC/routing,
SentenceBuilder, Context Assist or release change.

Frozen tranche remains1024TRAIN/256DEV, manifest SHA
`6b4f152c6bd51eae7af697a58c88c6e20cb0b5e537e272a1a84a897aec54ae6e`.
All1280 original RGB files still exist (8,631,742,503bytes); no reacquisition needed.
Geometry Adapter.v1405/config/order/implementation identities remain unchanged.

## Implemented contract

Architecture was frozen before the gate in
`docs/apphear-fingerspelling-visual-fusion-plan-2026-10-04.md` and
`pipeline/config/fingerspelling_visual_v1.json` (SHA
`e0694f00021bf8d29cc36fb941b44cb0d11a36d4903b97608c8c2a59c433aba3`).
Exact reusable contract: `context/fingerspelling-visual-v1.md`; registry imprinted in
`context/feature-schema.md`.

- **HandCropExtractor.v1:** same current upright RGB + both Candidate01 proposal ROI
  slots; square side×1.10,128RGB, shared float32 zero-border bilinear sampler,
  external[-1,1]. No second detector, rotation redesign, horizontal flip or fill.
  Present finite ROI, side≥8pixels and ≥50% source-area intersection define availability.
  Proposal/refiner acceptance are separate; rejected landmarks can retain a crop.
- **HandAppearanceEncoder.v1:** frozen locally cached/hash-verified MobileNetV3Small,
  939120parameters, global-average576embedding per slot. No DEV fitting, augmentation
  or appearance-encoder training. Official cached ImageNet weights MD5
  `d3e8ec802a04aa4fc771ee12a9a9b836`, SHA
  `002803a73df2ab65425267ee2082d1ec213b6aa9716f19ac1a1ed5361239c5f6`.
  [Keras MobileNet documentation](https://keras.io/api/applications/mobilenet/) governs
  normalization/preprocessing API; ImageNet pretraining is not handshape supervision.
- **FingerspellingVisualFusion.v1:** separate packed1559input =405geometry +1152appearance
  +2crop masks. Geometry→64, shared appearance→32/slot with masks applied after bias,
  concatenate/project→64, B2-size causal TCN,28CTC logits.154492trainable parameters;
  receptive field61, stride1. No B4-scale capacity increase.
- **Temporal alignment:** B2 chooses real raw indices; geometry dt/motion recompute
  using original Adapter.v1, appearance selects those exact frames. Geometry remains
  available with missing crops; no fabricated/fill/duplicated visual observations.

Implementation paths: `pipeline/fingerspelling/visual_crop.py`, `visual_package.py`,
`model/fingerspelling_appearance.py`, `fingerspelling_visual_execution.py`,
`fingerspelling_visual_gate.py`, `tools/fingerspelling/visual_fusion.py`.

## Bounded package and crop review

Only **64TRAIN +17DEV** visual packages were materialized: historical TRAIN64 IDs,
32DAUN/32MacKenzie,42TRAIN signers;17DEV from15official held-out signers (DAUN),
including the two established sparse-CTC-infeasible examples. Same official roles and
DEV overlap policy. TRAIN includes22J sequences,16Z,27adjacent-repeat sequences;
DEV includes3J,2Z,11repeat sequences. This is a diagnostic subset, not a new split.
TRAIN covers25letters; X is absent. Per-character/subgroup counts remain limited.

There are no single-letter TRAIN transcripts in the tranche. The gate therefore uses
sequence transcripts/CTC, **no invented frame labels or letter boundaries**.

81packages/13792observations validate;24218valid slot crops, weighted any-crop
availability93.9965%. Valid crops include10401refiner-rejected slot observations.
Refined-point containment minimum1.0: this checks consistency with retained landmarks,
not annotated true fingertip containment or semantic hand correctness.

Five contact sheets reviewed directly, covering DAUN/MacKenzie/DEV and the lowest
availability clip. Typical crops visibly retain finger overlap, thumb placement and
hand rotation. Slots often duplicate a physical hand. Some false proposal crops
contain face/arm/background; blur and non-hand context remain. The lowest-coverage clip
has no visible hand at its three QA times and one background proposal. Those snapshots
do not establish the entire attempt's timing/completeness. No relabeling/exclusion.

Separate archives retain source/raw/geometry SHA lineage, exact raw frame IDs/times,
expanded ROIs, masks, normalized-crop SHA, encoder/config/code/version identities and
receipt hashes. Invalid embedding/ROI/crop-hash zeroing, chronology, source dimensions,
orientation and size/MD5/SHA are checked. No original geometry archive was rewritten.

One wrapper bug found/fixed: older diagnostic receipts pin orientation indirectly in
`video_probe.json`. The new reader verifies that artifact SHA and matching source/sample
identity instead of assuming a root orientation field. Eleven new visual packages
already prepared were archived and metadata-rebound to the fixed implementation hash;
**all numeric crop/ROI/embedding/timestamp arrays remained bit-exact**. Original
source/raw/geometry receipts were untouched. Migration is explicitly recorded.

## One fixed information gate

Three fresh equal-architecture input ablations: geometry-only, appearance-only,
combined. Same initialization/state SHA, seed20261002, samples/order, Adam/.001/clip5,
three B2 cadence regimes and feasible-view fallback. Appearance-only retains common
dt/dt-valid columns0:2 but no hand/body geometry. Each arm fits TRAIN64 for exactly
60epochs/480updates; fixed evaluation0/30/60, no DEV checkpoint selection or calibration.
No additional epochs, probes, encoder variants or threshold changes followed results.

Frozen pass rule required combined TRAIN mean CER≥5points better, both views improved;
DEV mean CER≥3points better, neither view regressing>2points; DEV aligned correct/reference
gain≥3points; mean correct/predicted precision not lower, neither view losing>2points.
The held-out/precision guard prevents signer/background fitting or longer output alone
from authorizing the expensive experiment.

| Input | TRAIN native CER | TRAIN sparse CER | DEV native CER | DEV sparse CER |
|---|---:|---:|---:|---:|
|Geometry-only|70.72%|66.49%|85.34%|85.78%|
|Appearance-only|50.71%|30.25%|83.19%|82.76%|
|Combined|47.62%|26.46%|91.81%|84.91%|

Balanced TRAIN CER68.61%→37.04% is a large fitting improvement. Balanced DEV
85.56%→88.36% worsens2.80points. DEV correct/reference mean improves only1.08points;
correct/predicted precision loses7.79points. TRAIN checks pass; all held-out gate checks
fail. Combined has5exact sparse TRAIN strings but **zero exact DEV strings**.

| DEV view/input | Correct /232 | Predicted | Substitutions | Deletions | Insertions |
|---|---:|---:|---:|---:|---:|
|Native geometry|35|116|80|117|1|
|Native combined|37|170|115|80|18|
|Sparse geometry|34|118|83|115|1|
|Sparse combined|37|171|132|63|2|

Thus combined mostly increases emission and substitutions, with only2/3more correctly
aligned DEV characters. Appearance-only retains a small held-out signal but not a
convincing fusion improvement. Per-character recall/confusions, signer/subgroup CER,
headroom/CTC loss, blank/length and epoch metrics remain in each evaluation artifact.

For context, saved B2 predictions on these same IDs are TRAIN48.24%/43.12% and
DEV62.50%/56.90% raw native/sparse. **B2 was trained on1024sources**, whereas these
fresh controls saw64; this is not an equal-volume model replacement comparison.
The gate's geometry control also includes the declared fusion projections. Its weaker
fit cannot be used to diagnose B2 itself. Full256DEV fusion performance was not measured.
No research CER here is a deployed AppHear accuracy claim.

## Engineering evidence / practicality

- Six focused tests pass: known RGB/no-reflection sampler, borders/missingness,
  real-frame/405-parity alignment, finite gradients, causal prefix, invalid-crop bias
  masking, save/load equality, gate rejection of emission-only improvement, and
  historical orientation identity guard. Six production modules pass mypy.
- Ruff passes with one documented E501 exception for a fixed long historical evidence
  path literal; artifact implementation identity remained stable during preparation.
  External Keras/NumPy deprecation warnings do not affect these checks.
- Gate paused after one epoch and resumed in a separate process: model/Adam/epoch
  state exactly restored. Stochastic continuation bit-identity is not claimed.
  All180arm-epochs retain64sources; equal sample order/views/update counts verified.
  Infeasible requested TRAIN views use existing denser fallback; impossible sparse DEV
  remains decoded and only its CTC loss is omitted. No policy weakened.
- New compressed embeddings51.19MB. Diagnostic decode/crop/encoder time593.96seconds,
  encoder41.73seconds,23.22source frames/s on this host with microbatch32. This is
  offline throughput, **not phone latency**. Entire217221-frame tranche would need
  at most1.00GBdense embeddings; observed compression suggests roughly0.81GB plus
  receipts. At observed host rate preparation alone would take about2.6hours; estimate,
  not benchmark. Bulk preparation was not run; sufficient local storage remains.

Future Android seam: prepared current RGB + Candidate01 ROI before
`session.consume(observation)`/`image.close()`. No second camera/inference. Existing
224/[0,1] refiner crop is not the128/[-1,1] visual tensor. Actual crop/encoder TFLite
parity, CPU p50/p95, delivered fusion cadence, causal state and exclusive WORD commit
ownership remain later gates. Geometry-only6.23Hz does not prove fusion throughput.

## Review / stop consequence

Plan alignment PASS (conditional full training correctly withheld), protected boundaries
PASS, diagnostic engineering PASS. Production readiness NOT CLAIMED. Critical/important
implementation defects remaining:0/0; minor:1long-path lint exception. Known experimental
limits include small DEV coverage, generic frozen global-image embeddings, erroneous
proposals/background, no convergence proof and no installed-device parity/profile.

Do **not** launch full visual preprocessing/training, expand data, tune decoder or
replace B2. The next justified discussion is bounded crop reliability/non-hand context
and frozen-embedding suitability using retained evidence. Strong TRAIN fitting alone
does not identify the cause of weak held-out results. No new experiment is started here.

Read-only inspection commands:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m tools.fingerspelling.visual_fusion status --diagnostic
& .\.venv\Scripts\python.exe -m tools.fingerspelling.visual_fusion validate --diagnostic
Get-Content -LiteralPath '.\artifacts\fingerspelling_visual_fusion_01\visual_information_gate.json'
```

Evidence: `artifacts/fingerspelling_visual_fusion_01/` (preservation, config identities,
coverage, QA sheets/summary, migration, validation, gate and saved B2 subset reference).
Models/checkpoints/evaluations: `runs/fingerspelling_visual_information_gate_01/`.
Actual prepared visual inventory **64TRAIN/17DEV**, geometry inventory unchanged1280.
No full fusion trainer/run was authorized or launched following the negative gate.

VISUAL_INFORMATION_GATE_NOT_SUPPORTED
