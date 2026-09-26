"""Frozen P4-C1 WiLoR-Det eligibility benchmark.

This evaluator deliberately uses only the detector invoked by WiLoR's official
``demo.py``.  It does not load the WiLoR reconstruction network and it does not
combine detector results with DWPose.  DWPose data are read only after WiLoR
inference to produce the preregistered pairwise diagnostic.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np
import psutil
import torch
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4c1_wilor_det_01"
TRUTH = (
    ROOT
    / "artifacts/recognition_upgrade/perception_backend_replacement/"
    "p4a2_fresh_evidence_repair_v2_01/frozen_truth/P4A2_FRESH_HUMAN_TRUTH_V1.csv"
)
TRUTH_META = TRUTH.with_suffix(".json")
INFERENCE_MANIFEST = (
    ROOT
    / "artifacts/recognition_upgrade/perception_backend_replacement/"
    "p4a2_high_recall_rescue_final_01/p4a2_frozen_inference_manifest.csv"
)
DWPOSE_FEATURES = (
    ROOT
    / "artifacts/recognition_upgrade/perception_backend_replacement/"
    "p4a2_high_recall_rescue_final_01/p4a2_derived_features.csv"
)
WILOR_REPO = OUT / "third_party/WiLoR"
CHECKPOINT = WILOR_REPO / "pretrained_models/detector.pt"
OFFICIAL_DEMO = WILOR_REPO / "demo.py"
OFFICIAL_LICENSE = WILOR_REPO / "license.txt"
WARMUP_IMAGE = WILOR_REPO / "demo_img/test1.jpg"

EXPECTED_DATASET_SHA256 = "7819c59123b4dacdafac190c81754deb766d6ed6087a2b58535490d45a6a3edd"
EXPECTED_ANNOTATION_SHA256 = "1b9f34412ba885e397019742bf29027987ce58668d099fd3914e48ab3206774b"
EXPECTED_CHECKPOINT_SHA256 = "5ef3df44e42d2db52d4ffe91f83a22ce9925e2acc9abebf453f2c5d22e380033"
EXPECTED_REPO_COMMIT = "fcb911312a38fa8badd30d9656a167485d61b8f9"
CONFIDENCE = 0.30
EXPECTED_IMGSZ = 512
EXPECTED_NMS_IOU = 0.70
EXPECTED_CLASS_NAMES = {0: "left", 1: "right"}

INPUT_MANIFEST_OUT = OUT / "p4c1_frozen_input_manifest.csv"
RAW_DETECTIONS_OUT = OUT / "p4c1_raw_detections.csv"
SLOT_RESULTS_OUT = OUT / "p4c1_hand_slot_results.csv"
FRAME_RESULTS_OUT = OUT / "p4c1_frame_results.csv"
ONE_HAND_OUT = OUT / "p4c1_one_hand_results.csv"
ZERO_REST_OUT = OUT / "p4c1_zero_rest_results.csv"
ENTRY_LEAVING_OUT = OUT / "p4c1_entry_leaving_results.csv"
PAIRWISE_OUT = OUT / "p4c1_dwpose_pairwise.csv"
RUNTIME_OUT = OUT / "p4c1_runtime_results.csv"
PROVENANCE_OUT = OUT / "p4c1_wilor_provenance.json"
ENVIRONMENT_OUT = OUT / "p4c1_environment_manifest.json"
RESULT_JSON_OUT = OUT / "p4c1_wilor_det_eligibility_result.json"
REPORT_OUT = OUT / "P4C1_WILOR_DET_ELIGIBILITY_RESULT.md"
HASH_MANIFEST_OUT = OUT / "p4c1_artifact_hash_manifest.json"
RAW_NATIVE_DIR = OUT / "raw_native_outputs"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def atomic_write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else []
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def normalized_dataset_hash(rows: list[dict[str, str]]) -> str:
    # Exact frozen algorithm from p4a2_annotation_finalize_v2.py.
    label_fields = [
        "any_hand_visible", "visible_left", "visible_right", "zero_hand", "rest",
        "entering", "leaving", "blur", "occlusion", "edge_clipped",
        "partial_visibility", "crossing", "hand_hand_contact", "hand_body_contact",
        "left_visibility_quality", "right_visibility_quality", "reviewer_note",
    ]
    fields = ["annotation_row_id", "sequence_id", "frame_index", "image_sha256", *label_fields, "reviewer_status"]
    payload = [
        {field: row[field] for field in fields}
        for row in sorted(rows, key=lambda item: item["annotation_row_id"])
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def percentile(values: Iterable[float], q: float) -> float:
    data = sorted(float(value) for value in values)
    if not data:
        return math.nan
    position = (len(data) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return data[lower]
    return data[lower] * (upper - position) + data[upper] * (position - lower)


def rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def pct(value: float | None) -> str:
    return "N/A" if value is None else f"{100.0 * value:.2f}%"


def bool_text(value: bool) -> str:
    return "YES" if value else "NO"


def git_value(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(WILOR_REPO), *args], text=True).strip()


def verify_frozen_evidence() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if not TRUTH.exists() or not TRUTH_META.exists() or not INFERENCE_MANIFEST.exists():
        raise RuntimeError("P4C1_FROZEN_EVIDENCE_MISMATCH: required frozen artifact is missing")
    annotation_hash = sha256(TRUTH)
    truth_rows = read_csv(TRUTH)
    dataset_hash = normalized_dataset_hash(truth_rows)
    metadata = json.loads(TRUTH_META.read_text(encoding="utf-8"))
    if annotation_hash != EXPECTED_ANNOTATION_SHA256:
        raise RuntimeError(f"P4C1_FROZEN_EVIDENCE_MISMATCH: annotation {annotation_hash}")
    if dataset_hash != EXPECTED_DATASET_SHA256:
        raise RuntimeError(f"P4C1_FROZEN_EVIDENCE_MISMATCH: dataset {dataset_hash}")
    if metadata.get("dataset_sha256") != EXPECTED_DATASET_SHA256:
        raise RuntimeError("P4C1_FROZEN_EVIDENCE_MISMATCH: frozen metadata dataset hash")
    if len(truth_rows) != 458 or any(row["reviewer_status"] != "COMPLETE" for row in truth_rows):
        raise RuntimeError("P4C1_FROZEN_EVIDENCE_MISMATCH: expected 458 completed rows")
    if len({row["annotation_row_id"] for row in truth_rows}) != 458:
        raise RuntimeError("P4C1_FROZEN_EVIDENCE_MISMATCH: duplicate truth row ID")

    inference_rows = read_csv(INFERENCE_MANIFEST)
    inference_by_id = {row["annotation_row_id"]: row for row in inference_rows}
    if len(inference_rows) != 458 or len(inference_by_id) != 458:
        raise RuntimeError("P4C1_FROZEN_EVIDENCE_MISMATCH: inference identity manifest")
    if set(inference_by_id) != {row["annotation_row_id"] for row in truth_rows}:
        raise RuntimeError("P4C1_FROZEN_EVIDENCE_MISMATCH: truth/image identity set")
    return truth_rows, inference_rows


def verify_official_model(model: YOLO) -> dict[str, Any]:
    if sha256(CHECKPOINT) != EXPECTED_CHECKPOINT_SHA256:
        raise RuntimeError("P4C1_INVALID: official checkpoint hash mismatch")
    commit = git_value("rev-parse", "HEAD")
    if commit != EXPECTED_REPO_COMMIT:
        raise RuntimeError(f"P4C1_INVALID: WiLoR source commit changed: {commit}")
    names = {int(key): str(value) for key, value in model.names.items()}
    if names != EXPECTED_CLASS_NAMES:
        raise RuntimeError(f"P4C1_INVALID: detector class semantics changed: {names}")
    yaml = model.model.yaml
    if model.task != "pose" or yaml.get("scale") != "m" or yaml.get("kpt_shape") != [21, 3]:
        raise RuntimeError("P4C1_INVALID: detector architecture identity mismatch")
    return {"commit": commit, "names": names, "yaml": yaml}


def build_input_manifest(
    truth_rows: list[dict[str, str]], inference_rows: list[dict[str, str]]
) -> list[dict[str, Any]]:
    inference_by_id = {row["annotation_row_id"]: row for row in inference_rows}
    manifest: list[dict[str, Any]] = []
    for truth in truth_rows:
        identity = inference_by_id[truth["annotation_row_id"]]
        image_path = Path(identity["image_path"])
        if not image_path.is_file():
            raise RuntimeError(f"P4C1_FROZEN_EVIDENCE_MISMATCH: missing image {image_path}")
        actual_hash = sha256(image_path)
        if actual_hash != truth["image_sha256"] or actual_hash != identity["image_sha256"]:
            raise RuntimeError(f"P4C1_FROZEN_EVIDENCE_MISMATCH: image hash {truth['annotation_row_id']}")
        image = cv2.imread(str(image_path))
        if image is None:
            raise RuntimeError(f"P4C1_FROZEN_EVIDENCE_MISMATCH: unreadable image {image_path}")
        height, width = image.shape[:2]
        manifest.append({
            "manifest_row_id": f"P4C1_{truth['annotation_row_id']}",
            "annotation_row_id": truth["annotation_row_id"],
            "sequence_id": truth["sequence_id"],
            "signer_id": truth["signer_id"],
            "gloss": truth["gloss"],
            "frame_index": truth["frame_index"],
            "timestamp_ns": identity["timestamp_ns"],
            "image_path": str(image_path.resolve()),
            "image_sha256": actual_hash,
            "image_width": width,
            "image_height": height,
            "governed_benchmark": "GOVERNED_P4C_ARCHITECTURE_COMPARISON_BENCHMARK",
        })
    atomic_write_csv(INPUT_MANIFEST_OUT, manifest)
    return manifest


def save_environment() -> dict[str, Any]:
    import ultralytics

    memory = psutil.virtual_memory()
    environment = {
        "captured_utc": utc_now(),
        "platform": platform.platform(),
        "python": sys.version,
        "python_executable": sys.executable,
        "cpu": platform.processor(),
        "logical_cpu_count": psutil.cpu_count(logical=True),
        "physical_cpu_count": psutil.cpu_count(logical=False),
        "system_ram_bytes": memory.total,
        "torch": torch.__version__,
        "torchvision": __import__("torchvision").__version__,
        "ultralytics": ultralytics.__version__,
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "psutil": psutil.__version__,
        "backend": "CPU/PYTORCH",
        "cuda_available": torch.cuda.is_available(),
        "yolo_config_dir": os.environ.get("YOLO_CONFIG_DIR", ""),
    }
    atomic_write_json(ENVIRONMENT_OUT, environment)
    freeze = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    atomic_write_text(OUT / "p4c1_pip_freeze.txt", freeze)
    return environment


def run_detector(manifest: list[dict[str, Any]], model: YOLO) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    RAW_NATIVE_DIR.mkdir(parents=True, exist_ok=True)
    # Official demo image only; benchmark frames are never used for runtime setup.
    warmup = cv2.imread(str(WARMUP_IMAGE))
    if warmup is None:
        raise RuntimeError("P4C1_INVALID: official warm-up image unavailable")
    warm_result = model(warmup, conf=CONFIDENCE, verbose=False, device="cpu")[0]
    predictor = model.predictor
    if int(predictor.args.imgsz) != EXPECTED_IMGSZ:
        raise RuntimeError(f"P4C1_INVALID: reference image size {predictor.args.imgsz}")
    if abs(float(predictor.args.iou) - EXPECTED_NMS_IOU) > 1e-12:
        raise RuntimeError(f"P4C1_INVALID: reference NMS IoU {predictor.args.iou}")
    if bool(predictor.args.agnostic_nms) or int(predictor.args.max_det) != 300:
        raise RuntimeError("P4C1_INVALID: reference NMS behavior changed")
    del warm_result

    detection_rows: list[dict[str, Any]] = []
    runtime_rows: list[dict[str, Any]] = []
    process = psutil.Process()
    peak_rss = process.memory_info().rss
    for number, row in enumerate(manifest, start=1):
        image = cv2.imread(row["image_path"])
        started = time.perf_counter_ns()
        result = model(image, conf=CONFIDENCE, verbose=False, device="cpu")[0]
        ended = time.perf_counter_ns()
        rss = process.memory_info().rss
        peak_rss = max(peak_rss, rss)
        boxes = result.boxes
        xyxy = boxes.xyxy.detach().cpu().numpy() if boxes is not None else np.empty((0, 4))
        confidences = boxes.conf.detach().cpu().numpy() if boxes is not None else np.empty((0,))
        classes = boxes.cls.detach().cpu().numpy().astype(int) if boxes is not None else np.empty((0,), dtype=int)
        keypoints = result.keypoints.data.detach().cpu().numpy() if result.keypoints is not None else np.empty((0, 21, 3))
        native_detections: list[dict[str, Any]] = []
        for index, (box, confidence, class_id) in enumerate(zip(xyxy, confidences, classes)):
            points = keypoints[index].tolist() if index < len(keypoints) else []
            decoded = EXPECTED_CLASS_NAMES.get(int(class_id), f"unknown_{int(class_id)}")
            native = {
                "detection_index": index,
                "xyxy": [float(value) for value in box],
                "confidence": float(confidence),
                "class_id": int(class_id),
                "decoded_anatomical_side": decoded,
                "keypoints_21x3": points,
            }
            native_detections.append(native)
            detection_rows.append({
                "annotation_row_id": row["annotation_row_id"],
                "sequence_id": row["sequence_id"],
                "frame_index": row["frame_index"],
                "timestamp_ns": row["timestamp_ns"],
                "image_sha256": row["image_sha256"],
                "detection_index": index,
                "x1": float(box[0]), "y1": float(box[1]),
                "x2": float(box[2]), "y2": float(box[3]),
                "confidence": float(confidence),
                "class_id": int(class_id),
                "decoded_anatomical_side": decoded,
                "keypoints_21x3_json": json.dumps(points, separators=(",", ":")),
                "confidence_operating_point": CONFIDENCE,
                "nms_iou": EXPECTED_NMS_IOU,
            })
        native_output = {
            "annotation_row_id": row["annotation_row_id"],
            "image_sha256": row["image_sha256"],
            "original_shape_hw": list(result.orig_shape),
            "input_size": EXPECTED_IMGSZ,
            "confidence_operating_point": CONFIDENCE,
            "nms_iou": EXPECTED_NMS_IOU,
            "class_names": EXPECTED_CLASS_NAMES,
            "pre_confidence_candidate_count": None,
            "pre_confidence_candidate_count_exposed_by_official_api": False,
            "post_nms_accepted_count": len(native_detections),
            "detections": native_detections,
        }
        atomic_write_json(RAW_NATIVE_DIR / f"{row['annotation_row_id']}.json", native_output)
        speed = result.speed
        runtime_rows.append({
            "annotation_row_id": row["annotation_row_id"],
            "sequence_id": row["sequence_id"],
            "frame_index": row["frame_index"],
            "preprocess_ms": float(speed.get("preprocess", math.nan)),
            "inference_ms": float(speed.get("inference", math.nan)),
            "postprocess_ms": float(speed.get("postprocess", math.nan)),
            "total_model_ms": sum(float(speed.get(key, 0.0)) for key in ("preprocess", "inference", "postprocess")),
            "total_wall_ms": (ended - started) / 1_000_000.0,
            "process_rss_bytes": rss,
            "peak_process_rss_bytes_so_far": peak_rss,
            "backend": "CPU/PYTORCH",
        })
        if number % 25 == 0 or number == len(manifest):
            print(f"P4-C1 processed {number}/{len(manifest)}", flush=True)
    atomic_write_csv(RAW_DETECTIONS_OUT, detection_rows, fields=[
        "annotation_row_id", "sequence_id", "frame_index", "timestamp_ns", "image_sha256",
        "detection_index", "x1", "y1", "x2", "y2", "confidence", "class_id",
        "decoded_anatomical_side", "keypoints_21x3_json", "confidence_operating_point", "nms_iou",
    ])
    atomic_write_csv(RUNTIME_OUT, runtime_rows)
    return detection_rows, runtime_rows


def score(
    truth_rows: list[dict[str, str]],
    manifest: list[dict[str, Any]],
    detections: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    manifest_by_id = {row["annotation_row_id"]: row for row in manifest}
    detections_by_id: dict[str, list[dict[str, Any]]] = {row["annotation_row_id"]: [] for row in manifest}
    for detection in detections:
        detections_by_id[detection["annotation_row_id"]].append(detection)

    dwpose_rows = read_csv(DWPOSE_FEATURES)
    dwpose = {
        (row["annotation_row_id"], row["anatomical_side"].lower()): float(row["hand_count_ge_030"]) >= 11
        for row in dwpose_rows
    }
    if len(dwpose) != 916:
        raise RuntimeError("P4C1_INVALID: frozen DWPose pairwise evidence is incomplete")

    slot_rows: list[dict[str, Any]] = []
    frame_rows: list[dict[str, Any]] = []
    one_hand_rows: list[dict[str, Any]] = []
    zero_rest_rows: list[dict[str, Any]] = []
    entry_leaving_rows: list[dict[str, Any]] = []
    pairwise_rows: list[dict[str, Any]] = []
    confusion = Counter()
    for truth in truth_rows:
        row_id = truth["annotation_row_id"]
        frame_detections = detections_by_id[row_id]
        pred = {
            side: any(det["decoded_anatomical_side"] == side for det in frame_detections)
            for side in ("left", "right")
        }
        visible = {side: truth[f"visible_{side}"] == "YES" for side in ("left", "right")}
        unknown = {side: truth[f"visible_{side}"] == "UNCERTAIN" for side in ("left", "right")}
        any_visible = any(visible.values())
        any_pred = any(pred.values())
        two_visible = all(visible.values())
        one_visible = sum(visible.values()) == 1 and not any(unknown.values())
        dw = {side: dwpose[(row_id, side)] for side in ("left", "right")}
        for side in ("left", "right"):
            if unknown[side]:
                outcome = "EXCLUDED_UNKNOWN"
            elif visible[side] and pred[side]:
                outcome = "TP"
            elif visible[side] and not pred[side]:
                outcome = "FN"
            elif not visible[side] and pred[side]:
                outcome = "FP"
            else:
                outcome = "TN"
            confusion[outcome] += 1
            side_detections = [d for d in frame_detections if d["decoded_anatomical_side"] == side]
            slot_rows.append({
                "annotation_row_id": row_id, "sequence_id": truth["sequence_id"],
                "signer_id": truth["signer_id"], "frame_index": truth["frame_index"],
                "timestamp_ns": manifest_by_id[row_id]["timestamp_ns"], "anatomical_side": side,
                "human_truth": truth[f"visible_{side}"], "wilor_present": bool_text(pred[side]),
                "outcome": outcome, "detection_count": len(side_detections),
                "max_confidence": max((float(d["confidence"]) for d in side_detections), default=""),
                "dwpose_frozen_presence": bool_text(dw[side]),
            })
        frame_row = {
            "annotation_row_id": row_id, "sequence_id": truth["sequence_id"],
            "signer_id": truth["signer_id"], "gloss": truth["gloss"],
            "frame_index": truth["frame_index"], "timestamp_ns": manifest_by_id[row_id]["timestamp_ns"],
            "image_sha256": truth["image_sha256"], "human_visible_left": truth["visible_left"],
            "human_visible_right": truth["visible_right"], "human_any_visible": bool_text(any_visible),
            "human_zero_hand": truth["zero_hand"], "human_rest": truth["rest"],
            "human_entering": truth["entering"], "human_leaving": truth["leaving"],
            "wilor_left": bool_text(pred["left"]), "wilor_right": bool_text(pred["right"]),
            "wilor_any": bool_text(any_pred), "wilor_detection_count": len(frame_detections),
            "wilor_both_anatomical_sides": bool_text(all(pred.values())),
            "dwpose_left": bool_text(dw["left"]), "dwpose_right": bool_text(dw["right"]),
            "dwpose_any": bool_text(any(dw.values())),
        }
        frame_rows.append(frame_row)
        if one_visible:
            visible_side = "left" if visible["left"] else "right"
            opposite = "right" if visible_side == "left" else "left"
            one_hand_rows.append({
                **frame_row, "visible_side": visible_side,
                "visible_side_detected": bool_text(pred[visible_side]),
                "opposite_slot_false_presence": bool_text(pred[opposite]),
            })
        if truth["zero_hand"] == "YES" or truth["rest"] == "YES":
            zero_rest_rows.append({
                **frame_row,
                "true_zero_hand": truth["zero_hand"],
                "explicit_rest": truth["rest"],
                "rest_with_visible_hand": bool_text(truth["rest"] == "YES" and any_visible),
            })
        if truth["entering"] == "YES" or truth["leaving"] == "YES":
            entry_leaving_rows.append(frame_row)

        for side in ("left", "right"):
            if visible[side]:
                pairwise_type = (
                    "WILOR_HIT_DWPOSE_HIT" if pred[side] and dw[side]
                    else "WILOR_HIT_DWPOSE_MISS" if pred[side]
                    else "WILOR_MISS_DWPOSE_HIT" if dw[side]
                    else "BOTH_MISS"
                )
                pairwise_rows.append({
                    "annotation_row_id": row_id, "sequence_id": truth["sequence_id"],
                    "frame_index": truth["frame_index"], "scope": "VISIBLE_HAND_SLOT",
                    "anatomical_side": side, "human_truth": "VISIBLE",
                    "wilor_present": bool_text(pred[side]), "dwpose_present": bool_text(dw[side]),
                    "pairwise_category": pairwise_type,
                })
        if truth["zero_hand"] == "YES":
            wilor_rejects = not any_pred
            dwpose_rejects = not any(dw.values())
            pairwise_type = (
                "WILOR_REJECTS_DWPOSE_REJECTS" if wilor_rejects and dwpose_rejects
                else "WILOR_REJECTS_DWPOSE_HALLUCINATES" if wilor_rejects
                else "WILOR_FIRES_DWPOSE_REJECTS" if dwpose_rejects
                else "BOTH_FIRE"
            )
            pairwise_rows.append({
                "annotation_row_id": row_id, "sequence_id": truth["sequence_id"],
                "frame_index": truth["frame_index"], "scope": "ZERO_HAND_FRAME",
                "anatomical_side": "", "human_truth": "ZERO_HAND",
                "wilor_present": bool_text(any_pred), "dwpose_present": bool_text(any(dw.values())),
                "pairwise_category": pairwise_type,
            })

    atomic_write_csv(SLOT_RESULTS_OUT, slot_rows)
    atomic_write_csv(FRAME_RESULTS_OUT, frame_rows)
    atomic_write_csv(ONE_HAND_OUT, one_hand_rows)
    atomic_write_csv(ZERO_REST_OUT, zero_rest_rows)
    atomic_write_csv(ENTRY_LEAVING_OUT, entry_leaving_rows)
    atomic_write_csv(PAIRWISE_OUT, pairwise_rows)

    tp, fp, tn, fn = (confusion[key] for key in ("TP", "FP", "TN", "FN"))
    visible_frames = [row for row in frame_rows if row["human_any_visible"] == "YES"]
    zero_frames = [row for row in frame_rows if row["human_zero_hand"] == "YES"]
    rest_frames = [row for row in frame_rows if row["human_rest"] == "YES"]
    rest_zero_frames = [row for row in rest_frames if row["human_zero_hand"] == "YES"]
    two_frames = [row for row in frame_rows if row["human_visible_left"] == "YES" and row["human_visible_right"] == "YES"]
    entering_frames = [row for row in entry_leaving_rows if row["human_entering"] == "YES"]
    leaving_frames = [row for row in entry_leaving_rows if row["human_leaving"] == "YES"]
    visible_pairwise = Counter(row["pairwise_category"] for row in pairwise_rows if row["scope"] == "VISIBLE_HAND_SLOT")
    zero_pairwise = Counter(row["pairwise_category"] for row in pairwise_rows if row["scope"] == "ZERO_HAND_FRAME")

    metrics = {
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "per_hand_precision": rate(tp, tp + fp),
        "per_hand_recall": rate(tp, tp + fn),
        "per_hand_specificity": rate(tn, tn + fp),
        "per_hand_f1": rate(2 * tp, 2 * tp + fp + fn),
        "any_visible_frame_recall": rate(sum(row["wilor_any"] == "YES" for row in visible_frames), len(visible_frames)),
        "one_hand_visible_recall": rate(sum(row["visible_side_detected"] == "YES" for row in one_hand_rows), len(one_hand_rows)),
        "opposite_slot_false_presence": rate(sum(row["opposite_slot_false_presence"] == "YES" for row in one_hand_rows), len(one_hand_rows)),
        "opposite_slot_false_count": sum(row["opposite_slot_false_presence"] == "YES" for row in one_hand_rows),
        "zero_hand_false_presence": rate(sum(row["wilor_any"] == "YES" for row in zero_frames), len(zero_frames)),
        "zero_hand_false_count": sum(row["wilor_any"] == "YES" for row in zero_frames),
        "rest_activation_rate": rate(sum(row["wilor_any"] == "YES" for row in rest_frames), len(rest_frames)),
        "rest_activation_count": sum(row["wilor_any"] == "YES" for row in rest_frames),
        "rest_zero_hand_false_presence": rate(sum(row["wilor_any"] == "YES" for row in rest_zero_frames), len(rest_zero_frames)),
        "rest_zero_hand_false_count": sum(row["wilor_any"] == "YES" for row in rest_zero_frames),
        "rest_visible_hand_frames": sum(row["human_any_visible"] == "YES" for row in rest_frames),
        "complete_two_hand_retention": rate(sum(row["wilor_both_anatomical_sides"] == "YES" for row in two_frames), len(two_frames)),
        "complete_two_hand_count": sum(row["wilor_both_anatomical_sides"] == "YES" for row in two_frames),
        "two_hand_two_or_more_detection_rate": rate(sum(int(row["wilor_detection_count"]) >= 2 for row in two_frames), len(two_frames)),
        "entry_any_hand_recall": rate(sum(row["wilor_any"] == "YES" for row in entering_frames if row["human_any_visible"] == "YES"), sum(row["human_any_visible"] == "YES" for row in entering_frames)),
        "leaving_any_hand_recall": rate(sum(row["wilor_any"] == "YES" for row in leaving_frames if row["human_any_visible"] == "YES"), sum(row["human_any_visible"] == "YES" for row in leaving_frames)),
        "visible_pairwise": dict(visible_pairwise),
        "zero_hand_pairwise": dict(zero_pairwise),
        "counts": {
            "frames": len(frame_rows), "hand_slots": len(slot_rows), "visible_hand_observations": tp + fn,
            "one_hand_frames": len(one_hand_rows), "zero_hand_frames": len(zero_frames),
            "rest_frames": len(rest_frames), "rest_zero_hand_frames": len(rest_zero_frames),
            "two_hand_frames": len(two_frames), "entry_frames": len(entering_frames), "leaving_frames": len(leaving_frames),
        },
    }
    return metrics, {
        "slot": slot_rows, "frame": frame_rows, "one_hand": one_hand_rows,
        "zero_rest": zero_rest_rows, "entry_leaving": entry_leaving_rows, "pairwise": pairwise_rows,
    }


def runtime_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for field in ("preprocess_ms", "inference_ms", "postprocess_ms", "total_model_ms", "total_wall_ms"):
        values = [float(row[field]) for row in rows]
        summary[field] = {
            "p50": percentile(values, 0.50), "p95": percentile(values, 0.95),
            "max": max(values), "mean": statistics.fmean(values),
        }
    summary["peak_process_rss_bytes"] = max(int(row["peak_process_rss_bytes_so_far"]) for row in rows)
    return summary


def write_report(result: dict[str, Any], provenance: dict[str, Any]) -> None:
    metrics = result["metrics"]
    runtime = result["runtime"]
    gates = result["gates"]
    report = f"""# P4-C1 WiLoR-Det Eligibility Result

