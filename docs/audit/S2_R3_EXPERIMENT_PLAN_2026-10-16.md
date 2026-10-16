# S2-R3 — continuous-context segmenter retraining: implementation plan

Status: **PLAN — confirmed decisions, no code written.** Date 2026-10-16.

Evidence base: [S2_HISTORY_DEPENDENCE_VERIFICATION_2026-10-16.md](S2_HISTORY_DEPENDENCE_VERIFICATION_2026-10-16.md).
Implementation belongs on a new branch cut from `codex/recognition-v3-stage2@4503b55`. When work
starts, `context/progress-tracker.md` on that branch gets this plan's status and its open
decisions. The frozen S2-R2 package stays the runtime default throughout.

## Overview

| | |
|---|---|
| **What** | Retrain the class-agnostic PRE/ACTIVE/POST segmenter (S2) so that, in continuous use, it leaves POST and can re-enter ACTIVE without the hands-down wait. It must not become more sensitive to non-sign movement. |
| **Stages touched** | S5 gating / segmentation only (S2 weights and normalization). Arm B also changes the S2 feature contract (offline F + Android S4 builder). |
| **Untouched** | Candidate01 perception, raw-v1, CONFIG_01 decoder and re-arm, materializer, Recognition V2 / 236-class WORD model, SentenceBuilder, FINGERSPELL, Context Assist |
| **Why** | Frozen S2 never saw a POST→ACTIVE or POST→PRE transition: all 515 training sequences end in POST. In continuous sessions it stays in POST a median 6.1 s after each event, while READY appears at 0.5 s (13/14 events). Runtime history caps and resets trade misses for false activations and are rejected. |

## Terminology (aligned)

- **Acquisition:** at least one S2 ACTIVE observation inside a human-labelled sign. A per-sign S2
  metric; diagnostic.
- **Sign-with-event:** a decoder event whose ACTIVE span overlaps the labelled sign. The stream
  metric that is closest to what the user experiences.
- **False activation:** S2 ACTIVE observations, or decoder events fully contained, inside
  human-confirmed non-sign intervals.
- **POST (S2-R3 meaning):** *bounded* recovery after a sign. It may be followed by PRE or directly
  by ACTIVE. It is never terminal.
- **POST dwell:** time from event commit until S2's argmax first leaves POST.
- **Development-exposed:** data that has not trained a model but has been analysed. Segmentation
  DEV and the four labelled phone sessions are development-exposed. Tier 3 is untouched.

## Decisions (confirmed)

| # | Decision | Choice |
|---|---|---|
| D1 | Evaluation tiers | **Three tiers.** Tier 1 is the DEV context suite (gate). Tier 2 is the four phone sessions (gate; development-exposed). Tier 3 is a new qualified-signer continuous capture plus the reserved E6 negative signer `0F747C-S001`, opened once at the end. **Checkpoint selection uses CAL streams built from FIT-signer sources only.** |
| D2 | Label semantics | **Keep 3 states; POST is bounded.** In stitched streams, POST covers each source clip's own human-labelled recovery tail, then the next segment's own labels apply (PRE for rest or negatives, ACTIVE for a direct next sign). The existing 100 ms ignore band is kept, and joins are ignore. The output contract, Android runner, decoder and export are unchanged. |
| D3 | Training data | **Staged.** R3a stitches real raw-v1 observations from existing governed FIT sources only. R3b, a design-signer labelled continuous TRAIN capture with sign→sign, holds, repeats and non-sign, is triggered only if R3a passes Tier 1 but fails the hold or hands-up items of Tier 2. The R3b signer is never the Tier 3 signer. |
| D4 | Input contract | **Two predeclared arms, one run each.** Arm A uses unchanged `segmentation_features.v1`. Arm B uses `segmentation_features.v2`: same 378 layout and order, but refiner-rejected slots have proposal support, presence/finite, proposal-present, ROI, ROI deltas/validity and proposal transitions zeroed, recomputed causally. **A tie goes to Arm A.** |
| D5 | Gate | **Absolute targets plus non-inferiority on false activations.** Every line in the gate table must pass. |
| D6 (default) | Architecture | Identical causal TCN: 64-channel projection, 4×2 residual causal convs at dilations 1/2/4/8, RF 61, 123,779 parameters. Training is from scratch with seed 5103, 30 epochs, batch 8, LR 1e-3, and S2-R2 source-family weights. Only data and labels (and the Arm B input) change. |
| D7 (default) | Checkpoint selection | On CAL streams only, lexicographic: (1) CAL non-sign ACTIVE rate ≤ the frozen S2-R2 rate on the same CAL streams; (2) maximize CAL second-sign acquisition; (3) maximize isolated CAL containment. No Tier 1 or Tier 2 data participates. |
| D8 (default) | Flag / rollback | New debug-only package id `S2_R3_CANDIDATE` in the existing `PhoneS2Package` selector. `S2_R2_CANDIDATE` stays the debug and release default, and `PHASE7_CONTROL` stays as rollback. Release cannot select S2-R3 until a separate promotion decision. |

