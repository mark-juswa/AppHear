# AppHear fingerspelling quality resolution 01

Status: IMPLEMENTED_USER_RUN_EXPANDED_DATA_TRAINING_READY; actual expanded data pending.

## Finding and decision

**VERIFIED bottleneck:** the recognizer does not reliably discriminate/emits missing
characters, and generalization to held-out signers remains weak. This is present offline
before Android. Numerical train/serve parity and decoder parity are already established.
There is no demonstrated implementation defect in CTC, Adapter.v1, or Android that explains
the remaining error. Outer-window trimming worsened recognition rather than fixing it.

**Most likely actionable limitation:** insufficient sequence supervision and variation
in the 1,024-example feasibility tranche. It supplies only 18,377 transcript characters
across 117 TRAIN humans, about 5â€“14 clips/person. This does not prove that 2D observations
retain every necessary distinction, nor that more data guarantees success. Existing small
subset fit gates show that the representation can learn; neither larger capacity nor the
visual alternatives established a broad improvement. The evidence does not justify another
encoder/feature/boundary redesign before using more of the already-governed corpus.

Chosen intervention: materialize the already-frozen TRAIN-4096 plan, then **fine-tune an
immutable copy of B2** on expanded supervision. This is one data intervention, without a
model-family search. It reuses the same causal 193,116-parameter TCN, 61-observation receptive
field, stride-one 28-logit CTC head, Adapter.v1 `[T,405]`, masks, and cadence-aware view
selection/fallback. Existing residual candidate, B2, Android and WORD remain unchanged.

The old residual adapter is conditioned on the old frozen B2 representation. **Do not attach
it to the newly fine-tuned geometry model without separate evidence.** This run trains the
retained B2 research path and must outperform the existing residual+beam candidate on DEV-A
before any further integration is considered. No visual branch is trained or redesigned.

## Direct code/data/result inspection

Reviewed the actual B2 architecture and checkpoint, compiled CTC loss/update path, feature
cache, temporal sampling/recomputation, source/raw/feature receipts, frozen expansion
selection/governance, B1â€“B4/residual/decoder results and the outer-window oracle. Previous
TRAIN-fitting claims used subsets (64 examples, or eight for residual), so a new one-time
**inference-only diagnostic on all 1,024 original TRAIN sequences** closes that gap.

Frozen B2 epoch 076, prefix beam10, blank27, penalty0.5; TRAIN values are fitting diagnostics,
not held-out accuracy. DEV-A remains the same 256 sequences/15 official held-out signers.

| View | Full TRAIN CER | TRAIN S / D / I | TRAIN correct chars | TRAIN exact strings | B2 DEV-A CER | Current residual DEV-A CER |
|---|---:|---|---:|---:|---:|---:|
| Native | 39.07% | 2,520 / 3,742 / 918 | 12,115 / 18,377 | 8 / 1,024 | 50.19% | 49.52% |
| Phone-like | 42.43% | 3,141 / 3,993 / 663 | 11,243 / 18,377 | 4 / 1,024 | 52.70% | 52.16% |

The same-stratum comparison is also worse on DEV: DAUN TRAIN CER41.65% native/42.33%
phone versus DEV-A50.19%/52.70%. Aggregate TRAIN/DEV includes MacKenzie in TRAIN only;
that composition difference must not be mistaken for a pure generalization measurement.

TRAIN coverage grouping is descriptive, not a causal proof: low observed-hand coverage
has CER76.62% native/72.22% phone, but the high-coverage group still has CER32.15%/35.98%.
Missing hand evidence contributes; it cannot account for all of the recognition error.
Native TRAIN aligned recall is A83.05%, E78.17%, I79.98%, U28.92%, Q10%, X21.43%.
Q has only20 transcript occurrences, X28; common-character errors also remain, so rare
characters alone do not explain the overall result.

