"""E4-H controlled BYE/NO/YES variant and data-balance intervention package.

Experiment-only. Builds a manual variant-review package from the completed E4-G BYE/NO/YES
separability diagnostic. It copies existing visual panels, creates contact sheets, and prepares a
CSV where the reviewer decides whether each clip is the intended label and variant.

No Android assets, production recognizer files, source videos, model files, or datasets are modified.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

DEFAULT_SOURCE_RUN = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_g_bye_yes_no_separability_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_h_bye_no_yes_variant_review_01"
)
TARGETS = ("BYE", "NO", "YES")
REVIEW_FIELDS = [
    "review_status",
    "label_correct",
    "variant_group",
    "variant_matches_train_reference",
    "hands_visible",
    "motion_visible_enough",
    "recommended_action",
    "review_notes",
]
BASE_FIELDS = [
    "review_id",
    "priority",
    "review_reason",
    "panel_rel_path",
    "contact_sheet_rel_path",
    "sample_id",
    "sample_index",
    "split",
    "true_gloss",
    "model_pred_gloss",
    "model_correct",
    "model_confidence",
    "target_restricted_pred_gloss",
    "target_restricted_correct",
    "prob_BYE",
    "prob_NO",
    "prob_YES",
    "length",
    "video_path",
    "signer_id",
    "source_folder",
    "folder_word",
    "hand_hit_rate",
    "warnings",
]
QUEUE_FIELDS = BASE_FIELDS + REVIEW_FIELDS
REVIEW_STATUS_VALUES = {"done", "skip", "needs_second_review"}
YES_NO_UNSURE = {"yes", "no", "unsure"}
HANDS_VALUES = {"yes", "partial", "no"}
ACTION_VALUES = {
    "keep",
    "split_variant",
    "relabel",
    "quarantine",
    "recollect_same_variant",
    "defer_sign",
    "needs_second_review",
}


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


def _priority(row: dict[str, str]) -> tuple[int, str]:
    split = row.get("split", "")
    true_gloss = row.get("true_gloss", "")
    pred = row.get("model_pred_gloss", "")
    correct = row.get("model_correct", "") == "True"
    if split == "test" and true_gloss == "BYE" and pred == "YES":
        return 1, "held-out BYE predicted as YES"
    if split == "test" and true_gloss == "NO" and pred == "YES":
        return 2, "held-out NO predicted as YES"
    if split == "test" and true_gloss == "YES":
        return 3, "held-out YES reference/confusion comparison"
    if split == "test" and not correct:
        return 4, "other held-out target error"
    if split in {"train", "val"} and true_gloss in TARGETS:
        return 5, "train/validation reference for variant comparison"
    return 9, "target-group reference"


def _safe_name(value: str) -> str:
    keep = []
    for char in value:
        if char.isalnum() or char in {"-", "_", "."}:
            keep.append(char)
        else:
            keep.append("_")
    return "".join(keep).strip("_") or "item"


def _copy_panel(row: dict[str, str], dst_dir: Path, review_id: str) -> str:
    src = Path(row["panel_path"])
    if not src.exists():
        raise FileNotFoundError(f"missing source panel: {src}")
    name = (
        f"{review_id}_{row.get('split','')}_{row.get('true_gloss','')}"
        f"_pred-{row.get('model_pred_gloss','')}_{row.get('sample_id','')}.jpg"
    )
    dst = dst_dir / _safe_name(name)
    shutil.copy2(src, dst)
    return str(Path("panels") / dst.name)


def _make_contact_sheet(items: list[dict[str, str]], out_path: Path, title: str) -> None:
    if not items:
        return
    thumb_w = 520
    header_h = 52
    gap = 14
    cols = 2
    font = ImageFont.load_default()
    loaded: list[tuple[dict[str, str], Image.Image]] = []
    for item in items:
        image_path = out_path.parent.parent / item["panel_rel_path"]
        with Image.open(image_path) as image:
            image = image.convert("RGB")
            scale = thumb_w / image.width
            thumb_h = max(1, int(image.height * scale))
            loaded.append((item, image.resize((thumb_w, thumb_h))))
    rows = (len(loaded) + cols - 1) // cols
    max_h = max(image.height for _, image in loaded)
    width = cols * thumb_w + (cols + 1) * gap
    height = header_h + rows * (max_h + 58 + gap) + gap
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((gap, 14), title, fill=(0, 0, 0), font=font)
    for index, (item, image) in enumerate(loaded):
        row = index // cols
        col = index % cols
        x = gap + col * (thumb_w + gap)
        y = header_h + row * (max_h + 58 + gap)
        label = (
            f"{item['review_id']} {item['split']} true={item['true_gloss']} "
            f"pred={item['model_pred_gloss']} signer={item['signer_id']}"
        )
        draw.text((x, y), label[:96], fill=(0, 0, 0), font=font)
        canvas.paste(image, (x, y + 18))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=88)


def _build_html(run_dir: Path, rows: list[dict[str, str]], contact_sheets: dict[str, str]) -> None:
    parts = [
        "<!doctype html><meta charset='utf-8'><title>E4-H BYE/NO/YES Review</title>",
        "<style>body{font-family:Arial,sans-serif;margin:24px;line-height:1.4} img{max-width:100%;border:1px solid #ccc;margin:8px 0 24px} table{border-collapse:collapse;width:100%;font-size:13px} td,th{border:1px solid #ddd;padding:4px;vertical-align:top} th{background:#f3f3f3}</style>",
        "<h1>E4-H BYE/NO/YES Variant Review</h1>",
        "<p>Use this page for visual comparison. Record decisions in <code>variant_review_queue.csv</code>.</p>",
        "<h2>Contact Sheets</h2>",
    ]
    for key, rel in sorted(contact_sheets.items()):
        rel_url = rel.replace("\\", "/")
        parts.append(f"<h3>{key}</h3><img src='{rel_url}' alt='{key}'>")
    parts.append("<h2>Review Queue</h2><table><tr><th>ID</th><th>Reason</th><th>Split</th><th>True</th><th>Pred</th><th>Signer</th><th>Video</th><th>Panel</th></tr>")
    for row in rows:
        panel = row["panel_rel_path"].replace("\\", "/")
        parts.append(
            "<tr>"
            f"<td>{row['review_id']}</td><td>{row['review_reason']}</td><td>{row['split']}</td>"
            f"<td>{row['true_gloss']}</td><td>{row['model_pred_gloss']}</td><td>{row['signer_id']}</td>"
            f"<td>{row['video_path']}</td><td><a href='{panel}'>panel</a></td>"
            "</tr>"
        )
    parts.append("</table>")
    (run_dir / "review.html").write_text("\n".join(parts), encoding="utf-8")


def _write_guide(run_dir: Path) -> None:
    guide = r"""# E4-H BYE/NO/YES Variant Review Guide

