"""Prepare the frozen, blinded P4-C2A DWPose-guided RGB crop audit."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4c2a_dwpose_rgb_crop_separability_01"
TRUTH = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4a2_fresh_evidence_repair_v2_01/frozen_truth/P4A2_FRESH_HUMAN_TRUTH_V1.csv"
TRUTH_META = TRUTH.with_suffix(".json")
INFERENCE = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4a2_high_recall_rescue_final_01/p4a2_frozen_inference_manifest.csv"
FEATURES = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4a2_high_recall_rescue_final_01/p4a2_derived_features.csv"
REVIEW_TOOL = ROOT / "eval/runtime_diagnostics/p4c2a_crop_review.py"
TEST_FILE = ROOT / "tests/test_p4c2a_crop_review.py"
EXPECTED_DATASET = "7819c59123b4dacdafac190c81754deb766d6ed6087a2b58535490d45a6a3edd"
EXPECTED_ANNOTATION = "1b9f34412ba885e397019742bf29027987ce58668d099fd3914e48ab3206774b"
EXPECTED_DWPOSE = "e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7"
RULE_ID = "P4C2A_CROP_RULE_V1_PADDING_1P5_MIN_10PCT_32PX"
SAMPLE_SEED = "P4C2A_AUDIT_SAMPLE_V1_20260824"
ORDER_SEED = "P4C2A_BLINDED_ORDER_V1_20260824"
ALL_CROPS = OUT / "immutable_audit_crops"
MANIFEST_OUT = OUT / "p4c2a_crop_generation_manifest.csv"
MISSES_OUT = OUT / "p4c2a_proposal_misses.csv"
SAMPLE_OUT = OUT / "p4c2a_audit_sample_manifest.csv"
QUEUE_OUT = OUT / "p4c2a_blinded_review_queue.csv"
REVIEWS_OUT = OUT / "p4c2a_human_crop_review.csv"
RULE_OUT = OUT / "p4c2a_crop_rule.json"
BLINDING_OUT = OUT / "p4c2a_blinding_manifest.json"
PROVENANCE_OUT = OUT / "p4c2a_provenance.json"
REPORT_OUT = OUT / "P4C2A_DWPOSE_RGB_CROP_SEPARABILITY_RESULT.md"
HASH_OUT = OUT / "p4c2a_artifact_hash_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else []
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def dataset_hash(rows: list[dict[str, str]]) -> str:
    label_fields = [
        "any_hand_visible", "visible_left", "visible_right", "zero_hand", "rest", "entering",
        "leaving", "blur", "occlusion", "edge_clipped", "partial_visibility", "crossing",
        "hand_hand_contact", "hand_body_contact", "left_visibility_quality",
        "right_visibility_quality", "reviewer_note",
    ]
    fields = ["annotation_row_id", "sequence_id", "frame_index", "image_sha256", *label_fields, "reviewer_status"]
    payload = [{field: row[field] for field in fields} for row in sorted(rows, key=lambda row: row["annotation_row_id"])]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def crop_id(row_id: str, side: str, source_hash: str) -> str:
    token = hashlib.sha256(f"{RULE_ID}|{row_id}|{side}|{source_hash}".encode()).hexdigest()[:24]
    return f"P4C2A_{token}"


def temporal_spread(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: (int(row["frame_index"]), row["crop_id"]))
    if not ordered:
        return []
    chosen: list[dict[str, Any]] = []
    remaining = ordered[:]
    first = remaining.pop(len(remaining) // 2)
    chosen.append(first)
    while remaining:
        candidate = max(
            remaining,
            key=lambda row: (
                min(abs(int(row["frame_index"]) - int(selected["frame_index"])) for selected in chosen),
                hashlib.sha256(f"{SAMPLE_SEED}|{row['crop_id']}".encode()).hexdigest(),
            ),
        )
        remaining.remove(candidate)
        chosen.append(candidate)
    return chosen


def sequence_aware_sample(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["sequence_id"]].append(row)
    sequence_ids = sorted(groups, key=lambda value: hashlib.sha256(f"{SAMPLE_SEED}|{value}".encode()).hexdigest())
    ordered_groups = {key: temporal_spread(groups[key]) for key in sequence_ids}
    selected: list[dict[str, Any]] = []
    round_index = 0
    while len(selected) < count:
        progressed = False
        for sequence in sequence_ids:
            group = ordered_groups[sequence]
            if round_index < len(group):
                selected.append(group[round_index])
                progressed = True
                if len(selected) == count:
                    break
        if not progressed:
            break
        round_index += 1
    if len(selected) != count:
        raise RuntimeError(f"P4C2A_INVALID: requested {count}, selected {len(selected)}")
    return selected


def main() -> None:
    if REVIEWS_OUT.exists():
        existing = read_csv(REVIEWS_OUT)
        if any(row.get("reviewer_status") == "COMPLETE" for row in existing):
            raise RuntimeError("P4C2A_INVALID: review already started; package is immutable")
    OUT.mkdir(parents=True, exist_ok=True)
    ALL_CROPS.mkdir(parents=True, exist_ok=True)
    truth_rows = read_csv(TRUTH)
    if sha256(TRUTH) != EXPECTED_ANNOTATION or dataset_hash(truth_rows) != EXPECTED_DATASET:
        raise RuntimeError("P4C2A_FROZEN_EVIDENCE_MISMATCH")
    metadata = json.loads(TRUTH_META.read_text(encoding="utf-8"))
    if metadata["dataset_sha256"] != EXPECTED_DATASET or metadata["annotation_sha256"] != EXPECTED_ANNOTATION:
        raise RuntimeError("P4C2A_FROZEN_EVIDENCE_MISMATCH")
    truth = {row["annotation_row_id"]: row for row in truth_rows}
    inference_rows = read_csv(INFERENCE)
    inference = {row["annotation_row_id"]: row for row in inference_rows}
    feature_rows = read_csv(FEATURES)
    if len(truth) != 458 or len(inference) != 458 or len(feature_rows) != 916:
        raise RuntimeError("P4C2A_FROZEN_EVIDENCE_MISMATCH")

    rule = {
        "rule_id": RULE_ID, "padding_factor": 1.5,
        "minimum_crop_side_px": "max(32, 0.10 * min(frame_width, frame_height))",
        "coordinate_source": "all finite native DWPose 21-point xy coordinates",
        "rectangle": "smallest axis-aligned point rectangle, expanded about its center",
        "clamping": "floor lower bounds, ceil upper bounds, clamp once to source RGB frame",
        "proposal_qualification": "frozen DWPose presence: >=11/21 native scores >=0.30",
        "human_truth_used_for_crop_position": False,
        "frozen_before_human_crop_review": True,
    }
    atomic_json(RULE_OUT, rule)
    feature_by_key = {(row["annotation_row_id"], row["anatomical_side"]): row for row in feature_rows}
    manifests: list[dict[str, Any]] = []
    misses: list[dict[str, Any]] = []
    for row_id, frame in inference.items():
        human = truth[row_id]
        image_path = Path(frame["image_path"])
        if not image_path.is_file() or sha256(image_path) != frame["image_sha256"] or frame["image_sha256"] != human["image_sha256"]:
            raise RuntimeError("P4C2A_FROZEN_EVIDENCE_MISMATCH")
        image = cv2.imread(str(image_path))
        if image is None:
            raise RuntimeError("P4C2A_FROZEN_EVIDENCE_MISMATCH")
        height, width = image.shape[:2]
        raw_path = ROOT / frame["raw_relative_path"]
        if not raw_path.is_file():
            raise RuntimeError(f"P4C2A_FROZEN_EVIDENCE_MISMATCH: missing native output {row_id}")
        native = np.load(raw_path, allow_pickle=False)
        if str(native["source_sha256"].item()) != frame["image_sha256"] or str(native["checkpoint_sha256"].item()) != EXPECTED_DWPOSE:
            raise RuntimeError("P4C2A_FROZEN_EVIDENCE_MISMATCH")
        for side_index, side in enumerate(("left", "right")):
            feature = feature_by_key[(row_id, side)]
            human_visible = human[f"visible_{side}"] == "YES"
            qualified = float(feature["hand_count_ge_030"]) >= 11
            if qualified != bool(native["gated_presence"][side_index]):
                raise RuntimeError("P4C2A_FROZEN_EVIDENCE_MISMATCH: proposal gate disagreement")
            if not qualified:
                if human_visible:
                    misses.append({
                        "annotation_row_id": row_id, "sequence_id": human["sequence_id"],
                        "signer_id": human["signer_id"], "frame_index": human["frame_index"],
                        "anatomical_side": side, "human_truth": "VISIBLE",
                        "reason": "FROZEN_DWPOSE_PRESENCE_GATE_FALSE", "image_sha256": human["image_sha256"],
                    })
                continue
            points = np.asarray(native[f"{side}_hand_keypoints"], dtype=np.float64)
            finite = points[np.isfinite(points).all(axis=1)]
            if len(finite) < 2:
                if human_visible:
                    misses.append({
                        "annotation_row_id": row_id, "sequence_id": human["sequence_id"],
                        "signer_id": human["signer_id"], "frame_index": human["frame_index"],
                        "anatomical_side": side, "human_truth": "VISIBLE",
                        "reason": "UNUSABLE_PROPOSAL_GEOMETRY", "image_sha256": human["image_sha256"],
                    })
                continue
            raw_x1, raw_y1 = finite.min(axis=0)
            raw_x2, raw_y2 = finite.max(axis=0)
            center_x, center_y = (raw_x1 + raw_x2) / 2.0, (raw_y1 + raw_y2) / 2.0
            minimum = max(32.0, 0.10 * min(width, height))
            crop_width = max((raw_x2 - raw_x1) * 1.5, minimum)
            crop_height = max((raw_y2 - raw_y1) * 1.5, minimum)
            x1 = max(0, min(width, math.floor(center_x - crop_width / 2.0)))
            y1 = max(0, min(height, math.floor(center_y - crop_height / 2.0)))
            x2 = max(0, min(width, math.ceil(center_x + crop_width / 2.0)))
            y2 = max(0, min(height, math.ceil(center_y + crop_height / 2.0)))
            if x2 - x1 < 2 or y2 - y1 < 2:
                if human_visible:
                    misses.append({
                        "annotation_row_id": row_id, "sequence_id": human["sequence_id"],
                        "signer_id": human["signer_id"], "frame_index": human["frame_index"],
                        "anatomical_side": side, "human_truth": "VISIBLE",
                        "reason": "CLAMPED_CROP_DEGENERATE", "image_sha256": human["image_sha256"],
                    })
                continue
            crop = image[y1:y2, x1:x2]
            identifier = crop_id(row_id, side, human["image_sha256"])
            crop_path = ALL_CROPS / f"{identifier}.png"
            ok, encoded = cv2.imencode(".png", crop)
            if not ok:
                raise RuntimeError("P4C2A_INVALID: crop encoding failed")
            atomic_bytes(crop_path, encoded.tobytes())
            category = "REAL_VISIBLE_HAND" if human_visible else "FALSE_DWPOSE_PROPOSAL"
            one_hand = (human["visible_left"] == "YES") ^ (human["visible_right"] == "YES")
            manifests.append({
                "crop_id": identifier, "truth_category": category,
                "annotation_row_id": row_id, "sequence_id": human["sequence_id"],
                "signer_id": human["signer_id"], "gloss": human["gloss"],
                "frame_index": human["frame_index"], "timestamp_ns": frame["timestamp_ns"],
                "anatomical_side": side, "source_image_path": str(image_path.resolve()),
                "source_image_sha256": human["image_sha256"], "native_output_path": str(raw_path.resolve()),
                "raw_x1": raw_x1, "raw_y1": raw_y1, "raw_x2": raw_x2, "raw_y2": raw_y2,
                "crop_x1": x1, "crop_y1": y1, "crop_x2": x2, "crop_y2": y2,
                "finite_keypoint_count": len(finite), "confident_joint_count": int(float(feature["hand_count_ge_030"])),
                "crop_rule_id": RULE_ID, "crop_path": str(crop_path.resolve()), "crop_sha256": sha256(crop_path),
                "zero_hand": human["zero_hand"], "rest": human["rest"], "entering": human["entering"],
                "leaving": human["leaving"], "one_hand_opposite_slot_absent": "YES" if one_hand and not human_visible else "NO",
                "two_hand_context": "YES" if human["visible_left"] == "YES" and human["visible_right"] == "YES" else "NO",
                "raw_origin": frame["raw_origin"], "new_dwpose_inference": "NO",
            })
    if len({row["crop_id"] for row in manifests}) != len(manifests):
        raise RuntimeError("P4C2A_INVALID: duplicate crop ID")
    atomic_csv(MANIFEST_OUT, manifests)
    atomic_csv(MISSES_OUT, misses)
    counts = Counter(row["truth_category"] for row in manifests)
    if counts["REAL_VISIBLE_HAND"] != 429 or counts["FALSE_DWPOSE_PROPOSAL"] != 159 or len(misses) != 19:
        raise RuntimeError(f"P4C2A_INVALID: unexpected governed counts {counts}, misses={len(misses)}")

    sample_size = min(100, counts["FALSE_DWPOSE_PROPOSAL"])
    positives = sequence_aware_sample([row for row in manifests if row["truth_category"] == "REAL_VISIBLE_HAND"], sample_size)
    negatives = sequence_aware_sample([row for row in manifests if row["truth_category"] == "FALSE_DWPOSE_PROPOSAL"], sample_size)
    sample = [{**row, "sample_category_target": row["truth_category"]} for row in positives + negatives]
    atomic_csv(SAMPLE_OUT, sample)
    shuffled = sample[:]
    random.Random(ORDER_SEED).shuffle(shuffled)
    queue = []
    reviews = []
    for order, row in enumerate(shuffled):
        queue.append({
            "crop_id": row["crop_id"], "queue_order": order,
            "crop_path": row["crop_path"], "crop_sha256": row["crop_sha256"],
            "full_frame_path": row["source_image_path"], "full_frame_sha256": row["source_image_sha256"],
        })
        reviews.append({
            "crop_id": row["crop_id"], "queue_order": order, "crop_sha256": row["crop_sha256"],
            "reviewer_label": "", "preliminary_label": "", "context_requested": "",
            "reviewer_status": "UNREVIEWED", "reviewed_utc": "", "revision_count": "0",
            "last_edit_utc": "", "last_edit_reason": "",
        })
    atomic_csv(QUEUE_OUT, queue)
    atomic_csv(REVIEWS_OUT, reviews)
    blinding = {
        "status": "FROZEN_BEFORE_REVIEW", "review_order_seed": ORDER_SEED,
        "sample_selection_seed": SAMPLE_SEED, "queue_rows": len(queue),
        "reviewer_visible_queue_columns": list(queue[0]),
        "hidden_from_reviewer": ["truth_category", "anatomical_side", "sequence_id", "signer_id", "gloss", "DWPose scores/keypoints", "E2/R1", "WiLoR", "human truth"],
        "context_policy": "full frame may be shown only after a preliminary crop-only label is selected",
        "model_output_used_for_sample_selection": False,
        "sampling_fields": ["truth category", "sequence ID", "signer ID", "frame index/timing"],
        "review_tool_sha256": sha256(REVIEW_TOOL), "review_queue_sha256": sha256(QUEUE_OUT),
    }
    atomic_json(BLINDING_OUT, blinding)
    provenance = {
        "status": "HUMAN_REVIEW_PENDING", "dataset_sha256": EXPECTED_DATASET,
        "annotation_sha256": EXPECTED_ANNOTATION, "dwpose_checkpoint_sha256": EXPECTED_DWPOSE,
        "native_frames_reused": 458, "new_dwpose_frames_inferred": 0,
        "crop_rule_sha256": sha256(RULE_OUT), "crop_manifest_sha256": sha256(MANIFEST_OUT),
        "sample_manifest_sha256": sha256(SAMPLE_OUT), "queue_sha256": sha256(QUEUE_OUT),
        "blinding_manifest_sha256": sha256(BLINDING_OUT), "review_tool_sha256": sha256(REVIEW_TOOL),
        "test_sha256": sha256(TEST_FILE), "generator_sha256": sha256(Path(__file__)),
    }
    atomic_json(PROVENANCE_OUT, provenance)
    report = f"""# P4-C2A DWPose RGB Crop Separability Result

