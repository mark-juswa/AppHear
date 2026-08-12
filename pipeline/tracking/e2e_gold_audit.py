"""Score MediaPipe landmark instances against side-independent hand-contour gold."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from itertools import permutations
from math import hypot
from pathlib import Path
from typing import Any

from pipeline.tracking.e2e_gold_review import completion_error, load_run, parse_boxes

PALM_LANDMARK_INDICES = (0, 5, 9, 13, 17)
MIN_IN_BOX_LANDMARK_FRACTION = 0.50


def iou(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax1, ay1, ax2, ay2 = (float(a[key]) for key in ("x_min", "y_min", "x_max", "y_max"))
    if "box" in b:
        bx1, by1, bx2, by2 = (float(value) for value in b["box"])
    else:
        bx1, by1, bx2, by2 = (float(b[key]) for key in ("x_min", "y_min", "x_max", "y_max"))
    intersection = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - intersection
    return intersection / union if union else 0.0


def _prediction_points(prediction: dict[str, Any]) -> list[tuple[float, float]]:
    raw = prediction.get("landmarks")
    if not isinstance(raw, list) or len(raw) != 21:
        raise ValueError("each MediaPipe instance must contain exactly 21 landmarks")
    points = []
    for landmark in raw:
        if not isinstance(landmark, dict) or "x" not in landmark or "y" not in landmark:
            raise ValueError("invalid MediaPipe landmark payload")
        points.append((float(landmark["x"]), float(landmark["y"])))
    return points


def palm_center(prediction: dict[str, Any]) -> tuple[float, float]:
    points = _prediction_points(prediction)
    palm = [points[index] for index in PALM_LANDMARK_INDICES]
    return (
        sum(point[0] for point in palm) / len(palm),
        sum(point[1] for point in palm) / len(palm),
    )


def _inside(box: dict[str, Any], point: tuple[float, float]) -> bool:
    return float(box["x_min"]) <= point[0] <= float(box["x_max"]) and float(box["y_min"]) <= point[
        1
    ] <= float(box["y_max"])


def landmark_fraction_inside(gold_box: dict[str, Any], prediction: dict[str, Any]) -> float:
    points = _prediction_points(prediction)
    return sum(_inside(gold_box, point) for point in points) / len(points)


def association_score(
    gold_box: dict[str, Any],
    prediction: dict[str, Any],
    min_landmark_fraction: float = MIN_IN_BOX_LANDMARK_FRACTION,
) -> float | None:
    """Return an association score only when the robust palm belongs to the gold hand."""

    center = palm_center(prediction)
    if not _inside(gold_box, center):
        return None
    fraction = landmark_fraction_inside(gold_box, prediction)
    if fraction < min_landmark_fraction:
        return None
    gold_center_x = (float(gold_box["x_min"]) + float(gold_box["x_max"])) / 2.0
    gold_center_y = (float(gold_box["y_min"]) + float(gold_box["y_max"])) / 2.0
    diagonal = hypot(
        float(gold_box["x_max"]) - float(gold_box["x_min"]),
        float(gold_box["y_max"]) - float(gold_box["y_min"]),
    )
    normalized_distance = hypot(center[0] - gold_center_x, center[1] - gold_center_y) / max(
        diagonal, 1e-9
    )
    proximity = 1.0 - min(normalized_distance, 1.0)
    return fraction + 0.10 * proximity


def landmark_matches(
    gold: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    min_landmark_fraction: float = MIN_IN_BOX_LANDMARK_FRACTION,
) -> list[tuple[int, int, float]]:
    scores: dict[tuple[int, int], float] = {}
    for gold_index, gold_box in enumerate(gold):
        for prediction_index, prediction in enumerate(predictions):
            score = association_score(gold_box, prediction, min_landmark_fraction)
            if score is not None:
                scores[(gold_index, prediction_index)] = score

    maximum = min(len(gold), len(predictions))
    for count in range(maximum, 0, -1):
        best: list[tuple[int, int, float]] | None = None
        best_score = float("-inf")
        for gold_order in permutations(range(len(gold)), count):
            for prediction_order in permutations(range(len(predictions)), count):
                pairs = list(zip(gold_order, prediction_order, strict=True))
                if not all(pair in scores for pair in pairs):
                    continue
                total = sum(scores[pair] for pair in pairs)
                if total > best_score:
                    best_score = total
                    best = [
                        (gold_index, prediction_index, scores[(gold_index, prediction_index)])
                        for gold_index, prediction_index in pairs
                    ]
        if best is not None:
            return best
    return []


def _iou_matches(
    gold: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    threshold: float,
) -> list[tuple[int, int, float]]:
    candidates = sorted(
        (
            (gold_index, prediction_index, iou(gold_box, prediction))
            for gold_index, gold_box in enumerate(gold)
            for prediction_index, prediction in enumerate(predictions)
        ),
        key=lambda item: item[2],
        reverse=True,
    )
    matches = []
    used_gold: set[int] = set()
    used_predictions: set[int] = set()
    for gold_index, prediction_index, overlap in candidates:
        if overlap < threshold:
            break
        if gold_index in used_gold or prediction_index in used_predictions:
            continue
        used_gold.add(gold_index)
        used_predictions.add(prediction_index)
        matches.append((gold_index, prediction_index, overlap))
    return matches


def analyze(run_dir: Path, output: Path) -> dict[str, Any]:
    reviews, index = load_run(run_dir)
    accepted = [row for row in reviews if row["review_status"] == "accepted"]
    incomplete = [
        row["sample_id"]
        for row in reviews
        if row["review_status"] != "quarantine" and completion_error(row) is not None
    ]
    counters: dict[str, float] = defaultdict(float)
    subgroups: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    identity_correct = identity_total = 0
    per_frame = []

    for row in accepted:
        if completion_error(row):
            continue
        metadata = index[row["sample_id"]]
        gold = parse_boxes(row)
        predictions = json.loads(metadata["detected_hands_json"])
        if not isinstance(predictions, list):
            raise ValueError("detected_hands_json must be a list")
        matches = landmark_matches(gold, predictions)
        matches_50 = _iou_matches(gold, predictions, 0.50)
        matches_75 = _iou_matches(gold, predictions, 0.75)

        counters["frames"] += 1
        counters["gold_instances"] += len(gold)
        counters["predicted_instances"] += len(predictions)
        counters["matched_instances"] += len(matches)
        counters["unmatched_predictions"] += len(predictions) - len(matches)
        counters["iou_matched_50"] += len(matches_50)
        counters["iou_matched_75"] += len(matches_75)
        if gold:
            counters["frames_with_visible_hands"] += 1
            counters["any_hand_frame_hits"] += int(bool(matches))
        else:
            counters["negative_frames"] += 1
            counters["negative_frames_with_prediction"] += int(bool(predictions))
        if len(gold) == 2:
            counters["two_hand_frames"] += 1
            counters["both_hands_complete"] += int(len(matches) == 2)

        subgroup_names = [
            f"sampling_stratum={metadata['sampling_cadence']}",
            f"motion_blur={row['motion_blur']}",
            f"source_mirrored={row['source_mirrored']}",
        ]
        for name in subgroup_names:
            subgroups[name]["gold_instances"] += len(gold)
            subgroups[name]["matched_instances"] += len(matches)

        if row["source_mirrored"] != "unknown":
            swap = row["source_mirrored"] == "mirrored"
            for gold_index, prediction_index, _score in matches:
                side = gold[gold_index]["anatomical_side"]
                if side == "unknown":
                    continue
                predicted = str(predictions[prediction_index]["label"]).lower()
                if swap:
                    predicted = "right" if predicted == "left" else "left"
                identity_total += 1
                identity_correct += int(predicted == side)

        per_frame.append(
            {
                "sample_id": row["sample_id"],
                "gold_instances": len(gold),
                "predicted_instances": len(predictions),
                "matched_instances": len(matches),
                "unmatched_predictions": len(predictions) - len(matches),
                "both_hands_complete": len(gold) == 2 and len(matches) == 2,
                "associations": [
                    {
                        "gold_index": gold_index,
                        "prediction_index": prediction_index,
                        "score": score,
                        "landmark_fraction_inside": landmark_fraction_inside(
                            gold[gold_index], predictions[prediction_index]
                        ),
                        "palm_center": palm_center(predictions[prediction_index]),
                    }
                    for gold_index, prediction_index, score in matches
                ],
            }
        )

    gold_instances = counters["gold_instances"]
    predicted_instances = counters["predicted_instances"]
    visible_frames = counters["frames_with_visible_hands"]
    two_hand_frames = counters["two_hand_frames"]
    negative_frames = counters["negative_frames"]
    report = {
        "prediction_schema": "mediapipe_hand_21_landmarks_v1",
        "association_contract": {
            "palm_landmark_indices": list(PALM_LANDMARK_INDICES),
            "requires_palm_center_inside_gold": True,
            "min_landmark_fraction_inside_gold": MIN_IN_BOX_LANDMARK_FRACTION,
            "matching": "maximum-cardinality one-to-one, then coverage plus center proximity",
        },
        "accepted_frames": len(accepted),
        "quarantined_frames": sum(row["review_status"] == "quarantine" for row in reviews),
        "incomplete_sample_ids": incomplete,
        "primary": {
            "visible_hand_instance_recall": (
                counters["matched_instances"] / gold_instances if gold_instances else None
            ),
            "any_hand_frame_recall": (
                counters["any_hand_frame_hits"] / visible_frames if visible_frames else None
            ),
            "both_hands_complete_recall": (
                counters["both_hands_complete"] / two_hand_frames if two_hand_frames else None
            ),
            "unmatched_prediction_rate": (
                counters["unmatched_predictions"] / predicted_instances
                if predicted_instances
                else None
            ),
            "negative_frame_false_positive_rate": (
                counters["negative_frames_with_prediction"] / negative_frames
                if negative_frames
                else None
            ),
            "counts": dict(counters),
        },
        "localization_diagnostic_not_detector_recall": {
            "landmark_envelope_iou_50_match_rate": (
                counters["iou_matched_50"] / gold_instances if gold_instances else None
            ),
            "landmark_envelope_iou_75_match_rate": (
                counters["iou_matched_75"] / gold_instances if gold_instances else None
            ),
        },
        "identity": {
            "eligible_matched_instances": identity_total,
            "correct": identity_correct,
            "accuracy": identity_correct / identity_total if identity_total else None,
            "scope": "Mirror-adjudicated samples with known anatomical side only.",
        },
        "subgroups": {
            name: {
                **dict(values),
                "visible_hand_instance_recall": (
                    values["matched_instances"] / values["gold_instances"]
                    if values["gold_instances"]
                    else None
                ),
            }
            for name, values in sorted(subgroups.items())
        },
        "per_frame": per_frame,
        "valid_for_gate_decision": not incomplete and len(accepted) >= 120,
        "warning": (
            "The association rule is under smoke validation. Do not use fewer than 120 "
            "accepted frames for a gate or accuracy claim."
        ),
    }
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Score E2e landmark-instance gold audit")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    output = args.output or args.run_dir / "audit_summary.json"
    try:
        report = analyze(args.run_dir, output)
    except (FileNotFoundError, KeyError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"[tracking/e2e-gold-audit] ERROR: {error}")
        return 2
    print(json.dumps(report, indent=2))
    return 2 if report["incomplete_sample_ids"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
