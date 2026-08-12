"""Audit existing AppHear captures for protected-baseline evaluation eligibility.

This module reads lineage manifests and raw files only. It does not extract features,
run inference, train models, or modify Android assets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INTEGRATION = ROOT / (
    "artifacts/recognition_upgrade/product_core_data_readiness/"
    "e6_collection_integration_01/manifest.csv"
)
DEFAULT_NEGATIVE = ROOT / (
    "artifacts/recognition_upgrade/product_core_data_readiness/"
    "e6_negative_upload_review_01/accepted_fresh_negative_manifest.csv"
)
DEFAULT_BASELINE_USAGE = ROOT / (
    "artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_baseline_01/"
    "positive_extraction_manifest.csv"
)
DEFAULT_REJECTION_USAGE = ROOT / (
    "artifacts/recognition_upgrade/e6_rejection/e6_3_frozen_embedding_01/"
    "dataset/negative_window_manifest.csv"
)
DEFAULT_MODEL = ROOT / "android/app/src/main/assets/streaming.tflite"
DEFAULT_OUTPUT = ROOT / (
    "artifacts/recognition_upgrade/heldout_baseline_evaluation/"
    "eligibility_audit_01"
)
EXPECTED_MODEL_SHA256 = (
    "42575710A4ADB0A1433B58BA9093BC4E9F49401381582CC4AD304FEEB669D4BB"
)
EXPERIMENT_SCAN_ROOTS = (
    "artifacts/recognition_upgrade/e6_baseline",
    "artifacts/recognition_upgrade/e6_landmark_geometry",
    "artifacts/recognition_upgrade/e6_registry",
    "artifacts/recognition_upgrade/e6_rejection",
    "artifacts/recognition_upgrade/e6_specialists",
    "artifacts/recognition_upgrade/e2e_c0",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _sidecar_recording_date(video: Path) -> str:
    sidecar = video.with_suffix(".json")
    if not sidecar.is_file():
        return ""
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(payload.get("recording_date", ""))


def _is_after_model(recording_date: str, video: Path, model: Path) -> bool:
    if recording_date:
        try:
            return date.fromisoformat(recording_date) > datetime.fromtimestamp(
                model.stat().st_mtime
            ).date()
        except ValueError:
            pass
    return video.stat().st_mtime > model.stat().st_mtime


def _hashes(rows: Iterable[dict[str, str]], field: str) -> set[str]:
    return {row.get(field, "").strip().upper() for row in rows if row.get(field, "").strip()}


def _scan_experiment_hash_usage(targets: set[str]) -> tuple[dict[str, set[str]], int]:
    usage: dict[str, set[str]] = {digest: set() for digest in targets}
    scanned = 0
    for relative_root in EXPERIMENT_SCAN_ROOTS:
        root = ROOT / relative_root
        if not root.is_dir():
            continue
        for path in root.rglob("*.csv"):
            scanned += 1
            try:
                rows = _read_csv(path)
            except (OSError, UnicodeError, csv.Error):
                continue
            for row in rows:
                values = {str(value).strip().upper() for value in row.values()}
                for digest in targets.intersection(values):
                    usage[digest].add(str(path.resolve()))
    return usage, scanned


def _positive_eligibility(used_by_e6_baseline: bool, later_usage: set[str]) -> tuple[str, str]:
    if used_by_e6_baseline:
        return (
            "reused_e6_diagnostic_only",
            "raw hash was consumed by the E6 five-sign baseline",
        )
    if later_usage:
        return (
            "reused_other_experiment_diagnostic_only",
            "raw hash appears in a later experiment artifact",
        )
    return (
        "clean_isolated_replay_candidate",
        "not used by the E6 baseline or scanned E6/C0 experiment CSVs",
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    required = (
        args.integration_manifest,
        args.negative_manifest,
        args.baseline_usage_manifest,
        args.rejection_usage_manifest,
        args.model,
    )
    missing_inputs = [str(path) for path in required if not path.is_file()]
    if missing_inputs:
        raise FileNotFoundError(f"missing required inputs: {missing_inputs}")

    model_sha256 = _sha256(args.model)
    integration = _read_csv(args.integration_manifest)
    positives = [
        row
        for row in integration
        if row.get("source") == "apphear_capture"
        and row.get("quality_status") == "usable"
        and row.get("split") != "exclude"
    ]
    negatives = _read_csv(args.negative_manifest)
    baseline_hashes = _hashes(_read_csv(args.baseline_usage_manifest), "raw_video_sha256")
    rejection_hashes = _hashes(_read_csv(args.rejection_usage_manifest), "raw_video_sha256")

    nonbaseline_positive_hashes = {
        row["raw_video_sha256"].upper()
        for row in positives
        if row["raw_video_sha256"].upper() not in baseline_hashes
    }
    later_usage, csv_files_scanned = _scan_experiment_hash_usage(nonbaseline_positive_hashes)

    output_rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for row in positives:
        video = Path(row["raw_video_path"])
        expected = row["raw_video_sha256"].upper()
        exists = video.is_file()
        actual = _sha256(video) if exists and args.verify_hashes else ""
        hash_match = exists and (not args.verify_hashes or actual == expected)
        if not exists:
            errors.append(f"missing:{video}")
        elif not hash_match:
            errors.append(f"hash_mismatch:{video}")
        usage = later_usage.get(expected, set())
        eligibility, reason = _positive_eligibility(expected in baseline_hashes, usage)
        recording_date = _sidecar_recording_date(video) if exists else ""
        after_model = exists and _is_after_model(recording_date, video, args.model)
        output_rows.append(
            {
                "sample_kind": "positive",
                "label_or_subtype": row["canonical_gloss"],
                "signer_group_id": row["signer_group_id"],
                "proposed_split": row["split"],
                "raw_video_path": str(video),
                "raw_video_sha256": expected,
                "recording_date": recording_date,
                "exists": str(exists).lower(),
                "hash_match": str(hash_match).lower(),
                "recorded_after_deployed_model": str(after_model).lower(),
                "eligibility": eligibility,
                "prior_model_experiment_usage": " | ".join(sorted(usage)),
                "reason": reason,
            }
        )

    for row in negatives:
        video = Path(row["raw_video_path"])
        expected = row["raw_video_sha256"].upper()
        exists = video.is_file()
        actual = _sha256(video) if exists and args.verify_hashes else ""
        hash_match = exists and (not args.verify_hashes or actual == expected)
        if not exists:
            errors.append(f"missing:{video}")
        elif not hash_match:
            errors.append(f"hash_mismatch:{video}")
        used = expected in rejection_hashes
        recording_date = _sidecar_recording_date(video) if exists else ""
        after_model = exists and _is_after_model(recording_date, video, args.model)
        output_rows.append(
            {
                "sample_kind": "negative",
                "label_or_subtype": row["canonical_subtype"],
                "signer_group_id": row["signer_id"],
                "proposed_split": row["final_split"],
                "raw_video_path": str(video),
                "raw_video_sha256": expected,
                "recording_date": recording_date,
                "exists": str(exists).lower(),
                "hash_match": str(hash_match).lower(),
                "recorded_after_deployed_model": str(after_model).lower(),
                "eligibility": (
                    "reused_e6_3_diagnostic_only" if used else "clean_negative_replay_candidate"
                ),
                "prior_model_experiment_usage": (
                    str(args.rejection_usage_manifest.resolve()) if used else ""
                ),
                "reason": (
                    "raw hash was consumed by E6-3 rejection evaluation"
                    if used
                    else "not found in the E6-3 negative window manifest"
                ),
            }
        )

    fields = list(output_rows[0])
    _write_csv(args.output / "eligibility_manifest.csv", output_rows, fields)
    clean = [row for row in output_rows if row["eligibility"] == "clean_isolated_replay_candidate"]
    summary = {
        "experiment": "post_c0_protected_baseline_eligibility_v1",
        "status": "bounded_isolated_diagnostic_available_phrase_evaluation_blocked",
        "model_path": str(args.model.resolve()),
        "model_sha256": model_sha256,
        "model_hash_matches_e6_0": model_sha256 == EXPECTED_MODEL_SHA256,
        "verify_hashes": args.verify_hashes,
        "candidate_rows": len(output_rows),
        "positive_rows": len(positives),
        "negative_rows": len(negatives),
        "clean_isolated_replay_rows": len(clean),
        "clean_isolated_counts_by_label": dict(Counter(row["label_or_subtype"] for row in clean)),
        "clean_isolated_signers": sorted({row["signer_group_id"] for row in clean}),
        "eligibility_counts": dict(Counter(row["eligibility"] for row in output_rows)),
        "all_paths_and_hashes_valid": not errors,
        "csv_files_scanned_for_prior_usage": csv_files_scanned,
        "natural_phrase_sessions_available": 0,
        "project_fresh_negative_rows": sum(
            row["eligibility"] == "clean_negative_replay_candidate" for row in output_rows
        ),
        "decision": (
            "Use only SELL/TAKE/THINK for the next protected-model isolated replay diagnostic. "
            "Do not claim held-out phrase accuracy. Reused positives and negatives may be reported "
            "only as historical diagnostics."
        ),
        "errors": errors,
        "passed": not errors and model_sha256 == EXPECTED_MODEL_SHA256,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "eligibility_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--integration-manifest", type=Path, default=DEFAULT_INTEGRATION)
    parser.add_argument("--negative-manifest", type=Path, default=DEFAULT_NEGATIVE)
    parser.add_argument("--baseline-usage-manifest", type=Path, default=DEFAULT_BASELINE_USAGE)
    parser.add_argument("--rejection-usage-manifest", type=Path, default=DEFAULT_REJECTION_USAGE)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-hashes", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = run(args)
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
