"""Independent validation of the frozen recognition-v2 representation gate.

The implementation deliberately does not import metric helpers from the original
gate. It reloads the saved V1/V2 packages and recomputes every reported metric.
No model is fitted and no representation feature is changed.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.perception_vnext.recognition_schema import load_raw_sequence

ROOT = Path(__file__).resolve().parents[2]
BASE = (
    ROOT
    / "artifacts"
    / "recognition_upgrade"
    / "perception_vnext"
    / "recognition_utility_236_01"
)
DEFAULT_V2_ROOT = BASE / "representation_v2_236_production_01"
DEV_SIGNERS = ("P5", "P12", "P21", "P26", "P39")
TOLERANCE = 2.0e-6


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    if len(rows) != 4742:
        raise RuntimeError(f"V2_VALIDATION_ROW_COUNT:{len(rows)}")
    return rows


def _summarize(features: np.ndarray, mask: np.ndarray) -> np.ndarray:
    real = np.asarray(features, np.float64)[np.asarray(mask, bool)]
    if not len(real):
        raise RuntimeError("V2_VALIDATION_EMPTY_VIEW")
    middle = max(1, len(real) // 2)
    late = real[middle:] if middle < len(real) else real[-1:]
    return np.concatenate(
        [real.mean(axis=0), real.std(axis=0), real[:middle].mean(axis=0), late.mean(axis=0)]
    )


def _embeddings(
    rows: list[dict[str, Any]], condition: str, version: str
) -> np.ndarray:
    values: list[np.ndarray] = []
    key = "v1_feature_path" if version == "v1" else "feature_path"
    for row in rows:
        with np.load(Path(row[key]), allow_pickle=False) as package:
            values.append(
                _summarize(
                    package[f"{condition}_features"], package[f"{condition}_mask"]
                )
            )
    result = np.asarray(values, np.float64)
    if not np.all(np.isfinite(result)):
        raise RuntimeError(f"V2_VALIDATION_NONFINITE:{version}:{condition}")
    return result


def _train_standardize(
    all_values: np.ndarray, train: np.ndarray
) -> tuple[np.ndarray, int]:
    train_values = all_values[train]
    mean = train_values.mean(axis=0)
    standard_deviation = train_values.std(axis=0)
    active = np.isfinite(standard_deviation) & (standard_deviation > 1.0e-6)
    return (all_values[:, active] - mean[active]) / standard_deviation[active], int(
        np.count_nonzero(active)
    )


def _group_centroids(
    values: np.ndarray, labels: np.ndarray, groups: np.ndarray
) -> np.ndarray:
    return np.asarray([values[labels == group].mean(axis=0) for group in groups])


def _distance_squared(values: np.ndarray, centers: np.ndarray) -> np.ndarray:
    return np.maximum(
        np.sum(values * values, axis=1, keepdims=True)
        + np.sum(centers * centers, axis=1)[None]
        - 2.0 * values @ centers.T,
        0.0,
    )


def _signer_accuracy(
    standardized: np.ndarray,
    train: np.ndarray,
    source_ids: np.ndarray,
    class_ids: np.ndarray,
    signer_ids: np.ndarray,
) -> dict[str, Any]:
    eligible = train & (source_ids == "ASL_CITIZEN")
    values = standardized[eligible]
    classes = class_ids[eligible]
    signers = signer_ids[eligible]
    class_centers = {
        int(class_id): values[classes == class_id].mean(axis=0)
        for class_id in np.unique(classes)
    }
    residual = np.asarray(
        [value - class_centers[int(label)] for value, label in zip(values, classes, strict=True)]
    )
    predicted: list[str] = []
    actual: list[str] = []
    for fold in range(5):
        reference = classes % 5 != fold
        query = ~reference
        identities = np.asarray(
            sorted(set(signers[reference]) & set(signers[query])), dtype=object
        )
        centers = _group_centroids(residual[reference], signers[reference], identities)
        usable_query = query & np.isin(signers, identities)
        nearest = np.argmin(_distance_squared(residual[usable_query], centers), axis=1)
        predicted.extend(identities[nearest].tolist())
        actual.extend(signers[usable_query].tolist())
    return {
        "accuracy": float(np.mean(np.asarray(predicted) == np.asarray(actual))),
        "clips": len(actual),
        "signers": len(set(actual)),
        "chance_fraction": 1.0 / len(set(actual)),
    }


def _metrics(
    standardized: np.ndarray,
    train: np.ndarray,
    class_ids: np.ndarray,
    signer_ids: np.ndarray,
) -> tuple[dict[str, Any], dict[str, dict[str, float]]]:
    train_values = standardized[train]
    dev_values = standardized[~train]
    train_labels = class_ids[train]
    dev_labels = class_ids[~train]
    dev_signer_ids = signer_ids[~train]
    classes = np.asarray(sorted(set(train_labels)), np.int32)
    train_centers = _group_centroids(train_values, train_labels, classes)
    dev_centers = _group_centroids(dev_values, dev_labels, classes)
    dimensions = train_values.shape[1]
    centroid_shift = np.sqrt(np.mean((train_centers - dev_centers) ** 2, axis=1))
    squared_euclidean = _distance_squared(dev_values, train_centers)
    rms_distances = np.sqrt(squared_euclidean / dimensions)
    class_column = {int(label): column for column, label in enumerate(classes)}
    truth_columns = np.asarray([class_column[int(label)] for label in dev_labels])
    true_distance = rms_distances[np.arange(len(dev_values)), truth_columns]
    wrong_distances = rms_distances.copy()
    wrong_distances[np.arange(len(dev_values)), truth_columns] = np.inf
    nearest_wrong_distance = np.min(wrong_distances, axis=1)
    ranked = np.argsort(rms_distances, axis=1)
    top1 = classes[ranked[:, 0]]
    top5 = classes[ranked[:, :5]]
    grand_center = train_centers.mean(axis=0)
    between = np.mean((train_centers - grand_center) ** 2)
    within = np.mean(
        [
            np.mean((value - train_centers[class_column[int(label)]]) ** 2)
            for value, label in zip(train_values, train_labels, strict=True)
        ]
    )
    summary = {
        "active_embedding_dimensions": dimensions,
        "class_conditioned_centroid_shift_median": float(np.median(centroid_shift)),
        "class_conditioned_centroid_shift_mean": float(np.mean(centroid_shift)),
        "dev_true_class_distance_median": float(np.median(true_distance)),
        "dev_true_class_distance_mean": float(np.mean(true_distance)),
        "nearest_centroid_top1": float(np.mean(top1 == dev_labels)),
        "nearest_centroid_top5": float(
            np.mean(
                [truth in guesses for truth, guesses in zip(dev_labels, top5, strict=True)]
            )
        ),
        # Despite the historical key name, this is nearest-wrong divided by true.
        "true_vs_nearest_wrong_distance_ratio": float(
            np.median(nearest_wrong_distance / np.maximum(true_distance, 1.0e-8))
        ),
        "class_fisher_between_within_ratio": float(between / max(within, 1.0e-12)),
        "raw_euclidean_true_class_distance_median": float(
            np.median(true_distance * np.sqrt(dimensions))
        ),
    }
    by_signer: dict[str, dict[str, float]] = {}
    for signer in DEV_SIGNERS:
        keep = np.asarray([value.split(":")[-1] == signer for value in dev_signer_ids])
        by_signer[signer] = {
            "clips": int(np.count_nonzero(keep)),
            "true_class_distance_mean": float(true_distance[keep].mean()),
            "true_class_distance_median": float(np.median(true_distance[keep])),
            "nearest_centroid_top1": float(np.mean(top1[keep] == dev_labels[keep])),
            "nearest_centroid_top5": float(
                np.mean(
                    [
                        truth in guesses
                        for truth, guesses in zip(
                            dev_labels[keep], top5[keep], strict=True
                        )
                    ]
                )
            ),
        }
    return summary, by_signer


def _maximum_metric_delta(
    expected: dict[str, Any], actual: dict[str, Any], names: tuple[str, ...]
) -> float:
    return max(abs(float(expected[name]) - float(actual[name])) for name in names)


def _validate_motion_pair(
    features: np.ndarray,
    row: int,
    static_slice: slice,
    motion_slice: slice,
    validity: float,
    dt: float,
) -> float:
    actual = features[row, motion_slice]
    if validity < 0.5:
        return float(np.max(np.abs(actual)))
    expected = np.tanh(
        ((features[row, static_slice] - features[row - 1, static_slice]) / dt) / 4.0
    )
    return float(np.max(np.abs(actual - expected)))


def sparse_motion_audit(rows: list[dict[str, Any]], sample_count: int = 32) -> dict[str, Any]:
    maximum_dt_error = 0.0
    maximum_elapsed_error = 0.0
    maximum_motion_error = 0.0
    nonconsecutive_steps = 0
    invalid_motion_values_nonzero = 0
    first_step_failures = 0
    checked_steps = 0
    for row in rows[:sample_count]:
        raw = load_raw_sequence(Path(row["raw_path"]))
        with np.load(Path(row["feature_path"]), allow_pickle=False) as package:
            indices = np.asarray(package["sparse_source_indices"], np.int32)
            timestamps = np.asarray(package["sparse_source_timestamps_ms"], np.float64)
            mask = np.asarray(package["sparse_mask"], bool)
            features = np.asarray(package["sparse_features"], np.float64)[mask]
        if not np.all(np.diff(indices) > 0) or len(set(indices.tolist())) != len(indices):
            raise RuntimeError(f"V2_SPARSE_DUPLICATE_OR_ORDER:{row['sample_id']}")
        np.testing.assert_array_equal(timestamps, raw.timestamp_ms[indices])
        expected_dt = np.zeros(len(indices), np.float64)
        expected_dt[1:] = np.clip(np.diff(timestamps) / 1000.0, 0.0, 1.0)
        maximum_dt_error = max(
            maximum_dt_error,
            float(np.max(np.abs(features[:, 348] - expected_dt))),
        )
        duration = float(raw.timestamp_ms[-1] - raw.timestamp_ms[0])
        expected_elapsed = (
            (timestamps - raw.timestamp_ms[0]) / duration
            if duration > 0
            else np.zeros(len(indices))
        )
        maximum_elapsed_error = max(
            maximum_elapsed_error,
            float(np.max(np.abs(features[:, 349] - expected_elapsed))),
        )
        if np.any(features[0, 303:348] != 0.0):
            first_step_failures += 1
        for selected_row in range(1, len(indices)):
            checked_steps += 1
            if indices[selected_row] - indices[selected_row - 1] > 1:
                nonconsecutive_steps += 1
            dt = float(expected_dt[selected_row])
            for static_start, motion_start in ((0, 303), (130, 324)):
                specifications = [
                    (
                        slice(static_start + 120, static_start + 122),
                        slice(motion_start, motion_start + 2),
                        motion_start + 14,
                    ),
                    (
                        slice(static_start + 122, static_start + 124),
                        slice(motion_start + 2, motion_start + 4),
                        motion_start + 15,
                    ),
                ]
                for tip in range(5):
                    specifications.append(
                        (
                            slice(static_start + 105 + tip * 2, static_start + 107 + tip * 2),
                            slice(motion_start + 4 + tip * 2, motion_start + 6 + tip * 2),
                            motion_start + 16 + tip,
                        )
                    )
                for static_slice, motion_slice, validity_index in specifications:
                    validity = features[selected_row, validity_index]
                    error = _validate_motion_pair(
                        features,
                        selected_row,
                        static_slice,
                        motion_slice,
                        validity,
                        dt,
                    )
                    maximum_motion_error = max(maximum_motion_error, error)
                    if validity < 0.5 and error > 1.0e-7:
                        invalid_motion_values_nonzero += 1
            inter_validity = features[selected_row, 347]
            inter_error = _validate_motion_pair(
                features,
                selected_row,
                slice(298, 300),
                slice(345, 347),
                inter_validity,
                dt,
            )
            maximum_motion_error = max(maximum_motion_error, inter_error)
            if inter_validity < 0.5 and inter_error > 1.0e-7:
                invalid_motion_values_nonzero += 1
    passed = bool(
        maximum_dt_error <= 2.0e-7
        and maximum_elapsed_error <= 2.0e-7
        and maximum_motion_error <= 2.0e-6
        and nonconsecutive_steps > 0
        and invalid_motion_values_nonzero == 0
        and first_step_failures == 0
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "clips_checked": min(sample_count, len(rows)),
        "motion_steps_checked": checked_steps,
        "nonconsecutive_sparse_steps": nonconsecutive_steps,
        "maximum_dt_error": maximum_dt_error,
        "maximum_elapsed_fraction_error": maximum_elapsed_error,
        "maximum_selected_motion_error": maximum_motion_error,
        "invalid_motion_nonzero_failures": invalid_motion_values_nonzero,
        "first_step_failures": first_step_failures,
        "duplicates_or_interpolation": False,
    }


def run(v2_root: Path) -> dict[str, Any]:
    rows = _read_rows(v2_root / "dataset" / "index.jsonl")
    original = json.loads((v2_root / "representation_v2_gate.json").read_text(encoding="utf-8"))
    train = np.asarray([row["split"] == "train" for row in rows])
    class_ids = np.asarray([int(row["class_id"]) for row in rows], np.int32)
    signer_ids = np.asarray([row["signer_id"] for row in rows], dtype=object)
    source_ids = np.asarray([row["source_id"] for row in rows], dtype=object)
    metric_names = (
        "class_conditioned_centroid_shift_median",
        "class_conditioned_centroid_shift_mean",
        "dev_true_class_distance_median",
        "dev_true_class_distance_mean",
        "nearest_centroid_top1",
        "nearest_centroid_top5",
        "true_vs_nearest_wrong_distance_ratio",
        "class_fisher_between_within_ratio",
    )
    recomputed: dict[str, Any] = {}
    maximum_delta = 0.0
    maximum_signer_delta = 0.0
    for condition in ("dense", "sparse"):
        recomputed[condition] = {}
        for version in ("v1", "v2"):
            summary_values = _embeddings(rows, condition, version)
            standardized, active_dimensions = _train_standardize(summary_values, train)
            metrics, signer_metrics = _metrics(
                standardized, train, class_ids, signer_ids
            )
            metrics["active_embedding_dimensions"] = active_dimensions
            metrics["signer_identifiability"] = _signer_accuracy(
                standardized, train, source_ids, class_ids, signer_ids
            )
            recomputed[condition][version] = {
                "metrics": metrics,
                "dev_signers": signer_metrics,
            }
            expected = original["conditions"][condition][version]
            maximum_delta = max(
                maximum_delta,
                _maximum_metric_delta(expected, metrics, metric_names),
                abs(
                    float(expected["signer_identifiability"]["accuracy"])
                    - float(metrics["signer_identifiability"]["accuracy"])
                ),
            )

    with (v2_root / "dev_signer_representation_gate.csv").open(
        "r", encoding="utf-8", newline=""
    ) as stream:
        original_signers = list(csv.DictReader(stream))
    for row in original_signers:
        actual = recomputed[row["condition"]][row["version"]]["dev_signers"][row["signer"]]
        for name in (
            "true_class_distance_mean",
            "true_class_distance_median",
            "nearest_centroid_top1",
            "nearest_centroid_top5",
        ):
            maximum_signer_delta = max(
                maximum_signer_delta, abs(float(row[name]) - float(actual[name]))
            )

    motion = sparse_motion_audit(rows)
    reproducible = maximum_delta <= TOLERANCE and maximum_signer_delta <= TOLERANCE
    positive_signal = all(
        (
            recomputed[condition]["v2"]["metrics"]["signer_identifiability"]["accuracy"]
            < recomputed[condition]["v1"]["metrics"]["signer_identifiability"]["accuracy"]
            and recomputed[condition]["v2"]["metrics"]["nearest_centroid_top1"]
            > recomputed[condition]["v1"]["metrics"]["nearest_centroid_top1"]
            and recomputed[condition]["v2"]["metrics"]["nearest_centroid_top5"]
            > recomputed[condition]["v1"]["metrics"]["nearest_centroid_top5"]
            and recomputed[condition]["v2"]["metrics"][
                "true_vs_nearest_wrong_distance_ratio"
            ]
            > recomputed[condition]["v1"]["metrics"][
                "true_vs_nearest_wrong_distance_ratio"
            ]
        )
        for condition in ("dense", "sparse")
    )
    classification = (
        "V2_GATE_VALID_PROMISING"
        if reproducible and motion["status"] == "PASS" and positive_signal
        else "V2_GATE_INVALID"
        if not reproducible or motion["status"] != "PASS"
        else "V2_GATE_VALID_NOT_PROMISING"
    )
    result = {
        "milestone": "PERCEPTION_VNEXT_REPRESENTATION_V2_GATE_VALIDATION",
        "status": "PASS" if reproducible and motion["status"] == "PASS" else "FAIL",
        "ratio_formula": {
            "historical_key": "true_vs_nearest_wrong_distance_ratio",
            "actual_formula": "median(nearest_wrong_rms_distance / true_class_rms_distance)",
            "numerator": "nearest wrong TRAIN-class centroid RMS distance",
            "denominator": "true TRAIN-class centroid RMS distance",
            "better_direction": "higher",
            "original_direction_correct": True,
            "key_name_is_reversed": True,
        },
        "distance_comparability": {
            "classification": "PARTIAL",
            "train_dimensionwise_standardization": True,
            "constant_dimensions_removed": True,
            "distance": "sqrt(mean(squared standardized coordinate differences))",
            "dimension_normalized": True,
            "mechanical_sqrt_dimension_inflation_removed": True,
            "remaining_limit": (
                "feature semantics, redundancy and cross-coordinate correlation differ; "
                "RMS distances are comparable diagnostics but not identical statistical spaces"
            ),
        },
        "independent_recomputation": {
            "status": "PASS" if reproducible else "FAIL",
            "maximum_aggregate_delta": maximum_delta,
            "maximum_dev_signer_delta": maximum_signer_delta,
            "values": recomputed,
        },
        "sparse_dt_motion_audit": motion,
        "final_v2_classification": classification,
        "v2_features_modified": False,
        "model_training_executed": False,
        "protected_test_accessed": False,
    }
    _write_json(v2_root / "representation_v2_gate_validation.json", result)
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v2-root", type=Path, default=DEFAULT_V2_ROOT)
    args = parser.parse_args()
    result = run(args.v2_root.resolve())
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
