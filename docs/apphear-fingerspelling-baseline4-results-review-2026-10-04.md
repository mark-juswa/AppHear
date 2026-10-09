# AppHear Fingerspelling Baseline 4 — completed results review

**Decision: BASELINE4_COMPLETE_MIXED_NO_REPLACEMENT.** The capacity gate showed that the wider TCN can fit a small repeated TRAIN subset better. Full-tranche training did not turn that into a clear recognition improvement. Retain calibrated Baseline 2 as the best completed research reference; preserve B4 as evidence. No further training, data acquisition, feature redesign or Android integration was started in this review.

## Verified execution and preservation

Branch `codex/current-working-text-to-asl-baseline-2026-09-29`, HEAD `cc1f3949114d0ed1dab38d4428191151b37df358`. Protected WORD ref remains `baseline/apphear-s2-r2-integration-complete-2026-09-26` (`76d93cecd85bf9f76064d320aa4a5791b5f0704a`). Existing dirty/untracked work preserved.

Run: `runs/fingerspelling_ctc_baseline_04`. Trained 55 epochs; frozen early stopping after 15 non-improving epochs; best raw balanced DEV checkpoint is epoch 40. Checkpoint SHA `d4c703fdc513321154392e472bded5528041be42149eb26e4f45d32d6db9a522` matches the saved model, completion and final report. Configuration/code/data/adapter identity matches the current frozen runner. This is the intended fresh 558,236-parameter width-128 TCN, not fit-gate fine-tuning.

All 55 reports are chronological; recomputed balanced DEV selection and patience produce the reported checkpoint/stop. Saved final TRAIN/DEV predictions match epoch40. All 1,024 TRAIN sources were retained every epoch with feasible training views. The sparse DEV's two structurally infeasible sequences remain in decoding metrics, excluded only from CTC loss. No TEST access, production promotion or failure artifact. Recorded epoch time sums to 4,349.92seconds (72.5minutes), excluding separate preflight/final evaluation overhead.

The original 1,265-file protected/research snapshot remains unchanged. Candidate01, raw-v1, adapter v1 `[T,405]`, governed1,024/256 manifest, official signers/DEV policy, B1–B3 source/checkpoints, Android WORD behavior and Context Assist remain unchanged. Integrity evidence: `artifacts/fingerspelling_baseline4/results_integrity.json` and `preservation_after.json`.

## Selected-checkpoint comparison

Same 256 signer-disjoint DEV sequences, 3,457 reference characters per view. These are FSboard sequence diagnostics; sparse sampling is a phone-cadence approximation, not measured end-to-end phone recognition.

| DEV metric | B2 | B4 | Interpretation |
|---|---:|---:|---|
| Raw native CER | 58.43% | 55.71% | 2.72points better |
| Raw sparse CER | 54.82% | 56.09% | 1.27points worse |
| Raw balanced CER | 56.62% | 55.90% | 0.72points better overall, mixed views |
| Selected blank penalty | 0.5 | 0.0 | Existing bounded procedure unchanged |
| Calibrated balanced CER | **54.76%** | 55.90% | B2 remains 1.14points better |
| Native exact strings | 1/256 | 0/256 | No complete-string gain |
| Sparse exact strings | 0/256 | 0/256 | No complete-string gain |
| Native empty strings | 5 | 4 | Small improvement |
| Sparse empty strings | 1 | 3 | Worse |

B2 calibrated native/sparse CER is55.05%/54.47%. Compare raw to raw when isolating the encoder; compare selected calibrated outputs when choosing the best completed system. B4 calibration candidates0/0.5/1/1.5/2 have combined CER55.90/55.94/58.88/64.64/74.36%; no nonzero penalty qualified. Additional blank tuning is not supported.

| Raw errors | B2 native | B4 native | B2 sparse | B4 sparse |
|---|---:|---:|---:|---:|
| Substitutions | 386 | 598 | 733 | 852 |
| Deletions | 1,592 | 1,224 | 1,063 | 946 |
| Insertions | 42 | 104 | 99 | 141 |
| Predicted/reference ratio | 55.16% | 67.60% | 72.11% | 76.71% |
| Blank argmax fraction | 91.81% | 89.56% | 61.84% | 58.61% |

Native deletions fell368, but substitutions rose212 and insertions62. Sparse deletions fell117, while substitutions rose119 and insertions42. Sparse correctly aligned reference characters are1,661 for B2 versus1,659 for B4: additional output did **not** increase aggregate correct-character coverage in that view. This supports an emission/error tradeoff, not a broad sparse discrimination improvement. CTC blank occupancy alone is not evidence of a failure cause.

## TRAIN fitting and convergence

The same historical64 TRAIN diagnostic examples (1,134 reference characters) were decoded at the DEV-selected checkpoint. These are seen-signer fitting diagnostics, not held-out accuracy.

