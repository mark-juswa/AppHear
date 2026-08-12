"""Generate a blinded, side-independent E2e-A hand-detection gold audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2

from pipeline.crops.config import load_config
from pipeline.crops.sampling import select_clips
from pipeline.tracking.e2e_pilot import HandPoseRunner, _annotate, _fit, _frame

INDEX_FIELDS = (
    "sample_id",
    "clip_id",
    "video_file",
    "participant_id",
    "split",
    "gloss",
    "frame_index",
    "timestamp_ms",
    "sampling_cadence",
    "sampling_target_hand",
    "sampling_target_detected",
    "sampling_raw_detected_hands",
    "image_width",
    "image_height",
    "center_image_path",
    "context_panel_path",
    "diagnostic_panel_path",
    "detected_hands_json",
    "pose_wrists_json",
)

REVIEW_FIELDS = (
    "sample_id",
    "review_status",
    "source_mirrored",
    "mirror_evidence",
    "visible_hand_count",
    "gold_hands_json",
    "motion_blur",
    "occlusion",
    "near_face",
    "edge_clipped",
    "partial_visibility",
    "notes",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def select_gold_samples(
    rows: list[dict[str, str]],
    count: int,
    seed: int,
    max_per_clip: int = 1,
) -> list[dict[str, str]]:
    """Sample independently of detector success while balancing available cadences."""

    if count <= 0:
        raise ValueError("count must be positive")
    eligible = [
        row for row in rows if row["label"] == "positive" and row["candidate_id"] == "image_d50_p50"
    ]
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for row in eligible:
        unique.setdefault((row["clip_id"], row["frame_index"]), row)

    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in unique.values():
        grouped[int(row["cadence"])].append(row)
    if not grouped:
        raise ValueError("no eligible positive control frames")

    rng = random.Random(seed)
    for candidates in grouped.values():
        rng.shuffle(candidates)

    selected: list[dict[str, str]] = []
    clip_counts: dict[str, int] = defaultdict(int)
    cadences = sorted(grouped)
    while len(selected) < count:
        progress = False
        for cadence in cadences:
            candidates = grouped[cadence]
            while candidates:
                candidate = candidates.pop()
                if clip_counts[candidate["clip_id"]] >= max_per_clip:
                    continue
                selected.append(candidate)
                clip_counts[candidate["clip_id"]] += 1
                progress = True
                break
            if len(selected) == count:
                break
        if not progress:
            raise ValueError(
                f"only {len(selected)} unique frames satisfy max_per_clip={max_per_clip}"
            )
    return selected


def span_frame(onset: int, release: int, fraction: float) -> int:
    if onset < 0 or release < onset:
        raise ValueError(f"invalid sign span: {onset}..{release}")
    if not 0.0 <= fraction <= 1.0:
        raise ValueError(f"invalid span fraction: {fraction}")
    return round(onset + fraction * (release - onset))


def select_balanced_clip_frames(
    config_path: Path,
    count: int,
    seed: int,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Select one detector-independent in-sign frame from each balanced unique clip."""

    config = load_config(config_path)
    clips = select_clips(config, count, seed)
    fractions = (0.25, 0.50, 0.75)
    rows = []
    phase_counts: dict[str, int] = defaultdict(int)
    for index, clip in enumerate(clips):
        fraction = fractions[index % len(fractions)]
        phase = f"span_q{round(fraction * 100):02d}"
        phase_counts[phase] += 1
        rows.append(
            {
                "clip_id": clip.clip_id,
                "video_file": clip.video_file,
                "participant_id": clip.participant_id,
                "split": clip.split,
                "gloss": clip.gloss,
                "frame_index": str(span_frame(clip.onset, clip.release, fraction)),
                "timestamp_ms": "",
                "cadence": phase,
                "hand": "",
                "target_detected": "",
                "raw_detected_hands": "",
            }
        )
    source = {
        "pool": "asl_citizen_balanced_unique_clips_v1",
        "config_path": str(config_path.resolve()),
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "unique_clips": len({row["clip_id"] for row in rows}),
        "unique_signers": len({row["participant_id"] for row in rows}),
        "phase_counts": dict(sorted(phase_counts.items())),
        "selection": (
            "Signer/coverage-balanced train+val clips; one frame per clip at balanced "
            "25/50/75% sign-span positions; no selected-frame MediaPipe result consulted."
        ),
    }
    return rows, source


