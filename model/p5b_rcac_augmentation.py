"""P5-B RCA-C DWPose-compatible augmentation and guarded training runner.

Full training is user-run only. RCA-C changes only historically proven train-time
temporal/geometric augmentation; representation, model, data, and validation stay frozen.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
import numpy as np  # noqa: E402

from model.p5b_rcab_horizon import (  # noqa: E402
    atomic_json,
    atomic_model_save,
    keras_fit_dataset,
    sha256,
)
from model.p5b_temporal_baseline import (  # noqa: E402
    build_model as build_baseline_model,
)
from model.p5b_temporal_baseline import (
    classification_metrics,
    clip_probs,
    load_split,
)

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5b_rcac_preparation_01"
CONTRACT = PREP / "p5b_rcac_augmentation_contract.json"
VALIDATION_BASELINE = PREP / "p5b_rcac_validation_baseline.json"
RUN = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5b_rcac_augmentation_01"
DATA = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5b_migration_01/dataset"
EXPECTED_CONTRACT_SHA256 = "61e01388429ee8a200cb9c8390f2e1fea0b0d7d2d5fb88d2d2ed9a958abcc3a1"
EXPECTED_DATA_HASHES = {
    "train": "a2261ea8d61e5eed1a526da0493da5b36c1bb54432ccef7f7479d6ca94634f11",
    "val": "627275d03087f49fda65138253425131e35fe9c5cb8ded6a93b914484be5afe2",
}
MAX_EPOCHS = 100
PATIENCE = 8
BATCH = 32
SEED = 101
STEPS_PER_EPOCH = math.ceil(3926 / BATCH)
TEMPORAL_PROBABILITY = 0.75
MAX_STRIDE = 5
MIN_FRAMES = 4
ROTATION_DEG = 10.0
SCALE_RANGE = 0.10
NOISE_STD = 0.01
HISTORY_FIELDS = [
    "epoch",
    "phase",
    "loss",
    "pf_acc",
    "val_loss",
    "val_pf_acc",
    "learning_rate",
    "optimizer_iterations",
]
BLOCKS = ((0, 84, 21), (84, 168, 21), (168, 236, 17))


def _rng_for_occurrence(occurrence: int) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([SEED, int(occurrence)]))


def augment_sample(
    features: np.ndarray,
    frame_mask: np.ndarray,
    occurrence: int,
    enabled: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply the frozen temporal-then-geometric policy to one `[96,238]` sample."""
    x = np.asarray(features, dtype=np.float32).copy()
    mask = np.asarray(frame_mask, dtype=bool).copy()
    if x.shape != (96, 238) or mask.shape != (96,):
        raise ValueError(f"RCA-C sample contract mismatch: {x.shape}, {mask.shape}")
    if not enabled:
        return x, mask
    rng = _rng_for_occurrence(occurrence)

    valid_frames = np.flatnonzero(mask)
    if len(valid_frames) >= max(2, MIN_FRAMES) and rng.random() < TEMPORAL_PROBABILITY:
        stride_cap = min(MAX_STRIDE, len(valid_frames) // MIN_FRAMES)
        if stride_cap >= 2:
            stride = int(rng.integers(2, stride_cap + 1))
            selected = valid_frames[::stride]
            compact = np.zeros_like(x)
            compact[: len(selected)] = x[selected]
            x = compact
            mask[:] = False
            mask[: len(selected)] = True

    theta = np.deg2rad(np.float32(rng.uniform(-ROTATION_DEG, ROTATION_DEG)))
    cosine, sine = np.float32(np.cos(theta)), np.float32(np.sin(theta))
    scale = np.float32(rng.uniform(1.0 - SCALE_RANGE, 1.0 + SCALE_RANGE))
    for start, end, points in BLOCKS:
        block = x[:, start:end].reshape(96, points, 4)
        valid = (block[..., 3] > 0.5) & mask[:, None]
        old_score = block[..., 2].copy()
        old_valid = block[..., 3].copy()
        xy = block[..., :2].copy()
        noise = rng.normal(0.0, NOISE_STD, xy.shape).astype(np.float32)
        transformed_x = scale * (cosine * xy[..., 0] - sine * xy[..., 1]) + noise[..., 0]
        transformed_y = scale * (sine * xy[..., 0] + cosine * xy[..., 1]) + noise[..., 1]
        block[..., 0] = np.where(valid, transformed_x, 0.0)
        block[..., 1] = np.where(valid, transformed_y, 0.0)
        block[..., 2] = np.where(valid, old_score, 0.0)
        block[..., 3] = np.where(valid, old_valid, 0.0)
        x[:, start:end] = block.reshape(96, end - start)

    # Observation masks are perception state, never augmentation targets.
    x[~mask] = 0.0
    for start, end, observed_index in ((0, 84, 236), (84, 168, 237)):
        unobserved = mask & (x[:, observed_index] <= 0.5)
        x[unobserved, start:end] = 0.0
    if not np.isfinite(x).all():
        raise RuntimeError("P5B_RCAC_NONFINITE_AUGMENTATION")
    return x.astype(np.float32, copy=False), mask


def augment_batch_numpy(
    features: np.ndarray,
    frame_mask: np.ndarray,
    occurrences: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    output = np.empty_like(np.asarray(features, dtype=np.float32))
    masks = np.empty_like(np.asarray(frame_mask, dtype=bool))
    for index in range(len(output)):
        output[index], masks[index] = augment_sample(
            features[index], frame_mask[index], int(occurrences[index]), enabled=True
        )
    return output, masks


def augment_sample_tf(features: Any, frame_mask: Any, occurrence: Any) -> tuple[Any, Any]:
    """Stateless TensorFlow implementation used by the checkpointable training iterator."""
    import tensorflow as tf

    x = tf.ensure_shape(tf.cast(features, tf.float32), (96, 238))
    mask = tf.ensure_shape(tf.cast(frame_mask, tf.bool), (96,))
    seed = tf.stack([tf.constant(SEED, tf.int32), tf.cast(occurrence, tf.int32)])
    seeds = tf.random.experimental.stateless_split(seed, 8)
    valid_indices = tf.cast(tf.reshape(tf.where(mask), (-1,)), tf.int32)
    valid_count = tf.size(valid_indices)
    stride_cap = tf.minimum(tf.constant(MAX_STRIDE, tf.int32), valid_count // MIN_FRAMES)
    use_temporal = tf.logical_and(
        stride_cap >= 2,
        tf.random.stateless_uniform((), seeds[0]) < TEMPORAL_PROBABILITY,
    )

    def compress() -> tuple[Any, Any]:
        stride = tf.random.stateless_uniform(
            (), seeds[1], minval=2, maxval=stride_cap + 1, dtype=tf.int32
        )
        selected = tf.gather(valid_indices, tf.range(0, valid_count, stride))
        compact_count = tf.size(selected)
        compact = tf.concat(
            [tf.gather(x, selected), tf.zeros((96 - compact_count, 238), tf.float32)],
            axis=0,
        )
        return compact, tf.sequence_mask(compact_count, 96)

    x, mask = tf.cond(use_temporal, compress, lambda: (x, mask))
    theta = tf.random.stateless_uniform((), seeds[2], minval=-ROTATION_DEG, maxval=ROTATION_DEG) * (
        np.pi / 180.0
    )
    cosine, sine = tf.cos(theta), tf.sin(theta)
    scale = tf.random.stateless_uniform(
        (), seeds[3], minval=1.0 - SCALE_RANGE, maxval=1.0 + SCALE_RANGE
    )
    rebuilt = []
    for block_index, (start, end, points) in enumerate(BLOCKS):
        block = tf.reshape(x[:, start:end], (96, points, 4))
        valid = tf.logical_and(block[..., 3] > 0.5, mask[:, None])
        xy = block[..., :2]
        noise = tf.random.stateless_normal(tf.shape(xy), seeds[4 + block_index], stddev=NOISE_STD)
        transformed_x = scale * (cosine * xy[..., 0] - sine * xy[..., 1]) + noise[..., 0]
        transformed_y = scale * (sine * xy[..., 0] + cosine * xy[..., 1]) + noise[..., 1]
        rebuilt.append(
            tf.stack(
                [
                    tf.where(valid, transformed_x, 0.0),
                    tf.where(valid, transformed_y, 0.0),
                    tf.where(valid, block[..., 2], 0.0),
                    tf.where(valid, block[..., 3], 0.0),
                ],
                axis=-1,
            )
        )
    output = tf.concat(
        [
            tf.reshape(rebuilt[0], (96, 84)),
            tf.reshape(rebuilt[1], (96, 84)),
            tf.reshape(rebuilt[2], (96, 68)),
            x[:, 236:238],
        ],
        axis=1,
    )
    left_unobserved = tf.logical_and(mask, output[:, 236] <= 0.5)
    right_unobserved = tf.logical_and(mask, output[:, 237] <= 0.5)
    output = tf.concat(
        [
            tf.where(left_unobserved[:, None], 0.0, output[:, :84]),
            tf.where(right_unobserved[:, None], 0.0, output[:, 84:168]),
            output[:, 168:],
        ],
        axis=1,
    )
    output = tf.where(mask[:, None], output, 0.0)
    return tf.ensure_shape(output, (96, 238)), tf.ensure_shape(mask, (96,))


def augment_batch_tf(features: Any, frame_mask: Any, occurrences: Any) -> tuple[Any, Any]:
    import tensorflow as tf

    return tf.map_fn(
        lambda values: augment_sample_tf(values[0], values[1], values[2]),
        (features, frame_mask, occurrences),
        fn_output_signature=(
            tf.TensorSpec((96, 238), tf.float32),
            tf.TensorSpec((96,), tf.bool),
        ),
        parallel_iterations=1,
    )


def train_dataset(x: np.ndarray, y: np.ndarray, mask: np.ndarray) -> Any:
    import tensorflow as tf

    ypf = np.repeat(y[:, None], 96, axis=1)
    source_index = np.arange(len(x), dtype=np.int64)
    ds = tf.data.Dataset.from_tensor_slices((x, ypf, mask.astype(bool), source_index))
    ds = ds.shuffle(len(x), seed=SEED, reshuffle_each_iteration=True).repeat().enumerate()
    ds = ds.batch(BATCH)

    def apply_aug(occurrence: Any, values: Any) -> Any:
        xb, yb, mb, _ = values
        xa, ma = augment_batch_tf(xb, mb, occurrence)
        xa.set_shape(xb.shape)
        ma.set_shape(mb.shape)
        return xa, yb, tf.cast(ma, tf.float32)

    return ds.map(apply_aug, num_parallel_calls=1, deterministic=True).prefetch(1)


def validation_dataset(x: np.ndarray, y: np.ndarray, mask: np.ndarray) -> Any:
    import tensorflow as tf

    ypf = np.repeat(y[:, None], 96, axis=1)
    return (
        tf.data.Dataset.from_tensor_slices((x, ypf, mask.astype(np.float32)))
        .batch(BATCH)
        .prefetch(1)
    )


def build_model() -> Any:
    import tensorflow as tf

    tf.keras.utils.set_random_seed(SEED)
    model = build_baseline_model(236)
    model.optimizer.build(model.trainable_variables)
    return model


def preflight() -> dict[str, Any]:
    if sha256(CONTRACT) != EXPECTED_CONTRACT_SHA256:
        raise RuntimeError("P5B_RCAC_CONTRACT_HASH_MISMATCH")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if (
        contract["augmentation_only"] is not True
        or contract["training"]["maximum_total_epochs"] != 100
    ):
        raise RuntimeError("P5B_RCAC_CONTRACT_CONTENT_MISMATCH")
    for name, expected in EXPECTED_DATA_HASHES.items():
        if sha256(DATA / f"{name}.npz") != expected:
            raise RuntimeError(f"P5B_RCAC_{name.upper()}_HASH_MISMATCH")
    loaded = {name: load_split(name) for name in ("train", "val")}
    return {
        "passed": True,
        "contract_sha256": EXPECTED_CONTRACT_SHA256,
        "counts": {name: len(values[1]) for name, values in loaded.items()},
        "test_loaded": False,
    }


def checkpoint_bundle(model: Any, iterator: Any) -> tuple[Any, Any, Any, Any, Any]:
    import tensorflow as tf

    completed = tf.Variable(0, trainable=False, dtype=tf.int64, name="completed_epochs")
    best = tf.Variable(-np.inf, trainable=False, dtype=tf.float64, name="best_val_pf_acc")
    wait = tf.Variable(0, trainable=False, dtype=tf.int64, name="early_stop_wait")
    seed_states = {
        f"dropout_seed_state_{index}": variable
        for index, variable in enumerate(model.non_trainable_variables)
        if "seed_generator_state" in variable.name
    }
    checkpoint = tf.train.Checkpoint(
        model=model,
        optimizer=model.optimizer,
        train_iterator=iterator,
        completed_epochs=completed,
        best_val_pf_acc=best,
        early_stop_wait=wait,
        **seed_states,
    )
    manager = tf.train.CheckpointManager(checkpoint, str(RUN / "resume_state"), max_to_keep=2)
    return checkpoint, completed, best, wait, manager


def _initialize_history() -> None:
    with (RUN / "history.csv").open("w", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=HISTORY_FIELDS).writeheader()


def _append_history(row: dict[str, Any]) -> None:
    with (RUN / "history.csv").open("a", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=HISTORY_FIELDS).writerow(row)
        handle.flush()
        os.fsync(handle.fileno())


def train(resume: bool) -> int:
    import tensorflow as tf

    preflight()
    xtr, ytr, mtr, _, _ = load_split("train")
    xv, yv, mv, _, _ = load_split("val")
    iterator = iter(train_dataset(xtr, ytr, mtr))
    training = keras_fit_dataset(iterator)
    validation = validation_dataset(xv, yv, mv)
    model = build_model()
    checkpoint, completed, best, wait, manager = checkpoint_bundle(model, iterator)
    state_path = RUN / "run_state.json"
    if resume:
        if not manager.latest_checkpoint or not state_path.is_file():
            raise RuntimeError("P5B_RCAC_NO_RESUMABLE_CHECKPOINT")
        checkpoint.restore(manager.latest_checkpoint).assert_existing_objects_matched()
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if int(completed.numpy()) != int(state["completed_epochs"]):
            raise RuntimeError("P5B_RCAC_STATE_CHECKPOINT_EPOCH_MISMATCH")
    else:
        if RUN.exists() and any(RUN.iterdir()):
            raise RuntimeError("P5B_RCAC_RUN_EXISTS_USE_RESUME")
        RUN.mkdir(parents=True, exist_ok=True)
        _initialize_history()
        state = {"completed_epochs": 0, "status": "RUNNING"}
    start = int(completed.numpy())
    if start >= MAX_EPOCHS or state.get("status") in {"EARLY_STOPPED", "MAX_EPOCH_REACHED"}:
        print(json.dumps({**state, "message": "RCA-C training already complete"}, indent=2))
        return 0
    class EpochStateCallback(tf.keras.callbacks.Callback):
        """Persist governed state without retracing the augmented graph every epoch."""

        def on_epoch_end(self, epoch: int, logs: dict[str, Any] | None = None) -> None:
            metrics = {key: float(value) for key, value in (logs or {}).items()}
            value = metrics["val_pf_acc"]
            if value > float(best.numpy()):
                best.assign(value)
                wait.assign(0)
                atomic_model_save(model, RUN / "best.keras")
            else:
                wait.assign_add(1)
            completed.assign(epoch + 1)
            latest_checkpoint = manager.save(checkpoint_number=epoch + 1)
            atomic_model_save(model, RUN / "latest.keras")
            _append_history(
                {
                    "epoch": epoch,
                    "phase": "RCAC_AUGMENTATION_ONLY",
                    "loss": metrics["loss"],
                    "pf_acc": metrics["pf_acc"],
                    "val_loss": metrics["val_loss"],
                    "val_pf_acc": metrics["val_pf_acc"],
                    "learning_rate": float(
                        tf.keras.backend.get_value(model.optimizer.learning_rate)
                    ),
                    "optimizer_iterations": int(model.optimizer.iterations.numpy()),
                }
            )
            current_state = {
                "completed_epochs": int(completed.numpy()),
                "last_completed_epoch": epoch,
                "best_val_pf_acc": float(best.numpy()),
                "early_stop_wait": int(wait.numpy()),
                "optimizer_iterations": int(model.optimizer.iterations.numpy()),
                "latest_checkpoint": latest_checkpoint,
                "status": "RUNNING",
            }
            if int(wait.numpy()) >= PATIENCE:
                current_state["status"] = "EARLY_STOPPED"
            elif int(completed.numpy()) >= MAX_EPOCHS:
                current_state["status"] = "MAX_EPOCH_REACHED"
            atomic_json(state_path, current_state)
            print(json.dumps(current_state, indent=2), flush=True)
            if current_state["status"] != "RUNNING":
                self.model.stop_training = True

    # Keep one compiled fit graph alive for the remainder of the run. Re-entering
    # model.fit once per epoch retained augmented tf.data graphs on native Windows
    # and exhausted CPU memory after epoch 3.
    model.fit(
        training,
        steps_per_epoch=STEPS_PER_EPOCH,
        validation_data=validation,
        initial_epoch=start,
        epochs=MAX_EPOCHS,
        callbacks=[EpochStateCallback()],
        verbose=2,
        shuffle=False,
    )
    return 0


def _signer_metrics(y: np.ndarray, pred: np.ndarray, signers: np.ndarray) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for signer in sorted(set(map(str, signers))):
        selected = np.asarray([str(value) == signer for value in signers])
        result[signer] = {
            "n": int(selected.sum()),
            "top1": float(np.mean(pred[selected] == y[selected])),
            "macro_f1": classification_metrics(y[selected], pred[selected], 236)[-1],
        }
    return result


def validation_metrics(model: Any) -> dict[str, Any]:
    x, y, mask, ids, signers = load_split("val")
    probabilities = clip_probs(model, x, mask)
    predictions = probabilities.argmax(axis=1)
    top5 = np.argsort(probabilities, axis=1)[:, -5:]
    matrix, precision, recall, f1, support, macro = classification_metrics(y, predictions, 236)
    evaluation = model.evaluate(validation_dataset(x, y, mask), verbose=0, return_dict=True)
    return {
        "rows": len(y),
        "sample_ids_sha256": hashlib.sha256("\n".join(map(str, ids)).encode()).hexdigest(),
        "top1": float(np.mean(predictions == y)),
        "top5": float(np.mean([y[index] in top5[index] for index in range(len(y))])),
        "macro_f1": macro,
        "per_frame": {key: float(value) for key, value in evaluation.items()},
        "signers": _signer_metrics(y, predictions, signers),
        "per_class": [
            {
                "class_id": index,
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
            }
            for index in range(236)
        ],
        "confusion_matrix_sha256": hashlib.sha256(matrix.tobytes()).hexdigest(),
    }


def evaluate_validation() -> int:
    import tensorflow as tf

    preflight()
    state_path = RUN / "run_state.json"
    if not state_path.is_file() or not (RUN / "best.keras").is_file():
        raise RuntimeError("P5B_RCAC_VALIDATION_CHECKPOINT_NOT_FROZEN")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") not in {"EARLY_STOPPED", "MAX_EPOCH_REACHED"}:
        raise RuntimeError("P5B_RCAC_TRAINING_NOT_COMPLETE")
    model = tf.keras.models.load_model(RUN / "best.keras", safe_mode=False)
    result = {
        "rcab_baseline": json.loads(VALIDATION_BASELINE.read_text(encoding="utf-8")),
        "rcac": validation_metrics(model),
        "protected_test_accessed": False,
        "training_state": state,
        "passed": True,
    }
    atomic_json(RUN / "validation_comparison.json", result)
    print(json.dumps(result, indent=2))
    return 0


def smoke() -> int:
    import tensorflow as tf

    preflight()
    rng = np.random.default_rng(SEED)
    x = rng.normal(size=(8, 96, 238)).astype(np.float32)
    mask = np.ones((8, 96), dtype=bool)
    # Make invalid points, missing hands, and padding explicit.
    x[..., 3:236:4] = 1.0
    x[..., 236:238] = 1.0
    x[0, :, :84] = 0.0
    x[0, :, 236] = 0.0
    mask[1, 20:] = False
    x[1, 20:] = 0.0
    y = np.arange(8, dtype=np.int32)
    with tempfile.TemporaryDirectory(prefix="p5b_rcac_smoke_") as temp_dir:
        root = Path(temp_dir)
        iterator = iter(train_dataset(x, y, mask))
        training = keras_fit_dataset(iterator)
        model = build_model()
        epoch = tf.Variable(0, trainable=False, dtype=tf.int64)
        seed_states = {
            f"dropout_seed_state_{index}": value
            for index, value in enumerate(model.non_trainable_variables)
            if "seed_generator_state" in value.name
        }
        checkpoint = tf.train.Checkpoint(
            model=model,
            optimizer=model.optimizer,
            train_iterator=iterator,
            completed_epochs=epoch,
            **seed_states,
        )
        manager = tf.train.CheckpointManager(checkpoint, str(root / "state"), max_to_keep=1)
        before = [value.numpy().copy() for value in model.trainable_variables]
        model.fit(training, steps_per_epoch=1, epochs=1, verbose=0, shuffle=False)
        epoch.assign(1)
        saved = manager.save(checkpoint_number=1)
        changed = any(
            not np.array_equal(a, b.numpy())
            for a, b in zip(before, model.trainable_variables, strict=True)
        )
        expected_next = next(iterator)[0].numpy().copy()
        iterator2 = iter(train_dataset(x, y, mask))
        restored = build_model()
        epoch2 = tf.Variable(0, trainable=False, dtype=tf.int64)
        seed_states2 = {
            f"dropout_seed_state_{index}": value
            for index, value in enumerate(restored.non_trainable_variables)
            if "seed_generator_state" in value.name
        }
        checkpoint2 = tf.train.Checkpoint(
            model=restored,
            optimizer=restored.optimizer,
            train_iterator=iterator2,
            completed_epochs=epoch2,
            **seed_states2,
        )
        checkpoint2.restore(saved).assert_existing_objects_matched()
        actual_next = next(iterator2)[0].numpy().copy()
        result = {
            "synthetic_only": True,
            "weights_changed": changed,
            "optimizer_iterations": int(restored.optimizer.iterations.numpy()),
            "completed_epoch": int(epoch2.numpy()),
            "augmented_iterator_exact_after_reload": bool(
                np.array_equal(expected_next, actual_next)
            ),
            "protected_test_accessed": False,
        }
        result["passed"] = bool(
            changed
            and result["optimizer_iterations"] == 1
            and result["completed_epoch"] == 1
            and result["augmented_iterator_exact_after_reload"]
        )
        atomic_json(PREP / "p5b_rcac_training_smoke.json", result)
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 2


def status() -> int:
    state = RUN / "run_state.json"
    print(
        state.read_text(encoding="utf-8")
        if state.is_file()
        else json.dumps({"status": "NOT_STARTED"}, indent=2)
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    train_parser = sub.add_parser("train")
    train_parser.add_argument("--resume", action="store_true")
    sub.add_parser("smoke")
    sub.add_parser("status")
    sub.add_parser("evaluate-validation")
    args = parser.parse_args()
    if args.command == "preflight":
        print(json.dumps(preflight(), indent=2))
        return 0
    if args.command == "train":
        return train(args.resume)
    if args.command == "smoke":
        return smoke()
    if args.command == "status":
        return status()
    return evaluate_validation()


if __name__ == "__main__":
    raise SystemExit(main())
