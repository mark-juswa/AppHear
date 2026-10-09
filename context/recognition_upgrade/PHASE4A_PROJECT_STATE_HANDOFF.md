# AppHear Project State Handoff Before Phase 4A

**Decision date:** 2026-09-14  
**Decision authority:** project lead  
**Milestone entering:** `PHASE_4A_BOUNDED_PHONE_RECOGNITION_VALIDATION`

This is the governing project-state transition from paused Phase 3 to Phase 4A. It preserves all
earlier scientific evidence and does not assert that Phase 3 is solved.

## Anti-drift source order

When older plans, reports, or status text disagree about what to do next, use this order:

1. this handoff for the current phase, active checkpoint, closed branches, and next boundary;
2. `context/feature-schema.md` for exact raw-v1 and recognition-v2 feature semantics;
3. `context/progress-tracker.md` for the chronological evidence and completed milestones;
4. immutable milestone artifacts for scientific measurements and hashes;
5. older recognition-upgrade plans only as historical rationale.

Never infer that Phase 3 is solved from entry into Phase 4A. Never substitute the rejected invariant
checkpoint for the ordinary V2 checkpoint. Never follow an older `next action` without first
checking this handoff and the newest progress-tracker entry.

## Canonical phase state

| Phase | State | Governing boundary |
|---|---|---|
| Phase 1 — Candidate 01 perception | **FROZEN / COMPLETE** | Keep Candidate 01; do not create Candidate 02 |
| Phase 2 — recognition representation | **CLOSED / FROZEN** | `apphear.perception_vnext.recognition.v2`, `[96,350] + [96]` mask; no V2.1 or V3 |
| Phase 3 — 236-class recognition | **REOPEN NEXT — GENERALIZATION UNSOLVED** | `PHASE_3_RECOGNIZER_GENERALIZATION_REOPEN`; project lead must choose new signer/information diversity; no same-data microtuning |
| Phase 4A — bounded phone validation | **COMPLETE** | Gate 5: `PHASE_4A_COMPLETE_RETURN_TO_PHASE_3`; Gate 4A-2 superseded until later post-improvement validation |
| Phase 5 — automatic gating and AppHear UI | **NOT STARTED** | No automatic start/end, commit policy, or conversational-UI connection yet |

## Frozen active recognition stack

The strongest governed recognizer remains the **ordinary V2 TCN**, not the rejected invariant
candidate.

Pipeline:

```text
Candidate 01 perception
→ apphear.perception_vnext.recognition.v2 [96,350] + [96] mask
→ ordinary mask-aware causal TCN
→ 236-way isolated-sign prediction
```

Recognizer architecture:

- four temporal blocks;
- 64 channels;
- dilations `1,2,4,8`;
- kernel `3`;
- dropout `0.3`;
- 236 outputs.

Frozen checkpoint:

`artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/tcn_v2_run_01/best.keras`

SHA-256:

`8107accbc621ae5652766fec80d314fe8dc9f94ba0d0548a6aef80ed91729340`

Frozen governed results:

| Population / condition | Top-1 | Top-5 | Macro-F1 | Zero recall |
|---|---:|---:|---:|---:|
| DEV dense | 50.25% | 76.23% | 48.55% | 34 |
| DEV PHONE_01 sparse | 39.95% | 70.96% | 38.15% | 52 |
| TRAIN dense | 86.91% | — | — | — |
| TRAIN PHONE_01 sparse | 82.25% | — | — | — |

These results make the ordinary V2 TCN the active control, not a production-ready recognizer.

## Phase-3 status and preserved evidence

Phase 3 is paused with two unresolved problems:

1. **Primary:** unseen-signer generalization.
2. **Secondary:** phone cadence / observation density.

The following branches remain closed and must not be automatically revisited:

- class→signer→clip balanced sampling;
- class weighting;
- more epochs;
- learning-rate or optimizer sweeps;
- random-seed sweeps;
- V3 or V2.1 representation work;
- another signer/cadence contrastive-loss weighting;
- another metric-learning variant;
- another simple TCN-objective adjustment.

Balanced sampling was harmful. Recognition V2 was successful and is frozen. The explicit
signer/cadence-invariant objective was structurally valid but scientifically unsupported:

- DEV dense Top-1: `50.25% → 46.32%`;
- DEV sparse Top-1: `39.95% → 39.09%`.

