"""Prepare RU-D5 targeted external-signer supplementation metadata.

This module audits source metadata and creates a review scaffold only. It does
not download videos, run MediaPipe, accept a variant, build training tensors, or
train a model. Public validation/test rows are counted for leakage protection
but are never emitted as AppHear training candidates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METADATA = ROOT / "artifacts/recognition_upgrade/ru_d5/source_metadata"
DEFAULT_OUTPUT = ROOT / "artifacts/recognition_upgrade/ru_d5/external_candidate_01"
DEFAULT_FOUNDATION = ROOT / "artifacts/recognition_upgrade/ru_d3/repair_candidate_01"
TARGETS = ("KNOW", "WHO", "WE", "COME", "LEAVE")
MS_FILES = {
    "train": "MSASL_train.json",
    "val": "MSASL_val.json",
    "test": "MSASL_test.json",
}
ASLLVD_FIELDS = {
    "id": "Video ID number",
    "main": "main entry gloss label",
    "variant": "entry/variant gloss label",
    "occurrence": "occurrence label",
    "clip_start": "start frame of video clip containing the sign (relative to full videos)",
    "clip_end": "end frame of video clip containing the sign (relative to full videos)",
    "sign_start": "start frame of the sign (relative to full videos)",
    "sign_end": "end frame of the sign (relative to full videos)",
    "video": "full video file",
    "class": "Class Label",
}
POPSIGN_V1_VOCAB = {"WHO", "WE"}
MINIMUM_SIGNER_TARGETS = {"KNOW": 3, "WHO": 5, "WE_COME_PAIR": 5, "LEAVE": 5}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _ms_rows(metadata: Path) -> dict[str, list[dict[str, Any]]]:
    root = metadata / "ms_asl/MS-ASL"
    result: dict[str, list[dict[str, Any]]] = {}
    for split, filename in MS_FILES.items():
        path = root / filename
        result[split] = json.loads(path.read_text(encoding="utf-8"))
    return result


def _availability_rows(
    ms: dict[str, list[dict[str, Any]]], asllvd: list[dict[str, str]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for gloss in TARGETS:
        popsign_label = "weus" if gloss == "WE" else gloss.lower()
        present = gloss in POPSIGN_V1_VOCAB
        usable = gloss == "WHO"
        rows.append(
            {
                "source": "POPSIGN_V1",
                "canonical_gloss": gloss,
                "source_label": popsign_label if present else "",
                "train_candidates": "archive_pending" if present else 0,
                "train_signers": "archive_pending" if present else 0,
                "heldout_candidates": "not_downloaded",
                "status": (
                    "TRAIN_ARCHIVE_AVAILABLE"
                    if usable
                    else "UNPAIRED_WE_NOT_ELIGIBLE"
                    if gloss == "WE"
                    else "GLOSS_ABSENT"
                ),
                "notes": (
                    "game/train WHO only; manual AppHear variant review still required"
                    if usable
                    else "PopSign has WE/US but no COME, so it cannot enter the paired pilot"
                    if gloss == "WE"
                    else "not in official PopSign v1 vocabulary"
                ),
            }
        )
    for gloss in TARGETS:
        counts: dict[str, int] = {}
        signer_counts: dict[str, int] = {}
        for split, split_rows in ms.items():
            hits = [row for row in split_rows if str(row.get("text", "")).upper() == gloss]
            counts[split] = len(hits)
            signer_counts[split] = len({str(row.get("signer_id", "")) for row in hits})
        rows.append(
            {
                "source": "MS_ASL",
                "canonical_gloss": gloss,
                "source_label": gloss.lower(),
                "train_candidates": counts["train"],
                "train_signers": signer_counts["train"],
                "heldout_candidates": counts["val"] + counts["test"],
                "status": "METADATA_ONLY_STRICT_REVIEW_REQUIRED",
                "notes": "scraped/unconstrained source; val/test rows permanently excluded",
            }
        )
    for gloss in TARGETS:
        hits = [
            row
            for row in asllvd
            if row[ASLLVD_FIELDS["main"]] == gloss
            or row[ASLLVD_FIELDS["variant"]] == gloss
            or row[ASLLVD_FIELDS["class"]] == gloss
        ]
        variants = sorted({row[ASLLVD_FIELDS["variant"]] for row in hits})
        rows.append(
            {
                "source": "ASLLVD",
                "canonical_gloss": gloss,
                "source_label": "|".join(variants),
                "train_candidates": len(hits),
                "train_signers": "manual_source_mapping_required" if hits else 0,
                "heldout_candidates": "no_AppHear_split_assigned",
                "status": "LEXICAL_BOUNDARY_REFERENCE" if hits else "GLOSS_ABSENT",
                "notes": (
                    "citation-form tokens; exact boundaries/variants; limited signer diversity"
                ),
            }
        )
    for gloss in TARGETS:
        rows.append(
            {
                "source": "SEM_LEX",
                "canonical_gloss": gloss,
                "source_label": "pending_release_metadata",
                "train_candidates": "terms_acceptance_and_archive_pending",
                "train_signers": "pending",
                "heldout_candidates": "must_remain_excluded",
                "status": "ACCESS_BLOCKED_PENDING_USER_TERMS",
                "notes": "inspect native 3:1:1 split after user-authorized download",
            }
        )
    return rows


def _ms_candidates(ms: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(ms["train"]):
        gloss = str(row.get("text", "")).upper()
        if gloss not in TARGETS:
            continue
        signer = f"MSASL-{row.get('signer_id')}"
        rows.append(
            {
                "candidate_id": f"MSASL-TRAIN-{index:05d}",
                "source": "MS_ASL",
                "source_split": "train",
                "canonical_gloss": gloss,
                "source_gloss": row.get("org_text", row.get("text", "")),
                "source_signer_id": signer,
                "source_video_id": row.get("file", ""),
                "source_url": row.get("url", ""),
                "source_start": row.get("start_time", ""),
                "source_end": row.get("end_time", ""),
                "source_variant": "UNREVIEWED",
                "expected_variant": "see_variant_registry",
                "expected_hands": "see_variant_registry",
                "manual_variant_decision": "PENDING",
                "manual_boundary_decision": "PENDING",
                "raw_video_path": "",
                "raw_video_sha256": "",
                "mediapipe_decision": "NOT_RUN",
                "final_decision": "PENDING",
                "rejection_reason": "",
            }
        )
    return rows


def _asllvd_candidates(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        glosses = {
            row[ASLLVD_FIELDS["main"]],
            row[ASLLVD_FIELDS["variant"]],
            row[ASLLVD_FIELDS["class"]],
        }
        gloss = next((target for target in TARGETS if target in glosses), "")
        if not gloss:
            continue
        candidates.append(
            {
                "candidate_id": f"ASLLVD-{row[ASLLVD_FIELDS['id']]}",
                "source": "ASLLVD",
                "source_split": "unassigned_reference",
                "canonical_gloss": gloss,
                "source_gloss": row[ASLLVD_FIELDS["occurrence"]],
                "source_signer_id": "PENDING_FROM_SESSION_METADATA",
                "source_video_id": row[ASLLVD_FIELDS["video"]],
                "source_url": "https://dai.cs.rutgers.edu/dai/s/signbank",
                "source_start": row[ASLLVD_FIELDS["clip_start"]],
                "source_end": row[ASLLVD_FIELDS["clip_end"]],
                "source_variant": row[ASLLVD_FIELDS["variant"]],
                "expected_variant": "see_variant_registry",
                "expected_hands": "see_variant_registry",
                "manual_variant_decision": "PENDING",
                "manual_boundary_decision": "PENDING",
                "raw_video_path": "",
                "raw_video_sha256": "",
                "mediapipe_decision": "NOT_RUN",
                "final_decision": "PENDING",
                "rejection_reason": "",
            }
        )
    return candidates


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty RU-D5 output: {args.output}")
    required = [
        args.metadata / "ms_asl/MS-ASL/MSASL_train.json",
        args.metadata / "ms_asl/MS-ASL/MSASL_val.json",
        args.metadata / "ms_asl/MS-ASL/MSASL_test.json",
        args.metadata / "asllvd_signs_2023_10_23.csv",
        args.foundation / "variant_registry.json",
        args.foundation / "dataset/train.npz",
        args.foundation / "dataset/manifests/train.csv",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing RU-D5 input: {missing}")
    args.output.mkdir(parents=True)
    ms = _ms_rows(args.metadata)
    asllvd_path = args.metadata / "asllvd_signs_2023_10_23.csv"
    asllvd = _read_csv(asllvd_path)
    availability = _availability_rows(ms, asllvd)
    candidates = _ms_candidates(ms) + _asllvd_candidates(asllvd)
    _write_csv(args.output / "source_availability.csv", availability)
    _write_csv(args.output / "candidate_discovery.csv", candidates)
    variant_registry = json.loads(
        (args.foundation / "variant_registry.json").read_text(encoding="utf-8")
    )
    policy = {
        "phase": "RU-D5",
        "scope": "targeted external signer supplementation; no training",
        "foundation": {
            "path": str((args.foundation / "dataset").resolve()),
            "train_sha256": _sha256(args.foundation / "dataset/train.npz"),
            "manifest_sha256": _sha256(args.foundation / "dataset/manifests/train.csv"),
        },
        "feature_contract": [96, 258],
        "target_variants": variant_registry["variants"],
        "minimum_distinct_external_signers": MINIMUM_SIGNER_TARGETS,
        "pilot_selection": {
            "rule": "maximize unique eligible train-split signers before a second clip",
            "per_signer_class_cap_first_pass": 1,
            "we_come": "paired same-source/same-signer rows only",
            "leave_second_clip_exception": (
                "after five unique signers, allow one second clip from two signers "
                "to reach seven"
            ),
            "source_balance": (
                "when two sources qualify, no source may provide more than three "
                "of the first five signer slots"
            ),
        },
        "hard_exclusions": [
            "all public validation/test signers",
            "current AppHear phone signer",
            "alternate or ambiguous variants",
            "invalid/incomplete spans",
            "poor MediaPipe hand coverage",
            "missing required hands",
            "unpaired WE-only supplementation",
        ],
        "production_authorized": False,
        "training_authorized": False,
    }
    _write_json(args.output / "screening_policy.json", policy)
    we_signers = {
        str(row.get("signer_id")) for row in ms["train"] if row.get("text") == "we"
    }
    come_signers = {
        str(row.get("signer_id")) for row in ms["train"] if row.get("text") == "come"
    }
    summary = {
        "phase": "RU-D5",
        "stage": "source_metadata_audit",
        "candidate_rows": len(candidates),
        "candidate_counts": dict(Counter(row["canonical_gloss"] for row in candidates)),
        "ms_asl_train_we_come_paired_signers": sorted(we_signers & come_signers),
        "popsign_eligible_downloads": ["WHO"],
        "popsign_ineligible": {
            "KNOW": "gloss absent",
            "WE_COME": "WE/US exists but COME absent; pair unavailable",
            "LEAVE": "gloss absent and intended target is two-handed",
        },
        "semlex_status": "blocked pending user acceptance of dataset terms/download",
        "metadata_hashes": {
            "ms_train": _sha256(args.metadata / "ms_asl/MS-ASL/MSASL_train.json"),
            "ms_val": _sha256(args.metadata / "ms_asl/MS-ASL/MSASL_val.json"),
            "ms_test": _sha256(args.metadata / "ms_asl/MS-ASL/MSASL_test.json"),
            "asllvd": _sha256(asllvd_path),
        },
        "protected_test_accessed": False,
        "videos_downloaded": 0,
        "features_extracted": 0,
        "accepted_for_training": 0,
        "passed": True,
        "next": "developer downloads PopSign WHO train archive and obtains Sem-Lex access",
    }
    _write_json(args.output / "metadata_audit_summary.json", summary)
    return summary


def check(args: argparse.Namespace) -> dict[str, Any]:
    required = [
        args.output / "source_availability.csv",
        args.output / "candidate_discovery.csv",
        args.output / "screening_policy.json",
        args.output / "metadata_audit_summary.json",
    ]
    errors = [f"missing {path}" for path in required if not path.is_file()]
    if not errors:
        policy = json.loads((args.output / "screening_policy.json").read_text(encoding="utf-8"))
        summary = json.loads(
            (args.output / "metadata_audit_summary.json").read_text(encoding="utf-8")
        )
        if policy.get("training_authorized") is not False:
            errors.append("training must remain unauthorized")
        if summary.get("protected_test_accessed") is not False:
            errors.append("protected test access flag is not false")
        if summary.get("accepted_for_training") != 0:
            errors.append("metadata audit cannot accept training rows")
        candidates = _read_csv(args.output / "candidate_discovery.csv")
        if any(row["source_split"] in {"val", "test"} for row in candidates):
            errors.append("public held-out row leaked into candidate discovery")
    return {
        "output": str(args.output.resolve()),
        "errors": errors,
        "protected_test_accessed": False,
        "passed": not errors,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    prepare_parser.add_argument("--foundation", type=Path, default=DEFAULT_FOUNDATION)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> None:
    args = _parser().parse_args()
    result = prepare(args) if args.command == "prepare" else check(args)
    print(json.dumps(result, indent=2))
    if not result.get("passed", False):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
