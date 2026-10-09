# ruff: noqa: E501
"""Frozen staged P4-A2 high-recall eligibility rescue experiment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

import numpy as np

from eval.runtime_diagnostics.p4a_dwpose_eligibility import BASE_FEATURES, BONES, derive_slot_features

PROJECT = Path(__file__).resolve().parents[2]
EVALUATOR = Path(__file__).resolve()
EVIDENCE = PROJECT / "artifacts/recognition_upgrade/perception_backend_replacement/p4a2_fresh_evidence_repair_v2_01"
P3 = PROJECT / "artifacts/recognition_upgrade/perception_backend_replacement/p3_dwpose_temporal_usability_01"
P4A = PROJECT / "artifacts/recognition_upgrade/perception_backend_replacement/p4a_dwpose_presence_eligibility_01"
OUTPUT = PROJECT / "artifacts/recognition_upgrade/perception_backend_replacement/p4a2_high_recall_rescue_final_01"
INFERENCE_MANIFEST = OUTPUT / "p4a2_frozen_inference_manifest.csv"
INFERENCE_PROTOCOL = OUTPUT / "p4a2_frozen_inference_protocol.json"
INFERENCE_COMPLETION = OUTPUT / "p4a2_inference_completion.json"
FEATURES = OUTPUT / "p4a2_derived_features.csv"
FEATURE_MANIFEST = OUTPUT / "p4a2_rescue_feature_manifest.json"
E2_MODEL = P4A / "p4a_selected_model.json"
DEV = EVIDENCE / "splits/p4a2_dev_manifest.csv"
VALIDATION = EVIDENCE / "splits/p4a2_validation_manifest.csv"
FINAL = EVIDENCE / "sealed_final/p4a2_final_eval_manifest.csv"
R1_PROTOCOL = OUTPUT / "p4a2_r1_candidate_protocol.json"
SELECTION = OUTPUT / "p4a2_candidate_selection.json"
SELECTED_RULE = OUTPUT / "p4a2_selected_rescue_rule.json"
FINAL_MANIFEST = OUTPUT / "p4a2_final_evaluation_manifest.csv"
FINAL_RESULT = OUTPUT / "p4a2_final_result.json"

EXPECTED = {
    "dataset_sha256": "7819c59123b4dacdafac190c81754deb766d6ed6087a2b58535490d45a6a3edd",
    "annotation_sha256": "1b9f34412ba885e397019742bf29027987ce58668d099fd3914e48ab3206774b",
    "dev_sha256": "142efe1f1864dbe19efb16357948ed7a2fe5adb6faf9901a3679daf6291736d8",
    "validation_sha256": "a8ae3cb2a65433e5d21361254fe7490fdcd479a382ac784d79fc87e15fe84771",
    "final_sha256": "af78e1048566ad7842e792ae4dbd709bca43d79697ec1e0a234f94acfddcfcfc",
    "inference_manifest_sha256": "c6f55b5f2bfeb7e315d7f5cb8740cf48900480d91c5ffe99504a3a6d51745541",
}

R1_ALLOWED_FEATURES = [
    "hand_count_ge_030", "hand_score_min", "hand_score_mean", "hand_score_median",
    "hand_wrist_score", "mcp_score_mean", "mcp_score_min", "tip_score_mean", "tip_score_min",
    "hand_area_norm", "palm_spread_norm", "median_bone_norm", "bone_cv", "shoulder_score",
    "elbow_score", "body_wrist_score", "arm_score_min", "arm_score_mean", "arm_length_ratio",
    "hand_wrist_to_body_wrist_norm", "body_confident_count", "torso_score_min",
    "person_body_plausible",
]
R2_ALLOWED_FEATURES = [
    "current_e2_or_r1_reject", "previous_final_accept", "previous_dt_ms",
    "palm_displacement_norm", "median_bone_ratio_to_previous", "hand_count_ge_030",
    "hand_score_mean", "body_wrist_score", "consecutive_rescue_count",
]
GATES = {
    "visible_recall": 0.98,
    "one_hand_recall": 0.97,
    "zero_hand_fpr": 0.10,
    "rest_fpr": 0.10,
    "complete_two_hand": 0.95,
}
R1_CANDIDATES = [
    {
        "name": "R1_PRIMARY_ARM_COHERENT_SUPPORT",
        "complexity": 1,
        "all": {
            "hand_count_ge_030__ge": 8.0,
            "hand_score_mean__ge": 0.29,
            "arm_score_min__ge": 0.40,
            "body_wrist_score__ge": 0.40,
            "hand_wrist_to_body_wrist_norm__le": 0.10,
            "hand_area_norm__ge": 0.003,
            "hand_area_norm__le": 0.50,
            "bone_cv__le": 1.20,
            "person_body_plausible__ge": 1.0,
        },
        "derivation": "rounded DEV visible-E2-reject support/arm/geometry lower-tail bounds; no validation outcomes used",
    },
    {
        "name": "R1_VARIANT_SUPPORT_HEAVY",
        "complexity": 2,
        "all": {
            "hand_count_ge_030__ge": 18.0,
            "hand_score_mean__ge": 0.40,
            "mcp_score_min__ge": 0.30,
            "tip_score_min__ge": 0.25,
            "arm_score_min__ge": 0.35,
            "hand_wrist_to_body_wrist_norm__le": 0.20,
            "hand_area_norm__ge": 0.003,
            "hand_area_norm__le": 0.50,
            "bone_cv__le": 1.25,
            "person_body_plausible__ge": 1.0,
        },
        "derivation": "bounded high-joint-support variant fixed from DEV distributions; no validation outcomes used",
    },
    {
        "name": "R1_VARIANT_LOW_SUPPORT_ARM_COHERENT",
        "complexity": 3,
        "all": {
            "hand_count_ge_030__ge": 4.0,
            "hand_score_mean__ge": 0.23,
            "mcp_score_mean__ge": 0.25,
            "tip_score_mean__ge": 0.20,
            "arm_score_min__ge": 0.35,
            "body_wrist_score__ge": 0.35,
            "hand_wrist_to_body_wrist_norm__le": 0.10,
            "hand_area_norm__ge": 0.002,
            "hand_area_norm__le": 0.50,
            "bone_cv__le": 1.20,
            "person_body_plausible__ge": 1.0,
        },
        "derivation": "bounded lower-support variant using DEV p10-style support with stricter arm/geometry coherence; no validation outcomes used",
    },
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(rows[0]) if rows else [])
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1"}


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def verify_pre_final() -> dict[str, Any]:
    meta = json.loads((EVIDENCE / "frozen_truth/P4A2_FRESH_HUMAN_TRUTH_V1.json").read_text(encoding="utf-8"))
    checks = {
        "dataset_sha256": meta["dataset_sha256"],
        "annotation_sha256": sha256(EVIDENCE / "frozen_truth/P4A2_FRESH_HUMAN_TRUTH_V1.csv"),
        "dev_sha256": sha256(DEV),
        "validation_sha256": sha256(VALIDATION),
        "final_sha256": sha256(FINAL),
        "inference_manifest_sha256": sha256(INFERENCE_MANIFEST),
    }
    if checks != EXPECTED:
        raise RuntimeError(f"P4A2_FROZEN_EVIDENCE_MISMATCH: {checks}")
    inference = json.loads(INFERENCE_COMPLETION.read_text(encoding="utf-8"))
    if inference["processed"] != 256 or inference["reused_p3_outputs"] != 202 or len(inference["raw_output_hashes"]) != 256:
        raise RuntimeError("P4-A2 native inference completion mismatch")
    for item in inference["raw_output_hashes"]:
        path = OUTPUT / item["path"]
        if sha256(path) != item["sha256"]:
            raise RuntimeError(f"P4-A2 native output hash mismatch: {item['path']}")
    p4a_manifest = json.loads((P4A / "provenance_hash_manifest.json").read_text(encoding="utf-8"))["files"]
    p4a_hashes = {row["path"].replace("\\", "/"): row["sha256"] for row in p4a_manifest}
    for name in ("p4a_selected_model.json", "p4a_feature_manifest.json"):
        if sha256(P4A / name) != p4a_hashes[name]:
            raise RuntimeError(f"Frozen E2 mismatch: {name}")
    return checks


def prepare() -> dict[str, Any]:
    checks = verify_pre_final()
    if FEATURES.exists() or FEATURE_MANIFEST.exists():
        raise RuntimeError("P4-A2 feature evidence already prepared")
    manifest = read_csv(INFERENCE_MANIFEST)
    rows: list[dict[str, Any]] = []
    for frame in manifest:
        raw_path = PROJECT / frame["raw_relative_path"]
        raw = np.load(raw_path)
        keypoints = np.asarray(raw["keypoints_133"], dtype=np.float64)
        scores = np.asarray(raw["scores_133"], dtype=np.float64)
        source_hash = str(np.asarray(raw["source_sha256"]).item())
        roi = np.asarray(raw["roi_xyxy"], dtype=np.float64)
        width, height = int(round(roi[2])), int(round(roi[3]))
        if keypoints.shape != (133, 2) or scores.shape != (133,) or source_hash != frame["image_sha256"]:
            raise RuntimeError(f"Invalid native output provenance: {frame['annotation_row_id']}")
        for side in ("left", "right"):
            values, palm = derive_slot_features(keypoints, scores, side, width, height)
            hand_slice = slice(91, 112) if side == "left" else slice(112, 133)
            hand = keypoints[hand_slice]
            bone_lengths = np.linalg.norm(hand[BONES[:, 0]] - hand[BONES[:, 1]], axis=1)
            rows.append({
                "eligibility_row_id": f"{frame['annotation_row_id']}__{side}",
                "annotation_row_id": frame["annotation_row_id"],
                "sequence_id": frame["sequence_id"],
                "frame_index": frame["frame_index"],
                "timestamp_ns": frame["timestamp_ns"],
                "signer_id": frame["signer_id"],
                "gloss": frame["gloss"],
                "split_role": frame["intended_future_role"],
                "anatomical_side": side,
                "raw_origin": frame["raw_origin"],
                **values,
                "palm_x_norm": float(palm[0]),
                "palm_y_norm": float(palm[1]),
                "median_bone_px": float(np.median(bone_lengths)),
            })
    by_sequence_side: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_sequence_side[(row["sequence_id"], row["anatomical_side"])].append(row)
    for sequence in by_sequence_side.values():
        sequence.sort(key=lambda row: (int(row["timestamp_ns"]), int(row["frame_index"])))
        previous: dict[str, Any] | None = None
        for row in sequence:
            dt_ms = 0.0 if previous is None else (int(row["timestamp_ns"]) - int(previous["timestamp_ns"])) / 1e6
            valid = previous is not None and 0 < dt_ms <= 1000
            row["previous_exists"] = valid
            row["previous_dt_ms"] = dt_ms if valid else 0.0
            row["palm_displacement_norm"] = (
                float(np.linalg.norm(np.asarray([row["palm_x_norm"], row["palm_y_norm"]]) - np.asarray([previous["palm_x_norm"], previous["palm_y_norm"]])))
                if valid else 0.0
            )
            row["median_bone_ratio_to_previous"] = (
                float(row["median_bone_px"] / max(float(previous["median_bone_px"]), 1e-8)) if valid else 1.0
            )
            previous = row
    e2 = json.loads(E2_MODEL.read_text(encoding="utf-8"))["model"]
    coefficients = np.asarray(e2["coefficients"], dtype=np.float64)
    mean = np.asarray(e2["mean"], dtype=np.float64)
    scale = np.asarray(e2["scale"], dtype=np.float64)
    for row in rows:
        vector = np.asarray([float(row[name]) for name in e2["features"]], dtype=np.float64)
        logit = float(coefficients[0] + ((vector - mean) / scale) @ coefficients[1:])
        probability = 1.0 / (1.0 + math.exp(-max(-50.0, min(50.0, logit))))
        row["e2_probability"] = probability
        row["e2_accept"] = probability >= float(e2["threshold"])
    write_csv(FEATURES, rows)
    feature_manifest = {
        "identity": "P4A2_HIGH_RECALL_ELIGIBILITY_RESCUE_FEATURE_FREEZE",
        "e2_identity": "E2_FIXED_L2_LOGISTIC_SINGLE_FRAME",
        "e2_model_sha256": sha256(E2_MODEL),
        "e2_features": BASE_FEATURES,
        "r1_allowed_features": R1_ALLOWED_FEATURES,
        "r1_candidate_limit": "one primary plus at most two bounded variants; thresholds derived on DEV only and frozen before validation selection",
        "r1_activation": "E2_REJECT only",
        "r2_allowed_features": R2_ALLOWED_FEATURES,
        "r2_activation": "only if frozen R1 validation shows isolated/transition deficit",
        "r2_frozen_safety_template": {
            "max_consecutive_rescues": 1,
            "requires_previous_final_accept": True,
            "requires_current_native_prediction": True,
            "minimum_current_joint_support": 11,
            "minimum_current_mean_score": 0.25,
            "minimum_current_body_wrist_score": 0.30,
            "maximum_palm_displacement_norm": 0.50,
            "median_bone_ratio_range": [0.5, 2.0],
            "no_future_frames": True,
            "no_coordinate_carry_forward": True,
        },
        "gates": GATES,
        "limitations": ["zero WEAK one-hand labels", "no positive optional blur/occlusion/contact subgroup labels"],
        "features_sha256": sha256(FEATURES),
        "inference_manifest_sha256": checks["inference_manifest_sha256"],
        "final_truth_status": "SEALED",
    }
    write_json(FEATURE_MANIFEST, feature_manifest)
    return {"feature_rows": len(rows), "frames": len(rows) // 2, "feature_manifest": feature_manifest}


def truth_rows(path: Path, role: str) -> list[dict[str, Any]]:
    frames = read_csv(path)
    rows: list[dict[str, Any]] = []
    for frame in frames:
        left_visible = frame["visible_left"] == "YES"
        right_visible = frame["visible_right"] == "YES"
        if frame["visible_left"] == "UNCERTAIN" or frame["visible_right"] == "UNCERTAIN":
            continue
        for side, visible in (("left", left_visible), ("right", right_visible)):
            rows.append({
                "eligibility_row_id": f"{frame['annotation_row_id']}__{side}",
                "annotation_row_id": frame["annotation_row_id"],
                "sequence_id": frame["sequence_id"],
                "frame_index": frame["frame_index"],
                "signer_id": frame["signer_id"],
                "gloss": frame["gloss"],
                "split_role": role,
                "anatomical_side": side,
                "truth_visible": visible,
                "one_hand_frame": left_visible ^ right_visible,
                "two_hand_frame": left_visible and right_visible,
                "zero_hand_frame": frame["zero_hand"] == "YES",
                "rest_frame": frame["rest"] == "YES",
                "entering_frame": frame["entering"] == "YES",
                "leaving_frame": frame["leaving"] == "YES",
            })
    return rows


def joined_rows(path: Path, role: str) -> list[dict[str, Any]]:
    features = {row["eligibility_row_id"]: row for row in read_csv(FEATURES)}
    rows = []
    for truth in truth_rows(path, role):
        feature = features[truth["eligibility_row_id"]]
        rows.append({**feature, **truth})
    return rows


def metric_bundle(rows: list[dict[str, Any]], predictions: list[bool]) -> dict[str, Any]:
    paired = list(zip(rows, predictions, strict=True))
    tp = sum(parse_bool(row["truth_visible"]) and pred for row, pred in paired)
    fp = sum(not parse_bool(row["truth_visible"]) and pred for row, pred in paired)
    tn = sum(not parse_bool(row["truth_visible"]) and not pred for row, pred in paired)
    fn = sum(parse_bool(row["truth_visible"]) and not pred for row, pred in paired)
    frames: dict[str, list[tuple[dict[str, Any], bool]]] = defaultdict(list)
    for row, pred in paired:
        frames[row["annotation_row_id"]].append((row, pred))
    zero = [values for values in frames.values() if parse_bool(values[0][0]["zero_hand_frame"])]
    rest = [values for values in frames.values() if parse_bool(values[0][0]["rest_frame"])]
    two = [values for values in frames.values() if parse_bool(values[0][0]["two_hand_frame"])]
    one_visible = [(row, pred) for row, pred in paired if parse_bool(row["one_hand_frame"]) and parse_bool(row["truth_visible"])]
    entry = [values for values in frames.values() if parse_bool(values[0][0]["entering_frame"])]
    leaving = [values for values in frames.values() if parse_bool(values[0][0]["leaving_frame"])]
    return {
        "rows": len(rows),
        "frames": len(frames),
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "specificity": ratio(tn, tn + fp),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
        "one_hand_visible_recall": {"numerator": sum(pred for _, pred in one_visible), "denominator": len(one_visible), "rate": ratio(sum(pred for _, pred in one_visible), len(one_visible))},
        "zero_hand_frame_false_presence": {"numerator": sum(any(pred for _, pred in values) for values in zero), "denominator": len(zero), "rate": ratio(sum(any(pred for _, pred in values) for values in zero), len(zero))},
        "rest_frame_false_presence": {"numerator": sum(any(pred for _, pred in values) for values in rest), "denominator": len(rest), "rate": ratio(sum(any(pred for _, pred in values) for values in rest), len(rest))},
        "complete_two_hand_retention": {"numerator": sum(all(pred for _, pred in values) for values in two), "denominator": len(two), "rate": ratio(sum(all(pred for _, pred in values) for values in two), len(two))},
        "entry_any_presence": {"numerator": sum(any(pred for _, pred in values) for values in entry), "denominator": len(entry), "rate": ratio(sum(any(pred for _, pred in values) for values in entry), len(entry))},
        "leaving_any_presence": {"numerator": sum(any(pred for _, pred in values) for values in leaving), "denominator": len(leaving), "rate": ratio(sum(any(pred for _, pred in values) for values in leaving), len(leaving))},
    }


def baseline() -> dict[str, Any]:
    verify_pre_final()
    if not FEATURES.exists() or sha256(FEATURES) != json.loads(FEATURE_MANIFEST.read_text(encoding="utf-8"))["features_sha256"]:
        raise RuntimeError("P4-A2 frozen features missing or changed")
    dev_rows = joined_rows(DEV, "DEV_POOL")
    validation_rows = joined_rows(VALIDATION, "VALIDATION_POOL")
    result: dict[str, Any] = {}
    output_rows: list[dict[str, Any]] = []
    for role, rows in (("development", dev_rows), ("validation", validation_rows)):
        predictions = [parse_bool(row["e2_accept"]) for row in rows]
        result[role] = metric_bundle(rows, predictions)
        for row, prediction in zip(rows, predictions, strict=True):
            output_rows.append({**row, "system": "E2_ONLY", "prediction_eligible": prediction})
    result["final_evaluation"] = "SEALED"
    write_json(OUTPUT / "p4a2_e2_baseline_results.json", result)
    write_csv(OUTPUT / "p4a2_fresh_e2_baseline.csv", output_rows)
    dev_failures = [
        {key: row[key] for key in [
            "eligibility_row_id", "annotation_row_id", "sequence_id", "frame_index", "anatomical_side",
            "truth_visible", "one_hand_frame", "zero_hand_frame", "rest_frame", "entering_frame", "leaving_frame",
            "e2_probability", *R1_ALLOWED_FEATURES,
        ]}
        for row in dev_rows
        if (parse_bool(row["truth_visible"]) and not parse_bool(row["e2_accept"]))
        or (not parse_bool(row["truth_visible"]) and parse_bool(row["e2_accept"]))
    ]
    write_csv(OUTPUT / "p4a2_development_e2_failure_diagnostics.csv", dev_failures)
    return result


def diagnose_development() -> dict[str, Any]:
    """Summarize DEV-only E2 rejects; this is not a candidate sweep."""
    verify_pre_final()
    rows = joined_rows(DEV, "DEV_POOL")
    rejected = [row for row in rows if not parse_bool(row["e2_accept"])]
    groups = {
        "visible_e2_reject": [row for row in rejected if parse_bool(row["truth_visible"])],
        "not_visible_e2_reject": [row for row in rejected if not parse_bool(row["truth_visible"])],
    }
    selected = [
        "hand_count_ge_030", "hand_score_mean", "hand_score_min", "hand_wrist_score",
        "mcp_score_mean", "mcp_score_min", "tip_score_mean", "tip_score_min",
        "arm_score_min", "body_wrist_score", "hand_wrist_to_body_wrist_norm",
        "hand_area_norm", "bone_cv", "person_body_plausible",
    ]
    summary: dict[str, Any] = {}
    for name, subset in groups.items():
        summary[name] = {"rows": len(subset), "one_hand_rows": sum(parse_bool(row["one_hand_frame"]) for row in subset)}
        for feature in selected:
            values = np.asarray([float(row[feature]) for row in subset], dtype=np.float64)
            summary[name][feature] = {
                "min": float(np.min(values)), "p10": float(np.percentile(values, 10)),
                "p25": float(np.percentile(values, 25)), "p50": float(np.percentile(values, 50)),
                "p75": float(np.percentile(values, 75)), "p90": float(np.percentile(values, 90)),
                "max": float(np.max(values)),
            } if len(values) else None
    native_predictions = [float(row["hand_count_ge_030"]) >= 11 for row in rows]
    summary["native_030_11_dev_metrics"] = metric_bundle(rows, native_predictions)
    write_json(OUTPUT / "p4a2_development_r1_diagnostic.json", summary)
    return summary


def freeze_r1_candidates() -> dict[str, Any]:
    verify_pre_final()
    if R1_PROTOCOL.exists():
        raise RuntimeError("P4-A2 R1 candidate protocol is already frozen")
    feature_manifest = json.loads(FEATURE_MANIFEST.read_text(encoding="utf-8"))
    protocol = {
        "identity": "P4A2_R1_BOUNDED_CANDIDATE_FREEZE",
        "candidate_count": len(R1_CANDIDATES),
        "candidates": R1_CANDIDATES,
        "activation": "only when frozen E2 rejects",
        "selection_evidence": "validation only after DEV-derived candidate freeze",
        "selection_order": [
            "all gates pass", "highest visible recall", "highest one-hand recall",
            "lowest zero-hand FPR", "lowest rest FPR", "lowest complexity",
        ],
        "r2_template": feature_manifest["r2_frozen_safety_template"],
        "r2_activation": "only if selected frozen R1 validation has a remaining causal-continuity-eligible visible rejection and fails a recall gate",
        "feature_manifest_sha256": sha256(FEATURE_MANIFEST),
        "development_diagnostic_sha256": sha256(OUTPUT / "p4a2_development_r1_diagnostic.json"),
        "validation_candidate_results_accessed": False,
        "final_truth_status": "SEALED",
    }
    write_json(R1_PROTOCOL, protocol)
    return protocol


def rule_matches(row: dict[str, Any], candidate: dict[str, Any]) -> bool:
    for expression, threshold in candidate["all"].items():
        feature, operator = expression.rsplit("__", 1)
        value = float(row[feature])
        if operator == "ge" and value < float(threshold):
            return False
        if operator == "le" and value > float(threshold):
            return False
    return True


def apply_r1(rows: list[dict[str, Any]], candidate: dict[str, Any]) -> tuple[list[bool], list[bool]]:
    predictions = []
    rescues = []
    for row in rows:
        e2 = parse_bool(row["e2_accept"])
        rescue = not e2 and rule_matches(row, candidate)
        predictions.append(e2 or rescue)
        rescues.append(rescue)
    return predictions, rescues


def apply_r2(rows: list[dict[str, Any]], base_predictions: list[bool]) -> tuple[list[bool], list[bool]]:
    by_key: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_key[(row["sequence_id"], row["anatomical_side"])].append(index)
    final = list(base_predictions)
    rescued = [False] * len(rows)
    for indices in by_key.values():
        indices.sort(key=lambda index: (int(rows[index]["timestamp_ns"]), int(rows[index]["frame_index"])))
        previous_accept = False
        previous_was_rescue = False
        for index in indices:
            row = rows[index]
            if final[index]:
                previous_accept = True
                previous_was_rescue = False
                continue
            continuity = (
                previous_accept
                and not previous_was_rescue
                and parse_bool(row["previous_exists"])
                and 0 < float(row["previous_dt_ms"]) <= 1000
                and float(row["hand_count_ge_030"]) >= 11
                and float(row["hand_score_mean"]) >= 0.25
                and float(row["body_wrist_score"]) >= 0.30
                and float(row["palm_displacement_norm"]) <= 0.50
                and 0.5 <= float(row["median_bone_ratio_to_previous"]) <= 2.0
            )
            if continuity:
                final[index] = True
                rescued[index] = True
                previous_accept = True
                previous_was_rescue = True
            else:
                previous_accept = False
                previous_was_rescue = False
    return final, rescued


def gate_values(metrics: dict[str, Any]) -> dict[str, bool]:
    return {
        "visible_recall": metrics["recall"] is not None and metrics["recall"] >= GATES["visible_recall"],
        "one_hand_recall": metrics["one_hand_visible_recall"]["rate"] is not None and metrics["one_hand_visible_recall"]["rate"] >= GATES["one_hand_recall"],
        "zero_hand_fpr": metrics["zero_hand_frame_false_presence"]["rate"] is not None and metrics["zero_hand_frame_false_presence"]["rate"] <= GATES["zero_hand_fpr"],
        "rest_fpr": metrics["rest_frame_false_presence"]["rate"] is not None and metrics["rest_frame_false_presence"]["rate"] <= GATES["rest_fpr"],
        "complete_two_hand": metrics["complete_two_hand_retention"]["rate"] is not None and metrics["complete_two_hand_retention"]["rate"] >= GATES["complete_two_hand"],
    }


def compact_candidate_row(name: str, split: str, metrics: dict[str, Any], complexity: int, r2: bool = False) -> dict[str, Any]:
    gates = gate_values(metrics)
    return {
        "candidate": name, "split": split, "r2_activated": r2, "complexity": complexity,
        "visible_recall": metrics["recall"],
        "one_hand_recall": metrics["one_hand_visible_recall"]["rate"],
        "zero_hand_fpr": metrics["zero_hand_frame_false_presence"]["rate"],
        "rest_fpr": metrics["rest_frame_false_presence"]["rate"],
        "complete_two_hand": metrics["complete_two_hand_retention"]["rate"],
        **{f"gate_{key}": value for key, value in gates.items()},
        "all_gates": all(gates.values()),
    }


def candidate_rank(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        not parse_bool(row["all_gates"]),
        -float(row["visible_recall"] or 0.0),
        -float(row["one_hand_recall"] or 0.0),
        float(row["zero_hand_fpr"] if row["zero_hand_fpr"] is not None else 1.0),
        float(row["rest_fpr"] if row["rest_fpr"] is not None else 1.0),
        int(row["complexity"]),
        row["candidate"],
    )


def select_candidate() -> dict[str, Any]:
    verify_pre_final()
    if SELECTION.exists() or SELECTED_RULE.exists() or FINAL_MANIFEST.exists():
        raise RuntimeError("P4-A2 candidate selection is already frozen")
    protocol = json.loads(R1_PROTOCOL.read_text(encoding="utf-8"))
    if protocol["validation_candidate_results_accessed"]:
        raise RuntimeError("P4-A2 R1 validation was already accessed")
    if sha256(FEATURE_MANIFEST) != protocol["feature_manifest_sha256"]:
        raise RuntimeError("P4-A2 rescue feature freeze changed")
    dev_rows = joined_rows(DEV, "DEV_POOL")
    validation_rows = joined_rows(VALIDATION, "VALIDATION_POOL")
    comparison: list[dict[str, Any]] = []
    candidate_details: dict[str, Any] = {}
    for candidate in protocol["candidates"]:
        dev_prediction, dev_rescue = apply_r1(dev_rows, candidate)
        validation_prediction, validation_rescue = apply_r1(validation_rows, candidate)
        dev_metrics = metric_bundle(dev_rows, dev_prediction)
        validation_metrics = metric_bundle(validation_rows, validation_prediction)
        comparison.append(compact_candidate_row(candidate["name"], "development", dev_metrics, candidate["complexity"]))
        comparison.append(compact_candidate_row(candidate["name"], "validation", validation_metrics, candidate["complexity"]))
        candidate_details[candidate["name"]] = {
            "rule": candidate,
            "development_metrics": dev_metrics,
            "validation_metrics": validation_metrics,
            "development_rescues": sum(dev_rescue),
            "validation_rescues": sum(validation_rescue),
        }
    validation_summary = [row for row in comparison if row["split"] == "validation"]
    validation_summary.sort(key=candidate_rank)
    selected_r1_name = validation_summary[0]["candidate"]
    selected_r1 = next(candidate for candidate in protocol["candidates"] if candidate["name"] == selected_r1_name)
    base_validation_prediction, base_validation_rescues = apply_r1(validation_rows, selected_r1)
    base_validation_metrics = metric_bundle(validation_rows, base_validation_prediction)
    remaining_visible = [
        index for index, (row, pred) in enumerate(zip(validation_rows, base_validation_prediction, strict=True))
        if parse_bool(row["truth_visible"]) and not pred
    ]
    causal_eligible = []
    r2_probe_prediction, r2_probe_rescues = apply_r2(validation_rows, base_validation_prediction)
    for index in remaining_visible:
        if r2_probe_rescues[index]:
            causal_eligible.append(index)
    recall_gate_failed = not gate_values(base_validation_metrics)["visible_recall"] or not gate_values(base_validation_metrics)["one_hand_recall"]
    activate_r2 = recall_gate_failed and bool(causal_eligible)
    r2_metrics = None
    selected_system = "E2_PLUS_R1"
    selected_validation_prediction = base_validation_prediction
    if activate_r2:
        r2_metrics = metric_bundle(validation_rows, r2_probe_prediction)
        r2_row = compact_candidate_row(f"{selected_r1_name}_PLUS_R2", "validation", r2_metrics, selected_r1["complexity"] + 10, r2=True)
        comparison.append(r2_row)
        base_row = compact_candidate_row(selected_r1_name, "validation", base_validation_metrics, selected_r1["complexity"])
        if candidate_rank(r2_row) < candidate_rank(base_row):
            selected_system = "E2_PLUS_R1_PLUS_R2"
            selected_validation_prediction = r2_probe_prediction
    selected_validation_metrics = metric_bundle(validation_rows, selected_validation_prediction)
    write_csv(OUTPUT / "p4a2_r1_validation_results.csv", comparison)
    if activate_r2:
        r2_case_rows = []
        for row, base, final, rescue in zip(validation_rows, base_validation_prediction, r2_probe_prediction, r2_probe_rescues, strict=True):
            if rescue or (parse_bool(row["truth_visible"]) and not final):
                r2_case_rows.append({**row, "r1_prediction": base, "r2_rescue": rescue, "final_prediction": final})
        write_csv(OUTPUT / "p4a2_r2_validation_results.csv", r2_case_rows)
    identity_rows = [
        {key: row[key] for key in (
            "annotation_row_id", "sequence_id", "frame_index", "timestamp_ns", "signer_id", "gloss",
            "image_path", "image_sha256", "raw_origin", "raw_relative_path",
        )}
        for row in read_csv(INFERENCE_MANIFEST)
        if row["intended_future_role"] == "FINAL_EVAL_POOL"
    ]
    if len(identity_rows) != 196 or len({row["sequence_id"] for row in identity_rows}) != 12:
        raise RuntimeError("P4-A2 final identity-only manifest changed")
    write_csv(FINAL_MANIFEST, identity_rows)
    selected_rule = {
        "selected_system": selected_system,
        "e2_model_sha256": sha256(E2_MODEL),
        "r1": selected_r1,
        "r2_activated": selected_system == "E2_PLUS_R1_PLUS_R2",
        "r2_rule": protocol["r2_template"] if selected_system == "E2_PLUS_R1_PLUS_R2" else None,
        "normalization": "frozen E2 mean/scale; R1/R2 native feature values are unstandardized",
        "features_sha256": sha256(FEATURES),
        "feature_manifest_sha256": sha256(FEATURE_MANIFEST),
    }
    write_json(SELECTED_RULE, selected_rule)
    selection = {
        "status": "CANDIDATE_FROZEN_BEFORE_FINAL_TRUTH",
        "selected_system": selected_system,
        "selected_r1": selected_r1_name,
        "r2_activated": selected_system == "E2_PLUS_R1_PLUS_R2",
        "r2_considered": activate_r2,
        "remaining_visible_after_r1": len(remaining_visible),
        "causal_continuity_eligible_visible_rejects": len(causal_eligible),
        "validation_metrics": selected_validation_metrics,
        "validation_gates": gate_values(selected_validation_metrics),
        "candidate_details": candidate_details,
        "selected_rule_sha256": sha256(SELECTED_RULE),
        "final_identity_manifest_sha256": sha256(FINAL_MANIFEST),
        "final_truth_sha256": EXPECTED["final_sha256"],
        "evaluator_sha256": sha256(EVALUATOR),
        "final_evaluation_executions": 0,
    }
    write_json(SELECTION, selection)
    protocol["validation_candidate_results_accessed"] = True
    protocol["candidate_results_sha256"] = sha256(OUTPUT / "p4a2_r1_validation_results.csv")
    write_json(R1_PROTOCOL, protocol)
    return selection


def prediction_rows_for_system(rows: list[dict[str, Any]], selected_rule: dict[str, Any]) -> tuple[list[bool], list[bool], list[bool]]:
    r1_prediction, r1_rescue = apply_r1(rows, selected_rule["r1"])
    if selected_rule["r2_activated"]:
        final_prediction, r2_rescue = apply_r2(rows, r1_prediction)
    else:
        final_prediction, r2_rescue = r1_prediction, [False] * len(rows)
    return final_prediction, r1_rescue, r2_rescue


def fmt_rate(metric: dict[str, Any]) -> str:
    return f"{metric['numerator']}/{metric['denominator']} = {100 * metric['rate']:.3f}%" if metric["rate"] is not None else "N/A"


def final_evaluation() -> dict[str, Any]:
    verify_pre_final()
    if FINAL_RESULT.exists():
        raise RuntimeError("P4-A2 final evaluation has already been executed")
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    selected_rule = json.loads(SELECTED_RULE.read_text(encoding="utf-8"))
    if selection["final_evaluation_executions"] != 0:
        raise RuntimeError("P4-A2 final evaluation execution counter is not zero")
    if sha256(EVALUATOR) != selection["evaluator_sha256"] or sha256(SELECTED_RULE) != selection["selected_rule_sha256"]:
        raise RuntimeError("P4A2_PROTOCOL_INVALID: candidate code/rule changed after freeze")
    if sha256(FINAL_MANIFEST) != selection["final_identity_manifest_sha256"] or sha256(FINAL) != selection["final_truth_sha256"]:
        raise RuntimeError("P4A2_FROZEN_EVIDENCE_MISMATCH: final manifest changed")
    rows = joined_rows(FINAL, "FINAL_EVAL_POOL")
    if len(rows) != 392 or len({row["annotation_row_id"] for row in rows}) != 196 or len({row["sequence_id"] for row in rows}) != 12:
        raise RuntimeError("P4A2_PROTOCOL_INVALID: final evaluation identity changed")
    e2_prediction = [parse_bool(row["e2_accept"]) for row in rows]
    final_prediction, r1_rescue, r2_rescue = prediction_rows_for_system(rows, selected_rule)
    e2_metrics = metric_bundle(rows, e2_prediction)
    final_metrics = metric_bundle(rows, final_prediction)
    final_gates = gate_values(final_metrics)
    predictions = []
    for row, e2, final, r1, r2 in zip(rows, e2_prediction, final_prediction, r1_rescue, r2_rescue, strict=True):
        predictions.append({
            "eligibility_row_id": row["eligibility_row_id"], "annotation_row_id": row["annotation_row_id"],
            "sequence_id": row["sequence_id"], "frame_index": row["frame_index"], "signer_id": row["signer_id"],
            "gloss": row["gloss"], "anatomical_side": row["anatomical_side"], "truth_visible": row["truth_visible"],
            "one_hand_frame": row["one_hand_frame"], "two_hand_frame": row["two_hand_frame"],
            "zero_hand_frame": row["zero_hand_frame"], "rest_frame": row["rest_frame"],
            "entering_frame": row["entering_frame"], "leaving_frame": row["leaving_frame"],
            "e2_probability": row["e2_probability"], "e2_accept": e2, "r1_rescue": r1,
            "r2_rescue": r2, "selected_prediction": final,
            **{name: row[name] for name in R1_ALLOWED_FEATURES},
            "previous_dt_ms": row["previous_dt_ms"], "palm_displacement_norm": row["palm_displacement_norm"],
            "median_bone_ratio_to_previous": row["median_bone_ratio_to_previous"],
        })
    write_csv(OUTPUT / "p4a2_final_eval_predictions.csv", predictions)
    one_hand_frames: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in predictions:
        if parse_bool(row["one_hand_frame"]):
            one_hand_frames[row["annotation_row_id"]].append(row)
    one_hand_cases = []
    for frame_id, values in sorted(one_hand_frames.items()):
        visible = next(row for row in values if parse_bool(row["truth_visible"]))
        opposite = next(row for row in values if not parse_bool(row["truth_visible"]))
        one_hand_cases.append({
            "annotation_row_id": frame_id, "sequence_id": visible["sequence_id"], "frame_index": visible["frame_index"],
            "signer_id": visible["signer_id"], "gloss": visible["gloss"], "visible_side": visible["anatomical_side"],
            "e2_visible_accepted": visible["e2_accept"], "rescue_visible_accepted": visible["selected_prediction"],
            "remaining_false_negative": not parse_bool(visible["selected_prediction"]),
            "opposite_nonvisible_e2_false_positive": opposite["e2_accept"],
            "opposite_nonvisible_selected_false_positive": opposite["selected_prediction"],
        })
    write_csv(OUTPUT / "p4a2_one_hand_case_results.csv", one_hand_cases)
    rescued_visible = [row for row in predictions if parse_bool(row["truth_visible"]) and not parse_bool(row["e2_accept"]) and parse_bool(row["selected_prediction"])]
    new_false = [row for row in predictions if not parse_bool(row["truth_visible"]) and not parse_bool(row["e2_accept"]) and parse_bool(row["selected_prediction"])]
    entry_leaving = [row for row in predictions if parse_bool(row["entering_frame"]) or parse_bool(row["leaving_frame"])]
    write_csv(OUTPUT / "p4a2_rescued_visible_cases.csv", rescued_visible)
    write_csv(OUTPUT / "p4a2_new_false_positive_cases.csv", new_false)
    write_csv(OUTPUT / "p4a2_entry_leaving_cases.csv", entry_leaving)
    visible_lost = sum(parse_bool(row["truth_visible"]) and parse_bool(row["e2_accept"]) and not parse_bool(row["selected_prediction"]) for row in predictions)
    one_hand_gained = sum(parse_bool(row["one_hand_frame"]) and parse_bool(row["truth_visible"]) and not parse_bool(row["e2_accept"]) and parse_bool(row["selected_prediction"]) for row in predictions)
    zero_frames: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rest_frames: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in predictions:
        if parse_bool(row["zero_hand_frame"]):
            zero_frames[row["annotation_row_id"]].append(row)
        if parse_bool(row["rest_frame"]):
            rest_frames[row["annotation_row_id"]].append(row)
    new_zero_fp = sum(not any(parse_bool(row["e2_accept"]) for row in values) and any(parse_bool(row["selected_prediction"]) for row in values) for values in zero_frames.values())
    new_rest_fp = sum(not any(parse_bool(row["e2_accept"]) for row in values) and any(parse_bool(row["selected_prediction"]) for row in values) for values in rest_frames.values())
    all_pass = all(final_gates.values())
    improvement = (final_metrics["recall"] or 0.0) > (e2_metrics["recall"] or 0.0)
    classification = "ELIGIBILITY_SOLVED" if all_pass else "ELIGIBILITY_IMPROVED_BUT_GATES_FAILED" if improvement else "BOUNDED_RESCUE_INSUFFICIENT"
    result = {
        "status": "P4A2_COMPLETE", "classification": classification,
        "frozen_evidence_hash_verified": True, "selected_system": selected_rule["selected_system"],
        "r1_tested": True, "r2_activated": selected_rule["r2_activated"],
        "final_evaluation": {"frames": 196, "sequences": 12, "signers": 5, "signer_separated": True},
        "e2_final_metrics": e2_metrics, "selected_final_metrics": final_metrics, "final_gates": final_gates,
        "all_final_gates_passed": all_pass, "visible_hands_rescued_relative_to_e2": len(rescued_visible),
        "visible_hands_lost_relative_to_e2": visible_lost, "one_hand_observations_gained": one_hand_gained,
        "new_zero_hand_false_positive_frames": new_zero_fp, "new_rest_false_positive_frames": new_rest_fp,
        "r1_rescues": sum(r1_rescue), "r2_rescues": sum(r2_rescue),
        "rescues_on_true_absence_slots": len(new_false),
        "limitations": [
            "The fresh final set has zero WEAK one-hand labels.",
            "The fresh final set has no positive optional blur/occlusion/contact subgroup labels.",
            "Passing eligibility gates would not establish recognition, Android, representation, or difficult-condition robustness.",
        ],
        "final_evaluation_executions": 1,
    }
    write_json(FINAL_RESULT, result)
    baseline_result = json.loads((OUTPUT / "p4a2_e2_baseline_results.json").read_text(encoding="utf-8"))
    baseline_result["final_evaluation"] = e2_metrics
    write_json(OUTPUT / "p4a2_e2_baseline_results.json", baseline_result)
    selection["final_evaluation_executions"] = 1
    selection["final_result_sha256"] = sha256(FINAL_RESULT)
    write_json(SELECTION, selection)
    write_report(result, selection)
    create_hash_manifest()
    return result


def write_report(result: dict[str, Any], selection: dict[str, Any]) -> None:
    e2 = result["e2_final_metrics"]
    final = result["selected_final_metrics"]
    report = f"""# P4-A2 High-Recall Eligibility Rescue Final Result

