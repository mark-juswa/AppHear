# Post-C0 Product Scope Decision

**Purpose:** Resolve the product-scope decision required after C0-B0 failed, without inventing a
replacement model or weakening the recognition-upgrade gates.

**Scope:** Architecture and research-governance decision only. No code, model, dataset, schema,
Android asset, confirmation rule, or production behavior is changed by this decision.

**Status:** Complete. The current milestone is a **bounded on-device isolated-sign research
prototype using the protected 236-sign v3.0 recognizer**. Reliable continuous silent ASL
translation remains the long-term product goal, but is not a supported claim of the current system.

**Last updated:** 2026-08-11.

## Original Goal Preserved

AppHear's long-term goal remains translating another person signing for a hearing user who may not
know ASL. User confirmation is therefore not an acceptable correctness mechanism. A real
translator must make algorithmic decisions and must be evaluated end to end on held-out signers.

The goal is preserved, but the current evidence does not authorize describing the existing app as
a reliable continuous translator.

## Verified Current Capability

The protected Android baseline is:

```text
CameraX -> MediaPipe hand + pose -> schema v3.0 [96,258]
  -> 236-class streaming TCN TFLite -> confirmation -> sentence/UI
```

Verified baseline facts from `E6_0_BASELINE_FREEZE.md` and `recognition-accuracy.md`:

- 236 curated conversational gloss classes;
- schema `3.0`, `[96,258]`, MediaPipe IMAGE mode;
- INT8 model with float I/O and frozen Android assets;
- cross-signer offline top-1 around `0.606-0.612` under the documented conversational tests;
- low-FPS k8 diagnostic top-1 around `0.527` and top-5 around `0.825`;
- deployed confirmation precision was reported around `0.73` in prior offline evaluation;
- device throughput is approximately `5-8 fps`, below the project `>=15 fps` target;
- no completed held-out, end-to-end signed-phrase result exists for the current app.

These values support a research prototype and controlled demonstration. They do not establish
reliable silent translation, continuous ASL recognition, or production readiness.

## Why Other Immediate Routes Are Closed

| Route | Verified result | Decision |
|---|---|---|
| More global landmark/geometry variants | E1, E3-B4/B5/B6/B7, and E6-2 did not pass replacement gates | do not repeat now |
| Confidence/energy/distance rejection | E4, E5-H/I, and E6-3 supplied no safe general operating point | do not retune now |
| Scalable confusion specialists | one GOOD/SORRY proof passed, but E6 KNOW/HELLO failed and no scalable layer passed | do not integrate |
| Full-frame/upper-body RGB and naive fusion | E3-B0/B1/B2/B3/C generalized poorly and often damaged landmark performance | exhausted in tested form |
| Detector-derived hand RGB | C0-B0 I320 failed development recall/localization gates and has no independent hard-negative retraining set | retire as immediate route |
| Continuous CTC/translation | no natural sentence-level boundary/translation corpus and isolated reliability remains unresolved | remain blocked |
| Android shadow migration | no replacement component stack passed offline gates | remain blocked |

## Selected Current Scope

AppHear may be presented and evaluated as:

> An on-device research prototype for recognizing isolated/citation-form signs from a bounded
> 236-gloss vocabulary and incrementally assembling recognized glosses in the UI.

It must not be presented as:

- a reliable continuous ASL-to-English translator;
- conversation-level ASL understanding;
- signer-independent production recognition;
- safe open-set recognition of arbitrary signing;
- a system whose top-3 alternatives can be corrected by a non-signing observer;
- a production-ready accessibility replacement.

The UI sentence builder remains part of the application behavior, but it does not convert an
isolated-gloss classifier into a validated continuous translator.

## Protected Baseline, Recorded Drift, And Rollback

- Keep the exact schema, model, vocabulary, calibration, MediaPipe assets, confirmation logic, and
  Android runtime listed in `E6_0_BASELINE_FREEZE.md`.
- Keep recovery commit `67afa5f0815e758c32878282d87b3f00b2bdbb19` and tag
  `stable-baseline-before-redesign` as the recognition rollback reference.
- Do not replace production assets with E1-E6 or C0 artifacts.
- Keep all experimental artifacts research-only under `artifacts/recognition_upgrade/`.

Hash verification on 2026-08-11 found that the TFLite model, vocabulary, model manifest, and both
MediaPipe task files still match E6-0. `recognition_config.json` does not match its E6-0 hash because
the working tree contains a pre-existing, disabled `post_commit_rearm` configuration block:

```text
enabled=false; departure_frames=0; measurement_logging=false
```

This decision did not create or revert that change. Because the feature is disabled, it is treated
as behavior-preserving pending F22, but the current working tree must not be described as byte-for-
byte identical to the E6-0 configuration. Strict rollback still uses the recorded commit/tag.

## Next Executable Action

Run the existing F22 device smoke from `context/device-smoke.md` on the current behavior-preserving
baseline. This
is not a new model experiment. Its purpose is to verify that the protected app still builds,
loads the frozen model/landmarkers, captures frames, produces features, performs inference, and
retains rollback integrity after the research work.

After F22, the next accuracy evidence would be a separately approved held-out end-to-end baseline
evaluation, not model development. It requires fresh signer-separated positive phrases and
no-sign/OOV sessions. Without that data, report only the existing offline diagnostics and state
that end-to-end phrase accuracy is unknown.

## Conditions For Resuming Recognition R&D

Recognition architecture work remains paused unless one of these materially new inputs is approved:

1. New signer-diverse, training-only hard-negative and hand-box data sufficient to reopen C0-B0.
2. A natural continuous-sign corpus with boundaries/gloss/text appropriate for CTC or translation.
3. A materially new maintained pretrained visual/SLR model with a feasible Android or explicitly
   approved server contract, evaluated against the frozen baseline.
4. Fresh held-out device data showing a specific baseline failure that has not already been tested.

Any reopening must identify the closest prior experiment, the material difference, a single gate,
and a rollback path before implementation.

## Evidence Labels

- **Verified project evidence:** all metrics and experiment closures listed above.
- **Engineering inference:** the current system is useful as a bounded research demonstrator but
  cannot support a reliable-translator claim.
- **Hypothesis requiring experimentation:** new data or a materially different pretrained model
  could reopen a stronger architecture path.
- **Unknown:** current held-out end-to-end phrase accuracy and multi-device robustness.

## Source Of Truth

- `E6_0_BASELINE_FREEZE.md`
- `E6_COMPONENT_DECISION.md`
- `POST_E6_ARCHITECTURE_REVIEW.md`
- `C0B_STAGE2_DEVELOPMENT_RESULT.md`
- `C0B_POST_I320_DATA_DECISION.md`
- `ARCHITECTURE_DECISIONS.md`
- `MIGRATION_PHASES.md`
- `../project-overview.md`
- `../eval-protocol.md`
- `../recognition-accuracy.md`
- `../device-smoke.md`

## Next Required Action

Execute and record F22 device smoke on the current 236-sign baseline, explicitly confirming that
`post_commit_rearm.enabled=false`. Do not start model training,
RGB, detector, rejection, specialist, schema, or Android-recognizer migration work.
