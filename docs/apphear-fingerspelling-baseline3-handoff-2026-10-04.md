# APPHEAR_FINGERSPELLING_BASELINE_03 — implementation and execution handoff

2026-10-04. The canonical-hand experiment is implemented and ready for **user-run** training.
Full Baseline 3 has not started. Only bounded inference, existing-raw feature conversion,
engineering tests and a three-update smoke ran. No accuracy improvement is claimed yet.

## 1. Preserved repository and boundaries

Branch `codex/current-working-text-to-asl-baseline-2026-09-29`; HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358`. Protected WORD ref
`baseline/apphear-s2-r2-integration-complete-2026-09-26` resolves to
`76d93cecd85bf9f76064d320aa4a5791b5f0704a`.

Starting dirty/untracked inventory is retained at
`artifacts/fingerspelling_baseline3/git_status_before.txt`. Existing modifications to the
continuous-transition report, context and memory, old fingerspelling code/data/docs and phone
diagnostics were preserved. No reset, merge, branch switch, staging or commit was performed.
The 189-file prior fingerspelling/config/manifest/run snapshot and 883 protected-file snapshot
show zero changes (`preservation.json`). Original feature/source/raw integrity also passes
the full foundation preflight. Only new offline B3 files/data and append-only operational
documentation were added.

Candidate01, raw-v1, S2-R2/378, WORD event lifecycle/materializer, Recognition V2, the frozen
236-class model, PhoneProductionSession, SentenceBuilder, Context Assist and Android/product
behavior remain unchanged. No TEST payload, new dataset, acquisition or perception inference.

## 2. Baseline-2 diagnosis before representation work

Epoch-76 model SHA:
`64f425358ef30e21a4aca18795226854f7aa44a34c3bc3e54a8c06366cb61397`.
Metadata-selected 64 TRAIN sequences (32 per stratum, 42 unique official signer identities)
were fixed before inference; all 256 saved DEV predictions were reused. No retraining.
These TRAIN diagnostics measure fit, not held-out or deployment accuracy.

| Role/view | Sequences | Raw CER | Substitutions | Deletions | Insertions | Predicted/reference chars | Exact strings |
|---|---:|---:|---:|---:|---:|---:|---:|
| TRAIN native | 64 | 48.24% | 86 | 451 | 10 | 0.611 | 1 |
| TRAIN sparse | 64 | 43.12% | 169 | 297 | 23 | 0.758 | 0 |
| DEV native | 256 | 58.43% | 386 | 1,592 | 42 | 0.552 | 1 |
| DEV sparse | 256 | 54.82% | 733 | 1,063 | 99 | 0.721 | 0 |

All A–Z/SPACE recalls, aligned confusion counts including DELETION, inserted characters and
exact predictions are in `train_dev_decoding.json`. For example, raw sparse DEV recall is
66.9% for A (375 references), 52.2% for E (335), 26.0% for D (100), and 51.6% for J (62).
This is deterministic text-edit alignment, **not frame-level character annotation**.

Interpretation: TRAIN is also poor; this does not establish only a generalization problem or
prove under-capacity. Residual deletion remains substantial—wrong-character discrimination
is not the sole error in raw decoding. A modest capacity increase was permitted but **not
taken**, to isolate the representation experiment. B3 retains the same hidden channels,
dilations, dropout, optimizer and training/selection policy.

## 3. Slot evidence across the frozen raw corpus

All 1,280 TRAIN/DEV raw sequences were verified/read; Candidate01 was not rerun.

| Native observation diagnostic | All | DAUN | MacKenzie |
|---|---:|---:|---:|
| Frames | 217,221 | 113,496 | 103,725 |
| Neither slot observed | 72,094 | 44,871 | 27,223 |
| Only slot 0 | 14,472 | 7,053 | 7,419 |
| Only slot 1 | 59,792 | 27,130 | 32,662 |
| Both slots observed | 70,863 | 34,442 | 36,421 |
| Both with ROI IoU >=0.6 | 50,577 | 24,991 | 25,586 |
| Overlap + nearby-wrist duplicate proxy | 43,309 | 21,224 | 22,085 |
| Single-observed-slot change | 877 | 514 | 363 |
| Spatially continuous single-slot change | 467 | 271 | 196 |

Thus 71.4% of simultaneous-slot observations have substantial ROI overlap, and 61.1% meet
the duplicate proxy. Continuity requires same dimensions, <=1-second gap and <=0.08 short-side
wrist distance. These are geometry proxies, not physical-hand identity labels or failure-cause
proof. The narrowly defined switch count excludes two-slot transitions and undercounts general
assignment variability. Both strata support testing canonicalization. Per-clip/group evidence:
`slot_diagnostics.json`.

## 4. Frozen canonicalizer and adapter

`SigningHandCanonicalizer.v1` uses valid current-hand evidence plus past wrist association.
Observed+wrist-valid+five valid joints qualifies a candidate. Prefer spatial continuity;
otherwise quality (joint validity/presence/support), then deterministic current-evidence ties.
Duplicate proxies contribute one full primary geometry block. Potentially distinct candidates
retain secondary coarse context and explicit ambiguity. No handedness, anatomy label, future
frame, transcript or recognizer prediction participates.

The full math, thresholds, state/reset rules and Android-compatible field semantics are frozen
in `context/fingerspelling-sequence-v2.md`. Thresholds are configuration, not Candidate01
changes or DEV accuracy tuning. The tracker is a logical association hypothesis: crossing
hands, imperfect duplicate proxies and primary selection in genuine two-hand scenes remain
uncertain. It does not prove which physical hand is actively spelling.

`FingerspellingFeatureAdapter.v2` is `[T,255]`, float32:

| Zero-based columns | Contents |
|---|---|
| 0–1 | real dt + validity |
| 2–169 | primary joints 0..20: source XY, local XY, their masks, support + mask |
| 170–182 | primary presence/proposal/ROI/scale/wrist displacement and masks |
| 183–223 | original eight masked body references + availability |
| 224–231 | valid/quality/continuity/ambiguity/duplicate/distinct/reset/candidate fraction |
| 232–239 | secondary observed/presence/ROI context and masks |
| 240–254 | five fingertip dx/dy + motion masks |

Coordinates and scale reuse frozen v1 geometry. Displacement requires associated consecutive
selected observations, valid joints, same resolution, <=1-second gap and no current ambiguity.
No forward filling; missing primary geometry is zero with invalid masks. Actual dt remains.
Body completeness is never required. Slot ID is audit-only, not a feature.

Final identities:

- Config: `d525092a8d3608de65cf46bf062d154ca65b747e2ca222d4b5a092a709c1e02e`
- Adapter: `2ec4b2c49e970825b01e215e3519a24866fcf0695757ff2c79d4e4b134089325`
- Canonicalizer: `0eb72f6883978f0eaa204285ea9ceda6ef7732111728cf062f7cbbb2be73aeb4`
- Column order: `dd2da554bf48e8ec0e5975075dc18cf10c45106175aff33b6b3efdc3017bd9cd`

Nested v1 dependency identities and the exact 255 names are in the generated column registry
and every receipt. V1 remains frozen at 405. Adding fingertip motion and rebuilding smaller
input kernels are part of the representation change; results cannot establish that slot
canonicalization alone caused any future gain.

## 5. Parity, bug fixes and validation

Python/JVM: **820 observations, 18 comparisons, all bit-for-bit equal**, maximum error zero.
Fixtures include stable/switched slots, duplicate proposals, distinct-hand ambiguity,
both/one missing, partial joints, long gaps, resolution change, exact quality/wrist ties;
real TRAIN DAUN/MacKenzie and DEV DAUN cover all three temporal views. The Kotlin reference
is outside Android; installed-phone parity/integration remains a later gate.

A targeted invariance test found that exact quality/wrist ties could choose a proposal by
slot index despite differing finger geometry. This new-tooling bug was fixed before handoff:
common-evidence lexicographic ties now preserve feature output under slot permutation.
Python/Kotlin fixtures, feature regeneration and smoke were repeated. Provisional **new v2**
files and the earlier smoke are retained under v2 recovery/separate smoke directories;
none is admitted by the final identity check. Original v1 and B1/B2 files were not rewritten.

Checks passed: 13 current canonical/receipt/cache tests and 60 existing regression cases;
new-source Ruff; seven-source mypy with explicit package bases and imported-module diagnostics
excluded (`--follow-imports=silent`). Protected imported code was not modified to fix its
pre-existing type-check errors. One initial test assertion-placement error was corrected in
the new test file; its final rerun passes. Causal model-prefix, padding and finite forward
checks pass. Full raw -> selected indices -> canonical audit -> v2 features recomputation
passes all 1,280 sources; roles, manifests, hashes, targets, masks and chronology validate.

Final smoke: eight TRAIN/eight DEV, three updates, one request per regime per TRAIN source,
one denser feasible fallback, finite loss/gradients, native/sparse evaluation, saved-model
evaluation and bounded decoder calibration. Epoch-1 model/Adam restoration passed; a fresh
process restored committed epoch 3/three optimizer updates **without another update**.
Smoke CER is not research evidence. Stochastic bit-identical continuation is not claimed.

## 6. Actual prepared dataset and lineage

Root `datasets/fingerspelling/canonical_v2_01`, separate from `foundation_01`.
Same frozen manifest SHA
`6b4f152c6bd51eae7af697a58c88c6e20cb0b5e537e272a1a84a897aec54ae6e`.
Every receipt binds source/raw/parent receipt, official role/signer/transcript, adapter,
canonicalizer, temporal policy/implementation, package implementation and feature bytes.
Each view stores actual indices/timestamps, targets, features and audit arrays.

| Inventory | TRAIN | DEV |
|---|---:|---:|
| Sequences | 1,024 | 256 |
| Signers | 117 | 15 |
| DAUN / MacKenzie | 512 /512 | 256 /0 |
| Reference characters incl. SPACE | 18,377 | 3,457 |
| J-containing /Z-containing sequences | 318 /270 | 59 /52 |
| Adjacent-repeat sequences | 425 | 109 |
| Native observations | 178,444 | 38,777 |
| Intermediate observations | 60,523 | 13,424 |
| Sparse observations | 36,548 | 8,031 |
| Native primary-valid fraction | 68.25% | 60.18% |
| Sparse primary-valid fraction | 67.22% | 59.52% |
| Native /intermediate /sparse CTC-infeasible | 0 /4 /19 | 0 /0 /2 |

Compressed three-view NPZs total ~137.0 MiB; receipts ~7.9 MiB. Conversion from raw took
~183 seconds in the final pass; this is not Candidate01 throughput or full-training timing.
All failed/infeasible views remain counted, no target relabeling or source omission.
Training uses B2's nearest-denser feasible fallback; impossible sparse DEV remains in
decoded error metrics and is excluded only from its impossible CTC loss. DEV is DAUN-only
and phrase-policy-filtered/challenge-enriched; no MacKenzie held-out or population claim.
TEST remains sealed. Reflection policy remains released pixels as-is, no flip.

## 7. One comparable user-run training experiment

Entry: `model.fingerspelling_baseline3`. It imports the original TCN layer configuration,
loss, temporal view policy, decoder, metrics and stopping logic. Width-specific execution/cache
is separate. Layers remain 64 channels with dilations 1/2/4/8, dropout 0.1, one output per
observation, 28 logits, Adam 0.001/clip 5, batch 8, two CPU threads, seed 20261002.
Parameters: 154,716 vs B2's 193,116 because the input width is smaller. No hidden-capacity
increase, checkpoint migration, warm start or alternative encoder.

Same native/12-Hz/phone regime schedule, bounded denser fallback, raw balanced native/sparse
CER selection, maximum 90/minimum 30 epochs, patience 15, meaningful improvement 0.002.
Same bounded post-checkpoint penalties 0/0.5/1/1.5/2 and safeguards. Calibration remains
secondary; evaluate discrimination before calibration. No language model or special letters.

## 8. Exact PowerShell commands

Data conversion is already complete. **Do not run the old B2 command.**

Preflight (full source/raw/v1/v2 integrity; can take a few minutes):

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_baseline3 preflight
```