## Decision

**{result['classification']}**

This is a governed architecture-comparison benchmark, not a new untouched final holdout and
not a production Android result. WiLoR-Det was evaluated independently; it was not combined
with DWPose, E2, R1, MediaPipe, tracking, crops, or temporal logic.

## Frozen evidence and model identity

- Frozen evidence verified: **YES**
- Dataset SHA-256: `{EXPECTED_DATASET_SHA256}`
- Annotation SHA-256: `{EXPECTED_ANNOTATION_SHA256}`
- Frames processed: **458/458**
- Official source: `https://github.com/rolpotamias/WiLoR`
- Source commit: `{provenance['source_commit']}`
- Detector checkpoint: `detector.pt`
- Checkpoint SHA-256: `{EXPECTED_CHECKPOINT_SHA256}`
- Checkpoint size: {CHECKPOINT.stat().st_size:,} bytes
- Architecture: {provenance['detector_architecture']}
- Native task/classes: pose detector, `0=left`, `1=right`, 21x3 auxiliary keypoints
- Anatomical-side scoring valid: **YES**. The official class names and downstream `right`
  flag establish anatomical semantics; raw images are passed unmirrored.
- Operating point: confidence **0.30**, official class-aware IoU-NMS **0.70**, max detections 300
- Input/preprocessing: official Ultralytics 512-pixel stride-32 letterbox, BGR source to RGB
  tensor, `/255` scaling; no custom crop or preprocessing.

