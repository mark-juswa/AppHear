"""Read-only admission of frozen TRAIN-4096 + DEV-A; DEV-B is separate confirmation.

Reuses the existing source/raw/adapter verifiers. Never acquires, extracts, rewrites
foundation artifacts, opens TEST metadata/payloads, or admits an incomplete tranche.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

import numpy as np

from pipeline.fingerspelling.adapter import derive, identity, phone_indices, sha256, subset
from pipeline.fingerspelling.sequence_manifest import (
    ADMISSION,
    MANIFEST_SCHEMA,
    REPO,
    normalized,
    repeats,
    target_ids,
)
from pipeline.fingerspelling.sequence_package import (
    ARTIFACT_SCHEMA,
    RECEIPT_SCHEMA,
    verify_raw,
    verify_source,
)
from pipeline.fingerspelling.storage import declaration, receipt_identity

CONFIG = REPO / "model/config/fingerspelling_train4096_01.json"
FOUNDATION = REPO / "datasets/fingerspelling/foundation_01"
PLAN = REPO / "datasets/fingerspelling/train4096_plan_01"


def read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def configuration() -> dict[str, Any]:
    p = read_json(CONFIG)
    if (
        p["schema_version"] != "apphear.fingerspelling.train4096.v1"
        or p["feature_width"] != 405
        or p["adapter"] != identity()["schema_version"]
        or p["final_decoder"]
        != {"beam_width": 10, "blank_penalty": 0.5, "blank_index": 27, "top_paths": 1}
        or p["selection"] != "MEAN_UNCALIBRATED_NATIVE_PHONE_DEV_A_GREEDY_CER_FIRST_TIE"
        or p["dev_b_usage"] != "FINAL_CONFIRMATION_ONLY_AFTER_CHECKPOINT_FREEZE"
        or p["test_access"] != "SEALED"
    ):
        raise ValueError("[train4096/config] Frozen input/decoder/governance mismatch")
    return p


def indexed(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {r["sample_id"]: r for r in rows}
    if len(result) != len(rows):
        raise ValueError("[train4096/governance] Duplicate sample IDs")
    return result


def governance(documents: dict[str, dict[str, Any]]) -> None:
    f, t, a, b = [
        indexed(documents[k]["samples"])
        for k in ("foundation", "train", "additions", "confirmation")
    ]
    old_train = {sid: r for sid, r in f.items() if r["split_role"] == "TRAIN"}
    old_dev = {sid: r for sid, r in f.items() if r["split_role"] == "DEV"}
    if [len(x) for x in (old_train, old_dev, t, a, b)] != [1024, 256, 4096, 3072, 256]:
        raise ValueError("[train4096/governance] Exact frozen cohort counts required")
    if set(old_train) & set(a) or set(t) != set(old_train) | set(a):
        raise ValueError("[train4096/governance] Original TRAIN subset/additions changed")
    if any(t[sid] != row for sid, row in {**old_train, **a}.items()):
        raise ValueError("[train4096/governance] Original/added manifest rows changed")
    if set(t) & (set(old_dev) | set(b)) or set(old_dev) & set(b):
        raise ValueError("[train4096/governance] Cohort sequence leakage")
    groups = [(t, "TRAIN", "train"), (old_dev, "DEV", "validation"), (b, "DEV", "validation")]
    for group, role, official in groups:
        for row in group.values():
            text = row["normalized_transcript"]
            if row["split_role"] != role or row["official_split"] != official:
                raise ValueError("[train4096/governance] Official role mutation")
            if (
                normalized(row["transcript"]) != text
                or not text
                or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ " for c in text)
                or row["ctc_min_timesteps"] != len(text) + repeats(text)
                or row["reflection_policy"] != "USE_RELEASED_PIXELS_AS_IS"
            ):
                raise ValueError("[train4096/governance] Transcript/CTC/reflection mutation")
    train_signers = {r["official_signer_id"] for r in t.values()}
    dev_a_signers = {r["official_signer_id"] for r in old_dev.values()}
    dev_b_signers = {r["official_signer_id"] for r in b.values()}
    if len(train_signers) != 117 or len(dev_a_signers) != 15 or dev_b_signers != dev_a_signers:
        raise ValueError("[train4096/governance] Frozen signer coverage changed")
    if train_signers & (dev_a_signers | dev_b_signers):
        raise ValueError("[train4096/governance] Human leakage")
    if Counter(r["source_stratum"] for r in t.values()) != {"DAUN": 2048, "MacKenzie": 2048}:
        raise ValueError("[train4096/governance] Frozen source strata changed")
    combined = [*t.values(), *old_dev.values(), *b.values()]
    for field in ("kaggle_relative_path", "official_md5"):
        if len({r[field] for r in combined}) != len(combined):
            raise ValueError(f"[train4096/governance] Duplicate source identity: {field}")
    if set("".join(r["normalized_transcript"] for r in t.values())) != set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ "
    ):
        raise ValueError("[train4096/governance] Missing transcript class")


def manifests() -> dict[str, dict[str, Any]]:
    p = configuration()
    paths = {
        "foundation": (FOUNDATION / "tranche_manifest.json", p["foundation_manifest_sha256"]),
        "train": (PLAN / "train4096_manifest.json", p["train_manifest_sha256"]),
        "additions": (
            PLAN / "train_additions/tranche_manifest.json",
            p["additions_manifest_sha256"],
        ),
        "confirmation": (PLAN / "dev_b/tranche_manifest.json", p["confirmation_manifest_sha256"]),
    }
    docs = {}
    for name, (path, expected) in paths.items():
        if sha256(path) != expected:
            raise ValueError(f"[train4096/governance] Frozen manifest changed: {name}")
        docs[name] = read_json(path)
        if docs[name]["schema_version"] != MANIFEST_SCHEMA or docs[name]["adapter"] != identity():
            raise ValueError("[train4096/governance] Manifest schema/adapter mismatch")
        policy = REPO / docs[name]["dev_phrase_policy_path"]
        if sha256(policy) != p["dev_phrase_policy_sha256"] or docs[name][
            "dev_phrase_policy_sha256"
        ] != sha256(policy):
            raise ValueError("[train4096/governance] DEV overlap policy changed")
    governance(docs)
    return docs


def verify_record(
    package: Path, row: dict[str, Any], manifest_sha: str, *, full: bool
) -> dict[str, Any]:
    path = package / "features" / (row["sample_id"] + ".receipt.json")
    rec = read_json(path)
    if (
        rec["schema_version"] != RECEIPT_SCHEMA
        or rec["manifest_sha256"] != manifest_sha
        or rec["adapter"] != identity()
        or any(rec.get(k) != v for k, v in row.items() if k != "preparation_status")
        or any(rec.get(k) != v for k, v in receipt_identity(package).items())
    ):
        raise ValueError("[train4096/receipt] Manifest/adapter/storage identity mismatch")
    for key in ("source", "raw", "raw_receipt", "features"):
        resolved = (REPO / rec[f"{key}_path"]).resolve()
        legacy_reuse = (
            package.resolve() == FOUNDATION.resolve()
            and key in {"source", "raw", "raw_receipt"}
            and resolved.is_relative_to(ADMISSION.resolve())
        )
        if not resolved.is_relative_to(package.resolve()) and not legacy_reuse:
            raise ValueError("[train4096/receipt] File escapes its declared package")
        if not resolved.is_file() or sha256(resolved) != rec[f"{key}_sha256"]:
            raise ValueError(f"[train4096/receipt] {key} identity mismatch")
    if full:
        source_sha = verify_source(REPO / rec["source_path"], row)
        raw = verify_raw(REPO / rec["raw_path"], REPO / rec["raw_receipt_path"], row, source_sha)
        selected = phone_indices(raw.timestamp_ms)
        with np.load(REPO / rec["features_path"], allow_pickle=False) as data:
            meta = json.loads(str(data["metadata_json"].item()))
            if meta["schema_version"] != ARTIFACT_SCHEMA or meta["adapter"] != identity():
                raise ValueError("[train4096/features] Schema/adapter mismatch")
            checks = {
                "features": derive(raw),
                "phone_features": derive(subset(raw, selected)),
                "timestamps_ms": raw.timestamp_ms,
                "frame_indices": raw.frame_index,
                "phone_indices": selected,
                "phone_timestamps_ms": raw.timestamp_ms[selected],
                "targets": np.asarray(target_ids(row["normalized_transcript"]), np.int32),
                "hand_joint_valid": raw.hand_joint_valid,
                "hand_observed": raw.hand_observed,
                "hand_proposal_present": raw.hand_proposal_present,
                "body_valid": raw.body_valid,
                "body_available": raw.body_available,
            }
            if not all(np.array_equal(data[k], v) for k, v in checks.items()):
                raise ValueError(
                    "[train4096/features] Recomputed geometry/masks/timing/targets mismatch"
                )
            for key in ("features", "phone_features"):
                if data[key].dtype != np.float32 or not np.isfinite(data[key]).all():
                    raise ValueError("[train4096/features] Invalid numerical input")
            if (
                rec["frame_count"] != len(raw.frame_index)
                or rec["phone_frame_count"] != len(selected)
                or rec["native_ctc_feasible"] != (len(raw.frame_index) >= row["ctc_min_timesteps"])
                or rec["phone_ctc_feasible"] != (len(selected) >= row["ctc_min_timesteps"])
            ):
                raise ValueError("[train4096/features] CTC length/status mismatch")
    return rec


def package_records(
    package: Path, document: dict[str, Any], expected_sha: str, *, full: bool
) -> list[dict[str, Any]]:
    if sha256(package / "tranche_manifest.json") != expected_sha:
        raise ValueError("[train4096/package] Destination manifest mismatch")
    if package.resolve() != FOUNDATION.resolve() and declaration(package) is None:
        raise ValueError("[train4096/package] Managed external declaration required")
    expected = set(indexed(document["samples"]))
    receipt_ids = {
        p.name.removesuffix(".receipt.json") for p in (package / "features").glob("*.receipt.json")
    }
    feature_ids = {p.stem for p in (package / "features").glob("*.npz")}
    if receipt_ids != expected or feature_ids != expected:
        raise ValueError(
            f"[train4096/package] Incomplete/unexpected inventory: expected={len(expected)}, "
            f"receipts={len(receipt_ids)}, arrays={len(feature_ids)}, "
            f"missing={len(expected - receipt_ids)}, "
            f"unexpected={len((receipt_ids | feature_ids) - expected)}"
        )
    return [verify_record(package, row, expected_sha, full=full) for row in document["samples"]]


def load(
    destination: Path, *, confirmation: bool = False, full: bool = False
) -> list[dict[str, Any]]:
    """Training call cannot load DEV-B features; separate final-confirmation call only."""
    p, docs = configuration(), manifests()
    if confirmation:
        return package_records(
            destination / "dev_b",
            docs["confirmation"],
            p["confirmation_manifest_sha256"],
            full=full,
        )
    old = package_records(
        FOUNDATION, docs["foundation"], p["foundation_manifest_sha256"], full=full
    )
    added = package_records(
        destination / "train_additions",
        docs["additions"],
        p["additions_manifest_sha256"],
        full=full,
    )
    if Counter(r["split_role"] for r in old + added) != {"TRAIN": 4096, "DEV": 256}:
        raise ValueError("[train4096/admission] Exact TRAIN4096/DEV-A256 required")
    if any(not r["native_ctc_feasible"] for r in old + added if r["split_role"] == "TRAIN"):
        raise ValueError(
            "[train4096/admission] Native-infeasible TRAIN retained; explicit review required"
        )
    return old + added
