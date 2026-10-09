"""Three fixed input ablations; frozen geometry and same-observation appearance."""

from __future__ import annotations

from typing import Any

import numpy as np

from model import fingerspelling_baseline2 as b2
from model.fingerspelling_ctc import ctc_loss
from model.fingerspelling_temporal_execution import TemporalFeatureCache
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import verify_raw
from pipeline.fingerspelling.temporal_views import selected_indices
from pipeline.fingerspelling.visual_crop import config
from pipeline.fingerspelling.visual_package import load_visual

ARMS = ["geometry", "appearance", "combined"]
PACKED_WIDTH = 405 + 2 * 576 + 2


class FusionCache:
    """RAM views are real selected raw indices; invalid embeddings never carried."""

    def __init__(self, arm: str = "combined") -> None:
        if arm not in ARMS:
            raise ValueError("[visual/cache] Unknown ablation")
        self.arm = arm
        self.policy = b2.policy()[0]
        self.geometry = TemporalFeatureCache(self.policy)
        self.visual: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self.positions: dict[tuple[str, str], np.ndarray] = {}
        self.arrays: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = {}

    @property
    def bytes(self) -> int:
        return (
            self.geometry.bytes
            + sum(x.nbytes + y.nbytes for x, y in self.arrays.values())
            + sum(x.nbytes + m.nbytes for x, m in self.visual.values())
        )

    def load(self, rec: dict[str, Any], view: str) -> tuple[np.ndarray, np.ndarray]:
        key, sid = (rec["sample_id"], view), rec["sample_id"]
        if key not in self.arrays:
            self.geometry.register(rec)
            geometry, targets = self.geometry.load(rec, view)
            if sid not in self.visual:
                self.visual[sid] = load_visual(rec)
                raw = verify_raw(
                    REPO / rec["raw_path"],
                    REPO / rec["raw_receipt_path"],
                    rec,
                    rec["source_sha256"],
                )
                for v in self.policy["temporal_views"]:
                    self.positions[(sid, v)] = selected_indices(raw, v, self.policy)
            selected = self.positions[key]
            appearance, masks = self.visual[sid]
            if len(geometry) != len(selected):
                raise ValueError("[visual/cache] Geometry/appearance temporal misalignment")
            g = geometry if self.arm != "appearance" else np.zeros_like(geometry)
            if self.arm == "appearance":
                g[:, :2] = geometry[:, :2]  # Common dt/validity, not hand geometry.
            a = (
                appearance[selected].reshape(len(selected), -1)
                if self.arm != "geometry"
                else np.zeros((len(selected), 2 * config()["embedding_width"]), np.float32)
            )
            m = (
                masks[selected].astype(np.float32)
                if self.arm != "geometry"
                else np.zeros((len(selected), 2), np.float32)
            )
            packed = np.concatenate([g, a, m], axis=1)
            if packed.shape != (len(selected), PACKED_WIDTH) or not np.isfinite(packed).all():
                raise ValueError("[visual/cache] Invalid compound input")
            packed.setflags(write=False)
            self.arrays[key] = packed, targets
        return self.arrays[key]

    def batch(self, rows: list[dict[str, Any]], view: str) -> tuple[np.ndarray, ...]:
        arrays = [self.load(r, view) for r in rows]
        lengths = np.array([len(x) for x, _ in arrays], np.int32)
        target_lengths = np.array([len(y) for _, y in arrays], np.int32)
        x = np.zeros((len(rows), int(lengths.max()), PACKED_WIDTH), np.float32)
        mask = np.zeros((*x.shape[:2], 1), np.float32)
        y = np.zeros((len(rows), int(target_lengths.max())), np.int32)
        for i, (a, b) in enumerate(arrays):
            x[i, : len(a)], mask[i, : len(a)], y[i, : len(b)] = a, 1, b
        return x, mask, y, lengths, target_lengths

    def training_batch(
        self, rows: list[dict[str, Any]], epoch: int
    ) -> tuple[tuple[np.ndarray, ...], list[dict[str, Any]]]:
        tensors, choices = self.geometry.training_batch(rows, epoch)
        _, mask, y, lengths, target_lengths = tensors
        x = np.zeros((len(rows), mask.shape[1], PACKED_WIDTH), np.float32)
        for i, (r, choice) in enumerate(zip(rows, choices, strict=True)):
            a, _ = self.load(r, choice["actual"])
            if len(a) != lengths[i]:
                raise ValueError("[visual/cache] Mixed-view length mismatch")
            x[i, : len(a)] = a
        return (x, mask, y, lengths, target_lengths), choices


