from pipeline.rgb.e6_v30_five_sign_baseline import (
    CLASSES,
    ROLE_TO_SPLIT,
    _per_class,
    _select_smoke_rows,
)

import numpy as np


def test_roles_keep_fresh_and_historical_tests_separate() -> None:
    assert ROLE_TO_SPLIT["test_positive_fresh"] == "test_fresh"
    assert ROLE_TO_SPLIT["test_positive_historical"] == "test_historical"


def test_smoke_selection_has_every_class_in_train_and_val() -> None:
    rows = [
        {"split": split, "canonical_label": label, "sample_id": f"{split}_{label}"}
        for split in ("train", "val")
        for label in CLASSES
    ]
    selected = _select_smoke_rows(rows)
    assert len(selected) == 10
    assert {(row["split"], row["canonical_label"]) for row in selected} == {
        (split, label) for split in ("train", "val") for label in CLASSES
    }


def test_per_class_reports_recall() -> None:
    y = np.arange(len(CLASSES), dtype=np.int32)
    probs = np.eye(len(CLASSES), dtype=np.float32)
    report = _per_class(probs, y)
    assert all(report[label]["recall"] == 1.0 for label in CLASSES)
