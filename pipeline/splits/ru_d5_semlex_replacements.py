"""Final bounded Sem-Lex replacement-video acquisition for RU-D5.

This module reads only five preselected unused TRAIN COME members from the local
video archive. It never reads supplied poses, runs MediaPipe, accepts training
rows, builds Candidate C, or trains.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.splits.ru_d5_semlex_candidate import _extract_archive_members

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = ROOT / "artifacts/recognition_upgrade/ru_d5/semlex_candidate_01"
DEFAULT_ARCHIVE = Path(r"D:\Downloads\train.tar.gz")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    manifest = _read_csv(args.run / "replacement/replacement_manifest.csv")
    original_ids = {
        row["source_video_id"]
        for row in _read_csv(args.run / "semlex_screening_manifest.csv")
    }
    errors: list[str] = []
    if len(manifest) != 5:
        errors.append(f"expected five final replacement rows, found {len(manifest)}")
    if any(row["source_split"] != "train" for row in manifest):
        errors.append("non-TRAIN row in replacement manifest")
    if any(row["canonical_gloss"] != "COME" for row in manifest):
        errors.append("non-COME row in final replacement manifest")
    if any(row["source_label_type"] != "asllex" for row in manifest):
        errors.append("non-ASL-LEX row in final replacement manifest")
    overlap = sorted({row["source_video_id"] for row in manifest} & original_ids)
    if overlap:
        errors.append(f"replacement row was already screened: {overlap}")
    signers = sorted({row["source_signer_id"] for row in manifest})
    if len(signers) != len(manifest):
        errors.append("replacement pilot is not one-clip-per-new-signer")
    summary = {
        "phase": "RU-D5",
        "stage": "semlex_final_replacements_prepared",
        "replacement_rows": len(manifest),
        "class": "COME",
        "new_signers": signers,
        "selection_reason": (
            "COME has zero automatically surviving exact rows before bounded manual "
            "repairs and only two exact repaired signers; one unused ASL-LEX row per "
            "new signer is the minimum final diversity screen"
        ),
        "supplied_poses_used": False,
        "accepted_for_training": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "errors": errors,
        "passed": not errors,
    }
    _write_json(args.run / "replacement/prepare_summary.json", summary)
    return summary


def _filmstrip(video_path: Path, output_path: Path) -> tuple[int, float]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"cannot open replacement video: {video_path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS)) or 0.0
    frames: list[np.ndarray] = []
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frames.append(frame)
    finally:
        capture.release()
    if not frames:
        raise OSError(f"replacement video decodes zero frames: {video_path}")
    indices = np.linspace(0, len(frames) - 1, num=min(10, len(frames))).astype(int)
    tiles: list[np.ndarray] = []
    for index in indices:
        frame = frames[int(index)]
        scale = min(180 / frame.shape[1], 135 / frame.shape[0])
        resized = cv2.resize(
            frame,
            (int(frame.shape[1] * scale), int(frame.shape[0] * scale)),
            interpolation=cv2.INTER_AREA,
        )
        tile = np.full((135, 180, 3), 24, np.uint8)
        y = (135 - resized.shape[0]) // 2
        x = (180 - resized.shape[1]) // 2
        tile[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
        tiles.append(tile)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), np.concatenate(tiles, axis=1))
    return len(frames), fps


def extract(args: argparse.Namespace) -> dict[str, Any]:
    manifest = _read_csv(args.run / "replacement/replacement_manifest.csv")
    video_dir = args.run / "replacement/inbound/videos"
    wanted = {
        row["video_archive_member"]: video_dir / f"{row['source_video_id']}.webm"
        for row in manifest
    }
    extracted, missing = _extract_archive_members(args.video_archive, wanted, "replacement-videos")
    rows: list[dict[str, Any]] = []
    for source in manifest:
        item = extracted.get(source["video_archive_member"])
        if item is None:
            continue
        video_path = Path(item["local_path"])
        filmstrip_path = (
            args.run
            / "replacement/visual_review/filmstrips"
            / f"COME_{source['source_video_id']}.jpg"
        )
        frame_count, fps = _filmstrip(video_path, filmstrip_path)
        rows.append(
            {
                **source,
                "raw_video_path": str(video_path.resolve()),
                "raw_video_sha256": _sha256(video_path),
                "archive_member_bytes": item["archive_member_bytes"],
                "decoded_frames": frame_count,
                "reported_fps": f"{fps:.6f}",
                "filmstrip_path": str(filmstrip_path.resolve()),
                "visual_decision": "PENDING",
                "visual_reason": "",
                "apphear_extraction_status": "NOT_RUN",
            }
        )
    _write_csv(args.run / "replacement/replacement_extraction_manifest.csv", rows)
    summary = {
        "phase": "RU-D5",
        "stage": "semlex_final_replacement_videos_extracted",
        "requested_rows": len(manifest),
        "extracted_rows": len(rows),
        "missing_archive_members": sorted(missing),
        "archive_scans_performed": int(
            any(
                item.get("extraction_status") != "REUSED_EXISTING"
                for item in extracted.values()
            )
        ),
        "supplied_poses_used": False,
        "accepted_for_training": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "passed": len(rows) == len(manifest) and not missing,
    }
    _write_json(args.run / "replacement/extraction_summary.json", summary)
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    path = args.run / "replacement/replacement_extraction_manifest.csv"
    errors: list[str] = []
    rows = _read_csv(path) if path.is_file() else []
    if len(rows) != 5:
        errors.append(f"expected five extracted replacements, found {len(rows)}")
    for row in rows:
        video = Path(row["raw_video_path"])
        filmstrip = Path(row["filmstrip_path"])
        if not video.is_file() or _sha256(video) != row["raw_video_sha256"]:
            errors.append(f"invalid replacement video lineage: {video}")
        if not filmstrip.is_file():
            errors.append(f"missing replacement filmstrip: {filmstrip}")
        if row["visual_decision"] != "PENDING":
            errors.append(f"replacement prematurely adjudicated: {row['source_video_id']}")
    result = {
        "phase": "RU-D5",
        "stage": "semlex_final_replacement_check",
        "rows": len(rows),
        "errors": errors,
        "accepted_for_training": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "passed": not errors,
    }
    _write_json(args.run / "replacement/check_summary.json", result)
    return result


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("prepare", "extract", "check"):
        child = sub.add_parser(name)
        child.add_argument("--run", type=Path, default=DEFAULT_RUN)
        child.add_argument("--video-archive", type=Path, default=DEFAULT_ARCHIVE)
    return root


def main() -> int:
    args = parser().parse_args()
    result = {"prepare": prepare, "extract": extract, "check": check}[args.command](args)
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
