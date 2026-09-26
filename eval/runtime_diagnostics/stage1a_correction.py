"""Stage 1A-C correction and evidence validation.

This module reuses the immutable Stage-1A classifier-input latents. It never
opens the protected primary-test tensor and never trains or mutates a model.
All reference distributions are fitted from TRAIN only.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "artifacts/recognition_upgrade/p5_representation_v2"
OLD = BASE / "stage1a_rcab_root_cause_evidence_01"
OUT = BASE / "stage1a_correction_01"
DATA = BASE / "p5b_migration_01/dataset"
CHECKPOINT = BASE / "p5b_rcab_horizon_01/best.keras"
MANIFEST = ROOT / "artifacts/recognition_upgrade/phase1_full_vocab/manifest_01/canonical_manifest.csv"
VOCAB = DATA / "vocab.json"
SOURCES = {
    "train": DATA / "train.npz",
    "val": DATA / "val.npz",
    "stress": DATA / "diagnostic_validation_stress.npz",
}
LATENTS = {
    "train": OLD / "stage1a_train_latents.npz",
    "val": OLD / "stage1a_val_latents.npz",
    "stress": OLD / "stage1a_stress_latents.npz",
}
EXPECTED_CHECKPOINT_SHA = "3b858ca530b616c0d02ca2eee1d30678d092a039c36e9da38ec5f3d491a94a4c"
EXPECTED_COUNTS = {"train": 3926, "val": 816, "stress": 163}
NUM_CLASSES = 236
LATENT_LAYER = "tcn3_add"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    rows = list(rows)
    if fields is None:
        fields = list(rows[0]) if rows else []
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def euclid(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.sqrt(np.sum((a - b) ** 2, axis=-1))


def pair_distances(x: np.ndarray) -> np.ndarray:
    if len(x) < 2:
        return np.empty(0, np.float64)
    i, j = np.triu_indices(len(x), 1)
    return euclid(x[i], x[j])


def cross_distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if not len(a) or not len(b):
        return np.empty(0, np.float64)
    return np.sqrt(np.sum((a[:, None, :] - b[None, :, :]) ** 2, axis=2)).ravel()


def quant(values: np.ndarray, p: float) -> float | None:
    return float(np.quantile(values, p)) if len(values) else None


def percentile(values: np.ndarray, value: float) -> float | None:
    return float(100.0 * np.mean(values <= value)) if len(values) else None


def softmax(x: np.ndarray) -> np.ndarray:
    shifted = x - np.max(x, axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / np.sum(exp, axis=-1, keepdims=True)


def model_weights_hash(model: Any) -> str:
    h = hashlib.sha256()
    for value in model.weights:
        arr = np.asarray(value.numpy())
        h.update(value.name.encode())
        h.update(str(arr.dtype).encode())
        h.update(str(arr.shape).encode())
        h.update(arr.tobytes())
    return h.hexdigest()


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as z:
        return {key: np.asarray(z[key]) for key in z.files}


def verify_old_manifest() -> dict[str, str]:
    payload = json.loads((OLD / "artifact_hash_manifest.json").read_text(encoding="utf-8"))
    expected = {Path(row["path"]).name: row["sha256"] for row in payload["artifacts"]}
    hashes: dict[str, str] = {}
    for name, path in LATENTS.items():
        actual = sha256(path)
        if expected.get(path.name) != actual:
            raise RuntimeError(f"STAGE1A_CORRECTION_BLOCKED_LATENT_INTEGRITY:{name}")
        hashes[name] = actual
    return hashes


def signer_geometry(
    z: np.ndarray,
    labels: np.ndarray,
    signers: np.ndarray,
    vocab_by_id: dict[int, str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    signer_reps: dict[tuple[int, str], np.ndarray] = {}
    balanced_centroids: dict[int, np.ndarray] = {}
    cross_signer_reference: dict[int, np.ndarray] = {}
    train_margin_reference: dict[int, np.ndarray] = {}

    for c in range(NUM_CLASSES):
        idx = np.flatnonzero(labels == c)
        signer_indices = {
            signer: idx[np.asarray(signers[idx], str) == signer]
            for signer in sorted(set(map(str, signers[idx])))
        }
        for signer, si in signer_indices.items():
            signer_reps[(c, signer)] = np.median(z[si], axis=0)
        reps = np.stack([signer_reps[(c, s)] for s in signer_indices])
        balanced_centroids[c] = np.mean(reps, axis=0)

        same_parts = [pair_distances(z[si]) for si in signer_indices.values() if len(si) >= 2]
        same = np.concatenate(same_parts) if same_parts else np.empty(0)
        diff_parts = []
        signer_list = list(signer_indices)
        for i, a in enumerate(signer_list):
            for b in signer_list[i + 1 :]:
                diff_parts.append(cross_distances(z[signer_indices[a]], z[signer_indices[b]]))
        different = np.concatenate(diff_parts) if diff_parts else np.empty(0)
        same_signer_medians = np.asarray([
            np.median(pair_distances(z[si])) for si in signer_indices.values() if len(si) >= 2
        ], dtype=float)
        rep_different = pair_distances(reps)
        supported = bool(len(same) and len(different))
        sample_ratio = float(np.median(same) / max(np.median(different), 1e-12)) if supported else None
        balanced_ratio = (
            float(np.median(same_signer_medians) / max(np.median(rep_different), 1e-12))
            if len(same_signer_medians) and len(rep_different) else None
        )
        rows.append({
            "class_id": c,
            "gloss": vocab_by_id[c],
            "clips": len(idx),
            "unique_signers": len(signer_indices),
            "same_signer_pair_count": len(same),
            "different_signer_pair_count": len(different),
            "supports_same_vs_different_ratio": int(supported),
            "same_signer_distance_median": quant(same, .5),
            "different_signer_distance_median": quant(different, .5),
            "same_to_different_ratio": sample_ratio,
            "repeat_signers_contributing_to_balanced_same": len(same_signer_medians),
            "signer_balanced_same_distance_median": quant(same_signer_medians, .5),
            "signer_balanced_different_distance_median": quant(rep_different, .5),
            "signer_balanced_same_to_different_ratio": balanced_ratio,
        })

    sb = np.stack([balanced_centroids[c] for c in range(NUM_CLASSES)])
    # TRAIN-only leave-one-signer-out reference distances and margins.
    all_true_dist: dict[int, list[float]] = defaultdict(list)
    all_margin: dict[int, list[float]] = defaultdict(list)
    for i in range(len(z)):
        c = int(labels[i]); signer = str(signers[i])
        other_reps = [rep for (cc, ss), rep in signer_reps.items() if cc == c and ss != signer]
        own = np.mean(other_reps, axis=0) if other_reps else balanced_centroids[c]
        d_true = float(np.linalg.norm(z[i] - own))
        d_all = euclid(sb, z[i]); d_all[c] = np.inf
        d_wrong = float(np.min(d_all))
        all_true_dist[c].append(d_true)
        all_margin[c].append(d_wrong - d_true)
    cross_signer_reference = {c: np.asarray(all_true_dist[c], float) for c in range(NUM_CLASSES)}
    train_margin_reference = {c: np.asarray(all_margin[c], float) for c in range(NUM_CLASSES)}
    state = {
        "signer_reps": signer_reps,
        "balanced_centroids": sb,
        "cross_signer_reference": cross_signer_reference,
        "train_margin_reference": train_margin_reference,
    }
    return pd.DataFrame(rows), state


def class_geometry(
    signer_geometry_df: pd.DataFrame,
    state: dict[str, Any],
    vocab_by_id: dict[int, str],
) -> pd.DataFrame:
    sb = state["balanced_centroids"]
    rows = []
    for c in range(NUM_CLASSES):
        reps = np.stack([v for (cc, _), v in state["signer_reps"].items() if cc == c])
        dispersion = pair_distances(reps)
        distances = euclid(sb, sb[c]); distances[c] = np.inf
        nearest = int(np.argmin(distances))
        nearest_distance = float(distances[nearest])
        dispersion_median = quant(dispersion, .5)
        margins = state["train_margin_reference"][c]
        rows.append({
            "class_id": c, "gloss": vocab_by_id[c],
            "unique_signers": len(reps),
            "cross_signer_dispersion_pair_count": len(dispersion),
            "cross_signer_dispersion_p25": quant(dispersion, .25),
            "cross_signer_dispersion_p50": dispersion_median,
            "cross_signer_dispersion_p75": quant(dispersion, .75),
            "nearest_other_class_id": nearest,
            "nearest_other_class_gloss": vocab_by_id[nearest],
            "nearest_other_class_centroid_distance": nearest_distance,
            "within_to_nearest_between_ratio": float(dispersion_median / max(nearest_distance, 1e-12)) if dispersion_median is not None else None,
            "train_true_vs_nearest_wrong_margin_p25": quant(margins, .25),
            "train_true_vs_nearest_wrong_margin_p50": quant(margins, .5),
            "train_true_vs_nearest_wrong_margin_p75": quant(margins, .75),
        })
    return pd.DataFrame(rows)


def validation_geometry(
    val_z: np.ndarray,
    val: dict[str, np.ndarray],
    clip_probs: np.ndarray,
    state: dict[str, Any],
    vocab_by_id: dict[int, str],
    val_support: dict[int, int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sb = state["balanced_centroids"]
    rows, relationships = [], []
    predictions = clip_probs.argmax(1)
    for i in range(len(val_z)):
        true = int(val["y"][i]); pred = int(predictions[i])
        distances = euclid(sb, val_z[i])
        nearest = int(np.argmin(distances))
        wrong = distances.copy(); wrong[true] = np.inf
        nearest_wrong = int(np.argmin(wrong))
        d_true = float(distances[true]); d_pred = float(distances[pred]); d_wrong = float(distances[nearest_wrong])
        margin_nearest = d_wrong - d_true
        if pred == true and nearest == true:
            relationship = "RCAB_CORRECT_GEOMETRY_TRUE"
        elif pred == true:
            relationship = "RCAB_CORRECT_GEOMETRY_OTHER"
        elif nearest == true:
            relationship = "RCAB_WRONG_GEOMETRY_TRUE"
        elif nearest == pred:
            relationship = "RCAB_WRONG_GEOMETRY_SAME_AS_RCAB"
        else:
            relationship = "RCAB_WRONG_GEOMETRY_THIRD_CLASS"
        support = int(val_support.get(true, 0))
        support_tier = "HIGHER_SUPPORT_DESCRIPTIVE" if support >= 5 else "LOW_SUPPORT_EXPLORATORY"
        rows.append({
            "sample_id": str(val["sample_ids"][i]), "true_class_id": true,
            "true_gloss": vocab_by_id[true], "predicted_class_id": pred,
            "predicted_gloss": vocab_by_id[pred], "top1_correct": int(pred == true),
            "validation_class_support": support, "support_tier": support_tier,
            "d_true": d_true, "d_pred": d_pred, "d_nearest_wrong": d_wrong,
            "nearest_wrong_class_id": nearest_wrong, "nearest_wrong_gloss": vocab_by_id[nearest_wrong],
            "true_vs_pred_margin": d_pred - d_true,
            "true_vs_nearest_wrong_margin": margin_nearest,
            "d_true_train_cross_signer_percentile": percentile(state["cross_signer_reference"][true], d_true),
            "margin_train_reference_percentile": percentile(state["train_margin_reference"][true], margin_nearest),
            "nearest_signer_balanced_class_id": nearest,
            "nearest_signer_balanced_gloss": vocab_by_id[nearest],
            "true_probability": float(clip_probs[i, true]),
            "predicted_probability": float(clip_probs[i, pred]),
            "deprecated_old_overlap_flag": "DEPRECATED_OVERPERMISSIVE_DIAGNOSTIC",
        })
        relationships.append({
            "sample_id": str(val["sample_ids"][i]), "true_class_id": true,
            "true_gloss": vocab_by_id[true], "rcab_class_id": pred,
            "rcab_gloss": vocab_by_id[pred], "nearest_geometry_class_id": nearest,
            "nearest_geometry_gloss": vocab_by_id[nearest], "top1_correct": int(pred == true),
            "relationship": relationship, "validation_class_support": support,
            "support_tier": support_tier,
        })
    return pd.DataFrame(rows), pd.DataFrame(relationships)


def select_pairs(
    old_confusions: pd.DataFrame,
    old_per_class: pd.DataFrame,
    old_coverage: pd.DataFrame,
    class_geom: pd.DataFrame,
    vocab: dict[str, int],
) -> list[tuple[int, int, str]]:
    selected: dict[tuple[int, int], set[str]] = defaultdict(set)
    for row in old_confusions.head(20).itertuples(index=False):
        key = tuple(sorted((int(row.true_class_id), int(row.pred_class_id))))
        selected[key].add("TOP20_VALIDATION_CONFUSION")
    selected[tuple(sorted((vocab["KNOW"], vocab["HELLO"])))] .add("KNOWN_KNOW_HELLO")
    merged = old_coverage.merge(old_per_class, on="class_id").merge(
        class_geom[["class_id", "nearest_other_class_id", "within_to_nearest_between_ratio"]], on="class_id"
    )
    high_raw = merged[merged.raw_training_clips >= merged.raw_training_clips.quantile(.75)].sort_values(["recall", "raw_training_clips"], ascending=[True, False]).head(3)
    good_div = merged[merged.effective_signer_count >= merged.effective_signer_count.quantile(.75)].sort_values("recall").head(3)
    healthy = merged[(merged.support >= 5) & (merged.recall >= .8)].sort_values("within_to_nearest_between_ratio").head(3)
    for reason, frame in [
        ("HIGH_COVERAGE_POOR_PERFORMANCE", high_raw),
        ("GOOD_DIVERSITY_POOR_PERFORMANCE", good_div),
        ("HEALTHY_COMPARISON", healthy),
    ]:
        for row in frame.itertuples(index=False):
            key = tuple(sorted((int(row.class_id), int(row.nearest_other_class_id))))
            selected[key].add(reason)
    return [(a, b, "|".join(sorted(reasons))) for (a, b), reasons in sorted(selected.items())]


def pairwise_separation(
    pairs: list[tuple[int, int, str]],
    state: dict[str, Any],
    class_geom: pd.DataFrame,
    old_confusions: pd.DataFrame,
    val_support: dict[int, int],
    vocab_by_id: dict[int, str],
) -> pd.DataFrame:
    sb = state["balanced_centroids"]
    geom = class_geom.set_index("class_id")
    confusion_counts = {(int(r.true_class_id), int(r.pred_class_id)): int(r.confusion_count) for r in old_confusions.itertuples(index=False)}
    rows = []
    for a, b, reason in pairs:
        reps_a = [(s, v) for (c, s), v in state["signer_reps"].items() if c == a]
        reps_b = [(s, v) for (c, s), v in state["signer_reps"].items() if c == b]
        da = float(geom.loc[a, "cross_signer_dispersion_p50"])
        db = float(geom.loc[b, "cross_signer_dispersion_p50"])
        pooled = float(np.sqrt((da * da + db * db) / 2.0))
        centroid_distance = float(np.linalg.norm(sb[a] - sb[b]))

        def wrong_fraction(reps: list[tuple[str, np.ndarray]], own_class: int, other_class: int) -> tuple[int, int]:
            wrong = 0
            for signer, rep in reps:
                others = [v for (c, s), v in state["signer_reps"].items() if c == own_class and s != signer]
                own_centroid = np.mean(others, axis=0) if others else sb[own_class]
                if np.linalg.norm(rep - sb[other_class]) < np.linalg.norm(rep - own_centroid):
                    wrong += 1
            return wrong, len(reps)

        wrong_a, total_a = wrong_fraction(reps_a, a, b)
        wrong_b, total_b = wrong_fraction(reps_b, b, a)
        rows.append({
            "class_a_id": a, "class_a_gloss": vocab_by_id[a],
            "class_b_id": b, "class_b_gloss": vocab_by_id[b], "selection_reason": reason,
            "centroid_distance": centroid_distance,
            "class_a_cross_signer_dispersion": da,
            "class_b_cross_signer_dispersion": db,
            "pooled_dispersion_rms": pooled,
            "centroid_distance_to_pooled_dispersion_ratio": centroid_distance / max(pooled, 1e-12),
            "class_a_loso_closer_to_b_count": wrong_a,
            "class_a_signer_representatives": total_a,
            "class_a_loso_closer_to_b_fraction": wrong_a / max(total_a, 1),
            "class_b_loso_closer_to_a_count": wrong_b,
            "class_b_signer_representatives": total_b,
            "class_b_loso_closer_to_a_fraction": wrong_b / max(total_b, 1),
            "pairwise_nearest_centroid_confusion_rate": (wrong_a + wrong_b) / max(total_a + total_b, 1),
            "validation_a_to_b_count": confusion_counts.get((a, b), 0),
            "validation_b_to_a_count": confusion_counts.get((b, a), 0),
            "validation_support_a": val_support.get(a, 0),
            "validation_support_b": val_support.get(b, 0),
            "support_tier_a": "HIGHER_SUPPORT_DESCRIPTIVE" if val_support.get(a, 0) >= 5 else "LOW_SUPPORT_EXPLORATORY",
            "support_tier_b": "HIGHER_SUPPORT_DESCRIPTIVE" if val_support.get(b, 0) >= 5 else "LOW_SUPPORT_EXPLORATORY",
        })
    return pd.DataFrame(rows)


def temporal_row(
    split_name: str,
    i: int,
    split: dict[str, np.ndarray],
    logits: np.ndarray,
    probs: np.ndarray,
    competitor: int,
    vocab_by_id: dict[int, str],
    support: int,
) -> dict[str, Any]:
    true = int(split["y"][i]); clip_probs = probs[i].mean(0); pred = int(np.argmax(clip_probs))
    margin = logits[i][:, true] - logits[i][:, competitor]
    thirds = np.array_split(margin, 3)
    return {
        "split": split_name, "sample_id": str(split["sample_ids"][i]),
        "true_class_id": true, "true_gloss": vocab_by_id[true],
        "rcab_predicted_class_id": pred, "rcab_predicted_gloss": vocab_by_id[pred],
        "competing_class_id": competitor, "competing_gloss": vocab_by_id[competitor],
        "real_frames": len(margin), "validation_class_support": support if split_name == "PRIMARY_VAL" else None,
        "support_tier": ("HIGHER_SUPPORT_DESCRIPTIVE" if support >= 5 else "LOW_SUPPORT_EXPLORATORY") if split_name == "PRIMARY_VAL" else "DIAGNOSTIC_STRESS_ONLY",
        "fraction_true_logit_gt_competitor": float(np.mean(margin > 0)),
        "fraction_competitor_logit_gt_true": float(np.mean(margin < 0)),
        "true_minus_competitor_logit_p25": quant(margin, .25),
        "true_minus_competitor_logit_p50": quant(margin, .50),
        "true_minus_competitor_logit_p75": quant(margin, .75),
        "first_third_mean_margin": float(np.mean(thirds[0])),
        "middle_third_mean_margin": float(np.mean(thirds[1])),
        "final_third_mean_margin": float(np.mean(thirds[2])),
        "clip_true_probability": float(clip_probs[true]),
        "clip_competitor_probability": float(clip_probs[competitor]),
        "clip_predicted_probability": float(clip_probs[pred]),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=False)
    context_before = {str(p.relative_to(ROOT)): sha256(p) for p in sorted((ROOT / "context").rglob("*")) if p.is_file()}
    old_latent_hashes = verify_old_manifest()
    old_integrity = json.loads((OLD / "stage1a_integrity.json").read_text(encoding="utf-8"))
    old_contract = json.loads((OLD / "stage1a_latent_extraction_contract.json").read_text(encoding="utf-8"))
    if not old_integrity.get("passed") or old_contract.get("layer") != LATENT_LAYER or old_contract.get("inference_mode") != "training=False":
        raise RuntimeError("STAGE1A_CORRECTION_BLOCKED_LATENT_INTEGRITY:contract")

    source_before = {
        "checkpoint": sha256(CHECKPOINT), "manifest": sha256(MANIFEST), "vocabulary": sha256(VOCAB),
        **{name: sha256(path) for name, path in SOURCES.items()},
        **{f"latent_{name}": value for name, value in old_latent_hashes.items()},
    }
    if source_before["checkpoint"] != EXPECTED_CHECKPOINT_SHA:
        raise RuntimeError("STAGE1A_CORRECTION_BLOCKED_LATENT_INTEGRITY:checkpoint")

    latent = {name: load_npz(path) for name, path in LATENTS.items()}
    source = {name: load_npz(path) for name, path in SOURCES.items()}
    for name in ["train", "val", "stress"]:
        if latent[name]["latent_sequence"].shape != (EXPECTED_COUNTS[name], 96, 64):
            raise RuntimeError(f"STAGE1A_CORRECTION_BLOCKED_LATENT_INTEGRITY:{name}_shape")
        if not np.array_equal(latent[name]["sample_ids"], source[name]["sample_ids"]):
            raise RuntimeError(f"STAGE1A_CORRECTION_BLOCKED_LATENT_INTEGRITY:{name}_ids")
        if not np.array_equal(latent[name]["y"], source[name]["y"]):
            raise RuntimeError(f"STAGE1A_CORRECTION_BLOCKED_LATENT_INTEGRITY:{name}_labels")
        if not np.array_equal(latent[name]["frame_mask"], source[name]["frame_mask"]):
            raise RuntimeError(f"STAGE1A_CORRECTION_BLOCKED_LATENT_INTEGRITY:{name}_masks")
        if not np.isfinite(latent[name]["latent_sequence"]).all():
            raise RuntimeError(f"STAGE1A_CORRECTION_BLOCKED_LATENT_INTEGRITY:{name}_nonfinite")

    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    vocab_by_id = {int(v): str(k) for k, v in vocab.items()}
    manifest = pd.read_csv(MANIFEST, dtype=str, encoding="utf-8-sig").fillna("")
    manifest_lookup = manifest.set_index("sample_id").to_dict("index")

    import tensorflow as tf
    model = tf.keras.models.load_model(CHECKPOINT, safe_mode=False)
    if model.get_layer("logits_perframe").input.name.split("/")[0] != LATENT_LAYER:
        # Keras 3 tensor names can omit the producing layer; graph history is authoritative below.
        history = model.get_layer("logits_perframe").input._keras_history.operation.name
        if history != LATENT_LAYER:
            raise RuntimeError("STAGE1A_CORRECTION_BLOCKED_LATENT_INTEGRITY:classifier_layer")
    weights_before = model_weights_hash(model)
    latent_model = tf.keras.Model(model.input, model.get_layer(LATENT_LAYER).output)
    probe = np.array(latent_model(source["train"]["X"][:8], training=False), dtype=np.float32, copy=True)
    probe[~source["train"]["frame_mask"][:8].astype(bool)] = 0.0
    probe_delta = float(np.max(np.abs(probe - latent["train"]["latent_sequence"][:8])))
    if probe_delta > 1e-6:
        raise RuntimeError("STAGE1A_CORRECTION_BLOCKED_LATENT_INTEGRITY:latent_probe")
    final = model.get_layer("logits_perframe")
    if final.get_config().get("activation") != "softmax":
        raise RuntimeError("STAGE1A_CORRECTION_BLOCKED_LATENT_INTEGRITY:final_activation")
    kernel, bias = [np.asarray(x, np.float64) for x in final.get_weights()]

    scaler_mean = np.asarray(old_contract["standardization_mean"], np.float64)
    scaler_scale = np.asarray(old_contract["standardization_scale"], np.float64)
    z = {name: (latent[name]["clip_mean"].astype(np.float64) - scaler_mean) / scaler_scale for name in latent}
    train_y = latent["train"]["y"].astype(int)
    train_signers = latent["train"]["signer_group_ids"].astype(str)

    signer_df, state = signer_geometry(z["train"], train_y, train_signers, vocab_by_id)
    signer_df.to_csv(OUT / "stage1a_signer_geometry_corrected.csv", index=False)
    class_df = class_geometry(signer_df, state, vocab_by_id)
    class_df.to_csv(OUT / "stage1a_class_geometry_corrected.csv", index=False)

    # Frozen final projection reconstructed exactly from saved classifier-input latents.
    real_logits: dict[str, list[np.ndarray]] = {}
    real_probs: dict[str, list[np.ndarray]] = {}
    clip_probs: dict[str, np.ndarray] = {}
    for name in ["val", "stress"]:
        real_logits[name], real_probs[name] = [], []
        cp = np.zeros((EXPECTED_COUNTS[name], NUM_CLASSES), np.float64)
        for i in range(EXPECTED_COUNTS[name]):
            mask = latent[name]["frame_mask"][i].astype(bool)
            seq = latent[name]["latent_sequence"][i, mask].astype(np.float64)
            logits_i = seq @ kernel + bias
            probs_i = softmax(logits_i)
            real_logits[name].append(logits_i); real_probs[name].append(probs_i)
            cp[i] = probs_i.mean(0)
        clip_probs[name] = cp

    old_per_class = pd.read_csv(OLD / "stage1a_primary_val_per_class.csv")
    val_support = {int(r.class_id): int(r.support) for r in old_per_class.itertuples(index=False)}
    val_geom, classifier_geom = validation_geometry(z["val"], latent["val"], clip_probs["val"], state, vocab_by_id, val_support)
    val_geom.to_csv(OUT / "stage1a_validation_geometry_margins.csv", index=False)
    classifier_geom.to_csv(OUT / "stage1a_classifier_geometry_corrected.csv", index=False)

    old_confusions = pd.read_csv(OLD / "stage1a_ranked_confusion_pairs.csv")
    old_coverage = pd.read_csv(OLD / "stage1a_class_coverage_summary.csv")
    pairs = select_pairs(old_confusions, old_per_class, old_coverage, class_df, vocab)
    pair_df = pairwise_separation(pairs, state, class_df, old_confusions, val_support, vocab_by_id)
    pair_df.to_csv(OUT / "stage1a_pairwise_separation.csv", index=False)

    selected_classes = set(pair_df.class_a_id.astype(int)) | set(pair_df.class_b_id.astype(int))
    temporal_rows = []
    val_pred = clip_probs["val"].argmax(1)
    sb = state["balanced_centroids"]
    for i in range(EXPECTED_COUNTS["val"]):
        true = int(latent["val"]["y"][i]); pred = int(val_pred[i])
        if pred != true or true in selected_classes:
            if pred != true:
                competitor = pred
            else:
                d = euclid(sb, z["val"][i]); d[true] = np.inf; competitor = int(np.argmin(d))
            temporal_rows.append(temporal_row("PRIMARY_VAL", i, latent["val"], real_logits["val"], real_probs["val"], competitor, vocab_by_id, val_support.get(true, 0)))
    know, hello = int(vocab["KNOW"]), int(vocab["HELLO"])
    stress_know_indices = np.flatnonzero(latent["stress"]["y"].astype(int) == know)
    for i in stress_know_indices:
        temporal_rows.append(temporal_row("DIAGNOSTIC_STRESS", int(i), latent["stress"], real_logits["stress"], real_probs["stress"], hello, vocab_by_id, 0))
    temporal_df = pd.DataFrame(temporal_rows)
    temporal_df.to_csv(OUT / "stage1a_temporal_classifier_diagnostics.csv", index=False)
    temporal_val_errors = temporal_df[
        (temporal_df.split == "PRIMARY_VAL")
        & (temporal_df.rcab_predicted_class_id != temporal_df.true_class_id)
    ]
    segment_values = temporal_val_errors[
        ["first_third_mean_margin", "middle_third_mean_margin", "final_third_mean_margin"]
    ].to_numpy(float)
    temporal_error_summary = {
        "validation_errors_analyzed": len(temporal_val_errors),
        "predicted_beats_true_on_majority_of_real_frames": int((temporal_val_errors.fraction_competitor_logit_gt_true > .5).sum()),
        "true_beats_predicted_on_majority_of_real_frames": int((temporal_val_errors.fraction_true_logit_gt_competitor > .5).sum()),
        "all_three_temporal_segments_favor_predicted": int((segment_values < 0).all(axis=1).sum()),
        "mixed_temporal_segment_signs": int(((segment_values < 0).any(axis=1) & (segment_values > 0).any(axis=1)).sum()),
        "median_true_minus_predicted_logit_margin": float(temporal_val_errors.true_minus_competitor_logit_p50.median()),
    }

    know_reps = [(s, v) for (c, s), v in state["signer_reps"].items() if c == know]
    hello_reps = [(s, v) for (c, s), v in state["signer_reps"].items() if c == hello]
    know_rows = []
    for i in stress_know_indices:
        i = int(i); d_know = float(np.linalg.norm(z["stress"][i] - sb[know])); d_hello = float(np.linalg.norm(z["stress"][i] - sb[hello]))
        margin = real_logits["stress"][i][:, know] - real_logits["stress"][i][:, hello]
        thirds = np.array_split(margin, 3); cp = clip_probs["stress"][i]
        nearest_know = min(know_reps, key=lambda x: np.linalg.norm(z["stress"][i] - x[1]))
        nearest_hello = min(hello_reps, key=lambda x: np.linalg.norm(z["stress"][i] - x[1]))
        know_rows.append({
            "sample_id": str(latent["stress"]["sample_ids"][i]), "d_KNOW": d_know, "d_HELLO": d_hello,
            "HELLO_minus_KNOW_distance_margin": d_hello - d_know,
            "KNOW_distance_train_cross_signer_percentile": percentile(state["cross_signer_reference"][know], d_know),
            "nearest_KNOW_signer": nearest_know[0], "nearest_KNOW_signer_distance": float(np.linalg.norm(z["stress"][i] - nearest_know[1])),
            "nearest_HELLO_signer": nearest_hello[0], "nearest_HELLO_signer_distance": float(np.linalg.norm(z["stress"][i] - nearest_hello[1])),
            "rcab_clip_KNOW_probability": float(cp[know]), "rcab_clip_HELLO_probability": float(cp[hello]),
            "rcab_predicted_gloss": vocab_by_id[int(np.argmax(cp))],
            "fraction_KNOW_logit_gt_HELLO": float(np.mean(margin > 0)),
            "fraction_HELLO_logit_gt_KNOW": float(np.mean(margin < 0)),
            "KNOW_minus_HELLO_logit_p25": quant(margin, .25), "KNOW_minus_HELLO_logit_p50": quant(margin, .5), "KNOW_minus_HELLO_logit_p75": quant(margin, .75),
            "first_third_mean_margin": float(np.mean(thirds[0])), "middle_third_mean_margin": float(np.mean(thirds[1])), "final_third_mean_margin": float(np.mean(thirds[2])),
            "geometry_pairwise_favor": "KNOW" if d_know < d_hello else "HELLO",
            "temporal_pairwise_favor": "KNOW" if float(np.mean(margin)) > 0 else "HELLO",
        })
    know_df = pd.DataFrame(know_rows)
    know_df.to_csv(OUT / "stage1a_know_hello_temporal_diagnostic.csv", index=False)

    original_signer = pd.read_csv(OLD / "stage1a_train_embedding_signer_geometry.csv")
    original_summary = original_signer[original_signer.row_type == "CLASS_SUMMARY"]
    previous_ratio = float(original_summary.same_to_different_ratio.median())
    supported = signer_df[signer_df.supports_same_vs_different_ratio == 1]
    unsupported = signer_df[signer_df.supports_same_vs_different_ratio == 0]
    corrected_ratio = float(supported.same_to_different_ratio.median())
    corrected_balanced_ratio = float(supported.signer_balanced_same_to_different_ratio.dropna().median())
    unsupported_zero_count = int(((original_summary.same_pair_count.fillna(0) == 0) & (original_summary.same_to_different_ratio.fillna(0) == 0)).sum())
    bias = {
        "issue_confirmed": True,
        "previously_reported_all_class_median_ratio": previous_ratio,
        "corrected_supported_only_median_ratio": corrected_ratio,
        "corrected_supported_only_signer_balanced_median_ratio": corrected_balanced_ratio,
        "supported_classes": len(supported), "unsupported_classes": len(unsupported),
        "unsupported_zero_contributors_in_previous_aggregate": unsupported_zero_count,
        "absolute_bias_previous_minus_corrected": previous_ratio - corrected_ratio,
        "direction": "DOWNWARD" if previous_ratio < corrected_ratio else "UPWARD",
        "supported_ratio_percentiles": {f"p{p}": float(supported.same_to_different_ratio.quantile(p / 100)) for p in [25, 50, 75, 90]},
        "signer_balanced_supported_ratio_percentiles": {f"p{p}": float(supported.signer_balanced_same_to_different_ratio.quantile(p / 100)) for p in [25, 50, 75, 90]},
    }
    atomic_json(OUT / "stage1a_signer_geometry_bias_audit.json", bias)

    relations = classifier_geom.relationship.value_counts().to_dict()
    errors = classifier_geom[classifier_geom.top1_correct == 0]
    error_relations = errors.relationship.value_counts().to_dict()
    margin_median = float(val_geom.true_vs_nearest_wrong_margin.median())
    poor_sep = class_df[class_df.within_to_nearest_between_ratio >= 1.0]
    know_summary = {
        "clips": len(know_df),
        "geometrically_closer_KNOW": int((know_df.geometry_pairwise_favor == "KNOW").sum()),
        "geometrically_closer_HELLO": int((know_df.geometry_pairwise_favor == "HELLO").sum()),
        "temporally_favor_KNOW": int((know_df.temporal_pairwise_favor == "KNOW").sum()),
        "temporally_favor_HELLO": int((know_df.temporal_pairwise_favor == "HELLO").sum()),
        "geometry_temporal_disagreement": int((know_df.geometry_pairwise_favor != know_df.temporal_pairwise_favor).sum()),
        "rcab_predicted_HELLO": int((know_df.rcab_predicted_gloss == "HELLO").sum()),
    }
    summary = {
        "counts": EXPECTED_COUNTS, "vocabulary": NUM_CLASSES,
        "signer_geometry_bias_audit": bias,
        "old_overlap_flag": "DEPRECATED_OVERPERMISSIVE_DIAGNOSTIC",
        "validation_errors": len(errors),
        "classifier_geometry_all": {str(k): int(v) for k, v in relations.items()},
        "classifier_geometry_errors": {str(k): int(v) for k, v in error_relations.items()},
        "median_true_vs_nearest_wrong_margin_all_validation": margin_median,
        "classes_with_within_to_nearest_between_ratio_ge_1": len(poor_sep),
        "pairwise_pairs_analyzed": len(pair_df),
        "temporal_rows": len(temporal_df),
        "temporal_validation_error_summary": temporal_error_summary,
        "know_hello": know_summary,
        "validation_support": {"higher_support_rule": "support >= 5", "higher_support_classes": int((old_per_class.support >= 5).sum()), "low_support_classes": int((old_per_class.support < 5).sum())},
        "source_limitation": "Only five vocabulary classes have multi-source TRAIN coverage in Stage 1A; source geometry remains insufficient for vocabulary-wide conclusions.",
        "root_cause_selected": False, "fix_selected": False,
    }
    atomic_json(OUT / "stage1a_corrected_evidence_summary.json", summary)

    limitations = f"""# Stage 1A-C Corrected Evidence Limitations

