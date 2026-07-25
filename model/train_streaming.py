"""Feature 11 â€” train the Phase-1 per-frame streaming classifier.

  python -m model.train_streaming --smoke     # tiny synthetic run: validates the code path
  python -m model.train_streaming             # REAL run (developer executes)

Per-frame softmax over the vocab, every real frame targets the gloss (padded frames masked via
sample_weight). Encoder warm-started from the isolated best.keras. Trains on features_streaming/."""

from __future__ import annotations

import os

# oneDNN's INT32 primitive falls back to a path that SEGFAULTS on CPUs without AVX-512 (verified via
# faulthandler: the GCN encoder's INT32 keypoint-gather crashes with a Windows access violation on
# the first training step; disabling oneDNN trains cleanly). Must be set BEFORE TensorFlow is
# imported. Negligible numeric effect (float op-order only); correctness preserved. Harmless for the
# TCN (no INT32 gather). Override by exporting TF_ENABLE_ONEDNN_OPTS=1 if ever needed.
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import argparse  # noqa: E402
import sys  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

import numpy as np  # noqa: E402
import yaml  # noqa: E402

DEFAULT_CONFIG = Path(__file__).resolve().parent / "config" / "train_streaming.yaml"


@dataclass(frozen=True)
class StreamConfig:
    blocks: int
    channels: int
    dilations: tuple[int, ...]
    kernel: int
    dropout: float
    seed: int
    batch_size: int
    epochs: int
    learning_rate: float
    early_stop_patience: int
    weight_decay: float
    aug_enabled: bool
    rotation_deg: float
    scale: float
    noise_std: float
    frame_mask_frac: float
    warm_start_from: Path | None
    features_dir: Path
    output_dir: Path
    # dir holding vocab.json for num_classes; None -> features_dir.parent/"features"
    vocab_dir: Path | None
    class_weighting_enabled: bool = False
    class_weighting_weights: dict[str, float] | None = None
    # encoder-upgrade (context/encoder-upgrade.md): "tcn" (default) or "gcn" (ST-GCN candidate A).
    # The gcn model is CLIP-level with its posterior tiled across T â€” same I/O contract, so the
    # per-frame masked loss/eval below work unchanged (mean over identical rows = the clip prob).
    model_type: str = "tcn"
    gcn_channels: tuple[int, ...] | None = None
    gcn_early_strides: bool = False   # temporal downsample at blocks {0,4} instead of {4,7} (~2x)
    gcn_keypoints: str | None = None  # "upper51" -> hands + upper-body subset (~2x with strides)


def load_stream_config(path: Path) -> StreamConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    m, t, a = raw["model"], raw["train"], raw.get("augment", {})
    cw = raw.get("class_weighting", {})
    ws = raw.get("warm_start_from")
    return StreamConfig(
        blocks=int(m["blocks"]),
        channels=int(m["channels"]),
        dilations=tuple(m["dilations"]),
        kernel=int(m["kernel"]),
        dropout=float(m["dropout"]),
        seed=int(t["seed"]),
        batch_size=int(t["batch_size"]),
        epochs=int(t["epochs"]),
        learning_rate=float(t["learning_rate"]),
        early_stop_patience=int(t["early_stop_patience"]),
        weight_decay=float(t.get("weight_decay", 0.0)),
        aug_enabled=bool(a.get("enabled", False)),
        rotation_deg=float(a.get("rotation_deg", 0.0)),
        scale=float(a.get("scale", 0.0)),
        noise_std=float(a.get("noise_std", 0.0)),
        frame_mask_frac=float(a.get("frame_mask_frac", 0.0)),
        warm_start_from=Path(ws) if ws else None,
        features_dir=Path(raw["features_dir"]),
        output_dir=Path(raw["output_dir"]),
        vocab_dir=Path(raw["vocab_dir"]) if raw.get("vocab_dir") else None,
        class_weighting_enabled=bool(cw.get("enabled", False)),
        class_weighting_weights={str(k): float(v) for k, v in cw.get("weights", {}).items()},
        model_type=str(m.get("type", "tcn")),
        gcn_channels=tuple(m["gcn_channels"]) if m.get("gcn_channels") else None,
        gcn_early_strides=bool(m.get("gcn_early_strides", False)),
        gcn_keypoints=m.get("gcn_keypoints"),
    )



def _apply_class_weighting(
    frame_mask: np.ndarray,
    y: np.ndarray,
    vocab: dict[str, int],
    weights: dict[str, float] | None,
) -> np.ndarray:
    """Return per-frame sample weights with optional per-class multipliers.

    The feature tensor and label contract stay unchanged. Only the training loss contribution of
    selected clips changes; validation remains unweighted so eval is comparable to older runs.
    """
    if not weights:
        return frame_mask
    multipliers = np.ones(int(max(vocab.values())) + 1, dtype=np.float32)
    applied: list[str] = []
    for gloss, weight in weights.items():
        class_id = vocab.get(gloss)
        if class_id is None:
            print(f"[stream] class_weighting skipped unknown gloss: {gloss}", file=sys.stderr)
            continue
        multipliers[class_id] = max(float(weight), 0.0)
        applied.append(f"{gloss}={multipliers[class_id]:.2f}")
    if not applied:
        return frame_mask
    print("[stream] class_weighting active: " + ", ".join(applied))
    return frame_mask.astype(np.float32) * multipliers[y][:, None]

