"""E5-A large dual-source candidate screening.

Ranks ASL Citizen + local supplementary feature support for the full 236-label
inventory and proposes the next batch candidates. This is inventory/tiering
only: no training, extraction, Android changes, model export, or dataset mutation.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np

DEFAULT_ASL_DIR = Path(r"F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational")
DEFAULT_COMBINED_DIR = Path(r"F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational_plus_pc_236")
DEFAULT_LOCAL_PATH = Path(r"F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_recorded_local_pc_236\recorded.npz")
DEFAULT_E4P = Path("artifacts/recognition_upgrade/e4_generalization/e4_p_existing_feature_20sign_pressure_01/metrics/metrics.json")
DEFAULT_E4N = Path("artifacts/recognition_upgrade/e4_generalization/e4_n_dual_source_5sign_screen_01/metrics/metrics.json")
DEFAULT_E4AG = Path("artifacts/recognition_upgrade/e4_generalization/e4_ag_low_motion_gate_01/metrics/low_motion_gate_metrics.json")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e5_batch_screening/e5_a_dual_source_batch_screen_01")

SPLITS = ("train", "val", "test")
STABLE_PRIMARY = {"GOOD", "HELLO", "HAVE", "KNOW"}
ROUTED_PROVEN = {"SORRY"}
KNOWN_BLOCKED = {"MAKE", "GET", "WELCOME2", "BYE", "NO", "YES", "THANKYOU"}
CONFUSION_GROUP = {"SORRY", "HELP", "BECOME"}
WEAK_E4P = {"NICE", "KEEP", "START", "TALK1", "WHAT1", "CLEAN", "LEAVE"}
LOCAL_ID_RE = re.compile(r"^[0-9A-F]{6}-S\d{3}$", re.IGNORECASE)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_vocab(asl_dir: Path) -> dict[str, int]:
    for path in [asl_dir / "vocab.json", asl_dir.parent / "features_conversational" / "vocab.json"]:
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            return {str(k).upper(): int(v) for k, v in raw.items()}
    raise FileNotFoundError(f"missing vocab.json near {asl_dir}")


def _empty_stats() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for prefix in ("asl", "local"):
        for split in SPLITS:
            out[f"{prefix}_{split}_count"] = 0
            out[f"{prefix}_{split}_signer_count"] = 0
            out[f"{prefix}_{split}_signers"] = ""
    out.update({
        "asl_total_count": 0,
        "asl_total_signer_count": 0,
        "local_total_count": 0,
        "local_total_signer_count": 0,
        "local_total_signers": "",
    })
    return out


def _is_local_signer(participant_id: str) -> bool:
    return bool(LOCAL_ID_RE.match(participant_id))


def _count_combined(combined_dir: Path, id_to_gloss: dict[int, str]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(_empty_stats)
    total_signers: dict[tuple[str, str], set[str]] = defaultdict(set)
    for split in SPLITS:
        path = combined_dir / f"{split}.npz"
        if not path.exists():
            continue
        data = np.load(path, allow_pickle=True)
        y = data["y"].astype(int)
        participants = np.asarray(data["participant_ids"]).astype(str)
        for class_id, participant in zip(y, participants):
            gloss = id_to_gloss.get(int(class_id), f"class_{class_id}")
            source = "local" if _is_local_signer(participant) else "asl"
            item = stats[gloss]
            item[f"{source}_{split}_count"] += 1
            signers_key = f"{source}_{split}_signers"
            existing = set(filter(None, str(item[signers_key]).split(";")))
            existing.add(participant)
            item[signers_key] = ";".join(sorted(existing))
            total_signers[(gloss, source)].add(participant)
    for gloss, item in stats.items():
        for source in ("asl", "local"):
            total = sum(int(item[f"{source}_{split}_count"]) for split in SPLITS)
            item[f"{source}_total_count"] = total
            all_signers = sorted(total_signers[(gloss, source)])
            item[f"{source}_total_signer_count"] = len(all_signers)
            item[f"{source}_total_signers"] = ";".join(all_signers)
            for split in SPLITS:
                signers = list(filter(None, str(item[f"{source}_{split}_signers"]).split(";")))
                item[f"{source}_{split}_signer_count"] = len(signers)
    return dict(stats)


def _e4p_stats(path: Path) -> dict[str, dict[str, Any]]:
    metrics = _load_json(path)
    if not metrics:
        return {}
    out: dict[str, list[float]] = defaultdict(list)
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    classes = metrics.get("classes", [])
    for seeds in metrics.get("branches", {}).values():
        for seed_metrics in seeds.values():
            test = seed_metrics.get("latest", {}).get("test", {})
            matrix = test.get("confusion_matrix", [])
            for pc in test.get("per_class", []):
                gloss = pc["gloss"]
                out[gloss].append(float(pc["accuracy"]))
                row = matrix[int(pc["class_id"])] if matrix else []
                for idx, value in enumerate(row):
                    if idx < len(classes) and classes[idx] != gloss and int(value):
                        confusion[gloss][classes[idx]] += int(value)
        break
    result = {}
    for gloss, values in out.items():
        top = confusion[gloss].most_common(1)
        result[gloss] = {
            "e4p_mean_latest_acc": mean(values),
            "e4p_min_latest_acc": min(values),
            "e4p_top_confusion": top[0][0] if top else "",
            "e4p_top_confusion_count": top[0][1] if top else 0,
        }
    return result


def _e4n_passed(path: Path) -> set[str]:
    metrics = _load_json(path)
    return set(metrics.get("classes", [])) if metrics.get("passed") else set()


def _tier(row: dict[str, Any], args: argparse.Namespace) -> tuple[str, str, str]:
    gloss = row["gloss"]
    local_count = int(row["local_total_count"])
    local_signers = int(row["local_total_signer_count"])
    asl_train = int(row["asl_train_count"])
    asl_val = int(row["asl_val_count"])
    asl_test = int(row["asl_test_count"])
    asl_test_signers = int(row["asl_test_signer_count"])
    e4p_mean = row.get("e4p_mean_latest_acc")
    e4p_min = row.get("e4p_min_latest_acc")

    if gloss in STABLE_PRIMARY:
        return ("A0_primary_proven", "keep_as_primary_control", "Already passed stable-primary evidence.")
    if gloss in ROUTED_PROVEN:
        return ("A1_routed_specialist_proven", "keep_as_routed_specialist_control", "Recovered through GOOD/SORRY specialist and E4-AG safety gate.")
    if gloss in KNOWN_BLOCKED:
        return ("C2_blocked_prior_failure", "defer_or_repair", "Prior E4 evidence showed collapse, variant risk, or label/data problem.")
    if gloss in CONFUSION_GROUP:
        return ("B2_confusion_group", "specialist_or_repair", "Known SORRY/BECOME/HELP confusion group; do not add blindly to primary.")
    if local_count <= 0:
        return ("D0_asl_only_inventory", "not_current_dual_source_batch", "No local supplementary feature support.")
    enough_asl = asl_train >= args.min_asl_train and asl_val >= args.min_asl_val and asl_test >= args.min_asl_test and asl_test_signers >= args.min_asl_test_signers
    enough_local = local_count >= args.min_local_count and local_signers >= args.min_local_signers
    if not enough_asl:
        return ("C1_data_limited", "needs_asl_support_or_split_recheck", "Local exists, but ASL/split support is weak.")
    if not enough_local:
        return ("B1_candidate_needs_more_local_signers", "candidate_but_collect_more_local", "ASL support exists, but local support is too narrow for production-grade promotion.")
    if gloss in WEAK_E4P:
        return ("B3_prior_weak_in_pressure_test", "review_or_specialist_before_primary", "E4-P showed weak held-out behavior.")
    if isinstance(e4p_mean, float) and isinstance(e4p_min, float):
        if e4p_mean >= args.e4p_mean_min and e4p_min >= args.e4p_min_min:
            return ("A2_candidate_for_e5b_primary_pilot", "train_in_next_batch_pilot", "Dual-source support plus acceptable E4-P pressure behavior.")
        return ("B0_batch_candidate_but_unproven", "train_diagnostic_only", "Dual-source support exists, but E4-P behavior is borderline or absent.")
    return ("B0_batch_candidate_but_unproven", "train_diagnostic_only", "Dual-source support exists; no direct E4-P pressure evidence.")


def _score(row: dict[str, Any]) -> float:
    score = 0.0
    score += min(int(row["asl_train_count"]), 30) * 1.0
    score += min(int(row["asl_test_count"]), 30) * 1.2
    score += min(int(row["asl_test_signer_count"]), 12) * 3.0
    score += min(int(row["local_total_count"]), 70) * 1.5
    score += min(int(row["local_total_signer_count"]), 4) * 12.0
    if isinstance(row.get("e4p_mean_latest_acc"), float):
        score += float(row["e4p_mean_latest_acc"]) * 40.0
        score += float(row["e4p_min_latest_acc"]) * 25.0
    return round(score, 4)


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    for relative in ("tables", "reports", "logs"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    vocab = _load_vocab(args.asl_dir)
    id_to_gloss = {class_id: gloss for gloss, class_id in vocab.items()}
    combined = _count_combined(args.combined_dir, id_to_gloss)
    e4p = _e4p_stats(args.e4p_metrics)
    e4n_passed = _e4n_passed(args.e4n_metrics)
    e4ag = _load_json(args.e4ag_metrics)

    rows = []
    for gloss in sorted(vocab):
        item = {"gloss": gloss, "class_id": vocab[gloss]}
        item.update(_empty_stats())
        item.update(combined.get(gloss, {}))
        item.update(e4p.get(gloss, {}))
        item["e4n_passed"] = gloss in e4n_passed
        tier, action, reason = _tier(item, args)
        item["tier"] = tier
        item["recommended_action"] = action
        item["reason"] = reason
        item["score"] = _score(item)
        rows.append(item)

    tier_order = {
        "A0_primary_proven": 0,
        "A1_routed_specialist_proven": 1,
        "A2_candidate_for_e5b_primary_pilot": 2,
        "B0_batch_candidate_but_unproven": 3,
        "B1_candidate_needs_more_local_signers": 4,
        "B2_confusion_group": 5,
        "B3_prior_weak_in_pressure_test": 6,
        "C1_data_limited": 7,
        "C2_blocked_prior_failure": 8,
        "D0_asl_only_inventory": 9,
    }
    rows.sort(key=lambda r: (tier_order.get(r["tier"], 99), -float(r["score"]), r["gloss"]))

    fields = [
        "tier", "gloss", "recommended_action", "reason", "score", "class_id",
        "asl_train_count", "asl_val_count", "asl_test_count", "asl_total_count",
        "asl_train_signer_count", "asl_val_signer_count", "asl_test_signer_count", "asl_total_signer_count",
        "local_train_count", "local_val_count", "local_test_count", "local_total_count",
        "local_train_signer_count", "local_val_signer_count", "local_test_signer_count", "local_total_signer_count",
        "e4p_mean_latest_acc", "e4p_min_latest_acc", "e4p_top_confusion", "e4p_top_confusion_count", "e4n_passed",
        "local_total_signers",
    ]
    _write_csv(output / "tables" / "candidate_inventory_236.csv", rows, fields)
    for tier in sorted(set(r["tier"] for r in rows), key=lambda t: tier_order.get(t, 99)):
        _write_csv(output / "tables" / f"{tier}.csv", [r for r in rows if r["tier"] == tier], fields)

    e5b_candidates = [r for r in rows if r["tier"] == "A2_candidate_for_e5b_primary_pilot"][: int(args.max_e5b_candidates)]
    diagnostic_candidates = [r for r in rows if r["tier"] == "B0_batch_candidate_but_unproven"][: int(args.max_diagnostic_candidates)]
    _write_csv(output / "tables" / "recommended_e5b_primary_candidates.csv", e5b_candidates, fields)
    _write_csv(output / "tables" / "diagnostic_batch_candidates.csv", diagnostic_candidates, fields)

    summary = {
        "experiment": "e5_a_dual_source_batch_screen_v1",
        "run_dir": str(output.resolve()),
        "asl_dir": str(args.asl_dir.resolve()),
        "combined_dir": str(args.combined_dir.resolve()),
        "local_path": str(args.local_path.resolve()),
        "vocab_size": len(vocab),
        "tier_counts": dict(sorted(Counter(r["tier"] for r in rows).items())),
        "local_supported_labels": int(sum(1 for r in rows if int(r["local_total_count"]) > 0)),
        "recommended_e5b_primary_candidates": [r["gloss"] for r in e5b_candidates],
        "diagnostic_batch_candidates": [r["gloss"] for r in diagnostic_candidates],
        "stable_primary_controls": sorted(STABLE_PRIMARY),
        "routed_specialist_controls": sorted(ROUTED_PROVEN),
        "e4ag_safety_floor": e4ag.get("summary", {}),
        "decision": "inventory_screen_complete_prepare_e5b_batch_pilot",
        "warnings": [
            "No training or extraction was performed.",
            "Many local-supported labels still have only one local signer; they are diagnostic candidates, not production-ready.",
            "Android/export remains blocked until model, no-sign, quantization, and device gates pass.",
        ],
    }
    _write_json(output / "reports" / "screen_summary.json", summary)
    md = [
        "# E5-A Dual-Source Batch Screen",
        "",
        f"- Vocab size: `{len(vocab)}`",
        f"- Local-supported labels: `{summary['local_supported_labels']}`",
        f"- Tier counts: `{summary['tier_counts']}`",
        f"- Recommended E5-B primary candidates: `{summary['recommended_e5b_primary_candidates']}`",
        f"- Diagnostic candidates: `{summary['diagnostic_batch_candidates']}`",
        "",
        "This is inventory/tiering only. No training, extraction, Android export, or production replacement was performed.",
    ]
    (output / "reports" / "screen_summary.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = [
        "tables/candidate_inventory_236.csv",
        "tables/recommended_e5b_primary_candidates.csv",
        "tables/diagnostic_batch_candidates.csv",
        "reports/screen_summary.json",
        "reports/screen_summary.md",
    ]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    if args.require_report and (run_dir / "reports" / "screen_summary.json").exists():
        summary = _load_json(run_dir / "reports" / "screen_summary.json")
        if summary.get("experiment") != "e5_a_dual_source_batch_screen_v1":
            errors.append("unexpected experiment id")
        if int(summary.get("vocab_size", 0)) < 200:
            errors.append("vocab size unexpectedly small")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E5-A dual-source batch screening")
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run")
    run_p.add_argument("--asl-dir", type=Path, default=DEFAULT_ASL_DIR)
    run_p.add_argument("--combined-dir", type=Path, default=DEFAULT_COMBINED_DIR)
    run_p.add_argument("--local-path", type=Path, default=DEFAULT_LOCAL_PATH)
    run_p.add_argument("--e4p-metrics", type=Path, default=DEFAULT_E4P)
    run_p.add_argument("--e4n-metrics", type=Path, default=DEFAULT_E4N)
    run_p.add_argument("--e4ag-metrics", type=Path, default=DEFAULT_E4AG)
    run_p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_p.add_argument("--min-asl-train", type=int, default=10)
    run_p.add_argument("--min-asl-val", type=int, default=2)
    run_p.add_argument("--min-asl-test", type=int, default=2)
    run_p.add_argument("--min-asl-test-signers", type=int, default=5)
    run_p.add_argument("--min-local-count", type=int, default=10)
    run_p.add_argument("--min-local-signers", type=int, default=2)
    run_p.add_argument("--e4p-mean-min", type=float, default=0.75)
    run_p.add_argument("--e4p-min-min", type=float, default=0.60)
    run_p.add_argument("--max-e5b-candidates", type=int, default=12)
    run_p.add_argument("--max-diagnostic-candidates", type=int, default=20)

    check_p = sub.add_parser("check")
    check_p.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    check_p.add_argument("--require-report", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        print(f"[rgb/e5-a] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())

