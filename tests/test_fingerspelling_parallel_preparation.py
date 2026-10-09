"""Ownership, bounded work, cooperative stop and unchanged extraction controls."""

import json
import multiprocessing as mp
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from tools.fingerspelling import prepare_expansion_parallel as parallel
from tools.fingerspelling.tranche import single_writer


def inherited_socket_probe(lease: socket.socket, ready: Any, release: Any) -> None:
    ready.set()
    release.wait(20)
    lease.close()


def test_policy_caps_two_workers_preserves_frozen_candidate_defaults() -> None:
    p = parallel.policy()
    assert p["workers"] == p["maximum_workers"] == 2
    assert p["worker_priority"] == "BELOW_NORMAL"
    assert p["candidate_threads"] == "UNCHANGED_FROZEN_DEFAULTS"


def test_serial_and_parallel_share_same_root_owner(tmp_path: Path) -> None:
    with single_writer(tmp_path):
        with pytest.raises(RuntimeError, match="Another writer"):
            with parallel.shared_writer(tmp_path):
                raise AssertionError("Two owners cannot enter")
    with parallel.shared_writer(tmp_path):
        with pytest.raises(RuntimeError, match="Another preparation writer"):
            with single_writer(tmp_path):
                raise AssertionError("Two owners cannot enter")


def test_worker_inherits_root_lock_after_coordinator_socket_closes(tmp_path: Path) -> None:
    context = mp.get_context("spawn")
    ready, release = context.Event(), context.Event()
    with parallel.shared_writer(tmp_path) as lease:
        worker = context.Process(target=inherited_socket_probe, args=(lease, ready, release))
        worker.start()
        assert ready.wait(15)
    try:
        with pytest.raises(RuntimeError, match="Another preparation writer"):
            with single_writer(tmp_path):
                raise AssertionError("Worker still owns inherited lease")
    finally:
        release.set()
        worker.join(15)
    assert worker.exitcode == 0
    with single_writer(tmp_path):
        pass


def fixture_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, duplicate: bool) -> Path:
    output = tmp_path / "plan"
    output.mkdir()
    plan = {
        "batches": [
            {"package": "train_additions", "sample_ids": ["a", "b"]},
            {"package": "dev_b", "sample_ids": ["d"]},
        ]
    }
    (output / "batch_plan.json").write_text(json.dumps(plan))
    monkeypatch.setattr(parallel.serial, "OUTPUT", output)
    monkeypatch.setattr(
        parallel.serial,
        "rows",
        lambda name: (
            [
                {"sample_id": "a", "filename": "a.mp4", "split_role": "TRAIN"},
                {
                    "sample_id": "b",
                    "filename": "a.mp4" if duplicate else "b.mp4",
                    "split_role": "TRAIN",
                },
            ]
            if name == "train_additions"
            else [{"sample_id": "d", "filename": "d.mp4", "split_role": "DEV"}]
        ),
    )
    return output


def test_plan_requires_unique_sources_and_complete_roles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_plan(tmp_path, monkeypatch, False)
    batches = parallel.work_plan(tmp_path)
    assert [b["index"] for b in batches] == [0, 1]
    assert sum(len(b["rows"]) for b in batches) == 3


def test_duplicate_source_writers_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture_plan(tmp_path, monkeypatch, True)
    with pytest.raises(ValueError, match="Duplicate writer"):
        parallel.work_plan(tmp_path)


