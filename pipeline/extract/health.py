"""Cross-signer extraction health check.

Samples clips across MANY participants and reports landmark detection hit-rates per signer,
WITHOUT writing landmark files. Purpose: before the full extraction, catch signers for whom
detection quietly fails (e.g. pose never found, hands ~0 across all their clips) as opposed to
the expected low hand-rate caused by pre/post-sign dead time.

Example:
  python -m pipeline.extract.health --split val --participants 15 --per 2 --seed 0
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

from .config import ExtractConfig, load_config
from .landmarks import LandmarkExtractor
from .run import _hit_rates

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "extract.yaml"


def _sample(
    config: ExtractConfig, split: str, participants: int, per: int, seed: int
) -> list[dict[str, str]]:
    """Deterministically pick `per` clips from each of `participants` distinct signers."""
    path = config.splits_dir / f"{split}.csv"
    by_pid: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            by_pid[row["Participant ID"]].append(row)

    rng = random.Random(seed)
    eligible = sorted(pid for pid, rows in by_pid.items() if len(rows) >= per)
    chosen_pids = rng.sample(eligible, min(participants, len(eligible)))

    sample: list[dict[str, str]] = []
    for pid in chosen_pids:
        sample.extend(rng.sample(by_pid[pid], per))
    return sample


def run(split: str, participants: int, per: int, seed: int, config_path: Path) -> int:
    config = load_config(config_path)
    for task in (config.hand_task, config.pose_task):
        if not task.exists():
            print(f"[health] missing model asset: {task}", file=sys.stderr)
            return 2

    sample = _sample(config, split, participants, per, seed)
    per_pid: dict[str, list[tuple[float, float, float]]] = defaultdict(list)

    with LandmarkExtractor(config) as extractor:
        for i, row in enumerate(sample, start=1):
            video_path = config.videos_dir / row["Video file"]
            try:
                clip, _ = extractor.extract(video_path)
                per_pid[row["Participant ID"]].append(_hit_rates(clip))
            except Exception as err:  # noqa: BLE001
                print(f"[health] FAILED {row['Video file']}: {err}", file=sys.stderr)
            if i % 10 == 0:
                print(f"[health] {i}/{len(sample)} clips")

    print(f"\n=== cross-signer extraction health ({split}) ===")
    print(f"{'participant':<14}{'clips':>6}{'hand':>8}{'two_hand':>10}{'pose':>8}")
    all_pose: list[float] = []
    flags: list[str] = []
    for pid in sorted(per_pid):
        rates = per_pid[pid]
        n = len(rates)
        hand = sum(r[0] for r in rates) / n
        two = sum(r[1] for r in rates) / n
        pose = sum(r[2] for r in rates) / n
        all_pose.append(pose)
        print(f"{pid:<14}{n:>6}{hand:>8.2f}{two:>10.2f}{pose:>8.2f}")
        if pose < 0.9:
            flags.append(f"  - {pid}: pose_hit_rate {pose:.2f} (<0.90) — possible detector gap")
        if hand < 0.05:
            flags.append(f"  - {pid}: hand_hit_rate {hand:.2f} (~0) — hands never found")

    print(
        f"\nsigners sampled: {len(per_pid)} | mean pose hit-rate: "
        f"{(sum(all_pose) / len(all_pose)) if all_pose else 0:.3f}"
    )
    if flags:
        print("\nFLAGS (investigate before full extraction):")
        print("\n".join(flags))
    else:
        print("\nNo detector-failure flags: low hand-rate is dead time, not a detection gap.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Cross-signer extraction health check")
    p.add_argument("--split", default="val", choices=["train", "val", "test"])
    p.add_argument("--participants", type=int, default=15)
    p.add_argument("--per", type=int, default=2)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = p.parse_args()
    return run(args.split, args.participants, args.per, args.seed, args.config)


if __name__ == "__main__":
    raise SystemExit(main())
