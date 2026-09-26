from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np

import eval.runtime_diagnostics.phase8a_r_causal_episode_failure_attribution as p8r


def test_fixed_config_01_is_diagnostic_reference_only() -> None:
    assert p8r.CONFIG_01.minimum_active_ms == 133.308
    assert p8r.CONFIG_01.pre_gap_reset_ms == 133.308
    assert p8r.CONFIG_01.post_confirm_ms == 266.616
    assert p8r.CONFIG_01.pre_padding_ms == 250.0
    assert p8r.CONFIG_01.post_padding_ms == 250.0
    assert p8r.CONFIG_01.rearm_pre_stable_ms == 399.924
    source = Path(p8r.__file__).read_text(encoding="utf-8")
    assert "decoder_grid(" not in source
    assert "probability_threshold" not in source


def test_implementation_audit_opens_exactly_cal() -> None:
    source = inspect.getsource(p8r.implementation_audit)
    assert 'p7._load_view_rows({"CAL"})' in source
    assert 'p7._load_view_rows({"DEV"})' not in source
    audit = p8r.read_json(p8r.OUT / "implementation_audit.json")
    rows = p8r.p7._load_view_rows({"CAL"})
    assert len(rows) == 54
    assert len({row["sample_id"] for row in rows}) == 18
    assert {row["phase7_partition"] for row in rows} == {"CAL"}
    assert not audit["dev_access"]
    assert not audit["known_phone_access"]
    assert not audit["training"]
    assert not audit["decoder_v2_implemented"]


def test_state_runs_are_deterministic_and_timestamp_based() -> None:
    timestamps = np.asarray([0.0, 100.0, 250.0, 500.0, 800.0])
    states = np.asarray([1, 1, 2, 2, 1], np.int32)
    probabilities = np.eye(3, dtype=np.float64)[states]
    first = p8r.state_runs(timestamps, probabilities, states)
    second = p8r.state_runs(timestamps, probabilities, states)
    assert first == second
    assert first[0]["state"] == "ACTIVE"
    assert first[1]["state"] == "POST"
    assert first[1]["start_ms"] == 250.0


def test_interruption_duration_uses_elapsed_timestamps() -> None:
    timestamps = np.asarray([0.0, 100.0, 250.0, 500.0, 800.0])
    states = np.asarray([1, 1, 2, 2, 1], np.int32)
    probabilities = np.eye(3, dtype=np.float64)[states]
    runs = p8r.state_runs(timestamps, probabilities, states)
    interruptions = p8r.interruptions_from_runs(runs, 0.0, 900.0)
    assert len(interruptions) == 1
    assert interruptions[0]["state"] == "POST"
    assert interruptions[0]["duration_until_active_resumption_ms"] == 550.0
    assert interruptions[0]["inside_human_active"]


def test_interval_metrics_decomposes_missing_start_and_end() -> None:
    metrics = p8r.interval_metrics(200.0, 800.0, 100.0, 900.0, 1200.0)
    assert metrics["missing_at_start_ms"] == 100.0
    assert metrics["missing_at_end_ms"] == 100.0
    assert metrics["active_recall"] == 0.75
    assert p8r._dominant_truncation(metrics) == "BOTH"


def test_no_training_feature_change_phone_or_dev_entrypoint() -> None:
    source = inspect.getsource(p8r.analyze)
    assert "model.fit(" not in source
    assert "derive_causal_segmentation_features" not in source
    assert "PHONE_SESSION" not in source
    assert "SOURCE_SESSION" not in source
    assert "RecognitionV2" not in source
    assert "DecoderV2" not in source


def test_recoverability_records_prohibit_future_beyond_commit() -> None:
    source = inspect.getsource(p8r._attribute)
    assert '"all_information_observed_by_candidate_commit": causal_recoverable' in source
    assert '"global_rank_used_as_runtime_signal": False' in source
    assert '"human_label_used_only_for_evaluation": True' in source


def test_written_reproductions_match_frozen_artifacts() -> None:
    audit_path = p8r.OUT / "implementation_audit.json"
    if not audit_path.is_file():
        return
    audit = p8r.read_json(audit_path)
    if "reproduction" not in audit:
        return
    reproduction = audit["reproduction"]
    assert reproduction["phase7_global"]["matches_written"]
    assert reproduction["phase8a_config_01"]["matches_written"]
    assert reproduction["model_inference_rerun_required_for_probabilities"]
