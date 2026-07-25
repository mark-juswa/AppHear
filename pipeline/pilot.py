"""Cross-signer PILOT: a small, gloss-restricted, multi-signer slice through the whole offline
pipeline so we get a real (rough) cross-signer number and re-check the open caveats BEFORE
committing hours to the full ~83k-video run.

Why gloss-restricted: train/val/test are signer-disjoint, so to classify we need the SAME
glosses in every split. We pick K glosses present in all three splits, then extract their clips
(capped per split) across whatever signers have them → aligned classes + held-out signers.

Recipe:
  python -m pipeline.pilot            # select + extract + detect + features for train/val/test
  python -m model.train --epochs 25   # quick train on the pilot features
  python -m eval.run                  # first rough cross-signer number + per-signer

Writes into the normal derived roots; stray non-pilot clips are dropped as OOV at stage F
(train vocab = the K pilot glosses), so the result stays clean without separate dirs."""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import Counter
from pathlib import Path

from .detect.run import DEFAULT_CONFIG as DETECT_CFG
from .detect.run import run as detect_run
from .extract.config import load_config as load_extract_config
from .extract.run import DEFAULT_CONFIG as EXTRACT_CFG
from .extract.run import run as extract_run
from .features.run import DEFAULT_CONFIG as FEATURES_CFG
from .features.run import run as features_run

SPLITS = ("train", "val", "test")


def _rows(splits_dir: Path, split: str) -> list[dict[str, str]]:
    with (splits_dir / f"{split}.csv").open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def select_pilot(
    splits_dir: Path, glosses_k: int, max_per_split: int, seed: int
) -> tuple[list[str], dict[str, set[str]]]:
    """Pick K glosses common to all splits (most frequent in train), then a capped, shuffled
    clip allowlist per split. Returns (chosen_glosses, {split: {video_file}})."""
    rows = {s: _rows(splits_dir, s) for s in SPLITS}
    gloss_sets = {s: {r["Gloss"] for r in rows[s]} for s in SPLITS}
    common = gloss_sets["train"] & gloss_sets["val"] & gloss_sets["test"]
    if not common:
        raise ValueError("no glosses common to all three splits")
    train_freq = Counter(r["Gloss"] for r in rows["train"] if r["Gloss"] in common)
    chosen = [g for g, _ in train_freq.most_common(glosses_k)]

    rng = random.Random(seed)
    allowlists: dict[str, set[str]] = {}
    for s in SPLITS:
        picked = [r["Video file"] for r in rows[s] if r["Gloss"] in chosen]
        rng.shuffle(picked)
        allowlists[s] = set(picked[:max_per_split])
    return chosen, allowlists


def run(glosses_k: int, max_per_split: int, seed: int) -> int:
    splits_dir = load_extract_config(EXTRACT_CFG).splits_dir
    if not splits_dir.exists():
        print(f"[pilot] splits dir not found: {splits_dir}", file=sys.stderr)
        return 2
    chosen, allowlists = select_pilot(splits_dir, glosses_k, max_per_split, seed)
    print(
        f"[pilot] {len(chosen)} glosses across all splits; "
        f"clips per split: {{{', '.join(f'{s}:{len(a)}' for s, a in allowlists.items())}}}"
    )

    for split in SPLITS:
        print(f"\n########## PILOT: {split} ##########")
        stages = [
            ("extract", lambda sp=split: extract_run(sp, None, EXTRACT_CFG, only=allowlists[sp])),
            ("detect", lambda sp=split: detect_run(sp, None, DETECT_CFG)),
            ("features", lambda sp=split: features_run(sp, sp == "train", None, FEATURES_CFG)),
        ]
        for name, stage in stages:  # sequential; each depends on the previous
            code = stage()
            if code != 0:
                print(f"[pilot] {split} stage '{name}' failed (exit {code})", file=sys.stderr)
                return code

    print(
        "\n[pilot] pipeline done. Next:\n"
        "  python -m model.train --epochs 25\n"
        "  python -m eval.run"
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="AppHear 3 cross-signer pilot slice")
    p.add_argument("--glosses", type=int, default=20, help="number of common glosses (classes)")
    p.add_argument("--max-per-split", type=int, default=400, help="clip cap per split")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()
    return run(args.glosses, args.max_per_split, args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
