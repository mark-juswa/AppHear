"""Stage 1A frozen RCA-B learned-space evidence build.

Read-only with respect to governed datasets, checkpoints, and context.  The
only writes are new Stage-1A diagnostic artifacts.  The protected primary
test split is deliberately not represented by a path in this module.
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
DATA = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5b_migration_01/dataset"
RUN = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5b_rcab_horizon_01"
CHECKPOINT = RUN / "best.keras"
MANIFEST = ROOT / "artifacts/recognition_upgrade/phase1_full_vocab/manifest_01/canonical_manifest.csv"
VOCAB = DATA / "vocab.json"
SPLITS = {
    "train": DATA / "train.npz",
    "val": DATA / "val.npz",
    "stress": DATA / "diagnostic_validation_stress.npz",
}
OUT = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/stage1a_rcab_root_cause_evidence_01"
EXPECTED_CHECKPOINT_SHA = "3b858ca530b616c0d02ca2eee1d30678d092a039c36e9da38ec5f3d491a94a4c"
EXPECTED_COUNTS = {"train": 3926, "val": 816, "stress": 163}
NUM_CLASSES = 236
LATENT_LAYER = "tcn3_add"
TEMPORAL_POINTS = 16


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_text(path: Path, text: str) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    rows = list(rows)
    if fields is None:
        fields = list(rows[0]) if rows else []
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


def load_split(name: str) -> dict[str, np.ndarray]:
    with np.load(SPLITS[name], allow_pickle=False) as z:
        result = {key: np.asarray(z[key]) for key in z.files}
    if result["X"].shape != (EXPECTED_COUNTS[name], 96, 238):
        raise RuntimeError(f"STAGE1A_{name.upper()}_SHAPE_MISMATCH:{result['X'].shape}")
    if result["frame_mask"].shape != (EXPECTED_COUNTS[name], 96):
        raise RuntimeError(f"STAGE1A_{name.upper()}_MASK_MISMATCH")
    if not np.isfinite(result["X"]).all():
        raise RuntimeError(f"STAGE1A_{name.upper()}_NONFINITE")
    return result


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


def q(values: np.ndarray, pct: float, default: float = 0.0) -> float:
    return float(np.quantile(values, pct)) if len(values) else default


def mean_or_none(values: np.ndarray) -> float | None:
    return float(np.mean(values)) if len(values) else None


def metrics(y: np.ndarray, pred: np.ndarray, probs: np.ndarray) -> tuple[dict[str, Any], list[dict[str, Any]], np.ndarray]:
    cm = np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=np.int64)
    np.add.at(cm, (y, pred), 1)
    support = cm.sum(1)
    predicted = cm.sum(0)
    tp = np.diag(cm)
    precision = np.divide(tp, predicted, out=np.zeros(NUM_CLASSES, float), where=predicted > 0)
    recall = np.divide(tp, support, out=np.zeros(NUM_CLASSES, float), where=support > 0)
    f1 = np.divide(2 * precision * recall, precision + recall, out=np.zeros(NUM_CLASSES, float), where=precision + recall > 0)
    active = support + predicted > 0
    top5_idx = np.argpartition(probs, -5, axis=1)[:, -5:]
    top5_hit = np.asarray([int(y[i] in top5_idx[i]) for i in range(len(y))])
    overall = {
        "top1": float(np.mean(pred == y)),
        "top5": float(np.mean(top5_hit)),
        "macro_f1": float(np.mean(f1[active])),
    }
    per_class = [{
        "class_id": c,
        "support": int(support[c]),
        "precision": float(precision[c]),
        "recall": float(recall[c]),
        "f1": float(f1[c]),
        "top5_containment": float(np.mean(top5_hit[y == c])) if support[c] else None,
    } for c in range(NUM_CLASSES)]
    return overall, per_class, cm


def resample_sequence(seq: np.ndarray, points: int = TEMPORAL_POINTS) -> np.ndarray:
    if len(seq) == 1:
        return np.repeat(seq, points, axis=0)
    old = np.linspace(0.0, 1.0, len(seq))
    new = np.linspace(0.0, 1.0, points)
    out = np.empty((points, seq.shape[1]), np.float64)
    for d in range(seq.shape[1]):
        out[:, d] = np.interp(new, old, seq[:, d])
    return out


def extract(model: Any, latent_model: Any, split: dict[str, np.ndarray], batch: int = 32) -> tuple[np.ndarray, np.ndarray, float]:
    x = split["X"]
    mask = split["frame_mask"].astype(bool)
    latents = np.zeros((len(x), 96, 64), np.float32)
    clip_probs = np.zeros((len(x), NUM_CLASSES), np.float32)
    pf_correct = 0
    pf_total = 0
    for start in range(0, len(x), batch):
        stop = min(start + batch, len(x))
        xb = x[start:stop]
        # TensorFlow may expose an inference buffer as a read-only NumPy view.
        # Stage 1A masks padded latent rows in its private extraction array, so
        # take an explicit writable copy without mutating model output/state.
        lb = np.array(latent_model(xb, training=False), dtype=np.float32, copy=True)
        pb = np.asarray(model(xb, training=False), np.float32)
        mb = mask[start:stop]
        lb[~mb] = 0.0
        latents[start:stop] = lb
        denom = np.maximum(mb.sum(1, keepdims=True), 1)
        clip_probs[start:stop] = (pb * mb[:, :, None]).sum(1) / denom
        yb = split["y"][start:stop]
        pf_correct += int(np.sum((pb.argmax(2) == yb[:, None]) & mb))
        pf_total += int(mb.sum())
    return latents, clip_probs, float(pf_correct / pf_total)


def latent_means(latents: np.ndarray, mask: np.ndarray) -> np.ndarray:
    denom = np.maximum(mask.sum(1, keepdims=True), 1)
    return (latents * mask[:, :, None]).sum(1) / denom


def model_weights_hash(model: Any) -> str:
    h = hashlib.sha256()
    for value in model.weights:
        arr = np.asarray(value.numpy())
        h.update(value.name.encode())
        h.update(str(arr.dtype).encode())
        h.update(str(arr.shape).encode())
        h.update(arr.tobytes())
    return h.hexdigest()


def manifest_lookup() -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    frame = pd.read_csv(MANIFEST, dtype=str, encoding="utf-8-sig").fillna("")
    return frame, {str(row.sample_id): row._asdict() for row in frame.itertuples(index=False)}


def class_coverage(train_ids: np.ndarray, vocab_by_id: dict[int, str], lookup: dict[str, dict[str, str]]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    records = []
    for sid in map(str, train_ids):
        row = lookup[sid]
        records.append({"sample_id": sid, "class_id": int(row["class_id"]), "gloss": row["canonical_gloss"], "signer": row["signer_group_id"], "source": row["source_dataset"], "role": row["role"]})
    df = pd.DataFrame(records)
    coverage_rows: list[dict[str, Any]] = []
    signer_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    matrix_rows: list[dict[str, Any]] = []
    for c in range(NUM_CLASSES):
        part = df[df.class_id == c]
        sc = part.signer.value_counts()
        so = part.source.value_counts()
        n = len(part)
        sp = (sc / n).to_numpy(float)
        op = (so / n).to_numpy(float)
        signer_hhi = float(np.sum(sp ** 2))
        source_hhi = float(np.sum(op ** 2))
        coverage_rows.append({
            "class_id": c, "gloss": vocab_by_id[c], "raw_training_clips": n,
            "unique_signer_groups": len(sc), "unique_sources": len(so),
            "largest_signer_count": int(sc.iloc[0]), "largest_signer_share": float(sp[0]),
            "top2_signer_share": float(sp[:2].sum()), "top3_signer_share": float(sp[:3].sum()),
            "largest_source_share": float(op[0]), "signer_hhi": signer_hhi,
            "effective_signer_count": float(1.0 / signer_hhi), "source_hhi": source_hhi,
            "effective_source_count": float(1.0 / source_hhi),
            "clips_per_signer_json": json.dumps({str(k): int(v) for k, v in sc.items()}, sort_keys=True),
            "clips_per_source_json": json.dumps({str(k): int(v) for k, v in so.items()}, sort_keys=True),
        })
        for rank, (signer, count) in enumerate(sc.items(), 1):
            signer_rows.append({"class_id": c, "gloss": vocab_by_id[c], "signer_group_id": signer, "clips": int(count), "share": float(count / n), "rank": rank})
        for rank, (source, count) in enumerate(so.items(), 1):
            source_rows.append({"class_id": c, "gloss": vocab_by_id[c], "source": source, "clips": int(count), "share": float(count / n), "rank": rank})
        grouped = part.groupby(["signer", "source"]).size()
        for (signer, source), count in grouped.items():
            matrix_rows.append({"class_id": c, "gloss": vocab_by_id[c], "signer_group_id": signer, "source": source, "clips": int(count)})
    return pd.DataFrame(coverage_rows), pd.DataFrame(signer_rows), pd.DataFrame(source_rows), pd.DataFrame(matrix_rows)


def geometry(train_z: np.ndarray, labels: np.ndarray, signers: np.ndarray, sources: np.ndarray, vocab_by_id: dict[int, str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    sample_centroids: dict[int, np.ndarray] = {}
    balanced_centroids: dict[int, np.ndarray] = {}
    signer_centroids: dict[tuple[int, str], np.ndarray] = {}
    class_radii: dict[int, np.ndarray] = {}
    signer_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    for c in range(NUM_CLASSES):
        idx = np.flatnonzero(labels == c)
        sample_centroids[c] = np.mean(train_z[idx], axis=0)
        signer_reps = []
        for signer in sorted(set(map(str, signers[idx]))):
            si = idx[np.asarray(signers[idx], str) == signer]
            rep = np.median(train_z[si], axis=0)
            signer_centroids[(c, signer)] = rep
            signer_reps.append(rep)
            signer_rows.append({"row_type": "CLASS_SIGNER", "class_id": c, "gloss": vocab_by_id[c], "signer_group_id": signer, "clips": len(si), "distance_to_class_balanced_centroid": None, "within_signer_dispersion": q(euclid(train_z[si], rep), .5), "same_signer_pair_median": q(pair_distances(train_z[si]), .5), "different_signer_pair_median": None, "same_to_different_ratio": None})
        balanced_centroids[c] = np.mean(signer_reps, axis=0)
        class_radii[c] = euclid(train_z[idx], balanced_centroids[c])
        same_parts, diff_parts = [], []
        for i in range(len(idx)):
            for j in range(i + 1, len(idx)):
                d = float(np.linalg.norm(train_z[idx[i]] - train_z[idx[j]]))
                (same_parts if str(signers[idx[i]]) == str(signers[idx[j]]) else diff_parts).append(d)
        same_arr, diff_arr = np.asarray(same_parts), np.asarray(diff_parts)
        signer_rows.append({"row_type": "CLASS_SUMMARY", "class_id": c, "gloss": vocab_by_id[c], "signer_group_id": "", "clips": len(idx), "distance_to_class_balanced_centroid": None, "within_signer_dispersion": None, "same_signer_pair_median": q(same_arr, .5), "different_signer_pair_median": q(diff_arr, .5), "same_to_different_ratio": q(same_arr, .5) / max(q(diff_arr, .5), 1e-12), "same_pair_count": len(same_arr), "different_pair_count": len(diff_arr)})
        for signer in sorted(set(map(str, signers[idx]))):
            for row in reversed(signer_rows):
                if row["row_type"] == "CLASS_SIGNER" and row["class_id"] == c and row["signer_group_id"] == signer:
                    row["distance_to_class_balanced_centroid"] = float(np.linalg.norm(signer_centroids[(c, signer)] - balanced_centroids[c])); break
        unique_sources = sorted(set(map(str, sources[idx])))
        within_source, cross_source = [], []
        source_balanced_centroids: list[np.ndarray] = []
        for i in range(len(idx)):
            for j in range(i + 1, len(idx)):
                d = float(np.linalg.norm(train_z[idx[i]] - train_z[idx[j]]))
                (within_source if str(sources[idx[i]]) == str(sources[idx[j]]) else cross_source).append(d)
        for source in unique_sources:
            si = idx[np.asarray(sources[idx], str) == source]
            rep = np.median(train_z[si], axis=0)
            source_signer_reps = []
            for signer in sorted(set(map(str, signers[si]))):
                ssi = si[np.asarray(signers[si], str) == signer]
                source_signer_reps.append(np.median(train_z[ssi], axis=0))
            source_balanced = np.mean(source_signer_reps, axis=0)
            source_balanced_centroids.append(source_balanced)
            source_rows.append({
                "row_type": "CLASS_SOURCE", "class_id": c, "gloss": vocab_by_id[c],
                "source": source, "clips": len(si), "unique_signers": len(source_signer_reps),
                "within_source_dispersion": q(euclid(train_z[si], rep), .5),
                "within_source_pair_median": q(pair_distances(train_z[si]), .5),
                "distance_to_signer_balanced_class_centroid": float(np.linalg.norm(source_balanced - balanced_centroids[c])),
                "cross_source_pair_median": None, "within_to_cross_ratio": None,
                "signer_balanced_source_centroid_distance_median": None,
            })
        balanced_source_distances = pair_distances(np.stack(source_balanced_centroids)) if len(source_balanced_centroids) > 1 else np.empty(0)
        source_rows.append({
            "row_type": "CLASS_SUMMARY", "class_id": c, "gloss": vocab_by_id[c],
            "source": "", "clips": len(idx), "unique_signers": len(set(map(str, signers[idx]))),
            "within_source_dispersion": None,
            "within_source_pair_median": q(np.asarray(within_source), .5),
            "cross_source_pair_median": q(np.asarray(cross_source), .5),
            "within_to_cross_ratio": q(np.asarray(within_source), .5) / max(q(np.asarray(cross_source), .5), 1e-12) if cross_source else None,
            "distance_to_signer_balanced_class_centroid": None,
            "signer_balanced_source_centroid_distance_median": q(balanced_source_distances, .5) if len(balanced_source_distances) else None,
            "within_pair_count": len(within_source), "cross_pair_count": len(cross_source),
        })
    sb = np.stack([balanced_centroids[c] for c in range(NUM_CLASSES)])
    sw = np.stack([sample_centroids[c] for c in range(NUM_CLASSES)])
    class_rows = []
    for c in range(NUM_CLASSES):
        distances = euclid(sb, sb[c]); distances[c] = np.inf
        nearest = int(np.argmin(distances))
        signer_pair = pair_distances(np.stack([v for (cc, _), v in signer_centroids.items() if cc == c]))
        class_rows.append({
            "class_id": c, "gloss": vocab_by_id[c], "clips": int(np.sum(labels == c)),
            "within_class_sample_dispersion_median": q(class_radii[c], .5),
            "within_class_sample_dispersion_p75": q(class_radii[c], .75),
            "within_class_sample_dispersion_p95": q(class_radii[c], .95),
            "cross_signer_dispersion_median": q(signer_pair, .5),
            "nearest_other_class_id": nearest, "nearest_other_class_gloss": vocab_by_id[nearest],
            "nearest_other_class_centroid_distance": float(distances[nearest]),
            "within_to_nearest_between_ratio": q(class_radii[c], .5) / max(float(distances[nearest]), 1e-12),
        })
    state = {"sample_centroids": sw, "balanced_centroids": sb, "signer_centroids": signer_centroids, "class_radii": class_radii}
    return pd.DataFrame(class_rows), pd.DataFrame(signer_rows), pd.DataFrame(source_rows), state


def confusion_rows(cm: np.ndarray, vocab_by_id: dict[int, str]) -> list[dict[str, Any]]:
    support = cm.sum(1)
    rows = []
    for true in range(NUM_CLASSES):
        for pred in range(NUM_CLASSES):
            if true == pred or cm[true, pred] == 0:
                continue
            rows.append({
                "true_class_id": true, "true_gloss": vocab_by_id[true], "pred_class_id": pred,
                "pred_gloss": vocab_by_id[pred], "confusion_count": int(cm[true, pred]),
                "fraction_of_true_class": float(cm[true, pred] / max(support[true], 1)),
                "true_support": int(support[true]), "reciprocal_count": int(cm[pred, true]),
                "reciprocal_fraction": float(cm[pred, true] / max(support[pred], 1)),
            })
    rows.sort(key=lambda r: (r["confusion_count"], r["fraction_of_true_class"], r["reciprocal_count"]), reverse=True)
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
        row["top20_adequate_support"] = int(rank <= 20 and row["true_support"] >= 3)
    return rows


def validation_diagnostics(split: dict[str, np.ndarray], probs: np.ndarray, z: np.ndarray, sources: np.ndarray, state: dict[str, Any], coverage: pd.DataFrame, vocab_by_id: dict[int, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    y = split["y"].astype(int)
    pred = probs.argmax(1)
    sb, sw = state["balanced_centroids"], state["sample_centroids"]
    coverage_by = coverage.set_index("class_id")
    eff_p25 = float(coverage.effective_signer_count.quantile(.25))
    train_sources_by_class = defaultdict(set)
    manifest, lookup = manifest_lookup()
    for sid in map(str, load_split("train")["sample_ids"]):
        row = lookup[sid]; train_sources_by_class[int(row["class_id"])].add(row["source_dataset"])
    rows, compare = [], []
    for i in range(len(y)):
        true, chosen = int(y[i]), int(pred[i])
        dist_sb = euclid(sb, z[i])
        dist_sw = euclid(sw, z[i])
        nearest_sb = int(np.argmin(dist_sb)); nearest_sw = int(np.argmin(dist_sw))
        wrong_order = np.argsort(dist_sb)
        nearest_wrong = int(next(c for c in wrong_order if c != true))
        signer_items = [(signer, centroid) for (c, signer), centroid in state["signer_centroids"].items() if c == true]
        true_signer_dists = [(s, float(np.linalg.norm(z[i] - c))) for s, c in signer_items]
        all_wrong_signers = [(c, s, float(np.linalg.norm(z[i] - cent))) for (c, s), cent in state["signer_centroids"].items() if c != true]
        nearest_true_signer, nearest_true_signer_dist = min(true_signer_dists, key=lambda x: x[1])
        wrong_c, wrong_s, nearest_wrong_signer_dist = min(all_wrong_signers, key=lambda x: x[2])
        radius = state["class_radii"][true]
        pct = float(100.0 * np.mean(radius <= dist_sb[true]))
        p75, p95 = q(radius, .75), q(radius, .95)
        wrong_radius = state["class_radii"][chosen]
        centroid_overlap = float(np.linalg.norm(sb[true] - sb[chosen])) <= p75 + q(wrong_radius, .75)
        flags = []
        if chosen != true:
            if dist_sb[true] > p95: flags.append("OUTSIDE_TRUE_CLASS_TRAIN_DISTRIBUTION")
            if dist_sb[true] <= p75 and nearest_sb == true: flags.append("NEAR_TRUE_CLASS_BUT_CLASSIFIER_WRONG")
            if dist_sb[chosen] <= dist_sb[true] or centroid_overlap: flags.append("TRUE_AND_WRONG_CLASS_OVERLAP")
            if float(coverage_by.loc[true, "effective_signer_count"]) <= eff_p25 or sources[i] not in train_sources_by_class[true]: flags.append("SOURCE_OR_SIGNER_STRUCTURE_SUSPECTED")
            if not flags: flags.append("AMBIGUOUS_GEOMETRY")
        order = np.sort(probs[i])
        rows.append({
            "sample_id": str(split["sample_ids"][i]), "signer_group_id": str(split["signer_group_ids"][i]), "source": sources[i],
            "true_class_id": true, "true_gloss": vocab_by_id[true], "pred_class_id": chosen, "pred_gloss": vocab_by_id[chosen],
            "top1_correct": int(true == chosen), "true_probability": float(probs[i, true]), "predicted_probability": float(probs[i, chosen]),
            "classifier_margin": float(order[-1] - order[-2]), "distance_true_sample_weighted_centroid": float(dist_sw[true]),
            "distance_true_signer_balanced_centroid": float(dist_sb[true]), "distance_predicted_signer_balanced_centroid": float(dist_sb[chosen]),
            "nearest_wrong_class_id": nearest_wrong, "nearest_wrong_gloss": vocab_by_id[nearest_wrong], "nearest_wrong_centroid_distance": float(dist_sb[nearest_wrong]),
            "nearest_true_signer": nearest_true_signer, "nearest_true_signer_distance": nearest_true_signer_dist,
            "nearest_wrong_signer_class_id": wrong_c, "nearest_wrong_signer": wrong_s, "nearest_wrong_signer_distance": nearest_wrong_signer_dist,
            "true_class_train_distance_percentile": pct, "descriptive_geometry_flags": "|".join(flags),
        })
        if true == chosen and nearest_sb == true: relation = "BOTH_CORRECT"
        elif chosen != true and nearest_sb == true: relation = "RCAB_WRONG_CENTROID_TRUE"
        elif chosen != true and nearest_sb == chosen: relation = "RCAB_WRONG_CENTROID_SAME_WRONG"
        elif chosen == true and nearest_sb != true: relation = "RCAB_CORRECT_CENTROID_WRONG"
        else: relation = "OTHER_DISAGREEMENT"
        compare.append({"sample_id": str(split["sample_ids"][i]), "true_class_id": true, "rcab_class_id": chosen, "signer_balanced_centroid_class_id": nearest_sb, "sample_weighted_centroid_class_id": nearest_sw, "relationship": relation})
    return pd.DataFrame(rows), pd.DataFrame(compare)


def rank_average(values: pd.Series) -> np.ndarray:
    return values.rank(method="average").to_numpy(float)


def associations(coverage: pd.DataFrame, per_class: pd.DataFrame, class_geom: pd.DataFrame) -> pd.DataFrame:
    merged = coverage.merge(per_class, on="class_id").merge(class_geom, on="class_id", suffixes=("", "_geometry"))
    predictors = ["raw_training_clips", "unique_signer_groups", "effective_signer_count", "largest_signer_share", "top3_signer_share", "source_hhi", "cross_signer_dispersion_median", "nearest_other_class_centroid_distance", "within_to_nearest_between_ratio"]
    rows = []
    valid = merged.support > 0
    for target in ["recall", "f1"]:
        for predictor in predictors:
            pair = merged.loc[valid, [predictor, target]].dropna()
            rho = float(np.corrcoef(rank_average(pair[predictor]), rank_average(pair[target]))[0, 1]) if len(pair) > 2 else None
            rows.append({"analysis": "SPEARMAN", "target": target, "predictor": predictor, "n_classes": len(pair), "value": rho, "group": ""})
    quartiles = pd.qcut(merged.effective_signer_count.rank(method="first"), 4, labels=["Q1", "Q2", "Q3", "Q4"])
    for group in ["Q1", "Q2", "Q3", "Q4"]:
        part = merged[quartiles == group]
        rows.append({"analysis": "EFFECTIVE_SIGNER_QUARTILE", "target": "recall", "predictor": "effective_signer_count", "n_classes": len(part), "value": float(part.recall.mean()), "group": group})
    return pd.DataFrame(rows)


def select_case_studies(coverage: pd.DataFrame, per_class: pd.DataFrame, class_geom: pd.DataFrame, confusion: list[dict[str, Any]], compare: pd.DataFrame, source_geom: pd.DataFrame, vocab_by_id: dict[int, str]) -> pd.DataFrame:
    merged = coverage.merge(per_class, on="class_id").merge(class_geom, on="class_id", suffixes=("", "_g"))
    cases: list[dict[str, Any]] = [{"selection_reason": "KNOWN_STRESS_CASE", "class_or_pair": "KNOW->HELLO", "evidence": "30 repeatedly inspected AppHear stress KNOW clips; learned-space analysis included separately"}]
    if confusion:
        top = confusion[0]; cases.append({"selection_reason": "HIGHEST_PRIMARY_VAL_CONFUSION", "class_or_pair": f"{top['true_gloss']}->{top['pred_gloss']}", "evidence": f"count={top['confusion_count']}; fraction={top['fraction_of_true_class']:.4f}"})
    candidates = [
        ("HIGH_RAW_COUNT_POOR_RECALL", merged[(merged.raw_training_clips >= merged.raw_training_clips.quantile(.75))].sort_values(["recall", "raw_training_clips"], ascending=[True, False]).head(1)),
        ("LOW_EFFECTIVE_SIGNERS_POOR_RECALL", merged[(merged.effective_signer_count <= merged.effective_signer_count.quantile(.25))].sort_values("recall").head(1)),
        ("GOOD_SIGNER_DIVERSITY_POOR_RECALL", merged[(merged.effective_signer_count >= merged.effective_signer_count.quantile(.75))].sort_values("recall").head(1)),
        ("GOOD_RECALL_LOW_RAW_COUNT", merged[(merged.raw_training_clips <= merged.raw_training_clips.quantile(.25))].sort_values("recall", ascending=False).head(1)),
        ("TRAIN_MANIFOLD_OVERLAP", merged.sort_values("within_to_nearest_between_ratio", ascending=False).head(1)),
    ]
    disagreement = compare[compare.relationship == "RCAB_WRONG_CENTROID_TRUE"].groupby("true_class_id").size().sort_values(ascending=False)
    if len(disagreement):
        c = int(disagreement.index[0]); cases.append({"selection_reason": "CLASSIFIER_CENTROID_DISAGREEMENT", "class_or_pair": vocab_by_id[c], "evidence": f"{int(disagreement.iloc[0])} validation samples: RCA-B wrong, signer-balanced centroid true"})
    sg = source_geom[(source_geom.row_type == "CLASS_SUMMARY") & source_geom.cross_source_pair_median.notna()].copy()
    if len(sg):
        sg["cross_to_within"] = sg.cross_source_pair_median / sg.within_source_pair_median.replace(0, np.nan)
        row = sg.sort_values("cross_to_within", ascending=False).iloc[0]
        cases.append({"selection_reason": "SOURCE_STRUCTURE_HIGH", "class_or_pair": row.gloss, "evidence": f"cross/within source distance={row.cross_to_within:.4f}"})
    for reason, frame in candidates:
        if len(frame):
            row = frame.iloc[0]
            cases.append({"selection_reason": reason, "class_or_pair": row.gloss, "evidence": f"clips={int(row.raw_training_clips)}; effective_signers={row.effective_signer_count:.3f}; val_recall={row.recall:.3f}; separation_ratio={row.within_to_nearest_between_ratio:.3f}"})
    unique, seen = [], set()
    for item in cases:
        key = (item["selection_reason"], item["class_or_pair"])
        if key not in seen:
            seen.add(key); unique.append(item)
    return pd.DataFrame(unique[:12])


def temporal_cases(case_studies: pd.DataFrame, train_lat: np.ndarray, train: dict[str, np.ndarray], val_lat: np.ndarray, val: dict[str, np.ndarray], stress_lat: np.ndarray, stress: dict[str, np.ndarray], scaler_mean: np.ndarray, scaler_scale: np.ndarray, vocab: dict[str, int]) -> pd.DataFrame:
    names: set[str] = {"KNOW", "HELLO"}
    for text in case_studies.class_or_pair:
        names.update(str(text).split("->"))
    names = {n for n in names if n in vocab}
    template: dict[int, np.ndarray] = {}
    for name in names:
        c = vocab[name]
        seqs = []
        for i in np.flatnonzero(train["y"] == c):
            real = train_lat[i][train["frame_mask"][i]]
            seqs.append(resample_sequence((real - scaler_mean) / scaler_scale))
        template[c] = np.median(np.stack(seqs), axis=0)
    rows = []
    for split_name, lat, split in [("PRIMARY_VAL", val_lat, val), ("DIAGNOSTIC_STRESS", stress_lat, stress)]:
        for i in range(len(lat)):
            true = int(split["y"][i])
            if true not in template:
                continue
            real = (lat[i][split["frame_mask"][i]] - scaler_mean) / scaler_scale
            seq = resample_sequence(real)
            dists = {c: float(np.mean(euclid(seq, templ))) for c, templ in template.items()}
            nearest = min(dists, key=dists.get)
            third = TEMPORAL_POINTS // 3
            rows.append({
                "split": split_name, "sample_id": str(split["sample_ids"][i]), "true_class_id": true,
                "true_gloss": next(k for k, v in vocab.items() if v == true), "nearest_case_class_id": nearest,
                "nearest_case_gloss": next(k for k, v in vocab.items() if v == nearest),
                "aligned_temporal_distance_true": dists[true],
                "first_segment_distance_true": float(np.mean(euclid(seq[:third], template[true][:third]))),
                "middle_segment_distance_true": float(np.mean(euclid(seq[third:2*third], template[true][third:2*third]))),
                "last_segment_distance_true": float(np.mean(euclid(seq[2*third:], template[true][2*third:]))),
                "real_frames": int(split["frame_mask"][i].sum()),
            })
    return pd.DataFrame(rows)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=False)
    context_files = sorted((ROOT / "context").rglob("*"))
    context_before = {str(p.relative_to(ROOT)): sha256(p) for p in context_files if p.is_file()}
    source_before = {"checkpoint": sha256(CHECKPOINT), "manifest": sha256(MANIFEST), "vocabulary": sha256(VOCAB), **{name: sha256(path) for name, path in SPLITS.items()}}
    if source_before["checkpoint"] != EXPECTED_CHECKPOINT_SHA:
        raise RuntimeError("STAGE1A_RCAB_CHECKPOINT_HASH_MISMATCH")

    manifest, lookup = manifest_lookup()
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    vocab_by_id = {int(v): str(k) for k, v in vocab.items()}
    if len(vocab_by_id) != NUM_CLASSES or set(vocab_by_id) != set(range(NUM_CLASSES)):
        raise RuntimeError("STAGE1A_VOCABULARY_MISMATCH")
    splits = {name: load_split(name) for name in SPLITS}
    for name, split in splits.items():
        if len(set(map(str, split["sample_ids"]))) != len(split["sample_ids"]):
            raise RuntimeError(f"STAGE1A_{name.upper()}_DUPLICATE_IDS")
        if any(str(sid) not in lookup for sid in split["sample_ids"]):
            raise RuntimeError(f"STAGE1A_{name.upper()}_MANIFEST_ID_MISSING")
    if set(map(str, splits["train"]["sample_ids"])) & set(map(str, splits["val"]["sample_ids"])):
        raise RuntimeError("STAGE1A_TRAIN_VAL_ID_OVERLAP")
    if set(map(str, splits["train"]["signer_group_ids"])) & set(map(str, splits["val"]["signer_group_ids"])):
        raise RuntimeError("STAGE1A_TRAIN_VAL_SIGNER_OVERLAP")

    import tensorflow as tf
    model = tf.keras.models.load_model(CHECKPOINT, safe_mode=False)
    if tuple(model.input_shape[1:]) != (96, 238) or tuple(model.output_shape[1:]) != (96, NUM_CLASSES):
        raise RuntimeError("STAGE1A_MODEL_SHAPE_MISMATCH")
    latent_layer = model.get_layer(LATENT_LAYER)
    latent_model = tf.keras.Model(model.input, latent_layer.output)
    weights_before = model_weights_hash(model)
    probe = splits["train"]["X"][:16]
    probe1 = np.asarray(latent_model(probe, training=False))
    probe2 = np.asarray(latent_model(probe, training=False))
    deterministic_max_abs = float(np.max(np.abs(probe1 - probe2)))
    if deterministic_max_abs > 1e-7:
        raise RuntimeError("STAGE1A_LATENT_EXTRACTION_NONDETERMINISTIC")

    latents, probabilities, pf_accuracy = {}, {}, {}
    for name in ["train", "val", "stress"]:
        latents[name], probabilities[name], pf_accuracy[name] = extract(model, latent_model, splits[name])
        means = latent_means(latents[name], splits[name]["frame_mask"].astype(bool)).astype(np.float32)
        np.savez_compressed(
            OUT / f"stage1a_{name}_latents.npz", latent_sequence=latents[name], clip_mean=means,
            frame_mask=splits[name]["frame_mask"], sample_ids=splits[name]["sample_ids"],
            y=splits[name]["y"], signer_group_ids=splits[name]["signer_group_ids"],
        )
    means = {name: latent_means(latents[name], splits[name]["frame_mask"].astype(bool)).astype(np.float64) for name in splits}
    scaler_mean = means["train"].mean(0)
    scaler_std_raw = means["train"].std(0)
    scaler_scale = np.where(scaler_std_raw > 1e-8, scaler_std_raw, 1.0)
    z = {name: (means[name] - scaler_mean) / scaler_scale for name in means}

    train_sources = np.asarray([lookup[str(sid)]["source_dataset"] for sid in splits["train"]["sample_ids"]], str)
    val_sources = np.asarray([lookup[str(sid)]["source_dataset"] for sid in splits["val"]["sample_ids"]], str)
    stress_sources = np.asarray([lookup[str(sid)]["source_dataset"] for sid in splits["stress"]["sample_ids"]], str)
    coverage, signer_conc, source_conc, coverage_matrix = class_coverage(splits["train"]["sample_ids"], vocab_by_id, lookup)
    coverage.to_csv(OUT / "stage1a_class_coverage_summary.csv", index=False)
    signer_conc.to_csv(OUT / "stage1a_signer_concentration.csv", index=False)
    source_conc.to_csv(OUT / "stage1a_source_concentration.csv", index=False)
    coverage_matrix.to_csv(OUT / "stage1a_class_signer_source_coverage.csv", index=False)

    val_pred = probabilities["val"].argmax(1)
    overall, per_class_rows, cm = metrics(splits["val"]["y"].astype(int), val_pred, probabilities["val"])
    overall["per_frame_accuracy"] = pf_accuracy["val"]
    per_class = pd.DataFrame(per_class_rows)
    per_class["gloss"] = per_class.class_id.map(vocab_by_id)
    per_class.to_csv(OUT / "stage1a_primary_val_per_class.csv", index=False)
    cm_rows = [{"true_class_id": i, "true_gloss": vocab_by_id[i], **{str(j): int(cm[i, j]) for j in range(NUM_CLASSES)}} for i in range(NUM_CLASSES)]
    write_csv(OUT / "stage1a_primary_val_confusion.csv", cm_rows)
    confusions = confusion_rows(cm, vocab_by_id)
    write_csv(OUT / "stage1a_ranked_confusion_pairs.csv", confusions)
    atomic_json(OUT / "stage1a_primary_val_overall_metrics.json", overall)

    class_geom, signer_geom, source_geom, geom_state = geometry(z["train"], splits["train"]["y"].astype(int), splits["train"]["signer_group_ids"].astype(str), train_sources, vocab_by_id)
    class_geom.to_csv(OUT / "stage1a_train_embedding_class_geometry.csv", index=False)
    signer_geom.to_csv(OUT / "stage1a_train_embedding_signer_geometry.csv", index=False)
    source_geom.to_csv(OUT / "stage1a_train_embedding_source_geometry.csv", index=False)
    val_diag, classifier_compare = validation_diagnostics(splits["val"], probabilities["val"], z["val"], val_sources, geom_state, coverage, vocab_by_id)
    val_diag.to_csv(OUT / "stage1a_validation_embedding_diagnostics.csv", index=False)
    classifier_compare.to_csv(OUT / "stage1a_classifier_vs_centroid.csv", index=False)
    assoc = associations(coverage, per_class, class_geom)
    assoc.to_csv(OUT / "stage1a_coverage_performance_associations.csv", index=False)
    case_studies = select_case_studies(coverage, per_class, class_geom, confusions, classifier_compare, source_geom, vocab_by_id)
    case_studies.to_csv(OUT / "stage1a_case_studies.csv", index=False)

    know, hello = vocab["KNOW"], vocab["HELLO"]
    stress_pred = probabilities["stress"].argmax(1)
    know_rows = []
    know_radius = geom_state["class_radii"][know]
    know_signers = [(s, cent) for (c, s), cent in geom_state["signer_centroids"].items() if c == know]
    hello_signers = [(s, cent) for (c, s), cent in geom_state["signer_centroids"].items() if c == hello]
    for i in np.flatnonzero(splits["stress"]["y"] == know):
        dk = float(np.linalg.norm(z["stress"][i] - geom_state["balanced_centroids"][know]))
        dh = float(np.linalg.norm(z["stress"][i] - geom_state["balanced_centroids"][hello]))
        pred = int(stress_pred[i])
        order = np.sort(probabilities["stress"][i])
        flags = []
        if dk > q(know_radius, .95): flags.append("OUTSIDE_KNOW_TRAIN_MANIFOLD")
        if dk <= q(know_radius, .95) and pred == hello: flags.append("INSIDE_KNOW_BUT_CLASSIFIER_HELLO")
        if dh <= dk or float(np.linalg.norm(geom_state["balanced_centroids"][know] - geom_state["balanced_centroids"][hello])) <= q(know_radius, .75) + q(geom_state["class_radii"][hello], .75): flags.append("KNOW_HELLO_MANIFOLDS_OVERLAP")
        if stress_sources[i] not in {lookup[str(sid)]["source_dataset"] for sid in splits["train"]["sample_ids"] if int(lookup[str(sid)]["class_id"]) == know}: flags.append("SOURCE_SIGNER_STRUCTURE_PRESENT")
        if not flags: flags.append("INCONCLUSIVE")
        know_rows.append({
            "sample_id": str(splits["stress"]["sample_ids"][i]), "distance_train_know_balanced_centroid": dk,
            "distance_train_hello_balanced_centroid": dh,
            "nearest_train_know_signer": min(know_signers, key=lambda p: np.linalg.norm(z["stress"][i] - p[1]))[0],
            "nearest_train_know_signer_distance": min(float(np.linalg.norm(z["stress"][i] - p[1])) for p in know_signers),
            "nearest_train_hello_signer": min(hello_signers, key=lambda p: np.linalg.norm(z["stress"][i] - p[1]))[0],
            "nearest_train_hello_signer_distance": min(float(np.linalg.norm(z["stress"][i] - p[1])) for p in hello_signers),
            "know_train_distance_percentile": float(100 * np.mean(know_radius <= dk)),
            "rcab_know_probability": float(probabilities["stress"][i, know]), "rcab_hello_probability": float(probabilities["stress"][i, hello]),
            "predicted_class_id": pred, "predicted_gloss": vocab_by_id[pred], "classifier_margin": float(order[-1] - order[-2]),
            "descriptive_observations": "|".join(flags),
        })
    pd.DataFrame(know_rows).to_csv(OUT / "stage1a_know_hello_learned_space.csv", index=False)
    temporal = temporal_cases(case_studies, latents["train"], splits["train"], latents["val"], splits["val"], latents["stress"], splits["stress"], scaler_mean, scaler_scale, vocab)
    temporal.to_csv(OUT / "stage1a_temporal_case_study_diagnostics.csv", index=False)

    coverage_percentiles = {}
    for column in ["raw_training_clips", "unique_signer_groups", "effective_signer_count", "largest_signer_share", "top3_signer_share", "source_hhi"]:
        coverage_percentiles[column] = {f"p{p}": float(coverage[column].quantile(p / 100)) for p in [10, 25, 50, 75, 90, 95]}
    relation_counts = classifier_compare.relationship.value_counts().to_dict()
    wrong_diag = val_diag[val_diag.top1_correct == 0]
    flag_counts = Counter(flag for text in wrong_diag.descriptive_geometry_flags for flag in str(text).split("|") if flag)
    signer_summaries = signer_geom[signer_geom.row_type == "CLASS_SUMMARY"]
    source_summaries = source_geom[source_geom.row_type == "CLASS_SUMMARY"]
    recall_assoc = assoc[(assoc.analysis == "SPEARMAN") & (assoc.target == "recall")].set_index("predictor").value.to_dict()
    summary = {
        "counts": {name: len(splits[name]["y"]) for name in splits}, "vocabulary": NUM_CLASSES,
        "coverage_percentiles": coverage_percentiles,
        "most_signer_concentrated": coverage.sort_values(["largest_signer_share", "signer_hhi"], ascending=False).head(10)[["gloss", "raw_training_clips", "unique_signer_groups", "effective_signer_count", "largest_signer_share"]].to_dict("records"),
        "high_raw_low_effective_signers": coverage[(coverage.raw_training_clips >= coverage.raw_training_clips.quantile(.75)) & (coverage.effective_signer_count <= coverage.effective_signer_count.quantile(.25))].sort_values("effective_signer_count").head(10)[["gloss", "raw_training_clips", "unique_signer_groups", "effective_signer_count"]].to_dict("records"),
        "primary_validation": overall, "top_confusions": confusions[:20],
        "validation_errors": {"total": int(len(wrong_diag)), "flags": dict(flag_counts)},
        "classifier_vs_centroid": {str(k): int(v) for k, v in relation_counts.items()},
        "signer_structure": {"classes_supported": int(signer_summaries.different_pair_count.fillna(0).gt(0).sum()), "median_same_to_different_ratio": float(signer_summaries.same_to_different_ratio.dropna().median())},
        "source_structure": {"classes_with_cross_source_pairs": int(source_summaries.cross_pair_count.fillna(0).gt(0).sum()), "median_within_to_cross_ratio": float(source_summaries.within_to_cross_ratio.dropna().median()) if source_summaries.within_to_cross_ratio.notna().any() else None},
        "coverage_performance_spearman_recall": {str(k): float(v) for k, v in recall_assoc.items()},
        "know_hello": {"stress_know_count": len(know_rows), "observation_counts": dict(Counter(flag for row in know_rows for flag in row["descriptive_observations"].split("|")))},
        "root_cause_selected": False, "recommended_fix_selected": False,
    }
    atomic_json(OUT / "stage1a_raw_summary.json", summary)

    model_contract = {
        "checkpoint": str(CHECKPOINT.resolve()), "checkpoint_sha256": source_before["checkpoint"],
        "input_shape": list(model.input_shape), "output_shape": list(model.output_shape),
        "parameter_count_total": int(model.count_params()), "output_classes": NUM_CLASSES,
        "layers": [{"name": layer.name, "class": layer.__class__.__name__, "output_shape": str(getattr(layer, "output", "").shape), "parameters": int(layer.count_params())} for layer in model.layers],
        "final_projection": "logits_perframe", "classifier_input_layer": LATENT_LAYER,
        "classifier_input_shape": list(latent_layer.output.shape), "dropout_inference": False,
        "weights_hash_before": weights_before,
    }
    atomic_json(OUT / "stage1a_rcab_model_contract.json", model_contract)
    extraction_contract = {
        "layer": LATENT_LAYER, "tensor_shape_padded": [96, 64], "representation_type": "per_frame_classifier_input",
        "inference_mode": "training=False", "real_frame_rule": "frame_mask == true; padding excluded",
        "clip_representation": "arithmetic mean of classifier-input latent vectors over real frames only",
        "standardization_fit_population": "TRAIN clip means only", "standardization_mean": scaler_mean.tolist(), "standardization_scale": scaler_scale.tolist(),
        "zero_variance_channels": int(np.sum(scaler_std_raw <= 1e-8)), "determinism_tolerance": 1e-7,
        "determinism_max_abs_difference": deterministic_max_abs,
        "validation_geometry_flags": {
            "outside": "distance to signer-balanced true centroid > TRAIN true-class p95",
            "near_true_classifier_wrong": "distance <= TRAIN true-class p75 and signer-balanced nearest centroid is true class",
            "overlap": "wrong centroid no farther than true centroid OR true/wrong centroid distance <= sum of TRAIN class p75 radii",
            "source_signer_suspected": "true class effective signer count <= TRAIN vocabulary p25 OR validation source absent from true-class TRAIN sources",
            "ambiguous": "misclassified and no preceding condition",
        },
        "temporal_case_method": "linear resampling of real-frame latent sequence to 16 normalized positions; no learned model",
    }
    atomic_json(OUT / "stage1a_latent_extraction_contract.json", extraction_contract)

    low_support = per_class[per_class.support < 5]
    limitations = f"""# Stage 1A Evidence Limitations

