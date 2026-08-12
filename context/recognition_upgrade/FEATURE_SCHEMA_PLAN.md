# Feature Schema Plan

**Purpose:** Define the experimental multimodal contract without changing production schema 3.0.
**Status:** E6-2 EXPERIMENT CONTRACT DEFINED; PRODUCTION v3.0 UNCHANGED. **Last updated:** 2026-08-09.

## Contract Strategy

Keep `schema_version=3.0` and `[96,258]` immutable. Introduce a separately named experimental
contract, provisionally `apphear.hybrid.v0`, in new artifact/config paths. Promote to numeric
`4.0` only after E3 wins and `/imprint` updates the parent `feature-schema.md`.

## Proposed Sample

| Tensor/field | Proposed shape | Meaning |
|---|---|---|
| `timestamps_us` | `[T] int64` | monotonic capture timestamps |
| `dt_s` | `[T] float32` | clipped real inter-sample delta |
| `landmarks_xyz` | `[T,75,3]` | 42 hand + 33 pose points in canonical coordinates |
| `landmark_visibility` | `[T,75,1]` | pose visibility; hand-level score broadcast only if documented |
| `landmark_mask` | `[T,75,1] bool` | actual observation, never inferred from zero |
| `velocity`, `acceleration` | `[T,75,3]` | finite differences divided by real `dt`, masked |
| `bone_vectors` | `[T,E,3]` | directed anatomical edges |
| `joint_angles` | `[T,A]` | selected stable hand/arm angles |
| `relations` | `[T,R]` | hand-hand and hand-body distances/directions |
| `hand_rgb` | `[T,2,H,W,3] uint8` | synchronized left/right crops; H/W candidate 80/96/112 |
| `crop_box`, `crop_quality` | `[T,2,4]`, `[T,2,Q]` | source-frame normalized ROI and quality |
| `frame_mask` | `[T] bool` | valid time steps |
| `boundary_target` | `[T] int8` | idle/onset/active/release where annotated |
| metadata | structured sidecar | signer, gloss, camera, extraction hashes |

Do not falsely create per-landmark hand confidence: MediaPipe exposes detection/presence/handedness
scores at hand/category level, not a verified confidence for every landmark. Store the score at its
actual semantic level.

## Coordinate Spaces

Persist raw image coordinates. Derive: body-relative canonical coordinates; each hand centered at
wrist and scaled by palm size; optional orientation-normalized hand coordinates; relation features
in body scale. Keep camera chirality and canonical handedness explicit. Never mirror RGB without
applying the exact corresponding landmark/label transform.

## Missingness And Time

Missing values remain NaN in derived storage plus explicit masks; model input may use zero only
after masking. Velocity across a missing gap is invalid unless an experiment-approved interpolator
marks it as imputed. Cap `dt`; distinguish dropped frames from held pose. Resampling is an
augmentation/view, not canonical data.

## Parity

Python owns the contract. Kotlin must reproduce crop geometry, timestamps, normalization, masks,
and derived features within defined tolerances using golden fixtures containing raw frames and
landmarks. RGB parity uses pixel checksum/tolerance after crop/resize/color conversion. Every model
manifest lists schema, landmarker mode/model hashes, crop size/color order, temporal policy, tensor
shapes, normalization constants, and quantization.

## Decisions, Assumptions, Risks, Unknowns, Next Action

- **Decision:** structured named tensors, not one undocumented flat vector.
- **Alternative:** compute velocities/bones inside the model; E1/E3 compare for export/parity cost.
- **Assumption:** uint8 crops reduce storage/I/O without losing rebuildability because raw video stays.
- **Risks:** schema complexity, crop parity, inaccurate timestamps, mask misuse.
- **Open questions:** selected graph/angle/relation lists and crop resolution.
- **Next action:** do not freeze `v0` until E2e-C0 establishes reliable ROI semantics and E3 approves a multimodal contract; then run `/imprint`.


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-016 apply; component-specific decisions in this document apply only after their experiment gate passes.
- **Assumptions:** Any forecast or unmeasured dimension remains a hypothesis, not a project fact.
- **Open questions:** Unresolved items are tracked in this document and `OPEN_QUESTIONS.md`.
- **Risks:** Applicable failure modes and fallbacks are tracked in this document and `RISK_REGISTER.md`.
- **Next required action:** Follow the explicit next action above and the ordering in `EXPERIMENT_MATRIX.md`; do not skip gates.

## Dynamic Mixed Schema Revision - 2026-07-31

The next milestone keeps production schema `3.0` and `[96,258]` as the primary stable-sign contract.

Do not promote the E4-Q derived `[96,728]` feature tensor to Android. E4-Q showed that velocity/acceleration/relation features did not fix `SORRY/BECOME/HELP` and often worsened `SORRY`.

### Planned Additional Contracts

The dynamic mixed roadmap requires two future experiment-only contracts, both separate from schema `3.0`:

1. **Confusion registry config**
   - group id
   - gloss members
   - trigger rules from primary logits/top-k/margins
   - resolver asset and schema if available
   - thresholds for accept/reject
   - fallback behavior

2. **Specialist resolver schema**
   - starts group-specific;
   - may include hand/body RGB crops only for the registered group;
   - must include crop quality and missingness masks;
   - must define Kotlin/Python parity before Android use.

The primary recognizer must continue refusing schema mismatches. A specialist resolver must also refuse mismatched group id, label order, crop geometry, and calibration version.

### Next Schema Action

Do not run `/imprint` for `[96,728]`. The next schema work is an offline registry/resolver manifest design after the Phase 1 stable-primary experiment plan is prepared.

## E6 Feature-Schema Direction - 2026-08-03

Verified project evidence:

- Production schema v3.0 `[96,258]` remains immutable and is the control path.
- E4-Q derived `[96,728]` did not solve the `SORRY/BECOME/HELP` confusion and must not be promoted.
- E5-H/E5-I show the current v3.0 closed-set signal is not enough for open-set routed safety.

Engineering inference:

- The next feature-schema work should be an experiment-only kinematic landmark contract, not a production schema change.
- The contract should start from v3.0 positions and add explicit masks, real time deltas, velocity, selected bones, selected angles, duration, and hand/body relationships.
- RGB crops remain specialist-specific and should not be added to the primary contract until a group-level RGB experiment beats landmark controls.

Hypothesis requiring experimentation:

- A named contract such as `apphear.landmark_kinematic.v0` may improve open-set rejection and confusion separation by exposing motion/geometry/missingness that `[96,258]` leaves implicit.

Gate:

- The richer contract must beat v3.0 under identical signer-disjoint splits and routed/open-set metrics before any Kotlin parity work, `/imprint`, numeric schema promotion, or Android integration.

## E6-2 Geometry Control Contract - 2026-08-09

The E6-2 architecture is now specified in `E6_2_RICHER_LANDMARK_CONTROL_PLAN.md`.

- Experiment identifier: `apphear.landmark_geometry.v0`.
- Proposed shape: `[96,444]`.
- Layout: immutable v3.0 `258` + hand-local coordinates `120` + joint cosines `28` + palm
  normals `6` + body/head relations `28` + quality/masks `4`.
- It deliberately excludes the naive velocity/acceleration blocks already tested by E3-B6/B7.
- It uses existing pose nose/eye/ear/shoulder anchors; no dense face landmark task is added.
- The wider first layer must use zero-extension warm start so the candidate is functionally
  identical to the v3.0 control before training.
- Real timestamp-aware motion is deferred because the assembled E6 tensors do not retain
  authoritative per-frame timestamps.

Status: architecture only. No schema implementation, numeric schema promotion, `/imprint`, or
Android work is authorized.
