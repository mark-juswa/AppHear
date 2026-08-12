# E5-I Open-Set Reject Head Result

**Last updated:** 2026-08-03

## Purpose
Record the explicit open-set/rejection experiment created after E5-H showed that softmax confidence alone could not safely reject unsupported signs while preserving useful true-sign coverage.

## Scope
Offline experiment only. No Android export, production recognizer replacement, feature-schema change, extraction change, or source dataset mutation was authorized.

## Verified Project References
- Runner: `pipeline/rgb/e5_i_open_set_reject_head.py`
- Full 7-sign run: `artifacts/recognition_upgrade/e5_batch_screening/e5_i_open_set_reject_head_01`
- Stable-3 diagnostic run: `artifacts/recognition_upgrade/e5_batch_screening/e5_i_open_set_reject_head_3sign_01`
- Source primary data: `artifacts/recognition_upgrade/e5_batch_screening/e5_g_clean_7_primary_01`
- Unsupported pressure data: `artifacts/recognition_upgrade/e5_batch_screening/e5_d_reduced_primary_15sign_01`
- No-sign data: `artifacts/recognition_upgrade/e4_generalization/e4_ag_hello_like_nosign_expansion_01`

## Architecture Tested
E5-I trains a two-head Conv1D landmark model over schema v3.0 `[96,258]`:
- `sign` head: supported-class softmax;
- `accept` head: binary supported-vs-unsupported/no-sign probability.

At evaluation time, a commit requires both:
- `accept_probability >= accept_threshold`;
- `sign_confidence >= sign_threshold`.

Validation chooses thresholds; test reports accepted precision, positive coverage, unsupported false commits, no-sign false commits, and per-class recall.

## Full 7-Sign Result
Supported classes:
`WASH2`, `THINK`, `TAKE`, `MEET`, `GOOD`, `SELL`, `STAND2`

Dataset:
- rows: `1099`
- train/val/test: `718` / `127` / `254`
- positives: `344`
- unsupported: `351`
- no-sign: `404`

Selected policy:
- accept threshold: `0.95`
- sign threshold: `0.80`

Closed-set positive accuracy by seed:
- seed `101`: `0.7500`
- seed `202`: `0.7917`
- seed `303`: `0.8333`

Routed test summary:
- mean/min accepted precision: `0.8985` / `0.8333`
- mean/min positive coverage: `0.2778` / `0.2083`
- max unsupported false commit rate: `0.0220`
- max no-sign false commit rate: `0.0110`
- min class recall: `0.0000`
- mean class recall: `0.2567`

Decision: **NO-GO**. The reject head improves false-commit control but rejects too many true signs and still has zero-recall classes under the selected policy.

## Stable-3 Diagnostic Result
Supported classes:
`WASH2`, `THINK`, `TAKE`

Dataset:
- rows: `1337`
- train/val/test: `904` / `139` / `294`
- positives: `106`
- unsupported: `827`
- no-sign: `404`

Selected policy:
- accept threshold: `0.95`
- sign threshold: `0.80`

Closed-set positive accuracy by seed:
- seed `101`: `0.9375`
- seed `202`: `0.9375`
- seed `303`: `0.8750`

Routed test summary:
- mean/min accepted precision: `0.7129` / `0.5532`
- mean/min positive coverage: `0.5833` / `0.4375`
- max unsupported false commit rate: `0.1170`
- max no-sign false commit rate: `0.0220`
- min class recall: `0.0000`
- mean class recall: `0.5778`

Decision: **NO-GO**. The stable-3 sign classifier is strong in closed-set mode, but the shared accept head is seed-unstable and rejects or falsely accepts unevenly.

## Comparison to E5-H
E5-I is better than E5-H in the specific sense that it learns useful negative pressure:
- Full 7-sign E5-H mean coverage was `0.1111`; E5-I improved to `0.2778` while keeping unsupported false commits low.
- Stable-3 E5-H mean coverage was `0.1458`; E5-I improved to `0.5833`.

However, E5-I still fails the real app gate. The shared accept head is too blunt: it treats supportedness as one global decision and suppresses some valid classes.

## Architecture Decisions
- Do not export E5-I to Android.
- Do not return to confidence-only softmax rejection as the primary solution.
- Do not keep shrinking vocabulary as the main fix.
- The next experiment should test class-conditioned rejection: per-class accept thresholds, one-vs-rest supported heads, or a class-conditioned accept head.

## Engineering Inference
The problem is now more precise: the landmark classifier can recognize some supported signs, and negative training helps reject unsupported/no-sign rows, but a single global accept head is not expressive enough. Hard/easy signs need separate acceptance behavior.

## Assumptions
- The unsupported pressure rows are useful but not a complete real-world OOV set.
- Small validation counts can distort threshold choice, especially for per-class recall.
- Silent translation requires low false commits and cannot rely on user confirmation.

## Open Questions
- Would per-class accept thresholds recover `TAKE` without increasing unsupported false commits?
- Would a one-vs-rest bank perform better than a shared accept head?
- Should `GOOD`, `MEET`, `SELL`, and `STAND2` remain in the primary set or be deferred while stable core rejection is solved?
- Is additional no-sign/unsupported diversity needed before finalizing the reject model?

## Risks
- A class-conditioned reject system may overfit to current unsupported rows.
- Per-class thresholds may require more validation samples per class.
- Strong closed-set accuracy can still hide unsafe open-set behavior.

## Next Required Action
Prepare E5-J as a class-conditioned rejection experiment. Start with the stable-3 subset and compare:
1. shared accept head baseline from E5-I;
2. per-class threshold policy over E5-I outputs;
3. one-vs-rest accept heads if thresholding is insufficient.

No Android/export/production replacement is authorized before E5-J passes routed safety gates.
