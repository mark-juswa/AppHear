# ruff: noqa: E501
"""Frozen P2-A DWPose-L whole-body perception evaluation under Linux.

This module intentionally supports one experiment identity only. It prepares the
immutable 350-row manifest, runs the exact native MMPose model, and scores the
preregistered spatial association without changing AppHear's runtime contract.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import cv2
import numpy as np

PROJECT = Path("/mnt/f/ASL DATASET/5. Apphear3")
POSITIVE_ROOT = Path(
    "/mnt/f/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/"
    "e2e_all_hand_gold_v1/engineering_01"
)
GOLD_REVIEW = POSITIVE_ROOT / "gold_review.csv"
INTERNAL_INDEX = POSITIVE_ROOT / "internal_index.csv"
NEGATIVE_MANIFEST = PROJECT / (
    "artifacts/recognition_upgrade/perception_backend_replacement/"
    "negative_gold_item_level_audit_01/finalization/NEGATIVE_GOLD_V1_MANIFEST.csv"
)
PAIRWISE_BASELINE = PROJECT / (
    "artifacts/recognition_upgrade/perception_backend_replacement/"
    "p0_rtmdet_detector_02/paired_mediapipe_vs_rtmdet.csv"
)
WINDOWS_ATTEMPT = PROJECT / (
    "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01"
)
CHECKPOINT = WINDOWS_ATTEMPT / "checkpoint/dw-ll_ucoco.pth"
CONFIG = WINDOWS_ATTEMPT / (
    "toolchain/source_snapshot/mmpose/configs/wholebody_2d_keypoint/rtmpose/ubody/"
    "rtmpose-l_8xb64-270e_coco-ubody-wholebody-256x192.py"
)
BASE_RUNTIME = WINDOWS_ATTEMPT / (
    "toolchain/source_snapshot/mmpose/configs/_base_/default_runtime.py"
)
OUTPUT = PROJECT / (
    "artifacts/recognition_upgrade/perception_backend_replacement/" "p2a_dwpose_l_linux_01"
)

EXPECTED_CHECKPOINT_SHA = "e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7"
EXPECTED_CONFIG_SHA = "b2e741d2428667c99e74218f5170a183337602755c76e5b4138546a9b59d5032"
EXPECTED_BASE_SHA = "ee312fa38881570117466e80a6325977d22062cc782f6a2f447b26a1db0687a0"
DWPOSE_SOURCE_COMMIT = "0232d66f420f411451d277905a08ff8d541dc78e"
LEFT_SLICE = slice(91, 112)
RIGHT_SLICE = slice(112, 133)
PALM_INDICES = np.asarray([0, 5, 9, 13, 17], dtype=np.int64)
JOINT_THRESHOLD = 0.30
MIN_CONFIDENT_JOINTS = 11


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.write_text(payload, encoding="utf-8")


def windows_to_wsl(raw: str) -> str:
    cleaned = raw.replace("\\\\", "\\")
    if len(cleaned) >= 3 and cleaned[1:3] == ":\\":
        drive = cleaned[0].lower()
        return f"/mnt/{drive}/{cleaned[3:].replace(chr(92), '/')}"
    return cleaned


def bool_value(raw: str) -> bool:
    return raw.strip().lower() in {"true", "yes", "1"}


def git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(PROJECT), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def verify_identity() -> dict[str, Any]:
    values = {
        "checkpoint": {
            "path": str(CHECKPOINT),
            "expected_sha256": EXPECTED_CHECKPOINT_SHA,
            "sha256": sha256_file(CHECKPOINT),
            "bytes": CHECKPOINT.stat().st_size,
        },
        "config": {
            "path": str(CONFIG),
            "expected_sha256": EXPECTED_CONFIG_SHA,
            "sha256": sha256_file(CONFIG),
            "bytes": CONFIG.stat().st_size,
        },
        "base_runtime": {
            "path": str(BASE_RUNTIME),
            "expected_sha256": EXPECTED_BASE_SHA,
            "sha256": sha256_file(BASE_RUNTIME),
            "bytes": BASE_RUNTIME.stat().st_size,
        },
        "source_commit": DWPOSE_SOURCE_COMMIT,
    }
    for name in ("checkpoint", "config", "base_runtime"):
        if values[name]["sha256"] != values[name]["expected_sha256"]:
            raise RuntimeError(f"Frozen {name} SHA-256 mismatch")
    return values


def environment_manifest() -> dict[str, Any]:
    import mmcv
    import mmcv._ext  # noqa: F401
    import mmdet
    import mmengine
    import mmpose
    import psutil
    import torch
    import torchvision
    from mmcv.ops import roi_align  # noqa: F401

    freeze = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    (OUTPUT / "environment").mkdir(parents=True, exist_ok=True)
    (OUTPUT / "environment/pip_freeze.txt").write_text(freeze, encoding="utf-8")
    return {
        "platform": platform.platform(),
        "kernel": platform.release(),
        "python": sys.version,
        "executable": sys.executable,
        "torch": torch.__version__,
        "torchvision": torchvision.__version__,
        "mmengine": mmengine.__version__,
        "mmcv": mmcv.__version__,
        "mmcv_compiled_ext": True,
        "mmdet": mmdet.__version__,
        "mmpose": mmpose.__version__,
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "psutil": psutil.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "ram_bytes": psutil.virtual_memory().total,
        "pip_freeze_sha256": sha256_file(OUTPUT / "environment/pip_freeze.txt"),
    }


def prepare_manifest() -> dict[str, Any]:
    identity = verify_identity()
    gold_rows = load_csv(GOLD_REVIEW)
    index_rows = {row["sample_id"]: row for row in load_csv(INTERNAL_INDEX)}
    negative_rows = load_csv(NEGATIVE_MANIFEST)
    if len(gold_rows) != 150 or len(negative_rows) != 200:
        raise RuntimeError(
            f"Frozen benchmark count mismatch: {len(gold_rows)} positive, "
            f"{len(negative_rows)} negative"
        )

    manifest: list[dict[str, Any]] = []
    for row in gold_rows:
        sample_id = row["sample_id"]
        index = index_rows[sample_id]
        path = Path(windows_to_wsl(index["center_image_path"]))
        manifest.append(
            {
                "manifest_row_id": f"positive_{sample_id}",
                "benchmark_type": "POSITIVE_GOLD",
                "sample_id": sample_id,
                "source_id": sample_id,
                "source_path_original": index["center_image_path"],
                "source_path_wsl": str(path),
                "image_width": int(index["image_width"]),
                "image_height": int(index["image_height"]),
                "sha256": sha256_file(path),
            }
        )
    for row in negative_rows:
        path = Path(windows_to_wsl(row["image_path"]))
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"Cannot decode frozen negative image: {path}")
        height, width = image.shape[:2]
        digest = sha256_file(path)
        if digest != row["image_sha256"]:
            raise RuntimeError(f"Negative source SHA mismatch: {row['negative_gold_id']}")
        manifest.append(
            {
                "manifest_row_id": row["negative_gold_id"],
                "benchmark_type": "NEGATIVE_GOLD_V1",
                "sample_id": row["negative_gold_id"],
                "source_id": row["source_id"],
                "source_path_original": row["image_path"],
                "source_path_wsl": str(path),
                "image_width": width,
                "image_height": height,
                "sha256": digest,
            }
        )
    if len(manifest) != 350:
        raise RuntimeError(f"Expected 350 manifest rows, got {len(manifest)}")

    manifest_path = OUTPUT / "frozen_input_manifest_350.csv"
    write_csv(manifest_path, manifest)
    manifest_sha = sha256_file(manifest_path)
    provenance = {
        "experiment": "P2-A DWPose-L 256x192 whole-body Linux continuation",
        "historical_windows_status": "INCONCLUSIVE_P2A",
        "historical_windows_reason": "Windows/full-MMCV build environment blocker",
        "branch": git_value("branch", "--show-current"),
        "head": git_value("rev-parse", "HEAD"),
        "working_tree_status": git_value("status", "--short"),
        "identity": identity,
        "gold_review": {"path": str(GOLD_REVIEW), "sha256": sha256_file(GOLD_REVIEW)},
        "internal_index": {
            "path": str(INTERNAL_INDEX),
            "sha256": sha256_file(INTERNAL_INDEX),
        },
        "negative_manifest": {
            "path": str(NEGATIVE_MANIFEST),
            "sha256": sha256_file(NEGATIVE_MANIFEST),
        },
        "baseline_pairwise": {
            "path": str(PAIRWISE_BASELINE),
            "sha256": sha256_file(PAIRWISE_BASELINE),
        },
        "input_manifest": {
            "path": str(manifest_path),
            "sha256": manifest_sha,
            "rows": 350,
            "positive_rows": 150,
            "negative_rows": 200,
            "rows_not_collapsed_on_source_byte_overlap": True,
        },
        "frozen_rules": {
            "roi": "[0,0,image_width,image_height]",
            "padding": 1.25,
            "input_size_width_height": [192, 256],
            "input_aspect": "3:4 width:height",
            "flip_test": True,
            "left_hand_indices_inclusive": [91, 111],
            "right_hand_indices_inclusive": [112, 132],
            "joint_score_threshold": JOINT_THRESHOLD,
            "minimum_confident_joints": MIN_CONFIDENT_JOINTS,
            "palm_local_indices": PALM_INDICES.tolist(),
            "minimum_points_inside_gt_fraction": 0.5,
            "anatomical_identity_scored": False,
        },
        "prepared_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(OUTPUT / "provenance_manifest.json", provenance)
    environment = environment_manifest()
    write_json(OUTPUT / "environment/environment_manifest.json", environment)
    return provenance


def verify_frozen_manifest() -> list[dict[str, str]]:
    path = OUTPUT / "frozen_input_manifest_350.csv"
    provenance = json.loads((OUTPUT / "provenance_manifest.json").read_text(encoding="utf-8"))
    if sha256_file(path) != provenance["input_manifest"]["sha256"]:
        raise RuntimeError("Frozen input manifest hash changed")
    rows = load_csv(path)
    if len(rows) != 350:
        raise RuntimeError(f"Frozen input manifest has {len(rows)} rows")
    for row in rows:
        source = Path(row["source_path_wsl"])
        if sha256_file(source) != row["sha256"]:
            raise RuntimeError(f"Source hash changed: {row['manifest_row_id']}")
        image = cv2.imread(str(source), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"Source cannot decode: {row['manifest_row_id']}")
        if image.shape[1] != int(row["image_width"]) or image.shape[0] != int(row["image_height"]):
            raise RuntimeError(f"Source dimensions changed: {row['manifest_row_id']}")
    return rows


def official_affines(
    width: int, height: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    from mmpose.datasets.transforms import TopdownAffine
    from mmpose.structures.bbox import bbox_xyxy2cs, get_warp_matrix

    bbox = np.asarray([[0.0, 0.0, float(width), float(height)]], dtype=np.float32)
    centers, scales = bbox_xyxy2cs(bbox, padding=1.25)
    scales = TopdownAffine(input_size=(192, 256))._fix_aspect_ratio(scales, aspect_ratio=192 / 256)
    affine = get_warp_matrix(centers[0], scales[0], 0.0, output_size=(192, 256))
    inverse = cv2.invertAffineTransform(affine)
    return centers[0], scales[0], affine, inverse


def save_npz_atomic(path: Path, **values: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(handle, **values)
    os.replace(temporary, path)


def run_inference() -> dict[str, Any]:
    import psutil
    import torch
    from mmengine.dataset import Compose, pseudo_collate
    from mmengine.registry import init_default_scope
    from mmpose.apis import init_model
    from mmpose.utils import register_all_modules

    rows = verify_frozen_manifest()
    verify_identity()
    register_all_modules()
    model = init_model(str(CONFIG), str(CHECKPOINT), device="cpu")
    if model.cfg.codec["input_size"] != (192, 256):
        raise RuntimeError("Frozen model input size changed")
    if model.cfg.codec["simcc_split_ratio"] != 2.0:
        raise RuntimeError("Frozen SimCC split ratio changed")
    if not model.cfg.model.test_cfg.get("flip_test", False):
        raise RuntimeError("Frozen flip_test is not enabled")
    if model.cfg.model.head.get("out_channels") != 133:
        raise RuntimeError("Frozen output path is not 133 keypoints")
    init_default_scope(model.cfg.get("default_scope", "mmpose"))
    pipeline = Compose(model.cfg.test_dataloader.dataset.pipeline)
    raw_dir = OUTPUT / "raw_outputs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if any(raw_dir.glob("*.npz")):
        raise RuntimeError("Raw output directory is not empty; refusing to mix runs")

    process = psutil.Process()
    peak_rss = process.memory_info().rss
    timings: list[dict[str, Any]] = []
    started = time.perf_counter()
    for ordinal, row in enumerate(rows, start=1):
        source = Path(row["source_path_wsl"])
        t0 = time.perf_counter()
        image = cv2.imread(str(source), cv2.IMREAD_COLOR)
        height, width = image.shape[:2]
        info: dict[str, Any] = {
            "img": image,
            "bbox": np.asarray([[0.0, 0.0, float(width), float(height)]], dtype=np.float32),
            "bbox_score": np.ones(1, dtype=np.float32),
        }
        info.update(model.dataset_meta)
        data = pipeline(info)
        batch = pseudo_collate([data])
        t1 = time.perf_counter()
        with torch.no_grad():
            result = model.test_step(batch)[0]
        t2 = time.perf_counter()
        keypoints = np.asarray(result.pred_instances.keypoints[0], dtype=np.float32)
        scores = np.asarray(result.pred_instances.keypoint_scores[0], dtype=np.float32)
        if keypoints.shape != (133, 2) or scores.shape != (133,):
            raise RuntimeError(
                f"Invalid native output at {row['manifest_row_id']}: "
                f"{keypoints.shape}, {scores.shape}"
            )
        if not np.isfinite(keypoints).all() or not np.isfinite(scores).all():
            raise RuntimeError(f"Non-finite native output: {row['manifest_row_id']}")
        center, scale, affine, inverse = official_affines(width, height)
        left_scores = scores[LEFT_SLICE]
        right_scores = scores[RIGHT_SLICE]
        confident_counts = np.asarray(
            [
                np.count_nonzero(left_scores >= JOINT_THRESHOLD),
                np.count_nonzero(right_scores >= JOINT_THRESHOLD),
            ],
            dtype=np.int16,
        )
        present = confident_counts >= MIN_CONFIDENT_JOINTS
        t3 = time.perf_counter()
        timing = {
            "preprocessing_ms": (t1 - t0) * 1000.0,
            "inference_ms": (t2 - t1) * 1000.0,
            "postprocessing_ms": (t3 - t2) * 1000.0,
            "total_ms": (t3 - t0) * 1000.0,
        }
        save_npz_atomic(
            raw_dir / f"{row['manifest_row_id']}.npz",
            keypoints_133=keypoints,
            scores_133=scores,
            left_hand_keypoints=keypoints[LEFT_SLICE],
            left_hand_scores=left_scores,
            right_hand_keypoints=keypoints[RIGHT_SLICE],
            right_hand_scores=right_scores,
            confident_joint_counts=confident_counts,
            gated_presence=present,
            roi_xyxy=np.asarray([0.0, 0.0, float(width), float(height)], dtype=np.float32),
            bbox_center=center,
            bbox_scale=scale,
            affine=affine,
            inverse_affine=inverse,
            timings_ms=np.asarray(list(timing.values()), dtype=np.float64),
            manifest_row_id=np.asarray(row["manifest_row_id"]),
            source_sha256=np.asarray(row["sha256"]),
            checkpoint_sha256=np.asarray(EXPECTED_CHECKPOINT_SHA),
            config_sha256=np.asarray(EXPECTED_CONFIG_SHA),
        )
        timings.append({"manifest_row_id": row["manifest_row_id"], **timing})
        peak_rss = max(peak_rss, process.memory_info().rss)
        if ordinal == 1 or ordinal % 10 == 0 or ordinal == len(rows):
            print(
                json.dumps(
                    {
                        "processed": ordinal,
                        "total": len(rows),
                        "last_total_ms": timing["total_ms"],
                    }
                ),
                flush=True,
            )
    write_csv(OUTPUT / "timings.csv", timings)
    summary = {
        "processed": len(rows),
        "elapsed_s": time.perf_counter() - started,
        "peak_host_rss_bytes": peak_rss,
        "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(OUTPUT / "inference_completion.json", summary)
    return summary


def group_data(raw: Any, side: str) -> dict[str, Any]:
    prefix = "left" if side == "left" else "right"
    points = np.asarray(raw[f"{prefix}_hand_keypoints"], dtype=np.float64)
    scores = np.asarray(raw[f"{prefix}_hand_scores"], dtype=np.float64)
    count = int(np.count_nonzero(scores >= JOINT_THRESHOLD))
    return {
        "name": side,
        "points": points,
        "scores": scores,
        "confident_count": count,
        "present": count >= MIN_CONFIDENT_JOINTS,
        "score_min": float(scores.min()),
        "score_mean": float(scores.mean()),
        "score_median": float(np.median(scores)),
        "score_max": float(scores.max()),
    }


def association_diagnostic(group: dict[str, Any], box: np.ndarray) -> dict[str, Any]:
    points = group["points"]
    palm = points[PALM_INDICES].mean(axis=0)
    inside_points = (
        (points[:, 0] >= box[0])
        & (points[:, 0] <= box[2])
        & (points[:, 1] >= box[1])
        & (points[:, 1] <= box[3])
    )
    palm_inside = bool(box[0] <= palm[0] <= box[2] and box[1] <= palm[1] <= box[3])
    coverage = float(np.mean(inside_points))
    center = np.asarray([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])
    diagonal = max(float(np.hypot(box[2] - box[0], box[3] - box[1])), 1e-12)
    distance = float(np.linalg.norm(palm - center) / diagonal)
    return {
        "eligible": palm_inside and coverage >= 0.5,
        "palm_inside": palm_inside,
        "point_coverage": coverage,
        "normalized_palm_distance": distance,
        "palm_x": float(palm[0]),
        "palm_y": float(palm[1]),
    }


def exact_match(
    groups: list[dict[str, Any]], boxes: list[np.ndarray], gated: bool
) -> tuple[dict[int, int], dict[tuple[int, int], dict[str, Any]]]:
    diagnostics = {
        (group_index, box_index): association_diagnostic(group, box)
        for group_index, group in enumerate(groups)
        for box_index, box in enumerate(boxes)
    }
    eligible_pairs = [
        pair
        for pair, diag in diagnostics.items()
        if diag["eligible"] and (not gated or groups[pair[0]]["present"])
    ]
    candidates: list[list[tuple[int, int]]] = [[]]
    for size in range(1, min(len(groups), len(boxes)) + 1):
        for pairs in itertools.combinations(eligible_pairs, size):
            if (
                len({pair[0] for pair in pairs}) == size
                and len({pair[1] for pair in pairs}) == size
            ):
                candidates.append(list(pairs))
    best = max(
        candidates,
        key=lambda pairs: (
            len(pairs),
            sum(diagnostics[pair]["point_coverage"] for pair in pairs),
            -sum(diagnostics[pair]["normalized_palm_distance"] for pair in pairs),
            tuple((-pair[0], -pair[1]) for pair in sorted(pairs)),
        ),
    )
    return {box_index: group_index for group_index, box_index in best}, diagnostics


def metric_fraction(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "fraction": numerator / denominator if denominator else None,
        "percent": 100.0 * numerator / denominator if denominator else None,
    }


def percentile(values: Iterable[float], quantile: float) -> float | None:
    values = list(values)
    return float(np.percentile(values, quantile)) if values else None


def score_results() -> dict[str, Any]:
    manifest = verify_frozen_manifest()
    completion = json.loads((OUTPUT / "inference_completion.json").read_text(encoding="utf-8"))
    if completion["processed"] != 350:
        raise RuntimeError("Inference is incomplete")
    gold = {row["sample_id"]: row for row in load_csv(GOLD_REVIEW)}
    baseline_rows = load_csv(PAIRWISE_BASELINE)
    baseline = {(row["sample_id"], int(row["gold_index"])): row for row in baseline_rows}
    if len(baseline) != 184:
        raise RuntimeError(f"Expected 184 frozen baseline hands, got {len(baseline)}")

    hand_rows: list[dict[str, Any]] = []
    frame_rows: list[dict[str, Any]] = []
    negative_rows: list[dict[str, Any]] = []
    for manifest_row in manifest:
        raw = np.load(OUTPUT / "raw_outputs" / f"{manifest_row['manifest_row_id']}.npz")
        groups = [group_data(raw, "left"), group_data(raw, "right")]
        if manifest_row["benchmark_type"] == "NEGATIVE_GOLD_V1":
            left, right = groups
            negative_rows.append(
                {
                    "manifest_row_id": manifest_row["manifest_row_id"],
                    "negative_gold_id": manifest_row["sample_id"],
                    "source_id": manifest_row["source_id"],
                    "source_sha256": manifest_row["sha256"],
                    "left_confident_joint_count": left["confident_count"],
                    "right_confident_joint_count": right["confident_count"],
                    "gated_left_presence": left["present"],
                    "gated_right_presence": right["present"],
                    "gated_any_presence": left["present"] or right["present"],
                    "gated_group_count": int(left["present"]) + int(right["present"]),
                    "left_score_mean": left["score_mean"],
                    "left_score_max": left["score_max"],
                    "right_score_mean": right["score_mean"],
                    "right_score_max": right["score_max"],
                    "interpretation": "FORCED_ROI_NEGATIVE_STRESS_TEST",
                }
            )
            continue

        sample_id = manifest_row["sample_id"]
        gold_row = gold[sample_id]
        width = int(manifest_row["image_width"])
        height = int(manifest_row["image_height"])
        boxes = []
        for hand in json.loads(gold_row["gold_hands_json"]):
            boxes.append(
                np.asarray(
                    [
                        float(hand["x_min"]) * width,
                        float(hand["y_min"]) * height,
                        float(hand["x_max"]) * width,
                        float(hand["y_max"]) * height,
                    ],
                    dtype=np.float64,
                )
            )
        ungated_matches, ungated_diagnostics = exact_match(groups, boxes, gated=False)
        gated_matches, gated_diagnostics = exact_match(groups, boxes, gated=True)
        for gold_index, box in enumerate(boxes):
            frozen = baseline[(sample_id, gold_index)]
            ungated_group_index = ungated_matches.get(gold_index)
            gated_group_index = gated_matches.get(gold_index)
            best_index = max(
                range(2),
                key=lambda index: (
                    ungated_diagnostics[(index, gold_index)]["point_coverage"],
                    -ungated_diagnostics[(index, gold_index)]["normalized_palm_distance"],
                ),
            )
            report_index = ungated_group_index if ungated_group_index is not None else best_index
            group = groups[report_index]
            diag = ungated_diagnostics[(report_index, gold_index)]
            mp_hit = bool_value(frozen["mediapipe_hit"])
            ug_hit = ungated_group_index is not None
            gated_hit = gated_group_index is not None
            hand_rows.append(
                {
                    "sample_id": sample_id,
                    "gold_index": gold_index,
                    "gt_x_min": box[0],
                    "gt_y_min": box[1],
                    "gt_x_max": box[2],
                    "gt_y_max": box[3],
                    "motion_blur": bool_value(gold_row["motion_blur"]),
                    "occlusion": bool_value(gold_row["occlusion"]),
                    "near_face": bool_value(gold_row["near_face"]),
                    "edge_clipped": bool_value(gold_row["edge_clipped"]),
                    "partial_visibility": bool_value(gold_row["partial_visibility"]),
                    "mediapipe_hit": mp_hit,
                    "dwpose_ungated_hit": ug_hit,
                    "dwpose_gated_hit": gated_hit,
                    "ungated_native_group": (
                        "" if ungated_group_index is None else groups[ungated_group_index]["name"]
                    ),
                    "gated_native_group": (
                        "" if gated_group_index is None else groups[gated_group_index]["name"]
                    ),
                    "diagnostic_native_group": group["name"],
                    "confident_joint_count": group["confident_count"],
                    "group_present": group["present"],
                    "score_min": group["score_min"],
                    "score_mean": group["score_mean"],
                    "score_median": group["score_median"],
                    "score_max": group["score_max"],
                    "palm_inside": diag["palm_inside"],
                    "point_coverage": diag["point_coverage"],
                    "normalized_palm_distance": diag["normalized_palm_distance"],
                    "ungated_pairwise_category": ("MP_HIT_" if mp_hit else "MP_MISS_")
                    + ("DWPOSE_HIT" if ug_hit else "DWPOSE_MISS"),
                    "gated_pairwise_category": ("MP_HIT_" if mp_hit else "MP_MISS_")
                    + ("DWPOSE_HIT" if gated_hit else "DWPOSE_MISS"),
                    "frozen_rtmdet_pairwise_category": frozen["pairwise_category"],
                }
            )
        count = len(boxes)
        ug_count = len(ungated_matches)
        gated_count = len(gated_matches)
        frame_rows.append(
            {
                "sample_id": sample_id,
                "visible_hand_count": count,
                "ungated_matched_hands": ug_count,
                "gated_matched_hands": gated_count,
                "ungated_any_hand_hit": count > 0 and ug_count > 0,
                "gated_any_hand_hit": count > 0 and gated_count > 0,
                "ungated_complete_two_hand": count == 2 and ug_count == 2,
                "gated_complete_two_hand": count == 2 and gated_count == 2,
                "left_confident_joint_count": groups[0]["confident_count"],
                "right_confident_joint_count": groups[1]["confident_count"],
            }
        )

    if len(hand_rows) != 184 or len(frame_rows) != 150 or len(negative_rows) != 200:
        raise RuntimeError(
            f"Scored row mismatch: {len(hand_rows)}, {len(frame_rows)}, {len(negative_rows)}"
        )
    write_csv(OUTPUT / "dwpose_gold_hand_results.csv", hand_rows)
    write_csv(OUTPUT / "dwpose_positive_frame_results.csv", frame_rows)
    write_csv(OUTPUT / "dwpose_negative_stress_results.csv", negative_rows)

    complementary = [
        row for row in hand_rows if row["frozen_rtmdet_pairwise_category"] == "MP_MISS_RTMDET_HIT"
    ]
    regression = [
        row for row in hand_rows if row["frozen_rtmdet_pairwise_category"] == "MP_HIT_RTMDET_MISS"
    ]
    hard_core = [row for row in hand_rows if row["frozen_rtmdet_pairwise_category"] == "BOTH_MISS"]
    if (len(complementary), len(regression), len(hard_core)) != (16, 25, 46):
        raise RuntimeError("Frozen diagnostic subset counts changed")
    write_csv(OUTPUT / "dwpose_complementary_16.csv", complementary)
    write_csv(OUTPUT / "dwpose_regression_25.csv", regression)
    write_csv(OUTPUT / "dwpose_hard_core_46.csv", hard_core)

    metrics: dict[str, Any] = {}
    for view, key in (("ungated", "dwpose_ungated_hit"), ("gated", "dwpose_gated_hit")):
        visible = sum(bool(row[key]) for row in hand_rows)
        any_frames = sum(
            bool(row[f"{view}_any_hand_hit"])
            for row in frame_rows
            if int(row["visible_hand_count"]) > 0
        )
        two_frames = sum(
            bool(row[f"{view}_complete_two_hand"])
            for row in frame_rows
            if int(row["visible_hand_count"]) == 2
        )
        two_instances = sum(
            bool(row[key])
            for row in hand_rows
            if sum(1 for candidate in hand_rows if candidate["sample_id"] == row["sample_id"]) == 2
        )
        view_metrics = {
            "visible_hand_instance_recall": metric_fraction(visible, 184),
            "any_hand_frame_recall": metric_fraction(any_frames, 117),
            "complete_two_hand_frame_recall": metric_fraction(two_frames, 67),
            "two_hand_instance_recall": metric_fraction(two_instances, 134),
        }
        for name, field, denominator in (
            ("motion_blur_instance_recall", "motion_blur", 120),
            ("occlusion_instance_recall", "occlusion", 25),
            ("edge_clipped_instance_recall", "edge_clipped", 31),
            ("partial_visibility_instance_recall", "partial_visibility", 6),
        ):
            numerator = sum(bool(row[key]) for row in hand_rows if bool(row[field]))
            view_metrics[name] = metric_fraction(numerator, denominator)
        mp_misses = [row for row in hand_rows if not bool(row["mediapipe_hit"])]
        mp_hits = [row for row in hand_rows if bool(row["mediapipe_hit"])]
        recovered = sum(bool(row[key]) for row in mp_misses)
        lost = sum(not bool(row[key]) for row in mp_hits)
        view_metrics["mediapipe_misses_recovered"] = metric_fraction(recovered, 62)
        view_metrics["mediapipe_hits_lost"] = metric_fraction(lost, 122)
        view_metrics["net_hand_change"] = recovered - lost
        view_metrics["pairwise"] = dict(
            Counter(row[f"{view}_pairwise_category"] for row in hand_rows)
        )
        view_metrics["hard_core_46_recovery"] = metric_fraction(
            sum(bool(row[key]) for row in hard_core), 46
        )
        view_metrics["complementary_16_recovery"] = metric_fraction(
            sum(bool(row[key]) for row in complementary), 16
        )
        view_metrics["regression_25_retained"] = metric_fraction(
            sum(bool(row[key]) for row in regression), 25
        )
        metrics[view] = view_metrics

    false_frames = sum(bool(row["gated_any_presence"]) for row in negative_rows)
    false_left = sum(bool(row["gated_left_presence"]) for row in negative_rows)
    false_right = sum(bool(row["gated_right_presence"]) for row in negative_rows)
    false_groups = sum(int(row["gated_group_count"]) for row in negative_rows)
    metrics["forced_roi_negative_stress_test"] = {
        "interpretation": "FORCED_ROI_NEGATIVE_STRESS_TEST_NOT_PRODUCTION_FALSE_POSITIVE_RATE",
        "gated_false_hand_present_frames": metric_fraction(false_frames, 200),
        "false_left_groups": false_left,
        "false_right_groups": false_right,
        "total_hallucinated_groups": false_groups,
        "presence_gate_or_upstream_person_gate_required": false_frames > 100,
    }

    timings = load_csv(OUTPUT / "timings.csv")
    for stage in ("preprocessing_ms", "inference_ms", "postprocessing_ms", "total_ms"):
        values = [float(row[stage]) for row in timings]
        metrics.setdefault("latency_ms", {})[stage] = {
            "mean": float(np.mean(values)),
            "p50": percentile(values, 50),
            "p95": percentile(values, 95),
            "max": max(values),
        }
    metrics["peak_host_rss_bytes"] = completion["peak_host_rss_bytes"]

    gate_results: dict[str, Any] = {
        "A_recover_at_least_15_of_62": {
            view: metrics[view]["mediapipe_misses_recovered"]["numerator"] >= 15
            for view in ("ungated", "gated")
        },
        "B_retain_at_least_20_of_regression_25": {
            view: metrics[view]["regression_25_retained"]["numerator"] >= 20
            for view in ("ungated", "gated")
        },
        "C_complete_two_hand_at_least_37_of_67": {
            view: metrics[view]["complete_two_hand_frame_recall"]["numerator"] >= 37
            for view in ("ungated", "gated")
        },
        "D_recover_at_least_15_of_hard_core_46": {
            view: metrics[view]["hard_core_46_recovery"]["numerator"] >= 15
            for view in ("ungated", "gated")
        },
    }
    gated_all = all(result["gated"] for result in gate_results.values())
    ungated_localization = (
        gate_results["A_recover_at_least_15_of_62"]["ungated"]
        and gate_results["C_complete_two_hand_at_least_37_of_67"]["ungated"]
        and gate_results["D_recover_at_least_15_of_hard_core_46"]["ungated"]
    )
    if (
        gated_all
        and not metrics["forced_roi_negative_stress_test"][
            "presence_gate_or_upstream_person_gate_required"
        ]
    ):
        classification = "ARCHITECTURE_PROMISING"
    elif ungated_localization and (
        not gated_all
        or metrics["forced_roi_negative_stress_test"][
            "presence_gate_or_upstream_person_gate_required"
        ]
    ):
        classification = "LOCALIZATION_PROMISING_PRESENCE_GATE_WEAK"
    else:
        classification = "ARCHITECTURE_NOT_MATERIAL"

    result = {
        "status": "P2A_DWPOSE_COMPLETE",
        "classification": classification,
        "processed": {
            "all": 350,
            "positive_frames": 150,
            "positive_hands": 184,
            "negative_frames": 200,
        },
        "metrics": metrics,
        "gates": gate_results,
        "scope": {
            "windows_attempt_preserved_as": "INCONCLUSIVE_P2A",
            "linux_is_same_frozen_experiment_continuation": True,
            "model_threshold_roi_matching_changed": False,
            "sapiens_run": False,
            "android_or_s4_s5_s6_s7_changed": False,
            "training_or_finetuning": False,
        },
    }
    write_json(OUTPUT / "p2a_dwpose_linux_result.json", result)
    write_report(result)
    return result


def format_metric(metric: dict[str, Any]) -> str:
    return f"{metric['numerator']}/{metric['denominator']} = {metric['percent']:.4f}%"


def write_report(result: dict[str, Any]) -> None:
    metrics = result["metrics"]
    ug = metrics["ungated"]
    gd = metrics["gated"]
    neg = metrics["forced_roi_negative_stress_test"]
    gates = result["gates"]
    provenance = json.loads((OUTPUT / "provenance_manifest.json").read_text(encoding="utf-8"))
    environment = json.loads(
        (OUTPUT / "environment/environment_manifest.json").read_text(encoding="utf-8")
    )
    report = f"""# P2-A DWPose-L Frozen Perception Result — WSL2/Linux continuation