## Status

**HUMAN_REVIEW_PENDING — no separability classification yet.**

Frozen evidence was verified. All 458 governed frames already had exact frozen native DWPose
outputs, so no DWPose inference was run. The crop rule was frozen before human crop review and
does not use human boxes, WiLoR, E2/R1, or model-failure mining.

## Governed proposal inventory

- True visible-hand proposals: **429**
- False DWPose proposals: **159**
- Visible hand observations without a qualified proposal: **19**
- Proposal-generation recall: **429/448 = 95.76%**
- Immutable generated crops: **588**

## Frozen blinded audit

- REAL_VISIBLE_HAND crops: **100**
- FALSE_DWPOSE_PROPOSAL crops: **100**
- Total blinded queue: **200**
- Sample seed: `{SAMPLE_SEED}`
- Review-order seed: `{ORDER_SEED}`
- Selection is sequence-aware and timing-based within truth category; no confidence or prior
  detector outcomes were used.

## Crop rule

Use all finite native 21-point coordinates, take their smallest axis-aligned rectangle, expand
it 1.5x about its center, enforce each dimension to at least `max(32 px, 10% of the shorter frame
side)`, then clamp once to the source RGB frame. This rule is immutable after review begins.

## Feasibility gates (not yet scored)

- Gate A: at least 95% of governed true proposal crops judged YES_CLEAR or YES_PARTIAL.
- Gate B: at least 80% of false proposal crops judged NO.
- Gate C: at most 10% UNCERTAIN overall.

