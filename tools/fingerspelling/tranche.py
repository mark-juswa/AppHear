"""Serial resumable preparation of ONLY the frozen FSboard TRAIN/DEV tranche."""

from __future__ import annotations

import argparse
import contextlib
import importlib.metadata
import json
import os
import shutil
import socket
import sys
import time
from pathlib import Path
from typing import Any

from pipeline.fingerspelling.adapter import identity, sha256
from pipeline.fingerspelling.sequence_manifest import ADMISSION, REPO
from pipeline.fingerspelling.sequence_package import ASSETS, PREPROCESSING, validate
from tools.fingerspelling.foundation import DEFAULT_OUTPUT, acquire, extract

EXECUTION_PATH = REPO / "pipeline/config/fingerspelling_execution_v1.json"
EXECUTION = json.loads(EXECUTION_PATH.read_text())


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stage = path.with_name(path.name + ".pending")
    with stage.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    stage.replace(path)


def event(output: Path, kind: str, **data: Any) -> None:
    value = {"time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": kind, **data}
    folder = output / "execution"
    folder.mkdir(exist_ok=True)
    with (folder / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value) + "\n")
    print(json.dumps(value), flush=True)


def frozen_rows(output: Path) -> list[dict[str, Any]]:
    path = output / "tranche_manifest.json"
    actual = identity()
    if sha256(path) != EXECUTION["frozen_manifest_sha256"] or (
        actual["config_sha256"] != EXECUTION["frozen_adapter_config_sha256"]
        or actual["implementation_sha256"] != EXECUTION["frozen_adapter_source_sha256"]
        or actual["columns_sha256"] != EXECUTION["frozen_column_order_sha256"]
    ):
        raise ValueError("[fingerspelling/preflight] Frozen manifest/adapter changed")
    manifest = json.loads(path.read_text())
    rows: list[dict[str, Any]] = manifest["samples"]
    if len(rows) != 1280 or any(r["split_role"] not in {"TRAIN", "DEV"} for r in rows):
        raise ValueError("[fingerspelling/preflight] Unexpected inventory or protected role")
    return rows


def inventory(output: Path) -> dict[str, Any]:
    """Fast progress inventory, not a substitute for full hash/recompute validation."""
    rows = frozen_rows(output)
    counts = {"TRAIN": 0, "DEV": 0}
    completed = set()
    adapter_identity = identity()
    for row in rows:
        path = output / "features" / f"{row['sample_id']}.receipt.json"
        if path.is_file():
            rec = json.loads(path.read_text())
            if (
                rec["sample_id"] == row["sample_id"]
                and rec["adapter"] == adapter_identity
                and (REPO / rec["features_path"]).is_file()
            ):
                counts[row["split_role"]] += 1
                completed.add(row["sample_id"])
    failure_path = output / "execution/failures.json"
    failures = json.loads(failure_path.read_text()) if failure_path.is_file() else {}
    unresolved = {sid: detail for sid, detail in failures.items() if sid not in completed}
    disk_used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    free = shutil.disk_usage(output).free
    return {
        "schema_version": "apphear.fingerspelling.tranche_status.v1",
        "prepared_receipt_counts": counts,
        "target_counts": {"TRAIN": 1024, "DEV": 256},
        "pending": len(rows) - len(completed),
        "failures": unresolved,
        "package_disk_bytes": disk_used,
        "free_destination_bytes": free,
        "scope": "FAST_RECEIPT_INVENTORY_NOT_FRESH_HASH_VALIDATION",
    }


