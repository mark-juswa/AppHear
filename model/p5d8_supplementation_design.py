"""P5-D8 deterministic Sem-Lex supplementation design audit.

This module reads frozen AppHear and P5-D7B artifacts and writes manifest
simulations only.  It never loads a model, performs inference/training, copies
tensors, or mutates a canonical dataset.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/recognition_upgrade/p5_representation_v2"
D7A = BASE / "p5d7a_semlex_extraction_prep_01"
D7B = BASE / "p5d7b_semlex_integrity_audit_01"
D2 = BASE / "p5d2_temporal_objective_ablation_01"
D3 = BASE / "p5d3_data_coverage_curve_01"
P5B = BASE / "p5b_migration_01/dataset"
OUT = BASE / "p5d8_supplementation_design_01"
CANONICAL = ROOT / "artifacts/recognition_upgrade/phase1_full_vocab/manifest_01/canonical_manifest.csv"
PROGRESS = ROOT / "context/progress-tracker.md"
DECISION_SHEET = Path(r"C:\Users\Gigabyte\Downloads\semlex_human_decision_sheet_completed.csv")

EXPECTED = {
    "train": 3926,
    "classes": 236,
    "semlex_clips": 2415,
    "semlex_classes": 65,
    "semlex_signers": 32,
    "semlex_slots": 893,
    "decision_sheet_sha256": "36eaff387b8d7ce91831fbb419461142d4d82edcbf37a67b779fb3af2e03fdb7",
    "v2_train_sha256": "a2261ea8d61e5eed1a526da0493da5b36c1bb54432ccef7f7479d6ca94634f11",
    "vocab_sha256": "a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b",
    "canonical_sha256": "8c1fab3df04a0240b5a178853b2206408806958afebdd19bd3d44d6fca606571",
    "progress_sha256": "12cf08f81959a413a60aa1f869615a24485a41ee3d796e61fce7489ae5c480cf",
}

POLICIES = {
    "P0_ALL_USABLE_SEMLEX": "all usable post-audit Sem-Lex clips",
    "P1_ONE_CLIP_PER_EXTERNAL_SIGNER_CLASS": "one deterministic clip per AppHear class and namespaced Sem-Lex signer",
    "P2_ONE_PER_SIGNER_CLASS_CLASS_SHARE_50": "P1 capped at current AppHear clip count per class",
    "P3_ONE_PER_SIGNER_CLASS_CLASS_SHARE_67": "P1 capped at twice current AppHear clip count per class",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stable_hash(row: dict[str, str]) -> str:
    value = (
        f"P5D8_POLICY_V1|{int(row['apphear_class_id'])}|"
        f"SEMLEX::{row['semlex_signer_id']}|{row['semlex_sample_id']}"
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def verify_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    failures: list[str] = []
    for item in data.get("artifacts", []):
        candidate = ROOT / item["path"] if not Path(item["path"]).is_absolute() else Path(item["path"])
        if not candidate.is_file():
            candidate = path.parent / item["path"]
        if not candidate.is_file():
            failures.append(f"missing:{item['path']}")
        elif sha256(candidate) != item["sha256"]:
            failures.append(f"hash:{item['path']}")
    return {"path": str(path.resolve()), "passed": not failures, "failures": failures, "sha256": sha256(path)}


def hhi_effective(counts: Iterable[int]) -> tuple[float, float]:
    counts = list(counts)
    total = sum(counts)
    if not total:
        return 0.0, 0.0
    hhi = sum((count / total) ** 2 for count in counts)
    return hhi, 1.0 / hhi


def weighted_rate(rows: list[dict[str, Any]], key: str) -> float:
    denom = sum(int(row["real_length"]) for row in rows)
    return sum(float(row[key]) * int(row["real_length"]) for row in rows) / denom if denom else 0.0


def load_vocab(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [str(value) for value in data]
    for key in ("vocabulary", "classes", "glosses"):
        if key in data and isinstance(data[key], list):
            return [str(value) for value in data[key]]
    if all(str(key).isdigit() for key in data):
        return [str(data[str(index)]) for index in range(len(data))]
    if all(isinstance(value, int) for value in data.values()):
        ordered = [""] * len(data)
        for gloss, class_id in data.items():
            ordered[int(class_id)] = str(gloss)
        if all(ordered):
            return ordered
    raise RuntimeError("P5D8_VOCAB_FORMAT_UNRECOGNIZED")


def exact_decision(value: str) -> bool:
    return value in {"ACCEPT_EXACT_FORM", "ACCEPT_METADATA_EXACT"}


def policy_select(
    source: list[dict[str, str]], current_counts: dict[int, int]
) -> dict[str, list[dict[str, str]]]:
    ordered = sorted(
        source,
        key=lambda row: (
            int(row["apphear_class_id"]),
            f"SEMLEX::{row['semlex_signer_id']}",
            stable_hash(row),
            row["semlex_sample_id"],
        ),
    )
    p1: list[dict[str, str]] = []
    seen: set[tuple[int, str]] = set()
    for row in ordered:
        key = (int(row["apphear_class_id"]), row["semlex_signer_id"])
        if key not in seen:
            seen.add(key)
            p1.append(row)

    by_class: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in p1:
        by_class[int(row["apphear_class_id"])].append(row)

    def capped(multiplier: int) -> list[dict[str, str]]:
        selected: list[dict[str, str]] = []
        for class_id in sorted(by_class):
            rows = sorted(by_class[class_id], key=lambda row: (stable_hash(row), row["semlex_sample_id"]))
            selected.extend(rows[: min(len(rows), multiplier * current_counts[class_id])])
        return selected

    return {
        "P0_ALL_USABLE_SEMLEX": ordered,
        "P1_ONE_CLIP_PER_EXTERNAL_SIGNER_CLASS": p1,
        "P2_ONE_PER_SIGNER_CLASS_CLASS_SHARE_50": capped(1),
        "P3_ONE_PER_SIGNER_CLASS_CLASS_SHARE_67": capped(2),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    protected_names = {"test.npz", "protected_replay.npz", "primary_test"}
    source_paths = {
        "progress_tracker": PROGRESS,
        "v2_train": P5B / "train.npz",
        "vocab": P5B / "vocab.json",
        "canonical_manifest": CANONICAL,
        "d7b_candidate_manifest": D7B / "semlex_post_audit_candidate_manifest.csv",
        "d7b_usability": D7B / "semlex_training_usability_states.csv",
        "d7b_integrity_rows": D7B / "p5d7b_completed_v2_integrity.csv",
        "d7b_class_retention": D7B / "semlex_class_retention.csv",
        "d7b_missingness_comparison": D7B / "apphear_semlex_missingness_comparison.csv",
        "decision_sheet": DECISION_SHEET,
        "d2_initialization": D2 / "p5d2_initialization_parity.csv",
        "d2_contract": D2 / "p5d2_objective_contract.json",
        "d3_contract": D3 / "p5d3_subset_contract.json",
        "d3_budget": D3 / "p5d3_training_budget_audit.csv",
    }
    if any(name.lower() in str(path).lower() for path in source_paths.values() for name in protected_names):
        raise RuntimeError("P5D8_PROTECTED_PATH_GUARD")
    if not all(path.is_file() for path in source_paths.values()):
        missing = [str(path) for path in source_paths.values() if not path.is_file()]
        raise RuntimeError(f"P5D8_MISSING_INPUTS:{missing}")
    hashes_before = {name: sha256(path) for name, path in source_paths.items()}
    if hashes_before["v2_train"] != EXPECTED["v2_train_sha256"]:
        raise RuntimeError("P5D8_V2_TRAIN_HASH_MISMATCH")
    if hashes_before["vocab"] != EXPECTED["vocab_sha256"]:
        raise RuntimeError("P5D8_VOCAB_HASH_MISMATCH")
    if hashes_before["canonical_manifest"] != EXPECTED["canonical_sha256"]:
        raise RuntimeError("P5D8_CANONICAL_HASH_MISMATCH")
    if hashes_before["decision_sheet"] != EXPECTED["decision_sheet_sha256"]:
        raise RuntimeError("P5D8_DECISION_SHEET_HASH_MISMATCH")
    if hashes_before["progress_tracker"] != EXPECTED["progress_sha256"]:
        raise RuntimeError("P5D8_PROGRESS_HASH_MISMATCH")

    upstream_manifests = {
        "p5d7b": verify_manifest(D7B / "artifact_hash_manifest.json"),
        "p5d2": verify_manifest(D2 / "artifact_hash_manifest.json"),
        "p5d3": verify_manifest(D3 / "artifact_hash_manifest.json"),
    }
    if not all(value["passed"] for value in upstream_manifests.values()):
        raise RuntimeError(f"P5D8_UPSTREAM_MANIFEST_FAILURE:{upstream_manifests}")

    train = np.load(P5B / "train.npz", allow_pickle=False)
    vocab = load_vocab(P5B / "vocab.json")
    if train["X"].shape != (EXPECTED["train"], 96, 238):
        raise RuntimeError("P5D8_TRAIN_SHAPE_MISMATCH")
    if len(set(map(int, train["y"]))) != EXPECTED["classes"] or len(vocab) != EXPECTED["classes"]:
        raise RuntimeError("P5D8_VOCABULARY_MISMATCH")

    canonical = {row["sample_id"]: row for row in read_csv(CANONICAL)}
    sample_ids = [str(value) for value in train["sample_ids"]]
    if len(set(sample_ids)) != EXPECTED["train"] or any(sample not in canonical for sample in sample_ids):
        raise RuntimeError("P5D8_TRAIN_LINEAGE_MISMATCH")
    if any(canonical[sample]["role"] not in {"primary_train", "supplement_train"} for sample in sample_ids):
        raise RuntimeError("P5D8_NONTRAIN_ROLE_PRESENT")

    current_by_class: dict[int, dict[str, Any]] = {}
    for class_id in range(EXPECTED["classes"]):
        indices = np.where(train["y"] == class_id)[0]
        signer_counts = Counter(str(train["signer_group_ids"][idx]) for idx in indices)
        source_counts = Counter(canonical[sample_ids[idx]]["source_dataset"] for idx in indices)
        hhi, effective = hhi_effective(signer_counts.values())
        current_by_class[class_id] = {
            "class_id": class_id,
            "gloss": vocab[class_id],
            "clips": len(indices),
            "signer_counts": signer_counts,
            "unique_signers": len(signer_counts),
            "effective_signers": effective,
            "signer_hhi": hhi,
            "max_signer_share": max(signer_counts.values()) / len(indices),
            "clips_per_signer": "|".join(f"{key}:{value}" for key, value in sorted(signer_counts.items())),
            "source_composition": "|".join(f"{key}:{value}" for key, value in sorted(source_counts.items())),
        }

    candidates = read_csv(D7B / "semlex_post_audit_candidate_manifest.csv")
    if len(candidates) != EXPECTED["semlex_clips"] or any(row["training_usability_state"] != "USABLE_CANDIDATE" for row in candidates):
        raise RuntimeError("P5D8_SEMLEX_POOL_MISMATCH")
    if {row["apphear_gloss"] for row in candidates} & {"IF", "OLD", "GET", "TURN", "ANY"}:
        raise RuntimeError("P5D8_UNRESOLVED_CLASS_PRESENT")
    if len({int(row["apphear_class_id"]) for row in candidates}) != EXPECTED["semlex_classes"]:
        raise RuntimeError("P5D8_SEMLEX_CLASS_COUNT_MISMATCH")
    if len({row["semlex_signer_id"] for row in candidates}) != EXPECTED["semlex_signers"]:
        raise RuntimeError("P5D8_SEMLEX_SIGNER_COUNT_MISMATCH")
    slots = {(int(row["apphear_class_id"]), row["semlex_signer_id"]) for row in candidates}
    if len(slots) != EXPECTED["semlex_slots"]:
        raise RuntimeError("P5D8_SEMLEX_SLOT_COUNT_MISMATCH")

    usability = {row["semlex_sample_id"]: row for row in read_csv(D7B / "semlex_training_usability_states.csv")}
    completed = {row["semlex_sample_id"]: row for row in read_csv(D7B / "p5d7b_completed_v2_integrity.csv")}
    retention = {int(row["apphear_class_id"]): row for row in read_csv(D7B / "semlex_class_retention.csv")}
    comparison_rows = read_csv(D7B / "apphear_semlex_missingness_comparison.csv")
    apphear_missing = {int(row["class_id"]): row for row in comparison_rows if row["scope"] == "CLASS"}
    overall_apphear = next(row for row in comparison_rows if row["scope"] == "OVERALL_MATCHED_65_CLASSES")
    enriched: list[dict[str, Any]] = []
    for row in candidates:
        sample = row["semlex_sample_id"]
        if sample not in usability or sample not in completed:
            raise RuntimeError(f"P5D8_SEMLEX_LINEAGE_MISSING:{sample}")
        item = dict(row)
        item.update(usability[sample])
        item["native_path"] = completed[sample]["native_path"]
        item["v2_path"] = completed[sample]["v2_path"]
        item["valid_hand_landmark_rate"] = completed[sample]["valid_hand_landmark_rate"]
        item["body_valid_rate"] = completed[sample]["body_valid_rate"]
        item["namespaced_semlex_signer_id"] = f"SEMLEX::{row['semlex_signer_id']}"
        item["stable_sample_hash"] = stable_hash(row)
        enriched.append(item)

    current_counts = {class_id: current_by_class[class_id]["clips"] for class_id in current_by_class}
    selected = policy_select(enriched, current_counts)
    if len(selected["P1_ONE_CLIP_PER_EXTERNAL_SIGNER_CLASS"]) != EXPECTED["semlex_slots"]:
        raise RuntimeError("P5D8_P1_DID_NOT_RETAIN_ALL_SLOTS")

    # Per-class baseline.
    baseline_rows: list[dict[str, Any]] = []
    candidate_by_class: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in enriched:
        candidate_by_class[int(row["apphear_class_id"])].append(row)
    for class_id in sorted(candidate_by_class):
        rows = candidate_by_class[class_id]
        signer_counts = Counter(row["namespaced_semlex_signer_id"] for row in rows)
        ext_hhi, ext_eff = hhi_effective(signer_counts.values())
        miss = apphear_missing[class_id]
        decision = rows[0]["human_decision"]
        baseline_rows.append({
            "class_id": class_id,
            "gloss": current_by_class[class_id]["gloss"],
            "coverage_deficit_level": retention[class_id]["coverage_deficit_level"],
            "current_apphear_clips": current_by_class[class_id]["clips"],
            "current_apphear_unique_signers": current_by_class[class_id]["unique_signers"],
            "current_apphear_effective_signers": current_by_class[class_id]["effective_signers"],
            "current_apphear_clips_per_signer": current_by_class[class_id]["clips_per_signer"],
            "current_apphear_max_signer_concentration": current_by_class[class_id]["max_signer_share"],
            "current_apphear_source_composition": current_by_class[class_id]["source_composition"],
            "current_apphear_median_real_length": miss["apphear_median_sequence_length"],
            "current_apphear_either_hand_observation": miss["apphear_at_least_one_observed_rate"],
            "current_apphear_both_hand_observation": miss["apphear_both_observed_rate"],
            "semlex_usable_clips": len(rows),
            "semlex_source_distinct_signers": len(signer_counts),
            "semlex_effective_signers": ext_eff,
            "semlex_clips_per_signer": "|".join(f"{key}:{value}" for key, value in sorted(signer_counts.items())),
            "semlex_max_signer_concentration": max(signer_counts.values()) / len(rows),
            "semlex_signer_class_slots": len(signer_counts),
            "accept_exact_form": exact_decision(decision),
            "accept_compatible_variant": decision == "ACCEPT_COMPATIBLE_VARIANT",
            "human_decision": decision,
            "semlex_lh_observed_rate": weighted_rate(rows, "lh_observed_rate"),
            "semlex_rh_observed_rate": weighted_rate(rows, "rh_observed_rate"),
            "semlex_both_observed_rate": weighted_rate(rows, "both_observed_rate"),
            "semlex_either_observed_rate": weighted_rate(rows, "at_least_one_observed_rate"),
            "semlex_median_real_length": median(int(row["real_length"]) for row in rows),
        })
    write_csv(OUT / "p5d8_classwise_source_baseline.csv", baseline_rows, list(baseline_rows[0]))

    # Policy simulations and class summaries.
    policy_summary: list[dict[str, Any]] = []
    policy_class_rows: list[dict[str, Any]] = []
    class_stats_by_policy: dict[str, dict[int, dict[str, Any]]] = {}
    policy_file_names = {
        "P0_ALL_USABLE_SEMLEX": "p5d8_policy_p0_all_semlex.csv",
        "P1_ONE_CLIP_PER_EXTERNAL_SIGNER_CLASS": "p5d8_policy_p1_one_per_signer_class.csv",
        "P2_ONE_PER_SIGNER_CLASS_CLASS_SHARE_50": "p5d8_policy_p2_source50.csv",
        "P3_ONE_PER_SIGNER_CLASS_CLASS_SHARE_67": "p5d8_policy_p3_source67.csv",
    }
    policy_manifest_fields = [
        "policy", "apphear_class_id", "apphear_gloss", "coverage_deficit_level", "human_decision",
        "semlex_lexical_id", "semlex_sample_id", "namespaced_semlex_signer_id", "semlex_split",
        "raw_sha256", "native_path", "v2_path", "training_usability_state", "stable_sample_hash",
        "deterministic_selection_rule", "current_apphear_clips", "selected_semlex_clips_for_class",
        "hypothetical_combined_class_clips", "class_external_share",
    ]
    for policy, rows in selected.items():
        by_class: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_class[int(row["apphear_class_id"])].append(row)
        class_stats: dict[int, dict[str, Any]] = {}
        output_rows: list[dict[str, Any]] = []
        for class_id in sorted(by_class):
            class_rows = by_class[class_id]
            external_signer_counts = Counter(row["namespaced_semlex_signer_id"] for row in class_rows)
            external_signers = set(external_signer_counts)
            current = current_by_class[class_id]
            combined_counts = list(current["signer_counts"].values()) + list(external_signer_counts.values())
            _, combined_effective = hhi_effective(combined_counts)
            external_share = len(class_rows) / (current["clips"] + len(class_rows))
            decision = class_rows[0]["human_decision"]
            stat = {
                "policy": policy,
                "class_id": class_id,
                "gloss": current["gloss"],
                "coverage_deficit_level": retention[class_id]["coverage_deficit_level"],
                "current_apphear_clips": current["clips"],
                "current_apphear_signers": current["unique_signers"],
                "selected_semlex_clips": len(class_rows),
                "selected_semlex_signers": len(external_signers),
                "signer_slots_retained": len(external_signers),
                "hypothetical_combined_clips": current["clips"] + len(class_rows),
                "external_clip_share": external_share,
                "new_signer_gain": len(external_signers),
                "effective_signer_gain": combined_effective - current["effective_signers"],
                "human_decision": decision,
                "exact_form_selected_clips": len(class_rows) if exact_decision(decision) else 0,
                "compatible_variant_selected_clips": len(class_rows) if decision == "ACCEPT_COMPATIBLE_VARIANT" else 0,
                "lh_observed_rate": weighted_rate(class_rows, "lh_observed_rate"),
                "rh_observed_rate": weighted_rate(class_rows, "rh_observed_rate"),
                "both_hands_observed_rate": weighted_rate(class_rows, "both_observed_rate"),
                "either_hand_observed_rate": weighted_rate(class_rows, "at_least_one_observed_rate"),
                "neither_hand_observed_rate": 1.0 - weighted_rate(class_rows, "at_least_one_observed_rate"),
                "valid_hand_landmark_rate": weighted_rate(class_rows, "valid_hand_landmark_rate"),
                "body_valid_rate": weighted_rate(class_rows, "body_valid_rate"),
                "median_real_sequence_length": median(int(row["real_length"]) for row in class_rows),
            }
            class_stats[class_id] = stat
            policy_class_rows.append(stat)
            for row in class_rows:
                output_rows.append({
                    "policy": policy,
                    "apphear_class_id": class_id,
                    "apphear_gloss": current["gloss"],
                    "coverage_deficit_level": retention[class_id]["coverage_deficit_level"],
                    "human_decision": row["human_decision"],
                    "semlex_lexical_id": row["semlex_lexical_id"],
                    "semlex_sample_id": row["semlex_sample_id"],
                    "namespaced_semlex_signer_id": row["namespaced_semlex_signer_id"],
                    "semlex_split": row["semlex_split"],
                    "raw_sha256": row["raw_sha256"],
                    "native_path": row["native_path"],
                    "v2_path": row["v2_path"],
                    "training_usability_state": row["training_usability_state"],
                    "stable_sample_hash": row["stable_sample_hash"],
                    "deterministic_selection_rule": POLICIES[policy],
                    "current_apphear_clips": current["clips"],
                    "selected_semlex_clips_for_class": len(class_rows),
                    "hypothetical_combined_class_clips": current["clips"] + len(class_rows),
                    "class_external_share": external_share,
                })
        class_stats_by_policy[policy] = class_stats
        write_csv(OUT / policy_file_names[policy], output_rows, policy_manifest_fields)
        shares = [value["external_clip_share"] for value in class_stats.values()]
        all_slots = {(int(row["apphear_class_id"]), row["namespaced_semlex_signer_id"]) for row in rows}
        exact_rows = [row for row in rows if exact_decision(row["human_decision"])]
        variant_rows = [row for row in rows if row["human_decision"] == "ACCEPT_COMPATIBLE_VARIANT"]
        policy_summary.append({
            "policy": policy,
            "external_clips": len(rows),
            "hypothetical_combined_train_clips": EXPECTED["train"] + len(rows),
            "global_external_share": len(rows) / (EXPECTED["train"] + len(rows)),
            "retained_external_signers": len({row["namespaced_semlex_signer_id"] for row in rows}),
            "retained_signer_class_slots": len(all_slots),
            "slot_retention_percent": len(all_slots) / EXPECTED["semlex_slots"],
            "supplemented_classes": len(class_stats),
            "critical_classes_supplemented": sum(value["coverage_deficit_level"] == "CRITICAL_COVERAGE_DEFICIT" for value in class_stats.values()),
            "high_classes_supplemented": sum(value["coverage_deficit_level"] == "HIGH_COVERAGE_DEFICIT" for value in class_stats.values()),
            "median_external_signers_per_class": median(value["selected_semlex_signers"] for value in class_stats.values()),
            "median_effective_signer_gain": median(value["effective_signer_gain"] for value in class_stats.values()),
            "median_class_external_share": median(shares),
            "maximum_class_external_share": max(shares),
            "classes_above_50pct_external": sum(value > 0.5 for value in shares),
            "classes_above_67pct_external": sum(value > 2 / 3 for value in shares),
            "exact_form_clip_count": len(exact_rows),
            "exact_form_signer_slots": len({(row["apphear_class_id"], row["namespaced_semlex_signer_id"]) for row in exact_rows}),
            "compatible_variant_clip_count": len(variant_rows),
            "compatible_variant_signer_slots": len({(row["apphear_class_id"], row["namespaced_semlex_signer_id"]) for row in variant_rows}),
            "either_hand_observation": weighted_rate(rows, "at_least_one_observed_rate"),
            "both_hand_observation": weighted_rate(rows, "both_observed_rate"),
            "neither_hand_observation": 1.0 - weighted_rate(rows, "at_least_one_observed_rate"),
            "median_real_sequence_length": median(int(row["real_length"]) for row in rows),
        })
    p1_slots_by_class = {
        class_id: value["signer_slots_retained"]
        for class_id, value in class_stats_by_policy["P1_ONE_CLIP_PER_EXTERNAL_SIGNER_CLASS"].items()
    }
    for summary in policy_summary:
        stats = class_stats_by_policy[summary["policy"]]
        summary["signer_slots_sacrificed_vs_p1"] = EXPECTED["semlex_slots"] - summary["retained_signer_class_slots"]
        summary["external_signers_sacrificed_vs_p1"] = EXPECTED["semlex_signers"] - summary["retained_external_signers"]
        summary["classes_losing_signer_coverage_vs_p1"] = sum(
            stats[class_id]["signer_slots_retained"] < p1_slots_by_class[class_id]
            for class_id in p1_slots_by_class
        )
    write_csv(OUT / "p5d8_policy_comparison.csv", policy_summary, list(policy_summary[0]))
    write_csv(OUT / "p5d8_policy_by_class.csv", policy_class_rows, list(policy_class_rows[0]))

    summaries = {row["policy"]: row for row in policy_summary}
    p1_stats = class_stats_by_policy["P1_ONE_CLIP_PER_EXTERNAL_SIGNER_CLASS"]
    p2_stats = class_stats_by_policy["P2_ONE_PER_SIGNER_CLASS_CLASS_SHARE_50"]
    p3_stats = class_stats_by_policy["P3_ONE_PER_SIGNER_CLASS_CLASS_SHARE_67"]
    gain_cutoff = float(np.percentile([value["new_signer_gain"] for value in p1_stats.values()], 75))
    design_flags: list[dict[str, Any]] = []
    for class_id in sorted(p1_stats):
        p1, p2, p3 = p1_stats[class_id], p2_stats[class_id], p3_stats[class_id]
        app = apphear_missing[class_id]
        flags: list[str] = []
        if p1["external_clip_share"] > 2 / 3:
            flags.append("P1_HIGH_EXTERNAL_SOURCE_SHARE_GT_67PCT")
        if (p1["signer_slots_retained"] - p2["signer_slots_retained"]) / p1["signer_slots_retained"] >= 0.25:
            flags.append("P2_SUBSTANTIAL_SIGNER_COVERAGE_SACRIFICE_GE_25PCT")
        if (p1["signer_slots_retained"] - p3["signer_slots_retained"]) / p1["signer_slots_retained"] >= 0.25:
            flags.append("P3_SUBSTANTIAL_SIGNER_COVERAGE_SACRIFICE_GE_25PCT")
        if p1["selected_semlex_signers"] <= 5:
            flags.append("SEMLEX_EXTERNAL_SIGNERS_LE_5")
        if p1["new_signer_gain"] >= gain_cutoff:
            flags.append("SEMLEX_SIGNER_GAIN_TOP_QUARTILE")
        if p1["human_decision"] == "ACCEPT_COMPATIBLE_VARIANT":
            flags.append("COMPATIBLE_VARIANT_EXTERNAL_MATERIAL")
        miss_delta = abs(p1["either_hand_observed_rate"] - float(app["apphear_at_least_one_observed_rate"]))
        if miss_delta >= 0.25:
            flags.append("EITHER_HAND_OBSERVATION_SHIFT_GE_25PP")
        if p1["new_signer_gain"] <= 2 or p1["effective_signer_gain"] <= 0:
            flags.append("WEAK_INCREMENTAL_SIGNER_VALUE")
        design_flags.append({
            "class_id": class_id,
            "gloss": p1["gloss"],
            "coverage_deficit_level": p1["coverage_deficit_level"],
            "human_decision": p1["human_decision"],
            "p1_external_share": p1["external_clip_share"],
            "p1_signer_slots": p1["signer_slots_retained"],
            "p2_signer_slots": p2["signer_slots_retained"],
            "p2_slot_loss_fraction": (p1["signer_slots_retained"] - p2["signer_slots_retained"]) / p1["signer_slots_retained"],
            "p3_signer_slots": p3["signer_slots_retained"],
            "p3_slot_loss_fraction": (p1["signer_slots_retained"] - p3["signer_slots_retained"]) / p1["signer_slots_retained"],
            "p1_new_signer_gain": p1["new_signer_gain"],
            "p1_effective_signer_gain": p1["effective_signer_gain"],
            "either_hand_observation_delta_semlex_minus_apphear": p1["either_hand_observed_rate"] - float(app["apphear_at_least_one_observed_rate"]),
            "design_flags": "|".join(flags) if flags else "NONE",
            "flag_threshold_contract": "high_share>2/3; substantial_slot_sacrifice>=25%; low_gain<=2; missingness_shift>=25pp; large_gain=P1 classwise p75",
        })
    write_csv(OUT / "p5d8_class_design_flags.csv", design_flags, list(design_flags[0]))

    missingness_rows: list[dict[str, Any]] = []
    for summary in policy_summary:
        policy = summary["policy"]
        rows = selected[policy]
        missingness_rows.append({
            "scope": policy,
            "selected_external_clips": len(rows),
            "lh_observed_rate": weighted_rate(rows, "lh_observed_rate"),
            "rh_observed_rate": weighted_rate(rows, "rh_observed_rate"),
            "both_hands_observed_rate": weighted_rate(rows, "both_observed_rate"),
            "either_hand_observed_rate": weighted_rate(rows, "at_least_one_observed_rate"),
            "neither_hand_observed_rate": 1.0 - weighted_rate(rows, "at_least_one_observed_rate"),
            "valid_hand_landmark_rate": weighted_rate(rows, "valid_hand_landmark_rate"),
            "body_valid_rate": weighted_rate(rows, "body_valid_rate"),
            "median_real_sequence_length": median(int(row["real_length"]) for row in rows),
            "comparison_basis": "real/non-padding frames only; descriptive, not exclusion criterion",
        })
    missingness_rows.append({
        "scope": "MATCHED_65_CLASS_APPHEAR_TRAIN",
        "selected_external_clips": int(overall_apphear["apphear_clips"]),
        "lh_observed_rate": float(overall_apphear["apphear_lh_observed_rate"]),
        "rh_observed_rate": float(overall_apphear["apphear_rh_observed_rate"]),
        "both_hands_observed_rate": float(overall_apphear["apphear_both_observed_rate"]),
        "either_hand_observed_rate": float(overall_apphear["apphear_at_least_one_observed_rate"]),
        "neither_hand_observed_rate": float(overall_apphear["apphear_neither_observed_rate"]),
        "valid_hand_landmark_rate": float(overall_apphear["apphear_valid_hand_landmark_rate"]),
        "body_valid_rate": float(overall_apphear["apphear_body_valid_rate"]),
        "median_real_sequence_length": float(overall_apphear["apphear_median_sequence_length"]),
        "comparison_basis": "P5-D7B matched 65-class AppHear TRAIN, real/non-padding frames only",
    })
    write_csv(OUT / "p5d8_policy_missingness_comparison.csv", missingness_rows, list(missingness_rows[0]))

    composition_rows: list[dict[str, Any]] = []
    for summary in policy_summary:
        policy = summary["policy"]
        stats = class_stats_by_policy[policy]
        composition_rows.append({
            "policy": policy,
            "exact_form_classes": sum(exact_decision(value["human_decision"]) for value in stats.values()),
            "exact_form_clips": summary["exact_form_clip_count"],
            "exact_form_signer_slots": summary["exact_form_signer_slots"],
            "compatible_variant_classes": sum(value["human_decision"] == "ACCEPT_COMPATIBLE_VARIANT" for value in stats.values()),
            "compatible_variant_clips": summary["compatible_variant_clip_count"],
            "compatible_variant_signer_slots": summary["compatible_variant_signer_slots"],
            "all_external_material_compatible_variant_classes": "|".join(sorted(value["gloss"] for value in stats.values() if value["human_decision"] == "ACCEPT_COMPATIBLE_VARIANT")),
            "lexical_decisions_preserved": True,
        })
    write_csv(OUT / "p5d8_exact_variant_composition.csv", composition_rows, list(composition_rows[0]))

    # Pairwise deterministic dominance.
    dominance_rows: list[dict[str, Any]] = []
    dominated: set[str] = set()
    for a in summaries:
        for b in summaries:
            if a == b:
                continue
            left, right = summaries[a], summaries[b]
            conditions = {
                "b_slots_ge_a": right["retained_signer_class_slots"] >= left["retained_signer_class_slots"],
                "b_classes_ge_a": right["supplemented_classes"] >= left["supplemented_classes"],
                "b_clips_le_a": right["external_clips"] <= left["external_clips"],
                "b_global_share_le_a": right["global_external_share"] <= left["global_external_share"],
                "b_median_share_le_a": right["median_class_external_share"] <= left["median_class_external_share"],
                "b_max_share_le_a": right["maximum_class_external_share"] <= left["maximum_class_external_share"],
            }
            strict = any([
                right["retained_signer_class_slots"] > left["retained_signer_class_slots"],
                right["supplemented_classes"] > left["supplemented_classes"],
                right["external_clips"] < left["external_clips"],
                right["global_external_share"] < left["global_external_share"],
                right["median_class_external_share"] < left["median_class_external_share"],
                right["maximum_class_external_share"] < left["maximum_class_external_share"],
            ])
            is_dominated = all(conditions.values()) and strict
            if is_dominated:
                dominated.add(a)
            dominance_rows.append({
                "candidate_policy_a": a,
                "comparison_policy_b": b,
                **conditions,
                "at_least_one_strictly_better": strict,
                "a_dominated_by_b": is_dominated,
                "dominance_definition": "B >= slots/classes and <= clips/global-share/median-share/max-share, with >=1 strict",
            })
    write_csv(OUT / "p5d8_policy_dominance_analysis.csv", dominance_rows, list(dominance_rows[0]))
    non_dominated = [policy for policy in POLICIES if policy not in dominated]

    # Frozen priority rule. P1 preserves every slot/class, removes repetitions,
    # and caps are accepted only if concentration materially improves with <=5%
    # slot loss and <=5 affected classes.
    p1 = summaries["P1_ONE_CLIP_PER_EXTERNAL_SIGNER_CLASS"]
    cap_candidates: list[str] = []
    for policy in ("P3_ONE_PER_SIGNER_CLASS_CLASS_SHARE_67", "P2_ONE_PER_SIGNER_CLASS_CLASS_SHARE_50"):
        cap = summaries[policy]
        slot_loss = 1.0 - cap["slot_retention_percent"]
        affected = sum(
            class_stats_by_policy[policy][class_id]["signer_slots_retained"] < p1_stats[class_id]["signer_slots_retained"]
            for class_id in p1_stats
        )
        materially_reduces = (
            p1["classes_above_67pct_external"] > 0
            and cap["classes_above_67pct_external"] == 0
        )
        if policy in non_dominated and materially_reduces and slot_loss <= 0.05 and affected <= 5:
            cap_candidates.append(policy)
    selected_policy = cap_candidates[0] if cap_candidates else "P1_ONE_CLIP_PER_EXTERNAL_SIGNER_CLASS"
    selected_rows = selected[selected_policy]
    selected_summary = summaries[selected_policy]
    selected_stats = class_stats_by_policy[selected_policy]
    limitation_tokens = {
        "P1_HIGH_EXTERNAL_SOURCE_SHARE_GT_67PCT",
        "P2_SUBSTANTIAL_SIGNER_COVERAGE_SACRIFICE_GE_25PCT",
        "P3_SUBSTANTIAL_SIGNER_COVERAGE_SACRIFICE_GE_25PCT",
        "SEMLEX_EXTERNAL_SIGNERS_LE_5",
        "COMPATIBLE_VARIANT_EXTERNAL_MATERIAL",
        "EITHER_HAND_OBSERVATION_SHIFT_GE_25PP",
        "WEAK_INCREMENTAL_SIGNER_VALUE",
    }
    limitations = [
        row for row in design_flags
        if set(row["design_flags"].split("|")) & limitation_tokens
    ]
    overall_classification = "SUPPLEMENTATION_POLICY_READY_WITH_CLASS_LIMITATIONS" if limitations else "SUPPLEMENTATION_POLICY_READY"
    selected_affected = sum(
        selected_stats[class_id]["signer_slots_retained"] < p1_stats[class_id]["signer_slots_retained"]
        for class_id in p1_stats
    )
    selected_slot_loss = EXPECTED["semlex_slots"] - selected_summary["retained_signer_class_slots"]
    if selected_policy == "P1_ONE_CLIP_PER_EXTERNAL_SIGNER_CLASS":
        selection_rationale = (
            f"{selected_policy} is non-dominated under the frozen rule; it retains "
            f"{selected_summary['retained_signer_class_slots']}/{EXPECTED['semlex_slots']} signer-class slots and "
            f"{selected_summary['supplemented_classes']}/65 classes while using {selected_summary['external_clips']} external clips. "
            "Neither cap eliminated concentrated >67% classes while keeping slot loss <=5% and affected classes <=5."
        )
    else:
        selection_rationale = (
            f"{selected_policy} is the least restrictive non-dominated cap that removes all "
            f"{p1['classes_above_67pct_external']} P1 classes above two-thirds external share while losing only "
            f"{selected_slot_loss}/{EXPECTED['semlex_slots']} signer-class slots ({selected_slot_loss / EXPECTED['semlex_slots']:.2%}) "
            f"across {selected_affected} classes; it retains all 65 accepted classes and all 32 source-distinct signers."
        )

    selected_manifest: list[dict[str, Any]] = []
    for row in sorted(selected_rows, key=lambda value: (int(value["apphear_class_id"]), value["namespaced_semlex_signer_id"], value["stable_sample_hash"])):
        selected_manifest.append({
            "apphear_class_id": int(row["apphear_class_id"]),
            "apphear_gloss": row["apphear_gloss"],
            "human_lexical_decision": row["human_decision"],
            "semlex_lexical_id": row["semlex_lexical_id"],
            "semlex_sample_id": row["semlex_sample_id"],
            "namespaced_semlex_signer_id": row["namespaced_semlex_signer_id"],
            "semlex_source_split": row["semlex_split"],
            "raw_sha256": row["raw_sha256"],
            "native_dwpose_path": row["native_path"],
            "v2_path": row["v2_path"],
            "training_usability_state": row["training_usability_state"],
            "policy_selection_reason": POLICIES[selected_policy],
            "stable_sample_hash": row["stable_sample_hash"],
            "source_identity_governance": "CROSS_DATASET_SIGNER_IDENTITY_ASSUMED_DISTINCT",
        })
    selected_fields = list(selected_manifest[0])
    write_csv(OUT / "p5d8_selected_policy_manifest.csv", selected_manifest, selected_fields)
    selected_manifest_sha = sha256(OUT / "p5d8_selected_policy_manifest.csv")

    # Provenance attestation remains deliberately incomplete.
    attestation = {
        "status": "REVIEW_PROVENANCE_METADATA_INCOMPLETE",
        "completed_human_decision_sheet_sha256": EXPECTED["decision_sheet_sha256"],
        "accept_exact_form_classes": 47,
        "accept_compatible_variant_classes": 18,
        "unresolved_classes": ["IF", "OLD", "GET", "TURN", "ANY"],
        "rejected_classes": 0,
        "reviewer_name": "",
        "review_date": "",
        "attestation_date": "",
        "project_lead_confirmation": "",
        "training_authorization": "BLOCKED_BY_PROVENANCE",
        "instruction": "Project lead must complete all blank attestation fields before any P5-D9 training authorization.",
    }
    write_json(OUT / "human_review_provenance_attestation.json", attestation)
    write_text(OUT / "human_review_provenance_attestation.md", f"""# Human Review Provenance Attestation

