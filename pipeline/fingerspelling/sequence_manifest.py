"""Pinned metadata-only, signer-disjoint FSboard sequence inventory. TEST payload sealed."""

from __future__ import annotations

import collections
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pipeline.fingerspelling.adapter import CONFIG, VERSION, identity, sha256, validate_config

REPO = Path(__file__).resolve().parents[2]
GATE = "datasets/fingerspelling/fsboard_gate_20261002/official"
ADMISSION = REPO / "datasets/fingerspelling/fsboard_candidate01_admission_20261002"
MANIFEST_SCHEMA = "apphear.fingerspelling.sequence_manifest.v1"
METADATA = [
    (
        "daun_v3",
        "TRAIN",
        "train",
        "f85cbf264a4bab08924f5c19c565d3e9b32d4161fabe3004adeb40dd1ba56cdc",
    ),
    (
        "dmk_v3",
        "TRAIN",
        "train",
        "fcabb89d682fbc31af1427d120c7c228ac6a4cebe69cbf2b5b6d793a1782f4fc",
    ),
    (
        "daun_v3",
        "DEV",
        "validation",
        "d306aac4c80e7052492ebffdd01f2e8242d09755ff7243824e866360fb609648",
    ),
    (
        "daun_v3",
        "PROTECTED_TEST",
        "test",
        "94f53f6c9d9199cbc50c5207a31a96d400734e49eac60d4a157fc515a587423b",
    ),
]


def normalized(text: str) -> str:
    if not re.fullmatch(r"[A-Za-z ]+", text) or not re.search(r"[A-Za-z]", text):
        raise ValueError("[fingerspelling/transcript] Expected ASCII alphabet/spaces")
    return text.upper()  # Deliberately preserve original spaces, including repeated spaces.


def repeats(text: str) -> int:
    return sum(a == b for a, b in zip(text, text[1:], strict=False))


def target_ids(text: str) -> list[int]:
    validate_config()
    text = normalized(text)
    return [26 if c == " " else ord(c) - ord("A") for c in text]


def read_metadata() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows, sources = [], []
    human_roles: dict[str, str] = {}
    for group, role, official, expected in METADATA:
        path = REPO / f"{GATE}/{group}/metadata/{group}-{official}.json"
        if sha256(path) != expected:
            raise ValueError(f"[fingerspelling/metadata] Hash mismatch: {path}")
        sources.append(
            {
                "path": path.relative_to(REPO).as_posix(),
                "sha256": expected,
                "role": role,
                "group": group,
            }
        )
        for row in json.loads(path.read_text(encoding="utf-8")):
            signer = row["signerId"]
            if human_roles.setdefault(signer, role) != role:
                raise ValueError(f"[fingerspelling/split] Official signer leakage: {signer}")
            try:
                text = normalized(row["phrase"])
            except ValueError:
                continue
            rows.append(
                dict(
                    row, group=group, role=role, official_split=official, normalized_transcript=text
                )
            )
    return rows, sources


def record(row: dict[str, Any]) -> dict[str, Any]:
    relative = (
        f"{row['group']}/video_clips/{row['group']}-{row['official_split']}/{row['clipFilename']}"
    )
    digest = hashlib.sha256(f"googleai/fsboard\nv13\n{relative}".encode()).hexdigest()[:20]
    transcript = row["normalized_transcript"]
    duration = row["clipEndTimeS"] - row["clipStartTimeS"]
    return {
        "sample_id": f"fsboard-v13-{row['official_split']}-{digest}",
        "dataset": "googleai/fsboard",
        "dataset_version": 13,
        "split_role": row["role"],
        "official_split": row["official_split"],
        "source_group": row["group"],
        "source_stratum": "DAUN" if row["group"] == "daun_v3" else "MacKenzie",
        "official_signer_id": row["signerId"],
        "collection_id": row["collectionId"],
        "full_video_filename": row["fullVideoFilename"],
        "transcript": row["phrase"],
        "normalized_transcript": transcript,
        "transcript_length": len(transcript),
        "adjacent_repeat_count": repeats(transcript),
        "ctc_min_timesteps": len(transcript) + repeats(transcript),
        "kaggle_relative_path": relative,
        "filename": row["clipFilename"],
        "file_size_bytes": row["clipFileSize"],
        "official_md5": row["clipFileMd5"],
        "source_duration_metadata_s": duration,
        "official_metadata": {
            k: v
            for k, v in row.items()
            if k not in {"group", "role", "official_split", "normalized_transcript"}
        },
        "direct_download_url": "https://www.kaggle.com/api/v1/datasets/download/googleai/fsboard/"
        + quote(relative, safe="")
        + "?datasetVersionNumber=13",
        "adapter_version": VERSION,
        "reflection_policy": CONFIG["reflection_policy"],
        "reflection_provenance": CONFIG["reflection_provenance"],
        "uniform_phone_timesteps_estimate": int(duration * CONFIG["phone_observations_per_second"])
        + 1,
        "preparation_status": "PENDING_ACQUISITION_EXTRACTION",
    }


