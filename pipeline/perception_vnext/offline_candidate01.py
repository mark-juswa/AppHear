"""Offline Candidate 01 extractor matching the Android current-frame path."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.perception_vnext.hand_refiner import MediaPipeHandRefiner
from pipeline.perception_vnext.hand_roi import HandRoi, build_hand_roi
from pipeline.perception_vnext.recognition_schema import (
    BODY_INDICES,
    HAND_POINTS,
    HAND_PRESENCE_THRESHOLD,
    LEFT_HAND_START,
    MINIMUM_REFINED_VALID_POINTS,
    RAW_SCHEMA,
    RIGHT_HAND_START,
    RawSequence,
    body_point_valid,
)

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_ROOT = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/phone_01/candidate_01_dwpose_t_mp_hand"
)
DEFAULT_ONNX = CANDIDATE_ROOT / "export/dwpose_t_singlepass.onnx"
DEFAULT_REFINER = CANDIDATE_ROOT / "refiner/hand_landmarks_detector.tflite"
EXPECTED_ONNX_SHA256 = "37b0f265200f8e249adba1cc9b62925f5e1252245580ed1f66f583d7bce239c0"
EXPECTED_REFINER_SHA256 = "6acda74af3fbf40e68265c20c7394b2bad81a16a481dcd79ad7a081887c3d6b9"
MEAN = np.asarray([123.675, 116.28, 103.53], np.float32).reshape(1, 1, 3)
STD = np.asarray([58.395, 57.12, 57.375], np.float32).reshape(1, 1, 3)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sample_rgb(image_rgb: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Vectorized zero-border bilinear sampling in Android's arithmetic order."""

    image = np.asarray(image_rgb, np.uint8)
    height, width = image.shape[:2]
    sx = np.asarray(x, np.float32)
    sy = np.asarray(y, np.float32)
    x0 = np.floor(sx).astype(np.int32)
    y0 = np.floor(sy).astype(np.int32)
    x1 = x0 + 1
    y1 = y0 + 1
    wx = sx - x0.astype(np.float32)
    wy = sy - y0.astype(np.float32)

    def read(px: np.ndarray, py: np.ndarray) -> np.ndarray:
        valid = (px >= 0) & (px < width) & (py >= 0) & (py < height)
        out = np.zeros(px.shape + (3,), np.float32)
        out[valid] = image[py[valid], px[valid]].astype(np.float32)
        return out

    a = read(x0, y0)
    b = read(x1, y0)
    c = read(x0, y1)
    d = read(x1, y1)
    top = a * (1.0 - wx[..., None]) + b * wx[..., None]
    bottom = c * (1.0 - wx[..., None]) + d * wx[..., None]
    return top * (1.0 - wy[..., None]) + bottom * wy[..., None]


def source_transform(width: int, height: int) -> dict[str, float | int]:
    center_x = np.float32(width * 0.5)
    center_y = np.float32(height * 0.5)
    scale_x = np.float32(width * 1.25)
    scale_y = np.float32(height * 1.25)
    aspect = np.float32(192.0 / 256.0)
    if scale_x > scale_y * aspect:
        scale_y = np.float32(scale_x / aspect)
    else:
        scale_x = np.float32(scale_y * aspect)
    return {
        "source_width": width,
        "source_height": height,
        "center_x": float(center_x),
        "center_y": float(center_y),
        "scale_x": float(scale_x),
        "scale_y": float(scale_y),
    }


def pose_input(image_rgb: np.ndarray) -> tuple[np.ndarray, dict[str, float | int]]:
    height, width = image_rgb.shape[:2]
    transform = source_transform(width, height)
    dx, dy = np.meshgrid(np.arange(192, dtype=np.float32), np.arange(256, dtype=np.float32))
    x = np.float32(transform["center_x"]) + (dx - np.float32(96.0)) * np.float32(
        transform["scale_x"]
    ) / np.float32(192.0)
    y = np.float32(transform["center_y"]) + (dy - np.float32(128.0)) * np.float32(
        transform["scale_x"]
    ) / np.float32(192.0)
    sampled = _sample_rgb(image_rgb, x, y)
    normalized = (sampled - MEAN) / STD
    return np.ascontiguousarray(normalized.transpose(2, 0, 1)[None], np.float32), transform


