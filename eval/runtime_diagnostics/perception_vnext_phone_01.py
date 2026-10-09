"""Bounded phone-frame viability audit for Perception vNext candidate 01.

This is perception-only.  It consumes the frozen P8-C3B1 Xiaomi frames and
frozen P8-C3B2 DWPose-L Teacher outputs, runs the single-pass DWPose-t ONNX
candidate, and emits current-frame observations and visual panels.  It never
loads a recognizer, creates temporal padding, or changes S5/S7/UI state.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
B1 = ROOT / ("artifacts/recognition_upgrade/" "p8c3b1_controlled_live_student_geometry_capture_01")
B2 = ROOT / ("artifacts/recognition_upgrade/" "p8c3b2_exact_phone_frame_teacher_reference_01")
CANDIDATE = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/phone_01/" "candidate_01_dwpose_t_mp_hand"
)
ONNX = CANDIDATE / "export/dwpose_t_singlepass.onnx"
MODEL_MANIFEST = CANDIDATE / "export/model_manifest.json"
OUT = CANDIDATE / "offline"

EXPECTED_ONNX_SHA256 = "37b0f265200f8e249adba1cc9b62925f5e1252245580ed1f66f583d7bce239c0"
EXPECTED_B1_ROWS = 320
LEFT = np.arange(91, 112, dtype=np.int64)
RIGHT = np.arange(112, 133, dtype=np.int64)
BODY = np.asarray([5, 6, 7, 8, 9, 10, 11, 12], dtype=np.int64)
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
    (5, 9),
    (9, 13),
    (13, 17),
)
BODY_EDGES = ((0, 1), (0, 2), (2, 4), (1, 3), (3, 5), (0, 6), (1, 7), (6, 7))
MEAN = np.asarray([123.675, 116.28, 103.53], np.float32).reshape(3, 1, 1)
STD = np.asarray([58.395, 57.12, 57.375], np.float32).reshape(3, 1, 1)
SCORE_THRESHOLD = np.float32(0.30)
MIN_HAND_SUPPORT = 11


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


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
    if not rows:
        raise ValueError(f"cannot write empty table: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def percentile(values: Iterable[float | None], q: float) -> float | None:
    clean = [
        float(value)
        for value in values
        if value is not None and math.isfinite(float(value))
    ]
    if not clean:
        return None
    return float(np.quantile(np.asarray(clean, np.float64), q))


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


def finite_or_none(value: float) -> float | None:
    return float(value) if math.isfinite(float(value)) else None


def warp_matrix(center: np.ndarray, scale: np.ndarray) -> np.ndarray:
    source_width = float(scale[0])
    destination_width, destination_height = 192.0, 256.0
    source = np.zeros((3, 2), np.float32)
    source[0] = center
    source[1] = center + np.asarray([0.0, -0.5 * source_width], np.float32)
    source[2] = np.asarray(
        [
            source[1, 0] - (source[0, 1] - source[1, 1]),
            source[1, 1] + (source[0, 0] - source[1, 0]),
        ],
        np.float32,
    )
    destination = np.zeros((3, 2), np.float32)
    destination[0] = [destination_width * 0.5, destination_height * 0.5]
    destination[1] = [destination_width * 0.5, 32.0]
    destination[2] = [0.0, 32.0]
    return cv2.getAffineTransform(source, destination)


def preprocess(image: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    height, width = image.shape[:2]
    center = np.asarray([width * 0.5, height * 0.5], np.float32)
    scale = np.asarray([width * 1.25, height * 1.25], np.float32)
    aspect = 192.0 / 256.0
    if scale[0] > scale[1] * aspect:
        scale[1] = scale[0] / aspect
    else:
        scale[0] = scale[1] * aspect
    crop = cv2.warpAffine(
        image,
        warp_matrix(center, scale),
        (192, 256),
        flags=cv2.INTER_LINEAR,
    )
    rgb_chw = crop[:, :, ::-1].transpose(2, 0, 1).astype(np.float32)
    value = ((rgb_chw - MEAN) / STD)[None]
    return np.ascontiguousarray(value, np.float32), center, scale


def decode(
    simcc_x: np.ndarray,
    simcc_y: np.ndarray,
    center: np.ndarray,
    scale: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(simcc_x, np.float32).reshape(133, 384)
    y = np.asarray(simcc_y, np.float32).reshape(133, 512)
    points = np.stack([np.argmax(x, axis=1), np.argmax(y, axis=1)], axis=-1).astype(np.float32)
    scores = np.minimum(np.max(x, axis=1), np.max(y, axis=1)).astype(np.float32)
    points[scores <= 0] = -1
    points /= np.float32(2.0)
    points = (
        points / np.asarray([192.0, 256.0], np.float32) * scale + center - np.float32(0.5) * scale
    )
    return points.astype(np.float32), scores


def source_valid(points: np.ndarray, width: int, height: int) -> np.ndarray:
    return (
        np.all(np.isfinite(points), axis=1)
        & (points[:, 0] >= 0)
        & (points[:, 0] < width)
        & (points[:, 1] >= 0)
        & (points[:, 1] < height)
    )


def hand_support(scores: np.ndarray, indices: np.ndarray) -> tuple[int, bool]:
    count = int(np.count_nonzero(scores[indices] >= SCORE_THRESHOLD))
    return count, count >= MIN_HAND_SUPPORT


def compactness(points: np.ndarray) -> float:
    return float(np.linalg.norm(points - points.mean(axis=0), axis=1).mean())


def edge_ratio(points: np.ndarray, edges: Iterable[tuple[int, int]]) -> float:
    lengths = np.asarray([np.linalg.norm(points[a] - points[b]) for a, b in edges], np.float64)
    positive = lengths[lengths > 1e-3]
    if not len(positive):
        return math.inf
    return float(positive.max() / max(float(np.median(positive)), 1e-6))


def teacher_error(
    candidate: np.ndarray,
    teacher: np.ndarray,
    indices: np.ndarray,
    width: int,
    height: int,
) -> float:
    valid = source_valid(candidate[indices], width, height) & source_valid(
        teacher[indices], width, height
    )
    if not np.any(valid):
        return math.nan
    diagonal = math.hypot(width, height)
    return float(
        np.median(np.linalg.norm(candidate[indices][valid] - teacher[indices][valid], axis=1))
        / diagonal
    )


def draw_points(
    image: np.ndarray,
    points: np.ndarray,
    scores: np.ndarray,
    indices: np.ndarray,
    color: tuple[int, int, int],
    edges: Iterable[tuple[int, int]],
    threshold: float,
) -> None:
    local = points[indices]
    local_scores = scores[indices]
    for a, b in edges:
        if local_scores[a] >= threshold and local_scores[b] >= threshold:
            cv2.line(
                image,
                tuple(np.rint(local[a]).astype(int)),
                tuple(np.rint(local[b]).astype(int)),
                color,
                1,
                cv2.LINE_AA,
            )
    for point, score in zip(local, local_scores, strict=True):
        if score >= threshold:
            cv2.circle(image, tuple(np.rint(point).astype(int)), 2, color, -1, cv2.LINE_AA)


def run() -> int:
    import onnxruntime as ort

    if sha256(ONNX) != EXPECTED_ONNX_SHA256:
        raise RuntimeError("VNEXT_ONNX_IDENTITY_MISMATCH")
    manifest = read_json(MODEL_MANIFEST)
    if manifest.get("onnx_sha256") != EXPECTED_ONNX_SHA256:
        raise RuntimeError("VNEXT_MODEL_MANIFEST_MISMATCH")

    b1_rows = load_jsonl(B1 / "student_live_frames.jsonl")
    teacher_rows = load_jsonl(B2 / "teacher_phone_frames.jsonl")
    if len(b1_rows) != EXPECTED_B1_ROWS or len(teacher_rows) != EXPECTED_B1_ROWS:
        raise RuntimeError("VNEXT_FROZEN_PHONE_ROW_COUNT_MISMATCH")
    teacher_by_id = {int(row["retained_sequence_id"]): row for row in teacher_rows}
    if len(teacher_by_id) != EXPECTED_B1_ROWS:
        raise RuntimeError("VNEXT_TEACHER_IDENTITY_DUPLICATE")

    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(ONNX), sess_options=options, providers=["CPUExecutionProvider"]
    )
    output_rows: list[dict[str, Any]] = []
    timings: list[float] = []
    panels_by_condition: defaultdict[str, int] = defaultdict(int)
    panel_dir = OUT / "visualizations"
    panel_dir.mkdir(parents=True, exist_ok=True)

    for row in b1_rows:
        sequence_id = int(row["retained_sequence_id"])
        teacher = teacher_by_id[sequence_id]
        image_path = B1 / row["image_filename"]
        if sha256(image_path) != row["image_sha256"]:
            raise RuntimeError(f"VNEXT_PHONE_FRAME_HASH_MISMATCH:{sequence_id}")
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"VNEXT_PHONE_FRAME_DECODE_FAILURE:{sequence_id}")
        value, center, scale = preprocess(image)
        started = time.perf_counter_ns()
        simcc_x, simcc_y = session.run(["simcc_x", "simcc_y"], {"input": value})
        inference_ms = (time.perf_counter_ns() - started) / 1_000_000.0
        timings.append(inference_ms)
        points, scores = decode(simcc_x, simcc_y, center, scale)
        teacher_points = np.asarray(teacher["teacher_keypoints_133"], np.float32)
        width, height = int(row["source_width"]), int(row["source_height"])
        if points.shape != (133, 2) or teacher_points.shape != (133, 2):
            raise RuntimeError(f"VNEXT_POINT_SHAPE_FAILURE:{sequence_id}")
        left_count, left_observed = hand_support(scores, LEFT)
        right_count, right_observed = hand_support(scores, RIGHT)
        left_valid = source_valid(points[LEFT], width, height)
        right_valid = source_valid(points[RIGHT], width, height)
        body_valid = source_valid(points[BODY], width, height)
        body_supported = scores[BODY] >= SCORE_THRESHOLD

        output = {
            "schema": "APPHEAR_PERCEPTION_VNEXT_PHONE_FRAME_V1",
            "candidate_id": manifest["candidate_id"],
            "retained_sequence_id": sequence_id,
            "sensor_timestamp_ns": int(row["sensor_timestamp_ns"]),
            "condition_id": row["condition_id"],
            "condition_label": row["condition_label"],
            "operator_note": row["operator_note"],
            "movement": row["movement"],
            "hands_crossed": bool(row["hands_crossed"]),
            "physical_left_visible": bool(row["physical_left_visible"]),
            "physical_right_visible": bool(row["physical_right_visible"]),
            "person_visible": bool(row["person_visible"]),
            "image_filename": row["image_filename"],
            "image_sha256": row["image_sha256"],
            "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB",
            "source_width": width,
            "source_height": height,
            "inference_ms": inference_ms,
            "points_133_xy_source": points.tolist(),
            "scores_133": scores.tolist(),
            "body": {
                "indices": BODY.tolist(),
                "xy_source": points[BODY].tolist(),
                "support": scores[BODY].tolist(),
                "valid": body_valid.tolist(),
                "available": bool(np.count_nonzero(body_supported & body_valid) >= 6),
            },
            "left_hand": {
                "xy_source": points[LEFT].tolist(),
                "support": scores[LEFT].tolist(),
                "valid": left_valid.tolist(),
                "support_count_0p30": left_count,
                "localizer_observed": left_observed,
                "compactness_px": (
                    compactness(points[LEFT][left_valid]) if np.any(left_valid) else None
                ),
                "edge_ratio": finite_or_none(edge_ratio(points[LEFT], HAND_EDGES)),
                "teacher_median_error_image_diagonal": finite_or_none(
                    teacher_error(points, teacher_points, LEFT, width, height)
                ),
            },
            "right_hand": {
                "xy_source": points[RIGHT].tolist(),
                "support": scores[RIGHT].tolist(),
                "valid": right_valid.tolist(),
                "support_count_0p30": right_count,
                "localizer_observed": right_observed,
                "compactness_px": (
                    compactness(points[RIGHT][right_valid]) if np.any(right_valid) else None
                ),
                "edge_ratio": finite_or_none(edge_ratio(points[RIGHT], HAND_EDGES)),
                "teacher_median_error_image_diagonal": finite_or_none(
                    teacher_error(points, teacher_points, RIGHT, width, height)
                ),
            },
            "current_frame_only": True,
            "carried_forward": False,
            "synthetic_depth": False,
            "recognizer_connected": False,
        }
        output_rows.append(output)

        condition = str(row["condition_id"])
        if panels_by_condition[condition] < 2:
            panel = image.copy()
            draw_points(
                panel,
                teacher_points,
                np.asarray(teacher["teacher_scores_133"], np.float32),
                LEFT,
                (180, 180, 180),
                HAND_EDGES,
                0.30,
            )
            draw_points(
                panel,
                teacher_points,
                np.asarray(teacher["teacher_scores_133"], np.float32),
                RIGHT,
                (180, 180, 180),
                HAND_EDGES,
                0.30,
            )
            draw_points(panel, points, scores, LEFT, (0, 255, 255), HAND_EDGES, 0.30)
            draw_points(panel, points, scores, RIGHT, (255, 0, 255), HAND_EDGES, 0.30)
            draw_points(panel, points, scores, BODY, (0, 255, 0), BODY_EDGES, 0.30)
            cv2.putText(
                panel,
                f"{condition} {row['operator_note']}",
                (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                panel,
                f"LH {left_count}/21 RH {right_count}/21",
                (8, 43),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )
            panel_path = (
                panel_dir
                / f"{sequence_id:04d}_{condition}_{panels_by_condition[condition] + 1}.jpg"
            )
            cv2.imwrite(str(panel_path), panel, [cv2.IMWRITE_JPEG_QUALITY, 92])
            panels_by_condition[condition] += 1

    write_jsonl(OUT / "candidate_phone_frames.jsonl", output_rows)
    condition_rows: list[dict[str, Any]] = []
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in output_rows:
        grouped[row["condition_id"]].append(row)
    for condition, rows in grouped.items():
        physical_left = sum(bool(row["physical_left_visible"]) for row in rows)
        physical_right = sum(bool(row["physical_right_visible"]) for row in rows)
        left_hits = sum(
            bool(row["left_hand"]["localizer_observed"])
            for row in rows
            if row["physical_left_visible"]
        )
        right_hits = sum(
            bool(row["right_hand"]["localizer_observed"])
            for row in rows
            if row["physical_right_visible"]
        )
        complete_two = sum(
            bool(row["left_hand"]["localizer_observed"] and row["right_hand"]["localizer_observed"])
            for row in rows
            if row["physical_left_visible"] and row["physical_right_visible"]
        )
        expected_two = sum(
            bool(row["physical_left_visible"] and row["physical_right_visible"]) for row in rows
        )
        false_slots = sum(
            (bool(row["left_hand"]["localizer_observed"]) and not row["physical_left_visible"])
            + (bool(row["right_hand"]["localizer_observed"]) and not row["physical_right_visible"])
            for row in rows
        )
        condition_rows.append(
            {
                "condition_id": condition,
                "frames": len(rows),
                "physical_left_frames": physical_left,
                "left_observed_rate": left_hits / physical_left if physical_left else None,
                "physical_right_frames": physical_right,
                "right_observed_rate": right_hits / physical_right if physical_right else None,
                "physical_two_frames": expected_two,
                "complete_two_rate": complete_two / expected_two if expected_two else None,
                "false_slot_rate": false_slots / (2 * len(rows)),
                "body_available_rate": sum(bool(row["body"]["available"]) for row in rows)
                / len(rows),
                "inference_p50_ms": percentile((row["inference_ms"] for row in rows), 0.50),
                "inference_p95_ms": percentile((row["inference_ms"] for row in rows), 0.95),
            }
        )
    write_csv(OUT / "condition_metrics.csv", condition_rows)

    visible_left = [row for row in output_rows if row["physical_left_visible"]]
    visible_right = [row for row in output_rows if row["physical_right_visible"]]
    two_hand = [
        row for row in output_rows if row["physical_left_visible"] and row["physical_right_visible"]
    ]
    no_usable_hand = [
        row
        for row in output_rows
        if not row["physical_left_visible"] and not row["physical_right_visible"]
    ]
    unilateral = [
        row for row in output_rows if row["physical_left_visible"] ^ row["physical_right_visible"]
    ]
    articulation = [row for row in output_rows if row["condition_id"] == "C8_FINGER_ARTICULATION"]

    articulation_descriptors: defaultdict[str, list[np.ndarray]] = defaultdict(list)
    for row in articulation:
        for hand_name in ("left_hand", "right_hand"):
            points = np.asarray(row[hand_name]["xy_source"], np.float64)
            wrist_centered = points - points[0]
            scale_value = np.median(
                [np.linalg.norm(points[index] - points[0]) for index in (5, 9, 13, 17)]
            )
            if scale_value > 1e-6:
                articulation_descriptors[row["operator_note"]].append(
                    (wrist_centered / scale_value).reshape(-1)
                )
    prototypes = {
        name: np.median(np.stack(values), axis=0)
        for name, values in articulation_descriptors.items()
        if values
    }
    prototype_distances = {
        f"{left}_vs_{right}": float(np.linalg.norm(prototypes[left] - prototypes[right]))
        for index, left in enumerate(sorted(prototypes))
        for right in sorted(prototypes)[index + 1 :]
    }

    result = {
        "schema": "APPHEAR_PERCEPTION_VNEXT_OFFLINE_VIABILITY_RESULT_V1",
        "candidate_id": manifest["candidate_id"],
        "status": "MEASURED_NOT_PROMOTED",
        "frames": len(output_rows),
        "source": "frozen P8-C3B1 Xiaomi M2101K7AG upright-unmirrored phone frames",
        "teacher_role": "frozen DWPose-L reference, not human landmark truth",
        "runtime": {
            "backend": "ONNX Runtime CPU",
            "threads": 4,
            "inference_ms": stats(timings),
            "model_bytes": ONNX.stat().st_size,
            "model_sha256": sha256(ONNX),
        },
        "hands": {
            "visible_left_observation_rate": sum(
                bool(row["left_hand"]["localizer_observed"]) for row in visible_left
            )
            / len(visible_left),
            "visible_right_observation_rate": sum(
                bool(row["right_hand"]["localizer_observed"]) for row in visible_right
            )
            / len(visible_right),
            "complete_two_hand_rate": sum(
                bool(
                    row["left_hand"]["localizer_observed"]
                    and row["right_hand"]["localizer_observed"]
                )
                for row in two_hand
            )
            / len(two_hand),
            "no_usable_hand_false_observation_rate": sum(
                bool(
                    row["left_hand"]["localizer_observed"]
                    or row["right_hand"]["localizer_observed"]
                )
                for row in no_usable_hand
            )
            / len(no_usable_hand),
            "unilateral_exact_anatomical_state_rate": sum(
                bool(row["left_hand"]["localizer_observed"]) == bool(row["physical_left_visible"])
                and bool(row["right_hand"]["localizer_observed"])
                == bool(row["physical_right_visible"])
                for row in unilateral
            )
            / len(unilateral),
            "left_teacher_error_image_diagonal": stats(
                row["left_hand"]["teacher_median_error_image_diagonal"] for row in visible_left
            ),
            "right_teacher_error_image_diagonal": stats(
                row["right_hand"]["teacher_median_error_image_diagonal"] for row in visible_right
            ),
            "articulation_prototype_distances": prototype_distances,
        },
        "body": {
            "person_visible_availability_rate": sum(
                bool(row["body"]["available"]) for row in output_rows if row["person_visible"]
            )
            / sum(bool(row["person_visible"]) for row in output_rows),
            "no_person_false_availability_rate": sum(
                bool(row["body"]["available"]) for row in output_rows if not row["person_visible"]
            )
            / sum(not bool(row["person_visible"]) for row in output_rows),
        },
        "representation": {
            "body": "8 selected COCO-WholeBody joints: xy + native support + validity",
            "hands": "21 joints per anatomical side: xy + native support + validity + observed",
            "coordinates": "upright-unmirrored source pixels",
            "missingness": "explicit; no coordinate carries observation meaning",
            "depth": "none",
            "temporal_carry": "none",
        },
        "scope": {
            "recognition_training": False,
            "recognizer_inference": False,
            "s5_s7_ui": False,
            "five_sign": False,
        },
        "next_decision": (
            "human visual inspection plus metric review before crop-refiner integration"
        ),
    }
    write_json(OUT / "viability_result.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run",))
    args = parser.parse_args()
    if args.command == "run":
        return run()
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
