# E6-2 Richer Landmark Control Plan

**Purpose:** Define one bounded, non-duplicative richer-landmark experiment against the frozen
five-sign v3.0 control.

**Scope:** Architecture and experiment contract only. This document does not authorize feature
generation, training, model export, Android work, production asset replacement, or dataset changes.

**Current status:** COMPLETE / STRICT PROMOTION GATE NO-GO. See `E6_2_LANDMARK_GEOMETRY_RESULT.md`.

**Last updated:** 2026-08-09.

## Decision Summary

E6-2 will test one experiment-only `[96,444]` feature tensor named
`apphear.landmark_geometry.v0`. It preserves all 258 v3.0 channels and appends compact,
per-frame geometry that the E3-B6/E3-B7 experiments did not test:

- hand-local, palm-scale-normalized coordinates;
- hand joint-angle cosines;
- palm orientation normals;
- hand-to-head, hand-to-shoulder, and hand-to-hand relations;
- explicit hand, pose-anchor, and frame-valid masks.

E6-2 will **not** add naive frame velocity, acceleration, RGB, face-mesh landmarks, rejection,
specialists, routing, or Android integration. Those are separate hypotheses and remain blocked.

## Verified Project Evidence

### Frozen control

- Result: `product_core_data_readiness/collection_targets_v1/E6_V30_REPAIRED_VALIDATION_TRANSFER_RESULT.md`.
- Architecture: broad-warm-start, four-block, 64-channel causal streaming TCN.
- Input: schema v3.0 `[96,258]`.
- Classes: `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`.
- Seeds: `101`, `202`, `303`.
- Mean latest-checkpoint accuracy:
  - repaired validation `0.9940`;
  - AppHear variant stress `0.6973`;
  - fresh AppHear test `0.8889`;
  - historical ASL test `0.9630`.
- Fresh `KNOW` recall is `0.5611`; stress `KNOW` recall is approximately `0.0222`.
- Production Android remains schema v3.0 `[96,258]`, 236 classes, and MediaPipe `IMAGE` mode.

### Closest previous experiments

| Previous experiment | Similarity to E6-2 | Verified result | Why E6-2 is not a rerun |
|---|---:|---|---|
| E3-B6 `[96,728]` augmentation | 45% | Naive velocity, acceleration, and 20 relation/presence channels improved mean masked-TCN test from `0.3433` to `0.3867`, but missed the validation gate and retained a large train-validation gap. | E6-2 excludes velocity/acceleration, uses a repaired five-sign cross-source benchmark, preserves broad pretraining, and tests hand-local shape, angles, palm orientation, and head-relative geometry absent from E3-B6. |
| E3-B7 reduced ablation | 35% | No velocity/relation subset beat the full E3-B6 result; small handcrafted delta/relationship iteration was stopped. | E6-2 does not repeat any E3-B7 feature subset and uses one preregistered candidate rather than another combinatorial subset sweep. |
| E6 v3.0 five-sign transfer | 70% | Established a stable `0.8889` fresh control and localized failure to `KNOW` signer/variant transfer. | E6-2 changes only the representation while preserving clips, assignments, model family, broad source encoder, seeds, and evaluation views. |

The E6-1 **DO NOT REPEAT** rule remains binding. A `[258 + velocity + acceleration + 20
relations]` package, its E3-B7 subsets, or additional threshold/epoch/seed tuning is prohibited.

## Hypothesis

**Hypothesis requiring experimentation:** A compact description of hand shape and hand position
relative to stable body/head anchors will improve cross-signer `KNOW` recognition while preserving
the already strong four classes.

This is plausible because v3.0 contains raw normalized points but leaves these invariances for the
small five-class fine-tuning set to learn. It is not established fact. The difficult `KNOW` rows
may instead be an incompatible sign variant or an upstream landmark-quality problem.

## Exact Experimental Feature Contract

Contract identifier: `apphear.landmark_geometry.v0`

Tensor shape: `[96,444]`

