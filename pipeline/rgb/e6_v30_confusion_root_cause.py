"""Bounded root-cause audit for the E6 five-sign v3.0 baseline.

This module consumes existing features and checkpoints. It does not extract,
train, export, or modify Android assets.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from pipeline.rgb.e6_v30_five_sign_baseline import (
    CLASSES,
    DEFAULT_DEPLOYED_MODEL,
    DEFAULT_DEPLOYED_VOCAB,
    _load_split,
    _tflite_probs,
)


EXPERIMENT = "e6_v30_confusion_root_cause_v1"
TARGET_PAIRS = (("KNOW", "HELLO"), ("HAVE", "GOOD"))
DEFAULT_BASELINE = Path(
    "artifacts/recognition_upgrade/e6_baseline/e6_v30_five_sign_baseline_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e6_baseline/e6_v30_confusion_root_cause_01"
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    records = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in records for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _nan_stats(values: np.ndarray) -> list[float]:
    finite = values[np.isfinite(values)]
    if not len(finite):
        return [0.0, 0.0]
    return [float(np.mean(finite)), float(np.std(finite))]


def clip_descriptor(x: np.ndarray, frame_mask: np.ndarray) -> np.ndarray:
    """Create an interpretable summary without changing the v3.0 contract."""
    valid = x[np.asarray(frame_mask, dtype=bool)]
    if not len(valid):
        return np.zeros(24, dtype=np.float32)
    hands = valid[:, :126].reshape(-1, 2, 21, 3)
    pose = valid[:, 126:].reshape(-1, 33, 4)
    present = np.any(np.abs(hands) > 1e-7, axis=(2, 3))
    centroids = np.full((len(valid), 2, 3), np.nan, dtype=np.float32)
    for side in range(2):
        mask = present[:, side]
        centroids[mask, side] = hands[mask, side].mean(axis=1)
    active_valid = np.any(present, axis=1)
    active = np.zeros((len(valid), 3), dtype=np.float32)
    active[active_valid] = np.nanmean(centroids[active_valid], axis=1)
    nose = pose[:, 0, :3]
    shoulder = (pose[:, 11, :3] + pose[:, 12, :3]) / 2.0
    head_distance = np.full(len(valid), np.nan, dtype=np.float32)
    shoulder_distance = np.full(len(valid), np.nan, dtype=np.float32)
    head_distance[active_valid] = np.linalg.norm(
        active[active_valid, :2] - nose[active_valid, :2], axis=1
    )
    shoulder_distance[active_valid] = np.linalg.norm(
        active[active_valid, :2] - shoulder[active_valid, :2], axis=1
    )
    speed = np.full(max(len(valid) - 1, 0), np.nan, dtype=np.float32)
    if len(valid) > 1:
        pair_valid = active_valid[1:] & active_valid[:-1]
        speed[pair_valid] = np.linalg.norm(
            active[1:][pair_valid] - active[:-1][pair_valid], axis=1
        )
    result: list[float] = [
        float(len(valid) / 96.0),
        float(present[:, 0].mean()),
        float(present[:, 1].mean()),
        float(np.all(present, axis=1).mean()),
    ]
    for side in range(2):
        for axis in range(3):
            result.extend(_nan_stats(centroids[:, side, axis]))
    result.extend(_nan_stats(head_distance))
    result.extend(_nan_stats(shoulder_distance))
    result.extend(_nan_stats(speed))
    result.extend(
        [
            float(np.mean(pose[:, 0, 3])),
            float(np.mean((pose[:, 11, 3] + pose[:, 12, 3]) / 2.0)),
        ]
    )
    return np.asarray(result, dtype=np.float32)


def _nearest_centroid(
    train_desc: np.ndarray, train_y: np.ndarray, query_desc: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    mean = train_desc.mean(axis=0)
    std = train_desc.std(axis=0)
    std[std < 1e-6] = 1.0
    train_z = (train_desc - mean) / std
    query_z = (query_desc - mean) / std
    centers = np.stack([train_z[train_y == i].mean(axis=0) for i in range(len(CLASSES))])
    distances = np.linalg.norm(query_z[:, None, :] - centers[None, :, :], axis=2)
    return distances.argmin(axis=1), distances


def _split_balance(rows: list[dict[str, str]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for split in ("train", "val", "test_fresh", "test_historical"):
        subset = [row for row in rows if row["split"] == split]
        by_class = {}
        for label in CLASSES:
            class_rows = [row for row in subset if row["canonical_label"] == label]
            signer_counts = Counter(row["signer_group_id"] for row in class_rows)
            source_counts = Counter(row["source_dataset"] for row in class_rows)
            by_class[label] = {
                "clips": len(class_rows),
                "signers": len(signer_counts),
                "sources": dict(source_counts),
                "largest_signer_share": (
                    max(signer_counts.values()) / len(class_rows) if class_rows else None
                ),
            }
        result[split] = {
            "clips": len(subset),
            "signers": len({row["signer_group_id"] for row in subset}),
            "sources": dict(Counter(row["source_dataset"] for row in subset)),
            "by_class": by_class,
        }
    return result


def _predict_models(baseline: Path, splits: dict[str, dict[str, np.ndarray]]) -> dict[str, Any]:
    import tensorflow as tf

    from eval.streaming import predict_aggregate

    result: dict[str, Any] = defaultdict(dict)
    for seed in (101, 202, 303):
        model = tf.keras.models.load_model(
            baseline / "models" / f"seed_{seed}" / "latest.keras",
            compile=False,
            safe_mode=False,
        )
        for split, data in splits.items():
            probs, _, _ = predict_aggregate(
                model,
                data["X"].astype(np.float32),
                data["frame_mask"].astype(bool),
                data["y"].astype(np.int32),
                data["lengths"].astype(np.int32),
                32,
            )
            result[str(seed)][split] = probs
    return result


def _predict_deployed(
    model_path: Path, vocab_path: Path, splits: dict[str, dict[str, np.ndarray]]
) -> dict[str, np.ndarray]:
    import tensorflow as tf

    vocab = json.loads(vocab_path.read_text(encoding="utf-8"))
    selected = np.asarray([vocab[label] for label in CLASSES], dtype=np.int32)
    interpreter = tf.lite.Interpreter(model_path=str(model_path))
    interpreter.allocate_tensors()
    return {
        split: _tflite_probs(interpreter, data["X"], data["frame_mask"])[:, selected]
        for split, data in splits.items()
    }


def _render_review_sheets(rows: list[dict[str, Any]], output: Path) -> list[str]:
    import cv2

    rendered = []
    sheet_root = output / "review_sheets"
    sheet_root.mkdir(parents=True, exist_ok=True)
    thumb_w, thumb_h = 240, 160
    for page_start in range(0, len(rows), 8):
        page = rows[page_start : page_start + 8]
        sheet = np.full((len(page) * (thumb_h + 32), thumb_w * 3, 3), 245, dtype=np.uint8)
        for row_index, row in enumerate(page):
            capture = cv2.VideoCapture(row["raw_video_path"])
            frame_count = max(int(capture.get(cv2.CAP_PROP_FRAME_COUNT)), 1)
            for column, fraction in enumerate((0.15, 0.5, 0.85)):
                capture.set(cv2.CAP_PROP_POS_FRAMES, int((frame_count - 1) * fraction))
                ok, frame = capture.read()
                if not ok:
                    frame = np.zeros((thumb_h, thumb_w, 3), dtype=np.uint8)
                frame = cv2.resize(frame, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA)
                y = row_index * (thumb_h + 32)
                x = column * thumb_w
                sheet[y : y + thumb_h, x : x + thumb_w] = frame
            capture.release()
            text = (
                f"{row['split']} | {row['canonical_label']} | "
                f"TCN={row['three_seed_consensus']} | old={row['deployed_restricted_prediction']}"
            )
            cv2.putText(
                sheet,
                text[:105],
                (5, row_index * (thumb_h + 32) + thumb_h + 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.46,
                (15, 15, 15),
                1,
                cv2.LINE_AA,
            )
        path = sheet_root / f"review_{page_start // 8 + 1:02d}.jpg"
        cv2.imwrite(str(path), sheet)
        rendered.append(str(path))
    return rendered


def run(args: argparse.Namespace) -> int:
    baseline = args.baseline.resolve()
    output = args.output.resolve()
    manifest = _read_csv(baseline / "positive_extraction_manifest.csv")
    manifest_by_id = {row["sample_id"]: row for row in manifest}
    split_names = ("train", "val", "test_fresh", "test_historical")
    splits = {
        name: _load_split(baseline / "dataset" / "features", name)
        for name in split_names
    }
    descriptors = {
        split: np.stack(
            [clip_descriptor(x, mask) for x, mask in zip(data["X"], data["frame_mask"])]
        )
        for split, data in splits.items()
    }
    nearest = {}
    distances = {}
    for split in split_names:
        nearest[split], distances[split] = _nearest_centroid(
            descriptors["train"], splits["train"]["y"], descriptors[split]
        )
    model_probs = _predict_models(baseline, splits)
    deployed_probs = _predict_deployed(args.deployed_model, args.deployed_vocab, splits)

    diagnostics = []
    for split, data in splits.items():
        for index, sample_id in enumerate(data["sample_ids"].astype(str)):
            row = manifest_by_id[sample_id]
            record: dict[str, Any] = {
                **row,
                "length": int(data["lengths"][index]),
                "descriptor_nearest": CLASSES[int(nearest[split][index])],
                "descriptor_distance_true": round(float(distances[split][index, int(data['y'][index])]), 6),
                "deployed_restricted_prediction": CLASSES[int(deployed_probs[split][index].argmax())],
                "deployed_restricted_confidence": round(float(deployed_probs[split][index].max()), 6),
            }
            votes = []
            for seed in (101, 202, 303):
                probs = model_probs[str(seed)][split][index]
                prediction = CLASSES[int(probs.argmax())]
                votes.append(prediction)
                record[f"seed_{seed}_prediction"] = prediction
                record[f"seed_{seed}_confidence"] = round(float(probs.max()), 6)
            record["three_seed_consensus"] = votes[0] if len(set(votes)) == 1 else "MIXED"
            diagnostics.append(record)
    _write_csv(output / "sample_diagnostics.csv", diagnostics)

    pair_summary: dict[str, Any] = {}
    for truth, confusion in TARGET_PAIRS:
        key = f"{truth}_vs_{confusion}"
        pair_summary[key] = {}
        for split in split_names:
            rows = [
                row for row in diagnostics
                if row["split"] == split and row["canonical_label"] == truth
            ]
            pair_summary[key][split] = {
                "count": len(rows),
                "descriptor_nearest_confusion_rate": float(np.mean([
                    row["descriptor_nearest"] == confusion for row in rows
                ])) if rows else None,
                "three_seed_consensus_confusion_rate": float(np.mean([
                    row["three_seed_consensus"] == confusion for row in rows
                ])) if rows else None,
                "deployed_restricted_confusion_rate": float(np.mean([
                    row["deployed_restricted_prediction"] == confusion for row in rows
                ])) if rows else None,
            }

    review_candidates = [
        row for row in diagnostics
        if row["canonical_label"] in {item for pair in TARGET_PAIRS for item in pair}
        and row["split"] in {"train", "val", "test_fresh"}
    ]
    review_candidates.sort(
        key=lambda row: (
            0 if row["split"] == "test_fresh" and row["three_seed_consensus"] != row["canonical_label"] else 1,
            row["canonical_label"],
            row["signer_group_id"],
            row["sample_id"],
        )
    )
    selected_review = []
    seen: Counter[tuple[str, str]] = Counter()
    seen_source: Counter[tuple[str, str, str]] = Counter()
    for row in review_candidates:
        key = (row["split"], row["canonical_label"])
        source_key = (*key, row["source_dataset"])
        if seen[key] >= 3 or seen_source[source_key] >= 1:
            continue
        selected_review.append(row)
        seen[key] += 1
        seen_source[source_key] += 1
        if len(selected_review) >= 36:
            break
    _write_csv(output / "visual_review_queue.csv", selected_review)
    review_sheets = _render_review_sheets(selected_review, output)

    balance = _split_balance(manifest)
    risks = []
    if balance["test_fresh"]["signers"] == 1:
        risks.append("Fresh test measures one signer, so it cannot establish population-level signer independence.")
    for label in CLASSES:
        item = balance["val"]["by_class"][label]
        if item["clips"] < 10 or item["signers"] < 2:
            risks.append(f"Validation support for {label} is weak: {item['clips']} clips from {item['signers']} signer(s).")
    summary = {
        "experiment": EXPERIMENT,
        "baseline_run": str(baseline),
        "scope": "read-only audit; no extraction, training, export, or Android modification",
        "target_pairs": [list(pair) for pair in TARGET_PAIRS],
        "split_balance": balance,
        "pair_summary": pair_summary,
        "risks": risks,
        "outputs": {
            "sample_diagnostics": str(output / "sample_diagnostics.csv"),
            "visual_review_queue": str(output / "visual_review_queue.csv"),
            "review_sheets": review_sheets,
        },
        "passed": True,
    }
    _write_json(output / "root_cause_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


def check(args: argparse.Namespace) -> int:
    required = ("root_cause_summary.json", "sample_diagnostics.csv", "visual_review_queue.csv")
    errors = [name for name in required if not (args.run_dir / name).is_file()]
    if not errors:
        payload = json.loads((args.run_dir / "root_cause_summary.json").read_text(encoding="utf-8"))
        if payload.get("experiment") != EXPERIMENT or not payload.get("passed"):
            errors.append("invalid or failed root-cause summary")
    result = {"run_dir": str(args.run_dir.resolve()), "passed": not errors, "errors": errors}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    run_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_parser.add_argument("--deployed-model", type=Path, default=DEFAULT_DEPLOYED_MODEL)
    run_parser.add_argument("--deployed-vocab", type=Path, default=DEFAULT_DEPLOYED_VOCAB)
    run_parser.set_defaults(func=run)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    check_parser.set_defaults(func=check)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
