# S2-R3 Arm A/A2 and WORD Robustness — Development Results (2026-10-16)

Branch `claude/s2-r3-eval-suite` (uncommitted; the pre-existing uncommitted work was snapshotted before any change). All new models are isolated research artifacts under `artifacts/…/recognition_utility_236_01/{s2_r3_arm_a_01, s2_r3_arm_a2_01, word_track_robust_aug_01}`. Nothing in Android, the frozen S2-R2 package, the frozen recognizer, WORD/FINGERSPELL coordination or any production path changed. Protected TEST, the E6 signer and Tier 3 were not opened.

Labels: **MEASURED** (reproducible from the files named), **POST-HOC** (chosen after seeing the data), **ESTIMATE**.

---

## 1. Summary

| Question | Answer |
|---|---|
| Does S2-R3 detect more genuine signs? | **Yes, strongly.** Arm A detects 15/23 phone signs with their own event (S2-R2: 11) and 8/11 in continuous sessions (S2-R2: 2). Held-out acquisition after a 12-observation hold rises from 4.5% to 77%. MEASURED |
| Without more false activations? | **No.** Events inside confirmed non-sign intervals rise from 5 to 9, and non-sign ACTIVE observations from 64 to 72. Neither arm met the pre-registered CAL selection rule or the suite v03 gate. MEASURED |
| More correctly recognized words? | **Yes, on the phone set: 8 → 13 of 23 with the same frozen recognizer**, at the same number of wrong outputs (20). All five gains come from the two continuous design-signer sessions; the distinct-signer (paused) sessions are unchanged at 6/12. MEASURED |
| WORD progress | Phone-cadence augmentation lifts signer-disjoint DEV Top-1 from 38.6% to 42.5% at 3.75 fps (paired exact McNemar p = 0.007) and is much more robust to hand loss. It lost 3 of 29 phone oracle signs (two TABLE, where no hands are accepted). MEASURED |
| Best combined system on the phone set | S2-R3 Arm A + augmented recognizer + confidence ≥ 0.9 gives **11 correct / 3 wrong**. Today's system gives **8 correct / 20 wrong**. POST-HOC threshold; needs held-out validation |
| Held-out new signers, broad vocabulary (§5) | **S2-R3 Arm A raises correct words from 16.3% to 29.1% (natural) and from 9.6% to 15.4% (continuous)** on 812 signs from 5 unseen signers, with no rise in extra events in that rest-only setting. MEASURED |
| What limits continuous signing now? | **The event lifecycle.** Arm A acquires 85.6% of direct sign-to-sign signs but gives only 43.7% their own event (130 merged, 210 never emitted). MEASURED |
| Promotable now? | **No.** Both S2-R3 arms fail the phone non-inferiority lines (hands-visible movement), and the WORD model regresses on 3 phone signs. Each needs one more targeted iteration (§7) |

---

## 2. What was built (all new, isolated)

| Component | File | Purpose |
|---|---|---|
| Hands-visible negative extractor | `eval/runtime_diagnostics/s2_r3_negative_extraction.py` | Closes the hands-visible gap with already-governed material (details below) |
| S2-R3 stream builder + trainer | `eval/runtime_diagnostics/s2_r3_train.py`, `model/config/recognition_upgrade/s2_r3_train_01.json` (Arm A), `…_02.json` (Arm A2) | Stitched real-observation streams, D6 model, D7 CAL selection, pre-registered diagnostic fallback, per-epoch checkpoints |
| WORD robustness trainer | `model/perception_vnext/recognition_v2_robust_aug.py` | Recognition-v2 TCN, identical except the per-epoch sparse view (cadence 2.5–7.5 fps, random phase, 0–40% simulated refiner rejection) |
| Held-out full-video DEV extractor | `eval/runtime_diagnostics/heldout_dev_fullvideo_extraction.py` | Full-length Candidate01 raw for the 816 signer-disjoint DEV clips. Videos were found on I: and hash-verified against the frozen manifest |
| Held-out continuous end-to-end benchmark | `eval/runtime_diagnostics/heldout_dev_e2e.py` | Signer-disjoint continuous streams through S2 → decoder → materializer → WORD (§5) |
| Probe options | `docs/audit/probes/pipeline_v3/stage_attribution.py` (`--s2-keras`, `--recognizer`, `--sparse-fps`) | The same end-to-end harness scores any candidate pair |

