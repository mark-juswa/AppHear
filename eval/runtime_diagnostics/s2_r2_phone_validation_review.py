"""Blinded six-attempt temporal review on a distinct S2-R2 phone validation session."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics import s2_r2_phone_positive_temporal_review as review  # noqa: E402

BASE = (
    ROOT
    / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
    / "s2_r2_phone_deployment_and_independent_validation_01"
)
ATTEMPTS = (
    (1, "HELLO", "UNTOUCHED_VALIDATION"),
    (2, "HELLO", "UNTOUCHED_VALIDATION"),
    (3, "HOME", "UNTOUCHED_VALIDATION"),
    (4, "HOME", "UNTOUCHED_VALIDATION"),
    (5, "TABLE", "UNTOUCHED_VALIDATION"),
    (6, "TABLE", "UNTOUCHED_VALIDATION"),
)


def configure(session: Path) -> Path:
    output = BASE / session.name / "blinded_human_review"
    review.MILESTONE = "S2_R2_PHONE_DEPLOYMENT_AND_INDEPENDENT_VALIDATION_01"
    review.SESSION_ID = session.name
    review.SESSION_ROOT = session.resolve()
    review.OUTPUT_ROOT = output
    review.REVIEW_MANIFEST = output / "phone_positive_review_manifest.json"
    review.ANNOTATIONS = output / "phone_positive_temporal_annotations.json"
    review.SELECTED_ATTEMPTS = ATTEMPTS
    review.TABLE_006_EXCLUDED_FOR_WEAK_PERCEPTION_SUPPORT = False
    review.TOOL_VERSION = "s2-r2-independent-phone-review-v1"
    return output


def _segments(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    labels = {
        "PRE_IDLE": "PRE",
        "ACTIVE_SIGN": "ACTIVE",
        "POST_RECOVERY": "POST",
        "IGNORED": "UNCERTAIN_EXCLUDE",
    }
    result: list[dict[str, object]] = []
    for row in sorted(rows, key=lambda item: int(item["record_index"])):
        index = int(row["record_index"])
        label = labels[row["state_name"]]
        if result and result[-1]["label"] == label and result[-1]["end_index"] == index - 1:
            result[-1]["end_index"] = index
        else:
            result.append({"start_index": index, "end_index": index, "label": label})
    return result


def finalize_linkage(session: Path, output: Path, *, distinct_signer: bool) -> Path:
    linkage_path = session / "s2_exact_parity/linkage.csv"
    with linkage_path.open(encoding="utf-8", newline="") as stream:
        linkage = list(csv.DictReader(stream))
    capture_timestamps = [float(row["timestamp_ms"]) for row in linkage]
    if any(
        right <= left
        for left, right in zip(capture_timestamps, capture_timestamps[1:], strict=False)
    ):
        raise ValueError("S2_R2_REVIEW_NONCHRONOLOGICAL_CAPTURE_TIMESTAMPS")
    with (output / "phone_positive_observation_labels.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream))
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    used_indices: set[int] = set()
    for row in rows:
        source_ms = int(row["source_timestamp_ns"]) / 1_000_000.0
        matches = [
            int(capture["record_index"])
            for capture, timestamp_ms in zip(linkage, capture_timestamps, strict=True)
            if abs(timestamp_ms - source_ms) <= 0.001
        ]
        if len(matches) != 1:
            raise ValueError("S2_R2_REVIEW_VISUAL_TENSOR_LINKAGE_MISSING")
        record_index = matches[0]
        if record_index in used_indices:
            raise ValueError("S2_R2_REVIEW_DUPLICATE_TENSOR_LINKAGE")
        used_indices.add(record_index)
        row["record_index"] = str(record_index)
        grouped[int(row["attempt_ordinal"])].append(row)
    if sorted(grouped) != list(range(1, 7)):
        raise ValueError("S2_R2_REVIEW_ATTEMPTS_MISSING")
    summary = json.loads(
        (output / "phone_positive_temporal_review_summary.json").read_text(encoding="utf-8")
    )
    summary_by_ordinal = {
        int(item["attempt_id"].split("_")[-1]): item for item in summary["attempt_summaries"]
    }
    result = {
        "schema": "apphear.s2_r2.independent_phone_human_review.v1",
        "session_id": session.name,
        "reviewer_blinded_to_s2_output": True,
        "distinct_signer_attested_from_fit_and_checkpoint_selection": distinct_signer,
        "attempts": [
            {
                "attempt_id": ordinal,
                "gloss": gloss,
                "ambiguous": bool(summary_by_ordinal[ordinal]["ambiguous"]),
                "segments": _segments(grouped[ordinal]),
            }
            for ordinal, gloss, _ in ATTEMPTS
        ],
        "confirmed_non_sign_intervals": [],
        "non_sign_review_pending": True,
        "training_authorized": False,
    }
    path = output / "validation_human_review.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "serve", "finalize"))
    parser.add_argument("session", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8771)
    parser.add_argument("--attest-distinct-signer", action="store_true")
    args = parser.parse_args()
    session = args.session.resolve()
    output = configure(session)
    if args.command == "prepare":
        prepared = review.prepare(output)
        print(
            json.dumps(
                {
                    "status": "S2_R2_BLINDED_REVIEW_PREPARED",
                    "manifest": str(prepared["manifest_path"]),
                    "attempts": len(prepared["attempts"]),
                },
                indent=2,
            )
        )
    elif args.command == "serve":
        review.serve(output, args.host, args.port, True)
    else:
        if not args.attest_distinct_signer:
            parser.error("--attest-distinct-signer requires explicit human split-role confirmation")
        summary = review.finalize(output)
        linked = finalize_linkage(session, output, distinct_signer=True)
        print(
            json.dumps(
                {
                    "status": "S2_R2_BLINDED_REVIEW_FINALIZED",
                    "summary": summary,
                    "linked_review": str(linked),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
