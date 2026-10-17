# Recognition V3 — External Data Feasibility (IPN Hand) and S2 Reliability (2026-10-17)

Branch `claude/s2-r3-eval-suite`. Nothing is committed or pushed.

**What did not change:**
- Android, Candidate01, the frozen S2-R2 and Gate-2 packages, the decoder, the materializer,
  SentenceBuilder, FINGERSPELL and Context Assist.
- WORD is fixed to the frozen recognizer throughout.
- Protected TEST, E6 and Tier 3 were not opened.

**Evidence status:**
- Phone numbers are development-exposed engineering evidence. They were never used to select a
  model.
- No new independent device test was possible in this milestone.

## Decision

1. **IPN Hand is relevant and admissible, in part.** Its non-gesture segments (NOG) contain the
   same everyday movements behind our phone false events: grooming, drinking, phone use,
   face-touching, fidgeting and hand holds. Candidate01 accepts hands in 56% of NOG rows, and the
   body is available in 23% — the same as the phone. Arm A fires on them at 6.8 events per minute
   of held-out NOG.
2. **The failure is now better explained.**
   - All of S2-R3's hands-visible non-sign supervision came from a single person (P02).
   - The calibration set used to select Arm A contains hands-visible non-sign from one other person
     (P01), whose hands Candidate01 almost never accepts (5% of rows). Selection was therefore blind
     to this failure, which is why calibration looked near-perfect (AUC 0.99) while the phone did
     not (0.84).
   - Body-evidence reliance is a contributing factor. Removing it alone (Arm B) changes nothing.
3. **IPN negatives teach transferable non-sign behaviour, at a cost.** Arm I added NOG from 6 IPN
   subjects. On sources it never saw, it cut:
   - phone confirmed non-sign events: 9 → 0–1;
   - calibration hands-visible non-sign events: 80 → 40;
   - held-out IPN NOG events: 6.8 → 0.23 per minute.

   But it gave back part of Arm A's acquisition gain:
   - held-out ASL continuous correct words: 152 → 134;
   - phone correct words: 14 → 8.

   Its source-bias canary failed (§5), so under the pre-registered rule **no Arm I epoch is
   selected**.
4. **The external-data hypothesis is partly supported.** Diverse hands-visible negatives do reduce
   false activation across sources. They do not yet keep consecutive-sign acquisition, especially
   on the phone. **Not adopted.** Arm A + confirm-boundary remains the research reference.
5. **Confirm-boundary stays intact.** It adds held-out continuous words with every S2 candidate
   (Arm A e10: +27, Arm I e28: +25 over the same S2 with the production decoder). It never adds phone non-sign
   events beyond what S2 already produces.

## 1. Status checked before new work

| Item | State |
|---|---|
| Arm A e10 debug phone package | Done on branch `claude/wonderful-greider-840275` (uncommitted): `ARM_A_E10_CANDIDATE`, host parity max Δp 1.31e-6, device parity 4.77e-7, 0/669 state mismatches, PhoneS2 parity class 4/4 on the Xiaomi. Not repeated |
| Arm P (phone sessions in FIT), whole-event admission | Not repeated. Arm P is the contrast that defines this milestone's hypothesis (§4) |
| Research branch | Still uncommitted. This milestone adds files only, plus additive options in `s2_r3_train.py` and `event_reliability.py`; earlier results reproduce |

## 2. IPN Hand: what it is and what was used

