# Recognition V3 — Full-Pipeline Bottleneck Assessment (2026-10-16)

Branch `claude/s2-r3-eval-suite`. Offline, read-only evaluation of frozen components:
- Candidate01 raw-v1 as recorded;
- S2-R2 (suite reference package);
- CONFIG_01 decoder with PRE_OR_POST re-arm;
- the v1 materializer (±250 ms);
- Recognition V2 DENSE (as `PhoneCausalController.kt`);
- the 236-class recognizer `tcn_v2_run_01/best.keras` (`8107accb…`, source of the Android `ordinary_v2_tcn_fp32.tflite`, `1ccf0afa…`).

Nothing was trained, tuned or changed in Android. Protected TEST, the E6 signer and Tier-3 data were not opened.

Labels: **CONFIRMED** = measured here, reproducible from `docs/audit/probes/pipeline_v3/`. **LIKELY** = consistent across several measurements but not isolated. **HYPOTHESIS** = untested or post-hoc. **ESTIMATE** = arithmetic over measured rates.

---

## 1. Answers

| Question | Answer |
|---|---|
| Largest demonstrated failure | **S2 never enters ACTIVE** on 11/23 reviewed phone signs (48%). It is the first failure for 11 of the 15 runtime misses. CONFIRMED |
| Recognition with correct boundaries | Phone (3 glosses): runtime **8/23 → 16/23** (human interval through the runtime materializer) or 17/23 (tight). Signer-disjoint 236-class DEV, boundary-given: **50.3% dense, 40.0% at 5.6 fps, 38.6% at 3.75 fps**. CONFIRMED |
| Is the S2 history problem still major? | Yes as a mechanism, but it is a symptom. A fresh start recovers 11/11 missed signs and doubles activation on confirmed non-sign (19 → 39 of 84 chunks). The real defect is weak sign versus non-sign discrimination on the phone. CONFIRMED |
| Is the WORD model the ceiling? | Yes, for any vocabulary beyond a few heavily trained words: ≤40% Top-1 at phone cadence on new signers even with good boundaries. CONFIRMED (DEV); its phone transfer is LIKELY |
| Does missing hand evidence matter? | Yes, causally. Removing 25/50/75% of accepted hands from well-observed DEV clips drops phone-cadence Top-1 from 53.8% to 44.5/33.3/17.0%. CONFIRMED |
| Next priority | S2-R3, re-aimed at sign/non-sign discrimination with a hands-visible held-out negative gate. In parallel, a recognizer-generalization track and a cheap abstention gate. See §7 |

---

## 2. What was run

| # | Experiment | Population | Status |
|---|---|---|---|
| E1 | N0 raw-v1 extraction recovery | 57 N0 clips (FIT 21 / CAL 19 / HELD_OUT 17) | Complete, verified |
| E2 | Suite v03 freeze (adds the held-out P05/P06 negative tier) | Tier 1 + Tier 1b + Tier 2 | Frozen; reproduces v02 exactly |
| E3 | Per-sign stage attribution with oracle windows | 23 S2-valid reviewed phone signs (4 sessions), plus 6 S2-FIT phone attempts (WORD only) | Complete |
| E4 | Fresh-start S2 control on genuine and confirmed non-sign rows | Same sessions; 84 non-sign chunks | Complete |
| E5 | Unmatched-event analysis and confidence-gate sweep | 28 runtime word outputs | Complete (post-hoc) |
| E6 | Window-construction effect | 69 segmentation-DEV views (recognizer-TRAIN clips; relative only) | Complete |
| E7 | Boundary-error sensitivity (late onset / early commit) | 816 signer-disjoint recognizer-DEV clips | Complete |
| E8 | Causal hand-loss ablation (random and motion-targeted) | 143 DEV clips with hand fraction ≥ 0.75 | Complete |
| E9 | Observation-cadence sweep (5.6 / 3.75 / 3.0 fps) | 816 DEV clips | Complete |

Not run, and why:
- **Full-video runtime S2 on the 816 DEV clips.** The ASL Citizen videos are absent (`ASL_Citizen/videos` is missing; probably on the unmounted G: drive). DEV raw exists only cut to the governed span.
- **Any broad-vocabulary phone test.** No reviewed phone evidence beyond HELLO/HOME/TABLE (plus AT/STREET in the older Gate 4A-1C session) exists.

