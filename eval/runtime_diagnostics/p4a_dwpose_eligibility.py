# ruff: noqa: E501
"""P4-A DWPose per-hand physical-visibility eligibility experiment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

PROJECT = Path(__file__).resolve().parents[2]
P3 = PROJECT / (
    "artifacts/recognition_upgrade/perception_backend_replacement/p3_dwpose_temporal_usability_01"
)
OUTPUT = PROJECT / (
    "artifacts/recognition_upgrade/perception_backend_replacement/"
    "p4a_dwpose_presence_eligibility_01"
)
EVALUATOR = Path(__file__).resolve()
P3_FRAMES = P3 / "frozen_frame_manifest.csv"
P3_SEQUENCES = P3 / "frozen_sequence_manifest.csv"
P3_RESULT = P3 / "p3_dwpose_temporal_result.json"
P3_HASHES = P3 / "artifact_hash_manifest.json"

SPLIT_SEED = 2026082204
SPLIT_SEARCH_TRIALS = 50_000
SPLIT_SIZES = {"train": 11, "validation": 5, "holdout": 5}
JOINT_THRESHOLD = 0.30
MIN_JOINTS = 11
LEFT_SLICE = slice(91, 112)
RIGHT_SLICE = slice(112, 133)
PALM = np.asarray([0, 5, 9, 13, 17])
MCP = np.asarray([5, 9, 13, 17])
TIPS = np.asarray([4, 8, 12, 16, 20])
BONES = np.asarray(
    [
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
    ]
)
BASE_FEATURES = [
    "hand_count_ge_030",
    "hand_score_min",
    "hand_score_mean",
    "hand_score_median",
    "hand_score_max",
    "hand_wrist_score",
    "mcp_score_mean",
    "mcp_score_min",
    "tip_score_mean",
    "tip_score_min",
    "hand_extent_width_norm",
    "hand_extent_height_norm",
    "hand_area_norm",
    "palm_spread_norm",
    "median_bone_norm",
    "bone_cv",
    "shoulder_score",
    "elbow_score",
    "body_wrist_score",
    "arm_score_min",
    "arm_score_mean",
    "shoulder_elbow_norm",
    "elbow_wrist_norm",
    "arm_length_ratio",
    "arm_angle_cosine",
    "wrist_to_torso_norm",
    "hand_wrist_to_body_wrist_norm",
    "body_confident_count",
    "torso_score_mean",
    "torso_score_min",
    "pose_extent_width_norm",
    "pose_extent_height_norm",
    "pose_area_norm",
    "person_body_plausible",
]
CAUSAL_FEATURES = BASE_FEATURES + [
    "previous_exists",
    "previous_dt_ms",
    "previous_hand_count_ge_030",
    "previous_hand_score_mean",
    "previous_body_wrist_score",
    "previous_arm_score_min",
    "previous_hand_wrist_to_body_wrist_norm",
    "hand_count_change",
    "hand_score_mean_change",
    "palm_displacement_norm",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def truth_value(raw: str) -> str:
    return {"yes": "VISIBLE", "no": "NOT_VISIBLE"}.get(raw, "UNKNOWN")


def parse_bool(raw: Any) -> bool:
    return str(raw).strip().lower() in {"true", "yes", "1"}


def body_scale(points: np.ndarray, width: int, height: int) -> float:
    shoulders = float(np.linalg.norm(points[5] - points[6]))
    torso = float(np.linalg.norm((points[5] + points[6]) / 2 - (points[11] + points[12]) / 2))
    return max(shoulders, torso, 0.1 * math.hypot(width, height), 1e-6)


def verify_p3() -> dict[str, str]:
    result = json.loads(P3_RESULT.read_text(encoding="utf-8"))
    if result["status"] != "P3_COMPLETE" or result["classification"] != "TEMPORALLY_USABLE":
        raise RuntimeError("Frozen P3 result identity changed")
    manifest = json.loads(P3_HASHES.read_text(encoding="utf-8"))["files"]
    wanted = {
        "p3_dwpose_temporal_result.json",
        "frozen_frame_manifest.csv",
        "frozen_sequence_manifest.csv",
        "p3_frozen_protocol.json",
        "frozen_inference_evaluator.py",
        "corrected_scoring_evaluator.py",
    }
    by_name = {row["path"].replace("\\", "/"): row for row in manifest}
    evidence = {}
    for name in sorted(wanted):
        if name not in by_name:
            raise RuntimeError(f"P3 hash manifest missing {name}")
        path = P3 / name
        actual = sha256(path)
        if actual != by_name[name]["sha256"]:
            raise RuntimeError(f"P3 artifact hash changed: {name}")
        evidence[name] = actual
    raw = sorted((P3 / "raw_outputs").glob("*.npz"))
    if len(raw) != 753:
        raise RuntimeError(f"Expected 753 P3 raw outputs, found {len(raw)}")
    raw_manifest = [row for name, row in by_name.items() if name.startswith("raw_outputs/")]
    if len(raw_manifest) != 753:
        raise RuntimeError("P3 raw-output hash manifest count changed")
    for row in raw_manifest:
        path = P3 / row["path"]
        if sha256(path) != row["sha256"]:
            raise RuntimeError(f"P3 raw output hash changed: {row['path']}")
    evidence["artifact_hash_manifest.json"] = sha256(P3_HASHES)
    return evidence


def sequence_summary(frames: list[dict[str, str]], meta: dict[str, str]) -> dict[str, Any]:
    return {
        "sequence_id": meta["sequence_id"],
        "signer_id": meta["signer_id"],
        "gloss": meta["gloss"],
        "expected_hands": meta["expected_hands"],
        "selection_bucket": meta["selection_bucket"],
        "frames": len(frames),
        "visible_slots": sum(row["human_visible_left"] == "yes" for row in frames)
        + sum(row["human_visible_right"] == "yes" for row in frames),
        "zero_frames": sum(
            row["human_visible_left"] == "no" and row["human_visible_right"] == "no"
            for row in frames
        ),
        "rest_frames": sum(row["human_no_hand_rest"] == "yes" for row in frames),
        "leaving_frames": sum(row["human_leaving_frame"] == "yes" for row in frames),
        "two_visible_frames": sum(
            row["human_visible_left"] == "yes" and row["human_visible_right"] == "yes"
            for row in frames
        ),
        "crossing_contact_frames": sum(
            row["human_crossing"] == "yes"
            or row["human_hand_hand_contact"] == "yes"
            or row["human_hand_body_contact"] == "yes"
            for row in frames
        ),
    }


def freeze_splits(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rng = np.random.default_rng(SPLIT_SEED)
    metrics = [
        "visible_slots",
        "zero_frames",
        "rest_frames",
        "leaving_frames",
        "two_visible_frames",
    ]
    totals = {name: sum(row[name] for row in summaries) for name in metrics}
    target_fraction = {"train": 11 / 21, "validation": 5 / 21, "holdout": 5 / 21}
    sister = next(i for i, row in enumerate(summaries) if row["gloss"] == "SISTER")
    best: tuple[float, tuple[int, ...]] | None = None
    indices = np.arange(len(summaries))
    for _ in range(SPLIT_SEARCH_TRIALS):
        permutation = tuple(int(value) for value in rng.permutation(indices))
        assignment = {
            "train": permutation[:11],
            "validation": permutation[11:16],
            "holdout": permutation[16:],
        }
        if sister not in assignment["holdout"]:
            continue
        valid = True
        for split, members in assignment.items():
            rows = [summaries[index] for index in members]
            if len({row["signer_id"] for row in rows}) != 2:
                valid = False
            if {row["expected_hands"] for row in rows} != {"one", "two"}:
                valid = False
            if split != "train" and not any(
                row["selection_bucket"] != "A1_SIGNING_SENTINEL" for row in rows
            ):
                valid = False
        if not valid:
            continue
        score = 0.0
        for split, members in assignment.items():
            rows = [summaries[index] for index in members]
            for name in metrics:
                observed = sum(row[name] for row in rows)
                target = totals[name] * target_fraction[split]
                score += ((observed - target) / max(target, 1.0)) ** 2
        encoded = tuple(
            0 if i in assignment["train"] else 1 if i in assignment["validation"] else 2
            for i in indices
        )
        candidate = (score, encoded)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        raise RuntimeError("Unable to construct governed sequence split")
    labels = {0: "train", 1: "validation", 2: "holdout"}
    rows = []
    for summary, code in zip(summaries, best[1], strict=True):
        rows.append({**summary, "split": labels[code], "split_seed": SPLIT_SEED})
    if Counter(row["split"] for row in rows) != Counter(SPLIT_SIZES):
        raise RuntimeError("Frozen split sizes changed")
    return rows


def derive_slot_features(
    keypoints: np.ndarray,
    scores: np.ndarray,
    side: str,
    width: int,
    height: int,
) -> tuple[dict[str, float], np.ndarray]:
    section = LEFT_SLICE if side == "left" else RIGHT_SLICE
    shoulder_i, elbow_i, wrist_i = (5, 7, 9) if side == "left" else (6, 8, 10)
    hand = keypoints[section]
    hand_scores = scores[section]
    scale = body_scale(keypoints, width, height)
    shoulder, elbow, body_wrist = keypoints[[shoulder_i, elbow_i, wrist_i]]
    arm_a = elbow - shoulder
    arm_b = body_wrist - elbow
    se = float(np.linalg.norm(arm_a) / scale)
    ew = float(np.linalg.norm(arm_b) / scale)
    angle = float(np.dot(arm_a, arm_b) / max(np.linalg.norm(arm_a) * np.linalg.norm(arm_b), 1e-8))
    torso = (keypoints[5] + keypoints[6] + keypoints[11] + keypoints[12]) / 4
    extents = np.ptp(hand, axis=0) / scale
    bones = np.linalg.norm(hand[BONES[:, 0]] - hand[BONES[:, 1]], axis=1) / scale
    palm = hand[PALM].mean(axis=0)
    palm_points = hand[PALM]
    palm_spread = (
        max(np.linalg.norm(a - b) for i, a in enumerate(palm_points) for b in palm_points[i + 1 :])
        / scale
    )
    body_scores = scores[:23]
    torso_scores = scores[[5, 6, 11, 12]]
    pose_extent = np.ptp(keypoints[:23], axis=0) / scale
    arm_scores = scores[[shoulder_i, elbow_i, wrist_i]]
    values = {
        "hand_count_ge_030": float(np.count_nonzero(hand_scores >= JOINT_THRESHOLD)),
        "hand_score_min": float(np.min(hand_scores)),
        "hand_score_mean": float(np.mean(hand_scores)),
        "hand_score_median": float(np.median(hand_scores)),
        "hand_score_max": float(np.max(hand_scores)),
        "hand_wrist_score": float(hand_scores[0]),
        "mcp_score_mean": float(np.mean(hand_scores[MCP])),
        "mcp_score_min": float(np.min(hand_scores[MCP])),
        "tip_score_mean": float(np.mean(hand_scores[TIPS])),
        "tip_score_min": float(np.min(hand_scores[TIPS])),
        "hand_extent_width_norm": float(extents[0]),
        "hand_extent_height_norm": float(extents[1]),
        "hand_area_norm": float(extents[0] * extents[1]),
        "palm_spread_norm": float(palm_spread),
        "median_bone_norm": float(np.median(bones)),
        "bone_cv": float(np.std(bones) / max(np.mean(bones), 1e-8)),
        "shoulder_score": float(scores[shoulder_i]),
        "elbow_score": float(scores[elbow_i]),
        "body_wrist_score": float(scores[wrist_i]),
        "arm_score_min": float(np.min(arm_scores)),
        "arm_score_mean": float(np.mean(arm_scores)),
        "shoulder_elbow_norm": se,
        "elbow_wrist_norm": ew,
        "arm_length_ratio": ew / max(se, 1e-8),
        "arm_angle_cosine": angle,
        "wrist_to_torso_norm": float(np.linalg.norm(body_wrist - torso) / scale),
        "hand_wrist_to_body_wrist_norm": float(np.linalg.norm(hand[0] - body_wrist) / scale),
        "body_confident_count": float(np.count_nonzero(body_scores >= JOINT_THRESHOLD)),
        "torso_score_mean": float(np.mean(torso_scores)),
        "torso_score_min": float(np.min(torso_scores)),
        "pose_extent_width_norm": float(pose_extent[0]),
        "pose_extent_height_norm": float(pose_extent[1]),
        "pose_area_norm": float(pose_extent[0] * pose_extent[1]),
        "person_body_plausible": float(
            np.count_nonzero(body_scores >= JOINT_THRESHOLD) >= 8
            and np.mean(torso_scores) >= JOINT_THRESHOLD
        ),
    }
    return values, palm / scale


def prepare() -> dict[str, Any]:
    p3_hashes = verify_p3()
    frames = [row for row in read_csv(P3_FRAMES) if row["cohort"] == "A2_REVIEWED_PHONE"]
    sequences = [row for row in read_csv(P3_SEQUENCES) if row["cohort"] == "A2_REVIEWED_PHONE"]
    if len(frames) != 551 or len(sequences) != 21:
        raise RuntimeError("Governed A2 temporal evidence counts changed")
    by_sequence: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in frames:
        by_sequence[row["sequence_id"]].append(row)
    summaries = [sequence_summary(by_sequence[row["sequence_id"]], row) for row in sequences]
    split_rows = freeze_splits(summaries)
    split_lookup = {row["sequence_id"]: row["split"] for row in split_rows}
    meta_lookup = {row["sequence_id"]: row for row in sequences}

    truth_rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    palm_lookup: dict[tuple[str, str], np.ndarray] = {}
    for frame in frames:
        raw = np.load(P3 / "raw_outputs" / f"{frame['manifest_row_id']}.npz")
        keypoints = np.asarray(raw["keypoints_133"], dtype=np.float64)
        scores = np.asarray(raw["scores_133"], dtype=np.float64)
        if keypoints.shape != (133, 2) or scores.shape != (133,):
            raise RuntimeError(f"Invalid frozen native output: {frame['manifest_row_id']}")
        meta = meta_lookup[frame["sequence_id"]]
        for side in ("left", "right"):
            row_id = f"{frame['manifest_row_id']}__{side}"
            label = truth_value(frame[f"human_visible_{side}"])
            truth_rows.append(
                {
                    "eligibility_row_id": row_id,
                    "manifest_row_id": frame["manifest_row_id"],
                    "sequence_id": frame["sequence_id"],
                    "split": split_lookup[frame["sequence_id"]],
                    "source_frame_id": frame["source_frame_id"],
                    "timestamp_ns": frame["timestamp_ns"],
                    "anatomical_side": side,
                    "truth": label,
                    "human_visible_raw": frame[f"human_visible_{side}"],
                    "zero_visible_hands_frame": frame["human_visible_left"] == "no"
                    and frame["human_visible_right"] == "no",
                    "no_hand_rest": frame["human_no_hand_rest"],
                    "leaving_frame": frame["human_leaving_frame"],
                    "crossing": frame["human_crossing"],
                    "hand_hand_contact": frame["human_hand_hand_contact"],
                    "hand_body_contact": frame["human_hand_body_contact"],
                    "expected_hands": meta["expected_hands"],
                    "gloss": meta["gloss"],
                    "signer_id": meta["signer_id"],
                    "historical_blur_or_occlusion": meta["selection_bucket"]
                    == "TWO_HAND_OCCLUSION_OR_CONTACT"
                    or meta["source_sequence_id"] == "20260816021321308_WE",
                    "historical_condition_basis": meta["selection_bucket"],
                }
            )
            values, palm = derive_slot_features(
                keypoints, scores, side, int(frame["width"]), int(frame["height"])
            )
            feature_rows.append(
                {
                    "eligibility_row_id": row_id,
                    "manifest_row_id": frame["manifest_row_id"],
                    "sequence_id": frame["sequence_id"],
                    "split": split_lookup[frame["sequence_id"]],
                    "source_frame_id": frame["source_frame_id"],
                    "timestamp_ns": frame["timestamp_ns"],
                    "anatomical_side": side,
                    "baseline_present": values["hand_count_ge_030"] >= MIN_JOINTS,
                    **values,
                    "palm_x_norm": float(palm[0]),
                    "palm_y_norm": float(palm[1]),
                }
            )
            palm_lookup[(frame["manifest_row_id"], side)] = palm

    feature_by_sequence_side: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in feature_rows:
        feature_by_sequence_side[(row["sequence_id"], row["anatomical_side"])].append(row)
    for rows in feature_by_sequence_side.values():
        rows.sort(key=lambda row: int(row["timestamp_ns"]))
        previous = None
        for row in rows:
            dt_ms = (
                None
                if previous is None
                else (int(row["timestamp_ns"]) - int(previous["timestamp_ns"])) / 1e6
            )
            exists = previous is not None and 0 < dt_ms <= 500
            row.update(
                {
                    "previous_exists": float(exists),
                    "previous_dt_ms": float(dt_ms if exists else 0.0),
                    "previous_hand_count_ge_030": float(
                        previous["hand_count_ge_030"] if exists else 0.0
                    ),
                    "previous_hand_score_mean": float(
                        previous["hand_score_mean"] if exists else 0.0
                    ),
                    "previous_body_wrist_score": float(
                        previous["body_wrist_score"] if exists else 0.0
                    ),
                    "previous_arm_score_min": float(previous["arm_score_min"] if exists else 0.0),
                    "previous_hand_wrist_to_body_wrist_norm": float(
                        previous["hand_wrist_to_body_wrist_norm"] if exists else 0.0
                    ),
                    "hand_count_change": float(
                        row["hand_count_ge_030"] - previous["hand_count_ge_030"] if exists else 0.0
                    ),
                    "hand_score_mean_change": float(
                        row["hand_score_mean"] - previous["hand_score_mean"] if exists else 0.0
                    ),
                    "palm_displacement_norm": float(
                        np.linalg.norm(
                            np.asarray([row["palm_x_norm"], row["palm_y_norm"]])
                            - np.asarray([previous["palm_x_norm"], previous["palm_y_norm"]])
                        )
                        if exists
                        else 0.0
                    ),
                }
            )
            previous = row

    counts = Counter(row["truth"] for row in truth_rows)
    if counts != Counter({"NOT_VISIBLE": 753, "VISIBLE": 323, "UNKNOWN": 26}):
        raise RuntimeError(f"Eligibility truth counts changed: {counts}")
    write_csv(OUTPUT / "p4a_eligibility_truth.csv", truth_rows)
    write_csv(OUTPUT / "p4a_split_manifest.csv", split_rows)
    write_csv(OUTPUT / "p4a_derived_features.csv", feature_rows)
    feature_manifest = {
        "baseline": "hand_count_ge_030 >= 11",
        "single_frame_features": BASE_FEATURES,
        "conditional_causal_features": CAUSAL_FEATURES,
        "logical_rule": {
            "all": [
                "hand_count_ge_030 >= 11",
                "arm_score_min >= 0.30",
                "hand_wrist_to_body_wrist_norm <= 0.30",
                "0.35 <= arm_length_ratio <= 2.85",
                "0.0005 <= hand_area_norm <= 1.0",
                "person_body_plausible == 1",
            ]
        },
        "logistic": {
            "implementation": "fixed NumPy Newton/IRLS L2 logistic regression",
            "class_weight": "balanced from training rows only",
            "l2": 1.0,
            "threshold": 0.5,
            "max_iterations": 100,
            "tolerance": 1e-8,
        },
        "causal_activation": "activate only if neither logical nor single-frame logistic passes validation and the best has visible recall >=0.95 with zero/rest FPR >0.10",
        "no_future_frames": True,
    }
    write_json(OUTPUT / "p4a_feature_manifest.json", feature_manifest)
    protocol = {
        "identity": "P4A_DWPOSE_PRESENCE_ELIGIBILITY",
        "p3_hashes": p3_hashes,
        "evaluator_sha256": sha256(EVALUATOR),
        "split_seed": SPLIT_SEED,
        "split_search_trials": SPLIT_SEARCH_TRIALS,
        "split_sizes": SPLIT_SIZES,
        "truth_counts": dict(counts),
        "frozen_gates": {
            "visible_recall_min": 0.98,
            "zero_hand_frame_fpr_max": 0.10,
            "rest_frame_fpr_max": 0.10,
            "complete_two_hand_retention_min": 0.95,
            "full_visible_misses_max": 6,
            "clear_improvement": "zero-hand FPR reduction >=0.10 absolute and visible recall >=0.95",
        },
        "candidate_families": [
            "E1_FIXED_ANATOMICAL_LOGICAL_RULE",
            "E2_FIXED_L2_LOGISTIC_SINGLE_FRAME",
            "E3_FIXED_L2_LOGISTIC_CAUSAL_CONDITIONAL",
        ],
        "selection_rule": "validation only: pass all gates first, then gate count, visible recall, lower zero/rest FPR, higher two-hand retention, lexical candidate id",
        "holdout_policy": "one execution after selected artifact is frozen; no threshold/hyperparameter/feature changes",
        "truth_sha256": sha256(OUTPUT / "p4a_eligibility_truth.csv"),
        "split_sha256": sha256(OUTPUT / "p4a_split_manifest.csv"),
        "features_sha256": sha256(OUTPUT / "p4a_derived_features.csv"),
        "feature_manifest_sha256": sha256(OUTPUT / "p4a_feature_manifest.json"),
    }
    write_json(OUTPUT / "p4a_frozen_protocol.json", protocol)
    return protocol


def verify_prepared() -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    protocol = json.loads((OUTPUT / "p4a_frozen_protocol.json").read_text(encoding="utf-8"))
    checks = {
        "p4a_eligibility_truth.csv": "truth_sha256",
        "p4a_split_manifest.csv": "split_sha256",
        "p4a_derived_features.csv": "features_sha256",
        "p4a_feature_manifest.json": "feature_manifest_sha256",
    }
    if sha256(EVALUATOR) != protocol["evaluator_sha256"]:
        raise RuntimeError("Frozen P4-A evaluator changed")
    for name, field in checks.items():
        if sha256(OUTPUT / name) != protocol[field]:
            raise RuntimeError(f"Frozen P4-A artifact changed: {name}")
    return (
        read_csv(OUTPUT / "p4a_eligibility_truth.csv"),
        read_csv(OUTPUT / "p4a_derived_features.csv"),
        protocol,
    )


def join_rows(truth: list[dict[str, str]], features: list[dict[str, str]]) -> list[dict[str, Any]]:
    feature_lookup = {row["eligibility_row_id"]: row for row in features}
    return [{**row, **feature_lookup[row["eligibility_row_id"]]} for row in truth]


def fit_logistic(rows: list[dict[str, Any]], names: list[str]) -> dict[str, Any]:
    usable = [row for row in rows if row["truth"] != "UNKNOWN"]
    x = np.asarray([[float(row[name]) for name in names] for row in usable], dtype=np.float64)
    y = np.asarray([row["truth"] == "VISIBLE" for row in usable], dtype=np.float64)
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale < 1e-8] = 1.0
    z = (x - mean) / scale
    design = np.column_stack([np.ones(len(z)), z])
    positive = max(float(y.sum()), 1.0)
    negative = max(float((1 - y).sum()), 1.0)
    weights = np.where(y == 1, len(y) / (2 * positive), len(y) / (2 * negative))
    coefficients = np.zeros(design.shape[1], dtype=np.float64)
    regularizer = np.eye(design.shape[1], dtype=np.float64)
    regularizer[0, 0] = 0.0
    iterations = 0
    for step_index in range(1, 101):
        iterations = step_index
        logits = np.clip(design @ coefficients, -40, 40)
        probability = 1 / (1 + np.exp(-logits))
        gradient = design.T @ (weights * (probability - y)) + regularizer @ coefficients
        curvature = weights * probability * (1 - probability)
        hessian = design.T @ (curvature[:, None] * design) + regularizer
        hessian += np.eye(hessian.shape[0]) * 1e-9
        step = np.linalg.solve(hessian, gradient)
        coefficients -= step
        if float(np.max(np.abs(step))) < 1e-8:
            break
    return {
        "type": "logistic",
        "features": names,
        "mean": mean.tolist(),
        "scale": scale.tolist(),
        "coefficients": coefficients.tolist(),
        "threshold": 0.5,
        "iterations": iterations,
        "training_rows": len(usable),
    }


def predict_model(
    model: dict[str, Any], rows: list[dict[str, Any]]
) -> tuple[list[bool], list[float]]:
    if model["type"] == "logical":
        predictions = [logical_prediction(row) for row in rows]
        return predictions, [float(value) for value in predictions]
    names = model["features"]
    x = np.asarray([[float(row[name]) for name in names] for row in rows], dtype=np.float64)
    z = (x - np.asarray(model["mean"])) / np.asarray(model["scale"])
    logits = np.column_stack([np.ones(len(z)), z]) @ np.asarray(model["coefficients"])
    probability = 1 / (1 + np.exp(-np.clip(logits, -40, 40)))
    return list(probability >= model["threshold"]), probability.tolist()


def logical_prediction(row: dict[str, Any]) -> bool:
    return bool(
        float(row["hand_count_ge_030"]) >= 11
        and float(row["arm_score_min"]) >= 0.30
        and float(row["hand_wrist_to_body_wrist_norm"]) <= 0.30
        and 0.35 <= float(row["arm_length_ratio"]) <= 2.85
        and 0.0005 <= float(row["hand_area_norm"]) <= 1.0
        and parse_bool(row["person_body_plausible"])
    )


def metric_bundle(rows: list[dict[str, Any]], predictions: list[bool]) -> dict[str, Any]:
    records = [
        (row, bool(pred))
        for row, pred in zip(rows, predictions, strict=True)
        if row["truth"] != "UNKNOWN"
    ]
    tp = sum(row["truth"] == "VISIBLE" and pred for row, pred in records)
    fn = sum(row["truth"] == "VISIBLE" and not pred for row, pred in records)
    fp = sum(row["truth"] == "NOT_VISIBLE" and pred for row, pred in records)
    tn = sum(row["truth"] == "NOT_VISIBLE" and not pred for row, pred in records)

    def ratio(a: int, b: int) -> float | None:
        return a / b if b else None

    by_frame: dict[str, list[tuple[dict[str, Any], bool]]] = defaultdict(list)
    for record in records:
        by_frame[record[0]["manifest_row_id"]].append(record)
    zero = [
        values
        for values in by_frame.values()
        if len(values) == 2 and all(row["truth"] == "NOT_VISIBLE" for row, _ in values)
    ]
    rest = [values for values in zero if values[0][0]["no_hand_rest"] == "yes"]
    leaving = [values for values in by_frame.values() if values[0][0]["leaving_frame"] == "yes"]
    two = [
        values
        for values in by_frame.values()
        if len(values) == 2 and all(row["truth"] == "VISIBLE" for row, _ in values)
    ]
    zero_fp = sum(any(pred for _, pred in values) for values in zero)
    rest_fp = sum(any(pred for _, pred in values) for values in rest)
    return {
        "confusion": {"tp": tp, "fn": fn, "fp": fp, "tn": tn},
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "specificity": ratio(tn, tn + fp),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
        "false_positive_rate": ratio(fp, fp + tn),
        "false_negative_rate": ratio(fn, fn + tp),
        "zero_hand_frame_false_presence": {
            "numerator": zero_fp,
            "denominator": len(zero),
            "rate": ratio(zero_fp, len(zero)),
        },
        "rest_frame_false_presence": {
            "numerator": rest_fp,
            "denominator": len(rest),
            "rate": ratio(rest_fp, len(rest)),
        },
        "complete_two_hand_retention": {
            "numerator": sum(all(pred for _, pred in values) for values in two),
            "denominator": len(two),
            "rate": ratio(sum(all(pred for _, pred in values) for values in two), len(two)),
        },
        "leaving_frame_any_prediction": {
            "numerator": sum(any(pred for _, pred in values) for values in leaving),
            "denominator": len(leaving),
            "rate": ratio(sum(any(pred for _, pred in values) for values in leaving), len(leaving)),
        },
        "subgroups": {
            name: subgroup_metrics(records, predicate)
            for name, predicate in {
                "historical_blur_or_occlusion": lambda row: parse_bool(
                    row["historical_blur_or_occlusion"]
                ),
                "one_hand_sequences": lambda row: row["expected_hands"] == "one",
                "two_hand_sequences": lambda row: row["expected_hands"] == "two",
                "crossing_or_contact": lambda row: (
                    row["crossing"] == "yes"
                    or row["hand_hand_contact"] == "yes"
                    or row["hand_body_contact"] == "yes"
                ),
            }.items()
        },
    }


def subgroup_metrics(records: list[tuple[dict[str, Any], bool]], predicate: Any) -> dict[str, Any]:
    subset = [(row, pred) for row, pred in records if predicate(row)]
    visible = sum(row["truth"] == "VISIBLE" for row, _ in subset)
    visible_hits = sum(row["truth"] == "VISIBLE" and pred for row, pred in subset)
    not_visible = sum(row["truth"] == "NOT_VISIBLE" for row, _ in subset)
    false_positive = sum(row["truth"] == "NOT_VISIBLE" and pred for row, pred in subset)
    return {
        "rows": len(subset),
        "visible_recall": visible_hits / visible if visible else None,
        "false_positive_rate": false_positive / not_visible if not_visible else None,
    }


def gates(metrics: dict[str, Any]) -> dict[str, bool]:
    return {
        "visible_recall": metrics["recall"] is not None and metrics["recall"] >= 0.98,
        "zero_hand_fpr": metrics["zero_hand_frame_false_presence"]["rate"] is not None
        and metrics["zero_hand_frame_false_presence"]["rate"] <= 0.10,
        "rest_fpr": metrics["rest_frame_false_presence"]["rate"] is not None
        and metrics["rest_frame_false_presence"]["rate"] <= 0.10,
        "complete_two_hand": metrics["complete_two_hand_retention"]["rate"] is not None
        and metrics["complete_two_hand_retention"]["rate"] >= 0.95,
    }


def candidate_row(
    candidate: str, metrics: dict[str, Any], activated: bool = True
) -> dict[str, Any]:
    gate_values = (
        gates(metrics)
        if activated
        else {
            name: False
            for name in ("visible_recall", "zero_hand_fpr", "rest_fpr", "complete_two_hand")
        }
    )
    return {
        "candidate": candidate,
        "activated": activated,
        "validation_visible_recall": metrics.get("recall") if activated else None,
        "validation_precision": metrics.get("precision") if activated else None,
        "validation_zero_hand_fpr": metrics.get("zero_hand_frame_false_presence", {}).get("rate")
        if activated
        else None,
        "validation_rest_fpr": metrics.get("rest_frame_false_presence", {}).get("rate")
        if activated
        else None,
        "validation_complete_two_hand": metrics.get("complete_two_hand_retention", {}).get("rate")
        if activated
        else None,
        **{f"gate_{key}": value for key, value in gate_values.items()},
        "gate_count": sum(gate_values.values()),
        "all_gates": all(gate_values.values()),
    }


def select() -> dict[str, Any]:
    truth, features, protocol = verify_prepared()
    if (OUTPUT / "p4a_selection_freeze.json").exists():
        raise RuntimeError("P4-A selection already frozen")
    rows = join_rows(truth, features)
    train = [row for row in rows if row["split"] == "train"]
    validation = [row for row in rows if row["split"] == "validation"]
    baseline_train = metric_bundle(train, [parse_bool(row["baseline_present"]) for row in train])
    baseline_validation = metric_bundle(
        validation, [parse_bool(row["baseline_present"]) for row in validation]
    )
    write_json(
        OUTPUT / "p4a_baseline_results.json",
        {"train": baseline_train, "validation": baseline_validation, "holdout": "SEALED"},
    )
    models: dict[str, dict[str, Any]] = {
        "E1_FIXED_ANATOMICAL_LOGICAL_RULE": {"type": "logical"},
        "E2_FIXED_L2_LOGISTIC_SINGLE_FRAME": fit_logistic(train, BASE_FEATURES),
    }
    comparison = []
    validation_metrics: dict[str, dict[str, Any]] = {}
    for name, model in models.items():
        prediction, _ = predict_model(model, validation)
        validation_metrics[name] = metric_bundle(validation, prediction)
        comparison.append(candidate_row(name, validation_metrics[name]))
    best_first_two = max(
        validation_metrics,
        key=lambda name: (
            validation_metrics[name]["recall"] or 0.0,
            -(
                1.0
                if validation_metrics[name]["zero_hand_frame_false_presence"]["rate"] is None
                else validation_metrics[name]["zero_hand_frame_false_presence"]["rate"]
            ),
        ),
    )
    best_metrics = validation_metrics[best_first_two]
    activate_e3 = (
        not any(row["all_gates"] for row in comparison)
        and (best_metrics["recall"] or 0.0) >= 0.95
        and (
            (best_metrics["zero_hand_frame_false_presence"]["rate"] or 0.0) > 0.10
            or (best_metrics["rest_frame_false_presence"]["rate"] or 0.0) > 0.10
        )
    )
    if activate_e3:
        model = fit_logistic(train, CAUSAL_FEATURES)
        models["E3_FIXED_L2_LOGISTIC_CAUSAL"] = model
        prediction, _ = predict_model(model, validation)
        validation_metrics["E3_FIXED_L2_LOGISTIC_CAUSAL"] = metric_bundle(validation, prediction)
        comparison.append(
            candidate_row(
                "E3_FIXED_L2_LOGISTIC_CAUSAL",
                validation_metrics["E3_FIXED_L2_LOGISTIC_CAUSAL"],
            )
        )
    else:
        comparison.append(candidate_row("E3_FIXED_L2_LOGISTIC_CAUSAL", {}, activated=False))

    active = [row for row in comparison if row["activated"]]
    active.sort(
        key=lambda row: (
            not parse_bool(row["all_gates"]),
            -int(row["gate_count"]),
            -float(row["validation_visible_recall"] or 0.0),
            float(
                1.0 if row["validation_zero_hand_fpr"] is None else row["validation_zero_hand_fpr"]
            ),
            float(1.0 if row["validation_rest_fpr"] is None else row["validation_rest_fpr"]),
            -float(row["validation_complete_two_hand"] or 0.0),
            row["candidate"],
        )
    )
    selected = active[0]["candidate"]
    final_training = [row for row in rows if row["split"] in {"train", "validation"}]
    if models[selected]["type"] == "logistic":
        final_model = fit_logistic(final_training, models[selected]["features"])
    else:
        final_model = models[selected]
    model_artifact = {
        "candidate": selected,
        "model": final_model,
        "training_splits": ["train", "validation"],
        "threshold_tuned": False,
        "holdout_accessed": False,
    }
    write_json(OUTPUT / "p4a_selected_model.json", model_artifact)
    write_csv(OUTPUT / "p4a_candidate_comparison.csv", comparison)
    selection = {
        "selected_candidate": selected,
        "e3_activated": activate_e3,
        "candidate_comparison_sha256": sha256(OUTPUT / "p4a_candidate_comparison.csv"),
        "selected_model_sha256": sha256(OUTPUT / "p4a_selected_model.json"),
        "holdout_evaluated": False,
        "protocol_sha256": sha256(OUTPUT / "p4a_frozen_protocol.json"),
        "evaluator_sha256": protocol["evaluator_sha256"],
    }
    write_json(OUTPUT / "p4a_selection_freeze.json", selection)
    return selection


def holdout() -> dict[str, Any]:
    truth, features, protocol = verify_prepared()
    if (OUTPUT / "p4a_dwpose_eligibility_result.json").exists():
        raise RuntimeError("P4-A holdout has already been evaluated")
    selection = json.loads((OUTPUT / "p4a_selection_freeze.json").read_text(encoding="utf-8"))
    if selection["holdout_evaluated"]:
        raise RuntimeError("P4-A holdout flag is already set")
    if sha256(OUTPUT / "p4a_selected_model.json") != selection["selected_model_sha256"]:
        raise RuntimeError("Selected P4-A model artifact changed")
    rows = join_rows(truth, features)
    holdout_rows = [row for row in rows if row["split"] == "holdout"]
    model_artifact = json.loads((OUTPUT / "p4a_selected_model.json").read_text(encoding="utf-8"))
    holdout_prediction, holdout_probability = predict_model(model_artifact["model"], holdout_rows)
    holdout_metrics = metric_bundle(holdout_rows, holdout_prediction)
    holdout_gates = gates(holdout_metrics)

    all_prediction, all_probability = predict_model(model_artifact["model"], rows)
    all_metrics = metric_bundle(rows, all_prediction)
    full_count_gates = {
        "visible_misses_max_6": all_metrics["confusion"]["fn"] <= 6,
        "zero_hand_fpr": all_metrics["zero_hand_frame_false_presence"]["rate"] <= 0.10,
        "rest_fpr": all_metrics["rest_frame_false_presence"]["rate"] <= 0.10,
        "complete_two_hand": all_metrics["complete_two_hand_retention"]["rate"] >= 0.95,
    }
    baseline_holdout = metric_bundle(
        holdout_rows, [parse_bool(row["baseline_present"]) for row in holdout_rows]
    )
    baseline_all = metric_bundle(rows, [parse_bool(row["baseline_present"]) for row in rows])
    baseline = json.loads((OUTPUT / "p4a_baseline_results.json").read_text(encoding="utf-8"))
    baseline.update({"holdout": baseline_holdout, "all_governed": baseline_all})
    write_json(OUTPUT / "p4a_baseline_results.json", baseline)

    prediction_rows = []
    for row, prediction, probability in zip(
        holdout_rows, holdout_prediction, holdout_probability, strict=True
    ):
        prediction_rows.append(
            {
                "eligibility_row_id": row["eligibility_row_id"],
                "manifest_row_id": row["manifest_row_id"],
                "sequence_id": row["sequence_id"],
                "source_frame_id": row["source_frame_id"],
                "anatomical_side": row["anatomical_side"],
                "truth": row["truth"],
                "prediction_eligible": prediction,
                "probability": probability,
                "baseline_present": row["baseline_present"],
                "zero_visible_hands_frame": row["zero_visible_hands_frame"],
                "no_hand_rest": row["no_hand_rest"],
                "leaving_frame": row["leaving_frame"],
                "crossing": row["crossing"],
                "hand_body_contact": row["hand_body_contact"],
                "historical_blur_or_occlusion": row["historical_blur_or_occlusion"],
                **{name: row[name] for name in BASE_FEATURES},
            }
        )
    write_csv(OUTPUT / "p4a_holdout_predictions.csv", prediction_rows)

    all_cases = []
    for row, prediction, probability in zip(rows, all_prediction, all_probability, strict=True):
        all_cases.append({**row, "prediction_eligible": prediction, "probability": probability})
    false_positive = [
        row
        for row in all_cases
        if row["truth"] == "NOT_VISIBLE" and parse_bool(row["prediction_eligible"])
    ]
    false_negative = [
        row
        for row in all_cases
        if row["truth"] == "VISIBLE" and not parse_bool(row["prediction_eligible"])
    ]
    special = [
        row
        for row in all_cases
        if row["leaving_frame"] == "yes"
        or row["crossing"] == "yes"
        or row["hand_hand_contact"] == "yes"
        or row["hand_body_contact"] == "yes"
        or (row["expected_hands"] == "two" and row["truth"] == "VISIBLE")
    ]
    write_csv(OUTPUT / "p4a_false_positive_cases.csv", false_positive)
    write_csv(OUTPUT / "p4a_false_negative_cases.csv", false_negative)
    write_csv(OUTPUT / "p4a_special_subgroup_cases.csv", special)

    all_holdout_pass = all(holdout_gates.values())
    all_full_pass = all(full_count_gates.values())
    baseline_zero = baseline_holdout["zero_hand_frame_false_presence"]["rate"] or 0.0
    candidate_zero = holdout_metrics["zero_hand_frame_false_presence"]["rate"] or 0.0
    clear_improvement = (
        baseline_zero - candidate_zero >= 0.10 and (holdout_metrics["recall"] or 0.0) >= 0.95
    )
    if all_holdout_pass and all_full_pass:
        classification = "ELIGIBILITY_SIGNAL_VALIDATED"
    elif clear_improvement:
        classification = "ELIGIBILITY_IMPROVED_BUT_GATES_FAILED"
    else:
        classification = "BOUNDED_ELIGIBILITY_APPROACH_NOT_SEPARABLE"
    result = {
        "status": "P4A_COMPLETE",
        "classification": classification,
        "selected_candidate": selection["selected_candidate"],
        "eligibility_truth_rows": len(rows),
        "scoreable_truth_rows": sum(row["truth"] != "UNKNOWN" for row in rows),
        "split_sequence_counts": dict(
            Counter(row["split"] for row in read_csv(OUTPUT / "p4a_split_manifest.csv"))
        ),
        "baseline_holdout": baseline_holdout,
        "selected_holdout": holdout_metrics,
        "selected_all_governed": all_metrics,
        "holdout_gates": holdout_gates,
        "full_governed_gates": full_count_gates,
        "all_gates_passed": all_holdout_pass and all_full_pass,
        "holdout_executions": 1,
        "no_model_inference_rerun": True,
        "no_threshold_sweep": True,
    }
    write_json(OUTPUT / "p4a_dwpose_eligibility_result.json", result)
    write_report(result)
    selection["holdout_evaluated"] = True
    selection["holdout_predictions_sha256"] = sha256(OUTPUT / "p4a_holdout_predictions.csv")
    write_json(OUTPUT / "p4a_selection_freeze.json", selection)
    create_hash_manifest()
    return result


def format_rate(metric: dict[str, Any]) -> str:
    rate = metric["rate"]
    return (
        f"{metric['numerator']}/{metric['denominator']} = {100 * rate:.3f}%"
        if rate is not None
        else "N/A"
    )


def write_report(result: dict[str, Any]) -> None:
    baseline = result["baseline_holdout"]
    selected = result["selected_holdout"]
    all_rows = result["selected_all_governed"]
    comparison = read_csv(OUTPUT / "p4a_candidate_comparison.csv")
    split_rows = read_csv(OUTPUT / "p4a_split_manifest.csv")
    split_summary = Counter(row["split"] for row in split_rows)
    report = f"""# P4-A DWPose Presence Eligibility Result

