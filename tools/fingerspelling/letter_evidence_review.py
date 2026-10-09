"""Small TRAIN-only review request and label validation; no decoder/model experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.input_evidence import assess
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import verify_raw, verify_source

CONFIG = REPO / "pipeline/config/fingerspelling_letter_review_01.json"
OUT = REPO / "artifacts/fingerspelling_letter_review_01"
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
REQUEST_SCHEMA = "apphear.fingerspelling.letter_review_request.v1"
LABEL_SCHEMA = "apphear.fingerspelling.human_letter_review.v1"


def read(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def select(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    """Metadata-only coverage. Distinct signers; no predictions or perception metrics."""
    pool = [
        r
        for r in rows
        if r["split_role"] == "TRAIN"
        and len(r["normalized_transcript"]) <= config["maximum_transcript_length"]
    ]
    selected: list[dict[str, Any]] = []
    signers: set[str] = set()
    covered: Counter[str] = Counter()
    groups = list(config["stratum_quota"])
    for index in range(config["review_sequence_count"]):
        group = groups[index % len(groups)]
        candidates = [
            r
            for r in pool
            if r["source_stratum"] == group and r["official_signer_id"] not in signers
        ]
        if not candidates:
            raise ValueError("[letter-review/selection] Cannot satisfy signer/stratum policy")

        def key(row: dict[str, Any]) -> tuple[int, int, str]:
            letters = set(row["normalized_transcript"]) - {" "}
            gain = sum(
                max(0, config["metadata_coverage_occurrences"] - covered[c]) for c in letters
            )
            salt = config["selection_salt"] + row["sample_id"]
            tie = hashlib.sha256(salt.encode()).hexdigest()
            return -gain, len(row["normalized_transcript"]), tie

        chosen = min(candidates, key=key)
        selected.append(chosen)
        signers.add(chosen["official_signer_id"])
        covered.update(set(chosen["normalized_transcript"]) - {" "})
    if Counter(r["source_stratum"] for r in selected) != config["stratum_quota"]:
        raise ValueError("[letter-review/selection] Exact stratum quota mismatch")
    if set(covered) != set(ALPHABET):
        raise ValueError(
            "[letter-review/selection] Review request lacks transcript alphabet coverage"
        )
    return selected


def prepare() -> dict[str, Any]:
    policy = read(CONFIG)
    if policy["schema_version"] != "apphear.fingerspelling.letter_review_policy.v1":
        raise ValueError("[letter-review/config] Schema mismatch")
    manifest = REPO / policy["foundation_manifest"]
    if sha256(manifest) != policy["foundation_manifest_sha256"]:
        raise ValueError("[letter-review/manifest] Frozen foundation changed")
    rows = select(read(manifest)["samples"], policy)
    packet: dict[str, Any] = dict(
        schema_version=REQUEST_SCHEMA,
        policy_sha256=sha256(CONFIG),
        manifest_sha256=sha256(manifest),
        training_admitted=False,
        test_accessed=False,
        samples=[],
    )
    for row in rows:
        receipt_path = manifest.parent / "features" / f"{row['sample_id']}.receipt.json"
        receipt = read(receipt_path)
        source = REPO / receipt["source_path"]
        raw_path, raw_receipt = REPO / receipt["raw_path"], REPO / receipt["raw_receipt_path"]
        source_sha = verify_source(source, row)
        raw = verify_raw(raw_path, raw_receipt, row, source_sha)
        if source_sha != receipt["source_sha256"] or sha256(raw_path) != receipt["raw_sha256"]:
            raise ValueError("[letter-review/lineage] Existing feature receipt changed")
        packet["samples"].append(
            dict(
                sample_id=row["sample_id"],
                split_role="TRAIN",
                official_signer_id=row["official_signer_id"],
                source_stratum=row["source_stratum"],
                normalized_transcript=row["normalized_transcript"],
                source_path=str(source.resolve()),
                source_sha256=source_sha,
                raw_path=str(raw_path.resolve()),
                raw_sha256=sha256(raw_path),
                feature_receipt_path=str(receipt_path.resolve()),
                feature_receipt_sha256=sha256(receipt_path),
                frame_indices=raw.frame_index.tolist(),
                timestamps_ms=raw.timestamp_ms.tolist(),
                input_assessment=assess(raw),
                reflection_policy=row["reflection_policy"],
            )
        )
    OUT.mkdir(parents=True, exist_ok=True)
    destination = OUT / "review_request.json"
    if destination.exists() and read(destination) != packet:
        raise ValueError("[letter-review/freeze] Existing request differs; do not overwrite")
    if not destination.exists():
        destination.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    labels = OUT / "human_reviews.json"
    if not labels.exists():
        labels.write_text(
            json.dumps(
                dict(
                    schema_version=LABEL_SCHEMA,
                    request_sha256=sha256(destination),
                    reviews=[
                        dict(
                            sample_id=r["sample_id"],
                            reviewer_id="",
                            review_status="PENDING",
                            labels=[],
                            notes="",
                        )
                        for r in rows
                    ],
                ),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return validate_labels(packet, read(labels), sha256(destination))


def validate_labels(
    request: dict[str, Any], reviews: dict[str, Any], request_sha: str
) -> dict[str, Any]:
    """Reject invented frame indices, unreviewed labels, role leakage and duplicate ranges."""
    if request["schema_version"] != REQUEST_SCHEMA or reviews["schema_version"] != LABEL_SCHEMA:
        raise ValueError("[letter-review/schema] Unsupported schema")
    if reviews["request_sha256"] != request_sha:
        raise ValueError("[letter-review/labels] Request identity mismatch")
    indexed = {r["sample_id"]: r for r in request["samples"]}
    if len(indexed) != len(request["samples"]):
        raise ValueError("[letter-review/identity] Duplicate request source")
    if any(r["split_role"] != "TRAIN" for r in indexed.values()):
        raise ValueError("[letter-review/role] Only official TRAIN review is permitted")
    items = reviews["reviews"]
    if len(items) != len(indexed) or {r["sample_id"] for r in items} != set(indexed):
        raise ValueError("[letter-review/identity] Missing/duplicate/extra reviewed identity")
    labels: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    for review in items:
        source = indexed[review["sample_id"]]
        status = review["review_status"]
        if status not in {"PENDING", "REVIEWED", "UNASSESSABLE"}:
            raise ValueError("[letter-review/status] Unknown review status")
        statuses[status] += 1
        if status != "REVIEWED" and review["labels"]:
            raise ValueError("[letter-review/labels] Non-reviewed labels are forbidden")
        if status == "REVIEWED" and (not review["reviewer_id"].strip() or not review["labels"]):
            raise ValueError("[letter-review/reviewer] Identified human and labels required")
        positions = {frame: index for index, frame in enumerate(source["frame_indices"])}
        previous_end = -1
        for label in review["labels"]:
            letter = label["letter"]
            if len(letter) != 1 or letter not in ALPHABET:
                raise ValueError("[letter-review/target] Only authoritative A-Z labels")
            if letter not in source["normalized_transcript"]:
                raise ValueError(
                    "[letter-review/target] Label absent from authoritative transcript"
                )
            start, end = label["start_frame_index"], label["end_frame_index"]
            if (
                type(start) is not int
                or type(end) is not int
                or start not in positions
                or end not in positions
            ):
                raise ValueError("[letter-review/frame] Actual integer source frames required")
            a, b = positions[start], positions[end]
            if a > b or a <= previous_end:
                raise ValueError("[letter-review/order] Reversed or overlapping label spans")
            if letter in "JZ" and a == b:
                raise ValueError("[letter-review/motion] J/Z require a reviewed temporal span")
            if label["candidate_slot"] not in (0, 1) or type(label["candidate_slot"]) is not int:
                raise ValueError("[letter-review/slot] Explicit Candidate01 slot required")
            if label["crop_semantic_review"] != "TRUSTED_HAND_WITH_REQUIRED_FINGERS":
                raise ValueError("[letter-review/crop] Untrusted crop cannot provide supervision")
            if (
                label["label_source"] != "HUMAN_RGB_REVIEW"
                or label["qualified_fingerspelling_review"] is not True
            ):
                raise ValueError("[letter-review/label-source] Qualified human RGB review required")
            previous_end = b
            labels[letter] += 1
    return dict(
        status="LETTER_REVIEW_PACKET_VALID",
        review_sequences=len(indexed),
        review_statuses=dict(statuses),
        verified_letter_labels=dict(sorted(labels.items())),
        training_admitted=False,
        model_quality_improvement_claim=False,
        test_accessed=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "validate"))
    args = parser.parse_args()
    result = (
        prepare()
        if args.command == "prepare"
        else validate_labels(
            read(OUT / "review_request.json"),
            read(OUT / "human_reviews.json"),
            sha256(OUT / "review_request.json"),
        )
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
