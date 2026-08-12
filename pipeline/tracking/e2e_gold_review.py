"""Resumable GUI for blind all-visible-hand box annotation."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import shutil
import sys
from functools import partial
from pathlib import Path
from typing import Any, cast

import cv2

from pipeline.tracking.e2e_gold import INDEX_FIELDS, REVIEW_FIELDS

MIRROR_VALUES = {"mirrored", "unmirrored", "unknown"}
SIDES = {"left", "right", "unknown"}
BOOLEAN_FIELDS = (
    "motion_blur",
    "occlusion",
    "near_face",
    "edge_clipped",
    "partial_visibility",
)
QUALITY_LABELS = {
    "motion_blur": "Hand is blurry",
    "occlusion": "Hand is blocked or overlapping",
    "near_face": "Hand is close to the face",
    "edge_clipped": "Hand touches or leaves the frame edge",
    "partial_visibility": "Only part of a hand is visible",
}


def _read(path: Path, expected: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(expected):
            raise ValueError(f"expected columns {expected}, got {reader.fieldnames}")
        return [dict(row) for row in reader]


def load_run(run_dir: Path) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    reviews = _read(run_dir / "gold_review.csv", REVIEW_FIELDS)
    index_rows = _read(run_dir / "internal_index.csv", INDEX_FIELDS)
    return reviews, {row["sample_id"]: row for row in index_rows}


def parse_boxes(row: dict[str, str]) -> list[dict[str, Any]]:
    if not row["gold_hands_json"]:
        return []
    value = json.loads(row["gold_hands_json"])
    if not isinstance(value, list):
        raise ValueError(f"{row['sample_id']}: gold_hands_json must be a list")
    return value


def completion_error(row: dict[str, str]) -> str | None:
    if row["review_status"] == "quarantine":
        return None
    if row["review_status"] != "accepted":
        return "review status is incomplete"
    if row["source_mirrored"] not in MIRROR_VALUES:
        return "source mirror status is required"
    if row["source_mirrored"] != "unknown" and not row["mirror_evidence"].strip():
        return "known mirror status requires evidence"
    try:
        count = int(row["visible_hand_count"])
    except ValueError:
        return "visible hand count must be 0, 1, or 2"
    if count not in {0, 1, 2}:
        return "visible hand count must be 0, 1, or 2"
    try:
        boxes = parse_boxes(row)
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        return str(error)
    if len(boxes) != count:
        return f"visible count is {count}, but {len(boxes)} boxes were drawn"
    for box in boxes:
        if box.get("anatomical_side") not in SIDES:
            return "every box needs left, right, or unknown identity"
        coordinates = [box.get(key) for key in ("x_min", "y_min", "x_max", "y_max")]
        if not all(isinstance(value, (int, float)) for value in coordinates):
            return "box coordinates must be numeric"
        x1, y1, x2, y2 = cast(tuple[float, float, float, float], tuple(coordinates))
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            return "box coordinates must be valid normalized bounds"
    if any(row[field] not in {"yes", "no"} for field in BOOLEAN_FIELDS):
        return "all quality flags must be yes or no"
    if count == 0 and any(row[field] == "yes" for field in BOOLEAN_FIELDS):
        return "zero-hand rows cannot have hand-quality flags"
    return None


def save_atomic(path: Path, rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in REVIEW_FIELDS} for row in rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def validate_run(rows: list[dict[str, str]], index: dict[str, dict[str, str]]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    video_mirror: dict[str, str] = {}
    for number, row in enumerate(rows, start=1):
        sample_id = row["sample_id"]
        if sample_id in seen:
            errors.append(f"row {number}: duplicate sample_id {sample_id}")
        seen.add(sample_id)
        metadata = index.get(sample_id)
        if metadata is None:
            errors.append(f"row {number}: sample absent from internal index: {sample_id}")
            continue
        for field in ("center_image_path", "context_panel_path"):
            if not Path(metadata[field]).is_file():
                errors.append(f"row {number}: missing {field}: {metadata[field]}")
        if row["review_status"] == "accepted" and completion_error(row) is None:
            mirror_status = row["source_mirrored"]
            video = metadata["video_file"]
            prior = video_mirror.get(video)
            if prior and prior != mirror_status:
                errors.append(
                    f"row {number}: inconsistent mirror status for {video}: "
                    f"{prior} versus {mirror_status}"
                )
            video_mirror[video] = mirror_status
    return errors


def status(rows: list[dict[str, str]]) -> dict[str, int]:
    completed = sum(completion_error(row) is None for row in rows)
    quarantined = sum(row["review_status"] == "quarantine" for row in rows)
    return {
        "total": len(rows),
        "completed": completed,
        "remaining": len(rows) - completed,
        "quarantined": quarantined,
    }


class ReviewApp:
    def __init__(
        self,
        review_path: Path,
        rows: list[dict[str, str]],
        index: dict[str, dict[str, str]],
    ) -> None:
        import tkinter as tk

        self._tk = tk
        self._review_path = review_path
        self._rows = rows
        self._index_rows = index
        self._index = next(
            (i for i, row in enumerate(rows) if completion_error(row) is not None),
            max(len(rows) - 1, 0),
        )
        self._boxes: list[dict[str, Any]] = []
        self._selected: int | None = None
        self._drag_start: tuple[float, float] | None = None
        self._display_origin = (0.0, 0.0)
        self._display_scale = 1.0
        self._source_size = (1, 1)
        self._photo: Any = None
        self._context_photo: Any = None

        self._root = tk.Tk()
        self._root.title("AppHear Hand Visibility Review")
        self._root.configure(bg="#171717")
        self._root.geometry("1280x920")
        self._root.minsize(1000, 760)
        self._count_buttons: dict[int, Any] = {}
        self._advanced_visible = False

        self._progress = tk.Label(
            self._root, fg="white", bg="#171717", font=("Segoe UI", 13, "bold")
        )
        self._progress.pack(pady=(8, 1))
        self._instructions = tk.Label(
            self._root,
            text=(
                "Count every hand with any visible pixels, including blurred, clipped, or "
                "partly blocked hands. Draw its visible extent, mark problems, then save."
            ),
            fg="#d8d8d8",
            bg="#171717",
            font=("Segoe UI", 10),
        )
        self._instructions.pack(pady=(0, 3))
        self._message = tk.Label(
            self._root, fg="#ffd166", bg="#171717", font=("Segoe UI", 11, "bold")
        )
        self._message.pack(pady=(0, 3))

        tk.Label(
            self._root,
            text="Motion context (the frame you label is the middle/third image)",
            fg="#a8a8a8",
            bg="#171717",
            font=("Segoe UI", 9),
        ).pack()
        self._context = tk.Label(self._root, bg="#111111")
        self._context.pack(fill="x", padx=12, pady=(1, 3))
        tk.Label(
            self._root,
            text=(
                "CENTER FRAME - drag a tight rectangle around every visible hand or "
                "visible part of a hand"
            ),
            fg="white",
            bg="#171717",
            font=("Segoe UI", 10, "bold"),
        ).pack()
        self._canvas = tk.Canvas(self._root, bg="#111111", cursor="crosshair", highlightthickness=0)
        self._canvas.pack(fill="both", expand=True, padx=12, pady=3)

        required = tk.Frame(self._root, bg="#252525", padx=8, pady=7)
        required.pack(fill="x", padx=12, pady=(3, 2))
        tk.Label(
            required,
            text="STEP 1 - How many hands are visible in the center frame?",
            fg="white",
            bg="#252525",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left", padx=(0, 8))
        for count, label in ((0, "NO HANDS"), (1, "ONE HAND"), (2, "TWO HANDS")):
            button = tk.Button(
                required,
                text=label,
                command=partial(self._set_count, count),
                bg="#444444",
                fg="white",
                activeforeground="white",
                font=("Segoe UI", 9, "bold"),
                padx=10,
            )
            button.pack(side="left", padx=3)
            self._count_buttons[count] = button
        tk.Button(required, text="Undo last box", command=self._undo).pack(side="right", padx=3)
        tk.Button(required, text="Clear boxes", command=self._clear).pack(side="right", padx=3)

        qualities = tk.Frame(self._root, bg="#171717")
        qualities.pack(fill="x", padx=12, pady=2)
        tk.Label(
            qualities,
            text="Optional: check only problems visible in the center frame:",
            fg="#d8d8d8",
            bg="#171717",
        ).pack(side="left", padx=(0, 5))
        self._quality_vars: dict[str, Any] = {}
        for field in BOOLEAN_FIELDS:
            variable = tk.BooleanVar(value=False)
            self._quality_vars[field] = variable
            tk.Checkbutton(
                qualities,
                text=QUALITY_LABELS[field],
                variable=variable,
                bg="#171717",
                fg="white",
                selectcolor="#444444",
                activebackground="#171717",
                activeforeground="white",
            ).pack(side="left", padx=3)

        advanced_toggle = tk.Frame(self._root, bg="#171717")
        advanced_toggle.pack(fill="x", padx=12)
        tk.Button(
            advanced_toggle,
            text="Show optional mirror / left-right details",
            command=self._toggle_advanced,
        ).pack(side="left")
        self._advanced_summary = tk.Label(
            advanced_toggle,
            text="Defaults: mirror unknown, hand side unknown (safe for detector scoring)",
            fg="#a8a8a8",
            bg="#171717",
        )
        self._advanced_summary.pack(side="left", padx=8)
        self._advanced = tk.Frame(self._root, bg="#252525", padx=8, pady=5)
        tk.Label(
            self._advanced,
            text=(
                "Only change these when independently certain. Left/right means the signer's body."
            ),
            fg="#ffd166",
            bg="#252525",
        ).pack(side="left", padx=3)
        for value in ("unmirrored", "mirrored", "unknown"):
            tk.Button(
                self._advanced,
                text=f"Video: {value}",
                command=partial(self._set_mirror, value),
            ).pack(side="left", padx=2)
        self._evidence = tk.Entry(self._advanced, font=("Segoe UI", 9), width=18)
        self._evidence.pack(side="left", padx=3)
        for side in ("left", "right", "unknown"):
            tk.Button(
                self._advanced,
                text=f"Selected box: {side}",
                command=partial(self._set_side, side),
            ).pack(side="left", padx=2)

        navigation = tk.Frame(self._root, bg="#171717")
        navigation.pack(fill="x", padx=12, pady=(2, 8))
        tk.Button(navigation, text="Previous frame", command=self._previous).pack(side="left")
        tk.Button(
            navigation,
            text="Cannot judge - skip",
            command=self._quarantine,
            bg="#b54708",
            fg="white",
        ).pack(side="left", padx=5)
        self._notes = tk.Entry(navigation, font=("Segoe UI", 9))
        self._notes.pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(navigation, text="Exit and save", command=self._close).pack(side="right", padx=5)
        tk.Button(
            navigation,
            text="SAVE AND NEXT",
            command=self._accept,
            bg="#18794e",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=16,
        ).pack(side="right")

        self._canvas.bind("<ButtonPress-1>", self._start_box)
        self._canvas.bind("<B1-Motion>", self._drag_box)
        self._canvas.bind("<ButtonRelease-1>", self._finish_box)
        self._root.bind("0", lambda _event: self._set_count(0))
        self._root.bind("1", lambda _event: self._set_count(1))
        self._root.bind("2", lambda _event: self._set_count(2))
        self._root.protocol("WM_DELETE_WINDOW", self._close)
        self._show()

    def run(self) -> None:
        self._root.mainloop()

    def _row(self) -> dict[str, str]:
        return self._rows[self._index]

    def _prepare_defaults(self, row: dict[str, str]) -> None:
        if not row["source_mirrored"]:
            row["source_mirrored"] = "unknown"
        if not row["gold_hands_json"]:
            row["gold_hands_json"] = "[]"
        for field in BOOLEAN_FIELDS:
            if not row[field]:
                row[field] = "no"

    def _desired_count(self) -> int | None:
        value = self._row().get("visible_hand_count", "")
        return int(value) if value in {"0", "1", "2"} else None

    def _toggle_advanced(self) -> None:
        if self._advanced_visible:
            self._advanced.pack_forget()
        else:
            self._advanced.pack(
                fill="x", padx=12, pady=2, before=self._advanced.master.winfo_children()[-1]
            )
        self._advanced_visible = not self._advanced_visible

    def _update_guidance(self, message: str | None = None) -> None:
        count = self._desired_count()
        for value, button in self._count_buttons.items():
            selected = value == count
            button.configure(bg="#18794e" if selected else "#444444")
        if message:
            self._message.configure(text=message)
            return
        if count is None:
            text = "STEP 1: Choose NO HANDS, ONE HAND, or TWO HANDS below."
        elif count == 0:
            text = "No boxes needed. Click SAVE AND NEXT."
        elif len(self._boxes) < count:
            remaining = count - len(self._boxes)
            text = f"STEP 2: Draw {remaining} more hand box{'es' if remaining != 1 else ''}."
        else:
            text = "Ready. Check any visible problems, then click SAVE AND NEXT."
        self._message.configure(text=text)

    def _show(self) -> None:
        row = self._row()
        self._prepare_defaults(row)
        metadata = self._index_rows[row["sample_id"]]
        counts = status(self._rows)
        self._progress.configure(
            text=(
                f"Frame {self._index + 1} of {counts['total']}  |  "
                f"saved {counts['completed']}  |  remaining {counts['remaining']}"
            )
        )
        self._boxes = parse_boxes(row)
        self._selected = len(self._boxes) - 1 if self._boxes else None
        self._evidence.delete(0, self._tk.END)
        self._evidence.insert(0, row.get("mirror_evidence", ""))
        self._notes.delete(0, self._tk.END)
        self._notes.insert(0, row.get("notes", ""))
        for field, variable in self._quality_vars.items():
            variable.set(row.get(field) == "yes")
        self._render_context(metadata["context_panel_path"])
        self._render_center(metadata["center_image_path"])
        self._advanced_summary.configure(
            text=(
                f"Optional values: video {row['source_mirrored']}; "
                "new boxes default to side unknown"
            )
        )
        self._update_guidance()

    def _render_context(self, path: str) -> None:
        image = cv2.imread(path, cv2.IMREAD_COLOR)
        if image is None:
            raise OSError(f"cannot read context panel: {path}")
        scale = min(1180 / image.shape[1], 140 / image.shape[0])
        image = cv2.resize(
            image,
            (round(image.shape[1] * scale), round(image.shape[0] * scale)),
            interpolation=cv2.INTER_AREA,
        )
        self._context_photo = self._photo_image(image)
        self._context.configure(image=self._context_photo)

    def _render_center(self, path: str) -> None:
        image = cv2.imread(path, cv2.IMREAD_COLOR)
        if image is None:
            raise OSError(f"cannot read center image: {path}")
        height, width = image.shape[:2]
        self._source_size = (width, height)
        canvas_width = max(self._canvas.winfo_width(), 900)
        canvas_height = max(self._canvas.winfo_height(), 420)
        scale = min(canvas_width / width, canvas_height / height)
        shown = cv2.resize(
            image,
            (round(width * scale), round(height * scale)),
            interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_NEAREST,
        )
        self._display_scale = scale
        self._display_origin = (
            (canvas_width - shown.shape[1]) / 2,
            (canvas_height - shown.shape[0]) / 2,
        )
        self._photo = self._photo_image(shown)
        self._canvas.delete("all")
        self._canvas.create_image(
            self._display_origin[0],
            self._display_origin[1],
            image=self._photo,
            anchor="nw",
        )
        for index, box in enumerate(self._boxes):
            x1 = self._display_origin[0] + box["x_min"] * shown.shape[1]
            y1 = self._display_origin[1] + box["y_min"] * shown.shape[0]
            x2 = self._display_origin[0] + box["x_max"] * shown.shape[1]
            y2 = self._display_origin[1] + box["y_max"] * shown.shape[0]
            color = "#ffd166" if index == self._selected else "#33dd88"
            self._canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=3)
            self._canvas.create_text(
                x1 + 4,
                y1 + 4,
                text=f"{index + 1}: {box['anatomical_side']}",
                fill=color,
                anchor="nw",
                font=("Segoe UI", 11, "bold"),
            )

    def _photo_image(self, image: Any) -> Any:
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise OSError("could not encode review image")
        data = base64.b64encode(encoded.tobytes()).decode("ascii")
        return self._tk.PhotoImage(data=data)

    def _set_mirror(self, value: str) -> None:
        self._row()["source_mirrored"] = value
        self._advanced_summary.configure(
            text=f"Optional values: video {value}; new boxes default to side unknown"
        )

    def _set_count(self, count: int) -> None:
        self._row()["visible_hand_count"] = str(count)
        if count == 0:
            for variable in self._quality_vars.values():
                variable.set(False)
        if count < len(self._boxes):
            self._boxes = self._boxes[:count]
            self._selected = len(self._boxes) - 1 if self._boxes else None
            self._render_center(self._index_rows[self._row()["sample_id"]]["center_image_path"])
        self._update_guidance()

    def _set_side(self, side: str) -> None:
        if self._selected is None:
            self._update_guidance("Draw a box before assigning optional left/right identity.")
            return
        self._boxes[self._selected]["anatomical_side"] = side
        self._render_center(self._index_rows[self._row()["sample_id"]]["center_image_path"])
        self._update_guidance(f"Selected box identity set to {side}.")

    def _start_box(self, event: Any) -> None:
        desired = self._desired_count()
        if desired is None:
            self._update_guidance("Choose the visible-hand count before drawing.")
            return
        if len(self._boxes) >= desired:
            self._update_guidance(
                "You already drew the selected number of boxes. Use Undo if needed."
            )
            return
        self._drag_start = (event.x, event.y)

    def _drag_box(self, event: Any) -> None:
        if self._drag_start is None:
            return
        self._canvas.delete("preview_box")
        self._canvas.create_rectangle(
            self._drag_start[0],
            self._drag_start[1],
            event.x,
            event.y,
            outline="#ffd166",
            width=3,
            dash=(6, 3),
            tags="preview_box",
        )

    def _finish_box(self, event: Any) -> None:
        desired = self._desired_count()
        self._canvas.delete("preview_box")
        if self._drag_start is None or desired is None or len(self._boxes) >= desired:
            self._drag_start = None
            return
        ox, oy = self._display_origin
        width, height = self._source_size
        x1 = (min(self._drag_start[0], event.x) - ox) / (width * self._display_scale)
        y1 = (min(self._drag_start[1], event.y) - oy) / (height * self._display_scale)
        x2 = (max(self._drag_start[0], event.x) - ox) / (width * self._display_scale)
        y2 = (max(self._drag_start[1], event.y) - oy) / (height * self._display_scale)
        self._drag_start = None
        x1, y1, x2, y2 = (max(0.0, min(1.0, value)) for value in (x1, y1, x2, y2))
        if x2 - x1 < 0.01 or y2 - y1 < 0.01:
            self._update_guidance("That box was too small. Drag around the whole visible hand.")
            return
        self._boxes.append(
            {
                "x_min": round(x1, 6),
                "y_min": round(y1, 6),
                "x_max": round(x2, 6),
                "y_max": round(y2, 6),
                "anatomical_side": "unknown",
            }
        )
        self._selected = len(self._boxes) - 1
        self._render_center(self._index_rows[self._row()["sample_id"]]["center_image_path"])
        self._update_guidance()

    def _undo(self) -> None:
        if self._boxes:
            self._boxes.pop()
            self._selected = len(self._boxes) - 1 if self._boxes else None
            self._render_center(self._index_rows[self._row()["sample_id"]]["center_image_path"])
        self._update_guidance()

    def _clear(self) -> None:
        self._boxes = []
        self._selected = None
        self._render_center(self._index_rows[self._row()["sample_id"]]["center_image_path"])
        self._update_guidance()

    def _capture(self, review_status: str) -> str | None:
        row = self._row()
        row["review_status"] = review_status
        row["mirror_evidence"] = self._evidence.get().strip()
        row["gold_hands_json"] = json.dumps(self._boxes, separators=(",", ":"))
        has_visible_hand = self._desired_count() in {1, 2}
        for field, variable in self._quality_vars.items():
            row[field] = "yes" if has_visible_hand and variable.get() else "no"
        row["notes"] = self._notes.get().strip()
        error = completion_error(row)
        if error and review_status == "accepted":
            row["review_status"] = ""
        return error

    def _accept(self) -> None:
        error = self._capture("accepted")
        if error:
            self._message.configure(text=f"Cannot accept: {error}")
            return
        save_atomic(self._review_path, self._rows)
        self._advance()

    def _quarantine(self) -> None:
        self._capture("quarantine")
        save_atomic(self._review_path, self._rows)
        self._advance()

    def _advance(self) -> None:
        next_index = next(
            (
                i
                for i in range(self._index + 1, len(self._rows))
                if completion_error(self._rows[i]) is not None
            ),
            None,
        )
        if next_index is None:
            next_index = next(
                (i for i, row in enumerate(self._rows) if completion_error(row) is not None),
                None,
            )
        if next_index is None:
            self._message.configure(text="Audit complete and saved")
            return
        self._index = next_index
        self._show()

    def _previous(self) -> None:
        self._capture(self._row().get("review_status", ""))
        save_atomic(self._review_path, self._rows)
        if self._index > 0:
            self._index -= 1
            self._show()

    def _close(self) -> None:
        self._capture(self._row().get("review_status", ""))
        save_atomic(self._review_path, self._rows)
        self._root.destroy()


def check(run_dir: Path) -> int:
    rows, index = load_run(run_dir)
    errors = validate_run(rows, index)
    counts = status(rows)
    print(
        f"[tracking/e2e-gold-review] rows={counts['total']} "
        f"completed={counts['completed']} remaining={counts['remaining']} "
        f"quarantined={counts['quarantined']} errors={len(errors)}"
    )
    for error in errors[:20]:
        print(f"[tracking/e2e-gold-review] ERROR: {error}", file=sys.stderr)
    return 2 if errors or counts["remaining"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Review E2e all-hand-box gold audit")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        rows, index = load_run(args.run_dir)
        if args.check:
            return check(args.run_dir)
        errors = validate_run(rows, index)
        if errors:
            for error in errors[:20]:
                print(f"[tracking/e2e-gold-review] ERROR: {error}", file=sys.stderr)
            return 2
        review_path = args.run_dir / "gold_review.csv"
        backup = args.run_dir / "gold_review.pre_review_backup.csv"
        if not backup.exists():
            shutil.copy2(review_path, backup)
        ReviewApp(review_path, rows, index).run()
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as error:
        print(f"[tracking/e2e-gold-review] ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