---

## 3. N0 extraction and suite preparation

- **The first run's error was not recorded.** It exited with code 4 after 17/57 clips. Its stderr was piped through a filter, so the error text was lost. Code 4 is not a Python exception exit code. A rerun with unfiltered output processed the next clip (`n0_p02_08`, hash-verified) and all remaining clips with exit 0 and no error lines. The cause is therefore **not data-dependent**; the most likely explanation is that the process was terminated externally (UNKNOWN beyond that).
- **Preserved outputs are valid.** The 17 earlier npz files were all validated (monotonic timestamps) and reused. Re-extracting `n0_p01_01` from video reproduces every array **bit-identically**, so mixing the two runs is safe.
- **Manifest:** 57 clips. P01 10, P02 11, P03 10, P04 9, P05 8, P06 9.
- **Suite v03 is frozen** (`evidence/s2_r3_context_suite_20261016/suite_freeze_03.json`). Tier 1 and Tier 2 reference results are identical to v02. The new Tier 1b reference (held-out P05/P06, no visible hands) is:
  - 7/1,227 ACTIVE observations (0.57%);
  - 1 event in 4.2 min (0.24/min).
- **Tier 1b is a weak false-activation test.** S2-R2 almost never fires without hands. The false events that matter come from hands-visible movement (§5.3), and no held-out participant supplies that yet. This is the most important remaining gap in the suite (§8).
- **Tests:** 20/20 pass for the suite and the split, including from-source reproduction of v01/v02/v03 and the exact split rebuild. Ruff is clean on the production-side modules.

---

## 4. Where recognition fails — phone stage attribution (E3)

Population: every human-reviewed **GENUINE_SIGN** in the four suite Tier-2 sessions (n = 23; SEP27 7, OCT15 4, SEP23_INDEPENDENT 6, SEP23_REPRESENTATIVE 6). These signs are signer-untouched by S2 training. There are three glosses: HELLO 11, HOME 6, TABLE 6. UNCERTAIN signs are excluded (1 in SEP27 has boundaries; 3 in OCT15 have none).

### 4.1 First-failure waterfall (runtime = S2-R2 + decoder + materializer + recognizer)

| First failure | Signs | Recognizer correct with oracle window |
|---|---:|---:|
| Never observed adequately (<4 obs or <50% frames with an accepted hand), as sole cause | 0 | — |
| **Not segmented** (no ACTIVE argmax inside the sign) | **11** | 7 |
| — of which weak hand observation (all TABLE) | 4 | 2 |
| Acquired, no event (ACTIVE too brief) | 1 | 1 |
| Merged with another sign | 0 | — |
| Event but bad window (<90% coverage); still classified correctly | 2 | 2 |
| Good window, **misclassified** | 3 | 0 |
| Correct | 6 | 6 |
| **Runtime correct total** | **8 / 23 (35%)** | — |
| **Oracle ±250 ms / tight** | — | **16 / 23 (70%) / 17 / 23 (74%)** |

What the waterfall shows:
- **Segmentation is the first and largest failure (CONFIRMED).** Perfect boundaries alone would add 8–9 correct signs, doubling end-to-end accuracy on this vocabulary. A perfect recognizer with today's S2 could reach at most 11/23 (the signs that get a distinct event).
- **No sign was missed because of merging, re-arm or lifecycle (CONFIRMED on this evidence).** Bad windows occurred twice, and both were still classified correctly.
- **The 3 misclassifications are recognizer/perception failures, not boundary failures.** All three stay wrong with oracle windows:
  - HOME → THINK;
  - TABLE ×2 → BABY/ON (NICE with oracle).
- **Downstream suppression is zero by construction.** The V3 path shows the top-1 with no confidence gate (`PhoneCausalController.kt:251`), and no merges occurred.

### 4.2 Perception inside phone signs (CONFIRMED descriptive)

- **Hands are usually observed, except for TABLE.** Median accepted-hand fraction on genuine signs is 0.83. But **TABLE is 0.00–0.14 in all 8 attempts** across every phone signer (including the S2-FIT session). That is a systematic, sign-specific refiner failure on flat, horizontal hands, consistent with the earlier axis-aligned-crop finding. DWPose proposals are present in 100% of frames. Even so, the recognizer gets TABLE right in 4/8 oracle windows.
- **The body reference is often missing.** `body_available` is 0 for most HELLO/HOME signs in the close-framed sessions. Whether that drives the HOME → THINK/WHY/KNOW location confusions is a HYPOTHESIS (one HOME failure had full body).
- **Observation rate is low:** median 267 ms per observation (about 3.75 fps) and a median of 9 observations per sign.

