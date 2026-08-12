"""Build and verify the research-only C0-B0 Stage 2 dataset manifest."""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from pipeline.tracking.e2e_c0b import _path_key, _read_csv, _write_csv, _write_json

EXPERIMENT = "c0b_stage2_research_manifest_v1"
DEFAULT_ROOT = Path("artifacts/recognition_upgrade/e2e_c0")
DEFAULT_BASE = DEFAULT_ROOT / "c0b_training_annotation_pilot_01"
DEFAULT_TOPUP = DEFAULT_ROOT / "c0b_condition_topup_01"
DEFAULT_INVENTORY = DEFAULT_ROOT / "c0b_inventory_01"
DEFAULT_OUTPUT = DEFAULT_ROOT / "c0b_stage2_research_manifest_01"

CONDITION_FIELDS = (
    "motion_blur",
    "occlusion",
    "near_face",
    "edge_clipped",
    "partial_visibility",
)

MANIFEST_FIELDS = (
    "sample_id",
    "source_run",
    "source_dataset",
    "source_split",
    "participant_id",
    "gloss",
    "raw_video_path",
    "raw_video_sha256",
    "frame_index",
    "timestamp_ms",
    "center_image_path",
    "context_panel_path",
    "gold_hands_json",
    "hand_count",
    *CONDITION_FIELDS,
    "dataset_split",
    "split_reason",
    "research_only",
)


def _load_run(run: Path) -> list[dict[str, Any]]:
    annotations = {row["sample_id"]: row for row in _read_csv(run / "annotation_manifest.csv")}
    reviews = _read_csv(run / "gold_review.csv")
    rows: list[dict[str, Any]] = []
    for review in reviews:
        if review.get("review_status") != "accepted":
            continue
        sample_id = review["sample_id"]
        annotation = annotations.get(sample_id)
        if annotation is None:
            raise ValueError(f"{run}: missing annotation row for {sample_id}")
        boxes = json.loads(review.get("gold_hands_json", "[]"))
        if not isinstance(boxes, list):
            raise ValueError(f"{run}: invalid gold box list for {sample_id}")
        rows.append(
            {
                "sample_id": sample_id,
                "source_run": run.name,
                "source_dataset": annotation["source_dataset"],
                "source_split": annotation["source_split"],
                "participant_id": annotation["participant_id"],
                "gloss": annotation["gloss"],
                "raw_video_path": annotation["raw_video_path"],
                "raw_video_sha256": annotation["raw_video_sha256"].upper(),
                "frame_index": annotation["frame_index"],
                "timestamp_ms": annotation["timestamp_ms"],
                "center_image_path": annotation["center_image_path"],
                "context_panel_path": annotation["context_panel_path"],
                "gold_hands_json": review["gold_hands_json"],
                "hand_count": len(boxes),
                **{field: review.get(field, "no") for field in CONDITION_FIELDS},
                "dataset_split": "",
                "split_reason": "",
                "research_only": "true",
            }
        )
    return rows


def _stats(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "rows": len(rows),
        "hand_instances": sum(int(row["hand_count"]) for row in rows),
        "no_hand": sum(int(row["hand_count"]) == 0 for row in rows),
        "one_hand": sum(int(row["hand_count"]) == 1 for row in rows),
        "two_hand": sum(int(row["hand_count"]) == 2 for row in rows),
        **{
            field: sum(row[field] == "yes" for row in rows)
            for field in CONDITION_FIELDS
        },
    }


def _subset_score(
    development: list[dict[str, Any]], all_rows: list[dict[str, Any]], target: float
) -> float:
    dev = _stats(development)
    total = _stats(all_rows)
    metrics = ("rows", "no_hand", "two_hand", *CONDITION_FIELDS)
    score = 0.0
    for metric in metrics:
        count = total[metric]
        if count == 0:
            continue
        desired = count * target
        weight = 2.0 if metric in CONDITION_FIELDS or metric == "no_hand" else 1.0
        score += weight * ((dev[metric] - desired) / max(1.0, desired)) ** 2
        if count >= 2 and dev[metric] == 0:
            score += 4.0
        if count >= 2 and dev[metric] == count:
            score += 8.0
    return score


def _choose_development_signers(
    rows: list[dict[str, Any]], target: float, seed: int
) -> set[str]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["participant_id"])].append(row)
    signers = sorted(grouped)
    if len(signers) < 2:
        raise ValueError("each source requires at least two signers for a disjoint split")

    candidates: list[set[str]] = []
    if len(signers) <= 12:
        for size in range(1, len(signers)):
            candidates.extend(set(values) for values in combinations(signers, size))
    else:
        rng = random.Random(seed)
        seen: set[tuple[str, ...]] = set()
        attempts = 50_000
        for _ in range(attempts):
            chosen = tuple(sorted(signer for signer in signers if rng.random() < target))
            if chosen and len(chosen) < len(signers) and chosen not in seen:
                seen.add(chosen)
                candidates.append(set(chosen))

    if not candidates:
        raise ValueError("could not generate a development-signer candidate")
    return min(
        candidates,
        key=lambda chosen: _subset_score(
            [row for row in rows if row["participant_id"] in chosen], rows, target
        ),
    )