def test_wave_never_exceeds_two_inflight_writers_and_settles_before_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    active, maximum = 0, 0
    lock = threading.Lock()

    def task(package: str, row: dict[str, Any]) -> dict[str, Any]:
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        time.sleep(0.015)
        with lock:
            active -= 1
        return dict(row, status="COMPLETE")

    monkeypatch.setattr(parallel, "process_sequence", task)
    tasks = [(tmp_path, {"sample_id": str(i)}) for i in range(9)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = parallel.wave(pool, threading.Event(), tasks, lambda _: None)
    assert maximum == 2 and active == 0
    assert {r["sample_id"] for r in results} == {str(i) for i in range(9)}


def test_failure_stops_dispatch_and_retains_all_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    barrier = threading.Barrier(2)
    calls = []

    def task(package: str, row: dict[str, Any]) -> dict[str, Any]:
        calls.append(row["sample_id"])
        barrier.wait(2)
        if row["sample_id"] != "0":
            time.sleep(0.08)
        return dict(row, status="FAILED" if row["sample_id"] == "0" else "COMPLETE")

    monkeypatch.setattr(parallel, "process_sequence", task)
    stop = threading.Event()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = parallel.wave(
            pool, stop, [(tmp_path, {"sample_id": str(i)}) for i in range(8)], lambda _: None
        )
    assert stop.is_set() and set(calls) == {"0", "1"}
    assert len(results) == 2


def test_ctrl_c_settles_writers_without_dispatching_more(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_wait = parallel.wait
    wait_calls = 0

    def interrupt_once(*args: Any, **kwargs: Any) -> Any:
        nonlocal wait_calls
        wait_calls += 1
        if wait_calls == 1:
            raise KeyboardInterrupt
        return real_wait(*args, **kwargs)

    monkeypatch.setattr(parallel, "wait", interrupt_once)

    def finish(p: str, r: dict[str, Any]) -> dict[str, Any]:
        time.sleep(0.02)
        return dict(r, status="COMPLETE")

    monkeypatch.setattr(parallel, "process_sequence", finish)
    completed: list[dict[str, Any]] = []
    stop = threading.Event()
    with ThreadPoolExecutor(max_workers=2) as pool:
        with pytest.raises(KeyboardInterrupt):
            parallel.wave(
                pool, stop, [(tmp_path, {"sample_id": str(i)}) for i in range(9)], completed.append
            )
    assert stop.is_set() and len(completed) == 2


def test_protected_role_never_reaches_acquisition(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        parallel.serial, "acquire", lambda *a: pytest.fail("Protected source reached I/O")
    )
    with pytest.raises(ValueError, match="Protected role"):
        parallel.process_sequence("unused", {"sample_id": "test", "split_role": "PROTECTED_TEST"})


def test_recovery_preserves_only_known_staging_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        parallel.serial, "rows", lambda _: [{"sample_id": "a", "filename": "a.mp4"}]
    )
    folder = tmp_path / "train_additions/features"
    folder.mkdir(parents=True)
    stage = folder / "a.pending.npz"
    committed = folder / "a.npz"
    unknown = folder / "unowned.pending.npz"
    stage.write_bytes(b"partial")
    committed.write_bytes(b"complete")
    unknown.write_bytes(b"not ours")
    parallel.recover_staging(tmp_path)
    assert not stage.exists()
    assert committed.read_bytes() == b"complete" and unknown.read_bytes() == b"not ours"
    assert list((tmp_path / "train_additions/recovery").glob("*/a.pending.npz"))


def test_worker_exception_is_recorded_and_stops_new_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(package: str, row: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("worker failed")

    monkeypatch.setattr(parallel, "process_sequence", fail)
    stop = threading.Event()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = parallel.wave(
            pool, stop, [(tmp_path, {"sample_id": str(i)}) for i in range(6)], lambda _: None
        )
    assert stop.is_set() and len(results) == 2
    assert all(r["status"] == "FAILED" and r["error"] == "worker failed" for r in results)


def test_unverified_or_stale_real_gate_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = tmp_path / "gate.json"
    monkeypatch.setattr(parallel, "GATE", gate)
    monkeypatch.setattr(parallel, "code_identity", lambda: {"current": True})
    report = {
        "code_identity": {"current": True},
        "exact_raw_feature_parity": True,
        "structural_pass": True,
        "two_workers_overlap": True,
        "speedup_supported": True,
        "test_accessed": False,
    }
    gate.write_text(json.dumps(report))
    parallel.check_gate()
    for key in ["exact_raw_feature_parity", "speedup_supported", "structural_pass"]:
        gate.write_text(json.dumps(dict(report, **{key: False})))
        with pytest.raises(ValueError, match="Passing unchanged real smoke"):
            parallel.check_gate()
    gate.write_text(json.dumps(dict(report, code_identity={"changed": True})))
    with pytest.raises(ValueError, match="Passing unchanged real smoke"):
        parallel.check_gate()


def test_insufficient_memory_refuses_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(parallel.os, "cpu_count", lambda: 12)
    monkeypatch.setattr(parallel, "available_ram_gib", lambda: 2)
    with pytest.raises(ValueError, match="headroom"):
        parallel.resources()


def test_coordinator_resume_and_idle_validation_barrier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    batches = [
        {
            "index": 0,
            "package": "train_additions",
            "rows": [
                {"sample_id": "old", "split_role": "TRAIN"},
                {"sample_id": "new", "split_role": "TRAIN"},
            ],
        },
        {
            "index": 1,
            "package": "dev_b",
            "rows": [
                {"sample_id": "dev", "split_role": "DEV"},
            ],
        },
    ]
    for name in ["train_additions", "dev_b"]:
        (tmp_path / name / "features").mkdir(parents=True)
    (tmp_path / "train_additions/features/old.receipt.json").write_text("{}")
    active = 0
    lock = threading.Lock()
    calls: list[str] = []
    preflights: list[Path] = []
    validations: list[Path] = []

    def task(package: str, row: dict[str, Any]) -> dict[str, Any]:
        nonlocal active
        with lock:
            active += 1
        calls.append(row["sample_id"])
        time.sleep(0.02)
        (Path(package) / "features" / (row["sample_id"] + ".receipt.json")).write_text("{}")
        with lock:
            active -= 1
        return dict(row, status="COMPLETE")

    def validate(package: Path, *args: Any, **kwargs: Any) -> dict[str, Any]:
        assert active == 0
        validations.append(package)
        return {"structural_pass": True, "scoped_pending": 0}

    monkeypatch.setattr(parallel, "preflight", preflights.append)
    monkeypatch.setattr(parallel, "work_plan", lambda root: batches)
    monkeypatch.setattr(parallel, "process_sequence", task)
    monkeypatch.setattr(
        parallel, "ProcessPoolExecutor", lambda **kwargs: ThreadPoolExecutor(max_workers=2)
    )
    monkeypatch.setattr(parallel.serial, "validate", validate)
    monkeypatch.setattr(parallel.serial, "inventory", lambda root: {"prepared": len(calls)})
    monkeypatch.setattr(parallel.serial, "full_validate", lambda *args: {"status": "PASS"})
    assert parallel.prepare(tmp_path)["status"] == "PASS"
    assert set(calls) == {"new", "dev"} and len(validations) == 2
    assert parallel.prepare(tmp_path)["status"] == "PASS"
    assert len(calls) == 2 and len(validations) == 2 and len(preflights) == 2