## Eligibility results

| Metric | Result | Gate | Status |
|---|---:|---:|---:|
| Visible-hand recall | {metrics['confusion']['tp']}/{metrics['counts']['visible_hand_observations']} = {pct(metrics['per_hand_recall'])} | >=98% | {gates['gate_1_visible_recall']} |
| One-hand visible recall | {sum(row['visible_side_detected'] == 'YES' for row in read_csv(ONE_HAND_OUT))}/{metrics['counts']['one_hand_frames']} = {pct(metrics['one_hand_visible_recall'])} | >=97% | {gates['gate_2_one_hand_recall']} |
| Zero-hand false presence | {metrics['zero_hand_false_count']}/{metrics['counts']['zero_hand_frames']} = {pct(metrics['zero_hand_false_presence'])} | <=10% | {gates['gate_3_zero_hand_fpr']} |
| Explicit-rest activation | {metrics['rest_activation_count']}/{metrics['counts']['rest_frames']} = {pct(metrics['rest_activation_rate'])} | <=10% | {gates['gate_4_rest_fpr']} |
| Complete two-hand retention | {metrics['complete_two_hand_count']}/{metrics['counts']['two_hand_frames']} = {pct(metrics['complete_two_hand_retention'])} | >=95% | {gates['gate_5_complete_two_hand']} |

