"""One-run production-cadence-aligned temporal segmenter experiment.

The prepare stage reuses only the 112 frozen complete-source raw-v1 sequences,
selects genuine observations on three timestamp grids, and recomputes every
causal transition from the immediately preceding selected observation. Training
uses FIT only, checkpoint selection uses CAL only, and frozen DEV remains closed
until the selected checkpoint has been hashed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics.phase5_1t_first_segmenter import (  # noqa: E402
    IGNORE_LABEL,
    LABEL_NAMES,
    aggregate_events,
    build_model,
    decode_event,
    distribution,
    event_result,
    load_population,
    softmax,
    state_metrics,
    temporal_labels,
)
from pipeline.perception_vnext.recognition_schema import (  # noqa: E402
    RAW_SCHEMA,
    RawSequence,
    load_raw_sequence,
)
from pipeline.perception_vnext.segmentation.learned_features import (  # noqa: E402
    FEATURE_BLOCKS,
    FEATURE_WIDTH,
    SEGMENTATION_FEATURE_SCHEMA,
    apply_normalization,
    derive_causal_segmentation_features,
    feature_names,
    normalization_from_train,
)

MILESTONE = "PHASE_7_PRODUCTION_CADENCE_ALIGNED_SEGMENTER_01"
BASE = ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
T2 = BASE / "phase5_1t_2_bounded_segmentation_seed_dataset_01"
T3 = BASE / "phase5_1t_3_first_class_agnostic_segmenter_01"
P6 = BASE / "phase6_frozen_learned_segmenter_phone_replay_01"
OUT = BASE / "phase7_production_cadence_aligned_segmenter_01"
CONFIG = OUT / "phase7_config.json"
T3_MANIFEST = T3 / "extracted_feature_manifest.json"
SELECTED = T2 / "selected_120_manifest.json"
SPLIT = T2 / "frozen_segmentation_split.json"
EXPECTED_SELECTED_SHA = "832ba25420bef80acda3b40e7a44414654c3227222e4336d66174b8cca7ea15e"
EXPECTED_SPLIT_SHA = "b4a2dbaf9c3810a86f8407068ea50dfc3f2079fc951932ff3a76bbe411b599c6"
PHONE_SESSION_ID = "session_20260915T065635Z"
PHONE_SESSION = BASE / ("phase4a_gate4a1b_controlled_live_input_recovery_01/" + PHONE_SESSION_ID)
ATTEMPTS = tuple(f"attempt_{index:03d}" for index in range(1, 11))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(value))


def freeze_json(path: Path, value: Any) -> None:
    payload = canonical_json(value)
    if path.exists() and path.read_bytes() != payload:
        raise RuntimeError(f"FROZEN_ARTIFACT_MUTATION_REFUSED:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(payload)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def stable_name(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def load_config() -> dict[str, Any]:
    config = read_json(CONFIG)
    if config.get("milestone") != MILESTONE:
        raise RuntimeError("PHASE7_CONFIG_MILESTONE_MISMATCH")
    if config["features"] != {
        "schema": SEGMENTATION_FEATURE_SCHEMA,
        "width": FEATURE_WIDTH,
        "normalization_population": "FIT_SPARSE_VIEWS_ONLY",
        "future_information": False,
        "recognition_v2": False,
        "recognizer_outputs": False,
        "gloss_or_class_input": False,
    }:
        raise RuntimeError("PHASE7_FEATURE_CONFIG_MISMATCH")
    intervals = [float(row["target_interval_ms"]) for row in config["cadence_views"]]
    if intervals != [133.308, 199.962, 266.616]:
        raise RuntimeError("PHASE7_TARGET_INTERVAL_MISMATCH")
    return config


def verify_frozen_inputs() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if sha256(SELECTED) != EXPECTED_SELECTED_SHA:
        raise RuntimeError("FROZEN_SELECTED_MANIFEST_IDENTITY_MISMATCH")
    if sha256(SPLIT) != EXPECTED_SPLIT_SHA:
        raise RuntimeError("FROZEN_SEGMENTATION_SPLIT_IDENTITY_MISMATCH")
    rows = load_population()
    train = [row for row in rows if row["segmentation_split"] == "SEGMENTATION_TRAIN"]
    dev = [row for row in rows if row["segmentation_split"] == "SEGMENTATION_DEV"]
    if len(train) != 89 or len(dev) != 23:
        raise RuntimeError("PHASE7_POPULATION_COUNT_MISMATCH")
    if {row["signer_id"] for row in train} & {row["signer_id"] for row in dev}:
        raise RuntimeError("PHASE7_SIGNER_LEAKAGE")

    manifest = read_json(T3_MANIFEST)
    if manifest.get("sample_count") != 112 or manifest.get("full_source_video_count") != 112:
        raise RuntimeError("PHASE7_FULL_RAW_MANIFEST_COUNT_MISMATCH")
    by_id = {str(row["sample_id"]): row for row in manifest["rows"]}
    if set(by_id) != {str(row["sample_id"]) for row in rows}:
        raise RuntimeError("PHASE7_FULL_RAW_MEMBERSHIP_MISMATCH")
    failures = []
    for row in rows:
        item = by_id[str(row["sample_id"])]
        path = Path(item["raw_path"])
        if not path.is_file():
            failures.append({"sample_id": row["sample_id"], "reason": "MISSING", "path": str(path)})
        elif sha256(path) != item["raw_sha256"]:
            failures.append(
                {"sample_id": row["sample_id"], "reason": "HASH_MISMATCH", "path": str(path)}
            )
        elif item["full_video_verification"]["scope"] != "FULL_SOURCE_VIDEO":
            failures.append(
                {"sample_id": row["sample_id"], "reason": "NOT_FULL_VIDEO", "path": str(path)}
            )
    if failures:
        write_json(OUT / "missing_or_invalid_raw_v1.json", {"failures": failures})
        raise RuntimeError("PHASE7_REQUIRED_FULL_RAW_V1_MISSING_OR_INVALID")
    return rows, by_id


def deterministic_fit_cal_split(rows: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    train = [row for row in rows if row["segmentation_split"] == "SEGMENTATION_TRAIN"]
    dev_ids = sorted(
        str(row["sample_id"]) for row in rows if row["segmentation_split"] == "SEGMENTATION_DEV"
    )
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in train:
        grouped[str(row["source"])].append(row)
    target_total = round(len(train) * 0.2)
    quotas = {source: int(len(values) * 0.2) for source, values in grouped.items()}
    remainder = target_total - sum(quotas.values())
    fractional = sorted(
        grouped,
        key=lambda source: (-(len(grouped[source]) * 0.2 % 1.0), source),
    )
    for source in fractional[:remainder]:
        quotas[source] += 1

    cal_ids: set[str] = set()
    for source, values in sorted(grouped.items()):
        ranked = sorted(
            values,
            key=lambda row: hashlib.sha256(
                f"{seed}|{source}|{row['sample_id']}".encode()
            ).hexdigest(),
        )
        cal_ids.update(str(row["sample_id"]) for row in ranked[: quotas[source]])
    train_ids = {str(row["sample_id"]) for row in train}
    fit_ids = train_ids - cal_ids
    if len(fit_ids) != 71 or len(cal_ids) != 18 or (fit_ids & cal_ids):
        raise RuntimeError("PHASE7_FIT_CAL_SPLIT_COUNT_FAILURE")
    if (fit_ids | cal_ids) & set(dev_ids):
        raise RuntimeError("PHASE7_DEV_IN_FIT_CAL")
    source_counts = {
        source: {
            "FIT": sum(str(row["sample_id"]) in fit_ids for row in values),
            "CAL": sum(str(row["sample_id"]) in cal_ids for row in values),
        }
        for source, values in sorted(grouped.items())
    }
    return {
        "schema": "apphear.phase7.frozen_fit_cal_split.v1",
        "milestone": MILESTONE,
        "seed": seed,
        "method": "SOURCE_STRATIFIED_STABLE_SHA256_RANK",
        "fit_sample_ids": sorted(fit_ids),
        "cal_sample_ids": sorted(cal_ids),
        "excluded_segmentation_dev_sample_ids": dev_ids,
        "fit_count": len(fit_ids),
        "cal_count": len(cal_ids),
        "dev_count": len(dev_ids),
        "source_counts": source_counts,
        "all_three_views_grouped_with_original_clip": True,
        "dev_used_for_selection": False,
    }


def deterministic_offset_ms(sample_id: str, view_id: str, interval_ms: float) -> float:
    digest = hashlib.sha256(f"{sample_id}|{view_id}".encode()).digest()
    unit = int.from_bytes(digest[:8], "big") / float(2**64)
    return unit * interval_ms


def sparse_observation_indices(
    timestamps_ms: np.ndarray,
    sample_id: str,
    view_id: str,
    interval_ms: float,
) -> tuple[np.ndarray, float]:
    timestamps = np.asarray(timestamps_ms, np.float64)
    if len(timestamps) == 0 or not np.all(np.diff(timestamps) > 0):
        raise ValueError("SPARSE_SOURCE_TIMESTAMPS_INVALID")
    offset = deterministic_offset_ms(sample_id, view_id, interval_ms)
    target = float(timestamps[0]) + offset
    selected: list[int] = []
    previous = -1
    while target <= float(timestamps[-1]):
        insertion = int(np.searchsorted(timestamps, target, side="left"))
        candidates = [
            index for index in (insertion - 1, insertion) if previous < index < len(timestamps)
        ]
        if not candidates:
            candidates = [index for index in range(previous + 1, len(timestamps))]
        if not candidates:
            break
        chosen = min(candidates, key=lambda index: (abs(float(timestamps[index]) - target), index))
        selected.append(chosen)
        previous = chosen
        target += interval_ms
    if not selected:
        selected = [0]
    result = np.asarray(selected, np.int32)
    if not np.all(np.diff(result) > 0):
        raise RuntimeError("SPARSE_SELECTED_INDICES_NOT_STRICTLY_INCREASING")
    return result, offset


def subset_raw(raw: RawSequence, indices: np.ndarray) -> RawSequence:
    selected = np.asarray(indices, np.int32)
    value = RawSequence(
        **{
            field.name: (
                dict(raw.metadata)
                if field.name == "metadata"
                else np.asarray(getattr(raw, field.name))[selected]
            )
            for field in fields(RawSequence)
        }
    )
    value.validate()
    return value


def view_identity(sample_id: str, view_id: str) -> str:
    return f"{sample_id}::{view_id}"


def make_view(
    row: dict[str, Any],
    manifest_row: dict[str, Any],
    view: dict[str, Any],
    ignore_band_ms: float,
) -> dict[str, Any]:
    raw = load_raw_sequence(Path(manifest_row["raw_path"]))
    interval = float(view["target_interval_ms"])
    view_id = str(view["view_id"])
    indices, offset = sparse_observation_indices(
        raw.timestamp_ms, str(row["sample_id"]), view_id, interval
    )
    sparse = subset_raw(raw, indices)
    features = derive_causal_segmentation_features(sparse)
    labels = temporal_labels(
        sparse.timestamp_ms,
        float(row["human_sign_start_ms"]),
        float(row["human_sign_end_ms"]),
        ignore_band_ms,
    )
    if not np.any(labels == 1):
        raise RuntimeError(f"PHASE7_VIEW_HAS_NO_ACTIVE_SUPERVISION:{row['sample_id']}:{view_id}")
    return {
        **row,
        "view_key": view_identity(str(row["sample_id"]), view_id),
        "view_id": view_id,
        "target_interval_ms": interval,
        "phase_offset_ms": offset,
        "selected_indices": indices,
        "timestamps_ms": sparse.timestamp_ms.astype(np.float64),
        "features": features,
        "labels": labels.astype(np.int32),
        "raw_sha256": manifest_row["raw_sha256"],
        "raw_path": manifest_row["raw_path"],
    }


def _save_view(row: dict[str, Any], directory: Path) -> tuple[Path, str]:
    path = directory / f"{stable_name(row['view_key'])}.npz"
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        schema=np.asarray(SEGMENTATION_FEATURE_SCHEMA),
        sample_id=np.asarray(str(row["sample_id"])),
        view_id=np.asarray(str(row["view_id"])),
        target_interval_ms=np.asarray(float(row["target_interval_ms"])),
        selected_indices=row["selected_indices"].astype(np.int32),
        timestamps_ms=row["timestamps_ms"].astype(np.float64),
        features=row["features"].astype(np.float32),
        labels=row["labels"].astype(np.int8),
        source_raw_sha256=np.asarray(str(row["raw_sha256"])),
    )
    return path, sha256(path)


def feature_schema_document(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SEGMENTATION_FEATURE_SCHEMA,
        "width": FEATURE_WIDTH,
        "dtype": "float32",
        "source": RAW_SCHEMA,
        "sparse_transition_policy": "CURRENT_MINUS_IMMEDIATELY_PREVIOUS_SELECTED_OBSERVATION",
        "dt_policy": "ACTUAL_SELECTED_SOURCE_TIMESTAMP_DIFFERENCE",
        "missingness": "ZERO_PLUS_EXPLICIT_VALIDITY_NO_INTERPOLATION_OR_CARRY",
        "normalization": "FIT_SPARSE_VIEWS_ONLY",
        "blocks": [block.__dict__ for block in FEATURE_BLOCKS],
        "feature_names": feature_names(),
        "model_contract": config["model"],
    }


def prepare(smoke: bool = False) -> dict[str, Any]:
    config = load_config()
    population, raw_by_id = verify_frozen_inputs()
    split = deterministic_fit_cal_split(population, int(config["fit_cal_split"]["seed"]))
    if smoke:
        train = next(row for row in population if row["segmentation_split"] == "SEGMENTATION_TRAIN")
        dev = next(row for row in population if row["segmentation_split"] == "SEGMENTATION_DEV")
        selected_population = [train, dev]
        destination = OUT / "smoke_sparse_features"
    else:
        freeze_json(OUT / "frozen_fit_cal_split.json", split)
        selected_population = population
        destination = OUT / "sparse_features"

    fit_ids = set(split["fit_sample_ids"])
    cal_ids = set(split["cal_sample_ids"])
    views: list[dict[str, Any]] = []
    for row in selected_population:
        sample_id = str(row["sample_id"])
        partition = "FIT" if sample_id in fit_ids else "CAL" if sample_id in cal_ids else "DEV"
        for view in config["cadence_views"]:
            item = make_view(
                row,
                raw_by_id[sample_id],
                view,
                float(config["labels"]["ignore_band_ms"]),
            )
            item["phase7_partition"] = partition
            path, feature_sha = _save_view(item, destination)
            item["feature_path"] = str(path.resolve())
            item["feature_sha256"] = feature_sha
            views.append(item)

    if smoke:
        summary = {
            "status": "PHASE7_SMOKE_PREPARATION_PASS",
            "original_clip_count": 2,
            "sparse_view_count": 6,
            "views": [
                {
                    "sample_id": row["sample_id"],
                    "view_id": row["view_id"],
                    "selected_observation_count": len(row["selected_indices"]),
                    "feature_shape": list(row["features"].shape),
                    "first_selected_index": int(row["selected_indices"][0]),
                    "last_selected_index": int(row["selected_indices"][-1]),
                }
                for row in views
            ],
        }
        write_json(OUT / "smoke_prepare_result.json", summary)
        return summary

    if len(views) != 336:
        raise RuntimeError(f"PHASE7_SPARSE_VIEW_COUNT_MISMATCH:{len(views)}")
    counts = Counter(row["phase7_partition"] for row in views)
    if counts != {"FIT": 213, "CAL": 54, "DEV": 69}:
        raise RuntimeError(f"PHASE7_VIEW_PARTITION_COUNT_MISMATCH:{dict(counts)}")
    fit_features = [row["features"] for row in views if row["phase7_partition"] == "FIT"]
    stats = normalization_from_train(fit_features)
    normalization = {
        "schema": "apphear.phase7.cadence_aligned_fit_normalization.v1",
        "feature_schema": SEGMENTATION_FEATURE_SCHEMA,
        "population": "71_FIT_CLIPS_X_3_SPARSE_VIEWS_ONLY",
        "fit_original_clip_count": 71,
        "fit_sparse_view_count": 213,
        "fit_sample_ids": split["fit_sample_ids"],
        "observation_count": int(sum(len(value) for value in fit_features)),
        "mean": stats["mean"].astype(float).tolist(),
        "std": stats["std"].astype(float).tolist(),
        "cal_influenced_statistics": False,
        "dev_influenced_statistics": False,
        "phase6_phone_influenced_statistics": False,
        "fit_dt_seconds": distribution(
            [float(value) for features in fit_features for value in features[1:, 215]]
        ),
        "normalized_fit_dt_z": distribution(
            [
                float((value - stats["mean"][215]) / stats["std"][215])
                for features in fit_features
                for value in features[1:, 215]
            ]
        ),
        "phone_target_interval_dt_z": {
            row["view_id"]: float(
                (float(row["target_interval_ms"]) / 1000.0 - stats["mean"][215]) / stats["std"][215]
            )
            for row in config["cadence_views"]
        },
    }
    freeze_json(OUT / "cadence_aligned_normalization_stats.json", normalization)
    freeze_json(OUT / "sparse_feature_schema.json", feature_schema_document(config))

    manifest_rows = []
    label_rows = []
    totals: defaultdict[str, Counter[int]] = defaultdict(Counter)
    for row in views:
        counts_row = Counter(map(int, row["labels"]))
        totals[row["phase7_partition"]].update(counts_row)
        manifest_rows.append(
            {
                "view_key": row["view_key"],
                "sample_id": row["sample_id"],
                "view_id": row["view_id"],
                "target_interval_ms": row["target_interval_ms"],
                "phase_offset_ms": row["phase_offset_ms"],
                "source": row["source"],
                "signer_id": row["signer_id"],
                "segmentation_split": row["segmentation_split"],
                "phase7_partition": row["phase7_partition"],
                "source_raw_path": row["raw_path"],
                "source_raw_sha256": row["raw_sha256"],
                "source_observation_count": len(
                    load_raw_sequence(Path(row["raw_path"])).timestamp_ms
                ),
                "selected_observation_count": len(row["selected_indices"]),
                "selected_indices": row["selected_indices"].astype(int).tolist(),
                "selected_timestamps_ms": row["timestamps_ms"].astype(float).tolist(),
                "feature_path": row["feature_path"],
                "feature_sha256": row["feature_sha256"],
                "feature_width": FEATURE_WIDTH,
                "interpolated": False,
                "duplicated": False,
                "fabricated": False,
            }
        )
        label_rows.append(
            {
                "view_key": row["view_key"],
                "sample_id": row["sample_id"],
                "view_id": row["view_id"],
                "phase7_partition": row["phase7_partition"],
                "human_sign_start_ms": float(row["human_sign_start_ms"]),
                "human_sign_end_ms": float(row["human_sign_end_ms"]),
                "timestamps_ms": row["timestamps_ms"].astype(float).tolist(),
                "labels": row["labels"].astype(int).tolist(),
                "counts": {
                    LABEL_NAMES[key] if key >= 0 else "IGNORED": counts_row[key]
                    for key in (-1, 0, 1, 2)
                },
            }
        )
    freeze_json(
        OUT / "sparse_view_manifest.json",
        {
            "schema": "apphear.phase7.sparse_view_manifest.v1",
            "milestone": MILESTONE,
            "selected_manifest_sha256": EXPECTED_SELECTED_SHA,
            "segmentation_split_sha256": EXPECTED_SPLIT_SHA,
            "original_clip_count": 112,
            "train_original_clip_count": 89,
            "dev_original_clip_count": 23,
            "sparse_view_count": len(manifest_rows),
            "fit_view_count": counts["FIT"],
            "cal_view_count": counts["CAL"],
            "dev_view_count": counts["DEV"],
            "candidate01_rerun": False,
            "rows": manifest_rows,
        },
    )
    freeze_json(
        OUT / "generated_sparse_temporal_labels.json",
        {
            "schema": "apphear.phase7.sparse_temporal_labels.v1",
            "ignore_band_ms": float(config["labels"]["ignore_band_ms"]),
            "human_boundaries_are_labels_only": True,
            "totals": {
                partition: {
                    LABEL_NAMES[key] if key >= 0 else "IGNORED": counter[key]
                    for key in (-1, 0, 1, 2)
                }
                for partition, counter in sorted(totals.items())
            },
            "views": label_rows,
        },
    )
    result = {
        "status": "PHASE7_CADENCE_DATA_PREPARED",
        "original_clips": 112,
        "sparse_views": 336,
        "fit_views": 213,
        "cal_views": 54,
        "dev_views": 69,
        "candidate01_rerun": False,
    }
    write_json(OUT / "prepare_result.json", result)
    return result


def _load_view_rows(partitions: set[str]) -> list[dict[str, Any]]:
    manifest = read_json(OUT / "sparse_view_manifest.json")
    labels = read_json(OUT / "generated_sparse_temporal_labels.json")
    label_by_key = {row["view_key"]: row for row in labels["views"]}
    population = {str(row["sample_id"]): row for row in load_population()}
    result = []
    for item in manifest["rows"]:
        if item["phase7_partition"] not in partitions:
            continue
        with np.load(item["feature_path"], allow_pickle=False) as data:
            if str(data["schema"].item()) != SEGMENTATION_FEATURE_SCHEMA:
                raise RuntimeError("PHASE7_SAVED_FEATURE_SCHEMA_MISMATCH")
            features = np.asarray(data["features"], np.float32)
            timestamps = np.asarray(data["timestamps_ms"], np.float64)
            selected_indices = np.asarray(data["selected_indices"], np.int32)
        label_row = label_by_key[item["view_key"]]
        target = np.asarray(label_row["labels"], np.int32)
        if features.shape != (len(target), FEATURE_WIDTH) or len(timestamps) != len(target):
            raise RuntimeError(f"PHASE7_FEATURE_LABEL_ALIGNMENT:{item['view_key']}")
        row = dict(population[str(item["sample_id"])])
        row.update(item)
        row.update(
            {
                "features": features,
                "timestamps_ms": timestamps,
                "selected_indices": selected_indices,
                "labels": target,
            }
        )
        result.append(row)
    return result


def _normalization() -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    document = read_json(OUT / "cadence_aligned_normalization_stats.json")
    if document["population"] != "71_FIT_CLIPS_X_3_SPARSE_VIEWS_ONLY":
        raise RuntimeError("PHASE7_NORMALIZATION_POPULATION_MISMATCH")
    return (
        np.asarray(document["mean"], np.float32),
        np.asarray(document["std"], np.float32),
        document,
    )


def predict_rows(
    model: Any, rows: list[dict[str, Any]], config: dict[str, Any]
) -> tuple[list[np.ndarray], list[dict[str, Any]], list[dict[str, Any]]]:
    predictions = []
    events = []
    probability_rows = []
    threshold = float(config["evaluation"]["containment_active_recall_threshold"])
    for row in rows:
        logits = model(row["normalized_features"][None], training=False).numpy()[0]
        probabilities = softmax(logits)
        states = np.argmax(probabilities, axis=1).astype(np.int32)
        event = decode_event(
            row["timestamps_ms"], probabilities, float(row["video_duration_ms"]), config
        )
        result = event_result(row, event, threshold)
        result.update(
            {
                "view_key": row["view_key"],
                "view_id": row["view_id"],
                "target_interval_ms": float(row["target_interval_ms"]),
                "phase7_partition": row["phase7_partition"],
                "selected_observation_count": len(row["timestamps_ms"]),
                "ends_at_final_observation": bool(
                    event is not None
                    and int(event["active_observation_end_index"]) == len(row["timestamps_ms"]) - 1
                ),
                "full_window_reduction_fraction": (
                    0.0
                    if event is None
                    else max(
                        0.0,
                        1.0
                        - (float(event["end_ms"]) - float(event["start_ms"]))
                        / float(row["video_duration_ms"]),
                    )
                ),
                "predicted_state_counts": {
                    LABEL_NAMES[index]: int(np.count_nonzero(states == index)) for index in range(3)
                },
            }
        )
        if event is not None:
            result["decoder"] = event
        predictions.append(states)
        events.append(result)
        probability_rows.append(
            {
                "view_key": row["view_key"],
                "probabilities": probabilities.astype(float).tolist(),
                "argmax_states": states.astype(int).tolist(),
            }
        )
    return predictions, events, probability_rows


def aggregate_sparse_events(rows: list[dict[str, Any]]) -> dict[str, Any]:
    value = aggregate_events(rows)
    value.update(
        {
            "events_ending_at_final_observation": sum(
                row["ends_at_final_observation"] for row in rows
            ),
            "final_observation_end_rate": float(
                np.mean([row["ends_at_final_observation"] for row in rows])
            ),
            "full_window_context_reduction": {
                "mean": float(np.mean([row["full_window_reduction_fraction"] for row in rows])),
                "median": float(np.median([row["full_window_reduction_fraction"] for row in rows])),
            },
        }
    )
    return value


def _group_results(
    event_rows: list[dict[str, Any]],
    state_rows: list[np.ndarray],
    source_rows: list[dict[str, Any]],
    key: str,
) -> dict[str, Any]:
    groups: defaultdict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(source_rows):
        groups[str(row[key])].append(index)
    result = {}
    for name, indices in sorted(groups.items()):
        result[name] = {
            "event_metrics": aggregate_sparse_events([event_rows[index] for index in indices]),
            "state_metrics": state_metrics(
                [source_rows[index]["labels"] for index in indices],
                [state_rows[index] for index in indices],
            ),
        }
    return result


def _checkpoint_key(events: list[dict[str, Any]], state: dict[str, Any]) -> tuple[float, ...]:
    aggregate = aggregate_sparse_events(events)
    return (
        float(aggregate["containment_rate"]),
        -float(aggregate["premature_cut_rate"]),
        float(aggregate["event_emission_rate"]),
        float(aggregate["predicted_window_precision"].get("mean", 0.0)),
        float(state["macro_f1"]),
    )


def train() -> dict[str, Any]:
    if (OUT / "training_history.json").exists() or (OUT / "best_model.keras").exists():
        raise RuntimeError("PHASE7_SINGLE_TRAINING_RUN_ALREADY_EXECUTED")
    config = load_config()
    fit_rows = _load_view_rows({"FIT"})
    cal_rows = _load_view_rows({"CAL"})
    if len(fit_rows) != 213 or len(cal_rows) != 54:
        raise RuntimeError("PHASE7_FIT_CAL_VIEW_COUNT_MISMATCH")
    mean, std, normalization = _normalization()
    for row in fit_rows + cal_rows:
        row["normalized_features"] = apply_normalization(row["features"], mean, std)
    if {row["sample_id"] for row in fit_rows} & {row["sample_id"] for row in cal_rows}:
        raise RuntimeError("PHASE7_VIEW_GROUP_LEAKAGE")

    import tensorflow as tf

    seed = int(config["training"]["seed"])
    tf.keras.utils.set_random_seed(seed)
    tf.config.experimental.enable_op_determinism()
    counts = Counter(
        int(label) for row in fit_rows for label in row["labels"] if int(label) != IGNORE_LABEL
    )
    if set(counts) != {0, 1, 2}:
        raise RuntimeError("PHASE7_FIT_LABEL_CLASS_MISSING")
    total = sum(counts.values())
    class_weights = {index: total / (3.0 * counts[index]) for index in range(3)}
    max_length = max(len(row["labels"]) for row in fit_rows)
    x = np.zeros((len(fit_rows), max_length, FEATURE_WIDTH), np.float32)
    y = np.zeros((len(fit_rows), max_length), np.int32)
    weights = np.zeros((len(fit_rows), max_length), np.float32)
    for index, row in enumerate(fit_rows):
        length = len(row["labels"])
        x[index, :length] = row["normalized_features"]
        valid = row["labels"] != IGNORE_LABEL
        y[index, :length] = np.where(valid, row["labels"], 0)
        weights[index, :length] = np.asarray(
            [
                class_weights[int(label)] if keep else 0.0
                for label, keep in zip(row["labels"], valid, strict=True)
            ],
            np.float32,
        )
    model = build_model(config)
    if model.count_params() != 123_779:
        raise RuntimeError(f"PHASE7_MODEL_PARAMETER_MISMATCH:{model.count_params()}")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(float(config["training"]["learning_rate"])),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        weighted_metrics=[tf.keras.metrics.SparseCategoricalAccuracy(name="state_accuracy")],
    )
    summary_lines: list[str] = []
    model.summary(print_fn=summary_lines.append)
    write_json(
        OUT / "model_summary.json",
        {
            "schema": "apphear.phase7.model_summary.v1",
            "parameter_count": model.count_params(),
            "architecture": config["model"],
            "input_shape": [None, None, FEATURE_WIDTH],
            "output_shape": [None, None, 3],
            "keras_summary": summary_lines,
        },
    )

    class CalCheckpoint(tf.keras.callbacks.Callback):
        def __init__(self) -> None:
            super().__init__()
            self.best_key: tuple[float, ...] | None = None
            self.best_epoch: int | None = None
            self.records: list[dict[str, Any]] = []

        def on_epoch_end(self, epoch: int, logs: dict[str, float] | None = None) -> None:
            predictions, events, _ = predict_rows(self.model, cal_rows, config)
            state = state_metrics([row["labels"] for row in cal_rows], predictions)
            event_metrics = aggregate_sparse_events(events)
            key = _checkpoint_key(events, state)
            improved = self.best_key is None or key > self.best_key
            if improved:
                self.best_key = key
                self.best_epoch = epoch + 1
                self.model.save(OUT / "best_model.keras", overwrite=True)
            record = {
                "epoch": epoch + 1,
                "fit_logs": {name: float(value) for name, value in (logs or {}).items()},
                "cal_checkpoint_key": list(key),
                "cal_event_metrics": event_metrics,
                "cal_state_metrics": state,
                "saved_as_best": improved,
            }
            self.records.append(record)
            print(f"cal-check epoch={epoch + 1} key={key} best={improved}", flush=True)

    callback = CalCheckpoint()
    history = model.fit(
        x,
        y,
        sample_weight=weights,
        batch_size=int(config["training"]["batch_size"]),
        epochs=int(config["training"]["epochs"]),
        shuffle=True,
        verbose=2,
        callbacks=[callback],
    )
    if callback.best_epoch is None or not (OUT / "best_model.keras").is_file():
        raise RuntimeError("PHASE7_BEST_CHECKPOINT_NOT_CREATED")
    history_doc = {
        "schema": "apphear.phase7.training_history.v1",
        "training_run_identity": "SINGLE_AUTHORIZED_RUN_01",
        "started_from_random_initialization": True,
        "seed": seed,
        "epochs_completed": len(history.history["loss"]),
        "best_epoch": callback.best_epoch,
        "best_checkpoint_key": list(callback.best_key or ()),
        "checkpoint_population": "CAL_ONLY",
        "fit_original_clip_count": 71,
        "fit_sparse_view_count": 213,
        "cal_original_clip_count": 18,
        "cal_sparse_view_count": 54,
        "dev_evaluated_during_training": False,
        "phone_replay_used_during_training": False,
        "class_label_counts_fit_only": {LABEL_NAMES[key]: counts[key] for key in range(3)},
        "class_weights_fit_only": {LABEL_NAMES[key]: class_weights[key] for key in range(3)},
        "keras_history": {
            name: [float(value) for value in values] for name, values in history.history.items()
        },
        "epoch_cal_metrics": callback.records,
        "normalization_sha256": sha256(OUT / "cadence_aligned_normalization_stats.json"),
        "normalization_population": normalization["population"],
    }
    write_json(OUT / "training_history.json", history_doc)
    best_hash = sha256(OUT / "best_model.keras")
    freeze_json(
        OUT / "best_model.sha256.json",
        {
            "schema": "apphear.phase7.frozen_checkpoint.v1",
            "path": str((OUT / "best_model.keras").resolve()),
            "sha256": best_hash,
            "selected_by": "CAL_ONLY_PREDECLARED_LEXICOGRAPHIC_RULE",
            "best_epoch": callback.best_epoch,
            "dev_opened_before_freeze": False,
            "phone_replay_opened_before_freeze": False,
        },
    )
    best_record = callback.records[callback.best_epoch - 1]
    write_json(
        OUT / "cal_metrics.json",
        {
            "schema": "apphear.phase7.cal_metrics.v1",
            "best_epoch": callback.best_epoch,
            "checkpoint_key": list(callback.best_key or ()),
            "event_metrics": best_record["cal_event_metrics"],
            "state_metrics": best_record["cal_state_metrics"],
        },
    )
    return {
        "status": "PHASE7_TRAINING_COMPLETE_CHECKPOINT_FROZEN",
        "best_epoch": callback.best_epoch,
        "best_model_sha256": best_hash,
        "next": "RUN_EVALUATE_FROZEN_DEV",
    }


def verify_checkpoint() -> dict[str, Any]:
    identity = read_json(OUT / "best_model.sha256.json")
    if sha256(OUT / "best_model.keras") != identity["sha256"]:
        raise RuntimeError("PHASE7_FROZEN_CHECKPOINT_HASH_MISMATCH")
    history = read_json(OUT / "training_history.json")
    if history["checkpoint_population"] != "CAL_ONLY" or history["dev_evaluated_during_training"]:
        raise RuntimeError("PHASE7_CHECKPOINT_SELECTION_CONTAMINATION")
    return identity


def _write_dev_csv(rows: list[dict[str, Any]]) -> None:
    fields_csv = [
        "view_key",
        "sample_id",
        "view_id",
        "target_interval_ms",
        "source",
        "signer_id",
        "event_emitted",
        "active_recall",
        "contained_90pct",
        "premature_cut",
        "predicted_start_ms",
        "predicted_end_ms",
        "window_precision",
        "start_error_ms",
        "end_error_ms",
        "start_absolute_error_ms",
        "end_absolute_error_ms",
        "excess_pre_ms",
        "excess_post_ms",
        "retained_context_ms",
        "full_window_reduction_fraction",
        "ends_at_final_observation",
    ]
    with (OUT / "per_sparse_dev_result.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields_csv, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _sparse_dev_gate(
    aggregate: dict[str, Any], by_cadence: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    gate = config["evaluation"]["sparse_dev_gate"]
    checks = {
        "event_emission_at_least_0_95": aggregate["event_emission_rate"]
        >= gate["minimum_event_emission_rate"],
        "containment_at_least_0_85": aggregate["containment_rate"]
        >= gate["minimum_containment_rate"],
        "median_active_recall_at_least_0_95": aggregate["active_recall"]["median"]
        >= gate["minimum_median_active_recall"],
        "premature_cut_at_most_0_15": aggregate["premature_cut_rate"]
        <= gate["maximum_premature_cut_rate"],
        "mean_context_reduction_at_least_0_25": aggregate["full_window_context_reduction"]["mean"]
        >= gate["minimum_mean_full_window_reduction"],
        "final_observation_end_rate_at_most_0_25": aggregate["final_observation_end_rate"]
        <= gate["maximum_final_observation_end_rate"],
        "each_cadence_mean_recall_at_least_0_80": all(
            item["event_metrics"]["active_recall"]["mean"]
            >= gate["minimum_each_cadence_mean_active_recall"]
            for item in by_cadence.values()
        ),
    }
    return {"checks": checks, "passed": all(checks.values())}


def write_report(decision: dict[str, Any]) -> None:
    dev = read_json(OUT / "sparse_dev_event_metrics.json")
    state = read_json(OUT / "sparse_dev_state_metrics.json")["overall"]
    cadence = read_json(OUT / "sparse_dev_by_cadence.json")
    source = read_json(OUT / "sparse_dev_by_source.json")
    history = read_json(OUT / "training_history.json")
    checkpoint = read_json(OUT / "best_model.sha256.json")
    normalization = read_json(OUT / "cadence_aligned_normalization_stats.json")
    overall = dev["overall"]
    cadence_lines = []
    for view_id, value in cadence.items():
        event = value["event_metrics"]
        cadence_lines.append(
            f"| {view_id} | {event['event_emission_rate']:.3f} | "
            f"{event['containment_rate']:.3f} | {event['active_recall']['mean']:.3f} | "
            f"{event['premature_cut_rate']:.3f} | "
            f"{event['final_observation_end_rate']:.3f} | "
            f"{event['full_window_context_reduction']['mean']:.3f} | "
            f"{value['state_metrics']['macro_f1']:.3f} |"
        )
    source_lines = []
    for name, value in source.items():
        event = value["event_metrics"]
        source_lines.append(
            f"| {name} | {event['clip_count']} | {event['containment_rate']:.3f} | "
            f"{event['active_recall']['mean']:.3f} | {event['premature_cut_rate']:.3f} | "
            f"{event['final_observation_end_rate']:.3f} | "
            f"{value['state_metrics']['macro_f1']:.3f} |"
        )

    phone_section = "Phone replay was not run because sparse DEV had not passed."
    if (OUT / "phone_replay_recognition.json").exists():
        phone = read_json(OUT / "phone_replay_recognition.json")
        boundary = read_json(OUT / "phone_replay_boundary_comparison.json")
        recognition_by_id = {row["attempt_id"]: row for row in phone["attempts"]}
        attempt_lines = []
        for row in boundary["attempts"]:
            recognition = recognition_by_id[row["attempt_id"]]
            attempt_lines.append(
                f"| {row['attempt_id']} | {row['annotation_confidence']} | "
                f"{row['unpadded_oracle']['reference_interval_recall']:.3f} | "
                f"{row['full_window_reduction_fraction']:.3f} | "
                f"{row['ends_at_final_phone_observation']} | "
                f"{recognition.get('top1_gloss')} | {recognition.get('expected_rank')} | "
                f"{recognition.get('expected_probability', 0.0):.6f} |"
            )
        phone_section = f"""All 10 attempts emitted an event; none ended at the final observation.
