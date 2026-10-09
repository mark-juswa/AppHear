"""Resumable governed RGB-to-appearance preparation. No perception/model fitting."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from typing import Any

from model import fingerspelling_baseline2 as b2
from model import fingerspelling_ctc as reference
from model.fingerspelling_appearance import EVIDENCE, PACKAGE, build_encoder, ensure_weights
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.visual_crop import config
from pipeline.fingerspelling.visual_package import (
    load_visual,
    prepare,
    receipt_path,
    visual_identity,
)
from tools.fingerspelling.tranche import single_writer


def diagnostic_rows(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    path = REPO / "artifacts/fingerspelling_baseline3/diagnostic_manifest.json"
    if sha256(path) != "fff5c54beac8ad14940eb48d7626f75eec1d45c76ca4d5b7612020a3b6015dd9":
        raise ValueError("[visual/diagnostic] Historical TRAIN64 IDs changed")
    ids = json.loads(path.read_text())["sample_ids"]
    by_id = {r["sample_id"]: r for r in rows}
    train = [by_id[sid] for sid in ids]
    dev = b2.diagnostic_rows(rows, b2.policy()[0])[1]
    if (
        len(train) != 64
        or any(r["split_role"] != "TRAIN" for r in train)
        or any(r["split_role"] != "DEV" for r in dev)
    ):
        raise ValueError("[visual/diagnostic] Official roles changed")
    manifest = {
        "schema_version": "apphear.fingerspelling.visual_gate_manifest.v1",
        "train_ids": ids,
        "dev_ids": [r["sample_id"] for r in dev],
        "data_lineage_sha256": b2.lineage(train + dev),
        "selection": "FROZEN_TRAIN64_PLUS_B2_METADATA_DEV_SIGNERS_AND_INFEASIBLE",
        "test_accessed": False,
    }
    output = EVIDENCE / "diagnostic_manifest.json"
    if output.exists() and json.loads(output.read_text()) != manifest:
        raise ValueError("[visual/diagnostic] Frozen gate manifest mismatch")
    if not output.exists():
        write_json_atomic(output, manifest)
    return train, dev


def preflight() -> dict[str, Any]:
    rows = b2.dataset(b2.DEFAULT_DATA)
    ensure_weights()
    train, dev = diagnostic_rows(rows)
    missing = [r["sample_id"] for r in rows if not (REPO / r["source_path"]).is_file()]
    result = {
        "status": "VISUAL_PREFLIGHT_PASS" if not missing else "VISUAL_PREFLIGHT_BLOCKED",
        "counts": dict(Counter(r["split_role"] for r in rows)),
        "diagnostic_counts": {"TRAIN": len(train), "DEV": len(dev)},
        "source_files_present": len(rows) - len(missing),
        "missing_sources": missing,
        "native_observations": sum(r["frame_count"] for r in rows),
        "maximum_dense_embedding_bytes": sum(r["frame_count"] for r in rows)
        * 2
        * config()["embedding_width"]
        * 4,
        "free_bytes": shutil.disk_usage(REPO).free,
        "visual_identity": visual_identity(),
        "no_download": True,
        "test_accessed": False,
    }
    write_json_atomic(EVIDENCE / "preflight.json", result)
    return result


def status(rows: list[dict[str, Any]], validate: bool = False) -> dict[str, Any]:
    counts: Counter = Counter()
    failures = []
    for r in rows:
        if not receipt_path(r).exists():
            continue
        if validate:
            try:
                load_visual(r)
            except (ValueError, OSError, KeyError) as exc:
                failures.append({"sample_id": r["sample_id"], "error": str(exc)})
                continue
        counts[r["split_role"]] += 1
    selected = Counter(r["split_role"] for r in rows)
    result = {
        "schema_version": "apphear.fingerspelling.visual_validation.v1",
        "status": (
            "VISUAL_PACKAGE_VALID"
            if validate and not failures and sum(counts.values()) == len(rows)
            else "VISUAL_PACKAGE_PENDING_OR_FAILED"
        ),
        "prepared": dict(counts),
        "selected": dict(selected),
        "pending": len(rows) - sum(counts.values()) - len(failures),
        "failures": failures,
        "validation_performed": validate,
        "test_accessed": False,
    }
    return result


def preparation(rows: list[dict[str, Any]], limit: int | None, qa: bool) -> dict[str, Any]:
    import cv2

    # Decode/QA only. Crop arithmetic and encoder semantics are unchanged.
    cv2.setNumThreads(1)
    _, base = b2.policy()
    tf = reference.tensorflow(base)
    encoder = build_encoder(tf)
    new = 0
    completed = []
    with single_writer(PACKAGE):
        for rec in rows:
            if limit is not None and new >= limit:
                break
            try:
                result = prepare(rec, tf, encoder, qa=qa)
                completed.append(result)
                new += result["status"] != "REUSED_VERIFIED"
                write_json_atomic(
                    EVIDENCE / "progress.json",
                    {
                        "sample_id": rec["sample_id"],
                        "new_this_invocation": new,
                        "result": result,
                        "inventory": status(rows),
                    },
                )
                print(json.dumps(result), flush=True)
            except BaseException as exc:
                write_json_atomic(
                    EVIDENCE / "failures" / f"{rec['sample_id']}.json",
                    {
                        "sample_id": rec["sample_id"],
                        "type": type(exc).__name__,
                        "error": str(exc),
                        "resume": (
                            "Rerun identical preparation command; "
                            "verified completed receipts reused"
                        ),
                    },
                )
                raise
        result = {
            "status": (
                "VISUAL_PREPARATION_COMPLETE"
                if status(rows)["pending"] == 0
                else "VISUAL_PREPARATION_PARTIAL"
            ),
            "encoder_parameters": encoder.count_params(),
            "completed_this_invocation": completed,
            "inventory": status(rows, validate=True),
        }
        write_json_atomic(EVIDENCE / "preparation_summary.json", result)
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["preflight", "prepare-diagnostic", "prepare-tranche", "status", "validate"],
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    rows = b2.dataset(b2.DEFAULT_DATA)
    train, dev = diagnostic_rows(rows)
    if args.command == "preflight":
        result = preflight()
    elif args.command.startswith("prepare-"):
        if args.limit is not None and args.limit <= 0:
            parser.error("--limit must be positive")
        selected = train + dev if args.command == "prepare-diagnostic" else rows
        result = preparation(selected, args.limit, qa=args.command == "prepare-diagnostic")
    else:
        selected = train + dev if args.diagnostic else rows
        result = status(selected, validate=args.command == "validate")
        if args.command == "validate":
            write_json_atomic(
                EVIDENCE
                / (
                    "diagnostic_validation.json"
                    if args.diagnostic
                    else "tranche_validation.json"
                ),
                result,
            )
    printable = {k: v for k, v in result.items() if k != "completed_this_invocation"}
    print(json.dumps(printable, indent=2), flush=True)


if __name__ == "__main__":
    main()
