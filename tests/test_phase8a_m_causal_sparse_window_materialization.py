from __future__ import annotations

import inspect

import eval.runtime_diagnostics.phase8a_m_causal_sparse_window_materialization as phase8am


def test_phase8am_loads_only_frozen_cal() -> None:
    rows, by_key, state = phase8am.load_inputs()
    assert len(rows) == 54
    assert len({row["sample_id"] for row in rows}) == 18
    assert {row["phase7_partition"] for row in rows} == {"CAL"}
    assert len(by_key) == 54
    assert state["s2_checkpoint_sha256"] == phase8am.EXPECTED_S2_SHA


def test_phase8am_has_no_model_inference_training_or_recognition() -> None:
    source = inspect.getsource(phase8am)
    assert "_model_predictions(" not in source
    assert ".fit(" not in source
    assert "RecognitionV2" not in source
    assert "recognizer" not in source.lower()
    assert 'p7._load_view_rows({"DEV"})' not in source


def test_b_and_c_share_identical_logical_events() -> None:
    rows, _ = phase8am.evaluate()
    assert all(row["b_c_logical_decision_equal"] for row in rows)
    assert all(row["b_c_logical_boundary_equal"] is not False for row in rows)


def test_materializer_uses_fixed_context_without_grid() -> None:
    assert phase8am.MATERIALIZER_CONFIG.requested_pre_context_ms == 250.0
    assert phase8am.MATERIALIZER_CONFIG.requested_post_context_ms == 250.0
    source = inspect.getsource(phase8am.evaluate)
    assert "for padding" not in source
    assert "padding_grid" not in source
