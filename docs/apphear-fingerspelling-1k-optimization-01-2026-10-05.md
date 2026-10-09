# AppHear fingerspelling: existing 1K optimization check

Status: `ONE_K_FINISHING_NOT_SUPPORTED_KEEP_CURRENT_MODEL`; 4K remains paused.

## Conclusion

The existing 1K recognizer has **not been demonstrated to have exhausted its potential**.
There is also no demonstrated preprocessing, CTC, decoder, or Android correctness bug
whose repair would explain the remaining quality problem. The verified limitation is
weak learned character discrimination, incomplete TRAIN fitting, and poorer recognition
on held-out signers. That is a recognition failure description, not proof of one exclusive
physical cause.

The most concrete unfinished training opportunity was a lower-learning-rate finishing
stage. It has now been implemented and tested once on the existing data. The result does
**not** support replacing the current candidate: native CER improved slightly, but
phone-like CER and its substitution/precision behavior worsened. Do not promote this
checkpoint or launch its longer continuation. Do not infer from three epochs that every
possible 1K training improvement has been ruled out.

The earlier recommendation that more supervision is the most practical next intervention
remains a hypothesis. It was too strong to treat it as proof that 1K cannot reasonably
improve. This report supersedes the previous automatic next-action recommendation to
prepare TRAIN-4096. No expansion was acquired or processed here.

## Evidence inspected before implementation

Actual sources: `model/fingerspelling_baseline2.py`, `fingerspelling_ctc.py`, compiled
training/loss execution, temporal feature cache/views, Adapter.v1, prefix beam decoding,
foundation manifest/receipts, B1–B4/residual evaluations, the decoder audit and the
publisher-window oracle. Existing train/serve parity and protected Android evidence
were retained rather than rerun or redesigned.

The original B2 uses a 193,116-parameter causal TCN, 64 channels, kernel3,
dilations1/2/4/8, two temporal convolutions per block, stride1, and a61-observation
receptive field. It uses Adam at a **constant0.001**, batch8, dropout0.1, clipnorm5,
and the mean of unnormalized sequence CTC losses. No annealing stage is present.

B2's last recorded epoch is79; best checkpoint76. The patience anchor remained at64
because the new best checkpoints72/73/76 did not clear the frozen0.002 improvement
threshold. This is the policy working as written, **not a code bug**. TRAIN CTC loss
was still falling/noisy:31.15 at60,30.73 at64,29.73 at72,29.79 at76,29.20 at79.
Original selection used uncalibrated greedy DEV output; the deployed fingerspelling
decoder now uses fixed beam10/blank penalty0.5. That selection mismatch is real,
but its contribution to the quality problem has not been isolated.

Previous full1024 TRAIN inference with frozen B2/beam shows native CER39.07% and
phone-like42.43%, versus DEV50.19%/52.70%. These TRAIN values are fit diagnostics.
High observed-hand coverage TRAIN still has32.15%/35.98% CER, so missing evidence
does not explain every error. Q has20 and X28 TRAIN occurrences; common-character
errors remain as well. Sparse supervision and inconsistent observations are plausible
contributors, but the records cannot separate their causal contributions conclusively.

Larger capacity, canonicalization and visual approaches did not establish broad gains.
Publisher-window trimming worsened recognition. These failures are not proof of a hard
Candidate01 information ceiling. No new detector, representation or boundary component
is justified by this check.

## One controlled existing-data intervention

New isolated files:

- `model/config/fingerspelling_1k_optimization_01.json`
- `model/fingerspelling_1k_optimization.py`
- `tests/test_fingerspelling_1k_optimization.py`

Only an immutable copy of B2 epoch076 was trained, with fresh Adam at0.0001. The original
weights, architecture, features, loss, targets, cadence selection/fallback and decoder
were unchanged. Fresh Adam avoids mixing epoch79 optimizer state with epoch76 weights.
The old residual projection was not attached to a changed B2 state: its learned
correction belongs to the original frozen backbone.

Exactly three epochs used all1024 original TRAIN sequences. Every sequence requested
native, intermediate and phone views once; valid denser fallback occurred6/9/8 times.
No observation was manufactured and no sequence was dropped. Epoch CTC losses were
27.10,28.27,27.18. Their reduction is not a held-out quality improvement claim.

