# E6 Component Decision

**Purpose:** Consolidate the verified E6 results and decide whether the planned mixed recognition
architecture may proceed to routed simulation or Android shadow integration.

**Scope:** Architecture gate and rollback record only. No experiment, model, data, schema, export,
or Android change is authorized by this document.

**Current status:** E6 COMPONENT REVIEW COMPLETE / E6-6 AND E6-7 BLOCKED / BASELINE PRESERVED.

**Last updated:** 2026-08-09.

## Protected Baseline

The protected production path remains unchanged:

```text
CameraX -> MediaPipe hand + pose -> schema v3.0 [96,258]
  -> existing [1,96,258] TFLite recognizer -> confirmation -> sentence/UI
```

The E6 five-sign models are offline experimental controls. They have not replaced the current
Android model, vocabulary, configuration, confirmation behavior, or sentence/UI path.

## Component Ledger

| Phase | Component/question | Verified decision | Eligible for integration? |
|---|---|---|---|
| E6-0 | frozen production baseline and rollback | complete; baseline protected | baseline only |
| E6-1 | evidence/data audit | complete; bounded repaired dataset created | supports offline controls only |
| E6 v3 control | five-sign v3.0 positive recognizer | useful diagnostic control; `KNOW` weak on fresh/stress AppHear | no production migration |
| E6-2 | global `[96,444]` geometry | no-go as primary; useful research evidence | no |
| E6-3 | MSP/energy/Mahalanobis rejection | strict no-go; no valid operating point | no |
| E6-4 | frozen confusion registry | evidence pass; provisional `KNOW -> HELLO` only | registry evidence only |
| E6-5 | v3/geometry `KNOW/HELLO` specialist | no-go; no branch selected | no |
| E6-6 | routed-system simulation | prerequisites absent | blocked |
| E6-7 | Android shadow deployment | E6-6 not passed | blocked |

## Why E6-6 Cannot Proceed

E6-6 was designed to combine a passed primary, calibrated/rejected acceptance path, registered
confusion groups, and independently passed specialists. The required E6-3 rejector and E6-5
specialist both failed. Combining failed components would contradict the staged plan and would not
produce new trustworthy evidence.

Running the primary alone under an E6-6 name would duplicate the existing five-sign control.
Running the registry without a passed resolver would add routing complexity without a corrective
decision. Therefore E6-6 is skipped, not renamed or weakened.

## Product-Core Consequence

- `GOOD`, `HELLO`, `SORRY`, and `HAVE` retain their existing bounded positive-recognition evidence;
  this is not a production-readiness claim because open-set/no-sign safety is still unresolved.
- `KNOW` is deferred from the E6 candidate set because fresh and stress signer behavior failed in
  the primary, geometry, pair-restricted, and specialist tests.
- No E6 result authorizes a four-sign production model. Removing `KNOW` from the experimental
  candidate set does not silently alter the Android vocabulary.

## Confirmed Versus Unknown

### Verified project evidence

- The current closed-set landmark path recognizes selected supported signs but does not provide a
  safe open-set decision boundary.
- Available handcrafted geometry does not solve the hardest AppHear `KNOW` performances.
- The frozen embedding does not support the tested global rejectors.
- A binary temporal specialist does not solve the registered `KNOW/HELLO` group.

### Engineering inference

- The currently planned mixed architecture has no evidence-supported correction/acceptance stack
  to integrate beyond the protected baseline.
- Continuing with thresholds, extra epochs, or another pair specialist would repeat exhausted work.

### Unknowns requiring separate approval

- Whether a validated data/variant repair can make `KNOW` generalize to new AppHear signers.
- Whether a genuinely different hand-crop RGB stream can help a future confusion group.
- Which open-set/streaming architecture can meet false-commit requirements after E6-3.

## DO NOT REPEAT

- E6-2 handcrafted geometry as a global replacement or additional geometry subsets.
- E6-3 MSP, fixed-temperature energy, or pooled OAS-Mahalanobis threshold sweeps.
- E6-5 pair restriction, v3 binary TCN, or geometry binary TCN for `KNOW/HELLO` on the same data.
- Selecting seed `303` geometry because its fresh result is better; it still fails stress and the
  fixed all-seed gate.
- Upper-body frozen-MobileNet RGB or naive fusion from E3-B3/E3-C/E4-V.
- E6-6 under a new name without independently passed components.

## Rollback And Safety State

- No rollback action is necessary because no E6 experiment modified production behavior.
- All E6 artifacts remain isolated under `artifacts/recognition_upgrade/`.
- Deleting experimental artifacts is unnecessary and is not authorized here.
- Current Android assets and runtime remain the fallback and active baseline.

## Decision

The planned E6 mixed architecture does **not** advance to E6-6 or E6-7 with the current evidence.
The project remains on the protected baseline. `KNOW` is deferred rather than repeatedly optimized.

This is a checkpoint, not authorization for an alternative architecture. Any future direction must
first be reviewed against this component ledger and the original recognition-upgrade goals.

## Source-Of-Truth Files

- `E6_PRODUCTION_RECOGNITION_ARCHITECTURE_PLAN.md`
- `E6_2_LANDMARK_GEOMETRY_RESULT.md`
- `E6_3_OPEN_SET_REJECTION_RESULT.md`
- `E6_4_CONFUSION_REGISTRY_RESULT.md`
- `E6_5_KNOW_HELLO_SPECIALIST_RESULT.md`
- `ROLLBACK_AND_COMPATIBILITY_PLAN.md`
- parent `../feature-schema.md`
- parent `../eval-protocol.md`

## Risks And Open Questions

- **Risk:** interpreting bounded closed-set results as a translator-ready model.
- **Risk:** replacing failed components with unreviewed alternatives and restarting experiment
  churn.
- **Open question:** which future direction best serves the full translator goal while respecting
  the E1-E6 evidence?

## Next Required Action

Review and approve the consolidated E6 decision before authorizing any new architecture, dataset
repair, vocabulary expansion, model training, routing, RGB, or Android work.

## Post-E6 Review Resolution - 2026-08-09

The review is complete in `POST_E6_ARCHITECTURE_REVIEW.md`. E6-6/E6-7 remain blocked. Exactly one
next experiment is selected: the staged C0-B0 hand-ROI feasibility gate in
`C0B_APPHEAR_HAND_ROI_FEASIBILITY_PLAN.md`. Only Stage 1 inventory and toolchain preflight may be
implemented after user approval; no detector training is automatic.
