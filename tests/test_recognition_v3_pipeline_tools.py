"""Host tests for the pipelined-pose parity and trace tools (measurement integrity only)."""

from __future__ import annotations

import importlib.util
import math
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools/recognition_v3"
sys.path.insert(0, str(TOOLS))


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PARITY = load("compare_pipeline_parity")
PIPE = load("summarize_pipeline_trace")


def record(index: int, presence: float = 0.9) -> bytes:
    floats = [0.25] * 84 + [0.5] * 42 + [presence, math.nan] + [1.0] * 6 + [0.1] * 16 + [0.7] * 8
    flags = [1] * 42 + [1, 0] + [1, 0] + [1] * 8 + [1]
    head = struct.pack("<iQii", index, struct.unpack("<Q", struct.pack("<d", 1000.0 + index))[0], 480, 640)
    return head + struct.pack(f"<{len(floats)}f", *floats) + bytes(flags)


def write(directory: Path, name: str, rows: list[bytes]) -> None:
    (directory / f"{name}.raw").write_bytes(b"".join(rows))


def test_record_layout_matches_the_android_canonical_size() -> None:
    assert len(record(0)) == PARITY.RECORD == 20 + 158 * 4 + 55


def test_identical_streams_pass_and_pipelined_may_hold_back_one_frame(tmp_path: Path) -> None:
    rows = [record(i) for i in range(5)]
    write(tmp_path, "s_legacy", rows)
    write(tmp_path, "s_serial", rows)
    write(tmp_path, "s_pipelined_a", rows[:4])
    result = PARITY.compare(tmp_path)
    assert result["status"] == "PASS"
    assert len(result["pairs"]) == 2


def test_one_flipped_bit_or_a_missing_frame_fails(tmp_path: Path) -> None:
    rows = [record(i) for i in range(5)]
    write(tmp_path, "s_serial", rows)
    write(tmp_path, "s_pipelined_bit", rows[:2] + [record(2, presence=struct.unpack("<f", struct.pack("<I", struct.unpack("<I", struct.pack("<f", 0.9))[0] + 1))[0])] + rows[3:4])
    write(tmp_path, "s_pipelined_short", rows[:3])
    result = PARITY.compare(tmp_path)
    assert result["status"] == "FAIL"
    problems = {p["candidate"]: p["problem"] for p in result["pairs"]}
    assert problems["s_pipelined_bit"] == "observation 2 field hand_presence"
    assert problems["s_pipelined_short"] == "3 observations, expected 4"


def test_emit_on_hands_must_match_every_serial_frame(tmp_path: Path) -> None:
    rows = [record(i) for i in range(5)]
    write(tmp_path, "s_serial", rows)
    write(tmp_path, "s_emit_ok", rows)
    write(tmp_path, "s_emit_held_back", rows[:4])
    result = PARITY.compare(tmp_path)
    problems = {p["candidate"]: p["problem"] for p in result["pairs"]}
    assert problems == {"s_emit_ok": None, "s_emit_held_back": "4 observations, expected 5"}
    assert result["status"] == "FAIL"


def test_free_running_emit_is_checked_against_its_subset_serial(tmp_path: Path) -> None:
    rows = [record(i) for i in range(6)]
    write(tmp_path, "s_serial", rows)
    write(tmp_path, "s_dropfree_x", rows[:4])
    write(tmp_path, "s_dropfree_x_subset_serial", rows[:4])
    result = PARITY.compare(tmp_path)
    assert result["status"] == "PASS"
    assert [(p["reference"], p["candidate"]) for p in result["pairs"]] == [
        ("s_dropfree_x_subset_serial", "s_dropfree_x")]


def trace_rows(gaps_frames: list[int], pipelined: bool, emit: bool = False) -> list[dict]:
    rows, capture = [], 1_000_000_000
    for index, frames in enumerate([0] + gaps_frames):
        capture += round(frames * 66.654e6)
        row = {key: 10.0 for key in PIPE.summarize.__globals__["TIMING_KEYS"]}
        row.update(schema_version="apphear.perception_v3_timing.v1", source_index=index,
                   capture_timestamp_ns=capture, completed_timestamp_ns=capture + 250_000_000,
                   newly_measured=True, reused=False, v3_parallel_hands=False, owner="WORD",
                   source_width=480, source_height=640, rotation_degrees=270, body_valid_points=8,
                   hands_observed=1, hand_valid_points=21, java_heap_bytes=1, native_heap_bytes=1)
        if pipelined:
            row.update(v3_pipelined_pose=True, pose_wait_ms=float(index % 3), pose_threads=2,
                       pose_spinning=True, hand_threads=2)
        if emit:
            row.update(v3_emit_on_hands=True, delivery_wait_ms=1.5, busy_drops_total=index // 2)
        rows.append(row)
    return rows


def test_interval_distribution_is_reported_in_camera_frames() -> None:
    result = PIPE.summarize_pipeline(trace_rows([2, 2, 2, 3] * 5, pipelined=True), 66.654)
    assert result["pipelined_pose"] is True
    assert result["interval_camera_frames"] == {"2": 0.75, "3": 0.25}
    assert abs(result["interval_ms"]["mean"] - 66.654 * 2.25) < 0.01
    assert abs(result["capture_to_completed_ms"]["p50"] - 250.0) < 1e-6
    assert result["pose_wait_ms"]["max"] == 2.0
    assert result["emit_on_hands"] is False and "delivery_wait_ms" not in result


def test_emit_on_hands_trace_reports_delivery_wait() -> None:
    result = PIPE.summarize_pipeline(trace_rows([2] * 20, pipelined=True, emit=True), 66.654)
    assert result["emit_on_hands"] is True
    assert result["delivery_wait_ms"]["p50"] == 1.5
    assert result["released_while_busy"]["frames"] == 10


def test_cpu_is_attributed_per_thread_from_raw_proc_stat(tmp_path: Path) -> None:
    tail = " 0 0 0 0 0"
    before = tmp_path / "before.txt"
    after = tmp_path / "after.txt"
    before.write_text("100 (AppHearV3 Pose) S 1 1 1 0 -1 0 0 0 0 0 100 50" + tail + "\n"
                      "101 (pool-2-thread) S 1 1 1 0 -1 0 0 0 0 0 10 10" + tail + "\n")
    after.write_text("100 (AppHearV3 Pose) S 1 1 1 0 -1 0 0 0 0 0 300 100" + tail + "\n"
                     "101 (pool-2-thread) S 1 1 1 0 -1 0 0 0 0 0 60 10" + tail + "\n")
    cpu = PIPE.cpu_from_proc(before, after, wall_s=2.0)
    assert cpu["process_cpu_percent_of_one_core"] == 150.0
    assert cpu["top_threads_percent_of_one_core"]["AppHearV3 Pose"] == 125.0
