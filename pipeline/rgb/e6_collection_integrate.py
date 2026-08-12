"""Build the E6 product-core lineage package from reviewed and new raw data.

This utility is data-readiness only. It does not extract landmarks/features,
train a model, export TFLite, or modify Android/production assets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


MANIFEST_VERSION = "apphear_dataset_manifest_v1"
TARGET_SIGNS = ["GOOD", "HELLO", "SORRY", "HAVE", "KNOW", "THINK", "TAKE", "SELL"]
STRICT_REQUIREMENTS = {
    "total_clips": 150,
    "local_clips": 75,
    "local_signers": 5,
}
APPROVED_EXCEPTIONS = {
    "HAVE": {"local_signers": 4, "reason": "collection-limited provisional baseline"},
}
NEW_SIGNER_SPLITS = {
    "P_NEW01": "train",
    "P_NEW02": "test_fresh",
    "P_NEW03": "val",
    "P_NEW04": "test_fresh",
}
RECORDER_SIGNER_RE = re.compile(r"^([A-Za-z0-9]+-S[0-9]+)_")
MANIFEST_FIELDS = [
    "manifest_version",
    "row_id",
    "clip_id",
    "source",
    "source_manifest_path",
    "source_row_index",
    "raw_video_path",
    "raw_video_sha256",
    "raw_video_bytes",
    "raw_video_width",
    "raw_video_height",
    "raw_video_fps",
    "raw_video_frame_count",
    "decode_status",
    "canonical_gloss",
    "label_variant",
    "label_status",
    "sample_kind",
    "negative_subtype",
    "signer_id",
    "signer_source_id",
    "signer_group_id",
    "device_id",
    "environment_id",
    "camera_facing",
    "handedness",
    "split",
    "split_reason",
    "onset_frame",
    "release_frame",
    "quality_status",
    "quality_flags",
    "extraction_schema_version",
    "extractor_version",
    "mediapipe_mode",
    "normalizer_version",
    "feature_row_id",
    "feature_artifact_path",
    "feature_artifact_sha256",
    "reviewer_id",
    "reviewed_at",
    "previous_experiment_usage",
    "review_scope",
    "notes",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _probe(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "decode_status": "not_checked",
        "frame_count": "",
        "fps": "",
        "width": "",
        "height": "",
        "duration_sec": "",
    }
    if not path.exists():
        result["decode_status"] = "missing"
        return result
    if path.stat().st_size <= 0:
        result["decode_status"] = "zero_byte"
        return result
    if cv2 is None:
        return result
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        result["decode_status"] = "decode_failed"
        return result
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    sample_indices = sorted({0, max(0, frame_count // 2), max(0, frame_count - 1)})
    decoded = 0
    for index in sample_indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        decoded += int(ok and frame is not None)
    capture.release()
    result.update(
        {
            "decode_status": "ok" if decoded == len(sample_indices) else "decode_failed",
            "frame_count": frame_count,
            "fps": round(fps, 3),
            "width": width,
            "height": height,
            "duration_sec": round(frame_count / fps, 3) if fps else "",
        }
    )
    return result


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _final_review_decision(
    source_row: dict[str, str], review_row: dict[str, str] | None
) -> tuple[str, str, str, str]:
    if source_row.get("classification") == "Accepted":
        return "verified", "usable", "", "existing_conservative_acceptance"
    if review_row and review_row.get("review_decision") == "accept":
        return (
            "verified",
            "usable",
            "",
            "completed_product_core_manual_review",
        )
    if review_row and review_row.get("review_decision") == "diagnostic_only":
        return "verified", "exclude", "diagnostic_only", "completed_product_core_manual_review"
    reasons = source_row.get("classification_reasons", "")
    if review_row:
        reasons = review_row.get("review_reason", "") or reasons
    return "exclude", "exclude", reasons or "not_accepted", "completed_product_core_manual_review"


def _existing_split(row: dict[str, str], accepted: bool) -> tuple[str, str]:
    if not accepted:
        return "exclude", "not accepted by the E6 product-core review"
    source = row.get("source_dataset", "")
    source_split = row.get("source_split", "").lower()

    if source == "ASL_CITIZEN":
        if source_split == "train":
            return "train", "preserve official ASL Citizen signer split"
        if source_split == "val":
            return "val", "preserve official ASL Citizen signer split"
        if source_split == "test":
            return (
                "test_source_holdout",
                "preserve official test signer; not fresh after E3-E5 reuse",
            )
    if source == "LOCAL_SUPPLEMENTARY":
        return "train", "historical local sample reused in E4/E5; training-only to avoid test reuse"
    return "audit_only", "accepted lineage row lacks an approved split mapping"


def _convert_existing(
    source_rows: list[dict[str, str]], review_rows: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    converted = []
    for row in source_rows:
        gloss = row.get("canonical_gloss", "")
        if gloss not in TARGET_SIGNS:
            continue
        label_status, quality_status, flags, review_scope = _final_review_decision(
            row, review_rows.get(row.get("row_id", ""))
        )
        accepted = label_status == "verified" and quality_status == "usable"
        split, split_reason = _existing_split(row, accepted)
        source = "asl_citizen" if row.get("source_dataset") == "ASL_CITIZEN" else "local"
        signer = row.get("signer_id", "")
        converted.append(
            {
                "manifest_version": MANIFEST_VERSION,
                "row_id": row.get("row_id", ""),
                "clip_id": Path(row.get("raw_video_path", "unknown")).stem,
                "source": source,
                "source_manifest_path": row.get("source_manifest_path", ""),
                "source_row_index": row.get("source_row_index", ""),
                "raw_video_path": row.get("raw_video_path", ""),
                "raw_video_sha256": row.get("raw_video_sha256", ""),
                "raw_video_bytes": row.get("raw_video_bytes", ""),
                "raw_video_width": row.get("width", ""),
                "raw_video_height": row.get("height", ""),
                "raw_video_fps": row.get("fps", ""),
                "raw_video_frame_count": row.get("frame_count", ""),
                "decode_status": row.get("decode_status", ""),
                "canonical_gloss": gloss,
                "label_variant": row.get("label_variant", "none") or "none",
                "label_status": label_status,
                "sample_kind": "positive",
                "negative_subtype": "",
                "signer_id": signer,
                "signer_source_id": signer,
                "signer_group_id": (
                    f"local_recorder:{signer}" if source == "local" else f"{source}:{signer}"
                ),
                "device_id": "unknown",
                "environment_id": row.get("background", "unknown") or "unknown",
                "camera_facing": row.get("camera_direction", "unknown") or "unknown",
                "handedness": row.get("dominant_hand", "unknown") or "unknown",
                "split": split,
                "split_reason": split_reason,
                "quality_status": quality_status,
                "quality_flags": flags,
                "reviewer_id": "product_core_reviewer"
                if review_scope.startswith("completed")
                else "audit_rule",
                "reviewed_at": (review_rows.get(row.get("row_id", "")) or {}).get(
                    "reviewed_at", ""
                ),
                "previous_experiment_usage": " | ".join(
                    value
                    for value in (
                        row.get("previous_experiment_usage_exact", ""),
                        row.get("previous_experiment_usage_inferred", ""),
                    )
                    if value
                ),
                "review_scope": review_scope,
                "notes": row.get("notes", ""),
            }
        )
    return converted


def _technical_flags(row: dict[str, str]) -> list[str]:
    flags = []
    if row.get("decode_status") != "ok":
        flags.append(f"decode_{row.get('decode_status', 'unknown')}")
    try:
        duration = float(row.get("duration_sec", "") or 0)
        fps = float(row.get("fps", "") or 0)
        width = int(float(row.get("width", "") or 0))
        height = int(float(row.get("height", "") or 0))
    except ValueError:
        flags.append("invalid_video_metadata")
        return flags
    if duration < 0.5:
        flags.append("too_short_under_0_5s")
    if duration > 8.0:
        flags.append("unusually_long_over_8s")
    if fps < 15.0:
        flags.append("low_native_fps_under_15")
    if min(width, height) < 240:
        flags.append("low_resolution_under_240")
    if row.get("duplicate_group"):
        flags.append("exact_duplicate")
    return flags


def _recorder_signer_id(path: Path, folder_participant: str) -> tuple[str, str]:
    match = RECORDER_SIGNER_RE.match(path.name)
    if match:
        return match.group(1), "recorder_filename"
    return folder_participant, "collection_folder"


def _convert_collection(inventory_path: Path) -> list[dict[str, Any]]:
    rows = _read_csv(inventory_path)
    converted = []
    for index, row in enumerate(rows, start=1):
        if row.get("kind") != "positive" or row.get("label_or_subtype") not in TARGET_SIGNS:
            continue
        path = Path(row["raw_video_path"])
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        flags = _technical_flags(row)
        participant = row.get("participant_id", "")
        signer_id, signer_id_source = _recorder_signer_id(path, participant)
        proposed_split = NEW_SIGNER_SPLITS.get(participant, "audit_only")
        converted.append(
            {
                "manifest_version": MANIFEST_VERSION,
                "row_id": f"pc_capture_{index:05d}",
                "clip_id": path.stem,
                "source": "apphear_capture",
                "source_manifest_path": str(inventory_path.resolve()),
                "source_row_index": index,
                "raw_video_path": str(path),
                "raw_video_sha256": row.get("sha256", ""),
                "raw_video_bytes": row.get("bytes", ""),
                "raw_video_width": row.get("width", ""),
                "raw_video_height": row.get("height", ""),
                "raw_video_fps": row.get("fps", ""),
                "raw_video_frame_count": row.get("frame_count", ""),
                "decode_status": row.get("decode_status", ""),
                "canonical_gloss": row.get("label_or_subtype", ""),
                "label_variant": row.get("label_or_subtype", ""),
                "label_status": "needs_adjudication",
                "sample_kind": "positive",
                "negative_subtype": "",
                "signer_id": signer_id,
                "signer_source_id": signer_id,
                "signer_group_id": f"local_recorder:{signer_id}",
                "device_id": row.get("device_id", "unknown") or "unknown",
                "environment_id": row.get("environment_id", "unknown") or "unknown",
                "camera_facing": row.get("camera_facing", "unknown") or "unknown",
                "handedness": "unknown",
                "split": "audit_only",
                "split_reason": f"pending group spot review; proposed split={proposed_split}",
                "quality_status": "needs_review" if not flags else "needs_review",
                "quality_flags": "|".join(flags),
                "reviewer_id": "unreviewed",
                "reviewed_at": "",
                "previous_experiment_usage": "none_new_capture",
                "review_scope": "deterministic_group_spot_review_required",
                "notes": (
                    f"folder_participant={participant};signer_id_source={signer_id_source}. "
                    "Folder label/signer metadata is capture evidence, not independent "
                    "ASL label adjudication."
                ),
            }
        )
    return converted


def _apply_spot_review(
    collection_rows: list[dict[str, Any]], review_path: Path | None
) -> dict[str, Any]:
    if review_path is None or not review_path.is_file():
        return {"available": False, "groups_passed": 0, "groups_blocked": 0}
    review_rows = _read_csv(review_path)
    by_group: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in review_rows:
        group = (row.get("canonical_gloss", ""), row.get("signer_id", ""))
        by_group[group].append(row)
    passed: set[tuple[str, str]] = set()
    blocked: set[tuple[str, str]] = set()
    for group, rows in by_group.items():
        complete = all(row.get("review_status") for row in rows)
        accepted = complete and all(row.get("review_decision") == "accept" for row in rows)
        (passed if accepted else blocked).add(group)
    reviewed_at = max((row.get("reviewed_at", "") for row in review_rows), default="")
    for row in collection_rows:
        if row.get("quality_status") == "exclude":
            continue
        group = (str(row.get("canonical_gloss", "")), str(row.get("signer_id", "")))
        if group in passed:
            row["label_status"] = "verified"
            row["quality_status"] = "usable"
            row["split"] = _proposed_split(row)
            row["split_reason"] = "sign-signer batch passed deterministic 3-clip spot review"
            row["reviewer_id"] = "product_core_spot_reviewer"
            row["reviewed_at"] = reviewed_at
            row["review_scope"] = "batch_approved_from_first_middle_last_spot_review"
        elif group in blocked:
            flags = [flag for flag in str(row.get("quality_flags", "")).split("|") if flag]
            flags.append("spot_review_group_blocked")
            row["quality_flags"] = "|".join(sorted(set(flags)))
    return {
        "available": True,
        "rows": len(review_rows),
        "groups_passed": len(passed),
        "groups_blocked": len(blocked),
    }


def _n0_raw_index(raw_root: Path) -> dict[str, Path]:
    return {
        path.stem.lower(): path.resolve()
        for path in raw_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".m4v", ".avi", ".mkv"}
    }


def _convert_n0(
    reviewed_path: Path, raw_root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reviewed = _read_csv(reviewed_path)
    by_clip: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in reviewed:
        by_clip[row.get("clip_id", "")].append(row)
    raw_index = _n0_raw_index(raw_root)
    converted = []
    evidence = []
    for index, (clip_id, rows) in enumerate(sorted(by_clip.items()), start=1):
        path = raw_index.get(clip_id.lower())
        if path is None:
            probe = {
                "decode_status": "missing",
                "frame_count": "",
                "fps": "",
                "width": "",
                "height": "",
                "duration_sec": "",
            }
            sha = ""
            size = ""
        else:
            probe = _probe(path)
            sha = _sha256(path)
            size = path.stat().st_size
        eligible_rows = [row for row in rows if _bool(row.get("eligible", ""))]
        excluded_rows = [row for row in rows if not _bool(row.get("eligible", ""))]
        clean_clip = bool(path) and probe["decode_status"] == "ok" and not excluded_rows
        participant = rows[0].get("participant_id", "")
        timestamps = [int(row["timestamp_ms"]) for row in eligible_rows if row.get("timestamp_ms")]
        flags = [] if clean_clip else ["reviewed_visible_hand_contamination"]
        if path is None or probe["decode_status"] != "ok":
            flags.append("raw_video_unavailable_or_invalid")
        converted.append(
            {
                "manifest_version": MANIFEST_VERSION,
                "row_id": f"n0_capture_{index:03d}",
                "clip_id": clip_id,
                "source": "nosign_capture",
                "source_manifest_path": str(reviewed_path.resolve()),
                "source_row_index": "",
                "raw_video_path": str(path) if path else "",
                "raw_video_sha256": sha,
                "raw_video_bytes": size,
                "raw_video_width": probe["width"],
                "raw_video_height": probe["height"],
                "raw_video_fps": probe["fps"],
                "raw_video_frame_count": probe["frame_count"],
                "decode_status": probe["decode_status"],
                "canonical_gloss": "",
                "label_variant": "none",
                "label_status": "verified",
                "sample_kind": "no_sign",
                "negative_subtype": "N0_NO_HAND",
                "signer_id": f"N0_{participant}",
                "signer_source_id": participant,
                "signer_group_id": f"nosign_capture:{participant}",
                "device_id": rows[0].get("device_id", "unknown") or "unknown",
                "environment_id": rows[0].get("environment_id", "unknown") or "unknown",
                "camera_facing": rows[0].get("camera_facing", "unknown") or "unknown",
                "handedness": "unknown",
                "split": "train" if clean_clip else "exclude",
                "split_reason": (
                    "historical reviewed fixture reused for development/training only; "
                    "never fresh test"
                )
                if clean_clip
                else "contains reviewed contamination or invalid raw video",
                "quality_status": "usable" if clean_clip else "exclude",
                "quality_flags": "|".join(flags),
                "reviewer_id": "e2e_c0_gold_review",
                "reviewed_at": "2026-07-27",
                "previous_experiment_usage": (
                    "E2e-C0,E4-X,E4-Y,E4-AA and related no-sign diagnostics"
                ),
                "review_scope": "reviewed_1fps_frame_evidence",
                "notes": (
                    f"reviewed_frames={len(rows)};"
                    f"eligible_frames={len(eligible_rows)};"
                    f"eligible_timestamps_ms={'|'.join(map(str, timestamps))}"
                ),
            }
        )
        evidence.append(
            {
                "clip_id": clip_id,
                "raw_video_path": str(path) if path else "",
                "participant_id": participant,
                "reviewed_frames": len(rows),
                "eligible_no_hand_frames": len(eligible_rows),
                "excluded_frames": len(excluded_rows),
                "eligible_timestamps_ms": "|".join(map(str, timestamps)),
                "training_development_eligible": str(clean_clip),
                "reason": "" if clean_clip else "reviewed contamination or invalid raw video",
            }
        )
    return converted, evidence


def _spot_review_queue(collection_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in collection_rows:
        if row.get("quality_status") == "exclude":
            continue
        grouped[(str(row["canonical_gloss"]), str(row["signer_id"]))].append(row)
    selected: dict[str, dict[str, Any]] = {}
    for (gloss, signer), rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda item: str(item["raw_video_path"]))
        positions = sorted({0, len(ordered) // 2, len(ordered) - 1})
        for position in positions:
            row = ordered[position]
            selected[str(row["row_id"])] = {
                "row_id": row["row_id"],
                "canonical_gloss": gloss,
                "signer_id": signer,
                "raw_video_path": row["raw_video_path"],
                "selection_reason": "first_middle_last_group_spot_check",
                "review_status": "",
                "review_decision": "",
                "use_for": "",
                "label_correct": "",
                "variant_compatible": "",
                "hand_visible": "",
                "sign_complete": "",
                "quality_ok": "",
                "review_reason": "",
                "review_notes": "",
                "reviewed_at": "",
            }
        for row in ordered:
            if row.get("quality_flags"):
                selected[str(row["row_id"])] = {
                    "row_id": row["row_id"],
                    "canonical_gloss": gloss,
                    "signer_id": signer,
                    "raw_video_path": row["raw_video_path"],
                    "selection_reason": f"technical_flag:{row['quality_flags']}",
                    "review_status": "",
                    "review_decision": "",
                    "use_for": "",
                    "label_correct": "",
                    "variant_compatible": "",
                    "hand_visible": "",
                    "sign_complete": "",
                    "quality_ok": "",
                    "review_reason": "",
                    "review_notes": "",
                    "reviewed_at": "",
                }
    return sorted(
        selected.values(),
        key=lambda row: (row["canonical_gloss"], row["signer_id"], row["raw_video_path"]),
    )


def _provisional_positive_report(manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for gloss in TARGET_SIGNS:
        candidates = [
            row
            for row in manifest
            if row.get("canonical_gloss") == gloss
            and row.get("sample_kind") == "positive"
            and row.get("quality_status") != "exclude"
            and row.get("decode_status") == "ok"
        ]
        local = [row for row in candidates if row.get("source") in {"local", "apphear_capture"}]
        total_signers = {
            row.get("signer_group_id") for row in candidates if row.get("signer_group_id")
        }
        local_signers = {row.get("signer_group_id") for row in local if row.get("signer_group_id")}
        strict = (
            len(candidates) >= STRICT_REQUIREMENTS["total_clips"]
            and len(local) >= STRICT_REQUIREMENTS["local_clips"]
            and len(local_signers) >= STRICT_REQUIREMENTS["local_signers"]
        )
        exception = APPROVED_EXCEPTIONS.get(gloss, {})
        provisional_total_target = int(
            exception.get("total_clips", STRICT_REQUIREMENTS["total_clips"])
        )
        provisional_signer_target = int(
            exception.get("local_signers", STRICT_REQUIREMENTS["local_signers"])
        )
        provisional = (
            len(candidates) >= provisional_total_target
            and len(local) >= STRICT_REQUIREMENTS["local_clips"]
            and len(local_signers) >= provisional_signer_target
        )
        split_counts = Counter(_proposed_split(row) for row in candidates)
        rows.append(
            {
                "canonical_gloss": gloss,
                "candidate_total_clips": len(candidates),
                "candidate_local_clips": len(local),
                "candidate_total_signers": len(total_signers),
                "candidate_local_signers": len(local_signers),
                "strict_gate_passed": str(strict),
                "provisional_exception_gate_passed": str(provisional),
                "approved_exception": exception.get("reason", ""),
                "proposed_train_clips": split_counts.get("train", 0),
                "proposed_val_clips": split_counts.get("val", 0),
                "proposed_test_fresh_clips": split_counts.get("test_fresh", 0),
                "proposed_test_source_holdout_clips": split_counts.get("test_source_holdout", 0),
            }
        )
    return rows


def _proposed_split(row: dict[str, Any]) -> str:
    if row.get("source") != "apphear_capture":
        return str(row.get("split", ""))
    notes = str(row.get("notes", ""))
    marker = "folder_participant="
    folder_participant = ""
    if marker in notes:
        folder_participant = notes.split(marker, 1)[1].split(";", 1)[0]
    return NEW_SIGNER_SPLITS.get(folder_participant, "audit_only")


def _split_audit(manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_signer: dict[str, set[str]] = defaultdict(set)
    for row in manifest:
        if row.get("quality_status") == "exclude":
            continue
        split = _proposed_split(row)
        if split not in {"train", "val", "test_fresh", "test_source_holdout"}:
            continue
        by_signer[str(row.get("signer_group_id", ""))].add(split)
    return [
        {
            "signer_group_id": signer,
            "splits": "|".join(sorted(splits)),
            "leakage": str(len(splits) > 1),
            "reason": "signer assigned to multiple proposed splits" if len(splits) > 1 else "",
        }
        for signer, splits in sorted(by_signer.items())
    ]


def _resolve_duplicate_rows(manifest: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in manifest:
        sha = str(row.get("raw_video_sha256", ""))
        if sha:
            by_hash[sha].append(row)
    duplicate_groups: dict[str, list[str]] = {}
    source_priority = {"local": 0, "asl_citizen": 1, "nosign_capture": 2, "apphear_capture": 3}
    for sha, rows in by_hash.items():
        if len(rows) <= 1:
            continue
        ordered = sorted(
            rows,
            key=lambda row: (
                source_priority.get(str(row.get("source")), 9),
                str(row.get("row_id")),
            ),
        )
        keeper = ordered[0]
        duplicate_groups[sha] = [str(row.get("row_id")) for row in ordered]
        keeper_flags = [flag for flag in str(keeper.get("quality_flags", "")).split("|") if flag]
        keeper_flags.append("canonical_duplicate_keeper")
        keeper["quality_flags"] = "|".join(sorted(set(keeper_flags)))
        for duplicate in ordered[1:]:
            duplicate["quality_status"] = "exclude"
            duplicate["split"] = "exclude"
            duplicate["split_reason"] = f"exact duplicate of canonical row {keeper.get('row_id')}"
            duplicate["label_status"] = "exclude"
            flags = [flag for flag in str(duplicate.get("quality_flags", "")).split("|") if flag]
            flags.append("duplicate_across_canonical_manifest")
            duplicate["quality_flags"] = "|".join(sorted(set(flags)))
            duplicate["notes"] = (
                f"{duplicate.get('notes', '')} canonical_duplicate_row={keeper.get('row_id')}"
            ).strip()
    return duplicate_groups


def build(args: argparse.Namespace) -> None:
    output = args.output.resolve()
    source_rows = _read_csv(args.source_manifest)
    review_rows = {row.get("row_id", ""): row for row in _read_csv(args.review_manifest)}
    existing = _convert_existing(source_rows, review_rows)
    collection = _convert_collection(args.collection_inventory)
    spot_review = _apply_spot_review(collection, args.spot_review_manifest)
    n0, n0_evidence = _convert_n0(args.n0_reviewed_manifest, args.n0_raw_root)
    manifest = existing + collection + n0
    row_ids = [str(row.get("row_id")) for row in manifest]
    duplicate_row_ids = sorted(row_id for row_id, count in Counter(row_ids).items() if count > 1)
    duplicate_hashes = _resolve_duplicate_rows(manifest)
    lineage_rows = []
    for row in manifest:
        path = Path(str(row.get("raw_video_path", "")))
        exists = path.is_file()
        sha = str(row.get("raw_video_sha256", ""))

        errors = []
        if not exists:
            errors.append("raw_video_missing")
        if not sha:
            errors.append("sha256_missing")
        if row.get("decode_status") != "ok":
            errors.append(f"decode_status={row.get('decode_status')}")
        if row.get("sample_kind") == "positive" and not row.get("canonical_gloss"):
            errors.append("positive_gloss_missing")
        if not row.get("signer_id"):
            errors.append("signer_id_missing")
        lineage_rows.append(
            {
                "row_id": row.get("row_id"),
                "raw_video_path": row.get("raw_video_path"),
                "exists": str(exists),
                "sha256_present": str(bool(sha)),
                "decode_status": row.get("decode_status"),
                "lineage_passed": str(not errors),
                "errors": "|".join(errors),
            }
        )

    positive_report = _provisional_positive_report(manifest)
    split_rows = _split_audit(manifest)
    review_queue = _spot_review_queue(collection)
    clean_n0 = [row for row in n0 if row.get("quality_status") == "usable"]
    eligible_n0_frames = sum(int(row["eligible_no_hand_frames"]) for row in n0_evidence)
    unresolved_positive = sum(
        1
        for row in collection
        if row.get("quality_status") != "exclude"
        and (row.get("label_status") != "verified" or row.get("quality_status") != "usable")
    )
    strict_positive_pass = all(row["strict_gate_passed"] == "True" for row in positive_report)
    provisional_positive_pass = all(
        row["provisional_exception_gate_passed"] == "True" for row in positive_report
    )
    split_leakage = [row for row in split_rows if row["leakage"] == "True"]
    gates = {
        "manifest_version": MANIFEST_VERSION,
        "scope": "data readiness only; no extraction or modeling authorization",
        "counts": {
            "manifest_rows": len(manifest),
            "existing_rows": len(existing),
            "new_positive_rows": len(collection),
            "n0_raw_clip_rows": len(n0),
            "n0_clean_development_clips": len(clean_n0),
            "n0_eligible_reviewed_frames": eligible_n0_frames,
            "spot_review_rows": len(review_queue),
            "spot_review_result": spot_review,
        },
        "gates": {
            "lineage_complete": {
                "passed": all(row["lineage_passed"] == "True" for row in lineage_rows),
                "failed_rows": sum(row["lineage_passed"] != "True" for row in lineage_rows),
            },
            "unique_selected_rows_and_raw_videos": {
                "passed": not duplicate_row_ids
                and all(
                    sum(
                        1
                        for row in manifest
                        if row.get("raw_video_sha256") == sha
                        and row.get("quality_status") != "exclude"
                    )
                    == 1
                    for sha in duplicate_hashes
                ),
                "duplicate_row_ids": duplicate_row_ids,
                "duplicate_hash_groups": len(duplicate_hashes),
                "resolution": "one canonical keeper; copied rows excluded",
            },
            "positive_strict_counts_and_signers": {"passed": strict_positive_pass},
            "positive_provisional_exceptions": {
                "passed": provisional_positive_pass,
                "exceptions": APPROVED_EXCEPTIONS,
            },
            "new_positive_label_quality_review": {
                "passed": unresolved_positive == 0,
                "unresolved_rows": unresolved_positive,
                "spot_review_rows": len(review_queue),
                "spot_review_result": spot_review,
            },
            "proposed_split_signer_disjoint": {
                "passed": not split_leakage,
                "leakage_groups": len(split_leakage),
            },
            "n0_source_evidence": {
                "passed": len(clean_n0) > 0 and eligible_n0_frames >= 150,
                "note": (
                    "reviewed frame evidence only; future windows must be materialized "
                    "from raw video"
                ),
            },
            "full_nosign_oov_transition_coverage": {
                "passed": False,
                "remaining_windows": 850,
                "missing_subtypes": [
                    "P1_IDLE_HANDS",
                    "P1_FACE_ADJACENT",
                    "P1_ACCIDENTAL_MOTION",
                    "OOV_SIGN",
                    "TRANSITION_PARTIAL",
                ],
            },
        },
    }
    gates["overall_data_readiness_passed"] = all(gate["passed"] for gate in gates["gates"].values())
    gates["decision"] = (
        "data_ready_for_clean_v3_baseline"
        if gates["overall_data_readiness_passed"]
        else (
            "blocked_missing_positive_and_negative_context"
            if unresolved_positive == 0
            else "blocked_pending_spot_review_and_missing_negative_context"
        )
    )
    label_audit = [
        {
            "row_id": row.get("row_id"),
            "canonical_gloss": row.get("canonical_gloss"),
            "source": row.get("source"),
            "label_status": row.get("label_status"),
            "quality_status": row.get("quality_status"),
            "quality_flags": row.get("quality_flags"),
            "review_scope": row.get("review_scope"),
        }
        for row in manifest
    ]
    summary = {
        "manifest_version": MANIFEST_VERSION,
        "rows": len(manifest),
        "by_source": dict(Counter(str(row.get("source")) for row in manifest)),
        "by_sample_kind": dict(Counter(str(row.get("sample_kind")) for row in manifest)),
        "by_label_status": dict(Counter(str(row.get("label_status")) for row in manifest)),
        "by_quality_status": dict(Counter(str(row.get("quality_status")) for row in manifest)),
        "by_split": dict(Counter(str(row.get("split")) for row in manifest)),
    }
    schema = {
        "manifest_version": MANIFEST_VERSION,
        "fields": [
            {"name": field, "required": field in MANIFEST_FIELDS[:39]} for field in MANIFEST_FIELDS
        ],
        "note": (
            "Extraction fields remain blank until a separately authorized schema-v3.0 "
            "extraction run."
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "manifest.csv", manifest, MANIFEST_FIELDS)
    _write_json(output / "manifest.schema.json", schema)
    _write_json(output / "manifest_summary.json", summary)
    _write_csv(output / "lineage_audit.csv", lineage_rows, list(lineage_rows[0].keys()))
    _write_csv(output / "split_audit.csv", split_rows, list(split_rows[0].keys()))
    _write_csv(output / "label_audit.csv", label_audit, list(label_audit[0].keys()))
    _write_csv(
        output / "positive_readiness_by_sign.csv", positive_report, list(positive_report[0].keys())
    )
    _write_csv(output / "n0_reviewed_frame_evidence.csv", n0_evidence, list(n0_evidence[0].keys()))
    review_fields = list(review_queue[0].keys()) if review_queue else ["row_id"]
    _write_csv(output / "manual_review_queue.csv", review_queue, review_fields)
    _write_json(output / "readiness_gate.json", gates)
    print(json.dumps(gates, indent=2))


def check(args: argparse.Namespace) -> None:
    required = [
        "manifest.csv",
        "manifest.schema.json",
        "manifest_summary.json",
        "lineage_audit.csv",
        "split_audit.csv",
        "label_audit.csv",
        "positive_readiness_by_sign.csv",
        "n0_reviewed_frame_evidence.csv",
        "manual_review_queue.csv",
        "readiness_gate.json",
    ]
    errors = [name for name in required if not (args.run_dir / name).is_file()]
    if not errors:
        payload = json.loads((args.run_dir / "readiness_gate.json").read_text(encoding="utf-8"))
        if payload.get("manifest_version") != MANIFEST_VERSION:
            errors.append("unexpected manifest version")
        if not payload.get("gates", {}).get("lineage_complete", {}).get("passed"):
            errors.append("lineage gate failed")
        if not payload.get("gates", {}).get("proposed_split_signer_disjoint", {}).get("passed"):
            errors.append("proposed split leakage")
    result = {"run_dir": str(args.run_dir.resolve()), "passed": not errors, "errors": errors}
    print(json.dumps(result, indent=2))
    if errors:
        raise RuntimeError("; ".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="E6 canonical collection/N0 lineage integration")
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument(
        "--source-manifest",
        type=Path,
        default=Path(
            "artifacts/recognition_upgrade/product_core_data_readiness/e6_product_core_review_01/source_manifest_snapshot.csv"
        ),
    )
    build_parser.add_argument(
        "--review-manifest",
        type=Path,
        default=Path(
            "artifacts/recognition_upgrade/product_core_data_readiness/e6_product_core_review_01/review_manifest.csv"
        ),
    )
    build_parser.add_argument(
        "--collection-inventory",
        type=Path,
        default=Path(
            "artifacts/recognition_upgrade/product_core_data_readiness/e6_collection_validation_check_20260805_v2/raw_collection_inventory.csv"
        ),
    )
    build_parser.add_argument(
        "--spot-review-manifest",
        type=Path,
        default=Path(
            "artifacts/recognition_upgrade/product_core_data_readiness/"
            "e6_collection_spot_review_01/review_manifest.csv"
        ),
    )
    build_parser.add_argument(
        "--n0-reviewed-manifest",
        type=Path,
        default=Path("artifacts/recognition_upgrade/e2e_c0/n0_capture_06/reviewed_manifest.csv"),
    )
    build_parser.add_argument(
        "--n0-raw-root",
        type=Path,
        default=Path("scratchpad/e2e_c0_capture/raw/n0"),
    )
    build_parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/recognition_upgrade/product_core_data_readiness/e6_collection_integration_01"
        ),
    )
    build_parser.set_defaults(func=build)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.set_defaults(func=check)
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"[e6-collection-integrate] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
