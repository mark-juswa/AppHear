"""Causal anatomical hand identity assignment for the offline A2-1 experiment.

This module deliberately does not recover, interpolate, or carry hand landmarks forward.  It
only assigns *direct* MediaPipe observations to persistent anatomical left/right tracks.  A frame
that cannot be assigned safely is emitted as ambiguous and does not update either track.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


class AnatomicalSide(StrEnum):
    LEFT = "left"
    RIGHT = "right"


class MediaPipeSlot(StrEnum):
    LEFT = "mp_left"
    RIGHT = "mp_right"


@dataclass(frozen=True)
class IdentityConfig:
    """Frozen A2-1 cost weights in shoulder-normalized S4 coordinates."""

    wrist_weight: float = 0.65
    palm_weight: float = 0.20
    pose_wrist_weight: float = 0.05
    mediapipe_label_penalty: float = 0.10
    invert_mediapipe_handedness: bool = True
    velocity_ema: float = 0.60
    max_prediction_dt_s: float = 0.50
    max_assignment_cost: float = 0.85
    min_assignment_margin: float = 0.12
    collision_ambiguity_distance: float = 0.08


@dataclass(frozen=True)
class DirectObservation:
    slot: MediaPipeSlot
    timestamp_ns: int
    landmarks: FloatArray

    def __post_init__(self) -> None:
        if self.landmarks.shape != (21, 3):
            raise ValueError(f"hand landmarks must be [21,3], got {self.landmarks.shape}")
        if not np.isfinite(self.landmarks).all():
            raise ValueError("direct landmarks must be finite")


@dataclass
class _TrackState:
    landmarks: FloatArray | None = None
    timestamp_ns: int | None = None
    wrist_velocity: FloatArray | None = None
    direct_updates: int = 0


@dataclass(frozen=True)
class FrameAssignment:
    timestamp_ns: int
    left: DirectObservation | None
    right: DirectObservation | None
    ambiguous_slots: tuple[MediaPipeSlot, ...]
    assignment_margin: float | None
    assignment_cost: float | None

    @property
    def identity_stable(self) -> bool:
        return not self.ambiguous_slots


_PALM_INDICES = np.asarray([0, 5, 9, 13, 17], dtype=np.int64)


class AnatomicalIdentityTracker:
    """Two-track causal assignment with explicit ambiguity and no landmark recovery."""

    def __init__(self, config: IdentityConfig | None = None) -> None:
        self.config = config or IdentityConfig()
        self._tracks = {
            AnatomicalSide.LEFT: _TrackState(),
            AnatomicalSide.RIGHT: _TrackState(),
        }

    def reset(self) -> None:
        for side in AnatomicalSide:
            self._tracks[side] = _TrackState()

    def update(
        self,
        timestamp_ns: int,
        observations: tuple[DirectObservation, ...],
        pose_wrists: dict[AnatomicalSide, FloatArray] | None = None,
    ) -> FrameAssignment:
        if len(observations) > 2:
            raise ValueError("A2-1 supports at most two direct hand observations")
        if any(observation.timestamp_ns != timestamp_ns for observation in observations):
            raise ValueError("all observations must use the frame timestamp")
        if not observations:
            return FrameAssignment(timestamp_ns, None, None, (), None, None)

        if len(observations) == 2:
            wrist_separation = float(
                np.linalg.norm(observations[0].landmarks[0, :2] - observations[1].landmarks[0, :2])
            )
            if wrist_separation < self.config.collision_ambiguity_distance:
                return FrameAssignment(
                    timestamp_ns=timestamp_ns,
                    left=None,
                    right=None,
                    ambiguous_slots=tuple(observation.slot for observation in observations),
                    assignment_margin=0.0,
                    assignment_cost=None,
                )

        candidates = self._candidate_assignments(observations)
        scored = sorted(
            (
                self._assignment_cost(timestamp_ns, assignment, pose_wrists),
                assignment,
            )
            for assignment in candidates
        )
        best_cost, best = scored[0]
        second_cost = scored[1][0] if len(scored) > 1 else float("inf")
        margin = second_cost - best_cost
        maximum = self.config.max_assignment_cost * len(observations)
        if best_cost > maximum or margin < self.config.min_assignment_margin:
            return FrameAssignment(
                timestamp_ns=timestamp_ns,
                left=None,
                right=None,
                ambiguous_slots=tuple(observation.slot for observation in observations),
                assignment_margin=float(margin),
                assignment_cost=float(best_cost),
            )

        assigned = {side: observation for side, observation in best}
        for side, observation in best:
            self._update_track(side, observation)
        return FrameAssignment(
            timestamp_ns=timestamp_ns,
            left=assigned.get(AnatomicalSide.LEFT),
            right=assigned.get(AnatomicalSide.RIGHT),
            ambiguous_slots=(),
            assignment_margin=float(margin),
            assignment_cost=float(best_cost),
        )

    def _candidate_assignments(
        self, observations: tuple[DirectObservation, ...]
    ) -> tuple[tuple[tuple[AnatomicalSide, DirectObservation], ...], ...]:
        if len(observations) == 1:
            observation = observations[0]
            return (
                ((AnatomicalSide.LEFT, observation),),
                ((AnatomicalSide.RIGHT, observation),),
            )
        first, second = observations
        return (
            (
                (AnatomicalSide.LEFT, first),
                (AnatomicalSide.RIGHT, second),
            ),
            (
                (AnatomicalSide.LEFT, second),
                (AnatomicalSide.RIGHT, first),
            ),
        )

    def _assignment_cost(
        self,
        timestamp_ns: int,
        assignment: tuple[tuple[AnatomicalSide, DirectObservation], ...],
        pose_wrists: dict[AnatomicalSide, FloatArray] | None,
    ) -> float:
        return sum(
            self._observation_cost(timestamp_ns, side, observation, pose_wrists)
            for side, observation in assignment
        )

    def _observation_cost(
        self,
        timestamp_ns: int,
        side: AnatomicalSide,
        observation: DirectObservation,
        pose_wrists: dict[AnatomicalSide, FloatArray] | None,
    ) -> float:
        cfg = self.config
        state = self._tracks[side]
        if self.config.invert_mediapipe_handedness:
            label_side = (
                AnatomicalSide.RIGHT
                if observation.slot == MediaPipeSlot.LEFT
                else AnatomicalSide.LEFT
            )
        else:
            label_side = (
                AnatomicalSide.LEFT
                if observation.slot == MediaPipeSlot.LEFT
                else AnatomicalSide.RIGHT
            )
        cost = cfg.mediapipe_label_penalty if label_side != side else 0.0

        if state.landmarks is not None and state.timestamp_ns is not None:
            dt_s = max(0.0, (timestamp_ns - state.timestamp_ns) / 1_000_000_000.0)
            dt_s = min(dt_s, cfg.max_prediction_dt_s)
            predicted_wrist = state.landmarks[0, :2].copy()
            if state.wrist_velocity is not None:
                predicted_wrist += state.wrist_velocity * dt_s
            wrist_distance = float(
                np.linalg.norm(observation.landmarks[0, :2] - predicted_wrist)
            )
            palm_distance = float(
                np.linalg.norm(
                    observation.landmarks[_PALM_INDICES, :2]
                    - state.landmarks[_PALM_INDICES, :2],
                    axis=1,
                ).mean()
            )
            cost += cfg.wrist_weight * wrist_distance + cfg.palm_weight * palm_distance

        if pose_wrists is not None and side in pose_wrists:
            pose_wrist = np.asarray(pose_wrists[side], dtype=np.float64)
            if pose_wrist.shape == (2,) and np.isfinite(pose_wrist).all():
                cost += cfg.pose_wrist_weight * float(
                    np.linalg.norm(observation.landmarks[0, :2] - pose_wrist)
                )
        return cost

    def _update_track(self, side: AnatomicalSide, observation: DirectObservation) -> None:
        state = self._tracks[side]
        new_velocity: FloatArray | None = None
        if state.landmarks is not None and state.timestamp_ns is not None:
            dt_s = (observation.timestamp_ns - state.timestamp_ns) / 1_000_000_000.0
            if dt_s > 1e-6:
                measured = (
                    observation.landmarks[0, :2] - state.landmarks[0, :2]
                ) / dt_s
                if state.wrist_velocity is None:
                    new_velocity = measured
                else:
                    alpha = self.config.velocity_ema
                    new_velocity = alpha * state.wrist_velocity + (1.0 - alpha) * measured
        state.landmarks = observation.landmarks.copy()
        state.timestamp_ns = observation.timestamp_ns
        state.wrist_velocity = new_velocity
        state.direct_updates += 1


def observations_from_feature(
    feature: FloatArray, timestamp_ns: int
) -> tuple[DirectObservation, ...]:
    """Decode the two direct MediaPipe hand slots from a schema-v3.0 feature row."""

    values = np.asarray(feature, dtype=np.float64)
    if values.shape != (258,):
        raise ValueError(f"schema-v3.0 feature must be [258], got {values.shape}")
    observations: list[DirectObservation] = []
    for slot_index, slot in enumerate((MediaPipeSlot.LEFT, MediaPipeSlot.RIGHT)):
        block = values[slot_index * 63 : (slot_index + 1) * 63].reshape(21, 3)
        if np.any(block != 0.0):
            observations.append(DirectObservation(slot, timestamp_ns, block.copy()))
    return tuple(observations)


def pose_wrists_from_feature(feature: FloatArray) -> dict[AnatomicalSide, FloatArray]:
    """Return normalized pose wrist xy anchors from schema-v3.0 indices 15/16."""

    values = np.asarray(feature, dtype=np.float64)
    if values.shape != (258,):
        raise ValueError(f"schema-v3.0 feature must be [258], got {values.shape}")
    pose = values[126:].reshape(33, 4)
    return {
        AnatomicalSide.LEFT: pose[15, :2].copy(),
        AnatomicalSide.RIGHT: pose[16, :2].copy(),
    }