- **{int((old_per_class.support < 5).sum())}/{NUM_CLASSES}** classes have fewer than five primary-validation clips and are marked `LOW_SUPPORT_EXPLORATORY`; only **{int((old_per_class.support >= 5).sum())}** are `HIGHER_SUPPORT_DESCRIPTIVE`.
- Same-vs-different signer ratios are supported for only **{len(supported)}/{NUM_CLASSES}** classes. Unsupported classes are NA and excluded from all aggregate percentiles.
- The former `TRUE_AND_WRONG_CLASS_OVERLAP` radius rule is deprecated as `DEPRECATED_OVERPERMISSIVE_DIAGNOSTIC`; it is not used in corrected evidence.
- Centroid and leave-one-signer-out diagnostics are non-trained simplifications of the nonlinear temporal classifier. Disagreement is not automatically a classifier failure.
- Pairwise class separation uses TRAIN signer representatives only. Small signer counts can still make individual pair results unstable.
- Only five classes have multi-source TRAIN evidence, so vocabulary-wide source conclusions remain unsupported.
- The KNOW/HELLO stress result covers one repeatedly inspected AppHear signer and is diagnostic only.
- No protected primary-test tensor was opened. No threshold was tuned against validation.
"""
    atomic_text(OUT / "stage1a_corrected_limitations.md", limitations)

    source_after = {
        "checkpoint": sha256(CHECKPOINT), "manifest": sha256(MANIFEST), "vocabulary": sha256(VOCAB),
        **{name: sha256(path) for name, path in SOURCES.items()},
        **{f"latent_{name}": sha256(path) for name, path in LATENTS.items()},
    }
    context_after = {str(p.relative_to(ROOT)): sha256(p) for p in sorted((ROOT / "context").rglob("*")) if p.is_file()}
    weights_after = model_weights_hash(model)
    integrity = {
        "passed": source_before == source_after and context_before == context_after and weights_before == weights_after,
        "existing_stage1a_latents_reused": True,
        "latent_integrity": "PASS",
        "latent_layer": LATENT_LAYER, "latent_inference_mode": "training=False",
        "latent_probe_max_abs_difference": probe_delta,
        "sample_counts": EXPECTED_COUNTS, "vocabulary_classes": NUM_CLASSES,
        "source_hashes_before": source_before, "source_hashes_after": source_after,
        "checkpoint_unchanged": source_before["checkpoint"] == source_after["checkpoint"],
        "latents_unchanged": all(source_before[f"latent_{n}"] == source_after[f"latent_{n}"] for n in LATENTS),
        "datasets_unchanged": all(source_before[n] == source_after[n] for n in SOURCES),
        "vocabulary_unchanged": source_before["vocabulary"] == source_after["vocabulary"],
        "manifest_unchanged": source_before["manifest"] == source_after["manifest"],
        "model_weights_changed": weights_before != weights_after,
        "training_performed": False, "protected_primary_test_opened": False,
        "context_files_modified": context_before != context_after,
        "progress_tracker_untouched": context_before.get("context/progress-tracker.md") == context_after.get("context/progress-tracker.md"),
    }
    atomic_json(OUT / "stage1a_correction_integrity.json", integrity)
    if not integrity["passed"]:
        raise RuntimeError("STAGE1A_CORRECTION_INTEGRITY_FAILURE")

    result = f"""# Stage 1A-C — Stage 1A Correction and Evidence Validation

