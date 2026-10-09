"""Exact tiny CTC enumeration, repeat/blank separation and frozen greedy compatibility."""

import itertools
import math

import numpy as np
import pytest

from model.fingerspelling_emission import score_logits
from model.fingerspelling_prefix_beam import decode_beam, decode_greedy, prefix_search
from tools.fingerspelling.decoder_audit import group_report


def collapse(path: tuple[int, ...], blank: int) -> tuple[int, ...]:
    return tuple(x for i, x in enumerate(path) if x != blank and (i == 0 or x != path[i - 1]))


def test_alignment_marginal_matches_exhaustive() -> None:
    probabilities = np.array([[0.45, 0.25, 0.30], [0.40, 0.35, 0.25], [0.30, 0.40, 0.30]])
    totals = {}
    for path in itertools.product(range(3), repeat=3):
        labels = collapse(path, 2)
        totals[labels] = totals.get(labels, 0) + math.prod(
            probabilities[t, s] for t, s in enumerate(path)
        )
    expected = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    actual = prefix_search(np.log(probabilities), 2, 100)
    assert [p for p, _ in actual] == [p for p, _ in expected]
    np.testing.assert_allclose(
        [math.exp(s) for _, s in actual], [s for _, s in expected], atol=1e-14
    )


def peaked(tokens: list[int]) -> np.ndarray:
    values = np.full((len(tokens), 28), -30, np.float32)
    for i, token in enumerate(tokens):
        values[i, token] = 30
    return values


@pytest.mark.parametrize(
    "tokens,text", [([11, 11], "L"), ([11, 27, 11], "LL"), ([27, 27], ""), ([0, 26, 1], "A B")]
)
def test_repeat_blank_and_space(tokens: list[int], text: str) -> None:
    assert decode_beam(peaked(tokens), 0.5, 10, 5)[0]["prediction"] == text
    assert decode_greedy(peaked(tokens), 0.5) == text


def test_marginal_can_beat_best_alignment() -> None:
    probs = np.array([[0.4, 0.6], [0.4, 0.6]])
    # Greedy blank/blank => empty (mass .36); A has summed mass .64.
    assert prefix_search(np.log(probs), 1, 10)[0][0] == (0,)


def test_greedy_identical_to_existing_penalty_and_no_mutation() -> None:
    values = np.random.default_rng(71).normal(size=(37, 28)).astype(np.float32)
    original = values.copy()
    row = {
        "sample_id": "fixture",
        "signer_id": "fixture",
        "reference": "HELLO",
        "logits": values,
        "headroom": 20,
        "ctc_loss": 1.0,
    }
    expected = score_logits([row], 0.5, [10, 20])["predictions"][0]["prediction"]
    assert decode_greedy(values, 0.5) == expected
    decode_beam(values, 0.5, 10, 5)
    np.testing.assert_array_equal(values, original)


def test_empty_extreme_finite_and_deterministic() -> None:
    assert decode_beam(np.empty((0, 28), np.float32), 0.5, 10, 5) == [
        {"prediction": "", "log_ctc_mass_pruned": 0.0}
    ]
    values = peaked([0, 1, 27, 1]) * 100
    first = decode_beam(values, 0.5, 10, 5)
    assert first == decode_beam(values, 0.5, 10, 5)
    assert len({r["prediction"] for r in first}) == len(first)
    assert all(math.isfinite(r["log_ctc_mass_pruned"]) for r in first)
    assert [r["log_ctc_mass_pruned"] for r in first] == sorted(
        [r["log_ctc_mass_pruned"] for r in first], reverse=True
    )


@pytest.mark.parametrize(
    "values,penalty,width,paths",
    [
        (np.zeros((2, 27)), 0.5, 10, 5),
        (np.full((2, 28), np.nan), 0.5, 10, 5),
        (np.zeros((2, 28)), -1, 10, 5),
        (np.zeros((2, 28)), 0.5, 4, 5),
    ],
)
def test_invalid_input(values: np.ndarray, penalty: float, width: int, paths: int) -> None:
    with pytest.raises(ValueError):
        decode_beam(values, penalty, width, paths)


def test_oracle_is_separate_from_ranked_top1() -> None:
    rows = [
        {
            "sample_id": "a",
            "signer_id": "s",
            "reference": "A",
            "greedy": "B",
            "candidates": [{"prediction": x} for x in ["B", "C", "A"]],
        },
        {
            "sample_id": "b",
            "signer_id": "s",
            "reference": "LL",
            "greedy": "L",
            "candidates": [{"prediction": x} for x in ["L", "LL", "L L"]],
        },
    ]
    result = group_report(rows)
    assert result["beam_top1"]["cer"] == pytest.approx(2 / 3)
    assert result["beam_top1"]["exact_sequence_count"] == 0
    assert result["topn"]["3"]["exact_reference_inclusion_count"] == 2
    assert result["topn"]["3"]["oracle_best_cer"] == 0
    assert result["beam_top1"]["correct_predicted_precision"] == 0.5


def test_change_counts_include_neutral_different_strings() -> None:
    rows = [
        {
            "sample_id": str(i),
            "signer_id": "s",
            "reference": ref,
            "greedy": greedy,
            "candidates": [{"prediction": beam}],
        }
        for i, (ref, greedy, beam) in enumerate(
            [("AB", "AB", "AA"), ("CD", "E", "CD"), ("F", "G", "H")]
        )
    ]
    assert group_report(rows)["top1_changes"] == {
        "different_from_greedy": 3,
        "improved": 1,
        "regressed": 1,
        "neutral": 1,
    }
