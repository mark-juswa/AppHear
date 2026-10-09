"""Causal canonical hand identity, missingness and new-contract safety checks."""

from __future__ import annotations

import copy
import json
from typing import Any

import numpy as np
import pytest

from pipeline.fingerspelling.adapter import subset
from pipeline.fingerspelling.adapter_v2 import WIDTH, column_names, derive
from pipeline.fingerspelling.temporal_views import selected_indices
from pipeline.perception_vnext.recognition_schema import RAW_SCHEMA, RawSequence


def raw() -> RawSequence:
    n = 8
    xy = np.zeros((n, 2, 21, 2), np.float32)
    xy[..., 0] = np.arange(21) * 2 + 50
    xy[..., 1] = np.arange(21) + 100
    xy += np.arange(n, dtype=np.float32)[:, None, None, None]
    return RawSequence(
        metadata={"schema": RAW_SCHEMA, "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB"},
        frame_index=np.arange(n, dtype=np.int32),
        timestamp_ms=np.arange(n) * 100.0,
        source_size=np.tile([400, 400], (n, 1)).astype(np.int32),
        hand_xy=xy,
        hand_joint_valid=np.ones((n, 2, 21), bool),
        hand_proposal_support=np.full((n, 2, 21), 0.8, np.float32),
        hand_presence=np.ones((n, 2), np.float32),
        hand_observed=np.ones((n, 2), bool),
        hand_proposal_present=np.ones((n, 2), bool),
        hand_roi_center_side=np.tile([60, 110, 100], (n, 2, 1)).astype(np.float32),
        hand_handedness_diagnostic=np.zeros((n, 2), np.float32),
        body_xy=np.full((n, 8, 2), np.nan, np.float32),
        body_support=np.full((n, 8), np.nan, np.float32),
        body_valid=np.zeros((n, 8), bool),
        body_available=np.zeros(n, bool),
    )


def hide(r: RawSequence, i: Any, s: Any) -> None:
    r.hand_observed[i, s] = False
    r.hand_joint_valid[i, s] = False
    r.hand_xy[i, s] = np.nan


def test_slot_switch_equivalent_geometry_and_motion() -> None:
    r = raw()
    hide(r, slice(None), 1)
    reference, _ = derive(r)
    switched = raw()
    hide(switched, slice(0, 3), 1)
    hide(switched, slice(3, None), 0)
    actual, audit = derive(switched)
    assert audit["primary_slot"].tolist() == [0, 0, 0, 1, 1, 1, 1, 1]
    np.testing.assert_array_equal(actual, reference)
    assert actual[3, 182] == 1  # geometry motion crosses slot, physical association preserved


def test_duplicate_geometry_not_repeated_secondary_context() -> None:
    f, a = derive(raw())
    assert f.shape == (8, WIDTH) and len(column_names()) == WIDTH
    assert a["canonical_states"][:, 4].all()
    assert not f[:, 232:240].any()
    assert "primary.joint20.source_x" in column_names()
    assert all("slot" not in name for name in column_names())


def test_slot_permutation_and_transcript_independence() -> None:
    r = raw()
    r.hand_xy[:, 1] += 150
    r.hand_roi_center_side[:, 1, :2] += 150
    f, _ = derive(r)
    permuted = copy.deepcopy(r)
    for name in [
        "hand_xy",
        "hand_joint_valid",
        "hand_proposal_support",
        "hand_presence",
        "hand_observed",
        "hand_proposal_present",
        "hand_roi_center_side",
    ]:
        getattr(permuted, name)[:] = getattr(r, name)[:, ::-1]
    permuted.metadata["transcript"] = "ZZZZ"
    permuted.metadata["signer_id"] = "unknown"
    permuted.hand_handedness_diagnostic[:] = np.nan
    np.testing.assert_array_equal(f, derive(permuted)[0])


def test_causal_prefix_and_determinism() -> None:
    r = raw()
    f, _ = derive(r)
    np.testing.assert_array_equal(f, derive(r)[0])
    np.testing.assert_array_equal(f[:4], derive(subset(r, np.arange(4, dtype=np.int32)))[0])
    r.hand_xy[4:] += 100
    r.hand_presence[4:] = 0
    np.testing.assert_array_equal(f[:4], derive(r)[0][:4])


def test_equal_quality_and_wrist_tie_is_slot_independent() -> None:
    r = raw()
    r.hand_xy[:, 1, 4, 0] += 12
    expected, _ = derive(r)
    other = copy.deepcopy(r)
    other.hand_xy[:] = r.hand_xy[:, ::-1]
    np.testing.assert_array_equal(expected, derive(other)[0])


