from __future__ import annotations

from eval.runtime_diagnostics.s2_r2_temporal_supervision_readiness import (
    load_phone_join,
    summarize_phone_baseline,
)


def test_phone_baseline_summary_separates_human_and_predicted_state() -> None:
    rows = []
    attempts = (
        ("attempt_001", "HELLO", "POSITIVE_ANCHOR"),
        ("attempt_002", "HELLO", "HARD_POSITIVE_MISS"),
        ("attempt_003", "HOME", "HARD_POSITIVE_MISS"),
        ("attempt_004", "HOME", "HARD_POSITIVE_MISS"),
        ("attempt_005", "TABLE", "POSITIVE_ANCHOR"),
    )
    for attempt_id, gloss, role in attempts:
        for index in range(40):
            human = "ACTIVE_SIGN" if index == 20 else "POST_RECOVERY"
            prediction = (
                "ACTIVE_SIGN"
                if attempt_id == "attempt_001" and index == 20
                else "POST_RECOVERY"
            )
            rows.append(
                {
                    "attempt_id": attempt_id,
                    "expected_gloss": gloss,
                    "supervision_role": role,
                    "state_name": human,
                    "prediction_name": prediction,
                    "active_probability": 0.8 if prediction == "ACTIVE_SIGN" else 0.1,
                }
            )
    rows.extend(
        {
            "attempt_id": "attempt_005",
            "expected_gloss": "TABLE",
            "supervision_role": "POSITIVE_ANCHOR",
            "state_name": "IGNORED",
            "prediction_name": "POST_RECOVERY",
            "active_probability": 0.0,
        }
        for _ in range(2)
    )
    summary = summarize_phone_baseline(rows)
    assert summary["observations_total"] == 202
    assert summary["attempts_with_any_s2_active_during_human_active"] == 1
    assert summary["confusion_actual_rows_predicted_columns"]["ACTIVE_SIGN"] == {
        "ACTIVE_SIGN": 1,
        "POST_RECOVERY": 4,
    }


def test_phone_join_accepts_numeric_session_attempt_ordinal(tmp_path) -> None:
    labels = tmp_path / "labels.csv"
    labels.write_text(
        "attempt_id,attempt_ordinal,expected_gloss,supervision_role,state_id,state_name,"
        "source_timestamp_ns\n"
        "attempt_001,1,HELLO,POSITIVE_ANCHOR,1,ACTIVE_SIGN,1000000\n",
        encoding="utf-8",
    )
    observations = tmp_path / "observations.jsonl"
    observations.write_text(
        '{"source_timestamp_ms":1.0,"attempt_id":1,"argmax_state":2,'
        '"pre_probability":0.0,"active_probability":0.1,"post_probability":0.9}\n',
        encoding="utf-8",
    )
    joined = load_phone_join(labels, observations)
    assert joined[0]["attempt_id"] == "attempt_001"