Its alignment objectives reduced same-sign/different-signer and same-clip dense/sparse embedding
distances, but compressed different-class separation. Preserve its checkpoint, evaluation,
decision, and report as negative Phase-3 evidence; do not promote or overwrite them.

Phase 3 is paused because repeated small changes over the same current TRAIN population have not
resolved generalization efficiently. A later return should consider a fundamentally stronger
information/recognition strategy rather than resume local tuning loops.

The leading future Phase-3 direction is external/pretrained signing diversity:

```text
external signer-diverse isolated-sign data
→ Candidate 01 or a proven compatible representation
→ generic temporal/sign pretraining
→ AppHear 236-class fine-tuning
```

Sem-Lex is only a candidate source, not an authorized solution. Current evidence says a large
isolated-sign corpus exists locally, it has meaningful native signer/sign diversity, only 65
AppHear classes have governed direct lexical mappings, native-label pretraining might not require
direct 236-class mapping, Candidate 01 reuse governance/license scope remains unresolved, and fresh
decode/timestamp validation would be required. Do not start this work until the project lead
explicitly reopens Phase 3.

## Phase 4A purpose and scope

Phase 4A asks whether the actual phone pipeline behaves approximately as predicted by the frozen
offline PHONE_01-sparse evaluation.

Target pipeline:

```text
REAL PHONE CAMERA
→ frozen Candidate 01 perception
→ frozen Recognition V2 [96,350] + mask
→ frozen ordinary V2 TCN
→ manually bounded isolated-sign prediction
```

Interaction is strictly:

```text
START
→ user performs exactly one isolated sign
→ STOP
→ classify captured sequence
→ display prediction and diagnostics
```

Phase 4A is not production deployment, continuous recognition, automatic sign boundary detection,
confidence/commit integration, or final AppHear conversational-UI integration.

## Required implementation order

### 1. Android recognition-v2 parity

Implement the exact frozen V2 feature contract on Android. Before live recognition, compare
Android V2 against offline V2 from identical Candidate 01 raw observations. Verify:

- `[96,350]` layout and `[96]` frame mask;
- normalization and reference frames;
- hand-local geometry;
- body-relative features;
- motion derived from selected chronological observations;
- selected-observation `dt` and elapsed fraction;
- point/group validity and missingness;
- padding;
- dense and PHONE_01-sparse temporal behavior where applicable.

Any systematic layout, transform, temporal, validity, or padding disagreement is a parity failure
and blocks the next step.

### 2. Recognizer runtime parity

Package or convert only the frozen ordinary V2 TCN. For identical V2 tensors, verify equivalent
probabilities/logits, Top-1, and Top-5 between reference desktop/Keras inference and Android. The
rejected invariant checkpoint is forbidden.

### 3. Manually bounded live phone test

Implement only START → SIGN → STOP → CLASSIFY. Do not add automatic gating or conversational-UI
commit behavior.

### 4. Diagnostic evidence

Each attempt must preserve:

- attempt ID and optional expected gloss for labeled testing;
- start/end timestamps and capture duration;
- Candidate 01 observation timestamps and usable-observation count;
- selected observation indices/timestamps;
- raw Candidate 01 observations sufficient to reproduce V2;
- generated V2 `[96,350]` tensor or a proven reproducible equivalent;
- frame mask;
- model logits/probabilities, Top-1, Top-5, and confidence;
- recognition latency;
- available perception/runtime timing.

Every phone failure must be reproducible offline rather than diagnosed from visual impressions.

## Initial diagnostic class set

Phase 4A does not initially require all 236 signs. Before live testing, select and record a bounded
set directly from the frozen V2 evaluation artifacts containing:

- strong V2 classes;
- medium-performing classes;
- weak or zero-recall classes;
- classes with substantial dense→sparse degradation.

Do not invent linguistic groupings without governed metadata. The concrete class list and selection
query belong to Phase 4A implementation evidence and must be frozen before the phone run.

## Decision after Phase 4A

### Outcome A — phone approximately matches offline sparse behavior

Interpretation: Android implementation/runtime is likely correct and recognition/data
generalization remains the dominant blocker. Explicitly return to Phase 3 and decide whether to
authorize external/pretrained signing diversity or another fundamentally stronger strategy.

### Outcome B — phone is materially worse than offline sparse behavior

Interpretation: an additional phone-domain, runtime, perception, temporal-density, or parity
mismatch exists. Diagnose that mismatch before external-pretraining work.

Neither outcome authorizes automatic Phase-3 experimentation. The project lead must explicitly
reopen Phase 3 and choose one subsystem using the Phase 4A evidence.

