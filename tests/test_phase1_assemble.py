import numpy as np

from pipeline.splits.phase1_assemble import _select_rows, validate_arrays


def _valid_arrays(n: int = 2) -> tuple[np.ndarray, ...]:
    x = np.zeros((n, 96, 258), dtype=np.float32)
    y = np.arange(n, dtype=np.int32)
    mask = np.zeros((n, 96), dtype=bool)
    mask[:, :4] = True
    lengths = np.full(n, 4, dtype=np.int32)
    return x, y, mask, lengths


def test_validate_arrays_accepts_v30_contract() -> None:
    assert validate_arrays(*_valid_arrays()) == []


def test_validate_arrays_rejects_mask_length_mismatch() -> None:
    x, y, mask, lengths = _valid_arrays()
    lengths[0] = 3
    assert "frame_mask counts do not equal lengths" in validate_arrays(
        x, y, mask, lengths
    )


def test_select_rows_preserves_manifest_order_and_role() -> None:
    rows = [
        {"sample_id": "a", "role": "primary_train"},
        {"sample_id": "b", "role": "primary_val"},
        {"sample_id": "c", "role": "supplement_train"},
    ]
    selected = _select_rows(
        rows, ("primary_train", "supplement_train"), smoke_limit=None
    )
    assert [row["sample_id"] for row in selected] == ["a", "c"]


def test_smoke_selection_samples_each_requested_role() -> None:
    rows = [
        {"sample_id": "a1", "role": "primary_train"},
        {"sample_id": "a2", "role": "primary_train"},
        {"sample_id": "b1", "role": "supplement_train"},
        {"sample_id": "b2", "role": "supplement_train"},
    ]
    selected = _select_rows(
        rows, ("primary_train", "supplement_train"), smoke_limit=1
    )
    assert [row["sample_id"] for row in selected] == ["a1", "b1"]
