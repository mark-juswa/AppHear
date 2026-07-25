"""N1-N3 runner: apply normalization to each stage-E clip (over its D2 span) and report
CROSS-SIGNER INVARIANCE — the success metric for this feature. Writes a lightweight norm
manifest (params per clip) for the eventual feature-schema sidecar; the normalized landmarks
themselves are (re)produced at feature extraction F, not persisted here.

  python -m pipeline.normalize.run --split val
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np

from ..detect.schema import SpanSidecar
from ..extract.schema import ClipLandmarks
from .config import NormalizeConfig, load_config
from .handedness import decide_handedness
from .scale import clip_scale
from .transforms import _shoulder_angle, normalize_clip

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "normalize.yaml"

MANIFEST_FIELDS = (
    "clip_id",
    "split",
    "participant_id",
    "gloss",
    "scale",
    "roll_deg",
    "dominant",
    "mirrored",
    "norm_shoulder_width",
    "residual_deg",
    "canonical",
    "params_hash",
)


def _invariance(pose_norm: np.ndarray, onset: int, release: int, eps: float) -> tuple:
    """(normalized shoulder width, residual shoulder angle deg, canonical-after-norm)."""
    if onset < 0:
        onset, release = 0, pose_norm.shape[0] - 1
    span = pose_norm[onset : release + 1]
    width = clip_scale(span)
    residual_deg = math.degrees(_shoulder_angle(span))
    canonical = not decide_handedness(pose_norm, onset, release, eps).mirrored
    return width, residual_deg, canonical


def run(split: str, limit: int | None, config_path: Path) -> int:
    cfg = load_config(config_path)
    in_dir = cfg.input_root / split
    npz_files = sorted(in_dir.glob("*.npz"))
    if not npz_files:
        print(f"[normalize] no clips in {in_dir} — run stages E and D first", file=sys.stderr)
        return 2
    if limit is not None:
        npz_files = npz_files[:limit]

    manifest_path = cfg.output_root / f"manifest_norm_{split}.csv"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    metrics: list[tuple[str, float, float, bool, bool]] = (
        []
    )  # signer, width, |resid_deg|, mirr, canon
    n_failed = 0
    for npz_path in npz_files:
        cid = npz_path.stem
        span_path = cfg.spans_root / split / f"{cid}.span.json"
        if not span_path.exists():
            continue  # no span yet — D1/D2 hasn't covered this clip
        try:
            clip = ClipLandmarks.load(npz_path)
            span = SpanSidecar.load(span_path)
            _, pose_norm, params = normalize_clip(
                clip.hands_image, clip.pose_image, span.onset, span.release, cfg
            )
            width, residual_deg, canonical = _invariance(
                pose_norm, span.onset, span.release, cfg.handedness_epsilon
            )
            rows.append(
                {
                    "clip_id": cid,
                    "split": split,
                    "participant_id": span.participant_id,
                    "gloss": span.gloss,
                    "scale": round(params.scale, 6),
                    "roll_deg": round(math.degrees(params.roll_angle), 3),
                    "dominant": params.dominant,
                    "mirrored": params.mirrored,
                    "norm_shoulder_width": round(width, 5),
                    "residual_deg": round(residual_deg, 4),
                    "canonical": canonical,
                    "params_hash": cfg.params_hash,
                }
            )
            metrics.append(
                (span.participant_id, width, abs(residual_deg), params.mirrored, canonical)
            )
        except Exception as err:  # noqa: BLE001
            print(f"[normalize] FAILED {cid}: {err}", file=sys.stderr)
            n_failed += 1

    with manifest_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    _report(split, metrics, cfg, n_failed, manifest_path)
    return 0


def _report(
    split: str,
    metrics: list[tuple[str, float, float, bool, bool]],
    cfg: NormalizeConfig,
    n_failed: int,
    manifest_path: Path,
) -> None:
    print(f"\n[normalize] done {split}: ok={len(metrics)} failed={n_failed} -> {manifest_path}")
    if not metrics:
        return
    signers = {m[0] for m in metrics}
    widths = np.array([m[1] for m in metrics])
    residuals = np.array([m[2] for m in metrics])
    mirrored = np.array([m[3] for m in metrics])
    canonical = np.array([m[4] for m in metrics])

    print(f"\n=== N1-N3 invariance validation ({split}, params={cfg.params_hash}) ===")
    print(f"clips: {len(metrics)} across {len(signers)} signers")
    if cfg.n1_scale:
        print(
            f"N1 scale: normalized shoulder width mean={widths.mean():.4f} "
            f"std={widths.std():.4f}  (want mean~1.0 std~0)"
        )
    if cfg.n2_roll:
        print(
            f"N2 roll: residual shoulder angle mean|deg|={residuals.mean():.4f} "
            f"max={residuals.max():.4f}  (want ~0)"
        )
    if cfg.n3_handedness:
        print(
            f"N3 handedness: mirrored={mirrored.mean():.0%} of clips; "
            f"canonical-after-norm={canonical.mean():.0%}  (want 100%)"
        )


def main() -> int:
    p = argparse.ArgumentParser(description="AppHear 3 N1-N3 normalization + invariance check")
    p.add_argument("--split", default="val", choices=["train", "val", "test"])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = p.parse_args()
    return run(args.split, args.limit, args.config)


if __name__ == "__main__":
    raise SystemExit(main())
