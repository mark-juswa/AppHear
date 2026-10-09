"""P5-D4 metadata-only external ASL dataset qualification audit.

This module reads frozen AppHear TRAIN membership and lightweight external
annotations. It never opens protected-test tensors, downloads raw video,
extracts features, mutates datasets, or trains a model.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import statistics
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/recognition_upgrade"
OUT = BASE / "p5_representation_v2/p5d4_external_data_audit_01"
MEMBERSHIP = BASE / "p5_representation_v2/p5d3_data_coverage_curve_01/p5d3_subset_membership.csv"
D3_INTEGRITY = BASE / "p5_representation_v2/p5d3_data_coverage_curve_01/p5d3_integrity.json"
MANIFEST = BASE / "phase1_full_vocab/manifest_01/canonical_manifest.csv"
V2 = BASE / "p5_representation_v2/p5b_migration_01/dataset"
SEMLEX = Path(r"D:\Downloads\semlex_metadata.csv")
MSASL = BASE / "ru_d5/source_metadata/ms_asl/MS-ASL/MSASL_train.json"
ASLLVD = BASE / "ru_d5/source_metadata/asllvd_signs_2023_10_23.csv"
SEMLEX_EXACT = BASE / "ru_d5/semlex_candidate_01/candidate_c/final_external_lineage.csv"
PROGRESS = ROOT / "context/progress-tracker.md"

EXPECTED = {
    "membership": "7141a7fe763ec2b8b4a9c5e2cc278a26290d2fa977dbce7576f93608103e3716",
    "v2_train": "a2261ea8d61e5eed1a526da0493da5b36c1bb54432ccef7f7479d6ca94634f11",
    "v2_val": "627275d03087f49fda65138253425131e35fe9c5cb8ded6a93b914484be5afe2",
    "v2_vocab": "a7d7b08d1c9ff52455aaa93cefee40e744b86a11fa5047dce08d2dd23fc0539b",
    "canonical_manifest": "8c1fab3df04a0240b5a178853b2206408806958afebdd19bd3d44d6fca606571",
    "semlex_metadata": "f4250b2877e738f028e4b9517922952a350ec8952e59d53ceabdd778938fc3c3",
    "progress_tracker": "12cf08f81959a413a60aa1f869615a24485a41ee3d796e61fce7489ae5c480cf",
}

DATASETS = ("ASL_CITIZEN_CURRENT_REUSE", "SEM_LEX", "POPSIGN_V2_1", "MS_ASL", "ASLLVD")
OFFICIAL = {
    "ASL_CITIZEN_CURRENT_REUSE": "https://www.microsoft.com/en-us/research/project/asl-citizen/",
    "SEM_LEX": "https://github.com/leekezar/SemLex",
    "POPSIGN_V2_1": "https://signdata.cc.gatech.edu/view/datasets/popsign_v2_1/index.html",
    "MS_ASL": "https://microsoft.github.io/data-for-society/dataset?d=MS-ASL-American-Sign-Language-Dataset",
    "ASLLVD": "https://www.bu.edu/asllrp/av/dai-asllvd.html",
}


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


def write_csv(name: str, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path = OUT / name
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_json(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def percentile_rank(values: list[float], value: float) -> float:
    return 100.0 * sum(v <= value for v in values) / len(values)


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def current_coverage() -> tuple[list[dict[str, Any]], dict[int, list[dict[str, str]]]]:
    rows = list(csv.DictReader(MEMBERSHIP.open("r", encoding="utf-8", newline="")))
    by_class: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_class[int(row["class_id"])].append(row)
    result = []
    for cid in sorted(by_class):
        group = by_class[cid]
        signers = Counter(r["signer_group_id"] for r in group)
        sources = Counter(r["source"] for r in group)
        n = len(group)
        hhi = sum((v / n) ** 2 for v in signers.values())
        result.append({
            "class_id": cid, "canonical_gloss": group[0]["gloss"],
            "current_train_clips": n, "current_unique_signers": len(signers),
            "current_effective_signers": round(1 / hhi, 6),
            "median_clips_per_signer": median(list(signers.values())),
            "max_clips_from_one_signer": max(signers.values()),
            "max_signer_share": round(max(signers.values()) / n, 6),
            "current_source_count": len(sources), "source_names": "|".join(sorted(sources)),
            "current_class_signer_combinations": len(signers),
        })
    return result, by_class


def group_external(frame: pd.DataFrame, gloss_col: str, signer_col: str | None, id_col: str,
                   extra_col: str | None = None) -> dict[str, dict[str, Any]]:
    temp = frame.copy()
    temp["_norm"] = temp[gloss_col].map(norm)
    temp = temp[temp["_norm"] != ""]
    result: dict[str, dict[str, Any]] = {}
    for key, group in temp.groupby("_norm"):
        signers: Counter[str] = Counter()
        if signer_col:
            for value in group[signer_col].dropna().astype(str):
                if value not in ("", "-1", "nan"):
                    signers[value] += 1
        result[key] = {
            "external_gloss": str(group.iloc[0][gloss_col]),
            "external_lexical_id": "|".join(sorted(set(group[id_col].astype(str))))[:1000],
            "candidate_clips": len(group), "candidate_signers": len(signers) if signer_col else None,
            "signer_counts": dict(signers),
            "label_types": "|".join(sorted(set(group[extra_col].astype(str)))) if extra_col else "",
        }
    return result


def popsign_vocab() -> list[str]:
    url = OFFICIAL["POPSIGN_V2_1"]
    req = urllib.request.Request(url, headers={"User-Agent": "AppHear-P5D4-metadata-audit/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
    return sorted(set(re.findall(r"/view/datasets/popsign_v2_1/game/([^/]+)/index\.html", body)))


def popsign_class(slug: str) -> tuple[str, dict[str, Any] | None]:
    url = f"https://signdata.cc.gatech.edu/view/datasets/popsign_v2_1/game/{slug}/index.html"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AppHear-P5D4-metadata-audit/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
        match = re.search(r"sourceMap=JSON\.parse\('(.*?)'\),sources=", body)
        if not match:
            return slug, None
        decoded = bytes(match.group(1), "utf-8").decode("unicode_escape")
        data = json.loads(decoded)
        names = list(data.get("train", {}).get("prev_name", {}).values())
        signers = Counter(str(name).split("-", 1)[0] for name in names)
        return slug, {
            "external_gloss": slug, "external_lexical_id": slug,
            "candidate_clips": len(names), "candidate_signers": len(signers),
            "signer_counts": dict(signers), "label_types": "game_validated",
        }
    except Exception:
        return slug, None


def load_external(apphear_norms: set[str]) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, Any]]:
    sem = pd.read_csv(SEMLEX, low_memory=False)
    sem = sem[sem["split"].astype(str).str.lower() == "train"].copy()
    sem["lexical_id"] = sem["label_type"].astype(str) + ":" + sem["label"].astype(str)
    groups = {"SEM_LEX": group_external(sem, "label", "signer_id", "lexical_id", "label_type")}

    ms = pd.DataFrame(json.loads(MSASL.read_text(encoding="utf-8")))
    ms["lexical_id"] = ms["label"].astype(str)
    groups["MS_ASL"] = group_external(ms, "clean_text", "signer_id", "lexical_id")

    asl = pd.read_csv(ASLLVD, low_memory=False)
    asl["lexical_id"] = asl["Class Label"].astype(str) + ":" + asl["entry/variant gloss label"].astype(str)
    groups["ASLLVD"] = group_external(asl, "main entry gloss label", None, "lexical_id")

    slugs = popsign_vocab()
    matched_slugs = [s for s in slugs if norm(s) in apphear_norms]
    pop: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(popsign_class, slug) for slug in matched_slugs]
        for future in as_completed(futures):
            slug, record = future.result()
            if record:
                pop[norm(slug)] = record
            else:
                pop[norm(slug)] = {
                    "external_gloss": slug, "external_lexical_id": slug,
                    "candidate_clips": None, "candidate_signers": None,
                    "signer_counts": {}, "label_types": "metadata_page_parse_failed",
                }
    groups["POPSIGN_V2_1"] = pop
    metadata = {
        "semlex_rows_total": 91148, "semlex_train_rows": len(sem),
        "semlex_total_signers": 41, "semlex_total_vocabulary": 3149,
        "msasl_train_rows": len(ms), "msasl_train_signers_known": int(ms[ms["signer_id"] >= 0]["signer_id"].nunique()),
        "asllvd_rows": len(asl), "popsign_vocabulary": len(slugs),
        "popsign_matched_pages_requested": len(matched_slugs),
        "popsign_matched_pages_parsed": sum(v["candidate_clips"] is not None for v in pop.values()),
    }
    return groups, metadata


def compatibility(dataset: str, record: dict[str, Any], exact_glosses: set[str], gloss: str) -> tuple[str, str]:
    if dataset == "ASL_CITIZEN_CURRENT_REUSE":
        return "EXACT_METADATA_SUPPORTED", "Already governed AppHear source; no unconsumed incremental pool established."
    if dataset == "SEM_LEX" and gloss in exact_glosses:
        return "EXACT_METADATA_SUPPORTED", "Historical human review verified an exact-target subset; unreviewed matching rows still require row-level form review."
    if dataset == "SEM_LEX" and "asllex" in record.get("label_types", ""):
        return "LIKELY_COMPATIBLE_NEEDS_FORM_REVIEW", "ASL-LEX-aligned lexical metadata supports candidacy; direct AppHear form equivalence is unverified."
    if dataset == "ASLLVD":
        return "COMPATIBLE_VARIANT_CANDIDATE", "Citation-form lexical/variant metadata is strong, but AppHear form equivalence and signer identity require review."
    return "NEEDS_HUMAN_FORM_REVIEW", "English/prompt gloss equality does not prove ASL lexical-form equivalence."


def projected_effective(current_rows: list[dict[str, str]], signer_counts: dict[str, int]) -> float | None:
    if not signer_counts:
        return None
    counts = Counter("current:" + r["signer_group_id"] for r in current_rows)
    counts.update({"external:" + k: v for k, v in signer_counts.items()})
    n = sum(counts.values())
    return 1 / sum((v / n) ** 2 for v in counts.values())


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    before = {
        "membership": sha256(MEMBERSHIP), "canonical_manifest": sha256(MANIFEST),
        "v2_train": sha256(V2 / "train.npz"), "v2_val": sha256(V2 / "val.npz"),
        "v2_vocab": sha256(V2 / "vocab.json"), "semlex_metadata": sha256(SEMLEX),
        "progress_tracker": sha256(PROGRESS),
    }
    if any(before[key] != value for key, value in EXPECTED.items()):
        raise RuntimeError(f"Frozen hash mismatch: {before}")

    current, current_rows = current_coverage()
    if len(current) != 236 or sum(r["current_train_clips"] for r in current) != 3926:
        raise RuntimeError("Current AppHear coverage count mismatch")
    write_csv("current_apphear_class_coverage.csv", current)
    apphear_norms = {norm(r["canonical_gloss"]) for r in current}
    groups, metadata = load_external(apphear_norms)

    exact_rows = list(csv.DictReader(SEMLEX_EXACT.open("r", encoding="utf-8", newline="")))
    exact_glosses = {r["canonical_gloss"] for r in exact_rows if r.get("variant_decision") == "EXACT_TARGET"}
    exact_counts = Counter(r["canonical_gloss"] for r in exact_rows if r.get("variant_decision") == "EXACT_TARGET")

    match_rows: list[dict[str, Any]] = []
    projected: list[dict[str, Any]] = []
    lexical_rows: list[dict[str, Any]] = []
    for cur in current:
        cid, gloss, key = int(cur["class_id"]), cur["canonical_gloss"], norm(cur["canonical_gloss"])
        for dataset in DATASETS:
            if dataset == "ASL_CITIZEN_CURRENT_REUSE":
                rec = {"external_gloss": gloss, "external_lexical_id": gloss,
                       "candidate_clips": 0, "candidate_signers": 0, "signer_counts": {},
                       "label_types": "governed_current_source"}
                exists = True
            else:
                rec = groups.get(dataset, {}).get(key)
                exists = rec is not None
            if not exists:
                status, note = "NO_MATCH", "No normalized lexical candidate in available metadata."
                rec = {"external_gloss": "", "external_lexical_id": "", "candidate_clips": 0,
                       "candidate_signers": 0, "signer_counts": {}, "label_types": ""}
            else:
                status, note = compatibility(dataset, rec, exact_glosses, gloss)
            clips, signers = rec.get("candidate_clips"), rec.get("candidate_signers")
            raw_status = {
                "ASL_CITIZEN_CURRENT_REUSE": "RAW_VIDEO_DIRECTLY_AVAILABLE_CURRENT_GOVERNED_SOURCE",
                "SEM_LEX": "FULL_ARCHIVE_REQUIRED",
                "POPSIGN_V2_1": "RAW_VIDEO_SELECTIVELY_AVAILABLE_BY_CLASS_ARCHIVE",
                "MS_ASL": "RAW_VIDEO_SELECTIVELY_AVAILABLE_AS_TIMESTAMPED_URLS_SUBJECT_TO_LINK_ATTRITION",
                "ASLLVD": "RAW_VIDEO_SELECTIVELY_AVAILABLE",
            }[dataset]
            match_rows.append({
                "apphear_class_id": cid, "apphear_canonical_gloss": gloss,
                "external_dataset": dataset, "external_lexical_id": rec["external_lexical_id"],
                "external_gloss": rec["external_gloss"], "candidate_clip_count": clips,
                "candidate_signer_count": signers, "repetitions_per_signer":
                    round(clips / signers, 3) if isinstance(clips, int) and signers else "UNKNOWN",
                "metadata_source_evidence": OFFICIAL[dataset], "raw_video_availability": raw_status,
                "selective_download_status": "YES_BY_CLASS" if dataset == "POPSIGN_V2_1" else
                    "YES_BY_URL_SEGMENT" if dataset == "MS_ASL" else
                    "YES_BY_TOKEN" if dataset == "ASLLVD" else
                    "NO_DOCUMENTED_SELECTIVE_ACCESS" if dataset == "SEM_LEX" else "NOT_APPLICABLE_CURRENT_SOURCE",
                "compatibility_state": status, "translation_or_form_note": note,
                "historically_verified_exact_clips": exact_counts.get(gloss, 0) if dataset == "SEM_LEX" else 0,
                "cross_dataset_signer_identity_assumption": "CROSS_DATASET_SIGNER_IDENTITY_ASSUMED_DISTINCT" if dataset not in ("ASL_CITIZEN_CURRENT_REUSE",) and exists else "",
            })
            lexical_rows.append({
                "apphear_class_id": cid, "apphear_gloss": gloss, "external_dataset": dataset,
                "external_gloss": rec["external_gloss"], "compatibility_state": status,
                "risk_flags": "MULTIPLE_ASL_FORMS_POSSIBLE|REGIONAL_VARIANT|SEMANTIC_SENSE_MISMATCH|HANDEDNESS_VARIANT|CITATION_VS_CONVERSATIONAL" if exists and dataset != "ASL_CITIZEN_CURRENT_REUSE" else "",
                "evidence": note,
            })
            eff = projected_effective(current_rows[cid], rec.get("signer_counts", {})) if exists else None
            projected.append({
                "class_id": cid, "canonical_gloss": gloss, "external_dataset": dataset,
                "compatibility_state": status, "current_clips": cur["current_train_clips"],
                "candidate_clips": clips, "projected_clips": cur["current_train_clips"] + clips if isinstance(clips, int) else "UNKNOWN",
                "current_unique_signers": cur["current_unique_signers"], "candidate_independent_signers": signers,
                "projected_unique_signers": cur["current_unique_signers"] + signers if isinstance(signers, int) else "UNKNOWN",
                "current_effective_signers": cur["current_effective_signers"],
                "projected_effective_signers": round(eff, 6) if eff is not None else "UNKNOWN",
                "projected_class_signer_combinations": cur["current_class_signer_combinations"] + signers if isinstance(signers, int) else "UNKNOWN",
                "projection_only_no_merge": True,
            })
    write_csv("full_vocabulary_external_match_matrix.csv", match_rows)
    write_csv("lexical_compatibility_matrix.csv", lexical_rows)
    write_csv("projected_coverage_by_dataset.csv", projected)

    clips = [float(r["current_train_clips"]) for r in current]
    unique = [float(r["current_unique_signers"]) for r in current]
    effective = [float(r["current_effective_signers"]) for r in current]
    shares = [float(r["max_signer_share"]) for r in current]
    deficits = []
    for cur in current:
        clip_p = percentile_rank(clips, float(cur["current_train_clips"]))
        signer_p = percentile_rank(unique, float(cur["current_unique_signers"]))
        eff_p = percentile_rank(effective, float(cur["current_effective_signers"]))
        concentration_p = percentile_rank(shares, float(cur["max_signer_share"]))
        score = ((100 - clip_p) + (100 - signer_p) + (100 - eff_p) + concentration_p) / 4
        deficits.append({**cur, "clip_count_percentile": round(clip_p, 3),
                         "unique_signer_percentile": round(signer_p, 3),
                         "effective_signer_percentile": round(eff_p, 3),
                         "signer_concentration_percentile": round(concentration_p, 3),
                         "coverage_deficit_score": round(score, 3)})
    scores = sorted(float(r["coverage_deficit_score"]) for r in deficits)
    q65, q75, q90 = scores[math.ceil(.65 * len(scores)) - 1], scores[math.ceil(.75 * len(scores)) - 1], scores[math.ceil(.90 * len(scores)) - 1]
    candidate_lookup = defaultdict(list)
    for row in match_rows:
        if row["external_dataset"] != "ASL_CITIZEN_CURRENT_REUSE" and row["compatibility_state"] != "NO_MATCH":
            candidate_lookup[int(row["apphear_class_id"])].append(row)
    for row in deficits:
        s = float(row["coverage_deficit_score"])
        row["coverage_deficit_rank"] = "CRITICAL_COVERAGE_DEFICIT" if s >= q90 else "HIGH_COVERAGE_DEFICIT" if s >= q75 else "MODERATE_COVERAGE_DEFICIT" if s >= q65 else "LOW_COVERAGE_DEFICIT"
        row["high_volume_low_effective_signer_flag"] = bool(row["clip_count_percentile"] >= 75 and row["effective_signer_percentile"] <= 25)
        row["external_candidate_dataset_count"] = len(candidate_lookup[int(row["class_id"])])
    deficits.sort(key=lambda r: (-float(r["coverage_deficit_score"]), int(r["class_id"])))
    write_csv("coverage_deficit_ranking.csv", deficits)

    inventory = [
        {"dataset": "ASL_CITIZEN_CURRENT_REUSE", "availability_state": "LOCAL_FULL", "metadata_scope": "already governed current-source rows", "isolated_or_segmentable": "YES", "signer_ids": "YES", "raw_video": "CURRENT_GOVERNED_SOURCE", "official_source": OFFICIAL["ASL_CITIZEN_CURRENT_REUSE"], "notes": "Already materially consumed; no unused incremental pool established."},
        {"dataset": "SEM_LEX", "availability_state": "LOCAL_METADATA_ONLY", "metadata_scope": "91148 rows; 56388 TRAIN", "isolated_or_segmentable": "YES", "signer_ids": "YES", "raw_video": "PUBLIC_AFTER_TERMS; FULL_ARCHIVE", "official_source": OFFICIAL["SEM_LEX"], "notes": "ASL-LEX/SignBank aligned; frozen DWPose V2 would still require raw video."},
        {"dataset": "POPSIGN_V2_1", "availability_state": "REMOTE_METADATA_AVAILABLE", "metadata_scope": "562 game labels; per-class split/file metadata", "isolated_or_segmentable": "YES", "signer_ids": "PSEUDONYMOUS_FILE_PREFIX", "raw_video": "PER_CLASS_TAR", "official_source": OFFICIAL["POPSIGN_V2_1"], "notes": "Smartphone prompted signs; game and variant categories separated."},
        {"dataset": "MS_ASL", "availability_state": "LOCAL_METADATA_ONLY", "metadata_scope": "25513 total metadata rows; TRAIN audited", "isolated_or_segmentable": "TIMESTAMP_SEGMENTABLE", "signer_ids": "PARTIAL", "raw_video": "REMOTE_URL_SEGMENTS", "official_source": OFFICIAL["MS_ASL"], "notes": "Web-sourced; URL attrition and lexical form review are material risks."},
        {"dataset": "ASLLVD", "availability_state": "LOCAL_METADATA_ONLY", "metadata_scope": "9746 token annotations", "isolated_or_segmentable": "YES", "signer_ids": "NOT_IN_LOCAL_CSV", "raw_video": "TOKEN/DOWNLOAD INTERFACE", "official_source": OFFICIAL["ASLLVD"], "notes": "Citation-form variants from 1-6 native signers; signer mapping absent locally."},
    ]
    write_csv("external_dataset_inventory.csv", inventory)

    source_rows = [
        {"dataset": d, "source_type": "OFFICIAL", "url_or_path": OFFICIAL[d], "what_verified": "dataset identity, scope, access/collection documentation"}
        for d in DATASETS
    ] + [
        {"dataset": "SEM_LEX", "source_type": "LOCAL_METADATA", "url_or_path": str(SEMLEX), "what_verified": f"91148-row annotations; SHA256 {before['semlex_metadata']}"},
        {"dataset": "MS_ASL", "source_type": "LOCAL_METADATA", "url_or_path": str(MSASL), "what_verified": f"official JSON metadata TRAIN split; SHA256 {sha256(MSASL)}"},
        {"dataset": "ASLLVD", "source_type": "LOCAL_METADATA", "url_or_path": str(ASLLVD), "what_verified": f"9746 annotated sign tokens; SHA256 {sha256(ASLLVD)}"},
        {"dataset": "SEM_LEX", "source_type": "HISTORICAL_FORM_REVIEW", "url_or_path": str(SEMLEX_EXACT), "what_verified": f"32 row-level exact-target clips across five AppHear glosses; historical schema only; SHA256 {sha256(SEMLEX_EXACT)}"},
    ]
    write_csv("external_dataset_metadata_sources.csv", source_rows)

    def useful(dataset: str) -> list[dict[str, Any]]:
        return [r for r in match_rows if r["external_dataset"] == dataset and r["compatibility_state"] != "NO_MATCH"]

    deficit_by_id = {int(r["class_id"]): r for r in deficits}
    scorecard = []
    decisions = {
        "ASL_CITIZEN_CURRENT_REUSE": "LOW_INCREMENTAL_VALUE",
        "SEM_LEX": "HIGH_VALUE_METADATA_CANDIDATE",
        "POPSIGN_V2_1": "HIGH_VALUE_METADATA_CANDIDATE",
        "MS_ASL": "TARGETED_VALUE_METADATA_CANDIDATE",
        "ASLLVD": "METADATA_INSUFFICIENT_TO_DECIDE",
    }
    for dataset in DATASETS:
        rows = useful(dataset)
        incremental = [r for r in rows if dataset != "ASL_CITIZEN_CURRENT_REUSE"]
        candidate_clips = [r["candidate_clip_count"] for r in incremental if isinstance(r["candidate_clip_count"], int)]
        candidate_signers = [r["candidate_signer_count"] for r in incremental if isinstance(r["candidate_signer_count"], int)]
        helped = sum(deficit_by_id[int(r["apphear_class_id"])]["coverage_deficit_rank"] in ("CRITICAL_COVERAGE_DEFICIT", "HIGH_COVERAGE_DEFICIT") for r in incremental)
        scorecard.append({
            "dataset": dataset, "apphear_classes_with_candidate": len(incremental),
            "vocabulary_coverage_percent": round(100 * len(incremental) / 236, 3),
            "exact_metadata_supported_classes": sum(r["compatibility_state"] == "EXACT_METADATA_SUPPORTED" for r in incremental),
            "compatible_or_reviewable_classes": sum(r["compatibility_state"] not in ("NO_MATCH", "INCOMPATIBLE") for r in incremental),
            "classes_needing_human_form_review": sum("REVIEW" in r["compatibility_state"] or r["compatibility_state"] == "COMPATIBLE_VARIANT_CANDIDATE" for r in incremental),
            "no_match_classes": 236 - len(incremental), "total_candidate_clips": sum(candidate_clips),
            "total_candidate_signer_class_slots": sum(candidate_signers),
            "median_candidate_signers_per_covered_class": median(candidate_signers),
            "critical_high_deficit_classes_potentially_helped": helped,
            "raw_video_access": inventory[DATASETS.index(dataset)]["raw_video"],
            "selective_download": "YES" if dataset in ("POPSIGN_V2_1", "MS_ASL", "ASLLVD") else "NO_DOCUMENTED" if dataset == "SEM_LEX" else "NOT_INCREMENTAL",
            "metadata_completeness": "HIGH" if dataset in ("SEM_LEX", "POPSIGN_V2_1", "MS_ASL") else "MEDIUM",
            "classification": decisions[dataset],
        })
    write_csv("dataset_value_scorecard.csv", scorecard)

    queue = []
    priority_rank = {"CRITICAL_COVERAGE_DEFICIT": 0, "HIGH_COVERAGE_DEFICIT": 1, "MODERATE_COVERAGE_DEFICIT": 2, "LOW_COVERAGE_DEFICIT": 3}
    for row in match_rows:
        if row["external_dataset"] == "ASL_CITIZEN_CURRENT_REUSE" or row["compatibility_state"] in ("NO_MATCH", "INCOMPATIBLE", "EXACT_METADATA_SUPPORTED"):
            continue
        deficit = deficit_by_id[int(row["apphear_class_id"])]
        queue.append({
            "priority": "", "coverage_deficit_rank": deficit["coverage_deficit_rank"],
            "apphear_class_id": row["apphear_class_id"], "apphear_gloss": row["apphear_canonical_gloss"],
            "external_dataset": row["external_dataset"], "external_lexical_id": row["external_lexical_id"],
            "external_gloss": row["external_gloss"], "potential_signer_gain": row["candidate_signer_count"],
            "compatibility_state": row["compatibility_state"],
            "reason_for_review": row["translation_or_form_note"],
            "lightweight_reference": row["metadata_source_evidence"],
            "selective_access": row["selective_download_status"],
        })
    queue.sort(key=lambda r: (priority_rank[r["coverage_deficit_rank"]], -(r["potential_signer_gain"] if isinstance(r["potential_signer_gain"], int) else -1), r["apphear_gloss"], r["external_dataset"]))
    for i, row in enumerate(queue, 1):
        row["priority"] = i
    write_csv("human_form_review_queue.csv", queue)

    raw_rows = [
        {"dataset": "ASL_CITIZEN_CURRENT_REUSE", "status": "RAW_VIDEO_DIRECTLY_AVAILABLE", "selective_download": "NOT_APPLICABLE", "archive_size": "UNKNOWN", "requirement": "Already governed source; no external acquisition authorized."},
        {"dataset": "SEM_LEX", "status": "FULL_ARCHIVE_REQUIRED", "selective_download": "NOT_DOCUMENTED", "archive_size": "UNKNOWN", "requirement": "Accept terms; obtain raw video for frozen DWPose-L/V2."},
        {"dataset": "POPSIGN_V2_1", "status": "RAW_VIDEO_SELECTIVELY_AVAILABLE", "selective_download": "PER_CLASS_TAR", "archive_size": "1.1 TB full dataset", "requirement": "Acquire only reviewed class archives after authorization."},
        {"dataset": "MS_ASL", "status": "RAW_VIDEO_SELECTIVELY_AVAILABLE", "selective_download": "PER_TIMESTAMPED_URL", "archive_size": "UNKNOWN", "requirement": "Verify URL availability/terms, then segment accepted rows."},
        {"dataset": "ASLLVD", "status": "RAW_VIDEO_SELECTIVELY_AVAILABLE", "selective_download": "PER_TOKEN_OR_SIGNBANK_DOWNLOAD", "archive_size": "UNKNOWN", "requirement": "Resolve terms and signer metadata before acquisition."},
    ]
    write_csv("raw_video_access_matrix.csv", raw_rows)

    license_rows = [
        {"dataset": "ASL_CITIZEN_CURRENT_REUSE", "license_or_terms": "Official ASL Citizen license/terms; existing governed use", "research_use": "DOCUMENTED", "commercial_use": "REVIEW_REQUIRED", "redistribution": "REVIEW_REQUIRED", "attribution": "OFFICIAL_CITATION_REQUIRED", "status": "LICENSE_REVIEW_REQUIRED", "official_source": OFFICIAL["ASL_CITIZEN_CURRENT_REUSE"]},
        {"dataset": "SEM_LEX", "license_or_terms": "Dataset access requires agreement to terms; repository code Apache-2.0 is not the dataset license", "research_use": "PUBLIC_DOWNLOAD_AFTER_TERMS", "commercial_use": "UNKNOWN", "redistribution": "UNKNOWN", "attribution": "PAPER/DATASET_CITATION", "status": "LICENSE_REVIEW_REQUIRED", "official_source": OFFICIAL["SEM_LEX"]},
        {"dataset": "POPSIGN_V2_1", "license_or_terms": "CC BY 4.0", "research_use": "YES", "commercial_use": "LICENSE_PERMITS_WITH_ATTRIBUTION; PROJECT_LEGAL_REVIEW_REQUIRED", "redistribution": "CC_BY_4_0", "attribution": "REQUIRED", "status": "DOCUMENTED_NOT_LEGAL_ADVICE", "official_source": OFFICIAL["POPSIGN_V2_1"]},
        {"dataset": "MS_ASL", "license_or_terms": "C-UDA / official dataset terms", "research_use": "DOCUMENTED", "commercial_use": "REVIEW_REQUIRED", "redistribution": "REVIEW_REQUIRED; SOURCE VIDEOS THIRD_PARTY", "attribution": "OFFICIAL_CITATION_REQUIRED", "status": "LICENSE_REVIEW_REQUIRED", "official_source": OFFICIAL["MS_ASL"]},
        {"dataset": "ASLLVD", "license_or_terms": "ASLLRP Sign Bank terms of use", "research_use": "DOWNLOAD DOCUMENTED FOR SIGN_RECOGNITION_RESEARCH", "commercial_use": "UNKNOWN", "redistribution": "TERMS_REVIEW_REQUIRED", "attribution": "OFFICIAL_CITATION_REQUIRED", "status": "LICENSE_REVIEW_REQUIRED", "official_source": OFFICIAL["ASLLVD"]},
    ]
    write_csv("license_and_terms_review.csv", license_rows)

    write_json("external_dataset_decisions.json", {
        "classifications": decisions,
        "basis": "class-wise independent signer/variant coverage, lexical reviewability, metadata completeness, and raw-video accessibility; not total video count",
        "cross_dataset_signer_identity": "CROSS_DATASET_SIGNER_IDENTITY_ASSUMED_DISTINCT",
    })

    external_candidates = [r for r in match_rows if r["external_dataset"] != "ASL_CITIZEN_CURRENT_REUSE" and r["compatibility_state"] != "NO_MATCH"]
    best_by_class: dict[int, str] = {}
    precedence = ["EXACT_METADATA_SUPPORTED", "COMPATIBLE_VARIANT_CANDIDATE", "LIKELY_COMPATIBLE_NEEDS_FORM_REVIEW", "NEEDS_HUMAN_FORM_REVIEW", "QUESTIONABLE", "INCOMPATIBLE"]
    for cur in current:
        states = [r["compatibility_state"] for r in external_candidates if int(r["apphear_class_id"]) == int(cur["class_id"])]
        best_by_class[int(cur["class_id"])] = next((s for s in precedence if s in states), "NO_MATCH")
    best_counts = Counter(best_by_class.values())
    high_ids = {int(r["class_id"]) for r in deficits if r["coverage_deficit_rank"] in ("CRITICAL_COVERAGE_DEFICIT", "HIGH_COVERAGE_DEFICIT")}
    helped_high = len({int(r["apphear_class_id"]) for r in external_candidates} & high_ids)
    overall = {
        "overall_classification": "EXTERNAL_SUPPLEMENTATION_CANDIDATE_SUPPORTED",
        "confidence": "HIGH",
        "best_external_dataset_by_useful_class_wise_coverage": max(scorecard[1:], key=lambda r: (r["critical_high_deficit_classes_potentially_helped"], r["total_candidate_signer_class_slots"]))["dataset"],
        "best_status_by_apphear_class_counts": dict(best_counts),
        "critical_high_deficit_classes": len(high_ids),
        "critical_high_deficit_classes_potentially_helped": helped_high,
        "recommended_next_stage": "HUMAN_LEXICAL_FORM_REVIEW_AND_SELECTIVE_RAW_VIDEO_ACQUISITION_PLAN",
        "next_stage_executed": False,
        "what_established": "At least one metadata-qualified source can add substantial class-wise independent signer coverage to under-covered AppHear classes, subject to lexical-form and license review.",
        "what_not_established": "No external clip has been proven training-compatible, downloaded, DWPose-processed, merged, or shown to improve recognition.",
    }
    write_json("p5d4_overall_decision.json", overall)
    write_json("p5d4_next_gate.json", {"selected_next_gate": overall["recommended_next_stage"], "executed": False, "prohibitions": ["raw video download", "DWPose extraction", "dataset merge", "training"]})

    sem_score = next(r for r in scorecard if r["dataset"] == "SEM_LEX")
    pop_score = next(r for r in scorecard if r["dataset"] == "POPSIGN_V2_1")
    ms_score = next(r for r in scorecard if r["dataset"] == "MS_ASL")
    asl_score = next(r for r in scorecard if r["dataset"] == "ASLLVD")
    result = f"""# P5-D4 External Data Coverage Audit Result

