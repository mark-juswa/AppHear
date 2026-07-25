"""One-command offline pipeline: extract (E) -> detect (D1/D2) -> features (F, incl. N1-N4 + Q)
for one split. Makes the long jobs the developer runs push-button and resumable (E and D are
resumable; re-running skips done clips).

Recipe (run once, in order; --workers fans extraction across CPU cores):
  python -m pipeline.run_pipeline --split train --build-vocab --workers 8
  python -m pipeline.run_pipeline --split val --workers 8
  python -m pipeline.run_pipeline --split test --workers 8
  python -m pipeline.splits.run                 # freeze/verify signer splits
  python -m model.train                         # then train (slow; developer runs)

Each stage keeps its own config; this only orders them."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable

from .detect.run import DEFAULT_CONFIG as DETECT_CFG
from .detect.run import run as detect_run
from .extract.run import DEFAULT_CONFIG as EXTRACT_CFG
from .extract.run import run as extract_run
from .features.run import DEFAULT_CONFIG as FEATURES_CFG
from .features.run import run as features_run


def run_split(split: str, build_vocab: bool, limit: int | None, workers: int) -> int:
    print(f"\n########## PIPELINE: {split} (workers={workers}) ##########")
    stages: list[tuple[str, Callable[[], int]]] = [
        ("extract (E)", lambda: extract_run(split, limit, EXTRACT_CFG, workers=workers)),
        ("detect (D1/D2)", lambda: detect_run(split, limit, DETECT_CFG)),
        ("features (F)", lambda: features_run(split, build_vocab, limit, FEATURES_CFG)),
    ]
    for name, stage in stages:  # sequential; stop at the first failure
        code = stage()
        if code != 0:
            print(f"[pipeline] stage '{name}' failed (exit {code}) — stopping", file=sys.stderr)
            return code
    print(f"########## PIPELINE {split}: complete ##########")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="AppHear 3 offline pipeline E->D->F for a split")
    p.add_argument("--split", default="val", choices=["train", "val", "test"])
    p.add_argument(
        "--build-vocab", action="store_true", help="build the gloss vocab (use on train)"
    )
    p.add_argument("--limit", type=int, default=None, help="cap clips per stage (smoke/subset)")
    p.add_argument(
        "--workers",
        type=int,
        default=max(1, (os.cpu_count() or 2) - 1),
        help="parallel extraction workers",
    )
    args = p.parse_args()
    return run_split(args.split, args.build_vocab, args.limit, args.workers)


if __name__ == "__main__":
    raise SystemExit(main())
