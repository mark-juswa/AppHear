"""E3-B5 larger landmark-temporal validation.

This experiment scales the E3-B4 landmark-only temporal comparison from a 7-class pilot to a
deterministic signer-disjoint subset from ASL Citizen `features_streaming`. It is isolated from
Android and production recognizer assets.
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

DEFAULT_FEATURES_DIR = Path(r"F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming")
DEFAULT_VOCAB_PATH = Path(r"F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features\vocab.json")
DEFAULT_OUTPUT_ROOT = Path("artifacts/recognition_upgrade/e3_landmark_temporal")
DEFAULT_RUN_ID = "pilot_02_50class_multiseed"
DEFAULT_BRANCHES = ["conv1d_baseline", "tcn_pool", "tcn_masked_pool"]
SPLITS = {"train": 0, "val": 1, "test": 2}


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _load_vocab(path: Path) -> tuple[dict[str, int], dict[int, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing vocab: {path}")
    gloss_to_id = {str(k): int(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
    id_to_gloss = {value: key for key, value in gloss_to_id.items()}
    return gloss_to_id, id_to_gloss


def _open_split(features_dir: Path, split: str) -> Any:
    path = features_dir / f"{split}.npz"
    if not path.exists():
        raise FileNotFoundError(f"missing feature split: {path}")
    return np.load(path, allow_pickle=False)


def _load_split_meta(features_dir: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for split in SPLITS:
        data = _open_split(features_dir, split)
        required = {"X", "frame_mask", "lengths", "y", "participant_ids", "schema_version", "t_max"}
        missing = required.difference(data.files)
        if missing:
            raise ValueError(f"{split}.npz missing keys: {sorted(missing)}")
        y = data["y"].astype(np.int64)
        participant_ids = data["participant_ids"].astype(str)
        lengths = data["lengths"].astype(np.int32)
        schema_version = str(np.asarray(data["schema_version"]).item())
        t_max = int(np.asarray(data["t_max"]).item())
        if tuple(data["X"].shape[1:]) != (96, 258):
            raise ValueError(f"{split}.npz expected X[* ,96,258], got {list(data['X'].shape)}")
        if data["frame_mask"].shape != data["X"].shape[:2]:
            raise ValueError(f"{split}.npz frame_mask does not match X time dimension")
        out[split] = {
            "y": y,
            "participant_ids": participant_ids,
            "lengths": lengths,
            "counts": Counter(map(int, y.tolist())),
            "schema_version": schema_version,
            "t_max": t_max,
            "rows": int(len(y)),
            "participants": sorted(set(map(str, participant_ids.tolist()))),
        }
    return out


def _eligible_classes(
    meta: dict[str, dict[str, Any]],
    id_to_gloss: dict[int, str],
    train_per_class: int,
    val_per_class: int,
    test_per_class: int,
) -> list[int]:
    eligible = []
    for class_id in sorted(id_to_gloss):
        if (
            meta["train"]["counts"][class_id] >= train_per_class
            and meta["val"]["counts"][class_id] >= val_per_class
            and meta["test"]["counts"][class_id] >= test_per_class
        ):
            eligible.append(class_id)
    return sorted(
        eligible,
        key=lambda cid: (
            -meta["train"]["counts"][cid],
            -meta["val"]["counts"][cid],
            -meta["test"]["counts"][cid],
            id_to_gloss[cid],
        ),
    )


def inspect(args: argparse.Namespace) -> dict[str, Any]:
    _, id_to_gloss = _load_vocab(args.vocab_path)
    meta = _load_split_meta(args.features_dir)
    thresholds = [(8, 2, 2), (16, 4, 4), (24, 6, 6), (32, 8, 8)]
    support = []
    for train_n, val_n, test_n in thresholds:
        eligible = _eligible_classes(meta, id_to_gloss, train_n, val_n, test_n)
        support.append({"train_per_class": train_n, "val_per_class": val_n, "test_per_class": test_n, "eligible_classes": len(eligible)})
    selected = _eligible_classes(meta, id_to_gloss, args.train_per_class, args.val_per_class, args.test_per_class)[: args.class_count]
    result = {
        "experiment": "e3_b5_landmark_temporal_scale_v1",
        "features_dir": str(args.features_dir.resolve()),
        "vocab_path": str(args.vocab_path.resolve()),
        "split_rows": {split: meta[split]["rows"] for split in SPLITS},
        "split_participants": {split: meta[split]["participants"] for split in SPLITS},
        "participant_overlap": {
            "train_val": sorted(set(meta["train"]["participants"]) & set(meta["val"]["participants"])),
            "train_test": sorted(set(meta["train"]["participants"]) & set(meta["test"]["participants"])),
            "val_test": sorted(set(meta["val"]["participants"]) & set(meta["test"]["participants"])),
        },
        "support_thresholds": support,
        "requested_class_count": int(args.class_count),
        "eligible_for_requested_threshold": len(
            _eligible_classes(meta, id_to_gloss, args.train_per_class, args.val_per_class, args.test_per_class)
        ),
        "selected_classes_preview": [
            {
                "old_class_id": int(cid),
                "gloss": id_to_gloss[cid],
                "train": int(meta["train"]["counts"][cid]),
                "val": int(meta["val"]["counts"][cid]),
                "test": int(meta["test"]["counts"][cid]),
            }
            for cid in selected[:20]
        ],
    }
    return result


def _choose_indices(y: np.ndarray, class_ids: list[int], per_class: int, seed: int, offset: int) -> dict[int, np.ndarray]:
    rng = np.random.default_rng(seed + offset)
    chosen: dict[int, np.ndarray] = {}
    for cid in class_ids:
        candidates = np.flatnonzero(y == cid)
        if len(candidates) < per_class:
            raise ValueError(f"class {cid} has {len(candidates)} candidates, need {per_class}")
        selected = rng.choice(candidates, size=per_class, replace=False)
        chosen[cid] = np.sort(selected)
    return chosen


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    _, id_to_gloss = _load_vocab(args.vocab_path)
    meta = _load_split_meta(args.features_dir)
    output = args.output_root / args.run_id
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"output already exists: {output}")
    for relative in ("dataset", "logs", "metrics", "models", "smoke"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    all_eligible = _eligible_classes(meta, id_to_gloss, args.train_per_class, args.val_per_class, args.test_per_class)
    if len(all_eligible) < args.class_count:
        raise ValueError(
            f"only {len(all_eligible)} classes meet support "
            f"{args.train_per_class}/{args.val_per_class}/{args.test_per_class}; requested {args.class_count}"
        )
    selected_old_ids = all_eligible[: args.class_count]
    old_to_new = {old_id: new_id for new_id, old_id in enumerate(selected_old_ids)}
    class_names = [id_to_gloss[cid] for cid in selected_old_ids]

    selected_by_split = {
        "train": _choose_indices(meta["train"]["y"], selected_old_ids, args.train_per_class, args.seed, 11),
        "val": _choose_indices(meta["val"]["y"], selected_old_ids, args.val_per_class, args.seed, 17),
        "test": _choose_indices(meta["test"]["y"], selected_old_ids, args.test_per_class, args.seed, 23),
    }
    landmarks_parts = []
    frame_mask_parts = []
    y_parts = []
    split_parts = []
    lengths_parts = []
    old_y_parts = []
    source_index_parts = []
    participant_parts = []
    rows: list[dict[str, Any]] = []

    for split, split_id in SPLITS.items():
        data = _open_split(args.features_dir, split)
        ordered: list[int] = []
        for old_id in selected_old_ids:
            ordered.extend(selected_by_split[split][old_id].tolist())
        ordered_array = np.asarray(ordered, dtype=np.int64)
        split_y_old = meta[split]["y"][ordered_array].astype(np.int64)
        split_y_new = np.asarray([old_to_new[int(v)] for v in split_y_old], dtype=np.int64)
        split_pids = meta[split]["participant_ids"][ordered_array].astype(str)
        split_lengths = meta[split]["lengths"][ordered_array].astype(np.int32)

        landmarks_parts.append(data["X"][ordered_array].astype(np.float32))
        frame_mask_parts.append(data["frame_mask"][ordered_array].astype(np.float32))
        y_parts.append(split_y_new)
        split_parts.append(np.full(len(ordered_array), split_id, dtype=np.int64))
        lengths_parts.append(split_lengths)
        old_y_parts.append(split_y_old)
        source_index_parts.append(ordered_array)
        participant_parts.append(split_pids)

        for local_offset, source_index in enumerate(ordered_array.tolist()):
            old_id = int(split_y_old[local_offset])
            rows.append(
                {
                    "row_index": len(rows),
                    "split": split,
                    "source_split": split,
                    "source_index": int(source_index),
                    "participant_id": str(split_pids[local_offset]),
                    "old_class_id": old_id,
                    "new_class_id": int(old_to_new[old_id]),
                    "gloss": id_to_gloss[old_id],
                    "length": int(split_lengths[local_offset]),
                    "schema_version": meta[split]["schema_version"],
                }
            )

    landmarks = np.concatenate(landmarks_parts, axis=0)
    frame_mask = np.concatenate(frame_mask_parts, axis=0)
    y = np.concatenate(y_parts, axis=0)
    split_index = np.concatenate(split_parts, axis=0)
    lengths = np.concatenate(lengths_parts, axis=0)
    old_y = np.concatenate(old_y_parts, axis=0)
    source_indices = np.concatenate(source_index_parts, axis=0)
    participant_ids = np.concatenate(participant_parts, axis=0)

    if landmarks.shape[1:] != (96, 258):
        raise ValueError(f"prepared tensor has wrong shape: {list(landmarks.shape)}")
    np.savez_compressed(
        output / "dataset" / "landmark_features.npz",
        landmarks=landmarks,
        frame_mask=frame_mask,
        y=y,
        split_index=split_index,
        lengths=lengths,
        old_y=old_y,
        source_indices=source_indices,
        participant_ids=participant_ids,
    )
    _write_csv(
        output / "pilot_manifest.csv",
        rows,
        ["row_index", "split", "source_split", "source_index", "participant_id", "old_class_id", "new_class_id", "gloss", "length", "schema_version"],
    )
    selected_rows = [
        {
            "new_class_id": old_to_new[cid],
            "old_class_id": cid,
            "gloss": id_to_gloss[cid],
            "source_train": meta["train"]["counts"][cid],
            "source_val": meta["val"]["counts"][cid],
            "source_test": meta["test"]["counts"][cid],
        }
        for cid in selected_old_ids
    ]
    _write_csv(output / "selected_classes.csv", selected_rows, ["new_class_id", "old_class_id", "gloss", "source_train", "source_val", "source_test"])

    seeds = [int(seed) for seed in args.seeds]
    config = {
        "experiment": "e3_b5_landmark_temporal_scale_v1",
        "purpose": "larger signer-disjoint landmark-only temporal validation; not production training",
        "run_dir": str(output.resolve()),
        "features_dir": str(args.features_dir.resolve()),
        "vocab_path": str(args.vocab_path.resolve()),
        "input_shape": [96, 258],
        "schema_version": sorted(set(row["schema_version"] for row in rows)),
        "class_count": int(args.class_count),
        "classes": class_names,
        "old_class_ids": [int(cid) for cid in selected_old_ids],
        "rows": int(len(landmarks)),
        "split_counts": {name: int(np.sum(split_index == sid)) for name, sid in SPLITS.items()},
        "per_class": {"train": int(args.train_per_class), "val": int(args.val_per_class), "test": int(args.test_per_class)},
        "participant_overlap": {
            "train_val": sorted(set(meta["train"]["participants"]) & set(meta["val"]["participants"])),
            "train_test": sorted(set(meta["train"]["participants"]) & set(meta["test"]["participants"])),
            "val_test": sorted(set(meta["val"]["participants"]) & set(meta["test"]["participants"])),
        },
        "batch_size": int(args.batch_size),
        "epochs": int(args.epochs),
        "learning_rate": float(args.learning_rate),
        "branches": list(args.branches),
        "seeds": seeds,
        "selection_policy": {
            "class_selection": "top supported classes by train/val/test counts, then gloss name",
            "row_selection": "deterministic random sample within each source split and class",
            "selection_seed": int(args.seed),
            "validation_rule": "choose checkpoint and branch by validation metrics only; test remains reporting-only",
        },
        "gate": {
            "go_if": [
                "tcn_masked_pool has the highest mean best-validation accuracy across seeds",
                "tcn_masked_pool wins or ties validation in at least two of three seeds",
                "tcn_masked_pool test accuracy is not materially below the best comparator after validation selection",
                "prediction distribution does not collapse into a small number of classes",
            ],
            "no_go_if": [
                "masked TCN advantage disappears on the larger class set",
                "all branches are near random baseline",
                "training accuracy rises while validation/test stay flat",
                "predictions concentrate heavily into a few glosses",
            ],
        },
        "warnings": [
            "This does not change Android or production recognizer assets.",
            "This still uses the current 258-feature landmark contract.",
            "This tests isolated sign classification, not continuous recognition.",
        ],
    }
    (output / "pilot_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def _load_dataset(run_dir: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    path = run_dir / "dataset" / "landmark_features.npz"
    if not path.exists():
        raise FileNotFoundError(f"missing prepared tensor: {path}")
    data = np.load(path, allow_pickle=False)
    required = {"landmarks", "frame_mask", "y", "split_index", "lengths"}
    missing = required.difference(data.files)
    if missing:
        raise ValueError(f"landmark tensor missing keys: {sorted(missing)}")
    landmarks = data["landmarks"].astype(np.float32)
    frame_mask = data["frame_mask"].astype(np.float32)
    y = data["y"].astype(np.int64)
    split_index = data["split_index"].astype(np.int64)
    lengths = data["lengths"].astype(np.int32)
    if landmarks.ndim != 3 or landmarks.shape[1:] != (96, 258):
        raise ValueError(f"expected landmarks [N,96,258], got {list(landmarks.shape)}")
    if frame_mask.shape != landmarks.shape[:2]:
        raise ValueError("frame_mask shape does not match landmarks")
    if not (len(landmarks) == len(frame_mask) == len(y) == len(split_index) == len(lengths)):
        raise ValueError("dataset arrays are not aligned")
    return landmarks, frame_mask, y, split_index, lengths


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    landmarks, frame_mask, y, split_index, _ = _load_dataset(run_dir)
    train_rows = np.flatnonzero(split_index == 0)[: max(2, min(args.rows, 8))]
    val_rows = np.flatnonzero(split_index == 1)[: max(2, min(args.rows, 8))]
    if len(train_rows) < 2 or len(val_rows) < 2:
        raise ValueError("not enough rows for smoke test")
    summary = {
        "experiment": config["experiment"],
        "run_dir": str(run_dir.resolve()),
        "train_rows": int(len(train_rows)),
        "val_rows": int(len(val_rows)),
        "branches": {},
    }
    for branch in config["branches"]:
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(12345)
        model = _build_model(branch, (96, 258), int(config["class_count"]), float(config["learning_rate"]))
        probs = model.predict(_inputs_for(branch, landmarks[val_rows], frame_mask[val_rows]), batch_size=2, verbose=0)
        loss = model.train_on_batch(_inputs_for(branch, landmarks[train_rows], frame_mask[train_rows]), y[train_rows])
        weights_path = run_dir / "smoke" / f"{branch}.weights.h5"
        model.save_weights(weights_path)
        reloaded = _load_weights_model(branch, (96, 258), int(config["class_count"]), float(config["learning_rate"]), weights_path)
        reloaded_probs = reloaded.predict(_inputs_for(branch, landmarks[val_rows[:2]], frame_mask[val_rows[:2]]), batch_size=2, verbose=0)
        summary["branches"][branch] = {
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
    landmarks, frame_mask, y, split_index, _ = _load_dataset(run_dir)
    start = time.perf_counter()
    metrics: dict[str, Any] = {
        "experiment": config["experiment"],
        "run_dir": str(run_dir.resolve()),
        "input_shape": [96, 258],
        "class_count": int(config["class_count"]),
        "random_baseline": 1.0 / int(config["class_count"]),
        "split_counts": config["split_counts"],
        "branches": {},
        "elapsed_seconds": None,
        "passed": True,
    }
    train_mask = split_index == 0
    val_mask = split_index == 1

    for branch in config["branches"]:
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
            model = _build_model(branch, (96, 258), int(config["class_count"]), float(config["learning_rate"]))
            if args.resume and latest.exists():
                model.load_weights(latest)
                initial_epoch = int(epoch_file.read_text(encoding="utf-8"))
            else:
                initial_epoch = 0
            history = model.fit(
                _inputs_for(branch, landmarks[train_mask], frame_mask[train_mask]),
                y[train_mask],
                validation_data=(_inputs_for(branch, landmarks[val_mask], frame_mask[val_mask]), y[val_mask]),
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
                "latest": _evaluate(branch, model, landmarks, frame_mask, y, split_index, int(config["batch_size"]), config["classes"]),
                "best": _evaluate(
                    branch,
                    _load_weights_model(branch, (96, 258), int(config["class_count"]), float(config["learning_rate"]), best),
                    landmarks,
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


def _evaluate(
    branch: str,
    model: Any,
    landmarks: np.ndarray,
    frame_mask: np.ndarray,
    y: np.ndarray,
    split_index: np.ndarray,
    batch_size: int,
    classes: list[str],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    class_count = len(classes)
    for split_id, split_name in SPLITS.items():
        mask = split_index == split_name
        probs = model.predict(_inputs_for(branch, landmarks[mask], frame_mask[mask]), batch_size=batch_size, verbose=0)
        pred = np.argmax(probs, axis=1)
        truth = y[mask]
        confusion = np.zeros((class_count, class_count), dtype=np.int64)
        for true_id, pred_id in zip(truth.tolist(), pred.tolist(), strict=False):
            confusion[int(true_id), int(pred_id)] += 1
        predicted_counts = Counter(map(int, pred.tolist()))
        per_class = []
        for cid, name in enumerate(classes):
            total = int(np.sum(truth == cid))
            correct = int(confusion[cid, cid])
            per_class.append({"class_id": cid, "gloss": name, "count": total, "correct": correct, "accuracy": float(correct / total) if total else None})
        out[split_id] = {
            "accuracy": float(np.mean(pred == truth)),
            "mean_confidence": float(np.mean(np.max(probs, axis=1))),
            "count": int(len(truth)),
            "predicted_class_counts": {classes[cid]: int(count) for cid, count in sorted(predicted_counts.items())},
            "per_class": per_class,
            "confusion_matrix": confusion.tolist(),
        }
    return out


def _summarize(metrics: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"by_branch": {}, "winner_by_seed_best_val": {}, "decision_hint": {}}
    for branch, seeds in metrics["branches"].items():
        best_val = [result["best"]["val"]["accuracy"] for result in seeds.values()]
        best_test = [result["best"]["test"]["accuracy"] for result in seeds.values()]
        summary["by_branch"][branch] = {
            "mean_best_val": float(np.mean(best_val)),
            "std_best_val": float(np.std(best_val)),
            "mean_best_test": float(np.mean(best_test)),
            "std_best_test": float(np.std(best_test)),
            "seed_count": int(len(best_val)),
        }
    seed_ids = sorted({seed for branch in metrics["branches"].values() for seed in branch})
    for seed in seed_ids:
        candidates = {
            branch: result[seed]["best"]["val"]["accuracy"]
            for branch, result in metrics["branches"].items()
            if seed in result
        }
        if candidates:
            summary["winner_by_seed_best_val"][seed] = max(candidates, key=candidates.get)
    masked = summary["by_branch"].get("tcn_masked_pool")
    if masked:
        best_branch = max(summary["by_branch"], key=lambda b: summary["by_branch"][b]["mean_best_val"])
        wins = list(summary["winner_by_seed_best_val"].values()).count("tcn_masked_pool")
        summary["decision_hint"] = {
            "best_mean_validation_branch": best_branch,
            "masked_tcn_validation_wins": int(wins),
            "seed_count": int(len(seed_ids)),
            "promising": bool(best_branch == "tcn_masked_pool" and wins >= max(1, len(seed_ids) - 1)),
        }
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["pilot_config.json", "pilot_manifest.csv", "selected_classes.csv", "dataset/landmark_features.npz", "README_RUN.md"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    config: dict[str, Any] = {}
    config_path = run_dir / "pilot_config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        data = np.load(run_dir / "dataset" / "landmark_features.npz", allow_pickle=False)
        expected_rows = int(config["rows"])
        if int(data["landmarks"].shape[0]) != expected_rows:
            errors.append(f"dataset row count mismatch: {data['landmarks'].shape[0]} != {expected_rows}")
        if tuple(data["landmarks"].shape[1:]) != (96, 258):
            errors.append(f"dataset shape mismatch: {list(data['landmarks'].shape)}")
        if any(config.get("participant_overlap", {}).get(key) for key in ("train_val", "train_test", "val_test")):
            errors.append("participant overlap detected in prepared split")
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
            "# E3-B5 Landmark Temporal Scale Validation",
            "",
            "This is a larger signer-disjoint landmark-only experiment. It is not production training and does not modify Android.",
            "",
            "## Prepared Dataset",
            "",
            f"- Classes: {config['class_count']}",
            f"- Rows: {config['rows']}",
            f"- Split counts: {config['split_counts']}",
            f"- Per class: {config['per_class']}",
            f"- Input shape: {config['input_shape']}",
            f"- Branches: {', '.join(config['branches'])}",
            f"- Seeds: {', '.join(str(seed) for seed in config['seeds'])}",
            f"- Epochs per run command: {config['epochs']}",
            f"- Batch size: {config['batch_size']}",
            "",
            "## Smoke Test",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b5_landmark_temporal_scale smoke --run-dir "{run_dir}"',
            "```",
            "",
            "## Full Run",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b5_landmark_temporal_scale run --run-dir "{run_dir}"',
            "```",
            "",
            "## Resume",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b5_landmark_temporal_scale run --run-dir "{run_dir}" --resume',
            "```",
            "",
            "## Check",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b5_landmark_temporal_scale check --run-dir "{run_dir}" --require-metrics',
            "```",
            "",
        ]
    )


def _metrics_markdown(metrics: dict[str, Any]) -> str:
    lines = [
        "# E3-B5 Landmark Temporal Scale Metrics",
        "",
        "Signer-disjoint isolated-sign experiment only. Test accuracy is reporting-only after validation selection.",
        "",
        f"- Class count: {metrics['class_count']}",
        f"- Random baseline: {metrics['random_baseline']:.4f}",
        f"- Split counts: {metrics['split_counts']}",
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
    parser = argparse.ArgumentParser(description="E3-B5 larger landmark-temporal validation")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--features-dir", type=Path, default=DEFAULT_FEATURES_DIR)
    inspect_parser.add_argument("--vocab-path", type=Path, default=DEFAULT_VOCAB_PATH)
    inspect_parser.add_argument("--class-count", type=int, default=50)
    inspect_parser.add_argument("--train-per-class", type=int, default=16)
    inspect_parser.add_argument("--val-per-class", type=int, default=4)
    inspect_parser.add_argument("--test-per-class", type=int, default=4)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--features-dir", type=Path, default=DEFAULT_FEATURES_DIR)
    prepare_parser.add_argument("--vocab-path", type=Path, default=DEFAULT_VOCAB_PATH)
    prepare_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    prepare_parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    prepare_parser.add_argument("--class-count", type=int, default=50)
    prepare_parser.add_argument("--train-per-class", type=int, default=16)
    prepare_parser.add_argument("--val-per-class", type=int, default=4)
    prepare_parser.add_argument("--test-per-class", type=int, default=4)
    prepare_parser.add_argument("--seed", type=int, default=290729)
    prepare_parser.add_argument("--batch-size", type=int, default=8)
    prepare_parser.add_argument("--epochs", type=int, default=12)
    prepare_parser.add_argument("--learning-rate", type=float, default=5e-4)
    prepare_parser.add_argument("--branches", nargs="+", default=DEFAULT_BRANCHES)
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
        if args.command == "inspect":
            result = inspect(args)
        elif args.command == "prepare":
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
        print(f"[rgb/e3-b5] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
