"""Causal Temporal Convolutional Network for isolated ASL recognition (Phase 0).

Causal from day one so the ENCODER transfers unchanged to Phase 1 (streaming) and Phase 2
(CTC) — only the head changes (docs/03). Input is the v3.0 feature tensor (T, 258)."""

from __future__ import annotations

from typing import Any

from tensorflow.keras import Model, layers


def _tcn_block(x: Any, channels: int, kernel: int, dilation: int, dropout: float, name: str) -> Any:
    """Residual dilated causal block: two causal convs + LayerNorm/ReLU/Dropout + skip."""
    residual = x
    y = layers.Conv1D(
        channels, kernel, padding="causal", dilation_rate=dilation, name=f"{name}_conv1"
    )(x)
    y = layers.LayerNormalization(name=f"{name}_ln1")(y)
    y = layers.Activation("relu", name=f"{name}_relu1")(y)
    y = layers.Dropout(dropout, name=f"{name}_do1")(y)
    y = layers.Conv1D(
        channels, kernel, padding="causal", dilation_rate=dilation, name=f"{name}_conv2"
    )(y)
    y = layers.LayerNormalization(name=f"{name}_ln2")(y)
    y = layers.Activation("relu", name=f"{name}_relu2")(y)
    y = layers.Dropout(dropout, name=f"{name}_do2")(y)
    if residual.shape[-1] != channels:  # match channels on the skip path
        residual = layers.Conv1D(channels, 1, padding="same", name=f"{name}_proj")(residual)
    return layers.Add(name=f"{name}_add")([residual, y])


def build_encoder(
    input_len: int,
    feat_dim: int,
    blocks: int,
    channels: int,
    dilations: tuple[int, ...],
    kernel: int,
    dropout: float,
) -> Model:
    """Causal TCN encoder → per-frame embeddings (input_len, channels). Reused across phases."""
    inp = layers.Input(shape=(input_len, feat_dim), name="features")
    x = inp
    for i in range(blocks):
        x = _tcn_block(x, channels, kernel, dilations[i % len(dilations)], dropout, f"tcn{i}")
    return Model(inp, x, name="causal_tcn_encoder")


def build_classifier(
    input_len: int,
    feat_dim: int,
    num_classes: int,
    *,
    blocks: int = 4,
    channels: int = 64,
    dilations: tuple[int, ...] = (1, 2, 4, 8),
    kernel: int = 3,
    dropout: float = 0.1,
) -> Model:
    """Phase-0 isolated classifier: encoder → global-average-pool → softmax over the vocab."""
    encoder = build_encoder(input_len, feat_dim, blocks, channels, dilations, kernel, dropout)
    x = layers.GlobalAveragePooling1D(name="pool")(encoder.output)
    out = layers.Dense(num_classes, activation="softmax", name="logits")(x)
    return Model(encoder.input, out, name="tcn_isolated_classifier")


def build_streaming_classifier(
    input_len: int,
    feat_dim: int,
    num_classes: int,
    *,
    blocks: int = 4,
    channels: int = 64,
    dilations: tuple[int, ...] = (1, 2, 4, 8),
    kernel: int = 3,
    dropout: float = 0.1,
) -> Model:
    """Phase-1 streaming head: same causal encoder, but a PER-FRAME softmax (Dense over the last
    axis of the (T, channels) sequence) → output (T, num_classes). The encoder is shared with
    the isolated classifier so its weights can be warm-started (matching layer names)."""
    encoder = build_encoder(input_len, feat_dim, blocks, channels, dilations, kernel, dropout)
    out = layers.Dense(num_classes, activation="softmax", name="logits_perframe")(encoder.output)
    return Model(encoder.input, out, name="tcn_streaming_classifier")