Status: `REVIEW_PROVENANCE_METADATA_INCOMPLETE`

- Completed decision-sheet SHA-256: `{EXPECTED['decision_sheet_sha256']}`
- Accepted exact-form classes: 47
- Accepted compatible-variant classes: 18
- Unresolved/excluded: IF, OLD, GET, TURN, ANY
- Rejected: 0

Complete these fields before P5-D9 training can be authorized:

- reviewer_name: ______________________________
- review_date: _________________________________
- attestation_date: ____________________________
- project_lead_confirmation: ___________________

By completing this attestation, the project lead confirms that the completed human decision sheet is the governed lexical-form review used to define the 65 accepted Sem-Lex classes. This document does not authorize training by itself.
""")

    init_rows = read_csv(D2 / "p5d2_initialization_parity.csv")
    init_contract: dict[str, Any] = {}
    for seed in (101, 202, 303):
        rows = [row for row in init_rows if int(row["seed"]) == seed]
        if len(rows) != 2 or len({row["initialization_file_sha256"] for row in rows}) != 1 or not all(row["pair_equal"] == "1" for row in rows):
            raise RuntimeError(f"P5D8_INITIALIZATION_PARITY_FAILURE:{seed}")
        path = Path(rows[0]["initialization_path"])
        if sha256(path) != rows[0]["initialization_file_sha256"]:
            raise RuntimeError(f"P5D8_INITIALIZATION_HASH_FAILURE:{seed}")
        init_contract[str(seed)] = {
            "initial_weight_artifact": str(path),
            "initial_weight_sha256": rows[0]["initialization_file_sha256"],
            "initial_weight_tensor_sha256": rows[0]["initial_weight_tensor_sha256"],
            "pfce_clipce_pair_equal": True,
        }
    d3_contract = json.loads((D3 / "p5d3_subset_contract.json").read_text(encoding="utf-8"))
    budget_rows = read_csv(D3 / "p5d3_training_budget_audit.csv")
    budget_verified = len(budget_rows) == 12 and all(
        int(row["required_optimizer_updates"]) == 12300
        and int(row["actual_optimizer_updates"]) == 12300
        and int(row["validation_every_updates"]) == 123
        and int(row["actual_validation_opportunities"]) == 100
        and row["status"] == "PASS"
        for row in budget_rows
    )
    if not budget_verified or not d3_contract["d2_reuse_integrity"]["passed"]:
        raise RuntimeError("P5D8_D2_D3_CONTRACT_VERIFICATION_FAILURE")
    baseline_checkpoints = d3_contract["d2_reuse_integrity"]["checkpoints"]
    combined_membership_payload = [f"APPHEAR|{sample}" for sample in sorted(sample_ids)] + [
        f"SEMLEX|{row['semlex_sample_id']}|{row['apphear_class_id']}|{row['namespaced_semlex_signer_id']}"
        for row in selected_manifest
    ]
    combined_membership_sha = hashlib.sha256("\n".join(combined_membership_payload).encode("utf-8")).hexdigest()
    training_contract = {
        "contract_id": "P5D9_CONTROLLED_SEMLEX_SUPPLEMENTATION_V1",
        "status": "PREPARED_NOT_EXECUTED_TRAINING_BLOCKED_BY_REVIEW_PROVENANCE",
        "primary_causal_question": "Does governed external class-wise signer/variant supplementation improve unseen-signer generalization?",
        "baseline_membership": {"apphear_train_clips": 3926, "v2_train_sha256": EXPECTED["v2_train_sha256"]},
        "supplemented_membership": {
            "apphear_train_clips": 3926,
            "selected_policy": selected_policy,
            "selected_semlex_clips": len(selected_manifest),
            "selected_policy_manifest": str((OUT / "p5d8_selected_policy_manifest.csv").resolve()),
            "selected_policy_manifest_sha256": selected_manifest_sha,
            "combined_membership_sha256": combined_membership_sha,
            "same_manifest_all_objectives_and_seeds": True,
        },
        "representation": {"name": "DWPOSE_REPRESENTATION_V2_238", "input_shape": [96, 238], "changes": "NONE"},
        "model": {"architecture": "4x64 causal TCN", "dilations": [1, 2, 4, 8], "kernel": 3, "dropout": 0.3, "parameters": 163884, "changes": "NONE"},
        "objectives": ["PFCE_MATCHED", "CLIPCE_AGGREGATION_ALIGNED"],
        "optimizer": {"name": "AdamW", "learning_rate": 0.0005, "weight_decay": 0.0001, "batch_size": 32, "optimizer_update_budget": 12300},
        "seeds": [101, 202, 303],
        "initializations": init_contract,
        "sampling": {
            "membership_order": "AppHear rows followed by selected Sem-Lex rows, each source internally ordered by stable sample identity",
            "seed_specific_shuffle": "same deterministic seed-specific epoch/batch shuffle implementation as governed D2/D3",
            "source_handling": "ordinary membership; no source-aware over/undersampling",
            "class_balancing": "NONE",
        },
        "checkpoint_selection": {
            "validation_data": "same governed AppHear primary validation only",
            "validation_every_optimizer_updates": 123,
            "validation_opportunities": 100,
            "metric": "primary-validation clip NLL",
            "direction": "minimum",
            "tie_break": "earliest checkpoint because implementation updates best only on strict lower-than (<)",
            "final_loading": "load saved best.keras after full 12300-update run",
            "clip_aggregation": "per-frame softmax -> masked arithmetic mean over real frames",
            "evidence": [str((D2 / "p5d2_objective_contract.json").resolve()), str((D3 / "p5d3_subset_contract.json").resolve()), str((ROOT / "model/p5d2_temporal_objective_ablation.py").resolve()), str((ROOT / "model/p5d3_data_coverage_curve.py").resolve())],
        },
        "baseline_reuse": {"reusable": True, "reason": "D3 hash-verified the six D2 100% checkpoints under the same V2/model/objective/update/selection contracts", "checkpoints": baseline_checkpoints},
        "new_runs": [f"{objective}|seed_{seed}" for objective in ("PFCE_MATCHED", "CLIPCE_AGGREGATION_ALIGNED") for seed in (101, 202, 303)],
        "new_run_count": 6,
        "controls": {"augmentation": "NONE", "warm_start": "NONE", "class_loss_balancing": "NONE", "source_balancing": "NONE", "external_validation": "NONE", "protected_test": "NOT_ACCESSED"},
        "training_authorization": "BLOCKED_BY_PROVENANCE",
    }
    write_json(OUT / "p5d9_future_training_contract.json", training_contract)
    evaluation_contract = {
        "contract_id": "P5D9_CONTROLLED_SEMLEX_SUPPLEMENTATION_EVALUATION_V1",
        "status": "PREPARED_NOT_EXECUTED",
        "primary_question": training_contract["primary_causal_question"],
        "evaluation_population": "same governed AppHear primary validation only",
        "protected_test_access": False,
        "primary_scope": "all 236 classes",
        "primary_metrics": ["ordinary_top1", "signer_balanced_top1", "macro_f1", "top5", "clip_nll", "per_frame_accuracy", "signer_specific_metrics"],
        "temporal_failure_taxonomy": ["PERSISTENT_WRONG", "PHASE_DEPENDENT", "TRUE_MAJORITY_FINAL_WRONG"],
        "diagnostic_slices": ["all_236_classes", "65_supplemented_classes", "171_unsupplemented_classes", "ACCEPT_EXACT_FORM_supplemented", "ACCEPT_COMPATIBLE_VARIANT_supplemented", "critical_supplemented", "high_deficit_supplemented"],
        "comparison": "seed-matched supplemented minus reusable baseline for PFCE and CLIPCE; report all seeds, signer-aware uncertainty, and full-vocabulary effects",
        "policy_selection_reopening": "PROHIBITED_AFTER_RESULTS",
    }
    write_json(OUT / "p5d9_future_evaluation_contract.json", evaluation_contract)

    selected_policy_record = {
        "selected_policy": selected_policy,
        "selection_rationale": selection_rationale,
        "selected_policy_manifest_sha256": selected_manifest_sha,
        "combined_membership_sha256": combined_membership_sha,
        "dominated_policies": sorted(dominated),
        "non_dominated_policies": non_dominated,
        "selection_inputs": "TRAIN structure, signer coverage, source composition, human lexical decisions, descriptive missingness only",
        "validation_used_for_selection": False,
    }
    write_json(OUT / "p5d8_selected_policy.json", selected_policy_record)
    decision = {
        "overall_classification": overall_classification,
        "confidence": "HIGH",
        "selected_policy": selected_policy,
        "training_authorization": "BLOCKED_BY_PROVENANCE",
        "verified_fact": f"The selected manifest preserves {selected_summary['retained_signer_class_slots']} source-distinct class-signer slots across {selected_summary['supplemented_classes']} accepted classes with {selected_summary['external_clips']} deterministic external clips.",
        "design_interpretation": selection_rationale,
        "not_yet_established": "Whether the selected Sem-Lex supplementation policy improves unseen-signer recognition.",
    }
    write_json(OUT / "p5d8_decision.json", decision)
    write_json(OUT / "p5d8_next_gate.json", {
        "next_gate": "P5D9_CONTROLLED_SEMLEX_SUPPLEMENTATION_EXPERIMENT",
        "next_gate_executed": False,
        "blocking_condition": "TRAINING_AUTHORIZATION_BLOCKED_BY_REVIEW_PROVENANCE",
        "required_first_action": "PROJECT_LEAD_COMPLETES_HUMAN_REVIEW_PROVENANCE_ATTESTATION",
    })

    report = f"""# P5-D8 Sem-Lex Supplementation Design and Balancing Audit

