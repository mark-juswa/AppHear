"""Single-graph WORD blend: weighted average of recognizer probabilities (research / debug only).

The members share the Recognition V2 contract ([96,350] features + [96] mask -> 236 softmax), so
the blend keeps exactly the same inputs and output and can be exported to one TFLite file that the
existing Android WORD loader consumes unchanged. Only built-in layers (Rescaling, Add) are used, so
the blend reloads with ``safe_mode=True`` and converts to TFLite builtins.

Pre-registered candidate (2026-10-18, rule fixed on DEV calibration signers P5/P12/P21 before the
seed-202/303 enrichment runs were scored): 0.5 x frozen Gate-2 recognizer + 0.5 x the mean of the
three Sem-Lex-ENRICH runs (seeds 101/202/303). No seed is selected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

RU = Path("artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01")
CANDIDATE_01 = [
    (RU / "tcn_v2_run_01/best.keras", 0.5),
    (RU / "word_ec_semlex_01/naive_s101/best.keras", 0.5 / 3),
    (RU / "word_ec_semlex_01/naive_s202/best.keras", 0.5 / 3),
    (RU / "word_ec_semlex_01/naive_s303/best.keras", 0.5 / 3),
]


# Same pre-registered rule, members trained with human review package 02 added (2026-10-18).
CANDIDATE_02 = [
    (RU / "tcn_v2_run_01/best.keras", 0.5),
    (RU / "word_semlex2_01/naive2_s101/best.keras", 0.5 / 3),
    (RU / "word_semlex2_01/naive2_s202/best.keras", 0.5 / 3),
    (RU / "word_semlex2_01/naive2_s303/best.keras", 0.5 / 3),
]
CANDIDATES = {"01": CANDIDATE_01, "02": CANDIDATE_02}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(root: Path, members: list[tuple[Path, float]]) -> object:
    import keras

    if abs(sum(w for _, w in members) - 1.0) > 1e-9:
        raise ValueError("BLEND_WEIGHTS_MUST_SUM_TO_ONE")
    features = keras.Input((96, 350), dtype="float32", name="features")
    mask = keras.Input((96,), dtype="bool", name="mask")
    parts = []
    for k, (path, weight) in enumerate(members):
        member = keras.models.load_model(root / path, compile=False, safe_mode=True)
        member.name = f"member_{k}"
        parts.append(keras.layers.Rescaling(weight, name=f"weight_{k}")(member([features, mask])))
    output = keras.layers.Add(name="blend")(parts)
    return keras.Model([features, mask], output, name="word_blend")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="directory (created)")
    parser.add_argument("--candidate", choices=sorted(CANDIDATES), default="01")
    args = parser.parse_args()
    root = args.evidence_root
    members = CANDIDATES[args.candidate]
    model = build(root, members)
    args.output.mkdir(parents=True, exist_ok=False)
    target = args.output / "blend.keras"
    model.save(target)
    identity = {
        "schema": "apphear.word_blend.v1",
        "members": [
            {"path": str(p).replace("\\", "/"), "sha256": sha256(root / p), "weight": w}
            for p, w in members
        ],
        "parameter_count": int(model.count_params()),
        "blend_sha256": sha256(target),
        "selection": "weights fixed on DEV calibration signers P5/P12/P21; no seed selected",
        "protected_test_accessed": False,
    }
    (args.output / "blend_identity.json").write_text(
        json.dumps(identity, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(identity, indent=2))


if __name__ == "__main__":
    main()
