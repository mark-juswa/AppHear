# EXP-P3-001 — Recognition error analysis and end-to-end funnel

| Field | Value |
|---|---|
| **ID** | EXP-P3-001 |
| **Hypothesis** | Most wrong or missing words are NOT classifier errors: a large share is lost upstream (acquisition, event formation) and, within the classifier, errors concentrate in classes that are inseparable at phone cadence rather than in a few confusable pairs. (Falsifiable: if the oracle-window ceiling were close to the delivered words, upstream loss would be small.) |
| **Baseline** | Frozen Recognition-v2 `ordinary_v2_tcn_fp32.tflite` `1ccf0afa…`; segmenters S2-R2 (production) and Arm A e10 + confirm-boundary (experimental) |
| **Dataset / split** | Per-class: pooled INDEPENDENT clips = DEV (5 ASL Citizen val-split signers P5, P12, P21, P26, P39; selection-exposed for every model) + Sem-Lex EVAL-role signers (never trained on); 2,333 clips, 236 classes. Funnel: 406 held-out stitched streams, 812 signs, the 5 DEV signers |
| **Configuration** | `python -m eval.recognition_experiments.error_analysis` reading `docs/audit/probes/word_accuracy/difficult_words.json` and `docs/audit/probes/heldout_dev_e2e/{s2r2_base,armA_base}.json` |
| **Training** | none: analysis only |
| **Metrics** | clip-weighted accuracy, macro recall, per-class recall (runtime window at phone cadence, and dense), hard class = recall ≤ 0.30, diagnostic labels, estimated pair confusions = clips × (1 − recall) × dominant-partner share, funnel counts |
| **Model size / latency** | not applicable (no model change) |

## Results

### Data limits (NOT AVAILABLE in the repository)
Per-class **precision and F1**, a full **236×236 confusion matrix** and per-signer per-class results are not stored: the file keeps recall and only the dominant wrong prediction per class. They need the external artifact `word_vocabulary_eval_01` (`eval/runtime_diagnostics/word_vocabulary_report.py`). Event-level precision and the gate trade-off are in EXP-P3-002.

### Pooled independent population (REPRODUCED)
| Model | Clip-weighted accuracy | Macro recall | Median class recall | Hard classes (recall ≤ 0.30) | Zero-recall classes |
|---|---:|---:|---:|---:|---:|
| Frozen (production) | 29.8% | 40.6% | 36.3% | 98 | 3 |
| WORD_BLEND_01 | 38.1% | 47.1% | 46.2% | 78 | 4 |
| WORD_BLEND_02 | 41.6% | 48.0% | 44.0% | 64 | 3 |

The published hard-class counts 98 / 78 / 64 and the frozen label counts reproduce exactly. One published movement count differs by a single class: BLEND_01→BLEND_02 per-class movement is **57 up / 51 down / 128 within** under the stated rule ("more than 5 points"), versus the published 57 / 52 / 127. `SLEEP` changed by exactly −5.0 points (0.525 → 0.475, 40 clips); raw float arithmetic gives −0.05000000000000004 and tipped it into "down" in the original count. Immaterial; recorded for accuracy.

### Where words are lost: the end-to-end funnel (REPRODUCED)
Held-out stitched streams, 812 signs. "Oracle" = the same frozen recognizer on a perfectly bounded window.

| Segmenter / mode | Signs | S2 acquired | Own distinct event | Correct words | Oracle-correct | Lost upstream of classifier | Share of oracle words delivered |
|---|---:|---:|---:|---:|---:|---:|---:|
| S2-R2 NATURAL | 812 | 499 | 313 | 132 | 332 | 200 | 0.398 |
| S2-R2 CONTINUOUS | 812 | 600 | 256 | 78 | 296 | 218 | 0.264 |
| Arm A NATURAL | 812 | 664 | 515 | 236 | 332 | 96 | 0.711 |
| Arm A CONTINUOUS | 812 | 695 | 355 | 125 | 296 | 171 | 0.422 |

