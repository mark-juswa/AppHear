"""E3-B0 upper-body/full-frame RGB feasibility preflight.

This module performs inventory and smoke checks only. It does not extract frame tensors,
train models, modify Android, or touch production recognizer assets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_ASL_CITIZEN_ROOT = Path("F:/ASL DATASET/ASL CITIZEN/ASL_Citizen")
DEFAULT_LOCAL_ROOT = Path("F:/ASL DATASET/local")
DEFAULT_OUTPUT_ROOT = Path("artifacts/recognition_upgrade/e3_rgb_b0")
DEFAULT_SEED = 280728
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi"}


@dataclass(frozen=True)
class ClipRecord:
    source: str
    split: str
    signer_id: str
    gloss: str
    video_path: Path
    metadata_path: Path | None = None
    accepted: bool = True


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _load_asl_citizen(root: Path) -> list[ClipRecord]:
    splits_dir = root / "splits"
    videos_dir = root / "videos"
    records: list[ClipRecord] = []
    for split in ("train", "val", "test"):
        split_path = splits_dir / f"{split}.csv"
        if not split_path.exists():
            raise FileNotFoundError(f"missing ASL Citizen split file: {split_path}")
        for row in _read_csv(split_path):
            video_file = row["Video file"]
            records.append(
                ClipRecord(
                    source="asl_citizen",
                    split=split,
                    signer_id=row["Participant ID"],
                    gloss=row["Gloss"].strip().upper(),
                    video_path=videos_dir / video_file,
                )
            )
    return records


def _load_local(root: Path) -> list[ClipRecord]:
    if not root.exists():
        return []
    records: list[ClipRecord] = []
    for metadata_path in root.rglob("*.json"):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        video_file = metadata.get("video_file")
        if not video_file:
            continue
        video_path = metadata_path.with_name(video_file)
        records.append(
            ClipRecord(
                source="local",
                split="local_unassigned",
                signer_id=str(metadata.get("signer_id", "")),
                gloss=str(metadata.get("gloss") or metadata.get("word") or "").strip().upper(),
                video_path=video_path,
                metadata_path=metadata_path,
                accepted=bool(metadata.get("accepted", True)),
            )
        )
    return records


def _summarize(records: list[ClipRecord]) -> dict[str, Any]:
    by_source = Counter(record.source for record in records)
    by_split = Counter(f"{record.source}:{record.split}" for record in records)
    glosses = {record.gloss for record in records if record.gloss}
    signers = {record.signer_id for record in records if record.signer_id}
    missing_videos = [record for record in records if not record.video_path.exists()]
    return {
        "records": len(records),
        "sources": dict(sorted(by_source.items())),
        "splits": dict(sorted(by_split.items())),
        "unique_glosses": len(glosses),
        "unique_signers": len(signers),
        "missing_video_files": len(missing_videos),
        "accepted_records": sum(record.accepted for record in records),
    }


def _class_split_counts(records: list[ClipRecord], source: str) -> dict[str, dict[str, Any]]:
    table: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "train": 0,
            "val": 0,
            "test": 0,
            "local_unassigned": 0,
            "signers": set(),
            "video_paths": [],
        }
    )
    for record in records:
        if record.source != source or not record.accepted or not record.gloss:
            continue
        item = table[record.gloss]
        item[record.split] = int(item.get(record.split, 0)) + 1
        item["signers"].add(record.signer_id)
        item["video_paths"].append(str(record.video_path))

    result: dict[str, dict[str, Any]] = {}
    for gloss, item in table.items():
        result[gloss] = {
            "train": item["train"],
            "val": item["val"],
            "test": item["test"],
            "local_unassigned": item["local_unassigned"],
            "total": item["train"] + item["val"] + item["test"] + item["local_unassigned"],
            "signers": len(item["signers"]),
            "video_paths": item["video_paths"],
        }
    return result


def _select_asl_pilot(
    counts: dict[str, dict[str, Any]],
    class_count: int,
    min_train: int,
    min_val: int,
    min_test: int,
) -> list[dict[str, Any]]:
    candidates = []
    for gloss, item in counts.items():
        if item["train"] >= min_train and item["val"] >= min_val and item["test"] >= min_test:
            candidates.append(
                {
                    "gloss": gloss,
                    "train": item["train"],
                    "val": item["val"],
                    "test": item["test"],
                    "total": item["total"],
                    "signers": item["signers"],
                }
            )
    candidates.sort(key=lambda row: (-row["train"], -row["val"], -row["test"], row["gloss"]))
    return candidates[:class_count]


def _local_overlap(
    local_counts: dict[str, dict[str, Any]], selected_glosses: set[str]
) -> list[dict[str, Any]]:
    rows = []
    for gloss in sorted(selected_glosses & set(local_counts)):
        item = local_counts[gloss]
        rows.append(
            {
                "gloss": gloss,
                "local_clips": item["total"],
                "local_signers": item["signers"],
            }
        )
    return rows


def _video_probe(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "video_path": str(path),
        "exists": path.exists(),
        "readable": False,
        "frame_count": None,
        "fps": None,
        "width": None,
        "height": None,
        "error": None,
    }
    if not path.exists():
        result["error"] = "missing"
        return result
    try:
        import cv2  # type: ignore
    except ImportError:
        result["error"] = "opencv-python not installed"
        return result

    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            result["error"] = "cv2 could not open video"
            return result
        result["frame_count"] = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        result["fps"] = float(capture.get(cv2.CAP_PROP_FPS))
        result["width"] = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        result["height"] = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        ok, frame = capture.read()
        result["readable"] = bool(ok and frame is not None)
        if not result["readable"]:
            result["error"] = "first frame read failed"
    finally:
        capture.release()
    return result


def _sample_for_probe(
    records: list[ClipRecord], selected_glosses: set[str], limit: int, seed: int
) -> list[ClipRecord]:
    pool = [
        record
        for record in records
        if record.source == "asl_citizen"
        and record.accepted
        and record.gloss in selected_glosses
        and record.video_path.exists()
    ]
    grouped: dict[str, list[ClipRecord]] = defaultdict(list)
    for record in pool:
        grouped[record.gloss].append(record)
    rng = random.Random(seed)
    selected: list[ClipRecord] = []
    for gloss in sorted(grouped):
        choices = grouped[gloss][:]
        rng.shuffle(choices)
        selected.extend(choices[:1])
        if len(selected) >= limit:
            return selected[:limit]
    rng.shuffle(pool)
    for record in pool:
        if record not in selected:
            selected.append(record)
        if len(selected) >= limit:
            break
    return selected[:limit]


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output_root / args.run_id
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True, exist_ok=True)

    asl_records = _load_asl_citizen(args.asl_citizen_root)
    local_records = _load_local(args.local_root)
    all_records = asl_records + local_records
    asl_counts = _class_split_counts(all_records, "asl_citizen")
    local_counts = _class_split_counts(all_records, "local")
    selected = _select_asl_pilot(
        asl_counts,
        class_count=args.class_count,
        min_train=args.min_train,
        min_val=args.min_val,
        min_test=args.min_test,
    )
    selected_glosses = {row["gloss"] for row in selected}
    overlap = _local_overlap(local_counts, selected_glosses)

    selected_records = [
        record
        for record in asl_records
        if record.gloss in selected_glosses and record.video_path.exists()
    ]
    manifest_rows = [
        {
            "source": record.source,
            "split": record.split,
            "signer_id": record.signer_id,
            "gloss": record.gloss,
            "video_path": str(record.video_path),
        }
        for record in selected_records
    ]
    manifest_rows.sort(key=lambda row: (row["gloss"], row["split"], row["signer_id"], row["video_path"]))

    probe_records = _sample_for_probe(asl_records, selected_glosses, args.probe_videos, args.seed)
    probes = [_video_probe(record.video_path) for record in probe_records]

    split_signers: dict[str, set[str]] = defaultdict(set)
    for record in asl_records:
        if record.gloss in selected_glosses:
            split_signers[record.split].add(record.signer_id)
    leakage = {
        "train_val": sorted(split_signers["train"] & split_signers["val"]),
        "train_test": sorted(split_signers["train"] & split_signers["test"]),
        "val_test": sorted(split_signers["val"] & split_signers["test"]),
    }

    report = {
        "experiment": "e3_b0_rgb_feasibility_preflight_v1",
        "purpose": "inventory and tiny video-readability smoke only; no frame extraction or training",
        "run_dir": str(output.resolve()),
        "seed": args.seed,
        "inputs": {
            "asl_citizen_root": str(args.asl_citizen_root.resolve()),
            "local_root": str(args.local_root.resolve()),
            "train_csv_sha256": _sha256(args.asl_citizen_root / "splits" / "train.csv"),
            "val_csv_sha256": _sha256(args.asl_citizen_root / "splits" / "val.csv"),
            "test_csv_sha256": _sha256(args.asl_citizen_root / "splits" / "test.csv"),
        },
        "inventory": {
            "all": _summarize(all_records),
            "asl_citizen": _summarize(asl_records),
            "local": _summarize(local_records),
        },
        "selection_policy": {
            "class_count": args.class_count,
            "min_train": args.min_train,
            "min_val": args.min_val,
            "min_test": args.min_test,
            "selected_classes": len(selected),
        },
        "selected_classes": selected,
        "local_overlap_with_selected_classes": overlap,
        "signer_leakage": leakage,
        "video_probe": {
            "requested": args.probe_videos,
            "checked": len(probes),
            "readable": sum(bool(row["readable"]) for row in probes),
            "errors": [row for row in probes if row["error"]],
            "records": probes,
        },
        "estimated_full_pilot": {
            "manifest_records": len(manifest_rows),
            "frames_per_clip_options": [16, 32],
            "note": "Frame tensor extraction is intentionally not run by this preflight.",
        },
    }
    report["passed"] = (
        len(selected) >= min(args.class_count, 25)
        and not any(leakage.values())
        and report["video_probe"]["checked"] > 0
        and report["video_probe"]["readable"] == report["video_probe"]["checked"]
    )
    report["errors"] = []
    if len(selected) < min(args.class_count, 25):
        report["errors"].append("too few selected classes for a meaningful RGB pilot")
    if any(leakage.values()):
        report["errors"].append("signer leakage detected across selected ASL Citizen splits")
    if report["video_probe"]["checked"] == 0:
        report["errors"].append("no videos checked")
    elif report["video_probe"]["readable"] != report["video_probe"]["checked"]:
        report["errors"].append("one or more sampled videos were unreadable")

    _write_csv(
        output / "selected_classes.csv",
        selected,
        ["gloss", "train", "val", "test", "total", "signers"],
    )
    _write_csv(
        output / "pilot_manifest.csv",
        manifest_rows,
        ["source", "split", "signer_id", "gloss", "video_path"],
    )
    _write_csv(
        output / "local_overlap.csv",
        overlap,
        ["gloss", "local_clips", "local_signers"],
    )
    (output / "preflight_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (output / "preflight_report.md").write_text(_markdown(report), encoding="utf-8")
    return report


def check(args: argparse.Namespace) -> dict[str, Any]:
    report_path = args.run_dir / "preflight_report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"missing preflight report: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    required = [
        args.run_dir / "selected_classes.csv",
        args.run_dir / "pilot_manifest.csv",
        args.run_dir / "local_overlap.csv",
        args.run_dir / "preflight_report.md",
    ]
    errors = [f"missing output: {path}" for path in required if not path.exists()]
    if report.get("errors"):
        errors.extend(report["errors"])
    result = {
        "run_dir": str(args.run_dir.resolve()),
        "passed": not errors and bool(report.get("passed")),
        "errors": errors,
        "selected_classes": report.get("selection_policy", {}).get("selected_classes"),
        "manifest_records": report.get("estimated_full_pilot", {}).get("manifest_records"),
        "video_probe": report.get("video_probe", {}),
    }
    (args.run_dir / "check_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# E3-B0 RGB Feasibility Preflight",
        "",
        "Inventory and video-readability smoke only. No frame extraction or training was run.",
        "",
        f"- Passed: {report['passed']}",
        f"- Selected classes: {report['selection_policy']['selected_classes']}",
        f"- Pilot manifest records: {report['estimated_full_pilot']['manifest_records']}",
        f"- ASL Citizen records: {report['inventory']['asl_citizen']['records']}",
        f"- ASL Citizen unique glosses: {report['inventory']['asl_citizen']['unique_glosses']}",
        f"- ASL Citizen unique signers: {report['inventory']['asl_citizen']['unique_signers']}",
        f"- Local records: {report['inventory']['local']['records']}",
        f"- Local unique glosses: {report['inventory']['local']['unique_glosses']}",
        f"- Local unique signers: {report['inventory']['local']['unique_signers']}",
        f"- Video probe readable: {report['video_probe']['readable']}/{report['video_probe']['checked']}",
        "",
        "## Errors",
        "",
    ]
    if report["errors"]:
        lines.extend(f"- {error}" for error in report["errors"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Next",
            "",
            "If this preflight is accepted, prepare a user-run tiny tensor smoke. Do not start full RGB extraction or training yet.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="E3-B0 RGB feasibility preflight")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--run-id", default="preflight_01")
    prepare_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    prepare_parser.add_argument("--asl-citizen-root", type=Path, default=DEFAULT_ASL_CITIZEN_ROOT)
    prepare_parser.add_argument("--local-root", type=Path, default=DEFAULT_LOCAL_ROOT)
    prepare_parser.add_argument("--class-count", type=int, default=50)
    prepare_parser.add_argument("--min-train", type=int, default=20)
    prepare_parser.add_argument("--min-val", type=int, default=4)
    prepare_parser.add_argument("--min-test", type=int, default=4)
    prepare_parser.add_argument("--probe-videos", type=int, default=12)
    prepare_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    prepare_parser.add_argument("--overwrite", action="store_true")

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, KeyError, ValueError, OSError) as error:
        print(f"[rgb/e3-b0] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

