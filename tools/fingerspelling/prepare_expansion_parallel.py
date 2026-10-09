"""Two isolated, low-priority workers; frozen extraction and I/O contracts unchanged.

One shared OS socket protects the root even if the coordinator dies. At most two clips
are in flight. Scoped validation runs only at idle two-batch barriers: the unchanged
validator deliberately refuses unknown staging NPZ files. No training/TEST commands.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import json
import multiprocessing as mp
import os
import signal
import socket
import threading
import time
from collections.abc import Iterator
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from multiprocessing.util import Finalize
from pathlib import Path
from typing import Any

from pipeline.fingerspelling.adapter import identity, sha256
from pipeline.fingerspelling.package_io import recover_partial
from pipeline.fingerspelling.sequence_manifest import REPO
from tools.fingerspelling import prepare_expansion as serial
from tools.fingerspelling.tranche import EXECUTION, atomic_json, event

CONFIG = REPO / "pipeline/config/fingerspelling_parallel_execution_v1.json"
GATE = REPO / "artifacts/fingerspelling_parallel_preparation_01/parallel_smoke.json"
_CACHE: dict[str, Any] = {}
_STOP: Any = None
_LEASE: socket.socket | None = None
_FINALIZER: Any = None


def policy() -> dict[str, Any]:
    p: dict[str, Any] = json.loads(CONFIG.read_text())
    if (
        p["schema_version"] != "apphear.fingerspelling.parallel_execution.v1"
        or p["workers"] != 2
        or p["maximum_workers"] != 2
        or p["worker_priority"] != "BELOW_NORMAL"
        or p["batch_wave_count"] != 2
        or p["inflight_sequences_maximum"] != 2
        or p["test_access"] != "SEALED"
    ):
        raise ValueError("[parallel-preparation/config] Fixed two-worker policy required")
    return p


def code_identity() -> dict[str, Any]:
    names = [
        "tools/fingerspelling/prepare_expansion_parallel.py",
        "pipeline/config/fingerspelling_parallel_execution_v1.json",
        "tools/fingerspelling/parallel_preparation_smoke.py",
        "tools/fingerspelling/prepare_expansion.py",
        "tools/fingerspelling/foundation.py",
        "pipeline/fingerspelling/sequence_package.py",
        "pipeline/fingerspelling/storage.py",
    ]
    return {"code_sha256": {n: sha256(REPO / n) for n in names}, "adapter": identity()}


def check_gate() -> None:
    report = json.loads(GATE.read_text())
    if (
        report["code_identity"] != code_identity()
        or not report["exact_raw_feature_parity"]
        or not report["structural_pass"]
        or not report["two_workers_overlap"]
        or not report["speedup_supported"]
        or report["test_accessed"]
    ):
        raise ValueError("[parallel-preparation/gate] Passing unchanged real smoke required")


def lock_port(root: Path) -> int:
    # Must match tranche.single_writer exactly; inherited socket keeps that same lease.
    return (
        40000
        + int(hashlib.sha256(str(root.resolve()).lower().encode()).hexdigest()[:4], 16) % 20000
    )


@contextlib.contextmanager
def shared_writer(root: Path) -> Iterator[socket.socket]:
    sock = socket.socket()
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        sock.bind(("127.0.0.1", lock_port(root)))
    except OSError as exc:
        sock.close()
        raise RuntimeError(
            "[parallel-preparation/owner] Another writer is active; stop it gracefully first"
        ) from exc
    try:
        yield sock
    finally:
        sock.close()


def available_ram_gib() -> float:
    class Memory(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("load", ctypes.c_ulong),
            ("total", ctypes.c_ulonglong),
            ("available", ctypes.c_ulonglong),
            ("total_page", ctypes.c_ulonglong),
            ("available_page", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("reserved", ctypes.c_ulonglong),
        ]

    if os.name != "nt":
        raise ValueError("[parallel-preparation/platform] Validated Windows execution only")
    state = Memory()
    state.length = ctypes.sizeof(state)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
        raise OSError("[parallel-preparation/resources] Cannot read available RAM")
    return float(state.available / 2**30)


def resources() -> dict[str, Any]:
    p = policy()
    cpus, memory = os.cpu_count() or 1, available_ram_gib()
    if cpus < p["minimum_logical_processors"] or memory < p["minimum_available_ram_gib"]:
        raise ValueError("[parallel-preparation/resources] Insufficient moderate-worker headroom")
    return {"logical_processors": cpus, "available_ram_gib": memory, "workers": 2}


def _close_worker() -> None:
    if "runtime" in _CACHE:
        _CACHE["runtime"].close()
    if _LEASE is not None:
        _LEASE.close()


def _watch_parent() -> None:
    parent = mp.parent_process()
    while True:
        time.sleep(1)
        if parent is not None and not parent.is_alive():
            # No orphan may keep writing after coordinator death. Staging is preserved.
            os._exit(1)


def initialize_worker(stop: Any, lease: socket.socket | None) -> None:
    global _STOP, _LEASE, _FINALIZER
    _STOP, _LEASE = stop, lease
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    if os.name == "nt":
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        if not kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000):
            raise OSError("[parallel-preparation/priority] Below-normal priority failed")
    _FINALIZER = Finalize(None, _close_worker, exitpriority=10)
    threading.Thread(target=_watch_parent, daemon=True).start()


def process_sequence(package: str, row: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    result: dict[str, Any] = {
        "sample_id": row["sample_id"],
        "role": row["split_role"],
        "worker_pid": os.getpid(),
        "started": started,
    }
    if row["split_role"] not in {"TRAIN", "DEV"}:
        raise ValueError("[parallel-preparation/role] Protected role refused")
    try:
        if _STOP.is_set():
            return dict(result, status="INTERRUPTED")
        output = Path(package)
        for attempt in range(EXECUTION["download_attempts"]):
            try:
                serial.acquire(output, [row])
                break
            except OSError:
                if attempt + 1 == EXECUTION["download_attempts"]:
                    raise
                if _STOP.wait(EXECUTION["retry_backoff_seconds"] * (attempt + 1)):
                    return dict(result, status="INTERRUPTED")
        if _STOP.is_set():
            return dict(result, status="INTERRUPTED")
        serial.extract(output, [row], _CACHE)
        return dict(result, status="COMPLETE", ended=time.perf_counter())
    except Exception as exc:
        return dict(result, status="FAILED", error=str(exc), type=type(exc).__name__)


def wave(
    pool: Any, stop: Any, tasks: list[tuple[Path, dict[str, Any]]], on_result: Any
) -> list[dict[str, Any]]:
    """At most two futures, with no validation until all writes in this wave settle."""
    remaining, pending, results = iter(tasks), {}, []

    def submit() -> None:
        if not stop.is_set():
            item = next(remaining, None)
            if item is not None:
                package, row = item
                pending[pool.submit(process_sequence, str(package), row)] = row["sample_id"]

    submit()
    submit()
    interrupted = False
    while pending:
        try:
            done, _ = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)
            for future in done:
                sid = pending.pop(future)
                try:
                    result = future.result()
                except Exception as exc:
                    result = {
                        "sample_id": sid,
                        "status": "FAILED",
                        "error": str(exc),
                        "type": type(exc).__name__,
                    }
                if result["sample_id"] != sid:
                    raise ValueError("[parallel-preparation/identity] Worker returned wrong sample")
                results.append(result)
                if result["status"] != "COMPLETE":
                    stop.set()
                on_result(result)
            for _ in done:
                submit()
        except KeyboardInterrupt:
            interrupted = True
            stop.set()  # Current clips finish; do not kill writers mid-commit.
        except BaseException:
            stop.set()
            raise
    if interrupted:
        raise KeyboardInterrupt
    return results


def recover_staging(root: Path) -> None:
    """Quarantine only exact, manifest-owned uncommitted stages while holding root lease."""
    for name in serial.PACKAGES["ALL"]:
        output = root / name
        for row in serial.rows(name):
            sid = row["sample_id"]
            candidates = [
                output / "videos" / (row["filename"] + ".download"),
                output / "videos" / (row["filename"] + ".unpacked"),
                output / "raw" / (sid + ".raw-v1.pending.npz"),
                output / "raw" / (sid + ".receipt.json.pending"),
                output / "features" / (sid + ".pending.npz"),
                output / "features" / (sid + ".receipt.json.pending"),
            ]
            recover_partial(output, candidates, "Interrupted known parallel staging; preserved")


def work_plan(root: Path) -> list[dict[str, Any]]:
    by_id = {r["sample_id"]: r for n in serial.PACKAGES["ALL"] for r in serial.rows(n)}
    plan = json.loads((serial.OUTPUT / "batch_plan.json").read_text())
    seen, paths, batches = set(), set(), []
    for index, batch in enumerate(plan["batches"]):
        name = batch["package"]
        if name not in serial.PACKAGES["ALL"] or not 1 <= len(batch["sample_ids"]) <= 16:
            raise ValueError("[parallel-preparation/plan] Invalid frozen batch")
        selected = []
        for sid in batch["sample_ids"]:
            row = by_id[sid]
            path_key = (name, row["filename"])
            expected_role = "TRAIN" if name == "train_additions" else "DEV"
            if sid in seen or path_key in paths or row["split_role"] != expected_role:
                raise ValueError("[parallel-preparation/plan] Duplicate writer or wrong role")
            seen.add(sid)
            paths.add(path_key)
            selected.append(row)
        batches.append({"index": index, "package": name, "rows": selected})
    if seen != set(by_id):
        raise ValueError("[parallel-preparation/plan] Frozen coverage incomplete")
    return batches


def preflight(root: Path) -> dict[str, Any]:
    check_gate()
    hardware = resources()
    serial.validate_plan()
    serial.initialize(root, serial.PACKAGES["ALL"])
    recover_staging(root)
    base = serial.preflight(root, serial.PACKAGES["ALL"])
    profile = {"policy": policy(), "code_identity": code_identity(), "gate_sha256": sha256(GATE)}
    path = root / "execution/parallel/implementation_identity.json"
    if path.exists() and json.loads(path.read_text()) != profile:
        raise ValueError("[parallel-preparation/resume] Parallel implementation identity changed")
    atomic_json(path, profile)
    work_plan(root)
    return dict(base, parallel="TWO_WORKER_PREFLIGHT_PASS", resources=hardware)


def prepare(root: Path) -> dict[str, Any]:
    with shared_writer(root) as lease:
        preflight(root)
        batches = work_plan(root)
        failure_path = root / "execution/failures.json"
        failures = json.loads(failure_path.read_text()) if failure_path.exists() else {}
        known = {r["sample_id"] for b in batches for r in b["rows"]}
        if set(failures) - known:
            raise ValueError("[parallel-preparation/failures] Unknown failure identity")
        context = mp.get_context("spawn")
        stop = context.Event()
        with ProcessPoolExecutor(
            max_workers=2,
            mp_context=context,
            initializer=initialize_worker,
            initargs=(stop, lease),
        ) as pool:
            try:
                for offset in range(0, len(batches), 2):
                    group = batches[offset : offset + 2]
                    tasks = []
                    changed_batches = []
                    for batch in group:
                        package = root / batch["package"]
                        missing = []
                        for row in batch["rows"]:
                            if (
                                package / "features" / (row["sample_id"] + ".receipt.json")
                            ).is_file():
                                failures.pop(row["sample_id"], None)
                            else:
                                tasks.append((package, row))
                                missing.append(row)
                        if missing:
                            changed_batches.append(batch)
                            event(
                                root,
                                "BATCH_START",
                                index=batch["index"],
                                package=batch["package"],
                                pending=len(missing),
                                workers=2,
                            )
                    if not tasks:
                        atomic_json(failure_path, failures)
                        continue  # Full resume preflight already validated these old batches.

                    def record(result: dict[str, Any]) -> None:
                        sid = result["sample_id"]
                        if result["status"] == "COMPLETE":
                            failures.pop(sid, None)
                            event(root, "SEQUENCE_COMPLETE", **result)
                        elif result["status"] == "FAILED":
                            failures[sid] = result
                            event(root, "SEQUENCE_FAILED", **result)
                        atomic_json(failure_path, failures)

                    outcomes = wave(pool, stop, tasks, record)
                    if any(r["status"] != "COMPLETE" for r in outcomes):
                        raise RuntimeError(
                            "[parallel-preparation/batch] Incomplete wave; rerun to resume"
                        )
                    # No workers write now; *.pending.npz cannot race scoped validation.
                    for batch in changed_batches:
                        package = root / batch["package"]
                        selected = {r["sample_id"] for r in batch["rows"]}
                        checked = serial.validate(
                            package,
                            package / "tranche_manifest.json",
                            receipt_ids=selected,
                            report_path=package
                            / "execution/parallel/batches"
                            / f"{batch['index']:04d}.validation.json",
                        )
                        if not checked["structural_pass"] or checked["scoped_pending"]:
                            raise ValueError(
                                "[parallel-preparation/validation] Batch integrity failed"
                            )
                        event(
                            root,
                            "BATCH_VALIDATED",
                            index=batch["index"],
                            package=batch["package"],
                            workers=2,
                        )
                    atomic_json(root / "execution/progress.json", serial.inventory(root))
            except BaseException:
                stop.set()
                atomic_json(root / "execution/progress.json", serial.inventory(root))
                event(
                    root,
                    "RUN_STOPPED",
                    action="Rerun identical command; completed artifacts retained",
                )
                raise
        result = serial.full_validate(root, serial.PACKAGES["ALL"])
        atomic_json(root / "execution/progress.json", serial.inventory(root))
        event(root, "RUN_END", status=result["status"], workers=2)
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "prepare", "status", "validate"])
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    root = serial.root_path(args.destination)
    if args.command == "prepare":
        result = prepare(root)
    elif args.command == "status":
        serial.validate_plan()
        result = serial.inventory(root)
    else:
        with shared_writer(root):
            result = (
                preflight(root)
                if args.command == "preflight"
                else serial.full_validate(root, serial.PACKAGES["ALL"])
            )
    print(json.dumps(result, indent=2))
    if (
        args.command == "validate"
        and result["status"] != "SELECTED_PACKAGES_MATERIALIZED_INTEGRITY_PASS"
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