### 4.3 Is perception the cause of the S2 misses? (CONFIRMED: not primarily)

- **Hands were present.** 7 of the 11 non-segmented signs had hand fraction ≥ 0.5, and three had ≥ 0.86.
- **The evidence was sufficient.** S2 started fresh with only five lead-in observations enters ACTIVE on **11/11** of them. The S2 misses are driven by context, not by missing evidence.

---

## 5. S2: history versus discrimination

### 5.1 History dependence is real (CONFIRMED; suite v03 reference)

These are held-out segmentation-DEV views with raw-level stitched histories.

| Condition | Acquired / n |
|---|---|
| None | 68/69 |
| Rest phone history | 69/69 |
| POST phone history (15 / 60 obs) | 10/69 / 12/69 |
| Previous sign, same signer | 51/66 |
| Hold after previous sign: 0 / 3 / 6 / 12 / 24 obs | 63 / 58 / 38 / 3 / 0 of 66 |

In continuous Tier-2 sessions, only 2/11 signs get a distinct event.

### 5.2 A reset does not fix it (CONFIRMED, E4)

The same fresh-start procedure applied to confirmed non-sign rows, chunked to the session's median sign length:

| | Fresh start | Full history (production) |
|---|---:|---:|
| Genuine phone signs entering ACTIVE | 11/11 of the misses | 0/11 |
| Confirmed non-sign chunks entering ACTIVE | **39/84 (46%)** | 19/84 (23%) |
| SEP27 (continuous) non-sign chunks | 26/30 | 11/30 |

The accumulated POST state acts as a crude brake on false activations. Removing it recovers signs and doubles false activation. This is the same trade-off the earlier unconditional-reset work found.

**Conclusion (CONFIRMED):** the binding S2 defect is sign versus non-sign discrimination under phone conditions. History absorption is how S2-R2 implements its (poor) rejection.

**Consequence for S2-R3:** bounded POST alone is predicted to raise recall *and* false events. S2-R3 must learn rejection from hands-visible negatives, and must be gated on held-out hands-visible negatives. This narrows the approved plan; it does not reverse it.

### 5.3 False events (CONFIRMED, E5)

- **Most runtime word outputs are wrong.** The S2-valid sessions produce 28 runtime word outputs: 8 correct, 3 misclassified genuine signs, and **17 events on non-sign activity**. Word precision is **29%**.
- **Where the 17 come from:**
  - 5 lie inside human-confirmed non-sign intervals;
  - 12 come from positioning, warm-up or between-attempt activity in rows outside the reviewed sign and non-sign intervals.
- **None duplicates a preceding sign.** The nearest starts 37 observations after a matched sign.
- **SEP27 alone yields 9.** One comes before the first sign; eight fall in its designed non-sign blocks, 287–880 observations after the last sign.

### 5.4 Abstention gate (HYPOTHESIS, post-hoc, n = 28)

| Top-1 probability threshold | Kept | Correct | Wrong |
|---|---:|---:|---:|
| none | 28 | 8 | 20 |
| 0.3 | 18 | 8 | 10 |
| 0.5 | 16 | 8 | 8 |
| 0.9 | 9 | 7 | 2 |

A cheap downstream gate could halve wrong outputs at no recall cost on this set. It still needs a preregistered threshold and held-out validation (§7, step 3).

---

## 6. WORD recognizer, boundaries, perception and cadence

### 6.1 The DEV number is already a boundary-given number (CONFIRMED)

- **The recognizer only ever saw cut clips.** It was trained and evaluated on raw cut to the governed automatic onset/release span (`offline_candidate01.py:266`; median 30 frames).
- **What that means for the DEV score.** The 50.25% dense / 39.95% phone-cadence DEV Top-1 (reproduced exactly here) is what the model achieves on new signers *when boundaries are good*.
- **Signer spread is wide** (phone cadence): P5 10.7%, P12 24.6%, P21 41.7%, P26 44.6%, P39 41.4%.

### 6.2 Boundary-error sensitivity (E7, phone cadence)

