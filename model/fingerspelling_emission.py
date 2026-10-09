"""Measured CTC emission diagnostics and bounded global blank calibration; no language model."""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from model.fingerspelling_fast_execution import CompiledSteps, FeatureCache
from model.fingerspelling_metrics import greedy_decode, summarize


def collect_logits(
    tf: Any,
    steps: CompiledSteps,
    cache: FeatureCache,
    rows: list[dict[str, Any]],
    view: str,
    batch_size: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        x, mask, y, lengths, target_lengths = cache.batch(batch, view)
        logits = steps.infer(x, mask).numpy()
        eligible = [i for i, r in enumerate(batch) if lengths[i] >= r["ctc_min_timesteps"]]
        losses: dict[int, float] = {}
        if eligible:
            values = tf.nn.ctc_loss(
                labels=y[eligible],
                logits=logits[eligible],
                label_length=target_lengths[eligible],
                logit_length=lengths[eligible],
                logits_time_major=False,
                blank_index=27,
            ).numpy()
            if not np.isfinite(values).all():
                raise ValueError("[fingerspelling/emission] Non-finite CTC loss")
            losses = dict(zip(eligible, map(float, values), strict=True))
        for i, rec in enumerate(batch):
            actual = np.array(logits[i, : lengths[i]], copy=True)
            if not np.isfinite(actual).all():
                raise ValueError("[fingerspelling/emission] Non-finite logits")
            results.append(
                {
                    "sample_id": rec["sample_id"],
                    "signer_id": rec["official_signer_id"],
                    "reference": rec["normalized_transcript"],
                    "logits": actual,
                    "headroom": int(lengths[i] - rec["ctc_min_timesteps"]),
                    "ctc_loss": losses.get(i),
                    "input_length": int(lengths[i]),
                }
            )
    return results


def score_logits(rows: list[dict[str, Any]], penalty: float, bounds: list[int]) -> dict[str, Any]:
    if not np.isfinite(penalty) or penalty < 0:
        raise ValueError("[fingerspelling/decoder] Invalid blank penalty")
    predictions: list[dict[str, Any]] = []
    blanks, total, posterior_sum = 0, 0, 0.0
    for row in rows:
        logits = np.array(row["logits"], copy=True)
        logits[:, 27] -= np.float32(penalty)
        tokens = np.argmax(logits, axis=1)
        blanks += int(np.sum(tokens == 27))
        total += len(tokens)
        exp = np.exp(logits - logits.max(axis=1, keepdims=True))
        posterior_sum += float((exp[:, 27] / exp.sum(axis=1)).sum())
        predictions.append(
            {
                "sample_id": row["sample_id"],
                "signer_id": row["signer_id"],
                "reference": row["reference"],
                "prediction": greedy_decode(tokens.tolist()),
            }
        )
    metrics = summarize(predictions, 10)
    reference_count = metrics["reference_characters"]
    predicted = sum(len(r["prediction"]) for r in predictions)
    metrics.update(
        {
            "exact_sequence_count": sum(r["prediction"] == r["reference"] for r in predictions),
            "deletion_rate": metrics["deletions"] / reference_count if reference_count else None,
            "insertion_rate": metrics["insertions"] / reference_count if reference_count else None,
            "predicted_characters": predicted,
            "predicted_reference_ratio": predicted / reference_count if reference_count else None,
            "empty_prediction_count": sum(not r["prediction"] for r in predictions),
            "empty_prediction_rate": (
                sum(not r["prediction"] for r in predictions) / len(rows) if rows else None
            ),
        }
    )
    strata = {}
    for name, predicate in [
        ("short", lambda n: n <= bounds[0]),
        ("medium", lambda n: bounds[0] < n <= bounds[1]),
        ("long", lambda n: n > bounds[1]),
    ]:
        group = [r for r in predictions if predicate(len(r["reference"]))]
        value = summarize(group, 10)
        strata[name] = {k: v for k, v in value.items() if k not in {"signers", "subgroups"}}
    losses = [r["ctc_loss"] for r in rows if r["ctc_loss"] is not None]
    headroom = [r["headroom"] for r in rows]
    return {
        "metrics": metrics,
        "predictions": predictions,
        "blank_penalty": penalty,
        "emission": {
            "blank_argmax_fraction": blanks / total if total else None,
            "nonblank_argmax_fraction": 1 - blanks / total if total else None,
            "mean_blank_posterior": posterior_sum / total if total else None,
            "timesteps": total,
            "blank_timesteps": blanks,
            "average_decoded_length": predicted / len(rows) if rows else None,
        },
        "headroom": {
            "minimum": min(headroom) if headroom else None,
            "median": float(np.median(headroom)) if headroom else None,
            "feasible": len(losses),
            "infeasible": len(rows) - len(losses),
            "infeasible_retained_ids": [r["sample_id"] for r in rows if r["headroom"] < 0],
        },
        "ctc_mean_loss_uncalibrated_eligible_only": float(np.mean(losses)) if losses else None,
        "length_strata": strata,
        "all_sequences": len(rows),
    }


def balanced_score(views: dict[str, Any]) -> float:
    values = [views[v]["metrics"]["cer"] for v in ["native", "phone"]]
    if any(v is None or not np.isfinite(v) for v in values):
        raise ValueError("[fingerspelling/selection] Finite native and phone CER required")
    return float(np.mean(values))


def evaluate_views(
    tf: Any,
    steps: CompiledSteps,
    cache: FeatureCache,
    rows: list[dict[str, Any]],
    config: dict[str, Any],
    batch_size: int,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, float]]:
    views, logits, times = {}, {}, {}
    for view in ["native", "phone"]:
        start = time.perf_counter()
        logits[view] = collect_logits(tf, steps, cache, rows, view, batch_size)
        views[view] = score_logits(logits[view], 0, config["length_strata_bounds"])
        times[view] = time.perf_counter() - start
    return views, logits, times


