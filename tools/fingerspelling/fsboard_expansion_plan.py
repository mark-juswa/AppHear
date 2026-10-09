"""Metadata-only frozen expansion plan; no downloader, extraction or model invocation."""

from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

from pipeline.fingerspelling.adapter import CONFIG, identity, sha256
from pipeline.fingerspelling.sequence_manifest import (
    MANIFEST_SCHEMA,
    REPO,
    read_metadata,
    record,
    select_balanced,
    summary,
    target_ids,
    write_batch_plan,
)

CONFIG_PATH = REPO / "pipeline/config/fingerspelling_expansion_4096_01.json"
SETTINGS = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
BASE = REPO / SETTINGS["foundation_path"]
OUTPUT = REPO / SETTINGS["output_path"]


def serialized(value: Any) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(serialized(value)).hexdigest()


def frozen_write(path: Path, value: Any) -> None:
    data = serialized(value)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"[fsboard/expansion] Frozen artifact differs: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def foundation() -> dict[str, Any]:
    for path, expected in [
        (BASE / "tranche_manifest.json", SETTINGS["foundation_manifest_sha256"]),
        (BASE / "dev_phrase_policy.json", SETTINGS["dev_phrase_policy_sha256"]),
        (REPO / "pipeline/fingerspelling/sequence_manifest.py", SETTINGS["selector_source_sha256"]),
        (REPO / "tools/fingerspelling/foundation.py", SETTINGS["foundation_runner_sha256"]),
    ]:
        if sha256(path) != expected:
            raise ValueError(f"[fsboard/expansion] Governing identity changed: {path}")
    result: dict[str, Any] = json.loads((BASE / "tranche_manifest.json").read_text())
    if result["schema_version"] != MANIFEST_SCHEMA or result["adapter"] != identity():
        raise ValueError("[fsboard/expansion] Frozen schema/adapter mismatch")
    if SETTINGS["batch_sequences"] != CONFIG["batch_sequences"]:
        raise ValueError("[fsboard/expansion] Existing bounded-batch contract differs")
    return result


def manifest(base: dict[str, Any], samples: list[dict[str, Any]], cohort: str) -> dict[str, Any]:
    return {
        **{k: copy.deepcopy(v) for k, v in base.items() if k not in {"samples", "summary"}},
        "expansion_cohort": cohort,
        "selection_config_path": CONFIG_PATH.relative_to(REPO).as_posix(),
        "selection_config_sha256": sha256(CONFIG_PATH),
        "evaluation_usage": "FINAL_CONFIRMATION_ONLY" if cohort == "DEV_B" else "TRAIN_ONLY",
        "samples": samples,
        "summary": summary(samples),
    }


