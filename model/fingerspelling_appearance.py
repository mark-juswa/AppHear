"""Pinned local, frozen mobile appearance encoder. Never downloads weights."""

from __future__ import annotations

import importlib.metadata
import shutil
from pathlib import Path
from typing import Any

from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.visual_crop import config

PACKAGE = REPO / "datasets/fingerspelling/visual_fusion_01"
EVIDENCE = REPO / "artifacts/fingerspelling_visual_fusion_01"


def weights_path() -> Path:
    return PACKAGE / "encoder" / str(config()["weights_filename"])


def ensure_weights() -> Path:
    cfg = config()
    path = weights_path()
    if not path.exists():
        cached = Path.home() / ".keras/models" / cfg["weights_filename"]
        if not cached.is_file() or sha256(cached) != cfg["weights_sha256"]:
            raise ValueError(
                "[visual/encoder] Pinned local weights unavailable; no download attempted"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cached, path)
    if sha256(path) != cfg["weights_sha256"]:
        raise ValueError("[visual/encoder] Weights identity mismatch")
    return path


def encoder_identity() -> dict[str, Any]:
    return {
        "schema_version": "HandAppearanceEncoder.v1",
        "weights_sha256": config()["weights_sha256"],
        "implementation_sha256": sha256(REPO / "model/fingerspelling_appearance.py"),
        "tensorflow": importlib.metadata.version("tensorflow"),
        "keras": importlib.metadata.version("keras"),
        "training": False,
    }


def build_encoder(tf: Any) -> Any:
    cfg = config()
    path = ensure_weights()
    model = tf.keras.applications.MobileNetV3Small(
        input_shape=(cfg["crop_size"], cfg["crop_size"], 3),
        alpha=cfg["encoder_alpha"],
        include_top=False,
        weights=str(path),
        pooling="avg",
        include_preprocessing=False,
    )
    model.trainable = False
    if model.output_shape != (None, cfg["embedding_width"]):
        raise ValueError("[visual/encoder] Unexpected embedding width")

    @tf.function(
        input_signature=[tf.TensorSpec([None, cfg["crop_size"], cfg["crop_size"], 3], tf.float32)],
        jit_compile=False,
    )
    def encode(batch: Any) -> Any:
        return model(batch, training=False)

    model.apphear_encode = encode
    return model
