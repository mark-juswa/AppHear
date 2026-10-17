"""How do S2 models behave across genuine consecutive-sign transitions? (diagnostic, no tuning)

Transitions: every pair of consecutive GENUINE signs inside one block with human boundaries --
Tier-2 SEP27 (A, B) and OCT15, plus Stage-2 shadow session 20261017T023004Z (UNBLINDED labels).
For each pair and each S2 model (S2-R2, Arm A e10, Arm A e21) the per-observation P(PRE/ACTIVE/POST)
and argmax are traced from sign-1 start to sign-2 end, together with the hand-motion signal (median
accepted wrist speed, body-normalised when possible). Summaries per pair:
  gap_obs            observations strictly between sign-1 end and sign-2 start
  active_dip         min P(ACTIVE) between the two sign cores (from sign-1 end-1 to sign-2 start+1)
  non_active_run     longest run of non-ACTIVE argmax inside that range
  post_peak          max P(POST) inside that range
  speed_dip_ratio    min wrist speed in the range / median speed inside the two signs
The same quantities are measured on confirmed non-sign intervals (sliding 2-sign-length windows) to
see whether a cue that would split signs would also fire inside ordinary movement.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "docs/audit/probes/pipeline_v3"))


from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics.phone_s2_exact_parity_and_r2_decision import (  # noqa: E402
    load_capture,
)

E = Path("F:/ASL DATASET/5. Apphear3")
RU = E / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"


def wrist_speed(raw: Any) -> np.ndarray:
    """Per-observation max accepted-wrist displacement / shoulder width (NaN when unavailable)."""
    xy = np.asarray(raw.hand_xy, np.float64)[:, :, 0, :]
    ok = np.asarray(raw.hand_observed, bool)
    xy[~ok] = np.nan
    body = np.asarray(raw.body_xy, np.float64)
    bv = np.asarray(raw.body_valid, bool)
    width = np.where(bv[:, 0] & bv[:, 1], np.linalg.norm(body[:, 0] - body[:, 1], axis=-1), np.nan)
    scale = (
        np.nanmedian(width)
        if np.any(np.isfinite(width))
        else float(np.max(raw.source_size[0])) * 0.25
    )
    t = np.asarray(raw.timestamp_ms, np.float64)
    speed = np.full(len(t), np.nan)
    with np.errstate(invalid="ignore"):
        d = np.linalg.norm(np.diff(xy, axis=0), axis=-1) / scale / (np.diff(t)[:, None] / 1000.0)
        speed[1:] = np.nanmax(d, axis=1)
    return speed


def sessions() -> list[dict[str, Any]]:
    config = suite.read_json(suite.SUITES["03"][0])
    tier = config["tier2_sessions"]
    out = []
    for name in ("SEP27_TRANSITION", "OCT15_COMPACT"):
        spec = tier[name]
        capture = E / spec["capture"]
        labels = json.loads((capture / "transition_review/human_boundaries.json").read_text())
        out.append({"name": name, "capture": capture, "labels": labels, "provenance": "blinded"})
    capture = E / "artifacts/recognition_v3_stage2_compact_device/session_20261017T023004Z"
    out.append(
        {
            "name": "SHADOW_023004Z",
            "capture": capture,
            "labels": json.loads((capture / "transition_review/human_boundaries.json").read_text()),
            "provenance": "UNBLINDED",
        }
    )
    return out


def main() -> None:
    ref = suite.read_json(suite.SUITES["03"][0])["reference_package"]
    packages = {
        "S2_R2": suite.load_package("S2_R2", "v1", E / ref["keras"], E / ref["normalization"]),
        "ARM_A_E10": suite.load_package(
            "E10",
            "v1",
            RU / "s2_r3_arm_a_01/epoch_10.keras",
            RU / "s2_r3_arm_a_01/normalization.json",
        ),
        "ARM_A_E21": suite.load_package(
            "E21",
            "v1",
            RU / "s2_r3_arm_a_01/epoch_21.keras",
            RU / "s2_r3_arm_a_01/normalization.json",
        ),
    }
    pairs, nonsign = [], []
    for s in sessions():
        raw = load_capture(s["capture"], require_full_session=False).raw
        speed = wrist_speed(raw)
        feats = suite.features_for_raw(raw, "v1")
        probs = {k: p.probabilities(feats) for k, p in packages.items()}
        signs = [
            x
            for x in s["labels"]["signs"]
            if x["judgment"] == "GENUINE_SIGN" and x["start_index"] is not None
        ]
        signs.sort(key=lambda x: x["start_index"])
        for a, b in zip(signs, signs[1:], strict=False):
            if a["condition"] != b["condition"]:
                continue
            lo, hi = a["end_index"] - 1, b["start_index"] + 1
            inside = np.r_[
                a["start_index"] : a["end_index"] + 1, b["start_index"] : b["end_index"] + 1
            ]
            ref_speed = np.nanmedian(speed[inside])
            row: dict[str, Any] = {
                "session": s["name"],
                "provenance": s["provenance"],
                "block": a["condition"],
                "pair": f"{a['gloss']}->{b['gloss']}",
                "gap_obs": b["start_index"] - a["end_index"] - 1,
                "hand_fraction": float(np.mean(np.any(raw.hand_observed[lo : hi + 1], axis=1))),
                "speed_dip_ratio": (
                    float(np.nanmin(speed[lo : hi + 1]) / ref_speed)
                    if np.any(np.isfinite(speed[lo : hi + 1])) and ref_speed > 0
                    else None
                ),
            }
            for k, p in probs.items():
                arg = np.argmax(p, axis=1)
                seg = arg[lo : hi + 1]
                runs, cur = 0, 0
                for v in seg:
                    cur = cur + 1 if v != 1 else 0
                    runs = max(runs, cur)
                row[k] = {
                    "active_dip": float(p[lo : hi + 1, 1].min()),
                    "post_peak": float(p[lo : hi + 1, 2].max()),
                    "non_active_run": int(runs),
                    "trace_argmax": "".join(
                        "RAP"[v] if v == 1 else "_AP"[v] if v == 2 else "."
                        for v in arg[a["start_index"] : b["end_index"] + 1]
                    ),
                    "sign1_active": int(np.sum(arg[a["start_index"] : a["end_index"] + 1] == 1)),
                    "sign2_active": int(np.sum(arg[b["start_index"] : b["end_index"] + 1] == 1)),
                }
            pairs.append(row)
        for n in s["labels"].get("negative_intervals", []):
            if n.get("start_index") is None or n["judgment"] != "CONFIRMED_NON_SIGN":
                continue
            for start in range(n["start_index"], n["end_index"] - 10, 6):
                stop = start + 12
                entry: dict[str, Any] = {
                    "session": s["name"],
                    "interval": n.get("block"),
                    "rows": [start, stop],
                }
                for k, p in probs.items():
                    arg = np.argmax(p[start : stop + 1], axis=1)
                    entry[k] = {
                        "active_obs": int(np.sum(arg == 1)),
                        "active_to_post_to_active": bool(
                            any(
                                arg[i] == 1 and 2 in arg[i + 1 : j] and arg[j] == 1
                                for i in range(len(arg))
                                for j in range(i + 2, len(arg))
                            )
                        ),
                    }
                nonsign.append(entry)
    out = {"pairs": pairs, "nonsign_windows": nonsign}
    Path(__file__).with_name("transition_split_probe.json").write_text(json.dumps(out, indent=2))
    for r in pairs:
        print(
            f"{r['session'][:14]:14s} {r['block'][:12]:12s} {r['pair']:12s} gap={r['gap_obs']:2d} "
            f"hands={r['hand_fraction']:.2f} speed_dip={r['speed_dip_ratio']}"
        )
        for k in packages:
            m = r[k]
            print(
                f"     {k:9s} dip={m['active_dip']:.2f} post_peak={m['post_peak']:.2f} "
                f"nonA_run={m['non_active_run']} s1A={m['sign1_active']} "
                f"s2A={m['sign2_active']} {m['trace_argmax']}"
            )
    for k in packages:
        w = [x[k] for x in nonsign]
        print(
            k,
            "nonsign windows",
            len(w),
            "with ACTIVE",
            sum(x["active_obs"] > 0 for x in w),
            "with ACTIVE->POST->ACTIVE",
            sum(x["active_to_post_to_active"] for x in w),
        )


if __name__ == "__main__":
    main()
