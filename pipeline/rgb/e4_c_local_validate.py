"""E4-C local supplementary video validation.

This module validates the revised E4-C practical-vocabulary candidates from ``E:\local``.
It probes videos and split feasibility only. It does not extract tensors, train models,
modify Android, or touch production recognizer assets.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_AUDIT_DIR = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_audit_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_validation_01"
)
DEFAULT_MIN_FRAMES = 4
DEFAULT_MIN_READABLE_RATE = 0.98


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


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _load_selected_glosses(
    selected_path: Path, selected_glosses: list[str] | None = None
) -> list[str]:
    if selected_glosses:
        glosses = [gloss.strip().upper() for gloss in selected_glosses if gloss.strip()]
        if not glosses:
            raise ValueError("selected gloss list is empty")
        return glosses
    rows = _read_csv(selected_path)
    glosses = [row["canonical_gloss"].strip().upper() for row in rows]
    if not glosses:
        raise ValueError(f"no selected glosses found in {selected_path}")
    return glosses


def _load_candidate_rows(inventory_path: Path, selected_glosses: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _read_csv(inventory_path):
        gloss = row.get("canonical_gloss", "").strip().upper()
        if gloss not in selected_glosses:
            continue
        rows.append(
            {
                **row,
                "canonical_gloss": gloss,
                "accepted_bool": _as_bool(row.get("accepted")),
                "video_exists_bool": _as_bool(row.get("video_exists")),
                "hand_hit_float": _as_float(row.get("hand_hit_rate")),
                "hand_hit_known_bool": _as_bool(row.get("hand_hit_known")),
                "quality_score_float": _as_float(row.get("quality_score")),
                "quality_score_known_bool": _as_bool(row.get("quality_score_known")),
            }
        )
    if not rows:
        raise ValueError("selected glosses have no matching inventory rows")
    return rows


def _video_probe(path: Path, min_frames: int) -> dict[str, Any]:
    result: dict[str, Any] = {
        "probe_exists": path.exists(),
        "probe_readable": False,
        "probe_frame_count": "",
        "probe_fps": "",
        "probe_width": "",
        "probe_height": "",
        "probe_duration_seconds": "",
        "probe_error": "",
    }
    if not path.exists():
        result["probe_error"] = "missing_video"
        return result
    try:
        import cv2  # type: ignore
    except ImportError:
        result["probe_error"] = "opencv_python_missing"
        return result

    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            result["probe_error"] = "cv2_open_failed"
            return result
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        result["probe_frame_count"] = frame_count
        result["probe_fps"] = fps
        result["probe_width"] = width
        result["probe_height"] = height
        if math.isfinite(fps) and fps > 0 and frame_count > 0:
            result["probe_duration_seconds"] = frame_count / fps
        if frame_count < min_frames:
            result["probe_error"] = f"too_few_frames_lt_{min_frames}"
            return result

        middle = max(0, frame_count // 2)
        capture.set(cv2.CAP_PROP_POS_FRAMES, middle)
        ok, frame = capture.read()
        result["probe_readable"] = bool(ok and frame is not None)
        if not result["probe_readable"]:
            result["probe_error"] = "middle_frame_read_failed"
    finally:
        capture.release()
    return result


def _validate_rows(rows: list[dict[str, Any]], min_frames: int) -> list[dict[str, Any]]:
    validated = []
    for index, row in enumerate(rows, start=1):
        video_path = Path(row["video_path"])
        probe = _video_probe(video_path, min_frames=min_frames)
        hand_hit = row.get("hand_hit_float")
        quality = row.get("quality_score_float")
        warnings = []
        if not row["accepted_bool"]:
            warnings.append("not_accepted")
        if not row["video_exists_bool"]:
            warnings.append("inventory_video_missing")
        if row.get("hand_hit_known_bool") and hand_hit is not None and hand_hit < 0.5:
            warnings.append("low_hand_hit")
        if row.get("quality_score_known_bool") and quality is not None and quality < 0.35:
            warnings.append("low_quality_score")
        duration = probe.get("probe_duration_seconds")
        if isinstance(duration, float) and duration < 0.15:
            warnings.append("very_short_duration")
        eligible = bool(row["accepted_bool"] and probe["probe_readable"] and not probe["probe_error"])
        validated.append(
            {
                "row_index": index,
                "canonical_gloss": row["canonical_gloss"],
                "source_folder": row.get("source_folder", ""),
                "folder_word": row.get("folder_word", ""),
                "sidecar_dialect": row.get("sidecar_dialect", ""),
                "signer_id": row.get("signer_id", ""),
                "session_id": row.get("session_id", ""),
                "repetition_index": row.get("repetition_index", ""),
                "accepted": row.get("accepted", ""),
                "hand_hit_known": row.get("hand_hit_known", ""),
                "hand_hit_rate": row.get("hand_hit_rate", ""),
                "quality_score_known": row.get("quality_score_known", ""),
                "quality_score": row.get("quality_score", ""),
                "inventory_total_frames": row.get("total_frames", ""),
                "video_path": str(video_path),
                **probe,
                "eligible": eligible,
                "warnings": ";".join(warnings),
            }
        )
    return validated


def _summarize_by_gloss(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["canonical_gloss"]].append(row)

    out = []
    for gloss, items in sorted(grouped.items()):
        eligible = [row for row in items if row["eligible"]]
        signer_counts = Counter(row["signer_id"] for row in eligible if row["signer_id"])
        dialects = sorted({row["sidecar_dialect"] for row in items if row["sidecar_dialect"]})
        frame_counts = [
            int(row["probe_frame_count"])
            for row in eligible
            if isinstance(row.get("probe_frame_count"), int)
        ]
        out.append(
            {
                "canonical_gloss": gloss,
                "raw_rows": len(items),
                "eligible_rows": len(eligible),
                "readable_rows": sum(bool(row["probe_readable"]) for row in items),
                "signer_count": len(signer_counts),
                "signers": ";".join(sorted(signer_counts)),
                "min_eligible_per_signer": min(signer_counts.values()) if signer_counts else 0,
                "max_eligible_per_signer": max(signer_counts.values()) if signer_counts else 0,
                "sidecar_dialects": ";".join(dialects),
                "min_frames": min(frame_counts) if frame_counts else "",
                "median_frames": sorted(frame_counts)[len(frame_counts) // 2] if frame_counts else "",
                "max_frames": max(frame_counts) if frame_counts else "",
            }
        )
    return out


def _split_feasibility(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if row["eligible"]]
    signers = sorted({row["signer_id"] for row in eligible if row["signer_id"]})
    by_gloss_signer: dict[str, Counter[str]] = defaultdict(Counter)
    for row in eligible:
        if row["signer_id"]:
            by_gloss_signer[row["canonical_gloss"]][row["signer_id"]] += 1

    impossible_three_way = []
    impossible_two_way = []
    for gloss, counts in sorted(by_gloss_signer.items()):
        if len(counts) < 3:
            impossible_three_way.append(gloss)
        if len(counts) < 2:
            impossible_two_way.append(gloss)

    return {
        "unique_signers": len(signers),
        "signers": signers,
        "three_way_signer_disjoint_possible_for_all_classes": not impossible_three_way,
        "two_way_signer_disjoint_possible_for_all_classes": not impossible_two_way,
        "classes_blocking_three_way": impossible_three_way,
        "classes_blocking_two_way": impossible_two_way,
        "recommendation": (
            "three_way_signer_disjoint_train_val_test"
            if not impossible_three_way
            else "two_way_holdout_or_collect_more_signers_before_strong_generalization_claims"
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# E4-C Local Supplementary Validation",
        "",
        "Video readability and split-feasibility validation only. No extraction or training was run.",
        "",
        f"- Passed: {report['passed']}",
        f"- Selected glosses: {', '.join(report['selected_glosses'])}",
        f"- Candidate rows: {report['candidate_rows']}",
        f"- Eligible rows: {report['eligible_rows']}",
        f"- Readable rate: {report['readable_rate']:.4f}",
        f"- Unique eligible signers: {report['split_feasibility']['unique_signers']}",
        f"- Split recommendation: {report['split_feasibility']['recommendation']}",
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
            "If this validation is accepted, prepare a bounded E4-B local-supplementary manifest/split package. Do not train until that package is reviewed.",
            "",
        ]
    )
    return "\n".join(lines)


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists() and any(args.output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {args.output}")

    selected_path = args.audit_dir / "recommended_replacement_12_v1.csv"
    inventory_path = args.audit_dir / "local_clip_inventory.csv"
    selected = _load_selected_glosses(selected_path, args.selected_gloss)
    candidates = _load_candidate_rows(inventory_path, set(selected))
    rows = _validate_rows(candidates, min_frames=args.min_frames)
    by_gloss = _summarize_by_gloss(rows)
    split = _split_feasibility(rows)

    eligible_rows = sum(bool(row["eligible"]) for row in rows)
    readable_rows = sum(bool(row["probe_readable"]) for row in rows)
    readable_rate = readable_rows / len(rows) if rows else 0.0

    errors = []
    missing_glosses = sorted(set(selected) - {row["canonical_gloss"] for row in rows})
    if missing_glosses:
        errors.append(f"selected glosses missing from inventory: {missing_glosses}")
    weak = [row["canonical_gloss"] for row in by_gloss if int(row["eligible_rows"]) < args.min_per_gloss]
    if weak:
        errors.append(f"classes below min eligible rows {args.min_per_gloss}: {weak}")
    if readable_rate < args.min_readable_rate:
        errors.append(
            f"readable rate {readable_rate:.4f} below required {args.min_readable_rate:.4f}"
        )
    if not split["two_way_signer_disjoint_possible_for_all_classes"]:
        errors.append("at least one class has fewer than two eligible signers")

    report = {
        "experiment": "e4_c_local_supplementary_validation_v1",
        "audit_dir": str(args.audit_dir.resolve()),
        "run_dir": str(args.output.resolve()),
        "selected_glosses": selected,
        "candidate_rows": len(rows),
        "eligible_rows": eligible_rows,
        "readable_rows": readable_rows,
        "readable_rate": readable_rate,
        "min_frames": args.min_frames,
        "min_per_gloss": args.min_per_gloss,
        "min_readable_rate": args.min_readable_rate,
        "split_feasibility": split,
        "errors": errors,
        "passed": not errors,
        "production_changes": "none",
        "next_required_action": (
            "prepare reviewed manifest/split package if accepted; otherwise collect or relabel"
        ),
    }

    args.output.mkdir(parents=True, exist_ok=True)
    _write_csv(
        args.output / "validated_clip_inventory.csv",
        rows,
        [
            "row_index",
            "canonical_gloss",
            "source_folder",
            "folder_word",
            "sidecar_dialect",
            "signer_id",
            "session_id",
            "repetition_index",
            "accepted",
            "hand_hit_known",
            "hand_hit_rate",
            "quality_score_known",
            "quality_score",
            "inventory_total_frames",
            "video_path",
            "probe_exists",
            "probe_readable",
            "probe_frame_count",
            "probe_fps",
            "probe_width",
            "probe_height",
            "probe_duration_seconds",
            "probe_error",
            "eligible",
            "warnings",
        ],
    )
    _write_csv(
        args.output / "gloss_validation_summary.csv",
        by_gloss,
        [
            "canonical_gloss",
            "raw_rows",
            "eligible_rows",
            "readable_rows",
            "signer_count",
            "signers",
            "min_eligible_per_signer",
            "max_eligible_per_signer",
            "sidecar_dialects",
            "min_frames",
            "median_frames",
            "max_frames",
        ],
    )
    _write_json(args.output / "validation_report.json", report)
    (args.output / "README.md").write_text(_markdown(report), encoding="utf-8")
    return report


def check(args: argparse.Namespace) -> dict[str, Any]:
    report_path = args.run_dir / "validation_report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"missing validation report: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    required = [
        args.run_dir / "validated_clip_inventory.csv",
        args.run_dir / "gloss_validation_summary.csv",
        args.run_dir / "README.md",
    ]
    errors = [f"missing output: {path}" for path in required if not path.exists()]
    errors.extend(report.get("errors", []))
    result = {
        "run_dir": str(args.run_dir.resolve()),
        "passed": not errors and bool(report.get("passed")),
        "errors": errors,
        "candidate_rows": report.get("candidate_rows"),
        "eligible_rows": report.get("eligible_rows"),
        "readable_rate": report.get("readable_rate"),
        "split_feasibility": report.get("split_feasibility", {}),
    }
    _write_json(args.run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-C local supplementary validation")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--min-frames", type=int, default=DEFAULT_MIN_FRAMES)
    prepare_parser.add_argument("--min-per-gloss", type=int, default=20)
    prepare_parser.add_argument("--min-readable-rate", type=float, default=DEFAULT_MIN_READABLE_RATE)
    prepare_parser.add_argument(
        "--selected-gloss",
        action="append",
        default=None,
        help="Selected gloss override. Repeat for each gloss. Defaults to recommended_replacement_12_v1.csv.",
    )
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
    except (FileExistsError, FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-c-local] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
