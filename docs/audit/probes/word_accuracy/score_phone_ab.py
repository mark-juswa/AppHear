"""Score a live phone WORD A/B session from `adb logcat -v time -s AppHearPhone` (research only).

In EXPERIMENTAL_WORD_BLEND every committed event logs the displayed WORD_BLEND_01 prediction and
the frozen recognizer's prediction on the identical materialized window (`pairedGloss`), so one
session gives an exact paired classifier comparison. Ground truth is the protocol, not the log:
the signer performs the blocks of `protocol.json` in order and rests with hands down for at least
`--gap` seconds between blocks; commits are grouped into blocks by those gaps and each block's
intended gloss is taken from the protocol. If the number of gap-separated groups differs from the
protocol, the script prints the groups and stops; pass `--groups` (event-id ranges, one per block,
e.g. 1-3 4-7 ...) after checking them against what was actually signed. A prediction is correct
only when it equals the intended gloss of its block. Development-exposed evidence (one signer).
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

LINE = re.compile(
    r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+).*commit configuration=(\S+) .*?event=(\d+) .*?gloss=(\S+) "
    r"probability=(\S+) word=(\S+) wordMs=(\S+) top5=(\S+)"
    r"(?: paired=(\S+) pairedGloss=(\S+) pairedProbability=(\S+) pairedMs=(\S+) pairedTop5=(\S+))?"
)
CONFIG = re.compile(
    r"configuration=(\S+) package=(\S+) word=(\S+) wordModel=(\S+) paired=(\S+) fallback=(\S+)"
)


def parse(path: Path) -> tuple[list[dict], list[str]]:
    events, sessions = [], []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if (m := CONFIG.search(line)) and "commit" not in line:
            sessions.append(" ".join(m.groups()))
        m = LINE.search(line)
        if not m:
            continue
        g = m.groups()
        events.append(
            {
                "t": datetime.strptime("2026-" + g[0], "%Y-%m-%d %H:%M:%S.%f").timestamp(),
                "configuration": g[1],
                "event": int(g[2]),
                "gloss": g[3],
                "p": float(g[4]),
                "word": g[5],
                "word_ms": float(g[6]),
                "top5": g[7].split("|"),
                "paired_gloss": g[9],
                "paired_p": float(g[10]) if g[10] else None,
                "paired_ms": float(g[11]) if g[11] else None,
                "paired_top5": g[12].split("|") if g[12] else None,
            }
        )
    return events, sessions


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--logcat", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--gap", type=float, default=6.0, help="seconds of rest that end a block")
    parser.add_argument("--groups", nargs="*", help="manual event-id ranges, one per block")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    blocks = protocol["blocks"]
    events, sessions = parse(args.logcat)
    if args.groups:
        ranges = [tuple(int(x) for x in r.split("-")) for r in args.groups]
        groups = [[e for e in events if a <= e["event"] <= b] for a, b in ranges]
    else:
        groups = [[]]
        for e in events:
            if groups[-1] and e["t"] - groups[-1][-1]["t"] > args.gap:
                groups.append([])
            groups[-1].append(e)
        groups = [g for g in groups if g]
        # a final non-sign movement block that produced no commit at all is a clean result
        if len(groups) == len(blocks) - 1 and not blocks[-1]["signs"]:
            groups.append([])
    if len(groups) != len(blocks):
        for k, g in enumerate(groups):
            print(k + 1, [(e["event"], e["gloss"]) for e in g])
        raise SystemExit(f"{len(groups)} groups vs {len(blocks)} protocol blocks: pass --groups")
    rows, per_sign = [], defaultdict(lambda: defaultdict(int))
    for block, group in zip(blocks, groups, strict=True):
        intended = block["signs"]
        for k, e in enumerate(group):
            # within a sequence block, the k-th event is credited to the k-th intended sign
            target = intended[k] if k < len(intended) else None
            row = {
                **{
                    x: e[x] for x in ("event", "gloss", "p", "paired_gloss", "word_ms", "paired_ms")
                },
                "block": block["name"],
                "intended": target,
            }
            rows.append(row)
            s = per_sign[target or "EXTRA"]
            s["events"] += 1
            if target is None:
                continue
            s["primary_correct"] += int(e["gloss"] == target)
            s["primary_top5"] += int(target in e["top5"])
            if e["paired_gloss"] is not None:
                s["paired_correct"] += int(e["paired_gloss"] == target)
                s["paired_top5"] += int(target in (e["paired_top5"] or []))
        for target in intended[len(group) :]:
            per_sign[target]["missed"] += 1
    intended_events = [r for r in rows if r["intended"]]
    summary = {
        "sessions": sessions,
        "events": len(rows),
        "intended_events": len(intended_events),
        "extra_events": sum(1 for r in rows if r["intended"] is None),
        "missed_signs": sum(v["missed"] for v in per_sign.values()),
        "primary_correct": sum(r["gloss"] == r["intended"] for r in intended_events),
        "paired_correct": sum(
            r["paired_gloss"] == r["intended"]
            for r in intended_events
            if r["paired_gloss"] is not None
        ),
        "primary_only_correct": sum(
            r["gloss"] == r["intended"] != r["paired_gloss"] for r in intended_events
        ),
        "paired_only_correct": sum(
            r["paired_gloss"] == r["intended"] != r["gloss"] for r in intended_events
        ),
        "word_ms_median": float(np.median([r["word_ms"] for r in rows])) if rows else None,
        "paired_ms_median": (
            float(np.median([r["paired_ms"] for r in rows if r["paired_ms"] is not None]))
            if any(r["paired_ms"] is not None for r in rows)
            else None
        ),
        "per_sign": {k: dict(v) for k, v in per_sign.items()},
    }
    print(json.dumps(summary, indent=1))
    for r in rows:
        print(r)
    if args.out:
        args.out.write_text(
            json.dumps({"summary": summary, "rows": rows}, indent=1) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
