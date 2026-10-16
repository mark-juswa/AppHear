# S2 history dependence — verification and cause analysis

Date: 2026-10-16. Scope: offline only. No change was made to any model, Android source, asset,
branch or artifact. The frozen S2-R2 package (Keras `b6f8b52c…` with FIT normalization) and the
Phase-7 control were evaluated read-only. The scripts and JSON outputs are in
`docs/audit/probes/s2_history/` (Appendix A).

Labels: **CONFIRMED** (measured here), **LIKELY** (several independent measurements agree),
**HYPOTHESIS** (needs a test), **REJECTED** (contradicted by the measurements here).

> **Correction to the audit.** The audit (`APPHEAR_TECHNICAL_RESEARCH_AUDIT_2026-10-16.md` §1,
> §8.3 and R1) attributed missed signs to a *history-length / padding* shortcut. This
> investigation **rejects length as the primary mechanism**. The dependency is real, but it comes
> from the *content* of the history:
>
> - S2 learned POST as a terminal state that it never leaves.
> - Phantom hand proposals at rest push it into POST.
>
> The audit's oracle-reset table is reproduced exactly; its interpretation is what changed.

---

## 1. What was reproduced

| Check | Result |
|---|---|
| Frozen Keras S2-R2 vs Android, rolling 61 history | **CONFIRMED.** Four sessions, 3,348 observations, max \|Δp\| ≤ 1.3e-6, **0 argmax mismatches**. No history resets occurred in any session. |
| Python port of `PhoneCausalEventProducer` (PRE_OR_POST, PASS_THROUGH) | **CONFIRMED.** Reproduces **28/28** recorded events exactly (10 + 4 + 7 + 7). |
| Audit oracle-reset table (Sep 27, Oct 15) | **CONFIRMED.** Identical numbers, e.g. Sep 27 A-TABLE rolling 0/10 vs fresh@onset−4 10/10. |
| Stage-2 rejected reset-after-re-arm probe (Sep 27) | **CONFIRMED.** Exactly reproduced: events 10→20, fully contained non-sign events 4→9. |

**Reconciling counts across reports (CONFIRMED):**

- The audit's "10 of 12" covered the two design-signer sessions. Those contain 11 genuine signs
  plus 1 uncertain sign.
  - The Stage-2 investigation's "6 of 7 confident signs with zero ACTIVE" is Sep 27.
  - The device report's "3 of 4" is Oct 15.
- This investigation adds two September 23 S2-R2 validation captures (12 genuine attempts):
  - `phone_pull_s2_r2_independent_validation/session_20260923T013439Z`
  - `phone_pull_s2_r2_representative_final_validation/session_20260923T030939Z`

  Both are declared distinct-signer, untouched-validation sessions with blinded labels.
- That gives **23 genuine reviewed signs** across four sessions.
- With the unchanged runtime, S2 acquired ACTIVE on **12/23**:

  | Session | Acquired |
  |---|---|
  | Sep 27 | 1/7 |
  | Oct 15 | 1/4 |
  | Sep 23 independent | 4/6 |
  | Sep 23 representative | 6/6 |

  The last two match the earlier S2-R2 validation reports exactly.

---

## 2. Was S2's history really the problem? Yes — but not its length

### 2.1 Long history by itself does not suppress signs (length shortcut REJECTED as primary)

- **CONFIRMED.** In both September 23 sessions, every attempt began with a **full 61-observation
  history**, and S2 still acquired 10 of 12 signs.
- **CONFIRMED, controlled test on held-out signers.** The test used the 69 DEV views (23 clips,
  7 signers) that never trained either model. A real 60-observation history was prepended to each
  sign, and only S2 states were scored, so the lifecycle could not interfere.

| History before the same held-out sign (S2-R2) | Acquired | ACTIVE recall | False ACTIVE in the clip's own PRE/POST |
|---|---:|---:|---:|
| None (training condition) | 98.6% | 0.869 | 0.081 |
| 60 obs of real phone rest (S2 = PRE) | **100%** | 0.898 | 0.089 |
| 60 obs of the same scene held perfectly still | 85.5% | 0.743 | 0.081 |
| 60 obs of a real P1 non-sign recording | 79.7% | 0.672 | 0.091 |
| A previous sign by the same signer | 77.3% | 0.548 | 0.044 |
| **15 obs where frozen S2 sits in POST** | **14.5%** | 0.087 | 0.002 |
| **60 obs where frozen S2 sits in POST** | **17.4%** | 0.098 | 0.002 |

