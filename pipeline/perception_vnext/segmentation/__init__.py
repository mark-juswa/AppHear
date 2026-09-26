"""Deterministic offline isolated-sign segmentation over Candidate01 raw-v1."""

from .event import build_sign_event, validate_sign_event_raw_sequence
from .schema import (
    EVENT_SCHEMA,
    RAW_SCHEMA,
    STATE_MACHINE_VERSION,
    RawV1Document,
    load_raw_v1_json,
)
from .signals import SegmentationTransition, extract_segmentation_transitions
from .state_machine import (
    BoundaryDetection,
    SegmentationResult,
    SegmenterConfig,
    segment_raw_sequence,
)

__all__ = [
    "BoundaryDetection",
    "EVENT_SCHEMA",
    "RAW_SCHEMA",
    "STATE_MACHINE_VERSION",
    "RawV1Document",
    "SegmentationResult",
    "SegmentationTransition",
    "SegmenterConfig",
    "build_sign_event",
    "extract_segmentation_transitions",
    "load_raw_v1_json",
    "segment_raw_sequence",
    "validate_sign_event_raw_sequence",
]
