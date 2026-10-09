"""One focused V2.1 local-letter correction; frozen V2 cadence and raw robustness.

Opt-in separate run only. No acquisition, perception, Android or WORD dependency.
DEV-A equal native/phone full/no-SPACE raw-greedy CER selects; fixed beam10/0.5 final.
DEV-B opens only after checkpoint lock, never for augmentation or epoch selection.
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
from model.fingerspelling_emission import collect_logits, evaluate_views
from model.fingerspelling_fast_execution import CompiledSteps
from model.fingerspelling_prefix_beam import decode_beam, decode_greedy
from model.fingerspelling_sequence_v2_1_encoder import (
    CONFIG,
    build_model,
    configuration,
    inference_model,
)
from model.fingerspelling_sequence_v2_1_execution import DualSteps
from model.fingerspelling_sequence_v2_1_review import final_diagnostics
from model.fingerspelling_sequence_v2_encoder import receptive_field
from model.fingerspelling_sequence_v2_execution import RobustTemporalCache
from model.fingerspelling_train4096 import (
    DESTINATION,
    score,
)
from model.fingerspelling_train4096 import (
    code_identity as reference_code_identity,
)
from pipeline.fingerspelling.adapter import identity, sha256
from pipeline.fingerspelling.expanded_training import load, manifests, read_json
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from tools.fingerspelling.tranche import single_writer

RUN = REPO / "runs/fingerspelling_sequence_v2_1_01"
GATE = REPO / "artifacts/fingerspelling_sequence_v2_1_gate_01"
REFERENCE = REPO / "runs/fingerspelling_train4096_01/best_candidates/epoch_038.keras"
REFERENCE_SHA = "b037e32789f523c043b46c32cdc2ea11f2f600fd35f30ecd672604b6f6947886"


def no_space_score(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return score(
        [
            dict(
                r,
                reference=r["reference"].replace(" ", ""),
                prediction=r["prediction"].replace(" ", ""),
            )
            for r in predictions
        ]
    )


def selection_score(views: dict[str, Any]) -> float:
    values = []
    for view in ["native", "phone"]:
        views[view]["no_space_metrics"] = no_space_score(views[view]["predictions"])
        values.extend([views[view]["metrics"]["cer"], views[view]["no_space_metrics"]["cer"]])
    if not np.isfinite(values).all():
        raise ValueError("[sequence-v2.1/selection] Four finite CERs required")
    return float(np.mean(values))


def code_identity() -> dict[str, str]:
    names = [
        "model/fingerspelling_sequence_v2_1.py",
        "model/fingerspelling_sequence_v2_1_review.py",
        "model/fingerspelling_sequence_v2_1_encoder.py",
        "model/fingerspelling_sequence_v2_encoder.py",
        "model/fingerspelling_sequence_v2_1_execution.py",
        "model/fingerspelling_sequence_v2_execution.py",
        "pipeline/fingerspelling/evidence_robustness.py",
    ]
    return reference_code_identity() | {s: sha256(REPO / s) for s in names}


def safe_run(run: Path) -> None:
    if run.resolve().parent != RUN.parent.resolve() or not (
        run.name == RUN.name or run.name.startswith(RUN.name + "_smoke")
    ):
        raise ValueError(
            "[sequence-v2/run] Separate V2 run required; existing candidates protected"
        )


def gate_check() -> None:
    p = read_json(GATE / "architecture_gate.json")
    if (
        p["status"] != "V2_1_ENGINEERING_SMOKE_PASS"
        or p["configuration_sha256"] != sha256(CONFIG)
        or p["code_sha256"] != code_identity()
        or p["adapter"] != identity()
        or sha256(REFERENCE) != REFERENCE_SHA
        or sha256(REPO / configuration()["warmstart_model"]) != configuration()["warmstart_sha256"]
    ):
        raise ValueError("[sequence-v2/gate] Validated architecture/config/code/reference changed")


def run_identity(rows: list[dict[str, Any]], smoke: bool) -> dict[str, Any]:
    return {
        "schema_version": "apphear.fingerspelling.sequence_v2_1_run.v1",
        "configuration": configuration(),
        "configuration_sha256": sha256(CONFIG),
        "code_sha256": code_identity(),
        "adapter": identity(),
        "data_lineage_sha256": b2.lineage(rows),
        "receipt_sha256": {
            r["sample_id"]: sha256(REPO / r["features_path"].replace(".npz", ".receipt.json"))
            for r in rows
        },
        "sample_ids": [r["sample_id"] for r in rows],
        "smoke_only": smoke,
        "checkpoint_selection_cohort": "TRAIN_ENGINEERING_PROXY" if smoke else "DEV_A",
        "dev_b_loaded_for_selection": False,
        "test_accessed": False,
    }


def preflight(destination: Path, run: Path, *, full: bool = True) -> dict[str, Any]:
    import importlib.metadata
    import shutil

    safe_run(run)
    gate_check()
    rows = load(destination, full=full)  # No DEV-B feature arrays, no model inference.
    result = {
        "status": "V2_1_PREFLIGHT_PASS",
        "ready_to_train": True,
        "counts": dict(Counter(r["split_role"] for r in rows)),
        "data_lineage_sha256": b2.lineage(rows),
        "adapter": identity(),
        "configuration_sha256": sha256(CONFIG),
        "tensorflow": importlib.metadata.version("tensorflow"),
        "full_source_raw_adapter_validation": full,
        "phone_infeasible_retained": sum(not r["phone_ctc_feasible"] for r in rows),
        "dev_b_feature_access": False,
        "test_accessed": False,
        "run_disk_free_bytes": shutil.disk_usage(REPO).free,
    }
    write_json_atomic(GATE / "preflight_latest.json", result)
    return result


def engine(
    run: Path,
    rows: list[dict[str, Any]],
    tf: Any,
    *,
    smoke: bool = False,
    stop_after: int | None = None,
) -> dict[str, Any]:
    safe_run(run)
    p = configuration()
    if not smoke:
        expected = {
            r["sample_id"] for r in manifests()["foundation"]["samples"] if r["split_role"] == "DEV"
        }
        if (
            Counter(r["split_role"] for r in rows) != {"TRAIN": 4096, "DEV": 256}
            or {r["sample_id"] for r in rows if r["split_role"] == "DEV"} != expected
        ):
            raise ValueError("[sequence-v2/train] Exact TRAIN4096/DEV-A256 required, DEV-B refused")
    elif any(r["split_role"] != "TRAIN" for r in rows):
        raise ValueError("[sequence-v2/smoke] TRAIN-only engineering proxy required")
    rid = run_identity(rows, smoke)
    run.mkdir(parents=True, exist_ok=True)
    id_path = run / "run_identity.json"
    if id_path.exists():
        if read_json(id_path) != rid:
            raise ValueError("[sequence-v2/resume] Config/code/data changed; mixed resume refused")
    elif any(run.iterdir()):
        raise ValueError("[sequence-v2/run] Nonempty unowned run refused")
    else:
        write_json_atomic(id_path, rid)
    if (run / "confirmation_lock.json").exists():
        raise ValueError("[sequence-v2/train] Post-lock confirmation prohibits further fitting")
    model = build_model(tf, p)
    optimizer = tf.keras.optimizers.Adam(p["learning_rate"], clipnorm=p["gradient_clip_norm"])
    optimizer.build(model.trainable_variables)
    epoch_var = tf.Variable(0, trainable=False, dtype=tf.int64)
    checkpoint = tf.train.Checkpoint(model=model, optimizer=optimizer, epoch=epoch_var)
    manager = tf.train.CheckpointManager(
        checkpoint, str(run / "checkpoints"), max_to_keep=p["checkpoint_keep"]
    )
    state_path = run / "committed_epoch.json"
    state: dict[str, Any] = {
        "epoch": 0,
        "best_combined_cer": None,
        "best_model_path": None,
        "patience_anchor": None,
        "non_improving_epochs": 0,
    }
    if state_path.exists():
        state = read_json(state_path)
        checkpoint.restore(state["checkpoint"]).assert_existing_objects_matched()
        if (
            int(epoch_var.numpy()) != state["epoch"]
            or b2.state_digest(model, optimizer) != state["model_optimizer_sha256"]
        ):
            raise ValueError("[sequence-v2/resume] Model/Adam/epoch mismatch")
        write_json_atomic(
            run / "resume_verification.json",
            {
                "restored_epoch": state["epoch"],
                "optimizer_iterations": int(optimizer.iterations.numpy()),
                "model_optimizer_exactly_restored": True,
                "bit_exact_continuation_claim": False,
            },
        )
    elif manager.latest_checkpoint:
        raise ValueError("[sequence-v2/resume] Uncommitted checkpoint requires review")
    train = [r for r in rows if r["split_role"] == "TRAIN"]
    dev = train if smoke else [r for r in rows if r["split_role"] == "DEV"]
    cache, steps = RobustTemporalCache(p), DualSteps(tf, model, p, optimizer)
    dev_steps = CompiledSteps(tf, inference_model(tf, model))
    write_json_atomic(
        run / "environment.json",
        {
            "tensorflow": tf.__version__,
            "keras": tf.keras.__version__,
            "parameters": model.count_params(),
            "receptive_field": receptive_field(p),
            "causal": False,
            "cpu_threads": p["cpu_threads"],
            "initialization": p["initialization"],
            "resume_granularity": "Committed epoch; interrupted epoch repeats",
            "accuracy_claim": "NONE_ENGINEERING_ONLY" if smoke else "AWAIT_HELDOUT_EVALUATION",
            "test_accessed": False,
        },
    )
    maximum = 4 if smoke else p["maximum_epochs"]
    try:
        for epoch in range(state["epoch"], maximum):
            if (
                not smoke
                and epoch >= p["minimum_epochs"]
                and state["non_improving_epochs"] >= p["patience"]
            ):
                break
            t0 = time.perf_counter()
            order = np.random.default_rng(p["seed"] + epoch).permutation(len(train))
            losses, choices = [], []
            for offset in range(0, len(order), p["batch_size"]):
                batch = [train[i] for i in order[offset : offset + p["batch_size"]]]
                tensors, picked = cache.training_batch(batch, epoch)
                if steps.update is None:
                    raise RuntimeError("[sequence-v2/train] Optimizer unavailable")
                value = tuple(float(v.numpy()) for v in steps.update(*tensors))
                if not np.isfinite(value).all():
                    raise ValueError("[sequence-v2/train] Non-finite loss")
                losses.append((value, len(batch)))
                choices.extend(picked)
            train_seconds = time.perf_counter() - t0
            views, _, times = evaluate_views(tf, dev_steps, cache, dev, p, p["batch_size"])
            metric = selection_score(views)
            if state["best_combined_cer"] is None or metric < state["best_combined_cer"]:
                best = run / "best_candidates" / f"epoch_{epoch + 1:03d}.keras"
                best.parent.mkdir(exist_ok=True)
                inference_model(tf, model).save(best)
                training_best = best.with_name(best.stem + "_training.keras")
                model.save(training_best)
                state.update(
                    best_combined_cer=metric,
                    best_model_path=str(best),
                    best_model_sha256=sha256(best),
                    best_training_model_path=str(training_best),
                    best_training_model_sha256=sha256(training_best),
                    best_epoch=epoch + 1,
                )
            state.update(b2.stopping_state(state, metric, p))
            report = {
                "epoch": epoch + 1,
                "train_total_loss": sum(v[0] * n for v, n in losses) / sum(n for _, n in losses),
                "train_mean_ctc": sum(v[1] * n for v, n in losses) / sum(n for _, n in losses),
                "train_local_letter_ctc": sum(v[2] * n for v, n in losses)
                / sum(n for _, n in losses),
                "combined_raw_greedy_selection_cer": metric,
                "evaluation_cohort": "TRAIN_ENGINEERING_PROXY" if smoke else "DEV_A",
                "views": views,
                "temporal_choices": choices,
                "requested_regimes": dict(Counter(c["requested"] for c in choices)),
                "actual_regimes": dict(Counter(c["actual"] for c in choices)),
                "all_training_sources_retained": len(choices) == len(train),
                "cache_bytes_features_only": cache.bytes,
                "train_seconds": train_seconds,
                "evaluation_seconds": times,
                "dev_b_inference": False,
                "test_accessed": False,
                "smoke_only": smoke,
            }
            write_json_atomic(run / "epochs" / f"epoch_{epoch + 1:03d}.json", report)
            epoch_var.assign(epoch + 1)
            saved = manager.save(checkpoint_number=epoch + 1)
            state.update(
                epoch=epoch + 1,
                checkpoint=saved,
                model_optimizer_sha256=b2.state_digest(model, optimizer),
                optimizer_iterations=int(optimizer.iterations.numpy()),
            )
            write_json_atomic(state_path, state)
            progress = {
                "epoch": epoch + 1,
                "train_ctc": report["train_mean_ctc"],
                "train_local_letter_ctc": report["train_local_letter_ctc"],
                "train_total_loss": report["train_total_loss"],
                "native_selection_cer": views["native"]["metrics"]["cer"],
                "phone_selection_cer": views["phone"]["metrics"]["cer"],
                "selection_score": metric,
                "best_score": state["best_combined_cer"],
                "non_improving_epochs": state["non_improving_epochs"],
                "epoch_seconds": time.perf_counter() - t0,
                "requested_regimes": report["requested_regimes"],
            }
            write_json_atomic(run / "progress.json", progress)
            print(json.dumps(progress), flush=True)
            if stop_after is not None and state["epoch"] >= stop_after:
                return {"status": "ENGINEERING_PAUSE", "epoch": state["epoch"]}
        result = {
            "status": "V2_1_ENGINEERING_SMOKE_COMPLETE" if smoke else "V2_1_TRAINING_COMPLETE",
            **state,
            "production_promoted": False,
            "test_accessed": False,
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
                "last_committed_epoch": (
                    read_json(state_path)["epoch"] if state_path.exists() else 0
                ),
                "resume": "Rerun identical train command; incomplete epoch repeats",
            },
        )
        raise


def inference(
    tf: Any, model: Any, rows: list[dict[str, Any]], cache: RobustTemporalCache, views: list[str]
) -> dict[str, Any]:
    p = configuration()
    steps, result = CompiledSteps(tf, model), {}
    for view in views:
        started = time.perf_counter()
        items = collect_logits(tf, steps, cache, rows, view, p["batch_size"])
        predictions = [
            {k: r[k] for k in ("sample_id", "signer_id", "reference", "input_length", "headroom")}
            | {
                "prediction": decode_beam(r["logits"], 0.5, 10, 1)[0]["prediction"],
                "greedy": decode_greedy(r["logits"], 0.5),
            }
            for r in items
        ]
        result[view] = {
            "metrics": score(predictions),
            "no_space_metrics": no_space_score(predictions),
            "single_word_metrics": score([r for r in predictions if " " not in r["reference"]]),
            "predictions": predictions,
            "ctc_infeasible_retained": sum(r["headroom"] < 0 for r in items),
            "ctc_mean_loss_eligible_only": float(
                np.mean([r["ctc_loss"] for r in items if r["ctc_loss"] is not None])
            ),
            "runtime_seconds": time.perf_counter() - started,
        }
    return result


def comparison(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "cer",
        "substitutions",
        "deletions",
        "insertions",
        "correct_aligned_reference_characters",
        "predicted_reference_ratio",
        "correct_predicted_precision",
        "exact_sequences",
        "macro_signer_cer",
    ]
    return {
        view: {
            "delta": {
                f: candidate[view]["metrics"][f] - baseline[view]["metrics"][f] for f in fields
            },
            "signer_cer_delta": {
                s: m["cer"] - baseline[view]["metrics"]["signers"][s]["cer"]
                for s, m in candidate[view]["metrics"]["signers"].items()
            },
        }
        for view in candidate
    }


def final_evaluate(destination: Path, run: Path) -> dict[str, Any]:
    gate_check()
    completion = read_json(run / "completion.json")
    if completion["status"] != "V2_1_TRAINING_COMPLETE":
        raise ValueError("[sequence-v2/final] Completed full V2 run required")
    rows = load(destination)
    if read_json(run / "run_identity.json") != run_identity(rows, False):
        raise ValueError("[sequence-v2/final] Frozen run identity changed")
    selected = Path(completion["best_model_path"])
    if (
        not selected.resolve().is_relative_to(run.resolve())
        or sha256(selected) != completion["best_model_sha256"]
    ):
        raise ValueError("[sequence-v2/final] Selected checkpoint identity mismatch")
    lock = {
        "completion_sha256": sha256(run / "completion.json"),
        "selected_model_sha256": sha256(selected),
        "configuration_sha256": sha256(CONFIG),
        "reference_sha256": REFERENCE_SHA,
        "v2_reference_sha256": configuration()["warmstart_sha256"],
        "decoder": configuration()["final_decoder"],
    }
    lock_path = run / "confirmation_lock.json"
    if lock_path.exists() and read_json(lock_path) != lock:
        raise ValueError("[sequence-v2/final] Confirmation identity changed")
    if sha256(REPO / configuration()["warmstart_model"]) != configuration()["warmstart_sha256"]:
        raise ValueError("[sequence-v2.1/final] V2 reference changed")
    write_json_atomic(lock_path, lock)  # Lock before any DEV-B feature/inference access.
    if (run / "final_evaluation.json").exists():
        result = read_json(run / "final_evaluation.json")
        if result["confirmation_lock"] != lock:
            raise ValueError("[sequence-v2/final] Stored result identity mismatch")
        return result
    confirmation = load(destination, confirmation=True)
    tf = reference.tensorflow(configuration())
    model = tf.keras.models.load_model(selected, compile=False)
    frozen = tf.keras.models.load_model(REFERENCE, compile=False)
    v2 = tf.keras.models.load_model(REPO / configuration()["warmstart_model"], compile=False)
    cache = RobustTemporalCache(configuration())
    views = ["native", "phone", "stress_moderate", "stress_heavy", "stress_contiguous"]
    result = {
        "status": "V2_1_FINAL_EVALUATED_REVIEW_REQUIRED",
        "confirmation_lock": lock,
        "test_accessed": False,
        "production_promoted": False,
    }
    for cohort, group in [
        ("dev_a", [r for r in rows if r["split_role"] == "DEV"]),
        ("dev_b", confirmation),
    ]:
        candidate = inference(tf, model, group, cache, views)
        baseline = inference(tf, frozen, group, cache, views)
        v2_baseline = inference(tf, v2, group, cache, views)
        result[cohort] = {
            "candidate": candidate,
            "epoch038_reference": baseline,
            "v2_epoch046_reference": v2_baseline,
            "comparison": comparison(candidate, baseline),
            "comparison_vs_v2": comparison(candidate, v2_baseline),
        }
        write_json_atomic(run / (cohort + "_final.json"), result[cohort])
    result["stress_lineage"] = [
        dict(view=view, **info) for (_, view), info in cache.stress_info.items()
    ]
    result["limitations"] = [
        "DEV-A reused for model selection; DEV-B shares its 15 signers and is post-lock "
        "confirmation, not an untouched independent signer test.",
        "Stress masks are controlled synthetic evidence withdrawal, "
        "not a measured CameraX simulator.",
        "Auxiliary supervision and full/no-space checkpoint selection change together; "
        "no isolated causal attribution or quality guarantee.",
    ]
    result["letter_discrimination_diagnostics"] = final_diagnostics(result)
    write_json_atomic(run / "final_evaluation.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "train", "status", "evaluate"])
    parser.add_argument("--destination", type=Path, default=DESTINATION)
    parser.add_argument("--run-dir", type=Path, default=RUN)
    args = parser.parse_args()
    safe_run(args.run_dir)
    if args.command == "status":
        result = {
            name: (
                read_json(args.run_dir / (name + ".json"))
                if (args.run_dir / (name + ".json")).exists()
                else None
            )
            for name in ("progress", "completion", "failure")
        }
    elif args.command == "preflight":
        result = preflight(args.destination, args.run_dir)
    else:
        with single_writer(args.run_dir):
            if args.command == "train":
                preflight(args.destination, args.run_dir)
                result = engine(
                    args.run_dir, load(args.destination), reference.tensorflow(configuration())
                )
            else:
                result = final_evaluate(args.destination, args.run_dir)
    print(
        json.dumps(
            (
                result
                if args.command != "evaluate"
                else {
                    "status": result["status"],
                    "report": str(args.run_dir / "final_evaluation.json"),
                    "test_accessed": False,
                    "production_promoted": False,
                }
            ),
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
