"""Prepare and adjudicate the blinded P4-A2 fresh human evidence package.

This module performs evidence governance only. It never loads E2, DWPose,
MediaPipe, recognition output, or any other model-derived signal.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "model/config/recognition_upgrade/p4a2_fresh_evidence_review.json"
OUT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4a2_fresh_evidence_repair_01"
P3 = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p3_dwpose_temporal_usability_01"
A1 = ROOT / "artifacts/recognition_upgrade/a1_independent_clock/signing_sentinel_01"
P4A = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4a_dwpose_presence_eligibility_01"

SOURCE_FIELDS = [
    "annotation_row_id", "source_family", "sequence_id", "attempt_id", "signer_id",
    "gloss", "expected_hand_category", "source_video_image_path", "total_available_frames",
    "selected_frame_indices", "frame_index", "timestamp_ns", "image_sha256",
    "reason_for_inclusion", "intended_future_role", "sampling_phase", "review_batch",
]
LABEL_FIELDS = [
    "annotation_row_id", "any_hand_visible", "visible_left", "visible_right", "zero_hand",
    "rest", "entering", "leaving", "left_visibility_quality", "right_visibility_quality",
    "blur", "occlusion", "edge_clipped", "partial_visibility", "crossing",
    "hand_hand_contact", "hand_body_contact", "reviewer_status", "reviewer_note",
    "reviewed_utc",
]
ANNOTATION_FIELDS = [
    "annotation_row_id", "sequence_id", "frame_index", "timestamp_ns", "signer_id", "gloss",
    "image_sha256", *LABEL_FIELDS[1:],
]
TRUTH = {"YES", "NO", "UNCERTAIN"}
QUALITY = {"CLEAR", "WEAK", "NOT_APPLICABLE", "UNCERTAIN"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def wsl_to_windows(value: str) -> Path:
    if value.startswith("/mnt/") and len(value) > 6:
        drive = value[5].upper()
        return Path(f"{drive}:/{value[7:]}")
    return Path(value)


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def complete_sequence_metadata(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["sequence_id"])].append(row)
    for sequence_rows in grouped.values():
        indices = ";".join(str(row["frame_index"]) for row in sorted(sequence_rows, key=lambda value: int(value["frame_index"])))
        for row in sequence_rows:
            if not row.get("total_available_frames"):
                row["total_available_frames"] = len(sequence_rows)
            if not row.get("selected_frame_indices"):
                row["selected_frame_indices"] = indices
    return rows


def annotation_spans() -> dict[str, tuple[int, int]]:
    paths = [
        ROOT / "artifacts/recognition_upgrade/ru_d1/ru_d1_pilot_01_annotations.csv",
        ROOT / "artifacts/recognition_upgrade/ru_d2/ru_d2_targeted_confirmation_01_annotations.csv",
        ROOT / "artifacts/recognition_upgrade/ru_d2/ru_d2_today_controlled_closeout_01_annotations.csv",
        ROOT / "artifacts/recognition_upgrade/ru_d2/ru_d2_today_controlled_closeout_02_annotations.csv",
        ROOT / "artifacts/recognition_upgrade/ru_d7/phone_bc_01/annotations.csv",
        A1 / "annotations.csv",
    ]
    spans: dict[str, tuple[int, int]] = {}
    for path in paths:
        if not path.exists():
            continue
        for row in read_csv(path):
            if row.get("attempt_id") and row.get("onset_frame") and row.get("release_frame"):
                spans[row["attempt_id"]] = (int(row["onset_frame"]), int(row["release_frame"]))
    return spans


def used_p4a_attempts() -> set[str]:
    return {
        row["sequence_id"].removeprefix("A2__")
        for row in read_csv(P4A / "p4a_split_manifest.csv")
    }


def untouched_phone_attempts() -> list[dict[str, Any]]:
    used = used_p4a_attempts()
    spans = annotation_spans()
    attempts = []
    for bundle in sorted((A1 / "phone_bundles").iterdir()):
        metadata_path = bundle / "metadata.json"
        if not bundle.is_dir() or not metadata_path.exists():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        attempt_id = metadata["attempt_id"]
        frames = sorted((bundle / "evidence").glob("frame_*.jpg"))
        if attempt_id in used or not frames or attempt_id not in spans:
            continue
        attempts.append({"bundle": bundle, "metadata": metadata, "frames": frames, "span": spans[attempt_id]})
    return attempts


def choose_distinct(attempts: list[dict[str, Any]], count: int, hand_targets: dict[str, int]) -> list[dict[str, Any]]:
    """Deterministic metadata-only round robin over hand category and gloss."""
    chosen: list[dict[str, Any]] = []
    for hand, target in hand_targets.items():
        pool = [a for a in attempts if a["metadata"].get("expected_hands") == hand]
        pool.sort(key=lambda a: (a["metadata"].get("ground_truth", ""), a["metadata"]["attempt_id"]))
        seen_gloss: set[str] = set()
        for item in pool:
            gloss = item["metadata"].get("ground_truth", "")
            if gloss in seen_gloss:
                continue
            chosen.append(item)
            seen_gloss.add(gloss)
            if sum(x["metadata"].get("expected_hands") == hand for x in chosen) >= target:
                break
        if sum(x["metadata"].get("expected_hands") == hand for x in chosen) < target:
            for item in pool:
                if item in chosen:
                    continue
                chosen.append(item)
                if sum(x["metadata"].get("expected_hands") == hand for x in chosen) >= target:
                    break
    if len(chosen) != count:
        raise RuntimeError(f"Metadata-only selection produced {len(chosen)} attempts; expected {count}")
    return sorted(chosen, key=lambda a: a["metadata"]["attempt_id"])


def choose_phone_attempts() -> list[dict[str, Any]]:
    attempts = untouched_phone_attempts()
    signer = [a for a in attempts if a["metadata"].get("signer_id") == "signer_01"]
    withheld = [a for a in attempts if a["metadata"].get("signer_id") == "withheld_phone_01"]
    signer_selected = choose_distinct(signer, 8, {"one": 5, "two": 3})
    withheld_selected = choose_distinct(withheld, 8, {"one": 3, "two": 5})
    if sum(a["metadata"].get("expected_hands") == "one" for a in withheld_selected) != 3:
        raise RuntimeError("All three untouched withheld one-hand attempts were not preserved")
    return signer_selected + withheld_selected


def frame_id(path: Path) -> int:
    return int(path.stem.split("_")[-1])


def evenly(pool: list[Path], count: int) -> list[Path]:
    if count <= 0 or not pool:
        return []
    if len(pool) <= count:
        return pool
    indices = {round(i * (len(pool) - 1) / (count - 1)) for i in range(count)} if count > 1 else {len(pool) // 2}
    return [pool[i] for i in sorted(indices)]


def phone_frame_plan(item: dict[str, Any]) -> tuple[list[tuple[Path, str]], list[tuple[Path, str]]]:
    frames = item["frames"]
    onset, release = item["span"]
    span = max(1, release - onset + 1)
    q1, q3 = onset + span // 4, release - span // 4
    phase_pools = {
        "BEFORE": [p for p in frames if frame_id(p) < onset],
        "ONSET": [p for p in frames if onset <= frame_id(p) < q1],
        "MIDDLE": [p for p in frames if q1 <= frame_id(p) <= q3],
        "RELEASE": [p for p in frames if q3 < frame_id(p) <= release],
        "AFTER": [p for p in frames if frame_id(p) > release],
    }
    quotas = {"BEFORE": 3, "ONSET": 4, "MIDDLE": 2, "RELEASE": 4, "AFTER": 3}
    selected: list[tuple[Path, str]] = []
    for phase, quota in quotas.items():
        selected.extend((path, phase) for path in evenly(phase_pools[phase], quota))
    selected_paths = {path for path, _ in selected}
    if len(selected) < 16:
        remaining = [p for p in frames if p not in selected_paths]
        for path in evenly(remaining, 16 - len(selected)):
            selected.append((path, "TIMING_FILL"))
    selected = sorted(selected[:16], key=lambda value: frame_id(value[0]))
    selected_paths = {path for path, _ in selected}
    reserve = []
    for path in frames:
        if path in selected_paths:
            continue
        fid = frame_id(path)
        phase = "BEFORE" if fid < onset else "AFTER" if fid > release else "ONSET_RELEASE"
        reserve.append((path, phase))
    reserve = [(p, phase) for p, phase in evenly_pairs(reserve, 8)]
    return selected, reserve


def evenly_pairs(pool: list[tuple[Path, str]], count: int) -> list[tuple[Path, str]]:
    if len(pool) <= count:
        return pool
    indices = {round(i * (len(pool) - 1) / (count - 1)) for i in range(count)}
    return [pool[i] for i in sorted(indices)]


def trace_timestamps(bundle: Path) -> dict[int, int]:
    values: dict[int, int] = {}
    with (bundle / "trace.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = json.loads(line)
            # Deliberately read only timing identity, never model/recognition fields.
            values[int(raw["frame_id"])] = int(raw["timestamp_ns"])
    return values


def future_roles_for_p3(sequence_ids: list[str]) -> dict[str, str]:
    roles = ["DEV_POOL", "VALIDATION_POOL", "FINAL_EVAL_POOL"]
    return {sequence_id: roles[index % 3] for index, sequence_id in enumerate(sorted(sequence_ids))}


def copy_blinded(source: Path, row_id: str) -> Path:
    target = OUT / "review_images" / f"{row_id}{source.suffix.lower()}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or sha256(target) != sha256(source):
        shutil.copy2(source, target)
    return target


def prepare() -> None:
    if (OUT / "p4a2_annotation_source_manifest.csv").exists():
        existing = complete_sequence_metadata(read_csv(OUT / "p4a2_annotation_source_manifest.csv"))
        write_csv(OUT / "p4a2_annotation_source_manifest.csv", existing, SOURCE_FIELDS)
        write_review_queue(existing)
        blinding_path = OUT / "p4a2_blinding_manifest.json"
        blinding = json.loads(blinding_path.read_text(encoding="utf-8"))
        blinding["reviewer_input_columns"] = [
            "annotation_row_id", "anonymous_sequence_id", "anonymous_sequence_position",
            "anonymous_sequence_total", "review_image_path", "review_mode",
        ]
        blinding["review_mode_explanation"] = (
            "TRANSITION_TOPUP exposes only the governed review objective, never source metadata, "
            "historical truth, or model output."
        )
        write_json(blinding_path, blinding)
        check_package(allow_incomplete=True)
        write_provenance("ANNOTATION_PENDING")
        print(f"Package already frozen: {OUT}")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    config = load_config()
    p3_frames = [r for r in read_csv(P3 / "frozen_frame_manifest.csv") if r["cohort"] == "GOLD_MULTI_SIGNER_INTERNAL_ONLY"]
    p3_sequences = {r["sequence_id"]: r for r in read_csv(P3 / "frozen_sequence_manifest.csv") if r["cohort"] == "GOLD_MULTI_SIGNER_INTERNAL_ONLY"}
    if len(p3_sequences) != 12 or len(p3_frames) != 202:
        raise RuntimeError(f"Expected 12 P3 gold sequences / 202 frames; found {len(p3_sequences)} / {len(p3_frames)}")
    p3_roles = future_roles_for_p3(list(p3_sequences))
    rows: list[dict[str, Any]] = []
    reserve_rows: list[dict[str, Any]] = []
    sequence_frame_ids: dict[str, list[str]] = defaultdict(list)
    counter = 0
    for item in p3_frames:
        counter += 1
        source = wsl_to_windows(item["image_path"])
        if not source.exists() or sha256(source) != item["image_sha256"]:
            raise RuntimeError(f"P3 source/hash failure: {source}")
        sequence = p3_sequences[item["sequence_id"]]
        row_id = f"P4A2R_{counter:04d}"
        sequence_frame_ids[item["sequence_id"]].append(item["source_frame_id"])
        rows.append({
            "annotation_row_id": row_id, "source_family": "P3_GOLD_TEMPORAL",
            "sequence_id": item["sequence_id"], "attempt_id": "",
            "signer_id": sequence["signer_id"], "gloss": sequence["gloss"],
            "expected_hand_category": sequence["expected_hands"], "source_video_image_path": str(source),
            "total_available_frames": "", "selected_frame_indices": "", "frame_index": item["source_frame_id"],
            "timestamp_ns": item["timestamp_ns"], "image_sha256": item["image_sha256"],
            "reason_for_inclusion": "all frozen consecutive P3 gold temporal-window frames",
            "intended_future_role": p3_roles[item["sequence_id"]], "sampling_phase": "P3_CONSECUTIVE",
            "review_batch": "INITIAL",
        })
    phone = choose_phone_attempts()
    for phone_index, item in enumerate(phone):
        metadata = item["metadata"]
        role = "FINAL_EVAL_POOL" if metadata["signer_id"] == "withheld_phone_01" else ("DEV_POOL" if phone_index % 2 == 0 else "VALIDATION_POOL")
        selected, reserve = phone_frame_plan(item)
        timestamps = trace_timestamps(item["bundle"])
        all_selected_ids = [str(frame_id(path)) for path, _ in selected]
        for batch, chosen, destination in (("INITIAL", selected, rows), ("RESERVE", reserve, reserve_rows)):
            for path, phase in chosen:
                counter += 1
                fid = frame_id(path)
                row_id = f"P4A2R_{counter:04d}"
                destination.append({
                    "annotation_row_id": row_id, "source_family": "UNTOUCHED_PHONE_ATTEMPT",
                    "sequence_id": metadata["attempt_id"], "attempt_id": metadata["attempt_id"],
                    "signer_id": metadata["signer_id"], "gloss": metadata["ground_truth"],
                    "expected_hand_category": metadata.get("expected_hands", "unknown"),
                    "source_video_image_path": str(path), "total_available_frames": len(item["frames"]),
                    "selected_frame_indices": ";".join(all_selected_ids), "frame_index": fid,
                    "timestamp_ns": timestamps.get(fid, ""), "image_sha256": sha256(path),
                    "reason_for_inclusion": "timing-only phase coverage from untouched RGB; no semantic/model selection",
                    "intended_future_role": role, "sampling_phase": phase, "review_batch": batch,
                })
    for row in rows:
        copy_blinded(Path(row["source_video_image_path"]), row["annotation_row_id"])
    rows = complete_sequence_metadata(rows)
    write_csv(OUT / "p4a2_annotation_source_manifest.csv", rows, SOURCE_FIELDS)
    write_csv(OUT / "p4a2_annotation_reserve_manifest.csv", reserve_rows, SOURCE_FIELDS)
    write_review_queue(rows)
    blinding = {
        "protocol_id": config["protocol_id"], "created_utc": datetime.now(timezone.utc).isoformat(),
        "reviewer_input_columns": ["annotation_row_id", "anonymous_sequence_id", "anonymous_sequence_position", "review_image_path"],
        "forbidden_inputs_absent": config["forbidden_selection_inputs"],
        "assertions": {
            "no_E2": True, "no_DWPose": True, "no_MediaPipe": True,
            "no_recognition_outputs": True, "no_model_failure_tags": True,
            "rgb_has_no_overlay": True, "anatomical_side_not_derived_from_x": True,
        },
    }
    write_json(OUT / "p4a2_blinding_manifest.json", blinding)
    write_protocol(rows, reserve_rows)
    write_provenance("ANNOTATION_PENDING")
    check_package(allow_incomplete=True)
    print(json.dumps({"selected_sequences": len({r['sequence_id'] for r in rows}), "initial_frames": len(rows), "reserve_frames": len(reserve_rows), "status": "ANNOTATION_PENDING"}, indent=2))


def write_review_queue(rows: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["sequence_id"]].append(row)
    sequence_order = sorted(grouped, key=lambda value: hashlib.sha256(f"20260824:{value}".encode()).hexdigest())
    anonymous = {sequence_id: f"SEQ_{index + 1:02d}" for index, sequence_id in enumerate(sequence_order)}
    queue = []
    for sequence_id in sequence_order:
        sequence_rows = sorted(grouped[sequence_id], key=lambda value: int(value["frame_index"]))
        for position, row in enumerate(sequence_rows, 1):
            queue.append({
                "annotation_row_id": row["annotation_row_id"],
                "anonymous_sequence_id": anonymous[sequence_id],
                "anonymous_sequence_position": position,
                "anonymous_sequence_total": len(sequence_rows),
                "review_image_path": str(OUT / "review_images" / f"{row['annotation_row_id']}{Path(row['source_video_image_path']).suffix.lower()}"),
                "review_mode": "TRANSITION_TOPUP" if row.get("review_batch") == "TARGETED_TOPUP" else "STANDARD",
            })
    write_csv(OUT / "p4a2_blinded_review_queue.csv", queue, ["annotation_row_id", "anonymous_sequence_id", "anonymous_sequence_position", "anonymous_sequence_total", "review_image_path", "review_mode"])


def write_protocol(rows: list[dict[str, Any]], reserve_rows: list[dict[str, Any]]) -> None:
    selected_sequences = {r["sequence_id"] for r in rows}
    report = f"""# P4-A2 Fresh Evidence Repair Result

