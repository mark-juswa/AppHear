"""Train the Phase-0 isolated causal-TCN classifier on v3.0 features.

  python -m model.train --smoke              # tiny synthetic run: validates the code path
  python -m model.train                      # REAL run (developer executes; slow)
  python -m model.train --epochs 80          # override an epoch count

Cross-signer by construction: train/val/test come from signer-disjoint stage-F arrays.
Reports val top-1/top-5 per epoch; the full per-signer + calibration eval is feature 08."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

DEFAULT_CONFIG = Path(__file__).resolve().parent / "config" / "train.yaml"


@dataclass(frozen=True)
class TrainConfig:
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
    label_smoothing: float
    aug_enabled: bool
    rotation_deg: float
    scale: float
    noise_std: float
    frame_mask_frac: float
    features_dir: Path
    output_dir: Path


def load_train_config(path: Path) -> TrainConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    m, t = raw["model"], raw["train"]
    a = raw.get("augment", {})
    return TrainConfig(
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
        label_smoothing=float(t.get("label_smoothing", 0.0)),
        aug_enabled=bool(a.get("enabled", False)),
        rotation_deg=float(a.get("rotation_deg", 0.0)),
        scale=float(a.get("scale", 0.0)),
        noise_std=float(a.get("noise_std", 0.0)),
        frame_mask_frac=float(a.get("frame_mask_frac", 0.0)),
        features_dir=Path(raw["features_dir"]),
        output_dir=Path(raw["output_dir"]),
    )


def _synthetic(seed: int, n: int = 96, t: int = 64, f: int = 258, c: int = 12) -> tuple:
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((n, t, f)).astype(np.float32)
    y = rng.integers(0, c, size=n).astype(np.int32)
    return x, y, c


def _build_and_compile(input_len: int, feat_dim: int, num_classes: int, cfg: TrainConfig) -> Any:
    import tensorflow as tf

    from .model import build_classifier

    model = build_classifier(
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
        loss=tf.keras.losses.CategoricalCrossentropy(label_smoothing=cfg.label_smoothing),
        metrics=[
            tf.keras.metrics.CategoricalAccuracy(name="top1"),
            tf.keras.metrics.TopKCategoricalAccuracy(k=5, name="top5"),
        ],
    )
    return model


def run(config_path: Path, smoke: bool, epochs_override: int | None) -> int:
    import tensorflow as tf

    from .data import load_split, load_vocab, make_dataset

    cfg = load_train_config(config_path)
    tf.keras.utils.set_random_seed(cfg.seed)

    if smoke:
        x_tr, y_tr, num_classes = _synthetic(cfg.seed)
        x_val, y_val, _ = _synthetic(cfg.seed + 1)
        epochs = 2
        out_dir = cfg.output_dir / "smoke"
    else:
        if not (cfg.features_dir / "train.npz").exists():
            print(
                f"[train] no train.npz in {cfg.features_dir} — build features first "
                f"(see pipeline/run_pipeline.py)",
                file=sys.stderr,
            )
            return 2
        vocab = load_vocab(cfg.features_dir)
        num_classes = len(vocab)
        x_tr, y_tr, _ = load_split(cfg.features_dir, "train")
        x_val, y_val, _ = load_split(cfg.features_dir, "val")
        epochs = epochs_override or cfg.epochs
        out_dir = cfg.output_dir

    out_dir.mkdir(parents=True, exist_ok=True)
    input_len, feat_dim = x_tr.shape[1], x_tr.shape[2]
    model = _build_and_compile(input_len, feat_dim, num_classes, cfg)

    augment_fn = None
    if cfg.aug_enabled:
        from .augment import AugmentConfig, augment_batch

        acfg = AugmentConfig(cfg.rotation_deg, cfg.scale, cfg.noise_std, cfg.frame_mask_frac)
        rng = np.random.default_rng(cfg.seed)
        augment_fn = lambda a: augment_batch(a, acfg, rng)  # noqa: E731

    print(
        f"[train] {'SMOKE' if smoke else 'REAL'} run: X_train={x_tr.shape} "
        f"classes={num_classes} params={model.count_params():,} epochs={epochs} "
        f"dropout={cfg.dropout} aug={cfg.aug_enabled} wd={cfg.weight_decay} "
        f"ls={cfg.label_smoothing}"
    )

    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            str(out_dir / "best.keras"), monitor="val_top1", mode="max", save_best_only=True
        ),
        tf.keras.callbacks.CSVLogger(str(out_dir / "history.csv")),
        tf.keras.callbacks.EarlyStopping(
            monitor="val_top1",
            mode="max",
            patience=cfg.early_stop_patience,
            restore_best_weights=True,
        ),
    ]
    train_ds = make_dataset(
        x_tr,
        y_tr,
        cfg.batch_size,
        shuffle=True,
        seed=cfg.seed,
        num_classes=num_classes,
        one_hot=True,
        augment_fn=augment_fn,
    )
    val_ds = make_dataset(
        x_val,
        y_val,
        cfg.batch_size,
        shuffle=False,
        seed=cfg.seed,
        num_classes=num_classes,
        one_hot=True,
    )
    model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=epochs,
        callbacks=callbacks,
        shuffle=False,  # the tf.data pipeline already shuffles
        verbose=2,
    )
    model.save(out_dir / "final.keras")
    print(f"[train] done -> {out_dir}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="AppHear 3 isolated causal-TCN trainer")
    p.add_argument("--smoke", action="store_true", help="tiny synthetic run to validate the code")
    p.add_argument("--epochs", type=int, default=None)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = p.parse_args()
    return run(args.config, args.smoke, args.epochs)


if __name__ == "__main__":
    raise SystemExit(main())