The hands-visible negative extractor uses:
- **P1:** the 45 human-reviewed P1 intervals, every frame, PRE.
- **Phone:** the design-signer continuous phone session `20260920T145710Z`, re-run through Candidate01 from its 2,747 synchronized frames. PRE applies only inside the 15 human-confirmed non-sign event windows (248 observations); every other row is IGNORE, which supplies real phone context without inventing labels. The approximate sign ranges in that session are not used as labels.
- **E6 stays reserved.**

### S2-R3 training data (Arm A, seed 5103)

- **Streams:** 1,200 FIT streams (294,704 real observations, 60–400 each) and 240 CAL streams. They are built from the signer-grouped split: FIT 22 signers, CAL 6 signers, disjoint.
- **Negatives:** FIT uses P1 P02 and N0 P02/P03; CAL uses P1 P01 and N0 P01/P04. P05/P06 stay held out.
- **Unstitched rows kept:** 219 Phase-7 views, 30 enrichment, 26 P1, 6 exact phone positives, and 6 phone-negative chunks.
- **Label grammar audit (FIT), against the plan's verify step:**
  - POST→ACTIVE 2,175, POST→PRE 4,584, PRE→ACTIVE 5,251;
  - ACTIVE at positions ≥ 61: 23,864 observations;
  - ACTIVE→PRE: 75 (direct cuts whose next segment starts on a PRE row after the 2-observation join-ignore; minor).
- **Rules:** no duplicated or synthetic observations.
- **Arm A2:** identical data and seed. Non-sign rows inside streams get 4× loss weight. Pre-registered after Arm A epochs 1–7 and before any A2 result.

---

## 3. S2-R3 results

### 3.1 Selection (CAL only)

| | Non-sign ACTIVE | First-sign acquisition | Later-sign acquisition | Isolated containment |
|---|---:|---:|---:|---:|
| S2-R2 reference | **1.09%** | 97.1% | 60.7% | 75.0% |
| Arm A, epochs 10–30 | 1.57–6.7% | 92–100% | 95–99.9% | 75–83% |
| Arm A2, epochs 1–30 | 1.65–4.8% | 86–99% | 91–99.7% | 67–81% |

Neither arm had an epoch with CAL non-sign ACTIVE ≤ the S2-R2 rate. **Both runs ended `NO_ELIGIBLE_EPOCH`.**

The pre-registered diagnostic fallback picked:
- Arm A epoch 10 (1.57%, later 95.5%);
- Arm A2 epoch 1 (1.65%), which is undertrained.

These are diagnostic candidates, not D7-selected ones.

### 3.2 Suite v03 gate (frozen before training)

| Line | S2-R2 | Arm A e10 | Arm A2 e1 | Gate |
|---|---:|---:|---:|---|
| T1 none: acquisition / recall | 0.986 / 0.869 | **1.000 / 0.920** | 0.971 / 0.835 | ≥ .95 / ≥ .85 |
| T1 none: false ACTIVE | 0.081 | 0.108 ✗ | 0.129 ✗ | ≤ 0.10 |
| T1 isolated containment | 0.739 | **0.797** | 0.522 ✗ | ≥ 0.689 |
| T1 after previous sign | 0.773 | **0.970** | 0.924 | ≥ 0.90 |
| T1 direct +6 POST | 0.667 | **0.905** | 0.825 ✗ | ≥ 0.85 |
| T1 hold 6 observations | 0.576 | 0.803 ✗ | **0.894** | ≥ 0.85 |
| T1 hold 12 observations | 0.045 | **0.773** | **0.788** | ≥ 0.75 |
| T1 movement-30 recall | 0.914 | 0.840 | 0.686 ✗ | ≥ 0.70 |
| T1 movement-30 history false ACTIVE | 0.133 | **0.000** | **0.000** | ≤ ref |
| T1b held-out no-hands negatives: ACTIVE rate / events per min | 0.006 / 0.24 | **0.000 / 0.00** | 0.001 / 0.00 | ≤ ref |
| T2 signs with a distinct event (of 23) | 11 | 15 ✗ | 15 ✗ | ≥ 18 |
| T2 continuous signs with a distinct event (of 11) | 2 | **8** | **8** | ≥ 7 |
| T2 non-sign ACTIVE observations | 64 | 72 ✗ | 99 ✗ | ≤ 64 |
| T2 non-sign events | 5 | 9 ✗ | 7 ✗ | ≤ 5 |
| T2 POST dwell median | 6.08 s | 4.54 s ✗ | 3.87 s ✗ | ≤ 1.5 s |
| T2 merged events | 0 | 1 ✗ | 0 | ≤ 0 |

