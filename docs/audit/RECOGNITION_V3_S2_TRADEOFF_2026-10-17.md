# Recognition V3 — Why S2 Trades Signs for Silence (2026-10-17)

Branch `claude/s2-r3-eval-suite`. Nothing is committed, pushed or merged.

**What did not change:**
- Android, Candidate01, the frozen S2-R2 and WORD packages, the production decoder, the
  materializer, SentenceBuilder, FINGERSPELL and Context Assist.
- WORD is fixed to the frozen recognizer throughout.
- Protected TEST, E6 and Tier 3 were not opened, and no new data was downloaded.

**Evidence tiers:**
- *Phone* = the 5 reviewed sessions plus 022535Z. Development-exposed, diagnostic only, never
  used to select anything.
- *Held-out* = held-out ASL signers (stitched DEV) and suite v04's two IPN subjects.
- *CAL* = calibration streams; P1 is the calibration hands-visible person.

**Android state.** The Arm A e10 debug package is unchanged on `claude/wonderful-greider-840275`
(uncommitted): host and device parity pass (Δp ≤ 1.31e-6, 0/669 state mismatches). Nothing in
this milestone justifies a new shadow candidate, so nothing was integrated.

## Answers

1. **Why Arm I loses signs Arm A detects (established).** Mostly not acquisition.
   - It detects the signs: on held-out signers its peak P(ACTIVE) on lost signs is the same as
     Arm A's (median 0.9999), and its decoder-free sign recall is 0.88 vs 0.85.
   - The losses happen in the lifecycle. After a sign, Arm I often outputs PRE instead of POST
     (18% of ACTIVE runs on held-out signers vs 2% for Arm A; 10/31 vs 1/27 on the phone).
   - The production decoder treats ACTIVE → sustained PRE as an aborted activation. Its
     133 ms PRE-gap reset is shorter than one phone interval, so the candidate is discarded at
     the next observation.
   - Held-out PRE-gap discards: 87 for Arm I vs 10 for Arm A. That is most of its 55 lost
     `NO_EVENT` signs.
   - Smaller contributions: more signs swallowed during the 400 ms re-arm (182 vs 136), and 3
     phone signs never acquired.
2. **What reduced its unwanted events (established).** Two things, in roughly comparable measure.
   - **Real S2 discrimination.** Decoder-free AUC of sign vs non-sign peaks: phone 0.885 vs
     0.836; held-out ASL signs vs IPN movement 0.901 vs 0.783. Sign recall is the same, and
     non-sign firing at 0.5 falls to 0.19 vs 0.30 (phone) and 0.29 vs 0.61 (held-out).
   - **The same lifecycle discard that costs it signs.** Its non-sign activations also end in
     PRE. Neutralising the discard brings phone confirmed non-sign events back from 1 to 6–7,
     and IPN events from 0.23 to 1.13 per minute.
3. **What causes the trade-off (established, with one interpretation).**
   - **Established: training composition acting through PRE/POST semantics.**
     - IPN negatives labelled PRE teach "hands visible and moving, not signing → PRE". The
       post-sign recovery motion fits that description.
     - Arm J (IPN without body dropout) shows the same PRE exits (phone 11/36), so body dropout
       is not the cause. It adds a smaller share on its own (Arm B: 49 held-out PRE exits).
     - Arm J is even more suppressive than Arm I (gesture canary ~0, CAL acquisition below the
       floor). Body dropout was partly protecting Arm I from the "no body → IPN → non-sign"
       shortcut.
   - **Interpretation.** Beyond the PRE/POST coupling, every S2 we can train from current data
     sits close to one shared curve of held-out sign words against hands-visible false events.
     The remaining limit looks like discrimination capacity under phone conditions with this
     data, not the decoder.
4. **Intervention selected.** Two minimal, isolated changes that target the mechanism directly:
   - **Lifecycle (no training): research decoder variant `PRE_EXIT_POST`.** A valid ACTIVE run
     (≥ 133 ms) that exits into PRE goes through the same 266.6 ms end-of-sign confirmation as a
     POST exit. Shorter blips keep the production behaviour.
   - **Training: Arm K.** Identical to Arm I, but IPN negative rows are scored "not ACTIVE"
     (−log(p_PRE + p_POST)) instead of being forced to PRE. One run, same recipe, seed and
     selection rule.
