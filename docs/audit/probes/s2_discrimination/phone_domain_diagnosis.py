"""Why does a CAL-chosen S2-R3 operating point miss phone signs? (diagnosis; no training, no sweep)

Units, all with the runtime (full-history) S2 probabilities:
  phone GENUINE    peak P(ACTIVE) inside each reviewed genuine sign (Tier-2 sessions; dev-exposed)
  phone NON_SIGN   peak P(ACTIVE) per 9-observation chunk of each human-confirmed non-sign interval
  CAL SIGN         peak P(ACTIVE) inside each sign of the S2-R3 CAL streams (CAL signers)
  CAL NON_SIGN     peak P(ACTIVE) in each 9-observation chunk of CAL negative blocks (P1 P01, N0)
Separability = ROC AUC (genuine vs non-sign peaks) within a domain; shift = how the genuine peak
distribution moves between CAL and phone. Missed phone signs are related to the evidence the
features see (accepted-hand fraction, body availability, DWPose proposals).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics import s2_r3_train  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
RU = E / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
CHUNK = 9


def auc(pos: list[float], neg: list[float]) -> float:
    p, n = np.asarray(pos), np.asarray(neg)
    return (
        float(np.mean([(x > n).mean() + 0.5 * (x == n).mean() for x in p]))
        if len(p) and len(n)
        else float("nan")
    )


def chunks(first: int, last: int) -> list[tuple[int, int]]:
    return [
        (a, min(a + CHUNK - 1, last))
        for a in range(first, last + 1, CHUNK)
        if min(a + CHUNK - 1, last) - a >= 3
    ]


def main() -> None:
    packages = {
        "S2_R2": suite.load_package(
            "S2_R2",
            "v1",
            RU / "s2_r2_continuous_domain_correction_01/main_candidate/best_model.keras",
            RU / "s2_r2_continuous_domain_correction_01/main_candidate/normalization.json",
        ),
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
    config = suite.read_json(suite.SUITES["03"][0])
    tier = config["tier2_sessions"]
    sessions = {
        n: suite.load_tier2_session(E, n, s, "v1", int(tier["timestamp_match_tolerance_ns"]))
        for n, s in tier.items()
        if isinstance(s, dict) and "capture" in s
    }
    cal = s2_r3_train.build_dataset(E, suite.read_json(s2_r3_train.CONFIG_PATH))["cal_streams"]
    out: dict[str, Any] = {}
    for name, pkg in packages.items():
        phone_pos, phone_neg, detail = [], [], []
        for sname, s in sessions.items():
            p = pkg.probabilities(s["features"])[:, 1]
            raw = s["capture"].raw
            for sign in s["positives"]:
                rows = np.arange(sign["first"], sign["last"] + 1)
                phone_pos.append(float(p[rows].max()))
                detail.append(
                    {
                        "session": sname,
                        "sign": sign["name"],
                        "peak_active": float(p[rows].max()),
                        "hand_fraction": float(np.mean(np.any(raw.hand_observed[rows], axis=1))),
                        "proposal_fraction": float(
                            np.mean(np.any(raw.hand_proposal_present[rows], axis=1))
                        ),
                        "body_fraction": float(np.mean(raw.body_available[rows])),
                    }
                )
            for n in s["negatives"]:
                for a, b in chunks(n["first"], n["last"]):
                    phone_neg.append(float(p[a : b + 1].max()))
        cal_pos, cal_neg = [], []
        for stream in cal:
            p = pkg.probabilities(stream["features"])[:, 1]
            for o in sorted(set(stream["ordinals"].tolist()) - {-1}):
                rows = np.flatnonzero((stream["ordinals"] == o) & (stream["labels"] == 1))
                if len(rows):
                    cal_pos.append(float(p[rows].max()))
            neg_rows = np.flatnonzero(
                (stream["kinds"] == s2_r3_train.NEGATIVE_KIND) & (stream["labels"] == 0)
            )
            if len(neg_rows):
                splits = np.split(neg_rows, np.flatnonzero(np.diff(neg_rows) > 1) + 1)
                for block in splits:
                    for a, b in chunks(int(block[0]), int(block[-1])):
                        cal_neg.append(float(p[a : b + 1].max()))

        def q(v: list[float]) -> list[float]:
            return [round(float(x), 3) for x in np.percentile(v, [10, 25, 50, 75, 90])]

        res = {
            "phone": {
                "genuine_n": len(phone_pos),
                "nonsign_chunks_n": len(phone_neg),
                "auc": auc(phone_pos, phone_neg),
                "genuine_peak_q": q(phone_pos),
                "nonsign_peak_q": q(phone_neg),
            },
            "cal": {
                "sign_n": len(cal_pos),
                "nonsign_chunks_n": len(cal_neg),
                "auc": auc(cal_pos, cal_neg),
                "sign_peak_q": q(cal_pos),
                "nonsign_peak_q": q(cal_neg),
            },
            "phone_genuine_detected_at": {
                str(t): float(np.mean(np.asarray(phone_pos) >= t)) for t in (0.5, 0.8)
            },
            "phone_nonsign_fired_at": {
                str(t): float(np.mean(np.asarray(phone_neg) >= t)) for t in (0.5, 0.8)
            },
            "cal_sign_detected_at": {
                str(t): float(np.mean(np.asarray(cal_pos) >= t)) for t in (0.5, 0.8)
            },
            "cal_nonsign_fired_at": {
                str(t): float(np.mean(np.asarray(cal_neg) >= t)) for t in (0.5, 0.8)
            },
            "phone_signs": detail,
        }
        low = [d for d in detail if d["peak_active"] < 0.8]
        high = [d for d in detail if d["peak_active"] >= 0.8]
        res["evidence_by_peak"] = {
            k: {
                "n": len(v),
                "hand_fraction_mean": (
                    float(np.mean([d["hand_fraction"] for d in v])) if v else None
                ),
                "body_fraction_mean": (
                    float(np.mean([d["body_fraction"] for d in v])) if v else None
                ),
            }
            for k, v in (("peak<0.8", low), ("peak>=0.8", high))
        }
        out[name] = res
        print(
            name,
            json.dumps(
                {
                    k: res[k]
                    for k in (
                        "phone",
                        "cal",
                        "phone_genuine_detected_at",
                        "phone_nonsign_fired_at",
                        "cal_sign_detected_at",
                        "cal_nonsign_fired_at",
                        "evidence_by_peak",
                    )
                }
            ),
            flush=True,
        )
    Path(__file__).with_name("phone_domain_diagnosis.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
