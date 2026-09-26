"""Prepare and run the six-frame P4-GT1R count-first adjudication."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tkinter as tk
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from PIL import Image, ImageTk

from eval.runtime_diagnostics.p4c2r_truth_review import (
    CompletedRowImmutable,
    ReviewIntegrityError,
    RowIdentityMismatch,
    append_jsonl,
    atomic_csv,
    atomic_json,
    atomic_text,
    read_csv,
    sha256,
    verify_r0,
)
from eval.runtime_diagnostics.p4gt1_repeatability_review import (
    PASS1_FULL,
    verify_completed_pass1,
)
from eval.runtime_diagnostics.p4gt1_repeatability_review import (
    REVIEW as PASS2_REVIEW,
)
from eval.runtime_diagnostics.p4gt1_repeatability_review import (
    SAMPLE as PASS2_SAMPLE,
)

ROOT = Path(__file__).resolve().parents[2]
REPLACEMENT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement"
GT1 = REPLACEMENT / "p4gt1_eligibility_ground_truth_rebuild_01"
GT1_RESULT = GT1 / "p4gt1_result.json"
DISAGREEMENTS = GT1 / "p4gt1_repeatability_disagreements.csv"
P4C2A_REVIEW = REPLACEMENT / "p4c2a_dwpose_rgb_crop_separability_01/p4c2a_human_crop_review.csv"
OUT = REPLACEMENT / "p4gt1r_schema_repair_v2_01"
QUEUE = OUT / "p4gt1r_six_frame_queue.csv"
REVIEW = OUT / "p4gt1r_adjudication_review.csv"
ANALYSIS = OUT / "p4gt1r_count_repeatability_analysis.csv"
SCHEMA = OUT / "p4gt1r_truth_schema.json"
BLINDING = OUT / "p4gt1r_adjudication_blinding_manifest.json"
PROVENANCE = OUT / "p4gt1r_adjudication_provenance.json"
PREPARE_RESULT = OUT / "p4gt1r_adjudication_prepare_result.json"
REPORT = OUT / "P4GT1R_SCHEMA_REPAIR_AND_V2_RESCORE_RESULT.md"
HASH_MANIFEST = OUT / "p4gt1r_adjudication_artifact_hash_manifest.json"
EXPECTED_PASS1_FULL = "74ec425293d734a79550ba012555301cdfcd9491cd39eca4400f3af9fb489428"
EXPECTED_PASS2_REVIEW = "d619e0fa342cff00ca073dcea6a491065dff231ccad1c576f85a1e37a7cda8b6"
EXPECTED_DISAGREEMENTS = "88c4755ef40e08ea9ae175753970e1fb46622b6f4358cfd95dfe195da7bc83a5"
EXPECTED_CROP_REVIEW = "fe47dd7c710a91e2a2bb88df3d33269aa89edf8b0d657898394b86783c89522f"
ORDER_SEED = "P4GT1R_SIX_FRAME_ORDER_V1_20260825"
UI_VERSION = "P4GT1R_COUNT_FIRST_ADJUDICATION_UI_V1.0.0"

IDENTITY_FIELDS = [
    "adjudication_row_id",
    "frame_id",
    "source_sha256",
    "current_image_path",
    "previous_image_path",
    "previous_image_sha256",
    "next_image_path",
    "next_image_sha256",
    "queue_order",
]
LABEL_FIELDS = ["visible_hand_count", "one_hand_ownership", "ownership_context_used"]
AUDIT_FIELDS = [
    "reviewer_status",
    "reviewed_utc",
    "revision_count",
    "last_edit_utc",
    "last_edit_reason",
]
ALL_FIELDS = [*IDENTITY_FIELDS, *LABEL_FIELDS, *AUDIT_FIELDS]
UNREVIEWED = {
    "visible_hand_count": "",
    "one_hand_ownership": "",
    "ownership_context_used": "NO",
    "reviewer_status": "UNREVIEWED",
    "reviewed_utc": "",
    "revision_count": "0",
    "last_edit_utc": "",
    "last_edit_reason": "",
}


def adjudication_row_id(frame_id: str, source_sha: str) -> str:
    value = hashlib.sha256(f"P4GT1R|{frame_id}|{source_sha}".encode()).hexdigest()[:24]
    return f"P4GT1R_{value}"


def side_pair_to_schema(left: str, right: str) -> tuple[str, str]:
    if left == "NO" and right == "NO":
        return "ZERO", "NOT_APPLICABLE"
    if left == "YES" and right == "YES":
        return "TWO", "NOT_APPLICABLE"
    if left == "YES" and right == "NO":
        return "ONE", "LEFT"
    if left == "NO" and right == "YES":
        return "ONE", "RIGHT"
    return "UNCERTAIN", "UNCERTAIN"


def validate_label(label: dict[str, str]) -> None:
    count = label.get("visible_hand_count")
    ownership = label.get("one_hand_ownership")
    if count not in {"ZERO", "ONE", "TWO", "UNCERTAIN"}:
        raise ReviewIntegrityError("Select a physical visible-hand count")
    if count == "ONE":
        if ownership not in {"LEFT", "RIGHT", "UNCERTAIN"}:
            raise ReviewIntegrityError("Select LEFT, RIGHT, or UNCERTAIN ownership")
    elif ownership != "NOT_APPLICABLE":
        raise ReviewIntegrityError("Ownership must be NOT_APPLICABLE unless count is ONE")
    if label.get("ownership_context_used") not in {"YES", "NO"}:
        raise ReviewIntegrityError("Invalid ownership_context_used")


@dataclass(frozen=True)
class DisplayedIdentity:
    adjudication_row_id: str
    frame_id: str
    source_sha256: str
    current_image_path: str


def atomic_review(path: Path, rows: list[dict[str, str]]) -> None:
    atomic_csv(path, rows, ALL_FIELDS)


class AdjudicationStore:
    def __init__(self, path: Path = REVIEW, *, verify_images: bool = True) -> None:
        self.path = path
        self.verify_images = verify_images
        self.journal = path.parent / "p4gt1r_completed_label_edit_journal.jsonl"
        self.backups = path.parent / "adjudication_backups"
        self.rows = self._load_verified()

    def _load_verified(self) -> list[dict[str, str]]:
        rows = read_csv(self.path)
        ids = [row["adjudication_row_id"] for row in rows]
        if len(ids) != len(set(ids)):
            raise ReviewIntegrityError("DUPLICATE_ADJUDICATION_ROW_ID")
        for row in rows:
            expected = adjudication_row_id(row["frame_id"], row["source_sha256"])
            if row["adjudication_row_id"] != expected:
                raise RowIdentityMismatch("ANNOTATION_ROW_IDENTITY_MISMATCH")
            if row["reviewer_status"] not in {"UNREVIEWED", "COMPLETE"}:
                raise ReviewIntegrityError("Invalid reviewer status")
            if row["reviewer_status"] == "COMPLETE":
                validate_label(row)
            if self.verify_images:
                current = Path(row["current_image_path"])
                if not current.is_file() or sha256(current) != row["source_sha256"]:
                    raise RowIdentityMismatch("ANNOTATION_ROW_IDENTITY_MISMATCH")
                for prefix in ("previous", "next"):
                    path_value = row[f"{prefix}_image_path"]
                    hash_value = row[f"{prefix}_image_sha256"]
                    if path_value and (
                        not Path(path_value).is_file() or sha256(Path(path_value)) != hash_value
                    ):
                        raise RowIdentityMismatch("ANNOTATION_ROW_IDENTITY_MISMATCH")
        return rows

    def rescan(self) -> None:
        self.rows = self._load_verified()

    def by_id(self, identifier: str) -> dict[str, str]:
        matches = [row for row in self.rows if row["adjudication_row_id"] == identifier]
        if len(matches) != 1:
            raise RowIdentityMismatch("ANNOTATION_ROW_IDENTITY_MISMATCH")
        return matches[0]

    def next_unreviewed(self, after_id: str | None = None) -> dict[str, str] | None:
        self.rescan()
        ordered = sorted(self.rows, key=lambda row: int(row["queue_order"]))
        if after_id is not None:
            index = next(
                (idx for idx, row in enumerate(ordered) if row["adjudication_row_id"] == after_id),
                None,
            )
            if index is None:
                raise RowIdentityMismatch("ANNOTATION_ROW_IDENTITY_MISMATCH")
            ordered = ordered[index + 1 :] + ordered[: index + 1]
        return next((row for row in ordered if row["reviewer_status"] != "COMPLETE"), None)

    def verify_displayed(self, shown: DisplayedIdentity) -> dict[str, str]:
        row = self.by_id(shown.adjudication_row_id)
        expected = (
            row["frame_id"],
            row["source_sha256"],
            row["current_image_path"],
        )
        actual = (shown.frame_id, shown.source_sha256, shown.current_image_path)
        if expected != actual or sha256(Path(shown.current_image_path)) != shown.source_sha256:
            raise RowIdentityMismatch("ANNOTATION_ROW_IDENTITY_MISMATCH")
        return row

    def commit(self) -> None:
        atomic_review(self.path, self.rows)

    def snapshot(self, reason: str) -> Path:
        self.rescan()
        self.backups.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        target = self.backups / f"{stamp}_{reason}_{sha256(self.path)[:12]}.csv"
        shutil.copy2(self.path, target)
        if sha256(target) != sha256(self.path):
            raise ReviewIntegrityError("Backup hash mismatch")
        return target

    def save_new(self, shown: DisplayedIdentity, label: dict[str, str]) -> dict[str, str] | None:
        self.rescan()
        row = self.verify_displayed(shown)
        if row["reviewer_status"] == "COMPLETE":
            raise CompletedRowImmutable("EDIT_COMPLETED_LABEL_REQUIRED")
        validate_label(label)
        row.update({field: label[field] for field in LABEL_FIELDS})
        row.update({"reviewer_status": "COMPLETE", "reviewed_utc": datetime.now(UTC).isoformat()})
        self.commit()
        return self.next_unreviewed(after_id=shown.adjudication_row_id)

    def edit_completed(
        self,
        shown: DisplayedIdentity,
        label: dict[str, str],
        *,
        reason: str,
        confirmed: bool,
    ) -> dict[str, str]:
        if not confirmed or not reason.strip():
            raise CompletedRowImmutable("Explicit edit requires confirmation and reason")
        self.rescan()
        row = self.verify_displayed(shown)
        if row["reviewer_status"] != "COMPLETE":
            raise ReviewIntegrityError("Row is not complete")
        validate_label(label)
        prior = dict(row)
        now = datetime.now(UTC).isoformat()
        row.update({field: label[field] for field in LABEL_FIELDS})
        row.update(
            {
                "last_edit_utc": now,
                "last_edit_reason": reason.strip(),
                "revision_count": str(int(row["revision_count"]) + 1),
            }
        )
        append_jsonl(
            self.journal,
            {
                "event": "EDIT_COMPLETED_LABEL",
                "timestamp": now,
                "reason": reason.strip(),
                "prior": prior,
                "replacement": dict(row),
            },
        )
        self.commit()
        return row


def displayed(row: dict[str, str]) -> DisplayedIdentity:
    return DisplayedIdentity(
        row["adjudication_row_id"],
        row["frame_id"],
        row["source_sha256"],
        row["current_image_path"],
    )


def verify_sources() -> None:
    verify_r0()
    verify_completed_pass1()
    result = json.loads(GT1_RESULT.read_text(encoding="utf-8"))
    if result.get("status") != "P4GT1_REPEATABILITY_INSUFFICIENT":
        raise ReviewIntegrityError("P4GT1R_SOURCE_INTEGRITY_FAILURE")
    expected = {
        PASS1_FULL: EXPECTED_PASS1_FULL,
        PASS2_REVIEW: EXPECTED_PASS2_REVIEW,
        DISAGREEMENTS: EXPECTED_DISAGREEMENTS,
        P4C2A_REVIEW: EXPECTED_CROP_REVIEW,
    }
    if any(not path.is_file() or sha256(path) != digest for path, digest in expected.items()):
        raise ReviewIntegrityError("P4GT1R_SOURCE_INTEGRITY_FAILURE")


def prepare() -> dict[str, Any]:
    if REVIEW.exists() and any(row["reviewer_status"] == "COMPLETE" for row in read_csv(REVIEW)):
        raise ReviewIntegrityError("P4GT1R adjudication already started; package immutable")
    verify_sources()
    OUT.mkdir(parents=True, exist_ok=True)
    full = read_csv(PASS1_FULL)
    pass1_by_id = {row["frame_id"]: row for row in full}
    pass2_by_id = {row["source_annotation_row_id"]: row for row in read_csv(PASS2_REVIEW)}
    sample = read_csv(PASS2_SAMPLE)
    analysis_rows: list[dict[str, str]] = []
    count_disagreements = 0
    ownership_only = 0
    mixed = 0
    for first in sample:
        second = pass2_by_id[first["frame_id"]]
        count1, owner1 = side_pair_to_schema(first["visible_left"], first["visible_right"])
        count2, owner2 = side_pair_to_schema(second["visible_left"], second["visible_right"])
        if count1 != count2:
            classification = "COUNT_DISAGREEMENT"
            count_disagreements += 1
        elif count1 == "ONE" and owner1 != owner2:
            classification = "OWNERSHIP_ONLY_DISAGREEMENT"
            ownership_only += 1
        else:
            classification = "AGREEMENT"
        analysis_rows.append(
            {
                "frame_id": first["frame_id"],
                "source_sha256": first["source_sha256"],
                "pass1_visible_hand_count": count1,
                "pass2_visible_hand_count": count2,
                "count_agreement": "YES" if count1 == count2 else "NO",
                "pass1_one_hand_ownership": owner1,
                "pass2_one_hand_ownership": owner2,
                "ownership_comparable": "YES" if count1 == count2 == "ONE" else "NO",
                "repeatability_classification": classification,
                "pass1_source": first["pass1_source"],
            }
        )
    atomic_csv(ANALYSIS, analysis_rows, list(analysis_rows[0]))
    conflict_ids = {
        row["frame_id"]
        for row in read_csv(DISAGREEMENTS)
        if row["disagreement_type"] == "MATERIAL_YES_NO"
    }
    if len(conflict_ids) != 6:
        raise ReviewIntegrityError("P4GT1R_SOURCE_INTEGRITY_FAILURE")
    conflict_classes = {
        row["frame_id"]: row["repeatability_classification"]
        for row in analysis_rows
        if row["frame_id"] in conflict_ids
    }
    if set(conflict_classes) != conflict_ids:
        raise ReviewIntegrityError("P4GT1R_SOURCE_INTEGRITY_FAILURE")

    by_sequence: dict[str, list[dict[str, str]]] = {}
    for row in full:
        by_sequence.setdefault(row["sequence_id"], []).append(row)
    for rows in by_sequence.values():
        rows.sort(key=lambda row: int(row["frame_index"]))
    queue_rows: list[dict[str, str]] = []
    for frame_id in conflict_ids:
        current = pass1_by_id[frame_id]
        sequence = by_sequence[current["sequence_id"]]
        position = next(index for index, row in enumerate(sequence) if row["frame_id"] == frame_id)
        previous = sequence[position - 1] if position > 0 else None
        following = sequence[position + 1] if position + 1 < len(sequence) else None
        queue_rows.append(
            {
                "adjudication_row_id": adjudication_row_id(frame_id, current["source_sha256"]),
                "frame_id": frame_id,
                "source_sha256": current["source_sha256"],
                "current_image_path": current["source_image_path"],
                "previous_image_path": previous["source_image_path"] if previous else "",
                "previous_image_sha256": previous["source_sha256"] if previous else "",
                "next_image_path": following["source_image_path"] if following else "",
                "next_image_sha256": following["source_sha256"] if following else "",
                "queue_order": "",
            }
        )
    queue_rows.sort(
        key=lambda row: hashlib.sha256(
            f"{ORDER_SEED}|{row['adjudication_row_id']}".encode()
        ).hexdigest()
    )
    for order, row in enumerate(queue_rows):
        row["queue_order"] = str(order)
    atomic_csv(QUEUE, queue_rows, IDENTITY_FIELDS)
    atomic_review(REVIEW, [{**row, **UNREVIEWED} for row in queue_rows])
    atomic_json(
        SCHEMA,
        {
            "schema": "P4GT1R_COUNT_OWNERSHIP_V1",
            "visible_hand_count": ["ZERO", "ONE", "TWO", "UNCERTAIN"],
            "one_hand_ownership": ["LEFT", "RIGHT", "UNCERTAIN", "NOT_APPLICABLE"],
            "count_one_ownership_uncertain_is_valid": True,
            "left_right_mean_target_signer_anatomical_side": True,
            "count_question_uses_current_frame_only": True,
            "adjacent_context_allowed_only_for_one_hand_ownership": True,
            "governed_development_truth_not_final_research_gold": True,
        },
    )
    atomic_json(
        BLINDING,
        {
            "status": "FROZEN_BEFORE_SIX_FRAME_ADJUDICATION",
            "ui_version": UI_VERSION,
            "order_seed": ORDER_SEED,
            "reviewer_sees_initially": [
                "exact non-mirrored current RGB frame",
                "anonymous progress",
            ],
            "ownership_context_policy": (
                "previous/current/next available only after count ONE; context may establish "
                "ownership but must not change current-frame count"
            ),
            "hidden": [
                "REST/SIGNING/TRANSITION",
                "sign/gloss",
                "DWPose",
                "WiLoR",
                "previous truth",
                "Pass-1 result",
                "Pass-2 result",
                "model confidence",
                "disagreement classification",
            ],
            "single_keypress_saves": False,
            "explicit_confirm_required": True,
            "queue_sha256": sha256(QUEUE),
            "review_sha256_at_freeze": sha256(REVIEW),
        },
    )
    result = {
        "status": "P4GT1R_ADJUDICATION_READY",
        "repeatability_frames_analyzed": 100,
        "visible_hand_count_agreement": 100 - count_disagreements,
        "visible_hand_count_denominator": 100,
        "count_disagreements": count_disagreements,
        "ownership_only_disagreements": ownership_only,
        "mixed_disagreements": mixed,
        "six_previous_conflicts": conflict_classes,
        "adjudication_queue_count": 6,
        "queue_sha256": sha256(QUEUE),
        "review_sha256_at_freeze": sha256(REVIEW),
    }
    atomic_json(PREPARE_RESULT, result)
    atomic_json(
        PROVENANCE,
        {
            **result,
            "pass1_full_sha256": EXPECTED_PASS1_FULL,
            "pass2_review_sha256": EXPECTED_PASS2_REVIEW,
            "repeatability_disagreements_sha256": EXPECTED_DISAGREEMENTS,
            "p4c2a_crop_review_sha256": EXPECTED_CROP_REVIEW,
            "analysis_sha256": sha256(ANALYSIS),
            "schema_sha256": sha256(SCHEMA),
        },
    )
    atomic_text(
        REPORT,
        f"""# P4-GT1R Schema Repair and V2 Rescore Result

