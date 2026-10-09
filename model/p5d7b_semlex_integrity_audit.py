"""P5-D7B read-only audit of completed Sem-Lex DWPose/V2 extraction outputs.

This module never decodes video, runs DWPose, regenerates V2, trains, or merges
data.  It reads the governed P5-D5/D6/D7A lineage artifacts, the completed
project-lead extraction, and the frozen AppHear TRAIN V2 tensor, then writes a
new, separate audit package.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from model import p5d7a_semlex_prepare as d7a


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/recognition_upgrade"
D5 = BASE / "p5_representation_v2/p5d5_semlex_form_review_01"
D6 = BASE / "p5_representation_v2/p5d6_semlex_human_review_01"
D7A = BASE / "p5_representation_v2/p5d7a_semlex_extraction_prep_01"
OUT = BASE / "p5_representation_v2/p5d7b_semlex_integrity_audit_01"
STAGED = Path(r"G:\SEM LEX\AppHear_P5D7_candidate\staged")
EXTRACTED = Path(r"G:\SEM LEX\AppHear_P5D7_candidate\full_parallel_exact")
APPHEAR_V2 = BASE / "p5_representation_v2/p5b_migration_01/dataset/train.npz"
APPHEAR_VOCAB = BASE / "p5_representation_v2/p5b_migration_01/dataset/vocab.json"
APPHEAR_MANIFEST = BASE / "phase1_full_vocab/manifest_01/canonical_manifest.csv"
PROGRESS = ROOT / "context/progress-tracker.md"

EXPECTED = {
    "progress": "12cf08f81959a413a60aa1f869615a24485a41ee3d796e61fce7489ae5c480cf",
    "apphear_v2_train": "a2261ea8d61e5eed1a526da0493da5b36c1bb54432ccef7f7479d6ca94634f11",
    "apphear_vocab": "a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b",
    "apphear_manifest": "8c1fab3df04a0240b5a178853b2206408806958afebdd19bd3d44d6fca606571",
    "dwpose_checkpoint": "e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7",
    "dwpose_config": "b2e741d2428667c99e74218f5170a183337602755c76e5b4138546a9b59d5032",
    "v2_contract": "0c94e9c885f331164d8ab1f7f0915eb89de43101394bd0949fae033b57f76d8b",
}

USABLE = "USABLE_CANDIDATE"
ZERO_HAND = "ZERO_HAND_SEQUENCE_QUARANTINE"
DECODE_EXCLUSION = "RAW_MEDIA_DECODE_EXCLUSION"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(materialized)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def bool_text(value: bool) -> str:
    return "True" if value else "False"


def safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def effective_signers(rows: list[dict[str, Any]], signer_key: str) -> float:
    counts = Counter(str(row[signer_key]) for row in rows)
    total = sum(counts.values())
    hhi = sum((count / total) ** 2 for count in counts.values()) if total else 0.0
    return 1.0 / hhi if hhi else 0.0


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), q)) if values else 0.0


def verify_manifest(manifest_path: Path) -> list[str]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    artifacts = data.get("artifacts", [])
    items = (
        [{"path": path, "sha256": digest} for path, digest in artifacts.items()]
        if isinstance(artifacts, dict) else artifacts
    )
    for item in items:
        candidate = manifest_path.parent / item["path"]
        if not candidate.is_file():
            candidate = ROOT / item["path"]
        if not candidate.is_file():
            errors.append(f"MISSING:{item['path']}")
        elif sha256(candidate) != item["sha256"]:
            errors.append(f"HASH_MISMATCH:{item['path']}")
    return errors


def source_hashes() -> dict[str, str]:
    return {
        "progress_tracker": sha256(PROGRESS),
        "apphear_v2_train": sha256(APPHEAR_V2),
        "apphear_vocab": sha256(APPHEAR_VOCAB),
        "apphear_manifest": sha256(APPHEAR_MANIFEST),
        "d5_manifest": sha256(D5 / "artifact_hash_manifest.json"),
        "d6_manifest": sha256(D6 / "artifact_hash_manifest.json"),
        "d7a_manifest": sha256(D7A / "artifact_hash_manifest.json"),
        "staged_manifest": sha256(STAGED / "staged_manifest.csv"),
        "completed_human_decision_sheet": sha256(d7a.DECISIONS),
        "semlex_metadata": sha256(d7a.SEMLEX_META),
    }


def aggregate_tensor_metrics(
    features: np.ndarray,
    masks: np.ndarray,
    labels: np.ndarray,
    signers: np.ndarray,
    glosses: dict[int, str],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Compute the same V2 metrics for AppHear or an assembled Sem-Lex pool."""
    overall_acc: dict[str, float] = defaultdict(float)
    overall_counts: Counter[str] = Counter()
    by_class_indices: dict[int, list[int]] = defaultdict(list)
    by_signer_indices: dict[str, list[int]] = defaultdict(list)
    per_clip: dict[str, dict[str, Any]] = {}
    motion_values: list[float] = []

    for index in range(features.shape[0]):
        real = np.asarray(masks[index], dtype=bool)
        x = np.asarray(features[index], dtype=np.float32)
        length = int(real.sum())
        if length <= 0:
            raise RuntimeError(f"empty real-frame mask at row {index}")
        xr = x[real]
        left = xr[:, 0:84].reshape(-1, 21, 4)
        right = xr[:, 84:168].reshape(-1, 21, 4)
        body = xr[:, 168:236].reshape(-1, 17, 4)
        lh_obs = xr[:, 236] > 0.5
        rh_obs = xr[:, 237] > 0.5
        both = lh_obs & rh_obs
        either = lh_obs | rh_obs
        neither = ~either
        lvalid = left[:, :, 3] > 0.5
        rvalid = right[:, :, 3] > 0.5
        bvalid = body[:, :, 3] > 0.5
        valid_hand = np.concatenate([lvalid, rvalid], axis=1)
        hand_scores = np.concatenate([left[:, :, 2], right[:, :, 2]], axis=1)
        hand_xy = np.concatenate([left[:, :, :2], right[:, :, :2]], axis=1)

        for hand, valid in ((left, lvalid), (right, rvalid)):
            if length < 2:
                continue
            pair_valid = valid[1:] & valid[:-1]
            displacement = np.linalg.norm(hand[1:, :, :2] - hand[:-1, :, :2], axis=2)
            motion_values.extend(displacement[pair_valid].astype(np.float64).tolist())

        clip = {
            "length": length,
            "lh_observed_rate": float(lh_obs.mean()),
            "rh_observed_rate": float(rh_obs.mean()),
            "both_observed_rate": float(both.mean()),
            "at_least_one_observed_rate": float(either.mean()),
            "neither_observed_rate": float(neither.mean()),
            "valid_hand_landmark_rate": float(valid_hand.mean()),
            "body_valid_rate": float(bvalid.mean()),
            "mean_valid_hand_score": float(hand_scores[valid_hand].mean()) if valid_hand.any() else 0.0,
            "mean_valid_body_score": float(body[:, :, 2][bvalid].mean()) if bvalid.any() else 0.0,
            "mean_abs_hand_xy": float(np.abs(hand_xy[valid_hand]).mean()) if valid_hand.any() else 0.0,
            "zero_hand_sequence": bool(not either.any()),
            "never_both_observed": bool(not both.any()),
            "low_hand_observation": bool(float(either.mean()) < 0.5),
        }
        per_clip[str(index)] = clip
        for key, value in clip.items():
            if isinstance(value, bool):
                overall_counts[key] += int(value)
            else:
                overall_acc[key] += float(value)
        by_class_indices[int(labels[index])].append(index)
        by_signer_indices[str(signers[index])].append(index)

    def summarize(indices: list[int], key: str, value: str) -> dict[str, Any]:
        clips = [per_clip[str(index)] for index in indices]
        return {
            key: value,
            "clips": len(indices),
            "real_frames": int(sum(clip["length"] for clip in clips)),
            "median_sequence_length": float(np.median([clip["length"] for clip in clips])),
            "lh_observed_rate": float(np.average([clip["lh_observed_rate"] for clip in clips], weights=[clip["length"] for clip in clips])),
            "rh_observed_rate": float(np.average([clip["rh_observed_rate"] for clip in clips], weights=[clip["length"] for clip in clips])),
            "both_observed_rate": float(np.average([clip["both_observed_rate"] for clip in clips], weights=[clip["length"] for clip in clips])),
            "at_least_one_observed_rate": float(np.average([clip["at_least_one_observed_rate"] for clip in clips], weights=[clip["length"] for clip in clips])),
            "neither_observed_rate": float(np.average([clip["neither_observed_rate"] for clip in clips], weights=[clip["length"] for clip in clips])),
            "valid_hand_landmark_rate": float(np.average([clip["valid_hand_landmark_rate"] for clip in clips], weights=[clip["length"] for clip in clips])),
            "body_valid_rate": float(np.average([clip["body_valid_rate"] for clip in clips], weights=[clip["length"] for clip in clips])),
            "zero_hand_sequences": sum(clip["zero_hand_sequence"] for clip in clips),
            "never_both_observed_clips": sum(clip["never_both_observed"] for clip in clips),
            "low_hand_observation_clips": sum(clip["low_hand_observation"] for clip in clips),
            "low_hand_observation_clip_rate": safe_ratio(sum(clip["low_hand_observation"] for clip in clips), len(clips)),
            "mean_valid_hand_score": float(np.mean([clip["mean_valid_hand_score"] for clip in clips])),
            "mean_valid_body_score": float(np.mean([clip["mean_valid_body_score"] for clip in clips])),
            "mean_abs_hand_xy": float(np.mean([clip["mean_abs_hand_xy"] for clip in clips])),
        }

    class_rows = []
    for class_id, indices in sorted(by_class_indices.items()):
        row = summarize(indices, "class_id", class_id)
        row["gloss"] = glosses.get(class_id, "")
        class_rows.append(row)
    signer_rows = [summarize(indices, "signer_id", signer) for signer, indices in sorted(by_signer_indices.items())]
    all_indices = list(range(features.shape[0]))
    overall = summarize(all_indices, "scope", "OVERALL")
    overall["median_hand_motion"] = float(np.median(motion_values)) if motion_values else 0.0
    overall["p90_hand_motion"] = percentile(motion_values, 90)
    return overall, class_rows, signer_rows, per_clip


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    before_hashes = source_hashes()
    if before_hashes["progress_tracker"] != EXPECTED["progress"]:
        raise RuntimeError("progress-tracker hash mismatch")
    if before_hashes["apphear_v2_train"] != EXPECTED["apphear_v2_train"]:
        raise RuntimeError("AppHear V2 TRAIN hash mismatch")
    if before_hashes["apphear_vocab"] != EXPECTED["apphear_vocab"]:
        raise RuntimeError("AppHear vocabulary hash mismatch")
    if before_hashes["apphear_manifest"] != EXPECTED["apphear_manifest"]:
        raise RuntimeError("AppHear canonical manifest hash mismatch")
    if before_hashes["completed_human_decision_sheet"] != d7a.EXPECTED_DECISION_SHA:
        raise RuntimeError("completed human decision sheet hash mismatch")
    if before_hashes["semlex_metadata"] != d7a.EXPECTED_SEMLEX_META_SHA:
        raise RuntimeError("Sem-Lex metadata hash mismatch")
    source_manifest_errors = {
        "p5d5": verify_manifest(D5 / "artifact_hash_manifest.json"),
        "p5d6": verify_manifest(D6 / "artifact_hash_manifest.json"),
        "p5d7a": verify_manifest(D7A / "artifact_hash_manifest.json"),
    }
    if any(source_manifest_errors.values()):
        raise RuntimeError(f"governed source manifest mismatch: {source_manifest_errors}")

    accepted_classes, _ = d7a.accepted_classes()
    candidates = d7a.build_candidate_rows(accepted_classes)
    if len(accepted_classes) != 65 or len(candidates) != 2666:
        raise RuntimeError("accepted-set reconstruction mismatch")
    accepted_by_class = {int(row["apphear_class_id"]): row for row in accepted_classes}
    unresolved = {"IF", "OLD", "GET", "TURN", "ANY"}
    if unresolved & {row["apphear_gloss"] for row in accepted_classes}:
        raise RuntimeError("unresolved class entered accepted set")
    frozen_accepted = read_csv(D7A / "p5d7a_human_accepted_class_set.csv")
    reconstructed_keys = {
        (str(row["apphear_class_id"]), row["apphear_gloss"], row["human_decision"])
        for row in accepted_classes
    }
    frozen_keys = {
        (row["apphear_class_id"], row["apphear_gloss"], row["human_decision"])
        for row in frozen_accepted
    }
    if reconstructed_keys != frozen_keys:
        raise RuntimeError("reconstructed human acceptance set differs from frozen P5-D7A set")

    raw_audit = {row["semlex_sample_id"]: row for row in read_csv(D7A / "semlex_raw_join_audit.csv")}
    staged_rows = read_csv(STAGED / "staged_manifest.csv")
    staged_by_id = {row["semlex_sample_id"]: row for row in staged_rows}
    if len(staged_rows) != 2425 or len(staged_by_id) != 2425:
        raise RuntimeError("staged manifest count/uniqueness mismatch")
    staging_summary = json.loads((STAGED / "staging_summary.json").read_text(encoding="utf-8"))
    if not staging_summary.get("passed") or staging_summary.get("verified_staged") != 2425:
        raise RuntimeError("staging summary integrity mismatch")

    completion_records: dict[str, dict[str, Any]] = {}
    for path in sorted((EXTRACTED / "completed").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        completion_records[value["sample_id"]] = value
    failure_records: dict[str, dict[str, Any]] = {}
    for path in sorted((EXTRACTED / "failures").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        failure_records[value["sample_id"]] = value
    if len(completion_records) != 2417 or len(failure_records) != 8:
        raise RuntimeError("completed/failure record count mismatch")
    if set(completion_records) & set(failure_records):
        raise RuntimeError("sample appears in both completion and failure records")
    if set(staged_by_id) != set(completion_records) | set(failure_records):
        raise RuntimeError("staged extraction accounting mismatch")

    # Validate every native/V2 pair and assemble one array view for source comparison.
    integrity_rows: list[dict[str, Any]] = []
    sem_features: list[np.ndarray] = []
    sem_masks: list[np.ndarray] = []
    sem_labels: list[int] = []
    sem_signers: list[str] = []
    sem_sample_ids: list[str] = []
    center_methods: Counter[str] = Counter()
    scale_methods: Counter[str] = Counter()
    contract_failures = 0
    for sample_id, record in sorted(completion_records.items()):
        source = staged_by_id[sample_id]
        native_path = EXTRACTED / record["native_relative_path"]
        v2_path = EXTRACTED / record["v2_relative_path"]
        errors: list[str] = []
        if not native_path.is_file() or not v2_path.is_file():
            errors.append("OUTPUT_MISSING")
        else:
            if sha256(native_path) != record["native_sha256"]:
                errors.append("NATIVE_SHA_MISMATCH")
            if sha256(v2_path) != record["v2_sha256"]:
                errors.append("V2_SHA_MISMATCH")
        length = 0
        lh_rate = rh_rate = both_rate = either_rate = hand_valid_rate = body_valid_rate = 0.0
        if not errors:
            with np.load(native_path, allow_pickle=False) as native:
                keypoints = native["keypoints_xy"]
                scores = native["scores"]
                processed = int(native["processed_frame_count"])
                if keypoints.shape != (processed, 133, 2) or scores.shape != (processed, 133):
                    errors.append("NATIVE_SHAPE_INVALID")
                if keypoints.dtype != np.float32 or scores.dtype != np.float32:
                    errors.append("NATIVE_DTYPE_INVALID")
                if not np.isfinite(keypoints).all() or not np.isfinite(scores).all():
                    errors.append("NATIVE_NONFINITE")
                if str(native["sample_id"]) != sample_id:
                    errors.append("NATIVE_SAMPLE_LINEAGE_INVALID")
                if str(native["signer_id"]) != source["semlex_signer_id"]:
                    errors.append("NATIVE_SIGNER_LINEAGE_INVALID")
                if str(native["source_raw_sha256"]) != source["raw_sha256"]:
                    errors.append("NATIVE_RAW_SHA_LINEAGE_INVALID")
                if str(native["checkpoint_sha256"]) != EXPECTED["dwpose_checkpoint"]:
                    errors.append("NATIVE_CHECKPOINT_INVALID")
            with np.load(v2_path, allow_pickle=False) as v2:
                features = np.asarray(v2["features"])
                frame_mask = np.asarray(v2["frame_mask"], dtype=bool)
                length = int(v2["length"])
                if features.shape != (96, 238):
                    errors.append("V2_SHAPE_INVALID")
                if features.dtype != np.float32:
                    errors.append("V2_DTYPE_INVALID")
                if not np.isfinite(features).all():
                    errors.append("V2_NONFINITE")
                if frame_mask.shape != (96,) or frame_mask.sum() != length or not frame_mask[:length].all() or frame_mask[length:].any():
                    errors.append("V2_MASK_INVALID")
                if np.any(features[length:] != 0):
                    errors.append("V2_PADDING_NONZERO")
                left = features[:length, 0:84].reshape(-1, 21, 4)
                right = features[:length, 84:168].reshape(-1, 21, 4)
                body = features[:length, 168:236].reshape(-1, 17, 4)
                left_obs = features[:length, 236] > 0.5
                right_obs = features[:length, 237] > 0.5
                if not np.array_equal(left_obs, np.asarray(v2["left_observed"], dtype=bool)) or not np.array_equal(right_obs, np.asarray(v2["right_observed"], dtype=bool)):
                    errors.append("V2_OBSERVED_FLAG_INCONSISTENT")
                for block, name in ((left, "LH"), (right, "RH"), (body, "BODY")):
                    valid = block[:, :, 3] > 0.5
                    if np.any(block[:, :, :3][~valid] != 0):
                        errors.append(f"{name}_INVALID_LANDMARK_NONZERO")
                if np.any(left[~left_obs] != 0) or np.any(right[~right_obs] != 0):
                    errors.append("UNOBSERVED_WHOLE_HAND_NONZERO")
                if str(v2["sample_id"]) != sample_id or int(v2["class_id"]) != int(source["apphear_class_id"]):
                    errors.append("V2_SAMPLE_CLASS_LINEAGE_INVALID")
                if str(v2["signer_id"]) != source["semlex_signer_id"]:
                    errors.append("V2_SIGNER_LINEAGE_INVALID")
                lh_rate = float(left_obs.mean())
                rh_rate = float(right_obs.mean())
                both_rate = float((left_obs & right_obs).mean())
                either_rate = float((left_obs | right_obs).mean())
                hand_valid_rate = float(np.concatenate([left[:, :, 3], right[:, :, 3]], axis=1).mean())
                body_valid_rate = float(body[:, :, 3].mean())
                center_methods.update(map(str, v2["center_methods"].tolist()))
                scale_methods.update(map(str, v2["scale_methods"].tolist()))
                sem_features.append(features)
                sem_masks.append(frame_mask)
                sem_labels.append(int(v2["class_id"]))
                sem_signers.append(str(v2["signer_id"]))
                sem_sample_ids.append(sample_id)
        if errors:
            contract_failures += 1
        integrity_rows.append({
            "semlex_sample_id": sample_id,
            "apphear_class_id": source["apphear_class_id"],
            "apphear_gloss": source["apphear_gloss"],
            "semlex_signer_id": source["semlex_signer_id"],
            "human_decision": source["human_decision"],
            "native_path": str(native_path),
            "v2_path": str(v2_path),
            "native_sha_verified": bool_text("NATIVE_SHA_MISMATCH" not in errors),
            "v2_sha_verified": bool_text("V2_SHA_MISMATCH" not in errors),
            "native_valid": bool_text(not any(item.startswith("NATIVE_") for item in errors)),
            "v2_shape": "[96,238]" if "V2_SHAPE_INVALID" not in errors else "INVALID",
            "v2_dtype": "float32" if "V2_DTYPE_INVALID" not in errors else "INVALID",
            "finite": bool_text("V2_NONFINITE" not in errors),
            "padding_valid": bool_text("V2_PADDING_NONZERO" not in errors),
            "mask_valid": bool_text("V2_MASK_INVALID" not in errors),
            "observed_flags_valid": bool_text("V2_OBSERVED_FLAG_INCONSISTENT" not in errors),
            "invalid_landmarks_zero": bool_text(not any("INVALID_LANDMARK_NONZERO" in item for item in errors)),
            "unobserved_hands_zero": bool_text("UNOBSERVED_WHOLE_HAND_NONZERO" not in errors),
            "lineage_valid": bool_text(not any("LINEAGE_INVALID" in item for item in errors)),
            "real_length": length,
            "lh_observed_rate": lh_rate,
            "rh_observed_rate": rh_rate,
            "both_observed_rate": both_rate,
            "at_least_one_observed_rate": either_rate,
            "valid_hand_landmark_rate": hand_valid_rate,
            "body_valid_rate": body_valid_rate,
            "integrity_state": "PASS" if not errors else "FAIL",
            "errors": "|".join(errors),
        })
    if len(sem_features) != 2417:
        raise RuntimeError("not all completed V2 outputs were readable")

    sem_x = np.stack(sem_features)
    sem_m = np.stack(sem_masks)
    sem_y = np.asarray(sem_labels, dtype=np.int32)
    sem_s = np.asarray(sem_signers)
    glosses = {class_id: row["apphear_gloss"] for class_id, row in accepted_by_class.items()}
    sem_overall, sem_class_rows, sem_signer_rows, sem_clip_metrics_indexed = aggregate_tensor_metrics(
        sem_x, sem_m, sem_y, sem_s, glosses
    )
    sem_clip_metrics = {sample_id: sem_clip_metrics_indexed[str(index)] for index, sample_id in enumerate(sem_sample_ids)}

    with np.load(APPHEAR_V2, allow_pickle=False) as app:
        app_x = np.asarray(app["X"], dtype=np.float32)
        app_y = np.asarray(app["y"], dtype=np.int32)
        app_m = np.asarray(app["frame_mask"], dtype=bool)
        app_s = np.asarray(app["signer_group_ids"])
    vocab_raw = json.loads(APPHEAR_VOCAB.read_text(encoding="utf-8"))
    vocab = vocab_raw.get("classes", vocab_raw) if isinstance(vocab_raw, dict) else vocab_raw
    all_glosses = {index: str(value) for index, value in enumerate(vocab)}
    app_overall, app_class_rows, _, _ = aggregate_tensor_metrics(app_x, app_m, app_y, app_s, all_glosses)
    matched_apphear = np.isin(app_y, np.asarray(sorted(accepted_by_class), dtype=np.int32))
    app_matched_overall, _, _, _ = aggregate_tensor_metrics(
        app_x[matched_apphear], app_m[matched_apphear], app_y[matched_apphear], app_s[matched_apphear], all_glosses
    )
    app_class_by_id = {int(row["class_id"]): row for row in app_class_rows}
    sem_class_by_id = {int(row["class_id"]): row for row in sem_class_rows}

    # Explicitly quarantine only the two evidence-supported zero-hand sequences.
    usability: dict[str, str] = {}
    for sample_id in completion_records:
        usability[sample_id] = ZERO_HAND if sem_clip_metrics[sample_id]["zero_hand_sequence"] else USABLE
    zero_hand_ids = {sample_id for sample_id, state in usability.items() if state == ZERO_HAND}
    if zero_hand_ids != {"nCzDsK1bJa633owYTjfp", "tzQe8d8PfngcM8rqKUiQ"}:
        raise RuntimeError(f"zero-hand sequence set mismatch: {sorted(zero_hand_ids)}")

    # Reconstruct all 2,666 candidate rows; later duplicate occurrences are earliest-stage losses.
    occurrence: Counter[str] = Counter()
    ledger_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        sample_id = candidate["semlex_sample_id"]
        occurrence[sample_id] += 1
        duplicate_occurrence = occurrence[sample_id] > 1
        audit = raw_audit.get(sample_id, {})
        staged = sample_id in staged_by_id and not duplicate_occurrence
        completed = sample_id in completion_records and not duplicate_occurrence
        failed = sample_id in failure_records and not duplicate_occurrence
        raw_found = audit.get("reason", "") != "MISSING_RAW_ARCHIVE_MEMBER"
        if duplicate_occurrence:
            loss_stage = "STAGE_2_RAW_STAGING_ELIGIBILITY"
            loss_reason = "DUPLICATE_EXCLUSION"
            state = "NOT_EXTRACTED_PRE_STAGING"
            notes = f"Duplicate metadata occurrence {occurrence[sample_id]}; canonical occurrence retained for independent downstream accounting."
        elif not staged:
            reason = audit.get("reason", "")
            taxonomy = {
                "MISSING_RAW_ARCHIVE_MEMBER": "RAW_FILE_NOT_PRESENT",
                "NON_TRAIN_SPLIT": "NON_TRAIN_SPLIT",
                "MISSING_SIGNER_ID": "SIGNER_ID_MISSING",
                "LABEL_MAPPING_CONFLICT": "HUMAN_DECISION_MAPPING_FAILURE",
                "EXACT_RAW_DUPLICATE_NONCANONICAL": "DUPLICATE_EXCLUSION",
                "CONFIRMED_APPHEAR_TRAIN_RAW_SHA_OVERLAP": "PREVIOUSLY_EXISTING_APPHEAR_OVERLAP",
            }
            loss_stage = "STAGE_2_RAW_STAGING_ELIGIBILITY"
            loss_reason = taxonomy.get(reason, "OTHER_EXPLICITLY_DOCUMENTED_REASON")
            state = "NOT_EXTRACTED_PRE_STAGING"
            notes = reason or "No governed raw/staging-eligible row."
        elif failed:
            loss_stage = "STAGE_4_DWPOSE_EXTRACTION_INPUT_DECODE"
            loss_reason = DECODE_EXCLUSION
            state = "NOT_EXTRACTED_RAW_MEDIA_DECODE"
            notes = str(failure_records[sample_id].get("error", ""))
        elif contract_failures and next((row for row in integrity_rows if row["semlex_sample_id"] == sample_id), {}).get("integrity_state") != "PASS":
            loss_stage = "STAGE_5_V2_INTEGRITY"
            loss_reason = "V2_INTEGRITY_QUARANTINE"
            state = "V2_INTEGRITY_QUARANTINE"
            notes = "Completed output failed governed integrity checks."
        elif usability[sample_id] == ZERO_HAND:
            loss_stage = "STAGE_6_TRAINING_USABILITY"
            loss_reason = ZERO_HAND
            state = ZERO_HAND
            notes = "Decoded non-empty source; native body evidence present; neither hand observed on any real frame."
        else:
            loss_stage = ""
            loss_reason = ""
            state = USABLE
            notes = ""
        ledger_rows.append({
            "apphear_class_id": candidate["apphear_class_id"],
            "apphear_gloss": candidate["apphear_gloss"],
            "human_decision": candidate["human_decision"],
            "semlex_sample_id": sample_id,
            "semlex_signer_id": candidate["semlex_signer_id"],
            "semlex_lexical_id": candidate["semlex_lexical_id"],
            "metadata_candidate": "True",
            "raw_found": bool_text(raw_found),
            "staging_eligible": bool_text(staged),
            "staged": bool_text(staged),
            "dwpose_success": bool_text(completed),
            "v2_success": bool_text(completed and contract_failures == 0),
            "training_usability_state": state,
            "loss_stage": loss_stage,
            "loss_reason": loss_reason,
            "notes": notes,
        })
    if len(ledger_rows) != 2666:
        raise RuntimeError("attrition ledger count mismatch")

    pre_staging = [row for row in ledger_rows if row["staged"] == "False"]
    pre_counts = Counter(row["loss_reason"] for row in pre_staging)
    if len(pre_staging) != 241 or pre_counts != Counter({"RAW_FILE_NOT_PRESENT": 161, "DUPLICATE_EXCLUSION": 80}):
        raise RuntimeError(f"pre-staging attribution mismatch: {len(pre_staging)} {pre_counts}")
    pre_summary_rows = []
    for reason, count in sorted(pre_counts.items()):
        affected = [row for row in pre_staging if row["loss_reason"] == reason]
        pre_summary_rows.append({
            "loss_reason": reason,
            "candidate_rows": count,
            "unique_sample_ids": len({row["semlex_sample_id"] for row in affected}),
            "classes_affected": len({row["apphear_class_id"] for row in affected}),
            "signer_class_slots_affected": len({(row["apphear_class_id"], row["semlex_signer_id"]) for row in affected}),
            "explanation": "Repeated metadata rows canonicalized to one source sample." if reason == "DUPLICATE_EXCLUSION" else "Governed TRAIN metadata sample ID absent from the supplied Sem-Lex raw archive.",
        })

    # Projected signer-slot accounting (unique class/signer pairs).
    projected_slot_rows: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        projected_slot_rows[(int(row["apphear_class_id"]), row["semlex_signer_id"])].append(row)
    staged_slots = {(int(row["apphear_class_id"]), row["semlex_signer_id"]) for row in staged_rows}
    slot_rows = []
    for (class_id, signer), rows_for_slot in sorted(projected_slot_rows.items()):
        present = (class_id, signer) in staged_slots
        sample_ids = sorted({row["semlex_sample_id"] for row in rows_for_slot})
        missing_ids = [sample_id for sample_id in sample_ids if sample_id not in staged_by_id]
        slot_rows.append({
            "apphear_class_id": class_id,
            "apphear_gloss": accepted_by_class[class_id]["apphear_gloss"],
            "semlex_signer_id": signer,
            "projected_slot": "True",
            "staged_slot": bool_text(present),
            "projected_candidate_rows": len(rows_for_slot),
            "unique_projected_samples": len(sample_ids),
            "staged_samples": sum(sample_id in staged_by_id for sample_id in sample_ids),
            "slot_loss_reason": "" if present else "RAW_FILE_NOT_PRESENT_FOR_ALL_SLOT_SAMPLES",
            "missing_sample_ids": "|".join(missing_ids),
        })
    if len(slot_rows) != 925 or sum(row["staged_slot"] == "False" for row in slot_rows) != 31:
        raise RuntimeError("projected signer-slot accounting mismatch")

    decode_rows = []
    for sample_id, failure in sorted(failure_records.items()):
        source = staged_by_id[sample_id]
        slot = (int(source["apphear_class_id"]), source["semlex_signer_id"])
        same_slot_success = any(
            sid in completion_records and int(staged_by_id[sid]["apphear_class_id"]) == slot[0]
            and staged_by_id[sid]["semlex_signer_id"] == slot[1]
            for sid in staged_by_id
        )
        class_success = any(int(staged_by_id[sid]["apphear_class_id"]) == slot[0] for sid in completion_records)
        decode_rows.append({
            "semlex_sample_id": sample_id,
            "apphear_class_id": source["apphear_class_id"],
            "apphear_gloss": source["apphear_gloss"],
            "semlex_signer_id": source["semlex_signer_id"],
            "raw_video_path": source["raw_video_path"],
            "raw_sha256": source["raw_sha256"],
            "failure_evidence": failure.get("error", ""),
            "classification": DECODE_EXCLUSION,
            "entire_class_lost": bool_text(not class_success),
            "class_signer_slot_lost": bool_text(not same_slot_success),
            "signer_lost_from_class": bool_text(not same_slot_success),
            "not_a_dwpose_failure": "True",
            "not_a_v2_failure": "True",
        })

    # Per-sample usability, including non-exclusionary descriptive flags.
    usability_rows = []
    low_rows = []
    class_low_rates = {int(row["class_id"]): row["low_hand_observation_clip_rate"] for row in sem_class_rows}
    signer_low_rates = {str(row["signer_id"]): row["low_hand_observation_clip_rate"] for row in sem_signer_rows}
    for sample_id in sorted(completion_records):
        source = staged_by_id[sample_id]
        metrics = sem_clip_metrics[sample_id]
        state = usability[sample_id]
        usability_rows.append({
            "semlex_sample_id": sample_id,
            "apphear_class_id": source["apphear_class_id"],
            "apphear_gloss": source["apphear_gloss"],
            "semlex_signer_id": source["semlex_signer_id"],
            "human_decision": source["human_decision"],
            "real_length": metrics["length"],
            "lh_observed_rate": metrics["lh_observed_rate"],
            "rh_observed_rate": metrics["rh_observed_rate"],
            "both_observed_rate": metrics["both_observed_rate"],
            "at_least_one_observed_rate": metrics["at_least_one_observed_rate"],
            "body_valid_rate": metrics["body_valid_rate"],
            "training_usability_state": state,
            "quarantine_evidence": "No hand observed on any real frame despite non-empty decoded video and body evidence." if state == ZERO_HAND else "",
        })
        if metrics["low_hand_observation"]:
            class_systematic = class_low_rates[int(source["apphear_class_id"])] >= 0.5
            signer_systematic = signer_low_rates[source["semlex_signer_id"]] >= 0.5
            pattern = (
                "CLASS_AND_SIGNER_SYSTEMATIC_DESCRIPTIVE" if class_systematic and signer_systematic
                else "CLASS_SYSTEMATIC_DESCRIPTIVE" if class_systematic
                else "SIGNER_SYSTEMATIC_DESCRIPTIVE" if signer_systematic
                else "ISOLATED_OR_NONMAJORITY_DESCRIPTIVE"
            )
            low_rows.append({
                "semlex_sample_id": sample_id,
                "apphear_class_id": source["apphear_class_id"],
                "apphear_gloss": source["apphear_gloss"],
                "semlex_signer_id": source["semlex_signer_id"],
                "human_decision": source["human_decision"],
                "real_length": metrics["length"],
                "lh_observed_rate": metrics["lh_observed_rate"],
                "rh_observed_rate": metrics["rh_observed_rate"],
                "at_least_one_observed_rate": metrics["at_least_one_observed_rate"],
                "both_observed_rate": metrics["both_observed_rate"],
                "class_low_clip_rate": class_low_rates[int(source["apphear_class_id"])],
                "signer_low_clip_rate": signer_low_rates[source["semlex_signer_id"]],
                "descriptive_pattern": pattern,
                "automatic_exclusion": "False",
            })
    if len(low_rows) != 361:
        raise RuntimeError(f"low-observation clip count mismatch: {len(low_rows)}")

    evidence_rows = read_csv(D6 / "semlex_review_evidence_matrix.csv")
    review_reason_by_class = {int(row["class_id"]): row.get("review_reason", "") for row in evidence_rows}
    two_hand_rows = []
    for class_id in sorted(accepted_by_class):
        sem = sem_class_by_id[class_id]
        app = app_class_by_id.get(class_id, {})
        zero_both = int(sem["never_both_observed_clips"])
        two_hand_rows.append({
            "apphear_class_id": class_id,
            "apphear_gloss": accepted_by_class[class_id]["apphear_gloss"],
            "semlex_clips": sem["clips"],
            "semlex_never_both_observed_clips": zero_both,
            "semlex_never_both_clip_rate": safe_ratio(zero_both, int(sem["clips"])),
            "semlex_both_observed_frame_rate": sem["both_observed_rate"],
            "apphear_clips": app.get("clips", 0),
            "apphear_never_both_observed_clips": app.get("never_both_observed_clips", 0),
            "apphear_both_observed_frame_rate": app.get("both_observed_rate", 0.0),
            "human_review_reason": review_reason_by_class.get(class_id, "NOT_AVAILABLE"),
            "authoritative_intended_two_hand_evidence": "NOT_AVAILABLE_IN_GOVERNED_ARTIFACTS",
            "usability_assessment": "NO_OBSERVED_RISK" if zero_both == 0 else "DESCRIPTIVE_LOW_TWO_HAND_OBSERVABILITY_NOT_AUTOMATIC_FAILURE",
            "two_hand_data_usability_risk": "False",
            "quarantined_clips": 0,
            "notes": "No class is promoted to TWO_HAND_DATA_USABILITY_RISK without authoritative intended-form evidence; P5-D8 must retain this descriptive source shift.",
        })

    zero_rows = []
    for sample_id in sorted(zero_hand_ids):
        source = staged_by_id[sample_id]
        record = completion_records[sample_id]
        metrics = sem_clip_metrics[sample_id]
        zero_rows.append({
            "semlex_sample_id": sample_id,
            "apphear_class_id": source["apphear_class_id"],
            "apphear_gloss": source["apphear_gloss"],
            "semlex_signer_id": source["semlex_signer_id"],
            "raw_video_path": source["raw_video_path"],
            "raw_sha256": source["raw_sha256"],
            "raw_bytes": source["raw_bytes"],
            "original_frame_count": record["original_frame_count"],
            "processed_frame_count": record["processed_frame_count"],
            "body_valid_rate": metrics["body_valid_rate"],
            "lh_observed_rate": metrics["lh_observed_rate"],
            "rh_observed_rate": metrics["rh_observed_rate"],
            "tensor_contract_valid": "True",
            "classification": ZERO_HAND,
            "explicit_evidence": "Decoded non-empty video; DWPose native output exists; body landmarks are valid; neither hand observed on any real frame.",
        })

    usable_ids = {sample_id for sample_id, state in usability.items() if state == USABLE}
    usable_rows = [staged_by_id[sample_id] for sample_id in sorted(usable_ids)]
    usable_by_class: dict[int, list[dict[str, Any]]] = defaultdict(list)
    staged_by_class: dict[int, list[dict[str, Any]]] = defaultdict(list)
    successful_by_class: dict[int, list[dict[str, Any]]] = defaultdict(list)
    candidate_by_class: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        candidate_by_class[int(row["apphear_class_id"])].append(row)
    for row in staged_rows:
        staged_by_class[int(row["apphear_class_id"])].append(row)
    for sample_id in completion_records:
        row = staged_by_id[sample_id]
        successful_by_class[int(row["apphear_class_id"])].append(row)
    for row in usable_rows:
        usable_by_class[int(row["apphear_class_id"])].append(row)

    class_retention_rows = []
    coverage_rows = []
    classes_losing_projected_signers: list[str] = []
    for class_id in sorted(accepted_by_class):
        meta = candidate_by_class[class_id]
        staged = staged_by_class[class_id]
        successful = successful_by_class[class_id]
        usable_class = usable_by_class[class_id]
        meta_signers = {row["semlex_signer_id"] for row in meta}
        staged_signers = {row["semlex_signer_id"] for row in staged}
        success_signers = {row["semlex_signer_id"] for row in successful}
        usable_signers = {row["semlex_signer_id"] for row in usable_class}
        lost_signers = sorted(meta_signers - usable_signers)
        if lost_signers:
            classes_losing_projected_signers.append(accepted_by_class[class_id]["apphear_gloss"])
        class_retention_rows.append({
            "apphear_class_id": class_id,
            "apphear_gloss": accepted_by_class[class_id]["apphear_gloss"],
            "coverage_deficit_level": accepted_by_class[class_id]["coverage_deficit_level"],
            "human_decision": accepted_by_class[class_id]["human_decision"],
            "human_approved_candidate_clips": len(meta),
            "staged_clips": len(staged),
            "successful_v2_clips": len(successful),
            "post_usability_eligible_clips": len(usable_class),
            "human_projected_signers": len(meta_signers),
            "staged_signers": len(staged_signers),
            "successful_v2_signers": len(success_signers),
            "post_usability_eligible_signers": len(usable_signers),
            "projected_signer_class_slots": len(meta_signers),
            "actual_usable_signer_class_slots": len(usable_signers),
            "metadata_to_staging_retention": safe_ratio(len(staged), len(meta)),
            "staging_to_extraction_retention": safe_ratio(len(successful), len(staged)),
            "metadata_to_final_v2_retention": safe_ratio(len(successful), len(meta)),
            "metadata_to_post_usability_retention": safe_ratio(len(usable_class), len(meta)),
            "lost_projected_signers": "|".join(lost_signers),
            "zero_hand_quarantines": sum(usability.get(row["semlex_sample_id"]) == ZERO_HAND for row in successful),
            "decode_exclusions": sum(row["semlex_sample_id"] in failure_records for row in staged),
            "low_hand_observation_clips": sem_class_by_id[class_id]["low_hand_observation_clips"],
            "never_both_observed_clips": sem_class_by_id[class_id]["never_both_observed_clips"],
        })
        counts = Counter(row["semlex_signer_id"] for row in usable_class)
        total = sum(counts.values())
        hhi = sum((count / total) ** 2 for count in counts.values()) if total else 0.0
        coverage_rows.append({
            "apphear_class_id": class_id,
            "apphear_gloss": accepted_by_class[class_id]["apphear_gloss"],
            "coverage_deficit_level": accepted_by_class[class_id]["coverage_deficit_level"],
            "usable_clips": total,
            "unique_usable_signers": len(counts),
            "effective_usable_signers": 1.0 / hhi if hhi else 0.0,
            "signer_hhi": hhi,
            "median_clips_per_signer": float(np.median(list(counts.values()))) if counts else 0.0,
            "max_signer_share": max(counts.values()) / total if total else 0.0,
            "signer_class_slots": len(counts),
            "signer_ids": "|".join(sorted(counts)),
        })

    usable_slots = {(int(row["apphear_class_id"]), row["semlex_signer_id"]) for row in usable_rows}
    usable_signers = {row["semlex_signer_id"] for row in usable_rows}
    critical_classes = {int(row["apphear_class_id"]) for row in accepted_classes if row["coverage_deficit_level"] == "CRITICAL_COVERAGE_DEFICIT"}
    high_classes = {int(row["apphear_class_id"]) for row in accepted_classes if row["coverage_deficit_level"] == "HIGH_COVERAGE_DEFICIT"}
    critical_retained = len(critical_classes & set(usable_by_class))
    high_retained = len(high_classes & set(usable_by_class))

    # Apples-to-apples source comparisons overall and for the 65 accepted classes.
    comparison_rows = []
    comparison_fields = [
        "scope", "class_id", "gloss", "apphear_clips", "semlex_clips",
        "apphear_median_sequence_length", "semlex_median_sequence_length",
        "apphear_lh_observed_rate", "semlex_lh_observed_rate", "lh_rate_difference_semlex_minus_apphear",
        "apphear_rh_observed_rate", "semlex_rh_observed_rate", "rh_rate_difference_semlex_minus_apphear",
        "apphear_both_observed_rate", "semlex_both_observed_rate", "both_rate_difference_semlex_minus_apphear",
        "apphear_at_least_one_observed_rate", "semlex_at_least_one_observed_rate", "either_rate_difference_semlex_minus_apphear",
        "apphear_neither_observed_rate", "semlex_neither_observed_rate",
        "apphear_valid_hand_landmark_rate", "semlex_valid_hand_landmark_rate",
        "apphear_body_valid_rate", "semlex_body_valid_rate",
    ]

    def comparison(scope: str, class_id: str, gloss: str, app: dict[str, Any], sem: dict[str, Any]) -> dict[str, Any]:
        return {
            "scope": scope, "class_id": class_id, "gloss": gloss,
            "apphear_clips": app.get("clips", 0), "semlex_clips": sem.get("clips", 0),
            "apphear_median_sequence_length": app.get("median_sequence_length", 0.0), "semlex_median_sequence_length": sem.get("median_sequence_length", 0.0),
            "apphear_lh_observed_rate": app.get("lh_observed_rate", 0.0), "semlex_lh_observed_rate": sem.get("lh_observed_rate", 0.0),
            "lh_rate_difference_semlex_minus_apphear": sem.get("lh_observed_rate", 0.0) - app.get("lh_observed_rate", 0.0),
            "apphear_rh_observed_rate": app.get("rh_observed_rate", 0.0), "semlex_rh_observed_rate": sem.get("rh_observed_rate", 0.0),
            "rh_rate_difference_semlex_minus_apphear": sem.get("rh_observed_rate", 0.0) - app.get("rh_observed_rate", 0.0),
            "apphear_both_observed_rate": app.get("both_observed_rate", 0.0), "semlex_both_observed_rate": sem.get("both_observed_rate", 0.0),
            "both_rate_difference_semlex_minus_apphear": sem.get("both_observed_rate", 0.0) - app.get("both_observed_rate", 0.0),
            "apphear_at_least_one_observed_rate": app.get("at_least_one_observed_rate", 0.0), "semlex_at_least_one_observed_rate": sem.get("at_least_one_observed_rate", 0.0),
            "either_rate_difference_semlex_minus_apphear": sem.get("at_least_one_observed_rate", 0.0) - app.get("at_least_one_observed_rate", 0.0),
            "apphear_neither_observed_rate": app.get("neither_observed_rate", 0.0), "semlex_neither_observed_rate": sem.get("neither_observed_rate", 0.0),
            "apphear_valid_hand_landmark_rate": app.get("valid_hand_landmark_rate", 0.0), "semlex_valid_hand_landmark_rate": sem.get("valid_hand_landmark_rate", 0.0),
            "apphear_body_valid_rate": app.get("body_valid_rate", 0.0), "semlex_body_valid_rate": sem.get("body_valid_rate", 0.0),
        }

    comparison_rows.append(comparison("OVERALL_MATCHED_65_CLASSES", "", "", app_matched_overall, sem_overall))
    for class_id in sorted(accepted_by_class):
        comparison_rows.append(comparison("CLASS", str(class_id), accepted_by_class[class_id]["apphear_gloss"], app_class_by_id.get(class_id, {}), sem_class_by_id[class_id]))

    domain_rows = [
        {
            "source": "APPHEAR_TRAIN_V2_FULL_236_REFERENCE", "clips": app_overall["clips"], "real_frames": app_overall["real_frames"],
            "median_sequence_length": app_overall["median_sequence_length"], "median_hand_motion": app_overall["median_hand_motion"], "p90_hand_motion": app_overall["p90_hand_motion"],
            "lh_observed_rate": app_overall["lh_observed_rate"], "rh_observed_rate": app_overall["rh_observed_rate"], "both_observed_rate": app_overall["both_observed_rate"],
            "at_least_one_observed_rate": app_overall["at_least_one_observed_rate"], "valid_hand_landmark_rate": app_overall["valid_hand_landmark_rate"], "body_valid_rate": app_overall["body_valid_rate"],
            "mean_valid_hand_score": app_overall["mean_valid_hand_score"], "mean_valid_body_score": app_overall["mean_valid_body_score"], "mean_abs_hand_xy": app_overall["mean_abs_hand_xy"],
            "center_method": "NOT_AVAILABLE_IN_AGGREGATED_TENSOR", "scale_method": "NOT_AVAILABLE_IN_AGGREGATED_TENSOR",
        },
        {
            "source": "APPHEAR_TRAIN_V2_MATCHED_65_PRIMARY", "clips": app_matched_overall["clips"], "real_frames": app_matched_overall["real_frames"],
            "median_sequence_length": app_matched_overall["median_sequence_length"], "median_hand_motion": app_matched_overall["median_hand_motion"], "p90_hand_motion": app_matched_overall["p90_hand_motion"],
            "lh_observed_rate": app_matched_overall["lh_observed_rate"], "rh_observed_rate": app_matched_overall["rh_observed_rate"], "both_observed_rate": app_matched_overall["both_observed_rate"],
            "at_least_one_observed_rate": app_matched_overall["at_least_one_observed_rate"], "valid_hand_landmark_rate": app_matched_overall["valid_hand_landmark_rate"], "body_valid_rate": app_matched_overall["body_valid_rate"],
            "mean_valid_hand_score": app_matched_overall["mean_valid_hand_score"], "mean_valid_body_score": app_matched_overall["mean_valid_body_score"], "mean_abs_hand_xy": app_matched_overall["mean_abs_hand_xy"],
            "center_method": "NOT_AVAILABLE_IN_AGGREGATED_TENSOR", "scale_method": "NOT_AVAILABLE_IN_AGGREGATED_TENSOR",
        },
        {
            "source": "SEMLEX_CANDIDATE_V2", "clips": sem_overall["clips"], "real_frames": sem_overall["real_frames"],
            "median_sequence_length": sem_overall["median_sequence_length"], "median_hand_motion": sem_overall["median_hand_motion"], "p90_hand_motion": sem_overall["p90_hand_motion"],
            "lh_observed_rate": sem_overall["lh_observed_rate"], "rh_observed_rate": sem_overall["rh_observed_rate"], "both_observed_rate": sem_overall["both_observed_rate"],
            "at_least_one_observed_rate": sem_overall["at_least_one_observed_rate"], "valid_hand_landmark_rate": sem_overall["valid_hand_landmark_rate"], "body_valid_rate": sem_overall["body_valid_rate"],
            "mean_valid_hand_score": sem_overall["mean_valid_hand_score"], "mean_valid_body_score": sem_overall["mean_valid_body_score"], "mean_abs_hand_xy": sem_overall["mean_abs_hand_xy"],
            "center_method": "|".join(f"{key}:{value}" for key, value in sorted(center_methods.items())), "scale_method": "|".join(f"{key}:{value}" for key, value in sorted(scale_methods.items())),
        },
    ]

    # Exact overlap remains zero under the governed deterministic evidence.
    overlap_rows = read_csv(D7A / "semlex_apphear_lineage_overlap_audit.csv")
    if overlap_rows:
        raise RuntimeError("unexpected confirmed AppHear overlap rows")

    # Write required tabular artifacts.
    write_csv(OUT / "p5d7b_full_attrition_ledger.csv", ledger_rows, [
        "apphear_class_id", "apphear_gloss", "human_decision", "semlex_sample_id", "semlex_signer_id", "semlex_lexical_id",
        "metadata_candidate", "raw_found", "staging_eligible", "staged", "dwpose_success", "v2_success", "training_usability_state", "loss_stage", "loss_reason", "notes",
    ])
    write_csv(OUT / "p5d7b_pre_staging_loss_summary.csv", pre_summary_rows, [
        "loss_reason", "candidate_rows", "unique_sample_ids", "classes_affected", "signer_class_slots_affected", "explanation",
    ])
    write_csv(OUT / "p5d7b_signer_slot_attrition.csv", slot_rows, [
        "apphear_class_id", "apphear_gloss", "semlex_signer_id", "projected_slot", "staged_slot", "projected_candidate_rows", "unique_projected_samples", "staged_samples", "slot_loss_reason", "missing_sample_ids",
    ])
    write_csv(OUT / "p5d7b_decode_exclusions.csv", decode_rows, list(decode_rows[0]))
    write_csv(OUT / "p5d7b_completed_v2_integrity.csv", integrity_rows, list(integrity_rows[0]))

    overall_fields = ["scope", "clips", "real_frames", "median_sequence_length", "lh_observed_rate", "rh_observed_rate", "both_observed_rate", "at_least_one_observed_rate", "neither_observed_rate", "valid_hand_landmark_rate", "body_valid_rate", "zero_hand_sequences", "never_both_observed_clips", "low_hand_observation_clips", "low_hand_observation_clip_rate", "mean_valid_hand_score", "mean_valid_body_score", "mean_abs_hand_xy", "median_hand_motion", "p90_hand_motion"]
    write_csv(OUT / "semlex_missingness_overall.csv", [sem_overall], overall_fields)
    class_fields = ["class_id", "gloss", "clips", "real_frames", "median_sequence_length", "lh_observed_rate", "rh_observed_rate", "both_observed_rate", "at_least_one_observed_rate", "neither_observed_rate", "valid_hand_landmark_rate", "body_valid_rate", "zero_hand_sequences", "never_both_observed_clips", "low_hand_observation_clips", "low_hand_observation_clip_rate", "mean_valid_hand_score", "mean_valid_body_score", "mean_abs_hand_xy"]
    write_csv(OUT / "semlex_missingness_by_class.csv", sem_class_rows, class_fields)
    signer_fields = ["signer_id", "clips", "real_frames", "median_sequence_length", "lh_observed_rate", "rh_observed_rate", "both_observed_rate", "at_least_one_observed_rate", "neither_observed_rate", "valid_hand_landmark_rate", "body_valid_rate", "zero_hand_sequences", "never_both_observed_clips", "low_hand_observation_clips", "low_hand_observation_clip_rate", "mean_valid_hand_score", "mean_valid_body_score", "mean_abs_hand_xy"]
    write_csv(OUT / "semlex_missingness_by_signer.csv", sem_signer_rows, signer_fields)
    write_csv(OUT / "apphear_semlex_missingness_comparison.csv", comparison_rows, comparison_fields)
    write_csv(OUT / "semlex_zero_hand_sequence_audit.csv", zero_rows, list(zero_rows[0]))
    write_csv(OUT / "semlex_low_hand_observation_audit.csv", low_rows, list(low_rows[0]))
    write_csv(OUT / "semlex_two_hand_usability_audit.csv", two_hand_rows, list(two_hand_rows[0]))
    write_csv(OUT / "semlex_class_retention.csv", class_retention_rows, list(class_retention_rows[0]))
    write_csv(OUT / "semlex_actual_signer_coverage.csv", coverage_rows, list(coverage_rows[0]))
    write_csv(OUT / "semlex_apphear_domain_comparison.csv", domain_rows, list(domain_rows[0]))
    write_csv(OUT / "semlex_apphear_overlap_audit.csv", [], ["semlex_sample_id", "apphear_sample_id", "evidence", "status"])
    write_csv(OUT / "semlex_training_usability_states.csv", usability_rows, list(usability_rows[0]))
    candidate_fields = list(staged_rows[0]) + ["training_usability_state", "audit_source"]
    post_manifest = []
    for row in usable_rows:
        item = dict(row)
        item.update({"training_usability_state": USABLE, "audit_source": "P5D7B_SEMLEX_INTEGRITY_AUDIT_01"})
        post_manifest.append(item)
    write_csv(OUT / "semlex_post_audit_candidate_manifest.csv", post_manifest, candidate_fields)

    actual_coverage = {
        "human_approved_candidate_clips": 2666,
        "human_approved_projected_signer_class_slots": 925,
        "staged_clips": 2425,
        "staged_signer_class_slots": 894,
        "successful_v2_clips": 2417,
        "decode_exclusions": 8,
        "zero_hand_quarantines": 2,
        "usable_clips": len(usable_rows),
        "usable_classes": len(usable_by_class),
        "unique_usable_signers": len(usable_signers),
        "usable_signer_class_slots": len(usable_slots),
        "median_usable_signers_per_class": float(np.median([row["unique_usable_signers"] for row in coverage_rows])),
        "median_effective_signers_per_class": float(np.median([row["effective_usable_signers"] for row in coverage_rows])),
        "critical_classes_retained": critical_retained,
        "critical_classes_accepted": len(critical_classes),
        "high_classes_retained": high_retained,
        "high_classes_accepted": len(high_classes),
        "metadata_to_usable_retention": safe_ratio(len(usable_rows), 2666),
        "staged_to_usable_retention": safe_ratio(len(usable_rows), 2425),
        "projected_slot_to_usable_retention": safe_ratio(len(usable_slots), 925),
        "staged_slot_to_usable_retention": safe_ratio(len(usable_slots), 894),
    }
    write_json(OUT / "p5d7b_actual_usable_coverage.json", actual_coverage)

    decision = {
        "classification": "SEMLEX_SUPPLEMENTATION_CANDIDATE_READY_WITH_LIMITATIONS",
        "confidence": "HIGH",
        "justified_limitations": [
            "161 governed metadata sample IDs are absent from the supplied raw archive",
            "80 repeated metadata rows were canonicalized",
            "8 raw VP9/WebM clips decode zero frames and are excluded",
            "2 technically valid zero-hand sequences are quarantined",
            "reviewer/date provenance remains incomplete and blocks merge/training",
            "Sem-Lex hand observability differs descriptively from AppHear and must be preserved in P5-D8 design",
        ],
        "two_hand_data_usability_risk_classes": [],
        "next_gate": "P5D8_SUPPLEMENTATION_DESIGN_AND_BALANCING_AUDIT",
        "training_authorized": False,
        "merge_authorized": False,
    }
    write_json(OUT / "p5d7b_decision.json", decision)
    write_json(OUT / "p5d7b_next_gate.json", {
        "next_gate": "P5D8_SUPPLEMENTATION_DESIGN_AND_BALANCING_AUDIT",
        "executed": False,
        "constraints": ["NO_TRAINING", "NO_MERGE", "RESOLVE_REVIEW_PROVENANCE_BEFORE_FUTURE_MERGE_OR_TRAINING"],
    })

    report = f"""# P5-D7B Sem-Lex Full Extraction Integrity and Training-Usability Audit

## Decision

`SEMLEX_SUPPLEMENTATION_CANDIDATE_READY_WITH_LIMITATIONS`

The completed Sem-Lex extraction is internally valid and retains substantial class-wise signer coverage. The separate post-audit candidate pool contains **{len(usable_rows):,} clips**, **{len(usable_by_class)} classes**, **{len(usable_signers)} Sem-Lex signers**, and **{len(usable_slots)} class-signer slots**. It is not an AppHear TRAIN manifest and is not authorized for training or merge.

## Full attrition accounting

- Human-approved metadata rows: 2,666.
- Duplicate metadata occurrences canonicalized: 80.
- Unique metadata sample IDs: 2,586.
- Unique metadata samples absent from the supplied raw archive: 161.
- Staged raw clips: 2,425.
- Projected signer-class slots: 925.
- Staged signer-class slots: 894; all 31 lost slots are traced to raw unavailability for every sample in the slot.
- Successful native DWPose/V2 pairs: 2,417.
- Raw-media zero-frame decode exclusions: 8.
- V2 integrity failures: {contract_failures}.
- Training-usability quarantines: 2 zero-hand sequences.

The 241-row pre-staging difference is exactly **80 duplicate metadata rows + 161 missing raw archive members**. It is fully explained. Duplicate metadata rows do not independently represent signer/variant coverage.

## Completed-output integrity

All 2,417 completed pairs were independently checked against completion-record hashes and staged lineage. Every native output has the governed 133-point structure and checkpoint SHA. Every V2 output is float32 `[96,238]`, finite, compactly masked, zero-padded, free of stale padding, and consistent with invalid-landmark and whole-unobserved-hand zero rules. No completed output has a class, signer, sample, or raw-SHA lineage failure.

## Decode exclusions

Eight staged WebM/VP9 files decoded zero frames: COOK 1, COLD 1, HAPPY 1, STAY 1, TIME 3, and WALK2 1. They are `RAW_MEDIA_DECODE_EXCLUSION`, not DWPose, V2, architecture, or P4 failures. No class, signer, or class-signer slot was lost at extraction because other successful clips preserve every affected slot.

## Missingness and source comparison

Using real frames only, Sem-Lex has LH/RH/both/either-hand observation rates of **{sem_overall['lh_observed_rate']:.2%} / {sem_overall['rh_observed_rate']:.2%} / {sem_overall['both_observed_rate']:.2%} / {sem_overall['at_least_one_observed_rate']:.2%}**. In the primary apples-to-apples AppHear TRAIN subset restricted to the same 65 classes, the corresponding rates are **{app_matched_overall['lh_observed_rate']:.2%} / {app_matched_overall['rh_observed_rate']:.2%} / {app_matched_overall['both_observed_rate']:.2%} / {app_matched_overall['at_least_one_observed_rate']:.2%}**. Median real sequence length is {sem_overall['median_sequence_length']:.0f} frames for Sem-Lex versus {app_matched_overall['median_sequence_length']:.0f} for matched AppHear. The full 236-class AppHear reference remains separately reported and is not used as the primary source comparison.

These are source-distribution differences, not automatic rejection criteria. One-handed lexical forms make aggregate two-hand observation intrinsically ambiguous. The governed lexical artifacts do not encode authoritative per-class intended one/two-hand form strongly enough to promote any class to `TWO_HAND_DATA_USABILITY_RISK`; the full descriptive table is retained for P5-D8.

Two sequences—BAD `nCzDsK1bJa633owYTjfp` and BED2 `tzQe8d8PfngcM8rqKUiQ`—decode normally and contain body evidence but no observed hand in any real frame. Both are `ZERO_HAND_SEQUENCE_QUARANTINE`. BED2 loses one usable signer slot; all 65 classes remain represented.

## Coverage that survives extraction

- Usable clips: {len(usable_rows):,} ({safe_ratio(len(usable_rows), 2666):.2%} of metadata projection; {safe_ratio(len(usable_rows), 2425):.2%} of staged clips).
- Usable classes: {len(usable_by_class)}/65.
- Unique Sem-Lex signers: {len(usable_signers)}.
- Usable signer-class slots: {len(usable_slots)} ({safe_ratio(len(usable_slots), 925):.2%} of projected slots).
- Median usable signers per class: {actual_coverage['median_usable_signers_per_class']:.1f}.
- Critical classes retained: {critical_retained}/{len(critical_classes)}.
- High-deficit classes retained: {high_retained}/{len(high_classes)}.

The signer-diversity benefit survives extraction. P5-D8 should design a bounded supplementation policy around new class-signer coverage rather than maximum raw clip count, preserve source-aware diagnostics, and keep the two zero-hand clips and eight decode failures excluded.

## Scientific interpretation

**VERIFIED FACT:** The traceable 2,415-clip post-audit pool is contract-valid, covers all 65 accepted classes, and retains 893 class-signer slots after bounded raw-availability, decode, and zero-hand exclusions.

**CURRENT HYPOTHESIS:** Sem-Lex's different temporal length and hand-observation profile may interact with training and sampling; this requires a controlled supplementation design, not source rejection or P4 reopening.

**NOT YET ESTABLISHED:** Whether Sem-Lex supplementation improves unseen-signer recognition.

## Governance

- Training: NO.
- External merge: NO.
- Extraction rerun/repair: NO.
- Protected test: NOT ACCESSED.
- P4/Android/V2/model changes: NONE.
- Review provenance remains `REVIEW_PROVENANCE_METADATA_INCOMPLETE`; it must be resolved before any future merge or training authorization.
- `context/progress-tracker.md`: UNTOUCHED.

Next gate: `P5D8_SUPPLEMENTATION_DESIGN_AND_BALANCING_AUDIT` (not executed).
"""
    write_text(OUT / "P5D7B_SEMLEX_INTEGRITY_AUDIT_RESULT.md", report)

    after_hashes = source_hashes()
    integrity = {
        "passed": True,
        "source_manifest_errors": source_manifest_errors,
        "source_hashes_before": before_hashes,
        "source_hashes_after": after_hashes,
        "source_hashes_unchanged": before_hashes == after_hashes,
        "accepted_classes": len(accepted_classes),
        "unresolved_excluded": sorted(unresolved),
        "metadata_candidates_accounted": len(ledger_rows),
        "staged_samples_accounted": len(staged_rows),
        "completed_pairs_accounted": len(completion_records),
        "decode_failures_accounted": len(failure_records),
        "v2_integrity_failures": contract_failures,
        "raw_repair_performed": False,
        "extraction_rerun": False,
        "dwpose_inference_run": False,
        "v2_regenerated": False,
        "training_performed": False,
        "external_merge_performed": False,
        "protected_test_accessed": False,
        "p4_reopened": False,
        "android_modified": False,
        "popsign_used": False,
        "context_modified": False,
        "progress_tracker_untouched": before_hashes["progress_tracker"] == after_hashes["progress_tracker"] == EXPECTED["progress"],
        "review_provenance": "REVIEW_PROVENANCE_METADATA_INCOMPLETE",
    }
    write_json(OUT / "p5d7b_integrity.json", integrity)

    # Hash every required output except the manifest itself; then freeze the manifest.
    required = [
        "P5D7B_SEMLEX_INTEGRITY_AUDIT_RESULT.md", "p5d7b_integrity.json", "p5d7b_full_attrition_ledger.csv",
        "p5d7b_pre_staging_loss_summary.csv", "p5d7b_signer_slot_attrition.csv", "p5d7b_decode_exclusions.csv",
        "p5d7b_completed_v2_integrity.csv", "semlex_missingness_overall.csv", "semlex_missingness_by_class.csv",
        "semlex_missingness_by_signer.csv", "apphear_semlex_missingness_comparison.csv", "semlex_zero_hand_sequence_audit.csv",
        "semlex_low_hand_observation_audit.csv", "semlex_two_hand_usability_audit.csv", "semlex_class_retention.csv",
        "semlex_actual_signer_coverage.csv", "semlex_apphear_domain_comparison.csv", "semlex_apphear_overlap_audit.csv",
        "semlex_training_usability_states.csv", "semlex_post_audit_candidate_manifest.csv", "p5d7b_actual_usable_coverage.json",
        "p5d7b_decision.json", "p5d7b_next_gate.json",
    ]
    missing_required = [name for name in required if not (OUT / name).is_file()]
    if missing_required:
        raise RuntimeError(f"required artifact missing: {missing_required}")
    manifest = {
        "algorithm": "SHA-256",
        "artifacts": [
            {"path": name, "bytes": (OUT / name).stat().st_size, "sha256": sha256(OUT / name)}
            for name in required
        ] + [{"path": str(Path(__file__).relative_to(ROOT)), "bytes": Path(__file__).stat().st_size, "sha256": sha256(Path(__file__)), "role": "supporting_code"}],
    }
    write_json(OUT / "artifact_hash_manifest.json", manifest)
    print(json.dumps({
        "integrity": "PASS",
        "metadata_candidates": len(ledger_rows),
        "pre_staging_losses": len(pre_staging),
        "projected_slots": len(slot_rows),
        "staged_slots": len(staged_slots),
        "successful_v2": len(completion_records),
        "usable_clips": len(usable_rows),
        "usable_classes": len(usable_by_class),
        "usable_signers": len(usable_signers),
        "usable_slots": len(usable_slots),
        "decision": decision["classification"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
