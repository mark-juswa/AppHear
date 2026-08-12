"""Build the E6 five-sign signer-disjoint assignment package.

This is a data-assignment gate only. It does not extract features, train a
model, export TFLite, or modify Android/production assets.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


EXPERIMENT = "e6_five_sign_assignment_v1"
MANIFEST_VERSION = "apphear_assignment_manifest_v1"
VOCABULARY = ["GOOD", "HELLO", "SORRY", "HAVE", "KNOW"]
LEAN_DEVELOPMENT_NEGATIVE_TARGET = 547
FRESH_NEGATIVE_TARGET = 560

DEFAULT_POSITIVE_MANIFEST = Path(
    "artifacts/recognition_upgrade/product_core_data_readiness/"
    "e6_collection_integration_01/manifest.csv"
)
DEFAULT_N0_RUN = Path("artifacts/recognition_upgrade/e2e_c0/n0_capture_06")
DEFAULT_P1_WINDOWS = Path(
    "artifacts/recognition_upgrade/product_core_data_readiness/"
    "e6_negative_reuse_audit_01/reusable_windows.csv"
)
DEFAULT_OOV_MANIFEST = Path(
    "artifacts/recognition_upgrade/product_core_data_readiness/"
    "e6_existing_negative_source_search_01/asl_citizen_oov_manifest.csv"
)
DEFAULT_FRESH_NEGATIVE = Path(
    "artifacts/recognition_upgrade/product_core_data_readiness/"
    "e6_negative_upload_review_01/accepted_fresh_negative_manifest.csv"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/product_core_data_readiness/"
    "e6_five_sign_assignment_01"
)

FIELDS = [
    "assignment_version",
    "assignment_id",
    "sample_kind",
    "canonical_label",
    "negative_subtype",
    "role",
    "evaluation_freshness",
    "source_dataset",
    "source_row_id",
    "signer_group_id",
    "raw_video_path",
    "raw_video_sha256",
    "frame_index",
    "timestamp_ms",
    "lineage_source",
    "schema_version",
    "previous_experiment_usage",
    "notes",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _positive_role(split: str) -> tuple[str, str]:
    mapping = {
        "train": ("train_positive", "development"),
        "val": ("validation_positive", "development"),
        "test_source_holdout": ("test_positive_historical", "historical_reused"),
        "test_fresh": ("test_positive_fresh", "fresh"),
    }
    if split not in mapping:
        raise ValueError(f"unsupported accepted positive split: {split!r}")
    return mapping[split]


def _positive_rows(path: Path) -> list[dict[str, Any]]:
    result = []
    for row in _read_csv(path):
        if row.get("canonical_gloss") not in VOCABULARY:
            continue
        if row.get("label_status") != "verified" or row.get("quality_status") != "usable":
            continue
        if row.get("split") == "exclude":
            continue
        role, freshness = _positive_role(row.get("split", ""))
        result.append(
            {
                "assignment_version": MANIFEST_VERSION,
                "assignment_id": f"positive:{row['row_id']}",
                "sample_kind": "positive",
                "canonical_label": row["canonical_gloss"],
                "negative_subtype": "",
                "role": role,
                "evaluation_freshness": freshness,
                "source_dataset": row.get("source", ""),
                "source_row_id": row.get("row_id", ""),
                "signer_group_id": row.get("signer_group_id", ""),
                "raw_video_path": row.get("raw_video_path", ""),
                "raw_video_sha256": row.get("raw_video_sha256", "").upper(),
                "frame_index": "",
                "timestamp_ms": "",
                "lineage_source": str(path.resolve()),
                "schema_version": "3.0",
                "previous_experiment_usage": row.get("previous_experiment_usage", ""),
                "notes": row.get("split_reason", ""),
            }
        )
    return result


def _n0_rows(run_dir: Path) -> list[dict[str, Any]]:
    reviewed_path = run_dir / "reviewed_manifest.csv"
    capture_path = run_dir / "capture_manifest.csv"
    captures = {row["clip_id"]: row for row in _read_csv(capture_path)}
    eligible = [row for row in _read_csv(reviewed_path) if row.get("eligible", "").lower() == "true"]
    eligible.sort(key=lambda row: row["sample_id"])
    selected = eligible[:150]
    if len(selected) != 150:
        raise ValueError(f"expected at least 150 eligible N0 rows, found {len(eligible)}")
    result = []
    for row in selected:
        capture = captures.get(row["clip_id"])
        if not capture:
            raise ValueError(f"N0 row {row['sample_id']} has no capture lineage")
        result.append(
            {
                "assignment_version": MANIFEST_VERSION,
                "assignment_id": f"negative:n0:{row['sample_id']}",
                "sample_kind": "negative_context",
                "canonical_label": "NO_SIGN",
                "negative_subtype": "N0_NO_HAND",
                "role": "development_negative",
                "evaluation_freshness": "historical_reused",
                "source_dataset": "APPHEAR_N0_CAPTURE",
                "source_row_id": row["sample_id"],
                "signer_group_id": f"negative_capture:{row['participant_id']}",
                "raw_video_path": capture["video_path"],
                "raw_video_sha256": capture["sha256"].upper(),
                "frame_index": row["frame_index"],
                "timestamp_ms": row["timestamp_ms"],
                "lineage_source": str(reviewed_path.resolve()),
                "schema_version": "3.0",
                "previous_experiment_usage": "E2e-C0 N0 reviewed evidence",
                "notes": "deterministic first 150 eligible rows; lean pilot development credit",
            }
        )
    return result


def _p1_rows(path: Path) -> list[dict[str, Any]]:
    result = []
    for row in _read_csv(path):
        if row.get("review_status") != "accepted_historical_development":
            continue
        result.append(
            {
                "assignment_version": MANIFEST_VERSION,
                "assignment_id": f"negative:p1:{row['raw_video_sha256']}:{row['frame_index']}",
                "sample_kind": "negative_context",
                "canonical_label": "NO_SIGN",
                "negative_subtype": row["negative_subtype"],
                "role": "development_negative",
                "evaluation_freshness": "historical_reused",
                "source_dataset": "APPHEAR_P1_CAPTURE",
                "source_row_id": row.get("sample_ids", ""),
                "signer_group_id": f"negative_capture:{row['canonical_participant_id']}",
                "raw_video_path": row["canonical_raw_video_path"],
                "raw_video_sha256": row["raw_video_sha256"].upper(),
                "frame_index": row["frame_index"],
                "timestamp_ms": row["timestamp_ms"],
                "lineage_source": str(path.resolve()),
                "schema_version": "3.0",
                "previous_experiment_usage": row.get("previous_experiment_usage", ""),
                "notes": row.get("notes", ""),
            }
        )
    return result


def _oov_rows(path: Path) -> list[dict[str, Any]]:
    result = []
    for row in _read_csv(path):
        result.append(
            {
                "assignment_version": MANIFEST_VERSION,
                "assignment_id": f"negative:oov:{row['row_id']}",
                "sample_kind": "negative_context",
                "canonical_label": "UNKNOWN_SIGN",
                "negative_subtype": "OOV_SIGN",
                "role": "development_negative",
                "evaluation_freshness": "historical_reused",
                "source_dataset": "ASL_CITIZEN",
                "source_row_id": row["row_id"],
                "signer_group_id": f"asl_citizen:{row['participant_id']}",
                "raw_video_path": row["raw_video_path"],
                "raw_video_sha256": row["raw_video_sha256"].upper(),
                "frame_index": "",
                "timestamp_ms": "",
                "lineage_source": str(path.resolve()),
                "schema_version": "3.0",
                "previous_experiment_usage": row.get("previous_experiment_usage", ""),
                "notes": row.get("label_rationale", ""),
            }
        )
    return result


def _fresh_negative_rows(path: Path) -> list[dict[str, Any]]:
    result = []
    for row in _read_csv(path):
        if row.get("final_status") != "accepted_fresh_negative_evaluation":
            continue
        subtype = row["canonical_subtype"]
        result.append(
            {
                "assignment_version": MANIFEST_VERSION,
                "assignment_id": f"negative:fresh:{row['row_id']}",
                "sample_kind": "negative_context",
                "canonical_label": "UNKNOWN_SIGN" if subtype == "OOV_SIGN" else "NO_SIGN",
                "negative_subtype": subtype,
                "role": "test_negative_fresh_provisional",
                "evaluation_freshness": "fresh_single_signer_provisional",
                "source_dataset": row["source_dataset"],
                "source_row_id": row["row_id"],
                "signer_group_id": f"negative_capture:{row['signer_id']}",
                "raw_video_path": row["raw_video_path"],
                "raw_video_sha256": row["raw_video_sha256"].upper(),
                "frame_index": "",
                "timestamp_ms": "",
                "lineage_source": str(path.resolve()),
                "schema_version": "3.0",
                "previous_experiment_usage": row.get("previous_experiment_usage_exact", ""),
                "notes": "short-event evidence; evaluation only; no development gap credit",
            }
        )
    return result


def _gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    assignment_ids = [row["assignment_id"] for row in rows]
    if len(assignment_ids) != len(set(assignment_ids)):
        errors.append("duplicate assignment_id")

    missing_lineage = [
        row["assignment_id"]
        for row in rows
        if not row["raw_video_path"] or not row["raw_video_sha256"] or not row["signer_group_id"]
    ]
    if missing_lineage:
        errors.append(f"missing required lineage in {len(missing_lineage)} rows")
    missing_raw_files = [
        row["assignment_id"] for row in rows if not Path(row["raw_video_path"]).is_file()
    ]
    if missing_raw_files:
        errors.append(f"raw video missing for {len(missing_raw_files)} rows")

    positives = [row for row in rows if row["sample_kind"] == "positive"]
    development_negative = [row for row in rows if row["role"] == "development_negative"]
    fresh_negative = [row for row in rows if row["role"] == "test_negative_fresh_provisional"]
    if set(row["canonical_label"] for row in positives) != set(VOCABULARY):
        errors.append("positive vocabulary does not exactly match approved five signs")
    if len(development_negative) != LEAN_DEVELOPMENT_NEGATIVE_TARGET:
        errors.append(
            f"development negatives={len(development_negative)}, expected {LEAN_DEVELOPMENT_NEGATIVE_TARGET}"
        )
    if len(fresh_negative) != FRESH_NEGATIVE_TARGET:
        errors.append(f"fresh negatives={len(fresh_negative)}, expected {FRESH_NEGATIVE_TARGET}")

    roles_by_signer: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        roles_by_signer[row["signer_group_id"]].add(row["role"])
    forbidden_role_pairs = [
        {"train_positive", "validation_positive"},
        {"train_positive", "test_positive_historical"},
        {"train_positive", "test_positive_fresh"},
        {"validation_positive", "test_positive_historical"},
        {"validation_positive", "test_positive_fresh"},
        {"test_positive_historical", "test_positive_fresh"},
        {"development_negative", "test_negative_fresh_provisional"},
    ]
    signer_leakage = []
    for signer, roles in roles_by_signer.items():
        if any(pair <= roles for pair in forbidden_role_pairs):
            signer_leakage.append({"signer_group_id": signer, "roles": sorted(roles)})
    if signer_leakage:
        errors.append(f"signer role leakage in {len(signer_leakage)} signer groups")

    roles_by_hash: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        roles_by_hash[row["raw_video_sha256"]].add(row["role"])
    hash_leakage = [
        {"raw_video_sha256": digest, "roles": sorted(roles)}
        for digest, roles in roles_by_hash.items()
        if len(roles) > 1
    ]
    if hash_leakage:
        errors.append(f"raw-video hash crosses roles in {len(hash_leakage)} groups")

    fresh_signers = sorted({row["signer_group_id"] for row in fresh_negative})
    if len(fresh_signers) != 1:
        errors.append(f"expected one provisional fresh-negative signer, found {len(fresh_signers)}")

    role_counts = Counter(row["role"] for row in rows)
    positive_counts = defaultdict(Counter)
    positive_signers: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for row in positives:
        positive_counts[row["canonical_label"]][row["role"]] += 1
        positive_signers[row["canonical_label"]][row["role"]].add(
            row["signer_group_id"]
        )

    have_validation_count = positive_counts["HAVE"]["validation_positive"]
    if have_validation_count < 20:
        warnings.append(
            f"HAVE validation has only {have_validation_count} clips; class-level "
            "validation is pilot evidence and must not support a production claim"
        )
    warnings.extend(
        [
            "The 1,000-development-negative target is an unverified engineering target; "
            "this pilot waives the remaining 453 rows.",
            "Fresh negative evaluation contains one signer and short-event clips only.",
            "Signer namespaces are source-scoped; cross-source human identity equivalence "
            "cannot be proven from current metadata.",
        ]
    )

    passed = not errors
    return {
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
        "assignment_rows": len(rows),
        "positive_rows": len(positives),
        "development_negative_rows": len(development_negative),
        "fresh_negative_rows": len(fresh_negative),
        "role_counts": dict(sorted(role_counts.items())),
        "positive_counts_by_sign_and_role": {
            sign: dict(sorted(counts.items())) for sign, counts in sorted(positive_counts.items())
        },
        "positive_signers_by_sign_and_role": {
            sign: {role: len(signers) for role, signers in sorted(roles.items())}
            for sign, roles in sorted(positive_signers.items())
        },
        "signer_group_count": len(roles_by_signer),
        "fresh_negative_signers": fresh_signers,
        "signer_leakage": signer_leakage,
        "hash_role_leakage": hash_leakage,
    }


def build(args: argparse.Namespace) -> int:
    rows = [
        *_positive_rows(args.positive_manifest),
        *_n0_rows(args.n0_run),
        *_p1_rows(args.p1_windows),
        *_oov_rows(args.oov_manifest),
        *_fresh_negative_rows(args.fresh_negative_manifest),
    ]
    rows.sort(key=lambda row: (row["role"], row["canonical_label"], row["assignment_id"]))
    gate = _gate(rows)
    args.output.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output / "assignment_manifest.csv", rows)
    _write_csv(args.output / "positive_assignment.csv", (r for r in rows if r["sample_kind"] == "positive"))
    _write_csv(args.output / "development_negative_assignment.csv", (r for r in rows if r["role"] == "development_negative"))
    _write_csv(args.output / "fresh_negative_evaluation_assignment.csv", (r for r in rows if r["role"] == "test_negative_fresh_provisional"))
    summary = {
        "experiment": EXPERIMENT,
        "scope": "assignment and leakage validation only; no extraction or modeling",
        "vocabulary": VOCABULARY,
        "schema_contract": "v3.0 [96,258] remains unchanged",
        "lean_pilot_waiver": {
            "approved": True,
            "engineering_target": 1000,
            "development_negative_rows_used": LEAN_DEVELOPMENT_NEGATIVE_TARGET,
            "shortfall_waived_for_pilot": 1000 - LEAN_DEVELOPMENT_NEGATIVE_TARGET,
            "claim_limit": "pilot only; not production-ready negative coverage",
        },
        "fresh_negative_limit": "one signer and short-event clips; provisional evaluation only",
        "inputs": {
            "positive_manifest": str(args.positive_manifest.resolve()),
            "n0_run": str(args.n0_run.resolve()),
            "p1_windows": str(args.p1_windows.resolve()),
            "oov_manifest": str(args.oov_manifest.resolve()),
            "fresh_negative_manifest": str(args.fresh_negative_manifest.resolve()),
        },
        "gate": gate,
        "decision": "assignment_gate_passed_feature_extraction_may_be_prepared_separately"
        if gate["passed"]
        else "assignment_gate_failed",
        "next_authorized_action": "prepare one clean v3.0 five-sign baseline extraction/training package; do not run it automatically"
        if gate["passed"]
        else "repair assignment errors before extraction",
    }
    _write_json(args.output / "assignment_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if gate["passed"] else 1


def check(args: argparse.Namespace) -> int:
    required = [
        "assignment_manifest.csv",
        "positive_assignment.csv",
        "development_negative_assignment.csv",
        "fresh_negative_evaluation_assignment.csv",
        "assignment_summary.json",
    ]
    errors = [name for name in required if not (args.run_dir / name).is_file()]
    summary: dict[str, Any] = {}
    if not errors:
        summary = json.loads((args.run_dir / "assignment_summary.json").read_text(encoding="utf-8"))
        if not summary.get("gate", {}).get("passed"):
            errors.append("assignment gate did not pass")
        rows = _read_csv(args.run_dir / "assignment_manifest.csv")
        if len(rows) != summary.get("gate", {}).get("assignment_rows"):
            errors.append("manifest row count differs from summary")
    report = {
        "run_dir": str(args.run_dir.resolve()),
        "passed": not errors,
        "errors": errors,
    }
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build")
    build_parser.add_argument("--positive-manifest", type=Path, default=DEFAULT_POSITIVE_MANIFEST)
    build_parser.add_argument("--n0-run", type=Path, default=DEFAULT_N0_RUN)
    build_parser.add_argument("--p1-windows", type=Path, default=DEFAULT_P1_WINDOWS)
    build_parser.add_argument("--oov-manifest", type=Path, default=DEFAULT_OOV_MANIFEST)
    build_parser.add_argument("--fresh-negative-manifest", type=Path, default=DEFAULT_FRESH_NEGATIVE)
    build_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build_parser.set_defaults(func=build)
    check_parser = commands.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.set_defaults(func=check)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"[e6-five-sign-assignment] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
