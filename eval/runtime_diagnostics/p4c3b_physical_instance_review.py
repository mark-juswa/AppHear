"""Minimal status-driven UI for P4-C3B physical-instance review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageTk


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4c3b_physical_instance_validation_01"
QUEUE = OUT / "p4c3b_review_queue.csv"
RAW_REVIEW = OUT / "p4c3b_raw_A_visual_validation.csv"
PAIR_REVIEW = OUT / "p4c3b_pair_review.csv"
BACKUPS = OUT / "review_backups"
JOURNAL = OUT / "p4c3b_review_edit_journal.jsonl"
RAW_LABELS = [
    ("MISSING_REAL_HAND", "1 — Missing real hand"),
    ("DUPLICATE_EXISTING_HAND", "2 — Already represented hand"),
    ("OTHER_FALSE_REGION", "3 — Neither real hand"),
    ("AMBIGUOUS", "4 — Cannot determine"),
]
PAIR_LABELS = [
    ("SAME_PHYSICAL_HAND", "1 — Same physical hand"),
    ("DISTINCT_PHYSICAL_HANDS", "2 — Two distinct hands"),
    ("AMBIGUOUS", "3 — Cannot determine"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_csv(path: Path, rows: list[dict[str, str]]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_journal(value: dict[str, Any]) -> None:
    with JOURNAL.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


class ReviewStore:
    def __init__(self) -> None:
        self.queue = sorted(read_csv(QUEUE), key=lambda row: int(row["queue_order"]))
        self.raw = read_csv(RAW_REVIEW)
        self.pairs = read_csv(PAIR_REVIEW)
        self.raw_by_id = {row["item_id"]: row for row in self.raw}
        self.pair_by_id = {row["pair_id"]: row for row in self.pairs}
        if len(self.queue) != 121 or len(self.raw) != 21 or len(self.pairs) != 100:
            raise RuntimeError("P4C3B_REVIEW_PACKAGE_INTEGRITY_FAILURE")
        if len({row["item_id"] for row in self.queue}) != 121:
            raise RuntimeError("P4C3B_DUPLICATE_ITEM_ID")
        for item in self.queue:
            record = self.record(item)
            if record["overlay_sha256"] != item["overlay_sha256"]:
                raise RuntimeError("P4C3B_REVIEW_PACKAGE_INTEGRITY_FAILURE")

    def record(self, item: dict[str, str]) -> dict[str, str]:
        return self.raw_by_id[item["item_id"]] if item["task_type"] == "RAW_A" else self.pair_by_id[item["item_id"]]

    def completed(self) -> int:
        return sum(self.record(item)["reviewer_status"] == "COMPLETE" for item in self.queue)

    def next_incomplete(self) -> dict[str, str] | None:
        return next((item for item in self.queue if self.record(item)["reviewer_status"] != "COMPLETE"), None)

    def save(self, item: dict[str, str], label: str) -> None:
        record = self.record(item)
        if record["reviewer_status"] == "COMPLETE":
            raise RuntimeError("P4C3B_COMPLETED_LABEL_IMMUTABLE")
        overlay = Path(item["overlay_path"])
        if not overlay.is_file() or sha256(overlay) != item["overlay_sha256"] or record["overlay_sha256"] != item["overlay_sha256"]:
            raise RuntimeError("P4C3B_REVIEW_ITEM_IDENTITY_MISMATCH")
        allowed = {value for value, _ in (RAW_LABELS if item["task_type"] == "RAW_A" else PAIR_LABELS)}
        if label not in allowed:
            raise RuntimeError("P4C3B_INVALID_REVIEW_LABEL")
        record["review_label"] = label
        record["reviewer_status"] = "COMPLETE"
        record["reviewed_utc"] = datetime.now(timezone.utc).isoformat()
        atomic_csv(RAW_REVIEW if item["task_type"] == "RAW_A" else PAIR_REVIEW, self.raw if item["task_type"] == "RAW_A" else self.pairs)
        completed = self.completed()
        if completed % 25 == 0 or completed == 121:
            BACKUPS.mkdir(parents=True, exist_ok=True)
            shutil.copy2(RAW_REVIEW, BACKUPS / f"raw_{completed:03d}.csv")
            shutil.copy2(PAIR_REVIEW, BACKUPS / f"pairs_{completed:03d}.csv")

    def last_completed(self) -> tuple[dict[str, str], dict[str, str]] | None:
        completed = [(item, self.record(item)) for item in self.queue if self.record(item)["reviewer_status"] == "COMPLETE"]
        return max(completed, key=lambda pair: pair[1]["reviewed_utc"]) if completed else None

    def undo_last(self) -> bool:
        value = self.last_completed()
        if value is None:
            return False
        item, record = value
        previous = record["review_label"]
        append_journal({"event": "EXPLICIT_UNDO", "item_id": item["item_id"], "previous_label": previous, "timestamp_utc": datetime.now(timezone.utc).isoformat()})
        record["review_label"] = ""
        record["reviewer_status"] = "UNREVIEWED"
        record["reviewed_utc"] = ""
        record["revision_count"] = str(int(record["revision_count"]) + 1)
        record["last_edit_utc"] = datetime.now(timezone.utc).isoformat()
        record["last_edit_reason"] = "EXPLICIT_UNDO_LAST"
        atomic_csv(RAW_REVIEW if item["task_type"] == "RAW_A" else PAIR_REVIEW, self.raw if item["task_type"] == "RAW_A" else self.pairs)
        return True


def status() -> dict[str, Any]:
    store = ReviewStore()
    raw_counts: dict[str, int] = {}
    pair_counts: dict[str, int] = {}
    for row in store.raw:
        if row["reviewer_status"] == "COMPLETE":
            raw_counts[row["review_label"]] = raw_counts.get(row["review_label"], 0) + 1
    for row in store.pairs:
        if row["reviewer_status"] == "COMPLETE":
            pair_counts[row["review_label"]] = pair_counts.get(row["review_label"], 0) + 1
    return {"rows": 121, "completed": store.completed(), "remaining": 121 - store.completed(), "raw_labels": raw_counts, "pair_labels": pair_counts, "passed": True}


def run_gui() -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk

    store = ReviewStore()
    root = tk.Tk()
    root.title("P4-C3B Physical Hand Instance Review")
    root.geometry("1280x900")
    root.minsize(900, 650)
    scale = {"value": 1.0}
    current: dict[str, str] | None = None
    photo: ImageTk.PhotoImage | None = None

    header = ttk.Label(root, font=("Segoe UI", 14, "bold"), anchor="center")
    header.pack(fill="x", padx=12, pady=(10, 3))
    question = ttk.Label(root, font=("Segoe UI", 13, "bold"), anchor="center", justify="center")
    question.pack(fill="x", padx=12, pady=3)
    reminder = ttk.Label(root, text="Judge physical hand instances only. Candidate A/B are not anatomical labels.", foreground="#a32620", font=("Segoe UI", 11, "bold"), anchor="center")
    reminder.pack(fill="x", padx=12, pady=(0, 6))
    image_label = ttk.Label(root, anchor="center")
    image_label.pack(fill="both", expand=True, padx=12, pady=6)
    controls = ttk.Frame(root)
    controls.pack(fill="x", padx=12, pady=8)
    buttons = ttk.Frame(controls)
    buttons.pack(side="top", fill="x")
    utility = ttk.Frame(controls)
    utility.pack(side="top", pady=(10, 0))

    def render() -> None:
        nonlocal photo
        if current is None:
            return
        source = Image.open(current["overlay_path"])
        available_w = max(root.winfo_width() - 50, 700)
        available_h = max(root.winfo_height() - 250, 400)
        factor = min(available_w / source.width, available_h / source.height) * scale["value"]
        factor = max(0.2, min(factor, 3.0))
        resized = source.resize((max(1, int(source.width * factor)), max(1, int(source.height * factor))), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(resized)
        image_label.configure(image=photo)

    def refresh() -> None:
        nonlocal current
        current = store.next_incomplete()
        for child in buttons.winfo_children():
            child.destroy()
        completed = store.completed()
        if current is None:
            header.configure(text="ANNOTATION COMPLETE — 121/121")
            question.configure(text="All physical-instance judgments are safely saved.")
            image_label.configure(image="")
            return
        if sha256(Path(current["overlay_path"])) != current["overlay_sha256"]:
            raise RuntimeError("P4C3B_REVIEW_ITEM_IDENTITY_MISMATCH")
        header.configure(text=f"Review {completed + 1}/121  |  completed {completed}")
        if current["task_type"] == "RAW_A":
            question.configure(text="What physical region does the MAGENTA raw candidate represent?")
            labels = RAW_LABELS
        else:
            question.configure(text="Do candidate A and candidate B represent the same physical hand?")
            labels = PAIR_LABELS
        for index, (value, text) in enumerate(labels):
            ttk.Button(buttons, text=text, command=lambda selected=value: save(selected)).grid(row=0, column=index, padx=5, sticky="ew")
            buttons.columnconfigure(index, weight=1)
        scale["value"] = 1.0
        render()

    def save(label: str) -> None:
        if current is None:
            return
        store.save(current, label)
        refresh()

    def undo() -> None:
        if not messagebox.askyesno("Undo last", "Undo the most recently saved judgment and review it again?"):
            return
        if store.undo_last():
            refresh()

    def zoom(multiplier: float) -> None:
        scale["value"] = max(0.5, min(2.5, scale["value"] * multiplier))
        render()

    ttk.Button(utility, text="Zoom −", command=lambda: zoom(0.8)).pack(side="left", padx=4)
    ttk.Button(utility, text="Zoom +", command=lambda: zoom(1.25)).pack(side="left", padx=4)
    ttk.Button(utility, text="Undo last (U)", command=undo).pack(side="left", padx=16)
    ttk.Button(utility, text="Close", command=root.destroy).pack(side="left", padx=4)

    def shortcut(event: tk.Event) -> None:
        if current is None:
            return
        labels = RAW_LABELS if current["task_type"] == "RAW_A" else PAIR_LABELS
        if event.char in {str(index + 1) for index in range(len(labels))}:
            save(labels[int(event.char) - 1][0])
        elif event.char.lower() == "u":
            undo()
        elif event.char in {"+", "="}:
            zoom(1.25)
        elif event.char == "-":
            zoom(0.8)

    root.bind("<Key>", shortcut)
    root.bind("<Configure>", lambda _event: render() if current is not None else None)
    refresh()
    root.mainloop()
    print(json.dumps(status(), indent=2, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    print(json.dumps(status(), indent=2, sort_keys=True)) if args.status else run_gui()
