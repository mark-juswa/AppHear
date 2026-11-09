# Phase 3 — Recognition Accuracy Investigation

Date: 2026-11-09 · Branch `jepjep-claude` (working tree; **nothing committed or pushed**)
Experiment records: [`docs/recognition_experiments/`](recognition_experiments/README.md) · Result files: `docs/recognition_experiments/results/`

**Bottom line.** No candidate was trained or promoted, and no production model, vocabulary, threshold or camera/analyzer behaviour was changed. The evidence does not justify changing the production recognizer *now*; it does identify where accuracy is actually lost, rules out several tempting changes, and defines the experiments that would justify a change. One small hardening was made to the Phase 1 gate (§F.4).

## Evidence labels
| Label | Meaning |
|---|---|
| **REPRODUCED** | published by the repo's audits; recomputed here from tracked files |
| **COMPUTED** | new analysis here from tracked files (scripts + JSON in this repo) |
| **REPO-REPORTED** | published by the repo; needs external artifacts or a device; not reproduced |
| **MEASURED-EMU** | measured here on an arm64 emulator: contracts and relative cost only, never phone speed |
| **NOT AVAILABLE** | the data is not in this repository |

---

## A. Executive summary

### Current baseline
Production = **STABLE**: S2-R2 segmenter + frozen Recognition-v2 (`ordinary_v2_tcn_fp32.tflite`, 814,068 B, 236 classes) + Phase 1 gate (floor 0.55). Experimental = Arm A e10 + confirm-boundary + the same classifier (floor 0.75). Debug candidates (never in release): WORD v2, WORD_BLEND_01, WORD_BLEND_02 (3.23 MB each).

| Measure (independent held-out population) | Value | Label |
|---|---:|---|
| Classifier on realistic windows, DEV runtime windows, top-1 | 41.5 % | REPO-REPORTED |
| Pooled independent clips (DEV + 13 untouched Sem-Lex signers), frozen | **29.8 %** accuracy, 40.6 % macro recall, 98 of 236 classes with recall ≤ 0.30 | REPRODUCED |
| End to end, natural held-out streams, production S2-R2 | **16.3 %** of signs become the correct word (oracle ceiling with the same classifier: 40.9 %) | REPRODUCED |
| Same, Arm A + confirm-boundary | 29.1 % | REPRODUCED |
| Event-level gate on held-out signers (STABLE) | precision 0.36 → 0.50, retention of correct words 100 % → 75 % | REPRODUCED (Phase 1) |
| Live phone | no field-grade measurement exists; ≈ 5–8 fps delivered, below the 15 fps floor | REPO-REPORTED |

### Main accuracy problems
1. **Upstream loss is as large as classifier loss.** With production S2-R2, only 132 of the 332 words the classifier could get right on perfect windows are delivered: **60 % of recoverable correct words are lost before the classifier** (segmentation/event formation); a further 59 % of signs are wrong even with a perfect window.
2. **The weakest classes are information-limited, not data- or threshold-limited.** 18 of the 20 weakest classes cannot be fit even on their own training clips at phone cadence.
3. **Cross-signer variance is large** (≈ 2× across signers) and the confidence the model reports is **not calibrated** (ECE 0.15–0.27).
4. **Cadence matters directly:** frozen top-1 on runtime windows is 42.0 % at 266 ms spacing vs 48.6 % at 133 ms (REPO-REPORTED). The phone delivers ≈ 215 ms.

### Most important discoveries
- Documents I had not read in earlier phases (`docs/audit/WORD_*`, `docs/recognition-v3-*`) already contain a thorough attribution study and a pre-registered candidate (WORD_BLEND). I verified them rather than redoing them: the hard-class counts (98/78/64), label counts and the end-to-end funnel **reproduce exactly**; one published movement count differs by a single float-boundary class (§B).
- **WORD_BLEND_02 is the strongest evidence-backed accuracy candidate** (pooled independent accuracy 29.8 % → 41.6 %; hard classes 98 → 64) but lacks every prerequisite for promotion (§F).
- **Neither class-specific thresholds, per-signer thresholds nor a temporal-consistency rule is supported** by the available data (§E).
- The shipped floors are well placed: validation Youden J is slightly higher at 0.55/0.75 than at the ledger's own optimum (§E.G7).
- The phone evidence may not be signer-disjoint from training (§C).

---

## B. Recognition error analysis

