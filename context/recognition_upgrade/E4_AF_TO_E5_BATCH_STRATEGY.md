# E4-AF To E5 Batch Strategy

**Purpose:** Lock the next recognition-upgrade direction after E4-AC/E4-AD/E4-AE: finish the minimum no-sign safety floor, then move to batch-scale candidate screening instead of continuing one-sign loops.

**Scope:** Architecture and experiment planning only. This document does not authorize Android integration, TFLite export, production recognizer replacement, production asset changes, or source dataset mutation.

**Current status:** APPROVED NEXT DIRECTION / IMPLEMENTATION NOT STARTED.

**Last updated:** 2026-08-02.

## Executive Decision

The best next path is:

```text
E4-AF: short acceptance-policy and safety-floor experiment
  -> E5-A: large dual-source candidate screening batch
  -> E5-B: train next Tier-A primary model
  -> E5-C: register specialists only for proven confusion groups
  -> Android experimental integration only after offline no-sign/OOV gates pass
```

This avoids two bad extremes:

- continuing one-sign experiments indefinitely;
- blindly training a large vocabulary that repeats the earlier false-commit and generalization failures.

## Verified Evidence

The current dynamic mixed path is still supported:

- E4-S showed a stable primary candidate for `GOOD`, `HELLO`, `HAVE`, and `KNOW`: closed-set latest mean test `0.9848`.
- E4-V showed `GOOD/SORRY` can be resolved by a lightweight landmark specialist: mean/min test `0.9667`.
- E4-W showed primary plus specialist routing recovered withheld `SORRY`: mixed mean accuracy `0.9718`.
- E4-X passed only an artificial zero-landmark no-sign probe.
- E4-Y failed on real MediaPipe no-sign windows: max false commit rate `0.9688`.
- E4-Z crude gates removed false commits but destroyed positive coverage and `SORRY`.
- E4-AA fixed most no-sign commits but over-rejected low-motion `SORRY`.
- E4-AC is the best current gate: mean/min accepted precision `0.9548/0.9492`, positive coverage `0.9746/0.9661`, max no-sign false commit `0.0441`, and GOOD/SORRY recall `0.9667`.
- E4-AD localized residual failures to `NO_SIGN -> HELLO`, especially P1 ordinary-hand windows.
- E4-AE showed naive hard-negative weighting is not enough: min accepted precision fell to `0.9417`.

## Engineering Interpretation

The system is not blocked because landmark recognition is globally broken. It is blocked because the recognizer can still commit a gloss during real non-signing hand motion.

Therefore, the next safety work should be intentionally short:

- do not retrain many gate variants blindly;
- do not manually review every sign;
- do not broaden the vocabulary before the false-commit floor is defined;
- do test whether a production-shaped acceptance policy can make E4-AC safe enough to support batch screening.

## E4-AF: Safety-Floor Acceptance Policy

E4-AF should be a fast offline policy experiment using existing E4-AC, E4-AD, and routed-recognizer outputs.

### Input

- E4-AC best gate run: `artifacts/recognition_upgrade/e4_generalization/e4_ac_low_motion_aware_gate_01`
- E4-AD false-commit review: `artifacts/recognition_upgrade/e4_generalization/e4_ad_false_commit_review_01`
- E4-S primary model run: `artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01`
- E4-V specialist run: `artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01`
- E4-W/E4-X routed-system outputs
- E4-AA real N0/P1 no-sign feature dataset

### Candidate Policies

E4-AF should compare small, Android-realistic acceptance rules:

1. **E4-AC baseline policy**
   - Gate probability threshold chosen by E4-AC.
   - Existing E4-S/E4-V routed recognizer.

2. **Class-specific commit floor**
   - Keep E4-AC gate.
   - Add stricter commit requirements for `HELLO`, because E4-AD shows residual no-sign commits are mostly `HELLO`.

3. **Temporal stability requirement**
   - A gloss must remain stable for at least 2 or 3 consecutive windows before sentence commit.
   - This is production-shaped because the Android app is streaming, not single-window only.

4. **Uncertainty/reject policy**
   - Reject when gate, recognizer, and specialist evidence disagree.
   - Reject low-margin or unstable predictions instead of forcing a translation.

5. **Data-expansion trigger**
   - If policies cannot pass without damaging `HELLO` or `SORRY`, the next action is targeted capture of HELLO-like no-sign footage, not more threshold tuning.

### Acceptance Gate

E4-AF should pass only if all are true on held-out test rows:

- accepted precision minimum >= `0.95`;
- positive coverage minimum >= `0.90`;
- max no-sign false commit rate <= `0.05`;
- `GOOD` recall minimum >= `0.90`;
- `HELLO` recall minimum >= `0.90`;
- `SORRY` recall minimum >= `0.90`;
- no test rows are used to train or tune model weights.

### Go Decision

If E4-AF passes:

- freeze the acceptance policy as the offline safety floor;
- proceed to E5-A large dual-source batch screening;
- still do not export or integrate Android yet.

### No-Go Decision

If E4-AF fails:

- collect a bounded HELLO-like no-sign expansion set;
- add it to a new gate training run;
- do not continue generic gate weight sweeps;
- do not expand vocabulary before the safety floor is recovered.

## E5-A: Large Dual-Source Candidate Screening

E5-A is where AppHear should stop moving one word at a time.

### Dataset Sources

Use both:

- `F:\ASL DATASET\ASL CITIZEN`
- `F:\ASL DATASET\local`

MS-ASL remains optional/deferred unless it is downloaded and its metadata can support signer-disjoint evaluation.

### Screening Size

The first E5-A batch should screen many candidates at once:

- target range: `50` to `100` candidate glosses if existing features are already available;
- smaller only if the inventory cannot support signer-disjoint splits;
- no raw-video extraction should be started until the feature inventory report says it is necessary.

### Output Tiers

Each candidate sign must be assigned to:

- **Tier A:** primary-model candidate;
- **Tier B:** confusion-group/specialist candidate;
- **Tier C:** data/label repair required;
- **Tier D:** defer/reject;
- **Inventory only:** not enough evidence yet.

### Required Metrics

E5-A should report:

- sample count per sign;
- signer count per sign;
- source coverage: ASL Citizen vs local;
- train/validation/test split feasibility;
- source leakage risk;
- per-class accuracy/recall/F1;
- confusion groups;
- source-aware failure cases;
- no-sign false commit impact when added to the routed system;
- promotion recommendation per sign.

## Long-Term Production Shape

The long-term production recognizer should be:

```text
CameraX + MediaPipe
  -> schema v3.0 [96,258] landmark window
  -> signing/no-sign gate
  -> primary Tier-A landmark recognizer
  -> acceptance policy
  -> confusion registry/router
      -> small specialist for registered hard group
      -> reject if unresolved
  -> sentence/UI
```

RGB or hybrid models remain available for future specialists, but E4-V/E3-C evidence says RGB should not become the default path yet.

## Risks

- A policy-only E4-AF may not solve high-confidence HELLO-like no-sign windows.
- Existing no-sign data may be too small and too narrow for production.
- Batch screening may reveal that many desired signs lack signer-diverse support.
- Some ASL Citizen labels may not align with local variants.
- Specialists can become too complex if every weak sign is promoted prematurely.

## Next Required Action

Prepare and run E4-AF as a short offline acceptance-policy package. If it passes, immediately move to E5-A batch screening. If it fails, collect targeted HELLO-like no-sign data before E5-A.

Do not run another one-sign expansion loop as the main path.

