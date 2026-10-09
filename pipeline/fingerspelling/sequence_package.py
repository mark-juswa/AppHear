"""Source-to-frozen-raw-to-features receipts and explicit CTC admission diagnostics."""

from __future__ import annotations

import collections
import json
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.fingerspelling.adapter import (
    CONFIG,
    WIDTH,
    derive,
    identity,
    phone_indices,
    sha256,
    subset,
)
from pipeline.fingerspelling.package_io import recover_partial, write_json_atomic
from pipeline.fingerspelling.sequence_manifest import (
    ADMISSION,
    MANIFEST_SCHEMA,
    REPO,
    normalized,
    read_metadata,
    record,
    repeats,
    target_ids,
)
from pipeline.fingerspelling.storage import checked_path, receipt_identity, relative
from pipeline.perception_vnext.recognition_schema import RAW_SCHEMA, RawSequence, load_raw_sequence

ARTIFACT_SCHEMA = "apphear.fingerspelling.sequence_features.v1"
RECEIPT_SCHEMA = "apphear.fingerspelling.sequence_receipt.v1"
ASSETS = json.loads((REPO / "pipeline/config/fingerspelling_dataset_v1.json").read_text())[
    "candidate01_assets"
]
PREPROCESSING = {
    "offline_candidate01.py": "6e7a4533e97fac2cc57eb6d6d0ed3b483f50f3eddfcb58d37a04022c56159a95",
    "hand_roi.py": "5ba99d7f56c85ca5425d02ac8c0151c80b40f042f615b735a7953dac56f42209",
    "hand_refiner.py": "f70c35f6a403d7b3af8ca796fb93516ee6666bebea66b517420107dd7757a179",
    "recognition_schema.py": "21c863cce6748ad87e3ef083bedba19a5f6d2020823df3d89a3e58e4bff55fe9",
}


def verify_source(path: Path, row: dict[str, Any]) -> str:
    import hashlib

    if row["split_role"] not in {"TRAIN", "DEV"} or row["official_split"] not in {
        "train",
        "validation",
    }:
        raise ValueError("[fingerspelling/source] Protected/non-official role refused")
    if path.name != row["filename"] or not path.is_file():
        raise ValueError(f"[fingerspelling/source] Missing/misnamed source: {path}")
    if path.stat().st_size != row["file_size_bytes"]:
        raise ValueError("[fingerspelling/source] Size mismatch")
    md5 = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            md5.update(chunk)
    if md5.hexdigest() != row["official_md5"]:
        raise ValueError("[fingerspelling/source] MD5 mismatch")
    return sha256(path)


def verify_raw(
    raw_path: Path, receipt_path: Path, row: dict[str, Any], source_sha: str
) -> RawSequence:
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("schema_version") not in {
        "apphear.fsboard.admission_check_receipt.v1",
        "apphear.fsboard.admission_closure_diagnostic_receipt.v1",
        "apphear.fingerspelling.frozen_extraction_receipt.v1",
    }:
        raise ValueError("[fingerspelling/lineage] Unknown extraction receipt schema")
    if receipt["sample_id"] != row["sample_id"] or receipt["raw_sha256"] != sha256(raw_path):
        raise ValueError("[fingerspelling/lineage] Raw/receipt identity mismatch")
    if (
        receipt["source_sha256"] != source_sha
        or receipt["official_signer_id"] != row["official_signer_id"]
    ):
        raise ValueError("[fingerspelling/lineage] Source/signer mismatch")
    if receipt["split_role"] != row["split_role"] or receipt["raw_schema"] != RAW_SCHEMA:
        raise ValueError("[fingerspelling/lineage] Split/raw schema mismatch")
    if (
        receipt["candidate01_assets"] != ASSETS
        or receipt["preprocessing_source_sha256"] != PREPROCESSING
    ):
        raise ValueError("[fingerspelling/lineage] Candidate01 dialect not pinned")
    if (
        not receipt["whole_source_video"]
        or normalized(receipt["intended_transcript"]) != row["normalized_transcript"]
    ):
        raise ValueError("[fingerspelling/lineage] Partial video or transcript mismatch")
    for name, expected in PREPROCESSING.items():
        if sha256(REPO / "pipeline/perception_vnext" / name) != expected:
            raise ValueError("[fingerspelling/lineage] Frozen preprocessing changed")
    raw = load_raw_sequence(raw_path)
    if receipt["frame_count"] != len(raw.frame_index):
        raise ValueError("[fingerspelling/lineage] Receipt/raw frame count mismatch")
    if (
        raw.metadata["sample_id"] != row["sample_id"]
        or raw.metadata["source_video_sha256"] != source_sha
    ):
        raise ValueError("[fingerspelling/lineage] Raw metadata source mismatch")
    return raw


