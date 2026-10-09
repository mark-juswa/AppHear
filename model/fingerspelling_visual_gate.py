"""One fixed geometry/appearance/combined sequence information gate; TEST sealed."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, cast

import numpy as np

from model import fingerspelling_baseline2 as b2
from model import fingerspelling_ctc as reference
from model.fingerspelling_appearance import EVIDENCE
from model.fingerspelling_emission import balanced_score, evaluate_views
from model.fingerspelling_visual_execution import (
    ARMS,
    FusionCache,
    FusionSteps,
    build_fusion_model,
)
from pipeline.fingerspelling.adapter import identity, sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.visual_crop import CONFIG_PATH as CONFIG
from pipeline.fingerspelling.visual_crop import config
from pipeline.fingerspelling.visual_package import load_visual, receipt_path, visual_identity
from tools.fingerspelling.baseline3_analysis import character_metrics
from tools.fingerspelling.tranche import single_writer
from tools.fingerspelling.visual_fusion import diagnostic_rows

RUN = REPO / "runs/fingerspelling_visual_information_gate_01"


def code_identity() -> dict[str, str]:
    return {
        str(p.relative_to(REPO)): sha256(p)
        for p in [
            REPO / "model/fingerspelling_visual_gate.py",
            REPO / "model/fingerspelling_visual_execution.py",
            REPO / "tools/fingerspelling/visual_fusion.py",
            REPO / "model/fingerspelling_baseline2.py",
            REPO / "model/fingerspelling_emission.py",
            REPO / "model/fingerspelling_ctc.py",
        ]
    }


def discrimination(view: dict[str, Any]) -> dict[str, float]:
    chars = view["characters"]["per_character"]
    correct = sum(c["correct"] for c in chars.values())
    reference_count = sum(c["reference_count"] for c in chars.values())
    predicted = view["metrics"]["predicted_characters"]
    return {
        "correct_reference_fraction": correct / reference_count,
        "correct_predicted_precision": correct / predicted if predicted else 0.0,
    }


def decision(reports: dict[str, dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    g, c = reports["geometry"], reports["combined"]
    train_gain = balanced_score(g["train"]) - balanced_score(c["train"])
    dev_gain = balanced_score(g["dev"]) - balanced_score(c["dev"])
    stats = {
        a: {
            role: {v: discrimination(x) for v, x in report[role].items()}
            for role in ["train", "dev"]
        }
        for a, report in reports.items()
    }

    def mean(a: str, field: str) -> float:
        return float(np.mean([stats[a]["dev"][v][field] for v in ["native", "phone"]]))

    recall_gain = mean("combined", "correct_reference_fraction") - mean(
        "geometry", "correct_reference_fraction"
    )
    precision_gain = mean("combined", "correct_predicted_precision") - mean(
        "geometry", "correct_predicted_precision"
    )
    checks = {
        "train_cer_gain": train_gain >= cfg["gate_train_cer_gain"],
        "train_both_views_improve": all(
            c["train"][v]["metrics"]["cer"] < g["train"][v]["metrics"]["cer"]
            for v in ["native", "phone"]
        ),
        "dev_cer_gain": dev_gain >= cfg["gate_dev_cer_gain"],
        "dev_no_large_view_regression": all(
            c["dev"][v]["metrics"]["cer"] - g["dev"][v]["metrics"]["cer"]
            <= cfg["gate_dev_max_view_cer_regression"]
            for v in ["native", "phone"]
        ),
        "dev_correct_reference_gain": recall_gain >= cfg["gate_dev_correct_reference_gain"],
        "dev_mean_precision_not_lower": precision_gain >= 0,
        "dev_no_large_view_precision_loss": all(
            stats["geometry"]["dev"][v]["correct_predicted_precision"]
            - stats["combined"]["dev"][v]["correct_predicted_precision"]
            <= cfg["gate_dev_max_view_precision_loss"]
            for v in ["native", "phone"]
        ),
    }
    passed = all(checks.values())
    return {
        "status": (
            "VISUAL_INFORMATION_GATE_PASS"
            if passed
            else "VISUAL_INFORMATION_GATE_NOT_SUPPORTED"
        ),
        "full_fusion_training_authorized": passed,
        "checks": checks,
        "train_combined_cer_gain": train_gain,
        "dev_combined_cer_gain": dev_gain,
        "dev_correct_reference_gain": recall_gain,
        "dev_precision_gain": precision_gain,
        "discrimination": stats,
        "interpretation": (
            "Single seed, fixed 60-epoch subset, frozen ImageNet appearance encoder. "
            "A negative result does not establish that RGB lacks information; "
            "it stops this fusion baseline. No production accuracy claim."
        ),
    }


def evaluate(
    tf: Any,
    steps: FusionSteps,
    cache: FusionCache,
    rows: list[dict[str, Any]],
    dev: list[dict[str, Any]],
    p: dict[str, Any],
    batch_size: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    times = {}
    for name, selected in [("train", rows), ("dev", dev)]:
        views, _, seconds = evaluate_views(
            tf, cast(Any, steps), cast(Any, cache), selected, p, batch_size
        )
        for value in views.values():
            value["characters"] = character_metrics(value["predictions"])
        result[name], times[name] = views, seconds
    result.update(
        seconds=times,
        balanced_train_cer=balanced_score(result["train"]),
        balanced_dev_cer=balanced_score(result["dev"]),
    )
    return result


def arm_run(
    tf: Any,
    run: Path,
    arm: str,
    rows: list[dict[str, Any]],
    cache: FusionCache,
    dev: list[dict[str, Any]],
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
            raise ValueError("[visual/gate] Resume identity mismatch")
    elif any(run.iterdir()):
        raise ValueError("[visual/gate] Unowned directory refused")
    else:
        write_json_atomic(rid_path, arm_id)
    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(base["seed"])
    model = build_fusion_model(tf)
    opt = tf.keras.optimizers.Adam(base["learning_rate"], clipnorm=base["gradient_clip_norm"])
    opt.build(model.trainable_variables)
    initial_digest = b2.state_digest(model, opt)
    initial_path = run / "initialization.json"
    initial = {"state_sha256": initial_digest, "parameters": model.count_params()}
    if initial_path.exists() and json.loads(initial_path.read_text()) != initial:
        raise ValueError("[visual/gate] Initial model/optimizer are not reproducible")
    write_json_atomic(initial_path, initial)
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
            raise ValueError("[visual/gate] Restored model/optimizer/epoch mismatch")
        write_json_atomic(
            run / "resume_verification.json",
            {
                "epoch": state["epoch"],
                "state_exactly_restored": True,
                "bit_exact_continuation_claim": False,
            },
        )
    elif manager.latest_checkpoint:
        raise ValueError("[visual/gate] Uncommitted checkpoint requires review")
    steps = FusionSteps(tf, model, opt)
    if state["epoch"] == 0:
        write_json_atomic(
            run / "evaluations/epoch_000.json",
            evaluate(tf, steps, cache, rows, dev, p, base["batch_size"]),
        )
    for epoch in range(state["epoch"], cfg["gate_epochs"]):
        started = time.perf_counter()
        order = np.random.default_rng(base["seed"] + epoch).permutation(len(rows))
        losses, choices = [], []
        for start in range(0, len(order), base["batch_size"]):
            batch = [rows[i] for i in order[start : start + base["batch_size"]]]
            tensors, picked = cache.training_batch(batch, epoch)
            if steps.update is None:
                raise RuntimeError("[visual/gate] Optimizer missing")
            value = float(steps.update(*tensors).numpy())
            if not np.isfinite(value):
                raise ValueError("[visual/gate] Non-finite loss")
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
        if (epoch + 1) in cfg["gate_evaluation_epochs"]:
            eval_report = evaluate(tf, steps, cache, rows, dev, p, base["batch_size"])
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


def run_gate(stop_after: int | None = None) -> dict[str, Any]:
    cfg, (p, base) = config(), b2.policy()
    rows = b2.dataset(b2.DEFAULT_DATA)
    train, dev = diagnostic_rows(rows)
    for rec in train + dev:
        load_visual(rec)
    rid = {
        "schema_version": "apphear.fingerspelling.visual_information_gate.v1",
        "config_sha256": sha256(CONFIG),
        "adapter": identity(),
        "data_lineage_sha256": b2.lineage(train + dev),
        "visual_identity": visual_identity(),
        "code_sha256": code_identity(),
        "visual_receipts": {r["sample_id"]: sha256(receipt_path(r)) for r in train + dev},
        "train_ids": [r["sample_id"] for r in train],
        "dev_ids": [r["sample_id"] for r in dev],
        "seed": base["seed"],
        "test_accessed": False,
        "calibration": "NONE",
        "selection": "FIXED_EPOCH_60_NO_DEV_CHECKPOINT_SELECTION",
    }
    tf = reference.tensorflow(base)
    arms = {}
    for arm in ARMS:
        cache = FusionCache(arm)
        arms[arm] = arm_run(
            tf, RUN / arm, arm, train, cache, dev, rid, cfg, p, base, stop_after
        )
        if arms[arm]["status"] == "GATE_ENGINEERING_PAUSE":
            return arms[arm]
    reports = {
        a: json.loads((RUN / a / "evaluations/epoch_060.json").read_text()) for a in ARMS
    }
    initializations = [json.loads((RUN / a / "initialization.json").read_text()) for a in ARMS]
    if any(x != initializations[0] for x in initializations[1:]):
        raise ValueError("[visual/gate] Unequal initial model/optimizer state")
    for epoch in range(1, cfg["gate_epochs"] + 1):
        pairs = [
            json.loads((RUN / a / f"epochs/epoch_{epoch:03d}.json").read_text()) for a in ARMS
        ]
        for key in ["sample_order_sha256", "temporal_choices_sha256", "updates"]:
            if len({x[key] for x in pairs}) != 1:
                raise ValueError("[visual/gate] Unequal order/views/update budget")
    result = {
        **rid,
        **decision(reports, cfg),
        "arms": arms,
        "train_signers": len({r["official_signer_id"] for r in train}),
        "dev_signers": len({r["official_signer_id"] for r in dev}),
        "train_strata": dict(Counter(r["source_stratum"] for r in train)),
        "paired_data_order_views_updates_verified": True,
        "final_evaluations": {
            a: {"train_cer": balanced_score(r["train"]), "dev_cer": balanced_score(r["dev"])}
            for a, r in reports.items()
        },
    }
    write_json_atomic(EVIDENCE / "visual_information_gate.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stop-after",
        type=int,
        default=None,
        help="Engineering resume check; frozen total budget is unchanged",
    )
    args = parser.parse_args()
    with single_writer(RUN):
        try:
            result = run_gate(args.stop_after)
        except BaseException as exc:
            write_json_atomic(
                EVIDENCE / "gate_failure.json",
                {
                    "type": type(exc).__name__,
                    "error": str(exc),
                    "resume": "Rerun identical gate command; incomplete epoch repeats",
                },
            )
            raise
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
