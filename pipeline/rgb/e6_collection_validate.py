"""E6 product-core collection validator.

Data-readiness utility only. It validates raw recording folders against the
product-core collection targets. It does not extract features, train models,
modify schema, export TFLite, or touch Android.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

DEFAULT_TARGET_DIR = Path("context/recognition_upgrade/product_core_data_readiness/collection_targets_v1")
DEFAULT_RAW_ROOT = Path("scratchpad/e6_product_core_collection/raw")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/product_core_data_readiness/e6_collection_validation_01")
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}
KINDS = {"positive", "nosign", "oov", "transition"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def _probe(path: Path) -> dict[str, Any]:
    out = {"decode_status": "not_checked", "frame_count": "", "fps": "", "width": "", "height": "", "duration_sec": ""}
    if not path.exists():
        out["decode_status"] = "missing"
        return out
    if path.stat().st_size <= 0:
        out["decode_status"] = "zero_byte"
        return out
    if cv2 is None:
        return out
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        out["decode_status"] = "decode_failed_open"
        return out
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    ok, frame = cap.read()
    cap.release()
    out.update(
        {
            "decode_status": "ok" if ok and frame is not None else "decode_failed_frame",
            "frame_count": frame_count,
            "fps": round(fps, 3),
            "width": width,
            "height": height,
            "duration_sec": round(frame_count / fps, 3) if fps else "",
        }
    )
    return out


def _parse_video(root: Path, path: Path) -> dict[str, Any]:
    rel = path.relative_to(root)
    parts = rel.parts
    row = {
        "raw_video_path": str(path),
        "relative_path": str(rel),
        "kind": "",
        "label_or_subtype": "",
        "participant_id": "",
        "device_id": "",
        "environment_id": "",
        "camera_facing": "",
        "structure_status": "invalid",
        "structure_reason": "expected <kind>/<label_or_subtype>/<participant>/<device>/<environment>/<front-or-back>/<video>",
    }
    if len(parts) >= 7 and parts[0] in KINDS:
        row.update(
            {
                "kind": parts[0],
                "label_or_subtype": parts[1].upper(),
                "participant_id": parts[2],
                "device_id": parts[3],
                "environment_id": parts[4],
                "camera_facing": parts[5],
                "structure_status": "ok",
                "structure_reason": "",
            }
        )
    return row


def init(args: argparse.Namespace) -> None:
    root = args.raw_root
    positive = _read_csv(args.target_dir / "positive_collection_targets.csv")
    negative = _read_csv(args.target_dir / "nosign_oov_transition_targets.csv")
    for row in positive:
        for participant in args.placeholder_participants:
            (root / "positive" / row["canonical_gloss"] / participant / "phoneA" / "indoor" / "front").mkdir(parents=True, exist_ok=True)
    for row in negative:
        for participant in args.placeholder_participants:
            (root / "nosign" / row["sample_kind"] / participant / "phoneA" / "indoor" / "front").mkdir(parents=True, exist_ok=True)
    readme = root / "README_COLLECTION_STRUCTURE.txt"
    readme.write_text(
        "Place videos using this structure:\n"
        "positive/<SIGN>/<PARTICIPANT>/<DEVICE>/<ENVIRONMENT>/<front-or-back>/<video>.mp4\n"
        "nosign/<SUBTYPE>/<PARTICIPANT>/<DEVICE>/<ENVIRONMENT>/<front-or-back>/<video>.mp4\n"
        "oov/<OOV_LABEL>/<PARTICIPANT>/<DEVICE>/<ENVIRONMENT>/<front-or-back>/<video>.mp4\n"
        "transition/<SIGN_OR_PAIR>/<PARTICIPANT>/<DEVICE>/<ENVIRONMENT>/<front-or-back>/<video>.mp4\n",
        encoding="utf-8",
    )
    print(json.dumps({"raw_root": str(root.resolve()), "created": True}, indent=2))


def validate(args: argparse.Namespace) -> None:
    root = args.raw_root
    output = args.output
    positive_targets = {row["canonical_gloss"]: row for row in _read_csv(args.target_dir / "positive_collection_targets.csv")}
    negative_targets = {row["sample_kind"].upper(): row for row in _read_csv(args.target_dir / "nosign_oov_transition_targets.csv")}
    videos = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS] if root.exists() else []
    rows = []
    by_hash: dict[str, list[int]] = defaultdict(list)
    for path in sorted(videos):
        row = _parse_video(root, path)
        row["bytes"] = path.stat().st_size
        row["sha256"] = _sha256(path) if row["bytes"] else ""
        if row["sha256"]:
            by_hash[row["sha256"]].append(len(rows))
        row.update(_probe(path))
        row["validation_status"] = "accepted_for_manifest_review"
        reasons = []
        if row["structure_status"] != "ok":
            reasons.append(row["structure_reason"])
        if row["decode_status"] != "ok":
            reasons.append(f"decode_status={row['decode_status']}")
        if row["kind"] == "positive" and row["label_or_subtype"] not in positive_targets:
            reasons.append("positive label not in target signs")
        if row["kind"] == "nosign" and row["label_or_subtype"] not in negative_targets:
            reasons.append("nosign subtype not in target subtypes")
        if reasons:
            row["validation_status"] = "needs_fix"
        row["validation_reasons"] = " | ".join(reasons)
        rows.append(row)
    for sha, idxs in by_hash.items():
        if len(idxs) > 1:
            group = "dup_" + sha[:12]
            for idx in idxs:
                rows[idx]["duplicate_group"] = group
                rows[idx]["validation_status"] = "needs_fix"
                rows[idx]["validation_reasons"] = (rows[idx].get("validation_reasons", "") + " | exact duplicate video").strip(" |")
    for row in rows:
        row.setdefault("duplicate_group", "")
    fields = [
        "kind", "label_or_subtype", "participant_id", "device_id", "environment_id", "camera_facing",
        "raw_video_path", "relative_path", "bytes", "sha256", "duplicate_group", "decode_status",
        "frame_count", "fps", "width", "height", "duration_sec", "structure_status", "validation_status", "validation_reasons"
    ]
    _write_csv(output / "raw_collection_inventory.csv", rows, fields)
    positive_counts = defaultdict(lambda: {"clips": 0, "signers": set()})
    negative_counts = defaultdict(lambda: {"clips": 0, "signers": set()})
    for row in rows:
        if row["validation_status"] != "accepted_for_manifest_review":
            continue
        if row["kind"] == "positive":
            item = positive_counts[row["label_or_subtype"]]
            item["clips"] += 1
            item["signers"].add(row["participant_id"])
        elif row["kind"] in {"nosign", "oov", "transition"}:
            item = negative_counts[row["label_or_subtype"]]
            item["clips"] += 1
            item["signers"].add(row["participant_id"])
    progress = []
    for gloss, target in positive_targets.items():
        item = positive_counts[gloss]
        need_clips = int(target["recommended_new_local_clips"])
        need_signers = int(target["recommended_new_local_signers"])
        progress.append(
            {
                "canonical_gloss": gloss,
                "target_new_clips": need_clips,
                "accepted_new_clips": item["clips"],
                "remaining_new_clips": max(0, need_clips - item["clips"]),
                "target_new_signers": need_signers,
                "accepted_new_signers": len(item["signers"]),
                "remaining_new_signers": max(0, need_signers - len(item["signers"])),
            }
        )
    _write_csv(output / "positive_collection_progress.csv", progress, list(progress[0].keys()) if progress else [])
    neg_progress = []
    for subtype, target in negative_targets.items():
        item = negative_counts[subtype]
        need = int(target["target_windows"])
        neg_progress.append(
            {
                "sample_kind": subtype,
                "target_windows": need,
                "accepted_raw_videos_or_windows": item["clips"],
                "remaining_windows": max(0, need - item["clips"]),
                "accepted_signers": len(item["signers"]),
            }
        )
    _write_csv(output / "nosign_oov_transition_progress.csv", neg_progress, list(neg_progress[0].keys()) if neg_progress else [])
    summary = {
        "raw_root": str(root.resolve()),
        "videos_found": len(videos),
        "accepted_for_manifest_review": sum(1 for row in rows if row["validation_status"] == "accepted_for_manifest_review"),
        "needs_fix": sum(1 for row in rows if row["validation_status"] == "needs_fix"),
        "duplicate_groups": sum(1 for idxs in by_hash.values() if len(idxs) > 1),
        "remaining_positive_clips": sum(int(row["remaining_new_clips"]) for row in progress),
        "remaining_positive_signer_slots": sum(int(row["remaining_new_signers"]) for row in progress),
        "remaining_nosign_oov_transition_windows": sum(int(row["remaining_windows"]) for row in neg_progress),
        "outputs": ["raw_collection_inventory.csv", "positive_collection_progress.csv", "nosign_oov_transition_progress.csv"],
    }
    _write_json(output / "collection_validation_summary.json", summary)
    print(json.dumps(summary, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="E6 product-core collection folder initializer and validator")
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("--target-dir", type=Path, default=DEFAULT_TARGET_DIR)
    p_init.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    p_init.add_argument("--placeholder-participants", nargs="+", default=["P_NEW01", "P_NEW02", "P_NEW03", "P_NEW04"])
    p_init.set_defaults(func=init)
    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--target-dir", type=Path, default=DEFAULT_TARGET_DIR)
    p_validate.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    p_validate.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p_validate.set_defaults(func=validate)
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"[e6-collection] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
