"""E3-B4 bounded landmark temporal model comparison.

This experiment reuses the signer-disjoint 7-class landmark tensor produced by E3-B3 and compares
small landmark-only temporal heads. It is intentionally isolated from Android and production model
assets.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_SOURCE_RUN = Path("artifacts/recognition_upgrade/e3_fusion/pilot_01_landmark_rgb_fusion")
DEFAULT_OUTPUT_ROOT = Path("artifacts/recognition_upgrade/e3_landmark_temporal")
DEFAULT_RUN_ID = "pilot_01_tcn_vs_masked"

E3_B3_LANDMARK_BEST_VAL = 0.6071
E3_B3_LANDMARK_BEST_TEST = 0.6071
E3_B3_LANDMARK_LATEST_TEST = 0.6786


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


def _load_source_tensor(source_run: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    tensor_path = source_run / "dataset" / "landmark_features.npz"
    if not tensor_path.exists():
        raise FileNotFoundError(f"missing E3-B3 landmark tensor: {tensor_path}")
    data = np.load(tensor_path)
    required = {"landmarks", "y", "split_index", "frame_mask"}
    missing = required.difference(data.files)
    if missing:
        raise ValueError(f"landmark tensor missing keys: {sorted(missing)}")
    x = data["landmarks"].astype(np.float32)
    y = data["y"].astype(np.int64)
    split_index = data["split_index"].astype(np.int64)
    frame_mask = data["frame_mask"].astype(np.float32)
    if x.ndim != 3 or x.shape[1:] != (96, 258):
        raise ValueError(f"expected landmark tensor [N,96,258], got {list(x.shape)}")
    if frame_mask.shape != x.shape[:2]:
        raise ValueError(f"frame_mask shape {list(frame_mask.shape)} does not match {list(x.shape[:2])}")
    if not (len(y) == len(split_index) == len(frame_mask) == len(x)):
        raise ValueError("landmark tensor arrays are not aligned")
    return x, y, split_index, frame_mask


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    source_run = args.source_run
    output = args.output_root / args.run_id
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True, exist_ok=True)
    for relative in ("dataset", "logs", "metrics", "models"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    source_config_path = source_run / "pilot_config.json"
    source_manifest_path = source_run / "pilot_manifest.csv"
    source_landmark_manifest = source_run / "dataset" / "landmark_manifest.csv"
    if not source_config_path.exists():
        raise FileNotFoundError(f"missing source config: {source_config_path}")
    if not source_manifest_path.exists():
        raise FileNotFoundError(f"missing source manifest: {source_manifest_path}")

    x, y, split_index, frame_mask = _load_source_tensor(source_run)
    source_config = json.loads(source_config_path.read_text(encoding="utf-8"))
    rows = _read_csv(source_manifest_path)
    if len(rows) != len(x):
        raise ValueError(f"manifest rows {len(rows)} do not match tensor rows {len(x)}")

    shutil.copy2(source_manifest_path, output / "pilot_manifest.csv")
    if source_landmark_manifest.exists():
        shutil.copy2(source_landmark_manifest, output / "dataset" / "landmark_manifest.csv")
    np.savez_compressed(output / "dataset" / "landmark_features.npz", landmarks=x, y=y, split_index=split_index, frame_mask=frame_mask)

    config = {
        "experiment": "e3_b4_landmark_temporal_v1",
        "purpose": "bounded signer-disjoint landmark-only temporal architecture comparison; not production training",
        "run_dir": str(output.resolve()),
        "source_run": str(source_run.resolve()),
        "source_experiment": source_config.get("experiment"),
        "classes": source_config["classes"],
        "class_count": int(source_config["class_count"]),
        "rows": int(len(x)),
        "input_shape": [int(x.shape[1]), int(x.shape[2])],
        "split_counts": {
            "train": int(np.sum(split_index == 0)),
            "val": int(np.sum(split_index == 1)),
            "test": int(np.sum(split_index == 2)),
        },
        "batch_size": int(args.batch_size),
        "epochs": int(args.epochs),
        "learning_rate": float(args.learning_rate),
        "branches": ["conv1d_baseline", "tcn_pool", "tcn_masked_pool"],
        "baseline_reference": {
            "e3_b3_landmark_best_val": E3_B3_LANDMARK_BEST_VAL,
            "e3_b3_landmark_best_test": E3_B3_LANDMARK_BEST_TEST,
            "e3_b3_landmark_latest_test": E3_B3_LANDMARK_LATEST_TEST,
            "random_baseline": 1.0 / int(source_config["class_count"]),
        },
        "gate": {
            "promising_if": [
                "best validation accuracy is at least E3-B3 landmark best validation",
                "test accuracy is not worse than E3-B3 landmark best test after selecting by validation",
                "masked pooling is not worse than unmasked pooling on validation",
            ],
            "no_go_if": [
                "TCN variants do not beat or match the simple Conv1D control",
                "training accuracy rises while validation/test collapse",
            ],
        },
        "warnings": [
            "This uses the existing 7-class E3-B3 split only.",
            "This is not full AppHear training.",
            "This does not authorize Android integration or production model replacement.",
        ],
    }
    (output / "pilot_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def _build_conv1d_baseline(input_shape: tuple[int, int], classes: int, lr: float):
    import tensorflow as tf

    inputs = tf.keras.Input(shape=input_shape, name="features")
    x = tf.keras.layers.LayerNormalization(name="norm")(inputs)
    x = tf.keras.layers.Conv1D(128, 5, padding="same", activation="relu", name="conv5")(x)
    x = tf.keras.layers.Dropout(0.25, name="drop1")(x)
    x = tf.keras.layers.Conv1D(128, 3, padding="same", activation="relu", name="conv3")(x)
    x = tf.keras.layers.GlobalAveragePooling1D(name="pool")(x)
    outputs = tf.keras.layers.Dense(classes, activation="softmax", name="logits")(x)
    model = tf.keras.Model(inputs, outputs, name="e3_b4_conv1d_baseline")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def _build_tcn_pool(input_shape: tuple[int, int], classes: int, lr: float):
    import tensorflow as tf

    from model.model import build_classifier

    model = build_classifier(
        input_shape[0],
        input_shape[1],
        classes,
        blocks=4,
        channels=64,
        dilations=(1, 2, 4, 8),
        kernel=3,
        dropout=0.1,
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def _build_tcn_masked_pool(input_shape: tuple[int, int], classes: int, lr: float):
    import tensorflow as tf

    from model.model import build_encoder

    feature_input = tf.keras.Input(shape=input_shape, name="features")
    mask_input = tf.keras.Input(shape=(input_shape[0],), name="frame_mask")
    encoder = build_encoder(
        input_shape[0],
        input_shape[1],
        blocks=4,
        channels=64,
        dilations=(1, 2, 4, 8),
        kernel=3,
        dropout=0.1,
    )
    encoded = encoder(feature_input)
    expanded_mask = tf.keras.layers.Lambda(
        lambda m: tf.expand_dims(tf.cast(m, tf.float32), axis=-1),
        output_shape=(input_shape[0], 1),
        name="expand_frame_mask",
    )(mask_input)
    masked_sum = tf.keras.layers.Lambda(
        lambda values: tf.reduce_sum(values[0] * values[1], axis=1),
        output_shape=(64,),
        name="masked_sum",
    )([encoded, expanded_mask])
    denom = tf.keras.layers.Lambda(
        lambda m: tf.maximum(tf.reduce_sum(m, axis=1), 1.0),
        output_shape=(1,),
        name="mask_denominator",
    )(expanded_mask)
    pooled = tf.keras.layers.Lambda(
        lambda values: values[0] / values[1],
        output_shape=(64,),
        name="masked_pool",
    )([masked_sum, denom])
    outputs = tf.keras.layers.Dense(classes, activation="softmax", name="logits")(pooled)
    model = tf.keras.Model([feature_input, mask_input], outputs, name="e3_b4_tcn_masked_pool")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def _build_model(kind: str, input_shape: tuple[int, int], classes: int, lr: float):
    if kind == "conv1d_baseline":
        return _build_conv1d_baseline(input_shape, classes, lr)
    if kind == "tcn_pool":
        return _build_tcn_pool(input_shape, classes, lr)
    if kind == "tcn_masked_pool":
        return _build_tcn_masked_pool(input_shape, classes, lr)
    raise ValueError(f"unsupported branch: {kind}")


def _inputs_for(kind: str, landmarks: np.ndarray, frame_mask: np.ndarray) -> Any:
    if kind == "tcn_masked_pool":
        return [landmarks, frame_mask]
    return landmarks


def run(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config_path = run_dir / "pilot_config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"missing config; run prepare first: {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for relative in ("logs", "metrics", "models"):
        (run_dir / relative).mkdir(parents=True, exist_ok=True)

    landmarks, y, split_index, frame_mask = _load_source_tensor(run_dir)
    input_shape = tuple(int(v) for v in landmarks.shape[1:])
    start = time.perf_counter()
    results: dict[str, Any] = {
        "experiment": config["experiment"],
        "run_dir": str(run_dir.resolve()),
        "input_shape": list(input_shape),
        "class_count": int(config["class_count"]),
        "split_counts": config["split_counts"],
        "baseline_reference": config["baseline_reference"],
        "branches": {},
        "elapsed_seconds": None,
        "passed": True,
    }

    for kind in config["branches"]:
        branch_dir = run_dir / "models" / kind
        branch_dir.mkdir(parents=True, exist_ok=True)
        latest = branch_dir / "latest.weights.h5"
        best = branch_dir / "best.weights.h5"
        epoch_file = run_dir / "logs" / f"{kind}_epoch_count.txt"
        if latest.exists() and not args.resume:
            raise FileExistsError(f"{kind}: latest model exists; rerun with --resume: {latest}")
        model = _build_model(kind, input_shape, int(config["class_count"]), float(config["learning_rate"]))
        if args.resume and latest.exists():
            model.load_weights(latest)
            initial_epoch = int(epoch_file.read_text(encoding="utf-8"))
        else:
            initial_epoch = 0

        train_mask = split_index == 0
        val_mask = split_index == 1
        history_path = run_dir / "logs" / f"{kind}_history.csv"
        history = model.fit(
            _inputs_for(kind, landmarks[train_mask], frame_mask[train_mask]),
            y[train_mask],
            validation_data=(_inputs_for(kind, landmarks[val_mask], frame_mask[val_mask]), y[val_mask]),
            batch_size=int(config["batch_size"]),
            epochs=initial_epoch + int(config["epochs"]),
            initial_epoch=initial_epoch,
            callbacks=[
                tf.keras.callbacks.ModelCheckpoint(str(best), monitor="val_accuracy", mode="max", save_best_only=True, save_weights_only=True),
                tf.keras.callbacks.CSVLogger(str(history_path), append=history_path.exists()),
            ],
            verbose=2,
        )
        model.save_weights(latest)
        total_epochs = initial_epoch + int(config["epochs"])
        epoch_file.write_text(str(total_epochs), encoding="utf-8")
        results["branches"][kind] = {
            "latest": _evaluate(kind, model, landmarks, frame_mask, y, split_index, int(config["batch_size"]), config["classes"]),
            "best": _evaluate(
                kind,
                _load_weights_model(kind, input_shape, int(config["class_count"]), float(config["learning_rate"]), best),
                landmarks,
                frame_mask,
                y,
                split_index,
                int(config["batch_size"]),
                config["classes"],
            ),
            "epoch_count_total": total_epochs,
            "history": {key: [float(v) for v in values] for key, values in history.history.items()},
        }

    results["elapsed_seconds"] = time.perf_counter() - start
    results["decision_hint"] = _decision_hint(results)
    (run_dir / "metrics" / "metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (run_dir / "metrics" / "metrics.md").write_text(_metrics_markdown(results), encoding="utf-8")
    return results


def _load_weights_model(kind: str, input_shape: tuple[int, int], classes: int, lr: float, weights_path: Path) -> Any:
    model = _build_model(kind, input_shape, classes, lr)
    model.load_weights(weights_path)
    return model

def _evaluate(
    kind: str,
    model: Any,
    landmarks: np.ndarray,
    frame_mask: np.ndarray,
    y: np.ndarray,
    split_index: np.ndarray,
    batch_size: int,
    classes: list[str],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for sid, name in ((0, "train"), (1, "val"), (2, "test")):
        mask = split_index == sid
        probs = model.predict(_inputs_for(kind, landmarks[mask], frame_mask[mask]), batch_size=batch_size, verbose=0)
        pred = np.argmax(probs, axis=1)
        predicted_counts: dict[str, int] = {}
        for class_index in pred:
            class_name = classes[int(class_index)]
            predicted_counts[class_name] = predicted_counts.get(class_name, 0) + 1
        out[name] = {
            "accuracy": float(np.mean(pred == y[mask])),
            "mean_confidence": float(np.mean(np.max(probs, axis=1))),
            "count": int(np.sum(mask)),
            "predicted_class_counts": dict(sorted(predicted_counts.items())),
        }
    return out


def _decision_hint(metrics: dict[str, Any]) -> dict[str, Any]:
    best_by_val: dict[str, Any] = {}
    for branch, result in metrics["branches"].items():
        item = result["best"]
        best_by_val[branch] = {
            "best_val": item["val"]["accuracy"],
            "best_test": item["test"]["accuracy"],
            "latest_test": result["latest"]["test"]["accuracy"],
        }
    winning_branch = max(best_by_val, key=lambda branch: best_by_val[branch]["best_val"]) if best_by_val else None
    return {
        "winning_branch_by_best_val": winning_branch,
        "branch_summary": best_by_val,
        "promising_against_e3_b3": bool(
            winning_branch
            and best_by_val[winning_branch]["best_val"] >= E3_B3_LANDMARK_BEST_VAL
            and best_by_val[winning_branch]["best_test"] >= E3_B3_LANDMARK_BEST_TEST
        ),
    }


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = [
        "pilot_config.json",
        "pilot_manifest.csv",
        "dataset/landmark_features.npz",
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
                f"models/{branch}/latest.weights.h5",
                f"models/{branch}/best.weights.h5",
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
            "# E3-B4 Landmark Temporal Comparison",
            "",
            "This is a bounded signer-disjoint landmark-only experiment, not production training.",
            "",
            "## What It Tests",
            "",
            "- `conv1d_baseline`: the simple landmark head that matched E3-B3 behavior.",
            "- `tcn_pool`: AppHear's causal TCN encoder with ordinary global average pooling.",
            "- `tcn_masked_pool`: the same causal TCN encoder, but padded frames are excluded by the frame mask.",
            "",
            "## Settings",
            "",
            f"- Classes: {config['class_count']}",
            f"- Clips: {config['rows']}",
            f"- Input: {config['input_shape']}",
            f"- Split counts: {config['split_counts']}",
            f"- Branches: {', '.join(config['branches'])}",
            f"- Epochs per command: {config['epochs']}",
            f"- Batch size: {config['batch_size']}",
            "",
            "## Run",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b4_landmark_temporal run --run-dir "{run_dir}"',
            "```",
            "",
            "## Resume",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b4_landmark_temporal run --run-dir "{run_dir}" --resume',
            "```",
            "",
            "## Check",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b4_landmark_temporal check --run-dir "{run_dir}"',
            "```",
            "",
            "## Send Back",
            "",
            "- `metrics/metrics.json`",
            "- `metrics/metrics.md`",
            "- `check_report.json`",
            "- all `logs/*_history.csv` files",
            "",
        ]
    )


def _metrics_markdown(metrics: dict[str, Any]) -> str:
    lines = [
        "# E3-B4 Landmark Temporal Metrics",
        "",
        "Bounded signer-disjoint experiment only. Not a production accuracy claim.",
        "",
        f"- Passed: {metrics['passed']}",
        f"- Input shape: {metrics['input_shape']}",
        f"- Split counts: {metrics['split_counts']}",
        f"- E3-B3 landmark best val/test reference: {E3_B3_LANDMARK_BEST_VAL:.4f} / {E3_B3_LANDMARK_BEST_TEST:.4f}",
        "",
        "| Branch | Checkpoint | Train | Val | Test | Mean Val Conf |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for branch, result in metrics["branches"].items():
        for checkpoint in ("latest", "best"):
            item = result[checkpoint]
            lines.append(
                f"| {branch} | {checkpoint} | {item['train']['accuracy']:.4f} | "
                f"{item['val']['accuracy']:.4f} | {item['test']['accuracy']:.4f} | "
                f"{item['val']['mean_confidence']:.4f} |"
            )
    lines.extend(["", "## Decision Hint", "", "```json", json.dumps(metrics.get("decision_hint", {}), indent=2), "```", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="E3-B4 landmark temporal model comparison")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    prepare_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    prepare_parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
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
        print(f"[rgb/e3-b4] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




