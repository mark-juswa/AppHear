"""Prepare the E4-B local supplementary manifest/split package.

This is a planning/package step only. It converts the validated E4-C local supplementary
inventory into an explicit, reviewed manifest for a bounded E4-B pilot. It does not extract
features, train models, modify Android, or change production recognizer assets.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_VALIDATION_RUN = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_validation_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_b_local_supplementary_manifest_01"
)
DEFAULT_TEST_SIGNER = "6F7328-S001"
DEFAULT_SEED = 300730


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


def _load_eligible_rows(validation_run: Path, exclude_low_quality: bool) -> list[dict[str, Any]]:
    path = validation_run / "validated_clip_inventory.csv"
    rows: list[dict[str, Any]] = []
    for row in _read_csv(path):
        if not _as_bool(row.get("eligible")):
            continue
        warnings = {part for part in row.get("warnings", "").split(";") if part}
        quarantine = bool(exclude_low_quality and "low_quality_score" in warnings)
        rows.append({**row, "warnings_set": warnings, "quarantine": quarantine})
    if not rows:
        raise ValueError(f"no eligible rows found in {path}")
    return rows


def _select_test_signer(rows: list[dict[str, Any]], requested: str) -> str:
    by_signer_glosses: dict[str, set[str]] = defaultdict(set)
    all_glosses = {row["canonical_gloss"] for row in rows if not row["quarantine"]}
    for row in rows:
        if not row["quarantine"]:
            by_signer_glosses[row["signer_id"]].add(row["canonical_gloss"])
    if requested in by_signer_glosses and by_signer_glosses[requested] == all_glosses:
        return requested
    full_coverage = sorted(
        signer for signer, glosses in by_signer_glosses.items() if glosses == all_glosses
    )
    if not full_coverage:
        raise ValueError("no non-quarantined signer covers every selected class for test")
    return full_coverage[0]


def _split_rows(
    rows: list[dict[str, Any]],
    test_signer: str,
    val_fraction: float,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    manifest: list[dict[str, Any]] = []
    class_ids = {gloss: index for index, gloss in enumerate(sorted({r["canonical_gloss"] for r in rows}))}

    for row in rows:
        if row["quarantine"]:
            split = "quarantine"
        elif row["signer_id"] == test_signer:
            split = "test"
        else:
            grouped[(row["canonical_gloss"], row["signer_id"])].append(row)
            continue
        manifest.append(_manifest_row(row, split, class_ids))

    for (_gloss, _signer), items in sorted(grouped.items()):
        shuffled = list(items)
        rng.shuffle(shuffled)
        val_count = max(1, round(len(shuffled) * val_fraction)) if len(shuffled) >= 5 else 0
        for index, row in enumerate(shuffled):
            split = "val_internal" if index < val_count else "train"
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
        row["sample_id"] = f"e4b_local_{index:05d}"
    return manifest


def _manifest_row(row: dict[str, Any], split: str, class_ids: dict[str, int]) -> dict[str, Any]:
    warnings = ";".join(sorted(row["warnings_set"]))
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
        "warnings": warnings,
    }


def _summarize_manifest(rows: list[dict[str, Any]], test_signer: str) -> dict[str, Any]:
    split_counts = Counter(row["split"] for row in rows)
    gloss_split: dict[str, Counter[str]] = defaultdict(Counter)
    signer_split: dict[str, Counter[str]] = defaultdict(Counter)
    train_signers_by_gloss: dict[str, set[str]] = defaultdict(set)
    test_signers_by_gloss: dict[str, set[str]] = defaultdict(set)
    warning_counts: Counter[str] = Counter()
    for row in rows:
        gloss_split[row["canonical_gloss"]][row["split"]] += 1
        signer_split[row["signer_id"]][row["split"]] += 1
        for warning in row["warnings"].split(";"):
            if warning:
                warning_counts[warning] += 1
        if row["split"] in {"train", "val_internal"}:
            train_signers_by_gloss[row["canonical_gloss"]].add(row["signer_id"])
        if row["split"] == "test":
            test_signers_by_gloss[row["canonical_gloss"]].add(row["signer_id"])

    class_rows = []
    errors = []
    for gloss in sorted(gloss_split):
        counts = gloss_split[gloss]
        train_like = counts["train"] + counts["val_internal"]
        test = counts["test"]
        train_signers = sorted(train_signers_by_gloss.get(gloss, set()))
        test_signers = sorted(test_signers_by_gloss.get(gloss, set()))
        if train_like <= 0:
            errors.append(f"{gloss}: no train/val_internal rows")
        if test <= 0:
            errors.append(f"{gloss}: no held-out test rows")
        if set(train_signers) & set(test_signers):
            errors.append(f"{gloss}: signer leakage between train-like and test")
        class_rows.append(
            {
                "canonical_gloss": gloss,
                "train": counts["train"],
                "val_internal": counts["val_internal"],
                "test": counts["test"],
                "quarantine": counts["quarantine"],
                "train_like_signer_count": len(train_signers),
                "train_like_signers": ";".join(train_signers),
                "test_signers": ";".join(test_signers),
            }
        )

    return {
        "split_counts": dict(sorted(split_counts.items())),
        "test_signer": test_signer,
        "class_rows": class_rows,
        "signer_split_counts": {
            signer: dict(sorted(counts.items())) for signer, counts in sorted(signer_split.items())
        },
        "warning_counts": dict(sorted(warning_counts.items())),
        "errors": errors,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# E4-B Local Supplementary Manifest Package",
        "",
        "Manifest/split package only. No tensor extraction or training was run.",
        "",
        f"- Passed: {report['passed']}",
        f"- Rows: {report['manifest_rows']}",
        f"- Test signer: `{report['split_policy']['test_signer']}`",
        f"- Split policy: `{report['split_policy']['policy']}`",
        f"- Split counts: {report['summary']['split_counts']}",
        "",
        "## Why This Split",
        "",
        "The local supplementary set has only four signer IDs, and six selected signs have only two eligible signers. The package therefore uses one signer held out for test and an internal validation split carved from the remaining training signers. This is a practical engineering pilot, not a production-ready three-way signer-disjoint benchmark.",
        "",
        "## Next",
        "",
        "Review this manifest package before extraction/training. If accepted, the next task is to prepare a bounded E4-B training runner that consumes `pilot_manifest.csv` without changing Android or production assets.",
        "",
    ]
    if report["errors"]:
        lines.extend(["## Errors", ""])
        lines.extend(f"- {error}" for error in report["errors"])
        lines.append("")
    return "\n".join(lines)


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists() and any(args.output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {args.output}")
    rows = _load_eligible_rows(args.validation_run, exclude_low_quality=args.exclude_low_quality)
    test_signer = _select_test_signer(rows, args.test_signer)
    manifest = _split_rows(rows, test_signer, args.val_fraction, args.seed)
    summary = _summarize_manifest(manifest, test_signer)
    errors = list(summary["errors"])
    if summary["split_counts"].get("test", 0) <= 0:
        errors.append("no held-out test rows")
    if summary["split_counts"].get("train", 0) <= 0:
        errors.append("no train rows")
    if summary["split_counts"].get("val_internal", 0) <= 0:
        errors.append("no internal validation rows")

    report = {
        "experiment": "e4_b_local_supplementary_manifest_v1",
        "validation_run": str(args.validation_run.resolve()),
        "run_dir": str(args.output.resolve()),
        "manifest_rows": len(manifest),
        "split_policy": {
            "policy": "two_way_held_out_signer_with_internal_validation",
            "test_signer": test_signer,
            "val_fraction_from_non_test_signers": args.val_fraction,
            "exclude_low_quality": args.exclude_low_quality,
            "seed": args.seed,
        },
        "summary": {
            key: value for key, value in summary.items() if key not in {"class_rows", "errors"}
        },
        "errors": errors,
        "passed": not errors,
        "production_changes": "none",
        "next_required_action": "review manifest package before any extraction or training",
    }

    args.output.mkdir(parents=True, exist_ok=True)
    _write_csv(
        args.output / "pilot_manifest.csv",
        manifest,
        [
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
        ],
    )
    _write_csv(
        args.output / "class_split_summary.csv",
        summary["class_rows"],
        [
            "canonical_gloss",
            "train",
            "val_internal",
            "test",
            "quarantine",
            "train_like_signer_count",
            "train_like_signers",
            "test_signers",
        ],
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
        "warning_counts": report.get("summary", {}).get("warning_counts", {}),
    }
    _write_json(args.run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-B local supplementary manifest package")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--validation-run", type=Path, default=DEFAULT_VALIDATION_RUN)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--test-signer", default=DEFAULT_TEST_SIGNER)
    prepare_parser.add_argument("--val-fraction", type=float, default=0.2)
    prepare_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
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
        print(f"[rgb/e4-b-local] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
