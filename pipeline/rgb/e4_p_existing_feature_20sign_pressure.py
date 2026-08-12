"""E4-P existing-feature 20-sign batch pressure test.

Experiment-only. Builds one larger landmark-only batch from already-extracted ASL Citizen
features plus already-extracted local supplementary feature tensors. No Android assets,
production recognizer files, source videos, or source datasets are modified.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.features.contract import SCHEMA_VERSION
from pipeline.rgb.e3_b4_landmark_temporal import _build_model, _inputs_for, _load_weights_model
from pipeline.rgb.e4_b_strict_runner import check as _base_check
from pipeline.rgb.e4_b_strict_runner import run as _base_run

DEFAULT_CORE_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_j_reliable_core_3sign_pilot_01")
DEFAULT_E4M_RUN = Path("artifacts/recognition_upgrade/e4_generalization/e4_m_dual_source_candidate_screen_01")
DEFAULT_ASL_FEATURE_DIR = Path(r"F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational")
DEFAULT_LOCAL_FEATURE_PATH = Path(r"F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_recorded_local_pc_236\recorded.npz")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_p_existing_feature_20sign_pressure_01")
CORE_CLASSES = ["GOOD", "HELLO", "SORRY"]
PROVEN_CANDIDATES = ["HAVE", "KNOW"]
DEFAULT_CLASSES = [
    "GOOD", "HELLO", "SORRY", "HAVE", "KNOW", "WANT2", "HELP", "NICE", "KEEP", "START",
    "MEET", "CLOSE", "GIVE", "TALK1", "WHAT1", "CLEAN", "LEAVE", "STAND2", "BECOME", "WASH2",
]
EXCLUDED_GLOSSES = {"GET", "WELCOME2", "MAKE", "BYE", "NO", "YES", "THANKYOU"}
SPLITS = {"train": 0, "val": 1, "test": 2}
SPLIT_NAMES = {v: k for k, v in SPLITS.items()}
DEFAULT_BRANCHES = ["conv1d_baseline"]
DEFAULT_SEEDS = [101, 202, 303]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_vocab(feature_dir: Path) -> dict[str, int]:
    for path in (feature_dir / "vocab.json", feature_dir.parent / "features_conversational" / "vocab.json"):
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return {str(k).upper(): int(v) for k, v in data.items()}
    raise FileNotFoundError(f"missing vocab.json near {feature_dir}")


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    if not path.exists():
        raise FileNotFoundError(f"missing feature tensor: {path}")
    data = np.load(path, allow_pickle=False)
    return {
        "X": data["X"].astype(np.float32),
        "frame_mask": data["frame_mask"].astype(bool),
        "lengths": data["lengths"].astype(np.int32),
        "y": data["y"].astype(np.int64),
        "participant_ids": np.asarray(data["participant_ids"]).astype(str),
    }


def _load_core(core_run: Path) -> dict[str, np.ndarray]:
    path = core_run / "dataset" / "landmark_features.npz"
    if not path.exists():
        raise FileNotFoundError(f"missing E4-J core dataset: {path}")
    data = np.load(path, allow_pickle=False)
    return {
        "landmarks": data["landmarks"].astype(np.float32),
        "frame_mask": data["frame_mask"].astype(bool),
        "y": data["y"].astype(np.int64),
        "split_index": data["split_index"].astype(np.int64),
        "lengths": data["lengths"].astype(np.int32),
        "participant_ids": np.asarray(data["participant_ids"]).astype(str),
        "sample_ids": np.asarray(data["sample_ids"]).astype(str),
    }


def _normalize(dataset: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {
        "landmarks": dataset["landmarks"].astype(np.float32),
        "frame_mask": dataset["frame_mask"].astype(bool),
        "y": dataset["y"].astype(np.int64),
        "split_index": dataset["split_index"].astype(np.int64),
        "lengths": dataset["lengths"].astype(np.int32),
        "participant_ids": dataset["participant_ids"].astype(str),
        "sample_ids": dataset["sample_ids"].astype(str),
        "source_ids": dataset["source_ids"].astype(str),
    }


def _split_counts(split_index: np.ndarray) -> dict[str, int]:
    return {name: int(np.sum(split_index == sid)) for name, sid in SPLITS.items()}


def _class_counts(y: np.ndarray, split_index: np.ndarray, classes: list[str]) -> dict[str, dict[str, int]]:
    return {split: {classes[cid]: int(np.sum((y == cid) & (split_index == sid))) for cid in range(len(classes))} for split, sid in SPLITS.items()}


def _source_class_counts(y: np.ndarray, split_index: np.ndarray, source_ids: np.ndarray, classes: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for source in sorted(set(source_ids.tolist())):
        out[source] = {}
        smask = source_ids == source
        for split, sid in SPLITS.items():
            mask = smask & (split_index == sid)
            out[source][split] = {classes[cid]: int(np.sum(mask & (y == cid))) for cid in range(len(classes))}
    return out


def _local_split(indices: np.ndarray, participant_ids: np.ndarray) -> np.ndarray:
    split_ids = np.full(indices.size, SPLITS["train"], dtype=np.int64)
    by_pid: dict[str, list[int]] = defaultdict(list)
    for local_pos, source_idx in enumerate(indices):
        by_pid[str(participant_ids[source_idx])].append(local_pos)
    for pid, positions in by_pid.items():
        positions = sorted(positions)
        if pid == "6F7328-S001":
            split_ids[positions] = SPLITS["test"]
        elif len(positions) >= 4:
            val_count = max(1, min(3, len(positions) // 4))
            split_ids[positions[-val_count:]] = SPLITS["val"]
    return split_ids


def _empty_parts() -> dict[str, list[np.ndarray]]:
    return {key: [] for key in ("landmarks", "frame_mask", "y", "split_index", "lengths", "participant_ids", "sample_ids", "source_ids")}


def _append(parts: dict[str, list[np.ndarray]], block: dict[str, np.ndarray]) -> None:
    for key in parts:
        parts[key].append(block[key])


def _core_block(core_run: Path, classes: list[str]) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    data = _load_core(core_run)
    rows = []
    source_ids = np.asarray(["local_core_e4j"] * data["landmarks"].shape[0])
    for idx, sample_id in enumerate(data["sample_ids"]):
        split_id = int(data["split_index"][idx])
        class_id = int(data["y"][idx])
        rows.append({
            "sample_id": str(sample_id),
            "source_id": "local_core_e4j",
            "source_split": SPLIT_NAMES[split_id],
            "split": SPLIT_NAMES[split_id],
            "canonical_gloss": classes[class_id],
            "class_id": class_id,
            "participant_id": str(data["participant_ids"][idx]),
            "source_index": idx,
            "source_path": str((core_run / "dataset" / "landmark_features.npz").resolve()),
            "notes": "copied_from_e4_j_reliable_core",
        })
    return {**data, "source_ids": source_ids}, rows


def _asl_block(feature_dir: Path, vocab: dict[str, int], classes: list[str], candidate_classes: list[str]) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    parts = _empty_parts()
    rows: list[dict[str, Any]] = []
    for split, split_id in SPLITS.items():
        data = _load_npz(feature_dir / f"{split}.npz")
        for gloss in candidate_classes:
            source_class = vocab[gloss]
            class_id = classes.index(gloss)
            indices = np.flatnonzero(data["y"] == source_class)
            if indices.size == 0:
                continue
            sample_ids = np.asarray([f"asl_{split}_{gloss}_{int(i):05d}" for i in indices])
            source_id = f"asl_citizen_{split}"
            _append(parts, {
                "landmarks": data["X"][indices],
                "frame_mask": data["frame_mask"][indices],
                "y": np.full(indices.size, class_id, dtype=np.int64),
                "split_index": np.full(indices.size, split_id, dtype=np.int64),
                "lengths": data["lengths"][indices],
                "participant_ids": data["participant_ids"][indices],
                "sample_ids": sample_ids,
                "source_ids": np.asarray([source_id] * indices.size),
            })
            for local_idx, source_index in enumerate(indices):
                rows.append({
                    "sample_id": str(sample_ids[local_idx]),
                    "source_id": source_id,
                    "source_split": split,
                    "split": split,
                    "canonical_gloss": gloss,
                    "class_id": class_id,
                    "participant_id": str(data["participant_ids"][source_index]),
                    "source_index": int(source_index),
                    "source_path": str((feature_dir / f"{split}.npz").resolve()),
                    "notes": "selected_from_asl_citizen_streaming_conversational",
                })
    return _normalize({key: np.concatenate(value, axis=0) for key, value in parts.items()}), rows


def _local_block(path: Path, vocab: dict[str, int], classes: list[str], candidate_classes: list[str]) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    data = _load_npz(path)
    parts = _empty_parts()
    rows: list[dict[str, Any]] = []
    for gloss in candidate_classes:
        source_class = vocab[gloss]
        class_id = classes.index(gloss)
        indices = np.flatnonzero(data["y"] == source_class)
        if indices.size == 0:
            continue
        split_ids = _local_split(indices, data["participant_ids"])
        sample_ids = np.asarray([f"local_recorded_{gloss}_{int(i):05d}" for i in indices])
        _append(parts, {
            "landmarks": data["X"][indices],
            "frame_mask": data["frame_mask"][indices],
            "y": np.full(indices.size, class_id, dtype=np.int64),
            "split_index": split_ids,
            "lengths": data["lengths"][indices],
            "participant_ids": data["participant_ids"][indices],
            "sample_ids": sample_ids,
            "source_ids": np.asarray(["local_recorded_features"] * indices.size),
        })
        for local_idx, source_index in enumerate(indices):
            rows.append({
                "sample_id": str(sample_ids[local_idx]),
                "source_id": "local_recorded_features",
                "source_split": "generated_from_participant",
                "split": SPLIT_NAMES[int(split_ids[local_idx])],
                "canonical_gloss": gloss,
                "class_id": class_id,
                "participant_id": str(data["participant_ids"][source_index]),
                "source_index": int(source_index),
                "source_path": str(path.resolve()),
                "notes": "selected_from_existing_recorded_local_pc_236_tensor; one-signer local rows are diagnostic",
            })
    return _normalize({key: np.concatenate(value, axis=0) for key, value in parts.items()}), rows


def _candidate_evidence(e4m_run: Path, classes: list[str]) -> list[dict[str, str]]:
    rows = _read_csv(e4m_run / "tables" / "candidate_inventory_ranked.csv")
    by_gloss = {row["gloss"].upper(): row for row in rows}
    missing = [gloss for gloss in classes if gloss not in by_gloss]
    if missing:
        raise ValueError(f"selected classes missing from E4-M inventory: {missing}")
    return [by_gloss[gloss] for gloss in classes]


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("dataset", "logs", "metrics", "models", "smoke", "tables"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    classes = list(args.classes)
    if classes != DEFAULT_CLASSES:
        raise ValueError(f"E4-P class contract is fixed for this screen: {DEFAULT_CLASSES}")
    bad = sorted(set(classes) & EXCLUDED_GLOSSES)
    if bad:
        raise ValueError(f"E4-P excludes unstable/rejected signs: {bad}")
    candidate_classes = [gloss for gloss in classes if gloss not in CORE_CLASSES]
    vocab = _load_vocab(args.asl_feature_dir)
    evidence_rows = _candidate_evidence(args.e4m_run, classes)
    parts = _empty_parts()
    rows: list[dict[str, Any]] = []
    for block, block_rows in (
        _core_block(args.core_run, classes),
        _asl_block(args.asl_feature_dir, vocab, classes, candidate_classes),
        _local_block(args.local_feature_path, vocab, classes, candidate_classes),
    ):
        _append(parts, block)
        rows.extend(block_rows)
    dataset = _normalize({key: np.concatenate(value, axis=0) for key, value in parts.items()})
    order = np.lexsort((dataset["sample_ids"], dataset["source_ids"], dataset["split_index"]))
    dataset = {key: value[order] for key, value in dataset.items()}
    sample_order = {sample_id: idx for idx, sample_id in enumerate(dataset["sample_ids"].tolist())}
    rows = sorted(rows, key=lambda row: sample_order[row["sample_id"]])
    np.savez_compressed(output / "dataset" / "landmark_features.npz", **dataset)
    np.savez_compressed(output / "dataset" / "source_metadata.npz", source_ids=dataset["source_ids"], sample_ids=dataset["sample_ids"], participant_ids=dataset["participant_ids"])
    fields = ["sample_id", "source_id", "source_split", "split", "canonical_gloss", "class_id", "participant_id", "source_index", "source_path", "notes"]
    _write_csv(output / "pilot_manifest.csv", rows, fields)
    _write_csv(output / "selected_classes.csv", [{"class_id": idx, "gloss": gloss} for idx, gloss in enumerate(classes)], ["class_id", "gloss"])
    _write_csv(output / "tables" / "selected_candidate_evidence.csv", evidence_rows, list(evidence_rows[0].keys()))
    source_counts = Counter(row["source_id"] for row in rows)
    one_signer_candidates = [row["gloss"] for row in evidence_rows if row["gloss"] not in CORE_CLASSES and int(row.get("local_feature_signer_count") or 0) < 2]
    config = {
        "experiment": "e4_p_existing_feature_20sign_pressure_v1",
        "purpose": "fast 20-sign landmark-only pressure test using existing ASL Citizen and local feature tensors after E4-O rejected GET",
        "run_dir": str(output.resolve()),
        "core_run": str(args.core_run.resolve()),
        "e4_m_run": str(args.e4m_run.resolve()),
        "asl_feature_dir": str(args.asl_feature_dir.resolve()),
        "local_feature_path": str(args.local_feature_path.resolve()),
        "input_shape": [96, 258],
        "schema_version": SCHEMA_VERSION,
        "classes": classes,
        "class_count": len(classes),
        "core_classes": CORE_CLASSES,
        "proven_candidates": PROVEN_CANDIDATES,
        "diagnostic_candidates": [gloss for gloss in candidate_classes if gloss not in PROVEN_CANDIDATES],
        "excluded_glosses": sorted(EXCLUDED_GLOSSES),
        "one_signer_local_candidates": one_signer_candidates,
        "active_rows": int(dataset["landmarks"].shape[0]),
        "split_counts": _split_counts(dataset["split_index"]),
        "class_counts": _class_counts(dataset["y"], dataset["split_index"], classes),
        "source_counts": dict(sorted(source_counts.items())),
        "source_class_counts": _source_class_counts(dataset["y"], dataset["split_index"], dataset["source_ids"], classes),
        "batch_size": int(args.batch_size),
        "epochs": int(args.epochs),
        "learning_rate": float(args.learning_rate),
        "branches": list(args.branches),
        "seeds": list(args.seeds),
        "random_baseline": 1.0 / len(classes),
        "long_steps": ["run"],
        "gate": {"mean_latest_test_min": 0.45, "core_class_test_min": 0.80, "candidate_class_test_min": 0.20, "max_predicted_class_share": 0.35},
        "warnings": [
            "This is a pressure test, not production training.",
            "Many candidates have only one local supplementary feature signer; local-source evidence is diagnostic.",
            "GET/WELCOME2 are excluded because E4-O failed on local extracted GET.",
            "No Android integration, TFLite export, or production recognizer replacement is authorized.",
        ],
    }
    _write_json(output / "pilot_config.json", config)
    _write_json(output / "logs" / "prepare_summary.json", {**config, "passed": True})
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf
    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    data = np.load(run_dir / "dataset" / "landmark_features.npz", allow_pickle=False)
    rows = min(int(args.rows), int(data["landmarks"].shape[0]))
    x = data["landmarks"][:rows].astype(np.float32)
    frame_mask = data["frame_mask"][:rows].astype(bool)
    y = data["y"][:rows].astype(np.int64)
    result: dict[str, Any] = {"rows": rows, "shape": [int(v) for v in x.shape], "branches": {}}
    for branch in config["branches"]:
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(12345)
        model = _build_model(branch, (96, 258), int(config["class_count"]), float(config["learning_rate"]))
        probs = model.predict(_inputs_for(branch, x, frame_mask), batch_size=2, verbose=0)
        loss = model.train_on_batch(_inputs_for(branch, x, frame_mask), y)
        weights_path = run_dir / "smoke" / f"{branch}.weights.h5"
        model.save_weights(weights_path)
        result["branches"][branch] = {"forward_shape": [int(v) for v in probs.shape], "train_on_batch": [float(v) for v in np.atleast_1d(loss).tolist()], "weights_saved": str(weights_path.resolve())}
    _write_json(run_dir / "smoke" / "smoke_summary.json", result)
    return result


def _source_eval(branch: str, model: Any, run_dir: Path, batch_size: int, classes: list[str]) -> dict[str, Any]:
    data = np.load(run_dir / "dataset" / "landmark_features.npz", allow_pickle=False)
    x = data["landmarks"].astype(np.float32)
    frame_mask = data["frame_mask"].astype(bool)
    y = data["y"].astype(np.int64)
    split_index = data["split_index"].astype(np.int64)
    source_ids = data["source_ids"].astype(str)
    probs = model.predict(_inputs_for(branch, x, frame_mask), batch_size=batch_size, verbose=0)
    pred = np.argmax(probs, axis=1)
    result: dict[str, Any] = {}
    for source in sorted(set(source_ids.tolist())):
        result[source] = {}
        source_mask = source_ids == source
        for split, sid in SPLITS.items():
            mask = source_mask & (split_index == sid)
            if not np.any(mask):
                result[source][split] = {"count": 0, "accuracy": None, "per_class": []}
                continue
            per_class = []
            for class_id, gloss in enumerate(classes):
                cmask = mask & (y == class_id)
                if np.any(cmask):
                    per_class.append({"gloss": gloss, "count": int(np.sum(cmask)), "correct": int(np.sum(pred[cmask] == y[cmask])), "accuracy": float(np.mean(pred[cmask] == y[cmask]))})
            result[source][split] = {"count": int(np.sum(mask)), "accuracy": float(np.mean(pred[mask] == y[mask])), "per_class": per_class, "predicted_class_counts": {classes[int(cid)]: int(count) for cid, count in zip(*np.unique(pred[mask], return_counts=True))}}
    return result


def _gate(metrics: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    latest_tests = []
    min_core = []
    min_candidate = []
    max_pred_share = []
    for payload in metrics.get("branches", {}).get("conv1d_baseline", {}).values():
        test = payload["latest"]["test"]
        latest_tests.append(float(test["accuracy"]))
        by_gloss = {row["gloss"]: float(row["accuracy"]) for row in test.get("per_class", [])}
        min_core.append(min(by_gloss.get(gloss, 0.0) for gloss in CORE_CLASSES))
        candidates = [gloss for gloss in config["classes"] if gloss not in CORE_CLASSES]
        min_candidate.append(min(by_gloss.get(gloss, 0.0) for gloss in candidates))
        counts = test.get("predicted_class_counts", {})
        total = sum(int(v) for v in counts.values()) or 1
        max_pred_share.append(max((int(v) for v in counts.values()), default=0) / total)
    gate = config["gate"]
    passed = bool(
        latest_tests
        and float(np.mean(latest_tests)) >= float(gate["mean_latest_test_min"])
        and min(min_core) >= float(gate["core_class_test_min"])
        and min(min_candidate) >= float(gate["candidate_class_test_min"])
        and max(max_pred_share) <= float(gate["max_predicted_class_share"])
    )
    return {
        "mean_latest_test": float(np.mean(latest_tests)) if latest_tests else 0.0,
        "min_core_latest_test": float(min(min_core)) if min_core else 0.0,
        "min_candidate_latest_test": float(min(min_candidate)) if min_candidate else 0.0,
        "max_predicted_class_share": float(max(max_pred_share)) if max_pred_share else 0.0,
        "passed": passed,
        "decision": "eligible_for_larger_batch_or_targeted_cleanup" if passed else "no_export_no_android_integration",
    }


def _source_aware_summary(run_dir: Path, metrics: dict[str, Any]) -> dict[str, Any]:
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    classes = list(config["classes"])
    batch_size = int(config["batch_size"])
    summary: dict[str, Any] = {"branches": {}, "gate": {}}
    for branch, seeds in metrics.get("branches", {}).items():
        summary["branches"][branch] = {}
        for seed in seeds:
            seed_dir = run_dir / "models" / branch / f"seed_{seed}"
            latest = _load_weights_model(branch, (96, 258), int(config["class_count"]), float(config["learning_rate"]), seed_dir / "latest.weights.h5")
            summary["branches"][branch][seed] = {"latest": _source_eval(branch, latest, run_dir, batch_size, classes)}
    summary["gate"] = _gate(metrics, config)
    return summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    result = _base_run(args)
    config = json.loads((args.run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    result["classes"] = list(config["classes"])
    result["source_aware_summary"] = _source_aware_summary(args.run_dir, result)
    _write_json(args.run_dir / "metrics" / "metrics.json", result)
    (args.run_dir / "metrics" / "metrics.md").write_text(_metrics_markdown(result), encoding="utf-8")
    return result


def _metrics_markdown(metrics: dict[str, Any]) -> str:
    gate = metrics.get("source_aware_summary", {}).get("gate", {})
    lines = [
        "# E4-P Existing-Feature 20-Sign Pressure Test Metrics",
        "",
        "Experiment-only result. This is not a production Android model.",
        "",
        f"- Classes: {', '.join(metrics.get('classes', []))}",
        f"- Mean latest test: `{gate.get('mean_latest_test', 0.0):.4f}`",
        f"- Min core latest test: `{gate.get('min_core_latest_test', 0.0):.4f}`",
        f"- Min candidate latest test: `{gate.get('min_candidate_latest_test', 0.0):.4f}`",
        f"- Max predicted-class share: `{gate.get('max_predicted_class_share', 0.0):.4f}`",
        f"- Gate passed: `{gate.get('passed')}`",
        f"- Decision: `{gate.get('decision')}`",
        "",
        "| Branch | Seed | Latest Test | Best Test |",
        "|---|---:|---:|---:|",
    ]
    for branch, seeds in metrics.get("branches", {}).items():
        for seed, payload in seeds.items():
            lines.append(f"| {branch} | {seed} | {payload['latest']['test']['accuracy']:.4f} | {payload['best']['test']['accuracy']:.4f} |")
    return "\n".join(lines) + "\n"


def check(args: argparse.Namespace) -> dict[str, Any]:
    result = _base_check(args)
    run_dir = args.run_dir
    config_path = run_dir / "pilot_config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if config.get("experiment") != "e4_p_existing_feature_20sign_pressure_v1":
            result["errors"].append("unexpected experiment id")
            result["passed"] = False
        if config.get("classes") != DEFAULT_CLASSES:
            result["errors"].append("unexpected E4-P class list")
            result["passed"] = False
    dataset_path = run_dir / "dataset" / "landmark_features.npz"
    if dataset_path.exists():
        data = np.load(dataset_path, allow_pickle=False)
        if "source_ids" not in data.files:
            result["errors"].append("dataset missing source_ids")
            result["passed"] = False
    for required in ("logs/prepare_summary.json", "dataset/source_metadata.npz", "tables/selected_candidate_evidence.csv"):
        if not (run_dir / required).exists():
            result["errors"].append(f"missing output: {required}")
            result["passed"] = False
    _write_json(run_dir / "check_report.json", result)
    return result


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join([
        "# E4-P Existing-Feature 20-Sign Pressure Test",
        "",
        "This is a fast landmark-only batch screen using existing feature tensors. It is not production training.",
        "",
        f"- Classes: {', '.join(config['classes'])}",
        f"- Active rows: {config['active_rows']}",
        f"- Split counts: {config['split_counts']}",
        f"- One-signer local candidates: {', '.join(config['one_signer_local_candidates'])}",
        "",
        "## Smoke Test",
        "",
        "```powershell",
        'cd "F:\\ASL DATASET\\5. Apphear3"',
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_p_existing_feature_20sign_pressure smoke --run-dir "{run_dir}"',
        "```",
        "",
        "## Full Training",
        "",
        "This is the only longer step.",
        "",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_p_existing_feature_20sign_pressure run --run-dir "{run_dir}"',
        "```",
        "",
        "Resume if interrupted:",
        "",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_p_existing_feature_20sign_pressure run --run-dir "{run_dir}" --resume',
        "```",
        "",
        "## Check",
        "",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_p_existing_feature_20sign_pressure check --run-dir "{run_dir}" --require-full-dataset --require-metrics',
        "```",
        "",
    ]) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-P existing-feature 20-sign pressure test")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--core-run", type=Path, default=DEFAULT_CORE_RUN)
    prepare_parser.add_argument("--e4m-run", type=Path, default=DEFAULT_E4M_RUN)
    prepare_parser.add_argument("--asl-feature-dir", type=Path, default=DEFAULT_ASL_FEATURE_DIR)
    prepare_parser.add_argument("--local-feature-path", type=Path, default=DEFAULT_LOCAL_FEATURE_PATH)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--classes", nargs="+", default=DEFAULT_CLASSES)
    prepare_parser.add_argument("--branches", nargs="+", default=DEFAULT_BRANCHES)
    prepare_parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    prepare_parser.add_argument("--batch-size", type=int, default=8)
    prepare_parser.add_argument("--epochs", type=int, default=25)
    prepare_parser.add_argument("--learning-rate", type=float, default=5e-4)
    prepare_parser.add_argument("--overwrite", action="store_true")
    smoke_parser = sub.add_parser("smoke")
    smoke_parser.add_argument("--run-dir", type=Path, required=True)
    smoke_parser.add_argument("--rows", type=int, default=24)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--run-dir", type=Path, required=True)
    run_parser.add_argument("--resume", action="store_true")
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--require-dataset", action="store_true")
    check_parser.add_argument("--require-full-dataset", action="store_true")
    check_parser.add_argument("--require-metrics", action="store_true")
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
        print(f"[rgb/e4-p] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