| Window change | Top-1 |
|---|---:|
| Exact span | 39.95% |
| Late onset −10 / −20 / −30% | 39.1 / 39.3 / 38.0% |
| Early end −10 / −20 / −30% | 38.9 / 35.4 / **30.8%** |
| Both −20% | 34.7% |

Late onset is tolerated; **cutting the end hurts** (CONFIRMED). Containment of the sign end matters more than tight starts.

### 6.3 Window construction (E6; recognizer-TRAIN clips, so relative only)

| Window | Top-1 |
|---|---:|
| Whole clip | 33/69 |
| Tight human interval | 40/69 |
| **Human interval ±250 ms** | **53/69** |
| Runtime S2 event | 41/54 emitted (15 views emitted nothing) |

When S2 emits, its window is as good as the ±250 ms oracle: 40 both correct, 2 runtime-only wrong, 1 oracle-only wrong. Window coverage reaches ≥90% in 53/54 windows. **The materializer contract is not a bottleneck** (CONFIRMED). The loss is views with no event.

### 6.4 Perception: causal hand-loss ablation (E8)

Population: 143 DEV clips with hand fraction ≥ 0.75. Accepted hands were removed while proposals were kept, emulating refiner rejection.

| Accepted hands removed | Dense | Phone cadence (random) | Phone cadence (fastest-moving first) |
|---|---:|---:|---:|
| 0% | 60.8% | 53.8% | 53.8% |
| 25% | 60.1% | 44.5% | 44.1% |
| 50% | 49.2% | 33.3% | 33.6% |
| 75% | 26.6% | 17.0% | 23.8% |

**Hand loss causally costs accuracy (CONFIRMED), and it compounds with sparse cadence.** At 30 fps, losing 25% is nearly free; at phone cadence it costs 9 points. The correlational DEV gradient agrees: 17% Top-1 under 0.25 hand fraction, 65% at ≥ 0.9. 34% of DEV clips have hand fraction < 0.5.

### 6.5 Observation cadence (E9)

| Cadence | Top-1 | Median observations |
|---|---:|---:|
| Dense (about 30 fps) | 50.3% | 30 |
| 5.6 fps (design) | 40.0% | 6 |
| 3.75 fps (measured on these phone sessions) | 38.6% | 4 |
| 3.0 fps | 35.7% | 4 |

Most of the cadence penalty (about 10 points) is already paid at 5.6 fps. Raising the phone from 3.75 to 5.6 fps is worth only about 1.4 points to the recognizer alone (CONFIRMED). Larger throughput gains (≥ 10 fps) are untested. The interaction with hand loss (§6.4) is what makes perception worth fixing.

### 6.6 Why the phone oracle (70%) overstates the product (CONFIRMED provenance)

- **The phone glosses are among the best-trained classes.** HELLO has 190 TRAIN clips, against a per-class median of 14. HOME has 10 and TABLE 15.
- **Signer familiarity is unknown.** `APPHEAR_CAPTURE` (297 TRAIN clips, signer `6CC240-S001`) may be the design signer, so the SEP27/OCT15 signer may be familiar to the recognizer. Identity is not authoritative.
- On a broad vocabulary with new signers, the boundary-given ceiling is the DEV figure: about 39–40% Top-1, 71% Top-5.

### 6.7 Combined estimate for natural continuous signing (ESTIMATE)

- **Multiplying the measured rates gives ≈ 20% correct words.** The rates are:
  - phone acquisition ≈ 50% (11/23 + 1 lost before an event);
  - boundary-given recognition ≈ 39% on new signers at phone cadence;
  - hand loss on phone below DEV levels on some signs.
- **Precision is worse.** Today there are about 2 non-sign events per correct word on the demo vocabulary (17 against 8).
- **Fixing S2 completely** lifts this to ≈ 39%. **Fixing recognition completely** with today's S2 lifts it to ≈ 50%. Neither fix alone reaches usable accuracy.

---

## 7. Recommendation

The evidence does not support "S2-R3, then done". It supports this order:

