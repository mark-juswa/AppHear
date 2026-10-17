"""Decoder-free S2 discrimination: does Arm I separate signs from movement better, or just shift?

Units: peak P(ACTIVE) inside each genuine sign vs inside each 9-observation non-sign chunk.
  PHONE     reviewed genuine signs vs confirmed non-sign chunks (Tier-2 + shadow 023004Z)
  HELD_OUT  held-out ASL signers' signs (CONTINUOUS stitched DEV) vs hand-visible NOG chunks of the
            two held-out IPN subjects (suite v04 tier 1c inputs); both unseen by every model
  CAL       CAL signs vs CAL P1 (hands-visible person P01) chunks
Reports AUC and the operating points (sign recall, non-sign fire) at P(ACTIVE) >= 0.5 and 0.9.
Same AUC with lower fire and lower recall = an operating-point shift; higher AUC = discrimination.
Writes unit_separability.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics import event_reliability as er  # noqa: E402
from eval.runtime_diagnostics import heldout_dev_e2e as bench  # noqa: E402
from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics import s2_r3_train  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
HERE = Path(__file__).parent
MODELS = ("S2_R2", "ARM_A_E10", "ARM_A_E21", "ARM_B_E9", "ARM_I_E28")
CHUNK = 9


def auc(pos: list[float], neg: list[float]) -> float:
    p, n = np.asarray(pos), np.asarray(neg)
    return float((p[:, None] > n[None, :]).mean() + 0.5 * (p[:, None] == n[None, :]).mean())


def chunks(rows: np.ndarray) -> list[np.ndarray]:
    if not len(rows):
        return []
    blocks = np.split(rows, np.flatnonzero(np.diff(rows) > 1) + 1)
    return [
        b[a : a + CHUNK]
        for b in blocks
        for a in range(0, len(b), CHUNK)
        if len(b[a : a + CHUNK]) >= 4
    ]


def main() -> None:
    sessions = {
        k: v for k, v in er.phone_sessions(E).items() if v["kind"] != "SHADOW_PROTOCOL_ONLY"
    }
    dev = [s for s in bench.build_streams(E, 266.616) if s["mode"] == "CONTINUOUS"]
    dev_feats = [suite.features_for_raw(s["raw"], "v1") for s in dev]
    config = suite.read_json(suite.SUITES["04"][0])
    ipn = suite.load_ipn_streams(E, config, "v1")
    cal = s2_r3_train.build_dataset(E, suite.read_json(s2_r3_train.CONFIG_PATH))["cal_streams"]
    out = {}
    for m in MODELS:
        pkg = er.load_s2(E, m)
        units = {k: ([], []) for k in ("PHONE", "HELD_OUT", "CAL")}
        for s in sessions.values():
            a = np.clip(pkg.probabilities(s["features"])[:, 1], 0, 1)
            units["PHONE"][0].extend(
                float(a[x["first"] : x["last"] + 1].max()) for x in s["positives"]
            )
            for n in s["negatives"]:
                units["PHONE"][1].extend(
                    float(a[c].max()) for c in chunks(np.arange(n["first"], n["last"] + 1))
                )
        for s, f in zip(dev, dev_feats, strict=True):
            a = np.clip(pkg.probabilities(f)[:, 1], 0, 1)
            units["HELD_OUT"][0].extend(
                float(a[x["first"] : x["last"] + 1].max()) for x in s["signs"]
            )
        for s in ipn.values():
            a = np.clip(pkg.probabilities(s["features"])[:, 1], 0, 1)
            hands = np.asarray(s["raw"].hand_observed, bool).any(axis=1)
            units["HELD_OUT"][1].extend(
                float(a[c].max())
                for c in chunks(np.flatnonzero(s["classes"] == 0))
                if hands[c].any()
            )
        for s in cal:
            a = np.clip(pkg.probabilities(s["features"])[:, 1], 0, 1)
            for o in sorted(set(s["ordinals"].tolist()) - {-1}):
                rows = np.flatnonzero((s["ordinals"] == o) & (s["labels"] == 1))
                if len(rows):
                    units["CAL"][0].append(float(a[rows].max()))
            neg = np.flatnonzero(
                (s["kinds"] == s2_r3_train.NEGATIVE_KIND)
                & (s["labels"] == 0)
                & (s["negative_family"] == "P1")
            )
            units["CAL"][1].extend(float(a[c].max()) for c in chunks(neg))
        out[m] = {
            k: {
                "auc": auc(p, n),
                "n_sign": len(p),
                "n_nonsign": len(n),
                "sign_recall_0.5": float(np.mean(np.asarray(p) >= 0.5)),
                "nonsign_fire_0.5": float(np.mean(np.asarray(n) >= 0.5)),
                "sign_recall_0.9": float(np.mean(np.asarray(p) >= 0.9)),
                "nonsign_fire_0.9": float(np.mean(np.asarray(n) >= 0.9)),
            }
            for k, (p, n) in units.items()
        }
        print(
            m,
            {
                k: (
                    round(v["auc"], 3),
                    round(v["sign_recall_0.5"], 2),
                    round(v["nonsign_fire_0.5"], 2),
                )
                for k, v in out[m].items()
            },
            flush=True,
        )
    (HERE / "unit_separability.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
