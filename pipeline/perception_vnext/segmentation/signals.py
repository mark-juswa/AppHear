"""Unit-safe transition signals derived from genuine raw-v1 observations."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .schema import RawV1Document

HAND_CHANNELS = ("h_refined_body", "h_refined_image", "h_proposal_image")
BODY_CHANNEL = "l_body"


@dataclass(frozen=True)
class HandSideSignal:
    side: int
    channel: str | None
    value: float | None
    refined_body: float | None
    refined_image: float | None
    proposal_image: float | None


@dataclass(frozen=True)
class SegmentationTransition:
    """Signals for the interval ending at ``observation_index``."""

    observation_index: int
    previous_index: int
    frame_index: int
    timestamp_ms: float
    previous_timestamp_ms: float
    dt_ms: float
    hard_gap: bool
    rolling_median_dt_ms: float | None
    hand_sides: tuple[HandSideSignal, HandSideSignal]
    l_body: float | None
    proposal_transition: bool
    observed_transition: bool
    body_frame_valid: bool
    body_available: bool


def _body_frame(xy: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, np.ndarray, float] | None:
    for left, right in ((0, 1), (6, 7)):
        if valid[left] and valid[right]:
            delta = xy[left] - xy[right]
            scale = float(np.linalg.norm(delta))
            if np.isfinite(scale) and scale > 1e-6:
                lateral = delta / scale
                down = np.asarray([-lateral[1], lateral[0]], np.float64)
                origin = (xy[left] + xy[right]) * 0.5
                return np.stack([lateral, down]), origin, scale
    return None


def _refined_points(
    raw: RawV1Document, previous: int, current: int, side: int
) -> tuple[list[tuple[np.ndarray, np.ndarray]], bool]:
    arrays = raw.arrays
    if not (arrays.hand_observed[previous, side] and arrays.hand_observed[current, side]):
        return [], False
    points: list[tuple[np.ndarray, np.ndarray]] = []
    if arrays.hand_joint_valid[previous, side, 0] and arrays.hand_joint_valid[current, side, 0]:
        points.append((arrays.hand_xy[previous, side, 0], arrays.hand_xy[current, side, 0]))
    common = arrays.hand_joint_valid[previous, side] & arrays.hand_joint_valid[current, side]
    if int(np.count_nonzero(common)) >= 18:
        points.append(
            (
                np.mean(arrays.hand_xy[previous, side, common], axis=0),
                np.mean(arrays.hand_xy[current, side, common], axis=0),
            )
        )
    return points, bool(points)


def _refined_body_speed(
    raw: RawV1Document,
    previous: int,
    current: int,
    side: int,
    dt_s: float,
    frames: tuple[
        tuple[np.ndarray, np.ndarray, float] | None,
        tuple[np.ndarray, np.ndarray, float] | None,
    ],
) -> float | None:
    points, valid = _refined_points(raw, previous, current, side)
    if not valid or frames[0] is None or frames[1] is None:
        return None
    speeds: list[float] = []
    for before, after in points:
        basis0, origin0, scale0 = frames[0]
        basis1, origin1, scale1 = frames[1]
        normalized0 = basis0 @ (before - origin0) / scale0
        normalized1 = basis1 @ (after - origin1) / scale1
        speeds.append(float(np.linalg.norm(normalized1 - normalized0) / dt_s))
    return max(speeds)


def _refined_image_speed(
    raw: RawV1Document, previous: int, current: int, side: int, dt_s: float
) -> float | None:
    points, valid = _refined_points(raw, previous, current, side)
    if not valid:
        return None
    scale0 = float(np.min(raw.arrays.source_size[previous]))
    scale1 = float(np.min(raw.arrays.source_size[current]))
    speeds = [
        float(np.linalg.norm(after / scale1 - before / scale0) / dt_s)
        for before, after in points
    ]
    return max(speeds)


def _proposal_image_speed(
    raw: RawV1Document, previous: int, current: int, side: int, dt_s: float
) -> float | None:
    arrays = raw.arrays
    if not (
        arrays.hand_proposal_present[previous, side]
        and arrays.hand_proposal_present[current, side]
    ):
        return None
    before = arrays.hand_roi_center_side[previous, side, :2]
    after = arrays.hand_roi_center_side[current, side, :2]
    if not np.all(np.isfinite(before)) or not np.all(np.isfinite(after)):
        return None
    scale0 = float(np.min(arrays.source_size[previous]))
    scale1 = float(np.min(arrays.source_size[current]))
    return float(np.linalg.norm(after / scale1 - before / scale0) / dt_s)


def _limb_articulation_speed(
    raw: RawV1Document, previous: int, current: int, dt_s: float
) -> float | None:
    arrays = raw.arrays
    changes: list[float] = []
    for shoulder, elbow, wrist in ((0, 2, 4), (1, 3, 5)):
        for proximal, distal in ((shoulder, elbow), (elbow, wrist)):
            if not (
                arrays.body_valid[previous, proximal]
                and arrays.body_valid[previous, distal]
                and arrays.body_valid[current, proximal]
                and arrays.body_valid[current, distal]
            ):
                continue
            before = arrays.body_xy[previous, distal] - arrays.body_xy[previous, proximal]
            after = arrays.body_xy[current, distal] - arrays.body_xy[current, proximal]
            before_norm = float(np.linalg.norm(before))
            after_norm = float(np.linalg.norm(after))
            if before_norm > 1e-6 and after_norm > 1e-6:
                changes.append(
                    float(np.linalg.norm(after / after_norm - before / before_norm) / dt_s)
                )
    return max(changes) if changes else None


def extract_segmentation_transitions(
    raw: RawV1Document,
    *,
    gap_absolute_ms: float = 500.0,
    gap_median_multiplier: float = 3.0,
    gap_window_ms: float = 2000.0,
) -> list[SegmentationTransition]:
    """Derive transition signals without interpolation, carry, or cross-gap motion."""

    arrays = raw.arrays
    transitions: list[SegmentationTransition] = []
    positive_dt_history: list[tuple[float, float]] = []
    for current in range(1, raw.observation_count):
        previous = current - 1
        timestamp = float(arrays.timestamp_ms[current])
        previous_timestamp = float(arrays.timestamp_ms[previous])
        dt_ms = timestamp - previous_timestamp
        preceding = [
            value
            for end_timestamp, value in positive_dt_history
            if end_timestamp >= timestamp - gap_window_ms
        ]
        median_dt = float(np.median(preceding)) if preceding else None
        adaptive = gap_absolute_ms
        if median_dt is not None:
            adaptive = max(adaptive, gap_median_multiplier * median_dt)
        hard_gap = dt_ms > adaptive
        frames = (
            _body_frame(arrays.body_xy[previous], arrays.body_valid[previous]),
            _body_frame(arrays.body_xy[current], arrays.body_valid[current]),
        )
        sides: list[HandSideSignal] = []
        l_body: float | None = None
        if not hard_gap:
            dt_s = dt_ms / 1000.0
            for side in range(2):
                refined_body = _refined_body_speed(
                    raw, previous, current, side, dt_s, frames
                )
                refined_image = _refined_image_speed(raw, previous, current, side, dt_s)
                proposal_image = _proposal_image_speed(raw, previous, current, side, dt_s)
                if refined_body is not None:
                    channel, value = "h_refined_body", refined_body
                elif refined_image is not None:
                    channel, value = "h_refined_image", refined_image
                elif proposal_image is not None:
                    channel, value = "h_proposal_image", proposal_image
                else:
                    channel, value = None, None
                sides.append(
                    HandSideSignal(
                        side=side,
                        channel=channel,
                        value=value,
                        refined_body=refined_body,
                        refined_image=refined_image,
                        proposal_image=proposal_image,
                    )
                )
            l_body = _limb_articulation_speed(raw, previous, current, dt_s)
        else:
            sides = [
                HandSideSignal(side=side, channel=None, value=None, refined_body=None,
                               refined_image=None, proposal_image=None)
                for side in range(2)
            ]
        transitions.append(
            SegmentationTransition(
                observation_index=current,
                previous_index=previous,
                frame_index=int(arrays.frame_index[current]),
                timestamp_ms=timestamp,
                previous_timestamp_ms=previous_timestamp,
                dt_ms=dt_ms,
                hard_gap=hard_gap,
                rolling_median_dt_ms=median_dt,
                hand_sides=(sides[0], sides[1]),
                l_body=l_body,
                proposal_transition=bool(
                    np.any(
                        arrays.hand_proposal_present[current]
                        != arrays.hand_proposal_present[previous]
                    )
                ),
                observed_transition=bool(
                    np.any(arrays.hand_observed[current] != arrays.hand_observed[previous])
                ),
                body_frame_valid=frames[0] is not None and frames[1] is not None,
                body_available=bool(arrays.body_available[current]),
            )
        )
        positive_dt_history.append((timestamp, dt_ms))
    return transitions
