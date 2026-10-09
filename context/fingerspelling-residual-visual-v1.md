# Quality-gated residual visual research contract v1

Offline opt-in experiment only. Authoritative geometry remains Adapter.v1 `[T,405]`.
This contract does **not** replace `FingerspellingVisualFusion.v1`, its boolean masks,
or any existing geometry/perception contract. No Android implementation or parity claim.

## Input and source alignment

`apphear.fingerspelling.residual_visual_sequence.v1` packs `[T,1559]`:

| Columns, zero-based inclusive | Evidence |
|---|---|
| 0–404 | Unchanged Adapter.v1 geometry, timing, motion and missingness |
| 405–980 | Slot 0 frozen MobileNetV3Small embedding, 576 float32 values |
| 981–1556 | Slot 1 embedding, 576 float32 values |
| 1557–1558 | Slot 0/1 continuous visual quality scores, float32 `[0,1]` |

Geometry and appearance select the **same real raw observation indices**. Geometry
dt/motion are recomputed by the existing B2 temporal implementation. No interpolation,
carry, forward filling, horizontal flip or transcript-dependent crop choice.
Invalid/rejected/suppressed appearance is exactly zero, quality zero. A timestep remains
available to geometry even when neither crop is trusted. Padding has time-valid zero.

## Current-frame quality and appearance-only duplicates

Configuration: `model/config/fingerspelling_residual_visual_01.json`.
Require a finite, present usable ROI, accepted hand refiner, presence ≥0.90, ≥18 valid
joints, ≥15 proposal supports ≥0.10, ≥0.80 source intersection and ≥0.95 valid-joint
containment within the unchanged side×1.10 crop. Score equals presence × joint fraction
× supported-joint fraction × source intersection × containment. All gates must pass.
No full-body requirement and no temporal association state.

Rejection bits: 0 ROI invalid, 1 refiner not accepted, 2 presence, 3 joint coverage,
4 proposal support, 5 source intersection, 6 joint containment. Reasons can overlap.

Only when both slots pass: suppress the weaker appearance if ROI IoU≥0.75,
center distance/shorter side≤0.15, median common-joint distance/shorter side≤0.08,
side ratio≤1.25 and ≥18 common valid joints. Exact score ties retain slot0.
This is an obvious-duplicate heuristic, **not** proof of physical hand identity.
Retain both original geometry slots. Do not suppress distinct appearances from names
such as left/right. Rejected and duplicate decisions remain in the sidecar.

## Frozen B2 and residual

Load the actual B2 epoch076 checkpoint, pinned SHA-256
`64f425358ef30e21a4aca18795226854f7aa44a34c3bc3e54a8c06366cb61397`.
All B2 weights and its existing 64→28 CTC head are frozen.
Expose B2's final masked64-dimensional state. Disable Dropout in the private loaded
inference copy: Keras3 outer `training=True` otherwise re-enables it. This preserves
exact B2 inference, not B2 training behavior; the original checkpoint/source is unchanged.
Keep the head at one serialization scope to avoid nested shared-head reload failure.

Shared frozen appearance embeddings → trainable tanh576→16 projection → quality-weighted
slot pooling. A learned sigmoid gate sees frozen B2 state + pooled16. Tanh16→64 delta
starts with zero kernel/bias. Add `max_quality × gate × 0.25 × delta` to B2 state.
Gate starts at sigmoid(−2). Each residual coordinate is bounded by0.25, not its total norm.
Reuse the original frozen CTC head. Explicit `quality=0` selects the original B2 logits.
10,401 new trainable parameters; 203,517 total. Only six adapter variables receive updates.
Appearance CNN is precomputed/frozen; the actual B2 original is the direct comparator.

## Governance, evaluation and artifacts

Separate package `datasets/fingerspelling/residual_visual_01`, run
`runs/fingerspelling_residual_visual_01`. Existing1280 source/raw/geometry lineages
and official1024TRAIN/256DEV roles remain pinned; TEST sealed. Reuse old81 verified
embeddings only after identical crop/encoder/ROI/raw identity checks, then zero newly
untrusted slots. Other sources are decoded without rerunning Candidate01.

Receipts bind source/raw/geometry hashes, adapter/crop/quality/encoder identities,
source frame indices/timestamps, expanded ROIs, quality reasons/dedup, crop tensor hashes
and embedding hash. Metadata schema is checked before tensor reads. Source hashing and
upright decoder/frame checks precede new encoding. Reflection remains released pixels
as-is with the established attribution limitation. No new source acquisition.

Use unchanged B2 native/intermediate/phone views and CTC-feasibility fallback during TRAIN.
Adam0.001/clipnorm5, adapter-only L2 0.0001, maximum60epochs, minimum10, patience12,
meaningful stopping improvement0.002. Select earliest best balanced native/phone DEV CER
using B2's **already fixed** blank penalty0.5; also report raw penalty0. No decoder retuning.
Evaluate all256DEV and a fixed B2 TRAIN diagnostic set. Every epoch includes a direct
comparison to the frozen actual B2 reference, evaluated once on the same samples/views.

Before-result support rule: both fixed-penalty CERs lower, both aligned correct counts
higher, both substitution counts lower, mean correct/predicted precision not lower and
≥8/15 DEV signers improve balanced CER. Otherwise keep B2 and stop this visual direction.
No production accuracy claim, automatic promotion, next backbone or fusion sweep.

Android crop/encoder parity, export, CPU timing and commit isolation remain later gates.
