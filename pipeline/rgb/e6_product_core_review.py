"""E6 product-core manifest review utility.

Data-readiness only. This module reviews rows from the canonical raw-video
lineage manifest; it does not extract features, train models, export TFLite,
modify Android, or change the production recognizer.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import cv2
except Exception:  # pragma: no cover - checked at runtime
    cv2 = None

DEFAULT_MANIFEST = Path(
    "context/recognition_upgrade/product_core_data_readiness/lineage_fix_v1/"
    "canonical_product_core_manifest.csv"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/product_core_data_readiness/e6_product_core_review_01"
)
TARGET_SIGNS = ["GOOD", "HELLO", "SORRY", "HAVE", "KNOW", "THINK", "TAKE", "SELL"]
CONTROL_SIGNS = ["WASH2"]
SPLIT_TARGETS = {"total": 150, "local": 75, "local_signers": 5}
REVIEW_FIELDS = [
    "review_status",
    "review_decision",
    "use_for",
    "label_correct",
    "variant_compatible",
    "hand_visible",
    "sign_complete",
    "quality_ok",
    "review_reason",
    "review_notes",
    "reviewed_at",
]
VALID_DECISIONS = {"accept", "reject", "needs_expert", "diagnostic_only"}
VALID_STATUS = {"done", "needs_expert", "skip"}


@dataclass(frozen=True)
class Decision:
    key: str
    button: str
    status: str
    decision: str
    use_for: str
    label_correct: str
    variant_compatible: str
    hand_visible: str
    sign_complete: str
    quality_ok: str
    reason: str


DECISIONS = (
    Decision("1", "Accept: usable training candidate", "done", "accept", "train_candidate", "yes", "yes", "yes", "yes", "yes", "accepted_by_manual_review"),
    Decision("2", "Accept: low motion but valid", "done", "accept", "train_candidate", "yes", "yes", "yes", "yes", "usable_with_low_motion_note", "low_motion_but_valid_sign"),
    Decision("3", "Reject: wrong label / variant", "done", "reject", "reject", "no", "no", "unknown", "unknown", "unknown", "wrong_label_or_incompatible_variant"),
    Decision("4", "Reject: hands/framing/quality bad", "done", "reject", "reject", "yes", "unknown", "no", "unknown", "no", "bad_visibility_framing_or_quality"),
    Decision("5", "Reject: incomplete performance", "done", "reject", "reject", "yes", "unknown", "yes", "no", "unknown", "incomplete_or_partial_sign"),
    Decision("6", "Needs expert ASL review", "needs_expert", "needs_expert", "review_only", "unknown", "unknown", "unknown", "unknown", "unknown", "needs_expert_asl_review"),
    Decision("7", "Diagnostic only, not training", "done", "diagnostic_only", "diagnostic_only", "yes", "unknown", "unknown", "unknown", "unknown", "diagnostic_only_not_training"),
)
DECISION_BY_KEY = {d.key: d for d in DECISIONS}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _priority(row: dict[str, str]) -> tuple[int, int, str, str]:
    source_rank = 0 if row.get("source_dataset") == "LOCAL_SUPPLEMENTARY" else 1
    reason = row.get("classification_reasons", "")
    if "quality_warnings" in reason or "hand_hit_rate" in reason:
        reason_rank = 0
    elif row.get("source_dataset") == "ASL_CITIZEN":
        reason_rank = 2
    else:
        reason_rank = 1
    return (source_rank, reason_rank, row.get("canonical_gloss", ""), row.get("row_id", ""))


def _select_rows(
    rows: list[dict[str, str]],
    signs: set[str] | None,
    source: str | None,
    include_accepted: bool,
    limit: int | None,
) -> list[dict[str, str]]:
    selected = []
    for row in rows:
        if signs and row.get("canonical_gloss") not in signs:
            continue
        if source and row.get("source_dataset") != source:
            continue
        if row.get("classification") == "Manual review required" or (
            include_accepted and row.get("classification") == "Accepted"
        ):
            selected.append(row)
    selected.sort(key=_priority)
    if limit is not None:
        selected = selected[:limit]
    return selected


def prepare(args: argparse.Namespace) -> None:
    manifest = args.manifest
    if not manifest.exists():
        raise FileNotFoundError(f"manifest missing: {manifest}")
    run_dir = args.run_dir
    review_path = run_dir / "review_manifest.csv"
    if review_path.exists() and not args.overwrite:
        raise FileExistsError(f"review already exists: {review_path}; pass --overwrite to replace")
    rows = _read_csv(manifest)
    signs = set(args.signs) if args.signs else None
    selected = _select_rows(rows, signs, args.source, args.include_accepted, args.limit)
    if not selected:
        raise ValueError("no rows matched review selection")
    fields = list(selected[0].keys()) + [f for f in REVIEW_FIELDS if f not in selected[0]]
    out_rows = []
    for row in selected:
        out = dict(row)
        for field in REVIEW_FIELDS:
            out.setdefault(field, "")
        out_rows.append(out)
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(review_path, out_rows, fields)
    shutil.copy2(manifest, run_dir / "source_manifest_snapshot.csv")
    payload = {
        "experiment": "e6_product_core_manifest_review_v1",
        "run_dir": str(run_dir.resolve()),
        "source_manifest": str(manifest.resolve()),
        "rows": len(out_rows),
        "classification_counts": dict(Counter(row.get("classification", "") for row in out_rows)),
        "source_counts": dict(Counter(row.get("source_dataset", "") for row in out_rows)),
        "sign_counts": dict(Counter(row.get("canonical_gloss", "") for row in out_rows)),
        "review_command": f"python -m pipeline.rgb.e6_product_core_review review --run-dir \"{run_dir.resolve()}\"",
        "summarize_command": f"python -m pipeline.rgb.e6_product_core_review summarize --run-dir \"{run_dir.resolve()}\"",
        "check_command": f"python -m pipeline.rgb.e6_product_core_review check --run-dir \"{run_dir.resolve()}\"",
    }
    _write_json(run_dir / "prepare_summary.json", payload)
    print(json.dumps(payload, indent=2))


def _load_review(run_dir: Path) -> tuple[list[dict[str, str]], list[str]]:
    path = run_dir / "review_manifest.csv"
    if not path.exists():
        raise FileNotFoundError(f"missing review manifest: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    return rows, fields


def _save_review(run_dir: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    _write_csv(run_dir / "review_manifest.csv", rows, fields)


def _incomplete(row: dict[str, str]) -> bool:
    return not row.get("review_status")


def _make_strip(video_path: Path, width: int = 1080, frames: int = 6):
    if cv2 is None:
        raise RuntimeError("OpenCV is required for review image generation")
    if not video_path.exists():
        raise FileNotFoundError(video_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"could not open video: {video_path}")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total <= 0:
        indexes = [0]
    else:
        indexes = [round(i * max(total - 1, 0) / max(frames - 1, 1)) for i in range(frames)]
    images = []
    for index in indexes:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        h, w = frame.shape[:2]
        target_w = max(1, width // frames)
        scale = target_w / max(w, 1)
        target_h = max(1, int(h * scale))
        images.append(cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA))
    cap.release()
    if not images:
        raise RuntimeError(f"could not decode frames: {video_path}")
    min_h = min(img.shape[0] for img in images)
    images = [img[:min_h, :, :] for img in images]
    return cv2.hconcat(images)


def review(args: argparse.Namespace) -> None:
    rows, fields = _load_review(args.run_dir)
    negative_mode = bool(getattr(args, "negative_mode", False))
    try:
        import tkinter as tk
        from tkinter import messagebox
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"tkinter is required for review GUI: {exc}") from exc

    class ReviewApp:
        def __init__(self) -> None:
            self.root = tk.Tk()
            self.root.title(
                "AppHear E6 Fresh Negative Review"
                if negative_mode
                else "AppHear E6 Product-Core Review"
            )
            self.root.geometry("1320x860")
            self.root.minsize(1040, 720)
            self.rows = rows
            self.fields = fields
            self.index = self._first_incomplete()
            self.photo = None
            self.title = tk.StringVar()
            self.progress = tk.StringVar()
            self.sign_source = tk.StringVar()
            self.quality = tk.StringVar()
            self.history = tk.StringVar()
            self.path_text = tk.StringVar()
            self.current_decision = tk.StringVar()
            self.notes = tk.StringVar()

            self.root.configure(bg="#f4f6f8")
            header = tk.Frame(self.root, bg="#1f2937")
            header.pack(fill="x")
            tk.Label(
                header,
                textvariable=self.title,
                font=("Segoe UI", 16, "bold"),
                fg="white",
                bg="#1f2937",
                anchor="w",
                justify="left",
            ).pack(fill="x", padx=14, pady=(10, 2))
            tk.Label(
                header,
                textvariable=self.progress,
                font=("Segoe UI", 10),
                fg="#d1d5db",
                bg="#1f2937",
                anchor="w",
            ).pack(fill="x", padx=14, pady=(0, 10))

            body = tk.Frame(self.root, bg="#f4f6f8")
            body.pack(fill="both", expand=True, padx=12, pady=10)
            left = tk.Frame(body, bg="#f4f6f8")
            left.pack(side="left", fill="both", expand=True)
            right = tk.Frame(body, bg="#ffffff", width=360, highlightbackground="#d0d7de", highlightthickness=1)
            right.pack(side="right", fill="y", padx=(12, 0))
            right.pack_propagate(False)

            video_card = tk.Frame(left, bg="#ffffff", highlightbackground="#d0d7de", highlightthickness=1)
            video_card.pack(fill="both", expand=True)
            self.canvas_label = tk.Label(video_card, bg="#111827", fg="#f9fafb", font=("Segoe UI", 11))
            self.canvas_label.pack(fill="both", expand=True, padx=8, pady=8)

            info = tk.Frame(left, bg="#ffffff", highlightbackground="#d0d7de", highlightthickness=1)
            info.pack(fill="x", pady=(10, 0))
            self._section(info, "Sign / source", self.sign_source).pack(fill="x", padx=10, pady=(8, 3))
            self._section(info, "Quality signals", self.quality).pack(fill="x", padx=10, pady=3)
            self._section(info, "Previous usage", self.history).pack(fill="x", padx=10, pady=3)
            self._section(info, "Video path", self.path_text, wrap=980).pack(fill="x", padx=10, pady=(3, 8))

            tk.Label(
                right,
                text="Decision",
                font=("Segoe UI", 15, "bold"),
                bg="#ffffff",
                anchor="w",
            ).pack(fill="x", padx=12, pady=(12, 4))
            tk.Label(
                right,
                textvariable=self.current_decision,
                font=("Segoe UI", 10),
                bg="#ffffff",
                fg="#374151",
                wraplength=330,
                justify="left",
                anchor="w",
            ).pack(fill="x", padx=12, pady=(0, 10))

            if negative_mode:
                self._button(right, "1  Accept", "correct category and usable", "#18794e", lambda: self.capture(DECISION_BY_KEY["1"]))
                self._button(right, "2  Accept", "valid negative; subtype overlap is acceptable", "#2f6f9f", lambda: self.capture(DECISION_BY_KEY["2"]))
                self._button(right, "3  Reject", "wrong category or an approved core sign", "#b54708", lambda: self.capture(DECISION_BY_KEY["3"]))
                self._button(right, "4  Reject", "hands, framing, or quality bad", "#b42318", lambda: self.capture(DECISION_BY_KEY["4"]))
                self._button(right, "5  Reject", "claimed event is not visible", "#b42318", lambda: self.capture(DECISION_BY_KEY["5"]))
            else:
                self._button(right, "1  Accept", "usable training candidate", "#18794e", lambda: self.capture(DECISION_BY_KEY["1"]))
                self._button(right, "2  Accept", "low motion but valid", "#2f6f9f", lambda: self.capture(DECISION_BY_KEY["2"]))
                self._button(right, "3  Reject", "wrong label or variant", "#b54708", lambda: self.capture(DECISION_BY_KEY["3"]))
                self._button(right, "4  Reject", "hands, framing, or quality bad", "#b42318", lambda: self.capture(DECISION_BY_KEY["4"]))
                self._button(right, "5  Reject", "incomplete performance", "#b42318", lambda: self.capture(DECISION_BY_KEY["5"]))
            self._button(right, "6  Needs expert", "ASL label/variant uncertain", "#6b4f9b", lambda: self.capture(DECISION_BY_KEY["6"]))
            self._button(right, "7  Diagnostic only", "do not use for training", "#525252", lambda: self.capture(DECISION_BY_KEY["7"]))

            tk.Label(right, text="Notes", font=("Segoe UI", 11, "bold"), bg="#ffffff", anchor="w").pack(fill="x", padx=12, pady=(12, 2))
            tk.Entry(right, textvariable=self.notes, font=("Segoe UI", 10)).pack(fill="x", padx=12, pady=(0, 8))

            nav = tk.Frame(right, bg="#ffffff")
            nav.pack(fill="x", padx=12, pady=(6, 8))
            tk.Button(nav, text="Previous", command=self.prev, width=10).pack(side="left")
            tk.Button(nav, text="Next", command=self.next, width=10).pack(side="left", padx=4)
            tk.Button(nav, text="Save", command=self.save, width=8).pack(side="left")
            tk.Button(nav, text="Quit", command=self.root.destroy, width=8).pack(side="right")

            help_text = (
                (
                    "Use 1 when the displayed negative category is correct.\n"
                    "Use 2 when it is still a valid negative but overlaps another subtype.\n"
                    "Reject any approved core sign. Progress autosaves."
                )
                if negative_mode
                else (
                    "Use 1/2 only when the visible sign matches the target label.\n"
                    "Use 6 when you are unsure about ASL label or variant.\n"
                    "Left/Right arrows move between rows. Progress autosaves."
                )
            )
            tk.Label(
                right,
                text=help_text,
                font=("Segoe UI", 9),
                bg="#ffffff",
                fg="#4b5563",
                justify="left",
                wraplength=330,
            ).pack(fill="x", padx=12, pady=(4, 12))

            for decision in DECISIONS:
                self.root.bind(decision.key, lambda _event, d=decision: self.capture(d))
            self.root.bind("<Left>", lambda _event: self.prev())
            self.root.bind("<Right>", lambda _event: self.next())
            self.root.bind("<Control-s>", lambda _event: self.save())
            self.render()

        def _section(self, parent, title: str, variable: tk.StringVar, wrap: int = 980):
            frame = tk.Frame(parent, bg="#ffffff")
            tk.Label(frame, text=title, font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#111827", anchor="w").pack(fill="x")
            tk.Label(
                frame,
                textvariable=variable,
                font=("Consolas", 9),
                bg="#ffffff",
                fg="#374151",
                anchor="w",
                justify="left",
                wraplength=wrap,
            ).pack(fill="x")
            return frame

        def _button(self, parent, title: str, subtitle: str, color: str, command) -> None:
            frame = tk.Frame(parent, bg="#ffffff")
            frame.pack(fill="x", padx=12, pady=2)
            button = tk.Button(
                frame,
                text=title,
                command=command,
                bg=color,
                fg="white",
                activebackground=color,
                activeforeground="white",
                font=("Segoe UI", 11, "bold"),
                relief="flat",
                padx=8,
                pady=5,
                anchor="w",
            )
            button.pack(fill="x")
            tk.Label(frame, text=subtitle, font=("Segoe UI", 8), bg="#ffffff", fg="#6b7280", anchor="w").pack(fill="x")

        def _first_incomplete(self) -> int:
            for i, row in enumerate(self.rows):
                if _incomplete(row):
                    return i
            return 0

        def row(self) -> dict[str, str]:
            return self.rows[self.index]

        def _counts(self) -> tuple[int, int, int]:
            complete = sum(1 for r in self.rows if not _incomplete(r))
            remaining = len(self.rows) - complete
            return complete, remaining, len(self.rows)

        def render(self) -> None:
            row = self.row()
            complete, remaining, total = self._counts()
            gloss = row.get("canonical_gloss", "")
            source = row.get("source_dataset", "")
            classification = row.get("classification", "")
            reasons = row.get("classification_reasons", "") or "none"
            self.title.set(f"{gloss}   |   {source}   |   {row.get('row_id')}")
            self.progress.set(
                f"Row {self.index + 1} of {total}   |   reviewed {complete}   |   remaining {remaining}   |   original status: {classification}"
            )
            self.sign_source.set(
                f"variant={row.get('label_variant')}  signer={row.get('signer_id')}  "
                f"schema={row.get('source_schema')}  source_split={row.get('source_split')}"
            )
            self.quality.set(
                f"reason={reasons}\n"
                f"hand_hit={row.get('hand_hit_rate') or 'n/a'}  pose_hit={row.get('pose_hit_rate') or 'n/a'}  "
                f"warnings={row.get('quality_warnings') or 'none'}\n"
                f"duration={row.get('duration_sec') or 'n/a'}s  fps={row.get('fps') or 'n/a'}  "
                f"size={row.get('width') or '?'}x{row.get('height') or '?'}"
            )
            self.history.set(
                row.get("previous_experiment_usage_exact")
                or row.get("previous_experiment_usage_inferred")
                or "none recorded"
            )
            self.path_text.set(row.get("raw_video_path", ""))
            current = row.get("review_decision") or "not reviewed yet"
            current_reason = row.get("review_reason") or ""
            self.current_decision.set(f"Current: {current}" + (f"\nReason: {current_reason}" if current_reason else ""))
            self.notes.set(row.get("review_notes", ""))
            try:
                strip = _make_strip(Path(row.get("raw_video_path", "")), width=1200, frames=8)
                ok, encoded = cv2.imencode(".png", strip)
                if not ok:
                    raise RuntimeError("could not encode review strip")
                data = base64.b64encode(encoded.tobytes())
                self.photo = tk.PhotoImage(data=data)
                self.canvas_label.configure(image=self.photo, text="")
            except Exception as exc:
                self.photo = None
                self.canvas_label.configure(image="", text=f"Could not render video strip:\n{exc}")

        def capture(self, decision: Decision) -> None:
            row = self.row()
            row["review_status"] = decision.status
            row["review_decision"] = decision.decision
            row["use_for"] = (
                "fresh_negative_evaluation"
                if negative_mode and decision.decision == "accept"
                else decision.use_for
            )
            row["label_correct"] = decision.label_correct
            row["variant_compatible"] = decision.variant_compatible
            row["hand_visible"] = decision.hand_visible
            row["sign_complete"] = decision.sign_complete
            row["quality_ok"] = decision.quality_ok
            row["review_reason"] = decision.reason
            row["review_notes"] = self.notes.get()
            row["reviewed_at"] = _utc_now()
            self.save()
            self.next()

        def save(self) -> None:
            _save_review(args.run_dir, self.rows, self.fields)

        def next(self) -> None:
            self.rows[self.index]["review_notes"] = self.notes.get()
            self.save()
            self.index = min(len(self.rows) - 1, self.index + 1)
            self.render()

        def prev(self) -> None:
            self.rows[self.index]["review_notes"] = self.notes.get()
            self.save()
            self.index = max(0, self.index - 1)
            self.render()

        def run(self) -> None:
            self.root.mainloop()
            self.save()

    if not (args.run_dir / "review_manifest.pre_review_backup.csv").exists():
        shutil.copy2(args.run_dir / "review_manifest.csv", args.run_dir / "review_manifest.pre_review_backup.csv")
    ReviewApp().run()


def summarize(args: argparse.Namespace) -> None:
    rows, _fields = _load_review(args.run_dir)
    source_manifest = args.source_manifest or args.run_dir / "source_manifest_snapshot.csv"
    source_rows = _read_csv(source_manifest) if source_manifest.exists() else []
    by_review = {row.get("row_id", ""): row for row in rows}
    final_rows = []
    for row in source_rows:
        review_row = by_review.get(row.get("row_id", ""), {})
        final_decision = row.get("classification", "")
        if row.get("classification") == "Accepted":
            final_decision = "Accepted"
        elif review_row.get("review_decision") == "accept":
            final_decision = "Accepted"
        elif review_row.get("review_decision") == "reject":
            final_decision = "Rejected"
        elif review_row.get("review_decision") == "diagnostic_only":
            final_decision = "Diagnostic only"
        elif review_row.get("review_decision") == "needs_expert":
            final_decision = "Manual review required"
        elif row.get("classification") == "Manual review required":
            final_decision = "Manual review required"
        final = dict(row)
        final["final_decision"] = final_decision
        final["review_decision"] = review_row.get("review_decision", "")
        final["review_reason"] = review_row.get("review_reason", "")
        final["review_status"] = review_row.get("review_status", "")
        final_rows.append(final)

    gap_rows = []
    for gloss in TARGET_SIGNS:
        gr = [row for row in final_rows if row.get("canonical_gloss") == gloss]
        accepted = [row for row in gr if row.get("final_decision") == "Accepted"]
        accepted_local = [row for row in accepted if row.get("source_dataset") == "LOCAL_SUPPLEMENTARY"]
        gap_rows.append(
            {
                "canonical_gloss": gloss,
                "accepted_total_clips": len(accepted),
                "accepted_local_clips": len(accepted_local),
                "accepted_total_signers": len({row.get("signer_id", "") for row in accepted if row.get("signer_id")}),
                "accepted_local_signers": len({row.get("signer_id", "") for row in accepted_local if row.get("signer_id")}),
                "manual_review_remaining": sum(1 for row in gr if row.get("final_decision") == "Manual review required"),
                "rejected_or_diagnostic": sum(1 for row in gr if row.get("final_decision") in {"Rejected", "Diagnostic only"}),
                "remaining_total_gap": max(0, SPLIT_TARGETS["total"] - len(accepted)),
                "remaining_local_gap": max(0, SPLIT_TARGETS["local"] - len(accepted_local)),
                "remaining_local_signer_gap": max(0, SPLIT_TARGETS["local_signers"] - len({row.get("signer_id", "") for row in accepted_local if row.get("signer_id")})),
            }
        )
    out_dir = args.run_dir / "reports"
    _write_csv(out_dir / "post_review_gap_summary.csv", gap_rows, list(gap_rows[0].keys()))
    payload = {
        "experiment": "e6_product_core_manifest_review_v1",
        "run_dir": str(args.run_dir.resolve()),
        "review_rows": len(rows),
        "review_status_counts": dict(Counter(row.get("review_status", "") or "blank" for row in rows)),
        "review_decision_counts": dict(Counter(row.get("review_decision", "") or "blank" for row in rows)),
        "review_decision_by_sign": {
            gloss: dict(Counter(row.get("review_decision", "") or "blank" for row in rows if row.get("canonical_gloss") == gloss))
            for gloss in TARGET_SIGNS + CONTROL_SIGNS
        },
        "remaining_total_gap": sum(int(row["remaining_total_gap"]) for row in gap_rows),
        "remaining_local_gap": sum(int(row["remaining_local_gap"]) for row in gap_rows),
        "remaining_local_signer_gap": sum(int(row["remaining_local_signer_gap"]) for row in gap_rows),
        "post_review_gap_summary": str((out_dir / "post_review_gap_summary.csv").resolve()),
    }
    _write_json(out_dir / "review_summary.json", payload)
    print(json.dumps(payload, indent=2))


def check(args: argparse.Namespace) -> None:
    errors = []
    try:
        rows, fields = _load_review(args.run_dir)
    except Exception as exc:
        print(json.dumps({"run_dir": str(args.run_dir), "passed": False, "errors": [str(exc)]}, indent=2))
        return
    for field in REVIEW_FIELDS:
        if field not in fields:
            errors.append(f"missing review field: {field}")
    for idx, row in enumerate(rows, start=1):
        status = row.get("review_status", "")
        decision = row.get("review_decision", "")
        if status and status not in VALID_STATUS:
            errors.append(f"row {idx}: invalid review_status {status!r}")
        if decision and decision not in VALID_DECISIONS:
            errors.append(f"row {idx}: invalid review_decision {decision!r}")
        if args.require_reviewed and not status:
            errors.append(f"row {idx}: review incomplete")
        if row.get("raw_video_path") and not Path(row["raw_video_path"]).exists():
            errors.append(f"row {idx}: raw video missing")
        if len(errors) >= 20:
            break
    payload = {
        "run_dir": str(args.run_dir.resolve()),
        "rows": len(rows),
        "completed": sum(1 for row in rows if row.get("review_status")),
        "remaining": sum(1 for row in rows if not row.get("review_status")),
        "passed": not errors,
        "errors": errors,
    }
    if args.require_reviewed and payload["remaining"]:
        payload["passed"] = False
    print(json.dumps(payload, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="E6 product-core manifest review package")
    sub = parser.add_subparsers(dest="command", required=True)

    p_prepare = sub.add_parser("prepare")
    p_prepare.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p_prepare.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    p_prepare.add_argument("--signs", nargs="*", choices=TARGET_SIGNS + CONTROL_SIGNS)
    p_prepare.add_argument("--source", choices=["ASL_CITIZEN", "LOCAL_SUPPLEMENTARY"])
    p_prepare.add_argument("--limit", type=int)
    p_prepare.add_argument("--include-accepted", action="store_true")
    p_prepare.add_argument("--overwrite", action="store_true")
    p_prepare.set_defaults(func=prepare)

    p_review = sub.add_parser("review")
    p_review.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    p_review.set_defaults(func=review)

    p_summarize = sub.add_parser("summarize")
    p_summarize.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    p_summarize.add_argument("--source-manifest", type=Path)
    p_summarize.set_defaults(func=summarize)

    p_check = sub.add_parser("check")
    p_check.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    p_check.add_argument("--require-reviewed", action="store_true")
    p_check.set_defaults(func=check)

    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except Exception as exc:
        print(f"[e6-product-core-review] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
