"""E4-U reusable confusion-group evidence package.

Builds a compact evidence bundle for one primary false-commit group. The first use is
SORRY -> GOOD after E4-S/E4-T showed high-confidence false commits. This is not model
training; it prepares row manifests and contact sheets so the next specialist/data-repair
experiment is grounded in actual source videos and model predictions.
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
from PIL import Image, ImageDraw, ImageFont

DEFAULT_E4S_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01")
DEFAULT_E4T_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_t_router_simulation_01")
DEFAULT_E4J_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_j_reliable_core_3sign_pilot_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_u_sorry_good_evidence_01")
DEFAULT_TARGET = "SORRY"
DEFAULT_FALSE_COMMIT = "GOOD"
SPLITS = {"train": 0, "val": 1, "test": 2}


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


def _load_prediction_rows(e4t_run: Path, e4s_run: Path) -> dict[str, dict[str, Any]]:
    config = json.loads((e4s_run / "pilot_config.json").read_text(encoding="utf-8"))
    classes = list(config["classes"])
    rows: dict[str, dict[str, Any]] = {}
    for pred_path in sorted((e4t_run / "predictions").glob("seed_*_probs.npz")):
        seed = pred_path.stem.replace("seed_", "").replace("_probs", "")
        data = np.load(pred_path, allow_pickle=False)
        for prefix in ("active", "oov"):
            probs = data[f"{prefix}_probs"].astype(np.float32)
            sample_ids = data[f"{prefix}_sample_ids"].astype(str)
            pred = np.argmax(probs, axis=1)
            conf = probs[np.arange(probs.shape[0]), pred]
            order = np.argsort(probs, axis=1)
            margin = conf - probs[np.arange(probs.shape[0]), order[:, -2]]
            for idx, sample_id in enumerate(sample_ids.tolist()):
                item = rows.setdefault(str(sample_id), {"sample_id": str(sample_id), "seeds": {}})
                item["seeds"][seed] = {
                    "predicted_gloss": classes[int(pred[idx])],
                    "confidence": float(conf[idx]),
                    "margin": float(margin[idx]),
                }
    return rows


def _video_frames(path: Path, size: tuple[int, int], positions: tuple[float, ...]) -> list[Image.Image]:
    import cv2

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise OSError(f"cannot open video: {path}")
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frames: list[Image.Image] = []
    for position in positions:
        frame_index = max(0, min(count - 1, int(round((count - 1) * position)))) if count > 0 else 0
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        if not ok:
            continue
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame).resize(size)
        frames.append(image)
    cap.release()
    return frames


def _panel(row: dict[str, Any], out_path: Path, frame_size: tuple[int, int] = (160, 160)) -> bool:
    video = Path(str(row["video_path"]))
    try:
        frames = _video_frames(video, frame_size, (0.2, 0.5, 0.8))
    except OSError:
        return False
    if not frames:
        return False
    title_h = 58
    width = frame_size[0] * len(frames)
    image = Image.new("RGB", (width, title_h + frame_size[1]), "white")
    draw = ImageDraw.Draw(image)
    text = f"{row['canonical_gloss']} | split={row['split']} | signer={row['signer_id']} | pred={row['prediction_summary']}"
    draw.text((6, 6), text[:95], fill=(0, 0, 0))
    draw.text((6, 28), f"{row['sample_id']} | hand_hit={row.get('hand_hit_rate', '')} | warnings={row.get('warnings', '')}"[:95], fill=(70, 70, 70))
    for idx, frame in enumerate(frames):
        image.paste(frame, (idx * frame_size[0], title_h))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, quality=92)
    return True


def _contact_sheet(image_paths: list[Path], out_path: Path, columns: int = 4, thumb: tuple[int, int] = (480, 218)) -> None:
    if not image_paths:
        return
    images = [Image.open(path).resize(thumb) for path in image_paths]
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb[0], rows * thumb[1]), "white")
    for idx, image in enumerate(images):
        x = (idx % columns) * thumb[0]
        y = (idx // columns) * thumb[1]
        sheet.paste(image, (x, y))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=92)


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("logs", "panels", "contact_sheets", "review"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    e4s_active = _read_csv(args.e4s_run / "pilot_manifest.csv")
    e4s_oov = _read_csv(args.e4s_run / "oov_confusion_holdout_manifest.csv")
    e4j_rows = {row["sample_id"]: row for row in _read_csv(args.e4j_run / "pilot_manifest.csv")}
    predictions = _load_prediction_rows(args.e4t_run, args.e4s_run)

    selected: list[dict[str, Any]] = []
    for kind, rows in (("primary_reference", e4s_active), ("confusion_target", e4s_oov)):
        for row in rows:
            gloss = row["canonical_gloss"].upper()
            if kind == "primary_reference" and gloss != args.false_commit:
                continue
            if kind == "confusion_target" and gloss != args.target:
                continue
            if args.split != "all" and row["split"] != args.split:
                continue
            source = e4j_rows.get(row["sample_id"])
            if not source or not source.get("video_path"):
                continue
            pred = predictions.get(row["sample_id"], {"seeds": {}})
            seed_summary = ";".join(
                f"{seed}:{item['predicted_gloss']}@{item['confidence']:.4f}"
                for seed, item in sorted(pred.get("seeds", {}).items())
            )
            selected.append({
                "sample_id": row["sample_id"],
                "kind": kind,
                "split": row["split"],
                "canonical_gloss": gloss,
                "false_commit_gloss": args.false_commit if kind == "confusion_target" else "",
                "signer_id": source.get("signer_id", row.get("participant_id", "")),
                "video_path": source["video_path"],
                "frame_count": source.get("frame_count", ""),
                "fps": source.get("fps", ""),
                "hand_hit_rate": source.get("hand_hit_rate", ""),
                "warnings": source.get("warnings", ""),
                "prediction_summary": seed_summary,
            })

    panel_paths: list[Path] = []
    failures = []
    if not args.no_panels:
        for row in selected:
            panel_path = output / "panels" / row["kind"] / row["split"] / f"{row['sample_id']}.jpg"
            if _panel(row, panel_path):
                row["panel_path"] = str(panel_path.resolve())
                panel_paths.append(panel_path)
            else:
                row["panel_path"] = ""
                failures.append(row["sample_id"])
        for kind in ("primary_reference", "confusion_target"):
            kind_paths = [path for path in panel_paths if f"\\{kind}\\" in str(path)]
            _contact_sheet(kind_paths, output / "contact_sheets" / f"{kind}_{args.split}.jpg")

    fields = [
        "sample_id", "kind", "split", "canonical_gloss", "false_commit_gloss", "signer_id",
        "video_path", "frame_count", "fps", "hand_hit_rate", "warnings", "prediction_summary", "panel_path",
    ]
    _write_csv(output / "review" / "confusion_evidence_manifest.csv", selected, fields)
    by_kind = Counter(row["kind"] for row in selected)
    by_split = Counter(f"{row['kind']}:{row['split']}" for row in selected)
    config = {
        "experiment": "e4_u_confusion_evidence_package_v1",
        "purpose": "prepare reusable evidence for a confusion-group specialist/data-repair decision",
        "run_dir": str(output.resolve()),
        "e4s_run": str(args.e4s_run.resolve()),
        "e4t_run": str(args.e4t_run.resolve()),
        "e4j_run": str(args.e4j_run.resolve()),
        "target_gloss": args.target,
        "false_commit_gloss": args.false_commit,
        "split": args.split,
        "rows": len(selected),
        "row_counts_by_kind": dict(sorted(by_kind.items())),
        "row_counts_by_kind_split": dict(sorted(by_split.items())),
        "panel_failures": failures,
        "generated_panels": len(panel_paths),
        "warnings": [
            "This is an evidence package, not a training result.",
            "It focuses on the representative SORRY -> GOOD confusion to define a reusable specialist pattern.",
            "Do not infer production readiness from this package.",
        ],
        "next_action": "Use this evidence to choose the next specialist/data-repair experiment; do not inspect every sign one by one.",
    }
    _write_json(output / "pilot_config.json", config)
    _write_json(output / "logs" / "prepare_summary.json", {**config, "passed": True})
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["pilot_config.json", "logs/prepare_summary.json", "review/confusion_evidence_manifest.csv", "README_RUN.md"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    config = {}
    if (run_dir / "pilot_config.json").exists():
        config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
        if config.get("experiment") != "e4_u_confusion_evidence_package_v1":
            errors.append("unexpected experiment id")
        if args.require_panels and int(config.get("generated_panels", 0)) <= 0:
            errors.append("no panels were generated")
        if args.require_panels and config.get("panel_failures"):
            errors.append(f"panel generation failures: {config['panel_failures']}")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def _runbook(config: dict[str, Any]) -> str:
    return "\n".join([
        "# E4-U Confusion Evidence Package",
        "",
        "This package prepares evidence for a reusable confusion-group resolver strategy.",
        "",
        f"- Target confusion: `{config['target_gloss']} -> {config['false_commit_gloss']}`",
        f"- Rows: `{config['rows']}`",
        f"- Counts: `{config['row_counts_by_kind']}`",
        "",
        "Review the CSV and contact sheets before deciding whether the next step is RGB specialist training, targeted relabel/variant repair, or recollection.",
        "",
        "Main files:",
        "",
        "- `review/confusion_evidence_manifest.csv`",
        "- `contact_sheets/primary_reference_test.jpg`",
        "- `contact_sheets/confusion_target_test.jpg`",
        "",
    ]) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-U confusion evidence package")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--e4s-run", type=Path, default=DEFAULT_E4S_RUN)
    prepare_parser.add_argument("--e4t-run", type=Path, default=DEFAULT_E4T_RUN)
    prepare_parser.add_argument("--e4j-run", type=Path, default=DEFAULT_E4J_RUN)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--target", default=DEFAULT_TARGET)
    prepare_parser.add_argument("--false-commit", default=DEFAULT_FALSE_COMMIT)
    prepare_parser.add_argument("--split", choices=["train", "val", "test", "all"], default="test")
    prepare_parser.add_argument("--no-panels", action="store_true")
    prepare_parser.add_argument("--overwrite", action="store_true")

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--require-panels", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileExistsError, FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-u] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
