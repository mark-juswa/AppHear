from __future__ import annotations

from typing import Any

import numpy as np

from pipeline.perception_vnext.segmentation.event import build_sign_event
from pipeline.perception_vnext.segmentation.schema import (
    IMAGE_SEMANTICS,
    RAW_SCHEMA,
    RawV1Document,
    raw_v1_arrays,
)
from pipeline.perception_vnext.segmentation.signals import (
    HandSideSignal,
    SegmentationTransition,
    extract_segmentation_transitions,
)
from pipeline.perception_vnext.segmentation.state_machine import (
    ChannelThreshold,
    SegmenterConfig,
    segment_raw_sequence,
)


def _raw_source(timestamps: list[float]) -> dict[str, Any]:
    count = len(timestamps)
    body_points = [
        40.0,
        40.0,
        60.0,
        40.0,
        42.0,
        55.0,
        58.0,
        55.0,
        44.0,
        70.0,
        56.0,
        70.0,
        43.0,
        80.0,
        57.0,
        80.0,
    ]
    return {
        "schema": RAW_SCHEMA,
        "image_semantics": IMAGE_SEMANTICS,
        "frame_index": list(range(count)),
        "timestamp_ms": timestamps,
        "source_size": [100, 100] * count,
        "hand_xy": [0.0] * (count * 2 * 21 * 2),
        "hand_proposal_support": [0.0] * (count * 2 * 21),
        "hand_joint_valid": [False] * (count * 2 * 21),
        "hand_presence": [None] * (count * 2),
        "hand_observed": [False] * (count * 2),
        "hand_proposal_present": [False] * (count * 2),
        "hand_roi_center_side": [None] * (count * 2 * 3),
        "hand_handedness_diagnostic": [None] * (count * 2),
        "body_xy": body_points * count,
        "body_support": [1.0] * (count * 8),
        "body_valid": [True] * (count * 8),
        "body_available": [True] * count,
        "frame_runtime": [
            {
                "source_timestamp_ns": int(timestamp * 1_000_000),
                "completion_timestamp_ns": int(timestamp * 1_000_000 + 1),
                "camera_frame_count": index,
                "analyzed_frame_count": index,
            }
            for index, timestamp in enumerate(timestamps)
        ],
        "current_frame_only": True,
        "synthetic_depth": False,
        "stale_carry_forward": False,
    }


def _raw(timestamps: list[float]) -> RawV1Document:
    source = _raw_source(timestamps)
    return RawV1Document(source=source, arrays=raw_v1_arrays(source))


def _config() -> SegmenterConfig:
    return SegmenterConfig(
        thresholds={
            name: ChannelThreshold(0.1, 0.5)
            for name in (
                "h_refined_body",
                "h_refined_image",
                "h_proposal_image",
                "l_body",
            )
        }
    )


def _transition(
    current: int,
    timestamps: list[float],
    *,
    hand: float | None = None,
    body: float | None = None,
    hard_gap: bool = False,
) -> SegmentationTransition:
    side = HandSideSignal(
        side=0,
        channel="h_proposal_image" if hand is not None else None,
        value=hand,
        refined_body=None,
        refined_image=None,
        proposal_image=hand,
    )
    missing = HandSideSignal(
        side=1,
        channel=None,
        value=None,
        refined_body=None,
        refined_image=None,
        proposal_image=None,
    )
    return SegmentationTransition(
        observation_index=current,
        previous_index=current - 1,
        frame_index=current,
        timestamp_ms=timestamps[current],
        previous_timestamp_ms=timestamps[current - 1],
        dt_ms=timestamps[current] - timestamps[current - 1],
        hard_gap=hard_gap,
        rolling_median_dt_ms=200.0,
        hand_sides=(side, missing),
        l_body=body,
        proposal_transition=False,
        observed_transition=False,
        body_frame_valid=True,
        body_available=True,
    )


def test_canonical_raw_slice_preserves_flat_arrays_runtime_and_scalars() -> None:
    raw = _raw([0.0, 200.0, 400.0, 600.0])
    sliced = raw.slice_source(1, 2)
    assert sliced["frame_index"] == [1, 2]
    assert sliced["timestamp_ms"] == [200.0, 400.0]
    assert sliced["source_size"] == [100, 100, 100, 100]
    assert sliced["frame_runtime"] == raw.source["frame_runtime"][1:3]
    assert sliced["current_frame_only"] is True
    assert sliced["synthetic_depth"] is False
    assert sliced["stale_carry_forward"] is False


