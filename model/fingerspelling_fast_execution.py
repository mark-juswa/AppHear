"""Separate cached/compiled execution; the frozen model and feature math are reused."""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from model.fingerspelling_metrics import greedy_decode, summarize
from pipeline.fingerspelling.adapter import WIDTH, identity, sha256
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import ARTIFACT_SCHEMA, RECEIPT_SCHEMA


class FeatureCache:
    """Verified immutable arrays; missing hand evidence is never forward-filled."""

    def __init__(self) -> None:
        self.adapter = identity()
        self.arrays: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = {}
        self.file_hashes: dict[str, str] = {}
        self.file_loads = 0

    def load(self, rec: dict[str, Any], view: str) -> tuple[np.ndarray, np.ndarray]:
        if view not in {"native", "phone"}:
            raise ValueError("[fingerspelling/cache] Invalid temporal view")
        if rec["schema_version"] != RECEIPT_SCHEMA or rec["adapter"] != self.adapter:
            raise ValueError("[fingerspelling/cache] Receipt schema/adapter mismatch")
        if rec["split_role"] not in {"TRAIN", "DEV"}:
            raise ValueError("[fingerspelling/cache] Protected role refused")
        sid = rec["sample_id"]
        expected = rec["features_sha256"]
        if sid in self.file_hashes and self.file_hashes[sid] != expected:
            raise ValueError("[fingerspelling/cache] Source identity changed")
        key = (sid, view)
        if key not in self.arrays:
            path = REPO / rec["features_path"]
            if sha256(path) != expected:
                raise ValueError("[fingerspelling/cache] Feature hash mismatch")
            with np.load(path, allow_pickle=False) as data:
                meta = json.loads(str(data["metadata_json"].item()))
                if meta["schema_version"] != ARTIFACT_SCHEMA or meta["adapter"] != self.adapter:
                    raise ValueError("[fingerspelling/cache] Artifact schema/adapter mismatch")
                targets = np.array(data["targets"], dtype=np.int32, copy=True)
                for name, field in [("native", "features"), ("phone", "phone_features")]:
                    x = np.array(data[field], dtype=np.float32, copy=True)
                    if x.ndim != 2 or x.shape[1] != WIDTH or not len(x) or not np.isfinite(x).all():
                        raise ValueError("[fingerspelling/cache] Invalid features")
                    x.setflags(write=False)
                    self.arrays[(sid, name)] = (x, targets)
                if targets.ndim != 1 or not len(targets) or np.any((targets < 0) | (targets > 26)):
                    raise ValueError("[fingerspelling/cache] Invalid targets")
                targets.setflags(write=False)
            self.file_hashes[sid] = expected
            self.file_loads += 1
        return self.arrays[key]

    @property
    def bytes(self) -> int:
        unique = {id(a): a for pair in self.arrays.values() for a in pair}
        return sum(a.nbytes for a in unique.values())

    def batch(self, rows: list[dict[str, Any]], view: str) -> tuple[np.ndarray, ...]:
        arrays = [self.load(rec, view) for rec in rows]
        lengths = np.array([len(x) for x, _ in arrays], np.int32)
        target_lengths = np.array([len(y) for _, y in arrays], np.int32)
        x = np.zeros((len(rows), int(lengths.max()), WIDTH), np.float32)
        mask = np.zeros((*x.shape[:2], 1), np.float32)
        y: np.ndarray = np.zeros((len(rows), int(target_lengths.max())), np.int32)
        for i, (a, b) in enumerate(arrays):
            x[i, : len(a)], mask[i, : len(a)], y[i, : len(b)] = a, 1, b
        return x, mask, y, lengths, target_lengths


class CompiledSteps:
    """Dynamic shape signatures avoid tracing a new graph for every sequence length."""

    def __init__(self, tf: Any, model: Any, optimizer: Any = None) -> None:
        from model.fingerspelling_ctc import ctc_loss

        inputs = [
            tf.TensorSpec([None, None, WIDTH], tf.float32),
            tf.TensorSpec([None, None, 1], tf.float32),
        ]
        signature = [
            *inputs,
            tf.TensorSpec([None, None], tf.int32),
            tf.TensorSpec([None], tf.int32),
            tf.TensorSpec([None], tf.int32),
        ]

        @tf.function(input_signature=inputs, jit_compile=False)
        def infer(x: Any, mask: Any) -> Any:
            return model([x, mask], training=False)

        def gradients(training: bool) -> Any:
            @tf.function(input_signature=signature, jit_compile=False)
            def calculate(x: Any, mask: Any, y: Any, lengths: Any, target_lengths: Any) -> Any:
                with tf.GradientTape() as tape:
                    logits = model([x, mask], training=training)
                    loss = ctc_loss(tf, logits, y, lengths, target_lengths)
                values = tape.gradient(loss, model.trainable_variables)
                for value in values:
                    if value is None:
                        raise ValueError("[fingerspelling/compiled] Missing gradient")
                    tf.debugging.assert_all_finite(value, "Non-finite gradient")
                return loss, values

            return calculate

        self.infer = infer
        self.gradients_without_dropout = gradients(False)
        self.gradients_training = gradients(True)
        self.update = None
        if optimizer is not None:

            @tf.function(input_signature=signature, jit_compile=False)
            def update(x: Any, mask: Any, y: Any, lengths: Any, target_lengths: Any) -> Any:
                loss, values = self.gradients_training(x, mask, y, lengths, target_lengths)
                optimizer.apply_gradients(zip(values, model.trainable_variables, strict=True))
                return loss

            self.update = update


def evaluate_batched(
    tf: Any,
    steps: CompiledSteps,
    cache: FeatureCache,
    rows: list[dict[str, Any]],
    view: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    predictions: list[dict[str, Any]] = []
    weighted_loss, loss_count = 0.0, 0
    infeasible: list[str] = []
    for start in range(0, len(rows), config["batch_size"]):
        batch = rows[start : start + config["batch_size"]]
        x, mask, y, lengths, target_lengths = cache.batch(batch, view)
        logits = steps.infer(x, mask)
        tokens = np.argmax(logits.numpy(), axis=2)
        for i, rec in enumerate(batch):
            predictions.append(
                {
                    "sample_id": rec["sample_id"],
                    "signer_id": rec["official_signer_id"],
                    "reference": rec["normalized_transcript"],
                    "prediction": greedy_decode(tokens[i, : lengths[i]].tolist()),
                }
            )
        eligible = [i for i, rec in enumerate(batch) if lengths[i] >= rec["ctc_min_timesteps"]]
        infeasible.extend(rec["sample_id"] for i, rec in enumerate(batch) if i not in eligible)
        if eligible:
            values = tf.nn.ctc_loss(
                labels=y[eligible],
                logits=tf.gather(logits, eligible),
                label_length=target_lengths[eligible],
                logit_length=lengths[eligible],
                logits_time_major=False,
                blank_index=27,
            )
            tf.debugging.assert_all_finite(values, "Non-finite DEV CTC")
            weighted_loss += float(tf.reduce_sum(values).numpy())
            loss_count += len(eligible)
    return {
        "metrics": summarize(predictions, config["minimum_subgroup_sequences_to_interpret"]),
        "ctc_mean_loss_eligible_only": weighted_loss / loss_count if loss_count else None,
        "ctc_loss_sequence_count": loss_count,
        "ctc_infeasible_retained_ids": infeasible,
        "all_sequences_greedy_evaluated": len(predictions),
        "predictions": predictions,
        "view": view,
        "role": "DEV",
        "test_accessed": False,
    }