| Block | Width | Exact content |
|---|---:|---|
| `base_v30` | 258 | Immutable v3.0 hand and pose feature vector, byte-for-byte unchanged. |
| `hand_local_xyz` | 120 | For each hand, landmarks `1..20` minus wrist `0`, divided by per-frame palm scale; `20 * 3 * 2`. |
| `joint_cosines` | 28 | Fourteen joint-angle cosines per hand: two thumb joints and MCP/PIP/DIP joints for index, middle, ring, and pinky. |
| `palm_normals` | 6 | Unit cross product of wrist-to-index-MCP and wrist-to-pinky-MCP, three channels per hand. |
| `body_head_relations` | 28 | Per hand: centroid-to-nose, index-tip-to-same-side-eye, index-tip-to-same-side-ear, wrist-to-same-side-shoulder (`12 * 2`); hand-centroid vector and distance (`4`). |
| `quality_and_masks` | 4 | Mean pose visibility, left-hand present, right-hand present, frame valid. |
| **Total** | **444** | No RGB, world landmarks, detector confidence, velocity, acceleration, or face mesh. |

### Deterministic math

- Palm scale is `0.5 * (norm(index_mcp - wrist) + norm(pinky_mcp - wrist))`.
- If a hand is absent or palm scale is less than `1e-6`, all derived hand-shape channels for that
  hand are zero and its presence mask is zero.
- Joint channels store the cosine of the angle, not `acos`; normalized vector dot products are
  clamped to `[-1,1]`.
- Palm normals use an epsilon-safe normalized cross product. Degenerate palms emit zeros.
- Hand centroid is the mean of the 21 hand landmarks.
- A body/head relation is zero when either required hand or pose anchor is unavailable. Existing
  pose visibility remains available in the base block and mean pose visibility is appended.
- `hand_local_xyz` and body/head relation channels are clipped to `[-4,4]`. Angle cosines and palm
  normals remain in `[-1,1]`; masks remain binary.
- Padded frames are zero across all 444 channels.
- Every operation is frame-local and uses no future frames. The upstream v3.0 normalization remains
  unchanged; E6-2 does not claim to repair any existing normalization/runtime skew.

### Landmark indexing

- Hand: MediaPipe Hands indices `0` wrist, `4` thumb tip, `5/8` index MCP/tip, `9` middle MCP,
  `17` pinky MCP.
- Pose: MediaPipe Pose indices `0` nose, `2/5` eyes, `7/8` ears, `11/12` shoulders.
- Left/right anchor association follows the canonical handedness ordering already produced by the
  v3.0 normalizer. The implementation smoke test must verify mirror equivalence before training.

## Explicitly Deferred Inputs

### Real timestamps and motion

The current E6 assembled tensor stores `feature`, `frame_mask`, and `length`, but not the original
per-frame `timestamps_ms`, hand scores, pose score, or world landmarks. True timestamp-aware
velocity therefore cannot be reconstructed authoritatively from `[96,258]`.

E6-2 will not substitute nominal FPS or repeat E3-B6 frame deltas. A later `E6-2B` motion test is
allowed only if:

1. E6-2A leaves a verified motion-specific error;
2. raw landmark/timestamp lineage is rebuilt without changing v3.0 artifacts; and
3. the proposal documents why it is materially different from E3-B6/B7.

### Face landmarks

No Face Landmarker is added. Pose nose, eye, ear, and shoulder anchors provide a cheap first test
of face-adjacent location. Dense face landmarks add detector cost and non-manual information that
the current five-sign hypothesis does not independently require.

## Model-Control Design

The control and candidate must differ only in input representation.

- Same raw clips, assignment manifest, labels, train/validation/stress/fresh/historical views.
- Same seeds `101`, `202`, `303`, epochs, optimizer, class weights, batching, masking, and checkpoint
  policy as the repaired-validation transfer control.
- Same four-block/64-channel causal TCN and five-class output.
- Same broad 236-class encoder source and verified source hash.

### Zero-extension warm start

Expanding the input normally prevents exact first-layer transfer and would confound representation
with lost pretraining. E6-2 must instead:

1. copy every v3.0 input-channel kernel into candidate channels `0:258`;
2. initialize all extra-channel kernels to exactly zero in the first causal convolution and first
   residual projection;
3. copy every same-shaped downstream encoder layer exactly;
4. copy the matched five-class head initialization between control and candidate for each seed;
5. prove candidate and control logits agree within `1e-6` before training.

The wider input adds exactly `47,616` trainable kernel parameters (`186 * 3 * 64` plus
`186 * 1 * 64`). Parameter count and training memory must be reported. No hidden-width increase is
allowed.

## Evaluation Views

| View | Role | Selection use |
|---|---|---|
| Repaired validation | Complete-signer checkpoint selection | Allowed |
| AppHear variant stress | Known development stress set | Diagnostic and preregistered secondary gate; not an unbiased test |
| Fresh AppHear test | Previously inspected held-out report | Final comparative report only |
| Historical ASL test | Regression report | Final comparative report only |

Because all test views have already influenced project decisions, E6-2 is a controlled engineering
comparison, not a production accuracy estimate. No production claim is permitted without a new
untouched signer test.

Required reports for every seed and aggregate:

- latest and selected-checkpoint top-1, macro-F1, per-class precision/recall/F1;
- confusion matrices for every view;
- `KNOW -> HELLO` and `SORRY` error counts;
- train/validation gap and seed standard deviation;
- hand-presence and pose-visibility strata;
- feature finite/range/mask checks;
- initialization parity, parameter count, extraction time, and estimated Android arithmetic cost.

## Go / No-Go Gates

All primary gates must pass:

1. Mean fresh top-1 `>= 0.9089` (at least `+0.02` over frozen `0.8889`).
2. Mean fresh `KNOW` recall `>= 0.70`; minimum-seed fresh `KNOW` recall `>= 0.60`.
3. Mean variant-stress `KNOW` recall `>= 0.30` and stress overall `>= 0.7273`.
4. No stable class (`GOOD`, `HELLO`, `SORRY`, `HAVE`) loses more than `0.03` mean fresh recall.
5. Historical mean top-1 is no more than `0.03` below `0.9630`.
6. Fresh accuracy seed standard deviation `<= 0.03`; no prediction collapse.
7. Initialization parity, finite-value, mirror-equivalence, padding, and schema checks all pass.

Interpretation rules:

- **Proceed:** all gates pass. Run one confirmatory feature-group ablation before schema promotion.
- **Modify once:** fresh/stress `KNOW` improves materially but one regression gate narrowly fails;
  perform error analysis before approving one bounded adjustment.
- **Stop E6-2:** `KNOW` does not improve, gains occur only on repaired validation, or stable classes
  regress. Keep v3.0 and do not run more handcrafted subsets.

E6-2 does not authorize E6-3 automatically. Its result must first be reviewed and recorded.

## Independent Validation Before Full Training

The future implementation package must pass a lightweight smoke test covering:

1. exact `[N,96,444]` shape and channel offsets;
2. no NaN/Inf and zero padding;
3. absent-hand and degenerate-palm behavior;
4. deterministic mirror-equivalent fixture behavior;
5. zero-extension weight-copy completeness;
6. pretraining/control logit parity within `1e-6`;
7. one forward pass, one training step, checkpoint save/reload;
8. all outputs confined to a new E6-2 artifact directory.

The user runs full three-seed training if the smoke package passes; the agent should not start a
long training process automatically.

## Android Feasibility And Parity

No Android implementation is approved. If the offline gate eventually passes:

- implement the feature builder under a new schema and feature flag;
- preserve v3.0 and current model assets as fallback;
- create Python/Kotlin golden-vector fixtures for normal, mirrored, one-hand, missing-hand,
  low-confidence pose, and padded sequences;
- require elementwise parity before model export or device shadow mode;
- measure p50/p95 feature-build and inference latency, memory, sustained FPS, battery, and thermal
  behavior on target devices.

The derived geometry itself is low-cost arithmetic relative to MediaPipe, but that is an
engineering estimate until device measurement exists.

## Risks And Failure Paths

