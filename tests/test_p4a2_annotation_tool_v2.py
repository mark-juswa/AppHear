import json
from pathlib import Path

import pytest

from eval.runtime_diagnostics.p4a2_annotation_tool_v2 import (
    ALL_FIELDS,
    AnnotationIntegrityError,
    AnnotationRowIdentityMismatch,
    AnnotationStore,
    CompletedRowImmutable,
    DisplayedIdentity,
    UNREVIEWED_DEFAULTS,
    atomic_write_csv,
    immutable_row_id,
    sha256,
)


def make_row(tmp_path: Path, sequence: str, frame: int, *, batch: str = "INITIAL") -> dict[str, str]:
    image = tmp_path / f"{sequence}_{frame}.jpg"
    image.write_bytes(f"rgb:{sequence}:{frame}".encode())
    digest = sha256(image)
    return {
        "annotation_row_id": immutable_row_id(sequence, str(frame), digest),
        "source_annotation_row_id": f"old_{sequence}_{frame}",
        "source_family": "MOCK",
        "sequence_id": sequence,
        "frame_index": str(frame),
        "image_sha256": digest,
        "review_image_path": str(image),
        "signer_id": "hidden",
        "gloss": "hidden",
        "intended_future_role": "DEV_POOL",
        "review_batch": batch,
        "queue_order": str(frame),
        **UNREVIEWED_DEFAULTS,
    }


def identity(row: dict[str, str]) -> DisplayedIdentity:
    return DisplayedIdentity(
        row["annotation_row_id"], row["sequence_id"], row["frame_index"],
        row["image_sha256"], row["review_image_path"],
    )


def label(kind: str = "left") -> dict[str, str]:
    left, right = kind in {"left", "both"}, kind in {"right", "both"}
    visible = left or right
    return {
        "any_hand_visible": "YES" if visible else "NO",
        "visible_left": "YES" if left else "NO",
        "visible_right": "YES" if right else "NO",
        "zero_hand": "NO" if visible else "YES",
        "rest": "NO" if visible else "YES",
        "entering": "NO", "leaving": "NO", "blur": "NO", "occlusion": "NO",
        "edge_clipped": "NO", "partial_visibility": "NO", "crossing": "NO",
        "hand_hand_contact": "NO", "hand_body_contact": "NO",
        "left_visibility_quality": "CLEAR" if left else "NOT_APPLICABLE",
        "right_visibility_quality": "CLEAR" if right else "NOT_APPLICABLE",
        "reviewer_note": "",
    }


def store_for(tmp_path: Path, rows: list[dict[str, str]]) -> AnnotationStore:
    canonical = tmp_path / "annotations.csv"
    atomic_write_csv(canonical, rows, ALL_FIELDS)
    return AnnotationStore(canonical)


def test_fresh_empty_review(tmp_path: Path):
    rows = [make_row(tmp_path, "s", index) for index in range(3)]
    store = store_for(tmp_path, rows)
    assert store.next_unreviewed()["annotation_row_id"] == rows[0]["annotation_row_id"]
    assert all(row["reviewer_status"] == "UNREVIEWED" for row in store.rows)


def test_partial_review_resume_scans_status(tmp_path: Path):
    rows = [make_row(tmp_path, "s", index) for index in range(3)]
    store = store_for(tmp_path, rows)
    next_row = store.save_new(identity(rows[0]), label())
    assert next_row["annotation_row_id"] == rows[1]["annotation_row_id"]
    restarted = AnnotationStore(store.canonical)
    assert restarted.next_unreviewed()["annotation_row_id"] == rows[1]["annotation_row_id"]


def test_fully_completed_review_returns_none(tmp_path: Path):
    rows = [make_row(tmp_path, "s", index) for index in range(2)]
    store = store_for(tmp_path, rows)
    for row in rows:
        store.save_new(identity(row), label())
    assert AnnotationStore(store.canonical).next_unreviewed() is None


