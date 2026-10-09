"""Exact same-observation Android/host parity gate for the frozen Phase-7 S2.

This utility consumes only a debug phone capture produced with
``s2_exact_parity_capture=true``. It never reruns perception from JPEGs and never trains.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.perception_vnext.recognition_schema import RAW_SCHEMA, RawSequence  # noqa: E402
from pipeline.perception_vnext.segmentation.learned_features import (  # noqa: E402
    FEATURE_WIDTH,
    SEGMENTATION_FEATURE_SCHEMA,
    apply_normalization,
    derive_causal_segmentation_features,
)

BASE = ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
OUT = BASE / "phone_s2_exact_parity_and_r2_decision_01"
PHASE7 = BASE / "phase7_production_cadence_aligned_segmenter_01"
CHECKPOINT = PHASE7 / "best_model.keras"
NORMALIZATION = PHASE7 / "cadence_aligned_normalization_stats.json"
EXPECTED_CHECKPOINT_SHA = "dea7cf986d39ce252eb197ae7e130d2d66a101d03fde27427192bbf70ce35e73"
EXPECTED_NORMALIZATION_SHA = "3018348ae8cc9fe0671eda913535556e14cebf5a16fbe72a96be73ed494e9130"
EXPECTED_ATTEMPTS = ("HELLO", "HELLO", "HOME", "HOME", "TABLE", "TABLE")
FEATURE_TOLERANCE = 1.0e-6
NORMALIZATION_TOLERANCE = 1.0e-6
PROBABILITY_TOLERANCE = 1.0e-4


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def array(root: Path, name: str, dtype: str, shape: tuple[int, ...]) -> np.ndarray:
    value = np.fromfile(root / name, dtype=dtype)
    expected = int(np.prod(shape))
    if value.size != expected:
        raise ValueError(f"PARITY_CAPTURE_ARRAY_SHAPE_MISMATCH:{name}:{value.size}:{expected}")
    return value.reshape(shape)


@dataclass(frozen=True)
class Capture:
    session: Path
    count: int
    raw: RawSequence
    android_features: np.ndarray
    android_normalized: np.ndarray
    android_probabilities: np.ndarray
    android_argmax: np.ndarray
    history_length: np.ndarray
    linkage: list[dict[str, str]]
    manifest: dict[str, Any]


def load_capture(session: Path, *, require_full_session: bool = True) -> Capture:
    if "<CAPTURED_SESSION>" in str(session):
        raise ValueError(
            "REPLACE_CAPTURED_SESSION_PLACEHOLDER_WITH_REAL_SESSION_NAME; "
            "for example session_20260921T153138Z"
        )
    session = session.resolve()
    if not session.is_dir():
        raise FileNotFoundError(f"PHONE_S2_EXACT_PARITY_SESSION_DIRECTORY_MISSING:{session}")
    parity = session / "s2_exact_parity"
    manifest = read_json(parity / "manifest.json")
    if manifest.get("schema") != "apphear.phone_s2_exact_parity_capture.v1":
        raise ValueError("PARITY_CAPTURE_SCHEMA_MISMATCH")
    if manifest.get("raw_schema") != RAW_SCHEMA:
        raise ValueError("PARITY_CAPTURE_RAW_SCHEMA_MISMATCH")
    if manifest.get("feature_schema") != SEGMENTATION_FEATURE_SCHEMA:
        raise ValueError("PARITY_CAPTURE_FEATURE_SCHEMA_MISMATCH")
    count = int(manifest["observation_count"])
    if count <= 0 or count > int(manifest["maximum_observations"]):
        raise ValueError("PARITY_CAPTURE_COUNT_INVALID")
    for name, identity in manifest["files"].items():
        path = parity / name
        if sha256(path) != identity["sha256"]:
            raise ValueError(f"PARITY_CAPTURE_HASH_MISMATCH:{name}")
        if path.stat().st_size != count * int(identity["bytes_per_observation"]):
            raise ValueError(f"PARITY_CAPTURE_SIZE_MISMATCH:{name}")
    if sha256(parity / "linkage.csv") != manifest["linkage_sha256"]:
        raise ValueError("PARITY_CAPTURE_LINKAGE_HASH_MISMATCH")
    linkage = read_rows(parity / "linkage.csv")
    if len(linkage) != count:
        raise ValueError("PARITY_CAPTURE_LINKAGE_COUNT_MISMATCH")

    source_index = array(parity, "source_index.i32", "<i4", (count,))
    timestamp = array(parity, "timestamp_ms.f64", "<f8", (count,))
    source_size = array(parity, "source_size.i32", "<i4", (count, 2))
    if not np.array_equal(source_index, np.arange(count, dtype=np.int32)):
        raise ValueError("PARITY_CAPTURE_NONCONTIGUOUS_SOURCE_INDEX")
    if not np.all(np.diff(timestamp) > 0):
        raise ValueError("PARITY_CAPTURE_NONCHRONOLOGICAL_TIMESTAMP")
    for index, row in enumerate(linkage):
        record_mismatch = int(row["record_index"]) != index
        source_mismatch = int(row["source_index"]) != int(source_index[index])
        if record_mismatch or source_mismatch:
            raise ValueError(f"PARITY_CAPTURE_LINKAGE_INDEX_MISMATCH:{index}")
        if float(row["timestamp_ms"]) != float(timestamp[index]):
            raise ValueError(f"PARITY_CAPTURE_LINKAGE_TIMESTAMP_MISMATCH:{index}")

    raw = RawSequence(
        metadata={"schema": RAW_SCHEMA, "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB"},
        frame_index=source_index,
        timestamp_ms=timestamp,
        source_size=source_size,
        hand_xy=array(parity, "raw_hand_xy.f32", "<f4", (count, 2, 21, 2)),
        hand_proposal_support=array(
            parity, "raw_hand_proposal_support.f32", "<f4", (count, 2, 21)
        ),
        hand_joint_valid=array(
            parity, "raw_hand_joint_valid.u8", "u1", (count, 2, 21)
        ).astype(bool),
        hand_presence=array(parity, "raw_hand_presence.f32", "<f4", (count, 2)),
        hand_observed=array(parity, "raw_hand_observed.u8", "u1", (count, 2)).astype(bool),
        hand_proposal_present=array(
            parity, "raw_hand_proposal_present.u8", "u1", (count, 2)
        ).astype(bool),
        hand_roi_center_side=array(
            parity, "raw_hand_roi_center_side.f32", "<f4", (count, 2, 3)
        ),
        hand_handedness_diagnostic=np.full((count, 2), np.nan, np.float32),
        body_xy=array(parity, "raw_body_xy.f32", "<f4", (count, 8, 2)),
        body_support=array(parity, "raw_body_support.f32", "<f4", (count, 8)),
        body_valid=array(parity, "raw_body_valid.u8", "u1", (count, 8)).astype(bool),
        body_available=array(parity, "raw_body_available.u8", "u1", (count,)).astype(bool),
    )
    raw.validate()
    capture = Capture(
        session=session,
        count=count,
        raw=raw,
        android_features=array(parity, "android_features.f32", "<f4", (count, FEATURE_WIDTH)),
        android_normalized=array(
            parity, "android_normalized.f32", "<f4", (count, FEATURE_WIDTH)
        ),
        android_probabilities=array(
            parity, "android_probabilities.f32", "<f4", (count, 3)
        ),
        android_argmax=array(parity, "android_argmax.u8", "u1", (count,)),
        history_length=array(parity, "history_length.i32", "<i4", (count,)),
        linkage=linkage,
        manifest=manifest,
    )
    expected_history = np.minimum(np.arange(count, dtype=np.int32) + 1, 61)
    if not np.array_equal(capture.history_length, expected_history):
        raise ValueError("PARITY_CAPTURE_HISTORY_LENGTH_MISMATCH")
    if not np.all(np.isfinite(capture.android_probabilities)):
        raise ValueError("PARITY_CAPTURE_NONFINITE_PROBABILITY")
    if not np.allclose(capture.android_probabilities.sum(axis=1), 1.0, atol=1.0e-5):
        raise ValueError("PARITY_CAPTURE_PROBABILITY_SUM_MISMATCH")
    if not np.array_equal(
        np.argmax(capture.android_probabilities, axis=1).astype(np.uint8),
        capture.android_argmax,
    ):
        raise ValueError("PARITY_CAPTURE_ARGMAX_MISMATCH")
    if require_full_session:
        validate_session_integrity(capture)
    return capture


def validate_session_integrity(capture: Capture) -> None:
    session = capture.session
    identity = read_json(session / "identity.json")
    session_identity = read_json(session / "session_identity.json")
    if not identity.get("exact_s2_parity_capture_enabled"):
        raise ValueError("PARITY_CAPTURE_IDENTITY_NOT_ENABLED")
    if not session_identity.get("s2_exact_parity_capture_enabled"):
        raise ValueError("PARITY_CAPTURE_SESSION_IDENTITY_NOT_ENABLED")
    if identity["segmentation"]["source_checkpoint_sha256"] != EXPECTED_CHECKPOINT_SHA:
        raise ValueError("PARITY_CAPTURE_S2_IDENTITY_MISMATCH")
    if identity["segmentation"]["source_normalization_sha256"] != EXPECTED_NORMALIZATION_SHA:
        raise ValueError("PARITY_CAPTURE_NORMALIZATION_IDENTITY_MISMATCH")
    observation_lines = (session / "observations.jsonl").read_text().splitlines()
    observations = sum(1 for line in observation_lines if line)
    if observations != capture.count:
        raise ValueError(
            f"PARITY_CAPTURE_OBSERVATION_COUNT_MISMATCH:{observations}:{capture.count}"
        )
    attempt_lines = (session / "attempts.jsonl").read_text().splitlines()
    attempts = [json.loads(line) for line in attempt_lines if line]
    completed = tuple(row["expected_gloss"] for row in attempts if row["action"] == "COMPLETE")
    if completed != EXPECTED_ATTEMPTS:
        raise ValueError(f"PARITY_CAPTURE_ATTEMPT_POPULATION_MISMATCH:{completed}")
    visual = read_json(session / "continuous_visual/evidence_summary.json")
    originals = len(list((session / "continuous_visual/originals").glob("frame_*_original.jpg")))
    if (
        visual.get("finalized_after_capture_stop") is not True
        or int(visual["observation_frames_saved"]) != capture.count
        or int(visual["verified_original_files"]) != capture.count
        or originals != capture.count
    ):
        raise ValueError("PARITY_CAPTURE_VISUAL_EVIDENCE_INCOMPLETE")


def comparison(reference: np.ndarray, android: np.ndarray, tolerance: float) -> dict[str, Any]:
    difference = np.abs(np.asarray(reference, np.float64) - np.asarray(android, np.float64))
    per_row = np.max(difference.reshape(len(difference), -1), axis=1)
    return {
        "shape": list(android.shape),
        "tolerance": tolerance,
        "maximum_absolute_difference": float(difference.max(initial=0.0)),
        "mean_absolute_difference": float(difference.mean()),
        "rows_exceeding_tolerance": int(np.count_nonzero(per_row > tolerance)),
        "first_row_exceeding_tolerance": (
            int(np.flatnonzero(per_row > tolerance)[0])
            if np.any(per_row > tolerance)
            else None
        ),
        "pass": bool(np.all(difference <= tolerance)),
    }


def audit(session: Path) -> dict[str, Any]:
    capture = load_capture(session)
    result = {
        "status": "PHONE_S2_EXACT_PARITY_CAPTURE_INTEGRITY_PASS",
        "session": capture.session.name,
        "observations": capture.count,
        "attempts": list(EXPECTED_ATTEMPTS),
        "visual_originals": capture.count,
        "same_observation_linkage": True,
        "training_executed": False,
    }
    output = OUT / "captures" / capture.session.name
    write_json(output / "capture_integrity.json", result)
    return result


def parity(session: Path) -> dict[str, Any]:
    capture = load_capture(session)
    if sha256(CHECKPOINT) != EXPECTED_CHECKPOINT_SHA:
        raise RuntimeError("FROZEN_S2_CHECKPOINT_IDENTITY_MISMATCH")
    if sha256(NORMALIZATION) != EXPECTED_NORMALIZATION_SHA:
        raise RuntimeError("FROZEN_S2_NORMALIZATION_IDENTITY_MISMATCH")
    stats = read_json(NORMALIZATION)
    mean = np.asarray(stats["mean"], np.float32)
    std = np.asarray(stats["std"], np.float32)
    host_features = derive_causal_segmentation_features(capture.raw)
    feature_result = comparison(host_features, capture.android_features, FEATURE_TOLERANCE)
    host_normalized = apply_normalization(host_features, mean, std)
    normalization_result = comparison(
        host_normalized, capture.android_normalized, NORMALIZATION_TOLERANCE
    )

    probability_result: dict[str, Any]
    state_result: dict[str, Any]
    if feature_result["pass"] and normalization_result["pass"]:
        import tensorflow as tf

        model = tf.keras.models.load_model(CHECKPOINT, compile=False)
        logits = np.asarray(model(host_normalized[None], training=False), np.float32)[0]
        shifted = logits - np.max(logits, axis=-1, keepdims=True)
        host_probabilities = np.exp(shifted) / np.sum(np.exp(shifted), axis=-1, keepdims=True)
        probability_result = comparison(
            host_probabilities, capture.android_probabilities, PROBABILITY_TOLERANCE
        )
        host_argmax = np.argmax(host_probabilities, axis=1).astype(np.uint8)
        mismatches = np.flatnonzero(host_argmax != capture.android_argmax)
        state_result = {
            "mismatch_count": int(len(mismatches)),
            "first_mismatch": int(mismatches[0]) if len(mismatches) else None,
            "pass": len(mismatches) == 0,
        }
    else:
        probability_result = {"pass": False, "not_evaluated": True}
        state_result = {"pass": False, "not_evaluated": True}

    if not feature_result["pass"]:
        decision, first = "MATERIAL_PARITY_FAIL", "RAW_V1_TO_378_FEATURES"
    elif not normalization_result["pass"]:
        decision, first = "MATERIAL_PARITY_FAIL", "NORMALIZATION"
    elif not probability_result["pass"] or not state_result["pass"]:
        decision, first = "MATERIAL_PARITY_FAIL", "S2_RUNTIME_OUTPUT"
    else:
        decision, first = "PARITY_PASS_S2_DOMAIN_CORRECTION_SUPPORTED", None
    result = {
        "milestone": "PHONE_S2_EXACT_PARITY_AND_R2_DECISION_01",
        "session": capture.session.name,
        "observations": capture.count,
        "feature_parity": feature_result,
        "normalization_parity": normalization_result,
        "s2_probability_parity": probability_result,
        "s2_state_parity": state_result,
        "first_material_divergence": first,
        "decision": decision,
        "training_executed": False,
        "protected_test_accessed": False,
    }
    output = OUT / "captures" / capture.session.name
    write_json(output / "exact_parity_result.json", result)
    write_json(output / "final_decision.json", {"decision": decision, "first_divergence": first})
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("audit-capture", "parity"))
    parser.add_argument("session", type=Path)
    args = parser.parse_args()
    result = audit(args.session) if args.command == "audit-capture" else parity(args.session)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
