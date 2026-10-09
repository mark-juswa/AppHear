"""Offline-only input assessment. No inference, thresholds, temporal edits or routing."""

from __future__ import annotations

from typing import Any

import numpy as np

from pipeline.perception_vnext.recognition_schema import RawSequence

VERSION = "apphear.fingerspelling.input_evidence.v1"


def assess(raw: RawSequence) -> dict[str, Any]:
    """Report observable geometry, not confidence in a letter or a physical hand count.

    Only complete absence is a refusal recommendation. Partial missingness remains
    usable; fractions/runs are diagnostics without a guessed quality threshold.
    This utility is deliberately unused by training and Android.
    """
    raw.validate()
    if not np.isfinite(raw.timestamp_ms).all():
        raise ValueError("[fingerspelling/input-evidence] Non-finite observation timestamp")
    accepted = raw.hand_observed.astype(bool)
    usable_slots = accepted & raw.hand_joint_valid.astype(bool).any(axis=2)
    usable = np.asarray(usable_slots.any(axis=1), dtype=bool)
    run = longest = 0
    for present in usable:
        run = 0 if present else run + 1
        longest = max(longest, run)
    if not accepted.any():
        refusal = "NO_ACCEPTED_HAND_OBSERVATIONS"
    elif not usable.any():
        refusal = "NO_VALID_HAND_GEOMETRY"
    else:
        refusal = None
    return dict(
        schema_version=VERSION,
        raw_schema=raw.metadata["schema"],
        observations=len(usable),
        any_accepted_hand_observations=int(accepted.any(axis=1).sum()),
        any_usable_hand_observations=int(usable.sum()),
        usable_observation_fraction=float(usable.mean()),
        longest_missing_usable_hand_run=int(longest),
        timestamp_span_seconds=float((raw.timestamp_ms[-1] - raw.timestamp_ms[0]) / 1000),
        refusal_recommended=refusal is not None,
        refusal_reason=refusal,
        recognition_quality="NOT_ESTIMATED",
        observation_deletion=False,
        application_integration=False,
    )
