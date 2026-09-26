from pathlib import Path

import pytest

from eval.runtime_diagnostics.p4c2r_truth_review import (
    ALL_FIELDS,
    UNREVIEWED,
    CompletedRowImmutable,
    DisplayedIdentity,
    RowIdentityMismatch,
    atomic_csv,
    review_row_id,
    sha256,
)
from eval.runtime_diagnostics.p4gt1_pass1_review import GT1Store


def make_row(tmp_path: Path, frame: int) -> dict[str, str]:
    image = tmp_path / f"frame_{frame}.jpg"
    image.write_bytes(f"rgb:{frame}".encode())
    digest = sha256(image)
    return {
        "review_row_id": review_row_id("sequence", str(frame), digest),
        "source_annotation_row_id": f"source_{frame}",
        "sequence_id": "sequence",
        "frame_index": str(frame),
        "image_sha256": digest,
        "image_path": str(image),
        "queue_order": str(frame),
        **UNREVIEWED,
    }


def shown(row: dict[str, str]) -> DisplayedIdentity:
    return DisplayedIdentity(
        row["review_row_id"],
        row["source_annotation_row_id"],
        row["sequence_id"],
        row["frame_index"],
        row["image_sha256"],
        row["image_path"],
    )


def label() -> dict[str, str]:
    return {
        "visible_left": "YES",
        "visible_right": "NO",
        "frame_state": "REST",
        "reviewer_note": "",
    }


def make_store(tmp_path: Path, count: int = 3) -> tuple[GT1Store, list[dict[str, str]]]:
    rows = [make_row(tmp_path, index) for index in range(count)]
    path = tmp_path / "p4gt1_review.csv"
    atomic_csv(path, rows, ALL_FIELDS)
    return GT1Store(path), rows


def test_gt1_status_driven_resume(tmp_path: Path) -> None:
    store, rows = make_store(tmp_path)
    store.save_new(shown(rows[0]), label())
    assert GT1Store(store.path).next_unreviewed()["review_row_id"] == rows[1]["review_row_id"]


def test_gt1_completed_row_is_immutable(tmp_path: Path) -> None:
    store, rows = make_store(tmp_path, 1)
    store.save_new(shown(rows[0]), label())
    with pytest.raises(CompletedRowImmutable):
        store.save_new(shown(rows[0]), label())


def test_gt1_explicit_edit_is_journaled(tmp_path: Path) -> None:
    store, rows = make_store(tmp_path, 1)
    store.save_new(shown(rows[0]), label())
    store.edit_completed(shown(rows[0]), label(), reason="human correction", confirmed=True)
    assert store.journal.is_file()
    assert "EDIT_COMPLETED_LABEL" in store.journal.read_text(encoding="utf-8")


def test_gt1_wrong_source_hash_stops(tmp_path: Path) -> None:
    store, rows = make_store(tmp_path, 1)
    wrong = DisplayedIdentity(
        rows[0]["review_row_id"],
        rows[0]["source_annotation_row_id"],
        rows[0]["sequence_id"],
        rows[0]["frame_index"],
        "0" * 64,
        rows[0]["image_path"],
    )
    with pytest.raises(RowIdentityMismatch):
        store.save_new(wrong, label())


def test_gt1_partial_temp_file_does_not_replace_canonical(tmp_path: Path) -> None:
    store, rows = make_store(tmp_path, 2)
    store.save_new(shown(rows[0]), label())
    store.path.with_name(store.path.name + ".tmp").write_text("partial", encoding="utf-8")
    assert GT1Store(store.path).next_unreviewed()["review_row_id"] == rows[1]["review_row_id"]
