from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from eval.runtime_diagnostics.p4c2a_crop_review import (
    CompletedReviewImmutable,
    FIELDS,
    ReviewIntegrityError,
    ReviewStore,
    atomic_csv,
    sha256,
)


class P4C2AReviewStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.queue_path = self.root / "queue.csv"
        self.review_path = self.root / "reviews.csv"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self, count: int = 5) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        queue = []
        reviews = []
        for index in range(count):
            crop = self.root / f"crop_{index}.png"
            frame = self.root / f"frame_{index}.png"
            Image.new("RGB", (20, 20), (index, 10, 20)).save(crop)
            Image.new("RGB", (40, 40), (index, 30, 40)).save(frame)
            identifier = f"CROP_{index}"
            queue.append({
                "crop_id": identifier, "queue_order": str(index), "crop_path": str(crop),
                "crop_sha256": sha256(crop), "full_frame_path": str(frame),
                "full_frame_sha256": sha256(frame),
            })
            reviews.append({
                "crop_id": identifier, "queue_order": str(index), "crop_sha256": sha256(crop),
                "reviewer_label": "", "preliminary_label": "", "context_requested": "",
                "reviewer_status": "UNREVIEWED", "reviewed_utc": "", "revision_count": "0",
                "last_edit_utc": "", "last_edit_reason": "",
            })
        atomic_csv(self.queue_path, queue, list(queue[0]))
        atomic_csv(self.review_path, reviews, FIELDS)
        return queue, reviews

    def test_fresh_review_and_atomic_save(self) -> None:
        queue, _ = self.build()
        store = ReviewStore(self.queue_path, self.review_path)
        store.save(queue[0]["crop_id"], queue[0]["crop_sha256"], "YES_CLEAR", "YES_CLEAR", False)
        restored = ReviewStore(self.queue_path, self.review_path)
        self.assertEqual(restored.completed_count(), 1)
        self.assertEqual(restored.next_incomplete(), 1)

    def test_partial_resume_skips_completed_rows(self) -> None:
        queue, reviews = self.build()
        for index in (0, 2, 4):
            reviews[index].update({"reviewer_label": "NO", "preliminary_label": "NO",
                                   "context_requested": "NO", "reviewer_status": "COMPLETE"})
        atomic_csv(self.review_path, reviews, FIELDS)
        store = ReviewStore(self.queue_path, self.review_path)
        self.assertEqual(store.next_incomplete(), 1)
        before = dict(store.rows[2])
        store.save(queue[1]["crop_id"], queue[1]["crop_sha256"], "NO", "NO", False)
        self.assertEqual(store.next_incomplete(), 3)
        self.assertEqual(store.rows[2], before)

    def test_fully_completed_review(self) -> None:
        queue, _ = self.build(2)
        store = ReviewStore(self.queue_path, self.review_path)
        for row in queue:
            store.save(row["crop_id"], row["crop_sha256"], "NO", "NO", False)
        self.assertIsNone(store.next_incomplete())

    def test_completed_row_is_immutable(self) -> None:
        queue, _ = self.build(1)
        store = ReviewStore(self.queue_path, self.review_path)
        store.save(queue[0]["crop_id"], queue[0]["crop_sha256"], "NO", "NO", False)
        with self.assertRaises(CompletedReviewImmutable):
            store.save(queue[0]["crop_id"], queue[0]["crop_sha256"], "YES_CLEAR", "YES_CLEAR", False)

    def test_explicit_edit_is_journaled(self) -> None:
        queue, _ = self.build(1)
        store = ReviewStore(self.queue_path, self.review_path)
        store.save(queue[0]["crop_id"], queue[0]["crop_sha256"], "NO", "NO", False)
        store.save(queue[0]["crop_id"], queue[0]["crop_sha256"], "YES_PARTIAL", "NO", True,
                   allow_edit=True, edit_reason="mistake")
        self.assertEqual(store.rows[0]["revision_count"], "1")
        self.assertTrue(store.journal_path.is_file())

    def test_duplicate_crop_id_rejected(self) -> None:
        queue, reviews = self.build(2)
        queue[1]["crop_id"] = queue[0]["crop_id"]
        atomic_csv(self.queue_path, queue, list(queue[0]))
        with self.assertRaises(ReviewIntegrityError):
            ReviewStore(self.queue_path, self.review_path, verify_images=False)

    def test_wrong_crop_hash_rejected(self) -> None:
        queue, _ = self.build(1)
        Path(queue[0]["crop_path"]).write_bytes(b"changed")
        with self.assertRaises(ReviewIntegrityError):
            ReviewStore(self.queue_path, self.review_path)

    def test_save_targets_crop_id_not_position(self) -> None:
        queue, _ = self.build(3)
        store = ReviewStore(self.queue_path, self.review_path)
        store.save(queue[2]["crop_id"], queue[2]["crop_sha256"], "UNCERTAIN", "UNCERTAIN", False)
        self.assertEqual(store.rows[2]["reviewer_status"], "COMPLETE")
        self.assertEqual(store.rows[0]["reviewer_status"], "UNREVIEWED")

    def test_context_request_preserved(self) -> None:
        queue, _ = self.build(1)
        store = ReviewStore(self.queue_path, self.review_path)
        store.save(queue[0]["crop_id"], queue[0]["crop_sha256"], "YES_CLEAR", "UNCERTAIN", True)
        self.assertEqual(store.rows[0]["context_requested"], "YES")
        self.assertEqual(store.rows[0]["preliminary_label"], "UNCERTAIN")


if __name__ == "__main__":
    unittest.main()
