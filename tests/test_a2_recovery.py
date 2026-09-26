from __future__ import annotations

import numpy as np

from eval.runtime_diagnostics.a2_recovery_experiment import OneObservationRecovery, hand_block


def _config() -> dict:
    return {
        "eligibility": {
            "maximum_recovery_age_ms": 400.0,
            "minimum_history_dt_ms": 50.0,
            "maximum_history_dt_ms": 400.0,
            "minimum_hand_scale": 0.08,
            "maximum_hand_scale": 0.45,
            "maximum_pose_wrist_distance": 0.50,
            "maximum_wrist_radius": 1.25,
            "outward_motion_radius_threshold": 0.75,
            "outward_motion_delta_threshold": 0.08,
            "maximum_recovered_observations_per_gap": 1,
            "require_previous_signing_or_other_direct_hand": True,
        },
        "velocity": {
            "wrist_velocity_clip_per_second": 0.75,
            "relative_landmark_velocity_clip_per_second": 0.50,
            "maximum_wrist_displacement": 0.12,
            "maximum_landmark_displacement": 0.15,
        },
    }


def _feature(left_x: float | None, right_x: float | None = None) -> np.ndarray:
    feature = np.zeros(258, dtype=np.float64)
    for side_index, value in enumerate((left_x, right_x)):
        if value is None:
            continue
        hand = np.zeros((21, 3), dtype=np.float64)
        hand[:, 0] = value + np.linspace(0.0, 0.20, 21)
        hand[:, 1] = np.linspace(0.0, 0.12, 21)
        feature[side_index * 63 : (side_index + 1) * 63] = hand.reshape(-1)
    pose = feature[126:].reshape(33, 4)
    pose[15, :2] = (left_x or 0.0, 0.0)
    pose[16, :2] = (right_x or 0.0, 0.0)
    return feature


def _prime(engine: OneObservationRecovery) -> None:
    engine.process("a", 0, 1, 1_000_000_000, _feature(0.10), False, None)
    engine.process("a", 1, 2, 1_200_000_000, _feature(0.12), True, None)


def test_hold_recovers_once_and_never_recursively() -> None:
    engine = OneObservationRecovery("C1_ONE_OBSERVATION_HOLD", _config())
    _prime(engine)
    recovered, records = engine.process(
        "a", 2, 3, 1_400_000_000, _feature(None), True, _feature(0.14)
    )
    assert records[0].state == "RECOVERED_HOLD"
    assert np.allclose(hand_block(recovered, 0), hand_block(_feature(0.12), 0))
    missing, records = engine.process(
        "a", 3, 4, 1_600_000_000, _feature(None), True, _feature(None)
    )
    assert records[0].state == "MISSING"
    assert not np.any(hand_block(missing, 0))


def test_velocity_is_bounded_and_uses_direct_history() -> None:
    engine = OneObservationRecovery("C2_ONE_OBSERVATION_BOUNDED_VELOCITY", _config())
    _prime(engine)
    recovered, records = engine.process(
        "a", 2, 3, 1_400_000_000, _feature(None), True, _feature(0.14)
    )
    displacement = hand_block(recovered, 0) - hand_block(_feature(0.12), 0)
    assert records[0].state == "RECOVERED_VELOCITY"
    assert np.max(np.linalg.norm(displacement, axis=1)) <= 0.1500001


def test_recovery_requires_two_consecutive_direct_observations() -> None:
    engine = OneObservationRecovery("C1_ONE_OBSERVATION_HOLD", _config())
    engine.process("a", 0, 1, 1_000_000_000, _feature(0.10), True, None)
    _, records = engine.process(
        "a", 1, 2, 1_200_000_000, _feature(None), True, _feature(0.12)
    )
    assert records[0].state == "MISSING"
    assert records[0].eligibility_reason == "insufficient_direct_history"


def test_recovered_observation_does_not_seed_direct_history() -> None:
    engine = OneObservationRecovery("C1_ONE_OBSERVATION_HOLD", _config())
    _prime(engine)
    engine.process("a", 2, 3, 1_400_000_000, _feature(None), True, _feature(0.14))
    state = engine.history["left"]
    assert state.latest_observation_index == 1
    assert state.previous_observation_index == 0


def test_no_context_leaves_hand_missing() -> None:
    engine = OneObservationRecovery("C1_ONE_OBSERVATION_HOLD", _config())
    engine.process("a", 0, 1, 1_000_000_000, _feature(0.10), False, None)
    engine.process("a", 1, 2, 1_200_000_000, _feature(0.12), False, None)
    _, records = engine.process(
        "a", 2, 3, 1_400_000_000, _feature(None), False, _feature(0.14)
    )
    assert records[0].state == "MISSING"
    assert records[0].eligibility_reason == "no_causal_signing_context"
