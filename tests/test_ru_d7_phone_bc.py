from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from eval.runtime_diagnostics.ru_d7_phone_bc import PANEL, prediction_row, read_queue

ROOT = Path(__file__).resolve().parents[1]


def test_queue_is_bounded_and_balanced() -> None:
    rows = read_queue(ROOT / "context/recognition_upgrade/ru_d7_phone_bc_queue.csv")
    assert len(rows) == 26
    assert {row["gloss"] for row in rows} == set(PANEL)
    assert all(sum(item["gloss"] == gloss for item in rows) == 2 for gloss in PANEL)


def test_prediction_row_reports_rank_top5_and_s7() -> None:
    probabilities = np.full(236, 1e-5, dtype=np.float32)
    probabilities[7] = 0.7
    probabilities[3] = 0.2
    probabilities /= probabilities.sum()
    config = {
        "temperature": 1.0,
        "theta_conf": -10.0,
        "theta_margin": 0.0,
        "k_stability": 1,
        "low_fps_confirmation": {"enabled": False},
    }
    vocab = {index: f"G{index}" for index in range(236)}
    row = prediction_row((probabilities,), (False,), None, 3, vocab, config)
    assert row["top1"] == "G7"
    assert row["target_rank"] == 2
    assert row["top5"].split("|")[:2] == ["G7", "G3"]
    assert row["s7_commit"] == "G7"


def test_prediction_row_preserves_s5_no_inference_for_oracle_followup() -> None:
    row = prediction_row((), (), (), 3, {3: "WHO"}, {})
    assert row["top1"] == ""
    assert row["target_rank"] == -1
    assert row["s7_commit"] == ""


def test_queue_csv_has_no_blank_operating_fields() -> None:
    path = ROOT / "context/recognition_upgrade/ru_d7_phone_bc_queue.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key in (
            "capture_order",
            "gloss",
            "expected_hands",
            "repetition_id",
            "variant",
            "instruction",
        ):
            assert row[key].strip(), (row["capture_order"], key)
