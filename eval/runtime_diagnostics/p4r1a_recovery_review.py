"""Minimal immutable review UI for the 18 P4-R1A recovery cases."""

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
OUT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4r1a_rtmpose_hand5_targeted_recovery_01"
QUEUE = OUT / "p4r1a_recovery_review_queue.csv"
REVIEW = OUT / "p4r1a_recovery_review.csv"
BACKUPS = OUT / "review_backups"
JOURNAL = OUT / "p4r1a_recovery_review_edit_journal.jsonl"
ORDER_SEED = "P4R1A_RECOVERY_REVIEW_ORDER_V1_20260825"
LABELS = [
    ("MISSING_HAND_RECOVERED", "1 — Missing physical hand recovered"),
    ("DUPLICATE_EXISTING_HAND", "2 — Hand already represented by DWPose"),
    ("FALSE_REGION_OR_NO_OUTPUT", "3 — No real missing-hand recovery"),
    ("AMBIGUOUS", "4 — Cannot determine reliably"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_path(value: str) -> Path:
    """Resolve frozen WSL mount paths when the reviewer runs on Windows."""
    normalized = value.replace("\\", "/")
    if os.name == "nt" and normalized.startswith("/mnt/") and len(normalized) > 6:
        drive = normalized[5].upper()
        return Path(f"{drive}:/{normalized[7:]}")
    return Path(value)


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
        self.queue = sorted(
            read_csv(QUEUE),
            key=lambda row: hashlib.sha256(f"{ORDER_SEED}|{row['residual_id']}".encode()).hexdigest(),
        )
        self.review = read_csv(REVIEW)
        self.by_id = {row["residual_id"]: row for row in self.review}
        if len(self.queue) != 18 or len(self.review) != 18 or len(self.by_id) != 18:
            raise RuntimeError("P4R1A_REVIEW_PACKAGE_INTEGRITY_FAILURE")
        if len({row["residual_id"] for row in self.queue}) != 18:
            raise RuntimeError("P4R1A_DUPLICATE_REVIEW_ID")
        for item in self.queue:
            record = self.by_id.get(item["residual_id"])
            overlay = local_path(item["overlay_path"])
            if (
                record is None
                or record["overlay_sha256"] != item["overlay_sha256"]
                or not overlay.is_file()
                or sha256(overlay) != item["overlay_sha256"]
            ):
                raise RuntimeError("P4R1A_REVIEW_PACKAGE_INTEGRITY_FAILURE")

    def completed(self) -> int:
        return sum(row["reviewer_status"] == "COMPLETE" for row in self.review)

    def next_incomplete(self) -> dict[str, str] | None:
        return next((item for item in self.queue if self.by_id[item["residual_id"]]["reviewer_status"] != "COMPLETE"), None)

    def save(self, item: dict[str, str], label: str, note: str = "") -> None:
        record = self.by_id[item["residual_id"]]
        if record["reviewer_status"] == "COMPLETE":
            raise RuntimeError("P4R1A_COMPLETED_LABEL_IMMUTABLE")
        overlay = local_path(item["overlay_path"])
        if sha256(overlay) != item["overlay_sha256"] or record["overlay_sha256"] != item["overlay_sha256"]:
            raise RuntimeError("P4R1A_REVIEW_ITEM_IDENTITY_MISMATCH")
        if label not in {value for value, _ in LABELS}:
            raise RuntimeError("P4R1A_INVALID_REVIEW_LABEL")
        record.update(
            {
                "review_label": label,
                "reviewer_status": "COMPLETE",
                "reviewed_utc": datetime.now(timezone.utc).isoformat(),
                "reviewer_note": note.strip(),
            }
        )
        atomic_csv(REVIEW, self.review)
        completed = self.completed()
        if completed % 6 == 0 or completed == 18:
            BACKUPS.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REVIEW, BACKUPS / f"p4r1a_recovery_review_{completed:02d}.csv")

    def undo_last(self) -> bool:
        completed = [row for row in self.review if row["reviewer_status"] == "COMPLETE"]
        if not completed:
            return False
        record = max(completed, key=lambda row: row["reviewed_utc"])
        append_journal(
            {
                "event": "EXPLICIT_UNDO",
                "residual_id": record["residual_id"],
                "previous_label": record["review_label"],
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
        record.update(
            {
                "review_label": "",
                "reviewer_status": "UNREVIEWED",
                "reviewed_utc": "",
                "revision_count": str(int(record["revision_count"]) + 1),
                "last_edit_utc": datetime.now(timezone.utc).isoformat(),
                "last_edit_reason": "EXPLICIT_UNDO_LAST",
                "reviewer_note": "",
            }
        )
        atomic_csv(REVIEW, self.review)
        return True


def status() -> dict[str, Any]:
    store = ReviewStore()
    counts: dict[str, int] = {}
    for row in store.review:
        if row["reviewer_status"] == "COMPLETE":
            counts[row["review_label"]] = counts.get(row["review_label"], 0) + 1
    return {
        "rows": 18,
        "completed": store.completed(),
        "remaining": 18 - store.completed(),
        "counts": counts,
        "errors": [],
        "passed": True,
    }


def run_gui() -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk

    store = ReviewStore()
    root = tk.Tk()
    root.title("P4-R1A Missing-Hand Recovery Review")
    root.geometry("1180x860")
    root.minsize(900, 650)
    current: dict[str, str] | None = None
    photo: ImageTk.PhotoImage | None = None
    zoom = {"value": 1.0}

    header = ttk.Label(root, font=("Segoe UI", 14, "bold"), anchor="center")
    header.pack(fill="x", padx=12, pady=(10, 3))
    question = ttk.Label(
        root,
        text="Does any RECOVERY output correspond to the real physical hand missing from the existing DWPose result?",
        font=("Segoe UI", 12, "bold"),
        anchor="center",
        justify="center",
    )
    question.pack(fill="x", padx=12, pady=3)
    reminder = ttk.Label(
        root,
        text="Judge physical hand instances, not anatomical slot names. If there is no recovery output, choose 3.",
        foreground="#a32620",
        font=("Segoe UI", 10, "bold"),
        anchor="center",
    )
    reminder.pack(fill="x", padx=12, pady=(0, 5))
    image_label = ttk.Label(root, anchor="center")
    image_label.pack(fill="both", expand=True, padx=12, pady=5)
    controls = ttk.Frame(root)
    controls.pack(fill="x", padx=12, pady=8)
    button_row = ttk.Frame(controls)
    button_row.pack(fill="x")
    note_var = tk.StringVar()
    ttk.Label(controls, text="Optional note:").pack(anchor="w", pady=(8, 0))
    note_entry = ttk.Entry(controls, textvariable=note_var)
    note_entry.pack(fill="x")
    utility = ttk.Frame(controls)
    utility.pack(pady=(8, 0))

    def render() -> None:
        nonlocal photo
        if current is None:
            return
        source = Image.open(local_path(current["overlay_path"]))
        width = max(root.winfo_width() - 40, 700)
        height = max(root.winfo_height() - 260, 380)
        factor = min(width / source.width, height / source.height) * zoom["value"]
        factor = max(0.3, min(factor, 3.0))
        resized = source.resize((max(1, int(source.width * factor)), max(1, int(source.height * factor))), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(resized)
        image_label.configure(image=photo)

    def refresh() -> None:
        nonlocal current
        current = store.next_incomplete()
        completed = store.completed()
        note_var.set("")
        if current is None:
            header.configure(text="ANNOTATION COMPLETE — 18/18")
            question.configure(text="All recovery judgments are safely saved. Close this window.")
            image_label.configure(image="")
            return
        if sha256(local_path(current["overlay_path"])) != current["overlay_sha256"]:
            raise RuntimeError("P4R1A_REVIEW_ITEM_IDENTITY_MISMATCH")
        header.configure(text=f"Recovery case {completed + 1}/18  |  completed {completed}  |  outputs shown: {current['accepted_recovery_outputs']}")
        zoom["value"] = 1.0
        render()

    def save(label: str) -> None:
        if current is None:
            return
        store.save(current, label, note_var.get())
        refresh()

    def undo() -> None:
        if messagebox.askyesno("Undo last", "Undo the most recently saved judgment and review it again?") and store.undo_last():
            refresh()

    for index, (value, text) in enumerate(LABELS):
        ttk.Button(button_row, text=text, command=lambda selected=value: save(selected)).grid(row=0, column=index, padx=4, sticky="ew")
        button_row.columnconfigure(index, weight=1)
    ttk.Button(utility, text="Zoom −", command=lambda: change_zoom(0.8)).pack(side="left", padx=4)
    ttk.Button(utility, text="Zoom +", command=lambda: change_zoom(1.25)).pack(side="left", padx=4)
    ttk.Button(utility, text="Undo last (U)", command=undo).pack(side="left", padx=12)
    ttk.Button(utility, text="Close", command=root.destroy).pack(side="left", padx=4)

    def change_zoom(multiplier: float) -> None:
        zoom["value"] = max(0.5, min(2.5, zoom["value"] * multiplier))
        render()

    def shortcut(event: tk.Event) -> None:
        if current is None:
            return
        if event.char in {"1", "2", "3", "4"}:
            save(LABELS[int(event.char) - 1][0])
        elif event.char.lower() == "u":
            undo()
        elif event.char in {"+", "="}:
            change_zoom(1.25)
        elif event.char == "-":
            change_zoom(0.8)

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
