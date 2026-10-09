"""P4-C3A: decompose frozen DWPose proposal misses and one-hand collisions."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from eval.runtime_diagnostics.p4a_dwpose_eligibility import BONES, body_scale


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement"
V2_DIR = BASE / "p4gt1r_schema_repair_v2_01"
V2 = V2_DIR / "P4_ELIGIBILITY_TRUTH_V2.csv"
V2_RESULT = V2_DIR / "p4gt1r_result.json"
INFERENCE = BASE / "p4a2_high_recall_rescue_final_01/p4a2_frozen_inference_manifest.csv"
V1 = BASE / "p4a2_fresh_evidence_repair_v2_01/frozen_truth/P4A2_FRESH_HUMAN_TRUTH_V1.csv"
CROP_DIR = BASE / "p4c2a_dwpose_rgb_crop_separability_01"
OUT = BASE / "p4c3a_raw_dwpose_failure_decomposition_01"

EXPECTED_V2_SHA256 = "24f5d8d442702e3a27424ff7f55cc24f1338f5683e5988a6a4916557e1d4252d"
EXPECTED_CHECKPOINT = "e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7"
BASE_CAPACITY = 419
VISIBLE_HANDS = 444
TARGET_CAPACITY = 436
LEFT_SLICE = slice(91, 112)
RIGHT_SLICE = slice(112, 133)

# Frozen before aggregate classification. These are diagnostic boundaries, not a runtime rule.
PROTOCOL = {
    "identity": "P4C3A_RAW_DWPOSE_FAILURE_DECOMPOSITION_V1",
    "scope": {"expected_missing_hands": 25, "expected_one_hand_dual_slot_collisions": 60},
    "raw_hand_geometry_A": {
        "finite_points_min": 11,
        "minimum_short_envelope_side_body_scale": 0.005,
        "minimum_long_envelope_side_body_scale": 0.02,
        "maximum_envelope_side_body_scale": 1.0,
        "median_bone_body_scale_range": [0.002, 0.25],
        "bone_cv_max": 1.75,
        "covariance_minor_major_ratio_min": 0.005,
        "hand_wrist_to_body_wrist_body_scale_max": 0.45,
        "center_frame_margin_fraction": 0.10,
        "interpretation": "spatially coherent raw native hand block rejected by the frozen 0.30+11/21 proposal gate",
    },
    "arm_context_B": {
        "required_finite_points": ["shoulder", "elbow", "body_wrist"],
        "shoulder_score_min": 0.20,
        "elbow_score_min": 0.30,
        "body_wrist_score_min": 0.30,
        "elbow_wrist_body_scale_range": [0.03, 1.0],
        "wrist_frame_margin_fraction": 0.10,
        "interpretation": "raw hand geometry fails A but same-frame arm supplies a plausible ROI anchor/direction",
    },
    "collision": {
        "same_physical_hand": "intersection/min-area >=0.50 OR (normalized center distance <=0.60 AND IoU >=0.20)",
        "separate_false_region": "intersection/min-area <=0.10 AND normalized center distance >=1.00",
        "otherwise": "AMBIGUOUS_COLLISION",
        "center_distance_normalizer": "sqrt(min(proposal_area_left, proposal_area_right))",
    },
    "arm_association": {
        "strength": "-distance(proposal_center, corresponding_body_wrist)/body_scale + 0.25*direction_cosine",
        "preference_margin": 0.05,
    },
    "architecture_decision": {
        "A": "base+A >=436, C<=8, and collisions are mostly separate or arm-association true preference >=80%",
        "B": "A alone <436 but A+B >=436",
        "C": "A+B <436 or category C exceeds the 8-hand 98%-ceiling allowance",
        "ownership_required": "same-physical-hand duplicates >=20% of 60 collision frames",
    },
    "not_a_production_rule": True,
    "no_human_boxes": True,
    "no_threshold_tuning": True,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def atomic_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    rows = list(rows)
    fields = fields or (list(rows[0]) if rows else ["empty"])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def finite_vector(values: np.ndarray) -> bool:
    return bool(np.isfinite(values).all())


def direction_cos(elbow: np.ndarray, wrist: np.ndarray, center: np.ndarray) -> float:
    arm = wrist - elbow
    extension = center - wrist
    denominator = float(np.linalg.norm(arm) * np.linalg.norm(extension))
    return float(np.dot(arm, extension) / denominator) if denominator > 1e-8 else 0.0


def box_from_points(points: np.ndarray, width: int, height: int) -> np.ndarray:
    finite = points[np.isfinite(points).all(axis=1)]
    if len(finite) < 2:
        return np.asarray([0.0, 0.0, 0.0, 0.0])
    low = finite.min(axis=0)
    high = finite.max(axis=0)
    center = (low + high) / 2.0
    minimum = max(32.0, 0.10 * min(width, height))
    size = np.maximum((high - low) * 1.5, minimum)
    return np.asarray([
        max(0.0, center[0] - size[0] / 2), max(0.0, center[1] - size[1] / 2),
        min(float(width), center[0] + size[0] / 2), min(float(height), center[1] + size[1] / 2),
    ])


def box_metrics(first: np.ndarray, second: np.ndarray) -> dict[str, float]:
    iw = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    ih = max(0.0, min(first[3], second[3]) - max(first[1], second[1]))
    intersection = iw * ih
    area_a = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    area_b = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = area_a + area_b - intersection
    center_a = np.asarray([(first[0] + first[2]) / 2, (first[1] + first[3]) / 2])
    center_b = np.asarray([(second[0] + second[2]) / 2, (second[1] + second[3]) / 2])
    center_distance = float(np.linalg.norm(center_a - center_b))
    normalizer = math.sqrt(max(min(area_a, area_b), 1e-8))
    return {
        "iou": intersection / union if union else 0.0,
        "intersection_area": intersection,
        "intersection_min_area_ratio": intersection / min(area_a, area_b) if min(area_a, area_b) else 0.0,
        "center_distance_px": center_distance,
        "center_distance_normalized": center_distance / normalizer,
        "proposal_scale_ratio": max(area_a, area_b) / max(min(area_a, area_b), 1e-8),
    }


def verify() -> tuple[list[dict[str, str]], dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    if sha256(V2) != EXPECTED_V2_SHA256:
        raise RuntimeError("P4C3A_SOURCE_INTEGRITY_FAILURE")
    v2_result = json.loads(V2_RESULT.read_text(encoding="utf-8"))
    if v2_result["classification"] != "P4GT1R_V2_READY_FOR_ARCHITECTURE_DECISIONS":
        raise RuntimeError("P4C3A_SOURCE_INTEGRITY_FAILURE")
    v2 = read_csv(V2)
    inference = {row["annotation_row_id"]: row for row in read_csv(INFERENCE)}
    v1 = {row["annotation_row_id"]: row for row in read_csv(V1)}
    if len(v2) != 458 or len(inference) != 458 or len(v1) != 458:
        raise RuntimeError("P4C3A_SOURCE_INTEGRITY_FAILURE")
    if set(inference) != {row["frame_id"] for row in v2} or set(v1) != set(inference):
        raise RuntimeError("P4C3A_SOURCE_INTEGRITY_FAILURE")
    return v2, inference, v1


def native_path(item: dict[str, str]) -> Path:
    path = Path(item["raw_relative_path"])
    return path if path.is_absolute() else ROOT / path


def raw_geometry(points: np.ndarray, scores: np.ndarray, keypoints: np.ndarray, body_scores: np.ndarray,
                 side: str, width: int, height: int) -> dict[str, Any]:
    shoulder_i, elbow_i, wrist_i = (5, 7, 9) if side == "left" else (6, 8, 10)
    finite = points[np.isfinite(points).all(axis=1)]
    scale = body_scale(keypoints, width, height)
    envelope = np.ptp(finite, axis=0) if len(finite) else np.asarray([0.0, 0.0])
    bones = np.linalg.norm(points[BONES[:, 0]] - points[BONES[:, 1]], axis=1)
    covariance_ratio = 0.0
    if len(finite) >= 3:
        eigenvalues = np.linalg.eigvalsh(np.cov(finite.T))
        covariance_ratio = float(max(eigenvalues[0], 0.0) / max(eigenvalues[-1], 1e-8))
    hand_wrist = points[0]
    shoulder, elbow, wrist = keypoints[[shoulder_i, elbow_i, wrist_i]]
    center = finite.mean(axis=0) if len(finite) else np.asarray([math.nan, math.nan])
    short_side = float(np.min(envelope) / scale)
    long_side = float(np.max(envelope) / scale)
    median_bone = float(np.median(bones) / scale) if finite_vector(bones) else math.inf
    bone_cv = float(np.std(bones) / max(np.mean(bones), 1e-8)) if finite_vector(bones) else math.inf
    wrist_distance = float(np.linalg.norm(hand_wrist - wrist) / scale) if finite_vector(hand_wrist) and finite_vector(wrist) else math.inf
    center_inside = finite_vector(center) and (-0.10 * width <= center[0] <= 1.10 * width) and (-0.10 * height <= center[1] <= 1.10 * height)
    category_a = (
        len(finite) >= 11 and short_side >= 0.005 and long_side >= 0.02 and long_side <= 1.0
        and 0.002 <= median_bone <= 0.25 and bone_cv <= 1.75 and covariance_ratio >= 0.005
        and wrist_distance <= 0.45 and center_inside
    )
    forearm_norm = float(np.linalg.norm(wrist - elbow) / scale) if finite_vector(wrist) and finite_vector(elbow) else math.inf
    wrist_inside = finite_vector(wrist) and (-0.10 * width <= wrist[0] <= 1.10 * width) and (-0.10 * height <= wrist[1] <= 1.10 * height)
    category_b = (
        not category_a and finite_vector(shoulder) and finite_vector(elbow) and finite_vector(wrist)
        and body_scores[shoulder_i] >= 0.20 and body_scores[elbow_i] >= 0.30 and body_scores[wrist_i] >= 0.30
        and 0.03 <= forearm_norm <= 1.0 and wrist_inside
    )
    return {
        "finite_coordinate_count": len(finite), "confident_joint_count": int(np.count_nonzero(scores >= 0.30)),
        "score_min": float(np.min(scores)), "score_mean": float(np.mean(scores)), "score_median": float(np.median(scores)),
        "envelope_width_px": float(envelope[0]), "envelope_height_px": float(envelope[1]),
        "short_envelope_side_body_scale": short_side, "long_envelope_side_body_scale": long_side,
        "median_bone_body_scale": median_bone, "bone_cv": bone_cv, "covariance_minor_major_ratio": covariance_ratio,
        "hand_wrist_to_body_wrist_body_scale": wrist_distance, "shoulder_score": float(body_scores[shoulder_i]),
        "elbow_score": float(body_scores[elbow_i]), "body_wrist_score": float(body_scores[wrist_i]),
        "elbow_wrist_body_scale": forearm_norm, "center_inside_expanded_frame": bool(center_inside),
        "raw_geometry_A": bool(category_a), "arm_context_B": bool(category_b),
        "raw_hand_points_json": json.dumps(points.tolist(), separators=(",", ":")),
        "raw_hand_scores_json": json.dumps(scores.tolist(), separators=(",", ":")),
        "body_shoulder_json": json.dumps(shoulder.tolist(), separators=(",", ":")),
        "body_elbow_json": json.dumps(elbow.tolist(), separators=(",", ":")),
        "body_wrist_json": json.dumps(wrist.tolist(), separators=(",", ":")),
    }


def main() -> dict[str, Any]:
    v2, inference, v1 = verify()
    OUT.mkdir(parents=True, exist_ok=True)
    atomic_json(OUT / "p4c3a_diagnostic_protocol.json", PROTOCOL)
    sequence_bounds: dict[str, tuple[int, int]] = {}
    for sequence_id in {row["sequence_id"] for row in v2}:
        indices = [int(row["frame_index"]) for row in v2 if row["sequence_id"] == sequence_id]
        sequence_bounds[sequence_id] = (min(indices), max(indices))
    misses: list[dict[str, Any]] = []
    collisions: list[dict[str, Any]] = []
    collision_metric_rows: list[dict[str, Any]] = []
    arm_rows: list[dict[str, Any]] = []
    raw_cache: dict[str, dict[str, Any]] = {}

    for truth in v2:
        frame_id = truth["frame_id"]
        item = inference[frame_id]
        path = native_path(item)
        if not path.is_file():
            raise RuntimeError(f"P4C3A_NATIVE_OUTPUT_MISSING: {path}")
        with np.load(path, allow_pickle=False) as native:
            if str(native["source_sha256"].item()) != truth["source_sha256"] or str(native["checkpoint_sha256"].item()) != EXPECTED_CHECKPOINT:
                raise RuntimeError("P4C3A_SOURCE_INTEGRITY_FAILURE")
            keypoints = np.asarray(native["keypoints_133"], dtype=np.float64)
            scores = np.asarray(native["scores_133"], dtype=np.float64)
            gated = np.asarray(native["gated_presence"], dtype=bool).reshape(2)
            roi = np.asarray(native["roi_xyxy"], dtype=np.float64)
        width, height = int(round(roi[2])), int(round(roi[3]))
        raw_cache[frame_id] = {"keypoints": keypoints, "scores": scores, "gated": gated, "width": width, "height": height, "path": path}
        for side_index, side in enumerate(("left", "right")):
            if truth[f"{side}_visibility"] != "YES" or gated[side_index]:
                continue
            section = LEFT_SLICE if side == "left" else RIGHT_SLICE
            diagnostic = raw_geometry(keypoints[section], scores[section], keypoints, scores, side, width, height)
            category = "A_RAW_HAND_GEOMETRY_PRESENT" if diagnostic["raw_geometry_A"] else "B_HAND_WEAK_ARM_CONTEXT_USABLE" if diagnostic["arm_context_B"] else "C_NO_USABLE_SECOND_HAND_GEOMETRY"
            old = v1[frame_id]
            first_index, last_index = sequence_bounds[truth["sequence_id"]]
            position = (int(truth["frame_index"]) - first_index) / max(last_index - first_index, 1)
            misses.append({
                "frame_id": frame_id, "sequence_id": truth["sequence_id"], "signer_id": truth["signer_id"],
                "frame_index": truth["frame_index"], "anatomical_side": side.upper(),
                "governed_sequence_position_fraction": position,
                "hand_context": "TWO_HAND" if truth["visible_hand_count"] == "TWO" else "ONE_HAND",
                "source_image_path": truth["source_image_path"], "source_sha256": truth["source_sha256"],
                "native_output_path": str(path), "current_proposal_qualified": "NO", "primary_category": category,
                "historical_blur": old.get("blur", ""), "historical_occlusion": old.get("occlusion", ""),
                "historical_edge_clipped": old.get("edge_clipped", ""), "historical_partial_visibility": old.get("partial_visibility", ""),
                "historical_hand_hand_contact": old.get("hand_hand_contact", ""), "historical_hand_body_contact": old.get("hand_body_contact", ""),
                **diagnostic,
            })

        if truth["visible_hand_count"] == "ONE" and truth["one_hand_ownership"] in {"LEFT", "RIGHT"} and bool(gated[0]) and bool(gated[1]):
            left_points = keypoints[LEFT_SLICE]
            right_points = keypoints[RIGHT_SLICE]
            left_box = box_from_points(left_points, width, height)
            right_box = box_from_points(right_points, width, height)
            metrics = box_metrics(left_box, right_box)
            if metrics["intersection_min_area_ratio"] >= 0.50 or (metrics["center_distance_normalized"] <= 0.60 and metrics["iou"] >= 0.20):
                collision_category = "SAME_PHYSICAL_HAND_DUPLICATE"
            elif metrics["intersection_min_area_ratio"] <= 0.10 and metrics["center_distance_normalized"] >= 1.00:
                collision_category = "SEPARATE_FALSE_REGION"
            else:
                collision_category = "AMBIGUOUS_COLLISION"
            true_side = truth["one_hand_ownership"].lower()
            false_side = "right" if true_side == "left" else "left"
            centers = {
                "left": np.asarray([(left_box[0] + left_box[2]) / 2, (left_box[1] + left_box[3]) / 2]),
                "right": np.asarray([(right_box[0] + right_box[2]) / 2, (right_box[1] + right_box[3]) / 2]),
            }
            scale = body_scale(keypoints, width, height)
            arm_data: dict[str, dict[str, float]] = {}
            for side in ("left", "right"):
                shoulder_i, elbow_i, wrist_i = (5, 7, 9) if side == "left" else (6, 8, 10)
                wrist = keypoints[wrist_i]
                opposite_wrist = keypoints[10 if side == "left" else 9]
                own_distance = float(np.linalg.norm(centers[side] - wrist) / scale)
                opposite_distance = float(np.linalg.norm(centers[side] - opposite_wrist) / scale)
                cosine = direction_cos(keypoints[elbow_i], wrist, centers[side])
                arm_data[side] = {"own_wrist_distance": own_distance, "opposite_wrist_distance": opposite_distance, "direction_cosine": cosine, "strength": -own_distance + 0.25 * cosine}
            delta = arm_data[true_side]["strength"] - arm_data[false_side]["strength"]
            preference = "TRUE_SLOT_PREFERRED" if delta > 0.05 else "FALSE_SLOT_PREFERRED" if delta < -0.05 else "TIE_AMBIGUOUS"
            common = {
                "frame_id": frame_id, "sequence_id": truth["sequence_id"], "signer_id": truth["signer_id"],
                "frame_index": truth["frame_index"], "true_anatomical_side": true_side.upper(), "false_anatomical_side": false_side.upper(),
                "source_sha256": truth["source_sha256"], "source_image_path": truth["source_image_path"],
                "native_output_path": str(path),
                "left_box_json": json.dumps(left_box.tolist(), separators=(",", ":")), "right_box_json": json.dumps(right_box.tolist(), separators=(",", ":")),
                "left_hand_keypoints_json": json.dumps(left_points.tolist(), separators=(",", ":")),
                "right_hand_keypoints_json": json.dumps(right_points.tolist(), separators=(",", ":")),
                "left_shoulder_json": json.dumps(keypoints[5].tolist(), separators=(",", ":")),
                "left_elbow_json": json.dumps(keypoints[7].tolist(), separators=(",", ":")),
                "left_wrist_json": json.dumps(keypoints[9].tolist(), separators=(",", ":")),
                "right_shoulder_json": json.dumps(keypoints[6].tolist(), separators=(",", ":")),
                "right_elbow_json": json.dumps(keypoints[8].tolist(), separators=(",", ":")),
                "right_wrist_json": json.dumps(keypoints[10].tolist(), separators=(",", ":")),
                "collision_category": collision_category,
            }
            collisions.append(common)
            collision_metric_rows.append({**common, **metrics,
                "left_to_left_wrist_norm": arm_data["left"]["own_wrist_distance"], "left_to_right_wrist_norm": arm_data["left"]["opposite_wrist_distance"],
                "right_to_right_wrist_norm": arm_data["right"]["own_wrist_distance"], "right_to_left_wrist_norm": arm_data["right"]["opposite_wrist_distance"],
                "left_direction_cosine": arm_data["left"]["direction_cosine"], "right_direction_cosine": arm_data["right"]["direction_cosine"],
                "left_proposal_scale": float((left_box[2]-left_box[0])*(left_box[3]-left_box[1])),
                "right_proposal_scale": float((right_box[2]-right_box[0])*(right_box[3]-right_box[1])),
            })
            arm_rows.append({**common,
                "true_slot_strength": arm_data[true_side]["strength"], "false_slot_strength": arm_data[false_side]["strength"],
                "strength_delta_true_minus_false": delta, "arm_association_preference": preference,
                "true_slot_own_wrist_distance_norm": arm_data[true_side]["own_wrist_distance"],
                "false_slot_own_wrist_distance_norm": arm_data[false_side]["own_wrist_distance"],
                "true_slot_direction_cosine": arm_data[true_side]["direction_cosine"],
                "false_slot_direction_cosine": arm_data[false_side]["direction_cosine"],
            })

    if len(misses) != 25 or len(collisions) != 60:
        raise RuntimeError(f"P4C3A_FROZEN_COUNT_MISMATCH: misses={len(misses)}, collisions={len(collisions)}")

    category_counter = Counter(row["primary_category"] for row in misses)
    category_counts = {
        "A_RAW_HAND_GEOMETRY_PRESENT": category_counter["A_RAW_HAND_GEOMETRY_PRESENT"],
        "B_HAND_WEAK_ARM_CONTEXT_USABLE": category_counter["B_HAND_WEAK_ARM_CONTEXT_USABLE"],
        "C_NO_USABLE_SECOND_HAND_GEOMETRY": category_counter["C_NO_USABLE_SECOND_HAND_GEOMETRY"],
        "D_TRUTH_OR_FRAME_UNCERTAIN": category_counter["D_TRUTH_OR_FRAME_UNCERTAIN"],
    }
    context_counts = Counter(row["hand_context"] for row in misses)
    capacity_a = BASE_CAPACITY + category_counts["A_RAW_HAND_GEOMETRY_PRESENT"]
    capacity_ab = capacity_a + category_counts["B_HAND_WEAK_ARM_CONTEXT_USABLE"]
    recoverability = {
        "base_capacity": {"numerator": BASE_CAPACITY, "denominator": VISIBLE_HANDS, "rate": BASE_CAPACITY / VISIBLE_HANDS},
        "category_counts": dict(category_counts),
        "with_A": {"numerator": capacity_a, "denominator": VISIBLE_HANDS, "rate": capacity_a / VISIBLE_HANDS, "reaches_436": capacity_a >= TARGET_CAPACITY},
        "with_A_plus_B": {"numerator": capacity_ab, "denominator": VISIBLE_HANDS, "rate": capacity_ab / VISIBLE_HANDS, "reaches_436": capacity_ab >= TARGET_CAPACITY},
        "proposal_region_only_not_recognition_recovery": True,
    }

    crop_manifest = {(row["annotation_row_id"], row["anatomical_side"].lower()): row for row in read_csv(CROP_DIR / "p4c2a_crop_generation_manifest.csv")}
    crop_review = {row["crop_id"]: row for row in read_csv(CROP_DIR / "p4c2a_human_crop_review.csv") if row["reviewer_status"] == "COMPLETE"}
    crop_overlap: list[dict[str, Any]] = []
    for collision in collisions:
        frame_id = collision["frame_id"]
        true_side = collision["true_anatomical_side"].lower()
        false_side = collision["false_anatomical_side"].lower()
        values: dict[str, Any] = {**collision}
        for role, side in (("true", true_side), ("false", false_side)):
            crop = crop_manifest.get((frame_id, side))
            review = crop_review.get(crop["crop_id"]) if crop else None
            values[f"{role}_slot_crop_id"] = crop["crop_id"] if crop else ""
            values[f"{role}_slot_crop_reviewed"] = "YES" if review else "NO"
            values[f"{role}_slot_crop_label"] = review["reviewer_label"] if review else ""
            values[f"{role}_slot_rgb_hand_present"] = "YES" if review and review["reviewer_label"] in {"YES_CLEAR", "YES_PARTIAL"} else "NO" if review and review["reviewer_label"] == "NO" else "UNCERTAIN" if review else ""
        crop_overlap.append(values)

    collision_counter = Counter(row["collision_category"] for row in collisions)
    collision_counts = {
        "SAME_PHYSICAL_HAND_DUPLICATE": collision_counter["SAME_PHYSICAL_HAND_DUPLICATE"],
        "SEPARATE_FALSE_REGION": collision_counter["SEPARATE_FALSE_REGION"],
        "AMBIGUOUS_COLLISION": collision_counter["AMBIGUOUS_COLLISION"],
    }
    arm_counts = Counter(row["arm_association_preference"] for row in arm_rows if row["collision_category"] == "SAME_PHYSICAL_HAND_DUPLICATE")
    duplicates = collision_counts["SAME_PHYSICAL_HAND_DUPLICATE"]
    true_pref_rate = arm_counts["TRUE_SLOT_PREFERRED"] / duplicates if duplicates else None
    false_reviewed = [row for row in crop_overlap if row["false_slot_crop_reviewed"] == "YES"]
    true_reviewed = [row for row in crop_overlap if row["true_slot_crop_reviewed"] == "YES"]
    false_present = sum(row["false_slot_rgb_hand_present"] == "YES" for row in false_reviewed)
    false_absent = sum(row["false_slot_rgb_hand_present"] == "NO" for row in false_reviewed)
    true_present = sum(row["true_slot_rgb_hand_present"] == "YES" for row in true_reviewed)
    true_absent = sum(row["true_slot_rgb_hand_present"] == "NO" for row in true_reviewed)
    if false_present + false_absent == 0:
        rgb_useful = "INSUFFICIENT_OVERLAP"
    elif false_absent / (false_present + false_absent) >= 0.80:
        rgb_useful = "YES_FOR_MOST_REVIEWED_COLLISIONS"
    elif false_absent > 0:
        rgb_useful = "PARTIAL_FALSE_REGION_REJECTION_ONLY"
    else:
        rgb_useful = "NO_FOR_REVIEWED_COLLISIONS"

    c_count = category_counts["C_NO_USABLE_SECOND_HAND_GEOMETRY"]
    collision_disambiguable = collision_counts["SEPARATE_FALSE_REGION"] >= duplicates or (true_pref_rate is not None and true_pref_rate >= 0.80)
    if capacity_ab < TARGET_CAPACITY or c_count > 8:
        final_path = "C_TARGETED_SECOND_STAGE_LANDMARK_RECOVERY_REQUIRED"
        rationale = "A+B cannot satisfy the 98% proposal ceiling, or category C exceeds the eight-hand ceiling allowance."
    elif capacity_a >= TARGET_CAPACITY and c_count <= 8:
        final_path = "A_RAW_CANDIDATE_RGB_VERIFY"
        rationale = "Raw category-A candidates reach the proposal target; arm fallback adds only marginal coverage. The independent ownership-required flag remains mandatory because RGB authenticity cannot resolve duplicated real-hand slots."
    else:
        final_path = "B_ARM_WRIST_ROI_RGB_VERIFY"
        rationale = "Raw A alone is insufficient, while A+B reaches the proposal target using same-frame arm context."
    ownership_required = duplicates >= 12
    decision = {
        "final_path": final_path, "rationale": rationale, "ownership_required": ownership_required,
        "collision_disambiguable_under_diagnostic": collision_disambiguable,
        "rgb_authenticity_usefulness_for_reviewed_collisions": rgb_useful,
        "no_implementation_authorized": True,
    }

    atomic_csv(OUT / "p4c3a_missing_hand_inventory.csv", misses)
    atomic_csv(OUT / "p4c3a_missing_hand_classification.csv", misses)
    atomic_json(OUT / "p4c3a_missing_hand_recoverability.json", recoverability)
    atomic_csv(OUT / "p4c3a_collision_inventory.csv", collisions)
    atomic_csv(OUT / "p4c3a_collision_spatial_metrics.csv", collision_metric_rows)
    atomic_csv(OUT / "p4c3a_collision_classification.csv", collisions)
    atomic_csv(OUT / "p4c3a_arm_association_diagnostic.csv", arm_rows)
    atomic_csv(OUT / "p4c3a_crop_overlap_diagnostic.csv", crop_overlap)
    atomic_json(OUT / "p4c3a_architecture_decision.json", decision)

    result = {
        "status": "P4C3A_COMPLETE", "v2_hash_verified": True, "models_rerun": False,
        "missing_hand_observations": len(misses), "one_hand_misses": context_counts["ONE_HAND"],
        "two_hand_misses": context_counts["TWO_HAND"], "missing_categories": dict(category_counts),
        "recoverability": recoverability, "collision_frames": len(collisions),
        "collision_categories": dict(collision_counts), "arm_association_on_duplicates": {
            "true_slot_preferred": arm_counts["TRUE_SLOT_PREFERRED"], "false_slot_preferred": arm_counts["FALSE_SLOT_PREFERRED"],
            "tie_ambiguous": arm_counts["TIE_AMBIGUOUS"], "true_slot_preference_rate": true_pref_rate,
        },
        "crop_review_overlap": {"collision_frames_with_any_review": sum(row["true_slot_crop_reviewed"] == "YES" or row["false_slot_crop_reviewed"] == "YES" for row in crop_overlap),
            "true_slot_reviewed": len(true_reviewed), "true_slot_rgb_hand_present": true_present,
            "true_slot_rgb_hand_absent": true_absent,
            "false_slot_reviewed": len(false_reviewed), "false_slot_rgb_hand_present": false_present,
            "false_slot_rgb_hand_absent": false_absent, "rgb_authenticity_usefulness": rgb_useful},
        "decision": decision,
    }
    atomic_json(OUT / "p4c3a_result.json", result)

    a = category_counts["A_RAW_HAND_GEOMETRY_PRESENT"]
    b = category_counts["B_HAND_WEAK_ARM_CONTEXT_USABLE"]
    d = category_counts["D_TRUTH_OR_FRAME_UNCERTAIN"]
    side_counts = Counter(row["anatomical_side"] for row in misses)
    signer_counts = Counter(row["signer_id"] for row in misses)
    sequence_counts = Counter(row["sequence_id"] for row in misses)
    sequence_table = "\n".join(
        f"| {sequence} | {count} |" for sequence, count in sorted(sequence_counts.items(), key=lambda item: (-item[1], item[0]))
    )
    signer_table = "\n".join(
        f"| {signer} | {count} |" for signer, count in sorted(signer_counts.items(), key=lambda item: (-item[1], item[0]))
    )
    report = f"""# P4-C3A Raw DWPose Failure Decomposition Result

