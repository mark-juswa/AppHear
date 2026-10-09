"""Exact grammar diagnostics, not isolated-letter accuracy claims."""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from model.fingerspelling_prefix_beam import adjusted_logits, decode_greedy
from model.fingerspelling_single_letter import decode_single_letter


def peaked(tokens: list[int]) -> np.ndarray:
    values = np.full((len(tokens), 28), -30, dtype=np.float32)
    for frame, symbol in enumerate(tokens):
        values[frame, symbol] = 30
    return values


@pytest.mark.parametrize("timesteps", [1, 2, 3])
def test_matches_exhaustive_ctc_paths(timesteps: int) -> None:
    values = np.random.default_rng(41 + timesteps).normal(size=(timesteps, 28)).astype(np.float32)
    adjusted = adjusted_logits(values, 0.5).astype(np.float64)
    adjusted -= adjusted.max(axis=1, keepdims=True)
    probabilities = np.exp(adjusted)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    mass = np.zeros(26)
    empty = 0.0
    for path in itertools.product(range(28), repeat=timesteps):
        collapsed = [v for i, v in enumerate(path) if (i == 0 or v != path[i - 1]) and v != 27]
        probability = math.prod(probabilities[i, v] for i, v in enumerate(path))
        if not collapsed:
            empty += probability
        elif len(collapsed) == 1 and collapsed[0] < 26:
            mass[collapsed[0]] += probability
    result = decode_single_letter(values)
    np.testing.assert_allclose(np.exp(result.letter_log_masses), mass, rtol=1e-12)
    assert math.exp(result.empty_log_mass) == pytest.approx(empty, rel=1e-12)


@pytest.mark.parametrize("letter", range(26))
def test_all_letters_and_blank_edges(letter: int) -> None:
    assert decode_single_letter(peaked([27, letter, letter, 27])).text == chr(65 + letter)


def test_repeated_separate_captures_are_not_word_duplicate_handling() -> None:
    assert decode_single_letter(peaked([11, 27, 11])).text == "L"
    assert decode_greedy(peaked([11, 27, 11]), 0.5) == "LL"
    # Score contains only paths collapsing to ONE L; it cannot absorb both peaks.
    single = decode_single_letter(peaked([11, 11, 11]))
    split = decode_single_letter(peaked([11, 27, 11]))
    assert single.letter_log_masses[11] > split.letter_log_masses[11] + 40


@pytest.mark.parametrize("values", [peaked([27] * 10), peaked([26] * 4), peaked([])])
def test_blank_space_empty_do_not_force_letter(values: np.ndarray) -> None:
    assert decode_single_letter(values).text == ""


def test_penalty_once_tie_stable_and_no_input_mutation() -> None:
    values = np.full((1, 28), -30, dtype=np.float32)
    values[0, 0] = values[0, 1] = 0
    values[0, 27] = 0.5
    before = values.copy()
    result = decode_single_letter(values)
    assert result.best_letter == "A"
    assert result.text == ""  # blank wins exact tie after one adjustment
    np.testing.assert_array_equal(values, before)


def test_strong_but_wrong_input_stays_wrong_no_accuracy_invention() -> None:
    assert decode_single_letter(peaked([18] * 12)).text == "S"


def test_long_extreme_scores_finite() -> None:
    values = np.zeros((512, 28), np.float32)
    values[:, 12] = 10000
    result = decode_single_letter(values)
    assert result.text == "M"
    assert np.isfinite(result.letter_log_masses).all()


@pytest.mark.parametrize("values", [np.zeros((4, 27)), np.full((1, 28), np.nan)])
def test_reject_invalid_shape_or_numbers(values: np.ndarray) -> None:
    with pytest.raises(ValueError):
        decode_single_letter(values)


def test_frozen_penalty() -> None:
    with pytest.raises(ValueError, match="Frozen blank penalty"):
        decode_single_letter(peaked([0]), 0.0)