Full tables: [EXP-P3-001](recognition_experiments/EXP-P3-001_error_analysis_and_funnel.md) (per-class evidence file for all 236 classes × 3 models, funnel from 406 held-out streams).

### Evidence that exists, and what it cannot support (NOT AVAILABLE)
Per-class **recall**, dominant wrong prediction and diagnostic labels exist for all 236 classes. **Per-class precision, per-class F1, the full 236×236 confusion matrix and per-signer-per-class results are not stored** in the repo (only the dominant wrong prediction per class). I therefore did **not** fabricate them. They require the external artifact `word_vocabulary_eval_01` (`eval/runtime_diagnostics/word_vocabulary_report.py`). What I provide instead: per-class recall; estimated dominant-pair confusions; event-level precision/retention/F1 and the false-positive / false-rejection trade-off (EXP-P3-002).

### Overall (REPRODUCED)
| Model | Clip-weighted accuracy | Macro recall | Hard classes | Zero-recall classes |
|---|---:|---:|---:|---:|
| Frozen | 29.8 % | 40.6 % | 98 | 3 |
| WORD_BLEND_01 | 38.1 % | 47.1 % | 78 | 4 |
| WORD_BLEND_02 | 41.6 % | 48.0 % | 64 | 3 |

Population: 2,333 independent clips, 236 classes. DEV (5 signers) is selection-exposed to every model equally; the 13 Sem-Lex EVAL signers were never trained on. Median independent support is 4 clips per class, so individual per-class numbers are indicative; only 82 classes have ≥ 8 clips from ≥ 5 signers.

### Where errors originate — the funnel (REPRODUCED), stages E–G separated
| | Signs | S2 acquired | Own distinct event | Correct words | Oracle (perfect window) |
|---|---:|---:|---:|---:|---:|
| S2-R2 (production), natural | 812 | 499 | 313 | 132 | 332 |
| S2-R2, continuous | 812 | 600 | 256 | 78 | 296 |
| Arm A + CB, natural | 812 | 664 | 515 | 236 | 332 |
| Arm A + CB, continuous | 812 | 695 | 355 | 125 | 296 |

**Recognition coverage** (signs that get their own event): 38.5 % production vs 63.4 % Arm A (natural). An upstream miss is not a classifier error and is reported as such.

### Root-cause classification A–H
| Stage | Finding | Label |
|---|---|---|
| A Camera acquisition | cadence is a real lever: frozen top-1 42.0 % (266 ms) → 48.6 % (133 ms); synthetic dim light −8.9 points | REPO-REPORTED |
| B–D Pose / hand region / landmarks | accuracy by accepted-hand fraction 17.6 % (< 25 %) → 36.7 % (≥ 75 %); TABLE has no accepted hand on the phone; refiner rejects flat hands. B, C, D cannot be separated with tracked data | COMPUTED |
| E Segmentation | S2-R2 acquires a sign's own event for 38.5 %; Arm A 63.4 %. Largest single upstream loss | REPRODUCED |
| F Event decoder | merged events (continuous 61 → 100 with Arm A); contaminated windows correct 15.6 % / 32.2 % vs 47.9 % / 43.0 % clean | REPO-REPORTED |
| G Classifier | 78 % of runtime errors exist on the dense, clean view (50.3 % DEV vs 86.9 % TRAIN); 60 % of errors keep the correct word in the top-5 | REPO-REPORTED |
| H Commit gate | removes ≈ 25 % of correct words to halve wrong commits; hard classes lose more | COMPUTED |

### Top 20 weakest classes (frozen; ≥ 5 independent clips; COMPUTED)
Failure pattern of the whole list: **18 / 20 LOW_FIT**, 3 WEAK_HANDS, 3 THIN_COVERAGE, 1 PAIR, 1 CADENCE, 1 UNEXPLAINED (a class may carry several labels).

