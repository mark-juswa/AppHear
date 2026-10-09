from __future__ import annotations

import inspect

import numpy as np

import eval.runtime_diagnostics.phase8a_m2_frozen_sparse_dev_validation as phase8am2
from pipeline.perception_vnext.segmentation.streaming_decoder import (
    CausalStreamingSignEventDecoder,
)


def test_frozen_identity_matches() -> None:
    audit = phase8am2.identity_audit()
    assert audit["s2_checkpoint_sha256"] == phase8am2.EXPECTED_S2_SHA
    assert audit["materializer_contract_sha256"] == phase8am2.EXPECTED_MATERIALIZER_CONTRACT_SHA
    assert audit["feature_width"] == 378


def test_exact_signer_disjoint_dev_membership() -> None:
    rows, audit = phase8am2.load_dev_rows()
    assert len(rows) == 69
    assert len({row["sample_id"] for row in rows}) == 23
    assert {row["phase7_partition"] for row in rows} == {"DEV"}
    assert audit["segmentation_train_signers"] > 0
    assert audit["signer_overlap_with_segmentation_train"] == []
    assert audit["views_by_cadence"] == {"VIEW_A": 23, "VIEW_B": 23, "VIEW_C": 23}


def test_config01_and_materializer_are_frozen() -> None:
    assert phase8am2.CONFIG_01.minimum_active_ms == 133.308
    assert phase8am2.CONFIG_01.pre_gap_reset_ms == 133.308
    assert phase8am2.CONFIG_01.post_confirm_ms == 266.616
    assert phase8am2.MATERIALIZER_CONFIG.requested_pre_context_ms == 250.0
    assert phase8am2.MATERIALIZER_CONFIG.requested_post_context_ms == 250.0


def test_interval_metrics_make_no_event_a_strict_failure() -> None:
    result = phase8am2.interval_metrics(None, None, 500.0, 1500.0, 2500.0)
    assert result["active_recall"] == 0.0
    assert not result["contained_90pct"]
    assert result["premature_cut"]
    assert result["severe_cut"]
    assert result["context_reduction_fraction"] == 0.0


def test_failure_categories_are_evidence_bounded() -> None:
    late = {
        "contained_90pct": False,
        "active_recall": 0.8,
        "missing_at_start_ms": 300.0,
        "missing_at_end_ms": 100.0,
    }
    assert phase8am2.poor_event_classification(late) == "LATE_ACTIVE_START"
    wrong = dict(late, active_recall=0.0)
    assert phase8am2.poor_event_classification(wrong) == "WRONG_TEMPORAL_EPISODE"


def test_decision_keeps_event_and_materializer_layers_separate() -> None:
    source = inspect.getsource(phase8am2.decide)
    assert "event_supported" in source
    assert "materializer_supported" in source
    assert "MATERIALIZER_DEV_SUPPORTED_EVENT_PRODUCER_LIMITED" in source


def test_no_training_recognition_or_phone_path() -> None:
    source = inspect.getsource(phase8am2)
    assert ".fit(" not in source
    assert "phone_replay_predictions" not in source
    assert "recognizer" not in source.lower()
    assert "RecognitionV2" not in source


def test_persisted_state_reuse_is_identity_guarded() -> None:
    source = inspect.getsource(phase8am2.run_validation)
    assert "PHASE8A_M2_PERSISTED_DEV_STATE_IDENTITY_MISMATCH" in source
    assert "PHASE8A_M2_PERSISTED_DEV_TIMESTAMP_MISMATCH" in source


def test_missing_post_and_source_censoring_are_separate() -> None:
    timestamps = np.asarray([0.0, 133.0, 266.0, 399.0])
    probabilities = np.asarray([[0.0, 1.0, 0.0]] * 4)
    states = np.asarray([1, 1, 1, 1])
    decoder = CausalStreamingSignEventDecoder(phase8am2.CONFIG_01)
    decoder.run(timestamps, probabilities, states)
    censored = phase8am2.no_event_classification(decoder, timestamps, 350.0)
    genuine = phase8am2.no_event_classification(decoder, timestamps, 0.0)
    assert censored["classification"] == "RIGHT_CENSORED_NO_TERMINAL_OPPORTUNITY"
    assert genuine["classification"] == "MISSING_TERMINAL_POST"


def test_materializer_does_not_modify_logical_event() -> None:
    source = inspect.getsource(phase8am2.run_validation)
    assert '"logical_event_identity_preserved_by_materializer": True' in source
    assert "materialize_recognition_window" in source
