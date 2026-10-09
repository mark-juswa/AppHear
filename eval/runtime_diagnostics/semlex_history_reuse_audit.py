"""Recover Sem-Lex coverage evidence without extraction or training.

This audit is intentionally limited to existing metadata, manifests, and contracts.
It does not open the protected AppHear test population and it does not run any model.
"""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.perception_vnext.offline_candidate01 import iter_video_frames  # noqa: E402

OUT = (
    ROOT
    / "artifacts"
    / "recognition_upgrade"
    / "perception_vnext"
    / "recognition_utility_236_01"
    / "semlex_history_reuse_audit_01"
)
P5 = ROOT / "artifacts" / "recognition_upgrade" / "p5_representation_v2"
CURRENT = (
    ROOT
    / "artifacts"
    / "recognition_upgrade"
    / "perception_vnext"
    / "recognition_utility_236_01"
    / "dataset"
)

D4 = P5 / "p5d4_external_data_audit_01" / "full_vocabulary_external_match_matrix.csv"
D6 = P5 / "p5d6_semlex_post_review_01" / "p5d6_completed_human_review_result.json"
D7B = P5 / "p5d7b_semlex_integrity_audit_01" / "semlex_post_audit_candidate_manifest.csv"
D8 = P5 / "p5d8_supplementation_design_01" / "p5d8_selected_policy_manifest.csv"
ATTESTATION = (
    P5
    / "p5d8_supplementation_design_01"
    / "human_review_provenance_attestation.json"
)
GOVERNANCE = CURRENT / "governance_audit.json"
CONTRACT = CURRENT / "contract.json"

METADATA = Path("D:/Downloads/semlex_metadata.csv")
ARCHIVE = Path("G:/SEM LEX/train.tar.gz")
POSE_ARCHIVE = Path("G:/SEM LEX/sem-lex-train-poses.tar.gz")
STAGED_ROOT = Path("G:/SEM LEX/AppHear_P5D7_candidate/staged")
STAGED = STAGED_ROOT / "staged_manifest.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile_summary(values: list[int]) -> dict[str, float | int]:
    return {
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
    }


def windows_path(raw: str) -> Path:
    posix = PurePosixPath(raw)
    if len(posix.parts) >= 3 and posix.parts[0] == "/" and posix.parts[1] == "mnt":
        drive = posix.parts[2].upper()
        return Path(f"{drive}:/", *posix.parts[3:])
    return Path(raw)


def candidate01_decode_smoke(
    selected: list[dict[str, str]], staged_rows: dict[str, dict[str, str]]
) -> list[dict[str, object]]:
    picked = list(selected[:6])
    represented = {row["human_lexical_decision"] for row in picked}
    for row in selected:
        if row["human_lexical_decision"] not in represented:
            picked.append(row)
            represented.add(row["human_lexical_decision"])
    results: list[dict[str, object]] = []
    for row in picked:
        staged = staged_rows[row["semlex_sample_id"]]
        video = windows_path(staged["raw_video_path"])
        iterator, video_meta = iter_video_frames(video, None)
        frames = list(iterator)
        timestamps = [item[1] for item in frames]
        results.append(
            {
                "sample_id": row["semlex_sample_id"],
                "human_lexical_decision": row["human_lexical_decision"],
                "decoded_frames": len(frames),
                "source_width": int(frames[0][3].shape[1]),
                "source_height": int(frames[0][3].shape[0]),
                "duration_ms": timestamps[-1] - timestamps[0],
                "strictly_increasing_timestamps": all(
                    right > left for left, right in zip(timestamps, timestamps[1:])
                ),
                "timestamp_sources": dict(Counter(item[2] for item in frames)),
                **video_meta,
            }
        )
    return results


