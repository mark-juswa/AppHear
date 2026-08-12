"""Run the paired E2d MediaPipe detector operating-point sweep."""

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

from .e2c import _canonical_hands, _read_video

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "detector_e2d.yaml"
INDEX_FIELDS = (
    "item_id",
    "label",
    "candidate_id",
    "mode",
    "detection_threshold",
    "presence_threshold",
    "clip_id",
    "split",
    "participant_id",
    "gloss",
    "video_file",
    "frame_index",
    "timestamp_ms",
    "hand",
    "cadence",
    "target_detected",
    "target_score",
    "raw_detected_hands",
)
LATENCY_FIELDS = (
    "clip_id",
    "candidate_id",
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
class Candidate:
    candidate_id: str
    mode: str
    detection: float
    presence: float


@dataclass(frozen=True)
class Detection:
    scores: np.ndarray
    raw_detected_hands: int
    latency_ms: float


class OperatingPointRunner:
    def __init__(self, raw: dict[str, Any], candidate: Candidate, model_path: Path) -> None:
        model = raw["model"]
        running_mode = (
            vision.RunningMode.IMAGE
            if candidate.mode == "image"
            else vision.RunningMode.VIDEO
        )
        self._mode = candidate.mode
        self._landmarker = vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
                running_mode=running_mode,
                num_hands=int(model["num_hands"]),
                min_hand_detection_confidence=candidate.detection,
                min_hand_presence_confidence=candidate.presence,
                min_tracking_confidence=float(model["min_tracking_confidence"]),
            )
        )

    def close(self) -> None:
        self._landmarker.close()

    def __enter__(self) -> OperatingPointRunner:
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
        _hands, scores = _canonical_hands(result)
        return Detection(scores, len(result.hand_landmarks), latency_ms)


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


def _load_positive_items(source_run: Path) -> list[dict[str, Any]]:
    items = []
    for row in _read_csv(source_run / "internal_index.csv"):
        if row["strategy"] != "control_hold_100":
            continue
        items.append(
            {
                **row,
                "item_id": row["base_id"],
                "label": "positive",
            }
        )
    if len(items) != 120:
        raise ValueError(f"expected 120 positive E2b items, found {len(items)}")
    return items


def _load_negative_candidates(
    source_run: Path, audit_name: str, seed: int
) -> list[dict[str, Any]]:
    metadata = {
        row["crop_id"]: row for row in _read_csv(source_run / "internal_index.csv")
    }
    labels: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    representatives: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for audit in _read_csv(source_run / audit_name):
        meta = metadata.get(audit["crop_id"])
        if meta is None:
            raise ValueError(f"negative audit crop absent from index: {audit['crop_id']}")
        key = (meta["clip_id"], meta["frame_index"], meta["hand"], meta["cadence"])
        labels[key].append(audit["visible_hand"])
        representatives[key] = meta
    negatives = []
    for key, values in labels.items():
        if values and all(value == "no" for value in values):
            row = representatives[key]
            negatives.append(
                {
                    **row,
                    "item_id": _blind_id(seed, ("negative", *key)),
                    "label": "negative",
                }
            )
    return negatives


def _balanced_negative_selection(
    items: list[dict[str, Any]], count: int, seed: int
) -> list[dict[str, Any]]:
    groups: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        groups[(int(item["cadence"]), str(item["hand"]))].append(item)
    strata = (
        (1, "left"),
        (1, "right"),
        (4, "left"),
        (4, "right"),
        (8, "left"),
        (8, "right"),
    )
    if count % len(strata) != 0:
        raise ValueError("negative item count must divide evenly across six strata")
    per_group = count // len(strata)
    rng = random.Random(seed)
    selected = []
    for key in strata:
        candidates = groups[key]
        rng.shuffle(candidates)
        if len(candidates) < per_group:
            raise ValueError(f"negative stratum {key} has only {len(candidates)} items")
        selected.extend(candidates[:per_group])
    rng.shuffle(selected)
    return selected


