import json
from pathlib import Path

import pytest

from eval.runtime_diagnostics.p4c2r_truth_review import (
    ALL_FIELDS,
    UNREVIEWED,
    CompletedRowImmutable,
    DisplayedIdentity,
    ReviewIntegrityError,
    ReviewStore,
    RowIdentityMismatch,
    atomic_csv,
    review_row_id,
    sha256,
)


def make_row(tmp_path: Path, sequence: str, frame: int) -> dict[str, str]:
    image = tmp_path / f"{sequence}_{frame}.jpg"
    image.write_bytes(f"rgb:{sequence}:{frame}".encode())
    digest = sha256(image)
    return {
        "review_row_id": review_row_id(sequence, str(frame), digest),
        "source_annotation_row_id": f"source_{sequence}_{frame}",
        "sequence_id": sequence,
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


def label(left: str = "YES", right: str = "NO") -> dict[str, str]:
    return {
        "visible_left": left,
        "visible_right": right,
        "frame_state": "SIGNING",
        "reviewer_note": "",
    }


def store(tmp_path: Path, rows: list[dict[str, str]]) -> ReviewStore:
    path = tmp_path / "review.csv"
    atomic_csv(path, rows, ALL_FIELDS)
    return ReviewStore(path)


def test_fresh_review_and_status_resume(tmp_path: Path) -> None:
    rows = [make_row(tmp_path, "s", index) for index in range(3)]
    item = store(tmp_path, rows)
    assert item.next_unreviewed()["review_row_id"] == rows[0]["review_row_id"]
    item.save_new(shown(rows[0]), label())
    assert ReviewStore(item.path).next_unreviewed()["review_row_id"] == rows[1]["review_row_id"]


def test_fully_complete_returns_none(tmp_path: Path) -> None:
    rows = [make_row(tmp_path, "s", index) for index in range(2)]
    item = store(tmp_path, rows)
    for row in rows:
        item.save_new(shown(row), label())
    assert ReviewStore(item.path).next_unreviewed() is None


def test_completed_row_cannot_be_silently_overwritten(tmp_path: Path) -> None:
    row = make_row(tmp_path, "s", 1)
    item = store(tmp_path, [row])
    item.save_new(shown(row), label())
    with pytest.raises(CompletedRowImmutable):
        item.save_new(shown(row), label("NO", "YES"))


def test_explicit_edit_is_journaled(tmp_path: Path) -> None:
    row = make_row(tmp_path, "s", 1)
    item = store(tmp_path, [row])
    item.save_new(shown(row), label())
    item.edit_completed(shown(row), label("NO", "YES"), reason="review correction", confirmed=True)
    assert '"prior"' in item.journal.read_text(encoding="utf-8")
    assert ReviewStore(item.path).rows[0]["revision_count"] == "1"


def test_edit_requires_reason_and_confirmation(tmp_path: Path) -> None:
    row = make_row(tmp_path, "s", 1)
    item = store(tmp_path, [row])
    item.save_new(shown(row), label())
    with pytest.raises(CompletedRowImmutable):
        item.edit_completed(shown(row), label(), reason="", confirmed=True)


def test_duplicate_identity_rejected(tmp_path: Path) -> None:
    row = make_row(tmp_path, "s", 1)
    path = tmp_path / "review.csv"
    atomic_csv(path, [row, dict(row)], ALL_FIELDS)
    with pytest.raises(ReviewIntegrityError, match="DUPLICATE"):
        ReviewStore(path)


def test_wrong_displayed_image_hash_rejected(tmp_path: Path) -> None:
    row = make_row(tmp_path, "s", 1)
    item = store(tmp_path, [row])
    wrong = DisplayedIdentity(
        row["review_row_id"],
        row["source_annotation_row_id"],
        row["sequence_id"],
        row["frame_index"],
        "0" * 64,
        row["image_path"],
    )
    with pytest.raises(RowIdentityMismatch):
        item.save_new(wrong, label())


def test_crash_temp_file_does_not_replace_canonical(tmp_path: Path) -> None:
    rows = [make_row(tmp_path, "s", index) for index in range(2)]
    item = store(tmp_path, rows)
    item.save_new(shown(rows[0]), label())
    item.path.with_name(item.path.name + ".tmp").write_text("partial", encoding="utf-8")
    assert ReviewStore(item.path).next_unreviewed()["review_row_id"] == rows[1]["review_row_id"]


def test_atomic_save_preserves_other_rows_byte_equivalent(tmp_path: Path) -> None:
    rows = [make_row(tmp_path, "s", index) for index in range(3)]
    item = store(tmp_path, rows)
    before = {row["review_row_id"]: json.dumps(row, sort_keys=True) for row in item.rows[1:]}
    item.save_new(shown(rows[0]), label())
    after = {
        row["review_row_id"]: json.dumps(row, sort_keys=True) for row in ReviewStore(item.path).rows
    }
    assert all(after[key] == value for key, value in before.items())


def test_independent_mixed_side_answers_are_valid(tmp_path: Path) -> None:
    row = make_row(tmp_path, "s", 1)
    item = store(tmp_path, [row])
    item.save_new(shown(row), label("YES", "UNCERTAIN"))
    saved = ReviewStore(item.path).rows[0]
    assert saved["visible_left"] == "YES" and saved["visible_right"] == "UNCERTAIN"
