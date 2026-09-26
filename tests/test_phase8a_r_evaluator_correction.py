from __future__ import annotations

from typing import Any

import eval.runtime_diagnostics.phase8a_r_evaluator_correction as correction
from pipeline.perception_vnext.segmentation.streaming_decoder import (
    ACTIVE_SIGN,
    POST_RECOVERY,
    PRE_IDLE,
)


def synthetic_view(
    states: list[int], timestamps: list[float], human_start: float, human_end: float
) -> dict[str, Any]:
    observations = [
        {
            "observation_index": index,
            "timestamp_ms": timestamp,
            "pre_probability": 1.0 if state == PRE_IDLE else 0.0,
            "active_probability": 1.0 if state == ACTIVE_SIGN else 0.0,
            "post_probability": 1.0 if state == POST_RECOVERY else 0.0,
            "argmax_state": state,
            "argmax_state_name": correction.STATE_NAMES[state],
            "human_start_ms": human_start,
            "human_end_ms": human_end,
        }
        for index, (timestamp, state) in enumerate(zip(timestamps, states, strict=True))
    ]
    import numpy as np

    probs = np.asarray(
        [
            [row["pre_probability"], row["active_probability"], row["post_probability"]]
            for row in observations
        ]
    )
    runs = correction.old.state_runs(np.asarray(timestamps), probs, np.asarray(states))
    return {
        "view_key": "synthetic",
        "sample_id": "synthetic",
        "view_id": "SYNTHETIC",
        "human_start_ms": human_start,
        "human_end_ms": human_end,
        "observations": observations,
        "state_runs": runs,
    }


