from pathlib import Path

import pytest

from eval.runtime_diagnostics.p4c2r_truth_review import (
    CompletedRowImmutable,
    RowIdentityMismatch,
    sha256,
)
from eval.runtime_diagnostics.p4gt1r_adjudication_review import (
    ALL_FIELDS,
    UNREVIEWED,
    AdjudicationStore,
    DisplayedIdentity,
    adjudication_row_id,
    atomic_review,
    validate_label,
)


def make_row(tmp_path: Path, frame: int) -> dict[str, str]:
    image = tmp_path / f"frame_{frame}.jpg"
    image.write_bytes(f"rgb:{frame}".encode())
    digest = sha256(image)
    return {
        "adjudication_row_id": adjudication_row_id(f"frame_{frame}", digest),
        "frame_id": f"frame_{frame}",
        "source_sha256": digest,
        "current_image_path": str(image),
        "previous_image_path": "",
        "previous_image_sha256": "",
        "next_image_path": "",
        "next_image_sha256": "",
        "queue_order": str(frame),
        **UNREVIEWED,
    }


def shown(row: dict[str, str]) -> DisplayedIdentity:
    return DisplayedIdentity(
        row["adjudication_row_id"],
        row["frame_id"],
        row["source_sha256"],
        row["current_image_path"],
    )


def label(count: str = "ONE", owner: str = "UNCERTAIN", context: str = "NO") -> dict[str, str]:
    return {
        "visible_hand_count": count,
        "one_hand_ownership": owner,
        "ownership_context_used": context,
    }


def store(tmp_path: Path, count: int = 2) -> tuple[AdjudicationStore, list[dict[str, str]]]:
    rows = [make_row(tmp_path, index) for index in range(count)]
    path = tmp_path / "review.csv"
    atomic_review(path, rows)
    assert list(rows[0]) == ALL_FIELDS
    return AdjudicationStore(path), rows


def test_count_one_uncertain_ownership_is_valid() -> None:
    validate_label(label("ONE", "UNCERTAIN"))


def test_count_one_requires_ownership() -> None:
    with pytest.raises(Exception, match="LEFT, RIGHT, or UNCERTAIN"):
        validate_label(label("ONE", ""))


def test_non_one_requires_not_applicable() -> None:
    with pytest.raises(Exception, match="NOT_APPLICABLE"):
        validate_label(label("ZERO", "LEFT"))


def test_explicit_confirm_save_and_resume(tmp_path: Path) -> None:
    item, rows = store(tmp_path)
    item.save_new(shown(rows[0]), label("ZERO", "NOT_APPLICABLE"))
    assert AdjudicationStore(item.path).next_unreviewed()["frame_id"] == rows[1]["frame_id"]


def test_completed_row_is_immutable(tmp_path: Path) -> None:
    item, rows = store(tmp_path, 1)
    item.save_new(shown(rows[0]), label("TWO", "NOT_APPLICABLE"))
    with pytest.raises(CompletedRowImmutable):
        item.save_new(shown(rows[0]), label("ZERO", "NOT_APPLICABLE"))


def test_context_use_is_recorded(tmp_path: Path) -> None:
    item, rows = store(tmp_path, 1)
    item.save_new(shown(rows[0]), label("ONE", "RIGHT", "YES"))
    saved = AdjudicationStore(item.path).rows[0]
    assert saved["ownership_context_used"] == "YES"


def test_wrong_identity_rejected(tmp_path: Path) -> None:
    item, rows = store(tmp_path, 1)
    wrong = DisplayedIdentity(
        rows[0]["adjudication_row_id"],
        rows[0]["frame_id"],
        "0" * 64,
        rows[0]["current_image_path"],
    )
    with pytest.raises(RowIdentityMismatch):
        item.save_new(wrong, label())


def test_explicit_edit_journal(tmp_path: Path) -> None:
    item, rows = store(tmp_path, 1)
    item.save_new(shown(rows[0]), label("ONE", "LEFT"))
    item.edit_completed(
        shown(rows[0]), label("ONE", "UNCERTAIN"), reason="ownership uncertain", confirmed=True
    )
    assert "EDIT_COMPLETED_LABEL" in item.journal.read_text(encoding="utf-8")