def _assign_splits(
    rows: list[dict[str, Any]], target: float, seed: int
) -> dict[str, set[str]]:
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_source[str(row["source_dataset"])].append(row)
    chosen_by_source = {
        source: _choose_development_signers(source_rows, target, seed + offset)
        for offset, (source, source_rows) in enumerate(sorted(by_source.items()))
    }
    for row in rows:
        source = str(row["source_dataset"])
        signer = str(row["participant_id"])
        is_development = signer in chosen_by_source[source]
        row["dataset_split"] = "development" if is_development else "train"
        row["split_reason"] = (
            "source-specific held-out signer" if is_development else "source-specific train signer"
        )
    return chosen_by_source


def _verify(
    rows: list[dict[str, Any]], protected_paths: set[str], protected_hashes: set[str]
) -> list[str]:
    errors: list[str] = []
    for field in ("sample_id", "raw_video_path", "raw_video_sha256"):
        values = [str(row[field]).casefold() for row in rows]
        if len(values) != len(set(values)):
            errors.append(f"duplicate {field}")
    if any(_path_key(row["raw_video_path"]) in protected_paths for row in rows):
        errors.append("protected path overlap")
    if any(str(row["raw_video_sha256"]).upper() in protected_hashes for row in rows):
        errors.append("protected hash overlap")
    for source in sorted({str(row["source_dataset"]) for row in rows}):
        train_signers = {
            row["participant_id"]
            for row in rows
            if row["source_dataset"] == source and row["dataset_split"] == "train"
        }
        dev_signers = {
            row["participant_id"]
            for row in rows
            if row["source_dataset"] == source and row["dataset_split"] == "development"
        }
        if train_signers & dev_signers:
            errors.append(f"{source}: signer overlap")
        if not train_signers or not dev_signers:
            errors.append(f"{source}: empty train or development signer set")
    for split in ("train", "development"):
        split_rows = [row for row in rows if row["dataset_split"] == split]
        if not split_rows:
            errors.append(f"empty {split} split")
            continue
        if not any(int(row["hand_count"]) == 0 for row in split_rows):
            errors.append(f"{split}: no negative frames")
        if not any(int(row["hand_count"]) > 0 for row in split_rows):
            errors.append(f"{split}: no positive frames")
    return errors


def build(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    rows = _load_run(args.base_run) + _load_run(args.topup_run)
    protected = _read_csv(args.inventory / "protected_source_registry.csv")
    protected_paths = {
        _path_key(row["raw_video_path"]) for row in protected if row.get("raw_video_path")
    }
    protected_hashes = {
        row["raw_video_sha256"].upper()
        for row in protected
        if row.get("raw_video_sha256", "").strip()
    }
    chosen = _assign_splits(rows, args.development_fraction, args.seed)
    errors = _verify(rows, protected_paths, protected_hashes)
    _write_csv(output / "stage2_manifest.csv", rows, MANIFEST_FIELDS)

    split_rows = {
        split: [row for row in rows if row["dataset_split"] == split]
        for split in ("train", "development")
    }
    summary = {
        "experiment": EXPERIMENT,
        "scope": "internal non-commercial research only",
        "rows": len(rows),
        "sources": dict(sorted(Counter(row["source_dataset"] for row in rows).items())),
        "source_signers": {
            source: len({row["participant_id"] for row in rows if row["source_dataset"] == source})
            for source in sorted({row["source_dataset"] for row in rows})
        },
        "development_signers": {
            source: sorted(signers) for source, signers in sorted(chosen.items())
        },
        "split_counts": {split: len(values) for split, values in split_rows.items()},
        "split_stats": {split: _stats(values) for split, values in split_rows.items()},
        "signer_overlap": False,
        "protected_path_overlap": False,
        "protected_hash_overlap": False,
        "errors": errors,
        "passed": not errors,
        "training_authorized": False,
        "next": "verify manifest, then require separate research-training authorization",
    }
    _write_json(output / "manifest_summary.json", summary)
    (output / "README_RUN.md").write_text(
        "# C0-B0 Stage 2 Research Manifest\n\n"
        "Internal non-commercial research only. This manifest does not authorize training or "
        "production use. Splits are source-specific and signer-disjoint. P0/N0/P1 remain frozen.\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    run = args.run_dir
    rows = _read_csv(run / "stage2_manifest.csv")
    protected = _read_csv(args.inventory / "protected_source_registry.csv")
    protected_paths = {
        _path_key(row["raw_video_path"]) for row in protected if row.get("raw_video_path")
    }
    protected_hashes = {
        row["raw_video_sha256"].upper()
        for row in protected
        if row.get("raw_video_sha256", "").strip()
    }
    errors = _verify(rows, protected_paths, protected_hashes)
    summary = {
        "run_dir": str(run.resolve()),
        "rows": len(rows),
        "split_counts": dict(sorted(Counter(row["dataset_split"] for row in rows).items())),
        "errors": errors,
        "passed": not errors,
        "training_authorized": False,
    }
    _write_json(run / "check_report.json", summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="C0-B0 Stage 2 research manifest")
    commands = parser.add_subparsers(dest="command", required=True)

    build_parser = commands.add_parser("build")
    build_parser.add_argument("--base-run", type=Path, default=DEFAULT_BASE)
    build_parser.add_argument("--topup-run", type=Path, default=DEFAULT_TOPUP)
    build_parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    build_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build_parser.add_argument("--development-fraction", type=float, default=0.20)
    build_parser.add_argument("--seed", type=int, default=100826)
    build_parser.set_defaults(func=build)

    check_parser = commands.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT)
    check_parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    check_parser.set_defaults(func=check)

    args = parser.parse_args()
    try:
        result = args.func(args)
        return 0 if result.get("passed", True) else 2
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as error:
        print(f"[tracking/c0-b0-stage2] ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