The Phase-7 control shows the same pattern: 100% → 0% with POST history, and 100% with rest
history.

There is a **real but small length/position component** (still history: 98.6% → 85.5%). The
training data does have the confound the audit found (§2.3). But it is small next to the effect
of POST content.

### 2.2 The supported mechanism: S2 learned POST as an absorbing state (LIKELY, strong)

- **CONFIRMED, training labels.** Across all 302 S2-R2 FIT sequences and all 213 Phase-7 FIT
  sequences:
  - transitions are only PRE→ACTIVE (227) and ACTIVE→POST (261);
  - there are **zero POST→ACTIVE and zero POST→PRE transitions**;
  - no sequence contains two signs.

  POST is always the end of the sequence, so the model never saw an example of leaving it.
- **CONFIRMED, runtime behaviour.** In the two continuous sessions, after each committed event:
  - the app shows READY after a median of **534 ms**, because PRE_OR_POST re-arm accepts POST as
    "stable";
  - S2 itself first leaves POST after a median of **6.1 s (24 observations)**;
  - in **13 of 14 events S2 was still in POST when READY appeared.**

  The user sees READY, starts the next sign, and S2 cannot go ACTIVE. Waiting with the hands down
  for several seconds is what flushes POST out of the 61-observation window. That matches the
  reported "hands down and wait".
- **CONFIRMED, direct transitions on held-out signers.** The previous sign is cut just after its
  ACTIVE, then the next sign follows with a brief hold of k POST observations.

  | Hold between signs | S2-R2 acquired (all views) | At the densest cadence (VIEW_A, 133 ms) |
  |---|---:|---:|
  | 0 POST obs | 95.2% | 86% |
  | 3 POST obs | 82.5% | 52% |
  | 6 POST obs | 66.7% | 29% |

  The longer the hands rest in a "post-sign" pose, the less likely the next sign is detected.
- **CONFIRMED, history composition before reviewed signs** (23 genuine phone signs):
  - when the 10 observations before onset were mostly PRE: acquired **9/12**;
  - when they were mostly POST: acquired **3/10**.

### 2.3 Position confound in the training data (CONFIRMED; secondary effect)

ACTIVE labels sit at median index 8 from the start of their sequence (p90 22). **98.8%** of them
are at index < 60, so S2 almost never saw ACTIVE with a fully real receptive field. Negative
sequences are long (median 73). This explains the modest drop under still or P1 histories (§2.1).
It does not explain the collapse, which needs POST content.

### 2.4 Why the design-signer sessions fail and the validation sessions did not

Two factors, both measured.

**(a) Capture pauses (CONFIRMED).**

| | Sep 23 validation sessions | Sep 27 / Oct 15 |
|---|---|---|
| Pauses in observation delivery | 6 per session, **20–130 s**, between attempts | 0 pauses > 2 s |
| What precedes each sign | Tens of seconds of pause, then quiet rest; any POST has long flushed | A previous sign or movement a few seconds earlier |

The earlier S2-R2 validations (6/6, 4/6), and the September 23 real-app smoke test with READY
waits, therefore measured *isolated signs after long rests*. They did not measure continuous use.

**(b) Phantom hand proposals at rest push S2 into POST (LIKELY).**

- **CONFIRMED:** with the hands at rest and out of frame, DWPose still produces hand ROIs in
  58–100% of rest observations, while the refiner accepts a hand in only 1–28%.
- These phantom ROIs land in scene-dependent places and jitter. In the design-signer sessions,
  rest rows S2 calls POST have **about 3.5× the ROI motion** of rest rows it calls PRE (Sep 27: 0.275
  vs 0.080; Oct 15: 0.433 vs 0.124). Training POST rows also have the highest ROI motion.
- Whole-session POST share:

  | Session | POST share |
  |---|---|
  | Oct 15 | **68%** |
  | Sep 27 | 31% |
  | Sep 23 representative | 18% |

