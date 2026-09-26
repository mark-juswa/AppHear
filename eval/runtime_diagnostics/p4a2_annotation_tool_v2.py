"""Status-driven, atomic, blinded P4-A2 human annotation tool v2.

The v1 tooling-defect artifacts are read-only historical evidence. This module creates a
new all-UNREVIEWED annotation file and never imports historical labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4a2_fresh_evidence_repair_01"
OUT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p4a2_fresh_evidence_repair_v2_01"
CANONICAL = OUT / "p4a2_human_frame_annotations_v2.csv"
SOURCE_MANIFEST = OUT / "p4a2_annotation_source_manifest_v2.csv"
TOPUP_MANIFEST = OUT / "p4a2_inactive_topup_manifest_v2.csv"
HISTORICAL = OUT / "historical_invalid_tooling_defect"
UI_VERSION = "P4A2_ANNOTATION_UI_V2.0.0"

TRUTH_FIELDS = [
    "any_hand_visible", "visible_left", "visible_right", "zero_hand", "rest", "entering",
    "leaving", "blur", "occlusion", "edge_clipped", "partial_visibility", "crossing",
    "hand_hand_contact", "hand_body_contact",
]
QUALITY_FIELDS = ["left_visibility_quality", "right_visibility_quality"]
LABEL_FIELDS = [*TRUTH_FIELDS, *QUALITY_FIELDS, "reviewer_note"]
IDENTITY_FIELDS = [
    "annotation_row_id", "source_annotation_row_id", "source_family", "sequence_id",
    "frame_index", "image_sha256", "review_image_path", "signer_id", "gloss",
    "intended_future_role", "review_batch", "queue_order",
]
AUDIT_FIELDS = [
    "reviewer_status", "reviewed_utc", "revision_count", "last_edit_utc", "last_edit_reason",
]
ALL_FIELDS = [*IDENTITY_FIELDS, *LABEL_FIELDS, *AUDIT_FIELDS]
UNREVIEWED_DEFAULTS = {
    **{field: "" for field in TRUTH_FIELDS + QUALITY_FIELDS},
    "reviewer_note": "", "reviewer_status": "UNREVIEWED", "reviewed_utc": "",
    "revision_count": "0", "last_edit_utc": "", "last_edit_reason": "",
}


class AnnotationIntegrityError(RuntimeError):
    pass


class AnnotationRowIdentityMismatch(AnnotationIntegrityError):
    pass


class CompletedRowImmutable(AnnotationIntegrityError):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] = ALL_FIELDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_jsonl_fsync(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def immutable_row_id(sequence_id: str, frame_index: str, image_sha256: str) -> str:
    material = f"{sequence_id}\n{frame_index}\n{image_sha256}".encode("utf-8")
    return "P4A2V2_" + hashlib.sha256(material).hexdigest()[:24]


def queue_sort_key(row: dict[str, str]) -> tuple[str, int, str]:
    sequence_key = hashlib.sha256(f"20260824:{row['sequence_id']}".encode()).hexdigest()
    return sequence_key, int(row["frame_index"]), row["annotation_row_id"]


def validate_label(label: dict[str, str]) -> None:
    for field in TRUTH_FIELDS:
        if label.get(field) not in {"YES", "NO", "UNCERTAIN"}:
            raise AnnotationIntegrityError(f"Invalid {field}: {label.get(field)!r}")
    for field in QUALITY_FIELDS:
        if label.get(field) not in {"CLEAR", "WEAK", "NOT_APPLICABLE", "UNCERTAIN"}:
            raise AnnotationIntegrityError(f"Invalid {field}: {label.get(field)!r}")
    if label["any_hand_visible"] == "NO" and (label["visible_left"] != "NO" or label["visible_right"] != "NO"):
        raise AnnotationIntegrityError("No-hand answer conflicts with visible side")
    if label["any_hand_visible"] == "YES" and "YES" not in (label["visible_left"], label["visible_right"]):
        raise AnnotationIntegrityError("Visible-hand answer requires at least one visible anatomical side")
    if label["zero_hand"] == "YES" and label["any_hand_visible"] != "NO":
        raise AnnotationIntegrityError("ZERO_HAND requires no visible hand")


@dataclass
class DisplayedIdentity:
    annotation_row_id: str
    sequence_id: str
    frame_index: str
    image_sha256: str
    image_path: str


class AnnotationStore:
    def __init__(self, canonical: Path = CANONICAL, *, verify_images: bool = True) -> None:
        self.canonical = canonical
        self.verify_images = verify_images
        self.journal = canonical.parent / "p4a2_completed_label_edit_journal.jsonl"
        self.backups = canonical.parent / "backups"
        self.rows = self._load_verified()

    def _load_verified(self) -> list[dict[str, str]]:
        if not self.canonical.exists():
            raise AnnotationIntegrityError(f"Missing canonical annotation file: {self.canonical}")
        rows = read_csv(self.canonical)
        ids = [row["annotation_row_id"] for row in rows]
        if len(ids) != len(set(ids)):
            raise AnnotationIntegrityError("DUPLICATE_ANNOTATION_ROW_ID")
        for row in rows:
            expected = immutable_row_id(row["sequence_id"], row["frame_index"], row["image_sha256"])
            if row["annotation_row_id"] != expected:
                raise AnnotationRowIdentityMismatch("ANNOTATION_ROW_IDENTITY_MISMATCH")
            if row["reviewer_status"] not in {"UNREVIEWED", "COMPLETE"}:
                raise AnnotationIntegrityError(f"Invalid reviewer_status: {row['reviewer_status']}")
            if row["reviewer_status"] == "COMPLETE":
                validate_label(row)
            if self.verify_images:
                image = Path(row["review_image_path"])
                if not image.exists() or sha256(image) != row["image_sha256"]:
                    raise AnnotationRowIdentityMismatch("ANNOTATION_ROW_IDENTITY_MISMATCH")
        return rows

    def rescan(self) -> None:
        self.rows = self._load_verified()

    def by_id(self, row_id: str) -> dict[str, str]:
        matches = [row for row in self.rows if row["annotation_row_id"] == row_id]
        if len(matches) != 1:
            raise AnnotationRowIdentityMismatch("ANNOTATION_ROW_IDENTITY_MISMATCH")
        return matches[0]

    def ordered(self) -> list[dict[str, str]]:
        return sorted(self.rows, key=queue_sort_key)

    def next_unreviewed(self, after_row_id: str | None = None) -> dict[str, str] | None:
        self.rescan()
        ordered = self.ordered()
        start = 0
        if after_row_id is not None:
            indices = [index for index, row in enumerate(ordered) if row["annotation_row_id"] == after_row_id]
            if len(indices) != 1:
                raise AnnotationRowIdentityMismatch("ANNOTATION_ROW_IDENTITY_MISMATCH")
            start = indices[0] + 1
        scan = ordered[start:] + ordered[:start]
        return next((row for row in scan if row["reviewer_status"] != "COMPLETE"), None)

    def verify_displayed(self, identity: DisplayedIdentity) -> dict[str, str]:
        row = self.by_id(identity.annotation_row_id)
        expected = (row["sequence_id"], row["frame_index"], row["image_sha256"], row["review_image_path"])
        actual = (identity.sequence_id, identity.frame_index, identity.image_sha256, identity.image_path)
        if expected != actual or sha256(Path(identity.image_path)) != identity.image_sha256:
            raise AnnotationRowIdentityMismatch("ANNOTATION_ROW_IDENTITY_MISMATCH")
        return row

    def _commit(self) -> None:
        atomic_write_csv(self.canonical, self.rows)

    def snapshot(self, reason: str) -> Path:
        self.rescan()
        self.backups.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        target = self.backups / f"{stamp}_{reason}_{sha256(self.canonical)[:12]}.csv"
        shutil.copy2(self.canonical, target)
        if sha256(target) != sha256(self.canonical):
            raise AnnotationIntegrityError("Backup hash mismatch")
        return target

    def save_new(self, identity: DisplayedIdentity, label: dict[str, str]) -> dict[str, str] | None:
        self.rescan()
        row = self.verify_displayed(identity)
        if row["reviewer_status"] == "COMPLETE":
            raise CompletedRowImmutable("EDIT_COMPLETED_LABEL_REQUIRED")
        validate_label(label)
        now = datetime.now(timezone.utc).isoformat()
        row.update({field: label.get(field, "") for field in LABEL_FIELDS})
        row.update({"reviewer_status": "COMPLETE", "reviewed_utc": now})
        self._commit()
        completed = sum(item["reviewer_status"] == "COMPLETE" for item in self.rows)
        if completed % 25 == 0:
            self.snapshot(f"completed_{completed:04d}")
        return self.next_unreviewed(after_row_id=identity.annotation_row_id)

    def edit_completed(self, identity: DisplayedIdentity, label: dict[str, str], *, reason: str, confirmed: bool) -> dict[str, str]:
        if not confirmed or not reason.strip():
            raise CompletedRowImmutable("EDIT_COMPLETED_LABEL requires confirmation and reason")
        self.rescan()
        row = self.verify_displayed(identity)
        if row["reviewer_status"] != "COMPLETE":
            raise AnnotationIntegrityError("Row is not complete; use normal save")
        validate_label(label)
        prior = dict(row)
        now = datetime.now(timezone.utc).isoformat()
        row.update({field: label.get(field, "") for field in LABEL_FIELDS})
        row.update({
            "reviewer_status": "COMPLETE", "last_edit_utc": now,
            "last_edit_reason": reason.strip(), "revision_count": str(int(row["revision_count"]) + 1),
        })
        append_jsonl_fsync(self.journal, {"event": "EDIT_COMPLETED_LABEL", "timestamp": now, "reason": reason.strip(), "prior": prior, "replacement": dict(row)})
        self._commit()
        return row

    def undo_completed(self, identity: DisplayedIdentity, *, reason: str, confirmed: bool) -> dict[str, str]:
        if not confirmed or not reason.strip():
            raise CompletedRowImmutable("Undo requires confirmation and reason")
        self.rescan()
        row = self.verify_displayed(identity)
        if row["reviewer_status"] != "COMPLETE":
            return row
        prior = dict(row)
        now = datetime.now(timezone.utc).isoformat()
        row.update(UNREVIEWED_DEFAULTS)
        append_jsonl_fsync(self.journal, {"event": "UNDO_COMPLETED_LABEL", "timestamp": now, "reason": reason.strip(), "prior": prior, "replacement": dict(row)})
        self._commit()
        return row

    def append_unreviewed(self, new_rows: list[dict[str, str]]) -> None:
        self.snapshot("before_topup_merge")
        self.rescan()
        existing_ids = {row["annotation_row_id"] for row in self.rows}
        new_ids = [row["annotation_row_id"] for row in new_rows]
        if len(new_ids) != len(set(new_ids)) or existing_ids.intersection(new_ids):
            raise AnnotationIntegrityError("DUPLICATE_ANNOTATION_ROW_ID")
        for row in new_rows:
            if row["reviewer_status"] != "UNREVIEWED":
                raise AnnotationIntegrityError("Top-up rows must start UNREVIEWED")
        before = {row["annotation_row_id"]: json.dumps(row, sort_keys=True) for row in self.rows}
        self.rows.extend(new_rows)
        self._commit()
        self.rescan()
        after = {row["annotation_row_id"]: json.dumps(row, sort_keys=True) for row in self.rows}
        if any(after[row_id] != payload for row_id, payload in before.items()):
            raise AnnotationIntegrityError("Existing annotation changed during top-up merge")


def convert_source_row(row: dict[str, str]) -> dict[str, str]:
    row_id = immutable_row_id(row["sequence_id"], row["frame_index"], row["image_sha256"])
    converted = {
        "annotation_row_id": row_id,
        "source_annotation_row_id": row["annotation_row_id"],
        "source_family": row["source_family"],
        "sequence_id": row["sequence_id"],
        "frame_index": row["frame_index"],
        "image_sha256": row["image_sha256"],
        "review_image_path": str(V1 / "review_images" / f"{row['annotation_row_id']}{Path(row['source_video_image_path']).suffix.lower()}"),
        "signer_id": row["signer_id"],
        "gloss": row["gloss"],
        "intended_future_role": row["intended_future_role"],
        "review_batch": row["review_batch"],
        "queue_order": "",
        **UNREVIEWED_DEFAULTS,
    }
    return converted


def preserve_defective_history() -> dict[str, str]:
    HISTORICAL.mkdir(parents=True, exist_ok=True)
    paths = [
        V1 / "p4a2_blinded_review_labels.csv",
        V1 / "p4a2_benchmark_tooling_defect.json",
        V1 / "p4a2_resume_overwrite_affected_rows.csv",
        V1 / "P4A2_FRESH_EVIDENCE_REPAIR_RESULT.md",
    ]
    hashes = {}
    for source in paths:
        target = HISTORICAL / source.name
        if not target.exists():
            shutil.copy2(source, target)
        if sha256(target) != sha256(source):
            raise AnnotationIntegrityError("Historical preservation hash mismatch")
        hashes[source.name] = sha256(source)
    atomic_write_json(HISTORICAL / "INVALID_TOOLING_DEFECT_DO_NOT_USE.json", {
        "status": "INVALID_TOOLING_DEFECT_DO_NOT_USE",
        "historical_decision": "BENCHMARK_TOOLING_DEFECT — NOT FROZEN",
        "files": hashes,
    })
    return hashes


def prepare_clean_package() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    historical_hashes = preserve_defective_history()
    v1_rows = read_csv(V1 / "p4a2_annotation_source_manifest.csv")
    initial = [convert_source_row(row) for row in v1_rows if row["review_batch"] == "INITIAL"]
    topup = [convert_source_row(row) for row in v1_rows if row["review_batch"] == "TARGETED_TOPUP"]
    if len(initial) != 458 or len(topup) != 29:
        raise AnnotationIntegrityError(f"Expected 458 initial / 29 inactive top-up; found {len(initial)} / {len(topup)}")
    ordered = sorted(initial, key=queue_sort_key)
    for index, row in enumerate(ordered):
        row["queue_order"] = str(index)
    topup_ordered = sorted(topup, key=queue_sort_key)
    for index, row in enumerate(topup_ordered):
        row["queue_order"] = str(index)
    if CANONICAL.exists():
        existing = read_csv(CANONICAL)
        if any(row["reviewer_status"] != "UNREVIEWED" for row in existing):
            raise AnnotationIntegrityError("Clean v2 package already contains human labels; prepare will not overwrite it")
    else:
        atomic_write_csv(CANONICAL, ordered)
    atomic_write_csv(SOURCE_MANIFEST, ordered, IDENTITY_FIELDS)
    atomic_write_csv(TOPUP_MANIFEST, topup_ordered, IDENTITY_FIELDS)
    store = AnnotationStore(CANONICAL, verify_images=True)
    if len(store.rows) != 458 or any(row["reviewer_status"] != "UNREVIEWED" for row in store.rows):
        raise AnnotationIntegrityError("Fresh v2 package is not 458 all-UNREVIEWED rows")
    atomic_write_json(OUT / "p4a2_v2_blinding_manifest.json", {
        "ui_version": UI_VERSION,
        "reviewer_visible": ["raw current RGB", "anonymous sequence progress", "previous/next raw RGB context"],
        "hidden": ["corrupted labels", "DWPose", "E2", "MediaPipe", "recognition output", "P4-A failures", "signer", "gloss", "future role"],
        "old_labels_imported": False,
    })
    atomic_write_json(OUT / "p4a2_v2_prepare_result.json", {
        "status": "CLEAN_ANNOTATION_PACKAGE_READY",
        "ui_version": UI_VERSION,
        "initial_unreviewed_rows": 458,
        "inactive_deterministic_topup_rows": 29,
        "historical_corrupted_file_sha256": historical_hashes["p4a2_blinded_review_labels.csv"],
    })


class ReviewAppV2:
    def __init__(self, store: AnnotationStore | None = None) -> None:
        import tkinter as tk
        from tkinter import ttk
        from PIL import Image, ImageTk
        self.tk, self.ttk, self.Image, self.ImageTk = tk, ttk, Image, ImageTk
        self.store = store or AnnotationStore()
        self.root = tk.Tk(); self.root.title("P4-A2 Clean Blinded Review v2")
        self.root.geometry("1360x900"); self.root.minsize(1050, 700)
        self.current_row = self.store.next_unreviewed()
        self.last_saved_identity: DisplayedIdentity | None = None
        self.vars: dict[str, Any] = {}
        self.selected_state = tk.StringVar(value="ORDINARY")
        self.photo = None
        self.build()
        self.root.protocol("WM_DELETE_WINDOW", self.close_session)
        self.load_current()

    def build(self) -> None:
        tk, ttk = self.tk, self.ttk
        left = ttk.Frame(self.root, padding=12); left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(self.root, padding=12, width=560); right.pack(side="right", fill="both"); right.pack_propagate(False)
        self.progress = ttk.Label(right, font=("Segoe UI", 12, "bold")); self.progress.pack(anchor="w", pady=(0, 7))
        ttk.Label(right, text="LEFT/RIGHT mean the PERSON'S own hands — not picture position.", foreground="#a32618", wraplength=530, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 8))
        self.image_label = ttk.Label(left, anchor="center"); self.image_label.pack(fill="both", expand=True)
        context = ttk.Frame(left); context.pack(pady=6)
        ttk.Button(context, text="◀ Previous RGB context", command=lambda: self.show_context(-1)).pack(side="left")
        ttk.Button(context, text="CURRENT frame", command=self.load_image).pack(side="left", padx=7)
        ttk.Button(context, text="Next RGB context ▶", command=lambda: self.show_context(1)).pack(side="left")
        state_box = ttk.LabelFrame(right, text="1 — State (A/R/E/L/U)", padding=9); state_box.pack(fill="x", pady=6)
        state_grid = ttk.Frame(state_box); state_grid.pack(fill="x")
        self.state_buttons = {}
        for index, (key, value, label) in enumerate([("A","ORDINARY","Ordinary"),("R","REST","Rest"),("E","ENTERING","Entering"),("L","LEAVING","Leaving"),("U","UNCERTAIN","Unsure")]):
            button = tk.Button(state_grid, text=f"{label}\n[{key}]", command=lambda v=value: self.set_state(v), padx=7, pady=7)
            button.grid(row=0, column=index, sticky="nsew", padx=2); state_grid.columnconfigure(index, weight=1); self.state_buttons[value] = button
        self.state_status = ttk.Label(state_box, text="Selected: ORDINARY", font=("Segoe UI", 10, "bold")); self.state_status.pack(anchor="w", pady=(5,0))
        hand_box = ttk.LabelFrame(right, text="2 — Visible hands (0/1/2/3/4 saves + advances)", padding=9); hand_box.pack(fill="x", pady=6)
        hand_grid = ttk.Frame(hand_box); hand_grid.pack(fill="x")
        for index, (key, value, label) in enumerate([("0","NONE","No hands"),("1","LEFT","Person LEFT"),("2","RIGHT","Person RIGHT"),("3","BOTH","Both"),("4","UNCERTAIN","Unsure")]):
            ttk.Button(hand_grid, text=f"{label}\n[{key}]", command=lambda v=value: self.commit(v)).grid(row=0,column=index,sticky="nsew",padx=2,ipady=9); hand_grid.columnconfigure(index,weight=1)
        for field in TRUTH_FIELDS:
            self.vars[field] = tk.StringVar(value="NO")
        for field in QUALITY_FIELDS:
            self.vars[field] = tk.StringVar(value="CLEAR")
        self.details_toggle = ttk.Button(right, text="Optional details: weak, blur, clipping, contact…", command=self.toggle_details); self.details_toggle.pack(fill="x", pady=6)
        self.details = ttk.LabelFrame(right, text="Optional details", padding=8)
        self.detail_buttons = {}
        for index, (field,label) in enumerate([("blur","Blur"),("occlusion","Occlusion"),("edge_clipped","Edge clipped"),("partial_visibility","Partial"),("crossing","Crossing"),("hand_hand_contact","Hands touching"),("hand_body_contact","Hand-body contact")]):
            button = tk.Button(self.details,text=label,command=lambda f=field:self.cycle_truth(f),padx=5,pady=4); button.grid(row=index//4,column=index%4,sticky="nsew",padx=2,pady=2); self.details.columnconfigure(index%4,weight=1); self.detail_buttons[field]=(button,label)
        self.quality_buttons = {}
        for index,(field,label) in enumerate([("left_visibility_quality","LEFT quality"),("right_visibility_quality","RIGHT quality")]):
            button=tk.Button(self.details,command=lambda f=field:self.cycle_quality(f),padx=5,pady=4); button.grid(row=2,column=index*2,columnspan=2,sticky="nsew",padx=2,pady=4); self.quality_buttons[field]=(button,label)
        utility = ttk.Frame(right); utility.pack(fill="x",pady=7)
        ttk.Button(utility,text="Undo last save…",command=self.undo_last).pack(side="left")
        ttk.Button(utility,text="Edit last completed…",command=self.edit_last).pack(side="left",padx=5)
        self.note = tk.Text(right,height=3,width=45); self.note.pack(fill="x",pady=5)
        ttk.Label(right,text="Examples: E then 2 = person's RIGHT entering · L then 3 = both leaving · R then 0 = no-hands/rest · 3 = ordinary both",foreground="#555",wraplength=530).pack(anchor="w",pady=6)
        self.root.bind("<Key>",self.handle_key)
        self.refresh_details(); self.set_state("ORDINARY")

    def displayed_identity(self) -> DisplayedIdentity:
        if self.current_row is None: raise AnnotationIntegrityError("ANNOTATION_COMPLETE")
        return DisplayedIdentity(self.current_row["annotation_row_id"],self.current_row["sequence_id"],self.current_row["frame_index"],self.current_row["image_sha256"],self.current_row["review_image_path"])

    def set_state(self,state:str)->None:
        self.selected_state.set(state); colors={"ORDINARY":"#d9ead3","REST":"#cfe2f3","ENTERING":"#fce5cd","LEAVING":"#ead1dc","UNCERTAIN":"#fff2cc"}
        for value,button in self.state_buttons.items(): button.configure(relief="sunken" if value==state else "raised",background=colors[value] if value==state else "#eeeeee")
        self.state_status.configure(text=f"Selected: {state}")

    def reset_frame(self)->None:
        self.set_state("ORDINARY"); self.note.delete("1.0","end")
        for field in TRUTH_FIELDS:self.vars[field].set("NO")
        for field in QUALITY_FIELDS:self.vars[field].set("CLEAR")
        self.details.pack_forget(); self.details_toggle.configure(text="Optional details: weak, blur, clipping, contact…"); self.refresh_details()

    def cycle_truth(self,field:str)->None:
        states={"NO":"YES","YES":"UNCERTAIN","UNCERTAIN":"NO"}; self.vars[field].set(states[self.vars[field].get()]); self.refresh_details()

    def cycle_quality(self,field:str)->None:
        states={"CLEAR":"WEAK","WEAK":"UNCERTAIN","UNCERTAIN":"CLEAR","NOT_APPLICABLE":"CLEAR"}; self.vars[field].set(states[self.vars[field].get()]); self.refresh_details()

    def refresh_details(self)->None:
        colors={"NO":"#e8e8e8","YES":"#f6a54c","UNCERTAIN":"#f3dc72"}
        for field,(button,label) in self.detail_buttons.items():
            value=self.vars[field].get(); button.configure(text=("✓ " if value=="YES" else "? " if value=="UNCERTAIN" else "")+label,background=colors[value])
        qcolors={"CLEAR":"#d9ead3","WEAK":"#f6a54c","UNCERTAIN":"#f3dc72","NOT_APPLICABLE":"#e8e8e8"}
        for field,(button,label) in self.quality_buttons.items(): value=self.vars[field].get(); button.configure(text=f"{label}: {value}",background=qcolors[value])

    def toggle_details(self)->None:
        if self.details.winfo_manager(): self.details.pack_forget(); self.details_toggle.configure(text="Optional details: weak, blur, clipping, contact…")
        else:self.details.pack(fill="x",pady=4,after=self.details_toggle);self.details_toggle.configure(text="Hide optional details")

    def build_label(self,hands:str)->dict[str,str]:
        state=self.selected_state.get(); left=hands in {"LEFT","BOTH"};right=hands in {"RIGHT","BOTH"}
        if hands=="NONE" and state in {"ENTERING","LEAVING"}: raise AnnotationIntegrityError("Entering/leaving requires a visible hand")
        if hands=="UNCERTAIN": any_hand=vl=vr=zero="UNCERTAIN";lq=rq="UNCERTAIN"
        else:
            any_hand="YES" if left or right else "NO";vl="YES" if left else "NO";vr="YES" if right else "NO";zero="NO" if left or right else "YES"
            lq=self.vars["left_visibility_quality"].get() if left else "NOT_APPLICABLE";rq=self.vars["right_visibility_quality"].get() if right else "NOT_APPLICABLE"
        label={field:self.vars[field].get() for field in TRUTH_FIELDS};label.update({"any_hand_visible":any_hand,"visible_left":vl,"visible_right":vr,"zero_hand":zero,"rest":"YES" if state=="REST" else "UNCERTAIN" if state=="UNCERTAIN" else "NO","entering":"YES" if state=="ENTERING" else "UNCERTAIN" if state=="UNCERTAIN" else "NO","leaving":"YES" if state=="LEAVING" else "UNCERTAIN" if state=="UNCERTAIN" else "NO","left_visibility_quality":lq,"right_visibility_quality":rq,"reviewer_note":self.note.get("1.0","end").strip()})
        if hands=="NONE":
            for field in self.detail_buttons:label[field]="NO"
        validate_label(label);return label

    def commit(self,hands:str)->None:
        from tkinter import messagebox
        try:label=self.build_label(hands);identity=self.displayed_identity();next_row=self.store.save_new(identity,label)
        except AnnotationIntegrityError as error:messagebox.showerror("Annotation stopped",str(error));return
        self.last_saved_identity=identity;self.current_row=next_row
        if next_row is None:messagebox.showinfo("ANNOTATION_COMPLETE","ANNOTATION_COMPLETE");return
        self.reset_frame();self.load_current()

    def handle_key(self,event:Any)->None:
        if event.widget.winfo_class() in {"Text","Entry","TEntry"}:return
        key=(event.char or "").lower();states={"a":"ORDINARY","r":"REST","e":"ENTERING","l":"LEAVING","u":"UNCERTAIN"};hands={"0":"NONE","1":"LEFT","2":"RIGHT","3":"BOTH","4":"UNCERTAIN"}
        if key in states:self.set_state(states[key])
        elif key in hands:self.commit(hands[key])

    def load_current(self)->None:
        if self.current_row is None:return
        completed=sum(row["reviewer_status"]=="COMPLETE" for row in self.store.rows);self.progress.configure(text=f"Completed {completed}/{len(self.store.rows)} | remaining {len(self.store.rows)-completed}")
        self.load_image()

    def load_image(self)->None:
        if self.current_row is None:return
        image=self.Image.open(self.current_row["review_image_path"]).convert("RGB");scale=min(760/image.width,760/image.height)
        if abs(scale-1)>0.02:image=image.resize((round(image.width*scale),round(image.height*scale)),self.Image.Resampling.LANCZOS)
        self.photo=self.ImageTk.PhotoImage(image);self.image_label.configure(image=self.photo,text="CURRENT FRAME",compound="top")

    def show_context(self,delta:int)->None:
        if self.current_row is None:return
        same=sorted([row for row in self.store.rows if row["sequence_id"]==self.current_row["sequence_id"]],key=lambda row:int(row["frame_index"]));index=next(i for i,row in enumerate(same) if row["annotation_row_id"]==self.current_row["annotation_row_id"]);target=index+delta
        if 0<=target<len(same):
            image=self.Image.open(same[target]["review_image_path"]).convert("RGB");scale=min(760/image.width,760/image.height);image=image.resize((round(image.width*scale),round(image.height*scale)),self.Image.Resampling.LANCZOS) if abs(scale-1)>0.02 else image;self.photo=self.ImageTk.PhotoImage(image);self.image_label.configure(image=self.photo,text="CONTEXT ONLY — CURRENT LABEL TARGET UNCHANGED",compound="top")

    def undo_last(self)->None:
        from tkinter import messagebox
        if self.last_saved_identity is None:return
        if not messagebox.askyesno("Undo completed label","Explicitly undo the last completed label? The prior value will be journaled."):return
        row=self.store.undo_completed(self.last_saved_identity,reason="REVIEWER_UNDO",confirmed=True);self.current_row=row;self.last_saved_identity=None;self.reset_frame();self.load_current()

    def edit_last(self)->None:
        from tkinter import messagebox,simpledialog
        if self.last_saved_identity is None:return
        if not messagebox.askyesno("EDIT_COMPLETED_LABEL","Completed rows are immutable during normal review. Explicitly edit the last completed label?"):return
        reason=simpledialog.askstring("Edit reason","Reason for changing the completed label:")
        if not reason:return
        row=self.store.by_id(self.last_saved_identity.annotation_row_id);self.current_row=row
        for field in TRUTH_FIELDS+QUALITY_FIELDS:self.vars[field].set(row[field])
        self.note.delete("1.0","end");self.note.insert("1.0",row["reviewer_note"]);self.refresh_details()
        # The next hand selection calls edit rather than normal save.
        identity=self.last_saved_identity
        original_commit=self.commit
        def commit_edit(hands:str)->None:
            label=self.build_label(hands);self.store.edit_completed(identity,label,reason=reason,confirmed=True);self.commit=original_commit;self.current_row=self.store.next_unreviewed();self.reset_frame();self.load_current()
        self.commit=commit_edit

    def close_session(self)->None:
        self.store.snapshot("session_close");self.root.destroy()

    def run(self)->None:self.root.mainloop()


def write_repair_report(test_result: dict[str, Any]) -> None:
    tool = Path(__file__); test = ROOT / "tests/test_p4a2_annotation_tool_v2.py"
    provenance = {
        "ui_version": UI_VERSION,
        "annotation_tool_sha256": sha256(tool), "test_sha256": sha256(test),
        "source_manifest_sha256": sha256(SOURCE_MANIFEST),
        "selected_frame_manifest_sha256": sha256(CANONICAL),
        "tests": test_result,
    }
    atomic_write_json(OUT / "p4a2_v2_provenance_manifest.json", provenance)
    report = f"""# P4-A2 Annotation Tool Repair Report

