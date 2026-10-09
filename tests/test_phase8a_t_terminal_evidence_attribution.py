from __future__ import annotations

import inspect

import eval.runtime_diagnostics.phase8a_t_terminal_evidence_attribution as phase8at


def test_frozen_persisted_stream_identities() -> None:
    audit = phase8at.integrity_audit()
    assert audit["cal_streams"] == 54
    assert audit["dev_streams"] == 69
    assert audit["s2_checkpoint_sha256"] == phase8at.EXPECTED_S2_SHA
    assert not audit["s2_inference_rerun"]


def test_cal_and_dev_stream_membership() -> None:
    cal = phase8at._cal_streams()
    dev = phase8at._dev_streams()
    assert len(cal) == 54
    assert len(dev) == 69
    assert {row["population"] for row in cal} == {"CAL"}
    assert {row["population"] for row in dev} == {"DEV"}
    assert len({row["sample_id"] for row in dev}) == 23


def test_no_training_decoder_search_recognition_or_phone() -> None:
    source = inspect.getsource(phase8at)
    assert ".fit(" not in source
    assert "load_model(" not in source
    assert "phone_replay" not in source
    assert "recognizer" not in source.lower()
    assert "threshold_grid" not in source


def test_decision_is_clip_and_view_guarded() -> None:
    source = inspect.getsource(phase8at.analyze)
    assert "view_requirement" in source
    assert "clip_requirement" in source
    assert "0.70" in source
    assert "2.0 / 3.0" in source


def test_materializer_and_config01_are_unchanged() -> None:
    assert phase8at.CONFIG_01.minimum_active_ms == 133.308
    assert phase8at.CONFIG_01.post_confirm_ms == 266.616
    assert phase8at.MATERIALIZER_CONFIG.requested_pre_context_ms == 250.0
    assert phase8at.MATERIALIZER_CONFIG.requested_post_context_ms == 250.0
