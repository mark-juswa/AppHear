"""Prepare and run the blinded P4-C2R full-frame truth adjudication.

This module stops at R1. It never creates V2 or performs proposal/ownership analysis.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import tkinter as tk
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parents[2]
REPLACEMENT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement"
V1_DIR = REPLACEMENT / "p4a2_fresh_evidence_repair_v2_01"
V1 = V1_DIR / "frozen_truth/P4A2_FRESH_HUMAN_TRUTH_V1.csv"
P4C2A = REPLACEMENT / "p4c2a_dwpose_rgb_crop_separability_01"
INFERENCE = REPLACEMENT / "p4a2_high_recall_rescue_final_01/p4a2_frozen_inference_manifest.csv"
OUT = REPLACEMENT / "p4c2r_proposal_ownership_truth_repair_01"
QUEUE = OUT / "p4c2r_truth_review_queue.csv"
REVIEW = OUT / "p4c2r_truth_review.csv"
SELECTION = OUT / "p4c2r_truth_selection_manifest.csv"
R0_MANIFEST = OUT / "p4c2r_r0_source_evidence_manifest.json"
BLINDING = OUT / "p4c2r_blinding_manifest.json"
PROTOCOL = OUT / "p4c2r_truth_review_protocol.json"
PREPARE_RESULT = OUT / "p4c2r_prepare_result.json"
REPORT = OUT / "P4C2R_PROPOSAL_OWNERSHIP_TRUTH_REPAIR_RESULT.md"
HASH_MANIFEST = OUT / "p4c2r_artifact_hash_manifest.json"
EXPECTED_DATASET = "7819c59123b4dacdafac190c81754deb766d6ed6087a2b58535490d45a6a3edd"
EXPECTED_ANNOTATION = "1b9f34412ba885e397019742bf29027987ce58668d099fd3914e48ab3206774b"
EXPECTED_REVIEW = "fe47dd7c710a91e2a2bb88df3d33269aa89edf8b0d657898394b86783c89522f"
SAMPLE_SEED = "P4C2R_TRUTH_QA_V1_20260825"
ORDER_SEED = "P4C2R_BLINDED_ORDER_V1_20260825"
UI_VERSION = "P4C2R_TRUTH_REVIEW_UI_V1.0.0"

IDENTITY_FIELDS = [
    "review_row_id",
    "source_annotation_row_id",
    "sequence_id",
    "frame_index",
    "image_sha256",
    "image_path",
    "queue_order",
]
LABEL_FIELDS = ["visible_left", "visible_right", "frame_state", "reviewer_note"]
AUDIT_FIELDS = [
    "reviewer_status",
    "reviewed_utc",
    "revision_count",
    "last_edit_utc",
    "last_edit_reason",
]
ALL_FIELDS = [*IDENTITY_FIELDS, *LABEL_FIELDS, *AUDIT_FIELDS]
UNREVIEWED = {
    "visible_left": "",
    "visible_right": "",
    "frame_state": "",
    "reviewer_note": "",
    "reviewer_status": "UNREVIEWED",
    "reviewed_utc": "",
    "revision_count": "0",
    "last_edit_utc": "",
    "last_edit_reason": "",
}


class ReviewIntegrityError(RuntimeError):
    pass


class RowIdentityMismatch(ReviewIntegrityError):
    pass


class CompletedRowImmutable(ReviewIntegrityError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def dataset_hash(rows: list[dict[str, str]]) -> str:
    label_fields = [
        "any_hand_visible",
        "visible_left",
        "visible_right",
        "zero_hand",
        "rest",
        "entering",
        "leaving",
        "blur",
        "occlusion",
        "edge_clipped",
        "partial_visibility",
        "crossing",
        "hand_hand_contact",
        "hand_body_contact",
        "left_visibility_quality",
        "right_visibility_quality",
        "reviewer_note",
    ]
    fields = [
        "annotation_row_id",
        "sequence_id",
        "frame_index",
        "image_sha256",
        *label_fields,
        "reviewer_status",
    ]
    payload = [
        {field: row[field] for field in fields}
        for row in sorted(rows, key=lambda item: item["annotation_row_id"])
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def review_row_id(sequence_id: str, frame_index: str, image_sha: str) -> str:
    material = f"P4C2R\n{sequence_id}\n{frame_index}\n{image_sha}".encode()
    return "P4C2R_" + hashlib.sha256(material).hexdigest()[:24]


def validate_label(label: dict[str, str]) -> None:
    for field in ("visible_left", "visible_right"):
        if label.get(field) not in {"YES", "NO", "UNCERTAIN"}:
            raise ReviewIntegrityError(f"Invalid {field}: {label.get(field)!r}")
    if label.get("frame_state") not in {"REST", "SIGNING", "TRANSITION", "UNCERTAIN"}:
        raise ReviewIntegrityError(f"Invalid frame_state: {label.get('frame_state')!r}")


@dataclass(frozen=True)
class DisplayedIdentity:
    review_row_id: str
    source_annotation_row_id: str
    sequence_id: str
    frame_index: str
    image_sha256: str
    image_path: str


class ReviewStore:
    def __init__(self, path: Path = REVIEW, *, verify_images: bool = True) -> None:
        self.path = path
        self.verify_images = verify_images
        self.journal = path.parent / "p4c2r_completed_label_edit_journal.jsonl"
        self.backups = path.parent / "review_backups"
        self.rows = self._load_verified()

    def _load_verified(self) -> list[dict[str, str]]:
        rows = read_csv(self.path)
        ids = [row["review_row_id"] for row in rows]
        if len(ids) != len(set(ids)):
            raise ReviewIntegrityError("DUPLICATE_REVIEW_ROW_ID")
        for row in rows:
            expected = review_row_id(row["sequence_id"], row["frame_index"], row["image_sha256"])
            if row["review_row_id"] != expected:
                raise RowIdentityMismatch("ANNOTATION_ROW_IDENTITY_MISMATCH")
            if row["reviewer_status"] not in {"UNREVIEWED", "COMPLETE"}:
                raise ReviewIntegrityError("Invalid reviewer status")
            if row["reviewer_status"] == "COMPLETE":
                validate_label(row)
            if self.verify_images:
                image = Path(row["image_path"])
                if not image.is_file() or sha256(image) != row["image_sha256"]:
                    raise RowIdentityMismatch("ANNOTATION_ROW_IDENTITY_MISMATCH")
        return rows

    def rescan(self) -> None:
        self.rows = self._load_verified()

    def by_id(self, identifier: str) -> dict[str, str]:
        matches = [row for row in self.rows if row["review_row_id"] == identifier]
        if len(matches) != 1:
            raise RowIdentityMismatch("ANNOTATION_ROW_IDENTITY_MISMATCH")
        return matches[0]

    def next_unreviewed(self, after_id: str | None = None) -> dict[str, str] | None:
        self.rescan()
        ordered = sorted(self.rows, key=lambda row: int(row["queue_order"]))
        if after_id is None:
            scan = ordered
        else:
            indices = [
                index for index, row in enumerate(ordered) if row["review_row_id"] == after_id
            ]
            if len(indices) != 1:
                raise RowIdentityMismatch("ANNOTATION_ROW_IDENTITY_MISMATCH")
            start = indices[0] + 1
            scan = ordered[start:] + ordered[:start]
        return next((row for row in scan if row["reviewer_status"] != "COMPLETE"), None)

    def verify_displayed(self, shown: DisplayedIdentity) -> dict[str, str]:
        row = self.by_id(shown.review_row_id)
        expected = (
            row["source_annotation_row_id"],
            row["sequence_id"],
            row["frame_index"],
            row["image_sha256"],
            row["image_path"],
        )
        actual = (
            shown.source_annotation_row_id,
            shown.sequence_id,
            shown.frame_index,
            shown.image_sha256,
            shown.image_path,
        )
        if expected != actual or sha256(Path(shown.image_path)) != shown.image_sha256:
            raise RowIdentityMismatch("ANNOTATION_ROW_IDENTITY_MISMATCH")
        return row

    def _commit(self) -> None:
        atomic_csv(self.path, self.rows, ALL_FIELDS)

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
        row.update({field: label.get(field, "") for field in LABEL_FIELDS})
        row.update({"reviewer_status": "COMPLETE", "reviewed_utc": datetime.now(UTC).isoformat()})
        self._commit()
        completed = sum(item["reviewer_status"] == "COMPLETE" for item in self.rows)
        if completed % 25 == 0:
            self.snapshot(f"completed_{completed:04d}")
        return self.next_unreviewed(after_id=shown.review_row_id)

    def edit_completed(
        self, shown: DisplayedIdentity, label: dict[str, str], *, reason: str, confirmed: bool
    ) -> dict[str, str]:
        if not confirmed or not reason.strip():
            raise CompletedRowImmutable("EDIT_COMPLETED_LABEL requires confirmation and reason")
        self.rescan()
        row = self.verify_displayed(shown)
        if row["reviewer_status"] != "COMPLETE":
            raise ReviewIntegrityError("Row is not complete")
        validate_label(label)
        prior = dict(row)
        now = datetime.now(UTC).isoformat()
        row.update({field: label.get(field, "") for field in LABEL_FIELDS})
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
        self._commit()
        return row


def _category(row: dict[str, str]) -> str | None:
    left, right = row["visible_left"], row["visible_right"]
    if left == "NO" and right == "NO" and row["zero_hand"] == "YES":
        return "QA_ZERO_HAND"
    if (left == "YES") ^ (right == "YES") and "UNCERTAIN" not in (left, right):
        return "QA_ONE_HAND"
    if left == "YES" and right == "YES":
        return "QA_TWO_HAND"
    return None


def _diverse_sample(rows: list[dict[str, str]], count: int, category: str) -> list[dict[str, str]]:
    remaining = list(rows)
    selected: list[dict[str, str]] = []
    signer_counts: Counter[str] = Counter()
    sequence_counts: Counter[str] = Counter()
    while remaining and len(selected) < count:
        chosen = min(
            remaining,
            key=lambda row: (
                sequence_counts[row["sequence_id"]],
                signer_counts[row["signer_id"]],
                hashlib.sha256(
                    f"{SAMPLE_SEED}|{category}|{row['annotation_row_id']}".encode()
                ).hexdigest(),
            ),
        )
        remaining.remove(chosen)
        selected.append(chosen)
        signer_counts[chosen["signer_id"]] += 1
        sequence_counts[chosen["sequence_id"]] += 1
    if len(selected) != count:
        raise ReviewIntegrityError(
            f"Not enough {category}: requested {count}, selected {len(selected)}"
        )
    return selected


def verify_r0() -> dict[str, Any]:
    truth = read_csv(V1)
    if sha256(V1) != EXPECTED_ANNOTATION or dataset_hash(truth) != EXPECTED_DATASET:
        raise ReviewIntegrityError("P4C2R_SOURCE_EVIDENCE_MISMATCH")
    if sha256(P4C2A / "p4c2a_human_crop_review.csv") != EXPECTED_REVIEW:
        raise ReviewIntegrityError("P4C2R_SOURCE_EVIDENCE_MISMATCH")
    artifact_manifest = json.loads(
        (P4C2A / "p4c2a_artifact_hash_manifest.json").read_text(encoding="utf-8")
    )
    for relative, expected in artifact_manifest["artifacts"].items():
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            raise ReviewIntegrityError("P4C2R_SOURCE_EVIDENCE_MISMATCH")
    crop_rows = read_csv(P4C2A / "p4c2a_crop_generation_manifest.csv")
    for row in crop_rows:
        if sha256(Path(row["crop_path"])) != row["crop_sha256"]:
            raise ReviewIntegrityError("P4C2R_SOURCE_EVIDENCE_MISMATCH")
    inference = read_csv(INFERENCE)
    native_hashes: dict[str, str] = {}
    for row in inference:
        path = ROOT / row["raw_relative_path"]
        if not path.is_file():
            raise ReviewIntegrityError("P4C2R_SOURCE_EVIDENCE_MISMATCH")
        native_hashes[row["annotation_row_id"]] = sha256(path)
    return {
        "status": "R0_SOURCE_EVIDENCE_FROZEN",
        "v1_dataset_sha256": EXPECTED_DATASET,
        "v1_annotation_sha256": EXPECTED_ANNOTATION,
        "p4c2a_review_sha256": EXPECTED_REVIEW,
        "p4c2a_artifact_hash_manifest_sha256": sha256(P4C2A / "p4c2a_artifact_hash_manifest.json"),
        "p4c2a_crop_count_verified": len(crop_rows),
        "native_output_count_verified": len(native_hashes),
        "native_output_sha256": native_hashes,
        "verified_utc": datetime.now(UTC).isoformat(),
    }


def prepare() -> dict[str, Any]:
    if REVIEW.exists() and any(row["reviewer_status"] == "COMPLETE" for row in read_csv(REVIEW)):
        raise ReviewIntegrityError("Review already started; package is immutable")
    OUT.mkdir(parents=True, exist_ok=True)
    r0 = verify_r0()
    truth_rows = read_csv(V1)
    truth = {row["annotation_row_id"]: row for row in truth_rows}

    discrepancy = read_csv(P4C2A / "p4c2a_governed_truth_discrepancies.csv")
    opposite = [
        row
        for row in read_csv(P4C2A / "p4c2a_false_proposal_visual_positive_cases.csv")
        if row["one_hand_opposite_slot_absent"] == "YES"
    ]
    misses = read_csv(P4C2A / "p4c2a_proposal_misses.csv")
    reasons: dict[str, set[str]] = defaultdict(set)
    for row in discrepancy:
        reasons[row["annotation_row_id"]].add("KNOWN_ZERO_HAND_DISCREPANCY")
    for row in opposite:
        reasons[row["annotation_row_id"]].add("OPPOSITE_SLOT_CASE")
    for row in misses:
        reasons[row["annotation_row_id"]].add("VISIBLE_PROPOSAL_MISS")
    flagged_ids = set(reasons)
    if len(flagged_ids) != 48:
        raise ReviewIntegrityError(f"Expected 48 unique flagged frames, found {len(flagged_ids)}")

    qa_pools: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in truth_rows:
        if row["annotation_row_id"] in flagged_ids:
            continue
        category = _category(row)
        if category:
            qa_pools[category].append(row)
    qa_rows = [
        *_diverse_sample(qa_pools["QA_ZERO_HAND"], 40, "QA_ZERO_HAND"),
        *_diverse_sample(qa_pools["QA_ONE_HAND"], 40, "QA_ONE_HAND"),
        *_diverse_sample(qa_pools["QA_TWO_HAND"], 20, "QA_TWO_HAND"),
    ]
    selected_ids = flagged_ids | {row["annotation_row_id"] for row in qa_rows}
    if len(selected_ids) != 148:
        raise ReviewIntegrityError("P4C2R selection is not 148 unique source frames")

    qa_category = {row["annotation_row_id"]: _category(row) for row in qa_rows}
    selection_rows: list[dict[str, str]] = []
    neutral_rows: list[dict[str, str]] = []
    for source_id in selected_ids:
        source = truth[source_id]
        reason = (
            "+".join(sorted(reasons[source_id]))
            if source_id in reasons
            else qa_category[source_id] or ""
        )
        identifier = review_row_id(
            source["sequence_id"], source["frame_index"], source["image_sha256"]
        )
        selection_rows.append(
            {
                "review_row_id": identifier,
                "source_annotation_row_id": source_id,
                "sequence_id": source["sequence_id"],
                "signer_id": source["signer_id"],
                "frame_index": source["frame_index"],
                "image_sha256": source["image_sha256"],
                "image_path": source["review_image_path"],
                "selection_category": reason,
                "v1_visible_left": source["visible_left"],
                "v1_visible_right": source["visible_right"],
                "v1_zero_hand": source["zero_hand"],
                "v1_rest": source["rest"],
            }
        )
        neutral_rows.append(
            {
                "review_row_id": identifier,
                "source_annotation_row_id": source_id,
                "sequence_id": source["sequence_id"],
                "frame_index": source["frame_index"],
                "image_sha256": source["image_sha256"],
                "image_path": source["review_image_path"],
            }
        )

    neutral_rows.sort(
        key=lambda row: hashlib.sha256(f"{ORDER_SEED}|{row['review_row_id']}".encode()).hexdigest()
    )
    for index, row in enumerate(neutral_rows):
        row["queue_order"] = str(index)
    order_by_id = {row["review_row_id"]: row["queue_order"] for row in neutral_rows}
    for row in selection_rows:
        row["queue_order"] = order_by_id[row["review_row_id"]]
    selection_rows.sort(key=lambda row: int(row["queue_order"]))

    queue_fields = IDENTITY_FIELDS
    atomic_csv(QUEUE, neutral_rows, queue_fields)
    atomic_csv(REVIEW, [{**row, **UNREVIEWED} for row in neutral_rows], ALL_FIELDS)
    atomic_csv(SELECTION, selection_rows, list(selection_rows[0]))
    atomic_json(R0_MANIFEST, r0)
    atomic_json(
        PROTOCOL,
        {
            "protocol": "P4-C2R R1 independent full-frame truth adjudication",
            "review_question": "Are the person's anatomical left and right hands visible?",
            "side_values": ["YES", "NO", "UNCERTAIN"],
            "optional_frame_state_values": ["REST", "SIGNING", "TRANSITION", "UNCERTAIN"],
            "qa_gate": (
                "0-2 material frame disagreements among 100 QA permits targeted correction; "
                ">=3 stops"
            ),
            "qa_denominator": 100,
            "known_flagged_frames_excluded_from_qa_rate": True,
            "v1_is_immutable": True,
            "v2_created_before_review": False,
        },
    )
    atomic_json(
        BLINDING,
        {
            "status": "FROZEN_BEFORE_REVIEW",
            "ui_version": UI_VERSION,
            "review_order_seed": ORDER_SEED,
            "qa_sample_seed": SAMPLE_SEED,
            "reviewer_sees": ["raw full-frame RGB", "anonymous frame ID", "review progress"],
            "hidden_from_reviewer": [
                "DWPose",
                "crop",
                "WiLoR",
                "E2/R1",
                "V1 truth",
                "selection reason",
                "signer",
                "gloss",
                "QA category",
            ],
            "queue_sha256": sha256(QUEUE),
            "review_sha256_at_freeze": sha256(REVIEW),
        },
    )
    counts = Counter(row["selection_category"] for row in selection_rows)
    result = {
        "status": "P4C2R_R1_HUMAN_REVIEW_PENDING",
        "review_rows": 148,
        "flagged_unique_frames": 48,
        "qa_frames": 100,
        "qa_zero_hand": 40,
        "qa_one_hand": 40,
        "qa_two_hand": 20,
        "selection_category_counts": dict(sorted(counts.items())),
        "unique_sequences": len({row["sequence_id"] for row in selection_rows}),
        "unique_signers": len({row["signer_id"] for row in selection_rows}),
        "queue_sha256": sha256(QUEUE),
        "review_sha256": sha256(REVIEW),
        "selection_manifest_sha256": sha256(SELECTION),
        "r0_manifest_sha256": sha256(R0_MANIFEST),
    }
    atomic_json(PREPARE_RESULT, result)
    atomic_text(
        REPORT,
        """# P4-C2R Proposal Coverage, Slot Ownership, and Truth Repair

