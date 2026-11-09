"""Join the app's SHADOW echo log (AppHearEcho lines) with the manually specified ground truth of a labelled session (standard library only).

The shadow log was produced by the app (default-off HandEchoShadow). It only OBSERVES: nothing was suppressed. For every frame it says which values of a
fixed evaluation grid of support ratios WOULD have suppressed the weaker hand group. This script scores those counterfactual decisions against the truth
the person was asked to produce (schedule.json with wall-clock windows; the device and host clocks were verified equal to the second at session start).

Frames are joined by wall-clock window [epoch_start, epoch_start + frames/fps]. Unit of analysis: frames where both groups were observed (otherwise
nothing is duplicated). Metrics per grid value:
  echo_suppressed      one-hand frame, weaker group == the group that holds NO hand (correct drop)
  wrong_group_dropped  one-hand frame, weaker group == the REAL hand (the worst error)
  genuine_pair_dropped two-hand frame, any drop (a real hand would have been removed)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from eval.hand_diagnostics.capture_pose_session import CONFIG

GRID = [0.3, 0.4, 0.5, 0.6, 0.7]


def parse_shadow(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        i = line.find("{")
        if "apphear.hand_echo_shadow" not in line or i < 0:
            continue
        try:
            d = json.loads(line[i:])
        except json.JSONDecodeError:
            continue
        if d.get("schema") == "apphear.hand_echo_shadow.v1":
            out.append(d)
    return out


def join(records: list[dict], schedule: dict) -> list[dict]:
    """Attach truth/config/segment to every record that falls inside a segment window (others are dropped)."""
    out = []
    for seg, meta in schedule.items():
        if meta["truth"] is None or not (meta["truth"]["L"] or meta["truth"]["R"]):
            continue
        t0 = meta["epoch_start"] * 1000.0
        t1 = (meta["epoch_start"] + meta["frames"] / meta["fps"]) * 1000.0
        for r in records:
            if t0 <= r["wall_ms"] <= t1:
                out.append({**r, "segment": seg, "truth": meta["truth"], "config": meta.get("config") or CONFIG.get(seg, "other"),
                            "two_hands": bool(meta["truth"]["L"] and meta["truth"]["R"])})
    return out


def score(joined: list[dict]) -> dict:
    both = [r for r in joined if r["ratio"] is not None]          # both groups observed on the device
    res = {"frames_joined": len(joined), "frames_both_groups_observed": len(both), "by_grid": {}}
    for i, tau in enumerate(GRID):
        echo_frames = [r for r in both if not r["two_hands"]]
        pair_frames = [r for r in both if r["two_hands"]]
        dropped = lambda r, i=i: bool(r["mask"] >> i & 1)
        real_side = lambda r: "LEFT" if r["truth"]["L"] else "RIGHT"
        echo_ok = sum(1 for r in echo_frames if dropped(r) and r["weaker"] != real_side(r))
        wrong = sum(1 for r in echo_frames if dropped(r) and r["weaker"] == real_side(r))
        pair_drop = sum(1 for r in pair_frames if dropped(r))
        per_cfg = {}
        for cfg in sorted({r["config"] for r in both}):
            pf = [r for r in pair_frames if r["config"] == cfg]
            ef = [r for r in echo_frames if r["config"] == cfg]
            per_cfg[cfg] = {"one_hand_frames": len(ef), "echo_suppressed": sum(1 for r in ef if dropped(r) and r["weaker"] != real_side(r)),
                            "wrong_group_dropped": sum(1 for r in ef if dropped(r) and r["weaker"] == real_side(r)),
                            "two_hand_frames": len(pf), "genuine_pair_dropped": sum(1 for r in pf if dropped(r))}
        res["by_grid"][str(tau)] = {
            "one_hand_frames": len(echo_frames), "echo_suppressed": echo_ok,
            "echo_suppressed_rate": round(echo_ok / len(echo_frames), 4) if echo_frames else None, "wrong_group_dropped": wrong,
            "two_hand_frames": len(pair_frames), "genuine_pair_dropped": pair_drop,
            "genuine_pair_dropped_rate": round(pair_drop / len(pair_frames), 4) if pair_frames else None, "per_config": per_cfg}
    return res


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    shadow_log, schedule_json = Path(argv[0]), Path(argv[1])
    joined = join(parse_shadow(shadow_log.read_text(errors="replace")), json.loads(schedule_json.read_text()))
    print(json.dumps(score(joined), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
