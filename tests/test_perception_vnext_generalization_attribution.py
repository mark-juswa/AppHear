from __future__ import annotations

import numpy as np

from eval.runtime_diagnostics.perception_vnext_generalization_attribution import (
    _class_conditioned_shift_analysis,
    _rankdata,
    _spearman,
    _standardized_difference,
)


def test_rankdata_and_spearman_preserve_ties() -> None:
    np.testing.assert_allclose(_rankdata(np.asarray([3.0, 1.0, 1.0, 2.0])), [4.0, 1.5, 1.5, 3.0])
    assert _spearman([1, 2, 3, 4], [10, 20, 30, 40])["rho"] == 1.0
    assert _spearman([1, 1, 1], [2, 3, 4])["status"] == "UNAVAILABLE_CONSTANT_OR_SMALL"


def test_standardized_difference_direction_is_group_a_minus_b() -> None:
    effect = _standardized_difference([3.0, 4.0, 5.0], [0.0, 1.0, 2.0])
    assert effect["standardized_mean_difference"] > 0
    assert effect["rank_biserial"] == 1.0


def test_class_conditioned_shift_uses_same_class_reference() -> None:
    train = [
        {"class_id": 0, "metric": 0.0},
        {"class_id": 0, "metric": 2.0},
        {"class_id": 1, "metric": 100.0},
        {"class_id": 1, "metric": 102.0},
    ]
    dev = [
        {
            "sample_id": "a",
            "signer_id": "s1",
            "class_id": 0,
            "metric": 1.0,
            "dense_correct": True,
            "phone_01_sparse_correct": True,
        },
        {
            "sample_id": "b",
            "signer_id": "s2",
            "class_id": 1,
            "metric": 103.0,
            "dense_correct": False,
            "phone_01_sparse_correct": False,
        },
    ]
    result = _class_conditioned_shift_analysis(train, dev, ("metric",))
    assert result["metrics"]["metric"]["matched_dev_clips"] == 2
    assert result["metrics"]["metric"]["by_signer"]["s1"]["median_abs_z"] == 0.0
    assert result["metrics"]["metric"]["by_signer"]["s2"]["signed_mean_z"] > 0
