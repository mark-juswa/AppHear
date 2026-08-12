# E5-H Clean 7-Class Routed Simulation Result

**Last updated:** 2026-08-03

## Purpose
Record whether the E5-G clean 7-class landmark model can safely operate as a routed recognizer when no-sign windows and unsupported signs are present.

## Scope
Offline simulation only. No Android export, production recognizer replacement, feature-schema change, extraction change, or source dataset mutation was authorized.

## Verified Project References
- Runner: `pipeline/rgb/e5_h_clean_7_routed_sim.py`
- Full 7-sign run: `artifacts/recognition_upgrade/e5_batch_screening/e5_h_clean_7_routed_sim_01`
- Stable-3 diagnostic run: `artifacts/recognition_upgrade/e5_batch_screening/e5_h_clean_3_routed_sim_01`
- Source primary run: `artifacts/recognition_upgrade/e5_batch_screening/e5_g_clean_7_primary_01`
- Gate run: `artifacts/recognition_upgrade/e4_generalization/e4_ag_low_motion_gate_01`
- No-sign run: `artifacts/recognition_upgrade/e4_generalization/e4_ag_hello_like_nosign_expansion_01`

## Full 7-Sign Routed Result
Selected commit classes:
`WASH2`, `THINK`, `TAKE`, `MEET`, `GOOD`, `SELL`, `STAND2`

Dataset:
- rows: `1099`
- positives: `344`
- unsupported: `351`
- no-sign: `404`

Selected policy:
- primary confidence threshold: `0.995`

Test summary:
- mean/min accepted precision: `0.7571` / `0.7000`
- mean/min positive coverage: `0.1111` / `0.0833`
- max unsupported false commit rate: `0.0330`
- max no-sign false commit rate: `0.0000`
- min class recall: `0.0000`
- mean class recall: `0.1015`

Decision: **NO-GO**. The model became safe only by rejecting almost all true signs.

## Stable-3 Diagnostic Result
Commit classes:
`WASH2`, `THINK`, `TAKE`

Other E5-G classes were treated as unsupported pressure:
`MEET`, `GOOD`, `SELL`, `STAND2`

Dataset:
- rows: `1337`
- positives: `106`
- unsupported: `827`
- no-sign: `404`

Selected policy:
- primary confidence threshold: `0.995`

Test summary:
- mean/min accepted precision: `0.9333` / `0.8000`
- mean/min positive coverage: `0.1458` / `0.0938`
- max unsupported false commit rate: `0.0058`
- max no-sign false commit rate: `0.0000`
- min class recall: `0.0000`
- mean class recall: `0.1414`

Decision: **NO-GO**. Shrinking the commit vocabulary reduces false commits but still rejects too many true signs.

## Threshold Grid Finding
The validation grids show the core failure:
- Low thresholds preserve real-sign coverage but allow too many unsupported false commits.
- High thresholds suppress unsupported/no-sign commits but reject most true signs.

This is not just a vocabulary-size problem. It is an open-set rejection/calibration problem.

## Architecture Decisions
- Do not continue reducing vocabulary as the primary solution.
- Do not export E5-G or E5-H to Android.
- Do not rely on softmax confidence alone for silent translation safety.
- Proceed to an explicit reject/OOV experiment: train/evaluate a routed model or auxiliary head that learns `SUPPORTED_SIGN`, `UNSUPPORTED_SIGN`, and `NO_SIGN` evidence directly.

## Engineering Inference
E5-G proves the selected signs are learnable in closed-set classification. E5-H proves closed-set confidence does not transfer cleanly to open-set routed recognition. The next model needs explicit negative pressure during training or calibration, not only a post-hoc confidence threshold.

## Assumptions
- Silent translation requires low false commits more than high closed-set accuracy.
- Unsupported signs in E5-D are useful pressure rows but are not a complete real-world OOV set.

## Open Questions
- Should rejection be trained as a shared `OTHER/NO_SIGN` class, an auxiliary binary accept head, or a calibrated one-vs-rest bank?
- Can per-class thresholds help after explicit negative training, or are they insufficient alone?
- Which E5-G classes should remain candidates after open-set training?

## Risks
- Adding an `OTHER` class may overfit to the current unsupported set.
- A reject head may still reject low-motion true signs if no-sign data is not diverse enough.
- Validation counts are small, so thresholds must be selected cautiously.

## Next Required Action
Prepare E5-I as an explicit open-set/rejection experiment using:
- positives from E5-G selected classes;
- unsupported signs from E5-D and excluded E5-G rows;
- no-sign windows from E4-AG;
- metrics for accepted precision, positive coverage, unsupported false commits, no-sign false commits, and per-class recall.
