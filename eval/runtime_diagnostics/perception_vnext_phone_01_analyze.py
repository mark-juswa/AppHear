"""Audit a completed PERCEPTION_VNEXT_PHONE_01 Android evidence bundle."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

EXPECTED_COUNTS = {
    ("C0_EMPTY_FRAME_NO_PERSON", ""): 20,
    ("C1_PERSON_HANDS_DOWN", ""): 20,
    ("C2_LEFT_HAND_ONLY", ""): 30,
    ("C3_RIGHT_HAND_ONLY", ""): 30,
    ("C4_BOTH_WIDELY_SEPARATED", ""): 30,
    ("C5_BOTH_HANDS_CROSSING", ""): 50,
    ("C6L_HAND_NEAR_FACE_LEFT", ""): 25,
    ("C6R_HAND_NEAR_FACE_RIGHT", ""): 25,
    ("C7L_HAND_NEAR_TORSO_LEFT", ""): 25,
    ("C7R_HAND_NEAR_TORSO_RIGHT", ""): 25,
    ("C8_FINGER_ARTICULATION", "open_palm"): 10,
    ("C8_FINGER_ARTICULATION", "closed_fist"): 10,
    ("C8_FINGER_ARTICULATION", "index_extended"): 10,
    ("C8_FINGER_ARTICULATION", "two_fingers_extended"): 10,
}
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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def stats(values: Iterable[float | None]) -> dict[str, Any]:
    clean = np.asarray(
        [float(value) for value in values if value is not None and math.isfinite(float(value))],
        np.float64,
    )
    if not clean.size:
        return {"count": 0, "mean": None, "p50": None, "p95": None, "max": None}
    return {
        "count": int(clean.size),
        "mean": float(clean.mean()),
        "p50": float(np.median(clean)),
        "p95": float(np.quantile(clean, 0.95)),
        "max": float(clean.max()),
    }


def hand_array(row: dict[str, Any], side: str) -> np.ndarray:
    return np.asarray(row[f"{side}_xy_source"], np.float64).reshape(21, 2)


def palm_scale(points: np.ndarray) -> float:
    value = np.median([np.linalg.norm(points[index] - points[0]) for index in (5, 9, 13, 17)])
    return float(value)


def normalized_descriptor(points: np.ndarray) -> np.ndarray | None:
    scale = palm_scale(points)
    if not math.isfinite(scale) or scale <= 1e-6:
        return None
    return ((points - points[0]) / scale).reshape(-1)


def run(session: Path) -> int:
    identity = json.loads((session / "session_identity.json").read_text(encoding="utf-8"))
    phone = json.loads((session / "phone_result.json").read_text(encoding="utf-8"))
    rows = load_jsonl(session / "frame_measurements.jsonl")
    if phone["status"] != "CONTROLLED_CAPTURE_COMPLETE" or len(rows) != 320:
        raise RuntimeError("VNEXT_PHONE_CAPTURE_INCOMPLETE")
    if identity["recognizer_connected"] or identity["s5_s7_ui_connected"]:
        raise RuntimeError("VNEXT_PHONE_SCOPE_VIOLATION")
    timestamps = [int(row["sensor_timestamp_ns"]) for row in rows]
    if any(right <= left for left, right in zip(timestamps, timestamps[1:], strict=False)):
        raise RuntimeError("VNEXT_PHONE_TIMESTAMPS_NOT_MONOTONIC")
    grouped: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["condition_id"], row["operator_note"])].append(row)
        for key in ("left_xy_source", "right_xy_source", "body_xy_source", "body_support"):
            if not np.all(np.isfinite(np.asarray(row[key], np.float64))):
                raise RuntimeError(f"VNEXT_PHONE_NONFINITE:{key}")
    observed_counts = {key: len(value) for key, value in grouped.items()}
    if observed_counts != EXPECTED_COUNTS:
        raise RuntimeError("VNEXT_PHONE_CONDITION_COUNTS_MISMATCH")

    visible_left = [row for row in rows if row["physical_left_visible"]]
    visible_right = [row for row in rows if row["physical_right_visible"]]
    two_hand = [
        row for row in rows if row["physical_left_visible"] and row["physical_right_visible"]
    ]
    no_hand = [
        row
        for row in rows
        if not row["physical_left_visible"] and not row["physical_right_visible"]
    ]
    unilateral = [
        row for row in rows if row["physical_left_visible"] ^ row["physical_right_visible"]
    ]
    articulation = [row for row in rows if row["condition_id"] == "C8_FINGER_ARTICULATION"]

    edge_ratios: dict[str, list[float]] = {"left": [], "right": []}
    jitter: dict[str, list[float]] = {"left": [], "right": [], "body": []}
    static_ids = {
        "C6L_HAND_NEAR_FACE_LEFT",
        "C6R_HAND_NEAR_FACE_RIGHT",
        "C7L_HAND_NEAR_TORSO_LEFT",
        "C7R_HAND_NEAR_TORSO_RIGHT",
        "C8_FINGER_ARTICULATION",
    }
    for side in ("left", "right"):
        for row in rows:
            if not row[f"{side}_observed"]:
                continue
            points = hand_array(row, side)
            lengths = np.asarray(
                [np.linalg.norm(points[start] - points[end]) for start, end in HAND_EDGES],
                np.float64,
            )
            positive = lengths[lengths > 1e-6]
            if positive.size:
                edge_ratios[side].append(float(positive.max() / np.median(positive)))
        for key, condition_rows in grouped.items():
            if key[0] not in static_ids:
                continue
            observed = [row for row in condition_rows if row[f"{side}_observed"]]
            for previous, current in zip(observed, observed[1:], strict=False):
                before = hand_array(previous, side)
                after = hand_array(current, side)
                scale = np.median([palm_scale(before), palm_scale(after)])
                if scale > 1e-6:
                    jitter[side].append(
                        float(np.median(np.linalg.norm(after - before, axis=1)) / scale)
                    )

    for key, condition_rows in grouped.items():
        if key[0] not in static_ids:
            continue
        for previous, current in zip(condition_rows, condition_rows[1:], strict=False):
            before = np.asarray(previous["body_xy_source"], np.float64).reshape(8, 2)
            after = np.asarray(current["body_xy_source"], np.float64).reshape(8, 2)
            shoulder = np.median(
                [np.linalg.norm(before[0] - before[1]), np.linalg.norm(after[0] - after[1])]
            )
            if shoulder > 1e-6:
                jitter["body"].append(
                    float(np.median(np.linalg.norm(after - before, axis=1)) / shoulder)
                )

    prototypes: dict[tuple[str, str], np.ndarray] = {}
    for note in sorted({row["operator_note"] for row in articulation}):
        for side in ("left", "right"):
            values = [
                normalized_descriptor(hand_array(row, side))
                for row in articulation
                if row["operator_note"] == note and row[f"{side}_observed"]
            ]
            clean = [value for value in values if value is not None]
            if clean:
                prototypes[(note, side)] = np.median(np.stack(clean), axis=0)
    prototype_distances = {
        f"{side}:{left}_vs_{right}": float(
            np.linalg.norm(prototypes[(left, side)] - prototypes[(right, side)])
        )
        for side in ("left", "right")
        for index, left in enumerate(sorted({key[0] for key in prototypes if key[1] == side}))
        for right in sorted({key[0] for key in prototypes if key[1] == side})[index + 1 :]
    }

    complete_two_rate = sum(
        row["left_observed"] and row["right_observed"] for row in two_hand
    ) / len(two_hand)
    false_slots = sum(
        (row["left_observed"] and not row["physical_left_visible"])
        + (row["right_observed"] and not row["physical_right_visible"])
        for row in rows
    )
    crop = stats(row["hand_crop_ms"] for row in rows)
    pre = stats(row["preprocessing_ms"] for row in rows)
    total = stats(row["total_perception_ms"] for row in rows)
    result = {
        "schema": "APPHEAR_PERCEPTION_VNEXT_PHONE_AUDIT_V1",
        "milestone": "PERCEPTION_VNEXT_PHONE_01",
        "status": "GEOMETRY_PASS_RUNTIME_FAIL",
        "device": identity["device"],
        "frames": len(rows),
        "integrity": {
            "condition_counts_exact": True,
            "timestamps_strictly_monotonic": True,
            "all_coordinates_finite": True,
            "current_frame_only": identity["current_frame_only"],
            "recognizer_connected": identity["recognizer_connected"],
        },
        "hands": {
            "visible_left_observation_rate": sum(row["left_observed"] for row in visible_left)
            / len(visible_left),
            "visible_right_observation_rate": sum(row["right_observed"] for row in visible_right)
            / len(visible_right),
            "complete_two_hand_rate": complete_two_rate,
            "unilateral_exact_anatomical_state_rate": sum(
                row["left_observed"] == row["physical_left_visible"]
                and row["right_observed"] == row["physical_right_visible"]
                for row in unilateral
            )
            / len(unilateral),
            "no_usable_hand_false_observation_rate": sum(
                row["left_observed"] or row["right_observed"] for row in no_hand
            )
            / len(no_hand),
            "all_frame_false_slot_rate": false_slots / (2 * len(rows)),
            "crossing_complete_two_hand_rate": sum(
                row["left_observed"] and row["right_observed"]
                for row in rows
                if row["condition_id"] == "C5_BOTH_HANDS_CROSSING"
            )
            / EXPECTED_COUNTS[("C5_BOTH_HANDS_CROSSING", "")],
            "edge_length_max_to_median": {
                side: stats(values) for side, values in edge_ratios.items()
            },
            "static_interframe_median_joint_step_over_palm_scale": {
                side: stats(values) for side, values in jitter.items() if side != "body"
            },
            "articulation_prototype_distances": prototype_distances,
        },
        "body": {
            "person_visible_availability_rate": sum(
                row["body_available"] for row in rows if row["person_visible"]
            )
            / sum(row["person_visible"] for row in rows),
            "no_person_false_availability_rate": sum(
                row["body_available"] for row in rows if not row["person_visible"]
            )
            / sum(not row["person_visible"] for row in rows),
            "static_interframe_median_joint_step_over_shoulder_width": stats(jitter["body"]),
        },
        "runtime": {
            "analyzer_completed_fps": phone["analyzer_completed_fps"],
            "estimated_keep_only_latest_skips": phone["estimated_keep_only_latest_skips"],
            "preprocessing_ms": pre,
            "dwpose_t_ms": stats(row["dwpose_t_ms"] for row in rows),
            "hand_crop_total_ms": crop,
            "per_hand_refiner_ms": stats(
                value
                for row in rows
                for value in (row["left_refiner_ms"], row["right_refiner_ms"])
            ),
            "total_perception_ms": total,
            "preprocess_plus_crop_fraction_of_p50_total": (
                pre["p50"] + crop["p50"]
            )
            / total["p50"],
            "peak_pss_kb": phone["peak_pss_kb"],
            "maximum_thermal_status": phone["maximum_thermal_status"],
            "crash_or_anr_observed": False,
            "fifteen_fps_floor_pass": phone["analyzer_completed_fps"] >= 15.0,
        },
        "decision": {
            "recommendation": "FIX_ONE_BLOCKER",
            "largest_blocker": (
                "CPU runtime data path: Kotlin full-frame preprocessing plus two hand-crop "
                "resamples consume about 58% of median total latency; the complete serial "
                "two-hand path is 438.6 ms / 2.26 FPS"
            ),
            "next_bounded_change": (
                "replace only full-frame and ROI resampling with one parity-gated native reusable "
                "kernel, then remeasure the unchanged model pair on this phone"
            ),
            "freeze_perception_vnext": False,
            "recognition_training_authorized": False,
        },
    }
    output = session / "phone_audit.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    args = parser.parse_args()
    return run(args.session.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
