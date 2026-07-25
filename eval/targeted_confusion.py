"""Targeted confusion audit for known low-FPS Android failure groups.

This is a report-only tool. It does not change model assets or Android runtime files.

Examples:
  python -m eval.targeted_confusion --config model/config/train_streaming_conversational_plus_local_pc_236_targeted.yaml
  python -m eval.targeted_confusion --model path/to/best.keras --features-dir path/to/features --vocab path/to/vocab.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np  # noqa: E402

from model.train_streaming import DEFAULT_CONFIG, load_stream_config  # noqa: E402

DEFAULT_GROUPS: dict[str, list[str]] = {
    "important_family_more_introduce": ["IMPORTANT", "FAMILY", "MORE", "INTRODUCE"],
    "sell_put_decide_shop_teach": ["SELL", "PUT", "DECIDE1", "SHOP1", "TEACH2"],
    "want_many_wait_meet": ["WANT2", "MANY", "WAIT", "MEET"],
    "know_hello_sell_dontknow": ["KNOW", "HELLO", "SELL", "DONTKNOW"],
    "we_live_strong_sell": ["WE", "LIVE2", "STRONG", "SELL"],
}


def _load_split(features_dir: Path, split: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    with np.load(features_dir / f"{split}.npz", allow_pickle=True) as d:
        return (
            d["X"],
            d["y"].astype(np.int32),
            d["frame_mask"].astype(bool),
            d["lengths"].astype(np.int32),
            d["participant_ids"],
        )


def _predict_views(model: Any, features_dir: Path, split: str, batch_size: int) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray, np.ndarray]:
    x, y, frame_mask, lengths, participant_ids = _load_split(features_dir, split)
    n = len(y)
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
    return views, y, lengths, participant_ids


def _topk_contains(probs: np.ndarray, y: np.ndarray, k: int) -> np.ndarray:
    top = np.argpartition(-probs, kth=min(k, probs.shape[1]) - 1, axis=1)[:, :k]
    return (top == y[:, None]).any(axis=1)


def _rank_of_true(row: np.ndarray, true_id: int) -> int:
    return int(np.where(np.argsort(-row) == true_id)[0][0]) + 1


def _summarize_view(
    name: str,
    probs: np.ndarray,
    y: np.ndarray,
    lengths: np.ndarray,
    ids: dict[str, int],
    rev: dict[int, str],
    groups: dict[str, list[str]],
) -> dict[str, Any]:
    pred = probs.argmax(axis=1)
    out: dict[str, Any] = {
        "view": name,
        "overall": {
            "n": int(len(y)),
            "top1": float((pred == y).mean()),
            "top3": float(_topk_contains(probs, y, 3).mean()),
            "top5": float(_topk_contains(probs, y, 5).mean()),
        },
        "classes": {},
        "groups": {},
    }
    for gloss, class_id in ids.items():
        mask = y == class_id
        if not mask.any():
            continue
        rows = probs[mask]
        preds = pred[mask]
        ranks = [_rank_of_true(row, class_id) for row in rows]
        out["classes"][gloss] = {
            "n": int(mask.sum()),
            "top1": float((preds == class_id).mean()),
            "top3": float(_topk_contains(rows, y[mask], 3).mean()),
            "top5": float(_topk_contains(rows, y[mask], 5).mean()),
            "median_len": float(np.median(lengths[mask])),
            "mean_true_rank": float(np.mean(ranks)),
            "pred_counts": dict(Counter(rev[int(p)] for p in preds).most_common(8)),
        }
    for group_name, words in groups.items():
        present = [word for word in words if word in ids]
        group_ids = [ids[word] for word in present]
        group_mask = np.isin(y, group_ids)
        matrix = []
        for true_word in present:
            true_mask = y == ids[true_word]
            matrix.append([int(((pred == ids[pred_word]) & true_mask).sum()) for pred_word in present])
        out["groups"][group_name] = {
            "words": present,
            "n": int(group_mask.sum()),
            "top1": float((pred[group_mask] == y[group_mask]).mean()) if group_mask.any() else math.nan,
            "matrix_rows_true_cols_pred": matrix,
        }
    return out


def _load_vocab(path: Path) -> dict[str, int]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_markdown(path: Path, report: dict[str, Any], all_words: list[str]) -> None:
    lines = ["# Targeted Confusion Audit", ""]
    lines.append(f"Model: `{report['model']}`")
    lines.append(f"Features: `{report['features']}`")
    if report.get("fps_features"):
        lines.append(f"FPS stress features: `{report['fps_features']}`")
    lines.append("")
    lines.append("## Headline")
    for split_name, split_report in report["reports"].items():
        lines.append(f"### {split_name}")
        for view in ("mean", "last", "early4", "early6"):
            overall = split_report[view]["overall"]
            lines.append(
                f"- `{view}`: n={overall['n']} top1={overall['top1']:.3f} "
                f"top3={overall['top3']:.3f} top5={overall['top5']:.3f}"
            )
        lines.append("")
    lines.append("## Per-Class Held-Out Test")
    for view in ("mean", "last", "early4", "early6"):
        classes = report["reports"]["test"][view]["classes"]
        lines.append(f"### View: {view}")
        lines.append("| class | n | top1 | top3 | top5 | mean true rank | top predictions |")
        lines.append("|---|---:|---:|---:|---:|---:|---|")
        for word in all_words:
            item = classes.get(word)
            if not item:
                continue
            preds = ", ".join(f"{k}:{v}" for k, v in item["pred_counts"].items())
            lines.append(
                f"| {word} | {item['n']} | {item['top1']:.2f} | {item['top3']:.2f} | "
                f"{item['top5']:.2f} | {item['mean_true_rank']:.1f} | {preds} |"
            )
        lines.append("")
    lines.append("## Group Matrices - Held-Out Test Last View")
    for group_name, group in report["reports"]["test"]["last"]["groups"].items():
        words = group["words"]
        lines.append(f"### {group_name} (top1={group['top1']:.2f}, n={group['n']})")
        lines.append("| true / pred | " + " | ".join(words) + " |")
        lines.append("|---|" + "|".join(["---:"] * len(words)) + "|")
        for word, row in zip(words, group["matrix_rows_true_cols_pred"], strict=True):
            lines.append("| " + word + " | " + " | ".join(str(v) for v in row) + " |")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run(
    config: Path,
    model_path: Path | None,
    features_dir: Path | None,
    fps_features_dir: Path | None,
    vocab_path: Path | None,
    out_dir: Path,
    batch_size: int | None,
) -> int:
    import tensorflow as tf

    cfg = load_stream_config(config)
    model_path = model_path or (cfg.output_dir / "best.keras")
    features_dir = features_dir or cfg.features_dir
    vocab_path = vocab_path or (cfg.vocab_dir or (cfg.features_dir.parent / "features")) / "vocab.json"
    batch_size = batch_size or cfg.batch_size
    if not model_path.exists():
        raise FileNotFoundError(f"missing model: {model_path}")
    if not (features_dir / "test.npz").exists():
        raise FileNotFoundError(f"missing held-out test split: {features_dir / 'test.npz'}")
    vocab = _load_vocab(vocab_path)
    rev = {i: gloss for gloss, i in vocab.items()}
    groups = DEFAULT_GROUPS
    all_words = []
    for words in groups.values():
        for word in words:
            if word not in all_words:
                all_words.append(word)
    ids = {word: vocab[word] for word in all_words if word in vocab}

    print(f"[targeted] loading model: {model_path}")
    model = tf.keras.models.load_model(model_path, compile=False, safe_mode=False)
    reports = {}
    views, y, lengths, _ = _predict_views(model, features_dir, "test", batch_size)
    reports["test"] = {
        name: _summarize_view(name, probs, y, lengths, ids, rev, groups)
        for name, probs in views.items()
    }
    if fps_features_dir and (fps_features_dir / "val.npz").exists():
        fps_views, fps_y, fps_lengths, _ = _predict_views(model, fps_features_dir, "val", batch_size)
        reports["fps_val"] = {
            name: _summarize_view(name, probs, fps_y, fps_lengths, ids, rev, groups)
            for name, probs in fps_views.items()
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "model": str(model_path),
        "features": str(features_dir),
        "fps_features": str(fps_features_dir) if fps_features_dir else None,
        "vocab": str(vocab_path),
        "groups": groups,
        "reports": reports,
    }
    json_path = out_dir / "targeted_confusion_audit.json"
    md_path = out_dir / "targeted_confusion_audit.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(md_path, report, all_words)
    print(f"[targeted] wrote {json_path}")
    print(f"[targeted] wrote {md_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Targeted confusion audit for AppHear streaming models")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--features-dir", type=Path, default=None)
    parser.add_argument("--fps-features-dir", type=Path, default=None)
    parser.add_argument("--vocab", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/targeted_confusion_audit"))
    parser.add_argument("--batch-size", type=int, default=None)
    args = parser.parse_args()
    return run(args.config, args.model, args.features_dir, args.fps_features_dir, args.vocab, args.out_dir, args.batch_size)


if __name__ == "__main__":
    raise SystemExit(main())
