# WORD Accuracy and Robustness: Difficult Words, Phone Cadence, Camera Conditions (2026-10-18)

Research only, on branch `claude/s2-r3-eval-suite` (uncommitted, on `e2444ebb`). No Android, Candidate01, S2, decoder, materializer, production-default or deployed-model change. Protected TEST, E6 and Tier 3 were not opened. No phone session was used. The phone recordings are development-exposed and were not optimized against.

Evidence labels:
- **MEASURED** — reproducible from the named files.
- **SYNTHETIC** — controlled degradations of webcam video.
- **DEV-EXPOSED** — DEV is used for checkpoint selection by every WORD run.

The unit of evidence is the clip: the phases of one clip are averaged, never counted as independent samples. Paired tests use the per-clip majority. Changes carry signer-cluster bootstrap intervals.

## 0. Preserved live build

You tested this build on 2026-10-18. It is locked as `LIVE_WORD_BLEND_2026-10-18` (`docs/audit/baselines/live_word_blend_2026-10-18.json`; `deploy/lock_live_experimental_baseline.py --profile 2026-10-18-blend --verify` → OK). It is archived in `artifacts/live_baselines/word_blend_live_20261018/`.

| Item | Value |
|---|---|
| Debug APK | `3aa0b4df…` |
| Frozen WORD | `1ccf0afa…` |
| WORD_BLEND_01 | `bc8a6c91…` |
| Arm A | `e7725ef2…` |
| S2-R2 | `7d26c896…` |
| Archived alongside | 88 source files and the live session log |

- **Engines:** STABLE, EXPERIMENTAL, and EXPERIMENTAL_WORD_BLEND.
- **2026-10-17 lock:** still archived. It now shows 5 drifted files; these are exactly the WORD-blend engine edits.
- **Not verified:** the on-device APK hash (the phone was disconnected).

## 1. PLEASE and SORRY (MEASURED, frozen and blend)

| | PLEASE | SORRY |
|---|---|---|
| TRAIN | 11 clips, 11 ASL Citizen signers | 122 clips: 57 APPHEAR_CAPTURE + 51 LOCAL + 14 ASL Citizen |
| Sem-Lex coverage | yes (in WORD_BLEND_01) | no |
| Accepted-hand fraction, runtime windows | 0.37 | 0.40 |
| Independent runtime recall (blend) | 0.07 (7 clips, 7 signers) | 0.33 (3 clips) |
| Main confusions | HAPPY (46% of errors), BABY1, TABLE | LOVE (50% of errors), BABY1, WELCOME2 |
| TRAIN fit at 3.75 fps (in-sample) | 0.55–0.64 | 0.92 overall; ASL Citizen clips only 0.29–0.36 |

**PLEASE** is a hand-on-chest sign that shares its location and flat handshape with HAPPY. The difference is the movement (one hand circling vs both brushing upward) and, for SORRY/PLEASE, the handshape. The hand refiner accepts the hand on the chest in only about a third of observations. Four observations rarely capture the circle. The model cannot separate PLEASE from HAPPY even on its own training clips at phone cadence.

**SORRY** is a data-quality problem first. 108 of its 122 training clips are long local captures: median 86–89 frames, or 11 observations at 3.75 fps. ASL Citizen clips are 22 frames, about 3 observations. The model fits the long captures 100% but only a third of the short ones, so it has learned the capture signer's long SORRY rather than the sign across signers. HELLO, KNOW, GOOD and HAVE carry the same source/duration imbalance.

## 2. Difficult words across the vocabulary

Source: `docs/audit/probes/word_accuracy/difficult_words.py` → `difficult_words.json`. A class is "hard" if its independent runtime-window recall is ≤ 0.30 (DEV + Sem-Lex EVAL, per clip).

| | Frozen | WORD_BLEND_01 |
|---|---:|---:|
| Hard classes (of 236) | 98 | **74** |
| — model cannot fit its own TRAIN clips at 3.75 fps (LOW_FIT < 0.6) | 76 | 50 |
| — accepted-hand fraction < 0.45 (WEAK_HANDS) | 25 | 22 |
| — lost mainly at phone cadence (dense − runtime ≥ 0.25) | 24 | 22 |
| — one dominant confusion partner (PAIR) | 21 | 17 |
| — fewer than 12 TRAIN signers | 15 | 9 |
| — none of these | 10 | 11 |

The hardest blend classes are BECOME, COME, GIFT, HOSPITAL1, IN, WIFE (0 correct), ENTER, KNOW, LAST, PLEASE, CUT, KID, OLD, PERSON, WANT2 and WE. The pair confusions are mostly genuine near-minimal pairs: NOW→TODAY (90% of errors), FIND→PICK 70%, STAND2→JUMP 69%, TOOMUCH→MUCH 58%, SELL→TEACH2, PERSON→PEOPLE, WANT2→GRAB.

