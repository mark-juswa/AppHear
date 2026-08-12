"""Tiny E3-B0 RGB tensor smoke.

This is a bounded plumbing test. It extracts a very small subset of frames, builds a tiny
TensorFlow model, runs one forward pass and one training step, then writes all outputs under the
requested run directory. It is not full RGB extraction or model training.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
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


def _load_manifest(path: Path) -> list[dict[str, str]]:
    rows = _read_csv(path)
    required = {"split", "signer_id", "gloss", "video_path"}
    missing = required - set(rows[0].keys()) if rows else required
    if missing:
        raise ValueError(f"manifest missing fields: {sorted(missing)}")
    return rows


def _select_rows(
    manifest: list[dict[str, str]],
    selected_classes_path: Path,
    class_count: int,
    train_per_class: int,
    val_per_class: int,
    test_per_class: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    selected_classes = [row["gloss"] for row in _read_csv(selected_classes_path)[:class_count]]
    selected_set = set(selected_classes)
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in manifest:
        if row["gloss"] in selected_set:
            grouped[(row["gloss"], row["split"])].append(row)

    rng = random.Random(seed)
    picked: list[dict[str, Any]] = []
    split_limits = {"train": train_per_class, "val": val_per_class, "test": test_per_class}
    for gloss in selected_classes:
        for split, limit in split_limits.items():
            choices = grouped[(gloss, split)][:]
            rng.shuffle(choices)
            if len(choices) < limit:
                raise ValueError(f"{gloss}/{split}: need {limit}, found {len(choices)}")
            for row in choices[:limit]:
                picked.append(
                    {
                        "source": row.get("source", "asl_citizen"),
                        "split": split,
                        "signer_id": row["signer_id"],
                        "gloss": gloss,
                        "video_path": row["video_path"],
                    }
                )
    picked.sort(key=lambda row: (row["split"], row["gloss"], row["video_path"]))
    return picked, selected_classes


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
        {
            "frame_count": frame_total,
            "fps": fps,
            "width": width,
            "height": height,
        },
    )


def _build_tiny_model(frames: int, image_size: int, classes: int):
    import tensorflow as tf

    inputs = tf.keras.Input(shape=(frames, image_size, image_size, 3), name="rgb_frames")
    x = tf.keras.layers.TimeDistributed(
        tf.keras.layers.Conv2D(8, 3, strides=2, padding="same", activation="relu")
    )(inputs)
    x = tf.keras.layers.TimeDistributed(tf.keras.layers.MaxPooling2D())(x)
    x = tf.keras.layers.TimeDistributed(
        tf.keras.layers.Conv2D(16, 3, strides=2, padding="same", activation="relu")
    )(x)
    x = tf.keras.layers.TimeDistributed(tf.keras.layers.GlobalAveragePooling2D())(x)
    x = tf.keras.layers.Conv1D(32, 3, padding="same", activation="relu")(x)
    x = tf.keras.layers.GlobalAveragePooling1D()(x)
    outputs = tf.keras.layers.Dense(classes, activation="softmax")(x)
    model = tf.keras.Model(inputs, outputs)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output_root / args.run_id
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True, exist_ok=True)
    tensors_dir = output / "tensors"
    models_dir = output / "models"
    logs_dir = output / "logs"
    tensors_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = args.preflight_run / "pilot_manifest.csv"
    selected_classes_path = args.preflight_run / "selected_classes.csv"
    manifest = _load_manifest(manifest_path)
    rows, classes = _select_rows(
        manifest,
        selected_classes_path,
        class_count=args.class_count,
        train_per_class=args.train_per_class,
        val_per_class=args.val_per_class,
        test_per_class=args.test_per_class,
        seed=args.seed,
    )
    label_to_index = {gloss: index for index, gloss in enumerate(classes)}

    start = time.perf_counter()
    x_values = []
    y_values = []
    tensor_rows = []
    for row in rows:
        video_path = Path(row["video_path"])
        tensor, metadata = _read_video_tensor(video_path, args.frames, args.image_size)
        x_values.append(tensor)
        y_values.append(label_to_index[row["gloss"]])
        tensor_rows.append(
            {
                **row,
                "label_index": label_to_index[row["gloss"]],
                **metadata,
            }
        )
    x = np.stack(x_values, axis=0).astype(np.float32)
    y = np.asarray(y_values, dtype=np.int64)
    np.savez_compressed(tensors_dir / "tensor_smoke_batch.npz", x=x, y=y)

    import tensorflow as tf

    tf.keras.utils.set_random_seed(args.seed)
    model = _build_tiny_model(args.frames, args.image_size, len(classes))
    predictions = model.predict(x[: min(args.batch_size, len(x))], verbose=0)
    history = model.fit(x, y, batch_size=args.batch_size, epochs=1, verbose=0)
    model.save(models_dir / "tiny_rgb_smoke.keras")

    summary = {
        "experiment": "e3_b0_rgb_tensor_smoke_v1",
        "purpose": "tiny tensor/model plumbing only; not full extraction or training",
        "run_dir": str(output.resolve()),
        "preflight_run": str(args.preflight_run.resolve()),
        "classes": classes,
        "class_count": len(classes),
        "rows": len(rows),
        "frames": args.frames,
        "image_size": args.image_size,
        "tensor_shape": list(x.shape),
        "label_shape": list(y.shape),
        "x_dtype": str(x.dtype),
        "y_dtype": str(y.dtype),
        "x_min": float(np.min(x)),
        "x_max": float(np.max(x)),
        "forward_output_shape": list(predictions.shape),
        "forward_output_row_sum_min": float(np.min(np.sum(predictions, axis=1))),
        "forward_output_row_sum_max": float(np.max(np.sum(predictions, axis=1))),
        "train_history": {key: [float(v) for v in values] for key, values in history.history.items()},
        "model_path": str((models_dir / "tiny_rgb_smoke.keras").resolve()),
        "tensor_path": str((tensors_dir / "tensor_smoke_batch.npz").resolve()),
        "elapsed_seconds": time.perf_counter() - start,
        "passed": True,
        "warning": "Smoke only. Do not use as an accuracy result.",
    }
    _write_csv(
        output / "tensor_manifest.csv",
        tensor_rows,
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
    (output / "tensor_smoke_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (output / "tensor_smoke_summary.md").write_text(_markdown(summary), encoding="utf-8")
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    summary_path = args.run_dir / "tensor_smoke_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"missing summary: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    errors = []
    for relative in [
        "tensor_smoke_summary.md",
        "tensor_manifest.csv",
        "tensors/tensor_smoke_batch.npz",
        "models/tiny_rgb_smoke.keras",
    ]:
        if not (args.run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if summary["tensor_shape"][1:] != [summary["frames"], summary["image_size"], summary["image_size"], 3]:
        errors.append("unexpected tensor shape")
    if summary["forward_output_shape"][1] != summary["class_count"]:
        errors.append("unexpected forward output class dimension")
    result = {
        "run_dir": str(args.run_dir.resolve()),
        "passed": not errors and bool(summary.get("passed")),
        "errors": errors,
        "tensor_shape": summary.get("tensor_shape"),
        "class_count": summary.get("class_count"),
        "rows": summary.get("rows"),
        "model_path": summary.get("model_path"),
    }
    (args.run_dir / "check_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _markdown(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# E3-B0 RGB Tensor Smoke",
            "",
            "Tiny tensor/model plumbing only. This is not an accuracy result.",
            "",
            f"- Passed: {summary['passed']}",
            f"- Classes: {summary['class_count']}",
            f"- Rows: {summary['rows']}",
            f"- Tensor shape: {summary['tensor_shape']}",
            f"- Forward output shape: {summary['forward_output_shape']}",
            f"- Loss after one tiny epoch: {summary['train_history'].get('loss', [''])[0]}",
            f"- Accuracy after one tiny epoch: {summary['train_history'].get('accuracy', [''])[0]}",
            f"- Elapsed seconds: {summary['elapsed_seconds']:.2f}",
            "",
            "Next: inspect the tensor smoke, then prepare a user-run bounded pilot package. Do not start full extraction or training yet.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="E3-B0 tiny RGB tensor smoke")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--run-id", default="tensor_smoke_01")
    run_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    run_parser.add_argument("--preflight-run", type=Path, default=DEFAULT_PREFLIGHT_RUN)
    run_parser.add_argument("--class-count", type=int, default=3)
    run_parser.add_argument("--train-per-class", type=int, default=2)
    run_parser.add_argument("--val-per-class", type=int, default=1)
    run_parser.add_argument("--test-per-class", type=int, default=1)
    run_parser.add_argument("--frames", type=int, default=8)
    run_parser.add_argument("--image-size", type=int, default=112)
    run_parser.add_argument("--batch-size", type=int, default=4)
    run_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    run_parser.add_argument("--overwrite", action="store_true")

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, KeyError, ValueError, OSError) as error:
        print(f"[rgb/e3-b0-smoke] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