def hand_input(image_rgb: np.ndarray, roi: HandRoi) -> np.ndarray:
    dx, dy = np.meshgrid(np.arange(224, dtype=np.float32), np.arange(224, dtype=np.float32))
    x = np.float32(roi.center_x - roi.side * 0.5) + dx / np.float32(223.0) * np.float32(roi.side)
    y = np.float32(roi.center_y - roi.side * 0.5) + dy / np.float32(223.0) * np.float32(roi.side)
    return np.ascontiguousarray(_sample_rgb(image_rgb, x, y) / np.float32(255.0), np.float32)


def decode(
    simcc_x: np.ndarray,
    simcc_y: np.ndarray,
    transform: dict[str, float | int],
) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(simcc_x, np.float32).reshape(133, 384)
    y = np.asarray(simcc_y, np.float32).reshape(133, 512)
    x_index = np.argmax(x, axis=1).astype(np.float32)
    y_index = np.argmax(y, axis=1).astype(np.float32)
    support = np.minimum(np.max(x, axis=1), np.max(y, axis=1)).astype(np.float32)
    input_x = np.where(support > 0, x_index / np.float32(2.0), np.float32(-0.5))
    input_y = np.where(support > 0, y_index / np.float32(2.0), np.float32(-0.5))
    points = np.empty((133, 2), np.float32)
    points[:, 0] = (
        input_x / np.float32(192.0) * np.float32(transform["scale_x"])
        + np.float32(transform["center_x"])
        - np.float32(transform["scale_x"]) * np.float32(0.5)
    )
    points[:, 1] = (
        input_y / np.float32(256.0) * np.float32(transform["scale_y"])
        + np.float32(transform["center_y"])
        - np.float32(transform["scale_y"]) * np.float32(0.5)
    )
    return points, support


