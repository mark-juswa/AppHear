"""Sem-Lex enrichment vs its control (WORD v2, identical recipe without Sem-Lex) on held-out DEV.

Reports top-1 at dense / 5.6 / 3.75 fps for all 816 DEV clips, for the 65 Sem-Lex-covered classes
(234 clips) and for the uncovered classes (spill-over), paired exact McNemar, and per signer.
"""

from __future__ import annotations

import json
import sys
from math import comb
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "docs/audit/probes/pipeline_v3"))

import stage_attribution as sa  # noqa: E402

from pipeline.perception_vnext.recognition_schema import load_raw_sequence  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
RU = E / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"


def mcnemar(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    n01, n10 = int(np.sum(~a & b)), int(np.sum(a & ~b))
    n = n01 + n10
    p = min(1.0, 2 * sum(comb(n, k) for k in range(min(n01, n10) + 1)) / 2**n) if n else 1.0
    return {"fixed": n01, "broken": n10, "p": p}


def main() -> None:
    manifest = json.loads((RU / "semlex_candidate_raw_01/manifest.json").read_text())
    covered = {c["gloss"] for c in manifest["clips"]}
    dev = [json.loads(line) for line in open(E / sa.DATASET_INDEX) if '"split":"dev"' in line]
    raws = [load_raw_sequence(Path(r["raw_path"])) for r in dev]
    gloss = [r["canonical_gloss"] for r in dev]
    signer = np.asarray([r["signer_id"] for r in dev])
    cov = np.asarray([g in covered for g in gloss])
    models = {
        "frozen": sa.Recognizer(E),
        "v2": sa.Recognizer(E, RU / "word_track_robust_aug_02/best.keras"),
        "semlex": sa.Recognizer(E, RU / "word_track_semlex_01/best.keras"),
    }
    out: dict = {"covered_classes": len(covered), "covered_dev_clips": int(cov.sum())}
    for label, cond, fps in (
        ("dense", "dense", 5.606840672873506),
        ("5.6fps", "phone_01_sparse", 5.606840672873506),
        ("3.75fps", "phone_01_sparse", 3.75),
    ):
        sa.PHONE_COMPLETED_FPS = fps
        c = {
            k: np.asarray(
                [
                    m.score(p, g)["correct"]
                    for p, g in zip(m.probabilities(raws, cond), gloss, strict=True)
                ]
            )
            for k, m in models.items()
        }
        out[label] = {
            "all": {k: float(v.mean()) for k, v in c.items()},
            "covered": {k: float(v[cov].mean()) for k, v in c.items()},
            "uncovered": {k: float(v[~cov].mean()) for k, v in c.items()},
            "semlex_vs_v2_all": mcnemar(c["v2"], c["semlex"]),
            "semlex_vs_v2_covered": mcnemar(c["v2"][cov], c["semlex"][cov]),
            "semlex_vs_frozen_all": mcnemar(c["frozen"], c["semlex"]),
            "per_signer": {
                s: {k: round(float(v[signer == s].mean()), 4) for k, v in c.items()}
                for s in sorted(set(signer))
            },
        }
        print(
            label,
            json.dumps(
                {
                    k: out[label][k]
                    for k in (
                        "all",
                        "covered",
                        "uncovered",
                        "semlex_vs_v2_all",
                        "semlex_vs_v2_covered",
                    )
                }
            ),
            flush=True,
        )
    Path(__file__).with_name("semlex_eval.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