## Scope

Read-only correction using the immutable Stage-1A TRAIN, primary-validation, and diagnostic-stress classifier-input latents. No extraction regeneration, training, protected-test access, root-cause selection, or intervention selection occurred.

## Latent integrity

- Frozen checkpoint SHA-256: `{source_before['checkpoint']}`.
- Layer: `{LATENT_LAYER}`; saved shape `[N,96,64]`; inference mode `training=False`.
- Eight-sample direct checkpoint probe maximum absolute difference: `{probe_delta:.3g}`.
- Existing Stage-1A latent hashes and source/sample/mask alignment passed.

## Corrected signer aggregation

- Previous all-class median ratio: `{previous_ratio:.6f}`.
- Corrected supported-only sample-weighted median: `{corrected_ratio:.6f}`.
- Corrected supported-only signer-balanced median: `{corrected_balanced_ratio:.6f}`.
- Supported classes: `{len(supported)}/{NUM_CLASSES}`; unsupported classes excluded as NA: `{len(unsupported)}`.
- Unsupported zero contributors in the old aggregate: `{unsupported_zero_count}`. The old result was biased `{bias['direction'].lower()}` by `{abs(bias['absolute_bias_previous_minus_corrected']):.6f}`.

## Corrected continuous geometry

- Validation errors: `{len(errors)}`.
- RCA-B wrong / nearest geometry true: `{error_relations.get('RCAB_WRONG_GEOMETRY_TRUE', 0)}`.
- RCA-B wrong / nearest geometry same as RCA-B: `{error_relations.get('RCAB_WRONG_GEOMETRY_SAME_AS_RCAB', 0)}`.
- RCA-B wrong / nearest geometry third class: `{error_relations.get('RCAB_WRONG_GEOMETRY_THIRD_CLASS', 0)}`.
- Median continuous true-vs-nearest-wrong distance margin across validation: `{margin_median:.6f}`.
- Classes with cross-signer-dispersion / nearest-centroid-distance ratio >=1: `{len(poor_sep)}/{NUM_CLASSES}`. This remains descriptive continuous evidence, not a binary overlap/root-cause claim.
- The former `TRUE_AND_WRONG_CLASS_OVERLAP` rule is `DEPRECATED_OVERPERMISSIVE_DIAGNOSTIC` and is not used.

