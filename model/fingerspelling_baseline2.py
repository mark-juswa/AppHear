"""Controlled cadence-aware extension of the existing fingerspelling TCN/CTC pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any, cast

import numpy as np

from model import fingerspelling_ctc as reference
from model.fingerspelling_emission import balanced_score, calibrate, evaluate_views
from model.fingerspelling_fast_execution import CompiledSteps, FeatureCache
from model.fingerspelling_temporal_execution import TemporalFeatureCache
from pipeline.fingerspelling.adapter import derive, identity, sha256, subset
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import validate, verify_raw
from pipeline.fingerspelling.temporal_views import selected_indices
from tools.fingerspelling.tranche import single_writer

POLICY_PATH = REPO / "model/config/fingerspelling_ctc_baseline_02.json"
DEFAULT_DATA = REPO / "datasets/fingerspelling/foundation_01"
DEFAULT_RUN = REPO / "runs/fingerspelling_ctc_baseline_02"
EVIDENCE = REPO / "artifacts/fingerspelling_baseline2"


def policy() -> tuple[dict[str, Any], dict[str, Any]]:
    p = json.loads(POLICY_PATH.read_text())
    path = REPO / p["base_model_config"]
    if sha256(path) != p["base_model_config_sha256"]:
        raise ValueError("[baseline2/config] Frozen baseline architecture/config changed")
    base = reference.configuration(path)
    if (
        p["schema_version"] != "apphear.fingerspelling.baseline2.v1"
        or p["temporal_views"] != ["native", "intermediate", "phone"]
        or p["selection"] != "MEAN_UNCALIBRATED_NATIVE_PHONE_DEV_CER_FIRST_TIE"
        or p["blank_penalties"] != [0, 0.5, 1, 1.5, 2]
        or p["phone_hz"] != 6.231166
        or p["seed"] != base["seed"]
    ):
        raise ValueError("[baseline2/config] Frozen policy mismatch")
    return p, base


def dataset(output: Path, full: bool = False) -> list[dict[str, Any]]:
    pinned = json.loads((REPO / "pipeline/config/fingerspelling_execution_v1.json").read_text())
    if sha256(output / "tranche_manifest.json") != pinned["frozen_manifest_sha256"]:
        raise ValueError("[baseline2/data] Frozen manifest changed")
    report = (
        validate(output, output / "tranche_manifest.json")
        if full
        else json.loads((output / "validation.json").read_text())
    )
    if not report["ready_to_train"] or report["adapter"] != identity():
        raise ValueError("[baseline2/data] Complete valid frozen tranche required")
    rows = cast(list[dict[str, Any]], reference.records(output))
    manifest = json.loads((output / "tranche_manifest.json").read_text())
    by_id = {r["sample_id"]: r for r in manifest["samples"]}
    if len(rows) != 1280 or {r["sample_id"] for r in rows} != set(by_id):
        raise ValueError("[baseline2/data] Unexpected feature inventory")
    adapter_id = identity()
    for rec in rows:
        official = by_id[rec["sample_id"]]
        if any(
            rec[k] != official[k]
            for k in [
                "split_role",
                "official_signer_id",
                "normalized_transcript",
                "ctc_min_timesteps",
            ]
        ):
            raise ValueError("[baseline2/data] Role/identity/transcript changed")
        if (
            rec["adapter"] != adapter_id
            or rec["manifest_sha256"] != pinned["frozen_manifest_sha256"]
        ):
            raise ValueError("[baseline2/data] Receipt identity changed")
    signers = {
        role: {r["official_signer_id"] for r in rows if r["split_role"] == role}
        for role in ["TRAIN", "DEV"]
    }
    if signers["TRAIN"] & signers["DEV"] or Counter(r["split_role"] for r in rows) != {
        "TRAIN": 1024,
        "DEV": 256,
    }:
        raise ValueError("[baseline2/data] Split leakage or role count mismatch")
    return rows


def lineage(rows: list[dict[str, Any]]) -> str:
    ids = {
        r["sample_id"]: {k: r[k] for k in ["features_sha256", "raw_sha256", "source_sha256"]}
        for r in rows
    }
    return hashlib.sha256(json.dumps(ids, sort_keys=True).encode()).hexdigest()


def diagnostic_rows(
    rows: list[dict[str, Any]], p: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train = []
    for stratum in ["DAUN", "MacKenzie"]:
        group = [r for r in rows if r["split_role"] == "TRAIN" and r["source_stratum"] == stratum]
        selected: dict[str, Any] = {}
        for r in sorted(group, key=lambda r: (r["official_signer_id"], r["sample_id"])):
            selected.setdefault(r["official_signer_id"], r)
        train.extend(list(selected.values())[: p["diagnostic_train_per_stratum"]])
    dev_all = [r for r in rows if r["split_role"] == "DEV"]
    selected = {}
    for r in sorted(dev_all, key=lambda r: (r["official_signer_id"], r["sample_id"])):
        selected.setdefault(r["official_signer_id"], r)
    dev = list(selected.values())[: p["diagnostic_dev_signers"]]
    for r in dev_all:
        if not r["phone_ctc_feasible"] and r not in dev:
            dev.append(r)
    return train, dev


def diagnose(output: Path) -> dict[str, Any]:
    p, base = policy()
    rows = dataset(output)
    train, dev = diagnostic_rows(rows, p)
    completion = json.loads((REPO / "runs/fingerspelling_ctc_fast_01/completion.json").read_text())
    model_path = Path(completion["best_model_path"])
    ids = {"TRAIN": [r["sample_id"] for r in train], "DEV": [r["sample_id"] for r in dev]}
    write_json_atomic(
        EVIDENCE / "diagnostic_manifest.json",
        {
            "selection": "METADATA_SIGNER_ROUND_ROBIN_PLUS_ALL_INFEASIBLE_DEV_PHONE_CASES",
            "ids": ids,
            "policy_sha256": sha256(POLICY_PATH),
            "checkpoint_sha256": sha256(model_path),
        },
    )
    tf = reference.tensorflow(base)
    model = tf.keras.models.load_model(model_path)
    steps, cache = CompiledSteps(tf, model), FeatureCache()
    fixed = {}
    for role, subset_rows in [("TRAIN", train), ("DEV", dev)]:
        views, _, _ = evaluate_views(tf, steps, cache, subset_rows, p, base["batch_size"])
        fixed[role] = views
    sparse = fixed["DEV"]["phone"]
    supported = bool(
        sparse["emission"]["blank_argmax_fraction"] >= p["diagnostic_blank_fraction_threshold"]
        and sparse["metrics"]["predicted_reference_ratio"] < p["diagnostic_length_ratio_threshold"]
    )
    full_dev = [r for r in rows if r["split_role"] == "DEV"]
    views, logits, _ = evaluate_views(tf, steps, cache, full_dev, p, base["batch_size"])
    prior = json.loads((REPO / "runs/fingerspelling_ctc_fast_01/epochs/epoch_030.json").read_text())
    for view in ["native", "phone"]:
        if views[view]["metrics"]["cer"] != prior["dev"][view]["metrics"]["cer"]:
            raise ValueError("[baseline2/diagnosis] Baseline1 restored DEV metric mismatch")
    calibration = calibrate(logits, p, supported)
    result = {
        "schema_version": "apphear.fingerspelling.baseline1_emission_diagnosis.v1",
        "policy_sha256": sha256(POLICY_PATH),
        "manifest_sha256": sha256(output / "tranche_manifest.json"),
        "checkpoint_sha256": sha256(model_path),
        "fixed_subset": fixed,
        "blank_calibration_supported": supported,
        "full_dev_calibration": calibration,
        "no_training": True,
        "test_accessed": False,
        "interpretation": (
            "Blank fraction alone is normal in CTC; under-length outputs corroborate sparse "
            "blank-heavy behavior. Calibration is a symptom test, not proof of information loss."
        ),
    }
    write_json_atomic(EVIDENCE / "baseline1_diagnosis.json", result)
    return {
        "status": "BASELINE1_EMISSION_DIAGNOSED",
        "calibration_supported": supported,
        "selected_baseline1_penalty": calibration["selected_penalty"],
        "baseline1_combined_cer": calibration["uncalibrated_combined_cer"],
        "baseline1_calibrated_combined_cer": calibration["selected_combined_cer"],
        "fixed_dev_sparse_emission": sparse["emission"],
        "fixed_dev_sparse_length_ratio": sparse["metrics"]["predicted_reference_ratio"],
    }


def diagnosis(p: dict[str, Any], output: Path) -> dict[str, Any]:
    del p
    path = EVIDENCE / "baseline1_diagnosis.json"
    d: dict[str, Any] = json.loads(path.read_text())
    if (
        d["schema_version"] != "apphear.fingerspelling.baseline1_emission_diagnosis.v1"
        or d["policy_sha256"] != sha256(POLICY_PATH)
        or d["manifest_sha256"] != sha256(output / "tranche_manifest.json")
    ):
        raise ValueError("[baseline2/diagnosis] Stale or incompatible diagnostic decision")
    return d


def safe_run(run: Path) -> None:
    run.resolve().relative_to(REPO / "runs")
    if run.resolve() in {
        (REPO / "runs/fingerspelling_ctc_baseline_01").resolve(),
        (REPO / "runs/fingerspelling_ctc_fast_01").resolve(),
    }:
        raise ValueError("[baseline2/run] Baseline1 is read-only")


def code_identity() -> dict[str, str]:
    paths = [
        "model/fingerspelling_baseline2.py",
        "model/fingerspelling_emission.py",
        "model/fingerspelling_temporal_execution.py",
        "pipeline/fingerspelling/temporal_views.py",
        "model/fingerspelling_ctc.py",
        "model/fingerspelling_fast_execution.py",
        "model/fingerspelling_metrics.py",
    ]
    return {path: sha256(REPO / path) for path in paths}


def preflight(output: Path, run: Path) -> dict[str, Any]:
    import importlib.metadata
    import shutil
    import tempfile

    safe_run(run)
    p, base = policy()
    rows = dataset(output, full=True)
    d = diagnosis(p, output)
    run.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=run.parent) as stream:
        stream.write(b"baseline2 writable probe")
    report = {
        "schema_version": "apphear.fingerspelling.baseline2_preflight.v1",
        "status": "BASELINE2_PREFLIGHT_PASS",
        "counts": dict(Counter(r["split_role"] for r in rows)),
        "native_ctc_feasible": sum(r["native_ctc_feasible"] for r in rows),
        "phone_ctc_infeasible_retained": dict(
            Counter(r["split_role"] for r in rows if not r["phone_ctc_feasible"])
        ),
        "adapter": identity(),
        "dataset_lineage_sha256": lineage(rows),
        "policy_sha256": sha256(POLICY_PATH),
        "code_sha256": code_identity(),
        "tensorflow_installed": importlib.metadata.version("tensorflow"),
        "cpu_threads": base["cpu_threads"],
        "blank_calibration_supported": d["blank_calibration_supported"],
        "free_bytes": shutil.disk_usage(run.parent).free,
        "test_accessed": False,
        "full_dataset_validation": True,
    }
    write_json_atomic(EVIDENCE / "preflight.json", report)
    return report


def run_identity(output: Path, rows: list[dict[str, Any]], smoke: bool) -> dict[str, Any]:
    p, base = policy()
    diagnosis(p, output)
    return {
        "schema_version": "apphear.fingerspelling.baseline2_run.v1",
        "policy": p,
        "base_config": base,
        "policy_sha256": sha256(POLICY_PATH),
        "adapter": identity(),
        "code_sha256": code_identity(),
        "manifest_sha256": sha256(output / "tranche_manifest.json"),
        "dataset_lineage_sha256": lineage(rows),
        "diagnosis_sha256": sha256(EVIDENCE / "baseline1_diagnosis.json"),
        "smoke_only": smoke,
        "sample_ids": [r["sample_id"] for r in rows],
        "test_accessed": False,
    }


def state_digest(model: Any, optimizer: Any) -> str:
    digest = hashlib.sha256()
    for value in [*model.trainable_variables, *optimizer.variables]:
        a = np.asarray(value.numpy())
        digest.update(str((a.shape, a.dtype.str)).encode())
        digest.update(a.tobytes())
    return digest.hexdigest()


def stopping_state(state: dict[str, Any], score: float, p: dict[str, Any]) -> dict[str, Any]:
    previous = state.get("patience_anchor")
    if previous is None or score <= previous - p["minimum_improvement"]:
        return {"patience_anchor": score, "non_improving_epochs": 0}
    return {"patience_anchor": previous, "non_improving_epochs": state["non_improving_epochs"] + 1}


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
                "[baseline2/resume] Config/code/data identity changed; refusing mixed run"
            )
    elif any(run.iterdir()):
        raise ValueError("[baseline2/run] Nonempty unowned run directory refused")
    else:
        write_json_atomic(identity_path, rid)
    tf.keras.utils.set_random_seed(p["seed"])
    model = reference.build_model(tf, base)
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
            raise ValueError("[baseline2/resume] Restored weights/Adam/epoch mismatch")
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
    elif manager.latest_checkpoint:
        raise ValueError("[baseline2/resume] Uncommitted checkpoint requires review")
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
            "fresh_initialization_not_baseline1_finetuning": True,
        },
    )
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
                        raise RuntimeError("[baseline2/train] Optimizer missing")
                    value = float(steps.update(*tensors).numpy())
                    if not np.isfinite(value):
                        raise ValueError("[baseline2/train] Non-finite loss")
                    losses.append((value, len(batch)))
                    choices.extend(picked)
                train_seconds = time.perf_counter() - started
                views, _, view_seconds = evaluate_views(
                    tf, steps, cache, dev_rows, p, base["batch_size"]
                )
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
                report = {
                    "schema_version": "apphear.fingerspelling.baseline2_epoch.v1",
                    "epoch": epoch + 1,
                    "train_mean_ctc": sum(a * n for a, n in losses) / sum(n for _, n in losses),
                    "combined_uncalibrated_dev_cer": score,
                    "dev": views,
                    "temporal_views": {
                        "requested_counts": dict(Counter(c["requested"] for c in choices)),
                        "actual_counts": dict(Counter(c["actual"] for c in choices)),
                        "fallback_count": sum(c["fallback"] for c in choices),
                        "choices": choices,
                        "all_fit_sources_retained": len(choices) == len(train_rows),
                    },
                    "timings": {"train_seconds": train_seconds, "dev_seconds": view_seconds},
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
            "status": "BASELINE2_SMOKE_COMPLETE" if smoke else "BASELINE2_TRAINING_COMPLETE",
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


def smoke_rows(rows: list[dict[str, Any]], p: dict[str, Any]) -> list[dict[str, Any]]:
    train, dev = diagnostic_rows(rows, p)
    difficult = next(r for r in rows if r["split_role"] == "TRAIN" and not r["phone_ctc_feasible"])
    train = [difficult, *[r for r in train if r["sample_id"] != difficult["sample_id"]]][
        : p["smoke_train_count"]
    ]
    hard_dev = [r for r in rows if r["split_role"] == "DEV" and not r["phone_ctc_feasible"]]
    dev = [*hard_dev, *[r for r in dev if r not in hard_dev]][: p["smoke_dev_count"]]
    return train + dev


def smoke(output: Path, run: Path) -> dict[str, Any]:
    p, base = policy()
    rows = smoke_rows(dataset(output), p)
    cache = TemporalFeatureCache(p)
    parity = []
    for r in rows:
        raw = verify_raw(REPO / r["raw_path"], REPO / r["raw_receipt_path"], r, r["source_sha256"])
        cache.register(r)
        for view in p["temporal_views"]:
            indices = selected_indices(raw, view, p)
            actual = derive(subset(raw, indices))
            if not np.array_equal(actual, cache.load(r, view)[0]):
                raise ValueError("[baseline2/smoke] Stored/native or selected-view parity mismatch")
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
                raise ValueError("[baseline2/smoke] Cadence variation missing")
        if not any(c["fallback"] for c in choices) or any(c["headroom"] < 0 for c in choices):
            raise ValueError("[baseline2/smoke] Feasibility fallback not demonstrated")
        eval_report = final_evaluate(output, run, tf=tf, rows=rows)
    result = {
        "schema_version": "apphear.fingerspelling.baseline2_smoke.v1",
        "status": "BASELINE2_SMOKE_PASS",
        "policy_sha256": sha256(POLICY_PATH),
        "code_sha256": code_identity(),
        "ids": parity,
        "counts": dict(Counter(r["split_role"] for r in rows)),
        "native_phone_bit_exact_adapter_parity": True,
        "intermediate_recomputed_from_raw": True,
        "pause": first,
        "completion": restored,
        "resume_verification": json.loads((run / "resume_verification.json").read_text()),
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
        raise ValueError("[baseline2/eval] Run/data/code identity mismatch")
    completion = json.loads((run / "completion.json").read_text())
    model_path = Path(completion["best_model_path"])
    if sha256(model_path) != completion["best_model_sha256"]:
        raise ValueError("[baseline2/eval] Best checkpoint hash mismatch")
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
        raise ValueError("[baseline2/eval] Best checkpoint restored metric mismatch")
    calibration = calibrate(logits, p, diagnosis(p, output)["blank_calibration_supported"])
    report = {
        "schema_version": "apphear.fingerspelling.baseline2_final.v1",
        "status": "BASELINE2_FINAL_EVALUATED",
        "best_epoch": completion["best_epoch"],
        "checkpoint_sha256": sha256(model_path),
        "policy_sha256": sha256(POLICY_PATH),
        "adapter": identity(),
        "dataset_lineage_sha256": rid["dataset_lineage_sha256"],
        "uncalibrated": views,
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


def status(run: Path) -> dict[str, Any]:
    result = {"run_dir": str(run), "started": (run / "run_identity.json").exists()}
    for name in ["progress", "completion", "failure"]:
        path = run / f"{name}.json"
        if path.exists():
            result[name] = json.loads(path.read_text())
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["diagnose", "preflight", "smoke", "train", "status", "evaluate"]
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    args = parser.parse_args()
    output, run = args.dataset.resolve(), args.run_dir.resolve()
    output.relative_to(REPO)
    safe_run(run)
    if args.command == "diagnose":
        result = diagnose(output)
    elif args.command == "preflight":
        result = preflight(output, run)
    elif args.command == "smoke":
        if run == DEFAULT_RUN.resolve():
            raise ValueError("[baseline2/smoke] Supply an independent --run-dir")
        result = smoke(output, run)
    elif args.command == "status":
        result = status(run)
    elif args.command == "evaluate":
        with single_writer(run):
            result = final_evaluate(output, run)
    else:
        with single_writer(run):
            preflight(output, run)
            smoke_evidence = json.loads((EVIDENCE / "smoke.json").read_text())
            if (
                smoke_evidence["status"] != "BASELINE2_SMOKE_PASS"
                or smoke_evidence["code_sha256"] != code_identity()
                or smoke_evidence["policy_sha256"] != sha256(POLICY_PATH)
            ):
                raise ValueError("[baseline2/train] Matching engineering smoke required")
            p, base = policy()
            result = engine(output, run, dataset(output), reference.tensorflow(base))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