With production S2-R2 on natural streams only **132** of the **332** words the classifier *could* get right are delivered: **60 % of the recoverable correct words are lost before the classifier sees them**, and 480 of 812 signs (59 %) are wrong even with a perfect window. The system limit is therefore both ≈ 59 % classifier-limited and ≈ 25 % segmentation/decoder-limited (of all signs). Arm A + confirm-boundary delivers 236 of 332 (71 %) on natural streams but loses more in continuous signing (merged events 61 → 100).

### Signer-specific (REPRODUCED)
Correct-word rate, natural streams, production S2-R2 / Arm A: P12 5.9 % / 17.6 %, P21 15.8 % / 19.6 %, P26 13.4 % / 25.0 %, P39 22.1 % / 45.1 %, P5 17.9 % / 32.1 %. Runtime-window top-1 (frozen, REPO-REPORTED): P39 47.8 %, P26 42.4 %, P21 41.2 %, P12 25.4 %, P5 20.5 %; Sem-Lex EVAL signers 4.5 %–42.9 %. A ≥ 2× spread across signers is the norm, not the exception.

### The 20 weakest classes — frozen model (≥ 5 independent clips; COMPUTED from the tracked per-class file)
| # | Class | Clips/signers | Recall (phone cadence) | Recall (dense) | Hand frac. | Train fit | Train signers | Dominant wrong prediction (share of its errors) | Diagnostic labels |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | MONEY1 | 62/15 | 0.016 | 0.016 | 0.58 | 0.00 | 13 | BUY (0.15) | LOW_FIT |
| 2 | HEAR1 | 12/7 | 0.021 | 0.083 | 0.58 | 0.23 | 12 | BYE (0.30) | LOW_FIT |
| 3 | SOMETIMES | 8/6 | 0.031 | 0.000 | 0.68 | 0.46 | 12 | SHOW (0.13) | LOW_FIT |
| 4 | PLEASE | 7/7 | 0.036 | 0.143 | 0.37 | 0.64 | 11 | HAPPY (0.41) | WEAK_HANDS, PAIR, THIN_COVERAGE |
| 5 | NEW | 31/11 | 0.040 | 0.226 | 0.64 | 0.14 | 14 | EASY (0.14) | LOW_FIT |
| 6 | IN | 6/6 | 0.042 | 0.000 | 0.47 | 0.54 | 12 | NIGHT1 (0.13) | LOW_FIT |
| 7 | NICE | 40/12 | 0.044 | 0.050 | 0.59 | 0.20 | 15 | MOVIE1 (0.11) | LOW_FIT |
| 8 | CLEAN | 67/17 | 0.045 | 0.164 | 0.62 | 0.13 | 14 | MOVIE1 (0.11) | LOW_FIT |
| 9 | WHY | 9/7 | 0.056 | 0.000 | 0.43 | 0.25 | 12 | BECAUSE (0.24) | WEAK_HANDS, LOW_FIT |
| 10 | COOK | 30/13 | 0.067 | 0.200 | 0.62 | 0.31 | 11 | GOOD (0.20) | LOW_FIT, THIN_COVERAGE |
| 11 | MONTH | 11/9 | 0.068 | 0.182 | 0.67 | 0.29 | 13 | FROM (0.12) | LOW_FIT |
| 12 | SCHOOL | 54/14 | 0.074 | 0.167 | 0.61 | 0.40 | 15 | MOVIE1 (0.20) | LOW_FIT |
| 13 | HOSPITAL1 | 17/7 | 0.074 | 0.353 | 0.41 | 0.00 | 16 | US (0.14) | WEAK_HANDS, CADENCE, LOW_FIT |
| 14 | WALK2 | 17/9 | 0.088 | 0.118 | 0.66 | 0.61 | 12 | OFTEN (0.10) | UNEXPLAINED |
| 15 | CUT | 8/7 | 0.094 | 0.250 | 0.58 | 0.56 | 14 | US (0.10) | LOW_FIT |
| 16 | ENTER | 8/8 | 0.094 | 0.125 | 0.51 | 0.06 | 14 | ON (0.17) | LOW_FIT |
| 17 | BAD | 28/13 | 0.098 | 0.286 | 0.49 | 0.30 | 10 | HOT (0.10) | LOW_FIT, THIN_COVERAGE |
| 18 | SOME | 10/7 | 0.100 | 0.200 | 0.67 | 0.50 | 12 | GOOD (0.19) | LOW_FIT |
| 19 | MEAN2 | 5/5 | 0.100 | 0.200 | 0.68 | 0.40 | 15 | EACH (0.28) | LOW_FIT |
| 20 | WHAT1 | 5/5 | 0.100 | 0.200 | 0.73 | 0.33 | 13 | READ (0.22) | LOW_FIT |