Status: `P2A_DWPOSE_COMPLETE`  
Primary classification: `{result['classification']}`

## Experiment identity and validity

This is the Linux/WSL continuation of the same frozen P2-A experiment. The first Windows
attempt remains historically `INCONCLUSIVE_P2A` because the model never loaded: the blocker
was the Windows/full-MMCV build environment. No model, checkpoint, threshold, ROI, decoder,
flip-test, or matching rule changed in this continuation.

- checkpoint: `dw-ll_ucoco.pth`, SHA-256 `{EXPECTED_CHECKPOINT_SHA}`;
- config: `rtmpose-l_8xb64-270e_coco-ubody-wholebody-256x192.py`, SHA-256 `{EXPECTED_CONFIG_SHA}`;
- source commit: `{DWPOSE_SOURCE_COMMIT}`;
- input manifest: 350 rows, SHA-256 `{provenance['input_manifest']['sha256']}`;
- processing: 150/150 positive frames and 200/200 NEGATIVE_GOLD_V1 frames;
- native output: 133 keypoints; left 91..111, right 112..132.

## Environment

Python `{environment['python'].split()[0]}`, Torch `{environment['torch']}` CPU,
torchvision `{environment['torchvision']}`, MMEngine `{environment['mmengine']}`, full MMCV
`{environment['mmcv']}` with compiled ops, MMDetection `{environment['mmdet']}`, MMPose
`{environment['mmpose']}`, OpenCV `{environment['opencv']}`, NumPy `{environment['numpy']}`.