Status: `ANNOTATION_PENDING`

Historical decisions remain unchanged: P4-A is `ELIGIBILITY_IMPROVED_BUT_GATES_FAILED`; P4-A2 is `P4A2_BLOCKED — INSUFFICIENT_FRESH_EVIDENCE`. This package repairs evidence only.

## Frozen initial package

- Sequences: {len(selected_sequences)} (12 P3 gold + 16 untouched phone attempts)
- Frames queued: {len(rows)}
- Timing-only phone reserve: {len(reserve_rows)}
- Reviewer sees RGB and anonymous sequence progress only.
- No E2, DWPose, MediaPipe, recognition output, skeleton, box, or model-derived tag is present in the review queue.
- LEFT/RIGHT always means the person's anatomical left/right, never screen position.

## Stopping rule

Review stops when certain human labels reach 120 visible-hand observations, 70 one-hand observations, 100 zero-hand frames, 80 rest frames, 25 entry/leaving frames, and 30 complete two-hand frames. Reserve frames may be added only by a remaining semantic deficit and non-model phase metadata.

No E2/R1/R2 evaluation is authorized by this package.
"""
    (OUT / "P4A2_FRESH_EVIDENCE_REPAIR_RESULT.md").write_text(report, encoding="utf-8")
    protocol = {
        "decision": "ANNOTATION_PENDING", "selection_policy": "deterministic non-model metadata and timing only",
        "p3_policy": "all existing consecutive frozen temporal-window frames",
        "phone_policy": "16 initial and at most 8 reserved frames per attempt across before/onset/middle/release/after timing phases",
        "semantic_minimums": load_config()["semantic_minimums"],
        "uncertain_count_policy": "UNCERTAIN never contributes to a semantic minimum",
        "final_eval_policy": "withheld_phone attempts frozen to FINAL_EVAL_POOL before review; sequence-level split only",
    }
    write_json(OUT / "p4a2_annotation_protocol.json", protocol)


def validate_label(row: dict[str, str]) -> list[str]:
    errors = []
    for field in ["any_hand_visible", "visible_left", "visible_right", "zero_hand", "rest", "entering", "leaving", "blur", "occlusion", "edge_clipped", "partial_visibility", "crossing", "hand_hand_contact", "hand_body_contact"]:
        if row.get(field) not in TRUTH:
            errors.append(f"{field} invalid")
    for field in ["left_visibility_quality", "right_visibility_quality"]:
        if row.get(field) not in QUALITY:
            errors.append(f"{field} invalid")
    if row.get("any_hand_visible") == "NO" and (row.get("visible_left") != "NO" or row.get("visible_right") != "NO"):
        errors.append("no hand conflicts with visible side")
    if row.get("any_hand_visible") == "YES" and "YES" not in (row.get("visible_left"), row.get("visible_right")):
        errors.append("visible hand requires at least one visible anatomical side")
    if row.get("zero_hand") == "YES" and row.get("any_hand_visible") != "NO":
        errors.append("zero_hand requires any_hand_visible=NO")
    return errors


def semantic_counts(labels: list[dict[str, str]]) -> dict[str, int]:
    certain = [r for r in labels if r.get("reviewer_status") == "COMPLETE" and not validate_label(r)]
    visible = sum(r[side] == "YES" for r in certain for side in ("visible_left", "visible_right"))
    one_frames = [r for r in certain if (r["visible_left"] == "YES") + (r["visible_right"] == "YES") == 1]
    return {
        "completed_frames": len(certain),
        "uncertain_frames": sum("UNCERTAIN" in (r["any_hand_visible"], r["visible_left"], r["visible_right"]) for r in certain),
        "visible_hand_observations": visible,
        "one_hand_visible_observations": len(one_frames),
        "clear_one_hand_observations": sum((r["left_visibility_quality"] if r["visible_left"] == "YES" else r["right_visibility_quality"]) == "CLEAR" for r in one_frames),
        "weak_one_hand_observations": sum((r["left_visibility_quality"] if r["visible_left"] == "YES" else r["right_visibility_quality"]) == "WEAK" for r in one_frames),
        "zero_hand_frames": sum(r["zero_hand"] == "YES" for r in certain),
        "rest_frames": sum(r["rest"] == "YES" for r in certain),
        "entry_or_leaving_frames": sum(r["entering"] == "YES" or r["leaving"] == "YES" for r in certain),
        "complete_two_hand_frames": sum(r["visible_left"] == "YES" and r["visible_right"] == "YES" for r in certain),
        "blur_frames": sum(r["blur"] == "YES" for r in certain),
        "occlusion_frames": sum(r["occlusion"] == "YES" for r in certain),
        "crossing_frames": sum(r["crossing"] == "YES" for r in certain),
        "hand_hand_contact_frames": sum(r["hand_hand_contact"] == "YES" for r in certain),
        "hand_body_contact_frames": sum(r["hand_body_contact"] == "YES" for r in certain),
    }


def merged_annotations() -> list[dict[str, str]]:
    source = {r["annotation_row_id"]: r for r in read_csv(OUT / "p4a2_annotation_source_manifest.csv")}
    labels_path = OUT / "p4a2_blinded_review_labels.csv"
    labels = read_csv(labels_path) if labels_path.exists() else []
    rows = []
    for label in labels:
        metadata = source[label["annotation_row_id"]]
        rows.append({**metadata, **label})
    return rows


def summarize() -> dict[str, Any]:
    rows = merged_annotations()
    write_csv(OUT / "p4a2_human_frame_annotations.csv", rows, ANNOTATION_FIELDS)
    counts = semantic_counts(rows)
    minimums = load_config()["semantic_minimums"]
    deficits = {key: max(0, required - counts.get(key, 0)) for key, required in minimums.items()}
    total_queue = len(read_csv(OUT / "p4a2_blinded_review_queue.csv"))
    result = {
        "rows": total_queue, "completed": counts["completed_frames"],
        "remaining": total_queue - counts["completed_frames"], "semantic_counts": counts,
        "semantic_minimums": minimums, "deficits": deficits,
        "all_semantic_minimums_passed": all(value == 0 for value in deficits.values()),
    }
    write_json(OUT / "p4a2_semantic_count_summary.json", result)
    print(json.dumps(result, indent=2))
    return result


def topup() -> None:
    summary = summarize()
    if summary["remaining"]:
        raise RuntimeError("Finish the current blinded queue before selecting a top-up")
    if summary["all_semantic_minimums_passed"]:
        print("All semantic minimums already pass; no top-up added.")
        return
    reserve = read_csv(OUT / "p4a2_annotation_reserve_manifest.csv")
    active = read_csv(OUT / "p4a2_annotation_source_manifest.csv")
    deficits = summary["deficits"]
    def priority(row: dict[str, str]) -> tuple[int, str]:
        phase = row["sampling_phase"]
        hand = row["expected_hand_category"]
        score = 0
        if deficits["zero_hand_frames"] or deficits["rest_frames"]:
            score -= 5 if phase in {"BEFORE", "AFTER"} else 0
        if deficits["entry_or_leaving_frames"]:
            score -= 5 if phase == "ONSET_RELEASE" else 0
        if deficits["one_hand_visible_observations"]:
            score -= 4 if hand == "one" else 0
        if deficits["complete_two_hand_frames"]:
            score -= 4 if hand == "two" and phase == "ONSET_RELEASE" else 0
        return score, row["annotation_row_id"]
    reserve.sort(key=priority)
    largest_deficit = max(deficits.values())
    add_count = min(len(reserve), max(8, min(48, math.ceil(largest_deficit * 1.5))))
    added, remaining_reserve = reserve[:add_count], reserve[add_count:]
    for row in added:
        row["review_batch"] = "TARGETED_TOPUP"
        copy_blinded(Path(row["source_video_image_path"]), row["annotation_row_id"])
    active.extend(added)
    write_csv(OUT / "p4a2_annotation_source_manifest.csv", active, SOURCE_FIELDS)
    write_csv(OUT / "p4a2_annotation_reserve_manifest.csv", remaining_reserve, SOURCE_FIELDS)
    write_review_queue(active)
    write_provenance("TARGETED_TOPUP_PENDING")
    print(json.dumps({"added": len(added), "remaining_reserve": len(remaining_reserve), "deficits": deficits}, indent=2))


def check_package(allow_incomplete: bool = False) -> None:
    source = read_csv(OUT / "p4a2_annotation_source_manifest.csv")
    queue = read_csv(OUT / "p4a2_blinded_review_queue.csv")
    if len(source) != len(queue) or {r["annotation_row_id"] for r in source} != {r["annotation_row_id"] for r in queue}:
        raise RuntimeError("Source manifest and blinded queue disagree")
    forbidden = {"signer_id", "gloss", "intended_future_role", "expected_hand_category", "sampling_phase", "source_video_image_path"}
    if forbidden.intersection(queue[0]):
        raise RuntimeError("Blinded queue exposes governed metadata")
    for row in source:
        source_path = Path(row["source_video_image_path"])
        if not source_path.exists() or sha256(source_path) != row["image_sha256"]:
            raise RuntimeError(f"Source/hash failure: {row['annotation_row_id']}")
    labels_path = OUT / "p4a2_blinded_review_labels.csv"
    if labels_path.exists():
        for row in read_csv(labels_path):
            errors = validate_label(row)
            if errors:
                raise RuntimeError(f"Invalid annotation {row['annotation_row_id']}: {errors}")
    if not allow_incomplete:
        result = summarize()
        if result["remaining"]:
            raise RuntimeError(f"Human review incomplete: {result['remaining']} rows remain")
        if not result["all_semantic_minimums_passed"]:
            raise RuntimeError(f"Semantic minimums not met: {result['deficits']}")
        freeze_splits()
    print("P4-A2 evidence package validation passed.")


def audit_resume_overwrite_defect() -> None:
    source_rows = read_csv(OUT / "p4a2_annotation_source_manifest.csv")
    labels = read_csv(OUT / "p4a2_blinded_review_labels.csv")
    source = {row["annotation_row_id"]: row for row in source_rows}
    topup = [row for row in labels if source[row["annotation_row_id"]]["review_batch"] == "TARGETED_TOPUP"]
    if not topup:
        raise RuntimeError("No top-up labels exist; resume-overwrite audit is not applicable")
    cutoff = min(row["reviewed_utc"] for row in topup)
    affected = []
    for row in labels:
        metadata = source[row["annotation_row_id"]]
        if metadata["review_batch"] != "INITIAL" or row["reviewed_utc"] < cutoff:
            continue
        affected.append({
            "annotation_row_id": row["annotation_row_id"],
            "sequence_id": metadata["sequence_id"],
            "frame_index": metadata["frame_index"],
            "image_sha256": metadata["image_sha256"],
            "current_reviewed_utc": row["reviewed_utc"],
            "current_entering": row["entering"],
            "current_leaving": row["leaving"],
            "current_visible_left": row["visible_left"],
            "current_visible_right": row["visible_right"],
            "original_item_label_recoverable": "NO",
        })
    fields = list(affected[0])
    write_csv(OUT / "p4a2_resume_overwrite_affected_rows.csv", affected, fields)
    result = {
        "status": "BENCHMARK_TOOLING_DEFECT",
        "decision": "P4A2_FRESH_EVIDENCE_NOT_FROZEN",
        "defect": "resume advanced by queue index rather than next-unlabeled row",
        "first_topup_reviewed_utc": cutoff,
        "initial_rows": 458,
        "topup_rows": len(topup),
        "initial_rows_unaffected_before_cutoff": 458 - len(affected),
        "initial_rows_potentially_overwritten": len(affected),
        "affected_sequences": len({row["sequence_id"] for row in affected}),
        "affected_current_transition_labels": sum(row["current_entering"] == "YES" or row["current_leaving"] == "YES" for row in affected),
        "original_item_labels_recoverable": False,
        "current_label_file_preserved_sha256": sha256(OUT / "p4a2_blinded_review_labels.csv"),
        "freeze_permitted": False,
        "model_work_occurred": False,
    }
    write_json(OUT / "p4a2_benchmark_tooling_defect.json", result)
    report = f"""# P4-A2 Fresh Evidence Repair Result

