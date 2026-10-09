"""One controlled expanded-supervision run. No WORD imports or automatic deployment.

Warm-starts an immutable copy of B2, retaining its architecture, cadence and loss.
DEV-A selects checkpoints using the historical raw greedy score. Beam10/0.5 is fixed
for final evaluation; DEV-B is opened for inference only after completion is locked.
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
from model.fingerspelling_emission import balanced_score, collect_logits, evaluate_views
from model.fingerspelling_fast_execution import CompiledSteps, FeatureCache
from model.fingerspelling_metrics import alignment, summarize
from model.fingerspelling_prefix_beam import decode_beam, decode_greedy
from model.fingerspelling_temporal_execution import TemporalFeatureCache
from pipeline.fingerspelling.adapter import identity, sha256
from pipeline.fingerspelling.expanded_training import (
    CONFIG,
    FOUNDATION,
    configuration,
    load,
    manifests,
    read_json,
    verify_record,
)
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from tools.fingerspelling.tranche import single_writer

DESTINATION = Path("I:/AppHearData/FSboard_TRAIN4096_01")
RUN = REPO / "runs/fingerspelling_train4096_01"
EVIDENCE = REPO / "artifacts/fingerspelling_quality_resolution_01"


def settings() -> tuple[dict[str, Any], dict[str, Any]]:
    cadence, base = b2.policy()
    p = configuration()
    cadence = {
        **cadence,
        **{
            k: p[k] for k in ("maximum_epochs", "minimum_epochs", "patience", "minimum_improvement")
        },
    }
    if sha256(REPO / p["initial_checkpoint"]) != p["initial_checkpoint_sha256"]:
        raise ValueError("[train4096/model] Frozen B2 checkpoint changed")
    return cadence, {**base, "learning_rate": p["learning_rate"]}


def safe_run(run: Path) -> None:
    resolved = run.resolve()
    if resolved.parent != (REPO / "runs").resolve() or not (
        resolved.name == RUN.name or resolved.name.startswith(RUN.name + "_smoke")
    ):
        raise ValueError("[train4096/run] Separate owned expanded-data run required")


def code_identity() -> dict[str, str]:
    files = [
        "model/fingerspelling_train4096.py",
        "pipeline/fingerspelling/expanded_training.py",
        "model/fingerspelling_baseline2.py",
        "model/fingerspelling_ctc.py",
        "model/fingerspelling_fast_execution.py",
        "model/fingerspelling_temporal_execution.py",
        "model/fingerspelling_emission.py",
        "model/fingerspelling_metrics.py",
        "model/fingerspelling_prefix_beam.py",
        "pipeline/fingerspelling/temporal_views.py",
        "pipeline/fingerspelling/sequence_package.py",
        "pipeline/fingerspelling/storage.py",
        "model/config/fingerspelling_ctc_baseline_01.json",
        "model/config/fingerspelling_ctc_baseline_02.json",
    ]
    return {s: sha256(REPO / s) for s in files}


def run_identity(rows: list[dict[str, Any]], smoke: bool) -> dict[str, Any]:
    return {
        "schema_version": "apphear.fingerspelling.train4096_run.v1",
        "configuration": configuration(),
        "configuration_sha256": sha256(CONFIG),
        "adapter": identity(),
        "code_sha256": code_identity(),
        "data_lineage_sha256": b2.lineage(rows),
        "receipt_sha256": {
            r["sample_id"]: sha256(REPO / r["features_path"].replace(".npz", ".receipt.json"))
            for r in rows
        },
        "sample_ids": [r["sample_id"] for r in rows],
        "smoke_only": smoke,
        "checkpoint_selection_cohort": "DEV_A",
        "dev_b_loaded_for_selection": False,
        "test_accessed": False,
    }


def inventory(destination: Path) -> dict[str, Any]:
    docs = manifests()
    packages = [
        ("foundation", FOUNDATION, docs["foundation"]),
        ("train_additions", destination / "train_additions", docs["additions"]),
        ("dev_b", destination / "dev_b", docs["confirmation"]),
    ]
    counts = {}
    for name, path, doc in packages:
        counts[name] = {
            "selected": len(doc["samples"]),
            "receipt_files": sum(
                (path / "features" / (r["sample_id"] + ".receipt.json")).is_file()
                for r in doc["samples"]
            ),
        }
    return {"packages": counts, "fresh_integrity_validation": False, "test_accessed": False}


def preflight(destination: Path, run: Path) -> dict[str, Any]:
    import importlib.metadata
    import shutil

    safe_run(run)
    settings()
    report: dict[str, Any] = {
        "inventory": inventory(destination),
        "configuration_sha256": sha256(CONFIG),
        "adapter": identity(),
        "tensorflow": importlib.metadata.version("tensorflow"),
        "test_accessed": False,
    }
    if any(g["receipt_files"] != g["selected"] for g in report["inventory"]["packages"].values()):
        report.update(status="TRAIN4096_DATA_PENDING", ready_to_train=False)
    else:
        rows = load(destination, full=True)
        confirmation = load(destination, confirmation=True, full=True)
        # Metadata/raw validation is permitted here; no DEV-B model inference or selection.
        report.update(
            status="TRAIN4096_PREFLIGHT_PASS",
            ready_to_train=True,
            counts=dict(Counter(r["split_role"] for r in rows)),
            confirmation_count=len(confirmation),
            data_lineage_sha256=b2.lineage(rows),
            confirmation_lineage_sha256=b2.lineage(confirmation),
            phone_infeasible_retained=sum(not r["phone_ctc_feasible"] for r in rows),
            confirmation_inference=False,
            full_source_raw_adapter_validation=True,
        )
    report["run_disk_free_bytes"] = shutil.disk_usage(REPO).free
    write_json_atomic(EVIDENCE / "expanded_preflight.json", report)
    return report


def initial_model(tf: Any) -> Any:
    p = configuration()
    if sha256(REPO / p["initial_checkpoint"]) != p["initial_checkpoint_sha256"]:
        raise ValueError("[train4096/model] Initial checkpoint identity mismatch")
    model = tf.keras.models.load_model(REPO / p["initial_checkpoint"], compile=False)
    if (
        model.count_params() != 193116
        or model.input_shape != [(None, None, 405), (None, None, 1)]
        or model.output_shape != (None, None, 28)
    ):
        raise ValueError("[train4096/model] B2 architecture/shape mismatch")
    return model


def engine(
    run: Path,
    rows: list[dict[str, Any]],
    tf: Any,
    *,
    smoke: bool = False,
    stop_after: int | None = None,
) -> dict[str, Any]:
    safe_run(run)
    if not smoke and Counter(r["split_role"] for r in rows) != {"TRAIN": 4096, "DEV": 256}:
        raise ValueError("[train4096/train] Full admitted TRAIN4096 + DEV-A256 required")
    if not smoke and {r["sample_id"] for r in rows if r["split_role"] == "DEV"} != {
        r["sample_id"] for r in manifests()["foundation"]["samples"] if r["split_role"] == "DEV"
    }:
        raise ValueError("[train4096/train] DEV-A identities required; DEV-B refused")
    p, base = settings()
    rid = run_identity(rows, smoke)
    run.mkdir(parents=True, exist_ok=True)
    id_path = run / "run_identity.json"
    if id_path.is_file():
        if read_json(id_path) != rid:
            raise ValueError("[train4096/resume] Config/code/data changed; mixed resume refused")
    elif any(run.iterdir()):
        raise ValueError("[train4096/run] Nonempty unowned run refused")
    else:
        write_json_atomic(id_path, rid)
    if (run / "confirmation_lock.json").exists():
        raise ValueError(
            "[train4096/train] DEV-B already opened; further fitting/selection prohibited"
        )
    model = initial_model(tf)
    optimizer = tf.keras.optimizers.Adam(base["learning_rate"], clipnorm=base["gradient_clip_norm"])
    optimizer.build(model.trainable_variables)
    epoch_var = tf.Variable(0, trainable=False, dtype=tf.int64)
    checkpoint = tf.train.Checkpoint(model=model, optimizer=optimizer, epoch=epoch_var)
    manager = tf.train.CheckpointManager(
        checkpoint, str(run / "checkpoints"), max_to_keep=base["checkpoint_keep"]
    )
    state_path = run / "committed_epoch.json"
    state: dict[str, Any] = {
        "epoch": 0,
        "best_combined_cer": None,
        "best_model_path": None,
        "patience_anchor": None,
        "non_improving_epochs": 0,
    }
    if state_path.is_file():
        state = read_json(state_path)
        checkpoint.restore(state["checkpoint"]).assert_existing_objects_matched()
        if (
            int(epoch_var.numpy()) != state["epoch"]
            or b2.state_digest(model, optimizer) != state["model_optimizer_sha256"]
        ):
            raise ValueError("[train4096/resume] Model/Adam/epoch mismatch")
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
        raise ValueError("[train4096/resume] Uncommitted initial checkpoint requires review")
    maximum = 3 if smoke else p["maximum_epochs"]
    train = [r for r in rows if r["split_role"] == "TRAIN"]
    dev_a = [r for r in rows if r["split_role"] == "DEV"]
    cache, steps = TemporalFeatureCache(p), CompiledSteps(tf, model, optimizer)
    write_json_atomic(
        run / "environment.json",
        {
            "tensorflow": tf.__version__,
            "keras": tf.keras.__version__,
            "parameters": model.count_params(),
            "cpu_only": True,
            "fresh_adam": True,
            "initial_b2_checkpoint_sha256": configuration()["initial_checkpoint_sha256"],
            "resume_granularity": "Committed epoch; interrupted epoch repeats",
            "test_accessed": False,
        },
    )
    try:
        for epoch in range(state["epoch"], maximum):
            if (
                not smoke
                and epoch >= p["minimum_epochs"]
                and state["non_improving_epochs"] >= p["patience"]
            ):
                break
            started = time.perf_counter()
            order = np.random.default_rng(p["seed"] + epoch).permutation(len(train))
            losses, choices = [], []
            for offset in range(0, len(order), base["batch_size"]):
                batch = [train[i] for i in order[offset : offset + base["batch_size"]]]
                tensors, picked = cache.training_batch(batch, epoch)
                if steps.update is None:
                    raise RuntimeError("[train4096/train] Optimizer missing")
                value = float(steps.update(*tensors).numpy())
                if not np.isfinite(value):
                    raise ValueError("[train4096/train] Non-finite loss")
                losses.append((value, len(batch)))
                choices.extend(picked)
            train_seconds = time.perf_counter() - started
            views, _, view_seconds = evaluate_views(tf, steps, cache, dev_a, p, base["batch_size"])
            score = balanced_score(views)
            if state["best_combined_cer"] is None or score < state["best_combined_cer"]:
                best = run / "best_candidates" / f"epoch_{epoch + 1:03d}.keras"
                best.parent.mkdir(exist_ok=True)
                model.save(best)
                state.update(
                    best_combined_cer=score,
                    best_model_path=str(best),
                    best_model_sha256=sha256(best),
                    best_epoch=epoch + 1,
                )
            state.update(b2.stopping_state(state, score, p))
            report: dict[str, Any] = {
                "epoch": epoch + 1,
                "train_mean_ctc": sum(value * n for value, n in losses) / sum(n for _, n in losses),
                "combined_raw_greedy_dev_a_cer": score,
                "dev_a": views,
                "temporal_views": {
                    "requested_counts": dict(Counter(c["requested"] for c in choices)),
                    "actual_counts": dict(Counter(c["actual"] for c in choices)),
                    "fallback_count": sum(c["fallback"] for c in choices),
                    "choices": choices,
                    "all_training_sources_retained": len(choices) == len(train),
                },
                "timings": {"train_seconds": train_seconds, "dev_seconds": view_seconds},
                "cache_bytes": cache.bytes,
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
            report["timings"]["epoch_seconds"] = time.perf_counter() - started
            write_json_atomic(run / "epochs" / f"epoch_{epoch + 1:03d}.json", report)
            progress = {
                "epoch": epoch + 1,
                "train_ctc": report["train_mean_ctc"],
                "native_dev_a_cer": views["native"]["metrics"]["cer"],
                "phone_dev_a_cer": views["phone"]["metrics"]["cer"],
                "selection_score": score,
                "best_score": state["best_combined_cer"],
                "non_improving_epochs": state["non_improving_epochs"],
                "epoch_seconds": report["timings"]["epoch_seconds"],
                "requested_views": report["temporal_views"]["requested_counts"],
            }
            write_json_atomic(run / "progress.json", progress)
            print(json.dumps(progress), flush=True)
            if stop_after is not None and state["epoch"] >= stop_after:
                return {"status": "ENGINEERING_PAUSE", "epoch": state["epoch"]}
        completion = {
            "status": "ENGINEERING_SMOKE_COMPLETE" if smoke else "TRAIN4096_TRAINING_COMPLETE",
            **state,
            "test_accessed": False,
            "production_promoted": False,
        }
        write_json_atomic(run / "completion.json", completion)
        return completion
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
                "resume": "Rerun the identical train command; interrupted epoch repeats",
            },
        )
        raise


def score(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    result = summarize(predictions, 10)
    correct = result["reference_characters"] - result["substitutions"] - result["deletions"]
    predicted = sum(len(r["prediction"]) for r in predictions)
    result.update(
        correct_aligned_reference_characters=correct,
        predicted_characters=predicted,
        correct_predicted_precision=correct / predicted if predicted else 0.0,
        predicted_reference_ratio=predicted / result["reference_characters"],
        exact_sequences=sum(r["reference"] == r["prediction"] for r in predictions),
        empty_predictions=sum(not r["prediction"] for r in predictions),
        macro_signer_cer=float(np.mean([r["cer"] for r in result["signers"].values()])),
    )
    ops = [
        op for r in predictions for op in alignment(r["reference"], r["prediction"])["operations"]
    ]
    result["character_recall"] = {
        c: {
            "reference": sum(o[1] == c for o in ops),
            "correct": sum(o[0] == "M" and o[1] == c for o in ops),
        }
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ "
    }
    return result


def inference(
    tf: Any, model: Any, rows: list[dict[str, Any]], *, beam: bool = True
) -> dict[str, Any]:
    _, base = settings()
    steps, cache, result = CompiledSteps(tf, model), FeatureCache(), {}
    for view in ("native", "phone"):
        started = time.perf_counter()
        logits = collect_logits(tf, steps, cache, rows, view, base["batch_size"])
        predictions = [
            {k: r[k] for k in ("sample_id", "signer_id", "reference", "input_length", "headroom")}
            | {
                "prediction": (
                    decode_beam(r["logits"], 0.5, 10, 1)[0]["prediction"]
                    if beam
                    else decode_greedy(r["logits"], 0.5)
                )
            }
            for r in logits
        ]
        result[view] = {
            "metrics": score(predictions),
            "predictions": predictions,
            "ctc_infeasible_retained": sum(r["headroom"] < 0 for r in logits),
            "runtime_seconds": time.perf_counter() - started,
        }
    return result


def changes(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for view in ("native", "phone"):
        c, b = candidate[view]["metrics"], baseline[view]["metrics"]
        precision = (
            b["correct_aligned_reference_characters"] / b["predicted_characters"]
            if b["predicted_characters"]
            else 0.0
        )
        signers = {s: c["signers"][s]["cer"] - b["signers"][s]["cer"] for s in b["signers"]}
        result[view] = {
            "cer_delta": c["cer"] - b["cer"],
            "correct_character_delta": c["correct_aligned_reference_characters"]
            - b["correct_aligned_reference_characters"],
            "substitution_delta": c["substitutions"] - b["substitutions"],
            "deletion_delta": c["deletions"] - b["deletions"],
            "insertion_delta": c["insertions"] - b["insertions"],
            "precision_delta": c["correct_predicted_precision"] - precision,
            "signer_cer_deltas": signers,
            "improved_signers": sum(v < 0 for v in signers.values()),
            "regressed_signers": sum(v > 0 for v in signers.values()),
            "discrimination_pattern_supported": c["cer"] < b["cer"]
            and c["correct_aligned_reference_characters"]
            > b["correct_aligned_reference_characters"]
            and c["substitutions"] < b["substitutions"]
            and c["correct_predicted_precision"] >= precision
            and sum(v < 0 for v in signers.values()) > len(signers) / 2,
        }
    return result


def final_evaluate(destination: Path, run: Path) -> dict[str, Any]:
    safe_run(run)
    completion = read_json(run / "completion.json")
    if completion["status"] != "TRAIN4096_TRAINING_COMPLETE":
        raise ValueError("[train4096/final] Completed full run required before confirmation")
    rows = load(destination)
    if read_json(run / "run_identity.json") != run_identity(rows, False):
        raise ValueError("[train4096/final] Frozen run identity changed")
    model_path = Path(completion["best_model_path"])
    if (
        not model_path.resolve().is_relative_to(run.resolve())
        or sha256(model_path) != completion["best_model_sha256"]
    ):
        raise ValueError("[train4096/final] Selected checkpoint mismatch")
    confirmation = load(destination, confirmation=True)
    lock = {
        "completion_sha256": sha256(run / "completion.json"),
        "selected_checkpoint_sha256": sha256(model_path),
        "decoder": configuration()["final_decoder"],
        "dev_b_manifest_sha256": configuration()["confirmation_manifest_sha256"],
        "dev_b_lineage_sha256": b2.lineage(confirmation),
    }
    lock_path = run / "confirmation_lock.json"
    if lock_path.exists() and read_json(lock_path) != lock:
        raise ValueError("[train4096/final] Confirmation selection changed")
    write_json_atomic(lock_path, lock)  # No later train invocation can fit/select after this.
    if (run / "final_evaluation.json").is_file():
        result = read_json(run / "final_evaluation.json")
        if result["confirmation_lock"] != lock:
            raise ValueError("[train4096/final] Stored confirmation identity mismatch")
        return result
    _, base = settings()
    tf = reference.tensorflow(base)
    selected = tf.keras.models.load_model(model_path, compile=False)
    dev_a = [r for r in rows if r["split_role"] == "DEV"]
    candidate_a = inference(tf, selected, dev_a)
    write_json_atomic(run / "dev_a_final.json", candidate_a)
    # Historical current Android residual candidate, identical 256 DEV-A and beam10/0.5.
    archived_path = REPO / configuration()["dev_a_reference_artifact"]
    if sha256(archived_path) != configuration()["dev_a_reference_sha256"]:
        raise ValueError("[train4096/final] Historical comparison artifact changed")
    archived = read_json(archived_path)
    baseline_a = {
        v: {"metrics": archived["models"]["residual"][v]["full"]} for v in ("native", "phone")
    }
    candidate_b = inference(tf, selected, confirmation)
    reference_b = inference(tf, initial_model(tf), confirmation)
    comparisons = {
        "dev_a_vs_frozen_residual_beam": changes(candidate_a, baseline_a),
        "dev_b_vs_frozen_b2_beam": changes(candidate_b, reference_b),
    }
    old_train_ids = {
        r["sample_id"] for r in manifests()["foundation"]["samples"] if r["split_role"] == "TRAIN"
    }
    old_train = [r for r in rows if r["sample_id"] in old_train_ids]
    train_reference_path = REPO / configuration()["train_fit_reference_artifact"]
    if sha256(train_reference_path) != configuration()["train_fit_reference_sha256"]:
        raise ValueError("[train4096/final] Full TRAIN diagnostic reference changed")
    train_fit = inference(tf, selected, old_train)
    train_reference = read_json(train_reference_path)["views"]
    supported = all(
        v["discrimination_pattern_supported"] for c in comparisons.values() for v in c.values()
    )
    result = {
        "status": "TRAIN4096_FINAL_EVALUATED",
        "confirmation_lock": lock,
        "dev_a": candidate_a,
        "dev_b": candidate_b,
        "dev_b_frozen_b2_reference": reference_b,
        "comparisons": comparisons,
        "original_train1024_fit_diagnostic_not_heldout": train_fit,
        "fit_comparison_vs_b2_not_heldout": changes(train_fit, train_reference),
        "dev_a_reference_artifact_sha256": sha256(archived_path),
        "decision": (
            "EXPANDED_SUPERVISION_DISCRIMINATION_SUPPORTED_REVIEW_REQUIRED"
            if supported
            else "EXPANDED_SUPERVISION_IMPROVEMENT_NOT_ESTABLISHED"
        ),
        "limitation": (
            "DEV-A was reused for selection; DEV-B shares its 15 signers and has some phrase "
            "overlap. DEV-B is fresh confirmation, not a new independent signer test. "
            "Residual visual embeddings are not materialized for DEV-B; its comparator is B2 only."
        ),
        "test_accessed": False,
        "production_promoted": False,
    }
    write_json_atomic(run / "final_evaluation.json", result)
    return {
        k: result[k] for k in ("status", "decision", "test_accessed", "production_promoted")
    } | {"report": str(run / "final_evaluation.json")}


def smoke(run: Path) -> dict[str, Any]:
    p, base = settings()
    selected = b2.smoke_rows(b2.dataset(FOUNDATION), p)
    docs = manifests()
    by_id = {r["sample_id"]: r for r in docs["foundation"]["samples"]}
    for rec in selected:
        verify_record(
            FOUNDATION,
            by_id[rec["sample_id"]],
            configuration()["foundation_manifest_sha256"],
            full=True,
        )
    tf = reference.tensorflow(base)
    model = initial_model(tf)
    x, mask, *_ = FeatureCache().batch(selected[:2], "native")
    original = tf.keras.models.load_model(
        REPO / configuration()["initial_checkpoint"], compile=False
    )
    maximum_difference = float(
        np.max(
            np.abs(
                model([x, mask], training=False).numpy()
                - original([x, mask], training=False).numpy()
            )
        )
    )
    if maximum_difference != 0.0:
        raise ValueError("[train4096/smoke] Warm-start output parity failed")
    with single_writer(run):
        pause = engine(run, selected, tf, smoke=True, stop_after=1)
        finished = engine(run, selected, tf, smoke=True)
        chosen = [
            c
            for path in (run / "epochs").glob("*.json")
            for c in read_json(path)["temporal_views"]["choices"]
        ]
        if any(
            {c["requested"] for c in chosen if c["sample_id"] == r["sample_id"]}
            != set(p["temporal_views"])
            for r in selected
            if r["split_role"] == "TRAIN"
        ):
            raise ValueError("[train4096/smoke] Three cadence regimes not exercised")
        if not any(c["fallback"] for c in chosen) or any(c["headroom"] < 0 for c in chosen):
            raise ValueError("[train4096/smoke] Feasibility fallback failed")
        best = tf.keras.models.load_model(finished["best_model_path"], compile=False)
        dev = [r for r in selected if r["split_role"] == "DEV"]
        evaluated = inference(tf, best, dev)
        write_json_atomic(run / "engineering_evaluation.json", evaluated)
    report = {
        "status": "TRAIN4096_ENGINEERING_SMOKE_PASS",
        "warm_start_max_absolute_logit_difference": maximum_difference,
        "counts": dict(Counter(r["split_role"] for r in selected)),
        "pause": pause,
        "epochs": finished["epoch"],
        "resume": read_json(run / "resume_verification.json"),
        "requested_views": dict(Counter(c["requested"] for c in chosen)),
        "feasible_fallbacks": sum(c["fallback"] for c in chosen),
        "finite_loss_gradients": True,
        "native_phone_beam_evaluation": True,
        "dev_b_loaded": False,
        "test_accessed": False,
        "accuracy_claim": "NONE_ENGINEERING_ONLY",
    }
    write_json_atomic(run / "smoke.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "train", "status", "evaluate", "smoke"])
    parser.add_argument("--destination", type=Path, default=DESTINATION)
    parser.add_argument("--run-dir", type=Path, default=RUN)
    args = parser.parse_args()
    safe_run(args.run_dir)
    if args.command == "preflight":
        result = preflight(args.destination, args.run_dir)
    elif args.command == "status":
        result = {
            "data": inventory(args.destination),
            "progress": (
                read_json(args.run_dir / "progress.json")
                if (args.run_dir / "progress.json").exists()
                else None
            ),
        }
    elif args.command == "smoke":
        if not args.run_dir.name.startswith(RUN.name + "_smoke"):
            raise ValueError("[train4096/smoke] Explicit separate _smoke directory required")
        result = smoke(args.run_dir)
    else:
        with single_writer(args.run_dir):
            if args.command == "train":
                report = preflight(args.destination, args.run_dir)
                if not report["ready_to_train"]:
                    raise ValueError(
                        "[train4096/train] Materialize and validate the frozen expansion first"
                    )
                rows = load(args.destination)
                _, base = settings()
                result = engine(args.run_dir, rows, reference.tensorflow(base))
            else:
                result = final_evaluate(args.destination, args.run_dir)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
