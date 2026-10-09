"""Read-only experiment comparison and preservation verification; no model inference."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from model import fingerspelling_capacity as capacity
from model.fingerspelling_capacity_gate import correct_fraction
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO


def verify_preservation() -> dict[str, Any]:
    before = json.loads((capacity.EVIDENCE / "preservation_before.json").read_text())
    changes = [p for p, h in before.items() if not (REPO / p).is_file() or sha256(REPO / p) != h]
    result = {"checked_files": len(before), "changed_or_missing": changes, "pass": not changes}
    write_json_atomic(capacity.EVIDENCE / "preservation_after.json", result)
    if changes:
        raise ValueError("[baseline4/preservation] Pre-existing protected/research files changed")
    return result


def summary() -> dict[str, Any]:
    cfg, _, _ = capacity.policy()
    gate = json.loads((capacity.EVIDENCE / "fit_gate.json").read_text())
    results = {}
    for arm in ["control", "candidate"]:
        run = capacity.GATE_RUN / arm
        epochs = [json.loads(p.read_text()) for p in sorted((run / "epochs").glob("*.json"))]
        evaluations = {}
        for e in range(0, cfg["fit_epochs"] + 1, cfg["fit_evaluate_every"]):
            d = json.loads((run / f"evaluations/epoch_{e:03d}.json").read_text())
            evaluations[str(e)] = {
                v: {
                    **{
                        k: d["train"][v]["metrics"][k]
                        for k in [
                            "cer",
                            "substitutions",
                            "deletions",
                            "insertions",
                            "exact_sequence_count",
                            "predicted_reference_ratio",
                            "empty_prediction_count",
                        ]
                    },
                    "correct_character_fraction": correct_fraction(d["train"][v]),
                    "characters": d["train"][v]["characters"],
                    "ctc_mean_loss": d["train"][v]["ctc_mean_loss_uncalibrated_eligible_only"],
                }
                for v in ["native", "phone"]
            }
        results[arm] = {
            "parameters": cfg[f"{arm}_parameters"],
            "first_and_last_training_loss": [epochs[0]["train_ctc"], epochs[-1]["train_ctc"]],
            "update_seconds_including_checkpoint_and_scheduled_eval": sum(
                e["epoch_seconds"] for e in epochs
            ),
            "requested_view_counts": dict(
                sum((Counter(e["requested_counts"]) for e in epochs), Counter())
            ),
            "fallback_count": sum(e["fallback_count"] for e in epochs),
            "all_sources_retained_each_epoch": all(e["all_sources_retained"] for e in epochs),
            "evaluations": evaluations,
        }
    recall = {}
    for v in ["native", "phone"]:
        control, candidate = (
            results[a]["evaluations"]["60"][v]["characters"]["per_character"]
            for a in ["control", "candidate"]
        )
        changes = {
            k: candidate[k]["recall"] - control[k]["recall"]
            for k in control
            if control[k]["recall"] is not None
        }
        recall[v] = {
            "improved": sum(x > 0 for x in changes.values()),
            "worse": sum(x < 0 for x in changes.values()),
            "unchanged": sum(x == 0 for x in changes.values()),
            "delta": changes,
        }
    result = {
        "schema_version": "apphear.fingerspelling.baseline4_fit_summary.v1",
        "gate": gate,
        "arms": results,
        "character_recall_change": recall,
        "preservation": verify_preservation(),
        "test_accessed": False,
        "full_training_started": False,
    }
    write_json_atomic(capacity.EVIDENCE / "fit_summary.json", result)
    return result


if __name__ == "__main__":
    result = summary()
    print(
        json.dumps(
            {
                "status": result["gate"]["status"],
                "preservation": result["preservation"],
                "summary": str(capacity.EVIDENCE / "fit_summary.json"),
            },
            indent=2,
        )
    )