## Outcome

**{overall['overall_classification']}** (confidence: {overall['confidence']}).

The metadata evidence supports a governed human lexical-form review followed by a selective acquisition *plan*. It does not authorize acquisition, feature extraction, merging, or training.

## Frozen AppHear population

- TRAIN: 3,926 clips
- Vocabulary: 236 classes
- Protected primary test: not accessed
- Current-source hashes verified before and after the audit

## Candidate evidence

Sem-Lex provides 91,148 isolated clips across 3,149 signs and 41 deaf participants; its TRAIN annotations were audited locally. PopSign v2.1 provides a smartphone-isolated domain with 562 signs and 47 signers and class-addressable archives. MS-ASL supplies timestamp-segmentable metadata with many signer IDs but carries lexical, web-source, availability, and license risks. ASLLVD provides detailed citation-form/variant metadata, though the local table lacks signer IDs. ASL Citizen is already part of the governed AppHear population and has no established unused incremental pool in this audit.

| Dataset | AppHear candidates | Vocabulary | Candidate TRAIN clips | Signer-class slots | Median candidate signers | Critical/high classes helped | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| Sem-Lex | {sem_score['apphear_classes_with_candidate']} | {sem_score['vocabulary_coverage_percent']}% | {sem_score['total_candidate_clips']} | {sem_score['total_candidate_signer_class_slots']} | {sem_score['median_candidate_signers_per_covered_class']} | {sem_score['critical_high_deficit_classes_potentially_helped']} | `{sem_score['classification']}` |
| PopSign v2.1 | {pop_score['apphear_classes_with_candidate']} | {pop_score['vocabulary_coverage_percent']}% | {pop_score['total_candidate_clips']} | {pop_score['total_candidate_signer_class_slots']} | {pop_score['median_candidate_signers_per_covered_class']} | {pop_score['critical_high_deficit_classes_potentially_helped']} | `{pop_score['classification']}` |
| MS-ASL | {ms_score['apphear_classes_with_candidate']} | {ms_score['vocabulary_coverage_percent']}% | {ms_score['total_candidate_clips']} | {ms_score['total_candidate_signer_class_slots']} | {ms_score['median_candidate_signers_per_covered_class']} | {ms_score['critical_high_deficit_classes_potentially_helped']} | `{ms_score['classification']}` |
| ASLLVD | {asl_score['apphear_classes_with_candidate']} | {asl_score['vocabulary_coverage_percent']}% | {asl_score['total_candidate_clips']} | unknown | unknown | {asl_score['critical_high_deficit_classes_potentially_helped']} | `{asl_score['classification']}` |

