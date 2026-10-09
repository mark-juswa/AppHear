"""P5-D5 Sem-Lex lexical-form qualification and acquisition planning.

Metadata only: no raw video access, DWPose, V2 generation, dataset mutation,
protected-test access, or model training.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/recognition_upgrade"
D4 = BASE / "p5_representation_v2/p5d4_external_data_audit_01"
OUT = BASE / "p5_representation_v2/p5d5_semlex_form_review_01"
SEMLEX = Path(r"D:\Downloads\semlex_metadata.csv")
SEMLEX_EXACT = BASE / "ru_d5/semlex_candidate_01/candidate_c/final_external_lineage.csv"
ASLLVD = BASE / "ru_d5/source_metadata/asllvd_signs_2023_10_23.csv"
MSASL = BASE / "ru_d5/source_metadata/ms_asl/MS-ASL/MSASL_train.json"
PROGRESS = ROOT / "context/progress-tracker.md"
PROGRESS_SHA = "12cf08f81959a413a60aa1f869615a24485a41ee3d796e61fce7489ae5c480cf"
SEMLEX_SHA = "f4250b2877e738f028e4b9517922952a350ec8952e59d53ceabdd778938fc3c3"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def norm(value: Any) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"\s*\d+$", "", text)
    return re.sub(r"[^a-z0-9]", "", text)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(name: str, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path = OUT / name
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def eff(counts: Counter[str]) -> float | None:
    total = sum(counts.values())
    if not total:
        return None
    return 1 / sum((value / total) ** 2 for value in counts.values())


def verify_d4() -> dict[str, str]:
    manifest = json.loads((D4 / "artifact_hash_manifest.json").read_text(encoding="utf-8"))
    checks: dict[str, str] = {}
    for item in manifest["artifacts"]:
        if item.get("role") == "supporting_code":
            path = ROOT / item["path"]
        else:
            path = D4 / item["path"]
        actual = sha256(path)
        if actual != item["sha256"]:
            raise RuntimeError(f"P5-D4 artifact hash mismatch: {path}")
        checks[item["path"]] = actual
    if not json.loads((D4 / "p5d4_integrity.json").read_text(encoding="utf-8"))["passed"]:
        raise RuntimeError("P5-D4 integrity is not passed")
    return checks


def projection_row(target: dict[str, Any], candidate: dict[str, Any], included: bool,
                   clips: int, signer_counts: Counter[str], mode: str) -> dict[str, Any]:
    added_signers = len(signer_counts) if included else 0
    return {
        "projection": mode, "class_id": target["class_id"], "canonical_gloss": target["canonical_gloss"],
        "coverage_deficit_level": target["coverage_deficit_level"], "qualification_state": candidate["qualification_state"],
        "included": included, "current_clips": target["current_clips"], "added_candidate_clips": clips if included else 0,
        "projected_clips": int(target["current_clips"]) + (clips if included else 0),
        "current_unique_signers": target["current_unique_signers"], "added_signer_class_slots": added_signers,
        "projected_unique_signers": int(target["current_unique_signers"]) + added_signers,
        "current_effective_signers": target["current_effective_signers"],
        "candidate_effective_signers": round(eff(signer_counts), 6) if included and eff(signer_counts) else "",
        "projection_only_no_samples_accepted": True,
    }


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    d4_hashes = verify_d4()
    source_before = {
        "d4_coverage_deficit_ranking": sha256(D4 / "coverage_deficit_ranking.csv"),
        "d4_current_coverage": sha256(D4 / "current_apphear_class_coverage.csv"),
        "d4_lexical_matrix": sha256(D4 / "lexical_compatibility_matrix.csv"),
        "d4_match_matrix": sha256(D4 / "full_vocabulary_external_match_matrix.csv"),
        "d4_human_queue": sha256(D4 / "human_form_review_queue.csv"),
        "d4_projected_coverage": sha256(D4 / "projected_coverage_by_dataset.csv"),
        "semlex_metadata": sha256(SEMLEX), "historical_semlex_review": sha256(SEMLEX_EXACT),
        "asllvd_metadata": sha256(ASLLVD), "msasl_train_metadata": sha256(MSASL),
        "progress_tracker": sha256(PROGRESS),
    }
    if source_before["semlex_metadata"] != SEMLEX_SHA or source_before["progress_tracker"] != PROGRESS_SHA:
        raise RuntimeError("Governed source hash mismatch")

    ranking = read_csv(D4 / "coverage_deficit_ranking.csv")
    selected = [r for r in ranking if r["coverage_deficit_rank"] in ("CRITICAL_COVERAGE_DEFICIT", "HIGH_COVERAGE_DEFICIT")]
    if len(selected) != 70:
        raise RuntimeError("P5D5_BLOCKED_TARGET_SET_MISMATCH")
    target_rows = [{
        "class_id": int(r["class_id"]), "canonical_gloss": r["canonical_gloss"],
        "coverage_deficit_level": r["coverage_deficit_rank"],
        "current_clips": int(r["current_train_clips"]),
        "current_unique_signers": int(r["current_unique_signers"]),
        "current_effective_signers": float(r["current_effective_signers"]),
        "current_signer_concentration": float(r["max_signer_share"]),
    } for r in selected]
    target_rows.sort(key=lambda r: (0 if r["coverage_deficit_level"].startswith("CRITICAL") else 1, r["class_id"]))
    write_csv("p5d5_target_70_classes.csv", target_rows)

    sem = pd.read_csv(SEMLEX, low_memory=False)
    sem = sem[sem["split"].astype(str).str.lower() == "train"].copy()
    sem["_norm"] = sem["label"].map(norm)
    exact_rows = read_csv(SEMLEX_EXACT)
    exact_by_gloss: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in exact_rows:
        if row.get("variant_decision") == "EXACT_TARGET":
            exact_by_gloss[row["canonical_gloss"]].append(row)

    asllvd = pd.read_csv(ASLLVD, low_memory=False)
    asllvd["_norm"] = asllvd["main entry gloss label"].map(norm)
    d4_sem = {int(r["apphear_class_id"]): r for r in read_csv(D4 / "full_vocabulary_external_match_matrix.csv") if r["external_dataset"] == "SEM_LEX"}

    qualifications: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    candidate_signer_counts: dict[int, Counter[str]] = {}
    strict_signer_counts: dict[int, Counter[str]] = {}
    for target in target_rows:
        cid, gloss, key = int(target["class_id"]), target["canonical_gloss"], norm(target["canonical_gloss"])
        group = sem[sem["_norm"] == key]
        signer_counts = Counter(group["signer_id"].dropna().astype(str))
        candidate_signer_counts[cid] = signer_counts
        label_types = sorted(set(group["label_type"].dropna().astype(str)))
        lexical_ids = sorted(set((group["label_type"].astype(str) + ":" + group["label"].astype(str)).tolist()))
        signbank_ids = sorted(set(str(int(value)) for value in group["SignBank Reference ID"].dropna().astype(float)))
        asllex_refs = sorted(set(group[group["label_type"].astype(str) == "asllex"]["label"].astype(str)))
        asl_group = asllvd[asllvd["_norm"] == key]
        asllvd_refs = sorted(set((asl_group["Class Label"].astype(str) + ":" + asl_group["entry/variant gloss label"].astype(str)).tolist()))
        historical = exact_by_gloss.get(gloss, [])
        historical_signers = Counter(r["signer_group_id"] for r in historical)
        strict_signer_counts[cid] = historical_signers
        has_suffix_variant = bool(re.search(r"\d+$", gloss))
        if group.empty:
            state = "NO_SEMLEX_MATCH"
            rationale = "No normalized Sem-Lex TRAIN lexical candidate."
        elif historical:
            state = "ACCEPT_METADATA_EXACT"
            rationale = "Prior governed human review accepted exact-target Sem-Lex rows for this AppHear class. Strict projection uses only those reviewed rows."
        elif has_suffix_variant or len(signbank_ids) > 1 or len(asllvd_refs) > 1:
            state = "REVIEW_COMPATIBLE_VARIANT"
            rationale = "A plausible lexical/variant relation exists, but indexed AppHear form or multiple lexical references prevent exact metadata equivalence."
        else:
            state = "REVIEW_FORM_REQUIRED"
            rationale = "English/normalized gloss correspondence exists, but no governed evidence establishes exact AppHear sign-form equivalence."
        qualifications.append({
            "apphear_class_id": cid, "apphear_gloss": gloss,
            "coverage_deficit_level": target["coverage_deficit_level"],
            "semlex_lexical_ids": "|".join(lexical_ids),
            "semlex_glosses": "|".join(sorted(set(group["label"].astype(str)))) if not group.empty else "",
            "semlex_train_clip_count": len(group), "semlex_train_unique_signers": len(signer_counts),
            "semlex_effective_signer_count": round(eff(signer_counts), 6) if eff(signer_counts) else "",
            "semlex_signer_class_slots": len(signer_counts),
            "asllex_references": "|".join(asllex_refs), "signbank_reference_ids": "|".join(signbank_ids),
            "asllvd_references": "|".join(asllvd_refs),
            "historical_review_state": "EXACT_TARGET" if historical else "NONE",
            "historically_reviewed_exact_clips": len(historical),
            "historically_reviewed_exact_signers": len(historical_signers),
            "qualification_state": state, "qualification_rationale": rationale,
            "d4_candidate_clip_count": d4_sem[cid]["candidate_clip_count"],
            "d4_candidate_signer_count": d4_sem[cid]["candidate_signer_count"],
        })
        evidence_rows.append({
            "apphear_class_id": cid, "apphear_gloss": gloss,
            "semlex_lexical_ids": "|".join(lexical_ids), "label_types": "|".join(label_types),
            "asllex_references": "|".join(asllex_refs), "signbank_reference_ids": "|".join(signbank_ids),
            "asllvd_references": "|".join(asllvd_refs),
            "governed_human_review_evidence": f"{len(historical)} exact rows/{len(historical_signers)} signers" if historical else "NONE",
            "evidence_strength": "GOVERNED_HUMAN_EXACT" if historical else "LEXICAL_VARIANT_REFERENCES" if (has_suffix_variant or len(signbank_ids) > 1 or len(asllvd_refs) > 1) else "GLOSS_AND_LEXICON_REFERENCE_ONLY",
            "authoritative_sources": "Sem-Lex metadata|ASL-LEX|ASL SignBank|ASLLVD" if not group.empty else "NONE",
            "qualification_state": state,
        })
    write_csv("semlex_target_class_qualification.csv", qualifications)
    write_csv("semlex_authoritative_lexical_evidence.csv", evidence_rows)

    target_by_id = {int(r["class_id"]): r for r in target_rows}
    strength = {"REVIEW_COMPATIBLE_VARIANT": 0, "REVIEW_FORM_REQUIRED": 1, "UNRESOLVED_METADATA": 2, "NO_SEMLEX_MATCH": 3}
    queue = []
    for row in qualifications:
        if row["qualification_state"] in ("ACCEPT_METADATA_EXACT", "REJECT_METADATA_MISMATCH"):
            continue
        queue.append({
            "priority": "", "apphear_class_id": row["apphear_class_id"], "apphear_gloss": row["apphear_gloss"],
            "coverage_deficit_level": row["coverage_deficit_level"], "semlex_lexical_ids": row["semlex_lexical_ids"],
            "semlex_glosses": row["semlex_glosses"], "potential_new_semlex_signers": row["semlex_train_unique_signers"],
            "potential_candidate_clips": row["semlex_train_clip_count"], "qualification_state": row["qualification_state"],
            "reason_review_required": row["qualification_rationale"], "asllex_reference": row["asllex_references"],
            "signbank_reference": row["signbank_reference_ids"], "asllvd_reference": row["asllvd_references"],
            "official_lightweight_reference_route": "https://asl-lex.org/ | https://aslsignbank.haskins.yale.edu/ | https://www.bu.edu/asllrp/av/dai-asllvd.html",
            "allowed_human_decisions": "ACCEPT_EXACT_FORM|ACCEPT_COMPATIBLE_VARIANT|REJECT_FORM_MISMATCH|UNRESOLVED",
            "human_decision": "",
            "recommended_human_question": f"Does the Sem-Lex lexical candidate '{row['semlex_lexical_ids']}' show the same citation-form ASL sign intended by AppHear class {row['apphear_gloss']}?",
        })
    queue.sort(key=lambda r: (0 if r["coverage_deficit_level"].startswith("CRITICAL") else 1,
                              -int(r["potential_new_semlex_signers"]), strength.get(r["qualification_state"], 9), r["apphear_class_id"]))
    for index, row in enumerate(queue, 1):
        row["priority"] = index
    write_csv("semlex_human_review_queue.csv", queue)

    strict_rows, pending_rows = [], []
    for candidate in qualifications:
        cid = int(candidate["apphear_class_id"])
        target = target_by_id[cid]
        strict_include = candidate["qualification_state"] == "ACCEPT_METADATA_EXACT"
        strict_clips = int(candidate["historically_reviewed_exact_clips"]) if strict_include else 0
        strict_rows.append(projection_row(target, candidate, strict_include, strict_clips, strict_signer_counts[cid], "STRICT"))
        pending_include = candidate["qualification_state"] in ("ACCEPT_METADATA_EXACT", "REVIEW_COMPATIBLE_VARIANT", "REVIEW_FORM_REQUIRED")
        pending_rows.append(projection_row(target, candidate, pending_include, int(candidate["semlex_train_clip_count"]), candidate_signer_counts[cid], "REVIEW_PENDING"))
    write_csv("semlex_strict_coverage_projection.csv", strict_rows)
    write_csv("semlex_review_pending_projection.csv", pending_rows)

    counts = Counter(row["qualification_state"] for row in qualifications)
    strict_included = [row for row in strict_rows if row["included"]]
    pending_included = [row for row in pending_rows if row["included"]]
    strict_summary = {
        "classes": len(strict_included), "candidate_clips": sum(int(r["added_candidate_clips"]) for r in strict_included),
        "signer_class_slots": sum(int(r["added_signer_class_slots"]) for r in strict_included),
        "median_added_signers_per_class": statistics.median([int(r["added_signer_class_slots"]) for r in strict_included]) if strict_included else 0,
        "scope_note": "Only historically human-reviewed exact rows are counted; unreviewed same-gloss rows are excluded.",
    }
    pending_summary = {
        "classes": len(pending_included), "candidate_clips": sum(int(r["added_candidate_clips"]) for r in pending_included),
        "signer_class_slots": sum(int(r["added_signer_class_slots"]) for r in pending_included),
        "median_added_signers_per_class": statistics.median([int(r["added_signer_class_slots"]) for r in pending_included]) if pending_included else 0,
        "scope_note": "Projection only; no review-pending clip is accepted.",
    }
    critical_helped = sum(r["included"] and r["coverage_deficit_level"].startswith("CRITICAL") for r in pending_rows)
    high_helped = sum(r["included"] and r["coverage_deficit_level"].startswith("HIGH") for r in pending_rows)
    acquisition = {
        "classification": "SEMLEX_ACQUISITION_STRONGLY_JUSTIFIED_PENDING_HUMAN_REVIEW",
        "target_classes": 70, "qualification_counts": dict(counts),
        "strict_projection": strict_summary, "review_pending_projection": pending_summary,
        "critical_classes_potentially_helped": critical_helped, "high_classes_potentially_helped": high_helped,
        "archive_size_documented": "UNKNOWN", "full_archive_required": "YES_LIKELY",
        "full_archive_status": "FULL_ARCHIVE_LIKELY_REQUIRED",
        "selective_per_class_download_documented": "NO", "terms_acceptance_required": "YES",
        "storage_requirement": "UNKNOWN_ARCHIVE_SIZE; reserve archive plus filtered working/extraction space only after authorization",
        "future_priority": "NEW_CLASS_SIGNER_COVERAGE_NOT_MAXIMUM_RAW_VIDEO_COUNT",
        "balancing_cap_selected": False,
    }
    write_json("semlex_acquisition_value.json", acquisition)

    weak_signer_threshold = sorted(len(candidate_signer_counts[int(r["class_id"])]) for r in target_rows)[math.ceil(.25 * 70) - 1]
    ms_rows = {int(r["apphear_class_id"]): r for r in read_csv(D4 / "full_vocabulary_external_match_matrix.csv") if r["external_dataset"] == "MS_ASL"}
    fallback = []
    for candidate in qualifications:
        cid = int(candidate["apphear_class_id"])
        weak = int(candidate["semlex_train_unique_signers"]) <= weak_signer_threshold
        state_fallback = candidate["qualification_state"] in ("NO_SEMLEX_MATCH", "REJECT_METADATA_MISMATCH", "UNRESOLVED_METADATA")
        ms = ms_rows[cid]
        if (weak or state_fallback) and ms["compatibility_state"] != "NO_MATCH":
            fallback.append({
                "apphear_class_id": cid, "apphear_gloss": candidate["apphear_gloss"],
                "coverage_deficit_level": candidate["coverage_deficit_level"],
                "semlex_qualification_state": candidate["qualification_state"],
                "semlex_candidate_signers": candidate["semlex_train_unique_signers"],
                "fallback_reason": "SEMLEX_SIGNER_GAIN_AT_OR_BELOW_TARGET_P25" if weak else "SEMLEX_NOT_QUALIFIED",
                "msasl_candidate_clips": ms["candidate_clip_count"], "msasl_candidate_signers": ms["candidate_signer_count"],
                "msasl_compatibility_state": ms["compatibility_state"],
                "planning_only": True,
            })
    write_csv("msasl_fallback_candidates.csv", fallback)
    acquisition["msasl_fallback_weak_signer_threshold_p25"] = weak_signer_threshold
    acquisition["msasl_fallback_class_count"] = len(fallback)
    write_json("semlex_acquisition_value.json", acquisition)

    scope = {
        "SEM_LEX": {"role": "PRIMARY_EXTERNAL_SOURCE", "status": "FORM_QUALIFICATION_COMPLETE_ACQUISITION_NOT_AUTHORIZED"},
        "MS_ASL": {"role": "SECONDARY_FALLBACK_ONLY", "status": "PLANNING_ONLY"},
        "ASLLVD": {"role": "LEXICAL_AND_VARIANT_REFERENCE_ONLY", "signer_coverage_counted": False},
        "ASL_CITIZEN": {"role": "CURRENT_DATASET", "status": "LOW_INCREMENTAL_VALUE"},
        "POPSIGN_V2_1": {"role": "EXCLUDED", "status": "EXCLUDED_FROM_APPHEAR_SUPPLEMENTATION", "project_decision": "POPSIGN_EXCLUDED_MODALITY_MISMATCH", "reason": "MODALITY_MISMATCH_ONE_HAND_RECORDING_CONSTRAINT", "candidate_counts_used": False},
    }
    write_json("external_source_scope_decision.json", scope)

    plan = """# Sem-Lex Raw Access and Future Processing Plan