Purpose: decide whether the `BYE`, `NO`, and `YES` clips are label-consistent and variant-consistent enough to train another benchmark.

Open these first:

1. `review.html` for a browser view.
2. `contact_sheets/` for side-by-side visual comparisons.
3. `variant_review_queue.csv` to record decisions.

Fill these columns in `variant_review_queue.csv`:

- `review_status`: `done`, `skip`, or `needs_second_review`.
- `label_correct`: `yes`, `no`, or `unsure`.
- `variant_group`: short name such as `standard`, `wave`, `shake`, `fist`, `point`, `unknown`, or your own consistent name.
- `variant_matches_train_reference`: `yes`, `no`, or `unsure`.
- `hands_visible`: `yes`, `partial`, or `no`.
- `motion_visible_enough`: `yes`, `no`, or `unsure`.
- `recommended_action`: `keep`, `split_variant`, `relabel`, `quarantine`, `recollect_same_variant`, `defer_sign`, or `needs_second_review`.
- `review_notes`: short explanation only when useful.

How to judge:

- The label is the intended word/sign name. For example, rows labeled `BYE` come from the local `goodbye` folder.
- A variant is the way the sign is performed. Same English word can have different signing styles; if train and test use different styles, the model may fail even when labels look correct.
- For `BYE`, compare held-out test `goodbye` clips against train/validation `BYE` references. If the held-out signer waves differently or uses a different movement/hand orientation, mark `variant_matches_train_reference=no` and consider `split_variant` or `recollect_same_variant`.
- For `NO`, check whether the repeated finger/hand motion is clearly different from `YES` and visible in the frames.
- For `YES`, use it as the comparison class because both `BYE` and `NO` collapsed into `YES`.

