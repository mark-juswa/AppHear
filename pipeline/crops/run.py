"""Run the bounded E2 RGB hand-crop quality experiment.

This stage reuses existing IMAGE-mode landmarks and source videos. It never runs MediaPipe,
trains a model, or writes into production feature/model directories.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.extract.schema import ClipLandmarks

from .config import CropConfig, load_config
from .roi import causal_roi_sequence, extract_square_crop, sharpness_variance
from .sampling import ClipSample, select_clips, select_frame_indices

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "crops_e2.yaml"
INDEX_FIELDS = (
    "crop_id",
    "clip_id",
    "split",
    "participant_id",
    "gloss",
    "video_file",
    "frame_index",
    "timestamp_ms",
    "hand",
    "cadence",
    "crop_size",
    "expansion",
    "roi_source",
    "roi_age_ms",
    "box_x1",
    "box_y1",
    "box_x2",
    "box_y2",
    "padding_fraction",
    "sharpness",
    "panel_path",
    "crop_path",
)


def _phase_count(config: CropConfig, phase: str) -> tuple[int, int]:
    if phase == "smoke":
        return config.sampling.smoke_clips, config.sampling.smoke_frames_per_clip
    if phase == "engineering":
        return config.sampling.engineering_clips, config.sampling.frames_per_clip
    return config.sampling.audit_clips, config.sampling.frames_per_clip


def _phase_candidates(
    config: CropConfig,
    phase: str,
    crop_size: int | None,
    expansion: float | None,
) -> tuple[tuple[int, ...], tuple[float, ...], tuple[int, ...]]:
    if phase == "smoke":
        return (96,), (1.75,), config.sampling.cadences
    if phase == "audit":
        if crop_size is None or expansion is None:
            raise ValueError("audit phase requires --crop-size and --expansion selected by E2")
        return (crop_size,), (expansion,), config.sampling.cadences
    return config.roi.crop_sizes, config.roi.expansion_factors, config.sampling.cadences


def _select_review_ids(
    samples: list[ClipSample],
    cadences: tuple[int, ...],
    crop_sizes: tuple[int, ...],
    expansions: tuple[float, ...],
    frames_per_clip: int,
    seed: int,
    limit: int | None,
) -> set[str]:
    groups: dict[tuple[int, int, float], list[str]] = {}
    for cadence in cadences:
        for size in crop_sizes:
            for expansion in expansions:
                ids: list[str] = []
                for sample in samples:
                    for frame_index in select_frame_indices(
                        sample.onset, sample.release, cadence, frames_per_clip
                    ):
                        for hand in ("left", "right"):
                            ids.append(
                                _blind_id(
                                    seed,
                                    (
                                        sample.clip_id,
                                        frame_index,
                                        hand,
                                        cadence,
                                        size,
                                        expansion,
                                    ),
                                )
                            )
                groups[(cadence, size, expansion)] = ids

    rng = random.Random(seed)
    for ids in groups.values():
        rng.shuffle(ids)
    selected: set[str] = set()
    keys = sorted(groups)
    while keys and (limit is None or len(selected) < limit):
        remaining: list[tuple[int, int, float]] = []
        for key in keys:
            if groups[key] and (limit is None or len(selected) < limit):
                selected.add(groups[key].pop())
            if groups[key]:
                remaining.append(key)
        keys = remaining
    return selected


def _read_frames(video_path: Path, wanted: set[int]) -> tuple[dict[int, np.ndarray], int, int]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise OSError(f"cannot open video: {video_path}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frames: dict[int, np.ndarray] = {}
    frame_index = 0
    try:
        while wanted - frames.keys():
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index in wanted:
                frames[frame_index] = frame
            frame_index += 1
    finally:
        cap.release()
    missing = sorted(wanted - frames.keys())
    if missing:
        raise ValueError(f"video ended before requested frames: {missing[:5]}")
    return frames, width, height


def _blind_id(seed: int, fields: tuple[object, ...]) -> str:
    payload = "|".join(str(value) for value in (seed, *fields))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _source_code_hash() -> str:
    digest = hashlib.sha256()
    source_root = Path(__file__).resolve().parent
    for name in ("audit.py", "config.py", "roi.py", "run.py", "sampling.py"):
        digest.update(name.encode("utf-8"))
        digest.update((source_root / name).read_bytes())
    return digest.hexdigest()


def _review_panel(
    frame_bgr: np.ndarray,
    crop_bgr: np.ndarray | None,
    crop_size: int,
    full_width: int,
    hand: str,
) -> np.ndarray:
    height, width = frame_bgr.shape[:2]
    full_height = max(1, round(height * full_width / width))
    full = cv2.resize(frame_bgr, (full_width, full_height), interpolation=cv2.INTER_AREA)
    crop_panel = (
        crop_bgr if crop_bgr is not None else np.zeros((crop_size, crop_size, 3), dtype=np.uint8)
    )
    target_height = full_height
    target_width = max(1, round(crop_panel.shape[1] * target_height / crop_panel.shape[0]))
    crop_panel = cv2.resize(
        crop_panel,
        (target_width, target_height),
        interpolation=cv2.INTER_NEAREST,
    )
    cv2.putText(
        crop_panel,
        hand,
        (6, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return np.concatenate([full, crop_panel], axis=1)


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def _sample_manifest_rows(samples: list[ClipSample]) -> list[dict[str, Any]]:
    return [
        {
            "clip_id": sample.clip_id,
            "split": sample.split,
            "participant_id": sample.participant_id,
            "gloss": sample.gloss,
            "video_file": sample.video_file,
            "onset": sample.onset,
            "release": sample.release,
            "hand_coverage": sample.hand_coverage,
            "coverage_bin": sample.coverage_bin,
        }
        for sample in samples
    ]


def run(
    phase: str,
    config_path: Path,
    run_id: str,
    crop_size: int | None,
    expansion: float | None,
) -> Path:
    config = load_config(config_path)
    count, frames_per_clip = _phase_count(config, phase)
    crop_sizes, expansions, cadences = _phase_candidates(config, phase, crop_size, expansion)
    run_dir = config.output_root / run_id
    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    if phase == "smoke":
        candidates = select_clips(config, config.sampling.smoke_candidate_pool, config.seed)
        samples = [max(candidates, key=lambda sample: sample.hand_coverage)]
    else:
        samples = select_clips(config, count, config.seed)
    review_limit = None if phase == "smoke" else config.sampling.audit_max_items
    review_ids = _select_review_ids(
        samples,
        cadences,
        crop_sizes,
        expansions,
        frames_per_clip,
        config.seed,
        review_limit,
    )
    _write_csv(
        run_dir / "sample_manifest.csv",
        (
            "clip_id",
            "split",
            "participant_id",
            "gloss",
            "video_file",
            "onset",
            "release",
            "hand_coverage",
            "coverage_bin",
        ),
        _sample_manifest_rows(samples),
    )
    with (run_dir / "run_config.json").open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "phase": phase,
                "run_id": run_id,
                "experiment_version": config.experiment_version,
                "config_hash": config.config_hash,
                "source_code_hash": _source_code_hash(),
                "seed": config.seed,
                "crop_sizes": crop_sizes,
                "expansions": expansions,
                "cadences": cadences,
                "source_config": str(config_path.resolve()),
            },
            fh,
            indent=2,
        )

    index_rows: list[dict[str, Any]] = []
    for sample_index, sample in enumerate(samples, start=1):
        clip = ClipLandmarks.load(config.landmarks_root / sample.split / f"{sample.clip_id}.npz")
        frame_indices_by_cadence = {
            cadence: select_frame_indices(sample.onset, sample.release, cadence, frames_per_clip)
            for cadence in cadences
        }
        wanted = {value for values in frame_indices_by_cadence.values() for value in values}
        frames, width, height = _read_frames(config.videos_dir / sample.video_file, wanted)
        if clip.timestamps_ms.shape[0] <= max(wanted):
            raise ValueError(f"landmark/video frame mismatch for {sample.clip_id}")

        for expansion_value in expansions:
            for cadence, frame_indices in frame_indices_by_cadence.items():
                observation_mask = np.zeros(clip.timestamps_ms.shape, dtype=bool)
                observation_mask[::cadence] = True
                rois = causal_roi_sequence(
                    clip.hands_image,
                    clip.hand_score,
                    clip.timestamps_ms,
                    width,
                    height,
                    expansion_value,
                    config.roi,
                    observation_mask,
                )
                for frame_index in frame_indices:
                    frame = frames[frame_index]
                    for hand_index, hand in enumerate(("left", "right")):
                        observation = rois[frame_index][hand_index]
                        for size in crop_sizes:
                            crop = None
                            padding_fraction = 1.0
                            sharpness = 0.0
                            if observation.box_xyxy is not None:
                                crop, padding_fraction = extract_square_crop(
                                    frame,
                                    observation.box_xyxy,
                                    size,
                                    config.roi.pad_value_rgb,
                                )
                                sharpness = sharpness_variance(crop)
                            crop_id = _blind_id(
                                config.seed,
                                (
                                    sample.clip_id,
                                    frame_index,
                                    hand,
                                    cadence,
                                    size,
                                    expansion_value,
                                ),
                            )
                            crop_path = run_dir / "crops" / f"{crop_id}.jpg"
                            panel_path = run_dir / "review_panels" / f"{crop_id}.jpg"
                            if crop_id in review_ids:
                                crop_path.parent.mkdir(exist_ok=True)
                                panel_path.parent.mkdir(exist_ok=True)
                                if crop is not None:
                                    cv2.imwrite(
                                        str(crop_path),
                                        crop,
                                        [cv2.IMWRITE_JPEG_QUALITY, config.audit.jpeg_quality],
                                    )
                                panel = _review_panel(
                                    frame,
                                    crop,
                                    size,
                                    config.audit.panel_full_frame_width,
                                    hand.upper(),
                                )
                                cv2.imwrite(
                                    str(panel_path),
                                    panel,
                                    [cv2.IMWRITE_JPEG_QUALITY, config.audit.jpeg_quality],
                                )
                            box = observation.box_xyxy or ("", "", "", "")
                            index_rows.append(
                                {
                                    "crop_id": crop_id,
                                    "clip_id": sample.clip_id,
                                    "split": sample.split,
                                    "participant_id": sample.participant_id,
                                    "gloss": sample.gloss,
                                    "video_file": sample.video_file,
                                    "frame_index": frame_index,
                                    "timestamp_ms": int(clip.timestamps_ms[frame_index]),
                                    "hand": hand,
                                    "cadence": cadence,
                                    "crop_size": size,
                                    "expansion": expansion_value,
                                    "roi_source": observation.source,
                                    "roi_age_ms": observation.age_ms,
                                    "box_x1": box[0],
                                    "box_y1": box[1],
                                    "box_x2": box[2],
                                    "box_y2": box[3],
                                    "padding_fraction": round(padding_fraction, 6),
                                    "sharpness": round(sharpness, 4),
                                    "panel_path": str(panel_path) if crop_id in review_ids else "",
                                    "crop_path": (
                                        str(crop_path)
                                        if crop is not None and crop_id in review_ids
                                        else ""
                                    ),
                                }
                            )
        print(f"[crops/e2] {sample_index}/{len(samples)} {sample.clip_id}")

    _write_csv(run_dir / "internal_index.csv", INDEX_FIELDS, index_rows)
    audit_rows = [row for row in index_rows if row["crop_id"] in review_ids]
    random.Random(config.seed).shuffle(audit_rows)

    audit_fields = ("crop_id", "panel_path", "visible_hand", "usable", "failure_reason", "notes")
    _write_csv(
        run_dir / "audit_template.csv",
        audit_fields,
        [{"crop_id": row["crop_id"], "panel_path": row["panel_path"]} for row in audit_rows],
    )
    summary = {
        "clips": len(samples),
        "crop_records": len(index_rows),
        "audit_rows": len(audit_rows),
        "direct": sum(row["roi_source"] == "direct" for row in index_rows),
        "held": sum(row["roi_source"] == "held" for row in index_rows),
        "missing": sum(row["roi_source"] == "missing" for row in index_rows),
    }
    with (run_dir / "generation_summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"[crops/e2] complete -> {run_dir}")
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="AppHear E2 RGB crop-quality experiment")
    parser.add_argument("--phase", choices=["smoke", "engineering", "audit"], default="smoke")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--crop-size", type=int, default=None)
    parser.add_argument("--expansion", type=float, default=None)
    args = parser.parse_args()
    run_id = args.run_id or f"{args.phase}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%SZ')}"
    try:
        run(args.phase, args.config, run_id, args.crop_size, args.expansion)
    except (FileExistsError, OSError, ValueError) as err:
        print(f"[crops/e2] ERROR: {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