Label counts among these 20: {'LOW_FIT': 18, 'WEAK_HANDS': 3, 'THIN_COVERAGE': 3, 'PAIR': 1, 'CADENCE': 1, 'UNEXPLAINED': 1}. **18 of 20 are LOW_FIT**: the model cannot fit them even on its own training clips at phone cadence (train fit < 0.6), so this is an information limit at 4–6 observations per sign, not under-training and not a threshold problem. Only 3 are WEAK_HANDS (perception), 3 THIN_COVERAGE (< 12 training signers), 1 a dominant PAIR.

The same ranking for WORD_BLEND_02 (candidate):

| # | Class | Clips | Recall | Dominant wrong prediction | Labels |
|---|---|---:|---:|---|---|
| 1 | IN | 6 | 0.000 | NIGHT1 | LOW_FIT |
| 2 | PLEASE | 7 | 0.036 | HAPPY | WEAK_HANDS, LOW_FIT, PAIR, THIN_COVERAGE |
| 3 | NICE | 40 | 0.050 | SCHOOL | LOW_FIT |
| 4 | SOMETIMES | 8 | 0.062 | SHOW | LOW_FIT |
| 5 | CUT | 8 | 0.094 | OR | CADENCE |
| 6 | CLEAN | 67 | 0.097 | COOK | LOW_FIT |
| 7 | SOME | 10 | 0.125 | GOOD | LOW_FIT |
| 8 | FEW | 8 | 0.125 | LIKE | UNEXPLAINED |
| 9 | MONEY1 | 62 | 0.133 | BUY | LOW_FIT |
| 10 | WHY | 9 | 0.139 | BECAUSE | WEAK_HANDS, LOW_FIT |
| 11 | AT | 5 | 0.150 | NIGHT1 | CADENCE |
| 12 | MEAN2 | 5 | 0.150 | EACH | LOW_FIT |
| 13 | RIGHT3 | 5 | 0.150 | TABLE | WEAK_HANDS |
| 14 | SPECIAL1 | 5 | 0.150 | FAMILY | UNEXPLAINED |
| 15 | ENTER | 8 | 0.156 | ON | LOW_FIT |
| 16 | HEAR1 | 12 | 0.167 | BYE | LOW_FIT |
| 17 | COOK | 30 | 0.175 | GOOD | LOW_FIT, THIN_COVERAGE |
| 18 | SCHOOL | 54 | 0.185 | MOVIE1 | UNEXPLAINED |
| 19 | NEW | 31 | 0.185 | EASY | CADENCE, LOW_FIT |
| 20 | LUNCH1 | 8 | 0.188 | HOT | LOW_FIT |

