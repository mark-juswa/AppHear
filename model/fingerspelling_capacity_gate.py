"""Fixed two-arm TRAIN fitting diagnostic. No DEV selection or full training."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from model import fingerspelling_baseline2 as b2
from model import fingerspelling_capacity as capacity
from model import fingerspelling_ctc as reference
from model.fingerspelling_emission import balanced_score, evaluate_views
from model.fingerspelling_fast_execution import CompiledSteps
from model.fingerspelling_temporal_execution import TemporalFeatureCache
from pipeline.fingerspelling.adapter import identity, sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from tools.fingerspelling.baseline3_analysis import character_metrics
from tools.fingerspelling.tranche import single_writer


def correct_fraction(view: dict[str, Any]) -> float:
    chars = view["characters"]["per_character"]
    return float(
        sum(c["correct"] for c in chars.values())
        / sum(c["reference_count"] for c in chars.values())
    )


def decision(reports: dict[str, dict[int, dict[str, Any]]], cfg: dict[str, Any]) -> dict[str, Any]:
    checks = []
    for epoch in cfg["fit_decision_epochs"]:
        control, candidate = (reports[a][epoch]["train"] for a in ["control", "candidate"])
        gain = balanced_score(control) - balanced_score(candidate)
        checks.append(
            {
                "epoch": epoch,
                "combined_cer_improvement": gain,
                "control_combined_cer": balanced_score(control),
                "candidate_combined_cer": balanced_score(candidate),
                "both_views_cer_improved": all(
                    candidate[v]["metrics"]["cer"] < control[v]["metrics"]["cer"] for v in control
                ),
                "both_views_correct_character_fraction_improved": all(
                    correct_fraction(candidate[v]) > correct_fraction(control[v]) for v in control
                ),
                "effect_threshold_met": gain >= cfg["fit_minimum_combined_cer_improvement"],
            }
        )
    passed = all(
        c["effect_threshold_met"]
        and c["both_views_cer_improved"]
        and c["both_views_correct_character_fraction_improved"]
        for c in checks
    )
    return {
        "status": (
            "BASELINE4_CAPACITY_GATE_PASS" if passed else "BASELINE4_CAPACITY_GATE_NOT_SUPPORTED"
        ),
        "full_training_authorized": passed,
        "checks": checks,
        "interpretation": "Single-seed equal-update subset fit evidence; no held-out accuracy claim. A failed bounded test does not prove information loss or disprove all capacity improvements.",
    }


def evaluate(
    tf: Any,
    steps: CompiledSteps,
    cache: TemporalFeatureCache,
    rows: list[dict[str, Any]],
    p: dict[str, Any],
    batch_size: int,
) -> dict[str, Any]:
    views, _, times = evaluate_views(tf, steps, cache, rows, p, batch_size)
    for value in views.values():
        value["characters"] = character_metrics(value["predictions"])
    return {"train": views, "seconds": times, "balanced_train_cer": balanced_score(views)}


def arm_run(
    tf: Any,
    run: Path,
    arm: str,
    rows: list[dict[str, Any]],
    cache: TemporalFeatureCache,
    rid: dict[str, Any],
    cfg: dict[str, Any],
    p: dict[str, Any],
    base: dict[str, Any],
    stop_after: int | None,
) -> dict[str, Any]:
    run.mkdir(parents=True, exist_ok=True)
    rid_path = run / "run_identity.json"
    arm_id = {**rid, "arm": arm}
    if rid_path.exists():
        if json.loads(rid_path.read_text()) != arm_id:
            raise ValueError("[baseline4/gate] Resume identity mismatch")
    elif any(run.iterdir()):
        raise ValueError("[baseline4/gate] Unowned directory refused")
    else:
        write_json_atomic(rid_path, arm_id)
    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(base["seed"])
    model = capacity.build_model(tf, arm)
    opt = tf.keras.optimizers.Adam(base["learning_rate"], clipnorm=base["gradient_clip_norm"])
    opt.build(model.trainable_variables)
    epoch_var = tf.Variable(0, trainable=False, dtype=tf.int64)
    ckpt = tf.train.Checkpoint(model=model, optimizer=opt, epoch=epoch_var)
    manager = tf.train.CheckpointManager(ckpt, str(run / "checkpoints"), max_to_keep=3)
    state_path = run / "committed_epoch.json"
    state: dict[str, Any] = {"epoch": 0}
    if state_path.exists():
        state = json.loads(state_path.read_text())
        ckpt.restore(state["checkpoint"]).assert_existing_objects_matched()
        if (
            int(epoch_var.numpy()) != state["epoch"]
            or b2.state_digest(model, opt) != state["state_sha256"]
        ):
            raise ValueError("[baseline4/gate] Restored model/optimizer/epoch mismatch")
        write_json_atomic(
            run / "resume_verification.json",
            {
                "epoch": state["epoch"],
                "state_exactly_restored": True,
                "bit_exact_continuation_claim": False,
            },
        )
    elif manager.latest_checkpoint:
        raise ValueError("[baseline4/gate] Uncommitted checkpoint requires review")
    steps = CompiledSteps(tf, model, opt)
    if state["epoch"] == 0:
        write_json_atomic(
            run / "evaluations/epoch_000.json",
            evaluate(tf, steps, cache, rows, p, base["batch_size"]),
        )
    for epoch in range(state["epoch"], cfg["fit_epochs"]):
        started = time.perf_counter()
        order = np.random.default_rng(base["seed"] + epoch).permutation(len(rows))
        losses, choices = [], []
        for start in range(0, len(order), base["batch_size"]):
            batch = [rows[i] for i in order[start : start + base["batch_size"]]]
            tensors, picked = cache.training_batch(batch, epoch)
            if steps.update is None:
                raise RuntimeError("[baseline4/gate] Optimizer missing")
            value = float(steps.update(*tensors).numpy())
            if not np.isfinite(value):
                raise ValueError("[baseline4/gate] Non-finite loss")
            losses.append(value)
            choices.extend(picked)
        report = {
            "arm": arm,
            "epoch": epoch + 1,
            "train_ctc": float(np.mean(losses)),
            "updates": int(opt.iterations.numpy()),
            "requested_counts": dict(Counter(c["requested"] for c in choices)),
            "actual_counts": dict(Counter(c["actual"] for c in choices)),
            "fallback_count": sum(c["fallback"] for c in choices),
            "sample_order_sha256": hashlib.sha256(
                json.dumps([rows[i]["sample_id"] for i in order]).encode()
            ).hexdigest(),
            "temporal_choices_sha256": hashlib.sha256(
                json.dumps(choices, sort_keys=True).encode()
            ).hexdigest(),
            "all_sources_retained": len(choices) == len(rows),
        }
        if (epoch + 1) % cfg["fit_evaluate_every"] == 0:
            eval_report = evaluate(tf, steps, cache, rows, p, base["batch_size"])
            eval_report.update(epoch=epoch + 1, train_ctc=report["train_ctc"])
            write_json_atomic(run / f"evaluations/epoch_{epoch + 1:03d}.json", eval_report)
            report["balanced_train_cer"] = eval_report["balanced_train_cer"]
        epoch_var.assign(epoch + 1)
        state = {
            "epoch": epoch + 1,
            "checkpoint": manager.save(checkpoint_number=epoch + 1),
            "state_sha256": b2.state_digest(model, opt),
        }
        report["epoch_seconds"] = time.perf_counter() - started
        write_json_atomic(run / f"epochs/epoch_{epoch + 1:03d}.json", report)
        write_json_atomic(state_path, state)
        write_json_atomic(run / "progress.json", report)
        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(json.dumps(report), flush=True)
        if stop_after is not None and epoch + 1 >= stop_after:
            return {"status": "GATE_ENGINEERING_PAUSE", "arm": arm, "epoch": epoch + 1}
    path = run / "final.keras"
    model.save(path)
    result = {
        "status": "GATE_ARM_COMPLETE",
        "arm": arm,
        "epochs": state["epoch"],
        "updates": int(opt.iterations.numpy()),
        "parameters": model.count_params(),
        "checkpoint_sha256": sha256(path),
    }
    write_json_atomic(run / "completion.json", result)
    return result


def run_gate(output: Path, stop_after: int | None = None) -> dict[str, Any]:
    cfg, p, base = capacity.policy()
    run = capacity.GATE_RUN
    capacity.safe_gate(run)
    rows = capacity.diagnostic_rows(b2.dataset(output))
    cache = TemporalFeatureCache(p)
    for rec in rows:
        cache.register(rec)
    rid = {
        "schema_version": "apphear.fingerspelling.capacity_fit_gate.v1",
        "config_sha256": sha256(capacity.CONFIG),
        "adapter": identity(),
        "data_lineage_sha256": b2.lineage(rows),
        "code_sha256": capacity.code_identity(),
        "sample_ids": [r["sample_id"] for r in rows],
        "test_accessed": False,
        "seed": base["seed"],
    }
    tf = reference.tensorflow(base)
    arms = {}
    for arm in ["control", "candidate"]:
        arms[arm] = arm_run(tf, run / arm, arm, rows, cache, rid, cfg, p, base, stop_after)
        if arms[arm]["status"] == "GATE_ENGINEERING_PAUSE":
            return arms[arm]
    reports = {
        a: {
            e: json.loads((run / a / f"evaluations/epoch_{e:03d}.json").read_text())
            for e in cfg["fit_decision_epochs"]
        }
        for a in arms
    }
    for epoch in range(1, cfg["fit_epochs"] + 1):
        pairs = [json.loads((run / a / f"epochs/epoch_{epoch:03d}.json").read_text()) for a in arms]
        for key in ["sample_order_sha256", "temporal_choices_sha256", "updates"]:
            if pairs[0][key] != pairs[1][key]:
                raise ValueError("[baseline4/gate] Unequal order/views/update budget")
    result = {
        **rid,
        **decision(reports, cfg),
        "arms": arms,
        "signers": len({r["official_signer_id"] for r in rows}),
        "strata": dict(Counter(r["source_stratum"] for r in rows)),
        "paired_data_order_views_updates_verified": True,
        "run_dir": str(run),
    }
    write_json_atomic(capacity.EVIDENCE / "fit_gate.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=b2.DEFAULT_DATA)
    parser.add_argument(
        "--stop-after",
        type=int,
        default=None,
        help="Engineering resume check; does not change the frozen budget",
    )
    args = parser.parse_args()
    with single_writer(capacity.GATE_RUN):
        try:
            result = run_gate(args.dataset.resolve(), args.stop_after)
        except BaseException as exc:
            write_json_atomic(
                capacity.EVIDENCE / "gate_failure.json",
                {
                    "type": type(exc).__name__,
                    "error": str(exc),
                    "resume": "Rerun the same capacity-gate command; interrupted epoch repeats",
                },
            )
            raise
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
