"""Analyse one Stage-2 shadow capture: device WORD pair + offline S2 replays on the same frames.

Part 1 (device): every logged event's primary (frozen) and shadow (WORD v2) outputs, verified
against offline inference on the device's own Recognition V2 source indices (parity), with the
block it fell in and per-window hand/body evidence.
Part 2 (offline, exact-parity raw): S2-R2, S2-R3 Arm A e10 and Arm A e21 @ theta 0.8 replayed
through the reference PRE_OR_POST lifecycle and materializer, each window classified by both
recognizers. Labels are PROTOCOL EXPECTATIONS per block only (not human-reviewed): an output counts
as an expected-gloss output when its gloss is still unclaimed in that block's expected list.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "docs/audit/probes/pipeline_v3"))
sys.path.insert(0, str(REPO / "docs/audit/probes/s2_discrimination"))

import operating_point as op  # noqa: E402
import stage_attribution as sa  # noqa: E402

from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics.phone_s2_exact_parity_and_r2_decision import (  # noqa: E402
    load_capture,
)

E = Path("F:/ASL DATASET/5. Apphear3")
RU = E / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
EXPECTED = {
    "A_HANDS_DOWN": ["HELLO", "HOME"],
    "B_HANDS_UP": ["HELLO", "HOME"],
    "C_REPEAT_HANDS_UP": ["HELLO", "HELLO"],
    "D_SIGN_THEN_HOLD": ["HELLO"],
    "E_ORDINARY_MOVEMENT": [],
}


def blocks_of(session: Path) -> list[dict[str, Any]]:
    out, cur = [], {}
    for line in (session / "attempts.jsonl").open(encoding="utf-8"):
        a = json.loads(line)
        if a["action"] == "BEGIN":
            cur = {"block": a["expected_gloss"], "first": a["observation_count_before_mark"]}
        else:
            cur["last"] = a["observation_count_after_drain"] - 1
            out.append(cur)
    return out


def block_at(blocks: list[dict[str, Any]], index: int) -> str:
    return next((b["block"] for b in blocks if b["first"] <= index <= b["last"]), "OUTSIDE_BLOCKS")


def score(outputs: list[tuple[str, str]]) -> dict[str, int]:
    """outputs: (block, gloss). Expected-gloss outputs claim one expected slot each."""
    remaining = {b: Counter(g) for b, g in EXPECTED.items()}
    hit = wrong_in_sign_block = nonsign = outside = 0
    for block, gloss in outputs:
        if block == "OUTSIDE_BLOCKS":
            outside += 1
        elif block == "E_ORDINARY_MOVEMENT":
            nonsign += 1
        elif remaining[block][gloss] > 0:
            remaining[block][gloss] -= 1
            hit += 1
        else:
            wrong_in_sign_block += 1
    return {
        "expected_gloss_outputs": hit,
        "other_outputs_in_sign_blocks": wrong_in_sign_block,
        "outputs_in_ordinary_movement": nonsign,
        "outputs_outside_blocks": outside,
        "expected_signs": sum(len(g) for g in EXPECTED.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    args = parser.parse_args()
    session = args.session
    raw = load_capture(session, require_full_session=False).raw
    t = np.asarray(raw.timestamp_ms, np.float64)
    blocks = blocks_of(session)
    frozen = sa.Recognizer(E)
    v2 = sa.Recognizer(E, RU / "word_track_robust_aug_02/best.keras")
    events = [json.loads(line) for line in (session / "events.jsonl").open(encoding="utf-8")]
    windows = [
        suite._take(
            raw,
            np.asarray(e["recognition_v2_source_indices"]),
            t[np.asarray(e["recognition_v2_source_indices"])],
        )
        for e in events
    ]
    device = []
    for e, pf, pv in zip(
        events, frozen.probabilities(windows), v2.probabilities(windows), strict=True
    ):
        idx = np.asarray(e["materialized_source_indices"])
        device.append(
            {
                "event": e["event_id"],
                "block": block_at(blocks, int(e["logical_active_start_index"])),
                "device_frozen": [e["top1_gloss"], round(e["top1_probability"], 3)],
                "device_v2": [
                    e.get("shadow_top1_gloss"),
                    round(e.get("shadow_top1_probability") or 0, 3),
                ],
                "frozen_parity": frozen.glosses[int(pf.argmax())] == e["top1_gloss"]
                and abs(float(pf.max()) - e["top1_probability"]) < 1e-3,
                "v2_parity": v2.glosses[int(pv.argmax())] == e.get("shadow_top1_gloss")
                and abs(float(pv.max()) - (e.get("shadow_top1_probability") or -1)) < 1e-3,
                "shadow_ms": e.get("shadow_recognition_invocation_ms"),
                "hand_fraction": round(float(np.mean(np.any(raw.hand_observed[idx], axis=1))), 2),
                "body_fraction": round(float(np.mean(raw.body_available[idx])), 2),
            }
        )
    result: dict[str, Any] = {
        "session": session.name,
        "label_status": "PROTOCOL_EXPECTED_ONLY_NOT_HUMAN_REVIEWED",
        "observations": len(t),
        "hand_fraction": float(np.mean(np.any(raw.hand_observed, axis=1))),
        "body_fraction": float(np.mean(raw.body_available)),
        "blocks": [
            {
                **b,
                "hand_fraction": round(
                    float(np.mean(np.any(raw.hand_observed[b["first"] : b["last"] + 1], axis=1))), 2
                ),
                "body_fraction": round(
                    float(np.mean(raw.body_available[b["first"] : b["last"] + 1])), 2
                ),
            }
            for b in blocks
        ],
        "device_events": device,
        "device_score": {
            "frozen": score([(d["block"], d["device_frozen"][0]) for d in device]),
            "v2": score([(d["block"], d["device_v2"][0]) for d in device]),
        },
    }
    features = suite.features_for_raw(raw, "v1")
    ref = suite.read_json(suite.SUITES["03"][0])["reference_package"]
    packages = {
        "S2_R2": suite.load_package("S2_R2", "v1", E / ref["keras"], E / ref["normalization"]),
        "ARM_A_E10": suite.load_package(
            "E10",
            "v1",
            RU / "s2_r3_arm_a_01/epoch_10.keras",
            RU / "s2_r3_arm_a_01/normalization.json",
        ),
        "ARM_A_E21_T08": op.load(21, 0.8),
    }
    offline = {}
    for name, pkg in packages.items():
        p = pkg.probabilities(features)
        states = np.argmax(p, axis=1)
        evs = suite.replay(
            [
                {
                    "source_index": i,
                    "source_timestamp_ms": float(t[i]),
                    "argmax_state": int(states[i]),
                    "pre_probability": float(p[i, 0]),
                    "active_probability": float(p[i, 1]),
                    "post_probability": float(p[i, 2]),
                }
                for i in range(len(t))
            ],
            allow_post_rearm=True,
            exact_android_commit_recovery=True,
        )["events"]
        wins = []
        for e in evs:
            a, b = sa.window_for(
                t,
                int(e["logical_active_start_index"]),
                int(e["logical_active_end_index"]),
                int(e["first_post_index"]),
                int(e["emitted_at_index"]),
            )
            wins.append(suite.slice_raw(raw, a, b))
        blk = [block_at(blocks, int(e["logical_active_start_index"])) for e in evs]
        gf = [frozen.glosses[int(x.argmax())] for x in frozen.probabilities(wins)] if wins else []
        gv = [v2.glosses[int(x.argmax())] for x in v2.probabilities(wins)] if wins else []
        offline[name] = {
            "events": len(evs),
            "events_by_block": dict(Counter(blk)),
            "frozen": score(list(zip(blk, gf, strict=True))),
            "v2": score(list(zip(blk, gv, strict=True))),
            "outputs": [[b, f, v] for b, f, v in zip(blk, gf, gv, strict=True)],
        }
    result["offline_s2_replay"] = offline
    if name_check := [d for d in device if not (d["frozen_parity"] and d["v2_parity"])]:
        result["parity_failures"] = name_check
    out = (
        REPO
        / "docs/audit/probes/word_track"
        / f"shadow_session_{session.name.removeprefix('session_')}.json"
    )
    out.write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "observations",
                    "hand_fraction",
                    "body_fraction",
                    "blocks",
                    "device_score",
                )
            },
            indent=1,
        )
    )
    for d in device:
        print(d)
    for name, o in offline.items():
        print(name, o["events"], o["events_by_block"], "frozen", o["frozen"], "v2", o["v2"])
        print("   ", o["outputs"])


if __name__ == "__main__":
    main()
