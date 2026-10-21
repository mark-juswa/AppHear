"""Held-out end-to-end benchmark on the phone's 15 fps camera grid (perception-throughput probe).

heldout_dev_e2e.py samples every clip at one fixed interval. On the phone, observations can only
land on camera frames (front camera: 66.654 ms apart), and a pipelined perception stage delivers
a mix of 2-, 3- or 4-frame gaps. This wrapper keeps everything else identical (same signer-disjoint
DEV streams and seed, unchanged S2, CONFIRM_BOUNDARY decoder, materializer and WORD) and only
replaces the per-clip sampler: each next observation is k camera frames later, k drawn i.i.d. from
--gap-mix (e.g. "2:0.75,3:0.25"), then mapped to the nearest unique 30 fps source frame.

Decoder thresholds (133.308 / 266.616 / 399.924 / 533.232 ms) are exact multiples of the camera
frame, so a 2-frame gap sits on the PRE-gap, minimum-active and post-confirm boundaries. The 30 fps
sources give 133.333 ms gaps (always >= threshold); --time-scale 0.9998 gives 133.31 - 0.03 ms gaps
just below it, bounding what camera-timestamp jitter can flip on the phone.
Research only; no model, threshold or runtime change.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics import heldout_dev_e2e as bench  # noqa: E402
from pipeline.perception_vnext.recognition_schema import select_nearest_unique  # noqa: E402

CAMERA_FRAME_MS = 66.654


def parse_mix(text: str) -> tuple[np.ndarray, np.ndarray]:
    pairs = [item.split(":") for item in text.split(",")]
    gaps = np.asarray([int(k) for k, _ in pairs])
    weights = np.asarray([float(w) for _, w in pairs])
    if (gaps < 1).any() or (weights < 0).any() or weights.sum() <= 0:
        raise ValueError("gap mix must be positive frame counts with non-negative weights")
    return gaps, weights / weights.sum()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--s2-keras", type=Path, required=True)
    parser.add_argument("--s2-normalization", type=Path, required=True)
    parser.add_argument("--recognizer", type=Path, required=True)
    parser.add_argument("--gap-mix", required=True, help='camera-frame gaps, e.g. "2:0.75,3:0.25"')
    parser.add_argument("--decoder-variant", default="CONFIRM_BOUNDARY_70")
    parser.add_argument("--seed", type=int, default=20261020)
    parser.add_argument(
        "--time-scale", type=float, default=1.0,
        help="multiply stream timestamps (e.g. 0.9998 puts 2-frame gaps just below 133.308 ms)",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    gaps, weights = parse_mix(args.gap_mix)
    mean_interval = float(CAMERA_FRAME_MS * (gaps * weights).sum())
    draws = np.random.default_rng(args.seed)

    def camera_grid(raw, interval: float, phase: float) -> np.ndarray:  # noqa: ARG001
        t = np.asarray(raw.timestamp_ms, np.float64)
        steps = draws.choice(gaps, size=int((t[-1] - t[0]) / CAMERA_FRAME_MS) + 2, p=weights)
        targets = t[0] + phase + np.concatenate([[0.0], np.cumsum(steps * CAMERA_FRAME_MS)])
        return select_nearest_unique(t, targets[targets <= t[-1] + 1e-6])

    bench.sparse = camera_grid
    root = args.evidence_root
    package = bench.suite.load_package("EVAL", "v1", args.s2_keras, args.s2_normalization)
    word = bench.Word(args.recognizer, root / bench.VOCAB)
    streams = bench.build_streams(root, mean_interval)
    if args.time_scale != 1.0:
        import dataclasses

        for stream in streams:
            raw = stream["raw"]
            stream["raw"] = dataclasses.replace(
                raw, timestamp_ms=np.asarray(raw.timestamp_ms, np.float64) * args.time_scale)
    from eval.runtime_diagnostics.event_separation import VARIANTS, use_variant

    variant = next(v for v in VARIANTS if v.name == args.decoder_variant)
    with use_variant(variant):
        summary = bench.evaluate(package, word, streams)
    for mode in ("NATURAL", "CONTINUOUS"):
        summary[mode]["observations_per_second"] = summary[mode]["observations"] / (
            summary[mode]["minutes"] * 60.0)
    summary.pop("event_records", None)
    result = {
        "schema": "apphear.heldout_dev_e2e_camera_grid.v1",
        "decoder_variant": variant.name,
        "s2_package": package.identity,
        "recognizer_sha256": word.sha256,
        "camera_frame_ms": CAMERA_FRAME_MS,
        "gap_mix": {int(k): float(w) for k, w in zip(gaps, weights)},
        "mean_interval_ms": mean_interval,
        "seed": args.seed,
        "time_scale": args.time_scale,
        "streams": len(streams),
        "summary": summary,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({m: {k: summary[m][k] for k in ("correct_word_rate", "detection_rate",
          "word_precision", "extra_events_per_minute", "observations_per_second")}
          for m in ("NATURAL", "CONTINUOUS")}, indent=1), flush=True)


if __name__ == "__main__":
    main()
