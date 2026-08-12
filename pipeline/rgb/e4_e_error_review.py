"""E4-E focused error-review package for the E4-D same-provenance pilot.

This is an experiment-only diagnostic. It loads an already-trained E4-D checkpoint, recreates
per-sample predictions, and builds a manual review package for the failed held-out signs.
It does not train, export models, or modify Android/runtime assets.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.rgb.e3_b4_landmark_temporal import _build_model, _inputs_for

DEFAULT_SOURCE_RUN = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_d_stage_e_same_provenance_pilot_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_e_error_review_01"
)
DEFAULT_BRANCH = "tcn_masked_pool"
DEFAULT_SEED = 303
DEFAULT_TARGETS = ["BYE", "THANKYOU", "NO"]
DEFAULT_REFERENCE_CLASSES = ["YES", "SORRY", "GOOD"]
SPLIT_NAMES = {0: "train", 1: "val", 2: "test"}
MANUAL_FIELDS = [
    "review_status",
    "label_correct",
    "sign_variant_matches_target",
    "hands_visible",
    "landmark_problem_visible",
    "too_blurry_or_occluded",
    "ambiguous_even_to_reviewer",
    "recommended_action",
    "review_notes",
]
REVIEW_STATUS_VALUES = {"done", "skip", "needs_second_review"}
YES_NO_UNSURE = {"yes", "no", "unsure"}
HANDS_VISIBLE_VALUES = {"yes", "partial", "no"}
ACTION_VALUES = {"keep", "relabel", "quarantine", "recollect", "merge_variant", "needs_second_review"}


@dataclass(frozen=True)
class ReviewDecision:
    key: str
    label: str
    color: str
    review_status: str
    label_correct: str
    sign_variant_matches_target: str
    hands_visible: str
    landmark_problem_visible: str
    too_blurry_or_occluded: str
    ambiguous_even_to_reviewer: str
    recommended_action: str


DECISIONS = (
    ReviewDecision("1", "Keep: label and variant look correct", "#18794e", "done", "yes", "yes", "yes", "no", "no", "no", "keep"),
    ReviewDecision("2", "Variant mismatch: same idea, different sign style", "#8a6116", "done", "yes", "no", "yes", "no", "no", "no", "merge_variant"),
    ReviewDecision("3", "Wrong label: should be relabeled", "#b54708", "done", "no", "no", "yes", "no", "no", "no", "relabel"),
    ReviewDecision("4", "Hands not visible enough: recollect", "#b42318", "done", "yes", "unsure", "partial", "yes", "yes", "no", "recollect"),
    ReviewDecision("5", "Landmark/crop problem visible", "#6b4f9b", "done", "yes", "yes", "yes", "yes", "no", "no", "recollect"),
    ReviewDecision("6", "Too blurry or occluded", "#b42318", "done", "yes", "unsure", "partial", "unsure", "yes", "no", "recollect"),
    ReviewDecision("7", "Ambiguous: needs second review", "#525252", "needs_second_review", "unsure", "unsure", "partial", "unsure", "unsure", "yes", "needs_second_review"),
    ReviewDecision("8", "Skip/quarantine this row", "#3f3f46", "skip", "unsure", "unsure", "partial", "unsure", "unsure", "yes", "quarantine"),
)
DECISION_BY_KEY = {decision.key: decision for decision in DECISIONS}


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


def _load_dataset(source_run: Path) -> dict[str, np.ndarray]:
    path = source_run / "dataset" / "landmark_features.npz"
    if not path.exists():
        raise FileNotFoundError(f"missing E4-D dataset: {path}")
    data = np.load(path, allow_pickle=False)
    required = {"landmarks", "frame_mask", "y", "split_index", "lengths", "sample_ids"}
    missing = required.difference(data.files)
    if missing:
        raise ValueError(f"dataset missing keys: {sorted(missing)}")
    landmarks = data["landmarks"].astype(np.float32)
    if landmarks.ndim != 3 or tuple(landmarks.shape[1:]) != (96, 258):
        raise ValueError(f"expected [N,96,258] landmarks, got {list(landmarks.shape)}")
    return {
        "landmarks": landmarks,
        "frame_mask": data["frame_mask"].astype(bool),
        "y": data["y"].astype(np.int64),
        "split_index": data["split_index"].astype(np.int64),
        "lengths": data["lengths"].astype(np.int32),
        "sample_ids": np.asarray(data["sample_ids"]).astype(str),
    }


def _load_config(source_run: Path) -> dict[str, Any]:
    path = source_run / "pilot_config.json"
    if not path.exists():
        raise FileNotFoundError(f"missing E4-D config: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _predict(source_run: Path, branch: str, seed: int, batch_size: int) -> tuple[dict[str, Any], np.ndarray]:
    config = _load_config(source_run)
    dataset = _load_dataset(source_run)
    weights = source_run / "models" / branch / f"seed_{seed}" / "best.weights.h5"
    if not weights.exists():
        raise FileNotFoundError(f"missing best checkpoint: {weights}")
    model = _build_model(branch, (96, 258), int(config["class_count"]), float(config["learning_rate"]))
    model.load_weights(weights)
    probs = model.predict(
        _inputs_for(branch, dataset["landmarks"], dataset["frame_mask"]),
        batch_size=batch_size,
        verbose=0,
    )
    return dataset, probs


def _topk(probs: np.ndarray, classes: list[str], k: int = 3) -> list[list[tuple[str, float]]]:
    order = np.argsort(-probs, axis=1)[:, :k]
    out = []
    for row_index, indexes in enumerate(order):
        out.append([(classes[int(index)], float(probs[row_index, int(index)])) for index in indexes])
    return out


def _build_prediction_rows(
    source_run: Path,
    config: dict[str, Any],
    dataset: dict[str, np.ndarray],
    probs: np.ndarray,
    branch: str,
    seed: int,
) -> list[dict[str, Any]]:
    manifest = {row["sample_id"]: row for row in _read_csv(source_run / "pilot_manifest.csv")}
    extraction_manifest_path = source_run / "logs" / "feature_extraction_manifest.csv"
    extracted = {}
    if extraction_manifest_path.exists():
        extracted = {row["sample_id"]: row for row in _read_csv(extraction_manifest_path)}
    classes = list(config["classes"])
    top_rows = _topk(probs, classes, 3)
    rows = []
    for index, sample_id in enumerate(dataset["sample_ids"]):
        base = manifest.get(sample_id, {})
        extra = extracted.get(sample_id, {})
        truth_index = int(dataset["y"][index])
        pred_index = int(np.argmax(probs[index]))
        top = top_rows[index]
        row = {
            "sample_index": index,
            "sample_id": sample_id,
            "split": SPLIT_NAMES.get(int(dataset["split_index"][index]), str(int(dataset["split_index"][index]))),
            "true_gloss": classes[truth_index],
            "pred_gloss": classes[pred_index],
            "correct": str(pred_index == truth_index),
            "confidence": f"{float(np.max(probs[index])):.6f}",
            "top1": top[0][0],
            "top1_confidence": f"{top[0][1]:.6f}",
            "top2": top[1][0],
            "top2_confidence": f"{top[1][1]:.6f}",
            "top3": top[2][0],
            "top3_confidence": f"{top[2][1]:.6f}",
            "length": int(dataset["lengths"][index]),
            "model_branch": branch,
            "model_seed": seed,
            "signer_id": base.get("signer_id", ""),
            "source_folder": base.get("source_folder", ""),
            "folder_word": base.get("folder_word", ""),
            "session_id": base.get("session_id", ""),
            "repetition_index": base.get("repetition_index", ""),
            "video_path": base.get("video_path", ""),
            "manifest_hand_hit_rate": base.get("hand_hit_rate", ""),
            "extracted_hand_hit_rate": extra.get("hand_hit_rate_extracted", ""),
            "pose_hit_rate_extracted": extra.get("pose_hit_rate_extracted", ""),
            "native_frames_extracted": extra.get("native_frames_extracted", ""),
            "native_fps_extracted": extra.get("native_fps_extracted", ""),
        }
        rows.append(row)
    return rows


def _selected_review_rows(
    rows: list[dict[str, Any]],
    targets: set[str],
    reference_classes: set[str],
    max_reference_per_class: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used = set()

    def add(row: dict[str, Any], reason: str, priority: int) -> None:
        sample_id = row["sample_id"]
        if sample_id in used:
            return
        used.add(sample_id)
        selected.append({**row, "review_reason": reason, "review_priority": priority})

    for row in rows:
        if row["split"] == "test" and row["true_gloss"] in targets and row["correct"] != "True":
            add(row, "target_test_error", 1)
    for row in rows:
        if row["split"] == "test" and row["true_gloss"] in targets and row["correct"] == "True":
            add(row, "target_test_correct_reference", 2)

    by_ref: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["split"] == "test" and row["true_gloss"] in reference_classes:
            by_ref[row["true_gloss"]].append(row)
    for gloss in sorted(by_ref):
        for row in by_ref[gloss][:max_reference_per_class]:
            add(row, "confusion_class_test_reference", 3)

    by_split_target: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["split"] in {"train", "val"} and row["true_gloss"] in targets:
            by_split_target[(row["split"], row["true_gloss"])].append(row)
    for key in sorted(by_split_target):
        for row in by_split_target[key][:max_reference_per_class]:
            add(row, f"{key[0]}_target_reference", 4)

    return sorted(selected, key=lambda row: (int(row["review_priority"]), row["true_gloss"], row["sample_id"]))


def _make_panel(video_path: Path, output_path: Path, title: str, frames_per_panel: int) -> dict[str, Any]:
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("OpenCV is required for panel generation") from error

    output_path.parent.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        image = np.zeros((280, 280, 3), dtype=np.uint8)
        cv2.putText(image, "VIDEO OPEN FAILED", (12, 135), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        cv2.imwrite(str(output_path), image)
        return {"panel_path": str(output_path.resolve()), "panel_status": "video_open_failed", "frames_rendered": 0}

    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        total = frames_per_panel
    indexes = np.linspace(0, max(total - 1, 0), num=frames_per_panel, dtype=int)
    frames = []
    for index in indexes:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = capture.read()
        if not ok or frame is None:
            frame = np.zeros((224, 224, 3), dtype=np.uint8)
            cv2.putText(frame, "MISS", (55, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        frame = cv2.resize(frame, (224, 224), interpolation=cv2.INTER_AREA)
        cv2.putText(frame, f"f{int(index)}", (8, 215), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        frames.append(frame)
    capture.release()

    strip = np.concatenate(frames, axis=1)
    header = np.zeros((70, strip.shape[1], 3), dtype=np.uint8)
    cv2.putText(header, title[:150], (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    cv2.putText(header, str(video_path)[-150:], (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1)
    panel = np.concatenate([header, strip], axis=0)
    cv2.imwrite(str(output_path), panel)
    return {"panel_path": str(output_path.resolve()), "panel_status": "ok", "frames_rendered": len(frames)}


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    source_run = args.source_run
    output = args.output
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("predictions", "review_panels", "logs"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    config = _load_config(source_run)
    dataset, probs = _predict(source_run, args.branch, args.seed, args.batch_size)
    prediction_rows = _build_prediction_rows(source_run, config, dataset, probs, args.branch, args.seed)
    fields = list(prediction_rows[0].keys())
    _write_csv(output / "predictions" / "all_predictions.csv", prediction_rows, fields)

    review_rows = _selected_review_rows(
        prediction_rows,
        set(args.targets),
        set(args.reference_classes),
        int(args.max_reference_per_class),
    )
    review_fields = [
        "queue_id",
        "panel_path",
        "panel_status",
        "frames_rendered",
        "review_reason",
        "review_priority",
        *fields,
        *MANUAL_FIELDS,
    ]
    panel_rows = []
    for queue_index, row in enumerate(review_rows, start=1):
        safe_name = f"{queue_index:04d}_{row['split']}_{row['true_gloss']}_pred-{row['pred_gloss']}_{row['sample_id']}.jpg"
        safe_name = safe_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        panel_path = output / "review_panels" / safe_name
        title = (
            f"{queue_index:04d} {row['split']} true={row['true_gloss']} pred={row['pred_gloss']} "
            f"conf={row['confidence']} reason={row['review_reason']}"
        )
        panel_info = _make_panel(Path(str(row["video_path"])), panel_path, title, int(args.frames_per_panel))
        panel_rows.append(
            {
                "queue_id": f"{queue_index:04d}",
                **panel_info,
                **row,
                **{field: "" for field in MANUAL_FIELDS},
            }
        )
    _write_csv(output / "review_queue.csv", panel_rows, review_fields)

    summary = _automatic_summary(source_run, output, config, prediction_rows, panel_rows, args)
    _write_json(output / "summary.json", summary)
    (output / "README_REVIEW.md").write_text(_review_readme(summary), encoding="utf-8")
    return summary


def _automatic_summary(
    source_run: Path,
    output: Path,
    config: dict[str, Any],
    predictions: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    test_rows = [row for row in predictions if row["split"] == "test"]
    target_test = [row for row in test_rows if row["true_gloss"] in set(args.targets)]
    confusion = Counter((row["true_gloss"], row["pred_gloss"]) for row in target_test if row["correct"] != "True")
    per_class = {}
    for gloss in config["classes"]:
        class_rows = [row for row in test_rows if row["true_gloss"] == gloss]
        if class_rows:
            per_class[gloss] = {
                "rows": len(class_rows),
                "correct": sum(row["correct"] == "True" for row in class_rows),
                "accuracy": sum(row["correct"] == "True" for row in class_rows) / len(class_rows),
            }
    return {
        "experiment": "e4_e_focused_error_review_v1",
        "purpose": "manual review package for the failed E4-D held-out signs before collecting/training more data",
        "source_run": str(source_run.resolve()),
        "run_dir": str(output.resolve()),
        "model_branch": args.branch,
        "model_seed": int(args.seed),
        "classes": list(config["classes"]),
        "targets": list(args.targets),
        "reference_classes": list(args.reference_classes),
        "prediction_rows": len(predictions),
        "review_rows": len(review_rows),
        "review_reason_counts": dict(Counter(row["review_reason"] for row in review_rows)),
        "test_per_class": per_class,
        "target_error_confusions": {f"{true}->{pred}": count for (true, pred), count in sorted(confusion.items())},
        "outputs": {
            "review_queue": str((output / "review_queue.csv").resolve()),
            "all_predictions": str((output / "predictions" / "all_predictions.csv").resolve()),
            "review_panels": str((output / "review_panels").resolve()),
            "readme": str((output / "README_REVIEW.md").resolve()),
        },
        "passed": True,
    }


def _review_readme(summary: dict[str, Any]) -> str:
    run_dir = summary["run_dir"]
    return "\n".join(
        [
            "# E4-E Focused Error Review",
            "",
            "This package reviews why E4-D failed on `BYE`, `THANKYOU`, and `NO` before we collect more data or train again.",
            "",
            "## What To Open",
            "",
            f"- Review CSV: `{summary['outputs']['review_queue']}`",
            f"- Visual panels: `{summary['outputs']['review_panels']}`",
            f"- All predictions: `{summary['outputs']['all_predictions']}`",
            "",
            "## How To Review Each Row",
            "",
            "For each row in `review_queue.csv`, open the `panel_path` image and fill the manual columns:",
            "",
            "- `review_status`: `done`, `skip`, or `needs_second_review`.",
            "- `label_correct`: `yes`, `no`, or `unsure`.",
            "- `sign_variant_matches_target`: `yes`, `no`, or `unsure`.",
            "- `hands_visible`: `yes`, `partial`, or `no`.",
            "- `landmark_problem_visible`: `yes`, `no`, or `unsure`.",
            "- `too_blurry_or_occluded`: `yes`, `no`, or `unsure`.",
            "- `ambiguous_even_to_reviewer`: `yes`, `no`, or `unsure`.",
            "- `recommended_action`: `keep`, `relabel`, `quarantine`, `recollect`, `merge_variant`, or `needs_second_review`.",
            "- `review_notes`: short explanation when useful.",
            "",
            "## Check",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_e_error_review check --run-dir "{run_dir}"',
            "```",
            "",
            "After manual review, run:",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_e_error_review summarize --run-dir "{run_dir}" --require-reviewed',
            "```",
            "",
        ]
    )



def _manual_completion_error(row: dict[str, str]) -> str | None:
    if row.get("review_status", "") not in REVIEW_STATUS_VALUES:
        return "review_status must be done, skip, or needs_second_review"
    if row.get("label_correct", "") not in YES_NO_UNSURE:
        return "label_correct must be yes, no, or unsure"
    if row.get("sign_variant_matches_target", "") not in YES_NO_UNSURE:
        return "sign_variant_matches_target must be yes, no, or unsure"
    if row.get("hands_visible", "") not in HANDS_VISIBLE_VALUES:
        return "hands_visible must be yes, partial, or no"
    for field in ("landmark_problem_visible", "too_blurry_or_occluded", "ambiguous_even_to_reviewer"):
        if row.get(field, "") not in YES_NO_UNSURE:
            return f"{field} must be yes, no, or unsure"
    if row.get("recommended_action", "") not in ACTION_VALUES:
        return "recommended_action has an unsupported value"
    return None


def _review_status(rows: list[dict[str, str]]) -> dict[str, int]:
    completed = sum(_manual_completion_error(row) is None for row in rows)
    return {"total": len(rows), "completed": completed, "remaining": len(rows) - completed}


def _save_review_atomic(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class ReviewApp:
    def __init__(self, review_path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
        import tkinter as tk
        import cv2

        self._tk = tk
        self._cv2 = cv2
        self._review_path = review_path
        self._rows = rows
        self._fields = fields
        self._index = next(
            (index for index, row in enumerate(rows) if _manual_completion_error(row) is not None),
            max(len(rows) - 1, 0),
        )
        self._photo: Any = None

        self._root = tk.Tk()
        self._root.title("AppHear E4-E Error Review")
        self._root.configure(bg="#171717")
        self._root.geometry("1280x860")
        self._root.minsize(980, 680)

        self._progress = tk.Label(self._root, fg="white", bg="#171717", font=("Segoe UI", 13, "bold"))
        self._progress.pack(pady=(10, 2))
        self._details = tk.Label(self._root, fg="#d8d8d8", bg="#171717", font=("Segoe UI", 10), justify="left")
        self._details.pack(fill="x", padx=16, pady=(0, 3))
        self._message = tk.Label(self._root, fg="#ffd166", bg="#171717", font=("Segoe UI", 11, "bold"))
        self._message.pack(pady=(0, 4))

        self._image = tk.Label(self._root, bg="#111111")
        self._image.pack(fill="both", expand=True, padx=16, pady=5)

        self._notes = tk.Entry(self._root, font=("Segoe UI", 11))
        self._notes.pack(fill="x", padx=16, pady=(4, 8))

        controls = tk.Frame(self._root, bg="#171717")
        controls.pack(fill="x", padx=16, pady=(0, 8))
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
                wraplength=260,
            )
            button.grid(row=column // 2, column=column % 2, sticky="ew", padx=4, pady=3)
        for column in range(2):
            controls.grid_columnconfigure(column, weight=1)

        navigation = tk.Frame(self._root, bg="#171717")
        navigation.pack(fill="x", padx=16, pady=(0, 12))
        tk.Button(navigation, text="Previous (P)", command=self._previous).pack(side="left")
        tk.Button(navigation, text="Clear current row", command=self._clear_current).pack(side="left", padx=6)
        tk.Button(navigation, text="Exit and save (Esc)", command=self._close).pack(side="right")

        for key, decision in DECISION_BY_KEY.items():
            self._root.bind(key, partial(self._mark_from_event, decision))
        self._root.bind("p", self._previous_from_event)
        self._root.bind("<Escape>", self._close_from_event)
        self._root.protocol("WM_DELETE_WINDOW", self._close)
        self._show()

    def run(self) -> None:
        self._root.mainloop()

    def _row(self) -> dict[str, str]:
        return self._rows[self._index]

    def _show(self) -> None:
        row = self._row()
        status = _review_status(self._rows)
        self._progress.configure(
            text=f"Row {self._index + 1}/{status['total']} | completed {status['completed']} | remaining {status['remaining']}"
        )
        self._details.configure(
            text=(
                f"queue={row.get('queue_id')} reason={row.get('review_reason')} split={row.get('split')} "
                f"true={row.get('true_gloss')} pred={row.get('pred_gloss')} conf={row.get('confidence')}\n"
                f"top2={row.get('top2')} {row.get('top2_confidence')} | top3={row.get('top3')} {row.get('top3_confidence')} | "
                f"signer={row.get('signer_id')} source={row.get('source_folder')} word={row.get('folder_word')} | "
                f"hand_hit={row.get('extracted_hand_hit_rate')}"
            )
        )
        self._notes.delete(0, self._tk.END)
        self._notes.insert(0, row.get("review_notes", ""))
        error = _manual_completion_error(row)
        self._message.configure(text=("Already reviewed. You can change the decision." if error is None else "Choose the best decision button. Notes are optional."))
        self._render_panel(row["panel_path"])

    def _render_panel(self, path: str) -> None:
        image = self._cv2.imread(path, self._cv2.IMREAD_COLOR)
        if image is None:
            raise OSError(f"cannot read panel: {path}")
        max_width = max(self._root.winfo_width() - 70, 900)
        max_height = max(self._root.winfo_height() - 340, 360)
        scale = min(max_width / image.shape[1], max_height / image.shape[0], 2.0)
        if scale != 1.0:
            image = self._cv2.resize(
                image,
                (round(image.shape[1] * scale), round(image.shape[0] * scale)),
                interpolation=self._cv2.INTER_AREA if scale < 1.0 else self._cv2.INTER_NEAREST,
            )
        ok, encoded = self._cv2.imencode(".png", image)
        if not ok:
            raise OSError(f"cannot encode panel: {path}")
        data = base64.b64encode(encoded.tobytes()).decode("ascii")
        self._photo = self._tk.PhotoImage(data=data)
        self._image.configure(image=self._photo)

    def _mark(self, decision: ReviewDecision) -> None:
        row = self._row()
        row["review_status"] = decision.review_status
        row["label_correct"] = decision.label_correct
        row["sign_variant_matches_target"] = decision.sign_variant_matches_target
        row["hands_visible"] = decision.hands_visible
        row["landmark_problem_visible"] = decision.landmark_problem_visible
        row["too_blurry_or_occluded"] = decision.too_blurry_or_occluded
        row["ambiguous_even_to_reviewer"] = decision.ambiguous_even_to_reviewer
        row["recommended_action"] = decision.recommended_action
        row["review_notes"] = self._notes.get().strip()
        _save_review_atomic(self._review_path, self._rows, self._fields)
        self._advance()

    def _mark_from_event(self, decision: ReviewDecision, _event: object) -> None:
        self._mark(decision)

    def _advance(self) -> None:
        next_index = next(
            (index for index in range(self._index + 1, len(self._rows)) if _manual_completion_error(self._rows[index]) is not None),
            None,
        )
        if next_index is None:
            next_index = next((index for index, row in enumerate(self._rows) if _manual_completion_error(row) is not None), None)
        if next_index is None:
            self._message.configure(text="Review complete and saved. You can close this window.")
            return
        self._index = next_index
        self._show()

    def _previous(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._show()

    def _previous_from_event(self, _event: object) -> None:
        self._previous()

    def _clear_current(self) -> None:
        row = self._row()
        for field in MANUAL_FIELDS:
            row[field] = ""
        _save_review_atomic(self._review_path, self._rows, self._fields)
        self._show()

    def _close(self) -> None:
        _save_review_atomic(self._review_path, self._rows, self._fields)
        self._root.destroy()

    def _close_from_event(self, _event: object) -> None:
        self._close()


def open_review(run_dir: Path) -> None:
    queue_path = run_dir / "review_queue.csv"
    if not queue_path.exists():
        raise FileNotFoundError(f"missing review queue: {queue_path}")
    with queue_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    if not rows:
        raise ValueError("review_queue.csv is empty")
    missing = [row.get("panel_path", "") for row in rows if not Path(row.get("panel_path", "")).is_file()]
    if missing:
        raise FileNotFoundError(f"missing review panels: {len(missing)}; first={missing[0]}")
    backup = run_dir / "review_queue.pre_gui_backup.csv"
    if not backup.exists():
        shutil.copy2(queue_path, backup)
    ReviewApp(queue_path, rows, fields).run()
def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    for relative in ("summary.json", "README_REVIEW.md", "review_queue.csv", "predictions/all_predictions.csv"):
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    review_rows = []
    if (run_dir / "review_queue.csv").exists():
        review_rows = _read_csv(run_dir / "review_queue.csv")
        if not review_rows:
            errors.append("review_queue.csv is empty")
        missing_panels = [row.get("panel_path", "") for row in review_rows if not Path(row.get("panel_path", "")).exists()]
        if missing_panels:
            errors.append(f"missing review panels: {len(missing_panels)}")
        if args.require_reviewed:
            missing_review = [row["queue_id"] for row in review_rows if row.get("review_status", "").strip() == ""]
            if missing_review:
                errors.append(f"manual review incomplete: {len(missing_review)} rows")
    result = {
        "run_dir": str(run_dir.resolve()),
        "rows": len(review_rows),
        "passed": not errors,
        "errors": errors,
    }
    _write_json(run_dir / "check_report.json", result)
    return result


def summarize(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    queue_path = run_dir / "review_queue.csv"
    if not queue_path.exists():
        raise FileNotFoundError(f"missing review queue: {queue_path}")
    rows = _read_csv(queue_path)
    if args.require_reviewed:
        missing = [row["queue_id"] for row in rows if not row.get("review_status", "").strip()]
        if missing:
            raise ValueError(f"manual review incomplete: {len(missing)} rows; first={missing[:10]}")
    summary = {
        "experiment": "e4_e_focused_error_review_v1",
        "run_dir": str(run_dir.resolve()),
        "rows": len(rows),
        "review_status_counts": dict(Counter(row.get("review_status", "") for row in rows)),
        "recommended_action_counts": dict(Counter(row.get("recommended_action", "") for row in rows)),
        "label_correct_counts": dict(Counter(row.get("label_correct", "") for row in rows)),
        "variant_match_counts": dict(Counter(row.get("sign_variant_matches_target", "") for row in rows)),
        "hands_visible_counts": dict(Counter(row.get("hands_visible", "") for row in rows)),
        "blurry_or_occluded_counts": dict(Counter(row.get("too_blurry_or_occluded", "") for row in rows)),
        "target_action_counts": dict(
            Counter(
                f"{row.get('true_gloss', '')}:{row.get('recommended_action', '')}"
                for row in rows
                if row.get("true_gloss", "") in set(DEFAULT_TARGETS)
            )
        ),
        "passed": True,
    }
    _write_json(run_dir / "manual_review_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-E focused error-review package")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--branch", default=DEFAULT_BRANCH)
    prepare_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    prepare_parser.add_argument("--batch-size", type=int, default=8)
    prepare_parser.add_argument("--targets", nargs="+", default=DEFAULT_TARGETS)
    prepare_parser.add_argument("--reference-classes", nargs="+", default=DEFAULT_REFERENCE_CLASSES)
    prepare_parser.add_argument("--max-reference-per-class", type=int, default=8)
    prepare_parser.add_argument("--frames-per-panel", type=int, default=5)
    prepare_parser.add_argument("--overwrite", action="store_true")

    review_parser = sub.add_parser("review")
    review_parser.add_argument("--run-dir", type=Path, required=True)

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--require-reviewed", action="store_true")

    summarize_parser = sub.add_parser("summarize")
    summarize_parser.add_argument("--run-dir", type=Path, required=True)
    summarize_parser.add_argument("--require-reviewed", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "review":
            open_review(args.run_dir)
            result = {"run_dir": str(args.run_dir.resolve()), "review_window_closed": True}
        elif args.command == "check":
            result = check(args)
        elif args.command == "summarize":
            result = summarize(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileExistsError, FileNotFoundError, KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"[rgb/e4-e-review] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())