def test_reproduction_interspersed_topup_changes_only_three_new_rows(tmp_path: Path):
    original = [make_row(tmp_path, "seq", frame) for frame in range(10)]
    store = store_for(tmp_path, original)
    for row in original:
        store.save_new(identity(row), label("left"))
    before = {row["annotation_row_id"]: json.dumps(row, sort_keys=True) for row in AnnotationStore(store.canonical).rows}
    topups = [make_row(tmp_path, "seq", frame, batch="TARGETED_TOPUP") for frame in (2_001, 6_001, 9_001)]
    # Sort keys place these by status-driven identity; physical CSV position is irrelevant.
    store.append_unreviewed(topups)
    visited = []
    while True:
        row = store.next_unreviewed()
        if row is None:
            break
        visited.append(row["annotation_row_id"])
        store.save_new(identity(row), label("right"))
    after = {row["annotation_row_id"]: json.dumps(row, sort_keys=True) for row in AnnotationStore(store.canonical).rows}
    assert set(visited) == {row["annotation_row_id"] for row in topups}
    assert all(after[row_id] == payload for row_id, payload in before.items())


def test_undo_is_explicit_and_journaled(tmp_path: Path):
    row = make_row(tmp_path, "s", 1)
    store = store_for(tmp_path, [row])
    store.save_new(identity(row), label())
    store.undo_completed(identity(row), reason="reviewer correction", confirmed=True)
    assert AnnotationStore(store.canonical).rows[0]["reviewer_status"] == "UNREVIEWED"
    assert "UNDO_COMPLETED_LABEL" in store.journal.read_text(encoding="utf-8")


def test_completed_row_requires_explicit_edit_and_records_prior_new(tmp_path: Path):
    row = make_row(tmp_path, "s", 1)
    store = store_for(tmp_path, [row])
    store.save_new(identity(row), label("left"))
    with pytest.raises(CompletedRowImmutable):
        store.save_new(identity(row), label("right"))
    store.edit_completed(identity(row), label("right"), reason="mistake", confirmed=True)
    edited = AnnotationStore(store.canonical).rows[0]
    assert edited["visible_right"] == "YES" and edited["revision_count"] == "1"
    journal = store.journal.read_text(encoding="utf-8")
    assert '"prior"' in journal and '"replacement"' in journal and '"reason": "mistake"' in journal


def test_crash_restart_ignores_uncommitted_temp_file(tmp_path: Path):
    rows = [make_row(tmp_path, "s", index) for index in range(2)]
    store = store_for(tmp_path, rows)
    store.save_new(identity(rows[0]), label())
    store.canonical.with_name(store.canonical.name + ".tmp").write_text("corrupt partial write", encoding="utf-8")
    restarted = AnnotationStore(store.canonical)
    assert restarted.next_unreviewed()["annotation_row_id"] == rows[1]["annotation_row_id"]


def test_duplicate_row_id_rejected(tmp_path: Path):
    row = make_row(tmp_path, "s", 1)
    canonical = tmp_path / "annotations.csv"
    atomic_write_csv(canonical, [row, dict(row)], ALL_FIELDS)
    with pytest.raises(AnnotationIntegrityError, match="DUPLICATE"):
        AnnotationStore(canonical)


def test_wrong_image_sha_or_display_identity_rejected(tmp_path: Path):
    row = make_row(tmp_path, "s", 1)
    store = store_for(tmp_path, [row])
    wrong = DisplayedIdentity(row["annotation_row_id"], row["sequence_id"], row["frame_index"], "0" * 64, row["review_image_path"])
    with pytest.raises(AnnotationRowIdentityMismatch, match="ANNOTATION_ROW_IDENTITY_MISMATCH"):
        store.save_new(wrong, label())


def test_topup_after_partial_completion_preserves_completed_rows(tmp_path: Path):
    rows = [make_row(tmp_path, "s", index) for index in range(5)]
    store = store_for(tmp_path, rows)
    for row in rows[:2]:
        store.save_new(identity(row), label("left"))
    before = {row["annotation_row_id"]: json.dumps(row, sort_keys=True) for row in AnnotationStore(store.canonical).rows if row["reviewer_status"] == "COMPLETE"}
    topups = [make_row(tmp_path, "a", 3, batch="TARGETED_TOPUP"), make_row(tmp_path, "z", 1, batch="TARGETED_TOPUP")]
    store.append_unreviewed(topups)
    after = {row["annotation_row_id"]: json.dumps(row, sort_keys=True) for row in AnnotationStore(store.canonical).rows}
    assert all(after[row_id] == payload for row_id, payload in before.items())
    assert sum(row["reviewer_status"] == "UNREVIEWED" for row in store.rows) == 5
