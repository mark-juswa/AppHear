"""One frozen-B2 residual experiment. Full preparation/training are explicit user commands."""

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
from model.fingerspelling_emission import balanced_score, collect_logits, score_logits
from model.fingerspelling_residual_execution import (
    ResidualCache,
    ResidualSteps,
    base_model,
    build_model,
    frozen_digest,
)
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.residual_visual_package import identity, receipt_path
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.visual_quality import CONFIG, config
from tools.fingerspelling.baseline3_analysis import character_metrics
from tools.fingerspelling.residual_audit import EVIDENCE
from tools.fingerspelling.residual_lock import single_writer
from tools.fingerspelling.residual_visual import admission, smoke_rows, status

RUN = REPO / "runs/fingerspelling_residual_visual_01"
SMOKE_RUN = REPO / "runs/fingerspelling_residual_visual_smoke_03"
SOURCES = [
    "model/fingerspelling_residual_visual.py",
    "model/fingerspelling_residual_execution.py",
    "model/fingerspelling_baseline2.py",
    "model/fingerspelling_ctc.py",
    "model/fingerspelling_emission.py",
    "model/fingerspelling_visual_execution.py",
    "model/fingerspelling_temporal_execution.py",
    "pipeline/fingerspelling/temporal_views.py",
    "tools/fingerspelling/residual_visual.py",
    "tools/fingerspelling/residual_lock.py",
    "tools/fingerspelling/baseline3_analysis.py",
]


def run_identity(rows: list[dict[str, Any]], smoke: bool) -> dict[str, Any]:
    return {
        "schema_version": "apphear.fingerspelling.residual_run.v1",
        "config": config(),
        "config_sha256": sha256(CONFIG),
        "data_lineage": b2.lineage(rows),
        "visual": identity(),
        "visual_receipts": {r["sample_id"]: sha256(receipt_path(r)) for r in rows},
        "code": {p: sha256(REPO / p) for p in SOURCES},
        "admission": admission(),
        "temporal_policy": b2.policy()[0],
        "seed": config()["seed"],
        "sample_ids": [r["sample_id"] for r in rows],
        "smoke_only": smoke,
        "test_accessed": False,
    }


def check_run(run: Path, smoke: bool = False) -> None:
    allowed = SMOKE_RUN if smoke else RUN
    if run.resolve() != allowed.resolve():
        raise ValueError(
            "[residual/run] Only separate reserved residual run directory allowed"
        )


