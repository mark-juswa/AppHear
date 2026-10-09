"""Blind Phase-6 frozen learned-segmenter replay over retained phone raw-v1.

This stage intentionally has no access to human boundaries, expected glosses,
recognition-v2, or a recognizer.  It freezes model predictions and learned events
before the separate comparison stage is allowed to open those artifacts.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics.finalize_phase4a_gate4a1 import load_raw  # noqa: E402

MILESTONE = "PHASE_6_FROZEN_LEARNED_SEGMENTER_END_TO_END_PHONE_REPLAY_01"
ATTEMPTS = tuple(f"attempt_{index:03d}" for index in range(1, 11))
SESSION_ID = "session_20260915T065635Z"
BASE = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
)
SESSION = BASE / (
    "phase4a_gate4a1b_controlled_live_input_recovery_01/" + SESSION_ID
)
P5 = BASE / "phase5_1t_3_first_class_agnostic_segmenter_01"
OUT = BASE / "phase6_frozen_learned_segmenter_phone_replay_01"

IDENTITIES = {
    "training_config": (
        P5 / "training_config.json",
        "fd432e02739810050ae7194d0565856a086ae4672e782562794a2b55cc06e941",
    ),
    "best_model": (
        P5 / "best_model.keras",
        "8fb6830e278b89af947defbbaf8f8b509ad24476caf49a008e8687478bf3528c",
    ),
    "normalization": (
        P5 / "normalization_stats.json",
        "04436433ac0cbedaf14bc2e1f05c15f188016ce055b1e96e00f0751ac93951d9",
    ),
    "feature_schema": (
        P5 / "feature_schema.json",
        "71d8b66c601990069a87ea5f04786447b66ef535e1a01e14e283704d2357d363",
    ),
    "feature_implementation": (
        ROOT / "pipeline/perception_vnext/segmentation/learned_features.py",
        "dfb5e9c2877881ab676d7c463739455b797e95679dfbe1e25866b26e8908f5f9",
    ),
    "decoder_reference": (
        ROOT / "eval/runtime_diagnostics/phase5_1t_first_segmenter.py",
        "cd9460465a1c84b9e76fc9d0303f66db7cd5f5e052d971cc61f33b3ba95757a3",
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def freeze_json(path: Path, value: Any) -> None:
    """Write once, or prove an existing freeze is byte-identical."""

    payload = canonical_json_bytes(value)
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"FROZEN_LEARNED_EVENT_MUTATION_REFUSED:{path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def verify_identities() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, (path, expected) in IDENTITIES.items():
        actual = sha256(path)
        result[name] = {
            "path": str(path.resolve()),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "match": actual == expected,
        }
        if actual != expected:
            raise RuntimeError(f"PHASE6_FROZEN_IDENTITY_MISMATCH:{name}:{actual}")
    config = read_json(IDENTITIES["training_config"][0])
    decoder = config["decoding"]
    expected_decoder = {
        "active_decision": "ARGMAX_CLASS_1",
        "short_gap_merge_ms": 150.0,
        "primary_run": (
            "MAX_ACTIVE_PROBABILITY_TIME_INTEGRAL_THEN_DURATION_THEN_EARLIEST"
        ),
        "pre_padding_ms": 250.0,
        "post_padding_ms": 250.0,
        "probability_threshold": None,
    }
    if decoder != expected_decoder:
        raise RuntimeError("PHASE6_FROZEN_IDENTITY_MISMATCH:decoder")
    feature_schema = read_json(IDENTITIES["feature_schema"][0])
    if feature_schema.get("schema") != "apphear.perception_vnext.segmentation_features.v1":
        raise RuntimeError("PHASE6_FROZEN_IDENTITY_MISMATCH:feature_schema_name")
    if int(feature_schema.get("width", -1)) != 378:
        raise RuntimeError("PHASE6_FROZEN_IDENTITY_MISMATCH:feature_width")
    return {
        "schema": "apphear.phase6.frozen_segmenter_identity.v1",
        "milestone": MILESTONE,
        "session_id": SESSION_ID,
        "attempt_ids": list(ATTEMPTS),
        "identities": result,
        "decoder": decoder,
        "feature_contract": {
            "schema": feature_schema["schema"],
            "width": int(feature_schema["width"]),
        },
        "all_match": True,
    }


def distribution(values: np.ndarray) -> dict[str, Any]:
    array = np.asarray(values, np.float64).reshape(-1)
    if len(array) == 0:
        return {"count": 0}
    return {
        "count": len(array),
        "min": float(np.min(array)),
        "p10": float(np.percentile(array, 10)),
        "p25": float(np.percentile(array, 25)),
        "median": float(np.median(array)),
        "mean": float(np.mean(array)),
        "p75": float(np.percentile(array, 75)),
        "p90": float(np.percentile(array, 90)),
        "max": float(np.max(array)),
    }


def z_diagnostic(values: np.ndarray) -> dict[str, Any]:
    absolute = np.abs(np.asarray(values, np.float64).reshape(-1))
    result = {"absolute_z": distribution(absolute)}
    for threshold in (3, 5, 10):
        result[f"fraction_abs_z_gt_{threshold}"] = (
            float(np.mean(absolute > threshold)) if len(absolute) else 0.0
        )
    return result


def delta_diagnostic(
    normalized: np.ndarray,
    value_slice: slice,
    valid: np.ndarray,
) -> dict[str, Any]:
    values = np.asarray(normalized[:, value_slice], np.float64)
    valid_mask = np.asarray(valid, bool)
    return {
        "all_dimensions": z_diagnostic(values),
        "valid_transition_dimensions": z_diagnostic(values[valid_mask]),
        "valid_fraction": float(np.mean(valid_mask)) if valid_mask.size else 0.0,
    }


def load_phone_inputs() -> tuple[list[dict[str, Any]], list[Any]]:
    if SESSION.name != SESSION_ID or not SESSION.is_dir():
        raise RuntimeError("PHASE6_SOURCE_SESSION_IDENTITY_FAILURE")
    actual_attempts = tuple(
        path.name for path in sorted(SESSION.iterdir()) if path.is_dir()
    )
    if actual_attempts != ATTEMPTS:
        raise RuntimeError(f"PHASE6_PHONE_POPULATION_FAILURE:{actual_attempts}")
    manifest_rows: list[dict[str, Any]] = []
    sequences: list[Any] = []
    for attempt in ATTEMPTS:
        path = SESSION / attempt / "raw_v1.json"
        raw, _ = load_raw(path)
        timestamps = np.asarray(raw.timestamp_ms, np.float64)
        if len(timestamps) == 0 or not np.all(np.diff(timestamps) > 0):
            raise RuntimeError(f"PHASE6_NONCHRONOLOGICAL_PHONE_RAW:{attempt}")
        duration = float(timestamps[-1] - timestamps[0])
        effective_hz = (len(timestamps) - 1) * 1000.0 / duration
        manifest_rows.append(
            {
                "attempt_id": attempt,
                "raw_v1_path": str(path.resolve()),
                "raw_v1_sha256": sha256(path),
                "observation_count": len(timestamps),
                "first_source_timestamp_ms": float(timestamps[0]),
                "last_source_timestamp_ms": float(timestamps[-1]),
                "duration_ms": duration,
                "effective_observation_hz": effective_hz,
                "chronological": True,
                "resampled": False,
                "interpolated": False,
                "duplicated": False,
            }
        )
        sequences.append(raw)
    return manifest_rows, sequences


def run_blind_freeze() -> dict[str, Any]:
    identities = verify_identities()
    write_json(OUT / "frozen_identity.json", identities)
    manifest_rows, sequences = load_phone_inputs()
    manifest = {
        "schema": "apphear.phase6.phone_input_manifest.v1",
        "milestone": MILESTONE,
        "session_id": SESSION_ID,
        "attempt_count": len(manifest_rows),
        "attempt_ids": list(ATTEMPTS),
        "source_stream": "ORIGINAL_RETAINED_CHRONOLOGICAL_CANDIDATE01_RAW_V1",
        "candidate01_rerun": False,
        "timestamp_modification": False,
        "rows": manifest_rows,
    }
    write_json(OUT / "phone_input_manifest.json", manifest)

    # Imports happen only after every frozen segmenter identity has matched.
    import tensorflow as tf

    from eval.runtime_diagnostics.phase5_1t_first_segmenter import (
        decode_event,
        softmax,
    )
    from pipeline.perception_vnext.segmentation.learned_features import (
        apply_normalization,
        derive_causal_segmentation_features,
    )

    normalization = read_json(IDENTITIES["normalization"][0])
    mean = np.asarray(normalization["mean"], np.float32)
    std = np.asarray(normalization["std"], np.float32)
    if mean.shape != (378,) or std.shape != (378,):
        raise RuntimeError("PHASE6_FROZEN_IDENTITY_MISMATCH:normalization_shape")
    config = read_json(IDENTITIES["training_config"][0])
    model = tf.keras.models.load_model(IDENTITIES["best_model"][0], compile=False)
    if model.count_params() != 123_779:
        raise RuntimeError(f"PHASE6_FROZEN_IDENTITY_MISMATCH:model_params:{model.count_params()}")

    prediction_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    aggregate_values: defaultdict[str, list[np.ndarray]] = defaultdict(list)
    for manifest_row, raw in zip(manifest_rows, sequences, strict=True):
        attempt = manifest_row["attempt_id"]
        timestamps = np.asarray(raw.timestamp_ms, np.float64)
        relative = timestamps - timestamps[0]
        features = derive_causal_segmentation_features(raw)
        normalized = apply_normalization(features, mean, std)
        logits = model(normalized[None], training=False).numpy()[0]
        probabilities = softmax(logits)
        states = np.argmax(probabilities, axis=1).astype(np.int32)
        event = decode_event(relative, probabilities, float(relative[-1]), config)
        if event is None:
            event_row = {
                "attempt_id": attempt,
                "event_emitted": False,
                "start_index": None,
                "end_index": None,
                "decoder_event": None,
            }
        else:
            retained = np.flatnonzero(
                (relative >= float(event["start_ms"]))
                & (relative <= float(event["end_ms"]))
            )
            if len(retained) == 0:
                raise RuntimeError(f"PHASE6_DECODER_EVENT_HAS_NO_OBSERVATION:{attempt}")
            start_index = int(retained[0])
            end_index = int(retained[-1])
            event_row = {
                "attempt_id": attempt,
                "event_emitted": True,
                "start_index": start_index,
                "end_index": end_index,
                "retained_observation_count": end_index - start_index + 1,
                "start_source_timestamp_ms": float(timestamps[start_index]),
                "end_source_timestamp_ms": float(timestamps[end_index]),
                "start_relative_ms": float(relative[start_index]),
                "end_relative_ms": float(relative[end_index]),
                "retained_observation_duration_ms": float(
                    timestamps[end_index] - timestamps[start_index]
                ),
                "starts_at_first_phone_observation": start_index == 0,
                "ends_at_final_phone_observation": end_index == len(timestamps) - 1,
                "decoder_event": event,
            }
        event_rows.append(event_row)
        prediction_rows.append(
            {
                "attempt_id": attempt,
                "forward_pass_count": 1,
                "observations": [
                    {
                        "observation_index": index,
                        "source_timestamp_ms": float(timestamps[index]),
                        "relative_timestamp_ms": float(relative[index]),
                        "pre_probability": float(probabilities[index, 0]),
                        "active_probability": float(probabilities[index, 1]),
                        "post_probability": float(probabilities[index, 2]),
                        "argmax_state": int(states[index]),
                    }
                    for index in range(len(timestamps))
                ],
            }
        )

        dt_seconds = np.diff(timestamps) / 1000.0
        dt_z = normalized[1:, 215]
        hand_valid = np.repeat(features[:, 300:342].astype(bool), 2, axis=1)
        roi_valid = np.repeat(features[:, 348:350].astype(bool), 3, axis=1)
        body_valid = np.repeat(features[:, 366:374].astype(bool), 2, axis=1)
        diagnostic = {
            "attempt_id": attempt,
            "observation_count": len(timestamps),
            "duration_ms": float(relative[-1]),
            "effective_observation_hz": manifest_row["effective_observation_hz"],
            "dt_seconds": distribution(dt_seconds),
            "normalized_dt_z": z_diagnostic(dt_z),
            "hand_xy_delta_normalized": delta_diagnostic(
                normalized, slice(216, 300), hand_valid
            ),
            "hand_roi_delta_normalized": delta_diagnostic(
                normalized, slice(342, 348), roi_valid
            ),
            "body_xy_delta_normalized": delta_diagnostic(
                normalized, slice(350, 366), body_valid
            ),
        }
        diagnostics.append(diagnostic)
        aggregate_values["dt_seconds"].append(dt_seconds)
        aggregate_values["dt_z"].append(dt_z)
        aggregate_values["hand_values"].append(normalized[:, 216:300])
        aggregate_values["hand_valid"].append(hand_valid)
        aggregate_values["roi_values"].append(normalized[:, 342:348])
        aggregate_values["roi_valid"].append(roi_valid)
        aggregate_values["body_values"].append(normalized[:, 350:366])
        aggregate_values["body_valid"].append(body_valid)

    aggregate = {
        "attempt_count": 10,
        "observation_count": sum(row["observation_count"] for row in manifest_rows),
        "duration_ms": sum(row["duration_ms"] for row in manifest_rows),
        "effective_observation_hz": (
            sum(row["observation_count"] - 1 for row in manifest_rows)
            * 1000.0
            / sum(row["duration_ms"] for row in manifest_rows)
        ),
        "dt_seconds": distribution(np.concatenate(aggregate_values["dt_seconds"])),
        "normalized_dt_z": z_diagnostic(np.concatenate(aggregate_values["dt_z"])),
        "hand_xy_delta_normalized": delta_diagnostic(
            np.concatenate(aggregate_values["hand_values"]),
            slice(0, 84),
            np.concatenate(aggregate_values["hand_valid"]),
        ),
        "hand_roi_delta_normalized": delta_diagnostic(
            np.concatenate(aggregate_values["roi_values"]),
            slice(0, 6),
            np.concatenate(aggregate_values["roi_valid"]),
        ),
        "body_xy_delta_normalized": delta_diagnostic(
            np.concatenate(aggregate_values["body_values"]),
            slice(0, 16),
            np.concatenate(aggregate_values["body_valid"]),
        ),
    }
    write_json(
        OUT / "sparse_phone_feature_diagnostics.json",
        {
            "schema": "apphear.phase6.sparse_phone_feature_diagnostics.v1",
            "normalization_sha256": IDENTITIES["normalization"][1],
            "renormalized": False,
            "clipped": False,
            "diagnostic_only": True,
            "attempts": diagnostics,
            "aggregate": aggregate,
        },
    )
    write_json(
        OUT / "per_observation_segmenter_predictions.json",
        {
            "schema": "apphear.phase6.phone_segmenter_predictions.v1",
            "model_sha256": IDENTITIES["best_model"][1],
            "state_map": {"0": "PRE_IDLE", "1": "ACTIVE_SIGN", "2": "POST_RECOVERY"},
            "source_timestamps_preserved": True,
            "forward_passes_per_attempt": 1,
            "attempts": prediction_rows,
        },
    )
    frozen_events = {
        "schema": "apphear.phase6.learned_events_frozen.v1",
        "milestone": MILESTONE,
        "session_id": SESSION_ID,
        "model_sha256": IDENTITIES["best_model"][1],
        "normalization_sha256": IDENTITIES["normalization"][1],
        "feature_schema_sha256": IDENTITIES["feature_schema"][1],
        "feature_implementation_sha256": IDENTITIES["feature_implementation"][1],
        "decoder_reference_sha256": IDENTITIES["decoder_reference"][1],
        "decoder": identities["decoder"],
        "timestamp_policy": (
            "raw absolute source timestamps preserved for features/output; decoder receives "
            "source timestamp minus first source timestamp, preserving every interval"
        ),
        "events": event_rows,
        "comparison_inputs_opened": False,
        "manual_edits": False,
    }
    frozen_path = OUT / "learned_events_frozen.json"
    freeze_json(frozen_path, frozen_events)
    frozen_sha = sha256(frozen_path)
    freeze_json(
        OUT / "learned_events_frozen.sha256.json",
        {
            "schema": "apphear.phase6.learned_event_freeze_identity.v1",
            "path": str(frozen_path.resolve()),
            "sha256": frozen_sha,
            "immutable_before_comparison": True,
        },
    )
    return {
        "status": "LEARNED_EVENTS_FROZEN",
        "learned_events_sha256": frozen_sha,
        "events_emitted": sum(row["event_emitted"] for row in event_rows),
    }


if __name__ == "__main__":
    print(json.dumps(run_blind_freeze(), indent=2))
