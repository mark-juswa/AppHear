# APPHEAR_FINGERSPELLING_BASELINE_02_RESULTS_REVIEW

2026-10-04. Review of the user's completed run, without new inference, training, extraction,
source acquisition, TEST payload access or Android modification.

## Decision

**Baseline 2 substantially addresses sparse-cadence under-emission. Continue research with
the existing Candidate01 ->405-column adapter ->causal TCN/CTC architecture.** Do not infer
that current phone cadence is inherently incapable from Baseline-1 results. Do not deploy
this model yet: character errors remain high and the calibrated checkpoint decodes zero
complete DEV strings correctly. Discrimination/generalization is still a substantial problem.

This is signer-disjoint offline DEV sequence analysis. The sparse view approximates phone
observation density; it is not live phone end-to-end recognition accuracy.

## Run and integrity

Branch `codex/current-working-text-to-asl-baseline-2026-09-29`, HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358`; protected WORD baseline remains
`baseline/apphear-s2-r2-integration-complete-2026-09-26` at
`76d93cecd85bf9f76064d320aa4a5791b5f0704a`.

Run `runs/fingerspelling_ctc_baseline_02` completed **79 epochs**, with frozen early stopping.
Best balanced raw native/sparse DEV CER was at **epoch 76**. The patience anchor and the
strict best-checkpoint score have distinct improvement rules: modest improvements at epoch
76 did not reset the 0.002 meaningful-improvement patience anchor. Recomputing all 79
selection scores and patience states reproduced the recorded best epoch and stop condition.

Selected model SHA-256:
`64f425358ef30e21a4aca18795226854f7aa44a34c3bc3e54a8c06366cb61397`.
Run policy, adapter, code, original encoder/config, manifest and aggregate source/raw/features
lineage identities match the present frozen foundation. Model hash matches completion,
final evaluation and decoder calibration. Original 1,024 TRAIN /256 DEV signer-disjoint
inventory and DEV policy remain intact; no additional data or roles were introduced.

All saved text predictions and aggregate/signer/J/Z/repetition edit metrics were independently
recomputed across **79 epochs**, as were final calibration-candidate text metrics. All 256
official DEV identities/transcripts/signers match receipts. Raw final-evaluation results equal
the saved epoch-76 evaluation exactly. Emission posterior/argmax quantities are reviewed as
logged; checkpoint tensors were not rerun in this review.

## Baseline comparison

Each view covers the same 256 held-out DEV sequences and 3,457 reference characters.
Lower CER is better; CER is not sequence accuracy or percentage of correctly recognized words.

| Metric | B1 native | B2 raw native | B2 calibrated native |
|---|---:|---:|---:|
| CER | 60.83% | 58.43% | 55.05% |
| Substitutions | 366 | 386 | 582 |
| Deletions | 1,716 | 1,592 | 1,219 |
| Insertions | 21 | 42 | 102 |
| Predicted characters | 1,762 | 1,907 | 2,340 |
| Empty predictions | 8 | 5 | 3 |
| Exact sequences | 0 | 1 | 0 |

| Metric | B1 sparse | B2 raw sparse | B2 calibrated sparse |
|---|---:|---:|---:|
| CER | 94.68% | 54.82% | 54.47% |
| Substitutions | 63 | 733 | 968 |
| Deletions | 3,210 | 1,063 | 729 |
| Insertions | 0 | 99 | 186 |
| Predicted characters | 247 | 2,493 | 2,914 |
| Predicted/reference ratio | 7.15% | 72.11% | 84.29% |
| Empty predictions | 106 | 1 | 0 |
| Exact sequences | 0 | 0 | 0 |

Raw sparse CER improves by **39.86 percentage points**, before calibration. Raw sparse
deletions fall by 66.88%; calibrated sparse deletions fall by 77.29% relative to B1.
This is not just output inflation from adjusting the decoder. The main sparse improvement
is already present at zero blank penalty. Native raw CER improves modestly by 2.40 points.

For a fair calibration comparison, the prior bounded B1 diagnostic at penalty 1.5 achieved
native 55.02% /sparse 87.39%. B2's calibrated native 55.05% is approximately unchanged from
that diagnostic, while calibrated sparse 54.47% is substantially better. B2 also had a longer
training budget and different checkpoint-selection rule; no ablation establishes how much
of the improvement is exclusively due to cadence-aware views.

## Emission and calibration

B2 raw blank argmax fractions are 91.81% native /61.84% sparse, versus 89.39% /54.65% after
calibration. Raw sparse emits on 38.16% of real timesteps, rising to 45.35% with calibration.
Average decoded lengths: raw 7.45 native /9.74 sparse; calibrated 9.14 /11.38. The mean
reference length is 13.50 characters. Padding timesteps do not enter these statistics.

The frozen bounded DEV sweep selects **blank-logit penalty 0.5**. Mean raw CER is 56.62%,
calibrated 54.76%. Only 0.5 passes the predetermined nonzero acceptance safeguards;
larger penalties are not adopted. The chosen value is bound to the epoch-76 model hash in
`runs/fingerspelling_ctc_baseline_02/decoder_calibration.json`.

Calibration reduces sparse deletions 1,063 ->729 but increases substitutions 733 ->968 and
insertions 99 ->186. Sparse CER consequently improves only 0.35 percentage points. Sparse
insertion rate is 5.38%, versus 2.86% raw; native is 2.95%, versus 1.21% raw. This passes the
frozen safeguard but is a real tradeoff. Emitting more characters is not equivalent to
discriminating them correctly. Further blank-penalty tuning is not the next recommended step.

Calibration also removes the raw native model's one exact string. A mean-CER decoder
criterion did not preserve that isolated success. Complete-sequence recognition remains
insufficient despite much better character-level behavior.

## Signers and subgroups

All **15/15 held-out DEV signers** improve sparse CER against B1, both raw and calibrated;
native improves for 10/15 raw and 12/15 calibrated. This rules out the aggregate sparse gain
being confined to one held-out signer. However calibrated sparse signer CER still spans
**38.14%–74.65%**. Cross-signer errors remain substantial.

| Subgroup | Sequences | B2 raw native CER | B2 raw sparse CER | B2 calibrated sparse CER |
|---|---:|---:|---:|---:|
| J-containing | 59 | 58.67% | 54.67% | 54.93% |
| Z-containing | 52 | 59.31% | 56.97% | 56.41% |
| Repeated-letter | 109 | 57.16% | 54.38% | 53.51% |

Sparse aligned character recall is 51.61% J /27.59% Z raw and 56.45% /32.76% calibrated.
Those are diagnostic alignment recalls, not temporal-letter or phone-recognition accuracy.
No special letter rules were added. Length-stratum and signer details remain in the final
evaluation. DEV is DAUN only; held-out MacKenzie performance is still unestablished.

## Temporal training, feasibility and timing

Every epoch retains all 1,024 TRAIN sources. Requested view counts over 79 epochs are
26,958 native /26,973 intermediate /26,965 phone. The sample/seed/epoch regime schedule
matches the frozen policy. There are 604 recorded feasible-denser fallbacks over 19 unique
sources: 394 phone->intermediate, 104 phone->native and 106 intermediate->native.
No artificial frames or new feature artifacts were introduced. Native/phone CTC minima
remain as in the foundation: 256/256 native feasible, 254/256 sparse feasible; the two
impossible sparse DEV cases remain in all decoded metrics, excluded only from sparse loss.

Epoch-76 mean TRAIN CTC loss is 29.79, native DEV eligible loss 24.40, sparse DEV eligible
loss 30.99. These losses have different temporal inputs and are not a substitute for TRAIN
decoded CER or evidence that overfitting has been ruled out.

Median epoch 50.15 seconds; p95 55.76 seconds; summed epoch durations **67.43 minutes**.
This excludes separate preflight/final-evaluation and interrupted/unlogged operations, so it
is not a measured complete wall-clock session duration.

## Next technical direction

1. Retain this result as a successful correction of the severe sparse under-emission failure.
   Keep Candidate01, the 405 adapter, TCN family and governed data contracts stable.
2. Before launching another long run or expanding data, do a bounded current-checkpoint
   TRAIN-vs-DEV decoded comparison and character-confusion/error inspection. This will help
   distinguish fit/discrimination limits from cross-signer generalization. It requires later
   authorization; no additional inference was performed here.
3. Use that result to propose one controlled expansion of the governed TRAIN tranche or a
   focused training refinement. Do not make another broad architecture or dataset search.
4. Do not switch to runtime-cadence redesign merely from B1's sparse failure: B2 demonstrates
   much more usable sparse evidence in this approximation. Actual Xiaomi alphabet inference,
   streaming boundaries, TFLite parity and end-to-end spelling remain untested.

No automatic new run, additional acquisition, feature change or Android ABC integration is
authorized by completion of this review. TEST stays sealed, and WORD/Context Assist remain
protected. Evidence: `artifacts/fingerspelling_baseline2/review_02.json`; source report:
`runs/fingerspelling_ctc_baseline_02/final_evaluation.json`.

BASELINE2_COMPLETE_RESEARCH_IMPROVEMENT_NOT_DEPLOYMENT_READY