Status: `P4A2_COMPLETE`  
Classification: `{result['classification']}`  
Selected system: `{result['selected_system']}`

## Frozen evidence and protocol

The frozen dataset and annotation hashes matched `P4A2_FRESH_HUMAN_TRUTH_V1`. The 458-frame set
contains 28 sequences and 14 signers; development/validation remained sequence-separated and the
196-frame, 12-sequence final set remained signer-separated. The final truth was not opened until
the R1/R2 rule, thresholds, feature list, code hash, and identity-only final manifest were frozen.
The first valid final execution is canonical and the execution counter is one.

Frozen E2 was reused byte-for-byte and was not retrained. Existing P3 native outputs covered 202
frames; the exact frozen DWPose-L inference was run only for the 256 frames whose native outputs
were absent. No DWPose configuration, ROI, decoder, threshold, or model changed.

## Development and validation selection

R1 was limited to one primary rule and two bounded DEV-derived variants. It only acts on E2
rejections. Selected R1: `{selection['selected_r1']}`. R2 considered:
{selection['r2_considered']}; R2 selected: {result['r2_activated']}. Validation gates:
`{json.dumps(selection['validation_gates'], sort_keys=True)}`.

## Fresh signer-separated final evaluation

| Metric | Frozen E2 | Selected rescue |
|---|---:|---:|
| Per-hand precision | {e2['precision']:.4f} | {final['precision']:.4f} |
| Per-hand recall | {e2['recall']:.4f} | {final['recall']:.4f} |
| Specificity | {e2['specificity']:.4f} | {final['specificity']:.4f} |
| F1 | {e2['f1']:.4f} | {final['f1']:.4f} |
| One-hand visible recall | {fmt_rate(e2['one_hand_visible_recall'])} | {fmt_rate(final['one_hand_visible_recall'])} |
| Zero-hand frame false presence | {fmt_rate(e2['zero_hand_frame_false_presence'])} | {fmt_rate(final['zero_hand_frame_false_presence'])} |
| Rest-frame false presence | {fmt_rate(e2['rest_frame_false_presence'])} | {fmt_rate(final['rest_frame_false_presence'])} |
| Complete two-hand retention | {fmt_rate(e2['complete_two_hand_retention'])} | {fmt_rate(final['complete_two_hand_retention'])} |

