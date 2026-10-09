"""Three-worker opt-in retains the frozen extraction and original runner identities."""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from tools.fingerspelling import prepare_expansion_balanced as three


def test_policy_reserves_pc_headroom() -> None:
    p = three.policy()
    assert p["workers"] == p["maximum_workers"] == 3
    assert p["worker_logical_cpu_limit"] == 10 and p["reserve_logical_cpus"] == 2
    assert p["minimum_available_ram_gib"] == 6
    assert p["worker_priority"] == "BELOW_NORMAL"
    assert p["candidate_threads"] == "UNCHANGED_FROZEN_DEFAULTS"


def test_affinity_excludes_two_available_logical_cpus() -> None:
    assert three.affinity_mask(0xFFF) == 0x3FF
    sparse = sum(1 << i for i in range(0, 24, 2))
    chosen = three.affinity_mask(sparse)
    assert chosen.bit_count() == 10 and chosen & ~sparse == 0
    assert (sparse ^ chosen).bit_count() == 2
    with pytest.raises(ValueError, match="twelve"):
        three.affinity_mask(0xFF)


def test_memory_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(three.os, "cpu_count", lambda: 12)
    monkeypatch.setattr(three, "available_ram_gib", lambda: 5)
    with pytest.raises(ValueError, match="headroom"):
        three.resources()


@pytest.mark.parametrize("failure", [False, True])
def test_three_inflight_max_and_failures_stop_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: bool
) -> None:
    active, maximum = 0, 0
    lock = threading.Lock()
    calls: list[str] = []
    barrier = threading.Barrier(3)

    def task(package: str, row: dict[str, Any]) -> dict[str, Any]:
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        calls.append(row["sample_id"])
        if failure:
            barrier.wait(3)
        time.sleep(0.03)
        with lock:
            active -= 1
        return dict(row, status="FAILED" if failure else "COMPLETE")

    monkeypatch.setattr(three, "process_sequence", task)
    stop = threading.Event()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = three.wave(
            pool, stop, [(tmp_path, {"sample_id": str(i)}) for i in range(9)], lambda _: None
        )
    assert active == 0 and maximum == 3
    assert len(calls) == len(results) == (3 if failure else 9)
    assert stop.is_set() == failure


def test_new_gate_requires_resource_policy_and_incremental_speedup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = tmp_path / "gate.json"
    monkeypatch.setattr(three, "GATE", gate)
    monkeypatch.setattr(three, "code_identity", lambda: {"current": True})
    report = {
        "code_identity": {"current": True},
        "exact_raw_feature_parity": True,
        "structural_pass": True,
        "three_workers_overlap": True,
        "worker_resource_policy_pass": True,
        "speedup_supported": True,
        "test_accessed": False,
    }
    (tmp_path / "execution_approval.json").write_text(json.dumps({"approved": True}))
    gate.write_text(json.dumps(report))
    three.check_gate()
    for key in ["worker_resource_policy_pass", "speedup_supported", "exact_raw_feature_parity"]:
        gate.write_text(json.dumps(dict(report, **{key: False})))
        with pytest.raises(ValueError, match="Passing unchanged real smoke"):
            three.check_gate()


def test_unapproved_candidate_cannot_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(three, "GATE", tmp_path / "gate.json")
    with pytest.raises(ValueError, match="not approved"):
        three.check_gate()
    (tmp_path / "execution_approval.json").write_text(json.dumps({"approved": False}))
    with pytest.raises(ValueError, match="not approved"):
        three.check_gate()