def calibrate(
    logits: dict[str, list[dict[str, Any]]], config: dict[str, Any], enabled: bool
) -> dict[str, Any]:
    penalties = config["blank_penalties"] if enabled else [0.0]
    candidates: list[dict[str, Any]] = [
        {
            "penalty": p,
            "views": {
                v: score_logits(logits[v], p, config["length_strata_bounds"])
                for v in ["native", "phone"]
            },
        }
        for p in penalties
    ]
    base = candidates[0]
    base_score = balanced_score(base["views"])
    base_del = float(
        np.mean([base["views"][v]["metrics"]["deletion_rate"] for v in ["native", "phone"]])
    )
    base_ins = float(
        np.mean([base["views"][v]["metrics"]["insertion_rate"] for v in ["native", "phone"]])
    )
    for c in candidates:
        c["combined_cer"] = balanced_score(c["views"])
        c["eligible_nonzero"] = bool(
            c["penalty"] > 0
            and c["combined_cer"]
            <= base_score - config["calibration_minimum_combined_cer_improvement"]
            and float(
                np.mean([c["views"][v]["metrics"]["deletion_rate"] for v in ["native", "phone"]])
            )
            < base_del
            and c["views"]["native"]["metrics"]["cer"]
            <= base["views"]["native"]["metrics"]["cer"]
            + config["calibration_max_native_cer_increase"]
            and float(
                np.mean([c["views"][v]["metrics"]["insertion_rate"] for v in ["native", "phone"]])
            )
            <= base_ins + config["calibration_max_mean_insertion_rate_increase"]
        )
    acceptable = [base, *[c for c in candidates[1:] if c["eligible_nonzero"]]]
    selected = min(acceptable, key=lambda c: (c["combined_cer"], c["penalty"]))
    return {
        "enabled_by_diagnosis": enabled,
        "selected_penalty": selected["penalty"],
        "selected_combined_cer": selected["combined_cer"],
        "uncalibrated_combined_cer": base_score,
        "candidates": candidates,
        "selection_scope": "DEV_ONLY_FIXED_RANGE_NO_TRAINING_OR_LANGUAGE_MODEL",
    }
