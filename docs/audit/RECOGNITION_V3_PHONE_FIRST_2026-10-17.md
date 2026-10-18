# Recognition V3 — Phone-First Reliability: Where Phone Recognition Actually Fails (2026-10-17)

## Repository state (verified)

- **Research branch.** `claude/s2-r3-eval-suite` tip is `e2444ebb`: local only, no upstream, never
  pushed. The working tree is clean apart from the 21 excluded stream-ledger JSONs and
  `.claude/launch.json`.
- **Arm A phone export.** `claude/wonderful-greider-840275` is still at base `51152519`, with its
  8 export files **uncommitted**: debug package `ARM_A_E10_CANDIDATE`, host parity Δp 1.31e-6,
  device parity 4.77e-7 and 0/669 mismatches, 4/4 PhoneS2 parity tests.
- **Production defaults** (S2-R2, Gate-2 WORD, production decoder) are unchanged.

## Evidence used

- **Phone:** 29 reviewed genuine signs from 4 Tier-2 sessions (development-exposed) and shadow
  023004Z (labels **unblinded**).
- **Same everywhere:** every configuration is scored on the identical recorded observations,
  sign references and definitions. Frozen WORD is displayed, and WORD v2 is reported as shadow.
- **Status:** this is diagnosis, not independent validation. Nothing below was tuned on these
  recordings.

**Tool:** `eval/runtime_diagnostics/phone_replay_compare.py` (new). Results:
`docs/audit/probes/phone_first/{replay_compare_registry.json, phone_failure_matrix.json}`.

## 1–2. Dominant phone failures and the stage responsible

Earliest failing stage per genuine sign:
- **PERCEPTION** — fewer than 4 observations or under 50% accepted hands.
- **CLASSIFIER** — the frozen WORD is wrong even on the human-boundary window (±250 ms through
  the runtime materializer).
- **WINDOW** — wrong on the event window but right on the human-boundary window.

| Stage | Production | Arm A + CB | Arm A + R1 + CB | Arm I + R1 + CB |
|---|---:|---:|---:|---:|
| **Correct** | 12 | **19** | **19** | 12 |
| Perception (TABLE) | 6 | 6 | 6 | 6 |
| S2 not acquired | 8 | 0 | 0 | 4 |
| Lifecycle: swallowed in re-arm | 1 | 0 | 0 | 0 |
| Lifecycle: discarded | 1 | 1 | 1 | 4 |
| Merged | 0 | 0 | 0 | 0 |
| Window (boundary) | 0 | 0 | 0 | 0 |
| Classifier | 1 | 3 | 3 | 3 |
| Confirmed non-sign events | 6 | 10 | 12 | **1** |
| Unreviewed / uncertain events | 13 | 12 | 12 | 3 |
| Duplicate / shared events | 0 | 0 | 1 | 0 |
| Median commit latency after sign end | 667 ms | 634 ms | 634 ms | 668 ms |

**With the best configuration (Arm A + CB), the remaining phone losses are not in S2 or the
decoder.**
- **Perception: 6 of 10.** All six TABLE attempts.
  - DWPose proposes a hand on 100% of their observations, but the hand refiner's presence is
    near zero (median 0.03, against 0.97 for other signs).
  - Rendered frames show why: two flat hands stacked edge-on across the chest, overlapping each
    other against a low-contrast top, with one crop often containing both hands, plus some
    motion blur. The ROI boxes are placed correctly.
  - Lowering the 0.50 threshold cannot fix it. At 0.05 it accepts only 43% of TABLE rows, while
    acceptance on non-sign movement rises from 30% to 39%.
- **Classifier: 3 of 10.** All HOME. The frozen WORD is wrong even on ideal windows.
  - WORD v2 fixes them on ideal windows (23 vs 20 of 29).
  - On Arm A + CB's real windows it ties (19 vs 19): +2 HOME, −2 HELLO→LUNCH1 from the
    next-sign onset.
- **Lifecycle: 1 of 10.** One discarded HELLO.
- **Detection and boundaries are no longer the phone bottleneck for Arm A.** It has 0 signs not
  acquired, 0 swallowed, 0 merged, and 0 windows covering another sign.

## 3. What the existing configurations genuinely provide (phone)

- **Arm A + CB vs production: +7 correct words net** (12 → 19).
  - It acquires all 8 signs production never acquires: 7 become correct and 1 (SEP27 A HOME) is
    misread.
  - It recovers production's swallowed sign, and loses one HELLO that production got right
    (discarded).
  - The cost is +4 confirmed non-sign events (6 → 10). Latency is unchanged (634 vs 667 ms
    median).
