"""Prepare and operate the bounded NEGATIVE_GOLD_V1 item-level audit."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import platform
import random
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2

from pipeline.tracking.n0_blinded_readjudication import _dhash
from pipeline.tracking.negative_gold_external_confirmation import _assert_diversity
from pipeline.tracking.negative_gold_open_images import (
    QUEUE_FIELDS,
    _git,
    _read_csv,
    _resolve,
    _rotate_for_display,
    _sha256,
    _write_csv,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "model/config/recognition_upgrade/negative_gold_item_level_audit.json"
PROTOCOL = ROOT / "context/recognition_upgrade/NEGATIVE_GOLD_ITEM_LEVEL_AUDIT_PROTOCOL.md"
SEMANTICS = ROOT / "context/recognition_upgrade/NEGATIVE_GOLD_ITEM_LEVEL_SEMANTIC_DEFINITION.md"
SEMANTIC_CLASSES = ("NO_HUMAN_HAND_VISIBLE", "HUMAN_HAND_VISIBLE", "UNCERTAIN")


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if tuple(config["semantic_classes"]) != SEMANTIC_CLASSES:
        raise ValueError("item-audit semantic classes drifted")
    if int(config["eligible_pool_count"]) != 158:
        raise ValueError("eligible-pool count drifted")
    if int(config["initial_audit_count"]) != 40:
        raise ValueError("initial audit count drifted")
    if int(config["dhash_hamming_max"]) != 4:
        raise ValueError("frozen dHash threshold drifted")
    return config


def _truthy(value: str) -> bool:
    return value.strip().lower() == "true"


def _verify_source_hashes(config: dict[str, Any]) -> dict[str, str]:
    run = _resolve(config["confirmation_run"])
    seed = _resolve(config["seed_manifest"])
    actual: dict[str, str] = {}
    for relative, expected in config["expected_hashes"].items():
        path = seed if relative == "NEGATIVE_GOLD_V1_SEED_MANIFEST.csv" else run / relative
        digest = _sha256(path)
        if digest != expected:
            raise ValueError(f"frozen source artifact drifted: {relative}")
        actual[relative] = digest
    return actual


def _stratum(row: dict[str, str]) -> tuple[str, str]:
    return row["discovery_category"], row["scene_bucket"]


def _allocate_quotas(groups: dict[tuple[str, str], list[dict[str, str]]], count: int) -> dict[tuple[str, str], int]:
    """Give each stratum one seat, then use proportional largest remainders."""
    keys = sorted(groups)
    if count < len(keys):
        raise ValueError("audit size cannot represent every stratum")
    quotas = {key: 1 for key in keys}
    remaining_draws = count - len(keys)
    capacities = {key: len(groups[key]) - 1 for key in keys}
    total_capacity = sum(capacities.values())
    ideals = {
        key: (remaining_draws * capacities[key] / total_capacity if total_capacity else 0.0)
        for key in keys
    }
    for key in keys:
        quotas[key] += int(ideals[key])
    leftover = count - sum(quotas.values())
    ranked = sorted(keys, key=lambda key: (-(ideals[key] - int(ideals[key])), key))
    for key in ranked[:leftover]:
        quotas[key] += 1
    if sum(quotas.values()) != count or any(quotas[key] > len(groups[key]) for key in keys):
        raise ValueError("invalid stratified quota allocation")
    return quotas


def _stratum_seed(base: int, key: tuple[str, str]) -> int:
    token = f"{base}:{key[0]}:{key[1]}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(token).digest()[:8], "big")


def _sample(pool: list[dict[str, str]], count: int, seed: int, presentation_seed: int) -> tuple[list[dict[str, str]], dict[tuple[str, str], int]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in pool:
        groups[_stratum(row)].append(row)
    quotas = _allocate_quotas(groups, count)
    selected: list[dict[str, str]] = []
    for key in sorted(groups):
        rows = sorted(groups[key], key=lambda row: row["open_images_id"])
        random.Random(_stratum_seed(seed, key)).shuffle(rows)
        selected.extend(rows[: quotas[key]])
    random.Random(presentation_seed).shuffle(selected)
    return selected, quotas


def prepare(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    output = _resolve(config["output_run"])
    temporary = output.with_name(output.name + ".preparing")
    if output.exists() or temporary.exists():
        raise FileExistsError(f"refusing to overwrite frozen package: {output}")
    if not PROTOCOL.is_file() or not SEMANTICS.is_file():
        raise FileNotFoundError("frozen protocol or semantic definition is missing")
    verified_hashes = _verify_source_hashes(config)
    confirmation = _resolve(config["confirmation_run"])
    seed_rows = _read_csv(_resolve(config["seed_manifest"]))
    dual_rows = _read_csv(confirmation / "finalization/dual_pass_comparison.csv")
    qc_rows = _read_csv(confirmation / "finalization/hidden_repeat_qc.csv")
    source_rows = _read_csv(confirmation / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.csv")
    source_by_id = {row["ImageID"]: row for row in source_rows}

    if len(dual_rows) != 160 or not all(_truthy(row["dual_confirmed_zero_hand"]) for row in dual_rows):
        raise ValueError("second-pass dual-confirmation evidence drifted")
    conflicts = [row for row in qc_rows if _truthy(row["critical_binary_disagreement"])]
    conflict_ids = {row["open_images_id"] for row in conflicts}
    if len(conflicts) != 2 or len(conflict_ids) != 2:
        raise ValueError("expected exactly two known binary-repeat conflicts")
    dual_by_id = {row["open_images_id"]: row for row in dual_rows}
    eligible = [dict(row) for row in dual_rows if row["open_images_id"] not in conflict_ids]
    if len(eligible) != int(config["eligible_pool_count"]):
        raise ValueError(f"eligible pool is {len(eligible)}, not 158")

    conflict_output = []
    for qc in conflicts:
        dual = dual_by_id[qc["open_images_id"]]
        conflict_output.append({
            "open_images_id": qc["open_images_id"],
            "canonical_review_id": qc["canonical_review_id"],
            "repeat_review_id": qc["repeat_review_id"],
            "first_pass_label": dual["first_pass_label"],
            "second_pass_label": dual["second_pass_label"],
            "repeat_label": qc["repeat_label"],
            "source_image_path": dual["source_image_path"],
            "source_image_sha256": dual["source_image_sha256"],
            "dhash64": dual["dhash64"],
            "critical_binary_disagreement": True,
            "eligibility": "PERMANENTLY_EXCLUDED",
        })

    for row in eligible:
        source = source_by_id[row["open_images_id"]]
        image_path = Path(source["source_image_path"])
        if not image_path.is_file() or _sha256(image_path) != row["source_image_sha256"]:
            raise ValueError(f"source bytes drifted: {row['open_images_id']}")
        if f"{_dhash(image_path):016x}" != row["dhash64"]:
            raise ValueError(f"source dHash drifted: {row['open_images_id']}")
        row["Rotation"] = source["Rotation"]
        row["OriginalURL"] = source["OriginalURL"]
        row["OriginalLandingURL"] = source["OriginalLandingURL"]

    diversity = _assert_diversity(
        [source_by_id[row["open_images_id"]] for row in eligible],
        seed_rows,
        int(config["dhash_hamming_max"]),
    )
    selected, quotas = _sample(
        eligible,
        int(config["initial_audit_count"]),
        int(config["random_seed"]),
        int(config["presentation_seed"]),
    )

    temporary.mkdir(parents=True)
    review_dir = temporary / "review_package"
    image_dir = review_dir / "images"
    image_dir.mkdir(parents=True)
    _write_csv(temporary / "known_conflict_exclusions.csv", tuple(conflict_output[0]), conflict_output)
    (temporary / "known_conflict_exclusions.json").write_text(json.dumps(conflict_output, indent=2), encoding="utf-8")
    _write_csv(temporary / "eligible_pool_manifest.csv", tuple(eligible[0]), eligible)

    candidate_rows = []
    mapping_rows = []
    queue_rows = []
    license_rows = []
    for number, row in enumerate(selected, start=1):
        review_id = f"item_audit_{number:04d}"
        source = source_by_id[row["open_images_id"]]
        target = image_dir / f"{review_id}.jpg"
        shutil.copy2(Path(source["source_image_path"]), target)
        relative_target = output / "review_package/images" / target.name
        candidate_rows.append({**row, "audit_review_id": review_id})
        mapping_rows.append({
            "review_id": review_id,
            "open_images_id": row["open_images_id"],
            "source_image_sha256": row["source_image_sha256"],
            "rotation": row["Rotation"],
        })
        queue_rows.append({
            "review_id": review_id,
            "image_path": str(relative_target.resolve()),
            "review_status": "unreviewed",
            "semantic_class": "",
            "notes": "",
        })
        license_rows.append(source)
        if _sha256(target) != row["source_image_sha256"]:
            raise ValueError(f"audit image copy drifted: {review_id}")
    _write_csv(temporary / "audit_candidate_manifest.csv", tuple(candidate_rows[0]), candidate_rows)
    _write_csv(review_dir / "internal_audit_map.csv", tuple(mapping_rows[0]), mapping_rows)
    _write_csv(review_dir / "audit_queue.csv", QUEUE_FIELDS, queue_rows)
    _write_csv(temporary / "OPEN_IMAGES_SOURCE_LICENSE_MANIFEST.csv", tuple(source_rows[0]), license_rows)

    quota_rows = [
        {
            "discovery_category": key[0],
            "scene_bucket": key[1],
            "eligible_count": sum(1 for row in eligible if _stratum(row) == key),
            "audit_quota": quotas[key],
        }
        for key in sorted(quotas)
    ]
    _write_csv(temporary / "stratification_manifest.csv", tuple(quota_rows[0]), quota_rows)
    category_counts = Counter(row["discovery_category"] for row in selected)
    scene_counts = Counter(row["scene_bucket"] for row in selected)
    summary = {
        "status": "ITEM_LEVEL_INITIAL_AUDIT_PACKAGE_FROZEN_UNREVIEWED",
        "historical_first_pass_status": "QC_FAIL",
        "historical_second_pass_status": "NEGATIVE_GOLD_V1_STILL_INCOMPLETE_QC_FAIL",
        "known_conflict_exclusions": len(conflicts),
        "remaining_eligible_pool": len(eligible),
        "audit_sample_size": len(selected),
        "random_seed": config["random_seed"],
        "presentation_seed": config["presentation_seed"],
        "strata_represented": len(quotas),
        "audit_discovery_category_counts": dict(sorted(category_counts.items())),
        "audit_scene_bucket_counts": dict(sorted(scene_counts.items())),
        "unique_authors": len({row["author"] for row in selected}),
        "hidden_repeats": 0,
        "human_truth_status": "UNREVIEWED_ITEM_LEVEL_AUDIT",
        "model_outputs_used": False,
        "new_downloads_performed": False,
        **diversity,
    }
    (temporary / "prepare_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    provenance = {
        "protocol_version": config["protocol_version"],
        "branch": _git(["branch", "--show-current"]),
        "head": _git(["rev-parse", "HEAD"]),
        "working_tree_status": _git(["status", "--short"]),
        "python": sys.version,
        "platform": platform.platform(),
        "random_seed": config["random_seed"],
        "presentation_seed": config["presentation_seed"],
        "sampling": "19-stratum minimum-one then proportional largest remainder",
        "model_outputs_used": False,
        "new_downloads_performed": False,
        "prior_labels_exposed_to_reviewer": False,
        "config_sha256": _sha256(config_path),
        "protocol_sha256": _sha256(PROTOCOL),
        "semantic_definition_sha256": _sha256(SEMANTICS),
        "runner_sha256": _sha256(Path(__file__)),
        "source_artifact_hashes": verified_hashes,
        "eligible_pool_manifest_sha256": _sha256(temporary / "eligible_pool_manifest.csv"),
        "conflict_exclusions_sha256": _sha256(temporary / "known_conflict_exclusions.csv"),
        "audit_candidate_manifest_sha256": _sha256(temporary / "audit_candidate_manifest.csv"),
        "audit_queue_sha256": _sha256(review_dir / "audit_queue.csv"),
        "internal_audit_map_sha256": _sha256(review_dir / "internal_audit_map.csv"),
        "stratification_manifest_sha256": _sha256(temporary / "stratification_manifest.csv"),
    }
    (temporary / "provenance_manifest.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    shutil.copy2(PROTOCOL, temporary / PROTOCOL.name)
    shutil.copy2(SEMANTICS, temporary / SEMANTICS.name)
    temporary.rename(output)
    return summary


def check_review(config: dict[str, Any]) -> dict[str, Any]:
    output = _resolve(config["output_run"])
    queue = _read_csv(output / "review_package/audit_queue.csv")
    mapping = _read_csv(output / "review_package/internal_audit_map.csv")
    errors: list[str] = []
    counts: Counter[str] = Counter()
    if len(queue) != 40 or len(mapping) != 40:
        errors.append("audit row count drifted")
    map_by_id = {row["review_id"]: row for row in mapping}
    for row in queue:
        mapped = map_by_id.get(row["review_id"])
        path = Path(row["image_path"])
        if mapped is None or not path.is_file():
            errors.append(f"missing mapping/image: {row['review_id']}")
        elif _sha256(path) != mapped["source_image_sha256"]:
            errors.append(f"audit image bytes drifted: {row['review_id']}")
        if row["review_status"] == "accepted" and row["semantic_class"] in SEMANTIC_CLASSES:
            counts[row["semantic_class"]] += 1
        elif row["review_status"] != "unreviewed":
            errors.append(f"invalid review state: {row['review_id']}")
    completed = sum(row["review_status"] == "accepted" for row in queue)
    return {
        "rows": len(queue),
        "completed": completed,
        "remaining": len(queue) - completed,
        "counts": dict(sorted(counts.items())),
        "errors": errors,
        "passed": not errors and completed == len(queue),
    }


def _distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _select_final_additions(
    eligible: list[dict[str, str]], seed_rows: list[dict[str, str]], count: int
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    """Deterministically maximize dHash spread under proportional stratum quotas."""
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in eligible:
        groups[_stratum(row)].append(row)
    quotas = _allocate_quotas(groups, count)
    seed_fingerprints = [int(row["dhash64"], 16) for row in seed_rows]
    selected: list[dict[str, str]] = []
    remaining = list(eligible)
    stratum_counts: Counter[tuple[str, str]] = Counter()
    author_counts: Counter[str] = Counter()
    selection_diagnostics: list[dict[str, Any]] = []
    while len(selected) < count:
        available = [
            row for row in remaining if stratum_counts[_stratum(row)] < quotas[_stratum(row)]
        ]
        if not available:
            raise ValueError("diversity selection exhausted before target")
        reference = seed_fingerprints + [int(row["dhash64"], 16) for row in selected]

        def rank(row: dict[str, str]) -> tuple[float, int, int, str]:
            key = _stratum(row)
            minimum_distance = min(
                _distance(int(row["dhash64"], 16), prior) for prior in reference
            )
            quota_fill = stratum_counts[key] / quotas[key]
            return (-minimum_distance, quota_fill, author_counts[row["author"]], row["open_images_id"])

        winner = min(available, key=rank)
        minimum_distance = -rank(winner)[0]
        remaining.remove(winner)
        selected.append(winner)
        stratum_counts[_stratum(winner)] += 1
        author_counts[winner["author"]] += 1
        selection_diagnostics.append(
            {
                "selection_rank": len(selected),
                "open_images_id": winner["open_images_id"],
                "discovery_category": winner["discovery_category"],
                "scene_bucket": winner["scene_bucket"],
                "author": winner["author"],
                "minimum_dhash_distance_when_selected": int(minimum_distance),
            }
        )
    selected_ids = {row["open_images_id"] for row in selected}
    reserve = sorted(
        (row for row in eligible if row["open_images_id"] not in selected_ids),
        key=lambda row: row["open_images_id"],
    )
    report = {
        "algorithm": (
            "Proportional 19-stratum quotas with minimum one per stratum; deterministic "
            "global farthest-first 64-bit dHash selection against the trusted seed and prior "
            "selections; ties prefer lower quota fill, lower author count, then Open Images ID."
        ),
        "target_additions": count,
        "stratum_quotas": {
            f"{key[0]}|{key[1]}": value for key, value in sorted(quotas.items())
        },
        "selected_category_counts": dict(
            sorted(Counter(row["discovery_category"] for row in selected).items())
        ),
        "selected_scene_counts": dict(
            sorted(Counter(row["scene_bucket"] for row in selected).items())
        ),
        "selected_unique_authors": len({row["author"] for row in selected}),
        "reserve_count": len(reserve),
        "selection_diagnostics": selection_diagnostics,
    }
    return selected, reserve, report


def finalize_review(config: dict[str, Any]) -> dict[str, Any]:
    """Apply the preregistered item-level decision and freeze the benchmark when allowed."""
    output = _resolve(config["output_run"])
    final_dir = output / "finalization"
    temporary = output / "finalization.preparing"
    if final_dir.exists() or temporary.exists():
        raise FileExistsError(f"refusing to overwrite finalization artifacts: {final_dir}")
    check = check_review(config)
    if not check["passed"]:
        raise ValueError("item-level audit is incomplete or structurally invalid")

    queue = _read_csv(output / "review_package/audit_queue.csv")
    mapping = _read_csv(output / "review_package/internal_audit_map.csv")
    candidates = _read_csv(output / "audit_candidate_manifest.csv")
    eligible = _read_csv(output / "eligible_pool_manifest.csv")
    conflicts = _read_csv(output / "known_conflict_exclusions.csv")
    seed_rows = _read_csv(_resolve(config["seed_manifest"]))
    queue_by_id = {row["review_id"]: row for row in queue}
    candidate_by_id = {row["open_images_id"]: row for row in candidates}

    audit_labels = []
    for row in mapping:
        review = queue_by_id[row["review_id"]]
        candidate = candidate_by_id[row["open_images_id"]]
        audit_labels.append(
            {
                "review_id": row["review_id"],
                "open_images_id": row["open_images_id"],
                "semantic_class": review["semantic_class"],
                "notes": review["notes"],
                "source_image_sha256": row["source_image_sha256"],
                "first_pass_label": candidate["first_pass_label"],
                "second_pass_label": candidate["second_pass_label"],
            }
        )
    counts = Counter(row["semantic_class"] for row in audit_labels)
    contamination = counts["HUMAN_HAND_VISIBLE"]
    uncertain = counts["UNCERTAIN"]
    followup_required = contamination == 1
    pool_rejected = contamination >= 2
    if followup_required or pool_rejected:
        raise RuntimeError(
            "This finalizer only freezes the zero-contamination branch; prepare the separately "
            "bounded follow-up or rejection result instead."
        )

    excluded_audit_ids = {
        row["open_images_id"]
        for row in audit_labels
        if row["semantic_class"] in {"HUMAN_HAND_VISIBLE", "UNCERTAIN"}
    }
    clean_eligible = [row for row in eligible if row["open_images_id"] not in excluded_audit_ids]
    if len(clean_eligible) < 124:
        raise ValueError("eligible pool cannot supply 124 additions")
    diversity = _assert_diversity(
        [{"ImageID": row["open_images_id"], **row} for row in clean_eligible],
        seed_rows,
        int(config["dhash_hamming_max"]),
    )
    selected, reserve, selection_report = _select_final_additions(
        clean_eligible, seed_rows, 124
    )
    selected_diversity = _assert_diversity(
        [{"ImageID": row["open_images_id"], **row} for row in selected],
        seed_rows,
        int(config["dhash_hamming_max"]),
    )

    temporary.mkdir()
    _write_csv(temporary / "audit_labels.csv", tuple(audit_labels[0]), audit_labels)
    audit_by_image = {row["open_images_id"]: row for row in audit_labels}
    common_fields = (
        "negative_gold_id",
        "benchmark_partition",
        "origin",
        "source_group",
        "source_id",
        "clip_id",
        "participant_id",
        "device_id",
        "environment_id",
        "source_split",
        "image_path",
        "image_sha256",
        "dhash64",
        "semantic_class",
        "evidence_basis",
        "item_audit_label",
        "open_images_author",
        "open_images_license",
        "open_images_original_url",
        "open_images_landing_page",
        "discovery_category",
        "scene_bucket",
    )
    final_rows = []
    for row in seed_rows:
        final_rows.append(
            {
                "negative_gold_id": row["seed_id"],
                "benchmark_partition": "NEGATIVE_GOLD_V1",
                "origin": "APPHEAR_EXISTING",
                "source_group": row["source_group"],
                "source_id": row["source_id"],
                "clip_id": row["clip_id"],
                "participant_id": row["participant_id"],
                "device_id": row["device_id"],
                "environment_id": row["environment_id"],
                "source_split": row["source_split"],
                "image_path": row["image_path"],
                "image_sha256": row["image_sha256"],
                "dhash64": row["dhash64"],
                "semantic_class": "ZERO_HAND",
                "evidence_basis": "TRUSTED_EXISTING_HUMAN_GROUNDED",
                "item_audit_label": "",
                "open_images_author": "",
                "open_images_license": "",
                "open_images_original_url": "",
                "open_images_landing_page": "",
                "discovery_category": "",
                "scene_bucket": "",
            }
        )
    for offset, row in enumerate(selected, start=77):
        audit = audit_by_image.get(row["open_images_id"])
        final_rows.append(
            {
                "negative_gold_id": f"negative_gold_{offset:03d}",
                "benchmark_partition": "NEGATIVE_GOLD_V1",
                "origin": "OPEN_IMAGES_V7",
                "source_group": "OPEN_IMAGES_V7_VALIDATION",
                "source_id": row["open_images_id"],
                "clip_id": row["open_images_id"],
                "participant_id": "unknown",
                "device_id": "unknown",
                "environment_id": row["scene_bucket"],
                "source_split": "validation",
                "image_path": row["source_image_path"],
                "image_sha256": row["source_image_sha256"],
                "dhash64": row["dhash64"],
                "semantic_class": "ZERO_HAND",
                "evidence_basis": (
                    "DUAL_CONFIRMED_AND_ITEM_AUDITED"
                    if audit is not None
                    else "DUAL_CONFIRMED_PLUS_RANDOM_POOL_AUDIT"
                ),
                "item_audit_label": audit["semantic_class"] if audit is not None else "",
                "open_images_author": row["author"],
                "open_images_license": row["license"],
                "open_images_original_url": row["OriginalURL"],
                "open_images_landing_page": row["OriginalLandingURL"],
                "discovery_category": row["discovery_category"],
                "scene_bucket": row["scene_bucket"],
            }
        )
    if len(final_rows) != 200:
        raise ValueError("final NEGATIVE_GOLD_V1 row count drifted")
    _write_csv(temporary / "NEGATIVE_GOLD_V1_MANIFEST.csv", common_fields, final_rows)
    (temporary / "NEGATIVE_GOLD_V1_MANIFEST.json").write_text(
        json.dumps(final_rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    reserve_rows = []
    for number, row in enumerate(reserve, start=1):
        audit = audit_by_image.get(row["open_images_id"])
        reserve_rows.append(
            {
                "reserve_id": f"negative_gold_reserve_{number:03d}",
                "open_images_id": row["open_images_id"],
                "source_image_path": row["source_image_path"],
                "source_image_sha256": row["source_image_sha256"],
                "dhash64": row["dhash64"],
                "evidence_basis": (
                    "DUAL_CONFIRMED_AND_ITEM_AUDITED"
                    if audit is not None
                    else "DUAL_CONFIRMED_PLUS_RANDOM_POOL_AUDIT"
                ),
                "item_audit_label": audit["semantic_class"] if audit is not None else "",
                "author": row["author"],
                "license": row["license"],
                "discovery_category": row["discovery_category"],
                "scene_bucket": row["scene_bucket"],
            }
        )
    _write_csv(temporary / "NEGATIVE_GOLD_RESERVE_MANIFEST.csv", tuple(reserve_rows[0]), reserve_rows)
    (temporary / "NEGATIVE_GOLD_RESERVE_MANIFEST.json").write_text(
        json.dumps(reserve_rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    contamination_summary = {
        "audit_sample_size": len(audit_labels),
        "label_counts": dict(sorted(counts.items())),
        "clear_actual_human_hand_contamination": contamination,
        "uncertain": uncertain,
        "tooling_or_provenance_defect": False,
        "followup_audit_required": False,
        "pool_rejected": False,
        "decision_rule": "0 clear contamination and no tooling/provenance defect -> proceed",
        "passed": True,
    }
    (temporary / "contamination_summary.json").write_text(
        json.dumps(contamination_summary, indent=2), encoding="utf-8"
    )
    selection_report.update(
        {
            "eligible_after_item_exclusions": len(clean_eligible),
            "selected_additions": len(selected),
            "reserve_count": len(reserve),
            "full_pool_diversity": diversity,
            "selected_diversity": selected_diversity,
            "frozen_near_duplicate_rule": "64-bit dHash Hamming distance <=4 is a conflict",
        }
    )
    (temporary / "diversity_selection_report.json").write_text(
        json.dumps(selection_report, indent=2), encoding="utf-8"
    )
    result = {
        "decision": "NEGATIVE_GOLD_V1_COMPLETE",
        "historical_first_pass_status": "QC_FAIL",
        "historical_second_pass_status": "NEGATIVE_GOLD_V1_STILL_INCOMPLETE_QC_FAIL",
        "known_conflict_exclusions": len(conflicts),
        "remaining_eligible_pool_before_audit": len(eligible),
        "audit_sample_size": len(audit_labels),
        "audit_label_counts": dict(sorted(counts.items())),
        "contamination_count": contamination,
        "followup_audit_required": False,
        "diversity_clean_eligible_count": len(clean_eligible),
        "selected_additions_count": len(selected),
        "reserve_count": len(reserve),
        "trusted_existing_count": len(seed_rows),
        "final_benchmark_total": len(final_rows),
        "exact_remaining_deficit": 0,
        "benchmark_construction_closed": True,
        "prior_results_rewritten": False,
        "perception_model_or_training_or_android_work": False,
        "next_action": (
            "STOP. NEGATIVE_GOLD_V1 is complete and frozen. Do not start the next perception "
            "phase automatically."
        ),
    }
    (temporary / "negative_gold_item_level_audit_result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    hash_targets = (
        "audit_labels.csv",
        "contamination_summary.json",
        "diversity_selection_report.json",
        "NEGATIVE_GOLD_V1_MANIFEST.csv",
        "NEGATIVE_GOLD_V1_MANIFEST.json",
        "NEGATIVE_GOLD_RESERVE_MANIFEST.csv",
        "NEGATIVE_GOLD_RESERVE_MANIFEST.json",
        "negative_gold_item_level_audit_result.json",
    )
    provenance = {
        "protocol_version": config["protocol_version"],
        "branch": _git(["branch", "--show-current"]),
        "head": _git(["rev-parse", "HEAD"]),
        "runner_sha256_at_finalization": _sha256(Path(__file__)),
        "config_sha256": _sha256(DEFAULT_CONFIG),
        "protocol_sha256": _sha256(PROTOCOL),
        "semantic_definition_sha256": _sha256(SEMANTICS),
        "prepared_provenance_manifest_sha256": _sha256(output / "provenance_manifest.json"),
        "audit_queue_sha256": _sha256(output / "review_package/audit_queue.csv"),
        "internal_audit_map_sha256": _sha256(output / "review_package/internal_audit_map.csv"),
        "known_conflict_exclusions_sha256": _sha256(output / "known_conflict_exclusions.csv"),
        "eligible_pool_manifest_sha256": _sha256(output / "eligible_pool_manifest.csv"),
        "source_artifact_hashes": _verify_source_hashes(config),
        "result_artifact_hashes": {
            name: _sha256(temporary / name) for name in hash_targets
        },
        "human_labels_overridden": False,
        "model_outputs_used": False,
        "new_downloads_performed": False,
        "perception_model_or_training_or_android_work": False,
    }
    (temporary / "final_provenance_hash_manifest.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )
    temporary.rename(final_dir)
    return result


class AuditReviewApp:
    def __init__(self, queue_path: Path) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.queue_path = queue_path
        self.rows = _read_csv(queue_path)
        self.mapping = {row["review_id"]: row for row in _read_csv(queue_path.parent / "internal_audit_map.csv")}
        self.index = next((i for i, row in enumerate(self.rows) if row["review_status"] != "accepted"), 0)
        self.zoom = 1.0
        self.root = tk.Tk()
        self.root.title("AppHear Item-Level Human-Hand Audit")
        self.root.geometry("1400x920")
        self.root.configure(bg="#f4f5f7")
        self.status = tk.StringVar()
        self.notes = tk.StringVar()
        tk.Label(self.root, textvariable=self.status, font=("Segoe UI", 15, "bold"), bg="#f4f5f7").pack(pady=(10, 4))
        tk.Label(self.root, text="Is an actual human hand visible anywhere in this image?", font=("Segoe UI", 17, "bold"), fg="#0f172a", bg="#f4f5f7").pack(pady=4)
        tk.Label(
            self.root,
            text="Count only real human hands. Ignore statue, toy, drawing, mannequin, sculpted, cartoon, figurine, artificial, or photo-inside-scene hands.",
            font=("Segoe UI", 11, "bold"), fg="#9a3412", bg="#f4f5f7", wraplength=1320,
        ).pack(pady=(0, 8))
        viewer = tk.Frame(self.root, bg="#111827")
        viewer.pack(fill="both", expand=True, padx=12)
        self.canvas = tk.Canvas(viewer, bg="#111827", highlightthickness=0)
        xscroll = ttk.Scrollbar(viewer, orient="horizontal", command=self.canvas.xview)
        yscroll = ttk.Scrollbar(viewer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        viewer.grid_rowconfigure(0, weight=1)
        viewer.grid_columnconfigure(0, weight=1)
        zoom = tk.Frame(self.root, bg="#f4f5f7")
        zoom.pack(pady=5)
        tk.Button(zoom, text="Zoom −", command=lambda: self.change_zoom(0.8), width=10).pack(side="left", padx=3)
        tk.Button(zoom, text="Fit", command=self.reset_zoom, width=10).pack(side="left", padx=3)
        tk.Button(zoom, text="Zoom +", command=lambda: self.change_zoom(1.25), width=10).pack(side="left", padx=3)
        actions = tk.Frame(self.root, bg="#f4f5f7")
        actions.pack(pady=7)
        specs = (
            ("1 — NO HUMAN HAND", "NO_HUMAN_HAND_VISIBLE", "#15803d"),
            ("2 — HUMAN HAND VISIBLE", "HUMAN_HAND_VISIBLE", "#b91c1c"),
            ("3 — UNCERTAIN", "UNCERTAIN", "#a16207"),
        )
        for label, value, color in specs:
            tk.Button(actions, text=label, command=lambda item=value: self.accept(item), font=("Segoe UI", 12, "bold"), bg=color, fg="white", width=25, pady=8).pack(side="left", padx=7)
        notes = tk.Frame(self.root, bg="#f4f5f7")
        notes.pack(fill="x", padx=12)
        tk.Label(notes, text="Optional note:", bg="#f4f5f7").pack(side="left")
        tk.Entry(notes, textvariable=self.notes).pack(side="left", fill="x", expand=True, padx=8)
        nav = tk.Frame(self.root, bg="#f4f5f7")
        nav.pack(pady=(7, 12))
        tk.Button(nav, text="Previous", command=lambda: self.move(-1), width=14).pack(side="left", padx=6)
        tk.Button(nav, text="Next", command=lambda: self.move(1), width=14).pack(side="left", padx=6)
        for key, value in zip(("1", "2", "3"), SEMANTIC_CLASSES, strict=True):
            self.root.bind(key, lambda _event, item=value: self.accept(item))
        self.root.bind("<Left>", lambda _event: self.move(-1))
        self.root.bind("<Right>", lambda _event: self.move(1))
        self.root.bind("<Control-MouseWheel>", self.mouse_zoom)
        self.refresh()

    def _render(self) -> None:
        row = self.rows[self.index]
        image = cv2.imread(row["image_path"])
        if image is None:
            raise OSError(row["image_path"])
        image = _rotate_for_display(image, self.mapping[row["review_id"]]["rotation"])
        width, height = max(self.canvas.winfo_width(), 900), max(self.canvas.winfo_height(), 560)
        scale = min(width / image.shape[1], height / image.shape[0], 2.0) * self.zoom
        resized = cv2.resize(image, (max(1, round(image.shape[1] * scale)), max(1, round(image.shape[0] * scale))), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
        ok, encoded = cv2.imencode(".png", resized)
        if not ok:
            raise OSError(row["image_path"])
        self.photo = self.tk.PhotoImage(data=base64.b64encode(encoded.tobytes()).decode("ascii"))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.canvas.configure(scrollregion=(0, 0, resized.shape[1], resized.shape[0]))

    def refresh(self) -> None:
        row = self.rows[self.index]
        complete = sum(item["review_status"] == "accepted" for item in self.rows)
        self.status.set(f"Image {self.index + 1}/{len(self.rows)} | accepted {complete} | status={row['review_status']}")
        self.notes.set(row["notes"])
        self.root.after_idle(self._render)

    def accept(self, semantic_class: str) -> None:
        if semantic_class not in SEMANTIC_CLASSES:
            raise ValueError(semantic_class)
        row = self.rows[self.index]
        row["semantic_class"] = semantic_class
        row["notes"] = self.notes.get().strip()
        row["review_status"] = "accepted"
        _write_csv(self.queue_path, QUEUE_FIELDS, self.rows)
        self.index = min(self.index + 1, len(self.rows) - 1)
        self.zoom = 1.0
        self.refresh()

    def move(self, delta: int) -> None:
        self.index = min(max(self.index + delta, 0), len(self.rows) - 1)
        self.zoom = 1.0
        self.refresh()

    def change_zoom(self, factor: float) -> None:
        self.zoom = min(max(self.zoom * factor, 0.5), 6.0)
        self._render()

    def reset_zoom(self) -> None:
        self.zoom = 1.0
        self._render()

    def mouse_zoom(self, event: Any) -> None:
        self.change_zoom(1.25 if event.delta > 0 else 0.8)

    def run(self) -> None:
        self.root.mainloop()


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
        AuditReviewApp(output / "review_package/audit_queue.csv").run()
        return 0
    elif args.command == "finalize":
        result = finalize_review(config)
    else:
        result = check_review(config)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