## Open decisions (deferred on purpose)

- **Tier 3 capture protocol:** signer recruitment, phrase list, consent, and labelling reviewer.
  Metric definitions are frozen here; logistics are decided before the capture, not after R3a.
- **R3b design:** only if it is triggered. It needs its own labelling protocol for holds.
- **Re-arm and READY semantics** (PRE_OR_POST → PRE-based readiness) and the decoder's
  ACTIVE→PRE discard. These are revisited only after an S2-R3 arm passes; they are a separate
  gate.
- **Any change to WORD, FINGERSPELL or perception beyond Arm B:** out of scope.

## Contract and parity impact

- **Arm A:** no `schema_version` change. A new weights + normalization package only. Keras→TFLite
  parity is required on the existing 669-row fixture and the four sessions (≤1e-4 probability,
  0 argmax mismatches).
- **Arm B (only if selected):**
  - new `apphear.perception_vnext.segmentation_features.v2`;
  - Python reference in `pipeline/perception_vnext/segmentation/learned_features.py` (versioned
    function, v1 untouched);
  - Kotlin `PhoneSegmentationFeatureBuilder` v2 behind the package selector;
  - a byte-exact skew test on recorded raw-v1 sessions (max abs error 0);
  - `PhoneS2Runner` refuses a v1/v2 package/contract mismatch;
  - `/imprint` updates `context/feature-schema.md`.
- **Not affected:** Recognition V2 and FINGERSPELL. They already exclude refiner-rejected hands
  through `observed` / `valid` gating.

## Metric and evaluation gate (frozen before training)

The baselines are the frozen S2-R2 values reproduced in the verification report. They are
recomputed by the frozen suite as a self-test before any candidate is scored.

| Tier | Metric | Baseline (S2-R2) | Pass |
|---|---|---:|---|
| 1 DEV (69 views, 7 signers) | Acquisition, no history | 0.986 | ≥ 0.95 |
| 1 | ACTIVE recall, no history | 0.869 | ≥ 0.85 |
| 1 | Acquisition after 15 POST-state obs | 0.145 | ≥ 0.80 |
| 1 | Acquisition, direct transition +6 POST | 0.667 | ≥ 0.85 |
| 1 | Acquisition after previous sign (same signer) | 0.773 | ≥ 0.90 |
| 1 | False ACTIVE in clip PRE/POST (no history) | 0.081 | ≤ 0.10 |
| 1 | Isolated containment, CONFIG_01 + materializer (8A-M2 tooling) | 8A-M2 value | ≥ baseline − 0.05 |
| 2 phone (23 signs, 676 non-sign obs) | Signs-with-event | 11/23 | ≥ 18/23 |
| 2 | Non-sign ACTIVE observations | 64/676 | ≤ 64/676 |
| 2 | Events fully inside non-sign | 5 | ≤ 5 |
| 2 | Median POST dwell after commit (Sep 27 + Oct 15) | 6.1 s | ≤ 1.5 s |
| 3 untouched | Signs-with-event on natural 2–5-sign phrases; FWPM on E6 negatives and in-session non-sign; median time from sign end to next acquisition | — | Thresholds are set in the Tier 3 protocol **before** capture. They must at least meet the Tier 2 targets. |

Reporting rules:
- per-signer and per-cadence-view breakdowns;
- p50/p95 for timings;
- all numbers labelled *segmentation diagnostic*. End-to-end WORD accuracy is not claimed by S2-R3.
- A device step happens only after Tiers 1–2 pass offline (offline eval gate, `eval-protocol.md`).

## Build steps (each independently verifiable)

1. **Freeze the evaluation suite.** Promote the verification probes into
   `eval/runtime_diagnostics/s2_r3_context_suite.py` and add a config JSON listing:
   - every Tier 1 condition, with fixed history sources and indices;
   - the Tier 2 sessions and labels, by hash;
   - the gate table.

   *Verify:* the suite reproduces the S2-R2 baselines above exactly, and the config SHA is frozen
   and recorded before step 3.