def evaluate(
    tf: Any, steps: Any, cache: ResidualCache, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    p, base = b2.policy()
    raw: dict[str, Any] = {}
    fixed: dict[str, Any] = {}
    for v in ["native", "phone"]:
        logits = collect_logits(tf, steps, cast(Any, cache), rows, v, base["batch_size"])
        for penalty, dest in [(0.0, raw), (config()["blank_penalty"], fixed)]:
            dest[v] = score_logits(logits, penalty, p["length_strata_bounds"])
            chars = character_metrics(dest[v]["predictions"])
            correct = sum(c["correct"] for c in chars["per_character"].values())
            dest[v]["characters"] = chars
            dest[v]["discrimination"] = {
                "correctly_aligned_characters": correct,
                "correct_predicted_precision": (
                    correct / dest[v]["metrics"]["predicted_characters"]
                    if dest[v]["metrics"]["predicted_characters"]
                    else 0.0
                ),
            }
    return {
        "uncalibrated": raw,
        "fixed_b2_decoder": fixed,
        "balanced_fixed_cer": balanced_score(fixed),
    }


class ReferenceSteps:
    def __init__(self, tf: Any) -> None:
        b = base_model(tf)

        @tf.function(
            input_signature=[
                tf.TensorSpec([None, None, 1559], tf.float32),
                tf.TensorSpec([None, None, 1], tf.float32),
            ]
        )
        def infer(x: Any, mask: Any) -> Any:
            return b([x[:, :, :405], mask], training=False)

        self.infer = infer


def outcome(
    base: dict[str, Any], residual: dict[str, Any], smoke: bool
) -> dict[str, Any]:
    b, r = base["fixed_b2_decoder"], residual["fixed_b2_decoder"]
    checks = {}
    for v in ["native", "phone"]:
        checks[v + "_cer_lower"] = r[v]["metrics"]["cer"] < b[v]["metrics"]["cer"]
        checks[v + "_correct_characters_higher"] = (
            r[v]["discrimination"]["correctly_aligned_characters"]
            > b[v]["discrimination"]["correctly_aligned_characters"]
        )
        checks[v + "_substitutions_lower"] = (
            r[v]["metrics"]["substitutions"] < b[v]["metrics"]["substitutions"]
        )
    checks["mean_precision_not_lower"] = np.mean(
        [r[v]["discrimination"]["correct_predicted_precision"] for v in r]
    ) >= np.mean([b[v]["discrimination"]["correct_predicted_precision"] for v in b])
    signers = b["native"]["metrics"]["signers"]
    gains = {
        s: float(
            np.mean(
                [
                    b[v]["metrics"]["signers"][s]["cer"]
                    - r[v]["metrics"]["signers"][s]["cer"]
                    for v in b
                ]
            )
        )
        for s in signers
    }
    checks["at_least_eight_dev_signers_improve"] = (
        sum(g > 0 for g in gains.values()) >= 8
    )
    checks = {key: bool(value) for key, value in checks.items()}
    passed = all(checks.values()) and not smoke
    return {
        "status": (
            "ENGINEERING_SMOKE_NO_PERFORMANCE_DECISION"
            if smoke
            else (
                "RESIDUAL_VISUAL_DISCRIMINATION_SUPPORTED"
                if passed
                else "RESIDUAL_VISUAL_NOT_SUPPORTED_STOP_VISUAL_PATH"
            )
        ),
        "checks": checks,
        "signer_balanced_cer_gains": gains,
        "production_promoted": False,
        "decision_scope": "Fixed governed DEV research comparison; no production accuracy claim",
    }


def preflight() -> dict[str, Any]:
    rows = b2.dataset(b2.DEFAULT_DATA, full=True)
    admission()
    s = status(rows, True)
    if s["status"] != "RESIDUAL_VISUAL_VALID":
        raise ValueError(
            '[residual/preflight] Complete 1024 TRAIN / 256 DEV appearance package required: '
            f'{s["prepared"]}'
        )
    result = {
        "status": "RESIDUAL_TRAINING_PREFLIGHT_PASS",
        "dataset": s,
        "run_identity": run_identity(rows, False),
    }
    write_json_atomic(EVIDENCE / "training_preflight.json", result)
    return {"status": result["status"], "counts": s["prepared"], "run_dir": str(RUN)}


def engine(
    tf: Any,
    rows: list[dict[str, Any]],
    run: Path,
    smoke: bool = False,
    stop_after: int | None = None,
) -> dict[str, Any]:
    check_run(run, smoke)
    cfg = config()
    p, base = b2.policy()
    rid = run_identity(rows, smoke)
    run.mkdir(parents=True, exist_ok=True)
    id_path = run / "run_identity.json"
    if id_path.exists():
        if json.loads(id_path.read_text()) != rid:
            raise ValueError(
                "[residual/resume] Code/config/lineage changed; mixed run refused"
            )
    elif any(run.iterdir()):
        raise ValueError("[residual/run] Nonempty unowned directory refused")
    else:
        write_json_atomic(id_path, rid)
    tf.keras.utils.set_random_seed(cfg["seed"])
    model = build_model(tf)
    frozen = frozen_digest(model)
    opt = tf.keras.optimizers.Adam(
        cfg["learning_rate"], clipnorm=base["gradient_clip_norm"]
    )
    opt.build(model.trainable_variables)
    epoch_var = tf.Variable(0, dtype=tf.int64, trainable=False)
    ckpt = tf.train.Checkpoint(model=model, optimizer=opt, epoch=epoch_var)
    manager = tf.train.CheckpointManager(ckpt, str(run / "checkpoints"), max_to_keep=3)
    path = run / "committed_epoch.json"
    state: dict[str, Any] = {
        "epoch": 0,
        "best_combined_cer": None,
        "patience_anchor": None,
        "non_improving_epochs": 0,
    }
    if path.exists():
        state = json.loads(path.read_text())
        ckpt.restore(state["checkpoint"]).assert_existing_objects_matched()
        if (
            int(epoch_var.numpy()) != state["epoch"]
            or b2.state_digest(model, opt) != state["model_optimizer_sha256"]
            or frozen_digest(model) != frozen
        ):
            raise ValueError("[residual/resume] Weights/Adam/epoch/frozen B2 mismatch")
        write_json_atomic(
            run / "resume_verification.json",
            {
                "restored_epoch": state["epoch"],
                "model_optimizer_exactly_restored": True,
                "frozen_b2_exactly_restored": True,
                "optimizer_iterations": int(opt.iterations.numpy()),
                "bit_exact_continuation_claim": False,
            },
        )
    elif manager.latest_checkpoint:
        raise ValueError("[residual/resume] Uncommitted checkpoint requires review")
    write_json_atomic(
        run / "environment.json",
        {
            "tensorflow": tf.__version__,
            "keras": tf.keras.__version__,
            "parameters": model.count_params(),
            "trainable_parameters": sum(
                int(np.prod(v.shape)) for v in model.trainable_variables
            ),
            "trainable_variables": [v.path for v in model.trainable_variables],
            "frozen_b2_sha256": frozen,
            "cpu_only": True,
        },
    )
    cache = ResidualCache()
    steps = ResidualSteps(tf, model, opt)
    train = [r for r in rows if r["split_role"] == "TRAIN"]
    dev = [r for r in rows if r["split_role"] == "DEV"]
    train_diag = train if smoke else b2.diagnostic_rows(rows, p)[0]
    baseline_path = run / "frozen_b2_reference.json"
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text())
    else:
        reference_steps = ReferenceSteps(tf)
        baseline = {
            "base_checkpoint_sha256": cfg["base_checkpoint_sha256"],
            "decoder_blank_penalty": cfg["blank_penalty"],
            "dev": evaluate(tf, reference_steps, cache, dev),
            "train_diagnostic": evaluate(tf, reference_steps, cache, train_diag),
            "test_accessed": False,
        }
        write_json_atomic(baseline_path, baseline)
    maximum = 3 if smoke else cfg["maximum_epochs"]
    stopping = {"minimum_improvement": cfg["minimum_improvement"]}
    try:
        for epoch in range(state["epoch"], maximum):
            if (
                not smoke
                and state["epoch"] >= cfg["minimum_epochs"]
                and state["non_improving_epochs"] >= cfg["patience"]
            ):
                break
            t0 = time.perf_counter()
            choices = []
            losses = []
            order = np.random.default_rng(cfg["seed"] + epoch).permutation(len(train))
            for start in range(0, len(train), base["batch_size"]):
                batch = [train[i] for i in order[start : start + base["batch_size"]]]
                tensors, picked = cache.training_batch(batch, epoch)
                if steps.update is None:
                    raise RuntimeError("[residual/train] Missing optimizer")
                loss = float(steps.update(*tensors).numpy())
                losses.append((loss, len(batch)))
                choices.extend(picked)
            if frozen_digest(model) != frozen:
                raise ValueError("[residual/train] Frozen B2 weights changed")
            dev_report = evaluate(tf, steps, cache, dev)
            train_report = evaluate(tf, steps, cache, train_diag)
            score = dev_report["balanced_fixed_cer"]
            if state["best_combined_cer"] is None or score < state["best_combined_cer"]:
                best = run / "best_candidates" / f"epoch_{epoch+1:03d}.keras"
                best.parent.mkdir(exist_ok=True)
                model.save(best)
                state.update(
                    best_combined_cer=score,
                    best_epoch=epoch + 1,
                    best_model_path=str(best),
                    best_model_sha256=sha256(best),
                )
            state.update(b2.stopping_state(state, score, stopping))
            report = {
                "epoch": epoch + 1,
                "train_loss_ctc_plus_l2": sum(a * n for a, n in losses)
                / sum(n for _, n in losses),
                "dev": dev_report,
                "train_diagnostic": train_report,
                "paired_frozen_b2_dev_comparison": outcome(baseline["dev"], dev_report, smoke),
                "frozen_b2_reference_path": str(baseline_path),
                "temporal_choices": choices,
                "requested_views": dict(Counter(c["requested"] for c in choices)),
                "actual_views": dict(Counter(c["actual"] for c in choices)),
                "fallbacks": sum(c["fallback"] for c in choices),
                "frozen_b2_unchanged": True,
                "seconds": time.perf_counter() - t0,
                "smoke_only": smoke,
                "test_accessed": False,
            }
            write_json_atomic(run / "epochs" / f"epoch_{epoch+1:03d}.json", report)
            epoch_var.assign(epoch + 1)
            saved = manager.save(checkpoint_number=epoch + 1)
            state.update(
                epoch=epoch + 1,
                checkpoint=saved,
                model_optimizer_sha256=b2.state_digest(model, opt),
            )
            write_json_atomic(path, state)
            progress = {
                "epoch": epoch + 1,
                "train_loss": report["train_loss_ctc_plus_l2"],
                "native_dev_cer": dev_report["fixed_b2_decoder"]["native"]["metrics"][
                    "cer"
                ],
                "phone_dev_cer": dev_report["fixed_b2_decoder"]["phone"]["metrics"][
                    "cer"
                ],
                "balanced_fixed_cer": score,
                "best_balanced_fixed_cer": state["best_combined_cer"],
                "non_improving_epochs": state["non_improving_epochs"],
                "seconds": report["seconds"],
                "requested_views": report["requested_views"],
                "fallbacks": report["fallbacks"],
            }
            write_json_atomic(run / "progress.json", progress)
            print(json.dumps(progress), flush=True)
            if stop_after is not None and state["epoch"] >= stop_after:
                return {"status": "ENGINEERING_PAUSE", "epoch": state["epoch"]}
        result = {
            "status": (
                "RESIDUAL_SMOKE_COMPLETE" if smoke else "RESIDUAL_TRAINING_COMPLETE"
            ),
            "epochs": state["epoch"],
            "best_epoch": state["best_epoch"],
            "best_model_sha256": state["best_model_sha256"],
            "frozen_b2_unchanged": True,
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
                "resume": "Rerun identical train command; interrupted epoch is repeated",
            },
        )
        raise


