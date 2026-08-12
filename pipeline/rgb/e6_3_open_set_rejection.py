"""E6-3 frozen-embedding open-set rejection experiment.

This package never trains or modifies the five-sign classifier. It extracts
negative v3.0 windows, measures frozen TCN embeddings, and compares MSP,
energy, and predicted-class shrinkage-Mahalanobis rejection.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from pipeline.extract.config import load_config as load_extract_config
from pipeline.extract.landmarks import LandmarkExtractor
from pipeline.features.contract import FEATURE_DIM, clip_features_realtimed
from pipeline.normalize.config import load_config as load_normalize_config
from pipeline.rgb.e6_v30_five_sign_baseline import CLASSES, SEEDS

EXPERIMENT = "e6_3_frozen_embedding_rejection_v1"
DEFAULT_ASSIGNMENT = Path(
    "artifacts/recognition_upgrade/product_core_data_readiness/"
    "e6_five_sign_assignment_01/assignment_manifest.csv"
)
DEFAULT_REPAIRED = Path(
    "artifacts/recognition_upgrade/e6_baseline/e6_v30_validation_repair_01"
)
DEFAULT_CONTROL = Path(
    "artifacts/recognition_upgrade/e6_baseline/"
    "e6_v30_five_sign_transfer_repaired_val_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e6_rejection/e6_3_frozen_embedding_01"
)
DEFAULT_EXTRACT_CONFIG = Path("pipeline/config/extract.yaml")
DEFAULT_NORMALIZE_CONFIG = Path("pipeline/config/normalize.yaml")
POSITIVE_SPLITS = (
    "train",
    "val",
    "validation_variant_stress",
    "test_fresh",
    "test_historical",
)
DEV_NEGATIVE_ROLE = "development_negative"
FRESH_NEGATIVE_ROLE = "test_negative_fresh_provisional"
METHODS = ("msp", "energy", "mahalanobis")
GATES = {
    "development_accepted_precision_min": 0.95,
    "development_positive_coverage_min": 0.80,
    "development_nosign_far_max": 0.02,
    "development_oov_far_max": 0.05,
    "development_min_class_accepted_recall_min": 0.70,
    "fresh_mean_accepted_precision_min": 0.95,
    "fresh_min_accepted_precision_min": 0.93,
    "fresh_mean_positive_coverage_min": 0.80,
    "fresh_min_positive_coverage_min": 0.75,
    "fresh_stable_mean_accepted_recall_min": 0.85,
    "fresh_stable_min_accepted_recall_min": 0.75,
    "fresh_know_mean_accepted_recall_min": 0.50,
    "fresh_know_min_accepted_recall_min": 0.40,
    "fresh_oov_far_max": 0.05,
    "fresh_nonoov_subtype_far_max": 0.02,
    "stress_know_to_hello_reduction_min": 0.70,
    "stress_correct_know_retention_min": 0.30,
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _window_bounds(center: int, n_frames: int, window: int = 96) -> tuple[int, int]:
    if n_frames <= 0:
        raise ValueError("video has no frames")
    half = window // 2
    onset = max(0, center - half)
    release = min(n_frames - 1, onset + window - 1)
    onset = max(0, release - window + 1)
    return onset, release


def _load_positive(root: Path, split: str) -> dict[str, np.ndarray]:
    path = root / "dataset" / "features" / f"{split}.npz"
    if not path.exists():
        raise FileNotFoundError(path)
    with np.load(path, allow_pickle=False) as data:
        required = {"X", "frame_mask", "lengths", "y", "sample_ids"}
        missing = required.difference(data.files)
        if missing:
            raise ValueError(f"{path} missing keys: {sorted(missing)}")
        result = {key: data[key] for key in data.files}
    if tuple(result["X"].shape[1:]) != (96, FEATURE_DIM):
        raise ValueError(f"{split}: expected [N,96,{FEATURE_DIM}], got {result['X'].shape}")
    return result


def _negative_rows(assignment: Path) -> list[dict[str, str]]:
    rows = [row for row in _read_csv(assignment) if row.get("sample_kind") == "negative_context"]
    for row in rows:
        if row.get("role") not in {DEV_NEGATIVE_ROLE, FRESH_NEGATIVE_ROLE}:
            raise ValueError(f"unexpected negative role: {row.get('role')}")
        video = Path(row["raw_video_path"])
        if not video.exists():
            raise FileNotFoundError(video)
        expected = row.get("raw_video_sha256", "").upper()
        if not expected:
            raise ValueError(f"{row['assignment_id']}: missing raw video hash")
    return rows


def _cache_path(cache_root: Path, video: Path) -> Path:
    token = hashlib.sha256(str(video.resolve()).lower().encode("utf-8")).hexdigest()[:24]
    return cache_root / f"{token}.npz"


def _load_stage_e(path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    with np.load(path, allow_pickle=False) as data:
        hands = data["hands_image"].astype(np.float32)
        pose = data["pose_image"].astype(np.float32)
        meta = {
            "native_fps": float(data["native_fps"]),
            "n_frames": int(data["n_frames"]),
        }
    return hands, pose, meta


def _save_stage_e(path: Path, clip: Any, meta: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        hands_image=clip.hands_image.astype(np.float32),
        pose_image=clip.pose_image.astype(np.float32),
        native_fps=float(meta["native_fps"]),
        n_frames=int(meta["n_frames"]),
    )


def _extract_negative_rows(
    rows: list[dict[str, str]],
    output: Path,
    extract_config: Path,
    normalize_config: Path,
) -> dict[str, Any]:
    cache_root = output / "dataset" / "stage_e_cache"
    feature_root = output / "dataset" / "per_window"
    cache_root.mkdir(parents=True, exist_ok=True)
    feature_root.mkdir(parents=True, exist_ok=True)
    extract_cfg = load_extract_config(extract_config)
    normalize_cfg = load_normalize_config(normalize_config)
    by_video: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_video.setdefault(row["raw_video_path"], []).append(row)
    attempted = 0
    cached = 0
    extracted = 0
    errors: list[str] = []
    manifest: list[dict[str, Any]] = []
    started = time.perf_counter()
    with LandmarkExtractor(extract_cfg) as extractor:
        for video_index, (video_text, video_rows) in enumerate(sorted(by_video.items()), start=1):
            video = Path(video_text)
            stage_path = _cache_path(cache_root, video)
            try:
                if stage_path.exists():
                    hands, pose, meta = _load_stage_e(stage_path)
                    cached += 1
                else:
                    print(f"[e6-3/extract] video {video_index}/{len(by_video)} {video.name}")
                    clip, meta = extractor.extract(video)
                    if int(meta["n_frames"]) <= 0:
                        raise ValueError("no frames extracted")
                    _save_stage_e(stage_path, clip, meta)
                    hands = clip.hands_image.astype(np.float32)
                    pose = clip.pose_image.astype(np.float32)
                    extracted += 1
                for row in video_rows:
                    attempted += 1
                    window_path = feature_root / f"{row['assignment_id'].replace(':', '_')}.npz"
                    if window_path.exists():
                        with np.load(window_path, allow_pickle=False) as data:
                            feature = data["X"]
                            frame_mask = data["frame_mask"]
                            length = int(data["length"])
                            onset = int(data["window_onset"])
                            release = int(data["window_release"])
                    else:
                        frame_text = row.get("frame_index", "").strip()
                        if frame_text:
                            onset, release = _window_bounds(int(float(frame_text)), int(meta["n_frames"]))
                        else:
                            onset, release = 0, int(meta["n_frames"]) - 1
                        feature, frame_mask, length, _ = clip_features_realtimed(
                            hands, pose, onset, release, normalize_cfg, 96
                        )
                        np.savez_compressed(
                            window_path,
                            X=feature.astype(np.float32),
                            frame_mask=frame_mask.astype(bool),
                            length=np.int32(length),
                            window_onset=np.int32(onset),
                            window_release=np.int32(release),
                        )
                    if feature.shape != (96, FEATURE_DIM) or frame_mask.shape != (96,):
                        raise ValueError(f"invalid window shape for {row['assignment_id']}")
                    manifest.append(
                        {
                            "assignment_id": row["assignment_id"],
                            "role": row["role"],
                            "negative_subtype": row["negative_subtype"],
                            "source_dataset": row["source_dataset"],
                            "signer_group_id": row["signer_group_id"],
                            "raw_video_path": str(video.resolve()),
                            "raw_video_sha256": row["raw_video_sha256"],
                            "frame_index": row.get("frame_index", ""),
                            "timestamp_ms": row.get("timestamp_ms", ""),
                            "window_onset": onset,
                            "window_release": release,
                            "length": length,
                            "feature_path": str(window_path.resolve()),
                        }
                    )
            except Exception as exc:  # preserve all failures in one report
                errors.append(f"{video}: {type(exc).__name__}: {exc}")
    fields = [
        "assignment_id", "role", "negative_subtype", "source_dataset", "signer_group_id",
        "raw_video_path", "raw_video_sha256", "frame_index", "timestamp_ms", "window_onset",
        "window_release", "length", "feature_path",
    ]
    _write_csv(output / "dataset" / "negative_window_manifest.csv", manifest, fields)
    summary = {
        "attempted_windows": attempted,
        "completed_windows": len(manifest),
        "unique_videos": len(by_video),
        "stage_e_cached_videos": cached,
        "stage_e_extracted_videos": extracted,
        "role_counts": dict(sorted(Counter(row["role"] for row in manifest).items())),
        "subtype_counts": dict(sorted(Counter(row["negative_subtype"] for row in manifest).items())),
        "elapsed_seconds": time.perf_counter() - started,
        "errors": errors,
        "passed": not errors and len(manifest) == len(rows),
    }
    _write_json(output / "logs" / "negative_extraction_summary.json", summary)
    return summary


def _load_negative_features(output: Path) -> dict[str, Any]:
    manifest_path = output / "dataset" / "negative_window_manifest.csv"
    if not manifest_path.exists():
        raise FileNotFoundError("run extract-negatives before evaluate")
    rows = _read_csv(manifest_path)
    xs, masks, lengths = [], [], []
    for row in rows:
        with np.load(row["feature_path"], allow_pickle=False) as data:
            xs.append(data["X"].astype(np.float32))
            masks.append(data["frame_mask"].astype(bool))
            lengths.append(int(data["length"]))
    return {
        "X": np.stack(xs),
        "frame_mask": np.stack(masks),
        "lengths": np.asarray(lengths, dtype=np.int32),
        "rows": rows,
    }


def _masked_mean(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    weights = mask.astype(np.float64)[..., None]
    denominator = np.maximum(weights.sum(axis=1), 1.0)
    return (values.astype(np.float64) * weights).sum(axis=1) / denominator


def _model_outputs(model_path: Path, data: dict[str, np.ndarray], batch_size: int = 64) -> dict[str, np.ndarray]:
    import tensorflow as tf

    model = tf.keras.models.load_model(model_path, compile=False)
    if tuple(model.input_shape) != (None, 96, FEATURE_DIM) or tuple(model.output_shape) != (None, 96, len(CLASSES)):
        raise ValueError(f"frozen model contract mismatch: {model.input_shape}->{model.output_shape}")
    encoder_layer = model.get_layer("tcn3_add")
    if tuple(encoder_layer.output.shape[1:]) != (96, 64):
        raise ValueError(f"unexpected embedding shape: {encoder_layer.output.shape}")
    embedding_model = tf.keras.Model(model.input, encoder_layer.output)
    x = data["X"].astype(np.float32)
    mask = data["frame_mask"].astype(bool)
    per_frame_embeddings = embedding_model.predict(x, batch_size=batch_size, verbose=0)
    per_frame_probs = model.predict(x, batch_size=batch_size, verbose=0)
    dense = model.get_layer("logits_perframe")
    kernel, bias = dense.get_weights()
    per_frame_logits = np.einsum("ntd,dc->ntc", per_frame_embeddings, kernel) + bias
    clip_embeddings = _masked_mean(per_frame_embeddings, mask)
    clip_probs = _masked_mean(per_frame_probs, mask)
    predictions = np.argmax(clip_probs, axis=1).astype(np.int64)
    msp = np.max(clip_probs, axis=1)
    max_logits = np.max(per_frame_logits, axis=-1, keepdims=True)
    logsumexp = np.squeeze(max_logits, axis=-1) + np.log(
        np.sum(np.exp(per_frame_logits - max_logits), axis=-1)
    )
    energy_known_score = _masked_mean(logsumexp[..., None], mask)[:, 0]
    return {
        "embedding": clip_embeddings.astype(np.float64),
        "probabilities": clip_probs.astype(np.float64),
        "prediction": predictions,
        "msp": msp.astype(np.float64),
        "energy": energy_known_score.astype(np.float64),
    }


def _fit_oas_mahalanobis(embeddings: np.ndarray, labels: np.ndarray) -> dict[str, np.ndarray | float]:
    means = np.stack([embeddings[labels == class_id].mean(axis=0) for class_id in range(len(CLASSES))])
    residuals = embeddings - means[labels]
    empirical = residuals.T @ residuals / float(len(residuals))
    n_features = empirical.shape[0]
    mu = float(np.trace(empirical) / n_features)
    alpha = float(np.mean(empirical**2))
    denominator = (len(residuals) + 1.0) * (alpha - (mu * mu) / n_features)
    shrinkage = 1.0 if denominator <= 0.0 else min((alpha + mu * mu) / denominator, 1.0)
    covariance = (1.0 - shrinkage) * empirical
    covariance.flat[:: n_features + 1] += shrinkage * mu
    covariance.flat[:: n_features + 1] += 1e-8
    inverse = np.linalg.pinv(covariance, hermitian=True)
    return {"means": means, "inverse_covariance": inverse, "shrinkage": shrinkage}


def _mahalanobis_score(outputs: dict[str, np.ndarray], fit: dict[str, Any]) -> np.ndarray:
    predicted = outputs["prediction"]
    delta = outputs["embedding"] - fit["means"][predicted]
    distance = np.einsum("ni,ij,nj->n", delta, fit["inverse_covariance"], delta)
    return -distance


def _binary_auc(labels: np.ndarray, scores: np.ndarray) -> float:
    positives = scores[labels == 1]
    negatives = scores[labels == 0]
    if len(positives) == 0 or len(negatives) == 0:
        return float("nan")
    combined = np.concatenate([positives, negatives])
    order = np.argsort(combined, kind="mergesort")
    ranks = np.empty(len(combined), dtype=np.float64)
    ranks[order] = np.arange(1, len(combined) + 1, dtype=np.float64)
    _, inverse, counts = np.unique(combined, return_inverse=True, return_counts=True)
    for group, count in enumerate(counts):
        if count > 1:
            indices = np.flatnonzero(inverse == group)
            ranks[indices] = ranks[indices].mean()
    rank_sum = ranks[: len(positives)].sum()
    return float((rank_sum - len(positives) * (len(positives) + 1) / 2) / (len(positives) * len(negatives)))


def _operating_metrics(
    positive_outputs: dict[str, np.ndarray],
    positive_labels: np.ndarray,
    positive_scores: np.ndarray,
    negative_outputs: dict[str, np.ndarray],
    negative_scores: np.ndarray,
    negative_rows: list[dict[str, str]],
    threshold: float,
) -> dict[str, Any]:
    positive_accept = positive_scores >= threshold
    negative_accept = negative_scores >= threshold
    positive_correct = positive_outputs["prediction"] == positive_labels
    correct_accepted = int(np.sum(positive_accept & positive_correct))
    all_accepted = int(np.sum(positive_accept) + np.sum(negative_accept))
    per_class = {}
    for class_id, label in enumerate(CLASSES):
        class_mask = positive_labels == class_id
        per_class[label] = {
            "count": int(np.sum(class_mask)),
            "accepted_recall": float(np.mean(positive_accept[class_mask] & positive_correct[class_mask]))
            if np.any(class_mask) else float("nan"),
            "coverage": float(np.mean(positive_accept[class_mask])) if np.any(class_mask) else float("nan"),
        }
    subtype_far = {}
    subtypes = np.asarray([row["negative_subtype"] for row in negative_rows])
    for subtype in sorted(set(subtypes.tolist())):
        mask = subtypes == subtype
        subtype_far[subtype] = float(np.mean(negative_accept[mask]))
    return {
        "threshold": float(threshold),
        "accepted_precision": float(correct_accepted / all_accepted) if all_accepted else 1.0,
        "positive_coverage": float(np.mean(positive_accept)),
        "positive_accuracy_before_rejection": float(np.mean(positive_correct)),
        "negative_false_accept_rate": float(np.mean(negative_accept)),
        "negative_subtype_false_accept_rate": subtype_far,
        "per_class": per_class,
        "minimum_class_accepted_recall": float(min(item["accepted_recall"] for item in per_class.values())),
        "accepted_positive_count": int(np.sum(positive_accept)),
        "accepted_negative_count": int(np.sum(negative_accept)),
    }


def _valid_development(metrics: dict[str, Any]) -> bool:
    subtype = metrics["negative_subtype_false_accept_rate"]
    no_sign_values = [value for name, value in subtype.items() if name != "OOV_SIGN"]
    return bool(
        metrics["accepted_precision"] >= GATES["development_accepted_precision_min"]
        and metrics["positive_coverage"] >= GATES["development_positive_coverage_min"]
        and max(no_sign_values, default=0.0) <= GATES["development_nosign_far_max"]
        and subtype.get("OOV_SIGN", 0.0) <= GATES["development_oov_far_max"]
        and metrics["minimum_class_accepted_recall"]
        >= GATES["development_min_class_accepted_recall_min"]
    )


def _development_diagnostics(
    positive_outputs: dict[str, np.ndarray],
    labels: np.ndarray,
    positive_scores: np.ndarray,
    negative_outputs: dict[str, np.ndarray],
    negative_scores: np.ndarray,
    negative_rows: list[dict[str, str]],
) -> dict[str, Any]:
    candidates = np.unique(np.concatenate([positive_scores, negative_scores]))
    candidates = np.concatenate([[np.inf], candidates[::-1], [-np.inf]])
    rows = []
    for threshold in candidates:
        metrics = _operating_metrics(
            positive_outputs, labels, positive_scores, negative_outputs, negative_scores,
            negative_rows, float(threshold),
        )
        subtype = metrics["negative_subtype_false_accept_rate"]
        metrics["worst_nonoov_false_accept_rate"] = max(
            (value for name, value in subtype.items() if name != "OOV_SIGN"), default=0.0
        )
        metrics["oov_false_accept_rate"] = subtype.get("OOV_SIGN", 0.0)
        rows.append(metrics)

    def choose(predicate: Any, rank: Any) -> dict[str, Any] | None:
        eligible = [item for item in rows if predicate(item)]
        return max(eligible, key=rank) if eligible else None

    return {
        "best_precision_at_coverage_floor": choose(
            lambda item: item["positive_coverage"] >= GATES["development_positive_coverage_min"],
            lambda item: (
                item["accepted_precision"],
                -item["worst_nonoov_false_accept_rate"],
                -item["oov_false_accept_rate"],
            ),
        ),
        "best_coverage_at_precision_floor": choose(
            lambda item: item["accepted_precision"] >= GATES["development_accepted_precision_min"],
            lambda item: (item["positive_coverage"], item["minimum_class_accepted_recall"]),
        ),
        "best_coverage_at_negative_far_floors": choose(
            lambda item: (
                item["worst_nonoov_false_accept_rate"] <= GATES["development_nosign_far_max"]
                and item["oov_false_accept_rate"] <= GATES["development_oov_far_max"]
            ),
            lambda item: (item["positive_coverage"], item["accepted_precision"]),
        ),
        "best_min_class_recall_at_safety_floors": choose(
            lambda item: (
                item["accepted_precision"] >= GATES["development_accepted_precision_min"]
                and item["worst_nonoov_false_accept_rate"] <= GATES["development_nosign_far_max"]
                and item["oov_false_accept_rate"] <= GATES["development_oov_far_max"]
            ),
            lambda item: (item["minimum_class_accepted_recall"], item["positive_coverage"]),
        ),
    }


def _select_threshold(
    positive_outputs: dict[str, np.ndarray],
    labels: np.ndarray,
    positive_scores: np.ndarray,
    negative_outputs: dict[str, np.ndarray],
    negative_scores: np.ndarray,
    negative_rows: list[dict[str, str]],
) -> tuple[float | None, dict[str, Any] | None]:
    candidates = np.unique(np.concatenate([positive_scores, negative_scores]))
    candidates = np.concatenate([[np.inf], candidates[::-1], [-np.inf]])
    best: tuple[tuple[float, float], float, dict[str, Any]] | None = None
    for threshold in candidates:
        metrics = _operating_metrics(
            positive_outputs, labels, positive_scores, negative_outputs, negative_scores,
            negative_rows, float(threshold),
        )
        if not _valid_development(metrics):
            continue
        rank = (metrics["positive_coverage"], metrics["accepted_precision"])
        if best is None or rank > best[0]:
            best = (rank, float(threshold), metrics)
    return (None, None) if best is None else (best[1], best[2])


def prepare(args: argparse.Namespace) -> int:
    output = args.output.resolve()
    assignment = args.assignment.resolve()
    repaired = args.repaired.resolve()
    control = args.control.resolve()
    rows = _negative_rows(assignment)
    for split in POSITIVE_SPLITS:
        _load_positive(repaired, split)
    checkpoints = {}
    for seed in SEEDS:
        path = control / "models" / f"seed_{seed}" / "latest.keras"
        if not path.exists():
            raise FileNotFoundError(path)
        checkpoints[str(seed)] = {"path": str(path.resolve()), "sha256": _sha256(path)}
    for relative in ("config", "dataset", "logs", "metrics", "predictions", "smoke"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    config = {
        "experiment": EXPERIMENT,
        "assignment": str(assignment),
        "assignment_sha256": _sha256(assignment),
        "repaired_positive_root": str(repaired),
        "control_root": str(control),
        "classes": CLASSES,
        "seeds": SEEDS,
        "embedding_layer": "tcn3_add",
        "embedding_dim": 64,
        "methods": METHODS,
        "gates": GATES,
        "negative_rows": len(rows),
        "negative_role_counts": dict(sorted(Counter(row["role"] for row in rows).items())),
        "negative_subtype_counts": dict(sorted(Counter(row["negative_subtype"] for row in rows).items())),
        "checkpoints": checkpoints,
        "extract_config": str(args.extract_config.resolve()),
        "normalize_config": str(args.normalize_config.resolve()),
        "no_android_or_training": True,
    }
    _write_json(output / "config" / "experiment.json", config)
    runbook = f"""# E6-3 Frozen-Embedding Rejection Run\n\nNo model training or Android change occurs.\n\n```powershell\ncd \"F:\\ASL DATASET\\5. Apphear3\"\n.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e6_3_open_set_rejection smoke --run-dir \"{output}\"\n.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e6_3_open_set_rejection extract-negatives --run-dir \"{output}\"\n.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e6_3_open_set_rejection evaluate --run-dir \"{output}\"\n.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e6_3_open_set_rejection check --run-dir \"{output}\" --require-smoke --require-metrics\n```\n\n`extract-negatives` is the long step and is resumable through per-video/per-window caches.\n"""
    (output / "RUNBOOK.md").write_text(runbook, encoding="utf-8")
    print(json.dumps(config, indent=2))
    return 0


