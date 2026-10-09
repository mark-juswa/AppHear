"""SignEvent serialization and raw-v1 immutability validation."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .schema import EVENT_SCHEMA, RAW_SCHEMA, RawV1Document
from .state_machine import BoundaryDetection, SegmentationResult


def _identity(raw: RawV1Document, index: int) -> dict[str, int | float]:
    return {
        "observation_index": index,
        "frame_index": int(raw.arrays.frame_index[index]),
        "source_timestamp_ms": float(raw.arrays.timestamp_ms[index]),
        "source_timestamp_ns": int(round(float(raw.arrays.timestamp_ms[index]) * 1_000_000.0)),
    }


def _event_id(
    source_session_id: str, config_sha256: str, detection: BoundaryDetection
) -> str:
    payload = (
        f"{source_session_id}|{config_sha256}|{detection.event_ordinal}|"
        f"{detection.padded_start_index}|{detection.padded_end_index}"
    ).encode()
    return f"sign_event_{hashlib.sha256(payload).hexdigest()[:24]}"


def build_sign_event(
    raw: RawV1Document,
    detection: BoundaryDetection,
    result: SegmentationResult,
    *,
    segmenter_version: str,
    config_sha256: str,
    source_session_id: str,
) -> dict[str, Any]:
    trace = [
        row
        for row in result.state_transition_trace
        if row.get("event_ordinal") == detection.event_ordinal
    ]
    raw_sequence = raw.slice_source(detection.padded_start_index, detection.padded_end_index)
    event = {
        "schema": EVENT_SCHEMA,
        "segmenter_version": segmenter_version,
        "config_sha256": config_sha256,
        "event_id": _event_id(source_session_id, config_sha256, detection),
        "source_session_id": source_session_id,
        "raw_schema": RAW_SCHEMA,
        "image_semantics": raw.source["image_semantics"],
        "source_timestamp_ordering": "STRICTLY_INCREASING_SOURCE_TIMESTAMP_MS",
        "detected_onset": _identity(raw, detection.detected_onset_index),
        "detected_offset": _identity(raw, detection.detected_offset_index),
        "padded_start": _identity(raw, detection.padded_start_index),
        "padded_end": _identity(raw, detection.padded_end_index),
        "observation_count": detection.padded_end_index - detection.padded_start_index + 1,
        "state_transition_trace": trace,
        "signal_validity_summary": result.signal_validity_summary,
        "quality_flags": detection.quality_flags,
        "gap_summary": detection.gap_summary,
        "rearm_outcome": result.rearm_outcome,
        "raw_sequence": raw_sequence,
    }
    validate_sign_event_raw_sequence(event, raw, detection)
    return event


def _json_value_equal(left: Any, right: Any) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        return list(left) == list(right) and all(
            _json_value_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _json_value_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def validate_sign_event_raw_sequence(
    event: dict[str, Any], raw: RawV1Document, detection: BoundaryDetection
) -> None:
    if event.get("schema") != EVENT_SCHEMA or event.get("raw_schema") != RAW_SCHEMA:
        raise ValueError("SignEvent schema identity mismatch")
    expected = raw.slice_source(detection.padded_start_index, detection.padded_end_index)
    if not _json_value_equal(event.get("raw_sequence"), expected):
        raise ValueError("SignEvent raw_sequence differs from the canonical source slice")
    canonical = json.loads(json.dumps(event["raw_sequence"], separators=(",", ":")))
    if not _json_value_equal(canonical, expected):
        raise ValueError("SignEvent JSON round-trip changed a retained raw-v1 value")
