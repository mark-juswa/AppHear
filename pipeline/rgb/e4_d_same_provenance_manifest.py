"""Prepare E4-D same-provenance Stage-E-only diagnostic manifest.

This is an experiment-only package. It uses only local supplementary rows whose
sidecar dialect is Stage-E, so train/validation/test do not mix legacy embedded
features with current extracted features. The split is diagnostic because only
two Stage-E signer sources are available for the selected seven signs.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_INVENTORY = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_audit_01/"
    "local_clip_inventory.csv"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_manifest_01"
)
DEFAULT_GLOSSES = ["BYE", "GOOD", "HELLO", "NO", "SORRY", "THANKYOU", "YES"]
TRAIN_SOURCE_FOLDER = "2"
TEST_SOURCE_FOLDER = "1"
VAL_FRACTION = 0.25

FIELDS = [
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


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _row_index(row: dict[str, str]) -> int:
    return int(row.get("repetition_index") or 0)


def _eligible_rows(inventory: Path, glosses: list[str]) -> list[dict[str, str]]:
    selected = set(glosses)
    rows = []
    for source_index, row in enumerate(_read_csv(inventory)):
        if row.get("canonical_gloss") not in selected:
            continue
        if row.get("sidecar_dialect") != "stage_e":
            continue
        if not _truthy(row.get("video_exists", "")):
            continue
        row = dict(row)
        row["source_row_index"] = str(source_index)
        rows.append(row)
    if not rows:
        raise ValueError(f"no Stage-E rows found in {inventory}")
    return rows


def _manifest_row(row: dict[str, str], split: str, class_ids: dict[str, int]) -> dict[str, Any]:
    warnings: list[str] = []
    if row.get("hand_hit_known", "").strip().lower() == "true":
        try:
            if float(row.get("hand_hit_rate") or 0.0) < 0.80:
                warnings.append("low_hand_hit_rate")
        except ValueError:
            warnings.append("invalid_hand_hit_rate")
    return {
        "sample_id": "",
        "split": split,
        "canonical_gloss": row["canonical_gloss"],
        "class_id": class_ids[row["canonical_gloss"]],
        "signer_id": row["signer_id"],
        "source_row_index": row["source_row_index"],
        "source_folder": row["source_folder"],
        "folder_word": row["folder_word"],
        "sidecar_dialect": row["sidecar_dialect"],
        "session_id": row["session_id"],
        "repetition_index": row["repetition_index"],
        "video_path": row["video_path"],
        "frame_count": row["total_frames"],
        "fps": row["native_fps"],
        "width": row["frame_width"],
        "height": row["frame_height"],
        "duration_seconds": "",
        "hand_hit_known": row["hand_hit_known"],
        "hand_hit_rate": row["hand_hit_rate"],
        "quality_score_known": row["quality_score_known"],
        "quality_score": row["quality_score"],
        "warnings": ";".join(warnings),
    }


def _split_rows(rows: list[dict[str, str]], glosses: list[str]) -> list[dict[str, Any]]:
    class_ids = {gloss: idx for idx, gloss in enumerate(sorted(glosses))}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["canonical_gloss"]].append(row)

    manifest = []
    errors = []
    for gloss in sorted(glosses):
        gloss_rows = sorted(grouped.get(gloss, []), key=lambda row: (row["source_folder"], row["signer_id"], _row_index(row)))
        train_pool = [row for row in gloss_rows if row["source_folder"] == TRAIN_SOURCE_FOLDER]
        test_pool = [row for row in gloss_rows if row["source_folder"] == TEST_SOURCE_FOLDER]
        if not train_pool:
            errors.append(f"{gloss}: no Stage-E train-source rows")
        if not test_pool:
            errors.append(f"{gloss}: no Stage-E test-source rows")
        val_count = max(1, int(round(len(train_pool) * VAL_FRACTION))) if len(train_pool) > 1 else 0
        val_rows = train_pool[-val_count:] if val_count else []
        train_rows = train_pool[:-val_count] if val_count else train_pool
        for row in train_rows:
            manifest.append(_manifest_row(row, "train", class_ids))
        for row in val_rows:
            manifest.append(_manifest_row(row, "val", class_ids))
        for row in test_pool:
            manifest.append(_manifest_row(row, "test", class_ids))

    manifest.sort(key=lambda row: (row["split"], row["canonical_gloss"], row["source_folder"], int(row["repetition_index"] or 0)))
    for idx, row in enumerate(manifest):
        row["sample_id"] = f"e4d_stagee7_{idx:05d}"
    if errors:
        raise ValueError("; ".join(errors))
    return manifest


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    split_counts = Counter(row["split"] for row in rows)
    source_counts = Counter((row["split"], row["source_folder"], row["sidecar_dialect"]) for row in rows)
    split_signers: dict[str, set[str]] = defaultdict(set)
    class_rows: dict[str, Counter[str]] = defaultdict(Counter)
    warnings = Counter()
    for row in rows:
        split_signers[row["split"]].add(row["signer_id"])
        class_rows[row["canonical_gloss"]][row["split"]] += 1
        for warning in row["warnings"].split(";"):
            if warning:
                warnings[warning] += 1
    errors = []
    for gloss, counts in class_rows.items():
        for split in ("train", "val", "test"):
            if counts[split] <= 0:
                errors.append(f"{gloss}: no {split} rows")
    return {
        "split_counts": dict(sorted(split_counts.items())),
        "split_signers": {split: sorted(values) for split, values in sorted(split_signers.items())},
        "source_counts": {f"{split}:{folder}:{dialect}": count for (split, folder, dialect), count in sorted(source_counts.items())},
        "class_rows": [
            {
                "canonical_gloss": gloss,
                "train": counts["train"],
                "val": counts["val"],
                "test": counts["test"],
            }
            for gloss, counts in sorted(class_rows.items())
        ],
        "warning_counts": dict(sorted(warnings.items())),
        "errors": errors,
    }


def _markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# E4-D Stage-E Same-Provenance Diagnostic Manifest",
            "",
            "Manifest package only. No feature extraction, training, Android change, or production recognizer change was run.",
            "",
            "## Purpose",
            "",
            "This diagnostic removes the E4-B pilot 02 provenance confound by using only Stage-E/current-pipeline local supplementary clips.",
            "",
            "## Limits",
            "",
            "- This is not production-grade because only two Stage-E signer sources are available.",
            "- Validation is split from the train-source folder, so validation is not signer-independent.",
            "- Test is held out by signer/source folder and remains the key diagnostic signal.",
            "",
            "## Summary",
            "",
            f"- Passed: {report['passed']}",
            f"- Rows: {report['manifest_rows']}",
            f"- Split counts: {report['summary']['split_counts']}",
            f"- Split signers: {report['summary']['split_signers']}",
            f"- Source counts: {report['summary']['source_counts']}",
            "",
            "## Next",
            "",
            "If accepted, prepare a runner using this manifest, extract features, and train only as a diagnostic same-provenance check.",
            "",
        ]
    )


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists() and any(args.output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {args.output}")
    rows = _eligible_rows(args.inventory, args.glosses)
    manifest = _split_rows(rows, args.glosses)
    summary = _summarize(manifest)
    report = {
        "experiment": "e4_d_stage_e_same_provenance_manifest_v1",
        "run_dir": str(args.output.resolve()),
        "inventory": str(args.inventory.resolve()),
        "selected_glosses": sorted(args.glosses),
        "manifest_rows": len(manifest),
        "policy": {
            "same_provenance": "stage_e_only",
            "train_source_folder": TRAIN_SOURCE_FOLDER,
            "test_source_folder": TEST_SOURCE_FOLDER,
            "validation_policy": f"last {VAL_FRACTION:.0%} of train-source rows per class",
            "diagnostic_not_production": True,
        },
        "summary": {key: value for key, value in summary.items() if key != "errors"},
        "errors": summary["errors"],
        "passed": not summary["errors"],
        "production_changes": "none",
        "next_required_action": "review manifest, then prepare diagnostic runner if accepted",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output / "pilot_manifest.csv", manifest, FIELDS)
    _write_csv(args.output / "class_split_summary.csv", summary["class_rows"], ["canonical_gloss", "train", "val", "test"])
    _write_json(args.output / "manifest_report.json", report)
    (args.output / "README_RUN.md").write_text(_markdown(report), encoding="utf-8")
    return report


def check(args: argparse.Namespace) -> dict[str, Any]:
    report_path = args.run_dir / "manifest_report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"missing manifest report: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    required = ["pilot_manifest.csv", "class_split_summary.csv", "README_RUN.md"]
    errors = [f"missing output: {name}" for name in required if not (args.run_dir / name).exists()]
    errors.extend(report.get("errors", []))
    result = {
        "run_dir": str(args.run_dir.resolve()),
        "passed": not errors and bool(report.get("passed")),
        "errors": errors,
        "manifest_rows": report.get("manifest_rows"),
        "summary": report.get("summary", {}),
        "policy": report.get("policy", {}),
    }
    _write_json(args.run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-D Stage-E same-provenance manifest")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--glosses", nargs="+", default=DEFAULT_GLOSSES)
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
        print(f"[rgb/e4-d-stagee] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
