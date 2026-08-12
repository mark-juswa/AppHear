"""Audit historical P1 footage for E6 negative-context reuse.

This module performs lineage and annotation accounting only. It does not
extract features, train models, export assets, or modify Android.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

TARGETS = {
    "N0_NO_HAND": 150,
    "P1_IDLE_HANDS": 200,
    "P1_FACE_ADJACENT": 200,
    "P1_ACCIDENTAL_MOTION": 150,
    "OOV_SIGN": 200,
    "TRANSITION_PARTIAL": 100,
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _load_run(run_dir: Path, source_name: str) -> dict[str, Any]:
    required = ["capture_manifest.csv", "reviewed_manifest.csv", "gold_review.csv"]
    missing = [name for name in required if not (run_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"{run_dir}: missing {missing}")

    captures = _read_csv(run_dir / "capture_manifest.csv")
    reviewed = _read_csv(run_dir / "reviewed_manifest.csv")
    gold = {row["sample_id"]: row for row in _read_csv(run_dir / "gold_review.csv")}
    capture_by_clip = {row["clip_id"]: row for row in captures}
    if len(capture_by_clip) != len(captures):
        raise ValueError(f"{run_dir}: duplicate clip_id in capture manifest")

    for row in reviewed:
        if row.get("clip_id") not in capture_by_clip:
            raise ValueError(f"{run_dir}: unknown clip_id {row.get('clip_id')}")
        if row.get("sample_id") not in gold:
            raise ValueError(f"{run_dir}: missing gold row {row.get('sample_id')}")

    return {
        "source_name": source_name,
        "run_dir": run_dir.resolve(),
        "captures": captures,
        "capture_by_clip": capture_by_clip,
        "reviewed": reviewed,
        "gold": gold,
    }


def _canonical_capture_index(run: dict[str, Any]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in run["captures"]:
        digest = row["sha256"].lower()
        if digest in result:
            raise ValueError(f"canonical run repeats raw hash {digest}")
        result[digest] = row
    return result


def _lineage_rows(
    runs: list[dict[str, Any]], canonical: dict[str, dict[str, str]]
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for run in runs:
        for capture in run["captures"]:
            path = Path(capture["video_path"])
            recorded_hash = capture["sha256"].lower()
            actual_hash = _sha256(path) if path.is_file() else ""
            keeper = canonical.get(recorded_hash)
            if not path.is_file():
                errors.append(f"missing raw video: {path}")
            elif actual_hash != recorded_hash:
                errors.append(f"hash mismatch: {path}")
            if keeper is None:
                errors.append(f"no canonical P1 source for hash: {recorded_hash}")
            rows.append(
                {
                    "source_run": run["source_name"],
                    "presented_path": str(path.resolve()),
                    "recorded_sha256": recorded_hash,
                    "actual_sha256": actual_hash,
                    "hash_verified": actual_hash == recorded_hash,
                    "canonical_path": keeper.get("video_path", "") if keeper else "",
                    "canonical_participant_id": keeper.get("participant_id", "") if keeper else "",
                    "presented_participant_id": capture.get("participant_id", ""),
                    "lineage_status": (
                        "canonical_keeper"
                        if run["source_name"] == "P1_CANONICAL"
                        else "duplicate_alias_excluded"
                    ),
                    "participant_alias_is_stale": bool(
                        keeper and keeper.get("participant_id") != capture.get("participant_id")
                    ),
                }
            )
    return rows, errors


def _merge_windows(
    runs: list[dict[str, Any]], canonical: dict[str, dict[str, str]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    merged: dict[tuple[str, int], dict[str, Any]] = {}
    eligible_source_rows = Counter()
    for run in runs:
        for row in run["reviewed"]:
            if not _bool(row.get("eligible", "")):
                continue
            eligible_source_rows[run["source_name"]] += 1
            capture = run["capture_by_clip"][row["clip_id"]]
            digest = capture["sha256"].lower()
            keeper = canonical[digest]
            frame_index = int(row["frame_index"])
            key = (digest, frame_index)
            gold = run["gold"][row["sample_id"]]
            evidence = merged.setdefault(
                key,
                {
                    "raw_video_sha256": digest,
                    "frame_index": frame_index,
                    "timestamp_ms": int(row["timestamp_ms"]),
                    "canonical_clip_id": keeper["clip_id"],
                    "canonical_raw_video_path": keeper["video_path"],
                    "canonical_participant_id": keeper["participant_id"],
                    "device_id": keeper["device_id"],
                    "environment_id": keeper["environment_id"],
                    "camera_facing": keeper["camera_facing"],
                    "sources": [],
                    "sample_ids": [],
                    "near_face_votes": [],
                },
            )
            evidence["sources"].append(run["source_name"])
            evidence["sample_ids"].append(row["sample_id"])
            evidence["near_face_votes"].append(_bool(gold.get("near_face", "")))

    rows: list[dict[str, Any]] = []
    disagreement_count = 0
    for key in sorted(merged):
        evidence = merged[key]
        votes = evidence.pop("near_face_votes")
        disagreement_count += int(len(set(votes)) > 1)
        subtype = "P1_FACE_ADJACENT" if any(votes) else "P1_IDLE_HANDS"
        participant = evidence["canonical_participant_id"]
        rows.append(
            {
                **evidence,
                "source_runs": ";".join(sorted(set(evidence.pop("sources")))),
                "source_sample_ids": ";".join(evidence.pop("sample_ids")),
                "negative_subtype": subtype,
                "review_status": "accepted_historical_development",
                "proposed_split": (
                    "train_development" if participant == "P01" else "val_reused_diagnostic"
                ),
                "fresh_evaluation_eligible": False,
                "previous_experiment_usage": "E2e-C0;E4-AA;E4-AG;E4-E5 gate diagnostics",
                "notes": (
                    "Near-face wins when duplicate reviews disagree. Historical footage only; "
                    "same raw clip must never cross splits."
                ),
            }
        )
    diagnostics = {
        "eligible_source_rows": dict(eligible_source_rows),
        "unique_reusable_windows": len(rows),
        "overlapping_review_windows": sum(len(row["source_runs"].split(";")) > 1 for row in rows),
        "near_face_annotation_disagreements": disagreement_count,
    }
    return rows, diagnostics


def _coverage_rows(windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(row["negative_subtype"] for row in windows)
    credits = {"N0_NO_HAND": 150, **counts}
    rows = []
    for subtype, target in TARGETS.items():
        accepted = min(target, int(credits.get(subtype, 0)))
        rows.append(
            {
                "negative_subtype": subtype,
                "target_windows": target,
                "accepted_historical_development_windows": accepted,
                "fresh_evaluation_windows": 0,
                "remaining_volume_gap": target - accepted,
                "remaining_fresh_evaluation_gap": "required",
                "decision": (
                    "historical_development_reuse_only"
                    if accepted
                    else "new_or_other_validated_source_required"
                ),
            }
        )
    return rows


def build(args: argparse.Namespace) -> int:
    canonical_run = _load_run(args.p1_run, "P1_CANONICAL")
    alias_run = _load_run(args.e4ag_run, "E4AG_DUPLICATE_ALIAS")
    canonical = _canonical_capture_index(canonical_run)
    lineage, lineage_errors = _lineage_rows([canonical_run, alias_run], canonical)
    windows, diagnostics = _merge_windows([canonical_run, alias_run], canonical)
    coverage = _coverage_rows(windows)

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "raw_video_lineage.csv", lineage, list(lineage[0]))
    _write_csv(output / "reusable_windows.csv", windows, list(windows[0]))
    _write_csv(output / "coverage_recalculation.csv", coverage, list(coverage[0]))

    duplicate_hashes = sum(
        count > 1 for count in Counter(row["recorded_sha256"] for row in lineage).values()
    )
    stale_aliases = sum(_bool(str(row["participant_alias_is_stale"])) for row in lineage)
    subtype_counts = Counter(row["negative_subtype"] for row in windows)
    remaining = sum(int(row["remaining_volume_gap"]) for row in coverage)
    summary = {
        "experiment": "e6_negative_context_reuse_audit_v1",
        "scope": "lineage/review reuse only; no extraction or modeling",
        "raw_presentations": len(lineage),
        "unique_raw_videos": len(canonical),
        "duplicate_raw_hash_groups": duplicate_hashes,
        "stale_participant_alias_rows": stale_aliases,
        **diagnostics,
        "accepted_by_subtype": dict(sorted(subtype_counts.items())),
        "n0_credit_carried_forward": 150,
        "target_windows_total": sum(TARGETS.values()),
        "accepted_historical_development_total": sum(TARGETS.values()) - remaining,
        "remaining_volume_gap": remaining,
        "fresh_evaluation_coverage": 0,
        "lineage_errors": lineage_errors,
        "passed": not lineage_errors
        and len(windows) == len({(r["raw_video_sha256"], r["frame_index"]) for r in windows}),
        "decision": "reuse_for_development_only_collect_fresh_evaluation_and_missing_subtypes",
    }
    _write_json(output / "reuse_audit_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


def check(args: argparse.Namespace) -> int:
    required = [
        "raw_video_lineage.csv",
        "reusable_windows.csv",
        "coverage_recalculation.csv",
        "reuse_audit_summary.json",
    ]
    errors = [name for name in required if not (args.run_dir / name).is_file()]
    summary = {}
    if not errors:
        summary = json.loads(
            (args.run_dir / "reuse_audit_summary.json").read_text(encoding="utf-8")
        )
        if not summary.get("passed"):
            errors.append("reuse audit summary did not pass")
        if summary.get("unique_reusable_windows") != 197:
            errors.append("expected 197 unique reviewed historical windows")
        if summary.get("remaining_volume_gap") != 653:
            errors.append("expected recalculated remaining volume gap of 653")
        if summary.get("fresh_evaluation_coverage") != 0:
            errors.append("historical sources must not receive fresh-evaluation credit")
    report = {"run_dir": str(args.run_dir.resolve()), "passed": not errors, "errors": errors}
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build")
    build_parser.add_argument(
        "--p1-run", type=Path, default=Path("artifacts/recognition_upgrade/e2e_c0/p1_capture_03")
    )
    build_parser.add_argument(
        "--e4ag-run",
        type=Path,
        default=Path("artifacts/recognition_upgrade/e2e_c0/hello_like_p1_capture_01"),
    )
    build_parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/recognition_upgrade/product_core_data_readiness/e6_negative_reuse_audit_01"
        ),
    )
    build_parser.set_defaults(func=build)
    check_parser = commands.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.set_defaults(func=check)
    return root


def main() -> int:
    args = parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