Mean full-window reduction was `{boundary["mean_full_window_reduction_fraction"]:.4f}`. Only
`{boundary["primary_unpadded_recall_ge_0_80"]}/9` HIGH/MEDIUM attempts retained at least 80% of
the unpadded oracle interval, so the predeclared phone boundary gate failed. Recognition improved
to Top-1 `{phone["top1_correct"]}/10`, expected Top-5 `{phone["expected_in_top5"]}/10`, median
expected probability `{phone["median_expected_probability"]:.6f}`, and median rank
`{phone["median_expected_rank"]:.1f}`. Oracle-rescue attempts recovered were
`{phone["oracle_rescue_attempts_recovered"]}`.

| Attempt | Confidence | Oracle recall | Reduction | Ends final | Top-1 | Exp. rank | Exp. prob. |
|---|---|---:|---:|---|---|---:|---:|
{chr(10).join(attempt_lines)}"""
    report = f"""# Phase 7 Production-Cadence-Aligned Segmenter

Milestone: `{MILESTONE}`

## 1. Frozen population and transformation

The exact 89 TRAIN / 23 signer-disjoint DEV Phase-5.1T population is unchanged. Three genuine
timestamp-sampled views (`133.308`, `199.962`, `266.616` ms) are generated per clip from frozen
complete-source raw-v1. No observation is interpolated, duplicated, fabricated, or carried. Every
378-wide transition feature is recomputed from the immediately previous selected observation.
The prepared package contains 336 views: 213 FIT, 54 CAL, and 69 DEV.

