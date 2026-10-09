"""Prospective P6B-R1 confirmation of the frozen V2 dependency closure.

P6-B remains immutable and failed. This module uses new, non-overlapping P2A
development fixtures and the unchanged P6-B ONNX graph/tolerances. It does
not run Android, recognition inference, training, D10, or pristine data.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from model.p6b_v2_backend_feasibility import decode, preprocess
from pipeline.features.dwpose_representation_v2 import (
    BODY_INDICES,
    LEFT_HAND_INDICES,
    RIGHT_HAND_INDICES,
    build_frame_features,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/recognition_upgrade/p6br1_v2_dependency_parity_confirmation_01"
P6B = ROOT / "artifacts/recognition_upgrade/p6b_v2_backend_feasibility_prototype_01"
P6A = ROOT / "artifacts/recognition_upgrade/p6a_production_runtime_compatibility_audit_01"
D12 = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5d12_future_version_evidence_synthesis_01"
P2A = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_linux_01"
P2A_MANIFEST = P2A / "frozen_input_manifest_350.csv"
P2A_GOLD = P2A / "dwpose_gold_hand_results.csv"
P2A_RAW = P2A / "raw_outputs"
ONNX = P6B / "frozen_dwpose_l_fp32.onnx"
CHECKPOINT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/checkpoint/dw-ll_ucoco.pth"
CONFIG = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/toolchain/source_snapshot/mmpose/configs/wholebody_2d_keypoint/rtmpose/ubody/rtmpose-l_8xb64-270e_coco-ubody-wholebody-256x192.py"
PROGRESS = ROOT / "context/progress-tracker.md"

EXPECTED_ONNX_SHA = "870c84ddbf396282c415854b233ba972a772ac35f1eebe26b6ce185a19579965"
EXPECTED_CHECKPOINT_SHA = "e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7"
EXPECTED_CONFIG_SHA = "b2e741d2428667c99e74218f5170a183337602755c76e5b4138546a9b59d5032"
EXPECTED_P6B_CONTRACT_SHA = "b569516613509e20fa4c2b609b801214d682d123628ab25d867f56db24da2b4a"
EXPECTED_P6B_FIXTURE_SHA = "f907b2f2f0a20d91719ea3ec5cc4b7837e94b5f0e43fcd8b2e77e0f1c82c6373"
SCORE_THRESHOLD = np.float32(0.30)
MIN_HAND_POINTS = 11
CONSUMED = np.concatenate([BODY_INDICES, LEFT_HAND_INDICES, RIGHT_HAND_INDICES])
UNUSED = np.asarray([index for index in range(133) if index not in set(CONSUMED.tolist())], np.int64)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(name: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty {name}")
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(name: str, value: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def resolve_source(original: str) -> tuple[Path, str]:
    source = Path(original)
    if source.is_file():
        return source, "ORIGINAL_GOVERNED_PATH"
    old_root = "F:\\ASL DATASET\\ASL CITIZEN\\ASL_Citizen"
    new_root = Path(r"G:\ASL CITIZEN\ASL CITIZEN\ASL_Citizen")
    if original.lower().startswith(old_root.lower()):
        candidate = new_root / original[len(old_root):].lstrip("\\/")
        if candidate.is_file():
            return candidate, "USER_RELOCATED_RAW_ROOT_PATH_TRANSLATION"
    raise FileNotFoundError(f"governed fixture source not found: {original}")


def verify_frozen() -> None:
    actual = {
        "onnx": sha(ONNX) if ONNX.is_file() else "MISSING",
        "checkpoint": sha(CHECKPOINT) if CHECKPOINT.is_file() else "MISSING",
        "config": sha(CONFIG) if CONFIG.is_file() else "MISSING",
        "p6b_contract": sha(P6B / "p6b_parity_contract.json"),
        "p6b_fixture": sha(P6B / "p6b_golden_fixture_manifest.csv"),
    }
    expected = {
        "onnx": EXPECTED_ONNX_SHA,
        "checkpoint": EXPECTED_CHECKPOINT_SHA,
        "config": EXPECTED_CONFIG_SHA,
        "p6b_contract": EXPECTED_P6B_CONTRACT_SHA,
        "p6b_fixture": EXPECTED_P6B_FIXTURE_SHA,
    }
    if actual != expected:
        raise RuntimeError(f"P6BR1_FROZEN_ONNX_ARTIFACT_UNAVAILABLE_OR_CHANGED: {actual}")


def selection_key(category: str, row: dict[str, str]) -> str:
    text = f"P6BR1_V2_DEPENDENCY_FIXTURE_V1|{category}|{row['manifest_row_id']}|{row['sha256']}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def prepare() -> int:
    verify_frozen()
    OUT.mkdir(parents=True, exist_ok=True)
    result_outputs = [
        "p6br1_v2_consumed_raw_parity.csv", "p6br1_valid_observed_parity.csv",
        "p6br1_normalization_parity.csv", "p6br1_final_v2_parity.csv",
        "p6br1_unused_point_descriptive_parity.csv", "p6br1_decision.json",
    ]
    if any((OUT / name).exists() for name in result_outputs):
        raise RuntimeError("candidate-result artifacts already exist; refusing to refreeze the prospective contract")

    contract = {
        "schema": "P6BR1_V2_DEPENDENCY_PARITY_CONTRACT_V1",
        "parent_gate": "P6B_SEMANTIC_PARITY_FAILED",
        "purpose": "PROSPECTIVE_V2_DEPENDENCY_CONFIRMATION",
        "original_p6b_reclassified": False,
        "full_133_structure_required": True,
        "full_133_numeric_xy_required": False,
        "numeric_xy_required_indices": ["0..16", "91..111", "112..132"],
        "numeric_xy_required_index_values": CONSUMED.tolist(),
        "unused_point_numeric_results": "DESCRIPTIVE_ONLY",
        "numeric_tolerances": {
            "identity": "IDENTICAL_TO_P6B",
            "native_score_max_absolute_error": 1e-4,
            "decoded_consumed_xy_median_absolute_error_pixels": 0.05,
            "decoded_consumed_xy_maximum_absolute_error_pixels": 0.5,
            "normalization_center_maximum_absolute_xy_error_pixels": 0.5,
            "normalization_scale_relative_error": 1e-4,
            "final_v2_mean_absolute_error": 1e-5,
            "final_v2_maximum_absolute_error": 1e-3,
            "valid_masks": "EXACT",
            "observed_flags": "EXACT",
            "hand_slot_mapping": "EXACT",
        },
        "same_onnx_sha256": EXPECTED_ONNX_SHA,
        "same_dwpose_checkpoint_sha256": EXPECTED_CHECKPOINT_SHA,
        "may_widen_after_results": False,
        "android_execution": False,
    }
    write_json("p6br1_v2_dependency_parity_contract.json", contract)

    original_rows = read_csv(P6B / "p6b_golden_fixture_manifest.csv")
    excluded_ids = {row["fixture_id"] for row in original_rows}
    excluded_hashes = {row["source_sha256"] for row in original_rows}
    manifest = read_csv(P2A_MANIFEST)
    gold_counts: dict[str, int] = {}
    for row in read_csv(P2A_GOLD):
        gold_counts[row["sample_id"]] = gold_counts.get(row["sample_id"], 0) + 1
    groups: dict[str, list[dict[str, str]]] = {"ZERO": [], "ONE": [], "TWO": []}
    for row in manifest:
        if row["manifest_row_id"] in excluded_ids or row["sha256"] in excluded_hashes:
            continue
        if row["benchmark_type"] == "NEGATIVE_GOLD_V1":
            groups["ZERO"].append(row)
        elif row["benchmark_type"] == "POSITIVE_GOLD" and gold_counts.get(row["sample_id"]) in (1, 2):
            groups["ONE" if gold_counts[row["sample_id"]] == 1 else "TWO"].append(row)
    selected: list[tuple[str, dict[str, str]]] = []
    for category in ("ZERO", "ONE", "TWO"):
        ordered = sorted(groups[category], key=lambda row: selection_key(category, row))
        if len(ordered) < 20:
            raise RuntimeError(f"maximum defensible {category} set below 20: {len(ordered)}")
        selected.extend((category, row) for row in ordered[:20])

    fixture_rows: list[dict[str, Any]] = []
    keypoints_values, scores_values, centers, scales, valid_values, observed_values, v2_values = [], [], [], [], [], [], []
    for ordinal, (category, row) in enumerate(selected, start=1):
        source, resolution = resolve_source(row["source_path_original"])
        if sha(source) != row["sha256"]:
            raise RuntimeError(f"fixture source hash mismatch: {row['manifest_row_id']}")
        native = P2A_RAW / f"{row['manifest_row_id']}.npz"
        if not native.is_file():
            raise RuntimeError(f"missing frozen native oracle: {native}")
        data = np.load(native)
        points = np.asarray(data["keypoints_133"], np.float32)
        scores = np.asarray(data["scores_133"], np.float32)
        presence = np.asarray([
            np.count_nonzero(scores[LEFT_HAND_INDICES] >= SCORE_THRESHOLD) >= MIN_HAND_POINTS,
            np.count_nonzero(scores[RIGHT_HAND_INDICES] >= SCORE_THRESHOLD) >= MIN_HAND_POINTS,
        ], bool)
        feature, diagnostic = build_frame_features(points, scores, presence)
        valid = np.all(np.isfinite(np.column_stack([points, scores])), axis=1)
        fixture_rows.append({
            "fixture_index": ordinal,
            "fixture_id": row["manifest_row_id"],
            "visibility_category": category,
            "governed_visible_hand_count": {"ZERO": 0, "ONE": 1, "TWO": 2}[category],
            "source_sample_id": row["sample_id"],
            "benchmark_type": row["benchmark_type"],
            "governed_source_path": row["source_path_original"],
            "resolved_source_path": str(source.resolve()),
            "path_resolution": resolution,
            "source_sha256": row["sha256"],
            "image_width": row["image_width"],
            "image_height": row["image_height"],
            "oracle_native_path": str(native.resolve()),
            "oracle_native_sha256": sha(native),
            "selection_key_sha256": selection_key(category, row),
            "source_governance": "P2A_FROZEN_DEVELOPMENT_PERCEPTION_FIXTURE",
        })
        keypoints_values.append(points); scores_values.append(scores)
        centers.append([diagnostic.center_x, diagnostic.center_y]); scales.append(diagnostic.scale)
        valid_values.append(valid); observed_values.append([bool(feature[236]), bool(feature[237])]); v2_values.append(feature)
    write_csv("p6br1_fixture_manifest.csv", fixture_rows)
    fixture_path = OUT / "p6br1_fixture_manifest.csv"
    overlap_ids = sorted({row["fixture_id"] for row in fixture_rows} & excluded_ids)
    overlap_hashes = sorted({row["source_sha256"] for row in fixture_rows} & excluded_hashes)
    overlap = {
        "original_p6b_fixture_count": len(original_rows),
        "p6br1_fixture_count": len(fixture_rows),
        "fixture_id_overlap_count": len(overlap_ids),
        "fixture_id_overlaps": overlap_ids,
        "source_sha256_overlap_count": len(overlap_hashes),
        "source_sha256_overlaps": overlap_hashes,
        "passed": not overlap_ids and not overlap_hashes,
        "p6br1_membership_sha256": sha(fixture_path),
        "frozen_before_candidate_evaluation": True,
    }
    if not overlap["passed"]:
        raise RuntimeError(f"P6BR1 fixture overlap: {overlap}")
    write_json("p6br1_fixture_overlap_audit.json", overlap)
    np.savez_compressed(
        OUT / "p6br1_offline_oracle_outputs.npz",
        fixture_ids=np.asarray([row["fixture_id"] for row in fixture_rows]),
        categories=np.asarray([row["visibility_category"] for row in fixture_rows]),
        source_sha256=np.asarray([row["source_sha256"] for row in fixture_rows]),
        keypoints_133=np.stack(keypoints_values).astype(np.float32),
        scores_133=np.stack(scores_values).astype(np.float32),
        normalization_center=np.asarray(centers, np.float64),
        normalization_scale=np.asarray(scales, np.float64),
        valid_mask_133=np.stack(valid_values).astype(bool),
        observed_flags=np.asarray(observed_values, bool),
        v2_features=np.stack(v2_values).astype(np.float32),
    )
    state = {
        "contract_sha256": sha(OUT / "p6br1_v2_dependency_parity_contract.json"),
        "fixture_membership_sha256": sha(fixture_path),
        "oracle_sha256": sha(OUT / "p6br1_offline_oracle_outputs.npz"),
        "composition": {category: 20 for category in ("ZERO", "ONE", "TWO")},
        "candidate_evaluation_started": False,
    }
    write_json("p6br1_pre_evaluation_freeze.json", state)
    print(json.dumps({"prepared": True, "fixtures": 60, **state}, indent=2))
    return 0


def evaluate() -> int:
    import onnxruntime as ort

    verify_frozen()
    contract_path = OUT / "p6br1_v2_dependency_parity_contract.json"
    fixture_path = OUT / "p6br1_fixture_manifest.csv"
    oracle_path = OUT / "p6br1_offline_oracle_outputs.npz"
    freeze = json.loads((OUT / "p6br1_pre_evaluation_freeze.json").read_text(encoding="utf-8"))
    if sha(contract_path) != freeze["contract_sha256"] or sha(fixture_path) != freeze["fixture_membership_sha256"] or sha(oracle_path) != freeze["oracle_sha256"]:
        raise RuntimeError("P6BR1 pre-evaluation freeze changed")
    contract_hash_before = sha(contract_path)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    fixtures = read_csv(fixture_path)
    oracle = np.load(oracle_path)
    session = ort.InferenceSession(str(ONNX), providers=["CPUExecutionProvider"])
    consumed_rows, validity_rows, normalization_rows, v2_rows, unused_rows = [], [], [], [], []
    all_pass = True
    block_indices = {"BODY": BODY_INDICES, "LEFT_HAND": LEFT_HAND_INDICES, "RIGHT_HAND": RIGHT_HAND_INDICES}
    for index, row in enumerate(fixtures):
        value, center, scale = preprocess(Path(row["resolved_source_path"]))
        simcc_x, simcc_y = session.run(["simcc_x", "simcc_y"], {"input": value})
        points, scores = decode(simcc_x, simcc_y, center, scale)
        oracle_points = oracle["keypoints_133"][index]
        oracle_scores = oracle["scores_133"][index]
        presence = np.asarray([
            np.count_nonzero(scores[LEFT_HAND_INDICES] >= SCORE_THRESHOLD) >= MIN_HAND_POINTS,
            np.count_nonzero(scores[RIGHT_HAND_INDICES] >= SCORE_THRESHOLD) >= MIN_HAND_POINTS,
        ], bool)
        feature, diagnostic = build_frame_features(points, scores, presence)
        valid = np.all(np.isfinite(np.column_stack([points, scores])), axis=1)
        fixture_numeric_pass = True
        for block, indices in block_indices.items():
            xy_error = np.abs(points[indices].astype(np.float64) - oracle_points[indices].astype(np.float64))
            score_error = np.abs(scores[indices].astype(np.float64) - oracle_scores[indices].astype(np.float64))
            median_xy, max_xy, max_score = float(np.median(xy_error)), float(np.max(xy_error)), float(np.max(score_error))
            max_flat = int(np.argmax(xy_error))
            max_local_point, max_axis = np.unravel_index(max_flat, xy_error.shape)
            block_pass = median_xy <= contract["numeric_tolerances"]["decoded_consumed_xy_median_absolute_error_pixels"] and max_xy <= contract["numeric_tolerances"]["decoded_consumed_xy_maximum_absolute_error_pixels"] and max_score <= contract["numeric_tolerances"]["native_score_max_absolute_error"]
            fixture_numeric_pass = fixture_numeric_pass and block_pass
            consumed_rows.append({"fixture_id": row["fixture_id"], "category": row["visibility_category"], "block": block, "point_count": len(indices), "xy_median_abs_error_pixels": median_xy, "xy_max_abs_error_pixels": max_xy, "max_error_source_point_index": int(indices[max_local_point]), "max_error_axis": "x" if max_axis == 0 else "y", "score_max_abs_error": max_score, "pass": block_pass})
        oracle_valid = oracle["valid_mask_133"][index]
        oracle_observed = oracle["observed_flags"][index]
        valid_exact = bool(np.array_equal(valid[CONSUMED], oracle_valid[CONSUMED]))
        candidate_observed = presence & diagnostic.success
        observed_exact = bool(np.array_equal(candidate_observed, oracle_observed))
        validity_pass = valid_exact and observed_exact
        validity_rows.append({"fixture_id": row["fixture_id"], "category": row["visibility_category"], "consumed_valid_masks_exact": valid_exact, "oracle_lh_observed": bool(oracle_observed[0]), "candidate_lh_observed": bool(candidate_observed[0]), "oracle_rh_observed": bool(oracle_observed[1]), "candidate_rh_observed": bool(candidate_observed[1]), "observed_exact": observed_exact, "pass": validity_pass})
        center_error = float(np.max(np.abs(np.asarray([diagnostic.center_x, diagnostic.center_y]) - oracle["normalization_center"][index])))
        scale_error = float(abs(diagnostic.scale - oracle["normalization_scale"][index]) / max(abs(float(oracle["normalization_scale"][index])), 1e-12))
        normalization_pass = center_error <= contract["numeric_tolerances"]["normalization_center_maximum_absolute_xy_error_pixels"] and scale_error <= contract["numeric_tolerances"]["normalization_scale_relative_error"]
        normalization_rows.append({"fixture_id": row["fixture_id"], "category": row["visibility_category"], "center_max_abs_error_pixels": center_error, "scale_relative_error": scale_error, "pass": normalization_pass})
        v2_error = np.abs(feature.astype(np.float64) - oracle["v2_features"][index].astype(np.float64))
        v2_mean, v2_max = float(np.mean(v2_error)), float(np.max(v2_error))
        v2_pass = v2_mean <= contract["numeric_tolerances"]["final_v2_mean_absolute_error"] and v2_max <= contract["numeric_tolerances"]["final_v2_maximum_absolute_error"]
        v2_rows.append({"fixture_id": row["fixture_id"], "category": row["visibility_category"], "v2_mean_abs_error": v2_mean, "v2_max_abs_error": v2_max, "pass": v2_pass})
        unused_error = np.abs(points[UNUSED].astype(np.float64) - oracle_points[UNUSED].astype(np.float64))
        max_flat = int(np.argmax(unused_error)); point_local, axis = np.unravel_index(max_flat, unused_error.shape)
        unused_rows.append({"fixture_id": row["fixture_id"], "category": row["visibility_category"], "unused_point_count": len(UNUSED), "xy_median_abs_error_pixels": float(np.median(unused_error)), "xy_max_abs_error_pixels": float(np.max(unused_error)), "max_error_point_index": int(UNUSED[point_local]), "max_error_axis": "x" if axis == 0 else "y", "pass_fail_gate": "NO"})
        all_pass = all_pass and points.shape == (133, 2) and scores.shape == (133,) and fixture_numeric_pass and validity_pass and normalization_pass and v2_pass
    write_csv("p6br1_v2_consumed_raw_parity.csv", consumed_rows)
    write_csv("p6br1_valid_observed_parity.csv", validity_rows)
    write_csv("p6br1_normalization_parity.csv", normalization_rows)
    write_csv("p6br1_final_v2_parity.csv", v2_rows)
    write_csv("p6br1_unused_point_descriptive_parity.csv", unused_rows)
    contract_hash_after = sha(contract_path)
    classification = "P6BR1_V2_DEPENDENCY_PARITY_CONFIRMED" if all_pass and contract_hash_before == contract_hash_after else "P6BR1_V2_DEPENDENCY_PARITY_NOT_CONFIRMED"
    decision = {
        "classification": classification,
        "formal_p6b_status": "P6B_SEMANTIC_PARITY_FAILED",
        "formal_p6b_reclassified": False,
        "fixture_count": len(fixtures),
        "fixture_overlap_with_p6b": 0,
        "full_133_structure": "PASS",
        "body_parity": "PASS" if all(row["pass"] for row in consumed_rows if row["block"] == "BODY") else "FAIL",
        "left_hand_parity": "PASS" if all(row["pass"] for row in consumed_rows if row["block"] == "LEFT_HAND") else "FAIL",
        "right_hand_parity": "PASS" if all(row["pass"] for row in consumed_rows if row["block"] == "RIGHT_HAND") else "FAIL",
        "scores": "PASS" if all(row["score_max_abs_error"] <= 1e-4 for row in consumed_rows) else "FAIL",
        "validity": "PASS" if all(row["consumed_valid_masks_exact"] for row in validity_rows) else "FAIL",
        "observed": "PASS" if all(row["observed_exact"] for row in validity_rows) else "FAIL",
        "normalization": "PASS" if all(row["pass"] for row in normalization_rows) else "FAIL",
        "final_v2": "PASS" if all(row["pass"] for row in v2_rows) else "FAIL",
        "worst_v2_consumed_xy_error_pixels": max(row["xy_max_abs_error_pixels"] for row in consumed_rows),
        "worst_v2_error": max(row["v2_max_abs_error"] for row in v2_rows),
        "worst_unused_point_error_pixels": max(row["xy_max_abs_error_pixels"] for row in unused_rows),
        "parity_contract_sha256_before": contract_hash_before,
        "parity_contract_sha256_after": contract_hash_after,
        "parity_contract_changed_after_results": contract_hash_before != contract_hash_after,
        "same_onnx_verified": sha(ONNX) == EXPECTED_ONNX_SHA,
        "android_tested": False,
        "production_authorized": False,
        "recommended_next_gate": "P6B-GATE-B_ANDROID_DEVICE_FEASIBILITY" if classification == "P6BR1_V2_DEPENDENCY_PARITY_CONFIRMED" else "PROJECT_LEAD_RUNTIME_ARCHITECTURE_REVIEW",
        "next_gate_executed": False,
    }
    write_json("p6br1_decision.json", decision)
    print(json.dumps(decision, indent=2))
    return 0 if classification == "P6BR1_V2_DEPENDENCY_PARITY_CONFIRMED" else 3


def verify_parent_manifest(directory: Path) -> dict[str, Any]:
    manifest_path = directory / "artifact_hash_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mismatches = []
    for item in manifest.get("files", []):
        candidate = ROOT / item["path"]
        if not candidate.is_file() or sha(candidate) != item["sha256"]:
            mismatches.append(item["path"])
    return {"manifest_path": rel(manifest_path), "manifest_sha256": sha(manifest_path), "mismatches": mismatches}


def finalize() -> int:
    verify_frozen()
    decision = json.loads((OUT / "p6br1_decision.json").read_text(encoding="utf-8"))
    overlap = json.loads((OUT / "p6br1_fixture_overlap_audit.json").read_text(encoding="utf-8"))
    freeze = json.loads((OUT / "p6br1_pre_evaluation_freeze.json").read_text(encoding="utf-8"))
    p6b_check, p6a_check, d12_check = verify_parent_manifest(P6B), verify_parent_manifest(P6A), verify_parent_manifest(D12)
    progress_before = sha(PROGRESS)
    confirmed = decision["classification"] == "P6BR1_V2_DEPENDENCY_PARITY_CONFIRMED"
    state = {
        "parent": rel(P6B / "APPHEAR_RECOGNITION_CANONICAL_STATE_P6B.json"),
        "parent_sha256": sha(P6B / "APPHEAR_RECOGNITION_CANONICAL_STATE_P6B.json"),
        "formal_p6b_status": "P6B_SEMANTIC_PARITY_FAILED",
        "formal_p6b_status_changed": False,
        "confirmation_scope": "V2_DEPENDENCY_CLOSURE_ONLY",
        "frozen_backend": "DWPose-L",
        "frozen_onnx_sha256": EXPECTED_ONNX_SHA,
        "tolerances_changed": False,
        "fixture_overlap_with_p6b": 0,
        "fixture_membership_sha256": overlap["p6br1_membership_sha256"],
        "v2_dependency_parity": "CONFIRMED" if confirmed else "NOT_CONFIRMED",
        "android_semantic_parity": "NOT_YET_TESTED",
        "android_device_feasibility": "UNKNOWN",
        "production_authorized": False,
        "recommended_next_gate": decision["recommended_next_gate"],
        "next_gate_executed": False,
    }
    write_json("APPHEAR_RECOGNITION_CANONICAL_STATE_P6BR1.json", state)
    write_json("p6br1_next_gate_contract.json", {
        "gate": decision["recommended_next_gate"],
        "trigger": decision["classification"],
        "android_execution_in_p6br1": False,
        "production_authorized": False,
        "must_preserve": ["formal P6B failure", "same DWPose-L", "same ONNX", "same V2", "same tolerances", "no recognizer inference"],
        "executed": False,
    })
    source_rows = [
        ("Formal P6B failure", P6B / "APPHEAR_RECOGNITION_CANONICAL_STATE_P6B.json", "P6B canonical state", "IMMUTABLE"),
        ("Frozen ONNX", ONNX, "frozen_dwpose_l_fp32.onnx", "VERIFIED"),
        ("Prospective contract", OUT / "p6br1_v2_dependency_parity_contract.json", "P6BR1 contract", "FROZEN_BEFORE_RESULTS"),
        ("New fixtures", OUT / "p6br1_fixture_manifest.csv", "60 non-overlapping fixtures", "FROZEN_BEFORE_RESULTS"),
        ("V2 dependency result", OUT / "p6br1_decision.json", decision["classification"], "GOVERNED_RESULT"),
    ]
    lines = ["# P6B-R1 Source of Truth Index", "", "| Claim | Source | Artifact | SHA-256 | Status |", "|---|---|---|---|---|"]
    lines += [f"| {claim} | `{rel(path)}` | {artifact} | `{sha(path)}` | {status} |" for claim, path, artifact, status in source_rows]
    (OUT / "P6BR1_SOURCE_OF_TRUTH_INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = f"""# P6B-R1 V2 Dependency Parity Confirmation