| # | Class | Clips | Recall | Dominant wrong prediction | Labels |
|---|---|---:|---:|---|---|
| 1 | MONEY1 | 62 | 0.016 | BUY | LOW_FIT |
| 2 | HEAR1 | 12 | 0.021 | BYE | LOW_FIT |
| 3 | SOMETIMES | 8 | 0.031 | SHOW | LOW_FIT |
| 4 | PLEASE | 7 | 0.036 | HAPPY | WEAK_HANDS, PAIR, THIN_COVERAGE |
| 5 | NEW | 31 | 0.040 | EASY | LOW_FIT |
| 6 | IN | 6 | 0.042 | NIGHT1 | LOW_FIT |
| 7 | NICE | 40 | 0.044 | MOVIE1 | LOW_FIT |
| 8 | CLEAN | 67 | 0.045 | MOVIE1 | LOW_FIT |
| 9 | WHY | 9 | 0.056 | BECAUSE | WEAK_HANDS, LOW_FIT |
| 10 | COOK | 30 | 0.067 | GOOD | LOW_FIT, THIN_COVERAGE |
| 11 | MONTH | 11 | 0.068 | FROM | LOW_FIT |
| 12 | SCHOOL | 54 | 0.074 | MOVIE1 | LOW_FIT |
| 13 | HOSPITAL1 | 17 | 0.074 | US | WEAK_HANDS, CADENCE, LOW_FIT |
| 14 | WALK2 | 17 | 0.088 | OFTEN | UNEXPLAINED |
| 15 | CUT | 8 | 0.094 | US | LOW_FIT |
| 16 | ENTER | 8 | 0.094 | ON | LOW_FIT |
| 17 | BAD | 28 | 0.098 | HOT | LOW_FIT, THIN_COVERAGE |
| 18 | SOME | 10 | 0.100 | GOOD | LOW_FIT |
| 19 | MEAN2 | 5 | 0.100 | EACH | LOW_FIT |
| 20 | WHAT1 | 5 | 0.100 | READ | LOW_FIT |