Expect `BASELINE3_PREFLIGHT_PASS`, TRAIN 1024 /DEV 256, `ready_to_train: true`, no errors.
Start full B3 only after this succeeds:

```powershell
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_baseline3 train
```

Progress from another PowerShell in the same directory:

```powershell
& .\.venv\Scripts\python.exe -m model.fingerspelling_baseline3 status
```

Resume uses the **identical** command (no new run directory):

```powershell
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_baseline3 train
```

Ctrl+C records interruption. Resume checks dataset/code/config identity and restores the last
committed epoch, Adam and stopping state; an interrupted epoch is repeated. Do not run two
writers at once or edit pinned implementation/config while a run is in progress. Missing
or changed artifacts fail explicitly; no silent fallback to B1/B2 or partial dataset.

After `BASELINE3_TRAINING_COMPLETE`:

```powershell
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_baseline3 evaluate
```

Expected final status `BASELINE3_FINAL_EVALUATED`. Bring back `completion.json` and
`final_evaluation.json` from `runs/fingerspelling_ctc_baseline_03`.
That folder also contains run_identity/environment, progress, committed_epoch/checkpoints,
best_candidates, per-epoch JSON, resume verification, decoder calibration and failure report
if interrupted/failed. Epoch/final reports include native/sparse CER, edit/exact/output-length
metrics, per-character recalls/confusions, signer spread, length/J/Z/repeat diagnostics and
emission/headroom information. All metrics are signer-disjoint offline sequence diagnostics,
not AppHear end-to-end streaming accuracy.

