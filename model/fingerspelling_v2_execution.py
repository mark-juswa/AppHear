"""Dimension-general execution of the same B2 causal encoder, loss and regime policy."""

from __future__ import annotations

from typing import Any

import numpy as np

from model import fingerspelling_ctc as reference
from pipeline.fingerspelling.adapter_v2 import WIDTH
from pipeline.fingerspelling.package_v2 import check, parents
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.temporal_views import requested_view


def build_model(tf: Any, config: dict[str, Any]) -> Any:
    original = reference.build_model(tf, config)
    # Clone layers/configurations, rebuilding only the input-dependent kernels for D=255.
    inputs = [
        tf.keras.Input((None, WIDTH), name="features"),
        tf.keras.Input((None, 1), name="time_valid"),
    ]
    return tf.keras.models.clone_model(original, input_tensors=inputs)


class Steps:
    def __init__(self, tf: Any, model: Any, optimizer: Any = None) -> None:
        inputs = [
            tf.TensorSpec([None, None, WIDTH], tf.float32),
            tf.TensorSpec([None, None, 1], tf.float32),
        ]

        @tf.function(input_signature=inputs, jit_compile=False)
        def infer(x: Any, mask: Any) -> Any:
            return model([x, mask], training=False)

        self.infer = infer
        self.update = None
        if optimizer is not None:

            @tf.function(
                input_signature=[
                    *inputs,
                    tf.TensorSpec([None, None], tf.int32),
                    tf.TensorSpec([None], tf.int32),
                    tf.TensorSpec([None], tf.int32),
                ],
                jit_compile=False,
            )
            def update(x: Any, mask: Any, y: Any, lengths: Any, target_lengths: Any) -> Any:
                with tf.GradientTape() as tape:
                    loss = reference.ctc_loss(
                        tf, model([x, mask], training=True), y, lengths, target_lengths
                    )
                values = tape.gradient(loss, model.trainable_variables)
                tf.debugging.assert_all_finite(loss, "Non-finite v2 CTC")
                for value in values:
                    if value is None:
                        raise ValueError("[fingerspelling/v2-train] Missing gradient")
                    tf.debugging.assert_all_finite(value, "Non-finite v2 gradient")
                optimizer.apply_gradients(zip(values, model.trainable_variables, strict=True))
                return loss

            self.update = update


class Cache:
    def __init__(self, policy: dict[str, Any]) -> None:
        self.policy = policy
        self.arrays: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = {}
        self.originals = {r["sample_id"]: r for r in parents()}

    def load(self, rec: dict[str, Any], view: str) -> tuple[np.ndarray, np.ndarray]:
        if view not in self.policy["temporal_views"]:
            raise ValueError("[fingerspelling/v2-cache] Invalid view")
        key = (rec["sample_id"], view)
        if key not in self.arrays:
            check(rec, self.originals[rec["sample_id"]])
            with np.load(REPO / rec["features_path"], allow_pickle=False) as data:
                target = np.array(data["targets"], np.int32, copy=True)
                target.setflags(write=False)
                for name in self.policy["temporal_views"]:
                    x = np.array(data[f"{name}_features"], np.float32, copy=True)
                    x.setflags(write=False)
                    self.arrays[(rec["sample_id"], name)] = (x, target)
        return self.arrays[key]

    def tensors(self, rows: list[dict[str, Any]], views: list[str]) -> tuple[np.ndarray, ...]:
        arrays = [self.load(r, v) for r, v in zip(rows, views, strict=True)]
        lengths = np.asarray([len(x) for x, y in arrays], np.int32)
        tl = np.asarray([len(y) for x, y in arrays], np.int32)
        x: np.ndarray = np.zeros((len(rows), int(lengths.max()), WIDTH), np.float32)
        mask: np.ndarray = np.zeros((*x.shape[:2], 1), np.float32)
        targets: np.ndarray = np.zeros((len(rows), int(tl.max())), np.int32)
        for i, (a, b) in enumerate(arrays):
            x[i, : len(a)], mask[i, : len(a)], targets[i, : len(b)] = a, 1, b
        return x, mask, targets, lengths, tl

    def batch(self, rows: list[dict[str, Any]], view: str) -> tuple[np.ndarray, ...]:
        return self.tensors(rows, [view] * len(rows))

    def training_batch(
        self, rows: list[dict[str, Any]], epoch: int
    ) -> tuple[tuple[np.ndarray, ...], list[dict[str, Any]]]:
        choices = []
        views = self.policy["temporal_views"]
        for r in rows:
            requested = requested_view(r["sample_id"], epoch, self.policy)
            feasible = [
                v
                for v in reversed(views[: views.index(requested) + 1])
                if r["views"][v]["ctc_feasible"]
            ]
            if not feasible:
                raise ValueError(
                    "[fingerspelling/v2-training] Native infeasible; retained source refused"
                )
            actual = feasible[0]
            choices.append(
                {
                    "sample_id": r["sample_id"],
                    "requested": requested,
                    "actual": actual,
                    "fallback": requested != actual,
                    **r["views"][actual],
                }
            )
        return self.tensors(rows, [c["actual"] for c in choices]), choices