def _smoke_items(
    items: list[dict[str, Any]], label: str, seed: int
) -> list[dict[str, Any]]:
    groups: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        groups[(int(item["cadence"]), str(item["hand"]))].append(item)
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
        if label == "positive":
            candidates.sort(key=lambda row: row.get("roi_source") != "missing")
        selected.append(candidates[0])
    return selected


def _load_candidates(raw: dict[str, Any]) -> list[Candidate]:
    candidates = [
        Candidate(
            candidate_id=str(row["id"]),
            mode=str(row["mode"]),
            detection=float(row["detection"]),
            presence=float(row["presence"]),
        )
        for row in raw["candidates"]
    ]
    ids = [candidate.candidate_id for candidate in candidates]
    if len(set(ids)) != len(ids):
        raise ValueError("candidate ids must be unique")
    control = str(raw["gates"]["control_candidate"])
    if control not in ids:
        raise ValueError(f"control candidate not defined: {control}")
    if any(candidate.mode not in {"image", "video"} for candidate in candidates):
        raise ValueError("candidate mode must be image or video")
    return candidates


def _run_sequence(
    raw: dict[str, Any],
    candidate: Candidate,
    model_path: Path,
    cadence: int,
    clip_id: str,
    frames: list[np.ndarray],
    fps: float,
) -> tuple[dict[int, Detection], list[dict[str, Any]]]:
    detections = {}
    latency_rows = []
    with OperatingPointRunner(raw, candidate, model_path) as runner:
        for frame_index in range(0, len(frames), cadence):
            timestamp_ms = int(round(frame_index * 1000.0 / fps))
            result = runner.detect(frames[frame_index], timestamp_ms)
            detections[frame_index] = result
            latency_rows.append(
                {
                    "clip_id": clip_id,
                    "candidate_id": candidate.candidate_id,
                    "mode": candidate.mode,
                    "cadence": cadence,
                    "frame_index": frame_index,
                    "timestamp_ms": timestamp_ms,
                    "latency_ms": round(result.latency_ms, 6),
                    "raw_detected_hands": result.raw_detected_hands,
                    "left_present": int(result.scores[0] > 0.0),
                    "right_present": int(result.scores[1] > 0.0),
                }
            )
    return detections, latency_rows


def _percentile(values: list[float], value: float) -> float | None:
    return float(np.percentile(np.asarray(values), value)) if values else None


