"""E6 product-core signer-disjoint split dry-run.

Data-readiness gate only. This checks whether an accepted manifest can support
signer-disjoint train/val/test splits before feature extraction or training.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_MANIFEST = Path("artifacts/recognition_upgrade/product_core_data_readiness/e6_product_core_review_01/source_manifest_snapshot.csv")
DEFAULT_REVIEW = Path("artifacts/recognition_upgrade/product_core_data_readiness/e6_product_core_review_01/review_manifest.csv")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/product_core_data_readiness/e6_split_dry_run_01")
TARGET_SIGNS = ["GOOD", "HELLO", "SORRY", "HAVE", "KNOW", "THINK", "TAKE", "SELL"]
REQUIREMENTS = {
    "total_clips": 150,
    "local_clips": 75,
    "local_signers": 5,
    "train_signers": 6,
    "val_signers": 2,
    "test_signers": 2,
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


def _final_decision(source_row: dict[str, str], review_row: dict[str, str] | None) -> str:
    if source_row.get("classification") == "Accepted":
        return "Accepted"
    if not review_row:
        return source_row.get("classification", "")
    decision = review_row.get("review_decision", "")
    if decision == "accept":
        return "Accepted"
    if decision == "reject":
        return "Rejected"
    if decision == "diagnostic_only":
        return "Diagnostic only"
    return "Manual review required"


def run(args: argparse.Namespace) -> None:
    source_rows = _read_csv(args.source_manifest)
    review_rows = {row.get("row_id", ""): row for row in _read_csv(args.review_manifest)}
    accepted = []
    final_counts = Counter()
    for row in source_rows:
        if row.get("canonical_gloss") not in TARGET_SIGNS:
            continue
        final = _final_decision(row, review_rows.get(row.get("row_id", "")))
        final_counts[final] += 1
        if final == "Accepted":
            accepted.append(row)
    rows = []
    for gloss in TARGET_SIGNS:
        gr = [row for row in accepted if row.get("canonical_gloss") == gloss]
        local = [row for row in gr if row.get("source_dataset") == "LOCAL_SUPPLEMENTARY"]
        signers = sorted({row.get("signer_id", "") for row in gr if row.get("signer_id")})
        local_signers = sorted({row.get("signer_id", "") for row in local if row.get("signer_id")})
        enough = {
            "total_clips": len(gr) >= REQUIREMENTS["total_clips"],
            "local_clips": len(local) >= REQUIREMENTS["local_clips"],
            "local_signers": len(local_signers) >= REQUIREMENTS["local_signers"],
            "split_signers": len(signers) >= REQUIREMENTS["train_signers"] + REQUIREMENTS["val_signers"] + REQUIREMENTS["test_signers"],
        }
        feasible = all(enough.values())
        reasons = []
        if not enough["total_clips"]:
            reasons.append(f"needs {REQUIREMENTS['total_clips'] - len(gr)} more accepted total clips")
        if not enough["local_clips"]:
            reasons.append(f"needs {REQUIREMENTS['local_clips'] - len(local)} more accepted local clips")
        if not enough["local_signers"]:
            reasons.append(f"needs {REQUIREMENTS['local_signers'] - len(local_signers)} more accepted local signers")
        if not enough["split_signers"]:
            reasons.append("not enough total signers for 6/2/2 signer-disjoint train/val/test")
        rows.append({
            "canonical_gloss": gloss,
            "accepted_total_clips": len(gr),
            "accepted_local_clips": len(local),
            "accepted_total_signers": len(signers),
            "accepted_local_signers": len(local_signers),
            "split_feasible_now": str(feasible),
            "blocking_reasons": " | ".join(reasons),
            "example_total_signers": " ".join(signers[:20]),
            "example_local_signers": " ".join(local_signers[:20]),
        })
    args.output.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output / "split_feasibility_by_sign.csv", rows, list(rows[0].keys()))
    payload = {
        "experiment": "e6_product_core_split_dry_run_v1",
        "source_manifest": str(args.source_manifest.resolve()),
        "review_manifest": str(args.review_manifest.resolve()),
        "requirements": REQUIREMENTS,
        "final_decision_counts": dict(final_counts),
        "signs_feasible": sum(1 for row in rows if row["split_feasible_now"] == "True"),
        "signs_total": len(rows),
        "passed": all(row["split_feasible_now"] == "True" for row in rows),
        "decision": "split_gate_passed" if all(row["split_feasible_now"] == "True" for row in rows) else "split_gate_blocked_more_data_required",
        "output": str((args.output / "split_feasibility_by_sign.csv").resolve()),
    }
    _write_json(args.output / "split_dry_run_summary.json", payload)
    print(json.dumps(payload, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="E6 product-core signer-disjoint split dry-run")
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--review-manifest", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        run(args)
        return 0
    except Exception as exc:
        print(f"[e6-split-dry-run] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
