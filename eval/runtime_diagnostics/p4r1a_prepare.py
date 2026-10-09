"""Prepare the frozen P4-R1A residual/control and interaction-ROI package.

This module does not load or run a perception model.  It derives every input
from governed V2 truth plus the already-frozen native DWPose outputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement"
OUT = BASE / "p4r1a_rtmpose_hand5_targeted_recovery_01"
V2 = BASE / "p4gt1r_schema_repair_v2_01/P4_ELIGIBILITY_TRUTH_V2.csv"
V2_SHA256 = "24f5d8d442702e3a27424ff7f55cc24f1338f5683e5988a6a4916557e1d4252d"
P4C3A = BASE / "p4c3a_raw_dwpose_failure_decomposition_01"
P4C3B = BASE / "p4c3b_physical_instance_validation_01"
P4A2 = BASE / "p4a2_high_recall_rescue_final_01"
CONTROL_SEED = "P4R1A_CONTROL_SAMPLE_V1_20260825"

BODY_ARM_INDICES = (5, 6, 7, 8, 9, 10)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"P4R1A_EMPTY_OUTPUT:{path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
    tmp.replace(path)


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
    tmp.replace(path)


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


def stable_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def diversity_sample(rows: list[dict[str, str]], count: int, label: str) -> list[dict[str, str]]:
    if len(rows) < count:
        raise RuntimeError(f"P4R1A_CONTROL_POOL_TOO_SMALL:{label}:{len(rows)}")
    remaining = list(rows)
    signer_counts: Counter[str] = Counter()
    sequence_counts: Counter[str] = Counter()
    selected: list[dict[str, str]] = []
    while len(selected) < count:
        row = min(
            remaining,
            key=lambda item: (
                sequence_counts[item["sequence_id"]],
                signer_counts[item["signer_id"]],
                stable_hash(CONTROL_SEED, label, item["frame_id"]),
            ),
        )
        selected.append(row)
        remaining.remove(row)
        signer_counts[row["signer_id"]] += 1
        sequence_counts[row["sequence_id"]] += 1
    return selected


def interaction_roi(keypoints: np.ndarray, gated: np.ndarray, width: int, height: int) -> dict[str, Any]:
    body = keypoints[list(BODY_ARM_INDICES)]
    finite_body = body[np.isfinite(body).all(axis=1)]
    fallback = len(finite_body) < 4

    shoulders = keypoints[[5, 6]]
    shoulder_scale = float("nan")
    if np.isfinite(shoulders).all():
        shoulder_scale = float(np.linalg.norm(shoulders[0] - shoulders[1]))
    scale_floor = 0.20 * min(width, height)
    body_scale = max(shoulder_scale, scale_floor) if math.isfinite(shoulder_scale) else scale_floor
    if body_scale <= 0 or not math.isfinite(body_scale):
        fallback = True

    if fallback:
        return {
            "roi_x1": 0,
            "roi_y1": 0,
            "roi_x2": width,
            "roi_y2": height,
            "roi_rule": "FALLBACK_WHOLE_FRAME_INSUFFICIENT_BODY_GEOMETRY",
            "body_scale_px": body_scale,
            "finite_body_arm_points": int(len(finite_body)),
        }

    anchors: list[np.ndarray] = [finite_body]
    # Keep every finite native point: it is runtime-available search evidence,
    # not a claim that the hand exists. Qualified groups are recorded separately.
    for start in (91, 112):
        points = keypoints[start : start + 21]
        points = points[np.isfinite(points).all(axis=1)]
        if len(points):
            anchors.append(points)
    merged = np.concatenate(anchors, axis=0)
    merged[:, 0] = np.clip(merged[:, 0], 0, width)
    merged[:, 1] = np.clip(merged[:, 1], 0, height)
    low = merged.min(axis=0)
    high = merged.max(axis=0)
    margin = 0.50 * body_scale
    desired_side = max(float(high[0] - low[0] + 2 * margin), float(high[1] - low[1] + 2 * margin), 2.5 * body_scale)
    desired_side = min(desired_side, float(max(width, height)))
    center = (low + high) / 2.0
    x1 = center[0] - desired_side / 2.0
    y1 = center[1] - desired_side / 2.0
    x2 = x1 + desired_side
    y2 = y1 + desired_side
    if x1 < 0:
        x2 -= x1
        x1 = 0.0
    if y1 < 0:
        y2 -= y1
        y1 = 0.0
    if x2 > width:
        x1 -= x2 - width
        x2 = float(width)
    if y2 > height:
        y1 -= y2 - height
        y2 = float(height)
    x1, y1 = max(0.0, x1), max(0.0, y1)
    return {
        "roi_x1": int(math.floor(x1)),
        "roi_y1": int(math.floor(y1)),
        "roi_x2": int(math.ceil(x2)),
        "roi_y2": int(math.ceil(y2)),
        "roi_rule": "PRIMARY_CURRENT_FRAME_DWPOSE_INTERACTION_ENVELOPE",
        "body_scale_px": body_scale,
        "finite_body_arm_points": int(len(finite_body)),
        "dwpose_gated_left": bool(gated[0]),
        "dwpose_gated_right": bool(gated[1]),
    }


def prepare() -> None:
    required = [
        V2,
        P4C3A / "p4c3a_missing_hand_classification.csv",
        P4C3B / "p4c3b_raw_A_inventory.csv",
        P4C3B / "p4c3b_raw_A_visual_validation.csv",
        P4A2 / "p4a2_frozen_inference_manifest.csv",
    ]
    if any(not path.is_file() for path in required) or sha256(V2) != V2_SHA256:
        raise RuntimeError("P4R1A_SOURCE_INTEGRITY_FAILURE")

    v2_rows = read_csv(V2)
    if len(v2_rows) != 458 or len({row["frame_id"] for row in v2_rows}) != 458:
        raise RuntimeError("P4R1A_SOURCE_INTEGRITY_FAILURE")
    v2_by_id = {row["frame_id"]: row for row in v2_rows}
    inference_rows = read_csv(P4A2 / "p4a2_frozen_inference_manifest.csv")
    inference_by_id = {row["annotation_row_id"]: row for row in inference_rows}
    if len(inference_by_id) != 458:
        raise RuntimeError("P4R1A_SOURCE_INTEGRITY_FAILURE")

    missing_rows = read_csv(P4C3A / "p4c3a_missing_hand_classification.csv")
    if len(missing_rows) != 25:
        raise RuntimeError(f"P4R1A_RESIDUAL_RECONCILIATION_FAILURE:missing={len(missing_rows)}")
    raw_inventory = {row["item_id"]: row for row in read_csv(P4C3B / "p4c3b_raw_A_inventory.csv")}
    validated = read_csv(P4C3B / "p4c3b_raw_A_visual_validation.csv")
    recovered = {
        (raw_inventory[row["item_id"]]["frame_id"], raw_inventory[row["item_id"]]["missing_anatomical_side"])
        for row in validated
        if row["review_label"] == "MISSING_REAL_HAND" and row["reviewer_status"] == "COMPLETE"
    }
    if len(recovered) != 7:
        raise RuntimeError(f"P4R1A_RESIDUAL_RECONCILIATION_FAILURE:validated={len(recovered)}")
    residual = [row for row in missing_rows if (row["frame_id"], row["anatomical_side"]) not in recovered]
    if len(residual) != 18:
        raise RuntimeError(f"P4R1A_RESIDUAL_RECONCILIATION_FAILURE:residual={len(residual)}")

    # Enrich V2 rows with frozen native output identity and gate status.
    enriched: list[dict[str, str]] = []
    for truth in v2_rows:
        inf = inference_by_id[truth["frame_id"]]
        image_path = resolve_project_path(inf["image_path"])
        native_path = resolve_project_path(inf["raw_relative_path"])
        if not image_path.is_file() or not native_path.is_file():
            raise RuntimeError(f"P4R1A_SOURCE_INTEGRITY_FAILURE:{truth['frame_id']}")
        if sha256(image_path) != truth["source_sha256"] or truth["source_sha256"] != inf["image_sha256"]:
            raise RuntimeError(f"P4R1A_SOURCE_INTEGRITY_FAILURE:{truth['frame_id']}")
        with np.load(native_path, allow_pickle=False) as native:
            internal_sha = str(native["source_sha256"].item())
            gated = native["gated_presence"].astype(bool)
        if internal_sha != truth["source_sha256"]:
            raise RuntimeError(f"P4R1A_SOURCE_INTEGRITY_FAILURE:{truth['frame_id']}")
        enriched.append(
            {
                **truth,
                "native_output_path": str(native_path),
                "native_output_sha256": sha256(native_path),
                "dwpose_gated_left": "YES" if gated[0] else "NO",
                "dwpose_gated_right": "YES" if gated[1] else "NO",
            }
        )

    zero_pool = [row for row in enriched if row["visible_hand_count"] == "ZERO"]
    one_pool = [
        row
        for row in enriched
        if row["visible_hand_count"] == "ONE" and row["one_hand_ownership"] in {"LEFT", "RIGHT"}
    ]
    two_complete_pool = [
        row
        for row in enriched
        if row["visible_hand_count"] == "TWO"
        and row["dwpose_gated_left"] == "YES"
        and row["dwpose_gated_right"] == "YES"
    ]
    controls = (
        [("ZERO_CONTROL", row) for row in diversity_sample(zero_pool, 40, "ZERO")]
        + [("ONE_CONTROL", row) for row in diversity_sample(one_pool, 40, "ONE")]
        + [("TWO_CONTROL", row) for row in diversity_sample(two_complete_pool, 40, "TWO")]
    )

    residual_by_key = {(row["frame_id"], row["anatomical_side"]): row for row in residual}
    selected_ids = {row["frame_id"] for row in residual}
    selected_ids.update(row["frame_id"] for _, row in controls)
    roi_by_id: dict[str, dict[str, Any]] = {}
    for frame_id in sorted(selected_ids):
        truth = next(row for row in enriched if row["frame_id"] == frame_id)
        image = cv2.imread(truth["source_image_path"])
        if image is None:
            raise RuntimeError(f"P4R1A_SOURCE_INTEGRITY_FAILURE:{frame_id}")
        with np.load(truth["native_output_path"], allow_pickle=False) as native:
            roi = interaction_roi(native["keypoints_133"].copy(), native["gated_presence"], image.shape[1], image.shape[0])
        roi_by_id[frame_id] = roi

    residual_manifest: list[dict[str, Any]] = []
    for miss in residual:
        truth = next(row for row in enriched if row["frame_id"] == miss["frame_id"])
        residual_manifest.append(
            {
                "residual_id": "P4R1A_RESIDUAL_" + stable_hash(miss["frame_id"], miss["anatomical_side"])[:24],
                "frame_id": miss["frame_id"],
                "signer_id": miss["signer_id"],
                "sequence_id": miss["sequence_id"],
                "frame_index": miss["frame_index"],
                "missing_anatomical_side": miss["anatomical_side"],
                "visible_hand_count": truth["visible_hand_count"],
                "source_image_path": truth["source_image_path"],
                "source_sha256": truth["source_sha256"],
                "native_output_path": truth["native_output_path"],
                "native_output_sha256": truth["native_output_sha256"],
                "p4c3a_primary_category": miss["primary_category"],
                **roi_by_id[miss["frame_id"]],
            }
        )
    control_manifest: list[dict[str, Any]] = []
    for control_type, truth in controls:
        control_manifest.append(
            {
                "control_id": "P4R1A_CONTROL_" + stable_hash(control_type, truth["frame_id"])[:24],
                "control_type": control_type,
                "frame_id": truth["frame_id"],
                "signer_id": truth["signer_id"],
                "sequence_id": truth["sequence_id"],
                "frame_index": truth["frame_index"],
                "visible_hand_count": truth["visible_hand_count"],
                "one_hand_ownership": truth["one_hand_ownership"],
                "source_image_path": truth["source_image_path"],
                "source_sha256": truth["source_sha256"],
                "native_output_path": truth["native_output_path"],
                "native_output_sha256": truth["native_output_sha256"],
                "dwpose_gated_left": truth["dwpose_gated_left"],
                "dwpose_gated_right": truth["dwpose_gated_right"],
                **roi_by_id[truth["frame_id"]],
            }
        )

    OUT.mkdir(parents=True, exist_ok=True)
    atomic_csv(OUT / "p4r1a_residual_18_manifest.csv", residual_manifest)
    atomic_csv(OUT / "p4r1a_control_manifest.csv", control_manifest)
    atomic_json(
        OUT / "p4r1a_roi_protocol.json",
        {
            "identity": "P4R1A_CURRENT_FRAME_DWPOSE_INTERACTION_ROI_V1",
            "frozen_before_rtmpose_inference": True,
            "primary": {
                "anchors": "finite DWPose body shoulders/elbows/wrists plus both native 21-point hand blocks",
                "body_scale": "max(finite shoulder distance, 0.20 * min(frame width, frame height))",
                "margin_each_side": "0.50 * body_scale",
                "minimum_square_side": "2.50 * body_scale",
                "clamp": "shift then clamp to source frame",
            },
            "fallback": "whole frame only when fewer than four body arm points are finite or body scale is invalid",
            "forbidden_inputs": [
                "V2 visibility truth coordinates",
                "human hand boxes",
                "previous/future frames",
                "MediaPipe/WiLoR",
                "recognition output",
            ],
            "no_parameter_sweep": True,
        },
    )
    atomic_json(
        OUT / "p4r1a_prepare_result.json",
        {
            "status": "P4R1A_INPUTS_AND_ROI_FROZEN",
            "v2_sha256": sha256(V2),
            "v2_rows": len(v2_rows),
            "p4c3a_missing": len(missing_rows),
            "p4c3b_independent_recoveries_excluded": len(recovered),
            "residual_rows": len(residual_manifest),
            "control_counts": dict(Counter(row["control_type"] for row in control_manifest)),
            "unique_inference_frames": len(selected_ids),
            "control_seed": CONTROL_SEED,
            "manifests": {
                "residual": sha256(OUT / "p4r1a_residual_18_manifest.csv"),
                "controls": sha256(OUT / "p4r1a_control_manifest.csv"),
                "roi_protocol": sha256(OUT / "p4r1a_roi_protocol.json"),
            },
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare",))
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()


if __name__ == "__main__":
    main()