The gate evaluates **only the predefined final third epoch**, not the best of three
interim DEV results. Both views use all256 original DEV-A sequences, beam10, blank27,
and penalty0.5. The fixed support policy required a2-percentage-point balanced CER gain
plus both-view character/precision/signer improvement. This is an engineering effect-size
floor, not a production accuracy requirement; it was frozen before evaluation.
The observed phone regression independently fails the policy regardless of that floor.

## Full DEV-A results

Every row uses the same3457 reference characters and256 sequences. Lower CER is better.

| Model | Native CER | Phone-like CER | Balanced CER | Native correct chars | Phone correct chars |
|---|---:|---:|---:|---:|---:|
| Frozen B2 + beam |50.19%|52.70%|51.45%|1916|1775|
| Current frozen residual + beam |49.52%|52.16%|50.84%|1954|1798|
| One lower-rate finishing cycle |49.23%|53.05%|51.14%|1897|1802|

| View/model | Substitutions | Deletions | Insertions | Predicted chars | Correct/predicted precision | Exact strings |
|---|---:|---:|---:|---:|---:|---:|
| Native/current residual |679|824|209|2842|68.75%|0|
| Native/finishing |614|946|142|2653|71.50%|0|
| Phone/current residual |920|739|144|2862|62.82%|0|
| Phone/finishing |990|665|179|2971|60.65%|1|

The native CER gain comes with57 fewer correct characters and122 more deletions.
Phone-like output adds109 predicted characters but only4 correct characters, with
70 more substitutions and35 more insertions. Balanced CER is0.30 percentage points
worse than the current candidate. Seven of15 signers improve and seven regress in
each view versus the current residual; one is unchanged. There is no broad support
pattern. One exact phone-like string (`JOSH PATEL`) does not outweigh the aggregate
regression. All per-character/signer/J/Z/repeat metrics and predictions are retained.

These are held-out FSboard DEV sequence metrics, with a phone-like sampling approximation.
DEV has been reused during development; this is not untouched TEST confirmation or a
real-phone accuracy claim. The two structurally infeasible phone sequences are retained.

## Engineering and preservation

36 focused tests pass; Ruff and mypy pass. Initial B2 DEV CER, S/D/I and correct-character
counts reproduce the archived reference exactly. Repeating the completed gate restores
the model/Adam/epoch digest exactly, runs zero extra epochs, and retains the same result.
Bit-exact stochastic continuation after an interrupted epoch is not claimed.

Separate run: `runs/fingerspelling_1k_optimization_01/`. Its identity pins source/config,
adapter, original manifest and data lineage. A failed quality gate refuses the longer
`train` command. Nothing automatically exports or replaces the application model.

Research branch: `codex/current-working-text-to-asl-baseline-2026-09-29`; HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358`. Protected application baseline:
`baseline/apphear-text-to-asl-context-assist-ui-2026-10-04` at
`cee71d9f181695847936eb5f3605ea37eab82a95`. Existing unrelated modified/untracked
Android/research/data files were preserved. No reset/merge/switch or deletion occurred.

All11506 inventoried protected files remain hash-identical: WORD, both Android trees,
Candidate01, Adapter.v1, original sources/raw/features, original model checkpoints,
visual logic/artifacts and earlier evaluation evidence. TEST and DEV-B performance
remain untouched. No acquisition, Candidate01 extraction or long training was launched.

## Decision and next action

Keep the current residual+beam candidate and frozen B2 reference. Do not deploy the
finishing checkpoint; do not override its failed gate. 4K stays paused. No meaningful
existing-data quality fix was established, and no unique physical root cause or exhausted
1K ceiling can honestly be claimed from the available evidence.

A longer convergence check could answer more about optimization, but it would be
another training experiment, not a demonstrated fix. It is not launched or prescribed
as a guaranteed improvement here. Likewise, data expansion would be a controlled
supervision intervention, not the repair of a proven dataset-size defect. Review this
negative result before choosing either investment; there is no automatic next run.

Evidence: `artifacts/fingerspelling_1k_optimization_01/validation.json`, `review.json`,
`preservation.json`, `tests.xml`; full outcome:
`runs/fingerspelling_1k_optimization_01/gate_result.json`.

ONE_K_FINISHING_NOT_SUPPORTED_KEEP_CURRENT_MODEL
