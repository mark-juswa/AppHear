"""Prepare and run the remaining blinded P4-GT1 Pass-1 visibility review."""

from __future__ import annotations

import argparse
import hashlib
import json
import tkinter as tk
from collections import Counter
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from PIL import Image, ImageTk

from eval.runtime_diagnostics.p4c2r_truth_review import (
    ALL_FIELDS,
    UNREVIEWED,
    CompletedRowImmutable,
    DisplayedIdentity,
    ReviewIntegrityError,
    ReviewStore,
    atomic_csv,
    atomic_json,
    atomic_text,
    dataset_hash,
    read_csv,
    review_row_id,
    sha256,
    verify_r0,
)

ROOT = Path(__file__).resolve().parents[2]
REPLACEMENT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement"
V1 = REPLACEMENT / "p4a2_fresh_evidence_repair_v2_01/frozen_truth/P4A2_FRESH_HUMAN_TRUTH_V1.csv"
C2R = REPLACEMENT / "p4c2r_proposal_ownership_truth_repair_01"
C2R_QUEUE = C2R / "p4c2r_truth_review_queue.csv"
C2R_REVIEW = C2R / "p4c2r_truth_review.csv"
C2R_SELECTION = C2R / "p4c2r_truth_selection_manifest.csv"
C2R_RESULT = C2R / "p4c2r_result.json"
OUT = REPLACEMENT / "p4gt1_eligibility_ground_truth_rebuild_01"
STANDARD = OUT / "P4GT1_VISIBILITY_ANNOTATION_STANDARD.md"
QUEUE = OUT / "p4gt1_pass1_review_queue.csv"
REVIEW = OUT / "p4gt1_pass1_review.csv"
REUSED = OUT / "p4gt1_reused_p4c2r_pass1.csv"
BLINDING = OUT / "p4gt1_pass1_blinding_manifest.json"
PROVENANCE = OUT / "p4gt1_pass1_provenance.json"
PREPARE_RESULT = OUT / "p4gt1_pass1_prepare_result.json"
REPORT = OUT / "P4GT1_ELIGIBILITY_GROUND_TRUTH_REBUILD_RESULT.md"
HASH_MANIFEST = OUT / "p4gt1_pass1_artifact_hash_manifest.json"
EXPECTED_DATASET = "7819c59123b4dacdafac190c81754deb766d6ed6087a2b58535490d45a6a3edd"
EXPECTED_ANNOTATION = "1b9f34412ba885e397019742bf29027987ce58668d099fd3914e48ab3206774b"
EXPECTED_C2R_REVIEW = "e1c9ade5f165aa929e37813deb2c80b95405448b0583774a5d7a5ac5efc128b2"
ORDER_SEED = "P4GT1_REMAINING_PASS1_ORDER_V1_20260825"
UI_VERSION = "P4GT1_PASS1_VISIBILITY_UI_V1.0.0"


STANDARD_TEXT = """# P4-GT1 Visibility Annotation Standard

**Frozen before construction of the remaining Pass-1 review queue.**

## Target

Judge the physical visibility of the **target signer's anatomical left and right hands** in the
exact, original, non-mirrored RGB frame. Visibility is independent of whether the target signer is
signing, resting, or transitioning. Another person's hand does not count.

`REST + visible hand = VISIBLE`; `SIGNING + visible hand = VISIBLE`; and
`TRANSITION + visible hand = VISIBLE`. Activity state never determines visibility.

## Side labels

- **YES:** Visually identifiable hand anatomy belonging to that anatomical side is genuinely
  visible. This includes a full hand, palm, fingers, a clearly identifiable partial hand, a hand at
  rest or in transition, or a partly occluded hand with enough identifiable anatomy remaining.
- **NO:** No visually identifiable hand belonging to that anatomical side is present. This includes
  a hand completely outside the frame or occluded, an arm/forearm with no identifiable hand, and a
  background/body region with no visible hand.
- **UNCERTAIN:** The RGB frame cannot support a reliable YES/NO judgment, including extreme blur,
  tiny ambiguous pixels, severe occlusion, or uncertain anatomical ownership. Never force an
  ambiguous slot to YES or NO.

LEFT and RIGHT always mean the target signer's anatomical left/right—not screen position. Review
images must never be mirrored.

## Independent optional state

State is separately recorded as `REST`, `SIGNING`, `TRANSITION`, or `UNCERTAIN`. It must never
automatically set or override either visibility label.

## Blinding

The reviewer may see only the original full RGB frame, anonymous frame ID, progress, and review
controls. V1 labels, previous disagreements, model outputs, DWPose, WiLoR, crops, E2/R1,
sequence/gloss, and selection reasons remain hidden.
"""