| Fixed TRAIN64 metric | B2 best DEV checkpoint | B4 best DEV checkpoint |
|---|---:|---:|
| Native CER | 48.24% | **48.24%** |
| Sparse CER | 43.12% | 43.56% |
| Native S/D/I | 86/451/10 | 143/374/30 |
| Sparse S/D/I | 169/297/23 | 184/276/34 |
| Native exact strings | 1/64 | 0/64 |
| Sparse exact strings | 0/64 | 0/64 |

The full run does not reproduce the gate's striking native46.83%/sparse22.93% fitting pattern at the checkpoint chosen for generalization. That gate repeatedly fitted only64 examples; the full run fits1,024 varied examples. Its success proves learnability on those examples under those conditions, not adequate full-corpus discrimination.

| B4 epoch | TRAIN native/sparse CER | DEV native/sparse CER |
|---|---|---|
| 20 | 63.93% /54.85% | 67.83% /61.93% |
| 40, selected | 48.24% /43.56% | 55.71% /56.09% |
| 49, lowest balanced TRAIN diagnostic | 42.24% /39.07% | balanced57.62% |
| 55, final | 46.74% /38.89% | 57.62% /57.13% |

Later epochs demonstrate some additional TRAIN fitting, with weaker DEV. Epoch49's balanced TRAIN CER is40.65%; that is a post-hoc fitting observation, **not** an alternative checkpoint selection or a fair optimum comparison against B2. Lowest native TRAIN occurs49; lowest sparse TRAIN37.57% occurs51; do not combine minima from different checkpoints. Loss falls30.29 at selected40 to26.98 at55. Continued loss reduction is not sufficient to justify more epochs: later generalization does not improve under the frozen rule.

**Interpretation:** the evidence is more nuanced than “capacity has no effect” or “capacity is now solved.” Width helps controlled small-subset fitting; full-tranche diagnostic fitting is still limited and later improvements do not carry to DEV. Optimization, information sufficiency and diversity/generalization remain plausible contributors. Neither a hard feature-information ceiling nor a cadence impossibility has been established. The sparse model is not returning to Baseline1's collapse, so perception cadence is not the demonstrated primary new bottleneck here.

## Characters, signers and difficult groups

- Native DEV recall:16 of27 characters improve,9 worsen,2 tie. Sparse:14 improve,10 worsen,3 tie. Mixed recall; no broad consistent discrimination improvement. Levenshtein character alignment supplies these diagnostics, not letter boundaries.
- Native signer CER improves10/15, worsens5/15. Sparse improves5/15, worsens8/15, ties2/15. Sparse worst-signer CER worsens74.19%→80.65%; macro signer CER54.78%→56.06%.
- J-containing DEV sequence CER: native58.67%→55.47%, sparse54.67%→56.13% (59sequences). J character recall native51.61%→56.45%, sparse51.61%→48.39%.
- Z-containing DEV sequence CER: native59.31%→55.59%, sparse56.97%→59.59% (52sequences). Z character recall native25.86%→37.93%, sparse27.59%→29.31%; slight recall gain does not overcome other errors in the strings.
- Repeated-letter DEV sequence CER: native57.16%→55.50%, sparse54.38%→55.04% (109sequences). No complete strings in either B4 view.

These are subgroup diagnostics from one training run; rare-character changes and small aggregate differences are not statistical proof of superiority.

## Recommendation and boundary

1. Keep B2 with its selected0.5 blank penalty as the best completed research reference. Preserve B4 model/reports and the successful fit gate. Do not deploy either as production fingerspelling recognition.
2. Do not increase TCN width/depth again, retrain longer, revisit canonicalization, expand the corpus or tune blank penalties automatically. The proposed capacity correction did not yield the required joint TRAIN/generalization pattern.
3. Recommended next **bounded diagnostic**, to be scoped separately: compare native/sparse decoding on the entire existing1,024 TRAIN inventory for saved B2/B4 checkpoints, characterize error/hand-evidence quality and TRAIN/DEV gaps. The present64-source diagnostic alone cannot establish full TRAIN fit. Separate optimization/alignment, observation discrimination and diversity effects before selecting one next intervention. Reuse existing raw/features; no new Candidate01 extraction or TEST performance.

This is a partial fitting/generalization warning rather than clean OutcomeA, strong OutcomeB or proof of OutcomeC's presumed information limit. More signer/sequence diversity may eventually help, but the current evidence does not justify automatically launching that investment or another model run.

No new inference/training, architecture, feature or runtime changes were needed to verify these saved results. Progress and memory record completion; the previous user-run-ready state is superseded.

BASELINE4_COMPLETE_MIXED_NO_REPLACEMENT
