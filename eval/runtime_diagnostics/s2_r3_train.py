"""S2-R3 Arm A: stitched continuous-stream builder and trainer (plan build steps 3-5).

Data (real raw-v1 observations only; no duplicated, interpolated or synthetic holds):
  - Phase-7 sign clips, FIT/CAL by the frozen signer-grouped split, each at its Phase-7 cadence
    view (133/200/267 ms) with its own human-derived PRE/ACTIVE/POST/ignore labels;
  - hands-visible P1 negatives (reviewed intervals) and N0 negatives (1 s review exclusion),
    participant-grouped, resampled to the stream's cadence with a random phase;
  - unstitched FIT rows kept: Phase-7 views, S2-R2 enrichment rows, exact phone positives, P1 rows;
  - the design-signer phone stream 20260920T145710Z (FIT): PRE only inside the 15 confirmed
    non-sign event windows, IGNORE elsewhere, chunked at native cadence.
Streams join segments at the raw level and recompute the 378 features over the joined sequence;
the first observations after each join are IGNORE. Grammar: isolated clip pairs, direct sign->sign
(previous clip cut 0-6 observations after its last ACTIVE, next starting <=1 before its ACTIVE) and
sign->negative->sign, so POST->ACTIVE, POST->PRE and ACTIVE beyond position 61 all occur (D2:
POST is each clip's own bounded recovery tail).
Model, contract, optimizer and seed follow D6; selection follows D7 on CAL only. Nothing in
Android, the frozen S2-R2 package or any gate input changes.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics.phase5_1t_first_segmenter import (  # noqa: E402
    IGNORE_LABEL,
    build_model,
    softmax,
)
from eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter import (  # noqa: E402
    subset_raw,
)
from eval.runtime_diagnostics.s2_r3_data_split import FREEZE_PATH as SPLIT_PATH  # noqa: E402
from pipeline.perception_vnext.recognition_schema import (  # noqa: E402
    RawSequence,
    load_raw_sequence,
    select_nearest_unique,
)
from pipeline.perception_vnext.recognition_window_materializer import (  # noqa: E402
    LogicalSignEvent,
    materialize_recognition_window,
)
from pipeline.perception_vnext.segmentation.learned_features import (  # noqa: E402
    FEATURE_WIDTH,
    apply_normalization,
    normalization_from_train,
)
from pipeline.perception_vnext.segmentation.streaming_decoder import (  # noqa: E402
    CausalStreamingSignEventDecoder,
)

CONFIG_PATH = ROOT / "model/config/recognition_upgrade/s2_r3_train_01.json"
RU = Path("artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01")
PHASE7 = RU / "phase7_production_cadence_aligned_segmenter_01"
S2R2_MANIFEST = RU / "s2_r2_continuous_domain_correction_01/main_candidate/dataset_manifest.json"
N0_MANIFEST = RU / "s2_r3_n0_raw_01/manifest.json"
NEG_MANIFEST = RU / "s2_r3_negative_raw_01/manifest.json"
PRE, ACTIVE, POST = 0, 1, 2
# Training-only target (train_07): "not ACTIVE, PRE or POST both correct" for hands-visible
# external negatives, scored as -log(p_PRE + p_POST). Never a runtime state.
NON_ACTIVE = 3
NEGATIVE_KIND, SIGN_KIND = 0, 1


# ----------------------------------------------------------------------------- sources
def load_sources(root: Path) -> dict[str, Any]:
    split = suite.read_json(SPLIT_PATH)
    role_of = {p["sample_id"]: p["role"] for p in split["positives"]}
    signer_role = {p["signer"]: p["role"] for p in split["positives"]}
    manifest = suite.read_json(root / PHASE7 / "sparse_view_manifest.json")
    raw_cache: dict[str, RawSequence] = {}
    clips: dict[str, dict[str, list[dict[str, Any]]]] = {
        "FIT": defaultdict(list),
        "CAL": defaultdict(list),
    }
    for row in manifest["rows"]:
        role = role_of.get(row["sample_id"])
        if row["phase7_partition"] not in ("FIT", "CAL") or role is None:
            continue
        path = str(row["source_raw_path"])
        if path not in raw_cache:
            if suite.sha256(Path(path)) != row["source_raw_sha256"]:
                raise ValueError(f"[s2_r3/train] RAW_HASH:{row['sample_id']}")
            raw_cache[path] = load_raw_sequence(Path(path))
        with np.load(row["feature_path"], allow_pickle=False) as data:
            selected = np.asarray(data["selected_indices"], np.int32)
            labels = np.asarray(data["labels"], np.int32)
            stored = np.asarray(data["features"], np.float32)
        if not np.any(labels == ACTIVE):
            continue
        clips[role][row["view_id"]].append(
            {
                "sample_id": row["sample_id"],
                "signer": row["signer_id"],
                "view": row["view_id"],
                "raw": subset_raw(raw_cache[path], selected),
                "labels": labels,
                "features": stored,
            }
        )
    negatives: dict[str, list[dict[str, Any]]] = {"FIT": [], "CAL": []}
    for clip in suite.read_json(root / N0_MANIFEST)["clips"]:
        if clip["role"] in negatives:
            raw = load_raw_sequence(root / clip["raw_path"])
            excluded = [float(x["timestamp_ms"]) for x in clip["excluded_review_samples"]]
            negatives[clip["role"]].append(
                {"family": "N0", "id": clip["clip_id"], "raw": raw, "excluded_ms": excluded}
            )
    neg_manifest = suite.read_json(root / NEG_MANIFEST)
    phone_stream = None
    for source in neg_manifest["sources"]:
        raw = load_raw_sequence(root / source["raw_path"])
        if source["family"] == "P1_NEGATIVE" and source["role"] in negatives:
            negatives[source["role"]].append(
                {"family": "P1", "id": source["source_id"], "raw": raw, "excluded_ms": []}
            )
        elif source["family"] == "PHONE_DESIGN_NEGATIVE_STREAM":
            phone_stream = {
                "raw": raw,
                "labels": np.load(root / source["labels_path"]).astype(np.int32),
                "role": source["role"],
            }
    s2r2 = suite.read_json(root / S2R2_MANIFEST)["rows"]
    p1_role = {item["participant"]: item["role"] for item in split["p1_negatives"]}
    unstitched: dict[str, list[dict[str, Any]]] = {"FIT": [], "CAL": []}
    for row in s2r2:
        domain = row["domain"]
        if domain == "ENRICHMENT_SIGN":
            role, family = signer_role.get(row["signer_id"]), "ENRICHMENT_SIGN"
        elif domain == "PHONE_POSITIVE":
            role, family = split["phone_positive_design_signer"]["role"], "PHONE_POSITIVE"
        elif domain == "P1_NEGATIVE":
            role, family = p1_role[row["signer_id"]], "P1_NEGATIVE"
        else:
            continue  # Phase-7 views are taken directly from Phase-7 above
        if role not in unstitched:
            continue
        with np.load(row["feature_path"], allow_pickle=False) as data:
            unstitched[role].append(
                {
                    "row_id": row["row_id"],
                    "domain": family,
                    "features": np.asarray(data["features"], np.float32),
                    "labels": np.asarray(data["labels"], np.int32),
                    "timestamps_ms": np.asarray(data["timestamps_ms"], np.float64),
                }
            )
    return {
        "clips": clips,
        "negatives": negatives,
        "phone_stream": phone_stream,
        "unstitched": unstitched,
    }


# ----------------------------------------------------------------------------- streams
def negative_block(
    neg: dict[str, Any], interval: float, length: int, radius: float, rng: np.random.Generator
) -> tuple[RawSequence, np.ndarray]:
    t = np.asarray(neg["raw"].timestamp_ms, np.float64)
    targets = np.arange(t[0] + rng.uniform(0.0, interval), t[-1], interval)
    indices = select_nearest_unique(t, targets)
    if len(indices) > length:
        start = int(rng.integers(0, len(indices) - length + 1))
        indices = indices[start : start + length]
    part = subset_raw(neg["raw"], np.asarray(indices, np.int32))
    labels = np.full(len(indices), PRE, np.int32)
    for excluded in neg["excluded_ms"]:
        labels[np.abs(t[indices] - excluded) <= radius] = IGNORE_LABEL
    return part, labels


def build_stream(
    sources: dict[str, Any], role: str, config: dict[str, Any], rng: np.random.Generator
) -> dict[str, Any]:
    spec = config["streams"]
    view = str(rng.choice(sorted(config["views"])))
    interval = float(config["views"][view])
    pool = sources["clips"][role][view]
    by_signer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for clip in pool:
        by_signer[clip["signer"]].append(clip)
    signer = str(rng.choice(sorted(by_signer)))
    negs = sources["negatives"][role]
    families = {f: [n for n in negs if n["family"] == f] for f in ("P1", "N0")}
    mix = spec["negative_family_mix"]
    target = int(rng.integers(spec["length_range"][0], spec["length_range"][1] + 1))
    transitions = list(spec["transition_mix"])
    weights = np.asarray([spec["transition_mix"][k] for k in transitions], np.float64)

    def pick_negative() -> dict[str, Any]:
        family = "P1" if rng.random() < mix["P1"] else "N0"
        options = families[family] or negs
        return options[int(rng.integers(len(options)))]

    def pick_clip() -> dict[str, Any]:
        own = by_signer[signer]
        options = own if own and rng.random() < 0.7 else pool
        return options[int(rng.integers(len(options)))]

    parts: list[RawSequence] = []
    labels: list[np.ndarray] = []
    kinds: list[np.ndarray] = []
    ordinals: list[np.ndarray] = []
    families_rows: list[np.ndarray] = []
    spec_log: list[str] = []
    total = 0
    lo, hi = spec["negative_block_range"]
    if rng.random() < spec["start_with_negative_probability"]:
        neg = pick_negative()
        part, lab = negative_block(
            neg, interval, int(rng.integers(lo, hi + 1)), float(spec["n0_exclusion_radius_ms"]), rng
        )
        parts.append(part)
        labels.append(lab)
        kinds.append(np.full(len(lab), NEGATIVE_KIND))
        ordinals.append(np.full(len(lab), -1))
        families_rows.append(np.full(len(lab), neg["family"]))
        spec_log.append(f"NEG:{neg['id']}")
        total += len(lab)
    ordinal = 0
    transition_in = "ISOLATED"
    while total < target:
        clip = pick_clip()
        lab = clip["labels"]
        active = np.flatnonzero(lab == ACTIVE)
        transition_out = str(rng.choice(transitions, p=weights / weights.sum()))
        first = max(0, int(active[0]) - 1) if transition_in == "DIRECT" else 0
        if transition_out == "DIRECT":
            keep = int(
                rng.integers(
                    spec["direct_post_keep_range"][0], spec["direct_post_keep_range"][1] + 1
                )
            )
            last = min(len(lab) - 1, int(active[-1]) + keep)
        else:
            last = len(lab) - 1
        indices = np.arange(first, last + 1, dtype=np.int32)
        parts.append(subset_raw(clip["raw"], indices))
        labels.append(lab[indices].copy())
        kinds.append(np.full(len(indices), SIGN_KIND))
        ordinals.append(np.full(len(indices), ordinal))
        families_rows.append(np.full(len(indices), ""))
        spec_log.append(
            f"SIGN:{clip['sample_id']}[{first}:{last}]:{transition_in}->{transition_out}"
        )
        total += len(indices)
        ordinal += 1
        if transition_out == "VIA_NEGATIVE" and total < target:
            neg = pick_negative()
            part, nlab = negative_block(
                neg,
                interval,
                int(rng.integers(lo, hi + 1)),
                float(spec["n0_exclusion_radius_ms"]),
                rng,
            )
            parts.append(part)
            labels.append(nlab)
            kinds.append(np.full(len(nlab), NEGATIVE_KIND))
            ordinals.append(np.full(len(nlab), -1))
            families_rows.append(np.full(len(nlab), neg["family"]))
            spec_log.append(f"NEG:{neg['id']}")
            total += len(nlab)
        transition_in = transition_out
    join = int(spec["join_ignore_observations"])
    for k in range(1, len(labels)):
        labels[k][:join] = IGNORE_LABEL
    raw = suite.concat_raw(parts, interval)
    label = np.concatenate(labels)
    limit = int(spec["length_range"][1])
    features = suite.features_for_raw(raw, "v1")[:limit]
    return {
        "domain": "STITCHED_STREAM",
        "view": view,
        "features": features,
        "labels": label[:limit],
        "kinds": np.concatenate(kinds)[:limit],
        "ordinals": np.concatenate(ordinals)[:limit],
        "timestamps_ms": np.asarray(raw.timestamp_ms, np.float64)[:limit],
        "segments": spec_log,
        # Added for event-level reliability analysis (no RNG use; streams are unchanged).
        "raw": suite.slice_raw(raw, 0, min(limit, len(label)) - 1),
        "negative_family": np.concatenate(families_rows)[:limit],
    }


def grammar_audit(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        valid = [(i, int(v)) for i, v in enumerate(row["labels"]) if v != IGNORE_LABEL]
        for (_, a), (_, b) in zip(valid, valid[1:], strict=False):
            if a != b:
                counts[f"{['PRE', 'ACTIVE', 'POST'][a]}->{['PRE', 'ACTIVE', 'POST'][b]}"] += 1
        counts["ACTIVE_at_position_ge_61"] += int(np.sum(np.asarray(row["labels"][61:]) == ACTIVE))
    return dict(sorted(counts.items()))


def body_dropout(stream: dict[str, Any], p: float, rng: np.random.Generator) -> dict[str, Any]:
    """Remove all body evidence on randomly chosen whole segments (runs of equal kind/ordinal)
    and recompute the causal features. Labels, kinds and timing are unchanged."""
    kinds, ordinals = stream["kinds"], stream["ordinals"]
    change = np.flatnonzero((np.diff(kinds) != 0) | (np.diff(ordinals) != 0)) + 1
    raw = stream["raw"]
    keep = np.ones(len(raw.timestamp_ms), bool)
    for a, b in zip(np.r_[0, change], np.r_[change, len(kinds)], strict=True):
        if rng.random() < p:
            keep[a:b] = False
    if keep.all():
        return stream
    drop = ~keep
    body_xy, body_support = raw.body_xy.copy(), raw.body_support.copy()
    body_valid, body_available = raw.body_valid.copy(), raw.body_available.copy()
    body_xy[drop] = 0
    body_support[drop] = 0
    body_valid[drop] = False
    body_available[drop] = False
    new_raw = dataclasses.replace(
        raw,
        body_xy=body_xy,
        body_support=body_support,
        body_valid=body_valid,
        body_available=body_available,
    )
    features = suite.features_for_raw(new_raw, "v1")[: len(stream["labels"])]
    return {**stream, "raw": new_raw, "features": features, "body_dropped_rows": int(drop.sum())}


def ipn_negative_sources(root: Path, spec: dict[str, Any], role: str) -> list[dict[str, Any]]:
    """IPN Hand NOG intervals (>= min_ms, rows >= margin from any gesture) of `role` subjects."""
    from eval.runtime_diagnostics import ipn_hand_feasibility as ipn

    roles = suite.read_json(ROOT / spec["split"])["roles"]  # repo-relative config
    out = []
    for path in sorted((root / ipn.IPN / "raw_v1").glob("*.npz")):
        raw = load_raw_sequence(path)
        video = str(raw.metadata["sample_id"]).split(":", 1)[1]
        if roles[ipn.subject_of(video)] != role:
            continue
        t = np.asarray(raw.timestamp_ms, np.float64)
        cls = ipn.row_classes(t, ipn.hands_segments(root, video), float(spec["margin_ms"]))
        nog = np.flatnonzero(cls == ipn.NOG)
        for run in np.split(nog, np.flatnonzero(np.diff(nog) > 1) + 1) if len(nog) else []:
            if len(run) and t[run[-1]] - t[run[0]] >= float(spec["min_nog_ms"]):
                out.append(
                    {
                        "family": "IPN",
                        "id": f"ipn:{video}:{int(run[0])}",
                        "raw": subset_raw(raw, run.astype(np.int32)),
                        "excluded_ms": [],
                    }
                )
    if not out:
        raise ValueError(f"[s2_r3/train] NO_IPN_NEGATIVES:{role}")
    return out


def augment_fit_streams(
    root: Path, sources: dict[str, Any], config: dict[str, Any], base: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """train_04/05: extra IPN-negative streams and/or body dropout, each with its own RNG so the
    base FIT and CAL streams stay identical to the Arm A recipe."""
    aug = config.get("augment")
    if not aug:
        return base
    streams = list(base)
    ipn = aug.get("ipn_streams")
    if ipn:
        negatives = ipn_negative_sources(root, ipn, "FIT")
        rng_i = np.random.default_rng(int(config["seed"]) + 23)
        extra_sources = {**sources, "negatives": {"FIT": negatives, "CAL": []}}
        for _ in range(int(ipn["count"])):
            stream = build_stream(extra_sources, "FIT", config, rng_i)
            stream["domain"] = "STITCHED_IPN"
            if ipn.get("negative_label") == "NON_ACTIVE":
                rows = (
                    (stream["kinds"] == NEGATIVE_KIND)
                    & (stream["negative_family"] == "IPN")
                    & (stream["labels"] == PRE)
                )
                stream["labels"] = np.where(rows, NON_ACTIVE, stream["labels"]).astype(np.int32)
            streams.append(stream)
    p = float(aug.get("body_dropout", 0.0))
    if p > 0:
        rng_b = np.random.default_rng(int(config["seed"]) + 11)
        streams = [body_dropout(s, p, rng_b) for s in streams]
    return streams


def build_dataset(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    sources = load_sources(root)
    rng = np.random.default_rng(int(config["seed"]))
    streams = {
        role: [build_stream(sources, role, config, rng) for _ in range(int(config["streams"][key]))]
        for role, key in (("FIT", "fit_count"), ("CAL", "cal_count"))
    }
    fit_streams = augment_fit_streams(root, sources, config, streams["FIT"])
    fit: list[dict[str, Any]] = list(fit_streams)
    for view_clips in sources["clips"]["FIT"].values():
        fit += [
            {"domain": "PHASE7_SIGN", "features": c["features"], "labels": c["labels"]}
            for c in view_clips
        ]
    fit += sources["unstitched"]["FIT"]
    phone = sources["phone_stream"]
    if phone is not None and phone["role"] == "FIT":
        features = suite.features_for_raw(phone["raw"], "v1")
        chunk, stride = (
            config["phone_design_stream"]["chunk"],
            config["phone_design_stream"]["stride"],
        )
        for start in range(0, len(features), stride):
            lab = phone["labels"][start : start + chunk]
            if np.any(lab != IGNORE_LABEL):
                fit.append(
                    {
                        "domain": "PHONE_DESIGN_NEGATIVE",
                        "features": features[start : start + chunk],
                        "labels": lab,
                    }
                )
    reviewed = config.get("phone_reviewed_fit")
    if reviewed:
        fit += phone_reviewed_rows(root, reviewed, config.get("holdout_session"))
    cal_isolated = [c for view_clips in sources["clips"]["CAL"].values() for c in view_clips]
    return {
        "fit": fit,
        "cal_streams": streams["CAL"],
        "cal_isolated": cal_isolated,
        "audit": {
            "fit_rows_by_domain": dict(Counter(r["domain"] for r in fit)),
            "fit_stream_grammar": grammar_audit(streams["FIT"]),
            "cal_stream_grammar": grammar_audit(streams["CAL"]),
            "cal_isolated_views": len(cal_isolated),
            "fit_signers": sorted(
                {c["signer"] for v in sources["clips"]["FIT"].values() for c in v}
            ),
            "cal_signers": sorted(
                {c["signer"] for v in sources["clips"]["CAL"].values() for c in v}
            ),
            "negatives": {
                role: dict(Counter(n["family"] for n in sources["negatives"][role]))
                for role in ("FIT", "CAL")
            },
            "fit_stream_observations": int(sum(len(s["labels"]) for s in streams["FIT"])),
        },
    }


def phone_reviewed_rows(
    root: Path, spec: dict[str, Any], holdout: str | None
) -> list[dict[str, Any]]:
    """Reviewed phone sessions as FIT rows (train_03; leave-one-session-out capable).

    Labels at native cadence: PRE inside confirmed non-sign intervals, ACTIVE on reviewed genuine
    sign rows, IGNORE everywhere else (unreviewed, uncertain, edges within `edge_ignore` rows of a
    sign). The held-out session contributes nothing.
    """
    from eval.runtime_diagnostics import event_reliability as er

    sessions = er.phone_sessions(root)
    rows: list[dict[str, Any]] = []
    edge = int(spec.get("edge_ignore", 1))
    for name in spec["sessions"]:
        if name == holdout:
            continue
        session = sessions[name]
        labels = np.full(len(session["timestamps_ms"]), IGNORE_LABEL, np.int32)
        for n in session["negatives"]:
            labels[n["first"] : n["last"] + 1] = PRE
        for sign in session["positives"]:
            lo, hi = sign["first"], sign["last"]
            labels[max(0, lo - edge) : hi + edge + 1] = IGNORE_LABEL
            labels[lo : hi + 1] = ACTIVE
        features = session["features"]
        for start in range(0, len(features), int(spec["stride"])):
            lab = labels[start : start + int(spec["chunk"])]
            if np.any(lab != IGNORE_LABEL):
                rows.append(
                    {
                        "domain": "PHONE_REVIEWED",
                        "session": name,
                        "features": features[start : start + int(spec["chunk"])],
                        "labels": lab,
                    }
                )
    return rows


# ----------------------------------------------------------------------------- training
def pack(
    rows: list[dict[str, Any]],
    mean: np.ndarray,
    std: np.ndarray,
    family_weight: dict[str, float],
    negative_block_multiplier: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    length = max(len(r["labels"]) for r in rows)
    x = np.zeros((len(rows), length, FEATURE_WIDTH), np.float32)
    y = np.zeros((len(rows), length), np.int32)
    w = np.zeros((len(rows), length), np.float32)
    counts = Counter((r["domain"], int(v)) for r in rows for v in r["labels"] if v != IGNORE_LABEL)
    classes = {d: len({lab for dd, lab in counts if dd == d}) for d in {r["domain"] for r in rows}}
    for i, r in enumerate(rows):
        n = len(r["labels"])
        x[i, :n] = apply_normalization(r["features"], mean, std)
        valid = r["labels"] != IGNORE_LABEL
        y[i, :n] = np.where(valid, r["labels"], 0)
        for j in np.flatnonzero(valid):
            key = (r["domain"], int(r["labels"][j]))
            w[i, j] = family_weight[r["domain"]] / (classes[r["domain"]] * counts[key])
            if "kinds" in r and r["kinds"][j] == NEGATIVE_KIND:
                w[i, j] *= negative_block_multiplier
    w[w > 0] /= float(np.mean(w[w > 0]))
    return x, y, w


def probabilities(
    model: Any, features: np.ndarray, mean: np.ndarray, std: np.ndarray
) -> np.ndarray:
    normalized = apply_normalization(np.asarray(features, np.float32), mean, std)
    return np.asarray(softmax(np.asarray(model(normalized[None], training=False))[0]), np.float64)


def cal_metrics(
    model: Any, mean: np.ndarray, std: np.ndarray, data: dict[str, Any], containment: float
) -> dict[str, float]:
    nonsign = active_nonsign = 0
    acquired: dict[str, list[bool]] = {"first": [], "later": []}
    for stream in data["cal_streams"]:
        states = np.argmax(probabilities(model, stream["features"], mean, std), axis=1)
        mask = (stream["kinds"] == NEGATIVE_KIND) & (stream["labels"] == PRE)
        nonsign += int(np.sum(mask))
        active_nonsign += int(np.sum(states[mask] == ACTIVE))
        for o in sorted(set(stream["ordinals"].tolist()) - {-1}):
            rows = (stream["ordinals"] == o) & (stream["labels"] == ACTIVE)
            if np.any(rows):
                acquired["first" if o == 0 else "later"].append(
                    bool(np.any(states[rows] == ACTIVE))
                )
    contained = 0
    for clip in data["cal_isolated"]:
        p = probabilities(model, clip["features"], mean, std)
        t = np.asarray(clip["raw"].timestamp_ms, np.float64)
        decoder = CausalStreamingSignEventDecoder(suite.CONFIG_01)
        decoder.run(t, p, np.argmax(p, axis=1))
        active = np.flatnonzero(clip["labels"] == ACTIVE)
        lo, hi = t[active[0]], t[active[-1]]
        for e in decoder.events:
            window = materialize_recognition_window(
                t,
                LogicalSignEvent(
                    e.logical_active_start_index,
                    e.logical_active_end_index,
                    e.logical_active_start_ms,
                    e.logical_active_end_ms,
                    e.first_post_index,
                    e.first_post_ms,
                    e.emitted_at_index,
                    e.emitted_at_ms,
                ),
                suite.MATERIALIZER_CONFIG,
            )
            cover = max(0.0, min(window.selected_end_ms, hi) - max(window.selected_start_ms, lo))
            if (hi - lo <= 0 and window.selected_start_ms <= lo <= window.selected_end_ms) or (
                hi - lo > 0 and cover / (hi - lo) >= containment
            ):
                contained += 1
                break
    return {
        "nonsign_active_rate": active_nonsign / max(1, nonsign),
        "first_sign_acquisition": float(np.mean(acquired["first"])),
        "later_sign_acquisition": float(np.mean(acquired["later"])),
        "isolated_containment": contained / max(1, len(data["cal_isolated"])),
    }


def non_active_aware_loss(tf: Any) -> Any:
    """Sparse categorical cross-entropy on logits; label NON_ACTIVE scores -log(p_PRE + p_POST).
    Identical to SparseCategoricalCrossentropy(from_logits=True) when no NON_ACTIVE label exists."""

    def loss(y_true: Any, logits: Any) -> Any:
        y = tf.cast(tf.reshape(y_true, tf.shape(logits)[:-1]), tf.int32)
        log_p = tf.nn.log_softmax(logits, axis=-1)
        standard = -tf.gather(log_p, tf.minimum(y, 2), axis=-1, batch_dims=len(logits.shape) - 1)
        non_active = -tf.reduce_logsumexp(tf.gather(log_p, [0, 2], axis=-1), axis=-1)
        return tf.where(tf.equal(y, NON_ACTIVE), non_active, standard)

    return loss


def train(
    root: Path,
    config: dict[str, Any],
    epochs_override: int | None = None,
    config_path: Path = CONFIG_PATH,
) -> dict[str, Any]:
    import tensorflow as tf

    output = root / config["output"]
    if (output / "training_result.json").exists():
        raise RuntimeError(f"[s2_r3/train] RUN_ALREADY_EXECUTED:{output}")
    output.mkdir(parents=True, exist_ok=True)
    data = build_dataset(root, config)
    suite.write_json(output / "dataset_audit.json", data["audit"], overwrite=True)
    print(json.dumps(data["audit"], indent=1, default=str)[:3000], flush=True)
    fit = data["fit"]
    stats = normalization_from_train([r["features"] for r in fit])
    mean, std = stats["mean"], stats["std"]
    suite.write_json(
        output / "normalization.json",
        {
            "schema": "apphear.s2_r3.fit_normalization.v1",
            "feature_schema": "apphear.perception_vnext.segmentation_features.v1",
            "fit_observation_count": int(sum(len(r["labels"]) for r in fit)),
            "mean": mean.astype(float).tolist(),
            "std": std.astype(float).tolist(),
            "cal_or_gate_influenced_statistics": False,
        },
        overwrite=True,
    )
    x, y, w = pack(
        fit,
        mean,
        std,
        config["training"]["source_family_weight"],
        float(config["training"].get("negative_block_multiplier", 1.0)),
    )
    ref = config["reference_package"]
    reference = suite.load_package("S2_R2", "v1", root / ref["keras"], root / ref["normalization"])
    containment = float(config["selection"]["containment_fraction"])
    ref_metrics = cal_metrics(reference.model, reference.mean, reference.std, data, containment)
    print(f"[s2_r3/train] reference CAL {ref_metrics}", flush=True)

    tf.keras.utils.set_random_seed(int(config["seed"]))
    tf.config.experimental.enable_op_determinism()
    model = build_model(suite.read_json(root / PHASE7 / "phase7_config.json"))
    if model.count_params() != 123_779:
        raise RuntimeError(f"[s2_r3/train] PARAMETER_MISMATCH:{model.count_params()}")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(float(config["training"]["learning_rate"])),
        loss=non_active_aware_loss(tf),
        weighted_metrics=[tf.keras.metrics.SparseCategoricalAccuracy(name="state_accuracy")],
    )
    records: list[dict[str, Any]] = []
    best: dict[str, Any] = {"key": None, "epoch": None}

    class Select(tf.keras.callbacks.Callback):
        def on_epoch_end(self, epoch: int, logs: dict[str, float] | None = None) -> None:
            m = cal_metrics(self.model, mean, std, data, containment)
            eligible = m["nonsign_active_rate"] <= ref_metrics["nonsign_active_rate"]
            key = (m["later_sign_acquisition"], m["isolated_containment"])
            improved = eligible and (best["key"] is None or key > best["key"])
            if improved:
                best.update(key=key, epoch=epoch + 1)
                self.model.save(output / "best_model.keras", overwrite=True)
            self.model.save(output / f"epoch_{epoch + 1:02d}.keras", overwrite=True)
            records.append(
                {
                    "epoch": epoch + 1,
                    "loss": float((logs or {}).get("loss", np.nan)),
                    "cal": m,
                    "eligible": eligible,
                    "saved_as_best": improved,
                }
            )
            print(
                f"[s2_r3/train] epoch={epoch + 1} cal={m} eligible={eligible} best={improved}",
                flush=True,
            )

    history = model.fit(
        x,
        y,
        sample_weight=w,
        batch_size=int(config["training"]["batch_size"]),
        epochs=epochs_override or int(config["training"]["epochs"]),
        shuffle=True,
        verbose=2,
        callbacks=[Select()],
    )
    fallback = None
    if best["epoch"] is None:
        floor = float(
            config["selection"]["fallback_if_no_eligible_epoch"]["minimum_later_sign_acquisition"]
        )
        options = [r for r in records if r["cal"]["later_sign_acquisition"] >= floor]
        if options:
            fallback = min(options, key=lambda r: (r["cal"]["nonsign_active_rate"], -r["epoch"]))[
                "epoch"
            ]
    result = {
        "schema": "apphear.s2_r3.training_result.v1",
        "diagnostic_fallback_epoch": fallback,
        "milestone": config["milestone"],
        "config_sha256": suite.sha256(config_path),
        "split_sha256": suite.sha256(SPLIT_PATH),
        "reference_cal": ref_metrics,
        "best_epoch": best["epoch"],
        "best_key": list(best["key"] or ()),
        "status": "CANDIDATE_SELECTED" if best["epoch"] else "NO_ELIGIBLE_EPOCH",
        "model_sha256": (
            suite.sha256(output / "best_model.keras")
            if (output / "best_model.keras").exists()
            else None
        ),
        "normalization_sha256": suite.sha256(output / "normalization.json"),
        "epochs": records,
        "loss": [float(v) for v in history.history["loss"]],
        "gate_inputs_used_for_training_or_selection": bool(config.get("phone_reviewed_fit")),
        "holdout_session": config.get("holdout_session"),
        "protected_test_accessed": False,
    }
    suite.write_json(output / "training_result.json", result, overwrite=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit", "train", "smoke"])
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--holdout", help="train_03: reviewed phone session left out of FIT")
    args = parser.parse_args()
    config = suite.read_json(args.config)
    if args.holdout:
        if args.holdout not in config.get("phone_reviewed_fit", {}).get("sessions", []):
            raise ValueError(f"[s2_r3/train] UNKNOWN_HOLDOUT:{args.holdout}")
        config = {
            **config,
            "holdout_session": args.holdout,
            "output": f"{config['output']}/holdout_{args.holdout}",
        }
    if args.command == "audit":
        data = build_dataset(args.evidence_root, config)
        print(json.dumps(data["audit"], indent=1, default=str))
    elif args.command == "smoke":
        config = {
            **config,
            "output": config["output"] + "_smoke",
            "streams": {**config["streams"], "fit_count": 40, "cal_count": 12},
        }
        print(json.dumps(train(args.evidence_root, config, epochs_override=2)["epochs"], indent=1))
    else:
        result = train(args.evidence_root, config, config_path=args.config)
        print(json.dumps({k: result[k] for k in ("status", "best_epoch", "best_key")}, indent=1))


if __name__ == "__main__":
    main()