def preflight(output: Path, require_bulk_space: bool = True) -> dict[str, Any]:
    rows = frozen_rows(output)
    for name, expected in PREPROCESSING.items():
        if sha256(REPO / "pipeline/perception_vnext" / name) != expected:
            raise ValueError("[fingerspelling/preflight] Frozen Candidate01 source changed")
    from pipeline.perception_vnext.offline_candidate01 import DEFAULT_ONNX, DEFAULT_REFINER

    for path in [DEFAULT_ONNX, DEFAULT_REFINER]:
        if sha256(path) != ASSETS[path.name]:
            raise ValueError("[fingerspelling/preflight] Candidate01 asset hash mismatch")
    checked = validate(output, output / "tranche_manifest.json")
    if not checked["structural_pass"]:
        raise ValueError(
            "[fingerspelling/preflight] Structural errors: " + str(checked["structural_errors"])
        )
    probe = output / "execution" / f".writable-probe-{os.getpid()}-{time.time_ns()}"
    probe.parent.mkdir(exist_ok=True)
    with probe.open("xb") as stream:
        stream.write(b"AppHear write preflight")
    probe.unlink()
    pending_bytes, pending_duration = 0, 0.0
    for row in rows:
        if not (output / "features" / f"{row['sample_id']}.receipt.json").is_file():
            pending_duration += row["source_duration_metadata_s"]
        if (
            not (output / "videos" / row["filename"]).is_file()
            and not (ADMISSION / "videos" / row["filename"]).is_file()
        ):
            pending_bytes += row["file_size_bytes"]
    needed = (
        pending_bytes
        + int(pending_duration * EXECUTION["derived_bytes_per_metadata_second_estimate"])
        + EXECUTION["disk_reserve_bytes"]
    )
    free = shutil.disk_usage(output).free
    packages = {
        n: importlib.metadata.version(n)
        for n in ["numpy", "opencv-python", "onnxruntime", "tensorflow", "keras"]
    }
    result = {
        "schema_version": "apphear.fingerspelling.preflight.v1",
        "python": sys.version,
        "packages": packages,
        "adapter": identity(),
        "manifest_sha256": sha256(output / "tranche_manifest.json"),
        "candidate01_assets": ASSETS,
        "destination": str(output),
        "writable": True,
        "structural_pass": True,
        "pending_rgb_bytes": pending_bytes,
        "required_free_bytes_estimate_including_raw_features_and_reserve": needed,
        "free_destination_bytes": free,
        "bulk_space_sufficient": free >= needed,
        "complete_tranche_ready_to_train": checked["ready_to_train"],
    }
    atomic_json(output / "execution/preflight.json", result)
    if require_bulk_space and free < needed:
        raise ValueError(
            f"[fingerspelling/preflight] Need {needed / 1e9:.2f} GB free; "
            f"have {free / 1e9:.2f} GB. Free space, then rerun. No source is deleted."
        )
    return result


@contextlib.contextmanager
def single_writer(output: Path) -> Any:
    # OS socket ownership vanishes on Ctrl+C/process death, unlike stale PID lockfiles.
    import hashlib

    port = (
        40000
        + int(hashlib.sha256(str(output.resolve()).lower().encode()).hexdigest()[:4], 16) % 20000
    )
    sock = socket.socket()
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError as exc:
        sock.close()
        raise RuntimeError(
            "[fingerspelling/runner] Another preparation writer or local port owner is active"
        ) from exc
    try:
        yield
    finally:
        sock.close()


