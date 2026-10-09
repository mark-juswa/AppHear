"""Prepare the minimal blinded P4-C3B physical-instance review package."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement"
V2_DIR = BASE / "p4gt1r_schema_repair_v2_01"
V2 = V2_DIR / "P4_ELIGIBILITY_TRUTH_V2.csv"
C3A = BASE / "p4c3a_raw_dwpose_failure_decomposition_01"
MISSING = C3A / "p4c3a_missing_hand_classification.csv"
COLLISIONS = C3A / "p4c3a_collision_inventory.csv"
INFERENCE = BASE / "p4a2_high_recall_rescue_final_01/p4a2_frozen_inference_manifest.csv"
OUT = BASE / "p4c3b_physical_instance_validation_01"
OVERLAYS = OUT / "immutable_overlays"
EXPECTED_V2 = "24f5d8d442702e3a27424ff7f55cc24f1338f5683e5988a6a4916557e1d4252d"
EXPECTED_CHECKPOINT = "e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7"
PAIR_SAMPLE_SEED = "P4C3B_TWO_HAND_REFERENCE_V1_20260825"
ORDER_SEED = "P4C3B_BLINDED_REVIEW_ORDER_V1_20260825"


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
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    rows = list(rows)
    fields = fields or list(rows[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def stable_id(prefix: str, *values: str) -> str:
    return prefix + "_" + hashlib.sha256("|".join(values).encode()).hexdigest()[:24]


def native_path(row: dict[str, str]) -> Path:
    path = Path(row["raw_relative_path"])
    return path if path.is_absolute() else ROOT / path


def point_box(points: np.ndarray) -> tuple[int, int, int, int]:
    finite = points[np.isfinite(points).all(axis=1)]
    low, high = finite.min(axis=0), finite.max(axis=0)
    margin = max(4.0, 0.10 * float(max(high - low)))
    return tuple(int(round(value)) for value in (low[0] - margin, low[1] - margin, high[0] + margin, high[1] + margin))


def draw_candidate(image: np.ndarray, points: np.ndarray, color: tuple[int, int, int], label: str, line_type: int = cv2.LINE_AA) -> None:
    x1, y1, x2, y2 = point_box(points)
    cv2.rectangle(image, (x1, y1), (x2, y2), color, 3, line_type)
    for point in points:
        if np.isfinite(point).all():
            cv2.circle(image, tuple(np.rint(point).astype(int)), 3, color, -1, cv2.LINE_AA)
    label_x = min(max(4, x1), max(4, image.shape[1] - 230))
    label_y = min(max(24, y1 - 6), max(24, image.shape[0] - 10))
    cv2.putText(image, label, (label_x, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2, cv2.LINE_AA)


def pad_canvas(image: np.ndarray) -> np.ndarray:
    if image.shape[1] >= 640:
        return image
    return cv2.copyMakeBorder(image, 0, 0, 0, 640 - image.shape[1], cv2.BORDER_CONSTANT, value=(24, 24, 24))


def banner(image: np.ndarray, lines: list[tuple[str, tuple[int, int, int]]]) -> np.ndarray:
    image = pad_canvas(image)
    height = 42 + 30 * max(0, len(lines) - 1)
    canvas = cv2.copyMakeBorder(image, height, 0, 0, 0, cv2.BORDER_CONSTANT, value=(24, 24, 24))
    for index, (text, color) in enumerate(lines):
        cv2.putText(canvas, text, (12, 28 + index * 30), cv2.FONT_HERSHEY_SIMPLEX, 0.68, color, 2, cv2.LINE_AA)
    return canvas


def save_overlay(path: Path, image: np.ndarray) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("P4C3B_OVERLAY_ENCODING_FAILURE")
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(encoded.tobytes())
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return sha256(path)


def temporal_round_robin(rows: list[dict[str, str]], count: int) -> list[dict[str, str]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["sequence_id"]].append(row)
    for values in groups.values():
        values.sort(key=lambda row: int(row["frame_index"]))
    sequences = sorted(groups, key=lambda key: hashlib.sha256(f"{PAIR_SAMPLE_SEED}|{key}".encode()).hexdigest())
    selected: list[dict[str, str]] = []
    round_index = 0
    while len(selected) < count:
        progressed = False
        for sequence in sequences:
            values = groups[sequence]
            if round_index < len(values):
                selected.append(values[round_index])
                progressed = True
                if len(selected) == count:
                    break
        if not progressed:
            break
        round_index += 1
    if len(selected) != count:
        raise RuntimeError("P4C3B_REFERENCE_SAMPLE_INSUFFICIENT")
    return selected


def main() -> dict[str, Any]:
    for review_path in (OUT / "p4c3b_raw_A_visual_validation.csv", OUT / "p4c3b_pair_review.csv"):
        if review_path.exists() and any(row.get("reviewer_status") == "COMPLETE" for row in read_csv(review_path)):
            raise RuntimeError("P4C3B_REVIEW_ALREADY_STARTED_PACKAGE_IMMUTABLE")
    if sha256(V2) != EXPECTED_V2:
        raise RuntimeError("P4C3B_SOURCE_INTEGRITY_FAILURE")
    c3a_result = json.loads((C3A / "p4c3a_result.json").read_text(encoding="utf-8"))
    if c3a_result["status"] != "P4C3A_COMPLETE" or c3a_result["collision_categories"]["SAME_PHYSICAL_HAND_DUPLICATE"] != 59:
        raise RuntimeError("P4C3B_SOURCE_INTEGRITY_FAILURE")
    v2 = read_csv(V2)
    truth = {row["frame_id"]: row for row in v2}
    inference = {row["annotation_row_id"]: row for row in read_csv(INFERENCE)}
    category_a = [row for row in read_csv(MISSING) if row["primary_category"] == "A_RAW_HAND_GEOMETRY_PRESENT"]
    collision_rows = read_csv(COLLISIONS)
    if len(category_a) != 21 or len(collision_rows) != 60:
        raise RuntimeError("P4C3B_SOURCE_INTEGRITY_FAILURE")
    OUT.mkdir(parents=True, exist_ok=True)
    OVERLAYS.mkdir(parents=True, exist_ok=True)

    raw_inventory: list[dict[str, Any]] = []
    raw_reviews: list[dict[str, Any]] = []
    queue_rows: list[dict[str, Any]] = []
    for source in sorted(category_a, key=lambda row: row["frame_id"]):
        frame_id = source["frame_id"]
        item = inference[frame_id]
        path = native_path(item)
        with np.load(path, allow_pickle=False) as native:
            if str(native["source_sha256"].item()) != source["source_sha256"] or str(native["checkpoint_sha256"].item()) != EXPECTED_CHECKPOINT:
                raise RuntimeError("P4C3B_SOURCE_INTEGRITY_FAILURE")
            left = np.asarray(native["left_hand_keypoints"], dtype=np.float64)
            right = np.asarray(native["right_hand_keypoints"], dtype=np.float64)
            left_scores = np.asarray(native["left_hand_scores"], dtype=np.float64)
            right_scores = np.asarray(native["right_hand_scores"], dtype=np.float64)
            gated = np.asarray(native["gated_presence"], dtype=bool)
        image = cv2.imread(source["source_image_path"])
        if image is None or sha256(Path(source["source_image_path"])) != source["source_sha256"]:
            raise RuntimeError("P4C3B_SOURCE_INTEGRITY_FAILURE")
        side = source["anatomical_side"].lower()
        raw_points = left if side == "left" else right
        raw_scores = left_scores if side == "left" else right_scores
        overlay = pad_canvas(image.copy())
        for index, points in enumerate((left, right)):
            if gated[index]:
                draw_candidate(overlay, points, (40, 210, 40), "ACCEPTED")
        draw_candidate(overlay, raw_points, (220, 60, 220), "RAW CANDIDATE")
        overlay = banner(overlay, [("GREEN: currently accepted proposal", (40, 210, 40)), ("MAGENTA: raw recovery candidate", (220, 60, 220))])
        item_id = stable_id("P4C3B_RAW", frame_id, side, source["source_sha256"])
        overlay_path = OVERLAYS / f"{item_id}.png"
        overlay_sha = save_overlay(overlay_path, overlay)
        row = {
            "item_id": item_id, "frame_id": frame_id, "signer_id": source["signer_id"], "sequence_id": source["sequence_id"],
            "frame_index": source["frame_index"], "source_sha256": source["source_sha256"],
            "v2_visible_hand_count": truth[frame_id]["visible_hand_count"], "missing_anatomical_side": source["anatomical_side"],
            "accepted_left": "YES" if gated[0] else "NO", "accepted_right": "YES" if gated[1] else "NO",
            "raw_candidate_points_json": json.dumps(raw_points.tolist(), separators=(",", ":")),
            "raw_candidate_scores_json": json.dumps(raw_scores.tolist(), separators=(",", ":")),
            "left_points_json": json.dumps(left.tolist(), separators=(",", ":")),
            "right_points_json": json.dumps(right.tolist(), separators=(",", ":")),
            "native_output_path": str(path), "source_image_path": source["source_image_path"],
            "overlay_path": str(overlay_path), "overlay_sha256": overlay_sha,
        }
        raw_inventory.append(row)
        raw_reviews.append({"item_id": item_id, "overlay_sha256": overlay_sha, "review_label": "", "reviewer_status": "UNREVIEWED", "reviewed_utc": "", "revision_count": "0", "last_edit_utc": "", "last_edit_reason": ""})
        queue_rows.append({"item_id": item_id, "task_type": "RAW_A", "overlay_path": str(overlay_path), "overlay_sha256": overlay_sha})

    collision_ids = {row["frame_id"] for row in collision_rows}
    reference_candidates: list[dict[str, str]] = []
    for row in v2:
        if row["visible_hand_count"] != "TWO" or row["frame_id"] in collision_ids:
            continue
        path = native_path(inference[row["frame_id"]])
        with np.load(path, allow_pickle=False) as native:
            gated = np.asarray(native["gated_presence"], dtype=bool)
        if bool(gated[0]) and bool(gated[1]):
            reference_candidates.append(row)
    references = temporal_round_robin(reference_candidates, 40)

    pair_manifest: list[dict[str, Any]] = []
    pair_reviews: list[dict[str, Any]] = []
    pair_sources = [("COLLISION", truth[row["frame_id"]]) for row in collision_rows] + [("TWO_HAND_REFERENCE", row) for row in references]
    for origin, frame in pair_sources:
        frame_id = frame["frame_id"]
        item = inference[frame_id]
        path = native_path(item)
        with np.load(path, allow_pickle=False) as native:
            if str(native["source_sha256"].item()) != frame["source_sha256"] or str(native["checkpoint_sha256"].item()) != EXPECTED_CHECKPOINT:
                raise RuntimeError("P4C3B_SOURCE_INTEGRITY_FAILURE")
            left = np.asarray(native["left_hand_keypoints"], dtype=np.float64)
            right = np.asarray(native["right_hand_keypoints"], dtype=np.float64)
            gated = np.asarray(native["gated_presence"], dtype=bool)
        if not bool(gated[0]) or not bool(gated[1]):
            raise RuntimeError("P4C3B_PAIR_WITHOUT_TWO_CANDIDATES")
        image = cv2.imread(frame["source_image_path"])
        if image is None or sha256(Path(frame["source_image_path"])) != frame["source_sha256"]:
            raise RuntimeError("P4C3B_SOURCE_INTEGRITY_FAILURE")
        swap = int(hashlib.sha256(f"P4C3B_PAIR_ORDER|{frame_id}".encode()).hexdigest(), 16) % 2 == 1
        candidate_a, candidate_b = (right, left) if swap else (left, right)
        source_a, source_b = ("RIGHT_NATIVE_SLOT", "LEFT_NATIVE_SLOT") if swap else ("LEFT_NATIVE_SLOT", "RIGHT_NATIVE_SLOT")
        overlay = pad_canvas(image.copy())
        draw_candidate(overlay, candidate_a, (255, 220, 30), "CANDIDATE A")
        draw_candidate(overlay, candidate_b, (20, 150, 255), "CANDIDATE B")
        overlay = banner(overlay, [("CYAN: candidate A", (255, 220, 30)), ("ORANGE: candidate B", (20, 150, 255))])
        pair_id = stable_id("P4C3B_PAIR", frame_id, frame["source_sha256"])
        overlay_path = OVERLAYS / f"{pair_id}.png"
        overlay_sha = save_overlay(overlay_path, overlay)
        pair_manifest.append({
            "pair_id": pair_id, "frame_id": frame_id, "pair_origin": origin, "signer_id": frame["signer_id"],
            "sequence_id": frame["sequence_id"], "frame_index": frame["frame_index"], "source_sha256": frame["source_sha256"],
            "v2_visible_hand_count": frame["visible_hand_count"], "candidate_a_native_source": source_a,
            "candidate_b_native_source": source_b, "candidate_a_points_json": json.dumps(candidate_a.tolist(), separators=(",", ":")),
            "candidate_b_points_json": json.dumps(candidate_b.tolist(), separators=(",", ":")),
            "native_output_path": str(path), "source_image_path": frame["source_image_path"],
            "overlay_path": str(overlay_path), "overlay_sha256": overlay_sha,
            "selection_basis": "ALL_60_COLLISIONS" if origin == "COLLISION" else "DETERMINISTIC_SIGNER_SEQUENCE_TIME_ONLY_REFERENCE_SAMPLE",
        })
        pair_reviews.append({"pair_id": pair_id, "overlay_sha256": overlay_sha, "review_label": "", "reviewer_status": "UNREVIEWED", "reviewed_utc": "", "revision_count": "0", "last_edit_utc": "", "last_edit_reason": ""})
        queue_rows.append({"item_id": pair_id, "task_type": "PAIR", "overlay_path": str(overlay_path), "overlay_sha256": overlay_sha})

    if len(raw_inventory) != 21 or len(pair_manifest) != 100 or len({row["pair_id"] for row in pair_manifest}) != 100:
        raise RuntimeError("P4C3B_PACKAGE_COUNT_FAILURE")
    queue_rows.sort(key=lambda row: hashlib.sha256(f"{ORDER_SEED}|{row['item_id']}".encode()).hexdigest())
    for index, row in enumerate(queue_rows):
        row["queue_order"] = index
    atomic_csv(OUT / "p4c3b_raw_A_inventory.csv", raw_inventory)
    atomic_csv(OUT / "p4c3b_raw_A_visual_validation.csv", raw_reviews)
    atomic_csv(OUT / "p4c3b_pair_truth_manifest.csv", pair_manifest)
    atomic_csv(OUT / "p4c3b_pair_review.csv", pair_reviews)
    atomic_csv(OUT / "p4c3b_review_queue.csv", queue_rows)
    atomic_json(OUT / "p4c3b_review_protocol.json", {
        "status": "FROZEN_BEFORE_HUMAN_REVIEW", "p4c3a_duplicate_label_source": "GEOMETRY_DERIVED",
        "raw_A_cases": 21, "collision_pairs": 60, "two_hand_reference_pairs": 40, "total_review_items": 121,
        "reference_sample_seed": PAIR_SAMPLE_SEED, "review_order_seed": ORDER_SEED,
        "candidate_order": "deterministic per-pair hash; anatomical slot hidden",
        "raw_labels": ["MISSING_REAL_HAND", "DUPLICATE_EXISTING_HAND", "OTHER_FALSE_REGION", "AMBIGUOUS"],
        "pair_labels": ["SAME_PHYSICAL_HAND", "DISTINCT_PHYSICAL_HANDS", "AMBIGUOUS"],
        "reviewer_hidden": ["V2 truth", "anatomical side", "native left/right slot", "P4-C3A category rationale", "confidence", "pair origin", "model interpretation"],
        "no_geometry_labels_reused_as_truth": True, "no_model_inference": True,
    })
    atomic_json(OUT / "p4c3b_blinding_manifest.json", {
        "reviewer_visible": ["overlay image", "candidate legend", "task-specific physical-instance question", "progress"],
        "reviewer_hidden_columns": ["pair_origin", "signer", "sequence", "V2 count", "missing anatomical side", "candidate native slot source", "scores", "geometry classification"],
        "source_images_unmirrored": True,
    })
    result = {
        "status": "P4C3B_RAW_CANDIDATE_REVIEW_READY", "v2_verified": True,
        "p4c3a_duplicate_label_source": "GEOMETRY_DERIVED", "raw_A_review_count": 21,
        "pair_review_count": 100, "collision_pair_count": 60, "two_hand_reference_pair_count": 40,
        "total_review_items": 121, "models_rerun": False, "part_b_started": False,
    }
    atomic_json(OUT / "p4c3b_prepare_result.json", result)
    atomic_text(OUT / "P4C3B_PHYSICAL_INSTANCE_VALIDATION_RESULT.md", f"""# P4-C3B Physical Hand Instance Validation