**Reading.**
- **The history defect is largely fixed.** The continuous-signing and hold lines move from failing badly to passing or near-passing: hold-12 goes from 4.5% to 77%, and continuous distinct events from 2 to 8. This is the first S2 that keeps detecting signs after a previous sign or hold.
- **Discrimination got worse, not better.**
  - On the phone: about 1.1–1.8× more non-sign activation (8–35 more non-sign ACTIVE observations, 2–4 more non-sign events).
  - On DEV pre-sign rows: a slightly higher false-ACTIVE rate.
  - On held-out no-hands N0 it improves (to zero), so the extra activations come from hands-visible movement, exactly the under-represented data.
- **Weighting the existing negatives (A2) does not fix it.** The model needs more varied hands-visible non-sign data, not heavier weights on 26 P1 intervals and one phone session.

### 3.3 End-to-end phone words (frozen recognizer unless stated)

23 S2-valid reviewed signs:

| First failure | S2-R2 | Arm A e10 | Arm A2 e1 |
|---|---:|---:|---:|
| Not segmented | 11 | 6 (all TABLE, no accepted hands) | 6 |
| Acquired, no event | 1 | 1 | 2 |
| Merged | 0 | 1 | 0 |
| Bad window (still right) / (wrong) | 2 / 0 | 5 / 0 | 3 / 2 |
| Misclassified | 3 | 2 | 1 |
| **Correct words** | **8** | **13** | **12** |
| Unmatched events | 17 | 18 | 16 |

Per session:
- **The gain is all in the continuous design-signer sessions:** SEP27 + OCT15 go from 2 to 7.
- **The paused distinct-signer sessions are unchanged:** SEP23 ×2 stays at 6. S2-R2 already handled paused signing.
- **The remaining misses are perception, not S2:** every TABLE attempt still fails because the refiner accepts no hands (hand fraction 0–0.14).

### 3.4 Combined system on the phone set (POST-HOC thresholds, n = 23 signs, 28–33 outputs)

| System | No gate | ≥ 0.5 | ≥ 0.7 | ≥ 0.9 |
|---|---|---|---|---|
| S2-R2 + frozen recognizer (today) | 8 correct / 20 wrong | 8 / 8 | 7 / 4 | 7 / 2 |
| S2-R2 + augmented recognizer | 8 / 20 | 7 / 3 | 7 / 1 | 7 / 1 |
| Arm A + frozen recognizer | **13 / 20** | 13 / 12 | 12 / 9 | 10 / 6 |
| Arm A + augmented recognizer | 13 / 20 | 12 / 14 | 11 / 8 | **11 / 3** |

The augmented recognizer is less confident on non-sign windows: 2 of 17 false events reach top-1 ≥ 0.5, against 7 with the frozen recognizer. That makes a confidence gate effective. This is the most promising system direction. The thresholds were chosen after seeing this set and must be validated on held-out data.

---

## 4. WORD robustness results

Population: the 816 signer-disjoint DEV clips (span-cut, as the recognizer was trained). DEV is selection-exposed for both recognizers alike; only the training views differ.

| Condition | Frozen | Augmented |
|---|---:|---:|
| Dense | 50.25% | 50.74% |
| 5.6 fps (design) | 39.95% | **42.16%** (McNemar p = 0.13) |
| **3.75 fps (measured phone)** | 38.60% | **42.52%** (82 fixed vs 50 broken, **p = 0.007**) |
| 3.75 fps Top-5 | 69.6% | **73.3%** |
| 5.6 fps, sign end cut 30% | 30.8% | **35.3%** |
| 5.6 fps, 50% hands lost (random / fastest-first) | 33.3 / 33.6% | **43.1 / 46.9%** |
| 3.75 fps, 50% hands lost (random / fastest-first) | 31.5 / 36.4% | **35.0 / 39.2%** |
| Per signer at 3.75 fps (P5 / P12 / P21 / P26 / P39) | 10.7 / 23.2 / 40.5 / 39.9 / 43.0 | **21.4** / 23.2 / **43.0 / 44.6 / 48.0** |
| Phone oracle windows (29 signs: tight / ±250 ms) | 22 / 22 | 20 / 19 |

