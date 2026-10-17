# Recognition V3 — Architecture Iteration Results (2026-10-16, evening)

Branch `claude/s2-r3-eval-suite` (uncommitted, snapshotted again before this milestone). Everything below is offline research. Untouched:
- the Android runtime, Candidate01, the frozen S2-R2 package and frozen recognizer;
- FINGERSPELL, Context Assist, SentenceBuilder.

Protected TEST, the E6 signer and Tier 3 were not opened.

Evidence classes, as requested:

| Label | Data | Status |
|---|---|---|
| **HELD-OUT** | 816 recognizer-DEV clips / 812 valid spans, 5 ASL Citizen signers absent from every S2 source and from recognizer TRAIN | Selection-exposed for the recognizer only, equally for all recognizers |
| **STITCHED** | Continuous streams built by joining those clips | Semi-synthetic |
| **GENUINE PHONE** | The 4 reviewed Tier-2 sessions (23 genuine signs) | Development-exposed: analysed many times, never trained on. UNCERTAIN signs are excluded everywhere |

---

## 1. Approach selected, and why

Keep the architecture: Candidate01 → S2 → event lifecycle → materializer → WORD. Improve four parts in isolation and measure each separately:

| Part | Decision | Reason |
|---|---|---|
| S2 discrimination | **Operating point on the existing S2-R3 Arm A run**: an ACTIVE-probability threshold, chosen on CAL under the original D7 bar | Arm A had the acquisition gain but over-fired. Re-weighting the existing negatives (A2) already failed, and no new negative data exists, so another training run would re-learn the same data. A CAL-selected operating point is free, needs no new model, and its only runtime cost is one comparison |
| Event separation | **Tested three lightweight causal decoder rules; none adopted** | Gains on stitched streams did not appear on genuine phone signing, and false events rose (§3) |
| WORD | **Augmentation v2**: keep the baseline sparse view for half of the draws, cap simulated hand loss at 25%. **Sem-Lex** signer enrichment prepared, span rule ported and validated | v1's regression came from discarding what the baseline already knew |
| Output reliability | **Confidence gate** calibrated on 3 held-out signers, validated on the other 2 | Calibration and demonstration use disjoint people |

## 2. Implemented or trained

| Item | Files / artifacts |
|---|---|
| Event-separation variants (re-entry, short-POST split, maximum-ACTIVE split) as a research decoder subclass, swapped into the reference replay | `eval/runtime_diagnostics/event_separation.py`; `docs/audit/probes/event_separation/{select_on_cal.py, cal_selection.json, evaluate_variants.py, armA_e10_variants.json}` |
| Benchmark additions | `heldout_dev_e2e.py`: split signs, duplicate words, merged events, per-event records, `--decoder-variant` |
| S2 operating-point search: 30 epochs × 7 thresholds on CAL, then a full evaluation of the selected point | `docs/audit/probes/s2_discrimination/{operating_point.py, operating_point.json}` |
| WORD augmentation v2 (trained, 40 epochs) | `model/perception_vnext/recognition_v2_robust_aug.py --variant v2` → `artifacts/…/word_track_robust_aug_02` (best `4f56ce61…`) |
| Confidence-policy calibration (signer split) | `docs/audit/probes/output_policy/{calibrate.py, *.json, phone_false_words.json}` |
| d1 span rule ported to Candidate01 raw; θ fitted on TRAIN, validated on DEV | `pipeline/detect/candidate01_span.py`; `docs/audit/probes/word_track/{span_port_validation.py,.json}` |
| Sem-Lex candidate extraction (2,425 hash-checked webms; undecodable files logged, never fabricated) | `eval/runtime_diagnostics/semlex_candidate_extraction.py` → `artifacts/…/semlex_candidate_raw_01` |
| Sem-Lex enrichment option for the WORD trainer | `recognition_v2_robust_aug.py --extra semlex` |

## 3. Results against the frozen baseline

### 3.1 Complete system, HELD-OUT validation signers (P26, P39; STITCHED; 3.75 fps phone cadence)

Correct words / wrong outputs. Wrong includes wrong gloss, extra events and duplicate events. Gate thresholds were calibrated on P5/P12/P21 only.

| System | No gate | Calibrated gate (threshold) |
|---|---|---|
| **Today: S2-R2 + frozen recognizer** | 135 / 242 | 101 / 102 (0.55) |
| S2-R2 + WORD v2 | 138 / 239 | 86 / 80 (0.65) |
| S2-R3 op-point + frozen recognizer | 250 / 359 | 198 / 174 (0.55) |
| **S2-R3 op-point + WORD v2** | **261 / 348** | **198 / 135 (0.60)** |