## Result

`{overall_classification}` with **HIGH** confidence. No training, extraction, prediction, tensor merge, or validation-based policy selection occurred.

The selected design is `{selected_policy}`: {selected_summary['external_clips']} deterministic external clips preserve {selected_summary['retained_signer_class_slots']}/893 class-signer slots across {selected_summary['supplemented_classes']}/65 accepted classes. Sem-Lex signer identities remain namespaced and source-distinct.

## Policy comparison

| Policy | External clips | Slots | Global share | Median class share | Maximum class share | >50% classes | >67% classes |
|---|---:|---:|---:|---:|---:|---:|---:|
"""
    for row in policy_summary:
        report += f"| {row['policy']} | {row['external_clips']} | {row['retained_signer_class_slots']} | {row['global_external_share']:.2%} | {row['median_class_external_share']:.2%} | {row['maximum_class_external_share']:.2%} | {row['classes_above_50pct_external']} | {row['classes_above_67pct_external']} |\n"
    report += f"""

P0 is diagnostic and is dominated by P1 when applicable under the frozen design-level rule. P2 and P3 quantify source-share versus signer-slot tradeoffs; the caps are not claimed safe or optimal.

## Selection rationale

{selection_rationale}

The selected policy has a global external share of {selected_summary['global_external_share']:.2%}, a median supplemented-class share of {selected_summary['median_class_external_share']:.2%}, and a maximum class share of {selected_summary['maximum_class_external_share']:.2%}. Class limitations remain explicit in `p5d8_class_design_flags.csv`; none were automatically excluded.