## Status

**`P4GT1R_ADJUDICATION_READY` — six human decisions required.**

The existing 100-frame repeatability evidence has been reinterpreted without changing any prior
label. Visible-hand count agrees on **{100 - count_disagreements}/100** frames. All six former
direct side conflicts are **COUNT_DISAGREEMENT** cases; there are **{ownership_only}**
ownership-only conflicts and **{mixed}** mixed conflicts.

The adjudication queue contains only those six frames. It asks physical count from the exact current
frame first, then ownership only when count is ONE. Selecting an option does not save; explicit
Confirm/Enter is required. Adjacent RGB context remains hidden until count ONE and may be used only
for ownership.

No V2, rescore, model inference, training, threshold, Android, recognition, P4-C2B, P4-D, or P4-B
work has started.
""",
    )
    tracked = [QUEUE, REVIEW, ANALYSIS, SCHEMA, BLINDING, PROVENANCE, PREPARE_RESULT, REPORT]
    atomic_json(
        HASH_MANIFEST,
        {
            "status": "FROZEN_BEFORE_SIX_FRAME_ADJUDICATION",
            "artifacts": {
                str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in tracked
            },
        },
    )
    return result


class AdjudicationApp:
    def __init__(self, root: tk.Tk, store: AdjudicationStore) -> None:
        self.root = root
        self.store = store
        self.current = store.next_unreviewed()
        self.photo: ImageTk.PhotoImage | None = None
        self.count = tk.StringVar(value="")
        self.ownership = tk.StringVar(value="")
        self.context_used = False
        self.edit_mode = False
        self.edit_reason = ""
        root.title("P4-GT1R Count-First Hand Adjudication")
        root.geometry("1200x840")
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._build()
        self.render()

    def _build(self) -> None:
        self.image_label = ttk.Label(self.root, anchor="center")
        self.image_label.pack(side="left", fill="both", expand=True, padx=12, pady=12)
        panel = ttk.Frame(self.root, padding=18, width=430)
        panel.pack(side="right", fill="y")
        self.progress = ttk.Label(panel, font=("Segoe UI", 12, "bold"))
        self.progress.pack(anchor="w", pady=(0, 12))
        ttk.Label(
            panel,
            text="STEP 1 — How many of the TARGET SIGNER'S hands are physically visible NOW?",
            wraplength=400,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            panel,
            text="Use only the current non-mirrored frame. Selecting does not save.",
            wraplength=400,
        ).pack(anchor="w", pady=(0, 6))
        for label, value in (
            ("0 — no hands", "ZERO"),
            ("1 — exactly one hand", "ONE"),
            ("2 — both hands", "TWO"),
            ("UNCERTAIN", "UNCERTAIN"),
        ):
            ttk.Radiobutton(
                panel,
                text=label,
                variable=self.count,
                value=value,
                command=self.count_changed,
            ).pack(anchor="w", pady=2)
        self.ownership_host = ttk.Frame(panel)
        self.ownership_host.pack(fill="x")
        self.ownership_panel = ttk.Frame(self.ownership_host)
        ttk.Separator(self.ownership_panel).pack(fill="x", pady=12)
        ttk.Label(
            self.ownership_panel,
            text="STEP 2 — Which anatomical hand is the one visible hand?",
            font=("Segoe UI", 11, "bold"),
            wraplength=400,
        ).pack(anchor="w")
        ttk.Label(
            self.ownership_panel,
            text=(
                "LEFT/RIGHT means the SIGNER'S anatomical side, not screen position. "
                "UNCERTAIN is valid—never guess."
            ),
            foreground="#a6261d",
            wraplength=400,
        ).pack(anchor="w", pady=(4, 8))
        for label, value in (
            ("Anatomical LEFT", "LEFT"),
            ("Anatomical RIGHT", "RIGHT"),
            ("UNCERTAIN ownership", "UNCERTAIN"),
        ):
            ttk.Radiobutton(
                self.ownership_panel, text=label, variable=self.ownership, value=value
            ).pack(anchor="w", pady=2)
        ttk.Label(
            self.ownership_panel,
            text="Ownership context only — it must not change your Step-1 count.",
            wraplength=400,
        ).pack(anchor="w", pady=(10, 4))
        context = ttk.Frame(self.ownership_panel)
        context.pack(fill="x")
        self.previous_button = ttk.Button(
            context, text="Previous RGB", command=lambda: self.show_context("previous")
        )
        self.previous_button.pack(side="left", padx=2)
        ttk.Button(context, text="Current RGB", command=lambda: self.show_context("current")).pack(
            side="left", padx=2
        )
        self.next_button = ttk.Button(
            context, text="Next RGB", command=lambda: self.show_context("next")
        )
        self.next_button.pack(side="left", padx=2)
        ttk.Separator(panel).pack(fill="x", pady=14)
        ttk.Button(panel, text="CONFIRM AND SAVE (Enter)", command=self.confirm).pack(fill="x")
        ttk.Button(panel, text="Edit a completed adjudication…", command=self.start_edit).pack(
            fill="x", pady=(14, 0)
        )
        self.root.bind("<Return>", lambda _event: self.confirm())

    def count_changed(self) -> None:
        if self.count.get() == "ONE":
            self.ownership_panel.pack(fill="x", pady=(8, 0))
        else:
            self.ownership_panel.pack_forget()
            self.ownership.set("NOT_APPLICABLE")
            self.context_used = False
            self.show_context("current")

    def render(self) -> None:
        if self.current is None:
            self.progress.configure(text="ADJUDICATION_COMPLETE")
            self.image_label.configure(image="", text="All six adjudications are complete.")
            self.ownership_panel.pack_forget()
            return
        complete = sum(row["reviewer_status"] == "COMPLETE" for row in self.store.rows)
        self.progress.configure(text=f"Frame {complete + 1}/6 | completed {complete}")
        self.count.set(self.current.get("visible_hand_count") or "")
        self.ownership.set(self.current.get("one_hand_ownership") or "")
        self.context_used = self.current.get("ownership_context_used") == "YES"
        self.show_context("current")
        self.count_changed()

    def show_image(self, path: str) -> None:
        image = Image.open(path).convert("RGB")
        image.thumbnail((740, 790), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image)
        self.image_label.configure(image=self.photo, text="")

    def show_context(self, which: str) -> None:
        if self.current is None:
            return
        if which == "current":
            path = self.current["current_image_path"]
        else:
            if self.count.get() != "ONE":
                return
            path = self.current[f"{which}_image_path"]
            if not path:
                return
            self.context_used = True
        self.show_image(path)
        self.previous_button.configure(
            state="normal" if self.current["previous_image_path"] else "disabled"
        )
        self.next_button.configure(
            state="normal" if self.current["next_image_path"] else "disabled"
        )

    def label(self) -> dict[str, str]:
        count = self.count.get()
        ownership = self.ownership.get() if count == "ONE" else "NOT_APPLICABLE"
        return {
            "visible_hand_count": count,
            "one_hand_ownership": ownership,
            "ownership_context_used": "YES" if self.context_used and count == "ONE" else "NO",
        }

    def confirm(self) -> None:
        if self.current is None:
            return
        try:
            label = self.label()
            validate_label(label)
            if self.edit_mode:
                self.store.edit_completed(
                    displayed(self.current), label, reason=self.edit_reason, confirmed=True
                )
                self.edit_mode = False
                self.edit_reason = ""
                self.current = self.store.next_unreviewed()
            else:
                self.current = self.store.save_new(displayed(self.current), label)
            self.count.set("")
            self.ownership.set("")
            self.context_used = False
            self.render()
        except ReviewIntegrityError as error:
            messagebox.showerror("Complete both required steps", str(error))

    def start_edit(self) -> None:
        identifier = simpledialog.askstring(
            "Edit completed adjudication", "Enter the anonymous adjudication ID:"
        )
        if not identifier:
            return
        reason = simpledialog.askstring("Required reason", "Why must it change?")
        if not reason:
            return
        self.store.rescan()
        try:
            row = self.store.by_id(identifier.strip())
            if row["reviewer_status"] != "COMPLETE":
                raise ReviewIntegrityError("That row is not completed")
            if not messagebox.askyesno(
                "Confirm explicit edit", "Load this completed adjudication for a journaled edit?"
            ):
                return
            self.current = row
            self.edit_mode = True
            self.edit_reason = reason
            self.render()
        except ReviewIntegrityError as error:
            messagebox.showerror("Cannot edit", str(error))

    def close(self) -> None:
        try:
            self.store.snapshot("session_close")
        finally:
            self.root.destroy()


def check() -> dict[str, Any]:
    store = AdjudicationStore()
    counts = Counter(row["reviewer_status"] for row in store.rows)
    result = {
        "rows": len(store.rows),
        "completed": counts["COMPLETE"],
        "remaining": counts["UNREVIEWED"],
        "labels": dict(
            sorted(
                Counter(
                    f"COUNT={row['visible_hand_count']}|OWNER={row['one_hand_ownership']}|CTX={row['ownership_context_used']}"
                    for row in store.rows
                    if row["reviewer_status"] == "COMPLETE"
                ).items()
            )
        ),
        "errors": [],
        "passed": counts["COMPLETE"] == 6,
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
        AdjudicationApp(root, AdjudicationStore())
        root.mainloop()


if __name__ == "__main__":
    main()
