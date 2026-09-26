"""One signer/cadence-invariant objective over frozen recognition-v2.

Every TRAIN clip remains one clip-uniform anchor per epoch. Pair-aware batches
place same-class clips from distinct real signers together without changing
clip membership or materializing a pair corpus. Classification still sees the
exact dense+sparse view pair once per anchor clip; supervised contrastive and
dense/sparse cosine consistency losses act on the shared sequence embedding.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import json
import math
import shutil
from collections import defaultdict
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np

from model.perception_vnext.recognition_utility_236 import sha256, write_json
from model.perception_vnext.recognition_v2_236 import (
    BASE,
    DEFAULT_DATASET,
    VOCAB_MANIFEST,
    _load_rows,
    evaluate,
)
from pipeline.perception_vnext.recognition_schema import MAX_SEQUENCE_LENGTH, RAW_SCHEMA
from pipeline.perception_vnext.recognition_schema_v2 import FEATURE_SCHEMA_V2, FEATURE_WIDTH_V2

MILESTONE = "PERCEPTION_VNEXT_SIGNER_CADENCE_INVARIANT_RECOGNIZER_236_01"
ROOT = Path(__file__).resolve().parents[2]
V2_BASELINE_CONFIG = (
    ROOT
    / "model"
    / "config"
    / "recognition_upgrade"
    / "perception_vnext_representation_v2_236_production_01.json"
)
DEFAULT_CONFIG = (
    ROOT
    / "model"
    / "config"
    / "recognition_upgrade"
    / "perception_vnext_signer_cadence_invariant_recognizer_236_01.json"
)
V2_BASELINE_RUN = BASE / "tcn_v2_run_01"
DEFAULT_RUN = BASE / "tcn_signer_cadence_invariant_01"


def _load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    baseline = json.loads(V2_BASELINE_CONFIG.read_text(encoding="utf-8-sig"))
    if (
        config.get("milestone") != MILESTONE
        or config.get("raw_schema") != RAW_SCHEMA
        or config.get("feature_schema") != FEATURE_SCHEMA_V2
        or config.get("input_shape") != [MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2]
        or config.get("classes") != 236
        or config.get("governance", {}).get("protected_test_access") is not False
    ):
        raise RuntimeError("VNEXT_INVARIANT_CONFIG_CONTRACT")
    for field in ("seed", "raw_schema", "feature_schema", "input_shape", "classes", "model"):
        if config.get(field) != baseline.get(field):
            raise RuntimeError(f"VNEXT_INVARIANT_FROZEN_DELTA:{field}")
    for field in (
        "epochs",
        "batch_size",
        "learning_rate",
        "weight_decay",
        "early_stop_patience",
        "train_conditions",
        "condition_weighting",
        "validation_conditions",
        "selection_metric",
    ):
        if config.get("training", {}).get(field) != baseline.get("training", {}).get(field):
            raise RuntimeError(f"VNEXT_INVARIANT_TRAINING_DELTA:{field}")
    if config.get("governance") != baseline.get("governance"):
        raise RuntimeError("VNEXT_INVARIANT_GOVERNANCE_DELTA")
    if config.get("runtime_scope") != baseline.get("runtime_scope"):
        raise RuntimeError("VNEXT_INVARIANT_RUNTIME_SCOPE_DELTA")
    objective = config.get("invariant_objective", {})
    expected = {
        "schema": "apphear.perception_vnext.invariant_objective.v1",
        "embedding": "l2_normalized_masked_tcn_pool_64",
        "classification_weight": 1.0,
        "supervised_contrastive_weight": 0.2,
        "dense_sparse_consistency_weight": 0.2,
        "temperature": 0.1,
        "pair_batch_clip_limit": 16,
        "positive_rule": "same_class_different_train_signer",
        "classification_exposure": "each_train_clip_dense_plus_sparse_once_per_epoch",
    }
    if objective != expected:
        raise RuntimeError("VNEXT_INVARIANT_OBJECTIVE_CONTRACT")
    if config.get("training_sampler") is not None:
        raise RuntimeError("VNEXT_INVARIANT_BALANCED_SAMPLER_FORBIDDEN")
    return config


def _class_groups(
    rows: list[dict[str, Any]], rng: np.random.Generator
) -> list[list[dict[str, Any]]]:
    by_signer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_signer[row["signer_id"]].append(row)
    for values in by_signer.values():
        rng.shuffle(values)
    total = len(rows)
    maximum = max(len(values) for values in by_signer.values())
    if len(by_signer) < 2 or maximum * 2 > total:
        raise RuntimeError(f"VNEXT_INVARIANT_UNPAIRABLE_CLASS:{rows[0]['class_id']}")
    heap = [(-len(values), signer) for signer, values in by_signer.items()]
    heapq.heapify(heap)
    groups: list[list[dict[str, Any]]] = []
    if total % 2:
        chosen: list[tuple[int, str]] = [heapq.heappop(heap) for _ in range(3)]
        groups.append([by_signer[signer].pop() for _, signer in chosen])
        for count, signer in chosen:
            if count + 1 < 0:
                heapq.heappush(heap, (count + 1, signer))
    while heap:
        if len(heap) < 2:
            raise RuntimeError(f"VNEXT_INVARIANT_PAIRING_REMAINDER:{rows[0]['class_id']}")
        left_count, left_signer = heapq.heappop(heap)
        right_count, right_signer = heapq.heappop(heap)
        groups.append([by_signer[left_signer].pop(), by_signer[right_signer].pop()])
        if left_count + 1 < 0:
            heapq.heappush(heap, (left_count + 1, left_signer))
        if right_count + 1 < 0:
            heapq.heappush(heap, (right_count + 1, right_signer))
    if sum(len(group) for group in groups) != total:
        raise AssertionError("pair grouping lost clips")
    return groups


def paired_batches(
    rows: list[dict[str, Any]],
    *,
    seed: int,
    epoch: int,
    clip_limit: int,
) -> list[list[dict[str, Any]]]:
    """Use every row once while guaranteeing a cross-signer positive in-batch."""

    if clip_limit < 4:
        raise ValueError("pair batch clip limit must be at least four")
    rng = np.random.default_rng(np.random.SeedSequence([seed, epoch, 0x534349]))
    by_class: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("split") != "train":
            raise RuntimeError("VNEXT_INVARIANT_NONTRAIN_PAIR")
        by_class[int(row["class_id"])].append(row)
    groups: list[list[dict[str, Any]]] = []
    for class_id in sorted(by_class):
        groups.extend(_class_groups(by_class[class_id], rng))

    triple_groups = [group for group in groups if len(group) == 3]
    pair_groups = [group for group in groups if len(group) == 2]
    total = len(rows)
    full_batches, remainder = divmod(total, clip_limit)
    targets = [clip_limit] * full_batches
    if remainder >= 4:
        targets.append(remainder)
    elif remainder:
        if not targets:
            raise RuntimeError("VNEXT_INVARIANT_BATCH_TOO_SMALL")
        targets[-1] -= 4 - remainder
        targets.append(4)

    @cache
    def allocation(
        batch_index: int, triples_left: int, pairs_left: int
    ) -> tuple[tuple[int, int], ...] | None:
        if batch_index == len(targets):
            return () if triples_left == 0 and pairs_left == 0 else None
        target = targets[batch_index]
        for triple_count in range(min(triples_left, target // 3) + 1):
            residual = target - 3 * triple_count
            if residual < 0 or residual % 2:
                continue
            pair_count = residual // 2
            if pair_count > pairs_left or triple_count + pair_count < 2:
                continue
            tail = allocation(
                batch_index + 1,
                triples_left - triple_count,
                pairs_left - pair_count,
            )
            if tail is not None:
                return ((triple_count, pair_count), *tail)
        return None

    plan = allocation(0, len(triple_groups), len(pair_groups))
    if plan is None:
        raise RuntimeError("VNEXT_INVARIANT_EXACT_BATCH_PACKING")
    batches: list[list[dict[str, Any]]] | None = None
    for _ in range(100):
        rng.shuffle(triple_groups)
        rng.shuffle(pair_groups)
        triple_cursor = 0
        pair_cursor = 0
        flat: list[list[dict[str, Any]]] = []
        for triple_count, pair_count in plan:
            selected = triple_groups[triple_cursor : triple_cursor + triple_count]
            selected += pair_groups[pair_cursor : pair_cursor + pair_count]
            triple_cursor += triple_count
            pair_cursor += pair_count
            rng.shuffle(selected)
            flat.append([row for group in selected for row in group])
        if all(len({int(row["class_id"]) for row in batch}) >= 2 for batch in flat):
            batches = flat
            break
    if batches is None:
        raise RuntimeError("VNEXT_INVARIANT_NEGATIVE_BATCH_CONSTRUCTION")

    seen = [row["sample_id"] for batch in batches for row in batch]
    if len(seen) != len(rows) or len(set(seen)) != len(rows):
        raise RuntimeError("VNEXT_INVARIANT_CLIP_EXPOSURE")
    for batch in batches:
        for row in batch:
            positives = [
                other
                for other in batch
                if int(other["class_id"]) == int(row["class_id"])
                and other["signer_id"] != row["signer_id"]
            ]
            if not positives:
                raise RuntimeError(f"VNEXT_INVARIANT_POSITIVE_MISSING:{row['sample_id']}")
    return batches


def _load_view_batch(
    rows: list[dict[str, Any]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    dense: list[np.ndarray] = []
    sparse: list[np.ndarray] = []
    dense_mask: list[np.ndarray] = []
    sparse_mask: list[np.ndarray] = []
    labels: list[int] = []
    signers: list[str] = []
    for row in rows:
        with np.load(Path(row["feature_path"]), allow_pickle=False) as package:
            metadata = json.loads(str(package["metadata_json"].item()))
            if (
                metadata.get("schema") != FEATURE_SCHEMA_V2
                or metadata.get("sample_id") != row["sample_id"]
                or metadata.get("signer_id") != row["signer_id"]
                or int(metadata.get("class_id", -1)) != int(row["class_id"])
            ):
                raise RuntimeError(f"VNEXT_INVARIANT_FEATURE_IDENTITY:{row['sample_id']}")
            dense.append(np.asarray(package["dense_features"], np.float32))
            sparse.append(np.asarray(package["sparse_features"], np.float32))
            dense_mask.append(np.asarray(package["dense_mask"], bool))
            sparse_mask.append(np.asarray(package["sparse_mask"], bool))
        labels.append(int(row["class_id"]))
        signers.append(row["signer_id"])
    return (
        np.stack(dense),
        np.stack(dense_mask),
        np.stack(sparse),
        np.stack(sparse_mask),
        np.asarray(labels, np.int32),
        np.asarray(signers, object),
    )


def build_model(config: dict[str, Any]) -> Any:
    import tensorflow as tf

    from model.model import build_encoder

    model_config = config["model"]
    features = tf.keras.Input(
        (MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2), dtype="float32", name="features"
    )
    mask = tf.keras.Input((MAX_SEQUENCE_LENGTH,), dtype="bool", name="frame_mask")
    encoder = build_encoder(
        MAX_SEQUENCE_LENGTH,
        FEATURE_WIDTH_V2,
        int(model_config["blocks"]),
        int(model_config["channels"]),
        tuple(int(value) for value in model_config["dilations"]),
        int(model_config["kernel"]),
        float(model_config["dropout"]),
    )
    encoded = encoder(features)
    pooled = tf.keras.layers.GlobalAveragePooling1D(name="masked_pool")(encoded, mask=mask)
    embedding = tf.keras.layers.UnitNormalization(axis=-1, name="sequence_embedding")(pooled)
    probabilities = tf.keras.layers.Dense(
        236, activation="softmax", name="gloss_probabilities"
    )(pooled)
    model = tf.keras.Model(
        [features, mask],
        {"probabilities": probabilities, "embedding": embedding},
        name="vnext_v2_signer_cadence_invariant_tcn",
    )
    model.compile(
        optimizer=tf.keras.optimizers.AdamW(
            learning_rate=float(config["training"]["learning_rate"]),
            weight_decay=float(config["training"]["weight_decay"]),
        )
    )
    return model


def _supervised_contrastive_loss(
    embedding: Any,
    labels: Any,
    signers: np.ndarray,
    temperature: float,
) -> Any:
    import tensorflow as tf

    logits = tf.matmul(embedding, embedding, transpose_b=True) / tf.cast(
        temperature, embedding.dtype
    )
    count = tf.shape(logits)[0]
    self_mask = tf.eye(count, dtype=tf.bool)
    labels = tf.reshape(labels, (-1, 1))
    same_class = tf.equal(labels, tf.transpose(labels))
    signer_same = tf.convert_to_tensor(signers[:, None] == signers[None, :])
    signer_different = ~signer_same
    positive = same_class & signer_different & ~self_mask
    # Same-class clips from the same signer are neither valid invariance positives
    # nor negative signs. Exclude them from the contrastive denominator so the
    # objective never pushes two performances of the same gloss apart merely
    # because they came from the same signer.
    denominator = ~self_mask & ~(same_class & signer_same)
    logits = tf.where(denominator, logits, tf.cast(-1.0e9, logits.dtype))
    positive_count = tf.reduce_sum(tf.cast(positive, logits.dtype), axis=1)
    if bool(tf.reduce_any(positive_count <= 0)):
        raise RuntimeError("VNEXT_INVARIANT_BATCH_WITHOUT_POSITIVE")
    log_probability = logits - tf.reduce_logsumexp(logits, axis=1, keepdims=True)
    per_anchor = -tf.reduce_sum(
        tf.cast(positive, logits.dtype) * log_probability, axis=1
    ) / positive_count
    return tf.reduce_mean(per_anchor)


def _step(
    model: Any,
    batch: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    objective: dict[str, Any],
) -> dict[str, float]:
    import tensorflow as tf

    dense, dense_mask, sparse, sparse_mask, labels, signers = batch
    features = tf.convert_to_tensor(np.concatenate([dense, sparse]), tf.float32)
    masks = tf.convert_to_tensor(np.concatenate([dense_mask, sparse_mask]), tf.bool)
    labels_tensor = tf.convert_to_tensor(labels, tf.int32)
    with tf.GradientTape() as tape:
        output = model([features, masks], training=True)
        probabilities = output["probabilities"]
        embeddings = output["embedding"]
        size = len(labels)
        dense_probability, sparse_probability = probabilities[:size], probabilities[size:]
        dense_embedding, sparse_embedding = embeddings[:size], embeddings[size:]
        classification = 0.5 * (
            tf.reduce_mean(
                tf.keras.losses.sparse_categorical_crossentropy(
                    labels_tensor, dense_probability
                )
            )
            + tf.reduce_mean(
                tf.keras.losses.sparse_categorical_crossentropy(
                    labels_tensor, sparse_probability
                )
            )
        )
        clip_embedding = tf.math.l2_normalize(
            dense_embedding + sparse_embedding, axis=-1
        )
        metric = _supervised_contrastive_loss(
            clip_embedding,
            labels_tensor,
            signers,
            float(objective["temperature"]),
        )
        consistency = tf.reduce_mean(
            1.0 - tf.reduce_sum(dense_embedding * sparse_embedding, axis=-1)
        )
        total = (
            float(objective["classification_weight"]) * classification
            + float(objective["supervised_contrastive_weight"]) * metric
            + float(objective["dense_sparse_consistency_weight"]) * consistency
        )
    gradients = tape.gradient(total, model.trainable_variables)
    finite_gradients = all(
        gradient is not None and bool(tf.reduce_all(tf.math.is_finite(gradient)))
        for gradient in gradients
    )
    if not finite_gradients or not bool(tf.math.is_finite(total)):
        raise RuntimeError("VNEXT_INVARIANT_NONFINITE_STEP")
    model.optimizer.apply_gradients(zip(gradients, model.trainable_variables, strict=True))
    combined_probability = tf.concat([dense_probability, sparse_probability], axis=0)
    combined_labels = tf.concat([labels_tensor, labels_tensor], axis=0)
    top1 = tf.reduce_mean(
        tf.cast(
            tf.equal(
                tf.argmax(combined_probability, axis=1, output_type=tf.int32),
                combined_labels,
            ),
            tf.float32,
        )
    )
    top5 = tf.reduce_mean(
        tf.cast(tf.math.in_top_k(combined_labels, combined_probability, 5), tf.float32)
    )
    return {
        "loss": float(total),
        "classification_loss": float(classification),
        "metric_loss": float(metric),
        "consistency_loss": float(consistency),
        "top1": float(top1),
        "top5": float(top5),
        "finite_gradients": float(finite_gradients),
        "weight": float(len(labels)),
    }


def _validation(model: Any, rows: list[dict[str, Any]], clip_limit: int) -> dict[str, float]:
    import tensorflow as tf

    losses: list[float] = []
    correct: list[bool] = []
    top5: list[bool] = []
    for start in range(0, len(rows), clip_limit):
        dense, dense_mask, sparse, sparse_mask, labels, _ = _load_view_batch(
            rows[start : start + clip_limit]
        )
        features = np.concatenate([dense, sparse])
        masks = np.concatenate([dense_mask, sparse_mask])
        repeated_labels = np.concatenate([labels, labels])
        probability = np.asarray(
            model([features, masks], training=False)["probabilities"], np.float32
        )
        losses.extend(
            tf.keras.losses.sparse_categorical_crossentropy(
                repeated_labels, probability
            ).numpy()
        )
        predicted = np.argmax(probability, axis=1)
        correct.extend((predicted == repeated_labels).tolist())
        top = np.argpartition(probability, -5, axis=1)[:, -5:]
        top5.extend(
            label in guesses
            for label, guesses in zip(repeated_labels, top, strict=True)
        )
    return {
        "val_loss": float(np.mean(losses)),
        "val_top1": float(np.mean(correct)),
        "val_top5": float(np.mean(top5)),
    }


def _weighted_epoch(records: list[dict[str, float]]) -> dict[str, float]:
    total_weight = sum(record["weight"] for record in records)
    return {
        name: float(
            sum(record[name] * record["weight"] for record in records) / total_weight
        )
        for name in (
            "loss",
            "classification_loss",
            "metric_loss",
            "consistency_loss",
            "top1",
            "top5",
            "finite_gradients",
        )
    }


def _history(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = (
        "epoch",
        "loss",
        "classification_loss",
        "metric_loss",
        "consistency_loss",
        "top1",
        "top5",
        "finite_gradients",
        "val_loss",
        "val_top1",
        "val_top5",
    )
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def audit_pairing(dataset: Path, output: Path, config_path: Path) -> dict[str, Any]:
    """Persist a deterministic, full-TRAIN audit without loading feature tensors."""

    config = _load_config(config_path)
    rows = _load_rows(dataset)
    train_rows = [row for row in rows if row["split"] == "train"]
    dev_rows = [row for row in rows if row["split"] == "dev"]
    train_signers = {row["signer_id"] for row in train_rows}
    dev_signers = {row["signer_id"] for row in dev_rows}
    by_class: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in train_rows:
        by_class[int(row["class_id"])].append(row)
    signer_counts = [len({row["signer_id"] for row in values}) for values in by_class.values()]
    clip_limit = int(config["invariant_objective"]["pair_batch_clip_limit"])
    epoch_audits: list[dict[str, Any]] = []
    identities: list[str] = []
    for epoch in (0, 1, 39):
        batches = paired_batches(
            train_rows,
            seed=int(config["seed"]),
            epoch=epoch,
            clip_limit=clip_limit,
        )
        sample_ids = [row["sample_id"] for batch in batches for row in batch]
        sequence_hash = hashlib.sha256("\n".join(sample_ids).encode()).hexdigest()
        identities.append(sequence_hash)
        epoch_audits.append(
            {
                "epoch_zero_based": epoch,
                "pair_batches": len(batches),
                "anchor_clips": len(sample_ids),
                "classification_views": len(sample_ids) * 2,
                "unique_anchor_clips": len(set(sample_ids)),
                "batch_clip_min": min(len(batch) for batch in batches),
                "batch_clip_max": max(len(batch) for batch in batches),
                "batch_clip_mean": float(np.mean([len(batch) for batch in batches])),
                "sample_sequence_sha256": sequence_hash,
            }
        )
    repeated = paired_batches(
        train_rows,
        seed=int(config["seed"]),
        epoch=0,
        clip_limit=clip_limit,
    )
    repeated_ids = [row["sample_id"] for batch in repeated for row in batch]
    repeated_hash = hashlib.sha256("\n".join(repeated_ids).encode()).hexdigest()
    result = {
        "schema": "APPHEAR_VNEXT_INVARIANT_PAIRING_AUDIT_V1",
        "milestone": MILESTONE,
        "status": "PASS",
        "train_clips": len(train_rows),
        "dev_clips": len(dev_rows),
        "classes": len(by_class),
        "train_signers": len(train_signers),
        "dev_signers": sorted(dev_signers),
        "train_dev_signer_overlap": sorted(train_signers & dev_signers),
        "classes_with_cross_signer_positives": sum(value >= 2 for value in signer_counts),
        "signers_per_class": {
            "min": min(signer_counts),
            "median": float(np.median(signer_counts)),
            "mean": float(np.mean(signer_counts)),
            "max": max(signer_counts),
        },
        "same_epoch_deterministic": identities[0] == repeated_hash,
        "epoch_sequences_distinct": len(set(identities)) == len(identities),
        "epochs": epoch_audits,
        "classification_membership_changed": False,
        "protected_test_accessed": False,
    }
    if (
        len(train_rows) != 3926
        or len(dev_rows) != 816
        or len(by_class) != 236
        or train_signers & dev_signers
        or result["classes_with_cross_signer_positives"] != 236
        or not result["same_epoch_deterministic"]
        or not result["epoch_sequences_distinct"]
        or any(item["unique_anchor_clips"] != 3926 for item in epoch_audits)
    ):
        result["status"] = "FAIL"
        raise RuntimeError(f"VNEXT_INVARIANT_PAIRING_AUDIT:{result}")
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, result)
    return result


def train(
    dataset: Path,
    output: Path,
    config_path: Path,
    *,
    resume: bool,
    smoke: bool,
) -> dict[str, Any]:
    import tensorflow as tf

    config = _load_config(config_path)
    rows = _load_rows(dataset)
    train_rows = [row for row in rows if row["split"] == "train"]
    dev_rows = [row for row in rows if row["split"] == "dev"]
    objective = config["invariant_objective"]
    clip_limit = int(objective["pair_batch_clip_limit"])
    seed = int(config["seed"])
    tf.keras.utils.set_random_seed(seed)
    baseline_best = V2_BASELINE_RUN / "best.keras"
    if not baseline_best.is_file():
        raise RuntimeError("VNEXT_INVARIANT_V2_CONTROL_MISSING")
    output.mkdir(parents=True, exist_ok=True)
    identity = {
        "milestone": MILESTONE,
        "seed": seed,
        "raw_schema": RAW_SCHEMA,
        "feature_schema": FEATURE_SCHEMA_V2,
        "input_shape": [MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2],
        "vocabulary_sha256": sha256(VOCAB_MANIFEST),
        "config_sha256": sha256(config_path),
        "dataset_contract_sha256": sha256(dataset / "contract.json"),
        "v2_baseline_best_sha256": sha256(baseline_best),
        "scientific_delta": "pair-aware embedding objective only",
        "classification_anchor_exposure": "each TRAIN clip dense+sparse once per epoch",
        "smoke": smoke,
        "protected_test_accessed": False,
    }
    identity_path = output / "run_identity.json"
    if identity_path.is_file():
        if json.loads(identity_path.read_text(encoding="utf-8")) != identity:
            raise RuntimeError("VNEXT_INVARIANT_RUN_IDENTITY_DRIFT")
    else:
        write_json(identity_path, identity)
    reproducibility = output / "reproducibility_config.json"
    if reproducibility.is_file() and sha256(reproducibility) != sha256(config_path):
        raise RuntimeError("VNEXT_INVARIANT_CONFIG_DRIFT")
    if not reproducibility.is_file():
        shutil.copyfile(config_path, reproducibility)

    latest = output / "latest.keras"
    best = output / "best.keras"
    final = output / "final.keras"
    history_path = output / "history.csv"
    state_path = output / "resume_state.json"
    result_path = output / ("smoke_training_result.json" if smoke else "training_result.json")
    if resume and result_path.is_file():
        completed = json.loads(result_path.read_text(encoding="utf-8"))
        if completed.get("status") != "PASS" or not best.is_file() or not final.is_file():
            raise RuntimeError("VNEXT_INVARIANT_COMPLETED_INTEGRITY")
        completed["fit_skipped_existing_complete_run"] = True
        return completed

    history_rows: list[dict[str, Any]] = []
    best_loss = math.inf
    best_epoch = -1
    wait = 0
    initial_epoch = 0
    if state_path.is_file():
        if not resume:
            raise RuntimeError("VNEXT_INVARIANT_RUN_EXISTS_USE_RESUME")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if (
            state.get("config_sha256") != sha256(config_path)
            or state.get("dataset_contract_sha256") != sha256(dataset / "contract.json")
            or state.get("smoke") is not smoke
            or not latest.is_file()
            or state.get("latest_checkpoint_sha256") != sha256(latest)
        ):
            raise RuntimeError("VNEXT_INVARIANT_RESUME_STATE")
        model = tf.keras.models.load_model(latest, safe_mode=True)
        history_rows = list(state["history"])
        best_loss = float(state["best_val_loss"])
        best_epoch = int(state["best_epoch"])
        wait = int(state["early_stop_wait"])
        initial_epoch = int(state["completed_epochs"])
    elif any(path.exists() for path in (latest, best, final, history_path)):
        raise RuntimeError("VNEXT_INVARIANT_PARTIAL_RUN_WITHOUT_STATE")
    else:
        model = build_model(config)

    epochs = 1 if smoke else int(config["training"]["epochs"])
    effective_dev = dev_rows[:16] if smoke else dev_rows
    smoke_batches = 2
    stopped_early = False
    first_step: dict[str, float] | None = None
    batch_counts: list[int] = []
    for epoch in range(initial_epoch, epochs):
        batches = paired_batches(
            train_rows,
            seed=seed,
            epoch=epoch,
            clip_limit=clip_limit,
        )
        if smoke:
            batches = batches[:smoke_batches]
        batch_counts.append(len(batches))
        records: list[dict[str, float]] = []
        for batch_rows in batches:
            record = _step(model, _load_view_batch(batch_rows), objective)
            records.append(record)
            if first_step is None:
                first_step = record.copy()
        epoch_metrics = _weighted_epoch(records)
        validation = _validation(model, effective_dev, clip_limit)
        row = {"epoch": epoch, **epoch_metrics, **validation}
        history_rows.append(row)
        model.save(latest)
        if row["val_loss"] < best_loss:
            best_loss = row["val_loss"]
            best_epoch = epoch
            wait = 0
            shutil.copyfile(latest, best)
        else:
            wait += 1
        _history(history_path, history_rows)
        state = {
            "schema": "APPHEAR_VNEXT_INVARIANT_RESUME_STATE_V1",
            "config_sha256": sha256(config_path),
            "dataset_contract_sha256": sha256(dataset / "contract.json"),
            "smoke": smoke,
            "completed_epochs": epoch + 1,
            "best_epoch": best_epoch,
            "best_val_loss": best_loss,
            "early_stop_wait": wait,
            "latest_checkpoint_sha256": sha256(latest),
            "history": history_rows,
            "protected_test_accessed": False,
        }
        write_json(state_path, state)
        print(
            f"Epoch {epoch + 1}/{epochs} - "
            f"loss={row['loss']:.4f} class={row['classification_loss']:.4f} "
            f"metric={row['metric_loss']:.4f} consistency={row['consistency_loss']:.4f} "
            f"top1={row['top1']:.4f} val_loss={row['val_loss']:.4f} "
            f"val_top1={row['val_top1']:.4f}",
            flush=True,
        )
        if not smoke and wait >= int(config["training"]["early_stop_patience"]):
            stopped_early = True
            break

    if not best.is_file() or first_step is None:
        raise RuntimeError("VNEXT_INVARIANT_NO_COMPLETED_EPOCH")
    best_model = tf.keras.models.load_model(best, safe_mode=True)
    best_model.save(final)
    reloaded = tf.keras.models.load_model(final, safe_mode=True)
    sample = _load_view_batch(train_rows[:1])
    before = best_model([sample[0], sample[1]], training=False)
    after = reloaded([sample[0], sample[1]], training=False)
    reload_delta = max(
        float(np.max(np.abs(np.asarray(before[key]) - np.asarray(after[key]))))
        for key in ("probabilities", "embedding")
    )
    if reload_delta > 1.0e-6:
        raise RuntimeError(f"VNEXT_INVARIANT_RELOAD:{reload_delta}")
    result = {
        "schema": "APPHEAR_VNEXT_INVARIANT_TRAIN_RESULT_V1",
        "milestone": MILESTONE,
        "status": "PASS",
        "smoke": smoke,
        "input_shape": [MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2],
        "embedding_dimension": 64,
        "classes": 236,
        "parameter_count": best_model.count_params(),
        "train_clips": len(train_rows),
        "dev_clips": len(dev_rows),
        "classification_views_per_epoch": len(train_rows) * 2,
        "pair_batches_per_epoch": batch_counts,
        "epochs_completed": len(history_rows),
        "best_epoch_zero_based": best_epoch,
        "best_val_loss": best_loss,
        "stopped_early": stopped_early,
        "first_step": first_step,
        "checkpoint_reload_max_abs": reload_delta,
        "best_checkpoint": str(best.resolve()),
        "latest_checkpoint": str(latest.resolve()),
        "final_checkpoint": str(final.resolve()),
        "config_sha256": sha256(config_path),
        "dataset_contract_sha256": sha256(dataset / "contract.json"),
        "full_training_executed": not smoke,
        "recognition_accuracy_claim": not smoke,
        "protected_test_accessed": False,
    }
    write_json(result_path, result)
    return result


def smoke(dataset: Path, output: Path, config: Path) -> dict[str, Any]:
    training = train(dataset, output, config, resume=False, smoke=True)
    evaluation = evaluate(
        dataset,
        output / "best.keras",
        output / "smoke_evaluation.json",
        batch_size=4,
        limit_per_split=16,
    )
    result = {
        "milestone": MILESTONE,
        "status": "PASS",
        "training": training,
        "evaluation_status": evaluation["status"],
        "full_training_executed": False,
        "recognition_accuracy_claim": False,
        "protected_test_accessed": False,
    }
    write_json(output / "signer_cadence_invariant_smoke.json", result)
    return result


def evaluate_candidate(
    dataset: Path,
    checkpoint: Path,
    output: Path,
    *,
    batch_size: int,
) -> dict[str, Any]:
    """Run the unchanged V2 evaluator and persist a matched V2-control comparison."""

    candidate = evaluate(dataset, checkpoint, output, batch_size=batch_size)
    baseline_path = V2_BASELINE_RUN / "evaluation.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if (
        baseline.get("feature_schema") != FEATURE_SCHEMA_V2
        or baseline.get("input_shape") != [MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2]
        or baseline.get("protected_test_accessed") is not False
        or baseline.get("checkpoint_sha256") != sha256(V2_BASELINE_RUN / "best.keras")
    ):
        raise RuntimeError("VNEXT_INVARIANT_BASELINE_EVALUATION_IDENTITY")

    comparisons: dict[str, Any] = {}
    for split in ("train", "dev"):
        comparisons[split] = {}
        for condition in ("dense", "phone_01_sparse"):
            control_metrics = baseline["details"][split][condition]
            candidate_metrics = candidate["details"][split][condition]
            comparisons[split][condition] = {
                metric: {
                    "v2_control": float(control_metrics[metric]),
                    "candidate": float(candidate_metrics[metric]),
                    "delta": float(candidate_metrics[metric] - control_metrics[metric]),
                }
                for metric in ("top1", "top5", "macro_f1")
            }
            comparisons[split][condition]["zero_recall_classes"] = {
                "v2_control": len(control_metrics["zero_recall_classes"]),
                "candidate": len(candidate_metrics["zero_recall_classes"]),
                "delta": len(candidate_metrics["zero_recall_classes"])
                - len(control_metrics["zero_recall_classes"]),
            }
    signer_comparison: dict[str, Any] = {}
    for signer in sorted(candidate["details"]["dev"]["dense"]["by_signer"]):
        signer_comparison[signer] = {}
        for condition in ("dense", "phone_01_sparse"):
            control_value = baseline["details"]["dev"][condition]["by_signer"][signer][
                "top1"
            ]
            candidate_value = candidate["details"]["dev"][condition]["by_signer"][
                signer
            ]["top1"]
            signer_comparison[signer][condition] = {
                "v2_control": float(control_value),
                "candidate": float(candidate_value),
                "delta": float(candidate_value - control_value),
            }
    per_class_counts: dict[str, Any] = {}
    for condition in ("dense", "phone_01_sparse"):
        control_classes = baseline["details"]["dev"][condition]["per_class"]
        candidate_classes = candidate["details"]["dev"][condition]["per_class"]
        deltas = np.asarray(
            [
                float(new["recall"]) - float(old["recall"])
                for old, new in zip(control_classes, candidate_classes, strict=True)
            ]
        )
        per_class_counts[condition] = {
            "improved": int(np.count_nonzero(deltas > 0)),
            "unchanged": int(np.count_nonzero(deltas == 0)),
            "worsened": int(np.count_nonzero(deltas < 0)),
        }
    result = {
        "schema": "APPHEAR_VNEXT_INVARIANT_V2_MATCHED_COMPARISON_V1",
        "milestone": MILESTONE,
        "status": "PASS",
        "candidate_evaluation": str(output.resolve()),
        "candidate_checkpoint_sha256": sha256(checkpoint),
        "v2_control_evaluation": str(baseline_path.resolve()),
        "v2_control_checkpoint_sha256": baseline["checkpoint_sha256"],
        "aggregate": comparisons,
        "dev_signers": signer_comparison,
        "dev_per_class_recall_counts": per_class_counts,
        "dense_sparse_paired_comparison": candidate["dense_sparse_paired_comparison"],
        "train_minus_dev_top1_gap": candidate["train_minus_dev_top1_gap"],
        "protected_test_accessed": False,
    }
    comparison_path = output.with_name("v2_baseline_comparison.json")
    write_json(comparison_path, result)
    return {
        "evaluation": candidate,
        "comparison": result,
        "comparison_path": str(comparison_path.resolve()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    train_parser = commands.add_parser("train")
    train_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    train_parser.add_argument("--output", type=Path, default=DEFAULT_RUN)
    train_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    train_parser.add_argument("--resume", action="store_true")
    smoke_parser = commands.add_parser("smoke")
    smoke_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    smoke_parser.add_argument(
        "--output", type=Path, default=BASE / "signer_cadence_invariant_236_01_smoke"
    )
    smoke_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    audit_parser = commands.add_parser("audit-pairing")
    audit_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    audit_parser.add_argument(
        "--output",
        type=Path,
        default=BASE / "signer_cadence_invariant_236_01" / "pairing_audit.json",
    )
    audit_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    evaluate_parser = commands.add_parser("evaluate")
    evaluate_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    evaluate_parser.add_argument("--checkpoint", type=Path, required=True)
    evaluate_parser.add_argument("--output", type=Path, required=True)
    evaluate_parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    if args.command == "train":
        result = train(
            args.dataset.resolve(),
            args.output.resolve(),
            args.config.resolve(),
            resume=args.resume,
            smoke=False,
        )
    elif args.command == "smoke":
        result = smoke(args.dataset.resolve(), args.output.resolve(), args.config.resolve())
    elif args.command == "audit-pairing":
        result = audit_pairing(
            args.dataset.resolve(), args.output.resolve(), args.config.resolve()
        )
    elif args.command == "evaluate":
        result = evaluate_candidate(
            args.dataset.resolve(),
            args.checkpoint.resolve(),
            args.output.resolve(),
            batch_size=args.batch_size,
        )
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