Selected confusion: `{json.dumps(final['confusion'], sort_keys=True)}`. Entry behavior:
{fmt_rate(final['entry_any_presence'])}; leaving behavior: {fmt_rate(final['leaving_any_presence'])}.

Relative to E2, the rescue gained {result['visible_hands_rescued_relative_to_e2']} visible-hand
observations, lost {result['visible_hands_lost_relative_to_e2']}, gained
{result['one_hand_observations_gained']} one-hand observations, introduced
{result['new_zero_hand_false_positive_frames']} new zero-hand false-positive frames and
{result['new_rest_false_positive_frames']} new rest false-positive frames. R1 rescues:
{result['r1_rescues']}; R2 rescues: {result['r2_rescues']}.

Final gates: `{json.dumps(result['final_gates'], sort_keys=True)}`. All passed:
**{result['all_final_gates_passed']}**.

## Scope limits and decision

The fresh set has zero WEAK one-hand labels and no positive optional blur, occlusion, or contact
labels. This result therefore cannot claim weak-hand, blur, occlusion, or contact robustness.
`{result['classification']}` concerns eligibility only; it does not establish recognition,
representation, Android, or runtime readiness. P4-B was not started. No Android, S4-S7, S6,
recognition, Sapiens, fine-tuning, z fabrication, or threshold sweep occurred.
"""
    (OUTPUT / "P4A2_HIGH_RECALL_RESCUE_FINAL_RESULT.md").write_text(report, encoding="utf-8")


def create_hash_manifest() -> None:
    paths = sorted(path for path in OUTPUT.rglob("*") if path.is_file() and path.name != "provenance_hash_manifest.json")
    write_json(OUTPUT / "provenance_hash_manifest.json", {
        "files": [{"path": str(path.relative_to(OUTPUT)), "sha256": sha256(path), "bytes": path.stat().st_size} for path in paths]
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "baseline", "diagnose", "freeze-r1", "select", "final"))
    args = parser.parse_args()
    actions: dict[str, Callable[[], dict[str, Any]]] = {
        "prepare": prepare, "baseline": baseline, "diagnose": diagnose_development,
        "freeze-r1": freeze_r1_candidates, "select": select_candidate, "final": final_evaluation,
    }
    result = actions[args.command]()
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
