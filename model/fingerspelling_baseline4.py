"""Opt-in capacity baseline, reusing B2 data/views/loss/metrics/checkpoint policy."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import shutil
import tempfile
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from model import fingerspelling_baseline2 as b2
from model import fingerspelling_capacity as capacity
from model import fingerspelling_ctc as reference
from model.fingerspelling_capacity_gate import decision
from model.fingerspelling_emission import balanced_score, calibrate, evaluate_views
from model.fingerspelling_fast_execution import CompiledSteps, FeatureCache
from model.fingerspelling_temporal_execution import TemporalFeatureCache
from pipeline.fingerspelling.adapter import derive, identity, sha256, subset
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import verify_raw
from pipeline.fingerspelling.temporal_views import selected_indices
from tools.fingerspelling.baseline3_analysis import character_metrics
from tools.fingerspelling.tranche import single_writer

POLICY_PATH = capacity.CONFIG
DEFAULT_DATA = b2.DEFAULT_DATA
DEFAULT_RUN = REPO / "runs/fingerspelling_ctc_baseline_04"
EVIDENCE = capacity.EVIDENCE
dataset = b2.dataset
lineage = b2.lineage
state_digest = b2.state_digest
stopping_state = b2.stopping_state
smoke_rows = b2.smoke_rows
diagnosis = b2.diagnosis
status = b2.status


def policy() -> tuple[dict[str, Any], dict[str, Any]]:
    cfg, p, base = capacity.policy()
    return p, {**base, "channels": cfg["candidate_channels"]}


def code_identity() -> dict[str, str]:
    return {
        **capacity.code_identity(),
        "model/fingerspelling_baseline4.py": sha256(REPO / "model/fingerspelling_baseline4.py"),
    }


def safe_run(run: Path) -> None:
    resolved = run.resolve()
    resolved.relative_to(REPO / "runs")
    if not resolved.name.startswith("fingerspelling_ctc_baseline_04") or resolved in {
        capacity.GATE_RUN.resolve(),
        (REPO / "runs/fingerspelling_ctc_baseline_04_gate_resume_probe").resolve(),
    }:
        raise ValueError("[baseline4/run] Dedicated B4 directory required; old/gate runs read-only")
    if resolved.parent != (REPO / "runs").resolve():
        raise ValueError("[baseline4/run] Only a direct child of runs is permitted")


def admission(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cfg, _, _ = capacity.policy()
    gate: dict[str, Any] = json.loads((EVIDENCE / "fit_gate.json").read_text())
    if (
        gate["status"] != "BASELINE4_CAPACITY_GATE_PASS"
        or not gate["full_training_authorized"]
        or gate["config_sha256"] != sha256(POLICY_PATH)
        or gate["code_sha256"] != capacity.code_identity()
        or gate["adapter"] != identity()
        or gate["data_lineage_sha256"] != lineage(capacity.diagnostic_rows(rows))
        or not gate["paired_data_order_views_updates_verified"]
    ):
        raise ValueError("[baseline4/admission] Matching passed capacity gate required")
    reports = {
        a: {
            e: json.loads((capacity.GATE_RUN / a / f"evaluations/epoch_{e:03d}.json").read_text())
            for e in cfg["fit_decision_epochs"]
        }
        for a in ["control", "candidate"]
    }
    if not decision(reports, cfg)["full_training_authorized"]:
        raise ValueError("[baseline4/admission] Gate metric evidence no longer passes")
    for arm in ["control", "candidate"]:
        if (
            sha256(capacity.GATE_RUN / arm / "final.keras")
            != gate["arms"][arm]["checkpoint_sha256"]
        ):
            raise ValueError("[baseline4/admission] Gate checkpoint changed")
    return gate


def run_identity(output: Path, rows: list[dict[str, Any]], smoke: bool) -> dict[str, Any]:
    p, base = policy()
    return {
        "schema_version": "apphear.fingerspelling.baseline4_run.v1",
        "policy": p,
        "base_config": base,
        "policy_sha256": sha256(POLICY_PATH),
        "adapter": identity(),
        "code_sha256": code_identity(),
        "manifest_sha256": sha256(output / "tranche_manifest.json"),
        "dataset_lineage_sha256": lineage(rows),
        "capacity_gate_sha256": sha256(EVIDENCE / "fit_gate.json"),
        "diagnostic_manifest_sha256": capacity.policy()[0]["diagnostic_manifest_sha256"],
        "smoke_only": smoke,
        "sample_ids": [r["sample_id"] for r in rows],
        "test_accessed": False,
        "initialization": "FRESH_NOT_FIT_GATE_FINETUNING",
    }


def preflight(output: Path, run: Path) -> dict[str, Any]:
    safe_run(run)
    p, base = policy()
    rows = dataset(output, full=True)
    admission(rows)
    run.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=run.parent) as stream:
        stream.write(b"baseline4 writable probe")
    result = {
        "status": "BASELINE4_PREFLIGHT_PASS",
        "counts": dict(Counter(r["split_role"] for r in rows)),
        "adapter": identity(),
        "config_sha256": sha256(POLICY_PATH),
        "dataset_lineage_sha256": lineage(rows),
        "code_sha256": code_identity(),
        "tensorflow_installed": importlib.metadata.version("tensorflow"),
        "free_bytes": shutil.disk_usage(run.parent).free,
        "candidate_parameters": capacity.policy()[0]["candidate_parameters"],
        "cpu_threads": base["cpu_threads"],
        "full_dataset_validation": True,
        "test_accessed": False,
    }
    write_json_atomic(EVIDENCE / "preflight.json", result)
    return result


def add_characters(views: dict[str, Any]) -> None:
    for value in views.values():
        value["characters"] = character_metrics(value["predictions"])


def engine(
    output: Path,
    run: Path,
    rows: list[dict[str, Any]],
    tf: Any,
    smoke: bool = False,
    stop_after: int | None = None,
) -> dict[str, Any]:
    safe_run(run)
    p, base = policy()
    rid = run_identity(output, rows, smoke)
    run.mkdir(parents=True, exist_ok=True)
    identity_path = run / "run_identity.json"
    if identity_path.is_file():
        if json.loads(identity_path.read_text()) != rid:
            raise ValueError(
                "[baseline4/resume] Config/code/data identity changed; refusing mixed run"
            )
    elif any(run.iterdir()):
        raise ValueError("[baseline4/run] Nonempty unowned run directory refused")
    else:
        write_json_atomic(identity_path, rid)
    tf.keras.utils.set_random_seed(p["seed"])
    model = capacity.build_model(tf)
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
        state = json.loads(state_path.read_text())
        checkpoint.restore(state["checkpoint"]).assert_existing_objects_matched()
        if (
            int(epoch_var.numpy()) != state["epoch"]
            or state_digest(model, optimizer) != state["model_optimizer_sha256"]
        ):
            raise ValueError("[baseline4/resume] Restored weights/Adam/epoch mismatch")
        write_json_atomic(
            run / "resume_verification.json",
            {
                "restored_epoch": state["epoch"],
                "model_optimizer_exactly_restored": True,
                "optimizer_iterations": int(optimizer.iterations.numpy()),
                "early_stopping_state": {
                    k: state[k] for k in ["patience_anchor", "non_improving_epochs"]
                },
                "bit_exact_continuation_claim": False,
            },
        )
        with (run / "resume_history.jsonl").open("a", encoding="utf-8") as history:
            history.write(
                json.dumps(json.loads((run / "resume_verification.json").read_text())) + "\n"
            )
    elif manager.latest_checkpoint:
        raise ValueError("[baseline4/resume] Uncommitted checkpoint requires review")
    maximum = p["smoke_epochs"] if smoke else p["maximum_epochs"]
    train_rows = [r for r in rows if r["split_role"] == "TRAIN"]
    dev_rows = [r for r in rows if r["split_role"] == "DEV"]
    cache, steps = TemporalFeatureCache(p), CompiledSteps(tf, model, optimizer)
    write_json_atomic(
        run / "environment.json",
        {
            "tensorflow": tf.__version__,
            "keras": tf.keras.__version__,
            "parameters": model.count_params(),
            "cpu_only": True,
            "resume_granularity": "Committed epochs; interrupted epoch repeated",
            "bit_exact_continuation_claim": False,
            "fresh_initialization_not_fit_gate_finetuning": True,
        },
    )
    train_diagnostic = train_rows if smoke else capacity.diagnostic_rows(rows)
    try:
        if state["epoch"] < maximum and not (
            not smoke
            and state["epoch"] >= p["minimum_epochs"]
            and state["non_improving_epochs"] >= p["patience"]
        ):
            for epoch in range(state["epoch"], maximum):
                started = time.perf_counter()
                order = np.random.default_rng(p["seed"] + epoch).permutation(len(train_rows))
                losses, choices = [], []
                for start in range(0, len(order), base["batch_size"]):
                    batch = [train_rows[i] for i in order[start : start + base["batch_size"]]]
                    tensors, picked = cache.training_batch(batch, epoch)
                    if steps.update is None:
                        raise RuntimeError("[baseline4/train] Optimizer missing")
                    value = float(steps.update(*tensors).numpy())
                    if not np.isfinite(value):
                        raise ValueError("[baseline4/train] Non-finite loss")
                    losses.append((value, len(batch)))
                    choices.extend(picked)
                train_seconds = time.perf_counter() - started
                views, _, view_seconds = evaluate_views(
                    tf, steps, cache, dev_rows, p, base["batch_size"]
                )
                add_characters(views)
                train_views, _, train_view_seconds = evaluate_views(
                    tf, steps, cache, train_diagnostic, p, base["batch_size"]
                )
                add_characters(train_views)
                score = balanced_score(views)
                if state["best_combined_cer"] is None or score < state["best_combined_cer"]:
                    best_path = run / "best_candidates" / f"epoch_{epoch + 1:03d}.keras"
                    best_path.parent.mkdir(exist_ok=True)
                    model.save(best_path)
                    state.update(
                        best_combined_cer=score,
                        best_model_path=str(best_path),
                        best_epoch=epoch + 1,
                        best_model_sha256=sha256(best_path),
                    )
                state.update(stopping_state(state, score, p))
                report: dict[str, Any] = {
                    "schema_version": "apphear.fingerspelling.baseline4_epoch.v1",
                    "epoch": epoch + 1,
                    "train_mean_ctc": sum(a * n for a, n in losses) / sum(n for _, n in losses),
                    "combined_uncalibrated_dev_cer": score,
                    "dev": views,
                    "train_diagnostic": train_views,
                    "temporal_views": {
                        "requested_counts": dict(Counter(c["requested"] for c in choices)),
                        "actual_counts": dict(Counter(c["actual"] for c in choices)),
                        "fallback_count": sum(c["fallback"] for c in choices),
                        "choices": choices,
                        "all_fit_sources_retained": len(choices) == len(train_rows),
                    },
                    "timings": {
                        "train_seconds": train_seconds,
                        "dev_seconds": view_seconds,
                        "train_diagnostic_seconds": train_view_seconds,
                    },
                    "cache_bytes": cache.bytes,
                    "test_accessed": False,
                    "smoke_only": smoke,
                }
                write_json_atomic(run / "epochs" / f"epoch_{epoch + 1:03d}.json", report)
                epoch_var.assign(epoch + 1)
                saved = manager.save(checkpoint_number=epoch + 1)
                state.update(
                    epoch=epoch + 1,
                    checkpoint=saved,
                    model_optimizer_sha256=state_digest(model, optimizer),
                    optimizer_iterations=int(optimizer.iterations.numpy()),
                )
                write_json_atomic(state_path, state)
                report["timings"]["epoch_seconds"] = time.perf_counter() - started
                write_json_atomic(run / "epochs" / f"epoch_{epoch + 1:03d}.json", report)
                progress = {
                    "epoch": epoch + 1,
                    "train_ctc": report["train_mean_ctc"],
                    "native_dev_cer": views["native"]["metrics"]["cer"],
                    "native_train_diagnostic_cer": train_views["native"]["metrics"]["cer"],
                    "phone_train_diagnostic_cer": train_views["phone"]["metrics"]["cer"],
                    "phone_dev_cer": views["phone"]["metrics"]["cer"],
                    "combined_dev_cer": score,
                    "best_combined_dev_cer": state["best_combined_cer"],
                    "non_improving_epochs": state["non_improving_epochs"],
                    "epoch_seconds": report["timings"]["epoch_seconds"],
                    "requested_views": report["temporal_views"]["requested_counts"],
                    "fallbacks": report["temporal_views"]["fallback_count"],
                }
                write_json_atomic(run / "progress.json", progress)
                print(json.dumps(progress), flush=True)
                if stop_after is not None and state["epoch"] >= stop_after:
                    return {"status": "ENGINEERING_PAUSE", "epoch": state["epoch"]}
                if (
                    not smoke
                    and state["epoch"] >= p["minimum_epochs"]
                    and state["non_improving_epochs"] >= p["patience"]
                ):
                    break
        completion = {
            "status": "BASELINE4_SMOKE_COMPLETE" if smoke else "BASELINE4_TRAINING_COMPLETE",
            "epochs": state["epoch"],
            "maximum_epochs": maximum,
            "stop_reason": (
                "MAXIMUM_EPOCHS" if state["epoch"] >= maximum else "FROZEN_EARLY_STOPPING"
            ),
            "best_epoch": state["best_epoch"],
            "best_model_path": state["best_model_path"],
            "best_model_sha256": state["best_model_sha256"],
            "best_combined_dev_cer": state["best_combined_cer"],
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
                    json.loads(state_path.read_text())["epoch"] if state_path.exists() else 0
                ),
                "resume": "Rerun identical train command; interrupted epoch is repeated",
            },
        )
        raise


def smoke(output: Path, run: Path) -> dict[str, Any]:
    p, base = policy()
    all_rows = dataset(output)
    admission(all_rows)
    rows = smoke_rows(all_rows, p)
    cache = TemporalFeatureCache(p)
    parity = []
    for r in rows:
        raw = verify_raw(REPO / r["raw_path"], REPO / r["raw_receipt_path"], r, r["source_sha256"])
        cache.register(r)
        for view in p["temporal_views"]:
            indices = selected_indices(raw, view, p)
            actual = derive(subset(raw, indices))
            if not np.array_equal(actual, cache.load(r, view)[0]):
                raise ValueError("[baseline4/smoke] Stored/native or selected-view parity mismatch")
        parity.append(r["sample_id"])
    tf = reference.tensorflow(base)
    with single_writer(run):
        first = engine(output, run, rows, tf, smoke=True, stop_after=1)
        restored = engine(output, run, rows, tf, smoke=True)
        reports = [json.loads(path.read_text()) for path in sorted((run / "epochs").glob("*.json"))]
        train = [r for r in rows if r["split_role"] == "TRAIN"]
        choices = [c for r in reports for c in r["temporal_views"]["choices"]]
        for rec in train:
            if {c["requested"] for c in choices if c["sample_id"] == rec["sample_id"]} != set(
                p["temporal_views"]
            ):
                raise ValueError("[baseline4/smoke] Cadence variation missing")
        if not any(c["fallback"] for c in choices) or any(c["headroom"] < 0 for c in choices):
            raise ValueError("[baseline4/smoke] Feasibility fallback not demonstrated")
        eval_report = final_evaluate(output, run, tf=tf, rows=rows)
    result = {
        "schema_version": "apphear.fingerspelling.baseline4_smoke.v1",
        "status": "BASELINE4_SMOKE_PASS",
        "policy_sha256": sha256(POLICY_PATH),
        "code_sha256": code_identity(),
        "ids": parity,
        "counts": dict(Counter(r["split_role"] for r in rows)),
        "native_phone_bit_exact_adapter_parity": True,
        "intermediate_recomputed_from_raw": True,
        "pause": first,
        "completion": restored,
        "resume_verification": json.loads((run / "resume_verification.json").read_text()),
        "resume_history": [
            json.loads(line) for line in (run / "resume_history.jsonl").read_text().splitlines()
        ],
        "requested_counts": dict(Counter(c["requested"] for c in choices)),
        "fallbacks": sum(c["fallback"] for c in choices),
        "finite_gradients_loss": True,
        "final_evaluation_status": eval_report["status"],
        "accuracy_claim": "NONE_ENGINEERING_ONLY",
        "test_accessed": False,
    }
    write_json_atomic(EVIDENCE / "smoke.json", result)
    return result


def final_evaluate(
    output: Path, run: Path, tf: Any = None, rows: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    p, base = policy()
    rid = json.loads((run / "run_identity.json").read_text())
    if rows is None:
        rows = dataset(output)
    if rid != run_identity(output, rows, rid["smoke_only"]):
        raise ValueError("[baseline4/eval] Run/data/code identity mismatch")
    completion = json.loads((run / "completion.json").read_text())
    model_path = Path(completion["best_model_path"])
    if sha256(model_path) != completion["best_model_sha256"]:
        raise ValueError("[baseline4/eval] Best checkpoint hash mismatch")
    if tf is None:
        tf = reference.tensorflow(base)
    model = tf.keras.models.load_model(model_path)
    views, logits, times = evaluate_views(
        tf,
        CompiledSteps(tf, model),
        FeatureCache(),
        [r for r in rows if r["split_role"] == "DEV"],
        p,
        base["batch_size"],
    )
    if balanced_score(views) != completion["best_combined_dev_cer"]:
        raise ValueError("[baseline4/eval] Best checkpoint restored metric mismatch")
    add_characters(views)
    train_views, _, train_times = evaluate_views(
        tf,
        CompiledSteps(tf, model),
        FeatureCache(),
        (
            [r for r in rows if r["split_role"] == "TRAIN"]
            if rid["smoke_only"]
            else capacity.diagnostic_rows(rows)
        ),
        p,
        base["batch_size"],
    )
    add_characters(train_views)
    calibration = calibrate(logits, p, diagnosis(p, output)["blank_calibration_supported"])
    for candidate in calibration["candidates"]:
        add_characters(candidate["views"])
    b2_final = json.loads((b2.DEFAULT_RUN / "final_evaluation.json").read_text())
    b2_train = json.loads(
        (REPO / "artifacts/fingerspelling_baseline3/train_dev_decoding.json").read_text()
    )
    comparison = (
        {
            v: {
                "b2_raw_dev_cer": b2_final["uncalibrated"][v]["metrics"]["cer"],
                "b4_raw_dev_cer": views[v]["metrics"]["cer"],
                "b2_train64_cer": b2_train["train"][v]["metrics"]["cer"],
                "b4_train64_cer": train_views[v]["metrics"]["cer"],
            }
            for v in ["native", "phone"]
        }
        if not rid["smoke_only"]
        else {"engineering_smoke_not_performance_comparison": True}
    )
    report = {
        "schema_version": "apphear.fingerspelling.baseline4_final.v1",
        "status": "BASELINE4_FINAL_EVALUATED",
        "best_epoch": completion["best_epoch"],
        "checkpoint_sha256": sha256(model_path),
        "policy_sha256": sha256(POLICY_PATH),
        "adapter": identity(),
        "dataset_lineage_sha256": rid["dataset_lineage_sha256"],
        "uncalibrated": views,
        "train_diagnostic": train_views,
        "train_diagnostic_timings": train_times,
        "baseline2_comparison": comparison,
        "calibration": calibration,
        "timings": times,
        "test_accessed": False,
        "production_promoted": False,
        "smoke_only": rid["smoke_only"],
        "evaluation_scope": "SIGNER_DISJOINT_DEV_SEQUENCE_DIAGNOSTIC_NOT_PHONE_END_TO_END_ACCURACY",
    }
    write_json_atomic(run / "final_evaluation.json", report)
    write_json_atomic(
        run / "decoder_calibration.json",
        {
            "schema_version": "apphear.fingerspelling.blank_calibration.v1",
            "blank_index": 27,
            "subtract_from_blank_logit": calibration["selected_penalty"],
            "checkpoint_sha256": sha256(model_path),
            "policy_sha256": sha256(POLICY_PATH),
            "selection": "DEV_ONLY_AFTER_UNCALIBRATED_CHECKPOINT_SELECTION",
        },
    )
    return {
        "status": report["status"],
        "best_epoch": report["best_epoch"],
        "uncalibrated_combined_cer": balanced_score(views),
        "selected_blank_penalty": calibration["selected_penalty"],
        "calibrated_combined_cer": calibration["selected_combined_cer"],
        "report": str(run / "final_evaluation.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "smoke", "train", "status", "evaluate"])
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument(
        "--pause-after", type=int, default=None, help="Engineering smoke pause only"
    )
    args = parser.parse_args()
    output, run = args.dataset.resolve(), args.run_dir.resolve()
    output.relative_to(REPO)
    safe_run(run)
    if args.pause_after is not None and args.command != "smoke":
        parser.error("--pause-after is restricted to engineering smoke")
    if args.command == "status":
        result = status(run)
    elif args.command == "preflight":
        result = preflight(output, run)
    elif args.command == "smoke":
        if run == DEFAULT_RUN.resolve():
            raise ValueError("[baseline4/smoke] Use an independent smoke --run-dir")
        if args.pause_after is not None:
            p, base = policy()
            all_rows = dataset(output)
            admission(all_rows)
            with single_writer(run):
                result = engine(
                    output,
                    run,
                    smoke_rows(all_rows, p),
                    reference.tensorflow(base),
                    smoke=True,
                    stop_after=args.pause_after,
                )
        else:
            result = smoke(output, run)
    elif args.command == "evaluate":
        with single_writer(run):
            result = final_evaluate(output, run)
    else:
        with single_writer(run):
            preflight(output, run)
            evidence = json.loads((EVIDENCE / "smoke.json").read_text())
            if (
                evidence["status"] != "BASELINE4_SMOKE_PASS"
                or evidence["code_sha256"] != code_identity()
                or evidence["policy_sha256"] != sha256(POLICY_PATH)
            ):
                raise ValueError("[baseline4/train] Matching passed engineering smoke required")
            p, base = policy()
            result = engine(output, run, dataset(output), reference.tensorflow(base))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
