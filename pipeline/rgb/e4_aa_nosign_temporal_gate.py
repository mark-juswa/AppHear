"""E4-AA expanded no-sign dataset + temporal signing gate.

Builds a larger real N0/P1 no-sign feature set with deterministic clip-level
train/validation/test splits, then compares a temporal binary gate against the
E4-S primary + E4-V GOOD/SORRY routed recognizer.

Experiment-only: no Android assets, TFLite exports, production recognizer files,
or source datasets are modified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.extract.config import load_config as load_extract_config
from pipeline.extract.landmarks import LandmarkExtractor
from pipeline.features.contract import SCHEMA_VERSION, clip_features_realtimed
from pipeline.normalize.config import load_config as load_normalize_config
from pipeline.rgb.e4_x_routed_system_validation import (
    FINAL_CLASSES,
    NO_SIGN_ID,
    POSITIVE_CLASSES,
    SPECIALIST_CLASSES,
    _apply_policy,
    _evaluate_policy,
    _load_json,
    _load_npz,
    _seed_predictions,
)
from pipeline.rgb.e4_y_real_nosign_feature_validation import _clip_video_map, _window_bounds
from pipeline.rgb.e4_z_signing_gate import _class_recall, _policy, _source_false_commit_rates, _summary_features

DEFAULT_PRIMARY_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01")
DEFAULT_SPECIALIST_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01")
DEFAULT_E4X_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_x_routed_system_validation_01")
DEFAULT_E4Y_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_y_real_nosign_feature_validation_01")
DEFAULT_N0_RUN = Path("artifacts/recognition_upgrade/e2e_c0/n0_capture_06")
DEFAULT_P1_RUN = Path("artifacts/recognition_upgrade/e2e_c0/p1_capture_03")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_01")
DEFAULT_EXTRACT_CONFIG = Path("pipeline/config/extract.yaml")
DEFAULT_NORMALIZE_CONFIG = Path("pipeline/config/normalize.yaml")
SPLITS = {"train": 0, "val": 1, "test": 2}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _stable_split(clip_id: str, seed: int, train_ratio: float, val_ratio: float) -> str:
    digest = hashlib.sha256(f"{seed}:{clip_id}".encode("utf-8")).hexdigest()
    value = int(digest[:12], 16) / float(0xFFFFFFFFFFFF)
    if value < train_ratio:
        return "train"
    if value < train_ratio + val_ratio:
        return "val"
    return "test"


def _eligible_rows(run_dir: Path, kind: str, max_rows: int, seed: int, train_ratio: float, val_ratio: float) -> list[dict[str, Any]]:
    rows = _read_csv(run_dir / "reviewed_manifest.csv")
    selected = []
    for row in rows:
        if row.get("eligible", "").lower() != "true" or row.get("kind") != kind:
            continue
        visible = int(row.get("visible_hand_count", "0") or 0)
        if kind == "n0" and visible != 0:
            continue
        if kind == "p1" and visible <= 0:
            continue
        item = dict(row)
        item["source_kind"] = kind.upper()
        item["split"] = _stable_split(item["clip_id"], seed, train_ratio, val_ratio)
        selected.append(item)
    rng = random.Random(seed + (17 if kind == "p1" else 0))
    rng.shuffle(selected)
    selected = selected[:max_rows]
    return sorted(selected, key=lambda row: (SPLITS[row["split"]], row["source_kind"], row["clip_id"], int(row["frame_index"])))


def _load_clip_cache(cache_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, float | int]]:
    cached = np.load(cache_path, allow_pickle=False)
    meta = {
        "native_fps": float(cached["native_fps"]),
        "n_frames": int(cached["n_frames"]),
        "frame_width": int(cached["frame_width"]),
        "frame_height": int(cached["frame_height"]),
    }
    return (
        cached["hands_image"].astype(np.float32),
        cached["pose_image"].astype(np.float32),
        cached["hand_score"].astype(np.float32),
        cached["pose_score"].astype(np.float32),
        meta,
    )


def _extract_nosign(
    rows: list[dict[str, Any]],
    video_by_clip: dict[str, Path],
    extractor: LandmarkExtractor,
    normalize_config: Any,
    window: int,
    cache_dir: Path,
    cache_sources: list[Path],
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    features = []
    frame_masks = []
    lengths = []
    manifest = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["clip_id"], []).append(row)
    for index, (clip_id, clip_rows) in enumerate(sorted(grouped.items()), start=1):
        cache_path = cache_dir / f"{clip_id}.npz"
        source_cache = next((path / f"{clip_id}.npz" for path in cache_sources if (path / f"{clip_id}.npz").exists()), None)
        if cache_path.exists():
            hands, pose, hand_score, pose_score, meta = _load_clip_cache(cache_path)
        elif source_cache is not None:
            hands, pose, hand_score, pose_score, meta = _load_clip_cache(source_cache)
            np.savez_compressed(
                cache_path,
                hands_image=hands,
                pose_image=pose,
                hand_score=hand_score,
                pose_score=pose_score,
                native_fps=float(meta["native_fps"]),
                n_frames=int(meta["n_frames"]),
                frame_width=int(meta["frame_width"]),
                frame_height=int(meta["frame_height"]),
            )
        else:
            video = video_by_clip.get(clip_id)
            if video is None:
                raise FileNotFoundError(f"missing video path for clip_id {clip_id}")
            print(f"[e4-aa] extract clip {index}/{len(grouped)} {clip_id}")
            clip, meta = extractor.extract(video)
            hands = clip.hands_image
            pose = clip.pose_image
            hand_score = clip.hand_score
            pose_score = clip.pose_score
            np.savez_compressed(
                cache_path,
                hands_image=hands,
                pose_image=pose,
                hand_score=hand_score,
                pose_score=pose_score,
                native_fps=float(meta["native_fps"]),
                n_frames=int(meta["n_frames"]),
                frame_width=int(meta["frame_width"]),
                frame_height=int(meta["frame_height"]),
            )
        for row in clip_rows:
            center = int(row["frame_index"])
            onset, release = _window_bounds(center, int(meta["n_frames"]), window)
            feature, frame_mask, length, _params = clip_features_realtimed(hands, pose, onset, release, normalize_config, window)
            hand_window = hand_score[onset : release + 1]
            pose_window = pose_score[onset : release + 1]
            features.append(feature.astype(np.float32))
            frame_masks.append(frame_mask.astype(bool))
            lengths.append(int(length))
            manifest.append({
                "sample_id": row["sample_id"],
                "source_kind": row["source_kind"],
                "split": row["split"],
                "clip_id": row["clip_id"],
                "participant_id": row.get("participant_id", ""),
                "device_id": row.get("device_id", ""),
                "environment_id": row.get("environment_id", ""),
                "camera_facing": row.get("camera_facing", ""),
                "timestamp_ms": row.get("timestamp_ms", ""),
                "frame_index": center,
                "window_onset": onset,
                "window_release": release,
                "length": int(length),
                "native_fps": float(meta["native_fps"]),
                "hand_hit_rate_window": float(np.mean(np.any(hand_window > 0.0, axis=1))) if hand_window.size else 0.0,
                "pose_hit_rate_window": float(np.mean(pose_window > 0.0)) if pose_window.size else 0.0,
            })
    dataset = {
        "landmarks": np.stack(features).astype(np.float32),
        "frame_mask": np.stack(frame_masks).astype(bool),
        "y": np.full(len(features), 0, dtype=np.int64),
        "split_index": np.asarray([SPLITS[row["split"]] for row in manifest], dtype=np.int64),
        "lengths": np.asarray(lengths, dtype=np.int32),
        "sample_ids": np.asarray([row["sample_id"] for row in manifest]).astype(str),
        "source": np.asarray([row["source_kind"] for row in manifest]).astype(str),
    }
    return dataset, manifest


def build_nosign_dataset(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    for relative in ("dataset/stage_e_cache", "logs"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    existing_features = output / "dataset" / "nosign_features.npz"
    existing_manifest = output / "dataset" / "nosign_manifest.csv"
    existing_summary = output / "logs" / "dataset_summary.json"
    if existing_features.exists() and existing_manifest.exists() and existing_summary.exists():
        return _load_json(existing_summary, "E4-AA dataset summary")
    rows = _eligible_rows(args.n0_run, "n0", int(args.max_n0), int(args.split_seed), float(args.train_ratio), float(args.val_ratio))
    rows.extend(_eligible_rows(args.p1_run, "p1", int(args.max_p1), int(args.split_seed), float(args.train_ratio), float(args.val_ratio)))
    if not rows:
        raise ValueError("no no-sign rows selected")
    extract_config = load_extract_config(args.extract_config)
    normalize_config = load_normalize_config(args.normalize_config)
    video_map = {**_clip_video_map(args.n0_run), **_clip_video_map(args.p1_run)}
    cache_sources = [args.e4y_run / "dataset" / "stage_e_cache"]
    with LandmarkExtractor(extract_config) as extractor:
        dataset, manifest = _extract_nosign(rows, video_map, extractor, normalize_config, int(args.window), output / "dataset" / "stage_e_cache", cache_sources)
    np.savez_compressed(output / "dataset" / "nosign_features.npz", **dataset)
    _write_csv(
        output / "dataset" / "nosign_manifest.csv",
        manifest,
        ["sample_id", "source_kind", "split", "clip_id", "participant_id", "device_id", "environment_id", "camera_facing", "timestamp_ms", "frame_index", "window_onset", "window_release", "length", "native_fps", "hand_hit_rate_window", "pose_hit_rate_window"],
    )
    summary = {
        "rows": int(dataset["landmarks"].shape[0]),
        "shape": [int(v) for v in dataset["landmarks"].shape],
        "split_counts": dict(sorted(Counter(row["split"] for row in manifest).items())),
        "source_counts": dict(sorted(Counter(row["source_kind"] for row in manifest).items())),
        "mean_hand_hit_rate_by_source": {
            kind: float(np.mean([float(row["hand_hit_rate_window"]) for row in manifest if row["source_kind"] == kind]))
            for kind in sorted({row["source_kind"] for row in manifest})
        },
        "mean_pose_hit_rate_by_source": {
            kind: float(np.mean([float(row["pose_hit_rate_window"]) for row in manifest if row["source_kind"] == kind]))
            for kind in sorted({row["source_kind"] for row in manifest})
        },
        "schema_version": SCHEMA_VERSION,
    }
    _write_json(output / "logs" / "dataset_summary.json", summary)
    return summary


def _combined_dataset(primary_run: Path, run_dir: Path) -> dict[str, np.ndarray]:
    active = _load_npz(primary_run / "dataset" / "landmark_features.npz", "E4-S active tensor")
    oov = _load_npz(primary_run / "dataset" / "oov_confusion_holdout.npz", "E4-S OOV holdout tensor")
    no_path = run_dir / "dataset" / "nosign_features.npz"
    nosign = _load_npz(no_path, "E4-AA no-sign tensor")
    raw = np.load(no_path, allow_pickle=False)
    source = np.concatenate([
        np.full(int(active["landmarks"].shape[0]), "e4_s_active"),
        np.full(int(oov["landmarks"].shape[0]), "e4_s_oov_sorry"),
        np.asarray(raw["source"]).astype(str),
    ]).astype(str)
    return {
        "landmarks": np.concatenate([active["landmarks"], oov["landmarks"], nosign["landmarks"]], axis=0).astype(np.float32),
        "frame_mask": np.concatenate([active["frame_mask"], oov["frame_mask"], nosign["frame_mask"]], axis=0).astype(bool),
        "y_final": np.concatenate([
            active["y"],
            np.full(int(oov["landmarks"].shape[0]), POSITIVE_CLASSES.index("SORRY"), dtype=np.int64),
            np.full(int(nosign["landmarks"].shape[0]), NO_SIGN_ID, dtype=np.int64),
        ]),
        "y_sign": np.concatenate([
            np.ones(int(active["landmarks"].shape[0]), dtype=np.int64),
            np.ones(int(oov["landmarks"].shape[0]), dtype=np.int64),
            np.zeros(int(nosign["landmarks"].shape[0]), dtype=np.int64),
        ]),
        "split_index": np.concatenate([active["split_index"], oov["split_index"], nosign["split_index"]]).astype(np.int64),
        "source": source,
        "sample_ids": np.concatenate([active["sample_ids"], oov["sample_ids"], nosign["sample_ids"]]).astype(str),
    }


def _build_temporal_gate(input_shape: tuple[int, int], lr: float):
    import tensorflow as tf

    inputs = tf.keras.Input(shape=input_shape, name="landmarks")
    x = tf.keras.layers.LayerNormalization()(inputs)
    x = tf.keras.layers.Conv1D(32, 5, padding="same", activation="relu")(x)
    x = tf.keras.layers.MaxPooling1D(2)(x)
    x = tf.keras.layers.Conv1D(48, 5, padding="same", activation="relu")(x)
    x = tf.keras.layers.GlobalAveragePooling1D()(x)
    x = tf.keras.layers.Dense(32, activation="relu")(x)
    x = tf.keras.layers.Dropout(0.20)(x)
    outputs = tf.keras.layers.Dense(1, activation="sigmoid")(x)
    model = tf.keras.Model(inputs, outputs, name="e4_aa_temporal_signing_gate")
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=lr), loss="binary_crossentropy", metrics=["accuracy"])
    return model


def _select_threshold(probs: np.ndarray, y_sign: np.ndarray, val_mask: np.ndarray, min_sign_recall: float, max_false_accept: float) -> tuple[float, list[dict[str, Any]]]:
    thresholds = np.unique(np.quantile(probs[val_mask], np.linspace(0.0, 1.0, 81)))
    rows = []
    for threshold in thresholds:
        accept = probs >= threshold
        pos = y_sign.astype(bool)
        val_accept = accept[val_mask]
        val_pos = pos[val_mask]
        val_neg = ~val_pos
        sign_recall = float(np.mean(val_accept[val_pos])) if np.any(val_pos) else 0.0
        no_sign_false_accept = float(np.mean(val_accept[val_neg])) if np.any(val_neg) else 0.0
        rows.append({
            "threshold": float(threshold),
            "sign_recall": sign_recall,
            "no_sign_false_accept_rate": no_sign_false_accept,
            "passes_gate": bool(sign_recall >= min_sign_recall and no_sign_false_accept <= max_false_accept),
        })
    ranked = sorted(rows, key=lambda row: (row["passes_gate"], -row["no_sign_false_accept_rate"], row["sign_recall"]), reverse=True)
    return float(ranked[0]["threshold"]), rows


def _apply_gate(routed_final: np.ndarray, probs: np.ndarray, threshold: float) -> np.ndarray:
    out = routed_final.copy()
    out[probs < threshold] = NO_SIGN_ID
    return out


def _evaluate_system(y_true: np.ndarray, pred: np.ndarray, source: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    metrics = _evaluate_policy(y_true[mask], pred[mask])
    metrics["no_sign_false_commit_by_source"] = _source_false_commit_rates(y_true[mask], pred[mask], source[mask])
    return metrics


def _source_false_commit_rates(y_true: np.ndarray, y_pred: np.ndarray, source: np.ndarray) -> dict[str, dict[str, Any]]:
    out = {}
    for kind in sorted(set(source.tolist())):
        mask = source == kind
        no_sign = mask & (y_true == NO_SIGN_ID)
        if not np.any(no_sign):
            continue
        accepted = y_pred[no_sign] != NO_SIGN_ID
        out[kind] = {
            "rows": int(np.sum(no_sign)),
            "false_commits": int(np.sum(accepted)),
            "false_commit_rate": float(np.mean(accepted)),
            "predicted_counts": dict(sorted(Counter(FINAL_CLASSES[int(v)] for v in y_pred[no_sign]).items())),
        }
    return out


def _class_recall(metrics: dict[str, Any], gloss: str) -> float:
    for row in metrics["per_class"]:
        if row["gloss"] == gloss:
            return 0.0 if row["recall"] is None else float(row["recall"])
    return 0.0


def train_and_eval(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    for relative in ("models", "metrics", "logs"):
        (run_dir / relative).mkdir(parents=True, exist_ok=True)
    data = _combined_dataset(args.primary_run, run_dir)
    x = data["landmarks"]
    y_sign = data["y_sign"]
    split = data["split_index"]
    train_mask = split == SPLITS["train"]
    val_mask = split == SPLITS["val"]
    test_mask = split == SPLITS["test"]
    primary_config = _load_json(args.primary_run / "pilot_config.json", "E4-S config")
    specialist_config = _load_json(args.specialist_run / "pilot_config.json", "E4-V config")
    policy = _policy(args.e4x_run)
    seed_results = {}
    threshold_grid = []
    start = time.perf_counter()
    for seed in [int(seed) for seed in args.seeds]:
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(seed)
        model = _build_temporal_gate(tuple(x.shape[1:]), float(args.learning_rate))
        neg = max(int(np.sum(y_sign[train_mask] == 0)), 1)
        pos = max(int(np.sum(y_sign[train_mask] == 1)), 1)
        class_weight = {0: float((pos + neg) / (2 * neg)), 1: float((pos + neg) / (2 * pos))}
        history = model.fit(
            x[train_mask],
            y_sign[train_mask],
            validation_data=(x[val_mask], y_sign[val_mask]),
            batch_size=int(args.batch_size),
            epochs=int(args.epochs),
            verbose=0,
            class_weight=class_weight,
        )
        probs = model.predict(x, batch_size=int(args.batch_size), verbose=0).reshape(-1)
        threshold, rows = _select_threshold(probs, y_sign, val_mask, float(args.gate_sign_recall_min), float(args.gate_no_sign_false_accept_max))
        for row in rows:
            threshold_grid.append({"seed": seed, **row})
        seed_dir = run_dir / "models" / f"seed_{seed}"
        seed_dir.mkdir(parents=True, exist_ok=True)
        model.save(seed_dir / "temporal_signing_gate.keras")
        routed_preds = _seed_predictions(seed, args.primary_run, args.specialist_run, primary_config, specialist_config, data)
        routed_final = _apply_policy(routed_preds, policy)
        final = _apply_gate(routed_final, probs, threshold)
        seed_results[str(seed)] = {
            "threshold": threshold,
            "validation": _evaluate_system(data["y_final"], final, data["source"], val_mask),
            "test": _evaluate_system(data["y_final"], final, data["source"], test_mask),
            "history_last": {k: float(v[-1]) for k, v in history.history.items()},
        }
    _write_csv(run_dir / "metrics" / "threshold_grid.csv", threshold_grid, ["seed", "threshold", "sign_recall", "no_sign_false_accept_rate", "passes_gate"])
    tests = [payload["test"] for payload in seed_results.values()]
    summary = {
        "mean_test_accepted_precision": float(np.mean([m["accepted_precision"] for m in tests])),
        "min_test_accepted_precision": float(np.min([m["accepted_precision"] for m in tests])),
        "mean_test_positive_coverage": float(np.mean([m["positive_coverage"] for m in tests])),
        "min_test_positive_coverage": float(np.min([m["positive_coverage"] for m in tests])),
        "max_test_no_sign_false_commit_rate": float(np.max([m["no_sign_false_commit_rate"] for m in tests])),
        "mean_test_good_recall": float(np.mean([_class_recall(m, "GOOD") for m in tests])),
        "min_test_good_recall": float(np.min([_class_recall(m, "GOOD") for m in tests])),
        "mean_test_sorry_recall": float(np.mean([_class_recall(m, "SORRY") for m in tests])),
        "min_test_sorry_recall": float(np.min([_class_recall(m, "SORRY") for m in tests])),
    }
    gate = {
        "accepted_precision_min": float(args.accepted_precision_min),
        "positive_coverage_min": float(args.positive_coverage_min),
        "no_sign_false_commit_rate_max": float(args.no_sign_false_commit_rate_max),
        "good_recall_min": float(args.good_recall_min),
        "sorry_recall_min": float(args.sorry_recall_min),
    }
    passed = bool(
        summary["min_test_accepted_precision"] >= gate["accepted_precision_min"]
        and summary["min_test_positive_coverage"] >= gate["positive_coverage_min"]
        and summary["max_test_no_sign_false_commit_rate"] <= gate["no_sign_false_commit_rate_max"]
        and summary["min_test_good_recall"] >= gate["good_recall_min"]
        and summary["min_test_sorry_recall"] >= gate["sorry_recall_min"]
    )
    result = {
        "experiment": "e4_aa_nosign_temporal_gate_v1",
        "run_dir": str(run_dir.resolve()),
        "primary_run": str(args.primary_run.resolve()),
        "specialist_run": str(args.specialist_run.resolve()),
        "e4x_run": str(args.e4x_run.resolve()),
        "dataset_summary": _load_json(run_dir / "logs" / "dataset_summary.json", "dataset summary") if (run_dir / "logs" / "dataset_summary.json").exists() else {},
        "gate": gate,
        "seed_results": seed_results,
        "summary": summary,
        "elapsed_seconds": time.perf_counter() - start,
        "passed": passed,
        "decision": "temporal_signing_gate_candidate_ready_for_larger_validation" if passed else "temporal_signing_gate_no_go_or_needs_more_data",
        "warnings": [
            "Offline experiment only; no Android/export authorized.",
            "If run with smoke-sized N0/P1 counts, this is not a production-quality gate.",
            "Gate must preserve low-motion signs such as SORRY before promotion.",
        ],
    }
    _write_json(run_dir / "metrics" / "temporal_gate_metrics.json", result)
    _write_json(run_dir / "logs" / "run_summary.json", {"passed": passed, "summary": summary})
    return result


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.train_only:
        dataset_summary = _load_json(args.output / "logs" / "dataset_summary.json", "E4-AA dataset summary")
    else:
        dataset_summary = build_nosign_dataset(args)
    if args.prepare_only:
        return {
            "experiment": "e4_aa_nosign_temporal_gate_v1",
            "run_dir": str(args.output.resolve()),
            "prepared_only": True,
            "nosign_dataset": dataset_summary,
            "warning": "Dataset prepared only; run again with --train-only to train/evaluate the temporal gate.",
        }
    train_args = argparse.Namespace(**vars(args))
    train_args.run_dir = args.output
    result = train_and_eval(train_args)
    result["nosign_dataset"] = dataset_summary
    _write_json(args.output / "metrics" / "temporal_gate_metrics.json", result)
    return result


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["dataset/nosign_features.npz", "dataset/nosign_manifest.csv", "metrics/temporal_gate_metrics.json", "metrics/threshold_grid.csv", "logs/run_summary.json"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if args.require_metrics and (run_dir / "metrics" / "temporal_gate_metrics.json").exists():
        metrics = json.loads((run_dir / "metrics" / "temporal_gate_metrics.json").read_text(encoding="utf-8"))
        if metrics.get("experiment") != "e4_aa_nosign_temporal_gate_v1":
            errors.append("unexpected experiment id")
        if not isinstance(metrics.get("passed"), bool):
            errors.append("metrics missing boolean passed field")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-AA no-sign temporal signing gate")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--primary-run", type=Path, default=DEFAULT_PRIMARY_RUN)
    run_parser.add_argument("--specialist-run", type=Path, default=DEFAULT_SPECIALIST_RUN)
    run_parser.add_argument("--e4x-run", type=Path, default=DEFAULT_E4X_RUN)
    run_parser.add_argument("--e4y-run", type=Path, default=DEFAULT_E4Y_RUN)
    run_parser.add_argument("--n0-run", type=Path, default=DEFAULT_N0_RUN)
    run_parser.add_argument("--p1-run", type=Path, default=DEFAULT_P1_RUN)
    run_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_parser.add_argument("--extract-config", type=Path, default=DEFAULT_EXTRACT_CONFIG)
    run_parser.add_argument("--normalize-config", type=Path, default=DEFAULT_NORMALIZE_CONFIG)
    run_parser.add_argument("--max-n0", type=int, default=180)
    run_parser.add_argument("--max-p1", type=int, default=108)
    run_parser.add_argument("--window", type=int, default=96)
    run_parser.add_argument("--split-seed", type=int, default=280802)
    run_parser.add_argument("--train-ratio", type=float, default=0.60)
    run_parser.add_argument("--val-ratio", type=float, default=0.20)
    run_parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    run_parser.add_argument("--epochs", type=int, default=30)
    run_parser.add_argument("--batch-size", type=int, default=16)
    run_parser.add_argument("--learning-rate", type=float, default=8e-4)
    run_parser.add_argument("--gate-sign-recall-min", type=float, default=0.90)
    run_parser.add_argument("--gate-no-sign-false-accept-max", type=float, default=0.10)
    run_parser.add_argument("--accepted-precision-min", type=float, default=0.95)
    run_parser.add_argument("--positive-coverage-min", type=float, default=0.80)
    run_parser.add_argument("--no-sign-false-commit-rate-max", type=float, default=0.10)
    run_parser.add_argument("--good-recall-min", type=float, default=0.90)
    run_parser.add_argument("--sorry-recall-min", type=float, default=0.90)
    run_parser.add_argument("--prepare-only", action="store_true")
    run_parser.add_argument("--train-only", action="store_true")

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--require-metrics", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-aa] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