No MobileNet, CNN, logistic regression, augmentation, HVD, threshold tuning, WiLoR fusion,
P4-C2B, P4-D, P4-B, Android, recognition, or DWPose modification occurred.
"""
    atomic_text(REPORT_OUT, report)
    artifact_paths = [RULE_OUT, MANIFEST_OUT, MISSES_OUT, SAMPLE_OUT, QUEUE_OUT, REVIEWS_OUT, BLINDING_OUT, PROVENANCE_OUT, REPORT_OUT]
    hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in artifact_paths}
    crop_hashes = [row["crop_sha256"] for row in sorted(manifests, key=lambda row: row["crop_id"])]
    hashes["immutable_audit_crops_count"] = str(len(crop_hashes))
    hashes["immutable_audit_crops_aggregate_sha256"] = hashlib.sha256("\n".join(crop_hashes).encode()).hexdigest()
    atomic_json(HASH_OUT, hashes)
    summary = {
        "status": "P4C2A_HUMAN_REVIEW_PENDING", "frozen_evidence_verified": True,
        "true_visible_hand_proposals": 429, "false_dwpose_proposals": 159,
        "proposal_misses": 19, "proposal_generation_recall": 429 / 448,
        "audit_crops": len(queue), "positive_audit_crops": 100, "negative_audit_crops": 100,
        "new_dwpose_inference": 0, "queue": str(QUEUE_OUT), "review_file": str(REVIEWS_OUT),
    }
    atomic_json(OUT / "p4c2a_pre_review_summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
