"""One opt-in stable-hand TCN/CTC experiment. Full training is user-run only."""

from __future__ import annotations

import argparse
import json
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any, cast

import numpy as np

from model import fingerspelling_baseline2 as b2
from model import fingerspelling_ctc as reference
from model.fingerspelling_emission import balanced_score, calibrate, evaluate_views
from model.fingerspelling_v2_execution import Cache, Steps, build_model
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.adapter_v2 import identity
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.package_v2 import (
    DEFAULT,
    parents,
    prepare,
    temporal_identity,
    validate,
)
from pipeline.fingerspelling.sequence_manifest import REPO
from tools.fingerspelling.baseline3_analysis import character_metrics
from tools.fingerspelling.tranche import single_writer

CONFIG_PATH = REPO / "model/config/fingerspelling_ctc_baseline_03.json"
OUT = REPO / "artifacts/fingerspelling_baseline3"
DEFAULT_RUN = REPO / "runs/fingerspelling_ctc_baseline_03"


def records() -> list[dict[str, Any]]:
    return [
        json.loads(p.read_text()) for p in sorted((DEFAULT / "features").glob("*.receipt.json"))
    ]


def code_identity() -> dict[str, str]:
    names = [
        "model/fingerspelling_baseline3.py",
        "model/fingerspelling_v2_execution.py",
        "pipeline/fingerspelling/package_v2.py",
        "tools/fingerspelling/baseline3_analysis.py",
    ]
    return {n: sha256(REPO / n) for n in names}


def run_identity(rows: list[dict[str, Any]], smoke: bool) -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text())
    p, base = b2.policy()
    if (
        config["schema_version"] != "apphear.fingerspelling.baseline3.v1"
        or sha256(b2.POLICY_PATH) != config["baseline2_policy_sha256"]
        or config["feature_width"] != 255
        or config["capacity"] != "UNCHANGED_64_CHANNELS"
    ):
        raise ValueError("[baseline3/identity] Policy/architecture mismatch")
    return {
        "schema_version": "apphear.fingerspelling.baseline3_run.v1",
        "config": config,
        "config_sha256": sha256(CONFIG_PATH),
        "policy": p,
        "base_model": base,
        "adapter": identity(),
        "temporal": temporal_identity(),
        "code_sha256": code_identity(),
        "dataset_lineage_sha256": b2.lineage(rows),
        "sample_ids": [r["sample_id"] for r in rows],
        "smoke_only": smoke,
        "test_accessed": False,
        "seed": p["seed"],
    }


def preflight(run: Path) -> dict[str, Any]:
    b2.safe_run(run)
    if run.resolve() == b2.DEFAULT_RUN.resolve():
        raise ValueError("[baseline3/run] Baseline2 read-only")
    b2.dataset(b2.DEFAULT_DATA, full=True)
    report = validate(DEFAULT)
    if not report["ready_to_train"]:
        raise ValueError(
            "[baseline3/data] V2 preparation incomplete: "
            + str(report["counts"])
            + str(report["errors"])
        )
    parity = json.loads((OUT / "parity/parity.json").read_text())
    if (
        parity["status"] != "CANONICAL_V2_JVM_PARITY_PASS"
        or parity["adapter"] != identity()
        or parity["kotlin_sha256"] != sha256(REPO / "tools/fingerspelling/CanonicalParity.kt")
    ):
        raise ValueError("[baseline3/parity] Current reference parity required")
    report.update(status="BASELINE3_PREFLIGHT_PASS", run_identity=run_identity(records(), False))
    write_json_atomic(OUT / "preflight.json", report)
    return {k: v for k, v in report.items() if k not in {"run_identity", "pending_ids"}}


def evaluate(
    tf: Any, model: Any, cache: Cache, rows: list[dict[str, Any]]
) -> tuple[dict[str, Any], Any, dict[str, float]]:
    p, base = b2.policy()
    # Existing evaluator consumes this small protocol; no v1 geometry/cache implementation is used.
    views, logits, times = evaluate_views(
        tf, cast(Any, Steps(tf, model)), cast(Any, cache), rows, p, base["batch_size"]
    )
    for view in views.values():
        view["characters"] = character_metrics(view["predictions"])
    return views, logits, times