## Frozen inference and association

Every image used the complete source frame as `[0,0,width,height]`, official padding 1.25,
official 3:4 affine to 192x256, official SimCC decoding at split ratio 2.0, and enabled flip
testing. Ungated localization decodes and associates both native 21-joint blocks. Gated
localization additionally requires at least 11/21 native joint scores >=0.30. Association is
maximum-cardinality one-to-one, requires the five-point palm center inside the GT box and at
least 50% of hand points inside, then breaks ties by coverage and normalized palm distance.
Anatomical left/right identity is not scored because gold sides are unknown.

## Positive results

| Metric | Ungated LOCALIZED | Gated LOCALIZED_AND_PRESENT | Frozen MediaPipe |
|---|---:|---:|---:|
| Visible-hand instance recall | {format_metric(ug['visible_hand_instance_recall'])} | {format_metric(gd['visible_hand_instance_recall'])} | 122/184 = 66.3043% |
| Any-hand frame recall | {format_metric(ug['any_hand_frame_recall'])} | {format_metric(gd['any_hand_frame_recall'])} | 91/117 = 77.7778% |
| Complete two-hand frame recall | {format_metric(ug['complete_two_hand_frame_recall'])} | {format_metric(gd['complete_two_hand_frame_recall'])} | 31/67 = 46.2687% |
| Two-hand instance recall | {format_metric(ug['two_hand_instance_recall'])} | {format_metric(gd['two_hand_instance_recall'])} | 87/134 = 64.9254% |
| Motion-blur recall | {format_metric(ug['motion_blur_instance_recall'])} | {format_metric(gd['motion_blur_instance_recall'])} | 70/120 = 58.3333% |
| Occlusion recall | {format_metric(ug['occlusion_instance_recall'])} | {format_metric(gd['occlusion_instance_recall'])} | 13/25 = 52.0000% |
| Edge-clipped recall | {format_metric(ug['edge_clipped_instance_recall'])} | {format_metric(gd['edge_clipped_instance_recall'])} | 8/31 = 25.8065% |
| Partial-visibility recall | {format_metric(ug['partial_visibility_instance_recall'])} | {format_metric(gd['partial_visibility_instance_recall'])} | 1/6 = 16.6667% |

