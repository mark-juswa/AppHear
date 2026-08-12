"""E5-G clean 7-class primary retrain.

Builds and trains a clean primary landmark model using only the E5-E selected
7-sign subset. This is the follow-up to E5-F, which showed that filtering a
15-class E5-D model was not enough.

Experiment-only: no extraction, Android changes, TFLite export, production
recognizer replacement, or source dataset mutation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pipeline.rgb.e5_b_asl_led_primary_batch import (
    DEFAULT_BRANCHES,
    DEFAULT_COMBINED_DIR,
    DEFAULT_E5A_RUN,
    DEFAULT_SEEDS,
    _write_json,
    prepare as _prepare_base,
    smoke as _smoke_base,
)
from pipeline.rgb.e4_b_strict_runner import check as _base_check
from pipeline.rgb.e4_b_strict_runner import run as _base_run

DEFAULT_E5E_RUN = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_e_reduced_primary_decision_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_g_clean_7_primary_01")


def _load_e5e_classes(e5e_run: Path) -> list[str]:
    summary_path = e5e_run / "reports" / "decision_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"missing E5-E decision summary: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    classes = [str(x).upper() for x in summary.get("recommended_next_primary_subset", [])]
    if not classes:
        raise ValueError("E5-E summary did not provide recommended_next_primary_subset")
    return classes


def _runbook(config: dict[str, Any], e5e_run: Path) -> str:
    run_dir = config["run_dir"]
    return "\n".join([
        "# E5-G Clean 7-Class Primary Retrain",
        "",
        "Experiment-only clean reduced-primary landmark training. It does not modify Android or production assets.",
        "",
        f"- Source E5-E run: `{e5e_run.resolve()}`",
        f"- Classes: `{config['class_count']}`",
        f"- Vocabulary: `{', '.join(config['classes'])}`",
        f"- Rows: `{config['active_rows']}`",
        f"- Split counts: `{config['split_counts']}`",
        f"- Source counts: `{config['source_counts']}`",
        "",
        "## Smoke",
        "```powershell",
        'cd "F:\\ASL DATASET\\5. Apphear3"',
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_g_clean_7_primary smoke --run-dir "{run_dir}"',
        "```",
        "",
        "## Full Training",
        "```powershell",
        'cd "F:\\ASL DATASET\\5. Apphear3"',
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_g_clean_7_primary run --run-dir "{run_dir}"',
        "```",
        "",
        "Resume interrupted training:",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_g_clean_7_primary run --run-dir "{run_dir}" --resume',
        "```",
        "",
        "## Check",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_g_clean_7_primary check --run-dir "{run_dir}" --require-dataset --require-full-dataset --require-metrics',
        "```",
    ])


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    classes = list(args.classes) if args.classes else _load_e5e_classes(args.e5e_run)
    args.classes = classes
    args.class_count = len(classes)
    config = _prepare_base(args)
    config.update({
        "experiment": "e5_g_clean_7_primary_v1",
        "purpose": "Clean 7-class primary retrain from E5-E selected subset after E5-F replay no-go",
        "e5e_run": str(args.e5e_run.resolve()),
        "source_e5d_run": "artifacts/recognition_upgrade/e5_batch_screening/e5_d_reduced_primary_15sign_01",
        "source_e5f_run": "artifacts/recognition_upgrade/e5_batch_screening/e5_f_reduced_primary_routed_sim_01",
        "classes": classes,
        "class_count": len(classes),
        "gate": {
            "diagnostic_go_if": [
                "mean latest test accuracy and per-class recall improve over E5-F replay",
                "no prediction collapse or dominant class shortcut appears",
                "GOOD remains usable within the reduced subset",
                "model is suitable for a follow-up no-sign/OOV routed simulation",
            ],
            "no_go_if": [
                "clean 7-class training still has low selected-class recall",
                "GOOD/SELL/STAND2/MEET remain weak",
                "aggregate accuracy hides per-class collapse",
            ],
        },
        "warnings": [
            "Diagnostic only; not production-ready even if training accuracy is high.",
            "No Android/export is authorized by this package.",
            "Passing E5-G only authorizes a follow-up no-sign/OOV simulation, not production replacement.",
        ],
    })
    _write_json(args.output / "pilot_config.json", config)
    (args.output / "README_RUN.md").write_text(_runbook(config, args.e5e_run), encoding="utf-8")
    _write_json(
        args.output / "logs" / "e5g_selection_summary.json",
        {
            "source_e5e_run": str(args.e5e_run.resolve()),
            "classes": classes,
            "reason": "Clean retrain after E5-F showed post-hoc rejection over 15-class E5-D was insufficient.",
        },
    )
    return config


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    return _smoke_base(args)


def main() -> int:
    parser = argparse.ArgumentParser(description="E5-G clean 7-class primary retrain")
    sub = parser.add_subparsers(dest="command", required=True)

    prep = sub.add_parser("prepare")
    prep.add_argument("--e5e-run", type=Path, default=DEFAULT_E5E_RUN)
    prep.add_argument("--e5a-run", type=Path, default=DEFAULT_E5A_RUN)
    prep.add_argument("--combined-dir", type=Path, default=DEFAULT_COMBINED_DIR)
    prep.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prep.add_argument("--classes", nargs="*")
    prep.add_argument("--branches", nargs="+", default=DEFAULT_BRANCHES)
    prep.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    prep.add_argument("--epochs", type=int, default=24)
    prep.add_argument("--batch-size", type=int, default=32)
    prep.add_argument("--learning-rate", type=float, default=8e-4)
    prep.add_argument("--overwrite", action="store_true")

    smoke_p = sub.add_parser("smoke")
    smoke_p.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    smoke_p.add_argument("--rows", type=int, default=32)

    run_p = sub.add_parser("run")
    run_p.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    run_p.add_argument("--resume", action="store_true")

    check_p = sub.add_parser("check")
    check_p.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    check_p.add_argument("--require-dataset", action="store_true")
    check_p.add_argument("--require-full-dataset", action="store_true")
    check_p.add_argument("--require-metrics", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "smoke":
            result = smoke(args)
        elif args.command == "run":
            result = _base_run(args)
        elif args.command == "check":
            result = _base_check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileExistsError, FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e5-g] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
