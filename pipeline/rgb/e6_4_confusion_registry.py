"""E6-4 frozen confusion-registry evidence mining.

Runs inference only. No extraction, training, rejection, export, or Android
asset is performed or modified.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from pipeline.rgb.e6_3_open_set_rejection import _load_negative_features, _subset_negative
from pipeline.rgb.e6_v30_five_sign_baseline import CLASSES, SEEDS

EXPERIMENT = "e6_4_frozen_confusion_registry_v1"
DEFAULT_V30_FEATURES = Path(
    "artifacts/recognition_upgrade/e6_baseline/e6_v30_validation_repair_01/dataset/features"
)
DEFAULT_V30_MODELS = Path(
    "artifacts/recognition_upgrade/e6_baseline/"
    "e6_v30_five_sign_transfer_repaired_val_01/models"
)
DEFAULT_GEOMETRY_FEATURES = Path(
    "artifacts/recognition_upgrade/e6_landmark_geometry/e6_2_geometry_01/dataset/features"
)
DEFAULT_GEOMETRY_MODELS = Path(
    "artifacts/recognition_upgrade/e6_landmark_geometry/e6_2_geometry_01/models"
)
DEFAULT_E63 = Path(
    "artifacts/recognition_upgrade/e6_rejection/e6_3_frozen_embedding_01"
)
DEFAULT_OUTPUT = Path(
    "artifacts/recognition_upgrade/e6_registry/e6_4_confusion_registry_01"
)
POSITIVE_VIEWS = ("val", "validation_variant_stress", "test_fresh", "test_historical")
QUALIFYING_VIEWS = ("validation_variant_stress", "test_fresh", "test_historical")
FAMILIES = ("v30_primary", "geometry_corroboration")
REGISTRY_RATE = 0.20
REGISTRY_VIEWS = 2
REGISTRY_SAMPLES = 10
REGISTRY_SIGNERS = 2


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _load_split(root: Path, split: str, expected_dim: int) -> dict[str, np.ndarray]:
    path = root / f"{split}.npz"
    if not path.exists():
        raise FileNotFoundError(path)
    with np.load(path, allow_pickle=False) as data:
        required = {"X", "frame_mask", "lengths", "y", "sample_ids", "participant_ids", "source_ids"}
        missing = required.difference(data.files)
        if missing:
            raise ValueError(f"{path} missing keys: {sorted(missing)}")
        result = {key: data[key] for key in data.files}
    if tuple(result["X"].shape[1:]) != (96, expected_dim):
        raise ValueError(f"{split}: expected [N,96,{expected_dim}], got {result['X'].shape}")
    return result


def _masked_mean(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    weights = mask.astype(np.float64)[..., None]
    return (values.astype(np.float64) * weights).sum(axis=1) / np.maximum(weights.sum(axis=1), 1.0)


def _predict(model_path: Path, data: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    import tensorflow as tf

    model = tf.keras.models.load_model(model_path, compile=False)
    probabilities = model.predict(data["X"].astype(np.float32), batch_size=64, verbose=0)
    if probabilities.shape[:2] != (len(data["X"]), 96) or probabilities.shape[2] != len(CLASSES):
        raise ValueError(f"unexpected output from {model_path}: {probabilities.shape}")
    clip = _masked_mean(probabilities, data["frame_mask"].astype(bool))
    prediction = np.argmax(clip, axis=1)
    order = np.argsort(clip, axis=1)
    confidence = clip[np.arange(len(clip)), prediction]
    margin = confidence - clip[np.arange(len(clip)), order[:, -2]]
    return {"probabilities": clip, "prediction": prediction, "confidence": confidence, "margin": margin}


def _positive_rows(
    family: str,
    split: str,
    seed: int,
    data: dict[str, np.ndarray],
    outputs: dict[str, np.ndarray],
) -> list[dict[str, Any]]:
    rows = []
    for index in range(len(data["y"])):
        true_id = int(data["y"][index])
        pred_id = int(outputs["prediction"][index])
        rows.append(
            {
                "family": family,
                "seed": seed,
                "view": split,
                "sample_id": str(data["sample_ids"][index]),
                "signer_id": str(data["participant_ids"][index]),
                "source_id": str(data["source_ids"][index]),
                "true_label": CLASSES[true_id],
                "predicted_label": CLASSES[pred_id],
                "correct": int(true_id == pred_id),
                "confidence": float(outputs["confidence"][index]),
                "margin": float(outputs["margin"][index]),
            }
        )
    return rows


def _negative_rows(seed: int, data: dict[str, Any], outputs: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    rows = []
    for index, source in enumerate(data["rows"]):
        pred_id = int(outputs["prediction"][index])
        rows.append(
            {
                "seed": seed,
                "assignment_id": source["assignment_id"],
                "role": source["role"],
                "negative_subtype": source["negative_subtype"],
                "signer_id": source["signer_group_id"],
                "predicted_label": CLASSES[pred_id],
                "confidence": float(outputs["confidence"][index]),
                "margin": float(outputs["margin"][index]),
            }
        )
    return rows


def _consensus(positive_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in positive_rows:
        groups[(row["family"], row["view"], row["sample_id"])].append(row)
    results = []
    for (family, view, sample_id), rows in sorted(groups.items()):
        if len(rows) != len(SEEDS):
            raise ValueError(f"{family}/{view}/{sample_id}: expected {len(SEEDS)} seeds")
        counts = Counter(row["predicted_label"] for row in rows)
        predicted, votes = counts.most_common(1)[0]
        if votes < 2:
            predicted = "NO_MAJORITY"
        first = rows[0]
        results.append(
            {
                "family": family,
                "view": view,
                "sample_id": sample_id,
                "signer_id": first["signer_id"],
                "source_id": first["source_id"],
                "true_label": first["true_label"],
                "majority_prediction": predicted,
                "majority_votes": votes,
                "unanimous": int(votes == len(SEEDS)),
                "wrong_majority": int(predicted not in {first["true_label"], "NO_MAJORITY"}),
                "seed_predictions": ";".join(
                    f"{row['seed']}:{row['predicted_label']}" for row in sorted(rows, key=lambda item: item["seed"])
                ),
            }
        )
    return results


def _directed_confusions(
    positive_rows: list[dict[str, Any]], consensus: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seed_rows = []
    for (family, view, seed, true_label), rows in sorted(
        _group(positive_rows, lambda row: (row["family"], row["view"], row["seed"], row["true_label"])).items()
    ):
        total = len(rows)
        for predicted in CLASSES:
            if predicted == true_label:
                continue
            count = sum(row["predicted_label"] == predicted for row in rows)
            seed_rows.append(
                {
                    "family": family,
                    "view": view,
                    "seed": seed,
                    "true_label": true_label,
                    "predicted_label": predicted,
                    "true_count": total,
                    "confusion_count": count,
                    "confusion_rate": count / total if total else 0.0,
                }
            )
    consensus_rows = []
    for (family, view, true_label), rows in sorted(
        _group(consensus, lambda row: (row["family"], row["view"], row["true_label"])).items()
    ):
        total = len(rows)
        for predicted in CLASSES:
            if predicted == true_label:
                continue
            selected = [row for row in rows if row["majority_prediction"] == predicted]
            unanimous = [row for row in selected if row["unanimous"]]
            consensus_rows.append(
                {
                    "family": family,
                    "view": view,
                    "true_label": true_label,
                    "predicted_label": predicted,
                    "true_count": total,
                    "majority_count": len(selected),
                    "majority_rate": len(selected) / total if total else 0.0,
                    "unanimous_count": len(unanimous),
                    "unanimous_rate": len(unanimous) / total if total else 0.0,
                    "signer_count": len({row["signer_id"] for row in selected}),
                    "supporting_sample_ids": ";".join(row["sample_id"] for row in selected),
                }
            )
    return seed_rows, consensus_rows


def _group(rows: Iterable[dict[str, Any]], key: Any) -> dict[Any, list[dict[str, Any]]]:
    result: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[key(row)].append(row)
    return result


def _pair_decisions(
    positive_rows: list[dict[str, Any]], consensus: list[dict[str, Any]], consensus_table: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    primary = [row for row in consensus_table if row["family"] == "v30_primary"]
    geometry = {
        (row["view"], row["true_label"], row["predicted_label"]): row
        for row in consensus_table if row["family"] == "geometry_corroboration"
    }
    primary_consensus = [row for row in consensus if row["family"] == "v30_primary"]
    decisions = []
    registry = []
    for true_label in CLASSES:
        for predicted in CLASSES:
            if true_label == predicted:
                continue
            view_rows = [
                row for row in primary
                if row["true_label"] == true_label and row["predicted_label"] == predicted
                and row["view"] in QUALIFYING_VIEWS
            ]
            qualifying = [row for row in view_rows if float(row["majority_rate"]) >= REGISTRY_RATE]
            support = [
                row for row in primary_consensus
                if row["view"] in {item["view"] for item in qualifying}
                and row["true_label"] == true_label and row["majority_prediction"] == predicted
            ]
            signers = sorted({row["signer_id"] for row in support})
            seed_counts = {
                seed: sum(
                    row["seed"] == seed and row["view"] in {item["view"] for item in qualifying}
                    and row["true_label"] == true_label and row["predicted_label"] == predicted
                    for row in positive_rows if row["family"] == "v30_primary"
                )
                for seed in SEEDS
            }
            geometry_confirmed = [
                row["view"] for row in view_rows
                if float(geometry.get((row["view"], true_label, predicted), {}).get("majority_rate", 0.0))
                >= REGISTRY_RATE
            ]
            registered = bool(
                len(qualifying) >= REGISTRY_VIEWS
                and len(support) >= REGISTRY_SAMPLES
                and len(signers) >= REGISTRY_SIGNERS
                and all(count > 0 for count in seed_counts.values())
            )
            strongest = max((float(row["majority_rate"]) for row in view_rows), default=0.0)
            if registered:
                status = "registered_provisional"
            elif strongest >= 0.50 and any(
                float(row["majority_rate"]) >= 0.50 and row["view"] in geometry_confirmed
                for row in view_rows
            ):
                status = "single_domain_strong"
            elif strongest >= 0.10 or len(support) >= 5:
                status = "monitor"
            else:
                status = "not_reproducible"
            item = {
                "group_id": f"{true_label}__TO__{predicted}",
                "true_label": true_label,
                "predicted_label": predicted,
                "status": status,
                "qualifying_view_count": len(qualifying),
                "qualifying_views": ";".join(row["view"] for row in qualifying),
                "strongest_majority_rate": strongest,
                "supporting_sample_count": len(support),
                "supporting_signer_count": len(signers),
                "supporting_signers": ";".join(signers),
                "seed_101_error_count": seed_counts[101],
                "seed_202_error_count": seed_counts[202],
                "seed_303_error_count": seed_counts[303],
                "geometry_confirmed_views": ";".join(geometry_confirmed),
                "supporting_sample_ids": ";".join(row["sample_id"] for row in support),
            }
            decisions.append(item)
            if registered:
                registry.append(item)
    return decisions, registry


def _negative_attraction(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    groups = _group(rows, lambda row: (row["role"], row["negative_subtype"], row["seed"]))
    for (role, subtype, seed), items in sorted(groups.items()):
        for label in CLASSES:
            selected = [row for row in items if row["predicted_label"] == label]
            output.append(
                {
                    "role": role,
                    "negative_subtype": subtype,
                    "seed": seed,
                    "predicted_label": label,
                    "negative_count": len(items),
                    "prediction_count": len(selected),
                    "prediction_share": len(selected) / len(items),
                    "mean_confidence": float(np.mean([row["confidence"] for row in selected])) if selected else 0.0,
                }
            )
    return output


def _integrity(v30_root: Path) -> dict[str, Any]:
    splits = {
        split: _load_split(v30_root, split, 258)
        for split in ("train", *POSITIVE_VIEWS)
    }
    sample_sets = {split: set(data["sample_ids"].astype(str)) for split, data in splits.items()}
    signer_sets = {split: set(data["participant_ids"].astype(str)) for split, data in splits.items()}
    sample_overlaps = {}
    signer_overlaps = {}
    names = list(splits)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            sample = sorted(sample_sets[left] & sample_sets[right])
            signer = sorted(signer_sets[left] & signer_sets[right])
            if sample:
                sample_overlaps[f"{left}:{right}"] = sample
            if signer:
                signer_overlaps[f"{left}:{right}"] = signer
    return {
        "split_counts": {split: len(data["y"]) for split, data in splits.items()},
        "sample_overlaps": sample_overlaps,
        "signer_overlaps": signer_overlaps,
        "passed": not sample_overlaps and not signer_overlaps,
    }


def run(args: argparse.Namespace) -> int:
    output = args.output.resolve()
    for relative in ("predictions", "tables", "reports"):
        (output / relative).mkdir(parents=True, exist_ok=True)
    integrity = _integrity(args.v30_features.resolve())
    if not integrity["passed"]:
        raise ValueError(f"split integrity failed: {integrity}")
    family_specs = {
        "v30_primary": (args.v30_features.resolve(), args.v30_models.resolve(), 258),
        "geometry_corroboration": (args.geometry_features.resolve(), args.geometry_models.resolve(), 444),
    }
    positive_rows: list[dict[str, Any]] = []
    for family, (feature_root, model_root, dimension) in family_specs.items():
        split_data = {split: _load_split(feature_root, split, dimension) for split in POSITIVE_VIEWS}
        for seed in SEEDS:
            model_path = model_root / f"seed_{seed}" / "latest.keras"
            if not model_path.exists():
                raise FileNotFoundError(model_path)
            print(f"[e6-4] {family} seed {seed}")
            for split, data in split_data.items():
                positive_rows.extend(_positive_rows(family, split, seed, data, _predict(model_path, data)))

    negative_data = _load_negative_features(args.e63_run.resolve())
    negative_rows: list[dict[str, Any]] = []
    for seed in SEEDS:
        model_path = args.v30_models.resolve() / f"seed_{seed}" / "latest.keras"
        negative_rows.extend(_negative_rows(seed, negative_data, _predict(model_path, negative_data)))

    consensus = _consensus(positive_rows)
    directed, consensus_table = _directed_confusions(positive_rows, consensus)
    decisions, registry = _pair_decisions(positive_rows, consensus, consensus_table)
    attraction = _negative_attraction(negative_rows)

    _write_csv(output / "predictions" / "positive_predictions.csv", positive_rows, list(positive_rows[0]))
    _write_csv(output / "predictions" / "negative_predictions.csv", negative_rows, list(negative_rows[0]))
    _write_csv(output / "tables" / "positive_consensus.csv", consensus, list(consensus[0]))
    _write_csv(output / "tables" / "directed_confusions.csv", directed, list(directed[0]))
    _write_csv(output / "tables" / "consensus_confusions.csv", consensus_table, list(consensus_table[0]))
    _write_csv(output / "tables" / "pair_decisions.csv", decisions, list(decisions[0]))
    _write_csv(
        output / "tables" / "confusion_registry.csv",
        registry,
        list(decisions[0]),
    )
    _write_csv(output / "tables" / "negative_attraction.csv", attraction, list(attraction[0]))

    status_counts = Counter(row["status"] for row in decisions)
    summary = {
        "experiment": EXPERIMENT,
        "run_dir": str(output),
        "classes": CLASSES,
        "seeds": SEEDS,
        "positive_prediction_rows": len(positive_rows),
        "negative_prediction_rows": len(negative_rows),
        "consensus_rows": len(consensus),
        "integrity": integrity,
        "registry_rule": {
            "majority_rate_min": REGISTRY_RATE,
            "qualifying_views_min": REGISTRY_VIEWS,
            "supporting_samples_min": REGISTRY_SAMPLES,
            "supporting_signers_min": REGISTRY_SIGNERS,
            "all_seeds_required": True,
        },
        "pair_status_counts": dict(sorted(status_counts.items())),
        "registered_groups": registry,
        "registered_group_count": len(registry),
        "passed": True,
        "decision": "registry_evidence_complete",
        "warnings": [
            "A structural pass does not authorize a specialist or Android integration.",
            "Geometry is corroborating evidence only because E6-2 failed promotion.",
            "Negative attraction is not a supported-sign confusion registry.",
        ],
    }
    _write_json(output / "reports" / "registry_summary.json", summary)
    report_lines = [
        "# E6-4 Frozen Confusion Registry Report",
        "",
        f"Registered provisional groups: `{len(registry)}`.",
        "",
        "| Group | Views | Samples | Signers | Geometry corroboration |",
        "|---|---|---:|---:|---|",
    ]
    for row in registry:
        report_lines.append(
            f"| `{row['true_label']} -> {row['predicted_label']}` | `{row['qualifying_views']}` | "
            f"{row['supporting_sample_count']} | {row['supporting_signer_count']} | "
            f"`{row['geometry_confirmed_views']}` |"
        )
    if not registry:
        report_lines.append("| none | - | 0 | 0 | - |")
    report_lines.extend(
        ["", "This is evidence mining only. No specialist, router, export, or Android change is authorized.", ""]
    )
    (output / "reports" / "registry_report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


def check(args: argparse.Namespace) -> int:
    output = args.run_dir.resolve()
    required = [
        "predictions/positive_predictions.csv",
        "predictions/negative_predictions.csv",
        "tables/positive_consensus.csv",
        "tables/directed_confusions.csv",
        "tables/consensus_confusions.csv",
        "tables/pair_decisions.csv",
        "tables/confusion_registry.csv",
        "tables/negative_attraction.csv",
        "reports/registry_summary.json",
        "reports/registry_report.md",
    ]
    errors = [relative for relative in required if not (output / relative).exists()]
    if not errors:
        summary = json.loads((output / "reports" / "registry_summary.json").read_text(encoding="utf-8"))
        if not summary.get("passed") or not summary.get("integrity", {}).get("passed"):
            errors.append("summary or integrity gate failed")
        positive = sum(1 for _ in (output / "predictions" / "positive_predictions.csv").open(encoding="utf-8")) - 1
        negative = sum(1 for _ in (output / "predictions" / "negative_predictions.csv").open(encoding="utf-8")) - 1
        if positive != int(summary.get("positive_prediction_rows", -1)):
            errors.append("positive prediction row count mismatch")
        if negative != int(summary.get("negative_prediction_rows", -1)):
            errors.append("negative prediction row count mismatch")
    result = {"run_dir": str(output), "passed": not errors, "errors": errors}
    _write_json(output / "check_report.json", result)
    print(json.dumps(result, indent=2))
    return 0 if not errors else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--v30-features", type=Path, default=DEFAULT_V30_FEATURES)
    run_parser.add_argument("--v30-models", type=Path, default=DEFAULT_V30_MODELS)
    run_parser.add_argument("--geometry-features", type=Path, default=DEFAULT_GEOMETRY_FEATURES)
    run_parser.add_argument("--geometry-models", type=Path, default=DEFAULT_GEOMETRY_MODELS)
    run_parser.add_argument("--e63-run", type=Path, default=DEFAULT_E63)
    run_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run_parser.set_defaults(func=run)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    check_parser.set_defaults(func=check)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"[e6-4] ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
