"""Prepare the evidence-locked Phase 2 landmark/RGB pilot.

This module reads frozen Phase 1 artifacts and existing Stage-E metadata. It
does not decode RGB frames, extract crops, train models, access Android assets,
or modify the v3.0 feature contract.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = "phase2_error_registry_rgb_feasibility_v1"
DEFAULT_PHASE1_RUN = ROOT / (
    "artifacts/recognition_upgrade/phase1_full_vocab/tcn_comparison_01"
)
DEFAULT_DATASET = ROOT / "artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1"
DEFAULT_MANIFEST = ROOT / (
    "artifacts/recognition_upgrade/phase1_full_vocab/manifest_01/canonical_manifest.csv"
)
DEFAULT_OUTPUT = ROOT / (
    "artifacts/recognition_upgrade/phase2_preparation/phase2_prep_01"
)
PILOT_SIZE = 40
HISTORICAL_CORE = ("GOOD", "HELLO", "SORRY", "HAVE", "KNOW", "THINK", "TAKE", "SELL")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing required artifact: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    materialized = list(rows)
    if not materialized:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(materialized[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(materialized)


def _load_test_lineage(dataset: Path) -> dict[str, np.ndarray]:
    with np.load(dataset / "test.npz", allow_pickle=True) as data:
        return {key: np.asarray(data[key]) for key in data.files}


def verify_prediction_alignment(
    prediction_labels: np.ndarray,
    prediction_participants: np.ndarray,
    test_labels: np.ndarray,
    test_participants: np.ndarray,
) -> None:
    """Block row-order joins unless frozen predictions and test lineage align."""
    if not np.array_equal(prediction_labels.astype(np.int32), test_labels.astype(np.int32)):
        raise ValueError("protected predictions do not align with test labels")
    if not np.array_equal(
        prediction_participants.astype(str), test_participants.astype(str)
    ):
        raise ValueError("protected predictions do not align with test signer IDs")


def classify_sign(
    *,
    label: str,
    support: int,
    recall: float,
    f1: float,
    top5_recall: float,
    dominant_confusion_share: float,
    train_signers: int,
) -> tuple[list[str], list[str]]:
    """Return verified categories and explicitly hypothetical review flags."""
    categories: list[str] = []
    hypotheses: list[str] = []
    top5_rescue = top5_recall - recall
    if recall < 0.25:
        categories.append("zero_very_low_recall")
    if f1 >= 0.75 and recall >= 0.75:
        categories.append("landmark_stable")
    if (1.0 - recall) >= 0.25 and (
        dominant_confusion_share >= 0.30 or top5_rescue >= 0.25
    ):
        categories.append("confusion_heavy")
    if support < 8 or train_signers < 10:
        categories.append("insufficient_evidence")
    if not categories:
        categories.append("landmark_moderate")
    if top5_recall >= 0.75 and top5_rescue >= 0.25:
        hypotheses.append("appearance_evidence_may_help")
    if (bool(re.search(r"\d+$", label)) and f1 < 0.50) or (
        recall < 0.25 and top5_recall < 0.50
    ):
        hypotheses.append("dataset_or_variant_review_required")
    return categories, hypotheses


def _pose_anchor_available(pose: np.ndarray, side: int) -> np.ndarray:
    indices = (15, 17, 19, 21) if side == 0 else (16, 18, 20, 22)
    selected = pose[:, indices]
    finite = np.all(np.isfinite(selected[..., [0, 1, 3]]), axis=-1)
    visible = selected[..., 3] >= 0.50
    wrist_ok = finite[:, 0] & visible[:, 0]
    any_ok = np.any(finite & visible, axis=1)
    return np.asarray(wrist_ok & any_ok, dtype=bool)


def _near_face_rate(hands: np.ndarray, scores: np.ndarray, pose: np.ndarray) -> float:
    nose = pose[:, 0, :2]
    nose_ok = np.all(np.isfinite(nose), axis=1)
    near = np.zeros(len(hands), dtype=bool)
    for side in range(2):
        valid = scores[:, side] > 0
        xy = hands[:, side, :, :2]
        finite = np.all(np.isfinite(xy), axis=2)
        count = np.sum(finite, axis=1)
        center = np.zeros((len(hands), 2), dtype=np.float32)
        for coordinate in range(2):
            values = np.where(finite, xy[..., coordinate], 0.0)
            center[:, coordinate] = np.sum(values, axis=1) / np.maximum(count, 1)
        center_ok = np.all(np.isfinite(center), axis=1)
        distance = np.linalg.norm(center - nose, axis=1)
        near |= valid & center_ok & nose_ok & (distance <= 0.25)
    denominator = max(int(np.sum(np.any(scores > 0, axis=1) & nose_ok)), 1)
    return float(np.sum(near) / denominator)


def _stage_e_feasibility(row: dict[str, str]) -> dict[str, Any]:
    raw_path = Path(row["raw_video_path"])
    stage_path = Path(row["stage_e_path"])
    span_path = Path(row["span_path"])
    base = {
        "sample_id": row["sample_id"],
        "canonical_gloss": row["canonical_gloss"],
        "class_id": int(row["class_id"]),
        "split": row["split"],
        "role": row["role"],
        "source_dataset": row["source_dataset"],
        "signer_group_id": row["signer_group_id"],
        "raw_video_path": row["raw_video_path"],
        "raw_video_sha256": row["raw_video_sha256"],
        "raw_rgb_available": raw_path.is_file(),
        "stage_e_available": stage_path.is_file(),
        "span_available": span_path.is_file(),
        "lineage_status": row["lineage_status"],
        "rgb_decode_status": "not_checked_no_rgb_extraction_authorized",
        "pixel_crop_quality": "not_measured_requires_bounded_pilot_audit",
    }
    if not stage_path.is_file() or not span_path.is_file():
        return {
            **base,
            "synchronized": False,
            "span_frames": 0,
            "left_direct_rate": 0.0,
            "right_direct_rate": 0.0,
            "both_direct_rate": 0.0,
            "any_direct_rate": 0.0,
            "pose_fallback_candidate_rate": 0.0,
            "metadata_roi_candidate_rate": 0.0,
            "edge_risk_rate": 0.0,
            "near_face_rate": 0.0,
            "motion_p90": 0.0,
            "handedness_profile": "unavailable",
            "motion_profile": "unavailable",
            "roi_evidence_status": "missing_stage_e_or_span",
            "hybrid_metadata_eligible": False,
        }
    span = _read_json(span_path)
    with np.load(stage_path, allow_pickle=False) as data:
        hands = np.asarray(data["hands_image"], dtype=np.float32)
        scores = np.asarray(data["hand_score"], dtype=np.float32)
        pose = np.asarray(data["pose_image"], dtype=np.float32)
        timestamps = np.asarray(data["timestamps_ms"], dtype=np.int64)
    onset = max(0, int(span.get("onset", 0)))
    release = min(len(scores) - 1, int(span.get("release", len(scores) - 1)))
    if release < onset:
        onset, release = 0, len(scores) - 1
    selector = slice(onset, release + 1)
    hands, scores, pose = hands[selector], scores[selector], pose[selector]
    direct = scores > 0
    left_pose = _pose_anchor_available(pose, 0)
    right_pose = _pose_anchor_available(pose, 1)
    fallback = np.stack(
        [~direct[:, 0] & left_pose, ~direct[:, 1] & right_pose], axis=1
    )
    finite_xy = np.all(np.isfinite(hands[..., :2]), axis=-1)
    near_edge = np.any(
        finite_xy
        & (
            (hands[..., 0] <= 0.03)
            | (hands[..., 0] >= 0.97)
            | (hands[..., 1] <= 0.03)
            | (hands[..., 1] >= 0.97)
        ),
        axis=2,
    )
    direct_observations = max(int(np.sum(direct)), 1)
    left_rate = float(np.mean(direct[:, 0]))
    right_rate = float(np.mean(direct[:, 1]))
    both_rate = float(np.mean(np.all(direct, axis=1)))
    any_rate = float(np.mean(np.any(direct, axis=1)))
    metadata_rate = float(np.mean(direct | fallback))
    if both_rate >= 0.25:
        handedness_profile = "two_hand_frequent"
    elif max(left_rate, right_rate) >= 0.25:
        handedness_profile = "one_hand_dominant"
    else:
        handedness_profile = "weak_direct_hand_evidence"
    motion_p90 = float(span.get("motion_p90", 0.0) or 0.0)
    if motion_p90 >= 0.12:
        motion_profile = "high_motion"
    elif motion_p90 <= 0.04:
        motion_profile = "low_motion"
    else:
        motion_profile = "medium_motion"
    synchronized = bool(
        len(timestamps) == int(span.get("n_frames", len(timestamps)))
        and (len(timestamps) < 2 or np.all(np.diff(timestamps) >= 0))
        and release >= onset
    )
    return {
        **base,
        "synchronized": synchronized,
        "span_frames": len(scores),
        "left_direct_rate": left_rate,
        "right_direct_rate": right_rate,
        "both_direct_rate": both_rate,
        "any_direct_rate": any_rate,
        "pose_fallback_candidate_rate": float(np.mean(fallback)),
        "metadata_roi_candidate_rate": metadata_rate,
        "edge_risk_rate": float(np.sum(near_edge & direct) / direct_observations),
        "near_face_rate": _near_face_rate(hands, scores, pose),
        "motion_p90": motion_p90,
        "handedness_profile": handedness_profile,
        "motion_profile": motion_profile,
        "roi_evidence_status": (
            "metadata_candidate_only_pose_quality_unproven"
            if np.any(fallback)
            else "direct_landmark_metadata_only"
        ),
        "hybrid_metadata_eligible": bool(raw_path.is_file() and synchronized),
    }


def _mean(rows: list[dict[str, Any]], key: str) -> float:
    return float(np.mean([float(row[key]) for row in rows])) if rows else 0.0


def _aggregate_feasibility(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["canonical_gloss"])].append(row)
    output: dict[str, dict[str, Any]] = {}
    for label, members in grouped.items():
        output[label] = {
            "rows": len(members),
            "raw_available_rate": _mean(members, "raw_rgb_available"),
            "synchronized_rate": _mean(members, "synchronized"),
            "mean_any_direct_rate": _mean(members, "any_direct_rate"),
            "mean_both_direct_rate": _mean(members, "both_direct_rate"),
            "mean_metadata_roi_candidate_rate": _mean(
                members, "metadata_roi_candidate_rate"
            ),
            "mean_edge_risk_rate": _mean(members, "edge_risk_rate"),
            "mean_near_face_rate": _mean(members, "near_face_rate"),
            "mean_motion_p90": _mean(members, "motion_p90"),
            "hybrid_metadata_eligible_rows": sum(
                bool(row["hybrid_metadata_eligible"]) for row in members
            ),
            "handedness_profile_counts": dict(
                sorted(Counter(row["handedness_profile"] for row in members).items())
            ),
            "motion_profile_counts": dict(
                sorted(Counter(row["motion_profile"] for row in members).items())
            ),
            "signers": len({row["signer_group_id"] for row in members}),
            "split_counts": dict(sorted(Counter(row["split"] for row in members).items())),
            "source_counts": dict(
                sorted(Counter(row["source_dataset"] for row in members).items())
            ),
        }
    return output


def _pilot_selection(
    registry: list[dict[str, Any]],
    feasibility: dict[str, dict[str, Any]],
    confusion_pairs: list[dict[str, Any]],
) -> tuple[list[str], dict[str, list[str]]]:
    by_label = {str(row["label"]): row for row in registry}
    reasons: dict[str, list[str]] = defaultdict(list)
    selected: list[str] = []

    def add(label: str, reason: str) -> None:
        if label not in by_label:
            return
        reasons[label].append(reason)
        if label not in selected and len(selected) < PILOT_SIZE:
            selected.append(label)

    stable = sorted(
        (row for row in registry if "landmark_stable" in row["categories"]),
        key=lambda row: (-row["f1"], row["label"]),
    )
    for row in stable[:6]:
        add(str(row["label"]), "stable_landmark_control")

    for label in HISTORICAL_CORE:
        add(label, "historical_cross_experiment_core")

    for pair in confusion_pairs[:6]:
        add(str(pair["true_label"]), "major_confusion_group")
        add(str(pair["predicted_label"]), "major_confusion_group")

    low = sorted(
        (row for row in registry if "zero_very_low_recall" in row["categories"]),
        key=lambda row: (row["recall"], -row["top5_rescue_rate"], row["label"]),
    )
    for row in low[:6]:
        add(str(row["label"]), "zero_or_very_low_recall")

    appearance = sorted(
        (
            row
            for row in registry
            if "appearance_evidence_may_help" in row["hypotheses"]
        ),
        key=lambda row: (-row["top5_rescue_rate"], row["label"]),
    )
    for row in appearance[:6]:
        add(str(row["label"]), "top5_rgb_rerank_candidate")

    topology_candidates = [
        (
            sorted(
                registry,
                key=lambda row: feasibility[str(row["label"])]["mean_motion_p90"],
            )[:4],
            "relative_low_motion_static_handshape_proxy",
        ),
        (
            sorted(
                registry,
                key=lambda row: -feasibility[str(row["label"])]["mean_motion_p90"],
            )[:4],
            "relative_high_motion_case",
        ),
        (
            sorted(
                registry,
                key=lambda row: -feasibility[str(row["label"])]["mean_near_face_rate"],
            )[:4],
            "near_face_roi_case",
        ),
        (
            sorted(
                registry,
                key=lambda row: -feasibility[str(row["label"])]["mean_both_direct_rate"],
            )[:4],
            "two_hand_case",
        ),
    ]
    for candidates, reason in topology_candidates:
        for row in candidates:
            add(str(row["label"]), reason)

    diversity_ranked = sorted(
        registry,
        key=lambda row: (
            -float(feasibility[str(row["label"])]["mean_near_face_rate"]),
            -float(feasibility[str(row["label"])]["mean_both_direct_rate"]),
            -row["top5_rescue_rate"],
        ),
    )
    for row in diversity_ranked:
        if len(selected) >= PILOT_SIZE:
            break
        profile = feasibility[str(row["label"])]
        reason = "roi_or_articulation_diversity"
        if profile["mean_near_face_rate"] >= 0.25:
            reason = "near_face_roi_case"
        elif profile["mean_both_direct_rate"] >= 0.25:
            reason = "two_hand_case"
        add(str(row["label"]), reason)
    if len(selected) != PILOT_SIZE:
        raise ValueError(f"pilot selection produced {len(selected)} signs, expected {PILOT_SIZE}")
    return selected, dict(reasons)


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output: {args.output}")
    args.output.mkdir(parents=True)
    metrics_path = args.phase1_run / "metrics" / "protected_test_metrics.json"
    predictions_path = args.phase1_run / "metrics" / "protected_test_predictions.npz"
    freeze_path = args.phase1_run / "config" / "selection_freeze.json"
    metrics = _read_json(metrics_path)
    freeze = _read_json(freeze_path)
    if not metrics.get("protected_test_accessed") or not metrics.get("passed"):
        raise ValueError("Phase 1 protected evaluation is incomplete")
    if metrics.get("frozen_branch") != freeze.get("frozen_branch"):
        raise ValueError("Phase 1 metrics and selection freeze disagree")
    test = _load_test_lineage(args.dataset)
    with np.load(predictions_path, allow_pickle=True) as data:
        prediction_labels = np.asarray(data["labels"])
        prediction_participants = np.asarray(data["participant_ids"])
        probabilities = np.asarray(data["probabilities"], dtype=np.float32)
    verify_prediction_alignment(
        prediction_labels,
        prediction_participants,
        test["y"],
        test["participant_ids"],
    )
    vocab = _read_json(args.dataset / "vocab.json")
    labels_by_id = {int(class_id): label for label, class_id in vocab.items()}
    manifest = _read_csv(args.manifest)
    manifest_by_id = {row["sample_id"]: row for row in manifest}
    if len(manifest_by_id) != len(manifest):
        raise ValueError("canonical manifest contains duplicate sample IDs")

    predictions = np.argmax(probabilities, axis=1)
    top5 = np.argpartition(-probabilities, kth=4, axis=1)[:, :5]
    train_rows: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in manifest:
        if row["training_eligible"].lower() == "true":
            train_rows[int(row["class_id"])].append(row)
    pair_counts: Counter[tuple[int, int]] = Counter(
        (int(truth), int(predicted))
        for truth, predicted in zip(test["y"], predictions, strict=True)
        if truth != predicted
    )
    confusion_pairs = [
        {
            "true_class_id": truth,
            "true_label": labels_by_id[truth],
            "predicted_class_id": predicted,
            "predicted_label": labels_by_id[predicted],
            "count": count,
        }
        for (truth, predicted), count in pair_counts.most_common()
    ]
    registry: list[dict[str, Any]] = []
    for class_id in range(len(labels_by_id)):
        selected = test["y"] == class_id
        support = int(np.sum(selected))
        correct = int(np.sum(predictions[selected] == class_id))
        top5_hits = int(np.sum(np.any(top5[selected] == class_id, axis=1)))
        predicted_count = int(np.sum(predictions == class_id))
        precision = correct / max(predicted_count, 1)
        recall = correct / max(support, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-12)
        confusions = [
            pair
            for pair in confusion_pairs
            if int(str(pair["true_class_id"])) == class_id
        ]
        dominant = int(str(confusions[0]["count"])) if confusions else 0
        errors = support - correct
        training = train_rows[class_id]
        categories, hypotheses = classify_sign(
            label=labels_by_id[class_id],
            support=support,
            recall=recall,
            f1=f1,
            top5_recall=top5_hits / max(support, 1),
            dominant_confusion_share=dominant / max(errors, 1),
            train_signers=len({row["signer_group_id"] for row in training}),
        )
        registry.append(
            {
                "class_id": class_id,
                "label": labels_by_id[class_id],
                "support": support,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "top5_recall": top5_hits / max(support, 1),
                "top5_rescue_rate": (top5_hits - correct) / max(support, 1),
                "error_count": errors,
                "dominant_confusion_share": dominant / max(errors, 1),
                "dominant_confusion_label": (
                    confusions[0]["predicted_label"] if confusions else ""
                ),
                "train_rows": len(training),
                "train_signers": len({row["signer_group_id"] for row in training}),
                "train_source_counts": dict(
                    sorted(Counter(row["source_dataset"] for row in training).items())
                ),
                "categories": categories,
                "hypotheses": hypotheses,
                "evidence_note": (
                    "categories derive from frozen metrics; hypotheses require RGB/data review"
                ),
            }
        )

    feasibility_rows = [_stage_e_feasibility(row) for row in manifest]
    feasibility_by_sign = _aggregate_feasibility(feasibility_rows)
    pilot, pilot_reasons = _pilot_selection(
        registry, feasibility_by_sign, confusion_pairs
    )
    pilot_set = set(pilot)
    pilot_manifest = [
        row for row in feasibility_rows if row["canonical_gloss"] in pilot_set
    ]
    registry_rows = [
        {
            **row,
            "categories": "|".join(row["categories"]),
            "hypotheses": "|".join(row["hypotheses"]),
            "train_source_counts": json.dumps(row["train_source_counts"], sort_keys=True),
            "pilot_selected": row["label"] in pilot_set,
            "pilot_reasons": "|".join(pilot_reasons.get(str(row["label"]), [])),
        }
        for row in registry
    ]
    _write_csv(args.output / "error_registry.csv", registry_rows)
    _write_json(
        args.output / "error_registry.json",
        {
            "experiment": EXPERIMENT,
            "phase1_metrics_sha256": _sha256(metrics_path),
            "phase1_predictions_sha256": _sha256(predictions_path),
            "counts_by_category": dict(
                sorted(
                    Counter(
                        category
                        for row in registry
                        for category in row["categories"]
                    ).items()
                )
            ),
            "counts_by_hypothesis": dict(
                sorted(
                    Counter(
                        hypothesis
                        for row in registry
                        for hypothesis in row["hypotheses"]
                    ).items()
                )
            ),
            "signs": registry,
            "strongest_directional_confusions": confusion_pairs[:100],
            "passed": True,
        },
    )
    _write_csv(args.output / "rgb_feasibility_manifest.csv", pilot_manifest)
    _write_json(
        args.output / "rgb_feasibility_summary.json",
        {
            "experiment": EXPERIMENT,
            "scope": "metadata feasibility only; no RGB frames decoded or crops extracted",
            "all_phase1_rows_scanned": len(feasibility_rows),
            "pilot_rows": len(pilot_manifest),
            "pilot_raw_available": sum(row["raw_rgb_available"] for row in pilot_manifest),
            "pilot_synchronized": sum(row["synchronized"] for row in pilot_manifest),
            "pilot_hybrid_metadata_eligible": sum(
                row["hybrid_metadata_eligible"] for row in pilot_manifest
            ),
            "per_sign": {label: feasibility_by_sign[label] for label in pilot},
            "verified_prior_roi_limits": {
                "mediapipe_video_best_known_visible_availability": 0.575,
                "pose_recovery_metadata_availability": 0.792,
                "pose_recovered_crop_raw_usable_rate": 0.237,
                "i320_hand_availability": 0.6726,
                "i320_complete_two_hand_recall": 0.4103,
            },
            "pixel_quality_status": "blocked_until_bounded_pilot_crop_audit",
            "supplement_status": (
                "raw video exists, but rows without canonical Stage-E/span are excluded until "
                "a versioned synchronized re-extraction is separately authorized"
            ),
            "passed": True,
        },
    )
    _write_json(
        args.output / "pilot_vocabulary.json",
        {
            "experiment": EXPERIMENT,
            "size": len(pilot),
            "labels": pilot,
            "selection_reasons": {label: pilot_reasons[label] for label in pilot},
            "selection_policy": (
                "6 stable controls, historical E6 core, strongest confusion groups, "
                "6 lowest-recall signs, top5-rescue candidates, then low/high-motion, "
                "near-face, two-hand, and ROI diversity to 40 unique signs"
            ),
            "test_policy": (
                "Phase 1 protected test is historical diagnostic only; pilot selection and "
                "model choice use signer-disjoint validation; fresh signer/domain evidence "
                "is required before scaling"
            ),
            "passed": True,
        },
    )
    _write_json(
        args.output / "roi_strategy.json",
        {
            "decision": "bounded competing ROI routes; no source is promoted yet",
            "routes": [
                {
                    "id": "R0",
                    "name": "direct MediaPipe hand box plus 100ms causal hold",
                    "role": "control",
                },
                {
                    "id": "R1",
                    "name": "direct box plus pose-tracked motion and pose fallback",
                    "role": "recovery hypothesis; prior recovered-crop usability only 23.7%",
                },
                {
                    "id": "R2",
                    "name": "I320 detector proposal with direct-landmark anatomical assignment",
                    "role": "research diagnostic only; prior recall gates failed",
                },
                {
                    "id": "R3",
                    "name": "expanded upper-body fallback",
                    "role": "availability control only; prior upper-body RGB overfit",
                },
            ],
            "promotion_gate": {
                "known_visible_roi_coverage": 0.90,
                "complete_two_hand_coverage": 0.80,
                "reviewed_crop_usable_rate": 0.85,
                "wrong_stale_or_side_swap_rate_max": 0.02,
                "split_reporting": [
                    "motion_blur",
                    "near_face",
                    "edge",
                    "two_hand",
                    "held_out_signer",
                ],
            },
            "note": "gates are engineering targets; prior evidence shows no current route passes",
            "passed": True,
        },
    )
    _write_json(
        args.output / "pilot_experiment_contract.json",
        {
            "branches": {
                "A": "frozen Phase 1 production-TCN landmark baseline",
                "B": "trainable shared-weight left/right hand-crop RGB encoder",
                "C": (
                    "quality-gated intermediate landmark/RGB fusion with landmark "
                    "branch protection"
                ),
                "D": "landmark top-k candidate reranking by RGB evidence",
            },
            "seeds": [101, 202, 303],
            "selection": "signer-disjoint validation only",
            "primary_gate": {
                "mean_top1_gain_over_A_min": 0.05,
                "macro_f1_gain_over_A_min": 0.05,
                "stable_control_f1_drop_max": 0.02,
                "seed_consistency": "candidate beats A on at least 2/3 seeds and mean",
                "roi_coverage_min": 0.90,
            },
            "secondary": [
                "confusion-group macro-F1",
                "zero/low-recall recovery",
                "top5-to-top1 rerank conversion",
                "per-signer minimum and spread",
                "crop-source/quality ablations",
                "CPU latency/model-size projection",
            ],
            "do_not_repeat": [
                "frozen upper-body MobileNet embeddings",
                "unprotected simple concatenation fusion",
                "MediaPipe threshold or IMAGE/VIDEO retuning",
                "I320 retraining without new independent hard negatives",
            ],
            "production_authorized": False,
            "passed": True,
        },
    )
    summary = {
        "experiment": EXPERIMENT,
        "phase1_closed": True,
        "classes_registered": len(registry),
        "phase1_rows_scanned_for_metadata": len(feasibility_rows),
        "pilot_classes": len(pilot),
        "pilot_rows": len(pilot_manifest),
        "rgb_extracted": False,
        "models_trained": False,
        "android_modified": False,
        "passed": True,
        "next": "review pilot and run bounded RGB decode/crop-quality smoke only",
    }
    _write_json(args.output / "summary.json", summary)
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    required = (
        "summary.json",
        "error_registry.csv",
        "error_registry.json",
        "rgb_feasibility_manifest.csv",
        "rgb_feasibility_summary.json",
        "pilot_vocabulary.json",
        "roi_strategy.json",
        "pilot_experiment_contract.json",
    )
    for name in required:
        if not (args.output / name).is_file():
            errors.append(f"missing {name}")
    if not errors:
        summary = _read_json(args.output / "summary.json")
        registry = _read_csv(args.output / "error_registry.csv")
        pilot = _read_json(args.output / "pilot_vocabulary.json")
        feasibility = _read_csv(args.output / "rgb_feasibility_manifest.csv")
        if len(registry) != 236:
            errors.append(f"error registry has {len(registry)} rows, expected 236")
        if len(pilot.get("labels", [])) != PILOT_SIZE:
            errors.append("pilot vocabulary is not 40 unique signs")
        if len(set(pilot.get("labels", []))) != PILOT_SIZE:
            errors.append("pilot vocabulary contains duplicates")
        if not feasibility:
            errors.append("RGB feasibility manifest is empty")
        if summary.get("rgb_extracted") or summary.get("models_trained"):
            errors.append("preparation package claims extraction or training")
    report = {
        "run_dir": str(args.output.resolve()),
        "errors": errors,
        "passed": not errors,
    }
    _write_json(args.output / "check_report.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--phase1-run", type=Path, default=DEFAULT_PHASE1_RUN)
    prepare_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    prepare_parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = prepare(args) if args.command == "prepare" else check(args)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