## Pairwise and protected diagnostic subsets

| Result | Ungated | Gated |
|---|---:|---:|
| MediaPipe misses recovered | {format_metric(ug['mediapipe_misses_recovered'])} | {format_metric(gd['mediapipe_misses_recovered'])} |
| MediaPipe hits lost | {format_metric(ug['mediapipe_hits_lost'])} | {format_metric(gd['mediapipe_hits_lost'])} |
| Net hand-instance change | {ug['net_hand_change']} | {gd['net_hand_change']} |
| PERCEPTION_HARD_CORE_46 recovered | {format_metric(ug['hard_core_46_recovery'])} | {format_metric(gd['hard_core_46_recovery'])} |
| RTMDET_COMPLEMENTARY_16 recovered | {format_metric(ug['complementary_16_recovery'])} | {format_metric(gd['complementary_16_recovery'])} |
| RTMDET_REGRESSION_25 retained | {format_metric(ug['regression_25_retained'])} | {format_metric(gd['regression_25_retained'])} |

The exact 184-, 46-, 16-, and 25-row item-level tables are saved with the result package.

## FORCED_ROI_NEGATIVE_STRESS_TEST

This is not a production end-to-end false-positive rate. DWPose was deliberately invoked on
all 200 frozen zero-hand images as if each complete image were a person ROI.