def _summary(
    index_rows: list[dict[str, Any]],
    latency_rows: list[dict[str, Any]],
    candidates: list[Candidate],
    raw: dict[str, Any],
) -> dict[str, Any]:
    cadences = tuple(int(value) for value in raw["sampling"]["cadences"])
    metrics: dict[str, Any] = {}
    hand_metrics: dict[str, Any] = {}
    for candidate in candidates:
        for cadence in cadences:
            rows = [
                row
                for row in index_rows
                if row["candidate_id"] == candidate.candidate_id
                and int(row["cadence"]) == cadence
            ]
            positives = [row for row in rows if row["label"] == "positive"]
            negatives = [row for row in rows if row["label"] == "negative"]
            timings = [
                float(row["latency_ms"])
                for row in latency_rows
                if row["candidate_id"] == candidate.candidate_id
                and int(row["cadence"]) == cadence
            ]
            sequence_any = [
                row["left_present"] or row["right_present"]
                for row in latency_rows
                if row["candidate_id"] == candidate.candidate_id
                and int(row["cadence"]) == cadence
            ]
            sequence_both = [
                row["left_present"] and row["right_present"]
                for row in latency_rows
                if row["candidate_id"] == candidate.candidate_id
                and int(row["cadence"]) == cadence
            ]
            metrics[f"{candidate.candidate_id}|cadence={cadence}"] = {
                "positive_items": len(positives),
                "positive_detected": sum(
                    bool(row["target_detected"]) for row in positives
                ),
                "positive_recall": (
                    sum(bool(row["target_detected"]) for row in positives) / len(positives)
                    if positives
                    else None
                ),
                "negative_items": len(negatives),
                "negative_false_roi": sum(
                    bool(row["target_detected"]) for row in negatives
                ),
                "negative_false_roi_rate": (
                    sum(bool(row["target_detected"]) for row in negatives) / len(negatives)
                    if negatives
                    else None
                ),
                "inference_calls": len(timings),
                "latency_p50_ms": _percentile(timings, 50),
                "latency_p95_ms": _percentile(timings, 95),
                "sequence_any_hand_rate": (
                    sum(sequence_any) / len(sequence_any) if sequence_any else None
                ),
                "sequence_two_hand_rate": (
                    sum(sequence_both) / len(sequence_both) if sequence_both else None
                ),
            }
        for hand in ("left", "right"):
            positives = [
                row
                for row in index_rows
                if row["candidate_id"] == candidate.candidate_id
                and row["label"] == "positive"
                and row["hand"] == hand
            ]
            hand_metrics[f"{candidate.candidate_id}|hand={hand}"] = {
                "positive_items": len(positives),
                "positive_recall": sum(
                    bool(row["target_detected"]) for row in positives
                )
                / len(positives),
            }

    gates = raw["gates"]
    control_id = str(gates["control_candidate"])
    min_gain = float(gates["min_positive_recall_gain"])
    max_false = float(gates["max_negative_false_roi_rate"])
    max_false_increase = float(gates["max_negative_false_roi_increase"])
    max_latency_ratio = float(
        gates["max_candidate_to_control_p95_latency_ratio"]
    )
    comparisons: dict[str, Any] = {}
    for candidate in candidates:
        if candidate.candidate_id == control_id:
            continue
        cadence_results = {}
        candidate_passed = True
        for cadence in cadences:
            control = metrics[f"{control_id}|cadence={cadence}"]
            result = metrics[f"{candidate.candidate_id}|cadence={cadence}"]
            recall_gain = result["positive_recall"] - control["positive_recall"]
            false_increase = (
                result["negative_false_roi_rate"] - control["negative_false_roi_rate"]
            )
            latency_ratio = result["latency_p95_ms"] / control["latency_p95_ms"]
            passed = (
                recall_gain >= min_gain
                and result["negative_false_roi_rate"] <= max_false
                and false_increase <= max_false_increase
                and latency_ratio <= max_latency_ratio
            )
            candidate_passed = candidate_passed and passed
            cadence_results[str(cadence)] = {
                "positive_recall_gain": recall_gain,
                "negative_false_roi_increase": false_increase,
                "candidate_negative_false_roi_rate": result[
                    "negative_false_roi_rate"
                ],
                "candidate_to_control_p95_latency_ratio": latency_ratio,
                "passed": passed,
            }
        hand_results = {}
        for hand in ("left", "right"):
            control = hand_metrics[f"{control_id}|hand={hand}"]
            result = hand_metrics[f"{candidate.candidate_id}|hand={hand}"]
            gain = result["positive_recall"] - control["positive_recall"]
            passed = gain >= min_gain
            candidate_passed = candidate_passed and passed
            hand_results[hand] = {"positive_recall_gain": gain, "passed": passed}
        comparisons[candidate.candidate_id] = {
            "cadences": cadence_results,
            "hands": hand_results,
            "automatic_gate_passed": candidate_passed,
        }
    return {
        "control_candidate": control_id,
        "positive_items": sum(
            row["label"] == "positive" for row in index_rows
        )
        // len(candidates),
        "negative_items": sum(
            row["label"] == "negative" for row in index_rows
        )
        // len(candidates),
        "metrics": metrics,
        "hand_metrics": hand_metrics,
        "comparisons": comparisons,
        "promoted_candidates": [
            candidate_id
            for candidate_id, result in comparisons.items()
            if result["automatic_gate_passed"]
        ],
    }


