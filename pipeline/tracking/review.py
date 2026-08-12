"""Resumable staged reviewer for E2c paired A/B crop panels."""

from __future__ import annotations

import argparse
import base64
import csv
import os
import shutil
import sys
from functools import partial
from pathlib import Path
from typing import Any

import cv2

AUDIT_FIELDS = (
    "base_id",
    "panel_path",
    "source_blur",
    "a_quality",
    "b_quality",
    "notes",
)
SOURCE_VALUES = {"clear", "blur"}
QUALITY = {
    "1": ("usable", "#18794e"),
    "2": ("missing", "#b42318"),
    "3": ("clipped", "#b54708"),
    "4": ("stale", "#b54708"),
    "5": ("wrong_hand", "#b42318"),
    "6": ("low_detail", "#b54708"),
    "7": ("other", "#6b4f9b"),
}


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(AUDIT_FIELDS):
            raise ValueError(f"expected columns {AUDIT_FIELDS}, got {reader.fieldnames}")
        return [dict(row) for row in reader]


def is_complete(row: dict[str, str]) -> bool:
    valid_quality = {value[0] for value in QUALITY.values()}
    return (
        row["source_blur"] in SOURCE_VALUES
        and row["a_quality"] in valid_quality
        and row["b_quality"] in valid_quality
    )


def current_stage(row: dict[str, str]) -> str:
    if row["source_blur"] not in SOURCE_VALUES:
        return "source"
    valid_quality = {value[0] for value in QUALITY.values()}
    if row["a_quality"] not in valid_quality:
        return "a"
    if row["b_quality"] not in valid_quality:
        return "b"
    return "source"


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    errors = []
    seen = set()
    for number, row in enumerate(rows, start=1):
        base_id = row["base_id"]
        if not base_id:
            errors.append(f"row {number}: empty base_id")
        elif base_id in seen:
            errors.append(f"row {number}: duplicate base_id {base_id}")
        seen.add(base_id)
        if not Path(row["panel_path"]).is_file():
            errors.append(f"row {number}: panel missing: {row['panel_path']}")
    return errors


