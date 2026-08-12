"""ST-GCN-class encoder for the S6 model swap (context/encoder-upgrade.md — candidate A).

TFLite-INT8-safe formulation, deliberately: the spatial graph convolution X' = A·X is implemented
as a FROZEN non-trainable Dense along the keypoint axis (converts to FULLY_CONNECTED — the best
supported INT8 op) instead of einsum/gather graph ops; temporal convolution is a plain Conv2D
(k,1) over the (T,V) plane. The whole graph uses only: slice/reshape/concat/permute, Dense,
Conv2D, BatchNorm (folds at conversion), ReLU, GlobalAvgPool, Softmax, tile.

FROZEN I/O CONTRACT (encoder-upgrade.md §3): input (1, T=96, 258) float32 -> output
(1, 96, num_classes) float32. This model is CLIP-level (non-causal over the buffered window); its
single clip posterior is TILED across the 96 output frames inside the graph so the Android
Recognizer/Confirmation/manifest run byte-identically unchanged.

ADJACENCY [CHECK-AT-BUILD]: `skeleton_adjacency()` below is a structurally-plausible placeholder
(hand chains + arm links) sufficient for the export smoke-test and early training. Before the real
training run, verify the edge list against the OpenHands/ST-GCN reference — do NOT assume the
placeholder is the published topology.
"""

from __future__ import annotations

import numpy as np

# 75 keypoints: 0-20 hand L, 21-41 hand R, 42-74 pose (33). Derived inside the graph from the
# v3.0 258 layout [handL 63, handR 63, pose 132] — the S4 features are untouched (parity).
NUM_KP = 75
_HAND_CHAIN = [  # MediaPipe hand topology (wrist->fingers), same for both hands
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),  # thumb
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),  # index
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),  # middle
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),  # ring
    (13, 17),
    (0, 17),
    (17, 18),
    (18, 19),
    (19, 20),  # pinky + palm edge
]
_POSE_EDGES = [  # upper-body subset of MediaPipe pose (33-kp indexing), offset +42 below
    (11, 12),
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),  # shoulders/elbows/wrists
    (11, 23),
    (12, 24),
    (23, 24),  # torso
    (0, 11),
    (0, 12),  # nose->shoulders (rough)
]
_CROSS = [(15 + 42, 0), (16 + 42, 21)]  # pose wristL->handL wrist, pose wristR->handR wrist
# Official MediaPipe PoseLandmarksConnections topology (33 landmarks). Kept opt-in so legacy
# checkpoints and graph construction remain reproducible.
_POSE_EDGES_MEDIAPIPE = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 7),
    (0, 4),
    (4, 5),
    (5, 6),
    (6, 8),
    (9, 10),
    (11, 12),
    (11, 13),
    (13, 15),
    (15, 17),
    (15, 19),
    (15, 21),
    (17, 19),
    (12, 14),
    (14, 16),
    (16, 18),
    (16, 20),
    (16, 22),
    (18, 20),
    (11, 23),
    (12, 24),
    (23, 24),
    (23, 25),
    (24, 26),
    (25, 27),
    (26, 28),
    (27, 29),
    (28, 30),
    (29, 31),
    (30, 32),
    (27, 31),
    (28, 32),
]


def skeleton_adjacency(pose_topology: str = "legacy") -> np.ndarray:
    """Return normalized symmetric adjacency over the 75 v3.0 keypoints."""
    if pose_topology not in {"legacy", "mediapipe"}:
        raise ValueError(f"unsupported pose topology: {pose_topology}")
    pose_edges = _POSE_EDGES if pose_topology == "legacy" else _POSE_EDGES_MEDIAPIPE
    a = np.eye(NUM_KP, dtype=np.float32)
    edges = (
        [(i, j) for i, j in _HAND_CHAIN]
        + [(i + 21, j + 21) for i, j in _HAND_CHAIN]
        + [(i + 42, j + 42) for i, j in pose_edges]
        + _CROSS
    )
    for i, j in edges:
        a[i, j] = 1.0
        a[j, i] = 1.0
    d = a.sum(axis=1)
    dinv = 1.0 / np.sqrt(np.maximum(d, 1e-6))
    return (a * dinv[None, :] * dinv[:, None]).astype(np.float32)


