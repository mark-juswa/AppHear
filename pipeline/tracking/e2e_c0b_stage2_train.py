"""Prepare and run the bounded research-only C0-B0 detector learning curve."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from collections import Counter, defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import cv2

from pipeline.tracking.e2e_c0b import _read_csv, _write_json

EXPERIMENT = "c0b_stage2_detector_learning_curve_v1"
DEFAULT_MANIFEST_RUN = Path(
    "artifacts/recognition_upgrade/e2e_c0/c0b_stage2_research_manifest_01"
)
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e2e_c0/c0b_stage2_detector_01")
FRACTIONS = (25, 50, 100)
CONDITIONS = (
    "motion_blur",
    "occlusion",
    "near_face",
    "edge_clipped",
    "partial_visibility",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _asset(row: dict[str, str], manifest_run: Path) -> Path:
    value = Path(row["center_image_path"])
    candidates = (value, manifest_run.parent / row["source_run"] / "center_images" / value.name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"{row['sample_id']}: center image not found: {value}")


def _bucket(row: dict[str, str]) -> tuple[str, str, str]:
    hands = int(row["hand_count"])
    return row["source_dataset"], row["participant_id"], f"hands_{hands}"


def _nested_order(rows: list[dict[str, str]], seed: int) -> list[dict[str, str]]:
    """Return deterministic source/signer/hand-count round-robin order."""

    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[_bucket(row)].append(row)
    queues: dict[tuple[str, str, str], deque[dict[str, str]]] = {}
    for key, values in groups.items():
        queues[key] = deque(
            sorted(
                values,
                key=lambda row: hashlib.sha256(
                    f"{seed}:{row['sample_id']}".encode()
                ).hexdigest(),
            )
        )
    keys = sorted(queues)
    ordered: list[dict[str, str]] = []
    while queues:
        for key in list(keys):
            queue = queues.get(key)
            if queue:
                ordered.append(queue.popleft())
            if queue is not None and not queue:
                del queues[key]
        keys = [key for key in keys if key in queues]
    return ordered


def _link_or_copy(source: Path, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return "existing"
    try:
        os.link(source, target)
        return "hardlink"
    except OSError:
        shutil.copy2(source, target)
        return "copy"


def _coco_payload(
    rows: list[dict[str, str]], images_dir: Path, manifest_run: Path
) -> tuple[dict[str, Any], Counter[str]]:
    images: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    methods: Counter[str] = Counter()
    annotation_id = 1
    for image_id, row in enumerate(rows, start=1):
        source = _asset(row, manifest_run)
        suffix = source.suffix.lower() or ".jpg"
        filename = f"{row['sample_id']}{suffix}".replace(":", "_")
        target = images_dir / filename
        methods[_link_or_copy(source, target)] += 1
        image = cv2.imread(str(source))
        if image is None:
            raise OSError(f"cannot read image: {source}")
        height, width = image.shape[:2]
        images.append(
            {
                "id": image_id,
                "file_name": filename,
                "width": width,
                "height": height,
                "sample_id": row["sample_id"],
            }
        )
        boxes = json.loads(row["gold_hands_json"])
        for box in boxes:
            x = float(box["x_min"]) * width
            y = float(box["y_min"]) * height
            box_width = (float(box["x_max"]) - float(box["x_min"])) * width
            box_height = (float(box["y_max"]) - float(box["y_min"])) * height
            if box_width <= 0 or box_height <= 0:
                raise ValueError(f"{row['sample_id']}: non-positive gold box")
            annotations.append(
                {
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": 1,
                    "bbox": [x, y, box_width, box_height],
                    "area": box_width * box_height,
                    "iscrowd": 0,
                }
            )
            annotation_id += 1
    return {
        "categories": [{"id": 1, "name": "hand"}],
        "images": images,
        "annotations": annotations,
    }, methods


def _condition_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    return {
        "rows": len(rows),
        "hand_instances": sum(int(row["hand_count"]) for row in rows),
        "no_hand": sum(int(row["hand_count"]) == 0 for row in rows),
        "one_hand": sum(int(row["hand_count"]) == 1 for row in rows),
        "two_hand": sum(int(row["hand_count"]) == 2 for row in rows),
        **{field: sum(row[field] == "yes" for row in rows) for field in CONDITIONS},
    }


def _write_coco(
    root: Path, rows: list[dict[str, str]], manifest_run: Path
) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=False)
    payload, methods = _coco_payload(rows, root / "images", manifest_run)
    _write_json(root / "labels.json", payload)
    return {
        "root": str(root.resolve()),
        "rows": len(rows),
        "annotations": len(payload["annotations"]),
        "asset_methods": dict(methods),
        "conditions": _condition_counts(rows),
    }


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = args.manifest_run / "stage2_manifest.csv"
    rows = _read_csv(manifest_path)
    train = [row for row in rows if row["dataset_split"] == "train"]
    development = [row for row in rows if row["dataset_split"] == "development"]
    if not train or not development:
        raise ValueError("manifest must contain train and development rows")
    args.output.mkdir(parents=True, exist_ok=False)
    coco_root = args.output / "coco"
    coco_root.mkdir()
    ordered = _nested_order(train, args.seed)
    packages: dict[str, Any] = {
        "development": _write_coco(coco_root / "development", development, args.manifest_run)
    }
    previous_ids: set[str] = set()
    for fraction in FRACTIONS:
        count = len(train) if fraction == 100 else round(len(train) * fraction / 100)
        subset = ordered[:count]
        current_ids = {row["sample_id"] for row in subset}
        if not previous_ids.issubset(current_ids):
            raise ValueError(f"train_{fraction}: subsets are not nested")
        previous_ids = current_ids
        stats = _condition_counts(subset)
        if stats["no_hand"] == 0 or stats["hand_instances"] == 0:
            raise ValueError(f"train_{fraction}: missing positive or negative frames")
        packages[f"train_{fraction}"] = _write_coco(
            coco_root / f"train_{fraction}", subset, args.manifest_run
        )
    authorization = {
        "scope": "internal non-commercial research and development only",
        "research_training_authorized": True,
        "production_training_authorized": False,
        "android_integration_authorized": False,
        "restricted_data_redistribution_authorized": False,
        "user_authorized_on": "2026-08-10",
    }
    summary = {
        "experiment": EXPERIMENT,
        "stage": "coco_learning_curve_package",
        "manifest": str(manifest_path.resolve()),
        "manifest_sha256": _sha256(manifest_path),
        "seed": args.seed,
        "fractions": list(FRACTIONS),
        "packages": packages,
        "authorization": authorization,
        "passed": True,
        "next": "run MobileNetV2 256 at 25/50/100%; review before authorizing I320",
    }
    _write_json(args.output / "package_summary.json", summary)
    _write_json(args.output / "research_authorization.json", authorization)
    print(json.dumps(summary, indent=2))
    return summary


def _jsonable(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def train_one(args: argparse.Namespace) -> dict[str, Any]:
    from mediapipe_model_maker import object_detector

    branch = f"{args.model.lower()}_{args.fraction}"
    branch_dir = args.run_dir / "models" / branch
    summary_path = branch_dir / "training_summary.json"
    if summary_path.is_file():
        summary = cast(dict[str, Any], json.loads(summary_path.read_text(encoding="utf-8")))
        print(json.dumps({**summary, "resumed": True}, indent=2))
        return summary
    if branch_dir.exists():
        if not args.retry_incomplete:
            raise FileExistsError(
                f"incomplete branch exists: {branch_dir}; inspect it, then rerun with "
                "--retry-incomplete"
            )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        preserved = branch_dir.with_name(f"{branch_dir.name}.incomplete.{timestamp}")
        branch_dir.rename(preserved)
    branch_dir.mkdir(parents=True)
    train_root = args.run_dir / "coco" / f"train_{args.fraction}"
    development_root = args.run_dir / "coco" / "development"
    train_data = object_detector.Dataset.from_coco_folder(
        str(train_root), cache_dir=str(branch_dir / "cache" / "train")
    )
    development_data = object_detector.Dataset.from_coco_folder(
        str(development_root), cache_dir=str(branch_dir / "cache" / "development")
    )
    supported_model = getattr(object_detector.SupportedModels, args.model)
    options = object_detector.ObjectDetectorOptions(
        supported_model=supported_model,
        hparams=object_detector.HParams(
            export_dir=str(branch_dir / "export"),
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            shuffle=True,
            num_gpus=0,
        ),
    )
    started = time.perf_counter()
    model = object_detector.ObjectDetector.create(
        train_data=train_data,
        validation_data=development_data,
        options=options,
    )
    loss, coco_metrics = model.evaluate(development_data, batch_size=args.batch_size)
    model.export_model("model_float.tflite")
    model_path = branch_dir / "export" / "model_float.tflite"
    if not model_path.is_file():
        raise FileNotFoundError(model_path)
    summary = {
        "experiment": EXPERIMENT,
        "stage": "float_learning_curve_branch",
        "branch": branch,
        "model": args.model,
        "fraction": args.fraction,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "development_loss": _jsonable(loss),
        "development_coco_metrics": _jsonable(coco_metrics),
        "model_path": str(model_path.resolve()),
        "model_sha256": _sha256(model_path),
        "model_bytes": model_path.stat().st_size,
        "elapsed_seconds": time.perf_counter() - started,
        "research_only": True,
        "production_authorized": False,
        "passed": True,
    }
    _write_json(summary_path, summary)
    print(json.dumps(summary, indent=2))
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    package_path = args.run_dir / "package_summary.json"
    if not package_path.is_file():
        errors.append("missing package_summary.json")
    for split in ("development", *(f"train_{fraction}" for fraction in FRACTIONS)):
        root = args.run_dir / "coco" / split
        labels = root / "labels.json"
        if not labels.is_file():
            errors.append(f"{split}: missing labels.json")
            continue
        payload = json.loads(labels.read_text(encoding="utf-8"))
        for image in payload.get("images", []):
            if not (root / "images" / image["file_name"]).is_file():
                errors.append(f"{split}: missing image {image['file_name']}")
    if args.require_models:
        for fraction in FRACTIONS:
            branch = args.run_dir / "models" / f"mobilenet_v2_{fraction}"
            if not (branch / "training_summary.json").is_file():
                errors.append(f"missing completed MobileNetV2 branch: {fraction}%")
            if not (branch / "export" / "model_float.tflite").is_file():
                errors.append(f"missing MobileNetV2 float model: {fraction}%")
    if args.require_i320:
        for fraction in FRACTIONS:
            branch = args.run_dir / "models" / f"mobilenet_v2_i320_{fraction}"
            if not (branch / "training_summary.json").is_file():
                errors.append(f"missing completed MobileNetV2-I320 branch: {fraction}%")
            if not (branch / "export" / "model_float.tflite").is_file():
                errors.append(f"missing MobileNetV2-I320 float model: {fraction}%")
    summary = {
        "run_dir": str(args.run_dir.resolve()),
        "require_models": args.require_models,
        "require_i320": args.require_i320,
        "errors": errors,
        "passed": not errors,
        "production_authorized": False,
    }
    _write_json(args.run_dir / "check_report.json", summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="C0-B0 Stage 2 research learning curve")
    commands = parser.add_subparsers(dest="command", required=True)

    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--manifest-run", type=Path, default=DEFAULT_MANIFEST_RUN)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--seed", type=int, default=100826)
    prepare_parser.set_defaults(func=prepare)

    train_parser = commands.add_parser("train-one")
    train_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    train_parser.add_argument(
        "--model", choices=("MOBILENET_V2", "MOBILENET_V2_I320"), default="MOBILENET_V2"
    )
    train_parser.add_argument("--fraction", type=int, choices=FRACTIONS, required=True)
    train_parser.add_argument("--epochs", type=int, default=30)
    train_parser.add_argument("--batch-size", type=int, default=4)
    train_parser.add_argument("--learning-rate", type=float, default=0.3)
    train_parser.add_argument("--retry-incomplete", action="store_true")
    train_parser.set_defaults(func=train_one)

    check_parser = commands.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    check_parser.add_argument("--require-models", action="store_true")
    check_parser.add_argument("--require-i320", action="store_true")
    check_parser.set_defaults(func=check)

    args = parser.parse_args()
    try:
        result = args.func(args)
        return 0 if result.get("passed", True) else 2
    except (FileExistsError, FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as error:
        print(f"[tracking/c0-b0-stage2-train] ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
