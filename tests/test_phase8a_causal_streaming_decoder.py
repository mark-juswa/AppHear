from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError, asdict
from pathlib import Path

import numpy as np
import pytest

import eval.runtime_diagnostics.phase8a_causal_streaming_decoder as p8
from pipeline.perception_vnext.segmentation.streaming_decoder import (
    CausalStreamingSignEventDecoder,
    DecoderState,
    StreamingDecoderConfig,
)


def _run(states: list[int], timestamps: list[float], config: StreamingDecoderConfig | None = None):
    decoder = CausalStreamingSignEventDecoder(config or StreamingDecoderConfig(100.0, 200.0, 250.0))
    probabilities = np.eye(3, dtype=np.float64)[np.asarray(states, np.int32)]
    decoder.run(timestamps, probabilities, states)
    return decoder


def test_exact_grid_is_27_and_frozen_values_only() -> None:
    grid = p8.decoder_grid()
    assert len(grid) == 27
    assert {row.minimum_active_ms for row in grid} == {133.308, 199.962, 266.616}
    assert {row.pre_gap_reset_ms for row in grid} == {133.308, 199.962, 266.616}
    assert {row.post_confirm_ms for row in grid} == {266.616, 399.924, 533.232}
    assert {row.pre_padding_ms for row in grid} == {250.0}
    assert {row.post_padding_ms for row in grid} == {250.0}
    assert {row.rearm_pre_stable_ms for row in grid} == {399.924}


def test_frozen_s2_identity_and_sparse_population() -> None:
    identity = p8.verify_s2_identity()
    assert identity["checkpoint"]["sha256"] == p8.EXPECTED_MODEL_SHA
    assert identity["best_epoch"] == 17
    assert identity["cal_views"] == 54
    assert identity["dev_views"] == 69
    assert identity["feature_width"] == 378
    assert not identity["training_in_phase8a"]


def test_prefix_invariance_for_every_prefix() -> None:
    timestamps = [0.0, 120.0, 250.0, 400.0, 550.0, 700.0, 850.0, 1000.0]
    states = [0, 1, 1, 2, 2, 2, 0, 0]
    full = _run(states, timestamps)
    for length in range(1, len(states) + 1):
        prefix = _run(states[:length], timestamps[:length])
        expected = [asdict(event) for event in full.events if event.emitted_at_index < length]
        assert [asdict(event) for event in prefix.events] == expected
        assert prefix.trace == full.trace[:length]


def test_active_to_pre_never_emits_and_sustained_pre_discards() -> None:
    decoder = _run([1, 1, 0, 0, 0], [0.0, 120.0, 200.0, 400.0, 650.0])
    assert decoder.events == []
    assert decoder.candidate_discard_count == 1
    assert decoder.state == DecoderState.IDLE
    assert "DISCARD_SUSTAINED_PRE_GAP" in [row["action"] for row in decoder.trace]


def test_short_pre_gap_bridges_same_candidate() -> None:
    decoder = _run(
        [1, 1, 0, 1, 2, 2, 2],
        [0.0, 120.0, 200.0, 300.0, 400.0, 550.0, 700.0],
    )
    assert len(decoder.events) == 1
    assert decoder.bridged_pre_gap_count == 1
    assert decoder.events[0].logical_active_start_index == 0
    assert decoder.events[0].logical_active_end_index == 3


def test_active_to_post_requires_persistence_and_brief_post_does_not_cut() -> None:
    decoder = _run(
        [1, 1, 2, 1, 1, 2, 2, 2],
        [0.0, 120.0, 220.0, 300.0, 420.0, 520.0, 650.0, 800.0],
    )
    assert len(decoder.events) == 1
    assert decoder.events[0].logical_active_end_index == 4
    assert "CANCEL_POST_ACTIVE_RESUMED" in [row["action"] for row in decoder.trace]


def test_post_to_pre_counts_as_continuing_terminal_evidence() -> None:
    decoder = _run(
        [1, 1, 2, 0, 0],
        [0.0, 150.0, 300.0, 450.0, 600.0],
    )
    assert len(decoder.events) == 1
    assert decoder.events[0].first_post_index == 2
    assert decoder.events[0].emitted_at_index == 4


