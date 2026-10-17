# Recognition V3 — Re-arm Swallowing in Continuous Signing (2026-10-17)

Decoder-only, offline study. Branch `claude/s2-r3-eval-suite`, uncommitted.
- **Fixed throughout:** S2 = Arm A e10; WORD is the frozen recognizer.
- **Unchanged:** Android, the production decoder and every protected component.
- **Phone results** are development-exposed and diagnostic only.

## Finding

After an event is committed, the production decoder ignores ACTIVE until it has seen 400 ms of
stable non-ACTIVE (re-arm). In continuous signing the next sign usually starts sooner.

Under confirm-boundary, signs swallowed this way:
- 219 of 1,980 CAL signs;
- 134 held-out continuous signs.

They start a median of 540 ms after the previous commit, mostly 1–3 observations later. This is
the largest recoverable loss in continuous signing, larger than the merges confirm-boundary fixes.

## What a re-entry rule does, event by event

Re-entry starts a new candidate on ACTIVE during the re-arm wait, once enough non-ACTIVE
observations follow the commit. Re-entry events under `REENTRY_1` + confirm-boundary:

| Population | Re-entry events | Genuine new sign | Non-sign | Duplicate | Other |
|---|---:|---:|---:|---:|---:|
| CAL streams | 248 | **218** | 14 | 5 | 11 |
| Held-out continuous | 95 | **95** | 0 | 0 | 0 |

Of the 14 CAL "non-sign" re-entries, 8 start 0–2 observations after a raw-level splice. That is
where a sign clip is joined to a separately recorded negative clip, and where the training label
contract already leaves the first 2 rows unscored (IGNORE). Only 6 lie inside genuine negative
movement.

**Correction (made 2026-10-17 after seeing this data; applied to every variant).** The CAL rule
now counts a non-sign event only if its whole span lies on PRE-labelled negative rows. The
original count is kept alongside.

Source: `docs/audit/probes/rearm/{rearm_probe,select_rearm_on_cal}.{py,json}`.

## CAL selection (existing rule: split ≤ base + 0.02, non-sign ≤ 1.10 × base, max distinct)

| Variant | Distinct | Split | Non-sign events: original / label-contract |
|---|---:|---:|---:|
| Production decoder | 0.738 | 0.000 | 85 / 71 |
| Confirm-boundary 0.70 | 0.757 | 0.004 | 96 / 82 |
| REENTRY_1 | 0.837 | 0.004 | 100 / 79 |
| **REENTRY_2** | **0.795** | 0.001 | 96 / **76** |
| REENTRY_2 + CB | 0.814 | 0.005 | 107 / 87 |
| REENTRY_1 + CB | 0.857 | 0.008 | 111 / 90 |

- **Original rule:** nothing but the production decoder is eligible.
- **Label-contract rule:** `REENTRY_2` is eligible (+7%) and selected.
- **`REENTRY_2` semantics:** re-enter when ACTIVE follows the commit plus at least one more
  non-ACTIVE observation, which is about 270–530 ms after the sign at phone cadence.
- Confirm-boundary itself (+15%) and the combinations stay ineligible.

## Complete system (held-out and IPN independent; phone diagnostic)

Source: `docs/audit/probes/s2_tradeoff/decoder_matrix.json`.

| Arm A e10 + decoder | Held-out continuous / natural correct (of 812) | Duplicates (DEV / CAL) | Natural fragments | CAL P1 non-sign | IPN events/min | Phone correct / non-sign / unreviewed | 022535Z expected / movement |
|---|---:|---:|---:|---:|---:|---:|---:|
| Production decoder | 125 / 236 | 0 / 0 | 70 | 68 | 6.77 | 15 / 10 / 11 | 4 / 2 |
| **REENTRY_2** | **148 / 255** | 0 / 0 | 77 | 75 | 7.00 | 15 / 12 / 11 | 4 / 2 |
| Confirm-boundary (current candidate) | 152 / 238 | 1 / 7 | 75 | 80 | 7.68 | 19 / 10 / 12 | 5 / 2 |
| REENTRY_2 + CB | 176 / 255 | 1 / 7 | 81 | 87 | 7.90 | 19 / 12 / 12 | 5 / 2 |
| REENTRY_1 + CB | **192 / 264** | 1 / 12 | 81 | 90 | 8.58 | 19 / 12 / 12 | 5 / 3 |

(For scale: production S2-R2 = 78 / 132.)