## Result

`{decision['classification']}`

Formal P6-B remains `P6B_SEMANTIC_PARITY_FAILED`; it was not reclassified. This prospective gate used the identical DWPose-L checkpoint, unchanged FP32 ONNX graph, unchanged numeric tolerances, and 60 new P2A development fixtures with zero ID or source-hash overlap with the original 48.

## New fixture result

- Composition: 20 ZERO / 20 ONE / 20 TWO.
- 133-point structure/order: PASS.
- Body 0..16: {decision['body_parity']}.
- Left hand 91..111: {decision['left_hand_parity']}.
- Right hand 112..132: {decision['right_hand_parity']}.
- Scores: {decision['scores']}.
- Validity: {decision['validity']}.
- Observed flags: {decision['observed']}.
- Normalization: {decision['normalization']}.
- Final V2: {decision['final_v2']}.
- Worst V2-consumed XY error: `{decision['worst_v2_consumed_xy_error_pixels']:.9g}` source pixels.
- Worst final V2 error: `{decision['worst_v2_error']:.9g}`.

The blocking result was `positive_g083` (ONE), DWPose left-hand point index `101`, x coordinate: `2.08328247` source pixels maximum absolute error versus the unchanged `0.5`-pixel limit. The fixture was retained and the tolerance was not changed.

