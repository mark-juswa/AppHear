"""Finalize independent P4-C3B truth and one frozen symmetric deduplication rule."""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement"
OUT = BASE / "p4c3b_physical_instance_validation_01"
V2 = BASE / "p4gt1r_schema_repair_v2_01/P4_ELIGIBILITY_TRUTH_V2.csv"
EXPECTED_V2 = "24f5d8d442702e3a27424ff7f55cc24f1338f5683e5988a6a4916557e1d4252d"
RAW_INVENTORY = OUT / "p4c3b_raw_A_inventory.csv"
RAW_REVIEW = OUT / "p4c3b_raw_A_visual_validation.csv"
PAIR_MANIFEST = OUT / "p4c3b_pair_truth_manifest.csv"
PAIR_REVIEW = OUT / "p4c3b_pair_review.csv"
QUEUE = OUT / "p4c3b_review_queue.csv"
JOURNAL = OUT / "p4c3b_review_edit_journal.jsonl"
BASE_PROPOSALS = 419
VISIBLE_HANDS = 444
TARGET_PROPOSALS = 436
SPLIT_SEED = "P4C3B_SIGNER_SEPARATED_PAIR_SPLIT_V1_20260825"


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
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def atomic_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    rows = list(rows)
    fields = fields or list(rows[0])
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def verify_review() -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    if sha256(V2) != EXPECTED_V2:
        raise RuntimeError("P4C3B_SOURCE_INTEGRITY_FAILURE")
    raw_inventory = read_csv(RAW_INVENTORY)
    raw_review = read_csv(RAW_REVIEW)
    pair_manifest = read_csv(PAIR_MANIFEST)
    pair_review = read_csv(PAIR_REVIEW)
    queue = read_csv(QUEUE)
    if not (len(raw_inventory) == len(raw_review) == 21 and len(pair_manifest) == len(pair_review) == 100 and len(queue) == 121):
        raise RuntimeError("P4C3B_REVIEW_INTEGRITY_FAILURE")
    raw_ids = {row["item_id"] for row in raw_inventory}
    pair_ids = {row["pair_id"] for row in pair_manifest}
    if raw_ids != {row["item_id"] for row in raw_review} or pair_ids != {row["pair_id"] for row in pair_review}:
        raise RuntimeError("P4C3B_REVIEW_INTEGRITY_FAILURE")
    if any(row["reviewer_status"] != "COMPLETE" for row in raw_review + pair_review):
        raise RuntimeError("P4C3B_REVIEW_INCOMPLETE")
    allowed_raw = {"MISSING_REAL_HAND", "DUPLICATE_EXISTING_HAND", "OTHER_FALSE_REGION", "AMBIGUOUS"}
    allowed_pair = {"SAME_PHYSICAL_HAND", "DISTINCT_PHYSICAL_HANDS", "AMBIGUOUS"}
    if any(row["review_label"] not in allowed_raw for row in raw_review) or any(row["review_label"] not in allowed_pair for row in pair_review):
        raise RuntimeError("P4C3B_REVIEW_INTEGRITY_FAILURE")
    queue_by_id = {row["item_id"]: row for row in queue}
    for row in raw_review:
        item = queue_by_id[row["item_id"]]
        if item["task_type"] != "RAW_A" or item["overlay_sha256"] != row["overlay_sha256"] or sha256(Path(item["overlay_path"])) != row["overlay_sha256"]:
            raise RuntimeError("P4C3B_REVIEW_ITEM_IDENTITY_MISMATCH")
    for row in pair_review:
        item = queue_by_id[row["pair_id"]]
        if item["task_type"] != "PAIR" or item["overlay_sha256"] != row["overlay_sha256"] or sha256(Path(item["overlay_path"])) != row["overlay_sha256"]:
            raise RuntimeError("P4C3B_REVIEW_ITEM_IDENTITY_MISMATCH")
    expected_revisions = sum(int(row["revision_count"]) for row in raw_review + pair_review)
    journal_entries = [line for line in JOURNAL.read_text(encoding="utf-8").splitlines() if line.strip()] if JOURNAL.exists() else []
    if expected_revisions != len(journal_entries):
        raise RuntimeError("P4C3B_EDIT_JOURNAL_MISMATCH")
    return raw_inventory, raw_review, pair_manifest, pair_review