def final_evaluate(
    tf: Any, rows: list[dict[str, Any]], run: Path, smoke: bool = False
) -> dict[str, Any]:
    check_run(run, smoke)
    if json.loads((run / "run_identity.json").read_text()) != run_identity(rows, smoke):
        raise ValueError("[residual/evaluate] Run identity mismatch")
    state = json.loads((run / "committed_epoch.json").read_text())
    best = Path(state["best_model_path"])
    if sha256(best) != state["best_model_sha256"]:
        raise ValueError("[residual/evaluate] Best checkpoint changed")
    model = tf.keras.models.load_model(best, compile=False)
    cache = ResidualCache()
    dev = [r for r in rows if r["split_role"] == "DEV"]
    reference_report = evaluate(tf, ReferenceSteps(tf), cache, dev)
    residual = evaluate(tf, ResidualSteps(tf, model), cache, dev)
    decision = outcome(reference_report, residual, smoke)
    result = {
        "schema_version": "apphear.fingerspelling.residual_evaluation.v1",
        "status": "RESIDUAL_VISUAL_FINAL_EVALUATED",
        "best_epoch": state["best_epoch"],
        "base_checkpoint_sha256": config()["base_checkpoint_sha256"],
        "residual_checkpoint_sha256": state["best_model_sha256"],
        "decoder_blank_penalty": config()["blank_penalty"],
        "decoder_retuned": False,
        "frozen_b2": reference_report,
        "residual": residual,
        "decision": decision,
        "test_accessed": False,
        "smoke_only": smoke,
    }
    write_json_atomic(run / "final_evaluation.json", result)
    return {
        "status": result["status"],
        "best_epoch": state["best_epoch"],
        "reference_combined_cer": reference_report["balanced_fixed_cer"],
        "residual_combined_cer": residual["balanced_fixed_cer"],
        "decision": decision["status"],
        "report": str(run / "final_evaluation.json"),
    }


