"""How much of S2-R3's FIT supervision is 'accepted hands visible, not signing'?

Counts FIT rows (Arm A dataset, s2_r3_train_01) by domain and label (PRE / ACTIVE / POST) and
whether Candidate01 accepted any hand on that row (features 172-173 = hand_observed). Writes
fit_hand_evidence.json.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics import s2_r3_train  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
OBSERVED = slice(172, 174)
NAMES = {0: "PRE", 1: "ACTIVE", 2: "POST"}


def main() -> None:
    data = s2_r3_train.build_dataset(E, suite.read_json(s2_r3_train.CONFIG_PATH))
    table: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for row in data["fit"]:
        hand = np.asarray(row["features"])[:, OBSERVED].max(axis=1) > 0.5
        labels = np.asarray(row["labels"])
        n = min(len(hand), len(labels))
        for lab, name in NAMES.items():
            m = labels[:n] == lab
            table[row["domain"]][name][0] += int(m.sum())
            table[row["domain"]][name][1] += int((m & hand[:n]).sum())
        if "kinds" in row:
            m = (np.asarray(row["kinds"])[:n] == s2_r3_train.NEGATIVE_KIND) & (labels[:n] == 0)
            table["STITCHED_NEGATIVE_BLOCKS"]["PRE"][0] += int(m.sum())
            table["STITCHED_NEGATIVE_BLOCKS"]["PRE"][1] += int((m & hand[:n]).sum())
    out = {
        d: {
            k: {"rows": v[0], "with_accepted_hand": v[1], "fraction": v[1] / max(1, v[0])}
            for k, v in labs.items()
        }
        for d, labs in table.items()
    }
    total = {
        k: [
            sum(out[d][k]["rows"] for d in out if k in out[d] and d != "STITCHED_NEGATIVE_BLOCKS"),
            sum(
                out[d][k]["with_accepted_hand"]
                for d in out
                if k in out[d] and d != "STITCHED_NEGATIVE_BLOCKS"
            ),
        ]
        for k in NAMES.values()
    }
    out["ALL_FIT"] = {
        k: {"rows": v[0], "with_accepted_hand": v[1], "fraction": v[1] / max(1, v[0])}
        for k, v in total.items()
    }
    Path(__file__).with_name("fit_hand_evidence.json").write_text(json.dumps(out, indent=1))
    for d, labs in out.items():
        print(
            f"{d:26s}",
            {
                k: f"{v['with_accepted_hand']}/{v['rows']} ({v['fraction']:.2f})"
                for k, v in labs.items()
            },
        )


if __name__ == "__main__":
    main()