## Decision

**`P4C3A_COMPLETE` — `{final_path}`.**

V2 hash `{EXPECTED_V2_SHA256}` was verified. All 458 preserved native outputs were present and
matched their source/checkpoint identities; DWPose was not rerun. Diagnostic criteria were frozen
in `p4c3a_diagnostic_protocol.json` before aggregate classification. They are not production rules.

## 1. Candidate-region coverage

- Missing visible-hand observations analyzed: **25**
- One-hand / two-hand misses: **{context_counts['ONE_HAND']} / {context_counts['TWO_HAND']}**
- Left / right misses: **{side_counts['LEFT']} / {side_counts['RIGHT']}**
- Affected signers / sequences: **{len(signer_counts)} / {len(sequence_counts)}**
- A raw coherent hand geometry: **{a}**
- B weak hand, usable same-frame arm context: **{b}**
- C no usable second-hand geometry: **{c_count}**
- D uncertain truth/frame: **{d}**
- Base proposal capacity: **419/444 = {419/444:.2%}**
- Theoretical capacity with A: **{capacity_a}/444 = {capacity_a/444:.2%}** — {'REACHES' if capacity_a >= 436 else 'DOES NOT REACH'} 436
- Theoretical capacity with A+B: **{capacity_ab}/444 = {capacity_ab/444:.2%}** — {'REACHES' if capacity_ab >= 436 else 'DOES NOT REACH'} 436

