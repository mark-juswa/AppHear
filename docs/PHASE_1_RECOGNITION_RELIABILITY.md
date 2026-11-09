# Phase 1 — Recognition Reliability and False-Positive Prevention

Date: 2026-11-09 · Branch: `jepjep-claude` (working tree; **nothing committed or pushed**)
Addresses: `docs/PROJECT_RECONNAISSANCE.md` finding **F-001**.

Evidence labels (same as the reconnaissance report): **[CONFIRMED-CODE]** read in code · **[CONFIRMED-RUN]** executed in this phase · **[REPO-REPORTED]** a repo document reports it, I did not reproduce it · **[REPRODUCED]** repo-reported numbers I recomputed independently from the repo's own data · **[SUSPECTED]** · **[EVIDENCE GAP]**.

**No on-device run was made in this phase.** Everything measured below is offline replay of recordings already in the repo.

---

## 0. Correction to my earlier report

`docs/PROJECT_RECONNAISSANCE.md` said no false-positive rate had been measured and that no cross-signer evidence existed for the commit path. **That was wrong in part.** My first directory listing of `docs/` was truncated and I never opened `docs/audit/` (dated 2026-10-16…10-23). It contains a full study of exactly this problem (whole-event admission and a signer-split confidence gate), with an event ledger of human-reviewed phone sessions and held-out-signer streams. I have added an erratum to the top of that report. Everything in this phase builds on that evidence rather than ignoring it.

---

## 1. Initial findings

### 1.1 The exact place a top-1 becomes a committed word  **[CONFIRMED-CODE]**

`perceptionvnext/PhoneProductionSession.kt`, `consume()`, inside `if (event != null)`. Before this phase:

```
prediction = recognizer.invoke(view, …)      // RecognitionV2LiveRecognizer: softmax over 236 classes
top1       = prediction.top5.first()         // unconditional
sentence.add(recognizer.glosses[top1])        // SentenceBuilder mutation
heldCommit = RecognitionState.Committed(…)    // UI state
Update(…, evidence = RecognitionEvidence…)    // Context Assist input
```

Nothing between `recognizer.invoke` and `sentence.add` could say "no". The only upstream filter was the decoder (`PhoneCausalEventProducer`): ≥133 ms ACTIVE, ≥267 ms POST. `PhoneNewSignAdmission` only has `PASS_THROUGH`.

Full path, verified: `Candidate01FrameAnalyzer.analyze` → `PhoneRawObservation` → `PhoneProductionSession.consume` → `PhoneSegmentationFeatureBuilder` (378 floats) → `PhoneS2Runner.predict` (PRE/ACTIVE/POST) → `PhoneCausalEventProducer.consume` → on event: `PhoneObservationRingBuffer.materialize` → `RecognitionV2.temporalView` → `RecognitionV2LiveRecognizer.invoke` → **commit** → `SentenceBuilder` → `onResult` → UI.

### 1.2 What each score actually is (none is assumed calibrated)

| Score | What it represents | Calibrated? | Evidence of use |
|---|---|---|---|
| S2 ACTIVE/POST argmax | A 3-state segmentation label from a separate network (FP32 TCN, 378 inputs). It says "this looks like signing-motion", not "this is a known word". | No. Hard argmax drives the decoder; its probabilities are never thresholded. | S2 peak-ACTIVE separates sign from non-sign poorly: AUC 0.54 on held-out DEV, 0.57 on phone `[REPRODUCED]`/`[REPO-REPORTED]`. |
| Recognition-v2 top-1 probability | Softmax of a closed-set 236-way classifier trained with no "none" class. It is a *ranking score* over known words, so a non-sign window still gets a confident word. | **No.** The live path applies no temperature or calibration to this output `[CONFIRMED-CODE]`. (The `temperature=0.6262` in `recognition_config.json` belongs to the dead 258-feature model.) | AUC 0.75 on held-out DEV; usable only as a dial (§3.3). |
| Top-1/top-2 margin, entropy | Deterministic functions of the same softmax vector, hence the same information. | No. | No better than top-1 (§3.3). |
| Top-1 stability under trimming | Whether the top-1 survives dropping the first/last observation (needs 3 extra recognizer calls). | No. | AUC 0.655, weaker (§3.3). |
| Accepted-hand fraction in span | Share of observations in the logical sign span with ≥1 hand accepted by the hand refiner (presence ≥0.50 and ≥18/21 joints). A perception fact, not a model score. | n/a | Zero fraction ⇒ no hand ever seen in the span (§3.2). |

