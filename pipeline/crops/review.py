"""Local, resumable human-review window for an E2 blinded audit template."""

from __future__ import annotations

import argparse
import base64
import csv
import os
import shutil
import sys
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

import cv2

AUDIT_FIELDS = (
    "crop_id",
    "panel_path",
    "visible_hand",
    "usable",
    "failure_reason",
    "notes",
)


@dataclass(frozen=True)
class Decision:
    label: str
    key: str
    visible_hand: str
    usable: str
    failure_reason: str
    color: str


DECISIONS = (
    Decision("Hand not visible", "0", "no", "", "", "#555555"),
    Decision("Crop usable", "1", "yes", "yes", "", "#18794e"),
    Decision("Missing crop", "2", "yes", "no", "missing_roi", "#b42318"),
    Decision("Clipped", "3", "yes", "no", "clipped", "#b54708"),
    Decision("Motion blur", "4", "yes", "no", "motion_blur", "#b54708"),
    Decision("Stale crop", "5", "yes", "no", "stale_roi", "#b54708"),
    Decision("Wrong hand", "6", "yes", "no", "wrong_hand", "#b42318"),
    Decision("Low detail", "7", "yes", "no", "low_detail", "#b54708"),
    Decision("Other failure", "8", "yes", "no", "other", "#6b4f9b"),
)
DECISION_BY_KEY = {decision.key: decision for decision in DECISIONS}


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != list(AUDIT_FIELDS):
            raise ValueError(f"expected columns {AUDIT_FIELDS}, got {reader.fieldnames}")
        return [dict(row) for row in reader]


def is_complete(row: dict[str, str]) -> bool:
    visible = row["visible_hand"].strip().lower()
    usable = row["usable"].strip().lower()
    return visible == "no" or (visible == "yes" and usable in {"yes", "no"})


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        crop_id = row["crop_id"]
        if not crop_id:
            errors.append(f"row {index}: empty crop_id")
        elif crop_id in seen:
            errors.append(f"row {index}: duplicate crop_id {crop_id}")
        seen.add(crop_id)
        if not Path(row["panel_path"]).is_file():
            errors.append(f"row {index}: panel missing: {row['panel_path']}")
    return errors


def save_rows_atomic(path: Path, rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in AUDIT_FIELDS} for row in rows)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temporary, path)


def apply_decision(row: dict[str, str], decision: Decision, notes: str) -> None:
    row["visible_hand"] = decision.visible_hand
    row["usable"] = decision.usable
    row["failure_reason"] = decision.failure_reason
    row["notes"] = notes.strip()


def audit_status(rows: list[dict[str, str]]) -> dict[str, int]:
    completed = sum(is_complete(row) for row in rows)
    return {"total": len(rows), "completed": completed, "remaining": len(rows) - completed}


