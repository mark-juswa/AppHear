"""Bounded E3-B0 RGB pilot package.

This is an experiment-only runner. It extracts a bounded RGB tensor set from the passed
preflight manifest, trains a small temporal CNN, evaluates train/val/test splits, and writes all
outputs under the requested run directory. It does not modify Android or production recognizer
assets.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_PREFLIGHT_RUN = Path("artifacts/recognition_upgrade/e3_rgb_b0/preflight_02")
DEFAULT_OUTPUT_ROOT = Path("artifacts/recognition_upgrade/e3_rgb_b0")
DEFAULT_SEED = 280728


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _selected_classes(preflight_run: Path, class_count: int) -> list[str]:
    rows = _read_csv(preflight_run / "selected_classes.csv")
    classes = [row["gloss"] for row in rows[:class_count]]
    if len(classes) < class_count:
        raise ValueError(f"need {class_count} classes, found {len(classes)}")
    return classes


def _select_manifest(
    preflight_run: Path,
    classes: list[str],
    train_per_class: int,
    val_per_class: int,
    test_per_class: int,
    seed: int,
) -> list[dict[str, Any]]:
    rows = _read_csv(preflight_run / "pilot_manifest.csv")
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    class_set = set(classes)
    for row in rows:
        if row["gloss"] in class_set:
            grouped[(row["gloss"], row["split"])].append(row)
    rng = random.Random(seed)
    selected = []
    limits = {"train": train_per_class, "val": val_per_class, "test": test_per_class}
    for gloss in classes:
        for split, limit in limits.items():
            choices = grouped[(gloss, split)][:]
            rng.shuffle(choices)
            if len(choices) < limit:
                raise ValueError(f"{gloss}/{split}: need {limit}, found {len(choices)}")
            for row in choices[:limit]:
                selected.append(
                    {
                        "source": row.get("source", "asl_citizen"),
                        "split": split,
                        "signer_id": row["signer_id"],
                        "gloss": gloss,
                        "video_path": row["video_path"],
                    }
                )
    selected.sort(key=lambda row: (row["split"], row["gloss"], row["video_path"]))
    return selected


def _estimate_size(rows: int, frames: int, image_size: int) -> dict[str, Any]:
    bytes_float32 = rows * frames * image_size * image_size * 3 * 4
    return {
        "rows": rows,
        "frames": frames,
        "image_size": image_size,
        "float32_tensor_bytes": bytes_float32,
        "float32_tensor_mib": bytes_float32 / (1024 * 1024),
    }


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output_root / args.run_id
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True, exist_ok=True)
    classes = _selected_classes(args.preflight_run, args.class_count)
    rows = _select_manifest(
        args.preflight_run,
        classes,
        args.train_per_class,
        args.val_per_class,
        args.test_per_class,
        args.seed,
    )
    class_to_index = {gloss: index for index, gloss in enumerate(classes)}
    for row in rows:
        row["label_index"] = class_to_index[row["gloss"]]
    config = {
        "experiment": "e3_b0_rgb_bounded_pilot_v1",
        "purpose": "bounded RGB feasibility pilot; not production training",
        "run_dir": str(output.resolve()),
        "preflight_run": str(args.preflight_run.resolve()),
        "seed": args.seed,
        "class_count": args.class_count,
        "classes": classes,
        "train_per_class": args.train_per_class,
        "val_per_class": args.val_per_class,
        "test_per_class": args.test_per_class,
        "frames": args.frames,
        "image_size": args.image_size,
        "batch_size": args.batch_size,
        "epochs": args.epochs,
        "estimated_size": _estimate_size(len(rows), args.frames, args.image_size),
        "outputs": {
            "dataset_npz": "dataset/rgb_pilot_dataset.npz",
            "best_model": "models/best.keras",
            "latest_model": "models/latest.keras",
            "history_csv": "logs/history.csv",
            "metrics_json": "metrics/metrics.json",
        },
        "warnings": [
            "This is not production training.",
            "Do not compare as final accuracy without the registered E3 protocol.",
            "Android integration remains blocked.",
        ],
    }
    _write_csv(
        output / "pilot_manifest.csv",
        rows,
        ["source", "split", "signer_id", "gloss", "label_index", "video_path"],
    )
    (output / "pilot_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def _sample_indices(frame_count: int, frame_count_out: int) -> list[int]:
    if frame_count <= 0:
        return [0] * frame_count_out
    if frame_count_out <= 1:
        return [max(0, frame_count // 2)]
    return [
        min(frame_count - 1, round(i * (frame_count - 1) / (frame_count_out - 1)))
        for i in range(frame_count_out)
    ]


def _read_video_tensor(path: Path, frames: int, image_size: int) -> tuple[np.ndarray, dict[str, Any]]:
    import cv2  # type: ignore

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"could not open video: {path}")
    try:
        frame_total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        sampled = []
        for index in _sample_indices(frame_total, frames):
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            if not ok or frame is None:
                raise ValueError(f"failed reading frame {index} from {path}")
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (image_size, image_size), interpolation=cv2.INTER_AREA)
            sampled.append(frame.astype(np.float32) / 255.0)
    finally:
        capture.release()
    return (
        np.stack(sampled, axis=0),
        {"frame_count": frame_total, "fps": fps, "width": width, "height": height},
    )


def _build_model(frames: int, image_size: int, classes: int):
    import tensorflow as tf

    inputs = tf.keras.Input(shape=(frames, image_size, image_size, 3), name="rgb_frames")
    x = tf.keras.layers.TimeDistributed(
        tf.keras.layers.Conv2D(16, 3, strides=2, padding="same", activation="relu")
    )(inputs)
    x = tf.keras.layers.TimeDistributed(tf.keras.layers.BatchNormalization())(x)
    x = tf.keras.layers.TimeDistributed(tf.keras.layers.MaxPooling2D())(x)
    x = tf.keras.layers.TimeDistributed(
        tf.keras.layers.Conv2D(32, 3, strides=2, padding="same", activation="relu")
    )(x)
    x = tf.keras.layers.TimeDistributed(tf.keras.layers.BatchNormalization())(x)
    x = tf.keras.layers.TimeDistributed(tf.keras.layers.GlobalAveragePooling2D())(x)
    x = tf.keras.layers.Conv1D(64, 3, padding="same", activation="relu")(x)
    x = tf.keras.layers.Dropout(0.2)(x)
    x = tf.keras.layers.GlobalAveragePooling1D()(x)
    outputs = tf.keras.layers.Dense(classes, activation="softmax")(x)
    model = tf.keras.Model(inputs, outputs)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def _load_or_extract_dataset(run_dir: Path, config: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dataset_dir = run_dir / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = dataset_dir / "rgb_pilot_dataset.npz"
    if dataset_path.exists():
        data = np.load(dataset_path)
        return data["x"], data["y"], data["split_index"]

    rows = _read_csv(run_dir / "pilot_manifest.csv")
    x_values = []
    y_values = []
    split_values = []
    metadata_rows = []
    split_to_index = {"train": 0, "val": 1, "test": 2}
    for index, row in enumerate(rows, start=1):
        print(f"[e3-b0-pilot] extract {index}/{len(rows)} {row['split']} {row['gloss']}")
        tensor, metadata = _read_video_tensor(
            Path(row["video_path"]), config["frames"], config["image_size"]
        )
        x_values.append(tensor)
        y_values.append(int(row["label_index"]))
        split_values.append(split_to_index[row["split"]])
        metadata_rows.append({**row, **metadata})
    x = np.stack(x_values, axis=0).astype(np.float32)
    y = np.asarray(y_values, dtype=np.int64)
    split_index = np.asarray(split_values, dtype=np.int64)
    np.savez_compressed(dataset_path, x=x, y=y, split_index=split_index)
    _write_csv(
        dataset_dir / "dataset_manifest.csv",
        metadata_rows,
        [
            "source",
            "split",
            "signer_id",
            "gloss",
            "label_index",
            "video_path",
            "frame_count",
            "fps",
            "width",
            "height",
        ],
    )
    return x, y, split_index


def run(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    config_path = run_dir / "pilot_config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"missing pilot config: {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    run_dir.joinpath("models").mkdir(parents=True, exist_ok=True)
    run_dir.joinpath("logs").mkdir(parents=True, exist_ok=True)
    run_dir.joinpath("metrics").mkdir(parents=True, exist_ok=True)

    import tensorflow as tf

    tf.keras.utils.set_random_seed(config["seed"])
    start = time.perf_counter()
    x, y, split_index = _load_or_extract_dataset(run_dir, config)
    train_mask = split_index == 0
    val_mask = split_index == 1
    test_mask = split_index == 2

    latest_path = run_dir / "models" / "latest.keras"
    best_path = run_dir / "models" / "best.keras"
    if latest_path.exists() and not args.resume:
        raise FileExistsError(f"latest model exists; pass --resume to continue: {latest_path}")
    if latest_path.exists() and args.resume:
        model = tf.keras.models.load_model(latest_path)
        initial_epoch = int((run_dir / "logs" / "epoch_count.txt").read_text(encoding="utf-8"))
    else:
        model = _build_model(config["frames"], config["image_size"], config["class_count"])
        initial_epoch = 0

    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            filepath=str(best_path),
            monitor="val_accuracy",
            mode="max",
            save_best_only=True,
        ),
        tf.keras.callbacks.CSVLogger(str(run_dir / "logs" / "history.csv"), append=args.resume),
    ]
    history = model.fit(
        x[train_mask],
        y[train_mask],
        validation_data=(x[val_mask], y[val_mask]),
        batch_size=config["batch_size"],
        epochs=initial_epoch + config["epochs"],
        initial_epoch=initial_epoch,
        callbacks=callbacks,
        verbose=2,
    )
    model.save(latest_path)
    (run_dir / "logs" / "epoch_count.txt").write_text(
        str(initial_epoch + config["epochs"]), encoding="utf-8"
    )

    train_eval = model.evaluate(x[train_mask], y[train_mask], verbose=0, return_dict=True)
    val_eval = model.evaluate(x[val_mask], y[val_mask], verbose=0, return_dict=True)
    test_eval = model.evaluate(x[test_mask], y[test_mask], verbose=0, return_dict=True)
    metrics = {
        "experiment": config["experiment"],
        "run_dir": str(run_dir.resolve()),
        "warning": "Bounded pilot only. Not a production accuracy claim.",
        "dataset_shape": list(x.shape),
        "class_count": config["class_count"],
        "split_counts": {
            "train": int(np.sum(train_mask)),
            "val": int(np.sum(val_mask)),
            "test": int(np.sum(test_mask)),
        },
        "epochs_this_command": config["epochs"],
        "epoch_count_total": initial_epoch + config["epochs"],
        "train_eval": {key: float(value) for key, value in train_eval.items()},
        "val_eval": {key: float(value) for key, value in val_eval.items()},
        "test_eval": {key: float(value) for key, value in test_eval.items()},
        "history": {key: [float(v) for v in values] for key, values in history.history.items()},
        "elapsed_seconds": time.perf_counter() - start,
        "passed": True,
    }
    (run_dir / "metrics" / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    (run_dir / "metrics" / "metrics.md").write_text(_metrics_markdown(metrics), encoding="utf-8")
    return metrics


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = [
        "pilot_config.json",
        "pilot_manifest.csv",
        "dataset/rgb_pilot_dataset.npz",
        "dataset/dataset_manifest.csv",
        "models/latest.keras",
        "models/best.keras",
        "logs/history.csv",
        "logs/epoch_count.txt",
        "metrics/metrics.json",
        "metrics/metrics.md",
    ]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    metrics = {}
    metrics_path = run_dir / "metrics" / "metrics.json"
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        if not metrics.get("passed"):
            errors.append("metrics did not pass")
    result = {
        "run_dir": str(run_dir.resolve()),
        "passed": not errors,
        "errors": errors,
        "metrics": metrics,
    }
    (run_dir / "check_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join(
        [
            "# E3-B0 Bounded RGB Pilot",
            "",
            "This is a bounded feasibility run, not production training.",
            "",
            "## Settings",
            "",
            f"- Classes: {config['class_count']}",
            f"- Clips: {config['estimated_size']['rows']}",
            f"- Frames per clip: {config['frames']}",
            f"- Image size: {config['image_size']}x{config['image_size']}",
            f"- Estimated float32 tensor size: {config['estimated_size']['float32_tensor_mib']:.2f} MiB",
            f"- Epochs per command: {config['epochs']}",
            "",
            "## Run",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b0_pilot run --run-dir "{run_dir}"',
            "```",
            "",
            "## Resume",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b0_pilot run --run-dir "{run_dir}" --resume',
            "```",
            "",
            "## Check",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b0_pilot check --run-dir "{run_dir}"',
            "```",
            "",
            "Send back the full run directory after completion.",
            "",
        ]
    )


def _metrics_markdown(metrics: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# E3-B0 Bounded RGB Pilot Metrics",
            "",
            "Bounded feasibility result only. Not a production accuracy claim.",
            "",
            f"- Passed: {metrics['passed']}",
            f"- Dataset shape: {metrics['dataset_shape']}",
            f"- Split counts: {metrics['split_counts']}",
            f"- Total epochs: {metrics['epoch_count_total']}",
            f"- Train accuracy: {metrics['train_eval'].get('accuracy')}",
            f"- Val accuracy: {metrics['val_eval'].get('accuracy')}",
            f"- Test accuracy: {metrics['test_eval'].get('accuracy')}",
            f"- Elapsed seconds: {metrics['elapsed_seconds']:.2f}",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="E3-B0 bounded RGB pilot")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--run-id", default="pilot_01")
    prepare_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    prepare_parser.add_argument("--preflight-run", type=Path, default=DEFAULT_PREFLIGHT_RUN)
    prepare_parser.add_argument("--class-count", type=int, default=10)
    prepare_parser.add_argument("--train-per-class", type=int, default=8)
    prepare_parser.add_argument("--val-per-class", type=int, default=2)
    prepare_parser.add_argument("--test-per-class", type=int, default=2)
    prepare_parser.add_argument("--frames", type=int, default=16)
    prepare_parser.add_argument("--image-size", type=int, default=112)
    prepare_parser.add_argument("--batch-size", type=int, default=8)
    prepare_parser.add_argument("--epochs", type=int, default=3)
    prepare_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    prepare_parser.add_argument("--overwrite", action="store_true")

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--run-dir", type=Path, required=True)
    run_parser.add_argument("--resume", action="store_true")

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, KeyError, ValueError, OSError) as error:
        print(f"[rgb/e3-b0-pilot] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

