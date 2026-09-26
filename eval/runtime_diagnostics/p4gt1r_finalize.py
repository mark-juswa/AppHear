"""Freeze P4 eligibility truth V2 and rescore only preserved model outputs."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from eval.runtime_diagnostics.p4c2r_truth_review import dataset_hash


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement"
OUT = BASE / "p4gt1r_schema_repair_v2_01"
V1 = BASE / "p4a2_fresh_evidence_repair_v2_01/frozen_truth/P4A2_FRESH_HUMAN_TRUTH_V1.csv"
GT1 = BASE / "p4gt1_eligibility_ground_truth_rebuild_01"
PASS1 = GT1 / "p4gt1_pass1_full.csv"
PASS2 = GT1 / "p4gt1_repeatability_review.csv"
DISAGREEMENTS = GT1 / "p4gt1_repeatability_disagreements.csv"
QUEUE = OUT / "p4gt1r_six_frame_queue.csv"
ADJUDICATION = OUT / "p4gt1r_adjudication_review.csv"
P4A2 = BASE / "p4a2_high_recall_rescue_final_01"
INFERENCE_MANIFEST = P4A2 / "p4a2_frozen_inference_manifest.csv"
P4C2A = BASE / "p4c2a_dwpose_rgb_crop_separability_01"
P4C1 = BASE / "p4c1_wilor_det_01"

EXPECTED_DATASET = "7819c59123b4dacdafac190c81754deb766d6ed6087a2b58535490d45a6a3edd"
EXPECTED_ANNOTATION = "1b9f34412ba885e397019742bf29027987ce58668d099fd3914e48ab3206774b"
EXPECTED_PASS1 = "74ec425293d734a79550ba012555301cdfcd9491cd39eca4400f3af9fb489428"
EXPECTED_PASS2 = "d619e0fa342cff00ca073dcea6a491065dff231ccad1c576f85a1e37a7cda8b6"
EXPECTED_DISAGREEMENTS = "88c4755ef40e08ea9ae175753970e1fb46622b6f4358cfd95dfe195da7bc83a5"
EXPECTED_CROP_REVIEW = "fe47dd7c710a91e2a2bb88df3d33269aa89edf8b0d657898394b86783c89522f"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    rows = list(rows)
    temporary = path.with_name(path.name + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def yes(value: str) -> bool:
    return str(value).strip().upper() in {"YES", "TRUE", "1"}


def count_owner(left: str, right: str) -> tuple[str, str]:
    if left == "NO" and right == "NO":
        return "ZERO", "NOT_APPLICABLE"
    if left == "YES" and right == "YES":
        return "TWO", "NOT_APPLICABLE"
    if left == "YES" and right == "NO":
        return "ONE", "LEFT"
    if left == "NO" and right == "YES":
        return "ONE", "RIGHT"
    return "UNCERTAIN", "UNCERTAIN"


def derived_slots(count: str, owner: str) -> tuple[str, str]:
    if count == "ZERO":
        return "NO", "NO"
    if count == "TWO":
        return "YES", "YES"
    if count == "ONE" and owner == "LEFT":
        return "YES", "NO"
    if count == "ONE" and owner == "RIGHT":
        return "NO", "YES"
    return "UNCERTAIN", "UNCERTAIN"


def rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def verify_sources() -> dict[str, str]:
    checks = {
        "v1_annotation": sha256(V1),
        "pass1": sha256(PASS1),
        "pass2": sha256(PASS2),
        "disagreements": sha256(DISAGREEMENTS),
        "crop_review": sha256(P4C2A / "p4c2a_human_crop_review.csv"),
    }
    expected = {
        "v1_annotation": EXPECTED_ANNOTATION,
        "pass1": EXPECTED_PASS1,
        "pass2": EXPECTED_PASS2,
        "disagreements": EXPECTED_DISAGREEMENTS,
        "crop_review": EXPECTED_CROP_REVIEW,
    }
    if checks != expected or dataset_hash(read_csv(V1)) != EXPECTED_DATASET:
        raise RuntimeError("P4GT1R_SOURCE_INTEGRITY_FAILURE")
    return checks


def freeze_v2() -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    pass1 = read_csv(PASS1)
    v1_by_id = {row["annotation_row_id"]: row for row in read_csv(V1)}
    pass2_by_id = {row["source_annotation_row_id"]: row for row in read_csv(PASS2)}
    queue = {row["frame_id"]: row for row in read_csv(QUEUE)}
    adjudication = {row["frame_id"]: row for row in read_csv(ADJUDICATION)}
    if len(pass1) != 458 or len(v1_by_id) != 458 or len(queue) != 6 or set(queue) != set(adjudication):
        raise RuntimeError("P4GT1R_EVIDENCE_INTEGRITY_FAILURE")
    for frame_id, reviewed in adjudication.items():
        queued = queue[frame_id]
        if reviewed["reviewer_status"] != "COMPLETE" or reviewed["revision_count"] != "0":
            raise RuntimeError("P4GT1R_ADJUDICATION_INCOMPLETE_OR_EDITED")
        if reviewed["source_sha256"] != queued["source_sha256"]:
            raise RuntimeError("ANNOTATION_ROW_IDENTITY_MISMATCH")
        if reviewed["visible_hand_count"] == "ONE" and reviewed["one_hand_ownership"] not in {"LEFT", "RIGHT", "UNCERTAIN"}:
            raise RuntimeError("P4GT1R_INVALID_ADJUDICATION")
        if reviewed["visible_hand_count"] != "ONE" and reviewed["one_hand_ownership"] != "NOT_APPLICABLE":
            raise RuntimeError("P4GT1R_INVALID_ADJUDICATION")

    v2: list[dict[str, str]] = []
    changes: list[dict[str, str]] = []
    uncertainty: list[dict[str, str]] = []
    for source in sorted(pass1, key=lambda item: item["frame_id"]):
        frame_id = source["frame_id"]
        p1_count, p1_owner = count_owner(source["visible_left"], source["visible_right"])
        if frame_id in adjudication:
            decision = adjudication[frame_id]
            final_count = decision["visible_hand_count"]
            final_owner = decision["one_hand_ownership"]
            provenance = "P4GT1R_SIX_FRAME_ADJUDICATION"
            adjudicated = "YES"
            adjudication_row_id = decision["adjudication_row_id"]
        else:
            final_count, final_owner = p1_count, p1_owner
            provenance = "P4GT1_PASS1_RETAINED"
            adjudicated = "NO"
            adjudication_row_id = ""
        left, right = derived_slots(final_count, final_owner)
        v2_row = {
            "frame_id": frame_id,
            "signer_id": source["signer_id"],
            "sequence_id": source["sequence_id"],
            "frame_index": source["frame_index"],
            "source_sha256": source["source_sha256"],
            "source_image_path": source["source_image_path"],
            "visible_hand_count": final_count,
            "one_hand_ownership": final_owner,
            "left_visibility": left,
            "right_visibility": right,
            "frame_state": source["frame_state"],
            "truth_provenance": provenance,
            "pass1_source": source["pass1_source"],
            "pass1_left": source["visible_left"],
            "pass1_right": source["visible_right"],
            "pass2_left": pass2_by_id.get(frame_id, {}).get("visible_left", ""),
            "pass2_right": pass2_by_id.get(frame_id, {}).get("visible_right", ""),
            "adjudicated": adjudicated,
            "adjudication_row_id": adjudication_row_id,
            "development_truth_status": "GOVERNED_DEVELOPMENT_GROUND_TRUTH",
        }
        v2.append(v2_row)
        old = v1_by_id[frame_id]
        for side, new_value in (("LEFT", left), ("RIGHT", right)):
            old_value = old[f"visible_{side.lower()}"]
            if old_value == new_value:
                continue
            if old_value == "NO" and new_value == "YES":
                kind = "NO_TO_YES"
            elif old_value == "YES" and new_value == "NO":
                kind = "YES_TO_NO"
            elif old_value == "UNCERTAIN" and new_value in {"YES", "NO"}:
                kind = "UNCERTAIN_TO_BINARY"
            elif old_value in {"YES", "NO"} and new_value == "UNCERTAIN":
                kind = "BINARY_TO_UNCERTAIN"
            else:
                kind = "OTHER"
            changes.append({
                "frame_id": frame_id,
                "anatomical_side": side,
                "v1_value": old_value,
                "v2_value": new_value,
                "change_type": kind,
                "source_sha256": source["source_sha256"],
                "reason": provenance,
                "pass1_result": source[f"visible_{side.lower()}"],
                "pass2_result": pass2_by_id.get(frame_id, {}).get(f"visible_{side.lower()}", ""),
                "adjudication_result": new_value if adjudicated == "YES" else "",
            })
        if final_count == "UNCERTAIN" or final_owner == "UNCERTAIN" or "UNCERTAIN" in {left, right}:
            uncertainty.append({
                "frame_id": frame_id,
                "source_sha256": source["source_sha256"],
                "visible_hand_count": final_count,
                "one_hand_ownership": final_owner,
                "left_visibility": left,
                "right_visibility": right,
                "reason": "PASS1_UNCERTAINTY_PRESERVED" if adjudicated == "NO" else "ADJUDICATED_UNCERTAINTY",
            })

    v2_fields = list(v2[0])
    atomic_csv(OUT / "P4_ELIGIBILITY_TRUTH_V2.csv", v2, v2_fields)
    atomic_csv(OUT / "p4gt1r_v1_v2_change_log.csv", changes, list(changes[0]) if changes else ["frame_id"])
    atomic_csv(OUT / "p4gt1r_uncertainty_inventory.csv", uncertainty, list(uncertainty[0]) if uncertainty else ["frame_id"])
    counts = Counter(row["visible_hand_count"] for row in v2)
    owners = Counter(row["one_hand_ownership"] for row in v2 if row["visible_hand_count"] == "ONE")
    composition = {
        "frames": len(v2),
        "count_zero": counts["ZERO"],
        "count_one": counts["ONE"],
        "count_two": counts["TWO"],
        "count_uncertain": counts["UNCERTAIN"],
        "count_known_frames": len(v2) - counts["UNCERTAIN"],
        "one_left": owners["LEFT"],
        "one_right": owners["RIGHT"],
        "one_ownership_uncertain": owners["UNCERTAIN"],
        "visible_hands": counts["ONE"] + 2 * counts["TWO"],
        "absent_hands": 2 * counts["ZERO"] + counts["ONE"],
        "uncertain_sides_excluded": sum(row[side] == "UNCERTAIN" for row in v2 for side in ("left_visibility", "right_visibility")),
        "signers": len({row["signer_id"] for row in v2}),
        "sequences": len({row["sequence_id"] for row in v2}),
    }
    return v2, changes, uncertainty, composition


def proposal_rows(v2: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    manifest = {row["annotation_row_id"]: row for row in read_csv(INFERENCE_MANIFEST)}
    if set(manifest) != {row["frame_id"] for row in v2}:
        raise RuntimeError("P4GT1R_NATIVE_OUTPUT_IDENTITY_MISMATCH")
    count_rows: list[dict[str, Any]] = []
    ownership_rows: list[dict[str, Any]] = []
    for truth in v2:
        item = manifest[truth["frame_id"]]
        raw_path = Path(item["raw_relative_path"])
        if not raw_path.is_absolute():
            raw_path = ROOT / raw_path
        if not raw_path.is_file():
            raise RuntimeError(f"P4GT1R_NATIVE_OUTPUT_MISSING: {raw_path}")
        with np.load(raw_path, allow_pickle=False) as native:
            presence = np.asarray(native["gated_presence"], dtype=bool).reshape(-1)
        if len(presence) != 2:
            raise RuntimeError("P4GT1R_NATIVE_OUTPUT_INVALID")
        left, right = bool(presence[0]), bool(presence[1])
        proposal_count = int(left) + int(right)
        count_value = {"ZERO": 0, "ONE": 1, "TWO": 2}.get(truth["visible_hand_count"])
        count_rows.append({
            "frame_id": truth["frame_id"], "sequence_id": truth["sequence_id"],
            "visible_hand_count": truth["visible_hand_count"], "truth_count": "" if count_value is None else count_value,
            "proposal_left": "YES" if left else "NO", "proposal_right": "YES" if right else "NO",
            "proposal_count": proposal_count, "credited_proposals": "" if count_value is None else min(count_value, proposal_count),
            "count_truth_included": "NO" if count_value is None else "YES", "native_output_path": str(raw_path),
        })
        if truth["visible_hand_count"] == "ONE" and truth["one_hand_ownership"] in {"LEFT", "RIGHT"}:
            true_active = left if truth["one_hand_ownership"] == "LEFT" else right
            opposite_active = right if truth["one_hand_ownership"] == "LEFT" else left
            category = "BOTH" if true_active and opposite_active else "CORRECT_ONLY" if true_active else "OPPOSITE_ONLY" if opposite_active else "NONE"
            ownership_rows.append({
                "frame_id": truth["frame_id"], "sequence_id": truth["sequence_id"], "one_hand_ownership": truth["one_hand_ownership"],
                "proposal_left": "YES" if left else "NO", "proposal_right": "YES" if right else "NO",
                "true_slot_active": "YES" if true_active else "NO", "opposite_slot_active": "YES" if opposite_active else "NO",
                "ownership_proposal_category": category,
            })
    known = [row for row in count_rows if row["count_truth_included"] == "YES"]
    visible = [row for row in known if int(row["truth_count"]) > 0]
    zeros = [row for row in known if int(row["truth_count"]) == 0]
    ones = [row for row in known if int(row["truth_count"]) == 1]
    twos = [row for row in known if int(row["truth_count"]) == 2]
    total_truth = sum(int(row["truth_count"]) for row in visible)
    credited = sum(int(row["credited_proposals"]) for row in visible)
    metrics = {
        "physical_proposal_capacity": {"numerator": credited, "denominator": total_truth, "rate": rate(credited, total_truth)},
        "one_hand_existence_recall": {"numerator": sum(int(row["proposal_count"]) >= 1 for row in ones), "denominator": len(ones)},
        "complete_two_hand_proposal_recall": {"numerator": sum(int(row["proposal_count"]) >= 2 for row in twos), "denominator": len(twos)},
        "zero_hand_activation": {"numerator": sum(int(row["proposal_count"]) >= 1 for row in zeros), "denominator": len(zeros)},
        "proposal_misses": total_truth - credited,
        "ownership": {
            "known_one_hand_frames": len(ownership_rows),
            "true_slot_retention": sum(row["true_slot_active"] == "YES" for row in ownership_rows),
            "opposite_slot_false_presence": sum(row["opposite_slot_active"] == "YES" for row in ownership_rows),
            "dual_slot_collisions": sum(row["ownership_proposal_category"] == "BOTH" for row in ownership_rows),
        },
    }
    for key in ("one_hand_existence_recall", "complete_two_hand_proposal_recall", "zero_hand_activation"):
        metrics[key]["rate"] = rate(metrics[key]["numerator"], metrics[key]["denominator"])
    own = metrics["ownership"]
    own["true_slot_retention_rate"] = rate(own["true_slot_retention"], own["known_one_hand_frames"])
    own["opposite_slot_false_presence_rate"] = rate(own["opposite_slot_false_presence"], own["known_one_hand_frames"])
    own["dual_slot_collision_rate"] = rate(own["dual_slot_collisions"], own["known_one_hand_frames"])
    return count_rows, ownership_rows, metrics


def crop_rescore(v2: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    truth = {row["frame_id"]: row for row in v2}
    crops = {row["crop_id"]: row for row in read_csv(P4C2A / "p4c2a_crop_generation_manifest.csv")}
    reviews = read_csv(P4C2A / "p4c2a_human_crop_review.csv")
    rows: list[dict[str, Any]] = []
    counts = Counter()
    for review in reviews:
        crop = crops[review["crop_id"]]
        v2row = truth[crop["annotation_row_id"]]
        label = review["reviewer_label"]
        authenticity = "RGB_HAND_PRESENT" if label in {"YES_CLEAR", "YES_PARTIAL"} else "RGB_HAND_ABSENT" if label == "NO" else "UNCERTAIN"
        counts[authenticity] += 1
        side_truth = v2row[f"{crop['anatomical_side'].lower()}_visibility"]
        interpretation = "CROP_AUTHENTICITY_ONLY"
        if crop["truth_category"] == "FALSE_DWPOSE_PROPOSAL" and authenticity == "RGB_HAND_PRESENT":
            if side_truth == "YES":
                interpretation = "VALID_VISIBLE_HAND_UNDER_V2"
            elif v2row["visible_hand_count"] == "ZERO":
                interpretation = "GENUINE_FALSE_VISUAL_POSITIVE"
            elif v2row["visible_hand_count"] == "ONE" and side_truth == "NO":
                interpretation = "OPPOSITE_HAND_OR_OWNERSHIP_CASE"
            else:
                interpretation = "UNCERTAIN_SEMANTIC_CASE"
            counts[interpretation] += 1
        rows.append({
            "crop_id": review["crop_id"], "frame_id": crop["annotation_row_id"], "anatomical_side": crop["anatomical_side"],
            "original_truth_category": crop["truth_category"], "reviewer_label": label, "rgb_authenticity": authenticity,
            "v2_visible_hand_count": v2row["visible_hand_count"], "v2_one_hand_ownership": v2row["one_hand_ownership"],
            "v2_crop_slot_visibility": side_truth, "diagnostic_interpretation": interpretation,
        })
    summary = {
        "reviewed_crops": len(rows),
        "rgb_hand_present": counts["RGB_HAND_PRESENT"],
        "rgb_hand_absent": counts["RGB_HAND_ABSENT"],
        "uncertain": counts["UNCERTAIN"],
        "binary_human_decidability": rate(counts["RGB_HAND_PRESENT"] + counts["RGB_HAND_ABSENT"], len(rows)),
        "previous_false_visual_positive_rescore": {
            "valid_visible_hand_under_v2": counts["VALID_VISIBLE_HAND_UNDER_V2"],
            "opposite_hand_or_ownership_case": counts["OPPOSITE_HAND_OR_OWNERSHIP_CASE"],
            "genuine_false_visual_positive": counts["GENUINE_FALSE_VISUAL_POSITIVE"],
            "uncertain_semantic_case": counts["UNCERTAIN_SEMANTIC_CASE"],
        },
        "interpretation": "Human crop judgments measure RGB authenticity, not anatomical ownership.",
    }
    return rows, summary


def evaluate_predictions(v2_by_id: dict[str, dict[str, str]], predictions: dict[str, tuple[bool, bool]], name: str) -> dict[str, Any]:
    rows = [v2_by_id[key] for key in predictions if key in v2_by_id]
    known = [row for row in rows if row["visible_hand_count"] != "UNCERTAIN"]
    visible = [row for row in known if row["visible_hand_count"] != "ZERO"]
    zero = [row for row in known if row["visible_hand_count"] == "ZERO"]
    one = [row for row in known if row["visible_hand_count"] == "ONE"]
    two = [row for row in known if row["visible_hand_count"] == "TWO"]
    rest_zero = [row for row in zero if row["frame_state"] == "REST"]
    truth_total = sum(1 if row["visible_hand_count"] == "ONE" else 2 for row in visible)
    credited = sum(min(1 if row["visible_hand_count"] == "ONE" else 2, sum(predictions[row["frame_id"]])) for row in visible)
    return {
        "method": name, "frames_rescored": len(rows), "count_known_frames": len(known),
        "physical_capacity_rate": rate(credited, truth_total),
        "one_hand_existence_recall": rate(sum(any(predictions[row["frame_id"]]) for row in one), len(one)),
        "zero_hand_activation_rate": rate(sum(any(predictions[row["frame_id"]]) for row in zero), len(zero)),
        "rest_zero_activation_rate": rate(sum(any(predictions[row["frame_id"]]) for row in rest_zero), len(rest_zero)),
        "complete_two_hand_rate": rate(sum(all(predictions[row["frame_id"]]) for row in two), len(two)),
    }


def historical_rescore(v2: list[dict[str, str]]) -> tuple[list[dict[str, Any]], bool]:
    truth = {row["frame_id"]: row for row in v2}
    results: list[dict[str, Any]] = [{
        "method": "P4A_E2_HISTORICAL", "frames_rescored": 0, "status": "NOT_RESCOREABLE_NO_V2_FRAME_IDENTITY_OVERLAP",
        "historical_classification": "ELIGIBILITY_IMPROVED_BUT_GATES_FAILED",
    }]
    e2_rows = read_csv(P4A2 / "p4a2_fresh_e2_baseline.csv")
    e2: dict[str, list[bool]] = {}
    for row in e2_rows:
        e2.setdefault(row["annotation_row_id"], [False, False])[0 if row["anatomical_side"].lower() == "left" else 1] = yes(row["e2_accept"])
    value = evaluate_predictions(truth, {key: tuple(item) for key, item in e2.items()}, "P4A2_E2_DEV_VALIDATION_262")
    value.update({"status": "RESCORED_FROM_FROZEN_OUTPUT", "historical_classification": "ELIGIBILITY_IMPROVED_BUT_GATES_FAILED"})
    results.append(value)
    final_rows = read_csv(P4A2 / "p4a2_final_eval_predictions.csv")
    for field, name in (("e2_accept", "P4A2_E2_FINAL_196"), ("selected_prediction", "P4A2_E2_PLUS_R1_FINAL_196")):
        pred: dict[str, list[bool]] = {}
        for row in final_rows:
            pred.setdefault(row["annotation_row_id"], [False, False])[0 if row["anatomical_side"].lower() == "left" else 1] = yes(row[field])
        value = evaluate_predictions(truth, {key: tuple(item) for key, item in pred.items()}, name)
        value.update({"status": "RESCORED_FROM_FROZEN_OUTPUT", "historical_classification": "ELIGIBILITY_IMPROVED_BUT_GATES_FAILED"})
        results.append(value)
    wilor_rows = read_csv(P4C1 / "p4c1_frame_results.csv")
    wilor = {row["annotation_row_id"]: (yes(row["wilor_left"]), yes(row["wilor_right"])) for row in wilor_rows}
    value = evaluate_predictions(truth, wilor, "P4C1_WILOR_ALL_458")
    value.update({"status": "RESCORED_FROM_FROZEN_OUTPUT", "historical_classification": "WILOR_DETECTION_RECALL_INSUFFICIENT"})
    results.append(value)
    review_flag = False
    for row in results:
        if row.get("frames_rescored", 0) == 0:
            continue
        passes = (
            (row.get("physical_capacity_rate") or 0) >= .98
            and (row.get("one_hand_existence_recall") or 0) >= .97
            and (row.get("zero_hand_activation_rate") or 1) <= .10
            and (row.get("rest_zero_activation_rate") or 1) <= .10
            and (row.get("complete_two_hand_rate") or 0) >= .95
        )
        row["passes_all_original_relevant_gates"] = "YES" if passes else "NO"
        review_flag |= passes
    return results, review_flag


def finalize() -> dict[str, Any]:
    source_hashes = verify_sources()
    v2, changes, uncertainty, composition = freeze_v2()
    count_rows, ownership_rows, dwpose = proposal_rows(v2)
    crop_rows, crop = crop_rescore(v2)
    historical, historical_review = historical_rescore(v2)

    v2_path = OUT / "P4_ELIGIBILITY_TRUTH_V2.csv"
    atomic_csv(OUT / "p4gt1r_dwpose_count_rescore.csv", count_rows, list(count_rows[0]))
    atomic_csv(OUT / "p4gt1r_dwpose_ownership_rescore.csv", ownership_rows, list(ownership_rows[0]))
    atomic_csv(OUT / "p4gt1r_crop_authenticity_rescore.csv", crop_rows, list(crop_rows[0]))
    historical_fields = sorted({key for row in historical for key in row})
    atomic_csv(OUT / "p4gt1r_historical_rescore.csv", historical, historical_fields)

    capacity = dwpose["physical_proposal_capacity"]["rate"]
    one_recall = dwpose["one_hand_existence_recall"]["rate"]
    two_recall = dwpose["complete_two_hand_proposal_recall"]["rate"]
    enough_truth = composition["count_known_frames"] >= 440
    classification = "P4GT1R_V2_READY_FOR_ARCHITECTURE_DECISIONS" if enough_truth else "P4GT1R_EVIDENCE_INSUFFICIENT_AFTER_UNCERTAINTY"
    proposal_flag = capacity is not None and capacity < .98
    manifest = {
        "dataset_id": "P4_ELIGIBILITY_TRUTH_V2",
        "status": "GOVERNED_DEVELOPMENT_GROUND_TRUTH",
        "not_final_research_gold": True,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "v1_source_hashes": source_hashes,
        "v1_dataset_sha256": EXPECTED_DATASET,
        "v2_annotation_sha256": sha256(v2_path),
        "composition": composition,
        "adjudication_rows": 6,
        "adjudication_review_sha256": sha256(ADJUDICATION),
        "rule": "Pass1 retained except the six repeatability conflicts, which use count-first P4-GT1R adjudication.",
    }
    atomic_json(OUT / "p4gt1r_v2_manifest.json", manifest)
    result = {
        "status": "P4GT1R_COMPLETE",
        "classification": classification,
        "v2_annotation_sha256": manifest["v2_annotation_sha256"],
        "v2_manifest_sha256": sha256(OUT / "p4gt1r_v2_manifest.json"),
        "composition": composition,
        "six_conflicts": {"count_disagreement": 6, "ownership_only_disagreement": 0, "mixed": 0},
        "dwpose": dwpose,
        "proposal_gate_flags": {
            "physical_capacity_ge_98": capacity is not None and capacity >= .98,
            "one_hand_existence_ge_97": one_recall is not None and one_recall >= .97,
            "two_hand_complete_ge_95": two_recall is not None and two_recall >= .95,
            "v2_physical_proposal_ceiling_below_gate": proposal_flag,
        },
        "crop_authenticity": crop,
        "historical_result_requires_project_lead_review": historical_review,
        "historical_rescore": historical,
        "changes": {"rows": len(changes), "by_type": dict(Counter(row["change_type"] for row in changes))},
        "uncertainty_inventory_rows": len(uncertainty),
        "models_rerun": False,
        "models_trained": False,
    }
    atomic_json(OUT / "p4gt1r_result.json", result)

    own = dwpose["ownership"]
    report = f"""# P4-GT1R Schema Repair and V2 Rescore Result

