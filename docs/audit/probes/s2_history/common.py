"""Shared, read-only loaders for the S2 history-dependence investigation.

Nothing here writes to the repository or artifacts. All paths are inputs.
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

ROOT = Path("F:/ASL DATASET/5. Apphear3")
ART = ROOT / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
STAGE2 = Path("C:/Users/Gigabyte/.codex/worktrees/recognition-v3-stage2/5. Apphear3")

S2R2_DIR = ART / "s2_r2_continuous_domain_correction_01/main_candidate"
P7_DIR = ART / "phase7_production_cadence_aligned_segmenter_01"
S2R2_TFLITE = STAGE2 / "android/app/src/main/assets/phone_causal_recognition_01/s2_r2_candidate/s2_r2_fp32.tflite"

SESSIONS = {
    # name: (capture dir, label kind, role)
    "SEP27_TRANSITION": (ART / "continuous_transition_readiness_01/device_capture/session_20260927T162103Z",
                         "boundaries", "design signer, reviewed in prior audits"),
    "OCT15_COMPACT": (ROOT / "artifacts/recognition_v3_stage2_compact_device/finalized/session_20261015T155027Z",
                      "boundaries", "design signer (nonexpert), reviewed in prior audits"),
    "SEP23_INDEPENDENT": (ROOT / "phone_pull_s2_r2_independent_validation/session_20260923T013439Z",
                          "attempts", "distinct signer, untouched validation"),
    "SEP23_REPRESENTATIVE": (ROOT / "phone_pull_s2_r2_representative_final_validation/session_20260923T030939Z",
                             "attempts", "distinct signer, untouched validation"),
}
REVIEW = ART / "s2_r2_phone_deployment_and_independent_validation_01"

PRE, ACTIVE, POST, IGNORE = 0, 1, 2, -1


def softmax(z):
    z = np.asarray(z, np.float64)
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


@dataclass
class Model:
    name: str
    keras: object
    mean: np.ndarray
    std: np.ndarray

    def normalize(self, features):
        return ((np.asarray(features, np.float32) - self.mean) / self.std).astype(np.float32)

    def probs(self, normalized):
        """Causal full-sequence pass. With RF=61 this equals the rolling-61 runtime."""
        x = np.asarray(normalized, np.float32)[None]
        return softmax(np.asarray(self.keras(x, training=False))[0])


def load_models():
    import tensorflow as tf

    out = {}
    n = json.load(open(S2R2_DIR / "normalization.json", encoding="utf-8"))
    out["S2_R2"] = Model("S2_R2", tf.keras.models.load_model(S2R2_DIR / "best_model.keras", compile=False),
                         np.asarray(n["mean"], np.float32), np.asarray(n["std"], np.float32))
    p = json.load(open(P7_DIR / "cadence_aligned_normalization_stats.json", encoding="utf-8"))
    out["PHASE7"] = Model("PHASE7", tf.keras.models.load_model(P7_DIR / "best_model.keras", compile=False),
                          np.asarray(p["mean"], np.float32), np.asarray(p["std"], np.float32))
    return out


@dataclass
class Session:
    name: str
    role: str
    features: np.ndarray          # raw 378 (Android-computed)
    normalized_s2r2: np.ndarray   # Android-normalized (S2-R2 stats)
    timestamps_ms: np.ndarray
    android_probs: np.ndarray
    history_length: np.ndarray
    positives: list = field(default_factory=list)   # dicts: name, a, b (row indices, inclusive), active_rows
    negatives: list = field(default_factory=list)   # dicts: name, a, b


def load_session(name):
    path, kind, role = SESSIONS[name]
    p = path / "s2_exact_parity"
    n = len(np.fromfile(p / "source_index.i32", dtype=np.int32))
    src = np.fromfile(p / "source_index.i32", dtype=np.int32)
    s = Session(
        name=name, role=role,
        features=np.fromfile(p / "android_features.f32", dtype=np.float32).reshape(n, 378),
        normalized_s2r2=np.fromfile(p / "android_normalized.f32", dtype=np.float32).reshape(n, 378),
        timestamps_ms=np.fromfile(p / "timestamp_ms.f64", dtype=np.float64),
        android_probs=np.fromfile(p / "android_probabilities.f32", dtype=np.float32).reshape(n, 3),
        history_length=np.fromfile(p / "history_length.i32", dtype=np.int32),
    )
    pos = {int(v): i for i, v in enumerate(src)}
    if kind == "boundaries":
        lab = json.load(open(path / "transition_review/human_boundaries.json", encoding="utf-8"))
        for x in lab["signs"]:
            if x["start_index"] is None:
                continue
            a, b = pos[x["start_index"]], pos[x["end_index"]]
            s.positives.append({"name": f"{x['condition']}:{x['gloss']}#{x['ordinal']}",
                                "judgment": x["judgment"], "a": a, "b": b,
                                "active_rows": list(range(a, b + 1))})
        for x in lab.get("negative_intervals", []):
            if x["start_index"] is not None and x["judgment"] == "CONFIRMED_NON_SIGN":
                s.negatives.append({"name": x["block"], "a": pos[x["start_index"]], "b": pos[x["end_index"]]})
    else:
        review = REVIEW / path.name / "blinded_human_review"
        ts_ns = np.round(s.timestamps_ms * 1e6).astype(np.int64)
        by_ts = {int(t): i for i, t in enumerate(ts_ns)}
        rows = list(csv.DictReader(open(review / "phone_positive_observation_labels.csv", encoding="utf-8")))
        attempts = {}
        for r in rows:
            t = int(r["source_timestamp_ns"])
            i = by_ts.get(t)
            if i is None:  # tolerate float rounding of ms timestamps
                k = int(np.argmin(np.abs(ts_ns - t)))
                if abs(int(ts_ns[k]) - t) > 2000:
                    raise ValueError(f"unmatched timestamp {name} {t}")
                i = k
            attempts.setdefault(r["attempt_id"], []).append((i, int(r["state_id"]), r["expected_gloss"]))
        for att, lst in sorted(attempts.items()):
            act = [i for i, st, _ in lst if st == ACTIVE]
            if not act:
                continue
            s.positives.append({"name": f"{att}:{lst[0][2]}", "judgment": "GENUINE_SIGN",
                                "a": min(act), "b": max(act), "active_rows": act,
                                "attempt_a": min(i for i, _, _ in lst), "attempt_b": max(i for i, _, _ in lst)})
        nr = json.load(open(review / "non_sign_visual_review.json", encoding="utf-8"))
        for k, x in enumerate(nr["confirmed_non_sign_intervals"]):
            s.negatives.append({"name": f"NONSIGN_{k + 1}", "a": pos[x["start_index"]], "b": pos[x["end_index"]]})
    return s


def phase7_dev_views():
    m = json.load(open(P7_DIR / "sparse_view_manifest.json", encoding="utf-8"))
    out = []
    for r in m["rows"]:
        if r["phase7_partition"] != "DEV":
            continue
        z = np.load(r["feature_path"], allow_pickle=False)
        out.append({"key": r["view_key"], "signer": r["signer_id"], "source": r["source"],
                    "view": r["view_id"], "features": z["features"].astype(np.float32),
                    "labels": z["labels"].astype(np.int64), "timestamps_ms": z["timestamps_ms"]})
    return out


def s2r2_rows(domain=None, role=None):
    m = json.load(open(S2R2_DIR / "dataset_manifest.json", encoding="utf-8"))
    out = []
    for r in m["rows"]:
        if domain and r["domain"] != domain:
            continue
        if role and r["role"] != role:
            continue
        z = np.load(r["feature_path"], allow_pickle=False)
        out.append({"row_id": r["row_id"], "domain": r["domain"], "role": r["role"],
                    "signer": r["signer_id"], "features": z["features"].astype(np.float32),
                    "labels": z["labels"].astype(np.int64), "timestamps_ms": z["timestamps_ms"]})
    return out


# ---------------- faithful port of PhoneCausalEventProducer (PRE_OR_POST, PASS_THROUGH) -------------
class Decoder:
    MIN_ACTIVE, PRE_GAP, POST_CONFIRM, REARM, MAX_GAP = 133.308, 133.308, 266.616, 399.924, 533.232

    def __init__(self):
        self.state = "IDLE"
        self.last_t = None
        self.events = []
        self.idx = 0
        self._clear()
        self.rearm_start = None

    def _clear(self):
        self.c_start_i = self.c_start_t = self.last_act_i = self.last_act_t = None
        self.pre_gap_t = self.post_i = self.post_t = None

    def consume(self, t, s):
        i = self.idx
        self.idx += 1
        gap = None if self.last_t is None else t - self.last_t
        self.last_t = t
        st = self.state
        if st == "IDLE":
            if s == ACTIVE:
                self._clear()
                self.c_start_i, self.c_start_t, self.last_act_i, self.last_act_t = i, t, i, t
                self.state = "ACTIVE_CANDIDATE"
        elif st == "ACTIVE_CANDIDATE":
            if s == ACTIVE:
                self.last_act_i, self.last_act_t = i, t
            elif s == POST:
                self.post_i, self.post_t, self.pre_gap_t, self.state = i, t, None, "POST_CANDIDATE"
            else:
                self.pre_gap_t, self.state = t, "PRE_GAP"
        elif st == "PRE_GAP":
            el = t - self.pre_gap_t
            if s == ACTIVE and el < self.PRE_GAP:
                self.last_act_i, self.last_act_t, self.pre_gap_t, self.state = i, t, None, "ACTIVE_CANDIDATE"
            elif s == POST and el < self.PRE_GAP:
                self.post_i, self.post_t, self.pre_gap_t, self.state = i, t, None, "POST_CANDIDATE"
            elif el >= self.PRE_GAP:
                self._clear()
                self.state = "IDLE"
        elif st == "POST_CANDIDATE":
            el = t - self.post_t
            if s == ACTIVE:
                self.last_act_i, self.last_act_t, self.post_i, self.post_t = i, t, None, None
                self.state = "ACTIVE_CANDIDATE"
            elif el >= self.POST_CONFIRM:
                if self.last_act_t - self.c_start_t < self.MIN_ACTIVE:
                    self._clear()
                    self.state = "IDLE"
                else:
                    self.events.append({"start": self.c_start_i, "end": self.last_act_i, "commit": i})
                    self._clear()
                    self.state = "WAIT"
                    self.rearm_start = t if s in (PRE, POST) else None
        elif st == "WAIT":
            if gap is not None and gap > self.MAX_GAP:
                self.rearm_start = t if s in (PRE, POST) else None
            elif s == ACTIVE:
                self.rearm_start = None
            else:
                if self.rearm_start is None:
                    self.rearm_start = t
                elif t - self.rearm_start >= self.REARM:
                    self.rearm_start = None
                    self.state = "IDLE"
        return self.state


def decode(timestamps, states):
    d = Decoder()
    for t, s in zip(timestamps, states):
        d.consume(float(t), int(s))
    return d.events
