"""Evaluate candidate 01's crop hand-refiner on frozen Xiaomi phone frames.

The DWPose-t whole-body output supplies current-frame anatomical hand proposals.
The MediaPipe landmark submodel is invoked directly on those crops.  This
diagnostic never carries geometry across frames, reassigns anatomical slots,
or loads a recognizer.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
import time
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.perception_vnext.hand_refiner import (  # noqa: E402
    MediaPipeHandRefiner,
    RefinedHand,
)
from pipeline.perception_vnext.hand_roi import (  # noqa: E402
    HandRoi,
    build_hand_roi,
    crop_hand,
)

B1 = ROOT / (
    "artifacts/recognition_upgrade/"
    "p8c3b1_controlled_live_student_geometry_capture_01"
)
B2 = ROOT / (
    "artifacts/recognition_upgrade/"
    "p8c3b2_exact_phone_frame_teacher_reference_01"
)
CANDIDATE = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/phone_01/"
    "candidate_01_dwpose_t_mp_hand"
)
COARSE = CANDIDATE / "offline/candidate_phone_frames.jsonl"
MODEL = CANDIDATE / "refiner/hand_landmarks_detector.tflite"
OUT = CANDIDATE / "offline_refined"

EXPECTED_MODEL_SHA256 = (
    "6acda74af3fbf40e68265c20c7394b2bad81a16a481dcd79ad7a081887c3d6b9"
)
EXPECTED_ROWS = 320
PRESENCE_THRESHOLD = 0.50
MINIMUM_VALID_JOINTS = 18
HAND_EDGES = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (0, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (0, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (0, 17),
    (17, 18),
    (18, 19),
    (19, 20),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def stats(values: Iterable[float | None]) -> dict[str, Any]:
    clean = [
        float(value)
        for value in values
        if value is not None and math.isfinite(float(value))
    ]
    if not clean:
        return {"count": 0, "mean": None, "p50": None, "p95": None, "max": None}
    array = np.asarray(clean, np.float64)
    return {
        "count": len(clean),
        "mean": float(array.mean()),
        "p50": float(np.median(array)),
        "p95": float(np.quantile(array, 0.95)),
        "max": float(array.max()),
    }


def rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def roi_json(roi: HandRoi | None) -> dict[str, Any] | None:
    if roi is None:
        return None
    return {
        "center_xy_source": [roi.center_x, roi.center_y],
        "side_source_px": roi.side,
        "xyxy_source": list(roi.xyxy),
        "xyxy_normalized": list(roi.normalized_xyxy),
        "support_count_0p10": roi.support_count,
    }


def refined_json(
    roi: HandRoi | None,
    refined: RefinedHand | None,
    elapsed_ms: float | None,
) -> dict[str, Any]:
    if roi is None or refined is None:
        return {
            "proposal": roi_json(roi),
            "refiner_invoked": False,
            "refiner_ms": None,
            "presence": None,
            "handedness_diagnostic": None,
            "observed": False,
            "valid": [False] * 21,
            "xy_source": [[0.0, 0.0]] * 21,
            "raw_crop_z_diagnostic": [0.0] * 21,
            "world_xyz_diagnostic": [[0.0, 0.0, 0.0]] * 21,
        }
    valid_count = int(np.count_nonzero(refined.valid))
    observed = refined.presence >= PRESENCE_THRESHOLD and valid_count >= MINIMUM_VALID_JOINTS
    return {
        "proposal": roi_json(roi),
        "refiner_invoked": True,
        "refiner_ms": elapsed_ms,
        "presence": refined.presence,
        "handedness_diagnostic": refined.handedness,
        "observed": bool(observed),
        "valid": refined.valid.tolist(),
        "valid_count": valid_count,
        "xy_source": refined.xy_source.tolist(),
        "raw_crop_z_diagnostic": refined.raw_z.tolist(),
        "world_xyz_diagnostic": refined.world_xyz.tolist(),
    }


def teacher_error(
    hand: dict[str, Any], teacher_xy: np.ndarray, width: int, height: int
) -> float | None:
    if not hand["observed"]:
        return None
    candidate = np.asarray(hand["xy_source"], np.float32)
    valid = np.asarray(hand["valid"], bool)
    valid &= np.all(np.isfinite(teacher_xy), axis=1)
    valid &= (teacher_xy[:, 0] >= 0) & (teacher_xy[:, 0] < width)
    valid &= (teacher_xy[:, 1] >= 0) & (teacher_xy[:, 1] < height)
    if not np.any(valid):
        return None
    return float(
        np.median(np.linalg.norm(candidate[valid] - teacher_xy[valid], axis=1))
        / math.hypot(width, height)
    )


def draw_hand(
    image: np.ndarray, hand: dict[str, Any], color: tuple[int, int, int]
) -> None:
    proposal = hand["proposal"]
    if proposal is not None:
        left, top, right, bottom = np.rint(proposal["xyxy_source"]).astype(int)
        cv2.rectangle(image, (left, top), (right, bottom), color, 1, cv2.LINE_AA)
    if not hand["observed"]:
        return
    points = np.asarray(hand["xy_source"], np.float32)
    valid = np.asarray(hand["valid"], bool)
    for start, end in HAND_EDGES:
        if valid[start] and valid[end]:
            cv2.line(
                image,
                tuple(np.rint(points[start]).astype(int)),
                tuple(np.rint(points[end]).astype(int)),
                color,
                2,
                cv2.LINE_AA,
            )
    for point, is_valid in zip(points, valid, strict=True):
        if is_valid:
            cv2.circle(image, tuple(np.rint(point).astype(int)), 2, color, -1, cv2.LINE_AA)


def run() -> int:
    if sha256(MODEL) != EXPECTED_MODEL_SHA256:
        raise RuntimeError("VNEXT_HAND_REFINER_IDENTITY_MISMATCH")
    coarse_rows = load_jsonl(COARSE)
    teacher_rows = load_jsonl(B2 / "teacher_phone_frames.jsonl")
    if len(coarse_rows) != EXPECTED_ROWS or len(teacher_rows) != EXPECTED_ROWS:
        raise RuntimeError("VNEXT_REFINER_FROZEN_ROW_COUNT_MISMATCH")
    teacher_by_id = {int(row["retained_sequence_id"]): row for row in teacher_rows}

    refiner = MediaPipeHandRefiner(MODEL, num_threads=2)
    output_rows: list[dict[str, Any]] = []
    all_refiner_ms: list[float] = []
    try:
        for coarse in coarse_rows:
            sequence_id = int(coarse["retained_sequence_id"])
            image_path = B1 / coarse["image_filename"]
            if sha256(image_path) != coarse["image_sha256"]:
                raise RuntimeError(f"VNEXT_REFINER_FRAME_HASH_MISMATCH:{sequence_id}")
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is None:
                raise RuntimeError(f"VNEXT_REFINER_FRAME_DECODE_FAILURE:{sequence_id}")
            width = int(coarse["source_width"])
            height = int(coarse["source_height"])

            hand_results: dict[str, dict[str, Any]] = {}
            for side in ("left_hand", "right_hand"):
                localizer = coarse[side]
                roi = build_hand_roi(
                    np.asarray(localizer["xy_source"], np.float32),
                    np.asarray(localizer["support"], np.float32),
                    width,
                    height,
                )
                refined = None
                elapsed_ms = None
                if roi is not None:
                    crop = crop_hand(image, roi)
                    started = time.perf_counter_ns()
                    refined = refiner.refine(crop, roi)
                    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000.0
                    all_refiner_ms.append(elapsed_ms)
                hand_results[side] = refined_json(roi, refined, elapsed_ms)

            teacher = teacher_by_id[sequence_id]
            teacher_points = np.asarray(teacher["teacher_keypoints_133"], np.float32)
            hand_results["left_hand"]["teacher_median_error_image_diagonal"] = teacher_error(
                hand_results["left_hand"], teacher_points[91:112], width, height
            )
            hand_results["right_hand"]["teacher_median_error_image_diagonal"] = teacher_error(
                hand_results["right_hand"], teacher_points[112:133], width, height
            )
            output_rows.append(
                {
                    "schema": "APPHEAR_PERCEPTION_VNEXT_REFINED_PHONE_FRAME_V1",
                    "candidate_id": "DWPose-t-current-frame-plus-MP-hand-crop-refiner",
                    "retained_sequence_id": sequence_id,
                    "sensor_timestamp_ns": coarse["sensor_timestamp_ns"],
                    "condition_id": coarse["condition_id"],
                    "condition_label": coarse["condition_label"],
                    "operator_note": coarse["operator_note"],
                    "movement": coarse["movement"],
                    "hands_crossed": coarse["hands_crossed"],
                    "physical_left_visible": coarse["physical_left_visible"],
                    "physical_right_visible": coarse["physical_right_visible"],
                    "person_visible": coarse["person_visible"],
                    "image_filename": coarse["image_filename"],
                    "image_sha256": coarse["image_sha256"],
                    "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB",
                    "source_width": width,
                    "source_height": height,
                    "coarse_inference_ms": coarse["inference_ms"],
                    "body": coarse["body"],
                    "left_hand": hand_results["left_hand"],
                    "right_hand": hand_results["right_hand"],
                    "slot_assignment": "DWPose-t anatomical slot; never reassigned by handedness",
                    "presence_semantics": (
                        "MediaPipe group-level current-crop presence >=0.50 and >=18/21 valid xy"
                    ),
                    "per_joint_support_semantics": (
                        "validity only; refiner does not expose calibrated per-joint confidence"
                    ),
                    "current_frame_only": True,
                    "carried_forward": False,
                    "synthetic_depth": False,
                    "recognizer_connected": False,
                }
            )
    finally:
        refiner.close()

    write_jsonl(OUT / "refined_phone_frames.jsonl", output_rows)
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in output_rows:
        grouped[row["condition_id"]].append(row)
    condition_rows: list[dict[str, Any]] = []
    for condition, rows in grouped.items():
        visible_left = [row for row in rows if row["physical_left_visible"]]
        visible_right = [row for row in rows if row["physical_right_visible"]]
        expected_two = [
            row
            for row in rows
            if row["physical_left_visible"] and row["physical_right_visible"]
        ]
        false_slots = sum(
            (row["left_hand"]["observed"] and not row["physical_left_visible"])
            + (row["right_hand"]["observed"] and not row["physical_right_visible"])
            for row in rows
        )
        condition_rows.append(
            {
                "condition_id": condition,
                "frames": len(rows),
                "left_observed_rate": rate(
                    sum(row["left_hand"]["observed"] for row in visible_left),
                    len(visible_left),
                ),
                "right_observed_rate": rate(
                    sum(row["right_hand"]["observed"] for row in visible_right),
                    len(visible_right),
                ),
                "complete_two_rate": rate(
                    sum(
                        row["left_hand"]["observed"] and row["right_hand"]["observed"]
                        for row in expected_two
                    ),
                    len(expected_two),
                ),
                "false_slot_rate": false_slots / (2 * len(rows)),
                "body_available_rate": sum(row["body"]["available"] for row in rows)
                / len(rows),
            }
        )
    write_csv(OUT / "refined_condition_metrics.csv", condition_rows)

    visible_left = [row for row in output_rows if row["physical_left_visible"]]
    visible_right = [row for row in output_rows if row["physical_right_visible"]]
    two_hand = [
        row
        for row in output_rows
        if row["physical_left_visible"] and row["physical_right_visible"]
    ]
    no_hand = [
        row
        for row in output_rows
        if not row["physical_left_visible"] and not row["physical_right_visible"]
    ]
    unilateral = [
        row
        for row in output_rows
        if row["physical_left_visible"] ^ row["physical_right_visible"]
    ]
    result = {
        "schema": "APPHEAR_PERCEPTION_VNEXT_REFINER_VIABILITY_RESULT_V1",
        "candidate_id": "DWPose-t-current-frame-plus-MP-hand-crop-refiner",
        "status": "MEASURED_NOT_PROMOTED",
        "frames": len(output_rows),
        "source": "frozen P8-C3B1 Xiaomi M2101K7AG upright-unmirrored phone frames",
        "hands": {
            "visible_left_observation_rate": rate(
                sum(row["left_hand"]["observed"] for row in visible_left),
                len(visible_left),
            ),
            "visible_right_observation_rate": rate(
                sum(row["right_hand"]["observed"] for row in visible_right),
                len(visible_right),
            ),
            "complete_two_hand_rate": rate(
                sum(
                    row["left_hand"]["observed"] and row["right_hand"]["observed"]
                    for row in two_hand
                ),
                len(two_hand),
            ),
            "no_usable_hand_false_observation_rate": rate(
                sum(
                    row["left_hand"]["observed"] or row["right_hand"]["observed"]
                    for row in no_hand
                ),
                len(no_hand),
            ),
            "unilateral_exact_anatomical_state_rate": rate(
                sum(
                    row["left_hand"]["observed"] == row["physical_left_visible"]
                    and row["right_hand"]["observed"] == row["physical_right_visible"]
                    for row in unilateral
                ),
                len(unilateral),
            ),
            "left_teacher_error_image_diagonal": stats(
                row["left_hand"]["teacher_median_error_image_diagonal"]
                for row in visible_left
            ),
            "right_teacher_error_image_diagonal": stats(
                row["right_hand"]["teacher_median_error_image_diagonal"]
                for row in visible_right
            ),
        },
        "runtime": {
            "refiner_invocations": len(all_refiner_ms),
            "per_hand_refiner_ms": stats(all_refiner_ms),
            "refiner_model_bytes": MODEL.stat().st_size,
            "refiner_model_sha256": sha256(MODEL),
            "desktop_only": True,
        },
        "contract": {
            "hands": "21 source-xy anatomical joints + group presence + joint validity",
            "body": "DWPose-t selected upper-body source-xy + support + validity",
            "depth": "none; crop Z and model world coordinates diagnostic only",
            "missingness": "explicit observed state; unobserved coordinates are not evidence",
            "temporal_carry": "none",
        },
        "scope": {
            "recognition_training": False,
            "recognizer_inference": False,
            "s5_s7_ui": False,
            "five_sign": False,
        },
    }
    write_json(OUT / "refined_viability_result.json", result)

    panel_dir = OUT / "visualizations"
    panel_dir.mkdir(parents=True, exist_ok=True)
    for condition, rows in grouped.items():
        ranked = sorted(
            rows,
            key=lambda row: (
                int(row["left_hand"]["observed"]) + int(row["right_hand"]["observed"]),
                float(row["left_hand"]["presence"] or 0.0)
                + float(row["right_hand"]["presence"] or 0.0),
            ),
            reverse=True,
        )
        for panel_index, row in enumerate(ranked[:2], start=1):
            image = cv2.imread(str(B1 / row["image_filename"]), cv2.IMREAD_COLOR)
            draw_hand(image, row["left_hand"], (0, 255, 255))
            draw_hand(image, row["right_hand"], (255, 0, 255))
            left_presence = row["left_hand"]["presence"]
            right_presence = row["right_hand"]["presence"]
            left_label = f"{float(left_presence):.3f}" if left_presence is not None else "none"
            right_label = (
                f"{float(right_presence):.3f}" if right_presence is not None else "none"
            )
            cv2.putText(
                image,
                f"{condition} {row['operator_note']}",
                (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                image,
                f"LH {left_label} RH {right_label}",
                (8, 42),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )
            destination = panel_dir / (
                f"{int(row['retained_sequence_id']):04d}_{condition}_{panel_index}.jpg"
            )
            cv2.imwrite(str(destination), image, [cv2.IMWRITE_JPEG_QUALITY, 92])

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
