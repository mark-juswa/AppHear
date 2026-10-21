# Temporal Information vs Generalization: What Limits WORD Now (2026-10-20)

Research only, on top of commits A–D. Your two later Text-to-ASL commits (`ad9e97dc`, `5833df1c`) touch no recognition file.

Nothing was trained, and nothing in Android, Arm A, confirm-boundary, Candidate01, the materializer or SentenceBuilder changed. WORD_BLEND_02 is unchanged (Keras `7448597f…`, TFLite `40533bc3…`). Protected TEST, E6 and Tier 3 were not opened.

Every comparison below uses the same source clips and only real Candidate01 observations: never interpolated or duplicated frames.

**Populations:**
- DEV: 816 clips, 5 signers, selection-exposed.
- Sem-Lex EVAL: 1,517 clips from 13 signers never trained on, covering both reviewed packages.

The clip is the unit of evidence.

## 1. Is temporal information a major limitation? Yes end-to-end, only moderately for WORD

### WORD alone

WORD_BLEND_02 on the runtime-bounded window, same clips, real observations (`temporal_class_analysis.py`):

| Interval | Window observations | DEV | Sem-Lex EVAL | Pooled |
|---|---:|---:|---:|---:|
| Every frame (~33 ms) | 39 | 60.1% | 49.8% | **53.4%** |
| 100 ms | 14 | 58.6% | 46.2% | 50.6% |
| 133 ms | 10 | 56.1% | 45.1% | 49.0% |
| **200 ms (live median)** | 8 | 52.7% | 41.3% | **45.3%** |
| Phone-like irregular (≈ 230 ms) | 6 | 49.5% | 39.3% | 42.9% |
| 266 ms | 6 | 50.1% | 37.1% | 41.6% |
| 400 ms | 4 | 40.5% | 29.7% | 33.5% |

- **Denser is always better.** Accuracy rises monotonically, with no training-distribution mismatch at higher density, so no WORD retraining is needed to benefit.
- **Irregular timing is not a separate problem.** It costs about what its mean interval predicts.
- **Most errors are not temporal.** Even with every frame, 47% of clips are wrong, while the same model fits 90% of its own TRAIN clips at full density.

### Complete pipeline

Unchanged S2-R3 Arm A e10 + CONFIRM_BOUNDARY_70 + materializer + WORD_BLEND_02, on the held-out stitched streams (`heldout_dev_e2e.py --interval-ms`; DEV signers; semi-synthetic joins; outputs `e2e_cadence_*ms.json`):

| Interval | NATURAL: detected / correct words / precision / extra events per min | CONTINUOUS: detected / correct words / precision |
|---|---|---|
| 266 ms | 63.8 / 34.9 / 47.7% / 2.09 | 49.0 / 22.2 / 44.3% |
| **200 ms (live)** | 75.4 / **44.3** / 53.6% / 1.66 | 53.2 / **26.4** / 49.1% |
| 133 ms | 84.6 / **51.1** / 57.2% / 1.02 | 56.3 / **30.3** / 53.1% |
| 100 ms | 90.1 / **55.5** / 58.7% / 0.96 | 59.5 / **34.6** / 57.3% |

More observations help S2 detection and WORD together, and they reduce extra events. The S2 detector, trained at phone cadence, shows no sign of mismatch up to 100 ms.

Going from the live ~5 to ~7.5 observations per second is worth **+6.8 points of correct words in natural signing and +3.9 in continuous signing**. That is about as much as every WORD change since the frozen recognizer. Continuous-signing merges (67–81 merged events) persist at every cadence; that is a lifecycle problem, not a temporal one.

**Correction to `WORD_PRIORITIES_2026-10-18.md` §2.** That report called most covered-but-hard classes "information-limited". It relied on TRAIN fit at 3.75 fps alone. With every real frame, most of them remain wrong on new signers although they fit in-sample (next section). The temporal share was overstated.

## 2. Which classes, and why (per class, live 200 ms vs every frame; WORD_BLEND_02)

Of the 55 classes with recall ≤ 0.30 at 200 ms:

| Cause | Classes | Evidence | Examples |
|---|---:|---|---|
| **Cross-signer generalization** | **26** | Wrong on new signers even with every frame (≤ 35%) while TRAIN fit at full density ≥ 0.8. Across the 37 classes with this pattern (all recall levels), mean recall is 28% on DEV and 13% on Sem-Lex EVAL | PLEASE, SORRY, SIT, DRIVE, SCHOOL, COOK, FAST, NIGHT1, OPEN, AGAIN, HEAR1, IN, WHY, MUCH, STAND2, WE, SELL, SISTER, TICKET |
| Temporal (recovered by denser real observations, ≥ +25 points) | 11 | The cue exists in the video and is lost at the phone rate | CHAIR, CAR, ALWAYS, MONTH, WHY, BAD, GET, TURN, WELCOME2, WHAT1, BECOME |
| Weak hand evidence (overlaps the above) | 10 | Accepted-hand fraction < 0.45 | PLEASE (0.36), SORRY (0.39) |
| Not separable even in-sample | 2 | BUT, WHO: TRAIN fit at full density < 0.6 | |
| Mixed / none dominant | 17 | — | |