- **CONFIRMED, diagnostic.** The test clears refiner-rejected proposals from the S2 input and
  recomputes the dependent deltas. It is not deployable, because the model was trained with them.

  | Measure | Original | Phantom proposals removed |
  |---|---|---|
  | Oct 15 POST share | 0.68 | 0.17 |
  | Sep 27 POST share | 0.31 | 0.13 |
  | Acquisition, 4 sessions | 12/23 | **17/23** |
  | Total events | 28 | 20 |
  | Non-sign events | 5 | 4 |
  | Unlabelled extra events | 12 | 4 |
  | Non-sign ACTIVE observations | 64/676 | 55/676 |

  On held-out DEV, the same change *reduces* acquisition (98.6% → 84.1%). The model relies on the
  proposal channels it was trained with, so this is evidence of mechanism, not a fix.
- **CONFIRMED, phone perception is weaker than training perception.** For accepted phone hands,
  DWPose hand support has p10 of 0.10–0.22, against 0.45 in S2-R2 training data.

### 2.5 Other candidate causes

| Candidate | Verdict | Evidence |
|---|---|---|
| Train/serve feature or normalization error | **REJECTED** | Exact parity (§1) |
| History length / padding alone | **REJECTED as primary**, minor contributor | §2.1, §2.3 |
| POST-terminal label grammar | **LIKELY primary** | §2.2 |
| Phantom proposals / rest-scene perception | **LIKELY contributor**; explains session-to-session variation | §2.4 |
| Sparse delivery | **Secondary modulator** | DEV acquisition with no history (cropped to start just before the sign) is ≥0.91 at every cadence. POST suppression is stronger at the densest cadence in observation terms (§2.2). At ~5 obs/s, a 24-observation POST dwell lasts about 5 s. |
| Recovery timer (400 ms) | **Not the bottleneck** | READY arrives at 0.5 s while S2 stays POST for ~6 s |
| Decoder after acquisition | **Real secondary loss** | Even when S2 acquires, ACTIVE→PRE without POST is discarded (e.g. under a 12-observation cap: 23/23 acquired but 18/23 with an event) |

---

## 3. Can we fix it at runtime by changing the history? No (CONFIRMED)

Stream-level results use the exact decoder on all four sessions: 23 genuine signs and 676
reviewed non-sign observations.

| Policy | Signs acquired | Signs with an event | Total events | Events inside non-sign | Non-sign ACTIVE obs |
|---|---:|---:|---:|---:|---:|
| Current (rolling 61) | 12/23 | 11/23 | 28 | 5 | 64 |
| History cap 8 | 23/23 | 13/23 | 30 | 9 | **224** |
| History cap 12 | 23/23 | 18/23 | 39 | 10 | 141 |
| History cap 16 | 22/23 | 18/23 | 40 | 7 | 138 |
| History cap 32 | 15/23 | 12/23 | 30 | 6 | 107 |
| Reset after re-arm (rejected earlier) | 19/23 | 15/23 | **50** | 10 | 132 |

Every history manipulation that recovers signs also roughly doubles false ACTIVE on genuine
non-sign movement. Today the long POST history does two jobs:

- it **suppresses false alarms**;
- it **wrongly suppresses the next real sign**.

A runtime cap or reset cannot separate them. That needs a model that has learned to tell signing
from non-signing motion *with* realistic context. This independently confirms the earlier
rejection of the reset.

---

## 4. What this means for Recognition V3

1. **The S2 history-dependence finding is supported, but with a corrected mechanism.** S2 cannot
   leave POST except by its receptive field filling with rest. In continuous signing it stays in
   POST for seconds after each sign, so the next sign is missed while the UI already says READY.
   Phantom hand proposals at rest make this worse in some scenes.
2. **The suspected "length shortcut":**
   - **Length as the main cause: REJECTED.**
   - A minor position confound is CONFIRMED.
   - **A grammar shortcut (POST is terminal; there is only one sign per sequence): LIKELY, with
     strong evidence.**
3. **This is the main cause of the consecutive-sign failure in these recordings.**
   - It does not explain the recognizer's ~40% accuracy.
   - It does not explain motion-related hand dropout (audit §7), which is separate.
   - TABLE-type perception failures still matter for recognition, but S2 acquired TABLE with a
     fresh context, so they are not what blocks segmentation.
4. **Retraining S2 is justified.** It must be retrained on **realistic sequence structure**, not
   just longer sequences. Runtime fixes and timer changes are not justified.