- Primary validation has fewer than five clips for **{len(low_support)}/{NUM_CLASSES}** classes; class-level recall and confusion fractions are therefore unstable for those classes.
- Signer-distance analysis is descriptive. Classes lacking at least two training signers cannot support cross-signer geometry conclusions.
- Cross-source geometry is available for only **{int(source_summaries.cross_pair_count.fillna(0).gt(0).sum())}** classes with cross-source sample pairs; source and signer are partially confounded.
- The stress cohort is 163 natural AppHear clips from one repeatedly inspected signer and four classes. Its KNOW/HELLO findings do not establish vocabulary-wide generalization.
- Centroid distances simplify a nonlinear temporal classifier. Full latent-sequence diagnostics are supplied for selected cases, but no new classifier was fitted.
- Geometry flags use TRAIN-derived empirical distributions and are descriptive, non-exclusive evidence tags—not causal root-cause labels.
- Correlations across classes are descriptive and cannot establish causation.
- No primary-test tensor was opened or used.
"""
    atomic_text(OUT / "stage1a_evidence_limitations.md", limitations)

    context_after = {str(p.relative_to(ROOT)): sha256(p) for p in sorted((ROOT / "context").rglob("*")) if p.is_file()}
    source_after = {"checkpoint": sha256(CHECKPOINT), "manifest": sha256(MANIFEST), "vocabulary": sha256(VOCAB), **{name: sha256(path) for name, path in SPLITS.items()}}
    weights_after = model_weights_hash(model)
    integrity = {
        "passed": source_before == source_after and context_before == context_after and weights_before == weights_after,
        "checkpoint_sha_verified": source_before["checkpoint"] == EXPECTED_CHECKPOINT_SHA,
        "source_hashes_before": source_before, "source_hashes_after": source_after,
        "sample_counts": {name: len(splits[name]["y"]) for name in splits},
        "train_signer_count": len(set(map(str, splits["train"]["signer_group_ids"]))),
        "validation_signer_count": len(set(map(str, splits["val"]["signer_group_ids"]))),
        "stress_signer_count": len(set(map(str, splits["stress"]["signer_group_ids"]))),
        "train_source_count": len(set(train_sources)), "validation_source_count": len(set(val_sources)), "stress_source_count": len(set(stress_sources)),
        "protected_primary_test_opened": False, "training_performed": False, "model_weights_changed": weights_before != weights_after,
        "dataset_files_modified": source_before != source_after, "context_files_modified": context_before != context_after,
        "progress_tracker_untouched": context_before.get("context/progress-tracker.md") == context_after.get("context/progress-tracker.md"),
        "latent_repeat_max_abs_difference": deterministic_max_abs,
    }
    atomic_json(OUT / "stage1a_integrity.json", integrity)
    if not integrity["passed"]:
        raise RuntimeError("STAGE1A_INTEGRITY_FAILURE")

    result = f"""# Stage 1A — Frozen RCA-B Full-Vocabulary Root-Cause Evidence