Because the two networks answer different questions, **I do not combine their scores into one number.** The gate keeps them as separate, individually-justified checks.

### 1.3 Documented incidents and the repo's own measurements  **[REPO-REPORTED]**

Three unwanted words in short live smokes (open hand → HELLO; seat adjustment → HOSPITAL1; movement → STAND2). The repo's whole-event study (`docs/audit/RECOGNITION_V3_CONTINUOUS_RELIABILITY_2026-10-17.md`, §5, §7) concluded:

- A *completed event* does not carry enough commit-time evidence to separate ordinary hands-visible movement from signing without losing words; recognizer confidence "works only as a precision/recall dial: it removes roughly one false event per correct word lost".
- A held-out-signer-calibrated top-1 gate exists as an *optional precision setting* (0.55 for production S2-R2, 0.75 for Arm A + confirm-boundary).
- The next limiter is evidence: ≥30 reviewed hands-visible non-sign events from ≥3 people not in any training set.

Older offline research on the previous landmark model agrees (`E6_3_OPEN_SET_REJECTION_RESULT.md`: AUROC 0.73–0.94 for MSP/energy/Mahalanobis, but **no** threshold met the pre-registered operating point).

---

## 2. Root cause analysis

1. **Architectural, not a bug.** The recognizer is closed-set (236 classes, no "none"), the admission seam is deliberately pass-through, and the commit step performs no post-recognition decision. Any segmentation false-start becomes a word. `[CONFIRMED-CODE]`
2. **Why segmentation false-starts happen** `[REPO-REPORTED]`: S2 does not discriminate signing from the same person's ordinary movement; retraining it on a few phone sessions merely "quiets the whole phone domain" (Arm P: non-sign events 10 → 4 but correct words 19 → 11).
3. **Why a single confidence rule cannot be perfect** `[REPRODUCED]`: held-out-signer AUC of top-1 probability for "correct word vs everything else" is ≈0.75. The gate is a trade-off dial, not a fix.
4. **One structural gap no score is needed for**: events whose logical sign span contains **no observed hand**. The recognizer's input there is entirely "missing", so its output is meaningless however confident. `[CONFIRMED-CODE]` + data in §3.2.

---

## 3. Proposed solution and its evidence

Smallest change that is supported: add a **commit gate** at the single commit point (§1.1) with three outcomes.

| Outcome | Meaning | Rule | Effect |
|---|---|---|---|
| **ACCEPT** | Sufficient evidence | passes both checks below | commit top-1 (unchanged downstream behaviour) |
| **REJECT** | Structurally not a sign / unusable output | (a) no accepted hand in the logical sign span; or (b) non-finite or inconsistent probabilities | nothing committed |
| **UNCERTAIN** | Insufficient evidence | top-1 probability < configuration floor | nothing committed; recognizer keeps running; next episode judged independently |

Thresholds are **not invented**:
- Floor **0.55** for STABLE (S2-R2 + frozen Gate-2 recognizer) and **0.75** for EXPERIMENTAL (Arm A e10 + confirm-boundary + frozen Gate-2) are the operating points the repo already selected with its pre-registered rule: maximize Youden J on three held-out calibration signers (P5, P12, P21), validate on the others (`docs/audit/probes/output_policy/calibrate.py`, `event_reliability/gate_policy.json`).
- `WORD_BLEND_*` configurations have **no calibration**, so they get **no floor**; only the structural rule applies.
- The structural rule is an invariant, not a fitted threshold.

### 3.1 Independent reproduction  **[REPRODUCED]**

`docs/audit/probes/output_policy/phase1_commit_gate_eval.py` (stdlib only, reads only existing ledgers; outputs `phase1_commit_gate_eval.json`, input SHA-256 recorded):

