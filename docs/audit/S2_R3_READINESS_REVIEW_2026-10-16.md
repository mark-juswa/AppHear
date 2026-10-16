# S2-R3 readiness review: evaluation suite, history hypothesis, source data

Date: 2026-10-16. Branch `claude/s2-r3-eval-suite`, continuing from `f320781d`.

Scope: offline, read-only analysis. It covers:
- suite v02, a revised frozen gate that supersedes v01 (both remain reproducible);
- the build-step-2 source-data audit.

No model was trained, and no runtime, asset, feature contract or protected data was changed.

Labels: **CONFIRMED** (measured here), **LIKELY**, **HYPOTHESIS**, **REJECTED**, **UNKNOWN**.

## 1. Answers first

| Question | Answer |
|---|---|
| Is the history-dependency hypothesis supported? | **Yes, in refined form.** S2 does not depend on history *length*: 60 observations of real rest leave detection at 100%. It depends on whether the history has driven it into **POST**, which it never learned to leave. Hands held at the sign-end position collapse detection of the next sign from 96% to 0% (held-out signers, CONFIRMED). Close-framed idle scenes also suppress it, while ordinary movement does not. |
| Is the evaluation suite ready to judge a new model? | **Yes, as suite v02**, with the caveats in §3.3. v01 had four flaws; v02 fixes them (§3.2), reproduces every v01 measurement exactly, and is frozen before any S2-R3 model exists. |
| Can the available data support S2-R3 training? | **Partially.** All positive sources and their raw data are present and byte-reproducible, and DEV is cleanly separated. Two gaps decide the strategy: there is **no real "hold after a sign" data**, and **training negatives come from only 2 participants**. Stitching existing clips can teach POST→ACTIVE and POST→PRE exits, but not real holds. |
| Is retraining justified? | **Yes.** Recommended: a real-data stitched R3a, real hold/continuous data collection started in parallel, and N0 negatives added under a participant split (§5). |

## 2. The history hypothesis — what is and is not established

### 2.1 Held-out decomposition (CONFIRMED)

This uses the 69 segmentation-DEV views (23 clips, 7 signers never used in training) as targets.
Histories are stitched at the raw level and the 378 features are recomputed over the joined
sequence. The model is the frozen S2-R2; Phase-7 behaves the same. Probe and output:
`probes/s2_history_v2/decompose_history.py`, `decompose.json`.

| Factor isolated | History before the held-out sign | Detected | Recall |
|---|---|---:|---:|
| Baseline | none (training condition) | 0.986 | 0.869 |
| **Length / padding** | 8 / 16 / 32 / 60 perfectly still copies of the same scene | 0.971 / 0.913 / 0.826 / 0.841 | 0.87 / 0.80 / 0.74 / 0.74 |
| Length with real content | 30 / 60 observations of real phone rest | **1.000 / 1.000** | 0.90 |
| **Join artifact** | same POST history, feature-level vs raw-level join | 0.145 vs 0.145 | identical |
| Ordinary movement | 30 obs human-confirmed "Non sign movement" (untouched signer) | 1.000 | 0.914 |
| Idle scene | 30 obs human-confirmed "No sign" (face fills frame, no hands) | 0.797 | 0.431 |
| **Previous sign**, then g still obs | g = 0 / 10 / 20 / 60 | 0.773 / 0.803 / 0.818 / 0.818 | 0.53 / 0.70 / 0.74 / 0.74 |
| **Hold at sign end**, g obs, then next sign | g = 0 / 3 / 6 / 12 / 24 | **0.955 / 0.879 / 0.576 / 0.045 / 0.000** | 0.75 / 0.60 / 0.36 / 0.01 / 0.00 |

**Interpretation:**
- **Length/padding:** a small effect that saturates around 32 observations and appears only for
  unnaturally static histories. **REJECTED** as the cause of missed signs.