def documents() -> dict[str, dict[str, Any]]:
    base = foundation()
    rows, sources = read_metadata()  # Existing authorized metadata policy; never TEST RGB.
    if sources != base["metadata_sources"]:
        raise ValueError("[fsboard/expansion] Metadata identity mismatch")
    old = [r for r in base["samples"] if r["split_role"] == "TRAIN"]
    dev_a = [r for r in base["samples"] if r["split_role"] == "DEV"]
    forced = {r["filename"] for r in old}
    protected_md5 = {r["clipFileMd5"] for r in rows if r["role"] == "PROTECTED_TEST"}
    used_md5 = {r["official_md5"] for r in dev_a}
    chosen: list[dict[str, Any]] = []
    for group, quota in SETTINGS["train_stratum_quota"].items():
        pool = [
            r
            for r in rows
            if r["role"] == "TRAIN"
            and r["group"] == group
            and r["clipFileMd5"] not in protected_md5 | used_md5
        ]
        selected = select_balanced(pool, quota, forced)
        chosen.extend(record(r) for r in selected)
        used_md5.update(r["clipFileMd5"] for r in selected)
    old_ids = {r["sample_id"] for r in old}
    additions = [r for r in chosen if r["sample_id"] not in old_ids]
    # Preserve every original row and its order, not just its ID/transcript.
    train = copy.deepcopy(old) + additions
    policy = json.loads((BASE / "dev_phrase_policy.json").read_text())
    excluded = set(policy["excluded_dev_sample_ids"])
    dev_a_ids = {r["sample_id"] for r in dev_a}
    allowed_dev = [
        r
        for r in rows
        if r["role"] == "DEV"
        and record(r)["sample_id"] not in excluded | dev_a_ids
        and r["clipFileMd5"] not in protected_md5 | used_md5
    ]
    dev_b = [record(r) for r in select_balanced(allowed_dev, SETTINGS["dev_b_sequences"], set())]
    return {
        "train4096_manifest.json": manifest(base, train, "TRAIN_4096"),
        "train_additions/tranche_manifest.json": manifest(base, additions, "TRAIN_ADDITIONS"),
        "dev_b/tranche_manifest.json": manifest(base, dev_b, "DEV_B"),
        "dev_a_reference.json": {
            "schema_version": "apphear.fsboard.frozen_dev_a_reference.v1",
            "foundation_manifest_path": (BASE / "tranche_manifest.json")
            .relative_to(REPO)
            .as_posix(),
            "foundation_manifest_sha256": SETTINGS["foundation_manifest_sha256"],
            "sample_ids": [r["sample_id"] for r in dev_a],
            "usage": "UNCHANGED_EXISTING_FRAMEWORK_HISTORICAL_SELECTION_AND_COMPARISON",
        },
        "dev_b_policy.json": {
            "schema_version": "apphear.fsboard.confirmation_dev_policy.v1",
            "manifest_path": (OUTPUT / "dev_b/tranche_manifest.json").relative_to(REPO).as_posix(),
            "manifest_sha256": digest(manifest(base, dev_b, "DEV_B")),
            "sample_ids": [r["sample_id"] for r in dev_b],
            "permitted_use": SETTINGS["dev_b_usage"],
            "forbidden_uses": SETTINGS["dev_b_forbidden_uses"],
            "same_official_dev_signers_as_dev_a": True,
            "phrase_disjointness_from_train_or_dev_a_claimed": False,
            "test_payload_accessed": False,
        },
    }