## Decision

**`P4GT1R_COMPLETE` — `{classification}`.**

`P4_ELIGIBILITY_TRUTH_V2` is frozen as **governed development ground truth**. It is not
presented as a perfect final research gold set; a fresh unseen evaluation remains necessary after
an architecture is frozen. V1 and every historical report remain immutable.

## Ground-truth repair

- V1 hashes verified: **yes**
- Complete Pass-1 frames: **458**
- Six conflicts adjudicated: **6/6**, with no edit revisions
- Previous repeatability conflicts: **6 count disagreements, 0 ownership-only, 0 mixed**
- Count-known frames: **{composition['count_known_frames']}**
- Count-uncertain frames: **{composition['count_uncertain']}**
- ZERO / ONE / TWO: **{composition['count_zero']} / {composition['count_one']} / {composition['count_two']}**
- One-hand ownership LEFT / RIGHT / UNCERTAIN: **{composition['one_left']} / {composition['one_right']} / {composition['one_ownership_uncertain']}**
- Visible / absent hands in known truth: **{composition['visible_hands']} / {composition['absent_hands']}**
- Uncertain anatomical sides excluded: **{composition['uncertain_sides_excluded']}**
- V1→V2 changed side labels: **{len(changes)}**

## A. Physical proposal availability

- Capacity: **{dwpose['physical_proposal_capacity']['numerator']}/{dwpose['physical_proposal_capacity']['denominator']} = {capacity:.2%}**
- One-hand existence: **{dwpose['one_hand_existence_recall']['numerator']}/{dwpose['one_hand_existence_recall']['denominator']} = {one_recall:.2%}**
- Complete two-hand proposals: **{dwpose['complete_two_hand_proposal_recall']['numerator']}/{dwpose['complete_two_hand_proposal_recall']['denominator']} = {two_recall:.2%}**
- Zero-hand activation: **{dwpose['zero_hand_activation']['numerator']}/{dwpose['zero_hand_activation']['denominator']} = {dwpose['zero_hand_activation']['rate']:.2%}**
- Remaining missing proposal capacity: **{dwpose['proposal_misses']} hand observations**
- Physical-capacity ≥98% gate: **{'PASS' if capacity >= .98 else 'FAIL'}**

