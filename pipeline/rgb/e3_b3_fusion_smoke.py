"""E3-B3 bounded landmark + RGB fusion smoke.

This experiment reuses the E3-B1 RGB frame embeddings and rebuilds v3.0 landmark tensors for the
same 7-class signer-disjoint manifest from existing Stage-E landmarks and spans. It trains three
small heads on the exact same split: RGB-only, landmark-only, and fused. No MediaPipe extraction,
Android assets, or production recognizer files are modified.
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

from pipeline.detect.schema import SpanSidecar
from pipeline.extract.schema import ClipLandmarks
from pipeline.features.contract import FEATURE_DIM, SCHEMA_VERSION, clip_features_realtimed
from pipeline.normalize.config import load_config as load_normalize_config

DEFAULT_RGB_RUN = Path("artifacts/recognition_upgrade/e3_rgb_b1/pilot_01_mobilenetv3_upper_body")
DEFAULT_OUTPUT_ROOT = Path("artifacts/recognition_upgrade/e3_fusion")
DEFAULT_LANDMARKS_ROOT = Path("F:/ASL DATASET/ASL CITIZEN/derived/apphear3/landmarks")
DEFAULT_SPANS_ROOT = Path("F:/ASL DATASET/ASL CITIZEN/derived/apphear3/spans")
DEFAULT_NORMALIZE_CONFIG = Path("pipeline/config/normalize.yaml")
DEFAULT_T_MAX = 96


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


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output_root / args.run_id
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True, exist_ok=True)

    rgb_manifest = args.rgb_run / "pilot_manifest.csv"
    rgb_config_path = args.rgb_run / "pilot_config.json"
    if not rgb_manifest.exists():
        raise FileNotFoundError(f"missing RGB manifest: {rgb_manifest}")
    if not rgb_config_path.exists():
        raise FileNotFoundError(f"missing RGB config: {rgb_config_path}")

    rows = _read_csv(rgb_manifest)
    rgb_config = json.loads(rgb_config_path.read_text(encoding="utf-8"))
    missing = _missing_landmark_inputs(rows, args.landmarks_root, args.spans_root)
    if missing:
        _write_csv(output / "missing_landmark_inputs.csv", missing, ["split", "gloss", "clip_id", "landmark", "span"])
        raise FileNotFoundError(f"{len(missing)} clips missing landmark/span inputs; see missing_landmark_inputs.csv")

    _write_csv(
        output / "pilot_manifest.csv",
        rows,
        ["source", "split", "signer_id", "gloss", "label_index", "video_path"],
    )
    config = {
        "experiment": "e3_b3_landmark_rgb_fusion_smoke_v1",
        "purpose": "bounded signer-disjoint landmark+RGB fusion smoke; not production training",
        "run_dir": str(output.resolve()),
        "rgb_run": str(args.rgb_run.resolve()),
        "rgb_features": str((args.rgb_run / "dataset" / "rgb_frame_features.npz").resolve()),
        "landmarks_root": str(args.landmarks_root.resolve()),
        "spans_root": str(args.spans_root.resolve()),
        "normalize_config": str(args.normalize_config),
        "schema_version": SCHEMA_VERSION,
        "classes": rgb_config["classes"],
        "class_count": int(rgb_config["class_count"]),
        "rows": len(rows),
        "t_max": args.t_max,
        "batch_size": args.batch_size,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "branches": ["rgb_only", "landmark_only", "fusion"],
        "baseline_reference": {
            "e3_b1_latest_val": 0.1429,
            "e3_b1_latest_test": 0.1429,
            "e3_b1_best_val": 0.2143,
            "e3_b1_best_test": 0.1071,
            "random_baseline": 1.0 / int(rgb_config["class_count"]),
        },
        "warnings": [
            "This is not production training.",
            "This does not authorize Android integration.",
            "Fusion is useful only if it beats both branch-only heads on held-out signers.",
        ],
    }
    (output / "pilot_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def _missing_landmark_inputs(rows: list[dict[str, str]], landmarks_root: Path, spans_root: Path) -> list[dict[str, Any]]:
    missing = []
    for row in rows:
        clip_id = Path(row["video_path"]).stem
        landmark_path = landmarks_root / row["split"] / f"{clip_id}.npz"
        span_path = spans_root / row["split"] / f"{clip_id}.span.json"
        if not landmark_path.exists() or not span_path.exists():
            missing.append(
                {
                    "split": row["split"],
                    "gloss": row["gloss"],
                    "clip_id": clip_id,
                    "landmark": landmark_path.exists(),
                    "span": span_path.exists(),
                }
            )
    return missing


def _load_or_build_landmarks(run_dir: Path, config: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    dataset_dir = run_dir / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    out_path = dataset_dir / "landmark_features.npz"
    if out_path.exists():
        data = np.load(out_path)
        return data["landmarks"], data["y"], data["split_index"], data["frame_mask"]

    rows = _read_csv(run_dir / "pilot_manifest.csv")
    ncfg = load_normalize_config(Path(config["normalize_config"]))
    split_to_index = {"train": 0, "val": 1, "test": 2}
    x_values: list[np.ndarray] = []
    y_values: list[int] = []
    split_values: list[int] = []
    mask_values: list[np.ndarray] = []
    meta_rows: list[dict[str, Any]] = []
    landmarks_root = Path(config["landmarks_root"])
    spans_root = Path(config["spans_root"])

    for index, row in enumerate(rows, start=1):
        clip_id = Path(row["video_path"]).stem
        print(f"[e3-b3-fusion] landmarks {index}/{len(rows)} {row['split']} {row['gloss']}")
        clip = ClipLandmarks.load(landmarks_root / row["split"] / f"{clip_id}.npz")
        span = SpanSidecar.load(spans_root / row["split"] / f"{clip_id}.span.json")
        feat, frame_mask, length, _ = clip_features_realtimed(
            clip.hands_image,
            clip.pose_image,
            span.onset,
            span.release,
            ncfg,
            int(config["t_max"]),
        )
        x_values.append(feat.astype(np.float32))
        mask_values.append(frame_mask.astype(bool))
        y_values.append(int(row["label_index"]))
        split_values.append(split_to_index[row["split"]])
        meta_rows.append({**row, "clip_id": clip_id, "length": int(length), "span_onset": span.onset, "span_release": span.release})

    landmarks = np.stack(x_values).astype(np.float32)
    y = np.asarray(y_values, dtype=np.int64)
    split_index = np.asarray(split_values, dtype=np.int64)
    frame_mask = np.stack(mask_values).astype(bool)
    np.savez_compressed(out_path, landmarks=landmarks, y=y, split_index=split_index, frame_mask=frame_mask)
    _write_csv(
        dataset_dir / "landmark_manifest.csv",
        meta_rows,
        ["source", "split", "signer_id", "gloss", "label_index", "video_path", "clip_id", "length", "span_onset", "span_release"],
    )
    return landmarks, y, split_index, frame_mask


def _load_rgb_features(config: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    path = Path(config["rgb_features"])
    if not path.exists():
        raise FileNotFoundError(f"missing RGB features: {path}")
    data = np.load(path)
    return data["features"].astype(np.float32), data["y"].astype(np.int64), data["split_index"].astype(np.int64)


def _build_model(kind: str, landmark_shape: tuple[int, int], rgb_shape: tuple[int, int], classes: int, lr: float):
    import tensorflow as tf

    inputs: list[Any] = []
    branches: list[Any] = []
    if kind in {"landmark_only", "fusion"}:
        land_in = tf.keras.Input(shape=landmark_shape, name="landmarks")
        x = tf.keras.layers.LayerNormalization()(land_in)
        x = tf.keras.layers.Conv1D(128, 5, padding="same", activation="relu")(x)
        x = tf.keras.layers.Dropout(0.25)(x)
        x = tf.keras.layers.Conv1D(128, 3, padding="same", activation="relu")(x)
        x = tf.keras.layers.GlobalAveragePooling1D()(x)
        inputs.append(land_in)
        branches.append(x)
    if kind in {"rgb_only", "fusion"}:
        rgb_in = tf.keras.Input(shape=rgb_shape, name="rgb")
        x = tf.keras.layers.LayerNormalization()(rgb_in)
        x = tf.keras.layers.Conv1D(128, 3, padding="same", activation="relu")(x)
        x = tf.keras.layers.Dropout(0.25)(x)
        x = tf.keras.layers.GlobalAveragePooling1D()(x)
        inputs.append(rgb_in)
        branches.append(x)
    if len(branches) == 1:
        x = branches[0]
    else:
        x = tf.keras.layers.Concatenate()(branches)
        x = tf.keras.layers.Dense(128, activation="relu")(x)
        x = tf.keras.layers.Dropout(0.25)(x)
    outputs = tf.keras.layers.Dense(classes, activation="softmax")(x)
    model = tf.keras.Model(inputs, outputs, name=f"e3_b3_{kind}")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
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

    start = time.perf_counter()
    landmarks, y, split_index, _ = _load_or_build_landmarks(run_dir, config)
    rgb, rgb_y, rgb_split = _load_rgb_features(config)
    if not (np.array_equal(y, rgb_y) and np.array_equal(split_index, rgb_split)):
        raise ValueError("landmark/RGB labels or splits do not align")

    results: dict[str, Any] = {
        "experiment": config["experiment"],
        "run_dir": str(run_dir.resolve()),
        "landmark_shape": list(landmarks.shape),
        "rgb_shape": list(rgb.shape),
        "class_count": config["class_count"],
        "split_counts": {
            "train": int(np.sum(split_index == 0)),
            "val": int(np.sum(split_index == 1)),
            "test": int(np.sum(split_index == 2)),
        },
        "branches": {},
        "elapsed_seconds": None,
        "passed": True,
    }
    for kind in config["branches"]:
        branch_dir = run_dir / "models" / kind
        branch_dir.mkdir(parents=True, exist_ok=True)
        latest = branch_dir / "latest.keras"
        best = branch_dir / "best.keras"
        if latest.exists() and not args.resume:
            raise FileExistsError(f"{kind}: latest model exists; rerun with --resume: {latest}")
        if args.resume and latest.exists():
            model = tf.keras.models.load_model(latest)
            initial_epoch = int((run_dir / "logs" / f"{kind}_epoch_count.txt").read_text(encoding="utf-8"))
        else:
            model = _build_model(
                kind,
                tuple(landmarks.shape[1:]),
                tuple(rgb.shape[1:]),
                int(config["class_count"]),
                float(config["learning_rate"]),
            )
            initial_epoch = 0
        train_mask = split_index == 0
        val_mask = split_index == 1
        x_train = _inputs_for(kind, landmarks[train_mask], rgb[train_mask])
        x_val = _inputs_for(kind, landmarks[val_mask], rgb[val_mask])
        history_path = run_dir / "logs" / f"{kind}_history.csv"
        history = model.fit(
            x_train,
            y[train_mask],
            validation_data=(x_val, y[val_mask]),
            batch_size=int(config["batch_size"]),
            epochs=initial_epoch + int(config["epochs"]),
            initial_epoch=initial_epoch,
            callbacks=[
                tf.keras.callbacks.ModelCheckpoint(str(best), monitor="val_accuracy", mode="max", save_best_only=True),
                tf.keras.callbacks.CSVLogger(str(history_path), append=history_path.exists()),
            ],
            verbose=2,
        )
        model.save(latest)
        total_epochs = initial_epoch + int(config["epochs"])
        (run_dir / "logs" / f"{kind}_epoch_count.txt").write_text(str(total_epochs), encoding="utf-8")
        results["branches"][kind] = {
            "latest": _evaluate(kind, model, landmarks, rgb, y, split_index, int(config["batch_size"])),
            "best": _evaluate(kind, tf.keras.models.load_model(best), landmarks, rgb, y, split_index, int(config["batch_size"])),
            "epoch_count_total": total_epochs,
            "history": {key: [float(v) for v in values] for key, values in history.history.items()},
        }
    results["elapsed_seconds"] = time.perf_counter() - start
    (run_dir / "metrics" / "metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (run_dir / "metrics" / "metrics.md").write_text(_metrics_markdown(results), encoding="utf-8")
    return results


def _inputs_for(kind: str, landmarks: np.ndarray, rgb: np.ndarray) -> Any:
    if kind == "landmark_only":
        return landmarks
    if kind == "rgb_only":
        return rgb
    if kind == "fusion":
        return [landmarks, rgb]
    raise ValueError(f"unsupported branch: {kind}")


def _evaluate(kind: str, model: Any, landmarks: np.ndarray, rgb: np.ndarray, y: np.ndarray, split_index: np.ndarray, batch_size: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for sid, name in ((0, "train"), (1, "val"), (2, "test")):
        mask = split_index == sid
        probs = model.predict(_inputs_for(kind, landmarks[mask], rgb[mask]), batch_size=batch_size, verbose=0)
        pred = np.argmax(probs, axis=1)
        out[name] = {
            "accuracy": float(np.mean(pred == y[mask])),
            "mean_confidence": float(np.mean(np.max(probs, axis=1))),
            "count": int(np.sum(mask)),
        }
    return out


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = [
        "pilot_config.json",
        "pilot_manifest.csv",
        "dataset/landmark_features.npz",
        "dataset/landmark_manifest.csv",
        "metrics/metrics.json",
        "metrics/metrics.md",
    ]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    config = {}
    config_path = run_dir / "pilot_config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        for branch in config.get("branches", []):
            for relative in (
                f"models/{branch}/latest.keras",
                f"models/{branch}/best.keras",
                f"logs/{branch}_history.csv",
                f"logs/{branch}_epoch_count.txt",
            ):
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
            "# E3-B3 Landmark + RGB Fusion Smoke",
            "",
            "This is a bounded signer-disjoint fusion smoke, not production training.",
            "",
            "## Settings",
            "",
            f"- Classes: {config['class_count']}",
            f"- Clips: {config['rows']}",
            f"- Landmark input: [{config['t_max']}, 258]",
            "- RGB input: E3-B1 MobileNetV3 frame embeddings",
            f"- Branches: {', '.join(config['branches'])}",
            f"- Epochs per command: {config['epochs']}",
            "",
            "## Run",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b3_fusion_smoke run --run-dir "{run_dir}"',
            "```",
            "",
            "## Resume",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b3_fusion_smoke run --run-dir "{run_dir}" --resume',
            "```",
            "",
            "## Check",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b3_fusion_smoke check --run-dir "{run_dir}"',
            "```",
            "",
        ]
    )


def _metrics_markdown(metrics: dict[str, Any]) -> str:
    lines = [
        "# E3-B3 Fusion Smoke Metrics",
        "",
        "Bounded signer-disjoint smoke only. Not a production accuracy claim.",
        "",
        f"- Passed: {metrics['passed']}",
        f"- Landmark shape: {metrics['landmark_shape']}",
        f"- RGB shape: {metrics['rgb_shape']}",
        f"- Split counts: {metrics['split_counts']}",
        "",
        "| Branch | Checkpoint | Train | Val | Test |",
        "|---|---|---:|---:|---:|",
    ]
    for branch, result in metrics["branches"].items():
        for checkpoint in ("latest", "best"):
            item = result[checkpoint]
            lines.append(
                f"| {branch} | {checkpoint} | {item['train']['accuracy']:.4f} | "
                f"{item['val']['accuracy']:.4f} | {item['test']['accuracy']:.4f} |"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="E3-B3 landmark + RGB fusion smoke")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--run-id", default="pilot_01_landmark_rgb_fusion")
    prepare_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    prepare_parser.add_argument("--rgb-run", type=Path, default=DEFAULT_RGB_RUN)
    prepare_parser.add_argument("--landmarks-root", type=Path, default=DEFAULT_LANDMARKS_ROOT)
    prepare_parser.add_argument("--spans-root", type=Path, default=DEFAULT_SPANS_ROOT)
    prepare_parser.add_argument("--normalize-config", type=Path, default=DEFAULT_NORMALIZE_CONFIG)
    prepare_parser.add_argument("--t-max", type=int, default=DEFAULT_T_MAX)
    prepare_parser.add_argument("--batch-size", type=int, default=8)
    prepare_parser.add_argument("--epochs", type=int, default=8)
    prepare_parser.add_argument("--learning-rate", type=float, default=5e-4)
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
        print(f"[rgb/e3-b3] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
