"""E3-B6 landmark derived-feature augmentation on the frozen E3-B5 split.

This experiment reads the prepared E3-B5 50-class signer-disjoint landmark tensor and appends
simple, deterministic, Android-portable derived features. It writes isolated outputs only.
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

from pipeline.rgb.e3_b4_landmark_temporal import _build_model, _inputs_for, _load_weights_model
from pipeline.rgb.e3_b5_landmark_temporal_scale import _evaluate as _evaluate_e3b5

DEFAULT_SOURCE_RUN = Path("artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed")
DEFAULT_OUTPUT_ROOT = Path("artifacts/recognition_upgrade/e3_landmark_temporal")
DEFAULT_RUN_ID = "pilot_03_feature_augmented"
SPLITS = {"train": 0, "val": 1, "test": 2}
BRANCH_KIND = {
    "aug_conv1d_baseline": "conv1d_baseline",
    "aug_tcn_pool": "tcn_pool",
    "aug_tcn_masked_pool": "tcn_masked_pool",
}


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _load_source(source_run: Path) -> tuple[dict[str, Any], np.lib.npyio.NpzFile]:
    config_path = source_run / "pilot_config.json"
    data_path = source_run / "dataset" / "landmark_features.npz"
    if not config_path.exists():
        raise FileNotFoundError(f"missing E3-B5 config: {config_path}")
    if not data_path.exists():
        raise FileNotFoundError(f"missing E3-B5 tensor: {data_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    data = np.load(data_path, allow_pickle=False)
    required = {"landmarks", "frame_mask", "y", "split_index", "lengths", "old_y", "source_indices", "participant_ids"}
    missing = required.difference(data.files)
    if missing:
        raise ValueError(f"source tensor missing keys: {sorted(missing)}")
    if tuple(data["landmarks"].shape[1:]) != (96, 258):
        raise ValueError(f"expected source landmarks [N,96,258], got {list(data['landmarks'].shape)}")
    return config, data


def _xyz_streams(x: np.ndarray) -> np.ndarray:
    hands_xyz = x[:, :, :126]
    pose = x[:, :, 126:].reshape(x.shape[0], x.shape[1], 33, 4)
    pose_xyz = pose[:, :, :, :3].reshape(x.shape[0], x.shape[1], 99)
    return np.concatenate([hands_xyz, pose_xyz], axis=-1).astype(np.float32)


def _temporal_delta(values: np.ndarray, frame_mask: np.ndarray) -> np.ndarray:
    delta = np.zeros_like(values, dtype=np.float32)
    pair_mask = (frame_mask[:, 1:] > 0.5) & (frame_mask[:, :-1] > 0.5)
    delta[:, 1:] = (values[:, 1:] - values[:, :-1]) * pair_mask[:, :, None].astype(np.float32)
    return delta


def _relation_features(x: np.ndarray, frame_mask: np.ndarray) -> tuple[np.ndarray, list[str]]:
    n, t, _ = x.shape
    hands = x[:, :, :126].reshape(n, t, 2, 21, 3)
    pose = x[:, :, 126:].reshape(n, t, 33, 4)
    pose_xyz = pose[:, :, :, :3]
    pose_vis = pose[:, :, :, 3]
    left_present = (np.any(hands[:, :, 0] != 0.0, axis=(2, 3)) & (frame_mask > 0.5)).astype(np.float32)
    right_present = (np.any(hands[:, :, 1] != 0.0, axis=(2, 3)) & (frame_mask > 0.5)).astype(np.float32)
    real = (frame_mask > 0.5).astype(np.float32)

    left_wrist = hands[:, :, 0, 0, :]
    right_wrist = hands[:, :, 1, 0, :]
    pose_left_wrist = pose_xyz[:, :, 15, :]
    pose_right_wrist = pose_xyz[:, :, 16, :]
    pose_left_shoulder = pose_xyz[:, :, 11, :]
    pose_right_shoulder = pose_xyz[:, :, 12, :]

    def masked_vec(vec: np.ndarray, mask: np.ndarray) -> np.ndarray:
        return (vec * mask[:, :, None]).astype(np.float32)

    left_hand_to_pose_wrist = masked_vec(left_wrist - pose_left_wrist, left_present)
    right_hand_to_pose_wrist = masked_vec(right_wrist - pose_right_wrist, right_present)
    left_hand_to_shoulder = masked_vec(left_wrist - pose_left_shoulder, left_present)
    right_hand_to_shoulder = masked_vec(right_wrist - pose_right_shoulder, right_present)
    both_present = left_present * right_present
    hand_to_hand = masked_vec(left_wrist - right_wrist, both_present)
    hand_distance = np.linalg.norm(hand_to_hand, axis=-1, keepdims=True).astype(np.float32)
    pose_vis_mean = (np.mean(pose_vis, axis=-1, keepdims=True) * real[:, :, None]).astype(np.float32)

    features = np.concatenate(
        [
            left_hand_to_pose_wrist,
            right_hand_to_pose_wrist,
            left_hand_to_shoulder,
            right_hand_to_shoulder,
            hand_to_hand,
            hand_distance,
            left_present[:, :, None],
            right_present[:, :, None],
            real[:, :, None],
            pose_vis_mean,
        ],
        axis=-1,
    ).astype(np.float32)
    names = [
        "left_hand_wrist_minus_pose_wrist_xyz",
        "right_hand_wrist_minus_pose_wrist_xyz",
        "left_hand_wrist_minus_left_shoulder_xyz",
        "right_hand_wrist_minus_right_shoulder_xyz",
        "left_hand_wrist_minus_right_hand_wrist_xyz",
        "hand_wrist_distance",
        "left_hand_present",
        "right_hand_present",
        "frame_valid",
        "pose_visibility_mean",
    ]
    return features, names


def build_augmented_features(landmarks: np.ndarray, frame_mask: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    x = landmarks.astype(np.float32)
    mask = frame_mask.astype(np.float32)
    xyz = _xyz_streams(x)
    velocity = _temporal_delta(xyz, mask)
    acceleration = _temporal_delta(velocity, mask)
    relations, relation_names = _relation_features(x, mask)
    augmented = np.concatenate([x, velocity, acceleration, relations], axis=-1).astype(np.float32)
    invalid = mask <= 0.5
    augmented[invalid] = 0.0
    if np.isnan(augmented).any() or np.isinf(augmented).any():
        raise ValueError("augmented tensor contains NaN or Inf")
    schema = {
        "experiment_schema": "e3_b6_augmented_landmark_v1",
        "base_feature_dim": 258,
        "velocity_dim": 225,
        "acceleration_dim": 225,
        "relation_dim": int(relations.shape[-1]),
        "feature_dim": int(augmented.shape[-1]),
        "layout": [
            {"name": "base_v3_0_landmarks", "start": 0, "end_exclusive": 258},
            {"name": "xyz_velocity", "start": 258, "end_exclusive": 483},
            {"name": "xyz_acceleration", "start": 483, "end_exclusive": 708},
            {"name": "relations_and_presence", "start": 708, "end_exclusive": int(augmented.shape[-1]), "items": relation_names},
        ],
        "mask_rule": "all derived and original channels are zeroed on padded frames; deltas require adjacent real frames",
    }
    return augmented, schema


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    source_config, source = _load_source(args.source_run)
    output = args.output_root / args.run_id
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"output already exists: {output}")
    for relative in ("dataset", "logs", "metrics", "models", "smoke"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    landmarks = source["landmarks"].astype(np.float32)
    frame_mask = source["frame_mask"].astype(np.float32)
    augmented, feature_schema = build_augmented_features(landmarks, frame_mask)
    np.savez_compressed(
        output / "dataset" / "augmented_features.npz",
        features=augmented,
        frame_mask=frame_mask,
        y=source["y"].astype(np.int64),
        split_index=source["split_index"].astype(np.int64),
        lengths=source["lengths"].astype(np.int32),
        old_y=source["old_y"].astype(np.int64),
        source_indices=source["source_indices"].astype(np.int64),
        participant_ids=source["participant_ids"].astype(str),
    )

    source_manifest = args.source_run / "pilot_manifest.csv"
    source_classes = args.source_run / "selected_classes.csv"
    if source_manifest.exists():
        (output / "pilot_manifest.csv").write_text(source_manifest.read_text(encoding="utf-8"), encoding="utf-8")
    if source_classes.exists():
        (output / "selected_classes.csv").write_text(source_classes.read_text(encoding="utf-8"), encoding="utf-8")
    (output / "feature_schema.json").write_text(json.dumps(feature_schema, indent=2), encoding="utf-8")

    branches = list(args.branches)
    unknown = [branch for branch in branches if branch not in BRANCH_KIND]
    if unknown:
        raise ValueError(f"unsupported branches: {unknown}")
    config = {
        "experiment": "e3_b6_feature_augmentation_v1",
        "purpose": "test deterministic derived landmark-motion features on the frozen E3-B5 split",
        "run_dir": str(output.resolve()),
        "source_run": str(args.source_run.resolve()),
        "source_experiment": source_config["experiment"],
        "classes": source_config["classes"],
        "class_count": int(source_config["class_count"]),
        "rows": int(augmented.shape[0]),
        "input_shape": [int(augmented.shape[1]), int(augmented.shape[2])],
        "split_counts": {name: int(np.sum(source["split_index"] == sid)) for name, sid in SPLITS.items()},
        "feature_schema": feature_schema,
        "baseline_reference": {
            "e3_b5_conv1d_mean_best_val": 0.4750,
            "e3_b5_conv1d_mean_best_test": 0.3400,
            "e3_b5_tcn_pool_mean_best_val": 0.4733,
            "e3_b5_tcn_pool_mean_best_test": 0.3433,
            "e3_b5_tcn_masked_pool_mean_best_val": 0.4900,
            "e3_b5_tcn_masked_pool_mean_best_test": 0.3433,
        },
        "batch_size": int(args.batch_size),
        "epochs": int(args.epochs),
        "learning_rate": float(args.learning_rate),
        "branches": branches,
        "branch_model_map": BRANCH_KIND,
        "seeds": [int(seed) for seed in args.seeds],
        "gate": {
            "go_if": [
                "best augmented branch improves mean best-validation over E3-B5 masked TCN by >= 0.03",
                "mean best-test is not below E3-B5 masked TCN",
                "train-validation gap does not increase materially",
                "worst-class and confusion concentration improve in analysis",
            ],
            "no_go_if": [
                "only train accuracy improves",
                "validation/test gap grows",
                "prediction bias increases",
                "test accuracy regresses",
            ],
        },
        "warnings": [
            "Experiment-only feature schema; does not change v3.0 production contract.",
            "If promoted later, every derived feature must be ported to Kotlin with skew tests.",
            "This does not test RGB or non-manual cues.",
        ],
    }
    (output / "pilot_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def _load_dataset(run_dir: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    data_path = run_dir / "dataset" / "augmented_features.npz"
    if not data_path.exists():
        raise FileNotFoundError(f"missing prepared E3-B6 tensor: {data_path}")
    data = np.load(data_path, allow_pickle=False)
    required = {"features", "frame_mask", "y", "split_index", "lengths"}
    missing = required.difference(data.files)
    if missing:
        raise ValueError(f"augmented tensor missing keys: {sorted(missing)}")
    return (
        data["features"].astype(np.float32),
        data["frame_mask"].astype(np.float32),
        data["y"].astype(np.int64),
        data["split_index"].astype(np.int64),
        data["lengths"].astype(np.int32),
    )


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    features, frame_mask, y, split_index, _ = _load_dataset(run_dir)
    train_rows = np.flatnonzero(split_index == 0)[: max(2, min(args.rows, 8))]
    val_rows = np.flatnonzero(split_index == 1)[: max(2, min(args.rows, 8))]
    summary: dict[str, Any] = {
        "experiment": config["experiment"],
        "run_dir": str(run_dir.resolve()),
        "input_shape": config["input_shape"],
        "train_rows": int(len(train_rows)),
        "val_rows": int(len(val_rows)),
        "branches": {},
    }
    for branch in config["branches"]:
        kind = BRANCH_KIND[branch]
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(12345)
        model = _build_model(kind, tuple(config["input_shape"]), int(config["class_count"]), float(config["learning_rate"]))
        probs = model.predict(_inputs_for(kind, features[val_rows], frame_mask[val_rows]), batch_size=2, verbose=0)
        loss = model.train_on_batch(_inputs_for(kind, features[train_rows], frame_mask[train_rows]), y[train_rows])
        weights_path = run_dir / "smoke" / f"{branch}.weights.h5"
        model.save_weights(weights_path)
        reloaded = _load_weights_model(kind, tuple(config["input_shape"]), int(config["class_count"]), float(config["learning_rate"]), weights_path)
        reloaded_probs = reloaded.predict(_inputs_for(kind, features[val_rows[:2]], frame_mask[val_rows[:2]]), batch_size=2, verbose=0)
        summary["branches"][branch] = {
            "model_kind": kind,
            "forward_shape": [int(v) for v in probs.shape],
            "train_on_batch": [float(v) for v in np.atleast_1d(loss).tolist()],
            "weights_saved": str(weights_path.resolve()),
            "reload_forward_shape": [int(v) for v in reloaded_probs.shape],
        }
    (run_dir / "smoke" / "smoke_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config_path = run_dir / "pilot_config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"missing config; run prepare first: {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    features, frame_mask, y, split_index, _ = _load_dataset(run_dir)
    train_mask = split_index == 0
    val_mask = split_index == 1
    start = time.perf_counter()
    metrics: dict[str, Any] = {
        "experiment": config["experiment"],
        "run_dir": str(run_dir.resolve()),
        "input_shape": config["input_shape"],
        "class_count": int(config["class_count"]),
        "baseline_reference": config["baseline_reference"],
        "branches": {},
        "elapsed_seconds": None,
        "passed": True,
    }
    for branch in config["branches"]:
        kind = BRANCH_KIND[branch]
        metrics["branches"][branch] = {}
        for seed in config["seeds"]:
            seed = int(seed)
            tf.keras.backend.clear_session()
            tf.keras.utils.set_random_seed(seed)
            seed_dir = run_dir / "models" / branch / f"seed_{seed}"
            seed_dir.mkdir(parents=True, exist_ok=True)
            latest = seed_dir / "latest.weights.h5"
            best = seed_dir / "best.weights.h5"
            epoch_file = run_dir / "logs" / f"{branch}_seed_{seed}_epoch_count.txt"
            history_path = run_dir / "logs" / f"{branch}_seed_{seed}_history.csv"
            if latest.exists() and not args.resume:
                raise FileExistsError(f"{branch} seed {seed}: latest weights exist; rerun with --resume: {latest}")
            model = _build_model(kind, tuple(config["input_shape"]), int(config["class_count"]), float(config["learning_rate"]))
            if args.resume and latest.exists():
                model.load_weights(latest)
                initial_epoch = int(epoch_file.read_text(encoding="utf-8"))
            else:
                initial_epoch = 0
            history = model.fit(
                _inputs_for(kind, features[train_mask], frame_mask[train_mask]),
                y[train_mask],
                validation_data=(_inputs_for(kind, features[val_mask], frame_mask[val_mask]), y[val_mask]),
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
            metrics["branches"][branch][str(seed)] = {
                "latest": _evaluate_e3b5(kind, model, features, frame_mask, y, split_index, int(config["batch_size"]), config["classes"]),
                "best": _evaluate_e3b5(
                    kind,
                    _load_weights_model(kind, tuple(config["input_shape"]), int(config["class_count"]), float(config["learning_rate"]), best),
                    features,
                    frame_mask,
                    y,
                    split_index,
                    int(config["batch_size"]),
                    config["classes"],
                ),
                "epoch_count_total": int(total_epochs),
                "history_last": {key: float(values[-1]) for key, values in history.history.items() if values},
            }
            (run_dir / "metrics" / "metrics_partial.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    metrics["elapsed_seconds"] = time.perf_counter() - start
    metrics["summary"] = _summarize(metrics)
    (run_dir / "metrics" / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (run_dir / "metrics" / "metrics.md").write_text(_metrics_markdown(metrics), encoding="utf-8")
    return metrics


def _summarize(metrics: dict[str, Any]) -> dict[str, Any]:
    by_branch: dict[str, Any] = {}
    winners: dict[str, str] = {}
    for branch, seeds in metrics["branches"].items():
        vals = [result["best"]["val"]["accuracy"] for result in seeds.values()]
        tests = [result["best"]["test"]["accuracy"] for result in seeds.values()]
        trains = [result["best"]["train"]["accuracy"] for result in seeds.values()]
        by_branch[branch] = {
            "mean_best_train": float(np.mean(trains)),
            "mean_best_val": float(np.mean(vals)),
            "std_best_val": float(np.std(vals)),
            "mean_best_test": float(np.mean(tests)),
            "std_best_test": float(np.std(tests)),
            "mean_train_val_gap": float(np.mean(np.asarray(trains) - np.asarray(vals))),
            "mean_val_test_gap": float(np.mean(np.asarray(vals) - np.asarray(tests))),
            "seed_count": int(len(vals)),
        }
    seed_ids = sorted({seed for branch in metrics["branches"].values() for seed in branch})
    for seed in seed_ids:
        candidates = {branch: values[seed]["best"]["val"]["accuracy"] for branch, values in metrics["branches"].items() if seed in values}
        winners[seed] = max(candidates, key=candidates.get)
    best_branch = max(by_branch, key=lambda branch: by_branch[branch]["mean_best_val"])
    baseline = metrics["baseline_reference"]
    gain_val = by_branch[best_branch]["mean_best_val"] - float(baseline["e3_b5_tcn_masked_pool_mean_best_val"])
    gain_test = by_branch[best_branch]["mean_best_test"] - float(baseline["e3_b5_tcn_masked_pool_mean_best_test"])
    return {
        "by_branch": by_branch,
        "winner_by_seed_best_val": winners,
        "decision_hint": {
            "best_mean_validation_branch": best_branch,
            "validation_gain_over_e3_b5_masked": float(gain_val),
            "test_gain_over_e3_b5_masked": float(gain_test),
            "promising": bool(gain_val >= 0.03 and gain_test >= 0.0),
        },
    }


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["pilot_config.json", "feature_schema.json", "dataset/augmented_features.npz", "README_RUN.md"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    config: dict[str, Any] = {}
    config_path = run_dir / "pilot_config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        features, frame_mask, y, split_index, _ = _load_dataset(run_dir)
        if list(features.shape[1:]) != config.get("input_shape"):
            errors.append(f"feature shape mismatch: {list(features.shape[1:])} != {config.get('input_shape')}")
        if np.isnan(features).any() or np.isinf(features).any():
            errors.append("feature tensor contains NaN or Inf")
        if np.any(features[frame_mask <= 0.5] != 0.0):
            errors.append("padded frames are not zeroed")
        if len(y) != int(config.get("rows", -1)) or len(split_index) != int(config.get("rows", -1)):
            errors.append("row count mismatch")
    metrics_path = run_dir / "metrics" / "metrics.json"
    if args.require_metrics and not metrics_path.exists():
        errors.append("missing output: metrics/metrics.json")
    if metrics_path.exists() and config:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        for branch in config.get("branches", []):
            for seed in config.get("seeds", []):
                for relative in (
                    f"models/{branch}/seed_{seed}/latest.weights.h5",
                    f"models/{branch}/seed_{seed}/best.weights.h5",
                    f"logs/{branch}_seed_{seed}_history.csv",
                    f"logs/{branch}_seed_{seed}_epoch_count.txt",
                ):
                    if not (run_dir / relative).exists():
                        errors.append(f"missing output: {relative}")
                if str(seed) not in metrics.get("branches", {}).get(branch, {}):
                    errors.append(f"missing metrics for {branch} seed {seed}")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    (run_dir / "check_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join(
        [
            "# E3-B6 Landmark Feature Augmentation",
            "",
            "This is an isolated experiment on the frozen E3-B5 split. It does not change Android or production assets.",
            "",
            "## Settings",
            "",
            f"- Input shape: {config['input_shape']}",
            f"- Classes: {config['class_count']}",
            f"- Rows: {config['rows']}",
            f"- Branches: {', '.join(config['branches'])}",
            f"- Seeds: {', '.join(str(seed) for seed in config['seeds'])}",
            f"- Epochs per run command: {config['epochs']}",
            f"- Batch size: {config['batch_size']}",
            "",
            "## Smoke",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b6_feature_augmentation smoke --run-dir "{run_dir}"',
            "```",
            "",
            "## Full Run",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b6_feature_augmentation run --run-dir "{run_dir}"',
            "```",
            "",
            "## Resume",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b6_feature_augmentation run --run-dir "{run_dir}" --resume',
            "```",
            "",
            "## Check",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b6_feature_augmentation check --run-dir "{run_dir}" --require-metrics',
            "```",
            "",
        ]
    )


def _metrics_markdown(metrics: dict[str, Any]) -> str:
    lines = [
        "# E3-B6 Landmark Feature Augmentation Metrics",
        "",
        "Frozen E3-B5 split. Test accuracy is reporting-only after validation selection.",
        "",
        "| Branch | Seed | Best Val | Best Test | Latest Val | Latest Test |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for branch, seeds in metrics["branches"].items():
        for seed, result in seeds.items():
            lines.append(
                f"| {branch} | {seed} | {result['best']['val']['accuracy']:.4f} | "
                f"{result['best']['test']['accuracy']:.4f} | {result['latest']['val']['accuracy']:.4f} | "
                f"{result['latest']['test']['accuracy']:.4f} |"
            )
    lines.extend(["", "## Summary", "", "```json", json.dumps(metrics.get("summary", {}), indent=2), "```", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="E3-B6 landmark feature augmentation")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    prepare_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    prepare_parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    prepare_parser.add_argument("--batch-size", type=int, default=8)
    prepare_parser.add_argument("--epochs", type=int, default=12)
    prepare_parser.add_argument("--learning-rate", type=float, default=5e-4)
    prepare_parser.add_argument("--branches", nargs="+", default=list(BRANCH_KIND))
    prepare_parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    prepare_parser.add_argument("--overwrite", action="store_true")

    smoke_parser = sub.add_parser("smoke")
    smoke_parser.add_argument("--run-dir", type=Path, required=True)
    smoke_parser.add_argument("--rows", type=int, default=8)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--run-dir", type=Path, required=True)
    run_parser.add_argument("--resume", action="store_true")

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
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
    except (FileNotFoundError, KeyError, ValueError, OSError) as error:
        print(f"[rgb/e3-b6] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