**Reading.**
- **Gains at real phone conditions are measured and significant.** Cheap, data-free augmentation recovers about 4 of the 11.6 points lost between dense and 3.75 fps, and roughly a third of the hand-loss penalty.
- **The phone regression is concentrated on TABLE.** The frozen model recognized TABLE from body/proposal cues when no hand was accepted; the augmented model lost that (2 signs), plus one HOME.
- **Not promotable yet:** a phone-domain regression on a sign that perception already fails.

**Signer diversity (next WORD lever, prepared, not run).** The Sem-Lex candidate set is on `I:\SEM LEX\AppHear_P5D7_candidate\staged`:

| | Value |
|---|---|
| Hash-listed webms, all present | 2,425 |
| Accepted mapped classes | 65 (exact or compatible variant) |
| New signers | 32 |
| Training clips per covered class | median 13 today, +29 added |
| DEV clips in those classes | 234 |

It is blocked on one governed decision. The recognizer trains on span-cut clips, and the span detector (`pipeline/detect`, d1) consumes Stage-E MediaPipe landmarks, not Candidate01 raw. There are two options:
- port d1 to DWPose wrists, elbows and hips, then validate against existing ASL Citizen spans;
- train on whole clips.

---

## 5. Held-out continuous end-to-end benchmark (signer-disjoint, broad vocabulary)

**The strongest evidence in this report: signer-disjoint, broad vocabulary, untouched by any S2 training or selection.**

- **Population:** 812 of the 816 recognizer-DEV clips with a valid span; 5 ASL Citizen signers absent from every S2 FIT/CAL source and from recognizer TRAIN; 203 streams of 4 signs per mode.
- **Cadence:** the measured phone cadence, 266.6 ms.
- **Streams:** built from full-length videos.
  - NATURAL keeps each clip's own rest.
  - CONTINUOUS cuts clips to the governed span ±1 observation (direct sign-to-sign).
- **Ground truth:** governed automatic spans plus the gloss (not human boundaries).
- **Extra events:** events overlapping no sign. Here the non-sign content is clip rest only, so this is a weak false-activation test compared with phone hands-visible movement.

| System (S2 + recognizer) | Mode | S2 acquired | Sign detected (own event) | **Correct words** | Word precision | Extra events/min | Merged events |
|---|---|---:|---:|---:|---:|---:|---:|
| S2-R2 + frozen (today) | NATURAL | 61.5% | 38.5% | **16.3%** | 34.5% | 1.95 | 11 |
| S2-R3 Arm A + frozen | NATURAL | 81.8% | **63.4%** | **29.1%** | 40.3% | 1.95 | 7 |
| S2-R3 Arm A + augmented | NATURAL | 81.8% | 63.4% | **30.3%** | 42.1% | 1.95 | 7 |
| S2-R2 + frozen (today) | CONTINUOUS | 73.9% | 31.5% | **9.6%** | 29.9% | 0.21 | 61 |
| S2-R3 Arm A + frozen | CONTINUOUS | 85.6% | **43.7%** | **15.4%** | 34.8% | 0.17 | 100 |
| S2-R3 Arm A + augmented | CONTINUOUS | 85.6% | 43.7% | **15.6%** | 35.4% | 0.17 | 100 |
| Oracle windows, frozen / augmented (ceiling at this cadence) | NATURAL | — | 100% | 40.9% / 40.8% | — | — | — |
| Oracle windows, frozen / augmented (ceiling at this cadence) | CONTINUOUS | — | 100% | 36.5% / 39.0% | — | — | — |

