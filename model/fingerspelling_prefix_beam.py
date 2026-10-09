"""Bounded, language-free CTC prefix search; never changes the existing decoder."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from model.fingerspelling_metrics import greedy_decode

BLANK = 27
VOCABULARY = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ ")
NEGATIVE_INFINITY = -math.inf


def adjusted_logits(logits: np.ndarray, blank_penalty: float) -> np.ndarray:
    """Match score_logits: copy float32 logits, subtract once at blank index 27."""
    values = np.array(logits, dtype=np.float32, copy=True)
    if values.ndim != 2 or values.shape[1] != BLANK + 1:
        raise ValueError("[fingerspelling/beam] Expected [T,28] logits")
    if not np.isfinite(values).all() or not math.isfinite(blank_penalty) or blank_penalty < 0:
        raise ValueError("[fingerspelling/beam] Finite logits and nonnegative penalty required")
    values[:, BLANK] -= np.float32(blank_penalty)
    if not np.isfinite(values).all():
        raise ValueError("[fingerspelling/beam] Penalty overflow")
    return values


def decode_greedy(logits: np.ndarray, blank_penalty: float) -> str:
    return greedy_decode(np.argmax(adjusted_logits(logits, blank_penalty), axis=1).tolist())


def log_add(a: float, b: float) -> float:
    if a == NEGATIVE_INFINITY:
        return b
    if b == NEGATIVE_INFINITY:
        return a
    high, low = (a, b) if a >= b else (b, a)
    return high + math.log1p(math.exp(low - high))


def prefix_search(
    log_probs: np.ndarray, blank: int, beam_width: int
) -> list[tuple[tuple[int, ...], float]]:
    """Track separate blank/nonblank-ending alignment masses per label prefix.

    Prune label prefixes only after summing all symbol expansions for a timestep.
    No token pruning, length normalization, insertion bonus or transcript input.
    Returned mass is approximate when prefix pruning has removed alignments.
    """
    beams: dict[tuple[int, ...], tuple[float, float]] = {(): (0.0, NEGATIVE_INFINITY)}
    for frame in log_probs.tolist():
        next_beams: dict[tuple[int, ...], list[float]] = {}
        for prefix, (p_blank, p_nonblank) in beams.items():
            total = log_add(p_blank, p_nonblank)
            same = next_beams.setdefault(prefix, [NEGATIVE_INFINITY, NEGATIVE_INFINITY])
            same[0] = log_add(same[0], total + frame[blank])
            for symbol, probability in enumerate(frame):
                if symbol == blank:
                    continue
                if prefix and symbol == prefix[-1]:
                    # Same repeated nonblank continues the existing label. A new
                    # identical label can only extend an alignment ending blank.
                    same[1] = log_add(same[1], p_nonblank + probability)
                    extension_mass = p_blank + probability
                else:
                    extension_mass = total + probability
                if extension_mass == NEGATIVE_INFINITY:
                    continue
                extended = next_beams.setdefault(
                    (*prefix, symbol), [NEGATIVE_INFINITY, NEGATIVE_INFINITY]
                )
                extended[1] = log_add(extended[1], extension_mass)
        ranked = sorted(next_beams.items(), key=lambda item: (-log_add(*item[1]), item[0]))[
            :beam_width
        ]
        beams = {prefix: (mass[0], mass[1]) for prefix, mass in ranked}
    return sorted(
        ((prefix, log_add(*mass)) for prefix, mass in beams.items()),
        key=lambda item: (-item[1], item[0]),
    )


def decode_beam(
    logits: np.ndarray, blank_penalty: float, beam_width: int, top_paths: int
) -> list[dict[str, Any]]:
    if not 1 <= top_paths <= beam_width:
        raise ValueError("[fingerspelling/beam] Require 1 <= top_paths <= beam_width")
    values = adjusted_logits(logits, blank_penalty).astype(np.float64)
    if len(values):
        values -= values.max(axis=1, keepdims=True)
        values -= np.log(np.exp(values).sum(axis=1, keepdims=True))
    return [
        {
            "prediction": "".join(VOCABULARY[i] for i in prefix),
            "log_ctc_mass_pruned": score,
        }
        for prefix, score in prefix_search(values, BLANK, beam_width)[:top_paths]
    ]
