"""Prepare the bounded TRAIN-only Android recognition-v2 parity corpus.

This command never reads DEV or protected TEST. It selects governed raw-v1 TRAIN clips by
structural observation properties, writes Python recognition-v2 golden tensors, and records
Gate-0 deployment identities. It does not run perception, training, or model conversion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.perception_vnext.recognition_schema import RAW_SCHEMA, load_raw_sequence
from pipeline.perception_vnext.recognition_schema_v2 import (
    FEATURE_LAYOUT_V2,
    FEATURE_SCHEMA_V2,
    FEATURE_WIDTH_V2,
    temporal_view_v2,
)

MILESTONE = "PHASE_4A_ANDROID_V2_PARITY_01"
PHONE_FPS = 5.606840672873506
TOLERANCE = 1.0e-5
EXPECTED_CHECKPOINT_SHA = (
    "8107accbc621ae5652766fec80d314fe8dc9f94ba0d0548a6aef80ed91729340"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def structural_stats(path: Path) -> dict[str, Any]:
    raw = load_raw_sequence(path)
    observed = raw.hand_observed.astype(bool)
    effective = raw.hand_joint_valid.astype(bool) & observed[:, :, None]
    required = effective[:, :, [0, 5, 9, 17]].all(axis=-1)
    return {
        "path": path,
        "sample_id": str(raw.metadata["sample_id"]),
        "frames": int(len(raw.frame_index)),
        "left_only": int(np.count_nonzero(observed[:, 0] & ~observed[:, 1])),
        "right_only": int(np.count_nonzero(~observed[:, 0] & observed[:, 1])),
        "both": int(np.count_nonzero(observed.all(axis=1))),
        "neither": int(np.count_nonzero(~observed.any(axis=1))),
        "body_unavailable": int(np.count_nonzero(~raw.body_available.astype(bool))),
        "invalid_observed_joints": int(
            np.count_nonzero(observed[:, :, None] & ~raw.hand_joint_valid.astype(bool))
        ),
        "missing_hand_reference": int(np.count_nonzero(observed & ~required)),
        "body_reference_unavailable": int(
            np.count_nonzero(
                ~(
                    (raw.body_valid[:, 0] & raw.body_valid[:, 1])
                    | (raw.body_valid[:, 6] & raw.body_valid[:, 7])
                )
            )
        ),
    }


def choose_corpus(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Greedy, deterministic, structural-only selection with lexical identity ignored."""

    selectors = [
        ("shortest", lambda row: True, lambda row: (row["frames"], row["sample_id"])),
        ("longest", lambda row: True, lambda row: (-row["frames"], row["sample_id"])),
        ("near_96", lambda row: True, lambda row: (abs(row["frames"] - 96), row["sample_id"])),
        (
            "left_only_coverage",
            lambda row: row["left_only"] > 0,
            lambda row: (-row["left_only"] / row["frames"], row["sample_id"]),
        ),
        (
            "right_only_coverage",
            lambda row: row["right_only"] > 0,
            lambda row: (-row["right_only"] / row["frames"], row["sample_id"]),
        ),
        (
            "two_hand_coverage",
            lambda row: row["both"] > 0,
            lambda row: (-row["both"] / row["frames"], row["sample_id"]),
        ),
        (
            "no_hand_coverage",
            lambda row: row["neither"] > 0,
            lambda row: (-row["neither"] / row["frames"], row["sample_id"]),
        ),
        (
            "body_unavailable",
            lambda row: row["body_unavailable"] > 0,
            lambda row: (-row["body_unavailable"], row["sample_id"]),
        ),
        (
            "invalid_hand_joints",
            lambda row: row["invalid_observed_joints"] > 0,
            lambda row: (-row["invalid_observed_joints"], row["sample_id"]),
        ),
        (
            "missing_hand_reference",
            lambda row: row["missing_hand_reference"] > 0,
            lambda row: (-row["missing_hand_reference"], row["sample_id"]),
        ),
        (
            "body_reference_unavailable",
            lambda row: row["body_reference_unavailable"] > 0,
            lambda row: (-row["body_reference_unavailable"], row["sample_id"]),
        ),
    ]
    chosen: list[dict[str, Any]] = []
    used: set[str] = set()
    for reason, eligible, key in selectors:
        for row in sorted((row for row in rows if eligible(row)), key=key):
            if row["sample_id"] not in used:
                value = dict(row)
                value["selection_reason"] = reason
                chosen.append(value)
                used.add(row["sample_id"])
                break
    return chosen


