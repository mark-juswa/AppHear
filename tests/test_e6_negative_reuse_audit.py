from pipeline.rgb.e6_negative_reuse_audit import _coverage_rows


def test_coverage_recalculation_uses_historical_p1_and_n0_credit() -> None:
    windows = [
        *({"negative_subtype": "P1_IDLE_HANDS"} for _ in range(143)),
        *({"negative_subtype": "P1_FACE_ADJACENT"} for _ in range(54)),
    ]

    rows = {row["negative_subtype"]: row for row in _coverage_rows(windows)}

    assert rows["N0_NO_HAND"]["remaining_volume_gap"] == 0
    assert rows["P1_IDLE_HANDS"]["remaining_volume_gap"] == 57
    assert rows["P1_FACE_ADJACENT"]["remaining_volume_gap"] == 146
    assert rows["P1_ACCIDENTAL_MOTION"]["remaining_volume_gap"] == 150
    assert sum(row["remaining_volume_gap"] for row in rows.values()) == 653
    assert all(row["fresh_evaluation_windows"] == 0 for row in rows.values())