## Current gate

No acquisition is authorized. Official Sem-Lex documentation states that video access requires agreement to its terms. It does not document selective per-class raw-video download or the archive size; therefore the governed status is `FULL_ARCHIVE_LIKELY_REQUIRED`, with archive/storage size `UNKNOWN` until the official access response is obtained.

Official access route: https://github.com/leekezar/SemLex

## Conditional phases — none executed

1. **Phase A — Authorized access:** after human lexical-form review, accept official terms and obtain the raw archive only with project-lead authorization.
2. **Phase B — Filter:** retain only accepted AppHear lexical IDs/classes; do not use every same-gloss candidate blindly.
3. **Phase C — Lineage:** verify raw-video SHA, Sem-Lex sample ID, signer ID, split, lexical ID, and form-review decision.
4. **Phase D — Perception:** run the frozen DWPose-L backend without threshold or detector changes.
5. **Phase E — Representation:** generate exact `DWPOSE_REPRESENTATION_V2_238 [96,238]` using governed AppHear preprocessing.
6. **Phase F — Integrity:** audit schema, masks, padding, missingness, duplicate/video overlap, signer lineage, class mapping, and train-only eligibility.
7. **Phase G — Training authorization:** only a separately governed decision may merge accepted samples and run supplementation training.

## Future selection principle