def extract_negatives(args: argparse.Namespace) -> int:
    output = args.run_dir.resolve()
    config = json.loads((output / "config" / "experiment.json").read_text(encoding="utf-8"))
    rows = _negative_rows(Path(config["assignment"]))
    summary = _extract_negative_rows(
        rows, output, Path(config["extract_config"]), Path(config["normalize_config"])
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 2


def smoke(args: argparse.Namespace) -> int:
    output = args.run_dir.resolve()
    config = json.loads((output / "config" / "experiment.json").read_text(encoding="utf-8"))
    all_rows = _negative_rows(Path(config["assignment"]))
    chosen = []
    for role in (DEV_NEGATIVE_ROLE, FRESH_NEGATIVE_ROLE):
        for subtype in sorted({row["negative_subtype"] for row in all_rows if row["role"] == role}):
            chosen.append(next(row for row in all_rows if row["role"] == role and row["negative_subtype"] == subtype))
    smoke_root = output / "smoke" / "negative_extract"
    summary = _extract_negative_rows(
        chosen, smoke_root, Path(config["extract_config"]), Path(config["normalize_config"])
    )
    train = _load_positive(Path(config["repaired_positive_root"]), "train")
    selected = np.concatenate(
        [np.flatnonzero(train["y"] == class_id)[:4] for class_id in range(len(CLASSES))]
    )
    small = {
        key: value[selected]
        for key, value in train.items()
        if isinstance(value, np.ndarray) and len(value) == len(train["y"])
    }
    model_path = Path(config["checkpoints"][str(SEEDS[0])]["path"])
    outputs = _model_outputs(model_path, small, batch_size=16)
    fit = _fit_oas_mahalanobis(outputs["embedding"], small["y"].astype(np.int64))
    scores = _mahalanobis_score(outputs, fit)
    smoke_summary = {
        "experiment": EXPERIMENT,
        "negative_extract": summary,
        "model_path": str(model_path),
        "model_sha256": _sha256(model_path),
        "embedding_shape": list(outputs["embedding"].shape),
        "probability_shape": list(outputs["probabilities"].shape),
        "probability_rows_sum_to_one": bool(np.allclose(outputs["probabilities"].sum(axis=1), 1.0, atol=1e-5)),
        "mahalanobis_finite": bool(np.isfinite(scores).all()),
        "oas_shrinkage": float(fit["shrinkage"]),
        "serialized_parameter_bytes_float32": int(
            fit["means"].astype(np.float32).nbytes
            + fit["inverse_covariance"].astype(np.float32).nbytes
        ),
        "passed": bool(summary["passed"] and outputs["embedding"].shape[1] == 64 and np.isfinite(scores).all()),
    }
    _write_json(output / "smoke" / "smoke_summary.json", smoke_summary)
    print(json.dumps(smoke_summary, indent=2))
    return 0 if smoke_summary["passed"] else 2


def _subset_negative(data: dict[str, Any], role: str) -> dict[str, Any]:
    indices = np.asarray([index for index, row in enumerate(data["rows"]) if row["role"] == role])
    return {
        "X": data["X"][indices],
        "frame_mask": data["frame_mask"][indices],
        "lengths": data["lengths"][indices],
        "rows": [data["rows"][int(index)] for index in indices],
    }


def evaluate(args: argparse.Namespace) -> int:
    output = args.run_dir.resolve()
    config = json.loads((output / "config" / "experiment.json").read_text(encoding="utf-8"))
    positive_root = Path(config["repaired_positive_root"])
    positives = {split: _load_positive(positive_root, split) for split in POSITIVE_SPLITS}
    negatives = _load_negative_features(output)
    dev_negative = _subset_negative(negatives, DEV_NEGATIVE_ROLE)
    fresh_negative = _subset_negative(negatives, FRESH_NEGATIVE_ROLE)
    results = {}
    started = time.perf_counter()
    for seed in SEEDS:
        print(f"[e6-3/evaluate] seed {seed}")
        model_path = Path(config["checkpoints"][str(seed)]["path"])
        positive_outputs = {split: _model_outputs(model_path, data) for split, data in positives.items()}
        dev_outputs = _model_outputs(model_path, dev_negative)
        fresh_outputs = _model_outputs(model_path, fresh_negative)
        fit = _fit_oas_mahalanobis(
            positive_outputs["train"]["embedding"], positives["train"]["y"].astype(np.int64)
        )
        scores = {}
        for method in METHODS:
            if method == "mahalanobis":
                positive_scores = {split: _mahalanobis_score(value, fit) for split, value in positive_outputs.items()}
                dev_scores = _mahalanobis_score(dev_outputs, fit)
                fresh_scores = _mahalanobis_score(fresh_outputs, fit)
            else:
                positive_scores = {split: value[method] for split, value in positive_outputs.items()}
                dev_scores = dev_outputs[method]
                fresh_scores = fresh_outputs[method]
            threshold, development = _select_threshold(
                positive_outputs["val"], positives["val"]["y"].astype(np.int64), positive_scores["val"],
                dev_outputs, dev_scores, dev_negative["rows"],
            )
            method_result: dict[str, Any] = {
                "valid_operating_point": threshold is not None,
                "threshold": threshold,
                "development": development,
                "known_vs_dev_negative_auroc": _binary_auc(
                    np.concatenate([np.ones(len(positive_scores["val"])), np.zeros(len(dev_scores))]),
                    np.concatenate([positive_scores["val"], dev_scores]),
                ),
                "known_vs_fresh_negative_auroc": _binary_auc(
                    np.concatenate([np.ones(len(positive_scores["test_fresh"])), np.zeros(len(fresh_scores))]),
                    np.concatenate([positive_scores["test_fresh"], fresh_scores]),
                ),
                "development_diagnostics": _development_diagnostics(
                    positive_outputs["val"], positives["val"]["y"].astype(np.int64),
                    positive_scores["val"], dev_outputs, dev_scores, dev_negative["rows"],
                ),
            }
            if threshold is not None:
                for split in ("test_fresh", "test_historical", "validation_variant_stress"):
                    method_result[split] = _operating_metrics(
                        positive_outputs[split], positives[split]["y"].astype(np.int64), positive_scores[split],
                        fresh_outputs if split == "test_fresh" else dev_outputs,
                        fresh_scores if split == "test_fresh" else dev_scores,
                        fresh_negative["rows"] if split == "test_fresh" else dev_negative["rows"],
                        threshold,
                    )
                stress_y = positives["validation_variant_stress"]["y"].astype(np.int64)
                stress_pred = positive_outputs["validation_variant_stress"]["prediction"]
                stress_accept = positive_scores["validation_variant_stress"] >= threshold
                know_id, hello_id = CLASSES.index("KNOW"), CLASSES.index("HELLO")
                know_mask = stress_y == know_id
                wrong = know_mask & (stress_pred == hello_id)
                correct = know_mask & (stress_pred == know_id)
                method_result["stress_know"] = {
                    "know_count": int(np.sum(know_mask)),
                    "know_to_hello_before": int(np.sum(wrong)),
                    "know_to_hello_accepted": int(np.sum(wrong & stress_accept)),
                    "know_to_hello_reduction": float(1.0 - np.sum(wrong & stress_accept) / max(np.sum(wrong), 1)),
                    "correct_know_before": int(np.sum(correct)),
                    "correct_know_accepted": int(np.sum(correct & stress_accept)),
                    "correct_know_retention": float(np.sum(correct & stress_accept) / max(np.sum(correct), 1)),
                }
            scores[method] = method_result
        np.savez_compressed(
            output / "metrics" / f"seed_{seed}_mahalanobis_parameters.npz",
            means=fit["means"].astype(np.float32),
            inverse_covariance=fit["inverse_covariance"].astype(np.float32),
            shrinkage=np.float32(fit["shrinkage"]),
        )
        results[str(seed)] = {"model": str(model_path), "methods": scores}
    mahalanobis = [results[str(seed)]["methods"]["mahalanobis"] for seed in SEEDS]
    valid = all(item["valid_operating_point"] for item in mahalanobis)
    gate_checks: dict[str, bool] = {"valid_all_seeds": valid}
    if valid:
        fresh = [item["test_fresh"] for item in mahalanobis]
        stress = [item["stress_know"] for item in mahalanobis]
        precision = [item["accepted_precision"] for item in fresh]
        coverage = [item["positive_coverage"] for item in fresh]
        stable = [
            item["per_class"][label]["accepted_recall"]
            for item in fresh for label in ("GOOD", "HELLO", "SORRY", "HAVE")
        ]
        know = [item["per_class"]["KNOW"]["accepted_recall"] for item in fresh]
        oov = [item["negative_subtype_false_accept_rate"].get("OOV_SIGN", 0.0) for item in fresh]
        nonoov = [
            value for item in fresh for subtype, value in item["negative_subtype_false_accept_rate"].items()
            if subtype != "OOV_SIGN"
        ]
        reductions = [item["know_to_hello_reduction"] for item in stress]
        retentions = [item["correct_know_retention"] for item in stress]
        gate_checks.update(
            {
                "fresh_precision": np.mean(precision) >= GATES["fresh_mean_accepted_precision_min"]
                and min(precision) >= GATES["fresh_min_accepted_precision_min"],
                "fresh_coverage": np.mean(coverage) >= GATES["fresh_mean_positive_coverage_min"]
                and min(coverage) >= GATES["fresh_min_positive_coverage_min"],
                "fresh_stable_recall": np.mean(stable) >= GATES["fresh_stable_mean_accepted_recall_min"]
                and min(stable) >= GATES["fresh_stable_min_accepted_recall_min"],
                "fresh_know_recall": np.mean(know) >= GATES["fresh_know_mean_accepted_recall_min"]
                and min(know) >= GATES["fresh_know_min_accepted_recall_min"],
                "fresh_oov_far": max(oov) <= GATES["fresh_oov_far_max"],
                "fresh_nonoov_far": max(nonoov, default=0.0) <= GATES["fresh_nonoov_subtype_far_max"],
                "stress_false_commit_reduction": np.mean(reductions) >= GATES["stress_know_to_hello_reduction_min"],
                "stress_correct_retention": np.mean(retentions) >= GATES["stress_correct_know_retention_min"],
            }
        )
    passed = bool(gate_checks and all(gate_checks.values()))
    payload = {
        "experiment": EXPERIMENT,
        "run_dir": str(output),
        "results": results,
        "gate_checks": gate_checks,
        "passed": passed,
        "decision": "e6_3_diagnostic_go" if passed else "e6_3_no_go_or_more_negative_evidence_required",
        "elapsed_seconds": time.perf_counter() - started,
        "limitations": [
            "Fresh negative evaluation has one signer and cannot support a production claim.",
            "Fresh and stress positive diagnostics have been inspected repeatedly.",
            "No Android/export action is authorized by this result.",
        ],
    }
    _write_json(output / "metrics" / "metrics.json", payload)
    print(json.dumps(payload, indent=2))
    return 0


def check(args: argparse.Namespace) -> int:
    output = args.run_dir.resolve()
    errors = []
    config_path = output / "config" / "experiment.json"
    if not config_path.exists():
        errors.append("missing config/experiment.json")
    if args.require_smoke:
        smoke_path = output / "smoke" / "smoke_summary.json"
        if not smoke_path.exists():
            errors.append("missing smoke/smoke_summary.json")
        elif not json.loads(smoke_path.read_text(encoding="utf-8")).get("passed"):
            errors.append("smoke did not pass")
    if args.require_metrics:
        metrics_path = output / "metrics" / "metrics.json"
        if not metrics_path.exists():
            errors.append("missing metrics/metrics.json")
    payload = {"run_dir": str(output), "passed": not errors, "errors": errors}
    _write_json(output / "check_report.json", payload)
    print(json.dumps(payload, indent=2))
    return 0 if not errors else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="E6-3 frozen-embedding open-set rejection")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--assignment", type=Path, default=DEFAULT_ASSIGNMENT)
    prepare_parser.add_argument("--repaired", type=Path, default=DEFAULT_REPAIRED)
    prepare_parser.add_argument("--control", type=Path, default=DEFAULT_CONTROL)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--extract-config", type=Path, default=DEFAULT_EXTRACT_CONFIG)
    prepare_parser.add_argument("--normalize-config", type=Path, default=DEFAULT_NORMALIZE_CONFIG)
    prepare_parser.set_defaults(func=prepare)
    for name, func in (("extract-negatives", extract_negatives), ("smoke", smoke), ("evaluate", evaluate), ("check", check)):
        command = sub.add_parser(name)
        command.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
        if name == "check":
            command.add_argument("--require-smoke", action="store_true")
            command.add_argument("--require-metrics", action="store_true")
        command.set_defaults(func=func)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"[e6-3] ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