| Configuration | Published (`gate_policy.json`, held-out validation signers) | Recomputed | Match |
|---|---|---|---|
| STABLE @ 0.55 | 101 correct / 102 wrong | 101 / 102 | **yes** |
| EXPERIMENTAL @ 0.75 | 173 correct / 98 wrong | 173 / 98 | **yes** |

### 3.2 Structural rule: what it removes  **[REPRODUCED]**

Events with zero accepted-hand fraction in the logical span:
- STABLE: DEV 9 events (6 wrong-gloss, 3 non-sign fragments); phone 11 events (1 wrong-gloss, 2 confirmed non-sign, 8 unreviewed). **Correct words lost: 0.**
- EXPERIMENTAL: DEV 4 events (3 wrong-gloss, 1 fragment); phone 4 unreviewed. **Correct words lost: 0.**
- It catches one case the probability floor does not: a confirmed non-sign event decoded as **HELLO at top-1 = 0.703** with no hand in the span (SEP27 session).

Caveat: 0 of 20 is a small sample; the justification is the invariant, the data only fail to contradict it.

### 3.3 Alternatives considered and not implemented (pre-registered split: calibrate on P5/P12/P21, validate on P26/P39)  **[REPRODUCED]**

| Score (higher = more correct) | Cal J | Threshold | Validation: correct kept / wrong kept | Val AUC |
|---|---:|---:|---|---:|
| **Top-1 probability (chosen)** | 0.475 | 0.575 | 98/135 · 98/242 | 0.751 |
| Top-1/top-2 margin | 0.447 | 0.582 | 86/135 · 60/242 | 0.733 |
| Negative entropy | 0.497 | −1.149 | 97/135 · 85/242 | 0.762 |
| Top-1 stability under trimming | 0.286 | 0.667 | 110/135 · 130/242 | 0.655 |
| Accepted-hand fraction | 0.181 | 0.800 | 109/135 · 126/242 | 0.630 |

(The repo publishes 0.55, chosen on a 0.05 grid; the 0.575 above is the optimum over the unique observed values in the ledger's events. Same operating region; the repo's 0.55 is what ships, and my recomputation of its counts matches exactly, §3.1.)

Margin and entropy move along the same trade-off curve as top-1 (same information); none dominates. Stability is weaker and triples recognizer cost. Segment duration has AUC 0.49 (no signal). Hand fraction as a *threshold* is weak; only its zero case is used. **No combination rule is supported by this data**, so none was added. Also, for any floor ≥ 0.5, acceptance implies top-1 > top-2 (`p2 ≤ 1−p1 < p1`), so near-ties are already excluded; a unit test checks this.

### 3.4 What the gate measures — held-out results  **[REPRODUCED]**

Event-level, STABLE (S2-R2 + frozen Gate-2). "Ungated" = previous behaviour. Wilson 95% intervals in brackets.

**Held-out DEV validation signers (P26, P39; stitched ASL-Citizen streams; not phone video):**

| | Ungated | Shipped gate |
|---|---:|---:|
| Correct words committed | 135 / 135 | **101 / 135** |
| False-rejection rate (correct words withheld) | 0 % | **25.2 %** [18.6, 33.1] |
| Wrong-gloss events committed | 195 / 195 | 75 / 195 |
| Non-sign fragments committed | 47 / 47 | 27 / 47 (57.4 % [43.3, 70.5]) |
| Precision of committed words | 0.358 | **0.498** |
| F1 (correct-commit) | 0.527 | **0.598** |

**Reviewed phone sessions (development-exposed, one phone, few people):**

| | Ungated | Shipped gate |
|---|---:|---:|
| Correct words committed | 12 / 12 | 10 / 12 (FRR 16.7 % [4.7, 44.8]) |
| Wrong-gloss events committed | 3 / 3 | 1 / 3 |
| Confirmed non-sign events committed | 7 / 7 | **1 / 7** (FPR 14.3 % [2.6, 51.3]) |
| Unreviewed / partial events (not scored) | 18 / 18 | 6 / 18 |
| Precision (scored) / F1 | 0.545 / 0.706 | 0.833 / 0.833 |

EXPERIMENTAL @ 0.75: DEV validation correct 265 → 173 (FRR 34.7 %), wrong-gloss 313 → 72, fragments 57 → 25; phone correct 19 → 16, non-sign 12 → 3 (full table in the JSON).