The rest gate follows the preregistered all-rest denominator. Five of the 146 rest frames
contain a human-visible hand, so `rest activation` is not identical to eligibility error.
On the 141 frames that are both rest and human ZERO_HAND, false presence is
{metrics['rest_zero_hand_false_count']}/141 = {pct(metrics['rest_zero_hand_false_presence'])}.

Per-hand confusion: TP={metrics['confusion']['tp']}, FP={metrics['confusion']['fp']},
TN={metrics['confusion']['tn']}, FN={metrics['confusion']['fn']}. Precision is
{pct(metrics['per_hand_precision'])}, specificity {pct(metrics['per_hand_specificity'])}, and
F1 {pct(metrics['per_hand_f1'])}. Opposite-slot false presence occurred in
{metrics['opposite_slot_false_count']}/{metrics['counts']['one_hand_frames']} governed
one-hand frames ({pct(metrics['opposite_slot_false_presence'])}).

Entry any-hand recall: {pct(metrics['entry_any_hand_recall'])}. Leaving any-hand recall:
{pct(metrics['leaving_any_hand_recall'])}. This benchmark has no positive WEAK, blur,
occlusion, or contact labels, so it cannot support claims for those conditions.

## DWPose complementarity (no fusion)

Visible hand slots: `{json.dumps(metrics['visible_pairwise'], sort_keys=True)}`.