Across all 236 classes, 42 classes gain ≥ 25 points from every frame and 30 drop more than 10 points. Most classes have 2–9 independent clips, so per-class moves are indicative only.

**Minimal pairs do not get better with more observations** (confusions within the pair, every frame vs 200 ms):

| Pair | Every frame | 200 ms | Reading |
|---|---:|---:|---|
| CHAIR/SIT | 42% | 44% | CHAIR itself improves (0.62 → 1.0), but SIT stays at 0.3 for every density: SIT is a generalization failure |
| NOW/TODAY | 36% | 32% | No density effect |
| HAPPY/PLEASE | 26% | 13% | Denser is not better; PLEASE is 0% at every density |
| MUCH/TOOMUCH | 29% | 29% | No density effect; TOOMUCH TRAIN fit only 0.69 |
| CAR/DRIVE | 19% | 16% | CAR improves (0.33 → 1.0); DRIVE does not (0.23–0.35) |

**What the model fails to capture.** For the generalization classes the information is in the representation: the model separates these classes on its training signers at full density. It does not transfer it to new signers. Two compounding factors (MEASURED associations, not yet causal):
- **Hand evidence:** accuracy halves when hands are rarely accepted.
- **Form variants:** accepted "compatible variant" Sem-Lex EVAL clips score 27.7% against 43.3% for exact forms.

The repetition-based minimal pairs are partly recovered by density (CHAIR, CAR) but their partners are not (SIT, DRIVE). The partner's failure is generalization.

**PLEASE and SORRY:**
- **PLEASE** is 0% on every held-out clip at every density. It fits 82% in-sample, its hand is rarely accepted (0.36), and it has only 11 TRAIN signers (all ASL Citizen). It needs signer diversity and hand evidence, not cadence.
- **SORRY** fits 99% in-sample, but 108 of its 122 TRAIN clips come from the long local captures. On 3 independent clips it scores 0–33% (too few clips to rank). It is #2 in review package 03.

## 3. Priority

1. **Perception throughput (observation rate): the largest measured end-to-end lever** (+6.8 / +3.9 points of correct words at 133 ms, and fewer extra events), with no retraining of S2 or WORD. It is outside WORD.
   - **Where the time goes on the device:** DWPose takes about 80 ms and each hand refiner about 51 ms, run serially, so 180–200 ms per frame. The default-off parallel-hands option did not raise WORD fps on the Xiaomi (4.64 → 4.36) because of CPU contention.
   - **Candidate approach:** pipeline DWPose of frame t+1 with the refiners of frame t, keeping every per-frame output bit-identical. This is HYPOTHESIS until measured.
   - **What it needs:** its own milestone with recorded-frame bitwise parity, device fps/latency/thermal measurement, and an S2/decoder check at the new cadence. The offline result above supports S2 compatibility.
2. **Verified signer diversity: the dominant WORD-side lever** (26 generalization-hard classes; package 02 gave +11 points on its classes). Review package 03 (30 classes, 63 rows, UNDECIDED) covers SORRY, SHOW, STAND2, SPECIAL1, FIND and BYE among the generalization classes, plus the temporal classes CAR, GET, STUDENT, WORLD, GIVE and FRIEND. It needs human sign-form verification, and nothing in it was used.
3. **Not justified now:**
   - WORD retraining for density: higher density already helps without it, and sparse-only training was negative.
   - Minimal-pair specialists: those pairs fail on generalization, not on information.
   - A larger WORD model: in-sample fit is already 90%.

## 4. What was implemented

Two analysis tools; no model, no app change:
- `docs/audit/probes/word_accuracy/temporal_class_analysis.py` (+ `.json`): per-class and per-pair WORD accuracy at seven real observation densities, with in-sample fit.
- The existing `heldout_dev_e2e.py`, run at four cadences (`e2e_cadence_{266,200,133,100}ms.json`).

**No new WORD candidate** was produced, so there is nothing new for Android. WORD_BLEND_02 remains the reference and the installed debug engine.

## 5. Next steps

1. A separate **perception-throughput investigation**: scheduling only, with Candidate01 outputs bit-identical, S2 and WORD unchanged, a device measurement and a cadence check of the lifecycle. If it reaches about 7.5 observations per second, the offline evidence predicts the largest single end-to-end gain so far.
2. **Human review of package 03**, then WORD_BLEND_03 under the same rule, compared against WORD_BLEND_02 on identical windows.
3. Keep the two separate. Cadence and data effects add up but must be measured one at a time.