Historical findings constrain the change: cadence correction was effective; canonicalization
was not; capacity expansion did not broadly improve held-out sparse discrimination;
generic appearance fusion overfit; residual gains were modest; fixed beam decoding helped;
publisher-window oracle trimming cost correct characters. These results do **not** prove a
hard Candidate01 information ceiling. No additional architecture experiment is launched.

## Repository and protection

Research branch `codex/current-working-text-to-asl-baseline-2026-09-29`, HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358`. Correct application integration baseline:
`baseline/apphear-text-to-asl-context-assist-ui-2026-10-04` at
`cee71d9f181695847936eb5f3605ea37eab82a95`. Earlier WORD ref
`76d93cecd85bf9f76064d320aa4a5791b5f0704a` remains protected.

Pre-existing dirty/untracked Android/research/docs/data/run work was preserved; no reset,
branch switch, merge, deletion or Android edit. The current application worktree under
`C:/Users/Gigabyte/.codex/worktrees/fingerspell-oct04-integration/5. Apphear3` is untouched.
No Candidate01 inference, new video download, bulk extraction, full training, TEST payload
access, Context Assist change or WORD change was performed. Only bounded engineering
training on eight existing TRAIN/eight DEV-A examples was executed; no accuracy claim.

## Implemented solution

New files:

- `model/config/fingerspelling_train4096_01.json`: frozen data/model/reference identities,
  warm-start policy, fixed decoder and confirmation governance.
- `pipeline/fingerspelling/expanded_training.py`: read-only, exact-count expanded admission.
  Reuses frozen source/raw/adapter verifiers; validates manifests, roles, human separation,
  source uniqueness, class coverage, source/hash lineage, storage marker, raw dialect,
  recomputed native/phone geometry/masks/timestamps/targets and CTC lengths.
- `model/fingerspelling_train4096.py`: separate user-run preflight/train/status/evaluate/smoke
  runner, reusing existing temporal cache, compiled updates, loss and evaluation machinery.
- `tests/test_fingerspelling_train4096.py`: governance, absolute-path parity, tampering,
  incomplete data refusal, decoder result integration and confirmation lock tests.

Preparation code locked by the I: initialization is unchanged. The existing preparation
runner continues producing separate `train_additions` and `dev_b` packages. Original
foundation archives are referenced with their original receipts/manifest hash. The original
12 admission sources/raws are allowed at their existing governed legacy location; no copies
or rebinding are required. New source paths must remain within their declared package.

Warm start: B2 epoch076 SHA
`64f425358ef30e21a4aca18795226854f7aa44a34c3bc3e54a8c06366cb61397`.
Fresh Adam at0.0003, clipnorm5, same batch8/CPU execution/dropout/loss; max60 epochs,
minimum15, patience12, minimum CER improvement0.002. The reduced learning rate and fresh
optimizer are supporting fine-tuning choices, not a hyperparameter sweep. This is not a
pure from-scratch data-size ablation. B2 weights/optimizer archives are never overwritten.

Checkpoint selection stays historical: balanced **uncalibrated greedy DEV-A** CER, first
tie; no beam or penalty tuning. Final recognition comparisons use fixed beam10/penalty0.5.
Resume restores model/Adam/epoch exactly and repeats an interrupted epoch. Bit-exact
dropout-RNG continuation is not claimed. Code/data/config changes refuse mixed resumes.

DEV-B is never loaded by the training loader for fitting/checkpoint selection. Final
evaluation requires completed training and creates a checkpoint/decoder/data-lineage lock;
later training through this runner is refused. DEV-B compares the selected model against
the actual frozen B2 checkpoint. It shares DEV-A's15 signers and some phrases; it is fresh
confirmation, not independent new-human TEST. Residual visual evidence is not prepared
for DEV-B; its comparator is explicitly B2-only. TEST remains sealed.

## Verification and acceptance

Engineering smoke: warm-start maximum logit difference0.0; finite loss/gradients; exact
model+Adam resume after epoch1; three epochs; native/intermediate/phone requests8 each;
one valid CTC fallback; native/phone fixed-beam evaluation passed. No DEV-B inference.
The first smoke exposed a new wrapper field-name bug (`text` versus decoder `prediction`);
fixed and regression-tested. This was not a historical recognizer bug. Failed smoke
artifacts are retained separately; the passing run is `runs/fingerspelling_train4096_01_smoke_verified`.

Final evidence must report actual correct characters, S/D/I, CER, precision, exact strings,
per-character counts, signer CER, J/Z/repeats, CTC infeasibility and the old1024 TRAIN fit
diagnostic. A longer prediction is not success. The frozen support pattern requires lower
native/phone CER, more correct characters, fewer substitutions, non-regressing precision
and a majority of signers improving in both views, on DEV-A versus the residual reference
and DEV-B versus frozen B2. The report retains every delta even when this pattern fails;
effect magnitude still needs human review. No automatic Android promotion occurs.

72 unique focused tests pass (including the final-confirmation lifecycle check); Ruff
and mypy pass. Review: scope/plan, integrity and engineering gates PASS; no automatic
production promotion. Only actual expanded data and its trained quality result remain
open. Focused test/static/preservation outputs are under
`artifacts/fingerspelling_quality_resolution_01/`. The protected inventory covers11,506
existing files, including WORD, both Android trees, Candidate01, frozen datasets/checkpoints,
decoder and visual artifacts. Completion evidence is recorded in `validation.json` and
`preservation.json`; no need to rebuild Android because no runtime file changed.

## Actual data and next commands

Existing data:1,024 TRAIN +256 DEV-A, all valid. New data currently prepared:0 TRAIN
additions +0 DEV-B;3,328 pending. TRAIN-4096 will retain all original examples, all117
TRAIN humans and2,048 examples per stratum. Transcript supervision grows18,377â†’76,985;
Q20â†’105 and X28â†’132. No additional TRAIN humans are introduced by this expansion.

New artifacts go to `I:\AppHearData\FSboard_TRAIN4096_01`. Existing F: data stays in place.
Estimated additional RGB23,631,341,894 bytes, approximately0.781GB raw/features, conservative
25.49GB free-space requirement. Prior measured-throughput estimate:13.36hours Candidate01
processing, plus download/validation. No new speed or extraction measurement is claimed.

Run preparation first. Check `$LASTEXITCODE` after each command; proceed only on success.
Both preparation and training commands are resumable by rerunning the identical command.

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m tools.fingerspelling.prepare_expansion preflight --destination 'I:\AppHearData\FSboard_TRAIN4096_01'
& .\.venv\Scripts\python.exe -u -m tools.fingerspelling.prepare_expansion prepare --destination 'I:\AppHearData\FSboard_TRAIN4096_01'
& .\.venv\Scripts\python.exe -m tools.fingerspelling.prepare_expansion validate --destination 'I:\AppHearData\FSboard_TRAIN4096_01'
& .\.venv\Scripts\python.exe -m model.fingerspelling_train4096 preflight
```

Required preparation success:3,072 additions +256 DEV-B, zero structural errors;
`SELECTED_PACKAGES_MATERIALIZED_INTEGRITY_PASS`, then `TRAIN4096_PREFLIGHT_PASS` with
TRAIN4096/DEV-A256 and confirmation256. Pending data is a hard refusal, not a smaller run.

Only after that preflight succeeds:

```powershell
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_train4096 train
```

Status from another terminal:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m model.fingerspelling_train4096 status
```

After `TRAIN4096_TRAINING_COMPLETE`, freeze the selected checkpoint and run confirmation:

```powershell
& .\.venv\Scripts\python.exe -u -m model.fingerspelling_train4096 evaluate
```

Output: `runs/fingerspelling_train4096_01/` contains immutable run identity, epoch metrics,
progress, checkpoints, resume verification, completion, confirmation lock and
`final_evaluation.json`. Return that final report for review. It can report that improvement
was not established; nothing silently replaces the current recognizer.

IMPLEMENTED_USER_RUN_EXPANDED_DATA_TRAINING_READY