def test_signal_hierarchy_prefers_refined_body_then_image_then_proposal() -> None:
    source = _raw_source([0.0, 200.0, 400.0])
    hand_xy = np.asarray(source["hand_xy"], object).reshape(3, 2, 21, 2)
    hand_valid = np.asarray(source["hand_joint_valid"], bool).reshape(3, 2, 21)
    observed = np.asarray(source["hand_observed"], bool).reshape(3, 2)
    proposal = np.asarray(source["hand_proposal_present"], bool).reshape(3, 2)
    roi = np.asarray(source["hand_roi_center_side"], object).reshape(3, 2, 3)
    for frame in range(3):
        observed[frame, 0] = True
        hand_valid[frame, 0] = True
        hand_xy[frame, 0, :, 0] = np.arange(21) + frame
        hand_xy[frame, 0, :, 1] = np.arange(21)
        proposal[frame, 1] = True
        roi[frame, 1] = [20.0 + frame, 30.0, 10.0]
    source["hand_xy"] = hand_xy.astype(float).reshape(-1).tolist()
    source["hand_joint_valid"] = hand_valid.reshape(-1).tolist()
    source["hand_observed"] = observed.reshape(-1).tolist()
    source["hand_proposal_present"] = proposal.reshape(-1).tolist()
    source["hand_roi_center_side"] = roi.reshape(-1).tolist()
    raw = RawV1Document(source=source, arrays=raw_v1_arrays(source))
    transitions = extract_segmentation_transitions(raw)
    assert transitions[0].hand_sides[0].channel == "h_refined_body"
    assert transitions[0].hand_sides[1].channel == "h_proposal_image"

    no_body = dict(source)
    no_body["body_valid"] = [False] * (3 * 8)
    no_body["body_available"] = [False] * 3
    fallback = RawV1Document(source=no_body, arrays=raw_v1_arrays(no_body))
    fallback_transitions = extract_segmentation_transitions(fallback)
    assert fallback_transitions[0].hand_sides[0].channel == "h_refined_image"
    assert fallback_transitions[0].l_body is None


def test_short_quiet_pause_does_not_split_and_raised_hands_can_rearm() -> None:
    timestamps = [
        0.0,
        100.0,
        400.0,
        600.0,
        800.0,
        1000.0,
        1200.0,
        1400.0,
        1600.0,
        1800.0,
    ]
    raw = _raw(timestamps)
    transitions = [
        _transition(1, timestamps, hand=0.8),
        _transition(2, timestamps, hand=0.8),
        _transition(3, timestamps, hand=0.2),
        _transition(4, timestamps, hand=0.05),
        _transition(5, timestamps, hand=0.2),
        _transition(6, timestamps, hand=0.05),
        _transition(7, timestamps, hand=0.05),
        _transition(8, timestamps, hand=0.05),
        _transition(9, timestamps, hand=0.05),
    ]
    result = segment_raw_sequence(raw, transitions, _config())
    assert len(result.events) == 1
    assert result.events[0].detected_onset_index == 1
    assert result.events[0].detected_offset_index == 5
    assert result.rearm_outcome == "COMPLETED"
    assert result.final_state == "IDLE"


def test_hard_gap_resets_idle_and_possible_start() -> None:
    timestamps = [0.0, 100.0, 800.0]
    raw = _raw(timestamps)
    idle = segment_raw_sequence(
        raw,
        [
            _transition(1, timestamps, hand=0.05),
            _transition(2, timestamps, hard_gap=True),
        ],
        _config(),
    )
    assert not idle.events
    assert idle.final_state == "IDLE"

    possible = segment_raw_sequence(
        raw,
        [
            _transition(1, timestamps, hand=0.8),
            _transition(2, timestamps, hard_gap=True),
        ],
        _config(),
    )
    assert not possible.events
    assert possible.final_state == "IDLE"
    assert any(
        row["reason"] == "hard_gap_reset_possible_start"
        for row in possible.state_transition_trace
    )


def test_hard_gap_during_active_or_possible_end_emits_degraded_event() -> None:
    active_timestamps = [0.0, 100.0, 400.0, 600.0, 1200.0]
    active_raw = _raw(active_timestamps)
    active = segment_raw_sequence(
        active_raw,
        [
            _transition(1, active_timestamps, hand=0.8),
            _transition(2, active_timestamps, hand=0.8),
            _transition(3, active_timestamps, hand=0.2),
            _transition(4, active_timestamps, hard_gap=True),
        ],
        _config(),
    )
    assert len(active.events) == 1
    assert "PERCEPTION_GAP_TRUNCATED" in active.events[0].quality_flags

    end_timestamps = [0.0, 100.0, 400.0, 600.0, 800.0, 1400.0]
    end_raw = _raw(end_timestamps)
    possible_end = segment_raw_sequence(
        end_raw,
        [
            _transition(1, end_timestamps, hand=0.8),
            _transition(2, end_timestamps, hand=0.8),
            _transition(3, end_timestamps, hand=0.2),
            _transition(4, end_timestamps, hand=0.05),
            _transition(5, end_timestamps, hard_gap=True),
        ],
        _config(),
    )
    assert len(possible_end.events) == 1
    assert "PERCEPTION_GAP_TRUNCATED" in possible_end.events[0].quality_flags


def test_sign_event_round_trip_keeps_only_original_observations() -> None:
    timestamps = [0.0, 100.0, 400.0, 600.0, 800.0, 1000.0, 1200.0, 1400.0]
    raw = _raw(timestamps)
    transitions = [
        _transition(1, timestamps, hand=0.8),
        _transition(2, timestamps, hand=0.8),
        _transition(3, timestamps, hand=0.2),
        _transition(4, timestamps, hand=0.05),
        _transition(5, timestamps, hand=0.05),
        _transition(6, timestamps, hand=0.05),
        _transition(7, timestamps, hand=0.05),
    ]
    result = segment_raw_sequence(raw, transitions, _config())
    event = build_sign_event(
        raw,
        result.events[0],
        result,
        segmenter_version="phase5.1-test",
        config_sha256="0" * 64,
        source_session_id="unit_fixture",
    )
    assert event["observation_count"] == len(event["raw_sequence"]["frame_index"])
    assert event["raw_sequence"]["frame_index"] == list(
        range(result.events[0].padded_start_index, result.events[0].padded_end_index + 1)
    )