Reading: these classes are mostly distinguished by repetition count, a small movement or handshape detail that 4–6 observations per sign cannot resolve; several collapse onto a single partner (MONEY1→BUY, CLEAN/SCHOOL/NICE→MOVIE1, COOK/SOME→GOOD). Most-confused pairs (estimated): MOVIE1/SCHOOL, CHAIR/SIT, BUY/MONEY1, THEN/TIME, HOT/PICK, CLEAN/MOVIE1, PLAY/TODAY, COOK/GOOD (the repo's multi-phase count adds CHAIR↔SIT 25, HOT↔PICK 16). The same table for WORD_BLEND_02 is in EXP-P3-001; the candidate improves 134 classes and worsens 20 by more than 5 points versus frozen (largest drops: MOUTH −25 pts, TODAY −19, TOOMUCH −19, CITY2 −17, each on 3–9 clips).

### Signer-specific performance (REPRODUCED)
Correct-word rate, natural streams, S2-R2 / Arm A: P12 5.9 / 17.6 %, P21 15.8 / 19.6 %, P26 13.4 / 25.0 %, P39 22.1 / 45.1 %, P5 17.9 / 32.1 %. Classifier top-1 on runtime windows: P39 47.8 %, P26 42.4 %, P21 41.2 %, P12 25.4 %, P5 20.5 %; Sem-Lex EVAL signers 4.5–42.9 %.

### False positives and false rejections
Event level, held-out signers, STABLE (Phase 1 reproduction): ungated precision 0.358; gated 0.498; false-rejection 25 %. By class group (EXP-P3-002 G3): at the shipped floor, valid words of hard classes are kept 66.7 % of the time vs 80.0 % for other classes (STABLE) and 46.5 % vs 67.1 % (EXPERIMENTAL): the gate costs hard classes more recall. Non-sign false-positive rates on real phone video: **NOT AVAILABLE** (Phase 1.1 protocol exists; no data).

---

## C. Dataset audit
Details: [EXP-P3-005](recognition_experiments/EXP-P3-005_signer_separation_and_dataset_audit.md).

- **Composition (REPO-REPORTED):** recognizer TRAIN 3,926 clips, 40 signers (35 ASL Citizen, 4 LOCAL, 1 APPHEAR), 8–20 clips per class except GOOD/HAVE/HELLO/KNOW/SORRY (120–190). DEV 816 clips / 5 signers; Sem-Lex EVAL 777 clips / 13 signers / 63 classes; phone 29 signs / 1 developer / 3 classes.
- **Signer separation (COMPUTED, tested):** ASL Citizen split 35 train / 6 val / 11 test signers, pairwise disjoint; the five DEV signers are val signers; gate calibration (P5/P12/P21) and validation (P26/P39) signers are disjoint.
- **Governance (read from the training script):** `protected_test_access` must be false; a balanced sampler is forbidden (it was measured harmful); checkpoints are selected on DEV `val_loss`, so **DEV is selection-exposed for every recognizer**.
- **Train/serve consistency:** JVM and device parity tests for the Recognition-v2 feature builder and recognizer pass (§G).
- **Concerns:** (1) the phone evidence may include a TRAIN signer (`APPHEAR_CAPTURE`, 297 clips) and its words (HELLO 190 clips) are the best-trained classes → optimistic and not independent; (2) class imbalance exists but explains ≤ 1.3–1.8 points; (3) median 13 training signers per class, 23 classes < 12; (4) median 4 independent evaluation clips per class.
- **Not auditable here (NOT AVAILABLE):** duplicate clips, incorrect annotations and label noise (raw data is external); differences between training and inference features beyond the parity tests.

---

## D. Model investigation
- **Existing limits:** classifier discrimination across signers (78 % of runtime errors present on the clean dense view); temporal resolution (cadence curve); perception evidence for some classes; no per-frame stream (one decision per event).
- **Feature representation:** the recognizer input is `[96, 350]` landmark features with a mask; accuracy rises with accepted-hand fraction (17.6 % → 36.7 %) and with observation count (cadence curve), i.e. the representation is limited by *what perception supplies at phone cadence*, not by input dimensionality. The repo's tests of larger capacity, neighbour context (WORD v3), contrastive invariance and sparse-only training were negative or neutral (REPO-REPORTED), and dense TRAIN fit is already 87–91 %: **no evidence of a capacity limit**.
- **Feature normalization / augmentation / balancing / architecture:** augmentation (WORD v2) +3.0 points DEV; hierarchical sampling harmful; exposure-controlled enrichment ≈ no gain; naive Sem-Lex enrichment helps but shifts the class prior; the blend (0.5 × frozen + 0.5 × mean of three enrichment runs) gives the best measured result.
- **Proposed improvements, in order of evidence:** (1) more independent signers per class via reviewed Sem-Lex packages (the only lever with a measured effect); (2) more observations per sign (perception throughput: Phase 2's thread-budget experiment); (3) a better segmenter (Arm A); (4) nothing on the classifier architecture.

---

## E. Experiment results
All Phase 3 experiments are analyses on tracked evidence (no training; no held-out data used to train or tune anything). Registry: [REGISTRY.md](recognition_experiments/REGISTRY.md).

| ID | Result |
|---|---|
| **EXP-P3-001** error analysis | §B |
| **EXP-P3-002** gate study | below |
| **EXP-P3-003** contract and doc drift | 42 / 42 checks pass; one stale doc sentence (blend "not wired" — it is) |
| **EXP-P3-004** candidate parity and cost | blend parity 2.4e-7 / 4.2e-7 vs Keras; ≈ 4.1× / 4.2× invocation cost on an emulator |
| **EXP-P3-005** signer separation | disjoint; phone set caveat |

### Gate study (EXP-P3-002; DEV-exposed, 5 signers, calibration P5/P12/P21, validation P26/P39)
- **G1 Calibration:** ECE 0.15–0.27 → top-1 probability is a ranking score, not a probability. Floors stay empirical.
- **G2 Global threshold:** per-signer optima span ≈ 0.57–0.80 (n ≤ 356 per signer). A single floor is a compromise; per-signer floors are not implementable (no signer identity) and not estimable.
- **G3** hard classes lose more recall under any global floor (§B).
- **G4 Class-specific thresholds:** no class has ≥ 30 events and ≤ 1 has ≥ 10 on the calibration signers → **no independent data; not built.**
- **G5 Frozen vs WORD v2 (identical events, each calibrated on calibration signers only):**

| Ledger / model | Committed correct | Committed wrong | Precision | Retention (recall) | False-rejection | Coverage | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| STABLE frozen, ungated | 135 | 242 | 0.358 | 1.000 | 0.000 | 1.000 | 0.527 |
| STABLE frozen, gated @ 0.575 | 98 | 98 | 0.500 | 0.726 | 0.274 | 0.520 | 0.592 |
| STABLE v2, gated @ 0.653 | 86 | 79 | 0.521 | 0.623 | 0.377 | 0.438 | 0.568 |
| EXPERIMENTAL frozen, ungated | 265 | 370 | 0.417 | 1.000 | 0.000 | 1.000 | 0.589 |
| EXPERIMENTAL frozen, gated @ 0.669 | 186 | 123 | 0.602 | 0.702 | 0.298 | 0.487 | 0.648 |
| EXPERIMENTAL v2, gated @ 0.663 | 199 | 109 | 0.646 | 0.696 | 0.304 | 0.485 | 0.670 |

  Paired: on the production segmenter v2 vs frozen is not distinguishable (22 vs 19 discordant, McNemar p = 0.76) and its F1 is lower; with Arm A it is better (46 vs 25, p = 0.017). WORD v2 is superseded by the blends, for which no event-level data exists in the repo.
- **G6 Temporal rule:** trimming-stability AUC 0.65–0.66 vs top-1 probability 0.76–0.77, and it would triple recognizer calls → **not supported, not implemented.**
- **G7 Shipped floors:** the ledger's own calibration optimum is 0.575 (STABLE; shipped 0.55) and 0.669 (EXPERIMENTAL; shipped 0.75). Validation Youden J is slightly higher at the shipped values (0.327 vs 0.321; 0.388 vs 0.370) and calibration differences (≤ 0.02) are within sampling noise: the curve is flat there. **No floor change is justified.** (I could not reproduce 0.75 as a ledger Youden optimum; it was chosen by the repo's own pooling.)

### Candidate recognizers (no new training; REPRODUCED / REPO-REPORTED)
| | Frozen | WORD_BLEND_01 | WORD_BLEND_02 |
|---|---:|---:|---:|
| Pooled independent clip accuracy (REPRODUCED) | 29.8 % | 38.1 % | 41.6 % |
| Hard classes (REPRODUCED) | 98 | 78 | 64 |
| DEV runtime windows, top-1 (REPO-REPORTED) | 41.5 % | 48.6 % | — |
| 13 untouched Sem-Lex signers (REPO-REPORTED) | 29.4 % | 45.8 % | — |
| End-to-end natural correct words, Arm A (REPO-REPORTED) | 29.3 % | 33.5 % | — |
| Model size (MEASURED, file) | 814,068 B | 3,232,620 B | 3,232,620 B |
| Invocation median, emulator (MEASURED-EMU) | 0.75 ms | 3.05 ms | 3.19 ms |
| Invocation on the target phone | ≈ 2.7 ms (REPO-REPORTED, measured) | ≈ 12 ms (ESTIMATE by the repo) | not measured |

---

## F. Production recommendation

### F.1 Recommendation
**Keep the current production configuration unchanged** (S2-R2 + frozen Recognition-v2 + Phase 1 gate, floors 0.55 / 0.75). Do **not** replace Recognition-v2, change the vocabulary, change thresholds, add class-specific or temporal rules, or retrain. No candidate has the evidence a promotion requires.

### F.2 Why WORD_BLEND_02 is not promoted yet
It is the best candidate, but: (1) **no phone validation** (the 12-sign A/B protocol was never run; phone evidence is also not independent, §C); (2) **no calibrated confidence floor** (the engines run with the structural rule only; no event-level blend data exists in the repo); (3) **device latency unmeasured** (≈ 12 ms is an estimate); (4) **per-class regressions** (MOUTH, TODAY, TOOMUCH, CITY2) on 3–9 clips each that cannot be judged; (5) the DEV half of its evidence is selection-exposed. Everything it needs is listed in [PLANNED.md](recognition_experiments/PLANNED.md) (EXP-P3-101/102).

### F.3 Is more data required? **Yes.** In priority: (a) more independent signers per class (median 13 training signers; Sem-Lex review package 03 is prepared and needs human review); (b) phone-domain data from several signers in the same capture conditions; (c) non-sign / hard-negative events from several people (≥ 30 events from ≥ 3 independent people, the repo's own bar) for gate calibration.

### F.4 Change made in this phase (the only production-code change)
`PhoneEventCommitter.decide` now also checks that the reported top-1 is an argmax of the **full** output vector when the gate is enabled; if not it returns REJECT / `INVALID_RECOGNIZER_OUTPUT`. The Phase 1 policy test (`p2 > p1`) cannot see a mis-ordered `top5` whose entries tie. In valid use (top-5 built best-first, as `RecognitionV2LiveRecognizer` does) behaviour is identical; the disabled (pre-gate) policy is untouched; cost is 236 comparisons per event. Found by the new "output interpretation" regression test; mutation-checked.

### F.5 Risks and rollback
Candidate model files exist **only** in the debug source set (a release build cannot load them, asserted by a test), are selectable only in debug Settings, and fall back to STABLE on any failure (`resolve` / `load` fallback, tested). Rollback of any future promotion: re-select STABLE (one setting), or remove the candidate asset directory and the engine entry; production assets were never overwritten. The Phase 2 analyzer recovery and Phase 1/1.1 behaviour are unchanged and still pass their tests.

---

## G. Testing and verification

| Run | Result |
|---|---|
| Full JVM suite (scratch copy of `android/`; Gradle 8.14.3) | **415 tests, 0 failures** (404 before this phase + 11 new) |
| New `RecognitionAccuracyRegressionTest` (11) | all 236 class mappings identical across 4 packages and legacy `vocab.json`; difficult/partner classes are real vocabulary classes; model files match manifests, shapes, schema and pins; candidates debug-only; STABLE fallback; floors equal the calibration evidence and BLEND has none; the gate treats **every one of the 236 classes** identically (confident → commit exactly that gloss; low confidence → withheld); the 98 hard classes get no special rule; mis-ordered output rejected; top-5 interpretation; recognition and sentence survive an analyzer recovery |
| Mutation check | removing the new argmax guard makes the output-interpretation test fail |
| `:app:compileReleaseKotlin`, `:app:compileDebugAndroidTestKotlin` | success |
| New Python tests (`tests/test_recognition_experiments.py`, 25) + Phase 1.1 (`tests/test_shadow_report.py`, 29) | **54 / 54 pass** (stdlib only); includes reproduction tests of published numbers, signer-separation test and the model-contract run |
| Instrumented, emulator, package `perceptionvnext` | **25 run, 22 pass**; 3 environment failures (two need `v3/manifest.json` fixtures from a Gradle property; one needs a launch extra), none touches this phase's code |
| Existing Python research suite | **not runnable here**: 186 tests discovered, 147 error at import (`numpy`, `pytest`, `cv2`, `yaml`, `PIL` absent); no TensorFlow either, so no model can be trained or Keras-evaluated in this environment |
| Model contract validation | 42 / 42 checks pass (EXP-P3-003) |
| Offline evaluation suites | the repo's heavy suites (`word_vocabulary_eval/report`, `heldout_dev_e2e`, `event_reliability`) need external artifacts and TensorFlow; their **stored outputs** were analysed instead |

**Regression findings:** none caused by this phase. Outstanding: the three environment-dependent instrumented tests; stale sentence in `WORD_ACCURACY_236 §5`.

---

## H. Remaining limitations (all need physical-device or external-data validation)
1. **No physical-device measurement.** Blend latency on the phone, any accuracy on the phone, and the effect of the Phase 2 diagnostics on a phone are unmeasured. The emulator numbers are relative only.
2. **No new model was trained**; training data and TensorFlow are unavailable here. No accuracy improvement is claimed.
3. **Per-class precision / F1 and the full confusion matrix** need the external evaluation artifact.
4. **Blend gate floors** need event-level blend data (external artifacts or a Phase 1.1 shadow study).
5. **DEV signers are selection-exposed**; phone sessions are development-exposed and may overlap a training signer.
6. Gate-study statistics use 5 signers and stitched ASL-Citizen clips, not phone video; intervals are wide.
7. Duplicate/annotation-error audit of the raw datasets is not possible here.
8. Cadence is an accuracy lever **only if** the phone's processed rate actually rises: this is the Phase 2 follow-up (EXP-P3-103), unmeasured.

## Files
**Added:** `eval/recognition_experiments/{__init__,model_contract_check,error_analysis,gate_study}.py`; `tests/test_recognition_experiments.py`; `android/app/src/test/java/com/example/apphear/perceptionvnext/RecognitionAccuracyRegressionTest.kt`; `docs/PHASE_3_RECOGNITION_ACCURACY.md`; `docs/recognition_experiments/{README,REGISTRY,PLANNED,EXP-P3-001…005}.md` and `results/{model_contract_check,error_analysis,gate_study}.json`.
**Modified:** `android/app/src/main/java/com/example/apphear/perceptionvnext/PhoneCommitGate.kt` (argmax guard, §F.4); `context/progress-tracker.md` (dated entry).
**Unchanged by design:** Recognition-v2 and all model assets, vocabulary, confidence floors, camera/analyzer, Phase 2 recovery, Phase 1.1 shadow log, parallel-hands and thread settings.
**Not committed.** The emulator used for §G was started read-only and shut down.