## Current Gate 0 / Gate 1 / Gate 2 / Gate 3 execution state

- Gate 0 deployment identity is **PASS**. The frozen ordinary V2 checkpoint is exactly
  `8107accbc621ae5652766fec80d314fe8dc9f94ba0d0548a6aef80ed91729340`; the 236-class vocabulary
  SHA-256 is `a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b`.
- The exact frozen V2 transform is implemented in debug-only Kotlin at
  `android/app/src/debug/java/com/example/apphear/perceptionvnext/RecognitionV2.kt`.
- The reproducible parity corpus contains 10 structurally selected TRAIN clips and both dense and
  PHONE_01-sparse views. DEV and protected TEST were not accessed.
- The same Android debug-source Kotlin code passes the host preflight against Python goldens with
  max/p95/mean absolute error `1.1920929e-7/0/6.3152280e-11` and zero discrete mismatches.
- Physical-device instrumentation passed on Xiaomi M2101K7AG (Android 12). Dense max/p95/mean
  absolute error is `1.1920929e-7/0/1.0493871e-10`; sparse is
  `1.1920929e-7/0/2.1365850e-11`. Selection, timestamps, masks and discrete features have zero
  mismatches. Padding/mask, invalid-state, and sparse selected-timestamp motion tests all pass.
- Evidence root:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase4a_android_v2_parity_01/`.
- Gate 2 recognizer runtime parity is **PASS**. The frozen ordinary V2 checkpoint converted to
  standard-builtins-only FP32 TFLite with SHA-256
  `1ccf0afa9af9aa602aa0de33c9635f5cffd7feec7d9b4e32382bc5e3fa02880c`. On the exact 10 dense
  and 10 sparse TRAIN-only tensors, Keras↔host-TFLite max absolute error was `4.7683716e-7` and
  Keras↔physical-Xiaomi max absolute error was `3.5762787e-7`; all Top-1, Top-5 membership and
  Top-5 ordering checks matched. Masked padding was exactly invariant on all three runtimes.
- Gate 2 Android runtime was TFLite 2.16.1, deterministic FP32 CPU with four threads, XNNPACK
  requested and GPU/NNAPI disabled. The runtime manifest explicitly pins
  `apphear.perception_vnext.recognition.v2`. Recognizer-only p50/p95/max was
  `1.693/1.823/1.859 ms` after
  warm-up. Evidence root:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase4a_gate2_recognizer_runtime_parity_01/`.
- Gate 3 known-TRAIN end-to-end replay is **PASS**. On the same 10 raw-v1 TRAIN fixtures and both
  dense and PHONE_01-sparse views, the physical Xiaomi composed
  `raw-v1 -> RecognitionV2.kt -> authorized FP32 TFLite -> class/gloss`. Android V2 intermediate
  max/p95/mean absolute error was `1.1920929e-7/0/6.3152280e-11` with zero
  selection/timestamp/mask/discrete mismatches. Composed Keras-reference probability max/p95/mean
  error was `4.1723251e-7/1.7462298e-9/1.5262949e-9`; Top-1, Top-5 membership, Top-5 order and
  class/gloss mapping all matched on 20/20 views. Forward/reverse and both dense/sparse invocation
  orders were exactly invariant across 14,160 output comparisons. Semantic correctness was 9/10
  dense and 8/10 sparse, diagnostic only and not part of the gate decision. Evidence root:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase4a_gate3_known_train_end_to_end_replay_01/`.

## Gate 4A-1 live-plumbing result

- Gate 4A-1 is **`LIVE_PLUMBING_VALIDATED`** on the Xiaomi M2101K7AG. The debug-only surface kept
  Candidate 01 warm, bounded attempts by camera source timestamp, deterministically drained
  eligible post-STOP work, preserved actual live cadence without applying the PHONE_01 simulator,
  and saved raw-v1/V2/mask/all probabilities and timing for every attempt.
- The deterministic five TRAIN-derived targets were HELLO/80, AT/8, HOME/83, STREET/179 and
  TABLE/183. Five valid attempts completed; no no-observation retry occurred. Tester signer status
  is `UNKNOWN`, so no familiar/unseen-signer interpretation is authorized.
- Host evidence was pulled before cleanup. Frozen offline replay matched Android with V2 max abs
  `1.1920929e-7` and probability max abs `3.8743019e-7`; Top-1 and Top-5 membership/order matched
  exactly for all five attempts. This proves the live plumbing and reproduction path, not semantic
  recognition quality.
- Semantic diagnostics were Top-1 `1/5` and expected-in-Top-5 `2/5`. Body availability was 100%,
  but mean LH/RH observed rates were `4.15%/24.62%`; TABLE had zero observed hands. This materially
  weaker hand evidence requires project-lead interpretation before authorizing a larger panel.
- Canonical evidence:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase4a_gate4a1_live_plumbing_validation_01/`.