- **Join method:** irrelevant. The suite is not measuring a stitching artifact.
- **Ordinary movement:** does not suppress the next sign, but it does raise false ACTIVE (§3.2).
- **Sign context:** a previous sign costs about 20 points, and most of that recovers within 10–20
  still observations, well inside the 61-observation field. **Content, not field length.**
- **Holds:** dose-dependent collapse. This is the hands-up continuous-signing symptom, now
  reproduced on held-out signers.

> **Correction.** In the interim message I described the "No sign" interval as "non-sign motion
> halves recall". It was the session's *No sign* interval (close face, no hands). The genuine
> *Non sign movement* interval does not suppress detection. The table above is correct.

### 2.2 Combined evidence and remaining uncertainty

**CONFIRMED:**
- Zero POST→ACTIVE and zero POST→PRE label transitions in all 515 S2 training sequences.
- In continuous phone sessions, S2 stays in POST a median 6.1 s after each event, while READY
  shows at 0.5 s.
- Held-out suppression follows POST-inducing content (holds, a previous sign, close idle scenes),
  not history length.

**LIKELY:** training on sequences that contain real POST exits and POST→ACTIVE transitions will
restore acquisition after holds.

**UNKNOWN (only training can answer):**
- whether that can be done *without* raising false activations, given only 2 negative
  participants;
- whether real holds behave like the diagnostic holds. Those are a genuine observation repeated,
  so they are perfectly static. Real holds have jitter, which A_STILL suggests may suppress less.

## 3. Evaluation suite review

### 3.1 What v01 got right (kept)

- Exact reproduction:
  - raw→378 recomputation (error 0);
  - Android probability parity (≤1.1e-6);
  - recorded event replay in all 4 sessions;
  - rolling-prefix equivalence (≤5e-7).
- Held-out DEV targets.
- Isolated-containment non-regression.
- False activations gated as non-inferiority against the frozen reference.

### 3.2 Problems found and fixed in v02

`model/config/recognition_upgrade/s2_r3_context_suite_02.json`, frozen record
`evidence/s2_r3_context_suite_20261016/suite_freeze_02.json`.

| v01 problem | Evidence | v02 fix |
|---|---|---|
| POST-15 gate was one 15-observation snippet from a likely-FIT signer, **selected because the reference sits in POST** (circular, single source) | history_sources POST_PHONE | Diagnostic only. Gated instead by **HOLD_06 ≥ 0.85** and **HOLD_12 ≥ 0.75**, built from each held-out signer's own previous sign (reference 0.576 / 0.045) |
| No condition for the dominant failure (hands held after a sign) | §2.1 | HOLD_00/03/06/12/24 at raw level; hold rows are not scored as false activations because the label is ambiguous |
| False activations under a non-sign history were not measured | — | NONSIGN_MOVEMENT_30 (untouched distinct signer): recall ≥ 0.70 (ref 0.914, a safety line), and **history false ACTIVE ≤ reference 0.133** |
| "Signs-with-event" credited one **merged** episode to two signs | code review | One-to-one `match_signs`; gates use `signs_with_distinct_event`, plus **T2_MERGED_EVENTS ≤ 0** |
| Paused isolated and continuous sessions pooled; signer roles undocumented | session identities | Separate **T2_CONTINUOUS_SIGNS_WITH_DISTINCT_EVENT ≥ 7/11** (ref 2/11); signer role recorded per session |

v02 reproduces every v01 measurement identically (test `test_suite_02_reproduces_every_suite_01_measurement`).

**Reference S2-R2 against the v02 gate:**
- **Passes all isolated and false-activation lines.** These are the guard rails S2-R3 must keep.
- **Fails exactly the continuous lines:**

  | Line | S2-R2 | Required |
  |---|---:|---:|
  | PREV_SIGN | 0.773 | ≥ 0.90 |
  | DIRECT6 | 0.667 | ≥ 0.85 |
  | HOLD06 | 0.576 | ≥ 0.85 |
  | HOLD12 | 0.045 | ≥ 0.75 |
  | Distinct-event signs | 11/23 | ≥ 18/23 |
  | Continuous distinct-event signs | 2/11 | ≥ 7/11 |
  | POST dwell | 6.1 s | ≤ 1.5 s |

