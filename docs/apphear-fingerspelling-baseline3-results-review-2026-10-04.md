# APPHEAR_FINGERSPELLING_BASELINE_03_RESULTS_REVIEW

2026-10-04. The user completed training and final evaluation. This review recomputes saved
text metrics and performs one bounded inference-only TRAIN-fit diagnostic on the **existing
fixed 64-source subset**. No new training, acquisition, Candidate01 inference, TEST payload
access, Android change or production-model replacement.

## Decision

**Keep Baseline 2 /adapter v1 as the research reference. Baseline 3 does not justify replacing
it or continuing to tune the canonicalizer.** Preserve the completed B3 model, separate v2
data and implementation as a documented result; do not delete/rewrite them or revert unrelated
work. The protected WORD recognizer continues unchanged, and no fingerspelling model is deployed.

Native DEV improves slightly, but sparse DEV worsens, substitutions rise, sparse signer spread
worsens, and exact strings remain zero. The same fixed TRAIN subset also decodes worse.
This particular canonical representation has not demonstrated the intended discrimination
or generalization improvement. This does **not** prove that stable physical-hand tracking is
inherently useless or that Candidate01/CTC is impossible: input capacity, retained evidence,
initialization and training trajectory also differ, with no replicated ablation.

All numbers below are offline sequence diagnostics. DEV signers are held out, but the
quantized sparse view is not live-phone end-to-end accuracy. TRAIN diagnostics are fit-only.

## Verified run and preservation

