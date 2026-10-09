"""Focused raw robustness/CTC/preservation checks, no corpus training."""

from __future__ import annotations

import copy

import numpy as np
import pytest

from model.fingerspelling_prefix_beam import decode_beam
from model.fingerspelling_sequence_v2_encoder import configuration, receptive_field
from model.fingerspelling_sequence_v2_execution import RobustTemporalCache
from pipeline.fingerspelling.adapter import column_names, derive
from pipeline.fingerspelling.evidence_robustness import seed_for, withdraw
from pipeline.fingerspelling.sequence_package import RECEIPT_SCHEMA
from tests.test_fingerspelling_baseline2 import raw


@pytest.mark.parametrize("profile", ["moderate", "heavy", "contiguous"])
def test_deterministic_consistent_withdrawal(profile: str) -> None:
    r, p = raw(), configuration()
    original = copy.deepcopy(r)
    a, info = withdraw(r, "train-one", 0, profile, p)
    b, again = withdraw(r, "train-one", 0, profile, p)
    assert info == again and info["withdrawn_slots"] <= info["withdrawal_budget"]
    assert info["withdrawn_slots"] > 0
    np.testing.assert_array_equal(a.hand_xy, b.hand_xy)
    np.testing.assert_array_equal(r.hand_xy, original.hand_xy)
    np.testing.assert_array_equal(r.hand_observed, original.hand_observed)
    np.testing.assert_array_equal(a.timestamp_ms, r.timestamp_ms)
    np.testing.assert_array_equal(a.frame_index, r.frame_index)
    np.testing.assert_array_equal(a.body_xy, r.body_xy)
    removed = r.hand_observed & ~a.hand_observed
    assert np.isnan(a.hand_xy[removed]).all() and not a.hand_joint_valid[removed].any()
    no_proposal = removed & ~a.hand_proposal_present
    assert np.isnan(a.hand_presence[no_proposal]).all()
    assert (a.hand_presence[removed & a.hand_proposal_present] == 0).all()
    np.testing.assert_array_equal(a.hand_xy[~removed], r.hand_xy[~removed])
    f = derive(a)
    assert f.shape == (10, 405) and np.isfinite(f).all()
    names = column_names()
    for slot in range(2):
        for i in np.flatnonzero(removed[:, slot]):
            assert f[i, names.index(f"slot{slot}.joint0.source_valid")] == 0
            assert f[i, names.index(f"slot{slot}.motion_valid")] == 0
            if i + 1 < len(f):
                assert f[i + 1, names.index(f"slot{slot}.motion_valid")] == 0


def test_no_evidence_invented_for_already_missing_slots() -> None:
    r = raw()
    r.hand_observed[:] = False
    r.hand_joint_valid[:] = False
    r.hand_xy[:] = np.nan
    a, info = withdraw(r, "no-hand", -1, "heavy", configuration())
    assert info["withdrawn_slots"] == info["withdrawal_budget"] == 0
    assert not a.hand_observed.any() and np.isfinite(derive(a)).all()


def test_distinct_seeds_and_unknown_policy_refused() -> None:
    assert seed_for(1, "a", 0, "moderate") != seed_for(1, "a", 1, "moderate")
    assert seed_for(1, "a", -1, "moderate") == seed_for(1, "a", -1, "moderate")
    with pytest.raises(ValueError, match="profile"):
        withdraw(raw(), "a", 0, "invented", configuration())


def test_four_regimes_and_ctc_denser_fallback() -> None:
    p = configuration()
    cache = RobustTemporalCache(p)
    rec = {
        "sample_id": "a",
        "split_role": "TRAIN",
        "ctc_min_timesteps": 3,
        "schema_version": RECEIPT_SCHEMA,
        "adapter": cache.adapter,
        "features_sha256": "synthetic",
    }
    cache.registered.add("a")
    for view, n in [("native", 10), ("intermediate", 5), ("phone", 2)]:
        x, y = np.zeros((n, 405), np.float32), np.array([12, 12], np.int32)
        cache.arrays[("a", view)] = x, y
        cache.view_info[("a", view)] = {"feasible": n >= 3, "frames": n}

    def augmented(rec, actual, profile, epoch):
        x, y = cache.load(rec, actual)
        return x, y, {"profile": profile}

    cache.augmented = augmented
    all_choices = [cache.training_array(rec, e)[2] for e in range(4)]
    assert {c["requested"] for c in all_choices} == set(p["train_regimes"])
    assert all(c["actual"] not in ("phone", "phone_robust") for c in all_choices)
    assert sum(c["fallback"] for c in all_choices) == 2
    with pytest.raises(ValueError, match="TRAIN"):
        cache.training_array({**rec, "split_role": "DEV"}, 0)
    for view in p["temporal_views"]:
        cache.view_info[("a", view)]["feasible"] = False
    with pytest.raises(ValueError, match="Native infeasible"):
        cache.training_array(rec, 0)


def test_output_ctc_contract_unchanged_repeats_space() -> None:
    p = configuration()
    assert receptive_field(p) == 1021 and p["temporal_stride"] == 1
    assert p["final_decoder"]["blank_penalty"] == 0.5
    x = np.full((5, 28), -20.0, np.float32)
    x[np.arange(5), [12, 27, 12, 26, 0]] = 20
    assert decode_beam(x, 0.5, 10, 1)[0]["prediction"] == "MM A"