**Reading:**
- **`REENTRY_2` (the CAL-selected variant).** +23 continuous and +19 natural held-out words,
  with no duplicates.
  - Its costs: +1 IPN event (7.00 vs 6.77 per minute), +7 CAL P1 events, +7 natural fragments,
    and +2 phone non-sign events (diagnostic).
  - It is the first event-lifecycle change to pass the (corrected) CAL rule.
- **Re-entry and confirm-boundary are complementary.** CB splits ACTIVE runs that merge; re-entry
  rescues signs that arrive during the re-arm wait.
  - REENTRY_2 + CB adds +24 continuous words over CB alone, and REENTRY_1 + CB adds +40.
  - Their false-event cost (IPN +3–12%, CAL P1 +9–13%) is mostly further fragmentation of activity Arm A already
    has. The combinations inherit CB's own ineligibility under the rule.
- **What re-entry does not do.** It does not touch the hands-visible false-activation problem:
  Arm A's IPN rate stays around 7 events per minute with every decoder. That is an S2 problem
  (see `RECOGNITION_V3_S2_TRADEOFF_2026-10-17.md`).

## Decision

- **`REENTRY_2` becomes the selected research lifecycle candidate.** It is the variant the
  pre-registered CAL rule selects (with the stated label-contract correction), and the
  independent held-out evidence agrees.
- **REENTRY_2 + CB is the strongest continuous-signing configuration measured** (176 / 255
  held-out). It is kept as a diagnostic candidate, because CB alone is not CAL-eligible.
- **Nothing is promoted.** The production decoder stays the default.
- **Next steps:**
  - An Android shadow of the lifecycle is not justified yet: the S2 false-activation problem
    dominates live false events.
  - The same phone capture session that tests Arm A would also show re-entry's live behaviour
    on genuine consecutive signs.

**Implemented:** `R1_CB70` and `R2_CB70` in `event_separation.VARIANTS`; a re-entry unit test
pinning that the commit observation counts as the first non-ACTIVE observation; and the probes
above.

## Addendum: re-entry with the better-discriminating S2 (Arm I e28)

Arm I e28 discriminates better at the S2 level (`RECOGNITION_V3_S2_TRADEOFF_2026-10-17.md`). It
fell short end to end mainly on natural-signing words, and re-entry is what recovered natural
words for Arm A. So the same CAL rule was run with Arm I as the S2
(`select_rearm_on_cal.py ARM_I_E28` → `cal_rearm_selection_ARM_I_E28.json`).

**CAL rule results with Arm I as the S2:**
- Label-contract count: confirm-boundary, re-entry and their combinations are all eligible, and
  the rule selects **R1_CB70** (distinct 0.582 → 0.712; non-sign 22 → 24).
- Original count: the rule selects CB70.
- Every PRE_EXIT combination is ineligible for Arm I on CAL (non-sign 33–37 vs 22).

| Configuration | Held-out continuous / natural (of 812) | Duplicates (DEV / CAL) | IPN events/min | CAL P1 non-sign | Phone correct / non-sign / unreviewed | 022535Z expected / movement |
|---|---:|---:|---:|---:|---:|---:|
| Arm A e10 + CB (reference) | 152 / 238 | 1 / 7 | 7.68 | 80 | 19 / 10 / 12 | 5 / 2 |
| Arm A e10 + R1 + CB | 192 / 264 | 1 / 12 | 8.58 | 90 | 19 / 12 / 12 | 5 / 3 |
| **Arm I e28 + R1 + CB** (CAL-selected decoder) | **196** / 222 | **0 / 0** | **0.45** | **48** | 12 / **1** / 3 | 2 / 0 |
| Arm I e28 + R2 + CB + PRE_EXIT (diagnostic) | 194 / 237 | 0 / 0 | 1.35 | 72 | 14 / 7 / 6 | 3 / 1 |

**Against the criteria fixed in the trade-off milestone** (held-out continuous ≥ 145 and natural
≥ 226; IPN ≤ 1.0/min; CAL P1 < 80; duplicates not worse):
- **Arm I + R1 + CB passes 4 of 5:**
  - continuous 196, the best measured;
  - IPN 0.45 per minute, inside suite v04's tier-1c limit;
  - CAL P1 48;
  - zero duplicates.

  It misses natural signing by 4 words (222).
- **The diagnostic PRE_EXIT combination** keeps natural words (237) but misses IPN (1.35).

