"""E4-V GOOD/SORRY visual specialist proof-of-value.

Uses the E4-J signer-disjoint GOOD/SORRY rows to compare a landmark-only binary control
against an upper-body RGB specialist. This tests the reusable confusion-group path after
E4-T showed simple confidence routing cannot prevent SORRY -> GOOD false commits.

Experiment-only: no Android assets, TFLite exports, production recognizer files, or source
datasets are modified.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.features.contract import SCHEMA_VERSION
from pipeline.rgb.e3_b1_pretrained_rgb import _build_encoder, _read_video_frames
from pipeline.rgb.e3_b4_landmark_temporal import _build_model as _build_landmark_model
from pipeline.rgb.e3_b4_landmark_temporal import _inputs_for as _landmark_inputs_for
from pipeline.rgb.e4_u_confusion_evidence import DEFAULT_OUTPUT as DEFAULT_E4U_RUN

DEFAULT_E4J_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_j_reliable_core_3sign_pilot_01")
DEFAULT_E4U_RUN = DEFAULT_E4U_RUN
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01")
CLASSES = ["GOOD", "SORRY"]
SPLITS = {"train": 0, "val": 1, "test": 2}
DEFAULT_BRANCHES = ["landmark_binary_control", "rgb_upper_body"]
DEFAULT_SEEDS = [101, 202, 303]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_e4j_dataset(e4j_run: Path) -> dict[str, np.ndarray]:
    path = e4j_run / "dataset" / "landmark_features.npz"
    if not path.exists():
        raise FileNotFoundError(f"missing E4-J landmark tensor: {path}")
    data = np.load(path, allow_pickle=False)
    return {
        "landmarks": data["landmarks"].astype(np.float32),
        "frame_mask": data["frame_mask"].astype(bool),
        "y": data["y"].astype(np.int64),
        "split_index": data["split_index"].astype(np.int64),
        "lengths": data["lengths"].astype(np.int32),
        "participant_ids": np.asarray(data["participant_ids"]).astype(str),
        "sample_ids": np.asarray(data["sample_ids"]).astype(str),
    }


def _split_counts(split_index: np.ndarray) -> dict[str, int]:
    return {name: int(np.sum(split_index == sid)) for name, sid in SPLITS.items()}


def _class_counts(y: np.ndarray, split_index: np.ndarray) -> dict[str, dict[str, int]]:
    return {
        split: {CLASSES[cid]: int(np.sum(y[split_index == sid] == cid)) for cid in range(len(CLASSES))}
        for split, sid in SPLITS.items()
    }


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("dataset", "logs", "metrics", "models", "smoke"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    source_config = json.loads((args.e4j_run / "pilot_config.json").read_text(encoding="utf-8"))
    source_classes = [str(item).upper() for item in source_config["classes"]]
    rows = _read_csv(args.e4j_run / "pilot_manifest.csv")
    selected_indices = []
    selected_rows: list[dict[str, Any]] = []
    remap = {source_classes.index("GOOD"): 0, source_classes.index("SORRY"): 1}
    for idx, row in enumerate(rows):
        gloss = row["canonical_gloss"].upper()
        if gloss not in CLASSES:
            continue
        selected_indices.append(idx)
        selected_rows.append({
            "sample_id": row["sample_id"],
            "split": row["split"],
            "canonical_gloss": gloss,
            "class_id": CLASSES.index(gloss),
            "signer_id": row.get("signer_id", ""),
            "video_path": row["video_path"],
            "frame_count": row.get("frame_count", ""),
            "fps": row.get("fps", ""),
            "hand_hit_rate": row.get("hand_hit_rate", ""),
            "warnings": row.get("warnings", ""),
            "notes": "selected_for_e4_v_good_sorry_specialist",
        })

    source = _load_e4j_dataset(args.e4j_run)
    mask = np.asarray(selected_indices, dtype=np.int64)
    y = np.asarray([remap[int(source["y"][idx])] for idx in selected_indices], dtype=np.int64)
    landmark = {
        "landmarks": source["landmarks"][mask].astype(np.float32),
        "frame_mask": source["frame_mask"][mask].astype(bool),
        "y": y,
        "split_index": source["split_index"][mask].astype(np.int64),
        "lengths": source["lengths"][mask].astype(np.int32),
        "participant_ids": source["participant_ids"][mask].astype(str),
        "sample_ids": source["sample_ids"][mask].astype(str),
    }
    np.savez_compressed(output / "dataset" / "landmark_binary_features.npz", **landmark)
    _write_csv(output / "pilot_manifest.csv", selected_rows, ["sample_id", "split", "canonical_gloss", "class_id", "signer_id", "video_path", "frame_count", "fps", "hand_hit_rate", "warnings", "notes"])
    _write_csv(output / "selected_classes.csv", [{"class_id": idx, "gloss": gloss} for idx, gloss in enumerate(CLASSES)], ["class_id", "gloss"])

    config = {
        "experiment": "e4_v_sorry_good_specialist_v1",
        "purpose": "compare landmark binary control against upper-body RGB specialist for the SORRY -> GOOD confusion group",
        "run_dir": str(output.resolve()),
        "e4j_run": str(args.e4j_run.resolve()),
        "e4u_run": str(args.e4u_run.resolve()),
        "schema_version": SCHEMA_VERSION,
        "classes": CLASSES,
        "class_count": len(CLASSES),
        "active_rows": int(len(selected_rows)),
        "split_counts": _split_counts(landmark["split_index"]),
        "class_counts": _class_counts(landmark["y"], landmark["split_index"]),
        "frames": int(args.frames),
        "image_size": int(args.image_size),
        "crop_mode": args.crop_mode,
        "encoder": args.encoder,
        "weights": args.weights,
        "embedding_batch_size": int(args.embedding_batch_size),
        "batch_size": int(args.batch_size),
        "epochs": int(args.epochs),
        "learning_rate": float(args.learning_rate),
        "branches": list(args.branches),
        "seeds": list(args.seeds),
        "gate": {
            "rgb_test_accuracy_min": 0.90,
            "rgb_good_recall_min": 0.90,
            "rgb_sorry_recall_min": 0.90,
            "rgb_gain_over_landmark_min": 0.05,
        },
        "warnings": [
            "This is a small proof-of-value screen, not production training.",
            "The split is inherited from E4-J and is signer-disjoint but small.",
            "No Android integration, TFLite export, or production recognizer replacement is authorized.",
        ],
    }
    _write_json(output / "pilot_config.json", config)
    _write_json(output / "logs" / "prepare_summary.json", {**config, "passed": True})
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def _load_landmark(run_dir: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    data = np.load(run_dir / "dataset" / "landmark_binary_features.npz", allow_pickle=False)
    return data["landmarks"].astype(np.float32), data["frame_mask"].astype(bool), data["y"].astype(np.int64), data["split_index"].astype(np.int64)


def _load_or_extract_frames(run_dir: Path, config: dict[str, Any], limit: int | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    path = run_dir / "dataset" / "rgb_frames_uint8.npz"
    if path.exists() and limit is None:
        data = np.load(path, allow_pickle=False)
        return data["x"], data["y"], data["split_index"]
    rows = _read_csv(run_dir / "pilot_manifest.csv")
    if limit is not None:
        rows = rows[:limit]
    x_values = []
    y_values = []
    split_values = []
    meta_rows = []
    for idx, row in enumerate(rows, start=1):
        print(f"[e4-v] rgb extract {idx}/{len(rows)} {row['split']} {row['canonical_gloss']}")
        frames, metadata = _read_video_frames(Path(row["video_path"]), int(config["frames"]), int(config["image_size"]), str(config["crop_mode"]))
        x_values.append(frames)
        y_values.append(int(row["class_id"]))
        split_values.append(SPLITS[row["split"]])
        meta_rows.append({**row, **metadata})
    x = np.stack(x_values, axis=0).astype(np.uint8)
    y = np.asarray(y_values, dtype=np.int64)
    split_index = np.asarray(split_values, dtype=np.int64)
    if limit is None:
        np.savez_compressed(path, x=x, y=y, split_index=split_index)
        _write_csv(run_dir / "dataset" / "rgb_frame_manifest.csv", meta_rows, ["sample_id", "split", "canonical_gloss", "class_id", "signer_id", "video_path", "frame_count", "fps", "width", "height", "hand_hit_rate", "warnings", "notes"])
    return x, y, split_index


def _load_or_embed_rgb(run_dir: Path, config: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    path = run_dir / "dataset" / "rgb_frame_features.npz"
    if path.exists():
        data = np.load(path, allow_pickle=False)
        return data["features"].astype(np.float32), data["y"].astype(np.int64), data["split_index"].astype(np.int64)
    frames, y, split_index = _load_or_extract_frames(run_dir, config)
    encoder = _build_encoder(config)
    flat = frames.reshape((-1, int(config["image_size"]), int(config["image_size"]), 3)).astype(np.float32)
    print(f"[e4-v] embedding {flat.shape[0]} frames")
    embeddings = encoder.predict(flat, batch_size=int(config["embedding_batch_size"]), verbose=2)
    features = embeddings.reshape((frames.shape[0], int(config["frames"]), embeddings.shape[-1])).astype(np.float32)
    np.savez_compressed(path, features=features, y=y, split_index=split_index)
    return features, y, split_index


def _build_rgb_head(frames: int, feature_dim: int, classes: int, lr: float):
    import tensorflow as tf

    inputs = tf.keras.Input(shape=(frames, feature_dim), name="rgb_features")
    x = tf.keras.layers.LayerNormalization()(inputs)
    x = tf.keras.layers.Conv1D(96, 3, padding="same", activation="relu")(x)
    x = tf.keras.layers.Dropout(0.25)(x)
    x = tf.keras.layers.GlobalAveragePooling1D()(x)
    x = tf.keras.layers.Dense(48, activation="relu")(x)
    x = tf.keras.layers.Dropout(0.20)(x)
    outputs = tf.keras.layers.Dense(classes, activation="softmax")(x)
    model = tf.keras.Model(inputs, outputs, name="e4_v_rgb_upper_body")
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=lr), loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    return model


def _evaluate_probs(probs: np.ndarray, y: np.ndarray, split_index: np.ndarray) -> dict[str, Any]:
    pred = np.argmax(probs, axis=1)
    out: dict[str, Any] = {}
    for split, sid in SPLITS.items():
        mask = split_index == sid
        per_class = []
        for cid, gloss in enumerate(CLASSES):
            cmask = mask & (y == cid)
            if np.any(cmask):
                per_class.append({"gloss": gloss, "count": int(np.sum(cmask)), "correct": int(np.sum(pred[cmask] == y[cmask])), "accuracy": float(np.mean(pred[cmask] == y[cmask]))})
        out[split] = {
            "accuracy": float(np.mean(pred[mask] == y[mask])) if np.any(mask) else None,
            "count": int(np.sum(mask)),
            "mean_confidence": float(np.mean(np.max(probs[mask], axis=1))) if np.any(mask) else None,
            "predicted_class_counts": dict(sorted(Counter(CLASSES[int(v)] for v in pred[mask]).items())),
            "per_class": per_class,
            "confusion_matrix": [[int(np.sum(mask & (y == true) & (pred == guess))) for guess in range(len(CLASSES))] for true in range(len(CLASSES))],
        }
    return out


def _evaluate_model(model: Any, inputs: Any, y: np.ndarray, split_index: np.ndarray, batch_size: int) -> dict[str, Any]:
    probs = model.predict(inputs, batch_size=batch_size, verbose=0)
    return _evaluate_probs(probs, y, split_index)


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    x, frame_mask, y, _split = _load_landmark(run_dir)
    frames, ry, _rsplit = _load_or_extract_frames(run_dir, config, limit=int(args.rows))
    encoder = _build_encoder(config)
    rgb = encoder.predict(frames.reshape((-1, int(config["image_size"]), int(config["image_size"]), 3)).astype(np.float32), batch_size=8, verbose=0)
    rgb = rgb.reshape((frames.shape[0], int(config["frames"]), rgb.shape[-1])).astype(np.float32)
    result: dict[str, Any] = {"rows": int(args.rows), "branches": {}}
    if "landmark_binary_control" in config["branches"]:
        tf.keras.backend.clear_session()
        model = _build_landmark_model("conv1d_baseline", (96, 258), len(CLASSES), float(config["learning_rate"]))
        probs = model.predict(_landmark_inputs_for("conv1d_baseline", x[: int(args.rows)], frame_mask[: int(args.rows)]), batch_size=2, verbose=0)
        loss = model.train_on_batch(_landmark_inputs_for("conv1d_baseline", x[: int(args.rows)], frame_mask[: int(args.rows)]), y[: int(args.rows)])
        weights = run_dir / "smoke" / "landmark_binary_control.weights.h5"
        model.save_weights(weights)
        result["branches"]["landmark_binary_control"] = {"forward_shape": [int(v) for v in probs.shape], "train_on_batch": [float(v) for v in np.atleast_1d(loss).tolist()], "weights_saved": str(weights.resolve())}
    if "rgb_upper_body" in config["branches"]:
        tf.keras.backend.clear_session()
        model = _build_rgb_head(int(config["frames"]), int(rgb.shape[-1]), len(CLASSES), float(config["learning_rate"]))
        probs = model.predict(rgb, batch_size=2, verbose=0)
        loss = model.train_on_batch(rgb, ry)
        weights = run_dir / "smoke" / "rgb_upper_body.weights.h5"
        model.save_weights(weights)
        result["branches"]["rgb_upper_body"] = {"forward_shape": [int(v) for v in probs.shape], "train_on_batch": [float(v) for v in np.atleast_1d(loss).tolist()], "weights_saved": str(weights.resolve())}
    _write_json(run_dir / "smoke" / "smoke_summary.json", result)
    return result


def run(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    for relative in ("dataset", "logs", "metrics", "models"):
        (run_dir / relative).mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    metrics: dict[str, Any] = {"experiment": config["experiment"], "run_dir": str(run_dir.resolve()), "classes": CLASSES, "branches": {}, "passed": True}
    if "landmark_binary_control" in config["branches"]:
        landmarks, frame_mask, y, split_index = _load_landmark(run_dir)
        train = split_index == SPLITS["train"]
        val = split_index == SPLITS["val"]
        metrics["branches"]["landmark_binary_control"] = {}
        for seed in config["seeds"]:
            seed = int(seed)
            tf.keras.backend.clear_session()
            tf.keras.utils.set_random_seed(seed)
            seed_dir = run_dir / "models" / "landmark_binary_control" / f"seed_{seed}"
            seed_dir.mkdir(parents=True, exist_ok=True)
            latest = seed_dir / "latest.weights.h5"
            best = seed_dir / "best.weights.h5"
            if latest.exists() and not args.resume:
                raise FileExistsError(f"landmark seed {seed}: latest exists; use --resume")
            model = _build_landmark_model("conv1d_baseline", (96, 258), len(CLASSES), float(config["learning_rate"]))
            initial_epoch = 0
            epoch_file = run_dir / "logs" / f"landmark_seed_{seed}_epoch_count.txt"
            if args.resume and latest.exists():
                model.load_weights(latest)
                initial_epoch = int(epoch_file.read_text(encoding="utf-8"))
            history = model.fit(
                _landmark_inputs_for("conv1d_baseline", landmarks[train], frame_mask[train]),
                y[train],
                validation_data=(_landmark_inputs_for("conv1d_baseline", landmarks[val], frame_mask[val]), y[val]),
                batch_size=int(config["batch_size"]),
                epochs=initial_epoch + int(config["epochs"]),
                initial_epoch=initial_epoch,
                callbacks=[tf.keras.callbacks.ModelCheckpoint(str(best), monitor="val_accuracy", mode="max", save_best_only=True, save_weights_only=True), tf.keras.callbacks.CSVLogger(str(run_dir / "logs" / f"landmark_seed_{seed}_history.csv"), append=True)],
                verbose=2,
            )
            model.save_weights(latest)
            epoch_file.write_text(str(initial_epoch + int(config["epochs"])), encoding="utf-8")
            metrics["branches"]["landmark_binary_control"][str(seed)] = {"latest": _evaluate_model(model, _landmark_inputs_for("conv1d_baseline", landmarks, frame_mask), y, split_index, int(config["batch_size"])), "history_last": {k: float(v[-1]) for k, v in history.history.items()}}
    if "rgb_upper_body" in config["branches"]:
        rgb, y, split_index = _load_or_embed_rgb(run_dir, config)
        train = split_index == SPLITS["train"]
        val = split_index == SPLITS["val"]
        metrics["branches"]["rgb_upper_body"] = {}
        for seed in config["seeds"]:
            seed = int(seed)
            tf.keras.backend.clear_session()
            tf.keras.utils.set_random_seed(seed)
            seed_dir = run_dir / "models" / "rgb_upper_body" / f"seed_{seed}"
            seed_dir.mkdir(parents=True, exist_ok=True)
            latest = seed_dir / "latest.keras"
            best = seed_dir / "best.keras"
            if latest.exists() and not args.resume:
                raise FileExistsError(f"rgb seed {seed}: latest exists; use --resume")
            if args.resume and latest.exists():
                model = tf.keras.models.load_model(latest)
                epoch_file = run_dir / "logs" / f"rgb_seed_{seed}_epoch_count.txt"
                initial_epoch = int(epoch_file.read_text(encoding="utf-8"))
            else:
                model = _build_rgb_head(int(config["frames"]), int(rgb.shape[-1]), len(CLASSES), float(config["learning_rate"]))
                initial_epoch = 0
                epoch_file = run_dir / "logs" / f"rgb_seed_{seed}_epoch_count.txt"
            history = model.fit(
                rgb[train],
                y[train],
                validation_data=(rgb[val], y[val]),
                batch_size=int(config["batch_size"]),
                epochs=initial_epoch + int(config["epochs"]),
                initial_epoch=initial_epoch,
                callbacks=[tf.keras.callbacks.ModelCheckpoint(str(best), monitor="val_accuracy", mode="max", save_best_only=True), tf.keras.callbacks.CSVLogger(str(run_dir / "logs" / f"rgb_seed_{seed}_history.csv"), append=True)],
                verbose=2,
            )
            model.save(latest)
            epoch_file.write_text(str(initial_epoch + int(config["epochs"])), encoding="utf-8")
            metrics["branches"]["rgb_upper_body"][str(seed)] = {"latest": _evaluate_model(model, rgb, y, split_index, int(config["batch_size"])), "history_last": {k: float(v[-1]) for k, v in history.history.items()}}
    metrics["elapsed_seconds"] = time.perf_counter() - start
    metrics["summary"] = _summary(metrics)
    _write_json(run_dir / "metrics" / "metrics.json", metrics)
    return metrics


def _summary(metrics: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"by_branch": {}}
    for branch, seeds in metrics.get("branches", {}).items():
        tests = []
        sorry = []
        good = []
        for payload in seeds.values():
            test = payload["latest"]["test"]
            tests.append(float(test["accuracy"]))
            by_class = {row["gloss"]: float(row["accuracy"]) for row in test["per_class"]}
            good.append(by_class.get("GOOD", 0.0))
            sorry.append(by_class.get("SORRY", 0.0))
        out["by_branch"][branch] = {
            "mean_latest_test": float(np.mean(tests)) if tests else 0.0,
            "min_latest_test": float(np.min(tests)) if tests else 0.0,
            "mean_good_recall": float(np.mean(good)) if good else 0.0,
            "mean_sorry_recall": float(np.mean(sorry)) if sorry else 0.0,
            "min_sorry_recall": float(np.min(sorry)) if sorry else 0.0,
        }
    rgb = out["by_branch"].get("rgb_upper_body", {})
    lm = out["by_branch"].get("landmark_binary_control", {})
    out["decision_hint"] = {
        "rgb_gain_over_landmark": float(rgb.get("mean_latest_test", 0.0) - lm.get("mean_latest_test", 0.0)) if rgb and lm else None,
        "rgb_specialist_promising": bool(
            rgb
            and rgb.get("mean_latest_test", 0.0) >= 0.90
            and rgb.get("mean_good_recall", 0.0) >= 0.90
            and rgb.get("mean_sorry_recall", 0.0) >= 0.90
            and (not lm or rgb.get("mean_latest_test", 0.0) >= lm.get("mean_latest_test", 0.0) + 0.05)
        ),
    }
    return out


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["pilot_config.json", "pilot_manifest.csv", "selected_classes.csv", "dataset/landmark_binary_features.npz", "README_RUN.md"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if args.require_smoke and not (run_dir / "smoke" / "smoke_summary.json").exists():
        errors.append("missing output: smoke/smoke_summary.json")
    if args.require_metrics and not (run_dir / "metrics" / "metrics.json").exists():
        errors.append("missing output: metrics/metrics.json")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join([
        "# E4-V GOOD/SORRY Specialist Proof",
        "",
        "Compares landmark binary control against an upper-body RGB specialist for the SORRY -> GOOD confusion.",
        "",
        f"- Classes: {', '.join(config['classes'])}",
        f"- Rows: {config['active_rows']}",
        f"- Split counts: {config['split_counts']}",
        f"- Branches: {', '.join(config['branches'])}",
        "",
        "## Smoke",
        "```powershell",
        'cd "F:\\ASL DATASET\\5. Apphear3"',
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_v_sorry_good_specialist smoke --run-dir "{run_dir}"',
        "```",
        "",
        "## Full Training",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_v_sorry_good_specialist run --run-dir "{run_dir}"',
        "```",
        "",
        "Resume:",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_v_sorry_good_specialist run --run-dir "{run_dir}" --resume',
        "```",
        "",
        "## Check",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_v_sorry_good_specialist check --run-dir "{run_dir}" --require-smoke --require-metrics',
        "```",
        "",
    ]) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-V GOOD/SORRY specialist proof")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--e4j-run", type=Path, default=DEFAULT_E4J_RUN)
    prepare_parser.add_argument("--e4u-run", type=Path, default=DEFAULT_E4U_RUN)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--frames", type=int, default=8)
    prepare_parser.add_argument("--image-size", type=int, default=160)
    prepare_parser.add_argument("--crop-mode", choices=["upper_body_center", "full_frame"], default="upper_body_center")
    prepare_parser.add_argument("--encoder", default="mobilenetv3small")
    prepare_parser.add_argument("--weights", default="imagenet")
    prepare_parser.add_argument("--embedding-batch-size", type=int, default=16)
    prepare_parser.add_argument("--batch-size", type=int, default=8)
    prepare_parser.add_argument("--epochs", type=int, default=20)
    prepare_parser.add_argument("--learning-rate", type=float, default=5e-4)
    prepare_parser.add_argument("--branches", nargs="+", default=DEFAULT_BRANCHES)
    prepare_parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    prepare_parser.add_argument("--overwrite", action="store_true")

    smoke_parser = sub.add_parser("smoke")
    smoke_parser.add_argument("--run-dir", type=Path, required=True)
    smoke_parser.add_argument("--rows", type=int, default=8)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--run-dir", type=Path, required=True)
    run_parser.add_argument("--resume", action="store_true")

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--require-smoke", action="store_true")
    check_parser.add_argument("--require-metrics", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "smoke":
            result = smoke(args)
        elif args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileExistsError, FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-v] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
