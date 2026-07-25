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
    (0, 1), (1, 2), (2, 3), (3, 4),          # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),          # index
    (5, 9), (9, 10), (10, 11), (11, 12),     # middle
    (9, 13), (13, 14), (14, 15), (15, 16),   # ring
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),  # pinky + palm edge
]
_POSE_EDGES = [  # upper-body subset of MediaPipe pose (33-kp indexing), offset +42 below
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),  # shoulders/elbows/wrists
    (11, 23), (12, 24), (23, 24),                      # torso
    (0, 11), (0, 12),                                  # nose->shoulders (rough)
]
_CROSS = [(15 + 42, 0), (16 + 42, 21)]  # pose wristL->handL wrist, pose wristR->handR wrist


def skeleton_adjacency() -> np.ndarray:
    """Normalized adjacency (A+I, symmetric, D^-1/2 (A+I) D^-1/2) over the 75 keypoints."""
    a = np.eye(NUM_KP, dtype=np.float32)
    edges = (
        [(i, j) for i, j in _HAND_CHAIN]
        + [(i + 21, j + 21) for i, j in _HAND_CHAIN]
        + [(i + 42, j + 42) for i, j in _POSE_EDGES]
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
UPPER51 = tuple(range(42)) + (42 + 0, 42 + 11, 42 + 12, 42 + 13, 42 + 14, 42 + 15, 42 + 16,
                              42 + 23, 42 + 24)


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
):
    """ST-GCN satisfying the frozen I/O contract. `strides` maps block idx -> temporal stride
    (default {4:2, 7:2}; candidate A uses EARLY strides {0:2, 4:2} for ~2x speed). An optional
    `keypoint_subset` gathers keypoints INSIDE the graph (input stays the 258 contract — no S4
    change); its adjacency is the sliced+renormalized skeleton."""
    import tensorflow as tf
    from tensorflow.keras import layers

    a = adjacency if adjacency is not None else skeleton_adjacency()
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
    ones = ops.ones_like(hands[..., :1])
    hands4 = layers.Concatenate(axis=-1)([hands, ones])
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
        h = layers.Conv2D(cout, (temporal_kernel, 1), strides=(stride, 1), padding="same",
                          name=f"b{idx}_tconv")(h)
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
        x = stgcn_block(x, prev, c, strides.get(i, 1), i)
        prev = c

    # clip head -> tiled per-frame output (frozen contract)
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