5. **A different segmentation paradigm is not yet required.**
   - A shorter-context classifier (approximated by the caps) does not solve discrimination.
   - Rule-based segmentation was already rejected (Phase 5.0).
   - The data and labels, not the TCN architecture, are what is missing.
6. **Perception changes should be considered together with the S2 retrain only where they touch
   S2's input** (phantom proposals). The WORD classifier already ignores refiner-rejected hands,
   and FINGERSPELL is untouched. So masking phantom proposals is an S2-only contract change that
   can be tested inside the same experiment.
7. **Earlier validation results overstated continuous readiness** (§2.4a).

---

## 5. Recommended next engineering decision

**Decision: start one offline S2 retraining experiment ("S2-R3"), planned through `/architect`.
Do not change the Android runtime, timers or history policy in the meantime.**

**Training data.**
- Stitch real raw-v1 clip observations into continuous streams, with labels kept at
  human-boundary resolution and joins marked as ignore:
  - sign → sign directly;
  - sign → hold k → sign;
  - sign → rest → sign;
  - sign → return-to-rest (POST→PRE);
  - long rest and non-sign streams that include phone-style phantom proposals.
- Recompute the 378 features over the stitched raw sequence, so deltas at joins are real
  differences, not copies.
- Decide label semantics before training. "Held still after a sign" must not be terminal; options
  are POST with a bounded duration then PRE, or a separate HOLD state. A 4th state is a contract
  change.

**Input A/B within the same experiment.**
- Current 378 contract.
- A versioned contract that masks refiner-rejected proposals (S2 only).

**Pre-registered evaluation, frozen before training.**
- The history-condition suite from this report becomes a regression suite: §2.1 table, §2.2
  direct transitions, and the §3 stream metrics.
- The two continuous sessions and the two September 23 sessions are diagnostics, not tuning
  targets.
- Success requires:
  - higher second-sign acquisition and signs-with-event;
  - **no increase** in non-sign ACTIVE observations or non-sign events against the current
    rolling-61 baseline;
  - no DEV regression in isolated containment.

**Final gate.** A new continuous capture with a qualified signer, with no capture pauses, hidden
predictions and human boundaries. This is the audit's R3 benchmark.

**After a successful S2-R3:**
- Switch re-arm back toward PRE-based readiness, so READY reflects S2's actual state.
- Then revisit the decoder's ACTIVE→PRE discard (§2.5).

Things not to do:
- deploy history caps or resets;
- shorten timers;
- tune on the four sessions;
- claim continuous improvement from paused-capture validations.

---

## Appendix A — Reproduce

The scripts run with `F:/ASL DATASET/5. Apphear3/.venv/Scripts/python.exe -I` from
`docs/audit/probes/s2_history/`, with that directory on `sys.path`. They read only:

- the frozen S2-R2 and Phase-7 checkpoints and normalizations;
- the Phase-7 DEV sparse views and the S2-R2 dataset manifest;
- four session captures and their human reviews.

| Script | Report section |
|---|---|
| `step1_reproduce.py` | §1, parity, decoder port, oracle table (`step1.json`) |
| `step2_history_content.py` | §2.2, state mix before onset |
| `step3_dev_history.py` | §2.1, held-out DEV history conditions (`step3.json`) |
| `step4_policies.py` | §3, runtime history policies (`step4.json`) |
| `step5_rest_profile.py`, `step6_support.py` | §2.4b |
| `step7_sanitize.py` | §2.4b, diagnostic |
| `step8_label_grammar.py` | §2.2–2.3 |
| `step9_post_dwell.py` | §2.2, READY vs POST dwell |
| `step10_direct_transition.py` | §2.2, direct transitions |

## Appendix B — Limits

- **Few signers.** There are three signer identities at most: the design signer plus two
  sessions declared distinct. Whether those two are different people is UNKNOWN. Signing
  proficiency is unknown or nonexpert.
- **Synthetic histories.** Stitched DEV histories and direct transitions introduce one artificial
  join row. Phone histories come from another domain. Every key conclusion is supported by both
  synthetic and real-session evidence.
- **Sanitization is not deployable.** The phantom-proposal diagnostic is out-of-distribution for
  the trained model. It shows a mechanism, not a solution.
- **No reserved sets opened.** The protected TEST, the reserved E6 negative signer, and the
  future independent phone signer were not opened.
