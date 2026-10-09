"""Cadence, CTC fallback, emission and frozen-selection regression checks; no bulk training."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from model.fingerspelling_baseline2 import policy, safe_run, stopping_state
from model.fingerspelling_emission import balanced_score, calibrate, score_logits
from model.fingerspelling_temporal_execution import TemporalFeatureCache
from pipeline.fingerspelling.adapter import column_names, derive, subset
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.temporal_views import requested_view, selected_indices
from pipeline.perception_vnext.recognition_schema import RAW_SCHEMA, RawSequence


def raw() -> RawSequence:
    n = 10
    xy = np.zeros((n, 2, 21, 2), np.float32)
    xy[..., 0] = np.arange(21) * 2 + 50
    xy[..., 1] = np.arange(21) + 100
    xy[1] += 4
    return RawSequence(
        metadata={"schema": RAW_SCHEMA, "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB"},
        frame_index=np.arange(n, dtype=np.int32),
        timestamp_ms=np.arange(n) * 100.0,
        source_size=np.tile([200, 400], (n, 1)).astype(np.int32),
        hand_xy=xy,
        hand_proposal_support=np.full((n, 2, 21), 0.8, np.float32),
        hand_joint_valid=np.ones((n, 2, 21), bool),
        hand_presence=np.ones((n, 2), np.float32),
        hand_observed=np.ones((n, 2), bool),
        hand_proposal_present=np.ones((n, 2), bool),
        hand_roi_center_side=np.tile([50, 100, 80], (n, 2, 1)).astype(np.float32),
        hand_handedness_diagnostic=np.zeros((n, 2), np.float32),
        body_xy=np.full((n, 8, 2), np.nan, np.float32),
        body_support=np.full((n, 8), np.nan, np.float32),
        body_valid=np.zeros((n, 8), bool),
        body_available=np.zeros(n, bool),
    )


def logits(tokens: list[int], ref: str = "MM") -> list[dict[str, Any]]:
    values = np.full((len(tokens), 28), -5.0, np.float32)
    values[np.arange(len(tokens)), tokens] = 5
    return [
        {
            "sample_id": "one",
            "signer_id": "heldout",
            "reference": ref,
            "logits": values,
            "headroom": len(tokens) - 3,
            "ctc_loss": 1.0,
        }
    ]


def test_real_views_recompute_time_and_motion() -> None:
    p, _ = policy()
    r = raw()
    dense = derive(r)
    indices = selected_indices(r, "phone", p)
    assert indices.tolist() == [0, 2, 4, 6, 8]
    assert np.all(np.diff(indices) > 0)
    sparse = derive(subset(r, indices))
    assert sparse[1, 0] == np.float32(0.2)
    motion = column_names().index("slot0.wrist_dx")
    assert sparse[1, motion] == 0 and dense[2, motion] != 0
    np.testing.assert_array_equal(derive(subset(r, selected_indices(r, "native", p))), dense)


def test_missingness_partial_and_duplicate_slots_survive_selection() -> None:
    p, _ = policy()
    r = raw()
    r.hand_observed[2] = False
    r.hand_joint_valid[2] = False
    r.hand_xy[2] = np.nan
    r.hand_joint_valid[4, 0, 7] = False
    r.hand_xy[4, 0, 7] = np.nan
    selected = selected_indices(r, "phone", p)
    f = derive(subset(r, selected))
    assert np.isfinite(f).all() and not f[:, -1].any()
    names = column_names()
    assert f[1, names.index("slot0.joint0.source_valid")] == 0
    assert f[2, names.index("slot0.joint7.source_valid")] == 0
    assert f[2, names.index("slot0.motion_valid")] == 0
    np.testing.assert_array_equal(f[0, 2:183], f[0, 183:364])
    r2 = copy.deepcopy(r)
    r2.hand_xy[2] = 0
    np.testing.assert_array_equal(f, derive(subset(r2, selected)))


def test_schedule_deterministic_balanced_without_persistent_copies() -> None:
    p, _ = policy()
    for sid in ["clip1", "clip2", "clip3"]:
        views = [requested_view(sid, e, p) for e in range(3)]
        assert set(views) == set(p["temporal_views"])
        assert views == [requested_view(sid, e, p) for e in range(3)]
    with pytest.raises(ValueError):
        requested_view("clip", -1, p)


def test_temporal_order_and_unknown_view_rejected() -> None:
    p, _ = policy()
    r = raw()
    with pytest.raises(ValueError):
        selected_indices(r, "invented", p)
    r.timestamp_ms[3] = r.timestamp_ms[2]
    with pytest.raises(ValueError):
        selected_indices(r, "phone", p)


def test_fallback_uses_nearest_denser_and_never_discards_source() -> None:
    p, _ = policy()
    cache = TemporalFeatureCache(p)
    cache.registered.add("clip")
    for v, n in [("native", 10), ("intermediate", 5), ("phone", 2)]:
        cache.view_info[("clip", v)] = {"frames": n, "headroom": n - 3, "feasible": n >= 3}
    epoch = next(e for e in range(3) if requested_view("clip", e, p) == "phone")
    view, info = cache.choose({"sample_id": "clip"}, epoch)
    assert view == "intermediate" and info["fallback"] and info["headroom"] == 2
    for v in p["temporal_views"]:
        cache.view_info[("clip", v)]["feasible"] = False
    with pytest.raises(ValueError, match="source retained"):
        cache.choose({"sample_id": "clip"}, epoch)


def test_ctc_repeated_character_decode_and_blank_metrics() -> None:
    r = score_logits(logits([12, 12, 27, 12]), 0, [10, 20])
    assert r["metrics"]["exact_sequence_count"] == 1
    assert r["metrics"]["predicted_reference_ratio"] == 1
    assert r["emission"]["blank_argmax_fraction"] == 0.25
    blank = score_logits(logits([27, 27, 27]), 0, [10, 20])
    assert blank["metrics"]["empty_prediction_count"] == 1
    assert blank["metrics"]["deletion_rate"] == 1


def test_calibration_selects_smallest_successful_penalty_without_mutation() -> None:
    p, _ = policy()
    r = logits([27, 27, 27])
    r[0]["logits"][:, 27] = 1
    r[0]["logits"][[0, 2], 12] = 0.7
    original = r[0]["logits"].copy()
    result = calibrate({"native": r, "phone": r}, p, True)
    assert result["selected_penalty"] == 0.5
    np.testing.assert_array_equal(original, r[0]["logits"])
    assert calibrate({"native": r, "phone": r}, p, False)["selected_penalty"] == 0


def test_calibration_does_not_force_emissions_when_discrimination_poor() -> None:
    p, _ = policy()
    r = logits([27, 27, 27])
    r[0]["logits"][:, 27] = 1
    r[0]["logits"][:, 0] = 0.7
    result = calibrate({"native": r, "phone": r}, p, True)
    assert result["selected_penalty"] == 0  # substitutions replace deletions, no CER gain


def test_frozen_selection_retains_both_views_and_early_stop_state() -> None:
    assert balanced_score(
        {"native": {"metrics": {"cer": 0.4}}, "phone": {"metrics": {"cer": 0.8}}}
    ) == pytest.approx(0.6)
    p, _ = policy()
    state = stopping_state({}, 0.9, p)
    state = stopping_state(state, 0.899, p)
    assert state["non_improving_epochs"] == 1 and state["patience_anchor"] == 0.9
    state = stopping_state(state, 0.897, p)
    assert state["non_improving_epochs"] == 0


@pytest.mark.parametrize("name", ["fingerspelling_ctc_baseline_01", "fingerspelling_ctc_fast_01"])
def test_baseline1_run_refused(name: str) -> None:
    with pytest.raises(ValueError, match="read-only"):
        safe_run(REPO / "runs" / name)


def test_run_outside_runs_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        safe_run(tmp_path)
