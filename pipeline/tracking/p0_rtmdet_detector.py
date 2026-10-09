"""Frozen P0 RTMDet-nano hand-detector-only evaluation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from itertools import permutations
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
import onnxruntime as ort

EXPERIMENT = "p0_rtmdet_detector_only_v1"
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/perception_backend_replacement/"
    "p0_rtmdet_detector_02"
)
DEFAULT_POSITIVE = Path(
    "F:/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/"
    "e2e_all_hand_gold_v1/engineering_01"
)
DEFAULT_NEGATIVE = Path("artifacts/recognition_upgrade/e2e_c0/n0_capture_06")
DEFAULT_MODEL_RELATIVE = Path(
    "model/extracted/20230831/rtmdet_onnx/"
    "rtmdet_nano_8xb32-300e_hand-267f9c8f/end2end.onnx"
)
DEFAULT_RUNNER = Path(
    "model/config/recognition_upgrade/run_p0_rtmdet_detector.ps1"
)

INPUT_SIZE = 320
SCORE_THRESHOLD = 0.30
EXPORT_CANDIDATE_THRESHOLD = 0.05
BAKED_NMS_IOU = 0.50
MAX_OUTPUTS = 100
MEAN_BGR = np.asarray((103.5300, 116.2800, 123.6750), dtype=np.float32)
STD_BGR = np.asarray((57.3750, 57.1200, 58.3950), dtype=np.float32)
CONDITIONS = (
    "motion_blur",
    "occlusion",
    "near_face",
    "edge_clipped",
    "partial_visibility",
)
SUBGROUPS = (
    "clear",
    "motion_blur",
    "occlusion",
    "near_face",
    "edge_clipped",
    "partial_visibility",
    "two_hand",
)
GATES = {
    "visible_hand_recall_min": 0.81,
    "complete_two_hand_recall_min": 0.65,
    "blur_improvement_min_absolute": 0.10,
    "occlusion_improvement_min_absolute": 0.10,
    "no_hand_false_presence_max": 0.03,
    "duplicate_prediction_rate_max": 0.05,
    "two_hands_merged_rate_max": 0.05,
    "hard_subgroup_regression_max_absolute": 0.05,
}

Box = dict[str, float]
Match = tuple[int, int, float]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _git(*args: str) -> str:
    process = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return process.stdout.strip()


def _area(box: Box) -> float:
    return max(0.0, box["x_max"] - box["x_min"]) * max(
        0.0, box["y_max"] - box["y_min"]
    )


def _intersection(a: Box, b: Box) -> float:
    width = max(0.0, min(a["x_max"], b["x_max"]) - max(a["x_min"], b["x_min"]))
    height = max(0.0, min(a["y_max"], b["y_max"]) - max(a["y_min"], b["y_min"]))
    return width * height


def _iou(a: Box, b: Box) -> float:
    intersection = _intersection(a, b)
    union = _area(a) + _area(b) - intersection
    return intersection / union if union else 0.0


def _availability(gold: Box, prediction: Box) -> bool:
    center_x = (prediction["x_min"] + prediction["x_max"]) / 2.0
    center_y = (prediction["y_min"] + prediction["y_max"]) / 2.0
    center_inside = (
        gold["x_min"] <= center_x <= gold["x_max"]
        and gold["y_min"] <= center_y <= gold["y_max"]
    )
    prediction_area = _area(prediction)
    return (
        center_inside
        and prediction_area > 0.0
        and _intersection(gold, prediction) / prediction_area >= 0.50
    )


def _exact_matches(
    gold: list[Box], predictions: list[Box], eligible: Callable[[Box, Box], bool]
) -> list[Match]:
    scores = {
        (gold_index, prediction_index): _iou(gold_box, prediction)
        for gold_index, gold_box in enumerate(gold)
        for prediction_index, prediction in enumerate(predictions)
        if eligible(gold_box, prediction)
    }
    for count in range(min(len(gold), len(predictions)), 0, -1):
        best: list[Match] | None = None
        best_iou = -1.0
        for gold_order in permutations(range(len(gold)), count):
            for prediction_order in permutations(range(len(predictions)), count):
                pairs = list(zip(gold_order, prediction_order, strict=True))
                if not all(pair in scores for pair in pairs):
                    continue
                summed_iou = sum(scores[pair] for pair in pairs)
                if summed_iou > best_iou:
                    best_iou = summed_iou
                    best = [(g, p, scores[(g, p)]) for g, p in pairs]
        if best is not None:
            return best
    return []


def _merged_prediction(gold: list[Box], prediction: Box) -> bool:
    if len(gold) != 2:
        return False
    centers_inside = []
    gold_coverages = []
    for gold_box in gold:
        center_x = (gold_box["x_min"] + gold_box["x_max"]) / 2.0
        center_y = (gold_box["y_min"] + gold_box["y_max"]) / 2.0
        centers_inside.append(
            prediction["x_min"] <= center_x <= prediction["x_max"]
            and prediction["y_min"] <= center_y <= prediction["y_max"]
        )
        gold_area = _area(gold_box)
        gold_coverages.append(
            _intersection(gold_box, prediction) / gold_area if gold_area else 0.0
        )
    return all(centers_inside) or all(value >= 0.50 for value in gold_coverages)


def _duplicate_prediction(
    gold: list[Box], predictions: list[Box], matches: list[Match], prediction_index: int
) -> bool:
    if any(match[1] == prediction_index for match in matches):
        return False
    matched_gold = {match[0] for match in matches}
    return any(
        gold_index in matched_gold and _availability(gold_box, predictions[prediction_index])
        for gold_index, gold_box in enumerate(gold)
    )


def _wilson(successes: int, total: int) -> dict[str, float | int | None]:
    if total == 0:
        return {
            "numerator": successes,
            "denominator": total,
            "rate": None,
            "low": None,
            "high": None,
        }
    z = 1.959963984540054
    observed = successes / total
    denominator = 1.0 + z * z / total
    center = (observed + z * z / (2.0 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            observed * (1.0 - observed) / total
            + z * z / (4.0 * total * total)
        )
        / denominator
    )
    return {
        "numerator": successes,
        "denominator": total,
        "rate": observed,
        "low": max(0.0, center - margin),
        "high": min(1.0, center + margin),
    }


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def _parse_boxes(payload: str) -> list[Box]:
    boxes = json.loads(payload or "[]")
    return [
        {
            "x_min": float(box["x_min"]),
            "y_min": float(box["y_min"]),
            "x_max": float(box["x_max"]),
            "y_max": float(box["y_max"]),
        }
        for box in boxes
    ]


def _load_positive(run: Path) -> list[dict[str, Any]]:
    reviews = {row["sample_id"]: row for row in _read_csv(run / "gold_review.csv")}
    index = {row["sample_id"]: row for row in _read_csv(run / "internal_index.csv")}
    audit = _json(run / "audit_summary.json")
    per_frame = {row["sample_id"]: row for row in audit["per_frame"]}
    if int(audit["accepted_frames"]) != 150:
        raise ValueError("positive benchmark no longer has 150 accepted frames")
    counts = audit["primary"]["counts"]
    if int(counts["gold_instances"]) != 184:
        raise ValueError("positive benchmark no longer has 184 gold instances")
    rows: list[dict[str, Any]] = []
    for sample_id in sorted(reviews):
        review = reviews[sample_id]
        source = index[sample_id]
        canonical = per_frame[sample_id]
        if review["review_status"] != "accepted":
            raise ValueError(f"non-accepted positive row: {sample_id}")
        image_path = Path(source["center_image_path"])
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        gold = _parse_boxes(review["gold_hands_json"])
        if len(gold) != int(review["visible_hand_count"]):
            raise ValueError(f"gold count mismatch: {sample_id}")
        mp_hits = {int(item["gold_index"]) for item in canonical["associations"]}
        rows.append(
            {
                "sample_id": sample_id,
                "kind": "positive",
                "image_path": image_path,
                "participant_id": source["participant_id"],
                "clip_id": source["clip_id"],
                "split": source["split"],
                "gloss": source["gloss"],
                "gold": gold,
                "mp_hits": mp_hits,
                "conditions": {field: review[field] == "yes" for field in CONDITIONS},
                "detected_hands_json": source["detected_hands_json"],
            }
        )
    if len(rows) != 150 or sum(len(row["gold"]) for row in rows) != 184:
        raise ValueError("positive benchmark count validation failed")
    return rows


def _load_negative(run: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in _read_csv(run / "reviewed_manifest.csv"):
        if source["eligible"].lower() != "true":
            continue
        if int(source["visible_hand_count"]) != 0 or json.loads(source["gold_hands_json"]):
            raise ValueError(f"eligible negative contains a visible hand: {source['sample_id']}")
        image_path = Path(source["center_image_path"])
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        rows.append(
            {
                "sample_id": source["sample_id"],
                "kind": "negative",
                "image_path": image_path,
                "participant_id": source["participant_id"],
                "clip_id": source["clip_id"],
                "device_id": source["device_id"],
                "environment_id": source["environment_id"],
                "gold": [],
            }
        )
    if len(rows) != 613:
        raise ValueError(f"expected 613 governed negatives; found {len(rows)}")
    return rows


def _input_manifest(
    positive: list[dict[str, Any]], negative: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        {
            "sample_id": row["sample_id"],
            "kind": row["kind"],
            "participant_id": row["participant_id"],
            "clip_id": row["clip_id"],
            "image_path": str(row["image_path"].resolve()),
            "image_sha256": _sha256(row["image_path"]),
            "gold_hand_count": len(row["gold"]),
        }
        for row in [*positive, *negative]
    ]


def _source_hashes(
    positive_run: Path,
    negative_run: Path,
    model_path: Path,
    input_manifest: Path,
    runner: Path,
) -> list[dict[str, str]]:
    paths = [
        Path(__file__).resolve(),
        runner.resolve(),
        model_path.resolve(),
        (positive_run / "gold_review.csv").resolve(),
        (positive_run / "internal_index.csv").resolve(),
        (positive_run / "audit_summary.json").resolve(),
        (positive_run / "provenance.json").resolve(),
        (negative_run / "gold_review.csv").resolve(),
        (negative_run / "internal_index.csv").resolve(),
        (negative_run / "reviewed_manifest.csv").resolve(),
        (negative_run / "capture_summary.json").resolve(),
        input_manifest.resolve(),
    ]
    return [
        {"path": str(path), "sha256": _sha256(path), "bytes": str(path.stat().st_size)}
        for path in paths
    ]


def prepare(args: argparse.Namespace) -> None:
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    provenance_path = output / "p0_provenance_manifest.json"
    design_path = output / "p0_preregistered_design.json"
    if provenance_path.exists() or design_path.exists():
        raise FileExistsError("P0 provenance/design already frozen; refusing to overwrite")
    positive_run = args.positive.resolve()
    negative_run = args.negative.resolve()
    model_path = (output / args.model_relative).resolve()
    runner = args.runner.resolve()
    positive = _load_positive(positive_run)
    negative = _load_negative(negative_run)
    input_rows = _input_manifest(positive, negative)
    input_path = output / "p0_input_manifest.csv"
    _write_csv(
        input_path,
        input_rows,
        [
            "sample_id",
            "kind",
            "participant_id",
            "clip_id",
            "image_path",
            "image_sha256",
            "gold_hand_count",
        ],
    )
    baseline = _json(positive_run / "audit_summary.json")["primary"]
    design = {
        "experiment": EXPERIMENT,
        "candidate": {
            "identity": "rtmdet_nano_8xb32-300e_hand-267f9c8f",
            "architecture": "RTMDet nano; CSPNeXt-family depthwise detector; one hand class",
            "input_size": [320, 320],
            "score_threshold": SCORE_THRESHOLD,
            "threshold_policy": "documented rtmlib default only; no AppHear sweep",
            "export_candidate_threshold": EXPORT_CANDIDATE_THRESHOLD,
            "baked_nms_iou": BAKED_NMS_IOU,
            "max_outputs": MAX_OUTPUTS,
        },
        "preprocessing": {
            "decoder": "OpenCV BGR",
            "resize": "keep aspect ratio to 320x320",
            "placement": "top-left",
            "padding": "bottom/right BGR 114,114,114",
            "normalization_mean_bgr": MEAN_BGR.tolist(),
            "normalization_std_bgr": STD_BGR.tolist(),
            "layout": "NCHW float32",
        },
        "matching": {
            "primary_availability": (
                "prediction center inside gold and >=50% of prediction area inside gold"
            ),
            "assignment": "exact maximum-cardinality one-to-one, maximum summed IoU tie-break",
            "iou_diagnostics": [0.5, 0.75],
            "duplicate": "unmatched prediction availability-eligible for an already matched hand",
            "merged_two_hand": (
                "one prediction contains both gold centers or covers >=50% of each gold area"
            ),
        },
        "datasets": {
            "positive_frames": len(positive),
            "positive_signers": len({row["participant_id"] for row in positive}),
            "gold_instances": sum(len(row["gold"]) for row in positive),
            "negative_frames": len(negative),
            "negative_participants": len({row["participant_id"] for row in negative}),
            "negative_devices": len({row["device_id"] for row in negative}),
            "negative_environments": len({row["environment_id"] for row in negative}),
            "contact_body_overlap_truth": "NOT_AVAILABLE_IN_FROZEN_POSITIVE_GOLD",
        },
        "verified_mediapipe_baseline": baseline,
        "gates": GATES,
        "decision_labels": [
            "PROMOTE_P0_TO_P1",
            "REJECT_RTMDET_P0",
            "INCONCLUSIVE_P0",
        ],
    }
    _write_json(design_path, design)
    provenance = {
        "experiment": EXPERIMENT,
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "branch": _git("branch", "--show-current"),
        "head": _git("rev-parse", "HEAD"),
        "working_tree_status": _git("status", "--short"),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "opencv": cv2.__version__,
            "onnxruntime": ort.__version__,
            "providers": ort.get_available_providers(),
            "cpu_count": os.cpu_count(),
        },
        "source_hashes": _source_hashes(
            positive_run, negative_run, model_path, input_path, runner
        ),
        "model_sha256": _sha256(model_path),
        "model_bytes": model_path.stat().st_size,
        "design_sha256": _sha256(design_path),
    }
    _write_json(provenance_path, provenance)
    print(json.dumps({"prepared": True, "output": str(output), **design["datasets"]}, indent=2))


def _verify_provenance(output: Path) -> dict[str, Any]:
    provenance = cast(dict[str, Any], _json(output / "p0_provenance_manifest.json"))
    for item in provenance["source_hashes"]:
        path = Path(item["path"])
        if not path.is_file() or _sha256(path) != item["sha256"]:
            raise ValueError(f"frozen source hash mismatch: {path}")
    design_path = output / "p0_preregistered_design.json"
    if _sha256(design_path) != provenance["design_sha256"]:
        raise ValueError("preregistered design hash mismatch")
    return provenance


def _preprocess(image: np.ndarray) -> tuple[np.ndarray, float]:
    height, width = image.shape[:2]
    ratio = min(INPUT_SIZE / height, INPUT_SIZE / width)
    resized_width = int(width * ratio)
    resized_height = int(height * ratio)
    resized = cv2.resize(
        image, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR
    ).astype(np.uint8)
    padded = np.full((INPUT_SIZE, INPUT_SIZE, 3), 114, dtype=np.uint8)
    padded[:resized_height, :resized_width] = resized
    normalized = (padded.astype(np.float32) - MEAN_BGR) / STD_BGR
    tensor = normalized.transpose(2, 0, 1)[None].astype(np.float32, copy=False)
    return tensor, ratio


def _infer(
    session: ort.InferenceSession, image: np.ndarray
) -> tuple[list[Box], dict[str, float]]:
    start = time.perf_counter_ns()
    tensor, ratio = _preprocess(image)
    pre_end = time.perf_counter_ns()
    dets, labels = session.run(None, {"input": tensor})
    inference_end = time.perf_counter_ns()
    boxes: list[Box] = []
    height, width = image.shape[:2]
    for det, label in zip(dets[0], labels[0], strict=True):
        confidence = float(det[4])
        if int(label) != 0 or not confidence > SCORE_THRESHOLD:
            continue
        x_min, y_min, x_max, y_max = (float(value) / ratio for value in det[:4])
        boxes.append(
            {
                "x_min": min(1.0, max(0.0, x_min / width)),
                "y_min": min(1.0, max(0.0, y_min / height)),
                "x_max": min(1.0, max(0.0, x_max / width)),
                "y_max": min(1.0, max(0.0, y_max / height)),
                "confidence": confidence,
            }
        )
    boxes.sort(key=lambda box: box["confidence"], reverse=True)
    post_end = time.perf_counter_ns()
    return boxes, {
        "preprocess_ms": (pre_end - start) / 1e6,
        "detector_ms": (inference_end - pre_end) / 1e6,
        "postprocess_ms": (post_end - inference_end) / 1e6,
    }


def _subgroup_names(row: dict[str, Any]) -> list[str]:
    names = []
    conditions = row["conditions"]
    if not conditions["motion_blur"]:
        names.append("clear")
    names.extend(name for name in CONDITIONS if conditions[name])
    if len(row["gold"]) == 2:
        names.append("two_hand")
    return names


def _metric_record(counter: Counter[str]) -> dict[str, Any]:
    return {
        "frames": counter["frames"],
        "gold_instances": counter["gold"],
        "matched_instances": counter["matched"],
        "visible_hand_recall": _wilson(counter["matched"], counter["gold"]),
        "two_hand_frames": counter["two_hand_frames"],
        "complete_two_hand": counter["complete_two_hand"],
        "complete_two_hand_recall": _wilson(
            counter["complete_two_hand"], counter["two_hand_frames"]
        ),
    }


def _latency_summary(values: list[float]) -> dict[str, float | None]:
    return {
        "mean": statistics.fmean(values) if values else None,
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "max": max(values) if values else None,
    }


def _draw_box(image: np.ndarray, box: Box, color: tuple[int, int, int], text: str) -> None:
    height, width = image.shape[:2]
    p1 = (int(box["x_min"] * width), int(box["y_min"] * height))
    p2 = (int(box["x_max"] * width), int(box["y_max"] * height))
    cv2.rectangle(image, p1, p2, color, 2)
    cv2.putText(
        image,
        text,
        (p1[0], max(14, p1[1] - 4)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        color,
        1,
        cv2.LINE_AA,
    )


def _make_sheet(
    output: Path,
    name: str,
    items: list[dict[str, Any]],
    predictions: dict[str, list[Box]],
    max_items: int = 30,
) -> Path | None:
    if not items:
        return None
    cells: list[np.ndarray] = []
    for item in items[:max_items]:
        image = cv2.imread(str(item["image_path"]), cv2.IMREAD_COLOR)
        if image is None:
            continue
        for index, box in enumerate(item["gold"]):
            _draw_box(image, box, (0, 255, 0), f"G{index}")
        for index, box in enumerate(predictions[item["sample_id"]]):
            _draw_box(image, box, (0, 0, 255), f"R{index}:{box['confidence']:.2f}")
        image = cv2.resize(image, (320, 240), interpolation=cv2.INTER_AREA)
        cv2.rectangle(image, (0, 0), (320, 24), (0, 0, 0), -1)
        cv2.putText(
            image,
            item["sample_id"],
            (6, 17),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        cells.append(image)
    if not cells:
        return None
    columns = 5
    rows = math.ceil(len(cells) / columns)
    blank = np.zeros_like(cells[0])
    cells.extend(blank.copy() for _ in range(rows * columns - len(cells)))
    sheet = np.vstack(
        [np.hstack(cells[row * columns : (row + 1) * columns]) for row in range(rows)]
    )
    path = output / "failure_panels" / f"{name}.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return path


def _score(
    positive: list[dict[str, Any]],
    negative: list[dict[str, Any]],
    predictions: dict[str, list[Box]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    counts: Counter[str] = Counter()
    subgroup_counts: dict[str, Counter[str]] = defaultdict(Counter)
    pairwise: Counter[str] = Counter()
    miss_hit_conditions: Counter[str] = Counter()
    ious: list[float] = []
    paired_rows: list[dict[str, Any]] = []
    frame_rows: list[dict[str, Any]] = []
    panel_rows: list[dict[str, Any]] = []

    for row in positive:
        gold = row["gold"]
        frame_predictions = predictions[row["sample_id"]]
        matches = _exact_matches(gold, frame_predictions, _availability)
        match_by_gold = {g: (p, iou) for g, p, iou in matches}
        iou50 = _exact_matches(gold, frame_predictions, lambda a, b: _iou(a, b) >= 0.50)
        iou75 = _exact_matches(gold, frame_predictions, lambda a, b: _iou(a, b) >= 0.75)
        duplicate_indices = [
            index
            for index in range(len(frame_predictions))
            if _duplicate_prediction(gold, frame_predictions, matches, index)
        ]
        merged = len(gold) == 2 and any(
            _merged_prediction(gold, prediction) for prediction in frame_predictions
        )
        matched_prediction_indices = {match[1] for match in matches}
        false_prediction_indices = [
            index
            for index in range(len(frame_predictions))
            if index not in matched_prediction_indices and index not in duplicate_indices
        ]

        counts["positive_frames"] += 1
        counts["gold"] += len(gold)
        counts["predictions"] += len(frame_predictions)
        counts["matched"] += len(matches)
        counts["iou50"] += len(iou50)
        counts["iou75"] += len(iou75)
        counts["duplicates"] += len(duplicate_indices)
        counts["false_predictions"] += len(false_prediction_indices)
        if gold:
            counts["visible_frames"] += 1
            counts["any_hand_hits"] += int(bool(matches))
        if len(gold) == 2:
            counts["two_hand_frames"] += 1
            counts["complete_two_hand"] += int(len(matches) == 2)
            counts["merged_two_hand_frames"] += int(merged)
        ious.extend(match[2] for match in matches)

        for subgroup in _subgroup_names(row):
            subgroup_counts[subgroup]["frames"] += 1
            subgroup_counts[subgroup]["gold"] += len(gold)
            subgroup_counts[subgroup]["matched"] += len(matches)
            if len(gold) == 2:
                subgroup_counts[subgroup]["two_hand_frames"] += 1
                subgroup_counts[subgroup]["complete_two_hand"] += int(len(matches) == 2)

        for gold_index in range(len(gold)):
            mp_hit = gold_index in row["mp_hits"]
            rtmdet_hit = gold_index in match_by_gold
            category = (
                "MP_HIT_RTMDET_HIT"
                if mp_hit and rtmdet_hit
                else "MP_HIT_RTMDET_MISS"
                if mp_hit
                else "MP_MISS_RTMDET_HIT"
                if rtmdet_hit
                else "BOTH_MISS"
            )
            pairwise[category] += 1
            if category == "MP_MISS_RTMDET_HIT":
                active = [name for name in CONDITIONS if row["conditions"][name]]
                if not active:
                    miss_hit_conditions["other"] += 1
                for name in active:
                    miss_hit_conditions[name] += 1
            matched = match_by_gold.get(gold_index)
            paired_rows.append(
                {
                    "sample_id": row["sample_id"],
                    "gold_index": gold_index,
                    "pairwise_category": category,
                    "mediapipe_hit": mp_hit,
                    "rtmdet_hit": rtmdet_hit,
                    "rtmdet_prediction_index": matched[0] if matched else "",
                    "matched_iou": matched[1] if matched else "",
                    **{name: row["conditions"][name] for name in CONDITIONS},
                }
            )
        frame_rows.append(
            {
                "sample_id": row["sample_id"],
                "kind": "positive",
                "gold_count": len(gold),
                "prediction_count": len(frame_predictions),
                "matched_count": len(matches),
                "duplicate_count": len(duplicate_indices),
                "false_detection_count": len(false_prediction_indices),
                "merged_two_hand": merged,
                "complete_two_hand": len(gold) == 2 and len(matches) == 2,
            }
        )
        if any(index not in match_by_gold for index in range(len(gold))):
            panel_rows.append({**row, "panel_category": "RTMDET_MISS"})
        if any(
            item["pairwise_category"] == "MP_MISS_RTMDET_HIT"
            and item["sample_id"] == row["sample_id"]
            for item in paired_rows[-len(gold) :]
        ):
            panel_rows.append({**row, "panel_category": "MP_MISS_RTMDET_HIT"})
        if merged or duplicate_indices:
            panel_rows.append({**row, "panel_category": "MERGED_OR_DUPLICATE"})

    for row in negative:
        frame_predictions = predictions[row["sample_id"]]
        counts["negative_frames"] += 1
        counts["negative_predictions"] += len(frame_predictions)
        counts["negative_false_frames"] += int(bool(frame_predictions))
        counts["predictions"] += len(frame_predictions)
        counts["false_predictions"] += len(frame_predictions)
        frame_rows.append(
            {
                "sample_id": row["sample_id"],
                "kind": "negative",
                "gold_count": 0,
                "prediction_count": len(frame_predictions),
                "matched_count": 0,
                "duplicate_count": 0,
                "false_detection_count": len(frame_predictions),
                "merged_two_hand": False,
                "complete_two_hand": False,
            }
        )
        if frame_predictions:
            panel_rows.append({**row, "panel_category": "NEGATIVE_FALSE_POSITIVE"})

    subgroup_metrics = {
        name: _metric_record(subgroup_counts[name]) for name in SUBGROUPS
    }
    metrics = {
        "counts": dict(counts),
        "visible_hand_instance_recall": _wilson(counts["matched"], counts["gold"]),
        "any_hand_frame_coverage": _wilson(
            counts["any_hand_hits"], counts["visible_frames"]
        ),
        "complete_two_hand_recall": _wilson(
            counts["complete_two_hand"], counts["two_hand_frames"]
        ),
        "hand_instance_precision": _wilson(counts["matched"], counts["predictions"]),
        "false_detections_per_frame": counts["false_predictions"]
        / (counts["positive_frames"] + counts["negative_frames"]),
        "no_hand_false_presence_rate": _wilson(
            counts["negative_false_frames"], counts["negative_frames"]
        ),
        "duplicate_prediction_rate": _wilson(
            counts["duplicates"], counts["predictions"]
        ),
        "two_hands_merged_rate": _wilson(
            counts["merged_two_hand_frames"], counts["two_hand_frames"]
        ),
        "iou50_recall": _wilson(counts["iou50"], counts["gold"]),
        "iou75_recall": _wilson(counts["iou75"], counts["gold"]),
        "matched_iou": {
            "p50": _percentile(ious, 0.50),
            "p95": _percentile(ious, 0.95),
            "min": min(ious) if ious else None,
            "max": max(ious) if ious else None,
        },
        "subgroups": subgroup_metrics,
        "pairwise": {
            "counts": dict(pairwise),
            "mediapipe_miss_rtmdet_hit": _wilson(
                pairwise["MP_MISS_RTMDET_HIT"], counts["gold"]
            ),
            "mediapipe_miss_rtmdet_hit_condition_counts_overlapping": dict(
                miss_hit_conditions
            ),
        },
        "contact_body_overlap": "NOT_AVAILABLE_IN_FROZEN_GOLD",
    }
    return metrics, paired_rows, frame_rows, panel_rows


def _baseline_subgroups(positive: list[dict[str, Any]]) -> dict[str, float | None]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in positive:
        for name in _subgroup_names(row):
            counts[name]["gold"] += len(row["gold"])
            counts[name]["matched"] += len(row["mp_hits"])
    return {
        name: (
            counts[name]["matched"] / counts[name]["gold"]
            if counts[name]["gold"]
            else None
        )
        for name in SUBGROUPS
    }


def _decide(metrics: dict[str, Any], baseline_subgroups: dict[str, float | None]) -> dict[str, Any]:
    subgroup_rates = {
        name: value["visible_hand_recall"]["rate"]
        for name, value in metrics["subgroups"].items()
    }
    regressions = {
        name: subgroup_rates[name] - baseline
        for name, baseline in baseline_subgroups.items()
        if baseline is not None and subgroup_rates[name] is not None
    }
    gate_results = {
        "visible_hand_recall": metrics["visible_hand_instance_recall"]["rate"]
        >= GATES["visible_hand_recall_min"],
        "complete_two_hand_recall": metrics["complete_two_hand_recall"]["rate"]
        >= GATES["complete_two_hand_recall_min"],
        "blur_improvement": regressions["motion_blur"]
        >= GATES["blur_improvement_min_absolute"],
        "occlusion_improvement": regressions["occlusion"]
        >= GATES["occlusion_improvement_min_absolute"],
        "no_hand_false_presence": metrics["no_hand_false_presence_rate"]["rate"]
        <= GATES["no_hand_false_presence_max"],
        "duplicate_predictions": metrics["duplicate_prediction_rate"]["rate"]
        <= GATES["duplicate_prediction_rate_max"],
        "merged_two_hand": metrics["two_hands_merged_rate"]["rate"]
        <= GATES["two_hands_merged_rate_max"],
        "no_hard_subgroup_regression": all(
            delta >= -GATES["hard_subgroup_regression_max_absolute"]
            for delta in regressions.values()
        ),
    }
    passed = all(gate_results.values())
    return {
        "gates": gate_results,
        "subgroup_absolute_deltas_vs_mediapipe": regressions,
        "passed": passed,
        "decision": "PROMOTE_P0_TO_P1" if passed else "REJECT_RTMDET_P0",
    }


def evaluate(args: argparse.Namespace) -> None:
    output = args.output.resolve()
    provenance = _verify_provenance(output)
    positive = _load_positive(args.positive.resolve())
    negative = _load_negative(args.negative.resolve())
    model_path = (output / args.model_relative).resolve()
    session_options = ort.SessionOptions()
    session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(
        str(model_path), sess_options=session_options, providers=["CPUExecutionProvider"]
    )
    first_image = cv2.imread(str(positive[0]["image_path"]), cv2.IMREAD_COLOR)
    if first_image is None:
        raise ValueError("warm-up image cannot be decoded")
    for _ in range(20):
        _infer(session, first_image)

    predictions: dict[str, list[Box]] = {}
    timings: dict[str, list[float]] = defaultdict(list)
    detection_rows: list[dict[str, Any]] = []
    for index, row in enumerate([*positive, *negative], start=1):
        image = cv2.imread(str(row["image_path"]), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"image cannot be decoded: {row['image_path']}")
        boxes, per_image_latency = _infer(session, image)
        predictions[row["sample_id"]] = boxes
        for name, value in per_image_latency.items():
            timings[name].append(value)
        for prediction_index, box in enumerate(boxes):
            detection_rows.append(
                {
                    "sample_id": row["sample_id"],
                    "kind": row["kind"],
                    "prediction_index": prediction_index,
                    **box,
                }
            )
        if index % 100 == 0:
            print(f"scored {index}/{len(positive) + len(negative)}")

    metrics, paired_rows, frame_rows, panel_rows = _score(
        positive, negative, predictions
    )
    baseline_audit = _json(args.positive.resolve() / "audit_summary.json")
    baseline_subgroups = _baseline_subgroups(positive)
    decision = _decide(metrics, baseline_subgroups)
    latency_summary = {
        name: _latency_summary(values) for name, values in timings.items()
    }
    latency_summary["total_ms"] = _latency_summary(
        [
            timings["preprocess_ms"][index]
            + timings["detector_ms"][index]
            + timings["postprocess_ms"][index]
            for index in range(len(timings["detector_ms"]))
        ]
    )

    _write_csv(
        output / "raw_detections.csv",
        detection_rows,
        [
            "sample_id",
            "kind",
            "prediction_index",
            "confidence",
            "x_min",
            "y_min",
            "x_max",
            "y_max",
        ],
    )
    _write_csv(
        output / "paired_mediapipe_vs_rtmdet.csv",
        paired_rows,
        [
            "sample_id",
            "gold_index",
            "pairwise_category",
            "mediapipe_hit",
            "rtmdet_hit",
            "rtmdet_prediction_index",
            "matched_iou",
            *CONDITIONS,
        ],
    )
    _write_csv(
        output / "frame_safety_and_merge_table.csv",
        frame_rows,
        [
            "sample_id",
            "kind",
            "gold_count",
            "prediction_count",
            "matched_count",
            "duplicate_count",
            "false_detection_count",
            "merged_two_hand",
            "complete_two_hand",
        ],
    )
    subgroup_rows = []
    for name, value in metrics["subgroups"].items():
        subgroup_rows.append(
            {
                "subgroup": name,
                "gold_instances": value["gold_instances"],
                "matched_instances": value["matched_instances"],
                "rtmdet_recall": value["visible_hand_recall"]["rate"],
                "rtmdet_ci_low": value["visible_hand_recall"]["low"],
                "rtmdet_ci_high": value["visible_hand_recall"]["high"],
                "mediapipe_recall": baseline_subgroups[name],
                "absolute_delta": decision["subgroup_absolute_deltas_vs_mediapipe"].get(name),
                "two_hand_frames": value["two_hand_frames"],
                "complete_two_hand": value["complete_two_hand"],
                "complete_two_hand_rate": value["complete_two_hand_recall"]["rate"],
            }
        )
    _write_csv(
        output / "subgroup_table.csv",
        subgroup_rows,
        [
            "subgroup",
            "gold_instances",
            "matched_instances",
            "rtmdet_recall",
            "rtmdet_ci_low",
            "rtmdet_ci_high",
            "mediapipe_recall",
            "absolute_delta",
            "two_hand_frames",
            "complete_two_hand",
            "complete_two_hand_rate",
        ],
    )
    negative_rows = [row for row in frame_rows if row["kind"] == "negative"]
    _write_csv(
        output / "negative_set_safety_table.csv",
        negative_rows,
        [
            "sample_id",
            "prediction_count",
            "false_detection_count",
        ],
    )

    panel_index: list[dict[str, Any]] = []
    for category in (
        "MP_MISS_RTMDET_HIT",
        "RTMDET_MISS",
        "NEGATIVE_FALSE_POSITIVE",
        "MERGED_OR_DUPLICATE",
    ):
        items = [row for row in panel_rows if row["panel_category"] == category]
        sheet = _make_sheet(output, category.lower(), items, predictions)
        for row in items:
            panel_index.append(
                {
                    "sample_id": row["sample_id"],
                    "category": category,
                    "image_path": str(row["image_path"]),
                    "sheet_path": str(sheet) if sheet else "",
                }
            )
    _write_csv(
        output / "failure_panel_index.csv",
        panel_index,
        ["sample_id", "category", "image_path", "sheet_path"],
    )

    result = {
        "experiment": EXPERIMENT,
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "provenance_sha256": _sha256(output / "p0_provenance_manifest.json"),
        "design_sha256": provenance["design_sha256"],
        "model": {
            "identity": "rtmdet_nano_8xb32-300e_hand-267f9c8f",
            "sha256": provenance["model_sha256"],
            "bytes": provenance["model_bytes"],
            "runtime": "onnxruntime CPUExecutionProvider",
            "threshold": SCORE_THRESHOLD,
            "baked_nms_iou": BAKED_NMS_IOU,
        },
        "datasets": {
            "positive_frames": len(positive),
            "positive_signers": len({row["participant_id"] for row in positive}),
            "gold_instances": sum(len(row["gold"]) for row in positive),
            "negative_frames": len(negative),
            "negative_participants": len({row["participant_id"] for row in negative}),
            "negative_devices": len({row["device_id"] for row in negative}),
            "negative_environments": len({row["environment_id"] for row in negative}),
        },
        "verified_mediapipe_baseline": baseline_audit["primary"],
        "rtmdet": metrics,
        "desktop_diagnostic_latency_ms": latency_summary,
        "gate_evaluation": decision,
        "claim_boundary": (
            "Detector boxes only; no landmark, 3D, S4, recognition, or Android claim."
        ),
    }
    _write_json(output / "p0_rtmdet_detector_result.json", result)
    print(json.dumps({"decision": decision["decision"], "metrics": metrics}, indent=2))


def check(args: argparse.Namespace) -> None:
    output = args.output.resolve()
    _verify_provenance(output)
    required = [
        "p0_preregistered_design.json",
        "p0_provenance_manifest.json",
        "p0_input_manifest.csv",
        "p0_rtmdet_detector_result.json",
        "raw_detections.csv",
        "paired_mediapipe_vs_rtmdet.csv",
        "subgroup_table.csv",
        "negative_set_safety_table.csv",
        "frame_safety_and_merge_table.csv",
        "failure_panel_index.csv",
    ]
    missing = [name for name in required if not (output / name).is_file()]
    result = _json(output / "p0_rtmdet_detector_result.json") if not missing else {}
    errors = list(missing)
    if result:
        if result["gate_evaluation"]["decision"] not in {
            "PROMOTE_P0_TO_P1",
            "REJECT_RTMDET_P0",
            "INCONCLUSIVE_P0",
        }:
            errors.append("invalid decision label")
        if result["datasets"]["positive_frames"] != 150:
            errors.append("positive frame count changed")
        if result["datasets"]["gold_instances"] != 184:
            errors.append("gold instance count changed")
        if result["datasets"]["negative_frames"] < 200:
            errors.append("fewer than 200 governed negatives")
    summary = {"required_files": len(required), "errors": errors, "passed": not errors}
    _write_json(output / "p0_check_summary.json", summary)
    print(json.dumps(summary, indent=2))
    if errors:
        raise SystemExit(1)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("command", choices=("prepare", "evaluate", "check"))
    result.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    result.add_argument("--positive", type=Path, default=DEFAULT_POSITIVE)
    result.add_argument("--negative", type=Path, default=DEFAULT_NEGATIVE)
    result.add_argument("--model-relative", type=Path, default=DEFAULT_MODEL_RELATIVE)
    result.add_argument("--runner", type=Path, default=DEFAULT_RUNNER)
    return result


def main() -> None:
    args = parser().parse_args()
    {"prepare": prepare, "evaluate": evaluate, "check": check}[args.command](args)


if __name__ == "__main__":
    main()
