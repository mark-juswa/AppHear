"""Blinded, atomic P4-C2A RGB crop review tool."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from PIL import Image, ImageTk


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4c2a_dwpose_rgb_crop_separability_01"
QUEUE = OUT / "p4c2a_blinded_review_queue.csv"
REVIEWS = OUT / "p4c2a_human_crop_review.csv"
JOURNAL = OUT / "p4c2a_completed_review_edit_journal.jsonl"
BACKUPS = OUT / "review_backups"
LABELS = ("YES_CLEAR", "YES_PARTIAL", "NO", "UNCERTAIN")
FIELDS = [
    "crop_id", "queue_order", "crop_sha256", "reviewer_label", "preliminary_label",
    "context_requested", "reviewer_status", "reviewed_utc", "revision_count",
    "last_edit_utc", "last_edit_reason",
]


class ReviewIntegrityError(RuntimeError):
    pass


class CompletedReviewImmutable(ReviewIntegrityError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


class ReviewStore:
    def __init__(self, queue_path: Path = QUEUE, review_path: Path = REVIEWS, verify_images: bool = True):
        self.queue_path = queue_path
        self.review_path = review_path
        self.journal_path = review_path.with_name("p4c2a_completed_review_edit_journal.jsonl")
        self.backup_dir = review_path.parent / "review_backups"
        self.queue = read_csv(queue_path)
        self.rows = read_csv(review_path)
        self._verify(verify_images)

    def _verify(self, verify_images: bool) -> None:
        queue_ids = [row["crop_id"] for row in self.queue]
        row_ids = [row["crop_id"] for row in self.rows]
        if len(queue_ids) != len(set(queue_ids)) or len(row_ids) != len(set(row_ids)):
            raise ReviewIntegrityError("DUPLICATE_CROP_ID")
        if queue_ids != row_ids:
            raise ReviewIntegrityError("REVIEW_QUEUE_IDENTITY_MISMATCH")
        for queue, row in zip(self.queue, self.rows):
            if queue["queue_order"] != row["queue_order"] or queue["crop_sha256"] != row["crop_sha256"]:
                raise ReviewIntegrityError("REVIEW_ROW_IDENTITY_MISMATCH")
            if verify_images:
                crop = Path(queue["crop_path"])
                if not crop.is_file() or sha256(crop) != queue["crop_sha256"]:
                    raise ReviewIntegrityError("CROP_SHA256_MISMATCH")
                full = Path(queue["full_frame_path"])
                if not full.is_file() or sha256(full) != queue["full_frame_sha256"]:
                    raise ReviewIntegrityError("FULL_FRAME_SHA256_MISMATCH")

    def completed_count(self) -> int:
        return sum(row["reviewer_status"] == "COMPLETE" for row in self.rows)

    def next_incomplete(self) -> int | None:
        return next((i for i, row in enumerate(self.rows) if row["reviewer_status"] != "COMPLETE"), None)

    def save(
        self,
        crop_id: str,
        crop_sha256: str,
        label: str,
        preliminary_label: str,
        context_requested: bool,
        *,
        allow_edit: bool = False,
        edit_reason: str = "",
    ) -> None:
        if label not in LABELS or preliminary_label not in LABELS:
            raise ReviewIntegrityError("INVALID_REVIEW_LABEL")
        matches = [i for i, row in enumerate(self.rows) if row["crop_id"] == crop_id]
        if len(matches) != 1:
            raise ReviewIntegrityError("REVIEW_ROW_IDENTITY_MISMATCH")
        index = matches[0]
        row = self.rows[index]
        queue = self.queue[index]
        if row["crop_sha256"] != crop_sha256 or queue["crop_sha256"] != crop_sha256:
            raise ReviewIntegrityError("REVIEW_ROW_IDENTITY_MISMATCH")
        actual_hash = sha256(Path(queue["crop_path"]))
        if actual_hash != crop_sha256:
            raise ReviewIntegrityError("CROP_SHA256_MISMATCH")
        now = datetime.now(timezone.utc).isoformat()
        if row["reviewer_status"] == "COMPLETE":
            if not allow_edit:
                raise CompletedReviewImmutable("COMPLETED_REVIEW_IMMUTABLE")
            if not edit_reason.strip():
                raise ReviewIntegrityError("EDIT_REASON_REQUIRED")
            append_jsonl(self.journal_path, {
                "crop_id": crop_id, "edited_utc": now, "reason": edit_reason.strip(),
                "previous": dict(row),
                "new": {"reviewer_label": label, "preliminary_label": preliminary_label,
                        "context_requested": "YES" if context_requested else "NO"},
            })
            row["revision_count"] = str(int(row["revision_count"] or 0) + 1)
            row["last_edit_utc"] = now
            row["last_edit_reason"] = edit_reason.strip()
        row["reviewer_label"] = label
        row["preliminary_label"] = preliminary_label
        row["context_requested"] = "YES" if context_requested else "NO"
        row["reviewer_status"] = "COMPLETE"
        row["reviewed_utc"] = now
        atomic_csv(self.review_path, self.rows, FIELDS)
        if self.completed_count() % 25 == 0:
            self.backup("checkpoint")

    def backup(self, reason: str) -> None:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        shutil.copy2(self.review_path, self.backup_dir / f"{stamp}_{reason}.csv")


class ReviewApp:
    def __init__(self, root: tk.Tk, store: ReviewStore):
        self.root = root
        self.store = store
        self.index = store.next_incomplete()
        self.label: str | None = None
        self.preliminary: str | None = None
        self.context_requested = False
        self.context_visible = False
        self.edit_mode = False
        self.zoom = 1.0
        self.photo: ImageTk.PhotoImage | None = None
        root.title("P4-C2A Blinded RGB Hand Crop Review")
        root.geometry("1180x780")
        self._build()
        self._bind()
        self._show()

    def _build(self) -> None:
        self.image_label = ttk.Label(self.root, anchor="center")
        self.image_label.pack(side="left", fill="both", expand=True, padx=18, pady=18)
        panel = ttk.Frame(self.root, padding=18, width=390)
        panel.pack(side="right", fill="y")
        self.progress = ttk.Label(panel, font=("Segoe UI", 13, "bold"))
        self.progress.pack(anchor="w", pady=(0, 14))
        ttk.Label(panel, text="Does this crop visibly contain a real human hand?",
                  font=("Segoe UI", 14, "bold"), wraplength=360).pack(anchor="w", pady=(0, 12))
        ttk.Label(panel, text=("1  Clear hand — identifiable hand\n"
                               "2  Partial hand — real but cropped/blurred/occluded\n"
                               "3  No hand — no identifiable human hand\n"
                               "4  Unsure — crop alone is insufficient"),
                  font=("Segoe UI", 10), justify="left", wraplength=360).pack(anchor="w", pady=(0, 16))
        self.buttons: dict[str, ttk.Button] = {}
        for key, label, text in [
            ("1", "YES_CLEAR", "1 — YES, clear hand"),
            ("2", "YES_PARTIAL", "2 — YES, partial hand"),
            ("3", "NO", "3 — NO hand"),
            ("4", "UNCERTAIN", "4 — UNCERTAIN"),
        ]:
            button = ttk.Button(panel, text=text, command=lambda value=label: self.select(value))
            button.pack(fill="x", pady=4)
            self.buttons[label] = button
        self.selection = ttk.Label(panel, text="Choose 1–4", foreground="#555")
        self.selection.pack(anchor="w", pady=(12, 8))
        self.context_button = ttk.Button(panel, text="C — Show full-frame context", command=self.toggle_context, state="disabled")
        self.context_button.pack(fill="x", pady=4)
        self.save_button = ttk.Button(panel, text="Enter — Save + Next", command=self.save, state="disabled")
        self.save_button.pack(fill="x", pady=(14, 4))
        ttk.Button(panel, text="Edit a completed label…", command=self.edit_completed).pack(fill="x", pady=4)
        ttk.Button(panel, text="Zoom +", command=lambda: self.change_zoom(1.2)).pack(side="left", pady=16)
        ttk.Button(panel, text="Zoom −", command=lambda: self.change_zoom(1 / 1.2)).pack(side="left", padx=8, pady=16)
        ttk.Label(panel, text=("Keyboard: 1–4 choose · Enter saves · C context · +/- zoom\n"
                               "Labels, side, sequence, model scores, and source metadata are hidden."),
                  foreground="#666", wraplength=360).pack(anchor="w", pady=(22, 0))

    def _bind(self) -> None:
        for key, label in zip(("1", "2", "3", "4"), LABELS):
            self.root.bind(key, lambda _event, value=label: self.select(value))
        self.root.bind("<Return>", lambda _event: self.save())
        self.root.bind("c", lambda _event: self.toggle_context())
        self.root.bind("C", lambda _event: self.toggle_context())
        self.root.bind("+", lambda _event: self.change_zoom(1.2))
        self.root.bind("-", lambda _event: self.change_zoom(1 / 1.2))
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def current_queue(self) -> dict[str, str]:
        if self.index is None:
            raise ReviewIntegrityError("ANNOTATION_COMPLETE")
        return self.store.queue[self.index]

    def select(self, label: str) -> None:
        if self.index is None:
            return
        if self.preliminary is None:
            self.preliminary = label
        self.label = label
        self.selection.configure(text=f"Selected: {label}", foreground="#075")
        self.context_button.configure(state="normal")
        self.save_button.configure(state="normal")

    def toggle_context(self) -> None:
        if self.index is None or self.preliminary is None:
            return
        self.context_requested = True
        self.context_visible = not self.context_visible
        self.context_button.configure(text="C — Show crop again" if self.context_visible else "C — Show full-frame context")
        self._render_image()

    def change_zoom(self, factor: float) -> None:
        self.zoom = min(3.0, max(0.6, self.zoom * factor))
        self._render_image()

    def _render_image(self) -> None:
        if self.index is None:
            return
        queue = self.current_queue()
        path = Path(queue["full_frame_path"] if self.context_visible else queue["crop_path"])
        image = Image.open(path).convert("RGB")
        max_width = int(720 * self.zoom)
        max_height = int(700 * self.zoom)
        image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image)
        suffix = "\nFULL FRAME CONTEXT" if self.context_visible else "\nCROP ONLY"
        self.image_label.configure(image=self.photo, text=suffix, compound="top")

    def _show(self) -> None:
        if self.index is None:
            self.progress.configure(text=f"ANNOTATION COMPLETE — {self.store.completed_count()}/{len(self.store.rows)}")
            self.image_label.configure(image="", text="ANNOTATION COMPLETE")
            self.save_button.configure(state="disabled")
            self.context_button.configure(state="disabled")
            return
        queue = self.current_queue()
        self.label = self.preliminary = None
        self.context_requested = self.context_visible = False
        self.zoom = 1.0
        self.progress.configure(text=(f"Crop {self.store.completed_count()+1}/{len(self.store.rows)}  |  "
                                      f"ID {queue['crop_id']}"))
        self.selection.configure(text="Choose 1–4", foreground="#555")
        self.save_button.configure(state="disabled")
        self.context_button.configure(state="disabled", text="C — Show full-frame context")
        self._render_image()

    def save(self) -> None:
        if self.index is None or self.label is None or self.preliminary is None:
            return
        queue = self.current_queue()
        try:
            self.store.save(queue["crop_id"], queue["crop_sha256"], self.label, self.preliminary,
                            self.context_requested, allow_edit=self.edit_mode,
                            edit_reason="explicit reviewer correction" if self.edit_mode else "")
        except ReviewIntegrityError as error:
            messagebox.showerror("Review integrity error", str(error))
            return
        self.edit_mode = False
        self.index = self.store.next_incomplete()
        self._show()

    def edit_completed(self) -> None:
        completed = [i for i, row in enumerate(self.store.rows) if row["reviewer_status"] == "COMPLETE"]
        if not completed:
            return
        crop_id = simpledialog.askstring("Edit completed label", "Enter the crop ID to edit:")
        matches = [i for i in completed if self.store.rows[i]["crop_id"] == crop_id]
        if not matches:
            messagebox.showerror("Not found", "That completed crop ID was not found.")
            return
        if not messagebox.askyesno("Confirm explicit edit", "This will journal the previous label. Continue?"):
            return
        self.index = matches[0]
        self.edit_mode = True
        self._show()

    def close(self) -> None:
        self.store.backup("session_close")
        self.root.destroy()


def summary(store: ReviewStore) -> dict[str, Any]:
    counts: dict[str, int] = {label: 0 for label in LABELS}
    for row in store.rows:
        if row["reviewer_status"] == "COMPLETE":
            counts[row["reviewer_label"]] += 1
    return {
        "rows": len(store.rows), "completed": store.completed_count(),
        "remaining": len(store.rows) - store.completed_count(), "counts": counts,
        "passed": store.completed_count() == len(store.rows),
    }


def main() -> None:
    store = ReviewStore()
    if store.next_incomplete() is None:
        print(json.dumps(summary(store), indent=2))
        return
    root = tk.Tk()
    ReviewApp(root, store)
    root.mainloop()
    store = ReviewStore()
    print(json.dumps(summary(store), indent=2))


if __name__ == "__main__":
    main()
