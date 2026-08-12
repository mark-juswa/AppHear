"""E3-C landmark + RGB fusion on the frozen E3-B5 split.

This package reconstructs the exact E3-B5 50-class split, extracts upper-body RGB frame embeddings
for the same clips, and compares RGB-only, augmented-landmark-only, and fusion heads. It is
experiment-only and writes all outputs under the run directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.detect.schema import SpanSidecar
from pipeline.features.config import load_config as load_features_config
from pipeline.quality.config import load_config as load_quality_config

DEFAULT_SOURCE_RUN = Path(
    "artifacts/recognition_upgrade/e3_landmark_temporal/pilot_02_50class_multiseed"
)
DEFAULT_LANDMARK_RUN = Path(
    "artifacts/recognition_upgrade/e3_landmark_temporal/pilot_03_feature_augmented"
)
DEFAULT_OUTPUT_ROOT = Path("artifacts/recognition_upgrade/e3_fusion")
DEFAULT_RUN_ID = "pilot_02_frozen_50_landmark_rgb"
DEFAULT_FEATURES_CONFIG = Path("pipeline/config/features.yaml")
DEFAULT_VIDEOS_ROOT = Path(r"F:\ASL DATASET\ASL CITIZEN\ASL_Citizen\videos")
SPLITS = {"train": 0, "val": 1, "test": 2}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _accepted_streaming_index(
    split: str, features_config: Path, videos_root: Path
) -> list[dict[str, Any]]:
    fcfg = load_features_config(features_config)
    qcfg = load_quality_config(fcfg.quality_config)
    vocab = json.loads((fcfg.output_root / "vocab.json").read_text(encoding="utf-8"))
    streaming_path = fcfg.streaming_output_root / f"{split}.npz"
    if not streaming_path.exists():
        raise FileNotFoundError(f"missing streaming feature split: {streaming_path}")
    stream = np.load(streaming_path, allow_pickle=False)
    stream_y = stream["y"].astype(np.int64)
    stream_pid = stream["participant_ids"].astype(str)
    stream_len = stream["lengths"].astype(np.int32)
    t_max = int(np.asarray(stream["t_max"]).item())
    rows: list[dict[str, Any]] = []
    stream_index = 0
    for npz_path in sorted((qcfg.input_root / split).glob("*.npz")):
        clip_id = npz_path.stem
        span_path = qcfg.spans_root / split / f"{clip_id}.span.json"
        if not span_path.exists():
            continue
        span = SpanSidecar.load(span_path)
        if span.gloss not in vocab:
            continue
        if stream_index >= len(stream_y):
            break
        span_length = min(max(0, int(span.release) - int(span.onset) + 1), t_max)
        candidate = (int(vocab[span.gloss]), str(span.participant_id), int(span_length))
        expected = (
            int(stream_y[stream_index]),
            str(stream_pid[stream_index]),
            int(stream_len[stream_index]),
        )
        if candidate != expected:
            continue
        rows.append(
            {
                "source_split": split,
                "source_index": len(rows),
                "clip_id": clip_id,
                "participant_id": span.participant_id,
                "gloss": span.gloss,
                "label_id": int(vocab[span.gloss]),
                "video_path": str((videos_root / f"{clip_id}.mp4").resolve()),
                "onset": int(span.onset),
                "release": int(span.release),
                "native_fps": float(span.native_fps),
            }
        )
        stream_index += 1
    if stream_index != len(stream_y):
        raise ValueError(
            f"{split} metadata alignment recovered {stream_index}/{len(stream_y)} streaming rows; "
            "fall back to a quality-reconstruction mapper before using RGB fusion."
        )
    return rows


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output_root / args.run_id
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"output already exists: {output}")
    for relative in ("dataset", "logs", "metrics", "models", "smoke"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    source_config = json.loads((args.source_run / "pilot_config.json").read_text(encoding="utf-8"))
    source_rows = _read_csv(args.source_run / "pilot_manifest.csv")
    source_by_split = {
        split: _accepted_streaming_index(split, args.features_config, args.videos_root)
        for split in SPLITS
    }
    manifest_rows: list[dict[str, Any]] = []
    missing_video = []
    for row in source_rows:
        split = row["source_split"]
        source_index = int(row["source_index"])
        if source_index >= len(source_by_split[split]):
            raise ValueError(f"{split} source_index {source_index} outside reconstructed index")
        mapped = source_by_split[split][source_index]
        if mapped["participant_id"] != row["participant_id"] or mapped["gloss"] != row["gloss"]:
            raise ValueError(
                "reconstructed index mismatch at row "
                f"{row['row_index']}: expected {row['participant_id']} {row['gloss']}, "
                f"got {mapped['participant_id']} {mapped['gloss']}"
            )
        if not Path(mapped["video_path"]).exists():
            missing_video.append(mapped)
        manifest_rows.append(
            {
                "row_index": int(row["row_index"]),
                "split": row["split"],
                "split_index": SPLITS[row["split"]],
                "source_split": split,
                "source_index": source_index,
                "clip_id": mapped["clip_id"],
                "participant_id": mapped["participant_id"],
                "old_class_id": int(row["old_class_id"]),
                "label_index": int(row["new_class_id"]),
                "gloss": row["gloss"],
                "video_path": mapped["video_path"],
                "onset": mapped["onset"],
                "release": mapped["release"],
                "native_fps": mapped["native_fps"],
            }
        )
    if missing_video:
        _write_csv(
            output / "missing_videos.csv",
            missing_video,
            ["source_split", "source_index", "clip_id", "participant_id", "gloss", "video_path"],
        )
        raise FileNotFoundError(f"{len(missing_video)} videos are missing; see missing_videos.csv")

    _write_csv(
        output / "pilot_manifest.csv",
        manifest_rows,
        [
            "row_index",
            "split",
            "split_index",
            "source_split",
            "source_index",
            "clip_id",
            "participant_id",
            "old_class_id",
            "label_index",
            "gloss",
            "video_path",
            "onset",
            "release",
            "native_fps",
        ],
    )
    config = {
        "experiment": "e3_c_landmark_rgb_fusion_v1",
        "purpose": "frozen 50-class landmark+RGB fusion test; not production training",
        "run_dir": str(output.resolve()),
        "source_run": str(args.source_run.resolve()),
        "landmark_run": str(args.landmark_run.resolve()),
        "landmark_tensor": str(
            (args.landmark_run / "dataset" / "augmented_features.npz").resolve()
        ),
        "features_config": str(args.features_config),
        "videos_root": str(args.videos_root.resolve()),
        "class_count": int(source_config["class_count"]),
        "classes": source_config["classes"],
        "rows": len(manifest_rows),
        "split_counts": {
            name: sum(1 for row in manifest_rows if row["split"] == name) for name in SPLITS
        },
        "frames": int(args.frames),
        "image_size": int(args.image_size),
        "crop_mode": args.crop_mode,
        "encoder": args.encoder,
        "weights": args.weights,
        "embedding_batch_size": int(args.embedding_batch_size),
        "batch_size": int(args.batch_size),
        "epochs": int(args.epochs),
        "learning_rate": float(args.learning_rate),
        "branches": ["rgb_only", "landmark_aug_only", "fusion_aug_rgb"],
        "seeds": [int(seed) for seed in args.seeds],
        "baseline_reference": {
            "e3_b6_aug_masked_val": 0.5117,
            "e3_b6_aug_masked_test": 0.3867,
            "e3_b6_aug_conv_val": 0.5033,
            "e3_b6_aug_conv_test": 0.3883,
        },
        "gate": {
            "go_if": [
                "fusion improves mean best-test over E3-B6 full augmented Conv1D by >= 0.03",
                "fusion mean best-validation is at least E3-B6 full augmented masked TCN",
                "fusion beats both branch-only controls on validation and test",
                "prediction bias/confusion concentration improves",
            ],
            "no_go_if": [
                "RGB-only remains weak and fusion does not beat landmark-only",
                "fusion improves training only",
                "visual extraction is too slow or unstable for future mobile path",
            ],
        },
        "warnings": [
            "This is not Android integration.",
            "This does not change production recognizer assets.",
            "RGB extraction/training is the long step and should be developer-run.",
        ],
    }
    (output / "pilot_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (output / "README_RUN.md").write_text(_runbook(config), encoding="utf-8")
    return config


def _sample_indices(frame_count: int, frames: int, onset: int, release: int) -> list[int]:
    if frame_count <= 0:
        return [0] * frames
    start = max(0, min(frame_count - 1, onset))
    end = max(start, min(frame_count - 1, release))
    if frames <= 1:
        return [(start + end) // 2]
    return [
        min(frame_count - 1, round(start + i * (end - start) / (frames - 1))) for i in range(frames)
    ]


def _crop_frame(frame: np.ndarray, mode: str) -> np.ndarray:
    height, width = frame.shape[:2]
    if mode == "full_frame":
        return frame
    if mode == "upper_body_center":
        x0 = int(width * 0.08)
        x1 = int(width * 0.92)
        y0 = 0
        y1 = int(height * 0.92)
        return frame[y0:y1, x0:x1]
    raise ValueError(f"unsupported crop mode: {mode}")


def _read_video_frames(
    path: Path, frames: int, image_size: int, crop_mode: str, onset: int, release: int
) -> tuple[np.ndarray, dict[str, Any]]:
    import cv2  # type: ignore

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"could not open video: {path}")
    try:
        frame_total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        sampled = []
        indices = _sample_indices(frame_total, frames, onset, release)
        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            if not ok or frame is None:
                raise ValueError(f"failed reading frame {index} from {path}")
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = _crop_frame(frame, crop_mode)
            frame = cv2.resize(frame, (image_size, image_size), interpolation=cv2.INTER_AREA)
            sampled.append(frame.astype(np.uint8))
    finally:
        capture.release()
    return np.stack(sampled, axis=0), {
        "frame_count": frame_total,
        "fps": fps,
        "width": width,
        "height": height,
        "sampled_indices": json.dumps(indices),
    }


def _load_or_extract_frames(
    run_dir: Path, config: dict[str, Any], limit: int | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dataset_dir = run_dir / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if limit is None else f"_limit{limit}"
    frames_path = dataset_dir / f"rgb_frames_uint8{suffix}.npz"
    if frames_path.exists():
        data = np.load(frames_path, allow_pickle=False)
        return data["x"], data["y"], data["split_index"]
    rows = _read_csv(run_dir / "pilot_manifest.csv")
    if limit is not None:
        rows = rows[:limit]
    x_values = []
    y_values = []
    split_values = []
    metadata_rows = []
    for index, row in enumerate(rows, start=1):
        print(f"[e3-c] rgb extract {index}/{len(rows)} {row['split']} {row['gloss']}")
        frames, metadata = _read_video_frames(
            Path(row["video_path"]),
            int(config["frames"]),
            int(config["image_size"]),
            config["crop_mode"],
            int(row["onset"]),
            int(row["release"]),
        )
        x_values.append(frames)
        y_values.append(int(row["label_index"]))
        split_values.append(int(row["split_index"]))
        metadata_rows.append({**row, **metadata})
    x = np.stack(x_values, axis=0).astype(np.uint8)
    y = np.asarray(y_values, dtype=np.int64)
    split_index = np.asarray(split_values, dtype=np.int64)
    np.savez_compressed(frames_path, x=x, y=y, split_index=split_index)
    _write_csv(
        dataset_dir / f"rgb_frame_manifest{suffix}.csv",
        metadata_rows,
        [
            "row_index",
            "split",
            "split_index",
            "source_split",
            "source_index",
            "clip_id",
            "participant_id",
            "old_class_id",
            "label_index",
            "gloss",
            "video_path",
            "onset",
            "release",
            "native_fps",
            "frame_count",
            "fps",
            "width",
            "height",
            "sampled_indices",
        ],
    )
    return x, y, split_index


def _build_encoder(config: dict[str, Any]):
    import tensorflow as tf

    weights = None if config["weights"] == "none" else config["weights"]
    if config["encoder"] != "mobilenetv3small":
        raise ValueError(f"unsupported encoder: {config['encoder']}")
    encoder = tf.keras.applications.MobileNetV3Small(
        input_shape=(int(config["image_size"]), int(config["image_size"]), 3),
        include_top=False,
        weights=weights,
        pooling="avg",
        include_preprocessing=True,
    )
    encoder.trainable = False
    return encoder


def _load_or_build_rgb_embeddings(
    run_dir: Path, config: dict[str, Any]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    out_path = run_dir / "dataset" / "rgb_frame_features.npz"
    if out_path.exists():
        data = np.load(out_path, allow_pickle=False)
        return (
            data["features"].astype(np.float32),
            data["y"].astype(np.int64),
            data["split_index"].astype(np.int64),
        )
    x, y, split_index = _load_or_extract_frames(run_dir, config)
    features = _embed_frames(x, config)
    np.savez_compressed(out_path, features=features, y=y, split_index=split_index)
    return features, y, split_index


def _embed_frames(x: np.ndarray, config: dict[str, Any]) -> np.ndarray:
    encoder = _build_encoder(config)
    rows, frames = x.shape[:2]
    flat = x.reshape(rows * frames, int(config["image_size"]), int(config["image_size"]), 3)
    embeddings = encoder.predict(flat, batch_size=int(config["embedding_batch_size"]), verbose=1)
    return embeddings.reshape(rows, frames, embeddings.shape[-1]).astype(np.float32)


def _load_landmarks(
    config: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    path = Path(config["landmark_tensor"])
    if not path.exists():
        raise FileNotFoundError(f"missing landmark tensor: {path}")
    data = np.load(path, allow_pickle=False)
    required = {"features", "frame_mask", "y", "split_index"}
    missing = required.difference(data.files)
    if missing:
        raise ValueError(f"landmark tensor missing keys: {sorted(missing)}")
    return (
        data["features"].astype(np.float32),
        data["frame_mask"].astype(np.float32),
        data["y"].astype(np.int64),
        data["split_index"].astype(np.int64),
    )


def _masked_pool(encoded: Any, mask_input: Any, channels: int):
    import tensorflow as tf

    expanded_mask = tf.keras.layers.Lambda(
        lambda m: tf.expand_dims(tf.cast(m, tf.float32), axis=-1), output_shape=(None, 1)
    )(mask_input)
    masked_sum = tf.keras.layers.Lambda(
        lambda values: tf.reduce_sum(values[0] * values[1], axis=1), output_shape=(channels,)
    )([encoded, expanded_mask])
    denom = tf.keras.layers.Lambda(
        lambda m: tf.maximum(tf.reduce_sum(m, axis=1), 1.0), output_shape=(1,)
    )(expanded_mask)
    return tf.keras.layers.Lambda(lambda values: values[0] / values[1], output_shape=(channels,))(
        [masked_sum, denom]
    )


def _build_model(
    kind: str, landmark_shape: tuple[int, int], rgb_shape: tuple[int, int], classes: int, lr: float
):
    import tensorflow as tf

    from model.model import build_encoder

    inputs: list[Any] = []
    branches: list[Any] = []
    if kind in {"landmark_aug_only", "fusion_aug_rgb"}:
        land_in = tf.keras.Input(shape=landmark_shape, name="landmark_features")
        mask_in = tf.keras.Input(shape=(landmark_shape[0],), name="frame_mask")
        encoder = build_encoder(
            landmark_shape[0],
            landmark_shape[1],
            blocks=4,
            channels=64,
            dilations=(1, 2, 4, 8),
            kernel=3,
            dropout=0.1,
        )
        branches.append(_masked_pool(encoder(land_in), mask_in, 64))
        inputs.extend([land_in, mask_in])
    if kind in {"rgb_only", "fusion_aug_rgb"}:
        rgb_in = tf.keras.Input(shape=rgb_shape, name="rgb_features")
        x = tf.keras.layers.LayerNormalization()(rgb_in)
        x = tf.keras.layers.Conv1D(128, 3, padding="same", activation="relu")(x)
        x = tf.keras.layers.Dropout(0.25)(x)
        x = tf.keras.layers.GlobalAveragePooling1D()(x)
        branches.append(x)
        inputs.append(rgb_in)
    if len(branches) == 1:
        x = branches[0]
    else:
        x = tf.keras.layers.Concatenate()(branches)
        x = tf.keras.layers.Dense(128, activation="relu")(x)
        x = tf.keras.layers.Dropout(0.25)(x)
    out = tf.keras.layers.Dense(classes, activation="softmax")(x)
    model = tf.keras.Model(inputs, out, name=f"e3_c_{kind}")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def _inputs_for(kind: str, landmarks: np.ndarray, frame_mask: np.ndarray, rgb: np.ndarray) -> Any:
    if kind == "rgb_only":
        return rgb
    if kind == "landmark_aug_only":
        return [landmarks, frame_mask]
    if kind == "fusion_aug_rgb":
        return [landmarks, frame_mask, rgb]
    raise ValueError(f"unsupported branch: {kind}")


def smoke(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    x, y, split_index = _load_or_extract_frames(run_dir, config, limit=int(args.rows))
    rgb = _embed_frames(x, config)
    landmarks, frame_mask, ly, lsplit = _load_landmarks(config)
    landmarks = landmarks[: len(rgb)]
    frame_mask = frame_mask[: len(rgb)]
    if not np.array_equal(y, ly[: len(y)]) or not np.array_equal(
        split_index, lsplit[: len(split_index)]
    ):
        raise ValueError("smoke RGB/landmark labels do not align")
    summary: dict[str, Any] = {
        "experiment": config["experiment"],
        "run_dir": str(run_dir.resolve()),
        "rows": int(len(rgb)),
        "branches": {},
    }
    for branch in config["branches"]:
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(12345)
        model = _build_model(
            branch,
            tuple(landmarks.shape[1:]),
            tuple(rgb.shape[1:]),
            int(config["class_count"]),
            float(config["learning_rate"]),
        )
        probs = model.predict(
            _inputs_for(branch, landmarks, frame_mask, rgb), batch_size=2, verbose=0
        )
        loss = model.train_on_batch(_inputs_for(branch, landmarks, frame_mask, rgb), y)
        weights_path = run_dir / "smoke" / f"{branch}.weights.h5"
        model.save_weights(weights_path)
        summary["branches"][branch] = {
            "forward_shape": [int(v) for v in probs.shape],
            "train_on_batch": [float(v) for v in np.atleast_1d(loss).tolist()],
            "weights_saved": str(weights_path.resolve()),
        }
    (run_dir / "smoke" / "smoke_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    import tensorflow as tf

    run_dir = args.run_dir
    config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
    landmarks, frame_mask, y, split_index = _load_landmarks(config)
    rgb, rgb_y, rgb_split = _load_or_build_rgb_embeddings(run_dir, config)
    if not (np.array_equal(y, rgb_y) and np.array_equal(split_index, rgb_split)):
        raise ValueError("RGB/landmark labels or splits do not align")
    train_mask = split_index == 0
    val_mask = split_index == 1
    start = time.perf_counter()
    results: dict[str, Any] = {
        "experiment": config["experiment"],
        "run_dir": str(run_dir.resolve()),
        "landmark_shape": [int(v) for v in landmarks.shape],
        "rgb_shape": [int(v) for v in rgb.shape],
        "branches": {},
        "elapsed_seconds": None,
        "passed": True,
    }
    for branch in config["branches"]:
        results["branches"][branch] = {}
        for seed in config["seeds"]:
            seed = int(seed)
            tf.keras.backend.clear_session()
            tf.keras.utils.set_random_seed(seed)
            seed_dir = run_dir / "models" / branch / f"seed_{seed}"
            seed_dir.mkdir(parents=True, exist_ok=True)
            latest = seed_dir / "latest.weights.h5"
            best = seed_dir / "best.weights.h5"
            epoch_file = run_dir / "logs" / f"{branch}_seed_{seed}_epoch_count.txt"
            history_path = run_dir / "logs" / f"{branch}_seed_{seed}_history.csv"
            if latest.exists() and not args.resume:
                raise FileExistsError(
                    f"{branch} seed {seed}: latest weights exist; rerun with --resume"
                )
            model = _build_model(
                branch,
                tuple(landmarks.shape[1:]),
                tuple(rgb.shape[1:]),
                int(config["class_count"]),
                float(config["learning_rate"]),
            )
            if args.resume and latest.exists():
                model.load_weights(latest)
                initial_epoch = int(epoch_file.read_text(encoding="utf-8"))
            else:
                initial_epoch = 0
            history = model.fit(
                _inputs_for(branch, landmarks[train_mask], frame_mask[train_mask], rgb[train_mask]),
                y[train_mask],
                validation_data=(
                    _inputs_for(branch, landmarks[val_mask], frame_mask[val_mask], rgb[val_mask]),
                    y[val_mask],
                ),
                batch_size=int(config["batch_size"]),
                epochs=initial_epoch + int(config["epochs"]),
                initial_epoch=initial_epoch,
                callbacks=[
                    tf.keras.callbacks.ModelCheckpoint(
                        str(best),
                        monitor="val_accuracy",
                        mode="max",
                        save_best_only=True,
                        save_weights_only=True,
                    ),
                    tf.keras.callbacks.CSVLogger(str(history_path), append=history_path.exists()),
                ],
                verbose=2,
            )
            model.save_weights(latest)
            total_epochs = initial_epoch + int(config["epochs"])
            epoch_file.write_text(str(total_epochs), encoding="utf-8")
            results["branches"][branch][str(seed)] = {
                "latest": _evaluate(
                    branch,
                    model,
                    landmarks,
                    frame_mask,
                    rgb,
                    y,
                    split_index,
                    int(config["batch_size"]),
                    config["classes"],
                ),
                "best": _evaluate(
                    branch,
                    _load_weights_model(
                        branch,
                        tuple(landmarks.shape[1:]),
                        tuple(rgb.shape[1:]),
                        int(config["class_count"]),
                        float(config["learning_rate"]),
                        best,
                    ),
                    landmarks,
                    frame_mask,
                    rgb,
                    y,
                    split_index,
                    int(config["batch_size"]),
                    config["classes"],
                ),
                "epoch_count_total": int(total_epochs),
                "history_last": {
                    key: float(values[-1]) for key, values in history.history.items() if values
                },
            }
            (run_dir / "metrics" / "metrics_partial.json").write_text(
                json.dumps(results, indent=2), encoding="utf-8"
            )
    results["elapsed_seconds"] = time.perf_counter() - start
    results["summary"] = _summarize(results, config)
    (run_dir / "metrics" / "metrics.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    (run_dir / "metrics" / "metrics.md").write_text(_metrics_markdown(results), encoding="utf-8")
    return results


def _load_weights_model(
    kind: str,
    landmark_shape: tuple[int, int],
    rgb_shape: tuple[int, int],
    classes: int,
    lr: float,
    weights_path: Path,
):
    model = _build_model(kind, landmark_shape, rgb_shape, classes, lr)
    model.load_weights(weights_path)
    return model


def _evaluate(
    branch: str,
    model: Any,
    landmarks: np.ndarray,
    frame_mask: np.ndarray,
    rgb: np.ndarray,
    y: np.ndarray,
    split_index: np.ndarray,
    batch_size: int,
    classes: list[str],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for sid, split in SPLITS.items():
        mask = split_index == split
        probs = model.predict(
            _inputs_for(branch, landmarks[mask], frame_mask[mask], rgb[mask]),
            batch_size=batch_size,
            verbose=0,
        )
        pred = np.argmax(probs, axis=1)
        counts: dict[str, int] = {}
        for idx in pred:
            counts[classes[int(idx)]] = counts.get(classes[int(idx)], 0) + 1
        out[sid] = {
            "accuracy": float(np.mean(pred == y[mask])),
            "mean_confidence": float(np.mean(np.max(probs, axis=1))),
            "count": int(np.sum(mask)),
            "predicted_class_counts": dict(sorted(counts.items())),
        }
    return out


def _summarize(results: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    by_branch = {}
    winners = {}
    for branch, seeds in results["branches"].items():
        trains = np.asarray(
            [item["best"]["train"]["accuracy"] for item in seeds.values()], dtype=np.float32
        )
        vals = np.asarray(
            [item["best"]["val"]["accuracy"] for item in seeds.values()], dtype=np.float32
        )
        tests = np.asarray(
            [item["best"]["test"]["accuracy"] for item in seeds.values()], dtype=np.float32
        )
        by_branch[branch] = {
            "mean_best_train": float(np.mean(trains)),
            "mean_best_val": float(np.mean(vals)),
            "std_best_val": float(np.std(vals)),
            "mean_best_test": float(np.mean(tests)),
            "std_best_test": float(np.std(tests)),
            "mean_train_val_gap": float(np.mean(trains - vals)),
            "mean_val_test_gap": float(np.mean(vals - tests)),
            "seed_count": int(len(vals)),
        }
    seed_ids = sorted({seed for values in results["branches"].values() for seed in values})
    for seed in seed_ids:
        candidates = {
            branch: values[seed]["best"]["val"]["accuracy"]
            for branch, values in results["branches"].items()
            if seed in values
        }
        winners[seed] = max(candidates, key=candidates.get)
    best_val = max(by_branch, key=lambda branch: by_branch[branch]["mean_best_val"])
    best_test = max(by_branch, key=lambda branch: by_branch[branch]["mean_best_test"])
    ref = config["baseline_reference"]
    return {
        "by_branch": by_branch,
        "winner_by_seed_best_val": winners,
        "decision_hint": {
            "best_mean_validation_branch": best_val,
            "best_mean_test_branch": best_test,
            "fusion_val_gain_over_e3_b6_masked": float(
                by_branch["fusion_aug_rgb"]["mean_best_val"] - ref["e3_b6_aug_masked_val"]
            ),
            "fusion_test_gain_over_e3_b6_conv": float(
                by_branch["fusion_aug_rgb"]["mean_best_test"] - ref["e3_b6_aug_conv_test"]
            ),
            "promising": bool(
                by_branch["fusion_aug_rgb"]["mean_best_test"] >= ref["e3_b6_aug_conv_test"] + 0.03
                and by_branch["fusion_aug_rgb"]["mean_best_val"] >= ref["e3_b6_aug_masked_val"]
                and by_branch["fusion_aug_rgb"]["mean_best_test"]
                > by_branch["landmark_aug_only"]["mean_best_test"]
                and by_branch["fusion_aug_rgb"]["mean_best_test"]
                > by_branch["rgb_only"]["mean_best_test"]
            ),
        },
    }


def check(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = args.run_dir
    errors = []
    required = ["pilot_config.json", "pilot_manifest.csv", "README_RUN.md"]
    for relative in required:
        if not (run_dir / relative).exists():
            errors.append(f"missing output: {relative}")
    config = {}
    if (run_dir / "pilot_config.json").exists():
        config = json.loads((run_dir / "pilot_config.json").read_text(encoding="utf-8"))
        if len(_read_csv(run_dir / "pilot_manifest.csv")) != int(config.get("rows", -1)):
            errors.append("manifest row count mismatch")
    if args.require_metrics and not (run_dir / "metrics" / "metrics.json").exists():
        errors.append("missing output: metrics/metrics.json")
    if (run_dir / "metrics" / "metrics.json").exists() and config:
        metrics = json.loads((run_dir / "metrics" / "metrics.json").read_text(encoding="utf-8"))
        for branch in config.get("branches", []):
            for seed in config.get("seeds", []):
                for relative in (
                    f"models/{branch}/seed_{seed}/latest.weights.h5",
                    f"models/{branch}/seed_{seed}/best.weights.h5",
                    f"logs/{branch}_seed_{seed}_history.csv",
                    f"logs/{branch}_seed_{seed}_epoch_count.txt",
                ):
                    if not (run_dir / relative).exists():
                        errors.append(f"missing output: {relative}")
                if str(seed) not in metrics.get("branches", {}).get(branch, {}):
                    errors.append(f"missing metrics for {branch} seed {seed}")
    result = {"run_dir": str(run_dir.resolve()), "passed": not errors, "errors": errors}
    (run_dir / "check_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _runbook(config: dict[str, Any]) -> str:
    run_dir = config["run_dir"]
    return "\n".join(
        [
            "# E3-C Landmark + RGB Fusion",
            "",
            "This is an isolated frozen-split fusion experiment. It does not change Android "
            "or production assets.",
            "",
            "## Run",
            "",
            "```powershell",
            'cd "F:\\ASL DATASET\\5. Apphear3"',
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_c_fusion run --run-dir "{run_dir}"',
            "```",
            "",
            "## Resume",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_c_fusion run --run-dir '
            f'"{run_dir}" --resume',
            "```",
            "",
            "## Check",
            "",
            "```powershell",
            f'.\\.venv\\Scripts\\python.exe -m pipeline.rgb.e3_c_fusion check --run-dir '
            f'"{run_dir}" --require-metrics',
            "```",
            "",
        ]
    )


def _metrics_markdown(metrics: dict[str, Any]) -> str:
    lines = [
        "# E3-C Landmark + RGB Fusion Metrics",
        "",
        "| Branch | Seed | Best Val | Best Test | Latest Val | Latest Test |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for branch, seeds in metrics["branches"].items():
        for seed, result in seeds.items():
            lines.append(
                f"| {branch} | {seed} | {result['best']['val']['accuracy']:.4f} | "
                f"{result['best']['test']['accuracy']:.4f} | "
                f"{result['latest']['val']['accuracy']:.4f} | "
                f"{result['latest']['test']['accuracy']:.4f} |"
            )
    lines.extend(
        [
            "",
            "## Summary",
            "",
            "```json",
            json.dumps(metrics.get("summary", {}), indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="E3-C landmark + RGB fusion")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    prepare_parser.add_argument("--landmark-run", type=Path, default=DEFAULT_LANDMARK_RUN)
    prepare_parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    prepare_parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    prepare_parser.add_argument("--features-config", type=Path, default=DEFAULT_FEATURES_CONFIG)
    prepare_parser.add_argument("--videos-root", type=Path, default=DEFAULT_VIDEOS_ROOT)
    prepare_parser.add_argument("--frames", type=int, default=16)
    prepare_parser.add_argument("--image-size", type=int, default=160)
    prepare_parser.add_argument(
        "--crop-mode", default="upper_body_center", choices=["upper_body_center", "full_frame"]
    )
    prepare_parser.add_argument("--encoder", default="mobilenetv3small")
    prepare_parser.add_argument("--weights", default="imagenet", choices=["imagenet", "none"])
    prepare_parser.add_argument("--embedding-batch-size", type=int, default=32)
    prepare_parser.add_argument("--batch-size", type=int, default=8)
    prepare_parser.add_argument("--epochs", type=int, default=12)
    prepare_parser.add_argument("--learning-rate", type=float, default=5e-4)
    prepare_parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    prepare_parser.add_argument("--overwrite", action="store_true")

    smoke_parser = sub.add_parser("smoke")
    smoke_parser.add_argument("--run-dir", type=Path, required=True)
    smoke_parser.add_argument("--rows", type=int, default=8)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--run-dir", type=Path, required=True)
    run_parser.add_argument("--resume", action="store_true")

    check_parser = sub.add_parser("check")
    check_parser.add_argument("--run-dir", type=Path, required=True)
    check_parser.add_argument("--require-metrics", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "smoke":
            result = smoke(args)
        elif args.command == "run":
            result = run(args)
        elif args.command == "check":
            result = check(args)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (FileNotFoundError, KeyError, ValueError, OSError) as error:
        print(f"[rgb/e3-c] ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


