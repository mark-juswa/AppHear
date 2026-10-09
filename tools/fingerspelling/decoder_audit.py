"""Inference-only frozen residual DEV decoder audit. Never trains or writes old runs."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, cast

import numpy as np

from model import fingerspelling_baseline2 as b2
from model import fingerspelling_ctc as reference
from model.fingerspelling_emission import collect_logits
from model.fingerspelling_metrics import alignment, summarize
from model.fingerspelling_prefix_beam import decode_beam, decode_greedy
from model.fingerspelling_residual_execution import ResidualCache, ResidualSteps
from model.fingerspelling_residual_visual import RUN, run_identity
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO

CONFIG = REPO / "model/config/fingerspelling_decoder_audit_01.json"
OUT = REPO / "artifacts/fingerspelling_decoder_audit_01"


def distances(reference_text: str, prediction: str) -> dict[str, int]:
    a = alignment(reference_text, prediction)
    return {k: a[k] for k in ["substitutions", "deletions", "insertions"]}


def error_count(reference_text: str, prediction: str) -> int:
    return sum(distances(reference_text, prediction).values())


def group_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    greedy, beam = [], []
    for r in rows:
        common = {k: r[k] for k in ["sample_id", "signer_id", "reference"]}
        greedy.append({**common, "prediction": r["greedy"]})
        beam.append({**common, "prediction": r["candidates"][0]["prediction"]})
    scores = {}
    for name, predictions in [("greedy", greedy), ("beam_top1", beam)]:
        metrics = summarize(predictions, 10)
        scores[name] = {k: v for k, v in metrics.items() if k not in {"signers", "subgroups"}}
        scores[name]["exact_sequence_count"] = sum(
            r["prediction"] == r["reference"] for r in predictions
        )
        correct = metrics["reference_characters"] - metrics["substitutions"] - metrics["deletions"]
        predicted = sum(len(r["prediction"]) for r in predictions)
        scores[name]["correctly_aligned_characters"] = correct
        scores[name]["predicted_characters"] = predicted
        scores[name]["correct_predicted_precision"] = correct / predicted if predicted else None
    chars = sum(len(r["reference"]) for r in rows)
    scores["topn"] = {}
    for n in [3, 5]:
        errors = [
            min(error_count(r["reference"], c["prediction"]) for c in r["candidates"][:n])
            for r in rows
        ]
        exact = sum(
            any(c["prediction"] == r["reference"] for c in r["candidates"][:n]) for r in rows
        )
        near = sum(e <= 1 for e in errors)
        scores["topn"][str(n)] = {
            "exact_reference_inclusion_count": exact,
            "exact_reference_inclusion_rate": exact / len(rows) if rows else None,
            "oracle_best_cer": sum(errors) / chars if chars else None,
            "oracle_within_one_edit_count": near,
            "interpretation": "REFERENCE_SELECTED_ORACLE_NOT_AUTOMATIC_ACCURACY",
        }
    changed = [r for r in rows if r["greedy"] != r["candidates"][0]["prediction"]]
    effects: Counter[str] = Counter()
    for r in changed:
        difference = error_count(r["reference"], r["candidates"][0]["prediction"]) - error_count(
            r["reference"], r["greedy"]
        )
        effects["improved" if difference < 0 else "regressed" if difference > 0 else "neutral"] += 1
    scores["top1_changes"] = {
        "different_from_greedy": len(changed),
        **{k: effects[k] for k in ["improved", "regressed", "neutral"]},
    }
    return scores


def save_logits(path: Path, rows: list[dict[str, Any]], identity: dict[str, Any]) -> None:
    metadata = [{k: v for k, v in r.items() if k != "logits"} for r in rows]
    lengths = np.array([len(r["logits"]) for r in rows], np.int64)
    with path.open("wb") as f:
        np.savez_compressed(
            f,
            logits=np.concatenate([r["logits"] for r in rows]).astype(np.float32),
            offsets=np.concatenate([[0], np.cumsum(lengths)]),
            metadata_json=np.array(
                json.dumps(
                    {
                        "schema_version": "apphear.fingerspelling.audit_logits.v1",
                        "identity": identity,
                        "rows": metadata,
                    }
                )
            ),
        )
    write_json_atomic(
        path.with_suffix(".receipt.json"), {"sha256": sha256(path), "identity": identity}
    )


def load_logits(path: Path, identity: dict[str, Any]) -> list[dict[str, Any]]:
    receipt = json.loads(path.with_suffix(".receipt.json").read_text())
    if receipt != {"sha256": sha256(path), "identity": identity}:
        raise ValueError("[decoder/audit] Cached logits identity/hash mismatch")
    with np.load(path, allow_pickle=False) as data:
        metadata = json.loads(str(data["metadata_json"].item()))
        logits, offsets = data["logits"], data["offsets"]
        if (
            metadata["schema_version"] != "apphear.fingerspelling.audit_logits.v1"
            or metadata["identity"] != identity
        ):
            raise ValueError("[decoder/audit] Cached logits schema/identity mismatch")
        if (
            logits.shape[1:] != (28,)
            or not np.isfinite(logits).all()
            or len(offsets) != len(metadata["rows"]) + 1
            or offsets[0] != 0
            or offsets[-1] != len(logits)
            or np.any(np.diff(offsets) <= 0)
        ):
            raise ValueError("[decoder/audit] Invalid cached logits layout")
        rows = [
            {**row, "logits": np.array(logits[offsets[i] : offsets[i + 1]], copy=True)}
            for i, row in enumerate(metadata["rows"])
        ]
        if any(len(r["logits"]) != r["input_length"] for r in rows):
            raise ValueError("[decoder/audit] Cached logit lengths mismatch")
        return rows


def duration_report(values: list[float]) -> dict[str, float]:
    return {
        "total_seconds": sum(values),
        "p50_ms": float(np.percentile(values, 50) * 1000),
        "p95_ms": float(np.percentile(values, 95) * 1000),
        "maximum_ms": max(values) * 1000,
    }


def run() -> dict[str, Any]:
    cfg = json.loads(CONFIG.read_text())
    if cfg["schema_version"] != "apphear.fingerspelling.decoder_audit.v1" or (
        cfg["beam_width"],
        cfg["top_paths"],
        cfg["blank_index"],
        cfg["blank_penalty"],
        cfg["views"],
    ) != (10, 5, 27, 0.5, ["native", "phone"]):
        raise ValueError("[decoder/audit] Frozen decoder configuration changed")
    rows = b2.dataset(REPO / cfg["dataset"])
    original_identity = json.loads((RUN / "run_identity.json").read_text())
    if original_identity != run_identity(rows, False):
        raise ValueError("[decoder/audit] Residual input/code/run identity mismatch")
    checkpoint = REPO / cfg["model_checkpoint"]
    if sha256(checkpoint) != cfg["model_sha256"]:
        raise ValueError("[decoder/audit] Frozen residual checkpoint mismatch")
    history_path = REPO / cfg["historical_evaluation"]
    historical = json.loads(history_path.read_text())
    if (
        historical["residual_checkpoint_sha256"] != cfg["model_sha256"]
        or historical["decoder_blank_penalty"] != cfg["blank_penalty"]
    ):
        raise ValueError("[decoder/audit] Historical checkpoint/decoder mismatch")
    dev = [r for r in rows if r["split_role"] == "DEV"]
    if len(dev) != 256 or len({r["sample_id"] for r in dev}) != 256:
        raise ValueError("[decoder/audit] Exactly 256 unique governed DEV rows required")
    identity = {
        "residual_sha256": cfg["model_sha256"],
        "run_identity_sha256": sha256(RUN / "run_identity.json"),
        "data_lineage": original_identity["data_lineage"],
        "adapter": original_identity["visual"]["adapter"],
        "temporal_policy": original_identity["temporal_policy"],
        "official_dev_ids": [r["sample_id"] for r in dev],
        "test_accessed": False,
    }
    OUT.mkdir(exist_ok=True)
    write_json_atomic(
        OUT / "audit_identity.json",
        {
            "input": identity,
            "config": cfg,
            "config_sha256": sha256(CONFIG),
            "decoder_sha256": sha256(REPO / "model/fingerspelling_prefix_beam.py"),
            "runner_sha256": sha256(Path(__file__)),
            "historical_evaluation_sha256": sha256(history_path),
        },
    )
    tf = steps = cache = None
    results = {}
    for view in cfg["views"]:
        start = time.perf_counter()
        path = OUT / f"{view}_logits.npz"
        cache_identity = {**identity, "view": view}
        reused = path.exists() and path.with_suffix(".receipt.json").exists()
        if reused:
            logit_rows = load_logits(path, cache_identity)
        else:
            if tf is None:
                tf = reference.tensorflow(b2.policy()[1])
                model = tf.keras.models.load_model(checkpoint, compile=False)
                steps, cache = ResidualSteps(tf, model), ResidualCache()
            print(
                json.dumps({"stage": "FROZEN_INFERENCE_ONLY", "view": view, "sequences": len(dev)}),
                flush=True,
            )
            # Existing inference collector types name the original concrete cache;
            # ResidualSteps/Cache expose the same infer()/batch() interface.
            assert steps is not None and cache is not None
            logit_rows = collect_logits(
                tf, cast(Any, steps), cast(Any, cache), dev, view, b2.policy()[1]["batch_size"]
            )
            save_logits(path, logit_rows, cache_identity)
        if [r["sample_id"] for r in logit_rows] != identity["official_dev_ids"]:
            raise ValueError("[decoder/audit] Logit row selection/order changed")
        retrieval_seconds = time.perf_counter() - start
        old = {
            r["sample_id"]: r
            for r in historical["residual"]["fixed_b2_decoder"][view]["predictions"]
        }
        decoded, greedy_times, beam_times = [], [], []
        for i, row in enumerate(logit_rows):
            start = time.perf_counter()
            greedy = decode_greedy(row["logits"], cfg["blank_penalty"])
            greedy_times.append(time.perf_counter() - start)
            previous = old[row["sample_id"]]
            if (
                any(previous[k] != row[k] for k in ["signer_id", "reference"])
                or greedy != previous["prediction"]
            ):
                raise ValueError(
                    "[decoder/audit] Historical greedy reproduction mismatch: "
                    f"{view}/{row['sample_id']}"
                )
            start = time.perf_counter()
            candidates = decode_beam(
                row["logits"], cfg["blank_penalty"], cfg["beam_width"], cfg["top_paths"]
            )
            beam_times.append(time.perf_counter() - start)
            decoded.append(
                {
                    **{k: v for k, v in row.items() if k != "logits"},
                    "greedy": greedy,
                    "candidates": candidates,
                    "greedy_seconds": greedy_times[-1],
                    "beam_seconds": beam_times[-1],
                }
            )
            if (i + 1) % 32 == 0:
                write_json_atomic(
                    OUT / "progress.json",
                    {
                        "view": view,
                        "decoded": i + 1,
                        "selected": 256,
                        "training": False,
                        "test_accessed": False,
                    },
                )
                print(
                    json.dumps({"stage": "DECODING", "view": view, "completed": i + 1}), flush=True
                )
        value = group_report(decoded)
        value["signers"] = {
            s: group_report([r for r in decoded if r["signer_id"] == s])
            for s in sorted({r["signer_id"] for r in decoded})
        }
        groups = {
            "J": [r for r in decoded if "J" in r["reference"]],
            "Z": [r for r in decoded if "Z" in r["reference"]],
            "REPEATED_LETTERS": [
                r
                for r in decoded
                if any(
                    a == b and a != " "
                    for a, b in zip(r["reference"], r["reference"][1:], strict=False)
                )
            ],
        }
        value["subgroups"] = {
            name: {
                **group_report(group),
                "sample_count_sufficient": len(group) >= cfg["minimum_subgroup_sequences"],
            }
            for name, group in groups.items()
        }
        lengths = [r["input_length"] for r in decoded]
        value["timesteps"] = {
            "total": sum(lengths),
            "minimum": min(lengths),
            "median": float(np.median(lengths)),
            "maximum": max(lengths),
        }
        value["runtime"] = {
            "host_cpu_not_phone": True,
            "logits_reused": reused,
            "logit_inference_or_load_seconds": retrieval_seconds,
            "greedy": duration_report(greedy_times),
            "beam": duration_report(beam_times),
        }
        write_json_atomic(
            OUT / f"{view}_candidates.json",
            {
                "schema_version": cfg["schema_version"],
                "configuration": cfg,
                "rows": decoded,
                "test_accessed": False,
            },
        )
        results[view] = value
    result = {
        "schema_version": cfg["schema_version"],
        "status": "CTC_DECODER_AUDIT_COMPLETE",
        "configuration": cfg,
        "sequence_count_per_view": 256,
        "dev_signers": len({r["official_signer_id"] for r in dev}),
        "views": results,
        "historical_greedy_reproduced_exactly": True,
        "training": False,
        "test_accessed": False,
        "phone_logits_available": False,
        "oracle_scope": "REFERENCE_SELECTED_DIAGNOSTIC_NOT_AUTOMATIC_ACCURACY",
    }
    write_json_atomic(OUT / "comparison.json", result)
    print(
        json.dumps({"status": result["status"], "report": str(OUT / "comparison.json")}), flush=True
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run"])
    parser.parse_args()
    try:
        run()
    except Exception as error:
        OUT.mkdir(exist_ok=True)
        write_json_atomic(
            OUT / "failure.json", {"error": str(error), "training": False, "test_accessed": False}
        )
        raise


if __name__ == "__main__":
    main()