## Pairwise and temporal evidence

- TRAIN-only leave-one-signer-out pair analysis covers `{len(pair_df)}` systematically selected failure and healthy-comparison pairs.
- Temporal diagnostics cover `{len(temporal_df)}` selected primary-validation/diagnostic-stress clips using actual per-frame frozen final-projection logits.
- Of `{temporal_error_summary['validation_errors_analyzed']}` validation errors, the predicted class beats the true class on a majority of real frames in `{temporal_error_summary['predicted_beats_true_on_majority_of_real_frames']}`; all three temporal thirds favor the predicted class in `{temporal_error_summary['all_three_temporal_segments_favor_predicted']}`, while `{temporal_error_summary['mixed_temporal_segment_signs']}` have mixed-sign temporal thirds.
- KNOW/HELLO stress: `{know_summary['geometrically_closer_KNOW']}` geometry-favor KNOW, `{know_summary['geometrically_closer_HELLO']}` geometry-favor HELLO; `{know_summary['temporally_favor_KNOW']}` temporally favor KNOW, `{know_summary['temporally_favor_HELLO']}` temporally favor HELLO; geometry/temporal disagreement `{know_summary['geometry_temporal_disagreement']}`. One signer only.

## Decision boundary

No root cause or fix is selected. Interpretation is deferred to Stage 1B after manual review.
"""
    atomic_text(OUT / "STAGE1A_CORRECTION_RESULT.md", result)

    artifacts = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "artifact_hash_manifest.json":
            artifacts.append({"path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size})
    atomic_json(OUT / "artifact_hash_manifest.json", {
        "artifacts": artifacts,
        "supporting_code": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        "training_performed": False, "protected_primary_test_opened": False,
    })
    print(json.dumps({"status": "APPHEAR_STAGE1A_CORRECTION_COMPLETE", "integrity": integrity, "summary": summary, "artifact_directory": str(OUT.resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
