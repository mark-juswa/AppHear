"""Run the single frozen P4-R1A SSDLite + RTMPose Hand5 experiment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import os
import platform
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import mmcv
import mmdet
import mmengine
import mmpose
import numpy as np
import psutil
import torch
import torchvision
from mmengine.registry import init_default_scope
from mmdet.apis import inference_detector, init_detector
from mmdet.utils import register_all_modules as register_mmdet
from mmpose.apis import inference_topdown, init_model
from mmpose.evaluation.functional import nms
from mmpose.utils import register_all_modules as register_mmpose


ROOT = Path("/mnt/f/ASL DATASET/5. Apphear3")
OUT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4r1a_rtmpose_hand5_targeted_recovery_01"
RESIDUAL = OUT / "p4r1a_residual_18_manifest.csv"
CONTROLS = OUT / "p4r1a_control_manifest.csv"
ROI_PROTOCOL = OUT / "p4r1a_roi_protocol.json"
DET_CONFIG = OUT / "source_snapshot/ssdlite_mobilenetv2_scratch_600e_onehand.py"
POSE_CONFIG = OUT / "source_snapshot/mmpose/configs/hand_2d_keypoint/rtmpose/hand5/rtmpose-m_8xb256-210e_hand5-256x256.py"
DET_CHECKPOINT = OUT / "models/ssdlite_mobilenetv2_scratch_600e_onehand-4f9f8686_20220523.pth"
POSE_CHECKPOINT = OUT / "models/rtmpose-m_simcc-hand5_pt-aic-coco_210e-256x256-74fb594_20230320.pth"
V2 = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4gt1r_schema_repair_v2_01/P4_ELIGIBILITY_TRUTH_V2.csv"

V2_SHA256 = "24f5d8d442702e3a27424ff7f55cc24f1338f5683e5988a6a4916557e1d4252d"
DET_SHA256 = "25bdc4b9774da5570e80bc059e758e5305f75f0c3598007e3f07ad1c763bc607"
POSE_SHA256 = "b74fb5941684fe13c337b8d4fce644293e12903fed5407f8b27921f107dc6003"
DET_ACCEPT_THRESHOLD = 0.30
EXTERNAL_NMS_IOU = 0.30

HAND_EDGES = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def linux_path(value: str) -> Path:
    normalized = value.replace("\\", "/")
    if len(normalized) >= 3 and normalized[1:3] == ":/":
        return Path(f"/mnt/{normalized[0].lower()}/{normalized[3:]}")
    return Path(normalized)


def atomic_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = fieldnames or (list(rows[0]) if rows else [])
    if not names:
        raise RuntimeError(f"P4R1A_EMPTY_SCHEMA:{path.name}")
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def percentile(values: list[float], quantile: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), quantile)) if values else float("nan")


def draw_hand(image: np.ndarray, points: np.ndarray, color: tuple[int, int, int], label: str) -> None:
    finite = np.isfinite(points).all(axis=1)
    for start, end in HAND_EDGES:
        if finite[start] and finite[end]:
            cv2.line(image, tuple(np.rint(points[start]).astype(int)), tuple(np.rint(points[end]).astype(int)), color, 2, cv2.LINE_AA)
    for point in points[finite]:
        cv2.circle(image, tuple(np.rint(point).astype(int)), 3, color, -1, cv2.LINE_AA)
    if finite.any():
        anchor = tuple(np.rint(points[np.flatnonzero(finite)[0]]).astype(int))
        cv2.putText(image, label, anchor, cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)


def verify_inputs() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    required = (RESIDUAL, CONTROLS, ROI_PROTOCOL, DET_CONFIG, POSE_CONFIG, DET_CHECKPOINT, POSE_CHECKPOINT, V2)
    if any(not path.is_file() for path in required):
        raise RuntimeError("P4R1A_SOURCE_INTEGRITY_FAILURE")
    if sha256(V2) != V2_SHA256 or sha256(DET_CHECKPOINT) != DET_SHA256 or sha256(POSE_CHECKPOINT) != POSE_SHA256:
        raise RuntimeError("P4R1A_SOURCE_INTEGRITY_FAILURE")
    residual, controls = read_csv(RESIDUAL), read_csv(CONTROLS)
    if len(residual) != 18 or len(controls) != 120:
        raise RuntimeError("P4R1A_SOURCE_INTEGRITY_FAILURE")
    for row in residual + controls:
        image_path = linux_path(row["source_image_path"])
        native_path = linux_path(row["native_output_path"])
        if not image_path.is_file() or not native_path.is_file():
            raise RuntimeError(f"P4R1A_SOURCE_INTEGRITY_FAILURE:{row['frame_id']}")
        if sha256(image_path) != row["source_sha256"] or sha256(native_path) != row["native_output_sha256"]:
            raise RuntimeError(f"P4R1A_SOURCE_INTEGRITY_FAILURE:{row['frame_id']}")
    return residual, controls


def model_smoke(detector: Any, pose_model: Any) -> dict[str, Any]:
    synthetic = np.zeros((320, 320, 3), dtype=np.uint8)
    init_default_scope("mmdet")
    det_result = inference_detector(detector, synthetic)
    init_default_scope("mmpose")
    pose_result = inference_topdown(
        pose_model,
        synthetic,
        bboxes=np.asarray([[64, 64, 256, 256]], dtype=np.float32),
        bbox_format="xyxy",
    )
    shape = tuple(pose_result[0].pred_instances.keypoints.shape)
    if shape != (1, 21, 2):
        raise RuntimeError(f"P4R1A_MODEL_OUTPUT_SHAPE_FAILURE:{shape}")
    return {
        "synthetic_nonbenchmark": True,
        "detector_native_outputs": int(len(det_result.pred_instances)),
        "pose_output_shape": list(shape),
        "flip_test": bool(pose_model.test_cfg.get("flip_test")),
    }


def run() -> None:
    residual, controls = verify_inputs()
    rows_by_frame: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in residual:
        rows_by_frame[row["frame_id"]].append({**row, "membership": "RESIDUAL"})
    for row in controls:
        rows_by_frame[row["frame_id"]].append({**row, "membership": row["control_type"]})

    register_mmpose()
    register_mmdet(init_default_scope=False)
    init_default_scope("mmdet")
    detector = init_detector(str(DET_CONFIG), str(DET_CHECKPOINT), device="cpu")
    init_default_scope("mmpose")
    pose_model = init_model(str(POSE_CONFIG), str(POSE_CHECKPOINT), device="cpu")
    smoke = model_smoke(detector, pose_model)

    process = psutil.Process()
    peak_rss = process.memory_info().rss
    raw_detections: list[dict[str, Any]] = []
    raw_keypoints: list[dict[str, Any]] = []
    runtime_rows: list[dict[str, Any]] = []
    frame_outputs: dict[str, list[dict[str, Any]]] = {}
    native_dir = OUT / "raw_native_outputs"
    native_dir.mkdir(parents=True, exist_ok=True)

    for frame_id in sorted(rows_by_frame):
        row = rows_by_frame[frame_id][0]
        image = cv2.imread(str(linux_path(row["source_image_path"])), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"P4R1A_SOURCE_INTEGRITY_FAILURE:{frame_id}")
        x1, y1, x2, y2 = (int(row[key]) for key in ("roi_x1", "roi_y1", "roi_x2", "roi_y2"))
        total_start = time.perf_counter_ns()
        pre_start = time.perf_counter_ns()
        roi = np.ascontiguousarray(image[y1:y2, x1:x2])
        preprocessing_ms = (time.perf_counter_ns() - pre_start) / 1e6

        init_default_scope("mmdet")
        det_start = time.perf_counter_ns()
        det_result = inference_detector(detector, roi)
        detector_ms = (time.perf_counter_ns() - det_start) / 1e6
        instances = det_result.pred_instances.cpu().numpy()
        boxes = np.asarray(instances.bboxes, dtype=np.float32)
        scores = np.asarray(instances.scores, dtype=np.float32)
        labels = np.asarray(instances.labels, dtype=np.int64)

        post_start = time.perf_counter_ns()
        candidate_indices = np.flatnonzero((labels == 0) & (scores > DET_ACCEPT_THRESHOLD))
        if len(candidate_indices):
            nms_input = np.concatenate((boxes[candidate_indices], scores[candidate_indices, None]), axis=1)
            keep_local = np.asarray(nms(nms_input, EXTERNAL_NMS_IOU), dtype=np.int64)
            accepted_indices = candidate_indices[keep_local]
        else:
            accepted_indices = np.empty((0,), dtype=np.int64)
        postprocess_ms = (time.perf_counter_ns() - post_start) / 1e6
        accepted_set = {int(index) for index in accepted_indices}

        outputs: list[dict[str, Any]] = []
        pose_times: list[float] = []
        for det_index in range(len(boxes)):
            box_roi = boxes[det_index]
            box_full = box_roi + np.asarray([x1, y1, x1, y1], dtype=np.float32)
            raw_detections.append(
                {
                    "frame_id": frame_id,
                    "detection_index": det_index,
                    "bbox_roi_xyxy_json": json.dumps(box_roi.tolist(), separators=(",", ":")),
                    "bbox_full_xyxy_json": json.dumps(box_full.tolist(), separators=(",", ":")),
                    "score": float(scores[det_index]),
                    "class_id": int(labels[det_index]),
                    "exposed_after_detector_internal_score_0_02_nms_0_45": "YES",
                    "accepted_score_gt_0_30_external_nms_0_30": "YES" if det_index in accepted_set else "NO",
                }
            )
            if det_index not in accepted_set:
                continue
            init_default_scope("mmpose")
            pose_start = time.perf_counter_ns()
            pose_results = inference_topdown(
                pose_model,
                roi,
                bboxes=box_roi[None, :],
                bbox_format="xyxy",
            )
            pose_ms = (time.perf_counter_ns() - pose_start) / 1e6
            pose_times.append(pose_ms)
            pred = pose_results[0].pred_instances
            points_roi = np.asarray(pred.keypoints[0], dtype=np.float32)
            point_scores = np.asarray(pred.keypoint_scores[0], dtype=np.float32)
            points_full = points_roi + np.asarray([x1, y1], dtype=np.float32)
            output = {
                "detection_index": int(det_index),
                "detector_score": float(scores[det_index]),
                "bbox_full_xyxy": box_full.tolist(),
                "keypoints_full": points_full.tolist(),
                "keypoint_scores": point_scores.tolist(),
                "pose_latency_ms": pose_ms,
            }
            outputs.append(output)
            raw_keypoints.append(
                {
                    "frame_id": frame_id,
                    "detection_index": det_index,
                    "detector_score": float(scores[det_index]),
                    "bbox_full_xyxy_json": json.dumps(box_full.tolist(), separators=(",", ":")),
                    "keypoints_21_xy_json": json.dumps(points_full.tolist(), separators=(",", ":")),
                    "keypoint_scores_21_json": json.dumps(point_scores.tolist(), separators=(",", ":")),
                    "pose_latency_ms": pose_ms,
                }
            )

        total_ms = (time.perf_counter_ns() - total_start) / 1e6
        peak_rss = max(peak_rss, process.memory_info().rss)
        frame_outputs[frame_id] = outputs
        runtime_rows.append(
            {
                "frame_id": frame_id,
                "memberships": ";".join(sorted(item["membership"] for item in rows_by_frame[frame_id])),
                "roi_rule": row["roi_rule"],
                "preprocessing_ms": preprocessing_ms,
                "detector_inference_ms": detector_ms,
                "nms_postprocess_ms": postprocess_ms,
                "pose_detections": len(outputs),
                "pose_total_ms": sum(pose_times),
                "pose_per_hand_ms_json": json.dumps(pose_times, separators=(",", ":")),
                "total_ms": total_ms,
                "native_detector_outputs": len(boxes),
                "accepted_detections": len(outputs),
            }
        )
        np.savez_compressed(
            native_dir / f"{frame_id}.npz",
            detector_bboxes_roi=boxes,
            detector_scores=scores,
            detector_labels=labels,
            accepted_detector_indices=accepted_indices,
            accepted_keypoints_full=np.asarray([item["keypoints_full"] for item in outputs], dtype=np.float32).reshape(-1, 21, 2),
            accepted_keypoint_scores=np.asarray([item["keypoint_scores"] for item in outputs], dtype=np.float32).reshape(-1, 21),
            roi_xyxy=np.asarray([x1, y1, x2, y2], dtype=np.int32),
            source_sha256=np.asarray(row["source_sha256"]),
            detector_checkpoint_sha256=np.asarray(DET_SHA256),
            pose_checkpoint_sha256=np.asarray(POSE_SHA256),
        )

    # Produce the 18 mandatory independent-review overlays.
    overlay_dir = OUT / "immutable_recovery_overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    review_queue: list[dict[str, Any]] = []
    for row in residual:
        image = cv2.imread(str(linux_path(row["source_image_path"])), cv2.IMREAD_COLOR)
        with np.load(linux_path(row["native_output_path"]), allow_pickle=False) as native:
            points = native["keypoints_133"]
            gated = native["gated_presence"].astype(bool)
        if gated[0]:
            draw_hand(image, points[91:112], (255, 180, 0), "Existing DWPose A")
        if gated[1]:
            draw_hand(image, points[112:133], (255, 180, 0), "Existing DWPose B")
        colors = ((255, 0, 255), (0, 255, 80), (0, 160, 255), (180, 80, 255))
        for index, output in enumerate(frame_outputs[row["frame_id"]]):
            color = colors[index % len(colors)]
            box = np.rint(np.asarray(output["bbox_full_xyxy"])).astype(int)
            cv2.rectangle(image, tuple(box[:2]), tuple(box[2:]), color, 2)
            draw_hand(image, np.asarray(output["keypoints_full"]), color, f"Recovery {index + 1}")
        cv2.putText(
            image,
            f"Recovery outputs: {len(frame_outputs[row['frame_id']])}",
            (8, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        overlay_path = overlay_dir / f"{row['residual_id']}.png"
        if not cv2.imwrite(str(overlay_path), image):
            raise RuntimeError("P4R1A_OVERLAY_WRITE_FAILURE")
        review_queue.append(
            {
                "residual_id": row["residual_id"],
                "frame_id": row["frame_id"],
                "source_sha256": row["source_sha256"],
                "overlay_path": str(overlay_path),
                "overlay_sha256": sha256(overlay_path),
                "accepted_recovery_outputs": len(frame_outputs[row["frame_id"]]),
            }
        )

    atomic_csv(
        OUT / "p4r1a_raw_detections.csv",
        raw_detections,
        [
            "frame_id", "detection_index", "bbox_roi_xyxy_json", "bbox_full_xyxy_json", "score", "class_id",
            "exposed_after_detector_internal_score_0_02_nms_0_45", "accepted_score_gt_0_30_external_nms_0_30",
        ],
    )
    atomic_csv(
        OUT / "p4r1a_raw_keypoints.csv",
        raw_keypoints,
        [
            "frame_id", "detection_index", "detector_score", "bbox_full_xyxy_json", "keypoints_21_xy_json",
            "keypoint_scores_21_json", "pose_latency_ms",
        ],
    )
    atomic_csv(OUT / "p4r1a_runtime_results.csv", runtime_rows)
    atomic_csv(OUT / "p4r1a_recovery_review_queue.csv", review_queue)
    atomic_csv(
        OUT / "p4r1a_recovery_review.csv",
        [
            {
                "residual_id": row["residual_id"],
                "overlay_sha256": row["overlay_sha256"],
                "review_label": "",
                "reviewer_status": "UNREVIEWED",
                "reviewed_utc": "",
                "revision_count": 0,
                "last_edit_utc": "",
                "last_edit_reason": "",
                "reviewer_note": "",
            }
            for row in review_queue
        ],
    )

    total_times = [float(row["total_ms"]) for row in runtime_rows]
    detector_times = [float(row["detector_inference_ms"]) for row in runtime_rows]
    pose_times_all = [float(value) for row in runtime_rows for value in json.loads(row["pose_per_hand_ms_json"])]
    atomic_json(
        OUT / "environment/environment_manifest.json",
        {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "torchvision": torchvision.__version__,
            "mmengine": mmengine.__version__,
            "mmcv": mmcv.__version__,
            "mmdet": mmdet.__version__,
            "mmpose": mmpose.__version__,
            "opencv": cv2.__version__,
            "numpy": np.__version__,
            "psutil": psutil.__version__,
            "backend": "CPU",
            "torch_threads": torch.get_num_threads(),
            "mmcv_compiled_ext": importlib.import_module("mmcv._ext") is not None,
            "peak_rss_bytes": peak_rss,
        },
    )
    atomic_json(
        OUT / "p4r1a_model_provenance.json",
        {
            "official_repository": "https://github.com/open-mmlab/mmpose",
            "official_source_commit": "0232d66f420f411451d277905a08ff8d541dc78e",
            "mmpose_version": "1.1.0",
            "official_alias": "hand",
            "detector": {
                "architecture": "SSDLite-MobileNetV2",
                "variant": "one-class OneHand10K",
                "config": str(DET_CONFIG),
                "config_sha256": sha256(DET_CONFIG),
                "checkpoint": str(DET_CHECKPOINT),
                "checkpoint_sha256": sha256(DET_CHECKPOINT),
                "checkpoint_bytes": DET_CHECKPOINT.stat().st_size,
                "checkpoint_url": "https://download.openmmlab.com/mmpose/mmdet_pretrained/ssdlite_mobilenetv2_scratch_600e_onehand-4f9f8686_20220523.pth",
                "input": "320x320, keep_ratio=False, official DetDataPreprocessor BGR-to-RGB normalization",
                "internal_test_cfg": {"score_thr": 0.02, "nms_iou": 0.45, "max_per_img": 200},
                "official_inferencer_acceptance": {"score_strictly_greater_than": 0.30, "second_nms_iou": 0.30},
            },
            "hand_pose": {
                "architecture": "RTMPose-m",
                "config_name": "rtmpose-m_8xb256-210e_hand5-256x256",
                "config": str(POSE_CONFIG),
                "config_sha256": sha256(POSE_CONFIG),
                "checkpoint": str(POSE_CHECKPOINT),
                "checkpoint_sha256": sha256(POSE_CHECKPOINT),
                "checkpoint_bytes": POSE_CHECKPOINT.stat().st_size,
                "checkpoint_url": "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/rtmpose-m_simcc-hand5_pt-aic-coco_210e-256x256-74fb594_20230320.pth",
                "input": "256x256 official TopdownAffine",
                "output": "21 keypoints with native scores",
                "decoder": "SimCC split ratio 2.0",
                "flip_test": True,
                "training_collection": ["COCO-WholeBody-Hand", "OneHand10K", "FreiHand2d", "RHD2d", "Halpe"],
            },
            "code_licenses": {"MMPose": "Apache-2.0", "MMDetection": "Apache-2.0"},
            "weight_license_status": "No separate definitive checkpoint license bundled with the downloaded files",
            "dataset_terms_status": "Constituent Hand5 and OneHand10K dataset terms require separate production legal review",
            "deployment_license_flag": "DEPLOYMENT_LICENSE_REVIEW_REQUIRED",
            "export_observations": {
                "RTMPose": "Official MMDeploy documentation lists ONNX and ncnn routes; exact P4-R1A export not attempted",
                "SSDLite_detector": "MMDetection/MMDeploy model-family support exists, but exact artifact export not verified",
            },
        },
    )
    atomic_json(
        OUT / "p4r1a_inference_result.json",
        {
            "status": "P4R1A_RECOVERY_REVIEW_READY",
            "source_frames_processed": len(runtime_rows),
            "governed_memberships": 138,
            "residual_rows": 18,
            "control_rows": 120,
            "model_smoke": smoke,
            "accepted_recovery_outputs_total": len(raw_keypoints),
            "residual_output_count_distribution": dict(
                sorted(
                    defaultdict(int, {
                        count: sum(1 for row in review_queue if row["accepted_recovery_outputs"] == count)
                        for count in {row["accepted_recovery_outputs"] for row in review_queue}
                    }).items()
                )
            ),
            "runtime_diagnostic": {
                "total_p50_ms": statistics.median(total_times),
                "total_p95_ms": percentile(total_times, 95),
                "detector_p50_ms": statistics.median(detector_times),
                "detector_p95_ms": percentile(detector_times, 95),
                "pose_per_hand_p50_ms": statistics.median(pose_times_all) if pose_times_all else None,
                "pose_per_hand_p95_ms": percentile(pose_times_all, 95) if pose_times_all else None,
                "peak_rss_bytes": peak_rss,
            },
            "human_labels_invented": False,
            "controls_not_yet_physically_adjudicated": True,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run",))
    args = parser.parse_args()
    if args.command == "run":
        run()


if __name__ == "__main__":
    main()