def smoke() -> dict[str, Any]:
    rows = smoke_rows(b2.dataset(b2.DEFAULT_DATA))
    if status(rows, True)["status"] != "RESIDUAL_VISUAL_VALID":
        raise ValueError("[residual/smoke] Prepare smoke appearance records first")
    tf = reference.tensorflow(b2.policy()[1])
    cache = ResidualCache()
    with single_writer(SMOKE_RUN):
        first = engine(tf, rows, SMOKE_RUN, True, 1)
        completion = engine(tf, rows, SMOKE_RUN, True)
        reports = [
            json.loads(p.read_text())
            for p in sorted((SMOKE_RUN / "epochs").glob("*.json"))
        ]
        choices = [c for r in reports for c in r["temporal_choices"]]
        for r in [r for r in rows if r["split_role"] == "TRAIN"]:
            if {
                c["requested"] for c in choices if c["sample_id"] == r["sample_id"]
            } != {"native", "intermediate", "phone"}:
                raise ValueError("[residual/smoke] Missing cadence exposure")
        if any(c["headroom"] < 0 for c in choices):
            raise ValueError("[residual/smoke] Infeasible training view")
        model = tf.keras.models.load_model(
            json.loads((SMOKE_RUN / "committed_epoch.json").read_text())[
                "best_model_path"
            ],
            compile=False,
        )
        b = base_model(tf)
        errors = []
        for view in ["native", "intermediate", "phone"]:
            x, mask, _, _, _ = cache.batch(rows[:2], view)
            x[:, :, -2:] = 0
            expected = b([x[:, :, :405], mask], training=False).numpy()
            actual = model([x, mask], training=True).numpy()
            errors.append(float(np.max(np.abs(expected - actual))))
        if max(errors) > 1e-6:
            raise ValueError("[residual/smoke] Zero-quality B2 parity failed")
        evaluation = final_evaluate(tf, rows, SMOKE_RUN, True)
    result = {
        "status": "RESIDUAL_VISUAL_SMOKE_PASS",
        "counts": dict(Counter(r["split_role"] for r in rows)),
        "zero_quality_max_abs_errors": errors,
        "trainable_branch_only": True,
        "frozen_b2_unchanged": True,
        "pause": first,
        "completion": completion,
        "resume_verification": json.loads(
            (SMOKE_RUN / "resume_verification.json").read_text()
        ),
        "ctc_fallbacks": sum(c["fallback"] for c in choices),
        "evaluation": evaluation,
        "config_sha256": sha256(CONFIG),
        "code": run_identity(rows, True)["code"],
        "test_accessed": False,
    }
    write_json_atomic(EVIDENCE / "smoke.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["preflight", "smoke", "train", "status", "evaluate"]
    )
    args = parser.parse_args()
    if args.command == "preflight":
        result = preflight()
    elif args.command == "smoke":
        result = smoke()
    elif args.command == "status":
        result = (
            json.loads((RUN / "progress.json").read_text())
            if (RUN / "progress.json").exists()
            else {"status": "NOT_STARTED"}
        )
    else:
        preflight()
        passed = json.loads((EVIDENCE / "smoke.json").read_text())
        rows = b2.dataset(b2.DEFAULT_DATA)
        if (
            passed["status"] != "RESIDUAL_VISUAL_SMOKE_PASS"
            or passed["config_sha256"] != sha256(CONFIG)
            or passed["code"] != run_identity(smoke_rows(rows), True)["code"]
        ):
            raise ValueError("[residual/preflight] Matching engineering smoke required")
        tf = reference.tensorflow(b2.policy()[1])
        with single_writer(RUN):
            result = (
                engine(tf, rows, RUN)
                if args.command == "train"
                else final_evaluate(tf, rows, RUN)
            )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