5. **Implemented and tested.**
   - Decoder: `PRE_EXIT_POST` and `CB70_PRE_EXIT_POST` in `event_separation.py`, with 3 unit
     tests; production equivalence on POST exits is tested.
   - Trainer: `NON_ACTIVE` target and loss in `s2_r3_train.py`, with 2 unit tests; it is
     identical to standard cross-entropy when unused.
   - Configs: `s2_r3_train_06.json` (Arm J) and `_07.json` (Arm K).
   - Probes: `docs/audit/probes/s2_tradeoff/`, covering sign divergence, lifecycle mechanism,
     decoder-free separability and the S2 × decoder matrix.
6. **Did any candidate improve correct recognition while reducing false events?** Not
   convincingly; none is adopted. See the table below.
   - Arm I + CB + PRE_EXIT meets 3 of the 4 pre-fixed criteria. It narrowly fails natural words
     (216 < 226) and IPN events (1.13 > 1.0).
   - Against Arm A thresholded to a similar operating point (A @ 0.9), it has more continuous
     words (148 vs 140), fewer natural words (216 vs 223), far fewer IPN events (1.13 vs 3.84 per
     minute) and more CAL P1 events (61 vs 41).
   - The IPN advantage carries a source caveat (Arm I trained on other IPN people). So it is not
     a demonstrated move off the curve.
   - Arm K halves the PRE exits (68 vs 132) and recovers natural words (224–235), but it gives
     the IPN suppression back (3.6–4.7 per minute). It is another point on Arm A's curve.
7. **Confirm-boundary.** Preserved: +27 held-out continuous words for Arm A (125 → 152), and +25
   (109 → 134) or +29 (119 → 148) for Arm I, without and with PRE_EXIT. It was not measured
   separately for Arm K (no production-decoder run). `PRE_EXIT_POST` composes with it, and is neutral for
   Arm A (153 vs 152) because Arm A rarely exits to PRE.
8. **Unresolved and next.** See §3.

## Complete system (frozen WORD; same inputs)

Source: `docs/audit/probes/s2_tradeoff/decoder_matrix.json`. CB = confirm-boundary 0.70.

| System | Held-out continuous / natural correct (of 812) | Duplicates (DEV / CAL) | IPN held-out events/min | CAL P1 non-sign | Phone correct / non-sign / unreviewed | 022535Z expected / movement |
|---|---:|---:|---:|---:|---:|---:|
| Production S2-R2 | 78 / 132 | 0 / 0 | 0.00 | 7 | 12 / 6 / 13 | 2 / 1 |
| **Arm A e10 + CB** (reference) | **152 / 238** | 1 / 7 | 7.68 | 80 | **19** / 10 / 12 | 5 / 2 |
| Arm A e10 + CB + PRE_EXIT | 153 / 238 | 1 / 7 | 7.68 | 81 | 19 / 10 / 22 | 5 / 2 |
| Arm A e10 @ 0.9 + CB | 140 / 223 | 1 / 5 | 3.84 | 41 | 16 / 8 / 8 | 4 / 2 |
| Arm I e28 + CB | 134 / 192 | 0 / 0 | **0.23** | 40 | 12 / **1** / 2 | 2 / 0 |
| Arm I e28 + CB + PRE_EXIT | 148 / 216 | 0 / 0 | 1.13 | 61 | 14 / 7 / 5 | 3 / 1 |
| Arm K e23 + CB | 135 / 224 | 0 / 0 | 3.61 | 63 | 14 / 5 / 6 | 4 / 1 |
| Arm K e23 + CB + PRE_EXIT | 139 / 235 | 0 / 0 | 4.74 | 139 | 15 / 6 / 8 | 5 / 1 |

**Pre-fixed criteria** for "better than Arm A + CB" (set before any PRE_EXIT, Arm J or Arm K
result):
- held-out continuous ≥ 145 and natural ≥ 226;
- IPN ≤ 1.0 events/min;
- CAL P1 < 80;
- duplicates no worse.

No row meets all of them.

**Selection.**
- Arm J and Arm K, like Arm I, have no epoch eligible under the pre-registered rule (CAL
  acquisition floor and gesture canary).