## Source and lexical composition

Selected external either-hand observation is {selected_summary['either_hand_observation']:.2%}; both-hand observation is {selected_summary['both_hand_observation']:.2%}; median real length is {selected_summary['median_real_sequence_length']}. The matched AppHear figures are {float(overall_apphear['apphear_at_least_one_observed_rate']):.2%}, {float(overall_apphear['apphear_both_observed_rate']):.2%}, and {float(overall_apphear['apphear_median_sequence_length']):.0f}. These are descriptive source shifts, not rejection thresholds.

Exact-form and intentionally accepted compatible-variant decisions are preserved without relabeling. The selected policy includes {selected_summary['exact_form_clip_count']} exact-form clips/{selected_summary['exact_form_signer_slots']} slots and {selected_summary['compatible_variant_clip_count']} compatible-variant clips/{selected_summary['compatible_variant_signer_slots']} slots.

## Future P5-D9 contract

The six governed 100% D2 baselines are reusable because D3 independently hash-verified them. Future supplemented runs are fixed to 12,300 optimizer updates, validation every 123 updates (100 opportunities), minimum primary-validation clip NLL with earliest-on-tie behavior, and the same seed-specific initialization artifacts for 101/202/303. The same selected manifest is used by PFCE and CLIPCE for every seed.

