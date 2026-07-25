"""Causal online-param estimator tests: convergence to the offline params by span end, mirror-flip
summary, and the recognition-gate metric math. Pure numpy (no TF)."""

from __future__ import annotations

import numpy as np
import pytest

from eval.causal_skew import dominance_signer_breakdown, gate_metrics
from pipeline.normalize.causal import (
    CausalConfig,
    MirrorStabilizer,
    mirror_flip_summary,
    normalize_clip_causal,
)
from pipeline.normalize.transforms import NormParams, normalize_clip

_CCFG = CausalConfig(mirror_decisive_margin=0.30, mirror_min_abs_diff=0.15, mirror_confirm_k=4)


class _Cfg:
    n1_scale = True
    n2_roll = True
    n3_handedness = True
    handedness_epsilon = 0.1


def _synthetic_clip(t: int = 30, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """A plausible moving-signer clip: two shoulders + wrists with motion, no NaNs."""
    rng = np.random.default_rng(seed)
    pose = np.zeros((t, 33, 4), np.float32)
    # shoulders (11=L,12=R), wrists (15=L,16=R), hips (23=L,24=R) — fixed body, moving right wrist
    pose[:, 11, :2] = [0.4, 0.3]
    pose[:, 12, :2] = [0.6, 0.3]
    pose[:, 23, :2] = [0.42, 0.7]
    pose[:, 24, :2] = [0.58, 0.7]
    pose[:, 15, :2] = [0.4, 0.5]
    pose[:, 16, 0] = 0.6 + 0.1 * np.sin(np.linspace(0, 3, t))  # right wrist moves most
    pose[:, 16, 1] = 0.5
    pose[:, :, 3] = 1.0  # visibility
    hands = np.full((t, 2, 21, 3), np.nan, np.float32)
    hands[:, 1] = pose[:, 16, None, :3] + rng.standard_normal((t, 21, 3)) * 0.01  # right hand
    return hands, pose


def test_causal_converges_to_offline_by_span_end() -> None:
    hands, pose = _synthetic_clip()
    cfg = _Cfg()
    _, _, offline = normalize_clip(hands, pose, 0, pose.shape[0] - 1, cfg)  # type: ignore[arg-type]
    _, _, per_frame = normalize_clip_causal(
        hands, pose, 0, pose.shape[0] - 1, cfg, _CCFG  # type: ignore[arg-type]
    )
    last = per_frame[-1]
    # the final causal frame uses the full window == the offline params
    assert last.scale == pytest.approx(offline.scale, rel=1e-5)
    assert last.roll_angle == pytest.approx(offline.roll_angle, abs=1e-5)
    assert last.mirrored == offline.mirrored


def test_causal_last_frame_features_match_offline_tail() -> None:
    hands, pose = _synthetic_clip()
    cfg = _Cfg()
    h_off, p_off, _ = normalize_clip(hands, pose, 0, pose.shape[0] - 1, cfg)  # type: ignore[arg-type]
    h_c, p_c, _ = normalize_clip_causal(
        hands, pose, 0, pose.shape[0] - 1, cfg, _CCFG  # type: ignore[arg-type]
    )
    # by the final frame the causal params equal the offline ones, so that frame should match
    # (center is per-frame either way; only the span-median fallback path could differ, absent here)
    assert np.allclose(p_c[-1], p_off[-1], atol=1e-4)
    assert np.allclose(np.nan_to_num(h_c[-1]), np.nan_to_num(h_off[-1]), atol=1e-4)


def test_mirror_flip_summary_counts_changes() -> None:
    def p(m: bool) -> NormParams:
        return NormParams(scale=1.0, roll_angle=0.0, dominant="Right", mirrored=m)

    # stable: no flips
    assert mirror_flip_summary([p(False), p(False), p(False)]) == (0, -1)
    # one flip at index 2
    assert mirror_flip_summary([p(False), p(False), p(True), p(True)]) == (1, 2)
    # two flips, last at index 3
    assert mirror_flip_summary([p(False), p(True), p(False), p(True)]) == (3, 3)


def test_mirror_stabilizer_freezes_on_decisive_left_then_never_flips() -> None:
    # decisive-left (ratio>=0.3, abs>=0.15) held for confirm_k=2, then a later right-dominant
    # reading must be IGNORED (no post-commit flip). (cum_l, cum_r) per frame:
    s = MirrorStabilizer(decisive_margin=0.30, min_abs=0.15, confirm_k=2)
    out = [s.update(cl, cr) for cl, cr in [(0.1, 0.1), (0.5, 0.1), (0.6, 0.1), (0.1, 0.9)]]
    # frame0 not decisive; frames 1&2 decisive -> freeze at frame2; frame3 (right-lead) ignored
    assert out == [False, False, True, True]


def test_mirror_stabilizer_abs_guard_blocks_early_tiny_motion() -> None:
    # high RATIO but tiny ABSOLUTE motion (a twitch): abs guard must reject it -> no mirror
    s = MirrorStabilizer(decisive_margin=0.30, min_abs=0.15, confirm_k=2)
    out = [s.update(cl, cr) for cl, cr in [(0.05, 0.0), (0.10, 0.0), (0.12, 0.0)]]
    assert out == [False, False, False]  # ratio=1.0 but abs<0.15 -> never decisive


def test_mirror_stabilizer_stays_no_mirror_for_right_dominant() -> None:
    # right-dominant clip: left never leads -> never mirrors
    s = MirrorStabilizer(decisive_margin=0.30, min_abs=0.15, confirm_k=2)
    out = [s.update(cl, cr) for cl, cr in [(0.1, 0.5), (0.2, 1.0), (0.3, 1.5)]]
    assert out == [False, False, False]


def test_gate_metrics_agreement_and_late_flip() -> None:
    # 3 clips. full commits all correctly at frames [2,2,2]; causal matches clips 0,1 but flips
    # clip 2 to a different class, and clip 2's mirror flips AT the commit frame (late).
    committed_f = np.array([5, 6, 7])
    frame_f = np.array([2, 2, 2])
    arg_f = np.array([5, 6, 7])
    committed_c = np.array([5, 6, 9])  # clip2 disagrees
    frame_c = np.array([2, 2, 3])
    arg_c = np.array([5, 6, 9])
    y = np.array([5, 6, 7])
    last_flip = np.array([-1, 0, 2])  # clip2 flips at frame 2 == commit frame -> late
    m = gate_metrics(committed_c, frame_c, arg_c, committed_f, frame_f, arg_f, y, last_flip)
    # the DEPLOYMENT metric: full commits all 3 correctly (acc 1.0); causal commits clip2 wrong
    # (9 != 7) so causal commit-accuracy = 2/3; the delta is what the gate judges.
    assert m["full_commit_accuracy"] == pytest.approx(1.0)
    assert m["causal_commit_accuracy"] == pytest.approx(2 / 3)
    assert m["commit_accuracy_delta"] == pytest.approx(1 / 3)
    assert m["commit_agreement"] == pytest.approx(2 / 3)  # 2 of 3 committed clips agree (diag)
    assert m["late_mirror_flip_rate"] == pytest.approx(1 / 3)  # clip2 flip at/after its commit


def test_dominance_breakdown_isolates_left_dominant_cost() -> None:
    # 4 clips, all committed. Full gets all right; causal misses clip 3 (a left-dominant one).
    committed_f = np.array([1, 2, 3, 4])
    committed_c = np.array([1, 2, 3, 9])  # clip3 wrong on causal
    y = np.array([1, 2, 3, 4])
    offline_mirror = np.array([False, False, True, True])  # clips 2,3 are left-dominant
    pids = np.array(["A", "A", "B", "B"])
    bd = dominance_signer_breakdown(
        committed_c, committed_f, y, offline_mirror, pids, min_commits=1
    )
    left = bd["by_dominance"]["left_dominant_mirrored"]
    right = bd["by_dominance"]["right_or_symmetric"]
    assert right["delta"] == pytest.approx(0.0)  # right/symmetric clips unaffected
    assert left["full"] == pytest.approx(1.0)
    assert left["causal"] == pytest.approx(0.5)  # 1 of 2 left-dominant now wrong
    assert left["delta"] == pytest.approx(0.5)  # the cost is concentrated here
    assert bd["worst_signer"]["id"] == "B"  # signer B (the left-dominant one) bears it
