# AppHear fingerspelling TRAIN-4096 — Project Lead decision handoff

Date: 2026-10-07. Scope: completed-run review only. No new inference, training,
data acquisition, extraction, Android changes, or WORD changes.

## Technical decision

**Retain the frozen 4K epoch-038 geometry model as the next experimental candidate.
Proceed next to controlled export/parity and a bounded phone comparison; do not start
another offline tuning run or promote it to reliable/release recognition.**

The improvement is meaningful against the previous 1K reference: held-out strings
contain more correctly aligned characters, fewer substitutions, higher precision,
and lower CER in both temporal views. Fresh DEV-B sequences support the direction.
This does not reproduce the earlier capacity/visual failure pattern of emitting
more characters without recognizing more correctly.

It remains a weak spelling recognizer in absolute terms. Phone-like CER is about
46–47%; only one of 256 complete strings is exact in each DEV set. The result
justifies advancing the candidate, not claiming that the recognition problem is
solved. The next consequential unknown is whether these gains survive actual phone
input, which has not been evaluated with the new checkpoint.

## 1. What was actually run and checked

Research branch: `codex/current-working-text-to-asl-baseline-2026-09-29`; HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358`. Correct application baseline:
`baseline/apphear-text-to-asl-context-assist-ui-2026-10-04` at
`cee71d9f181695847936eb5f3605ea37eab82a95`. Existing dirty/untracked work was preserved.
The actual experimental integration is in
`C:/Users/Gigabyte/.codex/worktrees/fingerspell-oct04-integration/5. Apphear3`.

This is an **expanded-supervision fine-tune**, not a new architecture or a clean
from-scratch data-size ablation:

- Immutable B2 epoch-076 initialization; same 193,116-parameter causal TCN,
  64 channels, dilations 1/2/4/8, 61-observation receptive field, stride one.
- Candidate01/raw-v1 and Adapter.v1 `[T,405]` unchanged; the new model is **geometry-only**.
- Same native/intermediate/phone temporal regime, real observations only,
  recomputed timing/motion, masks, CTC vocabulary and loss.
- Fresh Adam, learning rate 0.0003, batch size eight, seed 20261002, gradient clip five.
- 4,096 TRAIN sequences, including every original 1,024 row exactly; 117 official
  TRAIN signers, 2,048 DAUN + 2,048 MacKenzie. Median clips/person increased from
  seven to 28; **no new TRAIN humans were added**.
- 76,985 target characters versus 18,377 originally. Q: 20→105; X: 28→132.
  More supervised instances/context is verified; condition diversity is not fully measured.
- DEV-A: original frozen 256, used for selection. DEV-B: 256 fresh sequence IDs,
  opened only after checkpoint locking. Both are DAUN, with the same 15 official
  DEV signers, disjoint from TRAIN. Neither is an independent new-signer TEST.
- No TRAIN/DEV normalized-phrase overlap in these manifests. DEV-A/DEV-B share
  ten unique normalized phrases; their sequence IDs are disjoint.
- Fixed final decoder: prefix beam width ten, all 28 symbols, blank 27, penalty
  0.5 once, Top-1 only; no dictionary, language model, or new calibration.

Selected checkpoint:
`runs/fingerspelling_train4096_01/best_candidates/epoch_038.keras`, SHA-256
`b037e32789f523c043b46c32cdc2ea11f2f600fd35f30ecd672604b6f6947886`.
B2 initialization SHA:
`64f425358ef30e21a4aca18795226854f7aa44a34c3bc3e54a8c06366cb61397`.
Frozen config SHA:
`4ce562d357c25aa2226d785b42b1ca620f0b4dbe6f5b49b9d00a526084f010b1`.

Fresh checks verified selected/initial model hashes, config and 14 pinned code-file
identities, Adapter implementation/config hashes, manifests, confirmation lock,
4,608 feature receipts and their lineage, and existence of all referenced source,
raw, extraction-receipt and feature files. Current receipt lineages reproduce the
saved run/confirmation identities. Previously completed full source/raw/adapter
validation is preserved; this review did **not** rehash every RGB/NPZ payload or
rerun Candidate01. Those scopes must not be conflated.

## 2. Training history and checkpoint selection

All 50 chronological epoch reports were read. Every epoch retains all 4,096 TRAIN
sources; every selected training view is CTC-feasible. Sixteen complete three-epoch
cycles expose each source to native/intermediate/phone requests. Infeasible sparse
requests use the existing denser fallback, without dropping or manufacturing data.
No epoch performs DEV-B or TEST inference.

Checkpoint selection remains the predetermined mean **uncalibrated greedy**
native/phone DEV-A CER. It is not the final calibrated beam score.

| Epoch | Mean TRAIN CTC | Native selection CER | Phone selection CER | Balanced selection CER |
|---|---:|---:|---:|---:|
| 1 | 34.59 | 58.66% | 53.20% | 55.93% |
| 20 | 31.82 | 54.47% | 50.36% | 52.42% |
| **38 selected** | **30.68** | **50.65%** | **48.80%** | **49.73%** |
| 50 stopped | 30.09 | 53.63% | 49.78% | 51.71% |

Recomputed best checkpoint and patience match completion exactly: best epoch 38,
12 non-improving epochs, stopped at 50 under the maximum-60 policy. Cycle-mean
TRAIN CTC falls from 34.20 in epochs 1–3 to 30.02 in epochs 48–50, but validation
does not improve after 38. **Falling training loss is not a reason to extend this run.**
The validation plateau does not prove all possible optimization is exhausted.
Do not compare absolute CTC loss against the shorter/different 1K corpus as accuracy.

The retained `failure.json` is a historical KeyboardInterrupt after committed epoch
47, not an unresolved training failure. Resume verified exact model/Adam/epoch state,
including 24,064 optimizer iterations; completion has 25,600. Bit-exact stochastic
continuation is not claimed. Recorded epoch times sum to 6,408.91 seconds (106.8
minutes), excluding interruptions, preflight and final evaluation. This is not wall-clock duration.

## 3. Full held-out sequence comparison

All rows below use the **same fixed beam/penalty**. DEV-A has 3,457 reference
characters/view; DEV-B has 3,374. CER includes SPACE. Counts use the established
deterministic Levenshtein alignment, not per-letter timing annotations or true
frame-level character recall. Phone is a sampling approximation of measured
AppHear cadence, not live-phone accuracy.

| Set / model / view | CER | S | D | I | Correct aligned | Predicted | Precision | Exact / 256 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DEV-A / 1K B2 / native | 50.19% | 687 | 854 | 194 | 1,916 | 2,797 | 68.50% | 0 | 0 |
| DEV-A / 1K residual / native | 49.52% | 679 | 824 | 209 | 1,954 | 2,842 | 68.75% | 0 | 0 |
| DEV-A / **4K** / native | **42.75%** | **513** | **801** | **164** | **2,143** | 2,820 | **75.99%** | 0 | 0 |
| DEV-A / 1K B2 / phone | 52.70% | 937 | 745 | 140 | 1,775 | 2,852 | 62.24% | 0 | 0 |
| DEV-A / 1K residual / phone | 52.16% | 920 | 739 | 144 | 1,798 | 2,862 | 62.82% | 0 | 0 |
| DEV-A / **4K** / phone | **46.98%** | **771** | **686** | 167 | **2,000** | 2,938 | **68.07%** | 1 | 0 |
| DEV-B / 1K B2 / native | 47.98% | 595 | 846 | 178 | 1,933 | 2,706 | 71.43% | 1 | 1 |
| DEV-B / **4K** / native | **41.88%** | **543** | **720** | **150** | **2,111** | 2,804 | **75.29%** | 2 | 1 |
| DEV-B / 1K B2 / phone | 52.40% | 880 | 762 | 126 | 1,732 | 2,738 | 63.26% | 0 | 1 |
| DEV-B / **4K** / phone | **46.24%** | **746** | **659** | 155 | **1,969** | 2,870 | **68.61%** | 1 | 1 |

Balanced DEV-A improves from 50.84% (current 1K residual) to **44.87%**: 5.97
percentage points, about 11.75% relative error reduction. Against plain 1K B2,
DEV-A improves from 51.45% to 44.87%. DEV-B improves from 50.19% (B2) to **44.06%**:
6.14 points, about 12.22% relative error reduction.

DEV-B has no residual embeddings, so it **does not establish superiority over the
residual model on DEV-B**. DEV-A provides that direct comparison. The two reference
scopes must remain explicit in any presentation.

Phone-like gains versus the applicable reference are 202/237 additional correctly
aligned characters and 149/134 fewer substitutions on DEV-A/DEV-B. Precision rises
5.25/5.35 points. Native DEV-A output actually becomes 22 characters shorter while
correct count rises 189: improvement cannot be explained by emitting more.

## 4. Spread, subgroups and regressions

| Comparison / view | Sequences improve | Regress | Same edit count | Signers improve / regress |
|---|---:|---:|---:|---:|
| DEV-A vs residual / native | 148 | 43 | 65 | 15 / 0 |
| DEV-A vs residual / phone | 140 | 49 | 67 | 15 / 0 |
| DEV-B vs B2 / native | 146 | 44 | 66 | 15 / 0 |
| DEV-B vs B2 / phone | 143 | 46 | 67 | 14 / 1 |

These are paired edit-count directions, not a count of exactly correct strings.
DEV-B signer `c6e5` phone CER rises 64.06%→64.52%. Other signer means improve,
but weak signers remain: new phone CER ranges 34.32–65.90% in DEV-A and
31.22–68.10% in DEV-B. Macro signer CER is 46.90%/46.21% in the phone views.
Full per-signer results are in `signer_results.csv`; broad gains do not mean universal improvement.

| Sequence subgroup | DEV-A count | DEV-A native residual→4K | DEV-A phone residual→4K | DEV-B count | DEV-B native B2→4K | DEV-B phone B2→4K |
|---|---:|---:|---:|---:|---:|---:|
| J-containing | 59 | 51.60→43.60% | 53.07→48.53% | 61 | 47.89→42.66% | 51.62→47.14% |
| Z-containing | 52 | 49.93→43.31% | 52.97→49.52% | 25 | 46.00→38.86% | 46.00→41.71% |
| Adjacent repeated letters | 109 | 49.67→43.17% | 51.19→47.35% | 110 | 51.41→45.48% | 56.45→49.90% |

Lower subgroup **sequence CER** does not establish the special character is solved.
DEV-A J aligned matches fall 39→37 native and 36→35 phone versus residual.
DEV-B J changes 41→40 native and stays 34/65 phone versus B2; native Z falls
8→6/26, though phone Z rises 8→10/26. No exact J/Z sequence emerges in either new
DEV set/view. Repeated-letter sequence CER improves, but exact repeated-letter
strings remain absent in both phone views. Repeated-letter *buffer* correctness
and learned repeated-letter recognition are separate.

Aligned symbol counts improve for 21/27 native and 23/27 phone symbols in DEV-A
versus residual, and 22/27 native and 18/27 phone symbols in DEV-B versus B2.
Important regressions include DEV-B phone R 164→140/250 and Y 18→15/52; DEV-A
phone U 26→21/83. Q/X counts are too small for strong individual claims.
New phone U recall remains 25.3%/27.9%, V 26.2%/33.3%, and Z 37.9%/38.5% in
DEV-A/DEV-B. Rare symbols are not the only weak characters. The complete 27-symbol
before/after inventory is in `character_recall.csv`.

Across project length buckets (≤10, 11–20, >20 characters), new phone CER is
46.54/47.36/45.74% in DEV-A and 47.38/45.89/49.71% in DEV-B. The final DEV-B long
bucket has only eight sequences and should not support a confident subgroup conclusion.

Examples are illustrative, not a substitute for the complete paired inventory:

| Set / phone prompt | Prior output | New output | Finding |
|---|---|---|---|
| DEV-A `WEST COVINA CALIFORNIA` | `WETCOUYNACLIENUNIA` | `WETCOVINA CALIENRNIA` | Five fewer edits; still wrong |
| DEV-A `BANC` | `BAN CR` | `BANC` | Only exact phone DEV-A sequence |
| DEV-A `MONTGOMERY AL` | `MON GOMERY AL` | `MNGHOMERYAL` | Three more edits |
| DEV-B `BO ROSALES` | `BOROSALES` | `BO ROSALES` | Only exact phone DEV-B sequence; gain is a SPACE |
| DEV-B `JASON DUFFY` | `JASON DUEFY` | `IJASNDRFYA` | Five more edits |

## 5. What the 1K problems became

**Confirmed partial correction:** inadequate learned character discrimination and
generalization. Gains transfer to held-out signers/phrases, with fewer substitutions
and higher aligned-character precision. Expanded fine-tuning is a useful intervention.

**Already corrected before this run:** catastrophic sparse empty-output collapse
was addressed by B2 cadence-aware training. Old 1K references already have zero
DEV-A empty predictions. Do not credit the 4K run with fixing that problem anew.
Beam decoding was also already validated and held fixed.

**Not solved:** substantial missing/misidentified characters, whole-string spelling,
weak individual characters/signers, J/Z recall, and repeated-letter exactness.
DEV-A phone output/reference ratio is 0.850; DEV-B is 0.851. Mean emitted strings
remain too short even though some individual strings over-emit. New phone errors
are S/D/I = 771/686/167 and 746/659/155. Neither a blanket emission penalty change
nor a universal trim is justified by this mixed behavior.

**New/regression costs:** sparse insertions increase 144→167 on DEV-A and 126→155
on DEV-B; 49/46 individual phone sequences regress. These costs are real, but do not
erase the stronger correct-character and precision gains. No new cadence collapse,
non-finite training failure, role leakage or schema mismatch was found.

On the identical original 1,024 TRAIN sequences, frozen B2→4K fitting CER improves
39.07→35.27% native and 42.43→41.31% phone; correct counts increase 590/279.
Exact counts are 8→9 and 4→7, while empties increase 1→2 and 2→4. This is **fitting
evidence only**, not held-out accuracy. Full 4,096-source decoded TRAIN fitting was
not saved; do not claim it was evaluated or that TRAIN is now fitted well.

SPACE remains weak (native aligned matches 62/262 and 53/253), but letter errors
constitute most remaining errors. SPACE-only correction would not solve recognition.
Phone CTC-infeasible sequences remain explicitly included: two DEV-A and four DEV-B.
Most sequences are structurally feasible and still fail; passing CTC length is not accuracy.

## 6. Technical diagnosis: known, likely, uncertain

**Known:** The limiting observed behavior remains learned character discrimination
and deletion, rather than a demonstrated decoder/adapter/runtime correctness bug.
The fixed small geometry recognizer learns additional useful signal when expanded
supervision is supplied. The new result beats the actual old residual+beam candidate
on DEV-A, without any visual branch. The 1K regime was not sufficient for the desired
quality; 4K has not become sufficient either.

**Best-supported interpretation:** effective supervised instance/context coverage
was a material limitation. More examples made the same geometry/TCN family generalize
better. This weakens the claim that its representation had already hit a hard ceiling
or that a larger TCN/visual redesign was necessarily the next fix.

**Not uniquely established:** the proportion attributable to dataset size, continued
optimization, fresh Adam/lower learning rate, perception loss, or representation limits.
Warm-start and optimizer changes accompany expansion, so this is not causal proof of
dataset size alone. Weak TRAIN fitting and the surviving TRAIN/DEV gap both matter;
neither pure overfitting nor pure under-capacity explains all evidence.

**Critical remaining external uncertainty:** new-model phone-domain behavior. Earlier
AMY/BELLA sessions used the old residual model, had about 38–43% accepted-hand coverage,
and unverified signing. Their incorrect outputs cannot be assigned to this new model,
nor can offline sparse gains establish that it fixes those sessions. No complete RGB/raw
session capture exists in the current integration for a faithful retrospective new-model
phone replay. Actual new-model cadence, latency, hand coverage and spelling are unmeasured.

DEV-A is repeatedly development-exposed. DEV-B was final-only for this run, but is
now opened; do not turn it into a new tuning set or repeatedly reselect checkpoints
against it. Same DEV signers, ten shared phrases and all-DAUN DEV limit claims about
new humans, new recording domains, and population-wide generalization. No statistical
confidence interval or independent TEST result is asserted. Reflection remains the
accepted released-pixels research limitation.

## 7. Next step and why no further offline correction now

Advance epoch 38 to **one controlled geometry-only phone candidate**, separately
authorized after this handoff. Preserve the old B2/residual application for rollback.
The next gate should answer transfer to the target runtime, not optimize DEV another time:

1. Export the exact selected checkpoint as a new package; preserve 405 input/mask,
   28 logits, source timing, fixed beam/penalty and manual session/confirmation semantics.
   Verify FP32 Keras→TFLite→Android logits and exact decoded-text parity, including sparse,
   missing-hand and repeated/SPACE fixtures. Do not retrain or quantize without a new gate.
2. Make the smallest isolated FINGERSPELL model-package change. **The current exporter
   `tools/fingerspelling/android_export.py` is pinned to old residual epoch035 and B2
   epoch076; running it unchanged will not export the new model.** The current Android
   package uses a 1559-wide residual input and two interpreters. A new geometry-only
   package/explicit experimental selection is required; this is not an unverified asset swap.
   Reuse established adapter/decoder/ownership; do not silently simplify 405 features.
3. Do not attach the old residual correction to altered B2 states. It was learned against
   the old checkpoint, and equivalence with the new state is unproven. Avoid unnecessary
   appearance inference for this geometry-only candidate, while preserving the old path
   as a separately selectable rollback. Any implementation stays outside WORD internals.
4. Profile actual delivered cadence and Done latency. Then use a small predeclared set
   of clearly visible, verified fingerspelling attempts, preferably another proficient
   signer, to compare against the old candidate. Record raw output, intended transcript,
   observation count/cadence, accepted-hand coverage, session duration and errors. This
   is a required transfer gate, not a large accuracy benchmark or custom training collection.
5. Rerun existing exclusive-owner, WORD preservation, rollback and parity checks. Keep
   manual Start/Done/preview/confirmation, debug-only; no automatic route or release claim.

If export parity fails, repair export/package parity only. If live quality is much worse
than offline while parity passes, resolve the demonstrated phone capture/cadence/domain
issue before more FSboard training. If live roughly matches offline, keep the improved
candidate as experimental and decide further quality investment from that evidence.

Do **not** now extend epochs, tune blank/beam, reopen canonicalization/visual backbones,
build an outer segmenter, scale TCN capacity, or automatically expand again. The prior
1K finishing, capacity, visual and outer-boundary results do not demonstrate a high-
likelihood small repair; the completed run's plateau also provides no support for a
longer continuation. This recommendation does not prove those directions impossible.
It is the shortest justified next action under the deadline.

## 8. Validation, preservation and exact evidence

Review checks recompute aggregate CER, S/D/I, exact/empty counts, signer/subgroup
scores and character matches from **all stored** paired predictions, reproducing the
saved metrics. Selection/patience/history and complete cadence cycles also reproduce.
Twenty-four existing expanded-training/governance tests pass. Initial test execution
failed on Windows sandbox temporary-file rename permissions; rerunning with a fresh
workspace test directory passes all 24, without source changes. Initial failure XML
is retained; an unrelated pyreadline shutdown warning occurs after the successful run.

Before/after hashes of 1,130 existing protected source/config/model files match,
including both Android trees, model/pipeline code/assets and saved model candidates.
This is the stated inventory scope, not a claim that all video bytes were freshly
hashed or that a new WORD/device regression session ran. No protected component was
edited; no TEST payload was accessed; no model was exported/deployed/promoted here.

Only this handoff, new review script/evidence and appended progress/memory notes are
added. Existing predictions/history/checkpoints/manifests remain unchanged.

Primary evidence:

- `runs/fingerspelling_train4096_01/final_evaluation.json`: complete saved evaluation.
- `runs/fingerspelling_train4096_01/completion.json`, `confirmation_lock.json`,
  `run_identity.json`, `epochs/`, `resume_verification.json`: selection/run/governance.
- `artifacts/fingerspelling_outer_boundary_oracle_01/paired_evaluation.json`: exact
  same-DEV-A B2/residual **full-sequence beam** references; no oracle scores substituted.
- `artifacts/fingerspelling_quality_resolution_01/full_train_diagnostic.json`:
  original full-1K B2 fitting comparator.
- `artifacts/fingerspelling_train4096_review_01/analysis.json`: independently recomputed
  metrics, error compositions, length buckets, cohort/receipt/history verification.
- Same review directory: `paired_sequences.csv`, `character_recall.csv`,
  `signer_results.csv`, `training_history.csv`, `evidence_index.json`,
  `preservation_before.json`, `preservation.json`, `governance_tests.xml`,
  `analyze_saved_evidence.py`, `review_run.log`.

**Conclusion: a useful, broad partial improvement; advance the frozen 4K geometry
candidate to controlled phone validation, preserve the old fallback, and do not
represent this as reliable complete-spelling recognition.**

TRAIN4096_RETAIN_EPOCH038_CONTROLLED_DEVICE_VALIDATION_NEXT
