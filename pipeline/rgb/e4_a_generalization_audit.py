"""E4-A landmark generalization and data-quality audit.

This is an offline analysis package. It reads existing E3 artifacts and writes a conservative
class/signer/confusion/data-quality decision report. It does not train models or mutate datasets.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_E3_B5 = Path(
    "artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed"
)
DEFAULT_E3_B6 = Path(
    "artifacts/recognition_upgrade/e3_landmark_temporal/pilot_03_feature_augmented"
)
DEFAULT_E3_B7 = Path("artifacts/recognition_upgrade/e3_landmark_temporal/pilot_04_feature_ablation")
DEFAULT_E3_C = Path("artifacts/recognition_upgrade/e3_fusion/pilot_02_frozen_50_landmark_rgb")
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e4_generalization/e4_a_landmark_data_audit_01")
SPLITS = ("train", "val", "test")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _mean(values: list[float]) -> float:
    return float(statistics.mean(values)) if values else 0.0


def _stdev(values: list[float]) -> float:
    return float(statistics.pstdev(values)) if len(values) > 1 else 0.0


def _support_by_gloss(manifest_rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in manifest_rows:
        gloss = row["gloss"]
        split = row["split"]
        entry = out.setdefault(
            gloss,
            {
                "gloss": gloss,
                "old_class_id": row.get("old_class_id", ""),
                "new_class_id": row.get("new_class_id", row.get("label_index", "")),
                "train_clips": 0,
                "val_clips": 0,
                "test_clips": 0,
                "train_signers": set(),
                "val_signers": set(),
                "test_signers": set(),
                "lengths": [],
            },
        )
        entry[f"{split}_clips"] += 1
        entry[f"{split}_signers"].add(row.get("participant_id", ""))
        if row.get("length"):
            entry["lengths"].append(int(float(row["length"])))
    for entry in out.values():
        for split in SPLITS:
            entry[f"{split}_signer_count"] = len(entry.pop(f"{split}_signers"))
        lengths = entry.pop("lengths")
        entry["median_length"] = float(statistics.median(lengths)) if lengths else ""
        entry["min_length"] = min(lengths) if lengths else ""
        entry["max_length"] = max(lengths) if lengths else ""
    return out


def _extract_e3_b6_class_metrics(metrics: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = defaultdict(lambda: defaultdict(list))
    for branch, seeds in metrics.get("branches", {}).items():
        for seed, result in seeds.items():
            best = result.get("best", {})
            for split in ("val", "test"):
                per_class = best.get(split, {}).get("per_class", {})
                if isinstance(per_class, dict):
                    per_class_rows = [dict(item, gloss=gloss) for gloss, item in per_class.items()]
                else:
                    per_class_rows = list(per_class)
                for item in per_class_rows:
                    gloss = str(item.get("gloss", item.get("class_id", "")))
                    key = f"e3_b6_{branch}_{split}_accuracy"
                    out[gloss][key].append(float(item.get("accuracy", 0.0)))
                    out[gloss][f"e3_b6_{split}_observations"].append(
                        float(item.get("count", 0.0))
                    )
                    out[gloss][f"e3_b6_{branch}_{split}_seed_{seed}"] = float(
                        item.get("accuracy", 0.0)
                    )
    summarized: dict[str, dict[str, Any]] = {}
    for gloss, values in out.items():
        row: dict[str, Any] = {}
        val_all: list[float] = []
        test_all: list[float] = []
        for key, raw in values.items():
            if isinstance(raw, list):
                row[f"{key}_mean"] = _mean(raw)
                row[f"{key}_std"] = _stdev(raw)
                if key.endswith("_val_accuracy"):
                    val_all.extend(raw)
                if key.endswith("_test_accuracy"):
                    test_all.extend(raw)
            else:
                row[key] = raw
        row["e3_b6_val_mean_all"] = _mean(val_all)
        row["e3_b6_test_mean_all"] = _mean(test_all)
        row["e3_b6_val_std_all"] = _stdev(val_all)
        row["e3_b6_test_std_all"] = _stdev(test_all)
        summarized[gloss] = row
    return summarized


def _extract_e3_b5_class_metrics(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        gloss = row["gloss"]
        key = f"e3_b5_{row['branch']}_{row['split']}_accuracy"
        grouped[gloss][key].append(float(row["accuracy"]))
        grouped[gloss][f"e3_b5_{row['split']}_accuracy_all"].append(float(row["accuracy"]))
    out: dict[str, dict[str, Any]] = {}
    for gloss, values in grouped.items():
        item: dict[str, Any] = {}
        for key, vals in values.items():
            item[f"{key}_mean"] = _mean(vals)
            item[f"{key}_std"] = _stdev(vals)
        out[gloss] = item
    return out


def _confusion_in_out(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = defaultdict(lambda: defaultdict(float))
    examples: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        truth = row["truth"]
        pred = row["predicted"]
        count = float(row["count"])
        rate = float(row["confusion_rate"])
        out[truth]["confusion_out_count"] += count
        out[truth]["max_out_rate"] = max(out[truth]["max_out_rate"], rate)
        out[pred]["confusion_in_count"] += count
        out[pred]["max_in_rate"] = max(out[pred]["max_in_rate"], rate)
        if len(examples[truth]) < 5:
            examples[truth].append(f"{truth}->{pred}:{int(count)} ({rate:.2f})")
    final: dict[str, dict[str, Any]] = {}
    for gloss, item in out.items():
        final[gloss] = dict(item)
        final[gloss]["top_confusion_examples"] = "; ".join(examples.get(gloss, []))
    return final


def _bias_by_gloss(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    max_rank: dict[str, int] = defaultdict(lambda: 999)
    for row in rows:
        gloss = row["gloss"]
        grouped[gloss].append(float(row["predicted_over_expected"]))
        max_rank[gloss] = min(max_rank[gloss], int(row["rank"]))
    return {
        gloss: {
            "mean_predicted_over_expected": _mean(vals),
            "max_predicted_over_expected": max(vals),
            "best_bias_rank": max_rank[gloss],
        }
        for gloss, vals in grouped.items()
    }


def _tier(row: dict[str, Any]) -> tuple[str, str]:
    val = float(row.get("e3_b6_val_mean_all", 0.0))
    test = float(row.get("e3_b6_test_mean_all", 0.0))
    val_std = float(row.get("e3_b6_val_std_all", 0.0))
    test_std = float(row.get("e3_b6_test_std_all", 0.0))
    max_conf = float(row.get("max_out_rate", 0.0))
    test_clips = int(row.get("test_clips", 0) or 0)
    val_clips = int(row.get("val_clips", 0) or 0)
    if test >= 0.65 and val >= 0.65 and max_conf < 0.35 and test_std <= 0.20:
        return "candidate_keep", "strong held-out class performance and no dominant confusion"
    if test >= 0.45 and val >= 0.45 and max_conf < 0.50:
        return (
            "borderline_collect_more",
            "moderate held-out performance; needs more signer evidence",
        )
    if max_conf >= 0.50:
        return "confusion_review", "dominant stable confusion requires video/label/variant review"
    if val_clips < 4 or test_clips < 4:
        return "borderline_collect_more", "low selected support in validation or test split"
    if test < 0.25 and val < 0.35:
        return "drop_or_defer", "weak held-out performance under current landmark evidence"
    if val_std > 0.25 or test_std > 0.25:
        return "borderline_collect_more", "unstable across branches/seeds"
    return (
        "needs_visual_evidence",
        "landmark evidence is inconclusive; review video before RGB claims",
    )


def _build_class_reliability(paths: dict[str, Path]) -> list[dict[str, Any]]:
    manifest = _read_csv(paths["e3_b5"] / "pilot_manifest.csv")
    support = _support_by_gloss(manifest)
    e3_b5 = _extract_e3_b5_class_metrics(
        _read_csv(paths["e3_b5"] / "analysis" / "class_accuracy_summary.csv")
    )
    e3_b6 = _extract_e3_b6_class_metrics(_read_json(paths["e3_b6"] / "metrics" / "metrics.json"))
    confusion = _confusion_in_out(_read_csv(paths["e3_b5"] / "analysis" / "confusion_pairs.csv"))
    bias = _bias_by_gloss(_read_csv(paths["e3_b5"] / "analysis" / "prediction_bias.csv"))
    rows: list[dict[str, Any]] = []
    for gloss in sorted(support):
        row: dict[str, Any] = {}
        row.update(support.get(gloss, {}))
        row.update(e3_b5.get(gloss, {}))
        row.update(e3_b6.get(gloss, {}))
        row.update(confusion.get(gloss, {}))
        row.update(bias.get(gloss, {}))
        tier, reason = _tier(row)
        row["reliability_tier"] = tier
        row["recommendation_reason"] = reason
        rows.append(row)
    rows.sort(
        key=lambda r: (
            r["reliability_tier"],
            -float(r.get("e3_b6_test_mean_all", 0.0)),
            r["gloss"],
        )
    )
    return rows


def _build_confusion_groups(paths: dict[str, Path]) -> list[dict[str, Any]]:
    rows = _read_csv(paths["e3_b5"] / "analysis" / "confusion_pairs.csv")
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        truth = row["truth"]
        pred = row["predicted"]
        key = tuple(sorted((truth, pred)))
        item = grouped.setdefault(
            key,
            {
                "group": " <-> ".join(key),
                "class_a": key[0],
                "class_b": key[1],
                "total_confusions": 0,
                "max_confusion_rate": 0.0,
                "branches": set(),
                "splits": set(),
                "directions": Counter(),
            },
        )
        item["total_confusions"] += int(float(row["count"]))
        item["max_confusion_rate"] = max(item["max_confusion_rate"], float(row["confusion_rate"]))
        item["branches"].add(row["branch"])
        item["splits"].add(row["split"])
        item["directions"][f"{truth}->{pred}"] += int(float(row["count"]))
    out = []
    for item in grouped.values():
        direction_text = "; ".join(f"{k}:{v}" for k, v in item["directions"].most_common(6))
        cause = "unknown"
        if item["max_confusion_rate"] >= 0.50:
            cause = "confusion_review_required"
        out.append(
            {
                "group": item["group"],
                "class_a": item["class_a"],
                "class_b": item["class_b"],
                "total_confusions": item["total_confusions"],
                "max_confusion_rate": item["max_confusion_rate"],
                "branch_count": len(item["branches"]),
                "split_count": len(item["splits"]),
                "branches": ";".join(sorted(item["branches"])),
                "splits": ";".join(sorted(item["splits"])),
                "directions": direction_text,
                "likely_cause": cause,
                "manual_review_required": "yes" if cause != "unknown" else "maybe",
            }
        )
    out.sort(key=lambda r: (-r["max_confusion_rate"], -r["total_confusions"], r["group"]))
    return out


def _build_support_rows(paths: dict[str, Path]) -> list[dict[str, Any]]:
    rows = _read_csv(paths["e3_b5"] / "pilot_manifest.csv")
    support = _support_by_gloss(rows)
    selected = {row["gloss"]: row for row in _read_csv(paths["e3_b5"] / "selected_classes.csv")}
    out = []
    for gloss, item in sorted(support.items()):
        item = dict(item)
        item.update({f"source_{k}": v for k, v in selected.get(gloss, {}).items()})
        risks = []
        if item["train_signer_count"] < 10:
            risks.append("low_train_signer_count")
        if item["val_signer_count"] < 2 or item["test_signer_count"] < 2:
            risks.append("low_eval_signer_count")
        if item["train_clips"] < 16:
            risks.append("low_train_clip_count")
        item["support_risks"] = ";".join(risks) if risks else "none_observed_in_manifest"
        out.append(item)
    return out


def _build_signer_rows(paths: dict[str, Path]) -> tuple[list[dict[str, Any]], str]:
    manifest = _read_csv(paths["e3_b5"] / "pilot_manifest.csv")
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in manifest:
        key = (row["split"], row["participant_id"])
        item = grouped.setdefault(
            key,
            {
                "split": row["split"],
                "participant_id": row["participant_id"],
                "clip_count": 0,
                "classes": set(),
                "lengths": [],
            },
        )
        item["clip_count"] += 1
        item["classes"].add(row["gloss"])
        if row.get("length"):
            item["lengths"].append(int(float(row["length"])))
    out = []
    for item in grouped.values():
        lengths = item.pop("lengths")
        classes = item.pop("classes")
        item["class_count"] = len(classes)
        item["median_length"] = float(statistics.median(lengths)) if lengths else ""
        item["accuracy_available"] = "no"
        item["tooling_gap"] = "per-clip predictions are not persisted in current E3 metrics"
        out.append(item)
    out.sort(key=lambda r: (r["split"], r["participant_id"]))
    note = (
        "Per-signer support can be computed from manifests, but per-signer accuracy requires "
        "per-clip predictions. Current E3 metrics persist aggregate/per-class counts, not stable "
        "per-clip predictions for every branch/seed. E4-A therefore reports this as a tooling gap."
    )
    return out, note


def _inventory(paths: dict[str, Path]) -> dict[str, Any]:
    checks = {}
    for name, run_dir in paths.items():
        if name == "output":
            continue
        checks[name] = {
            "run_dir": str(run_dir.resolve()),
            "exists": run_dir.exists(),
            "check_report_exists": (run_dir / "check_report.json").exists(),
            "metrics_exists": (run_dir / "metrics" / "metrics.json").exists(),
            "manifest_exists": (run_dir / "pilot_manifest.csv").exists(),
        }
        if (run_dir / "check_report.json").exists():
            try:
                checks[name]["check_report"] = _read_json(run_dir / "check_report.json")
            except json.JSONDecodeError:
                checks[name]["check_report_error"] = "invalid json"
    return {"experiment": "e4_a_landmark_generalization_audit_v1", "sources": checks}


def _markdown_table(rows: list[dict[str, Any]], fields: list[str], limit: int = 30) -> str:
    shown = rows[:limit]
    lines = ["| " + " | ".join(fields) + " |", "|" + "|".join(["---"] * len(fields)) + "|"]
    for row in shown:
        lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return "\n".join(lines)


def _write_reports(output: Path, data: dict[str, Any]) -> None:
    class_rows = data["class_reliability"]
    confusion_rows = data["confusion_groups"]
    support_rows = data["data_quality_support"]
    signer_rows = data["signer_generalization"]

    class_fields = sorted({key for row in class_rows for key in row})
    front = [
        "gloss",
        "old_class_id",
        "new_class_id",
        "reliability_tier",
        "recommendation_reason",
        "e3_b6_val_mean_all",
        "e3_b6_test_mean_all",
        "max_out_rate",
        "top_confusion_examples",
        "train_clips",
        "val_clips",
        "test_clips",
        "train_signer_count",
        "val_signer_count",
        "test_signer_count",
    ]
    class_fields = front + [field for field in class_fields if field not in front]
    _write_csv(output / "class_reliability.csv", class_rows, class_fields)
    _write_csv(
        output / "confusion_groups.csv",
        confusion_rows,
        [
            "group",
            "class_a",
            "class_b",
            "total_confusions",
            "max_confusion_rate",
            "branch_count",
            "split_count",
            "branches",
            "splits",
            "directions",
            "likely_cause",
            "manual_review_required",
        ],
    )
    _write_csv(
        output / "data_quality_support.csv",
        support_rows,
        sorted({key for row in support_rows for key in row}),
    )
    _write_csv(
        output / "signer_generalization.csv",
        signer_rows,
        [
            "split",
            "participant_id",
            "clip_count",
            "class_count",
            "median_length",
            "accuracy_available",
            "tooling_gap",
        ],
    )

    keep = [row for row in class_rows if row["reliability_tier"] == "candidate_keep"]
    borderline = [row for row in class_rows if row["reliability_tier"] == "borderline_collect_more"]
    hard = [
        row
        for row in class_rows
        if row["reliability_tier"] in {"confusion_review", "drop_or_defer", "needs_visual_evidence"}
    ]
    _write_csv(output / "reliable_vocabulary_v0.csv", keep, class_fields)
    _write_csv(output / "hard_confusion_set_v0.csv", hard, class_fields)

    counts = Counter(row["reliability_tier"] for row in class_rows)
    next_decision = "E4-C targeted data/label audit before retraining"
    if len(keep) >= 15:
        next_decision = "E4-B cleaned reliable-vocabulary retrain"
    elif len(keep) + len(borderline) >= 15:
        next_decision = "E4-C targeted collection then E4-B"

    summary = {
        "experiment": "e4_a_landmark_generalization_audit_v1",
        "class_count": len(class_rows),
        "tier_counts": dict(counts),
        "candidate_keep_count": len(keep),
        "borderline_count": len(borderline),
        "hard_or_defer_count": len(hard),
        "top_confusion_groups": confusion_rows[:20],
        "signer_accuracy_tooling_gap": data["signer_note"],
        "recommended_next_decision": next_decision,
        "passed": True,
    }
    _write_json(output / "summary.json", summary)

    class_md = [
        "# E4-A Class Reliability",
        "",
        "Reliability tiers are conservative and based on held-out E3-B6 class behavior, "
        "E3-B5 confusion/bias evidence, and manifest support. They are not release decisions.",
        "",
        "## Tier Counts",
        "",
        "```json",
        json.dumps(dict(counts), indent=2),
        "```",
        "",
        "## Top Rows",
        "",
        _markdown_table(class_rows, front[:10], 50),
        "",
    ]
    (output / "class_reliability.md").write_text("\n".join(class_md), encoding="utf-8")

    (output / "confusion_groups.md").write_text(
        "\n".join(
            [
                "# E4-A Confusion Groups",
                "",
                "Likely causes are hypotheses until video/label review is performed.",
                "",
                _markdown_table(
                    confusion_rows,
                    [
                        "group",
                        "total_confusions",
                        "max_confusion_rate",
                        "branch_count",
                        "split_count",
                        "directions",
                        "likely_cause",
                    ],
                    50,
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )
    (output / "signer_generalization.md").write_text(
        "\n".join(
            [
                "# E4-A Signer Generalization",
                "",
                data["signer_note"],
                "",
                _markdown_table(
                    signer_rows,
                    ["split", "participant_id", "clip_count", "class_count", "median_length"],
                    80,
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )
    (output / "data_quality_support.md").write_text(
        "\n".join(
            [
                "# E4-A Data Quality And Support",
                "",
                "Support risks are derived from the frozen E3-B5 manifest only.",
                "",
                _markdown_table(
                    support_rows,
                    [
                        "gloss",
                        "train_clips",
                        "val_clips",
                        "test_clips",
                        "train_signer_count",
                        "val_signer_count",
                        "test_signer_count",
                        "support_risks",
                    ],
                    80,
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )
    (output / "vocabulary_recommendation.md").write_text(
        "\n".join(
            [
                "# E4-A Vocabulary Recommendation",
                "",
                f"Candidate keep classes: {len(keep)}.",
                f"Borderline collect-more classes: {len(borderline)}.",
                f"Hard/defer classes: {len(hard)}.",
                "",
                "## Recommendation",
                "",
                next_decision,
                "",
                "A class excluded from `reliable_vocabulary_v0.csv` is not permanently removed. "
                "It is deferred until collection, label review, or a stronger evidence "
                "stream justifies it.",
                "",
                "## Candidate Keep",
                "",
                _markdown_table(
                    keep,
                    ["gloss", "e3_b6_val_mean_all", "e3_b6_test_mean_all", "recommendation_reason"],
                    80,
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )
    (output / "next_experiment_decision.md").write_text(
        "\n".join(
            [
                "# E4-A Next Experiment Decision",
                "",
                f"Recommended next decision: **{next_decision}**.",
                "",
                "## Reason",
                "",
                "E4-A is designed to prevent another blind training run. The next step depends on "
                "how many classes survive the conservative reliability gate and how many require "
                "label/confusion/data review.",
                "",
                "## Go/No-Go For E4-B",
                "",
                "Go to E4-B only if the user accepts the proposed reliable vocabulary or targeted "
                "collection plan. Do not train on a class list that has not been reviewed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (output / "summary.md").write_text(
        "\n".join(
            [
                "# E4-A Summary",
                "",
                f"Classes audited: {len(class_rows)}",
                f"Tier counts: `{dict(counts)}`",
                f"Recommended next decision: **{next_decision}**",
                "",
                "See `class_reliability.md`, `confusion_groups.md`, `data_quality_support.md`, "
                "`signer_generalization.md`, and `vocabulary_recommendation.md`.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (output / "README_RUN.md").write_text(
        "\n".join(
            [
                "# E4-A Landmark Generalization Audit Run",
                "",
                "```powershell",
                'cd "F:\\ASL DATASET\\5. Apphear3"',
                f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_a_generalization_audit '
                f'run --output "{output}"',
                f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e4_a_generalization_audit '
                f'check --run-dir "{output}"',
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_json(
        output / "check_report.json",
        {"run_dir": str(output.resolve()), "passed": True, "errors": []},
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True, exist_ok=True)
    paths = {"e3_b5": args.e3_b5, "e3_b6": args.e3_b6, "e3_b7": args.e3_b7, "e3_c": args.e3_c}
    inventory = _inventory(paths)
    _write_json(output / "inventory.json", inventory)
    missing = [name for name, item in inventory["sources"].items() if not item["exists"]]
    if missing:
        raise FileNotFoundError(f"missing source runs: {missing}")
    class_rows = _build_class_reliability(paths)
    confusion_rows = _build_confusion_groups(paths)
    support_rows = _build_support_rows(paths)
    signer_rows, signer_note = _build_signer_rows(paths)
    data = {
        "class_reliability": class_rows,
        "confusion_groups": confusion_rows,
        "data_quality_support": support_rows,
        "signer_generalization": signer_rows,
        "signer_note": signer_note,
    }
    _write_reports(output, data)
    return _read_json(output / "summary.json")


def check(args: argparse.Namespace) -> dict[str, Any]:
    required = [
        "inventory.json",
        "class_reliability.csv",
        "class_reliability.md",
        "confusion_groups.csv",
        "confusion_groups.md",
        "signer_generalization.csv",
        "signer_generalization.md",
        "data_quality_support.csv",
        "data_quality_support.md",
        "reliable_vocabulary_v0.csv",
        "hard_confusion_set_v0.csv",
        "vocabulary_recommendation.md",
        "next_experiment_decision.md",
        "summary.json",
        "summary.md",
        "README_RUN.md",
    ]
    errors = [f"missing output: {name}" for name in required if not (args.run_dir / name).exists()]
    if (args.run_dir / "summary.json").exists():
        summary = _read_json(args.run_dir / "summary.json")
        if not summary.get("recommended_next_decision"):
            errors.append("summary missing recommended_next_decision")
    result = {"run_dir": str(args.run_dir.resolve()), "passed": not errors, "errors": errors}
    _write_json(args.run_dir / "check_report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="E4-A landmark generalization audit")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--e3-b5", type=Path, default=DEFAULT_E3_B5)
    run_parser.add_argument("--e3-b6", type=Path, default=DEFAULT_E3_B6)
    run_parser.add_argument("--e3-b7", type=Path, default=DEFAULT_E3_B7)
    run_parser.add_argument("--e3-c", type=Path, default=DEFAULT_E3_C)
    run_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_parser.add_argument("--overwrite", action="store_true")

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)

    args = parser.parse_args()
    try:
        if args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, FileExistsError, KeyError, ValueError, OSError) as error:
        print(f"[e4-a] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

