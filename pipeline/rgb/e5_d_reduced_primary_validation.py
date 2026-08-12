"""E5-D reduced-primary validation package.

Builds a smaller primary landmark dataset from the E5-C reduced vocabulary
hypothesis. Reuses existing schema v3.0 [96,258] tensors and the E5-B training
machinery. Experiment-only: no extraction, Android export, production asset
replacement, or runtime pipeline changes.
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

DEFAULT_E5C_RUN = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_c_50class_tiering_01")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_d_reduced_primary_15sign_01")


def _load_e5c_classes(e5c_run: Path) -> list[str]:
    summary_path = e5c_run / "reports" / "tiering_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"missing E5-C tiering summary: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    classes = [str(x).upper() for x in summary.get("recommended_reduced_primary_vocabulary", [])]
    if not classes:
        raise ValueError("E5-C summary did not provide a reduced primary vocabulary")
    return classes


def _runbook(config: dict[str, Any], e5c_run: Path) -> str:
    run_dir = config["run_dir"]
    return "\n".join([
        "# E5-D Reduced Primary Validation",
        "",
        "Experiment-only reduced primary landmark validation. It does not modify Android or production assets.",
        "",
        f"- Source E5-C run: `{e5c_run.resolve()}`",
        f"- Classes: `{config['class_count']}`",
        f"- Vocabulary: `{', '.join(config['classes'])}`",
        f"- Rows: `{config['active_rows']}`",
        f"- Split counts: `{config['split_counts']}`",
        f"- Source counts: `{config['source_counts']}`",
        "",
        "## Smoke",
        "```powershell",
        'cd "F:\\ASL DATASET\\5. Apphear3"',
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_d_reduced_primary_validation smoke --run-dir "{run_dir}"',
        "```",
        "",
        "## Full Training",
        "```powershell",
        'cd "F:\\ASL DATASET\\5. Apphear3"',
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_d_reduced_primary_validation run --run-dir "{run_dir}"',
        "```",
        "",
        "Resume interrupted training:",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_d_reduced_primary_validation run --run-dir "{run_dir}" --resume',
        "```",
        "",
        "## Check",
        "```powershell",
        f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e5_d_reduced_primary_validation check --run-dir "{run_dir}" --require-dataset --require-full-dataset --require-metrics',
        "```",
    ])


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    classes = list(args.classes) if args.classes else _load_e5c_classes(args.e5c_run)
    args.classes = classes
    args.class_count = len(classes)
    config = _prepare_base(args)
    config.update({
        "experiment": "e5_d_reduced_primary_validation_v1",
        "purpose": "Reduced primary validation from E5-C tiered 50-class diagnostic",
        "e5c_run": str(args.e5c_run.resolve()),
        "source_e5b_run": "artifacts/recognition_upgrade/e5_batch_screening/e5_b_asl_led_50_primary_01",
        "classes": classes,
        "class_count": len(classes),
        "gate": {
            "diagnostic_go_if": [
                "mean latest test accuracy improves materially over E5-B 0.4897",
                "minimum per-class recall for strong candidates remains acceptable",
                "no prediction collapse or dominant class shortcut appears",
                "GOOD/HAVE remain strong; HELLO/KNOW remain excluded until repaired",
                "candidate set is small enough for later routed no-sign/SORRY validation",
            ],
            "no_go_if": [
                "E5-B confusions persist at reduced scale",
                "GOOD or HAVE degrade materially",
                "guarded classes dominate errors or require specialist routing",
                "aggregate accuracy hides per-class collapse",
            ],
        },
        "warnings": [
            "Diagnostic only; not production-ready even if accuracy is high.",
            "HELLO and KNOW are intentionally excluded due E5-C regression.",
            "SORRY remains outside primary and must be routed through specialist validation later.",
            "No Android/export is authorized by this package.",
        ],
    })
    _write_json(args.output / "pilot_config.json", config)
    (args.output / "README_RUN.md").write_text(_runbook(config, args.e5c_run), encoding="utf-8")
    _write_json(
        args.output / "logs" / "e5d_selection_summary.json",
        {
            "source_e5c_run": str(args.e5c_run.resolve()),
            "classes": classes,
            "excluded_regressed_controls": ["HELLO", "KNOW"],
            "external_specialist_ready": ["SORRY"],
        },
    )
    return config


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    return _smoke_base(args)


def main() -> int:
    parser = argparse.ArgumentParser(description="E5-D reduced primary validation")
    sub = parser.add_subparsers(dest="command", required=True)

    prep = sub.add_parser("prepare")
    prep.add_argument("--e5c-run", type=Path, default=DEFAULT_E5C_RUN)
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
        print(f"[rgb/e5-d] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
