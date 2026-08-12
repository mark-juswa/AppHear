"""Bounded P2-P2 synchronized RGB ROI and crop-quality audit.

This module decodes only a stratified 40-sign pilot. It does not train a model,
materialize a training dataset, access Android assets, or modify Phase 1.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import math
import os
import random
import shutil
import sys
from collections import Counter, defaultdict
from functools import partial
from itertools import permutations
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np

from pipeline.crops.config import RoiConfig
from pipeline.crops.pose_roi import PoseRecoveryConfig, causal_pose_recovery_sequence
from pipeline.crops.roi import (
    RoiObservation,
    causal_roi_sequence,
    extract_square_crop,
    sharpness_variance,
)
from pipeline.tracking.e2e_gold import INDEX_FIELDS as GOLD_INDEX_FIELDS
from pipeline.tracking.e2e_gold import REVIEW_FIELDS as GOLD_REVIEW_FIELDS
from pipeline.tracking.e2e_gold_review import (
    ReviewApp as GoldReviewApp,
)
from pipeline.tracking.e2e_gold_review import (
    completion_error as gold_completion_error,
)
from pipeline.tracking.e2e_gold_review import (
    load_run as load_gold_run,
)
from pipeline.tracking.e2e_gold_review import (
    validate_run as validate_gold_run,
)

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = "phase2_p2_bounded_roi_crop_audit_v1"
DEFAULT_PREP = ROOT / "artifacts/recognition_upgrade/phase2_preparation/phase2_prep_01"
DEFAULT_CANONICAL_MANIFEST = ROOT / (
    "artifacts/recognition_upgrade/phase1_full_vocab/manifest_01/canonical_manifest.csv"
)
DEFAULT_OUTPUT = ROOT / "artifacts/recognition_upgrade/phase2_roi_audit/p2_p2_roi_audit_01"
DEFAULT_I320_MODEL = ROOT / (
    "artifacts/recognition_upgrade/e2e_c0/c0b_stage2_detector_01/models/"
    "mobilenet_v2_i320_100/export/model_float.tflite"
)
DEFAULT_I320_METRICS = ROOT / (
    "artifacts/recognition_upgrade/e2e_c0/c0b_stage2_detector_01/"
    "development_evaluation/mobilenet_v2_i320_100/development_metrics.json"
)
ROUTES = ("R0", "R1", "R2", "R3")
Box4 = tuple[float, float, float, float]
PROMOTABLE_ROUTES = ("R0", "R1", "R2")
ROUTE_NAMES = {
    "R0": "direct MediaPipe plus 100 ms causal hold",
    "R1": "direct MediaPipe plus pose tracking/fallback",
    "R2": "I320 detector proposals with anatomical anchor assignment",
    "R3": "expanded upper-body availability control",
}
ROUTE_REVIEW_FIELDS = ("audit_id", "verdict", "notes")
SIDE_REVIEW_FIELDS = ("sample_id", "assignment", "notes")
SIDE_INDEX_FIELDS = (
    "sample_id",
    "gloss",
    "signer_group_id",
    "gold_hands_json",
    "panel_path",
)
ROUTE_INDEX_FIELDS = (
    "audit_id",
    "sample_id",
    "route",
    "blind_candidate",
    "gloss",
    "signer_group_id",
    "split",
    "role",
    "frame_index",
    "timestamp_ms",
    "visible_hand_count",
    "gold_hands_json",
    "route_boxes_json",
    "roi_sources_json",
    "triplet_available_rate",
    "padding_fraction_max",
    "sharpness_min",
    "synchronization_error_ms",
    "panel_path",
)
VERDICTS = {
    "1": ("usable_complete", "Usable: all visible hands", "#18794e"),
    "2": ("incomplete_two_hand", "Only one of two hands usable", "#b54708"),
    "3": ("missing_roi", "Missing hand ROI", "#b42318"),
    "4": ("clipped", "Hand clipped by crop", "#b54708"),
    "5": ("motion_blur", "Too blurry", "#b54708"),
    "6": ("wrong_side", "Wrong hand / side swap", "#b42318"),
    "7": ("stale_desynced", "Stale or desynchronized", "#b42318"),
    "8": ("inconsistent", "Unstable across frames", "#6b4f9b"),
    "9": ("low_detail", "Too little hand detail", "#6b4f9b"),
    "0": ("other_failure", "Other failure", "#555555"),
    "v": ("no_visible_hand", "No hand visible in reference", "#555555"),
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _blind_id(seed: int, *values: object) -> str:
    payload = "|".join(str(value) for value in (seed, *values))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def select_pilot_rows(
    rows: list[dict[str, str]], labels: list[str], per_sign: int, seed: int
) -> list[dict[str, str]]:
    """Select signer-diverse train/val clips without using detector success."""
    if per_sign <= 0:
        raise ValueError("per_sign must be positive")
    rng = random.Random(seed)
    selected: list[dict[str, str]] = []
    for label in labels:
        candidates = [
            row
            for row in rows
            if row["canonical_gloss"] == label
            and row["split"] in {"train", "val"}
            and row["hybrid_metadata_eligible"].lower() == "true"
        ]
        rng.shuffle(candidates)
        recovery_stress = sorted(candidates, key=lambda row: float(row["any_direct_rate"]))
        articulation_stress = sorted(
            candidates,
            key=lambda row: max(
                float(row["near_face_rate"]),
                float(row["both_direct_rate"]),
                float(row["edge_risk_rate"]),
            ),
            reverse=True,
        )
        ordinary_control = sorted(
            candidates,
            key=lambda row: (
                float(row["any_direct_rate"])
                - 0.5 * float(row["edge_risk_rate"])
                - 0.25 * float(row["near_face_rate"])
            ),
            reverse=True,
        )
        strata = (recovery_stress, articulation_stress, ordinary_control)
        chosen: list[dict[str, str]] = []
        used_signers: set[str] = set()
        while len(chosen) < per_sign:
            stratum = strata[len(chosen) % len(strata)]
            candidate = next(
                (
                    row
                    for row in stratum
                    if row not in chosen and row["signer_group_id"] not in used_signers
                ),
                None,
            )
            if candidate is None:
                break
            chosen.append(candidate)
            used_signers.add(candidate["signer_group_id"])
        for candidate in candidates:
            if len(chosen) == per_sign:
                break
            if candidate not in chosen:
                chosen.append(candidate)
        if len(chosen) < per_sign:
            raise ValueError(f"{label}: requested {per_sign}, found {len(chosen)}")
        selected.extend(chosen)
    return selected


def _video_frames(path: Path, wanted: set[int]) -> tuple[dict[int, np.ndarray], float, int]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise OSError(f"cannot open video: {path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    frames: dict[int, np.ndarray] = {}
    try:
        for index in sorted(wanted):
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            if not ok:
                raise ValueError(f"video ended before frame {index}: {path}")
            frames[index] = frame
    finally:
        capture.release()
    return frames, fps, count


def _fit_panel(images: list[np.ndarray], width: int = 360) -> np.ndarray:
    fitted = []
    for image in images:
        height = max(1, round(image.shape[0] * width / image.shape[1]))
        fitted.append(cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA))
    target = min(image.shape[0] for image in fitted)
    return np.concatenate([image[:target] for image in fitted], axis=1)


def _stage_arrays(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as data:
        return {key: np.asarray(data[key]) for key in data.files}


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    if args.run_dir.exists():
        raise FileExistsError(f"run directory exists: {args.run_dir}")
    feasibility = _read_csv(args.prep_dir / "rgb_feasibility_manifest.csv")
    canonical_rows = _read_csv(args.canonical_manifest)
    canonical = {row["sample_id"]: row for row in canonical_rows}
    if len(canonical) != len(canonical_rows):
        raise ValueError("canonical manifest contains duplicate sample IDs")
    missing_lineage = [row["sample_id"] for row in feasibility if row["sample_id"] not in canonical]
    if missing_lineage:
        raise ValueError(f"feasibility rows absent from canonical manifest: {missing_lineage[:5]}")
    feasibility = [{**row, **canonical[row["sample_id"]]} for row in feasibility]
    pilot = json.loads((args.prep_dir / "pilot_vocabulary.json").read_text(encoding="utf-8"))
    labels = list(pilot["labels"])
    selected = select_pilot_rows(feasibility, labels, args.per_sign, args.seed)
    args.run_dir.mkdir(parents=True)
    center_dir = args.run_dir / "gold" / "center_images"
    context_dir = args.run_dir / "gold" / "context_panels"
    diagnostic_dir = args.run_dir / "gold" / "diagnostic_panels"
    for directory in (center_dir, context_dir, diagnostic_dir):
        directory.mkdir(parents=True)
    index_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    fractions = (0.25, 0.50, 0.75)
    for number, row in enumerate(selected, start=1):
        arrays = _stage_arrays(Path(row["stage_e_path"]))
        span = json.loads(Path(row["span_path"]).read_text(encoding="utf-8"))
        onset = max(0, int(span["onset"]))
        release = min(len(arrays["timestamps_ms"]) - 1, int(span["release"]))
        fraction = fractions[(number - 1) % len(fractions)]
        center = round(onset + fraction * (release - onset))
        if len(arrays["timestamps_ms"]) < 5:
            raise ValueError(f"too few frames for temporal audit: {row['sample_id']}")
        center = min(max(center, 2), len(arrays["timestamps_ms"]) - 3)
        indices = {center - 2, center, center + 2}
        frames, fps, video_count = _video_frames(Path(row["raw_video_path"]), indices)
        ordered = [frames[index] for index in sorted(indices)]
        sample_id = _blind_id(args.seed, row["sample_id"], center)
        center_path = center_dir / f"{sample_id}.png"
        context_path = context_dir / f"{sample_id}.jpg"
        diagnostic_path = diagnostic_dir / f"{sample_id}.jpg"
        cv2.imwrite(str(center_path), frames[center])
        panel = _fit_panel(ordered)
        cv2.putText(
            panel,
            "CENTER FRAME IS MIDDLE",
            (12, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
        )
        cv2.imwrite(str(context_path), panel, [cv2.IMWRITE_JPEG_QUALITY, 92])
        cv2.imwrite(str(diagnostic_path), panel, [cv2.IMWRITE_JPEG_QUALITY, 92])
        timestamp = int(arrays["timestamps_ms"][center])
        height, width = frames[center].shape[:2]
        index_rows.append(
            {
                "sample_id": sample_id,
                "clip_id": row["sample_id"],
                "video_file": row["raw_video_path"],
                "participant_id": row["signer_group_id"],
                "split": row["split"],
                "gloss": row["canonical_gloss"],
                "frame_index": center,
                "timestamp_ms": timestamp,
                "sampling_cadence": f"span_q{round(fraction * 100):02d}",
                "sampling_target_hand": "",
                "sampling_target_detected": "",
                "sampling_raw_detected_hands": "",
                "image_width": width,
                "image_height": height,
                "center_image_path": str(center_path.resolve()),
                "context_panel_path": str(context_path.resolve()),
                "diagnostic_panel_path": str(diagnostic_path.resolve()),
                "detected_hands_json": "[]",
                "pose_wrists_json": "[]",
            }
        )
        selected_rows.append(
            {
                **row,
                "audit_sample_id": sample_id,
                "center_frame_index": center,
                "context_frame_indices": json.dumps(sorted(indices)),
                "stage_timestamp_ms": timestamp,
                "video_fps": fps,
                "video_frame_count": video_count,
            }
        )
        print(f"[phase2/p2-p2] prepare {number}/{len(selected)} {row['canonical_gloss']}")
    gold_dir = args.run_dir / "gold"
    _write_csv(gold_dir / "internal_index.csv", GOLD_INDEX_FIELDS, index_rows)
    _write_csv(
        gold_dir / "gold_review.csv",
        GOLD_REVIEW_FIELDS,
        [{"sample_id": row["sample_id"], "source_mirrored": "unknown"} for row in index_rows],
    )
    _write_csv(
        args.run_dir / "selected_samples.csv",
        tuple(selected_rows[0].keys()),
        selected_rows,
    )
    summary = {
        "experiment": EXPERIMENT,
        "stage": "gold_evidence_prepared",
        "rows": len(selected_rows),
        "signs": len(labels),
        "per_sign": args.per_sign,
        "splits": dict(Counter(row["split"] for row in selected_rows)),
        "signers": len({row["signer_group_id"] for row in selected_rows}),
        "selection": "detector-independent, signer-diverse train/val; balanced sign-span positions",
        "canonical_manifest": str(args.canonical_manifest.resolve()),
        "canonical_manifest_sha256": _sha256(args.canonical_manifest),
        "models_trained": False,
        "android_modified": False,
        "next": "review-gold",
        "passed": True,
    }
    _write_json(args.run_dir / "prepare_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return summary


def review_gold(args: argparse.Namespace) -> dict[str, Any]:
    rows, index = load_gold_run(args.run_dir / "gold")
    errors = validate_gold_run(rows, index)
    if errors:
        raise ValueError("; ".join(errors[:10]))
    GoldReviewApp(args.run_dir / "gold" / "gold_review.csv", rows, index).run()
    return {"passed": True, "review_window_closed": True}


def _roi_config() -> RoiConfig:
    return RoiConfig(
        crop_sizes=(160,),
        expansion_factors=(1.75,),
        min_valid_landmarks=15,
        min_side_fraction=0.12,
        max_side_fraction=0.75,
        max_hold_ms=100,
        pad_value_rgb=(0, 0, 0),
    )


def _expand_square(
    box: tuple[float, float, float, float], factor: float, width: int, height: int
) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    side = max(x2 - x1, y2 - y1) * factor
    floor = 0.12 * min(width, height)
    ceiling = 0.75 * max(width, height)
    side = min(max(side, floor), ceiling)
    return cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2


def _anchor(
    arrays: dict[str, np.ndarray], frame: int, side: int, width: int, height: int
) -> tuple[float, float] | None:
    if arrays["hand_score"][frame, side] > 0:
        points = arrays["hands_image"][frame, side, :, :2]
        valid = np.all(np.isfinite(points), axis=1)
        if int(np.sum(valid)) >= 5:
            return float(np.mean(points[valid, 0]) * width), float(
                np.mean(points[valid, 1]) * height
            )
    indices = (15, 17, 19, 21) if side == 0 else (16, 18, 20, 22)
    pose = arrays["pose_image"][frame, list(indices)]
    valid = np.all(np.isfinite(pose[:, [0, 1, 3]]), axis=1) & (pose[:, 3] >= 0.5)
    if np.any(valid):
        return float(np.mean(pose[valid, 0]) * width), float(np.mean(pose[valid, 1]) * height)
    return None


def assign_detector_boxes(
    detections: list[tuple[float, float, float, float]],
    anchors: list[tuple[float, float] | None],
) -> list[tuple[float, float, float, float] | None]:
    """Assign generic detector boxes to anatomical slots by exact minimum anchor distance."""
    output: list[tuple[float, float, float, float] | None] = [None, None]
    valid_sides = [index for index, anchor in enumerate(anchors) if anchor is not None]
    if not detections or not valid_sides:
        return output
    best: tuple[float, tuple[int, ...], tuple[int, ...]] | None = None
    count = min(len(valid_sides), len(detections))
    for sides in permutations(valid_sides, count):
        for boxes in permutations(range(len(detections)), count):
            distance = 0.0
            for side, box_index in zip(sides, boxes, strict=True):
                x1, y1, x2, y2 = detections[box_index]
                anchor = anchors[side]
                assert anchor is not None
                distance += math.hypot((x1 + x2) / 2 - anchor[0], (y1 + y2) / 2 - anchor[1])
            candidate = (distance, sides, boxes)
            if best is None or candidate[0] < best[0]:
                best = candidate
    assert best is not None
    for side, box_index in zip(best[1], best[2], strict=True):
        output[side] = detections[box_index]
    return output


class I320Detector:
    def __init__(self, model: Path, threshold: float) -> None:
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        self._mp = mp
        options = vision.ObjectDetectorOptions(
            base_options=python.BaseOptions(model_asset_path=str(model.resolve())),
            running_mode=vision.RunningMode.IMAGE,
            max_results=4,
            score_threshold=threshold,
        )
        self._detector = vision.ObjectDetector.create_from_options(options)

    def close(self) -> None:
        self._detector.close()

    def detect(self, frame: np.ndarray) -> list[tuple[float, float, float, float]]:
        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        result = self._detector.detect(image)
        boxes = []
        for detection in result.detections:
            box = detection.bounding_box
            boxes.append(
                (
                    float(box.origin_x),
                    float(box.origin_y),
                    float(box.origin_x + box.width),
                    float(box.origin_y + box.height),
                )
            )
        return boxes[:4]


def _upper_body_box(
    pose: np.ndarray, width: int, height: int
) -> tuple[float, float, float, float] | None:
    selected = pose[[0, 11, 12, 23, 24, 15, 16], :]
    valid = np.all(np.isfinite(selected[:, [0, 1, 3]]), axis=1) & (selected[:, 3] >= 0.35)
    if int(np.sum(valid)) < 3:
        return None
    x = selected[valid, 0] * width
    y = selected[valid, 1] * height
    cx, cy = float((np.min(x) + np.max(x)) / 2), float((np.min(y) + np.max(y)) / 2)
    side = max(float(np.ptp(x)), float(np.ptp(y))) * 1.6
    side = min(max(side, 0.35 * min(width, height)), 1.15 * max(width, height))
    return cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2


def _route_panel(
    frames: list[np.ndarray],
    boxes: list[list[tuple[float, float, float, float] | None]],
    crops: list[list[np.ndarray | None]],
    blind: str,
) -> np.ndarray:
    full = []
    colors = ((50, 220, 50), (50, 180, 255))
    for frame, frame_boxes in zip(frames, boxes, strict=True):
        annotated = frame.copy()
        for side, box in enumerate(frame_boxes):
            if box is None:
                continue
            x1, y1, x2, y2 = (round(value) for value in box)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), colors[side], 3)
            cv2.putText(
                annotated,
                "L" if side == 0 else "R",
                (x1, max(20, y1)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                colors[side],
                2,
            )
        full.append(annotated)
    top = _fit_panel(full, 300)
    crop_rows = []
    for side in range(2):
        side_crops = []
        for frame_crops in crops:
            crop = frame_crops[side]
            if crop is None:
                crop = np.zeros((160, 160, 3), dtype=np.uint8)
                cv2.putText(
                    crop, "MISSING", (20, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
                )
            side_crops.append(crop)
        crop_rows.append(_fit_panel(side_crops, 160))
    crop_width = top.shape[1]
    bottom = np.concatenate(crop_rows, axis=0)
    bottom = cv2.copyMakeBorder(
        bottom,
        0,
        0,
        0,
        max(0, crop_width - bottom.shape[1]),
        cv2.BORDER_CONSTANT,
        value=(25, 25, 25),
    )
    panel = np.concatenate([top, bottom[:, :crop_width]], axis=0)
    cv2.putText(
        panel,
        f"BLINDED ROI CANDIDATE {blind} - LEFT/RIGHT crop triplets",
        (12, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 255, 255),
        2,
    )
    return panel


def _gold_complete(run_dir: Path) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    rows, index = load_gold_run(run_dir / "gold")
    errors = validate_gold_run(rows, index)
    incomplete = [row["sample_id"] for row in rows if gold_completion_error(row) is not None]
    if errors or incomplete:
        raise ValueError(
            f"gold review incomplete/errors: {len(incomplete)} incomplete, {errors[:3]}"
        )
    return rows, index


def build_routes(args: argparse.Namespace) -> dict[str, Any]:
    gold_rows, gold_index = _gold_complete(args.run_dir)
    selected = {
        row["audit_sample_id"]: row for row in _read_csv(args.run_dir / "selected_samples.csv")
    }
    route_root = args.run_dir / "routes"
    if route_root.exists():
        raise FileExistsError(f"routes already exist: {route_root}")
    panels_dir = route_root / "review_panels"
    crops_dir = route_root / "crops"
    panels_dir.mkdir(parents=True)
    crops_dir.mkdir(parents=True)
    metrics = json.loads(args.i320_metrics.read_text(encoding="utf-8"))
    threshold = float(metrics["selected_threshold"]["threshold"])
    detector = I320Detector(args.i320_model, threshold)
    roi = _roi_config()
    route_rows: list[dict[str, Any]] = []
    try:
        for number, gold in enumerate(gold_rows, start=1):
            if gold["review_status"] == "quarantine":
                continue
            source = selected[gold["sample_id"]]
            arrays = _stage_arrays(Path(source["stage_e_path"]))
            indices = json.loads(source["context_frame_indices"])
            frames_by_index, fps, _ = _video_frames(Path(source["raw_video_path"]), set(indices))
            frames = [frames_by_index[index] for index in indices]
            width, height = frames[0].shape[1], frames[0].shape[0]
            direct = causal_roi_sequence(
                arrays["hands_image"],
                arrays["hand_score"],
                arrays["timestamps_ms"],
                width,
                height,
                1.75,
                roi,
            )
            pose = causal_pose_recovery_sequence(
                arrays["hands_image"],
                arrays["hand_score"],
                arrays["pose_image"],
                arrays["timestamps_ms"],
                width,
                height,
                1.75,
                roi,
                PoseRecoveryConfig(
                    min_pose_visibility=0.5,
                    fallback_side_ratio=0.7222874914635724,
                    max_track_age_ms=250,
                ),
            )
            route_sequences: dict[str, list[list[RoiObservation]]] = {
                "R0": [],
                "R1": [],
                "R2": [],
                "R3": [],
            }
            for frame_index, frame in zip(indices, frames, strict=True):
                route_sequences["R0"].append(direct[frame_index])
                route_sequences["R1"].append(pose[frame_index])
                raw_boxes = detector.detect(frame)
                anchors = [_anchor(arrays, frame_index, side, width, height) for side in range(2)]
                assigned = assign_detector_boxes(raw_boxes, anchors)
                route_sequences["R2"].append(
                    [
                        RoiObservation(_expand_square(box, 1.75, width, height), "i320_assigned", 0)
                        if box is not None
                        else RoiObservation(None, "missing", 0)
                        for box in assigned
                    ]
                )
                upper = _upper_body_box(arrays["pose_image"][frame_index], width, height)
                route_sequences["R3"].append(
                    [
                        RoiObservation(upper, "upper_body_shared", 0),
                        RoiObservation(upper, "upper_body_shared", 0),
                    ]
                )
            route_order = list(ROUTES)
            random.Random(int(gold["sample_id"], 16)).shuffle(route_order)
            blind_codes = {route: chr(65 + index) for index, route in enumerate(route_order)}
            for route in ROUTES:
                observations = route_sequences[route]
                route_boxes = [
                    [item.box_xyxy for item in frame_items] for frame_items in observations
                ]
                route_crops: list[list[np.ndarray | None]] = []
                paddings: list[float] = []
                sharpness: list[float] = []
                for context_number, (frame, frame_items) in enumerate(
                    zip(frames, observations, strict=True)
                ):
                    frame_crops: list[np.ndarray | None] = []
                    for side, observation in enumerate(frame_items):
                        crop = None
                        if observation.box_xyxy is not None:
                            crop, padding = extract_square_crop(
                                frame, observation.box_xyxy, 160, (0, 0, 0)
                            )
                            paddings.append(padding)
                            sharpness.append(sharpness_variance(crop))
                            crop_path = (
                                crops_dir
                                / f"{gold['sample_id']}_{route}_{context_number}_{side}.jpg"
                            )
                            cv2.imwrite(str(crop_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 94])
                        frame_crops.append(crop)
                    route_crops.append(frame_crops)
                audit_id = _blind_id(args.seed, gold["sample_id"], route)
                panel_path = panels_dir / f"{audit_id}.jpg"
                cv2.imwrite(
                    str(panel_path),
                    _route_panel(frames, route_boxes, route_crops, blind_codes[route]),
                    [cv2.IMWRITE_JPEG_QUALITY, 94],
                )
                center_offset = len(indices) // 2
                video_elapsed = int(round(indices[center_offset] * 1000.0 / fps)) if fps > 0 else 0
                stage_elapsed = int(
                    arrays["timestamps_ms"][indices[center_offset]] - arrays["timestamps_ms"][0]
                )
                center_boxes_normalized = [
                    (
                        [
                            box[0] / width,
                            box[1] / height,
                            box[2] / width,
                            box[3] / height,
                        ]
                        if box is not None
                        else None
                    )
                    for box in route_boxes[center_offset]
                ]
                route_rows.append(
                    {
                        "audit_id": audit_id,
                        "sample_id": gold["sample_id"],
                        "route": route,
                        "blind_candidate": blind_codes[route],
                        "gloss": gold_index[gold["sample_id"]]["gloss"],
                        "signer_group_id": source["signer_group_id"],
                        "split": source["split"],
                        "role": source["role"],
                        "frame_index": indices[center_offset],
                        "timestamp_ms": arrays["timestamps_ms"][indices[center_offset]],
                        "visible_hand_count": gold["visible_hand_count"],
                        "gold_hands_json": gold["gold_hands_json"],
                        "route_boxes_json": json.dumps(
                            center_boxes_normalized, separators=(",", ":")
                        ),
                        "roi_sources_json": json.dumps(
                            [item.source for item in observations[center_offset]],
                            separators=(",", ":"),
                        ),
                        "triplet_available_rate": sum(
                            item.box_xyxy is not None for items in observations for item in items
                        )
                        / 6.0,
                        "padding_fraction_max": max(paddings, default=1.0),
                        "sharpness_min": min(sharpness, default=0.0),
                        "synchronization_error_ms": abs(video_elapsed - stage_elapsed),
                        "panel_path": str(panel_path.resolve()),
                    }
                )
            gloss = gold_index[gold["sample_id"]]["gloss"]
            print(f"[phase2/p2-p2] routes {number}/{len(gold_rows)} {gloss}")
    finally:
        detector.close()
    random.Random(args.seed).shuffle(route_rows)
    _write_csv(route_root / "internal_index.csv", ROUTE_INDEX_FIELDS, route_rows)
    _write_csv(
        route_root / "route_review.csv",
        ROUTE_REVIEW_FIELDS,
        [{"audit_id": row["audit_id"]} for row in route_rows],
    )
    summary = {
        "experiment": EXPERIMENT,
        "stage": "routes_built",
        "gold_frames": len({row["sample_id"] for row in route_rows}),
        "route_panels": len(route_rows),
        "routes": list(ROUTES),
        "i320_model_sha256": _sha256(args.i320_model),
        "i320_threshold": threshold,
        "models_trained": False,
        "next": "review-routes",
        "passed": True,
    }
    _write_json(route_root / "build_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return summary


def _save_review(path: Path, rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(".csv.tmp")
    _write_csv(temporary, ROUTE_REVIEW_FIELDS, rows)
    os.replace(temporary, path)


class RouteReviewApp:
    def __init__(
        self, path: Path, rows: list[dict[str, str]], index: dict[str, dict[str, str]]
    ) -> None:
        import tkinter as tk

        self.tk = tk
        self.path = path
        self.rows = rows
        self.index_rows = index
        self.position = next(
            (i for i, row in enumerate(rows) if not row["verdict"]), max(len(rows) - 1, 0)
        )
        self.photo: Any = None
        self.root = tk.Tk()
        self.root.title("AppHear P2-P2 Blinded ROI Crop Review")
        self.root.configure(bg="#171717")
        self.root.geometry("1280x900")
        self.progress = tk.Label(self.root, fg="white", bg="#171717", font=("Segoe UI", 13, "bold"))
        self.progress.pack(pady=7)
        tk.Label(
            self.root,
            text=(
                "Judge the center crop and its before/after consistency. "
                "Candidate identity is blinded."
            ),
            fg="#d8d8d8",
            bg="#171717",
        ).pack()
        self.image = tk.Label(self.root, bg="#111111")
        self.image.pack(fill="both", expand=True, padx=12, pady=6)
        self.notes = tk.Entry(self.root, font=("Segoe UI", 10))
        self.notes.pack(fill="x", padx=12, pady=4)
        controls = tk.Frame(self.root, bg="#171717")
        controls.pack(fill="x", padx=12, pady=4)
        for column, (key, (_, label, color)) in enumerate(VERDICTS.items()):
            tk.Button(
                controls,
                text=f"{key}: {label}",
                bg=color,
                fg="white",
                command=partial(self.mark, key),
            ).grid(row=column // 5, column=column % 5, sticky="ew", padx=2, pady=2)
        for column in range(5):
            controls.grid_columnconfigure(column, weight=1)
        nav = tk.Frame(self.root, bg="#171717")
        nav.pack(fill="x", padx=12, pady=6)
        tk.Button(nav, text="Previous (P)", command=self.previous).pack(side="left")
        tk.Button(nav, text="Exit and save (Esc)", command=self.close).pack(side="right")
        for key in VERDICTS:
            self.root.bind(key, partial(self._mark_event, key))
        self.root.bind("p", self._previous_event)
        self.root.bind("<Escape>", self._close_event)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.show()

    def show(self) -> None:
        row = self.rows[self.position]
        completed = sum(bool(item["verdict"]) for item in self.rows)
        meta = self.index_rows[row["audit_id"]]
        self.progress.configure(
            text=(
                f"Panel {self.position + 1}/{len(self.rows)} | completed {completed} | "
                f"visible hands {meta['visible_hand_count']}"
            )
        )
        self.notes.delete(0, self.tk.END)
        self.notes.insert(0, row.get("notes", ""))
        image = cv2.imread(meta["panel_path"])
        if image is None:
            raise OSError(meta["panel_path"])
        max_width = max(self.root.winfo_width() - 40, 900)
        max_height = max(self.root.winfo_height() - 230, 500)
        scale = min(max_width / image.shape[1], max_height / image.shape[0], 1.5)
        image = cv2.resize(
            image,
            (round(image.shape[1] * scale), round(image.shape[0] * scale)),
            interpolation=cv2.INTER_AREA,
        )
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise OSError("panel encoding failed")
        self.photo = self.tk.PhotoImage(data=base64.b64encode(encoded.tobytes()).decode("ascii"))
        self.image.configure(image=self.photo)

    def mark(self, key: str) -> None:
        self.rows[self.position]["verdict"] = VERDICTS[key][0]
        self.rows[self.position]["notes"] = self.notes.get().strip()
        _save_review(self.path, self.rows)
        next_row = next(
            (i for i in range(self.position + 1, len(self.rows)) if not self.rows[i]["verdict"]),
            None,
        )
        if next_row is None:
            next_row = next((i for i, row in enumerate(self.rows) if not row["verdict"]), None)
        if next_row is None:
            self.progress.configure(text=f"Complete: {len(self.rows)}/{len(self.rows)} saved")
            self.image.configure(image="")
            return
        self.position = next_row
        self.show()

    def _mark_event(self, key: str, _event: object) -> None:
        self.mark(key)

    def previous(self) -> None:
        if self.position > 0:
            self.position -= 1
            self.show()

    def _previous_event(self, _event: object) -> None:
        self.previous()

    def close(self) -> None:
        _save_review(self.path, self.rows)
        self.root.destroy()

    def _close_event(self, _event: object) -> None:
        self.close()

    def run(self) -> None:
        self.root.mainloop()


def review_routes(args: argparse.Namespace) -> dict[str, Any]:
    path = args.run_dir / "routes" / "route_review.csv"
    rows = _read_csv(path)
    index = {
        row["audit_id"]: row for row in _read_csv(args.run_dir / "routes" / "internal_index.csv")
    }
    if set(index) != {row["audit_id"] for row in rows}:
        raise ValueError("route review/index IDs do not align")
    backup = path.with_name("route_review.pre_review_backup.csv")
    if not backup.exists():
        shutil.copy2(path, backup)
    RouteReviewApp(path, rows, index).run()
    return {"passed": True, "review_window_closed": True}


def _area(box: dict[str, Any] | Box4) -> float:
    if isinstance(box, dict):
        x1, y1, x2, y2 = (float(box[key]) for key in ("x_min", "y_min", "x_max", "y_max"))
    else:
        x1, y1, x2, y2 = box
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _coverage(gold: dict[str, Any], route: tuple[float, float, float, float]) -> float:
    gx1, gy1, gx2, gy2 = (float(gold[key]) for key in ("x_min", "y_min", "x_max", "y_max"))
    rx1, ry1, rx2, ry2 = route
    intersection = max(0.0, min(gx2, rx2) - max(gx1, rx1)) * max(0.0, min(gy2, ry2) - max(gy1, ry1))
    return intersection / _area(gold) if _area(gold) else 0.0


def score_route_boxes(
    gold: list[dict[str, Any]], route_boxes: list[Any], shared: bool = False
) -> tuple[int, bool, int]:
    """Score boxes with exact one-to-one matching.

    Known anatomical sides may only match their corresponding route slot. Unknown
    sides remain flexible, but one predicted slot can cover at most one gold hand.
    """
    boxes: list[Box4 | None] = [
        cast(Box4, tuple(float(value) for value in box)) if box is not None else None
        for box in route_boxes
    ]
    eligible: dict[tuple[int, int], float] = {}
    side_errors = 0
    for gold_index, hand in enumerate(gold):
        side = hand.get("anatomical_side", "unknown")
        expected = None if shared or side not in {"left", "right"} else (0 if side == "left" else 1)
        for box_index, box in enumerate(boxes):
            if box is None or (expected is not None and box_index != expected):
                continue
            coverage = _coverage(hand, box)
            if coverage >= 0.90:
                eligible[(gold_index, box_index)] = coverage
        if expected is not None:
            target = boxes[expected]
            opposite = boxes[1 - expected]
            target_coverage = _coverage(hand, target) if target is not None else 0.0
            opposite_coverage = _coverage(hand, opposite) if opposite is not None else 0.0
            side_errors += int(opposite_coverage >= 0.90 and target_coverage < 0.90)

    best_count = 0
    best_coverage = -1.0
    for count in range(1, min(len(gold), len(boxes)) + 1):
        for gold_order in permutations(range(len(gold)), count):
            for box_order in permutations(range(len(boxes)), count):
                pairs = list(zip(gold_order, box_order, strict=True))
                if not all(pair in eligible for pair in pairs):
                    continue
                coverage = sum(eligible[pair] for pair in pairs)
                if count > best_count or (count == best_count and coverage > best_coverage):
                    best_count = count
                    best_coverage = coverage
    covered = best_count
    return covered, len(gold) == 2 and covered == 2, side_errors


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _side_assignments(run_dir: Path) -> dict[str, str]:
    path = run_dir / "side_review" / "side_review.csv"
    if not path.is_file():
        return {}
    return {row["sample_id"]: row["assignment"] for row in _read_csv(path)}


def _resolve_gold_sides(
    sample_id: str, gold: list[dict[str, Any]], assignments: dict[str, str]
) -> list[dict[str, Any]]:
    assignment = assignments.get(sample_id, "")
    resolved = [dict(hand) for hand in gold]
    if len(resolved) != 2:
        return resolved
    if assignment == "box1_left_box2_right":
        resolved[0]["anatomical_side"] = "left"
        resolved[1]["anatomical_side"] = "right"
    elif assignment == "box1_right_box2_left":
        resolved[0]["anatomical_side"] = "right"
        resolved[1]["anatomical_side"] = "left"
    return resolved


def _strict_route_selector_oracle(
    index_rows: list[dict[str, str]],
    reviews: dict[str, dict[str, str]],
    side_assignments: dict[str, str],
) -> dict[str, Any]:
    """Measure the best whole-route R1/R2 choice available per frame.

    This is a non-deployable upper bound. It may choose a route using gold boxes,
    but it may not combine boxes from different routes or reuse a box.
    """
    by_sample: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in index_rows:
        if row["route"] in {"R1", "R2"}:
            by_sample[row["sample_id"]][row["route"]] = row

    gold_total = coverage_total = two_total = two_complete = 0
    known_side_hands = side_correct = visible_frames = 0
    geometry_selected_usable = union_usable = consistency_ok = sync_ok = 0
    selected_routes: Counter[str] = Counter()
    for sample_id, routes in by_sample.items():
        if set(routes) != {"R1", "R2"}:
            continue
        gold = _resolve_gold_sides(
            sample_id, json.loads(routes["R1"]["gold_hands_json"]), side_assignments
        )
        candidates: list[tuple[tuple[int, int, int, int], str, dict[str, Any]]] = []
        for route in ("R1", "R2"):
            row = routes[route]
            boxes = json.loads(row["route_boxes_json"])
            covered, complete, _ = score_route_boxes(gold, boxes)
            correct_sides = 0
            for hand in gold:
                side = hand.get("anatomical_side", "unknown")
                if side not in {"left", "right"}:
                    continue
                box = boxes[0 if side == "left" else 1]
                correct_sides += int(
                    box is not None
                    and _coverage(hand, cast(Box4, tuple(float(value) for value in box))) >= 0.90
                )
            rank = (covered, int(complete), correct_sides, int(route == "R1"))
            candidates.append(
                (
                    rank,
                    route,
                    {
                        "row": row,
                        "covered": covered,
                        "complete": complete,
                        "correct_sides": correct_sides,
                    },
                )
            )
        _, selected_route, selected = max(candidates, key=lambda candidate: candidate[0])
        selected_routes[selected_route] += 1
        gold_total += len(gold)
        coverage_total += selected["covered"]
        two_total += int(len(gold) == 2)
        two_complete += int(selected["complete"])
        visible_frames += int(bool(gold))
        known_side_hands += sum(
            hand.get("anatomical_side") in {"left", "right"} for hand in gold
        )
        side_correct += selected["correct_sides"]
        selected_verdict = reviews[selected["row"]["audit_id"]]["verdict"]
        geometry_selected_usable += int(bool(gold) and selected_verdict == "usable_complete")
        union_usable += int(
            bool(gold)
            and any(
                reviews[routes[route]["audit_id"]]["verdict"] == "usable_complete"
                for route in ("R1", "R2")
            )
        )
        consistency_ok += int(
            max(float(routes[route]["triplet_available_rate"]) for route in ("R1", "R2"))
            >= 5 / 6
        )
        sync_ok += int(
            min(float(routes[route]["synchronization_error_ms"]) for route in ("R1", "R2"))
            <= 50.0
        )

    coverage = _rate(coverage_total, gold_total)
    two_hand = _rate(two_complete, two_total)
    side_accuracy = _rate(side_correct, known_side_hands)
    return {
        "kind": "non_deployable_gold_oracle_whole_route_selection",
        "routes": ["R1", "R2"],
        "frames": len(by_sample),
        "selected_route_counts": dict(selected_routes),
        "known_visible_roi_coverage": coverage,
        "complete_two_hand_coverage": two_hand,
        "anatomical_side_gold_hands": known_side_hands,
        "anatomical_side_accuracy": side_accuracy,
        "geometry_selected_reviewed_usable_rate": _rate(
            geometry_selected_usable, visible_frames
        ),
        "union_reviewed_usable_upper_bound": _rate(union_usable, visible_frames),
        "triplet_consistency_upper_bound": _rate(consistency_ok, len(by_sample)),
        "synchronization_upper_bound": _rate(sync_ok, len(by_sample)),
        "geometry_gates_crossed": bool(
            (coverage or 0.0) >= 0.90
            and (two_hand or 0.0) >= 0.80
            and (side_accuracy or 0.0) >= 0.98
        ),
        "training_authorized": False,
    }


def _side_convention_counterfactuals(
    index_rows: list[dict[str, str]], side_assignments: dict[str, str]
) -> dict[str, Any]:
    """Compare existing route slots with a global left/right slot swap."""
    output: dict[str, Any] = {}
    for route in ("R0", "R1", "R2"):
        rows = [row for row in index_rows if row["route"] == route]
        variants: dict[str, Any] = {}
        for variant, swap in (("as_recorded", False), ("globally_swapped", True)):
            gold_total = covered_total = two_total = two_complete = 0
            known_side_hands = side_correct = 0
            for row in rows:
                gold = _resolve_gold_sides(
                    row["sample_id"], json.loads(row["gold_hands_json"]), side_assignments
                )
                boxes = json.loads(row["route_boxes_json"])
                if swap:
                    boxes = list(reversed(boxes))
                covered, complete, _ = score_route_boxes(gold, boxes)
                gold_total += len(gold)
                covered_total += covered
                two_total += int(len(gold) == 2)
                two_complete += int(complete)
                for hand in gold:
                    side = hand.get("anatomical_side", "unknown")
                    if side not in {"left", "right"}:
                        continue
                    known_side_hands += 1
                    box = boxes[0 if side == "left" else 1]
                    side_correct += int(
                        box is not None
                        and _coverage(hand, cast(Box4, tuple(float(value) for value in box)))
                        >= 0.90
                    )
            variants[variant] = {
                "known_visible_roi_coverage": _rate(covered_total, gold_total),
                "complete_two_hand_coverage": _rate(two_complete, two_total),
                "anatomical_side_gold_hands": known_side_hands,
                "anatomical_side_accuracy": _rate(side_correct, known_side_hands),
            }
        original = variants["as_recorded"]["anatomical_side_accuracy"] or 0.0
        swapped = variants["globally_swapped"]["anatomical_side_accuracy"] or 0.0
        variants["preferred_convention"] = (
            "globally_swapped" if swapped > original else "as_recorded"
        )
        output[route] = variants
    return output


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    index_rows = _read_csv(args.run_dir / "routes" / "internal_index.csv")
    reviews = {
        row["audit_id"]: row for row in _read_csv(args.run_dir / "routes" / "route_review.csv")
    }
    incomplete = [row["audit_id"] for row in index_rows if not reviews[row["audit_id"]]["verdict"]]
    if incomplete:
        raise ValueError(f"route review incomplete: {len(incomplete)} rows")
    by_route: dict[str, list[dict[str, str]]] = defaultdict(list)
    gold_reviews = {
        row["sample_id"]: row for row in _read_csv(args.run_dir / "gold" / "gold_review.csv")
    }
    side_assignments = _side_assignments(args.run_dir)
    for row in index_rows:
        by_route[row["route"]].append(row)
    results: dict[str, Any] = {}
    for route, rows in by_route.items():
        gold_total = coverage_total = two_total = two_complete = 0
        known_side_hands = side_correct = side_errors_total = 0
        sync_ok = consistency_ok = 0
        visible_frames = wrong_frames = negative_false_roi_frames = 0
        verdicts: Counter[str] = Counter()
        subgroup: dict[str, Counter[str]] = defaultdict(Counter)
        for row in rows:
            gold = _resolve_gold_sides(
                row["sample_id"], json.loads(row["gold_hands_json"]), side_assignments
            )
            boxes = json.loads(row["route_boxes_json"])
            covered, complete, side_error = score_route_boxes(gold, boxes, shared=route == "R3")
            gold_total += len(gold)
            coverage_total += covered
            two_total += int(len(gold) == 2)
            two_complete += int(complete)
            if route != "R3":
                for hand in gold:
                    side = hand.get("anatomical_side", "unknown")
                    if side not in {"left", "right"}:
                        continue
                    known_side_hands += 1
                    index = 0 if side == "left" else 1
                    box = boxes[index]
                    correct = (
                        box is not None
                        and _coverage(hand, cast(Box4, tuple(float(value) for value in box)))
                        >= 0.90
                    )
                    side_correct += int(correct)
                side_errors_total += side_error
            sync_ok += int(float(row["synchronization_error_ms"]) <= 50.0)
            consistency_ok += int(float(row["triplet_available_rate"]) >= 5 / 6)
            verdict = reviews[row["audit_id"]]["verdict"]
            verdicts[verdict] += 1
            visible_frames += int(bool(gold))
            wrong_frames += int(
                bool(gold) and (side_error > 0 or verdict in {"wrong_side", "stale_desynced"})
            )
            negative_false_roi_frames += int(not gold and any(box is not None for box in boxes))
            conditions = [f"hands={len(gold)}"]
            gold_source = gold_reviews[row["sample_id"]]
            conditions.extend(
                field
                for field in (
                    "motion_blur",
                    "occlusion",
                    "near_face",
                    "edge_clipped",
                    "partial_visibility",
                )
                if gold_source[field] == "yes"
            )
            for condition in conditions:
                subgroup[condition]["frames"] += 1
                subgroup[condition]["usable"] += int(verdict == "usable_complete")
        known_visible = _rate(coverage_total, gold_total)
        complete_two = _rate(two_complete, two_total)
        usable = _rate(verdicts["usable_complete"], visible_frames)
        wrong = _rate(wrong_frames, visible_frames)
        synchronized = _rate(sync_ok, len(rows))
        consistent = _rate(consistency_ok, len(rows))
        promotable = route in PROMOTABLE_ROUTES
        side_accuracy = _rate(side_correct, known_side_hands)
        side_evidence_sufficient = known_side_hands >= 60
        gate_passed = bool(
            promotable
            and (known_visible or 0.0) >= 0.90
            and (complete_two or 0.0) >= 0.80
            and (usable or 0.0) >= 0.85
            and (wrong if wrong is not None else 1.0) <= 0.02
            and (synchronized or 0.0) >= 0.98
            and (consistent or 0.0) >= 0.90
            and side_evidence_sufficient
            and (side_accuracy or 0.0) >= 0.98
        )
        metrics: dict[str, Any] = {
            "name": ROUTE_NAMES[route],
            "promotable": promotable,
            "frames": len(rows),
            "visible_reference_frames": visible_frames,
            "known_visible_roi_coverage": known_visible,
            "complete_two_hand_coverage": complete_two,
            "reviewed_crop_usable_rate": usable,
            "wrong_stale_or_side_swap_rate": wrong,
            "synchronization_pass_rate": synchronized,
            "triplet_availability_consistency_rate": consistent,
            "anatomical_side_gold_hands": known_side_hands,
            "anatomical_side_accuracy": side_accuracy,
            "anatomical_side_errors": side_errors_total,
            "anatomical_side_evidence_sufficient": side_evidence_sufficient,
            "no_visible_hand_false_roi_rate": _rate(
                negative_false_roi_frames, len(rows) - visible_frames
            ),
            "verdict_counts": dict(verdicts),
            "subgroups": {
                name: {
                    "frames": counts["frames"],
                    "usable_rate": _rate(counts["usable"], counts["frames"]),
                }
                for name, counts in sorted(subgroup.items())
            },
        }
        metrics["gate_passed"] = gate_passed
        results[route] = metrics
    passing = [route for route in PROMOTABLE_ROUTES if results.get(route, {}).get("gate_passed")]
    winner = max(
        passing,
        key=lambda route: (
            results[route]["reviewed_crop_usable_rate"],
            results[route]["complete_two_hand_coverage"],
            results[route]["known_visible_roi_coverage"],
        ),
        default=None,
    )
    decision = "GO_CREATE_40_SIGN_RGB_DATASET" if winner else "NO_GO_RGB_DATASET"
    summary = {
        "experiment": EXPERIMENT,
        "stage": "final_roi_crop_gate",
        "scoring_version": "p2p2.strict_one_to_one.v2",
        "manual_review_status": "single_reviewer_provisional",
        "side_adjudication": {
            "rows": len(side_assignments),
            "resolved": sum(
                value in {"box1_left_box2_right", "box1_right_box2_left"}
                for value in side_assignments.values()
            ),
            "cannot_determine": sum(
                value == "cannot_determine" for value in side_assignments.values()
            ),
        },
        "routes": results,
        "strict_r1_r2_selector_oracle": _strict_route_selector_oracle(
            index_rows, reviews, side_assignments
        ),
        "side_convention_counterfactuals": _side_convention_counterfactuals(
            index_rows, side_assignments
        ),
        "decision": decision,
        "selected_roi_strategy": winner,
        "reason": "at least one promotable route passed every preregistered gate"
        if winner
        else "no promotable route passed every preregistered gate",
        "models_trained": False,
        "android_modified": False,
        "passed": True,
    }
    result_path = args.run_dir / "p2_p2_final_result.json"
    superseded = args.run_dir / "p2_p2_final_result.superseded_nonunique_matching.json"
    if result_path.is_file() and not superseded.exists():
        shutil.copy2(result_path, superseded)
    _write_json(result_path, summary)
    print(json.dumps(summary, indent=2))
    return summary


def _side_panel(image: np.ndarray, boxes: list[dict[str, Any]]) -> np.ndarray:
    panel = image.copy()
    height, width = panel.shape[:2]
    colors = ((40, 80, 255), (255, 220, 40))
    for index, (box, color) in enumerate(zip(boxes, colors, strict=True), start=1):
        x1 = round(float(box["x_min"]) * width)
        y1 = round(float(box["y_min"]) * height)
        x2 = round(float(box["x_max"]) * width)
        y2 = round(float(box["y_max"]) * height)
        cv2.rectangle(panel, (x1, y1), (x2, y2), color, 4)
        cv2.putText(
            panel,
            f"BOX {index}",
            (x1, max(28, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.85,
            color,
            3,
            cv2.LINE_AA,
        )
    cv2.putText(
        panel,
        "Identify the SIGNER'S anatomical left/right hand",
        (12, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return panel


def prepare_side_review(args: argparse.Namespace) -> dict[str, Any]:
    output = args.run_dir / "side_review"
    if output.exists():
        raise FileExistsError(f"side review already exists: {output}")
    gold_rows, gold_index = _gold_complete(args.run_dir)
    route_rows = _read_csv(args.run_dir / "routes" / "internal_index.csv")
    by_sample: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in route_rows:
        by_sample[row["sample_id"]][row["route"]] = row
    candidates: list[tuple[int, str, dict[str, str]]] = []
    for row in gold_rows:
        gold = json.loads(row["gold_hands_json"] or "[]")
        if row["review_status"] != "accepted" or len(gold) != 2:
            continue
        routes = by_sample[row["sample_id"]]
        r1 = json.loads(routes["R1"]["route_boxes_json"])
        r2 = json.loads(routes["R2"]["route_boxes_json"])
        r1_count, _, _ = score_route_boxes(gold, r1)
        r2_count, _, _ = score_route_boxes(gold, r2)
        union_boxes = [box for box in r1 + r2 if box is not None]
        union_count, _, _ = score_route_boxes(gold, union_boxes)
        complement_gain = union_count - max(r1_count, r2_count)
        candidates.append((complement_gain, row["sample_id"], row))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    chosen: list[dict[str, str]] = []
    used_signers: set[str] = set()
    for distinct_only in (True, False):
        for _, sample_id, row in candidates:
            signer = gold_index[sample_id]["participant_id"]
            if row in chosen or (distinct_only and signer in used_signers):
                continue
            chosen.append(row)
            used_signers.add(signer)
            if len(chosen) == args.count:
                break
        if len(chosen) == args.count:
            break
    if len(chosen) < args.count:
        raise ValueError(f"requested {args.count} side rows, found {len(chosen)}")
    panels = output / "panels"
    panels.mkdir(parents=True)
    index_rows: list[dict[str, Any]] = []
    for row in chosen:
        sample_id = row["sample_id"]
        meta = gold_index[sample_id]
        image = cv2.imread(meta["center_image_path"])
        if image is None:
            raise OSError(meta["center_image_path"])
        boxes = json.loads(row["gold_hands_json"])
        panel_path = panels / f"{sample_id}.jpg"
        cv2.imwrite(
            str(panel_path),
            _side_panel(image, boxes),
            [cv2.IMWRITE_JPEG_QUALITY, 95],
        )
        index_rows.append(
            {
                "sample_id": sample_id,
                "gloss": meta["gloss"],
                "signer_group_id": meta["participant_id"],
                "gold_hands_json": row["gold_hands_json"],
                "panel_path": str(panel_path.resolve()),
            }
        )
    _write_csv(output / "internal_index.csv", SIDE_INDEX_FIELDS, index_rows)
    _write_csv(
        output / "side_review.csv",
        SIDE_REVIEW_FIELDS,
        [{"sample_id": row["sample_id"]} for row in index_rows],
    )
    summary = {
        "experiment": EXPERIMENT,
        "stage": "anatomical_side_review_prepared",
        "rows": len(index_rows),
        "gold_hands": 2 * len(index_rows),
        "signers": len({row["signer_group_id"] for row in index_rows}),
        "selection": "two-hand frames; complementary R1/R2 failures first; signer diversity",
        "next": "review-sides",
        "passed": True,
    }
    _write_json(output / "prepare_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return summary


class SideReviewApp:
    def __init__(
        self,
        path: Path,
        rows: list[dict[str, str]],
        index: dict[str, dict[str, str]],
    ) -> None:
        import tkinter as tk

        self.tk = tk
        self.path = path
        self.rows = rows
        self.index_rows = index
        self.position = next(
            (i for i, row in enumerate(rows) if not row["assignment"]),
            max(len(rows) - 1, 0),
        )
        self.photo: Any = None
        self.root = tk.Tk()
        self.root.title("AppHear P2-P2 Anatomical Side Review")
        self.root.configure(bg="#171717")
        self.root.geometry("1120x820")
        self.progress = tk.Label(self.root, fg="white", bg="#171717", font=("Segoe UI", 13, "bold"))
        self.progress.pack(pady=8)
        tk.Label(
            self.root,
            text=(
                "Choose from the SIGNER'S perspective. Do not use screen-left/screen-right. "
                "If uncertain, choose Cannot determine."
            ),
            fg="#ffd166",
            bg="#171717",
            font=("Segoe UI", 10, "bold"),
        ).pack()
        self.image = tk.Label(self.root, bg="#111111")
        self.image.pack(fill="both", expand=True, padx=14, pady=8)
        self.notes = tk.Entry(self.root, font=("Segoe UI", 10))
        self.notes.pack(fill="x", padx=14, pady=4)
        controls = tk.Frame(self.root, bg="#171717")
        controls.pack(fill="x", padx=14, pady=6)
        options = (
            ("1", "box1_left_box2_right", "BOX 1 = signer's LEFT; BOX 2 = RIGHT", "#18794e"),
            ("2", "box1_right_box2_left", "BOX 1 = signer's RIGHT; BOX 2 = LEFT", "#1f6feb"),
            ("3", "cannot_determine", "Cannot determine safely", "#6b4f9b"),
        )
        for column, (key, value, label, color) in enumerate(options):
            tk.Button(
                controls,
                text=f"{key}: {label}",
                bg=color,
                fg="white",
                command=partial(self.mark, value),
                pady=10,
            ).grid(row=0, column=column, sticky="ew", padx=3)
            self.root.bind(key, partial(self._mark_event, value))
        for column in range(3):
            controls.grid_columnconfigure(column, weight=1)
        nav = tk.Frame(self.root, bg="#171717")
        nav.pack(fill="x", padx=14, pady=6)
        tk.Button(nav, text="Previous (P)", command=self.previous).pack(side="left")
        tk.Button(nav, text="Exit and save (Esc)", command=self.close).pack(side="right")
        self.root.bind("p", self._previous_event)
        self.root.bind("<Escape>", self._close_event)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.show()

    def show(self) -> None:
        row = self.rows[self.position]
        completed = sum(bool(item["assignment"]) for item in self.rows)
        meta = self.index_rows[row["sample_id"]]
        self.progress.configure(
            text=(
                f"Frame {self.position + 1}/{len(self.rows)} | completed {completed} | "
                f"sign {meta['gloss']}"
            )
        )
        self.notes.delete(0, self.tk.END)
        self.notes.insert(0, row.get("notes", ""))
        image = cv2.imread(meta["panel_path"])
        if image is None:
            raise OSError(meta["panel_path"])
        max_width = max(self.root.winfo_width() - 40, 850)
        max_height = max(self.root.winfo_height() - 210, 500)
        scale = min(max_width / image.shape[1], max_height / image.shape[0], 1.8)
        image = cv2.resize(
            image,
            (round(image.shape[1] * scale), round(image.shape[0] * scale)),
            interpolation=cv2.INTER_AREA,
        )
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise OSError("side panel encoding failed")
        self.photo = self.tk.PhotoImage(data=base64.b64encode(encoded.tobytes()).decode("ascii"))
        self.image.configure(image=self.photo)

    def mark(self, assignment: str) -> None:
        self.rows[self.position]["assignment"] = assignment
        self.rows[self.position]["notes"] = self.notes.get().strip()
        _write_csv(self.path, SIDE_REVIEW_FIELDS, self.rows)
        next_row = next(
            (i for i in range(self.position + 1, len(self.rows)) if not self.rows[i]["assignment"]),
            None,
        )
        if next_row is None:
            next_row = next((i for i, row in enumerate(self.rows) if not row["assignment"]), None)
        if next_row is None:
            self.progress.configure(text=f"Complete: {len(self.rows)}/{len(self.rows)} saved")
            self.image.configure(image="")
            return
        self.position = next_row
        self.show()

    def _mark_event(self, assignment: str, _event: object) -> None:
        self.mark(assignment)

    def previous(self) -> None:
        if self.position > 0:
            self.position -= 1
            self.show()

    def _previous_event(self, _event: object) -> None:
        self.previous()

    def close(self) -> None:
        _write_csv(self.path, SIDE_REVIEW_FIELDS, self.rows)
        self.root.destroy()

    def _close_event(self, _event: object) -> None:
        self.close()

    def run(self) -> None:
        self.root.mainloop()


def review_sides(args: argparse.Namespace) -> dict[str, Any]:
    root = args.run_dir / "side_review"
    path = root / "side_review.csv"
    rows = _read_csv(path)
    index = {row["sample_id"]: row for row in _read_csv(root / "internal_index.csv")}
    if set(index) != {row["sample_id"] for row in rows}:
        raise ValueError("side review/index IDs do not align")
    backup = root / "side_review.pre_review_backup.csv"
    if not backup.exists():
        shutil.copy2(path, backup)
    SideReviewApp(path, rows, index).run()
    return {"passed": True, "review_window_closed": True}


def check(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    required = [
        args.run_dir / "prepare_summary.json",
        args.run_dir / "selected_samples.csv",
        args.run_dir / "gold" / "internal_index.csv",
        args.run_dir / "gold" / "gold_review.csv",
    ]
    if args.require_routes or args.require_routes_reviewed:
        required.extend(
            [
                args.run_dir / "routes" / "internal_index.csv",
                args.run_dir / "routes" / "route_review.csv",
            ]
        )
    if args.require_result:
        required.append(args.run_dir / "p2_p2_final_result.json")
    if args.require_side_reviewed:
        required.extend(
            [
                args.run_dir / "side_review" / "internal_index.csv",
                args.run_dir / "side_review" / "side_review.csv",
            ]
        )
    for path in required:
        if not path.is_file():
            errors.append(f"missing: {path}")
    if not errors:
        selected = _read_csv(args.run_dir / "selected_samples.csv")
        gold_rows, gold_index = load_gold_run(args.run_dir / "gold")
        if len(selected) != 120 or len(gold_rows) != 120 or len(gold_index) != 120:
            errors.append(
                "expected 120 aligned selected/gold rows, got "
                f"{len(selected)}/{len(gold_rows)}/{len(gold_index)}"
            )
        if args.require_gold_reviewed:
            incomplete = [
                row["sample_id"] for row in gold_rows if gold_completion_error(row) is not None
            ]
            if incomplete:
                errors.append(f"gold review incomplete: {len(incomplete)} rows")
        if args.require_routes or args.require_routes_reviewed:
            route_index = _read_csv(args.run_dir / "routes" / "internal_index.csv")
            route_review = _read_csv(args.run_dir / "routes" / "route_review.csv")
            expected_routes = 4 * sum(
                gold_completion_error(row) is None and row["review_status"] != "quarantine"
                for row in gold_rows
            )
            if len(route_index) != expected_routes or len(route_review) != expected_routes:
                errors.append(
                    "route row count mismatch: expected "
                    f"{expected_routes}, got {len(route_index)}/{len(route_review)}"
                )
            if args.require_routes_reviewed:
                incomplete_routes = [row["audit_id"] for row in route_review if not row["verdict"]]
                if incomplete_routes:
                    errors.append(f"route review incomplete: {len(incomplete_routes)} rows")
        if args.require_side_reviewed:
            side_rows = _read_csv(args.run_dir / "side_review" / "side_review.csv")
            incomplete_sides = [row["sample_id"] for row in side_rows if not row["assignment"]]
            resolved_sides = sum(
                row["assignment"] in {"box1_left_box2_right", "box1_right_box2_left"}
                for row in side_rows
            )
            if incomplete_sides:
                errors.append(f"side review incomplete: {len(incomplete_sides)} rows")
            if resolved_sides < 30:
                errors.append(f"only {resolved_sides} side rows resolved; at least 30 are required")
    summary = {
        "run_dir": str(args.run_dir.resolve()),
        "errors": errors,
        "passed": not errors,
        "production_authorized": False,
    }
    print(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="P2-P2 bounded synchronized RGB ROI audit")
    commands = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser = commands.add_parser("prepare", parents=[common])
    prepare_parser.add_argument("--prep-dir", type=Path, default=DEFAULT_PREP)
    prepare_parser.add_argument(
        "--canonical-manifest", type=Path, default=DEFAULT_CANONICAL_MANIFEST
    )
    prepare_parser.add_argument("--per-sign", type=int, default=3)
    prepare_parser.add_argument("--seed", type=int, default=120826)
    prepare_parser.set_defaults(func=prepare)
    gold_parser = commands.add_parser("review-gold", parents=[common])
    gold_parser.set_defaults(func=review_gold)
    routes_parser = commands.add_parser("build-routes", parents=[common])
    routes_parser.add_argument("--i320-model", type=Path, default=DEFAULT_I320_MODEL)
    routes_parser.add_argument("--i320-metrics", type=Path, default=DEFAULT_I320_METRICS)
    routes_parser.add_argument("--seed", type=int, default=120826)
    routes_parser.set_defaults(func=build_routes)
    review_parser = commands.add_parser("review-routes", parents=[common])
    review_parser.set_defaults(func=review_routes)
    side_prepare_parser = commands.add_parser("prepare-side-review", parents=[common])
    side_prepare_parser.add_argument("--count", type=int, default=40)
    side_prepare_parser.set_defaults(func=prepare_side_review)
    side_review_parser = commands.add_parser("review-sides", parents=[common])
    side_review_parser.set_defaults(func=review_sides)
    eval_parser = commands.add_parser("evaluate", parents=[common])
    eval_parser.set_defaults(func=evaluate)
    check_parser = commands.add_parser("check", parents=[common])
    check_parser.add_argument("--require-routes", action="store_true")
    check_parser.add_argument("--require-gold-reviewed", action="store_true")
    check_parser.add_argument("--require-routes-reviewed", action="store_true")
    check_parser.add_argument("--require-side-reviewed", action="store_true")
    check_parser.add_argument("--require-result", action="store_true")
    check_parser.set_defaults(func=check)
    args = parser.parse_args()
    try:
        result = args.func(args)
        return 0 if result.get("passed", True) else 2
    except (
        FileExistsError,
        FileNotFoundError,
        json.JSONDecodeError,
        KeyError,
        OSError,
        ValueError,
    ) as error:
        print(f"[phase2/p2-p2] ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
