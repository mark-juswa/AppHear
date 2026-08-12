"""Search existing sources for E6 negative-context development evidence.

The first supported source is ASL Citizen OOV footage. This utility audits raw
video lineage and coverage only; it does not extract features or train models.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import cv2

CORE_SIGNS = {"GOOD", "HELLO", "SORRY", "HAVE", "KNOW", "THINK", "TAKE", "SELL"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _normalize_gloss(value: str) -> str:
    return "".join(character for character in value.upper() if character.isalnum())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _probe(path: Path) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        return {"decode_status": "failed"}
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    decoded = 0
    for index in sorted({0, max(0, frames // 2), max(0, frames - 1)}):
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        decoded += int(ok and frame is not None)
    capture.release()
    return {
        "decode_status": "ok" if frames > 0 and decoded == 3 else "failed",
        "frame_count": frames,
        "fps": round(fps, 3),
        "width": width,
        "height": height,
        "duration_seconds": round(frames / fps, 3) if fps > 0 else "",
    }


def _round_robin_unique_glosses(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    grouped: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    for row in sorted(rows, key=lambda item: (item["participant_id"], item["video_file"])):
        grouped[row["participant_id"]].append(row)
    participants = sorted(grouped)
    selected: list[dict[str, Any]] = []
    glosses: set[str] = set()
    while len(selected) < count:
        progressed = False
        for participant in participants:
            queue = grouped[participant]
            while queue and queue[0]["canonical_gloss"] in glosses:
                queue.popleft()
            if not queue:
                continue
            row = queue.popleft()
            selected.append(row)
            glosses.add(row["canonical_gloss"])
            progressed = True
            if len(selected) == count:
                break
        if not progressed:
            break
    if len(selected) != count:
        raise ValueError(f"only {len(selected)} distinct-gloss OOV rows available; need {count}")
    return selected


def _candidate_rows(dataset_root: Path) -> list[dict[str, Any]]:
    split_path = dataset_root / "splits" / "train.csv"
    videos_root = dataset_root / "videos"
    rows = []
    for source_row in _read_csv(split_path):
        gloss = _normalize_gloss(source_row["Gloss"])
        path = videos_root / source_row["Video file"]
        if not gloss or gloss in CORE_SIGNS or not path.is_file():
            continue
        rows.append(
            {
                "participant_id": source_row["Participant ID"],
                "video_file": source_row["Video file"],
                "canonical_gloss": gloss,
                "source_gloss": source_row["Gloss"],
                "asl_lex_code": source_row.get("ASL-LEX Code", ""),
                "raw_video_path": str(path.resolve()),
            }
        )
    return rows


def build(args: argparse.Namespace) -> int:
    candidates = _candidate_rows(args.asl_citizen_root)
    selected = _round_robin_unique_glosses(candidates, args.count)
    manifest = []
    for index, row in enumerate(selected, start=1):
        path = Path(row["raw_video_path"])
        manifest.append(
            {
                "row_id": f"asl_oov_{index:04d}",
                "source_dataset": "ASL_CITIZEN",
                "source_split": "train",
                **row,
                "raw_video_sha256": _sha256(path),
                **_probe(path),
                "sample_kind": "oov_sign",
                "negative_subtype": "OOV_SIGN",
                "intended_role": "historical_development_training",
                "fresh_evaluation_eligible": False,
                "label_rationale": (
                    "official non-core ASL Citizen gloss; exact OOV class not trained"
                ),
                "previous_experiment_usage": "ASL Citizen E1-E5 source; not fresh evaluation",
            }
        )

    hashes = [row["raw_video_sha256"] for row in manifest]
    errors = []
    if any(row["decode_status"] != "ok" for row in manifest):
        errors.append("one or more selected OOV videos failed decode probe")
    if len(hashes) != len(set(hashes)):
        errors.append("selected OOV videos contain duplicate raw hashes")
    if len({row["canonical_gloss"] for row in manifest}) != args.count:
        errors.append("selected OOV rows do not have distinct glosses")

    prior = _read_csv(args.prior_coverage)
    coverage = []
    for row in prior:
        updated = dict(row)
        if row["negative_subtype"] == "OOV_SIGN":
            updated["accepted_historical_development_windows"] = args.count
            updated["remaining_volume_gap"] = max(0, int(row["target_windows"]) - args.count)
            updated["decision"] = "asl_citizen_historical_development_reuse"
        coverage.append(updated)

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "asl_citizen_oov_manifest.csv", manifest, list(manifest[0]))
    _write_csv(output / "coverage_after_existing_sources.csv", coverage, list(coverage[0]))
    remaining = sum(int(row["remaining_volume_gap"]) for row in coverage)
    summary = {
        "experiment": "e6_existing_negative_source_search_v1",
        "scope": "existing-source lineage and coverage only; no extraction or modeling",
        "asl_citizen_candidates": len(candidates),
        "selected_oov_rows": len(manifest),
        "selected_unique_glosses": len({row["canonical_gloss"] for row in manifest}),
        "selected_participants": len({row["participant_id"] for row in manifest}),
        "selected_participant_counts": {
            participant: sum(row["participant_id"] == participant for row in manifest)
            for participant in sorted({row["participant_id"] for row in manifest})
        },
        "selected_unique_hashes": len(set(hashes)),
        "decode_ok": sum(row["decode_status"] == "ok" for row in manifest),
        "historical_development_coverage_total": 1000 - remaining,
        "remaining_volume_gap": remaining,
        "fresh_evaluation_coverage": 0,
        "still_missing_subtypes": [
            row["negative_subtype"] for row in coverage if int(row["remaining_volume_gap"]) > 0
        ],
        "errors": errors,
        "passed": not errors,
        "decision": "oov_development_volume_filled_fresh_and_other_context_still_required",
    }
    _write_json(output / "source_search_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if not errors else 1


def check(args: argparse.Namespace) -> int:
    required = [
        "asl_citizen_oov_manifest.csv",
        "coverage_after_existing_sources.csv",
        "source_search_summary.json",
    ]
    errors = [name for name in required if not (args.run_dir / name).is_file()]
    if not errors:
        summary = json.loads((args.run_dir / "source_search_summary.json").read_text())
        if not summary.get("passed"):
            errors.append("source search summary did not pass")
        if summary.get("selected_oov_rows") != 200:
            errors.append("expected 200 selected OOV rows")
        if summary.get("remaining_volume_gap") != 453:
            errors.append("expected remaining volume gap of 453")
        if summary.get("fresh_evaluation_coverage") != 0:
            errors.append("historical ASL Citizen rows must not receive fresh-evaluation credit")
    report = {"run_dir": str(args.run_dir.resolve()), "passed": not errors, "errors": errors}
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build")
    build_parser.add_argument(
        "--asl-citizen-root",
        type=Path,
        default=Path(r"F:\ASL DATASET\ASL CITIZEN\ASL_Citizen"),
    )
    build_parser.add_argument("--count", type=int, default=200)
    build_parser.add_argument(
        "--prior-coverage",
        type=Path,
        default=Path(
            "artifacts/recognition_upgrade/product_core_data_readiness/"
            "e6_negative_reuse_audit_01/coverage_recalculation.csv"
        ),
    )
    build_parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/recognition_upgrade/product_core_data_readiness/"
            "e6_existing_negative_source_search_01"
        ),
    )
    build_parser.set_defaults(func=build)
    check_parser = commands.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.set_defaults(func=check)
    return root


def main() -> int:
    args = parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