After review, run:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_h_variant_intervention summarize `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_h_bye_no_yes_variant_review_01" `
  --require-reviewed
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_h_variant_intervention check `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_h_bye_no_yes_variant_review_01" `
  --require-reviewed
```

Do not run another full 7-sign training job until this review is summarized.
"""
    (run_dir / "USER_REVIEW_GUIDE.md").write_text(guide, encoding="utf-8")


def prepare(args: argparse.Namespace) -> int:
    source_run = args.source_run.resolve()
    run_dir = args.run_dir.resolve()
    panel_index_path = source_run / "review_panel_index.csv"
    if not panel_index_path.exists():
        raise FileNotFoundError(f"missing E4-G panel index: {panel_index_path}")
    if run_dir.exists() and any(run_dir.iterdir()) and not args.overwrite:
        raise FileExistsError(f"run dir already exists; pass --overwrite to replace package files: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    panels_dir = run_dir / "panels"
    contact_dir = run_dir / "contact_sheets"
    panels_dir.mkdir(parents=True, exist_ok=True)
    contact_dir.mkdir(parents=True, exist_ok=True)

    source_rows = [row for row in _read_csv(panel_index_path) if row.get("true_gloss") in TARGETS]
    source_rows.sort(key=lambda row: (_priority(row)[0], row.get("true_gloss", ""), row.get("split", ""), row.get("sample_id", "")))

    rows: list[dict[str, Any]] = []
    for index, row in enumerate(source_rows, start=1):
        priority, reason = _priority(row)
        review_id = f"h{index:04d}"
        out = {field: row.get(field, "") for field in BASE_FIELDS if field not in {"review_id", "priority", "review_reason", "panel_rel_path", "contact_sheet_rel_path"}}
        out.update(
            {
                "review_id": review_id,
                "priority": priority,
                "review_reason": reason,
                "panel_rel_path": _copy_panel(row, panels_dir, review_id),
                "contact_sheet_rel_path": "",
            }
        )
        for field in REVIEW_FIELDS:
            out[field] = ""
        rows.append(out)

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[f"{row['true_gloss']}_{row['split']}"].append(row)  # type: ignore[index]
    contact_sheets: dict[str, str] = {}
    for key, items in groups.items():
        out_path = contact_dir / f"{_safe_name(key)}.jpg"
        title = f"E4-H {key}: compare variants, hand motion, and signer style"
        _make_contact_sheet(items, out_path, title)
        rel = str(Path("contact_sheets") / out_path.name)
        contact_sheets[key] = rel
        for item in items:
            item["contact_sheet_rel_path"] = rel

    _write_csv(run_dir / "variant_review_queue.csv", rows, QUEUE_FIELDS)
    _write_json(
        run_dir / "summary" / "prepare_summary.json",
        {
            "experiment": "e4_h_bye_no_yes_variant_intervention_v1",
            "source_run": str(source_run),
            "run_dir": str(run_dir),
            "rows": len(rows),
            "targets": list(TARGETS),
            "counts_by_true_split": dict(Counter(f"{row['true_gloss']}:{row['split']}" for row in rows)),
            "counts_by_reason": dict(Counter(row["review_reason"] for row in rows)),
            "contact_sheets": contact_sheets,
            "queue": str(run_dir / "variant_review_queue.csv"),
            "guide": str(run_dir / "USER_REVIEW_GUIDE.md"),
            "html": str(run_dir / "review.html"),
        },
    )
    _write_guide(run_dir)
    _build_html(run_dir, rows, contact_sheets)
    print(json.dumps({"experiment": "e4_h_bye_no_yes_variant_intervention_v1", "run_dir": str(run_dir), "rows": len(rows), "contact_sheets": len(contact_sheets), "passed": True}, indent=2))
    return 0


def _validate_review_row(row: dict[str, str], row_number: int) -> list[str]:
    errors: list[str] = []
    status = row.get("review_status", "").strip()
    if status not in REVIEW_STATUS_VALUES:
        errors.append(f"row {row_number}: review_status must be one of {sorted(REVIEW_STATUS_VALUES)}")
    for field in ("label_correct", "variant_matches_train_reference", "motion_visible_enough"):
        value = row.get(field, "").strip()
        if value not in YES_NO_UNSURE:
            errors.append(f"row {row_number}: {field} must be yes/no/unsure")
    hands = row.get("hands_visible", "").strip()
    if hands not in HANDS_VALUES:
        errors.append(f"row {row_number}: hands_visible must be yes/partial/no")
    action = row.get("recommended_action", "").strip()
    if action not in ACTION_VALUES:
        errors.append(f"row {row_number}: recommended_action must be one of {sorted(ACTION_VALUES)}")
    if not row.get("variant_group", "").strip():
        errors.append(f"row {row_number}: variant_group is required")
    return errors



def autofill(args: argparse.Namespace) -> int:
    """Auto-fill the queue with conservative engineering triage decisions."""
    run_dir = args.run_dir.resolve()
    queue_path = run_dir / "variant_review_queue.csv"
    if not queue_path.exists():
        raise FileNotFoundError(f"missing review queue: {queue_path}")
    rows = _read_csv(queue_path)
    if not args.overwrite and any(row.get("review_status", "").strip() for row in rows):
        raise ValueError("review queue already has decisions; pass --overwrite to replace them")

    action_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    for row in rows:
        true_gloss = row.get("true_gloss", "")
        split = row.get("split", "")
        pred = row.get("model_pred_gloss", "")
        correct = row.get("model_correct", "") == "True"
        hand_hit = float(row.get("hand_hit_rate", "0") or 0.0)
        hands_visible = "yes" if hand_hit >= 0.80 else "partial" if hand_hit >= 0.40 else "no"
        motion_visible = "yes" if hand_hit >= 0.75 else "unsure" if hand_hit >= 0.40 else "no"

        if split in {"train", "val"}:
            status = "done"
            label_correct = "yes"
            variant_group = f"{true_gloss.lower()}_reference"
            variant_match = "yes"
            action = "keep"
            note = "auto-triage: train/validation reference row; not ASL-fluent verification"
        elif true_gloss == "YES" and correct:
            status = "done"
            label_correct = "yes"
            variant_group = "yes_reference"
            variant_match = "yes"
            action = "keep"
            note = "auto-triage: held-out YES reference row; not ASL-fluent verification"
        elif true_gloss == "BYE" and pred == "YES":
            status = "needs_second_review"
            label_correct = "unsure"
            variant_group = "bye_test_collapse"
            variant_match = "unsure"
            action = "needs_second_review"
            note = "auto-triage: critical BYE->YES collapse; requires human variant/label decision"
        elif true_gloss == "NO" and pred == "YES":
            status = "needs_second_review"
            label_correct = "unsure"
            variant_group = "no_yes_confusion"
            variant_match = "unsure"
            action = "needs_second_review"
            note = "auto-triage: critical NO->YES confusion; requires human variant/label decision"
        elif not correct:
            status = "needs_second_review"
            label_correct = "unsure"
            variant_group = f"{true_gloss.lower()}_error"
            variant_match = "unsure"
            action = "needs_second_review"
            note = "auto-triage: held-out target error; requires human decision"
        else:
            status = "done"
            label_correct = "yes"
            variant_group = f"{true_gloss.lower()}_heldout_reference"
            variant_match = "yes"
            action = "keep"
            note = "auto-triage: held-out correct/reference row; not ASL-fluent verification"

        row["review_status"] = status
        row["label_correct"] = label_correct
        row["variant_group"] = variant_group
        row["variant_matches_train_reference"] = variant_match
        row["hands_visible"] = hands_visible
        row["motion_visible_enough"] = motion_visible
        row["recommended_action"] = action
        row["review_notes"] = note
        action_counts[action] += 1
        status_counts[status] += 1

    _write_csv(queue_path, rows, QUEUE_FIELDS)
    payload = {
        "experiment": "e4_h_bye_no_yes_variant_intervention_v1",
        "run_dir": str(run_dir),
        "rows": len(rows),
        "mode": "conservative_auto_triage",
        "warning": "This is not ASL-fluent semantic review. Critical rows are marked needs_second_review.",
        "review_status_counts": dict(status_counts),
        "recommended_action_counts": dict(action_counts),
        "queue": str(queue_path),
    }
    _write_json(run_dir / "summary" / "autofill_summary.json", payload)
    print(json.dumps(payload, indent=2))
    return 0
def summarize(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.resolve()
    queue_path = run_dir / "variant_review_queue.csv"
    if not queue_path.exists():
        raise FileNotFoundError(f"missing review queue: {queue_path}")
    rows = _read_csv(queue_path)
    errors: list[str] = []
    reviewed = 0
    for index, row in enumerate(rows, start=1):
        if row.get("review_status", "").strip():
            reviewed += 1
            errors.extend(_validate_review_row(row, index))
    if args.require_reviewed and reviewed != len(rows):
        errors.append(f"reviewed rows {reviewed} below required {len(rows)}")
    summary = {
        "experiment": "e4_h_bye_no_yes_variant_intervention_v1",
        "run_dir": str(run_dir),
        "rows": len(rows),
        "reviewed": reviewed,
        "remaining": len(rows) - reviewed,
        "review_status_counts": dict(Counter(row.get("review_status", "") or "blank" for row in rows)),
        "label_correct_counts": dict(Counter(row.get("label_correct", "") or "blank" for row in rows)),
        "variant_group_counts": dict(Counter(row.get("variant_group", "") or "blank" for row in rows)),
        "variant_match_counts": dict(Counter(row.get("variant_matches_train_reference", "") or "blank" for row in rows)),
        "action_counts": dict(Counter(row.get("recommended_action", "") or "blank" for row in rows)),
        "action_by_true_gloss": dict(Counter(f"{row.get('true_gloss','')}:{row.get('recommended_action','') or 'blank'}" for row in rows)),
        "errors": errors,
        "passed": not errors,
    }
    _write_json(run_dir / "summary" / "review_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if not errors else 1


def check(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.resolve()
    errors: list[str] = []
    required = [
        run_dir / "variant_review_queue.csv",
        run_dir / "USER_REVIEW_GUIDE.md",
        run_dir / "review.html",
        run_dir / "summary" / "prepare_summary.json",
    ]
    for path in required:
        if not path.exists():
            errors.append(f"missing required file: {path}")
    panels = list((run_dir / "panels").glob("*.jpg")) if (run_dir / "panels").exists() else []
    sheets = list((run_dir / "contact_sheets").glob("*.jpg")) if (run_dir / "contact_sheets").exists() else []
    if len(panels) < 80:
        errors.append(f"expected at least 80 copied panels, found {len(panels)}")
    if len(sheets) < 6:
        errors.append(f"expected at least 6 contact sheets, found {len(sheets)}")
    queue_rows = _read_csv(run_dir / "variant_review_queue.csv") if (run_dir / "variant_review_queue.csv").exists() else []
    if len(queue_rows) != len(panels):
        errors.append(f"queue rows {len(queue_rows)} do not match panels {len(panels)}")
    if args.require_reviewed:
        reviewed = sum(1 for row in queue_rows if row.get("review_status", "").strip())
        if reviewed != len(queue_rows):
            errors.append(f"reviewed rows {reviewed} below required {len(queue_rows)}")
        for index, row in enumerate(queue_rows, start=1):
            errors.extend(_validate_review_row(row, index))
    payload = {"run_dir": str(run_dir), "rows": len(queue_rows), "panels": len(panels), "contact_sheets": len(sheets), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", payload)
    print(json.dumps(payload, indent=2))
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    prep = sub.add_parser("prepare")
    prep.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    prep.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    prep.add_argument("--overwrite", action="store_true")
    prep.set_defaults(func=prepare)

    auto = sub.add_parser("autofill")
    auto.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    auto.add_argument("--overwrite", action="store_true")
    auto.set_defaults(func=autofill)

    summ = sub.add_parser("summarize")
    summ.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    summ.add_argument("--require-reviewed", action="store_true")
    summ.set_defaults(func=summarize)

    chk = sub.add_parser("check")
    chk.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    chk.add_argument("--require-reviewed", action="store_true")
    chk.set_defaults(func=check)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001 - command-line experiment should report concise failures.
        print(f"[e4-h] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
