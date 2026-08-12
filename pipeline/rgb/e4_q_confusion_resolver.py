"""E4-Q focused confusion resolver for GOOD/SORRY/HELP/BECOME.

Experiment-only. Compares base landmarks, derived landmark-motion features, and
class-balanced derived training. No Android or production assets are modified.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.features.contract import SCHEMA_VERSION
from pipeline.rgb.e3_b4_landmark_temporal import _build_model, _inputs_for, _load_weights_model
from pipeline.rgb.e3_b5_landmark_temporal_scale import _evaluate
from pipeline.rgb.e3_b6_feature_augmentation import build_augmented_features
from pipeline.rgb.e4_p_existing_feature_20sign_pressure import (
    SPLITS,
    SPLIT_NAMES,
    _append,
    _asl_block,
    _empty_parts,
    _load_core,
    _load_vocab,
    _local_block,
    _normalize,
    _source_class_counts,
    _split_counts,
    _write_csv,
    _write_json,
)

DEFAULT_CORE_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_j_reliable_core_3sign_pilot_01")
DEFAULT_ASL_FEATURE_DIR = Path(r"F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational")
DEFAULT_LOCAL_FEATURE_PATH = Path(r"F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_recorded_local_pc_236\recorded.npz")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_q_confusion_resolver_sorry_become_help_01")
CLASSES = ["GOOD", "SORRY", "HELP", "BECOME"]
CORE_CLASSES = ["GOOD", "SORRY"]
CANDIDATE_CLASSES = ["HELP", "BECOME"]
VARIANTS = ["base_conv1d", "derived_conv1d", "derived_balanced_conv1d"]
SEEDS = [101, 202, 303]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _class_counts(y: np.ndarray, split_index: np.ndarray, classes: list[str]) -> dict[str, dict[str, int]]:
    return {split: {classes[cid]: int(np.sum((y == cid) & (split_index == sid))) for cid in range(len(classes))} for split, sid in SPLITS.items()}


def _core_block(core_run: Path, classes: list[str]) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    data = _load_core(core_run)
    source_map = {"GOOD": 0, "SORRY": 2}
    selected: list[int] = []
    labels: list[int] = []
    for gloss in CORE_CLASSES:
        idx = np.flatnonzero(data["y"] == source_map[gloss])
        selected.extend(idx.tolist())
        labels.extend([classes.index(gloss)] * len(idx))
    selected_arr = np.asarray(selected, dtype=np.int64)
    labels_arr = np.asarray(labels, dtype=np.int64)
    order = np.argsort(selected_arr)
    selected_arr = selected_arr[order]
    labels_arr = labels_arr[order]
    rows = []
    for out_i, src_i in enumerate(selected_arr):
        split_id = int(data["split_index"][src_i])
        class_id = int(labels_arr[out_i])
        rows.append({
            "sample_id": str(data["sample_ids"][src_i]),
            "source_id": "local_core_e4j",
            "source_split": SPLIT_NAMES[split_id],
            "split": SPLIT_NAMES[split_id],
            "canonical_gloss": classes[class_id],
            "class_id": class_id,
            "participant_id": str(data["participant_ids"][src_i]),
            "source_index": int(src_i),
            "source_path": str((core_run / "dataset" / "landmark_features.npz").resolve()),
            "notes": "selected_and_remapped_from_e4_j_reliable_core",
        })
    block = {
        "landmarks": data["landmarks"][selected_arr],
        "frame_mask": data["frame_mask"][selected_arr],
        "y": labels_arr,
        "split_index": data["split_index"][selected_arr],
        "lengths": data["lengths"][selected_arr],
        "participant_ids": data["participant_ids"][selected_arr],
        "sample_ids": data["sample_ids"][selected_arr],
        "source_ids": np.asarray(["local_core_e4j"] * len(selected_arr)),
    }
    return _normalize(block), rows


def _class_weight(y: np.ndarray, train_mask: np.ndarray, class_count: int) -> dict[int, float]:
    counts = np.bincount(y[train_mask], minlength=class_count).astype(np.float32)
    total = float(np.sum(counts))
    return {i: float(total / (class_count * max(c, 1.0))) for i, c in enumerate(counts)}


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for rel in ("dataset", "logs", "metrics", "models", "smoke"):
        (output / rel).mkdir(parents=True, exist_ok=True)
    if list(args.classes) != CLASSES:
        raise ValueError(f"E4-Q class contract is fixed: {CLASSES}")
    vocab = _load_vocab(args.asl_feature_dir)
    parts = _empty_parts()
    rows: list[dict[str, Any]] = []
    for block, block_rows in (
        _core_block(args.core_run, CLASSES),
        _asl_block(args.asl_feature_dir, vocab, CLASSES, CANDIDATE_CLASSES),
        _local_block(args.local_feature_path, vocab, CLASSES, CANDIDATE_CLASSES),
    ):
        _append(parts, block)
        rows.extend(block_rows)
    dataset = _normalize({k: np.concatenate(v, axis=0) for k, v in parts.items()})
    order = np.lexsort((dataset["sample_ids"], dataset["source_ids"], dataset["split_index"]))
    dataset = {k: v[order] for k, v in dataset.items()}
    sample_order = {sample_id: i for i, sample_id in enumerate(dataset["sample_ids"].tolist())}
    rows = sorted(rows, key=lambda r: sample_order[r["sample_id"]])
    derived, derived_schema = build_augmented_features(dataset["landmarks"], dataset["frame_mask"])
    np.savez_compressed(output / "dataset" / "base_features.npz", **dataset)
    np.savez_compressed(
        output / "dataset" / "derived_features.npz",
        features=derived,
        frame_mask=dataset["frame_mask"],
        y=dataset["y"],
        split_index=dataset["split_index"],
        lengths=dataset["lengths"],
        participant_ids=dataset["participant_ids"],
        sample_ids=dataset["sample_ids"],
        source_ids=dataset["source_ids"],
    )
    fields = ["sample_id", "source_id", "source_split", "split", "canonical_gloss", "class_id", "participant_id", "source_index", "source_path", "notes"]
    _write_csv(output / "pilot_manifest.csv", rows, fields)
    _write_csv(output / "selected_classes.csv", [{"class_id": i, "gloss": g} for i, g in enumerate(CLASSES)], ["class_id", "gloss"])
    config = {
        "experiment": "e4_q_confusion_resolver_sorry_become_help_v1",
        "purpose": "focused resolver for E4-P SORRY collapse against BECOME/HELP",
        "run_dir": str(output.resolve()),
        "core_run": str(args.core_run.resolve()),
        "asl_feature_dir": str(args.asl_feature_dir.resolve()),
        "local_feature_path": str(args.local_feature_path.resolve()),
        "schema_version": SCHEMA_VERSION,
        "classes": CLASSES,
        "class_count": len(CLASSES),
        "base_input_shape": [96, 258],
        "derived_input_shape": [int(v) for v in derived.shape[1:]],
        "derived_schema": derived_schema,
        "active_rows": int(dataset["landmarks"].shape[0]),
        "split_counts": _split_counts(dataset["split_index"]),
        "class_counts": _class_counts(dataset["y"], dataset["split_index"], CLASSES),
        "source_counts": dict(sorted(Counter(dataset["source_ids"].tolist()).items())),
        "source_class_counts": _source_class_counts(dataset["y"], dataset["split_index"], dataset["source_ids"], CLASSES),
        "variants": list(args.variants),
        "variant_model": {"base_conv1d": "base", "derived_conv1d": "derived", "derived_balanced_conv1d": "derived"},
        "variant_training": {"base_conv1d": "standard", "derived_conv1d": "standard", "derived_balanced_conv1d": "class_weighted"},
        "seeds": list(args.seeds),
        "batch_size": int(args.batch_size),
        "epochs": int(args.epochs),
        "learning_rate": float(args.learning_rate),
        "random_baseline": 1.0 / len(CLASSES),
        "long_steps": ["run"],
        "gate": {"mean_latest_test_min": 0.85, "min_sorry_latest_test_min": 0.85, "min_core_latest_test_min": 0.85, "min_candidate_latest_test_min": 0.70, "max_predicted_class_share": 0.45},
        "warnings": [
            "Resolver experiment only; no Android integration or production recognizer replacement.",
            "HELP/BECOME test rows are ASL Citizen only; local HELP/BECOME held-out coverage is absent in existing tensors.",
            "If derived features pass, Kotlin parity/skew tests are required before runtime use.",
            "If all landmark variants fail, the next resolver should use RGB hand/chest crops or dataset review.",
        ],
    }
    _write_json(output / "pilot_config.json", config)
    _write_json(output / "logs" / "prepare_summary.json", {**config, "passed": True})
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def _load_variant(run_dir: Path, variant: str):
    if variant == "base_conv1d":
        data = np.load(run_dir / "dataset" / "base_features.npz", allow_pickle=False)
        return data["landmarks"].astype(np.float32), data["frame_mask"].astype(bool), data["y"].astype(np.int64), data["split_index"].astype(np.int64), data["source_ids"].astype(str)
    data = np.load(run_dir / "dataset" / "derived_features.npz", allow_pickle=False)
    return data["features"].astype(np.float32), data["frame_mask"].astype(bool), data["y"].astype(np.int64), data["split_index"].astype(np.int64), data["source_ids"].astype(str)


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf
    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    out: dict[str, Any] = {"experiment": config["experiment"], "run_dir": str(run_dir.resolve()), "variants": {}}
    for variant in config["variants"]:
        x, mask, y, split, _source = _load_variant(run_dir, variant)
        rows = np.flatnonzero(split == SPLITS["train"])[: max(4, min(args.rows, 12))]
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(12345)
        model = _build_model("conv1d_baseline", tuple(x.shape[1:]), int(config["class_count"]), float(config["learning_rate"]))
        probs = model.predict(_inputs_for("conv1d_baseline", x[rows], mask[rows]), batch_size=2, verbose=0)
        loss = model.train_on_batch(_inputs_for("conv1d_baseline", x[rows], mask[rows]), y[rows])
        weights = run_dir / "smoke" / f"{variant}.weights.h5"
        model.save_weights(weights)
        out["variants"][variant] = {"input_shape": [int(v) for v in x.shape[1:]], "rows": int(len(rows)), "forward_shape": [int(v) for v in probs.shape], "train_on_batch": [float(v) for v in np.atleast_1d(loss).tolist()], "weights_saved": str(weights.resolve())}
    _write_json(run_dir / "smoke" / "smoke_summary.json", out)
    return out


def _source_eval(model: Any, x: np.ndarray, mask: np.ndarray, y: np.ndarray, split: np.ndarray, sources: np.ndarray, batch_size: int) -> dict[str, Any]:
    probs = model.predict(_inputs_for("conv1d_baseline", x, mask), batch_size=batch_size, verbose=0)
    pred = np.argmax(probs, axis=1)
    out: dict[str, Any] = {}
    for source in sorted(set(sources.tolist())):
        out[source] = {}
        sm = sources == source
        for split_name, sid in SPLITS.items():
            m = sm & (split == sid)
            if not np.any(m):
                out[source][split_name] = {"count": 0, "accuracy": None, "per_class": []}
                continue
            per_class = []
            for cid, gloss in enumerate(CLASSES):
                cm = m & (y == cid)
                if np.any(cm):
                    per_class.append({"gloss": gloss, "count": int(np.sum(cm)), "correct": int(np.sum(pred[cm] == y[cm])), "accuracy": float(np.mean(pred[cm] == y[cm]))})
            out[source][split_name] = {"count": int(np.sum(m)), "accuracy": float(np.mean(pred[m] == y[m])), "per_class": per_class, "predicted_class_counts": {CLASSES[int(cid)]: int(count) for cid, count in zip(*np.unique(pred[m], return_counts=True))}}
    return out


def _gate(metrics: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    by_variant: dict[str, Any] = {}
    for variant, seeds in metrics["variants"].items():
        latest_tests = []
        min_sorry = []
        min_core = []
        min_candidate = []
        max_pred_share = []
        for payload in seeds.values():
            test = payload["latest"]["test"]
            latest_tests.append(float(test["accuracy"]))
            by_gloss = {row["gloss"]: float(row["accuracy"]) for row in test.get("per_class", [])}
            min_sorry.append(by_gloss.get("SORRY", 0.0))
            min_core.append(min(by_gloss.get(g, 0.0) for g in CORE_CLASSES))
            min_candidate.append(min(by_gloss.get(g, 0.0) for g in CANDIDATE_CLASSES))
            counts = test.get("predicted_class_counts", {})
            total = sum(int(v) for v in counts.values()) or 1
            max_pred_share.append(max((int(v) for v in counts.values()), default=0) / total)
        g = config["gate"]
        passed = bool(latest_tests and float(np.mean(latest_tests)) >= g["mean_latest_test_min"] and min(min_sorry) >= g["min_sorry_latest_test_min"] and min(min_core) >= g["min_core_latest_test_min"] and min(min_candidate) >= g["min_candidate_latest_test_min"] and max(max_pred_share) <= g["max_predicted_class_share"])
        by_variant[variant] = {"mean_latest_test": float(np.mean(latest_tests)) if latest_tests else 0.0, "min_sorry_latest_test": float(min(min_sorry)) if min_sorry else 0.0, "min_core_latest_test": float(min(min_core)) if min_core else 0.0, "min_candidate_latest_test": float(min(min_candidate)) if min_candidate else 0.0, "max_predicted_class_share": float(max(max_pred_share)) if max_pred_share else 0.0, "passed": passed}
    best = max(by_variant, key=lambda k: by_variant[k]["mean_latest_test"]) if by_variant else None
    any_passed = any(v["passed"] for v in by_variant.values())
    return {"by_variant": by_variant, "best_mean_latest_test_variant": best, "passed": bool(any_passed), "decision": "resolver_candidate_for_followup" if any_passed else "landmark_resolver_failed_try_rgb_or_data_review"}


def run(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf
    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    metrics: dict[str, Any] = {"experiment": config["experiment"], "run_dir": str(run_dir.resolve()), "classes": CLASSES, "variants": {}, "passed": True}
    for variant in config["variants"]:
        x, mask, y, split, sources = _load_variant(run_dir, variant)
        train_mask = split == SPLITS["train"]
        val_mask = split == SPLITS["val"]
        cw = _class_weight(y, train_mask, len(CLASSES)) if config["variant_training"][variant] == "class_weighted" else None
        metrics["variants"][variant] = {}
        for seed in config["seeds"]:
            seed = int(seed)
            tf.keras.backend.clear_session()
            tf.keras.utils.set_random_seed(seed)
            seed_dir = run_dir / "models" / variant / f"seed_{seed}"
            seed_dir.mkdir(parents=True, exist_ok=True)
            latest = seed_dir / "latest.weights.h5"
            best = seed_dir / "best.weights.h5"
            epoch_file = run_dir / "logs" / f"{variant}_seed_{seed}_epoch_count.txt"
            history_path = run_dir / "logs" / f"{variant}_seed_{seed}_history.csv"
            if latest.exists() and not args.resume:
                raise FileExistsError(f"{variant} seed {seed}: latest weights exist; rerun with --resume")
            model = _build_model("conv1d_baseline", tuple(x.shape[1:]), len(CLASSES), float(config["learning_rate"]))
            initial_epoch = 0
            if args.resume and latest.exists():
                model.load_weights(latest)
                initial_epoch = int(epoch_file.read_text(encoding="utf-8"))
            history = model.fit(
                _inputs_for("conv1d_baseline", x[train_mask], mask[train_mask]),
                y[train_mask],
                validation_data=(_inputs_for("conv1d_baseline", x[val_mask], mask[val_mask]), y[val_mask]),
                batch_size=int(config["batch_size"]),
                epochs=initial_epoch + int(config["epochs"]),
                initial_epoch=initial_epoch,
                class_weight=cw,
                callbacks=[
                    tf.keras.callbacks.ModelCheckpoint(str(best), monitor="val_accuracy", mode="max", save_best_only=True, save_weights_only=True),
                    tf.keras.callbacks.CSVLogger(str(history_path), append=history_path.exists()),
                ],
                verbose=2,
            )
            model.save_weights(latest)
            total_epochs = initial_epoch + int(config["epochs"])
            epoch_file.write_text(str(total_epochs), encoding="utf-8")
            best_model = _load_weights_model("conv1d_baseline", tuple(x.shape[1:]), len(CLASSES), float(config["learning_rate"]), best)
            metrics["variants"][variant][str(seed)] = {
                "input_shape": [int(v) for v in x.shape[1:]],
                "training": config["variant_training"][variant],
                "class_weight": cw,
                "latest": _evaluate("conv1d_baseline", model, x, mask, y, split, int(config["batch_size"]), CLASSES),
                "best": _evaluate("conv1d_baseline", best_model, x, mask, y, split, int(config["batch_size"]), CLASSES),
                "source_aware_latest": _source_eval(model, x, mask, y, split, sources, int(config["batch_size"])),
                "epoch_count_total": total_epochs,
                "history_last": {k: float(v[-1]) for k, v in history.history.items() if v},
            }
            _write_json(run_dir / "metrics" / "metrics_partial.json", metrics)
    metrics["gate"] = _gate(metrics, config)
    _write_json(run_dir / "metrics" / "metrics.json", metrics)
    (run_dir / "metrics" / "metrics.md").write_text(_metrics_markdown(metrics), encoding="utf-8")
    return metrics


def _metrics_markdown(metrics: dict[str, Any]) -> str:
    gate = metrics.get("gate", {})
    lines = ["# E4-Q Confusion Resolver Metrics", "", "Experiment-only result. This is not a production Android model.", "", f"- Classes: {', '.join(CLASSES)}", f"- Gate passed: `{gate.get('passed')}`", f"- Decision: `{gate.get('decision')}`", f"- Best mean latest-test variant: `{gate.get('best_mean_latest_test_variant')}`", "", "| Variant | Seed | Latest Test | Best Test | Latest SORRY | Best SORRY |", "|---|---:|---:|---:|---:|---:|"]
    for variant, seeds in metrics.get("variants", {}).items():
        for seed, payload in seeds.items():
            latest_pc = {row["gloss"]: row["accuracy"] for row in payload["latest"]["test"].get("per_class", [])}
            best_pc = {row["gloss"]: row["accuracy"] for row in payload["best"]["test"].get("per_class", [])}
            lines.append(f"| {variant} | {seed} | {payload['latest']['test']['accuracy']:.4f} | {payload['best']['test']['accuracy']:.4f} | {latest_pc.get('SORRY', 0.0):.4f} | {best_pc.get('SORRY', 0.0):.4f} |")
    lines.extend(["", "```json", json.dumps(gate, indent=2), "```", ""])
    return "\n".join(lines)


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    for rel in ("pilot_config.json", "README_RUN.md", "pilot_manifest.csv", "selected_classes.csv", "dataset/base_features.npz", "dataset/derived_features.npz"):
        if not (run_dir / rel).exists():
            errors.append(f"missing output: {rel}")
    config_path = run_dir / "pilot_config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if config.get("experiment") != "e4_q_confusion_resolver_sorry_become_help_v1":
            errors.append("unexpected experiment id")
        base = np.load(run_dir / "dataset" / "base_features.npz", allow_pickle=False)
        derived = np.load(run_dir / "dataset" / "derived_features.npz", allow_pickle=False)
        if list(base["landmarks"].shape[1:]) != [96, 258]:
            errors.append(f"base shape mismatch: {list(base['landmarks'].shape)}")
        if list(derived["features"].shape[1:]) != config.get("derived_input_shape"):
            errors.append("derived shape mismatch")
        if int(base["landmarks"].shape[0]) != int(config.get("active_rows", -1)):
            errors.append("base row count mismatch")
        if np.isnan(derived["features"]).any() or np.isinf(derived["features"]).any():
            errors.append("derived tensor contains NaN or Inf")
    if args.require_metrics and not (run_dir / "metrics" / "metrics.json").exists():
        errors.append("missing output: metrics/metrics.json")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join([
        "# E4-Q Confusion Resolver: SORRY/BECOME/HELP",
        "",
        "Focused resolver experiment only. No Android or production files are changed.",
        "",
        f"- Classes: {', '.join(config['classes'])}",
        f"- Active rows: {config['active_rows']}",
        f"- Split counts: {config['split_counts']}",
        f"- Variants: {', '.join(config['variants'])}",
        "",
        "```powershell",
        'cd "F:\\ASL DATASET\\5. Apphear3"',
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_q_confusion_resolver smoke --run-dir "{run_dir}"',
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_q_confusion_resolver run --run-dir "{run_dir}"',
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_q_confusion_resolver check --run-dir "{run_dir}" --require-metrics',
        "```",
        "",
    ]) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-Q confusion-group resolver")
    sub = parser.add_subparsers(dest="command", required=True)
    pp = sub.add_parser("prepare")
    pp.add_argument("--core-run", type=Path, default=DEFAULT_CORE_RUN)
    pp.add_argument("--asl-feature-dir", type=Path, default=DEFAULT_ASL_FEATURE_DIR)
    pp.add_argument("--local-feature-path", type=Path, default=DEFAULT_LOCAL_FEATURE_PATH)
    pp.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    pp.add_argument("--classes", nargs="+", default=CLASSES)
    pp.add_argument("--variants", nargs="+", default=VARIANTS)
    pp.add_argument("--seeds", nargs="+", type=int, default=SEEDS)
    pp.add_argument("--batch-size", type=int, default=8)
    pp.add_argument("--epochs", type=int, default=25)
    pp.add_argument("--learning-rate", type=float, default=5e-4)
    pp.add_argument("--overwrite", action="store_true")
    sp = sub.add_parser("smoke")
    sp.add_argument("--run-dir", type=Path, required=True)
    sp.add_argument("--rows", type=int, default=12)
    rp = sub.add_parser("run")
    rp.add_argument("--run-dir", type=Path, required=True)
    rp.add_argument("--resume", action="store_true")
    cp = sub.add_parser("check")
    cp.add_argument("--run-dir", type=Path, required=True)
    cp.add_argument("--require-metrics", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "smoke":
            result = smoke(args)
        elif args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileExistsError, FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-q] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