**What this shows (MEASURED):**
- **S2-R3 Arm A raises correct words on new signers by about 79% (natural) and 60% (continuous) relative.** Precision is higher and there is no rise in extra events in this rest-only setting. The phone gain (§3.3) therefore generalizes to new signers and broad vocabulary.
- **The augmented recognizer adds about 1 point** end-to-end, and 2.5 points at the continuous oracle.
- **Natural signing reaches 71% of the oracle ceiling** (29.1 / 40.9); continuous reaches 42% (15.4 / 36.5).

**After S2-R3, continuous signing is limited by the event lifecycle.**
- Arm A acquires 85.6% of continuous signs, but only 43.7% get their own event.
- Of the 340 acquired-but-uncredited signs, 130 sit inside an event shared with a neighbouring sign, and 210 never get an event.
- **Diagnostic counterfactual** (re-arm stability 399.9 → 133.3 ms, `--diagnostic-rearm-ms`; not a proposal):
  - continuous detection 43.7% → 49.9%, correct words 15.4% → 18.2%;
  - natural detection 63.4% → 68.5%, correct words 29.1% → 31.4%;
  - extra events per minute +0.1–0.2 (natural);
  - 115 merged and 142 event-less signs remain.

So re-arm explains part of the loss. The rest is event splitting when one ACTIVE run spans two signs with no POST between them, which a re-arm change cannot fix.

---

## 6. What failed and why

1. **D7 selection is unreachable with today's negatives.** No epoch of either arm matched S2-R2's CAL non-sign rate (1.09%). S2-R2 reaches it partly through POST absorption, which also kills continuous detection. The bar is right, but the training data cannot meet it.
2. **Up-weighting existing negatives (A2) traded isolated containment and movement recall for little discrimination.** More weight on 26 P1 intervals is not more information.
3. **The WORD augmentation broke a perception shortcut** (TABLE without hands). Augmentation should keep a share of unmodified sparse views, or the hand-drop rate should be lower.

## 7. Recommended next steps (ordered)

1. **R3b capture now, with more hands-visible non-sign.** This is the binding data gap for S2-R3. The draft protocol in the R3b session has a single ordinary-movement block. Add:
   - non-sign movement between two signs;
   - phone handling;
   - face, hair and glasses touches;
   - gesturing while talking;
   - reaching;
   - all with hands in signing space.

   Also record 2–3 further people for hands-visible negatives only. This is easy, with no signing skill needed, and should be FIT/CAL/held-out by person.
2. **S2-R3 Arm A, iteration 2,** on R3a + R3b with unchanged recipe and selection. Gate on suite v03 plus a held-out hands-visible tier from the new negative-only participants. Arm B (masked phantom proposals) is the planned second arm.
3. **A pre-registered recognizer confidence gate** (a downstream filter, debug flag only): fix the threshold on CAL-style data, then validate on the held-out benchmark and Tier 3.
4. **WORD iteration 2:**
   - augmentation that keeps unmodified sparse views (fixing the TABLE regression);
   - then Sem-Lex signer enrichment after the span decision.
5. **Event lifecycle for direct sign-to-sign** (new, measured in §5). Split events when ACTIVE persists across a sign boundary, and review re-arm/READY; this is the plan's deferred re-arm gate. Evaluate on `heldout_dev_e2e.py` CONTINUOUS together with Tier 2.
6. **Perception: horizontal or flat hands** (TABLE: 0 accepted hands on every phone attempt). After S2-R3 this is the first failure for those signs, and no S2 or WORD change can recover them.

## Reproduce

```bash
python eval/runtime_diagnostics/s2_r3_negative_extraction.py --evidence-root "F:/ASL DATASET/5. Apphear3"
```

```bash
python eval/runtime_diagnostics/s2_r3_train.py train --evidence-root "F:/ASL DATASET/5. Apphear3"
```

```bash
python eval/runtime_diagnostics/s2_r3_train.py train --config model/config/recognition_upgrade/s2_r3_train_02.json --evidence-root "F:/ASL DATASET/5. Apphear3"
```

```bash
python -m model.perception_vnext.recognition_v2_robust_aug --evidence-root "F:/ASL DATASET/5. Apphear3" --output <new dir>
```

Each candidate is then scored with `s2_r3_context_suite.py evaluate --suite 03 …` and `stage_attribution.py --parts phone --s2-keras … --recognizer …`. Outputs are in `docs/audit/probes/{s2_r3_arms,word_track}/`.