Clip accuracy by accepted-hand fraction (blend, runtime windows):

| Accepted-hand fraction | Accuracy |
|---|---:|
| < 0.25 | 27% |
| 0.25–0.5 | 35% |
| 0.5–0.75 | 49% |
| ≥ 0.75 | 56% |

## 3. Is the phone-cadence loss trainable? No (MEASURED)

Even on its own TRAIN clips (800 ASL Citizen clips, span only), every recognizer is right only about half the time at phone cadence:

| Model | Dense | 200 ms (5 obs) | 266 ms (4 obs) | 400 ms (3 obs) |
|---|---:|---:|---:|---:|
| Frozen | 84% | 53% | 47% | 32% |
| WORD v2 augmentation | 87% | 59% | 52% | 37% |
| Blend | 88% | 60% | 53% | 37% |

**Experiment (new, not a repeat).** Every earlier WORD run trains half of each batch on the dense 30 fps view, which the phone never produces. `recognition_v2_robust_aug.py --views sparse_only` removes it from training and from checkpoint selection. Everything else matches the WORD_BLEND_01 members (naive Sem-Lex-ENRICH recipe), paired seed by seed (101/202/303). Script: `compare_sparse_only.py`.

| Paired change, SPARSE − NAIVE | Seed 101 | Seed 202 | Seed 303 |
|---|---|---|---|
| DEV runtime windows, 266 ms | +0.7 [−1.2, 2.9] | −0.6 [−2.3, 0.3] | +1.1 [−1.2, 3.0] |
| DEV runtime windows, 200 ms | −0.6 | −1.0 | −0.9 |
| Sem-Lex EVAL, 266 ms | +4.0 [1.5, 6.0] | +0.3 | +0.6 |
| TRAIN fit at 3.75 fps (in-sample) | 62.4 → 62.8% | 60.3 → 62.5% | 61.8 → 60.8% |

Under the WORD_BLEND_01 rule, the sparse-only members are indistinguishable from WORD_BLEND_01 (DEV −0.1 points). **Conclusion:** the model is not under-trained on sparse input. With four to five observations per sign, the information that separates many classes is simply not in the window. The sparse-only option is not adopted.

**What more observations would buy** (`cadence_curve.py`, DEV runtime windows; ≈ marks the live median):

| Observation interval | Window observations | Frozen | Blend | Blend TRAIN fit |
|---|---:|---:|---:|---:|
| 400 ms | 5 | 33.8% | 40.2% | 37.9% |
| 266 ms | 6 | 42.0% | 49.5% | 51.3% |
| 200 ms (≈ live median) | 9 | 43.7% | 51.4% | 62.2% |
| 133 ms | 12 | 48.6% | 54.7% | 71.4% |
| 100 ms | 16 | 49.6% | 56.7% | 75.3% |

Going from about 5 to 7.5–10 observations per second is worth +3 to +5 points: as much as any WORD change so far, and with no classifier change. Perception speed (Candidate01 takes about 90 ms per frame on the Xiaomi) is a perception/runtime investigation, not a WORD one.

## 4. Camera conditions (SYNTHETIC, `camera_condition_study.py`)

Setup:
- **Subset:** 220 signer-disjoint DEV videos.
- **Perception:** re-run through the unchanged Candidate01 (re-extraction reproduces the stored raw exactly).
- **Degradations:** geometry-preserving only — no flip, rotation, crop or time change.
- **Measurement:** the identical runtime windows.

| Condition | Frames with an accepted hand | Two-hand frames | Frozen runtime top-1 | Blend runtime top-1 | Blend Δ (signer CI) |
|---|---:|---:|---:|---:|---|
| Reference | 38.6% | 20.3% | 34.7% | 42.8% | — |
| Dim + sensor noise | **29.1%** | 13.5% | 27.6% | 34.0% | **−8.9** [−12.5, −5.9], p = 0.0008 |
| Motion blur | 38.1% | 17.9% | 31.7% | 38.6% | −4.2 [−8.1, −0.3] |
| Low contrast | 37.2% | 19.1% | 32.6% | 39.3% | −3.5 [−6.8, −0.9] |
| Low resolution | 40.8% | 20.9% | 33.4% | 40.1% | −2.7 [−5.3, −0.3] |

- **Dim light dominates, through perception:** a quarter of hand observations are lost and WORD follows.
- **Blur and contrast are smaller and partly classifier-side.** Hand acceptance barely changes, but two-hand frames drop.
- **The blend keeps its lead** over frozen in every condition.