def select_balanced(
    rows: list[dict[str, Any]], count: int, forced: set[str]
) -> list[dict[str, Any]]:
    """Round-robin signers; per signer rotate length and J/Z/repetition/ordinary strata."""
    by_signer: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        by_signer[row["signerId"]].append(row)
    queues: dict[str, list[dict[str, Any]]] = {}
    for signer, values in by_signer.items():
        buckets: dict[tuple[int, int], list[dict[str, Any]]] = collections.defaultdict(list)
        for r in values:
            text = r["normalized_transcript"]
            band = 0 if len(text) <= 11 else 1 if len(text) <= 20 else 2
            tag = 0 if "J" in text else 1 if "Z" in text else 2 if repeats(text) else 3
            buckets[band, tag].append(r)
        for bucket in buckets.values():
            bucket.sort(
                key=lambda r: hashlib.sha256(
                    (CONFIG["selection_salt"] + "\n" + r["clipFilename"]).encode()
                ).hexdigest()
            )
        queue = []
        while any(buckets.values()):
            for key in sorted(buckets):
                if buckets[key]:
                    queue.append(buckets[key].pop(0))
        queues[signer] = queue
    chosen = [r for r in rows if r["clipFilename"] in forced]
    used = {r["clipFilename"] for r in chosen}
    md5s = {r["clipFileMd5"] for r in chosen}
    # Forced evidence clips count toward signer quotas before ordinary selection.
    while len(chosen) < count:
        progressed = False
        order = sorted(queues, key=lambda s: (sum(r["signerId"] == s for r in chosen), s))
        for signer in order:
            while queues[signer]:
                r = queues[signer].pop(0)
                if r["clipFilename"] in used or r["clipFileMd5"] in md5s:
                    continue
                chosen.append(r)
                used.add(r["clipFilename"])
                md5s.add(r["clipFileMd5"])
                progressed = True
                break
            if len(chosen) == count:
                break
        if not progressed:
            raise ValueError("[fingerspelling/selection] Insufficient distinct clips")
    return chosen


def summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for role in ("TRAIN", "DEV"):
        rows = [s for s in samples if s["split_role"] == role]
        texts = [s["normalized_transcript"] for s in rows]
        result[role] = {
            "sequences": len(rows),
            "signers": len({s["official_signer_id"] for s in rows}),
            "source_counts": dict(collections.Counter(s["source_stratum"] for s in rows)),
            "character_counts": dict(sorted(collections.Counter("".join(texts)).items())),
            "j_sequences": sum("J" in t for t in texts),
            "z_sequences": sum("Z" in t for t in texts),
            "repeat_sequences": sum(repeats(t) > 0 for t in texts),
            "lengths": [len(t) for t in texts],
            "duration_sum_s": sum(s["source_duration_metadata_s"] for s in rows),
            "expected_source_bytes": sum(s["file_size_bytes"] for s in rows),
            "uniform_phone_ctc_infeasible": sum(
                s["uniform_phone_timesteps_estimate"] < s["ctc_min_timesteps"] for s in rows
            ),
            "signer_counts": dict(
                sorted(collections.Counter(s["official_signer_id"] for s in rows).items())
            ),
        }
    return result


