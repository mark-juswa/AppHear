"""Bounded warm two/three-worker parity/throughput check using existing TRAIN only."""

from __future__ import annotations

import ctypes
import json
import multiprocessing as mp
import shutil
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from pipeline.fingerspelling.sequence_manifest import REPO
from tools.fingerspelling import prepare_expansion_balanced as balanced
from tools.fingerspelling import prepare_expansion_parallel as two
from tools.fingerspelling.parallel_preparation_smoke import arrays_equal
from tools.fingerspelling.tranche import atomic_json

_READY: Any = None


def initialize_warm(
    stop: Any, lease: Any, ready: Any, count: Any, workers: int, source: str
) -> None:
    """Initialize unchanged Candidate01 once, then signal all workers ready before timing."""
    from pipeline.perception_vnext.offline_candidate01 import Candidate01Offline, iter_video_frames

    global _READY
    _READY = ready
    balanced.initialize_worker(stop, lease)
    two._CACHE["runtime"] = Candidate01Offline()
    frames, _ = iter_video_frames(Path(source), None)
    iterator = iter(frames)
    try:
        _, _, _, rgb = next(iterator)
        two._CACHE["runtime"].process_rgb(rgb)
    finally:
        close = getattr(iterator, "close", None)
        if close is not None:
            close()
    with count.get_lock():
        count.value += 1
        if count.value == workers:
            ready.set()


def wait_ready() -> bool:
    return bool(_READY.wait(120))


def system_ticks() -> tuple[int, int, int]:
    class FileTime(ctypes.Structure):
        _fields_ = [("lo", ctypes.c_ulong), ("hi", ctypes.c_ulong)]

    values = [FileTime(), FileTime(), FileTime()]
    if not ctypes.windll.kernel32.GetSystemTimes(*(ctypes.byref(x) for x in values)):
        raise OSError("Cannot measure system CPU")
    ticks = [x.lo + (x.hi << 32) for x in values]
    return ticks[0], ticks[1], ticks[2]


def main() -> None:
    foundation = REPO / "datasets/fingerspelling/foundation_01"
    manifest = json.loads((foundation / "tranche_manifest.json").read_text())
    # Same six already reviewed source identities as the prior bounded scheduling gate.
    prior = json.loads(
        (
            REPO / "artifacts/fingerspelling_three_worker_preparation_01/parallel_smoke.json"
        ).read_text()
    )
    ids = {r["sample_id"] for r in prior["comparisons"]}
    selected = [r for r in manifest["samples"] if r["sample_id"] in ids]
    if len(selected) != 6 or any(r["split_role"] != "TRAIN" for r in selected):
        raise ValueError("Six fixed existing TRAIN sources required")
    root = REPO / ".codex_tmp" / ("balanced_smoke_" + time.strftime("%Y%m%d_%H%M%S"))
    root.mkdir()
    context = mp.get_context("spawn")
    timings, outcomes, checks, cpu, startup = {}, {}, {}, {}, {}
    for name, workers in [("two", 2), ("three", 3)]:
        package = root / name
        (package / "videos").mkdir(parents=True)
        atomic_json(package / "tranche_manifest.json", dict(manifest, samples=selected))
        for row in selected:
            receipt = json.loads(
                (foundation / "features" / (row["sample_id"] + ".receipt.json")).read_text()
            )
            shutil.copyfile(REPO / receipt["source_path"], package / "videos" / row["filename"])
        stop, ready, count = context.Event(), context.Event(), context.Value("i", 0)
        cold_started = time.perf_counter()
        with balanced.shared_writer(package) as lease:
            with ProcessPoolExecutor(
                max_workers=workers,
                mp_context=context,
                initializer=initialize_warm,
                initargs=(
                    stop,
                    lease,
                    ready,
                    count,
                    workers,
                    str(package / "videos" / selected[0]["filename"]),
                ),
            ) as pool:
                warming = [pool.submit(wait_ready) for _ in range(workers)]
                if not ready.wait(120) or not all(f.result(timeout=5) for f in warming):
                    raise ValueError("All worker models must initialize before timed work")
                startup[name] = time.perf_counter() - cold_started
                a, started = system_ticks(), time.perf_counter()
                results = balanced.wave(pool, stop, [(package, r) for r in selected], print)
                timings[name] = time.perf_counter() - started
                b = system_ticks()
                delta = [y - x for x, y in zip(a, b, strict=True)]
                cpu[name] = 100 * (1 - delta[0] / (delta[1] + delta[2]))
        if any(r["status"] != "COMPLETE" for r in results):
            raise ValueError(f"Worker failure: {results}")
        outcomes[name] = results
        checks[name] = balanced.serial.validate(
            package,
            package / "tranche_manifest.json",
            receipt_ids=ids,
            report_path=package / "smoke.validation.json",
        )
    comparisons = []
    for row in selected:
        sid = row["sample_id"]
        old = json.loads((foundation / "features" / (sid + ".receipt.json")).read_text())
        record: dict[str, Any] = {"sample_id": sid, "source_stratum": row["source_stratum"]}
        for kind, suffix, old_key in [
            ("raw", ".raw-v1.npz", "raw_path"),
            ("features", ".npz", "features_path"),
        ]:
            a, b = [root / n / kind / (sid + suffix) for n in ["two", "three"]]
            record[kind + "_two_three_bytes_equal"] = arrays_equal(a, b)
            record[kind + "_original_bytes_equal"] = arrays_equal(a, REPO / old[old_key])
        comparisons.append(record)
    runs = outcomes["three"]
    overlap = len({r["worker_pid"] for r in runs}) == 3 and any(
        a["worker_pid"] != b["worker_pid"]
        and max(a["started"], b["started"]) < min(a["ended"], b["ended"])
        for a in runs
        for b in runs
    )
    report = {
        "schema_version": "apphear.fingerspelling.warm_preparation_smoke.v1",
        "code_identity": balanced.code_identity(),
        "fixture_root": str(root),
        "warm_timings_seconds": timings,
        "startup_seconds": startup,
        "system_average_cpu_percent": cpu,
        "speedup_ratio": timings["two"] / timings["three"],
        "speedup_supported": timings["three"] < timings["two"],
        "exact_raw_feature_parity": all(
            all(v for k, v in c.items() if k.endswith("bytes_equal")) for c in comparisons
        ),
        "structural_pass": all(
            c["structural_pass"] and not c["scoped_pending"] for c in checks.values()
        ),
        "three_workers_overlap": overlap,
        "worker_resource_policy_pass": all(
            r["worker_logical_cpu_count"] == 10 and r["worker_priority_class"] == 0x4000
            for group in outcomes.values()
            for r in group
        ),
        "worker_cpu_limit": 10,
        "reserved_logical_cpus": 2,
        "candidate_threads": "UNCHANGED_FROZEN_DEFAULTS",
        "test_accessed": False,
        "comparisons": comparisons,
        "outcomes": outcomes,
    }
    atomic_json(balanced.GATE, report)
    print(json.dumps(report, indent=2))
    balanced.check_gate()


if __name__ == "__main__":
    main()