These are synthetic sensitivities of webcam video, not measurements of the user's room. They support the user's lighting observation; they do not prove it. Candidate01 was not changed.

## 5. Decision

| Lever | Evidence | Decision |
|---|---|---|
| Signer diversity (Sem-Lex) | Only lever with measured cross-signer gains (WORD_BLEND_01: +7.1 DEV, +16.4 Sem-Lex EVAL) | **Pursue.** 156 uncovered classes have ≥ 5 Sem-Lex candidate signers. The governed review package is prepared (below). |
| Sparse-only / cadence training | Negative (§3) | Not adopted; do not repeat. |
| Faster perception (more observations per sign) | +3 to +5 points from 200 → 133–100 ms (§3) | Propose an isolated perception-speed investigation. |
| Low-light hand acceptance | −8.9 points under synthetic dim light (§4) | Propose an isolated perception investigation (refiner acceptance on the torso and in low light). |
| SORRY / heavy-class source imbalance | Long single-source captures dominate five classes | Fix inside the next data revision (cut local captures to their span or balance by source); no separate run now. |

At the time of this section, no new WORD candidate was proposed: WORD_BLEND_01 remained the experimental accuracy candidate, and the one experiment run here was negative. **Update:** the review was completed the same day and produced WORD_BLEND_02; see §8.

## 6. Governed review package (prepared, awaiting a human)

The package lives in `artifacts/semlex_review_02/` and is built by `eval/runtime_diagnostics/semlex_review_package.py`. Its contents:
- the top 40 uncovered classes from `docs/audit/probes/word_accuracy/semlex_review_priority.csv` (low blend recall × Sem-Lex candidate signers);
- 87 Sem-Lex lexical-form rows;
- 206 Sem-Lex TRAIN clips from different signers, streamed from the local archive (no download);
- 80 ASL Citizen TRAIN reference videos.

Open `review.html` in a browser, choose a P5-D6 decision for each row, and press Export. Every row starts UNDECIDED; nothing is used for training without a decision. One row (WANT2 `freetext:want`) has no clips in the TRAIN archive.

## 7. Next steps (ordered)

1. **Human form review** of `semlex_review_02` (about 87 rows; the top 20 classes are the minimum useful batch).
2. **Train the WORD_BLEND_01 recipe with the accepted forms added** (ENRICH signers only; Sem-Lex EVAL stays held out), fixing the heavy-class source imbalance in the same data revision. Evaluate with `word_vocabulary_eval` / `compare_*` on the identical windows. Only a reproducible multi-population gain becomes an Android debug candidate.
3. **Isolated perception investigations:** hand acceptance in low light and with the hand on the torso, and observation rate.

## 8. Review package 02 completed → WORD_BLEND_02 (MEASURED)

**Decisions.** The human decisions are recorded in `docs/audit/probes/word_accuracy/semlex_review_02_decisions.csv` (sha256 `005099ec…`):

| Decision | Forms |
|---|---:|
| ACCEPT_EXACT_FORM | 45 |
| ACCEPT_COMPATIBLE_VARIANT | 11 |
| REJECT_FORM_MISMATCH | 30 |
| UNRESOLVED | 1 |

All 40 classes have at least one accepted form. Rejected and unresolved forms are never used.

**Ingest.** `semlex_review_ingest.py` covers the accepted labels:
- 2,425 Sem-Lex TRAIN clips carry an accepted label;
- 174 of them are absent from the local TRAIN archive and 12 are undecodable (both logged);
- 2,239 have Candidate01 raw (assets unchanged), and 2,136 have a valid span.

**Training.** Members are trained as WORD_BLEND_01's, plus the new classes:
- **Signers:** ENRICH-role only, 665 clips from 18 signers. The 13 EVAL-role signers (427 clips) are never trained on.
- **Cap:** at most two clips per signer and class, fixed before training (`--extra semlex2_enrich`).
- **Seeds:** 101, 202, 303.

WORD_BLEND_02 applies the pre-registered rule unchanged: 0.5 frozen + 0.5 mean of the three seeds. No seed or weight was selected.

Results on identical windows (`compare_blend02.py`; clip unit, signer-cluster 95% intervals). NEW40 = the 40 reviewed classes.