Branch `codex/current-working-text-to-asl-baseline-2026-09-29`; HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358`. Protected WORD baseline
`baseline/apphear-s2-r2-integration-complete-2026-09-26` remains
`76d93cecd85bf9f76064d320aa4a5791b5f0704a`.

B3 completed **64 epochs** with frozen early stopping; best balanced raw DEV checkpoint
**epoch 49**. Its model SHA:
`e8be293d74c64ebfdd628b00e822545b39004d57318cc098d667f6bea9c4a68e`.
Selection and 15-epoch patience state recompute correctly. Current code/config/adapter/
temporal policy and aggregate lineage match the recorded run identity. All 1,280 actual
feature-file checksums match their receipts; the governed 1024 TRAIN/256 DEV roles remain.

All 64 epochs' saved predictions, aggregate/signer/subgroup edits, character recalls/confusions
and selection scores were recomputed. Official DEV IDs/transcripts/signers match all 256
receipts; final raw evaluation equals epoch49's saved evaluation. Calibration candidates'
text metrics also recompute. Logged logits/posterior quantities are not independently rerun.
All 99 completed B3 run files, 189 prior fingerspelling files/run artifacts and 883 protected
files remain byte-identical during review. No reset/merge/staging/branch switch.

## Baseline comparison

Same 256 DEV sequences and 3,457 reference characters in both views. Lower CER is better;
CER is an edit rate, not percentage of correctly recognized words or complete sequences.

| Metric | B2 raw native | B3 raw native | B2 raw sparse | B3 raw sparse |
|---|---:|---:|---:|---:|
| CER | 58.43% | 57.33% | 54.82% | 56.73% |
| Substitutions | 386 | 578 | 733 | 952 |
| Deletions | 1,592 | 1,329 | 1,063 | 847 |
| Insertions | 42 | 75 | 99 | 162 |
| Predicted characters | 1,907 | 2,203 | 2,493 | 2,772 |
| Predicted/reference ratio | 55.16% | 63.73% | 72.11% | 80.19% |
| Empty predictions | 5 | 3 | 1 | 2 |
| Exact strings | 1 | 0 | 0 | 0 |

Native improves **1.10 percentage points**, sparse worsens **1.91 points**. Raw balanced CER
worsens **56.62% ->57.03%** (+0.40 points). B2's governed calibrated combined CER is 54.76%;
B3 retains zero penalty and 57.03%, a 2.27-point regression between selected decoders.
The raw/raw comparison is the primary representation comparison.

Sparse deletions fall by 216, but substitutions rise by 219 and insertions by 63. Correctly
aligned sparse reference characters are essentially unchanged: 1,661 ->1,658, despite 279
extra predicted characters. Native correctly aligned characters rise 1,479 ->1,550, but
complete strings disappear. This is largely a different emission/error tradeoff rather than
the desired broad discrimination improvement.

## Character recall, signers and subgroups

Native aligned recall improves for 13 letters, worsens for 10, is unchanged for three.
Sparse improves for 11, worsens for 13, is unchanged for two. SPACE is recorded separately.
Full confusion matrices include deletion and insertion counts, not invented letter timing.

| Sparse aligned character recall | References | B2 | B3 |
|---|---:|---:|---:|
| J | 62 | 51.61% | 37.10% |
| Z | 58 | 27.59% | 24.14% |
| M | 84 | 47.62% | 33.33% |
| E | 335 | 52.24% | 46.57% |
| L | 202 | 33.17% | 42.08% |

This is mixed behavior, not a broad recall gain. Rare-character counts limit interpretation.
No letter-specific rule or tuning is warranted from these diagnostics.

Native CER improves for **9/15** signers and worsens for six. Sparse improves for **4/15**
and worsens for eleven. Native signer CER population standard deviation narrows 10.96 ->9.81
percentage points; sparse widens 8.81 ->9.62 points. Sparse range changes from
40.25%–74.19% to 45.19%–77.88%. No statistical-significance or replication claim.

| Subgroup | Sequences | B2/B3 native CER | B2/B3 sparse CER |
|---|---:|---:|---:|
| J-containing | 59 | 58.67% /57.87% | 54.67% /60.13% |
| Z-containing | 52 | 59.31% /58.76% | 56.97% /59.03% |
| Repeated-letter | 109 | 57.16% /58.62% | 54.38% /55.77% |

DEV is DAUN-only and follows the frozen phrase policy/challenge-enriched tranche;
held-out MacKenzie and phone-domain generalization remain unestablished.

## TRAIN fit and next technical priority

Inference uses the same preselected 64 TRAIN sequences as the earlier B2 diagnostic:
32 per stratum, 42 unique official signer identities. Same IDs/transcripts, raw models'
greedy decoding and native/sparse views; no new subset selection or training.

| Diagnostic | B2 | B3 |
|---|---:|---:|
| Native TRAIN CER | 48.24% | 49.91% |
| Sparse TRAIN CER | 43.12% | 45.77% |
| Native substitutions/deletions/insertions | 86 /451 /10 | 133 /418 /15 |
| Sparse substitutions/deletions/insertions | 169 /297 /23 | 236 /245 /38 |
| Native/sparse exact strings | 1 /0 | 0 /0 |

B3 has not shown better fit on this fixed TRAIN sample. It is not the case where TRAIN
became strong while DEV remained poor. This supports the user's **both remain poor** decision
path: investigate fit/capacity/optimization or retained information before assuming more data
alone will solve it. It does not prove underfitting: the diagnostic is bounded and uses
DEV-selected checkpoints at different epochs, not a full-TRAIN fit study.

Recommended next investment: a bounded, explicitly planned fit/capacity/information diagnostic
using the preserved B2 representation and existing data. Consider a modest same-family TCN
revision only if that evidence supports it. Do not automatically start Baseline4, enlarge the
corpus, tune canonicalizer thresholds, change Candidate01, choose another encoder or integrate
Android. Preserve the demonstrated B2 cadence benefit and the B3 negative/mixed result.

## Calibration, feasibility and timing

The bounded policy selects blank penalty **0.0**. Penalty0.5 changes mean CER from57.0292%
to56.9280%, only0.10 points, below the frozen0.5-point minimum improvement; sparse CER also
worsens to58.09%. Larger penalties worsen combined CER. Do not relax the safeguards or
continue blank tuning to rescue this run.

B3 raw blank argmax fractions are90.33% native /56.47% sparse, lower than B2's91.81% /61.84%.
This corroborates increased emission, not improved character discrimination. Epoch49 TRAIN
mean CTC is32.13, DEV eligible native/sparse loss26.81/32.19; these different-view losses do
not substitute for decoded fit metrics.

All1024 TRAIN sources remain represented each epoch. Across64 epochs, requested counts are
21838 native /21853 intermediate /21845 phone, with489 denser feasible fallbacks and no
negative chosen-view headroom. DEV retains256 native /256 sparse predictions;254 sparse
sequences are CTC-feasible and the two impossible cases remain in CER, excluded only from loss.
No fake frames or target relabeling.

Median epoch45.34 seconds, p95 51.62; summed epoch durations49.99 minutes. This excludes
preflight, final evaluation and unlogged interruptions and is not a full-session wall clock
or a controlled speed benchmark.

## Evidence and boundaries

Machine review: `artifacts/fingerspelling_baseline3/results_review_01.json`;
reproducible saved-metric script: `results_review_01.py` in that folder.
Bounded TRAIN inference: `completed_train_diagnostic.json`; the original diagnostic manifest
remains unchanged. Completed model/predictions: `runs/fingerspelling_ctc_baseline_03`.

V2 changes several things together: canonical association, removal of full secondary geometry,
new fingertip/state features, reduced input-kernel parameter count (154716 vs193116), and fresh
initialization. Same hidden TCN architecture/policy does not make this a single-variable
ablation. No root cause is established from this result. Reflection remains the accepted
as-is research limitation; TEST remains sealed; Candidate01, WORD and Context Assist unchanged.

BASELINE3_COMPLETE_CANONICALIZATION_NOT_SUPPORTED_AS_REPLACEMENT