def write_features(
    output: Path,
    manifest: Path,
    row: dict[str, Any],
    source: Path,
    raw_path: Path,
    raw_receipt: Path,
) -> dict[str, Any]:
    source_sha = verify_source(source, row)
    raw = verify_raw(raw_path, raw_receipt, row, source_sha)
    if json.loads(manifest.read_text())["adapter"] != identity():
        raise ValueError("[fingerspelling/adapter] Frozen manifest adapter mismatch")
    existing_receipt = output / "features" / f"{row['sample_id']}.receipt.json"
    existing_features = output / "features" / f"{row['sample_id']}.npz"
    if existing_receipt.is_file():
        old: dict[str, Any] = json.loads(existing_receipt.read_text())
        if (
            not existing_features.is_file()
            or sha256(existing_features) != old["features_sha256"]
            or old["raw_sha256"] != sha256(raw_path)
            or old["source_sha256"] != source_sha
            or old["adapter"] != identity()
            or old["manifest_sha256"] != sha256(manifest)
        ):
            raise ValueError("[fingerspelling/resume] Completed artifact integrity mismatch")
        return old
    recover_partial(output, [existing_features], "Uncommitted feature array without receipt")
    actual = derive(raw)
    if not np.array_equal(actual, derive(raw)):
        raise ValueError("[fingerspelling/adapter] Non-deterministic transform")
    selected = phone_indices(raw.timestamp_ms)
    sparse = subset(raw, selected)
    phone = derive(sparse)  # Never slice dense motion/dt columns into a sparse view.
    minimum = row["ctc_min_timesteps"]
    meta = {
        "schema_version": ARTIFACT_SCHEMA,
        "sample_id": row["sample_id"],
        "adapter": identity(),
        "reflection_policy": CONFIG["reflection_policy"],
        "reflection_provenance": CONFIG["reflection_provenance"],
    }
    folder = output / "features"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{row['sample_id']}.npz"
    staged_features = path.with_name(path.name + ".pending")
    recover_partial(output, [staged_features], "Interrupted feature staging")
    with staged_features.open("wb") as stream:
        np.savez_compressed(
            stream,
            metadata_json=np.asarray(json.dumps(meta, sort_keys=True)),
            features=actual,
            timestamps_ms=raw.timestamp_ms,
            frame_indices=raw.frame_index,
            targets=np.asarray(target_ids(row["normalized_transcript"]), np.int32),
            phone_features=phone,
            phone_indices=selected,
            phone_timestamps_ms=sparse.timestamp_ms,
            hand_joint_valid=raw.hand_joint_valid,
            hand_observed=raw.hand_observed,
            hand_proposal_present=raw.hand_proposal_present,
            body_valid=raw.body_valid,
            body_available=raw.body_available,
        )
    staged_features.rename(path)
    record = {
        **row,
        "preparation_status": "FEATURES_VALIDATED_RESEARCH_ONLY",
        "schema_version": RECEIPT_SCHEMA,
        "source_path": relative(source, output),
        "source_sha256": source_sha,
        "raw_path": relative(raw_path, output),
        "raw_sha256": sha256(raw_path),
        "raw_receipt_path": relative(raw_receipt, output),
        "raw_receipt_sha256": sha256(raw_receipt),
        "features_path": relative(path, output),
        **receipt_identity(output),
        "features_sha256": sha256(path),
        "adapter": identity(),
        "manifest_sha256": sha256(manifest),
        "frame_count": len(actual),
        "phone_frame_count": len(phone),
        "native_ctc_feasible": len(actual) >= minimum,
        "phone_ctc_feasible": len(phone) >= minimum,
        "timestamp_start_ms": float(raw.timestamp_ms[0]),
        "timestamp_end_ms": float(raw.timestamp_ms[-1]),
        "any_hand_observed_fraction": float(np.any(raw.hand_observed, axis=1).mean()),
        "slot_observed_fraction": raw.hand_observed.mean(axis=0).tolist(),
        "phone_any_hand_observed_fraction": float(np.any(sparse.hand_observed, axis=1).mean()),
        "body_available_fraction": float(raw.body_available.mean()),
        "research_only_authority": "User development decision 2026-10-02; released pixels as-is",
        "formal_collection_reflection_proven": False,
        "training_loss_status": (
            "NATIVE_CTC_ELIGIBLE" if len(actual) >= minimum else "CTC_INFEASIBLE_RETAINED"
        ),
        "phone_view_loss_status": (
            "PHONE_CTC_ELIGIBLE" if len(phone) >= minimum else "CTC_INFEASIBLE_RETAINED"
        ),
    }
    write_json_atomic(folder / f"{row['sample_id']}.receipt.json", record)
    return record


