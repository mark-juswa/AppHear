"""Artifact-only attribution audit for Perception vNext 236-class generalization."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.perception_vnext.recognition_schema import (
    BODY_SUPPORT_THRESHOLD,
    FEATURE_SCHEMA,
    HAND_PROPOSAL_SUPPORT_THRESHOLD,
    RAW_SCHEMA,
    derive_frame_features,
    load_raw_sequence,
)

MILESTONE = "PERCEPTION_VNEXT_GENERALIZATION_ATTRIBUTION_236_01"
ROOT = Path(__file__).resolve().parents[2]
UTILITY_ROOT = (
    ROOT
    / "artifacts"
    / "recognition_upgrade"
    / "perception_vnext"
    / "recognition_utility_236_01"
)
DEFAULT_DATASET = UTILITY_ROOT / "dataset"
DEFAULT_RUN = UTILITY_ROOT / "tcn_run_01"
DEFAULT_OUTPUT = UTILITY_ROOT / "generalization_attribution_236_01"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"ATTRIBUTION_EMPTY_CSV:{path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _finite(values: Iterable[Any]) -> np.ndarray:
    array = np.asarray(list(values), np.float64)
    return array[np.isfinite(array)]


def _mean(values: Iterable[Any]) -> float | None:
    array = _finite(values)
    return float(array.mean()) if len(array) else None


def _median(values: Iterable[Any]) -> float | None:
    array = _finite(values)
    return float(np.median(array)) if len(array) else None


def _percentile(values: Iterable[Any], value: float) -> float | None:
    array = _finite(values)
    return float(np.percentile(array, value)) if len(array) else None


def _safe_rate(numerator: int | float, denominator: int | float) -> float | None:
    return float(numerator / denominator) if denominator else None


def _rankdata(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, np.float64)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), np.float64)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + end - 1) * 0.5 + 1.0
        start = end
    return ranks


def _spearman(left: Iterable[Any], right: Iterable[Any]) -> dict[str, Any]:
    x = np.asarray(list(left), np.float64)
    y = np.asarray(list(right), np.float64)
    keep = np.isfinite(x) & np.isfinite(y)
    x, y = x[keep], y[keep]
    if len(x) < 3 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return {"n": int(len(x)), "rho": None, "status": "UNAVAILABLE_CONSTANT_OR_SMALL"}
    rho = float(np.corrcoef(_rankdata(x), _rankdata(y))[0, 1])
    return {"n": int(len(x)), "rho": rho, "status": "AVAILABLE_DESCRIPTIVE"}


def _standardized_difference(group_a: Iterable[Any], group_b: Iterable[Any]) -> dict[str, Any]:
    """Group-A minus group-B descriptive effects; positive means A is higher."""

    a, b = _finite(group_a), _finite(group_b)
    result: dict[str, Any] = {
        "group_a_n": int(len(a)),
        "group_b_n": int(len(b)),
        "group_a_mean": float(a.mean()) if len(a) else None,
        "group_b_mean": float(b.mean()) if len(b) else None,
        "group_a_median": float(np.median(a)) if len(a) else None,
        "group_b_median": float(np.median(b)) if len(b) else None,
        "standardized_mean_difference": None,
        "rank_biserial": None,
    }
    if not len(a) or not len(b):
        return result
    variance = 0.0
    denominator = len(a) + len(b) - 2
    if denominator > 0:
        variance = (
            max(len(a) - 1, 0) * float(np.var(a, ddof=1) if len(a) > 1 else 0.0)
            + max(len(b) - 1, 0) * float(np.var(b, ddof=1) if len(b) > 1 else 0.0)
        ) / denominator
    if variance > 0:
        result["standardized_mean_difference"] = float((a.mean() - b.mean()) / math.sqrt(variance))
    sorted_b = np.sort(b)
    greater = sum(int(np.searchsorted(sorted_b, value, side="left")) for value in a)
    less = sum(int(len(b) - np.searchsorted(sorted_b, value, side="right")) for value in a)
    result["rank_biserial"] = float((greater - less) / (len(a) * len(b)))
    return result


def _side_geometry(block: np.ndarray) -> dict[str, float]:
    valid = block[:, :, 3] > 0.5
    points = block[:, :, :2]
    valid_points = points[valid]
    output = {
        "norm_x_mean": math.nan,
        "norm_y_mean": math.nan,
        "norm_x_p05": math.nan,
        "norm_x_p95": math.nan,
        "norm_y_p05": math.nan,
        "norm_y_p95": math.nan,
        "norm_wrist_x_mean": math.nan,
        "norm_wrist_y_mean": math.nan,
        "norm_center_x_mean": math.nan,
        "norm_center_y_mean": math.nan,
        "norm_span_mean": math.nan,
    }
    if len(valid_points):
        output.update(
            {
                "norm_x_mean": float(valid_points[:, 0].mean()),
                "norm_y_mean": float(valid_points[:, 1].mean()),
                "norm_x_p05": float(np.percentile(valid_points[:, 0], 5)),
                "norm_x_p95": float(np.percentile(valid_points[:, 0], 95)),
                "norm_y_p05": float(np.percentile(valid_points[:, 1], 5)),
                "norm_y_p95": float(np.percentile(valid_points[:, 1], 95)),
            }
        )
    wrists = points[:, 0]
    wrist_valid = valid[:, 0]
    if np.any(wrist_valid):
        output["norm_wrist_x_mean"] = float(wrists[wrist_valid, 0].mean())
        output["norm_wrist_y_mean"] = float(wrists[wrist_valid, 1].mean())
    centers: list[np.ndarray] = []
    spans: list[float] = []
    for frame_points, frame_valid in zip(points, valid, strict=True):
        visible = frame_points[frame_valid]
        if len(visible):
            centers.append(visible.mean(axis=0))
        if len(visible) >= 2:
            extent = np.ptp(visible, axis=0)
            spans.append(float(np.linalg.norm(extent)))
    if centers:
        center = np.asarray(centers).mean(axis=0)
        output["norm_center_x_mean"] = float(center[0])
        output["norm_center_y_mean"] = float(center[1])
    if spans:
        output["norm_span_mean"] = float(np.mean(spans))
    return output


def _clip_statistics(row: dict[str, Any]) -> dict[str, Any]:
    raw = load_raw_sequence(Path(row["raw_path"]))
    features = derive_frame_features(raw)
    with np.load(Path(row["feature_path"]), allow_pickle=False) as saved:
        metadata = json.loads(str(saved["metadata_json"].item()))
        if metadata.get("schema") != FEATURE_SCHEMA:
            raise RuntimeError(f"ATTRIBUTION_FEATURE_SCHEMA:{row['sample_id']}")
        dense_count = int(np.count_nonzero(saved["dense_mask"]))
        sparse_count = int(np.count_nonzero(saved["sparse_mask"]))
    if (
        raw.metadata.get("schema") != RAW_SCHEMA
        or raw.metadata.get("sample_id") != row["sample_id"]
    ):
        raise RuntimeError(f"ATTRIBUTION_RAW_IDENTITY:{row['sample_id']}")
    if dense_count != int(row["dense_frames"]) or sparse_count != int(row["sparse_frames"]):
        raise RuntimeError(f"ATTRIBUTION_TEMPORAL_COUNT:{row['sample_id']}")

    observed = raw.hand_observed.astype(bool)
    proposal = raw.hand_proposal_present.astype(bool)
    valid = raw.hand_joint_valid.astype(bool) & observed[:, :, None]
    valid_counts = valid.sum(axis=2)
    proposal_support = np.asarray(raw.hand_proposal_support, np.float64)
    support_keep = proposal[:, :, None] & np.isfinite(proposal_support)
    support_values = proposal_support[support_keep]
    side_support = [proposal_support[proposal[:, side]] for side in range(2)]
    side_support = [values[np.isfinite(values)] for values in side_support]
    body_support = np.asarray(raw.body_support, np.float64)
    body_support_values = body_support[np.isfinite(body_support)]
    body_valid = raw.body_valid.astype(bool)
    source_short = np.min(raw.source_size.astype(np.float64), axis=1)
    shoulders_ok = body_valid[:, 0] & body_valid[:, 1]
    hips_ok = body_valid[:, 6] & body_valid[:, 7]
    shoulder_fraction = np.linalg.norm(raw.body_xy[:, 0] - raw.body_xy[:, 1], axis=1) / source_short
    hip_fraction = np.linalg.norm(raw.body_xy[:, 6] - raw.body_xy[:, 7], axis=1) / source_short
    normalized_body = features[:, 168:200].reshape(len(features), 8, 4)
    normalized_body_valid = normalized_body[:, :, 3] > 0.5
    body_centers: list[np.ndarray] = []
    for points, frame_valid in zip(
        normalized_body[:, :, :2], normalized_body_valid, strict=True
    ):
        if np.any(frame_valid):
            body_centers.append(points[frame_valid].mean(axis=0))
    body_center = np.asarray(body_centers).mean(axis=0) if body_centers else [math.nan, math.nan]
    lh_geometry = _side_geometry(features[:, 0:84].reshape(len(features), 21, 4))
    rh_geometry = _side_geometry(features[:, 84:168].reshape(len(features), 21, 4))
    duration_ms = float(metadata["duration_ms"])
    deltas = np.diff(raw.timestamp_ms.astype(np.float64))

    output: dict[str, Any] = {
        "sample_id": row["sample_id"],
        "split": row["split"],
        "class_id": int(row["class_id"]),
        "canonical_gloss": row["canonical_gloss"],
        "signer_id": row["signer_id"],
        "source_id": row["source_id"],
        "raw_frames": len(raw.frame_index),
        "dense_frames": dense_count,
        "sparse_frames": sparse_count,
        "duration_ms": duration_ms,
        "lh_observed_rate": float(observed[:, 0].mean()),
        "rh_observed_rate": float(observed[:, 1].mean()),
        "either_hand_observed_rate": float(np.any(observed, axis=1).mean()),
        "both_hands_observed_rate": float(np.all(observed, axis=1).mean()),
        "no_hand_observed_rate": float((~np.any(observed, axis=1)).mean()),
        "lh_proposal_present_rate": float(proposal[:, 0].mean()),
        "rh_proposal_present_rate": float(proposal[:, 1].mean()),
        "either_proposal_present_rate": float(np.any(proposal, axis=1).mean()),
        "both_proposals_present_rate": float(np.all(proposal, axis=1).mean()),
        "lh_valid_joints_per_frame": float(valid_counts[:, 0].mean()),
        "rh_valid_joints_per_frame": float(valid_counts[:, 1].mean()),
        "valid_hand_joints_per_frame": float(valid_counts.sum(axis=1).mean()),
        "lh_valid_fraction_observed": _mean(valid_counts[observed[:, 0], 0] / 21.0),
        "rh_valid_fraction_observed": _mean(valid_counts[observed[:, 1], 1] / 21.0),
        "hand_proposal_support_mean": _mean(support_values),
        "hand_proposal_support_median": _median(support_values),
        "hand_low_support_fraction": _safe_rate(
            int(np.count_nonzero(support_values < HAND_PROPOSAL_SUPPORT_THRESHOLD)),
            len(support_values),
        ),
        "lh_proposal_support_mean": _mean(side_support[0]),
        "rh_proposal_support_mean": _mean(side_support[1]),
        "body_valid_points_per_frame": float(body_valid.sum(axis=1).mean()),
        "body_available_rate": float(raw.body_available.astype(bool).mean()),
        "body_support_mean": _mean(body_support_values),
        "body_support_median": _median(body_support_values),
        "body_low_support_fraction": _safe_rate(
            int(np.count_nonzero(body_support_values < BODY_SUPPORT_THRESHOLD)),
            len(body_support_values),
        ),
        "body_normalization_valid_rate": float((features[:, 205] > 0.5).mean()),
        "normalization_fallback_rate": float((features[:, 205] <= 0.5).mean()),
        "shoulder_scale_source_fraction": _mean(shoulder_fraction[shoulders_ok]),
        "hip_scale_source_fraction": _mean(hip_fraction[hips_ok]),
        "normalized_body_center_x": float(body_center[0]),
        "normalized_body_center_y": float(body_center[1]),
        "frame_delta_ms_mean": _mean(deltas),
        "frame_delta_ms_median": _median(deltas),
    }
    output.update({f"lh_{key}": value for key, value in lh_geometry.items()})
    output.update({f"rh_{key}": value for key, value in rh_geometry.items()})
    return output


def _predict_dev(
    rows: list[dict[str, Any]], checkpoint: Path, batch_size: int
) -> dict[str, dict[str, Any]]:
    import tensorflow as tf

    model = tf.keras.models.load_model(checkpoint, safe_mode=True)
    output: dict[str, dict[str, Any]] = {row["sample_id"]: {} for row in rows}
    for condition, prefix in (("dense", "dense"), ("phone_01_sparse", "sparse")):
        for start in range(0, len(rows), batch_size):
            batch_rows = rows[start : start + batch_size]
            features, masks = [], []
            for row in batch_rows:
                with np.load(Path(row["feature_path"]), allow_pickle=False) as data:
                    features.append(np.asarray(data[f"{prefix}_features"], np.float32))
                    masks.append(np.asarray(data[f"{prefix}_mask"], bool))
            probabilities = np.asarray(
                model([np.stack(features), np.stack(masks)], training=False), np.float32
            )
            for row, probability in zip(batch_rows, probabilities, strict=True):
                label = int(row["class_id"])
                prediction = int(np.argmax(probability))
                top5 = np.argpartition(probability, -5)[-5:]
                output[row["sample_id"]].update(
                    {
                        f"{condition}_prediction": prediction,
                        f"{condition}_correct": bool(prediction == label),
                        f"{condition}_top5_correct": bool(label in top5),
                        f"{condition}_target_probability": float(probability[label]),
                        f"{condition}_max_probability": float(probability[prediction]),
                    }
                )
    return output


QUALITY_METRICS = (
    "lh_observed_rate",
    "rh_observed_rate",
    "either_hand_observed_rate",
    "both_hands_observed_rate",
    "no_hand_observed_rate",
    "either_proposal_present_rate",
    "both_proposals_present_rate",
    "valid_hand_joints_per_frame",
    "lh_valid_fraction_observed",
    "rh_valid_fraction_observed",
    "hand_proposal_support_mean",
    "hand_low_support_fraction",
    "body_valid_points_per_frame",
    "body_available_rate",
    "body_support_mean",
    "body_low_support_fraction",
    "body_normalization_valid_rate",
    "normalization_fallback_rate",
    "raw_frames",
    "dense_frames",
    "sparse_frames",
    "duration_ms",
)

SHIFT_METRICS = (
    "lh_norm_wrist_x_mean",
    "lh_norm_wrist_y_mean",
    "rh_norm_wrist_x_mean",
    "rh_norm_wrist_y_mean",
    "lh_norm_center_x_mean",
    "lh_norm_center_y_mean",
    "rh_norm_center_x_mean",
    "rh_norm_center_y_mean",
    "lh_norm_span_mean",
    "rh_norm_span_mean",
    "normalized_body_center_x",
    "normalized_body_center_y",
    "shoulder_scale_source_fraction",
    "hip_scale_source_fraction",
    "body_normalization_valid_rate",
    "normalization_fallback_rate",
    "frame_delta_ms_mean",
    "duration_ms",
    "dense_frames",
    "sparse_frames",
)


def _aggregate_signers(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in clips:
        groups[(row["split"], row["signer_id"])].append(row)
    output = []
    for (split, signer), rows in sorted(groups.items()):
        item: dict[str, Any] = {
            "split": split,
            "signer_id": signer,
            "clips": len(rows),
            "raw_frames": int(sum(int(row["raw_frames"]) for row in rows)),
            "sources": "|".join(sorted({row["source_id"] for row in rows})),
        }
        for metric in QUALITY_METRICS:
            values = [row.get(metric) for row in rows]
            item[f"{metric}_mean"] = _mean(values)
            item[f"{metric}_median"] = _median(values)
            if metric in {
                "hand_proposal_support_mean",
                "body_support_mean",
                "duration_ms",
                "raw_frames",
                "sparse_frames",
            }:
                item[f"{metric}_p10"] = _percentile(values, 10)
                item[f"{metric}_p90"] = _percentile(values, 90)
        if split == "dev":
            item["dense_top1"] = _mean(row["dense_correct"] for row in rows)
            item["phone_01_sparse_top1"] = _mean(
                row["phone_01_sparse_correct"] for row in rows
            )
        output.append(item)
    return output


def _error_associations(dev: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "effect_direction": (
            "correct minus incorrect; positive means higher values on correct clips"
        ),
        "causality_claim": False,
        "conditions": {},
    }
    for condition in ("dense", "phone_01_sparse"):
        correct = [row for row in dev if row[f"{condition}_correct"]]
        incorrect = [row for row in dev if not row[f"{condition}_correct"]]
        result["conditions"][condition] = {
            "correct_clips": len(correct),
            "incorrect_clips": len(incorrect),
            "metrics": {
                metric: _standardized_difference(
                    [row.get(metric) for row in correct],
                    [row.get(metric) for row in incorrect],
                )
                for metric in QUALITY_METRICS
            },
        }
    return result


def _class_conditioned_shift_analysis(
    train: list[dict[str, Any]],
    dev: list[dict[str, Any]],
    metrics: tuple[str, ...],
) -> dict[str, Any]:
    train_by_class: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in train:
        train_by_class[int(row["class_id"])].append(row)
    metric_results: dict[str, Any] = {}
    clip_abs_z: defaultdict[str, list[float]] = defaultdict(list)
    for metric in metrics:
        global_values = _finite(row.get(metric) for row in train)
        global_sd = float(np.std(global_values, ddof=1)) if len(global_values) > 1 else 0.0
        signer_values: defaultdict[str, list[float]] = defaultdict(list)
        matched: list[tuple[dict[str, Any], float]] = []
        for row in dev:
            value = row.get(metric)
            if value is None or not np.isfinite(float(value)):
                continue
            reference = _finite(item.get(metric) for item in train_by_class[int(row["class_id"])])
            if not len(reference):
                continue
            center = float(np.median(reference))
            class_sd = float(np.std(reference, ddof=1)) if len(reference) > 1 else 0.0
            scale = max(class_sd, global_sd * 0.10, 1e-6)
            standardized = float((float(value) - center) / scale)
            signer_values[row["signer_id"]].append(standardized)
            clip_abs_z[row["sample_id"]].append(abs(standardized))
            matched.append((row, standardized))
        metric_results[metric] = {
            "matched_dev_clips": len(matched),
            "signed_mean_z": _mean(value for _, value in matched),
            "median_abs_z": _median(abs(value) for _, value in matched),
            "by_signer": {
                signer: {
                    "clips": len(values),
                    "signed_mean_z": _mean(values),
                    "median_abs_z": _median(abs(value) for value in values),
                }
                for signer, values in sorted(signer_values.items())
            },
            "abs_shift_correct_minus_incorrect": {
                condition: _standardized_difference(
                    [
                        abs(value)
                        for row, value in matched
                        if row[f"{condition}_correct"]
                    ],
                    [
                        abs(value)
                        for row, value in matched
                        if not row[f"{condition}_correct"]
                    ],
                )
                for condition in ("dense", "phone_01_sparse")
            },
        }
    composite_rows = [
        (row, float(np.median(clip_abs_z[row["sample_id"]])))
        for row in dev
        if clip_abs_z[row["sample_id"]]
    ]
    return {
        "metrics": metric_results,
        "composite_median_abs_z": {
            "clips": len(composite_rows),
            "by_signer": {
                signer: {
                    "clips": len(values),
                    "mean": _mean(values),
                    "median": _median(values),
                }
                for signer, values in sorted(
                    {
                        signer: [
                            value
                            for row, value in composite_rows
                            if row["signer_id"] == signer
                        ]
                        for signer in {row["signer_id"] for row, _ in composite_rows}
                    }.items()
                )
            },
            "correct_minus_incorrect": {
                condition: _standardized_difference(
                    [
                        value
                        for row, value in composite_rows
                        if row[f"{condition}_correct"]
                    ],
                    [
                        value
                        for row, value in composite_rows
                        if not row[f"{condition}_correct"]
                    ],
                )
                for condition in ("dense", "phone_01_sparse")
            },
        },
        "method": (
            "Each DEV clip is centered on its TRAIN-class median and divided by the larger of "
            "that class SD, 10% of global TRAIN SD, or 1e-6. Descriptive only."
        ),
    }


def _normalization_shift(clips: list[dict[str, Any]]) -> dict[str, Any]:
    train = [row for row in clips if row["split"] == "train"]
    dev = [row for row in clips if row["split"] == "dev"]
    unconditioned = {
        metric: _standardized_difference(
            [row.get(metric) for row in dev], [row.get(metric) for row in train]
        )
        for metric in SHIFT_METRICS
    }
    conditioned = _class_conditioned_shift_analysis(train, dev, SHIFT_METRICS)
    return {
        "schema": "APPHEAR_VNEXT_NORMALIZATION_SHIFT_V1",
        "feature_schema": FEATURE_SCHEMA,
        "unconditioned_dev_minus_train": unconditioned,
        "class_conditioned": conditioned["metrics"],
        "composite_class_conditioned_shift": conditioned["composite_median_abs_z"],
        "class_conditioned_method": conditioned["method"],
        "protected_test_accessed": False,
    }


def _perception_quality_shift(clips: list[dict[str, Any]]) -> dict[str, Any]:
    train = [row for row in clips if row["split"] == "train"]
    dev = [row for row in clips if row["split"] == "dev"]
    metrics = (
        "lh_observed_rate",
        "rh_observed_rate",
        "either_hand_observed_rate",
        "both_hands_observed_rate",
        "valid_hand_joints_per_frame",
        "hand_proposal_support_mean",
        "hand_low_support_fraction",
        "body_valid_points_per_frame",
        "body_available_rate",
        "body_support_mean",
        "body_normalization_valid_rate",
    )
    conditioned = _class_conditioned_shift_analysis(train, dev, metrics)
    return {
        "schema": "APPHEAR_VNEXT_PERCEPTION_QUALITY_SHIFT_V1",
        "raw_schema": RAW_SCHEMA,
        "class_conditioned": conditioned["metrics"],
        "composite_class_conditioned_shift": conditioned["composite_median_abs_z"],
        "class_conditioned_method": conditioned["method"],
        "protected_test_accessed": False,
    }


def _class_diversity(
    index_rows: list[dict[str, Any]], evaluation: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    train: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    dev: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in index_rows:
        (train if row["split"] == "train" else dev)[int(row["class_id"])].append(row)
    dense = {row["class_id"]: row for row in evaluation["details"]["dev"]["dense"]["per_class"]}
    sparse = {
        row["class_id"]: row
        for row in evaluation["details"]["dev"]["phone_01_sparse"]["per_class"]
    }
    output = []
    for class_id in range(236):
        rows = train[class_id]
        signer_counts = Counter(row["signer_id"] for row in rows)
        source_counts = Counter(row["source_id"] for row in rows)
        signer_shares = np.asarray(list(signer_counts.values()), np.float64) / len(rows)
        source_shares = np.asarray(list(source_counts.values()), np.float64) / len(rows)
        output.append(
            {
                "class_id": class_id,
                "canonical_gloss": rows[0]["canonical_gloss"],
                "train_clips": len(rows),
                "train_distinct_signers": len(signer_counts),
                "train_distinct_sources": len(source_counts),
                "train_clips_per_signer_mean": float(len(rows) / len(signer_counts)),
                "largest_signer_share": float(signer_shares.max()),
                "signer_concentration_hhi": float(np.square(signer_shares).sum()),
                "effective_signers": float(1.0 / np.square(signer_shares).sum()),
                "largest_source_share": float(source_shares.max()),
                "source_concentration_hhi": float(np.square(source_shares).sum()),
                "effective_sources": float(1.0 / np.square(source_shares).sum()),
                "train_asl_citizen_clips": source_counts.get("ASL_CITIZEN", 0),
                "train_apphear_capture_clips": source_counts.get("APPHEAR_CAPTURE", 0),
                "train_local_clips": source_counts.get("LOCAL", 0),
                "dev_support": len(dev[class_id]),
                "dense_dev_recall": dense[class_id]["recall"],
                "dense_dev_f1": dense[class_id]["f1"],
                "sparse_dev_recall": sparse[class_id]["recall"],
                "sparse_dev_f1": sparse[class_id]["f1"],
            }
        )
    predictors = (
        "train_clips",
        "train_distinct_signers",
        "train_distinct_sources",
        "largest_signer_share",
        "signer_concentration_hhi",
        "largest_source_share",
        "source_concentration_hhi",
    )
    outcomes = ("dense_dev_recall", "dense_dev_f1", "sparse_dev_recall", "sparse_dev_f1")
    correlations = {
        predictor: {
            outcome: _spearman(
                [row[predictor] for row in output], [row[outcome] for row in output]
            )
            for outcome in outcomes
        }
        for predictor in predictors
    }

    def quartiles(metric: str, outcome: str) -> list[dict[str, Any]]:
        ordered = sorted(output, key=lambda row: (row[metric], row["class_id"]))
        return [
            {
                "rank_quartile": index + 1,
                "classes": len(group),
                "predictor_min": float(min(row[metric] for row in group)),
                "predictor_max": float(max(row[metric] for row in group)),
                "outcome_mean": _mean(row[outcome] for row in group),
                "dev_support": int(sum(row["dev_support"] for row in group)),
            }
            for index, group in enumerate(np.array_split(np.asarray(ordered, dtype=object), 4))
        ]

    summary = {
        "schema": "APPHEAR_VNEXT_CLASS_DIVERSITY_SUMMARY_V1",
        "classes": len(output),
        "correlations": correlations,
        "rank_quartile_summaries": {
            metric: {
                outcome: quartiles(metric, outcome)
                for outcome in ("dense_dev_recall", "sparse_dev_recall")
            }
            for metric in ("train_clips", "train_distinct_signers", "signer_concentration_hhi")
        },
        "dev_support_warning": "DEV support is 1-6 clips/class; correlations are descriptive.",
        "protected_test_accessed": False,
    }
    return output, summary


def _source_balance(
    index_rows: list[dict[str, Any]],
    class_rows: list[dict[str, Any]],
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    train = [row for row in index_rows if row["split"] == "train"]
    source_groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in train:
        source_groups[row["source_id"]].append(row)
    source_summary = {}
    for source, rows in sorted(source_groups.items()):
        source_summary[source] = {
            "clips": len(rows),
            "distinct_signers": len({row["signer_id"] for row in rows}),
            "classes": len({int(row["class_id"]) for row in rows}),
            "dense_train_top1": evaluation["details"]["train"]["dense"]["by_source"][source][
                "top1"
            ],
            "sparse_train_top1": evaluation["details"]["train"]["phone_01_sparse"][
                "by_source"
            ][source]["top1"],
        }
    supplemented = [
        row
        for row in class_rows
        if row["train_apphear_capture_clips"] + row["train_local_clips"] > 0
    ]
    unsupplemented = [row for row in class_rows if row not in supplemented]

    def class_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "classes": len(rows),
            "train_clips_mean": _mean(row["train_clips"] for row in rows),
            "train_signers_mean": _mean(row["train_distinct_signers"] for row in rows),
            "dense_dev_recall_mean": _mean(row["dense_dev_recall"] for row in rows),
            "sparse_dev_recall_mean": _mean(row["sparse_dev_recall"] for row in rows),
            "dense_dev_f1_mean": _mean(row["dense_dev_f1"] for row in rows),
            "sparse_dev_f1_mean": _mean(row["sparse_dev_f1"] for row in rows),
        }

    return {
        "schema": "APPHEAR_VNEXT_SOURCE_BALANCE_V1",
        "train_sources": source_summary,
        "dev_sources": {"ASL_CITIZEN": {"clips": 816, "signers": 5, "classes": 236}},
        "supplemented_classes": [
            {
                key: row[key]
                for key in (
                    "class_id",
                    "canonical_gloss",
                    "train_clips",
                    "train_distinct_signers",
                    "train_asl_citizen_clips",
                    "train_apphear_capture_clips",
                    "train_local_clips",
                    "largest_signer_share",
                    "dense_dev_recall",
                    "sparse_dev_recall",
                )
            }
            for row in supplemented
        ],
        "supplemented_group": class_group(supplemented),
        "unsupplemented_group": class_group(unsupplemented),
        "causality_claim": False,
        "protected_test_accessed": False,
    }


def _confusion_summary(
    dev: list[dict[str, Any]], evaluation: dict[str, Any]
) -> dict[str, Any]:
    output: dict[str, Any] = {
        "schema": "APPHEAR_VNEXT_CONFUSION_ATTRIBUTION_V1",
        "linguistic_grouping": {
            "status": "UNAVAILABLE",
            "reason": (
                "The governed index/raw/feature/evaluation artifacts contain no handshape, "
                "location, motion, one/two-hand, or lexical-variant grouping fields."
            ),
        },
        "conditions": {},
        "protected_test_accessed": False,
    }
    for condition in ("dense", "phone_01_sparse"):
        metrics = evaluation["details"]["dev"][condition]
        by_class: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in dev:
            by_class[int(row["class_id"])].append(row)
        recovery = []
        for class_id, rows in sorted(by_class.items()):
            top1 = sum(bool(row[f"{condition}_correct"]) for row in rows)
            top5 = sum(bool(row[f"{condition}_top5_correct"]) for row in rows)
            errors = len(rows) - top1
            recovery.append(
                {
                    "class_id": class_id,
                    "canonical_gloss": rows[0]["canonical_gloss"],
                    "support": len(rows),
                    "top1_correct": top1,
                    "top5_correct": top5,
                    "top5_only_recovered": top5 - top1,
                    "top5_recovery_among_top1_errors": _safe_rate(top5 - top1, errors),
                }
            )
        output["conditions"][condition] = {
            "zero_recall_classes": metrics["zero_recall_classes"],
            "zero_recall_count": len(metrics["zero_recall_classes"]),
            "largest_confusion_pairs": metrics["largest_confusion_pairs"],
            "top5_recovery_by_class": recovery,
            "top5_only_recovered_clips": int(
                sum(row["top5_only_recovered"] for row in recovery)
            ),
        }
    return output


def _cadence_interaction(dev: list[dict[str, Any]]) -> dict[str, Any]:
    categories: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in dev:
        dense = bool(row["dense_correct"])
        sparse = bool(row["phone_01_sparse_correct"])
        category = (
            "both_correct"
            if dense and sparse
            else "dense_only"
            if dense
            else "sparse_only"
            if sparse
            else "both_wrong"
        )
        categories[category].append(row)
    dense_only = categories["dense_only"]
    other = [row for name, rows in categories.items() if name != "dense_only" for row in rows]
    return {
        "schema": "APPHEAR_VNEXT_CADENCE_ERROR_INTERACTION_V1",
        "category_counts": {name: len(rows) for name, rows in sorted(categories.items())},
        "category_metric_means": {
            name: {metric: _mean(row.get(metric) for row in rows) for metric in QUALITY_METRICS}
            for name, rows in sorted(categories.items())
        },
        "dense_only_harmed_minus_all_other": {
            "effect_direction": "dense-only harmed minus all other DEV clips",
            "metrics": {
                metric: _standardized_difference(
                    [row.get(metric) for row in dense_only], [row.get(metric) for row in other]
                )
                for metric in QUALITY_METRICS
            },
        },
        "causality_claim": False,
        "protected_test_accessed": False,
    }


def _verify_prediction_parity(
    dev: list[dict[str, Any]], evaluation: dict[str, Any]
) -> dict[str, Any]:
    results = {}
    for condition in ("dense", "phone_01_sparse"):
        top1 = float(np.mean([row[f"{condition}_correct"] for row in dev]))
        top5 = float(np.mean([row[f"{condition}_top5_correct"] for row in dev]))
        expected = evaluation["details"]["dev"][condition]
        if abs(top1 - expected["top1"]) > 1e-12 or abs(top5 - expected["top5"]) > 1e-12:
            raise RuntimeError(f"ATTRIBUTION_PREDICTION_PARITY:{condition}:{top1}:{top5}")
        results[condition] = {
            "clips": len(dev),
            "top1": top1,
            "top5": top5,
            "matches_evaluation": True,
        }
    return results


def run(dataset: Path, run_dir: Path, output: Path, batch_size: int) -> dict[str, Any]:
    contract_path = dataset / "contract.json"
    governance_path = dataset / "governance_audit.json"
    index_path = dataset / "index.jsonl"
    evaluation_path = run_dir / "evaluation.json"
    checkpoint = run_dir / "best.keras"
    required = (
        contract_path,
        governance_path,
        index_path,
        evaluation_path,
        checkpoint,
        run_dir / "history.csv",
        run_dir / "run_identity.json",
        run_dir / "reproducibility_config.json",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"ATTRIBUTION_REQUIRED_ARTIFACT_MISSING:{missing}")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    governance = json.loads(governance_path.read_text(encoding="utf-8"))
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    if contract.get("raw_schema") != RAW_SCHEMA or contract.get("feature_schema") != FEATURE_SCHEMA:
        raise RuntimeError("ATTRIBUTION_CONTRACT_IDENTITY")
    if governance.get("status") != "PASS" or governance.get("protected_test_accessed"):
        raise RuntimeError("ATTRIBUTION_GOVERNANCE_FAILURE")
    if evaluation.get("status") != "PASS" or evaluation.get("protected_test_accessed"):
        raise RuntimeError("ATTRIBUTION_EVALUATION_IDENTITY")
    if _sha256(checkpoint) != evaluation.get("checkpoint_sha256"):
        raise RuntimeError("ATTRIBUTION_CHECKPOINT_HASH")
    index_rows = [
        json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line
    ]
    train_index = [row for row in index_rows if row["split"] == "train"]
    dev_index = [row for row in index_rows if row["split"] == "dev"]
    if len(train_index) != 3926 or len(dev_index) != 816:
        raise RuntimeError("ATTRIBUTION_POPULATION_COUNT")
    if {row["signer_id"] for row in train_index} & {row["signer_id"] for row in dev_index}:
        raise RuntimeError("ATTRIBUTION_SIGNER_LEAKAGE")
    if set(row["class_id"] for row in train_index) != set(range(236)) or set(
        row["class_id"] for row in dev_index
    ) != set(range(236)):
        raise RuntimeError("ATTRIBUTION_CLASS_COVERAGE")

    clip_rows = [_clip_statistics(row) for row in index_rows]
    predictions = _predict_dev(dev_index, checkpoint, batch_size)
    for row in clip_rows:
        if row["split"] == "dev":
            row.update(predictions[row["sample_id"]])
    dev_clips = [row for row in clip_rows if row["split"] == "dev"]
    prediction_parity = _verify_prediction_parity(dev_clips, evaluation)

    signer_rows = _aggregate_signers(clip_rows)
    error_association = _error_associations(dev_clips)
    perception_shift = _perception_quality_shift(clip_rows)
    normalization = _normalization_shift(clip_rows)
    class_rows, class_summary = _class_diversity(index_rows, evaluation)
    source = _source_balance(index_rows, class_rows, evaluation)
    confusion = _confusion_summary(dev_clips, evaluation)
    cadence = _cadence_interaction(dev_clips)

    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "per_signer_perception_quality.csv", signer_rows)
    _write_csv(output / "per_clip_quality_vs_correctness.csv", clip_rows)
    _write_csv(output / "class_diversity_generalization.csv", class_rows)
    _write_json(output / "perception_error_association.json", error_association)
    _write_json(output / "perception_quality_shift_summary.json", perception_shift)
    _write_json(output / "normalization_shift_summary.json", normalization)
    _write_json(output / "class_diversity_summary.json", class_summary)
    _write_json(output / "source_balance_summary.json", source)
    _write_json(output / "cadence_error_interaction.json", cadence)
    _write_json(output / "confusion_summary.json", confusion)
    integrity = {
        "schema": "APPHEAR_VNEXT_GENERALIZATION_ATTRIBUTION_INTEGRITY_V1",
        "milestone": MILESTONE,
        "status": "PASS",
        "raw_schema": RAW_SCHEMA,
        "feature_schema": FEATURE_SCHEMA,
        "train_clips": len(train_index),
        "dev_clips": len(dev_index),
        "classes": 236,
        "train_signers": len({row["signer_id"] for row in train_index}),
        "dev_signers": len({row["signer_id"] for row in dev_index}),
        "signer_overlap": [],
        "checkpoint_sha256": _sha256(checkpoint),
        "evaluation_sha256": _sha256(evaluation_path),
        "prediction_parity": prediction_parity,
        "full_extraction_executed": False,
        "full_training_executed": False,
        "protected_test_accessed": False,
    }
    _write_json(output / "integrity.json", integrity)
    result = {
        "schema": "APPHEAR_VNEXT_GENERALIZATION_ATTRIBUTION_AUDIT_V1",
        "milestone": MILESTONE,
        "status": "PASS",
        "output": str(output.resolve()),
        "integrity": integrity,
        "artifacts": sorted(path.name for path in output.iterdir() if path.is_file()),
        "decision": "REQUIRES_EVIDENCE_INTERPRETATION",
        "protected_test_accessed": False,
    }
    _write_json(output / "audit_summary.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_size > 256:
        raise RuntimeError("ATTRIBUTION_BATCH_SIZE_OUT_OF_RANGE")
    result = run(args.dataset, args.run, args.output, args.batch_size)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
