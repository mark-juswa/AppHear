"""Full 236-class regression audit for AppHear streaming model candidates.

Compares multiple trained streaming models on the same held-out features and reports:
- overall top1/top3/top5 by view
- per-class top1/top3/top5 by view
- worst regressions/improvements versus the first model supplied as baseline

This is report-only. It does not export, copy, or deploy Android assets.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np  # noqa: E402


@dataclass(frozen=True)
class ModelSpec:
    name: str
    path: Path


def _parse_model_spec(raw: str) -> ModelSpec:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("model spec must be NAME=PATH")
    name, path = raw.split("=", 1)
    if not name.strip():
        raise argparse.ArgumentTypeError("model name cannot be empty")
    return ModelSpec(name.strip(), Path(path.strip().strip('"')))


def _load_vocab(path: Path) -> tuple[dict[str, int], dict[int, str]]:
    vocab: dict[str, int] = json.loads(path.read_text(encoding="utf-8"))
    return vocab, {idx: gloss for gloss, idx in vocab.items()}


def _load_split(features_dir: Path, split: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    with np.load(features_dir / f"{split}.npz", allow_pickle=True) as data:
        return (
            data["X"],
            data["y"].astype(np.int32),
            data["frame_mask"].astype(bool),
            data["lengths"].astype(np.int32),
        )


def _topk(probs: np.ndarray, y: np.ndarray, k: int) -> float:
    if len(y) == 0:
        return float("nan")
    top = np.argpartition(-probs, kth=min(k, probs.shape[1]) - 1, axis=1)[:, :k]
    return float((top == y[:, None]).any(axis=1).mean())


def _predict_views(model: Any, x: np.ndarray, frame_mask: np.ndarray, lengths: np.ndarray, batch_size: int) -> dict[str, np.ndarray]:
    n = len(x)
    num_classes = int(model.output_shape[-1])
    views = {
        "mean": np.empty((n, num_classes), np.float32),
        "last": np.empty((n, num_classes), np.float32),
        "early4": np.empty((n, num_classes), np.float32),
        "early6": np.empty((n, num_classes), np.float32),
    }
    for start in range(0, n, batch_size):
        stop = min(start + batch_size, n)
        per_frame = np.asarray(model(x[start:stop], training=False), dtype=np.float32)
        mask = frame_mask[start:stop].astype(np.float32)
        denom = np.clip(mask.sum(axis=1, keepdims=True), 1.0, None)
        views["mean"][start:stop] = (per_frame * mask[..., None]).sum(axis=1) / denom
        last_idx = np.clip(lengths[start:stop] - 1, 0, per_frame.shape[1] - 1)
        views["last"][start:stop] = per_frame[np.arange(stop - start), last_idx]
        for k, name in ((4, "early4"), (6, "early6")):
            early_idx = np.minimum(np.maximum(lengths[start:stop] - 1, 0), k - 1)
            views[name][start:stop] = per_frame[np.arange(stop - start), early_idx]
    return views


def _summarize_views(views: dict[str, np.ndarray], y: np.ndarray, rev: dict[int, str]) -> dict[str, Any]:
    report: dict[str, Any] = {}
    class_ids = sorted(rev)
    for view_name, probs in views.items():
        pred = probs.argmax(axis=1)
        classes: dict[str, Any] = {}
        for class_id in class_ids:
            mask = y == class_id
            if not mask.any():
                continue
            rows = probs[mask]
            yy = y[mask]
            classes[rev[class_id]] = {
                "id": int(class_id),
                "n": int(mask.sum()),
                "top1": float((pred[mask] == yy).mean()),
                "top3": _topk(rows, yy, 3),
                "top5": _topk(rows, yy, 5),
            }
        report[view_name] = {
            "overall": {
                "n": int(len(y)),
                "top1": float((pred == y).mean()),
                "top3": _topk(probs, y, 3),
                "top5": _topk(probs, y, 5),
            },
            "classes": classes,
        }
    return report


def _rank_deltas(report: dict[str, Any], baseline: str, candidate: str, split: str, view: str, metric: str) -> list[dict[str, Any]]:
    base_classes = report["models"][baseline][split][view]["classes"]
    cand_classes = report["models"][candidate][split][view]["classes"]
    out = []
    for gloss, base_item in base_classes.items():
        cand_item = cand_classes.get(gloss)
        if not cand_item:
            continue
        out.append(
            {
                "gloss": gloss,
                "n": int(base_item["n"]),
                "baseline": float(base_item[metric]),
                "candidate": float(cand_item[metric]),
                "delta": float(cand_item[metric] - base_item[metric]),
            }
        )
    return sorted(out, key=lambda item: item["delta"])


def _write_markdown(path: Path, report: dict[str, Any], baseline: str, focus_words: list[str], worst_n: int) -> None:
    lines: list[str] = ["# Full 236-Class Regression Audit", ""]
    lines.append(f"Baseline: `{baseline}`")
    lines.append("")
    lines.append("## Overall")
    for split in report["splits"]:
        lines.append(f"### {split}")
        for view in ("mean", "last", "early4", "early6"):
            lines.append(f"#### {view}")
            lines.append("| model | top1 | top3 | top5 |")
            lines.append("|---|---:|---:|---:|")
            for model_name in report["model_order"]:
                overall = report["models"][model_name][split][view]["overall"]
                lines.append(
                    f"| {model_name} | {overall['top1']:.3f} | {overall['top3']:.3f} | {overall['top5']:.3f} |"
                )
            lines.append("")
    lines.append("## Focus Words - Held-Out Last View")
    lines.append("| gloss | " + " | ".join(report["model_order"]) + " |")
    lines.append("|---|" + "|".join(["---:"] * len(report["model_order"])) + "|")
    for gloss in focus_words:
        row = [gloss]
        for model_name in report["model_order"]:
            item = report["models"][model_name]["test"]["last"]["classes"].get(gloss)
            row.append(f"{item['top1']:.2f}" if item else "")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    for candidate in report["model_order"][1:]:
        lines.append(f"## {candidate} vs {baseline} - Held-Out Last Top1")
        deltas = _rank_deltas(report, baseline, candidate, "test", "last", "top1")
        lines.append("### Worst Regressions")
        lines.append("| gloss | n | baseline | candidate | delta |")
        lines.append("|---|---:|---:|---:|---:|")
        for item in deltas[:worst_n]:
            lines.append(
                f"| {item['gloss']} | {item['n']} | {item['baseline']:.2f} | {item['candidate']:.2f} | {item['delta']:.2f} |"
            )
        lines.append("")
        lines.append("### Best Improvements")
        lines.append("| gloss | n | baseline | candidate | delta |")
        lines.append("|---|---:|---:|---:|---:|")
        for item in reversed(deltas[-worst_n:]):
            lines.append(
                f"| {item['gloss']} | {item['n']} | {item['baseline']:.2f} | {item['candidate']:.2f} | {item['delta']:.2f} |"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run(
    models: list[ModelSpec],
    features_dir: Path,
    fps_features_dir: Path | None,
    vocab_path: Path,
    out_dir: Path,
    batch_size: int,
    worst_n: int,
) -> int:
    import tensorflow as tf

    if len(models) < 2:
        raise ValueError("provide at least baseline and one candidate model")
    _, rev = _load_vocab(vocab_path)
    splits = {"test": features_dir}
    if fps_features_dir and (fps_features_dir / "val.npz").exists():
        splits["fps_val"] = fps_features_dir
    loaded = {split: _load_split(directory, "test" if split == "test" else "val") for split, directory in splits.items()}
    report: dict[str, Any] = {
        "model_order": [spec.name for spec in models],
        "baseline": models[0].name,
        "splits": list(splits),
        "features_dir": str(features_dir),
        "fps_features_dir": str(fps_features_dir) if fps_features_dir else None,
        "vocab": str(vocab_path),
        "models": {},
    }
    for spec in models:
        if not spec.path.exists():
            raise FileNotFoundError(f"missing model {spec.name}: {spec.path}")
        print(f"[full-regression] loading {spec.name}: {spec.path}")
        model = tf.keras.models.load_model(spec.path, compile=False, safe_mode=False)
        report["models"][spec.name] = {}
        for split, (x, y, frame_mask, lengths) in loaded.items():
            views = _predict_views(model, x, frame_mask, lengths, batch_size)
            report["models"][spec.name][split] = _summarize_views(views, y, rev)
        del model
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "full_regression_audit.json"
    md_path = out_dir / "full_regression_audit.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    focus_words = [
        "CUT", "IMPORTANT", "FAMILY", "MORE", "INTRODUCE", "SELL", "PUT", "DECIDE1", "SHOP1", "TEACH2",
        "WANT2", "MANY", "WAIT", "MEET", "KNOW", "HELLO", "DONTKNOW", "WE", "LIVE2", "STRONG",
    ]
    _write_markdown(md_path, report, models[0].name, focus_words, worst_n)
    print(f"[full-regression] wrote {json_path}")
    print(f"[full-regression] wrote {md_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare full per-class regressions across 236-class streaming models")
    parser.add_argument("--model", action="append", type=_parse_model_spec, required=True, help="NAME=PATH. First model is the baseline.")
    parser.add_argument("--features-dir", type=Path, required=True)
    parser.add_argument("--fps-features-dir", type=Path, default=None)
    parser.add_argument("--vocab", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--worst-n", type=int, default=20)
    args = parser.parse_args()
    return run(args.model, args.features_dir, args.fps_features_dir, args.vocab, args.out_dir, args.batch_size, args.worst_n)


if __name__ == "__main__":
    raise SystemExit(main())