def test_missing_frames_never_fill_and_no_motion_across_gap() -> None:
    r = raw()
    hide(r, 2, slice(None))
    f, a = derive(r)
    assert a["primary_slot"][2] == -1 and not f[2, 2:183].any()
    assert not f[2, 224:255].any() and f[2, 1] == 1
    assert f[3, 182] == 0 and not f[3, 240:].any()
    assert f[3, 226] == 1  # association memory allowed, no landmark fill/motion across missing


def test_distinct_secondary_and_ambiguity_explicit() -> None:
    r = raw()
    r.hand_xy[:, 1] += 150
    r.hand_roi_center_side[:, 1, :2] += 150
    f, a = derive(r)
    assert a["secondary_slot"].tolist() == [1] * 8
    assert f[:, 229].all() and f[0, 227] == 1
    assert f[:, 239].all() and f[:, 238].all()
    assert not f[:, 228].any()


def test_partial_invalid_wrist_and_insufficient_candidate() -> None:
    r = raw()
    hide(r, slice(None), 1)
    r.hand_joint_valid[1, 0, 7] = False
    r.hand_xy[1, 0, 7] = np.nan
    r.hand_joint_valid[2, 0, 0] = False
    r.hand_xy[2, 0, 0] = np.nan
    f, a = derive(r)
    assert f[1, column_names().index("primary.joint7.source_valid")] == 0
    assert a["primary_slot"][2] == -1
    assert np.isfinite(f).all()


def test_long_gap_resolution_change_and_reacquisition_suppress_motion() -> None:
    for mode in ["gap", "resolution", "distance"]:
        r = raw()
        hide(r, slice(None), 1)
        if mode == "gap":
            r.timestamp_ms[3:] += 2000
        elif mode == "resolution":
            r.source_size[3:] += 1
        else:
            r.hand_xy[3:] += 200
        f, _ = derive(r)
        assert f[3, 230] == 1 and f[3, 182] == 0 and not f[3, 240:].any()


def test_sparse_recompute_canonical_motion_not_dense_slice() -> None:
    r = raw()
    hide(r, slice(None), 1)
    p = {"phone_hz": 6.231166, "intermediate_hz": 12}
    dense, _ = derive(r)
    idx = selected_indices(r, "phone", p)
    sparse, _ = derive(subset(r, idx))
    assert sparse[1, 0] == np.float32(0.2) and dense[idx[1], 0] == np.float32(0.1)
    assert sparse[1, 180] == pytest.approx(dense[idx[1], 180] * 2)


def test_bad_schema_and_chronology_refused() -> None:
    r = raw()
    r.metadata["schema"] = "v-other"
    with pytest.raises(ValueError):
        derive(r)
    r.metadata["schema"] = RAW_SCHEMA
    r.timestamp_ms[2] = r.timestamp_ms[1]
    with pytest.raises(ValueError):
        derive(r)


def test_v2_receipt_rejects_contract_role_and_lineage_mutation() -> None:
    from pipeline.fingerspelling.package_v2 import DEFAULT, check, parents

    originals = parents()
    original = originals[0]
    path = DEFAULT / "features" / f"{original['sample_id']}.receipt.json"
    assert path.exists(), "Bounded preparation must precede this real-lineage check"
    receipt = json.loads(path.read_text())
    check(receipt, original, recompute=True)
    for key, value in [
        ("schema_version", "wrong-schema"),
        ("split_role", "DEV"),
        ("official_signer_id", "another-human"),
        ("raw_sha256", "0" * 64),
        ("features_sha256", "0" * 64),
        ("parent_receipt_sha256", "0" * 64),
        ("package_implementation_sha256", "0" * 64),
    ]:
        changed = copy.deepcopy(receipt)
        changed[key] = value
        with pytest.raises(ValueError):
            check(changed, original)
    changed = copy.deepcopy(receipt)
    changed["adapter"]["feature_width"] = 405
    with pytest.raises(ValueError):
        check(changed, original)


def test_v2_cache_preserves_lengths_targets_and_padding_masks() -> None:
    from model.fingerspelling_v2_execution import Cache
    from pipeline.fingerspelling.package_v2 import DEFAULT, policy

    rows = [
        json.loads(p.read_text()) for p in sorted((DEFAULT / "features").glob("*.receipt.json"))[:2]
    ]
    assert len(rows) == 2
    cache = Cache(policy())
    tensors = cache.tensors(rows, ["native", "phone"])
    x, mask, targets, lengths, target_lengths = tensors
    assert x.shape[2] == 255 and targets.shape[0] == 2
    for i, view in enumerate(["native", "phone"]):
        original, target = cache.load(rows[i], view)
        assert not original.flags.writeable and not target.flags.writeable
        assert lengths[i] == len(original) and target_lengths[i] == len(target)
        np.testing.assert_array_equal(x[i, : lengths[i]], original)
        np.testing.assert_array_equal(targets[i, : target_lengths[i]], target)
        assert mask[i, : lengths[i]].all()
        assert not mask[i, lengths[i] :].any() and not x[i, lengths[i] :].any()
