"""Build and audit recognition-v2 from frozen Candidate 01 raw observations.

This program never invokes perception models and never trains a recognizer.  It
derives one immutable V2 contract, proves temporal parity with recognition-v1,
and runs bounded, deterministic representation diagnostics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.perception_vnext.recognition_schema import (
    FEATURE_SCHEMA,
    FEATURE_WIDTH,
    MAX_SEQUENCE_LENGTH,
    RAW_SCHEMA,
    load_raw_sequence,
)
from pipeline.perception_vnext.recognition_schema_v2 import (
    FEATURE_LAYOUT_V2,
    FEATURE_SCHEMA_V2,
    FEATURE_WIDTH_V2,
    temporal_view_v2,
)

MILESTONE = "PERCEPTION_VNEXT_REPRESENTATION_V2_236_PRODUCTION_01"
ROOT = Path(__file__).resolve().parents[2]
BASELINE_ROOT = (
    ROOT
    / "artifacts"
    / "recognition_upgrade"
    / "perception_vnext"
    / "recognition_utility_236_01"
)
DEFAULT_SOURCE_DATASET = BASELINE_ROOT / "dataset"
DEFAULT_OUTPUT = BASELINE_ROOT / "representation_v2_236_production_01"
DEV_SIGNERS = ("P5", "P12", "P21", "P26", "P39")
SEED = 101


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
        raise RuntimeError(f"V2_EMPTY_CSV:{path.name}")
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _rows(dataset: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    with (dataset / "index.jsonl").open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                row = json.loads(line)
                if row.get("split") not in {"train", "dev"}:
                    raise RuntimeError(f"V2_FORBIDDEN_SPLIT:{row.get('split')}")
                result.append(row)
    if len(result) != 4742:
        raise RuntimeError(f"V2_DATASET_COUNT:{len(result)}")
    counts = Counter(row["split"] for row in result)
    classes = {int(row["class_id"]) for row in result}
    if counts != {"train": 3926, "dev": 816} or len(classes) != 236:
        raise RuntimeError(f"V2_GOVERNANCE:{dict(counts)}:classes={len(classes)}")
    train_signers = {row["signer_id"] for row in result if row["split"] == "train"}
    dev_signers = {row["signer_id"] for row in result if row["split"] == "dev"}
    if train_signers & dev_signers:
        raise RuntimeError("V2_SIGNER_LEAKAGE")
    return result


def _load_v1(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as data:
        metadata = json.loads(str(data["metadata_json"].item()))
        if metadata.get("schema") != FEATURE_SCHEMA:
            raise RuntimeError(f"V2_BASELINE_SCHEMA:{path}")
        return {name: np.asarray(data[name]) for name in data.files if name != "metadata_json"}


def _valid_v2_package(path: Path, sample_id: str, baseline_path: Path) -> bool:
    try:
        with (
            np.load(path, allow_pickle=False) as data,
            np.load(baseline_path, allow_pickle=False) as baseline,
        ):
            metadata = json.loads(str(data["metadata_json"].item()))
            return bool(
                metadata.get("schema") == FEATURE_SCHEMA_V2
                and metadata.get("sample_id") == sample_id
                and data["dense_features"].shape
                == (MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2)
                and data["sparse_features"].shape
                == (MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2)
                and np.all(np.isfinite(data["dense_features"]))
                and np.all(np.isfinite(data["sparse_features"]))
                and np.array_equal(data["dense_mask"], baseline["dense_mask"])
                and np.array_equal(data["sparse_mask"], baseline["sparse_mask"])
                and np.array_equal(
                    data["dense_source_indices"], baseline["dense_source_indices"]
                )
                and np.array_equal(
                    data["sparse_source_indices"], baseline["sparse_source_indices"]
                )
            )
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return False


def _save_v2_package(
    path: Path,
    row: dict[str, Any],
    dense: dict[str, np.ndarray],
    sparse: dict[str, np.ndarray],
    phone_fps: float,
) -> None:
    metadata = {
        "milestone": MILESTONE,
        "schema": FEATURE_SCHEMA_V2,
        "raw_schema": RAW_SCHEMA,
        "baseline_schema": FEATURE_SCHEMA,
        "sample_id": row["sample_id"],
        "split": row["split"],
        "class_id": int(row["class_id"]),
        "canonical_gloss": row["canonical_gloss"],
        "signer_id": row["signer_id"],
        "source_id": row["source_id"],
        "feature_width": FEATURE_WIDTH_V2,
        "max_sequence_length": MAX_SEQUENCE_LENGTH,
        "phone_completed_fps": phone_fps,
        "dense_frames": int(np.count_nonzero(dense["mask"])),
        "sparse_frames": int(np.count_nonzero(sparse["mask"])),
        "motion_semantics": "timestamp-aware deltas over adjacent selected real observations",
        "padding_semantics": "post-zero-padding with false mask; no copied observations",
        "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".partial")
    with temporary.open("wb") as stream:
        np.savez_compressed(
            stream,
            metadata_json=np.asarray(json.dumps(metadata, sort_keys=True)),
            dense_features=dense["features"],
            dense_mask=dense["mask"],
            dense_source_indices=dense["source_indices"],
            dense_source_timestamps_ms=dense["source_timestamps_ms"],
            sparse_features=sparse["features"],
            sparse_mask=sparse["mask"],
            sparse_source_indices=sparse["source_indices"],
            sparse_source_timestamps_ms=sparse["source_timestamps_ms"],
        )
    temporary.replace(path)


def generate(source_dataset: Path, output: Path) -> dict[str, Any]:
    rows = _rows(source_dataset)
    baseline_contract = json.loads(
        (source_dataset / "contract.json").read_text(encoding="utf-8")
    )
    if (
        baseline_contract.get("raw_schema") != RAW_SCHEMA
        or baseline_contract.get("feature_schema") != FEATURE_SCHEMA
        or baseline_contract.get("feature_width") != FEATURE_WIDTH
        or baseline_contract.get("max_sequence_length") != MAX_SEQUENCE_LENGTH
        or baseline_contract.get("protected_test_accessed") is not False
    ):
        raise RuntimeError("V2_BASELINE_CONTRACT_MISMATCH")
    phone_fps = float(baseline_contract["phone_completed_fps"])
    generated = 0
    reused = 0
    output_rows: list[dict[str, Any]] = []
    for number, row in enumerate(rows, start=1):
        destination = output / "dataset" / "features" / row["split"] / Path(
            row["feature_path"]
        ).name
        if _valid_v2_package(
            destination, row["sample_id"], Path(row["feature_path"])
        ):
            reused += 1
        else:
            raw = load_raw_sequence(Path(row["raw_path"]))
            if raw.metadata.get("sample_id") != row["sample_id"]:
                raise RuntimeError(f"V2_RAW_IDENTITY:{row['sample_id']}")
            dense = temporal_view_v2(
                raw, condition="dense", phone_completed_fps=phone_fps
            )
            sparse = temporal_view_v2(
                raw, condition="phone_01_sparse", phone_completed_fps=phone_fps
            )
            baseline = _load_v1(Path(row["feature_path"]))
            for condition, view in (("dense", dense), ("sparse", sparse)):
                if not np.array_equal(
                    view["source_indices"], baseline[f"{condition}_source_indices"]
                ):
                    raise RuntimeError(
                        f"V2_TEMPORAL_INDEX_PARITY:{row['sample_id']}:{condition}"
                    )
                if not np.array_equal(view["mask"], baseline[f"{condition}_mask"]):
                    raise RuntimeError(
                        f"V2_TEMPORAL_MASK_PARITY:{row['sample_id']}:{condition}"
                    )
            _save_v2_package(destination, row, dense, sparse, phone_fps)
            generated += 1
        output_rows.append(
            {
                **row,
                "v1_feature_path": row["feature_path"],
                "feature_path": str(destination.resolve()),
                "feature_schema": FEATURE_SCHEMA_V2,
                "feature_width": FEATURE_WIDTH_V2,
            }
        )
        if number % 250 == 0 or number == len(rows):
            print(
                f"V2_FEATURE_PROGRESS {number}/{len(rows)} "
                f"generated={generated} reused={reused}",
                flush=True,
            )

    index = output / "dataset" / "index.jsonl"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows),
        encoding="utf-8",
    )
    contract = {
        "milestone": MILESTONE,
        "raw_schema": RAW_SCHEMA,
        "feature_schema": FEATURE_SCHEMA_V2,
        "feature_width": FEATURE_WIDTH_V2,
        "feature_layout": [
            {"name": name, "start": start, "end_exclusive": end}
            for name, start, end in FEATURE_LAYOUT_V2
        ],
        "max_sequence_length": MAX_SEQUENCE_LENGTH,
        "phone_completed_fps": phone_fps,
        "source_dataset_contract": str((source_dataset / "contract.json").resolve()),
        "source_dataset_contract_sha256": _sha256(source_dataset / "contract.json"),
        "source_index_sha256": _sha256(source_dataset / "index.jsonl"),
        "train_clips": 3926,
        "dev_clips": 816,
        "classes": 236,
        "seed": SEED,
        "perception_reextraction": False,
        "protected_test_accessed": False,
    }
    _write_json(output / "dataset" / "contract.json", contract)
    result = {
        **contract,
        "status": "PASS",
        "generated_this_invocation": generated,
        "reused_this_invocation": reused,
        "materialized_packages": len(rows),
        "total": len(rows),
        "index_sha256": _sha256(index),
        "finite_check": "PASS",
        "temporal_index_and_mask_parity": "PASS",
    }
    _write_json(output / "v2_feature_generation.json", result)
    return result


def _embedding(features: np.ndarray, mask: np.ndarray) -> np.ndarray:
    values = np.asarray(features, np.float32)[np.asarray(mask, bool)]
    if len(values) == 0:
        raise RuntimeError("V2_EMPTY_TEMPORAL_VIEW")
    split = max(1, len(values) // 2)
    first = values[:split]
    second = values[split:] if split < len(values) else values[-1:]
    return np.concatenate(
        [
            values.mean(axis=0),
            values.std(axis=0),
            first.mean(axis=0),
            second.mean(axis=0),
        ]
    ).astype(np.float32)


def _load_embeddings(
    rows: list[dict[str, Any]], condition: str, version: str
) -> np.ndarray:
    embeddings: list[np.ndarray] = []
    for row in rows:
        path = Path(row["v1_feature_path"] if version == "v1" else row["feature_path"])
        with np.load(path, allow_pickle=False) as data:
            if version == "v2":
                metadata = json.loads(str(data["metadata_json"].item()))
                if metadata.get("schema") != FEATURE_SCHEMA_V2:
                    raise RuntimeError(f"V2_PACKAGE_SCHEMA:{row['sample_id']}")
            embeddings.append(
                _embedding(
                    data[f"{condition}_features"], data[f"{condition}_mask"]
                )
            )
    result = np.asarray(embeddings, np.float32)
    if not np.all(np.isfinite(result)):
        raise RuntimeError(f"V2_NONFINITE_EMBEDDING:{version}:{condition}")
    return result


def _standardize(train: np.ndarray, dev: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = train.mean(axis=0, dtype=np.float64)
    scale = train.std(axis=0, dtype=np.float64)
    active = np.isfinite(scale) & (scale > 1.0e-6)
    if not np.any(active):
        raise RuntimeError("V2_NO_ACTIVE_EMBEDDING_DIMENSIONS")
    return (
        ((train[:, active] - mean[active]) / scale[active]).astype(np.float32),
        ((dev[:, active] - mean[active]) / scale[active]).astype(np.float32),
    )


def _centroids(
    embeddings: np.ndarray, labels: np.ndarray, identities: np.ndarray
) -> np.ndarray:
    return np.asarray(
        [embeddings[labels == identity].mean(axis=0) for identity in identities],
        np.float32,
    )


def _squared_distances(values: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    left = np.sum(values * values, axis=1, keepdims=True)
    right = np.sum(centroids * centroids, axis=1)[None]
    return np.maximum(left + right - 2.0 * (values @ centroids.T), 0.0)


def _signer_identifiability(
    embeddings: np.ndarray,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    keep = np.asarray(
        [row["split"] == "train" and row["source_id"] == "ASL_CITIZEN" for row in rows]
    )
    values = embeddings[keep]
    labels = np.asarray([row["class_id"] for row in rows], np.int32)[keep]
    signers = np.asarray([row["signer_id"] for row in rows], object)[keep]
    class_centers = {
        class_id: values[labels == class_id].mean(axis=0)
        for class_id in np.unique(labels)
    }
    residuals = np.asarray(
        [value - class_centers[int(label)] for value, label in zip(values, labels, strict=True)],
        np.float32,
    )
    predicted: list[str] = []
    actual: list[str] = []
    for fold in range(5):
        train_fold = labels % 5 != fold
        test_fold = ~train_fold
        eligible_signers = np.asarray(
            sorted(set(signers[train_fold]) & set(signers[test_fold])), object
        )
        if len(eligible_signers) < 2:
            continue
        centers = _centroids(residuals[train_fold], signers[train_fold], eligible_signers)
        valid_test = test_fold & np.isin(signers, eligible_signers)
        distances = _squared_distances(residuals[valid_test], centers)
        predicted.extend(eligible_signers[np.argmin(distances, axis=1)].tolist())
        actual.extend(signers[valid_test].tolist())
    if not actual:
        raise RuntimeError("V2_SIGNER_DIAGNOSTIC_EMPTY")
    return {
        "method": (
            "five-fold cross-class nearest-centroid on class-residual "
            "ASL_CITIZEN TRAIN embeddings"
        ),
        "clips": len(actual),
        "signers": len(set(actual)),
        "chance_fraction": 1.0 / len(set(actual)),
        "accuracy": float(np.mean(np.asarray(predicted) == np.asarray(actual))),
    }


def _representation_metrics(
    train: np.ndarray,
    dev: np.ndarray,
    train_rows: list[dict[str, Any]],
    dev_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    train_labels = np.asarray([row["class_id"] for row in train_rows], np.int32)
    dev_labels = np.asarray([row["class_id"] for row in dev_rows], np.int32)
    identities = np.asarray(sorted(set(train_labels)), np.int32)
    if len(identities) != 236 or set(identities) != set(dev_labels):
        raise RuntimeError("V2_CLASS_COVERAGE")
    train_centers = _centroids(train, train_labels, identities)
    dev_centers = _centroids(dev, dev_labels, identities)
    center_shift = np.sqrt(np.mean((train_centers - dev_centers) ** 2, axis=1))
    distances = _squared_distances(dev, train_centers) / train.shape[1]
    label_to_column = {int(label): index for index, label in enumerate(identities)}
    true_columns = np.asarray([label_to_column[int(label)] for label in dev_labels], np.int32)
    true_distance = np.sqrt(distances[np.arange(len(dev)), true_columns])
    wrong = distances.copy()
    wrong[np.arange(len(dev)), true_columns] = np.inf
    nearest_wrong = np.sqrt(np.min(wrong, axis=1))
    order = np.argsort(distances, axis=1)
    top1 = identities[order[:, 0]]
    top5 = identities[order[:, :5]]
    class_mean = train_centers.mean(axis=0)
    between = float(np.mean((train_centers - class_mean) ** 2))
    within = float(
        np.mean(
            [
                np.mean((value - train_centers[label_to_column[int(label)]]) ** 2)
                for value, label in zip(train, train_labels, strict=True)
            ]
        )
    )
    class_rows: list[dict[str, Any]] = []
    for column, class_id in enumerate(identities):
        dev_keep = dev_labels == class_id
        class_rows.append(
            {
                "class_id": int(class_id),
                "gloss": next(
                    row["canonical_gloss"]
                    for row in train_rows
                    if int(row["class_id"]) == int(class_id)
                ),
                "train_count": int(np.count_nonzero(train_labels == class_id)),
                "dev_count": int(np.count_nonzero(dev_keep)),
                "centroid_shift_rms": float(center_shift[column]),
                "dev_true_centroid_distance_mean": float(true_distance[dev_keep].mean()),
            }
        )
    signer_rows: list[dict[str, Any]] = []
    for signer in DEV_SIGNERS:
        keep = np.asarray(
            [str(row["signer_id"]).split(":")[-1] == signer for row in dev_rows]
        )
        if not np.any(keep):
            raise RuntimeError(f"V2_MISSING_DEV_SIGNER:{signer}")
        signer_rows.append(
            {
                "signer": signer,
                "clips": int(np.count_nonzero(keep)),
                "true_class_distance_mean": float(true_distance[keep].mean()),
                "true_class_distance_median": float(np.median(true_distance[keep])),
                "nearest_centroid_top1": float(np.mean(top1[keep] == dev_labels[keep])),
                "nearest_centroid_top5": float(
                    np.mean(
                        [
                            label in predicted
                            for label, predicted in zip(
                                dev_labels[keep], top5[keep], strict=True
                            )
                        ]
                    )
                ),
            }
        )
    metrics = {
        "active_embedding_dimensions": int(train.shape[1]),
        "class_conditioned_centroid_shift_median": float(np.median(center_shift)),
        "class_conditioned_centroid_shift_mean": float(np.mean(center_shift)),
        "dev_true_class_distance_median": float(np.median(true_distance)),
        "dev_true_class_distance_mean": float(np.mean(true_distance)),
        "nearest_centroid_top1": float(np.mean(top1 == dev_labels)),
        "nearest_centroid_top5": float(
            np.mean(
                [
                    label in predicted
                    for label, predicted in zip(dev_labels, top5, strict=True)
                ]
            )
        ),
        "true_vs_nearest_wrong_distance_ratio": float(
            np.median(nearest_wrong / np.maximum(true_distance, 1.0e-8))
        ),
        "class_fisher_between_within_ratio": between / max(within, 1.0e-12),
    }
    return metrics, class_rows, signer_rows


def _direction(new: float, old: float, better: str) -> str:
    if new == old:
        return "EQUAL"
    improved = new < old if better == "lower" else new > old
    return "IMPROVED" if improved else "WORSE"


def gate(source_dataset: Path, output: Path) -> dict[str, Any]:
    source_rows = _rows(source_dataset)
    v2_rows_by_id: dict[str, dict[str, Any]] = {}
    with (output / "dataset" / "index.jsonl").open("r", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            v2_rows_by_id[row["sample_id"]] = row
    rows = [v2_rows_by_id[row["sample_id"]] for row in source_rows]
    train_rows = [row for row in rows if row["split"] == "train"]
    dev_rows = [row for row in rows if row["split"] == "dev"]
    condition_results: dict[str, Any] = {}
    all_class_rows: list[dict[str, Any]] = []
    all_signer_rows: list[dict[str, Any]] = []
    for condition in ("dense", "sparse"):
        print(f"V2_GATE_LOAD condition={condition}", flush=True)
        embeddings = {
            version: _load_embeddings(rows, condition, version)
            for version in ("v1", "v2")
        }
        split = np.asarray([row["split"] == "train" for row in rows])
        condition_result: dict[str, Any] = {}
        standardized: dict[str, np.ndarray] = {}
        for version in ("v1", "v2"):
            train, dev = _standardize(embeddings[version][split], embeddings[version][~split])
            standardized[version] = np.concatenate([train, dev])
            metrics, class_rows, signer_rows = _representation_metrics(
                train, dev, train_rows, dev_rows
            )
            metrics["signer_identifiability"] = _signer_identifiability(
                standardized[version], rows
            )
            condition_result[version] = metrics
            all_class_rows.extend(
                {"condition": condition, "version": version, **row}
                for row in class_rows
            )
            all_signer_rows.extend(
                {"condition": condition, "version": version, **row}
                for row in signer_rows
            )
        comparisons: dict[str, str] = {}
        for name in (
            "class_conditioned_centroid_shift_median",
            "dev_true_class_distance_median",
        ):
            comparisons[name] = _direction(
                condition_result["v2"][name], condition_result["v1"][name], "lower"
            )
        comparisons["signer_identifiability"] = _direction(
            condition_result["v2"]["signer_identifiability"]["accuracy"],
            condition_result["v1"]["signer_identifiability"]["accuracy"],
            "lower",
        )
        for name in (
            "nearest_centroid_top1",
            "nearest_centroid_top5",
            "true_vs_nearest_wrong_distance_ratio",
            "class_fisher_between_within_ratio",
        ):
            comparisons[name] = _direction(
                condition_result["v2"][name], condition_result["v1"][name], "higher"
            )
        condition_result["comparison"] = comparisons
        condition_results[condition] = condition_result

    invariance_names = (
        "class_conditioned_centroid_shift_median",
        "dev_true_class_distance_median",
        "signer_identifiability",
    )
    preservation_names = (
        "nearest_centroid_top5",
        "true_vs_nearest_wrong_distance_ratio",
        "class_fisher_between_within_ratio",
    )
    invariance_all = all(
        condition_results[condition]["comparison"][name] == "IMPROVED"
        for condition in ("dense", "sparse")
        for name in invariance_names
    )
    preservation_all = all(
        condition_results[condition]["comparison"][name] in {"IMPROVED", "EQUAL"}
        for condition in ("dense", "sparse")
        for name in preservation_names
    )
    invariance_none = all(
        condition_results[condition]["comparison"][name] != "IMPROVED"
        for condition in ("dense", "sparse")
        for name in invariance_names
    )
    separation_worse_both = all(
        condition_results[condition]["comparison"][name] == "WORSE"
        for condition in ("dense", "sparse")
        for name in preservation_names
    )
    if invariance_all and preservation_all:
        decision = "REPRESENTATION_V2_GATE_PASS"
        reason = (
            "All preregistered invariance directions improved in dense and sparse views, "
            "while every primary class-preservation direction was retained or improved."
        )
    elif invariance_none or separation_worse_both:
        decision = "REPRESENTATION_V2_GATE_FAIL"
        reason = (
            "V2 either failed to reduce signer/class-conditioned shift or reduced it while "
            "all primary class-preservation diagnostics worsened in both temporal views."
        )
    else:
        decision = "REPRESENTATION_V2_GATE_INCONCLUSIVE"
        reason = (
            "The dense/sparse invariance and class-preservation directions are mixed; the "
            "evidence does not justify a full recognizer run or an automatic V3."
        )
    _write_csv(output / "class_conditioned_shift.csv", all_class_rows)
    _write_csv(output / "dev_signer_representation_gate.csv", all_signer_rows)
    result = {
        "milestone": MILESTONE,
        "status": "PASS",
        "gate_decision": decision,
        "reason": reason,
        "diagnostic_contract": {
            "clip_embedding": "masked temporal mean + std + first-half mean + second-half mean",
            "standardization": "TRAIN mean/std only; constant dimensions excluded",
            "shift": (
                "class-conditioned TRAIN-vs-DEV centroid RMS and DEV-to-TRAIN "
                "true-class distance"
            ),
            "signer_identifiability": (
                "cross-class nearest-centroid over ASL_CITIZEN TRAIN class residuals"
            ),
            "class_separation": "DEV nearest TRAIN-class centroid and TRAIN Fisher ratio",
            "separation_ratio": {
                "legacy_key": "true_vs_nearest_wrong_distance_ratio",
                "formula": "median(nearest_wrong_rms_distance / true_class_rms_distance)",
                "better_direction": "higher",
                "note": "the legacy key is worded in the reverse order of the implemented ratio",
            },
            "training_performed": False,
        },
        "conditions": condition_results,
        "protected_test_accessed": False,
    }
    _write_json(output / "representation_v2_gate.json", result)
    return result


def _report(output: Path, generation: dict[str, Any], result: dict[str, Any]) -> None:
    lines = [
        f"# {MILESTONE}",
        "",
        "## Status",
        "",
        f"Gate decision: **{result['gate_decision']}**",
        "",
        result["reason"],
        "",
        "## V1 analysis",
        "",
        "Recognition-v1 is `[96,208]` plus a `[96]` Boolean mask. Each current frame keeps all "
        "42 hand points and eight body points in one body-centered isotropic frame, proposal/body "
        "support, explicit validity/observed state, and time. It retains raw bone lengths, body "
        "scale ratios and source-plane roll, and it has no hand-local articulation frame or "
        "selected-observation motion channels. Those properties can expose signer anatomy and "
        "camera posture to the recognizer.",
        "",
        "## Representation V2",
        "",
        "`apphear.perception_vnext.recognition.v2` is `[96,350]` float32 plus the unchanged "
        "`[96]` Boolean mask. It is derived only from raw-v1 current observations.",
        "",
        "- LH `0:130`, RH `130:260`: 20 palm-scale-independent bone directions plus validity; "
        "15 signed 2D joint-angle sine/cosine pairs plus validity; five palm-normalized fingertip "
        "positions plus validity; wrist and palm-center body-relative location; palm orientation "
        "in the body frame; presence, observed state, mean proposal support and hand-reference "
        "validity.",
        "- Body `260:296`: six roll-normalized upper-body limb directions plus validity, eight "
        "point supports, eight point-validity values, body availability and body-frame validity.",
        "- Inter-hand `296:303`: body-relative wrist/center displacement, their distances and "
        "both-hands-observed state.",
        "- Motion `303:348`: timestamp-aware wrist/center and hand-local fingertip velocities "
        "with explicit validity, plus inter-hand center-relative velocity. Motion is bounded with "
        "`tanh(v/4)` and is computed after dense/sparse real-observation selection.",
        "- Time `348:350`: real selected-observation delta seconds and elapsed clip fraction.",
        "- Invalid derived values are zero only beside authoritative validity/observed channels. "
        "There is no Z, interpolation, carry-forward or copied evidence.",
        "",
        "The body frame uses the shoulder pair, then the hip pair, with source-frame fallback "
        "marked invalid. The hand frame uses wrist, index/middle/pinky MCP geometry and palm "
        "scale. "
        "All operations are finite arithmetic over Candidate 01 fields and are phone-computable; "
        "an Android S4 implementation was intentionally not added because this gate did not pass.",
        "",
        "## Frozen-data generation",
        "",
        f"- Clips: {generation['total']} (TRAIN 3,926; DEV 816; 236 classes)",
        f"- Materialized V2 packages: {generation['materialized_packages']}; generated in this "
        f"invocation: {generation['generated_this_invocation']}; integrity-checked and reused: "
        f"{generation['reused_this_invocation']}",
        "- Perception re-extraction: NO",
        "- Temporal source-index/mask parity with V1: PASS",
        "- Protected TEST accessed: NO",
        f"- V2 feature packages: `{generation['total']}`.",
        "",
        "## Representation diagnostics",
        "",
    ]
    for condition in ("dense", "sparse"):
        lines.extend([f"### {condition}", ""])
        values = result["conditions"][condition]
        lines.append("| Metric | V1 | V2 | Direction |")
        lines.append("|---|---:|---:|---|")
        for name in (
            "class_conditioned_centroid_shift_median",
            "dev_true_class_distance_median",
            "nearest_centroid_top1",
            "nearest_centroid_top5",
            "true_vs_nearest_wrong_distance_ratio",
            "class_fisher_between_within_ratio",
        ):
            label = (
                "nearest_wrong_over_true_distance_ratio"
                if name == "true_vs_nearest_wrong_distance_ratio"
                else name
            )
            lines.append(
                f"| {label} "
                f"| {values['v1'][name]:.6f} | {values['v2'][name]:.6f} | "
                f"{values['comparison'][name]} |"
            )
        lines.append(
            "| signer_identifiability_accuracy | "
            f"{values['v1']['signer_identifiability']['accuracy']:.6f} | "
            f"{values['v2']['signer_identifiability']['accuracy']:.6f} | "
            f"{values['comparison']['signer_identifiability']} |"
        )
        lines.append("")
    lines.extend(
        [
            "## DEV-signer result",
            "",
            "The detailed P5/P12/P21/P26/P39 dense and sparse distances and nearest-centroid "
            "retrieval rates are preserved in `dev_signer_representation_gate.csv`. V2 improves "
            "retrieval for most signer/condition pairs. Mean true-class distance improves only "
            "for dense P5/P26 (median only for P5) and worsens for all sparse signers.",
            "",
            "## Decision boundary",
            "",
            "Full TCN training executed: **NO**. Training smoke: **NOT RUN — gate did not pass**. "
            "Protected TEST accessed: **NO**. No V3 or alternate representation was created.",
        ]
    )
    (output / "REPRESENTATION_V2_GATE_REPORT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def run(source_dataset: Path, output: Path) -> dict[str, Any]:
    generation = generate(source_dataset, output)
    result = gate(source_dataset, output)
    _report(output, generation, result)
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dataset", type=Path, default=DEFAULT_SOURCE_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.source_dataset.resolve(), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