**Published facts** (project page, IPN HandS README, ICPR 2020 paper):
- 200 continuous RGB webcam videos (640×480, 30 fps) of 50 students at their own PCs.
- 13 gesture classes, plus NOG ("natural hand movements", including "natural interaction with
  objects").
- CC BY 4.0.
- **IPN HandS** re-annotates the videos on its own timeline: `ffmpeg -vf fps=30`, 1-based,
  inclusive, contiguous. It must not be mixed with the original `Annot_List.txt`.
- There are no per-video downloads.

**Downloaded with approval** to `artifacts/external/ipn_hand/` (untracked; read as data only):

| File | Size | Notes |
|---|---|---|
| `videos05.tgz` | 933,117,579 B | 40 videos, 10 subjects, recording group 4CM11. The first transfer was truncated and was resumed; gzip and tar verified |
| `IPN_HandS_annotations.zip` | 82 KB | |
| `Annot_List.txt`, `metadata.csv` | 193 KB, 12 KB | Metadata only |

**Timeline check.** Decoded frame counts equal the HandS counts exactly, or within 4 of about
4,000. Labels are therefore mapped by time: HandS frame = round(t·30) + 1. This is pinned by
`tests/test_ipn_hand_feasibility.py`.

**Admissibility rules** (applied before any S2 result was seen):
- Only NOG rows at least 500 ms from any gesture segment, and only NOG runs of at least 2 s, are
  negatives.
- IPN gestures are never positives or negatives. They are used only as a source-bias canary.
- The 10 subjects are split by a frozen hash: 6 FIT, 2 CAL, 2 held-out
  (`model/config/recognition_upgrade/ipn_hand_split_01.json`).

**Visual review of NOG frames** (contact sheets of 28 NOG frames and 24 Arm A NOG events):
- Mostly everyday movement: rubbing eyes, drinking, adjusting glasses, typing on a phone, face in
  hands, hands on head, chin rest, clasped-hand fidgeting.
- A minority are raised fists held in signing space between gestures. That matches our reviewed
  phone "open-hand hold" non-sign behaviour, but it is the main admissibility risk, since static
  handshapes overlap fingerspelling.
- 22 of the 24 Arm A events reviewed were everyday movement.

## 3. Root cause, from existing data (no training)

Source: `docs/audit/probes/s2_discrimination/domain_shift.{py,json}`, `fit_hand_evidence.{py,json}`.

| Population | Accepted hand | Both hands | Body available | Arm A peak ≥ 0.5 |
|---|---:|---:|---:|---:|
| CAL sign rows | 82% | 32% | 69% | — |
| CAL P1 "hands-visible" non-sign (P01) | **4.7%** | 1.0% | 86% | 6.5% of chunks |
| CAL N0 non-sign | 5.3% | 0.2% | 100% | — |
| FIT P1 non-sign (P02, the only FIT hands-visible person) | 65% | — | — | — |
| Phone genuine signs | 71% | 17% | **22%** | — |
| Phone confirmed non-sign | 30% | 13% | **23%** | 30% of chunks |
| IPN NOG (10 subjects) | 56% | 36% | **23%** | 67% of hand-visible chunks |

- **Source cues alone separate CAL signs from CAL P1.** Hand presence, hand scale and body
  availability, with no motion at all, separate them with AUC 0.98 (stream-grouped CV). On CAL,
  "accepted hand present" is nearly the label.
- **The counterfactual on CAL streams:**
  - Removing all body evidence collapses Arm A's CAL separability from 0.986 to 0.62. Its P1
    false-firing rises from 6.5% to 69%.
  - A ×1.5 zoom has no effect.

  S2-R3 leans on body pose when hands are absent, and the phone rarely has a body.
- **Why the calibration AUC of 0.99 looked better than the phone's 0.84:** the calibration
  negatives almost never contain an accepted hand. Selection therefore could not see the failure.

## 4. Experiment design (controlled; pre-registered before any result)

- **Shared recipe.** All arms use Arm A's recipe, seed and identical base FIT and CAL streams
  (verified byte-identical). Additions use their own RNGs.
- **Arm B** (`s2_r3_train_04.json`): Arm A + body-evidence dropout on 50% of whole stitched
  segments. It isolates the body-shift hypothesis.
- **Arm I** (`s2_r3_train_05.json`): Arm B + 300 extra stitched streams. These pair FIT ASL sign
  clips with IPN NOG negative blocks from the 6 FIT subjects (94 intervals, about 11 minutes),
  in domain `STITCHED_IPN` at weight 0.15.
- **How it differs from Arm P:**
  - Arm P's negatives came from the same few people and sessions as the evaluation positives.
  - Arm I's come from 6 new people, and phone data is untouched.
- **Selection** (`docs/audit/probes/ipn_hand/select_and_score.py`, rule frozen before training):
  - eligible: CAL later-sign acquisition ≥ Arm A e10 − 0.03, and IPN-CAL gesture canary
    ≥ 0.7 × Arm A e10's;
  - choose the lowest IPN-CAL NOG events per minute;
  - the same rule is applied to Arm A's own epochs as a selection-only control.

## 5. Results

**IPN, by subject role.** NOG events/min / hand-visible NOG chunk fire / gesture canary:

| Candidate | Held-out subjects | CAL subjects | FIT subjects |
|---|---|---|---|
| Production S2-R2 | 0.00 / 0.03 / 0.08 | 0.00 / 0.06 / 0.09 | 0.29 / 0.08 / 0.17 |
| Arm A e10 | 6.77 / 0.61 / 0.64 | 8.76 / 0.70 / 0.66 | 6.33 / 0.70 / 0.71 |
| Arm A e21 (selection-only control) | 4.51 / 0.73 / 0.64 | 2.53 / 0.87 / 0.59 | 3.49 / 0.76 / 0.71 |
| Arm B e9 (selected) | 4.74 / 0.62 / 0.55 | 2.07 / 0.87 / 0.57 | 3.64 / 0.69 / 0.71 |
| Arm I e28 (diagnostic, canary failed) | **0.23** / 0.29 / 0.15 | 0.00 / 0.27 / 0.10 | 0.29 / 0.20 / 0.28 |

**Reading:**
- **Every Arm A and Arm B epoch fires on everyday movement** (59–98% of chunks). Re-selecting an
  epoch cannot fix it, and body dropout alone does not either.
- **Arm I generalises across IPN people** (held-out ≈ FIT).
- **No Arm I epoch passes the canary** (best 0.29, against a floor of 0.46). Arm I also stopped
  firing on IPN's articulated non-ASL gestures. That is either over-suppression or a legitimate
  "not ASL" judgement, so the canary is ambiguous. The genuine-sign tests below decide.
- **Diagnostic epoch.** The epoch is chosen by the CAL-only half of the rule (canary dropped; no
  phone data): epoch 28. Epoch 29 is shown only as a sensitivity check.

**Complete system** (frozen WORD; CB = confirm-boundary 0.70):

| System | Held-out ASL continuous correct (of 812) | Held-out natural correct | CAL P1 / N0 non-sign events | Phone Tier-2 correct (of 23) | Phone confirmed non-sign | Continuous distinct (of 11) | 023004Z correct / non-sign | 022535Z expected / movement words |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Production S2-R2 | 78 | 132 | 7 / 8 | 8 | 5 | 2 | 4/6 / 1 | 2 / 1 |
| Arm A e10 + CB | 152 | 238 | 80 / 16 | **14** | 9 | **9** | 5/6 / 1 | 5 / 2 |
| Arm A e21 + CB (selection-only) | **159** | **247** | 63 / 2 | 11 | 6 | 7 | 5/6 / 2 | 5 / 3 |
| Arm B e9 + CB | 143 | 240 | 72 / 10 | 9 | 7 | 7 | 4/6 / 2 | 4 / 3 |
| Arm I e28, production decoder | 109 | 190 | 38 / 0 | 8 | **0** | 5 | 4/6 / 0 | 2 / 0 |
| Arm I e28 + CB | 134 | 192 | 40 / 0 | 8 | 1 | 6 | 4/6 / 0 | 2 / 0 |
| Arm I e29 + CB (sensitivity) | — | — | — | 6 | 2 | — | 4/6 / 0 | 1 / 1 |

**Reading:**
- **IPN negatives reduce false activation on sources the model never saw:**
  - phone confirmed non-sign 9 → 0–1, across all six phone sessions;
  - the CAL P1 person: 80 → 40;
  - movement words in 022535Z: 2 → 0.

  This is not pure "IPN = quiet" source bias.
- **Genuine acquisition drops, unevenly by domain.**
  - Held-out ASL webcam signers keep most of Arm A's gain: 134 vs 152 continuous, still +72% over
    production.
  - On the phone, Arm I falls to production's 8/23. Its phone profile is "production without the
    false events", not "Arm A without the false events".
  - The residual gap is phone-specific: framing, body absence, and phone signs with fewer accepted
    hands.
- **The Arm A e21 control** has the best held-out ASL numbers (159/247) and fewer CAL N0 events,
  but it still fires on IPN and phone movement (4.5/min; phone 6). Better selection alone is not
  a reliability fix.

## 6. Answers

1. **Relevant and admissible?** Yes, for NOG under the rules in §2. NOG reproduces our phone
   false-activation behaviours across 10 people. Gestures are not admissible as positives or
   negatives. Raised-fist holds are a known, minor admissibility risk.
2. **Compatible?** Yes. Candidate01 processes IPN unchanged: hands accepted in 56% of NOG rows,
   body available in 23% (phone-like). Frame conventions were verified and tested.
3. **Comparable failure patterns?** Yes. Arm A fires on 61–70% of hand-visible NOG chunks and
   produces 6–9 events per NOG minute, on the same behaviours seen on the phone. S2-R2 does not.
4. **Hypothesis?** Partly supported and refined. The specific gap is single-person hands-visible
   supervision plus a calibration set that cannot see accepted-hand non-sign. IPN negatives from 6
   people transfer to unseen sources, but at this mixing strength they also cost acquisition,
   mostly on the phone. Data quantity alone does not resolve the phone shift.
5. **Training.** Two runs.
   - Arm B (body dropout): no improvement.
   - Arm I: large false-activation reductions, but no epoch passes the pre-registered canary. Its
     acquisition is lower than Arm A (held-out ASL −12% continuous, −19% natural; phone 14 → 8).
     Not adopted.
6. **Confirm-boundary.** Intact and complementary. It adds words with every S2, adds no phone
   false events with Arm I, and keeps duplicates rare (0–11 of about 1,400 CAL events).
7. **Unresolved:**
   - Phone-domain acquisition (framing and body absence, which affect positives as much as
     negatives).
   - TABLE perception: no accepted hands.
   - The canary's ambiguity.
   - Only one IPN recording group (10 subjects) was used.
   - All phone evidence is development-exposed.
   - No new independent device test.
8. **Next most valuable action.**
   - **Make the CAL selection set able to see this failure.** Add an IPN hands-visible NOG tier
     (CAL and held-out subjects) to the frozen S2 suite as suite v04, so no future S2 is selected
     blind to it. This needs no training.
   - **Then one controlled mixing-strength experiment.** Arm I at a lower IPN weight (for example
     0.05), with more IPN subjects (the remaining four archives, about 3.7 GB, would give 50
     people). Select on CAL, IPN-CAL and held-out ASL acquisition, never on the phone.
   - **The phone-acquisition gap needs phone-framed positives,** which no external dataset
     provides. The capture session with the shadow build remains the only way to measure it
     independently. The Arm A device package is ready for it.

## 8. Follow-up: S2 suite v04 adds the IPN hands-visible tier (no training, no download)

`s2_r3_context_suite.py` now registers suite **04** as current.

**Config** (`model/config/recognition_upgrade/s2_r3_context_suite_04.json`): suite 03 unchanged,
plus `tier1c_ipn_hands_visible`:
- the 2 held-out IPN subjects (8 videos), never used for training or selection;
- hash-pinned by `artifacts/external/ipn_hand/raw_v1/manifest.json` (raw, annotation and source
  video hashes, plus the Candidate01 asset hashes) and by the subject split;
- the split file is `-text` in `.gitattributes`, so its pinned hash survives checkout.

**Metrics:** NOG active rate and NOG events per minute through the reference lifecycle (gated);
hand-visible chunk firing and the gesture canary (diagnostics only).

**New gate lines** (absolute product bounds):
- `T1C_IPN_NOG_EVENTS_PER_MIN` ≤ 1.0;
- `T1C_IPN_NOG_ACTIVE_RATE` ≤ 0.10, the same bound as `T1_NONE_FALSE_ACTIVE`.

**Freeze** (`evidence/s2_r3_context_suite_20261016/suite_freeze_04.json`):
- Tiers 1, 1b and 2 are identical to suite 03.
- Production S2-R2 measures 0.00 NOG events/min and a 1.5% NOG active rate (1,329 NOG
  observations, 4.4 min).
- The freeze reproduces from source inputs: the evidence-root test for suite 04 passes.

| Candidate (suite v04, production decoder) | IPN NOG events/min | IPN NOG active rate | Chunk fire | Canary | T1C | Other failed lines |
|---|---:|---:|---:|---:|---|---:|
| Production S2-R2 (reference) | 0.00 | 0.015 | 0.03 | 0.08 | pass | as suite 03 |
| Arm A e10 | 6.77 | 0.185 | 0.61 | 0.64 | **fail** | 7 |
| Arm A e21 | 4.52 | 0.351 | 0.73 | 0.64 | **fail** | 3 |
| Arm B e9 | 4.74 | 0.229 | 0.62 | 0.55 | **fail** | 6 |
| Arm I e28 | 0.23 | 0.096 | 0.29 | 0.15 | pass | 8 (acquisition) |

**What it shows.** The suite now sees the failure that suite 03's CAL-style negatives could not.
It also shows Arm I's opposite failure on the acquisition lines. Any future S2 candidate has to
clear both at once. Results: `docs/audit/probes/ipn_hand/suite_v04_*.json`.

## 7. Files (all uncommitted)

| Kind | Path |
|---|---|
| IPN loader / feasibility | `eval/runtime_diagnostics/ipn_hand_feasibility.py`, `tests/test_ipn_hand_feasibility.py` |
| Trainer options | `eval/runtime_diagnostics/s2_r3_train.py` (`augment.body_dropout`, `augment.ipn_streams`; own RNGs), `model/config/recognition_upgrade/{s2_r3_train_04,s2_r3_train_05,ipn_hand_split_01}.json` |
| Root-cause probes | `docs/audit/probes/s2_discrimination/{domain_shift,fit_hand_evidence}.{py,json}` |
| Suite v04 | `eval/runtime_diagnostics/s2_r3_context_suite.py` (tier 1c), `model/config/recognition_upgrade/s2_r3_context_suite_04.json`, `evidence/s2_r3_context_suite_20261016/suite_freeze_04.json`, `tests/test_s2_r3_context_suite.py` |
| IPN probes | `docs/audit/probes/ipn_hand/`: `feasibility.json`, `suite_v04_*.json`, `select_and_score.py` → `selection_ARM_{A,B,I}.json`, `score_candidates.py` → `ipn_scores.json` |
| System comparison | `docs/audit/probes/event_reliability/system_compare.{py,json}`; `ledger_*` and `stream_ledger_*` for ARM_A_E21, ARM_B_E9, ARM_I_E28 (and E29 phone) |
| External data (untracked) | `artifacts/external/ipn_hand/{download,videos,handS_annotations,raw_v1}` |
| Models (evidence root) | `.../s2_r3_arm_b_01/`, `.../s2_r3_arm_i_01/` |

Reproduce, in order:
`ipn_hand_feasibility.py extract --all-videos` → `analyze`
→ `s2_r3_train.py train --config s2_r3_train_0{4,5}.json`
→ `select_and_score.py --run ARM_{A,B,I}` → `score_candidates.py`
→ `build_ledgers.py` / `stream_ledgers.py --configs ...` → `system_compare.py`.