def envelope(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
    low, high = np.min(points, axis=0), np.max(points, axis=0)
    center = (low + high) / 2
    size = high - low
    area = float(max(size[0], 1e-8) * max(size[1], 1e-8))
    diagonal = float(np.linalg.norm(size))
    return low, high, area, diagonal


def pair_features(row: dict[str, str]) -> dict[str, Any]:
    a = np.asarray(json.loads(row["candidate_a_points_json"]), dtype=np.float64)
    b = np.asarray(json.loads(row["candidate_b_points_json"]), dtype=np.float64)
    if a.shape != (21, 2) or b.shape != (21, 2) or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise RuntimeError("P4C3B_PAIR_GEOMETRY_INVALID")
    low_a, high_a, area_a, diag_a = envelope(a)
    low_b, high_b, area_b, diag_b = envelope(b)
    iw = max(0.0, min(high_a[0], high_b[0]) - max(low_a[0], low_b[0]))
    ih = max(0.0, min(high_a[1], high_b[1]) - max(low_a[1], low_b[1]))
    intersection = iw * ih
    union = area_a + area_b - intersection
    center_a, center_b = (low_a + high_a) / 2, (low_b + high_b) / 2
    hand_scale = max((diag_a + diag_b) / 2, 1e-8)
    distances = np.linalg.norm(a - b, axis=1)
    centered_a, centered_b = a - np.mean(a, axis=0), b - np.mean(b, axis=0)
    rms_a = float(np.sqrt(np.mean(np.sum(centered_a**2, axis=1))))
    rms_b = float(np.sqrt(np.mean(np.sum(centered_b**2, axis=1))))
    shape_distance = float(np.mean(np.linalg.norm(centered_a / max(rms_a, 1e-8) - centered_b / max(rms_b, 1e-8), axis=1)))
    return {
        "pair_id": row["pair_id"], "frame_id": row["frame_id"], "signer_id": row["signer_id"],
        "sequence_id": row["sequence_id"], "frame_index": row["frame_index"], "pair_origin": row["pair_origin"],
        "box_iou": intersection / union if union else 0.0,
        "intersection_smaller_box_ratio": intersection / min(area_a, area_b) if min(area_a, area_b) else 0.0,
        "center_distance_px": float(np.linalg.norm(center_a - center_b)),
        "normalized_center_distance": float(np.linalg.norm(center_a - center_b) / hand_scale),
        "raw_wrist_distance_px": float(np.linalg.norm(a[0] - b[0])),
        "normalized_wrist_distance": float(np.linalg.norm(a[0] - b[0]) / hand_scale),
        "mean_corresponding_distance_px": float(np.mean(distances)),
        "median_corresponding_distance_px": float(np.median(distances)),
        "max_corresponding_distance_px": float(np.max(distances)),
        "mean_corresponding_distance_normalized": float(np.mean(distances) / hand_scale),
        "median_corresponding_distance_normalized": float(np.median(distances) / hand_scale),
        "relative_proposal_scale": float(max(area_a, area_b) / max(min(area_a, area_b), 1e-8)),
        "candidate_point_envelope_overlap": intersection / min(area_a, area_b) if min(area_a, area_b) else 0.0,
        "translation_scale_normalized_shape_distance": shape_distance,
        "symmetric_feature_contract": "YES",
    }


def freeze_split(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [row for row in rows if row["truth_label"] != "AMBIGUOUS"]
    signers = sorted({row["signer_id"] for row in usable})
    totals = Counter(row["truth_label"] for row in usable)
    target = {label: totals[label] * 0.35 for label in totals}
    best: tuple[float, tuple[str, ...]] | None = None
    for size in range(2, len(signers) - 1):
        for selected in itertools.combinations(signers, size):
            validation = [row for row in usable if row["signer_id"] in selected]
            development = [row for row in usable if row["signer_id"] not in selected]
            val = Counter(row["truth_label"] for row in validation)
            dev = Counter(row["truth_label"] for row in development)
            if min(val["SAME_PHYSICAL_HAND"], val["DISTINCT_PHYSICAL_HANDS"], dev["SAME_PHYSICAL_HAND"], dev["DISTINCT_PHYSICAL_HANDS"]) < 8:
                continue
            score = sum(((val[label] - target[label]) / max(target[label], 1)) ** 2 for label in target)
            score += 0.05 * abs(len(validation) / len(usable) - 0.35)
            tie = tuple(hashlib.sha256(f"{SPLIT_SEED}|{name}".encode()).hexdigest() for name in selected)
            candidate = (score, tie)
            if best is None or candidate < (best[0], tuple(hashlib.sha256(f"{SPLIT_SEED}|{name}".encode()).hexdigest() for name in best[1])):
                best = (score, selected)
    if best is None:
        raise RuntimeError("P4C3B_SIGNER_SEPARATED_SPLIT_UNAVAILABLE")
    validation_signers = set(best[1])
    assignments = {}
    for row in rows:
        assignments[row["pair_id"]] = "VALIDATION" if row["signer_id"] in validation_signers else "DEVELOPMENT"
    return {
        "split_seed": SPLIT_SEED, "strategy": "SIGNER_SEPARATED_STRATIFIED_BY_INDEPENDENT_PAIR_TRUTH",
        "validation_signers": sorted(validation_signers), "development_signers": sorted(set(signers) - validation_signers),
        "assignments": assignments,
    }


def quantiles(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {name: float(np.quantile(array, q)) for name, q in (("min", 0), ("p10", .10), ("p50", .50), ("p90", .90), ("p95", .95), ("max", 1))}


def auc(labels: list[int], scores: list[float]) -> float | None:
    positive = [score for label, score in zip(labels, scores, strict=True) if label == 1]
    negative = [score for label, score in zip(labels, scores, strict=True) if label == 0]
    if not positive or not negative:
        return None
    wins = sum(p < n for p in positive for n in negative)
    ties = sum(p == n for p in positive for n in negative)
    return (wins + 0.5 * ties) / (len(positive) * len(negative))


def main() -> dict[str, Any]:
    raw_inventory, raw_review, pair_manifest, pair_review = verify_review()
    raw_by_id = {row["item_id"]: row for row in raw_inventory}
    raw_rows = [{**raw_by_id[row["item_id"]], **row} for row in raw_review]
    raw_counts = Counter(row["review_label"] for row in raw_rows)
    actual_numerator = BASE_PROPOSALS + raw_counts["MISSING_REAL_HAND"]
    actual = {
        "base": {"numerator": BASE_PROPOSALS, "denominator": VISIBLE_HANDS, "rate": BASE_PROPOSALS / VISIBLE_HANDS},
        "independently_validated_A_true": raw_counts["MISSING_REAL_HAND"],
        "raw_A_label_counts": dict(raw_counts),
        "actual_raw_recovery_capacity": {"numerator": actual_numerator, "denominator": VISIBLE_HANDS, "rate": actual_numerator / VISIBLE_HANDS},
        "required_numerator": TARGET_PROPOSALS, "reaches_98_percent_gate": actual_numerator >= TARGET_PROPOSALS,
    }
    atomic_json(OUT / "p4c3b_actual_recovery_capacity.json", actual)

    review_by_id = {row["pair_id"]: row for row in pair_review}
    pair_rows: list[dict[str, Any]] = []
    for source in pair_manifest:
        review = review_by_id[source["pair_id"]]
        pair_rows.append({**pair_features(source), "truth_label": review["review_label"], "reviewed_utc": review["reviewed_utc"], "revision_count": review["revision_count"]})
    split = freeze_split(pair_rows)
    for row in pair_rows:
        row["split"] = split["assignments"][row["pair_id"]]
    atomic_json(OUT / "p4c3b_pair_split.json", split)
    atomic_csv(OUT / "p4c3b_pair_features.csv", pair_rows)

    # One preregistered transparent family, fitted from development only.
    center_feature = "normalized_center_distance"
    landmark_feature = "median_corresponding_distance_normalized"
    development = [row for row in pair_rows if row["split"] == "DEVELOPMENT" and row["truth_label"] != "AMBIGUOUS"]
    validation = [row for row in pair_rows if row["split"] == "VALIDATION" and row["truth_label"] != "AMBIGUOUS"]
    dev_same = [row for row in development if row["truth_label"] == "SAME_PHYSICAL_HAND"]
    dev_distinct = [row for row in development if row["truth_label"] == "DISTINCT_PHYSICAL_HANDS"]

    def threshold(feature: str) -> tuple[float, dict[str, Any]]:
        same = [float(row[feature]) for row in dev_same]
        distinct = [float(row[feature]) for row in dev_distinct]
        same_p95 = float(np.quantile(same, .95))
        distinct_p02 = float(np.quantile(distinct, .02))
        if same_p95 < distinct_p02:
            value = (same_p95 + distinct_p02) / 2
            derivation = "midpoint between development SAME p95 and DISTINCT p02 separation gap"
        else:
            value = same_p95
            derivation = "development SAME p95 because class tails overlap"
        return value, {"same": quantiles(same), "distinct": quantiles(distinct), "derivation": derivation}

    center_threshold, center_dev = threshold(center_feature)
    landmark_threshold, landmark_dev = threshold(landmark_feature)
    rule = {
        "identity": "P4C3B_SYMMETRIC_TWO_DISTANCE_AND_RULE_V1",
        "prediction": f"DUPLICATE iff {center_feature} <= {center_threshold:.17g} AND {landmark_feature} <= {landmark_threshold:.17g}",
        "features": [center_feature, landmark_feature], "symmetric_candidate_order": True,
        "center_threshold": center_threshold, "landmark_threshold": landmark_threshold,
        "threshold_derivation": {center_feature: center_dev, landmark_feature: landmark_dev},
        "frozen_from": "DEVELOPMENT_ONLY", "validation_opened_after_rule_write": True,
        "no_anatomical_or_native_slot_input": True, "no_model": True, "no_threshold_sweep": True,
    }
    atomic_json(OUT / "p4c3b_dedup_rule.json", rule)
    frozen_rule_sha = sha256(OUT / "p4c3b_dedup_rule.json")

    scored: list[dict[str, Any]] = []
    for row in pair_rows:
        predicted_duplicate = float(row[center_feature]) <= center_threshold and float(row[landmark_feature]) <= landmark_threshold
        truth_binary = "" if row["truth_label"] == "AMBIGUOUS" else "DUPLICATE" if row["truth_label"] == "SAME_PHYSICAL_HAND" else "DISTINCT"
        outcome = "EXCLUDED_AMBIGUOUS" if not truth_binary else "TP" if truth_binary == "DUPLICATE" and predicted_duplicate else "FN_FALSE_SPLIT" if truth_binary == "DUPLICATE" else "FP_FALSE_MERGE" if predicted_duplicate else "TN"
        scored.append({**row, "predicted_class": "DUPLICATE" if predicted_duplicate else "DISTINCT", "truth_binary": truth_binary, "outcome": outcome, "dedup_rule_sha256": frozen_rule_sha})
    atomic_csv(OUT / "p4c3b_dedup_validation.csv", scored)
    validation_scored = [row for row in scored if row["split"] == "VALIDATION" and row["truth_binary"]]
    counts = Counter(row["outcome"] for row in validation_scored)
    tp, fn, fp, tn = counts["TP"], counts["FN_FALSE_SPLIT"], counts["FP_FALSE_MERGE"], counts["TN"]
    duplicate_recall = tp / (tp + fn) if tp + fn else None
    distinct_preservation = tn / (tn + fp) if tn + fp else None
    precision = tp / (tp + fp) if tp + fp else None
    f1 = 2 * precision * duplicate_recall / (precision + duplicate_recall) if precision is not None and duplicate_recall is not None and precision + duplicate_recall else None
    composite_scores = [max(float(row[center_feature]) / max(center_threshold, 1e-8), float(row[landmark_feature]) / max(landmark_threshold, 1e-8)) for row in validation]
    auc_value = auc([1 if row["truth_label"] == "SAME_PHYSICAL_HAND" else 0 for row in validation], composite_scores)
    validation_metrics = {
        "rows": len(validation_scored), "confusion": {"tp_duplicate": tp, "fn_false_split": fn, "fp_false_merge": fp, "tn_distinct": tn},
        "duplicate_recall": duplicate_recall, "distinct_preservation": distinct_preservation,
        "precision": precision, "f1": f1, "roc_auc_diagnostic": auc_value,
        "duplicate_gate_pass": duplicate_recall is not None and duplicate_recall >= .95,
        "distinct_gate_pass": distinct_preservation is not None and distinct_preservation >= .98,
    }
    feature_distributions: dict[str, Any] = {}
    for feature in (center_feature, landmark_feature):
        feature_distributions[feature] = {}
        for split_name in ("DEVELOPMENT", "VALIDATION"):
            feature_distributions[feature][split_name] = {}
            for truth_name in ("SAME_PHYSICAL_HAND", "DISTINCT_PHYSICAL_HANDS"):
                values = [float(row[feature]) for row in pair_rows if row["split"] == split_name and row["truth_label"] == truth_name]
                feature_distributions[feature][split_name][truth_name] = quantiles(values)

    capacity_pass = actual_numerator >= TARGET_PROPOSALS
    dedup_pass = validation_metrics["duplicate_gate_pass"] and validation_metrics["distinct_gate_pass"]
    if not capacity_pass:
        classification = "RAW_CANDIDATES_INSUFFICIENT_TARGETED_RECOVERY_REQUIRED"
        path = "PATH_2"
        slot_identity = "RETAIN"
        rationale = "Only independently confirmed missing-hand candidates count; actual capacity remains below 98%."
    elif not dedup_pass:
        classification = "RAW_CANDIDATES_USEFUL_ASSOCIATION_UNSOLVED"
        path = "PATH_3"
        slot_identity = "RETAIN"
        rationale = "Raw recovery reaches 98%, but geometry-only physical-instance deduplication fails one or both safety gates."
    else:
        classification = "RAW_INSTANCE_PIPELINE_VALIDATED"
        path = "PATH_1"
        slot_identity = "DEMOTE_TO_METADATA"
        rationale = "Independent raw recovery and symmetric geometry-only deduplication both pass their frozen gates."
    decision = {
        "classification": classification, "path": path, "rationale": rationale,
        "anatomical_slot_as_primary_identity": slot_identity,
        "capacity_gate_pass": capacity_pass, "deduplication_gates_pass": dedup_pass,
        "no_implementation_authorized": True,
    }
    atomic_json(OUT / "p4c3b_architecture_decision.json", decision)
    result = {
        "status": "P4C3B_COMPLETE", "v2_verified": True, "raw_A_reviewed": len(raw_rows),
        "raw_A_labels": dict(raw_counts), "actual_recovery": actual,
        "independent_pair_truth": dict(Counter(row["truth_label"] for row in pair_rows)),
        "split": {"development_rows": sum(row["split"] == "DEVELOPMENT" for row in pair_rows),
            "validation_rows": sum(row["split"] == "VALIDATION" for row in pair_rows),
            "signer_separated": True, "development_signers": len(split["development_signers"]),
            "validation_signers": len(split["validation_signers"])},
        "deduplication_validation": validation_metrics, "feature_distributions": feature_distributions,
        "decision": decision,
        "models_rerun": False, "models_trained": False,
    }
    atomic_json(OUT / "p4c3b_result.json", result)

    pair_counts = Counter(row["truth_label"] for row in pair_rows)
    report = f"""# P4-C3B Physical Hand Instance Validation Result

## Decision

**`P4C3B_COMPLETE` — `{classification}` (`{path}`).**

V2 and all 121 overlay identities were verified. Four explicit undos were preserved in the edit
journal and exactly match the four revision counters; there were no silent edits. P4-C3A's
duplicate labels were geometry-derived and were not used as independent truth.

## Part A — independent raw-candidate validation

- Reviewed category-A candidates: **21/21**
- Missing real hand: **{raw_counts['MISSING_REAL_HAND']}**
- Duplicate existing hand: **{raw_counts['DUPLICATE_EXISTING_HAND']}**
- Other false region: **{raw_counts['OTHER_FALSE_REGION']}**
- Ambiguous: **{raw_counts['AMBIGUOUS']}**
- Actual proposal capacity: **{actual_numerator}/444 = {actual_numerator/444:.2%}**
- Required capacity: **436/444**
- Capacity gate: **{'PASS' if capacity_pass else 'FAIL'}**

The earlier 440/444 theoretical ceiling is not confirmed: coherent raw geometry frequently points
to an already represented hand or another region.

## Part B — independent same-vs-distinct pair truth

- SAME: **{pair_counts['SAME_PHYSICAL_HAND']}**
- DISTINCT: **{pair_counts['DISTINCT_PHYSICAL_HANDS']}**
- AMBIGUOUS: **{pair_counts['AMBIGUOUS']}** (excluded from binary fitting/scoring)
- Split: **signer-separated**, {result['split']['development_rows']} development / {result['split']['validation_rows']} validation rows

One symmetric rule family was frozen from development only: duplicate when both normalized center
distance and normalized median corresponding-landmark distance fall below their frozen thresholds.
Candidate ordering and DWPose/anatomical left-right labels are not inputs.

### First and only validation result

- Duplicate recall: **{duplicate_recall:.2%}** — {'PASS' if validation_metrics['duplicate_gate_pass'] else 'FAIL'} (required 95%)
- Distinct-hand preservation: **{distinct_preservation:.2%}** — {'PASS' if validation_metrics['distinct_gate_pass'] else 'FAIL'} (required 98%)
- False merges: **{fp}**
- False splits: **{fn}**
- Precision / F1: **{precision:.2%} / {f1:.2%}**
- Diagnostic ROC AUC: **{auc_value:.4f}**

Full development/validation class-conditional feature distributions (min, p10, p50, p90, p95,
max) are frozen in `p4c3b_result.json`; every item-level value is preserved in
`p4c3b_pair_features.csv`.

## Architecture conclusion

Selected **`{path}`**: {rationale}

`ANATOMICAL_SLOT_AS_PRIMARY_IDENTITY = {slot_identity}`. This does not validate RGB authenticity,
recognition, temporal accuracy, Android runtime, or a recovery model. No detector/model was run or
trained, and no deduplication, recovery, RGB verifier, Android, recognition, or S4-S7 component was
implemented.
"""
    atomic_text(OUT / "P4C3B_PHYSICAL_INSTANCE_VALIDATION_RESULT.md", report)
    tracked = [path for path in OUT.iterdir() if path.is_file() and path.name != "p4c3b_artifact_hash_manifest.json"]
    atomic_json(OUT / "p4c3b_artifact_hash_manifest.json", {
        "status": "P4C3B_FINAL_FROZEN", "created_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": {path.name: sha256(path) for path in sorted(tracked)},
        "source_hashes": {"v2": sha256(V2), "raw_review": sha256(RAW_REVIEW), "pair_review": sha256(PAIR_REVIEW),
            "raw_inventory": sha256(RAW_INVENTORY), "pair_manifest": sha256(PAIR_MANIFEST)},
        "code_hashes": {"finalizer": sha256(Path(__file__)),
            "review_tool": sha256(ROOT / "eval/runtime_diagnostics/p4c3b_physical_instance_review.py"),
            "preparer": sha256(ROOT / "eval/runtime_diagnostics/p4c3b_prepare_review.py"),
            "finalizer_tests": sha256(ROOT / "tests/test_p4c3b_finalize.py"),
            "review_tests": sha256(ROOT / "tests/test_p4c3b_physical_instance_review.py")},
    })
    return result


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True, allow_nan=False))
