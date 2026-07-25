"""Feature 12 tests — confirmation policy: calibration, evidence, commit gates, metrics.
Pure numpy — the correctness-critical logic runs without TF."""

from __future__ import annotations

import numpy as np
import pytest

from eval.confirm import (
    calibrated_logp,
    commit,
    confirmation_metrics,
    frame_evidence_summary,
)


def test_calibrated_logp_is_normalized() -> None:
    probs = np.array([[[0.7, 0.2, 0.1]]], np.float32)
    logp = calibrated_logp(probs, temperature=1.0)
    assert np.allclose(np.exp(logp).sum(-1), 1.0, atol=1e-5)
    assert logp.argmax(-1)[0, 0] == 0  # temperature keeps the ranking


def test_evidence_summary_tracks_leader_and_margin() -> None:
    # one clip, 2 frames, class 1 dominant -> A1 leader = class 1, positive margin
    pf = np.zeros((1, 2, 3), np.float32)
    pf[0, :, 1] = 0.9
    pf[0, :, 0] = 0.05
    pf[0, :, 2] = 0.05
    top1, a1, a2 = frame_evidence_summary(pf, temperature=1.0)
    assert np.all(top1 == 1)
    assert np.all(a1 > a2)  # leader ahead of runner-up


def test_commit_fires_when_gates_pass() -> None:
    # leader class 1, strong evidence + margin, stable -> commit early
    top1 = np.array([[1, 1, 1, 1]], np.int32)
    a1 = np.array([[-3.0, -1.0, -0.5, -0.4]], np.float32)
    a2 = np.array([[-3.5, -2.0, -2.0, -2.0]], np.float32)
    committed, frame = commit(top1, a1, a2, np.array([4]), theta_conf=-1.0, theta_margin=0.5, k=2)
    assert committed[0] == 1 and frame[0] == 1  # first frame all gates hold


def test_commit_drops_when_never_confident() -> None:
    top1 = np.array([[0, 1, 0, 1]], np.int32)  # unstable
    a1 = np.array([[-3.0, -3.0, -3.0, -3.0]], np.float32)  # weak evidence
    a2 = np.array([[-3.1, -3.1, -3.1, -3.1]], np.float32)  # tiny margin
    committed, frame = commit(top1, a1, a2, np.array([4]), theta_conf=-1.0, theta_margin=0.5, k=2)
    assert committed[0] == -1 and frame[0] == -1  # dropped


def test_margin_gate_blocks_low_confidence() -> None:
    top1 = np.array([[1, 1, 1]], np.int32)
    a1 = np.array([[-0.5, -0.5, -0.5]], np.float32)  # strong evidence
    a2 = np.array([[-0.6, -0.6, -0.6]], np.float32)  # but margin only 0.1 < 0.5
    committed, _ = commit(top1, a1, a2, np.array([3]), theta_conf=-1.0, theta_margin=0.5, k=1)
    assert committed[0] == -1  # margin guard prevents a shaky commit


def test_metrics_including_correct_but_dropped() -> None:
    # 4 clips: committed=[1(correct), 2(wrong), -1(dropped), -1(dropped)]
    committed = np.array([1, 2, -1, -1], np.int32)
    frame = np.array([5, 3, -1, -1], np.int32)
    y = np.array([1, 1, 2, 3], np.int32)
    lengths = np.array([10, 10, 10, 10], np.int32)
    model_arg = np.array([1, 1, 2, 0], np.int32)  # model would get clips 0,1,2 right
    m = confirmation_metrics(committed, frame, y, lengths, model_arg)
    assert m["commit_rate"] == pytest.approx(0.5)
    assert m["correct_commit_rate"] == pytest.approx(0.25)  # 1 of 4
    assert m["false_commit_rate"] == pytest.approx(0.25)
    assert m["precision_when_committed"] == pytest.approx(0.5)  # 1 of 2 commits
    # clips 0,1,2 model-correct; clip 2 was dropped -> 1 of 3 correct-but-dropped
    assert m["correct_but_dropped"] == pytest.approx(1 / 3)
    assert m["mean_commit_latency_frac"] == pytest.approx(0.4)  # (5/10 + 3/10)/2