def engine(
    run: Path, rows: list[dict[str, Any]], tf: Any, smoke: bool = False, pause: int | None = None
) -> dict[str, Any]:
    b2.safe_run(run)
    if run.resolve() == b2.DEFAULT_RUN.resolve():
        raise ValueError("[baseline3/run] Baseline2 read-only")
    p, base = b2.policy()
    rid = run_identity(rows, smoke)
    run.mkdir(parents=True, exist_ok=True)
    ip = run / "run_identity.json"
    if ip.exists():
        if json.loads(ip.read_text()) != rid:
            raise ValueError("[baseline3/resume] Dataset/code/config changed")
    elif any(run.iterdir()):
        raise ValueError("[baseline3/run] Unowned nonempty folder")
    else:
        write_json_atomic(ip, rid)
    tf.keras.utils.set_random_seed(p["seed"])
    model = build_model(tf, base)
    optimizer = tf.keras.optimizers.Adam(base["learning_rate"], clipnorm=base["gradient_clip_norm"])
    optimizer.build(model.trainable_variables)
    ev = tf.Variable(0, trainable=False, dtype=tf.int64)
    ckpt = tf.train.Checkpoint(model=model, optimizer=optimizer, epoch=ev)
    manager = tf.train.CheckpointManager(
        ckpt, str(run / "checkpoints"), max_to_keep=base["checkpoint_keep"]
    )
    sp = run / "committed_epoch.json"
    state: dict[str, Any] = {
        "epoch": 0,
        "best_combined_cer": None,
        "best_model_path": None,
        "patience_anchor": None,
        "non_improving_epochs": 0,
    }
    if sp.exists():
        state = json.loads(sp.read_text())
        ckpt.restore(state["checkpoint"]).assert_existing_objects_matched()
        if (
            int(ev.numpy()) != state["epoch"]
            or b2.state_digest(model, optimizer) != state["model_optimizer_sha256"]
        ):
            raise ValueError("[baseline3/resume] Model/Adam/epoch restore mismatch")
        write_json_atomic(
            run / "resume_verification.json",
            {
                "restored_epoch": state["epoch"],
                "exact_model_optimizer_restore": True,
                "optimizer_iterations": int(optimizer.iterations.numpy()),
                "early_stop_state": {
                    k: state[k] for k in ["patience_anchor", "non_improving_epochs"]
                },
                "bit_exact_continuation_claim": False,
            },
        )
    elif manager.latest_checkpoint:
        raise ValueError("[baseline3/resume] Uncommitted checkpoint needs review")
    train = [r for r in rows if r["split_role"] == "TRAIN"]
    dev = [r for r in rows if r["split_role"] == "DEV"]
    maximum = p["smoke_epochs"] if smoke else p["maximum_epochs"]
    cache = Cache(p)
    steps = Steps(tf, model, optimizer)
    write_json_atomic(
        run / "environment.json",
        {
            "tensorflow": tf.__version__,
            "parameters": model.count_params(),
            "cpu_threads": base["cpu_threads"],
            "input_width": 255,
            "same_layer_configuration_as_b2": True,
            "fresh_initialization": True,
            "resume_granularity": "COMMITTED_EPOCHS",
            "bit_exact_continuation_claim": False,
        },
    )
    try:
        stopped = (
            not smoke
            and state["epoch"] >= p["minimum_epochs"]
            and state["non_improving_epochs"] >= p["patience"]
        )
        for epoch in range(state["epoch"], maximum) if not stopped else []:
            started = time.perf_counter()
            losses = []
            choices = []
            order = np.random.default_rng(p["seed"] + epoch).permutation(len(train))
            for start in range(0, len(order), base["batch_size"]):
                batch = [train[i] for i in order[start : start + base["batch_size"]]]
                tensors, picked = cache.training_batch(batch, epoch)
                if steps.update is None:
                    raise RuntimeError("[baseline3/train] Missing optimizer")
                loss = float(steps.update(*tensors).numpy())
                losses.append((loss, len(batch)))
                choices.extend(picked)
            train_seconds = time.perf_counter() - started
            views, _, times = evaluate(tf, model, cache, dev)
            score = balanced_score(views)
            if state["best_combined_cer"] is None or score < state["best_combined_cer"]:
                path = run / "best_candidates" / f"epoch_{epoch+1:03d}.keras"
                path.parent.mkdir(exist_ok=True)
                model.save(path)
                state.update(
                    best_combined_cer=score,
                    best_model_path=str(path),
                    best_model_sha256=sha256(path),
                    best_epoch=epoch + 1,
                )
            state.update(b2.stopping_state(state, score, p))
            report: dict[str, Any] = {
                "schema_version": "apphear.fingerspelling.baseline3_epoch.v1",
                "epoch": epoch + 1,
                "train_mean_ctc": sum(a * n for a, n in losses) / sum(n for a, n in losses),
                "combined_uncalibrated_dev_cer": score,
                "dev": views,
                "temporal_choices": choices,
                "test_accessed": False,
                "smoke_only": smoke,
                "timings": {"train_seconds": train_seconds, "dev_seconds": times},
            }
            path = run / "epochs" / f"epoch_{epoch+1:03d}.json"
            write_json_atomic(path, report)
            ev.assign(epoch + 1)
            saved = manager.save(checkpoint_number=epoch + 1)
            state.update(
                epoch=epoch + 1,
                checkpoint=saved,
                model_optimizer_sha256=b2.state_digest(model, optimizer),
                optimizer_iterations=int(optimizer.iterations.numpy()),
            )
            write_json_atomic(sp, state)
            report["timings"]["epoch_seconds"] = time.perf_counter() - started
            write_json_atomic(path, report)
            progress = {
                "epoch": epoch + 1,
                "train_ctc": report["train_mean_ctc"],
                "native_dev_cer": views["native"]["metrics"]["cer"],
                "phone_dev_cer": views["phone"]["metrics"]["cer"],
                "combined_dev_cer": score,
                "best_combined_dev_cer": state["best_combined_cer"],
                "non_improving_epochs": state["non_improving_epochs"],
                "requested_views": dict(Counter(c["requested"] for c in choices)),
                "fallbacks": sum(c["fallback"] for c in choices),
                "epoch_seconds": report["timings"]["epoch_seconds"],
            }
            write_json_atomic(run / "progress.json", progress)
            print(json.dumps(progress), flush=True)
            if pause is not None and epoch + 1 >= pause:
                return {"status": "ENGINEERING_PAUSE", "epoch": epoch + 1}
            if (
                not smoke
                and epoch + 1 >= p["minimum_epochs"]
                and state["non_improving_epochs"] >= p["patience"]
            ):
                break
        result = {
            "status": "BASELINE3_SMOKE_COMPLETE" if smoke else "BASELINE3_TRAINING_COMPLETE",
            "epochs": state["epoch"],
            "best_epoch": state["best_epoch"],
            "best_model_path": state["best_model_path"],
            "best_model_sha256": state["best_model_sha256"],
            "best_combined_dev_cer": state["best_combined_cer"],
            "stop_reason": (
                "MAXIMUM_EPOCHS" if state["epoch"] >= maximum else "FROZEN_EARLY_STOPPING"
            ),
            "test_accessed": False,
            "production_promoted": False,
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
                "last_committed_epoch": json.loads(sp.read_text())["epoch"] if sp.exists() else 0,
            },
        )
        raise


