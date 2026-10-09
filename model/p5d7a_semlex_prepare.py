"""P5-D7A Sem-Lex accepted-set preparation and archive indexing.

The quick ``prepare`` command never scans the large archive. The project-lead-run
``index-archive`` command performs one sequential, metadata-only archive pass,
hashes raw members without decoding frames, and finalizes lineage manifests.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import tarfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/recognition_upgrade"
OUT = BASE / "p5_representation_v2/p5d7a_semlex_extraction_prep_01"
D5 = BASE / "p5_representation_v2/p5d5_semlex_form_review_01"
DECISIONS = Path(r"C:\Users\Gigabyte\Downloads\semlex_human_decision_sheet_completed.csv")
SEMLEX_META = Path(r"D:\Downloads\semlex_metadata.csv")
HISTORICAL_EXACT = BASE / "ru_d5/semlex_candidate_01/candidate_c/final_external_lineage.csv"
VISUAL_SELECTION = BASE / "p5_representation_v2/p5d6_semlex_visual_review_01/visual_review_selection.csv"
ARCHIVE = Path(r"G:\SEM LEX\train.tar.gz")
APPHEAR_TRAIN = BASE / "phase1_full_vocab/dataset_v1/manifests/train.csv"
PROGRESS = ROOT / "context/progress-tracker.md"
PROGRESS_SHA = "12cf08f81959a413a60aa1f869615a24485a41ee3d796e61fce7489ae5c480cf"
EXPECTED_DECISION_SHA = "36eaff387b8d7ce91831fbb419461142d4d82edcbf37a67b779fb3af2e03fdb7"
EXPECTED_SEMLEX_META_SHA = "f4250b2877e738f028e4b9517922952a350ec8952e59d53ceabdd778938fc3c3"
UNRESOLVED = {"IF", "OLD", "GET", "TURN", "ANY"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def norm(value: Any) -> str:
    text = re.sub(r"\s*\d+$", "", str(value).strip().lower())
    return re.sub(r"[^a-z0-9]", "", text)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def verify_sources() -> None:
    if sha256(PROGRESS) != PROGRESS_SHA:
        raise RuntimeError("progress-tracker hash mismatch")
    if sha256(DECISIONS) != EXPECTED_DECISION_SHA:
        raise RuntimeError("completed human decision sheet hash mismatch")
    if sha256(SEMLEX_META) != EXPECTED_SEMLEX_META_SHA:
        raise RuntimeError("Sem-Lex metadata hash mismatch")
    if not ARCHIVE.is_file():
        raise RuntimeError(f"Sem-Lex archive missing: {ARCHIVE}")


def accepted_classes() -> tuple[list[dict[str, Any]], dict[str, str]]:
    decisions = read_csv(DECISIONS)
    allowed = {"ACCEPT_EXACT_FORM", "ACCEPT_COMPATIBLE_VARIANT", "UNRESOLVED", "REJECT_FORM_MISMATCH"}
    if len(decisions) != 68 or len({row["class_id"] for row in decisions}) != 68:
        raise RuntimeError("P5D7A_BLOCKED_HUMAN_REVIEW_SET_MISMATCH")
    if any(row["human_decision"] not in allowed for row in decisions):
        raise RuntimeError("invalid human decision")
    accepted_human = [row for row in decisions if row["human_decision"].startswith("ACCEPT_")]
    unresolved = {row["canonical_gloss"] for row in decisions if row["human_decision"] == "UNRESOLVED"}
    if Counter(row["human_decision"] for row in decisions) != Counter(
        {"ACCEPT_EXACT_FORM": 45, "ACCEPT_COMPATIBLE_VARIANT": 18, "UNRESOLVED": 5}
    ) or unresolved != UNRESOLVED:
        raise RuntimeError("P5D7A_BLOCKED_HUMAN_REVIEW_SET_MISMATCH")
    qualified = read_csv(D5 / "semlex_target_class_qualification.csv")
    pre_exact = [row for row in qualified if row["qualification_state"] == "ACCEPT_METADATA_EXACT"]
    if {(row["apphear_class_id"], row["apphear_gloss"]) for row in pre_exact} != {("36", "COME"), ("221", "WHO")}:
        raise RuntimeError("pre-qualified exact class identity mismatch")
    rows: list[dict[str, Any]] = []
    for row in accepted_human:
        rows.append({
            "apphear_class_id": int(row["class_id"]), "apphear_gloss": row["canonical_gloss"],
            "human_decision": row["human_decision"], "coverage_deficit_level": row["coverage_deficit_level"],
            "review_source": "P5D6_COMPLETED_HUMAN_REVIEW", "reviewer": row.get("reviewer", ""),
            "review_date": row.get("review_date", ""),
        })
    for row in pre_exact:
        rows.append({
            "apphear_class_id": int(row["apphear_class_id"]), "apphear_gloss": row["apphear_gloss"],
            "human_decision": "ACCEPT_METADATA_EXACT", "coverage_deficit_level": row["coverage_deficit_level"],
            "review_source": "GOVERNED_HISTORICAL_ROW_LEVEL_EXACT", "reviewer": "HISTORICAL_GOVERNED_REVIEW",
            "review_date": "",
        })
    rows.sort(key=lambda row: row["apphear_class_id"])
    if len(rows) != 65 or len({row["apphear_class_id"] for row in rows}) != 65:
        raise RuntimeError("P5D7A_BLOCKED_HUMAN_REVIEW_SET_MISMATCH")
    return rows, {row["class_id"]: row["human_decision"] for row in decisions}


def build_candidate_rows(classes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metadata = read_csv(SEMLEX_META)
    train = [row for row in metadata if row["split"].strip().lower() == "train"]
    by_norm: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_video = {row["video_id"]: row for row in train}
    for row in train:
        by_norm[norm(row["label"])].append(row)
    historical = [
        row for row in read_csv(HISTORICAL_EXACT)
        if row.get("variant_decision") == "EXACT_TARGET" and row["canonical_gloss"] in {"COME", "WHO"}
    ]
    historical_ids = {row["source_video_id"] for row in historical}
    if len(historical) != 15 or len(historical_ids) != 15:
        raise RuntimeError("historical exact Sem-Lex row set mismatch")
    candidates: list[dict[str, Any]] = []
    for accepted in classes:
        gloss = accepted["apphear_gloss"]
        source_rows = (
            [by_video[video_id] for video_id in sorted(historical_ids) if video_id in by_video and norm(by_video[video_id]["label"]) == norm(gloss)]
            if gloss in {"COME", "WHO"}
            else by_norm[norm(gloss)]
        )
        for row in source_rows:
            video_id = row["video_id"]
            candidates.append({
                "apphear_class_id": accepted["apphear_class_id"], "apphear_gloss": gloss,
                "human_decision": accepted["human_decision"],
                "semlex_lexical_id": f"{row['label_type']}:{row['label']}", "semlex_gloss": row["label"],
                "semlex_sample_id": video_id, "semlex_signer_id": row["signer_id"], "semlex_split": row["split"],
                "archive_member": f"train/{video_id}.webm",
                "raw_video_path": f"tar://{ARCHIVE}!train/{video_id}.webm", "raw_sha256": "",
                "raw_bytes": "", "duration_ms": row.get("duration", ""), "source_dataset": "SEM_LEX",
                "mapping_status": "PENDING_ARCHIVE_INDEX", "eligible_for_extraction": False,
                "exclusion_reason": "PENDING_ARCHIVE_INDEX",
            })
    candidates.sort(key=lambda row: (int(row["apphear_class_id"]), row["semlex_sample_id"]))
    if len(candidates) != 2666:
        raise RuntimeError(f"metadata candidate ceiling mismatch: {len(candidates)}")
    return candidates


def prepare() -> None:
    verify_sources()
    OUT.mkdir(parents=True, exist_ok=True)
    classes, _ = accepted_classes()
    candidates = build_candidate_rows(classes)
    atomic_csv(OUT / "p5d7a_human_accepted_class_set.csv", classes)
    atomic_json(OUT / "review_provenance_status.json", {
        "status": "REVIEW_PROVENANCE_METADATA_INCOMPLETE",
        "blank_reviewer_rows": 68, "blank_review_date_rows": 68,
        "blocks_external_merge_or_training": True,
        "blocks_preparation_or_smoke": False,
        "original_decision_sheet_sha256": sha256(DECISIONS),
    })
    atomic_csv(OUT / "semlex_accepted_raw_manifest.csv", candidates)
    inventory_fields = ["raw_video_path", "archive_member", "filename", "file_size", "raw_sha256", "semlex_sample_id", "semlex_lexical_id", "gloss", "signer_id", "split", "duration_ms", "fps", "frame_count", "width", "height"]
    atomic_csv(OUT / "semlex_raw_inventory.csv", [], inventory_fields)
    audit_fields = ["semlex_sample_id", "apphear_class_id", "apphear_gloss", "status", "reason", "canonical_sample_id"]
    atomic_csv(OUT / "semlex_raw_join_audit.csv", [], audit_fields)
    atomic_csv(OUT / "semlex_duplicate_audit.csv", [], ["duplicate_type", "value", "sample_ids", "action"])
    atomic_csv(OUT / "semlex_apphear_lineage_overlap_audit.csv", [], ["semlex_sample_id", "apphear_sample_id", "evidence", "status"])

    visual = [row for row in read_csv(VISUAL_SELECTION) if row["side"] == "SEMLEX"]
    candidate_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        candidate_groups[candidate["semlex_sample_id"]].append(candidate)
    candidate_by_id = {
        sample_id: rows[0] for sample_id, rows in candidate_groups.items()
        if len({row["apphear_class_id"] for row in rows}) == 1
    }
    accepted_visual = [row for row in visual if row["sample_id"] in candidate_by_id and Path(row["viewer_media_path"]).is_file()]
    exact = [row for row in accepted_visual if candidate_by_id[row["sample_id"]]["human_decision"] == "ACCEPT_EXACT_FORM"]
    variant = [row for row in accepted_visual if candidate_by_id[row["sample_id"]]["human_decision"] == "ACCEPT_COMPATIBLE_VARIANT"]
    chosen: list[dict[str, str]] = []
    for pool in (exact, variant):
        for row in sorted(pool, key=lambda item: hashlib.sha256(("P5D7A_SMOKE|" + item["sample_id"]).encode()).hexdigest()):
            if row["class_id"] not in {item["class_id"] for item in chosen} and row["signer_id"] not in {item["signer_id"] for item in chosen}:
                chosen.append(row); break
    for row in sorted(accepted_visual, key=lambda item: hashlib.sha256(("P5D7A_SMOKE3|" + item["sample_id"]).encode()).hexdigest()):
        if len(chosen) == 3: break
        if row["class_id"] not in {item["class_id"] for item in chosen} and row["signer_id"] not in {item["signer_id"] for item in chosen}:
            chosen.append(row)
    if len(chosen) != 3:
        raise RuntimeError("could not construct governed three-video smoke set")
    smoke = []
    for row in chosen:
        item = dict(candidate_by_id[row["sample_id"]])
        path = Path(row["viewer_media_path"])
        item.update({"raw_video_path": str(path), "raw_sha256": sha256(path), "raw_bytes": path.stat().st_size,
                     "mapping_status": "VISUAL_REVIEW_RAW_COPY_VERIFIED", "eligible_for_extraction": True,
                     "exclusion_reason": ""})
        smoke.append(item)
    atomic_csv(OUT / "p5d7a_smoke_test_manifest.csv", smoke)
    atomic_json(OUT / "p5d7a_prepare_status.json", {
        "accepted_classes": len(classes), "metadata_candidate_ceiling": len(candidates),
        "unique_metadata_sample_ids": len(candidate_groups),
        "conflicting_apphear_mapping_sample_ids": sum(
            len({row["apphear_class_id"] for row in rows}) > 1 for rows in candidate_groups.values()
        ),
        "smoke_rows": len(smoke), "archive_index_required": True,
        "archive_index_executed": False, "full_extraction_executed": False,
    })
    print(json.dumps({"accepted_classes": 65, "candidate_ceiling": 2666, "smoke_rows": 3,
                      "next_project_lead_command": "index-archive"}, indent=2))


def index_archive() -> None:
    """Project-lead-run long job: scan/hash archive members without video decoding."""
    verify_sources()
    candidates = read_csv(OUT / "semlex_accepted_raw_manifest.csv")
    candidate_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        candidate_groups[row["semlex_sample_id"]].append(row)
    canonical_candidates: list[dict[str, str]] = []
    metadata_duplicate_audits: list[dict[str, Any]] = []
    mapping_conflicts: set[str] = set()
    for sample_id, rows in sorted(candidate_groups.items()):
        classes = sorted({row["apphear_class_id"] for row in rows}, key=int)
        if len(classes) > 1:
            mapping_conflicts.add(sample_id)
            metadata_duplicate_audits.append({
                "duplicate_type": "LABEL_MAPPING_CONFLICT", "value": sample_id,
                "sample_ids": sample_id, "action": "EXCLUDE; APPHEAR_CLASSES=" + "|".join(classes),
            })
            canonical_candidates.append(rows[0])
            continue
        canonical_candidates.append(rows[0])
        if len(rows) > 1:
            metadata_duplicate_audits.append({
                "duplicate_type": "DUPLICATE_METADATA_ROW", "value": sample_id,
                "sample_ids": "|".join([sample_id] * len(rows)),
                "action": f"KEEP ONE CANONICAL ROW; EXCLUDE {len(rows)-1} DUPLICATE ROW(S)",
            })
    metadata_rows = read_csv(SEMLEX_META)
    metadata_by_id = {row["video_id"]: row for row in metadata_rows}
    inventory: list[dict[str, Any]] = []
    last_percent = -1
    started = time.monotonic()
    with tarfile.open(ARCHIVE, "r:gz") as archive:
        for ordinal, member in enumerate(archive, 1):
            if not member.isfile() or not member.name.lower().endswith(".webm"):
                continue
            normalized = member.name.lstrip("./")
            video_id = Path(normalized).stem
            source = archive.extractfile(member)
            if source is None:
                continue
            digest = hashlib.sha256()
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
            meta = metadata_by_id.get(video_id, {})
            inventory.append({
                "raw_video_path": f"tar://{ARCHIVE}!{normalized}", "archive_member": normalized,
                "filename": Path(normalized).name, "file_size": member.size, "raw_sha256": digest.hexdigest(),
                "semlex_sample_id": video_id, "semlex_lexical_id": f"{meta.get('label_type','')}:{meta.get('label','')}" if meta else "",
                "gloss": meta.get("label", ""), "signer_id": meta.get("signer_id", ""),
                "split": meta.get("split", ""), "duration_ms": meta.get("duration", ""),
                "fps": "", "frame_count": "", "width": "", "height": "",
            })
            compressed = getattr(archive.fileobj, "fileobj", None)
            position = compressed.tell() if compressed is not None else 0
            percent = min(100, int(100 * position / ARCHIVE.stat().st_size))
            if percent > last_percent:
                elapsed = time.monotonic() - started
                print(f"\rArchive inventory: {percent:3d}% | videos: {len(inventory)} | elapsed: {elapsed/60:.1f} min", end="", flush=True)
                last_percent = percent
    print()
    atomic_csv(OUT / "semlex_raw_inventory.csv", inventory)
    inv_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in inventory:
        inv_by_id[row["semlex_sample_id"]].append(row)
    sha_groups: dict[str, list[str]] = defaultdict(list)
    for row in inventory:
        sha_groups[row["raw_sha256"]].append(row["semlex_sample_id"])
    duplicates: list[dict[str, Any]] = list(metadata_duplicate_audits)
    duplicate_noncanonical: set[str] = set()
    for value, ids in sha_groups.items():
        unique = sorted(set(ids))
        if len(unique) > 1:
            canonical = unique[0]
            duplicate_noncanonical.update(unique[1:])
            duplicates.append({"duplicate_type": "RAW_SHA256", "value": value, "sample_ids": "|".join(unique),
                               "action": f"KEEP {canonical}; EXCLUDE OTHERS"})
    atomic_csv(OUT / "semlex_duplicate_audit.csv", duplicates, ["duplicate_type", "value", "sample_ids", "action"])
    apphear_train = read_csv(APPHEAR_TRAIN)
    apphear_by_sha = {row["raw_video_sha256"].lower(): row for row in apphear_train if row.get("raw_video_sha256")}
    audits: list[dict[str, Any]] = []
    overlaps: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    for row in canonical_candidates:
        matches = inv_by_id.get(row["semlex_sample_id"], [])
        reasons: list[str] = []
        if row["semlex_sample_id"] in mapping_conflicts: reasons.append("LABEL_MAPPING_CONFLICT")
        if len(matches) == 0: reasons.append("MISSING_RAW_ARCHIVE_MEMBER")
        if len(matches) > 1: reasons.append("DUPLICATE_ARCHIVE_SAMPLE_ID")
        if not row["semlex_signer_id"]: reasons.append("MISSING_SIGNER_ID")
        if not row["semlex_lexical_id"]: reasons.append("MISSING_LEXICAL_ID")
        if row["semlex_split"].lower() != "train": reasons.append("NON_TRAIN_SPLIT")
        if row["semlex_sample_id"] in duplicate_noncanonical: reasons.append("EXACT_RAW_DUPLICATE_NONCANONICAL")
        if matches:
            raw = matches[0]
            row["raw_video_path"] = raw["raw_video_path"]
            row["raw_sha256"] = raw["raw_sha256"]
            row["raw_bytes"] = raw["file_size"]
            if raw["raw_sha256"].lower() in apphear_by_sha:
                reasons.append("CONFIRMED_APPHEAR_TRAIN_RAW_SHA_OVERLAP")
                overlaps.append({"semlex_sample_id": row["semlex_sample_id"],
                                 "apphear_sample_id": apphear_by_sha[raw["raw_sha256"].lower()]["sample_id"],
                                 "evidence": "RAW_SHA256_EQUAL", "status": "EXCLUDE"})
        row["mapping_status"] = "EXCLUDED" if reasons else "RAW_LINEAGE_VERIFIED"
        row["eligible_for_extraction"] = not reasons
        row["exclusion_reason"] = "|".join(reasons)
        audits.append({"semlex_sample_id": row["semlex_sample_id"], "apphear_class_id": row["apphear_class_id"],
                       "apphear_gloss": row["apphear_gloss"], "status": row["mapping_status"],
                       "reason": row["exclusion_reason"], "canonical_sample_id": ""})
        if not reasons: accepted.append(row)
    atomic_csv(OUT / "semlex_raw_join_audit.csv", audits)
    atomic_csv(OUT / "semlex_apphear_lineage_overlap_audit.csv", overlaps,
               ["semlex_sample_id", "apphear_sample_id", "evidence", "status"])
    atomic_csv(OUT / "semlex_accepted_raw_manifest.csv", accepted)
    atomic_json(OUT / "p5d7a_archive_index_summary.json", {
        "archive_members_in_inventory": len(inventory), "metadata_candidate_ceiling": len(candidates),
        "unique_metadata_sample_ids": len(canonical_candidates),
        "duplicate_metadata_rows_excluded": len(candidates) - len(canonical_candidates),
        "accepted_raw_rows_mapped": len(accepted), "excluded_unique_samples": len(canonical_candidates) - len(accepted),
        "exact_duplicate_groups": len(duplicates), "apphear_train_overlaps": len(overlaps),
        "archive_path": str(ARCHIVE), "archive_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": "NOT_COMPUTED_TO_AVOID_SECOND_23GB_PASS",
        "archive_member_sha256_complete": True, "full_extraction_executed": False,
    })
    print(json.dumps({"accepted_raw_rows_mapped": len(accepted), "excluded": len(candidates)-len(accepted)}, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "index-archive"])
    args = parser.parse_args()
    prepare() if args.command == "prepare" else index_archive()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
