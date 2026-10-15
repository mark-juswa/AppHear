"""Summarize one bounded AppHearV3 logcat trace. Never infer camera drops from timing gaps."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

TIMING_KEYS = (
    "preprocess_ms",
    "pose_inference_and_output_ms",
    "pose_decode_ms",
    "hand_crop_ms",
    "hand_inference_ms",
    "hands_wall_ms",
    "perception_ms",
    "analyzer_ms",
)


def parse_trace(lines: list[str]) -> list[dict]:
    """JSON field order is unspecified; reject damaged target records instead of dropping them."""
    rows = []
    for line in lines:
        start = line.find("{")
        if start < 0:
            continue
        try:
            row = json.loads(line[start:])
        except json.JSONDecodeError as error:
            if "AppHearV3" in line or "apphear.perception_v3_timing.v1" in line:
                raise ValueError("Truncated or malformed V3 timing record") from error
            continue
        if isinstance(row, dict) and row.get("schema_version") == "apphear.perception_v3_timing.v1":
            rows.append(row)
    return rows


def partition_bindings(rows: list[dict]) -> list[list[dict]]:
    """Expose explicit session/owner boundaries. Positive index gaps stay errors, never new runs."""
    groups: list[list[dict]] = []
    identity = ("v3_parallel_hands", "owner", "source_width", "source_height", "rotation_degrees")
    for row in rows:
        if not groups:
            groups.append([row])
            continue
        old = groups[-1][-1]
        if row["source_index"] == 0 or any(row[k] != old[k] for k in identity):
            groups.append([])
        groups[-1].append(row)
    return groups


def summarize(rows: list[dict]) -> dict:
    if len(rows) < 2:
        raise ValueError("At least two genuine observations are required")
    for a, b in zip(rows, rows[1:], strict=False):
        if b["source_index"] != a["source_index"] + 1:
            raise ValueError("Source index reset or missing log rows; use one contiguous binding")
        if b["capture_timestamp_ns"] <= a["capture_timestamp_ns"]:
            raise ValueError("Duplicate or nonchronological capture identity")
        if b["completed_timestamp_ns"] <= a["completed_timestamp_ns"]:
            raise ValueError("Nonchronological completion clock")
    if any(not r["newly_measured"] or r["reused"] for r in rows):
        raise ValueError("Trace includes reused observations")
    for row in rows:
        for key in (*TIMING_KEYS, "java_heap_bytes", "native_heap_bytes"):
            if not math.isfinite(row[key]) or row[key] < 0:
                raise ValueError(f"Invalid measurement: {key}")
        if not 0 <= row["hands_observed"] <= 2:
            raise ValueError("Invalid hand observation count")
    if (
        len(
            {
                (
                    r["v3_parallel_hands"],
                    r["owner"],
                    r["source_width"],
                    r["source_height"],
                    r["rotation_degrees"],
                )
                for r in rows
            }
        )
        != 1
    ):
        raise ValueError("Split traces by arm, owner, lens binding and geometry before comparison")

    def percentile(key: str, p: float) -> float:
        values = sorted(r[key] for r in rows)
        return float(values[int((len(values) - 1) * p)])

    result = {
        "schema_version": "apphear.v3.trace_summary.v1",
        "genuine_observations": len(rows),
        "v3_parallel_hands": rows[0]["v3_parallel_hands"],
        "owner": rows[0]["owner"],
        "delivered_observation_fps": (len(rows) - 1)
        * 1e9
        / (rows[-1]["completed_timestamp_ns"] - rows[0]["completed_timestamp_ns"]),
        "capture_span_observation_fps": (len(rows) - 1)
        * 1e9
        / (rows[-1]["capture_timestamp_ns"] - rows[0]["capture_timestamp_ns"]),
        "frame_drops": "NOT_MEASURED_USE_SENSOR_TIMESTAMP_JOIN",
        "reused_observations": 0,
        "body_valid_points_total": sum(r["body_valid_points"] for r in rows),
        "hands_observed_total": sum(r["hands_observed"] for r in rows),
        "hand_valid_points_total": sum(r["hand_valid_points"] for r in rows),
        "accuracy_claim": "NONE",
        "source_index_range": [rows[0]["source_index"], rows[-1]["source_index"]],
        "observation_gap_p95_ms": sorted(
            (b["capture_timestamp_ns"] - a["capture_timestamp_ns"]) / 1e6
            for a, b in zip(rows, rows[1:], strict=False)
        )[int((len(rows) - 2) * 0.95)],
    }
    for key in TIMING_KEYS:
        result[key] = {"p50": percentile(key, 0.5), "p95": percentile(key, 0.95)}
    for key in ("java_heap_bytes", "native_heap_bytes"):
        result[key] = {"first": rows[0][key], "max": max(r[key] for r in rows)}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--skip-warmup", type=int, default=0)
    parser.add_argument("--segment", type=int, help="Explicit zero-based binding/owner segment")
    parser.add_argument("--list-segments", action="store_true")
    args = parser.parse_args()
    if args.skip_warmup < 0:
        raise ValueError("Warmup count must be nonnegative")
    rows = parse_trace(args.trace.read_text(encoding="utf-8-sig").splitlines())
    groups = partition_bindings(rows)
    if args.list_segments:
        print(
            json.dumps(
                [
                    {
                        "segment": i,
                        "rows": len(g),
                        "owner": g[0]["owner"],
                        "v3_parallel_hands": g[0]["v3_parallel_hands"],
                        "first_capture_ns": g[0]["capture_timestamp_ns"],
                        "source_index_range": [g[0]["source_index"], g[-1]["source_index"]],
                    }
                    for i, g in enumerate(groups)
                ],
                indent=2,
            )
        )
        return
    if args.segment is not None:
        if not 0 <= args.segment < len(groups):
            raise ValueError("Segment index out of range; use --list-segments")
        rows = groups[args.segment]
    elif len(groups) > 1:
        raise ValueError(
            "Multiple sessions/owners: use --list-segments and select --segment explicitly"
        )
    # Validate the entire capture first: warmup trimming must not conceal a reset or lost rows.
    summarize(rows)
    result = summarize(rows[args.skip_warmup :])
    result["selected_segment"] = args.segment if args.segment is not None else 0
    result["segments_in_input"] = len(groups)
    result["warmup_rows_excluded"] = args.skip_warmup
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
