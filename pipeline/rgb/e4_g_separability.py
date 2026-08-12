"""E4-G focused BYE/NO/YES separability diagnostic.

Experiment-only. Uses the cleaned E4-F tensor and best E4-F checkpoint to diagnose whether the
BYE/NO/YES failures look like feature separability, source/signer shift, or model decision issues.
No Android assets, production recognizer files, or datasets are modified.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.rgb.e3_b4_landmark_temporal import _build_model, _inputs_for
from pipeline.rgb.e4_e_error_review import _make_panel

DEFAULT_SOURCE_RUN = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_f_cleaned_diagnostic_pilot_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e4_generalization/e4_g_bye_yes_no_separability_01"
)
DEFAULT_BRANCH = "tcn_masked_pool"
DEFAULT_SEED = 303
DEFAULT_TARGETS = ["BYE", "NO", "YES"]
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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_config(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "pilot_config.json"
    if not path.exists():
        raise FileNotFoundError(f"missing source config: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_dataset(run_dir: Path) -> dict[str, np.ndarray]:
    path = run_dir / "dataset" / "landmark_features.npz"
    if not path.exists():
        raise FileNotFoundError(f"missing source tensor: {path}")
    data = np.load(path, allow_pickle=False)
    required = {"landmarks", "frame_mask", "y", "split_index", "lengths", "sample_ids"}
    missing = required.difference(data.files)
    if missing:
        raise ValueError(f"source tensor missing keys: {sorted(missing)}")
    landmarks = data["landmarks"].astype(np.float32)
    if landmarks.ndim != 3 or tuple(landmarks.shape[1:]) != (96, 258):
        raise ValueError(f"expected [N,96,258], got {list(landmarks.shape)}")
    return {
        "landmarks": landmarks,
        "frame_mask": data["frame_mask"].astype(bool),
        "y": data["y"].astype(np.int64),
        "split_index": data["split_index"].astype(np.int64),
        "lengths": data["lengths"].astype(np.int32),
        "sample_ids": np.asarray(data["sample_ids"]).astype(str),
    }


def _compact_embeddings(landmarks: np.ndarray, frame_mask: np.ndarray) -> np.ndarray:
    rows = []
    for x, mask in zip(landmarks, frame_mask, strict=False):
        valid = x[mask.astype(bool)]
        if len(valid) == 0:
            valid = np.zeros((1, x.shape[1]), dtype=np.float32)
        mean = np.mean(valid, axis=0)
        std = np.std(valid, axis=0)
        delta = valid[-1] - valid[0]
        if len(valid) > 1:
            velocity = np.mean(np.abs(np.diff(valid, axis=0)), axis=0)
        else:
            velocity = np.zeros_like(mean)
        rows.append(np.concatenate([mean, std, delta, velocity]).astype(np.float32))
    return np.stack(rows).astype(np.float32)


def _standardize(train_x: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = np.mean(train_x, axis=0, keepdims=True)
    std = np.std(train_x, axis=0, keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    return (x - mean) / std, mean, std


def _nearest_centroid(
    embeddings: np.ndarray,
    labels: np.ndarray,
    split_index: np.ndarray,
    target_ids: list[int],
) -> dict[str, Any]:
    train_mask = (split_index == 0) & np.isin(labels, target_ids)
    train_z, mean, std = _standardize(embeddings[train_mask], embeddings)
    centroids = {}
    for class_id in target_ids:
        centroids[class_id] = np.mean(train_z[train_mask & (labels == class_id)], axis=0)
    centroid_matrix = np.stack([centroids[class_id] for class_id in target_ids])
    centroid_norm = np.linalg.norm(centroid_matrix, axis=1, keepdims=True) + 1e-8
    z_norm = np.linalg.norm(train_z, axis=1, keepdims=True) + 1e-8
    cosine = (train_z / z_norm) @ (centroid_matrix / centroid_norm).T
    pred_pos = np.argmax(cosine, axis=1)
    pred_ids = np.asarray([target_ids[int(pos)] for pos in pred_pos], dtype=np.int64)
    result = _evaluate_target_classifier(labels, split_index, pred_ids, target_ids)
    result["centroid_cosine"] = _pairwise_centroid_cosine(centroid_matrix, target_ids)
    result["standardization_mean_shape"] = list(mean.shape)
    result["standardization_std_shape"] = list(std.shape)
    return result


def _ridge_probe(
    embeddings: np.ndarray,
    labels: np.ndarray,
    split_index: np.ndarray,
    target_ids: list[int],
    ridge: float,
) -> dict[str, Any]:
    train_mask = (split_index == 0) & np.isin(labels, target_ids)
    x_all, _mean, _std = _standardize(embeddings[train_mask], embeddings)
    x_train = x_all[train_mask]
    y_train = labels[train_mask]
    y_onehot = np.zeros((len(y_train), len(target_ids)), dtype=np.float32)
    id_to_pos = {class_id: pos for pos, class_id in enumerate(target_ids)}
    for row, class_id in enumerate(y_train.tolist()):
        y_onehot[row, id_to_pos[int(class_id)]] = 1.0
    xtx = x_train.T @ x_train
    reg = np.eye(xtx.shape[0], dtype=np.float32) * float(ridge)
    weights = np.linalg.solve(xtx + reg, x_train.T @ y_onehot)
    scores = x_all @ weights
    pred_pos = np.argmax(scores, axis=1)
    pred_ids = np.asarray([target_ids[int(pos)] for pos in pred_pos], dtype=np.int64)
    result = _evaluate_target_classifier(labels, split_index, pred_ids, target_ids)
    result["ridge"] = float(ridge)
    return result


def _pairwise_centroid_cosine(centroids: np.ndarray, target_ids: list[int]) -> list[dict[str, Any]]:
    normalized = centroids / (np.linalg.norm(centroids, axis=1, keepdims=True) + 1e-8)
    sim = normalized @ normalized.T
    rows = []
    for i, left in enumerate(target_ids):
        for j, right in enumerate(target_ids):
            if i < j:
                rows.append({"left_class_id": int(left), "right_class_id": int(right), "cosine_similarity": float(sim[i, j])})
    return rows


def _evaluate_target_classifier(
    labels: np.ndarray,
    split_index: np.ndarray,
    pred_ids: np.ndarray,
    target_ids: list[int],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for split_id, split_name in SPLIT_NAMES.items():
        mask = (split_index == split_id) & np.isin(labels, target_ids)
        truth = labels[mask]
        pred = pred_ids[mask]
        confusion = np.zeros((len(target_ids), len(target_ids)), dtype=np.int64)
        id_to_pos = {class_id: pos for pos, class_id in enumerate(target_ids)}
        for t, p in zip(truth.tolist(), pred.tolist(), strict=False):
            confusion[id_to_pos[int(t)], id_to_pos[int(p)]] += 1
        per_class = []
        for class_id in target_ids:
            class_mask = truth == class_id
            total = int(np.sum(class_mask))
            correct = int(np.sum(pred[class_mask] == class_id))
            per_class.append({"class_id": int(class_id), "count": total, "correct": correct, "accuracy": float(correct / total) if total else None})
        out[split_name] = {
            "count": int(len(truth)),
            "accuracy": float(np.mean(pred == truth)) if len(truth) else None,
            "per_class": per_class,
            "predicted_class_counts": {str(class_id): int(np.sum(pred == class_id)) for class_id in target_ids},
            "confusion_matrix": confusion.tolist(),
        }
    return out


def _load_model_predictions(source_run: Path, config: dict[str, Any], dataset: dict[str, np.ndarray], branch: str, seed: int, batch_size: int) -> np.ndarray:
    weights = source_run / "models" / branch / f"seed_{seed}" / "best.weights.h5"
    if not weights.exists():
        raise FileNotFoundError(f"missing selected checkpoint: {weights}")
    model = _build_model(branch, (96, 258), int(config["class_count"]), float(config["learning_rate"]))
    model.load_weights(weights)
    return model.predict(_inputs_for(branch, dataset["landmarks"], dataset["frame_mask"]), batch_size=batch_size, verbose=0)


def _prediction_rows(
    source_run: Path,
    config: dict[str, Any],
    dataset: dict[str, np.ndarray],
    probs: np.ndarray,
    target_names: list[str],
) -> list[dict[str, Any]]:
    manifest = {row["sample_id"]: row for row in _read_csv(source_run / "pilot_manifest.csv")}
    classes = list(config["classes"])
    target_ids = [classes.index(name) for name in target_names]
    rows = []
    for index, sample_id in enumerate(dataset["sample_ids"]):
        true_id = int(dataset["y"][index])
        if true_id not in target_ids:
            continue
        target_probs = probs[index, target_ids]
        target_pred_id = target_ids[int(np.argmax(target_probs))]
        pred_id = int(np.argmax(probs[index]))
        base = manifest.get(sample_id, {})
        rows.append(
            {
                "sample_index": index,
                "sample_id": sample_id,
                "split": SPLIT_NAMES[int(dataset["split_index"][index])],
                "true_gloss": classes[true_id],
                "model_pred_gloss": classes[pred_id],
                "model_correct": str(pred_id == true_id),
                "model_confidence": f"{float(np.max(probs[index])):.6f}",
                "target_restricted_pred_gloss": classes[target_pred_id],
                "target_restricted_correct": str(target_pred_id == true_id),
                "prob_BYE": f"{float(probs[index, classes.index('BYE')]):.6f}" if "BYE" in classes else "",
                "prob_NO": f"{float(probs[index, classes.index('NO')]):.6f}" if "NO" in classes else "",
                "prob_YES": f"{float(probs[index, classes.index('YES')]):.6f}" if "YES" in classes else "",
                "length": int(dataset["lengths"][index]),
                "video_path": base.get("video_path", ""),
                "signer_id": base.get("signer_id", ""),
                "source_folder": base.get("source_folder", ""),
                "folder_word": base.get("folder_word", ""),
                "hand_hit_rate": base.get("hand_hit_rate", ""),
                "warnings": base.get("warnings", ""),
            }
        )
    return rows


def _model_target_summary(rows: list[dict[str, Any]], target_names: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for split in ("train", "val", "test"):
        split_rows = [row for row in rows if row["split"] == split]
        out[split] = {
            "rows": len(split_rows),
            "model_accuracy": float(np.mean([row["model_correct"] == "True" for row in split_rows])) if split_rows else None,
            "target_restricted_accuracy": float(np.mean([row["target_restricted_correct"] == "True" for row in split_rows])) if split_rows else None,
            "model_confusions": dict(Counter(f"{row['true_gloss']}->{row['model_pred_gloss']}" for row in split_rows)),
            "target_restricted_confusions": dict(Counter(f"{row['true_gloss']}->{row['target_restricted_pred_gloss']}" for row in split_rows)),
        }
    out["targets"] = target_names
    return out


def _hand_hit_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        try:
            value = float(row.get("hand_hit_rate", ""))
        except ValueError:
            continue
        groups[f"{row['split']}:{row['true_gloss']}"].append(value)
    return {
        key: {"count": len(values), "mean": float(np.mean(values)), "min": float(np.min(values)), "max": float(np.max(values))}
        for key, values in sorted(groups.items())
        if values
    }


def _make_review_panels(output: Path, rows: list[dict[str, Any]], max_per_split_class: int, frames_per_panel: int) -> list[dict[str, Any]]:
    panel_rows = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["split"], row["true_gloss"])].append(row)
    for key in sorted(grouped):
        for row in grouped[key][:max_per_split_class]:
            panel_index = len(panel_rows) + 1
            filename = f"{panel_index:04d}_{row['split']}_{row['true_gloss']}_pred-{row['model_pred_gloss']}_{row['sample_id']}.jpg"
            panel_path = output / "review_panels" / filename
            title = (
                f"{panel_index:04d} {row['split']} true={row['true_gloss']} "
                f"pred={row['model_pred_gloss']} target_pred={row['target_restricted_pred_gloss']}"
            )
            panel_info = _make_panel(Path(str(row["video_path"])), panel_path, title, frames_per_panel)
            panel_rows.append({"panel_id": f"{panel_index:04d}", **panel_info, **row})
    return panel_rows


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    source_run = args.source_run
    output = args.output
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("diagnostics", "predictions", "review_panels"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    config = _load_config(source_run)
    dataset = _load_dataset(source_run)
    classes = list(config["classes"])
    for target in args.targets:
        if target not in classes:
            raise ValueError(f"target not in source classes: {target}")
    target_ids = [classes.index(name) for name in args.targets]

    probs = _load_model_predictions(source_run, config, dataset, args.branch, int(args.seed), int(args.batch_size))
    pred_rows = _prediction_rows(source_run, config, dataset, probs, list(args.targets))
    _write_csv(output / "predictions" / "bye_no_yes_predictions.csv", pred_rows, list(pred_rows[0].keys()))

    embeddings = _compact_embeddings(dataset["landmarks"], dataset["frame_mask"])
    centroid = _nearest_centroid(embeddings, dataset["y"], dataset["split_index"], target_ids)
    ridge = _ridge_probe(embeddings, dataset["y"], dataset["split_index"], target_ids, float(args.ridge))
    panels = _make_review_panels(output, pred_rows, int(args.max_panels_per_split_class), int(args.frames_per_panel))
    _write_csv(output / "review_panel_index.csv", panels, list(panels[0].keys()) if panels else [])

    target_counts = {
        split: dict(Counter(row["true_gloss"] for row in pred_rows if row["split"] == split))
        for split in ("train", "val", "test")
    }
    summary = {
        "experiment": "e4_g_bye_yes_no_separability_v1",
        "purpose": "focused diagnostic for BYE/NO/YES separability after E4-F cleaned diagnostic",
        "source_run": str(source_run.resolve()),
        "run_dir": str(output.resolve()),
        "targets": list(args.targets),
        "target_ids": [int(v) for v in target_ids],
        "model_branch": args.branch,
        "model_seed": int(args.seed),
        "target_counts": target_counts,
        "model_target_summary": _model_target_summary(pred_rows, list(args.targets)),
        "nearest_centroid": centroid,
        "ridge_probe": ridge,
        "hand_hit_summary": _hand_hit_summary(pred_rows),
        "review_panel_count": len(panels),
        "outputs": {
            "summary": str((output / "diagnostics" / "separability_summary.json").resolve()),
            "predictions": str((output / "predictions" / "bye_no_yes_predictions.csv").resolve()),
            "panels": str((output / "review_panels").resolve()),
            "panel_index": str((output / "review_panel_index.csv").resolve()),
        },
        "passed": True,
    }
    _write_json(output / "diagnostics" / "separability_summary.json", summary)
    (output / "README_RUN.md").write_text(_runbook(summary), encoding="utf-8")
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = [
        "README_RUN.md",
        "diagnostics/separability_summary.json",
        "predictions/bye_no_yes_predictions.csv",
        "review_panel_index.csv",
    ]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    panel_count = 0
    if (run_dir / "review_panel_index.csv").exists():
        panel_rows = _read_csv(run_dir / "review_panel_index.csv")
        panel_count = len(panel_rows)
        missing = [row.get("panel_path", "") for row in panel_rows if not Path(row.get("panel_path", "")).exists()]
        if missing:
            errors.append(f"missing panels: {len(missing)}")
    result = {"run_dir": str(run_dir.resolve()), "panel_count": panel_count, "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def _runbook(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# E4-G BYE/NO/YES Separability Diagnostic",
            "",
            "Experiment-only diagnostic. No Android or production recognizer changes.",
            "",
            f"- Source run: `{summary['source_run']}`",
            f"- Targets: {', '.join(summary['targets'])}",
            f"- Model checkpoint: {summary['model_branch']} seed {summary['model_seed']}",
            f"- Review panels: {summary['review_panel_count']}",
            "",
            "## Outputs",
            "",
            f"- Summary: `{summary['outputs']['summary']}`",
            f"- Predictions: `{summary['outputs']['predictions']}`",
            f"- Panels: `{summary['outputs']['panels']}`",
            "",
            "## Check",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_g_separability check --run-dir "{summary["run_dir"]}"',
            "```",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-G BYE/NO/YES separability diagnostic")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze_parser = sub.add_parser("analyze")
    analyze_parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    analyze_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    analyze_parser.add_argument("--targets", nargs="+", default=DEFAULT_TARGETS)
    analyze_parser.add_argument("--branch", default=DEFAULT_BRANCH)
    analyze_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    analyze_parser.add_argument("--batch-size", type=int, default=8)
    analyze_parser.add_argument("--ridge", type=float, default=10.0)
    analyze_parser.add_argument("--max-panels-per-split-class", type=int, default=12)
    analyze_parser.add_argument("--frames-per-panel", type=int, default=5)
    analyze_parser.add_argument("--overwrite", action="store_true")

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "analyze":
            result = analyze(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileExistsError, FileNotFoundError, KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"[rgb/e4-g] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