# Upper-body 51-keypoint subset: both hands complete (0..41) + pose nose, shoulders, elbows,
# wrists, hips. Drops face-outline/leg keypoints (irrelevant to ASL). ~2x training/inference
# speedup vs all 75 (measured 2026-07-07: 46.6 -> 24.0 min/epoch with early strides).
UPPER51 = tuple(range(42)) + (
    42 + 0,
    42 + 11,
    42 + 12,
    42 + 13,
    42 + 14,
    42 + 15,
    42 + 16,
    42 + 23,
    42 + 24,
)


def build_stgcn(
    time_window: int = 96,
    feature_dim: int = 258,
    num_classes: int = 236,
    channels: tuple = (64, 64, 64, 64, 128, 128, 128, 256, 256, 256),
    temporal_kernel: int = 9,
    dropout: float = 0.3,
    adjacency: np.ndarray | None = None,
    strides: dict[int, int] | None = None,
    keypoint_subset: tuple[int, ...] | None = None,
    mask_padded_frames: bool = False,
    infer_hand_presence: bool = False,
    pose_topology: str = "legacy",
):
    """ST-GCN satisfying the frozen I/O contract. `strides` maps block idx -> temporal stride
    (default {4:2, 7:2}; candidate A uses EARLY strides {0:2, 4:2} for ~2x speed). An optional
    `keypoint_subset` gathers keypoints INSIDE the graph (input stays the 258 contract — no S4
    change); its adjacency is the sliced+renormalized skeleton."""
    import tensorflow as tf
    from tensorflow.keras import layers

    a = adjacency if adjacency is not None else skeleton_adjacency(pose_topology)
    assert a.shape == (NUM_KP, NUM_KP)
    strides = strides if strides is not None else {4: 2, 7: 2}
    if keypoint_subset is not None:
        keep = list(keypoint_subset)
        a = a[np.ix_(keep, keep)].astype(np.float32)
        d = np.maximum(a.sum(axis=1), 1e-6)
        dinv = 1.0 / np.sqrt(d)
        a = (a * dinv[None, :] * dinv[:, None]).astype(np.float32)
        num_kp = len(keep)
    else:
        keep = None
        num_kp = NUM_KP

    from keras import ops  # Keras 3 native ops — serialize WITHOUT Lambda layers (safe_mode-proof)

    inp = layers.Input(shape=(time_window, feature_dim), name="features")

    # 258 -> (T, 75, 4): hands get a constant 1.0 presence channel to match pose's 4th (visibility).
    # NO Lambda layers anywhere (Keras refuses to deserialize python-lambda Lambdas by default,
    # which broke checkpoint resume) — direct KerasTensor slicing + keras.ops only.
    hands = layers.Reshape((time_window, 42, 3))(inp[..., :126])
    pose = layers.Reshape((time_window, 33, 4))(inp[..., 126:])
    frame_mask = ops.any(ops.not_equal(inp, 0.0), axis=-1)
    if infer_hand_presence:
        left_present = ops.any(ops.not_equal(hands[:, :, :21, :], 0.0), axis=(2, 3))
        right_present = ops.any(ops.not_equal(hands[:, :, 21:, :], 0.0), axis=(2, 3))
        left_presence = ops.cast(left_present, hands.dtype)[:, :, None, None]
        right_presence = ops.cast(right_present, hands.dtype)[:, :, None, None]
        presence = ops.concatenate(
            [
                ops.repeat(left_presence, 21, axis=2),
                ops.repeat(right_presence, 21, axis=2),
            ],
            axis=2,
        )
    else:
        presence = ops.ones_like(hands[..., :1])
    hands4 = layers.Concatenate(axis=-1)([hands, presence])
    x = layers.Concatenate(axis=2, name="kp_concat")([hands4, pose])  # (T, 75, 4)
    if keep is not None:
        x = ops.take(x, list(keep), axis=2)  # (T, V', 4)

    def graph_dense(name: str):
        """Frozen A^T as a Dense along the keypoint axis: (T,C,V) @ (V,V) -> FULLY_CONNECTED."""
        d = layers.Dense(num_kp, use_bias=False, trainable=False, name=name)
        return d

    def stgcn_block(x, cin: int, cout: int, stride: int, idx: int):
        # spatial: permute (T,V,C)->(T,C,V), apply frozen adjacency, permute back
        h = layers.Permute((1, 3, 2), name=f"b{idx}_tocv")(x)
        gd = graph_dense(f"b{idx}_adj")
        h = gd(h)
        h = layers.Permute((1, 3, 2), name=f"b{idx}_tovc")(h)
        # channel mixing (the trainable W of A·X·W)
        h = layers.Conv2D(cout, (1, 1), padding="same", name=f"b{idx}_w")(h)
        h = layers.BatchNormalization(name=f"b{idx}_bn1")(h)
        h = layers.ReLU(name=f"b{idx}_relu1")(h)
        # temporal conv over T (keypoint axis untouched)
        h = layers.Conv2D(
            cout, (temporal_kernel, 1), strides=(stride, 1), padding="same", name=f"b{idx}_tconv"
        )(h)
        h = layers.BatchNormalization(name=f"b{idx}_bn2")(h)
        h = layers.Dropout(dropout, name=f"b{idx}_drop")(h)
        # residual
        if cin != cout or stride != 1:
            r = layers.Conv2D(cout, (1, 1), strides=(stride, 1), name=f"b{idx}_res")(x)
            r = layers.BatchNormalization(name=f"b{idx}_resbn")(r)
        else:
            r = x
        h = layers.Add(name=f"b{idx}_add")([h, r])
        return layers.ReLU(name=f"b{idx}_relu2")(h)

    # to 4D (T, V, C) image-like tensor for Conv2D
    prev = 4
    for i, c in enumerate(channels):
        stride = strides.get(i, 1)
        x = stgcn_block(x, prev, c, stride, i)
        if stride > 1:
            frame_mask = layers.MaxPooling1D(
                pool_size=stride, strides=stride, padding="same", name=f"b{i}_mask_pool"
            )(ops.cast(frame_mask[:, :, None], "float32"))
            frame_mask = ops.greater(frame_mask[..., 0], 0.0)
        prev = c

    # clip head -> tiled per-frame output (frozen contract)
    if mask_padded_frames:
        weights = ops.cast(frame_mask[:, :, None, None], x.dtype)
        numerator = ops.sum(x * weights, axis=(1, 2))
        denominator = ops.maximum(
            ops.sum(weights, axis=(1, 2)) * ops.cast(ops.shape(x)[2], x.dtype),
            ops.cast(1.0, x.dtype),
        )
        x = numerator / denominator
    else:
        x = layers.GlobalAveragePooling2D(name="gap")(x)
    x = layers.Dropout(dropout, name="head_drop")(x)
    logits = layers.Dense(num_classes, name="head")(x)
    probs = layers.Softmax(name="probs")(logits)
    tiled = layers.RepeatVector(time_window, name="tile_contract")(probs)  # (T, num_classes)

    model = tf.keras.Model(inp, tiled, name="stgcn_clip")
    # install the frozen adjacency into every graph_dense layer (kernel = A^T)
    for lyr in model.layers:
        if lyr.name.endswith("_adj"):
            lyr.set_weights([a.T])
    return model


if __name__ == "__main__":
    m = build_stgcn()
    m.summary(line_length=110)
    print(f"params: {m.count_params():,}")
