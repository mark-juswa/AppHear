"""Prepare the bounded second-pass human confirmation for NEGATIVE_GOLD_V1."""

from __future__ import annotations

import argparse
import json
import platform
import random
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pipeline.tracking.n0_blinded_readjudication import _dhash
from pipeline.tracking.negative_gold_open_images import (
    QUEUE_FIELDS,
    REVIEW_MAP_FIELDS,
    SEMANTIC_CLASSES,
    ReviewApp,
    _git,
    _read_csv,
    _resolve,
    _review_order,
    _sha256,
    _write_csv,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "model/config/recognition_upgrade/negative_gold_external_confirmation.json"
PROTOCOL = ROOT / "context/recognition_upgrade/NEGATIVE_GOLD_EXTERNAL_CONFIRMATION_PROTOCOL.md"


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if tuple(config["semantic_classes"]) != SEMANTIC_CLASSES:
        raise ValueError("semantic classes drifted")
    if int(config["canonical_candidate_count"]) != 160:
        raise ValueError("confirmation count drifted")
    if int(config["qc_repeat_count"]) != 20:
        raise ValueError("concealed-repeat count drifted")
    if int(config["dhash_hamming_max"]) != 4:
        raise ValueError("frozen dHash threshold drifted")
    if float(config["minimum_repeat_exact_agreement"]) != 0.92:
        raise ValueError("repeat-consistency threshold drifted")
    return config


def _verify_hashes(config: dict[str, Any]) -> dict[str, str]:
    first_pass = _resolve(config["first_pass_run"])
    actual = {}
    for relative, expected in config["expected_first_pass_hashes"].items():
        path = first_pass / relative
        value = _sha256(path)
        if value != expected:
            raise ValueError(f"first-pass artifact drifted: {relative}")
        actual[relative] = value
    seed_path = _resolve(config["seed_manifest"])
    seed_hash = _sha256(seed_path)
    if seed_hash != config["expected_seed_manifest_sha256"]:
        raise ValueError("frozen 76-frame seed manifest drifted")
    actual["NEGATIVE_GOLD_V1_SEED_MANIFEST.csv"] = seed_hash
    return actual


def _balanced_pick(rows: list[dict[str, str]], count: int, seed: int) -> list[dict[str, str]]:
    """Greedily spread selections across scene, author, and label metadata."""
    if count > len(rows):
        raise ValueError("diversity target exceeds eligible rows")
    rng = random.Random(seed)
    remaining = list(rows)
    rng.shuffle(remaining)
    selected: list[dict[str, str]] = []
    scene_counts: Counter[str] = Counter()
    author_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    while len(selected) < count:
        best = min(
            remaining,
            key=lambda row: (
                scene_counts[row["scene_bucket"]],
                author_counts[row["Author"]],
                label_counts[row["primary_label"]],
                rng.random(),
            ),
        )
        remaining.remove(best)
        selected.append(best)
        scene_counts[best["scene_bucket"]] += 1
        author_counts[best["Author"]] += 1
        label_counts[best["primary_label"]] += 1
    return selected


def _select_diverse(pool: list[dict[str, str]], count: int, seed: int) -> list[dict[str, str]]:
    by_category: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in pool:
        by_category[row["discovery_category"]].append(row)
    people = by_category["PEOPLE_PRESENT_DISCOVERY"]
    free = by_category["PERSON_FREE_DISCOVERY"]
    people_target = min(len(people), count)
    free_target = count - people_target
    if free_target > len(free):
        raise ValueError("eligible discovery categories cannot fill confirmation target")
    selected = _balanced_pick(people, people_target, seed)
    selected.extend(_balanced_pick(free, free_target, seed + 1))
    random.Random(seed + 2).shuffle(selected)
    return selected


def _assert_diversity(
    selected: list[dict[str, str]], seed_rows: list[dict[str, str]], threshold: int
) -> dict[str, int]:
    selected_hashes: set[str] = set()
    selected_dhashes: list[int] = []
    seed_hashes = {row["image_sha256"] for row in seed_rows}
    seed_dhashes = [int(row["dhash64"], 16) for row in seed_rows]
    minimum_internal = 64
    minimum_seed = 64
    for row in selected:
        image_hash = row["source_image_sha256"]
        fingerprint = int(row["dhash64"], 16)
        if image_hash in seed_hashes or image_hash in selected_hashes:
            raise ValueError(f"exact duplicate in selection: {row['ImageID']}")
        internal_distances = [(fingerprint ^ prior).bit_count() for prior in selected_dhashes]
        seed_distances = [(fingerprint ^ prior).bit_count() for prior in seed_dhashes]
        if internal_distances:
            minimum_internal = min(minimum_internal, min(internal_distances))
        if seed_distances:
            minimum_seed = min(minimum_seed, min(seed_distances))
        if any(distance <= threshold for distance in internal_distances):
            raise ValueError(f"internal dHash conflict: {row['ImageID']}")
        if any(distance <= threshold for distance in seed_distances):
            raise ValueError(f"seed dHash conflict: {row['ImageID']}")
        selected_hashes.add(image_hash)
        selected_dhashes.append(fingerprint)
    return {
        "minimum_internal_dhash_distance": minimum_internal,
        "minimum_seed_dhash_distance": minimum_seed,
    }


def prepare(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    output = _resolve(config["output_run"])
    temporary = output.with_name(output.name + ".preparing")
    if output.exists() or temporary.exists():
        raise FileExistsError(f"refusing to overwrite frozen package: {output}")
    if not PROTOCOL.is_file():
        raise FileNotFoundError(PROTOCOL)
    verified_hashes = _verify_hashes(config)
    first_pass = _resolve(config["first_pass_run"])
    seed_rows = _read_csv(_resolve(config["seed_manifest"]))
    canonical = _read_csv(first_pass / "canonical_human_labels_220.csv")
    repeat_qc = _read_csv(first_pass / "hidden_repeat_qc.csv")
    source_rows = _read_csv(first_pass / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.csv")
    source_by_id = {row["ImageID"]: row for row in source_rows}

    canonical_counts = Counter(row["semantic_class"] for row in canonical)
    if len(canonical) != 220 or canonical_counts != Counter(
        {"ZERO_HAND": 181, "HAND_VISIBLE": 38, "UNCERTAIN": 1}
    ):
        raise ValueError("first-pass canonical result does not match frozen evidence")
    discordant_ids = {
        row["canonical_review_id"]
        for row in repeat_qc
        if row["zero_vs_nonzero_disagreement"].lower() == "true"
    }
    if len(discordant_ids) != 2:
        raise ValueError("expected two first-pass binary-discordant canonical images")
    eligible_labels = [
        row
        for row in canonical
        if row["semantic_class"] == "ZERO_HAND" and row["review_id"] not in discordant_ids
    ]
    if len(eligible_labels) != 180:
        raise ValueError(f"eligible provisional-zero pool is {len(eligible_labels)}, not 180")

    eligible = []
    for label in eligible_labels:
        source = dict(source_by_id[label["open_images_id"]])
        image_path = Path(source["source_image_path"])
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        if _sha256(image_path) != source["source_image_sha256"]:
            raise ValueError(f"source bytes drifted: {source['ImageID']}")
        if f"{_dhash(image_path):016x}" != source["dhash64"]:
            raise ValueError(f"source dHash drifted: {source['ImageID']}")
        source["first_pass_review_id"] = label["review_id"]
        source["first_pass_semantic_class"] = label["semantic_class"]
        eligible.append(source)

    selected = _select_diverse(
        eligible, int(config["canonical_candidate_count"]), int(config["selection_seed"])
    )
    diversity = _assert_diversity(selected, seed_rows, int(config["dhash_hamming_max"]))
    selected_ids = {row["ImageID"] for row in selected}
    if len(selected_ids) != 160:
        raise ValueError("selected Open Images IDs are not unique")

    temporary.mkdir(parents=True)
    source_dir = temporary / "source_images"
    review_dir = temporary / "review_package"
    review_images = review_dir / "images"
    source_dir.mkdir()
    review_images.mkdir(parents=True)

    manifest_fields = tuple(source_rows[0])
    clean_manifest = [{field: row[field] for field in manifest_fields} for row in selected]
    for row in clean_manifest:
        target = source_dir / f"{row['ImageID']}.jpg"
        shutil.copy2(Path(row["source_image_path"]), target)
        row["source_image_path"] = str((output / "source_images" / target.name).resolve())
    _write_csv(
        temporary / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.csv", manifest_fields, clean_manifest
    )
    (temporary / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.json").write_text(
        json.dumps(clean_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    selection_fields = (
        "first_pass_review_id",
        "open_images_id",
        "first_pass_semantic_class",
        "source_image_sha256",
        "dhash64",
        "discovery_category",
        "scene_bucket",
        "author",
        "license",
    )
    selection_rows = [
        {
            "first_pass_review_id": row["first_pass_review_id"],
            "open_images_id": row["ImageID"],
            "first_pass_semantic_class": row["first_pass_semantic_class"],
            "source_image_sha256": row["source_image_sha256"],
            "dhash64": row["dhash64"],
            "discovery_category": row["discovery_category"],
            "scene_bucket": row["scene_bucket"],
            "author": row["Author"],
            "license": row["License"],
        }
        for row in selected
    ]
    _write_csv(temporary / "internal_confirmation_selection.csv", selection_fields, selection_rows)

    clean_by_id = {row["ImageID"]: row for row in clean_manifest}
    order = _review_order(selected, int(config["qc_repeat_count"]), int(config["qc_seed"]))
    canonical_review_ids: dict[str, str] = {}
    queue_rows = []
    map_rows = []
    for number, (row, is_repeat) in enumerate(order, start=1):
        review_id = f"confirmation_{number:04d}"
        if not is_repeat:
            canonical_review_ids[row["ImageID"]] = review_id
        target = review_images / f"{review_id}.jpg"
        shutil.copy2(source_dir / f"{row['ImageID']}.jpg", target)
        queue_rows.append(
            {
                "review_id": review_id,
                "image_path": str((output / "review_package" / "images" / target.name).resolve()),
                "review_status": "unreviewed",
                "semantic_class": "",
                "notes": "",
            }
        )
        map_rows.append(
            {
                "review_id": review_id,
                "candidate_id": clean_by_id[row["ImageID"]]["candidate_id"],
                "open_images_id": row["ImageID"],
                "canonical_review_id": "" if is_repeat else review_id,
                "is_qc_repeat": str(is_repeat).lower(),
                "source_image_sha256": row["source_image_sha256"],
            }
        )
    for row in map_rows:
        if row["is_qc_repeat"] == "true":
            row["canonical_review_id"] = canonical_review_ids[row["open_images_id"]]
    _write_csv(review_dir / "review_queue.csv", QUEUE_FIELDS, queue_rows)
    _write_csv(review_dir / "internal_repeat_map.csv", REVIEW_MAP_FIELDS, map_rows)
    for row in map_rows:
        if _sha256(review_images / f"{row['review_id']}.jpg") != row["source_image_sha256"]:
            raise ValueError(f"review copy bytes drifted: {row['review_id']}")

    shutil.copy2(first_pass / "ATTRIBUTION.md", temporary / "ATTRIBUTION.md")
    (temporary / "source_artifact_hashes.json").write_text(
        json.dumps(verified_hashes, indent=2), encoding="utf-8"
    )
    category_counts = Counter(row["discovery_category"] for row in selected)
    scene_counts = Counter(row["scene_bucket"] for row in selected)
    summary = {
        "status": "NEGATIVE_GOLD_EXTERNAL_CONFIRMATION_PACKAGE_FROZEN_UNREVIEWED",
        "first_pass_provisional_zero_hand": 181,
        "first_pass_binary_discordant_canonical_images": len(discordant_ids),
        "eligible_non_discordant_provisional_zero_hand": len(eligible),
        "canonical_confirmation_candidates": len(selected),
        "hidden_repeats": int(config["qc_repeat_count"]),
        "review_rows": len(queue_rows),
        "discovery_category_counts": dict(sorted(category_counts.items())),
        "scene_bucket_counts": dict(sorted(scene_counts.items())),
        "unique_authors": len({row["Author"] for row in selected}),
        "unique_primary_labels": len({row["primary_label"] for row in selected}),
        "frozen_near_duplicate_rule": "64-bit dHash Hamming distance <=4",
        **diversity,
        "human_truth_status": "UNREVIEWED_SECOND_PASS",
        "model_outputs_used": False,
    }
    (temporary / "prepare_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    provenance = {
        "protocol_version": config["protocol_version"],
        "branch": _git(["branch", "--show-current"]),
        "head": _git(["rev-parse", "HEAD"]),
        "working_tree_status": _git(["status", "--short"]),
        "python": sys.version,
        "platform": platform.platform(),
        "selection_seed": config["selection_seed"],
        "qc_seed": config["qc_seed"],
        "dhash_hamming_max": config["dhash_hamming_max"],
        "minimum_repeat_exact_agreement": config["minimum_repeat_exact_agreement"],
        "model_outputs_used": False,
        "new_downloads_performed": False,
        "first_pass_labels_exposed_to_reviewer": False,
        "config_sha256": _sha256(config_path),
        "protocol_sha256": _sha256(PROTOCOL),
        "runner_sha256": _sha256(Path(__file__)),
        "source_artifact_hashes": verified_hashes,
        "source_license_manifest_sha256": _sha256(
            temporary / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.csv"
        ),
        "internal_selection_sha256": _sha256(temporary / "internal_confirmation_selection.csv"),
        "review_queue_sha256": _sha256(review_dir / "review_queue.csv"),
        "internal_repeat_map_sha256": _sha256(review_dir / "internal_repeat_map.csv"),
    }
    (temporary / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    temporary.rename(output)
    return summary


def check_review(config: dict[str, Any]) -> dict[str, Any]:
    output = _resolve(config["output_run"])
    queue = _read_csv(output / "review_package/review_queue.csv")
    mapping = _read_csv(output / "review_package/internal_repeat_map.csv")
    errors = []
    counts: Counter[str] = Counter()
    for row in queue:
        if not Path(row["image_path"]).is_file():
            errors.append(f"missing image: {row['review_id']}")
        if row["review_status"] == "accepted" and row["semantic_class"] in SEMANTIC_CLASSES:
            counts[row["semantic_class"]] += 1
        elif row["review_status"] != "unreviewed":
            errors.append(f"invalid review state: {row['review_id']}")
    by_id = {row["review_id"]: row for row in mapping}
    for row in mapping:
        if row["is_qc_repeat"] == "true":
            canonical = by_id.get(row["canonical_review_id"])
            if canonical is None or canonical["source_image_sha256"] != row["source_image_sha256"]:
                errors.append(f"invalid repeat mapping: {row['review_id']}")
    completed = sum(row["review_status"] == "accepted" for row in queue)
    result = {
        "rows": len(queue),
        "canonical_candidates": len(queue) - int(config["qc_repeat_count"]),
        "hidden_repeats": int(config["qc_repeat_count"]),
        "completed": completed,
        "remaining": len(queue) - completed,
        "counts_including_hidden_repeats": dict(sorted(counts.items())),
        "errors": errors,
        "passed": not errors and completed == len(queue),
    }
    return result


def finalize_review(config: dict[str, Any]) -> dict[str, Any]:
    """Formalize the completed review without repairing or overriding human labels."""
    output = _resolve(config["output_run"])
    final_dir = output / "finalization"
    temporary = output / "finalization.preparing"
    if final_dir.exists() or temporary.exists():
        raise FileExistsError(f"refusing to overwrite finalization artifacts: {final_dir}")
    check = check_review(config)
    if not check["passed"]:
        raise ValueError("review is incomplete or structurally invalid")

    queue = _read_csv(output / "review_package/review_queue.csv")
    mapping = _read_csv(output / "review_package/internal_repeat_map.csv")
    source_rows = _read_csv(output / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.csv")
    selection_rows = _read_csv(output / "internal_confirmation_selection.csv")
    seed_rows = _read_csv(_resolve(config["seed_manifest"]))
    queue_by_id = {row["review_id"]: row for row in queue}
    map_by_id = {row["review_id"]: row for row in mapping}
    source_by_id = {row["ImageID"]: row for row in source_rows}
    selection_by_id = {row["open_images_id"]: row for row in selection_rows}

    second_pass = []
    for row in mapping:
        if row["is_qc_repeat"] == "true":
            continue
        review = queue_by_id[row["review_id"]]
        source = source_by_id[row["open_images_id"]]
        second_pass.append(
            {
                "second_pass_review_id": row["review_id"],
                "open_images_id": row["open_images_id"],
                "semantic_class": review["semantic_class"],
                "notes": review["notes"],
                "source_image_path": source["source_image_path"],
                "source_image_sha256": source["source_image_sha256"],
                "dhash64": source["dhash64"],
                "discovery_category": source["discovery_category"],
                "scene_bucket": source["scene_bucket"],
                "author": source["Author"],
                "license": source["License"],
            }
        )
    if len(second_pass) != int(config["canonical_candidate_count"]):
        raise ValueError("second-pass canonical count drifted")

    qc_rows = []
    for row in mapping:
        if row["is_qc_repeat"] != "true":
            continue
        canonical_label = queue_by_id[row["canonical_review_id"]]["semantic_class"]
        repeat_label = queue_by_id[row["review_id"]]["semantic_class"]
        exact = canonical_label == repeat_label
        binary_agreement = (canonical_label == "ZERO_HAND") == (repeat_label == "ZERO_HAND")
        qc_rows.append(
            {
                "canonical_review_id": row["canonical_review_id"],
                "repeat_review_id": row["review_id"],
                "open_images_id": row["open_images_id"],
                "source_image_sha256": row["source_image_sha256"],
                "canonical_label": canonical_label,
                "repeat_label": repeat_label,
                "exact_agreement": exact,
                "binary_zero_hand_agreement": binary_agreement,
                "critical_binary_disagreement": not binary_agreement,
            }
        )
        canonical_map = map_by_id[row["canonical_review_id"]]
        if canonical_map["source_image_sha256"] != row["source_image_sha256"]:
            raise ValueError(f"repeat bytes do not match: {row['review_id']}")

    exact_count = sum(bool(row["exact_agreement"]) for row in qc_rows)
    binary_count = sum(bool(row["binary_zero_hand_agreement"]) for row in qc_rows)
    exact_fraction = exact_count / len(qc_rows)
    binary_disagreements = len(qc_rows) - binary_count
    repeat_qc_passed = binary_disagreements == 0 and exact_fraction >= float(
        config["minimum_repeat_exact_agreement"]
    )

    dual_pass = []
    second_by_id = {row["open_images_id"]: row for row in second_pass}
    for image_id, selection in selection_by_id.items():
        second = second_by_id[image_id]
        first_label = selection["first_pass_semantic_class"]
        second_label = second["semantic_class"]
        eligible = first_label == "ZERO_HAND" and second_label == "ZERO_HAND"
        dual_pass.append(
            {
                "open_images_id": image_id,
                "first_pass_review_id": selection["first_pass_review_id"],
                "second_pass_review_id": second["second_pass_review_id"],
                "first_pass_label": first_label,
                "second_pass_label": second_label,
                "dual_confirmed_zero_hand": eligible,
                "source_image_path": second["source_image_path"],
                "source_image_sha256": second["source_image_sha256"],
                "dhash64": second["dhash64"],
                "discovery_category": second["discovery_category"],
                "scene_bucket": second["scene_bucket"],
                "author": second["author"],
                "license": second["license"],
            }
        )
    dual_confirmed = [row for row in dual_pass if row["dual_confirmed_zero_hand"]]
    diversity_rows = [source_by_id[row["open_images_id"]] for row in dual_confirmed]
    diversity = _assert_diversity(diversity_rows, seed_rows, int(config["dhash_hamming_max"]))
    diversity_clean_count = len(diversity_rows)

    # A run-level repeat-QC failure invalidates promotion even when canonical rows agree.
    selected_additions = 0
    reserve_count = 0
    final_total = len(seed_rows)
    remaining_deficit = 200 - final_total
    decision = "NEGATIVE_GOLD_V1_STILL_INCOMPLETE"
    benchmark_frozen = False
    if repeat_qc_passed and diversity_clean_count >= 124:
        raise RuntimeError(
            "passing finalization is intentionally not implemented in the QC-failure branch"
        )

    temporary.mkdir()
    _write_csv(
        temporary / "second_pass_canonical_labels.csv",
        tuple(second_pass[0]),
        second_pass,
    )
    _write_csv(temporary / "hidden_repeat_qc.csv", tuple(qc_rows[0]), qc_rows)
    _write_csv(temporary / "dual_pass_comparison.csv", tuple(dual_pass[0]), dual_pass)
    qc = {
        "repeat_pairs": len(qc_rows),
        "exact_agreements": exact_count,
        "exact_agreement_fraction": exact_fraction,
        "binary_zero_hand_agreements": binary_count,
        "binary_zero_hand_agreement_fraction": binary_count / len(qc_rows),
        "critical_binary_disagreements": binary_disagreements,
        "minimum_exact_agreement": config["minimum_repeat_exact_agreement"],
        "all_repeat_source_bytes_identical": True,
        "passed": repeat_qc_passed,
    }
    (temporary / "hidden_repeat_qc.json").write_text(json.dumps(qc, indent=2), encoding="utf-8")
    diversity_report = {
        "frozen_rule": "64-bit dHash Hamming distance <=4 is a conflict",
        "dual_confirmed_zero_hand_diagnostic": len(dual_confirmed),
        "diversity_clean_dual_confirmed_diagnostic": diversity_clean_count,
        **diversity,
        "promotion_blocked_by_repeat_qc": not repeat_qc_passed,
        "selected_benchmark_additions": selected_additions,
        "reserve_count": reserve_count,
    }
    (temporary / "final_diversity_dedup_report.json").write_text(
        json.dumps(diversity_report, indent=2), encoding="utf-8"
    )
    second_counts = Counter(row["semantic_class"] for row in second_pass)
    result = {
        "decision": decision,
        "completed_canonical_count": len(second_pass),
        "second_pass_label_counts": dict(sorted(second_counts.items())),
        "hidden_repeat_qc": qc,
        "dual_confirmed_zero_hand_diagnostic": len(dual_confirmed),
        "diversity_clean_confirmed_diagnostic": diversity_clean_count,
        "confirmed_new_zero_hand": 0,
        "selected_benchmark_additions": selected_additions,
        "reserve_count": reserve_count,
        "trusted_existing_zero_hand": len(seed_rows),
        "final_negative_gold_v1_total": final_total,
        "exact_remaining_deficit": remaining_deficit,
        "benchmark_frozen": benchmark_frozen,
        "first_pass_artifacts_modified": False,
        "perception_model_or_training_or_android_work": False,
        "stop_reason": (
            "Two concealed repeats changed between ZERO_HAND and non-ZERO_HAND; "
            "the preregistered run-level hard QC gate failed."
        ),
        "next_action": (
            "STOP. Do not auto-loop or promote canonical labels. Any repair requires a "
            "separately approved, independently blinded adjudication of only the two "
            "discordant source images."
        ),
    }
    result_path = temporary / "negative_gold_external_confirmation_result.json"
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    hash_targets = (
        "second_pass_canonical_labels.csv",
        "hidden_repeat_qc.csv",
        "hidden_repeat_qc.json",
        "dual_pass_comparison.csv",
        "final_diversity_dedup_report.json",
        "negative_gold_external_confirmation_result.json",
    )
    manifest = {
        "protocol_version": config["protocol_version"],
        "branch": _git(["branch", "--show-current"]),
        "head": _git(["rev-parse", "HEAD"]),
        "runner_sha256_at_finalization": _sha256(Path(__file__)),
        "review_queue_sha256": _sha256(output / "review_package/review_queue.csv"),
        "internal_repeat_map_sha256": _sha256(output / "review_package/internal_repeat_map.csv"),
        "source_license_manifest_sha256": _sha256(
            output / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.csv"
        ),
        "first_pass_artifact_hashes": _verify_hashes(config),
        "result_artifact_hashes": {name: _sha256(temporary / name) for name in hash_targets},
        "model_outputs_used": False,
        "human_labels_overridden": False,
    }
    (temporary / "provenance_hash_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    temporary.rename(final_dir)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "review", "check", "status", "finalize"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = load_config(args.config)
    output = _resolve(config["output_run"])
    if args.command == "prepare":
        result = prepare(args.config)
    elif args.command == "review":
        ReviewApp(output / "review_package/review_queue.csv").run()
        return 0
    elif args.command == "finalize":
        result = finalize_review(config)
    else:
        result = check_review(config)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