Prioritize new class-signer coverage and bounded signer diversity, not maximum raw clip count. No balancing cap is selected in P5-D5.
"""
    (OUT / "semlex_raw_access_plan.md").write_text(plan, encoding="utf-8")

    next_gate = "HUMAN_SEMLEX_LEXICAL_FORM_REVIEW"
    write_json("p5d5_next_gate.json", {"selected_next_gate": next_gate, "executed": False, "human_review_queue_size": len(queue), "raw_acquisition_authorized": False})

    result = f"""# P5-D5 Sem-Lex Form Qualification Result

## Outcome

`{acquisition['classification']}`

The 70-class target was reconstructed directly from P5-D4: 40 critical and 30 high coverage-deficit classes. Sem-Lex has metadata candidates for {70 - counts['NO_SEMLEX_MATCH']} targets. Only prior governed human-reviewed exact rows qualify automatically; English gloss equality was never treated as exact ASL-form evidence.

## Qualification

| State | Classes |
|---|---:|
| ACCEPT_METADATA_EXACT | {counts['ACCEPT_METADATA_EXACT']} |
| REVIEW_COMPATIBLE_VARIANT | {counts['REVIEW_COMPATIBLE_VARIANT']} |
| REVIEW_FORM_REQUIRED | {counts['REVIEW_FORM_REQUIRED']} |
| REJECT_METADATA_MISMATCH | {counts['REJECT_METADATA_MISMATCH']} |
| NO_SEMLEX_MATCH | {counts['NO_SEMLEX_MATCH']} |
| UNRESOLVED_METADATA | {counts['UNRESOLVED_METADATA']} |

