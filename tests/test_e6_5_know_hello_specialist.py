from __future__ import annotations

import numpy as np

from pipeline.rgb.e6_5_know_hello_specialist import (
    EVAL_SPLITS,
    _filter_pair_payload,
    _pair_report,
    _summarize_branch,
)


def test_filter_pair_payload_preserves_lineage_and_remaps_labels() -> None:
    data = {
        "X": np.zeros((5, 96, 258), dtype=np.float32),
        "frame_mask": np.ones((5, 96), dtype=bool),
        "lengths": np.full(5, 96, dtype=np.int32),
        "y": np.asarray([0, 1, 4, 2, 1], dtype=np.int32),
        "participant_ids": np.asarray(["a", "b", "c", "d", "e"]),
        "sample_ids": np.asarray(["s0", "s1", "s2", "s3", "s4"]),
        "source_ids": np.asarray(["x"] * 5),
    }

    result = _filter_pair_payload(data)

    assert result["sample_ids"].tolist() == ["s1", "s2", "s4"]
    assert result["original_y"].tolist() == [1, 4, 1]
    assert result["y"].tolist() == [0, 1, 0]
    assert result["X"].shape == (3, 96, 258)


def test_pair_report_counts_rejected_predictions_as_errors() -> None:
    report = _pair_report(
        np.asarray([0, 1, -1, 1], dtype=np.int32),
        np.asarray([0, 1, 0, 0], dtype=np.int32),
    )

    assert report["accuracy"] == 0.5
    assert report["per_class"]["HELLO"]["recall"] == 1.0 / 3.0
    assert report["per_class"]["KNOW"]["recall"] == 1.0


def _view(accuracy: float, hello: float, know: float) -> dict:
    return {
        "accuracy": accuracy,
        "per_class": {
            "HELLO": {"count": 10, "correct": int(hello * 10), "recall": hello},
            "KNOW": {"count": 10, "correct": int(know * 10), "recall": know},
        },
    }


def test_summary_requires_real_gain_and_all_views() -> None:
    branch_rows = []
    primary_rows = []
    for _seed in range(3):
        branch_rows.append(
            {
                split: {
                    "routed_specialist": _view(
                        0.95,
                        1.0,
                        0.9 if split == "validation_variant_stress" else 0.9,
                    )
                }
                for split in EVAL_SPLITS
            }
        )
        primary_rows.append(
            {
                split: {"five_way_primary": _view(0.70, 1.0, 0.4)}
                for split in EVAL_SPLITS
            }
        )

    summary = _summarize_branch(branch_rows, primary_rows)

    assert summary["passed"] is True
    assert summary["mean_fresh_gain_over_primary"] == 0.25
    assert summary["mean_stress_gain_over_primary"] == 0.25


def test_summary_fails_when_stress_know_is_not_recovered() -> None:
    branch_rows = []
    primary_rows = []
    for _seed in range(3):
        branch_rows.append(
            {
                split: {
                    "routed_specialist": _view(
                        0.95,
                        1.0,
                        0.2 if split == "validation_variant_stress" else 0.9,
                    )
                }
                for split in EVAL_SPLITS
            }
        )
        primary_rows.append(
            {
                split: {"five_way_primary": _view(0.70, 1.0, 0.4)}
                for split in EVAL_SPLITS
            }
        )

    summary = _summarize_branch(branch_rows, primary_rows)

    assert summary["passed"] is False
    assert summary["gate_checks"]["stress_know"] is False
