"""Governed P6-B fixture preparation and ONNX Runtime semantic-parity audit.

This module performs perception/feature parity only. It never loads a
recognizer, accesses D10, trains, modifies V2, or changes P4/S5/S7.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.features.dwpose_representation_v2 import (
    BODY_INDICES,
    LEFT_HAND_INDICES,
    RIGHT_HAND_INDICES,
    build_frame_features,
    normalization_from_body,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/recognition_upgrade/p6b_v2_backend_feasibility_prototype_01"
P2A = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_linux_01"
P2A_MANIFEST = P2A / "frozen_input_manifest_350.csv"
P2A_GOLD = P2A / "dwpose_gold_hand_results.csv"
P2A_RAW = P2A / "raw_outputs"
CONFIG = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/toolchain/source_snapshot/mmpose/configs/wholebody_2d_keypoint/rtmpose/ubody/rtmpose-l_8xb64-270e_coco-ubody-wholebody-256x192.py"
CHECKPOINT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/checkpoint/dw-ll_ucoco.pth"
P6A = ROOT / "artifacts/recognition_upgrade/p6a_production_runtime_compatibility_audit_01"
D12 = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5d12_future_version_evidence_synthesis_01"
PROGRESS = ROOT / "context/progress-tracker.md"
EXPECTED_CHECKPOINT_SHA = "e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7"
EXPECTED_CONFIG_SHA = "b2e741d2428667c99e74218f5170a183337602755c76e5b4138546a9b59d5032"
SCORE_THRESHOLD = np.float32(0.30)
MIN_HAND_POINTS = 11
MEAN = np.asarray([123.675, 116.28, 103.53], np.float32).reshape(3, 1, 1)
STD = np.asarray([58.395, 57.12, 57.375], np.float32).reshape(3, 1, 1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def deterministic_order(category: str, row: dict[str, str]) -> str:
    key = f"P6B_GOLDEN_FIXTURE_V1|{category}|{row['manifest_row_id']}|{row['sha256']}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def raw_path(row: dict[str, str]) -> Path:
    return P2A_RAW / f"{row['manifest_row_id']}.npz"


def prepare() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    identity = {"checkpoint_sha256": sha256(CHECKPOINT), "config_sha256": sha256(CONFIG)}
    if identity != {"checkpoint_sha256": EXPECTED_CHECKPOINT_SHA, "config_sha256": EXPECTED_CONFIG_SHA}:
        raise RuntimeError(f"P6B_FROZEN_MODEL_IDENTITY_MISMATCH: {identity}")

    manifest = read_csv(P2A_MANIFEST)
    gold_counts: dict[str, int] = {}
    for row in read_csv(P2A_GOLD):
        gold_counts[row["sample_id"]] = gold_counts.get(row["sample_id"], 0) + 1
    categories: dict[str, list[dict[str, str]]] = {"ZERO": [], "ONE": [], "TWO": []}
    for row in manifest:
        if row["benchmark_type"] == "NEGATIVE_GOLD_V1":
            categories["ZERO"].append(row)
        elif row["benchmark_type"] == "POSITIVE_GOLD" and gold_counts.get(row["sample_id"]) in (1, 2):
            categories["ONE" if gold_counts[row["sample_id"]] == 1 else "TWO"].append(row)
    selected: list[tuple[str, dict[str, str]]] = []
    for category in ("ZERO", "ONE", "TWO"):
        ordered = sorted(categories[category], key=lambda row: deterministic_order(category, row))
        if len(ordered) < 16:
            raise RuntimeError(f"insufficient governed {category} fixtures: {len(ordered)}")
        selected.extend((category, row) for row in ordered[:16])

    fixture_rows: list[dict[str, Any]] = []
    keypoints_values, score_values, body_values, lh_values, rh_values = [], [], [], [], []
    centers, scales, valid_masks, observed_values, v2_values = [], [], [], [], []
    for index, (category, row) in enumerate(selected, start=1):
        source = Path(row["source_path_original"])
        native = raw_path(row)
        if not source.is_file() or sha256(source) != row["sha256"]:
            raise RuntimeError(f"fixture source integrity failure: {row['manifest_row_id']}")
        if not native.is_file():
            raise RuntimeError(f"missing frozen P2A output: {native}")
        data = np.load(native)
        keypoints = np.asarray(data["keypoints_133"], np.float32)
        scores = np.asarray(data["scores_133"], np.float32)
        if keypoints.shape != (133, 2) or scores.shape != (133,):
            raise RuntimeError(f"invalid P2A native shape: {row['manifest_row_id']}")
        presence = np.asarray([
            np.count_nonzero(scores[LEFT_HAND_INDICES] >= SCORE_THRESHOLD) >= MIN_HAND_POINTS,
            np.count_nonzero(scores[RIGHT_HAND_INDICES] >= SCORE_THRESHOLD) >= MIN_HAND_POINTS,
        ], dtype=bool)
        feature, diagnostic = build_frame_features(keypoints, scores, presence)
        structural_valid = np.all(np.isfinite(np.column_stack([keypoints, scores])), axis=1)
        keypoints_values.append(keypoints)
        score_values.append(scores)
        body_values.append(keypoints[BODY_INDICES])
        lh_values.append(keypoints[LEFT_HAND_INDICES])
        rh_values.append(keypoints[RIGHT_HAND_INDICES])
        centers.append([diagnostic.center_x, diagnostic.center_y])
        scales.append(diagnostic.scale)
        valid_masks.append(structural_valid)
        observed_values.append([bool(feature[236]), bool(feature[237])])
        v2_values.append(feature)
        fixture_rows.append({
            "fixture_index": index,
            "fixture_id": row["manifest_row_id"],
            "visibility_category": category,
            "governed_visible_hand_count": {"ZERO": 0, "ONE": 1, "TWO": 2}[category],
            "benchmark_type": row["benchmark_type"],
            "source_sample_id": row["sample_id"],
            "source_path": str(source.resolve()),
            "source_sha256": row["sha256"],
            "image_width": row["image_width"],
            "image_height": row["image_height"],
            "oracle_native_path": str(native.resolve()),
            "oracle_native_sha256": sha256(native),
            "selection_key_sha256": deterministic_order(category, row),
            "source_governance": "P2A_FROZEN_DEVELOPMENT_PERCEPTION_FIXTURE",
        })
    fixture_path = OUT / "p6b_golden_fixture_manifest.csv"
    write_csv(fixture_path, list(fixture_rows[0]), fixture_rows)

    np.savez_compressed(
        OUT / "p6b_offline_oracle_outputs.npz",
        fixture_ids=np.asarray([row["fixture_id"] for row in fixture_rows]),
        categories=np.asarray([row["visibility_category"] for row in fixture_rows]),
        source_sha256=np.asarray([row["source_sha256"] for row in fixture_rows]),
        keypoints_133=np.stack(keypoints_values).astype(np.float32),
        scores_133=np.stack(score_values).astype(np.float32),
        body_xy=np.stack(body_values).astype(np.float32),
        left_hand_xy=np.stack(lh_values).astype(np.float32),
        right_hand_xy=np.stack(rh_values).astype(np.float32),
        normalization_center=np.asarray(centers, np.float64),
        normalization_scale=np.asarray(scales, np.float64),
        point_valid_mask_133=np.stack(valid_masks).astype(bool),
        observed_flags=np.asarray(observed_values, bool),
        v2_features=np.stack(v2_values).astype(np.float32),
    )

    backend_identity = {
        "backend": "DWPose-L",
        "config": CONFIG.name,
        "config_sha256": identity["config_sha256"],
        "checkpoint": CHECKPOINT.name,
        "checkpoint_sha256": identity["checkpoint_sha256"],
        "checkpoint_bytes": CHECKPOINT.stat().st_size,
        "whole_body_points": 133,
        "body_indices": [0, 16],
        "left_hand_indices": [91, 111],
        "right_hand_indices": [112, 132],
        "native_values": ["x", "y", "score"],
        "precision": "FP32",
        "verified": True,
    }
    write_json(OUT / "p6b_frozen_backend_identity.json", backend_identity)
    oracle_contract = {
        "status": "RECOVERED",
        "input_decode": "OpenCV BGR source image; EXIF is not separately applied",
        "orientation": "source pixels as stored in governed fixture",
        "person_roi": "single full-frame xyxy [0,0,width,height]; no detector",
        "bbox_center_scale": "center=(x1+x2,y1+y2)/2; scale=(x2-x1,y2-y1)*1.25",
        "aspect_ratio": "scale fixed to 192/256 before affine",
        "affine": "MMPose get_warp_matrix, rotation=0, cv2.INTER_LINEAR, output 192x256",
        "color": "BGR to RGB",
        "normalization": {"mean": [123.675, 116.28, 103.53], "std": [58.395, 57.12, 57.375]},
        "network_input": [1, 3, 256, 192],
        "test_time_augmentation": "horizontal input flip; 133 flip-index reorder; reverse SimCC-x; arithmetic mean logits",
        "network_outputs": {"simcc_x": [1, 133, 384], "simcc_y": [1, 133, 512]},
        "decoder": "argmax each SimCC axis; score=min(axis maxima); nonpositive score coordinate=-1; coordinates divided by split ratio 2.0",
        "source_restore": "input-space coordinate/input_size*bbox_scale+bbox_center-0.5*bbox_scale",
        "point_order": "COCO-WholeBody 133; body 0..16, LH 91..111, RH 112..132",
        "downstream_v2": "pipeline/features/dwpose_representation_v2.py unchanged",
        "new_detector": False,
        "reproducible": True,
    }
    write_json(OUT / "p6b_offline_oracle_contract.json", oracle_contract)
    parity_contract = {
        "schema": "P6B_FP32_PARITY_CONTRACT_V1",
        "frozen_before_candidate_evaluation": True,
        "fixture_manifest_sha256": sha256(fixture_path),
        "fixture_count": len(fixture_rows),
        "composition": {category: 16 for category in ("ZERO", "ONE", "TWO")},
        "exact": {
            "point_count": 133,
            "anatomical_index_ordering": "100_PERCENT",
            "left_right_slot_mapping": "100_PERCENT",
            "point_valid_mask": "100_PERCENT",
            "left_observed": "100_PERCENT",
            "right_observed": "100_PERCENT",
            "padding_missingness": "100_PERCENT",
            "final_v2_layout": "100_PERCENT",
        },
        "numeric": {
            "native_score_max_abs_error": 1e-4,
            "decoded_xy_median_abs_error_source_pixels": 0.05,
            "decoded_xy_max_abs_error_source_pixels": 0.5,
            "normalization_center_max_abs_error_source_pixels": 0.5,
            "normalization_scale_max_relative_error": 1e-4,
            "final_v2_mean_abs_error": 1e-5,
            "final_v2_max_abs_error": 1e-3,
        },
        "observed_threshold": {"score": 0.30, "minimum_of_21": 11, "any_flag_change_is_failure": True},
        "tolerance_source": "No repository-governed cross-runtime DWPose FP32 standard was found; P6-B preregistered defaults adopted before candidate results.",
        "may_widen_after_results": False,
    }
    parity_path = OUT / "p6b_parity_contract.json"
    write_json(parity_path, parity_contract)
    print(json.dumps({
        "prepared": True,
        "fixtures": len(fixture_rows),
        "composition": parity_contract["composition"],
        "membership_sha256": sha256(fixture_path),
        "parity_contract_sha256": sha256(parity_path),
        "oracle_sha256": sha256(OUT / "p6b_offline_oracle_outputs.npz"),
    }, indent=2))
    return 0


def get_warp_matrix(center: np.ndarray, scale: np.ndarray) -> np.ndarray:
    src_w = float(scale[0])
    dst_w, dst_h = 192.0, 256.0
    src = np.zeros((3, 2), np.float32)
    src[0] = center
    src[1] = center + np.asarray([0.0, -0.5 * src_w], np.float32)
    src[2] = np.asarray([src[1, 0] - (src[0, 1] - src[1, 1]), src[1, 1] + (src[0, 0] - src[1, 0])], np.float32)
    dst = np.zeros((3, 2), np.float32)
    dst[0] = [dst_w * 0.5, dst_h * 0.5]
    dst[1] = [dst_w * 0.5, dst_h * 0.5 - dst_w * 0.5]
    dst[2] = np.asarray([dst[1, 0] - (dst[0, 1] - dst[1, 1]), dst[1, 1] + (dst[0, 0] - dst[1, 0])], np.float32)
    return cv2.getAffineTransform(src, dst)


def preprocess(source: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"cannot decode fixture {source}")
    height, width = image.shape[:2]
    center = np.asarray([width * 0.5, height * 0.5], np.float32)
    scale = np.asarray([width * 1.25, height * 1.25], np.float32)
    aspect = 192.0 / 256.0
    if scale[0] > scale[1] * aspect:
        scale[1] = scale[0] / aspect
    else:
        scale[0] = scale[1] * aspect
    warp = get_warp_matrix(center, scale)
    crop = cv2.warpAffine(image, warp, (192, 256), flags=cv2.INTER_LINEAR)
    rgb_chw = crop[:, :, ::-1].transpose(2, 0, 1).astype(np.float32)
    value = ((rgb_chw - MEAN) / STD)[None]
    return np.ascontiguousarray(value, np.float32), center, scale


def decode(simcc_x: np.ndarray, simcc_y: np.ndarray, center: np.ndarray, scale: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(simcc_x, np.float32).reshape(133, 384)
    y = np.asarray(simcc_y, np.float32).reshape(133, 512)
    x_locs = np.argmax(x, axis=1)
    y_locs = np.argmax(y, axis=1)
    points = np.stack([x_locs, y_locs], axis=-1).astype(np.float32)
    scores = np.minimum(np.max(x, axis=1), np.max(y, axis=1)).astype(np.float32)
    points[scores <= 0] = -1
    points /= np.float32(2.0)
    points = points / np.asarray([192.0, 256.0], np.float32) * scale + center - np.float32(0.5) * scale
    return points.astype(np.float32), scores


def evaluate(onnx_path: Path) -> int:
    import onnxruntime as ort

    parity_path = OUT / "p6b_parity_contract.json"
    fixture_path = OUT / "p6b_golden_fixture_manifest.csv"
    oracle_path = OUT / "p6b_offline_oracle_outputs.npz"
    export_manifest_path = OUT / "p6b_runtime_export_manifest.json"
    if not all(path.is_file() for path in (parity_path, fixture_path, oracle_path, export_manifest_path, onnx_path)):
        raise RuntimeError("P6B preparation/export artifacts are incomplete")
    contract_hash_before = sha256(parity_path)
    contract = json.loads(parity_path.read_text(encoding="utf-8"))
    export = json.loads(export_manifest_path.read_text(encoding="utf-8"))
    if export["onnx_sha256"] != sha256(onnx_path):
        raise RuntimeError("export manifest ONNX hash mismatch")
    fixtures = read_csv(fixture_path)
    oracle = np.load(oracle_path)
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    if [item.name for item in session.get_inputs()] != ["input"]:
        raise RuntimeError("unexpected ONNX input contract")
    raw_rows, v2_rows, observed_rows = [], [], []
    all_pass = True
    for index, row in enumerate(fixtures):
        value, center, scale = preprocess(Path(row["source_path"]))
        simcc_x, simcc_y = session.run(["simcc_x", "simcc_y"], {"input": value})
        points, scores = decode(simcc_x, simcc_y, center, scale)
        oracle_points = oracle["keypoints_133"][index]
        oracle_scores = oracle["scores_133"][index]
        presence = np.asarray([
            np.count_nonzero(scores[LEFT_HAND_INDICES] >= SCORE_THRESHOLD) >= MIN_HAND_POINTS,
            np.count_nonzero(scores[RIGHT_HAND_INDICES] >= SCORE_THRESHOLD) >= MIN_HAND_POINTS,
        ], bool)
        feature, diagnostic = build_frame_features(points, scores, presence)
        point_valid = np.all(np.isfinite(np.column_stack([points, scores])), axis=1)
        oracle_feature = oracle["v2_features"][index]
        oracle_valid = oracle["point_valid_mask_133"][index]
        oracle_observed = oracle["observed_flags"][index]
        xy_error = np.abs(points.astype(np.float64) - oracle_points.astype(np.float64))
        score_error = np.abs(scores.astype(np.float64) - oracle_scores.astype(np.float64))
        v2_error = np.abs(feature.astype(np.float64) - oracle_feature.astype(np.float64))
        center_error = float(np.max(np.abs(np.asarray([diagnostic.center_x, diagnostic.center_y]) - oracle["normalization_center"][index])))
        scale_rel_error = float(abs(diagnostic.scale - oracle["normalization_scale"][index]) / max(abs(float(oracle["normalization_scale"][index])), 1e-12))
        raw_pass = bool(
            float(np.max(score_error)) <= contract["numeric"]["native_score_max_abs_error"]
            and float(np.median(xy_error)) <= contract["numeric"]["decoded_xy_median_abs_error_source_pixels"]
            and float(np.max(xy_error)) <= contract["numeric"]["decoded_xy_max_abs_error_source_pixels"]
        )
        exact_pass = bool(np.array_equal(point_valid, oracle_valid) and np.array_equal(presence & diagnostic.success, oracle_observed))
        v2_pass = bool(
            float(np.mean(v2_error)) <= contract["numeric"]["final_v2_mean_abs_error"]
            and float(np.max(v2_error)) <= contract["numeric"]["final_v2_max_abs_error"]
            and center_error <= contract["numeric"]["normalization_center_max_abs_error_source_pixels"]
            and scale_rel_error <= contract["numeric"]["normalization_scale_max_relative_error"]
            and exact_pass
        )
        all_pass = all_pass and raw_pass and v2_pass
        max_xy_flat = int(np.argmax(xy_error))
        max_xy_point, max_xy_axis = np.unravel_index(max_xy_flat, xy_error.shape)
        semantic_block = "BODY" if max_xy_point <= 16 else "FOOT" if max_xy_point <= 22 else "FACE" if max_xy_point <= 90 else "LEFT_HAND" if max_xy_point <= 111 else "RIGHT_HAND"
        raw_rows.append({"fixture_id": row["fixture_id"], "category": row["visibility_category"], "point_count_exact": points.shape == (133, 2), "score_max_abs_error": float(np.max(score_error)), "xy_median_abs_error_pixels": float(np.median(xy_error)), "xy_max_abs_error_pixels": float(np.max(xy_error)), "max_xy_point_index": int(max_xy_point), "max_xy_axis": "x" if max_xy_axis == 0 else "y", "max_xy_semantic_block": semantic_block, "pass": raw_pass})
        v2_rows.append({"fixture_id": row["fixture_id"], "category": row["visibility_category"], "normalization_center_max_abs_error_pixels": center_error, "normalization_scale_relative_error": scale_rel_error, "v2_mean_abs_error": float(np.mean(v2_error)), "v2_max_abs_error": float(np.max(v2_error)), "pass": v2_pass})
        observed_rows.append({"fixture_id": row["fixture_id"], "category": row["visibility_category"], "valid_mask_exact": bool(np.array_equal(point_valid, oracle_valid)), "oracle_lh_observed": bool(oracle_observed[0]), "candidate_lh_observed": bool(presence[0] and diagnostic.success), "oracle_rh_observed": bool(oracle_observed[1]), "candidate_rh_observed": bool(presence[1] and diagnostic.success), "observed_exact": bool(np.array_equal(presence & diagnostic.success, oracle_observed)), "pass": exact_pass})
    write_csv(OUT / "p6b_raw_output_parity.csv", list(raw_rows[0]), raw_rows)
    write_csv(OUT / "p6b_v2_feature_parity.csv", list(v2_rows[0]), v2_rows)
    write_csv(OUT / "p6b_observed_validity_parity.csv", list(observed_rows[0]), observed_rows)
    operator_rows = [{"operator": operator, "onnxruntime_desktop_load": "PASS", "android_full_package_support": "TO_BE_VERIFIED_ON_DEVICE", "custom_operator": "NO" if operator.startswith("ai.onnx::") else "REVIEW"} for operator in export["operators"]]
    write_csv(OUT / "p6b_operator_support.csv", list(operator_rows[0]), operator_rows)
    contract_hash_after = sha256(parity_path)
    result = {
        "gate_a_pass": all_pass and contract_hash_before == contract_hash_after,
        "runtime": "ONNX_RUNTIME_MOBILE_ANDROID_FP32",
        "desktop_reference_runtime_version": ort.__version__,
        "execution_provider": "CPUExecutionProvider",
        "fixtures": len(fixtures),
        "raw_topology": "PASS" if all(bool(row["point_count_exact"]) for row in raw_rows) else "FAIL",
        "hand_slots": "PASS" if all(bool(row["observed_exact"]) for row in observed_rows) else "FAIL",
        "decoded_xy": "PASS" if all(float(row["xy_median_abs_error_pixels"]) <= contract["numeric"]["decoded_xy_median_abs_error_source_pixels"] and float(row["xy_max_abs_error_pixels"]) <= contract["numeric"]["decoded_xy_max_abs_error_source_pixels"] for row in raw_rows) else "FAIL",
        "scores": "PASS" if all(float(row["score_max_abs_error"]) <= contract["numeric"]["native_score_max_abs_error"] for row in raw_rows) else "FAIL",
        "valid_masks": "PASS" if all(bool(row["valid_mask_exact"]) for row in observed_rows) else "FAIL",
        "observed_flags": "PASS" if all(bool(row["observed_exact"]) for row in observed_rows) else "FAIL",
        "normalization": "PASS" if all(float(row["normalization_center_max_abs_error_pixels"]) <= contract["numeric"]["normalization_center_max_abs_error_source_pixels"] and float(row["normalization_scale_relative_error"]) <= contract["numeric"]["normalization_scale_max_relative_error"] for row in v2_rows) else "FAIL",
        "final_v2": "PASS" if all(bool(row["pass"]) for row in v2_rows) else "FAIL",
        "parity_contract_sha256_before": contract_hash_before,
        "parity_contract_sha256_after": contract_hash_after,
        "parity_contract_changed_after_results": contract_hash_before != contract_hash_after,
        "summary": {
            "score_max_abs_error": max(float(row["score_max_abs_error"]) for row in raw_rows),
            "xy_median_abs_error_pixels_max_fixture": max(float(row["xy_median_abs_error_pixels"]) for row in raw_rows),
            "xy_max_abs_error_pixels": max(float(row["xy_max_abs_error_pixels"]) for row in raw_rows),
            "v2_mean_abs_error_max_fixture": max(float(row["v2_mean_abs_error"]) for row in v2_rows),
            "v2_max_abs_error": max(float(row["v2_max_abs_error"]) for row in v2_rows),
        },
    }
    write_json(OUT / "p6b_gate_a_result.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["gate_a_pass"] else 3


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    evaluate_parser = sub.add_parser("evaluate")
    evaluate_parser.add_argument("--onnx", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        return prepare()
    return evaluate(args.onnx)


if __name__ == "__main__":
    raise SystemExit(main())
