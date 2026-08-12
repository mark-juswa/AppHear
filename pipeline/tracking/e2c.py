"""Generate paired MediaPipe IMAGE-versus-VIDEO hand-tracking evidence for E2c."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np
import yaml
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from pipeline.crops.config import RoiConfig
from pipeline.crops.roi import (
    direct_square_box,
    extract_square_crop,
    sharpness_variance,
)
from pipeline.extract.constants import HAND_SLOTS, MISSING, NUM_HAND_LANDMARKS, NUM_HANDS

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "tracking_e2c.yaml"
AUDIT_FIELDS = (
    "base_id",
    "panel_path",
    "source_blur",
    "a_quality",
    "b_quality",
    "notes",
)
INDEX_FIELDS = (
    "base_id",
    "mode",
    "clip_id",
    "split",
    "participant_id",
    "gloss",
    "video_file",
    "frame_index",
    "timestamp_ms",
    "hand",
    "cadence",
    "hand_score",
    "raw_detected_hands",
    "roi_available",
    "box_x1",
    "box_y1",
    "box_x2",
    "box_y2",
    "padding_fraction",
    "sharpness",
    "crop_path",
    "panel_path",
)
LATENCY_FIELDS = (
    "clip_id",
    "mode",
    "cadence",
    "frame_index",
    "timestamp_ms",
    "latency_ms",
    "raw_detected_hands",
    "left_present",
    "right_present",
)


@dataclass(frozen=True)
class Detection:
    hands_image: np.ndarray
    hand_score: np.ndarray
    raw_detected_hands: int
    latency_ms: float


class HandRunner:
    """One MediaPipe instance. VIDEO runners must never cross clip boundaries."""

    def __init__(self, raw: dict[str, Any], mode: str, model_path: Path) -> None:
        model = raw["model"]
        running_mode = (
            vision.RunningMode.IMAGE if mode == "image" else vision.RunningMode.VIDEO
        )
        self._mode = mode
        self._landmarker = vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
                running_mode=running_mode,
                num_hands=int(model["num_hands"]),
                min_hand_detection_confidence=float(
                    model["min_hand_detection_confidence"]
                ),
                min_hand_presence_confidence=float(model["min_hand_presence_confidence"]),
                min_tracking_confidence=float(model["min_tracking_confidence"]),
            )
        )

    def close(self) -> None:
        self._landmarker.close()

    def __enter__(self) -> HandRunner:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def detect(self, frame_bgr: np.ndarray, timestamp_ms: int) -> Detection:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        started = time.perf_counter_ns()
        if self._mode == "image":
            result = self._landmarker.detect(image)
        else:
            result = self._landmarker.detect_for_video(image, timestamp_ms)
        latency_ms = (time.perf_counter_ns() - started) / 1_000_000.0
        hands, scores = _canonical_hands(result)
        return Detection(hands, scores, len(result.hand_landmarks), latency_ms)


def _canonical_hands(result: Any) -> tuple[np.ndarray, np.ndarray]:
    hands = np.full((NUM_HANDS, NUM_HAND_LANDMARKS, 3), MISSING, dtype=np.float32)
    scores = np.zeros((NUM_HANDS,), dtype=np.float32)
    for index, handedness in enumerate(result.handedness):
        label = handedness[0].category_name
        slot = HAND_SLOTS.index(label) if label in HAND_SLOTS else index % NUM_HANDS
        hands[slot] = np.asarray(
            [[point.x, point.y, point.z] for point in result.hand_landmarks[index]],
            dtype=np.float32,
        )
        scores[slot] = float(handedness[0].score)
    return hands, scores


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(
    path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def _blind_id(seed: int, fields: tuple[object, ...]) -> str:
    payload = "|".join(str(value) for value in (seed, *fields))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _load_base_items(source_run: Path) -> list[dict[str, str]]:
    rows = _read_csv(source_run / "internal_index.csv")
    bases: dict[str, dict[str, str]] = {}
    for row in rows:
        if row["strategy"] == "control_hold_100":
            bases[row["base_id"]] = row
    if len(bases) != 120:
        raise ValueError(f"expected 120 E2b base items, found {len(bases)}")
    return list(bases.values())


def _select_smoke(items: list[dict[str, str]], seed: int) -> list[dict[str, str]]:
    groups: dict[tuple[int, str], list[dict[str, str]]] = defaultdict(list)
    for item in items:
        groups[(int(item["cadence"]), item["hand"])].append(item)
    rng = random.Random(seed)
    selected = []
    for key in (
        (1, "left"),
        (1, "right"),
        (4, "left"),
        (4, "right"),
        (8, "left"),
        (8, "right"),
    ):
        candidates = groups[key]
        rng.shuffle(candidates)
        candidates.sort(key=lambda row: row["roi_source"] != "missing")
        selected.append(candidates[0])
    return selected


def _read_video(path: Path) -> tuple[list[np.ndarray], float, int, int]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise OSError(f"cannot open video: {path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0.0:
        capture.release()
        raise ValueError(f"invalid FPS {fps}: {path}")
    frames = []
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frames.append(frame)
    finally:
        capture.release()
    if not frames:
        raise ValueError(f"video contains no frames: {path}")
    return frames, fps, width, height


def _run_sequence(
    raw: dict[str, Any],
    model_path: Path,
    mode: str,
    cadence: int,
    clip_id: str,
    frames: list[np.ndarray],
    fps: float,
) -> tuple[dict[int, Detection], list[dict[str, Any]]]:
    detections: dict[int, Detection] = {}
    latency_rows: list[dict[str, Any]] = []
    with HandRunner(raw, mode, model_path) as runner:
        for frame_index in range(0, len(frames), cadence):
            timestamp_ms = int(round(frame_index * 1000.0 / fps))
            detection = runner.detect(frames[frame_index], timestamp_ms)
            detections[frame_index] = detection
            latency_rows.append(
                {
                    "clip_id": clip_id,
                    "mode": mode,
                    "cadence": cadence,
                    "frame_index": frame_index,
                    "timestamp_ms": timestamp_ms,
                    "latency_ms": round(detection.latency_ms, 6),
                    "raw_detected_hands": detection.raw_detected_hands,
                    "left_present": int(detection.hand_score[0] > 0.0),
                    "right_present": int(detection.hand_score[1] > 0.0),
                }
            )
    return detections, latency_rows


def _roi_config(raw: dict[str, Any]) -> RoiConfig:
    crop = raw["crop"]
    pad = tuple(int(value) for value in crop["pad_value_rgb"])
    if len(pad) != 3:
        raise ValueError("crop.pad_value_rgb must have three values")
    return RoiConfig(
        crop_sizes=(int(crop["diagnostic_size"]),),
        expansion_factors=(float(crop["diagnostic_expansion"]),),
        min_valid_landmarks=int(crop["min_valid_landmarks"]),
        min_side_fraction=float(crop["min_side_fraction"]),
        max_side_fraction=float(crop["max_side_fraction"]),
        max_hold_ms=0,
        pad_value_rgb=(pad[0], pad[1], pad[2]),
    )


def _paired_panel(
    frame: np.ndarray,
    crop_a: np.ndarray | None,
    crop_b: np.ndarray | None,
    crop_size: int,
    full_width: int,
    hand: str,
) -> np.ndarray:
    height, width = frame.shape[:2]
    panel_height = max(1, round(height * full_width / width))
    full = cv2.resize(frame, (full_width, panel_height), interpolation=cv2.INTER_AREA)
    cv2.putText(
        full,
        f"TARGET {hand.upper()}",
        (8, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    crop_width = panel_height
    panels = [full]
    for label, crop in (("A", crop_a), ("B", crop_b)):
        image = (
            crop
            if crop is not None
            else np.zeros((crop_size, crop_size, 3), dtype=np.uint8)
        )
        image = cv2.resize(
            image, (crop_width, panel_height), interpolation=cv2.INTER_NEAREST
        )
        cv2.putText(
            image,
            label,
            (8, 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        panels.append(image)
    return np.concatenate(panels, axis=1)


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values), percentile))


def _generation_summary(
    index_rows: list[dict[str, Any]],
    latency_rows: list[dict[str, Any]],
    raw: dict[str, Any],
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for mode in ("image", "video"):
        for cadence in tuple(int(value) for value in raw["sampling"]["cadences"]):
            rows = [
                row
                for row in index_rows
                if row["mode"] == mode and int(row["cadence"]) == cadence
            ]
            latency = [
                float(row["latency_ms"])
                for row in latency_rows
                if row["mode"] == mode and int(row["cadence"]) == cadence
            ]
            metrics[f"{mode}|cadence={cadence}"] = {
                "base_items": len(rows),
                "available": sum(bool(row["roi_available"]) for row in rows),
                "availability_rate": (
                    sum(bool(row["roi_available"]) for row in rows) / len(rows)
                    if rows
                    else None
                ),
                "inference_calls": len(latency),
                "latency_p50_ms": _percentile(latency, 50),
                "latency_p95_ms": _percentile(latency, 95),
            }
    comparisons = {}
    min_gain = float(raw["audit"]["diagnostic_min_availability_gain"])
    max_latency_ratio = float(
        raw["audit"]["diagnostic_max_video_to_image_p95_latency_ratio"]
    )
    for cadence in tuple(int(value) for value in raw["sampling"]["cadences"]):
        image = metrics[f"image|cadence={cadence}"]
        video = metrics[f"video|cadence={cadence}"]
        gain = video["availability_rate"] - image["availability_rate"]
        ratio = video["latency_p95_ms"] / image["latency_p95_ms"]
        comparisons[str(cadence)] = {
            "availability_gain": gain,
            "video_to_image_p95_latency_ratio": ratio,
            "automatic_gate_passed": gain >= min_gain and ratio <= max_latency_ratio,
        }
    return {
        "known_visible_base_items": len(index_rows) // 2,
        "metrics": metrics,
        "paired_comparisons": comparisons,
        "automatic_gate_passed": all(
            value["automatic_gate_passed"] for value in comparisons.values()
        ),
    }


def _source_hash() -> str:
    digest = hashlib.sha256()
    for name in ("e2c.py", "review.py", "audit.py"):
        path = Path(__file__).parent / name
        if path.exists():
            digest.update(name.encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def run(config_path: Path, run_id: str, smoke: bool) -> Path:
    with config_path.open("r", encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle)
    seed = int(raw["seed"])
    repo_root = Path(__file__).resolve().parents[2]
    model_path = Path(raw["model"]["hand_task"])
    if not model_path.is_absolute():
        model_path = repo_root / model_path
    if not model_path.is_file():
        raise FileNotFoundError(f"hand model missing: {model_path}")
    source_run = Path(raw["source_e2b"]["run_dir"])
    if not (source_run / "internal_index.csv").is_file():
        raise FileNotFoundError(f"E2b index missing: {source_run / 'internal_index.csv'}")
    output_dir = Path(raw["output"]["root"]) / run_id
    if output_dir.exists():
        raise FileExistsError(f"run directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    items = _load_base_items(source_run)
    if smoke:
        items = _select_smoke(items, seed)
    elif len(items) != int(raw["sampling"]["engineering_base_items"]):
        raise ValueError("E2c engineering count does not match frozen E2b base set")
    by_clip: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in items:
        by_clip[item["clip_id"]].append(item)

    dataset_root = Path(raw["dataset"]["root"])
    videos_dir = dataset_root / raw["dataset"]["videos_subdir"]
    roi = _roi_config(raw)
    crop_size = int(raw["crop"]["diagnostic_size"])
    expansion = float(raw["crop"]["diagnostic_expansion"])
    index_rows: list[dict[str, Any]] = []
    latency_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    blind_rows: list[dict[str, Any]] = []

    for clip_number, (clip_id, clip_items) in enumerate(sorted(by_clip.items()), start=1):
        first = clip_items[0]
        frames, fps, width, height = _read_video(videos_dir / first["video_file"])
        sequence: dict[tuple[str, int], dict[int, Detection]] = {}
        for cadence in sorted({int(item["cadence"]) for item in clip_items}):
            for mode in ("image", "video"):
                detections, timings = _run_sequence(
                    raw, model_path, mode, cadence, clip_id, frames, fps
                )
                sequence[(mode, cadence)] = detections
                latency_rows.extend(timings)

        for item in clip_items:
            frame_index = int(item["frame_index"])
            cadence = int(item["cadence"])
            if frame_index % cadence != 0:
                raise ValueError(
                    f"base frame {frame_index} is not aligned to cadence {cadence}"
                )
            if frame_index >= len(frames):
                raise ValueError(f"base frame outside video: {clip_id}/{frame_index}")
            hand_index = 0 if item["hand"] == "left" else 1
            crops: dict[str, np.ndarray | None] = {}
            pending_rows: list[dict[str, Any]] = []
            for mode in ("image", "video"):
                detection = sequence[(mode, cadence)][frame_index]
                box = None
                if detection.hand_score[hand_index] > 0.0:
                    box = direct_square_box(
                        detection.hands_image[hand_index],
                        width,
                        height,
                        expansion,
                        roi,
                    )
                crop = None
                padding = 1.0
                sharpness = 0.0
                crop_path = output_dir / "crops" / mode / f"{item['base_id']}.jpg"
                if box is not None:
                    crop, padding = extract_square_crop(
                        frames[frame_index], box, crop_size, roi.pad_value_rgb
                    )
                    sharpness = sharpness_variance(crop)
                    crop_path.parent.mkdir(parents=True, exist_ok=True)
                    cv2.imwrite(
                        str(crop_path),
                        crop,
                        [cv2.IMWRITE_JPEG_QUALITY, int(raw["audit"]["jpeg_quality"])],
                    )
                crops[mode] = crop
                coordinates = box or ("", "", "", "")
                pending_rows.append(
                    {
                        "base_id": item["base_id"],
                        "mode": mode,
                        "clip_id": clip_id,
                        "split": item["split"],
                        "participant_id": item["participant_id"],
                        "gloss": item["gloss"],
                        "video_file": item["video_file"],
                        "frame_index": frame_index,
                        "timestamp_ms": int(round(frame_index * 1000.0 / fps)),
                        "hand": item["hand"],
                        "cadence": cadence,
                        "hand_score": round(
                            float(detection.hand_score[hand_index]), 6
                        ),
                        "raw_detected_hands": detection.raw_detected_hands,
                        "roi_available": int(box is not None),
                        "box_x1": coordinates[0],
                        "box_y1": coordinates[1],
                        "box_x2": coordinates[2],
                        "box_y2": coordinates[3],
                        "padding_fraction": round(padding, 6),
                        "sharpness": round(sharpness, 4),
                        "crop_path": str(crop_path) if crop is not None else "",
                    }
                )
            first_mode = (
                "image"
                if int(_blind_id(seed, (item["base_id"], "mapping")), 16) % 2 == 0
                else "video"
            )
            second_mode = "video" if first_mode == "image" else "image"
            panel_path = output_dir / "review_panels" / f"{item['base_id']}.jpg"
            panel_path.parent.mkdir(exist_ok=True)
            panel = _paired_panel(
                frames[frame_index],
                crops[first_mode],
                crops[second_mode],
                crop_size,
                int(raw["audit"]["panel_full_frame_width"]),
                item["hand"],
            )
            cv2.imwrite(
                str(panel_path),
                panel,
                [cv2.IMWRITE_JPEG_QUALITY, int(raw["audit"]["jpeg_quality"])],
            )
            for row in pending_rows:
                row["panel_path"] = str(panel_path)
                index_rows.append(row)
            blind_rows.append(
                {
                    "base_id": item["base_id"],
                    "mode_a": first_mode,
                    "mode_b": second_mode,
                }
            )
            audit_rows.append(
                {
                    "base_id": item["base_id"],
                    "panel_path": str(panel_path),
                }
            )
        print(f"[tracking/e2c] {clip_number}/{len(by_clip)} {clip_id}")

    random.Random(seed).shuffle(audit_rows)
    _write_csv(output_dir / "internal_index.csv", INDEX_FIELDS, index_rows)
    _write_csv(output_dir / "latency.csv", LATENCY_FIELDS, latency_rows)
    _write_csv(
        output_dir / "blind_map.csv", ("base_id", "mode_a", "mode_b"), blind_rows
    )
    _write_csv(output_dir / "audit_template.csv", AUDIT_FIELDS, audit_rows)
    summary = _generation_summary(index_rows, latency_rows, raw)
    with (output_dir / "generation_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    config_hash = hashlib.sha256(
        json.dumps(raw, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    with (output_dir / "run_config.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "run_id": run_id,
                "smoke": smoke,
                "experiment_version": raw["experiment_version"],
                "seed": seed,
                "config_hash": config_hash,
                "source_code_hash": _source_hash(),
                "source_e2b_run": str(source_run),
                "mediapipe_version": getattr(mp, "__version__", "unknown"),
                "hand_model": str(model_path),
                "hand_model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                "base_items": len(items),
                "created_utc": datetime.now(UTC).isoformat(),
            },
            handle,
            indent=2,
        )
    print(json.dumps(summary, indent=2))
    print(f"[tracking/e2c] complete -> {output_dir}")
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AppHear E2c paired IMAGE-versus-VIDEO tracking"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    run_id = args.run_id or (
        f"{'smoke' if args.smoke else 'engineering'}_"
        f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%SZ')}"
    )
    try:
        run(args.config, run_id, args.smoke)
    except (FileExistsError, FileNotFoundError, OSError, ValueError) as error:
        print(f"[tracking/e2c] ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