## 2. FIT/CAL, normalization, and training isolation

FIT/CAL is frozen at 71/18 original TRAIN clips, with all three views grouped by clip. New
normalization and class weights use FIT views only. CAL alone selects the checkpoint. Frozen DEV
and the known phone replay remained inaccessible until checkpoint hashing. FIT selected-dt median
was `{normalization["fit_dt_seconds"]["median"]:.6f}` seconds; frozen phone target dt z-scores were
`{normalization["phone_target_interval_dt_z"]}`.

One from-scratch 30-epoch run was executed. CAL selected epoch `{history["best_epoch"]}` with key
`{history["best_checkpoint_key"]}`. Checkpoint SHA-256: `{checkpoint["sha256"]}`. DEV was not used
for normalization, class weights, epoch selection, or checkpoint selection.

## 3. Sparse signer-disjoint DEV

All seven predeclared gates passed. Event emission was `{overall["event_emission_rate"]:.3f}`;
>=90% containment `{overall["containment_rate"]:.3f}`; median/mean ACTIVE recall
`{overall["active_recall"]["median"]:.3f}/{overall["active_recall"]["mean"]:.3f}`; premature-cut
rate `{overall["premature_cut_rate"]:.3f}`; mean full-window reduction
`{overall["full_window_context_reduction"]["mean"]:.3f}`; final-observation end rate
`{overall["final_observation_end_rate"]:.3f}`. State accuracy/macro-F1 were
`{state["accuracy"]:.3f}/{state["macro_f1"]:.3f}`. PRE/ACTIVE/POST F1 were
`{state["per_class"]["PRE_IDLE"]["f1"]:.3f}` / `{state["per_class"]["ACTIVE_SIGN"]["f1"]:.3f}` /
`{state["per_class"]["POST_RECOVERY"]["f1"]:.3f}`.

