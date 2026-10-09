from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

import eval.runtime_diagnostics.p4c3b_physical_instance_review as review


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4c3b_physical_instance_validation_01"


def copy_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("p4c3b_review_queue.csv", "p4c3b_raw_A_visual_validation.csv", "p4c3b_pair_review.csv"):
        shutil.copy2(PACKAGE / name, tmp_path / name)
    for name in ("p4c3b_raw_A_visual_validation.csv", "p4c3b_pair_review.csv"):
        path = tmp_path / name
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            row.update({"review_label": "", "reviewer_status": "UNREVIEWED", "reviewed_utc": "", "revision_count": "0", "last_edit_utc": "", "last_edit_reason": ""})
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    monkeypatch.setattr(review, "QUEUE", tmp_path / "p4c3b_review_queue.csv")
    monkeypatch.setattr(review, "RAW_REVIEW", tmp_path / "p4c3b_raw_A_visual_validation.csv")
    monkeypatch.setattr(review, "PAIR_REVIEW", tmp_path / "p4c3b_pair_review.csv")
    monkeypatch.setattr(review, "BACKUPS", tmp_path / "backups")
    monkeypatch.setattr(review, "JOURNAL", tmp_path / "journal.jsonl")


def label_for(item: dict[str, str]) -> str:
    return "AMBIGUOUS"


def test_package_counts_and_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    copy_package(tmp_path, monkeypatch)
    store = review.ReviewStore()
    assert len(store.queue) == 121
    assert store.completed() == 0
    first = store.next_incomplete()
    assert first is not None
    store.save(first, label_for(first))
    assert store.completed() == 1
    assert store.next_incomplete()["item_id"] != first["item_id"]
    restarted = review.ReviewStore()
    assert restarted.completed() == 1
    assert restarted.next_incomplete()["item_id"] != first["item_id"]


def test_completed_row_cannot_be_silently_overwritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    copy_package(tmp_path, monkeypatch)
    store = review.ReviewStore()
    first = store.next_incomplete()
    assert first is not None
    store.save(first, label_for(first))
    with pytest.raises(RuntimeError, match="IMMUTABLE"):
        store.save(first, label_for(first))


def test_explicit_undo_is_journaled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    copy_package(tmp_path, monkeypatch)
    store = review.ReviewStore()
    first = store.next_incomplete()
    assert first is not None
    store.save(first, label_for(first))
    assert store.undo_last() is True
    assert store.completed() == 0
    assert (tmp_path / "journal.jsonl").read_text(encoding="utf-8").count("EXPLICIT_UNDO") == 1


def test_wrong_overlay_hash_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    copy_package(tmp_path, monkeypatch)
    queue_path = tmp_path / "p4c3b_review_queue.csv"
    with queue_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["overlay_sha256"] = "0" * 64
    with queue_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(RuntimeError, match="INTEGRITY"):
        review.ReviewStore()


def test_task_specific_labels_are_enforced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    copy_package(tmp_path, monkeypatch)
    store = review.ReviewStore()
    raw_item = next(item for item in store.queue if item["task_type"] == "RAW_A")
    pair_item = next(item for item in store.queue if item["task_type"] == "PAIR")
    with pytest.raises(RuntimeError, match="INVALID_REVIEW_LABEL"):
        store.save(raw_item, "SAME_PHYSICAL_HAND")
    with pytest.raises(RuntimeError, match="INVALID_REVIEW_LABEL"):
        store.save(pair_item, "MISSING_REAL_HAND")
