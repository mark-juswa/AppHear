"""E4-M dual-source candidate screening preflight.

Ranks ASL Citizen + local supplementary signs before any larger extraction/training.
Experiment-only: does not modify Android, production model assets, source videos, or source tensors.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_ASL_FEATURE_DIR = Path(r"F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational")
DEFAULT_LOCAL_FEATURE_PATH = Path(r"F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_recorded_local_pc_236\recorded.npz")
DEFAULT_LOCAL_AUDIT_DIR = Path("artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_audit_01")
DEFAULT_LOCAL_VALIDATION_DIR = Path("artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_validation_01")
DEFAULT_E4L_RESULT = Path("artifacts/recognition_upgrade/e4_generalization/e4_l_make_expansion_pilot_01/metrics/metrics.json")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_m_dual_source_candidate_screen_01")
CORE_GLOSSES = {"GOOD", "HELLO", "SORRY"}
PRIOR_REJECTED = {"MAKE"}
PRIOR_UNSTABLE = {"BYE", "NO", "YES", "THANKYOU"}
SPLITS = ("train", "val", "test")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
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


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _as_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _load_vocab(feature_dir: Path) -> dict[str, int]:
    candidates = [feature_dir / "vocab.json", feature_dir.parent / "features_conversational" / "vocab.json"]
    for path in candidates:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return {str(k).upper(): int(v) for k, v in data.items()}
    raise FileNotFoundError(f"missing vocab.json near {feature_dir}")


def _npz_class_stats(path: Path, vocab: dict[str, int]) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = np.load(path, allow_pickle=True)
    y = data["y"].astype(int)
    participant_ids = np.asarray(data["participant_ids"]).astype(str)
    id_to_gloss = {class_id: gloss for gloss, class_id in vocab.items()}
    stats: dict[str, dict[str, Any]] = {}
    for class_id in sorted(set(y.tolist())):
        gloss = id_to_gloss.get(int(class_id), f"class_{class_id}")
        mask = y == int(class_id)
        signers = sorted(set(participant_ids[mask].tolist()))
        stats[gloss] = {"count": int(mask.sum()), "signers": signers, "signer_count": len(signers)}
    return stats


def _asl_stats(feature_dir: Path, vocab: dict[str, int]) -> dict[str, dict[str, Any]]:
    by_gloss: dict[str, dict[str, Any]] = {gloss: {} for gloss in vocab}
    for split in SPLITS:
        split_stats = _npz_class_stats(feature_dir / f"{split}.npz", vocab)
        for gloss in vocab:
            payload = split_stats.get(gloss, {"count": 0, "signers": [], "signer_count": 0})
            by_gloss[gloss][f"asl_{split}_count"] = payload["count"]
            by_gloss[gloss][f"asl_{split}_signer_count"] = payload["signer_count"]
            by_gloss[gloss][f"asl_{split}_signers"] = ";".join(payload["signers"])
    return by_gloss


def _local_feature_stats(path: Path, vocab: dict[str, int]) -> dict[str, dict[str, Any]]:
    raw = _npz_class_stats(path, vocab)
    return {
        gloss: {
            "local_feature_count": payload["count"],
            "local_feature_signer_count": payload["signer_count"],
            "local_feature_signers": ";".join(payload["signers"]),
        }
        for gloss, payload in raw.items()
    }


def _local_raw_stats(local_audit_dir: Path, local_validation_dir: Path) -> dict[str, dict[str, Any]]:
    audit_rows = _read_csv(local_audit_dir / "local_clip_inventory.csv")
    validation_rows = _read_csv(local_validation_dir / "validated_clip_inventory.csv")
    by_gloss: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "local_raw_rows": 0,
        "local_raw_signers": set(),
        "local_raw_accepted_rows": 0,
        "local_raw_known_hand_hit_rows": 0,
        "local_raw_hand_hit_sum": 0.0,
        "validated_rows": 0,
        "validated_eligible_rows": 0,
        "validated_signers": set(),
        "validated_warning_rows": 0,
    })
    for row in audit_rows:
        gloss = row.get("canonical_gloss", "").strip().upper()
        if not gloss:
            continue
        item = by_gloss[gloss]
        item["local_raw_rows"] += 1
        signer = row.get("signer_id", "").strip()
        if signer:
            item["local_raw_signers"].add(signer)
        if _as_bool(row.get("accepted")):
            item["local_raw_accepted_rows"] += 1
        hand_hit = _as_float(row.get("hand_hit_rate"))
        if hand_hit is not None:
            item["local_raw_known_hand_hit_rows"] += 1
            item["local_raw_hand_hit_sum"] += hand_hit
    for row in validation_rows:
        gloss = row.get("canonical_gloss", "").strip().upper()
        if not gloss:
            continue
        item = by_gloss[gloss]
        item["validated_rows"] += 1
        if _as_bool(row.get("eligible")):
            item["validated_eligible_rows"] += 1
            signer = row.get("signer_id", "").strip()
            if signer:
                item["validated_signers"].add(signer)
        if row.get("warnings", "").strip():
            item["validated_warning_rows"] += 1
    out: dict[str, dict[str, Any]] = {}
    for gloss, item in by_gloss.items():
        raw_signers = sorted(item["local_raw_signers"])
        valid_signers = sorted(item["validated_signers"])
        known = int(item["local_raw_known_hand_hit_rows"])
        out[gloss] = {
            "local_raw_rows": int(item["local_raw_rows"]),
            "local_raw_accepted_rows": int(item["local_raw_accepted_rows"]),
            "local_raw_signer_count": len(raw_signers),
            "local_raw_signers": ";".join(raw_signers),
            "local_raw_mean_hand_hit": round(float(item["local_raw_hand_hit_sum"]) / known, 4) if known else "",
            "validated_rows": int(item["validated_rows"]),
            "validated_eligible_rows": int(item["validated_eligible_rows"]),
            "validated_signer_count": len(valid_signers),
            "validated_signers": ";".join(valid_signers),
            "validated_warning_rows": int(item["validated_warning_rows"]),
        }
    return out


def _score_and_recommend(row: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    gloss = row["gloss"]
    asl_train = int(row["asl_train_count"])
    asl_val = int(row["asl_val_count"])
    asl_test = int(row["asl_test_count"])
    asl_train_signers = int(row["asl_train_signer_count"])
    asl_test_signers = int(row["asl_test_signer_count"])
    local_feature = int(row["local_feature_count"])
    local_feature_signers = int(row["local_feature_signer_count"])
    local_raw = int(row["local_raw_rows"])
    local_raw_signers = int(row["local_raw_signer_count"])
    validated_eligible = int(row["validated_eligible_rows"])
    validated_signers = int(row["validated_signer_count"])
    warnings = int(row["validated_warning_rows"])

    enough_asl = (
        asl_train >= args.min_asl_train
        and asl_val >= args.min_asl_val
        and asl_test >= args.min_asl_test
        and asl_train_signers >= args.min_asl_train_signers
        and asl_test_signers >= args.min_asl_test_signers
    )
    enough_local_features = local_feature >= args.min_local_features and local_feature_signers >= args.min_local_feature_signers
    enough_local_raw = local_raw >= args.min_local_raw and local_raw_signers >= args.min_local_raw_signers
    enough_validated = validated_eligible >= args.min_validated and validated_signers >= args.min_validated_signers
    warning_rate = warnings / validated_eligible if validated_eligible else 0.0

    score = 0
    score += min(asl_train, 30) * 1.0
    score += min(asl_test, 30) * 1.2
    score += min(asl_train_signers, 20) * 2.0
    score += min(asl_test_signers, 11) * 2.5
    score += min(local_feature, 30) * 1.4
    score += min(local_feature_signers, 3) * 8.0
    score += min(validated_eligible or local_raw, 70) * 0.25
    score += min(validated_signers or local_raw_signers, 3) * 6.0
    score -= warnings * 0.75

    flags = []
    if gloss in CORE_GLOSSES:
        recommendation = "keep_core_control"
        flags.append("core")
    elif gloss in PRIOR_REJECTED:
        recommendation = "reject_prior_failed_e4_l"
        flags.append("prior_failed")
    elif gloss in PRIOR_UNSTABLE:
        recommendation = "needs_prior_failure_review"
        flags.append("prior_unstable")
    elif enough_asl and enough_local_features and enough_validated and warning_rate <= args.max_validated_warning_rate:
        recommendation = "train_ready_existing_features"
    elif enough_asl and enough_validated and not enough_local_features:
        recommendation = "needs_local_feature_extraction"
    elif enough_asl and enough_local_raw and not enough_validated:
        recommendation = "needs_video_validation_first"
    elif enough_asl and not enough_local_raw:
        recommendation = "asl_only_candidate_not_dual_source"
    elif local_raw and not enough_asl:
        recommendation = "local_only_or_asl_support_weak"
    else:
        recommendation = "reject_insufficient_support"

    for name, passed in (
        ("enough_asl", enough_asl),
        ("enough_local_features", enough_local_features),
        ("enough_validated", enough_validated),
        ("enough_local_raw", enough_local_raw),
    ):
        if passed:
            flags.append(name)
    row.update(
        {
            "score": round(score, 4),
            "recommendation": recommendation,
            "screen_flags": ";".join(flags),
            "warning_rate_validated": round(warning_rate, 4) if validated_eligible else "",
        }
    )
    return row


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    if output.exists() and any(output.iterdir()) and not args.overwrite:
        raise FileExistsError(f"output already exists; use --overwrite: {output}")
    for relative in ("logs", "reports", "tables"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    vocab = _load_vocab(args.asl_feature_dir)
    asl = _asl_stats(args.asl_feature_dir, vocab)
    local_features = _local_feature_stats(args.local_feature_path, vocab)
    local_raw = _local_raw_stats(args.local_audit_dir, args.local_validation_dir)
    rows = []
    for gloss in sorted(vocab):
        row: dict[str, Any] = {"gloss": gloss, "class_id": vocab[gloss]}
        row.update(asl.get(gloss, {}))
        row.update(
            {
                "local_feature_count": 0,
                "local_feature_signer_count": 0,
                "local_feature_signers": "",
                "local_raw_rows": 0,
                "local_raw_accepted_rows": 0,
                "local_raw_signer_count": 0,
                "local_raw_signers": "",
                "local_raw_mean_hand_hit": "",
                "validated_rows": 0,
                "validated_eligible_rows": 0,
                "validated_signer_count": 0,
                "validated_signers": "",
                "validated_warning_rows": 0,
            }
        )
        row.update(local_features.get(gloss, {}))
        row.update(local_raw.get(gloss, {}))
        rows.append(_score_and_recommend(row, args))
    ranked = sorted(rows, key=lambda row: (row["recommendation"] != "train_ready_existing_features", -float(row["score"]), row["gloss"]))
    selected = [row for row in ranked if row["recommendation"] == "train_ready_existing_features"][: args.max_selected]
    needs_extraction = [row for row in ranked if row["recommendation"] == "needs_local_feature_extraction"][: args.max_selected]

    fields = [
        "gloss", "class_id", "recommendation", "score", "screen_flags", "warning_rate_validated",
        "asl_train_count", "asl_val_count", "asl_test_count",
        "asl_train_signer_count", "asl_val_signer_count", "asl_test_signer_count",
        "local_feature_count", "local_feature_signer_count", "local_raw_rows", "local_raw_accepted_rows",
        "local_raw_signer_count", "local_raw_mean_hand_hit", "validated_rows", "validated_eligible_rows",
        "validated_signer_count", "validated_warning_rows", "local_feature_signers", "local_raw_signers",
        "validated_signers", "asl_train_signers", "asl_val_signers", "asl_test_signers",
    ]
    _write_csv(output / "tables" / "candidate_inventory_ranked.csv", ranked, fields)
    _write_csv(output / "tables" / "train_ready_existing_features.csv", selected, fields)
    _write_csv(output / "tables" / "needs_local_feature_extraction.csv", needs_extraction, fields)

    recommendation_counts = Counter(row["recommendation"] for row in rows)
    report = {
        "experiment": "e4_m_dual_source_candidate_screen_v1",
        "run_dir": str(output.resolve()),
        "asl_feature_dir": str(args.asl_feature_dir.resolve()),
        "local_feature_path": str(args.local_feature_path.resolve()),
        "local_audit_dir": str(args.local_audit_dir.resolve()),
        "local_validation_dir": str(args.local_validation_dir.resolve()),
        "vocab_size": len(vocab),
        "recommendation_counts": dict(sorted(recommendation_counts.items())),
        "selected_train_ready_count": len(selected),
        "selected_train_ready_glosses": [row["gloss"] for row in selected],
        "needs_local_feature_extraction_count": len(needs_extraction),
        "needs_local_feature_extraction_glosses": [row["gloss"] for row in needs_extraction],
        "core_glosses": sorted(CORE_GLOSSES),
        "prior_rejected": sorted(PRIOR_REJECTED),
        "prior_unstable": sorted(PRIOR_UNSTABLE),
        "thresholds": {
            "min_asl_train": args.min_asl_train,
            "min_asl_val": args.min_asl_val,
            "min_asl_test": args.min_asl_test,
            "min_asl_train_signers": args.min_asl_train_signers,
            "min_asl_test_signers": args.min_asl_test_signers,
            "min_local_features": args.min_local_features,
            "min_local_feature_signers": args.min_local_feature_signers,
            "min_local_raw": args.min_local_raw,
            "min_local_raw_signers": args.min_local_raw_signers,
            "min_validated": args.min_validated,
            "min_validated_signers": args.min_validated_signers,
            "max_validated_warning_rate": args.max_validated_warning_rate,
        },
        "decision": "inventory_only_no_training",
        "next_required_action": "review candidate ranking, then approve a bounded extraction/training screen for selected candidates",
        "production_changes": "none",
    }
    _write_json(output / "reports" / "screen_summary.json", report)
    (output / "README_RUN.md").write_text(_runbook(report), encoding="utf-8")
    (output / "reports" / "screen_summary.md").write_text(_markdown(report, selected, needs_extraction), encoding="utf-8")
    return report


def _markdown(report: dict[str, Any], selected: list[dict[str, Any]], needs_extraction: list[dict[str, Any]]) -> str:
    lines = [
        "# E4-M Dual-Source Candidate Screening Preflight",
        "",
        "Inventory/ranking only. No training, extraction, Android integration, or production asset replacement was run.",
        "",
        f"- Vocab size inspected: `{report['vocab_size']}`",
        f"- Recommendation counts: `{report['recommendation_counts']}`",
        f"- Train-ready with existing features: `{report['selected_train_ready_count']}`",
        f"- Needs local feature extraction: `{report['needs_local_feature_extraction_count']}`",
        "",
        "## Train-Ready Existing Features",
        "",
        "| Gloss | Score | ASL train/test | Local features | Validated local |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in selected:
        lines.append(
            f"| {row['gloss']} | {row['score']} | {row['asl_train_count']}/{row['asl_test_count']} | "
            f"{row['local_feature_count']} / {row['local_feature_signer_count']} signers | "
            f"{row['validated_eligible_rows']} / {row['validated_signer_count']} signers |"
        )
    if not selected:
        lines.append("| none | | | | |")
    lines.extend(["", "## Needs Local Feature Extraction", "", "| Gloss | Score | ASL train/test | Local raw/validated |", "|---|---:|---:|---:|"])
    for row in needs_extraction:
        lines.append(
            f"| {row['gloss']} | {row['score']} | {row['asl_train_count']}/{row['asl_test_count']} | "
            f"raw {row['local_raw_rows']} / validated {row['validated_eligible_rows']} |"
        )
    if not needs_extraction:
        lines.append("| none | | | |")
    lines.extend(
        [
            "",
            "## Interpretation Rules",
            "",
            "- `train_ready_existing_features` means ASL Citizen and local feature tensors both have enough support for a cheap follow-up training screen.",
            "- `needs_local_feature_extraction` means the raw/validated local inventory is promising, but existing reusable local tensors are too sparse.",
            "- `reject_prior_failed_e4_l` preserves the E4-L no-go for `MAKE` even if support looks reasonable.",
            "- `needs_prior_failure_review` preserves earlier E4 failures for `BYE`, `NO`, `YES`, and `THANKYOU`; counts alone cannot promote them.",
            "- This preflight does not prove sign correctness or production readiness.",
        ]
    )
    return "\n".join(lines) + "\n"


def _runbook(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# E4-M Dual-Source Candidate Screening",
            "",
            "Fast preflight/ranking only. It reads existing ASL Citizen and local supplementary artifacts and writes isolated reports.",
            "",
            "## Re-run Preflight",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_m_dual_source_screen prepare --output "{report["run_dir"]}" --overwrite',
            "```",
            "",
            "## Check",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_m_dual_source_screen check --run-dir "{report["run_dir"]}" --require-report',
            "```",
            "",
            "## Important",
            "",
            "Do not use this as an accuracy result. The output is a candidate queue for the next bounded extraction/training screen.",
        ]
    ) + "\n"


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = [
        run_dir / "tables" / "candidate_inventory_ranked.csv",
        run_dir / "tables" / "train_ready_existing_features.csv",
        run_dir / "tables" / "needs_local_feature_extraction.csv",
        run_dir / "README_RUN.md",
    ]
    if args.require_report:
        required.extend([run_dir / "reports" / "screen_summary.json", run_dir / "reports" / "screen_summary.md"])
    for path in required:
        if not path.exists():
            errors.append(f"missing output: {path.relative_to(run_dir)}")
    summary = {}
    summary_path = run_dir / "reports" / "screen_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("decision") != "inventory_only_no_training":
            errors.append("unexpected decision in screen summary")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors, "summary": summary}
    _write_json(run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-M dual-source candidate screening preflight")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--asl-feature-dir", type=Path, default=DEFAULT_ASL_FEATURE_DIR)
    prepare_parser.add_argument("--local-feature-path", type=Path, default=DEFAULT_LOCAL_FEATURE_PATH)
    prepare_parser.add_argument("--local-audit-dir", type=Path, default=DEFAULT_LOCAL_AUDIT_DIR)
    prepare_parser.add_argument("--local-validation-dir", type=Path, default=DEFAULT_LOCAL_VALIDATION_DIR)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare_parser.add_argument("--overwrite", action="store_true")
    prepare_parser.add_argument("--max-selected", type=int, default=20)
    prepare_parser.add_argument("--min-asl-train", type=int, default=10)
    prepare_parser.add_argument("--min-asl-val", type=int, default=2)
    prepare_parser.add_argument("--min-asl-test", type=int, default=2)
    prepare_parser.add_argument("--min-asl-train-signers", type=int, default=8)
    prepare_parser.add_argument("--min-asl-test-signers", type=int, default=5)
    prepare_parser.add_argument("--min-local-features", type=int, default=10)
    prepare_parser.add_argument("--min-local-feature-signers", type=int, default=2)
    prepare_parser.add_argument("--min-local-raw", type=int, default=20)
    prepare_parser.add_argument("--min-local-raw-signers", type=int, default=2)
    prepare_parser.add_argument("--min-validated", type=int, default=20)
    prepare_parser.add_argument("--min-validated-signers", type=int, default=2)
    prepare_parser.add_argument("--max-validated-warning-rate", type=float, default=0.15)

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--require-report", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileExistsError, FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e4-m] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