These are proposal-region ceilings only, not recognition or successful landmark recovery claims.

### Missing-hand distribution by sequence

| Sequence | Misses |
| --- | ---: |
{sequence_table}

### Missing-hand distribution by signer

| Signer | Misses |
| --- | ---: |
{signer_table}

Historical optional blur/occlusion/contact/edge/partial fields are retained row-by-row in the
inventory. They are not promoted into new condition truth and no missing condition label was
invented.

## 2. RGB authenticity

The existing crop review overlaps **{sum(row['true_slot_crop_reviewed'] == 'YES' or row['false_slot_crop_reviewed'] == 'YES' for row in crop_overlap)}/60** collision frames.
Among reviewed true-slot crops, **{true_present}** visibly contain a real hand and **{true_absent}**
contain no hand. Among reviewed false-slot crops, **{false_present}** visibly contain a real hand
and **{false_absent}** contain no hand; uncertain cases remain excluded. Result:
**`{rgb_useful}`**. RGB authenticity can
reject visually empty regions, but it cannot by itself assign a duplicated real hand to anatomy.

## 3. Anatomical ownership

- SAME_PHYSICAL_HAND_DUPLICATE: **{duplicates}/60**
- SEPARATE_FALSE_REGION: **{collision_counts['SEPARATE_FALSE_REGION']}/60**
- AMBIGUOUS_COLLISION: **{collision_counts['AMBIGUOUS_COLLISION']}/60**
- Arm association on duplicates — true / false / tie: **{arm_counts['TRUE_SLOT_PREFERRED']} / {arm_counts['FALSE_SLOT_PREFERRED']} / {arm_counts['TIE_AMBIGUOUS']}**
- True-slot preference rate: **{f'{true_pref_rate:.2%}' if true_pref_rate is not None else 'not applicable'}**
- Ownership-required flag: **{'YES' if ownership_required else 'NO'}**

