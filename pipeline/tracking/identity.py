"""Pure coordinate and anatomical-hand assignment primitives for E2e-A."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import permutations
from math import hypot

SIDES = ("left", "right")


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Box:
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def __post_init__(self) -> None:
        if not (
            0.0 <= self.x_min < self.x_max <= 1.0
            and 0.0 <= self.y_min < self.y_max <= 1.0
        ):
            raise ValueError(f"invalid normalized box: {self}")

    @property
    def center(self) -> Point:
        return Point((self.x_min + self.x_max) / 2.0, (self.y_min + self.y_max) / 2.0)


@dataclass(frozen=True)
class HandCandidate:
    candidate_id: str
    box: Box
    mediapipe_label: str
    score: float

    def __post_init__(self) -> None:
        if self.mediapipe_label.lower() not in SIDES:
            raise ValueError(f"invalid MediaPipe label: {self.mediapipe_label}")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"invalid candidate score: {self.score}")


@dataclass(frozen=True)
class AssociationConfig:
    pose_weight: float
    temporal_weight: float
    confidence_weight: float
    max_cost: float
    max_track_age_ms: int


@dataclass
class Track:
    center: Point
    velocity_x_per_ms: float = 0.0
    velocity_y_per_ms: float = 0.0
    timestamp_ms: int = 0

    def predict(self, timestamp_ms: int, max_age_ms: int) -> Point | None:
        age = timestamp_ms - self.timestamp_ms
        if age < 0 or age > max_age_ms:
            return None
        return Point(
            self.center.x + self.velocity_x_per_ms * age,
            self.center.y + self.velocity_y_per_ms * age,
        )


@dataclass
class TemporalState:
    tracks: dict[str, Track] = field(default_factory=dict)

    def predicted(self, timestamp_ms: int, max_age_ms: int) -> dict[str, Point]:
        result: dict[str, Point] = {}
        for side, track in self.tracks.items():
            point = track.predict(timestamp_ms, max_age_ms)
            if point is not None:
                result[side] = point
        return result

    def update(
        self, assignments: Mapping[str, HandCandidate], timestamp_ms: int
    ) -> None:
        for side, candidate in assignments.items():
            center = candidate.box.center
            old = self.tracks.get(side)
            velocity_x = velocity_y = 0.0
            if old is not None and timestamp_ms > old.timestamp_ms:
                elapsed = timestamp_ms - old.timestamp_ms
                velocity_x = (center.x - old.center.x) / elapsed
                velocity_y = (center.y - old.center.y) / elapsed
            self.tracks[side] = Track(
                center=center,
                velocity_x_per_ms=velocity_x,
                velocity_y_per_ms=velocity_y,
                timestamp_ms=timestamp_ms,
            )


def mirror_point(point: Point) -> Point:
    return Point(1.0 - point.x, point.y)


def mirror_box(box: Box) -> Box:
    return Box(1.0 - box.x_max, box.y_min, 1.0 - box.x_min, box.y_max)


def canonicalize_point(point: Point, inference_mirrored: bool) -> Point:
    return mirror_point(point) if inference_mirrored else point


def canonicalize_box(box: Box, inference_mirrored: bool) -> Box:
    return mirror_box(box) if inference_mirrored else box


def canonicalize_pose_points(
    points: Mapping[str, Point], inference_mirrored: bool
) -> dict[str, Point]:
    if not inference_mirrored:
        return dict(points)
    canonical: dict[str, Point] = {}
    for source_side, point in points.items():
        anatomical_side = "right" if source_side == "left" else "left"
        canonical[anatomical_side] = mirror_point(point)
    return canonical


def direct_label_assignment(
    candidates: Sequence[HandCandidate], swap_labels: bool
) -> dict[str, HandCandidate]:
    assignments: dict[str, HandCandidate] = {}
    for candidate in candidates:
        side = candidate.mediapipe_label.lower()
        if swap_labels:
            side = "right" if side == "left" else "left"
        current = assignments.get(side)
        if current is None or candidate.score > current.score:
            assignments[side] = candidate
    return assignments


def _distance(a: Point, b: Point) -> float:
    return hypot(a.x - b.x, a.y - b.y)


def geometry_assignment(
    candidates: Sequence[HandCandidate],
    pose_wrists: Mapping[str, Point],
    predicted_centers: Mapping[str, Point],
    config: AssociationConfig,
) -> dict[str, HandCandidate]:
    """Assign at most two candidates to anatomical sides using pose and causal track state."""

    if not candidates:
        return {}
    usable_sides = [
        side for side in SIDES if side in pose_wrists or side in predicted_centers
    ]
    if not usable_sides:
        return {}

    count = min(len(candidates), len(usable_sides))
    best_cost = float("inf")
    best: dict[str, HandCandidate] = {}
    for side_order in permutations(usable_sides, count):
        for candidate_order in permutations(candidates, count):
            total = 0.0
            valid = True
            proposed: dict[str, HandCandidate] = {}
            for side, candidate in zip(side_order, candidate_order, strict=True):
                terms = []
                if side in pose_wrists:
                    terms.append(
                        config.pose_weight
                        * _distance(candidate.box.center, pose_wrists[side])
                    )
                if side in predicted_centers:
                    terms.append(
                        config.temporal_weight
                        * _distance(candidate.box.center, predicted_centers[side])
                    )
                if not terms:
                    valid = False
                    break
                cost = sum(terms) - config.confidence_weight * candidate.score
                if cost > config.max_cost:
                    valid = False
                    break
                total += cost
                proposed[side] = candidate
            if valid and total < best_cost:
                best_cost = total
                best = proposed
    return best


def pose_assignment(
    candidates: Sequence[HandCandidate],
    pose_wrists: Mapping[str, Point],
    config: AssociationConfig,
) -> dict[str, HandCandidate]:
    return geometry_assignment(candidates, pose_wrists, {}, config)


def temporal_pose_assignment(
    candidates: Sequence[HandCandidate],
    pose_wrists: Mapping[str, Point],
    timestamp_ms: int,
    state: TemporalState,
    config: AssociationConfig,
) -> dict[str, HandCandidate]:
    predicted = state.predicted(timestamp_ms, config.max_track_age_ms)
    assignments = geometry_assignment(candidates, pose_wrists, predicted, config)
    state.update(assignments, timestamp_ms)
    return assignments
