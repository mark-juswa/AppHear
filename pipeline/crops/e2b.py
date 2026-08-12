"""Generate paired E2b control and pose-recovery hand-crop panels."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml

from pipeline.extract.schema import ClipLandmarks, ClipSidecar

from .config import RoiConfig
from .pose_roi import (
    PoseRecoveryConfig,
    causal_pose_recovery_sequence,
    hand_to_shoulder_ratios,
)
from .roi import causal_roi_sequence, extract_square_crop, sharpness_variance
from .run import _blind_id, _read_frames, _review_panel, _write_csv

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "crops_e2b.yaml"
INDEX_FIELDS = (
    "crop_id",
    "base_id",
    "strategy",
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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _source_hash() -> str:
    digest = hashlib.sha256()
    for name in ("config.py", "e2b.py", "pose_roi.py", "roi.py", "run.py"):
        digest.update(name.encode("utf-8"))
        digest.update((Path(__file__).parent / name).read_bytes())
    return digest.hexdigest()


def _base_key(row: dict[str, str]) -> tuple[str, int, str, int]:
    return row["clip_id"], int(row["frame_index"]), row["hand"], int(row["cadence"])


def _known_visible_candidates(
    audit_rows: list[dict[str, str]],
    index_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    metadata = {row["crop_id"]: row for row in index_rows}
    visibility: dict[tuple[str, int, str, int], list[bool]] = defaultdict(list)
    representative: dict[tuple[str, int, str, int], dict[str, str]] = {}
    for audit in audit_rows:
        meta = metadata.get(audit["crop_id"])
        if meta is None:
            raise ValueError(f"E2 audit crop absent from index: {audit['crop_id']}")
        value = audit.get("visible_hand", "").strip().lower()
        if value not in {"yes", "no"}:
            continue
        key = _base_key(meta)
        visibility[key].append(value == "yes")
        representative[key] = meta
    candidates = []
    for key, labels in visibility.items():
        if labels and all(labels):
            candidates.append(representative[key])
    if not candidates:
        raise ValueError("E2 audit contains no unanimously known-visible base items")
    return candidates


def _select_paired_items(
    candidates: list[dict[str, str]], count: int, seed: int
) -> list[dict[str, str]]:
    groups: dict[tuple[int, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        availability = "available" if row["roi_source"] != "missing" else "missing"
        groups[(int(row["cadence"]), row["hand"], availability)].append(row)
    rng = random.Random(seed)
    for rows in groups.values():
        rng.shuffle(rows)
    keys = sorted(groups)
    selected: list[dict[str, str]] = []
    while keys and len(selected) < count:
        remaining = []
        for key in keys:
            if groups[key] and len(selected) < count:
                selected.append(groups[key].pop())
            if groups[key]:
                remaining.append(key)
        keys = remaining
    if len(selected) < count:
        raise ValueError(f"requested {count} paired base items, found {len(selected)}")
    rng.shuffle(selected)
    return selected


def _select_smoke_items(
    candidates: list[dict[str, str]], seed: int
) -> list[dict[str, str]]:
    """Select one known-visible item for every cadence/hand combination."""
    groups: dict[tuple[int, str], list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        groups[(int(row["cadence"]), row["hand"])].append(row)
    rng = random.Random(seed)
    selected = []
    strata = (
        (1, "left"),
        (1, "right"),
        (4, "left"),
        (4, "right"),
        (8, "left"),
        (8, "right"),
    )
    for key in strata:
        rows = groups.get(key, [])
        if not rows:
            raise ValueError(f"no known-visible E2 item for smoke stratum {key}")
        rng.shuffle(rows)
        rows.sort(key=lambda row: row["roi_source"] != "missing")
        selected.append(rows[0])
    rng.shuffle(selected)
    return selected

def _fit_fallback_ratio(
    source_run: Path,
    landmarks_root: Path,
    quantile: float,
    min_valid_landmarks: int,
    min_pose_visibility: float,
) -> tuple[float, int]:
    ratios: list[float] = []
    for row in _read_csv(source_run / "sample_manifest.csv"):
        if row["split"] != "train":
            continue
        clip_id = row["clip_id"]
        root = landmarks_root / "train"
        clip = ClipLandmarks.load(root / f"{clip_id}.npz")
        sidecar = ClipSidecar.load(root / f"{clip_id}.json")
        ratios.extend(
            hand_to_shoulder_ratios(
                clip.hands_image,
                clip.hand_score,
                clip.pose_image,
                sidecar.frame_width,
                sidecar.frame_height,
                min_valid_landmarks,
                min_pose_visibility,
            )
        )
    if len(ratios) < 100:
        raise ValueError(f"only {len(ratios)} train observations available for fallback fit")
    return float(np.quantile(np.asarray(ratios), quantile)), len(ratios)


def _roi_config(raw: dict[str, Any]) -> RoiConfig:
    roi = raw["roi"]
    pad_values = tuple(int(v) for v in roi["pad_value_rgb"])
    if len(pad_values) != 3:
        raise ValueError("roi.pad_value_rgb must contain exactly three values")
    return RoiConfig(
        crop_sizes=(int(roi["diagnostic_crop_size"]),),
        expansion_factors=(float(roi["diagnostic_expansion"]),),
        min_valid_landmarks=int(roi["min_valid_landmarks"]),
        min_side_fraction=float(roi["min_side_fraction"]),
        max_side_fraction=float(roi["max_side_fraction"]),
        max_hold_ms=int(roi["control_hold_ms"]),
        pad_value_rgb=(pad_values[0], pad_values[1], pad_values[2]),
    )


def run(config_path: Path, run_id: str, smoke: bool) -> Path:
    with config_path.open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)
    seed = int(raw["seed"])
    source_run = Path(raw["source_e2"]["run_dir"])
    audit_path = source_run / raw["source_e2"]["audit_csv"]
    index_path = source_run / "internal_index.csv"
    for required in (audit_path, index_path, source_run / "sample_manifest.csv"):
        if not required.exists():
            raise FileNotFoundError(f"required E2 artifact missing: {required}")

    output_dir = Path(raw["output"]["root"]) / run_id
    if output_dir.exists():
        raise FileExistsError(f"run directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    roi = _roi_config(raw)
    count = int(
        raw["sampling"]["smoke_base_items"] if smoke else raw["sampling"]["base_items"]
    )
    candidates = _known_visible_candidates(_read_csv(audit_path), _read_csv(index_path))
    selected = (
        _select_smoke_items(candidates, seed)
        if smoke
        else _select_paired_items(candidates, count, seed)
    )
    landmarks_root = Path(raw["dataset"]["landmarks_root"])
    ratio, ratio_count = _fit_fallback_ratio(
        source_run,
        landmarks_root,
        float(raw["roi"]["fallback_size_quantile"]),
        roi.min_valid_landmarks,
        float(raw["roi"]["pose_min_visibility"]),
    )
    ages = tuple(int(value) for value in raw["roi"]["pose_track_max_age_ms"])
    strategies = ("control_hold_100", *(f"pose_track_{age}" for age in ages))
    dataset_root = Path(raw["dataset"]["root"])
    videos_dir = dataset_root / raw["dataset"]["videos_subdir"]
    crop_size = int(raw["roi"]["diagnostic_crop_size"])
    expansion = float(raw["roi"]["diagnostic_expansion"])

    by_clip: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in selected:
        by_clip[row["clip_id"]].append(row)
    index_output: list[dict[str, Any]] = []
    for clip_number, (clip_id, rows) in enumerate(sorted(by_clip.items()), start=1):
        first = rows[0]
        clip = ClipLandmarks.load(landmarks_root / first["split"] / f"{clip_id}.npz")
        wanted = {int(row["frame_index"]) for row in rows}
        frames, width, height = _read_frames(videos_dir / first["video_file"], wanted)
        sequence_by_strategy: dict[tuple[str, int], list[list[Any]]] = {}
        for cadence in {int(row["cadence"]) for row in rows}:
            observation_mask = np.zeros(clip.timestamps_ms.shape, dtype=bool)
            observation_mask[::cadence] = True
            sequence_by_strategy[("control_hold_100", cadence)] = causal_roi_sequence(
                clip.hands_image,
                clip.hand_score,
                clip.timestamps_ms,
                width,
                height,
                expansion,
                roi,
                observation_mask,
            )
            for age in ages:
                strategy = f"pose_track_{age}"
                sequence_by_strategy[(strategy, cadence)] = causal_pose_recovery_sequence(
                    clip.hands_image,
                    clip.hand_score,
                    clip.pose_image,
                    clip.timestamps_ms,
                    width,
                    height,
                    expansion,
                    roi,
                    PoseRecoveryConfig(
                        min_pose_visibility=float(raw["roi"]["pose_min_visibility"]),
                        fallback_side_ratio=ratio,
                        max_track_age_ms=age,
                    ),
                    observation_mask,
                )

        for base in rows:
            frame_index = int(base["frame_index"])
            cadence = int(base["cadence"])
            hand = base["hand"]
            hand_index = 0 if hand == "left" else 1
            base_id = _blind_id(seed, (clip_id, frame_index, hand, cadence))
            frame = frames[frame_index]
            for strategy in strategies:
                observation = sequence_by_strategy[(strategy, cadence)][frame_index][hand_index]
                crop = None
                padding = 1.0
                sharpness = 0.0
                if observation.box_xyxy is not None:
                    crop, padding = extract_square_crop(
                        frame, observation.box_xyxy, crop_size, roi.pad_value_rgb
                    )
                    sharpness = sharpness_variance(crop)
                crop_id = _blind_id(seed, (base_id, strategy))
                crop_path = output_dir / "crops" / f"{crop_id}.jpg"
                panel_path = output_dir / "review_panels" / f"{crop_id}.jpg"
                crop_path.parent.mkdir(exist_ok=True)
                panel_path.parent.mkdir(exist_ok=True)
                if crop is not None:
                    cv2.imwrite(
                        str(crop_path),
                        crop,
                        [cv2.IMWRITE_JPEG_QUALITY, int(raw["audit"]["jpeg_quality"])],
                    )
                panel = _review_panel(
                    frame,
                    crop,
                    crop_size,
                    int(raw["audit"]["panel_full_frame_width"]),
                    hand.upper(),
                )
                cv2.imwrite(
                    str(panel_path),
                    panel,
                    [cv2.IMWRITE_JPEG_QUALITY, int(raw["audit"]["jpeg_quality"])],
                )
                box = observation.box_xyxy or ("", "", "", "")
                index_output.append(
                    {
                        "crop_id": crop_id,
                        "base_id": base_id,
                        "strategy": strategy,
                        "clip_id": clip_id,
                        "split": base["split"],
                        "participant_id": base["participant_id"],
                        "gloss": base["gloss"],
                        "video_file": base["video_file"],
                        "frame_index": frame_index,
                        "timestamp_ms": int(clip.timestamps_ms[frame_index]),
                        "hand": hand,
                        "cadence": cadence,
                        "crop_size": crop_size,
                        "expansion": expansion,
                        "roi_source": observation.source,
                        "roi_age_ms": observation.age_ms,
                        "box_x1": box[0],
                        "box_y1": box[1],
                        "box_x2": box[2],
                        "box_y2": box[3],
                        "padding_fraction": round(padding, 6),
                        "sharpness": round(sharpness, 4),
                        "panel_path": str(panel_path),
                        "crop_path": str(crop_path) if crop is not None else "",
                    }
                )
        print(f"[crops/e2b] {clip_number}/{len(by_clip)} {clip_id}")

    _write_csv(output_dir / "internal_index.csv", INDEX_FIELDS, index_output)
    audit_rows = [
        {"crop_id": row["crop_id"], "panel_path": row["panel_path"]}
        for row in index_output
    ]
    random.Random(seed).shuffle(audit_rows)
    _write_csv(
        output_dir / "audit_template.csv",
        ("crop_id", "panel_path", "visible_hand", "usable", "failure_reason", "notes"),
        audit_rows,
    )
    config_hash = hashlib.sha256(
        json.dumps(raw, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    with (output_dir / "run_config.json").open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "run_id": run_id,
                "smoke": smoke,
                "experiment_version": raw["experiment_version"],
                "seed": seed,
                "config_hash": config_hash,
                "source_code_hash": _source_hash(),
                "source_e2_run": str(source_run),
                "source_e2_audit": str(audit_path),
                "base_items": len(selected),
                "strategies": strategies,
                "fallback_side_ratio": ratio,
                "fallback_fit_observations": ratio_count,
                "fallback_fit_split": "train",
                "created_utc": datetime.now(UTC).isoformat(),
            },
            fh,
            indent=2,
        )
    print(f"[crops/e2b] complete -> {output_dir}")
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="AppHear E2b paired ROI-recovery experiment")
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
        print(f"[crops/e2b] ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