| Risk | Probability / impact | Early warning | Mitigation | Failure path |
|---|---|---|---|---|
| Repeating E3 feature engineering | Medium / High | gains only match E3-B6 scale or appear only in train | exclude old delta blocks; one candidate only | stop E6-2 |
| Wider first layer overfits | Medium / High | train rises while fresh/stress falls | zero-extension initialization; fixed hidden width; multi-seed gates | retain v3.0 |
| Variant mismatch is semantic, not geometric | High / High | repaired val stays perfect but stress `KNOW` remains near zero | inspect errors after one run only | data/variant repair or defer `KNOW` |
| Landmark jitter corrupts angles/normals | Medium / High | extreme feature values or low-visibility regressions | epsilon guards, clipping, quality-stratified reports | remove failed group only after evidence |
| Mirror/side semantics drift | Medium / Critical | mirrored fixture differs | canonical-side fixture and golden vectors | block training/integration |
| Test reuse creates optimism | High / Critical | decisions tuned repeatedly to fresh/historical sets | label result diagnostic; require new signer test for production | no production claim |
| Train/serve mismatch | Medium / Critical | Python/Kotlin golden vectors differ | schema manifest and parity gate | no Android promotion |

## Protected Baseline And Rollback

Do not modify or overwrite:

- `pipeline/features/contract.py` v3.0 behavior;
- the current v3.0 extraction artifacts and assignment manifests;
- Android feature construction, model, vocabulary, configuration, MediaPipe asset, confirmation,
  sentence, camera, or navigation behavior;
- stable Git tag `stable-baseline-before-redesign`;
- frozen E6 v3.0 control runs.

All future E6-2 files must use new module names, schema identifiers, run directories, caches, and
model filenames. A failed E6-2 requires no rollback action because production remains untouched.

## Source-Of-Truth Files

- `product_core_data_readiness/collection_targets_v1/E6_V30_REPAIRED_VALIDATION_TRANSFER_RESULT.md`
- `E3_B6_FEATURE_AUGMENTATION_PLAN.md`
- `E3_B6_RESULT.md`
- `E3_B7_FEATURE_ABLATION_PLAN.md`
- `E3_B7_RESULT.md`
- `E6_1_CONSOLIDATED_EVIDENCE_DATASET_AUDIT.md`
- `../feature-schema.md`

## Related Context Files

- `README.md`
- `E6_PRODUCTION_RECOGNITION_ARCHITECTURE_PLAN.md`
- `FEATURE_SCHEMA_PLAN.md`
- `EXPERIMENT_MATRIX.md`
- `EVALUATION_AND_ACCEPTANCE_GATES.md`
- `ROLLBACK_AND_COMPATIBILITY_PLAN.md`
- `RISK_REGISTER.md`
- `OPEN_QUESTIONS.md`

## Architecture Decisions

- Preserve schema v3.0 as the immutable control.
- Run one compact geometry candidate, not another broad handcrafted subset search.
- Preserve broad encoder knowledge with zero-extension warm start.
- Use pose head anchors before adding dense face landmarks.
- Defer timestamp-aware motion until authoritative timestamps are available and a motion-specific
  failure justifies it.
- Stop after one no-go; do not restart the E3/E5 experiment loop.

## Assumptions

- Existing v3.0 normalized points and masks can produce the 444-channel candidate without new
  MediaPipe extraction.
- The repaired split package and source broad checkpoint remain readable and hash-consistent.
- The current five signs are sufficient to test the specific `KNOW` invariance hypothesis, not to
  estimate large-vocabulary production performance.

## Open Questions

- Does the AppHear `KNOW` performance represent a compatible ASL variant?
- Will pose eye/ear anchors be stable enough without dense face landmarks?
- Does the wider first layer need stronger regularization after the first controlled run?
- What new signer set can remain untouched for an eventual production claim?

## Next Required Action

E6-2 is closed. Retain v3.0 as primary and do not run more handcrafted geometry subsets. Architect
and duplicate-audit E6-3 before implementation; RGB, specialists, export, and Android remain
blocked.