## Status

**`P4C3B_RAW_CANDIDATE_REVIEW_READY` — human review required; Part B has not started.**

P4-C3A duplicate labels were **`GEOMETRY_DERIVED`**, so they were not reused as independent truth.
The frozen blinded package contains exactly 21 category-A raw-candidate cases, all 60 collision
pairs, and 40 signer/sequence/time-selected two-hand reference pairs. No pair was selected by
distance, overlap, apparent ease, or expected model outcome.

The overlay shows physical proposal regions only. It hides native left/right slot identity,
anatomical truth, confidence, P4-C3A rationale, pair origin, and expected answer. The user answers
only whether a raw candidate represents the missing/already-seen/neither hand, or whether two
candidates represent the same/distinct physical hand.

No DWPose inference, deduplication rule, feature fitting, classifier, HVD, detector, Android,
recognition, or S4-S7 work occurred. After 121/121 independent labels are complete, Part B may
compute symmetric pair features, freeze a sequence-level development/validation split, select one
transparent rule on development, and open validation once.
""")
    tracked = [path for path in OUT.iterdir() if path.is_file() and path.name != "p4c3b_prepare_hash_manifest.json"]
    atomic_json(OUT / "p4c3b_prepare_hash_manifest.json", {
        "status": "P4C3B_REVIEW_PACKAGE_FROZEN", "artifacts": {path.name: sha256(path) for path in sorted(tracked)},
        "overlay_count": len(list(OVERLAYS.glob("*.png"))),
        "overlay_hashes": {path.name: sha256(path) for path in sorted(OVERLAYS.glob("*.png"))},
        "source_hashes": {"v2": sha256(V2), "p4c3a_result": sha256(C3A / "p4c3a_result.json"), "inference_manifest": sha256(INFERENCE)},
        "tool_hashes": {
            "preparer": sha256(Path(__file__)),
            "review_ui": sha256(ROOT / "eval/runtime_diagnostics/p4c3b_physical_instance_review.py"),
            "tests": sha256(ROOT / "tests/test_p4c3b_physical_instance_review.py"),
            "launcher": sha256(ROOT / "model/config/recognition_upgrade/run_p4c3b_physical_instance_review.ps1"),
        },
    })
    return result


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
