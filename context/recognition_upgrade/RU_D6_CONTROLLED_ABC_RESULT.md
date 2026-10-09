# RU-D6 Controlled A/B/C Result

**Status:** COMPLETE — Candidate C wins validation, production promotion blocked  
**Date:** 2026-08-15

## Contract and integrity

All nine production-family TCN runs completed for A/B/C and seeds `101/202/303`. The shared
816-row validation tensor, vocabulary, warm start, preprocessing, augmentation, hyperparameters,
and checkpoint policy were held constant. Candidate C differs from B only by the 32 frozen
exact-target Sem-Lex TRAIN rows. Structural validation passed with no errors. The protected test
was not accessed.

## Aggregate result

| Branch | Top-1 | Top-5 | Macro-F1 | Worst-decile recall | Worst-decile F1 | ECE |
|---|---:|---:|---:|---:|---:|---:|
| A frozen baseline | 0.6712 | 0.9040 | 0.6482 | 0.0694 | 0.0865 | 0.2399 |
| B RU-D3 cleanup | 0.6650 | 0.8995 | 0.6427 | 0.0507 | 0.0616 | 0.2393 |
| C cleanup + Sem-Lex | **0.6793** | **0.9101** | **0.6606** | **0.0910** | **0.1106** | 0.2425 |

C versus B improves Top-1 by `+1.43 pp`, Top-5 by `+1.06 pp`, macro-F1 by `+1.78 pp`,
worst-decile recall by `+4.03 pp`, and worst-decile F1 by `+4.90 pp`. ECE worsens slightly by
`0.31 pp` and remains poor in absolute terms; RU-D6 does not authorize calibration/S7 changes.

C beats B Top-1 in seeds 101 and 202 but not 303. It beats B Top-5 in all three seeds. Thus the
gain is meaningful but not fully seed-stable.

## Target classes

| Gloss | Ensemble B -> C recall | C Top-5 | Interpretation |
|---|---:|---:|---|
| KNOW | 0.00 -> **0.25** | 0.75 | Promising ranking/generalization repair; nonzero recall in 2/3 seeds, still weak. |
| WHO | 0.00 -> **0.50** | 0.75 | Strongest target repair; improves all three seeds, but creates WHO attraction. |
| WE | 1.00 -> **1.00** | 1.00 | Recall preserved; ensemble F1 falls 0.667 -> 0.600 from one additional false attraction. |
| COME | 0.00 -> **0.00** | 1.00 | No measurable Top-1 repair; the sole validation row remains MORNING. |
| LEAVE | 0.00 -> **0.333** | 1.00 | Restores A-level recall in every seed; still weak but no longer cleanup-starved. |

The ensemble removes the B `KNOW -> HELLO` error. WE/COME produce no mutual validation
confusions. C predicts WHO for two correct WHO rows but also for one SISTER and one KEEP row.

## Unrelated-class regressions

Eleven classes meet the preregistered C-vs-B severe-regression rule, but validation support is only
3-5 rows per class. Six are losses of gains B had over A rather than new losses below A. Five are
also worse than A: ABOUT2, BAG2, IN, ROOM, and SISTER. SISTER is the clearest concern: recall
`0.667 -> 0.000`, worse in all three seeds, including one `SISTER -> WHO` ensemble error.

This prevents immediate promotion. It does not justify reverting to contaminated RU-D3 inputs:
Candidate C is the strongest clean foundation and remains the only branch that improves aggregate,
tail, and target metrics together.

## Verdict and next gate

Keep Candidate C as the preferred repaired research foundation. Do not deploy, recalibrate S7, add
data, or retrain again yet. The next bounded gate is a fresh-phone RU-D diagnostic comparison using
the withheld phone signer and exact captured `[96,258]` windows. Compare the best overall
validation checkpoints (B seed 303 control, C seed 202 candidate) on the same attempts, with actual
and oracle spans. Focus on KNOW, WHO, WE, COME, LEAVE, healthy controls, and WHO/WE false-attraction
evidence. Capture once and replay both models; do not change production behavior during capture.

Stop Candidate C promotion if it fails to improve target ranks/commits over B, harms healthy
controls, or introduces target-class false commitments. COME should be marked externally
data-limited for this Sem-Lex route if it remains unrepaired; no further Sem-Lex cycle is allowed.