| Metric | WORD_BLEND_01 | WORD_BLEND_02 | Δ [CI] | Fixed / broken |
|---|---:|---:|---|---|
| Sem-Lex EVAL, NEW40 (13 untouched signers), 266 ms | 18.5% | 29.5% | **+11.1** [8.4, 12.8] | 102 / 0 |
| Sem-Lex EVAL, NEW40, 200 ms | 20.9% | 34.5% | +13.6 [10.3, 15.8] | 123 / 7 |
| DEV NEW40, 266 ms | 21.8% | 33.5% | +11.6 [8.1, 14.4] | 17 / 2 |
| DEV all, 266 ms | 48.6% | 49.6% | +1.0 [−0.6, 2.8] | 34 / 26 |
| DEV all, 200 ms (≈ live cadence) | 50.5% | 53.6% | **+3.1** [1.6, 4.8] | 41 / 12 |
| DEV other classes (REST), 266 / 200 ms | 57.9 / 60.3% | 56.9 / 61.4% | −1.0 n.s. / +1.0 n.s. | — |
| Sem-Lex EVAL, the 64 package-01 classes | 45.8% | 44.8% | −1.0 [−1.8, −0.5] | 21 / 35 |
| End-to-end words, NATURAL / CONTINUOUS | 33.5 / 21.9% | 34.9 / 22.2% | +1.4 / +0.3 | — |
| Phone oracle / runtime (DEV-EXPOSED) | 24/29, 20/22 | 24/29, 20/22 | 0 | — |
| Frozen → WORD_BLEND_02, DEV all 266 / 200 ms | 41.5 / 44.6% | 49.6 / 53.6% | +8.1 / +9.0 | 95 / 20 |

**Members.** Individually, the members again show a prior shift onto the newly enriched classes: REST −0.9 to −3.1 points at 266 ms, two of three seeds significant. Phone runtime varies by seed from 13/22 to 21/22, which confirms the phone set cannot separate candidates. The blend absorbs the shift; the remaining costs are about −1 point and not significant on DEV.

**Android readiness.** WORD_BLEND_02 has been prepared for a later Android debug comparison, but not deployed:
- **Package:** debug-only, in `android/app/src/debug/assets/word_blend_candidate_02/` (model `40533bc3…`, manifest `ae9f8914…`). No Kotlin code references it yet.
- **Host parity:** max abs 4.2e-7, 0 Top-1/Top-5 mismatches, 816/816 DEV agreement, padding invariance.
- **Contract:** same I/O, vocabulary and cost as WORD_BLEND_01 (one 770k-parameter graph, about 10 ms per committed word on the Xiaomi in-app).

**Decision.**
- WORD_BLEND_02 is the next experimental accuracy candidate, ready for a later Android debug comparison (a fourth debug engine, or replacing the WORD_BLEND_01 asset in the debug engine). It needs device evidence before any claim about real phone use.
- Stable and both current Experimental engines are unchanged.
- **Next data step:** the same review for the next ~40 classes in `semlex_review_priority.csv` (ranks 41–80). Then retrain under the same rule, adding the heavy-class source balance in that revision.

### 8.1 Debug engine added and installed (2026-10-18)

- **Engine.** `PhoneRecognitionConfiguration.EXPERIMENTAL_WORD_BLEND_02` ("Experimental + WORD Blend 02"):
  - Arm A e10, confirm-boundary 0.7 and the materializer are identical to EXPERIMENTAL; only the WORD stage changes.
  - WORD_BLEND_02 is displayed and committed.
  - WORD_BLEND_01 classifies the identical view and is logged only (`paired=WORD_BLEND_01`), so a phone session compares 02 against 01 directly.
  - Debug builds only; load failure falls back to STABLE.
  - Stable, Experimental and Experimental + WORD Blend 01 are unchanged.
- **JVM tests.** `ExperimentalRecognitionConfigurationTest` 7/7 (including the Stable and Experimental decoder parity), `PhoneCausalCoreTest` 13/13, `RecognitionV3Stage2RecordedTransitionTest` 3/3.
- **Device** (Xiaomi M2101K7AG):
  - installed with `adb install -r` at 12:13; data and selection kept;
  - on-device `base.apk` sha256 `9b2f6bd9…` equals the local APK;
  - `am instrument` 7/7: WORD_BLEND_02 max abs 2.4e-7 against Keras, frozen class order kept, 5.79 ms median (p95 6.19 ms).
- **Lock.** `DEBUG_WORD_BLEND_02_2026-10-18` (`docs/audit/baselines/debug_word_blend02_2026-10-18.json`, archive `artifacts/live_baselines/word_blend02_debug_20261018/`).
  - The earlier locks report drift only for files edited on purpose afterwards; their archives hold the exact originals.
- **Not yet verified on the device.** Selecting the new engine and running it on the recognition screen. ADB input injection is blocked on this MIUI phone, so that step needs the user.
