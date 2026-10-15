"""Measurement integrity tests, not perception or recognition accuracy evidence."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "v3_trace", Path(__file__).resolve().parents[1] / "tools/recognition_v3/summarize_trace.py"
)
assert SPEC is not None and SPEC.loader is not None
TRACE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRACE)


def records() -> list[dict]:
    result = []
    for index in range(4):
        row: dict = {key: float(index + 1) for key in TRACE.TIMING_KEYS}
        row.update(
            schema_version="apphear.perception_v3_timing.v1",
            source_index=index,
            capture_timestamp_ns=1_000_000_000 + index * 100_000_000,
            completed_timestamp_ns=2_000_000_000 + index * 50_000_000,
            newly_measured=True,
            reused=False,
            v3_parallel_hands=True,
            owner="WORD",
            source_width=480,
            source_height=640,
            rotation_degrees=270,
            body_valid_points=8,
            hands_observed=2,
            hand_valid_points=42,
            java_heap_bytes=100,
            native_heap_bytes=200,
        )
        result.append(row)
    return result


def test_distinguishes_delivered_fps_from_capture_span_and_never_invents_drops() -> None:
    actual = TRACE.summarize(records())
    assert actual["delivered_observation_fps"] == 20
    assert actual["capture_span_observation_fps"] == 10
    assert actual["frame_drops"] == "NOT_MEASURED_USE_SENSOR_TIMESTAMP_JOIN"
    assert actual["observation_gap_p95_ms"] == 100
    assert actual["analyzer_ms"] == {"p50": 2.0, "p95": 3.0}


def test_parser_accepts_any_json_field_order_and_logcat_prefix() -> None:
    rows = records()
    lines = ["unrelated log"] + ["I AppHearV3: " + json.dumps(row) for row in rows]
    assert TRACE.parse_trace(lines) == rows
    assert TRACE.parse_trace([json.dumps(dict(reversed(list(r.items())))) for r in rows]) == rows


def test_partitions_explicit_resets_but_never_conceals_missing_positive_indices() -> None:
    rows = records()
    assert [len(g) for g in TRACE.partition_bindings(rows + records())] == [4, 4]
    rows[2]["source_index"] = 9
    assert len(TRACE.partition_bindings(rows)) == 1
    with pytest.raises(ValueError, match="missing log"):
        TRACE.summarize(rows)


def test_owner_boundary_is_explicit_and_does_not_mix_recognition_modes() -> None:
    rows = records()
    rows[2]["owner"] = rows[3]["owner"] = "FINGERSPELL"
    groups = TRACE.partition_bindings(rows)
    assert [len(g) for g in groups] == [2, 2]
    assert TRACE.summarize(groups[0])["owner"] == "WORD"
    assert TRACE.summarize(groups[1])["owner"] == "FINGERSPELL"


@pytest.mark.parametrize(
    "line",
    [
        'I AppHearV3: {"schema_version":"apphear.perception_v3_timing.v1",',
        'I AppHearV3: {"source_index":12,',
    ],
)
def test_rejects_truncated_target_records(line: str) -> None:
    with pytest.raises(ValueError, match="malformed"):
        TRACE.parse_trace([line])


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("source_index", 0),
        ("source_index", 8),
        ("capture_timestamp_ns", 1),
        ("completed_timestamp_ns", 1),
        ("reused", True),
        ("newly_measured", False),
        ("owner", "FINGERSPELL"),
        ("rotation_degrees", 90),
        ("v3_parallel_hands", False),
        ("analyzer_ms", float("nan")),
        ("hands_wall_ms", -1),
        ("hands_observed", 3),
    ],
)
def test_rejects_reset_missing_stale_mixed_or_invalid_measurements(key: str, value: object) -> None:
    rows = copy.deepcopy(records())
    rows[2][key] = value
    with pytest.raises(ValueError):
        TRACE.summarize(rows)
