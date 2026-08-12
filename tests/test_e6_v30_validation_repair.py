from collections import Counter

import pytest

from pipeline.rgb.e6_v30_validation_repair import CLASSES, plan_assignments


def _row(split: str, signer: str, label: str, source: str = "local") -> dict[str, str]:
    return {
        "split": split,
        "signer_group_id": signer,
        "canonical_label": label,
        "source_dataset": source,
    }


def test_plan_moves_complete_signer_and_preserves_stress() -> None:
    rows = []
    for label in CLASSES:
        rows.extend(_row("train", "complete", label) for _ in range(20))
    rows.append(_row("train", "other", "GOOD"))
    rows.append(_row("val", "asl", "GOOD", "asl_citizen"))
    rows.append(_row("val", "app", "GOOD", "apphear_capture"))
    planned = plan_assignments(rows, "complete")
    counts = Counter(row["new_split"] for row in planned)
    assert counts["val"] == 101
    assert counts["train"] == 1
    assert counts["validation_variant_stress"] == 1


def test_plan_rejects_incomplete_validation_signer() -> None:
    rows = [_row("train", "incomplete", "GOOD") for _ in range(20)]
    with pytest.raises(ValueError, match="lacks >=20"):
        plan_assignments(rows, "incomplete")