## Architecture interpretation

1. Candidate region availability: **{capacity_ab}/444 with A+B**.
2. Visual authenticity: **useful only where a crop is visually empty; real-hand duplicates remain ownership cases**.
3. Anatomical ownership: **separate unresolved layer**.

Selected path: **`{final_path}`**. {rationale}

No raw-candidate acceptance, arm fallback, verifier training, ownership heuristic, new model,
Android, recognition, or S4-S7 work was implemented.
"""
    atomic_text(OUT / "P4C3A_RAW_DWPOSE_FAILURE_DECOMPOSITION_RESULT.md", report)

    tracked = [path for path in OUT.iterdir() if path.is_file() and path.name != "p4c3a_artifact_hash_manifest.json"]
    atomic_json(OUT / "p4c3a_artifact_hash_manifest.json", {
        "status": "P4C3A_FROZEN_DIAGNOSTIC", "created_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": {path.name: sha256(path) for path in sorted(tracked)},
        "source_artifacts": {"v2": sha256(V2), "inference_manifest": sha256(INFERENCE),
            "crop_manifest": sha256(CROP_DIR / "p4c2a_crop_generation_manifest.csv"),
            "crop_review": sha256(CROP_DIR / "p4c2a_human_crop_review.csv"),
            "evaluator": sha256(Path(__file__)),
            "tests": sha256(ROOT / "tests/test_p4c3a_raw_dwpose_failure_decomposition.py")},
    })
    return result


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True, allow_nan=False))
