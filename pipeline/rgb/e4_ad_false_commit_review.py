"""E4-AD signing-gate false-commit review and hard-negative mining.

Uses the best E4-AC low-motion-aware signing gate to find residual real no-sign
false commits, generate visual panels, and prepare train/validation hard-negative
candidates for the next gate iteration without leaking test labels into training.

Experiment-only: no Android assets, model exports, production recognizer files,
or source datasets are modified.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.rgb.e4_aa_nosign_temporal_gate import _combined_dataset, _write_json
from pipeline.rgb.e4_x_routed_system_validation import _apply_policy, _load_json, _seed_predictions
from pipeline.rgb.e4_z_signing_gate import _policy

DEFAULT_E4AC_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_ac_low_motion_aware_gate_01")
DEFAULT_E4AA_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_01")
DEFAULT_PRIMARY_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01")
DEFAULT_SPECIALIST_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01")
DEFAULT_E4X_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_x_routed_system_validation_01")
DEFAULT_N0_RUN = Path("artifacts/recognition_upgrade/e2e_c0/n0_capture_06")
DEFAULT_P1_RUN = Path("artifacts/recognition_upgrade/e2e_c0/p1_capture_03")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_ad_false_commit_review_01")
FINAL_CLASSES = ["GOOD", "HELLO", "HAVE", "KNOW", "SORRY", "NO_SIGN"]
NO_SIGN_ID = 5
SPLITS = {"train": 0, "val": 1, "test": 2}
SPLIT_NAMES = {0: "train", 1: "val", 2: "test"}


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


def _capture_video_map(*run_dirs: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for run_dir in run_dirs:
        path = run_dir / "capture_manifest.csv"
        if not path.exists():
            continue
        for row in _read_csv(path):
            out[row["clip_id"]] = row["video_path"]
    return out


def _nosign_manifest(path: Path) -> dict[str, dict[str, str]]:
    return {row["sample_id"]: row for row in _read_csv(path)}


def _fit_panel(frame: Any, width: int = 260, height: int = 190) -> Any:
    import cv2

    h, w = frame.shape[:2]
    scale = min(width / max(w, 1), height / max(h, 1))
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_NEAREST)
    top = (height - new_h) // 2
    bottom = height - new_h - top
    left = (width - new_w) // 2
    right = width - new_w - left
    return cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(245, 245, 245))


def _make_panel(row: dict[str, Any], out_path: Path, frames_each_side: int = 2) -> str:
    import cv2

    video_path = Path(str(row.get("video_path", "")))
    if not video_path.exists():
        return "missing_video"
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return "open_failed"
    center = int(float(row.get("frame_index", 0) or 0))
    fps = float(capture.get(cv2.CAP_PROP_FPS) or row.get("native_fps", 30) or 30)
    step = max(1, int(round(fps * 0.25)))
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frames = []
    for offset in range(-frames_each_side, frames_each_side + 1):
        index = max(0, min(max(total - 1, 0), center + offset * step))
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok:
            frame = np.full((190, 260, 3), 210, dtype=np.uint8)
            cv2.putText(frame, "MISS", (80, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 200), 2)
        cv2.putText(frame, f"f{index}", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        frames.append(_fit_panel(frame))
    capture.release()
    strip = cv2.hconcat(frames)
    header = np.full((76, strip.shape[1], 3), 30, dtype=np.uint8)
    title = f"{row['review_type']} seed={row['seed']} true=NO_SIGN pred={row['predicted_gloss']} p={float(row['sign_probability']):.4f} split={row['split']} src={row['source_kind']}"
    meta = f"{row['sample_id']} clip={row.get('clip_id','')} t={row.get('timestamp_ms','')} hand={row.get('hand_hit_rate_window','')} pose={row.get('pose_hit_rate_window','')}"
    cv2.putText(header, title[:170], (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(header, meta[:190], (8, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (210, 210, 210), 1, cv2.LINE_AA)
    panel = cv2.vconcat([header, strip])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(out_path), panel, [cv2.IMWRITE_JPEG_QUALITY, 92]):
        return "write_failed"
    return "ok"


def _contact_sheet(panel_paths: list[Path], out_path: Path, columns: int = 2) -> None:
    if not panel_paths:
        return
    from PIL import Image, ImageDraw

    thumbs = []
    for path in panel_paths:
        img = Image.open(path).convert("RGB")
        img.thumbnail((680, 250))
        canvas = Image.new("RGB", (680, 250), "white")
        canvas.paste(img, ((680 - img.width) // 2, (250 - img.height) // 2))
        thumbs.append(canvas)
    rows = (len(thumbs) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * 680, rows * 250 + 40), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((10, 10), out_path.stem, fill=(0, 0, 0))
    for idx, img in enumerate(thumbs):
        x = (idx % columns) * 680
        y = 40 + (idx // columns) * 250
        sheet.paste(img, (x, y))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=92)


def _predictions(args: argparse.Namespace, data: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    import tensorflow as tf

    primary_config = _load_json(args.primary_run / "pilot_config.json", "E4-S config")
    specialist_config = _load_json(args.specialist_run / "pilot_config.json", "E4-V config")
    route_policy = _policy(args.e4x_run)
    ac_metrics = _load_json(args.e4ac_run / "metrics" / "low_motion_gate_metrics.json", "E4-AC metrics")
    rows: list[dict[str, Any]] = []
    for seed in [int(seed) for seed in args.seeds]:
        model_path = args.e4ac_run / "models" / f"seed_{seed}" / "low_motion_signing_gate.keras"
        if not model_path.exists():
            raise FileNotFoundError(f"missing E4-AC model: {model_path}")
        threshold = float(ac_metrics["seed_results"][str(seed)]["threshold"])
        tf.keras.backend.clear_session()
        model = tf.keras.models.load_model(model_path)
        probs = model.predict(data["landmarks"], batch_size=int(args.batch_size), verbose=0).reshape(-1)
        routed = _seed_predictions(seed, args.primary_run, args.specialist_run, primary_config, specialist_config, data)
        routed_final = _apply_policy(routed, route_policy)
        final = routed_final.copy()
        final[probs < threshold] = NO_SIGN_ID
        no_sign_indices = np.where(data["y_final"] == NO_SIGN_ID)[0]
        for idx in no_sign_indices.tolist():
            rows.append({
                "seed": seed,
                "sample_id": str(data["sample_ids"][idx]),
                "split": SPLIT_NAMES[int(data["split_index"][idx])],
                "source_kind": str(data["source"][idx]),
                "routed_gloss": FINAL_CLASSES[int(routed_final[idx])],
                "predicted_gloss": FINAL_CLASSES[int(final[idx])],
                "pred_id": int(final[idx]),
                "sign_probability": float(probs[idx]),
                "threshold": threshold,
                "false_commit": bool(final[idx] != NO_SIGN_ID),
            })
    return rows


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    for relative in ("review", "panels", "contact_sheets", "logs"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    data = _combined_dataset(args.primary_run, args.e4aa_run)
    pred_rows = _predictions(args, data)
    manifest_by_id = _nosign_manifest(args.e4aa_run / "dataset" / "nosign_manifest.csv")
    video_by_clip = _capture_video_map(args.n0_run, args.p1_run)

    enriched: list[dict[str, Any]] = []
    for row in pred_rows:
        meta = manifest_by_id.get(row["sample_id"], {})
        item = {**row, **meta}
        item["video_path"] = video_by_clip.get(str(meta.get("clip_id", "")), "")
        if row["false_commit"]:
            item["review_type"] = "false_commit"
        elif row["split"] in {"train", "val"} and float(row["sign_probability"]) >= float(args.hard_negative_probability_min):
            item["review_type"] = "hard_negative_candidate"
        else:
            item["review_type"] = "background"
        enriched.append(item)

    false_commits = [row for row in enriched if row["review_type"] == "false_commit"]
    hard_candidates = [row for row in enriched if row["review_type"] == "hard_negative_candidate"]
    review_rows = false_commits + hard_candidates[: int(args.max_hard_negative_panels)]
    panel_paths: list[Path] = []
    for idx, row in enumerate(review_rows, start=1):
        safe = f"{idx:04d}_{row['review_type']}_seed{row['seed']}_{row['split']}_{row['source_kind']}_{row['predicted_gloss']}_{row['sample_id']}.jpg"
        panel_path = output / "panels" / safe
        status = _make_panel(row, panel_path)
        row["panel_status"] = status
        row["panel_path"] = str(panel_path.resolve()) if status == "ok" else ""
        if status == "ok":
            panel_paths.append(panel_path)
    false_paths = [Path(row["panel_path"]) for row in review_rows if row.get("review_type") == "false_commit" and row.get("panel_path")]
    hard_paths = [Path(row["panel_path"]) for row in review_rows if row.get("review_type") == "hard_negative_candidate" and row.get("panel_path")]
    _contact_sheet(false_paths, output / "contact_sheets" / "false_commits.jpg")
    _contact_sheet(hard_paths, output / "contact_sheets" / "hard_negative_candidates.jpg")

    fields = [
        "review_type", "seed", "sample_id", "split", "source_kind", "routed_gloss", "predicted_gloss", "sign_probability", "threshold",
        "clip_id", "participant_id", "device_id", "environment_id", "camera_facing", "timestamp_ms", "frame_index", "window_onset", "window_release",
        "hand_hit_rate_window", "pose_hit_rate_window", "video_path", "panel_status", "panel_path",
    ]
    _write_csv(output / "review" / "false_commit_manifest.csv", false_commits, fields)
    _write_csv(output / "review" / "hard_negative_candidates.csv", hard_candidates, fields)
    _write_csv(output / "review" / "review_queue.csv", review_rows, fields)

    false_counts = Counter(f"{row['split']}:{row['source_kind']}->{row['predicted_gloss']}" for row in false_commits)
    hard_counts = Counter(f"{row['split']}:{row['source_kind']}" for row in hard_candidates)
    summary = {
        "experiment": "e4_ad_false_commit_review_v1",
        "run_dir": str(output.resolve()),
        "e4ac_run": str(args.e4ac_run.resolve()),
        "e4aa_run": str(args.e4aa_run.resolve()),
        "false_commit_rows": len(false_commits),
        "hard_negative_candidate_rows": len(hard_candidates),
        "review_queue_rows": len(review_rows),
        "panel_count": len(panel_paths),
        "false_commit_counts": dict(sorted(false_counts.items())),
        "hard_negative_counts": dict(sorted(hard_counts.items())),
        "hard_negative_probability_min": float(args.hard_negative_probability_min),
        "decision": "review_false_commits_before_hard_negative_training",
        "warnings": [
            "Review/test false commits are diagnostic only; do not add test rows to training.",
            "Use train/val hard-negative candidates for the next training iteration to avoid test leakage.",
            "No Android/export is authorized from this evidence package.",
        ],
    }
    _write_json(output / "logs" / "run_summary.json", summary)
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["review/false_commit_manifest.csv", "review/hard_negative_candidates.csv", "review/review_queue.csv", "logs/run_summary.json"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if args.require_panels:
        queue = _read_csv(run_dir / "review" / "review_queue.csv") if (run_dir / "review" / "review_queue.csv").exists() else []
        missing = [row.get("panel_path", "") for row in queue if not row.get("panel_path") or not Path(row["panel_path"]).exists()]
        if missing:
            errors.append(f"missing review panels: {len(missing)}")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-AD false-commit review and hard-negative mining")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--e4ac-run", type=Path, default=DEFAULT_E4AC_RUN)
    run_parser.add_argument("--e4aa-run", type=Path, default=DEFAULT_E4AA_RUN)
    run_parser.add_argument("--primary-run", type=Path, default=DEFAULT_PRIMARY_RUN)
    run_parser.add_argument("--specialist-run", type=Path, default=DEFAULT_SPECIALIST_RUN)
    run_parser.add_argument("--e4x-run", type=Path, default=DEFAULT_E4X_RUN)
    run_parser.add_argument("--n0-run", type=Path, default=DEFAULT_N0_RUN)
    run_parser.add_argument("--p1-run", type=Path, default=DEFAULT_P1_RUN)
    run_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    run_parser.add_argument("--batch-size", type=int, default=16)
    run_parser.add_argument("--hard-negative-probability-min", type=float, default=0.001)
    run_parser.add_argument("--max-hard-negative-panels", type=int, default=40)

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--require-panels", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-ad] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
