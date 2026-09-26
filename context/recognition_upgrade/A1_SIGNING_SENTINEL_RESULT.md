# A1 Small Signing Sentinel Result

**Date:** 2026-08-16  
**Decision:** `KEEP A1 AS V2 FOUNDATION`  
**Deployment:** not authorized  
**A2:** not implemented

## Evidence boundary

The order-balanced sentinel captured 24 visually reviewed, natural, single-sign attempts from one
signer on the same Xiaomi phone: two Baseline and two A1 attempts each for `GOOD`, `WE`, `NOW`,
`KNOW`, `HAVE`, and `HELLO`. Every attempt begins and ends at rest, matches the queued sign and
variant, has a complete RU-D1 bundle, and has a manually selected visible sign span independent of
S5. This is a bounded non-regression sentinel, not an accuracy or cross-signer claim.

All 24 exact reconstructed window hashes matched Android and all 24 S7 policy replays matched the
recorded Android outcome. X86 TFLite argmax matched Android in only 14/24 attempts (maximum posterior
delta `0.1797`), consistent with the known quantized cross-runtime limitation. Consequently, this
decision uses recorded on-phone ranks and commits; oracle-span classifier counterfactuals are not
trusted for attempts with argmax mismatch.

## Aggregate comparison

| Signed metric | Baseline | A1 | Interpretation |
| --- | ---: | ---: | --- |
| Mean required-hand coverage | 57.1% | 57.9% | Essentially unchanged |
| Mean two-hand coverage | 20.6% | 20.0% | Essentially unchanged |
| Pose coverage | 100% | 100% | No signed pose-loss regression |
| S5 onset attempts | 11/12 | 11/12 | No aggregate onset regression |
| Target Top-1 | 4/12 | 5/12 | Slightly better |
| Target Top-5 | 10/12 | 9/12 | One-attempt decrease |
| Correct commits | 2/12 | 5/12 | Better in this sentinel |
| Wrong commits | 5/12 | 4/12 | No false-commit increase |
| No commit | 5/12 | 3/12 | Fewer missed outputs |

Signed hand coverage stayed flat even though Stage 1 proved a 33.5% higher fresh-hand rate and a
34.5% lower p95 hand gap. Independent clocks therefore improve temporal sampling/freshness, but do
not increase the fraction of visible sign frames where MediaPipe successfully returns the required
hands. The remaining continuity problem is detector/occlusion loss, not scheduler starvation alone.

## Per-sign outcome

| Sign | Baseline commits | A1 commits | Reading |
| --- | --- | --- | --- |
| GOOD | none / none | GOOD / GOOD | Two-hand contact sentinel improved; A1 hand/two-hand coverage also slightly higher |
| HAVE | none / none | HAVE / HAVE | Healthy two-hand control improved |
| HELLO | HELLO / HELLO | none / HELLO | One A1 attempt missed S5 onset; isolated regression to retain as a follow-up sentinel |
| KNOW | HELLO / HELLO | HELLO / HELLO | Existing S5/S6 limitation unchanged; A1 does not solve it |
| NOW | none / HAVE | none / none | A1 removed one wrong commit but did not produce a correct commit |
| WE | SORRY / SORRY | COME / COME | Still wrong; confusion changed, underlying recognition problem remains |

`HELLO` is the only clear per-sign regression signal: A1 missed one onset where both Baseline
attempts committed correctly. It is one non-identical natural attempt, while aggregate onset count
was unchanged and A1 materially improved `GOOD` and `HAVE`; there is no narrow scheduling defect
identified that would justify `MODIFY ONCE`. This caveat must remain in any later broader evaluation.

## Decision

A1 satisfies its frozen final criteria:

- Stage 1 materially improved fresh-hand delivery and tail continuity;
- synchronizer yield remained `99.8%`, pose age stayed below the frozen ceiling, and runtime was
  stable;
- signed pose, hand, two-hand, and S5-onset aggregates did not materially regress;
- correct commits increased and wrong commits did not increase in the bounded sentinel.

Therefore keep the default-off independent-clock path as the experimental v2 perception
foundation. This is not permission to replace the production Baseline. It also is not evidence that
A1 solves perception continuity: contact/occlusion and detector dropout remain directly visible,
and `KNOW`, `NOW`, and `WE` remain unresolved. A2 may be considered as the next separately approved
hypothesis, but no A2 implementation occurred here.

Machine-readable summary:
`artifacts/recognition_upgrade/a1_independent_clock/signing_sentinel_01/a1_signing_sentinel_summary.json`.