## Gate 4A-1B controlled live-input recovery result

- Gate 4A-1B is a **technical PASS** on Xiaomi M2101K7AG: 10/10 valid controlled attempts were
  captured after the tester acknowledged the exact governed TRAIN exemplar for HELLO, AT, HOME,
  STREET and TABLE before each repetition. No invalid/no-observation attempt occurred.
- Evidence was pulled to the host before any cleanup. Frozen offline replay matched Android with
  V2 max/p95/mean absolute error `1.1920929e-7/0/1.9362189e-11` and probability error
  `5.9604645e-7/3.7252903e-9/3.2923340e-9`; Top-1 and Top-5 membership/order mismatches were zero.
- Semantic diagnostics remain weak: Top-1 `2/10`, expected gloss in Top-5 `5/10`. HELLO was Top-1
  in both repetitions; HOME reached Top-5 once and STREET reached Top-5 twice; AT and TABLE did not
  reach Top-5.
- The original whole-capture hand-rate interpretation was incomplete. Seven of ten controlled
  attempts retained an observed hand continuously or near-continuously (`87.5–100%`) across the
  actual first-to-last hand-observed interval. STREET retained both hands continuously for
  `1.47 s` and `1.80 s`. Long `6.14–10.83 s` START/STOP windows contain substantial hands-down
  lead-in/lead-out and dilute whole-attempt rates.
- The evidence is nevertheless not uniformly healthy: both TABLE repetitions retained a hand in
  only half of their short active interval, and the saved overlays show contact/overlap ROIs with
  refiner-presence collapse. The exact TRAIN TABLE reference also had 0% refined-hand observation,
  so this alone does not establish a new live-only Candidate01 failure. HELLO/HOME body-group availability was 0 despite partial visible body
  joints because close framing did not satisfy the frozen full body-reference predicate.
- Final attribution is **`MIXED_OR_INCONCLUSIVE`**. Gross darkness/blur alone is not supported;
  exact-exemplar guidance did not restore Top-1 beyond HELLO; active-sign evidence is coherent for
  most attempts, TABLE remains contact/refiner-poor in both TRAIN and live, and long manual bounds plus body
  framing and the known recognizer-generalization limitation remain entangled.
- Candidate 01, Recognition V2 and the ordinary V2 TCN were not modified. No training, DEV access,
  protected-TEST access, production UI connection, automatic boundaries, or Gate 4A-2 panel
  occurred. Canonical evidence:
  `artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase4a_gate4a1b_controlled_live_input_recovery_01/`.

## Gate 4A-1C validated causal finding and locked transition

The project lead independently validated
PHASE_4A_GATE_4A1C_ORACLE_TEMPORAL_BOUNDARY_REPLAY_01 as **PASS** with classification
TEMPORAL_BOUNDARY_PRIMARY_EFFECT_SUPPORTED.

- source session: session_20260915T065635Z;
- oracle-boundary SHA-256:
  0e6f14f159287ce830b68c4d33edba88dbb6aeef386060b80f79e3fed4a1e41f;
- confidence: HIGH 8, MEDIUM 1, LOW 1, UNCERTAIN 0;
- full windows: Top-1 2/10, expected-in-Top-5 5/10;
- oracle windows: Top-1 7/10, expected-in-Top-5 8/10;
- median expected probability: 0.053839→0.585159;
- median expected rank: 5→1;
- became correct: HOME attempts 005/006, STREET attempt 007, TABLE attempts 009/010;
- became wrong: none;
- still wrong: AT attempt 003→WINDOW, AT attempt 004→IN, STREET attempt 008→CLOTHES.

This causally establishes excessive idle/preparation/recovery context as a major Phase-4 failure
source. The required future isolated-sign architecture is:

    continuous phone camera
    → frozen Candidate01 continuous raw-v1 observations
    → rolling observation buffer
    → automatic sign-start
    → sign active
    → automatic sign-end
    → small controlled pre/post margin
    → frozen recognition-v2
    → improved 236-class recognizer
    → gloss
    → existing AppHear conversational UI
    → automatic re-arm

