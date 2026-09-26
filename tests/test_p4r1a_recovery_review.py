from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

import eval.runtime_diagnostics.p4r1a_recovery_review as review


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4r1a_rtmpose_hand5_targeted_recovery_01"


def copy_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("p4r1a_recovery_review_queue.csv", "p4r1a_recovery_review.csv"):
        shutil.copy2(PACKAGE / name, tmp_path / name)
    review_path = tmp_path / "p4r1a_recovery_review.csv"
    with review_path.open(encoding="utf-8-sig", newline="") as handle:
        review_rows = list(csv.DictReader(handle))
    for row in review_rows:
        row.update(
            {
                "review_label": "",
                "reviewer_status": "UNREVIEWED",
                "reviewed_utc": "",
                "revision_count": "0",
                "last_edit_utc": "",
                "last_edit_reason": "",
                "reviewer_note": "",
            }
        )
    with review_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(review_rows[0]))
        writer.writeheader()
        writer.writerows(review_rows)
    queue_path = tmp_path / "p4r1a_recovery_review_queue.csv"
    with queue_path.open(encoding="utf-8-sig", newline="") as handle:
        queue_rows = list(csv.DictReader(handle))
    overlay_dir = tmp_path / "overlays"
    overlay_dir.mkdir()
    for row in queue_rows:
        source = review.local_path(row["overlay_path"])
        target = overlay_dir / source.name
        shutil.copy2(source, target)
        row["overlay_path"] = str(target)
    with queue_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(queue_rows[0]))
        writer.writeheader()
        writer.writerows(queue_rows)
    monkeypatch.setattr(review, "QUEUE", tmp_path / "p4r1a_recovery_review_queue.csv")
    monkeypatch.setattr(review, "REVIEW", tmp_path / "p4r1a_recovery_review.csv")
    monkeypatch.setattr(review, "BACKUPS", tmp_path / "backups")
    monkeypatch.setattr(review, "JOURNAL", tmp_path / "journal.jsonl")


def test_package_count_resume_and_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    copy_package(tmp_path, monkeypatch)
    store = review.ReviewStore()
    assert len(store.queue) == 18
    first = store.next_incomplete()
    assert first is not None
    store.save(first, "AMBIGUOUS")
    restarted = review.ReviewStore()
    assert restarted.completed() == 1
    assert restarted.next_incomplete()["residual_id"] != first["residual_id"]


def test_completed_label_is_immutable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    copy_package(tmp_path, monkeypatch)
    store = review.ReviewStore()
    first = store.next_incomplete()
    assert first is not None
    store.save(first, "FALSE_REGION_OR_NO_OUTPUT")
    with pytest.raises(RuntimeError, match="IMMUTABLE"):
        store.save(first, "MISSING_HAND_RECOVERED")


def test_undo_is_explicit_and_journaled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    copy_package(tmp_path, monkeypatch)
    store = review.ReviewStore()
    first = store.next_incomplete()
    assert first is not None
    store.save(first, "AMBIGUOUS")
    assert store.undo_last()
    assert store.completed() == 0
    assert "EXPLICIT_UNDO" in (tmp_path / "journal.jsonl").read_text(encoding="utf-8")


def test_wrong_overlay_hash_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    copy_package(tmp_path, monkeypatch)
    queue_path = tmp_path / "p4r1a_recovery_review_queue.csv"
    with queue_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["overlay_sha256"] = "0" * 64
    with queue_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(RuntimeError, match="INTEGRITY"):
        review.ReviewStore()


def test_invalid_label_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    copy_package(tmp_path, monkeypatch)
    store = review.ReviewStore()
    first = store.next_incomplete()
    assert first is not None
    with pytest.raises(RuntimeError, match="INVALID_REVIEW_LABEL"):
        store.save(first, "AUTO_RECOVERED")