All 5 held-out signers, both stream types:

| System | NATURAL detected / correct words / precision | CONTINUOUS detected / correct words / precision |
|---|---|---|
| Today | 38.5% / 16.3% / 34.5% | 31.5% / 9.6% / 29.9% |
| S2-R3 op-point + WORD v2 | **64.0% / 31.2% / 42.2%** | **44.1% / 16.4% / 36.3%** |

### 3.2 Complete system, GENUINE PHONE (23 signs; development-exposed; `phone_false_words.json`)

| | Today, no gate | Candidate, no gate | Today, gate 0.55 | Candidate, gate 0.60 |
|---|---:|---:|---:|---:|
| Correct words | 8 | **10** | 7 | 8 |
| Misclassified genuine signs | 3 | 1 | 1 | 1 |
| Words during confirmed non-sign movement | 5 | 6 | 2 | 3 |
| Other unrequested words | 12 | **3** | 4 | 2 |
| **Total wrong outputs** | **20** | **10** | 7 | 6 |

Per session, correct words today → candidate:

| Session | Today | Candidate |
|---|---:|---:|
| OCT15 (continuous) | 1 | 3 |
| SEP27 (continuous) | 1 | 1 |
| SEP23 representative | 3 | 4 |
| SEP23 independent | 3 | 2 |

### 3.3 S2 discrimination: operating point

**Selection.** 26 of 210 (epoch, θ) pairs met the D7 bar (CAL non-sign ACTIVE ≤ 1.09%). The selected point is **Arm A epoch 21, θ = 0.8**: CAL non-sign 1.05%, later-sign acquisition 98.6% (S2-R2: 60.7%).

**Suite v03** (S2-R2 → Arm A e10 → E21@0.8):

| Line | S2-R2 | Arm A e10 | **E21@0.8** | Gate |
|---|---:|---:|---:|---|
| T1 none: false ACTIVE | 0.081 | 0.108 ✗ | **0.087 ✓** | ≤ 0.10 |
| T1 after previous sign | 0.773 | 0.970 | **0.970** | ≥ 0.90 |
| T1 direct +6 POST | 0.667 | 0.905 | 0.841 ✗ | ≥ 0.85 |
| T1 hold 6 / 12 observations | 0.576 / 0.045 | 0.803 / 0.773 | **0.894 / 0.879 ✓** | ≥ 0.85 / 0.75 |
| T1 isolated containment | 0.739 | 0.797 | 0.768 | ≥ 0.689 |
| T1 movement-30 recall / history false ACTIVE | 0.914 / 0.133 | 0.840 / 0 | 0.865 / 0 | ✓ |
| T1b held-out no-hands negatives | 0.006 / 0.24 per min | 0 / 0 | 0 / 0 | ✓ |
| T2 signs with own event (of 23) | 11 | 15 | 11 ✗ | ≥ 18 |
| T2 continuous signs with own event (of 11) | 2 | 8 | 5 ✗ | ≥ 7 |
| **T2 non-sign ACTIVE observations** | 64 | 72 ✗ | **52 ✓** | ≤ 64 |
| T2 non-sign events | 5 | 9 ✗ | 6 ✗ | ≤ 5 |
| T2 POST dwell median | 6.08 s | 4.54 s | 2.63 s ✗ | ≤ 1.5 s |
| T2 merged events | 0 | 1 ✗ | 0 ✓ | 0 |

The operating point keeps all Tier-1 continuity gains (holds, previous sign) and is the first S2 configuration to pass the Tier-1 false-ACTIVE line and to reduce phone non-sign activation below S2-R2. It still fails 5 lines: direct +6 POST (0.841 vs 0.85) and four Tier-2 lines.

**Why Tier 2 lags.** On the phone it acquires fewer signs than Arm A e10 (9 never segmented vs 6). Phone-sign ACTIVE probabilities run lower than CAL's, and CAL contains no phone positives, so a CAL-only operating point is not calibrated for the phone domain. This is a measured data gap, not a modelling failure.

### 3.4 Event separation (Arm A e10 + frozen recognizer)

| Variant | HELD-OUT STITCHED continuous: detected / correct words / split signs | GENUINE PHONE correct words | Phone words in non-sign movement | Phone unmatched |
|---|---|---:|---:|---:|
| Production decoder | 43.7% / 15.4% / 0 | 13 | 9 | 18 |
| MAX_ACTIVE 2,000 ms (CAL-selected) | 49.0% / 18.7% / 18 | 13 | 11 | 24 |
| REENTRY 1 | 54.8% / 20.2% / 0 | 13 | 11 | 20 |
| REENTRY + SHORT_POST + MAX_ACTIVE | 61.5% / 24.6% / 13 | 13 | 13 | 26 |