def write_batch_plan(output: Path, manifest: dict[str, Any]) -> None:
    batches = []
    base = ".venv/Scripts/python.exe -m tools.fingerspelling.foundation"
    destination = output.relative_to(REPO).as_posix()
    for role in ("TRAIN", "DEV"):
        rows = [r for r in manifest["samples"] if r["split_role"] == role]
        for start in range(0, len(rows), CONFIG["batch_sequences"]):
            selected = rows[start : start + CONFIG["batch_sequences"]]
            flags = (
                f'--output "{destination}" --role {role} --start {start} --count {len(selected)}'
            )
            batches.append(
                {
                    "role": role,
                    "start": start,
                    "count": len(selected),
                    "expected_source_bytes": sum(r["file_size_bytes"] for r in selected),
                    "sample_ids": [r["sample_id"] for r in selected],
                    "plan_command": f"{base} plan-batch {flags}",
                    "acquire_command": f"{base} acquire-batch {flags}",
                    "extract_command": f"{base} extract-batch {flags}",
                    "validate_command": f'{base} validate --output "{destination}"',
                }
            )
    (output / "batch_plan.json").write_text(
        json.dumps(
            {
                "schema_version": "apphear.fingerspelling.batch_plan.v1",
                "manifest_sha256": sha256(output / "tranche_manifest.json"),
                "batch_limit": CONFIG["batch_sequences"],
                "acquisition_extraction_commands_not_executed": True,
                "batches": batches,
            },
            indent=2,
        )
        + "\n"
    )


def prepare(output: Path) -> dict[str, Any]:
    rows, sources = read_metadata()
    test_phrases = {r["normalized_transcript"] for r in rows if r["role"] == "PROTECTED_TEST"}
    excluded = [
        r for r in rows if r["role"] == "DEV" and r["normalized_transcript"] in test_phrases
    ]
    allowed_dev = [
        r for r in rows if r["role"] == "DEV" and r["normalized_transcript"] not in test_phrases
    ]
    old = json.loads(
        (ADMISSION / "fsboard_candidate01_admission_download_manifest.json").read_text()
    )
    forced = {s["clip_filename"] for s in old["samples"]}
    selected = []
    for group, quota in CONFIG["train_stratum_quota"].items():
        selected.extend(
            select_balanced(
                [r for r in rows if r["role"] == "TRAIN" and r["group"] == group], quota, forced
            )
        )
    selected.extend(select_balanced(allowed_dev, CONFIG["dev_sequences"], set()))
    samples = [record(r) for r in selected]
    if len({s["official_md5"] for s in samples}) != len(samples):
        raise ValueError("[fingerspelling/selection] Cross-role duplicate bytes")
    policy = {
        "schema_version": "apphear.fsboard.dev_phrase_policy.v1",
        "policy": CONFIG["dev_test_phrase_policy"],
        "normalization": "ASCII uppercase; spaces unchanged",
        "test_payload_accessed": False,
        "official_roles_changed": False,
        "metadata_sources": sources,
        "excluded_dev_sample_ids": sorted(record(r)["sample_id"] for r in excluded),
        "overlapping_distinct_phrases": len({r["normalized_transcript"] for r in excluded}),
        "eligible_dev_after_exclusion": len(allowed_dev),
        "eligible_dev_signers": len({r["signerId"] for r in allowed_dev}),
    }
    output.mkdir(parents=True, exist_ok=True)
    policy_path = output / "dev_phrase_policy.json"
    policy_path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "adapter": identity(),
        "preparation_scope": "RESEARCH_ONLY_NOT_PRODUCTION_OR_FORMAL_REFLECTION_PROOF",
        "research_authorization": {
            "authority": "User development decision 2026-10-02",
            "policy": CONFIG["reflection_policy"],
            "provenance": CONFIG["reflection_provenance"],
            "legacy_diagnostic_receipts_unchanged": True,
        },
        "metadata_sources": sources,
        "dev_phrase_policy_path": str(policy_path.relative_to(REPO)).replace("\\", "/"),
        "dev_phrase_policy_sha256": sha256(policy_path),
        "samples": samples,
        "summary": summary(samples),
    }
    (output / "tranche_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    write_batch_plan(output, manifest)
    return manifest