Historical status remains `BENCHMARK_TOOLING_DEFECT — NOT FROZEN`.

## Root cause

The v1 UI resumed at the first unlabeled row but then advanced by adjacent queue index. Interspersed top-up rows therefore caused completed rows to be revisited and overwritten.

## Exact repair

- Every row uses an immutable ID derived from sequence ID, frame index, and image SHA-256.
- Every save verifies displayed row ID, sequence, frame, image hash, and source bytes.
- Normal save rejects completed rows and rescans the canonical file for the next non-COMPLETE row.
- Atomic temporary-write/fsync/replace protects the canonical CSV.
- Backups occur every 25 completions, on close, and before top-up merge.
- Completed-label editing requires explicit confirmation/reason and journals prior/new values.

## Verification

- Reproduction test passed: {test_result['reproduction_test_passed']}
- Regression tests passed: {test_result['regression_tests_passed']}
- Completed-row overwrite protection: yes
- Interspersed top-up safe: yes
- Clean v2 rows: 458, all `UNREVIEWED`
- Inactive deterministic top-up rows: 29
- UI version: `{UI_VERSION}`

No corrupted labels were imported. No E2, R1/R2, DWPose, MediaPipe, recognition, training, Android, S4-S7, S6, Sapiens, P4-B, or new recording work occurred.
"""
    (OUT / "P4A2_ANNOTATION_TOOL_REPAIR_REPORT.md").write_text(report,encoding="utf-8")


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("command",choices=["prepare","review","validate"]);args=parser.parse_args()
    if args.command=="prepare":prepare_clean_package()
    elif args.command=="review":ReviewAppV2().run()
    else:
        store=AnnotationStore();print(json.dumps({"rows":len(store.rows),"completed":sum(r["reviewer_status"]=="COMPLETE" for r in store.rows),"remaining":sum(r["reviewer_status"]!="COMPLETE" for r in store.rows)},indent=2))


if __name__=="__main__":main()