**Conclusion: do not change the lifecycle on this evidence.** Every variant adds stitched-stream words and none adds a phone word, while phone false events rise by 2–8. The stitched joins most likely supply boundary cues that genuine signing does not. Genuine direct sign-to-sign evidence is limited to two hands-up blocks (5 signs), too few to decide. The re-entry rule is the safest candidate for later (no within-sign splits, +0.2 extra events per minute on natural streams), but it needs genuine continuous data first.

### 3.5 WORD (HELD-OUT DEV, 816 clips, span-cut)

| Condition | Frozen | v1 | **v2** |
|---|---:|---:|---:|
| Dense | 50.25% | 50.74% | **52.21%** |
| 5.6 fps | 39.95% | 42.16% | **44.00%** (vs frozen: 69 fixed / 36 broken, p = 0.002) |
| 3.75 fps | 38.60% | 42.52% | **43.01%** (81 / 45, p = 0.002) |
| 5.6 fps, 50% hands lost (random / fastest-first) | 33.3 / 33.6% | 43.1 / 46.9% | 39.2 / 46.2% |
| 3.75 fps per signer (P5 / P12 / P21 / P26 / P39) | 10.7 / 23.2 / 40.5 / 39.9 / 43.0 | 21.4 / 23.2 / 43.0 / 44.6 / 48.0 | 21.4 / 24.6 / 45.9 / 46.4 / 44.7 |
| Phone oracle windows (29; ±250 ms / tight) | 22 / 22 | 19 / 20 | **22** / 20 |

- **v2 vs v1:** not significantly different on DEV.
- **v2 removes v1's phone regression** at the runtime-style ±250 ms window.
- **Phone flips against frozen:**
  - fixed 2 HOME (frozen read them as WHY and THINK);
  - lost 1 HELLO (hands-down) and the S2-FIT TABLE attempt.
- **TABLE remains fragile** in both directions because the refiner accepts no hands for it.

**Sem-Lex** (`span_port_validation.json`).

| Item | Result |
|---|---|
| Span port, fitted on 84 TRAIN clips (θ = 0.4×) | — |
| DEV validation against governed spans | onset error median 2 frames (64% ≤ 3), release error median 10 frames, IoU median 0.62, 4% invalid |
| Extraction | 2 of 2,425 webms undecodable (logged) |

Training results are in §3.6.

### 3.6 Sem-Lex enrichment (WORD v2 recipe + Sem-Lex; control = WORD v2)

**Data.** 2,417 of 2,425 staged webms decoded (8 undecodable, logged). The d1 port gave valid spans for 2,252 clips (165 invalid, skipped), adding **65 classes and 32 new signers** to the 3,926 TRAIN clips. No Sem-Lex signer overlaps DEV. Run: `artifacts/…/word_track_semlex_01`; best DEV val_loss 2.04 (v2 2.17, frozen 2.41).

**HELD-OUT DEV, uncorrected model** (`semlex_eval.json`):

| Cadence | All 816: v2 → Sem-Lex | 65 covered classes (234): v2 → Sem-Lex | 171 uncovered (582): v2 → Sem-Lex |
|---|---|---|---|
| Dense | 52.2 → 55.3% (p = 0.07) | 40.2 → **60.3%** (60 fixed / 13 broken, p < 1e-7) | 57.0 → 53.3% |
| 5.6 fps | 44.0 → **48.4%** (p = 0.006) | 37.2 → **53.8%** (p < 1e-5) | 46.7 → 46.2% |
| 3.75 fps | 43.0 → 42.0% (n.s.) | 37.6 → **50.0%** (p = 1e-4) | 45.2 → **38.8%** |

**Cause of the uncovered loss: prior shift.** The 65 enriched classes gained about 60% more training mass, so the model predicts them more often.
- Restoring the original prior fully (exponent 1, fixed in advance) recovers the uncovered classes (3.75 fps: 46.2%) but removes most of the covered gain (38.9%) (`semlex_prior_correction.json`).
- The exponent is therefore chosen on calibration signers P5/P12/P21 and reported on validation signers P26/P39 (`semlex_prior_signer_split.json`):

| Cadence (chosen exponent) | Validation all: v2 → Sem-Lex | Covered | Uncovered | Paired test |
|---|---|---|---|---|
| 5.6 fps (0.5) | 45.9 → **50.3%** | 41.0 → 51.8% | 47.9 → 49.7% | 56 fixed / 35 broken, **p = 0.035** |
| 3.75 fps (0.8) | 45.5 → 48.0% | 38.8 → 46.8% | 48.2 → 48.5% | 56 / 44, p = 0.27 |

