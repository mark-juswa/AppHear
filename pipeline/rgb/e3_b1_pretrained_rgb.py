"""E3-B1 improved RGB pilot using a frozen frame encoder.

This is experiment-only tooling. It keeps the E3-B0 strict-support split, extracts cropped RGB
frames, converts them to frozen MobileNetV3 frame embeddings, trains a small temporal head, and
writes every output under the requested run directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_SOURCE_RUN = Path("artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support")
DEFAULT_OUTPUT_ROOT = Path("artifacts/recognition_upgrade/e3_rgb_b1")


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


def _estimate_uint8_size(rows: int, frames: int, image_size: int) -> dict[str, Any]:
    bytes_uint8 = rows * frames * image_size * image_size * 3
    return {
        "rows": rows,
        "frames": frames,
        "image_size": image_size,
        "uint8_frame_bytes": bytes_uint8,
        "uint8_frame_mib": bytes_uint8 / (1024 * 1024),
    }


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output_root / args.run_id
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True, exist_ok=True)

    source_manifest = args.source_run / "pilot_manifest.csv"
    if not source_manifest.exists():
        raise FileNotFoundError(f"missing source manifest: {source_manifest}")
    rows = _read_csv(source_manifest)
    source_config_path = args.source_run / "pilot_config.json"
    if source_config_path.exists():
        source_config = json.loads(source_config_path.read_text(encoding="utf-8"))
        classes = list(source_config["classes"])
    else:
        class_pairs = sorted({(int(row["label_index"]), row["gloss"]) for row in rows})
        classes = [gloss for _, gloss in class_pairs]

    config = {
        "experiment": "e3_b1_pretrained_rgb_pilot_v1",
        "purpose": "bounded improved RGB pilot; frozen frame encoder plus temporal head",
        "run_dir": str(output.resolve()),
        "source_run": str(args.source_run.resolve()),
        "source_manifest": str(source_manifest.resolve()),
        "class_count": len(classes),
        "classes": classes,
        "frames": args.frames,
        "image_size": args.image_size,
        "crop_mode": args.crop_mode,
        "encoder": args.encoder,
        "weights": args.weights,
        "embedding_batch_size": args.embedding_batch_size,
        "train_batch_size": args.train_batch_size,
        "epochs": args.epochs,
        "estimated_size": _estimate_uint8_size(len(rows), args.frames, args.image_size),
        "baseline_reference": {
            "run": "artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support",
            "random_baseline": 1.0 / len(classes),
            "b0_val_accuracy": 0.0714,
            "b0_test_accuracy": 0.1071,
        },
        "outputs": {
            "frames_npz": "dataset/rgb_frames_uint8.npz",
            "features_npz": "dataset/rgb_frame_features.npz",
            "latest_model": "models/latest.keras",
            "best_model": "models/best.keras",
            "metrics_json": "metrics/metrics.json",
            "prediction_diagnostic": "metrics/prediction_diagnostic.json",
        },
        "warnings": [
            "This is not production training.",
            "Preferred weights mode is imagenet. weights=none is a plumbing fallback only.",
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


def _crop_frame(frame: np.ndarray, mode: str) -> np.ndarray:
    height, width = frame.shape[:2]
    if mode == "full_frame":
        return frame
    if mode == "upper_body_center":
        x0 = int(width * 0.08)
        x1 = int(width * 0.92)
        y0 = 0
        y1 = int(height * 0.92)
        return frame[y0:y1, x0:x1]
    raise ValueError(f"unsupported crop mode: {mode}")


def _read_video_frames(path: Path, frames: int, image_size: int, crop_mode: str) -> tuple[np.ndarray, dict[str, Any]]:
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
            frame = _crop_frame(frame, crop_mode)
            frame = cv2.resize(frame, (image_size, image_size), interpolation=cv2.INTER_AREA)
            sampled.append(frame.astype(np.uint8))
    finally:
        capture.release()
    return (
        np.stack(sampled, axis=0),
        {"frame_count": frame_total, "fps": fps, "width": width, "height": height},
    )


def _load_or_extract_frames(run_dir: Path, config: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dataset_dir = run_dir / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    frames_path = dataset_dir / "rgb_frames_uint8.npz"
    if frames_path.exists():
        data = np.load(frames_path)
        return data["x"], data["y"], data["split_index"]

    rows = _read_csv(run_dir / "pilot_manifest.csv")
    x_values = []
    y_values = []
    split_values = []
    metadata_rows = []
    split_to_index = {"train": 0, "val": 1, "test": 2}
    for index, row in enumerate(rows, start=1):
        print(f"[e3-b1-rgb] extract {index}/{len(rows)} {row['split']} {row['gloss']}")
        frames, metadata = _read_video_frames(
            Path(row["video_path"]), config["frames"], config["image_size"], config["crop_mode"]
        )
        x_values.append(frames)
        y_values.append(int(row["label_index"]))
        split_values.append(split_to_index[row["split"]])
        metadata_rows.append({**row, **metadata})
    x = np.stack(x_values, axis=0).astype(np.uint8)
    y = np.asarray(y_values, dtype=np.int64)
    split_index = np.asarray(split_values, dtype=np.int64)
    np.savez_compressed(frames_path, x=x, y=y, split_index=split_index)
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


def _build_encoder(config: dict[str, Any]):
    import tensorflow as tf

    weights = None if config["weights"] == "none" else config["weights"]
    if config["encoder"] != "mobilenetv3small":
        raise ValueError(f"unsupported encoder: {config['encoder']}")
    encoder = tf.keras.applications.MobileNetV3Small(
        input_shape=(config["image_size"], config["image_size"], 3),
        include_top=False,
        weights=weights,
        pooling="avg",
        include_preprocessing=True,
    )
    encoder.trainable = False
    return encoder


def _load_or_extract_features(
    run_dir: Path, config: dict[str, Any], x: np.ndarray, y: np.ndarray, split_index: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    features_path = run_dir / "dataset" / "rgb_frame_features.npz"
    if features_path.exists():
        data = np.load(features_path)
        return data["features"], data["y"], data["split_index"]

    encoder = _build_encoder(config)
    flat = x.reshape((-1, config["image_size"], config["image_size"], 3)).astype(np.float32)
    print(f"[e3-b1-rgb] embedding {flat.shape[0]} frames with {config['encoder']}")
    embeddings = encoder.predict(flat, batch_size=config["embedding_batch_size"], verbose=2)
    features = embeddings.reshape((x.shape[0], config["frames"], embeddings.shape[-1])).astype(np.float32)
    np.savez_compressed(features_path, features=features, y=y, split_index=split_index)
    return features, y, split_index


def _build_temporal_head(frames: int, feature_dim: int, classes: int):
    import tensorflow as tf

    inputs = tf.keras.Input(shape=(frames, feature_dim), name="frame_features")
    x = tf.keras.layers.LayerNormalization()(inputs)
    x = tf.keras.layers.Conv1D(128, 3, padding="same", activation="relu")(x)
    x = tf.keras.layers.Dropout(0.25)(x)
    x = tf.keras.layers.Conv1D(128, 3, padding="same", activation="relu")(x)
    x = tf.keras.layers.GlobalAveragePooling1D()(x)
    x = tf.keras.layers.Dense(64, activation="relu")(x)
    x = tf.keras.layers.Dropout(0.25)(x)
    outputs = tf.keras.layers.Dense(classes, activation="softmax")(x)
    model = tf.keras.Model(inputs, outputs)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=5e-4),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def run(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    for relative in ("dataset", "logs", "metrics", "models"):
        (run_dir / relative).mkdir(parents=True, exist_ok=True)
    latest_path = run_dir / "models" / "latest.keras"
    best_path = run_dir / "models" / "best.keras"
    if latest_path.exists() and not args.resume:
        raise FileExistsError(f"latest model exists; rerun with --resume: {latest_path}")

    start = time.perf_counter()
    frames, y, split_index = _load_or_extract_frames(run_dir, config)
    features, y, split_index = _load_or_extract_features(run_dir, config, frames, y, split_index)
    train_mask = split_index == 0
    val_mask = split_index == 1
    test_mask = split_index == 2

    if args.resume and latest_path.exists():
        model = tf.keras.models.load_model(latest_path)
        initial_epoch = int((run_dir / "logs" / "epoch_count.txt").read_text(encoding="utf-8"))
    else:
        model = _build_temporal_head(config["frames"], features.shape[-1], config["class_count"])
        initial_epoch = 0

    history_path = run_dir / "logs" / "history.csv"
    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(str(best_path), monitor="val_accuracy", mode="max", save_best_only=True),
        tf.keras.callbacks.CSVLogger(str(history_path), append=history_path.exists()),
    ]
    history = model.fit(
        features[train_mask],
        y[train_mask],
        validation_data=(features[val_mask], y[val_mask]),
        batch_size=config["train_batch_size"],
        epochs=initial_epoch + config["epochs"],
        initial_epoch=initial_epoch,
        callbacks=callbacks,
        verbose=2,
    )
    model.save(latest_path)
    total_epochs = initial_epoch + config["epochs"]
    (run_dir / "logs" / "epoch_count.txt").write_text(str(total_epochs), encoding="utf-8")

    metrics = _evaluate_and_diagnose(run_dir, config, model, features, y, split_index)
    metrics.update(
        {
            "experiment": config["experiment"],
            "run_dir": str(run_dir.resolve()),
            "warning": "Bounded improved RGB pilot only. Not a production accuracy claim.",
            "feature_shape": list(features.shape),
            "class_count": config["class_count"],
            "epochs_this_command": config["epochs"],
            "epoch_count_total": total_epochs,
            "history": {key: [float(v) for v in values] for key, values in history.history.items()},
            "elapsed_seconds": time.perf_counter() - start,
            "passed": True,
        }
    )
    (run_dir / "metrics" / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (run_dir / "metrics" / "metrics.md").write_text(_metrics_markdown(metrics), encoding="utf-8")
    return metrics


def _evaluate_and_diagnose(
    run_dir: Path, config: dict[str, Any], model: Any, features: np.ndarray, y: np.ndarray, split_index: np.ndarray
) -> dict[str, Any]:
    classes = config["classes"]
    split_names = {0: "train", 1: "val", 2: "test"}
    probs = model.predict(features, batch_size=config["train_batch_size"], verbose=0)
    pred = np.argmax(probs, axis=1)
    conf = np.max(probs, axis=1)
    result: dict[str, Any] = {"split_counts": {}, "eval": {}, "diagnostic": {}}
    for split_id, split_name in split_names.items():
        idxs = np.where(split_index == split_id)[0]
        correct = pred[idxs] == y[idxs]
        result["split_counts"][split_name] = int(len(idxs))
        result["eval"][split_name] = {
            "accuracy": float(np.mean(correct)) if len(idxs) else None,
            "mean_confidence": float(np.mean(conf[idxs])) if len(idxs) else None,
        }
        predicted_counts: dict[str, int] = {}
        per_class: dict[str, Any] = {}
        for class_index, class_name in enumerate(classes):
            class_idxs = [int(i) for i in idxs if int(y[i]) == class_index]
            if not class_idxs:
                continue
            class_correct = sum(int(pred[i]) == class_index for i in class_idxs)
            per_class[class_name] = {
                "count": len(class_idxs),
                "correct": int(class_correct),
                "accuracy": float(class_correct / len(class_idxs)),
            }
        for class_index in pred[idxs]:
            class_name = classes[int(class_index)]
            predicted_counts[class_name] = predicted_counts.get(class_name, 0) + 1
        result["diagnostic"][split_name] = {
            "predicted_class_counts": dict(sorted(predicted_counts.items())),
            "per_class": per_class,
        }
    (run_dir / "metrics" / "prediction_diagnostic.json").write_text(
        json.dumps(result["diagnostic"], indent=2), encoding="utf-8"
    )
    return result


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = [
        "pilot_config.json",
        "pilot_manifest.csv",
        "dataset/rgb_frames_uint8.npz",
        "dataset/rgb_frame_features.npz",
        "dataset/dataset_manifest.csv",
        "models/latest.keras",
        "models/best.keras",
        "logs/history.csv",
        "logs/epoch_count.txt",
        "metrics/metrics.json",
        "metrics/metrics.md",
        "metrics/prediction_diagnostic.json",
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
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors, "metrics": metrics}
    (run_dir / "check_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join(
        [
            "# E3-B1 Improved RGB Pilot",
            "",
            "This is a bounded RGB improvement test, not production training.",
            "",
            "## Settings",
            "",
            f"- Classes: {config['class_count']}",
            f"- Clips: {config['estimated_size']['rows']}",
            f"- Frames per clip: {config['frames']}",
            f"- Crop mode: {config['crop_mode']}",
            f"- Image size: {config['image_size']}x{config['image_size']}",
            f"- Encoder: {config['encoder']}",
            f"- Weights: {config['weights']}",
            f"- Estimated uint8 frame size: {config['estimated_size']['uint8_frame_mib']:.2f} MiB",
            f"- Epochs per command: {config['epochs']}",
            "",
            "## Run",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b1_pretrained_rgb run --run-dir "{run_dir}"',
            "```",
            "",
            "## Resume",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b1_pretrained_rgb run --run-dir "{run_dir}" --resume',
            "```",
            "",
            "## Check",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b1_pretrained_rgb check --run-dir "{run_dir}"',
            "```",
            "",
            "If `weights=imagenet` fails because the weights are not cached or downloadable, stop and report the exact error.",
            "",
        ]
    )


def _metrics_markdown(metrics: dict[str, Any]) -> str:
    evals = metrics["eval"]
    return "\n".join(
        [
            "# E3-B1 Improved RGB Pilot Metrics",
            "",
            "Bounded feasibility result only. Not a production accuracy claim.",
            "",
            f"- Passed: {metrics['passed']}",
            f"- Feature shape: {metrics['feature_shape']}",
            f"- Split counts: {metrics['split_counts']}",
            f"- Total epochs: {metrics['epoch_count_total']}",
            f"- Train accuracy: {evals['train'].get('accuracy')}",
            f"- Val accuracy: {evals['val'].get('accuracy')}",
            f"- Test accuracy: {evals['test'].get('accuracy')}",
            f"- Elapsed seconds: {metrics['elapsed_seconds']:.2f}",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="E3-B1 improved RGB pilot")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--run-id", default="pilot_01_mobilenetv3_upper_body")
    prepare_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    prepare_parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    prepare_parser.add_argument("--frames", type=int, default=16)
    prepare_parser.add_argument("--image-size", type=int, default=160)
    prepare_parser.add_argument("--crop-mode", choices=["upper_body_center", "full_frame"], default="upper_body_center")
    prepare_parser.add_argument("--encoder", choices=["mobilenetv3small"], default="mobilenetv3small")
    prepare_parser.add_argument("--weights", choices=["imagenet", "none"], default="imagenet")
    prepare_parser.add_argument("--embedding-batch-size", type=int, default=32)
    prepare_parser.add_argument("--train-batch-size", type=int, default=8)
    prepare_parser.add_argument("--epochs", type=int, default=8)
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
        print(f"[rgb/e3-b1] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
