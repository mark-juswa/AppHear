"""Read-only development decomposition of the frozen one-run S2-R2 checkpoint."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics import s2_r2_continuous_domain_correction as r2  # noqa: E402
from eval.runtime_diagnostics.phase5_1t_first_segmenter import state_metrics  # noqa: E402
from eval.runtime_diagnostics.phase8a_causal_streaming_decoder import (  # noqa: E402
    aggregate_event_metrics,
    event_metrics_for_row,
    run_decoder,
)
from pipeline.perception_vnext.segmentation.learned_features import (  # noqa: E402
    apply_normalization,
)


def _predictions(
    model: Any, rows: list[dict[str, Any]], mean: np.ndarray, std: np.ndarray
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    result = {}
    for row in rows:
        inputs = apply_normalization(row["features"], mean, std)
        logits = np.asarray(model(inputs[None], training=False))[0]
        probabilities = r2.softmax(logits)
        states = np.argmax(probabilities, axis=1).astype(np.int32)
        result[row["row_id"]] = (probabilities, states)
    return result


def _summarize(
    rows: list[dict[str, Any]], predictions: dict[str, tuple[np.ndarray, np.ndarray]]
) -> dict[str, Any]:
    config = r2._decoder_config(r2.load_main_config())
    groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    per_row = []
    for row in rows:
        probabilities, states = predictions[row["row_id"]]
        state = state_metrics([row["labels"]], [states])
        item = {
            "row_id": row["row_id"],
            "domain": row["domain"],
            "source": row.get("source"),
            "signer_id": row.get("signer_id"),
            "view_id": row.get("view_id"),
            "state": state,
        }
        if row["domain"] in {"BASELINE_SIGN", "PHONE_POSITIVE"}:
            decoder = run_decoder(row["timestamps_ms"], probabilities, states, config)
            item["event"] = event_metrics_for_row(row, decoder)
        elif row["domain"] == "P1_NEGATIVE":
            decoder = run_decoder(row["timestamps_ms"], probabilities, states, config)
            item["event_count"] = len(decoder.events)
        per_row.append(item)
        groups[f"domain:{row['domain']}"].append(item)
        if row["domain"] == "BASELINE_SIGN":
            groups[f"cal_source:{row['source']}"].append(item)
            groups[f"cal_cadence:{row['view_id']}"].append(item)
            groups[f"cal_signer:{row['signer_id']}"].append(item)
        elif row["domain"] == "P1_NEGATIVE":
            groups[f"p1_participant:{row['signer_id']}"].append(item)
    summaries = {}
    for key, items in sorted(groups.items()):
        domain = items[0]["domain"]
        relevant = [row for row in rows if row["row_id"] in {x["row_id"] for x in items}]
        state = state_metrics(
            [row["labels"] for row in relevant],
            [predictions[row["row_id"]][1] for row in relevant],
        )
        summary: dict[str, Any] = {"row_count": len(items), "state": state}
        if domain in {"BASELINE_SIGN", "PHONE_POSITIVE"}:
            summary["events"] = aggregate_event_metrics([item["event"] for item in items])
        elif domain == "P1_NEGATIVE":
            summary["event_count"] = sum(item["event_count"] for item in items)
            summary["event_rate"] = sum(item["event_count"] for item in items) / len(items)
        summaries[key] = summary
    return {"groups": summaries, "per_row": per_row}


def main() -> None:
    import tensorflow as tf

    output = r2.OUT / "main_candidate"
    training = r2.read_json(output / "training_result.json")
    if training["status"] != "S2_R2_CANDIDATE_SUPPORTED" or training["best_epoch"] != 7:
        raise RuntimeError("S2_R2_FROZEN_SELECTION_MISMATCH")
    model_path = output / "best_model.keras"
    normalization_path = output / "normalization.json"
    if r2.sha256_file(model_path) != training["model_sha256"]:
        raise RuntimeError("S2_R2_MODEL_HASH_MISMATCH")
    if r2.sha256_file(normalization_path) != training["normalization_sha256"]:
        raise RuntimeError("S2_R2_NORMALIZATION_HASH_MISMATCH")
    rows = [
        row for row in r2._load_main_rows(False) if row["role"] == "INTERNAL_DEVELOPMENT"
    ]
    normalization = r2.read_json(normalization_path)
    candidate_model = tf.keras.models.load_model(model_path, compile=False)
    baseline_model = tf.keras.models.load_model(r2.PHASE7_MODEL, compile=False)
    candidate = _summarize(
        rows,
        _predictions(
            candidate_model,
            rows,
            np.asarray(normalization["mean"], np.float32),
            np.asarray(normalization["std"], np.float32),
        ),
    )
    baseline_normalization = r2.read_json(r2.PHASE7_NORM)
    baseline = _summarize(
        rows,
        _predictions(
            baseline_model,
            rows,
            np.asarray(baseline_normalization["mean"], np.float32),
            np.asarray(baseline_normalization["std"], np.float32),
        ),
    )
    result = {
        "schema": "apphear.s2_r2.postrun_decomposition.v1",
        "milestone": r2.MILESTONE,
        "purpose": "READ_ONLY_OPENED_INTERNAL_DEVELOPMENT_NOT_INDEPENDENT_VALIDATION",
        "model_sha256": training["model_sha256"],
        "normalization_sha256": training["normalization_sha256"],
        "training_result_sha256": r2.sha256_file(output / "training_result.json"),
        "development_rows": len(rows),
        "candidate": candidate,
        "baseline": baseline,
        "protected_test_accessed": False,
        "untouched_validation_consumed": False,
    }
    r2.freeze_json(output / "postrun_decomposition.json", result)
    print("S2_R2_POSTRUN_DECOMPOSITION_COMPLETE")


if __name__ == "__main__":
    main()