def final_evaluate(
    run: Path, tf: Any = None, rows: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    rid = json.loads((run / "run_identity.json").read_text())
    rows = records() if rows is None else rows
    if rid != run_identity(rows, rid["smoke_only"]):
        raise ValueError("[baseline3/eval] Identity mismatch")
    c = json.loads((run / "completion.json").read_text())
    p, base = b2.policy()
    path = Path(c["best_model_path"])
    if sha256(path) != c["best_model_sha256"]:
        raise ValueError("[baseline3/eval] Checkpoint hash mismatch")
    tf = reference.tensorflow(base) if tf is None else tf
    model = tf.keras.models.load_model(path)
    views, logits, times = evaluate(
        tf, model, Cache(p), [r for r in rows if r["split_role"] == "DEV"]
    )
    if balanced_score(views) != c["best_combined_dev_cer"]:
        raise ValueError("[baseline3/eval] Restored score mismatch")
    calibration = calibrate(logits, p, True)
    for candidate in calibration["candidates"]:
        for v in candidate["views"].values():
            v["characters"] = character_metrics(v["predictions"])
    report = {
        "schema_version": "apphear.fingerspelling.baseline3_final.v1",
        "status": "BASELINE3_FINAL_EVALUATED",
        "best_epoch": c["best_epoch"],
        "checkpoint_sha256": sha256(path),
        "uncalibrated": views,
        "calibration": calibration,
        "timings": times,
        "adapter": identity(),
        "dataset_lineage_sha256": rid["dataset_lineage_sha256"],
        "smoke_only": rid["smoke_only"],
        "test_accessed": False,
        "phone_end_to_end_accuracy_claim": False,
    }
    write_json_atomic(run / "final_evaluation.json", report)
    write_json_atomic(
        run / "decoder_calibration.json",
        {
            "blank_index": 27,
            "subtract_from_blank_logit": calibration["selected_penalty"],
            "checkpoint_sha256": sha256(path),
            "run_config_sha256": sha256(CONFIG_PATH),
            "selection": "DEV_ONLY_AFTER_RAW_CHECKPOINT_SELECTION",
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


def smoke(run: Path) -> dict[str, Any]:
    if run.resolve() == DEFAULT_RUN.resolve():
        raise ValueError("[baseline3/smoke] Separate run folder required")
    p, base = b2.policy()
    original = b2.smoke_rows(b2.dataset(b2.DEFAULT_DATA), p)
    for r in original:
        prepare_one_for_smoke(r)
    by_id = {r["sample_id"]: r for r in records()}
    rows = [by_id[r["sample_id"]] for r in original]
    tf = reference.tensorflow(base)
    with single_writer(run):
        first = engine(run, rows, tf, True, 1)
        completion = engine(run, rows, tf, True)
        evaluation = final_evaluate(run, tf, rows)
    reports = [json.loads(p.read_text()) for p in sorted((run / "epochs").glob("*.json"))]
    choices = [c for r in reports for c in r["temporal_choices"]]
    for r in rows:
        if r["split_role"] == "TRAIN" and {
            c["requested"] for c in choices if c["sample_id"] == r["sample_id"]
        } != set(p["temporal_views"]):
            raise ValueError("[baseline3/smoke] Missing regime variation")
    if any(c["headroom"] < 0 for c in choices) or not any(c["fallback"] for c in choices):
        raise ValueError("[baseline3/smoke] Feasibility fallback not tested")
    result = {
        "status": "BASELINE3_SMOKE_PASS",
        "adapter": identity(),
        "code_sha256": code_identity(),
        "ids": [r["sample_id"] for r in rows],
        "pause": first,
        "completion": completion,
        "evaluation": evaluation,
        "resume": json.loads((run / "resume_verification.json").read_text()),
        "requested_counts": dict(Counter(c["requested"] for c in choices)),
        "fallbacks": sum(c["fallback"] for c in choices),
        "finite_gradients_loss": True,
        "engineering_only": True,
        "test_accessed": False,
    }
    write_json_atomic(OUT / "smoke.json", result)
    return result


def prepare_one_for_smoke(rec: dict[str, Any]) -> None:
    from pipeline.fingerspelling.package_v2 import prepare_one

    parent = next(r for r in parents() if r["sample_id"] == rec["sample_id"])
    prepare_one(DEFAULT, parent)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["prepare", "preflight", "train", "status", "evaluate", "smoke"]
    )
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    a = parser.parse_args()
    run = a.run_dir.resolve()
    b2.safe_run(run)
    if run == b2.DEFAULT_RUN.resolve():
        raise ValueError("[baseline3/run] Baseline2 read-only")
    if a.command == "prepare":
        result = prepare()
    elif a.command == "preflight":
        result = preflight(run)
    elif a.command == "smoke":
        result = smoke(run)
    elif a.command == "status":
        result = b2.status(run)
    elif a.command == "evaluate":
        with single_writer(run):
            result = final_evaluate(run)
    else:
        with single_writer(run):
            preflight(run)
            e = json.loads((OUT / "smoke.json").read_text())
            if (
                e["status"] != "BASELINE3_SMOKE_PASS"
                or e["adapter"] != identity()
                or e["code_sha256"] != code_identity()
            ):
                raise ValueError("[baseline3/train] Matching smoke required")
            p, base = b2.policy()
            result = engine(run, records(), reference.tensorflow(base))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
