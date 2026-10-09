"""Protected-test-blind governance for the approved 236-class TRAIN/DEV population."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATASET_ROOT = ROOT / "artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1"
TRAIN_MANIFEST = DATASET_ROOT / "manifests/train.csv"
DEV_MANIFEST = DATASET_ROOT / "manifests/val.csv"
VOCAB_MANIFEST = DATASET_ROOT / "vocab.json"
EXPECTED = {
    "train_manifest_sha256": "751a2426b63a5474786440a2343098d0750af819b93d6f8ed54f002095cbdb33",
    "dev_manifest_sha256": "aa0e46c18c34e2eb6eb3584692e30594967cd81ec29300bcb5e4c76e27ec040b",
    "classes": 236,
    "train_clips": 3926,
    "dev_clips": 816,
    "train_signers": 40,
    "dev_signers": 5,
}
PATH_RELOCATIONS = {
    "ASL_CITIZEN": (
        (
            Path(r"F:\ASL DATASET\ASL CITIZEN"),
            Path(r"G:\ASL CITIZEN\ASL CITIZEN"),
        ),
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def resolve_governed_path(path_text: str, source_dataset: str) -> Path:
    """Resolve an approved manifest path after a byte-preserving corpus relocation.

    The pinned manifest remains immutable. The original path always wins when it exists;
    otherwise only an explicit source-specific root mapping may be used.
    """

    original = Path(path_text)
    if not path_text or original.is_file():
        return original
    original_text = str(original)
    original_folded = original_text.casefold()
    for old_root, new_root in PATH_RELOCATIONS.get(source_dataset, ()):
        old_text = str(old_root)
        old_folded = old_text.casefold()
        if original_folded == old_folded:
            relative = ""
        elif original_folded.startswith(old_folded + "\\"):
            relative = original_text[len(old_text) + 1 :]
        else:
            continue
        candidate = new_root / relative
        if candidate.is_file():
            return candidate
    return original


def resolve_row_paths(row: dict[str, str]) -> dict[str, str]:
    """Return a copy with only governed video/span paths resolved."""

    resolved = dict(row)
    source = row["source_dataset"]
    for field in ("raw_video_path", "span_path"):
        value = row.get(field, "").strip()
        if value:
            resolved[field] = str(resolve_governed_path(value, source))
    return resolved


def audit_governed_dataset(*, check_video_exists: bool = True) -> dict[str, Any]:
    """Audit only TRAIN and DEV. No protected-test path is discovered or opened."""

    identities = {
        "train_manifest_sha256": sha256(TRAIN_MANIFEST),
        "dev_manifest_sha256": sha256(DEV_MANIFEST),
        "vocab_manifest_sha256": sha256(VOCAB_MANIFEST),
    }
    for name in ("train_manifest_sha256", "dev_manifest_sha256"):
        if identities[name] != EXPECTED[name]:
            raise RuntimeError(f"VNEXT_GOVERNANCE_MANIFEST_IDENTITY:{name}")
    vocab = json.loads(VOCAB_MANIFEST.read_text(encoding="utf-8-sig"))
    if len(vocab) != EXPECTED["classes"] or sorted(vocab.values()) != list(range(236)):
        raise RuntimeError("VNEXT_GOVERNANCE_VOCAB_IDENTITY")
    manifest_splits = {
        "train": load_rows(TRAIN_MANIFEST),
        "dev": load_rows(DEV_MANIFEST),
    }
    splits = {
        split: [resolve_row_paths(row) for row in rows]
        for split, rows in manifest_splits.items()
    }
    expected_counts = {"train": EXPECTED["train_clips"], "dev": EXPECTED["dev_clips"]}
    expected_signers = {"train": EXPECTED["train_signers"], "dev": EXPECTED["dev_signers"]}
    summaries: dict[str, Any] = {}
    missing_videos: list[str] = []
    missing_spans: list[str] = []
    relocation_counts: Counter[str] = Counter()
    sample_ids: set[str] = set()
    signer_sets: dict[str, set[str]] = {}
    for split, rows in splits.items():
        original_by_sample = {row["sample_id"]: row for row in manifest_splits[split]}
        if len(rows) != expected_counts[split]:
            raise RuntimeError(f"VNEXT_GOVERNANCE_CLIP_COUNT:{split}:{len(rows)}")
        class_counts = Counter()
        source_counts = Counter()
        class_signers: defaultdict[int, set[str]] = defaultdict(set)
        signers: set[str] = set()
        for row in rows:
            sample_id = row["sample_id"]
            if sample_id in sample_ids:
                raise RuntimeError(f"VNEXT_GOVERNANCE_DUPLICATE_SAMPLE:{sample_id}")
            sample_ids.add(sample_id)
            class_id = int(row["class_id"])
            gloss = row["canonical_gloss"]
            if vocab.get(gloss) != class_id:
                raise RuntimeError(f"VNEXT_GOVERNANCE_LABEL_MISMATCH:{sample_id}")
            expected_split = "val" if split == "dev" else "train"
            if row["split"] != expected_split:
                raise RuntimeError(f"VNEXT_GOVERNANCE_SPLIT_MISMATCH:{sample_id}")
            class_counts[class_id] += 1
            source_counts[row["source_dataset"]] += 1
            signers.add(row["signer_group_id"])
            class_signers[class_id].add(row["signer_group_id"])
            original_row = original_by_sample[sample_id]
            for field in ("raw_video_path", "span_path"):
                if row.get(field, "") != original_row.get(field, ""):
                    relocation_counts[f"{row['source_dataset']}:{field}"] += 1
            if check_video_exists:
                if not Path(row["raw_video_path"]).is_file():
                    missing_videos.append(sample_id)
                span_text = row.get("span_path", "").strip()
                if span_text and not Path(span_text).is_file():
                    missing_spans.append(sample_id)
        if set(class_counts) != set(range(236)):
            raise RuntimeError(f"VNEXT_GOVERNANCE_CLASS_COVERAGE:{split}")
        if len(signers) != expected_signers[split]:
            raise RuntimeError(f"VNEXT_GOVERNANCE_SIGNER_COUNT:{split}:{len(signers)}")
        signer_sets[split] = signers
        clip_values = list(class_counts.values())
        signer_values = [len(class_signers[class_id]) for class_id in range(236)]
        summaries[split] = {
            "clips": len(rows),
            "classes": len(class_counts),
            "signers": len(signers),
            "sources": dict(sorted(source_counts.items())),
            "clips_per_class": {
                "min": min(clip_values),
                "max": max(clip_values),
                "counts_by_class_id": {str(k): class_counts[k] for k in range(236)},
            },
            "signers_per_class": {
                "min": min(signer_values),
                "max": max(signer_values),
                "counts_by_class_id": {str(k): len(class_signers[k]) for k in range(236)},
            },
        }
    overlap = sorted(signer_sets["train"] & signer_sets["dev"])
    if overlap:
        raise RuntimeError(f"VNEXT_GOVERNANCE_SIGNER_OVERLAP:{overlap}")
    return {
        "schema": "APPHEAR_VNEXT_GOVERNED_DATASET_AUDIT_V1",
        "status": (
            "PASS"
            if not missing_videos and not missing_spans
            else "BLOCKED_MISSING_GOVERNED_INPUT"
        ),
        "protected_test_accessed": False,
        "vocabulary_classes": len(vocab),
        "vocabulary": dict(sorted(vocab.items(), key=lambda item: item[1])),
        "identities": identities,
        "train": summaries["train"],
        "dev": summaries["dev"],
        "signer_overlap": overlap,
        "missing_raw_video_count": len(missing_videos),
        "missing_raw_video_examples": missing_videos[:20],
        "missing_span_count": len(missing_spans),
        "missing_span_examples": missing_spans[:20],
        "resolved_path_relocations": dict(sorted(relocation_counts.items())),
        "path_relocation_roots": {
            source: [
                {"manifest_root": str(old), "current_root": str(new)} for old, new in mappings
            ]
            for source, mappings in PATH_RELOCATIONS.items()
        },
    }


def governed_rows(split: str) -> list[dict[str, str]]:
    if split == "train":
        return [resolve_row_paths(row) for row in load_rows(TRAIN_MANIFEST)]
    if split == "dev":
        return [resolve_row_paths(row) for row in load_rows(DEV_MANIFEST)]
    raise ValueError("only governed train/dev splits are allowed")