**Per class (DEV, all signers):** 131 classes have at least one correct event; median retention 1.0; 23 of those 131 lose *all* their (mostly 1–2) correct events at 0.55; among the 17 classes with ≥3 correct events none has zero retention. Support per class is too small for a reliable per-class claim `[EVIDENCE GAP]`.

**How to read this honestly**
- The gate removes most *wrong commits* and costs about a quarter of the correct words on held-out signers. **Half of the words it still commits on held-out signers are wrong** (precision 0.50). It does not make recognition reliable; it makes it more conservative. The phone sample (n=12/7) is far too small to claim a rate; the intervals are wide.
- Held-out DEV is stitched isolated clips, not live phone use. The phone sessions are development-exposed. **No claim of live accuracy improvement is made.**
- The repo's earlier finding stands: the gate removes roughly one wrong event per correct word lost; it is a policy dial.

---

## 4. Negative-input evaluation framework

### 4.1 What already exists and is reused

- `eval/runtime_diagnostics/event_reliability.py`: the event ledger (one row per decoder event with `word_p1`, `word_margin`, `word_entropy`, `word_stability`, S2 stats, `hand_fraction`, motion, and a **human-review category**: `GENUINE`, `DUPLICATE`, `CONFIRMED_NONSIGN`, `PARTIAL_NONSIGN`, `UNCERTAIN`, `UNREVIEWED`, `PROTOCOL_*`). Only reviewed labels are counted as false words; `UNREVIEWED` is never counted.
- `docs/audit/probes/event_reliability/{ledger_*,stream_ledger_*}.json` (production and Arm A) and `gate_policy.py`.
- `eval/runtime_diagnostics/s2_r3_negative_extraction.py` and `s2_r2_phone_non_sign_review.py` (blind visual review tool).
- `context/recognition_upgrade/product_core_data_readiness/collection_targets_v1/nosign_oov_transition_targets.csv`: targets `N0_NO_HAND`, `P1_IDLE_HANDS`, `P1_FACE_ADJACENT`, `P1_ACCIDENTAL_MOTION`, `OOV_SIGN`, `TRANSITION_PARTIAL` (150–200 windows each).
- `context/eval-protocol.md`: split by signer, calibrate on val, test touched once.

### 4.2 Corpus design (data **not** collected here; nothing fabricated)

Capture with the existing shadow build on the target phone, **≥3 people not in any training set**, reviewed blind (reviewer has not seen model output). Each behaviour ≈3 minutes per person:

| Category (user's list) | Capture protocol | Existing target class |
|---|---|---|
| Open-hand idle poses | hands raised/held open, no lexical sign | `P1_IDLE_HANDS` |
| Random hand movements | free gesturing, scratching, hand-on-face, drinking | `P1_ACCIDENTAL_MOTION`, `P1_FACE_ADJACENT` |
| Body movements | shifting posture, leaning, stretching | `P1_ACCIDENTAL_MOTION` |
| Seat adjustments | sit down / reposition chair | `P1_ACCIDENTAL_MOTION` |
| Hand repositioning | rest ↔ ready position, reaching for phone | `TRANSITION_PARTIAL` |
| Partial gestures / incomplete signs | aborted signs started and not finished | `TRANSITION_PARTIAL` |
| Background motion | another person moving behind, no hands in frame | `N0_NO_HAND` |
| Signing transitions | between-sign movement in continuous signing | `TRANSITION_PARTIAL` |
| Out-of-vocabulary real signs | signs outside the 236 | `OOV_SIGN` |

Plus an equal-size set of genuine in-vocabulary signs captured in the same sessions (needed for retention).

### 4.3 Definitions (event level; unit = one decoder-emitted event, labelled by blind review)

Let C = events whose word is correct, W = events with a wrong gloss on a genuine sign, N = confirmed non-sign events. `kept` = outcome ACCEPT.

- **False-positive rate (non-sign)** = N_kept / N. *Primary safety metric.*
- **False rejection rate** = (C − C_kept) / C. *Primary cost metric.*
- **Recall (correct-word retention)** = C_kept / C.
- **Precision of committed words** = C_kept / (C_kept + W_kept + N_kept).
- **F1** = 2·P·R / (P + R).
- **Per-class**: per predicted gloss — correct events, retention, wrong-kept, precision of committed. Report only classes with ≥ ~10 events; others pooled.
- Also: false events per minute of non-sign video; signs never emitted by the decoder are an **upstream miss**, reported separately (they are invisible to the gate).
- Every rate reported with a Wilson 95% interval and per signer, never only pooled.

### 4.4 Acceptance rule for changing a threshold (pre-registered)

1. Calibrate on a signer-disjoint calibration set; validate on other signers; touch sealed TEST once.
2. Minimum evidence to *claim* anything about non-sign rejection: the repo's own bar — **≥30 reviewed hands-visible non-sign events from ≥3 independent people**.
3. A new operating point is adopted only if validation FPR(non-sign) falls and FRR does not exceed a pre-stated budget; report the budget **before** looking at validation. (No budget is asserted here; setting it is a product decision.)

---

## 5. Implementation

### 5.1 Design
- New pure-Kotlin unit `PhoneCommitGate.kt`: `CommitOutcome {ACCEPT, REJECT, UNCERTAIN}`, `PhoneCommitEvidence`, `PhoneCommitPolicy` (+ `DISABLED`), `phoneHandSpanFraction()`, and `PhoneEventCommitter` (owns *event → committed word*: event-id guard, decision, sentence mutation).
- `PhoneProductionSession.consume` now calls the committer instead of mutating the sentence directly.
- `PhoneRecognitionConfiguration.commitPolicy()` holds each configuration's calibrated floor with provenance.
- Build flag `WORD_COMMIT_GATE_ENABLED` (Gradle property `wordCommitGate`, **default true**; `-PwordCommitGate=false` restores the previous commit-every-event behaviour). Release builds are `true`.

### 5.2 Behaviour on non-ACCEPT
- No `sentence.add`, no `heldCommit`, no `RecognitionEvidence` (so Context Assist and `signingTurn` never see it), UI state `Idle`.
- The event id still advances (an event cannot be processed twice) but the "last committed gloss" memory is untouched, so a later repeat of the same word is still committed (SentenceBuilder's existing consecutive-duplicate collapse applies only to accepted words).
- **Display fix.** While the decoder re-arms after a *withheld* event there is no held word, and the recognition screen shows "Initializing recognition…" whenever `phoneReady == false` and the state is `Idle`. I found this in review (before it shipped) and added a display-only `PhoneProductionSession.isReadyForDisplay` (pure helper `phoneDisplayReady`), used by `Candidate01FrameAnalyzer` for `FrameResult.phoneReady`. `isReady` (used by the coordination router) and the behaviour after an *accepted* event are unchanged.
- A `commit_gate outcome=… reason=… top1Probability=… margin=… handSpanFraction=… top5=…` log line is emitted per non-ACCEPT event and extended onto the existing `commit` line. These fields (margin, hand fraction) are exactly what the §4 corpus needs.

### 5.3 What was deliberately **not** changed
Camera, Candidate01 perception (apart from the one-token display readiness above), S2, the event decoder and admission seam, the materializer, Recognition-v2 and its 236-word vocabulary, model files, `SentenceBuilder`, `RecognitionEvidence`, UI, FINGERSPELL, Context Assist, the debug research controller (`PhoneCausalController` and the p-series debug activities, which intentionally log un-gated research output), and any model asset. **Note:** `team-current-state-2026-10-09.md` lists `PhoneProductionSession` as protected "as a side effect of unrelated experiments". This change is an explicit, requested, flagged edit of its commit step only.

---

## 6. Files

Modified:
- `android/app/src/main/java/com/example/apphear/perceptionvnext/PhoneProductionSession.kt` — commit step routed through the committer; `Update.commitDecision` added (defaulted; no caller breaks); `lastCommittedEventId` moved into the committer; private field `sentence` kept (an instrumented test reflects on it).
- `android/app/src/main/java/com/example/apphear/perceptionvnext/PhoneRecognitionConfiguration.kt` — `commitPolicy()` with calibration provenance.
- `android/app/src/main/java/com/example/apphear/perceptionvnext/Candidate01FrameAnalyzer.kt` — one token: `phoneReady` now uses `session.isReadyForDisplay` (see §5.2).
- `android/app/build.gradle.kts` — `wordCommitGate` property and `WORD_COMMIT_GATE_ENABLED` in both build types.
- `docs/PROJECT_RECONNAISSANCE.md` — erratum only.
- `context/progress-tracker.md` — dated entry (repo rule: update after each completed feature).

Added:
- `android/app/src/main/java/com/example/apphear/perceptionvnext/PhoneCommitGate.kt`
- `android/app/src/test/java/com/example/apphear/perceptionvnext/PhoneCommitGateTest.kt`
- `docs/audit/probes/output_policy/phase1_commit_gate_eval.py` and `phase1_commit_gate_eval.json`
- `docs/PHASE_1_RECOGNITION_RELIABILITY.md`

No model asset, native library or feature schema changed (so `feature-schema.md` needs no update).

---

## 7. Tests added (`PhoneCommitGateTest`, 20 tests)

| Requested case | Test(s) |
|---|---|
| High-confidence valid recognition | `highConfidenceValidRecognitionIsAcceptedAndCommitted` |
| Low-confidence rejection | `lowConfidenceIsUncertainAndNothingIsCommitted`, `floorIsInclusiveAndJustBelowIsWithheld`, `aCorrectButLowConfidenceWordIsWithheld…` (documents the cost) |
| Ambiguous top-1/top-2 | `ambiguousTop1Top2IsUncertain`, `anyAcceptedEventHasAStrictlyDominantTop1…` (sweep) |
| Inconsistent consecutive predictions | `inconsistentConsecutiveEventsAreJudgedIndependently…` (see limitation L3) |
| Non-sign input | `nonSignWithNoHandEvidence…` (recorded HELLO@0.703 case), `nonSignEpisodeWithoutHandsProducesNoWordAndRecognitionContinues`, `rejectionTakesPrecedenceOverUncertainty`, `invalidRecognizerOutputIsRejected` |
| Incomplete sign episodes | `incompleteSignEpisodeNeverReachesTheGateAndTheNextValidSignStillCommits` (real decoder: 67 ms ACTIVE is discarded) |
| Duplicate prevention | `duplicateRecognitionIsPrevented` |
| Recovery after rejection / valid after rejected | `recoveryAfterAnUncertainEpisodeAndValidRecognitionFollowingIt`, `nonSignEpisode…RecognitionContinues`, `resetAllowsANewCameraGenerationToRestartEventIds` |
| Backward compatibility | `disabledPolicyReproducesThePreviousCommitEveryEventBehavior` |
| No "Initializing…" flash after a withheld event | `screenReadinessKeepsInitializingOffTheScreenAfterAWithheldEventButNotWhileSigning` |
| Config provenance | `calibratedFloorsAreTheRepoSelectedOperatingPointsAndBlendHasNone` |
| Hand-span evidence | `handSpanFractionCountsOnlyObservationsInsideTheLogicalSpan` |

These prove **behaviour**, not accuracy. Scenario tests drive the real `PhoneCausalEventProducer` with the committer exactly as the session does.

---

## 8. Tests executed and results  **[CONFIRMED-RUN]**

Run on an isolated scratch copy of `android/` (so the repo stays clean of build output) with Gradle 8.14.3, plus a copy of `eval/` because one existing test reads `../../eval`.

| Run | Result |
|---|---|
| `PhoneCommitGateTest` alone | **20 / 20 passed** (19 on the first run; the 20th was added with the display fix, §5.2) |
| Full `:app:testDebugUnitTest` (final code) | **356 tests, 0 failures, 0 errors, 0 skipped** (baseline 336; +20 new) |
| `:app:compileReleaseKotlin` | success (validates the release `BuildConfig` field) |
| `:app:compileDebugAndroidTestKotlin` | success (instrumented tests still compile against the changed session) |
| `phase1_commit_gate_eval.py` | ran; reproduces the repo's published gate counts for both configurations |

**Not run:** instrumented tests on a device/emulator, Python test suite, a release APK build, any live camera test. An arm64 emulator was available but the app was not installed; a virtual camera is not representative anyway.

---

## 9. Performance impact

- Per emitted event (≈ one per sign, not per frame): one pass over the event's window observations (tens of observations; the ring buffer is capped at 256) for the hand fraction, three comparisons, and one extra `Log.i` on non-ACCEPT. **No additional model invocation, no per-frame cost.** `[CONFIRMED-CODE]` structure; the cost is negligible by construction but **was not timed on a device** `[EVIDENCE GAP]`.
- The recognizer still runs on every event (the gate decides after inference). Skipping inference for handless spans would save one recognizer invocation per such event (its cost is logged as `wordMs` but was not measured here); that is a separate change.
- **Behavioural cost** (the real cost): fewer correct words — 25 % fewer on held-out signers at 0.55 and 35 % at 0.75 `[REPRODUCED]`. Users will sometimes see no word for a genuine sign, with no on-screen explanation (L2).

---

## 10. Remaining risks and limitations

- **L1. Precision is still ~50 % on held-out signers.** The gate lowers wrong commits; it does not solve recognition. Phone numbers (n=12/7) have wide intervals and are development-exposed.
- **L2. No UI for UNCERTAIN/REJECT.** The user sees nothing for a withheld sign. The distinction REJECT vs UNCERTAIN is logged but behaves identically. A "didn't catch that" affordance is a product decision I did not make.
- **L3. "Temporal consistency across frames" is not implemented.** The architecture classifies once per event, so there is no frame sequence of predictions to compare, and the only available proxy (stability under trimming) was weaker than top-1 (AUC 0.655) and triples inference cost. UNCERTAIN means "discard and stay armed", not "keep observing the same episode"; true deferred re-classification would need a decoder/materializer change and evidence it helps. The "inconsistent consecutive predictions" test therefore checks independence of consecutive events.
- **L4. No segmentation-confidence or duration rule.** S2 peak-ACTIVE (AUC 0.54–0.57) and duration (0.49) carry no usable signal in the data.
- **L5. Calibration is by a dial, not probability.** 0.55/0.75 are valid only for the exact S2 + recognizer pair they were selected on; any model change requires recalibration. `WORD_BLEND_*` has no floor.
- **L6. Non-sign evidence is thin** (7 labelled non-sign phone events for STABLE: 6 human-confirmed + 1 protocol ordinary-movement; DEV "non-sign" events are mostly sign fragments). The structural rule's 0-of-20 correct-word loss is not strong statistics.
- **L7. Default-on changes release behaviour.** The repo's usual rule is "flag first, default off". I set it **on** because the task requires non-sign input not to commit; `-PwordCommitGate=false` is the kill switch. The prior finding "gate costs correct words" means this is a product trade-off you should explicitly accept.
- **L8. Not verified on a device**; the real analyzer → session → gate chain was exercised only through JVM tests of its parts.
- **L9. Stale/duplicate evidence.** Ledgers are from the 2026-10-16/17 audit builds; the live app has since changed (FINGERSPELL, UI). The decoder/recognizer path used here is unchanged since.

---

## 11. Recommended next steps

1. **Collect the §4 corpus** (≥3 new people, ≥30 non-sign events, blind review), in *shadow mode first*: log `commit_gate` decisions without acting, then compare to labels. The new log fields already carry margin and hand fraction.
2. **Install and exercise on the Xiaomi**: repeat the documented smokes (open hand, seat adjustment, movement) and a fixed HELLO/HOME/TABLE sequence with and without `-PwordCommitGate=false`; record events/min and withheld correct signs.
3. **Decide the product policy** for UNCERTAIN (silent / subtle indicator / prompt to repeat) and the acceptable false-rejection budget.
4. **Recalibrate** the floor whenever S2 or Recognition-v2 changes; add a calibrated floor for any `WORD_BLEND_*` package before it ships.
5. **Skip recognition on handless spans** (saves inference) and consider adding an explicit "none" / open-set head only if the new corpus shows the dial is insufficient — the repo's earlier open-set work (E5-I/E6-3) found that costs large coverage, so treat it as research, not a quick fix.
6. Continue with the reconnaissance roadmap items that interact with this: P1-2 (recoverable analyzer errors), P1-4 (degraded-mode banner) and P3 throughput work — fewer observations per second raise the chance of both segmentation false-starts and missed signs.