Tests: 14 pass, including from-source reproduction of both suites (73 s, with
`APPHEAR_EVIDENCE_ROOT`).

### 3.3 Caveats that remain (not fixable with existing data)

1. **Tier 2 is not signer-held-out for continuous signing.**
   - The September 27 and October 15 sessions are by the Xiaomi design/supervisor signer, LIKELY
     the same person whose September 21 phone positives are FIT in S2-R2. Identity linkage is not
     authoritative.
   - Their 11 continuous signs are in-domain evidence.
   - Distinct-signer evidence comes only from the two paused September 23 sessions.
   - **Tier 3 remains mandatory** before any promotion claim.
2. **Hold conditions use duplicated observations.** If S2-R3 were trained on synthetic holds of the
   same kind, the HOLD gates would no longer be independent evidence (§5.2).
3. **Held-out negatives are thin:** 676 Tier-2 non-sign observations, 340 of them continuous, from
   at most 3 signers. Adding held-out N0 participants would strengthen this (§5.3).
4. **The current decoder is part of what Tier 2 measures.** Even a perfect S2 merges or drops a
   sign that starts within ~0.7 s of the previous one, because ACTIVE cancels pending POST and
   ACTIVE during WAIT is discarded. `T2_MERGED_EVENTS` now makes this visible. A pass on Tier 1
   with a Tier-2 failure driven by merges would point to the planned re-arm/decoder gate, not to
   S2.

## 4. Source-data readiness (build step 2)

Probe: `probes/s2_history_v2/source_readiness.py`; report: `source_readiness.json`.

| Source (planned R3a role) | Count | Raw-v1 | Labels | Verdict |
|---|---|---|---|---|
| Phase-7 FIT (stitching positives) | 71 clips × 3 views, 27 signers, 995 ACTIVE labels | complete-source raw on disk, **213/213 hash-verified** | human START/END, 71/71 | **Ready** |
| Phase-7 CAL (selection) | 18 clips, 14 signers, 256 ACTIVE | 54/54 verified | 18/18 human | Ready, but **13/14 CAL signers also appear in FIT** |
| Segmentation DEV (gate only) | 23 clips, 7 signers | 69/69 verified | 23/23 human | Ready; **0 signer overlap** with every training source |
| Enrichment (positives) | 16 clips, 8 signers | features only. Re-extraction from the original MP4 is **byte-exact** (max error 0, labels equal) | human | 10/16 ready. **6 ASL Citizen clips need drive `G:` mounted** |
| P1 negatives | 45 rows (37 FIT), 3,119 obs, **2 participants (P01/P02)** | features only. Re-extraction **byte-exact**; 45/45 videos verified | human-reviewed intervals | Ready, but **narrow** |
| Exact phone positives | 4 FIT + 2 dev attempts, 669 obs | Android raw arrays; raw→378 exact | exact-tensor human review | Ready (design signer only) |
| **N0 negatives (unused)** | **57 clips, 876 s, 6 participants (P01–P06), 5 phones, 5 environments** | videos present; not yet extracted | 1-FPS hand-presence gold review only | **Available, needs extraction + non-sign confirmation** |
| Real holds / continuous phrases | **none** | — | — | **Missing** |

**Separation (CONFIRMED):**
- DEV is disjoint from FIT, CAL, enrichment, P1 and phone sources.
- Signers overlap within FIT/CAL/enrichment.
- P1 internal-dev shares P01/P02 with P1 FIT.
- Reserved and never opened: protected TEST, E6 `0F747C-S001`, and the future independent phone
  signer.

**Reproducibility (CONFIRMED):** every planned source either has hash-verified raw on disk or
re-extracts byte-exactly from a hash-verified video with the pinned Candidate01 assets.

## 5. Recommended training strategy

### 5.1 What to change before step 3 (decisions for you)