- Their rows use the CAL-only diagnostic epoch (`docs/audit/probes/ipn_hand/selection_ARM_{J,K}.json`).
- No phone or held-out data was used to pick any epoch.

## 1. How the mechanism was isolated

**Sign divergence** (`sign_divergence.{py,json}`). First failing stage for every genuine sign,
per model and decoder:
- Phone, signs Arm A gets right and Arm I misses (7): 3 not acquired, 3 `NO_EVENT`, 1 wrong word.
- Held-out continuous (69): 55 `NO_EVENT`, 7 not acquired, 4 merged, 3 wrong word.
- Arm I's peak P(ACTIVE) on the held-out lost signs equals Arm A's.

**Lifecycle attribution** (`lifecycle_mechanism{,_J,_K}.json`). Decoder trace for each acquired
sign with no event, plus the exit state after each ACTIVE run.

| Model | Held-out PRE exits | Held-out PRE-gap discards | Held-out swallowed in re-arm | Phone PRE exits | Phone PRE-gap discards |
|---|---:|---:|---:|---:|---:|
| Arm A e10 | 15 / 727 | 10 | 136 | 1 / 27 | 1 |
| Arm B e9 (body dropout) | 49 / 755 | 31 | 169 | 6 / 36 | 5 |
| Arm I e28 (+ IPN as PRE) | 132 / 740 | 87 | 182 | 10 / 31 | 5 |
| Arm J e2 (IPN as PRE, no dropout) | 45 / 773 | 36 | 196 | 11 / 36 | 8 |
| Arm K e23 (IPN as NON_ACTIVE) | 68 / 751 | 36 | 197 | 6 / 27 | 2 |

**Decoder-free separability** (`unit_separability.{py,json}`). AUC of peak P(ACTIVE) per genuine
sign vs per 9-observation non-sign chunk:

| Model | Phone | Held-out (ASL signs vs IPN NOG) | CAL (signs vs P1) |
|---|---:|---:|---:|
| S2-R2 | 0.789 | 0.962 (recall 0.73) | 0.940 |
| Arm A e10 | 0.836 | 0.783 | 0.986 |
| Arm B e9 | 0.807 | 0.820 | 0.982 |
| Arm I e28 | **0.885** | **0.901** | 0.984 |

## 2. Established vs hypothesis

**Established** (traced on the same inputs):
- the PRE-exit discard mechanism;
- its share of Arm I's losses and of its false-event reduction;
- that IPN negatives labelled PRE cause it without body dropout;
- that the NON_ACTIVE target halves it;
- that `PRE_EXIT_POST` is neutral for Arm A.

**Hypothesis:**
- that the remaining shared trade-off curve reflects S2's discrimination capacity under phone
  framing with the available data;
- that hands-visible negatives from the phone's own capture conditions (with positives from the
  same people) are needed to move off it.

The Arm P result (phone negatives from the same people made S2 quieter) argues that this
requires many people, not more sessions.

## 3. Unresolved, and the next action

**Unresolved:**
- No S2 candidate beats Arm A + CB on all pre-fixed criteria.
- The phone evidence (development-exposed) agrees but cannot decide.
- The re-arm wait swallows 136–197 held-out continuous signs for every model. That is a
  lifecycle limit independent of this trade-off, and the largest single loss in continuous
  signing.
- TABLE remains a perception gap (no accepted hands).
- Suite v04's IPN thresholds were set after earlier diagnostics, and its two subjects are now
  development-evaluation subjects.

**Next, in order of value:**
1. **Keep `PRE_EXIT_POST` as the lifecycle companion of confirm-boundary for any non-Arm-A S2.**
   It is required to evaluate such models fairly, and neutral for Arm A.
2. **Investigate the re-arm swallowing (offline, decoder-only).** It costs more continuous signs
   than anything studied here. The earlier `REENTRY` variant addressed part of it; a fresh look
   with the event ledger and the CAL rule is a small, decoder-only step.
3. **No further IPN retrain** until phone-framed data from several people exists. With the
   Android Arm A debug package ready, the capture session remains the step that can tell whether
   any of these curves holds on a live phone.

No additional IPN download is justified by these results.
