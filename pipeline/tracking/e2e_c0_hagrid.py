"""C0-A HaGRID transfer preflight and bounded smoke runner."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

DEFAULT_P0_RUN = Path(
    "F:/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/"
    "e2e_all_hand_gold_v1/engineering_01"
)
DEFAULT_N0_RUN = Path("artifacts/recognition_upgrade/e2e_c0/n0_capture_06")
DEFAULT_P1_RUN = Path("artifacts/recognition_upgrade/e2e_c0/p1_capture_03")
DEFAULT_OUTPUT_ROOT = Path("artifacts/recognition_upgrade/e2e_c0")
DEFAULT_SEED = 280728

SMOKE_FIELDS = (
    "sample_id",
    "source_set",
    "image_path",
    "gold_hands_json",
    "visible_hand_count",
    "motion_blur",
    "occlusion",
    "near_face",
    "edge_clipped",
    "partial_visibility",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _json_list(raw: str, sample_id: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError as error:
        raise ValueError(f"{sample_id}: invalid gold_hands_json") from error
    if not isinstance(value, list):
        raise ValueError(f"{sample_id}: gold_hands_json must be a list")
    return value


def _normalize_image_path(path_text: str) -> str:
    path = Path(path_text)
    if not path.exists():
        raise FileNotFoundError(f"image path does not exist: {path}")
    return str(path.resolve())


def _positive_rows(p0_run: Path) -> list[dict[str, str]]:
    reviews = {row["sample_id"]: row for row in _read_csv(p0_run / "gold_review.csv")}
    index = {row["sample_id"]: row for row in _read_csv(p0_run / "internal_index.csv")}
    rows = []
    for sample_id, review in reviews.items():
        if review["review_status"] != "accepted":
            continue
        boxes = _json_list(review["gold_hands_json"], sample_id)
        if not boxes:
            continue
        metadata = index[sample_id]
        rows.append(
            {
                "sample_id": sample_id,
                "source_set": "p0_positive_gold",
                "image_path": _normalize_image_path(metadata["center_image_path"]),
                "gold_hands_json": review["gold_hands_json"],
                "visible_hand_count": str(len(boxes)),
                "motion_blur": review["motion_blur"],
                "occlusion": review["occlusion"],
                "near_face": review["near_face"],
                "edge_clipped": review["edge_clipped"],
                "partial_visibility": review["partial_visibility"],
            }
        )
    return rows


def _capture_rows(run_dir: Path, source_set: str, require_hands: bool) -> list[dict[str, str]]:
    rows = []
    for row in _read_csv(run_dir / "reviewed_manifest.csv"):
        if row["eligible"].lower() != "true":
            continue
        boxes = _json_list(row["gold_hands_json"], row["sample_id"])
        if require_hands and not boxes:
            continue
        if not require_hands and boxes:
            continue
        rows.append(
            {
                "sample_id": row["sample_id"],
                "source_set": source_set,
                "image_path": _normalize_image_path(row["center_image_path"]),
                "gold_hands_json": row["gold_hands_json"],
                "visible_hand_count": str(len(boxes)),
                "motion_blur": "",
                "occlusion": "",
                "near_face": "",
                "edge_clipped": "",
                "partial_visibility": "",
            }
        )
    return rows


def _pick_positive(rows: list[dict[str, str]], count: int, seed: int) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    used: set[str] = set()
    priority_rules = [
        lambda row: row["edge_clipped"] == "yes",
        lambda row: row["motion_blur"] == "yes",
        lambda row: row["occlusion"] == "yes",
        lambda row: int(row["visible_hand_count"]) >= 2,
        lambda row: row["near_face"] == "yes",
        lambda row: row["partial_visibility"] == "yes",
    ]
    for rule in priority_rules:
        for row in rows:
            if row["sample_id"] not in used and rule(row):
                selected.append(row)
                used.add(row["sample_id"])
                break
        if len(selected) >= count:
            return selected[:count]

    remaining = [row for row in rows if row["sample_id"] not in used]
    random.Random(seed).shuffle(remaining)
    selected.extend(remaining[: max(0, count - len(selected))])
    return selected[:count]


def _pick_random(rows: list[dict[str, str]], count: int, seed: int) -> list[dict[str, str]]:
    pool = rows[:]
    random.Random(seed).shuffle(pool)
    return pool[:count]


def prepare(
    output: Path,
    p0_run: Path,
    n0_run: Path,
    p1_run: Path,
    seed: int,
    positive_count: int,
    negative_count: int,
    p1_count: int,
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")

    positives = _positive_rows(p0_run)
    negatives = _capture_rows(n0_run, "n0_no_visible_hands", require_hands=False)
    p1 = _capture_rows(p1_run, "p1_visible_non_sign_hands", require_hands=True)

    if len(positives) < positive_count:
        raise ValueError(f"only {len(positives)} P0 positive rows available")
    if len(negatives) < negative_count:
        raise ValueError(f"only {len(negatives)} N0 negative rows available")
    if len(p1) < p1_count:
        raise ValueError(f"only {len(p1)} P1 diagnostic rows available")

    smoke_rows = _pick_positive(positives, positive_count, seed) + _pick_random(
        negatives, negative_count, seed + 1
    )
    p1_rows = _pick_random(p1, p1_count, seed + 2)

    _write_csv(output / "smoke_manifest.csv", SMOKE_FIELDS, smoke_rows)
    _write_csv(output / "p1_diagnostic_manifest.csv", SMOKE_FIELDS, p1_rows)

    provenance = {
        "experiment": "e2e_c0_a_hagrid_preflight_v1",
        "purpose": "six-positive/twenty-negative HaGRID transfer smoke; no full C0-A inference",
        "seed": seed,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "p1_diagnostic_count": p1_count,
        "sources": {
            "p0_run": str(p0_run.resolve()),
            "n0_run": str(n0_run.resolve()),
            "p1_run": str(p1_run.resolve()),
            "p0_gold_review_sha256": _sha256(p0_run / "gold_review.csv"),
            "n0_reviewed_manifest_sha256": _sha256(n0_run / "reviewed_manifest.csv"),
            "p1_reviewed_manifest_sha256": _sha256(p1_run / "reviewed_manifest.csv"),
        },
        "checkpoint_contract": {
            "candidate_id": "hagridv2_yolov10n_hands_reference",
            "weights_filename": "YOLOv10n_hands.pt",
            "weights_source": "https://github.com/hukenovs/hagrid README hand detector link",
            "research_only_reason": "HaGRID/YOLO reference; production licensing and mobile export not approved",
            "expected_runtime": "ultralytics/torch on desktop for C0-A transfer screen only",
        },
    }
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return provenance


def check(run_dir: Path, weights: Path | None = None) -> dict[str, Any]:
    smoke = _read_csv(run_dir / "smoke_manifest.csv")
    p1 = _read_csv(run_dir / "p1_diagnostic_manifest.csv")
    errors = []
    positives = [row for row in smoke if row["source_set"] == "p0_positive_gold"]
    negatives = [row for row in smoke if row["source_set"] == "n0_no_visible_hands"]
    if len(positives) != 6:
        errors.append(f"expected 6 P0 positives, found {len(positives)}")
    if len(negatives) != 20:
        errors.append(f"expected 20 N0 negatives, found {len(negatives)}")
    for row in smoke + p1:
        if not Path(row["image_path"]).exists():
            errors.append(f"missing image: {row['image_path']}")
        boxes = _json_list(row["gold_hands_json"], row["sample_id"])
        if row["source_set"] == "p0_positive_gold" and not boxes:
            errors.append(f"{row['sample_id']}: P0 positive has no hand boxes")
        if row["source_set"] == "n0_no_visible_hands" and boxes:
            errors.append(f"{row['sample_id']}: N0 negative has hand boxes")
    dependency_state: dict[str, Any] = {}
    try:
        import ultralytics  # type: ignore

        dependency_state["ultralytics_available"] = True
        dependency_state["ultralytics_version"] = getattr(ultralytics, "__version__", "unknown")
    except ImportError:
        dependency_state["ultralytics_available"] = False
    if weights is not None:
        dependency_state["weights_path"] = str(weights.resolve())
        dependency_state["weights_exists"] = weights.exists()
        if weights.exists():
            dependency_state["weights_sha256"] = _sha256(weights)
        else:
            errors.append(f"weights file does not exist: {weights}")

    result = {
        "run_dir": str(run_dir.resolve()),
        "smoke_rows": len(smoke),
        "p1_diagnostic_rows": len(p1),
        "errors": errors,
        "passed": not errors,
        "dependency_state": dependency_state,
    }
    (run_dir / "preflight_check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def run_smoke(run_dir: Path, weights: Path, confidence: float) -> dict[str, Any]:
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError as error:
        raise RuntimeError(
            "ultralytics is not installed. Install the isolated C0-A requirements first."
        ) from error
    if not weights.exists():
        raise FileNotFoundError(f"weights file does not exist: {weights}")

    model = YOLO(str(weights))
    rows = _read_csv(run_dir / "smoke_manifest.csv")
    predictions_dir = run_dir / "predictions"
    predictions_dir.mkdir(parents=True, exist_ok=True)
    output_path = predictions_dir / "hagrid_yolov10n_hands_smoke.jsonl"
    records = []
    start_total = time.perf_counter()
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            start = time.perf_counter()
            result = model.predict(
                source=row["image_path"],
                conf=confidence,
                verbose=False,
            )[0]
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            boxes = []
            for box in result.boxes:
                xyxy = box.xyxyn[0].detach().cpu().tolist()
                conf = float(box.conf[0].detach().cpu().item())
                cls = int(box.cls[0].detach().cpu().item())
                boxes.append(
                    {
                        "x_min": float(xyxy[0]),
                        "y_min": float(xyxy[1]),
                        "x_max": float(xyxy[2]),
                        "y_max": float(xyxy[3]),
                        "confidence": conf,
                        "class_id": cls,
                    }
                )
            record = {
                "sample_id": row["sample_id"],
                "source_set": row["source_set"],
                "image_path": row["image_path"],
                "latency_ms": elapsed_ms,
                "detections": boxes,
            }
            records.append(record)
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")

    positives = [record for record in records if record["source_set"] == "p0_positive_gold"]
    negatives = [record for record in records if record["source_set"] == "n0_no_visible_hands"]
    summary = {
        "weights_path": str(weights.resolve()),
        "weights_sha256": _sha256(weights),
        "confidence": confidence,
        "records": len(records),
        "positive_frames_with_any_detection": sum(bool(r["detections"]) for r in positives),
        "negative_frames_with_any_detection": sum(bool(r["detections"]) for r in negatives),
        "elapsed_total_ms": (time.perf_counter() - start_total) * 1000.0,
        "prediction_jsonl": str(output_path.resolve()),
        "warning": "Smoke only. Do not use as the C0-A gate result.",
    }
    (run_dir / "smoke_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="C0-A HaGRID checkpoint preflight and smoke")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--run-id", default="c0a_hagrid_smoke_01")
    prepare_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    prepare_parser.add_argument("--p0-run", type=Path, default=DEFAULT_P0_RUN)
    prepare_parser.add_argument("--n0-run", type=Path, default=DEFAULT_N0_RUN)
    prepare_parser.add_argument("--p1-run", type=Path, default=DEFAULT_P1_RUN)
    prepare_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    prepare_parser.add_argument("--positive-count", type=int, default=6)
    prepare_parser.add_argument("--negative-count", type=int, default=20)
    prepare_parser.add_argument("--p1-count", type=int, default=4)

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--weights", type=Path, default=None)

    run_parser = sub.add_parser("run-smoke")
    run_parser.add_argument("--run-dir", type=Path, required=True)
    run_parser.add_argument("--weights", type=Path, required=True)
    run_parser.add_argument("--confidence", type=float, default=0.01)

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            output = args.output_root / args.run_id
            result = prepare(
                output=output,
                p0_run=args.p0_run,
                n0_run=args.n0_run,
                p1_run=args.p1_run,
                seed=args.seed,
                positive_count=args.positive_count,
                negative_count=args.negative_count,
                p1_count=args.p1_count,
            )
        elif args.command == "check":
            result = check(args.run_dir, args.weights)
        elif args.command == "run-smoke":
            result = run_smoke(args.run_dir, args.weights, args.confidence)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, KeyError, RuntimeError, ValueError, OSError) as error:
        print(f"[tracking/e2e-c0-hagrid] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