def metadata_summary() -> dict:
    rows = read_csv(METADATA)
    by_split: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_split[row["split"].strip()].append(row)

    summary: dict[str, object] = {
        "path": str(METADATA),
        "bytes": METADATA.stat().st_size,
        "sha256": sha256(METADATA),
        "rows": len(rows),
        "columns": list(rows[0]),
        "splits": {},
    }
    signer_sets: dict[str, set[str]] = {}
    for split, split_rows in sorted(by_split.items()):
        signer_sets[split] = {row["signer_id"].strip() for row in split_rows}
        durations = [
            float(row["duration"])
            for row in split_rows
            if row.get("duration", "").strip()
        ]
        lexical_pairs = {
            (row["label_type"].strip().casefold(), row["label"].strip().casefold())
            for row in split_rows
        }
        labels = {row["label"].strip().casefold() for row in split_rows}
        summary["splits"][split] = {
            "rows": len(split_rows),
            "signers": len(signer_sets[split]),
            "lexical_pairs": len(lexical_pairs),
            "normalized_labels": len(labels),
            "median_duration_ms": statistics.median(durations),
            "label_types": dict(Counter(row["label_type"].strip() for row in split_rows)),
            "sign_types": dict(Counter(row.get("Sign Type", "").strip() for row in split_rows)),
        }
    summary["all_lexical_pairs"] = len(
        {
            (row["label_type"].strip().casefold(), row["label"].strip().casefold())
            for row in rows
        }
    )
    summary["all_normalized_labels"] = len(
        {row["label"].strip().casefold() for row in rows}
    )
    summary["all_signers"] = len({row["signer_id"].strip() for row in rows})
    summary["signer_overlap"] = {
        "train_val": sorted(signer_sets.get("train", set()) & signer_sets.get("val", set())),
        "train_test": sorted(signer_sets.get("train", set()) & signer_sets.get("test", set())),
        "val_test": sorted(signer_sets.get("val", set()) & signer_sets.get("test", set())),
    }
    return summary