def _source_hash() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


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
    positive_run = Path(raw["source_positive"]["run_dir"])
    negative_run = Path(raw["source_negative"]["run_dir"])
    positives = _load_positive_items(positive_run)
    negative_candidates = _load_negative_candidates(
        negative_run, str(raw["source_negative"]["audit_csv"]), seed
    )
    if smoke:
        positives = _smoke_items(positives, "positive", seed)
        negatives = _smoke_items(negative_candidates, "negative", seed)
    else:
        if len(positives) != int(raw["sampling"]["engineering_positive_items"]):
            raise ValueError("positive item count does not match frozen config")
        negatives = _balanced_negative_selection(
            negative_candidates,
            int(raw["sampling"]["engineering_negative_items"]),
            seed,
        )
    items = [*positives, *negatives]
    candidates = _load_candidates(raw)
    output_dir = Path(raw["output"]["root"]) / run_id
    if output_dir.exists():
        raise FileExistsError(f"run directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    by_clip: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_clip[str(item["clip_id"])].append(item)
    videos_dir = Path(raw["dataset"]["root"]) / raw["dataset"]["videos_subdir"]
    index_rows: list[dict[str, Any]] = []
    latency_rows: list[dict[str, Any]] = []
    for clip_number, (clip_id, clip_items) in enumerate(sorted(by_clip.items()), start=1):
        first = clip_items[0]
        frames, fps, _width, _height = _read_video(videos_dir / first["video_file"])
        sequence: dict[tuple[str, int], dict[int, Detection]] = {}
        for cadence in sorted({int(item["cadence"]) for item in clip_items}):
            for candidate in candidates:
                detections, timings = _run_sequence(
                    raw, candidate, model_path, cadence, clip_id, frames, fps
                )
                sequence[(candidate.candidate_id, cadence)] = detections
                latency_rows.extend(timings)
        for item in clip_items:
            frame_index = int(item["frame_index"])
            cadence = int(item["cadence"])
            if frame_index % cadence != 0 or frame_index >= len(frames):
                raise ValueError(
                    f"invalid item frame/cadence: {clip_id}/{frame_index}/k{cadence}"
                )
            hand_index = 0 if item["hand"] == "left" else 1
            for candidate in candidates:
                detection = sequence[(candidate.candidate_id, cadence)][frame_index]
                index_rows.append(
                    {
                        "item_id": item["item_id"],
                        "label": item["label"],
                        "candidate_id": candidate.candidate_id,
                        "mode": candidate.mode,
                        "detection_threshold": candidate.detection,
                        "presence_threshold": candidate.presence,
                        "clip_id": clip_id,
                        "split": item["split"],
                        "participant_id": item["participant_id"],
                        "gloss": item["gloss"],
                        "video_file": item["video_file"],
                        "frame_index": frame_index,
                        "timestamp_ms": int(round(frame_index * 1000.0 / fps)),
                        "hand": item["hand"],
                        "cadence": cadence,
                        "target_detected": int(detection.scores[hand_index] > 0.0),
                        "target_score": round(float(detection.scores[hand_index]), 6),
                        "raw_detected_hands": detection.raw_detected_hands,
                    }
                )
        print(f"[tracking/e2d] {clip_number}/{len(by_clip)} {clip_id}")

    _write_csv(output_dir / "item_index.csv", INDEX_FIELDS, index_rows)
    _write_csv(output_dir / "latency.csv", LATENCY_FIELDS, latency_rows)
    summary = _summary(index_rows, latency_rows, candidates, raw)
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
                "mediapipe_version": getattr(mp, "__version__", "unknown"),
                "hand_model": str(model_path),
                "hand_model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                "positive_source": str(positive_run),
                "negative_source": str(negative_run),
                "positive_items": len(positives),
                "negative_items": len(negatives),
                "candidates": [candidate.__dict__ for candidate in candidates],
                "created_utc": datetime.now(UTC).isoformat(),
            },
            handle,
            indent=2,
        )
    print(json.dumps(summary, indent=2))
    print(f"[tracking/e2d] complete -> {output_dir}")
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AppHear E2d MediaPipe detector threshold sweep"
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
        print(f"[tracking/e2d] ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