def reuse_fixed(output: Path, manifest: Path) -> list[dict[str, Any]]:
    rows = {s["sample_id"]: s for s in json.loads(manifest.read_text())["samples"]}
    diagnostics = json.loads(
        (ADMISSION / "admission_closure_01/evidence/candidate01_results.json").read_text()
    )
    records = []
    for d in diagnostics:
        row = rows[d["sample_id"]]
        receipts = list(ADMISSION.glob(f"admission_*/evidence/{d['sample_id']}.receipt.json"))
        if len(receipts) != 1:
            raise ValueError("[fingerspelling/reuse] Missing/ambiguous original receipt")
        records.append(
            write_features(
                output,
                manifest,
                row,
                ADMISSION / "videos" / row["filename"],
                REPO / d["raw_path"],
                receipts[0],
            )
        )
    return records


def validate(
    output: Path,
    manifest_path: Path,
    *,
    receipt_ids: set[str] | None = None,
    report_path: Path | None = None,
) -> dict[str, Any]:
    if receipt_ids is not None and report_path is None:
        raise ValueError("[fingerspelling/validation] Scoped check needs separate report path")
    if report_path is not None:
        report_path.resolve().relative_to(output.resolve())
    manifest = json.loads(manifest_path.read_text())
    errors: list[str] = []
    records = []
    metadata, sources = read_metadata()  # Pinned allow-list; TEST metadata only, never payload.
    official = {
        (r["group"], r["clipFilename"]): r for r in metadata if r["role"] != "PROTECTED_TEST"
    }
    protected_phrases = {
        r["normalized_transcript"] for r in metadata if r["role"] == "PROTECTED_TEST"
    }
    protected_md5s = {r["clipFileMd5"] for r in metadata if r["role"] == "PROTECTED_TEST"}
    policy = REPO / manifest["dev_phrase_policy_path"]
    if manifest["schema_version"] != MANIFEST_SCHEMA or manifest["adapter"] != identity():
        errors.append("MANIFEST_OR_ADAPTER_IDENTITY")
    if manifest["metadata_sources"] != sources:
        errors.append("METADATA_SOURCE_IDENTITY")
    if (
        manifest["research_authorization"]["policy"] != CONFIG["reflection_policy"]
        or manifest["research_authorization"]["provenance"] != CONFIG["reflection_provenance"]
    ):
        errors.append("RESEARCH_REFLECTION_AUTHORITY")
    if sha256(policy) != manifest["dev_phrase_policy_sha256"]:
        errors.append("DEV_POLICY_IDENTITY")
    humans: dict[str, str] = {}
    ids, md5s = set(), set()
    for row in manifest["samples"]:
        sid = row["sample_id"]
        try:
            if sid in ids or row["official_md5"] in md5s:
                raise ValueError("DUPLICATE_ID_OR_SOURCE")
            ids.add(sid)
            md5s.add(row["official_md5"])
            role = row["split_role"]
            if (
                role not in {"TRAIN", "DEV"}
                or humans.setdefault(row["official_signer_id"], role) != role
            ):
                raise ValueError("SIGNER_ROLE_LEAKAGE_OR_TEST")
            if row["official_md5"] in protected_md5s:
                raise ValueError("PROTECTED_SOURCE_COPY")
            o = official[row["source_group"], row["filename"]]
            if (
                o["role"],
                o["signerId"],
                o["normalized_transcript"],
                o["clipFileMd5"],
                o["group"],
            ) != (
                role,
                row["official_signer_id"],
                row["normalized_transcript"],
                row["official_md5"],
                row["source_group"],
            ):
                raise ValueError("OFFICIAL_METADATA_MISMATCH")
            expected_row = record(o)
            if any(row[k] != v for k, v in expected_row.items()):
                raise ValueError("OFFICIAL_SOURCE_LINKAGE_OR_SELECTION_FIELDS")
            text = normalized(row["transcript"])
            if text != row["normalized_transcript"] or row["ctc_min_timesteps"] != len(
                text
            ) + repeats(text):
                raise ValueError("TRANSCRIPT_OR_CTC_MINIMUM")
            if role == "DEV" and text in protected_phrases:
                raise ValueError("DEV_TEST_PHRASE_LEAKAGE")
            if receipt_ids is not None and sid not in receipt_ids:
                continue  # Check metadata globally; reread only this batch's arrays.
            path = output / "features" / f"{sid}.receipt.json"
            if not path.is_file():
                continue  # Explicit pending counts reported below, never ready.
            rec = json.loads(path.read_text())
            if any(rec[k] != v for k, v in row.items() if k != "preparation_status"):
                raise ValueError("RECEIPT_MANIFEST_FIELDS")
            if rec["schema_version"] != RECEIPT_SCHEMA or rec["manifest_sha256"] != sha256(
                manifest_path
            ):
                raise ValueError("RECEIPT_SCHEMA_OR_MANIFEST_IDENTITY")
            if (
                rec["adapter"] != identity()
                or rec["reflection_policy"] != CONFIG["reflection_policy"]
            ):
                raise ValueError("ADAPTER_OR_REFLECTION_POLICY")
            storage = receipt_identity(output)
            if storage and any(rec.get(k) != v for k, v in storage.items()):
                raise ValueError("STORAGE_RECEIPT_IDENTITY")
            for key in ("source", "raw", "raw_receipt", "features"):
                path = checked_path(REPO / rec[f"{key}_path"], output)
                if not path.is_file() or sha256(path) != rec[f"{key}_sha256"]:
                    raise ValueError(f"{key.upper()}_IDENTITY")
            source_sha = verify_source(REPO / rec["source_path"], row)
            raw = verify_raw(
                REPO / rec["raw_path"], REPO / rec["raw_receipt_path"], row, source_sha
            )
            selected = phone_indices(raw.timestamp_ms)
            with np.load(REPO / rec["features_path"], allow_pickle=False) as data:
                meta = json.loads(str(data["metadata_json"].item()))
                if meta["schema_version"] != ARTIFACT_SCHEMA or meta["adapter"] != identity():
                    raise ValueError("ARTIFACT_SCHEMA")
                if (
                    data["features"].shape != (len(raw.frame_index), WIDTH)
                    or data["features"].dtype != np.float32
                ):
                    raise ValueError("FEATURE_SHAPE_OR_DTYPE")
                checks = {
                    "features": derive(raw),
                    "phone_features": derive(subset(raw, selected)),
                    "timestamps_ms": raw.timestamp_ms,
                    "frame_indices": raw.frame_index,
                    "phone_indices": selected,
                    "phone_timestamps_ms": raw.timestamp_ms[selected],
                    "targets": np.asarray(target_ids(text), np.int32),
                    "hand_joint_valid": raw.hand_joint_valid,
                    "hand_observed": raw.hand_observed,
                    "hand_proposal_present": raw.hand_proposal_present,
                    "body_valid": raw.body_valid,
                    "body_available": raw.body_available,
                }
                if not all(np.array_equal(data[k], v) for k, v in checks.items()):
                    raise ValueError("DETERMINISM_MASKS_TIMESTAMPS_TARGETS")
                for k in ("features", "phone_features"):
                    if not np.isfinite(data[k]).all():
                        raise ValueError("NON_FINITE_FEATURES")
                if rec["frame_count"] != len(data["features"]) or rec["phone_frame_count"] != len(
                    selected
                ):
                    raise ValueError("CTC_FRAME_COUNT")
                if rec["native_ctc_feasible"] != (
                    len(data["features"]) >= row["ctc_min_timesteps"]
                ) or rec["phone_ctc_feasible"] != (len(selected) >= row["ctc_min_timesteps"]):
                    raise ValueError("CTC_STATUS")
            records.append(rec)
        except (ValueError, KeyError, OSError) as exc:
            errors.append(f"{sid}: {exc}")
    unexpected = {
        p.stem.removesuffix(".receipt") for p in (output / "features").glob("*.receipt.json")
    } - ids
    unexpected |= {p.stem for p in (output / "features").glob("*.npz")} - ids
    if unexpected:
        errors.append("UNEXPECTED_FEATURE_IDENTITIES: " + str(sorted(unexpected)))
    if receipt_ids is not None and receipt_ids - ids:
        errors.append("UNKNOWN_SELECTED_RECEIPT_IDS: " + str(sorted(receipt_ids - ids)))
    stats = {}
    for role in ("TRAIN", "DEV"):
        rows = [r for r in records if r["split_role"] == role]
        chars = collections.Counter("".join(r["normalized_transcript"] for r in rows))
        stats[role] = {
            "sequences": len(rows),
            "signers": len({r["official_signer_id"] for r in rows}),
            "characters": dict(sorted(chars.items())),
            "native_frames": sum(r["frame_count"] for r in rows),
            "phone_frames": sum(r["phone_frame_count"] for r in rows),
            "native_ctc_infeasible": sum(not r["native_ctc_feasible"] for r in rows),
            "phone_ctc_infeasible": sum(not r["phone_ctc_feasible"] for r in rows),
            "j_sequences": sum("J" in r["normalized_transcript"] for r in rows),
            "z_sequences": sum("Z" in r["normalized_transcript"] for r in rows),
            "repeat_sequences": sum(r["adjacent_repeat_count"] > 0 for r in rows),
            "strata": dict(collections.Counter(r["source_stratum"] for r in rows)),
            "lengths": [r["transcript_length"] for r in rows],
            "temporal_lengths": [r["frame_count"] for r in rows],
            "missing_hand_fractions": [1 - r["any_hand_observed_fraction"] for r in rows],
        }
    blockers = []
    batch_plan = output / "batch_plan.json"
    if batch_plan.is_file() and json.loads(batch_plan.read_text())["manifest_sha256"] != sha256(
        manifest_path
    ):
        errors.append("FROZEN_BATCH_PLAN_MANIFEST_IDENTITY")
    parity_path = output / "parity/parity.json"
    if not parity_path.is_file():
        blockers.append("KOTLIN_REFERENCE_PARITY_PENDING")
    else:
        parity = json.loads(parity_path.read_text())
        if (
            not parity["pass"]
            or parity["adapter"] != identity()
            or parity["kotlin_reference_sha256"]
            != sha256(REPO / "tools/fingerspelling/FoundationParity.kt")
        ):
            blockers.append("KOTLIN_REFERENCE_PARITY_STALE_OR_FAILED")
    if len(records) != len(manifest["samples"]):
        blockers.append(f"PENDING_OR_FAILED_SEQUENCES={len(manifest['samples']) - len(records)}")
    for role in ("TRAIN", "DEV"):
        if set(stats[role]["characters"]) != set("ABCDEFGHIJKLMNOPQRSTUVWXYZ "):
            blockers.append(f"{role}_CHARACTER_COVERAGE_INCOMPLETE")
        expected_count = CONFIG["train_sequences"] if role == "TRAIN" else CONFIG["dev_sequences"]
        if stats[role]["sequences"] != expected_count:
            blockers.append(f"{role}_TRANCHE_INCOMPLETE")
        eligible = [r for r in records if r["split_role"] == role and r["native_ctc_feasible"]]
        if set("".join(r["normalized_transcript"] for r in eligible)) != set(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ "
        ):
            blockers.append(f"{role}_NATIVE_CTC_ELIGIBLE_COVERAGE_INCOMPLETE")
        if not any(r["adjacent_repeat_count"] for r in eligible):
            blockers.append(f"{role}_REPEATED_SEQUENCE_COVERAGE_INCOMPLETE")
    expected_strata = {
        "DAUN" if group == "daun_v3" else "MacKenzie": count
        for group, count in CONFIG["train_stratum_quota"].items()
    }
    if stats["TRAIN"]["strata"] != expected_strata:
        blockers.append("TRAIN_BOTH_STRATA_TRANCHE_INCOMPLETE")
    if errors:
        blockers.append("STRUCTURAL_ERRORS")
    result = {
        "schema_version": "apphear.fingerspelling.sequence_validation.v1",
        "manifest_sha256": sha256(manifest_path),
        "adapter": identity(),
        "structural_errors": errors,
        "structural_pass": not errors,
        "validated_sequences": len(records),
        "selected_sequences": len(manifest["samples"]),
        "statistics": stats,
        "readiness_blockers": blockers,
        "ready_to_train": not blockers,
        "accuracy_claim": "NONE",
        "test_payload_accessed": False,
    }
    views = {
        "schema_version": "apphear.fingerspelling.ctc_view_inventory.v1",
        "adapter": identity(),
        "ready_to_train": not blockers,
        "native_eligible_ids": [r["sample_id"] for r in records if r["native_ctc_feasible"]],
        "native_infeasible_retained_ids": [
            r["sample_id"] for r in records if not r["native_ctc_feasible"]
        ],
        "phone_eligible_ids": [r["sample_id"] for r in records if r["phone_ctc_feasible"]],
        "phone_infeasible_retained_ids": [
            r["sample_id"] for r in records if not r["phone_ctc_feasible"]
        ],
        "rule": (
            "A future loss loader must select a feasible view explicitly; "
            "inventory never drops the source"
        ),
    }
    if receipt_ids is not None:
        result["validation_scope"] = "SELECTED_RECEIPTS_ONLY_NOT_FULL_PACKAGE_ADMISSION"
        result["selected_receipt_ids"] = sorted(receipt_ids)
        result["scoped_pending"] = len(receipt_ids) - len(records)
        result["ready_to_train"] = False
        views["ready_to_train"] = False
    result_path = report_path or output / "validation.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    views_path = (
        result_path.with_suffix(".ctc_views.json") if report_path else output / "ctc_views.json"
    )
    views_path.write_text(json.dumps(views, indent=2) + "\n")
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    return result
