"""One resumable, serial trusted-appearance preparation command; no downloads or training."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from collections import Counter
from typing import Any

from model import fingerspelling_baseline2 as b2
from model import fingerspelling_ctc as reference
from model.fingerspelling_appearance import build_encoder
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.residual_visual_package import (
    PACKAGE,
    identity,
    load,
    prepare,
    receipt_path,
)
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.visual_package import receipt_path as old_receipt
from pipeline.fingerspelling.visual_quality import config
from pipeline.fingerspelling.visual_quality import identity as quality_identity
from tools.fingerspelling.residual_audit import EVIDENCE
from tools.fingerspelling.residual_lock import single_writer


def admission() -> dict[str, Any]:
    cfg = config()
    if sha256(REPO / cfg["base_checkpoint"]) != cfg["base_checkpoint_sha256"]:
        raise ValueError("[residual/preflight] B2 checkpoint changed")
    decoder = json.loads((REPO / cfg["base_decoder"]).read_text())
    if decoder["subtract_from_blank_logit"] != cfg["blank_penalty"]:
        raise ValueError("[residual/preflight] B2 decoder policy mismatch")
    audit = json.loads((EVIDENCE / "crop_audit.json").read_text())
    if (
        audit["quality_identity"] != quality_identity()
        or audit["review_status"] != "BOUNDED_CROP_RELIABILITY_PASS"
    ):
        raise ValueError(
            "[residual/preflight] Matching crop reliability audit required"
        )
    if (
        audit["retained_non_hand_count"] / audit["retained_review_count"]
        > cfg["crop_audit_max_nuisance_fraction"]
    ):
        raise ValueError("[residual/preflight] Crop contamination gate failed")
    for sheet in audit["sheets"]:
        if sha256(REPO / sheet["path"]) != sheet["sha256"]:
            raise ValueError("[residual/preflight] Audit image changed")
    return {
        "crop_audit_sha256": sha256(EVIDENCE / "crop_audit.json"),
        "base_checkpoint_sha256": cfg["base_checkpoint_sha256"],
    }


def smoke_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    available = [r for r in rows if old_receipt(r).is_file()]
    selected = []
    for role, stratum, count in [
        ("TRAIN", "DAUN", 4),
        ("TRAIN", "MacKenzie", 4),
        ("DEV", "DAUN", 8),
    ]:
        group = sorted(
            [
                r
                for r in available
                if r["split_role"] == role and r["source_stratum"] == stratum
            ],
            key=lambda r: (
                r["phone_ctc_feasible"],
                r["official_signer_id"],
                r["sample_id"],
            ),
        )
        used = set()
        for r in group:
            if r["official_signer_id"] not in used:
                selected.append(r)
                used.add(r["official_signer_id"])
                if len(used) == count:
                    break
        if len(used) != count:
            raise ValueError("[residual/smoke] Insufficient historical sidecars")
    return selected


def status(rows: list[dict[str, Any]], validate: bool = False) -> dict[str, Any]:
    counts: Counter = Counter()
    errors = []
    retained = frames = duplicate = 0
    by_group: dict[str, dict[str, int]] = {}
    for r in rows:
        if not receipt_path(r).is_file():
            continue
        try:
            saved = json.loads(receipt_path(r).read_text())
            if validate:
                load(r)
            elif saved["identity"] != identity():
                raise ValueError("[residual/status] Identity mismatch")
            counts[r["split_role"]] += 1
            m = saved["metadata"]
            frames += m["frames"]
            retained += m["retained_slots"]
            duplicate += m["duplicate_frames"]
            key = r["split_role"] + "_" + r["source_stratum"]
            g = by_group.setdefault(key, {"frames": 0, "no_crop_frames": 0})
            g["frames"] += m["frames"]
            g["no_crop_frames"] += m["no_crop_frames"]
        except (ValueError, OSError, KeyError) as exc:
            errors.append({"sample_id": r["sample_id"], "error": str(exc)})
    complete = not errors and sum(counts.values()) == len(rows)
    result = {
        "status": (
            "RESIDUAL_VISUAL_VALID"
            if complete and validate
            else "RESIDUAL_VISUAL_PENDING"
        ),
        "prepared": dict(counts),
        "selected": dict(Counter(r["split_role"] for r in rows)),
        "pending": len(rows) - sum(counts.values()) - len(errors),
        "failures": errors,
        "frames": frames,
        "retained_slots": retained,
        "duplicate_frames": duplicate,
        "group_coverage": by_group,
        "validation_performed": validate,
        "test_accessed": False,
    }
    return result


def preflight(rows: list[dict[str, Any]]) -> dict[str, Any]:
    adm = admission()
    missing = [r["sample_id"] for r in rows if not (REPO / r["source_path"]).is_file()]
    if missing:
        raise ValueError(
            f"[residual/preflight] Missing {len(missing)} governed RGB files; no download performed"
        )
    PACKAGE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=PACKAGE) as stream:
        stream.write(b"residual writable probe")
    result = {
        "status": "RESIDUAL_VISUAL_PREFLIGHT_PASS",
        "counts": dict(Counter(r["split_role"] for r in rows)),
        "identity": identity(),
        "admission": adm,
        "sources_present": len(rows),
        "free_bytes": shutil.disk_usage(REPO).free,
        "maximum_uncompressed_embedding_bytes": sum(r["frame_count"] for r in rows)
        * 2
        * 576
        * 4,
        "no_download": True,
        "test_accessed": False,
    }
    write_json_atomic(EVIDENCE / "preflight.json", result)
    return result


def preparation(rows: list[dict[str, Any]], limit: int | None = None) -> dict[str, Any]:
    import cv2

    cv2.setNumThreads(1)
    admission()
    encoder = None
    new = 0
    with single_writer(PACKAGE):
        for r in rows:
            if limit is not None and new >= limit:
                break
            try:
                if (
                    not receipt_path(r).is_file()
                    and not old_receipt(r).is_file()
                    and encoder is None
                ):
                    tf = reference.tensorflow(b2.policy()[1])
                    encoder = build_encoder(tf)
                result = prepare(r, encoder)
                new += result["status"] == "PREPARED_VALIDATED"
                write_json_atomic(
                    EVIDENCE / "preparation_progress.json",
                    {"new_this_invocation": new, "latest": result},
                )
                print(
                    json.dumps(
                        {"sample_id": r["sample_id"], "status": result["status"]}
                    ),
                    flush=True,
                )
            except BaseException as exc:
                write_json_atomic(
                    EVIDENCE / "failures" / f"{r['sample_id']}.json",
                    {
                        "sample_id": r["sample_id"],
                        "type": type(exc).__name__,
                        "error": str(exc),
                        "resume": "Rerun identical command; verified completed receipts are reused",
                    },
                )
                raise
        result = status(rows, True)
        write_json_atomic(EVIDENCE / "preparation_summary.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["preflight", "prepare-smoke", "prepare-tranche", "status", "validate"],
    )
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    rows = b2.dataset(b2.DEFAULT_DATA, full=args.command == "validate")
    if args.command == "preflight":
        result = preflight(rows)
    elif args.command == "prepare-smoke":
        result = preparation(smoke_rows(rows), args.limit)
    elif args.command == "prepare-tranche":
        result = preparation(rows, args.limit)
    else:
        result = status(rows, args.command == "validate")
        if args.command == "validate":
            write_json_atomic(EVIDENCE / "validation.json", result)
    print(json.dumps(result, indent=2))
    if result.get("failures") or (
        args.command == "validate" and result["status"] != "RESIDUAL_VISUAL_VALID"
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
