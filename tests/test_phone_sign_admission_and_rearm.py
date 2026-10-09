from __future__ import annotations

from eval.runtime_diagnostics.phone_sign_admission_and_rearm import phone_region_summary


def observation(index: int, state: int, *, observed: bool, body: bool) -> dict[str, object]:
    return {
        "source_index": index,
        "argmax_state": state,
        "active_probability": 0.9 if state == 1 else 0.05,
        "post_probability": 0.9 if state == 2 else 0.05,
        "dt_ms": 200.0,
        "left_observed": observed,
        "right_observed": False,
        "left_proposal": True,
        "right_proposal": False,
        "body_available": body,
    }


def test_region_keeps_preceding_and_active_evidence_separate() -> None:
    rows = [
        observation(0, 2, observed=False, body=False),
        observation(1, 2, observed=False, body=False),
        observation(2, 1, observed=True, body=True),
        observation(3, 1, observed=True, body=True),
    ]
    result = phone_region_summary(rows, 2, 3, preceding_count=2)
    assert result["preceding"]["argmax_states"] == [2, 2]
    assert result["active_episode"]["argmax_states"] == [1, 1]
    assert result["fresh_argmax_transition_from_non_active"] is True


def test_missing_refinement_is_descriptive_not_a_semantic_label() -> None:
    rows = [
        observation(0, 2, observed=False, body=False),
        observation(1, 1, observed=False, body=False),
        observation(2, 1, observed=False, body=False),
    ]
    result = phone_region_summary(rows, 1, 2, preceding_count=1)
    assert result["active_episode"]["both_refined_hands_unobserved_fraction"] == 1.0
    assert "semantic_classification" not in result