class GT1Store(ReviewStore):
    def __init__(self, path: Path = REVIEW, *, verify_images: bool = True) -> None:
        super().__init__(path, verify_images=verify_images)
        self.journal = path.parent / "p4gt1_pass1_completed_label_edit_journal.jsonl"
        self.backups = path.parent / "pass1_review_backups"


def displayed(row: dict[str, str]) -> DisplayedIdentity:
    return DisplayedIdentity(
        row["review_row_id"],
        row["source_annotation_row_id"],
        row["sequence_id"],
        row["frame_index"],
        row["image_sha256"],
        row["image_path"],
    )


def verify_sources() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    truth = read_csv(V1)
    if sha256(V1) != EXPECTED_ANNOTATION or dataset_hash(truth) != EXPECTED_DATASET:
        raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
    verify_r0()
    if sha256(C2R_REVIEW) != EXPECTED_C2R_REVIEW:
        raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
    result = json.loads(C2R_RESULT.read_text(encoding="utf-8"))
    if result.get("status") != "TRUTH_V1_BROADER_REAUDIT_REQUIRED":
        raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
    queue = read_csv(C2R_QUEUE)
    reviews = read_csv(C2R_REVIEW)
    selection = read_csv(C2R_SELECTION)
    if not (len(queue) == len(reviews) == len(selection) == 148):
        raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
    by_queue = {row["review_row_id"]: row for row in queue}
    by_selection = {row["review_row_id"]: row for row in selection}
    if len(by_queue) != 148 or len(by_selection) != 148:
        raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
    for row in reviews:
        identifier = row["review_row_id"]
        if row["reviewer_status"] != "COMPLETE" or identifier not in by_queue:
            raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
        if identifier not in by_selection or row["revision_count"] != "0":
            raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
        for field in (
            "source_annotation_row_id",
            "sequence_id",
            "frame_index",
            "image_sha256",
            "image_path",
        ):
            if row[field] != by_queue[identifier][field]:
                raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
            if row[field] != by_selection[identifier][field]:
                raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
        image = Path(row["image_path"])
        if not image.is_file() or sha256(image) != row["image_sha256"]:
            raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
    return truth, reviews