def test_too_short_active_candidate_is_discarded_after_post_confirmation() -> None:
    decoder = _run(
        [1, 2, 2, 2],
        [0.0, 100.0, 250.0, 400.0],
        StreamingDecoderConfig(133.308, 199.962, 266.616),
    )
    assert decoder.events == []
    assert decoder.candidate_discard_count == 1
    assert decoder.trace[-1]["action"] == "DISCARD_TOO_SHORT"


def test_padding_uses_only_observed_samples_available_at_emission() -> None:
    timestamps = [0.0, 100.0, 220.0, 330.0, 470.0, 610.0, 760.0]
    decoder = _run([0, 1, 1, 2, 2, 2, 0], timestamps)
    event = decoder.events[0]
    assert event.padded_start_ms in timestamps
    assert event.padded_end_ms in timestamps
    assert event.padded_end_index <= event.emitted_at_index
    assert event.padded_start_ms == 0.0
    assert event.padded_end_ms == 470.0


def test_event_is_immutable_and_rearm_requires_stable_pre_elapsed_time() -> None:
    decoder = _run(
        [1, 1, 2, 2, 2, 0, 0, 0, 1],
        [0.0, 120.0, 250.0, 400.0, 550.0, 600.0, 800.0, 1000.0, 1100.0],
    )
    assert len(decoder.events) == 1
    frozen = asdict(decoder.events[0])
    assert decoder.trace[7]["action"] == "REARM_COMPLETE"
    assert decoder.trace[8]["action"] == "START_ACTIVE_CANDIDATE"
    assert asdict(decoder.events[0]) == frozen
    with pytest.raises(FrozenInstanceError):
        decoder.events[0].padded_end_ms = 999.0  # type: ignore[misc]


def test_no_end_of_sequence_flush() -> None:
    decoder = _run([0, 1, 1, 1], [0.0, 100.0, 300.0, 700.0])
    assert decoder.events == []
    assert decoder.state == DecoderState.ACTIVE_CANDIDATE


def test_all_durations_use_timestamps_not_observation_counts() -> None:
    # Same states and counts, but only the long-elapsed stream can confirm POST.
    short = _run([1, 1, 2, 2], [0.0, 100.0, 150.0, 200.0])
    long = _run([1, 1, 2, 2], [0.0, 100.0, 150.0, 450.0])
    assert len(short.events) == 0
    assert len(long.events) == 1


def test_nonchronological_timestamps_are_rejected() -> None:
    decoder = CausalStreamingSignEventDecoder(StreamingDecoderConfig(100.0, 200.0, 250.0))
    decoder.consume(10.0, [1.0, 0.0, 0.0], 0)
    with pytest.raises(ValueError, match="NON_CHRONOLOGICAL_TIMESTAMP"):
        decoder.consume(10.0, [1.0, 0.0, 0.0], 0)


def test_phase_order_blocks_phone_before_dev_and_contains_no_training_call() -> None:
    source = Path(p8.__file__).read_text(encoding="utf-8")
    phone_source = inspect.getsource(p8.known_phone_replay)
    assert "PHASE8A_PHONE_REPLAY_FORBIDDEN_BEFORE_DEV_PASS" in phone_source
    assert "model.fit(" not in source
    assert "compile(" not in source
    assert "Candidate01Offline" not in source
    assert "RecognitionV2" not in inspect.getsource(p8.cal_search)
    assert "SOURCE_SESSION" not in inspect.getsource(p8.cal_search)
    assert "SOURCE_SESSION" not in inspect.getsource(p8.evaluate_sparse_dev)


def test_cal_eligibility_and_selection_are_predeclared() -> None:
    source = inspect.getsource(p8.is_cal_eligible)
    assert 'metrics["event_emission_rate"] >= 0.95' in source
    assert 'metrics["exactly_one_event_rate"] >= 0.95' in source
    assert 'metrics["containment_rate"] >= 0.85' in source
    assert 'metrics["premature_cut_rate"] <= 0.15' in source
    assert 'metrics["severe_cut_rate"] <= 0.10' in source
    assert 'metrics["context_reduction_fraction"]["mean"] >= 0.25' in source
    assert p8.search_document()["selection_population"] == "CAL_ONLY"
