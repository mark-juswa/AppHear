"""Load v3.0 feature arrays (stage F output) into tf.data pipelines for training."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import tensorflow as tf


def load_vocab(features_dir: Path) -> dict[str, int]:
    with (features_dir / "vocab.json").open("r", encoding="utf-8") as fh:
        vocab: dict[str, int] = json.load(fh)
    return vocab


def load_split(features_dir: Path, split: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (X (N,T,258) f32, y (N,) i32, participant_ids (N,))."""
    with np.load(features_dir / f"{split}.npz", allow_pickle=True) as d:
        return d["X"], d["y"], d["participant_ids"]


def load_streaming_split(
    features_dir: Path, split: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return (X (N,T,258), y (N,), frame_mask (N,T) bool, lengths (N,), participant_ids (N,))."""
    with np.load(features_dir / f"{split}.npz", allow_pickle=True) as d:
        return d["X"], d["y"], d["frame_mask"], d["lengths"], d["participant_ids"]


def make_stream_dataset(
    x: np.ndarray,
    y: np.ndarray,
    frame_mask: np.ndarray,
    batch_size: int,
    shuffle: bool,
    seed: int,
    augment_fn: Any = None,
) -> Any:
    """Per-frame streaming dataset yielding (X, per-frame targets (N,T), sample_weight=frame_mask).
    Padded frames get weight 0, so they're ignored in the per-frame loss/metric."""
    t = x.shape[1]
    y_per_frame = np.repeat(y[:, None], t, axis=1).astype(np.int32)  # every frame targets the gloss
    sample_weight = frame_mask.astype(np.float32)
    ds = tf.data.Dataset.from_tensor_slices((x, y_per_frame, sample_weight))
    if shuffle:
        ds = ds.shuffle(buffer_size=min(len(x), 4096), seed=seed, reshuffle_each_iteration=True)
    ds = ds.batch(batch_size)
    if augment_fn is not None:

        def _aug(xb: Any, yb: Any, sw: Any) -> Any:
            xa = tf.numpy_function(augment_fn, [xb, sw], tf.float32)
            xa.set_shape(xb.shape)
            return xa, yb, sw

        ds = ds.map(_aug, num_parallel_calls=tf.data.AUTOTUNE)
    return ds.prefetch(tf.data.AUTOTUNE)


def make_dataset(
    x: np.ndarray,
    y: np.ndarray,
    batch_size: int,
    shuffle: bool,
    seed: int,
    num_classes: int | None = None,
    one_hot: bool = False,
    augment_fn: Any = None,
) -> Any:
    """Batched tf.data pipeline. Optionally one-hots labels (for a label-smoothed loss) and
    applies a TRAIN-ONLY batch augmentation callable (np array -> np array)."""
    ds = tf.data.Dataset.from_tensor_slices((x, y))
    if shuffle:
        ds = ds.shuffle(buffer_size=min(len(x), 4096), seed=seed, reshuffle_each_iteration=True)
    ds = ds.batch(batch_size)
    if augment_fn is not None:

        def _aug(xb: Any, yb: Any) -> Any:
            xa = tf.numpy_function(augment_fn, [xb], tf.float32)
            xa.set_shape(xb.shape)
            return xa, yb

        ds = ds.map(_aug, num_parallel_calls=tf.data.AUTOTUNE)
    if one_hot:
        assert num_classes is not None
        ds = ds.map(
            lambda xb, yb: (xb, tf.one_hot(yb, num_classes)),
            num_parallel_calls=tf.data.AUTOTUNE,
        )
    return ds.prefetch(tf.data.AUTOTUNE)
