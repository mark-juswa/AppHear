"""Opt-in three-worker preparation, low priority, eight-of-twelve CPU affinity.

The validated two-worker module remains immutable. Reuse its frozen worker/extraction,
root lease, recovery and manifest checks; only scheduling/profile differs here.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import multiprocessing as mp
import os
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path
from typing import Any

from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.sequence_manifest import REPO
from tools.fingerspelling import prepare_expansion_parallel as two
from tools.fingerspelling.prepare_expansion_parallel import (
    available_ram_gib,
    recover_staging,
    serial,
    shared_writer,
    work_plan,
)
from tools.fingerspelling.tranche import atomic_json, event

CONFIG = REPO / "pipeline/config/fingerspelling_three_worker_execution_v1.json"
GATE = REPO / "artifacts/fingerspelling_three_worker_preparation_01/parallel_smoke.json"


def code_identity() -> dict[str, Any]:
    base = two.code_identity()
    for name in [
        "tools/fingerspelling/prepare_expansion_three.py",
        "tools/fingerspelling/three_worker_preparation_smoke.py",
        "pipeline/config/fingerspelling_three_worker_execution_v1.json",
    ]:
        base["code_sha256"][name] = sha256(REPO / name)
    return base


def affinity_mask(allowed: int) -> int:
    bits = [1 << i for i in range(allowed.bit_length()) if allowed & (1 << i)]
    if len(bits) < 12:
        raise ValueError("[three-worker/resources] At least twelve available logical CPUs required")
    return sum(bits[:8])  # At least four logical CPUs excluded from worker execution.


def initialize_worker(stop: Any, lease: Any) -> None:
    two.initialize_worker(stop, lease)
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.GetProcessAffinityMask.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    current, system = ctypes.c_size_t(), ctypes.c_size_t()
    handle = kernel.GetCurrentProcess()
    if not kernel.GetProcessAffinityMask(handle, ctypes.byref(current), ctypes.byref(system)):
        raise OSError("[three-worker/affinity] Cannot read allowed CPU set")
    mask = affinity_mask(current.value)
    if not kernel.SetProcessAffinityMask(handle, mask):
        raise OSError("[three-worker/affinity] Cannot reserve foreground CPU headroom")


def process_sequence(package: str, row: dict[str, Any]) -> dict[str, Any]:
    result = two.process_sequence(package, row)
    current, system = ctypes.c_size_t(), ctypes.c_size_t()
    kernel = ctypes.windll.kernel32
    handle = kernel.GetCurrentProcess()
    if not kernel.GetProcessAffinityMask(handle, ctypes.byref(current), ctypes.byref(system)):
        raise OSError("[three-worker/affinity] Cannot verify worker CPU set")
    kernel.GetPriorityClass.argtypes = [ctypes.c_void_p]
    result["worker_logical_cpu_count"] = current.value.bit_count()
    result["worker_affinity_mask"] = current.value
    result["worker_priority_class"] = kernel.GetPriorityClass(handle)
    return result


def policy() -> dict[str, Any]:
    p: dict[str, Any] = json.loads(CONFIG.read_text())
    if (
        p["schema_version"] != "apphear.fingerspelling.parallel_execution.v1"
        or p["workers"] != 3
        or p["maximum_workers"] != 3
        or p["worker_priority"] != "BELOW_NORMAL"
        or p["batch_wave_count"] != 3
        or p["inflight_sequences_maximum"] != 3
        or p["test_access"] != "SEALED"
        or p["worker_logical_cpu_limit"] != 8
        or p["reserve_logical_cpus"] != 4
    ):
        raise ValueError("[parallel-preparation/config] Fixed three-worker policy required")
    return p


def check_gate() -> None:
    report = json.loads(GATE.read_text())
    if (
        report["code_identity"] != code_identity()
        or not report["exact_raw_feature_parity"]
        or not report["structural_pass"]
        or not report["three_workers_overlap"]
        or not report["worker_resource_policy_pass"]
        or not report["speedup_supported"]
        or report["test_accessed"]
    ):
        raise ValueError("[parallel-preparation/gate] Passing unchanged real smoke required")


def resources() -> dict[str, Any]:
    p = policy()
    cpus, memory = os.cpu_count() or 1, available_ram_gib()
    if cpus < p["minimum_logical_processors"] or memory < p["minimum_available_ram_gib"]:
        raise ValueError("[parallel-preparation/resources] Insufficient moderate-worker headroom")
    return {"logical_processors": cpus, "available_ram_gib": memory, "workers": 3}


def wave(
    pool: Any, stop: Any, tasks: list[tuple[Path, dict[str, Any]]], on_result: Any
) -> list[dict[str, Any]]:
    """At most three futures, with no validation until all writes in this wave settle."""
    remaining, pending, results = iter(tasks), {}, []

    def submit() -> None:
        if not stop.is_set():
            item = next(remaining, None)
            if item is not None:
                package, row = item
                pending[pool.submit(process_sequence, str(package), row)] = row["sample_id"]

    submit()
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


def preflight(root: Path) -> dict[str, Any]:
    check_gate()
    hardware = resources()
    serial.validate_plan()
    serial.initialize(root, serial.PACKAGES["ALL"])
    recover_staging(root)
    base = serial.preflight(root, serial.PACKAGES["ALL"])
    profile = {"policy": policy(), "code_identity": code_identity(), "gate_sha256": sha256(GATE)}
    path = root / "execution/parallel3/implementation_identity.json"
    if path.exists() and json.loads(path.read_text()) != profile:
        raise ValueError("[parallel-preparation/resume] Parallel implementation identity changed")
    atomic_json(path, profile)
    work_plan(root)
    return dict(base, parallel="THREE_WORKER_PREFLIGHT_PASS", resources=hardware)


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
            max_workers=3,
            mp_context=context,
            initializer=initialize_worker,
            initargs=(stop, lease),
        ) as pool:
            try:
                for offset in range(0, len(batches), 3):
                    group = batches[offset : offset + 3]
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
                                workers=3,
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
                            / "execution/parallel3/batches"
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
                            workers=3,
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
        event(root, "RUN_END", status=result["status"], workers=3)
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
