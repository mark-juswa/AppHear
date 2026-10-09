"""A2-2R offline one-observation landmark recovery experiment.

The recovery path is causal and slot-preserving. It never imports the rejected A2 identity
tracker, never lets recovered landmarks seed history, and never recovers beyond the first missing
observation. Future direct observations are used only for retrospective geometry scoring.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from eval.runtime_diagnostics import ru_d1

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "model/config/recognition_upgrade/a2_recovery.json"
FEATURE_DIM = 258
HAND_POINTS = 21
HAND_DIM = 63
SIDES = ("left", "right")
POSE_WRISTS = {"left": 15, "right": 16}
MCP_INDICES = np.asarray([5, 9, 13, 17], dtype=np.int64)


FloatArray = NDArray[np.float64]


@dataclass
class DirectHistory:
    previous: FloatArray | None = None
    previous_timestamp_ns: int | None = None
    previous_observation_index: int | None = None
    latest: FloatArray | None = None
    latest_timestamp_ns: int | None = None
    latest_observation_index: int | None = None
    missing_run: int = 0


@dataclass
class RecoveryRecord:
    condition: str
    attempt_id: str
    frame_id: int
    timestamp_ns: int
    observation_index: int
    side: str
    state: str
    source_direct_timestamp_ns: int | None
    recovery_age_ms: float | None
    last_direct_observation_index: int | None
    next_direct_returned: bool
    eligibility_reason: str
    recovered_landmarks: FloatArray | None = None
    source_landmarks: FloatArray | None = None


@dataclass(frozen=True)
class S5Frame:
    frame_id: int
    event: str
    signing: bool
    motion: float
    hands_seen: bool
    onset_candidate: bool


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile(values: list[float], value: float) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=np.float64), value))


def hand_block(feature: FloatArray, side_index: int) -> FloatArray:
    start = side_index * HAND_DIM
    return feature[start : start + HAND_DIM].reshape(HAND_POINTS, 3)


def hand_present(block: FloatArray) -> bool:
    return bool(np.any(block != 0.0) and np.isfinite(block).all())


def hand_scale(block: FloatArray) -> float:
    return float(np.mean(np.linalg.norm(block[MCP_INDICES, :2] - block[0, :2], axis=1)))


def clip_vectors(values: FloatArray, maximum: float) -> FloatArray:
    norms = np.linalg.norm(values, axis=-1, keepdims=True)
    factors = np.minimum(1.0, maximum / np.maximum(norms, 1e-12))
    return values * factors


class OneObservationRecovery:
    """Direct-history-only recovery for one missing observation per gap."""

    def __init__(self, condition: str, config: dict[str, Any]) -> None:
        if condition not in {
            "C0_DIRECT_ONLY",
            "C1_ONE_OBSERVATION_HOLD",
            "C2_ONE_OBSERVATION_BOUNDED_VELOCITY",
        }:
            raise ValueError(f"unknown A2-2R condition: {condition}")
        self.condition = condition
        self.eligibility = config["eligibility"]
        self.velocity = config["velocity"]
        self.history = {side: DirectHistory() for side in SIDES}

    def process(
        self,
        attempt_id: str,
        observation_index: int,
        frame_id: int,
        timestamp_ns: int,
        feature: FloatArray,
        previous_signing: bool,
        next_feature: FloatArray | None,
    ) -> tuple[FloatArray, list[RecoveryRecord]]:
        base = np.asarray(feature, dtype=np.float64)
        if base.shape != (FEATURE_DIM,):
            raise ValueError(f"expected [{FEATURE_DIM}], got {base.shape}")
        output = base.copy()
        direct = [hand_present(hand_block(base, index)) for index in range(2)]
        pose = base[126:].reshape(33, 4)
        records: list[RecoveryRecord] = []

        for side_index, side in enumerate(SIDES):
            state = self.history[side]
            block = hand_block(base, side_index)
            if direct[side_index]:
                state.previous = None if state.latest is None else state.latest.copy()
                state.previous_timestamp_ns = state.latest_timestamp_ns
                state.previous_observation_index = state.latest_observation_index
                state.latest = block.copy()
                state.latest_timestamp_ns = timestamp_ns
                state.latest_observation_index = observation_index
                state.missing_run = 0
                records.append(
                    RecoveryRecord(
                        self.condition,
                        attempt_id,
                        frame_id,
                        timestamp_ns,
                        observation_index,
                        side,
                        "DIRECT",
                        timestamp_ns,
                        0.0,
                        observation_index,
                        False,
                        "direct_observation",
                    )
                )
                continue

            state.missing_run += 1
            next_direct = bool(
                next_feature is not None
                and hand_present(hand_block(np.asarray(next_feature, dtype=np.float64), side_index))
            )
            reason = self._eligibility_reason(
                side,
                side_index,
                state,
                observation_index,
                timestamp_ns,
                pose,
                previous_signing,
                direct[1 - side_index],
            )
            recovered: FloatArray | None = None
            state_name = "MISSING"
            if self.condition != "C0_DIRECT_ONLY" and reason == "eligible":
                if self.condition == "C1_ONE_OBSERVATION_HOLD":
                    recovered = state.latest.copy() if state.latest is not None else None
                    state_name = "RECOVERED_HOLD"
                else:
                    recovered = self._predict_velocity(state, timestamp_ns)
                    state_name = "RECOVERED_VELOCITY"
                if recovered is None:
                    reason = "prediction_unavailable"
                    state_name = "MISSING"
                else:
                    start = side_index * HAND_DIM
                    output[start : start + HAND_DIM] = recovered.reshape(-1)
            age_ms = (
                (timestamp_ns - state.latest_timestamp_ns) / 1_000_000.0
                if state.latest_timestamp_ns is not None
                else None
            )
            records.append(
                RecoveryRecord(
                    self.condition,
                    attempt_id,
                    frame_id,
                    timestamp_ns,
                    observation_index,
                    side,
                    state_name,
                    state.latest_timestamp_ns,
                    age_ms,
                    state.latest_observation_index,
                    next_direct,
                    reason,
                    None if recovered is None else recovered.copy(),
                    None if state.latest is None else state.latest.copy(),
                )
            )
        return output, records

    def _eligibility_reason(
        self,
        side: str,
        side_index: int,
        state: DirectHistory,
        observation_index: int,
        timestamp_ns: int,
        pose: FloatArray,
        previous_signing: bool,
        other_direct: bool,
    ) -> str:
        cfg = self.eligibility
        if state.missing_run > int(cfg["maximum_recovered_observations_per_gap"]):
            return "consecutive_missing_observation"
        if state.latest is None or state.previous is None:
            return "insufficient_direct_history"
        if (
            state.latest_observation_index != observation_index - 1
            or state.previous_observation_index != observation_index - 2
        ):
            return "nonconsecutive_direct_history"
        if state.latest_timestamp_ns is None or state.previous_timestamp_ns is None:
            return "missing_direct_timestamp"
        age_ms = (timestamp_ns - state.latest_timestamp_ns) / 1_000_000.0
        history_ms = (state.latest_timestamp_ns - state.previous_timestamp_ns) / 1_000_000.0
        if age_ms < 0.0 or age_ms > float(cfg["maximum_recovery_age_ms"]):
            return "recovery_age_exceeded"
        if not (
            float(cfg["minimum_history_dt_ms"])
            <= history_ms
            <= float(cfg["maximum_history_dt_ms"])
        ):
            return "history_interval_out_of_bounds"
        scale = hand_scale(state.latest)
        if not (
            np.isfinite(scale)
            and float(cfg["minimum_hand_scale"])
            <= scale
            <= float(cfg["maximum_hand_scale"])
        ):
            return "degenerate_direct_geometry"
        wrist = state.latest[0, :2]
        previous_wrist = state.previous[0, :2]
        radius = float(np.linalg.norm(wrist))
        if radius > float(cfg["maximum_wrist_radius"]):
            return "wrist_outside_safe_radius"
        radial_delta = radius - float(np.linalg.norm(previous_wrist))
        if (
            radius > float(cfg["outward_motion_radius_threshold"])
            and radial_delta > float(cfg["outward_motion_delta_threshold"])
        ):
            return "outward_motion_risk"
        pose_wrist = pose[POSE_WRISTS[side], :2]
        if not np.isfinite(pose_wrist).all():
            return "pose_wrist_unavailable"
        if float(np.linalg.norm(wrist - pose_wrist)) > float(cfg["maximum_pose_wrist_distance"]):
            return "pose_wrist_conflict"
        if bool(cfg["require_previous_signing_or_other_direct_hand"]) and not (
            previous_signing or other_direct
        ):
            return "no_causal_signing_context"
        return "eligible"

    def _predict_velocity(
        self, state: DirectHistory, timestamp_ns: int
    ) -> FloatArray | None:
        if (
            state.latest is None
            or state.previous is None
            or state.latest_timestamp_ns is None
            or state.previous_timestamp_ns is None
        ):
            return None
        history_dt = (state.latest_timestamp_ns - state.previous_timestamp_ns) / 1e9
        prediction_dt = (timestamp_ns - state.latest_timestamp_ns) / 1e9
        if history_dt <= 0.0 or prediction_dt < 0.0:
            return None
        wrist_velocity = (state.latest[0] - state.previous[0]) / history_dt
        wrist_velocity = clip_vectors(
            wrist_velocity[None, :], float(self.velocity["wrist_velocity_clip_per_second"])
        )[0]
        latest_relative = state.latest - state.latest[0]
        previous_relative = state.previous - state.previous[0]
        relative_velocity = (latest_relative - previous_relative) / history_dt
        relative_velocity = clip_vectors(
            relative_velocity, float(self.velocity["relative_landmark_velocity_clip_per_second"])
        )
        wrist_displacement = clip_vectors(
            (wrist_velocity * prediction_dt)[None, :],
            float(self.velocity["maximum_wrist_displacement"]),
        )[0]
        proposed = state.latest + wrist_displacement + relative_velocity * prediction_dt
        displacement = clip_vectors(
            proposed - state.latest, float(self.velocity["maximum_landmark_displacement"])
        )
        return state.latest + displacement


class S5DeltaReplay:
    """Frozen S5 replay using exact logged C0 inputs plus only recovered-hand motion delta."""

    def __init__(self, recognition_config: dict[str, Any]) -> None:
        self.config = recognition_config
        signing = recognition_config["signing"]
        low = recognition_config["low_fps_s5"]
        self.delta_ring: deque[float] = deque(
            maxlen=max(int(signing["smoothing_window"]), int(low["smoothing_window"]))
        )
        self.signing = False
        self.on_count = 0
        self.off_count = 0

    def update(
        self,
        row: dict[str, Any],
        candidate_feature: FloatArray,
        base_previous: FloatArray | None,
        candidate_previous: FloatArray | None,
    ) -> S5Frame:
        base = np.asarray(row["feature"], dtype=np.float64)
        delta = 0.0
        if base_previous is not None and candidate_previous is not None:
            base_motion = hand_wrist_motion(base_previous, base)
            candidate_motion = hand_wrist_motion(candidate_previous, candidate_feature)
            delta = float(self.config["signing"]["hand_aux_weight"]) * (
                candidate_motion - base_motion
            )
        self.delta_ring.append(delta)
        low = bool(row["low_fps"]) and bool(self.config["low_fps_s5"]["enabled"])
        smoothing = int(
            self.config["low_fps_s5"]["smoothing_window"]
            if low
            else self.config["signing"]["smoothing_window"]
        )
        values = list(self.delta_ring)[-min(smoothing, len(self.delta_ring)) :]
        motion = max(0.0, float(row["s5"]["motion"]) + sum(values) / len(values))
        hands_seen = any(
            hand_present(hand_block(candidate_feature, side_index)) for side_index in range(2)
        )
        raised = bool(row["s5"]["raised_gate"])
        onset_candidate = (
            motion > float(self.config["signing"]["theta_on"])
            and raised
            and hands_seen
        )
        k_on = int(
            self.config["low_fps_s5"]["k_on"] if low else self.config["signing"]["k_on"]
        )
        k_off = int(
            self.config["low_fps_s5"]["k_off"] if low else self.config["signing"]["k_off"]
        )
        event = "NONE"
        if not self.signing:
            if onset_candidate:
                self.on_count += 1
                if self.on_count >= k_on:
                    self.signing = True
                    self.on_count = 0
                    self.off_count = 0
                    event = "ONSET"
            else:
                self.on_count = 0
        else:
            if motion < float(self.config["signing"]["theta_off"]) or not hands_seen:
                self.off_count += 1
                if self.off_count >= k_off:
                    self.signing = False
                    self.on_count = 0
                    self.off_count = 0
                    event = "RELEASE"
            else:
                self.off_count = 0
        return S5Frame(
            frame_id=int(row["frame_id"]),
            event=event,
            signing=self.signing,
            motion=motion,
            hands_seen=hands_seen,
            onset_candidate=onset_candidate,
        )


def hand_wrist_motion(previous: FloatArray, current: FloatArray) -> float:
    distances: list[float] = []
    for side_index in range(2):
        before = hand_block(previous, side_index)
        after = hand_block(current, side_index)
        if hand_present(before) and hand_present(after):
            distances.append(float(np.linalg.norm(after[0, :2] - before[0, :2])))
    return float(np.mean(distances)) if distances else 0.0


def load_package(config: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    package = ROOT / config["source_package"]
    return read_csv(package / "internal_index.csv"), read_csv(package / "annotations.csv")


def load_sequences(index_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for row in index_rows:
        unique.setdefault(
            row["attempt_id"],
            {
                "attempt_id": row["attempt_id"],
                "cohort": row["cohort"],
                "trace_path": row["source_trace_path"],
            },
        )
    sequences: list[dict[str, Any]] = []
    for item in unique.values():
        trace_path = ROOT / item["trace_path"]
        trace = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
        metadata = read_json(trace_path.parent / "metadata.json")
        sequences.append({**item, "trace": trace, "metadata": metadata})
    return sorted(sequences, key=lambda value: value["attempt_id"])


def audit_subset(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = read_json(config_path)
    index_rows, annotation_rows = load_package(config)
    annotations = {row["sample_id"]: row for row in annotation_rows}
    sequences = {row["attempt_id"]: row for row in load_sequences(index_rows)}
    by_attempt: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in index_rows:
        by_attempt[row["attempt_id"]].append(row)
    subset_rows: list[dict[str, Any]] = []
    for attempt_id, rows in by_attempt.items():
        trace = sequences[attempt_id]["trace"]
        positions = {int(row["frame_id"]): index for index, row in enumerate(trace)}
        for row in sorted(rows, key=lambda value: int(value["timestamp_ns"])):
            annotation = annotations[row["sample_id"]]
            position = positions[int(row["frame_id"])]
            for side in SIDES:
                visible = annotation[f"visible_{side}"] == "yes"
                detected = side in (
                    annotation["mp_left_identity"],
                    annotation["mp_right_identity"],
                )
                if not visible or detected:
                    continue
                previous_direct = position > 0 and bool(trace[position - 1][f"{side}_hand_present"])
                next_direct = position + 1 < len(trace) and bool(
                    trace[position + 1][f"{side}_hand_present"]
                )
                two_history = position > 1 and previous_direct and bool(
                    trace[position - 2][f"{side}_hand_present"]
                )
                subset_rows.append(
                    {
                        "sample_id": row["sample_id"],
                        "cohort": row["cohort"],
                        "attempt_id": attempt_id,
                        "frame_id": row["frame_id"],
                        "side": side,
                        "human_recoverability": annotation[f"recoverable_{side}"],
                        "previous_direct": str(previous_direct).lower(),
                        "next_direct": str(next_direct).lower(),
                        "two_consecutive_direct_history": str(two_history).lower(),
                        "scoreable_single_observation": str(
                            annotation[f"recoverable_{side}"] == "yes"
                            and previous_direct
                            and next_direct
                        ).lower(),
                        "candidate_history_ready": str(
                            annotation[f"recoverable_{side}"] == "yes"
                            and next_direct
                            and two_history
                        ).lower(),
                        "leaving_frame": annotation["leaving_frame"],
                        "no_hand_rest": annotation["no_hand_rest"],
                    }
                )
    output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(output_dir / "a2_2r_recovery_subset.csv", subset_rows)
    summary = {
        "experiment_id": config["experiment_id"],
        "selected_frames": len(index_rows),
        "sequences": len(sequences),
        "visible_missing_hand_sides": len(subset_rows),
        "recoverability": dict(
            sorted(Counter(row["human_recoverability"] for row in subset_rows).items())
        ),
        "scoreable_recoverable_single_observation_events": sum(
            row["scoreable_single_observation"] == "true" for row in subset_rows
        ),
        "candidate_history_ready_events": sum(
            row["candidate_history_ready"] == "true" for row in subset_rows
        ),
        "candidate_results_inspected": False,
        "gates_frozen": config["preregistered_gates"],
    }
    write_json(output_dir / "a2_2r_subset_summary.json", summary)
    provenance = build_provenance(config_path, config, output_dir)
    write_json(output_dir / "pre_evaluation_provenance.json", provenance)
    return summary


def build_provenance(
    config_path: Path, config: dict[str, Any], output_dir: Path
) -> dict[str, Any]:
    source_package = ROOT / config["source_package"]
    required = {
        "recovery_evaluator": Path(__file__).resolve(),
        "recovery_config": config_path.resolve(),
        "recovery_runner": ROOT / "model/config/recognition_upgrade/run_a2_recovery.ps1",
        "annotations": source_package / "annotations.csv",
        "internal_index": source_package / "internal_index.csv",
        "sequence_manifest": source_package / "sequence_manifest.csv",
        "baseline_freeze": source_package / "baseline_freeze.json",
        "subset": output_dir / "a2_2r_recovery_subset.csv",
        "subset_summary": output_dir / "a2_2r_subset_summary.json",
        "recognition_config": ROOT / "android/app/src/main/assets/recognition_config.json",
        "model_manifest": ROOT / "android/app/src/main/assets/model_manifest.json",
        "streaming_model": ROOT / "android/app/src/main/assets/streaming.tflite",
        "vocabulary": ROOT / "android/app/src/main/assets/vocab.json",
    }
    freeze = read_json(source_package / "baseline_freeze.json")
    protected: list[dict[str, Any]] = []
    for entry in freeze["protected_files"]:
        path = ROOT / entry["path"]
        current = sha256(path)
        if current != entry["sha256"]:
            raise RuntimeError(f"protected baseline drift: {entry['path']}")
        protected.append({"path": entry["path"], "sha256": current, "matches_frozen": True})
    return {
        "experiment_id": config["experiment_id"],
        "captured_before_evaluation": True,
        "branch": subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True
        ).strip(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "working_tree_status": subprocess.check_output(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT, text=True
        ).splitlines(),
        "required_sha256": {name: sha256(path) for name, path in required.items()},
        "protected_files": protected,
        "hard_boundaries": config["hard_boundaries"],
        "candidate_results_inspected": False,
    }


def verify_provenance(config_path: Path, config: dict[str, Any], output_dir: Path) -> None:
    provenance = read_json(output_dir / "pre_evaluation_provenance.json")
    paths = {
        "recovery_evaluator": Path(__file__).resolve(),
        "recovery_config": config_path.resolve(),
        "recovery_runner": ROOT / "model/config/recognition_upgrade/run_a2_recovery.ps1",
        "annotations": ROOT / config["source_package"] / "annotations.csv",
        "internal_index": ROOT / config["source_package"] / "internal_index.csv",
        "sequence_manifest": ROOT / config["source_package"] / "sequence_manifest.csv",
        "baseline_freeze": ROOT / config["source_package"] / "baseline_freeze.json",
        "subset": output_dir / "a2_2r_recovery_subset.csv",
        "subset_summary": output_dir / "a2_2r_subset_summary.json",
        "recognition_config": ROOT / "android/app/src/main/assets/recognition_config.json",
        "model_manifest": ROOT / "android/app/src/main/assets/model_manifest.json",
        "streaming_model": ROOT / "android/app/src/main/assets/streaming.tflite",
        "vocabulary": ROOT / "android/app/src/main/assets/vocab.json",
    }
    for name, path in paths.items():
        if sha256(path) != provenance["required_sha256"][name]:
            raise RuntimeError(f"STOP: pre-evaluation hash drift: {name}")
    for entry in provenance["protected_files"]:
        if sha256(ROOT / entry["path"]) != entry["sha256"]:
            raise RuntimeError(f"STOP: protected hash drift: {entry['path']}")


def replay_model(
    rows: list[dict[str, Any]],
    s5_frames: list[S5Frame],
    runner: ru_d1.TFLiteRunner,
    recognition_config: dict[str, Any],
    time_window: int,
) -> dict[str, Any]:
    window = np.zeros((time_window, FEATURE_DIM), dtype=np.float32)
    pre_onset: deque[tuple[int, NDArray[np.float32]]] = deque()
    pre_count = int(recognition_config.get("pre_onset", {}).get("frames", 0))
    count = 0
    awaiting_release = False
    bout_probs: list[NDArray[np.float32]] = []
    bout_low: list[bool] = []
    commits: list[tuple[int, int]] = []
    probabilities: list[NDArray[np.float32]] = []
    inference_frames: list[int] = []

    def clear(clear_pre: bool) -> None:
        nonlocal count, awaiting_release, bout_probs, bout_low
        count = 0
        awaiting_release = False
        bout_probs = []
        bout_low = []
        window.fill(0.0)
        if clear_pre:
            pre_onset.clear()

    for row, state in zip(rows, s5_frames, strict=True):
        frame_id = int(row["frame_id"])
        feature = np.asarray(row["feature"], dtype=np.float32)
        if state.event == "ONSET":
            clear(clear_pre=False)
            while pre_onset and count < time_window:
                _, buffered = pre_onset.popleft()
                window[count] = buffered
                count += 1
        elif state.event == "RELEASE":
            clear(clear_pre=True)
            continue
        if not state.signing:
            if pre_count > 0:
                pre_onset.append((frame_id, feature.copy()))
                while len(pre_onset) > pre_count:
                    pre_onset.popleft()
            continue
        if awaiting_release or count >= time_window:
            continue
        window[count] = feature
        count += 1
        probs = runner.infer(window, count - 1)
        probabilities.append(probs)
        inference_frames.append(frame_id)
        bout_probs.append(probs)
        bout_low.append(bool(row["low_fps"]))
        confirmation = ru_d1.confirm(bout_probs, bout_low, recognition_config)
        if confirmation.commit_class >= 0:
            commits.append((frame_id, confirmation.commit_class))
            awaiting_release = True
    return {
        "commits": commits,
        "probabilities": probabilities,
        "inference_frames": inference_frames,
    }


def target_rank(probabilities: list[NDArray[np.float32]], target: int) -> int:
    if not probabilities:
        return -1
    return int(np.where(np.argsort(probabilities[-1])[::-1] == target)[0][0]) + 1


def run_condition(
    condition: str,
    sequences: list[dict[str, Any]],
    config: dict[str, Any],
    recognition_config: dict[str, Any],
    model_manifest: dict[str, Any],
    runner: ru_d1.TFLiteRunner,
    vocab: dict[str, int],
) -> dict[str, Any]:
    sequence_results: list[dict[str, Any]] = []
    provenance_rows: list[dict[str, Any]] = []
    modified_by_attempt: dict[str, dict[int, FloatArray]] = {}
    records_by_attempt: dict[str, dict[tuple[int, str], RecoveryRecord]] = {}
    c0_parity_errors: list[str] = []
    all_recovery_records: list[RecoveryRecord] = []
    for sequence in sequences:
        attempt_id = sequence["attempt_id"]
        trace = sequence["trace"]
        recovery = OneObservationRecovery(condition, config)
        s5 = S5DeltaReplay(recognition_config)
        modified_rows: list[dict[str, Any]] = []
        states: list[S5Frame] = []
        records: dict[tuple[int, str], RecoveryRecord] = {}
        base_previous: FloatArray | None = None
        candidate_previous: FloatArray | None = None
        for index, row in enumerate(trace):
            feature = np.asarray(row["feature"], dtype=np.float64)
            next_feature = (
                np.asarray(trace[index + 1]["feature"], dtype=np.float64)
                if index + 1 < len(trace)
                else None
            )
            candidate, frame_records = recovery.process(
                attempt_id,
                index,
                int(row["frame_id"]),
                int(row["timestamp_ns"]),
                feature,
                s5.signing,
                next_feature,
            )
            state = s5.update(row, candidate, base_previous, candidate_previous)
            if condition == "C0_DIRECT_ONLY" and (
                state.event != row["s5"]["event"]
                or state.signing != bool(row["s5"]["signing"])
            ):
                c0_parity_errors.append(f"{attempt_id}:{row['frame_id']}")
            states.append(state)
            modified_rows.append({**row, "feature": candidate.tolist()})
            for record in frame_records:
                records[(record.frame_id, record.side)] = record
                all_recovery_records.append(record)
                provenance_rows.append(
                    {
                        key: value
                        for key, value in asdict(record).items()
                        if key not in {"recovered_landmarks", "source_landmarks"}
                    }
                )
            base_previous = feature
            candidate_previous = candidate
        replay = replay_model(
            modified_rows,
            states,
            runner,
            recognition_config,
            int(model_manifest["time_window"]),
        )
        target_id = vocab[str(sequence["metadata"]["ground_truth"])]
        onset = int(sequence["metadata"].get("onset_frame", -1))
        release = int(sequence["metadata"].get("release_frame", -1))
        if onset < 0 or release < 0:
            manifest_row = sequence["manifest"]
            onset = int(manifest_row["onset_frame"])
            release = int(manifest_row["release_frame"])
        onsets = [state.frame_id for state in states if state.event == "ONSET"]
        releases = [state.frame_id for state in states if state.event == "RELEASE"]
        commits = replay["commits"]
        sequence_results.append(
            {
                "condition": condition,
                "cohort": sequence["cohort"],
                "attempt_id": attempt_id,
                "ground_truth": sequence["metadata"]["ground_truth"],
                "onsets": "|".join(map(str, onsets)),
                "releases": "|".join(map(str, releases)),
                "false_onsets_outside_span": sum(
                    not (onset <= frame <= release) for frame in onsets
                ),
                "commits": "|".join(str(class_id) for _, class_id in commits),
                "correct_commits": sum(class_id == target_id for _, class_id in commits),
                "wrong_commits": sum(class_id != target_id for _, class_id in commits),
                "false_commits_outside_span": sum(
                    not (onset <= frame <= release) for frame, _ in commits
                ),
                "no_commit": len(commits) == 0,
                "target_rank": target_rank(replay["probabilities"], target_id),
                "target_top5": 0 < target_rank(replay["probabilities"], target_id) <= 5,
            }
        )
        modified_by_attempt[attempt_id] = {
            int(row["frame_id"]): np.asarray(row["feature"], dtype=np.float64)
            for row in modified_rows
        }
        records_by_attempt[attempt_id] = records
    if condition == "C0_DIRECT_ONLY" and c0_parity_errors:
        raise RuntimeError(f"C0 S5 parity failed: {c0_parity_errors[:10]}")
    recovered_records = [
        record for record in all_recovery_records if record.state.startswith("RECOVERED")
    ]
    full_multi_persistence = 0
    previous_by_track: dict[tuple[str, str], RecoveryRecord] = {}
    for record in sorted(
        recovered_records,
        key=lambda value: (value.attempt_id, value.side, value.observation_index),
    ):
        key = (record.attempt_id, record.side)
        previous = previous_by_track.get(key)
        if previous is not None and record.observation_index == previous.observation_index + 1:
            full_multi_persistence += 1
        previous_by_track[key] = record
    return {
        "sequence_rows": sequence_results,
        "provenance_rows": provenance_rows,
        "modified_by_attempt": modified_by_attempt,
        "records_by_attempt": records_by_attempt,
        "c0_parity_errors": c0_parity_errors,
        "full_recovery_safety": {
            "recovered_observations": len(recovered_records),
            "stale_recoveries_at_long_gap_onset": sum(
                not record.next_direct_returned for record in recovered_records
            ),
            "multi_observation_persistence": full_multi_persistence,
            "eligibility_rejections": dict(
                sorted(
                    Counter(
                        record.eligibility_reason
                        for record in all_recovery_records
                        if record.state == "MISSING"
                    ).items()
                )
            ),
        },
    }


def evaluate_selected(
    condition: str,
    index_rows: list[dict[str, str]],
    annotations: dict[str, dict[str, str]],
    sequences: dict[str, dict[str, Any]],
    condition_run: dict[str, Any],
    scoreable: set[tuple[str, str]],
    fingertip_indices: list[int],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    visible_instances = recovered_visible_instances = 0
    visible_frames = covered_frames = 0
    two_visible_frames = two_covered_frames = 0
    recoveries = false_absence = rest = leaving = stale = wrong_hand = swaps = 0
    multi_persistence = 0
    scored_recoveries = 0
    geometry_rows: list[dict[str, Any]] = []
    previous_recovered: set[tuple[str, str]] = set()
    for row in sorted(
        index_rows,
        key=lambda value: (value["attempt_id"], int(value["timestamp_ns"])),
    ):
        attempt_id = row["attempt_id"]
        frame_id = int(row["frame_id"])
        annotation = annotations[row["sample_id"]]
        feature = condition_run["modified_by_attempt"][attempt_id][frame_id]
        records = condition_run["records_by_attempt"][attempt_id]
        visible = {side: annotation[f"visible_{side}"] == "yes" for side in SIDES}
        present = {
            side: hand_present(hand_block(feature, side_index))
            for side_index, side in enumerate(SIDES)
        }
        visible_instances += sum(visible.values())
        recovered_visible_instances += sum(visible[side] and present[side] for side in SIDES)
        if any(visible.values()):
            visible_frames += 1
            covered_frames += int(any(visible[side] and present[side] for side in SIDES))
        if all(visible.values()):
            two_visible_frames += 1
            two_covered_frames += int(all(present.values()))
        current_recovered: set[tuple[str, str]] = set()
        for side_index, side in enumerate(SIDES):
            record = records[(frame_id, side)]
            if not record.state.startswith("RECOVERED"):
                continue
            recoveries += 1
            key = (attempt_id, side)
            current_recovered.add(key)
            multi_persistence += int(key in previous_recovered)
            false_absence += int(annotation[f"visible_{side}"] == "no")
            rest += int(annotation["no_hand_rest"] == "yes")
            leaving += int(annotation["leaving_frame"] == "yes")
            stale += int(not record.next_direct_returned)
            other = SIDES[1 - side_index]
            wrong_hand += int(
                annotation[f"visible_{side}"] == "no"
                and annotation[f"visible_{other}"] == "yes"
            )
            swaps += 0
            if (row["sample_id"], side) not in scoreable or not record.next_direct_returned:
                continue
            next_trace = sequences[attempt_id]["trace"][record.observation_index + 1]
            next_hand = hand_block(np.asarray(next_trace["feature"], dtype=np.float64), side_index)
            if record.recovered_landmarks is None or record.source_landmarks is None:
                continue
            recovered = record.recovered_landmarks
            source = record.source_landmarks
            dt_in = max(record.recovery_age_ms or 0.0, 1e-6) / 1000.0
            dt_out = max(
                (int(next_trace["timestamp_ns"]) - record.timestamp_ns) / 1e9,
                1e-6,
            )
            velocity_in = (recovered - source) / dt_in
            velocity_out = (next_hand - recovered) / dt_out
            geometry_rows.append(
                {
                    "condition": condition,
                    "sample_id": row["sample_id"],
                    "cohort": row["cohort"],
                    "attempt_id": attempt_id,
                    "frame_id": frame_id,
                    "side": side,
                    "reentry_wrist_error": float(
                        np.linalg.norm(recovered[0, :2] - next_hand[0, :2])
                    ),
                    "reentry_mean_landmark_error": float(
                        np.mean(np.linalg.norm(recovered - next_hand, axis=1))
                    ),
                    "reentry_fingertip_error": float(
                        np.mean(
                            np.linalg.norm(
                                recovered[np.asarray(fingertip_indices)]
                                - next_hand[np.asarray(fingertip_indices)],
                                axis=1,
                            )
                        )
                    ),
                    "direct_to_recovered_jump": float(
                        np.mean(np.linalg.norm(recovered - source, axis=1))
                    ),
                    "recovered_to_next_direct_jump": float(
                        np.mean(np.linalg.norm(next_hand - recovered, axis=1))
                    ),
                    "velocity_discontinuity_per_second": float(
                        np.mean(np.linalg.norm(velocity_out - velocity_in, axis=1))
                    ),
                }
            )
            scored_recoveries += 1
        previous_recovered = current_recovered
    geometry = {}
    for field in (
        "reentry_wrist_error",
        "reentry_mean_landmark_error",
        "reentry_fingertip_error",
        "direct_to_recovered_jump",
        "recovered_to_next_direct_jump",
        "velocity_discontinuity_per_second",
    ):
        values = [float(row[field]) for row in geometry_rows]
        geometry[field] = {
            "mean": float(np.mean(values)) if values else None,
            "p50": percentile(values, 50),
            "p95": percentile(values, 95),
            "max": max(values, default=None),
        }
    metrics = {
        "visible_hand_instance_recall": (
            recovered_visible_instances / visible_instances if visible_instances else None
        ),
        "any_hand_coverage": covered_frames / visible_frames if visible_frames else None,
        "complete_two_hand_coverage": (
            two_covered_frames / two_visible_frames if two_visible_frames else None
        ),
        "recovery": {
            "recovered_observations_full_trace": condition_run["full_recovery_safety"][
                "recovered_observations"
            ],
            "recovered_hand_sides_on_selected_frames": recoveries,
            "scoreable_recoveries": scored_recoveries,
            "false_recoveries_on_true_absence": false_absence,
            "recoveries_on_no_hand_rest": rest,
            "recoveries_on_leaving_frames": leaving,
            "stale_recoveries_at_long_gap_onset": condition_run["full_recovery_safety"][
                "stale_recoveries_at_long_gap_onset"
            ],
            "stale_recoveries_on_selected_frames": stale,
            "multi_observation_persistence": condition_run["full_recovery_safety"][
                "multi_observation_persistence"
            ],
            "multi_observation_persistence_on_selected_frames": multi_persistence,
            "identity_swaps": swaps,
            "wrong_hand_recoveries": wrong_hand,
            "eligibility_rejections_full_trace": condition_run["full_recovery_safety"][
                "eligibility_rejections"
            ],
        },
        "geometry": geometry,
    }
    return metrics, geometry_rows


def downstream_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ranks = [int(row["target_rank"]) for row in rows if int(row["target_rank"]) > 0]
    return {
        "attempts": len(rows),
        "s5_onsets": sum(bool(row["onsets"]) for row in rows),
        "s5_releases": sum(bool(row["releases"]) for row in rows),
        "false_onsets_outside_span": sum(int(row["false_onsets_outside_span"]) for row in rows),
        "correct_commits": sum(int(row["correct_commits"]) for row in rows),
        "wrong_commits": sum(int(row["wrong_commits"]) for row in rows),
        "false_commits_outside_span": sum(int(row["false_commits_outside_span"]) for row in rows),
        "no_commit_attempts": sum(bool(row["no_commit"]) for row in rows),
        "target_top5_attempts": sum(bool(row["target_top5"]) for row in rows),
        "median_final_target_rank": float(np.median(ranks)) if ranks else None,
    }


def evaluate(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = read_json(config_path)
    verify_provenance(config_path, config, output_dir)
    index_rows, annotation_rows = load_package(config)
    annotations = {row["sample_id"]: row for row in annotation_rows}
    subset = read_csv(output_dir / "a2_2r_recovery_subset.csv")
    scoreable = {
        (row["sample_id"], row["side"])
        for row in subset
        if row["scoreable_single_observation"] == "true"
    }
    manifest_rows = {
        row["attempt_id"]: row
        for row in read_csv(ROOT / config["source_package"] / "sequence_manifest.csv")
    }
    sequences = load_sequences(index_rows)
    for sequence in sequences:
        sequence["manifest"] = manifest_rows[sequence["attempt_id"]]
    sequence_map = {row["attempt_id"]: row for row in sequences}
    assets = ROOT / "android/app/src/main/assets"
    recognition_config = read_json(assets / "recognition_config.json")
    model_manifest = read_json(assets / "model_manifest.json")
    vocab_value = read_json(assets / "vocab.json")
    vocab = (
        {str(gloss): index for index, gloss in enumerate(vocab_value)}
        if isinstance(vocab_value, list)
        else {str(key): int(value) for key, value in vocab_value.items()}
    )
    runner = ru_d1.TFLiteRunner(assets / "streaming.tflite")
    condition_runs: dict[str, dict[str, Any]] = {}
    selected_metrics: dict[str, dict[str, Any]] = {}
    downstream: dict[str, dict[str, Any]] = {}
    all_geometry_rows: list[dict[str, Any]] = []
    all_sequence_rows: list[dict[str, Any]] = []
    all_provenance_rows: list[dict[str, Any]] = []
    for condition in config["conditions"]:
        run = run_condition(
            condition,
            sequences,
            config,
            recognition_config,
            model_manifest,
            runner,
            vocab,
        )
        condition_runs[condition] = run
        metrics, geometry_rows = evaluate_selected(
            condition,
            index_rows,
            annotations,
            sequence_map,
            run,
            scoreable,
            [int(value) for value in config["velocity"]["fingertip_indices"]],
        )
        selected_metrics[condition] = metrics
        downstream[condition] = downstream_summary(run["sequence_rows"])
        all_geometry_rows.extend(geometry_rows)
        all_sequence_rows.extend(run["sequence_rows"])
        all_provenance_rows.extend(run["provenance_rows"])
    c0 = selected_metrics["C0_DIRECT_ONLY"]
    c0_downstream = downstream["C0_DIRECT_ONLY"]
    gates = config["preregistered_gates"]
    candidate_gates: dict[str, dict[str, bool]] = {}
    scoreable_count = len(scoreable)
    for condition in config["conditions"][1:]:
        metrics = selected_metrics[condition]
        recovery = metrics["recovery"]
        geometry = metrics["geometry"]
        down = downstream[condition]
        visible_gain = metrics["visible_hand_instance_recall"] - c0["visible_hand_instance_recall"]
        two_hand_gain = metrics["complete_two_hand_coverage"] - c0["complete_two_hand_coverage"]
        candidate_gates[condition] = {
            "evidence": scoreable_count
            >= int(gates["minimum_scoreable_recoverable_single_observation_events"]),
            "recovery_count": recovery["scoreable_recoveries"]
            >= int(gates["minimum_recovered_scoreable_events"]),
            "recovery_recall": recovery["scoreable_recoveries"] / scoreable_count
            >= float(gates["minimum_scoreable_recovery_recall"]),
            "coverage": visible_gain
            >= float(gates["minimum_visible_hand_instance_recall_gain"])
            or two_hand_gain >= float(gates["minimum_complete_two_hand_coverage_gain"]),
            "false_absence": recovery["false_recoveries_on_true_absence"]
            <= int(gates["maximum_false_recoveries_on_true_absence"]),
            "no_hand_rest": recovery["recoveries_on_no_hand_rest"]
            <= int(gates["maximum_recoveries_on_no_hand_rest"]),
            "leaving": recovery["recoveries_on_leaving_frames"]
            <= int(gates["maximum_recoveries_on_leaving_frames"]),
            "stale": recovery["stale_recoveries_at_long_gap_onset"]
            <= int(gates["maximum_stale_recoveries_at_long_gap_onset"]),
            "persistence": recovery["multi_observation_persistence"]
            <= int(gates["maximum_multi_observation_persistence"]),
            "identity": recovery["identity_swaps"] <= int(gates["maximum_identity_swaps"])
            and recovery["wrong_hand_recoveries"]
            <= int(gates["maximum_wrong_hand_recoveries"]),
            "geometry": geometry["reentry_wrist_error"]["p95"]
            <= float(gates["maximum_reentry_wrist_error_p95"])
            and geometry["reentry_mean_landmark_error"]["p95"]
            <= float(gates["maximum_reentry_mean_landmark_error_p95"])
            and geometry["reentry_fingertip_error"]["p95"]
            <= float(gates["maximum_reentry_fingertip_error_p95"])
            and geometry["direct_to_recovered_jump"]["p95"]
            <= float(gates["maximum_direct_to_recovered_jump_p95"])
            and geometry["velocity_discontinuity_per_second"]["p95"]
            <= float(gates["maximum_velocity_discontinuity_p95_per_second"]),
            "wrong_commits": down["wrong_commits"] - c0_downstream["wrong_commits"]
            <= int(gates["maximum_wrong_commit_increase"]),
            "no_sign_onsets": down["false_onsets_outside_span"]
            - c0_downstream["false_onsets_outside_span"]
            <= int(gates["maximum_no_sign_false_onset_increase"]),
            "no_sign_commits": down["false_commits_outside_span"]
            - c0_downstream["false_commits_outside_span"]
            <= int(gates["maximum_no_sign_false_commit_increase"]),
        }
    c1_name, c2_name = config["conditions"][1:]
    c1_pass = all(candidate_gates[c1_name].values())
    c2_pass = all(candidate_gates[c2_name].values())
    c1_error = selected_metrics[c1_name]["geometry"]["reentry_mean_landmark_error"]["mean"]
    c2_error = selected_metrics[c2_name]["geometry"]["reentry_mean_landmark_error"]["mean"]
    c2_reduction = (
        (c1_error - c2_error) / c1_error if c1_error is not None and c1_error > 0 else None
    )
    c2_complexity_justified = bool(
        c2_pass
        and (
            not c1_pass
            or (
                c2_reduction is not None
                and c2_reduction
                >= float(gates["minimum_c2_mean_landmark_error_reduction_vs_c1"])
            )
        )
    )
    if c2_complexity_justified:
        decision = "KEEP_C2_ONE_FRAME_VELOCITY"
        next_step = "ANDROID_RECOVERY_IMPLEMENTATION"
    elif c1_pass:
        decision = "KEEP_C1_ONE_FRAME_HOLD"
        next_step = "ANDROID_RECOVERY_IMPLEMENTATION"
    else:
        decision = "REJECT_A2_2R_RECOVERY"
        next_step = "PERCEPTION_BACKEND_REPLACEMENT_STUDY"
    write_csv(output_dir / "a2_2r_provenance.csv", all_provenance_rows)
    write_csv(output_dir / "a2_2r_geometry.csv", all_geometry_rows)
    write_csv(output_dir / "a2_2r_downstream_attempts.csv", all_sequence_rows)
    provenance = read_json(output_dir / "pre_evaluation_provenance.json")
    result = {
        "experiment_id": config["experiment_id"],
        "source_sha256": provenance["required_sha256"],
        "scoreable_recoverable_single_observation_events": scoreable_count,
        "selected_metrics": selected_metrics,
        "downstream_replay": downstream,
        "candidate_gates": candidate_gates,
        "candidate_pass": {c1_name: c1_pass, c2_name: c2_pass},
        "c2_mean_landmark_error_reduction_vs_c1": c2_reduction,
        "c2_complexity_justified": c2_complexity_justified,
        "decision": decision,
        "next_step": next_step,
        "downstream_interpretation": config["downstream_replay"]["x86_tflite_interpretation"],
        "hard_boundaries": config["hard_boundaries"],
    }
    write_json(output_dir / "a2_2r_result.json", result)
    return result


def check(config_path: Path, output_dir: Path, require_result: bool) -> dict[str, Any]:
    config = read_json(config_path)
    errors: list[str] = []
    for name in (
        "a2_2r_recovery_subset.csv",
        "a2_2r_subset_summary.json",
        "pre_evaluation_provenance.json",
    ):
        if not (output_dir / name).is_file():
            errors.append(f"missing {name}")
    if not errors:
        try:
            verify_provenance(config_path, config, output_dir)
        except RuntimeError as exc:
            errors.append(str(exc))
    if require_result:
        for name in (
            "a2_2r_result.json",
            "a2_2r_provenance.csv",
            "a2_2r_geometry.csv",
            "a2_2r_downstream_attempts.csv",
        ):
            if not (output_dir / name).is_file():
                errors.append(f"missing {name}")
    report = {"passed": not errors, "errors": errors, "require_result": require_result}
    write_json(output_dir / "check_report.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("audit", "check", "evaluate"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--require-result", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = read_json(args.config)
    output_dir = args.output_dir or ROOT / config["output_directory"]
    if args.command == "audit":
        result = audit_subset(args.config, output_dir)
    elif args.command == "check":
        result = check(args.config, output_dir, args.require_result)
    else:
        result = evaluate(args.config, output_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