Strict projection: {strict_summary['classes']} classes, {strict_summary['candidate_clips']} governed exact clips, {strict_summary['signer_class_slots']} signer-class slots. Review-pending projection: {pending_summary['classes']} classes, {pending_summary['candidate_clips']} metadata candidate clips, {pending_summary['signer_class_slots']} signer-class slots, median {pending_summary['median_added_signers_per_class']} signers/class. Review-pending rows are not accepted.

## Acquisition governance

- Official terms acceptance: required.
- Archive size: not documented in verified public documentation (`UNKNOWN`).
- Selective per-class raw download: not documented.
- Access status: `FULL_ARCHIVE_LIKELY_REQUIRED`.
- Raw video downloaded: no.
- DWPose/V2/training: none.

## Source scope

- Sem-Lex: primary.
- MS-ASL: fallback planning for weak/unqualified Sem-Lex targets only.
- ASLLVD: lexical/variant evidence only; unknown signer coverage is not counted.
- PopSign v2.1: `EXCLUDED_FROM_APPHEAR_SUPPLEMENTATION` because `MODALITY_MISMATCH_ONE_HAND_RECORDING_CONSTRAINT`; no PopSign count contributes to projections.

## Next gate

`{next_gate}` — not executed.
"""
    (OUT / "P5D5_SEMLEX_FORM_REVIEW_RESULT.md").write_text(result, encoding="utf-8")

    source_after = {
        "d4_coverage_deficit_ranking": sha256(D4 / "coverage_deficit_ranking.csv"),
        "d4_current_coverage": sha256(D4 / "current_apphear_class_coverage.csv"),
        "d4_lexical_matrix": sha256(D4 / "lexical_compatibility_matrix.csv"),
        "d4_match_matrix": sha256(D4 / "full_vocabulary_external_match_matrix.csv"),
        "d4_human_queue": sha256(D4 / "human_form_review_queue.csv"),
        "d4_projected_coverage": sha256(D4 / "projected_coverage_by_dataset.csv"),
        "semlex_metadata": sha256(SEMLEX), "historical_semlex_review": sha256(SEMLEX_EXACT),
        "asllvd_metadata": sha256(ASLLVD), "msasl_train_metadata": sha256(MSASL),
        "progress_tracker": sha256(PROGRESS),
    }
    integrity = {
        "passed": source_before == source_after and len(target_rows) == 70,
        "source_hashes_before": source_before, "source_hashes_after": source_after,
        "d4_artifact_hashes_verified": len(d4_hashes),
        "target_classes_derived_automatically_from_d4": True, "target_class_count": len(target_rows),
        "critical_target_count": sum(r["coverage_deficit_level"].startswith("CRITICAL") for r in target_rows),
        "high_target_count": sum(r["coverage_deficit_level"].startswith("HIGH") for r in target_rows),
        "protected_test_accessed": False, "raw_video_downloaded": False,
        "dwpose_extraction": "NONE", "v2_generation": "NONE", "external_merge": False,
        "training_performed": False, "popsign_used": False, "android_modified": False,
        "context_files_modified": False, "progress_tracker_untouched": source_before["progress_tracker"] == source_after["progress_tracker"],
    }
    write_json("p5d5_integrity.json", integrity)

    artifacts = []
    for path in sorted(OUT.iterdir()):
        if path.name == "artifact_hash_manifest.json" or not path.is_file():
            continue
        artifacts.append({"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size})
    code = Path(__file__)
    artifacts.append({"path": str(code.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(code), "bytes": code.stat().st_size, "role": "supporting_code"})
    write_json("artifact_hash_manifest.json", {"algorithm": "SHA-256", "artifacts": artifacts})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["build"])
    args = parser.parse_args()
    if args.command == "build":
        build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
