"""Summarize a completed blinded E2 crop audit."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _parse_bool(value: str) -> bool | None:
    cleaned = value.strip().lower()
    if cleaned in {"1", "true", "yes", "y"}:
        return True
    if cleaned in {"0", "false", "no", "n"}:
        return False
    return None


def summarize(audit_path: Path, index_path: Path, output_path: Path, gate: float) -> dict[str, Any]:
    with index_path.open("r", encoding="utf-8", newline="") as fh:
        metadata = {row["crop_id"]: row for row in csv.DictReader(fh)}

    totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"reviewed": 0, "visible": 0, "usable": 0, "roi_available": 0}
    )
    incomplete = 0
    with audit_path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            visible = _parse_bool(row.get("visible_hand", ""))
            usable = _parse_bool(row.get("usable", ""))
            if visible is None or (visible and usable is None):
                incomplete += 1
                continue
            meta = metadata.get(row["crop_id"])
            if meta is None:
                raise ValueError(f"audit crop_id absent from internal index: {row['crop_id']}")
            key = (
                f"size={meta['crop_size']}|expand={meta['expansion']}|" f"cadence={meta['cadence']}"
            )
            for group in ("overall", key):
                totals[group]["reviewed"] += 1
                if visible:
                    totals[group]["visible"] += 1
                    totals[group]["usable"] += int(bool(usable))
                    totals[group]["roi_available"] += int(meta["roi_source"] != "missing")

    report: dict[str, Any] = {"incomplete_rows": incomplete, "gate": gate, "groups": {}}
    for key, counts in totals.items():
        visible_count = counts["visible"]
        usability = counts["usable"] / visible_count if visible_count else None
        availability = counts["roi_available"] / visible_count if visible_count else None
        report["groups"][key] = {
            **counts,
            "usable_visible_rate": usability,
            "roi_available_visible_rate": availability,
            "passed": usability is not None and usability >= gate,
        }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize a completed E2 blinded audit")
    parser.add_argument("--audit-csv", type=Path, required=True)
    parser.add_argument("--index-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gate", type=float, default=0.98)
    args = parser.parse_args()
    report = summarize(args.audit_csv, args.index_csv, args.output, args.gate)
    print(json.dumps(report, indent=2))
    return 2 if report["incomplete_rows"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
