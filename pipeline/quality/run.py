"""Stage Q + N4 runner: evaluate the quality gate for each stage-E clip (over its D2 span),
sanity-check N4 resampling, and emit a DATASET-HEALTH REPORT + advisory accept manifest.
Non-destructive: nothing is deleted; F/training consults the manifest.

  python -m pipeline.quality.run --split val
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

from ..detect.schema import SpanSidecar
from ..extract.schema import ClipLandmarks
from ..normalize.resample import resample_clip
from .config import QualityConfig, load_config
from .gate import evaluate_quality

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "quality.yaml"

MANIFEST_FIELDS = (
    "clip_id",
    "split",
    "participant_id",
    "gloss",
    "accept",
    "reasons",
    "coverage",
    "confidence",
    "n_span",
    "native_fps",
    "params_hash",
)


def run(split: str, limit: int | None, config_path: Path) -> int:
    cfg = load_config(config_path)
    in_dir = cfg.input_root / split
    npz_files = sorted(in_dir.glob("*.npz"))
    if not npz_files:
        print(f"[quality] no clips in {in_dir} — run stages E and D first", file=sys.stderr)
        return 2
    if limit is not None:
        npz_files = npz_files[:limit]

    manifest_path = cfg.output_root / f"manifest_quality_{split}.csv"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    n_failed = 0
    for npz_path in npz_files:
        cid = npz_path.stem
        span_path = cfg.spans_root / split / f"{cid}.span.json"
        if not span_path.exists():
            continue
        try:
            clip = ClipLandmarks.load(npz_path)
            span = SpanSidecar.load(span_path)
            res = evaluate_quality(
                clip.hand_score,
                clip.pose_score,
                span.onset,
                span.release,
                span.valid,
                span.native_fps,
                cfg,
            )
            if cfg.n4_resample and res.accept:  # N4 shape sanity on accepted clips
                h, p = resample_clip(
                    clip.hands_image,
                    clip.pose_image,
                    span.onset,
                    span.release,
                    cfg.resample_T,
                    cfg.resample_method,
                )
                assert h.shape == (cfg.resample_T, 2, 21, 3) and p.shape == (cfg.resample_T, 33, 4)
            rows.append(
                {
                    "clip_id": cid,
                    "split": split,
                    "participant_id": span.participant_id,
                    "gloss": span.gloss,
                    "accept": res.accept,
                    "reasons": ";".join(res.reasons),
                    "coverage": round(res.coverage, 4),
                    "confidence": round(res.confidence, 4),
                    "n_span": res.n_span,
                    "native_fps": round(span.native_fps, 3),
                    "params_hash": cfg.params_hash,
                }
            )
        except Exception as err:  # noqa: BLE001
            print(f"[quality] FAILED {cid}: {err}", file=sys.stderr)
            n_failed += 1

    with manifest_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    _report(split, rows, cfg, n_failed, manifest_path)
    return 0


def _report(
    split: str,
    rows: list[dict[str, object]],
    cfg: QualityConfig,
    n_failed: int,
    manifest_path: Path,
) -> None:
    print(f"\n[quality] done {split}: clips={len(rows)} failed={n_failed} -> {manifest_path}")
    if not rows:
        return
    n = len(rows)
    accepted = [r for r in rows if r["accept"]]
    print(f"\n=== Q dataset-health report ({split}, params={cfg.params_hash}) ===")
    print(f"accepted: {len(accepted)}/{n} = {len(accepted) / n:.1%}")

    reason_counts: Counter[str] = Counter()
    for r in rows:
        for reason in str(r["reasons"]).split(";"):
            if reason:
                reason_counts[reason.split("(")[0]] += 1
    if reason_counts:
        print("reject reasons:", dict(reason_counts.most_common()))

    by_signer: dict[str, list[bool]] = defaultdict(list)
    by_gloss: dict[str, list[bool]] = defaultdict(list)
    for r in rows:
        by_signer[str(r["participant_id"])].append(bool(r["accept"]))
        by_gloss[str(r["gloss"])].append(bool(r["accept"]))

    print(
        f"per-signer reject rate ({len(by_signer)} signers): "
        + ", ".join(f"{s}={1 - sum(a) / len(a):.0%}" for s, a in sorted(by_signer.items()))
    )
    worst = sorted(by_gloss.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))[:5]
    if worst and any(1 - sum(a) / len(a) > 0 for _, a in worst):
        print(
            "most-rejected glosses: "
            + ", ".join(
                f"{g}={1 - sum(a) / len(a):.0%}" for g, a in worst if 1 - sum(a) / len(a) > 0
            )
        )


def main() -> int:
    p = argparse.ArgumentParser(description="AppHear 3 stage Q quality gate + N4 sanity")
    p.add_argument("--split", default="val", choices=["train", "val", "test"])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = p.parse_args()
    return run(args.split, args.limit, args.config)


if __name__ == "__main__":
    raise SystemExit(main())
