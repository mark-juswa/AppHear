"""S2-R3 frozen context suite (build step 1 of docs/audit/S2_R3_EXPERIMENT_PLAN_2026-10-16.md).

Read-only evaluation of one S2 segmenter package under the preregistered Tier-1 (held-out
segmentation DEV with controlled histories) and Tier-2 (four labelled phone sessions) gate.
`freeze` measures the frozen S2-R2 reference once and records every input identity before any
S2-R3 training; `evaluate` scores a candidate against that frozen record. Nothing is written
outside the requested evidence/output paths, and no model, feature contract or label changes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics.phase5_1t_first_segmenter import softmax  # noqa: E402
from eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter import (  # noqa: E402
    sparse_observation_indices,
    subset_raw,
)
from eval.runtime_diagnostics.phase8a_m2_frozen_sparse_dev_validation import (  # noqa: E402
    CONFIG_01,
    MATERIALIZER_CONFIG,
    interval_metrics,
)
from eval.runtime_diagnostics.phone_repeated_recognition_integration import (  # noqa: E402
    replay,
)
from eval.runtime_diagnostics.phone_s2_exact_parity_and_r2_decision import (  # noqa: E402
    load_capture,
)
from pipeline.perception_vnext.recognition_schema import (  # noqa: E402
    RawSequence,
    load_raw_sequence,
)
from pipeline.perception_vnext.recognition_window_materializer import (  # noqa: E402
    LogicalSignEvent,
    materialize_recognition_window,
)
from pipeline.perception_vnext.segmentation.learned_features import (  # noqa: E402
    FEATURE_WIDTH,
    apply_normalization,
    derive_causal_segmentation_features,
)
from pipeline.perception_vnext.segmentation.streaming_decoder import (  # noqa: E402
    CausalStreamingSignEventDecoder,
)

SUITES = {
    "01": (
        ROOT / "model/config/recognition_upgrade/s2_r3_context_suite_01.json",
        ROOT / "evidence/s2_r3_context_suite_20261016/suite_freeze.json",
    ),
    "02": (
        ROOT / "model/config/recognition_upgrade/s2_r3_context_suite_02.json",
        ROOT / "evidence/s2_r3_context_suite_20261016/suite_freeze_02.json",
    ),
    "03": (
        ROOT / "model/config/recognition_upgrade/s2_r3_context_suite_03.json",
        ROOT / "evidence/s2_r3_context_suite_20261016/suite_freeze_03.json",
    ),
    "04": (
        ROOT / "model/config/recognition_upgrade/s2_r3_context_suite_04.json",
        ROOT / "evidence/s2_r3_context_suite_20261016/suite_freeze_04.json",
    ),
}
CURRENT_SUITE = "04"
CONFIG_PATH, FREEZE_PATH = SUITES["01"]
PRE, ACTIVE, POST = 0, 1, 2
SUPPORTED_CONTRACTS = ("v1",)


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path: Path, value: Any, *, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"[s2_r3/suite] refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def features_for_raw(raw: RawSequence, contract: str) -> np.ndarray:
    """One dispatch point so a later versioned contract is evaluated on identical sources."""
    if contract == "v1":
        return np.asarray(derive_causal_segmentation_features(raw), np.float32)
    raise ValueError(f"[s2_r3/suite] S2R3_CONTRACT_NOT_IMPLEMENTED:{contract}")


def _take(raw: RawSequence, indices: np.ndarray, timestamps: np.ndarray) -> RawSequence:
    values: dict[str, Any] = {
        f.name: np.asarray(getattr(raw, f.name))[indices]
        for f in dataclass_fields(RawSequence)
        if f.name not in ("metadata", "frame_index", "timestamp_ms")
    }
    value = RawSequence(
        metadata=dict(raw.metadata),
        frame_index=np.arange(len(indices), dtype=np.int32),
        timestamp_ms=np.asarray(timestamps, np.float64),
        **values,
    )
    value.validate()
    return value


def slice_raw(raw: RawSequence, first: int, last: int) -> RawSequence:
    indices = np.arange(first, last + 1, dtype=np.int32)
    return _take(raw, indices, np.asarray(raw.timestamp_ms, np.float64)[indices])


def hold_raw(raw: RawSequence, index: int, count: int, interval_ms: float) -> RawSequence:
    """Diagnostic-only still hold: one genuine observation repeated at the view interval."""
    indices = np.full(count, index, np.int32)
    return _take(raw, indices, np.arange(count, dtype=np.float64) * interval_ms)


def concat_raw(parts: list[RawSequence], interval_ms: float) -> RawSequence:
    """Raw-level stitching: features are recomputed over the joined sequence, so the join is
    an ordinary (cross-source) backward delta rather than a start-of-sequence marker."""
    chunks: dict[str, list[np.ndarray]] = defaultdict(list)
    stamps: list[np.ndarray] = []
    offset = 0.0
    for part in parts:
        t = np.asarray(part.timestamp_ms, np.float64)
        shifted = t - t[0] + offset
        stamps.append(shifted)
        offset = float(shifted[-1]) + interval_ms
        for f in dataclass_fields(RawSequence):
            if f.name not in ("metadata", "frame_index", "timestamp_ms"):
                chunks[f.name].append(np.asarray(getattr(part, f.name)))
    timestamp = np.concatenate(stamps)
    value = RawSequence(
        metadata=dict(parts[-1].metadata),
        frame_index=np.arange(len(timestamp), dtype=np.int32),
        timestamp_ms=timestamp,
        **{name: np.concatenate(values) for name, values in chunks.items()},
    )
    value.validate()
    return value


@dataclass
class Package:
    package_id: str
    contract: str
    model: Any
    mean: np.ndarray
    std: np.ndarray
    identity: dict[str, str]

    def probabilities(self, features: np.ndarray) -> np.ndarray:
        """Causal full-sequence pass; equals the rolling runtime prefix (checked in tier 2)."""
        normalized = apply_normalization(np.asarray(features, np.float32), self.mean, self.std)
        logits = np.asarray(self.model(normalized[None], training=False))[0]
        return np.asarray(softmax(logits), np.float64)

    def rolling_probability(
        self, features: np.ndarray, index: int, receptive_field: int
    ) -> np.ndarray:
        start = max(0, index - receptive_field + 1)
        return np.asarray(self.probabilities(features[start : index + 1])[-1], np.float64)


def load_package(
    package_id: str,
    contract: str,
    keras_path: Path,
    normalization_path: Path,
    expected_keras_sha: str | None = None,
    expected_normalization_sha: str | None = None,
) -> Package:
    import tensorflow as tf

    if contract not in SUPPORTED_CONTRACTS:
        raise ValueError(f"[s2_r3/suite] S2R3_CONTRACT_NOT_IMPLEMENTED:{contract}")
    identity = {
        "keras_sha256": sha256(keras_path),
        "normalization_sha256": sha256(normalization_path),
    }
    if expected_keras_sha and identity["keras_sha256"] != expected_keras_sha:
        raise ValueError(f"[s2_r3/suite] PACKAGE_KERAS_HASH_MISMATCH:{package_id}")
    if (
        expected_normalization_sha
        and identity["normalization_sha256"] != expected_normalization_sha
    ):
        raise ValueError(f"[s2_r3/suite] PACKAGE_NORMALIZATION_HASH_MISMATCH:{package_id}")
    normalization = read_json(normalization_path)
    mean = np.asarray(normalization["mean"], np.float32)
    std = np.asarray(normalization["std"], np.float32)
    if mean.shape != (FEATURE_WIDTH,) or std.shape != (FEATURE_WIDTH,) or np.any(std <= 0):
        raise ValueError("[s2_r3/suite] PACKAGE_NORMALIZATION_INVALID")
    model = tf.keras.models.load_model(keras_path, compile=False)
    return Package(package_id, contract, model, mean, std, identity)


# ----------------------------------------------------------------------------- tier 1 inputs
def load_tier1_views(root: Path, config: dict[str, Any], contract: str) -> list[dict[str, Any]]:
    tier = config["tier1_dev"]
    selected_path = root / tier["selected_manifest"]
    if sha256(selected_path) != tier["selected_manifest_sha256"]:
        raise ValueError("[s2_r3/suite] DEV_SELECTED_MANIFEST_HASH_MISMATCH")
    population = {str(row["sample_id"]): row for row in read_json(selected_path)["rows"]}
    annotations = {
        str(row["sample_id"]): row
        for row in read_json(root / tier["human_annotations"])["annotations"]
    }
    manifest = read_json(root / tier["sparse_view_manifest"])
    raw_cache: dict[str, RawSequence] = {}
    views = []
    for item in manifest["rows"]:
        if item["phase7_partition"] != "DEV":
            continue
        if item["segmentation_split"] != "SEGMENTATION_DEV":
            raise ValueError("[s2_r3/suite] NON_DEV_VIEW_IN_TIER1")
        feature_path = Path(item["feature_path"])
        if sha256(feature_path) != item["feature_sha256"]:
            raise ValueError(f"[s2_r3/suite] DEV_FEATURE_HASH_MISMATCH:{item['view_key']}")
        with np.load(feature_path, allow_pickle=False) as data:
            stored = np.asarray(data["features"], np.float32)
            labels = np.asarray(data["labels"], np.int64)
            timestamps = np.asarray(data["timestamps_ms"], np.float64)
            selected = np.asarray(data["selected_indices"], np.int32)
        raw_path = str(item["source_raw_path"])
        if raw_path not in raw_cache:
            if sha256(Path(raw_path)) != item["source_raw_sha256"]:
                raise ValueError(f"[s2_r3/suite] DEV_RAW_HASH_MISMATCH:{item['view_key']}")
            raw_cache[raw_path] = load_raw_sequence(Path(raw_path))
        raw = subset_raw(raw_cache[raw_path], selected)
        features = features_for_raw(raw, contract)
        annotation = annotations[str(item["sample_id"])]
        views.append(
            {
                "key": str(item["view_key"]),
                "sample_id": str(item["sample_id"]),
                "signer": str(item["signer_id"]),
                "source": str(item["source"]),
                "view": str(item["view_id"]),
                "interval_ms": float(item["target_interval_ms"]),
                "raw": raw,
                "features": features,
                "stored_v1_features": stored,
                "labels": labels,
                "timestamps_ms": timestamps,
                "human_start_ms": float(annotation["human_sign_start_ms"]),
                "human_end_ms": float(annotation["human_sign_end_ms"]),
                "video_duration_ms": float(population[str(item["sample_id"])]["video_duration_ms"]),
            }
        )
    signers = {view["signer"] for view in views}
    clips = {view["sample_id"] for view in views}
    if (len(views), len(clips), len(signers)) != (
        tier["expected_views"],
        tier["expected_clips"],
        tier["expected_signers"],
    ):
        raise ValueError("[s2_r3/suite] DEV_MEMBERSHIP_MISMATCH")
    return views


# ----------------------------------------------------------------------------- tier 2 inputs
def load_tier2_session(
    root: Path, name: str, spec: dict[str, Any], contract: str, tolerance_ns: int
) -> dict[str, Any]:
    capture_dir = root / spec["capture"]
    capture = load_capture(capture_dir, require_full_session=False)
    features = features_for_raw(capture.raw, contract)
    timestamps = np.asarray(capture.raw.timestamp_ms, np.float64)
    positives: list[dict[str, Any]] = []
    uncertain: list[dict[str, Any]] = []
    negatives: list[dict[str, Any]] = []
    if spec["labels"] == "boundaries":
        labels = read_json(capture_dir / "transition_review/human_boundaries.json")
        for sign in labels["signs"]:
            if sign["start_index"] is None:
                continue
            first, last = int(sign["start_index"]), int(sign["end_index"])
            item: dict[str, Any] = {
                "name": f"{sign['condition']}:{sign['gloss']}#{sign['ordinal']}",
                "first": first,
                "last": last,
                "active_rows": list(range(first, last + 1)),
            }
            (positives if sign["judgment"] == "GENUINE_SIGN" else uncertain).append(item)
        for interval in labels.get("negative_intervals", []):
            if interval["start_index"] is not None and interval["judgment"] == "CONFIRMED_NON_SIGN":
                negatives.append(
                    {
                        "name": str(interval["block"]),
                        "first": int(interval["start_index"]),
                        "last": int(interval["end_index"]),
                    }
                )
    elif spec["labels"] == "attempts":
        review = root / spec["review"]
        stamp_ns = np.round(timestamps * 1e6).astype(np.int64)
        attempts: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
        with (review / "phone_positive_observation_labels.csv").open(encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                target = int(row["source_timestamp_ns"])
                index = int(np.argmin(np.abs(stamp_ns - target)))
                if abs(int(stamp_ns[index]) - target) > tolerance_ns:
                    raise ValueError(f"[s2_r3/suite] UNMATCHED_LABEL_TIMESTAMP:{name}:{target}")
                attempts[row["attempt_id"]].append(
                    (index, int(row["state_id"]), row["expected_gloss"])
                )
        for attempt_id, rows in sorted(attempts.items()):
            active = sorted(index for index, state, _ in rows if state == ACTIVE)
            if active:
                positives.append(
                    {
                        "name": f"{attempt_id}:{rows[0][2]}",
                        "first": active[0],
                        "last": active[-1],
                        "active_rows": active,
                    }
                )
        for k, interval in enumerate(
            read_json(review / "non_sign_visual_review.json")["confirmed_non_sign_intervals"]
        ):
            negatives.append(
                {
                    "name": f"NONSIGN_{k + 1}",
                    "first": int(interval["start_index"]),
                    "last": int(interval["end_index"]),
                }
            )
    else:
        raise ValueError(f"[s2_r3/suite] UNKNOWN_LABEL_KIND:{spec['labels']}")
    return {
        "name": name,
        "capture": capture,
        "features": features,
        "timestamps_ms": timestamps,
        "positives": positives,
        "uncertain": uncertain,
        "negatives": negatives,
        "continuous": bool(spec["continuous_no_capture_pauses"]),
        "capture_manifest_files": {
            key: value["sha256"] for key, value in capture.manifest["files"].items()
        },
    }


# ----------------------------------------------------------------------------- tier 1 scoring
def score_view(
    package: Package, history: np.ndarray, target: np.ndarray, labels: np.ndarray
) -> dict[str, float]:
    sequence = np.concatenate([history, target]) if len(history) else target
    predicted = np.argmax(package.probabilities(sequence)[len(history) :], axis=1)
    active = labels == ACTIVE
    other = (labels != ACTIVE) & (labels >= 0)
    return {
        "acquired": float(np.any(predicted[active] == ACTIVE)),
        "active_recall": float(np.mean(predicted[active] == ACTIVE)),
        "false_active": float(np.mean(predicted[other] == ACTIVE)) if np.any(other) else 0.0,
    }


def score_stitched(
    package: Package,
    combined: RawSequence,
    history_rows: int,
    labels: np.ndarray,
    history_scored: np.ndarray,
) -> dict[str, float]:
    """Score a raw-stitched sequence; history rows marked in `history_scored` count as
    confirmed non-sign evidence for the history false-ACTIVE rate."""
    features = features_for_raw(combined, package.contract)
    predicted = np.argmax(package.probabilities(features), axis=1)
    target, history = predicted[history_rows:], predicted[:history_rows]
    active = labels == ACTIVE
    other = (labels != ACTIVE) & (labels >= 0)
    return {
        "acquired": float(np.any(target[active] == ACTIVE)),
        "active_recall": float(np.mean(target[active] == ACTIVE)),
        "false_active": float(np.mean(target[other] == ACTIVE)) if np.any(other) else 0.0,
        "history_false_active": (
            float(np.mean(history[history_scored] == ACTIVE)) if np.any(history_scored) else 0.0
        ),
    }


def summarize(rows: list[dict[str, float]]) -> dict[str, float]:
    summary = {
        "n": len(rows),
        "acquired_count": int(sum(row["acquired"] for row in rows)),
        "acquired_fraction": float(np.mean([row["acquired"] for row in rows])),
        "active_recall_mean": float(np.mean([row["active_recall"] for row in rows])),
        "false_active_mean": float(np.mean([row["false_active"] for row in rows])),
    }
    if rows and "history_false_active" in rows[0]:
        summary["history_false_active_mean"] = float(
            np.mean([row["history_false_active"] for row in rows])
        )
    return summary


def stitched_condition(
    package: Package,
    condition: dict[str, Any],
    config: dict[str, Any],
    view: dict[str, Any],
    group: list[dict[str, Any]],
    sessions: dict[str, dict[str, Any]],
) -> dict[str, float] | None:
    """Raw-level held-out conditions (suite v02+)."""
    interval = float(view["interval_ms"])
    raw, labels = view["raw"], view["labels"]
    kind = condition["kind"]
    if kind == "raw_hold_after_previous_sign":
        others = [other for other in group if other["sample_id"] != view["sample_id"]]
        if not others:
            return None
        previous = others[0]
        previous_active = np.flatnonzero(previous["labels"] == ACTIVE)
        last_active = int(previous_active[-1])
        hold = int(condition["hold_observations"])
        parts = [slice_raw(previous["raw"], 0, last_active)]
        if hold:
            parts.append(hold_raw(previous["raw"], last_active, hold, interval))
        history = concat_raw(parts, interval)
        first_active = int(np.flatnonzero(labels == ACTIVE)[0])
        start = max(0, first_active - 1)
        target = slice_raw(raw, start, len(raw.timestamp_ms) - 1)
        scored = np.zeros(len(history.timestamp_ms), bool)
        return score_stitched(
            package, concat_raw([history, target], interval), len(scored), labels[start:], scored
        )
    if kind == "raw_session_history":
        source = config["history_sources"][condition["source"]]
        session_raw = sessions[source["session"]]["capture"].raw
        last = int(source["last_row"])
        first = max(int(source["first_row"]), last - int(condition["length"]) + 1)
        history = slice_raw(session_raw, first, last)
        scored = np.full(len(history.timestamp_ms), bool(source.get("confirmed_non_sign", False)))
        return score_stitched(
            package, concat_raw([history, raw], interval), len(scored), labels, scored
        )
    raise ValueError(f"[s2_r3/suite] UNKNOWN_CONDITION_KIND:{kind}")


def evaluate_tier1(
    package: Package,
    config: dict[str, Any],
    views: list[dict[str, Any]],
    sessions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for view in views:
        groups[(view["signer"], view["view"])].append(view)
    empty = np.zeros((0, FEATURE_WIDTH), np.float32)
    result: dict[str, Any] = {}
    for condition in config["tier1_conditions"]:
        rows: list[dict[str, float]] = []
        for view in views:
            group = groups[(view["signer"], view["view"])]
            kind = condition["kind"]
            target, labels, history = view["features"], view["labels"], empty
            if kind == "phone_history":
                source = config["history_sources"][condition["source"]]
                block = sessions[source["session"]]["features"][
                    source["first_row"] : source["last_row"] + 1
                ]
                history = block[-int(condition["length"]) :]
            elif kind == "previous_clip_full":
                others = [other for other in group if other["sample_id"] != view["sample_id"]]
                if not others:
                    continue
                history = others[0]["features"]
            elif kind == "direct_transition":
                if len(group) < 2:
                    continue
                position = next(i for i, item in enumerate(group) if item is view)
                previous = group[position - 1]
                previous_labels = previous["labels"]
                previous_active = np.flatnonzero(previous_labels == ACTIVE)
                after = [
                    i
                    for i in range(int(previous_active[-1]) + 1, len(previous_labels))
                    if previous_labels[i] == POST
                ]
                if not after:
                    continue
                end = min(after[0] + int(condition["extra_post"]), len(previous_labels) - 1)
                history = previous["features"][: end + 1]
                first_active = int(np.flatnonzero(labels == ACTIVE)[0])
                target = target[max(0, first_active - 1) :]
                labels = labels[max(0, first_active - 1) :]
            elif kind.startswith("raw_"):
                stitched = stitched_condition(package, condition, config, view, group, sessions)
                if stitched is not None:
                    rows.append(stitched)
                continue
            elif kind != "none":
                raise ValueError(f"[s2_r3/suite] UNKNOWN_CONDITION_KIND:{kind}")
            rows.append(score_view(package, history, target, labels))
        result[condition["id"]] = summarize(rows)
    result["isolated"] = isolated_containment(package, config, views)
    return result


def isolated_containment(
    package: Package, config: dict[str, Any], views: list[dict[str, Any]]
) -> dict[str, Any]:
    spec = config["tier1_isolated_containment"]
    if (
        MATERIALIZER_CONFIG.requested_pre_context_ms,
        MATERIALIZER_CONFIG.requested_post_context_ms,
    ) != (
        spec["materializer_pre_ms"],
        spec["materializer_post_ms"],
    ):
        raise ValueError("[s2_r3/suite] MATERIALIZER_CONFIG_DRIFT")
    contained = emitted = 0
    for view in views:
        probabilities = package.probabilities(view["features"])
        decoder = CausalStreamingSignEventDecoder(CONFIG_01)
        decoder.run(view["timestamps_ms"], probabilities, np.argmax(probabilities, axis=1))
        if not decoder.events:
            continue
        emitted += 1
        event = decoder.events[0]
        window = materialize_recognition_window(
            view["timestamps_ms"],
            LogicalSignEvent(
                event.logical_active_start_index,
                event.logical_active_end_index,
                event.logical_active_start_ms,
                event.logical_active_end_ms,
                event.first_post_index,
                event.first_post_ms,
                event.emitted_at_index,
                event.emitted_at_ms,
            ),
            MATERIALIZER_CONFIG,
        )
        metrics = interval_metrics(
            window.selected_start_ms,
            window.selected_end_ms,
            view["human_start_ms"],
            view["human_end_ms"],
            view["video_duration_ms"],
        )
        contained += int(float(metrics["active_recall"]) >= float(spec["containment_fraction"]))
    return {
        "n": len(views),
        "emitted": emitted,
        "contained": contained,
        "contained_fraction": contained / len(views),
    }


# ----------------------------------------------------------------------------- tier 2 scoring
def match_signs(
    positives: list[dict[str, Any]], events: list[dict[str, Any]], states: np.ndarray
) -> tuple[list[dict[str, Any]], set[int], int]:
    """Overlap matching of reviewed signs to logical events. An event may be credited to at most
    one sign (a merged episode spanning two signs is one recognition, not two)."""
    used: set[int] = set()
    credited: set[int] = set()
    signs_per_event: dict[int, int] = defaultdict(int)
    signs = []
    for sign in positives:
        hits = [
            k
            for k, event in enumerate(events)
            if max(sign["first"], event["logical_active_start_index"])
            <= min(sign["last"], event["logical_active_end_index"])
        ]
        used.update(hits)
        for k in hits:
            signs_per_event[k] += 1
        distinct = next((k for k in hits if k not in credited), None)
        if distinct is not None:
            credited.add(distinct)
        signs.append(
            {
                "name": sign["name"],
                "acquired": bool(np.any(states[sign["active_rows"]] == ACTIVE)),
                "with_event": bool(hits),
                "with_distinct_event": distinct is not None,
            }
        )
    merged = sum(1 for count in signs_per_event.values() if count > 1)
    return signs, used, merged


def evaluate_session(
    package: Package, session: dict[str, Any], receptive_field: int, sample: int, tolerance: float
) -> dict[str, Any]:
    features, timestamps = session["features"], session["timestamps_ms"]
    probabilities = package.probabilities(features)
    rng = np.random.default_rng(0)
    checked = sorted(rng.choice(len(features), size=min(sample, len(features)), replace=False))
    rolling_error = max(
        float(
            np.max(
                np.abs(
                    package.rolling_probability(features, int(i), receptive_field)
                    - probabilities[i]
                )
            )
        )
        for i in checked
    )
    if rolling_error > tolerance:
        raise ValueError(
            f"[s2_r3/suite] ROLLING_EQUIVALENCE_FAILED:{session['name']}:{rolling_error}"
        )
    states = np.argmax(probabilities, axis=1)
    replayed = replay(
        [
            {
                "source_index": index,
                "source_timestamp_ms": float(timestamps[index]),
                "argmax_state": int(states[index]),
                "pre_probability": float(probabilities[index, PRE]),
                "active_probability": float(probabilities[index, ACTIVE]),
                "post_probability": float(probabilities[index, POST]),
            }
            for index in range(len(states))
        ],
        allow_post_rearm=True,
        exact_android_commit_recovery=True,
    )
    events = replayed["events"]
    signs, used, merged = match_signs(session["positives"], events, states)
    nonsign_observations = sum(n["last"] - n["first"] + 1 for n in session["negatives"])
    nonsign_active = sum(
        int(np.sum(states[n["first"] : n["last"] + 1] == ACTIVE)) for n in session["negatives"]
    )
    inside_nonsign = sum(
        1
        for event in events
        for n in session["negatives"]
        if n["first"] <= event["logical_active_start_index"]
        and event["logical_active_end_index"] <= n["last"]
    )
    dwell = []
    for event in events:
        commit = int(event["emitted_at_index"])
        leave = next((i for i in range(commit, len(states)) if states[i] != POST), None)
        if leave is not None:
            dwell.append(float(timestamps[leave] - timestamps[commit]))
    return {
        "genuine_signs": len(signs),
        "acquired": sum(sign["acquired"] for sign in signs),
        "signs_with_event": sum(sign["with_event"] for sign in signs),
        "signs_with_distinct_event": sum(sign["with_distinct_event"] for sign in signs),
        "merged_events": merged,
        "events": len(events),
        "events_inside_nonsign": inside_nonsign,
        "other_events": len(events) - len(used) - inside_nonsign,
        "nonsign_observations": nonsign_observations,
        "nonsign_active_observations": nonsign_active,
        "post_dwell_ms": dwell,
        "continuous": session["continuous"],
        "rolling_equivalence_max_abs": rolling_error,
        "event_identities": [
            [
                int(event["logical_active_start_index"]),
                int(event["logical_active_end_index"]),
                int(event["emitted_at_index"]),
            ]
            for event in events
        ],
        "per_sign": signs,
    }


def evaluate_tier2(
    package: Package, config: dict[str, Any], sessions: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    per = {
        name: evaluate_session(
            package,
            session,
            int(config["receptive_field_observations"]),
            int(config["rolling_equivalence_sample_size"]),
            float(config["rolling_equivalence_tolerance"]),
        )
        for name, session in sessions.items()
    }
    keys = (
        "genuine_signs",
        "acquired",
        "signs_with_event",
        "signs_with_distinct_event",
        "merged_events",
        "events",
        "events_inside_nonsign",
        "other_events",
        "nonsign_observations",
        "nonsign_active_observations",
    )
    total = {key: int(sum(result[key] for result in per.values())) for key in keys}
    tier = config["tier2_sessions"]
    if total["genuine_signs"] != tier["expected_genuine_signs"]:
        raise ValueError("[s2_r3/suite] TIER2_SIGN_COUNT_MISMATCH")
    if total["nonsign_observations"] != tier["expected_nonsign_observations"]:
        raise ValueError("[s2_r3/suite] TIER2_NONSIGN_COUNT_MISMATCH")
    dwell = [
        value
        for result in per.values()
        if result["continuous"]
        for value in result["post_dwell_ms"]
    ]
    continuous = {
        key: int(sum(result[key] for result in per.values() if result["continuous"]))
        for key in keys
    }
    return {
        "sessions": per,
        "total": total,
        "continuous": {
            **continuous,
            "post_dwell_events": len(dwell),
            "post_dwell_median_ms": float(np.median(dwell)) if dwell else None,
        },
    }


# ----------------------------------------------------------------------------- gate
def metric_value(results: dict[str, Any], path: str) -> float:
    value: Any = results
    for part in path.split("."):
        value = value[part]
    # A missing measurement (e.g. no events to time) can never satisfy a gate line.
    return float("nan") if value is None else float(value)


def apply_gate(
    config: dict[str, Any], results: dict[str, Any], reference: dict[str, Any]
) -> dict[str, Any]:
    lines = []
    for line in config["gate"]:
        if "value_from_reference_minus" in line:
            threshold = metric_value(reference, line["metric"]) - float(
                line["value_from_reference_minus"]
            )
        elif "value_from_reference_plus" in line:
            threshold = metric_value(reference, line["metric"]) + float(
                line["value_from_reference_plus"]
            )
        else:
            threshold = float(line["value"])
        observed = metric_value(results, line["metric"])
        passed = bool(observed >= threshold if line["op"] == ">=" else observed <= threshold)
        lines.append(
            {
                "id": line["id"],
                "observed": observed,
                "op": line["op"],
                "threshold": threshold,
                "pass": passed,
            }
        )
    return {"lines": lines, "pass": all(line["pass"] for line in lines)}


# ----------------------------------------------------------------------------- tier 1b
def load_heldout_negative_streams(
    root: Path, config: dict[str, Any], contract: str
) -> dict[str, dict[str, Any]]:
    """One continuous stream per held-out N0 participant (suite v03+): each clip is sampled at
    the configured phone cadence view, clips are raw-stitched in clip-id order, and rows within
    the exclusion radius of a human-flagged visible-hand sample are left unscored."""
    spec = config["tier1b_heldout_negatives"]
    manifest = read_json(root / spec["n0_manifest"])
    split = read_json(ROOT / spec["data_split"])
    if sha256(ROOT / spec["data_split"]) != manifest["split_sha256"]:
        raise ValueError("[s2_r3/suite] N0_MANIFEST_SPLIT_MISMATCH")
    allowed = {clip["clip_id"] for clip in split["n0_negatives"] if clip["role"] in spec["roles"]}
    interval = float(spec["view_interval_ms"])
    radius = float(spec["exclusion_radius_ms"])
    by_participant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for clip in manifest["clips"]:
        if clip["clip_id"] in allowed:
            by_participant[clip["participant"]].append(clip)
    if {c for clips in by_participant.values() for c in (x["clip_id"] for x in clips)} != allowed:
        raise ValueError("[s2_r3/suite] N0_HELDOUT_CLIPS_INCOMPLETE")
    streams = {}
    for participant, clips in sorted(by_participant.items()):
        parts, scored = [], []
        for clip in sorted(clips, key=lambda c: c["clip_id"]):
            path = root / clip["raw_path"]
            if sha256(path) != clip["raw_sha256"]:
                raise ValueError(f"[s2_r3/suite] N0_RAW_HASH_MISMATCH:{clip['clip_id']}")
            raw = load_raw_sequence(path)
            indices, _ = sparse_observation_indices(
                np.asarray(raw.timestamp_ms), clip["clip_id"], spec["view_id"], interval
            )
            sparse = subset_raw(raw, indices)
            stamps = np.asarray(sparse.timestamp_ms, np.float64) - float(raw.timestamp_ms[0])
            mask = np.ones(len(stamps), bool)
            for sample in clip["excluded_review_samples"]:
                mask &= np.abs(stamps - float(sample["timestamp_ms"])) > radius
            parts.append(sparse)
            scored.append(mask)
        stream = concat_raw(parts, interval)
        streams[participant] = {
            "features": features_for_raw(stream, contract),
            "timestamps_ms": np.asarray(stream.timestamp_ms, np.float64),
            "scored": np.concatenate(scored),
            "clips": len(clips),
        }
    return streams


def evaluate_heldout_negatives(
    package: Package, streams: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    per = {}
    for participant, stream in streams.items():
        probabilities = package.probabilities(stream["features"])
        states = np.argmax(probabilities, axis=1)
        timestamps = stream["timestamps_ms"]
        replayed = replay(
            [
                {
                    "source_index": index,
                    "source_timestamp_ms": float(timestamps[index]),
                    "argmax_state": int(states[index]),
                    "pre_probability": float(probabilities[index, PRE]),
                    "active_probability": float(probabilities[index, ACTIVE]),
                    "post_probability": float(probabilities[index, POST]),
                }
                for index in range(len(states))
            ],
            allow_post_rearm=True,
            exact_android_commit_recovery=True,
        )
        scored = stream["scored"]
        events = [
            event
            for event in replayed["events"]
            if scored[int(event["logical_active_start_index"])]
        ]
        minutes = float(timestamps[-1] - timestamps[0]) / 60000.0
        per[participant] = {
            "clips": stream["clips"],
            "observations": int(len(states)),
            "scored_observations": int(np.sum(scored)),
            "active_observations": int(np.sum(states[scored] == ACTIVE)),
            "events": len(events),
            "minutes": minutes,
        }
    scored_total = sum(item["scored_observations"] for item in per.values())
    minutes_total = sum(item["minutes"] for item in per.values())
    active_total = sum(item["active_observations"] for item in per.values())
    events_total = sum(item["events"] for item in per.values())
    return {
        "participants": per,
        "total": {
            "scored_observations": scored_total,
            "active_observations": active_total,
            "active_rate": active_total / scored_total if scored_total else float("nan"),
            "events": events_total,
            "minutes": minutes_total,
            "events_per_minute": events_total / minutes_total if minutes_total else float("nan"),
        },
    }


# ----------------------------------------------------------------------------- tier 1c
def load_ipn_streams(
    root: Path, config: dict[str, Any], contract: str
) -> dict[str, dict[str, Any]]:
    """IPN Hand held-out subjects (suite v04+): hands-visible everyday movement from people outside
    every S2 training and selection set. Each video is one stream at the configured view; rows are
    labelled from IPN HandS by time (ffmpeg fps=30 timeline, 1-based inclusive); NOG rows within
    the margin of any gesture are unscored transitions; gestures are never treated as ASL."""
    from eval.runtime_diagnostics import ipn_hand_feasibility as ipn

    spec = config["tier1c_ipn_hands_visible"]
    manifest_path = root / spec["manifest"]
    if sha256(manifest_path) != spec["manifest_sha256"]:
        raise ValueError("[s2_r3/suite] IPN_MANIFEST_CHANGED")
    if sha256(ROOT / spec["subject_split"]) != spec["subject_split_sha256"]:
        raise ValueError("[s2_r3/suite] IPN_SPLIT_CHANGED")
    roles = read_json(ROOT / spec["subject_split"])["roles"]
    streams = {}
    for clip in read_json(manifest_path)["clips"]:
        if roles[clip["subject"]] not in spec["roles"]:
            continue
        for key in ("raw", "annotation"):
            if sha256(root / clip[f"{key}_path"]) != clip[f"{key}_sha256"]:
                raise ValueError(f"[s2_r3/suite] IPN_{key.upper()}_HASH:{clip['video']}")
        full = load_raw_sequence(root / clip["raw_path"])
        raw = subset_raw(full, ipn.view(full, float(spec["view_interval_ms"])))
        t = np.asarray(raw.timestamp_ms, np.float64)
        segments = ipn.hands_segments(root, clip["video"])
        streams[clip["video"]] = {
            "subject": clip["subject"],
            "raw": raw,
            "features": features_for_raw(raw, contract),
            "timestamps_ms": t,
            "classes": ipn.row_classes(t, segments, float(spec["gesture_margin_ms"])),
            "segments": segments,
        }
    if len({s["subject"] for s in streams.values()}) != int(spec["expected_subjects"]):
        raise ValueError("[s2_r3/suite] IPN_SUBJECT_COUNT_MISMATCH")
    return streams


def evaluate_ipn(
    package: Package, streams: dict[str, dict[str, Any]], spec: dict[str, Any]
) -> dict[str, Any]:
    chunk = int(spec["chunk_observations"])
    per: dict[str, dict[str, Any]] = {}
    for video, stream in streams.items():
        probabilities = package.probabilities(stream["features"])
        states = np.argmax(probabilities, axis=1)
        t, cls = stream["timestamps_ms"], stream["classes"]
        replayed = replay(
            [
                {
                    "source_index": index,
                    "source_timestamp_ms": float(t[index]),
                    "argmax_state": int(states[index]),
                    "pre_probability": float(probabilities[index, PRE]),
                    "active_probability": float(probabilities[index, ACTIVE]),
                    "post_probability": float(probabilities[index, POST]),
                }
                for index in range(len(states))
            ],
            allow_post_rearm=True,
            exact_android_commit_recovery=True,
        )
        spans = [
            (int(e["logical_active_start_index"]), int(e["logical_active_end_index"]))
            for e in replayed["events"]
        ]
        nog = np.flatnonzero(cls == 0)
        hands = np.asarray(stream["raw"].hand_observed, bool).any(axis=1)
        chunks = fired = 0
        for block in np.split(nog, np.flatnonzero(np.diff(nog) > 1) + 1) if len(nog) else []:
            for a in range(0, len(block), chunk):
                rows = block[a : a + chunk]
                if len(rows) >= 4 and hands[rows].any():
                    chunks += 1
                    fired += int(probabilities[rows, ACTIVE].max() >= 0.5)
        rel = (t - t[0]) * 30.0 / 1000.0 + 1.0
        gestures = hit = 0
        for c, start, end in stream["segments"]:
            if c in spec["canary_classes"]:
                rows = np.flatnonzero((rel >= start) & (rel <= end))
                if len(rows):
                    gestures += 1
                    hit += int(any(max(a, rows[0]) <= min(b, rows[-1]) for a, b in spans))
        per[video] = {
            "subject": stream["subject"],
            "nog_observations": int(len(nog)),
            "nog_active_observations": int(np.sum(states[nog] == ACTIVE)),
            "nog_events": sum(1 for a, b in spans if np.all(cls[a : b + 1] == 0)),
            "nog_minutes": float(len(nog) * float(spec["view_interval_ms"]) / 60000.0),
            "hand_visible_nog_chunks": chunks,
            "hand_visible_nog_chunks_fired": fired,
            "canary_gestures": gestures,
            "canary_gestures_with_event": hit,
        }

    def total(key: str) -> float:
        return float(sum(v[key] for v in per.values()))

    return {
        "videos": per,
        "total": {
            "subjects": sorted({v["subject"] for v in per.values()}),
            "nog_observations": int(total("nog_observations")),
            "nog_active_rate": total("nog_active_observations")
            / max(1.0, total("nog_observations")),
            "nog_events": int(total("nog_events")),
            "nog_minutes": total("nog_minutes"),
            "nog_events_per_minute": total("nog_events") / max(1e-9, total("nog_minutes")),
            "hand_visible_nog_chunk_fire_rate": total("hand_visible_nog_chunks_fired")
            / max(1.0, total("hand_visible_nog_chunks")),
            "gesture_canary": total("canary_gestures_with_event")
            / max(1.0, total("canary_gestures")),
        },
    }


# ----------------------------------------------------------------------------- commands
def run_suite(
    root: Path, config: dict[str, Any], package: Package
) -> tuple[dict[str, Any], dict[str, Any]]:
    tier2_spec = config["tier2_sessions"]
    sessions = {
        name: load_tier2_session(
            root, name, spec, package.contract, int(tier2_spec["timestamp_match_tolerance_ns"])
        )
        for name, spec in tier2_spec.items()
        if isinstance(spec, dict) and "capture" in spec
    }
    views = load_tier1_views(root, config, package.contract)
    results = {
        "tier1": evaluate_tier1(package, config, views, sessions),
        "tier2": evaluate_tier2(package, config, sessions),
    }
    if "tier1b_heldout_negatives" in config:
        streams = load_heldout_negative_streams(root, config, package.contract)
        results["tier1b"] = evaluate_heldout_negatives(package, streams)
    if "tier1c_ipn_hands_visible" in config:
        ipn_streams = load_ipn_streams(root, config, package.contract)
        results["tier1c"] = evaluate_ipn(package, ipn_streams, config["tier1c_ipn_hands_visible"])
    return results, {"views": views, "sessions": sessions}


def freeze(root: Path, suite_id: str = CURRENT_SUITE) -> dict[str, Any]:
    import tensorflow as tf

    config_path, freeze_path = SUITES[suite_id]
    config = read_json(config_path)
    spec = config["reference_package"]
    package = load_package(
        spec["package_id"],
        spec["contract"],
        root / spec["keras"],
        root / spec["normalization"],
        spec["keras_sha256"],
        spec["normalization_sha256"],
    )
    results, inputs = run_suite(root, config, package)
    views = inputs["views"]
    feature_parity = max(
        float(np.max(np.abs(view["features"] - view["stored_v1_features"]))) for view in views
    )
    if feature_parity != 0.0:
        raise ValueError(f"[s2_r3/suite] DEV_V1_RECOMPUTATION_MISMATCH:{feature_parity}")
    session_checks = {}
    for name, session in inputs["sessions"].items():
        capture = session["capture"]
        recorded = [
            json.loads(line)
            for line in (root / config["tier2_sessions"][name]["capture"] / "events.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        recorded_ids = [
            [e["logical_active_start_index"], e["logical_active_end_index"], e["commit_index"]]
            for e in recorded
        ]
        session_checks[name] = {
            "v1_features_vs_android_max_abs": float(
                np.max(np.abs(session["features"] - capture.android_features))
            ),
            "probabilities_vs_android_max_abs": float(
                np.max(
                    np.abs(
                        package.probabilities(session["features"]) - capture.android_probabilities
                    )
                )
            ),
            "replayed_events_equal_recorded": results["tier2"]["sessions"][name]["event_identities"]
            == recorded_ids,
            "capture_file_sha256": session["capture_manifest_files"],
        }
        if session_checks[name]["v1_features_vs_android_max_abs"] != 0.0:
            raise ValueError(f"[s2_r3/suite] SESSION_V1_RECOMPUTATION_MISMATCH:{name}")
        if not session_checks[name]["replayed_events_equal_recorded"]:
            raise ValueError(f"[s2_r3/suite] SESSION_EVENT_REPLAY_MISMATCH:{name}")
    record = {
        "schema": "apphear.s2_r3.context_suite_freeze.v1",
        "suite_id": suite_id,
        "config_path": str(config_path.relative_to(ROOT)).replace("\\", "/"),
        "config_sha256": sha256(config_path),
        "reference_package": {**spec, "measured_identity": package.identity},
        "input_identity": {
            "dev_selected_manifest_sha256": config["tier1_dev"]["selected_manifest_sha256"],
            "dev_sparse_view_manifest_sha256": sha256(
                root / config["tier1_dev"]["sparse_view_manifest"]
            ),
            "dev_human_annotations_sha256": sha256(root / config["tier1_dev"]["human_annotations"]),
            "dev_view_feature_sha256": {
                view["key"]: hashlib.sha256(view["stored_v1_features"].tobytes()).hexdigest()
                for view in views
            },
            **(
                {
                    "ipn_manifest_sha256": config["tier1c_ipn_hands_visible"]["manifest_sha256"],
                    "ipn_subject_split_sha256": config["tier1c_ipn_hands_visible"][
                        "subject_split_sha256"
                    ],
                }
                if "tier1c_ipn_hands_visible" in config
                else {}
            ),
        },
        "reproduction_checks": {
            "dev_v1_recomputed_vs_stored_max_abs": feature_parity,
            "sessions": session_checks,
        },
        "reference_results": results,
        "reference_gate": apply_gate(config, results, results),
        "environment": {
            "python": platform.python_version(),
            "tensorflow": tf.__version__,
            "numpy": np.__version__,
        },
        "scope": "Development-exposed Tier 1/2 diagnostics only; not ASL accuracy and not Tier 3.",
    }
    write_json(freeze_path, record)
    return record


def evaluate_candidate(
    root: Path,
    package_id: str,
    contract: str,
    keras: Path,
    normalization: Path,
    out: Path,
    suite_id: str = CURRENT_SUITE,
) -> dict[str, Any]:
    config_path, freeze_path = SUITES[suite_id]
    config = read_json(config_path)
    frozen = read_json(freeze_path)
    if sha256(config_path) != frozen["config_sha256"]:
        raise ValueError("[s2_r3/suite] CONFIG_CHANGED_AFTER_FREEZE")
    package = load_package(package_id, contract, keras, normalization)
    results, _ = run_suite(root, config, package)
    record = {
        "schema": "apphear.s2_r3.context_suite_result.v1",
        "suite_id": suite_id,
        "config_sha256": frozen["config_sha256"],
        "package_id": package_id,
        "contract": contract,
        "package_identity": package.identity,
        "results": results,
        "gate": apply_gate(config, results, frozen["reference_results"]),
    }
    write_json(out, record)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("freeze", "evaluate"):
        command = sub.add_parser(name)
        command.add_argument("--evidence-root", type=Path, required=True)
        command.add_argument("--suite", choices=sorted(SUITES), default=CURRENT_SUITE)
    candidate = sub.choices["evaluate"]
    candidate.add_argument("--package-id", required=True)
    candidate.add_argument("--contract", default="v1")
    candidate.add_argument("--keras", type=Path, required=True)
    candidate.add_argument("--normalization", type=Path, required=True)
    candidate.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        record = freeze(args.evidence_root, args.suite)
        print(json.dumps(record["reference_gate"], indent=2))
    else:
        record = evaluate_candidate(
            args.evidence_root,
            args.package_id,
            args.contract,
            args.keras,
            args.normalization,
            args.out,
            args.suite,
        )
        print(json.dumps(record["gate"], indent=2))


if __name__ == "__main__":
    main()
