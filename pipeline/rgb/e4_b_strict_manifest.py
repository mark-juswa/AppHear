"""Prepare the E4-B strict local supplementary signer-disjoint manifest.

This package uses only local supplementary signs that have at least three eligible signers.
It creates global signer-disjoint train/validation/test splits. It does not extract tensors,
train models, modify Android, or change production recognizer assets.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_VALIDATION_RUN = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_validation_strict_7_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_b_strict_7_signer_disjoint_manifest_01"
)
DEFAULT_TRAIN_SIGNER = "93EB89-S001"
DEFAULT_TEST_SIGNER = "6F7328-S001"


CHECK_FIELDS = [
    "sample_id",
    "split",
    "canonical_gloss",
    "class_id",
    "signer_id",
    "source_row_index",
    "source_folder",
    "folder_word",
    "sidecar_dialect",
    "session_id",
    "repetition_index",
    "video_path",
    "frame_count",
    "fps",
    "width",
    "height",
    "duration_seconds",
    "hand_hit_known",
    "hand_hit_rate",
    "quality_score_known",
    "quality_score",
    "warnings",
]


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


def _load_rows(validation_run: Path, exclude_low_quality: bool) -> list[dict[str, Any]]:
    path = validation_run / "validated_clip_inventory.csv"
    rows = []
    for row in _read_csv(path):
        if not _as_bool(row.get("eligible")):
            continue
        warnings = {part for part in row.get("warnings", "").split(";") if part}
        if exclude_low_quality and "low_quality_score" in warnings:
            split = "quarantine"
        else:
            split = ""
        rows.append({**row, "warnings_set": warnings, "forced_split": split})
    if not rows:
        raise ValueError(f"no eligible rows found in {path}")
    return rows


def _split_rows(rows: list[dict[str, Any]], train_signer: str, test_signer: str) -> list[dict[str, Any]]:
    glosses = sorted({row["canonical_gloss"] for row in rows})
    class_ids = {gloss: index for index, gloss in enumerate(glosses)}
    manifest = []
    for row in rows:
        if row["forced_split"] == "quarantine":
            split = "quarantine"
        elif row["signer_id"] == train_signer:
            split = "train"
        elif row["signer_id"] == test_signer:
            split = "test"
        else:
            split = "val"
        manifest.append(_manifest_row(row, split, class_ids))
    manifest.sort(
        key=lambda row: (
            row["split"],
            row["canonical_gloss"],
            row["signer_id"],
            int(row["source_row_index"]),
        )
    )
    for index, row in enumerate(manifest):
        row["sample_id"] = f"e4b_strict7_{index:05d}"
    return manifest


def _manifest_row(row: dict[str, Any], split: str, class_ids: dict[str, int]) -> dict[str, Any]:
    return {
        "sample_id": "",
        "split": split,
        "canonical_gloss": row["canonical_gloss"],
        "class_id": class_ids[row["canonical_gloss"]],
        "signer_id": row["signer_id"],
        "source_row_index": row["row_index"],
        "source_folder": row["source_folder"],
        "folder_word": row["folder_word"],
        "sidecar_dialect": row["sidecar_dialect"],
        "session_id": row["session_id"],
        "repetition_index": row["repetition_index"],
        "video_path": row["video_path"],
        "frame_count": row["probe_frame_count"],
        "fps": row["probe_fps"],
        "width": row["probe_width"],
        "height": row["probe_height"],
        "duration_seconds": row["probe_duration_seconds"],
        "hand_hit_known": row["hand_hit_known"],
        "hand_hit_rate": row["hand_hit_rate"],
        "quality_score_known": row["quality_score_known"],
        "quality_score": row["quality_score"],
        "warnings": ";".join(sorted(row["warnings_set"])),
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    split_counts = Counter(row["split"] for row in rows)
    split_signers: dict[str, set[str]] = defaultdict(set)
    gloss_split: dict[str, Counter[str]] = defaultdict(Counter)
    warning_counts: Counter[str] = Counter()
    for row in rows:
        if row["split"] != "quarantine":
            split_signers[row["split"]].add(row["signer_id"])
        gloss_split[row["canonical_gloss"]][row["split"]] += 1
        for warning in row["warnings"].split(";"):
            if warning:
                warning_counts[warning] += 1

    class_rows = []
    errors = []
    for gloss in sorted(gloss_split):
        counts = gloss_split[gloss]
        if counts["train"] <= 0:
            errors.append(f"{gloss}: no train rows")
        if counts["val"] <= 0:
            errors.append(f"{gloss}: no val rows")
        if counts["test"] <= 0:
            errors.append(f"{gloss}: no test rows")
        class_rows.append(
            {
                "canonical_gloss": gloss,
                "train": counts["train"],
                "val": counts["val"],
                "test": counts["test"],
                "quarantine": counts["quarantine"],
            }
        )

    active_splits = {split: signers for split, signers in split_signers.items() if split in {"train", "val", "test"}}
    for left in active_splits:
        for right in active_splits:
            if left >= right:
                continue
            overlap = active_splits[left] & active_splits[right]
            if overlap:
                errors.append(f"signer leakage {left}<->{right}: {sorted(overlap)}")

    return {
        "split_counts": dict(sorted(split_counts.items())),
        "split_signers": {split: sorted(signers) for split, signers in sorted(active_splits.items())},
        "class_rows": class_rows,
        "warning_counts": dict(sorted(warning_counts.items())),
        "errors": errors,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# E4-B Strict 7-Sign Manifest Package",
        "",
        "Manifest/split package only. No tensor extraction or training was run.",
        "",
        f"- Passed: {report['passed']}",
        f"- Rows: {report['manifest_rows']}",
        f"- Split policy: `{report['split_policy']['policy']}`",
        f"- Split counts: {report['summary']['split_counts']}",
        f"- Split signers: {report['summary']['split_signers']}",
        "",
        "## Why This Split",
        "",
        "This strict package drops the six two-signer classes and keeps only the signs with at least three eligible signers. It uses globally signer-disjoint train, validation, and test splits. This is cleaner than the 12-sign local pilot, but still small because each class has only one signer per split.",
        "",
        "## Next",
        "",
        "Review this manifest before any extraction or training. If accepted, prepare a bounded E4-B runner that consumes `pilot_manifest.csv` and keeps outputs isolated.",
        "",
    ]
    if report["errors"]:
        lines.extend(["## Errors", ""])
        lines.extend(f"- {error}" for error in report["errors"])
    return "\n".join(lines)


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists() and any(args.output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {args.output}")
    source_rows = _load_rows(args.validation_run, args.exclude_low_quality)
    manifest = _split_rows(source_rows, args.train_signer, args.test_signer)
    summary = _summarize(manifest)
    errors = list(summary["errors"])
    if summary["split_counts"].get("train", 0) <= 0:
        errors.append("no train rows")
    if summary["split_counts"].get("val", 0) <= 0:
        errors.append("no val rows")
    if summary["split_counts"].get("test", 0) <= 0:
        errors.append("no test rows")

    report = {
        "experiment": "e4_b_strict_7_signer_disjoint_manifest_v1",
        "validation_run": str(args.validation_run.resolve()),
        "run_dir": str(args.output.resolve()),
        "manifest_rows": len(manifest),
        "split_policy": {
            "policy": "global_signer_disjoint_train_val_test",
            "train_signer": args.train_signer,
            "test_signer": args.test_signer,
            "validation_signers": sorted(summary["split_signers"].get("val", [])),
            "exclude_low_quality": args.exclude_low_quality,
        },
        "summary": {key: value for key, value in summary.items() if key not in {"class_rows", "errors"}},
        "errors": errors,
        "passed": not errors,
        "production_changes": "none",
        "next_required_action": "review strict manifest before extraction or training",
    }

    args.output.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output / "pilot_manifest.csv", manifest, CHECK_FIELDS)
    _write_csv(
        args.output / "class_split_summary.csv",
        summary["class_rows"],
        ["canonical_gloss", "train", "val", "test", "quarantine"],
    )
    _write_json(args.output / "manifest_report.json", report)
    (args.output / "README_RUN.md").write_text(_markdown(report), encoding="utf-8")
    return report


def check(args: argparse.Namespace) -> dict[str, Any]:
    report_path = args.run_dir / "manifest_report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"missing manifest report: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    required = [
        args.run_dir / "pilot_manifest.csv",
        args.run_dir / "class_split_summary.csv",
        args.run_dir / "README_RUN.md",
    ]
    errors = [f"missing output: {path}" for path in required if not path.exists()]
    errors.extend(report.get("errors", []))
    result = {
        "run_dir": str(args.run_dir.resolve()),
        "passed": not errors and bool(report.get("passed")),
        "errors": errors,
        "manifest_rows": report.get("manifest_rows"),
        "split_policy": report.get("split_policy", {}),
        "split_counts": report.get("summary", {}).get("split_counts", {}),
        "split_signers": report.get("summary", {}).get("split_signers", {}),
        "warning_counts": report.get("summary", {}).get("warning_counts", {}),
    }
    _write_json(args.run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-B strict 7-sign manifest package")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--validation-run", type=Path, default=DEFAULT_VALIDATION_RUN)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--train-signer", default=DEFAULT_TRAIN_SIGNER)
    prepare_parser.add_argument("--test-signer", default=DEFAULT_TEST_SIGNER)
    prepare_parser.add_argument("--exclude-low-quality", action="store_true", default=True)
    prepare_parser.add_argument("--include-low-quality", dest="exclude_low_quality", action="store_false")
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
        print(f"[rgb/e4-b-strict] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())