- **Re-entry on top of Arm A: no phone gain.** This phone protocol has pauses and holds between
  signs, so no sign is swallowed by the re-arm wait for re-entry to rescue. On this evidence it
  only adds 2 non-sign events and 1 duplicate.

  Its held-out gain (+40 continuous words) comes from tightly consecutive signing that these
  recordings do not contain. On the phone it is **untested, not disproven**.
- **Arm I + R1 + CB: production's word count with almost no false events** (12 correct, 1
  non-sign, 3 unreviewed). It loses Arm A's gains through 4 S2 suppressions and 4 lifecycle
  discards (mechanisms in `RECOGNITION_V3_S2_TRADEOFF` and `RECOGNITION_V3_REARM` addendum 2).
- **Output policy (precision, not a model fix).** The held-out-calibrated confidence gate (0.75)
  on Arm A + CB keeps 16 of 19 words and cuts confirmed non-sign events 10 → 3
  (`probes/event_reliability/gate_policy.json`).

## 4–5. Decisions: selected, implemented, rejected

**Selected.** No new S2 model, decoder rule or WORD training.
- The phone failure matrix shows these stages are not where the remaining recoverable phone
  failures are.
- Changing them now would be tuning to development-exposed recordings.

**Implemented:**
- **`phone_replay_compare.py`.** Paired, sign-by-sign stage attribution for any exact-parity
  capture with human boundaries (`--capture`), or for the reviewed registry (`--registry`).
  - It covers the four reference configurations, or any `LABEL=S2:DECODER` set.
  - It reports non-sign, unreviewed and duplicate events and commit latency.
  - It carries label provenance (BLINDED / UNBLINDED / TIER2_REVIEW_DEVELOPMENT_EXPOSED) into the
    output.
  - Validated: it reproduces the probe's matrix and the earlier ledger counts exactly, and the
    `--capture` path matches the registry entry for 023004Z.
  - 4 unit tests cover stage ordering.
- **`docs/audit/probes/phone_first/phone_failure_matrix.py`.** The diagnostic probe behind the
  tables above.

**Rejected or not pursued, with reason:**
- **Lower hand-presence threshold:** cannot recover TABLE (see §1–2).
- **WORD v2 swap:** neutral on runtime windows.
- **Re-entry for the phone:** no phone opportunity in the current protocol.
- **Further S2 retraining:** no S2 acquisition loss remains for Arm A.

## 6–7. Did phone recognition and unwanted output improve? Any regressions?

**No new candidate was adopted, so nothing changed in phone behaviour this milestone.** The best
existing configuration stands:
- **Arm A + CB:** 19/29 correct with 10 confirmed non-sign events, against production's 12 and
  6. With the 0.75 gate: 16 and 3.
- **No regression measured** in event separation, duplicates (0) or latency (634 ms median).
- **Re-entry:** +1 duplicate and +2 non-sign events on the phone; kept as a research candidate,
  not for the current phone protocol.

## 8. What remains blocked

- **Perception (largest).** Flat, overlapping, edge-on hands such as TABLE are rejected by the
  MediaPipe refiner. This needs an isolated perception research track, for example:
  - refiner input crops for two-hand overlap;
  - or a DWPose hand-keypoint fallback evaluated as a separate observation source with its own
    feature contract.

  Candidate01 stays protected until such a candidate is measured.
- **WORD.** HOME is misread by the frozen recognizer even on ideal windows. v2 fixes it but is
  sensitive to next-sign onset in runtime windows. That limit is measured, but not yet large
  enough to justify a WORD track.
- **Unwanted output.** Arm A's false activations are an S2 discrimination problem (see the
  trade-off report). Today the choices are the precision gate or Arm I's quieter operating
  point; both cost words.
- **Data.** All phone evidence is from few people and development-exposed; one session's labels
  are unblinded.

## 9. Next minimum action

1. **One short capture, no code change.**
   - Use the existing compact protocol (hands-down, hands-up consecutive pair, repeat, hold,
     ordinary movement) and the existing debug build with exact-parity capture on.
   - Use a signer not yet recorded, and a reviewer who has not seen model output, so the
     human-boundary labels are BLINDED.
   - Score with:

     ```bash
     python -m eval.runtime_diagnostics.phone_replay_compare --evidence-root ROOT --capture <session> --out <file>
     ```

     This gives the first independent paired comparison of production, Arm A + CB, Arm A + R1 +
     CB and Arm I + R1 + CB on identical live observations.
2. **Separately, if re-entry's phone value matters:** a debug-only protocol profile with one
   phrase block (3–4 consecutive signs, no pauses). The current profile is pinned in
   `PhoneStage2TransitionProtocol.kt`, so this is a small Android debug change. It needs your
   approval.
3. **Separately, a perception research track on overlapping and flat hands (TABLE)**, using the
   saved phone originals, with Candidate01 left unchanged until a candidate is measured.