def warm_start_encoder(stream_model: Any, isolated_path: Path) -> int:
    """Copy matching-name layer weights (the shared causal encoder) from the isolated model into
    the streaming model. The head differs (per-frame vs pooled) and is skipped. Returns #copied."""
    import tensorflow as tf

    # compile=False: we only copy weights (skips optimizer deserialization). safe_mode=False: our
    # own artifacts are trusted â€” required to load checkpoints containing Lambda layers (the
    # pre-rewrite GCN best.keras; the current GCN is Lambda-free but old checkpoints must resume).
    iso = tf.keras.models.load_model(isolated_path, compile=False, safe_mode=False)
    iso_layers = {layer.name: layer for layer in iso.layers}
    copied = 0
    for layer in stream_model.layers:
        src = iso_layers.get(layer.name)
        if src is None or not layer.get_weights():
            continue
        try:
            layer.set_weights(src.get_weights())
            copied += 1
        except ValueError:
            pass  # shape mismatch (the head) â€” expected
    return copied


def _synthetic(seed: int, n: int = 96, t: int = 96, f: int = 258, c: int = 12) -> tuple:
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((n, t, f)).astype(np.float32)
    y = rng.integers(0, c, size=n).astype(np.int32)
    fm = np.zeros((n, t), dtype=bool)
    for i in range(n):
        fm[i, : rng.integers(t // 2, t + 1)] = True  # variable real length
    return x, y, fm, c


def _build_and_compile(input_len: int, feat_dim: int, num_classes: int, cfg: StreamConfig) -> Any:
    import tensorflow as tf

    if cfg.model_type == "gcn":
        from .model_gcn import UPPER51, build_stgcn

        model = build_stgcn(
            input_len,
            feat_dim,
            num_classes,
            channels=cfg.gcn_channels or (32, 32, 32, 32, 64, 64, 64, 128, 128, 128),
            dropout=cfg.dropout,
            strides={0: 2, 4: 2} if cfg.gcn_early_strides else None,
            keypoint_subset=UPPER51 if cfg.gcn_keypoints == "upper51" else None,
        )
    else:
        from .model import build_streaming_classifier

        model = build_streaming_classifier(
            input_len,
            feat_dim,
            num_classes,
            blocks=cfg.blocks,
            channels=cfg.channels,
            dilations=cfg.dilations,
            kernel=cfg.kernel,
            dropout=cfg.dropout,
        )
    model.compile(
        optimizer=tf.keras.optimizers.AdamW(cfg.learning_rate, weight_decay=cfg.weight_decay),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(),  # per-frame; padded frames masked
        weighted_metrics=[tf.keras.metrics.SparseCategoricalAccuracy(name="pf_acc")],
    )
    return model


def run(config_path: Path, smoke: bool, epochs_override: int | None) -> int:
    import tensorflow as tf

    from .data import load_streaming_split, load_vocab, make_stream_dataset

    cfg = load_stream_config(config_path)
    tf.keras.utils.set_random_seed(cfg.seed)

    if smoke:
        x_tr, y_tr, fm_tr, num_classes = _synthetic(cfg.seed)
        x_val, y_val, fm_val, _ = _synthetic(cfg.seed + 1)
        epochs, out_dir, warm = 2, cfg.output_dir / "smoke", None
    else:
        if not (cfg.features_dir / "train.npz").exists():
            print(
                f"[stream] no streaming features in {cfg.features_dir} â€” run "
                f"pipeline.features.streaming first",
                file=sys.stderr,
            )
            return 2
        vocab_dir = cfg.vocab_dir or (cfg.features_dir.parent / "features")
        vocab = load_vocab(vocab_dir)
        num_classes = len(vocab)
        x_tr, y_tr, fm_tr, _, _ = load_streaming_split(cfg.features_dir, "train")
        x_val, y_val, fm_val, _, _ = load_streaming_split(cfg.features_dir, "val")
        epochs, out_dir, warm = epochs_override or cfg.epochs, cfg.output_dir, cfg.warm_start_from

    out_dir.mkdir(parents=True, exist_ok=True)
    input_len, feat_dim = x_tr.shape[1], x_tr.shape[2]
    model = _build_and_compile(input_len, feat_dim, num_classes, cfg)

    n_warm = warm_start_encoder(model, warm) if (warm and warm.exists()) else 0

    augment_fn = None
    if cfg.aug_enabled:
        from .augment import AugmentConfig, augment_batch

        acfg = AugmentConfig(cfg.rotation_deg, cfg.scale, cfg.noise_std, cfg.frame_mask_frac)
        rng = np.random.default_rng(cfg.seed)
        augment_fn = lambda a: augment_batch(a, acfg, rng)  # noqa: E731

    if cfg.class_weighting_enabled and not smoke:
        fm_tr = _apply_class_weighting(fm_tr, y_tr, vocab, cfg.class_weighting_weights)

    print(
        f"[stream] {'SMOKE' if smoke else 'REAL'}: X={x_tr.shape} classes={num_classes} "
        f"params={model.count_params():,} epochs={epochs} warm_started_layers={n_warm}"
    )

    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            str(out_dir / "best.keras"), monitor="val_pf_acc", mode="max", save_best_only=True
        ),
        tf.keras.callbacks.CSVLogger(str(out_dir / "history.csv")),
        tf.keras.callbacks.EarlyStopping(
            monitor="val_pf_acc",
            mode="max",
            patience=cfg.early_stop_patience,
            restore_best_weights=True,
        ),
    ]
    model.fit(
        make_stream_dataset(x_tr, y_tr, fm_tr, cfg.batch_size, True, cfg.seed, augment_fn),
        validation_data=make_stream_dataset(x_val, y_val, fm_val, cfg.batch_size, False, cfg.seed),
        epochs=epochs,
        callbacks=callbacks,
        shuffle=False,
        verbose=2,
    )
    model.save(out_dir / "final.keras")
    print(f"[stream] done -> {out_dir}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="AppHear 3 per-frame streaming trainer")
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--epochs", type=int, default=None)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = p.parse_args()
    return run(args.config, args.smoke, args.epochs)


if __name__ == "__main__":
    raise SystemExit(main())

