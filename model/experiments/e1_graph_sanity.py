"""E1: audit and overfit sanity gate for the existing AppHear graph encoder.

This experiment reads the existing v3.0 training features and writes only a JSON report under
artifacts/. It does not update a production model, feature tensor, or Android asset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# The graph path is unstable with oneDNN on the project's Windows CPU. This must precede TF import.
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import numpy as np

from model.model_gcn import build_stgcn, skeleton_adjacency

DEFAULT_FEATURES = Path(
    "F:/ASL DATASET/ASL CITIZEN/derived/apphear3/features_streaming_conversational_fps"
)
DEFAULT_OUTPUT = Path("artifacts/recognition_upgrade/e1_graph_sanity")
FULL_CHANNELS = (64, 64, 64, 64, 128, 128, 128, 256, 256, 256)
SLIM_CHANNELS = (32, 32, 32, 32, 64, 64, 64, 128, 128, 128)


@dataclass(frozen=True)
class Selection:
    class_ids: list[int]
    indices: list[int]
    remapped_labels: list[int]


def connected_components(adjacency: np.ndarray) -> list[list[int]]:
    """Return graph components, ignoring self loops and edge weights."""
    unseen = set(range(adjacency.shape[0]))
    components: list[list[int]] = []
    while unseen:
        root = min(unseen)
        stack = [root]
        component: list[int] = []
        unseen.remove(root)
        while stack:
            node = stack.pop()
            component.append(node)
            neighbors = np.flatnonzero(adjacency[node] > 0)
            for neighbor in neighbors:
                neighbor_i = int(neighbor)
                if neighbor_i != node and neighbor_i in unseen:
                    unseen.remove(neighbor_i)
                    stack.append(neighbor_i)
        components.append(sorted(component))
    return sorted(components, key=lambda group: (-len(group), group[0]))


def select_balanced(
    y: np.ndarray,
    classes: int,
    clips_per_class: int,
    seed: int,
    eligible_mask: np.ndarray | None = None,
) -> Selection:
    """Select a deterministic balanced slice and remap labels to contiguous experiment IDs."""
    allowed = np.ones(len(y), dtype=bool) if eligible_mask is None else eligible_mask
    allowed_classes, allowed_counts = np.unique(y[allowed], return_counts=True)
    eligible = sorted(
        int(class_id)
        for class_id, count in zip(allowed_classes, allowed_counts, strict=True)
        if int(count) >= clips_per_class
    )
    if len(eligible) < classes:
        raise ValueError(f"need {classes} eligible classes, found {len(eligible)}")
    class_ids = eligible[:classes]
    rng = np.random.default_rng(seed)
    indices: list[int] = []
    remapped: list[int] = []
    for experiment_id, class_id in enumerate(class_ids):
        candidates = np.flatnonzero((y == class_id) & allowed)
        chosen = np.sort(rng.choice(candidates, clips_per_class, replace=False))
        indices.extend(int(index) for index in chosen)
        remapped.extend([experiment_id] * clips_per_class)
    return Selection(class_ids, indices, remapped)


def array_digest(*arrays: np.ndarray) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        digest.update(np.ascontiguousarray(array).view(np.uint8))
    return digest.hexdigest()


def audit(
    features_dir: Path, classes: int, clips_per_class: int, seed: int, max_time: int
) -> tuple[dict, Selection]:
    split_path = features_dir / "train.npz"
    with np.load(split_path, allow_pickle=True) as data:
        required = {"X", "y", "frame_mask", "lengths", "participant_ids", "schema_version"}
        missing = required.difference(data.files)
        if missing:
            raise ValueError(f"{split_path} is missing {sorted(missing)}")
        y = np.asarray(data["y"], dtype=np.int32)
        all_lengths = np.asarray(data["lengths"], dtype=np.int32)
        selection = select_balanced(
            y, classes, clips_per_class, seed, eligible_mask=all_lengths <= max_time
        )
        idx = np.asarray(selection.indices)
        x = np.asarray(data["X"][idx, :max_time], dtype=np.float32)
        mask = np.asarray(data["frame_mask"][idx, :max_time], dtype=bool)
        lengths = np.asarray(data["lengths"][idx], dtype=np.int32)
        participants = np.asarray(data["participant_ids"][idx]).astype(str)
        schema_version = str(data["schema_version"])

    adjacency = skeleton_adjacency()
    components = connected_components(adjacency)
    mediapipe_adjacency = skeleton_adjacency("mediapipe")
    mediapipe_components = connected_components(mediapipe_adjacency)
    report = {
        "split": {
            "path": str(split_path.resolve()),
            "size_bytes": split_path.stat().st_size,
            "schema_version": schema_version,
            "selected_shape": list(x.shape),
            "selected_digest_sha256": array_digest(x, mask, lengths),
            "class_ids": selection.class_ids,
            "clips_per_class": clips_per_class,
            "participant_count": int(np.unique(participants).size),
            "length_min": int(lengths.min()),
            "length_mean": float(lengths.mean()),
            "length_max": int(lengths.max()),
            "all_finite": bool(np.isfinite(x).all()),
            "mask_matches_lengths": bool(np.all(mask.sum(axis=1) == lengths)),
        },
        "graph": {
            "shape": list(adjacency.shape),
            "symmetric": bool(np.allclose(adjacency, adjacency.T)),
            "finite": bool(np.isfinite(adjacency).all()),
            "component_count": len(components),
            "component_sizes": [len(component) for component in components],
            "isolated_nodes": [component[0] for component in components if len(component) == 1],
            "mediapipe_component_count": len(mediapipe_components),
            "mediapipe_component_sizes": [len(component) for component in mediapipe_components],
            "mediapipe_isolated_nodes": [
                component[0] for component in mediapipe_components if len(component) == 1
            ],
        },
    }
    return report, selection


def run_overfit(
    features_dir: Path,
    selection: Selection,
    architecture: str,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    seed: int,
    target_accuracy: float,
    max_time: int,
) -> dict[str, Any]:
    import tensorflow as tf

    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(seed)
    with np.load(features_dir / "train.npz", allow_pickle=True) as data:
        idx = np.asarray(selection.indices)
        x = np.asarray(data["X"][idx, :max_time], dtype=np.float32)
    y = np.asarray(selection.remapped_labels, dtype=np.int32)
    full = architecture.startswith("gcn-full")
    corrected_padding = architecture.endswith("-masked")
    channels = FULL_CHANNELS if full else SLIM_CHANNELS
    strides = None if full else {0: 2, 4: 2}
    base = build_stgcn(
        time_window=x.shape[1],
        feature_dim=x.shape[2],
        num_classes=len(selection.class_ids),
        channels=channels,
        dropout=0.0,
        strides=strides,
        mask_padded_frames=corrected_padding,
        infer_hand_presence=corrected_padding,
        pose_topology="mediapipe" if corrected_padding else "legacy",
    )
    # The existing GCN repeats one clip posterior across T. Train its unique posterior directly.
    model = tf.keras.Model(base.input, base.output[:, 0, :], name=f"{architecture}_overfit")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(),
        metrics=[tf.keras.metrics.SparseCategoricalAccuracy(name="accuracy")],
    )

    class StopAtTarget(tf.keras.callbacks.Callback):
        def on_epoch_end(self, epoch: int, logs: dict[str, float] | None = None) -> None:
            if logs and float(logs.get("accuracy", 0.0)) >= target_accuracy:
                self.model.stop_training = True

    started = time.perf_counter()
    history = model.fit(
        x,
        y,
        batch_size=batch_size,
        epochs=epochs,
        shuffle=True,
        verbose=2,
        callbacks=[StopAtTarget()],
    )
    elapsed = time.perf_counter() - started
    final_accuracy = float(history.history["accuracy"][-1])
    return {
        "architecture": architecture,
        "channels": list(channels),
        "params": int(model.count_params()),
        "epochs_completed": len(history.epoch),
        "elapsed_seconds": elapsed,
        "final_train_accuracy": final_accuracy,
        "best_train_accuracy": float(max(history.history["accuracy"])),
        "target_accuracy": target_accuracy,
        "passed": bool(max(history.history["accuracy"]) >= target_accuracy),
        "history": {
            key: [float(value) for value in values] for key, values in history.history.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AppHear E1 graph audit and overfit gate")
    parser.add_argument("--features-dir", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--classes", type=int, default=50)
    parser.add_argument("--clips-per-class", type=int, default=5)
    parser.add_argument("--seed", type=int, default=240725)
    parser.add_argument(
        "--architecture",
        choices=("gcn-slim", "gcn-slim-masked", "gcn-full", "gcn-full-masked"),
        default="gcn-full-masked",
    )
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--target-accuracy", type=float, default=0.95)
    parser.add_argument("--max-time", type=int, default=96)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()

    report, selection = audit(
        args.features_dir, args.classes, args.clips_per_class, args.seed, args.max_time
    )
    report["experiment"] = {
        "id": "E1",
        "seed": args.seed,
        "architecture": args.architecture,
        "pose_topology": "mediapipe" if args.architecture.endswith("-masked") else "legacy",
        "classes": args.classes,
        "clips_per_class": args.clips_per_class,
        "python": platform.python_version(),
        "numpy": np.__version__,
    }
    if not args.audit_only:
        report["overfit"] = run_overfit(
            args.features_dir,
            selection,
            args.architecture,
            args.epochs,
            args.batch_size,
            args.learning_rate,
            args.seed,
            args.target_accuracy,
            args.max_time,
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    suffix = "audit" if args.audit_only else args.architecture
    output_path = args.output_dir / f"{suffix}_t{args.max_time}_seed{args.seed}.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"[E1] report -> {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