Training remains blocked: `TRAINING_AUTHORIZATION_BLOCKED_BY_REVIEW_PROVENANCE`. The project lead must complete the attestation fields before P5-D9 can be authorized.

## Evidence boundary

- **Verified fact:** deterministic manifest simulation preserves the reported signer-class coverage and quantifies source-share tradeoffs without model outcomes.
- **Design interpretation:** the selected policy is the cleanest bounded intervention under the frozen priority rule.
- **Not yet established:** whether supplementation improves unseen-signer recognition.

`progress-tracker.md` was not modified. P5-D9 was not executed.
"""
    write_text(OUT / "P5D8_SUPPLEMENTATION_DESIGN_RESULT.md", report)

    hashes_after = {name: sha256(path) for name, path in source_paths.items()}
    integrity = {
        "passed": hashes_before == hashes_after,
        "source_hashes_before": hashes_before,
        "source_hashes_after": hashes_after,
        "upstream_artifact_manifests": upstream_manifests,
        "apphear_train_clips": EXPECTED["train"],
        "apphear_classes": EXPECTED["classes"],
        "semlex_usable_candidates": len(enriched),
        "semlex_classes": len(candidate_by_class),
        "semlex_source_distinct_signers": len({row["namespaced_semlex_signer_id"] for row in enriched}),
        "semlex_signer_class_slots": len(slots),
        "cross_dataset_signer_identity_assumption": "CROSS_DATASET_SIGNER_IDENTITY_ASSUMED_DISTINCT",
        "decode_exclusions_remain_excluded": 8,
        "zero_hand_quarantines_remain_excluded": 2,
        "unresolved_classes_remain_excluded": ["IF", "OLD", "GET", "TURN", "ANY"],
        "human_decisions_unchanged": hashes_before["decision_sheet"] == hashes_after["decision_sheet"],
        "protected_test_accessed": False,
        "training_executed": False,
        "external_merge": False,
        "combined_tensors_created": False,
        "new_extraction": False,
        "v2_regeneration": False,
        "validation_mutated": False,
        "model_changed": False,
        "p4_reopened": False,
        "popsign_used": False,
        "additional_external_dataset_used": False,
        "android_modified": False,
        "context_files_modified": False,
        "progress_tracker_untouched": hashes_before["progress_tracker"] == hashes_after["progress_tracker"],
        "d2_d3_update_budget_verified": budget_verified,
        "seed_specific_initial_weight_parity_verified": True,
        "future_baseline_reuse_verified": True,
    }
    write_json(OUT / "p5d8_integrity.json", integrity)

    required = [
        "P5D8_SUPPLEMENTATION_DESIGN_RESULT.md", "p5d8_integrity.json",
        "human_review_provenance_attestation.md", "human_review_provenance_attestation.json",
        "p5d8_classwise_source_baseline.csv", "p5d8_policy_p0_all_semlex.csv",
        "p5d8_policy_p1_one_per_signer_class.csv", "p5d8_policy_p2_source50.csv",
        "p5d8_policy_p3_source67.csv", "p5d8_policy_comparison.csv", "p5d8_policy_by_class.csv",
        "p5d8_policy_missingness_comparison.csv", "p5d8_exact_variant_composition.csv",
        "p5d8_class_design_flags.csv", "p5d8_policy_dominance_analysis.csv",
        "p5d8_selected_policy_manifest.csv", "p5d8_selected_policy.json",
        "p5d9_future_training_contract.json", "p5d9_future_evaluation_contract.json",
        "p5d8_decision.json", "p5d8_next_gate.json",
    ]
    manifest = {
        "contract_id": "P5D8_ARTIFACT_HASH_MANIFEST_V1",
        "artifacts": [
            {"path": name, "bytes": (OUT / name).stat().st_size, "sha256": sha256(OUT / name)}
            for name in required
        ] + [{"path": str(Path(__file__).relative_to(ROOT)), "bytes": Path(__file__).stat().st_size, "sha256": sha256(Path(__file__)), "role": "supporting_code"}],
        "selected_policy_manifest_sha256": selected_manifest_sha,
    }
    write_json(OUT / "artifact_hash_manifest.json", manifest)
    print(json.dumps({
        "integrity": integrity["passed"],
        "selected_policy": selected_policy,
        "selected_manifest_sha256": selected_manifest_sha,
        "policy_summary": policy_summary,
        "dominated": sorted(dominated),
        "non_dominated": non_dominated,
        "class_limitations": len(limitations),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
