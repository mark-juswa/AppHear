"""Research decoder variants: BASELINE must equal production; split rules behave causally."""

from __future__ import annotations

from dataclasses import asdict

import numpy as np

from eval.runtime_diagnostics.event_separation import BASELINE, SplitConfig, SplitDecoder
from eval.runtime_diagnostics.phase8a_m2_frozen_sparse_dev_validation import CONFIG_01
from pipeline.perception_vnext.segmentation.streaming_decoder import (
    CausalStreamingSignEventDecoder,
)

STEP = 266.616


def run(decoder: CausalStreamingSignEventDecoder, states: list[int]) -> list[dict]:
    for i, s in enumerate(states):
        probs = [0.0, 0.0, 0.0]
        probs[s] = 1.0
        decoder.consume(i * STEP, probs, s)
    return [asdict(e) for e in decoder.events]


def test_baseline_variant_equals_production_decoder_on_random_streams() -> None:
    rng = np.random.default_rng(3)
    for _ in range(50):
        states = rng.choice([0, 1, 2], size=120, p=[0.5, 0.3, 0.2]).tolist()
        assert run(SplitDecoder(CONFIG_01, BASELINE), states) == run(
            CausalStreamingSignEventDecoder(CONFIG_01), states
        )


def test_reentry_emits_second_sign_that_production_ignores() -> None:
    # sign, two POST to confirm, one POST, then a second sign before the 400 ms re-arm completes
    states = [0, 1, 1, 1, 2, 2, 2, 1, 1, 1, 2, 2, 2, 0, 0, 0]
    assert len(run(CausalStreamingSignEventDecoder(CONFIG_01), states)) == 1
    split = SplitConfig("R", reentry=True, reentry_gap=1)
    events = run(SplitDecoder(CONFIG_01, split), states)
    assert len(events) == 2
    assert events[1]["logical_active_start_index"] == 7


def test_max_active_splits_long_run_at_weakest_observation() -> None:
    decoder = SplitDecoder(CONFIG_01, SplitConfig("M", max_active_ms=2000.0))
    active = [0.9] * 6 + [0.55] + [0.9] * 6
    for i, p in enumerate([0.0] + active + [0.0, 0.0, 0.0]):
        state = 1 if p > 0 else 2
        decoder.consume(
            i * STEP, [1 - p if state == 1 else 0.0, p, 0.0 if state == 1 else 1.0], state
        )
    assert decoder.split_counts["MAX_ACTIVE"] >= 1
    first = decoder.events[0]
    assert first.first_post_index == 7  # the 0.55 dip (index 7 = 1 lead + 6 strong)


def test_pre_exit_post_commits_a_valid_sign_that_ends_in_pre() -> None:
    # A valid ACTIVE run (3 observations) followed by PRE: production discards it at the next
    # observation (PRE gap reset < cadence); PRE_EXIT_POST confirms it like a POST exit.
    states = [0, 1, 1, 1, 0, 0, 0, 0]
    assert run(CausalStreamingSignEventDecoder(CONFIG_01), states) == []
    events = run(SplitDecoder(CONFIG_01, SplitConfig("P", pre_exit_post=True)), states)
    assert len(events) == 1
    assert (events[0]["logical_active_start_index"], events[0]["logical_active_end_index"]) == (
        1,
        3,
    )
    assert events[0]["first_post_index"] == 4


def test_pre_exit_post_keeps_discarding_a_single_active_blip() -> None:
    states = [0, 1, 0, 0, 0, 0]
    assert run(SplitDecoder(CONFIG_01, SplitConfig("P", pre_exit_post=True)), states) == []


def test_pre_exit_post_leaves_post_exits_unchanged() -> None:
    rng = np.random.default_rng(5)
    for _ in range(50):
        states = rng.choice([1, 2], size=80, p=[0.5, 0.5]).tolist()
        assert run(SplitDecoder(CONFIG_01, SplitConfig("P", pre_exit_post=True)), states) == run(
            CausalStreamingSignEventDecoder(CONFIG_01), states
        )


def test_reentry_2_counts_the_commit_observation_and_needs_one_more_non_active() -> None:
    # The commit observation (POST, index 5) is the first non-ACTIVE observation after the event.
    right_after = [0, 1, 1, 1, 2, 2, 1, 1, 1, 2, 2, 2, 0, 0, 0]  # ACTIVE at the next observation
    one_more = [0, 1, 1, 1, 2, 2, 2, 1, 1, 1, 2, 2, 2, 0, 0, 0]  # one more POST first
    r1 = SplitConfig("R1", reentry=True, reentry_gap=1)
    r2 = SplitConfig("R2", reentry=True, reentry_gap=2)
    assert len(run(CausalStreamingSignEventDecoder(CONFIG_01), one_more)) == 1
    assert len(run(SplitDecoder(CONFIG_01, r1), right_after)) == 2
    assert len(run(SplitDecoder(CONFIG_01, r2), right_after)) == 1
    assert len(run(SplitDecoder(CONFIG_01, r2), one_more)) == 2


def test_nonactive_peak_splits_when_post_mass_has_moved_to_pre() -> None:
    # Two signs separated by one end-of-sign observation (next ACTIVE lands on the confirmation
    # boundary) whose probability is split between PRE and POST.
    step = STEP
    rows = [
        ([0.9, 0.1, 0.0], 0),
        ([0.0, 1.0, 0.0], 1),
        ([0.0, 1.0, 0.0], 1),
        ([0.0, 1.0, 0.0], 1),
        ([0.45, 0.1, 0.45], 2),  # end evidence: P(POST) 0.45 < 0.7, but 1 - P(ACTIVE) = 0.9
        ([0.0, 1.0, 0.0], 1),
        ([0.0, 1.0, 0.0], 1),
        ([0.0, 1.0, 0.0], 1),
        ([0.0, 0.0, 1.0], 2),
        ([0.0, 0.0, 1.0], 2),
        ([0.0, 0.0, 1.0], 2),
    ]

    def events(split: SplitConfig) -> int:
        d = SplitDecoder(CONFIG_01, split)
        for i, (p, s) in enumerate(rows):
            d.consume(i * step, p, s)
        return len(d.events)

    post_gated = SplitConfig("CB", confirm_boundary=True, post_peak=0.7)
    nonactive_gated = SplitConfig("CBN", confirm_boundary=True, post_peak=0.7, nonactive_peak=True)
    assert events(post_gated) == 1
    assert events(nonactive_gated) == 2
