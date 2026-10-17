"""Event ledgers with admission evidence on CAL streams and held-out DEV streams.

CAL: the 240 seeded S2-R3 CAL streams (s2_r3_train.build_dataset; CAL signers + CAL P1/N0
negatives). Sign intervals = each ordinal's ACTIVE rows; negative rows = negative blocks.
DEV: the signer-disjoint held-out DEV stitched streams (heldout_dev_e2e.build_streams, 266.616 ms),
NATURAL and CONTINUOUS. Sign intervals = governed spans; negative rows = everything outside spans
(rest, lead-in/out). Calibration signers P5/P12/P21, validation P26/P39 (as output_policy).
Writes stream_ledger_<S2>__<DECODER>.json.
"""

from __future__ import annotations

import argparse
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


def categories(rows: list[dict]) -> dict[str, int]:
    return {
        c: sum(r["category"] == c for r in rows)
        for c in ("GENUINE", "DUPLICATE", "NONSIGN", "OTHER")
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configs", nargs="+", required=True, help="S2:DECODER pairs")
    args = parser.parse_args()
    cal = s2_r3_train.build_dataset(E, suite.read_json(s2_r3_train.CONFIG_PATH))["cal_streams"]
    dev = bench.build_streams(E, 266.616)
    frozen = er.Word(E, er.FROZEN_WORD, er.FROZEN_WORD_SHA)
    shadow = er.Word(E, er.V2_WORD)
    for config in args.configs:
        s2_name, variant = config.split(":")
        s2 = er.load_s2(E, s2_name)
        out: dict = {
            "s2": s2.identity,
            "s2_name": s2_name,
            "decoder": variant,
            "cal": [],
            "dev": [],
        }
        for k, stream in enumerate(cal):
            labels, ordinals = stream["labels"], stream["ordinals"]
            signs = []
            for o in sorted(set(ordinals.tolist()) - {-1}):
                rows = np.flatnonzero((ordinals == o) & (labels == 1))
                if len(rows):
                    signs.append({"first": int(rows[0]), "last": int(rows[-1])})
            neg = stream["kinds"] == s2_r3_train.NEGATIVE_KIND
            probs = s2.probabilities(stream["features"])
            for r in er.stream_ledger(stream["raw"], probs, variant, signs, neg, frozen, shadow):
                s, f = r["logical"]
                fam = stream["negative_family"][s : f + 1]
                r.update({"stream": k, "family": str(fam[0]) if r["category"] == "NONSIGN" else ""})
                out["cal"].append(r)
        for k, stream in enumerate(dev):
            raw = stream["raw"]
            neg = np.ones(len(raw.timestamp_ms), bool)
            for sign in stream["signs"]:
                neg[sign["first"] : sign["last"] + 1] = False
            probs = s2.probabilities(suite.features_for_raw(raw, "v1"))
            for r in er.stream_ledger(raw, probs, variant, stream["signs"], neg, frozen, shadow):
                r.update({"stream": k, "signer": stream["signer"], "mode": stream["mode"]})
                out["dev"].append(r)
            if k == 0:
                out["dev_signs"] = {}
            key = f"{stream['mode']}:{stream['signer']}"
            out["dev_signs"][key] = out["dev_signs"].get(key, 0) + len(stream["signs"])
        out["cal_signs"] = int(sum(len(set(s["ordinals"][s["labels"] == 1].tolist())) for s in cal))
        (HERE / f"stream_ledger_{s2_name}__{variant}.json").write_text(
            json.dumps(out, default=float), encoding="utf-8"
        )
        print(config, "CAL", categories(out["cal"]), "DEV", categories(out["dev"]), flush=True)


if __name__ == "__main__":
    main()
