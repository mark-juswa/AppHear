"""Compact full-sequence TCN. Separate identity; no protected model changes."""

from __future__ import annotations

from typing import Any

from pipeline.fingerspelling.adapter import VERSION, WIDTH
from pipeline.fingerspelling.expanded_training import read_json
from pipeline.fingerspelling.sequence_manifest import REPO

CONFIG = REPO / "model/config/fingerspelling_sequence_v2_01.json"


def configuration() -> dict[str, Any]:
    p = read_json(CONFIG)
    if (
        p["schema_version"] != "apphear.fingerspelling.sequence_encoder_v2.v1"
        or p["adapter_version"] != VERSION
        or p["feature_width"] != WIDTH
        or p["padding"] != "same"
        or p["temporal_stride"] != 1
        or p["logits"] != 28
        or p["blank_index"] != 27
        or p["space_index"] != 26
        or not p["mask_each_convolution"]
        or p["final_decoder"]
        != {"blank_index": 27, "blank_penalty": 0.5, "beam_width": 10, "top_paths": 1}
        or p["test_access"] != "SEALED"
    ):
        raise ValueError("[sequence-v2/config] Frozen contract mismatch")
    return p


def receptive_field(config: dict[str, Any]) -> int:
    return int(1 + 2 * (config["kernel_size"] - 1) * sum(config["dilations"]))


def build_model(tf: Any, config: dict[str, Any]) -> Any:
    """SAME stride-1 context. Padding is re-masked after every biased operation.

    A time-valid mask means an actual observation, including a hand-missing one.
    Hand missingness remains encoded by Adapter v1; it is never padding.
    LayerNorm is per timestep, never across the time axis.
    """
    features = tf.keras.Input((None, WIDTH), name="features")
    mask = tf.keras.Input((None, 1), name="time_valid")
    x = tf.keras.layers.Multiply(name="input_mask")([features, mask])
    for i, dilation in enumerate(config["dilations"]):
        residual = x
        for j in range(2):
            tag = f"v2_block{i}_{j}"
            x = tf.keras.layers.Conv1D(
                config["channels"],
                config["kernel_size"],
                dilation_rate=dilation,
                padding="same",
                name=tag + "_conv",
            )(x)
            x = tf.keras.layers.LayerNormalization(name=tag + "_norm")(x)
            x = tf.keras.layers.ReLU(name=tag + "_relu")(x)
            x = tf.keras.layers.Dropout(
                config["dropout"], seed=config["seed"] + i * 2 + j, name=tag + "_dropout"
            )(x)
            x = tf.keras.layers.Multiply(name=tag + "_mask")([x, mask])
        if residual.shape[-1] != config["channels"]:
            residual = tf.keras.layers.Conv1D(config["channels"], 1, name="v2_input_projection")(
                residual
            )
        x = tf.keras.layers.Add(name=f"v2_block{i}_add")([x, residual])
        x = tf.keras.layers.Multiply(name=f"v2_block{i}_mask")([x, mask])
    logits = tf.keras.layers.Dense(28, name="character_logits")(x)
    logits = tf.keras.layers.Multiply(name="output_mask")([logits, mask])
    return tf.keras.Model([features, mask], logits, name="fingerspell_sequence_encoder_v2_01")