**Status of the evidence:**
- **Established on held-out data:** with the CAL-selected decoder, Arm I gives more continuous
  words than Arm A + CB together with about 94% fewer hands-visible IPN false events. That is
  the first configuration off the previous trade-off curve.
- **Caveats:**
  - Arm I e28 is the diagnostic epoch: it failed the pre-registered gesture canary.
  - The held-out benchmark and IPN subjects have now been used across many configurations, so
    they are increasingly development-exposed.
  - On the phone (development-exposed, n = 29), every Arm I configuration recognises fewer words
    than Arm A + CB (12–14 vs 19), with far fewer false events (1–7 vs 10). The phone-domain
    acquisition gap remains the open question.

**Next step:** a live phone A/B. It needs no Android integration. The capture build records
exact-parity observations, and offline replay of any S2 + decoder on them is exact. One blinded
multi-person session can therefore score Arm A + CB, Arm A + R1 + CB and Arm I + R1 + CB on
identical live data. That is the decisive test the current evidence cannot provide.

## Addendum 2: why Arm I + R1 + CB recognises fewer phone words, sign by sign

Sources: `docs/audit/probes/s2_tradeoff/phone_loss_diagnosis.{py,json}`,
`phone_sign_peaks_by_arm.json`. Phone data is development-exposed and diagnostic only.

Seven reviewed phone signs are correct with Arm A e10 + CB and not with Arm I e28 + R1 + CB.
None go the other way. Peak P(ACTIVE) inside each sign, per arm:

| Sign | Arm A e10 | Arm A e21 | Arm B | Arm I | Arm J | Arm K | Arm I failure | Attribution |
|---|---:|---:|---:|---:|---:|---:|---|---|
| SEP27 A HELLO#1 | 0.99 | 0.16 | 0.85 | 0.32 | 0.97 | 0.55 | not acquired | Borderline sign; Arm A's own e21 also misses it |
| SEP23-ind #2 HELLO | 0.79 | 0.01 | 0.24 | 0.02 | 0.22 | 0.01 | not acquired | Only Arm A e10 catches it: reference epoch luck |
| SEP23-ind #4 HOME | 1.00 | 0.99 | 0.53 | 0.37 | 0.91 | 1.00 | not acquired | Body dropout (Arm B and Arm I low; Arm J without dropout fine) |
| OCT15 B HELLO#1 | 1.00 | 0.92 | 0.68 | 0.98 | 0.74 | 1.00 | no event (ACTIVE → PRE discard) | PRE semantics; PRE_EXIT recovers it |
| SEP23-ind #3 HOME | 1.00 | 1.00 | 0.75 | 0.76 | 0.99 | 0.83 | no event (one ACTIVE obs, then PRE) | PRE semantics; too short for any rule |
| SEP27 B HOME#2 | — | — | — | — | — | — | wrong word (merged window) | ACTIVE/end ambiguity between consecutive signs |
| Shadow B HOME#2 | — | — | — | — | — | — | wrong word (window runs on) | ACTIVE/end ambiguity between consecutive signs |

**What the gap is made of:**
- About 2 of the 7 are variance in the reference itself: Arm A e21 + CB scores 16, not 19.
- 1 comes from body dropout.
- 2 come from Arm I's PRE semantics (`RECOGNITION_V3_S2_TRADEOFF_2026-10-17.md`).
- 2 come from boundary ambiguity.

**One hypothesis tested and rejected.** The idea was that confirm-boundary fails for Arm I
because its POST mass moved to PRE. A variant gating the split on 1 − P(ACTIVE) instead of
P(POST) (`nonactive_peak`, `R1_CBN70`) was CAL-eligible but changed nothing: phone 12 / 1 / 3,
held-out 196 / 222, both identical to R1_CB70. At those two transitions Arm I is genuinely
uncertain between ACTIVE and end-of-sign.

**R1_CBN70 + PRE_EXIT** reaches the highest held-out counts measured (222 / 248), but it
fragments signs (35 CAL duplicates, IPN 1.81 per minute) and is CAL-ineligible.

**Conclusion.**
- Arm I's systematic phone deficit is about 3–5 signs out of 29. Its causes are already
  identified: PRE semantics, body dropout and boundary ambiguity.
- Further decoder rules would be fitted to two or three phone signs, so this line stops here.
- The CAL-selected configuration for Arm I remains R1_CB70.
- The decisive comparison is the live multi-person capture, replayed offline.
