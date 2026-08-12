"""Prepare and validate the E2e-C0 N0/P1 capture sets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2

from pipeline.tracking.e2e_gold import INDEX_FIELDS, REVIEW_FIELDS
from pipeline.tracking.e2e_gold_review import (
    ReviewApp,
    completion_error,
    load_run,
    parse_boxes,
    validate_run,
)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
CAPTURE_KINDS = {"n0", "p1"}
CAMERA_FACINGS = {"front", "back"}
CAPTURE_FIELDS = (
    "clip_id",
    "kind",
    "video_path",
    "participant_id",
    "device_id",
    "environment_id",
    "camera_facing",
    "duration_seconds",
    "native_fps",
    "frame_count",
    "sha256",
)
FINAL_FIELDS = (
    "sample_id",
    "kind",
    "clip_id",
    "participant_id",
    "device_id",
    "environment_id",
    "camera_facing",
    "timestamp_ms",
    "frame_index",
    "center_image_path",
    "visible_hand_count",
    "gold_hands_json",
    "eligible",
    "exclusion_reason",
)


@dataclass(frozen=True)
class CaptureClip:
    path: Path
    kind: str
    participant_id: str
    device_id: str
    environment_id: str
    camera_facing: str
    fps: float
    frame_count: int
    duration_seconds: float
    sha256: str

    @property
    def clip_id(self) -> str:
        return self.path.stem


@dataclass(frozen=True)
class FrameRequest:
    clip: CaptureClip
    timestamp_seconds: float
    frame_index: int


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_capture_path(raw_root: Path, video: Path, kind: str) -> tuple[str, str, str, str]:
    relative = video.relative_to(raw_root / kind)
    if len(relative.parts) != 5:
        raise ValueError(
            f"{video}: expected {kind}/<person>/<device>/<environment>/<front-or-back>/<video>"
        )
    participant, device, environment, camera, _filename = relative.parts
    if camera.lower() not in CAMERA_FACINGS:
        raise ValueError(f"{video}: camera folder must be front or back")
    if any(not value.strip() for value in (participant, device, environment)):
        raise ValueError(f"{video}: capture metadata folders cannot be empty")
    return participant, device, environment, camera.lower()


def discover_clips(raw_root: Path, kind: str, hash_videos: bool = True) -> list[CaptureClip]:
    if kind not in CAPTURE_KINDS:
        raise ValueError(f"kind must be one of {sorted(CAPTURE_KINDS)}")
    kind_root = raw_root / kind
    if not kind_root.is_dir():
        raise FileNotFoundError(f"missing capture folder: {kind_root}")
    videos = sorted(
        path
        for path in kind_root.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )
    if not videos:
        raise ValueError(f"no videos found under {kind_root}")

    clips = []
    clip_ids: set[str] = set()
    for path in videos:
        participant, device, environment, camera = _parse_capture_path(raw_root, path, kind)
        if path.stem in clip_ids:
            raise ValueError(f"duplicate video stem/clip_id: {path.stem}")
        clip_ids.add(path.stem)
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            raise OSError(f"cannot open video: {path}")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        capture.release()
        if not math.isfinite(fps) or fps <= 0 or frame_count <= 0:
            raise ValueError(f"invalid video metadata: {path} fps={fps} frames={frame_count}")
        duration = frame_count / fps
        clips.append(
            CaptureClip(
                path=path.resolve(),
                kind=kind,
                participant_id=participant,
                device_id=device,
                environment_id=environment,
                camera_facing=camera,
                fps=fps,
                frame_count=frame_count,
                duration_seconds=duration,
                sha256=_sha256(path) if hash_videos else "",
            )
        )
    return clips


def capture_diversity(clips: list[CaptureClip]) -> dict[str, Any]:
    return {
        "clips": len(clips),
        "duration_seconds": sum(clip.duration_seconds for clip in clips),
        "participants": sorted({clip.participant_id for clip in clips}),
        "devices": sorted({clip.device_id for clip in clips}),
        "environments": sorted({clip.environment_id for clip in clips}),
        "camera_facings": sorted({clip.camera_facing for clip in clips}),
    }


def _clip_requests(clip: CaptureClip, sample_fps: float) -> list[FrameRequest]:
    interval = 1.0 / sample_fps
    timestamps = []
    timestamp = interval / 2.0
    while timestamp < clip.duration_seconds:
        frame_index = min(round(timestamp * clip.fps), clip.frame_count - 1)
        timestamps.append(FrameRequest(clip, timestamp, frame_index))
        timestamp += interval
    return timestamps


def select_requests(
    clips: list[CaptureClip],
    sample_fps: float,
    max_total: int,
    seed: int,
) -> list[FrameRequest]:
    if sample_fps <= 0:
        raise ValueError("sample_fps must be positive")
    if max_total <= 0:
        raise ValueError("max_total must be positive")
    grouped = {clip.clip_id: _clip_requests(clip, sample_fps) for clip in clips}
    if any(not requests for requests in grouped.values()):
        empty = [clip_id for clip_id, requests in grouped.items() if not requests]
        raise ValueError(f"videos too short to sample: {empty}")

    rng = random.Random(seed)
    for requests in grouped.values():
        rng.shuffle(requests)
    clip_ids = sorted(grouped)
    rng.shuffle(clip_ids)
    selected: list[FrameRequest] = []
    while len(selected) < max_total:
        progressed = False
        for clip_id in clip_ids:
            if grouped[clip_id]:
                selected.append(grouped[clip_id].pop())
                progressed = True
                if len(selected) == max_total:
                    break
        if not progressed:
            break
    if len(selected) < max_total:
        raise ValueError(f"only {len(selected)} frames available, requested {max_total}")
    return sorted(
        selected,
        key=lambda request: (request.clip.clip_id, request.timestamp_seconds),
    )


def _read_frame(capture: cv2.VideoCapture, frame_index: int, video: Path) -> Any:
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = capture.read()
    if not ok or frame is None:
        raise OSError(f"cannot decode frame {frame_index} from {video}")
    return frame


def _fit_panel(frame: Any, width: int = 240, height: int = 180) -> Any:
    scale = min(width / frame.shape[1], height / frame.shape[0])
    resized = cv2.resize(
        frame,
        (round(frame.shape[1] * scale), round(frame.shape[0] * scale)),
        interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_NEAREST,
    )
    canvas = cv2.copyMakeBorder(
        resized,
        (height - resized.shape[0]) // 2,
        height - resized.shape[0] - (height - resized.shape[0]) // 2,
        (width - resized.shape[1]) // 2,
        width - resized.shape[1] - (width - resized.shape[1]) // 2,
        cv2.BORDER_CONSTANT,
        value=(24, 24, 24),
    )
    return canvas


def _write_sample(
    request: FrameRequest,
    sample_id: str,
    center_dir: Path,
    panel_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    capture = cv2.VideoCapture(str(request.clip.path))
    if not capture.isOpened():
        raise OSError(f"cannot open video: {request.clip.path}")
    offsets = (-2, -1, 0, 1, 2)
    context = [
        _read_frame(
            capture,
            min(max(request.frame_index + offset, 0), request.clip.frame_count - 1),
            request.clip.path,
        )
        for offset in offsets
    ]
    capture.release()
    center = context[2]
    center_path = center_dir / f"{sample_id}.png"
    panel_path = panel_dir / f"{sample_id}.jpg"
    if not cv2.imwrite(str(center_path), center):
        raise OSError(f"cannot write {center_path}")
    panel = cv2.hconcat([_fit_panel(frame) for frame in context])
    cv2.putText(
        panel,
        f"{sample_id} | chronological | label center frame",
        (12, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    if not cv2.imwrite(str(panel_path), panel):
        raise OSError(f"cannot write {panel_path}")

    index = {field: "" for field in INDEX_FIELDS}
    index.update(
        {
            "sample_id": sample_id,
            "clip_id": request.clip.clip_id,
            "video_file": request.clip.path.name,
            "participant_id": request.clip.participant_id,
            "split": "unassigned",
            "gloss": request.clip.kind.upper(),
            "frame_index": str(request.frame_index),
            "timestamp_ms": str(round(request.timestamp_seconds * 1000)),
            "sampling_cadence": "1fps",
            "image_width": str(center.shape[1]),
            "image_height": str(center.shape[0]),
            "center_image_path": str(center_path.resolve()),
            "context_panel_path": str(panel_path.resolve()),
            "diagnostic_panel_path": "",
            "detected_hands_json": "[]",
            "pose_wrists_json": "{}",
        }
    )
    review = {field: "" for field in REVIEW_FIELDS}
    review["sample_id"] = sample_id
    return index, review


def prepare_run(
    raw_root: Path,
    kind: str,
    output: Path,
    max_total: int,
    sample_fps: float,
    seed: int,
    hash_videos: bool = True,
) -> dict[str, Any]:
    clips = discover_clips(raw_root, kind, hash_videos=hash_videos)
    requests = select_requests(clips, sample_fps, max_total, seed)
    output.mkdir(parents=True, exist_ok=False)
    center_dir = output / "center_images"
    panel_dir = output / "context_panels"
    center_dir.mkdir()
    panel_dir.mkdir()

    index_rows = []
    review_rows = []
    for number, request in enumerate(requests, start=1):
        sample_id = f"{kind}_{number:04d}"
        index, review = _write_sample(request, sample_id, center_dir, panel_dir)
        index_rows.append(index)
        review_rows.append(review)
        print(f"[tracking/e2e-c0] {number}/{len(requests)} {request.clip.clip_id}")

    capture_rows = [
        {
            "clip_id": clip.clip_id,
            "kind": clip.kind,
            "video_path": str(clip.path),
            "participant_id": clip.participant_id,
            "device_id": clip.device_id,
            "environment_id": clip.environment_id,
            "camera_facing": clip.camera_facing,
            "duration_seconds": f"{clip.duration_seconds:.3f}",
            "native_fps": f"{clip.fps:.6f}",
            "frame_count": clip.frame_count,
            "sha256": clip.sha256,
        }
        for clip in clips
    ]
    _write_csv(output / "capture_manifest.csv", CAPTURE_FIELDS, capture_rows)
    _write_csv(output / "internal_index.csv", INDEX_FIELDS, index_rows)
    _write_csv(output / "gold_review.csv", REVIEW_FIELDS, review_rows)
    provenance = {
        "experiment": "e2e_c0_capture_v1",
        "kind": kind,
        "raw_root": str(raw_root.resolve()),
        "sample_fps": sample_fps,
        "max_total": max_total,
        "seed": seed,
        "selection": "seeded round-robin across clips, then chronological output",
        "capture_diversity": capture_diversity(clips),
        "source_hashes_recorded": hash_videos,
        "review_command": (
            f"python -m pipeline.tracking.e2e_c0_capture review --run-dir \"{output.resolve()}\""
        ),
        "check_command": (
            f"python -m pipeline.tracking.e2e_c0_capture check --run-dir \"{output.resolve()}\""
        ),
    }
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return provenance


def _capture_lookup(run_dir: Path) -> dict[str, dict[str, str]]:
    with (run_dir / "capture_manifest.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    if not rows or tuple(rows[0]) != CAPTURE_FIELDS:
        raise ValueError("invalid capture_manifest.csv schema")
    return {row["clip_id"]: row for row in rows}


def check_run(run_dir: Path) -> tuple[dict[str, Any], list[str]]:
    reviews, index = load_run(run_dir)
    generic_errors = validate_run(reviews, index)
    provenance = json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))
    kind = str(provenance["kind"])
    captures = _capture_lookup(run_dir)
    rows = []
    counts: defaultdict[str, int] = defaultdict(int)
    for review in reviews:
        sample_id = review["sample_id"]
        metadata = index[sample_id]
        capture = captures[metadata["clip_id"]]
        error = completion_error(review)
        eligible = False
        reason = ""
        if error is not None:
            reason = f"incomplete: {error}"
            counts["incomplete"] += 1
        elif review["review_status"] == "quarantine":
            reason = "quarantined"
            counts["quarantined"] += 1
        else:
            visible = int(review["visible_hand_count"])
            if kind == "n0" and visible == 0:
                eligible = True
                counts["eligible"] += 1
            elif kind == "n0":
                reason = "visible-hand contamination"
                counts["contaminated"] += 1
            elif kind == "p1" and visible > 0:
                eligible = True
                counts["eligible"] += 1
                counts["gold_hands"] += len(parse_boxes(review))
            else:
                reason = "no visible hand"
                counts["no_visible_hand"] += 1
        rows.append(
            {
                "sample_id": sample_id,
                "kind": kind,
                "clip_id": metadata["clip_id"],
                "participant_id": metadata["participant_id"],
                "device_id": capture["device_id"],
                "environment_id": capture["environment_id"],
                "camera_facing": capture["camera_facing"],
                "timestamp_ms": metadata["timestamp_ms"],
                "frame_index": metadata["frame_index"],
                "center_image_path": metadata["center_image_path"],
                "visible_hand_count": review["visible_hand_count"],
                "gold_hands_json": review["gold_hands_json"],
                "eligible": str(eligible).lower(),
                "exclusion_reason": reason,
            }
        )

    diversity = provenance["capture_diversity"]
    contract_errors = list(generic_errors)
    target = 600 if kind == "n0" else 100
    if counts["eligible"] < target:
        contract_errors.append(
            f"{kind}: eligible frames {counts['eligible']} below required {target}"
        )
    if kind == "n0":
        requirements = {
            "clips": 20,
            "duration_seconds": 600,
            "participants": 6,
            "devices": 2,
            "environments": 5,
        }
        for key, minimum in requirements.items():
            actual = (
                len(diversity[key])
                if isinstance(diversity[key], list)
                else float(diversity[key])
            )
            if actual < minimum:
                contract_errors.append(f"n0: {key} {actual} below required {minimum}")

    summary = {
        "experiment": "e2e_c0_capture_v1",
        "kind": kind,
        "rows": len(reviews),
        "counts": dict(sorted(counts.items())),
        "capture_diversity": diversity,
        "errors": contract_errors,
        "passed": not contract_errors,
    }
    _write_csv(run_dir / "reviewed_manifest.csv", FINAL_FIELDS, rows)
    (run_dir / "capture_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary, contract_errors


def open_review(run_dir: Path) -> None:
    reviews, index = load_run(run_dir)
    backup = run_dir / "gold_review.pre_review_backup.csv"
    if not backup.exists():
        shutil.copy2(run_dir / "gold_review.csv", backup)
    ReviewApp(run_dir / "gold_review.csv", reviews, index).run()


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare/review/check E2e-C0 N0/P1 fixtures")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--raw-root", type=Path, required=True)
    prepare.add_argument("--kind", choices=sorted(CAPTURE_KINDS), required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--max-total", type=int)
    prepare.add_argument("--sample-fps", type=float, default=1.0)
    prepare.add_argument("--seed", type=int, default=270727)
    prepare.add_argument("--skip-video-hashes", action="store_true")

    review = subparsers.add_parser("review")
    review.add_argument("--run-dir", type=Path, required=True)

    check = subparsers.add_parser("check")
    check.add_argument("--run-dir", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            maximum = args.max_total or (600 if args.kind == "n0" else 100)
            report = prepare_run(
                args.raw_root,
                args.kind,
                args.output,
                maximum,
                args.sample_fps,
                args.seed,
                hash_videos=not args.skip_video_hashes,
            )
            print(json.dumps(report, indent=2))
            return 0
        if args.command == "review":
            open_review(args.run_dir)
            return 0
        summary, errors = check_run(args.run_dir)
        print(json.dumps(summary, indent=2))
        return 2 if errors else 0
    except (FileExistsError, FileNotFoundError, KeyError, OSError, TypeError, ValueError) as error:
        print(f"[tracking/e2e-c0] ERROR: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
