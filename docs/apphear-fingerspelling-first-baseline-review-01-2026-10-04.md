# AppHear first fingerspelling baseline review 01

2026-10-04. **First research baseline completed; model is not ready for deployment.**
One user-run optimized causal TCN/CTC experiment finished 30 epochs. No second experiment,
additional acquisition/extraction, TEST evaluation or Android change was launched by this review.

## Recorded run and integrity — VERIFIED

Run: `runs/fingerspelling_ctc_fast_01`.
Branch: `codex/current-working-text-to-asl-baseline-2026-09-29`.
HEAD: `cc1f3949114d0ed1dab38d4428191151b37df358`.

All 30 epoch reports exist and have finite recorded training losses. Completion and committed
epoch agree on epoch 30 and its best-native-DEV-CER checkpoint. Saved source/config/adapter
hashes match current files; the frozen manifest and 1,280 feature-receipt lineage aggregate
match the run identity. Each epoch's saved predictions contains exactly the 256 governed DEV
sample IDs, matching transcript and official signer. Text metrics were independently
recomputed from all saved epoch predictions and matched the reports.

This is report/code/receipt verification, not a fresh raw-to-feature recomputation or model
inference rerun. Recorded validation declares no TEST payload access; this review accessed
only the TRAIN/DEV manifest, receipts and training reports. Original WORD/runtime remains
protected; no recognition code/config/model change occurred.

Best model: `runs/fingerspelling_ctc_fast_01/best_candidates/epoch_030.keras`.
SHA-256: `29c07b51000512e60ae3ec01b7d5163210ea966566039f48e5de45c9f5c9bd2d`.
Selection uses lowest native DEV CER, first tie, as frozen before training; phone results
below are from that same selected checkpoint, not an independently selected phone checkpoint.

## Held-out DEV results — VERIFIED

256 sequences, 15 official DEV signers, 3,457 reference characters including SPACE.
TRAIN used 1,024 sequences / 117 other official signers; DEV is the frozen challenge-enriched
DAUN subset with TEST-phrase overlap exclusion. These results are FSboard sequence-level
held-out DEV metrics; not live-phone, end-to-end AppHear or population accuracy.

| Epoch-30 metric | Native view | Sparse phone sensitivity view |
|---|---:|---:|
| Character error rate (lower is better) | 60.83% | 94.68% |
| Exact decoded sequences | 0 / 256 | 0 / 256 |
| Substitutions | 366 | 63 |
| Deletions | 1,716 | 3,210 |
| Insertions | 21 | 0 |
| Predicted characters | 1,762 | 247 |
| Empty predictions | 8 | 106 |
| Eligible CTC-loss sequences | 256 | 254 |
| Infeasible views retained in greedy metrics | 0 | 2 |
| Eligible mean CTC loss | 26.054 | 75.024 |

CTC train loss at epoch 30: 25.887. Last five native DEV CERs:
65.37%, 61.96%, 62.40%, 63.44%, 60.83%. Improvement continues across this bounded run;
neither convergence nor the effect of additional epochs is established. CER is an edit-error
rate and must not be converted to `100%-CER` as a recognition-accuracy claim.

| Subgroup at selected checkpoint | Native | Phone sensitivity |
|---|---:|---:|
| J-containing sequence CER, 59 sequences | 57.60% | 95.73% |
| Aligned J recall, 62 occurrences | 58.06% | 3.23% |
| Z-containing sequence CER, 52 sequences | 63.03% | 94.07% |
| Aligned Z recall, 58 occurrences | 6.90% | 1.72% |
| Repeated-letter sequence CER, 109 sequences | 61.21% | 94.16% |

These are text edit-alignments, not video letter boundaries or direct trajectory assessments.
Subgroups overlap. Detailed per-signer results remain in the epoch report.

The sparse view keeps genuine observations according to the frozen approximately-6.23/s
minimum-gap policy, recomputes adapter motion features and does not interpolate. Frame
rounding makes it conservative; it does not reproduce actual Xiaomi jitter, camera domain,
resolution or full AppHear session handling. Native-only fitting and sparse-view evaluation
therefore show cadence sensitivity, not a completed installed-phone performance measurement.

## Execution results — VERIFIED

Epoch 1: 57.49 s; epoch 30: 47.09 s; median epoch: 47.28 s.
Sum of recorded epoch durations: 1,435.48 s, approximately 23.9 minutes; excludes preflight
and other startup time. Last-epoch fitting: 17.44 s; native DEV: 24.18 s; phone DEV: 5.31 s.
Evaluation is now the largest recorded component. Cache: 424,203,336 bytes / 1,280 files.

The optimized command executed complete epochs, graph-based updates, checkpoints and DEV
evaluation successfully. The original eager run was interrupted and is not a completed
paired quality experiment; this run cannot prove unchanged final CER relative to it. Saved
best-model restore inference and stop/resume equivalence were not re-exercised by this review.

## Interpretation and next boundary

The data-to-training pipeline is demonstrated and native decoding learns some information.
Deletion-heavy predictions, very low Z recall, zero exact strings and severe sparse-cadence
degradation make this checkpoint unsuitable for release or production ABC integration.
This does not reject FSboard/Candidate01 as a corpus/representation: the result is one small
native-cadence-trained baseline, not a controlled attribution experiment.

**Recommended next work:** one bounded failure-analysis phase using saved predictions and
existing governed features: characterize deletions/empty outputs by sequence length, CTC
headroom and hand missingness; inspect blank/output behavior on a small fixed TRAIN/DEV
diagnostic set; verify training-vs-held-out and temporal-rate behavior. Separate observation
loss, cadence mismatch and learning/decoder behavior before selecting one next experiment.
Do not assume more epochs, more data, another architecture or a language model will fix it.

No further training, architecture comparison, feature revision, phone integration or data
download is authorized/executed by this completion review. Keep this run, checkpoints,
config and frozen dataset unchanged as the reference. TEST remains sealed; reflection stays
an accepted research limitation, not a newly proven collection convention.

Evidence: `artifacts/fingerspelling_baseline_review_01/review.json` and the saved run reports.

FIRST_BASELINE_COMPLETE_NOT_DEPLOYMENT_READY