1. **Start the real-hold / continuous TRAIN capture now (R3b), instead of waiting for an R3a
   failure.**
   - The dominant failure has no real training examples, and synthetic holds would contaminate
     the HOLD gate.
   - Design signer, phone, TRAIN role.
   - Contents:
     - sign→sign with hands up;
     - sign→hold (1–3 s)→sign;
     - repeated signs;
     - rest/non-sign scenes, including close framing.
   - Labelled with the existing blinded boundary tool.
   - Hold rows are labelled **POST**, and the next onset ACTIVE. That matches the confirmed
     bounded-POST semantics.
2. **Use N0 under a participant split.** P03/P04 → training negatives; P05/P06 → a new held-out
   false-activation set (suite v03, frozen before training). This lifts negative diversity from 2
   to 4 training participants, and gives held-out false-activation evidence on unseen people and
   phones.
3. **Use a signer-grouped FIT/CAL split** for S2-R3 checkpoint selection, built from the 89 TRAIN
   clips + enrichment, so selection is not on FIT signers. DEV is untouched.
4. **Mount `G:`** to include the 6 remaining enrichment clips, or exclude them explicitly.

### 5.2 Training recipe (R3a, then R3a+R3b)

- **Real observations only. No duplicated or synthetic holds in training**, which keeps the HOLD
  gates independent.
- **Stitch at the raw level** and recompute features. Joins are labelled ignore (first 2
  observations after each join).
- **Grammar mix** (fixed in config, seeded):
  - full isolated clips (keeps the isolated guard rails);
  - direct sign→sign, cutting the previous clip at its last ACTIVE (+0–6 of its own POST);
  - sign→POST tail→PRE rest (teaches POST→PRE);
  - sign→real rest/negative→sign;
  - long rest/negative streams (30–120 s) containing N0/P1 negatives, so ACTIVE and non-ACTIVE
    both appear at every position ≥ 61.
- **Arms:** A (v1 contract) and B (masked phantom proposals, v2 contract). Same data and seed,
  one run each.
- **Architecture:** identical TCN (RF 61, 123,779 parameters), from scratch, S2-R2 hyperparameters.
- **Selection:** on signer-grouped CAL streams only, lexicographic: (1) CAL non-sign ACTIVE rate ≤
  reference; (2) CAL second-sign acquisition; (3) CAL isolated containment.

### 5.3 Validation criteria (frozen)

- **Gate:** suite v02 as committed. It moves to v03 only if you approve the N0 held-out split; v03
  must also be frozen before training.
- **Must pass** all isolated and false-activation lines (S2-R2 passes them today), and all
  continuous lines (S2-R2 fails them today).
- **Tie-break:** the existing arm rule, with ties going to Arm A.
- **Then:**
  1. Android packaging and parity.
  2. Re-arm/READY and decoder review (§3.3, caveat 4).
  3. **Tier 3:** untouched qualified signer, natural 2–5-sign phrases, no capture pauses, hidden
     predictions. Reported as distinct-event sign rate, false words per minute on E6 and
     in-session non-sign, and time-to-next-acquisition.

**Success criterion stated plainly:** more genuine consecutive signs detected as separate events,
with non-sign activations no higher than today. A segmenter that only scores better on Tier 1 does
not meet it.

## Appendix — reproduce

From the repository root, with `F:/ASL DATASET/5. Apphear3/.venv/Scripts/python.exe`:

```
python eval/runtime_diagnostics/s2_r3_context_suite.py freeze --suite 02 --evidence-root "F:/ASL DATASET/5. Apphear3"   # refuses to overwrite
APPHEAR_EVIDENCE_ROOT="F:/ASL DATASET/5. Apphear3" python -m pytest tests/test_s2_r3_context_suite.py
python docs/audit/probes/s2_history_v2/decompose_history.py "F:/ASL DATASET/5. Apphear3" decompose.json
python docs/audit/probes/s2_history_v2/source_readiness.py "F:/ASL DATASET/5. Apphear3" source_readiness.json
```
