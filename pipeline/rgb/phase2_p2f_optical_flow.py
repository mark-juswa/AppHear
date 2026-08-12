"""P2-P2F causal optical-flow ROI feasibility on frozen P2-P2 evidence.

This experiment does not train a model, materialize an RGB training dataset, or
modify Android. It tests whether image-content tracking can repair the objective
ROI failures left by direct landmarks, pose recovery, and I320 detection.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np

from pipeline.crops.pose_roi import PoseRecoveryConfig, causal_pose_recovery_sequence
from pipeline.crops.roi import RoiObservation, direct_square_box
from pipeline.rgb.phase2_p2_roi_audit import (
    ROOT,
    Box4,
    _gold_complete,
    _rate,
    _read_csv,
    _resolve_gold_sides,
    _roi_config,
    _side_assignments,
    _stage_arrays,
    _video_frames,
    _write_csv,
    _write_json,
    score_route_boxes,
)

EXPERIMENT = "phase2_p2f_optical_flow_roi_v1"
DEFAULT_SOURCE = ROOT / "artifacts/recognition_upgrade/phase2_roi_audit/p2_p2_roi_audit_02"
DEFAULT_OUTPUT = ROOT / "artifacts/recognition_upgrade/phase2_roi_audit/p2_p2f_flow_01"
ROW_FIELDS = (
    "sample_id",
    "gloss",
    "signer_group_id",
    "split",
    "center_frame_index",
    "gold_hands_json",
    "route_boxes_json",
    "roi_sources_json",
    "triplet_available_rate",
    "synchronization_error_ms",
)


@dataclass
class FlowState:
    box: Box4
    points: np.ndarray
    timestamp_ms: int


def _features_in_box(gray: np.ndarray, box: Box4, max_corners: int = 40) -> np.ndarray:
    height, width = gray.shape
    x1, y1, x2, y2 = box
    left = max(0, min(width - 1, int(np.floor(x1))))
    top = max(0, min(height - 1, int(np.floor(y1))))
    right = max(left + 1, min(width, int(np.ceil(x2))))
    bottom = max(top + 1, min(height, int(np.ceil(y2))))
    mask = np.zeros_like(gray, dtype=np.uint8)
    mask[top:bottom, left:right] = 255
    points = cv2.goodFeaturesToTrack(
        gray,
        maxCorners=max_corners,
        qualityLevel=0.01,
        minDistance=4,
        mask=mask,
        blockSize=5,
    )
    if points is None:
        return np.empty((0, 1, 2), dtype=np.float32)
    return points.astype(np.float32)


def _translate_box(box: Box4, dx: float, dy: float) -> Box4:
    x1, y1, x2, y2 = box
    return x1 + dx, y1 + dy, x2 + dx, y2 + dy


def _flow_box(
    previous_gray: np.ndarray,
    current_gray: np.ndarray,
    state: FlowState,
    max_fb_error: float = 1.5,
    min_points: int = 6,
) -> tuple[Box4, np.ndarray] | None:
    if len(state.points) < min_points:
        return None
    forward, status_forward, _ = cv2.calcOpticalFlowPyrLK(
        previous_gray,
        current_gray,
        state.points,
        np.empty_like(state.points),
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )
    if forward is None or status_forward is None:
        return None
    backward, status_backward, _ = cv2.calcOpticalFlowPyrLK(
        current_gray,
        previous_gray,
        forward,
        np.empty_like(forward),
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )
    if backward is None or status_backward is None:
        return None
    fb_error = np.linalg.norm(state.points.reshape(-1, 2) - backward.reshape(-1, 2), axis=1)
    valid = (
        status_forward.reshape(-1).astype(bool)
        & status_backward.reshape(-1).astype(bool)
        & np.isfinite(fb_error)
        & (fb_error <= max_fb_error)
    )
    if int(np.sum(valid)) < min_points:
        return None
    old = state.points.reshape(-1, 2)[valid]
    new = forward.reshape(-1, 2)[valid]
    displacement = np.median(new - old, axis=0)
    diagonal = float(np.hypot(previous_gray.shape[1], previous_gray.shape[0]))
    if float(np.linalg.norm(displacement)) > 0.20 * diagonal:
        return None
    return _translate_box(state.box, float(displacement[0]), float(displacement[1])), new.reshape(
        -1, 1, 2
    ).astype(np.float32)


def causal_flow_roi_sequence(
    frames: list[np.ndarray],
    arrays: dict[str, np.ndarray],
    max_flow_age_ms: int = 350,
) -> list[list[RoiObservation]]:
    """Track canonical hand slots causally using direct, flow, then pose fallback."""
    if len(frames) != len(arrays["timestamps_ms"]):
        raise ValueError("decoded frame count and Stage-E timestamp count differ")
    height, width = frames[0].shape[:2]
    config = _roi_config()
    pose = causal_pose_recovery_sequence(
        arrays["hands_image"],
        arrays["hand_score"],
        arrays["pose_image"],
        arrays["timestamps_ms"],
        width,
        height,
        1.75,
        config,
        PoseRecoveryConfig(
            min_pose_visibility=0.5,
            fallback_side_ratio=0.7222874914635724,
            max_track_age_ms=250,
        ),
    )
    output: list[list[RoiObservation]] = []
    states: list[FlowState | None] = [None, None]
    previous_gray: np.ndarray | None = None
    for frame_index, frame in enumerate(frames):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        timestamp = int(arrays["timestamps_ms"][frame_index])
        observations: list[RoiObservation] = []
        for side in range(2):
            direct = None
            if arrays["hand_score"][frame_index, side] > 0:
                direct = direct_square_box(
                    arrays["hands_image"][frame_index, side], width, height, 1.75, config
                )
            source = "missing"
            age_ms = 0
            box = direct
            flow_points: np.ndarray | None = None
            if box is not None:
                source = "direct"
            else:
                state = states[side]
                if previous_gray is not None and state is not None:
                    age_ms = timestamp - state.timestamp_ms
                    if 0 <= age_ms <= max_flow_age_ms:
                        tracked = _flow_box(previous_gray, gray, state)
                        if tracked is not None:
                            box, flow_points = tracked
                            source = "optical_flow"
                if box is None and pose[frame_index][side].box_xyxy is not None:
                    box = pose[frame_index][side].box_xyxy
                    source = "pose_fallback"
                    age_ms = pose[frame_index][side].age_ms

            if box is None:
                states[side] = None
                observations.append(RoiObservation(None, "missing", max(age_ms, 0)))
                continue
            points = flow_points if flow_points is not None else _features_in_box(gray, box)
            if len(points) < 6:
                points = _features_in_box(gray, box, max_corners=80)
            states[side] = FlowState(box=box, points=points, timestamp_ms=timestamp)
            observations.append(RoiObservation(box, source, max(age_ms, 0)))
        output.append(observations)
        previous_gray = gray
    return output


def _load_all_frames(video: Path, count: int) -> tuple[list[np.ndarray], float]:
    frame_map, fps, _ = _video_frames(video, set(range(count)))
    missing = [index for index in range(count) if index not in frame_map]
    if missing:
        raise ValueError(f"{video}: missing {len(missing)} decoded frames")
    return [frame_map[index] for index in range(count)], fps


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists():
        raise FileExistsError(f"output already exists: {args.output}")
    selected = {
        row["audit_sample_id"]: row for row in _read_csv(args.source_run / "selected_samples.csv")
    }
    gold_rows, gold_index = _gold_complete(args.source_run)
    if args.limit is not None:
        if args.limit <= 0:
            raise ValueError("limit must be positive")
        gold_rows = gold_rows[: args.limit]
    assignments = _side_assignments(args.source_run)
    output_rows: list[dict[str, Any]] = []
    gold_total = covered_total = two_total = two_complete = 0
    known_side_hands = side_correct = side_errors = 0
    visible_frames = negative_frames = negative_false_roi = triplet_consistent = sync_ok = 0
    source_counts: Counter[str] = Counter()
    for number, gold_row in enumerate(gold_rows, start=1):
        if gold_row["review_status"] == "quarantine":
            continue
        sample_id = gold_row["sample_id"]
        source = selected[sample_id]
        arrays = _stage_arrays(Path(source["stage_e_path"]))
        frames, fps = _load_all_frames(Path(source["raw_video_path"]), len(arrays["timestamps_ms"]))
        sequence = causal_flow_roi_sequence(frames, arrays, args.max_flow_age_ms)
        context_indices = json.loads(source["context_frame_indices"])
        center = int(source["center_frame_index"])
        observations = sequence[center]
        height, width = frames[center].shape[:2]
        boxes = [
            [box[0] / width, box[1] / height, box[2] / width, box[3] / height]
            if (box := observation.box_xyxy) is not None
            else None
            for observation in observations
        ]
        gold = _resolve_gold_sides(sample_id, json.loads(gold_row["gold_hands_json"]), assignments)
        covered, complete, errors = score_route_boxes(gold, boxes)
        gold_total += len(gold)
        covered_total += covered
        two_total += int(len(gold) == 2)
        two_complete += int(complete)
        visible_frames += int(bool(gold))
        negative_frames += int(not gold)
        negative_false_roi += int(not gold and any(box is not None for box in boxes))
        side_errors += errors
        for hand in gold:
            side = hand.get("anatomical_side", "unknown")
            if side not in {"left", "right"}:
                continue
            known_side_hands += 1
            normalized_box = boxes[0 if side == "left" else 1]
            side_correct += int(
                normalized_box is not None
                and p2_coverage(
                    hand, cast(Box4, tuple(float(value) for value in normalized_box))
                )
                >= 0.90
            )
        triplet_rate = sum(
            sequence[index][side].box_xyxy is not None
            for index in context_indices
            for side in range(2)
        ) / 6.0
        triplet_consistent += int(triplet_rate >= 5 / 6)
        video_elapsed = int(round(center * 1000.0 / fps)) if fps > 0 else 0
        stage_elapsed = int(arrays["timestamps_ms"][center] - arrays["timestamps_ms"][0])
        sync_error = abs(video_elapsed - stage_elapsed)
        sync_ok += int(sync_error <= 50)
        source_counts.update(observation.source for observation in observations)
        output_rows.append(
            {
                "sample_id": sample_id,
                "gloss": gold_index[sample_id]["gloss"],
                "signer_group_id": source["signer_group_id"],
                "split": source["split"],
                "center_frame_index": center,
                "gold_hands_json": json.dumps(gold, separators=(",", ":")),
                "route_boxes_json": json.dumps(boxes, separators=(",", ":")),
                "roi_sources_json": json.dumps(
                    [observation.source for observation in observations], separators=(",", ":")
                ),
                "triplet_available_rate": triplet_rate,
                "synchronization_error_ms": sync_error,
            }
        )
        print(f"[phase2/p2-p2f] {number}/{len(gold_rows)} {gold_index[sample_id]['gloss']}")

    coverage = _rate(covered_total, gold_total)
    two_hand = _rate(two_complete, two_total)
    side_accuracy = _rate(side_correct, known_side_hands)
    consistency = _rate(triplet_consistent, len(output_rows))
    synchronization = _rate(sync_ok, len(output_rows))
    negative_false = _rate(negative_false_roi, negative_frames)
    objective_gate = bool(
        (coverage or 0.0) >= 0.90
        and (two_hand or 0.0) >= 0.80
        and (side_accuracy or 0.0) >= 0.98
        and (consistency or 0.0) >= 0.90
        and (synchronization or 0.0) >= 0.98
        and (negative_false if negative_false is not None else 1.0) <= 0.02
    )
    source_result = json.loads(
        (args.source_run / "p2_p2_final_result.json").read_text(encoding="utf-8")
    )
    r1 = source_result["routes"]["R1"]
    deltas = {
        "known_visible_roi_coverage": (coverage or 0.0)
        - float(r1["known_visible_roi_coverage"]),
        "complete_two_hand_coverage": (two_hand or 0.0)
        - float(r1["complete_two_hand_coverage"]),
        "anatomical_side_accuracy": (side_accuracy or 0.0)
        - float(r1["anatomical_side_accuracy"]),
        "triplet_availability_consistency_rate": (consistency or 0.0)
        - float(r1["triplet_availability_consistency_rate"]),
    }
    args.output.mkdir(parents=True)
    _write_csv(args.output / "flow_route.csv", ROW_FIELDS, output_rows)
    summary = {
        "experiment": EXPERIMENT,
        "source_run": str(args.source_run.resolve()),
        "frames": len(output_rows),
        "smoke": args.limit is not None,
        "max_flow_age_ms": args.max_flow_age_ms,
        "known_visible_roi_coverage": coverage,
        "complete_two_hand_coverage": two_hand,
        "anatomical_side_gold_hands": known_side_hands,
        "anatomical_side_accuracy": side_accuracy,
        "anatomical_side_errors": side_errors,
        "triplet_availability_consistency_rate": consistency,
        "synchronization_pass_rate": synchronization,
        "no_visible_hand_false_roi_rate": negative_false,
        "center_roi_source_counts": dict(source_counts),
        "frozen_r1_comparison": {
            "r1": {
                "known_visible_roi_coverage": r1["known_visible_roi_coverage"],
                "complete_two_hand_coverage": r1["complete_two_hand_coverage"],
                "anatomical_side_accuracy": r1["anatomical_side_accuracy"],
                "triplet_availability_consistency_rate": r1[
                    "triplet_availability_consistency_rate"
                ],
            },
            "p2_p2f_minus_r1": deltas,
        },
        "registered_gates": {
            "known_visible_roi_coverage_min": 0.90,
            "complete_two_hand_coverage_min": 0.80,
            "anatomical_side_accuracy_min": 0.98,
            "triplet_availability_consistency_min": 0.90,
            "synchronization_pass_rate_min": 0.98,
            "no_visible_hand_false_roi_rate_max": 0.02,
        },
        "objective_gate_passed": objective_gate,
        "decision": (
            "GO_BLINDED_CROP_REVIEW"
            if objective_gate
            else "NO_GO_RETIRE_CURRENT_ROI_STACK"
        ),
        "models_trained": False,
        "rgb_dataset_created": False,
        "android_modified": False,
        "passed": True,
    }
    _write_json(args.output / "result.json", summary)
    print(json.dumps(summary, indent=2))
    return summary


def p2_coverage(gold: dict[str, Any], box: Box4) -> float:
    gx1, gy1, gx2, gy2 = (float(gold[key]) for key in ("x_min", "y_min", "x_max", "y_max"))
    x1, y1, x2, y2 = box
    intersection = max(0.0, min(gx2, x2) - max(gx1, x1)) * max(
        0.0, min(gy2, y2) - max(gy1, y1)
    )
    area = max(0.0, gx2 - gx1) * max(0.0, gy2 - gy1)
    return intersection / area if area else 0.0


def check(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    result_path = args.output / "result.json"
    rows_path = args.output / "flow_route.csv"
    if not result_path.is_file():
        errors.append("missing result.json")
    if not rows_path.is_file():
        errors.append("missing flow_route.csv")
    rows = _read_csv(rows_path) if rows_path.is_file() else []
    if args.require_full and len(rows) != 120:
        errors.append(f"expected 120 route rows, found {len(rows)}")
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else {}
    if result and result.get("models_trained") is not False:
        errors.append("unexpected model-training state")
    report = {
        "run_dir": str(args.output.resolve()),
        "rows": len(rows),
        "errors": errors,
        "passed": not errors,
        "production_authorized": False,
    }
    print(json.dumps(report, indent=2))
    if errors:
        raise ValueError("; ".join(errors))
    return report


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="P2-P2F optical-flow ROI feasibility")
    sub = root.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE)
    run_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_parser.add_argument("--max-flow-age-ms", type=int, default=350)
    run_parser.add_argument("--limit", type=int)
    run_parser.set_defaults(func=run)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    check_parser.add_argument("--require-full", action="store_true")
    check_parser.set_defaults(func=check)
    return root


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
