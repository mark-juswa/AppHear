"""Isolated lower-rate finishing of the existing 1K B2 recognizer; WORD is sealed.

One fixed three-epoch cadence-cycle gate precedes any user-run continuation. No data,
perception, architecture, decoder, loss or feature contract changes; no 4K/DEV-B/TEST.
"""

from __future__ import annotations

import argparse
import json
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from model import fingerspelling_baseline2 as b2
from model import fingerspelling_ctc as reference
from model.fingerspelling_emission import collect_logits
from model.fingerspelling_fast_execution import CompiledSteps, FeatureCache
from model.fingerspelling_prefix_beam import decode_beam
from model.fingerspelling_temporal_execution import TemporalFeatureCache
from model.fingerspelling_train4096 import changes, score
from pipeline.fingerspelling.adapter import identity, sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from tools.fingerspelling.tranche import single_writer

CONFIG = REPO / "model/config/fingerspelling_1k_optimization_01.json"
DATA = REPO / "datasets/fingerspelling/foundation_01"
RUN = REPO / "runs/fingerspelling_1k_optimization_01"
EVIDENCE = REPO / "artifacts/fingerspelling_1k_optimization_01"


def read(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return result


def configuration() -> dict[str, Any]:
    p = read(CONFIG)
    if (
        p["schema_version"] != "apphear.fingerspelling.1k_optimization.v1"
        or p["feature_width"] != 405
        or p["train_count"] != 1024
        or p["dev_count"] != 256
        or p["beam_width"] != 10
        or p["blank_penalty"] != 0.5
        or p["blank_index"] != 27
        or p["top_paths"] != 1
        or p["gate_epochs"] != 3
        or p["test_access"] != "SEALED"
        or sha256(REPO / p["initial_checkpoint"]) != p["initial_checkpoint_sha256"]
        or sha256(DATA / "tranche_manifest.json") != p["foundation_manifest_sha256"]
    ):
        raise ValueError("[1k-optimization/config] Frozen experiment identity mismatch")
    return p


def safe_run(run: Path) -> None:
    if run.resolve().parent != (REPO / "runs").resolve() or not (
        run.name == RUN.name or run.name.startswith(RUN.name + "_smoke")
    ):
        raise ValueError("[1k-optimization/run] Separate owned 1K run required")


def lr(epoch_index: int) -> float:
    return float(configuration()["gate_learning_rate"]) * (1.0 if epoch_index < 6 else 0.5)


def combined(report: dict[str, Any]) -> float:
    return float(np.mean([report[v]["metrics"]["cer"] for v in ("native", "phone")]))


def initial_model(tf: Any) -> Any:
    p = configuration()
    model = tf.keras.models.load_model(REPO / p["initial_checkpoint"], compile=False)
    if model.count_params() != 193116 or model.output_shape != (None, None, 28):
        raise ValueError("[1k-optimization/model] Frozen B2 architecture mismatch")
    return model


def inference(tf: Any, model: Any, rows: list[dict[str, Any]]) -> dict[str, Any]:
    _, base = b2.policy()
    cache, steps, result = FeatureCache(), CompiledSteps(tf, model), {}
    for view in ("native", "phone"):
        started = time.perf_counter()
        logits = collect_logits(tf, steps, cache, rows, view, base["batch_size"])
        predictions = [
            {k: r[k] for k in ("sample_id", "signer_id", "reference", "input_length", "headroom")}
            | {"prediction": decode_beam(r["logits"], 0.5, 10, 1)[0]["prediction"]}
            for r in logits
        ]
        result[view] = {
            "metrics": score(predictions),
            "predictions": predictions,
            "ctc_infeasible_retained": sum(r["headroom"] < 0 for r in logits),
            "seconds": time.perf_counter() - started,
        }
    return result


def gate_result(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    p = configuration()
    comparison = changes(candidate, baseline)
    gain = combined(baseline) - combined(candidate)
    return {
        "comparison": comparison,
        "balanced_cer_gain": gain,
        "meaningful_improvement_supported": gain >= p["gate_minimum_balanced_cer_gain"]
        and all(v["discrimination_pattern_supported"] for v in comparison.values()),
        "interpretation": (
            "DEV reused; controlled development result, not production or independent TEST accuracy"
        ),
    }


def run_identity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    code = [
        "model/fingerspelling_1k_optimization.py",
        "model/fingerspelling_baseline2.py",
        "model/fingerspelling_train4096.py",
        "pipeline/fingerspelling/expanded_training.py",
        "model/fingerspelling_fast_execution.py",
        "model/fingerspelling_ctc.py",
        "model/fingerspelling_metrics.py",
        "model/fingerspelling_prefix_beam.py",
        "model/fingerspelling_temporal_execution.py",
        "pipeline/fingerspelling/temporal_views.py",
    ]
    return {
        "config": configuration(),
        "config_sha256": sha256(CONFIG),
        "adapter": identity(),
        "data_lineage": b2.lineage(rows),
        "sample_ids": [r["sample_id"] for r in rows],
        "code": {s: sha256(REPO / s) for s in code},
        "test_accessed": False,
        "expanded_data_used": False,
    }


def engine(run: Path, tf: Any, *, gate: bool) -> dict[str, Any]:
    safe_run(run)
    p, rows = configuration(), b2.dataset(DATA)
    train = [r for r in rows if r["split_role"] == "TRAIN"]
    dev = [r for r in rows if r["split_role"] == "DEV"]
    if len(train) != 1024 or len(dev) != 256:
        raise ValueError("[1k-optimization/data] Exact original 1K/256 required")
    cadence, base = b2.policy()
    rid = run_identity(rows)
    run.mkdir(parents=True, exist_ok=True)
    if (run / "run_identity.json").exists():
        if read(run / "run_identity.json") != rid:
            raise ValueError("[1k-optimization/resume] Code/config/data identity changed")
    elif any(run.iterdir()):
        raise ValueError("[1k-optimization/run] Nonempty unowned run refused")
    else:
        write_json_atomic(run / "run_identity.json", rid)
    if not gate:
        result = read(run / "gate_result.json")
        if not result["vs_current_residual"]["meaningful_improvement_supported"]:
            raise ValueError("[1k-optimization/train] Gate did not justify further finishing")
    model = initial_model(tf)
    optimizer = tf.keras.optimizers.Adam(
        p["gate_learning_rate"], clipnorm=base["gradient_clip_norm"]
    )
    optimizer.build(model.trainable_variables)
    epoch_var = tf.Variable(0, trainable=False, dtype=tf.int64)
    checkpoint = tf.train.Checkpoint(model=model, optimizer=optimizer, epoch=epoch_var)
    manager = tf.train.CheckpointManager(checkpoint, str(run / "checkpoints"), max_to_keep=3)
    state_path = run / "committed_epoch.json"
    state: dict[str, Any] = {
        "epoch": 0,
        "best_epoch": 0,
        "best_model_path": str(REPO / p["initial_checkpoint"]),
        "best_model_sha256": p["initial_checkpoint_sha256"],
        "non_improving_epochs": 0,
    }
    if state_path.exists():
        state = read(state_path)
        checkpoint.restore(state["checkpoint"]).assert_existing_objects_matched()
        if (
            int(epoch_var.numpy()) != state["epoch"]
            or b2.state_digest(model, optimizer) != state["model_optimizer_sha256"]
        ):
            raise ValueError("[1k-optimization/resume] Model/Adam/epoch restore mismatch")
        write_json_atomic(
            run / "resume_verification.json",
            {
                "epoch": state["epoch"],
                "model_optimizer_exactly_restored": True,
                "bit_exact_continuation_claim": False,
            },
        )
    elif manager.latest_checkpoint:
        raise ValueError("[1k-optimization/resume] Uncommitted checkpoint requires review")
    initial_path = run / "initial_b2_dev.json"
    if not initial_path.exists():
        baseline = inference(tf, model, dev)
        old = read(
            REPO / "artifacts/fingerspelling_outer_boundary_oracle_01/paired_evaluation.json"
        )
        for view in ("native", "phone"):
            for key in (
                "cer",
                "substitutions",
                "deletions",
                "insertions",
                "correct_aligned_reference_characters",
            ):
                if baseline[view]["metrics"][key] != old["models"]["b2"][view]["full"][key]:
                    raise ValueError(
                        "[1k-optimization/parity] Initial frozen B2 DEV output changed"
                    )
        write_json_atomic(initial_path, baseline)
    else:
        baseline = read(initial_path)
    if "best_score" not in state:
        state["best_score"] = combined(baseline)
    maximum = p["gate_epochs"] if gate else p["maximum_epochs"]
    cache, steps = TemporalFeatureCache(cadence), CompiledSteps(tf, model, optimizer)
    try:
        for epoch in range(state["epoch"], maximum):
            if (
                not gate
                and epoch >= p["minimum_epochs"]
                and state["non_improving_epochs"] >= p["patience"]
            ):
                break
            started = time.perf_counter()
            optimizer.learning_rate.assign(lr(epoch))
            order = np.random.default_rng(cadence["seed"] + epoch).permutation(len(train))
            losses, choices = [], []
            for start in range(0, len(order), base["batch_size"]):
                batch = [train[i] for i in order[start : start + base["batch_size"]]]
                tensors, picked = cache.training_batch(batch, epoch)
                if steps.update is None:
                    raise RuntimeError("[1k-optimization/train] Optimizer missing")
                value = float(steps.update(*tensors).numpy())
                if not np.isfinite(value):
                    raise ValueError("[1k-optimization/train] Nonfinite loss")
                losses.append((value, len(batch)))
                choices.extend(picked)
            report: dict[str, Any] = {
                "epoch": epoch + 1,
                "learning_rate": lr(epoch),
                "train_ctc": sum(v * n for v, n in losses) / sum(n for _, n in losses),
                "temporal_choices": choices,
                "requested_views": dict(Counter(c["requested"] for c in choices)),
                "fallbacks": sum(c["fallback"] for c in choices),
                "all1024_retained": len(choices) == 1024,
                "test_accessed": False,
            }
            # Gate tests one predefined final model, not three post-hoc checkpoint choices.
            if not gate or epoch + 1 == maximum:
                dev_report = inference(tf, model, dev)
                write_json_atomic(run / "evaluation" / f"epoch_{epoch+1:03d}.json", dev_report)
                score = combined(dev_report)
                report["balanced_fixed_beam_dev_cer"] = score
                if score < state["best_score"]:
                    path = run / "best_candidates" / f"epoch_{epoch+1:03d}.keras"
                    path.parent.mkdir(exist_ok=True)
                    model.save(path)
                    state.update(
                        best_score=score,
                        best_epoch=epoch + 1,
                        best_model_path=str(path),
                        best_model_sha256=sha256(path),
                        non_improving_epochs=0,
                    )
                else:
                    state["non_improving_epochs"] += 1
            epoch_var.assign(epoch + 1)
            saved = manager.save(checkpoint_number=epoch + 1)
            state.update(
                epoch=epoch + 1,
                checkpoint=saved,
                model_optimizer_sha256=b2.state_digest(model, optimizer),
            )
            write_json_atomic(state_path, state)
            report["seconds"] = time.perf_counter() - started
            write_json_atomic(run / "epochs" / f"epoch_{epoch+1:03d}.json", report)
            progress = {
                k: report[k]
                for k in ["epoch", "learning_rate", "train_ctc", "requested_views", "seconds"]
            }
            progress["best_beam_dev_cer"] = state["best_score"]
            write_json_atomic(run / "progress.json", progress)
            print(json.dumps(progress), flush=True)
        if gate:
            candidate = read(run / "evaluation" / f"epoch_{p['gate_epochs']:03d}.json")
            archived = read(
                REPO / "artifacts/fingerspelling_outer_boundary_oracle_01/paired_evaluation.json"
            )
            residual = {
                v: {"metrics": archived["models"]["residual"][v]["full"]}
                for v in ["native", "phone"]
            }
            result = {
                "status": "ONE_CADENCE_CYCLE_GATE_EVALUATED",
                "epochs": state["epoch"],
                "counts": {"TRAIN": 1024, "DEV": 256},
                "vs_frozen_b2": gate_result(candidate, baseline),
                "vs_current_residual": gate_result(candidate, residual),
                "candidate": candidate,
                "reference_b2": baseline,
                "test_accessed": False,
                "4k_used": False,
                "android_promoted": False,
            }
            write_json_atomic(run / "gate_result.json", result)
            return {
                k: result[k] for k in ["status", "epochs", "vs_frozen_b2", "vs_current_residual"]
            }
        result = {
            "status": "ONE_K_FINISHING_COMPLETE",
            **state,
            "test_accessed": False,
            "android_promoted": False,
        }
        write_json_atomic(run / "completion.json", result)
        return result
    except BaseException as exc:
        write_json_atomic(
            run / "failure.json",
            {
                "type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "resume": "Rerun identical command; interrupted epoch repeats",
            },
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["gate", "train", "status"])
    parser.add_argument("--run-dir", type=Path, default=RUN)
    args = parser.parse_args()
    safe_run(args.run_dir)
    if args.command == "status":
        result = (
            read(args.run_dir / "progress.json")
            if (args.run_dir / "progress.json").exists()
            else {"status": "NOT_STARTED"}
        )
    else:
        _, base = b2.policy()
        tf = reference.tensorflow(base)
        with single_writer(args.run_dir):
            result = engine(args.run_dir, tf, gate=args.command == "gate")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
