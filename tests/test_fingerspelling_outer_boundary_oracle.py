"""Oracle selection/alignment invariants; no model training or production dependencies."""

from __future__ import annotations

import copy

import numpy as np
import pytest

from model.fingerspelling_baseline2 import policy
from pipeline.fingerspelling.adapter import column_names, derive
from pipeline.fingerspelling.visual_quality import quality
from tests.test_fingerspelling_baseline2 import raw
from tools.fingerspelling.outer_boundary_oracle import paired, selected_input, window_indices
from tools.fingerspelling.outer_boundary_phase_control import phase_locked_indices


def metadata(start: float = 10.2, end: float = 10.7) -> dict[str, float]:
    return {
        "annotationStartTimeS": start,
        "annotationEndTimeS": end,
        "clipStartTimeS": 10.0,
        "clipEndTimeS": 10.9,
        "fullVideoFirstPtsTimeS": 0.082,
    }


def test_original_pts_cancels_and_closed_window_selects_real_frames() -> None:
    r = raw()
    indices, diagnostic = window_indices(r, metadata())
    # Decimal time subtraction can place a mathematical endpoint a tiny fraction before a frame;
    # actual source times are used exactly, never fuzzy endpoint padding.
    expected = np.flatnonzero(
        (r.timestamp_ms >= (10.2 - 10) * 1000) & (r.timestamp_ms <= (10.7 - 10) * 1000)
    )
    np.testing.assert_array_equal(indices, expected)
    changed = metadata()
    changed["fullVideoFirstPtsTimeS"] = 123
    np.testing.assert_array_equal(window_indices(r, changed)[0], indices)
    assert diagnostic["before_removed"] + diagnostic["after_removed"] + len(indices) == 10


@pytest.mark.parametrize(
    "start,end", [(10.7, 10.2), (9.9, 10.5), (10.2, 11.0), (float("nan"), 10.7)]
)
def test_bad_windows_are_reportable_not_clamped(start: float, end: float) -> None:
    with pytest.raises(ValueError):
        window_indices(raw(), metadata(start, end))


def test_window_outside_observed_extent_not_silently_clipped() -> None:
    r = raw()
    r.timestamp_ms[-1] = 850
    with pytest.raises(ValueError, match="outside decoded"):
        window_indices(r, metadata(10.2, 10.89))


def test_trim_recomputes_first_motion_dt_and_sparse_alignment() -> None:
    r = raw()
    emb = np.repeat(np.arange(10, dtype=np.float32)[:, None, None], 2 * 576, axis=1).reshape(
        10, 2, 576
    )
    q = np.ones((10, 2), np.float32)
    indices = np.arange(2, 8, dtype=np.int32)
    native, n = selected_input(r, indices, "native", emb, q, policy()[0])
    sparse, s = selected_input(r, indices, "phone", emb, q, policy()[0])
    names = column_names()
    assert native[0, 0] == native[0, 1] == native[0, names.index("slot0.motion_valid")] == 0
    assert sparse[1, 0] == pytest.approx(0.2)
    np.testing.assert_array_equal(native[:, 405], n)
    np.testing.assert_array_equal(sparse[:, 405], s)
    np.testing.assert_array_equal(
        native[:, 405:], np.concatenate([emb[n].reshape(len(n), 1152), q[n]], axis=1)
    )
    np.testing.assert_array_equal(native[1:, :405], derive(r)[n[1:]])
    # Existing invalid mask is retained, not filled from a previous hand.
    r.hand_observed[4] = False
    r.hand_joint_valid[4] = False
    missing, _ = selected_input(r, indices, "native", emb, q, policy()[0])
    assert missing[2, names.index("slot0.observed")] == 0


def test_native_full_matches_existing_adapter_and_is_causal() -> None:
    r = raw()
    p = np.arange(10, dtype=np.int32)
    emb = np.zeros((10, 2, 576), np.float32)
    q = np.zeros((10, 2), np.float32)
    x, _ = selected_input(r, p, "native", emb, q, policy()[0])
    np.testing.assert_array_equal(x[:, :405], derive(r))
    later = copy.deepcopy(r)
    later.hand_xy[8:] += 50
    y, _ = selected_input(later, p, "native", emb, q, policy()[0])
    np.testing.assert_array_equal(x[:8], y[:8])


def test_visual_quality_is_pointwise_after_trim() -> None:
    from pipeline.fingerspelling.adapter import subset

    r = raw()
    p = np.arange(2, 7, dtype=np.int32)
    np.testing.assert_array_equal(quality(r)["quality"][p], quality(subset(r, p))["quality"])


def test_paired_counts_and_error_composition() -> None:
    common = {
        "sample_id": "a",
        "signer_id": "s",
        "reference": "AA",
        "input_length": 4,
        "headroom": 1,
    }
    w = {
        "a": {
            "before_removed_percent": 10,
            "after_removed_percent": 20,
            "full_duration_s": 1,
            "outside_missing_hand_fraction": None,
        }
    }
    value = paired([common | {"prediction": "ABA"}], [common | {"prediction": "AA"}], w)
    assert value["directions"] == {"improve": 1}
    assert value["full"]["insertions"] == 1
    assert value["oracle"]["correct_aligned_reference_characters"] == 2
    assert value["oracle"]["exact_sequences"] == 1


def test_phase_locked_control_changes_only_outer_membership() -> None:
    original = np.array([0, 2, 4, 6, 8], np.int32)
    window = np.array([3, 4, 5, 6, 7], np.int32)
    retained = phase_locked_indices(original, window)
    np.testing.assert_array_equal(retained, [4, 6])
    assert set(retained).issubset(set(original))
    r = raw()
    emb = np.zeros((10, 2, 576), np.float32)
    q = np.zeros((10, 2), np.float32)
    f, selected = selected_input(r, retained, "native", emb, q, policy()[0])
    np.testing.assert_array_equal(selected, retained)
    assert f[0, 0] == 0 and f[1, 0] == pytest.approx(0.2)