Human ZERO_HAND frames: `{json.dumps(metrics['zero_hand_pairwise'], sort_keys=True)}`.

These are pairwise diagnostics only. No hybrid rule was fitted or evaluated.

## Runtime diagnostics

- Backend: CPU / PyTorch
- Total model latency: p50 {runtime['total_model_ms']['p50']:.2f} ms, p95 {runtime['total_model_ms']['p95']:.2f} ms, max {runtime['total_model_ms']['max']:.2f} ms
- Wall latency: p50 {runtime['total_wall_ms']['p50']:.2f} ms, p95 {runtime['total_wall_ms']['p95']:.2f} ms
- Peak process RSS: {runtime['peak_process_rss_bytes'] / (1024 ** 2):.1f} MiB
- Checkpoint size: {CHECKPOINT.stat().st_size / (1024 ** 2):.1f} MiB

These are offline desktop CPU diagnostics, not Android FPS claims.

## Exportability and licensing

The native artifact is a PyTorch Ultralytics PoseModel with a fixed 512x512 reference input.
Ultralytics 8.1.34 exposes ONNX and TFLite export routes, and the checkpoint records static
export as its default; neither route was exercised here, so operator compatibility remains
unverified. No export or Android integration occurred.

**DEPLOYMENT_LICENSE_REVIEW_REQUIRED.** The WiLoR repository applies CC BY-NC-ND 4.0 to
its models, while the pinned Ultralytics dependency is AGPL-3.0 unless separately licensed.
This research result therefore does not establish proprietary/commercial deployment rights.