class Candidate01Offline:
    """Pinned DWPose-t + MediaPipe refiner, with no temporal state."""

    def __init__(self, onnx_path: Path = DEFAULT_ONNX, refiner_path: Path = DEFAULT_REFINER):
        import onnxruntime as ort

        if sha256(onnx_path) != EXPECTED_ONNX_SHA256:
            raise RuntimeError("VNEXT_OFFLINE_ONNX_IDENTITY_MISMATCH")
        if sha256(refiner_path) != EXPECTED_REFINER_SHA256:
            raise RuntimeError("VNEXT_OFFLINE_REFINER_IDENTITY_MISMATCH")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.pose = ort.InferenceSession(
            str(onnx_path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.refiner = MediaPipeHandRefiner(refiner_path, num_threads=2)

    def close(self) -> None:
        self.refiner.close()
        self.pose = None

    def __enter__(self) -> Candidate01Offline:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def process_rgb(self, image_rgb: np.ndarray) -> dict[str, Any]:
        image = np.asarray(image_rgb, np.uint8)
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Candidate 01 expects an RGB uint8 image")
        value, transform = pose_input(image)
        simcc_x, simcc_y = self.pose.run(["simcc_x", "simcc_y"], {"input": value})
        points, support = decode(simcc_x, simcc_y, transform)
        width = int(transform["source_width"])
        height = int(transform["source_height"])
        hands = []
        for start in (LEFT_HAND_START, RIGHT_HAND_START):
            roi = build_hand_roi(
                points[start : start + HAND_POINTS],
                support[start : start + HAND_POINTS],
                width,
                height,
            )
            if roi is None:
                hands.append(
                    {
                        "proposal_present": False,
                        "roi": np.full((3,), np.nan, np.float32),
                        "proposal_support": support[start : start + HAND_POINTS].copy(),
                        "xy": np.full((HAND_POINTS, 2), np.nan, np.float32),
                        "valid": np.zeros((HAND_POINTS,), bool),
                        "presence": np.float32(np.nan),
                        "handedness": np.float32(np.nan),
                        "observed": False,
                    }
                )
                continue
            refined = self.refiner.refine_input(hand_input(image, roi), roi)
            observed = bool(
                refined.presence >= HAND_PRESENCE_THRESHOLD
                and np.count_nonzero(refined.valid) >= MINIMUM_REFINED_VALID_POINTS
            )
            hands.append(
                {
                    "proposal_present": True,
                    "roi": np.asarray([roi.center_x, roi.center_y, roi.side], np.float32),
                    "proposal_support": support[start : start + HAND_POINTS].copy(),
                    "xy": refined.xy_source.copy(),
                    "valid": refined.valid.copy(),
                    "presence": np.float32(refined.presence),
                    "handedness": np.float32(refined.handedness),
                    "observed": observed,
                }
            )
        body_xy = points[BODY_INDICES].copy()
        body_support = support[BODY_INDICES].copy()
        body_valid = body_point_valid(body_xy, body_support, width, height)
        return {
            "source_size": np.asarray([width, height], np.int32),
            "hands": hands,
            "body_xy": body_xy,
            "body_support": body_support,
            "body_valid": body_valid,
            "body_available": bool(np.count_nonzero(body_valid) >= 6),
        }


def _rotate_upright(frame_bgr: np.ndarray, orientation: int) -> np.ndarray:
    if orientation == 90:
        return cv2.rotate(frame_bgr, cv2.ROTATE_90_CLOCKWISE)
    if orientation == 180:
        return cv2.rotate(frame_bgr, cv2.ROTATE_180)
    if orientation == 270:
        return cv2.rotate(frame_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame_bgr


def iter_video_frames(
    video_path: Path,
    span_path: Path | None,
) -> tuple[Iterable[tuple[int, float, str, np.ndarray]], dict[str, Any]]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"VNEXT_VIDEO_DECODE_OPEN:{video_path}")
    if hasattr(cv2, "CAP_PROP_ORIENTATION_AUTO"):
        capture.set(cv2.CAP_PROP_ORIENTATION_AUTO, 0)
    orientation = 0
    if hasattr(cv2, "CAP_PROP_ORIENTATION_META"):
        orientation = int(round(capture.get(cv2.CAP_PROP_ORIENTATION_META))) % 360
    if orientation not in (0, 90, 180, 270):
        orientation = 0
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    if not np.isfinite(fps) or fps <= 0:
        capture.release()
        raise RuntimeError(f"VNEXT_VIDEO_FPS_INVALID:{video_path}")
    start = 0
    end: int | None = None
    span_identity = None
    if span_path is not None and span_path.is_file():
        span = json.loads(span_path.read_text(encoding="utf-8-sig"))
        if not span.get("valid", False):
            capture.release()
            raise RuntimeError(f"VNEXT_INVALID_GOVERNED_SPAN:{span_path}")
        start = int(span["onset"])
        end = int(span["release"])
        span_identity = sha256(span_path)

    def frames() -> Iterable[tuple[int, float, str, np.ndarray]]:
        previous = -math.inf
        index = -1
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                index += 1
                if index < start:
                    continue
                if end is not None and index > end:
                    break
                container_ms = float(capture.get(cv2.CAP_PROP_POS_MSEC))
                fallback_ms = index * 1000.0 / fps
                if not np.isfinite(container_ms) or container_ms <= previous:
                    timestamp_ms = fallback_ms
                    source = "FRAME_INDEX_OVER_CONTAINER_FPS"
                else:
                    timestamp_ms = container_ms
                    source = "CONTAINER_POS_MSEC"
                if timestamp_ms <= previous:
                    timestamp_ms = previous + 1000.0 / fps
                    source = "MONOTONIC_FPS_REPAIR"
                previous = timestamp_ms
                upright = _rotate_upright(frame, orientation)
                yield index, timestamp_ms, source, cv2.cvtColor(upright, cv2.COLOR_BGR2RGB)
        finally:
            capture.release()

    return frames(), {
        "native_fps": fps,
        "orientation_degrees_clockwise": orientation,
        "span_start_inclusive": start,
        "span_end_inclusive": end,
        "span_sha256": span_identity,
    }


def extract_video(
    runtime: Candidate01Offline,
    row: dict[str, str],
) -> RawSequence:
    video = Path(row["raw_video_path"])
    if not video.is_file() or sha256(video).upper() != row["raw_video_sha256"].upper():
        raise RuntimeError(f"VNEXT_VIDEO_IDENTITY:{row['sample_id']}")
    span_text = row.get("span_path", "").strip()
    span = Path(span_text) if span_text else None
    iterator, video_meta = iter_video_frames(video, span)
    records: list[tuple[int, float, str, dict[str, Any]]] = []
    for frame_index, timestamp_ms, timestamp_source, image_rgb in iterator:
        records.append(
            (frame_index, timestamp_ms, timestamp_source, runtime.process_rgb(image_rgb))
        )
    if not records:
        raise RuntimeError(f"VNEXT_VIDEO_NO_SIGN_FRAMES:{row['sample_id']}")
    t = len(records)
    sequence = RawSequence(
        metadata={
            "schema": RAW_SCHEMA,
            "candidate_id": "dwpose_t_256x192_plus_mp_hand_224",
            "sample_id": row["sample_id"],
            "split": row["split"],
            "class_id": int(row["class_id"]),
            "canonical_gloss": row["canonical_gloss"],
            "signer_id": row["signer_group_id"],
            "source_id": row["source_dataset"],
            "source_video_path": str(video),
            "source_video_sha256": row["raw_video_sha256"].lower(),
            "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB",
            "timestamp_sources": sorted({record[2] for record in records}),
            "duration_scope": (
                "governed_span"
                if video_meta["span_end_inclusive"] is not None
                else "whole_isolated_clip"
            ),
            "current_frame_only": True,
            "synthetic_depth": False,
            "carry_forward": False,
            **video_meta,
        },
        frame_index=np.asarray([record[0] for record in records], np.int32),
        timestamp_ms=np.asarray([record[1] for record in records], np.float64),
        source_size=np.stack([record[3]["source_size"] for record in records]),
        hand_xy=np.stack([[hand["xy"] for hand in record[3]["hands"]] for record in records]),
        hand_proposal_support=np.stack(
            [[hand["proposal_support"] for hand in record[3]["hands"]] for record in records]
        ),
        hand_joint_valid=np.stack(
            [[hand["valid"] for hand in record[3]["hands"]] for record in records]
        ),
        hand_presence=np.asarray(
            [[hand["presence"] for hand in record[3]["hands"]] for record in records],
            np.float32,
        ),
        hand_observed=np.asarray(
            [[hand["observed"] for hand in record[3]["hands"]] for record in records],
            bool,
        ),
        hand_proposal_present=np.asarray(
            [[hand["proposal_present"] for hand in record[3]["hands"]] for record in records],
            bool,
        ),
        hand_roi_center_side=np.stack(
            [[hand["roi"] for hand in record[3]["hands"]] for record in records]
        ),
        hand_handedness_diagnostic=np.asarray(
            [[hand["handedness"] for hand in record[3]["hands"]] for record in records],
            np.float32,
        ),
        body_xy=np.stack([record[3]["body_xy"] for record in records]),
        body_support=np.stack([record[3]["body_support"] for record in records]),
        body_valid=np.stack([record[3]["body_valid"] for record in records]),
        body_available=np.asarray([record[3]["body_available"] for record in records], bool),
    )
    sequence.validate()
    if t != len(sequence.timestamp_ms):
        raise AssertionError("raw sequence assembly mismatch")
    return sequence
