"""Analyze completed E2c paired IMAGE-versus-VIDEO review evidence."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VALID_QUALITY = {
    "usable",
    "missing",
    "clipped",
    "stale",
    "wrong_hand",
    "low_detail",
    "other",
}


def _read(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def analyze(
    run_dir: Path,
    output_path: Path,
    parent_gate: float = 0.98,
    min_availability_gain: float = 0.20,
    max_wrong_or_stale_rate: float = 0.02,
    max_latency_ratio: float = 1.20,
) -> dict[str, Any]:
    audit_rows = _read(run_dir / "audit_template.csv")
    mapping = {row["base_id"]: row for row in _read(run_dir / "blind_map.csv")}
    index = {
        (row["base_id"], row["mode"]): row
        for row in _read(run_dir / "internal_index.csv")
    }
    generation = json.loads(
        (run_dir / "generation_summary.json").read_text(encoding="utf-8")
    )
    records: list[dict[str, Any]] = []
    incomplete = 0
    for audit in audit_rows:
        if (
            audit["source_blur"] not in {"clear", "blur"}
            or audit["a_quality"] not in VALID_QUALITY
            or audit["b_quality"] not in VALID_QUALITY
        ):
            incomplete += 1
            continue
        blind = mapping.get(audit["base_id"])
        if blind is None:
            raise ValueError(f"base absent from blind map: {audit['base_id']}")
        for panel_side in ("a", "b"):
            mode = blind[f"mode_{panel_side}"]
            meta = index.get((audit["base_id"], mode))
            if meta is None:
                raise ValueError(f"base/mode absent from index: {audit['base_id']}/{mode}")
            records.append(
                {
                    **meta,
                    "cadence": int(meta["cadence"]),
                    "available": meta["roi_available"] == "1",
                    "source_blur": audit["source_blur"],
                    "quality": audit[f"{panel_side}_quality"],
                }
            )

    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    by_base: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for record in records:
        mode = str(record["mode"])
        cadence = int(record["cadence"])
        base_id = str(record["base_id"])
        grouped[(mode, cadence)].append(record)
        by_base[base_id][mode] = record

    metrics: dict[str, Any] = {}
    contradictions: Counter[str] = Counter()
    for (mode, cadence), rows in sorted(grouped.items()):
        failures = Counter(
            row["quality"] for row in rows if row["quality"] != "usable"
        )
        usable = sum(row["quality"] == "usable" for row in rows)
        available = sum(row["available"] for row in rows)
        source_clear = [row for row in rows if row["source_blur"] == "clear"]
        source_clear_usable = sum(
            row["quality"] == "usable" for row in source_clear
        )
        for row in rows:
            if not row["available"] and row["quality"] != "missing":
                contradictions["missing_roi_nonmissing_quality"] += 1
            if row["available"] and row["quality"] == "missing":
                contradictions["present_roi_marked_missing"] += 1
        metrics[f"{mode}|cadence={cadence}"] = {
            "base_items": len(rows),
            "available": available,
            "availability_rate": available / len(rows) if rows else None,
            "usable": usable,
            "usable_rate": usable / len(rows) if rows else None,
            "source_clear": len(source_clear),
            "source_clear_usable_rate": (
                source_clear_usable / len(source_clear) if source_clear else None
            ),
            "failure_reasons": dict(sorted(failures.items())),
            "parent_gate_passed": bool(rows) and usable / len(rows) >= parent_gate,
        }

    comparisons: dict[str, Any] = {}
    for cadence in sorted({int(record["cadence"]) for record in records}):
        pairs = [
            pair
            for pair in by_base.values()
            if pair["image"]["cadence"] == cadence
        ]
        image_available = sum(pair["image"]["available"] for pair in pairs) / len(pairs)
        video_available = sum(pair["video"]["available"] for pair in pairs) / len(pairs)
        image_usable = sum(
            pair["image"]["quality"] == "usable" for pair in pairs
        ) / len(pairs)
        video_usable = sum(
            pair["video"]["quality"] == "usable" for pair in pairs
        ) / len(pairs)
        wrong_or_stale = sum(
            pair["video"]["quality"] in {"wrong_hand", "stale"} for pair in pairs
        ) / len(pairs)
        automatic = generation["paired_comparisons"][str(cadence)]
        diagnostic_passed = (
            video_available - image_available >= min_availability_gain
            and wrong_or_stale <= max_wrong_or_stale_rate
            and automatic["video_to_image_p95_latency_ratio"] <= max_latency_ratio
        )
        parent_passed = metrics[f"video|cadence={cadence}"]["parent_gate_passed"]
        comparisons[str(cadence)] = {
            "paired_items": len(pairs),
            "image_availability": image_available,
            "video_availability": video_available,
            "availability_gain": video_available - image_available,
            "image_usable_rate": image_usable,
            "video_usable_rate": video_usable,
            "usable_gain": video_usable - image_usable,
            "video_wrong_or_stale_rate": wrong_or_stale,
            "video_to_image_p95_latency_ratio": automatic[
                "video_to_image_p95_latency_ratio"
            ],
            "diagnostic_passed": diagnostic_passed,
            "parent_passed": parent_passed,
            "promotion_passed": diagnostic_passed and parent_passed,
        }
    report = {
        "incomplete_rows": incomplete,
        "gates": {
            "parent_usable": parent_gate,
            "min_availability_gain_each_cadence": min_availability_gain,
            "max_wrong_or_stale_rate": max_wrong_or_stale_rate,
            "max_video_to_image_p95_latency_ratio": max_latency_ratio,
        },
        "metrics": metrics,
        "paired_comparisons": comparisons,
        "contradictions": dict(contradictions),
        "promotion_passed": bool(comparisons)
        and all(value["promotion_passed"] for value in comparisons.values()),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze completed E2c paired review")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--parent-gate", type=float, default=0.98)
    parser.add_argument("--min-availability-gain", type=float, default=0.20)
    parser.add_argument("--max-wrong-or-stale-rate", type=float, default=0.02)
    parser.add_argument("--max-latency-ratio", type=float, default=1.20)
    args = parser.parse_args()
    output = args.output or args.run_dir / "audit_summary.json"
    try:
        report = analyze(
            args.run_dir,
            output,
            args.parent_gate,
            args.min_availability_gain,
            args.max_wrong_or_stale_rate,
            args.max_latency_ratio,
        )
    except (FileNotFoundError, KeyError, ValueError) as error:
        print(f"[tracking/audit] ERROR: {error}")
        return 2
    print(json.dumps(report, indent=2))
    return 2 if report["incomplete_rows"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