def prepare() -> dict[str, Any]:
    if REVIEW.exists() and any(row["reviewer_status"] == "COMPLETE" for row in read_csv(REVIEW)):
        raise ReviewIntegrityError("P4GT1 Pass-1 review already started; package is immutable")
    OUT.mkdir(parents=True, exist_ok=True)
    truth, reused = verify_sources()
    atomic_text(STANDARD, STANDARD_TEXT)
    standard_hash = sha256(STANDARD)

    truth_by_id = {row["annotation_row_id"]: row for row in truth}
    reused_ids = {row["source_annotation_row_id"] for row in reused}
    if len(truth_by_id) != 458 or len(reused_ids) != 148 or not reused_ids <= set(truth_by_id):
        raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")

    reusable_rows: list[dict[str, str]] = []
    for row in reused:
        source = truth_by_id[row["source_annotation_row_id"]]
        reusable_rows.append(
            {
                "annotation_row_id": source["annotation_row_id"],
                "sequence_id": source["sequence_id"],
                "signer_id": source["signer_id"],
                "frame_index": source["frame_index"],
                "image_sha256": source["image_sha256"],
                "visible_left": row["visible_left"],
                "visible_right": row["visible_right"],
                "frame_state": row["frame_state"],
                "reviewed_utc": row["reviewed_utc"],
                "pass1_source": "REUSED_P4C2R_148",
                "p4c2r_review_row_id": row["review_row_id"],
            }
        )
    atomic_csv(REUSED, reusable_rows, list(reusable_rows[0]))

    remaining = [row for row in truth if row["annotation_row_id"] not in reused_ids]
    if len(remaining) != 310:
        raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
    randomized = sorted(
        remaining,
        key=lambda row: hashlib.sha256(
            f"{ORDER_SEED}|{row['annotation_row_id']}|{row['image_sha256']}".encode()
        ).hexdigest(),
    )
    queue_rows: list[dict[str, str]] = []
    for order, source in enumerate(randomized):
        image = Path(source["review_image_path"])
        if not image.is_file() or sha256(image) != source["image_sha256"]:
            raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
        queue_rows.append(
            {
                "review_row_id": review_row_id(
                    source["sequence_id"], source["frame_index"], source["image_sha256"]
                ),
                "source_annotation_row_id": source["annotation_row_id"],
                "sequence_id": source["sequence_id"],
                "frame_index": source["frame_index"],
                "image_sha256": source["image_sha256"],
                "image_path": str(image),
                "queue_order": str(order),
            }
        )
    if len({row["review_row_id"] for row in queue_rows}) != 310:
        raise ReviewIntegrityError("P4GT1_SOURCE_INTEGRITY_FAILURE")
    atomic_csv(QUEUE, queue_rows, list(queue_rows[0]))
    atomic_csv(REVIEW, [{**row, **UNREVIEWED} for row in queue_rows], ALL_FIELDS)
    atomic_json(
        BLINDING,
        {
            "status": "FROZEN_BEFORE_REMAINING_PASS1_REVIEW",
            "ui_version": UI_VERSION,
            "review_order_seed": ORDER_SEED,
            "standard_sha256": standard_hash,
            "queue_sha256": sha256(QUEUE),
            "review_sha256_at_freeze": sha256(REVIEW),
            "reviewer_sees": [
                "original non-mirrored full RGB frame",
                "anonymous frame ID",
                "progress",
                "zoom and review controls",
            ],
            "hidden_from_reviewer": [
                "V1 labels",
                "model outputs",
                "DWPose",
                "WiLoR",
                "crops",
                "E2/R1",
                "sequence/gloss",
                "selection reason",
                "previous disagreement status",
            ],
        },
    )
    result = {
        "status": "P4GT1_PASS1_REVIEW_READY",
        "v1_hashes_verified": True,
        "p4c2r_148_reusable_as_gt1_pass1": True,
        "reusable_prior_review_count": 148,
        "remaining_review_count": 310,
        "total_expected_pass1_frames": 458,
        "unique_remaining_sequences": len({row["sequence_id"] for row in remaining}),
        "unique_remaining_signers": len({row["signer_id"] for row in remaining}),
        "annotation_standard_sha256": standard_hash,
        "queue_sha256": sha256(QUEUE),
        "review_sha256_at_freeze": sha256(REVIEW),
    }
    atomic_json(PREPARE_RESULT, result)
    atomic_json(
        PROVENANCE,
        {
            **result,
            "v1_dataset_sha256": EXPECTED_DATASET,
            "v1_annotation_sha256": EXPECTED_ANNOTATION,
            "p4c2r_review_sha256": EXPECTED_C2R_REVIEW,
            "p4c2r_queue_sha256": sha256(C2R_QUEUE),
            "p4c2r_selection_sha256": sha256(C2R_SELECTION),
            "reuse_compatibility": {
                "full_frame_rgb": True,
                "blinded_from_v1_and_models": True,
                "anatomical_left_right_independently_recorded": True,
                "yes_no_uncertain_compatible": True,
                "activity_state_independent": True,
                "material_incompatibility_found": False,
            },
        },
    )
    atomic_text(
        REPORT,
        """# P4-GT1 Eligibility Ground-Truth Rebuild Result

## Status

**`P4GT1_PASS1_REVIEW_READY` — human review required.**

Immutable V1 and the completed P4-C2R evidence were verified. The 148 P4-C2R judgments are
compatible with the frozen P4-GT1 standard and are reused as Pass-1 labels; they are not being
reviewed again. The remaining 310 unique source frames form a new blinded, randomized Pass-1
queue. Together they cover all 458 governed frames exactly once.

The reviewer sees only the original non-mirrored full RGB frame, anonymous ID/progress, and review
controls. The target is physical visibility of the target signer's anatomical hands. Activity
state is independent. Other people's hands do not count.

No Pass-2 queue, provisional full Pass-1 truth, V2 truth, proposal rescore, historical rescore,
model inference, training, threshold tuning, Android, recognition, P4-C2B, P4-D, or P4-B work has
started.
""",
    )
    tracked = [STANDARD, QUEUE, REVIEW, REUSED, BLINDING, PROVENANCE, PREPARE_RESULT, REPORT]
    atomic_json(
        HASH_MANIFEST,
        {
            "status": "FROZEN_BEFORE_REMAINING_PASS1_REVIEW",
            "artifacts": {
                str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in tracked
            },
        },
    )
    return result