Status: `BENCHMARK_TOOLING_DEFECT — NOT FROZEN`

The initial 458-row review completed, and a 29-row transition top-up was appended. The review UI resumed at the first unlabeled row but then advanced by adjacent queue index. Because top-up rows were interspersed among completed rows, subsequent saves revisited and overwrote completed labels instead of jumping to the next unlabeled row.

- Initial rows potentially overwritten: {len(affected)}/458
- Initial rows remaining before the first top-up timestamp: {458 - len(affected)}
- Affected sequences: {len({row['sequence_id'] for row in affected})}/28
- Current transition labels among affected rows: {sum(row['current_entering'] == 'YES' or row['current_leaving'] == 'YES' for row in affected)}
- Original overwritten item labels recoverable: no
- Current label artifact preserved unchanged: `{result['current_label_file_preserved_sha256']}`

The apparent all-gates-passed semantic result is invalid and must not freeze `P4A2_FRESH_HUMAN_TRUTH_V1`. No E2, R1/R2, DWPose, MediaPipe, recognition, training, Android, S4-S7, S6, Sapiens, P4-B, or new recording work occurred.
"""
    (OUT / "P4A2_FRESH_EVIDENCE_REPAIR_RESULT.md").write_text(report, encoding="utf-8")
    write_provenance("BENCHMARK_TOOLING_DEFECT")
    print(json.dumps(result, indent=2))


def freeze_splits() -> None:
    rows = merged_annotations()
    source_rows = read_csv(OUT / "p4a2_annotation_source_manifest.csv")
    role_by_sequence = {r["sequence_id"]: r["intended_future_role"] for r in source_rows}
    if any(role_by_sequence.get(r["sequence_id"]) == "FINAL_EVAL_POOL" and r["signer_id"] == "signer_01" for r in source_rows):
        raise RuntimeError("Final phone evaluation is not signer-separated")
    names = {"DEV_POOL": "p4a2_dev_manifest.csv", "VALIDATION_POOL": "p4a2_validation_manifest.csv", "FINAL_EVAL_POOL": "p4a2_final_eval_manifest.csv"}
    for role, filename in names.items():
        subset = [r for r in rows if role_by_sequence[r["sequence_id"]] == role]
        target = OUT / ("sealed_final" if role == "FINAL_EVAL_POOL" else "splits") / filename
        write_csv(target, subset, ANNOTATION_FIELDS)
    dataset_hash = hashlib.sha256("".join(sorted(f"{r['annotation_row_id']}:{r['image_sha256']}:{','.join(r.get(k, '') for k in LABEL_FIELDS[1:])}" for r in rows)).encode()).hexdigest()
    write_json(OUT / "P4A2_FRESH_HUMAN_TRUTH_V1.json", {"status": "P4A2_FRESH_EVIDENCE_READY", "dataset_id": "P4A2_FRESH_HUMAN_TRUTH_V1", "dataset_sha256": dataset_hash, "rows": len(rows)})
    write_provenance("P4A2_FRESH_EVIDENCE_READY")


def write_provenance(status: str) -> None:
    files = [CONFIG, Path(__file__), OUT / "p4a2_annotation_source_manifest.csv", OUT / "p4a2_blinding_manifest.json", OUT / "p4a2_annotation_protocol.json"]
    manifest = {"status": status, "generated_utc": datetime.now(timezone.utc).isoformat(), "files": [{"path": str(path), "sha256": sha256(path)} for path in files if path.exists()]}
    write_json(OUT / "p4a2_provenance_hash_manifest.json", manifest)


class ReviewApp:
    def __init__(self) -> None:
        import tkinter as tk
        from tkinter import ttk
        from PIL import Image, ImageTk
        self.tk, self.ttk, self.Image, self.ImageTk = tk, ttk, Image, ImageTk
        self.root = tk.Tk()
        self.root.title("P4-A2 Blinded Human Hand Visibility Review")
        self.queue = read_csv(OUT / "p4a2_blinded_review_queue.csv")
        labels_path = OUT / "p4a2_blinded_review_labels.csv"
        self.labels_path = labels_path
        self.labels = {r["annotation_row_id"]: r for r in read_csv(labels_path)} if labels_path.exists() else {}
        self.index = next((i for i, r in enumerate(self.queue) if r["annotation_row_id"] not in self.labels), max(0, len(self.queue) - 1))
        self.vars: dict[str, Any] = {}
        self.photo = None
        self.context_photo = None
        self.build()
        self.load()

    def build(self) -> None:
        tk, ttk = self.tk, self.ttk
        self.root.geometry("1360x900")
        self.root.minsize(1050, 700)
        left = ttk.Frame(self.root, padding=12); left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(self.root, padding=12, width=560); right.pack(side="right", fill="both")
        right.pack_propagate(False)
        self.progress = ttk.Label(right, font=("Segoe UI", 12, "bold")); self.progress.pack(anchor="w", pady=(0, 8))
        ttk.Label(
            right,
            text="IMPORTANT: LEFT and RIGHT mean the PERSON'S own hands — not the side of the picture.",
            foreground="#a32618", wraplength=620, font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            left,
            text="Judge the CURRENT FRAME. Nearby RGB frames are context only.",
            wraplength=760,
        ).pack(anchor="center", pady=(0, 6))
        self.image_label = ttk.Label(left, anchor="center"); self.image_label.pack(fill="both", expand=True)
        nav = ttk.Frame(left); nav.pack(pady=(8, 0))
        ttk.Button(nav, text="◀ Previous RGB context", command=lambda: self.show_context(-1)).pack(side="left")
        ttk.Button(nav, text="CURRENT frame", command=self.load_image).pack(side="left", padx=8)
        ttk.Button(nav, text="Next RGB context ▶", command=lambda: self.show_context(1)).pack(side="left")

        truth_fields = [
            "any_hand_visible", "visible_left", "visible_right", "zero_hand", "rest", "entering",
            "leaving", "blur", "occlusion", "edge_clipped", "partial_visibility", "crossing",
            "hand_hand_contact", "hand_body_contact",
        ]
        for field in truth_fields:
            self.vars[field] = tk.StringVar(value="NO")
        self.vars["left_visibility_quality"] = tk.StringVar(value="CLEAR")
        self.vars["right_visibility_quality"] = tk.StringVar(value="CLEAR")

        state_box = ttk.LabelFrame(right, text="STEP 1 — What is the frame state?", padding=10)
        state_box.pack(fill="x", pady=(0, 8))
        ttk.Label(state_box, text="Press A, R, E, L, or U. This does not save yet.", foreground="#555").pack(anchor="w", pady=(0, 5))
        self.selected_state = tk.StringVar(value="ORDINARY")
        self.state_buttons: dict[str, Any] = {}
        state_grid = ttk.Frame(state_box); state_grid.pack(fill="x")
        states = [
            ("A", "ORDINARY", "Ordinary"), ("R", "REST", "Rest"),
            ("E", "ENTERING", "Entering"), ("L", "LEAVING", "Leaving"),
            ("U", "UNCERTAIN", "Unsure"),
        ]
        for index, (key, value, label) in enumerate(states):
            button = tk.Button(state_grid, text=f"{label}\n[{key}]", command=lambda v=value: self.set_state(v), padx=8, pady=8)
            button.grid(row=0, column=index, sticky="nsew", padx=3)
            state_grid.columnconfigure(index, weight=1)
            self.state_buttons[value] = button
        self.state_status = ttk.Label(state_box, text="Selected: ORDINARY", font=("Segoe UI", 10, "bold"), foreground="#215a8a")
        self.state_status.pack(anchor="w", pady=(7, 0))

        hand_box = ttk.LabelFrame(right, text="STEP 2 — Which hands are visible? (choosing saves + advances)", padding=10)
        hand_box.pack(fill="x", pady=8)
        ttk.Label(hand_box, text="Press 0, 1, 2, 3, or 4. LEFT/RIGHT are the person's own hands.", foreground="#555").pack(anchor="w", pady=(0, 5))
        hand_grid = ttk.Frame(hand_box); hand_grid.pack(fill="x")
        hands = [
            ("0", "NONE", "No hands"), ("1", "LEFT", "Person's LEFT"),
            ("2", "RIGHT", "Person's RIGHT"), ("3", "BOTH", "Both hands"),
            ("4", "UNCERTAIN", "Unsure"),
        ]
        for index, (key, value, label) in enumerate(hands):
            ttk.Button(hand_grid, text=f"{label}\n[{key}]", command=lambda v=value: self.commit_hands(v)).grid(row=0, column=index, sticky="nsew", padx=3, ipady=10)
            hand_grid.columnconfigure(index, weight=1)

        self.details_toggle = ttk.Button(right, text="Optional details: weak hand, blur, clipping, contact…", command=self.toggle_details)
        self.details_toggle.pack(fill="x", pady=(7, 3), ipady=4)
        self.details_panel = ttk.LabelFrame(right, text="OPTIONAL DETAILS — leave closed for ordinary frames", padding=9)
        ttk.Label(
            self.details_panel,
            text="Click only what applies. Gray = NO · Orange = YES · Yellow ? = UNCERTAIN.",
            foreground="#555", wraplength=520,
        ).pack(anchor="w", pady=(0, 5))
        quality_row = ttk.Frame(self.details_panel); quality_row.pack(fill="x", pady=(0, 5))
        self.quality_buttons: dict[str, Any] = {}
        for field, label in [("left_visibility_quality", "Person's LEFT quality"), ("right_visibility_quality", "Person's RIGHT quality")]:
            button = tk.Button(quality_row, command=lambda f=field: self.cycle_quality(f), relief="raised", padx=8, pady=5)
            button.pack(side="left", fill="x", expand=True, padx=3)
            self.quality_buttons[field] = (button, label)
        condition_grid = ttk.Frame(self.details_panel); condition_grid.pack(fill="x")
        self.condition_buttons: dict[str, Any] = {}
        conditions = [
            ("blur", "Blur"), ("occlusion", "Occlusion"), ("edge_clipped", "Edge clipped"),
            ("partial_visibility", "Partial hand"), ("crossing", "Hands crossing"),
            ("hand_hand_contact", "Hands touching"), ("hand_body_contact", "Hand touches body"),
        ]
        for index, (field, label) in enumerate(conditions):
            button = tk.Button(condition_grid, command=lambda f=field: self.cycle_condition(f), relief="raised", padx=6, pady=4)
            button.grid(row=index // 4, column=index % 4, sticky="nsew", padx=3, pady=3)
            condition_grid.columnconfigure(index % 4, weight=1)
            self.condition_buttons[field] = (button, label)

        utility = ttk.Frame(right); utility.pack(fill="x", pady=(8, 0))
        ttk.Button(utility, text="← Edit previous frame", command=self.previous).pack(side="left")
        ttk.Button(utility, text="Clear optional marks", command=self.reset_modifiers).pack(side="left", padx=6)
        self.note_toggle = ttk.Button(utility, text="Add note…", command=self.toggle_note)
        self.note_toggle.pack(side="right")
        self.note_frame = ttk.Frame(right)
        ttk.Label(self.note_frame, text="Optional reviewer note").pack(anchor="w")
        self.note = tk.Text(self.note_frame, height=3, width=45); self.note.pack(fill="x")

        ttk.Label(
            right,
            text="Examples: E then 2 = person's RIGHT entering · L then 3 = both leaving · R then 0 = no hands/rest · 3 alone = ordinary both hands",
            foreground="#555", wraplength=520,
        ).pack(anchor="w", pady=(10, 0))
        self.root.bind("<Key>", self.handle_keyboard)
        self.refresh_modifier_buttons()

    def set_state(self, state: str) -> None:
        self.selected_state.set(state)
        colors = {"ORDINARY": "#d9ead3", "REST": "#cfe2f3", "ENTERING": "#fce5cd", "LEAVING": "#ead1dc", "UNCERTAIN": "#fff2cc"}
        for value, button in self.state_buttons.items():
            selected = value == state
            button.configure(
                relief="sunken" if selected else "raised",
                background=colors[value] if selected else "#eeeeee",
                activebackground=colors[value],
            )
        self.state_status.configure(text=f"Selected: {state}")

    def commit_hands(self, hands: str) -> None:
        state = self.selected_state.get()
        if hands == "NONE" and state in {"ENTERING", "LEAVING"}:
            from tkinter import messagebox
            messagebox.showinfo("Choose a visible hand", "Entering/leaving requires a hand to be visibly present. Choose LEFT, RIGHT, BOTH, or UNSURE.")
            return
        self.apply_matrix_label(hands, state)

    def handle_keyboard(self, event: Any) -> None:
        if event.widget.winfo_class() in {"Text", "Entry", "TEntry"}:
            return
        key = (event.char or "").lower()
        state_keys = {"a": "ORDINARY", "r": "REST", "e": "ENTERING", "l": "LEAVING", "u": "UNCERTAIN"}
        hand_keys = {"0": "NONE", "1": "LEFT", "2": "RIGHT", "3": "BOTH", "4": "UNCERTAIN"}
        if key in state_keys:
            self.set_state(state_keys[key])
        elif key in hand_keys:
            self.commit_hands(hand_keys[key])

    def toggle_details(self) -> None:
        if self.details_panel.winfo_manager():
            self.details_panel.pack_forget()
            self.details_toggle.configure(text="Optional details: weak hand, blur, clipping, contact…")
        else:
            self.details_panel.pack(fill="x", pady=(3, 6), after=self.details_toggle)
            self.details_toggle.configure(text="Hide optional details")

    def reset_modifiers(self) -> None:
        for field in self.condition_buttons:
            self.vars[field].set("NO")
        self.vars["left_visibility_quality"].set("CLEAR")
        self.vars["right_visibility_quality"].set("CLEAR")
        self.refresh_modifier_buttons()

    def cycle_condition(self, field: str) -> None:
        states = {"NO": "YES", "YES": "UNCERTAIN", "UNCERTAIN": "NO"}
        self.vars[field].set(states[self.vars[field].get()])
        self.refresh_modifier_buttons()

    def cycle_quality(self, field: str) -> None:
        current = self.vars[field].get()
        states = {"CLEAR": "WEAK", "WEAK": "UNCERTAIN", "UNCERTAIN": "CLEAR", "NOT_APPLICABLE": "CLEAR"}
        self.vars[field].set(states[current])
        self.refresh_modifier_buttons()

    def refresh_modifier_buttons(self) -> None:
        colors = {"NO": "#e8e8e8", "YES": "#f6a54c", "UNCERTAIN": "#f3dc72"}
        prefixes = {"NO": "", "YES": "✓ ", "UNCERTAIN": "? "}
        for field, (button, label) in self.condition_buttons.items():
            value = self.vars[field].get()
            button.configure(text=prefixes[value] + label, background=colors[value], activebackground=colors[value])
        quality_colors = {"CLEAR": "#d9ead3", "WEAK": "#f6a54c", "UNCERTAIN": "#f3dc72", "NOT_APPLICABLE": "#e8e8e8"}
        for field, (button, label) in self.quality_buttons.items():
            value = self.vars[field].get()
            button.configure(text=f"{label}: {value}", background=quality_colors[value], activebackground=quality_colors[value])

    def toggle_note(self) -> None:
        if self.note_frame.winfo_manager():
            self.note_frame.pack_forget()
            self.note_toggle.configure(text="Add note…")
        else:
            self.note_frame.pack(fill="x", pady=(6, 0))
            self.note_toggle.configure(text="Hide note")

    def apply_matrix_label(self, hands: str, state: str) -> None:
        if hands == "UNCERTAIN":
            self.vars["any_hand_visible"].set("UNCERTAIN")
            self.vars["visible_left"].set("UNCERTAIN")
            self.vars["visible_right"].set("UNCERTAIN")
            self.vars["zero_hand"].set("UNCERTAIN")
            self.vars["left_visibility_quality"].set("UNCERTAIN")
            self.vars["right_visibility_quality"].set("UNCERTAIN")
        else:
            left = hands in {"LEFT", "BOTH"}
            right = hands in {"RIGHT", "BOTH"}
            any_visible = left or right
            self.vars["any_hand_visible"].set("YES" if any_visible else "NO")
            self.vars["visible_left"].set("YES" if left else "NO")
            self.vars["visible_right"].set("YES" if right else "NO")
            self.vars["zero_hand"].set("NO" if any_visible else "YES")
            if left and self.vars["left_visibility_quality"].get() == "NOT_APPLICABLE":
                self.vars["left_visibility_quality"].set("CLEAR")
            if right and self.vars["right_visibility_quality"].get() == "NOT_APPLICABLE":
                self.vars["right_visibility_quality"].set("CLEAR")
            if not left:
                self.vars["left_visibility_quality"].set("NOT_APPLICABLE")
            if not right:
                self.vars["right_visibility_quality"].set("NOT_APPLICABLE")
            if not any_visible:
                for field in self.condition_buttons:
                    self.vars[field].set("NO")
        if state == "UNCERTAIN":
            self.vars["rest"].set("UNCERTAIN")
            self.vars["entering"].set("UNCERTAIN")
            self.vars["leaving"].set("UNCERTAIN")
        else:
            self.vars["rest"].set("YES" if state == "REST" else "NO")
            self.vars["entering"].set("YES" if state == "ENTERING" else "NO")
            self.vars["leaving"].set("YES" if state == "LEAVING" else "NO")
        self.save_next()

    def current(self) -> dict[str, str]: return self.queue[self.index]

    def load(self) -> None:
        row = self.current(); saved = self.labels.get(row["annotation_row_id"], {})
        condition_fields = set(self.condition_buttons)
        for field, variable in self.vars.items():
            if field in saved:
                value = saved[field]
            elif field in condition_fields:
                value = "NO"
            elif "quality" in field:
                value = "CLEAR"
            elif field in {"rest", "entering", "leaving"}:
                value = "NO"
            else:
                value = "UNCERTAIN"
            variable.set(value)
        if saved:
            if saved.get("entering") == "YES":
                state = "ENTERING"
            elif saved.get("leaving") == "YES":
                state = "LEAVING"
            elif saved.get("rest") == "YES":
                state = "REST"
            elif "UNCERTAIN" in (saved.get("rest"), saved.get("entering"), saved.get("leaving")):
                state = "UNCERTAIN"
            else:
                state = "ORDINARY"
        else:
            state = "ORDINARY"
        self.set_state(state)
        self.note.delete("1.0", "end"); self.note.insert("1.0", saved.get("reviewer_note", ""))
        if saved.get("reviewer_note") and not self.note_frame.winfo_manager():
            self.note_frame.pack(fill="x", pady=(6, 0))
            self.note_toggle.configure(text="Hide note")
        elif not saved.get("reviewer_note") and self.note_frame.winfo_manager():
            self.note_frame.pack_forget()
            self.note_toggle.configure(text="Add note…")
        has_optional = any(self.vars[field].get() != "NO" for field in self.condition_buttons) or any(
            self.vars[field].get() in {"WEAK", "UNCERTAIN"} for field in self.quality_buttons
        )
        if has_optional and not self.details_panel.winfo_manager():
            self.details_panel.pack(fill="x", pady=(3, 6), after=self.details_toggle)
            self.details_toggle.configure(text="Hide optional details")
        elif not has_optional and self.details_panel.winfo_manager():
            self.details_panel.pack_forget()
            self.details_toggle.configure(text="Optional details: weak hand, blur, clipping, contact…")
        self.refresh_modifier_buttons()
        self.progress.configure(text=f"Frame {self.index + 1}/{len(self.queue)} | {row['anonymous_sequence_id']} {row['anonymous_sequence_position']}/{row['anonymous_sequence_total']} | completed {len(self.labels)}")
        self.load_image()

    def display(self, path: Path, prefix: str = "") -> None:
        image = self.Image.open(path).convert("RGB")
        scale = min(820 / image.width, 760 / image.height)
        if abs(scale - 1.0) > 0.02:
            image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), self.Image.Resampling.LANCZOS)
        self.photo = self.ImageTk.PhotoImage(image)
        self.image_label.configure(image=self.photo, text=prefix, compound="top")

    def load_image(self) -> None: self.display(Path(self.current()["review_image_path"]), "CURRENT FRAME")

    def show_context(self, delta: int) -> None:
        current = self.current(); target = self.index + delta
        if 0 <= target < len(self.queue) and self.queue[target]["anonymous_sequence_id"] == current["anonymous_sequence_id"]:
            self.display(Path(self.queue[target]["review_image_path"]), "PREVIOUS CONTEXT" if delta < 0 else "NEXT CONTEXT")

    def previous(self) -> None:
        if self.index > 0: self.index -= 1; self.load()

    def save_next(self) -> None:
        row = {"annotation_row_id": self.current()["annotation_row_id"], **{field: variable.get() for field, variable in self.vars.items()}, "reviewer_status": "COMPLETE", "reviewer_note": self.note.get("1.0", "end").strip(), "reviewed_utc": datetime.now(timezone.utc).isoformat()}
        errors = validate_label(row)
        if errors:
            from tkinter import messagebox
            messagebox.showerror("Check this frame", "\n".join(errors)); return
        prior = self.labels.get(row["annotation_row_id"])
        if prior is not None:
            journal = OUT / "p4a2_label_revision_journal.jsonl"
            with journal.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"revised_utc": row["reviewed_utc"], "annotation_row_id": row["annotation_row_id"], "prior": prior, "replacement": row}, sort_keys=True) + "\n")
        self.labels[row["annotation_row_id"]] = row
        ordered = [self.labels[q["annotation_row_id"]] for q in self.queue if q["annotation_row_id"] in self.labels]
        write_csv(self.labels_path, ordered, LABEL_FIELDS)
        next_index = next((index for index in range(self.index + 1, len(self.queue)) if self.queue[index]["annotation_row_id"] not in self.labels), None)
        if next_index is None:
            next_index = next((index for index, item in enumerate(self.queue) if item["annotation_row_id"] not in self.labels), None)
        if next_index is not None:
            self.index = next_index
            self.load()
        else:
            from tkinter import messagebox
            messagebox.showinfo("Complete", "All queued frames are saved. Run the Summarize command.")

    def run(self) -> None: self.root.mainloop()


def review() -> None:
    check_package(allow_incomplete=True)
    ReviewApp().run()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "review", "summarize", "topup", "check", "defect-audit"])
    args = parser.parse_args()
    if args.command == "prepare": prepare()
    elif args.command == "review": review()
    elif args.command == "summarize": summarize()
    elif args.command == "topup": topup()
    elif args.command == "defect-audit": audit_resume_overwrite_defect()
    else: check_package(allow_incomplete=False)


if __name__ == "__main__":
    main()