### Most frequently confused pairs — frozen (estimated; both directions summed)
| Pair | Estimated errors | A→B / B→A |
|---|---:|---|
| MOVIE1/SCHOOL | 10.0 | 0.0 / 10.0 |
| CHAIR/SIT | 9.95 | 0.74 / 9.21 |
| BUY/MONEY1 | 9.15 | 0.0 / 9.15 |
| THEN/TIME | 7.92 | 0.0 / 7.92 |
| HOT/PICK | 7.42 | 7.42 / 0.0 |
| CLEAN/MOVIE1 | 7.04 | 7.04 / 0.0 |
| PLAY/TODAY | 6.99 | 6.99 / 0.0 |
| COOK/GOOD | 5.6 | 5.6 / 0.0 |
| COLD/WITH | 5.54 | 2.82 / 2.72 |
| FIRST/WHERE | 4.64 | 0.0 / 4.64 |
| BECAUSE/KNOW | 4.57 | 0.0 / 4.57 |
| HELP/WATCH | 4.46 | 4.46 / 0.0 |
| NOW/TODAY | 4.25 | 4.25 / 0.0 |
| HURRY/READY | 4.24 | 0.0 / 4.24 |
| MOVIE1/NICE | 4.21 | 0.0 / 4.21 |

The repo's multi-phase count lists CHAIR↔SIT 25, HOT↔PICK 16, THEN↔TIME 14 (REPO-REPORTED); the ranking above is a different, smaller estimate from one dominant partner per class and is only indicative. Several are genuine near-minimal ASL pairs distinguished by repetition or a small movement.

### Training-data coverage vs recall (COMPUTED, frozen)
Training signers per class: min 8, median 13, max 18; 23 classes have fewer than 12. Spearman ρ(recall, training fit) = **0.529**, ρ(recall, training signers) = 0.237, ρ(recall, accepted-hand fraction) = 0.204. Evaluation support is thin: median 4 independent clips per class; only 82 classes have ≥ 8 clips from ≥ 5 signers.

## Root-cause classification (stages A–H)
| Stage | Evidence | Effect | Label |
|---|---|---|---|
| A Camera acquisition | synthetic dim light −8.9 points; processed cadence 4.6–7.7 fps on the phone; frozen top-1 on runtime windows 42.0 % at 266 ms vs 48.6 % at 133 ms (cadence curve) | cadence is a real lever (+4 to +7 points) | REPO-REPORTED |
| B–D Pose / hand region / landmark quality | accuracy by accepted-hand fraction: < 25 % → 17.6 %, 25–50 % → 22.6 %, 50–75 % → 30.4 %, ≥ 75 % → 36.7 % (frozen); TABLE has no accepted hand on the phone; the refiner rejects flat hands | perception floor for some classes; B, C and D cannot be separated with tracked data | COMPUTED / REPO-REPORTED |
| E Segmentation (S2) | funnel above: S2-R2 gives a sign its own event for 38.5 % of natural signs; Arm A 63.4 % | largest single upstream loss | REPRODUCED |
| F Event decoder | merged events; contaminated windows are correct 15.6 % (natural) / 32.2 % (continuous) vs 47.9 % / 43.0 % when clean | continuous signing | REPO-REPORTED |
| G Classifier | 78 % of runtime errors already occur on the dense, well-bounded view; 50.3 % dense DEV vs 86.9 % TRAIN; 18 of the 20 weakest classes are LOW_FIT | cross-signer discrimination, information-limited at phone cadence | REPO-REPORTED / COMPUTED |
| H Commit gate | removes ≈ 25 % of correct words on held-out signers at the STABLE floor in exchange for halving wrong commits (Phase 1); hard classes lose more (EXP-P3-002 G3) | a trade-off dial, not a cause of upstream error | COMPUTED |

## Conclusion
Supported: errors are mostly (a) classifier discrimination limited by signer diversity and cadence, and (b) a large segmentation/decoder loss that precedes the classifier. **Not supported:** that a bigger model or a different threshold would fix the weakest classes (they are not separable on training data at phone cadence). Not decidable here: per-class precision/F1 and the full confusion matrix.