**Phone oracle windows (29 signs):**
- HOME (covered): 5/8 → 7/8 (v2) → **8/8**.
- TABLE (uncovered; no accepted hands on the phone): 4/8 → 3/8 → **0/8**.
- Total ±250 ms: 22 → 22 → 20.

**Reading.**
- **Signer diversity is the WORD lever (MEASURED).** Classes that received 32 new signers improve by 8–20 points on held-out signers.
- **Enrichment must be class-balanced**, either by enriching every class or with a calibrated prior correction; otherwise uncovered classes pay at phone cadence.
- **TABLE needs perception, not data.**

### 3.7 Latency and Android cost

**Device measurements** (Xiaomi; sessions 20261015T155027Z and 20260927T162103Z):

| Stage | Median | p95 |
|---|---:|---:|
| Observation interval | 200 ms | 267 ms (slower while signing) |
| Candidate01 pose inference | 87–92 ms | — |
| S2 | 7 ms | 24 ms |
| Recognition V2 features | 10–14 ms | — |
| Recognizer invocation | 2.7 ms | — |

**Cost of the candidates.** They keep the deployed architectures (S2 TCN 123,779 parameters; recognizer 192,556), so per-observation and per-event compute is unchanged. The threshold and the gate are one comparison each.

**Sign-end-to-commit latency** on the genuine phone sessions:

| Configuration | Median | p90 | n |
|---|---:|---:|---:|
| S2-R2 | 0.67 s | 1.07 s | 11 |
| Arm A e10 | 0.63 s | 1.64 s | 16 |
| E21@0.8 | 0.73 s | 1.61 s | 11 |

## 4. Remaining problems and regressions

1. **Phone-domain acquisition at the CAL operating point.** E21@0.8 gives 9 phone signs no event at all: 5 TABLE with no accepted hands, plus 4 others. Arm A e10 missed 6. CAL has no phone positives.
2. **Tier-2 gate still fails:**
   - signs with own event: 11 vs 18 required;
   - continuous signs with own event: 5 vs 7;
   - non-sign events: 6 vs ≤ 5;
   - POST dwell: 2.6 s vs ≤ 1.5 s;
   - direct +6 POST: 0.841 vs 0.85.
3. **Continuous separation.** 44% of held-out continuous signs get their own event, and no decoder rule is validated on genuine signing.
4. **TABLE / flat hands.** Perception accepts no hands, which caps both S2 and WORD.
5. **Repeated signs.** Only one genuine repeat block exists (OCT15 C; second repetition UNCERTAIN), so repetition handling is untested.
6. **The confidence gate costs correct words.** On validation signers it keeps 76% of correct words while removing 61% of wrong outputs; on the phone, 8 of 10. It supports, not replaces, segmentation and classification.

## 5. Continue, adjust or abandon

| Track | Verdict |
|---|---|
| S2-R3 (Arm A + operating point) | **Continue, adjusted.** Recipe and operating-point selection work. The next gain needs a CAL set with phone-domain positives and hands-visible negatives, so the operating point is calibrated for the phone |
| Decoder rule changes | **Pause.** No genuine-signing benefit; revisit re-entry only with genuine continuous data |
| WORD augmentation v2 | **Continue.** Significant held-out gain, no net phone regression. Candidate for the next device package |
| Sem-Lex enrichment | **Continue, with class balance.** Covered classes gain 8–20 points on held-out signers. Next: map more of the 170 unresolved Sem-Lex classes (human review), and train with balanced enrichment or a calibrated prior correction. Not deployable as-is (uncovered loss at 3.75 fps without correction; TABLE 0/8) |
| Confidence gate | **Continue as an optional debug-flag filter**, threshold fixed by the signer-split calibration |

## 6. Next most valuable step

**One small genuine phone capture, split by role (FIT / CAL / held-out),** then re-select the S2 operating point on a CAL set that includes the phone domain:
- R3b continuous sign-to-sign, holds and repeats from the design signer (FIT);
- plus 2–3 additional people;
- each person contributes a short continuous hands-up sign sequence and about 2 minutes of hands-visible non-sign movement (phone handling, face/hair touches, gesturing, reaching).

This single capture resolves three of the open items at once:
- phone-domain calibration;
- genuine evaluation of event separation;
- held-out hands-visible false-activation measurement.

In parallel: package S2-R3 E21@0.8 + WORD v2 as debug-only `S2_R3_CANDIDATE` / recognizer-candidate assets, with Keras→TFLite parity, for a device smoke test behind the existing selector.