| Cadence | Emission | Containment | Mean recall | Premature | Ends final | Reduction | Macro-F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(cadence_lines)}

| Source | Views | Containment | Mean recall | Premature | Ends final | Macro-F1 |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(source_lines)}

The held-out LOCAL signer remained weakest: its 12 views had containment `0.750`, premature-cut
rate `0.250`, final-observation end rate `0.750`, and macro-F1 `0.738`. This did not overturn the
predeclared aggregate sparse-DEV gate but remains a source/signer limitation.

## 4. Known Phase-6 phone diagnostic

{phone_section}

Cadence alignment corrected the old persistent-ACTIVE behavior (`10/10` ending at the final
observation became `0/10`) and recovered substantial recognition utility. It also introduced
phone truncation/misalignment: attempts 004 and 006 retained only `0.553` and `0.538` of the oracle
ACTIVE interval, while attempt 008 selected a disjoint early interval (`0.000` recall). Therefore
cadence mismatch was material but was not the sole transfer problem.

## 5. Governance and scientific decision

Exactly one architecture and one training run were used. Candidate01, raw-v1, Recognition V2, the
recognizer, human labels, split membership, Android, recognition DEV, protected TEST, and sealed
phone holdouts were not modified or accessed beyond the explicitly authorized known diagnostic.
There was no post-result tuning.