- gated false hand-present frames: {format_metric(neg['gated_false_hand_present_frames'])};
- false left groups: {neg['false_left_groups']};
- false right groups: {neg['false_right_groups']};
- total hallucinated groups: {neg['total_hallucinated_groups']};
- `PRESENCE_GATE_OR_UPSTREAM_PERSON_GATE_REQUIRED`: {str(neg['presence_gate_or_upstream_person_gate_required']).lower()}.

## Preregistered gates

| Gate | Ungated | Gated |
|---|---:|---:|
| A: recover >=15/62 MediaPipe misses | {'PASS' if gates['A_recover_at_least_15_of_62']['ungated'] else 'FAIL'} | {'PASS' if gates['A_recover_at_least_15_of_62']['gated'] else 'FAIL'} |
| B: retain >=20/25 regression cases | {'PASS' if gates['B_retain_at_least_20_of_regression_25']['ungated'] else 'FAIL'} | {'PASS' if gates['B_retain_at_least_20_of_regression_25']['gated'] else 'FAIL'} |
| C: complete >=37/67 two-hand frames | {'PASS' if gates['C_complete_two_hand_at_least_37_of_67']['ungated'] else 'FAIL'} | {'PASS' if gates['C_complete_two_hand_at_least_37_of_67']['gated'] else 'FAIL'} |
| D: recover >=15/46 HARD_CORE | {'PASS' if gates['D_recover_at_least_15_of_hard_core_46']['ungated'] else 'FAIL'} | {'PASS' if gates['D_recover_at_least_15_of_hard_core_46']['gated'] else 'FAIL'} |

