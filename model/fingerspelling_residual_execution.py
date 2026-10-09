"""Frozen actual B2, bounded current-frame appearance correction, unchanged CTC head."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from model.fingerspelling_ctc import ctc_loss
from model.fingerspelling_visual_execution import PACKED_WIDTH, FusionCache
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.residual_visual_package import load
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import verify_raw
from pipeline.fingerspelling.temporal_views import selected_indices
from pipeline.fingerspelling.visual_quality import config


def base_model(tf: Any) -> Any:
    cfg = config()
    path = REPO / cfg["base_checkpoint"]
    if sha256(path) != cfg["base_checkpoint_sha256"]:
        raise ValueError("[residual/model] Frozen B2 checkpoint changed")
    model = tf.keras.models.load_model(path, compile=False)
    model.trainable = False
    return model


def frozen_digest(model: Any) -> str:
    digest = hashlib.sha256()
    for value in model.non_trainable_variables:
        digest.update(value.numpy().tobytes())
    return digest.hexdigest()


class ResidualCache(FusionCache):
    """Reuse batch/view selection, replacing only the appearance sidecar reader."""

    def load(self, rec: dict[str, Any], view: str) -> tuple[np.ndarray, np.ndarray]:
        key, sid = (rec["sample_id"], view), rec["sample_id"]
        if key not in self.arrays:
            self.geometry.register(rec)
            geometry, targets = self.geometry.load(rec, view)
            if sid not in self.visual:
                self.visual[sid] = load(rec)
                raw = verify_raw(
                    REPO / rec["raw_path"],
                    REPO / rec["raw_receipt_path"],
                    rec,
                    rec["source_sha256"],
                )
                for v in self.policy["temporal_views"]:
                    self.positions[(sid, v)] = selected_indices(raw, v, self.policy)
            selected = self.positions[key]
            emb, q = self.visual[sid]
            if len(geometry) != len(selected):
                raise ValueError("[residual/cache] Appearance/geometry misalignment")
            packed = np.concatenate(
                [geometry, emb[selected].reshape(len(selected), 1152), q[selected]],
                axis=1,
            )
            if (
                packed.shape != (len(selected), PACKED_WIDTH)
                or not np.isfinite(packed).all()
            ):
                raise ValueError("[residual/cache] Invalid compound input")
            packed.setflags(write=False)
            self.arrays[key] = packed, targets
        return self.arrays[key]


def build_model(tf: Any) -> Any:
    cfg = config()
    b = base_model(tf)
    # Keras 3 propagates an outer training=True into nested functional nodes.
    # This private inference copy disables Dropout structurally; inference math
    # and every checkpoint weight remain exactly B2. The original file is untouched.
    for layer in b.layers:
        if isinstance(layer, tf.keras.layers.Dropout):
            layer.rate = 0.0
    head = b.get_layer("character_logits")
    # Keep the head at one serialization scope. Sharing the same Dense inside
    # and outside a nested model loses its weights in Keras .keras reload.
    frozen = tf.keras.Model(b.inputs, head.input, name="frozen_b2_representation")
    frozen.trainable = False
    x = tf.keras.Input((None, PACKED_WIDTH), name="geometry_appearance_quality")
    mask = tf.keras.Input((None, 1), name="time_valid")
    # Freezing weights alone does not disable Dropout: inference is explicit here.
    h = frozen([x[:, :, :405], mask], training=False)
    original = head(h) * mask
    shared = tf.keras.layers.Dense(
        cfg["projection_width"],
        activation="tanh",
        kernel_regularizer=tf.keras.regularizers.L2(cfg["l2"]),
        name="visual_projection",
    )
    q0, q1 = x[:, :, -2:-1] * mask, x[:, :, -1:] * mask
    e0, e1 = shared(x[:, :, 405:981]), shared(x[:, :, 981:1557])
    ops = tf.keras.ops
    total = q0 + q1
    pooled = (e0 * q0 + e1 * q1) / ops.maximum(total, 1e-6)
    confidence = ops.maximum(q0, q1)
    joined = tf.keras.layers.Concatenate()([h, pooled])
    gate = tf.keras.layers.Dense(
        1,
        activation="sigmoid",
        kernel_initializer="zeros",
        bias_initializer=tf.keras.initializers.Constant(cfg["gate_initial_bias"]),
        name="learned_visual_gate",
    )(joined)
    delta = tf.keras.layers.Dense(
        64,
        activation="tanh",
        kernel_initializer="zeros",
        bias_initializer="zeros",
        kernel_regularizer=tf.keras.regularizers.L2(cfg["l2"]),
        name="visual_delta",
    )(pooled)
    correction = confidence * gate * delta * cfg["maximum_residual_magnitude"]
    logits = head(h + correction) * mask
    # Guaranteed fallback at every zero-quality timestep, including after training.
    logits = ops.where(total > 0, logits, original)
    return tf.keras.Model([x, mask], logits, name="fingerspelling_residual_visual_v1")


class ResidualSteps:
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
            def update(
                x: Any, mask: Any, y: Any, lengths: Any, target_lengths: Any
            ) -> Any:
                with tf.GradientTape() as tape:
                    loss = ctc_loss(
                        tf, model([x, mask], training=True), y, lengths, target_lengths
                    )
                    if model.losses:
                        loss += tf.add_n(model.losses)
                tf.debugging.assert_all_finite(loss, "[residual/train] Nonfinite loss")
                grads = tape.gradient(loss, model.trainable_variables)
                for g in grads:
                    if g is None:
                        raise ValueError("[residual/train] Missing gradient")
                    tf.debugging.assert_all_finite(
                        g, "[residual/train] Nonfinite gradient"
                    )
                optimizer.apply_gradients(
                    zip(grads, model.trainable_variables, strict=True)
                )
                return loss

            self.update = update