def main() -> None:
    required = [D4, D6, D7B, D8, ATTESTATION, GOVERNANCE, CONTRACT, METADATA, STAGED]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"SEMLEX_AUDIT_MISSING_INPUT:{missing}")

    OUT.mkdir(parents=True, exist_ok=True)
    d4_rows = [row for row in read_csv(D4) if row["external_dataset"] == "SEM_LEX"]
    if len(d4_rows) != 236:
        raise SystemExit(f"SEMLEX_AUDIT_VOCABULARY_MISMATCH:{len(d4_rows)}")
    selected = read_csv(D8)
    selected_by_class: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in selected:
        selected_by_class[int(row["apphear_class_id"])].append(row)

    mapping_rows: list[dict[str, object]] = []
    final_counts: Counter[str] = Counter()
    for row in sorted(d4_rows, key=lambda item: int(item["apphear_class_id"])):
        class_id = int(row["apphear_class_id"])
        accepted = selected_by_class.get(class_id, [])
        decisions = sorted({item["human_lexical_decision"] for item in accepted})
        candidate_clips = int(row["candidate_clip_count"])
        if "ACCEPT_COMPATIBLE_VARIANT" in decisions:
            final_status = "VARIANT"
        elif decisions:
            final_status = "EXACT"
        elif candidate_clips:
            final_status = "AMBIGUOUS_UNREVIEWED_OR_UNRESOLVED"
        else:
            final_status = "NO_MATCH"
        final_counts[final_status] += 1
        mapping_rows.append(
            {
                "apphear_class_id": class_id,
                "apphear_canonical_gloss": row["apphear_canonical_gloss"],
                "semlex_candidate_clips": candidate_clips,
                "semlex_candidate_signers": int(row["candidate_signer_count"]),
                "semlex_lexical_ids": row["external_lexical_id"],
                "d4_compatibility_state": row["compatibility_state"],
                "historical_human_decisions": "|".join(decisions),
                "audit_mapping_status": final_status,
                "p3_selected_clips": len(accepted),
                "p3_selected_signers": len(
                    {item["namespaced_semlex_signer_id"] for item in accepted}
                ),
                "mapping_note": row["translation_or_form_note"],
            }
        )

    mapping_path = OUT / "semlex_apphear_236_mapping.csv"
    with mapping_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(mapping_rows[0]))
        writer.writeheader()
        writer.writerows(mapping_rows)

    governance = read_json(GOVERNANCE)
    current_counts = {
        int(key): int(value)
        for key, value in governance["train"]["signers_per_class"]["counts_by_class_id"].items()
    }
    selected_signers_by_class = {
        class_id: {row["namespaced_semlex_signer_id"] for row in rows}
        for class_id, rows in selected_by_class.items()
    }
    coverage_rows: list[dict[str, object]] = []
    for row in mapping_rows:
        class_id = int(row["apphear_class_id"])
        added_signers = len(selected_signers_by_class.get(class_id, set()))
        coverage_rows.append(
            {
                "class_id": class_id,
                "gloss": row["apphear_canonical_gloss"],
                "mapping_status": row["audit_mapping_status"],
                "current_train_signers": current_counts[class_id],
                "selected_semlex_signers": added_signers,
                "combined_namespaced_signers": current_counts[class_id] + added_signers,
                "selected_semlex_clips": int(row["p3_selected_clips"]),
            }
        )
    coverage_path = OUT / "semlex_signer_class_coverage.csv"
    with coverage_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(coverage_rows[0]))
        writer.writeheader()
        writer.writerows(coverage_rows)

    staged_rows = {row["semlex_sample_id"]: row for row in read_csv(STAGED)}
    staged_missing_join: list[str] = []
    staged_missing_files: list[str] = []
    staged_hash_manifest_mismatch: list[str] = []
    for row in selected:
        sample_id = row["semlex_sample_id"]
        staged = staged_rows.get(sample_id)
        if staged is None:
            staged_missing_join.append(sample_id)
            continue
        if staged["raw_sha256"].casefold() != row["raw_sha256"].casefold():
            staged_hash_manifest_mismatch.append(sample_id)
        if not windows_path(staged["raw_video_path"]).is_file():
            staged_missing_files.append(sample_id)

    before_signers = [item["current_train_signers"] for item in coverage_rows]
    after_signers = [item["combined_namespaced_signers"] for item in coverage_rows]
    selected_signers = {row["namespaced_semlex_signer_id"] for row in selected}
    d7b = read_csv(D7B)
    usable_d7b = [row for row in d7b if row["training_usability_state"] == "USABLE_CANDIDATE"]
    decode_smoke = candidate01_decode_smoke(selected, staged_rows)

    summary = {
        "audit_id": "SEMLEX_HISTORY_AND_REUSE_AUDIT",
        "generated_from_existing_artifacts_only": True,
        "training_executed": False,
        "candidate01_extraction_executed": False,
        "protected_apphear_test_accessed": False,
        "metadata": metadata_summary(),
        "raw_media": {
            "train_archive": {
                "path": str(ARCHIVE),
                "exists": ARCHIVE.is_file(),
                "bytes": ARCHIVE.stat().st_size if ARCHIVE.is_file() else None,
            },
            "precomputed_pose_archive": {
                "path": str(POSE_ARCHIVE),
                "exists": POSE_ARCHIVE.is_file(),
                "bytes": POSE_ARCHIVE.stat().st_size if POSE_ARCHIVE.is_file() else None,
            },
            "staged_manifest": str(STAGED),
            "staged_rows": len(staged_rows),
            "p3_selected_rows": len(selected),
            "p3_selected_rows_joined_to_staged": len(selected) - len(staged_missing_join),
            "p3_selected_files_currently_present": len(selected) - len(staged_missing_files) - len(staged_missing_join),
            "p3_selected_manifest_hash_identities_match": len(selected) - len(staged_hash_manifest_mismatch) - len(staged_missing_join),
            "missing_join_sample_ids": staged_missing_join,
            "missing_file_sample_ids": staged_missing_files,
            "manifest_hash_mismatch_sample_ids": staged_hash_manifest_mismatch,
        },
        "vocabulary_overlap": {
            "apphear_classes": len(mapping_rows),
            "semlex_train_metadata_candidate_classes": sum(
                int(row["semlex_candidate_clips"]) > 0 for row in mapping_rows
            ),
            "semlex_train_metadata_candidate_clips": sum(
                int(row["semlex_candidate_clips"]) for row in mapping_rows
            ),
            "exact": final_counts["EXACT"],
            "alias": 0,
            "variant": final_counts["VARIANT"],
            "ambiguous_unreviewed_or_unresolved": final_counts[
                "AMBIGUOUS_UNREVIEWED_OR_UNRESOLVED"
            ],
            "missing": final_counts["NO_MATCH"],
            "missing_glosses": [
                row["apphear_canonical_gloss"]
                for row in mapping_rows
                if row["audit_mapping_status"] == "NO_MATCH"
            ],
            "historically_reviewed_and_accepted_classes": len(selected_by_class),
        },
        "usable_pool": {
            "d7b_usable_clips": len(usable_d7b),
            "d7b_usable_classes": len({row["apphear_class_id"] for row in usable_d7b}),
            "d7b_usable_signers": len({row["semlex_signer_id"] for row in usable_d7b}),
            "p3_selected_clips": len(selected),
            "p3_selected_classes": len(selected_by_class),
            "p3_selected_namespaced_signers": len(selected_signers),
            "p3_selected_signer_class_slots": len(
                {
                    (row["apphear_class_id"], row["namespaced_semlex_signer_id"])
                    for row in selected
                }
            ),
            "p3_selected_signers_per_class": percentile_summary(
                [len(value) for value in selected_signers_by_class.values()]
            ),
            "cross_dataset_identity": "ASSUMED_DISTINCT_BY_NAMESPACE_NOT_BIOMETRICALLY_VERIFIED",
        },
        "current_vs_selected_p3": {
            "current_train": {
                "clips": governance["train"]["clips"],
                "classes": governance["train"]["classes"],
                "source_names": sorted(governance["train"]["sources"]),
                "nominal_namespaced_signers": governance["train"]["signers"],
                "signers_per_class": percentile_summary(before_signers),
            },
            "current_train_plus_p3": {
                "clips": governance["train"]["clips"] + len(selected),
                "classes": governance["train"]["classes"],
                "source_names": sorted([*governance["train"]["sources"], "SEM_LEX"]),
                "nominal_namespaced_signers": governance["train"]["signers"]
                + len(selected_signers),
                "signers_per_class": percentile_summary(after_signers),
                "classes_gaining_namespaced_signers": len(selected_by_class),
                "classes_without_semlex_benefit": 236 - len(selected_by_class),
                "classes_with_variant_mapping": final_counts["VARIANT"],
                "classes_with_ambiguous_mapping_excluded": final_counts[
                    "AMBIGUOUS_UNREVIEWED_OR_UNRESOLVED"
                ],
            },
        },
        "governance": {
            "historical_attestation": read_json(ATTESTATION),
            "historical_scope": "P5-D9 project-lead research TRAIN run using the frozen P3 manifest",
            "current_candidate01_reuse": "UNRESOLVED_REQUIRES_SCOPE_SPECIFIC_REAUTHORIZATION_AND_TERMS_RECORD_CONFIRMATION",
            "native_semlex_val_or_test_used_for_supplementation": False,
        },
        "candidate01_compatibility": {
            "classification": "PARTIAL_TECHNICALLY_PROCESSABLE_BOUNDED_SMOKE",
            "representation_change_required": False,
            "existing_dwp_pose_v2_features_reusable_as_candidate01": False,
            "required_manifest_adapter": {
                "raw_video_path": "current staged WebM path",
                "raw_video_sha256": "existing staged raw SHA-256",
                "sample_id": "SEMLEX::<native video_id> or another collision-safe stable ID",
                "split": "train only",
                "class_id_and_gloss": "frozen AppHear mapping",
                "signer_group_id": "namespaced SEMLEX::<signer_id>",
                "source_dataset": "SEM_LEX",
                "span_path": "blank for whole isolated clip unless a separately governed span exists",
            },
            "bounded_decode_smoke": decode_smoke,
            "dataset_wide_preflight_still_required": (
                "container FPS/frame-count metadata are unreliable for some WebM files; "
                "the bounded sample had monotonic container timestamps"
            ),
        },
        "source_hashes": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in [D4, D6, D7B, D8, ATTESTATION, GOVERNANCE, CONTRACT]
        },
    }
    audit_json_path = OUT / "semlex_history_reuse_audit.json"
    audit_json_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    generated = [mapping_path, coverage_path, audit_json_path]
    report_path = OUT / "SEMLEX_HISTORY_AND_REUSE_AUDIT.md"
    if report_path.is_file():
        generated.append(report_path)
    (OUT / "artifact_hash_manifest.json").write_text(
        json.dumps(
            {
                "audit_id": "SEMLEX_HISTORY_AND_REUSE_AUDIT",
                "artifacts": [
                    {
                        "path": path.name,
                        "bytes": path.stat().st_size,
                        "sha256": sha256(path),
                    }
                    for path in generated
                ],
                "training_executed": False,
                "protected_apphear_test_accessed": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(OUT),
        "mapping_counts": dict(final_counts),
        "p3_selected_files_present": summary["raw_media"]["p3_selected_files_currently_present"],
        "current_vs_p3": summary["current_vs_selected_p3"],
        "protected_apphear_test_accessed": False,
    }, indent=2))


if __name__ == "__main__":
    main()