## Runtime diagnostics

| Stage | Mean ms | p50 ms | p95 ms | Max ms |
|---|---:|---:|---:|---:|
"""
    for stage in ("preprocessing_ms", "inference_ms", "postprocessing_ms", "total_ms"):
        value = metrics["latency_ms"][stage]
        report += f"| {stage} | {value['mean']:.3f} | {value['p50']:.3f} | {value['p95']:.3f} | {value['max']:.3f} |\n"
    report += f"""

Peak host process RSS was {metrics['peak_host_rss_bytes'] / (1024 ** 3):.3f} GiB. CPU Python
runtime is diagnostic only and makes no Android FPS claim.

## Final classification

**`{result['classification']}`**

No Sapiens run, other model, threshold sweep, retry, person detector, training, fine-tuning,
Android modification, or S4/S5/S6/S7 change occurred. Native outputs were not mapped into
AppHear `[96,258]`.
"""
    report_path = OUTPUT / "P2A_DWPOSE_L_FROZEN_PERCEPTION_RESULT.md"
    report_path.write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run", "score", "all"))
    args = parser.parse_args()
    if args.command in {"prepare", "all"}:
        print(json.dumps(prepare_manifest(), indent=2), flush=True)
    if args.command in {"run", "all"}:
        print(json.dumps(run_inference(), indent=2), flush=True)
    if args.command in {"score", "all"}:
        print(json.dumps(score_results(), indent=2), flush=True)


if __name__ == "__main__":
    main()