The continuous camera/event loop does not solve fluent continuous ASL or coarticulation. Current
recognition scope remains one isolated, pause-separated sign at a time.

Candidate01 systemic failure is not supported and Phase 1 must not reopen. Complete body-reference
validity is not a hard global gate: HELLO remained correct and both HOME attempts became correct
after temporal isolation while complete body-group availability remained 0%. Framing readiness is
a future guidance/quality aid, not a mandatory recognition blocker unless separately validated.

The result does not solve Phase 3: AT ×2 and one STREET attempt remained wrong after defensible
isolation. Phase-4 causal investigation is closed, Gate 4A-2 is on hold, and the next primary
boundary is return to Phase 3 for project-lead selection of a new-information/diversity strategy.
No Phase-3 implementation or training is authorized by this handoff update.

## Gate 5 final attribution and Phase-4A completion

Gate 5 reviewed the retained Gate 0 through Gate 4A-1C evidence without running inference,
capture, evaluation, extraction or training. It classified Phase 4A as
**`PHASE_4A_COMPLETE_RETURN_TO_PHASE_3`**.

The final attribution is:

- Android runtime, recognition-v2 implementation, TFLite conversion, label mapping, buffer state,
  source-timestamp START/STOP membership and live double-sparsification are ruled out as primary
  causes by direct parity/integration tests;
- a general Candidate01 live-phone failure, lighting, tester sign variant and missing refined-hand
  evidence are not supported as the primary explanation by this bounded evidence;
- body/framing mismatch and phone cadence sensitivity are confirmed secondary issues;
- excessive temporal context/bad sign boundaries are a confirmed major contributor;
- unseen-signer/independent-signer generalization remains unresolved;
- the current ordinary V2 TCN is not production-ready.

All Phase-4A completion criteria passed: identity governance, Android V2 parity, TFLite parity,
saved-data composition, real-camera operation, offline replay, causal temporal attribution and
separation of residual recognition failures from Android/runtime faults. The canonical Gate-5
report is:
`artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/phase4a_gate5_live_phone_failure_attribution_and_decision_01/PHASE4A_GATE5_FINAL_REPORT.md`.

Gate 4A-2 does not run now. It is superseded by a later governed phone validation after Phase-3
recognition improves. The next primary boundary is **`PHASE_3_RECOGNIZER_GENERALIZATION_REOPEN`**,
but this handoff does not authorize a specific experiment, implementation or training run.

## Persistent anti-loop rules

- Gate 4A-1C is the last Phase-4 causal experiment; no Gate 4A-1D or 4A-1E.
- Gate 4A-2 is superseded until later validation after Phase-3 improvement; no further five-sign diagnostic loops.
- No Candidate02, V2.1/V3, FPS loop, threshold loop or Candidate01 changes.
- No same-data sampler/loss/contrastive-weight/LR/optimizer/seed/epoch loops.
- Do not confuse required automatic segmentation with a complete recognition solution.
- Do not confuse unresolved Phase-3 generalization with Android runtime failure.
- Do not access protected TEST.
- Change only one subsystem at a time.

## Governance and stop boundary

- Existing scientific artifacts remain immutable.
- No training is authorized by this handoff.
- Protected TEST must not be accessed.
- Gates 0, 1, 2, 3, 4A-1, 4A-1B and 4A-1C are complete. Gate 4A-1C added only an offline replay
  over retained Gate-4A1B raw-v1 and did not change Candidate01, V2, the recognizer or temporal
  construction. It classified **`TEMPORAL_BOUNDARY_PRIMARY_EFFECT_SUPPORTED`**: oracle trimming
  improved Top-1 `2/10→7/10` and expected-in-Top-5 `5/10→8/10`, with no correct attempt becoming
  wrong. AT ×2 and one STREET attempt remained wrong, so Phase 3 is still paused and unsolved.
- Gate 4A-1B added only bounded debug evidence
  around the frozen live path. No production UI/commit behavior, automatic boundaries, 30-class
  panel, training, DEV access or protected-TEST access occurred.
- Current boundary: **PHASE_3_RECOGNIZER_GENERALIZATION_REOPEN**. Phase 4A is complete and Gate
  4A-2 is superseded until later post-improvement validation. Do not implement automatic
  segmentation, start Phase 5, change Candidate01, or launch Phase-3 training automatically.