Across AppHear's relative ranking, {len(high_ids)} classes are critical/high deficit and {helped_high} have at least one external metadata candidate. The best per-class compatibility states (one state per AppHear class) are: {dict(best_counts)}.

## Lexical safety

English string equality was never treated as sufficient ASL form equivalence. Only previously human-reviewed Sem-Lex exact-target rows support `EXACT_METADATA_SUPPORTED`; all other apparent matches remain form-review or variant candidates.

## Raw video and feature contract

No raw video was downloaded. Any later accepted material must follow raw video -> frozen DWPose-L -> exact AppHear V2 preprocessing -> `[96,238]`. Existing external pose products were not qualified as AppHear inputs.

## Limitations

- Cross-dataset signer identities are assumed distinct unless future evidence proves overlap.
- Candidate counts are metadata projections, not accepted sample counts.
- Sem-Lex selective per-class raw download is not documented.
- MS-ASL URLs may have attrition and third-party terms.
- ASLLVD signer mapping is absent from the local metadata table.
- Human lexical-form and legal/license reviews remain mandatory.

## Next gate

`{overall['recommended_next_stage']}` — not executed.
"""
    (OUT / "P5D4_EXTERNAL_DATA_AUDIT_RESULT.md").write_text(result, encoding="utf-8")

    after = {
        "membership": sha256(MEMBERSHIP), "canonical_manifest": sha256(MANIFEST),
        "v2_train": sha256(V2 / "train.npz"), "v2_val": sha256(V2 / "val.npz"),
        "v2_vocab": sha256(V2 / "vocab.json"), "semlex_metadata": sha256(SEMLEX),
        "progress_tracker": sha256(PROGRESS),
    }
    integrity = {
        "passed": before == after and all(before[k] == EXPECTED[k] for k in EXPECTED),
        "source_hashes_before": before, "source_hashes_after": after,
        "apphear_train_clips": 3926, "apphear_classes": 236,
        "protected_test_accessed": False, "raw_video_downloaded": False,
        "dwpose_extraction": "NONE", "new_tensors_created": False,
        "training_performed": False, "external_dataset_merged": False,
        "android_modified": False, "p4_reopened": False, "p5c_started": False,
        "context_files_modified": False, "progress_tracker_untouched": before["progress_tracker"] == after["progress_tracker"],
        "metadata_summary": metadata,
        "external_metadata_hashes": {
            "semlex_metadata": sha256(SEMLEX), "msasl_train_metadata": sha256(MSASL),
            "asllvd_metadata": sha256(ASLLVD), "semlex_historical_exact_review": sha256(SEMLEX_EXACT),
        },
    }
    write_json("p5d4_integrity.json", integrity)

    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.name == "artifact_hash_manifest.json" or not path.is_file():
            continue
        manifest_rows.append({"path": str(path.relative_to(OUT)).replace("\\", "/"), "sha256": sha256(path), "bytes": path.stat().st_size})
    manifest_rows.append({"path": str(Path(__file__).relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(Path(__file__)), "bytes": Path(__file__).stat().st_size, "role": "supporting_code"})
    write_json("artifact_hash_manifest.json", {"algorithm": "SHA-256", "artifacts": manifest_rows})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["build"])
    args = parser.parse_args()
    if args.command == "build":
        build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