2. **Raw-source inventory.** Confirm raw-v1 availability and hashes for every R3a FIT source:
   - Phase-7 FIT `raw_full_video`;
   - 16 enrichment clips;
   - FIT exact-phone positives (session `20260921T153138Z` arrays);
   - FIT P1 negatives.

   Where only features exist (likely P1), re-extract raw-v1 from the original MP4 with pinned
   `Candidate01Offline`. This is permitted: no perception change.

   *Verify:* the source manifest has hash and signer role for every row, and no DEV, Tier 2, E6 or
   TEST source appears.
3. **Stitched-stream builder (data only).** Write a seeded generator for FIT streams and,
   separately, CAL streams. Per stream, 60–400 observations:
   - each source is sampled at a Phase-7 cadence view (133/200/267 ms) **before** stitching;
   - timestamps are concatenated continuously;
   - the 378 features (v1 and v2) are recomputed over the stitched raw;
   - the first 2 observations after every join are labelled ignore.

   Segment grammar, with mix ratios fixed in config:
   - rest/negative blocks of 10–80 observations;
   - full isolated clip;
   - direct sign→sign, where the previous clip is cut after k∈[0,6] POST observations and the
     next starts ≤1 observation before its ACTIVE;
   - sign→rest→sign.

   The unstitched FIT rows are kept as well.

   *Verify:* a label-grammar audit shows POST→PRE and POST→ACTIVE transitions present and ACTIVE
   labels at positions ≥61. There are no fabricated, duplicated or interpolated observations,
   and FIT/CAL source disjointness passes.
4. **Trainer.** Write a versioned S2-R3 trainer reusing `build_model` and the S2-R2 packing and
   weighting, plus the D7 selection callback on CAL streams.

   *Verify:* a 2-epoch smoke run on a small stitched subset gives finite, decreasing loss and a
   reload delta of 0. The smoke run does not consume the main run.
5. **Main runs:** Arm A and Arm B, one run each, supervisor-run.

   *Verify:* checkpoint and normalization hashes are frozen, and the training history is saved.
6. **Gate evaluation.** Run the frozen suite on both arms and apply the gate and the tie rule.
   Write a result report.
   - If both fail Tier 2 hold or hands-up items only, the outcome is
     `R3B_TRIGGERED`, and the R3b capture is planned separately.
   - If both fail Tier 1, stop, and route to a new diagnosis.
7. **Android packaging (only after a pass).**
   - Export the TFLite model.
   - Add `S2_R3_CANDIDATE` package assets and contract.
   - Run Keras/TFLite parity and connected-device S2 parity.
   - For Arm B, also run the Kotlin v2 builder skew test and `/imprint`.
   - Run `context/device-smoke.md`.
8. **Tier 3** with the protocol from the open decision. Then a promotion decision, plus the
   separate re-arm/READY gate.

## Risks

- **Stitching artifacts.** The model may learn join cues. Mitigations: joins are ignore-labelled,
  and every segment boundary uses real observations. Tier 2 (real continuous sessions) is a gate
  for exactly this reason.
- **Better acquisition with worse discrimination.** False-activation non-inferiority is a
  hard gate line; caps already showed this failure mode.
- **Phone holds are not representable in R3a.** That is the explicit R3b trigger.
- **Small Tier 2.** 23 signs and 676 non-sign observations from at most 3 signers are
  development-exposed. Tier 3 is mandatory before any promotion.

## Amendment approved 2026-10-16 (readiness review)

See [S2_R3_READINESS_REVIEW_2026-10-16.md](S2_R3_READINESS_REVIEW_2026-10-16.md).

- **Gate:** suite **v02** supersedes v01. It adds held-out HOLD and non-sign-movement
  conditions, one-to-one distinct-event matching with a merged-event line, and a continuous-only
  Tier-2 line. POST_PHONE_15 is now diagnostic. v01 remains reproducible.
- **D3 (approved change):** start the real-hold / continuous R3b TRAIN capture in parallel with
  R3a, instead of waiting for an R3a failure. Training must not use synthetic duplicated holds,
  so the HOLD gates stay independent.
- **New approved decisions:**
  - use N0 negatives under a participant split (P03/P04 train, P05/P06 held-out
    false-activation set, which would require suite v03);
  - use a signer-grouped FIT/CAL split for selection;
  - mount `G:` for the 6 remaining enrichment clips, or exclude them explicitly.