def prepare_tranche(output: Path) -> dict[str, Any]:
    with single_writer(output):
        preflight(output)
        rows = frozen_rows(output)
        plan = json.loads((output / "batch_plan.json").read_text())
        if plan["manifest_sha256"] != EXECUTION["frozen_manifest_sha256"]:
            raise ValueError("[fingerspelling/runner] Batch plan identity mismatch")
        by_id = {r["sample_id"]: r for r in rows}
        flattened = [sid for batch in plan["batches"] for sid in batch["sample_ids"]]
        if len(flattened) != len(rows) or set(flattened) != set(by_id):
            raise ValueError(
                "[fingerspelling/runner] Batch plan does not cover exact frozen inventory"
            )
        failures_path = output / "execution/failures.json"
        failures = json.loads(failures_path.read_text()) if failures_path.is_file() else {}
        known_ids = set(by_id)
        if any(sid not in known_ids for sid in failures):
            raise ValueError(
                "[fingerspelling/runner] Failure inventory contains unexpected identities"
            )
        event(output, "RUN_START", manifest_sha256=EXECUTION["frozen_manifest_sha256"])
        runtime_cache: dict[str, Any] = {}
        consecutive_failures = 0
        try:
            for batch_index, batch in enumerate(plan["batches"]):
                if len(batch["sample_ids"]) > EXECUTION["batch_sequences"]:
                    raise ValueError("[fingerspelling/runner] Oversized batch")
                event(output, "BATCH_START", index=batch_index, role=batch["role"])
                failures_before = dict(failures)
                for sid in batch["sample_ids"]:
                    row = by_id[sid]
                    if (output / "features" / f"{sid}.receipt.json").is_file():
                        # Full validation at start/after every batch has already verified this pair.
                        failures.pop(sid, None)
                        continue
                    try:
                        for attempt in range(EXECUTION["download_attempts"]):
                            try:
                                acquire(output, [row])
                                break
                            except OSError as exc:
                                event(
                                    output,
                                    "ACQUISITION_RETRY",
                                    sample_id=sid,
                                    attempt=attempt + 1,
                                    error=str(exc),
                                )
                                if attempt + 1 == EXECUTION["download_attempts"]:
                                    raise
                                time.sleep(EXECUTION["retry_backoff_seconds"] * (attempt + 1))
                        extract(output, [row], runtime_cache)  # one serial frozen runtime
                        failures.pop(sid, None)
                        consecutive_failures = 0
                        event(output, "SEQUENCE_COMPLETE", sample_id=sid, role=row["split_role"])
                    except Exception as exc:
                        consecutive_failures += 1
                        failures[sid] = {
                            "role": row["split_role"],
                            "error": str(exc),
                            "type": type(exc).__name__,
                        }
                        event(output, "SEQUENCE_FAILED", sample_id=sid, **failures[sid])
                    atomic_json(failures_path, failures)
                    atomic_json(output / "execution/progress.json", inventory(output))
                    if consecutive_failures >= EXECUTION["download_attempts"]:
                        raise RuntimeError(
                            "[fingerspelling/runner] Three consecutive failures; "
                            "inspect reports before retrying"
                        )
                checked = validate(output, output / "tranche_manifest.json")
                if failures != failures_before:
                    atomic_json(failures_path, failures)
                event(
                    output,
                    "BATCH_VALIDATED",
                    index=batch_index,
                    structural_pass=checked["structural_pass"],
                    counts={r: s["sequences"] for r, s in checked["statistics"].items()},
                )
                if not checked["structural_pass"]:
                    raise ValueError(
                        "[fingerspelling/runner] Structural errors; "
                        "stop and inspect validation.json"
                    )
        except KeyboardInterrupt:
            event(
                output,
                "RUN_INTERRUPTED",
                action="Rerun identical command; completed verified artifacts are reused",
            )
            atomic_json(output / "execution/progress.json", inventory(output))
            raise
        except Exception as exc:
            event(output, "RUN_STOPPED", error=str(exc), type=type(exc).__name__)
            raise
        final = validate(output, output / "tranche_manifest.json")
        result = {
            "status": (
                "TRANCHE_MATERIALIZED_READY_TO_TRAIN"
                if final["ready_to_train"]
                else "TRANCHE_INCOMPLETE"
            ),
            "actual_counts": {r: s["sequences"] for r, s in final["statistics"].items()},
            "pending": 1280 - final["validated_sequences"],
            "failures": failures,
            "validation": final,
            "training_started": False,
        }
        atomic_json(output / "execution/progress.json", inventory(output))
        atomic_json(output / "execution/final_summary.json", result)
        event(
            output,
            "RUN_END",
            status=result["status"],
            counts=result["actual_counts"],
            pending=result["pending"],
        )
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["preflight", "status", "prepare-tranche", "final-validate"]
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(REPO)
    if args.command == "status":
        print(json.dumps(inventory(output), indent=2))
    elif args.command == "preflight":
        print(json.dumps(preflight(output), indent=2))
    elif args.command == "final-validate":
        result = validate(output, output / "tranche_manifest.json")
        print(json.dumps({k: v for k, v in result.items() if k != "statistics"}, indent=2))
        if not result["ready_to_train"]:
            raise SystemExit(1)
    else:
        result = prepare_tranche(output)
        if result["status"] != "TRANCHE_MATERIALIZED_READY_TO_TRAIN":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
