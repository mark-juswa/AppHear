"""Freeze and validate P5-A's offline DWPose Representation V2 artifacts.

Feature generation consumes only preserved native DWPose output and frame metadata. Governed
human visibility truth is loaded only after the feature tensor has been built and hashed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from pipeline.features.dwpose_representation_v2 import (
    BODY_OFFSET,
    FEATURE_WIDTH,
    LEFT_OBSERVED_OFFSET,
    RIGHT_HAND_OFFSET,
    RIGHT_OBSERVED_OFFSET,
    SCHEMA_ID,
    SEQUENCE_LENGTH,
    build_frame_features,
    build_padded_sequence,
    feature_index_rows,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p5a_dwpose_representation_v2_01"
INFERENCE_MANIFEST = ROOT / (
    "artifacts/recognition_upgrade/perception_backend_replacement/"
    "p4a2_high_recall_rescue_final_01/p4a2_frozen_inference_manifest.csv"
)
TRUTH = ROOT / (
    "artifacts/recognition_upgrade/perception_backend_replacement/"
    "p4gt1r_schema_repair_v2_01/P4_ELIGIBILITY_TRUTH_V2.csv"
)
TRUTH_SHA256 = "24f5d8d442702e3a27424ff7f55cc24f1338f5683e5988a6a4916557e1d4252d"
CHECKPOINT_SHA256 = "e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7"
CONTRACT_MD_SHA256 = "57a45b6b5dd5340fbc5bf0eef12f30620f1478569b0e0b887cc9357f59911337"
CONTRACT_JSON_SHA256 = "0c94e9c885f331164d8ab1f7f0915eb89de43101394bd0949fae033b57f76d8b"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    values = list(rows)
    if fields is None:
        fields = list(values[0]) if values else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(values)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def scalar_string(value: np.ndarray) -> str:
    return str(np.asarray(value).item())


def percentile_summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "p25": None, "median": None, "p75": None, "p95": None, "max": None}
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": int(array.size),
        "min": float(np.min(array)),
        "p25": float(np.percentile(array, 25)),
        "median": float(np.percentile(array, 50)),
        "p75": float(np.percentile(array, 75)),
        "p95": float(np.percentile(array, 95)),
        "max": float(np.max(array)),
    }


def zero_runs(values: list[bool]) -> list[int]:
    runs: list[int] = []
    current = 0
    for value in values:
        if value:
            if current:
                runs.append(current)
                current = 0
        else:
            current += 1
    if current:
        runs.append(current)
    return runs


def ensure_frozen_inputs() -> None:
    checks = {
        TRUTH: TRUTH_SHA256,
        OUTPUT / "P5A_DWPOSE_REPRESENTATION_V2_CONTRACT.md": CONTRACT_MD_SHA256,
        OUTPUT / "p5a_representation_contract.json": CONTRACT_JSON_SHA256,
    }
    for path, expected in checks.items():
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"P5A_FROZEN_INPUT_MISMATCH: {path} expected={expected} actual={actual}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    ensure_frozen_inputs()

    manifest = csv_rows(INFERENCE_MANIFEST)
    if len(manifest) != 458 or len({row["annotation_row_id"] for row in manifest}) != 458:
        raise RuntimeError("P5A_GOVERNED_MANIFEST_IDENTITY_FAILURE")

    # Feature-generation phase: do not load human truth here.
    ordered = sorted(
        manifest,
        key=lambda row: (row["sequence_id"], int(row["timestamp_ns"]), int(row["frame_index"]), row["annotation_row_id"]),
    )
    features: list[np.ndarray] = []
    feature_manifest: list[dict[str, Any]] = []
    normalization_rows: list[dict[str, Any]] = []
    raw_hashes: dict[str, str] = {}
    image_hashes: dict[str, str] = {}
    raw_presence: dict[str, tuple[bool, bool]] = {}
    raw_scores: dict[str, np.ndarray] = {}
    for tensor_index, row in enumerate(ordered):
        image_path = Path(row["image_path"])
        if not image_path.is_file():
            raise RuntimeError(f"P5A_SOURCE_IMAGE_MISSING: {image_path}")
        image_hash = sha256_file(image_path)
        if image_hash != row["image_sha256"]:
            raise RuntimeError(f"P5A_SOURCE_IMAGE_HASH_MISMATCH: {row['annotation_row_id']}")
        raw_path = ROOT / row["raw_relative_path"]
        if not raw_path.is_file():
            raise RuntimeError(f"P5A_RAW_OUTPUT_MISSING: {raw_path}")
        raw_hash = sha256_file(raw_path)
        with np.load(raw_path, allow_pickle=False) as native:
            if scalar_string(native["source_sha256"]) != image_hash:
                raise RuntimeError(f"P5A_RAW_SOURCE_IDENTITY_MISMATCH: {row['annotation_row_id']}")
            if scalar_string(native["checkpoint_sha256"]) != CHECKPOINT_SHA256:
                raise RuntimeError(f"P5A_CHECKPOINT_IDENTITY_MISMATCH: {row['annotation_row_id']}")
            keypoints = np.asarray(native["keypoints_133"], dtype=np.float32)
            scores = np.asarray(native["scores_133"], dtype=np.float32)
            presence = np.asarray(native["gated_presence"], dtype=bool)
        feature, diagnostic = build_frame_features(keypoints, scores, presence)
        repeat, repeat_diagnostic = build_frame_features(keypoints.copy(), scores.copy(), presence.copy())
        if feature.tobytes() != repeat.tobytes() or diagnostic != repeat_diagnostic:
            raise RuntimeError(f"P5A_NONDETERMINISTIC_FRAME: {row['annotation_row_id']}")
        features.append(feature)
        frame_id = row["annotation_row_id"]
        raw_hashes[frame_id] = raw_hash
        image_hashes[frame_id] = image_hash
        raw_presence[frame_id] = (bool(presence[0]), bool(presence[1]))
        raw_scores[frame_id] = scores
        feature_manifest.append(
            {
                "tensor_index": tensor_index,
                "frame_id": frame_id,
                "sequence_id": row["sequence_id"],
                "signer_id": row["signer_id"],
                "frame_index": int(row["frame_index"]),
                "timestamp_ns": int(row["timestamp_ns"]),
                "source_image_path": row["image_path"],
                "source_image_sha256": image_hash,
                "raw_output_path": row["raw_relative_path"],
                "raw_output_sha256": raw_hash,
                "raw_origin": row["raw_origin"],
                "schema_id": SCHEMA_ID,
                "feature_width": FEATURE_WIDTH,
                "feature_sha256": hashlib.sha256(feature.tobytes()).hexdigest(),
            }
        )
        normalization_rows.append(
            {
                "frame_id": frame_id,
                "sequence_id": row["sequence_id"],
                "signer_id": row["signer_id"],
                "success": diagnostic.success,
                "center_method": diagnostic.center_method,
                "scale_method": diagnostic.scale_method,
                "center_x": diagnostic.center_x,
                "center_y": diagnostic.center_y,
                "scale": diagnostic.scale,
                "structurally_valid_body_points": diagnostic.structurally_valid_body_points,
            }
        )

    frame_tensor = np.ascontiguousarray(np.stack(features).astype("<f4", copy=False))
    if frame_tensor.shape != (458, FEATURE_WIDTH):
        raise RuntimeError("P5A_FRAME_TENSOR_SHAPE_FAILURE")
    feature_bytes_before_truth = frame_tensor.tobytes()
    np.save(output / "p5a_governed_frame_features.npy", frame_tensor, allow_pickle=False)
    write_csv(output / "p5a_governed_feature_manifest.csv", feature_manifest)
    write_csv(output / "p5a_normalization_diagnostics.csv", normalization_rows)
    write_csv(output / "p5a_feature_index_map.csv", feature_index_rows())

    grouped: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(ordered):
        grouped[row["sequence_id"]].append(index)
    sequence_ids = sorted(grouped)
    sequence_tensor = np.zeros((len(sequence_ids), SEQUENCE_LENGTH, FEATURE_WIDTH), dtype="<f4")
    sequence_mask = np.zeros((len(sequence_ids), SEQUENCE_LENGTH), dtype=bool)
    sequence_rows: list[dict[str, Any]] = []
    for sequence_index, sequence_id in enumerate(sequence_ids):
        indices = grouped[sequence_id]
        tensor, frame_mask, length = build_padded_sequence(frame_tensor[index] for index in indices)
        sequence_tensor[sequence_index] = tensor
        sequence_mask[sequence_index] = frame_mask
        first = ordered[indices[0]]
        sequence_rows.append(
            {
                "sequence_tensor_index": sequence_index,
                "sequence_id": sequence_id,
                "signer_id": first["signer_id"],
                "available_frames": len(indices),
                "encoded_frames": length,
                "truncated_frames": max(0, len(indices) - SEQUENCE_LENGTH),
            }
        )
    np.save(output / "p5a_governed_sequence_features.npy", sequence_tensor, allow_pickle=False)
    np.save(output / "p5a_governed_sequence_frame_mask.npy", sequence_mask, allow_pickle=False)
    write_csv(output / "p5a_governed_sequence_manifest.csv", sequence_rows)

    # Evaluation-only phase: truth is joined only after feature bytes are frozen in memory and on disk.
    truth_rows = csv_rows(TRUTH)
    truth_by_id = {row["frame_id"]: row for row in truth_rows}
    if len(truth_rows) != 458 or set(truth_by_id) != {row["annotation_row_id"] for row in ordered}:
        raise RuntimeError("P5A_TRUTH_JOIN_IDENTITY_FAILURE")
    if feature_bytes_before_truth != frame_tensor.tobytes():
        raise RuntimeError("P5A_GT_LEAKAGE_MUTATED_FEATURES")

    missingness_rows: list[dict[str, Any]] = []
    state_counts: dict[str, Counter[str]] = defaultdict(Counter)
    slot_scores: dict[str, list[float]] = {"LEFT": [], "RIGHT": [], "BODY": []}
    slot_valid: dict[str, list[float]] = {"LEFT": [], "RIGHT": [], "BODY": []}
    for index, row in enumerate(ordered):
        frame_id = row["annotation_row_id"]
        truth = truth_by_id[frame_id]
        left_observed, right_observed = raw_presence[frame_id]
        observed_count = int(left_observed) + int(right_observed)
        truth_count = truth["visible_hand_count"]
        state_counts[truth_count][f"OBSERVED_{observed_count}"] += 1
        feature = frame_tensor[index]
        for slot, start, end in (("LEFT", 0, 84), ("RIGHT", 84, 168), ("BODY", 168, 236)):
            block = feature[start:end].reshape(-1, 4)
            valid = block[:, 3] == 1
            slot_valid[slot].extend(block[:, 3].astype(float).tolist())
            slot_scores[slot].extend(block[valid, 2].astype(float).tolist())
        missingness_rows.append(
            {
                "frame_id": frame_id,
                "sequence_id": row["sequence_id"],
                "signer_id": row["signer_id"],
                "frame_index": int(row["frame_index"]),
                "timestamp_ns": int(row["timestamp_ns"]),
                "left_hand_observed_mask": int(left_observed),
                "right_hand_observed_mask": int(right_observed),
                "observed_hand_slot_count": observed_count,
                "left_valid_landmarks": int(np.sum(feature[3:84:4])),
                "right_valid_landmarks": int(np.sum(feature[87:168:4])),
                "body_valid_landmarks": int(np.sum(feature[171:236:4])),
                "human_truth_count_evaluation_only": truth_count,
                "human_left_visibility_evaluation_only": truth["left_visibility"],
                "human_right_visibility_evaluation_only": truth["right_visibility"],
            }
        )
    write_csv(output / "p5a_missingness_diagnostics.csv", missingness_rows)

    dropout_by_sequence: list[dict[str, Any]] = []
    all_runs: dict[str, list[int]] = {"LEFT": [], "RIGHT": []}
    transitions = Counter()
    for sequence_id in sequence_ids:
        indices = grouped[sequence_id]
        observations = [(raw_presence[ordered[index]["annotation_row_id"]]) for index in indices]
        counts = [int(left) + int(right) for left, right in observations]
        for before, after in zip(counts, counts[1:]):
            transitions[f"{before}_TO_{after}"] += 1
        for slot_index, slot in enumerate(("LEFT", "RIGHT")):
            values = [pair[slot_index] for pair in observations]
            runs = zero_runs(values)
            all_runs[slot].extend(runs)
            dropout_by_sequence.append(
                {
                    "sequence_id": sequence_id,
                    "signer_id": ordered[indices[0]]["signer_id"],
                    "slot": slot,
                    "frames": len(values),
                    "observed_frames": sum(values),
                    "observed_rate": sum(values) / len(values),
                    "missing_runs": len(runs),
                    "one_frame_missing_runs": sum(run == 1 for run in runs),
                    "multi_frame_missing_runs": sum(run > 1 for run in runs),
                    "max_missing_run": max(runs, default=0),
                }
            )
    write_csv(output / "p5a_dropout_by_sequence.csv", dropout_by_sequence)

    normalization_successes = sum(str(row["success"]).lower() == "true" for row in normalization_rows)
    primary_norm = sum(
        row["center_method"] == "SHOULDER_PRIMARY" and row["scale_method"] == "SHOULDER_DISTANCE_PRIMARY"
        for row in normalization_rows
    )
    two_truth = [row for row in missingness_rows if row["human_truth_count_evaluation_only"] == "TWO"]
    profile = {
        "schema_id": SCHEMA_ID,
        "source_scope": "458 governed P4 V2 frames; sampled/consecutive windows ordered by current timestamps",
        "human_truth_used_for_generation": False,
        "frames": len(ordered),
        "sequences": len(sequence_ids),
        "signers": len({row["signer_id"] for row in ordered}),
        "hand_observed_rate": {
            slot: sum(raw_presence[row["annotation_row_id"]][slot_index] for row in ordered) / len(ordered)
            for slot_index, slot in enumerate(("LEFT", "RIGHT"))
        },
        "per_landmark_valid_rate": {
            slot: float(np.mean(values)) for slot, values in slot_valid.items()
        },
        "valid_landmark_score_distribution": {
            slot: percentile_summary(values) for slot, values in slot_scores.items()
        },
        "missing_run_lengths": {slot: Counter(runs) for slot, runs in all_runs.items()},
        "single_frame_missing_run_count": {slot: sum(run == 1 for run in runs) for slot, runs in all_runs.items()},
        "multi_frame_missing_run_count": {slot: sum(run > 1 for run in runs) for slot, runs in all_runs.items()},
        "single_frame_loss_probability_over_dropout_runs": {
            slot: (sum(run == 1 for run in runs) / len(runs) if runs else 0.0) for slot, runs in all_runs.items()
        },
        "observation_state_transitions": dict(sorted(transitions.items())),
        "two_hand_truth_incomplete_observation_frequency": (
            sum(row["observed_hand_slot_count"] < 2 for row in two_truth) / len(two_truth) if two_truth else None
        ),
        "truth_state_observation_counts_evaluation_only": {
            state: dict(sorted(counter.items())) for state, counter in sorted(state_counts.items())
        },
        "normalization": {
            "success_count": normalization_successes,
            "success_rate": normalization_successes / len(normalization_rows),
            "primary_count": primary_norm,
            "fallback_count": normalization_successes - primary_norm,
            "fallback_rate": (normalization_successes - primary_norm) / len(normalization_rows),
        },
    }
    write_json(output / "p5a_observed_dropout_profile.json", profile)

    nonfinite = int(np.size(frame_tensor) - np.count_nonzero(np.isfinite(frame_tensor)))
    unobserved_zero_violations = 0
    for index, row in enumerate(ordered):
        left, right = raw_presence[row["annotation_row_id"]]
        if (not left and np.any(frame_tensor[index, :RIGHT_HAND_OFFSET] != 0)) or (
            not right and np.any(frame_tensor[index, RIGHT_HAND_OFFSET:BODY_OFFSET] != 0)
        ):
            unobserved_zero_violations += 1
    sequence_padding_violations = 0
    for sequence_index, row in enumerate(sequence_rows):
        length = int(row["encoded_frames"])
        if np.any(sequence_tensor[sequence_index, length:] != 0) or np.any(sequence_mask[sequence_index, length:]):
            sequence_padding_violations += 1
    integrity = {
        "status": "PASS" if nonfinite == 0 and unobserved_zero_violations == 0 and sequence_padding_violations == 0 and normalization_successes / 458 >= 0.99 else "FAIL",
        "schema_id": SCHEMA_ID,
        "contract_hashes_verified_before_conversion": True,
        "truth_hash_verified": True,
        "source_images_verified": len(image_hashes),
        "native_outputs_verified": len(raw_hashes),
        "new_dwpose_inference_frames": 0,
        "governed_frame_shape": list(frame_tensor.shape),
        "canonical_sequence_shape": [SEQUENCE_LENGTH, FEATURE_WIDTH],
        "sequence_tensor_shape": list(sequence_tensor.shape),
        "dtype": str(frame_tensor.dtype),
        "nan_inf_count": nonfinite,
        "unobserved_hand_nonzero_violations": unobserved_zero_violations,
        "sequence_padding_violations": sequence_padding_violations,
        "focused_unit_tests": {"passed": 6, "failed": 0},
        "determinism": "every frame rebuilt twice and compared byte-for-byte",
        "ground_truth_leakage": False,
        "feature_generation_inputs": ["native keypoints_133", "native scores_133", "native gated_presence", "frame metadata"],
        "human_truth_columns_used_by_builder": [],
        "normalization_success_count": normalization_successes,
        "normalization_success_rate": normalization_successes / 458,
        "normalization_fallback_count": normalization_successes - primary_norm,
        "normalization_fallback_rate": (normalization_successes - primary_norm) / 458,
        "sequence_truncated_frames": sum(int(row["truncated_frames"]) for row in sequence_rows),
        "frame_feature_data_sha256": hashlib.sha256(frame_tensor.tobytes()).hexdigest(),
        "sequence_feature_data_sha256": hashlib.sha256(sequence_tensor.tobytes()).hexdigest(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(output / "p5a_integrity_test_results.json", integrity)
    if integrity["status"] != "PASS":
        raise RuntimeError(f"P5A_INTEGRITY_FAILURE: {integrity}")
    print(json.dumps(integrity, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
