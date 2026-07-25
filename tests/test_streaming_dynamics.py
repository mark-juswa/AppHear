"""Feature 13 tests — within-sign emission dynamics: TTFC, TTSC, flicker, settled-fraction,
confidence-trajectory deciles, and real-frame masking. Pure numpy (no TF)."""

from __future__ import annotations

import numpy as np
import pytest

from eval.streaming_dynamics import clip_dynamics, per_signer, summarize

C = 3


def _pf(preds: list[int], t: int, conf: float = 0.9) -> np.ndarray:
    """(1,t,C) per-frame probs whose argmax at frame i is preds[i]; frames past len(preds) are
    filler (should be ignored via `length`)."""
    pf = np.full((1, t, C), (1 - conf) / (C - 1), np.float32)
    for i, p in enumerate(preds):
        pf[0, i] = (1 - conf) / (C - 1)
        pf[0, i, p] = conf
    return pf


def _one(preds: list[int], y: int, length: int, t: int | None = None) -> dict:
    t = t or len(preds)
    return clip_dynamics(_pf(preds, t), np.array([y]), np.array([length]), 1.0, 10)


def test_correct_from_onset() -> None:
    d = _one([1, 1, 1], y=1, length=3)
    assert d["ttfc"][0] == 0 and d["ttsc"][0] == 0
    assert d["switches"][0] == 0
    assert d["settled"][0] == pytest.approx(1.0)
    assert d["ever_correct"][0]


def test_correct_late_then_stable() -> None:
    d = _one([0, 0, 1, 1], y=1, length=4)  # wrong,wrong,right,right
    assert d["ttfc"][0] == 2
    assert d["ttsc"][0] == 2  # last wrong at idx1 -> settles at 2
    assert d["switches"][0] == 1  # 0->0,0->1,1->1
    assert d["settled"][0] == pytest.approx(0.5)  # final=1 appears 2/4


def test_flicker_never_settles() -> None:
    d = _one([1, 0, 1, 0], y=1, length=4)  # right at 0,2 but last frame wrong
    assert d["ttfc"][0] == 0
    assert d["ttsc"][0] == -1  # never stays correct to the end
    assert d["ever_correct"][0]
    assert d["switches"][0] == 3


def test_never_correct() -> None:
    d = _one([0, 2, 0], y=1, length=3)
    assert d["ttfc"][0] == -1 and d["ttsc"][0] == -1
    assert not d["ever_correct"][0]


def test_length_masks_padding() -> None:
    # real frames [0,3) all wrong; padding frames 3,4 are "correct" but must be ignored
    d = _one([0, 0, 0, 1, 1], y=1, length=3, t=5)
    assert d["ttfc"][0] == -1  # padding correctness ignored
    assert d["switches"][0] == 0  # no switches within the 3 real frames


def test_confidence_trajectory_shape_and_range() -> None:
    d = _one([1] * 5, y=1, length=5)
    r = summarize(d, 10)
    traj = r["confidence_trajectory_deciles"]
    assert len(traj) == 10
    assert all(0.0 <= v <= 1.0 for v in traj)


def test_summarize_never_correct_frac() -> None:
    # two clips: one correct-from-onset, one never-correct
    d1 = _one([1, 1, 1], y=1, length=3)
    d2 = _one([0, 0, 0], y=1, length=3)
    merged = {k: np.concatenate([d1[k], d2[k]], axis=0) for k in d1}
    r = summarize(merged, 10)
    assert r["n_clips"] == 2
    assert r["never_correct_frac"] == pytest.approx(0.5)
    assert r["time_to_first_correct"]["n"] == 1  # only the ever-correct clip counts


def test_per_signer_grouping() -> None:
    d1 = _one([1, 1, 1], y=1, length=3)
    d2 = _one([0, 0, 0], y=1, length=3)
    merged = {k: np.concatenate([d1[k], d2[k]], axis=0) for k in d1}
    out = per_signer(merged, np.array(["P1", "P2"]))
    assert set(out) == {"P1", "P2"}
    assert out["P1"]["never_correct_frac"] == pytest.approx(0.0)
    assert out["P2"]["never_correct_frac"] == pytest.approx(1.0)
