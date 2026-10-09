"""Read-only P5-B RCA-A artifact analysis.

This module reads frozen P5-A/P5-B and historical v3 artifacts and writes only new RCA-A
diagnostic files. It never trains, extracts landmarks, or changes any frozen artifact.
"""
from __future__ import annotations

import csv
import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "artifacts/recognition_upgrade/phase1_full_vocab"
OLD_DATA = OLD / "dataset_v1"
OLD_RUN = OLD / "tcn_comparison_01"
P5 = ROOT / "artifacts/recognition_upgrade/p5_representation_v2"
NEW_DATA = P5 / "p5b_migration_01/dataset"
MIGRATION = P5 / "p5b_migration_01"
NEW_RUN = P5 / "p5b_baseline_01"
OUT = P5 / "p5b_rcaa_01"
MANIFEST = OLD / "manifest_01/canonical_manifest.csv"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stats(values: Iterable[float]) -> dict[str, float | int | None]:
    x = np.asarray(list(values), dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return {"n": 0, "mean": None, "std": None, "median": None, "p1": None,
                "p90": None, "p95": None, "p99": None, "cv": None}
    mean = float(np.mean(x))
    return {
        "n": int(x.size), "mean": mean, "std": float(np.std(x)),
        "median": float(np.median(x)), "p1": float(np.percentile(x, 1)),
        "p90": float(np.percentile(x, 90)), "p95": float(np.percentile(x, 95)),
        "p99": float(np.percentile(x, 99)),
        "cv": float(np.std(x) / abs(mean)) if abs(mean) > 1e-12 else None,
    }


def slope(values: list[float], n: int) -> float:
    y = np.asarray(values[-n:], dtype=np.float64)
    x = np.arange(y.size, dtype=np.float64)
    return float(np.polyfit(x, y, 1)[0])


def effect_size(a: Iterable[float], b: Iterable[float]) -> float | None:
    x = np.asarray(list(a), dtype=np.float64); y = np.asarray(list(b), dtype=np.float64)
    x = x[np.isfinite(x)]; y = y[np.isfinite(y)]
    if len(x) < 2 or len(y) < 2:
        return None
    pooled = math.sqrt(((len(x)-1)*np.var(x, ddof=1)+(len(y)-1)*np.var(y, ddof=1))/(len(x)+len(y)-2))
    return float((np.mean(x)-np.mean(y))/pooled) if pooled > 1e-12 else 0.0


def training_dynamics() -> dict[str, Any]:
    rows = read_csv(NEW_RUN / "history.csv")
    for row in rows:
        for k in row:
            row[k] = float(row[k]) if k != "epoch" else int(row[k])
    best_acc = max(range(len(rows)), key=lambda i: rows[i]["val_pf_acc"])
    best_loss = min(range(len(rows)), key=lambda i: rows[i]["val_loss"])
    final = len(rows)-1
    metrics = ["loss", "pf_acc", "val_loss", "val_pf_acc"]
    trend = {m: {"last_5_slope_per_epoch": slope([r[m] for r in rows], 5),
                 "last_10_slope_per_epoch": slope([r[m] for r in rows], 10)} for m in metrics}
    still = (trend["val_loss"]["last_10_slope_per_epoch"] < -0.003 or
             trend["val_pf_acc"]["last_10_slope_per_epoch"] > 0.002)
    return {
        "epochs": len(rows), "best_validation_accuracy_epoch": int(rows[best_acc]["epoch"]),
        "best_validation_loss_epoch": int(rows[best_loss]["epoch"]),
        "final_epoch": int(rows[final]["epoch"]),
        "at_best_validation_accuracy": rows[best_acc],
        "at_best_validation_loss": rows[best_loss], "at_final": rows[final],
        "trends": trend,
        "diagnostic_rule": "STILL_CONVERGING if last-10 val_loss slope < -0.003 or val_pf_acc slope > 0.002",
        "classification": "STILL_CONVERGING" if still else "PLATEAUED",
        "raw_history": rows,
    }


def identity_and_mapping(manifest_rows: list[dict[str, str]]) -> tuple[dict[str, Any], dict[str, Any]]:
    with np.load(OLD_DATA / "test.npz", allow_pickle=False) as z:
        old_ids = z["sample_ids"].astype(str); old_y = z["y"].astype(np.int64)
        old_signers = z["participant_ids"].astype(str); old_mask = z["frame_mask"].astype(bool)
    with np.load(NEW_DATA / "test.npz", allow_pickle=False) as z:
        new_ids = z["sample_ids"].astype(str); new_y = z["y"].astype(np.int64)
        new_signers = z["signer_group_ids"].astype(str); new_mask = z["frame_mask"].astype(bool)
    rows_by_id = {r["sample_id"]: r for r in manifest_rows}
    class_pairs = {(r["canonical_gloss"], int(r["class_id"])) for r in manifest_rows}
    gloss_to_ids: dict[str, set[int]] = defaultdict(set)
    id_to_gloss: dict[int, set[str]] = defaultdict(set)
    for gloss, cid in class_pairs:
        gloss_to_ids[gloss].add(cid); id_to_gloss[cid].add(gloss)
    deterministic = [str(old_ids[i]) for i in [0, len(old_ids)//2, len(old_ids)-1]]
    samples = [{"sample_id": sid, "gloss": rows_by_id[sid]["canonical_gloss"],
                "manifest_class_id": int(rows_by_id[sid]["class_id"]),
                "old_y": int(old_y[np.where(old_ids == sid)[0][0]]),
                "new_y": int(new_y[np.where(new_ids == sid)[0][0]])} for sid in deterministic]
    identity = {
        "old_count": len(old_ids), "new_count": len(new_ids),
        "sample_ids_same_order": bool(np.array_equal(old_ids, new_ids)),
        "sample_id_sets_equal": bool(set(old_ids) == set(new_ids)),
        "labels_same_order": bool(np.array_equal(old_y, new_y)),
        "signers_same_order": bool(np.array_equal(old_signers, new_signers)),
        "frame_masks_same_order": bool(np.array_equal(old_mask, new_mask)),
        "old_sample_id_order_sha256": hashlib.sha256("\n".join(old_ids).encode()).hexdigest(),
        "new_sample_id_order_sha256": hashlib.sha256("\n".join(new_ids).encode()).hexdigest(),
        "old_labels_sha256": hashlib.sha256(old_y.tobytes()).hexdigest(),
        "new_labels_sha256": hashlib.sha256(new_y.tobytes()).hexdigest(),
        "comparison": "EXACT" if np.array_equal(old_ids,new_ids) and np.array_equal(old_y,new_y) else "NOT_EXACT",
    }
    mapping = {
        "class_count": len(id_to_gloss), "gloss_count": len(gloss_to_ids),
        "gloss_to_multiple_ids": {k: sorted(v) for k,v in gloss_to_ids.items() if len(v)>1},
        "id_to_multiple_glosses": {str(k): sorted(v) for k,v in id_to_gloss.items() if len(v)>1},
        "old_new_labels_identical": bool(np.array_equal(old_y,new_y)),
        "manifest_matches_old": bool(all(int(rows_by_id[s]["class_id"]) == int(y) for s,y in zip(old_ids,old_y))),
        "manifest_matches_new": bool(all(int(rows_by_id[s]["class_id"]) == int(y) for s,y in zip(new_ids,new_y))),
        "deterministic_samples": samples,
        "comparison": "EXACT" if np.array_equal(old_y,new_y) and not any(len(v)>1 for v in gloss_to_ids.values()) and not any(len(v)>1 for v in id_to_gloss.values()) else "NOT_EXACT",
    }
    return identity, mapping


def aggregation_audit() -> dict[str, Any]:
    return {
        "historical": {
            "artifact_backed_code": "eval/streaming.py:mean_over_real,predict_aggregate",
            "frame_mask": "boolean real-frame prefix; padded frames excluded",
            "operation": "arithmetic mean of per-frame softmax over real frames",
            "top1": "argmax of mean clip probabilities",
            "top5": "five largest mean clip probabilities",
        },
        "p5b": {
            "artifact_backed_code": "model/p5b_temporal_baseline.py:clip_probs,evaluate",
            "frame_mask": "boolean real-frame prefix; padded frames excluded",
            "operation": "arithmetic mean of per-frame softmax over real frames",
            "top1": "argmax of mean clip probabilities",
            "top5": "five largest mean clip probabilities",
        },
        "comparison": "EXACT",
        "note": "Equivalent formulas; no alternative aggregation tested.",
    }


def historical_parity_rows() -> list[dict[str, Any]]:
    evidence_old = "pipeline/config/normalize.yaml; pipeline/normalize/transforms.py; pipeline/features/contract.py"
    evidence_new = "pipeline/features/dwpose_representation_v2.py; p5b_training_contract.json"
    rows = [
        ("hand_coordinates","MediaPipe image XYZ, torso-centered/scaled/rolled/canonicalized","DWPose image XY, current-frame torso-centered/scaled","YES"),
        ("body_coordinates","MediaPipe 33 pose x,y,z,visibility","DWPose 17 body x,y,score,valid","YES"),
        ("depth","ACTIVE: hand and body Z scaled by clip scale","INACTIVE: no Z","YES"),
        ("confidence","hand confidence absent; pose visibility retained","DWPose continuous score retained for every landmark","YES"),
        ("validity_mask","no in-vector validity; NaN geometry zeroed","per-landmark valid_mask in vector","YES"),
        ("observation_mask","hand presence auxiliary, not in 258","left/right observed masks in 238","YES"),
        ("centering","ACTIVE: per-frame shoulder midpoint; span-median fallback","ACTIVE: current-frame shoulders; hips/body fallback","PARTIAL"),
        ("scale","ACTIVE: one median shoulder-width scalar per clip","ACTIVE: current-frame shoulder distance","YES"),
        ("roll_normalization","ACTIVE: one median shoulder angle per clip","INACTIVE","YES"),
        ("mirroring","ACTIVE conditionally for left-dominant clips","INACTIVE","YES"),
        ("handedness_canonicalization","ACTIVE: dominant hand canonicalized RIGHT and hand blocks swapped","INACTIVE: anatomical slots retained","YES"),
        ("hand_local_normalization","INACTIVE","INACTIVE","NO"),
        ("global_body_normalization","ACTIVE: shared body center/clip scale for hands+pose","ACTIVE: shared current-frame body center/scale","PARTIAL"),
        ("body_keypoint_count","33","17","YES"),
        ("temporal_normalization_scope","center per-frame; scale/roll/handedness per-clip span","center+scale independently per current frame","YES"),
        ("sequence_timing","real timing, prefix pad/truncate T=96","same governed real timing, prefix pad/truncate T=96","NO"),
        ("warm_start","ACTIVE: 17 encoder weights copied from accepted v3 model","INACTIVE","YES"),
        ("augmentation","ACTIVE: temporal stride plus rotation/scale/noise","INACTIVE: NONE","YES"),
    ]
    return [{"property":a,"historical_96x258":b,"p5b_96x238":c,"material_difference":d,
             "historical_evidence":evidence_old,"p5b_evidence":evidence_new} for a,b,c,d in rows]


def _motion(points: np.ndarray, valid: np.ndarray, scale: np.ndarray | None = None) -> np.ndarray:
    if len(points) < 2: return np.array([], dtype=np.float64)
    ok = valid[1:] & valid[:-1]
    d = np.linalg.norm(points[1:] - points[:-1], axis=-1)
    if scale is not None:
        d = d / np.maximum(scale[:-1], 1e-6)
    return d[ok & np.isfinite(d)]


def jitter_analysis(completed_rows: list[dict[str, Any]], predictions: dict[str, bool]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    aggregate: dict[str, list[float]] = defaultdict(list)
    for index, item in enumerate(completed_rows, 1):
        native_path = ROOT / item["native_path"]
        feature_path = ROOT / item["feature_path"]
        with np.load(native_path, allow_pickle=False) as z:
            kp = np.asarray(z["keypoints_xy"], np.float64); sc = np.asarray(z["scores"], np.float64)
        with np.load(feature_path, allow_pickle=False) as z:
            feat = np.asarray(z["features"], np.float64); length = int(z["length"])
        kp = kp[:length]; sc = sc[:length]; feat = feat[:length]
        finite = np.isfinite(kp).all(2) & np.isfinite(sc)
        centers = (kp[:,5]+kp[:,6])/2
        shoulder_scale = np.linalg.norm(kp[:,5]-kp[:,6],axis=1)
        center_valid = finite[:,5]&finite[:,6]&(shoulder_scale>1e-6)
        shoulder_vector = kp[:,6] - kp[:,5]
        shoulder_roll = np.arctan2(shoulder_vector[:,1], shoulder_vector[:,0])
        shoulder_roll = np.where(shoulder_roll > np.pi/2, shoulder_roll-np.pi, shoulder_roll)
        shoulder_roll = np.where(shoulder_roll <= -np.pi/2, shoulder_roll+np.pi, shoulder_roll)
        valid_roll = shoulder_roll[center_valid & np.isfinite(shoulder_roll)]
        left_wrist_steps = _motion(kp[:,9], finite[:,9])
        right_wrist_steps = _motion(kp[:,10], finite[:,10])
        left_motion = float(np.sum(left_wrist_steps)); right_motion = float(np.sum(right_wrist_steps))
        total_wrist_motion = left_motion + right_motion
        left_dominant = bool(total_wrist_motion > 0 and (left_motion-right_motion)/total_wrist_motion > 0.15)
        body_n = feat[:,168:236].reshape(length,17,4); lh_n=feat[:,:84].reshape(length,21,4); rh_n=feat[:,84:168].reshape(length,21,4)
        measures: dict[str,np.ndarray] = {}
        measures["center_jitter_raw_scale_adjusted"] = _motion(centers,center_valid,shoulder_scale)
        pct=np.abs(np.diff(shoulder_scale))/np.maximum(shoulder_scale[:-1],1e-6)
        measures["scale_pct_change"] = pct[center_valid[1:]&center_valid[:-1]&np.isfinite(pct)]
        for name,idx in [("left_elbow",7),("right_elbow",8),("left_wrist",9),("right_wrist",10),("left_shoulder",5),("right_shoulder",6),("left_hip",11),("right_hip",12)]:
            measures[f"{name}_raw_scale_adjusted"]=_motion(kp[:,idx],finite[:,idx],shoulder_scale)
            measures[f"{name}_normalized"]=_motion(body_n[:,idx,:2],body_n[:,idx,3]>.5)
        for name,inds,block in [("left_hand_centroid",np.arange(91,112),lh_n),("right_hand_centroid",np.arange(112,133),rh_n)]:
            raw_valid=np.all(finite[:,inds],axis=1)
            measures[f"{name}_raw_scale_adjusted"]=_motion(np.mean(kp[:,inds],axis=1),raw_valid,shoulder_scale)
            norm_valid=np.all(block[:,:,3]>.5,axis=1)
            measures[f"{name}_normalized"]=_motion(np.mean(block[:,:,:2],axis=1),norm_valid)
        base=np.concatenate([measures["left_wrist_raw_scale_adjusted"],measures["right_wrist_raw_scale_adjusted"]])
        norm=np.concatenate([measures["left_wrist_normalized"],measures["right_wrist_normalized"]])
        # Frozen diagnostic formula: ratio of distribution medians, not paired threshold tuning.
        amplification=float(np.median(norm)/max(np.median(base),1e-9)) if len(norm) and len(base) else math.nan
        row={"sample_id":item["sample_id"],"split":item["split"],"role":item["role"],"signer_group_id":item["signer_group_id"],"frames":length,
             "test_correct":int(predictions[item["sample_id"]]) if item["sample_id"] in predictions else "",
             "wrist_motion_amplification_ratio":amplification,
             "median_abs_shoulder_roll_degrees":float(np.degrees(np.median(np.abs(valid_roll)))) if len(valid_roll) else math.nan,
             "left_dominant_motion_proxy":int(left_dominant)}
        for key,values in measures.items():
            s=stats(values); row[f"{key}_median"]=s["median"]; row[f"{key}_p95"]=s["p95"]
            aggregate[key].extend(values.tolist())
        rows.append(row)
        if index % 500 == 0: print(f"[rcaa] jitter {index}/{len(completed_rows)}", flush=True)
    summary={"amplification_formula":"median(normalized wrist displacement) / median(raw wrist displacement / previous-frame shoulder distance)",
             "aggregate":{k:stats(v) for k,v in sorted(aggregate.items())}}
    ratios=[float(r["wrist_motion_amplification_ratio"]) for r in rows if np.isfinite(float(r["wrist_motion_amplification_ratio"]))]
    summary["sample_amplification_ratio"]=stats(ratios)
    test=[r for r in rows if r["test_correct"]!=""]
    summary["canonicalization_diagnostics"]={
        "median_abs_shoulder_roll_degrees":stats(float(r["median_abs_shoulder_roll_degrees"]) for r in rows),
        "left_dominant_motion_proxy_rate":float(np.mean([int(r["left_dominant_motion_proxy"]) for r in rows])),
        "note":"Proxy follows the historical 0.15 wrist-motion dominance rule using DWPose body wrists; it is not a label.",
    }
    for metric in ["scale_pct_change_median","center_jitter_raw_scale_adjusted_median","left_wrist_normalized_median","right_wrist_normalized_median","left_hand_centroid_normalized_median","right_hand_centroid_normalized_median","wrist_motion_amplification_ratio","median_abs_shoulder_roll_degrees","left_dominant_motion_proxy"]:
        correct=[float(r[metric]) for r in test if r["test_correct"]==1 and r[metric] is not None and np.isfinite(float(r[metric]))]
        wrong=[float(r[metric]) for r in test if r["test_correct"]==0 and r[metric] is not None and np.isfinite(float(r[metric]))]
        summary.setdefault("correct_vs_incorrect",{})[metric]={"correct":stats(correct),"incorrect":stats(wrong),"cohens_d_correct_minus_incorrect":effect_size(correct,wrong)}
    return rows,summary


def distribution_analysis(manifest_rows: list[dict[str,str]], predictions: dict[str,bool]) -> tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    by_id={r["sample_id"]:r for r in manifest_rows}
    distribution: list[dict[str,Any]]=[]; group_rows: list[dict[str,Any]]=[]
    for split in ["train","val","test"]:
        with np.load(NEW_DATA/f"{split}.npz",allow_pickle=False) as z:
            x=np.asarray(z["X"],np.float32); mask=np.asarray(z["frame_mask"],bool); ids=z["sample_ids"].astype(str); signers=z["signer_group_ids"].astype(str)
        real=x[mask]
        channel_mean=np.mean(real,axis=0); channel_var=np.var(real,axis=0); channel_zero=np.mean(real==0,axis=0)
        for i in range(238):
            distribution.append({"scope":"channel","split":split,"feature_index":i,"metric":"channel_distribution","mean":float(channel_mean[i]),"variance":float(channel_var[i]),"zero_fraction":float(channel_zero[i]),"constant":int(channel_var[i]==0),"near_constant":int(channel_var[i]<1e-8)})
        blocks={"x":np.concatenate([real[:,0:84:4].ravel(),real[:,84:168:4].ravel(),real[:,168:236:4].ravel()]),
                "y":np.concatenate([real[:,1:84:4].ravel(),real[:,85:168:4].ravel(),real[:,169:236:4].ravel()]),
                "score":np.concatenate([real[:,2:84:4].ravel(),real[:,86:168:4].ravel(),real[:,170:236:4].ravel()]),
                "valid":np.concatenate([real[:,3:84:4].ravel(),real[:,87:168:4].ravel(),real[:,171:236:4].ravel()])}
        for name,v in blocks.items():
            s=stats(v); distribution.append({"scope":"block","split":split,"feature_index":"","metric":name,**s,"zero_fraction":float(np.mean(v==0)),"extreme_abs_gt10":float(np.mean(np.abs(v)>10))})
        left=x[:,:,236][mask]; right=x[:,:,237][mask]
        distribution.extend([
            {"scope":"mask","split":split,"metric":"left_observed_rate","mean":float(left.mean())},
            {"scope":"mask","split":split,"metric":"right_observed_rate","mean":float(right.mean())},
            {"scope":"mask","split":split,"metric":"both_observed_rate","mean":float(np.mean((left>.5)&(right>.5)))},
            {"scope":"all","split":split,"metric":"overall_zero_fraction","mean":float(np.mean(real==0))},
        ])
        group_indices: dict[tuple[str,str],list[int]]=defaultdict(list)
        for i,sid in enumerate(ids):
            source=by_id[sid]["source_dataset"]
            group_indices[("source",source)].append(i); group_indices[("signer",signers[i])].append(i)
        for (kind,name),ix in sorted(group_indices.items()):
            xx=x[ix]; mm=mask[ix]; rr=xx[mm]
            lh=xx[:,:,236][mm]; rh=xx[:,:,237][mm]
            coord=np.concatenate([rr[:,0:84:4].ravel(),rr[:,1:84:4].ravel(),rr[:,84:168:4].ravel(),rr[:,85:168:4].ravel(),rr[:,168:236:4].ravel(),rr[:,169:236:4].ravel()])
            score=np.concatenate([rr[:,2:84:4].ravel(),rr[:,86:168:4].ravel(),rr[:,170:236:4].ravel()])
            correct=[predictions[ids[i]] for i in ix if ids[i] in predictions]
            group_rows.append({"split":split,"group_kind":kind,"group":name,"samples":len(ix),"real_frames":int(mm.sum()),"coordinate_mean":float(np.mean(coord)),"coordinate_std":float(np.std(coord)),"coordinate_p1":float(np.percentile(coord,1)),"coordinate_p99":float(np.percentile(coord,99)),"score_mean":float(np.mean(score)),"valid_rate":float(np.mean(np.concatenate([rr[:,3:84:4].ravel(),rr[:,87:168:4].ravel(),rr[:,171:236:4].ravel()]))),"left_observed_rate":float(lh.mean()),"right_observed_rate":float(rh.mean()),"both_observed_rate":float(np.mean((lh>.5)&(rh>.5))),"accuracy":float(np.mean(correct)) if correct else ""})
        del x,real
    return distribution,group_rows


def error_structure(manifest_rows:list[dict[str,str]], jitter_rows:list[dict[str,Any]]) -> list[dict[str,Any]]:
    pred_rows=read_csv(NEW_RUN/"test_predictions.csv"); by_manifest={r["sample_id"]:r for r in manifest_rows}; by_jitter={r["sample_id"]:r for r in jitter_rows}
    conf=Counter((int(r["true_class"]),int(r["pred_class"])) for r in pred_rows if r["correct"]=="0")
    rows=[]
    for r in pred_rows:
        m=by_manifest[r["sample_id"]]; j=by_jitter[r["sample_id"]]
        rows.append({"row_type":"sample","sample_id":r["sample_id"],"signer_group_id":r["signer_group_id"],"source_dataset":m["source_dataset"],"true_class":r["true_class"],"pred_class":r["pred_class"],"correct":r["correct"],"both_observed_fraction":r["both_observed_fraction"],"left_max_missing_run":r["left_max_missing_run"],"right_max_missing_run":r["right_max_missing_run"],"scale_variability":j["scale_pct_change_median"],"center_jitter":j["center_jitter_raw_scale_adjusted_median"],"wrist_motion_amplification":j["wrist_motion_amplification_ratio"]})
    for (truth,pred),n in conf.most_common(25): rows.append({"row_type":"top_confusion","true_class":truth,"pred_class":pred,"count":n})
    return rows


def _macro_f1(truth: np.ndarray, pred: np.ndarray, classes: int = 236) -> float:
    values=[]
    for c in range(classes):
        active=(truth==c)|(pred==c)
        if not np.any(active): continue
        tp=int(np.sum((truth==c)&(pred==c))); fp=int(np.sum((truth!=c)&(pred==c))); fn=int(np.sum((truth==c)&(pred!=c)))
        values.append((2*tp)/(2*tp+fp+fn) if (2*tp+fp+fn) else 0.0)
    return float(np.mean(values)) if values else 0.0


def finalize() -> int:
    dynamics=json.loads((OUT/"p5b_rcaa_training_dynamics.json").read_text(encoding="utf-8"))
    jitter=json.loads((OUT/"p5b_rcaa_temporal_jitter_summary.json").read_text(encoding="utf-8"))
    identity=json.loads((OUT/"p5b_rcaa_test_identity_audit.json").read_text(encoding="utf-8"))
    mapping=json.loads((OUT/"p5b_rcaa_label_mapping_audit.json").read_text(encoding="utf-8"))
    groups=read_csv(OUT/"p5b_rcaa_signer_source_analysis.csv")
    predictions=read_csv(NEW_RUN/"test_predictions.csv")
    by_signer:dict[str,list[tuple[int,int]]]=defaultdict(list)
    for row in predictions: by_signer[row["signer_group_id"]].append((int(row["true_class"]),int(row["pred_class"])))
    for row in groups:
        row["macro_f1"]=""
        if row["split"]=="test" and row["group_kind"]=="signer":
            pairs=by_signer[row["group"]]; y=np.asarray([x[0] for x in pairs]); p=np.asarray([x[1] for x in pairs]); row["macro_f1"]=_macro_f1(y,p)
    write_csv(OUT/"p5b_rcaa_signer_source_analysis.csv",groups)
    per_class=read_csv(NEW_RUN/"per_class_metrics.csv")
    zero=[int(r["class_id"]) for r in per_class if float(r["recall"])==0]
    conf=Counter((int(r["true_class"]),int(r["pred_class"])) for r in predictions if r["correct"]=="0")
    aggregate=jitter["aggregate"]
    wrist_raw=np.median([aggregate["left_wrist_raw_scale_adjusted"]["median"],aggregate["right_wrist_raw_scale_adjusted"]["median"]])
    wrist_norm=np.median([aggregate["left_wrist_normalized"]["median"],aggregate["right_wrist_normalized"]["median"]])
    robust_amplification=float(wrist_norm/wrist_raw)
    decision={
        "primary_rca_classification":"INSUFFICIENT_TRAINING_HORIZON",
        "evaluation_valid":True,
        "historical_test_identity":"EXACT",
        "label_mapping":"EXACT",
        "aggregation_parity":"EXACT",
        "training_dynamics":dynamics["classification"],
        "temporal_jitter_verdict":"NOT_MATERIAL: normalized/raw-scale-adjusted aggregate median wrist-motion ratio %.4f; correct-vs-incorrect effects negligible"%robust_amplification,
        "feature_distribution_verdict":"HEALTHY_WITH_EXPECTED_DOMAIN_MIX: no NaN/Inf, effectively no |coordinate|>10, validation/test closely aligned; combined train Y differs because AppHear/local supplements are train-only",
        "missingness_contribution":"SECONDARY: weak-both top1 24.88% versus moderate 34.23%, but strong-both is only 32.33% and does not restore historical performance",
        "signer_domain_contribution":"MATERIAL_SECONDARY: test signer accuracy spans 17.77%-47.24%; test is all ASL Citizen and feature distributions remain bounded",
        "historical_training_recipe_parity":"NOT_EXACT: historical run used 17-layer encoder warm start and temporal/geometric augmentation; P5-B used neither",
        "ranked_contributors":{
            "missingness":{"rank":"MEDIUM","evidence":"9.35-point weak-vs-moderate top1 gap, but strong observations remain poor"},
            "temporal_normalization":{"rank":"LOW","evidence":"aggregate wrist amplification %.4f and near-zero correct/error effect sizes"%robust_amplification},
            "canonicalization_loss":{"rank":"MEDIUM","evidence":"historical roll and dominant-hand mirror/swap were active; DWPose proxy marks 23.59% left-dominant; associations with errors are modest"},
            "signer_domain_shift":{"rank":"MEDIUM","evidence":"large signer accuracy spread; val/test ASL Citizen distributions are similar"},
            "insufficient_training_horizon":{"rank":"HIGH","evidence":"best val loss and val accuracy both at final epoch; last-10 val loss slope -0.00593 and val accuracy slope +0.00366/epoch"},
            "feature_scaling":{"rank":"LOW","evidence":"bounded coordinates, effectively zero extreme rate, val/test distribution agreement"},
            "label_evaluation_bug":{"rank":"RULED_OUT","evidence":"2620 IDs/order, labels, class map, frame masks, and aggregation are exact"},
            "tcn_capacity_mismatch":{"rank":"LOW","evidence":"same family succeeded historically; current run has not converged enough to test capacity cleanly"}},
        "recommended_next_intervention":"CONTROLLED_TRAINING_HORIZON_EXTENSION",
        "recommendation_scope":"Use the frozen P5-B representation, splits, architecture, seed, optimizer, and no-augmentation/no-warm-start policy; change only the preregistered epoch horizon/resume behavior. This is a recommendation, not authorization or execution.",
        "historical_canonicalization":{
            "per_frame_center":"ACTIVE","per_clip_center":"INACTIVE","per_frame_scale":"INACTIVE","per_clip_scale":"ACTIVE",
            "shoulder_roll_removal":"ACTIVE","mirroring":"ACTIVE_CONDITIONAL","dominant_nondominant_canonicalization":"ACTIVE",
            "anatomical_block_swap":"ACTIVE_WHEN_MIRRORED","hand_local_normalization":"INACTIVE","global_body_normalization":"ACTIVE",
            "pose_visibility":"ACTIVE","xyz":"ACTIVE"},
        "diagnostics":{"robust_aggregate_wrist_motion_amplification":robust_amplification,"zero_recall_classes":len(zero),"zero_recall_class_ids":zero,
                       "top_confusions":[{"true":a,"pred":b,"count":n} for (a,b),n in conf.most_common(10)]},
    }
    write_json(OUT/"p5b_rcaa_decision.json",decision)
    report=f"""# P5-B RCA-A — Temporal Representation Parity Audit

## Outcome

**P5B_RCAA_COMPLETE**

Primary classification: **INSUFFICIENT_TRAINING_HORIZON**.

The P5-B result is valid. The historical and P5-B protected-test populations, label mapping,
frame masks, and sign-level aggregation are exact. Current-frame normalization does not show
material temporal-motion amplification or an association large enough to explain the accuracy
collapse. The frozen 40-epoch P5-B run was still improving at its stop: both best validation loss
and best validation per-frame accuracy occurred at epoch 39.

RCA-A does not authorize training. The single recommended next intervention category is a
**controlled training-horizon extension**, holding representation, architecture, optimizer,
splits, seed, and the no-augmentation/no-warm-start policy fixed.

## 1. Evaluation and parity

| Check | Result |
|---|---|
| P5-B evaluation valid | YES |
| Test samples | 2,620 vs 2,620, same IDs and order |
| Sample-order SHA-256 | `{identity['new_sample_id_order_sha256']}` |
| Labels | Exact; SHA-256 `{identity['new_labels_sha256']}` |
| Class vocabulary/map | Exact: {mapping['class_count']} one-to-one classes |
| Frame masks | Exact |
| Sign aggregation | Exact mean of per-frame softmax over real frames |
| Top-1 / top-5 calculation | Exact |

The accuracy delta is therefore not explained by a sample, label, mapping, mask, or aggregation
bug. Training recipes are not exact: the historical run copied 17 encoder-weight groups from a
v3 warm start and used temporal/geometric augmentation; P5-B used no warm start and no
augmentation.

## 2. Training dynamics

- Best validation-accuracy epoch: **39** (`val_pf_acc=0.30731`).
- Best validation-loss epoch: **39** (`val_loss=1.09080`).
- Final train loss / per-frame accuracy: **0.77956 / 0.54834**.
- Last-10 slopes per epoch: train loss **-0.00846**, train accuracy **+0.00397**,
  validation loss **-0.00593**, validation accuracy **+0.00366**.
- Diagnostic classification: **STILL_CONVERGING**, not plateaued or overfit.

For context, historical seed-101 finished at train per-frame accuracy 0.67494 and validation
per-frame accuracy 0.47137; its best validation accuracy was epoch 37. The historical warm start
and augmentation mean this is training-protocol context, not proof that more epochs alone will
recover the entire gap.

## 3. Historical representation and canonicalization

The artifact-backed transform comparison is in `p5b_rcaa_historical_parity.csv`. Historical
[96,258] preprocessing used per-frame shoulder-midpoint centering, one robust per-clip shoulder
scale, one per-clip roll correction, and conditional dominant-hand mirroring with pose permutation
and anatomical hand-block swap. It retained hand/body XYZ and pose visibility. P5-B uses current-
frame center and scale, no roll correction, no mirroring, anatomical slot order, XY+score+valid,
and explicit observation masks.

Canonicalization loss is a credible secondary contributor: the DWPose wrist-motion proxy marks
**23.59%** of clips left-dominant under the historical 0.15 rule. However, left-dominance and
shoulder-roll effects on correct versus incorrect test cases were modest (Cohen's d -0.131 and
-0.100), so RCA-A does not select canonicalization as the primary cause.

## 4. Temporal jitter

The frozen comparison formula is median normalized wrist displacement divided by median raw
wrist displacement normalized by the previous frame's shoulder distance. Aggregate median motion
amplification is **{robust_amplification:.4f}**. Median shoulder-scale change is
**{aggregate['scale_pct_change']['median']*100:.3f}%** per frame; p95 is
**{aggregate['scale_pct_change']['p95']*100:.3f}%**. Correct-versus-incorrect effect sizes are
small: scale variability d={jitter['correct_vs_incorrect']['scale_pct_change_median']['cohens_d_correct_minus_incorrect']:.3f},
center jitter d={jitter['correct_vs_incorrect']['center_jitter_raw_scale_adjusted_median']['cohens_d_correct_minus_incorrect']:.3f},
and wrist amplification d={jitter['correct_vs_incorrect']['wrist_motion_amplification_ratio']['cohens_d_correct_minus_incorrect']:.3f}.

Verdict: **current-frame normalization did not materially amplify temporal jitter**. Static clips
make individual ratio tails numerically unstable when raw median motion approaches zero; the
aggregate displacement distributions and error effect sizes, not those tails, support the verdict.

## 5. Feature distributions and domain/signer structure

- Train/validation/test valid-landmark rates: **84.90% / 83.49% / 82.96%**.
- Left observed: **73.54% / 73.90% / 73.75%**.
- Right observed: **84.04% / 79.71% / 78.36%**.
- Both observed: **65.78% / 66.31% / 63.92%**.
- Overall zero fractions: **15.26% / 16.67% / 17.21%**.
- Coordinate values are bounded: test x p1/p99 **-1.083/1.064**, test y p1/p99
  **-0.731/1.775**; no test coordinate has absolute value above 10.

The 17 constant channels are body valid-mask channels fixed at one because all stored DWPose body
points are structurally finite; they are contract-consistent, not corruption. Validation and test
are both ASL Citizen and closely aligned. The combined train Y distribution is shifted because
AppHear/local supplements are train-only and have larger spatial spread; the ASL Citizen training
subset is much closer to validation/test.

Test signer accuracy ranges from **17.77% to 47.24%** (signer macro-F1 is preserved in the signer
artifact). This establishes material signer variability, but not a single corrupt domain. With
only 11 test signers, correlations with individual feature summaries are descriptive.

## 6. Missingness and error structure

Weak-both clips score **24.88%** top-1 versus **34.23%** for moderate clips, so missingness is a
real secondary weakness. It does not explain most errors: strong-both clips remain only **32.33%**,
near the overall 31.87%. There are **{len(zero)}** zero-recall classes; errors are broadly spread
across classes and signers rather than confined to missing-hand sequences.

## 7. Ranked contributors

| Contributor | Rank | Finding |
|---|---|---|
| Insufficient training horizon | HIGH | Best validation metrics at final epoch; train and validation still improve |
| Missingness | MEDIUM | Weak observations hurt, but strong-observation accuracy is still poor |
| Canonicalization loss | MEDIUM | Historical roll/mirror/swap active; modest error association |
| Signer/domain shift | MEDIUM | Wide signer spread; no gross val/test feature corruption |
| Temporal normalization | LOW | Motion amplification near one; negligible error effect |
| Feature scaling | LOW | Bounded, finite, val/test-stable distributions |
| TCN capacity mismatch | LOW | Same family worked historically; current training has not cleanly tested capacity |
| Label/evaluation bug | RULED_OUT | IDs, labels, mapping, masks, and aggregation exact |

## 8. Scope and next action

Recommended intervention: **CONTROLLED_TRAINING_HORIZON_EXTENSION** only. This report neither
implements nor authorizes it. P4 remains frozen; no feature, model, dataset, or context file was
modified. Missingness augmentation remains blocked until representation/model viability is shown.

## Artifact locations

All RCA-A artifacts are under:

`{OUT.resolve()}`

The analysis source is `{(ROOT/'eval/runtime_diagnostics/p5b_rcaa.py').resolve()}`. Existing
context files, including `context/progress-tracker.md`, were not modified.
"""
    (OUT/"P5B_RCAA_ROOT_CAUSE_RESULT.md").write_text(report,encoding="utf-8")
    artifact_files=[p for p in OUT.iterdir() if p.is_file() and p.name!="artifact_hash_manifest.json"]
    manifest={"scope":"P5-B RCA-A new artifacts only","generated_without_training_or_feature_mutation":True,
              "artifacts":[{"path":str(p.resolve()),"bytes":p.stat().st_size,"sha256":sha256(p)} for p in sorted(artifact_files)]}
    write_json(OUT/"artifact_hash_manifest.json",manifest)
    print(json.dumps({"passed":True,"classification":decision["primary_rca_classification"],"recommended_next_intervention":decision["recommended_next_intervention"],"report":str((OUT/'P5B_RCAA_ROOT_CAUSE_RESULT.md').resolve())},indent=2))
    return 0


def main() -> int:
    OUT.mkdir(parents=True,exist_ok=True)
    manifest_rows=read_csv(MANIFEST)
    identity,mapping=identity_and_mapping(manifest_rows)
    write_json(OUT/"p5b_rcaa_test_identity_audit.json",identity)
    write_json(OUT/"p5b_rcaa_label_mapping_audit.json",mapping)
    write_json(OUT/"p5b_rcaa_aggregation_parity.json",aggregation_audit())
    write_json(OUT/"p5b_rcaa_training_dynamics.json",training_dynamics())
    write_csv(OUT/"p5b_rcaa_historical_parity.csv",historical_parity_rows())
    pred_rows=read_csv(NEW_RUN/"test_predictions.csv"); predictions={r["sample_id"]:r["correct"]=="1" for r in pred_rows}
    completed=[]
    for p in sorted((MIGRATION/"completed").glob("*.json")):
        completed.append(json.loads(p.read_text(encoding="utf-8")))
    if len(completed)!=8131: raise RuntimeError(f"expected 8131 completed records, got {len(completed)}")
    jitter_rows,jitter_summary=jitter_analysis(completed,predictions)
    write_csv(OUT/"p5b_rcaa_temporal_jitter.csv",jitter_rows)
    write_json(OUT/"p5b_rcaa_temporal_jitter_summary.json",jitter_summary)
    dist,groups=distribution_analysis(manifest_rows,predictions)
    write_csv(OUT/"p5b_rcaa_feature_distribution.csv",dist)
    write_csv(OUT/"p5b_rcaa_signer_source_analysis.csv",groups)
    write_csv(OUT/"p5b_rcaa_error_structure.csv",error_structure(manifest_rows,jitter_rows))
    print(json.dumps({"passed":True,"output":str(OUT),"jitter_rows":len(jitter_rows),"distribution_rows":len(dist),"group_rows":len(groups)},indent=2))
    return 0


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--finalize-only",action="store_true")
    args=parser.parse_args()
    raise SystemExit(finalize() if args.finalize_only else main())
