"""Saved-evidence audit only; no TensorFlow, inference, raw/RGB loading or training."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from model.fingerspelling_metrics import alignment

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/fingerspelling_pre_v2_1_quality_audit_01"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def read(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))


def score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    expected: Counter[str] = Counter()
    correct: Counter[str] = Counter()
    substitutions: Counter[str] = Counter()
    deletions: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    for row in rows:
        expected.update(row["reference"])
        outcome = alignment(row["reference"], row["prediction"])
        for operation, reference, prediction in outcome["operations"]:
            counts[operation] += 1
            if operation == "M":
                correct[reference] += 1
            elif operation == "S":
                substitutions[f"{reference}->{prediction}"] += 1
            elif operation == "D":
                deletions[reference] += 1
    reference_count = sum(expected.values())
    predicted = sum(len(row["prediction"]) for row in rows)
    return dict(
        sequences=len(rows),
        reference_characters=reference_count,
        predicted_characters=predicted,
        correct=counts["M"],
        substitutions=counts["S"],
        deletions=counts["D"],
        insertions=counts["I"],
        cer=(counts["S"] + counts["D"] + counts["I"]) / reference_count,
        precision=counts["M"] / predicted if predicted else None,
        exact=sum(row["reference"] == row["prediction"] for row in rows),
        letter_correct=sum(correct[c] for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        letter_references=sum(expected[c] for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        space_correct=correct[" "],
        recall={
            c: dict(
                reference=expected[c],
                correct=correct[c],
                deleted=deletions[c],
                recall=correct[c] / expected[c] if expected[c] else None,
            )
            for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ "
        },
        largest_alignment_substitutions=substitutions.most_common(15),
        interpretation="Sequence edit alignment, not frame-level handshape confusion",
    )


def main() -> None:
    sources = [
        "runs/fingerspelling_sequence_v2_01/final_evaluation.json",
        "datasets/fingerspelling/train4096_plan_01/train4096_manifest.json",
        "datasets/fingerspelling/foundation_01/tranche_manifest.json",
        "datasets/fingerspelling/train4096_plan_01/dev_b/tranche_manifest.json",
        "artifacts/fingerspelling_sequence_v2_gate_01/train_missingness_evidence.json",
        "artifacts/fingerspelling_train4096_android_01/session_1791372125109.json",
    ]
    identities = {name: digest(ROOT / name) for name in sources}
    final = read(sources[0])
    assert final["test_accessed"] is False
    output: dict[str, Any] = dict(
        schema_version="apphear.fingerspelling.pre_v2_1_quality_audit.v1",
        source_sha256=identities,
        inference_run=False,
        training_run=False,
        test_accessed=False,
        phone_accuracy_measured=False,
        cohorts={},
    )
    for cohort in ("dev_a", "dev_b"):
        output["cohorts"][cohort] = {}
        for view in ("native", "phone"):
            output["cohorts"][cohort][view] = {}
            for model in ("epoch038_reference", "candidate"):
                record = final[cohort][model][view]
                rows = record["predictions"]
                result = score(rows)
                for key in ("cer", "substitutions", "deletions", "insertions"):
                    assert result[key] == record["metrics"][key], (cohort, view, model, key)
                assert len(rows) == len({r["sample_id"] for r in rows}) == 256
                result["single_word"] = score([r for r in rows if " " not in r["reference"]])
                output["cohorts"][cohort][view][model] = result
    output["pooled_phone"] = {}
    for model in ("epoch038_reference", "candidate"):
        rows = [r for c in ("dev_a", "dev_b") for r in final[c][model]["phone"]["predictions"]]
        output["pooled_phone"][model] = score(rows)
        output["pooled_phone"][model]["single_word"] = score(
            [r for r in rows if " " not in r["reference"]]
        )
    output["metadata_task_coverage"] = {}
    groups = {
        "TRAIN": read(sources[1])["samples"],
        "DEV_A": [r for r in read(sources[2])["samples"] if r["split_role"] == "DEV"],
        "DEV_B": read(sources[3])["samples"],
    }
    for role, samples in groups.items():
        texts = [r["normalized_transcript"] for r in samples]
        output["metadata_task_coverage"][role] = dict(
            sequences=len(texts),
            single_letter=sum(len(t) == 1 for t in texts),
            single_word=sum(" " not in t for t in texts),
            minimum_length=min(map(len, texts)),
            maximum_length=max(map(len, texts)),
            characters=dict(sorted(Counter("".join(texts)).items())),
        )
    output["measured_train_missingness"] = read(sources[4])
    phone = read(sources[5])
    output["phone_engineering_example"] = {
        key: phone[key]
        for key in (
            "observations",
            "any_hand_observed_frames",
            "greedyRaw",
            "beamRaw",
            "observations_per_second",
            "finish_ms",
        )
    }
    output["phone_engineering_example"]["linguistically_verified"] = False
    inventory = read("artifacts/fingerspelling_sequence_v2_1_gate_01/preservation_before.json")
    changed = [
        p
        for p, value in inventory.items()
        if not Path(p).is_file() or digest(Path(p)) != value["sha256"]
    ]
    output["protected_inventory"] = dict(files=len(inventory), changed=changed)
    assert not changed, "Protected input changed; inspect inventory before making claims"
    assert identities == {name: digest(ROOT / name) for name in sources}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audit.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PRE_V2_1_SAVED_EVIDENCE_VERIFIED",
                "report": str(OUT / "audit.json"),
                "protected_files": len(inventory),
                "protected_changes": len(changed),
                "training_or_inference_run": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
