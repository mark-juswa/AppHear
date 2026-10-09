"""Reproduce P5-B missingness strata from saved runtime masks and predictions."""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
import numpy as np

def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--predictions",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    with a.predictions.open("r",encoding="utf-8",newline="") as f: rows=list(csv.DictReader(f))
    groups={"strong_both":[],"moderate":[],"weak_both":[]}
    for r in rows:
        value=float(r["both_observed_fraction"]); key="strong_both" if value>=.9 else ("moderate" if value>=.5 else "weak_both");groups[key].append(int(r["correct"]))
    result={k:{"n":len(v),"top1":float(np.mean(v)) if v else None} for k,v in groups.items()}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps(result,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
