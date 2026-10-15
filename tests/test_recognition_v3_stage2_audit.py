"""Integrity of the diagnosis, not model/ASL accuracy tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eval.runtime_diagnostics import recognition_v3_stage2_audit as audit


def row(index: int, state: int = 2) -> dict:
    return dict(
        source_index=index,
        source_timestamp_ms=index * 250.0,
        argmax_state=state,
        event_state_before="IDLE",
        event_state_after="IDLE",
        event_action="NO_CHANGE",
        active_probability=0.01,
        left_observed=False,
        right_observed=False,
        left_proposal=True,
        right_proposal=False,
        hand_delta_valid_count=0,
        body_valid_point_count=8,
        admission_decision=None,
        left_valid_joint_count=21,
    )


def test_valid_coordinates_do_not_imply_an_accepted_hand() -> None:
    summary = audit.span_summary([row(0), row(1)])
    assert summary["any_accepted_hand_observations"] == 0
    assert summary["any_proposed_hand_observations"] == 2
    assert summary["zero_active_cannot_be_repaired_by_rearm_alone"] is True
    assert summary["admission_rejections"] == 0
    assert summary["ready_observations"] == 2


def test_waiting_active_is_distinguished_from_missing_active() -> None:
    blocked = row(0, state=1)
    blocked["event_state_before"] = audit.legacy.WAIT
    actual = audit.span_summary([blocked])
    assert actual["blocked_active_indices"] == [0]
    assert actual["zero_active_cannot_be_repaired_by_rearm_alone"] is False
    assert "genuine_sign" not in actual


def test_sampling_reports_missing_evidence_without_inventing_frame_drops() -> None:
    a, b = row(0), row(1)
    b["source_timestamp_ms"] = 1000.0
    summary = audit.sampling_summary([a, b])
    assert summary["gaps_over_533_232_ms"] == 1
    assert summary["sensor_frame_drops"] == "NOT_MEASURED"
    assert summary["dense_counterfactual"] == "UNAVAILABLE_NO_UNPROCESSED_SENSOR_FRAMES"


def test_empty_sign_span_is_rejected() -> None:
    with pytest.raises(ValueError, match="EMPTY_REVIEWED_SPAN"):
        audit.span_summary([])


@pytest.mark.parametrize("actual", [np.zeros((2, 3)), np.array([np.nan])])
def test_parity_rejects_invalid_shapes_and_numbers(actual: np.ndarray) -> None:
    with pytest.raises(ValueError, match="INVALID_PARITY_TENSORS"):
        audit.compare(actual, np.zeros(1), 1e-6)


def test_parity_failure_is_not_promoted() -> None:
    assert audit.compare(np.array([0.2]), np.array([0.0]), 1e-6)["pass"] is False


def test_fixture_export_preserves_real_values_and_event_link(tmp_path: Path) -> None:
    target = tmp_path / "capture.tsv"
    rows = [row(0), row(1)]
    audit.export_kotlin_fixture(rows, [{"commit_index": 1, "event_id": 7}], target)
    lines = target.read_text().splitlines()[1:]
    assert lines[0].split("\t") == ["0", "0.0", "2", "IDLE", "IDLE", "NO_CHANGE", "0"]
    assert lines[1].split("\t")[-1] == "7"


def test_prediction_hook_preserves_default_replay_and_sees_only_previous_action() -> None:
    from eval.runtime_diagnostics.phone_repeated_recognition_integration import replay

    states = [0, 1, 1, 2, 2, 2, 2, 2, 1, 1, 2, 2, 2]
    rows = []
    for index, state in enumerate(states):
        value = row(index, state)
        value["source_timestamp_ms"] = index * 200.0
        value.update(
            pre_probability=0.98 if state == 0 else 0.01,
            active_probability=0.98 if state == 1 else 0.01,
            post_probability=0.98 if state == 2 else 0.01,
        )
        rows.append(value)
    seen = []

    def predict(value: dict, previous_action: str | None) -> dict:
        seen.append((value["source_index"], previous_action))
        return dict(value)

    baseline = replay(rows, allow_post_rearm=True, exact_android_commit_recovery=True)
    hooked = replay(
        rows, allow_post_rearm=True, exact_android_commit_recovery=True, prediction_hook=predict
    )
    assert baseline == hooked
    assert [index for index, action in seen if action == "REARM_COMPLETE"] == [8]
    assert rows[0]["argmax_state"] == 0


def test_prediction_hook_cannot_change_capture_identity() -> None:
    from eval.runtime_diagnostics.phone_repeated_recognition_integration import replay

    def corrupt(value: dict, previous_action: str | None) -> dict:
        return {**value, "source_timestamp_ms": -1.0}

    with pytest.raises(ValueError, match="PREDICTION_HOOK_CHANGED_CAPTURE_IDENTITY"):
        replay([row(0)], allow_post_rearm=True, prediction_hook=corrupt)


def test_in_place_hook_edit_cannot_mutate_saved_source_identity() -> None:
    from eval.runtime_diagnostics.phone_repeated_recognition_integration import replay

    original = row(0)

    def corrupt(value: dict, previous_action: str | None) -> dict:
        value["source_timestamp_ms"] = -1.0
        return value

    with pytest.raises(ValueError, match="PREDICTION_HOOK_CHANGED_CAPTURE_IDENTITY"):
        replay([original], allow_post_rearm=True, prediction_hook=corrupt)
    assert original["source_timestamp_ms"] == 0.0
