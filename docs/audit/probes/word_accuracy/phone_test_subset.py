"""Pick a small, difficulty-stratified phone test set and copy verified reference demonstrations.

Strata (per class, independent runtime-window recall pooled over DEV and Sem-Lex EVAL, frozen vs
candidate; deterministic ordering by evidence size, then gloss):
  ANCHOR      HELLO and HOME (continuity with every earlier phone session)
  BOTH_GOOD   frozen and candidate >= 0.6
  GAIN        candidate - frozen >= 0.25 (RELIABLE tier first: the gain is measured on >= 5 signers)
  HARD        both <= 0.25 (includes the CHAIR / SIT minimal pair when eligible)
  RISK        candidate - frozen <= -0.15 (where the candidate may lose words)
Reference videos are ASL Citizen TRAIN clips of the same gloss from the governed index (labels are
dataset ground truth; the protected TEST split is never read). They are copied to
<evidence root>/artifacts/word_phone_protocol_01/reference/ with a protocol JSON and a README.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

E = Path("F:/ASL DATASET/5. Apphear3")
REPORT = (
    E
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
    / "word_vocabulary_eval_01/report"
)
VIDEOS = Path("I:/ASL CITIZEN/ASL CITIZEN/ASL_Citizen/videos")
OUT = E / "artifacts/word_phone_protocol_01"
PER_STRATUM = 3


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, help="report name of the candidate")
    parser.add_argument("--copy", action="store_true", help="copy reference videos")
    args = parser.parse_args()
    frozen = json.loads((REPORT / "frozen.json").read_text(encoding="utf-8"))["classes"]
    cand = json.loads((REPORT / f"{args.candidate}.json").read_text(encoding="utf-8"))["classes"]
    rows = []
    for gloss, f in frozen.items():
        c = cand[gloss]
        a, b = f.get("independent_realistic_recall"), c.get("independent_realistic_recall")
        if a is None or b is None:
            continue
        rows.append(
            {
                "gloss": gloss,
                "frozen": a,
                "candidate": b,
                "delta": round(b - a, 4),
                "tier": f["tier"],
                "clips": f["independent_clips"],
                "signers": f["independent_signers"],
                "frozen_confusion": f.get("top_confusion", ""),
                "candidate_confusion": c.get("top_confusion", ""),
            }
        )
    order = sorted(rows, key=lambda r: (r["tier"] != "RELIABLE", -r["clips"], r["gloss"]))
    picked: dict[str, list[dict]] = {"ANCHOR": [r for r in rows if r["gloss"] in ("HELLO", "HOME")]}
    used = {r["gloss"] for r in picked["ANCHOR"]}

    def take(name: str, cond, first: tuple[str, ...] = ()) -> None:
        chosen = [r for r in rows if r["gloss"] in first and r["gloss"] not in used and cond(r)]
        chosen += [r for r in order if r["gloss"] not in used and r not in chosen and cond(r)]
        picked[name] = chosen[:PER_STRATUM]
        used.update(r["gloss"] for r in picked[name])

    take("BOTH_GOOD", lambda r: r["frozen"] >= 0.6 and r["candidate"] >= 0.6)
    take("GAIN", lambda r: r["delta"] >= 0.25)
    take("HARD", lambda r: r["frozen"] <= 0.25 and r["candidate"] <= 0.25, ("CHAIR", "SIT"))
    take("RISK", lambda r: r["delta"] <= -0.15)
    index = [
        json.loads(line)
        for line in (
            E / "artifacts/recognition_upgrade/perception_vnext/"
            "recognition_utility_236_01/dataset/index.jsonl"
        ).open(encoding="utf-8")
    ]
    protocol = {
        "candidate": args.candidate,
        "attempts_per_sign": 3,
        "strata": picked,
        "references": {},
    }
    for stratum in picked.values():
        for r in stratum:
            refs = sorted(
                x["sample_id"]
                for x in index
                if x["split"] == "train"
                and x["source_id"] == "ASL_CITIZEN"
                and x["canonical_gloss"] == r["gloss"]
            )
            if not refs:
                continue
            video = VIDEOS / (refs[0].split(":", 2)[2] + ".mp4")
            protocol["references"][r["gloss"]] = {
                "sample_id": refs[0],
                "video": str(video),
                "exists": video.exists(),
            }
            if args.copy and video.exists():
                (OUT / "reference").mkdir(parents=True, exist_ok=True)
                shutil.copy2(video, OUT / "reference" / f"{r['gloss']}.mp4")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "protocol.json").write_text(json.dumps(protocol, indent=1) + "\n", encoding="utf-8")
    for name, stratum in picked.items():
        print(name, [(r["gloss"], r["frozen"], r["candidate"], r["tier"]) for r in stratum])


if __name__ == "__main__":
    main()