Optional preparation resume after an interrupted conversion, using **existing raw only**:

```powershell
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_baseline3 prepare
& .\.venv\Scripts\python.exe -u -m pipeline.fingerspelling.package_v2 validate --recompute
```

No download/extraction or training is triggered by these preparation commands.

## 9. Evidence, review and next decision

Evidence root `artifacts/fingerspelling_baseline3`: diagnostic_manifest, train_dev_decoding,
slot_diagnostics, parity/parity.json, dataset_summary, raw_feature_recomputation, preflight,
tests, smoke, fresh_process_resume, model_contract, preservation. Contract registry:
`context/fingerspelling-sequence-v2.md`. Review: `review.json`.

Review passes plan/boundary/offline-readiness checks. No unresolved implementation blocker
to one research run. Physical-hand identification remains heuristic; parity is a JVM
reference, not Android deployment; sparse cadence is quantized and not a live-phone replay;
native missing-hand fractions and DEV source restriction remain visible. These limitations
do not authorize production rollout.

After the user run, compare **raw** B3 vs epoch-76 B2 (58.43% native /54.82% sparse CER),
substitutions, broad character recall, exact strings and signer spread, then deletions,
insertions, J/Z/repeats and calibration. Better TRAIN/DEV supports retaining this representation
and considering more governed data; strong TRAIN/weak DEV supports diversity work; poor both
supports bounded capacity/information diagnostics. If canonicalization fails to help, retain
the result and return to the preserved B2 representation. No automatic next experiment.

FINGERSPELLING_BASELINE3_USER_RUN_READY