## Protocol boundaries

- No threshold sweep or post-result tuning.
- No full WiLoR reconstruction model or MANO dependency.
- No DWPose/WiLoR combination.
- No other detector, training, fine-tuning, Android, S4-S7, recognition, or `[96,258]` work.
"""
    atomic_write_text(REPORT_OUT, report)


def hash_outputs() -> dict[str, str]:
    paths = [
        PROVENANCE_OUT, INPUT_MANIFEST_OUT, RAW_DETECTIONS_OUT, SLOT_RESULTS_OUT,
        FRAME_RESULTS_OUT, ONE_HAND_OUT, ZERO_REST_OUT, ENTRY_LEAVING_OUT,
        PAIRWISE_OUT, RUNTIME_OUT, ENVIRONMENT_OUT, OUT / "p4c1_pip_freeze.txt",
        RESULT_JSON_OUT, REPORT_OUT,
    ]
    hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in paths}
    native_hashes = [sha256(path) for path in sorted(RAW_NATIVE_DIR.glob("*.json"))]
    hashes["raw_native_outputs_count"] = str(len(native_hashes))
    hashes["raw_native_outputs_aggregate_sha256"] = hashlib.sha256("\n".join(native_hashes).encode()).hexdigest()
    atomic_write_json(HASH_MANIFEST_OUT, hashes)
    return hashes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", choices=("full", "prepare"), default="full")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    truth_rows, inference_rows = verify_frozen_evidence()
    manifest = build_input_manifest(truth_rows, inference_rows)
    manifest_hash = sha256(INPUT_MANIFEST_OUT)
    environment = save_environment()

    model = YOLO(str(CHECKPOINT))
    identity = verify_official_model(model)
    provenance = {
        "created_utc": utc_now(),
        "experiment": "P4-C1_WILOR_DET_ONLY_ELIGIBILITY",
        "benchmark": "GOVERNED_P4C_ARCHITECTURE_COMPARISON_BENCHMARK",
        "repository_url": "https://github.com/rolpotamias/WiLoR",
        "source_commit": identity["commit"],
        "source_commit_utc": git_value("show", "-s", "--format=%cI", "HEAD"),
        "demo_sha256": sha256(OFFICIAL_DEMO),
        "source_license_sha256": sha256(OFFICIAL_LICENSE),
        "detector_architecture": "Ultralytics YOLOv8m-Pose-derived medium FCN (scale=m), 2 classes, 21x3 auxiliary keypoints",
        "detector_variant": "official/reference pretrained_models/detector.pt",
        "checkpoint_source": "https://huggingface.co/spaces/rolpotamias/WiLoR/resolve/main/pretrained_models/detector.pt",
        "checkpoint_path": str(CHECKPOINT.resolve()),
        "checkpoint_bytes": CHECKPOINT.stat().st_size,
        "checkpoint_sha256": sha256(CHECKPOINT),
        "checkpoint_internal_yaml": identity["yaml"],
        "class_names": identity["names"],
        "handedness_semantics": "0=anatomical left, 1=anatomical right; official downstream passes class ID as is_right and flips class 0 only",
        "input_mirroring": "NONE",
        "input_size": EXPECTED_IMGSZ,
        "preprocessing": "official Ultralytics letterbox (stride 32), BGR source -> RGB BCHW, uint8 / 255",
        "confidence": CONFIDENCE,
        "nms_iou": EXPECTED_NMS_IOU,
        "nms": "official Ultralytics class-aware NMS; max_det=300",
        "pre_threshold_count_exposed": False,
        "source_license": "CC-BY-NC-ND-4.0 per WiLoR README/license.txt",
        "checkpoint_license": "CC-BY-NC-ND-4.0 per WiLoR README applying the linked license to WiLoR models",
        "upstream_framework_license": "Ultralytics AGPL-3.0 or commercial enterprise license",
        "deployment_license_flag": "DEPLOYMENT_LICENSE_REVIEW_REQUIRED",
        "dataset_sha256": EXPECTED_DATASET_SHA256,
        "annotation_sha256": EXPECTED_ANNOTATION_SHA256,
        "input_manifest_sha256": manifest_hash,
        "runner_sha256": sha256(Path(__file__)),
        "environment": environment,
    }
    atomic_write_json(PROVENANCE_OUT, provenance)
    if args.command == "prepare":
        print(json.dumps({"prepared": True, "rows": len(manifest), "manifest_sha256": manifest_hash}, indent=2))
        return

    detections, runtime_rows = run_detector(manifest, model)
    if len(runtime_rows) != 458 or len(list(RAW_NATIVE_DIR.glob("*.json"))) != 458:
        raise RuntimeError("P4C1_INVALID: incomplete inference output")
    metrics, _ = score(truth_rows, manifest, detections)
    runtime = runtime_summary(runtime_rows)
    gates = {
        "gate_1_visible_recall": "PASS" if metrics["per_hand_recall"] >= 0.98 else "FAIL",
        "gate_2_one_hand_recall": "PASS" if metrics["one_hand_visible_recall"] >= 0.97 else "FAIL",
        "gate_3_zero_hand_fpr": "PASS" if metrics["zero_hand_false_presence"] <= 0.10 else "FAIL",
        "gate_4_rest_fpr": "PASS" if metrics["rest_activation_rate"] <= 0.10 else "FAIL",
        "gate_5_complete_two_hand": "PASS" if metrics["complete_two_hand_retention"] >= 0.95 else "FAIL",
    }
    if all(value == "PASS" for value in gates.values()):
        classification = "WILOR_ELIGIBILITY_PROMISING"
    elif gates["gate_1_visible_recall"] == "PASS" and gates["gate_2_one_hand_recall"] == "PASS":
        classification = "WILOR_DETECTION_STRONG_VERIFICATION_NEEDED"
    else:
        classification = "WILOR_DETECTION_RECALL_INSUFFICIENT"
    result = {
        "status": "P4C1_COMPLETE", "valid": True, "classification": classification,
        "frozen_evidence_verified": True, "frames_processed": len(runtime_rows),
        "anatomical_side_scoring_valid": True, "metrics": metrics,
        "runtime": runtime, "gates": gates, "provenance_path": str(PROVENANCE_OUT.resolve()),
        "report_path": str(REPORT_OUT.resolve()), "completed_utc": utc_now(),
    }
    atomic_write_json(RESULT_JSON_OUT, result)
    write_report(result, provenance)
    hash_outputs()
    print(json.dumps({
        "status": result["status"], "classification": classification,
        "frames_processed": len(runtime_rows), "metrics": metrics, "gates": gates,
        "report": str(REPORT_OUT),
    }, indent=2))


if __name__ == "__main__":
    main()