def validate_documents(docs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    base = foundation()
    official, _ = read_metadata()
    allowed = {record(r)["sample_id"]: record(r) for r in official if r["role"] != "PROTECTED_TEST"}
    excluded = set(
        json.loads((BASE / "dev_phrase_policy.json").read_text())["excluded_dev_sample_ids"]
    )
    protected = {r["clipFileMd5"] for r in official if r["role"] == "PROTECTED_TEST"}
    old = [r for r in base["samples"] if r["split_role"] == "TRAIN"]
    a = [r for r in base["samples"] if r["split_role"] == "DEV"]
    train = docs["train4096_manifest.json"]["samples"]
    extra = docs["train_additions/tranche_manifest.json"]["samples"]
    b = docs["dev_b/tranche_manifest.json"]["samples"]
    if train[: len(old)] != old or train[len(old) :] != extra:
        raise ValueError("[fsboard/expansion] Original TRAIN rows/order or additions changed")
    if (len(train), len(extra), len(b)) != (
        SETTINGS["train_sequences"],
        SETTINGS["train_sequences"] - len(old),
        SETTINGS["dev_b_sequences"],
    ):
        raise ValueError("[fsboard/expansion] Required cohort count mismatch")
    ids: set[str] = set()
    md5s: set[str] = set()
    humans: dict[str, str] = {}
    for role, samples in [("TRAIN", train), ("DEV", a + b)]:
        for row in samples:
            sid = row["sample_id"]
            if sid in ids or row["official_md5"] in md5s:
                raise ValueError("[fsboard/expansion] Duplicate ID or source across cohorts")
            ids.add(sid)
            md5s.add(row["official_md5"])
            if row != allowed.get(sid) or row["split_role"] != role:
                raise ValueError("[fsboard/expansion] Official metadata/source/role mutation")
            if humans.setdefault(row["official_signer_id"], role) != role:
                raise ValueError("[fsboard/expansion] Signer leakage")
            if row["official_md5"] in protected or (role == "DEV" and sid in excluded):
                raise ValueError("[fsboard/expansion] Protected-copy or phrase-policy violation")
            if len(target_ids(row["normalized_transcript"])) != row["transcript_length"]:
                raise ValueError("[fsboard/expansion] Transcript/target mismatch")
    quota = collections.Counter(r["source_group"] for r in train)
    if dict(quota) != SETTINGS["train_stratum_quota"]:
        raise ValueError("[fsboard/expansion] Stratum quota mismatch")
    if docs["dev_a_reference.json"]["sample_ids"] != [r["sample_id"] for r in a]:
        raise ValueError("[fsboard/expansion] DEV-A mutated")
    if docs["dev_b_policy.json"]["forbidden_uses"] != SETTINGS["dev_b_forbidden_uses"]:
        raise ValueError("[fsboard/expansion] DEV-B selection restriction changed")
    for cohort, samples, count in [
        ("TRAIN", train, SETTINGS["train_signers"]),
        ("DEV_B", b, SETTINGS["dev_signers"]),
    ]:
        if len({r["official_signer_id"] for r in samples}) != count:
            raise ValueError(f"[fsboard/expansion] {cohort} signer coverage mismatch")
        if set("".join(r["normalized_transcript"] for r in samples)) != set(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ "
        ):
            raise ValueError(f"[fsboard/expansion] {cohort} character coverage incomplete")
    return {
        "structural_pass": True,
        "train_sequences": len(train),
        "retained_train": len(old),
        "new_train": len(extra),
        "dev_a": len(a),
        "dev_b": len(b),
        "unique_ids_and_source_md5s": len(ids),
        "dev_b_usage": "FINAL_CONFIRMATION_ONLY",
        "test_payload_accessed": False,
    }


def build() -> dict[str, Any]:
    docs = documents()
    checked = validate_documents(docs)
    for name, doc in docs.items():
        frozen_write(OUTPUT / name, doc)
    batches: list[dict[str, Any]] = []
    for package in ["train_additions", "dev_b"]:
        write_batch_plan(OUTPUT / package, docs[package + "/tranche_manifest.json"])
        plan = json.loads((OUTPUT / package / "batch_plan.json").read_text())
        batches.extend(dict(batch, package=package) for batch in plan["batches"])
    frozen_write(
        OUTPUT / "batch_plan.json",
        {
            "schema_version": "apphear.fsboard.expansion_batch_plan.v1",
            "batches": batches,
            "existing_train_sequences_reused_without_extraction": 1024,
            "batch_limit": SETTINGS["batch_sequences"],
            "commands_executed": False,
        },
    )
    frozen_write(
        OUTPUT / "plan_identity.json",
        {
            "schema_version": "apphear.fsboard.expansion_plan_identity.v1",
            "selection_config_sha256": sha256(CONFIG_PATH),
            "manifest_sha256": {name: digest(doc) for name, doc in docs.items()},
            "batch_plan_sha256": sha256(OUTPUT / "batch_plan.json"),
            "foundation_manifest_sha256": SETTINGS["foundation_manifest_sha256"],
            "dev_b_training_config_reference": False,
            "test_payload_accessed": False,
        },
    )
    return checked


def validate_plan() -> dict[str, Any]:
    expected = documents()
    actual = {name: json.loads((OUTPUT / name).read_text()) for name in expected}
    result = validate_documents(actual)
    for name, value in expected.items():
        if (OUTPUT / name).read_bytes() != serialized(value):
            raise ValueError(f"[fsboard/expansion] Non-reproducible manifest: {name}")
    plan = json.loads((OUTPUT / "batch_plan.json").read_text())
    for package in ["train_additions", "dev_b"]:
        batches = [b for b in plan["batches"] if b["package"] == package]
        wanted = actual[package + "/tranche_manifest.json"]["samples"]
        if [sid for b in batches for sid in b["sample_ids"]] != [r["sample_id"] for r in wanted]:
            raise ValueError("[fsboard/expansion] Batch coverage/order mismatch")
        if any(
            b["count"] != len(b["sample_ids"]) or not 1 <= b["count"] <= SETTINGS["batch_sequences"]
            for b in batches
        ):
            raise ValueError("[fsboard/expansion] Invalid batch size")
        local_plan = json.loads((OUTPUT / package / "batch_plan.json").read_text())
        if local_plan["manifest_sha256"] != digest(actual[package + "/tranche_manifest.json"]):
            raise ValueError("[fsboard/expansion] Package batch manifest mismatch")
        if [dict(batch, package=package) for batch in local_plan["batches"]] != batches:
            raise ValueError("[fsboard/expansion] Package/combined batch plans differ")
        offset = 0
        for batch in batches:
            selected = wanted[offset : offset + batch["count"]]
            if (
                batch["start"] != offset
                or batch["role"] != selected[0]["split_role"]
                or batch["expected_source_bytes"] != sum(r["file_size_bytes"] for r in selected)
            ):
                raise ValueError("[fsboard/expansion] Batch offset/role/bytes mismatch")
            offset += batch["count"]
    identity_record = json.loads((OUTPUT / "plan_identity.json").read_text())
    if identity_record["batch_plan_sha256"] != sha256(
        OUTPUT / "batch_plan.json"
    ) or identity_record["selection_config_sha256"] != sha256(CONFIG_PATH):
        raise ValueError("[fsboard/expansion] Frozen plan/config hash mismatch")
    if identity_record["manifest_sha256"] != {
        name: digest(value) for name, value in actual.items()
    }:
        raise ValueError("[fsboard/expansion] Manifest identity mismatch")
    b_path = (OUTPUT / "dev_b/tranche_manifest.json").relative_to(REPO).as_posix()
    references = [
        str(p.relative_to(REPO))
        for p in (REPO / "model/config").glob("*.json")
        if b_path in p.read_text(encoding="utf-8")
        or "train4096_plan_01/dev_b" in p.read_text(encoding="utf-8")
    ]
    if references:
        raise ValueError(f"[fsboard/expansion] DEV-B referenced by model config: {references}")
    result.update(
        reproducible_manifests=True,
        manifest_sha256=identity_record["manifest_sha256"],
        batch_count=len(plan["batches"]),
        dev_b_training_config_references=references,
    )
    return result


def coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    lengths = collections.Counter(r["transcript_length"] for r in rows)
    signers = collections.Counter(r["official_signer_id"] for r in rows)
    texts = [r["normalized_transcript"] for r in rows]
    chars = collections.Counter("".join(texts))
    return {
        "sequences": len(rows),
        "signers": len(signers),
        "strata": dict(collections.Counter(r["source_stratum"] for r in rows)),
        "per_signer_min_median_max": [
            min(signers.values()),
            statistics.median(signers.values()),
            max(signers.values()),
        ],
        "signer_counts": dict(sorted(signers.items())),
        "characters": sum(chars.values()),
        "character_counts": {
            "SPACE" if c == " " else c: chars[c] for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ "
        },
        "length_histogram": dict(sorted(lengths.items())),
        "length_min_median_max": [
            min(lengths),
            statistics.median([r["transcript_length"] for r in rows]),
            max(lengths),
        ],
        "length_buckets": {
            "short_le_11": sum(n <= 11 for n in [len(t) for t in texts]),
            "medium_12_20": sum(12 <= len(t) <= 20 for t in texts),
            "long_ge_21": sum(len(t) >= 21 for t in texts),
        },
        "j_sequences": sum("J" in t for t in texts),
        "z_sequences": sum("Z" in t for t in texts),
        "repeat_sequences_including_spaces": sum(r["adjacent_repeat_count"] > 0 for r in rows),
        "repeated_letter_sequences": sum(
            any(a == b and a != " " for a, b in zip(t, t[1:], strict=False)) for t in texts
        ),
        "source_bytes": sum(r["file_size_bytes"] for r in rows),
        "metadata_duration_s": sum(r["source_duration_metadata_s"] for r in rows),
    }


def analyze() -> dict[str, Any]:
    validate_plan()
    docs = {name: json.loads((OUTPUT / name).read_text()) for name in documents()}
    base = foundation()
    cohorts = {
        "TRAIN_4096": docs["train4096_manifest.json"]["samples"],
        "DEV_A": [r for r in base["samples"] if r["split_role"] == "DEV"],
        "DEV_B": docs["dev_b/tranche_manifest.json"]["samples"],
    }
    stats = {name: coverage(rows) for name, rows in cohorts.items()}
    phrases = {name: {r["normalized_transcript"] for r in rows} for name, rows in cohorts.items()}
    stats["DEV_B"]["overlap"] = {
        name: {
            "sequence_ids": len(
                {r["sample_id"] for r in cohorts["DEV_B"]} & {r["sample_id"] for r in cohorts[name]}
            ),
            "distinct_normalized_phrases": len(phrases["DEV_B"] & phrases[name]),
            "dev_b_sequences_with_shared_phrase": sum(
                r["normalized_transcript"] in phrases[name] for r in cohorts["DEV_B"]
            ),
        }
        for name in ["TRAIN_4096", "DEV_A"]
    }
    receipts = [json.loads(p.read_text()) for p in (BASE / "features").glob("*.receipt.json")]
    by_id = {r["sample_id"]: r for r in receipts}
    reusable = []
    caches = []
    for cohort in ["TRAIN_4096", "DEV_B"]:
        for row in cohorts[cohort]:
            cached = [REPO / folder / row["filename"] for folder in SETTINGS["source_cache_roots"]]
            if row["sample_id"] in by_id:
                cached.insert(0, REPO / by_id[row["sample_id"]]["source_path"])
            found = next((p for p in cached if p.is_file()), None)
            if found is not None:
                # Metadata planning can inspect integrity bytes; it never decodes RGB.
                if found.stat().st_size != row["file_size_bytes"]:
                    raise ValueError(f"[fsboard/expansion] Cached source size mismatch: {found}")
                md5 = hashlib.md5(usedforsecurity=False)
                source_sha = hashlib.sha256()
                with found.open("rb") as stream:
                    for data in iter(lambda: stream.read(1024 * 1024), b""):
                        md5.update(data)
                        source_sha.update(data)
                if md5.hexdigest() != row["official_md5"]:
                    raise ValueError("[fsboard/expansion] Cached MD5 mismatch")
                if (
                    row["sample_id"] in by_id
                    and source_sha.hexdigest() != by_id[row["sample_id"]]["source_sha256"]
                ):
                    raise ValueError("[fsboard/expansion] Cached receipt SHA mismatch")
                caches.append(
                    {
                        "sample_id": row["sample_id"],
                        "cohort": cohort,
                        "source_path": found.relative_to(REPO).as_posix(),
                        "source_bytes": row["file_size_bytes"],
                        "md5": md5.hexdigest(),
                        "sha256": source_sha.hexdigest(),
                    }
                )
            if row["sample_id"] in by_id:
                rec = by_id[row["sample_id"]]
                if (
                    rec["manifest_sha256"] != SETTINGS["foundation_manifest_sha256"]
                    or rec["adapter"] != identity()
                ):
                    raise ValueError("[fsboard/expansion] Old receipt lineage mismatch")
                for kind in ["features", "raw", "raw_receipt"]:
                    if sha256(REPO / rec[kind + "_path"]) != rec[kind + "_sha256"]:
                        raise ValueError("[fsboard/expansion] Old artifact hash mismatch")
                reusable.append(
                    {
                        "sample_id": row["sample_id"],
                        "foundation_receipt_path": (
                            BASE / "features" / (row["sample_id"] + ".receipt.json")
                        )
                        .relative_to(REPO)
                        .as_posix(),
                        "features_path": rec["features_path"],
                        "features_sha256": rec["features_sha256"],
                        "raw_path": rec["raw_path"],
                        "raw_sha256": rec["raw_sha256"],
                        "source_path": rec["source_path"],
                        "source_sha256": rec["source_sha256"],
                        "original_manifest_sha256": rec["manifest_sha256"],
                        "reuse_rule": "REFERENCE_IMMUTABLE_ARTIFACT_NO_COPY_OR_RECEIPT_REWRITE",
                    }
                )
    for cohort in ["TRAIN_4096", "DEV_B"]:
        cache = [r for r in caches if r["cohort"] == cohort]
        stats[cohort].update(
            cached_source_count=len(cache),
            cached_source_bytes=sum(r["source_bytes"] for r in cache),
            required_download_count=len(cohorts[cohort]) - len(cache),
            required_download_bytes=stats[cohort]["source_bytes"]
            - sum(r["source_bytes"] for r in cache),
        )
    measured_frames = sum(r["frame_count"] for r in receipts)
    metadata_seconds = sum(r["source_duration_metadata_s"] for r in receipts)
    timed = []
    for r in receipts:
        raw_receipt = json.loads((REPO / r["raw_receipt_path"]).read_text())
        if "extraction_wall_seconds" in raw_receipt:
            timed.append(raw_receipt)
    fps = sum(r["frame_count"] for r in timed) / sum(r["extraction_wall_seconds"] for r in timed)
    storage = {
        kind: sum((REPO / r[kind + "_path"]).stat().st_size for r in receipts)
        for kind in ["features", "raw"]
    }
    new_rows = docs["train_additions/tranche_manifest.json"]["samples"] + cohorts["DEV_B"]
    new_frames = (
        sum(r["source_duration_metadata_s"] for r in new_rows) * measured_frames / metadata_seconds
    )
    workload = {
        "measured_foundation_sequences": len(receipts),
        "measured_frames": measured_frames,
        "measured_metadata_seconds": metadata_seconds,
        "measured_frames_per_metadata_second": measured_frames / metadata_seconds,
        "timed_extraction_receipts": len(timed),
        "measured_timed_extraction_seconds": sum(r["extraction_wall_seconds"] for r in timed),
        "measured_frames_per_processing_second": fps,
        "measured_archive_bytes": storage,
        "new_sequences_to_extract": len(new_rows),
        "estimated_new_frames": new_frames,
        "estimated_candidate01_hours": new_frames / fps / 3600,
        "estimated_new_archive_bytes": {
            k: round(v / measured_frames * new_frames) for k, v in storage.items()
        },
        "estimate_scope": (
            "SAME_HOST_AND_DISTRIBUTION; " "EXCLUDES_DOWNLOAD_AND_FULL_BATCH_VALIDATION_OVERHEAD"
        ),
        "original_artifacts_reused": len(reusable),
    }
    workload["estimated_by_cohort"] = {}
    for name, rows in [
        ("TRAIN_ADDITIONS", docs["train_additions/tranche_manifest.json"]["samples"]),
        ("DEV_B", cohorts["DEV_B"]),
    ]:
        frames = (
            sum(r["source_duration_metadata_s"] for r in rows) * measured_frames / metadata_seconds
        )
        workload["estimated_by_cohort"][name] = {
            "sequences": len(rows),
            "metadata_duration_s": sum(r["source_duration_metadata_s"] for r in rows),
            "frames": frames,
            "candidate01_hours": frames / fps / 3600,
            "archive_bytes": {k: round(v / measured_frames * frames) for k, v in storage.items()},
        }
    frozen_write(
        OUTPUT / "reuse_inventory.json",
        {"records": reusable, "foundation_manifest_sha256": SETTINGS["foundation_manifest_sha256"]},
    )
    frozen_write(
        OUTPUT / "cached_sources.json",
        {
            "records": caches,
            "scan_roots": SETTINGS["source_cache_roots"],
            "integrity": "SIZE_MD5_SHA256_VERIFIED_NO_RGB_DECODE",
        },
    )
    report = {
        "schema_version": "apphear.fsboard.expansion_plan_analysis.v1",
        "coverage": stats,
        "workload": workload,
        "no_accuracy_claim": True,
        "test_payload_accessed": False,
    }
    frozen_write(OUTPUT / "coverage_and_workload.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "validate", "analyze"])
    args = parser.parse_args()
    result = (
        build()
        if args.command == "build"
        else validate_plan() if args.command == "validate" else analyze()
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
