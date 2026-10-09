"""Prepare validation baseline, real-train augmentation audit, and RCA-C provenance."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import numpy as np
import tensorflow as tf

from model.p5b_rcac_augmentation import (
    PREP,
    ROOT,
    VALIDATION_BASELINE,
    atomic_json,
    augment_sample_tf,
    load_split,
    sha256,
    validation_metrics,
)

RCAB_BEST = (
    ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5b_rcab_horizon_01/best.keras"
)
EXPECTED_RCAB_BEST = "3b858ca530b616c0d02ca2eee1d30678d092a039c36e9da38ec5f3d491a94a4c"
TRAINER = ROOT / "model/p5b_rcac_augmentation.py"
RUNBOOK = ROOT / "context/recognition_upgrade/P5B_RCAC_RUNBOOK.md"


def validation_baseline() -> int:
    if sha256(RCAB_BEST) != EXPECTED_RCAB_BEST:
        raise RuntimeError("P5B_RCAC_RCAB_CHECKPOINT_MISMATCH")
    model = tf.keras.models.load_model(RCAB_BEST, safe_mode=False)
    result = validation_metrics(model)
    result.update(
        {
            "identity": "RCA-B validation-selected checkpoint on frozen primary validation",
            "checkpoint_sha256": EXPECTED_RCAB_BEST,
            "protected_test_accessed": False,
            "frozen_before_rcac_training": True,
        }
    )
    atomic_json(VALIDATION_BASELINE, result)
    print(
        json.dumps(
            {
                "passed": True,
                "rows": result["rows"],
                "top1": result["top1"],
                "top5": result["top5"],
                "macro_f1": result["macro_f1"],
                "per_frame": result["per_frame"],
                "protected_test_accessed": False,
            },
            indent=2,
        )
    )
    return 0


def _fractions(x: np.ndarray, mask: np.ndarray) -> tuple[float, float, float]:
    real = mask.astype(bool)
    count = max(int(real.sum()), 1)
    left = x[:, 236] > 0.5
    right = x[:, 237] > 0.5
    return (
        float((left & real).sum() / count),
        float((right & real).sum() / count),
        float((left & right & real).sum() / count),
    )


def audit_samples() -> int:
    x, _, mask, ids, signers = load_split("train")
    rows = []
    for index in range(len(x)):
        left, right, both = _fractions(x[index], mask[index])
        rows.append(
            {
                "index": index,
                "id": str(ids[index]),
                "signer": str(signers[index]),
                "length": int(mask[index].sum()),
                "left": left,
                "right": right,
                "both": both,
            }
        )
    rows.sort(key=lambda row: row["id"])
    predicates = {
        "one_handed": lambda row: (
            (row["left"] >= 0.7 and row["right"] <= 0.3)
            or (row["right"] >= 0.7 and row["left"] <= 0.3)
        ),
        "two_handed": lambda row: row["both"] >= 0.9,
        "left_dominant": lambda row: row["left"] - row["right"] >= 0.25,
        "right_dominant": lambda row: row["right"] - row["left"] >= 0.25,
        "weak_or_missing": lambda row: row["both"] < 0.5,
    }
    selected: list[tuple[str, dict[str, object]]] = []
    used: set[int] = set()
    for category, predicate in predicates.items():
        candidate = next(
            (row for row in rows if predicate(row) and int(row["index"]) not in used), None
        )
        if candidate is None:
            raise RuntimeError(f"P5B_RCAC_NO_TRAIN_AUDIT_SAMPLE_{category.upper()}")
        selected.append((category, candidate))
        used.add(int(candidate["index"]))
    short = min(
        (row for row in rows if int(row["index"]) not in used),
        key=lambda row: (int(row["length"]), row["id"]),
    )
    selected.append(("short_sequence", short))
    used.add(int(short["index"]))
    near = min(
        (row for row in rows if int(row["index"]) not in used),
        key=lambda row: (abs(96 - int(row["length"])), row["id"]),
    )
    selected.append(("near_96_sequence", near))

    results = []
    for occurrence, (category, row) in enumerate(selected, start=7000):
        index = int(row["index"])
        augmented_tensor, aug_mask_tensor = augment_sample_tf(x[index], mask[index], occurrence)
        augmented, aug_mask = augmented_tensor.numpy(), aug_mask_tensor.numpy()
        valid_xy = []
        for start, end, points in ((0, 84, 21), (84, 168, 21), (168, 236, 17)):
            block = augmented[:, start:end].reshape(96, points, 4)
            valid_xy.append(block[block[..., 3] > 0.5][..., :2])
        coordinates = np.concatenate(
            [part.reshape(-1, 2) for part in valid_xy if len(part)], axis=0
        )
        results.append(
            {
                "category": category,
                "sample_id": row["id"],
                "signer": row["signer"],
                "original_length": int(row["length"]),
                "augmented_length": int(aug_mask.sum()),
                "left_observed_fraction": row["left"],
                "right_observed_fraction": row["right"],
                "both_observed_fraction": row["both"],
                "shape": list(augmented.shape),
                "finite": bool(np.isfinite(augmented).all()),
                "padding_zero": bool(np.count_nonzero(augmented[~aug_mask]) == 0),
                "max_abs_valid_xy": float(np.max(np.abs(coordinates))) if len(coordinates) else 0.0,
                "occurrence_seed": occurrence,
            }
        )
    payload = {
        "source": "frozen training split only",
        "protected_test_accessed": False,
        "selection": "deterministic by runtime observation profile, length, and sample ID",
        "samples": results,
        "passed": all(
            item["finite"]
            and item["padding_zero"]
            and item["shape"] == [96, 238]
            and item["max_abs_valid_xy"] < 10
            for item in results
        ),
    }
    atomic_json(PREP / "p5b_rcac_real_train_augmentation_audit.json", payload)
    print(json.dumps(payload, indent=2))
    return 0 if payload["passed"] else 2


def environment() -> int:
    payload = {
        "python": sys.version,
        "platform": platform.platform(),
        "tensorflow": tf.__version__,
        "keras": tf.keras.__version__,
        "numpy": np.__version__,
        "backend": "CPU / oneDNN disabled by RCA-C trainer",
        "protected_test_accessed": False,
    }
    atomic_json(PREP / "environment_manifest.json", payload)
    print(json.dumps(payload, indent=2))
    return 0


def hash_manifest() -> int:
    paths = sorted(
        path
        for path in PREP.iterdir()
        if path.is_file() and path.name != "artifact_hash_manifest.json"
    )
    paths.extend([TRAINER, Path(__file__)])
    if RUNBOOK.is_file():
        paths.append(RUNBOOK)
    payload = {
        "scope": "P5-B RCA-C preparation only",
        "full_training_run": False,
        "protected_test_accessed": False,
        "artifacts": [
            {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in paths
        ],
    }
    atomic_json(PREP / "artifact_hash_manifest.json", payload)
    print(json.dumps({"passed": True, "hashed": len(paths)}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["validation-baseline", "audit-samples", "environment", "hash-manifest"]
    )
    command = parser.parse_args().command
    if command == "validation-baseline":
        return validation_baseline()
    if command == "audit-samples":
        return audit_samples()
    if command == "environment":
        return environment()
    return hash_manifest()


if __name__ == "__main__":
    raise SystemExit(main())