Status: `P4A_COMPLETE`  
Classification: `{result["classification"]}`  
Selected candidate: `{result["selected_candidate"]}`

## Evidence and frozen split

P4-A reused the 753 immutable P3 native outputs and no DWPose inference was rerun. Eligibility
truth is physical anatomical-hand visibility from the 551 governed A2 frames: 1,102 slot rows,
comprising 323 `VISIBLE`, 753 `NOT_VISIBLE`, and 26 `UNKNOWN`. Unknown rows were retained but not
scored. All frames from an attempt stay together. Frozen sequence counts are train
{split_summary["train"]}, validation {split_summary["validation"]}, and holdout
{split_summary["holdout"]}; the only directly reviewed crossing/contact sequence is in holdout.

No human landmark coordinates exist. Blur/occlusion is only a historical sequence-level tag where
available, not newly created frame truth.

## Frozen baseline on final holdout

The unchanged baseline is score >=0.30 on at least 11/21 hand joints.

- per-hand precision: {baseline["precision"]:.4f}; recall: {baseline["recall"]:.4f};
  specificity: {baseline["specificity"]:.4f}; F1: {baseline["f1"]:.4f};
- zero-hand frame false presence: {format_rate(baseline["zero_hand_frame_false_presence"])};
- rest-frame false presence: {format_rate(baseline["rest_frame_false_presence"])};
- complete two-visible-hand retention: {format_rate(baseline["complete_two_hand_retention"])}.

