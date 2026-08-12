"""Preflight and summarize the E1 matched TCN-versus-GCN experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from model.train_streaming import _build_and_compile, load_stream_config

CONFIG_DIR = Path("model/config/recognition_upgrade/e1_matched")
ARTIFACT_DIR = Path("artifacts/recognition_upgrade/e1_matched")
NATIVE_FEATURES = Path("../ASL CITIZEN/derived/apphear3/features_streaming_conversational")
K4_FEATURES = Path("../ASL CITIZEN/derived/apphear3/features_lowfps_conv_k4")
K8_FEATURES = Path("../ASL CITIZEN/derived/apphear3/features_lowfps_conv_k8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _split_summary(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=True) as data:
        y = np.asarray(data["y"])
        participants = np.asarray(data["participant_ids"]).astype(str)
        return {
            "path": str(path.resolve()),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "clips": int(len(y)),
            "classes": int(np.unique(y).size),
            "participants": sorted(np.unique(participants).tolist()),
            "schema_version": str(data["schema_version"]),
        }


def _config_paths() -> list[Path]:
    return sorted(CONFIG_DIR.glob("*.yaml"))


def preflight(build_models: bool) -> dict[str, Any]:
    paths = _config_paths()
    if len(paths) != 6:
        raise ValueError(f"expected 6 matched configs, found {len(paths)}")
    configs = [(path, load_stream_config(path)) for path in paths]
    outputs = [cfg.output_dir.resolve() for _, cfg in configs]
    if len(set(outputs)) != len(outputs):
        raise ValueError("matched configs must use unique output directories")

    rows: list[dict[str, Any]] = []
    for path, cfg in configs:
        if cfg.warm_start_from is not None:
            raise ValueError(f"{path} must be a fresh run without warm_start_from")
        rows.append(
            {
                "config": str(path.resolve()),
                "config_sha256": _sha256(path),
                "model_type": cfg.model_type,
                "seed": cfg.seed,
                "output_dir": str(cfg.output_dir.resolve()),
                "output_exists": cfg.output_dir.exists(),
                "features_dir": str(cfg.features_dir.resolve()),
            }
        )

    expected_pairs = {(model, seed) for model in ("tcn", "gcn") for seed in (0, 1, 2)}
    actual_pairs = {(row["model_type"], row["seed"]) for row in rows}
    if actual_pairs != expected_pairs:
        raise ValueError(f"unexpected model/seed matrix: {sorted(actual_pairs)}")

    splits = {
        "train_fps": _split_summary(configs[0][1].features_dir / "train.npz"),
        "val_fps": _split_summary(configs[0][1].features_dir / "val.npz"),
        "native_test": _split_summary(NATIVE_FEATURES / "test.npz"),
        "k4_test": _split_summary(K4_FEATURES / "test.npz"),
        "k8_test": _split_summary(K8_FEATURES / "test.npz"),
    }
    signer_sets = {name: set(split["participants"]) for name, split in splits.items()}
    if signer_sets["train_fps"] & signer_sets["val_fps"]:
        raise ValueError("train/validation signer leakage")
    if signer_sets["train_fps"] & signer_sets["native_test"]:
        raise ValueError("train/test signer leakage")
    if signer_sets["val_fps"] & signer_sets["native_test"]:
        raise ValueError("validation/test signer leakage")
    for name, split in splits.items():
        if split["schema_version"] != "3.0" or split["classes"] != 236:
            raise ValueError(f"unexpected schema/classes in {name}: {split}")
    if not (signer_sets["native_test"] == signer_sets["k4_test"] == signer_sets["k8_test"]):
        raise ValueError("native/k4/k8 test signer sets differ")

    models: dict[str, Any] = {}
    if build_models:
        for model_type in ("tcn", "gcn"):
            cfg = next(cfg for _, cfg in configs if cfg.model_type == model_type)
            model = _build_and_compile(96, 258, 236, cfg)
            models[model_type] = {
                "input_shape": list(model.input_shape),
                "output_shape": list(model.output_shape),
                "params": int(model.count_params()),
            }

    report = {
        "experiment": "E1-matched",
        "status": "preflight_passed",
        "configs": rows,
        "splits": splits,
        "models": models,
        "gates": {
            "native_top1_gain_over_matched_tcn_points": 5.0,
            "k8_top1_gain_over_matched_tcn_points": 3.0,
            "seeds": 3,
            "no_severe_class_regressions": True,
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    output = ARTIFACT_DIR / "preflight.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"[E1-matched] preflight -> {output.resolve()}")
    return report


def summarize() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for config_path in _config_paths():
        cfg = load_stream_config(config_path)
        for condition in ("native", "k4", "k8"):
            path = cfg.output_dir / f"eval_{condition}_test.json"
            if not path.exists():
                raise FileNotFoundError(f"missing evaluation report: {path}")
            report = json.loads(path.read_text(encoding="utf-8"))
            rows.append(
                {
                    "model_type": cfg.model_type,
                    "seed": cfg.seed,
                    "condition": condition,
                    "top1": float(report["overall"]["top1"]),
                    "top5": float(report["overall"]["top5"]),
                    "macro_top1_per_signer": float(report["overall"]["macro_top1_per_signer"]),
                }
            )

    aggregates: dict[str, Any] = {}
    for model_type in ("tcn", "gcn"):
        aggregates[model_type] = {}
        for condition in ("native", "k4", "k8"):
            selected = [
                row
                for row in rows
                if row["model_type"] == model_type and row["condition"] == condition
            ]
            aggregates[model_type][condition] = {
                metric: {
                    "mean": float(np.mean([row[metric] for row in selected])),
                    "std": float(np.std([row[metric] for row in selected])),
                }
                for metric in ("top1", "top5", "macro_top1_per_signer")
            }

    native_gain = (
        aggregates["gcn"]["native"]["top1"]["mean"] - aggregates["tcn"]["native"]["top1"]["mean"]
    )
    k8_gain = aggregates["gcn"]["k8"]["top1"]["mean"] - aggregates["tcn"]["k8"]["top1"]["mean"]
    result = {
        "experiment": "E1-matched",
        "rows": rows,
        "aggregates": aggregates,
        "gains": {"native_top1": native_gain, "k8_top1": k8_gain},
        "provisional_gate_pass": native_gain >= 0.05 and k8_gain >= 0.03,
        "note": "Per-class severe-regression review is still required before final approval.",
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    output = ARTIFACT_DIR / "summary.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"[E1-matched] summary -> {output.resolve()}")
    return result


def evaluate(config_path: Path) -> None:
    from eval.streaming import run as run_streaming_eval

    known = {path.resolve() for path in _config_paths()}
    if config_path.resolve() not in known:
        raise ValueError(f"config is not part of the frozen E1 matrix: {config_path}")
    conditions = (
        ("native", NATIVE_FEATURES),
        ("k4", K4_FEATURES),
        ("k8", K8_FEATURES),
    )
    for name, features_dir in conditions:
        exit_code = run_streaming_eval(
            False,
            config_path,
            features_dir,
            report_name=f"eval_{name}_test.json",
        )
        if exit_code:
            raise RuntimeError(f"{name} evaluation failed with exit code {exit_code}")


def main() -> int:
    parser = argparse.ArgumentParser(description="E1 matched experiment tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("--build-models", action="store_true")
    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--config", type=Path, required=True)
    subparsers.add_parser("summarize")
    args = parser.parse_args()
    if args.command == "preflight":
        preflight(args.build_models)
    elif args.command == "evaluate":
        evaluate(args.config)
    else:
        summarize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
