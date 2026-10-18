"""Experimental WORD-track run: recognition-v2 TCN with phone-cadence and hand-loss augmentation.

Scientific delta versus tcn_v2_run_01 (the source of the Android recognizer): the per-clip sparse
training view. The baseline trains every epoch on one dense view plus ONE fixed PHONE_01 sparse view
(5.6 fps, phase 0). Here the dense view is unchanged and the sparse view is drawn each epoch from a
seeded pool of real-observation views with random cadence (2.5-7.5 fps), random phase and simulated
refiner rejection (0-40% of accepted hand entries, random or fastest-motion-first, proposals kept).
Motivation: docs/audit/RECOGNITION_PIPELINE_BOTTLENECK_ASSESSMENT_2026-10-16.md (phones run at about
3.75 fps; hand loss compounds with sparse cadence).

Unchanged: population (3,926 TRAIN / 816 signer-disjoint DEV), vocabulary, V2 contract [96,350],
architecture (4x64 mask-aware causal TCN), optimizer, seed, epochs, early stopping, and selection on
DEV val_loss over the same precomputed dense+sparse DEV views. Output goes to a new run directory;
nothing in the Android assets or the frozen run changes. No protected TEST access.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any

import numpy as np

from eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter import subset_raw
from model.perception_vnext.recognition_utility_236 import sha256, write_json
from model.perception_vnext.recognition_v2_236 import _build_tcn
from pipeline.perception_vnext.recognition_schema import (
    MAX_SEQUENCE_LENGTH,
    RawSequence,
    load_raw_sequence,
    select_nearest_unique,
)
from pipeline.perception_vnext.recognition_schema_v2 import (
    FEATURE_WIDTH_V2,
    derive_selected_features_v2,
    temporal_view_v2,
)

ROOT = Path(__file__).resolve().parents[2]
RU = Path("artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01")
RAW_INDEX = RU / "dataset/index.jsonl"
SEMLEX = RU / "semlex_candidate_raw_01"
# 2026-10-18: forms accepted in human review package 02 (40 further classes)
SEMLEX_02 = RU / "semlex_candidate_raw_02"
# Pre-registered before training: the new classes keep at most two clips per signer, so they gain
# signer diversity without a large class-prior shift (MONEY1 alone has 195 accepted clips).
SEMLEX_02_CAP_PER_SIGNER_CLASS = 2
V2_DATASET = RU / "representation_v2_236_production_01/dataset"
CONFIG = (
    ROOT
    / "model/config/recognition_upgrade/perception_vnext_representation_v2_236_production_01.json"
)
AUG = {
    "pool_size": 10,
    "fps_range": [2.5, 7.5],
    "hand_drop_range": [0.0, 0.4],
    "hand_drop_modes": ["random", "motion"],
    "pool_seed": 7103,
    "original_view_fraction": 0.0,
}
# v2 (2026-10-16, after v1 regressed on phone TABLE/HOME): keep the baseline PHONE_01 sparse view
# for half of the sparse draws and cap simulated refiner rejection at 25%.
AUG_V2 = {**AUG, "hand_drop_range": [0.0, 0.25], "original_view_fraction": 0.5, "pool_seed": 7104}
# v3 (2026-10-17, after phone shadow sessions): v2 + neighbour context. On device, v2 failed only
# when the event window also held the next sign's onset; some augmented views therefore carry the
# tail of a preceding and/or the onset of a following sign (same signer when possible).
AUG_V3 = {
    **AUG_V2,
    "neighbour_probability": 0.4,
    "neighbour_fraction_range": [0.15, 0.6],
    "pool_seed": 7105,
}


def drop_hands(
    raw: RawSequence, fraction: float, mode: str, rng: np.random.Generator
) -> RawSequence:
    observed = np.asarray(raw.hand_observed, bool).copy()
    entries = np.argwhere(observed)
    count = int(round(fraction * len(entries)))
    if count == 0:
        return raw
    if mode == "random":
        chosen = rng.choice(len(entries), size=count, replace=False)
    else:
        wrist = np.asarray(raw.hand_xy, np.float64)[:, :, 0, :]
        speed = np.zeros(observed.shape)
        speed[1:] = np.linalg.norm(np.diff(wrist, axis=0), axis=-1)
        speed[~np.isfinite(speed)] = 0.0
        chosen = np.argsort(-speed[entries[:, 0], entries[:, 1]], kind="stable")[:count]
    for frame, side in entries[chosen]:
        observed[frame, side] = False
    values = {f.name: getattr(raw, f.name) for f in dataclass_fields(RawSequence)}
    values["hand_observed"] = observed
    return RawSequence(**values)


def augmented_view(raw: RawSequence, rng: np.random.Generator) -> np.ndarray:
    fps = float(rng.uniform(*AUG["fps_range"]))
    step = 1000.0 / fps
    t = np.asarray(raw.timestamp_ms, np.float64)
    start = t[0] + float(rng.uniform(0.0, step))
    targets = np.arange(start, t[-1] + step * 0.25, step)
    indices = select_nearest_unique(t, targets) if len(targets) else np.zeros(0, np.int32)
    if len(indices) == 0:
        indices = np.asarray([int(np.argmin(np.abs(t - start)))], np.int32)
    if len(indices) > MAX_SEQUENCE_LENGTH:
        indices = indices[np.linspace(0, len(indices) - 1, MAX_SEQUENCE_LENGTH).astype(int)]
    fraction = float(rng.uniform(*AUG["hand_drop_range"]))
    mode = str(rng.choice(AUG["hand_drop_modes"]))
    return derive_selected_features_v2(drop_hands(raw, fraction, mode, rng), np.unique(indices))


def concat_raws(parts: list[RawSequence]) -> RawSequence:
    """Join real observations end to end at the clip's own median spacing (no new frames)."""
    spacing = (
        float(np.median(np.diff(parts[len(parts) // 2].timestamp_ms)))
        if len(parts[len(parts) // 2].timestamp_ms) > 1
        else 33.3
    )
    chunks: dict[str, list[np.ndarray]] = {}
    stamps, offset = [], 0.0
    for part in parts:
        t = np.asarray(part.timestamp_ms, np.float64)
        stamps.append(t - t[0] + offset)
        offset = float(stamps[-1][-1]) + spacing
        for f in dataclass_fields(RawSequence):
            if f.name not in ("metadata", "frame_index", "timestamp_ms"):
                chunks.setdefault(f.name, []).append(np.asarray(getattr(part, f.name)))
    timestamp = np.concatenate(stamps)
    return RawSequence(
        metadata=dict(parts[0].metadata),
        frame_index=np.arange(len(timestamp), dtype=np.int32),
        timestamp_ms=timestamp,
        **{k: np.concatenate(v) for k, v in chunks.items()},
    )


def with_neighbours(
    raw: RawSequence, neighbours: list[RawSequence], rng: np.random.Generator
) -> RawSequence:
    n = len(raw.timestamp_ms)
    lo, hi = AUG["neighbour_fraction_range"]
    parts = []
    if rng.random() < 0.5:
        prev = neighbours[int(rng.integers(len(neighbours)))]
        k = max(1, min(len(prev.timestamp_ms), int(rng.uniform(lo, hi) * n)))
        parts.append(
            subset_raw(
                prev, np.arange(len(prev.timestamp_ms) - k, len(prev.timestamp_ms), dtype=np.int32)
            )
        )
    parts.append(raw)
    if rng.random() < 0.7 or len(parts) == 1:
        nxt = neighbours[int(rng.integers(len(neighbours)))]
        k = max(1, min(len(nxt.timestamp_ms), int(rng.uniform(lo, hi) * n)))
        parts.append(subset_raw(nxt, np.arange(0, k, dtype=np.int32)))
    return concat_raws(parts)


def build_pool(
    root: Path, rows: list[dict[str, Any]]
) -> tuple[list[np.ndarray], list[list[np.ndarray]]]:
    dense: list[np.ndarray] = []
    pool: list[list[np.ndarray]] = []
    raws = []
    for row in rows:
        raw = load_raw_sequence(Path(row["raw_path"]))
        if "span" in row:  # extra sources are cut to their span like the governed population
            raw = subset_raw(raw, np.arange(row["span"][0], row["span"][1] + 1, dtype=np.int32))
        raws.append(raw)
    by_signer: dict[str, list[int]] = {}
    for k, row in enumerate(rows):
        by_signer.setdefault(str(row.get("signer_id")), []).append(k)
    use_neighbours = float(AUG.get("neighbour_probability", 0.0)) > 0.0
    for k, row in enumerate(rows):
        raw = raws[k]
        view = temporal_view_v2(raw, condition="dense", phone_completed_fps=5.606840672873506)
        dense.append(view["features"][view["mask"]].astype(np.float32))
        rng = np.random.default_rng([AUG["pool_seed"], k])
        original = temporal_view_v2(
            raw, condition="phone_01_sparse", phone_completed_fps=5.606840672873506
        )
        variants = []
        for _ in range(AUG["pool_size"]):
            base = raw
            if use_neighbours and rng.random() < AUG["neighbour_probability"]:
                same = [i for i in by_signer[str(row.get("signer_id"))] if i != k]
                ids = same if same else [i for i in range(len(rows)) if i != k]
                base = with_neighbours(
                    raw,
                    [raws[i] for i in rng.choice(ids, size=min(4, len(ids)), replace=False)],
                    rng,
                )
            variants.append(augmented_view(base, rng).astype(np.float32))
        pool.append([original["features"][original["mask"]].astype(np.float32)] + variants)
        if k % 500 == 0:
            print(f"[aug] pool {k}/{len(rows)}", flush=True)
    return dense, pool


def pad(features: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    tensor = np.zeros((MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2), np.float32)
    mask = np.zeros(MAX_SEQUENCE_LENGTH, bool)
    tensor[: len(features)] = features
    mask[: len(features)] = True
    return tensor, mask


def semlex_rows(
    root: Path,
    theta_scale: float,
    role: str | None = None,
    source: Path = SEMLEX,
    cap_per_signer_class: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Sem-Lex candidates cut with the Candidate01 d1 port (theta fit on TRAIN, checked on DEV).

    ``role="ENRICH"`` keeps only the signers that word_vocabulary_eval reserves for training; the
    EVAL-role signers are then an untouched held-out set for every candidate.
    """
    from eval.runtime_diagnostics.word_vocabulary_eval import semlex_role
    from pipeline.detect.candidate01_span import candidate01_span
    from pipeline.detect.config import load_config

    cfg = load_config(ROOT / "pipeline/config/detect.yaml")
    manifest = json.loads((root / source / "manifest.json").read_text(encoding="utf-8"))
    clips_in = manifest["clips"]
    if cap_per_signer_class is not None:
        by_key: dict[tuple[str, int], list[dict[str, Any]]] = {}
        for clip in sorted(clips_in, key=lambda c: c["semlex_sample_id"]):
            by_key.setdefault((clip["signer"], int(clip["class_id"])), []).append(clip)
        rng = np.random.default_rng(7206)
        clips_in = []
        for key in sorted(by_key):
            group = by_key[key]
            keep = rng.choice(len(group), size=min(cap_per_signer_class, len(group)), replace=False)
            clips_in += [group[int(i)] for i in sorted(keep)]
    rows, invalid, skipped_role = [], 0, 0
    for clip in clips_in:
        if role is not None and semlex_role(clip["signer"]) != role:
            skipped_role += 1
            continue
        span = candidate01_span(load_raw_sequence(root / clip["raw_path"]), cfg, theta_scale)
        if not span.valid:
            invalid += 1
            continue
        rows.append(
            {
                "sample_id": f"semlex:{clip['semlex_sample_id']}",
                "class_id": clip["class_id"],
                "signer_id": clip["signer"],
                "raw_path": str(root / clip["raw_path"]),
                "span": [span.onset, span.release],
            }
        )
    audit = {
        "manifest_clips": len(manifest["clips"]),
        "invalid_span": invalid,
        "used": len(rows),
        "classes": len({r["class_id"] for r in rows}),
        "signers": len({r["signer_id"] for r in rows}),
        "theta_scale": theta_scale,
        "role": role,
        "skipped_other_role": skipped_role,
        "source": str(source).replace("\\", "/"),
        "cap_per_signer_class": cap_per_signer_class,
    }
    return rows, audit


def exposure_exact_order(
    labels: np.ndarray, base_count: dict[int, int], rng: np.random.Generator
) -> np.ndarray:
    """One epoch of (row, view) items with every class drawn exactly as often as in the baseline.

    Each class contributes its baseline clip count, drawn without replacement from all of its rows
    (governed TRAIN plus any extra source), each with one dense and one sparse view. The class prior
    and the number of optimizer steps are therefore identical to the baseline; only which clips
    represent a class changes (P5-D11 EC_P3 on the current V2 recognizer).
    """
    items = []
    for c, n in sorted(base_count.items()):
        pool = np.flatnonzero(labels == c)
        chosen = rng.choice(pool, size=n, replace=False)
        items.extend([2 * int(k) for k in chosen] + [2 * int(k) + 1 for k in chosen])
    return rng.permutation(np.asarray(items, np.int64))


def train(
    root: Path,
    output: Path,
    extra: str | None = None,
    seed_override: int | None = None,
    exposure: str = "natural",
    views: str = "dense_sparse",
) -> dict[str, Any]:
    import tensorflow as tf

    from model.perception_vnext import recognition_v2_236 as base

    config = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    seed = int(config["seed"]) if seed_override is None else int(seed_override)
    tf.keras.utils.set_random_seed(seed)
    raw_rows = {
        r["sample_id"]: r
        for r in (json.loads(line) for line in (root / RAW_INDEX).open(encoding="utf-8"))
    }
    v2_rows = [
        json.loads(line) for line in (root / V2_DATASET / "index.jsonl").open(encoding="utf-8")
    ]
    train_rows = [r for r in v2_rows if r["split"] == "train"]
    dev_rows = [r for r in v2_rows if r["split"] == "dev"]
    if (len(train_rows), len(dev_rows)) != (3926, 816):
        raise RuntimeError("AUG_POPULATION")
    if {r["signer_id"] for r in train_rows} & {r["signer_id"] for r in dev_rows}:
        raise RuntimeError("AUG_SIGNER_LEAKAGE")
    for r in train_rows:
        r["raw_path"] = raw_rows[r["sample_id"]]["raw_path"]
    base_count = {
        int(c): int(n)
        for c, n in zip(
            *np.unique([int(r["class_id"]) for r in train_rows], return_counts=True), strict=True
        )
    }
    base_steps_items = len(train_rows) * 2
    extra_audit = None
    if extra in ("semlex", "semlex_enrich", "semlex2_enrich"):
        added, extra_audit = semlex_rows(root, 0.4, "ENRICH" if extra != "semlex" else None)
        if extra == "semlex2_enrich":
            more, more_audit = semlex_rows(
                root, 0.4, "ENRICH", SEMLEX_02, SEMLEX_02_CAP_PER_SIGNER_CLASS
            )
            if {r["class_id"] for r in more} & {r["class_id"] for r in added}:
                raise RuntimeError("SEMLEX_02_OVERLAPS_SEMLEX_01_CLASSES")
            added += more
            extra_audit = {"semlex_01": extra_audit, "semlex_02": more_audit}
        if {r["signer_id"] for r in added} & {r["signer_id"] for r in dev_rows}:
            raise RuntimeError("AUG_EXTRA_SIGNER_LEAKAGE")
        train_rows = train_rows + added
        print(f"[aug] extra {extra_audit}", flush=True)
    if exposure not in ("natural", "exact"):
        raise ValueError(f"unknown exposure policy {exposure}")
    if views not in ("dense_sparse", "sparse_only"):
        raise ValueError(f"unknown training views {views}")
    output.mkdir(parents=True, exist_ok=False)
    write_json(
        output / "run_identity.json",
        {
            "schema": "apphear.word_track.robust_aug_run.v1",
            "baseline_run": str(root / RU / "tcn_v2_run_01"),
            "config_sha256": sha256(CONFIG),
            "augmentation": AUG,
            "extra_training_source": extra_audit,
            "class_exposure": exposure,
            "training_views": views,
            "selection_views": "sparse" if views == "sparse_only" else "dense+sparse",
            "seed": seed,
            "scientific_delta": "per-epoch sparse view drawn from a cadence/phase/hand-loss pool",
            "selection": "DEV val_loss on precomputed dense+PHONE_01 sparse views (as baseline)",
            "protected_test_accessed": False,
        },
    )
    dense, pool = build_pool(root, train_rows)
    labels = np.asarray([int(r["class_id"]) for r in train_rows], np.int32)
    state = {"epoch": 0}

    def generator() -> Any:
        rng = np.random.default_rng([seed, state["epoch"]])
        if exposure == "exact":
            order = exposure_exact_order(labels, base_count, rng)
        else:
            order = rng.permutation(len(train_rows) * 2)
        for item in order:
            k, kind = divmod(int(item), 2)
            if kind == 0 and views == "dense_sparse":
                features = dense[k]
            elif rng.random() < AUG["original_view_fraction"]:
                features = pool[k][0]
            else:
                features = pool[k][1 + int(rng.integers(len(pool[k]) - 1))]
            tensor, mask = pad(features)
            yield (tensor, mask), labels[k]

    batch = int(config["training"]["batch_size"])
    items = base_steps_items if exposure == "exact" else len(train_rows) * 2
    steps = math.ceil(items / batch)
    train_data = (
        tf.data.Dataset.from_generator(
            generator,
            output_signature=(
                (
                    tf.TensorSpec((MAX_SEQUENCE_LENGTH, FEATURE_WIDTH_V2), tf.float32),
                    tf.TensorSpec((MAX_SEQUENCE_LENGTH,), tf.bool),
                ),
                tf.TensorSpec((), tf.int32),
            ),
        )
        .batch(batch)
        .apply(tf.data.experimental.assert_cardinality(steps))
        .prefetch(2)
    )
    # sparse_only: the runtime never sees a dense 30 fps view, so neither training nor checkpoint
    # selection uses one; every item is a sparse pool view (same steps per epoch).
    val_views = ("sparse",) if views == "sparse_only" else ("dense", "sparse")
    dev_data = base._dataset(dev_rows, val_views, batch, seed, training=False)

    class Epoch(tf.keras.callbacks.Callback):
        def on_epoch_end(self, epoch: int, logs: dict[str, float] | None = None) -> None:
            state["epoch"] = epoch + 1

    model = _build_tcn(config)
    model.fit(
        train_data,
        validation_data=dev_data,
        epochs=int(config["training"]["epochs"]),
        verbose=2,
        callbacks=[
            Epoch(),
            tf.keras.callbacks.ModelCheckpoint(
                str(output / "best.keras"), monitor="val_loss", mode="min", save_best_only=True
            ),
            tf.keras.callbacks.CSVLogger(str(output / "history.csv")),
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss",
                mode="min",
                patience=int(config["training"]["early_stop_patience"]),
                restore_best_weights=True,
            ),
        ],
    )
    model.save(output / "final.keras")
    result = {
        "status": "PASS",
        "best_sha256": sha256(output / "best.keras"),
        "parameter_count": model.count_params(),
        "protected_test_accessed": False,
    }
    write_json(output / "training_result.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variant", choices=["v1", "v2", "v3"], default="v1")
    parser.add_argument(
        "--extra",
        choices=["semlex", "semlex_enrich", "semlex2_enrich"],
        default=None,
        help="semlex: every Sem-Lex signer; semlex_enrich: only the ENRICH-role signers",
    )
    parser.add_argument("--seed", type=int, default=None, help="override the config seed")
    parser.add_argument(
        "--exposure",
        choices=["natural", "exact"],
        default="natural",
        help="exact: per-class draws per epoch identical to the governed TRAIN (EC_P3)",
    )
    parser.add_argument(
        "--views",
        choices=["dense_sparse", "sparse_only"],
        default="dense_sparse",
        help="sparse_only: no dense view in training or checkpoint selection",
    )
    args = parser.parse_args()
    if args.variant == "v2":
        AUG.update(AUG_V2)
    elif args.variant == "v3":
        AUG.update(AUG_V3)
    result = train(
        args.evidence_root, args.output, args.extra, args.seed, args.exposure, args.views
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