def _raw_panel(context_frames: list[Any], sample_id: str) -> Any:
    strip = cv2.hconcat([_fit(frame) for frame in context_frames])
    cv2.putText(
        strip,
        f"{sample_id} | chronological context | center frame is third",
        (10, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return strip


def run(
    e2d_index: Path,
    video_root: Path,
    hand_task: Path,
    pose_task: Path,
    output_dir: Path,
    count: int,
    seed: int,
    max_per_clip: int,
    selected_override: list[dict[str, str]] | None = None,
    source_provenance: dict[str, Any] | None = None,
) -> Path:
    selected = selected_override or select_gold_samples(
        _read_csv(e2d_index), count=count, seed=seed, max_per_clip=max_per_clip
    )
    if len(selected) != count:
        raise ValueError(f"selected {len(selected)} frames, expected {count}")
    output_dir.mkdir(parents=True, exist_ok=False)
    images_dir = output_dir / "center_images"
    context_dir = output_dir / "context_panels"
    diagnostics_dir = output_dir / "diagnostic_panels_do_not_review"
    images_dir.mkdir()
    context_dir.mkdir()
    diagnostics_dir.mkdir()

    index_rows: list[dict[str, Any]] = []
    with HandPoseRunner(hand_task, pose_task) as runner:
        for number, item in enumerate(selected, start=1):
            video_path = video_root / item["video_file"]
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise FileNotFoundError(video_path)
            center = int(item["frame_index"])
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            timestamp_ms = item.get("timestamp_ms", "")
            if not timestamp_ms:
                if fps <= 0:
                    raise ValueError(f"invalid FPS for {video_path}")
                timestamp_ms = str(round(center * 1000.0 / fps))
            indices = [
                max(0, min(frame_count - 1, center + offset)) for offset in (-8, -4, 0, 4, 8)
            ]
            frames = [_frame(cap, index) for index in indices]
            cap.release()
            hands, wrists = runner.detect(frames[2])
            sample_id = f"g{number:03d}"

            image_path = images_dir / f"{sample_id}.png"
            context_path = context_dir / f"{sample_id}.jpg"
            diagnostic_path = diagnostics_dir / f"{sample_id}.jpg"
            if not cv2.imwrite(str(image_path), frames[2]):
                raise OSError(f"failed to write image: {image_path}")
            if not cv2.imwrite(str(context_path), _raw_panel(frames, sample_id)):
                raise OSError(f"failed to write panel: {context_path}")
            annotated = frames.copy()
            annotated[2] = _annotate(annotated[2], hands, wrists)
            if not cv2.imwrite(str(diagnostic_path), _raw_panel(annotated, sample_id)):
                raise OSError(f"failed to write diagnostic: {diagnostic_path}")

            height, width = frames[2].shape[:2]
            index_rows.append(
                {
                    "sample_id": sample_id,
                    "clip_id": item["clip_id"],
                    "video_file": item["video_file"],
                    "participant_id": item["participant_id"],
                    "split": item["split"],
                    "gloss": item["gloss"],
                    "frame_index": center,
                    "timestamp_ms": timestamp_ms,
                    "sampling_cadence": item["cadence"],
                    "sampling_target_hand": item.get("hand", ""),
                    "sampling_target_detected": item.get("target_detected", ""),
                    "sampling_raw_detected_hands": item.get("raw_detected_hands", ""),
                    "image_width": width,
                    "image_height": height,
                    "center_image_path": str(image_path.resolve()),
                    "context_panel_path": str(context_path.resolve()),
                    "diagnostic_panel_path": str(diagnostic_path.resolve()),
                    "detected_hands_json": json.dumps(hands, separators=(",", ":")),
                    "pose_wrists_json": json.dumps(wrists, separators=(",", ":")),
                }
            )
            print(f"[tracking/e2e-gold] {number}/{count} {sample_id}")

    _write_csv(output_dir / "internal_index.csv", INDEX_FIELDS, index_rows)
    _write_csv(
        output_dir / "gold_review.csv",
        REVIEW_FIELDS,
        [{"sample_id": row["sample_id"]} for row in index_rows],
    )
    provenance = {
        "experiment": "e2e.all_hand_box_gold.v1",
        "items": len(index_rows),
        "seed": seed,
        "max_per_clip": max_per_clip,
        "source": source_provenance
        or {
            "pool": "e2d_positive_controls_v1",
            "selection": (
                "Positive E2 controls balanced by cadence and sampled without conditioning "
                "on the current candidate's MediaPipe success."
            ),
            "e2d_index": str(e2d_index.resolve()),
            "e2d_index_sha256": hashlib.sha256(e2d_index.read_bytes()).hexdigest(),
        },
        "hand_task_sha256": hashlib.sha256(hand_task.read_bytes()).hexdigest(),
        "pose_task_sha256": hashlib.sha256(pose_task.read_bytes()).hexdigest(),
        "review_warning": (
            "Review center_images/context_panels only. Diagnostic panels reveal predictions."
        ),
    }
    (output_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return output_dir


def enrich_existing(
    run_dir: Path,
    hand_task: Path,
    pose_task: Path,
) -> Path:
    """Add full landmark instances to an existing reviewed run without changing gold."""

    index_path = run_dir / "internal_index.csv"
    provenance_path = run_dir / "provenance.json"
    rows = _read_csv(index_path)
    before_bytes = index_path.read_bytes()
    backup = run_dir / "internal_index.pre_landmark_enrichment.csv"
    if not backup.exists():
        shutil.copy2(index_path, backup)

    with HandPoseRunner(hand_task, pose_task) as runner:
        for number, row in enumerate(rows, start=1):
            image = cv2.imread(row["center_image_path"], cv2.IMREAD_COLOR)
            if image is None:
                raise FileNotFoundError(row["center_image_path"])
            hands, wrists = runner.detect(image)
            row["detected_hands_json"] = json.dumps(hands, separators=(",", ":"))
            row["pose_wrists_json"] = json.dumps(wrists, separators=(",", ":"))
            print(f"[tracking/e2e-gold] enrich {number}/{len(rows)} {row['sample_id']}")

    temporary = index_path.with_suffix(".csv.tmp")
    _write_csv(temporary, INDEX_FIELDS, rows)
    temporary.replace(index_path)
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["prediction_schema"] = "mediapipe_hand_21_landmarks_v1"
    provenance["pre_enrichment_index_sha256"] = hashlib.sha256(before_bytes).hexdigest()
    provenance["enriched_index_sha256"] = hashlib.sha256(index_path.read_bytes()).hexdigest()
    provenance["enrichment_source"] = "saved center_images; gold_review.csv unchanged"
    provenance_path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or enrich E2e all-hand gold audit")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--enrich-run-dir", type=Path)
    parser.add_argument("--count", type=int, default=150)
    parser.add_argument("--seed", type=int, default=260726)
    parser.add_argument("--max-per-clip", type=int, default=1)
    parser.add_argument(
        "--source-pool",
        choices=("balanced-clips", "e2d"),
        default="balanced-clips",
    )
    parser.add_argument(
        "--clip-config",
        type=Path,
        default=Path("pipeline/config/crops_e2.yaml"),
    )
    parser.add_argument(
        "--e2d-index",
        type=Path,
        default=Path(
            "F:/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/"
            "e2d_detector_operating_point_v0/engineering_e2d_01/item_index.csv"
        ),
    )
    parser.add_argument(
        "--video-root",
        type=Path,
        default=Path("F:/ASL DATASET/ASL CITIZEN/ASL_Citizen/videos"),
    )
    parser.add_argument(
        "--hand-task", type=Path, default=Path("assets/mediapipe/hand_landmarker.task")
    )
    parser.add_argument(
        "--pose-task",
        type=Path,
        default=Path("assets/mediapipe/pose_landmarker_lite.task"),
    )
    args = parser.parse_args()
    try:
        if args.enrich_run_dir is not None:
            result = enrich_existing(args.enrich_run_dir, args.hand_task, args.pose_task)
        else:
            assert args.output is not None
            selected_override = None
            source_provenance = None
            if args.source_pool == "balanced-clips":
                if args.max_per_clip != 1:
                    raise ValueError("balanced-clips requires --max-per-clip 1")
                selected_override, source_provenance = select_balanced_clip_frames(
                    args.clip_config, args.count, args.seed
                )
            result = run(
                args.e2d_index,
                args.video_root,
                args.hand_task,
                args.pose_task,
                args.output,
                args.count,
                args.seed,
                args.max_per_clip,
                selected_override,
                source_provenance,
            )
    except (FileExistsError, FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[tracking/e2e-gold] ERROR: {error}")
        return 2
    print(f"[tracking/e2e-gold] complete -> {result.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
