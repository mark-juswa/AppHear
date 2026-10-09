from __future__ import annotations

import numpy as np

from model.experiments.ru_d4_cleanup_only_ab import (
    BRANCHES,
    SEEDS,
    _canonical_recipe,
    _metrics,
)


def test_ru_d4_recipe_is_canonical_production_tcn_contract() -> None:
    recipe = _canonical_recipe()
    assert recipe["model_branch"] == "production_streaming_tcn"
    assert recipe["seeds"] == [101, 202, 303]
    assert recipe["model"] == {
        "blocks": 4,
        "channels": 64,
        "dilations": [1, 2, 4, 8],
        "kernel": 3,
        "dropout": 0.3,
    }
    assert recipe["training"]["batch_size"] == 32
    assert recipe["training"]["epochs"] == 40
    assert recipe["training"]["early_stop_patience"] == 8
    assert BRANCHES == ("A_frozen_baseline", "B_ru_d3_cleanup")
    assert SEEDS == (101, 202, 303)


def test_ru_d4_metrics_include_requested_worst_decile_and_calibration() -> None:
    probabilities = np.asarray(
        [[0.9, 0.1], [0.2, 0.8], [0.6, 0.4], [0.3, 0.7]], dtype=np.float32
    )
    labels = np.asarray([0, 1, 1, 0], dtype=np.int32)
    signers = np.asarray(["S1", "S1", "S2", "S2"])
    result = _metrics(probabilities, labels, signers, {0: "A", 1: "B"})
    assert result["top1"] == 0.5
    assert result["top5"] == 1.0
    assert "macro_f1" in result
    assert "worst_decile_mean_recall" in result
    assert "worst_decile_mean_f1" in result
    assert "ece_15_bin" in result
    assert [row["gloss"] for row in result["per_class"]] == ["A", "B"]