def build_fusion_model(tf: Any) -> Any:
    cfg = config()
    _, base = b2.policy()
    features = tf.keras.Input((None, PACKED_WIDTH), name="geometry_appearance_validity")
    time_valid = tf.keras.Input((None, 1), name="time_valid")
    # Input slices are schema-ordered; serializable standard Keras operations only.
    geometry = features[:, :, :405]
    geom = tf.keras.layers.Dense(
        cfg["geometry_projection"], activation="relu", name="geometry_projection"
    )(geometry)
    geom = tf.keras.layers.Multiply()([geom, time_valid])
    shared = tf.keras.layers.Dense(
        cfg["slot_appearance_projection"],
        activation="relu",
        name="shared_appearance_projection",
    )
    projected = []
    for slot in range(2):
        left = 405 + slot * cfg["embedding_width"]
        pixels = features[:, :, left : left + cfg["embedding_width"]]
        validity = features[:, :, -2 + slot : -1] if slot == 0 else features[:, :, -1:]
        branch = tf.keras.layers.Multiply()([shared(pixels), validity, time_valid])
        projected.append(branch)
    joined = tf.keras.layers.Concatenate()([geom, *projected, features[:, :, -2:]])
    x = tf.keras.layers.Dense(
        cfg["fused_channels"], activation="relu", name="fusion_projection"
    )(joined)
    x = tf.keras.layers.Multiply()([x, time_valid])
    for i, dilation in enumerate(base["dilations"]):
        residual = x
        for j in range(2):
            x = tf.keras.layers.Conv1D(
                base["channels"],
                base["kernel_size"],
                dilation_rate=dilation,
                padding="causal",
                name=f"block{i}_conv{j}",
            )(x)
            x = tf.keras.layers.LayerNormalization(name=f"block{i}_norm{j}")(x)
            x = tf.keras.layers.ReLU()(x)
            x = tf.keras.layers.Dropout(base["dropout"], seed=base["seed"] + i * 2 + j)(x)
        x = tf.keras.layers.Add()([x, residual])
        x = tf.keras.layers.Multiply()([x, time_valid])
    logits = tf.keras.layers.Dense(28, name="character_logits")(x)
    logits = tf.keras.layers.Multiply()([logits, time_valid])
    return tf.keras.Model(
        [features, time_valid], logits, name="fingerspelling_visual_fusion_v1"
    )


class FusionSteps:
    """Existing CTC loss/graph-update protocol at the versioned compound input width."""

    def __init__(self, tf: Any, model: Any, optimizer: Any = None) -> None:
        inputs = [
            tf.TensorSpec([None, None, PACKED_WIDTH], tf.float32),
            tf.TensorSpec([None, None, 1], tf.float32),
        ]
        targets = [
            tf.TensorSpec([None, None], tf.int32),
            tf.TensorSpec([None], tf.int32),
            tf.TensorSpec([None], tf.int32),
        ]

        @tf.function(input_signature=inputs, jit_compile=False)
        def infer(x: Any, mask: Any) -> Any:
            return model([x, mask], training=False)

        self.infer = infer
        self.update = None
        if optimizer is not None:

            @tf.function(input_signature=inputs + targets, jit_compile=False)
            def update(x: Any, mask: Any, y: Any, lengths: Any, target_lengths: Any) -> Any:
                with tf.GradientTape() as tape:
                    loss = ctc_loss(
                        tf, model([x, mask], training=True), y, lengths, target_lengths
                    )
                gradients = tape.gradient(loss, model.trainable_variables)
                for value in gradients:
                    if value is None:
                        raise ValueError("[visual/train] Missing gradient")
                    tf.debugging.assert_all_finite(value, "[visual/train] Nonfinite gradient")
                optimizer.apply_gradients(
                    zip(gradients, model.trainable_variables, strict=True)
                )
                return loss

            self.update = update
