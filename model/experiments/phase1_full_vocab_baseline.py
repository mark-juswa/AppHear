"""Phase 1 equal-budget 236-class landmark baseline comparison.

The experiment compares the production-family per-frame streaming TCN with a
mask-aware pooled TCN. It never evaluates protected test during training and
never exports or modifies Android assets.
"""

from __future__ import annotations

import os

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import argparse  # noqa: E402
import csv  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = "phase1_full_vocab_tcn_comparison_v1"
BRANCHES = ("production_streaming_tcn", "masked_pool_tcn")
SEEDS = (101, 202, 303)
DEFAULT_DATASET = ROOT / (
    "artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1"
)
DEFAULT_OUTPUT = ROOT / (
    "artifacts/recognition_upgrade/phase1_full_vocab/tcn_comparison_01"
)
DEFAULT_WARM_START = Path(
    "F:/ASL DATASET/ASL CITIZEN/derived/apphear3/runs/"
    "tcn_streaming_conversational_fps_v30/best.keras"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing required artifact: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _load_split(path: Path) -> tuple[np.ndarray, ...]:
    with np.load(path, allow_pickle=True) as data:
        return (
            np.asarray(data["X"], dtype=np.float32),
            np.asarray(data["y"], dtype=np.int32),
            np.asarray(data["frame_mask"], dtype=bool),
            np.asarray(data["lengths"], dtype=np.int32),
            np.asarray(data["participant_ids"]).astype(str),
        )


def temporal_subsample_batch(
    x: np.ndarray,
    frame_mask: np.ndarray,
    rng: np.random.Generator,
    probability: float,
    max_stride: int,
    min_frames: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply the existing Stage-F stride/compact/pad policy to a training batch."""
    out = np.asarray(x, dtype=np.float32).copy()
    masks = np.asarray(frame_mask, dtype=bool).copy()
    if out.shape[:2] != masks.shape:
        raise ValueError("feature and frame-mask shapes do not align")
    for index in range(len(out)):
        valid = np.flatnonzero(masks[index])
        if len(valid) < max(2, min_frames) or rng.random() >= probability:
            continue
        stride_cap = min(max_stride, len(valid) // min_frames)
        if stride_cap < 2:
            continue
        stride = int(rng.integers(2, stride_cap + 1))
        selected = valid[::stride]
        compact = np.zeros_like(out[index])
        compact[: len(selected)] = out[index, selected]
        out[index] = compact
        masks[index] = False
        masks[index, : len(selected)] = True
    return out, masks


def build_branch(branch: str, classes: int, dropout: float = 0.3) -> Any:
    import tensorflow as tf

    from model.model import build_encoder, build_streaming_classifier

    if branch == "production_streaming_tcn":
        return build_streaming_classifier(
            96,
            258,
            classes,
            blocks=4,
            channels=64,
            dilations=(1, 2, 4, 8),
            kernel=3,
            dropout=dropout,
        )
    if branch == "masked_pool_tcn":
        features = tf.keras.Input((96, 258), name="features")
        frame_mask = tf.keras.Input((96,), dtype="bool", name="frame_mask")
        encoder = build_encoder(96, 258, 4, 64, (1, 2, 4, 8), 3, dropout)
        encoded = encoder(features)
        pooled = tf.keras.layers.GlobalAveragePooling1D(name="masked_pool")(
            encoded, mask=frame_mask
        )
        output = tf.keras.layers.Dense(classes, activation="softmax", name="logits")(
            pooled
        )
        return tf.keras.Model(
            [features, frame_mask], output, name="phase1_masked_pool_tcn"
        )
    raise ValueError(f"unsupported branch: {branch}")


def compile_branch(model: Any, branch: str, learning_rate: float, weight_decay: float) -> None:
    import tensorflow as tf

    metric = "pf_acc" if branch == "production_streaming_tcn" else "accuracy"
    model.compile(
        optimizer=tf.keras.optimizers.AdamW(
            learning_rate=learning_rate, weight_decay=weight_decay
        ),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(),
        weighted_metrics=[tf.keras.metrics.SparseCategoricalAccuracy(name=metric)],
    )


def copy_encoder_weights(model: Any, warm_start: Path) -> int:
    """Copy only the common encoder, never the production classifier head."""
    import tensorflow as tf

    source = tf.keras.models.load_model(warm_start, compile=False, safe_mode=False)
    source_layers = {layer.name: layer for layer in source.layers}
    try:
        target_layers = model.get_layer("causal_tcn_encoder").layers
    except ValueError:
        target_layers = model.layers
    copied = 0
    for layer in target_layers:
        if not layer.name.startswith("tcn") or not layer.get_weights():
            continue
        source_layer = source_layers.get(layer.name)
        if source_layer is None:
            continue
        try:
            layer.set_weights(source_layer.get_weights())
        except ValueError as exc:
            raise ValueError(f"warm-start shape mismatch for {layer.name}") from exc
        copied += 1
    if copied == 0:
        raise ValueError("warm-start copied zero TCN encoder layers")
    return copied


def predict_clip_probs(
    model: Any,
    branch: str,
    x: np.ndarray,
    frame_mask: np.ndarray,
    batch_size: int,
) -> np.ndarray:
    classes = int(model.output_shape[-1])
    output = np.empty((len(x), classes), dtype=np.float32)
    for start in range(0, len(x), batch_size):
        end = min(start + batch_size, len(x))
        xb, mb = x[start:end], frame_mask[start:end]
        if branch == "production_streaming_tcn":
            per_frame = np.asarray(model(xb, training=False), dtype=np.float32)
            weights = mb.astype(np.float32)[..., None]
            output[start:end] = (per_frame * weights).sum(axis=1) / np.clip(
                weights.sum(axis=1), 1.0, None
            )
        else:
            output[start:end] = np.asarray(model([xb, mb], training=False))
    return output


def _augment(
    x: np.ndarray,
    mask: np.ndarray,
    rng: np.random.Generator,
    config: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    from model.augment import AugmentConfig, augment_batch

    temporal = config["augmentation"]["temporal"]
    x_aug, mask_aug = temporal_subsample_batch(
        x,
        mask,
        rng,
        float(temporal["probability"]),
        int(temporal["max_stride"]),
        int(temporal["min_frames"]),
    )
    geometric = config["augmentation"]["geometric"]
    x_aug = augment_batch(
        x_aug,
        AugmentConfig(
            rotation_deg=float(geometric["rotation_deg"]),
            scale=float(geometric["scale"]),
            noise_std=float(geometric["noise_std"]),
            frame_mask_frac=0.0,
        ),
        rng,
        valid_frame_mask=mask_aug,
    )
    return x_aug, mask_aug


def _dataset(
    branch: str,
    x: np.ndarray,
    y: np.ndarray,
    mask: np.ndarray,
    batch_size: int,
    seed: int,
    config: dict[str, Any],
    training: bool,
) -> Any:
    import tensorflow as tf

    ds = tf.data.Dataset.from_tensor_slices((x, y, mask))
    if training:
        ds = ds.shuffle(min(len(x), 4096), seed=seed, reshuffle_each_iteration=True)
    ds = ds.batch(batch_size)
    if training:
        rng = np.random.default_rng(seed)

        def apply_aug(xb: Any, yb: Any, mb: Any) -> tuple[Any, Any, Any]:
            xa, ma = tf.numpy_function(
                lambda xv, mv: _augment(xv, mv, rng, config),
                [xb, mb],
                [tf.float32, tf.bool],
            )
            xa.set_shape(xb.shape)
            ma.set_shape(mb.shape)
            return xa, yb, ma

        ds = ds.map(apply_aug, num_parallel_calls=1, deterministic=True)

    def format_batch(xb: Any, yb: Any, mb: Any) -> Any:
        if branch == "production_streaming_tcn":
            targets = tf.repeat(yb[:, None], repeats=96, axis=1)
            return xb, targets, tf.cast(mb, tf.float32)
        return (xb, mb), yb

    return ds.map(format_batch, num_parallel_calls=1, deterministic=True).prefetch(1)


def _config(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "experiment": EXPERIMENT,
        "scope": "offline full-vocabulary landmark comparison; protected test blocked",
        "dataset_dir": str(args.dataset.resolve()),
        "output_dir": str(args.output.resolve()),
        "schema_version": "3.0",
        "input_shape": [96, 258],
        "classes": 236,
        "branches": list(BRANCHES),
        "seeds": list(SEEDS),
        "model": {
            "blocks": 4,
            "channels": 64,
            "dilations": [1, 2, 4, 8],
            "kernel": 3,
            "dropout": 0.3,
        },
        "training": {
            "batch_size": 32,
            "epochs": 40,
            "learning_rate": 0.0005,
            "weight_decay": 0.0001,
            "early_stop_patience": 8,
        },
        "augmentation": {
            "temporal": {
                "policy": "existing stride-compact-zero-pad Stage-F policy",
                "probability": 0.75,
                "max_stride": 5,
                "min_frames": 4,
            },
            "geometric": {
                "rotation_deg": 10.0,
                "scale": 0.10,
                "noise_std": 0.01,
            },
            "missing_landmark": "evaluation only; no new unverified training transform",
        },
        "warm_start": {
            "path": str(args.warm_start.resolve()),
            "sha256": _sha256(args.warm_start),
            "policy": "same encoder weights only; both heads initialized fresh",
        },
        "selection": {
            "metric": "validation clip top-1",
            "test_access": "blocked until validation winner is frozen",
        },
        "production_authorized": False,
    }


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    assembly = args.dataset / "assembly_summary.json"
    check_report = args.dataset / "check_report.json"
    if not assembly.is_file() or not check_report.is_file():
        raise FileNotFoundError("Phase 1 assembled dataset has not been checked")
    assembly_data = json.loads(assembly.read_text(encoding="utf-8"))
    check_data = json.loads(check_report.read_text(encoding="utf-8"))
    if not assembly_data.get("passed") or assembly_data.get("smoke"):
        raise ValueError("full dataset assembly did not pass")
    if not check_data.get("passed"):
        raise ValueError("dataset checker did not pass")
    if assembly_data["splits"]["train"]["classes"] != 236:
        raise ValueError("training dataset does not cover 236 classes")
    if not args.warm_start.is_file():
        raise FileNotFoundError(f"missing warm-start model: {args.warm_start}")
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty run: {args.output}")
    for relative in ("config", "logs", "models", "metrics", "smoke"):
        (args.output / relative).mkdir(parents=True, exist_ok=True)
    config = _config(args)
    config["dataset_hashes"] = {
        name: _sha256(args.dataset / f"{name}.npz")
        for name in ("train", "val", "test")
    }
    _write_json(args.output / "config" / "experiment.json", config)
    _write_json(args.output / "logs" / "prepare_summary.json", {**config, "passed": True})
    return {**config, "passed": True, "next": "run smoke"}


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    config = json.loads(
        (args.run_dir / "config" / "experiment.json").read_text(encoding="utf-8")
    )
    x, y, mask, _, _ = _load_split(Path(config["dataset_dir"]) / "train.npz")
    indices = np.concatenate(
        [np.flatnonzero(y == class_id)[:1] for class_id in np.unique(y)[:32]]
    )
    x, y, mask = x[indices], y[indices], mask[indices]
    results: dict[str, Any] = {}
    for branch in BRANCHES:
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(101)
        model = build_branch(branch, 236)
        compile_branch(model, branch, 0.0005, 0.0001)
        copied = copy_encoder_weights(model, Path(config["warm_start"]["path"]))
        history = model.fit(
            _dataset(branch, x, y, mask, 16, 101, config, True),
            steps_per_epoch=1,
            epochs=1,
            verbose=0,
        )
        probs = predict_clip_probs(model, branch, x, mask, 8)
        checkpoint = args.run_dir / "smoke" / f"{branch}.keras"
        model.save(checkpoint)
        loaded = tf.keras.models.load_model(checkpoint, compile=False, safe_mode=False)
        reload_probs = predict_clip_probs(loaded, branch, x[:2], mask[:2], 2)
        results[branch] = {
            "rows": len(x),
            "parameters": model.count_params(),
            "encoder_weights_copied": copied,
            "one_step_history": {
                key: float(values[-1]) for key, values in history.history.items()
            },
            "clip_output_shape": list(probs.shape),
            "reload_output_shape": list(reload_probs.shape),
            "finite": bool(np.isfinite(probs).all() and np.isfinite(reload_probs).all()),
            "checkpoint": str(checkpoint.resolve()),
        }
    passed = all(
        item["finite"] and item["clip_output_shape"] == [len(x), 236]
        for item in results.values()
    )
    summary = {
        "experiment": EXPERIMENT,
        "stage": "actual_data_equal_budget_smoke",
        "branches": results,
        "protected_test_accessed": False,
        "passed": passed,
    }
    _write_json(args.run_dir / "smoke" / "smoke_summary.json", summary)
    return summary


def _history_epoch(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return max((int(row["epoch"]) for row in rows), default=-1) + 1


def train(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    config = json.loads(
        (args.run_dir / "config" / "experiment.json").read_text(encoding="utf-8")
    )
    dataset_dir = Path(config["dataset_dir"])
    x_train, y_train, mask_train, _, _ = _load_split(dataset_dir / "train.npz")
    x_val, y_val, mask_val, _, _ = _load_split(dataset_dir / "val.npz")
    training = config["training"]
    target_epochs = int(args.epochs or training["epochs"])
    completed: list[dict[str, Any]] = []

    class ValidationClipAccuracy(tf.keras.callbacks.Callback):
        def __init__(self, branch: str) -> None:
            super().__init__()
            self.branch = branch

        def on_epoch_end(self, epoch: int, logs: dict[str, Any] | None = None) -> None:
            assert self.model is not None
            probs = predict_clip_probs(
                self.model,
                self.branch,
                x_val,
                mask_val,
                int(training["batch_size"]),
            )
            accuracy = float(np.mean(np.argmax(probs, axis=1) == y_val))
            if logs is not None:
                logs["val_clip_acc"] = accuracy
            print(f" - val_clip_acc: {accuracy:.4f}")

    for branch in BRANCHES:
        for seed in SEEDS:
            tf.keras.backend.clear_session()
            tf.keras.utils.set_random_seed(seed)
            model_dir = args.run_dir / "models" / branch / f"seed_{seed}"
            model_dir.mkdir(parents=True, exist_ok=True)
            history = model_dir / "history.csv"
            latest = model_dir / "latest.keras"
            best = model_dir / "best.keras"
            final = model_dir / "final.keras"
            if args.resume and final.is_file():
                completed.append(
                    {"branch": branch, "seed": seed, "status": "already_complete"}
                )
                continue
            resuming_checkpoint = args.resume and latest.is_file()
            initial_epoch = _history_epoch(history) if resuming_checkpoint else 0
            if resuming_checkpoint:
                model = tf.keras.models.load_model(latest, safe_mode=False)
                copied = 0
            else:
                existing_output = any(
                    path.exists() for path in (history, latest, best, final)
                )
                if not args.resume and existing_output:
                    raise FileExistsError(
                        f"refusing to overwrite {model_dir}; use --resume or a new run"
                    )
                model = build_branch(branch, 236, float(config["model"]["dropout"]))
                compile_branch(
                    model,
                    branch,
                    float(training["learning_rate"]),
                    float(training["weight_decay"]),
                )
                copied = copy_encoder_weights(model, Path(config["warm_start"]["path"]))
            if initial_epoch >= target_epochs:
                completed.append(
                    {"branch": branch, "seed": seed, "status": "already_complete"}
                )
                continue
            callbacks = [
                ValidationClipAccuracy(branch),
                tf.keras.callbacks.ModelCheckpoint(
                    best, monitor="val_clip_acc", mode="max", save_best_only=True
                ),
                tf.keras.callbacks.ModelCheckpoint(latest, save_best_only=False),
                tf.keras.callbacks.CSVLogger(history, append=resuming_checkpoint),
                tf.keras.callbacks.EarlyStopping(
                    monitor="val_clip_acc",
                    mode="max",
                    patience=int(training["early_stop_patience"]),
                    restore_best_weights=True,
                ),
            ]
            model.fit(
                _dataset(
                    branch,
                    x_train,
                    y_train,
                    mask_train,
                    int(training["batch_size"]),
                    seed,
                    config,
                    True,
                ),
                validation_data=_dataset(
                    branch,
                    x_val,
                    y_val,
                    mask_val,
                    int(training["batch_size"]),
                    seed,
                    config,
                    False,
                ),
                initial_epoch=initial_epoch,
                epochs=target_epochs,
                callbacks=callbacks,
                verbose=2,
            )
            model.save(final)
            completed.append(
                {
                    "branch": branch,
                    "seed": seed,
                    "initial_epoch": initial_epoch,
                    "target_epochs": target_epochs,
                    "encoder_weights_copied": copied,
                    "status": "completed",
                }
            )
            _write_json(args.run_dir / "logs" / "train_progress.json", completed)
    summary = {
        "experiment": EXPERIMENT,
        "stage": "training",
        "runs": completed,
        "protected_test_accessed": False,
        "passed": len(completed) == len(BRANCHES) * len(SEEDS),
    }
    _write_json(args.run_dir / "logs" / "train_summary.json", summary)
    return summary


def classification_metrics(
    probabilities: np.ndarray,
    labels: np.ndarray,
    participant_ids: np.ndarray,
) -> dict[str, Any]:
    predictions = np.argmax(probabilities, axis=1)
    top_k = min(5, probabilities.shape[1])
    top5 = np.argpartition(-probabilities, kth=top_k - 1, axis=1)[:, :top_k]
    per_class: list[dict[str, Any]] = []
    f1_values: list[float] = []
    for class_id in range(probabilities.shape[1]):
        truth = labels == class_id
        predicted = predictions == class_id
        support = int(truth.sum())
        true_positive = int(np.sum(truth & predicted))
        precision = true_positive / max(int(predicted.sum()), 1)
        recall = true_positive / max(support, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-12)
        if support:
            f1_values.append(f1)
        per_class.append(
            {
                "class_id": class_id,
                "support": support,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
        )
    per_signer = {}
    for signer in sorted(set(participant_ids.tolist())):
        selected = participant_ids == signer
        per_signer[str(signer)] = {
            "rows": int(selected.sum()),
            "top1": float(np.mean(predictions[selected] == labels[selected])),
        }
    return {
        "rows": len(labels),
        "top1": float(np.mean(predictions == labels)),
        "top5": float(np.mean(np.any(top5 == labels[:, None], axis=1))),
        "macro_f1": float(np.mean(f1_values)),
        "per_class": per_class,
        "per_signer": per_signer,
    }


def expected_calibration_error(
    probabilities: np.ndarray, labels: np.ndarray, bins: int = 15
) -> float:
    predictions = np.argmax(probabilities, axis=1)
    confidence = np.max(probabilities, axis=1)
    correct = predictions == labels
    error = 0.0
    edges = np.linspace(0.0, 1.0, bins + 1)
    for index in range(bins):
        lower, upper = edges[index], edges[index + 1]
        selected = (confidence > lower) & (confidence <= upper)
        if index == 0:
            selected |= confidence == 0.0
        if not np.any(selected):
            continue
        error += float(selected.mean()) * abs(
            float(correct[selected].mean()) - float(confidence[selected].mean())
        )
    return error


def _diagnostic_metrics(
    probabilities: np.ndarray,
    labels: np.ndarray,
    participant_ids: np.ndarray,
    labels_by_id: dict[int, str],
) -> dict[str, Any]:
    metrics = classification_metrics(probabilities, labels, participant_ids)
    predictions = np.argmax(probabilities, axis=1)
    confusion = np.zeros((probabilities.shape[1], probabilities.shape[1]), dtype=np.int32)
    np.add.at(confusion, (labels, predictions), 1)
    groups: list[dict[str, Any]] = []
    for truth, predicted in np.argwhere(confusion > 0):
        if truth == predicted:
            continue
        groups.append(
            {
                "true_class_id": int(truth),
                "true_label": labels_by_id[int(truth)],
                "predicted_class_id": int(predicted),
                "predicted_label": labels_by_id[int(predicted)],
                "count": int(confusion[truth, predicted]),
            }
        )
    groups.sort(key=lambda item: (-item["count"], item["true_label"], item["predicted_label"]))
    supported_f1 = sorted(
        item["f1"] for item in metrics["per_class"] if item["support"] > 0
    )
    decile_count = max(1, int(np.ceil(len(supported_f1) * 0.1)))
    metrics.update(
        {
            "ece_15_bin": expected_calibration_error(probabilities, labels),
            "worst_decile_mean_f1": float(np.mean(supported_f1[:decile_count])),
            "top_confusions": groups[:50],
            "confusion_matrix": confusion.tolist(),
        }
    )
    return metrics


def _stride_proxy(
    x: np.ndarray, frame_mask: np.ndarray, stride: int
) -> tuple[np.ndarray, np.ndarray]:
    output = np.zeros_like(x)
    masks = np.zeros_like(frame_mask)
    for index in range(len(x)):
        selected = np.flatnonzero(frame_mask[index])[::stride]
        output[index, : len(selected)] = x[index, selected]
        masks[index, : len(selected)] = True
    return output, masks


def _hand_dropout_proxy(
    x: np.ndarray, frame_mask: np.ndarray, every: int = 4
) -> np.ndarray:
    """Zero both v3.0 hand blocks on deterministic real frames; pose is retained."""
    output = np.asarray(x, dtype=np.float32).copy()
    for index in range(len(output)):
        selected = np.flatnonzero(frame_mask[index])[::every]
        output[index, selected, :126] = 0.0
    return output


def evaluate_validation(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    config = json.loads(
        (args.run_dir / "config" / "experiment.json").read_text(encoding="utf-8")
    )
    dataset_dir = Path(config["dataset_dir"])
    datasets = {}
    for name in (
        "val",
        "diagnostic_validation_stress",
        "diagnostic_reused_positive",
    ):
        datasets[name] = _load_split(dataset_dir / f"{name}.npz")
    results: dict[str, Any] = {}
    for branch in BRANCHES:
        results[branch] = {}
        for seed in SEEDS:
            checkpoint = args.run_dir / "models" / branch / f"seed_{seed}" / "best.keras"
            if not checkpoint.is_file():
                raise FileNotFoundError(f"missing trained checkpoint: {checkpoint}")
            model = tf.keras.models.load_model(checkpoint, compile=False, safe_mode=False)
            seed_results = {}
            for name, (x, y, mask, _, pids) in datasets.items():
                probabilities = predict_clip_probs(model, branch, x, mask, 32)
                seed_results[name] = classification_metrics(probabilities, y, pids)
            results[branch][str(seed)] = seed_results
    summary_by_branch = {}
    for branch in BRANCHES:
        val_results = [results[branch][str(seed)]["val"] for seed in SEEDS]
        summary_by_branch[branch] = {
            "mean_val_top1": float(np.mean([item["top1"] for item in val_results])),
            "std_val_top1": float(np.std([item["top1"] for item in val_results])),
            "mean_val_top5": float(np.mean([item["top5"] for item in val_results])),
            "mean_val_macro_f1": float(
                np.mean([item["macro_f1"] for item in val_results])
            ),
        }
    winner = max(
        BRANCHES,
        key=lambda branch: (
            summary_by_branch[branch]["mean_val_top1"],
            summary_by_branch[branch]["mean_val_macro_f1"],
        ),
    )
    report = {
        "experiment": EXPERIMENT,
        "stage": "validation_only_selection",
        "results": results,
        "summary_by_branch": summary_by_branch,
        "provisional_winner": winner,
        "selection_metric": "mean validation clip top-1; macro-F1 tie-break",
        "protected_test_accessed": False,
        "passed": True,
        "next": "review and freeze branch before separately authorized protected test",
    }
    _write_json(args.run_dir / "metrics" / "validation_metrics.json", report)
    return report


def freeze_selection(args: argparse.Namespace) -> dict[str, Any]:
    config_path = args.run_dir / "config" / "experiment.json"
    validation_path = args.run_dir / "metrics" / "validation_metrics.json"
    freeze_path = args.run_dir / "config" / "selection_freeze.json"
    if freeze_path.exists():
        raise FileExistsError(f"selection is already frozen: {freeze_path}")
    config = _read_json(config_path)
    validation = _read_json(validation_path)
    if not validation.get("passed"):
        raise ValueError("validation report did not pass")
    branch = str(validation.get("provisional_winner", ""))
    if branch not in BRANCHES:
        raise ValueError(f"invalid validation-selected branch: {branch}")
    dataset_dir = Path(config["dataset_dir"])
    test_path = dataset_dir / "test.npz"
    expected_test_hash = str(config["dataset_hashes"]["test"])
    actual_test_hash = _sha256(test_path)
    if actual_test_hash != expected_test_hash:
        raise ValueError("protected test tensor hash does not match experiment config")
    checkpoints = []
    for seed in SEEDS:
        checkpoint = args.run_dir / "models" / branch / f"seed_{seed}" / "best.keras"
        if not checkpoint.is_file():
            raise FileNotFoundError(f"missing selected checkpoint: {checkpoint}")
        checkpoints.append(
            {
                "seed": seed,
                "path": str(checkpoint.resolve()),
                "sha256": _sha256(checkpoint),
            }
        )
    report = {
        "experiment": EXPERIMENT,
        "stage": "validation_selection_freeze",
        "frozen_branch": branch,
        "seeds": list(SEEDS),
        "selection_metric": validation["selection_metric"],
        "validation_summary": validation["summary_by_branch"][branch],
        "experiment_config_sha256": _sha256(config_path),
        "validation_metrics_sha256": _sha256(validation_path),
        "protected_test": {
            "path": str(test_path.resolve()),
            "sha256": actual_test_hash,
            "rows_expected": 2620,
            "accessed": False,
        },
        "checkpoints": checkpoints,
        "production_authorized": False,
        "passed": True,
        "next": "run the separately authorized one-time protected-test evaluation",
    }
    _write_json(freeze_path, report)
    _write_json(args.run_dir / "logs" / "selection_freeze_summary.json", report)
    return report


def _verified_freeze(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    config_path = run_dir / "config" / "experiment.json"
    validation_path = run_dir / "metrics" / "validation_metrics.json"
    freeze = _read_json(run_dir / "config" / "selection_freeze.json")
    config = _read_json(config_path)
    if not freeze.get("passed"):
        raise ValueError("selection freeze did not pass")
    if freeze["experiment_config_sha256"] != _sha256(config_path):
        raise ValueError("experiment config changed after selection freeze")
    if freeze["validation_metrics_sha256"] != _sha256(validation_path):
        raise ValueError("validation report changed after selection freeze")
    test_path = Path(freeze["protected_test"]["path"])
    if freeze["protected_test"]["sha256"] != _sha256(test_path):
        raise ValueError("protected test tensor changed after selection freeze")
    for checkpoint in freeze["checkpoints"]:
        if checkpoint["sha256"] != _sha256(Path(checkpoint["path"])):
            raise ValueError(f"selected checkpoint changed: {checkpoint['path']}")
    return freeze, config


def evaluate_protected_test(args: argparse.Namespace) -> dict[str, Any]:
    if not args.confirm_protected_test_access:
        raise ValueError("protected test access requires --confirm-protected-test-access")
    metrics_path = args.run_dir / "metrics" / "protected_test_metrics.json"
    receipt_path = args.run_dir / "logs" / "protected_test_access.json"
    if metrics_path.exists():
        raise FileExistsError("protected test evaluation is already complete")
    if receipt_path.exists() and not args.resume:
        raise FileExistsError(
            "protected test access already started; use --resume only to recover that run"
        )
    freeze, config = _verified_freeze(args.run_dir)
    receipt = {
        "experiment": EXPERIMENT,
        "stage": "protected_test_access",
        "freeze_sha256": _sha256(args.run_dir / "config" / "selection_freeze.json"),
        "status": "started",
        "passed": False,
    }
    _write_json(receipt_path, receipt)

    import tensorflow as tf

    x, y, mask, _, participant_ids = _load_split(
        Path(freeze["protected_test"]["path"])
    )
    if len(x) != int(freeze["protected_test"]["rows_expected"]):
        raise ValueError("protected test row count does not match selection freeze")
    vocab = _read_json(Path(config["dataset_dir"]) / "vocab.json")
    labels_by_id = {int(class_id): label for label, class_id in vocab.items()}
    branch = str(freeze["frozen_branch"])
    probabilities: dict[str, list[np.ndarray]] = {
        "native": [],
        "stride_2_proxy": [],
        "stride_3_proxy": [],
        "hand_dropout_25pct_proxy": [],
    }
    per_seed: dict[str, Any] = {}
    for checkpoint in freeze["checkpoints"]:
        tf.keras.backend.clear_session()
        model = tf.keras.models.load_model(
            checkpoint["path"], compile=False, safe_mode=False
        )
        seed = str(checkpoint["seed"])
        native = predict_clip_probs(model, branch, x, mask, 32)
        probabilities["native"].append(native)
        stride2_x, stride2_mask = _stride_proxy(x, mask, 2)
        probabilities["stride_2_proxy"].append(
            predict_clip_probs(model, branch, stride2_x, stride2_mask, 32)
        )
        del stride2_x, stride2_mask
        stride3_x, stride3_mask = _stride_proxy(x, mask, 3)
        probabilities["stride_3_proxy"].append(
            predict_clip_probs(model, branch, stride3_x, stride3_mask, 32)
        )
        del stride3_x, stride3_mask
        missing_x = _hand_dropout_proxy(x, mask)
        probabilities["hand_dropout_25pct_proxy"].append(
            predict_clip_probs(model, branch, missing_x, mask, 32)
        )
        del missing_x
        per_seed[seed] = classification_metrics(native, y, participant_ids)
    ensemble = {
        name: np.mean(np.stack(seed_probs, axis=0), axis=0)
        for name, seed_probs in probabilities.items()
    }
    diagnostics = {
        name: _diagnostic_metrics(probs, y, participant_ids, labels_by_id)
        for name, probs in ensemble.items()
    }
    native_top1 = diagnostics["native"]["top1"]
    degradation = {
        name: native_top1 - metrics["top1"]
        for name, metrics in diagnostics.items()
        if name != "native"
    }
    np.savez_compressed(
        args.run_dir / "metrics" / "protected_test_predictions.npz",
        labels=y,
        participant_ids=participant_ids,
        probabilities=ensemble["native"],
    )
    report = {
        "experiment": EXPERIMENT,
        "stage": "one_time_protected_test",
        "frozen_branch": branch,
        "freeze_sha256": receipt["freeze_sha256"],
        "per_seed_native": per_seed,
        "ensemble": diagnostics,
        "top1_degradation_from_native": degradation,
        "diagnostic_limitations": {
            "stride": "deterministic temporal stride proxies; not a claim of measured camera FPS",
            "missing_landmark": (
                "zeros both 63-value hand blocks on every fourth real frame while "
                "retaining pose"
            ),
            "no_sign_oov": "not measured by the isolated positive protected test",
            "end_to_end": "clip-level isolated-sign evaluation; not streaming phrase accuracy",
        },
        "protected_test_accessed": True,
        "production_authorized": False,
        "passed": True,
        "next": (
            "analyze class, signer, confusion, degradation, and calibration evidence "
            "before Phase 2"
        ),
    }
    _write_json(metrics_path, report)
    receipt.update({"status": "complete", "passed": True})
    _write_json(receipt_path, receipt)
    return report


def check(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    config = args.run_dir / "config" / "experiment.json"
    smoke_summary = args.run_dir / "smoke" / "smoke_summary.json"
    if not config.is_file():
        errors.append("missing experiment config")
    if args.require_smoke:
        if not smoke_summary.is_file():
            errors.append("missing smoke summary")
        elif not json.loads(smoke_summary.read_text(encoding="utf-8")).get("passed"):
            errors.append("smoke did not pass")
    if args.require_models:
        for branch in BRANCHES:
            for seed in SEEDS:
                best = args.run_dir / "models" / branch / f"seed_{seed}" / "best.keras"
                if not best.is_file():
                    errors.append(f"missing model: {best}")
    if args.require_validation:
        validation = args.run_dir / "metrics" / "validation_metrics.json"
        if not validation.is_file():
            errors.append("missing validation metrics")
        elif not json.loads(validation.read_text(encoding="utf-8")).get("passed"):
            errors.append("validation evaluation did not pass")
    if args.require_freeze:
        try:
            _verified_freeze(args.run_dir)
        except (FileNotFoundError, KeyError, ValueError) as exc:
            errors.append(f"selection freeze invalid: {exc}")
    protected_test_accessed = False
    if args.require_protected_test:
        protected = args.run_dir / "metrics" / "protected_test_metrics.json"
        if not protected.is_file():
            errors.append("missing protected test metrics")
        else:
            protected_data = json.loads(protected.read_text(encoding="utf-8"))
            protected_test_accessed = bool(protected_data.get("protected_test_accessed"))
            if not protected_data.get("passed") or not protected_test_accessed:
                errors.append("protected test evaluation did not pass")
    result = {
        "run_dir": str(args.run_dir.resolve()),
        "errors": errors,
        "passed": not errors,
        "protected_test_accessed": protected_test_accessed,
    }
    _write_json(args.run_dir / "logs" / "check_report.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--warm-start", type=Path, default=DEFAULT_WARM_START)
    for command in (
        "smoke",
        "train",
        "evaluate-validation",
        "freeze-selection",
        "evaluate-protected-test",
        "check",
    ):
        child = sub.add_parser(command)
        child.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
        if command == "train":
            child.add_argument("--resume", action="store_true")
            child.add_argument("--epochs", type=int, default=None)
        if command == "evaluate-protected-test":
            child.add_argument("--confirm-protected-test-access", action="store_true")
            child.add_argument("--resume", action="store_true")
        if command == "check":
            child.add_argument("--require-smoke", action="store_true")
            child.add_argument("--require-models", action="store_true")
            child.add_argument("--require-validation", action="store_true")
            child.add_argument("--require-freeze", action="store_true")
            child.add_argument("--require-protected-test", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "prepare":
        result = prepare(args)
    elif args.command == "smoke":
        result = smoke(args)
    elif args.command == "train":
        result = train(args)
    elif args.command == "evaluate-validation":
        result = evaluate_validation(args)
    elif args.command == "freeze-selection":
        result = freeze_selection(args)
    elif args.command == "evaluate-protected-test":
        result = evaluate_protected_test(args)
    else:
        result = check(args)
    console_result = result
    if args.command == "evaluate-protected-test":
        native = result["ensemble"]["native"]
        console_result = {
            "experiment": result["experiment"],
            "stage": result["stage"],
            "frozen_branch": result["frozen_branch"],
            "native_ensemble": {
                key: native[key]
                for key in (
                    "rows",
                    "top1",
                    "top5",
                    "macro_f1",
                    "ece_15_bin",
                    "worst_decile_mean_f1",
                )
            },
            "top1_degradation_from_native": result[
                "top1_degradation_from_native"
            ],
            "metrics_path": str(
                (args.run_dir / "metrics" / "protected_test_metrics.json").resolve()
            ),
            "predictions_path": str(
                (args.run_dir / "metrics" / "protected_test_predictions.npz").resolve()
            ),
            "protected_test_accessed": True,
            "production_authorized": False,
            "passed": result["passed"],
        }
    print(json.dumps(console_result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
