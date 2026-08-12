"""Import and review the bounded E6 negative-context upload.

This utility is data-readiness only. It never moves raw videos, extracts
landmarks, trains a model, exports TFLite, or modifies Android assets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pipeline.rgb import e6_product_core_review as review_gui


DEFAULT_RAW_ROOT = Path("scratchpad/e6_product_core_collection/raw/nosign/signs")
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/product_core_data_readiness/"
    "e6_negative_upload_review_01"
)
PROPOSED_SPLIT = "test_fresh_negative_provisional"
CORE_SIGNS = {"GOOD", "HELLO", "SORRY", "HAVE", "KNOW"}
DEVELOPMENT_GAPS = {
    "P1_IDLE_HANDS": 57,
    "P1_FACE_ADJACENT": 146,
    "P1_ACCIDENTAL_MOTION": 150,
    "TRANSITION_PARTIAL": 100,
}
FOLDER_TO_SUBTYPE = {
    "idle_hands": "P1_IDLE_HANDS",
    "face_adjacent": "P1_FACE_ADJACENT",
    "accidental_motion": "P1_ACCIDENTAL_MOTION",
    "transition_or_partial": "TRANSITION_PARTIAL",
}


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
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _canonical_category(folder_name: str) -> tuple[str, str]:
    key = folder_name.strip().lower()
    subtype = FOLDER_TO_SUBTYPE.get(key)
    if subtype:
        return subtype, ""
    return "OOV_SIGN", folder_name.strip().upper()


def _sample_indexes(count: int) -> list[int]:
    if count <= 0:
        return []
    return sorted({0, count // 2, count - 1})


def _spot_review_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row["session_id"])].append(row)
    selected: list[dict[str, Any]] = []
    for session_id in sorted(groups):
        group = sorted(groups[session_id], key=lambda row: str(row["raw_video_path"]))
        for rank, index in enumerate(_sample_indexes(len(group)), start=1):
            row = dict(group[index])
            row["review_sample_rank"] = rank
            row["review_group_size"] = len(group)
            selected.append(row)
    return selected


def _load_sidecar(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid sidecar {path}: {exc}") from exc
    required = {
        "sample_id",
        "signer_id",
        "session_id",
        "video_file",
        "native_fps",
        "total_frames",
    }
    missing = sorted(field for field in required if payload.get(field) in {None, ""})
    if missing:
        raise ValueError(f"sidecar missing {missing}: {path}")
    return payload


def _manifest_row(sidecar_path: Path, raw_root: Path) -> dict[str, Any]:
    sidecar = _load_sidecar(sidecar_path)
    video_path = sidecar_path.parent / str(sidecar["video_file"])
    if not video_path.is_file():
        raise FileNotFoundError(f"sidecar video missing: {video_path}")
    subtype, oov_label = _canonical_category(sidecar_path.parent.name)
    fps = float(sidecar["native_fps"])
    frames = int(sidecar["total_frames"])
    duration = frames / fps if fps > 0 else 0.0
    warnings = [str(item) for item in sidecar.get("quality_warnings", [])]
    if duration < 3.0:
        warnings.append("short_event_clip_not_full_streaming_window")
    display_label = f"OOV:{oov_label}" if subtype == "OOV_SIGN" else subtype
    return {
        "row_id": str(sidecar["sample_id"]),
        "sample_id": str(sidecar["sample_id"]),
        "source_dataset": "APPHEAR_NEGATIVE_CAPTURE",
        "source_schema": str(sidecar.get("schema_version", "")),
        "canonical_subtype": subtype,
        "oov_label": oov_label,
        "canonical_gloss": display_label,
        "label_variant": str(sidecar.get("word", "")),
        "signer_id": str(sidecar["signer_id"]),
        "session_id": str(sidecar["session_id"]),
        "repetition_index": str(sidecar.get("repetition_index", "")),
        "source_split": PROPOSED_SPLIT,
        "proposed_split": PROPOSED_SPLIT,
        "raw_video_path": str(video_path.resolve()),
        "relative_video_path": str(video_path.resolve().relative_to(raw_root.resolve())),
        "sidecar_path": str(sidecar_path.resolve()),
        "raw_video_sha256": _sha256(video_path),
        "bytes": video_path.stat().st_size,
        "duration_sec": f"{duration:.6f}",
        "fps": f"{fps:.6f}",
        "frame_count": frames,
        "width": int(sidecar.get("frame_width", 0) or 0),
        "height": int(sidecar.get("frame_height", 0) or 0),
        "hand_hit_rate": str(sidecar.get("hand_hit_rate", "")),
        "pose_hit_rate": str(sidecar.get("pose_hit_rate", "")),
        "camera_facing": str(sidecar.get("camera_direction", "")),
        "lighting": str(sidecar.get("lighting", "")),
        "background": str(sidecar.get("background", "")),
        "posture": str(sidecar.get("posture", "")),
        "quality_warnings": "|".join(warnings),
        "recorder_accepted": str(bool(sidecar.get("accepted", False))).lower(),
        "previous_experiment_usage_exact": "none_found_new_capture_2026_08_08",
        "classification": "Manual review required",
        "classification_reasons": (
            "new_single_signer_fresh_negative_candidate;"
            "short_event_not_full_streaming_window;"
            "session_batch_spot_review_required"
        ),
        "fresh_evaluation_only": "true",
        "development_gap_credit": 0,
    }


def _review_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for field in review_gui.REVIEW_FIELDS:
        out.setdefault(field, "")
    return out


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    raw_root = args.raw_root.resolve()
    if not raw_root.is_dir():
        raise FileNotFoundError(f"raw root missing: {raw_root}")
    run_dir = args.run_dir
    if run_dir.exists() and any(run_dir.iterdir()) and not args.overwrite:
        raise FileExistsError(f"run directory is not empty; pass --overwrite: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)

    sidecars = sorted(raw_root.rglob("*.json"))
    if not sidecars:
        raise ValueError(f"no JSON sidecars found under {raw_root}")
    rows = [_manifest_row(path, raw_root) for path in sidecars]
    hashes = Counter(str(row["raw_video_sha256"]) for row in rows)
    duplicate_hashes = {value for value, count in hashes.items() if count > 1}
    for row in rows:
        row["duplicate_status"] = (
            "exact_duplicate" if row["raw_video_sha256"] in duplicate_hashes else "unique"
        )
    if duplicate_hashes:
        raise ValueError(f"found {len(duplicate_hashes)} exact duplicate hash groups")

    signer_ids = sorted({str(row["signer_id"]) for row in rows})
    queue = [_review_row(row) for row in _spot_review_queue(rows)]
    manifest_fields = list(rows[0].keys())
    review_fields = list(queue[0].keys())
    _write_csv(run_dir / "source_manifest_snapshot.csv", rows, manifest_fields)
    _write_csv(run_dir / "review_manifest.csv", queue, review_fields)
    shutil.copy2(run_dir / "review_manifest.csv", run_dir / "review_manifest.pre_review_backup.csv")

    payload = {
        "experiment": "e6_negative_upload_review_v1",
        "run_dir": str(run_dir.resolve()),
        "raw_root": str(raw_root),
        "rows": len(rows),
        "review_rows": len(queue),
        "signers": signer_ids,
        "sessions": len({str(row["session_id"]) for row in rows}),
        "subtype_counts": dict(sorted(Counter(str(row["canonical_subtype"]) for row in rows).items())),
        "oov_label_counts": dict(sorted(Counter(str(row["oov_label"]) for row in rows if row["oov_label"]).items())),
        "unique_hashes": len(hashes),
        "proposed_split": PROPOSED_SPLIT,
        "development_gap_credit": 0,
        "review_command": f'python -m pipeline.rgb.e6_negative_upload_review review --run-dir "{run_dir.resolve()}"',
        "summarize_command": f'python -m pipeline.rgb.e6_negative_upload_review summarize --run-dir "{run_dir.resolve()}" --require-reviewed',
        "check_command": f'python -m pipeline.rgb.e6_negative_upload_review check --run-dir "{run_dir.resolve()}"',
        "warnings": [
            "Single-signer upload: reserve every row for fresh negative evaluation.",
            "Short recorder clips are not full 96-frame streaming-window evidence.",
            "Do not count these rows toward the 453-window development gap.",
        ],
    }
    _write_json(run_dir / "prepare_summary.json", payload)
    return payload


def review(args: argparse.Namespace) -> None:
    review_gui.review(argparse.Namespace(run_dir=args.run_dir, negative_mode=True))


def _session_decisions(review_rows: list[dict[str, str]]) -> dict[str, str]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in review_rows:
        grouped[row.get("session_id", "")].append(row)
    decisions: dict[str, str] = {}
    for session_id, rows in grouped.items():
        if len(rows) < 3 or any(not row.get("review_status") for row in rows):
            decisions[session_id] = "review_incomplete"
        elif all(row.get("review_decision") == "accept" for row in rows):
            decisions[session_id] = "accepted_batch"
        elif any(row.get("review_decision") == "needs_expert" for row in rows):
            decisions[session_id] = "needs_expert"
        else:
            decisions[session_id] = "full_session_review_required"
    return decisions


def summarize(args: argparse.Namespace) -> dict[str, Any]:
    source_rows = _read_csv(args.run_dir / "source_manifest_snapshot.csv")
    review_rows = _read_csv(args.run_dir / "review_manifest.csv")
    if args.require_reviewed and any(not row.get("review_status") for row in review_rows):
        raise ValueError("review is incomplete")
    session_decisions = _session_decisions(review_rows)
    final_rows = []
    for row in source_rows:
        final = dict(row)
        batch = session_decisions.get(row.get("session_id", ""), "review_incomplete")
        final["batch_review_decision"] = batch
        final["final_status"] = (
            "accepted_fresh_negative_evaluation"
            if batch == "accepted_batch"
            else "manual_review_required"
        )
        final["final_split"] = PROPOSED_SPLIT if batch == "accepted_batch" else "review_only"
        final_rows.append(final)

    accepted = [row for row in final_rows if row["final_status"] == "accepted_fresh_negative_evaluation"]
    final_fields = list(final_rows[0].keys())
    _write_csv(args.run_dir / "final_manifest.csv", final_rows, final_fields)
    _write_csv(args.run_dir / "accepted_fresh_negative_manifest.csv", accepted, final_fields)

    accepted_by_subtype = Counter(row["canonical_subtype"] for row in accepted)
    payload = {
        "experiment": "e6_negative_upload_review_v1",
        "run_dir": str(args.run_dir.resolve()),
        "rows": len(final_rows),
        "review_rows": len(review_rows),
        "accepted_fresh_evaluation_rows": len(accepted),
        "accepted_by_subtype": dict(sorted(accepted_by_subtype.items())),
        "session_decisions": dict(sorted(Counter(session_decisions.values()).items())),
        "signers": sorted({row["signer_id"] for row in accepted}),
        "final_split": PROPOSED_SPLIT,
        "development_gap_credit": 0,
        "development_gaps_unchanged": DEVELOPMENT_GAPS,
        "production_ready": False,
        "decision": (
            "provisional_fresh_negative_evaluation_ready"
            if accepted
            else "negative_upload_not_yet_accepted"
        ),
        "limitations": [
            "Only one fresh negative signer is represented.",
            "All clips are short events rather than complete streaming windows.",
            "This result cannot establish production signer-independent performance.",
        ],
    }
    _write_json(args.run_dir / "review_summary.json", payload)
    return payload


def check(args: argparse.Namespace) -> dict[str, Any]:
    errors = []
    required = ["prepare_summary.json", "source_manifest_snapshot.csv", "review_manifest.csv"]
    for relative in required:
        if not (args.run_dir / relative).is_file():
            errors.append(f"missing output: {relative}")
    rows = _read_csv(args.run_dir / "review_manifest.csv") if not errors else []
    if len(rows) != 54:
        errors.append(f"expected 54 deterministic review rows, found {len(rows)}")
    if any(row.get("proposed_split") != PROPOSED_SPLIT for row in rows):
        errors.append("review rows are not consistently reserved for fresh negative evaluation")
    if any(row.get("development_gap_credit") not in {"0", 0} for row in rows):
        errors.append("review rows incorrectly claim development-gap credit")
    if args.require_reviewed and any(not row.get("review_status") for row in rows):
        errors.append("review is incomplete")
    if args.require_summary and not (args.run_dir / "review_summary.json").is_file():
        errors.append("missing review_summary.json")
    return {
        "run_dir": str(args.run_dir.resolve()),
        "rows": len(rows),
        "completed": sum(1 for row in rows if row.get("review_status")),
        "remaining": sum(1 for row in rows if not row.get("review_status")),
        "passed": not errors,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="E6 negative upload import and review")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    prepare_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--overwrite", action="store_true")
    prepare_parser.set_defaults(func=prepare)

    review_parser = sub.add_parser("review")
    review_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    review_parser.set_defaults(func=review)

    summarize_parser = sub.add_parser("summarize")
    summarize_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    summarize_parser.add_argument("--require-reviewed", action="store_true")
    summarize_parser.set_defaults(func=summarize)

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    check_parser.add_argument("--require-reviewed", action="store_true")
    check_parser.add_argument("--require-summary", action="store_true")
    check_parser.set_defaults(func=check)

    args = parser.parse_args()
    try:
        result = args.func(args)
        if result is not None:
            print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        print(f"[e6-negative-upload] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
