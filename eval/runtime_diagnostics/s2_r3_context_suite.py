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
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.runtime_diagnostics.phase5_1t_first_segmenter import softmax  # noqa: E402
from eval.runtime_diagnostics.phase7_production_cadence_aligned_segmenter import (  # noqa: E402
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

CONFIG_PATH = ROOT / "model/config/recognition_upgrade/s2_r3_context_suite_01.json"
FREEZE_PATH = ROOT / "evidence/s2_r3_context_suite_20261016/suite_freeze.json"
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
        features = features_for_raw(subset_raw(raw_cache[raw_path], selected), contract)
        annotation = annotations[str(item["sample_id"])]
        views.append(
            {
                "key": str(item["view_key"]),
                "sample_id": str(item["sample_id"]),
                "signer": str(item["signer_id"]),
                "source": str(item["source"]),
                "view": str(item["view_id"]),
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


def summarize(rows: list[dict[str, float]]) -> dict[str, float]:
    return {
        "n": len(rows),
        "acquired_count": int(sum(row["acquired"] for row in rows)),
        "acquired_fraction": float(np.mean([row["acquired"] for row in rows])),
        "active_recall_mean": float(np.mean([row["active_recall"] for row in rows])),
        "false_active_mean": float(np.mean([row["false_active"] for row in rows])),
    }


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
    used: set[int] = set()
    signs = []
    for sign in session["positives"]:
        hits = [
            k
            for k, event in enumerate(events)
            if max(sign["first"], event["logical_active_start_index"])
            <= min(sign["last"], event["logical_active_end_index"])
        ]
        used.update(hits)
        signs.append(
            {
                "name": sign["name"],
                "acquired": bool(np.any(states[sign["active_rows"]] == ACTIVE)),
                "with_event": bool(hits),
            }
        )
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
    return {
        "sessions": per,
        "total": total,
        "continuous": {
            "post_dwell_events": len(dwell),
            "post_dwell_median_ms": float(np.median(dwell)) if dwell else None,
        },
    }


# ----------------------------------------------------------------------------- gate
def metric_value(results: dict[str, Any], path: str) -> float:
    value: Any = results
    for part in path.split("."):
        value = value[part]
    return float(value)


def apply_gate(
    config: dict[str, Any], results: dict[str, Any], reference: dict[str, Any]
) -> dict[str, Any]:
    lines = []
    for line in config["gate"]:
        threshold = (
            metric_value(reference, line["metric"]) - float(line["value_from_reference_minus"])
            if "value_from_reference_minus" in line
            else float(line["value"])
        )
        observed = metric_value(results, line["metric"])
        passed = observed >= threshold if line["op"] == ">=" else observed <= threshold
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
    return results, {"views": views, "sessions": sessions}


def freeze(root: Path) -> dict[str, Any]:
    import tensorflow as tf

    config = read_json(CONFIG_PATH)
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
        "config_path": str(CONFIG_PATH.relative_to(ROOT)).replace("\\", "/"),
        "config_sha256": sha256(CONFIG_PATH),
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
    write_json(FREEZE_PATH, record)
    return record


def evaluate_candidate(
    root: Path, package_id: str, contract: str, keras: Path, normalization: Path, out: Path
) -> dict[str, Any]:
    config = read_json(CONFIG_PATH)
    frozen = read_json(FREEZE_PATH)
    if sha256(CONFIG_PATH) != frozen["config_sha256"]:
        raise ValueError("[s2_r3/suite] CONFIG_CHANGED_AFTER_FREEZE")
    package = load_package(package_id, contract, keras, normalization)
    results, _ = run_suite(root, config, package)
    record = {
        "schema": "apphear.s2_r3.context_suite_result.v1",
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
    candidate = sub.choices["evaluate"]
    candidate.add_argument("--package-id", required=True)
    candidate.add_argument("--contract", default="v1")
    candidate.add_argument("--keras", type=Path, required=True)
    candidate.add_argument("--normalization", type=Path, required=True)
    candidate.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        record = freeze(args.evidence_root)
        print(json.dumps(record["reference_gate"], indent=2))
    else:
        record = evaluate_candidate(
            args.evidence_root,
            args.package_id,
            args.contract,
            args.keras,
            args.normalization,
            args.out,
        )
        print(json.dumps(record["gate"], indent=2))


if __name__ == "__main__":
    main()
