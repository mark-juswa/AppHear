"""Audit the completed signer/cadence-invariant V2 recognizer without training."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from model.perception_vnext.recognition_utility_236 import sha256, write_json
from model.perception_vnext.recognition_v2_236 import DEFAULT_DATASET, _load_rows
from model.perception_vnext.signer_cadence_invariant_236 import (
    DEFAULT_CONFIG,
    DEFAULT_RUN,
    MILESTONE,
    V2_BASELINE_RUN,
)

SCHEMA = "APPHEAR_VNEXT_INVARIANT_RESULT_AUDIT_V1"


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _finite_history(path: Path) -> list[dict[str, float]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = [
            {key: float(value) for key, value in row.items()}
            for row in csv.DictReader(stream)
        ]
    if not rows or not all(math.isfinite(value) for row in rows for value in row.values()):
        raise RuntimeError("VNEXT_INVARIANT_RESULT_NONFINITE_HISTORY")
    return rows


def _recompute_metrics(metrics: dict[str, Any]) -> dict[str, float | int]:
    matrix = np.asarray(metrics["confusion_matrix"], np.int64)
    if matrix.shape != (236, 236):
        raise RuntimeError("VNEXT_INVARIANT_RESULT_CONFUSION_SHAPE")
    support = matrix.sum(axis=1)
    predicted = matrix.sum(axis=0)
    true_positive = np.diag(matrix)
    recall = np.divide(true_positive, support, out=np.zeros(236), where=support > 0)
    precision = np.divide(true_positive, predicted, out=np.zeros(236), where=predicted > 0)
    f1 = np.divide(
        2 * precision * recall,
        precision + recall,
        out=np.zeros(236),
        where=(precision + recall) > 0,
    )
    return {
        "clips": int(matrix.sum()),
        "top1": float(true_positive.sum() / matrix.sum()),
        "macro_f1": float(np.mean(f1)),
        "zero_recall_classes": int(np.count_nonzero(recall == 0)),
    }


def _validate_evaluation(evaluation: dict[str, Any]) -> dict[str, Any]:
    recomputed: dict[str, Any] = {}
    for split in ("train", "dev"):
        recomputed[split] = {}
        for condition in ("dense", "phone_01_sparse"):
            reported = evaluation["details"][split][condition]
            values = _recompute_metrics(reported)
            if (
                values["clips"] != reported["clips"]
                or abs(float(values["top1"]) - float(reported["top1"])) > 1.0e-12
                or abs(float(values["macro_f1"]) - float(reported["macro_f1"]))
                > 1.0e-12
                or values["zero_recall_classes"]
                != len(reported["zero_recall_classes"])
            ):
                raise RuntimeError(f"VNEXT_INVARIANT_RESULT_METRIC_MISMATCH:{split}:{condition}")
            signer_clips = sum(item["clips"] for item in reported["by_signer"].values())
            if signer_clips != reported["clips"]:
                raise RuntimeError(f"VNEXT_INVARIANT_RESULT_SIGNER_TOTAL:{split}:{condition}")
            recomputed[split][condition] = values
    for split in ("train", "dev"):
        paired = evaluation["dense_sparse_paired_comparison"][split]
        expected = (
            paired["dense_correct_sparse_wrong"] - paired["sparse_correct_dense_wrong"]
        ) / paired["paired_clips"]
        if abs(expected - paired["dense_minus_sparse_top1"]) > 1.0e-12:
            raise RuntimeError(f"VNEXT_INVARIANT_RESULT_PAIRED_MISMATCH:{split}")
    return recomputed


def _load_feature_batch(
    rows: list[dict[str, Any]], condition: str
) -> tuple[np.ndarray, np.ndarray]:
    prefix = "dense" if condition == "dense" else "sparse"
    features: list[np.ndarray] = []
    masks: list[np.ndarray] = []
    for row in rows:
        with np.load(Path(row["feature_path"]), allow_pickle=False) as package:
            features.append(np.asarray(package[f"{prefix}_features"], np.float32))
            masks.append(np.asarray(package[f"{prefix}_mask"], bool))
    return np.stack(features), np.stack(masks)


def _normalize(values: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return values / np.maximum(norms, 1.0e-12)


def _extract_embeddings(
    model: Any,
    rows: list[dict[str, Any]],
    condition: str,
    *,
    candidate: bool,
    batch_size: int,
) -> np.ndarray:
    import tensorflow as tf

    if candidate:
        embedding_model = model
    else:
        embedding_model = tf.keras.Model(
            model.inputs,
            model.get_layer("masked_pool").output,
            name="v2_control_embedding_audit",
        )
    outputs: list[np.ndarray] = []
    for start in range(0, len(rows), batch_size):
        features, masks = _load_feature_batch(rows[start : start + batch_size], condition)
        value = embedding_model([features, masks], training=False)
        if candidate:
            if not isinstance(value, dict):
                raise RuntimeError("VNEXT_INVARIANT_RESULT_CANDIDATE_OUTPUT")
            value = value["embedding"]
        outputs.append(np.asarray(value, np.float32))
    return _normalize(np.concatenate(outputs))


def _summary(values: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95)),
    }


def _train_cross_signer_distance(
    embeddings: np.ndarray, labels: np.ndarray, signers: np.ndarray
) -> dict[str, float]:
    distances: list[float] = []
    for class_id in range(236):
        class_indices = np.flatnonzero(labels == class_id)
        class_embeddings = embeddings[class_indices]
        class_signers = signers[class_indices]
        total = class_embeddings.sum(axis=0)
        signer_sums: dict[str, np.ndarray] = {}
        signer_counts: dict[str, int] = {}
        for signer in np.unique(class_signers):
            selected = class_embeddings[class_signers == signer]
            signer_sums[str(signer)] = selected.sum(axis=0)
            signer_counts[str(signer)] = len(selected)
        for embedding, signer in zip(class_embeddings, class_signers, strict=True):
            count = len(class_embeddings) - signer_counts[str(signer)]
            centroid = (total - signer_sums[str(signer)]) / count
            centroid /= max(float(np.linalg.norm(centroid)), 1.0e-12)
            distances.append(1.0 - float(np.dot(embedding, centroid)))
    return _summary(np.asarray(distances))


def _class_centroid_diagnostic(
    train_embeddings: np.ndarray,
    train_labels: np.ndarray,
    dev_embeddings: np.ndarray,
    dev_labels: np.ndarray,
) -> dict[str, Any]:
    centroids = np.stack(
        [train_embeddings[train_labels == class_id].mean(axis=0) for class_id in range(236)]
    )
    centroids = _normalize(centroids)
    distances = 1.0 - dev_embeddings @ centroids.T
    true_distance = distances[np.arange(len(dev_labels)), dev_labels]
    wrong = distances.copy()
    wrong[np.arange(len(dev_labels)), dev_labels] = np.inf
    nearest_wrong = np.min(wrong, axis=1)
    centroid_distances = 1.0 - centroids @ centroids.T
    np.fill_diagonal(centroid_distances, np.inf)
    nearest_centroid_neighbor = np.min(centroid_distances, axis=1)
    order = np.argsort(distances, axis=1)
    ratio = nearest_wrong / np.maximum(true_distance, 1.0e-12)
    return {
        "true_class_cosine_distance": _summary(true_distance),
        "nearest_wrong_class_cosine_distance": _summary(nearest_wrong),
        "train_class_centroid_nearest_neighbor_distance": _summary(
            nearest_centroid_neighbor
        ),
        "nearest_wrong_over_true_ratio": _summary(ratio),
        "nearest_centroid_top1": float(np.mean(order[:, 0] == dev_labels)),
        "nearest_centroid_top5": float(
            np.mean(
                [
                    label in guesses
                    for label, guesses in zip(dev_labels, order[:, :5], strict=True)
                ]
            )
        ),
    }


def _embedding_audit(
    dataset: Path, candidate_checkpoint: Path, control_checkpoint: Path, batch_size: int
) -> dict[str, Any]:
    import tensorflow as tf

    rows = _load_rows(dataset)
    train_rows = [row for row in rows if row["split"] == "train"]
    dev_rows = [row for row in rows if row["split"] == "dev"]
    train_labels = np.asarray([int(row["class_id"]) for row in train_rows])
    train_signers = np.asarray([str(row["signer_id"]) for row in train_rows])
    dev_labels = np.asarray([int(row["class_id"]) for row in dev_rows])
    candidate_model = tf.keras.models.load_model(candidate_checkpoint, safe_mode=True)
    control_model = tf.keras.models.load_model(control_checkpoint, safe_mode=True)
    result: dict[str, Any] = {}
    for name, model, candidate in (
        ("v2_control", control_model, False),
        ("invariant_candidate", candidate_model, True),
    ):
        train_dense = _extract_embeddings(
            model, train_rows, "dense", candidate=candidate, batch_size=batch_size
        )
        train_sparse = _extract_embeddings(
            model, train_rows, "phone_01_sparse", candidate=candidate, batch_size=batch_size
        )
        dev_dense = _extract_embeddings(
            model, dev_rows, "dense", candidate=candidate, batch_size=batch_size
        )
        dev_sparse = _extract_embeddings(
            model, dev_rows, "phone_01_sparse", candidate=candidate, batch_size=batch_size
        )
        result[name] = {
            "same_clip_dense_sparse_cosine_distance": {
                "train": _summary(1.0 - np.sum(train_dense * train_sparse, axis=1)),
                "dev": _summary(1.0 - np.sum(dev_dense * dev_sparse, axis=1)),
            },
            "train_same_class_other_signer_cosine_distance": {
                "dense": _train_cross_signer_distance(
                    train_dense, train_labels, train_signers
                ),
                "phone_01_sparse": _train_cross_signer_distance(
                    train_sparse, train_labels, train_signers
                ),
            },
            "dev_to_train_class_centroids": {
                "dense": _class_centroid_diagnostic(
                    train_dense, train_labels, dev_dense, dev_labels
                ),
                "phone_01_sparse": _class_centroid_diagnostic(
                    train_sparse, train_labels, dev_sparse, dev_labels
                ),
            },
        }
    return result


def audit(run: Path, dataset: Path, config: Path, *, batch_size: int) -> dict[str, Any]:
    training = _json(run / "training_result.json")
    identity = _json(run / "run_identity.json")
    evaluation = _json(run / "evaluation.json")
    comparison = _json(run / "v2_baseline_comparison.json")
    baseline_evaluation = _json(V2_BASELINE_RUN / "evaluation.json")
    history = _finite_history(run / "history.csv")
    candidate_hash = sha256(run / "best.keras")
    control_hash = sha256(V2_BASELINE_RUN / "best.keras")
    checks = {
        "training_status_pass": training.get("status") == "PASS",
        "full_training_completed": training.get("full_training_executed") is True,
        "epochs_40": len(history) == training.get("epochs_completed") == 40,
        "history_finite": True,
        "best_epoch_matches_history": int(np.argmin([row["val_loss"] for row in history]))
        == training.get("best_epoch_zero_based"),
        "best_val_loss_matches_history": abs(
            min(row["val_loss"] for row in history) - training.get("best_val_loss")
        )
        <= 1.0e-12,
        "config_identity": sha256(config)
        == sha256(run / "reproducibility_config.json")
        == training.get("config_sha256")
        == identity.get("config_sha256"),
        "dataset_identity": sha256(dataset / "contract.json")
        == training.get("dataset_contract_sha256")
        == identity.get("dataset_contract_sha256"),
        "candidate_checkpoint_identity": candidate_hash
        == evaluation.get("checkpoint_sha256")
        == comparison.get("candidate_checkpoint_sha256"),
        "v2_control_identity": control_hash
        == identity.get("v2_baseline_best_sha256")
        == baseline_evaluation.get("checkpoint_sha256")
        == comparison.get("v2_control_checkpoint_sha256"),
        "population_identity": training.get("train_clips") == 3926
        and training.get("dev_clips") == 816
        and training.get("classes") == 236,
        "view_and_batch_budget": training.get("classification_views_per_epoch") == 7852
        and training.get("pair_batches_per_epoch") == [246] * 40,
        "protected_test_untouched": all(
            value.get("protected_test_accessed") is False
            for value in (training, identity, evaluation, comparison, baseline_evaluation)
        ),
    }
    recomputed = _validate_evaluation(evaluation)
    if not all(checks.values()):
        raise RuntimeError(f"VNEXT_INVARIANT_RESULT_INTEGRITY:{checks}")
    embeddings = _embedding_audit(
        dataset, run / "best.keras", V2_BASELINE_RUN / "best.keras", batch_size
    )
    control = baseline_evaluation["details"]
    candidate = evaluation["details"]
    deltas: dict[str, Any] = {}
    for split in ("train", "dev"):
        deltas[split] = {}
        for condition in ("dense", "phone_01_sparse"):
            deltas[split][condition] = {
                metric: float(
                    candidate[split][condition][metric]
                    - control[split][condition][metric]
                )
                for metric in ("top1", "top5", "macro_f1")
            }
            deltas[split][condition]["zero_recall_delta"] = len(
                candidate[split][condition]["zero_recall_classes"]
            ) - len(control[split][condition]["zero_recall_classes"])
    candidate_penalty = (
        candidate["dev"]["dense"]["top1"]
        - candidate["dev"]["phone_01_sparse"]["top1"]
    )
    control_penalty = control["dev"]["dense"]["top1"] - control["dev"][
        "phone_01_sparse"
    ]["top1"]
    result = {
        "schema": SCHEMA,
        "milestone": MILESTONE,
        "status": "PASS",
        "scientific_classification": "SIGNER_CADENCE_INVARIANT_NOT_SUPPORTED",
        "confidence": "high_for_this_fixed_candidate",
        "integrity_checks": checks,
        "artifact_hashes": {
            "candidate_best_sha256": candidate_hash,
            "v2_control_best_sha256": control_hash,
            "config_sha256": sha256(config),
            "dataset_contract_sha256": sha256(dataset / "contract.json"),
            "evaluation_sha256": sha256(run / "evaluation.json"),
        },
        "history": {
            "epochs": len(history),
            "best_epoch_zero_based": training["best_epoch_zero_based"],
            "best_epoch_human": training["best_epoch_zero_based"] + 1,
            "best_val_loss": training["best_val_loss"],
            "first_epoch": history[0],
            "best_epoch": history[training["best_epoch_zero_based"]],
            "final_epoch": history[-1],
        },
        "recomputed_evaluation": recomputed,
        "matched_deltas_candidate_minus_v2_control": deltas,
        "dev_cadence_top1_penalty": {
            "v2_control": float(control_penalty),
            "candidate": float(candidate_penalty),
            "delta": float(candidate_penalty - control_penalty),
        },
        "embedding_diagnostic": embeddings,
        "full_training_executed": True,
        "protected_test_accessed": False,
    }
    write_json(run / "signer_cadence_invariant_decision.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    result = audit(
        args.run.resolve(),
        args.dataset.resolve(),
        args.config.resolve(),
        batch_size=args.batch_size,
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