class ReviewApp:
    def __init__(self, root: tk.Tk, store: GT1Store) -> None:
        self.root = root
        self.store = store
        self.current = store.next_unreviewed()
        self.photo: ImageTk.PhotoImage | None = None
        self.zoom = 1.0
        self.edit_mode = False
        self.edit_reason = ""
        self.state = tk.StringVar(value="UNCERTAIN")
        self.left = tk.StringVar(value="UNCERTAIN")
        self.right = tk.StringVar(value="UNCERTAIN")
        self.note = tk.StringVar(value="")
        root.title("P4-GT1 Blinded Target-Signer Hand Visibility Review")
        root.geometry("1220x850")
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._build()
        self.render()

    def _build(self) -> None:
        image_panel = ttk.Frame(self.root)
        image_panel.pack(side="left", fill="both", expand=True, padx=12, pady=12)
        self.image_label = ttk.Label(image_panel, anchor="center")
        self.image_label.pack(fill="both", expand=True)
        zoom_bar = ttk.Frame(image_panel)
        zoom_bar.pack()
        ttk.Button(zoom_bar, text="− Zoom", command=lambda: self.set_zoom(-0.25)).pack(
            side="left", padx=4
        )
        ttk.Button(zoom_bar, text="Fit", command=self.fit_zoom).pack(side="left", padx=4)
        ttk.Button(zoom_bar, text="+ Zoom", command=lambda: self.set_zoom(0.25)).pack(
            side="left", padx=4
        )
        panel = ttk.Frame(self.root, padding=18, width=420)
        panel.pack(side="right", fill="y")
        self.progress = ttk.Label(panel, font=("Segoe UI", 12, "bold"))
        self.progress.pack(anchor="w", pady=(0, 12))
        ttk.Label(
            panel,
            text=(
                "Judge the TARGET SIGNER only. LEFT/RIGHT are the person's anatomical sides, "
                "not screen position. The image is not mirrored."
            ),
            foreground="#a6261d",
            wraplength=390,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", pady=(0, 10))
        ttk.Label(
            panel,
            text=(
                "Rest/signing/transition never decides visibility. Another person's hand "
                "does not count. Use UNCERTAIN when RGB cannot support a reliable answer."
            ),
            wraplength=390,
        ).pack(anchor="w", pady=(0, 12))
        ttk.Label(
            panel,
            text="0 No hands   1 LEFT only   2 RIGHT only   3 Both   4 Unsure",
            font=("Consolas", 11, "bold"),
        ).pack(anchor="w", pady=(0, 8))
        for text, left, right in (
            ("0  No target-signer hands", "NO", "NO"),
            ("1  Anatomical LEFT only", "YES", "NO"),
            ("2  Anatomical RIGHT only", "NO", "YES"),
            ("3  Both hands", "YES", "YES"),
            ("4  Unsure", "UNCERTAIN", "UNCERTAIN"),
        ):
            ttk.Button(
                panel,
                text=text,
                command=lambda left_value=left, right_value=right: self.quick_save(
                    left_value, right_value
                ),
            ).pack(fill="x", pady=2)
        ttk.Separator(panel).pack(fill="x", pady=12)
        ttk.Label(panel, text="Optional independent state (R/S/T/U)").pack(anchor="w")
        for label, value in (
            ("Rest", "REST"),
            ("Signing", "SIGNING"),
            ("Transition", "TRANSITION"),
            ("Uncertain", "UNCERTAIN"),
        ):
            ttk.Radiobutton(panel, text=label, variable=self.state, value=value).pack(anchor="w")
        ttk.Separator(panel).pack(fill="x", pady=12)
        for title, variable in (("Anatomical LEFT", self.left), ("Anatomical RIGHT", self.right)):
            row = ttk.Frame(panel)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=title, width=19).pack(side="left")
            ttk.Combobox(
                row,
                textvariable=variable,
                values=("YES", "NO", "UNCERTAIN"),
                state="readonly",
                width=14,
            ).pack(side="left")
        ttk.Entry(panel, textvariable=self.note).pack(fill="x", pady=(8, 3))
        ttk.Button(panel, text="Save detailed answer (Enter)", command=self.save_detailed).pack(
            fill="x"
        )
        ttk.Button(panel, text="Edit a completed label…", command=self.start_edit).pack(
            fill="x", pady=(14, 2)
        )
        for key, action in {
            "0": lambda: self.quick_save("NO", "NO"),
            "1": lambda: self.quick_save("YES", "NO"),
            "2": lambda: self.quick_save("NO", "YES"),
            "3": lambda: self.quick_save("YES", "YES"),
            "4": lambda: self.quick_save("UNCERTAIN", "UNCERTAIN"),
            "r": lambda: self.state.set("REST"),
            "s": lambda: self.state.set("SIGNING"),
            "t": lambda: self.state.set("TRANSITION"),
            "u": lambda: self.state.set("UNCERTAIN"),
        }.items():
            self.root.bind(key, lambda _event, fn=action: fn())
        self.root.bind("<Return>", lambda _event: self.save_detailed())

    def render(self) -> None:
        if self.current is None:
            self.progress.configure(text="ANNOTATION_COMPLETE")
            self.image_label.configure(image="", text="All 310 remaining frames are complete.")
            return
        complete = sum(row["reviewer_status"] == "COMPLETE" for row in self.store.rows)
        self.progress.configure(
            text=(
                f"Frame {complete + 1}/310 | completed {complete} | "
                f"ID {self.current['review_row_id']}"
            )
        )
        image = Image.open(self.current["image_path"]).convert("RGB")
        fit = min(760 / image.width, 740 / image.height)
        scale = fit * self.zoom
        size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        image = image.resize(size, Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image)
        self.image_label.configure(image=self.photo, text="")
        self.left.set(self.current.get("visible_left") or "UNCERTAIN")
        self.right.set(self.current.get("visible_right") or "UNCERTAIN")
        self.state.set(self.current.get("frame_state") or "UNCERTAIN")
        self.note.set(self.current.get("reviewer_note") or "")

    def set_zoom(self, delta: float) -> None:
        self.zoom = max(0.5, min(3.0, self.zoom + delta))
        self.render()

    def fit_zoom(self) -> None:
        self.zoom = 1.0
        self.render()

    def label(self, left: str, right: str) -> dict[str, str]:
        return {
            "visible_left": left,
            "visible_right": right,
            "frame_state": self.state.get(),
            "reviewer_note": self.note.get().strip(),
        }

    def quick_save(self, left: str, right: str) -> None:
        self.left.set(left)
        self.right.set(right)
        self.save(self.label(left, right))

    def save_detailed(self) -> None:
        self.save(self.label(self.left.get(), self.right.get()))

    def save(self, label: dict[str, str]) -> None:
        if self.current is None:
            return
        try:
            if self.edit_mode:
                self.store.edit_completed(
                    displayed(self.current), label, reason=self.edit_reason, confirmed=True
                )
                self.edit_mode = False
                self.edit_reason = ""
                self.current = self.store.next_unreviewed()
            else:
                self.current = self.store.save_new(displayed(self.current), label)
            self.state.set("UNCERTAIN")
            self.note.set("")
            self.render()
        except ReviewIntegrityError as error:
            messagebox.showerror("Review integrity stop", str(error))

    def start_edit(self) -> None:
        identifier = simpledialog.askstring("Edit completed label", "Enter anonymous frame ID:")
        if not identifier:
            return
        reason = simpledialog.askstring("Required reason", "Why must this label change?")
        if not reason:
            return
        self.store.rescan()
        try:
            row = self.store.by_id(identifier.strip())
            if row["reviewer_status"] != "COMPLETE":
                raise ReviewIntegrityError("That row is not completed")
            if not messagebox.askyesno(
                "Confirm explicit edit", "Load this completed label for a journaled edit?"
            ):
                return
            self.current = row
            self.edit_mode = True
            self.edit_reason = reason
            self.render()
        except (ReviewIntegrityError, CompletedRowImmutable) as error:
            messagebox.showerror("Cannot edit", str(error))

    def close(self) -> None:
        try:
            self.store.snapshot("session_close")
        finally:
            self.root.destroy()


def check() -> dict[str, Any]:
    store = GT1Store()
    counts = Counter(row["reviewer_status"] for row in store.rows)
    result = {
        "rows": len(store.rows),
        "completed": counts["COMPLETE"],
        "remaining": counts["UNREVIEWED"],
        "label_patterns": dict(
            sorted(
                Counter(
                    f"L={row['visible_left']}|R={row['visible_right']}|STATE={row['frame_state']}"
                    for row in store.rows
                    if row["reviewer_status"] == "COMPLETE"
                ).items()
            )
        ),
        "errors": [],
        "passed": counts["COMPLETE"] == 310,
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "review", "check"))
    args = parser.parse_args()
    if args.command == "prepare":
        print(json.dumps(prepare(), indent=2, sort_keys=True))
    elif args.command == "check":
        check()
    else:
        root = tk.Tk()
        ReviewApp(root, GT1Store())
        root.mainloop()


if __name__ == "__main__":
    main()
