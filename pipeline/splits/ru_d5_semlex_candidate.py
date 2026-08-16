"""Prepare and selectively extract the RU-D5 Sem-Lex screening pilot.

This module is intentionally pre-training. It selects only Sem-Lex TRAIN rows,
streams the supplied tar archives to extract only selected members, and records
member hashes. It cannot accept clips, run MediaPipe, assemble Candidate C, read
the AppHear protected test, or mutate the RU-D3 foundation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import tarfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METADATA = Path(r"D:\Downloads\semlex_metadata.csv")
DEFAULT_VIDEO_ARCHIVE = Path(r"D:\Downloads\train.tar.gz")
DEFAULT_POSE_ARCHIVE = Path(r"D:\Downloads\sem-lex-train-poses.tar.gz")
DEFAULT_FOUNDATION = ROOT / "artifacts/recognition_upgrade/ru_d3/repair_candidate_01"
DEFAULT_OUTPUT = ROOT / "artifacts/recognition_upgrade/ru_d5/semlex_candidate_01"
TARGETS = ("KNOW", "WHO", "WE", "COME", "LEAVE")
SINGLE_CLASS_TARGET_SIGNERS = 5
SINGLE_CLASS_CLIPS_PER_SIGNER = 2
PAIR_TARGET_SIGNERS = 5
PAIR_TARGET_PAIRS = 6
SELECTION_SEED = 5105
KNOWN_ARCHIVE_VIDEO_MISSING = {
    "V5XMcoCE0a8XrK5nELEr",
    "puu6X6CTG4oUkQmcj3o5",
}
KNOWN_SUPPLIED_POSE_UNAVAILABLE = {"XRGDr8F4tCHv6uQNwaPd"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _arrayless_file_identity(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [{str(key): str(value or "") for key, value in row.items()} for row in reader]


def _read_semlex_metadata(path: Path) -> list[dict[str, str]]:
    rows = _read_csv(path)
    if not rows:
        raise ValueError(f"Sem-Lex metadata is empty: {path}")
    required = {"video_id", "signer_id", "duration", "split", "label_type", "label"}
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"Sem-Lex metadata missing columns: {sorted(missing)}")
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _norm(value: str) -> str:
    return value.strip().casefold()


def _metadata_variant_status(row: dict[str, str], gloss: str) -> tuple[str, str]:
    """Apply only a metadata prefilter; video review remains mandatory."""
    if _norm(row["label_type"]) != "asllex":
        return "UNKNOWN_REVIEW_REQUIRED", "freetext label has no phonological metadata"
    sign_type = _norm(row.get("Sign Type", ""))
    major = _norm(row.get("Major Location", ""))
    minor = _norm(row.get("Minor Location", ""))
    nondominant = _norm(row.get("Nondominant Handshape", ""))
    expected = {
        "KNOW": "one handed" in sign_type and major == "head" and minor == "forehead",
        "WHO": "one handed" in sign_type and major == "head" and minor == "chin",
        "WE": "one handed" in sign_type and major == "body" and minor == "clavicle",
        "COME": "one handed" in sign_type and major == "neutral",
        "LEAVE": "symmetrical or alternating" in sign_type and bool(nondominant),
    }[gloss]
    if expected:
        return "METADATA_MATCH", "ASL-LEX fields match the AppHear lexical family"
    return "METADATA_MISMATCH", "ASL-LEX fields conflict with the target lexical family"


def _dedupe_target_rows(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    best: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        if _norm(row["split"]) != "train":
            continue
        gloss = row["label"].strip().upper()
        if gloss not in TARGETS:
            continue
        key = (gloss, row["video_id"].strip())
        if not key[1]:
            continue
        current = best.get(key)
        rank = 0 if _norm(row["label_type"]) == "asllex" else 1
        current_rank = (
            0 if current is not None and _norm(current["label_type"]) == "asllex" else 1
        )
        if current is None or rank < current_rank:
            best[key] = row
    return list(best.values())


def _duration(row: dict[str, str]) -> float:
    try:
        return float(row["duration"])
    except ValueError:
        return float("inf")


def _signer_order(gloss: str, signer: str) -> str:
    value = f"{SELECTION_SEED}:{gloss}:{signer}".encode()
    return hashlib.sha256(value).hexdigest()


def _rank_clips(rows: list[dict[str, str]], gloss: str) -> list[dict[str, str]]:
    upper = 3500.0 if gloss == "LEAVE" else 2500.0

    def key(row: dict[str, str]) -> tuple[int, int, float, str]:
        status, _ = _metadata_variant_status(row, gloss)
        metadata_rank = {"METADATA_MATCH": 0, "UNKNOWN_REVIEW_REQUIRED": 1}.get(status, 2)
        duration = _duration(row)
        duration_rank = 0 if 700.0 <= duration <= upper else 1
        return metadata_rank, duration_rank, duration, row["video_id"]

    return sorted(rows, key=key)


def _select_single_class(rows: list[dict[str, str]], gloss: str) -> list[dict[str, str]]:
    by_signer: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["label"].strip().upper() != gloss:
            continue
        status, _ = _metadata_variant_status(row, gloss)
        if status != "METADATA_MISMATCH":
            by_signer[row["signer_id"]].append(row)
    signers = sorted(
        by_signer,
        key=lambda signer: (
            0 if len(by_signer[signer]) >= SINGLE_CLASS_CLIPS_PER_SIGNER else 1,
            _signer_order(gloss, signer),
        ),
    )[:SINGLE_CLASS_TARGET_SIGNERS]
    selected: list[dict[str, str]] = []
    for signer in signers:
        selected.extend(
            _rank_clips(by_signer[signer], gloss)[:SINGLE_CLASS_CLIPS_PER_SIGNER]
        )
    return selected


def _select_we_come(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: {"WE": [], "COME": []}
    )
    for row in rows:
        gloss = row["label"].strip().upper()
        if gloss not in {"WE", "COME"}:
            continue
        status, _ = _metadata_variant_status(row, gloss)
        if status != "METADATA_MISMATCH":
            grouped[row["signer_id"]][gloss].append(row)
    overlap = [
        signer
        for signer, classes in grouped.items()
        if classes["WE"] and classes["COME"]
    ]
    overlap.sort(key=lambda signer: _signer_order("WE_COME", signer))
    overlap = overlap[:PAIR_TARGET_SIGNERS]
    ranked = {
        signer: {
            gloss: _rank_clips(grouped[signer][gloss], gloss)
            for gloss in ("WE", "COME")
        }
        for signer in overlap
    }
    selected: list[dict[str, str]] = []
    pair_count = 0
    round_index = 0
    while pair_count < PAIR_TARGET_PAIRS:
        added = False
        for signer in overlap:
            we = ranked[signer]["WE"]
            come = ranked[signer]["COME"]
            if round_index < len(we) and round_index < len(come):
                selected.extend((we[round_index], come[round_index]))
                pair_count += 1
                added = True
                if pair_count >= PAIR_TARGET_PAIRS:
                    break
        if not added:
            break
        round_index += 1
    return selected


def _variant_registry(foundation: Path) -> dict[str, dict[str, str]]:
    value = json.loads((foundation / "variant_registry.json").read_text(encoding="utf-8"))
    return value["variants"]


def _manifest_rows(
    selected: list[dict[str, str]], variants: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in sorted(
        selected,
        key=lambda item: (
            TARGETS.index(item["label"].strip().upper()),
            item["signer_id"],
            item["video_id"],
        ),
    ):
        gloss = row["label"].strip().upper()
        status, reason = _metadata_variant_status(row, gloss)
        video_id = row["video_id"].strip()
        rows.append(
            {
                "candidate_id": f"SEMLEX-TRAIN-{video_id}",
                "source": "SEM_LEX",
                "source_split": "train",
                "canonical_gloss": gloss,
                "source_label": row["label"],
                "source_label_type": row["label_type"],
                "source_signer_id": f"SEMLEX-{row['signer_id']}",
                "source_video_id": video_id,
                "duration_ms": row["duration"],
                "video_archive_member": f"train/{video_id}.webm",
                "pose_archive_member": f"train/{video_id}.npy",
                "metadata_variant_status": status,
                "metadata_variant_reason": reason,
                "expected_variant": variants[gloss]["variant_id"],
                "expected_hands": variants[gloss]["required_hands"],
                "sign_type": row.get("Sign Type", ""),
                "handshape": row.get("Handshape", ""),
                "path_movement": row.get("Path Movement", ""),
                "major_location": row.get("Major Location", ""),
                "minor_location": row.get("Minor Location", ""),
                "nondominant_handshape": row.get("Nondominant Handshape", ""),
                "manual_variant_decision": "PENDING",
                "manual_boundary_decision": "PENDING",
                "manual_framing_decision": "PENDING",
                "apphear_extraction_decision": "NOT_RUN",
                "final_decision": "PENDING",
                "rejection_reason": "",
                "raw_video_path": "",
                "raw_video_sha256": "",
                "provided_pose_path": "",
                "provided_pose_sha256": "",
            }
        )
    return rows


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    required = [
        args.metadata,
        args.video_archive,
        args.pose_archive,
        args.foundation / "variant_registry.json",
        args.foundation / "dataset/train.npz",
        args.foundation / "dataset/manifests/train.csv",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing RU-D5 Sem-Lex input: {missing}")
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output: {args.output}")
    args.output.mkdir(parents=True)
    all_rows = _read_semlex_metadata(args.metadata)
    target_rows = _dedupe_target_rows(all_rows)
    selected: list[dict[str, str]] = []
    for gloss in ("KNOW", "WHO", "LEAVE"):
        selected.extend(_select_single_class(target_rows, gloss))
    selected.extend(_select_we_come(target_rows))
    manifest = _manifest_rows(selected, _variant_registry(args.foundation))
    _write_csv(args.output / "semlex_screening_manifest.csv", manifest)
    counts = Counter(row["canonical_gloss"] for row in manifest)
    signers = {
        gloss: len(
            {
                row["source_signer_id"]
                for row in manifest
                if row["canonical_gloss"] == gloss
            }
        )
        for gloss in TARGETS
    }
    overlap = sorted(
        {
            row["source_signer_id"]
            for row in manifest
            if row["canonical_gloss"] == "WE"
        }
        & {
            row["source_signer_id"]
            for row in manifest
            if row["canonical_gloss"] == "COME"
        }
    )
    summary = {
        "phase": "RU-D5",
        "stage": "semlex_train_manifest_prepared",
        "selection_seed": SELECTION_SEED,
        "metadata_rows": len(all_rows),
        "deduplicated_train_target_rows": len(target_rows),
        "selected_rows": len(manifest),
        "selected_counts": dict(counts),
        "selected_signers": signers,
        "we_come_overlapping_selected_signers": overlap,
        "metadata_sha256": _sha256(args.metadata),
        "foundation_train_sha256": _sha256(args.foundation / "dataset/train.npz"),
        "foundation_manifest_sha256": _sha256(
            args.foundation / "dataset/manifests/train.csv"
        ),
        "video_archive_identity": _arrayless_file_identity(args.video_archive),
        "pose_archive_identity": _arrayless_file_identity(args.pose_archive),
        "videos_extracted": 0,
        "poses_extracted": 0,
        "accepted_for_training": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "protected_test_accessed": False,
        "passed": all(row["source_split"] == "train" for row in manifest),
    }
    summary["screening_manifest_sha256"] = _sha256(
        args.output / "semlex_screening_manifest.csv"
    )
    _write_json(args.output / "prepare_summary.json", summary)
    return summary


def _canonical_member(name: str) -> str:
    pure = PurePosixPath(name)
    parts = [part for part in pure.parts if part not in {".", ""}]
    if not parts or ".." in parts or pure.is_absolute():
        raise ValueError(f"unsafe tar member path: {name}")
    return "/".join(parts)


def _extract_archive_members(
    archive: Path,
    wanted: dict[str, Path],
    archive_kind: str,
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    remaining = set(wanted)
    found: dict[str, dict[str, Any]] = {}
    for member_name, destination in wanted.items():
        if not destination.is_file():
            continue
        found[member_name] = {
            "archive_member": member_name,
            "archive_member_bytes": destination.stat().st_size,
            "local_path": str(destination.resolve()),
            "sha256": _sha256(destination),
            "extraction_status": "REUSED_EXISTING",
        }
        remaining.remove(member_name)
    if not remaining:
        print(
            f"[{archive_kind}] all {len(found)} selected members already exist; "
            "archive scan skipped",
            flush=True,
        )
        return found, remaining
    scanned = 0
    print(
        f"[{archive_kind}] scanning {archive} for {len(remaining)} missing selected members; "
        f"reusing={len(found)}",
        flush=True,
    )
    with tarfile.open(archive, mode="r|gz") as handle:
        for member in handle:
            scanned += 1
            if scanned % 5000 == 0:
                print(
                    f"[{archive_kind}] scanned={scanned} extracted={len(found)} "
                    f"remaining={len(remaining)}",
                    flush=True,
                )
            if not member.isfile():
                continue
            canonical = _canonical_member(member.name)
            if canonical not in remaining:
                continue
            destination = wanted[canonical]
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if destination.stat().st_size != member.size:
                    raise FileExistsError(
                        f"existing selected file has wrong size; refusing overwrite: {destination}"
                    )
            else:
                source = handle.extractfile(member)
                if source is None:
                    raise OSError(f"cannot read selected tar member: {member.name}")
                with source, destination.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
            found[canonical] = {
                "archive_member": canonical,
                "archive_member_bytes": member.size,
                "local_path": str(destination.resolve()),
                "sha256": _sha256(destination),
                "extraction_status": "EXTRACTED_NOW",
            }
            remaining.remove(canonical)
            print(
                f"[{archive_kind}] extracted {canonical} ({len(found)}/{len(wanted)})",
                flush=True,
            )
            if not remaining:
                break
    if remaining:
        print(
            f"[{archive_kind}] unresolved members={len(remaining)}: "
            f"{sorted(remaining)[:10]}",
            flush=True,
        )
    return found, remaining


def _existing_distribution(
    manifest: list[dict[str, str]], available_ids: set[str]
) -> dict[str, Any]:
    present = [row for row in manifest if row["source_video_id"] in available_ids]
    counts: dict[str, dict[str, int]] = {}
    for gloss in TARGETS:
        rows = [row for row in present if row["canonical_gloss"] == gloss]
        counts[gloss] = {
            "clips": len(rows),
            "signers": len({row["source_signer_id"] for row in rows}),
        }
    we_signers = {
        row["source_signer_id"]
        for row in present
        if row["canonical_gloss"] == "WE"
    }
    come_signers = {
        row["source_signer_id"]
        for row in present
        if row["canonical_gloss"] == "COME"
    }
    paired = sorted(we_signers & come_signers)
    paired_rows = [
        row
        for row in present
        if row["canonical_gloss"] in {"WE", "COME"}
        and row["source_signer_id"] in paired
    ]
    return {
        "counts": counts,
        "we_come_paired_signers": paired,
        "we_come_pair_eligible_rows": len(paired_rows),
    }


def prepare_recovery(args: argparse.Namespace) -> dict[str, Any]:
    manifest = _read_csv(args.output / "semlex_screening_manifest.csv")
    metadata = _read_semlex_metadata(args.metadata)
    video_dir = args.output / "inbound/videos"
    available_ids = {
        row["source_video_id"]
        for row in manifest
        if (video_dir / f"{row['source_video_id']}.webm").is_file()
    }
    resolution_rows: list[dict[str, Any]] = []
    for row in manifest:
        video_id = row["source_video_id"]
        available = video_id in available_ids
        same_class_signer = sorted(
            {
                item["video_id"]
                for item in metadata
                if _norm(item["split"]) == "train"
                and item["label"].strip().upper() == row["canonical_gloss"]
                and f"SEMLEX-{item['signer_id']}" == row["source_signer_id"]
                and item["video_id"] != video_id
            }
        )
        if available:
            status = "AVAILABLE_EXISTING"
            local_path = video_dir / f"{video_id}.webm"
            local_hash = _sha256(local_path)
        else:
            status = "CANONICAL_MEMBER_MISSING_ALT_PATH_AUDIT_PENDING"
            local_path = Path()
            local_hash = ""
        if row["canonical_gloss"] in {"WE", "COME"}:
            role = "WE_COME_PAIR_MEMBER"
            replacement = (
                "NO_VALID_SAME_SIGNER_REPLACEMENT"
                if not available and not same_class_signer
                else "NOT_REQUIRED_OR_NOT_YET_DECIDED"
            )
        elif row["canonical_gloss"] == "LEAVE":
            role = "LEAVE_DIVERSITY_MEMBER"
            replacement = (
                "NOT_REQUIRED_SIGNER_REMAINS_REPRESENTED"
                if not available
                and any(
                    item["canonical_gloss"] == "LEAVE"
                    and item["source_signer_id"] == row["source_signer_id"]
                    and item["source_video_id"] in available_ids
                    for item in manifest
                )
                else "NOT_REQUIRED_OR_NOT_YET_DECIDED"
            )
        else:
            role = "CLASS_DIVERSITY_MEMBER"
            replacement = "NOT_REQUIRED_OR_NOT_YET_DECIDED"
        resolution_rows.append(
            {
                "candidate_id": row["candidate_id"],
                "canonical_gloss": row["canonical_gloss"],
                "source_signer_id": row["source_signer_id"],
                "source_video_id": video_id,
                "pairing_or_diversity_role": role,
                "expected_archive_member": row["video_archive_member"],
                "archive_video_status": status,
                "matched_archive_member": row["video_archive_member"] if available else "",
                "matched_archive_member_bytes": (
                    (video_dir / f"{video_id}.webm").stat().st_size if available else ""
                ),
                "raw_video_path": str(local_path.resolve()) if available else "",
                "raw_video_sha256": local_hash,
                "metadata_same_class_signer_alternatives": "|".join(same_class_signer),
                "replacement_decision": replacement,
            }
        )
    _write_csv(args.output / "archive_member_resolution.csv", resolution_rows)
    distribution = _existing_distribution(manifest, available_ids)
    missing = [
        row for row in resolution_rows if row["archive_video_status"].endswith("PENDING")
    ]
    summary = {
        "phase": "RU-D5",
        "stage": "semlex_partial_extraction_recovery_prepared",
        "selected_rows": len(manifest),
        "videos_preserved": len(available_ids),
        "canonical_members_missing": len(missing),
        "missing_ids": [row["source_video_id"] for row in missing],
        **distribution,
        "replacement_rows_selected": 0,
        "accepted_for_training": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "protected_test_accessed": False,
        "passed": len(available_ids) + len(missing) == len(manifest),
    }
    _write_json(args.output / "partial_extraction_recovery_summary.json", summary)
    return summary


def audit_missing(args: argparse.Namespace) -> dict[str, Any]:
    resolution_path = args.output / "archive_member_resolution.csv"
    resolution = _read_csv(resolution_path)
    pending = [
        row
        for row in resolution
        if row["archive_video_status"]
        == "CANONICAL_MEMBER_MISSING_ALT_PATH_AUDIT_PENDING"
    ]
    if not pending:
        return {
            "phase": "RU-D5",
            "stage": "semlex_missing_member_audit",
            "pending_rows": 0,
            "archive_scan_skipped": True,
            "passed": True,
        }
    wanted = {row["source_video_id"].casefold(): row for row in pending}
    matches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scanned = 0
    print(
        f"[missing-video-audit] scanning names for only {len(wanted)} basenames: "
        f"{sorted(row['source_video_id'] for row in pending)}",
        flush=True,
    )
    with tarfile.open(args.video_archive, mode="r|gz") as handle:
        for member in handle:
            scanned += 1
            if scanned % 5000 == 0:
                print(
                    f"[missing-video-audit] scanned={scanned} matches="
                    f"{sum(len(value) for value in matches.values())}",
                    flush=True,
                )
            if not member.isfile():
                continue
            canonical = _canonical_member(member.name)
            stem = PurePosixPath(canonical).stem.casefold()
            if stem not in wanted:
                continue
            source_row = wanted[stem]
            suffix = PurePosixPath(canonical).suffix.lower() or ".bin"
            destination = (
                args.output
                / "inbound/videos"
                / f"{source_row['source_video_id']}{suffix}"
            )
            if not destination.exists():
                source = handle.extractfile(member)
                if source is None:
                    raise OSError(f"cannot read alternate tar member: {member.name}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                with source, destination.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
            matches[stem].append(
                {
                    "member": canonical,
                    "bytes": member.size,
                    "path": str(destination.resolve()),
                    "sha256": _sha256(destination),
                }
            )
    for row in resolution:
        if row["archive_video_status"] != (
            "CANONICAL_MEMBER_MISSING_ALT_PATH_AUDIT_PENDING"
        ):
            continue
        found = matches.get(row["source_video_id"].casefold(), [])
        if len(found) > 1:
            raise ValueError(
                f"multiple alternate members match {row['source_video_id']}: {found}"
            )
        if found:
            match = found[0]
            row["archive_video_status"] = "FOUND_ALTERNATE_MEMBER"
            row["matched_archive_member"] = str(match["member"])
            row["matched_archive_member_bytes"] = str(match["bytes"])
            row["raw_video_path"] = str(match["path"])
            row["raw_video_sha256"] = str(match["sha256"])
            row["replacement_decision"] = "ORIGINAL_ID_RECOVERED_ALTERNATE_MEMBER"
        else:
            row["archive_video_status"] = "ARCHIVE_VIDEO_MISSING"
    _write_csv(resolution_path, resolution)
    unresolved = [
        row for row in resolution if row["archive_video_status"] == "ARCHIVE_VIDEO_MISSING"
    ]
    summary = {
        "phase": "RU-D5",
        "stage": "semlex_missing_member_audit",
        "archive_members_scanned": scanned,
        "target_basenames": len(pending),
        "alternate_members_found": sum(len(value) for value in matches.values()),
        "archive_members_missing": len(unresolved),
        "missing_ids": [row["source_video_id"] for row in unresolved],
        "replacement_rows_selected": 0,
        "accepted_for_training": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "protected_test_accessed": False,
        "passed": True,
    }
    _write_json(args.output / "missing_member_audit_summary.json", summary)
    return summary


def extract_selected(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = args.output / "semlex_screening_manifest.csv"
    manifest = _read_csv(manifest_path)
    if any(row["source_split"] != "train" for row in manifest):
        raise ValueError("non-train Sem-Lex row in screening manifest")
    resolution_path = args.output / "archive_member_resolution.csv"
    if not resolution_path.is_file():
        raise FileNotFoundError(
            "archive member resolution is missing; run prepare-recovery first"
        )
    resolution = _read_csv(resolution_path)
    if any(row["archive_video_status"].endswith("PENDING") for row in resolution):
        raise ValueError("alternate-path audit is pending; run audit-missing first")
    resolved_by_id = {row["source_video_id"]: row for row in resolution}
    eligible = [
        row
        for row in manifest
        if resolved_by_id[row["source_video_id"]]["archive_video_status"]
        in {"AVAILABLE_EXISTING", "FOUND_ALTERNATE_MEMBER"}
    ]
    videos: dict[str, dict[str, Any]] = {}
    for row in eligible:
        resolved = resolved_by_id[row["source_video_id"]]
        path = Path(resolved["raw_video_path"])
        if not path.is_file():
            raise FileNotFoundError(f"resolved video is missing: {path}")
        videos[row["video_archive_member"]] = {
            "archive_member": resolved["matched_archive_member"],
            "archive_member_bytes": int(resolved["matched_archive_member_bytes"]),
            "local_path": str(path.resolve()),
            "sha256": _sha256(path),
            "extraction_status": "REUSED_EXISTING",
        }
    print(
        f"[videos] reusing {len(videos)} resolved files; video archive scan skipped",
        flush=True,
    )
    pose_wanted = {
        row["pose_archive_member"]: args.output
        / "inbound/provided_poses"
        / f"{row['source_video_id']}.npy"
        for row in eligible
    }
    poses, missing_poses = _extract_archive_members(
        args.pose_archive, pose_wanted, "poses"
    )
    extraction_rows: list[dict[str, Any]] = []
    for row in eligible:
        video = videos[row["video_archive_member"]]
        pose = poses.get(row["pose_archive_member"])
        extraction_rows.append(
            {
                "candidate_id": row["candidate_id"],
                "source_split": row["source_split"],
                "canonical_gloss": row["canonical_gloss"],
                "source_signer_id": row["source_signer_id"],
                "source_video_id": row["source_video_id"],
                "video_archive_member": video["archive_member"],
                "video_archive_member_bytes": video["archive_member_bytes"],
                "raw_video_path": video["local_path"],
                "raw_video_sha256": video["sha256"],
                "pose_archive_member": row["pose_archive_member"],
                "pose_archive_member_bytes": pose["archive_member_bytes"] if pose else "",
                "provided_pose_path": pose["local_path"] if pose else "",
                "provided_pose_sha256": pose["sha256"] if pose else "",
                "provided_pose_status": (
                    "AVAILABLE" if pose else "SUPPLIED_POSE_UNAVAILABLE"
                ),
            }
        )
    _write_csv(args.output / "selective_extraction_manifest.csv", extraction_rows)
    summary = {
        "phase": "RU-D5",
        "stage": "semlex_selected_members_extracted",
        "selected_rows": len(manifest),
        "archive_missing_video_rows": len(manifest) - len(eligible),
        "eligible_video_rows": len(eligible),
        "videos_available": len(videos),
        "poses_available": len(poses),
        "poses_missing": len(missing_poses),
        "extracted_video_bytes": sum(item["archive_member_bytes"] for item in videos.values()),
        "extracted_pose_bytes": sum(item["archive_member_bytes"] for item in poses.values()),
        "extraction_manifest_sha256": _sha256(
            args.output / "selective_extraction_manifest.csv"
        ),
        "accepted_for_training": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "protected_test_accessed": False,
        "passed": len(videos) == len(eligible)
        and len(poses) + len(missing_poses) == len(eligible),
    }
    _write_json(args.output / "selective_extraction_summary.json", summary)
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    manifest_path = args.output / "semlex_screening_manifest.csv"
    prepare_path = args.output / "prepare_summary.json"
    if not manifest_path.is_file():
        errors.append(f"missing {manifest_path}")
    if not prepare_path.is_file():
        errors.append(f"missing {prepare_path}")
    manifest = _read_csv(manifest_path) if manifest_path.is_file() else []
    if any(row["source_split"] != "train" for row in manifest):
        errors.append("Sem-Lex held-out row leaked into screening manifest")
    if any(row["final_decision"] != "PENDING" for row in manifest):
        errors.append("pre-screening manifest prematurely accepted/rejected a row")
    extraction_path = args.output / "selective_extraction_manifest.csv"
    if args.require_extracted:
        if not extraction_path.is_file():
            errors.append(f"missing {extraction_path}")
        else:
            extracted = _read_csv(extraction_path)
            resolution_path = args.output / "archive_member_resolution.csv"
            resolution = _read_csv(resolution_path) if resolution_path.is_file() else []
            eligible_count = sum(
                row["archive_video_status"]
                in {"AVAILABLE_EXISTING", "FOUND_ALTERNATE_MEMBER"}
                for row in resolution
            )
            if len(extracted) != eligible_count:
                errors.append("selective extraction row count mismatch")
            for row in extracted:
                required_files = [("raw_video_path", "raw_video_sha256")]
                pose_status = row.get("provided_pose_status", "")
                if pose_status == "AVAILABLE":
                    required_files.append(
                        ("provided_pose_path", "provided_pose_sha256")
                    )
                elif pose_status != "SUPPLIED_POSE_UNAVAILABLE":
                    errors.append(
                        "invalid supplied-pose status for "
                        f"{row.get('source_video_id', '')}: {pose_status}"
                    )
                for path_key, hash_key in required_files:
                    path_value = row[path_key]
                    path = Path(path_value) if path_value else Path()
                    if not path_value or not path.is_file():
                        errors.append(f"missing extracted file: {path}")
                    elif _sha256(path) != row[hash_key]:
                        errors.append(f"extracted hash mismatch: {path}")
    result = {
        "run_dir": str(args.output.resolve()),
        "manifest_rows": len(manifest),
        "require_extracted": args.require_extracted,
        "errors": errors,
        "accepted_for_training": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "protected_test_accessed": False,
        "passed": not errors,
    }
    _write_json(args.output / "pre_screen_check.json", result)
    return result


def finalize_known_gaps(args: argparse.Namespace) -> dict[str, Any]:
    """Record already-audited archive gaps without reading either archive."""
    resolution_path = args.output / "archive_member_resolution.csv"
    extraction_path = args.output / "selective_extraction_manifest.csv"
    resolution = _read_csv(resolution_path)
    extracted = _read_csv(extraction_path)

    seen_missing_videos: set[str] = set()
    for row in resolution:
        video_id = row["source_video_id"]
        if video_id in KNOWN_ARCHIVE_VIDEO_MISSING:
            row["archive_video_status"] = "ARCHIVE_VIDEO_MISSING"
            seen_missing_videos.add(video_id)
    if seen_missing_videos != KNOWN_ARCHIVE_VIDEO_MISSING:
        raise ValueError(
            "known missing-video rows do not match the resolution manifest: "
            f"{sorted(KNOWN_ARCHIVE_VIDEO_MISSING - seen_missing_videos)}"
        )
    _write_csv(resolution_path, resolution)

    seen_missing_poses: set[str] = set()
    for row in extracted:
        video_id = row["source_video_id"]
        if video_id in KNOWN_SUPPLIED_POSE_UNAVAILABLE:
            if not Path(row["raw_video_path"]).is_file():
                raise FileNotFoundError(
                    f"raw video required for missing-pose row: {row['raw_video_path']}"
                )
            row["provided_pose_path"] = ""
            row["provided_pose_sha256"] = ""
            row["provided_pose_status"] = "SUPPLIED_POSE_UNAVAILABLE"
            seen_missing_poses.add(video_id)
    if seen_missing_poses != KNOWN_SUPPLIED_POSE_UNAVAILABLE:
        raise ValueError(
            "known missing-pose rows do not match the extraction manifest: "
            f"{sorted(KNOWN_SUPPLIED_POSE_UNAVAILABLE - seen_missing_poses)}"
        )
    _write_csv(extraction_path, extracted)

    available_poses = sum(row["provided_pose_status"] == "AVAILABLE" for row in extracted)
    unavailable_poses = sum(
        row["provided_pose_status"] == "SUPPLIED_POSE_UNAVAILABLE"
        for row in extracted
    )
    summary = {
        "phase": "RU-D5",
        "stage": "semlex_known_archive_gaps_finalized",
        "archive_scans_performed": 0,
        "archive_video_missing_ids": sorted(seen_missing_videos),
        "video_eligible_rows": len(extracted),
        "supplied_poses_available": available_poses,
        "supplied_pose_unavailable_ids": sorted(seen_missing_poses),
        "pose_equivalence_eligible_rows": available_poses,
        "replacement_rows_selected": 0,
        "accepted_for_training": 0,
        "candidate_c_built": False,
        "training_authorized": False,
        "protected_test_accessed": False,
        "passed": unavailable_poses == len(KNOWN_SUPPLIED_POSE_UNAVAILABLE),
    }
    _write_json(args.output / "known_archive_gaps_summary.json", summary)
    return summary


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    for command in (
        "prepare",
        "prepare-recovery",
        "audit-missing",
        "extract-selected",
        "finalize-known-gaps",
        "check",
    ):
        child = sub.add_parser(command)
        child.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
        child.add_argument("--video-archive", type=Path, default=DEFAULT_VIDEO_ARCHIVE)
        child.add_argument("--pose-archive", type=Path, default=DEFAULT_POSE_ARCHIVE)
        child.add_argument("--foundation", type=Path, default=DEFAULT_FOUNDATION)
        child.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
        if command == "check":
            child.add_argument("--require-extracted", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    result = {
        "prepare": prepare,
        "prepare-recovery": prepare_recovery,
        "audit-missing": audit_missing,
        "extract-selected": extract_selected,
        "finalize-known-gaps": finalize_known_gaps,
        "check": check,
    }[args.command](args)
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
