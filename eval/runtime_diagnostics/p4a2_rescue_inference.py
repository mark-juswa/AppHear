# ruff: noqa: E501
"""Prepare and run only the missing frozen DWPose inference for P4-A2."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from eval.runtime_diagnostics.p2a_dwpose_linux import (
    BASE_RUNTIME,
    CHECKPOINT,
    CONFIG,
    EXPECTED_BASE_SHA,
    EXPECTED_CHECKPOINT_SHA,
    EXPECTED_CONFIG_SHA,
    JOINT_THRESHOLD,
    LEFT_SLICE,
    MIN_CONFIDENT_JOINTS,
    RIGHT_SLICE,
    official_affines,
    sha256_file,
)

PROJECT = Path(__file__).resolve().parents[2]
P2_WINDOWS_ATTEMPT = PROJECT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01"
CHECKPOINT = P2_WINDOWS_ATTEMPT / "checkpoint/dw-ll_ucoco.pth"
CONFIG = P2_WINDOWS_ATTEMPT / "toolchain/source_snapshot/mmpose/configs/wholebody_2d_keypoint/rtmpose/ubody/rtmpose-l_8xb64-270e_coco-ubody-wholebody-256x192.py"
BASE_RUNTIME = P2_WINDOWS_ATTEMPT / "toolchain/source_snapshot/mmpose/configs/_base_/default_runtime.py"
EVALUATOR = Path(__file__).resolve()
EVIDENCE = PROJECT / "artifacts/recognition_upgrade/perception_backend_replacement/p4a2_fresh_evidence_repair_v2_01"
P3 = PROJECT / "artifacts/recognition_upgrade/perception_backend_replacement/p3_dwpose_temporal_usability_01"
P4A = PROJECT / "artifacts/recognition_upgrade/perception_backend_replacement/p4a_dwpose_presence_eligibility_01"
OUTPUT = PROJECT / "artifacts/recognition_upgrade/perception_backend_replacement/p4a2_high_recall_rescue_final_01"
SOURCE = EVIDENCE / "p4a2_annotation_source_manifest_v2.csv"
SOURCE_V1 = PROJECT / "artifacts/recognition_upgrade/perception_backend_replacement/p4a2_fresh_evidence_repair_01/p4a2_annotation_source_manifest.csv"
FROZEN_TRUTH = EVIDENCE / "frozen_truth/P4A2_FRESH_HUMAN_TRUTH_V1.csv"
FROZEN_META = EVIDENCE / "frozen_truth/P4A2_FRESH_HUMAN_TRUTH_V1.json"
MANIFEST = OUTPUT / "p4a2_frozen_inference_manifest.csv"
RAW_DIR = OUTPUT / "raw_outputs_missing_256"

EXPECTED = {
    "dataset_sha256": "7819c59123b4dacdafac190c81754deb766d6ed6087a2b58535490d45a6a3edd",
    "annotation_sha256": "1b9f34412ba885e397019742bf29027987ce58668d099fd3914e48ab3206774b",
    "source_manifest_sha256": "18250eea84cebd59002f1ccbbcaf43977106ecaa8e4b6597909221ee95a6899b",
    "dev_sha256": "142efe1f1864dbe19efb16357948ed7a2fe5adb6faf9901a3679daf6291736d8",
    "validation_sha256": "a8ae3cb2a65433e5d21361254fe7490fdcd479a382ac784d79fc87e15fe84771",
    "final_sha256": "af78e1048566ad7842e792ae4dbd709bca43d79697ec1e0a234f94acfddcfcfc",
    "annotation_tool_sha256": "36b8e8ecc7e0f35af7e69002b1aebae751ea82b0cb28a370c60230a411cc28b5",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def platform_path(raw: str) -> Path:
    if os.name != "nt" and len(raw) >= 3 and raw[1:3] == ":\\":
        drive = raw[0].lower()
        return Path(f"/mnt/{drive}/{raw[3:].replace(chr(92), '/')}")
    return Path(raw)


def project_path(relative: str) -> Path:
    return PROJECT / Path(relative)


def dataset_hash(rows: list[dict[str, str]]) -> str:
    label_fields = [
        "any_hand_visible", "visible_left", "visible_right", "zero_hand", "rest",
        "entering", "leaving", "blur", "occlusion", "edge_clipped", "partial_visibility",
        "crossing", "hand_hand_contact", "hand_body_contact", "left_visibility_quality",
        "right_visibility_quality", "reviewer_note",
    ]
    fields = ["annotation_row_id", "sequence_id", "frame_index", "image_sha256", *label_fields, "reviewer_status"]
    payload = [{field: row[field] for field in fields} for row in sorted(rows, key=lambda item: item["annotation_row_id"])]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_frozen_evidence() -> dict[str, Any]:
    meta = json.loads(FROZEN_META.read_text(encoding="utf-8"))
    checks = {
        "dataset_sha256": dataset_hash(read_csv(FROZEN_TRUTH)),
        "annotation_sha256": sha256(FROZEN_TRUTH),
        "source_manifest_sha256": sha256(SOURCE),
        "dev_sha256": sha256(EVIDENCE / "splits/p4a2_dev_manifest.csv"),
        "validation_sha256": sha256(EVIDENCE / "splits/p4a2_validation_manifest.csv"),
        "final_sha256": sha256(EVIDENCE / "sealed_final/p4a2_final_eval_manifest.csv"),
        "annotation_tool_sha256": sha256(PROJECT / "eval/runtime_diagnostics/p4a2_annotation_tool_v2.py"),
    }
    if checks != EXPECTED or meta["dataset_sha256"] != EXPECTED["dataset_sha256"]:
        raise RuntimeError(f"P4A2_FROZEN_EVIDENCE_MISMATCH: {checks}")
    if not meta["final_evaluation_signer_separated"] or meta["status"] != "FROZEN":
        raise RuntimeError("P4A2_FROZEN_EVIDENCE_MISMATCH: final split is not sealed/frozen")
    p4a_hashes = json.loads((P4A / "provenance_hash_manifest.json").read_text(encoding="utf-8"))["files"]
    by_name = {row["path"].replace("\\", "/"): row["sha256"] for row in p4a_hashes}
    for name in ("p4a_selected_model.json", "p4a_feature_manifest.json"):
        if sha256(P4A / name) != by_name[name]:
            raise RuntimeError(f"Frozen E2 artifact mismatch: {name}")
    return checks


def verify_dwpose_identity() -> None:
    expected = {
        CHECKPOINT: EXPECTED_CHECKPOINT_SHA,
        CONFIG: EXPECTED_CONFIG_SHA,
        BASE_RUNTIME: EXPECTED_BASE_SHA,
    }
    for path, digest in expected.items():
        if sha256_file(path) != digest:
            raise RuntimeError(f"Frozen DWPose identity mismatch: {path}")


def prepare() -> dict[str, Any]:
    checks = verify_frozen_evidence()
    verify_dwpose_identity()
    if MANIFEST.exists():
        raise RuntimeError("P4-A2 frozen inference manifest already exists")
    source = read_csv(SOURCE)
    source_v1 = {row["annotation_row_id"]: row for row in read_csv(SOURCE_V1)}
    p3_frames = read_csv(P3 / "frozen_frame_manifest.csv")
    p3_by_hash = {row["image_sha256"]: row for row in p3_frames}
    rows: list[dict[str, Any]] = []
    for row in source:
        image = platform_path(row["review_image_path"])
        if not image.is_file() or sha256(image) != row["image_sha256"]:
            raise RuntimeError(f"P4-A2 source image mismatch: {row['annotation_row_id']}")
        original = source_v1[row["source_annotation_row_id"]]
        matched = p3_by_hash.get(row["image_sha256"])
        raw_relative = (
            f"artifacts/recognition_upgrade/perception_backend_replacement/p3_dwpose_temporal_usability_01/raw_outputs/{matched['manifest_row_id']}.npz"
            if matched
            else f"artifacts/recognition_upgrade/perception_backend_replacement/p4a2_high_recall_rescue_final_01/raw_outputs_missing_256/{row['annotation_row_id']}.npz"
        )
        rows.append({
            "annotation_row_id": row["annotation_row_id"],
            "source_annotation_row_id": row["source_annotation_row_id"],
            "sequence_id": row["sequence_id"],
            "frame_index": row["frame_index"],
            "timestamp_ns": original["timestamp_ns"],
            "signer_id": row["signer_id"],
            "gloss": row["gloss"],
            "intended_future_role": row["intended_future_role"],
            "image_path": row["review_image_path"],
            "image_sha256": row["image_sha256"],
            "raw_origin": "P3_REUSED" if matched else "P4A2_EXACT_DWPOSE_RERUN_REQUIRED",
            "raw_relative_path": raw_relative,
        })
    if len(rows) != 458 or len({row["annotation_row_id"] for row in rows}) != 458:
        raise RuntimeError("P4-A2 frozen inference row identity changed")
    origin_counts = {name: sum(row["raw_origin"] == name for row in rows) for name in {row["raw_origin"] for row in rows}}
    if origin_counts != {"P3_REUSED": 202, "P4A2_EXACT_DWPOSE_RERUN_REQUIRED": 256}:
        raise RuntimeError(f"Unexpected native-output coverage: {origin_counts}")
    write_csv(MANIFEST, rows)
    protocol = {
        "identity": "P4A2_HIGH_RECALL_ELIGIBILITY_RESCUE",
        "historical_p4a": "ELIGIBILITY_IMPROVED_BUT_GATES_FAILED",
        "evidence_checks": checks,
        "final_truth_status": "SEALED_UNTIL_CANDIDATE_FREEZE",
        "manifest_sha256": sha256(MANIFEST),
        "evaluator_sha256": sha256(EVALUATOR),
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA,
        "config_sha256": EXPECTED_CONFIG_SHA,
        "base_runtime_sha256": EXPECTED_BASE_SHA,
        "native_output_coverage": origin_counts,
        "roi": "whole frame pseudo-person ROI; exact frozen P2/P3 preprocessing/decoder/flip test",
        "no_model_change": True,
    }
    write_json(OUTPUT / "p4a2_frozen_inference_protocol.json", protocol)
    return protocol


def save_npz(path: Path, **values: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".npz.tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(handle, **values)
    os.replace(temporary, path)


def infer() -> dict[str, Any]:
    import psutil
    import torch
    from mmengine.dataset import Compose, pseudo_collate
    from mmengine.registry import init_default_scope
    from mmpose.apis import init_model
    from mmpose.utils import register_all_modules

    verify_frozen_evidence()
    verify_dwpose_identity()
    protocol = json.loads((OUTPUT / "p4a2_frozen_inference_protocol.json").read_text(encoding="utf-8"))
    if sha256(MANIFEST) != protocol["manifest_sha256"] or sha256(EVALUATOR) != protocol["evaluator_sha256"]:
        raise RuntimeError("P4-A2 frozen inference protocol changed")
    rows = [row for row in read_csv(MANIFEST) if row["raw_origin"] == "P4A2_EXACT_DWPOSE_RERUN_REQUIRED"]
    if len(rows) != 256:
        raise RuntimeError("Expected exactly 256 missing native outputs")
    existing = list(RAW_DIR.glob("*.npz")) if RAW_DIR.exists() else []
    if existing:
        raise RuntimeError("P4-A2 missing-output directory is not empty")
    register_all_modules()
    model = init_model(str(CONFIG), str(CHECKPOINT), device="cpu")
    if model.cfg.codec["input_size"] != (192, 256) or model.cfg.codec["simcc_split_ratio"] != 2.0:
        raise RuntimeError("Frozen DWPose input/decoder identity changed")
    if model.cfg.model.head.get("out_channels") != 133 or not model.cfg.model.test_cfg.get("flip_test"):
        raise RuntimeError("Frozen DWPose output/flip identity changed")
    init_default_scope(model.cfg.get("default_scope", "mmpose"))
    pipeline = Compose(model.cfg.test_dataloader.dataset.pipeline)
    process = psutil.Process()
    peak_rss = process.memory_info().rss
    timings: list[dict[str, Any]] = []
    for ordinal, row in enumerate(rows, start=1):
        t0 = time.perf_counter()
        image_path = platform_path(row["image_path"])
        if sha256(image_path) != row["image_sha256"]:
            raise RuntimeError(f"Source changed before inference: {row['annotation_row_id']}")
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        height, width = image.shape[:2]
        info: dict[str, Any] = {
            "img": image,
            "bbox": np.asarray([[0.0, 0.0, float(width), float(height)]], dtype=np.float32),
            "bbox_score": np.ones(1, dtype=np.float32),
        }
        info.update(model.dataset_meta)
        batch = pseudo_collate([pipeline(info)])
        t1 = time.perf_counter()
        with torch.no_grad():
            result = model.test_step(batch)[0]
        t2 = time.perf_counter()
        keypoints = np.asarray(result.pred_instances.keypoints[0], dtype=np.float32)
        scores = np.asarray(result.pred_instances.keypoint_scores[0], dtype=np.float32)
        if keypoints.shape != (133, 2) or scores.shape != (133,) or not np.isfinite(keypoints).all() or not np.isfinite(scores).all():
            raise RuntimeError(f"Invalid DWPose native output: {row['annotation_row_id']}")
        center, scale, affine, inverse = official_affines(width, height)
        counts = np.asarray([
            np.count_nonzero(scores[LEFT_SLICE] >= JOINT_THRESHOLD),
            np.count_nonzero(scores[RIGHT_SLICE] >= JOINT_THRESHOLD),
        ], dtype=np.int16)
        t3 = time.perf_counter()
        save_npz(
            project_path(row["raw_relative_path"]),
            keypoints_133=keypoints,
            scores_133=scores,
            left_hand_keypoints=keypoints[LEFT_SLICE],
            left_hand_scores=scores[LEFT_SLICE],
            right_hand_keypoints=keypoints[RIGHT_SLICE],
            right_hand_scores=scores[RIGHT_SLICE],
            confident_joint_counts=counts,
            gated_presence=counts >= MIN_CONFIDENT_JOINTS,
            timestamp_ns=np.asarray(int(row["timestamp_ns"]), dtype=np.int64),
            source_frame_id=np.asarray(int(row["frame_index"]), dtype=np.int64),
            roi_xyxy=np.asarray([0.0, 0.0, width, height], dtype=np.float32),
            bbox_center=center,
            bbox_scale=scale,
            affine=affine,
            inverse_affine=inverse,
            source_sha256=np.asarray(row["image_sha256"]),
            checkpoint_sha256=np.asarray(EXPECTED_CHECKPOINT_SHA),
            protocol_sha256=np.asarray(sha256(OUTPUT / "p4a2_frozen_inference_protocol.json")),
        )
        timings.append({
            "annotation_row_id": row["annotation_row_id"],
            "preprocessing_ms": (t1 - t0) * 1000,
            "inference_ms": (t2 - t1) * 1000,
            "postprocessing_ms": (t3 - t2) * 1000,
            "total_ms": (t3 - t0) * 1000,
        })
        peak_rss = max(peak_rss, process.memory_info().rss)
        if ordinal == 1 or ordinal % 25 == 0 or ordinal == len(rows):
            print(json.dumps({"processed": ordinal, "total": len(rows)}), flush=True)
    write_csv(OUTPUT / "p4a2_missing_inference_timings.csv", timings)
    raw_hashes = [{"path": str(path.relative_to(OUTPUT)), "sha256": sha256(path), "bytes": path.stat().st_size} for path in sorted(RAW_DIR.glob("*.npz"))]
    completion = {
        "processed": len(rows),
        "reused_p3_outputs": 202,
        "total_fresh_frames": 458,
        "peak_host_rss_bytes": peak_rss,
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA,
        "config_sha256": EXPECTED_CONFIG_SHA,
        "manifest_sha256": protocol["manifest_sha256"],
        "evaluator_sha256": protocol["evaluator_sha256"],
        "raw_output_hashes": raw_hashes,
        "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(OUTPUT / "p4a2_inference_completion.json", completion)
    return completion


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "infer"))
    args = parser.parse_args()
    result = prepare() if args.command == "prepare" else infer()
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
