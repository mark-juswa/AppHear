"""F18 skew-test fixture exporter. Runs the EXACT offline S4 path (N1-N3 normalize + 258-vector,
N4 OFF / real-timed) on a handful of real val clips and writes them as JSON golden vectors for the
Android Kotlin S4 port to reproduce byte-for-byte. This isolates PORTING skew: the fixture gives
the Kotlin side the same raw landmarks + span, so it computes the same (non-causal) params and must
match. (Causal online-param skew is a separate, later measurement.)

  python -m pipeline.features.export_golden            # -> android test resources
  python -m pipeline.features.export_golden --limit 6

Encodes NaN as JSON null (raw MediaPipe landmarks are NaN when absent); the Kotlin loader maps
null -> Float.NaN. Arrays are flattened row-major with an explicit shape."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

from ..detect.schema import SpanSidecar
from ..extract.schema import ClipLandmarks
from ..normalize.causal import load_causal_config
from ..normalize.config import load_config as load_normalize_config
from ..quality.config import load_config as load_quality_config
from .config import load_config
from .contract import clip_features_causal, clip_features_realtimed

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "features.yaml"
# Kotlin JVM unit tests read from src/test/resources on the classpath.
DEFAULT_OUT = (
    Path(__file__).resolve().parents[2]
    / "android" / "app" / "src" / "test" / "resources" / "golden" / "s4_golden.json"
)


def _flat(a: np.ndarray) -> list:
    """Flatten row-major; NaN -> null (JSON-safe), else float."""
    return [None if math.isnan(v) else float(v) for v in a.astype(np.float64).ravel()]


def run(limit: int, want_mirrored: int, config_path: Path, out_path: Path) -> int:
    fcfg = load_config(config_path)
    ncfg = load_normalize_config(fcfg.normalize_config)
    ccfg = load_causal_config()
    qcfg = load_quality_config(fcfg.quality_config)
    t_max = fcfg.streaming_t_max

    in_dir = qcfg.input_root / "val"
    npz_files = sorted(in_dir.glob("*.npz"))
    if not npz_files:
        print(f"[golden] no clips in {in_dir}", file=sys.stderr)
        return 2

    clips: list[dict] = []
    n_mirrored = 0
    for npz_path in npz_files:
        if len(clips) >= limit and n_mirrored >= want_mirrored:
            break
        cid = npz_path.stem
        span_path = qcfg.spans_root / "val" / f"{cid}.span.json"
        if not span_path.exists():
            continue
        try:
            span = SpanSidecar.load(span_path)
            clip = ClipLandmarks.load(npz_path)
            # skip clips whose real span exceeds t_max (would be tail-truncated → frame-count
            # mismatch in the Kotlin test, which reproduces the untruncated real frames)
            real_len = clip.pose_image.shape[0] if span.onset < 0 else span.release - span.onset + 1
            if real_len > t_max:
                continue
            feat, fmask, length, params = clip_features_realtimed(
                clip.hands_image, clip.pose_image, span.onset, span.release, ncfg, t_max
            )
            cfeat, _, _, _ = clip_features_causal(
                clip.hands_image, clip.pose_image, span.onset, span.release, ncfg, ccfg, t_max
            )
        except Exception as err:  # noqa: BLE001
            print(f"[golden] skip {cid}: {err}", file=sys.stderr)
            continue

        # keep collecting until we have `limit` clips AND enough mirrored examples for coverage
        need_more = len(clips) < limit
        need_mirror = params.mirrored and n_mirrored < want_mirrored
        if not (need_more or need_mirror):
            continue
        if params.mirrored:
            n_mirrored += 1

        t = clip.pose_image.shape[0]
        clips.append(
            {
                "clip_id": cid,
                "onset": int(span.onset),
                "release": int(span.release),
                "hands_image": {"shape": [t, 2, 21, 3], "data": _flat(clip.hands_image)},
                "pose_image": {"shape": [t, 33, 4], "data": _flat(clip.pose_image)},
                "length": int(length),
                # export only the real (unpadded) frames; the padded tail is zeros by construction
                "expected_feature": {"shape": [length, 258], "data": _flat(feat[:length])},
                # causal (streaming) features — each frame's params from [onset..t] only
                "causal_expected_feature": {"shape": [length, 258], "data": _flat(cfeat[:length])},
                "params": {
                    "scale": float(params.scale),
                    "roll_angle": float(params.roll_angle),
                    "dominant": params.dominant,
                    "mirrored": bool(params.mirrored),
                },
            }
        )

    if not clips:
        print("[golden] no clips exported", file=sys.stderr)
        return 2

    payload = {
        "schema_version": "3.0",
        "t_max": t_max,
        "tolerance": 1e-4,
        "config": {
            "n1_scale": ncfg.n1_scale,
            "n2_roll": ncfg.n2_roll,
            "n2_yaw": ncfg.n2_yaw,
            "n3_handedness": ncfg.n3_handedness,
            "handedness_epsilon": ncfg.handedness_epsilon,
        },
        "causal_config": {
            "mirror_decisive_margin": ccfg.mirror_decisive_margin,
            "mirror_min_abs_diff": ccfg.mirror_min_abs_diff,
            "mirror_confirm_k": ccfg.mirror_confirm_k,
        },
        "clips": clips,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload), encoding="utf-8")
    kb = out_path.stat().st_size / 1024
    print(f"[golden] wrote {len(clips)} clips ({n_mirrored} mirrored) -> {out_path} ({kb:.0f} KB)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Export S4 golden-vector skew-test fixtures (F18)")
    p.add_argument("--limit", type=int, default=6)
    p.add_argument("--want-mirrored", type=int, default=2)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    return run(args.limit, args.want_mirrored, args.config, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