## B. Anatomical ownership diagnostics

On {own['known_one_hand_frames']} one-hand frames with known ownership:

- Correct-slot retention: **{own['true_slot_retention']}/{own['known_one_hand_frames']} = {own['true_slot_retention_rate']:.2%}**
- Opposite-slot activation: **{own['opposite_slot_false_presence']}/{own['known_one_hand_frames']} = {own['opposite_slot_false_presence_rate']:.2%}**
- Dual-slot collisions: **{own['dual_slot_collisions']}/{own['known_one_hand_frames']} = {own['dual_slot_collision_rate']:.2%}**

No ownership heuristic was created or tested.

## C. RGB crop authenticity

The existing 200 crop judgments are preserved and reinterpreted correctly as authenticity evidence:

- RGB hand present: **{crop['rgb_hand_present']}/200**
- RGB hand absent: **{crop['rgb_hand_absent']}/200**
- Uncertain: **{crop['uncertain']}/200**
- Binary human decidability: **{crop['binary_human_decidability']:.2%}**

These values do not measure anatomical ownership. A crop from an absent slot that contains the
opposite real hand is an ownership problem, not an RGB-authenticity error. The original P4-C2A
classification is not rewritten.

## Historical frozen-output rescore

P4-A cannot be joined to V2 by frame identity. P4-A2 E2/R1 and P4-C1 WiLoR were rescored only
from stored outputs; no inference or tuning occurred. **{'A closed method meets every relevant original gate and requires project-lead review.' if historical_review else 'No historically closed method meets every relevant original gate under V2.'}**

## Boundaries

No DWPose, WiLoR, E2, R1, detector, or other perception model was run or trained. No proposal
fallback, ownership rule, MobileNet, HVD, Android, S4-S7, recognition, P4-C2B, P4-D, or P4-B work
occurred.
"""
    atomic_text(OUT / "P4GT1R_SCHEMA_REPAIR_AND_V2_RESCORE_RESULT.md", report)

    tracked = [path for path in OUT.iterdir() if path.is_file() and path.name != "p4gt1r_artifact_hash_manifest.json"]
    atomic_json(OUT / "p4gt1r_artifact_hash_manifest.json", {
        "status": "P4GT1R_FROZEN_V2", "artifacts": {path.name: sha256(path) for path in sorted(tracked)}
    })
    return result


if __name__ == "__main__":
    print(json.dumps(finalize(), indent=2, sort_keys=True))