## Scope

Read-only evidence build using frozen TRAIN, primary validation, and the 163-row diagnostic stress cohort. No training, primary-test access, root-cause selection, or intervention selection occurred.

## Frozen model and learned representation

- Checkpoint: `{CHECKPOINT.resolve()}`
- SHA-256: `{source_before['checkpoint']}`
- Frozen input/output: `[96,238] -> [96,236]`
- True classifier-input layer: `{LATENT_LAYER}` with per-frame width 64.
- Full real-frame `[T,64]` latent sequences and masked arithmetic clip means were extracted with `training=False`.
- Repeat extraction maximum absolute difference: `{deterministic_max_abs:.3g}`.

## Coverage evidence

- TRAIN clips: {len(splits['train']['y'])}; vocabulary: {NUM_CLASSES}; TRAIN signers: {integrity['train_signer_count']}; sources: {integrity['train_source_count']}.
- Median raw clips/class: {coverage.raw_training_clips.median():.3f}.
- Median unique signers/class: {coverage.unique_signer_groups.median():.3f}.
- Median effective signer count/class: {coverage.effective_signer_count.median():.3f}.
- Largest-signer concentration, top-3 shares, signer/source HHI, and effective counts are reported for all classes. Raw clip count is kept distinct from independent signer diversity.

