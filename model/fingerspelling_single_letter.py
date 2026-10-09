"""Exact one-letter CTC grammar; frozen logits, no learned letter classifier."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from model.fingerspelling_prefix_beam import BLANK, adjusted_logits, log_add

VERSION = "apphear.fingerspelling.single_letter_ctc.v1"
BLANK_PENALTY = 0.5


@dataclass(frozen=True)
class SingleLetterResult:
    text: str
    best_letter: str
    letter_log_masses: tuple[float, ...]
    empty_log_mass: float
    space_log_mass: float


def decode_single_letter(logits: np.ndarray, blank_penalty: float = 0.5) -> SingleLetterResult:
    """Sum exact CTC paths for each singleton letter and the empty sequence.

    Alphabet A–Z is a task constraint, not a lexicon. SPACE and other-letter
    probabilities remain in the log-softmax denominator. Empty or singleton
    SPACE wins ties and requests Retry rather than forcing an arbitrary letter.
    The result is not a calibrated probability that a signer showed the letter.
    Input must be unadjusted [T,28] logits; subtract blank penalty exactly once.
    """
    if blank_penalty != BLANK_PENALTY:
        raise ValueError("[fingerspelling/single-letter] Frozen blank penalty must remain 0.5")
    values = adjusted_logits(logits, blank_penalty).astype(np.float64)
    if len(values):
        values -= values.max(axis=1, keepdims=True)
        values -= np.log(np.exp(values).sum(axis=1, keepdims=True))
    scores = []
    for symbol in range(27):
        before, letter, after = 0.0, -math.inf, -math.inf
        for row in values:
            before, letter, after = (
                before + float(row[BLANK]),
                log_add(before, letter) + float(row[symbol]),
                log_add(letter, after) + float(row[BLANK]),
            )
        scores.append(log_add(letter, after))
    best = max(range(26), key=lambda symbol: scores[symbol])
    empty = float(values[:, BLANK].sum())
    best_letter = chr(ord("A") + best)
    return SingleLetterResult(
        text=best_letter if scores[best] > max(empty, scores[26]) else "",
        best_letter=best_letter,
        letter_log_masses=tuple(scores[:26]),
        empty_log_mass=empty,
        space_log_mass=scores[26],
    )
