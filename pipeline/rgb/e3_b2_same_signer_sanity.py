"""E3-B2 same-signer visual sanity package builder.

This creates an intentionally signer-leaky source split for debugging the RGB visual branch. The
result is not a production accuracy claim. It answers only whether the improved RGB branch can
classify easier same-signer held-out clips before we spend time on fusion or larger training.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from pipeline.rgb import e3_b1_pretrained_rgb

DEFAULT_PREFLIGHT_RUN = Path("artifacts/recognition_upgrade/e3_rgb_b0/preflight_02")
DEFAULT_OUTPUT_ROOT = Path("artifacts/recognition_upgrade/e3_rgb_b2")
DEFAULT_SEED = 280729
DEFAULT_CLASSES = ["DOG1", "BITE1", "DEMAND1", "WHATFOR1", "DEAF1", "PARTY1", "ROCKINGCHAIR1"]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _build_same_signer_rows(
    manifest_rows: list[dict[str, str]],
    classes: list[str],
    train_per_class: int,
    val_per_class: int,
    test_per_class: int,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    class_to_index = {gloss: index for index, gloss in enumerate(classes)}
    selected: list[dict[str, Any]] = []
    for gloss in classes:
        class_rows = [row for row in manifest_rows if row["gloss"] == gloss]
        by_signer: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in class_rows:
            by_signer[row["signer_id"]].append(row)
        repeated = [(signer, rows[:]) for signer, rows in by_signer.items() if len(rows) >= 2]
        rng.shuffle(repeated)
        needed_heldout = val_per_class + test_per_class
        if len(repeated) < needed_heldout:
            raise ValueError(f"{gloss}: need {needed_heldout} repeated signers, found {len(repeated)}")

        used_video_paths: set[str] = set()
        heldout_plan = ["val"] * val_per_class + ["test"] * test_per_class
        for split, (signer, rows) in zip(heldout_plan, repeated[:needed_heldout], strict=True):
            rng.shuffle(rows)
            train_row, heldout_row = rows[0], rows[1]
            for out_split, source_row in (("train", train_row), (split, heldout_row)):
                used_video_paths.add(source_row["video_path"])
                selected.append(
                    {
                        "source": source_row.get("source", "asl_citizen"),
                        "split": out_split,
                        "signer_id": signer,
                        "gloss": gloss,
                        "label_index": class_to_index[gloss],
                        "video_path": source_row["video_path"],
                        "same_signer_pair": "true",
                    }
                )

        current_train = sum(1 for row in selected if row["gloss"] == gloss and row["split"] == "train")
        extra_needed = train_per_class - current_train
        if extra_needed < 0:
            raise ValueError(f"{gloss}: train_per_class smaller than required repeated signer pairs")
        extra_pool = [row for row in class_rows if row["video_path"] not in used_video_paths]
        rng.shuffle(extra_pool)
        if len(extra_pool) < extra_needed:
            raise ValueError(f"{gloss}: need {extra_needed} extra train clips, found {len(extra_pool)}")
        for row in extra_pool[:extra_needed]:
            selected.append(
                {
                    "source": row.get("source", "asl_citizen"),
                    "split": "train",
                    "signer_id": row["signer_id"],
                    "gloss": gloss,
                    "label_index": class_to_index[gloss],
                    "video_path": row["video_path"],
                    "same_signer_pair": "false",
                }
            )

    selected.sort(key=lambda row: (row["split"], row["gloss"], row["signer_id"], row["video_path"]))
    return selected


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output_root / args.run_id
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True, exist_ok=True)

    source_dir = output / "same_signer_source"
    classes = DEFAULT_CLASSES[: args.class_count]
    rows = _build_same_signer_rows(
        _read_csv(args.preflight_run / "pilot_manifest.csv"),
        classes,
        args.train_per_class,
        args.val_per_class,
        args.test_per_class,
        args.seed,
    )
    _write_csv(
        source_dir / "pilot_manifest.csv",
        rows,
        ["source", "split", "signer_id", "gloss", "label_index", "video_path", "same_signer_pair"],
    )
    source_config = {
        "experiment": "e3_b2_same_signer_source_v1",
        "purpose": "intentionally signer-leaky RGB sanity source; not a production split",
        "classes": classes,
        "class_count": len(classes),
        "train_per_class": args.train_per_class,
        "val_per_class": args.val_per_class,
        "test_per_class": args.test_per_class,
        "seed": args.seed,
        "preflight_run": str(args.preflight_run.resolve()),
        "warning": "Signer leakage is intentional for visual sanity only.",
    }
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "pilot_config.json").write_text(json.dumps(source_config, indent=2), encoding="utf-8")

    b1_args = argparse.Namespace(
        output_root=args.output_root,
        run_id=args.run_id,
        overwrite=True,
        source_run=source_dir,
        frames=args.frames,
        image_size=args.image_size,
        crop_mode=args.crop_mode,
        encoder=args.encoder,
        weights=args.weights,
        embedding_batch_size=args.embedding_batch_size,
        train_batch_size=args.train_batch_size,
        epochs=args.epochs,
    )
    config = e3_b1_pretrained_rgb.prepare(b1_args)
    config["experiment"] = "e3_b2_same_signer_rgb_sanity_v1"
    config["purpose"] = "same-signer improved RGB sanity; signer leakage intentional for debugging"
    config["same_signer_source"] = str(source_dir.resolve())
    config["warnings"].insert(0, "Signer leakage is intentional. Do not use as production evidence.")
    (output / "pilot_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    summary = _summarize(rows, classes)
    (output / "same_signer_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return {**config, "same_signer_summary": summary}


def _summarize(rows: list[dict[str, Any]], classes: list[str]) -> dict[str, Any]:
    summary: dict[str, Any] = {"split_counts": {}, "class_counts": {}, "heldout_signer_overlap": {}}
    for split in ("train", "val", "test"):
        summary["split_counts"][split] = sum(1 for row in rows if row["split"] == split)
    for gloss in classes:
        summary["class_counts"][gloss] = {
            split: sum(1 for row in rows if row["gloss"] == gloss and row["split"] == split)
            for split in ("train", "val", "test")
        }
        train_signers = {row["signer_id"] for row in rows if row["gloss"] == gloss and row["split"] == "train"}
        summary["heldout_signer_overlap"][gloss] = {
            split: sorted(
                {
                    row["signer_id"]
                    for row in rows
                    if row["gloss"] == gloss and row["split"] == split and row["signer_id"] in train_signers
                }
            )
            for split in ("val", "test")
        }
    return summary


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join(
        [
            "# E3-B2 Same-Signer RGB Sanity",
            "",
            "This is an intentionally signer-leaky debugging sanity check, not production training.",
            "",
            "## Settings",
            "",
            f"- Classes: {config['class_count']}",
            f"- Clips: {config['estimated_size']['rows']}",
            f"- Frames per clip: {config['frames']}",
            f"- Crop mode: {config['crop_mode']}",
            f"- Image size: {config['image_size']}x{config['image_size']}",
            f"- Encoder: {config['encoder']}",
            f"- Weights: {config['weights']}",
            f"- Epochs per command: {config['epochs']}",
            "",
            "## Run",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b1_pretrained_rgb run --run-dir "{run_dir}"',
            "```",
            "",
            "## Resume",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b1_pretrained_rgb run --run-dir "{run_dir}" --resume',
            "```",
            "",
            "## Check",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_b1_pretrained_rgb check --run-dir "{run_dir}"',
            "```",
            "",
            "Stop after check. Do not compare this as cross-signer accuracy.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="E3-B2 same-signer RGB sanity package builder")
    parser.add_argument("--run-id", default="pilot_01_same_signer_mobilenetv3")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--preflight-run", type=Path, default=DEFAULT_PREFLIGHT_RUN)
    parser.add_argument("--class-count", type=int, default=7)
    parser.add_argument("--train-per-class", type=int, default=8)
    parser.add_argument("--val-per-class", type=int, default=2)
    parser.add_argument("--test-per-class", type=int, default=2)
    parser.add_argument("--frames", type=int, default=16)
    parser.add_argument("--image-size", type=int, default=160)
    parser.add_argument("--crop-mode", choices=["upper_body_center", "full_frame"], default="upper_body_center")
    parser.add_argument("--encoder", choices=["mobilenetv3small"], default="mobilenetv3small")
    parser.add_argument("--weights", choices=["imagenet", "none"], default="imagenet")
    parser.add_argument("--embedding-batch-size", type=int, default=32)
    parser.add_argument("--train-batch-size", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        result = prepare(args)
    except (FileNotFoundError, KeyError, ValueError, OSError) as error:
        print(f"[rgb/e3-b2] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
