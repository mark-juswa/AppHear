from __future__ import annotations

from eval.runtime_diagnostics.phone_event_lifecycle_rearm_correction import replay


def stream(states: list[int], step_ms: float = 200.0) -> tuple[list[float], list[list[float]]]:
    times = [index * step_ms for index in range(len(states))]
    probabilities = [
        [0.98 if state == 0 else 0.01, 0.98 if state == 1 else 0.01, 0.98 if state == 2 else 0.01]
        for state in states
    ]
    return times, probabilities


def test_post_does_not_rearm_pre_only_control() -> None:
    states = [0, 1, 1, 2, 2, 2, 2, 2, 2]
    times, probabilities = stream(states)
    result = replay(times, probabilities, states, allow_post_rearm=False)
    assert result["event_count"] == 1
    assert result["rearm_complete_count"] == 0


def test_stable_post_rearms_non_active_candidate() -> None:
    states = [0, 1, 1, 2, 2, 2, 2, 2, 2]
    times, probabilities = stream(states)
    result = replay(times, probabilities, states, allow_post_rearm=True)
    assert result["event_count"] == 1
    assert result["rearm_complete_count"] == 1


def test_active_resets_non_active_rearm_timer() -> None:
    states = [0, 1, 1, 2, 2, 2, 1, 2, 2]
    times, probabilities = stream(states)
    result = replay(times, probabilities, states, allow_post_rearm=True)
    assert result["rearm_complete_count"] == 0


def test_first_event_is_identical_between_rearm_policies() -> None:
    states = [0, 1, 1, 2, 2, 2, 2, 1, 1, 2, 2, 2]
    times, probabilities = stream(states)
    control = replay(times, probabilities, states, allow_post_rearm=False)
    candidate = replay(times, probabilities, states, allow_post_rearm=True)
    assert candidate["event_identities"][0] == control["event_identities"][0]


def test_candidate_exposes_duplicate_risk_after_rearm() -> None:
    states = [0, 1, 1, 2, 2, 2, 2, 2, 2, 1, 1, 2, 2, 2]
    times, probabilities = stream(states)
    result = replay(times, probabilities, states, allow_post_rearm=True)
    assert result["event_count"] == 2


def test_pre_also_rearms_candidate_without_special_mapping() -> None:
    states = [0, 1, 1, 2, 2, 0, 0, 0]
    times, probabilities = stream(states)
    result = replay(times, probabilities, states, allow_post_rearm=True)
    assert result["rearm_complete_count"] == 1