class ReviewApp:
    def __init__(self, template_path: Path, rows: list[dict[str, str]]) -> None:
        import tkinter as tk

        self._tk = tk
        self._template_path = template_path
        self._rows = rows
        self._index = next(
            (index for index, row in enumerate(rows) if not is_complete(row)),
            max(len(rows) - 1, 0),
        )
        self._photo: Any = None

        self._root = tk.Tk()
        self._root.title("AppHear E2 Blinded Crop Review")
        self._root.configure(bg="#171717")
        self._root.geometry("1180x820")
        self._root.minsize(900, 650)

        self._progress = tk.Label(
            self._root,
            fg="white",
            bg="#171717",
            font=("Segoe UI", 13, "bold"),
        )
        self._progress.pack(pady=(12, 6))

        self._image = tk.Label(self._root, bg="#111111")
        self._image.pack(fill="both", expand=True, padx=18, pady=6)

        self._notes = tk.Entry(self._root, font=("Segoe UI", 11))
        self._notes.pack(fill="x", padx=18, pady=(4, 8))
        self._notes.insert(0, "")

        controls = tk.Frame(self._root, bg="#171717")
        controls.pack(fill="x", padx=18, pady=(0, 8))
        for column, decision in enumerate(DECISIONS):
            button = tk.Button(
                controls,
                text=f"{decision.key}: {decision.label}",
                command=partial(self._mark, decision),
                bg=decision.color,
                fg="white",
                activeforeground="white",
                font=("Segoe UI", 9, "bold"),
                padx=7,
                pady=8,
            )
            button.grid(row=column // 5, column=column % 5, sticky="ew", padx=3, pady=3)
        for column in range(5):
            controls.grid_columnconfigure(column, weight=1)

        navigation = tk.Frame(self._root, bg="#171717")
        navigation.pack(fill="x", padx=18, pady=(0, 12))
        tk.Button(navigation, text="Previous (P)", command=self._previous).pack(side="left")
        tk.Button(navigation, text="Exit and save (Esc)", command=self._close).pack(side="right")

        for key, decision in DECISION_BY_KEY.items():
            self._root.bind(key, partial(self._mark_from_event, decision))
        self._root.bind("p", self._previous_from_event)
        self._root.bind("<Escape>", self._close_from_event)
        self._root.protocol("WM_DELETE_WINDOW", self._close)
        self._show()

    def run(self) -> None:
        self._root.mainloop()

    def _show(self) -> None:
        if not self._rows:
            self._progress.configure(text="No audit rows")
            return
        row = self._rows[self._index]
        status = audit_status(self._rows)
        self._progress.configure(
            text=(
                f"Panel {self._index + 1}/{status['total']}  |  "
                f"completed {status['completed']}  |  remaining {status['remaining']}"
            )
        )
        self._notes.delete(0, self._tk.END)
        self._notes.insert(0, row.get("notes", ""))
        image = cv2.imread(row["panel_path"], cv2.IMREAD_COLOR)
        if image is None:
            raise OSError(f"cannot read panel: {row['panel_path']}")
        max_width = max(self._root.winfo_width() - 70, 800)
        max_height = max(self._root.winfo_height() - 260, 420)
        scale = min(max_width / image.shape[1], max_height / image.shape[0], 2.0)
        if scale != 1.0:
            image = cv2.resize(
                image,
                (round(image.shape[1] * scale), round(image.shape[0] * scale)),
                interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_NEAREST,
            )
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise OSError(f"cannot encode panel: {row['panel_path']}")
        data = base64.b64encode(encoded.tobytes()).decode("ascii")
        self._photo = self._tk.PhotoImage(data=data)
        self._image.configure(image=self._photo)

    def _mark(self, decision: Decision) -> None:
        apply_decision(self._rows[self._index], decision, self._notes.get())
        save_rows_atomic(self._template_path, self._rows)
        next_unfinished = next(
            (
                index
                for index in range(self._index + 1, len(self._rows))
                if not is_complete(self._rows[index])
            ),
            None,
        )
        if next_unfinished is None:
            next_unfinished = next(
                (index for index, row in enumerate(self._rows) if not is_complete(row)),
                None,
            )
        if next_unfinished is None:
            self._progress.configure(text=f"Complete: {len(self._rows)}/{len(self._rows)} saved")
            self._image.configure(image="")
            return
        self._index = next_unfinished
        self._show()

    def _mark_from_event(self, decision: Decision, _event: object) -> None:
        self._mark(decision)

    def _previous(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._show()

    def _previous_from_event(self, _event: object) -> None:
        self._previous()

    def _close(self) -> None:
        save_rows_atomic(self._template_path, self._rows)
        self._root.destroy()

    def _close_from_event(self, _event: object) -> None:
        self._close()


def check(template_path: Path) -> int:
    rows = load_rows(template_path)
    errors = validate_rows(rows)
    status = audit_status(rows)
    print(
        f"[crops/review] rows={status['total']} completed={status['completed']} "
        f"remaining={status['remaining']} missing_panels={len(errors)}"
    )
    for error in errors[:20]:
        print(f"[crops/review] ERROR: {error}", file=sys.stderr)
    return 2 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AppHear E2 blinded crop-review window")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--check", action="store_true", help="validate inputs without opening a GUI"
    )
    args = parser.parse_args()
    template_path = args.run_dir / "audit_template.csv"
    if not template_path.is_file():
        print(f"[crops/review] ERROR: audit template missing: {template_path}", file=sys.stderr)
        return 2
    if args.check:
        return check(template_path)

    rows = load_rows(template_path)
    errors = validate_rows(rows)
    if errors:
        for error in errors[:20]:
            print(f"[crops/review] ERROR: {error}", file=sys.stderr)
        return 2
    backup = args.run_dir / "audit_template.pre_review_backup.csv"
    if not backup.exists():
        shutil.copy2(template_path, backup)
    ReviewApp(template_path, rows).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
