"""Evaluate C0-B0 detector candidates on signer-disjoint development data."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import datetime
from itertools import permutations
from pathlib import Path
from typing import Any, cast

import cv2

from pipeline.tracking.e2e_c0b import _read_csv, _write_csv, _write_json
from pipeline.tracking.e2e_c0b_stage2_train import _sha256

EXPERIMENT = "c0b_stage2_development_threshold_v1"
DEFAULT_RUN = Path("artifacts/recognition_upgrade/e2e_c0/c0b_stage2_detector_01")
DEFAULT_MANIFEST_RUN = Path(
    "artifacts/recognition_upgrade/e2e_c0/c0b_stage2_research_manifest_01"
)
CONDITIONS = (
    "motion_blur",
    "occlusion",
    "near_face",
    "edge_clipped",
    "partial_visibility",
)
Box = dict[str, Any]
Match = tuple[int, int, float]


def _intersection(a: Box, b: Box) -> float:
    width = max(
        0.0,
        min(float(a["x_max"]), float(b["x_max"]))
        - max(float(a["x_min"]), float(b["x_min"])),
    )
    height = max(
        0.0,
        min(float(a["y_max"]), float(b["y_max"]))
        - max(float(a["y_min"]), float(b["y_min"])),
    )
    return width * height


def _area(box: Box) -> float:
    return max(0.0, float(box["x_max"]) - float(box["x_min"])) * max(
        0.0, float(box["y_max"]) - float(box["y_min"])
    )


def _iou(a: Box, b: Box) -> float:
    intersection = _intersection(a, b)
    union = _area(a) + _area(b) - intersection
    return intersection / union if union else 0.0


def _availability(gold: Box, prediction: Box) -> bool:
    center_x = (float(prediction["x_min"]) + float(prediction["x_max"])) / 2.0
    center_y = (float(prediction["y_min"]) + float(prediction["y_max"])) / 2.0
    center_inside = (
        float(gold["x_min"]) <= center_x <= float(gold["x_max"])
        and float(gold["y_min"]) <= center_y <= float(gold["y_max"])
    )
    predicted_area = _area(prediction)
    return (
        center_inside
        and predicted_area > 0
        and _intersection(gold, prediction) / predicted_area >= 0.50
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
            observed * (1.0 - observed) / total + z * z / (4.0 * total * total)
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


def _expanded_contains(gold: Box, prediction: Box, expansion: float) -> bool:
    center_x = (float(prediction["x_min"]) + float(prediction["x_max"])) / 2.0
    center_y = (float(prediction["y_min"]) + float(prediction["y_max"])) / 2.0
    half_width = (float(prediction["x_max"]) - float(prediction["x_min"])) * expansion / 2.0
    half_height = (float(prediction["y_max"]) - float(prediction["y_min"])) * expansion / 2.0
    expanded = {
        "x_min": max(0.0, center_x - half_width),
        "y_min": max(0.0, center_y - half_height),
        "x_max": min(1.0, center_x + half_width),
        "y_max": min(1.0, center_y + half_height),
    }
    return (
        float(expanded["x_min"]) <= float(gold["x_min"])
        and float(expanded["y_min"]) <= float(gold["y_min"])
        and float(expanded["x_max"]) >= float(gold["x_max"])
        and float(expanded["y_max"]) >= float(gold["y_max"])
    )


def _load_development(run_dir: Path, manifest_run: Path) -> list[dict[str, Any]]:
    root = run_dir / "coco" / "development"
    coco = json.loads((root / "labels.json").read_text(encoding="utf-8"))
    manifest = {
        row["sample_id"]: row
        for row in _read_csv(manifest_run / "stage2_manifest.csv")
        if row["dataset_split"] == "development"
    }
    annotations: dict[int, list[Box]] = defaultdict(list)
    images = {int(image["id"]): image for image in coco["images"]}
    for annotation in coco["annotations"]:
        image = images[int(annotation["image_id"])]
        x, y, width, height = (float(value) for value in annotation["bbox"])
        annotations[int(annotation["image_id"])].append(
            {
                "x_min": x / float(image["width"]),
                "y_min": y / float(image["height"]),
                "x_max": (x + width) / float(image["width"]),
                "y_max": (y + height) / float(image["height"]),
            }
        )
    rows: list[dict[str, Any]] = []
    for image_id, image in sorted(images.items()):
        sample_id = image["sample_id"]
        metadata = manifest.get(sample_id)
        if metadata is None:
            raise ValueError(f"development sample absent from locked manifest: {sample_id}")
        rows.append(
            {
                **metadata,
                "image_path": str((root / "images" / image["file_name"]).resolve()),
                "gold": annotations[image_id],
            }
        )
    return rows


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def _score_rows(
    rows: list[dict[str, Any]],
    predictions_by_id: dict[str, dict[str, Any]],
    threshold: float,
    expansion: float,
) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    subgroup_counts: dict[str, Counter[str]] = defaultdict(Counter)
    gold_coverages: list[float] = []
    for row in rows:
        gold = row["gold"]
        predictions = [
            box
            for box in predictions_by_id[row["sample_id"]]["detections"]
            if float(box["confidence"]) >= threshold
        ][:4]
        availability = _exact_matches(gold, predictions, _availability)
        iou50 = _exact_matches(gold, predictions, lambda a, b: _iou(a, b) >= 0.50)
        iou75 = _exact_matches(gold, predictions, lambda a, b: _iou(a, b) >= 0.75)
        counts["frames"] += 1
        counts["gold"] += len(gold)
        counts["predictions"] += len(predictions)
        counts["available"] += len(availability)
        counts["iou50"] += len(iou50)
        counts["iou75"] += len(iou75)
        counts["unmatched_predictions"] += len(predictions) - len(availability)
        counts["expanded_contains"] += sum(
            _expanded_contains(gold[g], predictions[p], expansion) for g, p, _ in availability
        )
        for gold_index, prediction_index, _ in availability:
            intersection = _intersection(gold[gold_index], predictions[prediction_index])
            gold_coverages.append(intersection / _area(gold[gold_index]))
        if gold:
            counts["visible_frames"] += 1
            counts["any_hand_hits"] += int(bool(availability))
        else:
            counts["negative_frames"] += 1
            counts["negative_false_frames"] += int(bool(predictions))
        if len(gold) == 2:
            counts["two_hand_frames"] += 1
            counts["complete_two_hand"] += int(len(availability) == 2)
        subgroup_names = [
            f"source={row['source_dataset']}",
            f"hand_count={len(gold)}",
            *(f"{field}=yes" for field in CONDITIONS if row[field] == "yes"),
        ]
        for name in subgroup_names:
            subgroup_counts[name]["frames"] += 1
            subgroup_counts[name]["gold"] += len(gold)
            subgroup_counts[name]["available"] += len(availability)
            subgroup_counts[name]["iou50"] += len(iou50)
            if len(gold) == 2:
                subgroup_counts[name]["two_hand_frames"] += 1
                subgroup_counts[name]["complete_two_hand"] += int(len(availability) == 2)
    subgroups: dict[str, Any] = {}
    for name, subgroup in sorted(subgroup_counts.items()):
        subgroups[name] = {
            "frames": subgroup["frames"],
            "availability": _wilson(subgroup["available"], subgroup["gold"]),
            "iou50_recall": _wilson(subgroup["iou50"], subgroup["gold"]),
            "complete_two_hand_recall": _wilson(
                subgroup["complete_two_hand"], subgroup["two_hand_frames"]
            ),
        }
    metrics: dict[str, Any] = {
        "threshold": threshold,
        "availability": _wilson(counts["available"], counts["gold"]),
        "any_hand_frame_recall": _wilson(counts["any_hand_hits"], counts["visible_frames"]),
        "complete_two_hand_recall": _wilson(counts["complete_two_hand"], counts["two_hand_frames"]),
        "iou50_recall": _wilson(counts["iou50"], counts["gold"]),
        "iou75_recall": _wilson(counts["iou75"], counts["gold"]),
        "negative_frame_false_positive_rate": _wilson(
            counts["negative_false_frames"], counts["negative_frames"]
        ),
        "expanded_crop_containment": _wilson(counts["expanded_contains"], counts["gold"]),
        "mean_gold_box_coverage_on_availability_matches": (
            statistics.fmean(gold_coverages) if gold_coverages else None
        ),
        "prediction_count": counts["predictions"],
        "unmatched_prediction_count": counts["unmatched_predictions"],
        "subgroups": subgroups,
    }
    return metrics


def _curve_fields() -> tuple[str, ...]:
    return (
        "threshold",
        "availability_recall",
        "availability_numerator",
        "availability_denominator",
        "complete_two_hand_recall",
        "iou50_recall",
        "iou75_recall",
        "negative_frame_false_positive_rate",
        "prediction_count",
        "unmatched_prediction_count",
    )


def _curve_row(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "threshold": metrics["threshold"],
        "availability_recall": metrics["availability"]["rate"],
        "availability_numerator": metrics["availability"]["numerator"],
        "availability_denominator": metrics["availability"]["denominator"],
        "complete_two_hand_recall": metrics["complete_two_hand_recall"]["rate"],
        "iou50_recall": metrics["iou50_recall"]["rate"],
        "iou75_recall": metrics["iou75_recall"]["rate"],
        "negative_frame_false_positive_rate": metrics["negative_frame_false_positive_rate"]["rate"],
        "prediction_count": metrics["prediction_count"],
        "unmatched_prediction_count": metrics["unmatched_prediction_count"],
    }


def _select_threshold(curve: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [
        item
        for item in curve
        if item["negative_frame_false_positive_rate"]["rate"] is not None
        and item["negative_frame_false_positive_rate"]["rate"] <= 0.02
    ]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda item: (
            item["availability"]["rate"] or 0.0,
            item["complete_two_hand_recall"]["rate"] or 0.0,
            item["iou50_recall"]["rate"] or 0.0,
            item["threshold"],
        ),
    )


def run_model(args: argparse.Namespace) -> dict[str, Any]:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    rows = _load_development(args.run_dir, args.manifest_run)
    model_path = args.model.resolve()
    output = args.run_dir / "development_evaluation" / args.candidate
    summary_path = output / "development_metrics.json"
    if summary_path.is_file():
        summary = cast(
            dict[str, Any], json.loads(summary_path.read_text(encoding="utf-8"))
        )
        print(json.dumps({**summary, "resumed": True}, indent=2))
        return summary
    if output.exists():
        if not args.retry_incomplete:
            raise FileExistsError(
                f"incomplete candidate exists: {output}; inspect it, then rerun with "
                "--retry-incomplete"
            )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output.rename(output.with_name(f"{output.name}.incomplete.{timestamp}"))
    output.mkdir(parents=True, exist_ok=False)
    options = vision.ObjectDetectorOptions(
        base_options=python.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.IMAGE,
        max_results=4,
        score_threshold=0.01,
    )
    records: list[dict[str, Any]] = []
    preprocessing_times: list[float] = []
    inference_times: list[float] = []
    with vision.ObjectDetector.create_from_options(options) as detector:
        for index, row in enumerate(rows):
            preprocessing_started = time.perf_counter()
            image = cv2.imread(row["image_path"])
            if image is None:
                raise OSError(f"cannot read {row['image_path']}")
            height, width = image.shape[:2]
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            preprocessing_ms = (time.perf_counter() - preprocessing_started) * 1000.0
            if index == 0:
                for _ in range(3):
                    detector.detect(mp_image)
            inference_started = time.perf_counter()
            result = detector.detect(mp_image)
            inference_ms = (time.perf_counter() - inference_started) * 1000.0
            detections: list[Box] = []
            for detection in result.detections:
                if not detection.categories:
                    continue
                box = detection.bounding_box
                detections.append(
                    {
                        "x_min": max(0.0, float(box.origin_x) / width),
                        "y_min": max(0.0, float(box.origin_y) / height),
                        "x_max": min(1.0, float(box.origin_x + box.width) / width),
                        "y_max": min(1.0, float(box.origin_y + box.height) / height),
                        "confidence": float(detection.categories[0].score),
                    }
                )
            detections.sort(key=lambda item: float(item["confidence"]), reverse=True)
            preprocessing_times.append(preprocessing_ms)
            inference_times.append(inference_ms)
            records.append(
                {
                    "sample_id": row["sample_id"],
                    "image_path": row["image_path"],
                    "preprocessing_ms": preprocessing_ms,
                    "inference_ms": inference_ms,
                    "detections": detections[:4],
                }
            )
    predictions_path = output / "raw_predictions.jsonl"
    with predictions_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    predictions_by_id = {record["sample_id"]: record for record in records}
    thresholds = sorted(
        {
            0.01,
            1.0,
            *(
                float(box["confidence"])
                for record in records
                for box in record["detections"]
            ),
        },
        reverse=True,
    )
    curve = [
        _score_rows(rows, predictions_by_id, threshold, args.crop_expansion)
        for threshold in thresholds
    ]
    selected = _select_threshold(curve)
    _write_csv(
        output / "threshold_curve.csv",
        (_curve_row(item) for item in curve),
        _curve_fields(),
    )
    summary = {
        "experiment": EXPERIMENT,
        "candidate": args.candidate,
        "model_path": str(model_path),
        "model_sha256": _sha256(model_path),
        "model_bytes": model_path.stat().st_size,
        "development_rows": len(rows),
        "raw_score_floor": 0.01,
        "max_results": 4,
        "matching": "exact maximum-cardinality one-to-one; tie by summed IoU",
        "availability_rule": "prediction center in gold and >=50% predicted area intersects gold",
        "crop_expansion_diagnostic": args.crop_expansion,
        "latency_ms": {
            "preprocessing_p50": statistics.median(preprocessing_times),
            "preprocessing_p95": _percentile(preprocessing_times, 0.95),
            "inference_p50": statistics.median(inference_times),
            "inference_p95": _percentile(inference_times, 0.95),
        },
        "selected_threshold": selected,
        "threshold_valid": selected is not None,
        "negative_denominator_warning": (
            "14 development no-hand frames; <=2% requires 0 false-positive frames"
        ),
        "research_only": True,
        "frozen_evaluation_accessed": False,
        "production_authorized": False,
        "passed": selected is not None,
    }
    _write_json(summary_path, summary)
    print(json.dumps(summary, indent=2))
    return summary


def compare(args: argparse.Namespace) -> dict[str, Any]:
    root = args.run_dir / "development_evaluation"
    candidates = {}
    errors = []
    for candidate in args.candidates:
        path = root / candidate / "development_metrics.json"
        if not path.is_file():
            errors.append(f"missing metrics: {candidate}")
            continue
        candidates[candidate] = json.loads(path.read_text(encoding="utf-8"))
    ranked = sorted(
        (name for name, value in candidates.items() if value.get("threshold_valid")),
        key=lambda name: (
            candidates[name]["selected_threshold"]["availability"]["rate"] or 0.0,
            candidates[name]["selected_threshold"]["complete_two_hand_recall"]["rate"] or 0.0,
            candidates[name]["selected_threshold"]["iou50_recall"]["rate"] or 0.0,
            -(candidates[name]["latency_ms"]["inference_p95"] or float("inf")),
        ),
        reverse=True,
    )
    summary = {
        "experiment": EXPERIMENT,
        "candidates": candidates,
        "development_ranking": ranked,
        "provisional_winner": ranked[0] if ranked else None,
        "warning": "Development selection only; frozen P0/N0/P1 not accessed.",
        "errors": errors,
        "passed": not errors and len(ranked) == len(args.candidates),
        "production_authorized": False,
    }
    _write_json(root / "comparison_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="C0-B0 development threshold evaluation")
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run-model")
    run_parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    run_parser.add_argument("--manifest-run", type=Path, default=DEFAULT_MANIFEST_RUN)
    run_parser.add_argument("--candidate", required=True)
    run_parser.add_argument("--model", type=Path, required=True)
    run_parser.add_argument("--crop-expansion", type=float, default=1.75)
    run_parser.add_argument("--retry-incomplete", action="store_true")
    run_parser.set_defaults(func=run_model)

    compare_parser = commands.add_parser("compare")
    compare_parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    compare_parser.add_argument(
        "--candidates",
        nargs="+",
        default=("mobilenet_v2_100", "mobilenet_v2_i320_100"),
    )
    compare_parser.set_defaults(func=compare)

    args = parser.parse_args()
    try:
        result = args.func(args)
        return 0 if result.get("passed", True) else 2
    except (FileExistsError, FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as error:
        print(f"[tracking/c0-b0-stage2-eval] ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