## Primary-validation performance

- Top-1: {overall['top1']:.6f}
- Top-5: {overall['top5']:.6f}
- Macro F1: {overall['macro_f1']:.6f}
- Per-frame accuracy: {overall['per_frame_accuracy']:.6f}

The complete 236×236 confusion matrix, per-class metrics, and ranked asymmetric/reciprocal confusion pairs are frozen in the companion artifacts.

## Learned-space evidence

- Misclassified validation clips: {len(wrong_diag)}.
- Outside true-class TRAIN p95: {flag_counts.get('OUTSIDE_TRUE_CLASS_TRAIN_DISTRIBUTION', 0)}.
- Near true-class centroid but classifier wrong: {flag_counts.get('NEAR_TRUE_CLASS_BUT_CLASSIFIER_WRONG', 0)}.
- True/wrong class overlap flag: {flag_counts.get('TRUE_AND_WRONG_CLASS_OVERLAP', 0)}.
- Source/signer structure suspected: {flag_counts.get('SOURCE_OR_SIGNER_STRUCTURE_SUSPECTED', 0)}.
- Classifier versus signer-balanced centroid relationships: `{json.dumps(relation_counts, sort_keys=True)}`.

Sample-weighted and signer-balanced class representations remain separate. Signer/source geometry and coverage-performance associations are descriptive only.

## KNOW/HELLO diagnostic

Thirty stress KNOW clips were measured in the actual frozen RCA-B classifier-input space against TRAIN KNOW and HELLO signer-balanced and signer-specific representatives. The exact distances, empirical KNOW percentiles, probabilities, margins, and non-causal observations are in `stage1a_know_hello_learned_space.csv`. This one-signer case is not promoted to a vocabulary-wide cause.

## Decision boundary

Stage 1A selects no root cause and recommends no fix. Interpretation is deferred to Stage 1B after review of the complete evidence package.
"""
    atomic_text(OUT / "STAGE1A_RCAB_EVIDENCE_RESULT.md", result)

    artifact_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "artifact_hash_manifest.json":
            artifact_rows.append({"path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size})
    atomic_json(OUT / "artifact_hash_manifest.json", {"artifacts": artifact_rows, "protected_primary_test_opened": False, "training_performed": False})
    print(json.dumps({"status": "APPHEAR_STAGE1A_EVIDENCE_BUILD_COMPLETE", "artifact_directory": str(OUT.resolve()), "integrity": integrity, "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