## Status

**R1 HUMAN REVIEW PENDING.** R0 source evidence is verified and frozen. R2-R5 have not started.

The neutral queue contains **148 unique full frames**: 48 flagged frames (8 known zero-hand
discrepancies, 23 opposite-slot cases, and 17 unique proposal-miss frames) plus a deterministic,
signer/sequence-aware **100-frame QA sample** (40 V1 zero-hand, 40 V1 one-hand, 20 V1 two-hand).

The reviewer sees only full-frame RGB, anonymous progress, and the anatomical-side question. V1
truth, DWPose, crops, WiLoR, E2/R1, signer/gloss, and selection reasons are hidden. Normal review
saves are atomic and status-driven; completed labels cannot be overwritten without an explicit,
journaled edit.

Do not create `P4_ELIGIBILITY_TRUTH_V2`, compute QA disagreements, optimize proposals, or analyze
ownership until all 148 rows are independently reviewed. If QA later contains at least three
material visibility disagreements, stop with `TRUTH_V1_BROADER_REAUDIT_REQUIRED`.

No classifier, detector, DWPose inference, threshold change, V2 truth, Android, recognition,
P4-C2B, HVD, P4-D, or P4-B work occurred.
""",
    )
    tracked = [
        QUEUE,
        REVIEW,
        SELECTION,
        R0_MANIFEST,
        BLINDING,
        PROTOCOL,
        PREPARE_RESULT,
        REPORT,
        Path(__file__),
        ROOT / "tests/test_p4c2r_truth_review.py",
        ROOT / "model/config/recognition_upgrade/run_p4c2r_truth_review.ps1",
    ]
    atomic_json(
        HASH_MANIFEST,
        {
            "status": "FROZEN_BEFORE_HUMAN_REVIEW",
            "artifacts": {
                str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in tracked
            },
        },
    )
    return result


def displayed(row: dict[str, str]) -> DisplayedIdentity:
    return DisplayedIdentity(
        row["review_row_id"],
        row["source_annotation_row_id"],
        row["sequence_id"],
        row["frame_index"],
        row["image_sha256"],
        row["image_path"],
    )


class ReviewApp:
    def __init__(self, root: tk.Tk, store: ReviewStore) -> None:
        self.root, self.store = root, store
        self.current = store.next_unreviewed()
        self.photo: ImageTk.PhotoImage | None = None
        self.edit_mode = False
        self.edit_reason = ""
        self.state = tk.StringVar(value="UNCERTAIN")
        self.left = tk.StringVar(value="UNCERTAIN")
        self.right = tk.StringVar(value="UNCERTAIN")
        self.note = tk.StringVar(value="")
        root.title("P4-C2R Blinded Anatomical Hand Visibility Review")
        root.geometry("1180x820")
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._build()
        self.render()

    def _build(self) -> None:
        self.image_label = ttk.Label(self.root, anchor="center")
        self.image_label.pack(side="left", fill="both", expand=True, padx=12, pady=12)
        panel = ttk.Frame(self.root, padding=18, width=410)
        panel.pack(side="right", fill="y")
        self.progress = ttk.Label(panel, font=("Segoe UI", 12, "bold"))
        self.progress.pack(anchor="w", pady=(0, 12))
        ttk.Label(
            panel,
            text="LEFT/RIGHT mean the PERSON'S anatomical left/right — not screen position.",
            foreground="#a6261d",
            wraplength=380,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", pady=(0, 14))
        ttk.Label(
            panel,
            text="Fast entry: optionally set frame state, then press one hand key.",
            wraplength=380,
        ).pack(anchor="w")
        ttk.Label(
            panel,
            text="0 No hands   1 LEFT only   2 RIGHT only   3 Both   4 Unsure",
            font=("Consolas", 11, "bold"),
        ).pack(anchor="w", pady=(4, 12))
        quick = ttk.Frame(panel)
        quick.pack(fill="x")
        for text, _key, left, right in (
            ("0  No hands", "0", "NO", "NO"),
            ("1  LEFT only", "1", "YES", "NO"),
            ("2  RIGHT only", "2", "NO", "YES"),
            ("3  Both", "3", "YES", "YES"),
            ("4  Unsure", "4", "UNCERTAIN", "UNCERTAIN"),
        ):
            ttk.Button(
                quick,
                text=text,
                command=lambda left_value=left, right_value=right: self.quick_save(
                    left_value, right_value
                ),
            ).pack(fill="x", pady=2)
        ttk.Separator(panel).pack(fill="x", pady=14)
        ttk.Label(panel, text="Optional frame state (R/S/T/U)", font=("Segoe UI", 10, "bold")).pack(
            anchor="w"
        )
        for label, value in (
            ("Rest", "REST"),
            ("Signing", "SIGNING"),
            ("Transition", "TRANSITION"),
            ("Uncertain / not needed", "UNCERTAIN"),
        ):
            ttk.Radiobutton(panel, text=label, variable=self.state, value=value).pack(anchor="w")
        ttk.Separator(panel).pack(fill="x", pady=14)
        ttk.Label(
            panel,
            text="Independent side controls for mixed/uncertain cases",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        for title, variable in (("Anatomical LEFT", self.left), ("Anatomical RIGHT", self.right)):
            row = ttk.Frame(panel)
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=title, width=18).pack(side="left")
            ttk.Combobox(
                row,
                textvariable=variable,
                values=("YES", "NO", "UNCERTAIN"),
                state="readonly",
                width=14,
            ).pack(side="left")
        ttk.Entry(panel, textvariable=self.note).pack(fill="x", pady=(8, 4))
        ttk.Button(panel, text="Save detailed answer (Enter)", command=self.save_detailed).pack(
            fill="x", pady=4
        )
        ttk.Button(panel, text="Edit a completed label…", command=self.start_edit).pack(
            fill="x", pady=(16, 2)
        )
        ttk.Label(
            panel,
            text="State keys: R Rest · S Signing · T Transition · U Uncertain",
            wraplength=380,
        ).pack(anchor="w", pady=(16, 0))
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
            self.image_label.configure(
                image="", text="All 148 frames are complete. Close this window."
            )
            return
        complete = sum(row["reviewer_status"] == "COMPLETE" for row in self.store.rows)
        identifier = self.current["review_row_id"]
        self.progress.configure(
            text=f"Frame {complete + 1}/148 | completed {complete} | ID {identifier}"
        )
        image = Image.open(self.current["image_path"]).convert("RGB")
        image.thumbnail((730, 760), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image)
        self.image_label.configure(image=self.photo, text="")
        self.left.set(self.current.get("visible_left") or "UNCERTAIN")
        self.right.set(self.current.get("visible_right") or "UNCERTAIN")
        self.state.set(self.current.get("frame_state") or "UNCERTAIN")
        self.note.set(self.current.get("reviewer_note") or "")

    def _label(self, left: str, right: str) -> dict[str, str]:
        return {
            "visible_left": left,
            "visible_right": right,
            "frame_state": self.state.get(),
            "reviewer_note": self.note.get().strip(),
        }

    def quick_save(self, left: str, right: str) -> None:
        self.left.set(left)
        self.right.set(right)
        self._save(self._label(left, right))

    def save_detailed(self) -> None:
        self._save(self._label(self.left.get(), self.right.get()))

    def _save(self, label: dict[str, str]) -> None:
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
        identifier = simpledialog.askstring(
            "Edit completed label", "Enter the complete anonymous frame ID:"
        )
        if not identifier:
            return
        reason = simpledialog.askstring("Required reason", "Why must this completed label change?")
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
        except ReviewIntegrityError as error:
            messagebox.showerror("Cannot edit", str(error))

    def close(self) -> None:
        try:
            self.store.snapshot("session_close")
        finally:
            self.root.destroy()


def check() -> dict[str, Any]:
    store = ReviewStore()
    counts = Counter(row["reviewer_status"] for row in store.rows)
    labels = Counter(
        f"L={row['visible_left']}|R={row['visible_right']}|STATE={row['frame_state']}"
        for row in store.rows
        if row["reviewer_status"] == "COMPLETE"
    )
    result = {
        "rows": len(store.rows),
        "completed": counts["COMPLETE"],
        "remaining": counts["UNREVIEWED"],
        "label_patterns": dict(sorted(labels.items())),
        "errors": [],
        "passed": counts["COMPLETE"] == len(store.rows),
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
        store = ReviewStore()
        root = tk.Tk()
        ReviewApp(root, store)
        root.mainloop()


if __name__ == "__main__":
    main()