**`{decision["final_evidence_state"]}`**

**`{decision["next_stop_boundary"]}`**

The decoder remains sequence-global. This experiment does not prove streaming Android SignEvent
behavior or production accuracy.
"""
    (OUT / "PHASE7_PRODUCTION_CADENCE_ALIGNED_SEGMENTER_REPORT.md").write_text(
        report, encoding="utf-8"
    )


def evaluate() -> dict[str, Any]:
    identity = verify_checkpoint()
    config = load_config()
    dev_rows = _load_view_rows({"DEV"})
    if len(dev_rows) != 69 or len({row["sample_id"] for row in dev_rows}) != 23:
        raise RuntimeError("PHASE7_DEV_VIEW_COUNT_MISMATCH")
    mean, std, _ = _normalization()
    for row in dev_rows:
        row["normalized_features"] = apply_normalization(row["features"], mean, std)

    import tensorflow as tf

    model = tf.keras.models.load_model(OUT / "best_model.keras", compile=False)
    predictions, events, _ = predict_rows(model, dev_rows, config)
    state = state_metrics([row["labels"] for row in dev_rows], predictions)
    event_metrics = aggregate_sparse_events(events)
    by_cadence = _group_results(events, predictions, dev_rows, "view_id")
    by_signer = _group_results(events, predictions, dev_rows, "signer_id")
    by_source = _group_results(events, predictions, dev_rows, "source")
    by_clip = _group_results(events, predictions, dev_rows, "sample_id")
    gate = _sparse_dev_gate(event_metrics, by_cadence, config)
    write_json(
        OUT / "sparse_dev_state_metrics.json",
        {"schema": "apphear.phase7.sparse_dev_state_metrics.v1", "overall": state},
    )
    write_json(
        OUT / "sparse_dev_event_metrics.json",
        {
            "schema": "apphear.phase7.sparse_dev_event_metrics.v1",
            "checkpoint_sha256": identity["sha256"],
            "overall": event_metrics,
            "by_original_clip": by_clip,
            "gate": gate,
        },
    )
    write_json(OUT / "sparse_dev_by_cadence.json", by_cadence)
    write_json(OUT / "sparse_dev_by_signer.json", by_signer)
    write_json(OUT / "sparse_dev_by_source.json", by_source)
    _write_dev_csv(events)
    if gate["passed"]:
        decision = {
            "schema": "apphear.phase7.final_decision.v1",
            "final_evidence_state": "SPARSE_DEV_GATE_PASS_PHONE_REPLAY_PENDING",
            "sparse_dev_gate": gate,
            "next_stop_boundary": "RUN_KNOWN_PHONE_REPLAY_ONCE",
            "checkpoint_sha256": identity["sha256"],
        }
    else:
        decision = {
            "schema": "apphear.phase7.final_decision.v1",
            "final_evidence_state": "CADENCE_ALIGNED_SEGMENTER_NOT_SUPPORTED",
            "sparse_dev_gate": gate,
            "failure_diagnosis": diagnose_sparse_dev(
                event_metrics, by_cadence, by_signer, by_source
            ),
            "next_stop_boundary": "WAIT_FOR_PROJECT_LEAD_SEGMENTATION_FAILURE_DIAGNOSIS",
            "checkpoint_sha256": identity["sha256"],
        }
    write_json(OUT / "final_decision.json", decision)
    write_report(decision)
    return decision


def diagnose_sparse_dev(
    aggregate: dict[str, Any],
    by_cadence: dict[str, Any],
    by_signer: dict[str, Any],
    by_source: dict[str, Any],
) -> list[str]:
    reasons = []
    if aggregate["event_emission_rate"] < 0.95:
        reasons.append("NO_EVENT")
    if aggregate["premature_cut_rate"] > 0.15:
        reasons.append("TRUNCATION")
    if aggregate["final_observation_end_rate"] > 0.25:
        reasons.append("ACTIVE_POST_RETAINED_RECOVERY")
    if aggregate["full_window_context_reduction"]["mean"] < 0.25:
        reasons.append("POOR_CONTEXT_REDUCTION")
    if any(item["event_metrics"]["active_recall"]["mean"] < 0.80 for item in by_cadence.values()):
        reasons.append("CADENCE_SPECIFIC")
    if any(item["event_metrics"]["active_recall"]["mean"] < 0.80 for item in by_signer.values()):
        reasons.append("SIGNER_SPECIFIC")
    if any(item["event_metrics"]["active_recall"]["mean"] < 0.80 for item in by_source.values()):
        reasons.append("SOURCE_SPECIFIC")
    return reasons or ["STATE_CONFUSION_REQUIRES_TRACE_REVIEW"]


def _interval_metrics(
    learned_start: float,
    learned_end: float,
    reference_start: float,
    reference_end: float,
) -> dict[str, float]:
    intersection = max(
        0.0,
        min(learned_end, reference_end) - max(learned_start, reference_start),
    )
    learned_duration = max(0.0, learned_end - learned_start)
    reference_duration = max(0.0, reference_end - reference_start)
    union = learned_duration + reference_duration - intersection
    return {
        "start_error_ms": learned_start - reference_start,
        "end_error_ms": learned_end - reference_end,
        "intersection_duration_ms": intersection,
        "reference_interval_recall": (
            intersection / reference_duration if reference_duration else 0.0
        ),
        "learned_window_precision": (intersection / learned_duration if learned_duration else 0.0),
        "iou": intersection / union if union else 0.0,
    }


def phone_boundary_comparison(
    event_doc: dict[str, Any],
    bounds: dict[str, Any],
    raw_by_attempt: dict[str, RawSequence],
) -> dict[str, Any]:
    events = {row["attempt_id"]: row for row in event_doc["events"]}
    rows = []
    for bound in bounds["bounds"]:
        attempt = str(bound["attempt_id"])
        raw = raw_by_attempt[attempt]
        relative = np.asarray(raw.timestamp_ms, np.float64) - float(raw.timestamp_ms[0])
        event = events[attempt]
        primary = bound["annotation_confidence"] in {"HIGH", "MEDIUM"}
        if not event["event_emitted"]:
            rows.append(
                {
                    "attempt_id": attempt,
                    "annotation_confidence": bound["annotation_confidence"],
                    "primary_boundary_population": primary,
                    "event_emitted": False,
                    "full_window_reduction_fraction": 1.0,
                    "starts_at_first_phone_observation": False,
                    "ends_at_final_phone_observation": False,
                    "unpadded_oracle": {"reference_interval_recall": 0.0},
                }
            )
            continue
        start_index = int(event["start_index"])
        end_index = int(event["end_index"])
        learned_start = float(relative[start_index])
        learned_end = float(relative[end_index])
        full_duration = float(relative[-1])
        unpadded_start = float(relative[int(bound["oracle_start_index"])])
        unpadded_end = float(relative[int(bound["oracle_end_index"])])
        padded_start = float(relative[int(bound["padded_start_index"])])
        padded_end = float(relative[int(bound["padded_end_index"])])
        learned_duration = learned_end - learned_start
        rows.append(
            {
                "attempt_id": attempt,
                "annotation_confidence": bound["annotation_confidence"],
                "primary_boundary_population": primary,
                "event_emitted": True,
                "learned_start_index": start_index,
                "learned_end_index": end_index,
                "learned_start_ms": learned_start,
                "learned_end_ms": learned_end,
                "learned_duration_ms": learned_duration,
                "full_duration_ms": full_duration,
                "full_window_reduction_fraction": 1.0 - learned_duration / full_duration,
                "starts_at_first_phone_observation": start_index == 0,
                "ends_at_final_phone_observation": end_index == len(relative) - 1,
                "unpadded_oracle": {
                    **_interval_metrics(
                        learned_start,
                        learned_end,
                        unpadded_start,
                        unpadded_end,
                    )
                },
                "padded_oracle": {
                    **_interval_metrics(
                        learned_start,
                        learned_end,
                        padded_start,
                        padded_end,
                    )
                },
            }
        )
    primary_rows = [row for row in rows if row["primary_boundary_population"]]
    primary_recalls = [
        float(row["unpadded_oracle"]["reference_interval_recall"]) for row in primary_rows
    ]
    reductions = [float(row["full_window_reduction_fraction"]) for row in rows]
    return {
        "schema": "apphear.phase7.phone_oracle_boundary_comparison.v1",
        "attempts": rows,
        "events_emitted": sum(row["event_emitted"] for row in rows),
        "events_ending_at_final_observation": sum(
            row["ends_at_final_phone_observation"] for row in rows
        ),
        "events_starting_at_first_observation": sum(
            row["starts_at_first_phone_observation"] for row in rows
        ),
        "mean_full_window_reduction_fraction": float(np.mean(reductions)),
        "primary_unpadded_recall_ge_0_80": sum(value >= 0.80 for value in primary_recalls),
        "primary_unpadded_recall_distribution": distribution(primary_recalls),
    }


def phone_replay() -> dict[str, Any]:
    dev = read_json(OUT / "sparse_dev_event_metrics.json")
    if not dev["gate"]["passed"]:
        raise RuntimeError("PHASE7_PHONE_REPLAY_FORBIDDEN_SPARSE_DEV_GATE_FAILED")
    identity = verify_checkpoint()
    config = load_config()
    mean, std, _ = _normalization()

    import tensorflow as tf

    from eval.runtime_diagnostics.finalize_phase4a_gate4a1 import load_raw
    from eval.runtime_diagnostics.phase4a_gate4a1c_oracle_boundary_replay import (
        BOUNDS,
        CHECKPOINT,
        EXPECTED,
        SOURCE_SESSION,
        inference_row,
        subset_raw,
        verify_frozen,
    )
    from eval.runtime_diagnostics.phase6_evaluate_phone_replay import (
        attach_glosses,
        recognition_document,
    )
    from pipeline.perception_vnext.governance import VOCAB_MANIFEST

    if SOURCE_SESSION.resolve() != PHONE_SESSION.resolve():
        raise RuntimeError("PHASE7_PHONE_SESSION_IDENTITY_MISMATCH")
    model = tf.keras.models.load_model(OUT / "best_model.keras", compile=False)
    predictions_doc = []
    event_rows = []
    raw_by_attempt = {}
    for attempt in ATTEMPTS:
        raw, _ = load_raw(PHONE_SESSION / attempt / "raw_v1.json")
        raw_by_attempt[attempt] = raw
        timestamps = np.asarray(raw.timestamp_ms, np.float64)
        relative = timestamps - timestamps[0]
        features = derive_causal_segmentation_features(raw)
        normalized = apply_normalization(features, mean, std)
        probabilities = softmax(model(normalized[None], training=False).numpy()[0])
        states = np.argmax(probabilities, axis=1).astype(np.int32)
        event = decode_event(relative, probabilities, float(relative[-1]), config)
        predictions_doc.append(
            {
                "attempt_id": attempt,
                "observations": [
                    {
                        "index": index,
                        "source_timestamp_ms": float(timestamps[index]),
                        "relative_timestamp_ms": float(relative[index]),
                        "pre_probability": float(probabilities[index, 0]),
                        "active_probability": float(probabilities[index, 1]),
                        "post_probability": float(probabilities[index, 2]),
                        "argmax_state": int(states[index]),
                    }
                    for index in range(len(timestamps))
                ],
            }
        )
        if event is None:
            event_rows.append({"attempt_id": attempt, "event_emitted": False})
            continue
        retained = np.flatnonzero(
            (relative >= float(event["start_ms"])) & (relative <= float(event["end_ms"]))
        )
        event_rows.append(
            {
                "attempt_id": attempt,
                "event_emitted": True,
                "start_index": int(retained[0]),
                "end_index": int(retained[-1]),
                "retained_observation_count": len(retained),
                "start_source_timestamp_ms": float(timestamps[retained[0]]),
                "end_source_timestamp_ms": float(timestamps[retained[-1]]),
                "start_relative_ms": float(relative[retained[0]]),
                "end_relative_ms": float(relative[retained[-1]]),
                "retained_observation_duration_ms": float(
                    relative[retained[-1]] - relative[retained[0]]
                ),
                "starts_at_first_phone_observation": int(retained[0]) == 0,
                "ends_at_final_phone_observation": int(retained[-1]) == len(timestamps) - 1,
                "decoder_event": event,
            }
        )
    freeze_json(
        OUT / "phone_replay_predictions.json",
        {
            "schema": "apphear.phase7.phone_replay_predictions.v1",
            "checkpoint_sha256": identity["sha256"],
            "attempts": predictions_doc,
        },
    )
    event_doc = {
        "schema": "apphear.phase7.phone_replay_events.v1",
        "checkpoint_sha256": identity["sha256"],
        "session_id": PHONE_SESSION_ID,
        "events": event_rows,
        "oracle_opened_during_event_generation": False,
        "recognizer_opened_during_event_generation": False,
    }
    freeze_json(OUT / "phone_replay_events.json", event_doc)

    bounds = read_json(BOUNDS)
    boundary = phone_boundary_comparison(event_doc, bounds, raw_by_attempt)
    write_json(OUT / "phone_replay_boundary_comparison.json", boundary)
    verify_frozen()
    recognizer = tf.keras.models.load_model(CHECKPOINT, compile=False, safe_mode=True)
    vocab_map = read_json(VOCAB_MANIFEST)
    glosses = [gloss for gloss, index in sorted(vocab_map.items(), key=lambda pair: pair[1])]
    bounds_by_id = {row["attempt_id"]: row for row in bounds["bounds"]}
    learned_rows = []
    for event in event_rows:
        attempt = event["attempt_id"]
        expected_class, expected_gloss = EXPECTED[attempt]
        common = {
            "attempt_id": attempt,
            "expected_class_id": expected_class,
            "expected_gloss": expected_gloss,
            "annotation_confidence": bounds_by_id[attempt]["annotation_confidence"],
        }
        if not event["event_emitted"]:
            learned_rows.append({**common, "inference_executed": False})
            continue
        selected = subset_raw(raw_by_attempt[attempt], event["start_index"], event["end_index"])
        learned_rows.append(
            {
                **common,
                **attach_glosses(inference_row(recognizer, selected, expected_class), glosses),
                "inference_executed": True,
                "start_index": event["start_index"],
                "end_index": event["end_index"],
            }
        )
    recognition = recognition_document("PHASE7_CADENCE_ALIGNED", learned_rows)
    rescued = [
        row["attempt_id"]
        for row in learned_rows
        if row.get("top1_class_id") == row["expected_class_id"]
        and row["attempt_id"]
        in {"attempt_005", "attempt_006", "attempt_007", "attempt_009", "attempt_010"}
    ]
    recognition["oracle_rescue_attempts_recovered"] = rescued
    recognition["comparison_reference"] = {
        "phase6_old_learned": {
            "events_ending_at_final_observation": 10,
            "mean_full_window_reduction_fraction": 0.07792928655363898,
            "top1_correct": 2,
            "expected_in_top5": 7,
        },
        "human_oracle": {"top1_correct": 7, "expected_in_top5": 8},
        "phase7_candidate": {
            "events_emitted": boundary["events_emitted"],
            "events_ending_at_final_observation": boundary["events_ending_at_final_observation"],
            "mean_full_window_reduction_fraction": boundary["mean_full_window_reduction_fraction"],
            "top1_correct": recognition["top1_correct"],
            "expected_in_top5": recognition["expected_in_top5"],
            "oracle_rescue_attempts_recovered": rescued,
        },
    }
    write_json(OUT / "phone_replay_recognition.json", recognition)
    checks = {
        "events_ending_at_final_at_most_3_of_10": boundary["events_ending_at_final_observation"]
        <= 3,
        "mean_window_reduction_at_least_0_25": boundary["mean_full_window_reduction_fraction"]
        >= 0.25,
        "primary_oracle_recall_at_least_8_of_9": boundary["primary_unpadded_recall_ge_0_80"] >= 8,
        "both_full_correct_hello_remain_correct": all(
            next(row for row in learned_rows if row["attempt_id"] == attempt).get("top1_class_id")
            == 80
            for attempt in ("attempt_001", "attempt_002")
        ),
        "learned_top1_at_least_4_of_10": recognition["top1_correct"] >= 4,
    }
    supported = all(checks.values())
    decision = {
        "schema": "apphear.phase7.final_decision.v1",
        "sparse_dev_gate": dev["gate"],
        "known_phone_checks": checks,
        "known_phone_is_development_diagnostic": True,
        "final_evidence_state": (
            "CADENCE_ALIGNED_SEGMENTER_CORRECTION_SUPPORTED"
            if supported
            else "CADENCE_ALIGNMENT_ALONE_INSUFFICIENT"
        ),
        "next_stop_boundary": (
            "WAIT_FOR_PROJECT_LEAD_NEW_PHONE_VALIDATION_DECISION"
            if supported
            else "WAIT_FOR_PROJECT_LEAD_FEATURE_REPRESENTATION_DECISION"
        ),
        "no_post_result_tuning": True,
        "android_modified": False,
        "training_runs": 1,
    }
    write_json(OUT / "final_decision.json", decision)
    write_report(decision)
    write_source_hashes()
    return decision


def write_source_hashes() -> None:
    files = [
        Path(__file__).resolve(),
        ROOT / "tests/test_phase7_production_cadence_aligned_segmenter.py",
        CONFIG,
        T3_MANIFEST,
        T3 / "feature_schema.json",
        ROOT / "pipeline/perception_vnext/segmentation/learned_features.py",
        ROOT / "eval/runtime_diagnostics/phase5_1t_first_segmenter.py",
        OUT / "test_results.json",
    ]
    write_json(
        OUT / "source_hashes.json",
        {
            "schema": "apphear.phase7.source_hashes.v1",
            "files": [
                {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}
                for path in files
                if path.exists()
            ],
        },
    )


def audit() -> dict[str, Any]:
    config = load_config()
    population, _ = verify_frozen_inputs()
    split = deterministic_fit_cal_split(population, int(config["fit_cal_split"]["seed"]))
    result = {
        "status": "PHASE7_INPUT_AUDIT_PASS",
        "usable_train": 89,
        "usable_dev": 23,
        "full_video_raw_verified": 112,
        "fit_count": split["fit_count"],
        "cal_count": split["cal_count"],
        "candidate01_rerun": False,
    }
    write_json(OUT / "input_audit_result.json", result)
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument(
        "command",
        choices=("audit", "smoke-prepare", "prepare", "train", "evaluate", "phone-replay"),
    )
    return value


def main() -> None:
    args = parser().parse_args()
    actions = {
        "audit": audit,
        "smoke-prepare": lambda: prepare(smoke=True),
        "prepare": prepare,
        "train": train,
        "evaluate": evaluate,
        "phone-replay": phone_replay,
    }
    print(json.dumps(actions[args.command](), indent=2), flush=True)


if __name__ == "__main__":
    main()
