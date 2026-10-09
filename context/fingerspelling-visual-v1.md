# Fingerspelling visual evidence v1 — offline research only

Separate opt-in research package. WORD, Candidate01, raw-v1, geometry Adapter.v1
`[T,405]`, B2 temporal views, official1024TRAIN/256DEV roles and TEST sealing remain
unchanged. Config: `pipeline/config/fingerspelling_visual_v1.json`.

## Current-frame crop

HandCropExtractor.v1 consumes the same upright uint8RGB frame as the raw observation,
source width/height and both proposal-present/ROI slots. Source-pixel ROI is
`[center_x,center_y,side]`. Slots may describe the same physical hand. No dominant-hand,
anatomical identity, association, second detector, reflection or temporal fill.

Validity: present proposal, finite ROI, side≥8pixels, positive source dimensions,
expanded-square/source intersection≥0.5. Expand side by float32 1.10, keep center.
Refiner acceptance is independent; proposal crops can survive landmark failure.
Validity is availability, not hand/letter correctness or confidence.

128×128 axis-aligned square: for output integer `(u,v)` in0:127,
`x = cx - side/2 + float32(u)/127 * side`, similarly y. Arithmetic/bilinear neighbor
weight order reuse frozen Candidate01 `_sample_rgb`; outside-source neighbors zeroRGB.
Normalize float32 sampledRGB `/127.5 - 1`, no intermediate rounding. A valid crop's
padded border is -1; invalid entire crop is zero and is never encoded. No augmentation.

Reuse frozen upright decoder. Compare each frame index/timestamp(0.001ms tolerance),
dimension/orientation to existing raw. Historical receipts pin orientation through
SHA-verified source probe; new receipts store it directly. Reflection remains
USE_RELEASED_PIXELS_AS_IS / STRONGLY_SUPPORTED_UNMIRRORED_NOT_FULLY_ATTRIBUTED.

## Appearance encoder

HandAppearanceEncoder.v1: frozen Keras MobileNetV3Small alpha1, no top, global-average
pool,128input, external normalization above, internal preprocessing disabled. Already
cached ImageNet weights copied locally, MD5/SHA pinned. No automatic download or
TRAIN/DEV fine-tuning. Inference BatchNorm/dropout, TF/Keras versions and implementation
hash are identity fields. Output576float32/slot; invalid embeddings zero. This is a
generic appearance prior, not a letter recognizer.

## Separate archive / lineage

apphear.fingerspelling.visual_sequence.v1 contains embeddings[T,2,576], crop_valid[T,2],
expanded_rois[T,2,3], crop_sha256[T,2,32] over normalized crop tensor, raw-identical frame
indices/timestamps and metadata. Metadata pins source/raw/geometry hashes, orientation,
decoder version, crop/config/encoder/weights/package identities and crop QA summary.

apphear.fingerspelling.visual_receipt.v1 pins artifact hash, parent source/raw/raw-receipt/
geometry hashes, official signer/role and metadata. Loader checks schema/identities,
hashes, shapes, chronology, finite values, proposal support and zero invalid embedding/
ROI/hash. Source size/MD5/SHA checked before preparation. No geometry archive rewritten.
Only governed TRAIN/DEV rows allowed; TEST sealed.

## Fusion ordering

FingerspellingVisualFusion.v1 compound `[T,1559]`, float32:

| Half-open columns | Evidence |
|---|---|
|0:405|Unchanged Adapter.v1, derived after temporal selection|
|405:981|Slot0 appearance576 at exactly selected raw frame|
|981:1557|Slot1 appearance576 at exactly selected raw frame|
|1557:1559|Slot0/slot1 crop-valid bits|

Separate time-valid[T,1] marks padding. Real-index native/intermediate/phone selection;
geometry dt/motion recomputed by original adapter, appearance selected at same indices.
No fake RGB/embeddings, carry or timestep removal for missing crops. CTC feasibility/
fallback/retention follow B2.

Geometry405→Dense64ReLU; shared slot576→Dense32ReLU, **then** multiply by slot/time masks
including bias masking. Concatenate geometry64+twoappearance32+valid2→Dense64ReLU.
B2-size TCN: four residual blocks, two64-channel kernel3 convs/block, dilation1/2/4/8,
LayerNorm/ReLU/dropout0.1, stride1, receptive field61observations. Masks after fusion/
blocks/logits.28CTC logits A–Z/SPACE/blank. No language model.

One fixed gate shares architecture/seed/order/views/optimizer across geometry-only,
appearance-only and combined. Geometry-only zeros appearance/validity. Appearance-only
zeros hand/body geometry but retains common adapter columns0:2(real dt/dt-valid).
Combined retains both. Common timing avoids denying appearance cadence evidence.
Adapter405 is unchanged.

## Future Android seam / limits

Candidate01FrameAnalyzer prepared current RGB and ROI exist before
`session.consume(observation)` / `image.close()`. Future explicit FINGERSPELL owner can
crop here without second Candidate01/camera. No connection now. Existing224/[0,1]
hand-refiner crop buffer is not visual128/[-1,1] automatically. Later port/parity-test
sampler and encoder. Python tests are not Android parity. TFLite export, current camera
orientation/alignment, streaming state, memory and CPU p50/p95 remain future gates.
Geometry's6.23Hz profile does not prove fusion throughput. Future exclusive mode must
prevent WORD internal commits, not merely hide UI. No production rollout enabled.
