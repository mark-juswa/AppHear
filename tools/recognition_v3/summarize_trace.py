"""Summarize one bounded AppHearV3 logcat trace. Never infer camera drops from timing gaps."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def summarize(rows: list[dict]) -> dict:
    if len(rows) < 2:
        raise ValueError("At least two genuine observations are required")
    for a, b in zip(rows, rows[1:], strict=False):
        if b["capture_timestamp_ns"] <= a["capture_timestamp_ns"]:
            raise ValueError("Duplicate or nonchronological capture identity")
        if b["completed_timestamp_ns"] <= a["completed_timestamp_ns"]:
            raise ValueError("Nonchronological completion clock")
    if any(not r["newly_measured"] or r["reused"] for r in rows):
        raise ValueError("Trace includes reused observations")
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
    }
    for key in (
        "preprocess_ms",
        "pose_inference_and_output_ms",
        "pose_decode_ms",
        "hand_crop_ms",
        "hand_inference_ms",
        "hands_wall_ms",
        "perception_ms",
        "analyzer_ms",
    ):
        result[key] = {"p50": percentile(key, 0.5), "p95": percentile(key, 0.95)}
    for key in ("java_heap_bytes", "native_heap_bytes"):
        result[key] = {"first": rows[0][key], "max": max(r[key] for r in rows)}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--skip-warmup", type=int, default=0)
    args = parser.parse_args()
    if args.skip_warmup < 0:
        raise ValueError("Warmup count must be nonnegative")
    rows = []
    for line in args.trace.read_text(encoding="utf-8").splitlines():
        start = line.find('{"schema_version":"apphear.perception_v3_timing.v1"')
        if start >= 0:
            rows.append(json.loads(line[start:]))
    print(json.dumps(summarize(rows[args.skip_warmup :]), indent=2))


if __name__ == "__main__":
    main()