1. **S2-R3 next, re-aimed at discrimination (largest demonstrated, nearest-term gain).**
   - **Why first:** it is the first failure for 48% of reviewed phone signs, and correcting it doubles phone end-to-end accuracy (8 → 16/23). Data, split, suite and plan already exist.
   - **Change of objective:** optimize ACTIVE acquisition *jointly with* rejection of hands-visible non-sign movement, not POST-boundedness alone.
   - **Data:** keep P1 hands-visible negatives in FIT/CAL, and add R3b continuous capture that includes realistic non-sign movement between signs (positioning, adjusting, resting hands up).
   - **Gate addition (blocking):** a held-out *hands-visible* non-sign tier, because Tier 1b N0 cannot catch the failure mode (0.24 events/min).
   - **Gate measure:** the §5.2 fresh-start control is a ready-made check that a candidate has learned rejection rather than relying on history.
   - **Payoff:** this is the step with an evaluation suite in place and a measured upside.
2. **In parallel, start a recognizer-generalization track (the long-term ceiling).**
   - **Why:** 39–40% Top-1 on new signers caps every pipeline.
   - **Product scoping:** what to do with Top-5 = 71% (confirmation UI), or a smaller vocabulary of well-supported words. Words with deep training data (HELLO) are near 100%.
   - **Data:** expand signers per gloss. ASL Citizen is exhausted for this vocabulary; mounting G: restores the enrichment videos.
   - **Evaluation:** report recognizer results at the measured phone cadence (3.75 fps), not only at 5.6.
   - This needs data work and is separate from S2; it does not block step 1.
3. **Cheap, low-risk: a confidence abstention gate in the V3 debug path.**
   - Preregister a threshold on existing data (CAL-style) and validate it on the new hands-visible held-out negatives. It reduces wrong words without touching S2 or the model.
   - It is a filter, not a recall fix.
4. **Perception, targeted rather than general.**
   - **TABLE-type horizontal hands** fail refinement systematically. The earlier rotation probe suggests rotated ROIs. This mainly limits WORD accuracy for such signs, not S2.
   - **Throughput** (3.75 → 5.6 fps) is low-yield for the recognizer alone (+1.4 points). It is worth doing only alongside better hand acceptance, where the two compound (§6.4).
   - **Close framing** removes the body reference (HYPOTHESIS for the HOME confusions); a framing guard is cheap to test.
5. **Deprioritize:** lifecycle/re-arm, merge handling and materializer changes. There is no demonstrated loss in current evidence.

Risk to existing function: steps 1–3 are offline or debug-flag-scoped. The production v3.0 recognizer and the FINGERSPELL path are untouched.

---

## 8. Limitations and the smallest evidence to close them

| Gap | Effect on conclusions | Smallest practical fix |
|---|---|---|
| The phone vocabulary is 3 glosses (HELLO dominates) from about 3 signers; n = 23 | Phone WORD numbers overstate broad-vocabulary accuracy; the S2 findings are better supported | Tier-3: 2–3 new signers × about 20 glosses in short natural phrases, with reviewed boundaries and non-sign intervals |
| No held-out hands-visible negatives | The S2-R3 false-activation gate is blind to the dominant failure | Capture P1-style hands-visible non-sign streams from P05/P06 (already held out) |
| DEV full videos are unavailable | No runtime-S2 measurement on signer-disjoint broad vocabulary | Mount G:, re-extract the 816 DEV videos full length (about 1 h CPU), rerun E3 Part A logic on DEV |
| Design-signer identity is unknown relative to recognizer TRAIN | Possible optimism in SEP27/OCT15 WORD results | Record signer identity in capture metadata |
| The abstention threshold is post-hoc | §5.4 is a hypothesis | Preregister on CAL; test on new held-out data |
| Segmentation DEV are recognizer-TRAIN clips | E6 is relative only | Covered by the DEV-full-video fix above |

---

## Reproduce

```bash
python docs/audit/probes/pipeline_v3/stage_attribution.py --evidence-root "F:/ASL DATASET/5. Apphear3" --out docs/audit/probes/pipeline_v3/stage_attribution.json
```

`--parts handloss` writes `handloss.json`. The cadence sweep (`dev_cadence.json`) uses the same `Recognizer` with `PHONE_COMPLETED_FPS` set to 5.6068 / 3.75 / 3.0.

The suite freeze is reproduced with `python eval/runtime_diagnostics/s2_r3_context_suite.py freeze --suite 03 --evidence-root …` and its tests with `APPHEAR_EVIDENCE_ROOT=… pytest tests/test_s2_r3_context_suite.py tests/test_s2_r3_data_split.py`.
