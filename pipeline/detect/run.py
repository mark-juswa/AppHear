"""Stages D1+D2 runner: detect the signing span for each stage-E clip in a split.

Non-destructive: writes a per-clip *.span.json + manifest_spans_<split>.csv, leaving the raw
.npz untouched. Resumable. Prints label-free validation stats (span coverage, in/out hand-rate
ratio, span-duration + motion distributions) so thresholds in detect.yaml can be tuned.

  python -m pipeline.detect.run --split val
  python -m pipeline.detect.run --split val --limit 50
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

from ..extract.schema import ClipLandmarks, ClipSidecar
from .config import DetectConfig, load_config
from .schema import SpanSidecar
from .signals import compute_signals
from .span import Span, detect_span

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "detect.yaml"

MANIFEST_FIELDS = (
    "clip_id",
    "split",
    "participant_id",
    "gloss",
    "status",
    "reason",
    "valid",
    "onset",
    "release",
    "n_frames",
    "span_duration_s",
    "in_span_hand_rate",
    "out_span_hand_rate",
    "params_hash",
)


def _hand_rates(hand_score: np.ndarray, span: Span) -> tuple[float, float]:
    """(in-span, out-span) fraction of frames with >=1 hand detected."""
    t = hand_score.shape[0]
    present = np.any(hand_score > 0.0, axis=1)  # (T,)
    in_mask = np.zeros(t, dtype=bool)
    if span.onset >= 0:
        in_mask[span.onset : span.release + 1] = True
    in_rate = float(present[in_mask].mean()) if in_mask.any() else float("nan")
    out_rate = float(present[~in_mask].mean()) if (~in_mask).any() else float("nan")
    return in_rate, out_rate


def _load_done(manifest_path: Path) -> set[str]:
    if not manifest_path.exists():
        return set()
    with manifest_path.open("r", encoding="utf-8", newline="") as fh:
        return {r["clip_id"] for r in csv.DictReader(fh) if r.get("status") == "ok"}


def _whole_clip_span(n: int) -> Span:
    return Span(0, n - 1, True, "detect_disabled", n) if n > 0 else Span(-1, -1, False, "empty", 0)


def run(split: str, limit: int | None, config_path: Path) -> int:
    cfg = load_config(config_path)
    in_dir = cfg.input_root / split
    npz_files = sorted(in_dir.glob("*.npz"))
    if not npz_files:
        print(f"[detect] no extracted clips in {in_dir} — run stage E first", file=sys.stderr)
        return 2
    if limit is not None:
        npz_files = npz_files[:limit]

    out_dir = cfg.output_root / split
    manifest_path = cfg.output_root / f"manifest_spans_{split}.csv"
    done = _load_done(manifest_path)
    write_header = not manifest_path.exists()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    n_ok = n_failed = n_skipped = 0
    stats: list[SpanSidecar] = []
    with manifest_path.open("a", encoding="utf-8", newline="") as mf:
        writer = csv.DictWriter(mf, fieldnames=MANIFEST_FIELDS)
        if write_header:
            writer.writeheader()

        for i, npz_path in enumerate(npz_files, start=1):
            cid = npz_path.stem
            if cid in done:
                n_skipped += 1
                continue
            side_path = npz_path.with_suffix(".json")
            try:
                clip = ClipLandmarks.load(npz_path)
                meta = ClipSidecar.load(side_path)
                n = clip.timestamps_ms.shape[0]

                if cfg.enabled:
                    signals = compute_signals(
                        clip,
                        cfg.pose_landmarks,
                        cfg.hand_aux_weight,
                        cfg.raise_margin,
                        cfg.smoothing_window,
                    )
                    span = detect_span(signals, cfg)
                    scale = signals.scale
                    m = signals.motion
                    mp50, mp90 = (
                        (float(np.percentile(m, 50)), float(np.percentile(m, 90)))
                        if m.size
                        else (float("nan"), float("nan"))
                    )
                else:
                    span = _whole_clip_span(n)
                    scale = float("nan")
                    mp50 = mp90 = float("nan")

                in_rate, out_rate = _hand_rates(clip.hand_score, span)
                dur = (span.release - span.onset + 1) / meta.native_fps if span.onset >= 0 else 0.0
                sidecar = SpanSidecar(
                    detect_version=cfg.detect_version,
                    params_hash=cfg.params_hash,
                    clip_id=cid,
                    split=split,
                    participant_id=meta.participant_id,
                    gloss=meta.gloss,
                    asl_lex_code=meta.asl_lex_code,
                    n_frames=n,
                    native_fps=meta.native_fps,
                    onset=span.onset,
                    release=span.release,
                    valid=span.valid,
                    reason=span.reason,
                    n_signing_frames=span.n_signing_frames,
                    span_duration_s=round(dur, 4),
                    shoulder_scale=round(scale, 6),
                    in_span_hand_rate=round(in_rate, 4),
                    out_span_hand_rate=round(out_rate, 4),
                    motion_p50=round(mp50, 5),
                    motion_p90=round(mp90, 5),
                )
                sidecar.save(out_dir / f"{cid}.span.json")
                writer.writerow(
                    {
                        "clip_id": cid,
                        "split": split,
                        "participant_id": meta.participant_id,
                        "gloss": meta.gloss,
                        "status": "ok",
                        "reason": span.reason,
                        "valid": span.valid,
                        "onset": span.onset,
                        "release": span.release,
                        "n_frames": n,
                        "span_duration_s": round(dur, 4),
                        "in_span_hand_rate": round(in_rate, 4),
                        "out_span_hand_rate": round(out_rate, 4),
                        "params_hash": cfg.params_hash,
                    }
                )
                mf.flush()
                stats.append(sidecar)
                n_ok += 1
            except Exception as err:  # noqa: BLE001 — one bad clip must not kill the run
                print(f"[detect] FAILED {cid}: {err}", file=sys.stderr)
                writer.writerow(
                    {"clip_id": cid, "split": split, "status": "failed", "reason": str(err)[:200]}
                )
                mf.flush()
                n_failed += 1

            if i % 250 == 0:
                print(
                    f"[detect] {split}: {i}/{len(npz_files)} "
                    f"(ok={n_ok} failed={n_failed} skipped={n_skipped})"
                )

    _report(split, stats, cfg, n_ok, n_failed, n_skipped, manifest_path)
    return 0


def _report(
    split: str,
    stats: list[SpanSidecar],
    cfg: DetectConfig,
    n_ok: int,
    n_failed: int,
    n_skipped: int,
    manifest_path: Path,
) -> None:
    print(
        f"\n[detect] done {split}: ok={n_ok} failed={n_failed} skipped={n_skipped} "
        f"-> {manifest_path}"
    )
    if not stats:
        return
    valid = [s for s in stats if s.valid]
    durations = np.array([s.span_duration_s for s in valid]) if valid else np.array([])
    in_rates = np.array([s.in_span_hand_rate for s in valid if not np.isnan(s.in_span_hand_rate)])
    out_rates = np.array(
        [s.out_span_hand_rate for s in valid if not np.isnan(s.out_span_hand_rate)]
    )
    m50 = np.array([s.motion_p50 for s in stats if not np.isnan(s.motion_p50)])
    m90 = np.array([s.motion_p90 for s in stats if not np.isnan(s.motion_p90)])

    print(f"\n=== D1/D2 label-free validation ({split}, params={cfg.params_hash}) ===")
    print(f"coverage (valid spans): {len(valid)}/{len(stats)} = {len(valid)/len(stats):.2%}")
    if durations.size:
        print(
            f"span duration s: mean={durations.mean():.2f} "
            f"p10={np.percentile(durations,10):.2f} p50={np.percentile(durations,50):.2f} "
            f"p90={np.percentile(durations,90):.2f}   (ASL-LEX mean ~0.85s)"
        )
    if in_rates.size and out_rates.size:
        ratio = in_rates.mean() / out_rates.mean() if out_rates.mean() > 0 else float("inf")
        print(
            f"hand-rate in-span={in_rates.mean():.2f} out-span={out_rates.mean():.2f} "
            f"ratio={ratio:.2f}  (want >> 1: trimming removes dead time)"
        )
    if m50.size:
        print(
            "motion (shoulder-widths/frame): "
            f"median-of-p50={np.median(m50):.4f}  median-of-p90={np.median(m90):.4f}  "
            f"(current theta_on={cfg.theta_on} theta_off={cfg.theta_off}) "
            "-- use these to tune thresholds"
        )


def main() -> int:
    p = argparse.ArgumentParser(description="AppHear 3 stage D1/D2 signing detection + trim")
    p.add_argument("--split", default="val", choices=["train", "val", "test"])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = p.parse_args()
    return run(args.split, args.limit, args.config)


if __name__ == "__main__":
    raise SystemExit(main())
