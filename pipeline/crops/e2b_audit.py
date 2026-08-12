"""Analyze a completed E2b blinded audit with paired strategy comparisons."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _read(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _yes(value: str) -> bool | None:
    cleaned = value.strip().lower()
    if cleaned == "yes":
        return True
    if cleaned == "no":
        return False
    return None


def analyze(
    audit_path: Path,
    index_path: Path,
    output_path: Path,
    parent_gate: float = 0.98,
    min_availability_gain: float = 0.20,
    max_wrong_or_stale_rate: float = 0.02,
) -> dict[str, Any]:
    metadata = {row["crop_id"]: row for row in _read(index_path)}
    records: list[dict[str, Any]] = []
    incomplete = 0
    for audit in _read(audit_path):
        meta = metadata.get(audit["crop_id"])
        if meta is None:
            raise ValueError(f"audit crop absent from internal index: {audit['crop_id']}")
        visible = _yes(audit.get("visible_hand", ""))
        usable = _yes(audit.get("usable", ""))
        if visible is None or (visible and usable is None):
            incomplete += 1
            continue
        records.append(
            {
                **meta,
                "cadence": int(meta["cadence"]),
                "visible": bool(visible),
                "usable": bool(usable) if visible else None,
                "available": meta["roi_source"] != "missing",
                "failure_reason": audit.get("failure_reason", "").strip(),
            }
        )

    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    by_base: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["strategy"], record["cadence"])].append(record)
        by_base[record["base_id"]].append(record)

    metrics: dict[str, Any] = {}
    for (strategy, cadence), rows in sorted(grouped.items()):
        visible_rows = [row for row in rows if row["visible"]]
        failures = Counter(row["failure_reason"] for row in visible_rows if not row["usable"])
        usable_count = sum(bool(row["usable"]) for row in visible_rows)
        available_count = sum(bool(row["available"]) for row in visible_rows)
        risky_count = failures["wrong_hand"] + failures["stale_roi"]
        denominator = len(visible_rows)
        metrics[f"{strategy}|cadence={cadence}"] = {
            "reviewed": len(rows),
            "visible": denominator,
            "usable": usable_count,
            "available": available_count,
            "usable_visible_rate": usable_count / denominator if denominator else None,
            "roi_available_visible_rate": available_count / denominator if denominator else None,
            "wrong_or_stale_visible_rate": risky_count / denominator if denominator else None,
            "source_motion_blur": failures["motion_blur"],
            "failure_reasons": dict(sorted(failures.items())),
            "parent_gate_passed": denominator > 0 and usable_count / denominator >= parent_gate,
        }

    visibility_conflicts = 0
    for rows in by_base.values():
        labels = {row["visible"] for row in rows}
        visibility_conflicts += len(labels) > 1

    comparisons: dict[str, Any] = {}
    strategies = sorted({record["strategy"] for record in records})
    candidates = [strategy for strategy in strategies if strategy != "control_hold_100"]
    for strategy in candidates:
        cadence_results: dict[str, Any] = {}
        strategy_passed = True
        for cadence in sorted({record["cadence"] for record in records}):
            pairs = []
            for rows in by_base.values():
                control = next(
                    (
                        row
                        for row in rows
                        if row["strategy"] == "control_hold_100"
                        and row["cadence"] == cadence
                    ),
                    None,
                )
                candidate = next(
                    (
                        row
                        for row in rows
                        if row["strategy"] == strategy and row["cadence"] == cadence
                    ),
                    None,
                )
                if control and candidate and control["visible"] and candidate["visible"]:
                    pairs.append((control, candidate))
            if not pairs:
                cadence_results[str(cadence)] = {"paired_visible": 0, "passed": False}
                strategy_passed = False
                continue
            control_available = sum(pair[0]["available"] for pair in pairs) / len(pairs)
            candidate_available = sum(pair[1]["available"] for pair in pairs) / len(pairs)
            risky_rate = sum(
                pair[1]["failure_reason"] in {"wrong_hand", "stale_roi"} for pair in pairs
            ) / len(pairs)
            gain = candidate_available - control_available
            passed = gain >= min_availability_gain and risky_rate <= max_wrong_or_stale_rate
            strategy_passed = strategy_passed and passed
            cadence_results[str(cadence)] = {
                "paired_visible": len(pairs),
                "control_availability": control_available,
                "candidate_availability": candidate_available,
                "availability_gain": gain,
                "candidate_wrong_or_stale_rate": risky_rate,
                "passed": passed,
            }
        comparisons[strategy] = {
            "cadences": cadence_results,
            "diagnostic_promotion_passed": strategy_passed,
        }

    report = {
        "incomplete_rows": incomplete,
        "visibility_conflict_base_items": visibility_conflicts,
        "parent_usable_gate": parent_gate,
        "diagnostic_gates": {
            "min_availability_gain_each_cadence": min_availability_gain,
            "max_wrong_or_stale_rate": max_wrong_or_stale_rate,
        },
        "metrics": metrics,
        "paired_comparisons": comparisons,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze completed E2b paired audit")
    parser.add_argument("--audit-csv", type=Path, required=True)
    parser.add_argument("--index-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--parent-gate", type=float, default=0.98)
    parser.add_argument("--min-availability-gain", type=float, default=0.20)
    parser.add_argument("--max-wrong-or-stale-rate", type=float, default=0.02)
    args = parser.parse_args()
    report = analyze(
        args.audit_csv,
        args.index_csv,
        args.output,
        args.parent_gate,
        args.min_availability_gain,
        args.max_wrong_or_stale_rate,
    )
    print(json.dumps(report, indent=2))
    return 2 if report["incomplete_rows"] or report["visibility_conflict_base_items"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