## Candidate families and selection

Exactly three families were preregistered: a fixed anatomical logical rule, fixed L2 single-frame
logistic regression, and a conditional fixed L2 causal logistic model. The conditional family was
only activated under the frozen validation rule. No score/joint-count threshold sweep, RGB,
future frame, neural network, feature addition after holdout, or holdout selection occurred.

Validation comparison is stored in `p4a_candidate_comparison.csv` ({len(comparison)} rows).

## Selected candidate: final holdout

- per-hand precision: {selected["precision"]:.4f}; recall: {selected["recall"]:.4f};
  specificity: {selected["specificity"]:.4f}; F1: {selected["f1"]:.4f};
- confusion: {selected["confusion"]};
- zero-hand false presence: {format_rate(selected["zero_hand_frame_false_presence"])};
- explicit-rest false presence: {format_rate(selected["rest_frame_false_presence"])};
- complete two-hand retention: {format_rate(selected["complete_two_hand_retention"])};
- leaving-frame any prediction: {format_rate(selected["leaving_frame_any_prediction"])}.

Holdout gates: {result["holdout_gates"]}. Full-governed count gates: {result["full_governed_gates"]}.
All gates passed: **{result["all_gates_passed"]}**.

## Full governed diagnostic

After the one-time holdout execution, the frozen candidate was also summarized across all governed
rows. Visible recall is {all_rows["recall"]:.4f}; zero-hand false presence is
{format_rate(all_rows["zero_hand_frame_false_presence"])}; rest false presence is
{format_rate(all_rows["rest_frame_false_presence"])}; complete two-hand retention is
{format_rate(all_rows["complete_two_hand_retention"])}. Training/validation rows in this diagnostic
are not independent holdout evidence.

## Subgroups and cases

Holdout subgroup results: `{json.dumps(selected["subgroups"], sort_keys=True)}`.
False-positive, false-negative, leaving/crossing/contact, and two-hand case tables retain the
relevant native scores and geometry. A visible hand at rest remains positive truth; P4-A does not
classify signing state.

## Decision

**`{result["classification"]}`**

This phase changes no production feature representation, does not fabricate z, does not retrain
S6, and does not modify Android or S4-S7. P4-B was not started.
"""
    (OUTPUT / "P4A_DWPOSE_PRESENCE_ELIGIBILITY_RESULT.md").write_text(report, encoding="utf-8")


def create_hash_manifest() -> None:
    paths = sorted(
        path
        for path in OUTPUT.rglob("*")
        if path.is_file() and path.name != "provenance_hash_manifest.json"
    )
    write_json(
        OUTPUT / "provenance_hash_manifest.json",
        {
            "files": [
                {
                    "path": str(path.relative_to(OUTPUT)),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
                for path in paths
            ]
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "select", "holdout"))
    args = parser.parse_args()
    action = {"prepare": prepare, "select": select, "holdout": holdout}[args.command]
    print(json.dumps(action(), indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