def diagnose(
    view: dict[str, Any], baseline_recall: float = 0.0
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    trajectory = correction.replay_trajectory(view)
    rows = correction.interruption_attribution(view, trajectory, baseline_recall, True)
    return trajectory, rows


def test_case_a_post_active_resumption_does_not_require_prior_emission() -> None:
    view = synthetic_view(
        [
            PRE_IDLE,
            ACTIVE_SIGN,
            ACTIVE_SIGN,
            POST_RECOVERY,
            ACTIVE_SIGN,
            POST_RECOVERY,
            POST_RECOVERY,
        ],
        [0, 100, 250, 400, 500, 700, 1000],
        100,
        500,
    )
    trajectory, rows = diagnose(view)
    post = rows[0]
    assert post["later_active_resumption_ms"] == 500
    assert post["v1_handling"] == "CANCELED_BY_V1"
    assert not post["v1_closed_candidate_before_resumption"]
    assert len(trajectory["events"]) == 1


def test_case_b_pre_discard_then_active_is_evaluated() -> None:
    view = synthetic_view(
        [
            PRE_IDLE,
            ACTIVE_SIGN,
            ACTIVE_SIGN,
            PRE_IDLE,
            PRE_IDLE,
            ACTIVE_SIGN,
            ACTIVE_SIGN,
            POST_RECOVERY,
            POST_RECOVERY,
        ],
        [0, 100, 250, 350, 500, 650, 800, 950, 1250],
        100,
        800,
    )
    trajectory, rows = diagnose(view)
    pre = rows[0]
    assert trajectory["candidate_discard_count"] == 1
    assert pre["v1_handling"] == "DISCARDED_BEFORE_RESUMPTION"
    assert pre["causally_attributable"]
    assert pre["bounded_causally_recoverable"]
    assert pre["minimum_required_grace_ms"] == 300


def test_case_c_post_eof_is_right_censored_only_when_time_is_sole_blocker() -> None:
    view = synthetic_view(
        [PRE_IDLE, ACTIVE_SIGN, ACTIVE_SIGN, POST_RECOVERY, POST_RECOVERY],
        [0, 100, 300, 500, 600],
        100,
        300,
    )
    trajectory, _ = diagnose(view)
    record = correction.right_censoring_record(view, trajectory, False)
    assert record is not None
    assert record["classification"] == "RIGHT_CENSORED_CONFIRMATION"
    assert record["additional_elapsed_time_required_ms"] > 0
    assert not record["synthetic_future_states_used"]


def test_case_d_pre_eof_without_later_active_is_not_recoverable() -> None:
    view = synthetic_view(
        [PRE_IDLE, ACTIVE_SIGN, ACTIVE_SIGN, PRE_IDLE, PRE_IDLE],
        [0, 100, 300, 500, 600],
        100,
        300,
    )
    trajectory, rows = diagnose(view)
    assert rows == []
    record = correction.right_censoring_record(view, trajectory, False)
    assert record is not None
    assert record["classification"] != "RIGHT_CENSORED_CONFIRMATION"


def test_case_e_stable_pre_separates_early_episode_from_true_sign() -> None:
    view = synthetic_view(
        [
            ACTIVE_SIGN,
            ACTIVE_SIGN,
            PRE_IDLE,
            PRE_IDLE,
            PRE_IDLE,
            ACTIVE_SIGN,
            ACTIVE_SIGN,
            POST_RECOVERY,
            POST_RECOVERY,
        ],
        [100, 250, 400, 800, 1200, 1500, 1700, 1900, 2200],
        1500,
        1700,
    )
    _, rows = diagnose(view)
    pre = rows[0]
    assert pre["stable_pre_separation"]
    assert pre["unsafe_distinct_episode_merge"]
    assert not pre["causally_attributable"]


def test_case_f_later_active_outside_human_is_not_beneficial() -> None:
    view = synthetic_view(
        [
            ACTIVE_SIGN,
            ACTIVE_SIGN,
            POST_RECOVERY,
            POST_RECOVERY,
            ACTIVE_SIGN,
            POST_RECOVERY,
            POST_RECOVERY,
        ],
        [100, 250, 400, 700, 800, 1000, 1300],
        100,
        400,
    )
    _, rows = diagnose(view)
    post = rows[0]
    assert not post["later_active_inside_human_active"]
    assert not post["causally_attributable"]


def test_case_g_late_start_not_misattributed_to_internal_post() -> None:
    view = synthetic_view(
        [
            PRE_IDLE,
            ACTIVE_SIGN,
            ACTIVE_SIGN,
            POST_RECOVERY,
            ACTIVE_SIGN,
            POST_RECOVERY,
            POST_RECOVERY,
        ],
        [0, 500, 650, 800, 900, 1100, 1400],
        0,
        1000,
    )
    _, rows = diagnose(view, baseline_recall=0.5)
    post = rows[0]
    assert post["v1_handling"] == "CANCELED_BY_V1"
    assert not post["causally_attributable"]


def test_case_h_emission_without_later_active_has_no_recovery() -> None:
    view = synthetic_view(
        [ACTIVE_SIGN, ACTIVE_SIGN, POST_RECOVERY, POST_RECOVERY],
        [100, 300, 500, 800],
        100,
        300,
    )
    trajectory, rows = diagnose(view)
    assert len(trajectory["events"]) == 1
    assert rows == []


def test_continuity_uses_persisted_cal_only_and_no_inference() -> None:
    continuity, bug, manifest = correction.continuity_and_bug_audit()
    assert continuity["cal_views"] == 54
    assert continuity["cal_clips"] == 18
    assert continuity["primary_failure_count"] == 22
    assert continuity["persisted_probabilities_reused"]
    assert not continuity["s2_inference_rerun"]
    assert not continuity["dev_access"]
    assert not continuity["phone_access"]
    assert not continuity["training"]
    assert bug["defect_confirmed"]
    assert len(manifest["views"]) == 54


def test_source_does_not_train_tune_or_implement_decoder_v2() -> None:
    source = correction.Path(correction.__file__).read_text(encoding="utf-8")
    assert ".fit(" not in source
    assert "_model_predictions(" not in source
    assert "decoder_grid(" not in source
    assert "class DecoderV2" not in source
    assert 'p7._load_view_rows({"DEV"})' not in source
