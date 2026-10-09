"""Bounded six-TRAIN-clip two/three-worker byte-parity and throughput gate.

Copies already governed sources into new local fixtures; never downloads or mutates
the foundation, external preparation, models, or TEST. This is not a training run.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import shutil
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.fingerspelling.sequence_manifest import REPO
from tools.fingerspelling import prepare_expansion_three as parallel
from tools.fingerspelling.tranche import atomic_json


def arrays_equal(first: Path, second: Path) -> bool:
    with np.load(first, allow_pickle=False) as a, np.load(second, allow_pickle=False) as b:
        keys = {k for k in a.files if k != "metadata_json"}
        if keys != {k for k in b.files if k != "metadata_json"}:
            return False
        return all(
            a[k].dtype == b[k].dtype
            and a[k].shape == b[k].shape
            and a[k].tobytes() == b[k].tobytes()
            for k in keys
        )


def main() -> None:
    foundation = REPO / "datasets/fingerspelling/foundation_01"
    manifest = json.loads((foundation / "tranche_manifest.json").read_text())
    selected: list[dict[str, Any]] = []
    for stratum in ["DAUN", "MacKenzie"]:
        seen: set[str] = set()
        for row in manifest["samples"]:
            if (
                row["split_role"] != "TRAIN"
                or row["source_stratum"] != stratum
                or not 3 <= row["source_duration_metadata_s"] <= 6
                or row["official_signer_id"] in seen
            ):
                continue
            receipt = json.loads(
                (foundation / "features" / (row["sample_id"] + ".receipt.json")).read_text()
            )
            source = REPO / receipt["source_path"]
            raw = REPO / receipt["raw_path"]
            if not source.is_relative_to(foundation) or not raw.is_relative_to(foundation):
                continue
            selected.append(row)
            seen.add(row["official_signer_id"])
            if len(seen) == 3:
                break
        if len(seen) != 3:
            raise ValueError("Six ordinary TRAIN sources from both strata required")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    root = REPO / ".codex_tmp" / ("three_worker_smoke_" + stamp)
    root.mkdir()
    timings, outcomes, checks = {}, {}, {}
    context = mp.get_context("spawn")
    for name, workers in [("two", 2), ("three", 3)]:
        package = root / name
        (package / "videos").mkdir(parents=True)
        atomic_json(package / "tranche_manifest.json", dict(manifest, samples=selected))
        for row in selected:
            receipt = json.loads(
                (foundation / "features" / (row["sample_id"] + ".receipt.json")).read_text()
            )
            shutil.copyfile(REPO / receipt["source_path"], package / "videos" / row["filename"])
        stop = context.Event()
        started = time.perf_counter()
        with parallel.shared_writer(package) as lease:
            with ProcessPoolExecutor(
                max_workers=workers,
                mp_context=context,
                initializer=parallel.initialize_worker,
                initargs=(stop, lease),
            ) as pool:
                results = parallel.wave(pool, stop, [(package, r) for r in selected], print)
        timings[name] = time.perf_counter() - started
        if any(r["status"] != "COMPLETE" for r in results):
            raise ValueError(f"Failed real extraction: {results}")
        outcomes[name] = results
        checks[name] = parallel.serial.validate(
            package,
            package / "tranche_manifest.json",
            receipt_ids={r["sample_id"] for r in selected},
            report_path=package / "smoke.validation.json",
        )
    comparisons = []
    for row in selected:
        sid = row["sample_id"]
        old = json.loads((foundation / "features" / (sid + ".receipt.json")).read_text())
        comparison: dict[str, Any] = {"sample_id": sid, "source_stratum": row["source_stratum"]}
        for kind, suffix, old_key in [
            ("raw", ".raw-v1.npz", "raw_path"),
            ("features", ".npz", "features_path"),
        ]:
            a, b = [root / n / kind / (sid + suffix) for n in ["two", "three"]]
            comparison[kind + "_two_three_bytes_equal"] = arrays_equal(a, b)
            comparison[kind + "_original_bytes_equal"] = arrays_equal(a, REPO / old[old_key])
        comparisons.append(comparison)
    runs = outcomes["three"]
    overlap = any(
        a["worker_pid"] != b["worker_pid"]
        and max(a["started"], b["started"]) < min(a["ended"], b["ended"])
        for a in runs
        for b in runs
    )
    worker_pids = {r["worker_pid"] for r in runs}
    overlap = overlap and len(worker_pids) == 3
    resource_pass = all(
        r["worker_logical_cpu_count"] == 8 and r["worker_priority_class"] == 0x4000
        for results in outcomes.values()
        for r in results
    )
    report = {
        "schema_version": "apphear.fingerspelling.parallel_preparation_smoke.v1",
        "code_identity": parallel.code_identity(),
        "selection": "First 3–6-second foundation-owned TRAIN clips, three signers per stratum; metadata only",
        "fixture_root": str(root),
        "timings_seconds": timings,
        "speedup_ratio": timings["two"] / timings["three"],
        "speedup_supported": timings["three"] < timings["two"],
        "exact_raw_feature_parity": all(
            all(value for key, value in c.items() if key.endswith("bytes_equal"))
            for c in comparisons
        ),
        "structural_pass": all(
            c["structural_pass"] and not c["scoped_pending"] for c in checks.values()
        ),
        "three_workers_overlap": overlap,
        "worker_resource_policy_pass": resource_pass,
        "comparisons": comparisons,
        "outcomes": outcomes,
        "test_accessed": False,
        "candidate_threads": "UNCHANGED_FROZEN_DEFAULTS",
        "priority": "BELOW_NORMAL_BOTH_CONDITIONS",
        "worker_affinity_logical_cpus": 8,
        "reserved_logical_cpus": 4,
    }
    atomic_json(parallel.GATE, report)
    print(json.dumps(report, indent=2))
    parallel.check_gate()


if __name__ == "__main__":
    main()
