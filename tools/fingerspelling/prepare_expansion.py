"""Opt-in serial expansion preparation with managed storage and batch-scoped validation.

No training or TEST commands. Preflight/status do not download or instantiate Candidate01.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any

from pipeline.fingerspelling.adapter import identity, sha256
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import ASSETS, PREPROCESSING, validate, verify_source
from pipeline.fingerspelling.storage import MARKER, SCHEMA, declaration
from tools.fingerspelling.foundation import acquire, extract
from tools.fingerspelling.fsboard_expansion_plan import OUTPUT, SETTINGS, validate_plan
from tools.fingerspelling.tranche import EXECUTION, atomic_json, event, single_writer

PACKAGES = {
    "ALL": ["train_additions", "dev_b"],
    "TRAIN_ADDITIONS": ["train_additions"],
    "DEV_B": ["dev_b"],
}


def root_path(destination: Path) -> Path:
    root = destination.resolve()
    if root == Path(root.anchor) or root == REPO or root.is_relative_to(REPO):
        raise ValueError("[fingerspelling/storage] Use a dedicated external data directory")
    if root.is_relative_to(REPO / SETTINGS["foundation_path"]):
        raise ValueError("[fingerspelling/storage] Original foundation cannot be a destination")
    return root


def frozen_copy(source: Path, target: Path) -> None:
    if target.exists():
        if sha256(target) != sha256(source):
            raise ValueError(f"[fingerspelling/storage] Existing frozen file differs: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())


def rows(package: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = json.loads(
        (OUTPUT / package / "tranche_manifest.json").read_text()
    )["samples"]
    return result


def initialize(root: Path, packages: list[str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    frozen_copy(OUTPUT / "plan_identity.json", root / "plan_identity.json")
    for name in packages:
        package = root / name
        frozen_copy(OUTPUT / name / "tranche_manifest.json", package / "tranche_manifest.json")
        frozen_copy(OUTPUT / name / "batch_plan.json", package / "batch_plan.json")
        marker = package / MARKER
        expected = {
            "schema_version": SCHEMA,
            "package_root": package.resolve().as_posix(),
            "manifest_sha256": sha256(package / "tranche_manifest.json"),
            "path_convention": "ABSOLUTE_MANAGED_PACKAGE_V1",
        }
        if marker.exists():
            if json.loads(marker.read_text()) != expected:
                raise ValueError("[fingerspelling/storage] Existing storage marker differs")
        else:
            atomic_json(marker, expected)
        declaration(package)


def inventory(root: Path) -> dict[str, Any]:
    counts: dict[str, int] = {}
    complete: set[str] = set()
    adapter = identity()
    for name in PACKAGES["ALL"]:
        counts[name] = 0
        package = root / name
        manifest_sha = sha256(OUTPUT / name / "tranche_manifest.json")
        for row in rows(name):
            path = package / "features" / (row["sample_id"] + ".receipt.json")
            if path.is_file():
                receipt = json.loads(path.read_text())
                if (
                    receipt["sample_id"] == row["sample_id"]
                    and receipt["adapter"] == adapter
                    and receipt["manifest_sha256"] == manifest_sha
                    and (REPO / receipt["features_path"]).is_file()
                ):
                    counts[name] += 1
                    complete.add(row["sample_id"])
    failure_path = root / "execution/failures.json"
    failures = json.loads(failure_path.read_text()) if failure_path.is_file() else {}
    unresolved = {sid: value for sid, value in failures.items() if sid not in complete}
    return {
        "status": "FAST_RECEIPT_INVENTORY_NOT_FRESH_INTEGRITY_VALIDATION",
        "prepared_new": counts,
        "selected_new": {name: len(rows(name)) for name in PACKAGES["ALL"]},
        "pending_new": 3328 - len(complete),
        "failures": unresolved,
        "existing_train_referenced_unchanged": 1024,
        "existing_dev_a_referenced_unchanged": 256,
        "package_disk_bytes": sum(p.stat().st_size for p in root.rglob("*") if p.is_file()),
        "test_payload_accessed": False,
    }


def preflight(root: Path, packages: list[str], *, require_space: bool = True) -> dict[str, Any]:
    validate_plan()
    initialize(root, packages)
    from pipeline.perception_vnext.offline_candidate01 import DEFAULT_ONNX, DEFAULT_REFINER

    for path in [DEFAULT_ONNX, DEFAULT_REFINER]:
        if sha256(path) != ASSETS[path.name]:
            raise ValueError("[fingerspelling/preflight] Frozen Candidate01 asset changed")
    for name, expected in PREPROCESSING.items():
        if sha256(REPO / "pipeline/perception_vnext" / name) != expected:
            raise ValueError("[fingerspelling/preflight] Frozen preprocessing changed")
    code_paths = [
        "tools/fingerspelling/prepare_expansion.py",
        "tools/fingerspelling/foundation.py",
        "pipeline/fingerspelling/sequence_package.py",
        "pipeline/fingerspelling/storage.py",
    ]
    run_identity = {
        "code_sha256": {name: sha256(REPO / name) for name in code_paths},
        "adapter": identity(),
    }
    identity_path = root / "execution/implementation_identity.json"
    if identity_path.exists() and json.loads(identity_path.read_text()) != run_identity:
        raise ValueError(
            "[fingerspelling/preflight] Preparation implementation changed since initialization"
        )
    atomic_json(identity_path, run_identity)
    needed = EXECUTION["disk_reserve_bytes"]
    analysis = json.loads((OUTPUT / "coverage_and_workload.json").read_text())
    validations = {}
    for name in packages:
        package = root / name
        checked = validate(package, package / "tranche_manifest.json")
        if not checked["structural_pass"]:
            raise ValueError(
                f"[fingerspelling/preflight] Integrity failed: {package / 'validation.json'}"
            )
        validations[name] = checked["validated_sequences"]
        for row in rows(name):
            source = package / "videos" / row["filename"]
            if source.is_file():
                verify_source(source, row)
            else:
                needed += row["file_size_bytes"]
        cohort = "TRAIN_ADDITIONS" if name == "train_additions" else "DEV_B"
        needed += sum(analysis["workload"]["estimated_by_cohort"][cohort]["archive_bytes"].values())
    free = shutil.disk_usage(root).free
    result = {
        "status": (
            "EXTERNAL_PREPARATION_PREFLIGHT_PASS"
            if free >= needed
            else "INSUFFICIENT_DESTINATION_SPACE"
        ),
        "destination": str(root),
        "free_bytes": free,
        "required_bytes_estimate": needed,
        "full_validated_prepared_counts": validations,
        "models_loaded": False,
        "downloads": False,
        "extraction": False,
        "training": False,
        "test_payload_accessed": False,
    }
    atomic_json(root / "execution/preflight.json", result)
    if require_space and free < needed:
        raise ValueError(
            f"[fingerspelling/preflight] Need {needed:,} bytes, have {free:,}; no data deleted"
        )
    return result


def full_validate(root: Path, packages: list[str]) -> dict[str, Any]:
    validate_plan()
    checked = {}
    for name in packages:
        frozen_copy(OUTPUT / name / "tranche_manifest.json", root / name / "tranche_manifest.json")
        checked[name] = validate(root / name, root / name / "tranche_manifest.json")
    valid = all(result["structural_pass"] for result in checked.values())
    complete = all(
        result["validated_sequences"] == result["selected_sequences"] for result in checked.values()
    )
    result = {
        "status": (
            "SELECTED_PACKAGES_MATERIALIZED_INTEGRITY_PASS"
            if valid and complete
            else "SELECTED_PACKAGES_PENDING_OR_INVALID"
        ),
        "packages": checked,
        "training_admitted": False,
        "dev_b_usage": "FINAL_CONFIRMATION_ONLY",
        "test_payload_accessed": False,
    }
    atomic_json(root / "execution/final_validation.json", result)
    return result


def prepare(root: Path, packages: list[str]) -> dict[str, Any]:
    with single_writer(root):
        preflight(root, packages)  # Full resume integrity check before trusting completed receipts.
        plan = json.loads((OUTPUT / "batch_plan.json").read_text())
        by_id = {r["sample_id"]: r for name in packages for r in rows(name)}
        failures_path = root / "execution/failures.json"
        failures = json.loads(failures_path.read_text()) if failures_path.is_file() else {}
        allowed_ids = {r["sample_id"] for name in PACKAGES["ALL"] for r in rows(name)}
        if set(failures) - allowed_ids:
            raise ValueError("[fingerspelling/runner] Unknown failure identity")
        runtime_cache: dict[str, Any] = {}
        started = time.perf_counter()
        try:
            for index, batch in enumerate(plan["batches"]):
                if batch["package"] not in packages:
                    continue
                package = root / batch["package"]
                pending = [
                    by_id[sid]
                    for sid in batch["sample_ids"]
                    if not (package / "features" / (sid + ".receipt.json")).is_file()
                ]
                if not pending:
                    for sid in batch["sample_ids"]:
                        failures.pop(sid, None)
                    atomic_json(failures_path, failures)
                    continue
                event(
                    root, "BATCH_START", index=index, package=batch["package"], pending=len(pending)
                )
                for row in pending:
                    sid = row["sample_id"]
                    try:
                        for attempt in range(EXECUTION["download_attempts"]):
                            try:
                                acquire(package, [row])
                                break
                            except OSError:
                                if attempt + 1 == EXECUTION["download_attempts"]:
                                    raise
                                time.sleep(EXECUTION["retry_backoff_seconds"] * (attempt + 1))
                        extract(package, [row], runtime_cache)
                        failures.pop(sid, None)
                        event(root, "SEQUENCE_COMPLETE", sample_id=sid)
                    except Exception as exc:
                        failures[sid] = {
                            "role": row["split_role"],
                            "error": str(exc),
                            "type": type(exc).__name__,
                        }
                        atomic_json(failures_path, failures)
                        event(root, "SEQUENCE_FAILED", sample_id=sid, **failures[sid])
                        raise  # Stop explicitly; keep completed artifacts for resume.
                    atomic_json(failures_path, failures)
                checked = validate(
                    package,
                    package / "tranche_manifest.json",
                    receipt_ids=set(batch["sample_ids"]),
                    report_path=package / "execution/batches" / f"{index:04d}.validation.json",
                )
                if not checked["structural_pass"] or checked["scoped_pending"]:
                    raise ValueError(
                        "[fingerspelling/runner] Completed-batch integrity validation failed"
                    )
                atomic_json(root / "execution/progress.json", inventory(root))
                event(
                    root,
                    "BATCH_VALIDATED",
                    index=index,
                    elapsed_seconds=time.perf_counter() - started,
                )
        except KeyboardInterrupt:
            event(root, "RUN_INTERRUPTED", action="Rerun same command to resume verified artifacts")
            raise
        except Exception as exc:
            event(root, "RUN_STOPPED", error=str(exc))
            raise
        finally:
            if "runtime" in runtime_cache:
                runtime_cache["runtime"].close()
        final = full_validate(root, packages)
        atomic_json(root / "execution/progress.json", inventory(root))
        event(
            root, "RUN_END", status=final["status"], elapsed_seconds=time.perf_counter() - started
        )
        return final


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "prepare", "status", "validate"])
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--package", choices=list(PACKAGES), default="ALL")
    args = parser.parse_args()
    root = root_path(args.destination)
    packages = PACKAGES[args.package]
    if args.command == "preflight":
        with single_writer(root):
            result = preflight(root, packages)
    elif args.command == "prepare":
        result = prepare(root, packages)
    elif args.command == "status":
        validate_plan()
        result = inventory(root)
    else:
        with single_writer(root):
            result = full_validate(root, packages)
    print(json.dumps(result, indent=2))
    if (
        args.command == "validate"
        and result["status"] != "SELECTED_PACKAGES_MATERIALIZED_INTEGRITY_PASS"
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