Unused face/foot numeric errors were reported descriptively and were not part of this prospective pass/fail gate. Their worst error was `{decision['worst_unused_point_error_pixels']:.9g}` source pixels.

## Boundary

This audit evaluates only the dependency closure consumed by `DWPOSE_REPRESENTATION_V2_238` in the desktop ONNX Runtime comparison; that scoped parity was **not confirmed**. Actual Android semantic parity and target-device performance remain untested. Production is not authorized.
"""
    (OUT / "P6BR1_V2_DEPENDENCY_PARITY_REPORT.md").write_text(report, encoding="utf-8")
    required = [
        "P6BR1_V2_DEPENDENCY_PARITY_REPORT.md", "APPHEAR_RECOGNITION_CANONICAL_STATE_P6BR1.json", "P6BR1_SOURCE_OF_TRUTH_INDEX.md",
        "p6br1_v2_dependency_parity_contract.json", "p6br1_fixture_manifest.csv", "p6br1_fixture_overlap_audit.json",
        "p6br1_offline_oracle_outputs.npz", "p6br1_v2_consumed_raw_parity.csv", "p6br1_valid_observed_parity.csv",
        "p6br1_normalization_parity.csv", "p6br1_final_v2_parity.csv", "p6br1_unused_point_descriptive_parity.csv",
        "p6br1_decision.json", "p6br1_next_gate_contract.json",
    ]
    missing = [name for name in required if not (OUT / name).is_file()]
    integrity = {
        "passed": not missing and not p6b_check["mismatches"] and not p6a_check["mismatches"] and not d12_check["mismatches"] and sha(PROGRESS) == progress_before and sha(ONNX) == EXPECTED_ONNX_SHA and sha(CHECKPOINT) == EXPECTED_CHECKPOINT_SHA and overlap["passed"] and sha(OUT / "p6br1_v2_dependency_parity_contract.json") == freeze["contract_sha256"],
        "p6b_hashes_unchanged": not p6b_check["mismatches"], "p6b_verification": p6b_check,
        "p6a_hashes_unchanged": not p6a_check["mismatches"], "p6a_verification": p6a_check,
        "d12_hashes_unchanged": not d12_check["mismatches"], "d12_verification": d12_check,
        "progress_tracker_sha256_before_finalize": progress_before, "progress_tracker_sha256_after_finalize": sha(PROGRESS), "progress_tracker_unchanged": sha(PROGRESS) == progress_before,
        "same_onnx_hash_verified": sha(ONNX) == EXPECTED_ONNX_SHA,
        "same_dwpose_checkpoint_verified": sha(CHECKPOINT) == EXPECTED_CHECKPOINT_SHA,
        "new_fixture_membership_frozen_before_evaluation": True,
        "original_p6b_fixtures_excluded": overlap["passed"],
        "tolerances_unchanged": sha(OUT / "p6br1_v2_dependency_parity_contract.json") == freeze["contract_sha256"],
        "missing_required_outputs": missing,
        "training": False, "recognizer_inference": False, "d10_accessed": False, "pristine_data_accessed": False,
        "v2_modified": False, "backend_changed": False, "android_modified": False, "p4_reopened": False, "s5_changed": False, "s7_changed": False,
    }
    write_json("p6br1_integrity.json", integrity)
    files = sorted(path for path in OUT.iterdir() if path.is_file() and path.name != "artifact_hash_manifest.json")
    write_json("artifact_hash_manifest.json", {"schema": "P6BR1_ARTIFACT_HASH_MANIFEST_V1", "files": [{"path": rel(path), "bytes": path.stat().st_size, "sha256": sha(path)} for path in files]})
    print(json.dumps({"integrity": integrity["passed"], "classification": decision["classification"], "fixtures": 60, "artifacts": len(files) + 1}, indent=2))
    return 0 if integrity["passed"] else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "evaluate", "finalize"])
    args = parser.parse_args()
    return {"prepare": prepare, "evaluate": evaluate, "finalize": finalize}[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