def json_array(value: np.ndarray) -> list[Any]:
    flat = np.asarray(value).reshape(-1)
    if flat.dtype.kind == "b":
        return [bool(item) for item in flat]
    if flat.dtype.kind in "iu":
        return [int(item) for item in flat]
    return [float(item) for item in flat]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def prepare(repo: Path) -> None:
    base = repo / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
    train_raw = base / "dataset/raw/train"
    checkpoint = base / "tcn_v2_run_01/best.keras"
    vocabulary = repo / "artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1/vocab.json"
    raw_contract = base / "dataset/contract.json"
    v2_contract = base / "representation_v2_236_production_01/dataset/contract.json"
    v2_code = repo / "pipeline/perception_vnext/recognition_schema_v2.py"
    run_identity = base / "tcn_v2_run_01/run_identity.json"
    artifact_root = base / "phase4a_android_v2_parity_01"
    asset_root = repo / "android/app/src/debug/assets/phase4a_v2_parity"

    for required in (train_raw, checkpoint, vocabulary, raw_contract, v2_contract, v2_code, run_identity):
        if not required.exists():
            raise FileNotFoundError(required)
    checkpoint_sha = sha256(checkpoint)
    if checkpoint_sha != EXPECTED_CHECKPOINT_SHA:
        raise RuntimeError(
            f"GATE0_CHECKPOINT_IDENTITY_FAILURE:{checkpoint_sha}:{EXPECTED_CHECKPOINT_SHA}"
        )
    vocabulary_value = json.loads(vocabulary.read_text(encoding="utf-8"))
    if len(vocabulary_value) != 236 or set(vocabulary_value.values()) != set(range(236)):
        raise RuntimeError("GATE0_VOCABULARY_IDENTITY_FAILURE")

    raw_files = sorted(train_raw.glob("*.npz"))
    if len(raw_files) != 3926:
        raise RuntimeError(f"GATE0_TRAIN_RAW_COUNT_FAILURE:{len(raw_files)}")
    rows = [structural_stats(path) for path in raw_files]
    selected = choose_corpus(rows)

    fixtures: list[dict[str, Any]] = []
    for fixture_index, selection in enumerate(selected, start=1):
        raw = load_raw_sequence(selection["path"])
        if raw.metadata.get("split") != "train":
            raise RuntimeError("NON_TRAIN_FIXTURE_REJECTED")
        fixture_id = f"p4a_v2_{fixture_index:02d}"
        raw_name = f"{fixture_id}_raw.json"
        raw_path = asset_root / raw_name
        raw_payload = {
            "schema": str(raw.metadata["schema"]),
            "image_semantics": str(raw.metadata["image_semantics"]),
            "frame_index": json_array(raw.frame_index),
            "timestamp_ms": json_array(raw.timestamp_ms),
            "source_size": json_array(raw.source_size),
            "hand_xy": json_array(raw.hand_xy.astype(np.float32)),
            "hand_proposal_support": json_array(raw.hand_proposal_support.astype(np.float32)),
            "hand_joint_valid": json_array(raw.hand_joint_valid.astype(bool)),
            "hand_presence": json_array(raw.hand_presence.astype(np.float32)),
            "hand_observed": json_array(raw.hand_observed.astype(bool)),
            "body_xy": json_array(raw.body_xy.astype(np.float32)),
            "body_support": json_array(raw.body_support.astype(np.float32)),
            "body_valid": json_array(raw.body_valid.astype(bool)),
            "body_available": json_array(raw.body_available.astype(bool)),
        }
        write_json(raw_path, raw_payload)
        fixture = {
            "fixture_id": fixture_id,
            "sample_id": str(raw.metadata["sample_id"]),
            "selection_reason": selection["selection_reason"],
            "structural_stats": {
                key: value
                for key, value in selection.items()
                if key not in {"path", "sample_id", "selection_reason"}
            },
            "raw_asset": f"phase4a_v2_parity/{raw_name}",
            "raw_sha256": sha256(raw_path),
            "views": {},
        }
        for condition, kotlin_name in (
            ("dense", "DENSE"),
            ("phone_01_sparse", "PHONE_01_SPARSE"),
        ):
            view = temporal_view_v2(
                raw, condition=condition, phone_completed_fps=PHONE_FPS
            )
            if not np.all(np.isfinite(view["features"])):
                raise RuntimeError(f"NONFINITE_GOLDEN:{fixture_id}:{condition}")
            tensor_name = f"{fixture_id}_{condition}.f32"
            tensor_path = asset_root / tensor_name
            tensor_path.parent.mkdir(parents=True, exist_ok=True)
            tensor_path.write_bytes(np.asarray(view["features"], dtype="<f4").tobytes())
            fixture["views"][condition] = {
                "kotlin_condition": kotlin_name,
                "tensor_asset": f"phase4a_v2_parity/{tensor_name}",
                "tensor_sha256": sha256(tensor_path),
                "source_indices": json_array(view["source_indices"]),
                "source_timestamps_ms": json_array(view["source_timestamps_ms"]),
                "mask": json_array(view["mask"]),
                "real_length": int(view["real_length"]),
            }
        fixtures.append(fixture)

    manifest = {
        "milestone": MILESTONE,
        "raw_schema": RAW_SCHEMA,
        "feature_schema": FEATURE_SCHEMA_V2,
        "shape": [96, FEATURE_WIDTH_V2],
        "phone_completed_fps": PHONE_FPS,
        "preregistered_max_abs_tolerance": TOLERANCE,
        "feature_groups": [
            {"name": name, "start": start, "end_exclusive": end}
            for name, start, end in FEATURE_LAYOUT_V2
        ],
        "selection_policy": "deterministic TRAIN-only structural observation coverage",
        "train_raw_population": len(raw_files),
        "dev_accessed": False,
        "protected_test_accessed": False,
        "fixtures": fixtures,
    }
    manifest_path = asset_root / "manifest.json"
    write_json(manifest_path, manifest)
    manifest_sha = sha256(manifest_path)

    gate0 = {
        "milestone": MILESTONE,
        "status": "PASS",
        "candidate01_raw_schema": RAW_SCHEMA,
        "candidate01_raw_contract": str(raw_contract.resolve()),
        "candidate01_raw_contract_sha256": sha256(raw_contract),
        "recognition_v2_schema": FEATURE_SCHEMA_V2,
        "recognition_v2_contract": str(v2_contract.resolve()),
        "recognition_v2_contract_sha256": sha256(v2_contract),
        "recognition_v2_python": str(v2_code.resolve()),
        "recognition_v2_python_sha256": sha256(v2_code),
        "input_shape": [96, FEATURE_WIDTH_V2],
        "vocabulary_path": str(vocabulary.resolve()),
        "vocabulary_sha256": sha256(vocabulary),
        "classes": 236,
        "class_id_to_canonical_gloss": [
            gloss for gloss, class_id in sorted(vocabulary_value.items(), key=lambda item: item[1])
        ],
        "active_checkpoint_path": str(checkpoint.resolve()),
        "active_checkpoint_sha256": checkpoint_sha,
        "recognizer_outputs": 236,
        "run_identity_path": str(run_identity.resolve()),
        "run_identity_sha256": sha256(run_identity),
        "invariant_candidate_selected": False,
        "balanced_sampler_candidate_selected": False,
        "android_candidate01": [
            "android/app/src/debug/java/com/example/apphear/perceptionvnext/PerceptionVNextRunners.kt",
            "android/app/src/debug/java/com/example/apphear/perceptionvnext/PerceptionVNextMath.kt",
            "android/app/src/debug/java/com/example/apphear/perceptionvnext/PerceptionVNextFixtureActivity.kt",
        ],
        "reused_parity_pattern": [
            "android/app/src/debug/java/com/example/apphear/p8b/P8bGoldenVerifier.kt",
            "android/app/src/androidTest/java/com/example/apphear/p8b/P8bGoldenInstrumentedTest.kt",
        ],
        "parity_manifest_path": str(manifest_path.resolve()),
        "parity_manifest_sha256": manifest_sha,
        "dev_accessed": False,
        "protected_test_accessed": False,
    }
    write_json(artifact_root / "gate0_deployment_identity.json", gate0)
    write_json(artifact_root / "parity_corpus_manifest.json", manifest)
    print(
        json.dumps(
            {
                "status": "PASS",
                "fixtures": len(fixtures),
                "dense_views": len(fixtures),
                "sparse_views": len(fixtures),
                "checkpoint_sha256": checkpoint_sha,
                "vocabulary_sha256": sha256(vocabulary),
                "manifest_sha256": manifest_sha,
            },
            indent=2,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    prepare(args.repo.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