def save_rows_atomic(path: Path, rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(
            {field: row.get(field, "") for field in AUDIT_FIELDS} for row in rows
        )
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


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
        self._stage = current_stage(rows[self._index]) if rows else "source"
        self._photo: Any = None
        self._root = tk.Tk()
        self._root.title("AppHear E2c Paired Tracking Review")
        self._root.configure(bg="#171717")
        self._root.geometry("1280x860")
        self._root.minsize(950, 680)

        self._progress = tk.Label(
            self._root, fg="white", bg="#171717", font=("Segoe UI", 13, "bold")
        )
        self._progress.pack(pady=(10, 4))
        self._stage_label = tk.Label(
            self._root, fg="#ffd166", bg="#171717", font=("Segoe UI", 12, "bold")
        )
        self._stage_label.pack(pady=(0, 4))
        self._image = tk.Label(self._root, bg="#111111")
        self._image.pack(fill="both", expand=True, padx=16, pady=4)
        self._values = tk.Label(
            self._root, fg="white", bg="#171717", font=("Consolas", 10)
        )
        self._values.pack(pady=3)
        self._notes = tk.Entry(self._root, font=("Segoe UI", 10))
        self._notes.pack(fill="x", padx=16, pady=(2, 6))

        source_controls = tk.Frame(self._root, bg="#171717")
        source_controls.pack(fill="x", padx=16)
        tk.Button(
            source_controls,
            text="C: Source clear",
            command=partial(self._mark_source, "clear"),
            bg="#18794e",
            fg="white",
        ).pack(side="left", fill="x", expand=True, padx=3)
        tk.Button(
            source_controls,
            text="M: Source motion blur",
            command=partial(self._mark_source, "blur"),
            bg="#b54708",
            fg="white",
        ).pack(side="left", fill="x", expand=True, padx=3)

        quality_controls = tk.Frame(self._root, bg="#171717")
        quality_controls.pack(fill="x", padx=16, pady=5)
        for column, (key, (value, color)) in enumerate(QUALITY.items()):
            tk.Button(
                quality_controls,
                text=f"{key}: {value.replace('_', ' ')}",
                command=partial(self._mark_quality, value),
                bg=color,
                fg="white",
            ).grid(row=0, column=column, sticky="ew", padx=2)
            quality_controls.grid_columnconfigure(column, weight=1)

        navigation = tk.Frame(self._root, bg="#171717")
        navigation.pack(fill="x", padx=16, pady=(0, 10))
        tk.Button(navigation, text="Previous (P)", command=self._previous).pack(
            side="left"
        )
        tk.Button(navigation, text="Exit and save (Esc)", command=self._close).pack(
            side="right"
        )
        self._root.bind("c", lambda _event: self._mark_source("clear"))
        self._root.bind("m", lambda _event: self._mark_source("blur"))
        for key, (value, _color) in QUALITY.items():
            self._root.bind(key, partial(self._quality_event, value))
        self._root.bind("p", lambda _event: self._previous())
        self._root.bind("<Escape>", lambda _event: self._close())
        self._root.protocol("WM_DELETE_WINDOW", self._close)
        self._show()

    def run(self) -> None:
        self._root.mainloop()

    def _show(self) -> None:
        if not self._rows:
            return
        row = self._rows[self._index]
        status = audit_status(self._rows)
        self._progress.configure(
            text=(
                f"Panel {self._index + 1}/{status['total']} | "
                f"completed {status['completed']} | remaining {status['remaining']}"
            )
        )
        stage_text = {
            "source": "STEP 1: judge source frame (C clear / M motion blur)",
            "a": "STEP 2: judge crop A (keys 1-7)",
            "b": "STEP 3: judge crop B (keys 1-7)",
        }[self._stage]
        self._stage_label.configure(text=stage_text)
        self._values.configure(
            text=(
                f"source={row['source_blur'] or '-'}  "
                f"A={row['a_quality'] or '-'}  B={row['b_quality'] or '-'}"
            )
        )
        self._notes.delete(0, self._tk.END)
        self._notes.insert(0, row.get("notes", ""))
        image = cv2.imread(row["panel_path"], cv2.IMREAD_COLOR)
        if image is None:
            raise OSError(f"cannot read panel: {row['panel_path']}")
        max_width = max(self._root.winfo_width() - 60, 850)
        max_height = max(self._root.winfo_height() - 260, 420)
        scale = min(max_width / image.shape[1], max_height / image.shape[0], 2.0)
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

    def _mark_source(self, value: str) -> None:
        if self._stage != "source":
            return
        self._rows[self._index]["source_blur"] = value
        self._stage = "a"
        self._show()

    def _mark_quality(self, value: str) -> None:
        if self._stage not in {"a", "b"}:
            return
        row = self._rows[self._index]
        row[f"{self._stage}_quality"] = value
        if self._stage == "a":
            self._stage = "b"
            self._show()
            return
        row["notes"] = self._notes.get().strip()
        save_rows_atomic(self._template_path, self._rows)
        self._advance()

    def _quality_event(self, value: str, _event: object) -> None:
        self._mark_quality(value)

    def _advance(self) -> None:
        next_index = next(
            (
                index
                for index in range(self._index + 1, len(self._rows))
                if not is_complete(self._rows[index])
            ),
            None,
        )
        if next_index is None:
            next_index = next(
                (index for index, row in enumerate(self._rows) if not is_complete(row)),
                None,
            )
        if next_index is None:
            self._progress.configure(text=f"Complete: {len(self._rows)}/{len(self._rows)}")
            self._stage_label.configure(text="All decisions saved")
            self._image.configure(image="")
            return
        self._index = next_index
        self._stage = current_stage(self._rows[self._index])
        self._show()

    def _previous(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._stage = "source"
            self._show()

    def _close(self) -> None:
        if self._rows:
            self._rows[self._index]["notes"] = self._notes.get().strip()
        save_rows_atomic(self._template_path, self._rows)
        self._root.destroy()


def check(template_path: Path) -> int:
    rows = load_rows(template_path)
    errors = validate_rows(rows)
    status = audit_status(rows)
    print(
        f"[tracking/review] rows={status['total']} completed={status['completed']} "
        f"remaining={status['remaining']} missing_panels={len(errors)}"
    )
    for error in errors[:20]:
        print(f"[tracking/review] ERROR: {error}", file=sys.stderr)
    return 2 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AppHear E2c paired tracking reviewer")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    template = args.run_dir / "audit_template.csv"
    if not template.is_file():
        print(f"[tracking/review] ERROR: missing audit template: {template}", file=sys.stderr)
        return 2
    if args.check:
        return check(template)
    rows = load_rows(template)
    errors = validate_rows(rows)
    if errors:
        for error in errors[:20]:
            print(f"[tracking/review] ERROR: {error}", file=sys.stderr)
        return 2
    backup = args.run_dir / "audit_template.pre_review_backup.csv"
    if not backup.exists():
        shutil.copy2(template, backup)
    ReviewApp(template, rows).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
