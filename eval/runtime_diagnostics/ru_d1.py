"""RU-D1: verify Android window replay, compare actual and oracle spans, emit two CSVs.

The analyzer is deliberately small. It will not attribute a failure unless every recorded
Android inference window reconstructs byte-exactly and replays with the same argmax.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ANDROID_ASSETS = ROOT / "android" / "app" / "src" / "main" / "assets"
FEATURE_DIM = 258
@dataclass(frozen=True)
class Annotation:
    attempt_id: str
    onset_frame: int
    release_frame: int
    performance_valid: bool
    required_hand_visible_when_missed: str
    notes: str = ""


@dataclass(frozen=True)
class ConfirmationResult:
    commit_class: int
    commit_frame: int
    final_top1: int
    final_evidence: float
    final_margin: float


@dataclass(frozen=True)
class ReplayResult:
    window_hash_match: bool
    argmax_match: bool
    max_probability_delta: float
    probabilities: tuple[np.ndarray, ...]
    recorded_probabilities: tuple[np.ndarray, ...]
    low_fps: tuple[bool, ...]
    reset_before: tuple[bool, ...]


@dataclass(frozen=True)
class AttemptResult:
    attempt_id: str
    signer_id: str
    ground_truth: str
    expected_hands: str
    attempts_valid: bool
    annotated_onset: int
    annotated_release: int
    processed_frames: int
    hand_coverage: float
    two_hand_coverage: float
    pose_coverage: float
    s4_mismatch_frames: int
    s5_onset_frame: int
    s5_release_frame: int
    actual_top1: str
    actual_ground_truth_rank: int
    oracle_top1: str
    oracle_ground_truth_rank: int
    actual_commit: str
    oracle_commit: str
    final_output: str
    replay_hash_match: bool
    replay_argmax_match: bool
    replay_s7_match: bool
    replay_max_probability_delta: float
    primary_failure: str
    notes: str
    session_id: str = ""
    repetition_id: str = ""
    capture_order: int = 0
    variant: str = ""


class TFLiteRunner:
    def __init__(self, model_path: Path) -> None:
        import tensorflow as tf

        self._interpreter = tf.lite.Interpreter(model_path=str(model_path), num_threads=2)
        # Match Recognizer.load(): pin the dynamic batch signature before allocation so
        # Android and offline replay delegate the same fixed [1,96,258] graph.
        input_detail = self._interpreter.get_input_details()[0]
        fixed_shape = np.asarray(input_detail["shape"], dtype=np.int32)
        fixed_shape[0] = 1
        self._interpreter.resize_tensor_input(
            input_detail["index"], fixed_shape.tolist()
        )
        self._interpreter.allocate_tensors()
        self._input = self._interpreter.get_input_details()[0]
        self._output = self._interpreter.get_output_details()[0]

    def infer(self, window: np.ndarray, index: int) -> np.ndarray:
        self._interpreter.set_tensor(self._input["index"], window[None].astype(np.float32))
        self._interpreter.invoke()
        output = self._interpreter.get_tensor(self._output["index"])
        return np.asarray(output[0, index], dtype=np.float32)


def window_sha256(window: np.ndarray) -> str:
    exact = np.ascontiguousarray(window, dtype="<f4")
    if exact.shape[1:] != (FEATURE_DIM,):
        raise ValueError(f"expected [T,{FEATURE_DIM}], got {exact.shape}")
    return hashlib.sha256(exact.tobytes(order="C")).hexdigest()


def reconstruct_window(
    source_frames: Iterable[int], features_by_frame: dict[int, np.ndarray], time_window: int
) -> np.ndarray:
    sources = list(source_frames)
    if len(sources) != time_window:
        raise ValueError(f"window source count {len(sources)} != contract {time_window}")
    window = np.zeros((time_window, FEATURE_DIM), dtype=np.float32)
    for row, source in enumerate(sources):
        if source < 0:
            continue
        if source not in features_by_frame:
            raise ValueError(f"source frame {source} is absent from trace")
        window[row] = features_by_frame[source]
    return window


def replay_actual(
    rows: list[dict[str, Any]], runner: TFLiteRunner, time_window: int
) -> ReplayResult:
    features = {int(row["frame_id"]): np.asarray(row["feature"], dtype=np.float32) for row in rows}
    all_hashes_match = True
    all_argmax_match = True
    maximum_delta = 0.0
    replayed: list[np.ndarray] = []
    recorded_probabilities: list[np.ndarray] = []
    low_fps: list[bool] = []
    reset_before: list[bool] = []
    for row in rows:
        s6 = row.get("s6")
        if not isinstance(s6, dict):
            continue
        window = reconstruct_window(s6["window_source_frames"], features, time_window)
        all_hashes_match &= window_sha256(window) == s6["window_sha256"]
        probs = runner.infer(window, int(s6["inference_index"]))
        recorded = np.asarray(s6["probabilities"], dtype=np.float32)
        maximum_delta = max(maximum_delta, float(np.max(np.abs(probs - recorded))))
        all_argmax_match &= int(np.argmax(probs)) == int(np.argmax(recorded))
        replayed.append(probs)
        recorded_probabilities.append(recorded)
        low_fps.append(bool(row["low_fps"]))
        reset_before.append(row["s5"]["event"] == "ONSET")
    return ReplayResult(
        all_hashes_match,
        all_argmax_match,
        maximum_delta,
        tuple(replayed),
        tuple(recorded_probabilities),
        tuple(low_fps),
        tuple(reset_before),
    )


def replay_oracle(
    rows: list[dict[str, Any]],
    annotation: Annotation,
    runner: TFLiteRunner,
    time_window: int,
    pre_onset_frames: int,
) -> tuple[tuple[np.ndarray, ...], tuple[bool, ...]]:
    ordered = sorted(rows, key=lambda row: int(row["frame_id"]))
    by_id = {int(row["frame_id"]): row for row in ordered}
    span_ids = [
        frame_id
        for frame_id in sorted(by_id)
        if annotation.onset_frame <= frame_id <= annotation.release_frame
    ]
    if not span_ids:
        raise ValueError(f"{annotation.attempt_id}: annotated span has no traced frames")
    prior = [frame_id for frame_id in sorted(by_id) if frame_id < span_ids[0]][-pre_onset_frames:]
    source_ids = prior + span_ids
    source_ids = source_ids[:time_window]
    probabilities: list[np.ndarray] = []
    low_fps: list[bool] = []
    for index in range(len(source_ids)):
        window = np.zeros((time_window, FEATURE_DIM), dtype=np.float32)
        for row_index, frame_id in enumerate(source_ids[: index + 1]):
            window[row_index] = np.asarray(by_id[frame_id]["feature"], dtype=np.float32)
        probabilities.append(runner.infer(window, index))
        low_fps.append(bool(by_id[source_ids[index]]["low_fps"]))
    return tuple(probabilities), tuple(low_fps)


def confirm(
    probabilities: Iterable[np.ndarray],
    low_fps: Iterable[bool],
    config: dict[str, Any],
    reset_before: Iterable[bool] | None = None,
) -> ConfirmationResult:
    probs_list = list(probabilities)
    low_list = list(low_fps)
    reset_list = list(reset_before) if reset_before is not None else [False] * len(probs_list)
    if not probs_list:
        return ConfirmationResult(-1, -1, -1, float("-inf"), 0.0)
    sums = np.zeros(len(probs_list[0]), dtype=np.float64)
    previous = -1
    streak = 0
    final_top1 = -1
    final_a1 = float("-inf")
    final_margin = 0.0
    bout_count = 0
    low_cfg = config.get("low_fps_confirmation", {})
    for frame, (probs, is_low, reset) in enumerate(
        zip(probs_list, low_list, reset_list, strict=True)
    ):
        if reset:
            sums.fill(0.0)
            previous = -1
            streak = 0
            bout_count = 0
        bout_count += 1
        logits = np.log(np.clip(probs.astype(np.float64), 1e-8, 1.0)) / float(config["temperature"])
        logits -= np.max(logits)
        logp = logits - np.log(np.exp(logits).sum())
        sums += logp
        evidence = sums / (frame + 1)
        order = np.argsort(evidence)[::-1]
        top1, top2 = int(order[0]), int(order[1])
        streak = streak + 1 if top1 == previous else 1
        previous = top1
        final_top1 = top1
        final_a1 = float(evidence[top1])
        final_margin = float(evidence[top1] - evidence[top2])
        low_mode = is_low and bool(low_cfg.get("enabled", False))
        theta = (
            float(low_cfg.get("theta_conf", config["theta_conf"]))
            if low_mode
            else float(config["theta_conf"])
        )
        margin = (
            float(low_cfg.get("theta_margin", config["theta_margin"]))
            if low_mode
            else float(config["theta_margin"])
        )
        stability = (
            int(low_cfg.get("k_stability", config["k_stability"]))
            if low_mode
            else int(config["k_stability"])
        )
        minimum_frame = int(low_cfg.get("min_commit_frame", 0)) if low_mode else 0
        commit_frame = bout_count - 1
        if (
            final_a1 >= theta
            and final_margin >= margin
            and streak >= stability
            and commit_frame >= minimum_frame
        ):
            return ConfirmationResult(top1, commit_frame, final_top1, final_a1, final_margin)
    return ConfirmationResult(-1, -1, final_top1, final_a1, final_margin)


def top_rank(probabilities: Iterable[np.ndarray], class_id: int) -> tuple[int, int]:
    rows = list(probabilities)
    if not rows:
        return -1, -1
    final = rows[-1]
    return int(np.argmax(final)), int(np.where(np.argsort(final)[::-1] == class_id)[0][0]) + 1


def classify_failure(
    annotation: Annotation,
    hand_miss_observed: bool,
    s4_mismatch_frames: int,
    ground_truth_id: int,
    actual_commit: int,
    oracle_confirmation: ConfirmationResult,
) -> str:
    if not annotation.performance_valid:
        return "INVALID_OR_VARIANT_MISMATCH"
    # A transient upstream defect is health evidence, but it is not the primary cause
    # of failure when the end-to-end output is already correct.
    if actual_commit == ground_truth_id:
        return "CORRECT"
    visual = annotation.required_hand_visible_when_missed.strip().lower()
    if visual == "true" and hand_miss_observed:
        return "MEDIAPIPE_DETECTION_FAILURE"
    if s4_mismatch_frames > 0:
        return "S4_FEATURE_FAILURE"
    if oracle_confirmation.commit_class == ground_truth_id:
        return "S5_FAILURE"
    if oracle_confirmation.final_top1 == ground_truth_id:
        return "S7_FAILURE"
    # RU-D1 stops here; data, generalization, ranking, and representation are later work.
    return "S6_RECOGNITION_FAILURE"


def analyze_attempt(
    directory: Path,
    annotation: Annotation | None,
    runner: TFLiteRunner,
    manifest: dict[str, Any],
    config: dict[str, Any],
    vocab: dict[str, int],
    assets: Path = ANDROID_ASSETS,
) -> AttemptResult:
    metadata = read_json(directory / "metadata.json")
    verify_artifacts(metadata, manifest, config, directory, assets)
    trace_lines = (directory / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in trace_lines]
    attempt_id = str(metadata["attempt_id"])
    ground_truth = str(metadata["ground_truth"])
    ground_truth_id = int(vocab[ground_truth])
    if annotation is None:
        return AttemptResult(
            attempt_id,
            str(metadata["signer_id"]),
            ground_truth,
            str(metadata["expected_hands"]),
            False,
            -1,
            -1,
            len(rows),
            0.0,
            0.0,
            0.0,
            0,
            -1,
            -1,
            "",
            -1,
            "",
            -1,
            "",
            "",
            "",
            False,
            False,
            False,
            float("inf"),
            "INSUFFICIENT_EVIDENCE",
            "annotation missing",
        )

    replay = replay_actual(rows, runner, int(manifest["time_window"]))
    oracle_probs, oracle_low = replay_oracle(
        rows,
        annotation,
        runner,
        int(manifest["time_window"]),
        int(config.get("pre_onset", {}).get("frames", 0)),
    )
    # Android S7 consumes the recorded Android posterior. Replaying S7 from the x86
    # posterior would turn permitted cross-runtime quantization deltas into false S7
    # mismatches even when window hashes and class ranking agree.
    actual_confirmation = confirm(
        replay.recorded_probabilities,
        replay.low_fps,
        config,
        reset_before=replay.reset_before,
    )
    oracle_confirmation = confirm(oracle_probs, oracle_low, config)
    actual_top1, actual_rank = top_rank(replay.recorded_probabilities, ground_truth_id)
    oracle_top1, oracle_rank = top_rank(oracle_probs, ground_truth_id)
    span = [
        row
        for row in rows
        if annotation.onset_frame <= int(row["frame_id"]) <= annotation.release_frame
    ]
    expected = str(metadata["expected_hands"])
    hand_coverage = float(np.mean([row["hand_count"] >= 1 for row in span])) if span else 0.0
    two_coverage = float(np.mean([row["hand_count"] >= 2 for row in span])) if span else 0.0
    pose_coverage = float(np.mean([row["pose_present"] for row in span])) if span else 0.0
    hand_miss = any(row["hand_count"] < (2 if expected == "two" else 1) for row in span)
    s4_mismatch_frames = sum(s4_mismatch(row) for row in span)
    onset = next((int(row["frame_id"]) for row in rows if row["s5"]["event"] == "ONSET"), -1)
    release = next((int(row["frame_id"]) for row in rows if row["s5"]["event"] == "RELEASE"), -1)
    logged_commit = next(
        (
            int(row["s7"]["committed_class"])
            for row in rows
            if row["s7"]["committed_class"] is not None
        ),
        -1,
    )
    s7_replay_match = actual_confirmation.commit_class == logged_commit
    primary = (
        "REPLAY_PARITY_FAILURE"
        if (
            not replay.window_hash_match
            or not replay.argmax_match
            or not s7_replay_match
        )
        else ""
    )
    if not primary:
        primary = classify_failure(
            annotation,
            hand_miss,
            s4_mismatch_frames,
            ground_truth_id,
            logged_commit,
            oracle_confirmation,
        )
    id_to_gloss = {class_id: gloss for gloss, class_id in vocab.items()}

    def gloss(class_id: int) -> str:
        return id_to_gloss.get(class_id, "")

    return AttemptResult(
        attempt_id=attempt_id,
        signer_id=str(metadata["signer_id"]),
        ground_truth=ground_truth,
        expected_hands=expected,
        attempts_valid=annotation.performance_valid,
        annotated_onset=annotation.onset_frame,
        annotated_release=annotation.release_frame,
        processed_frames=len(rows),
        hand_coverage=hand_coverage,
        two_hand_coverage=two_coverage,
        pose_coverage=pose_coverage,
        s4_mismatch_frames=s4_mismatch_frames,
        s5_onset_frame=onset,
        s5_release_frame=release,
        actual_top1=gloss(actual_top1),
        actual_ground_truth_rank=actual_rank,
        oracle_top1=gloss(oracle_top1),
        oracle_ground_truth_rank=oracle_rank,
        actual_commit=gloss(actual_confirmation.commit_class),
        oracle_commit=gloss(oracle_confirmation.commit_class),
        final_output=gloss(logged_commit),
        replay_hash_match=replay.window_hash_match,
        replay_argmax_match=replay.argmax_match,
        replay_s7_match=s7_replay_match,
        replay_max_probability_delta=replay.max_probability_delta,
        primary_failure=primary,
        notes=annotation.notes,
        session_id=str(metadata.get("session_id", "")),
        repetition_id=str(metadata.get("repetition_id", "")),
        capture_order=int(metadata.get("capture_order", 0)),
        variant=str(metadata.get("variant", "")),
    )


def s4_mismatch(row: dict[str, Any]) -> int:
    blocks = row["feature_blocks"]
    mirrored = bool(row["mirrored"])
    raw_left = bool(row["left_hand_present"])
    raw_right = bool(row["right_hand_present"])
    expected_left = raw_right if mirrored else raw_left
    expected_right = raw_left if mirrored else raw_right
    mismatch = expected_left and not bool(blocks["left_nonzero"])
    mismatch |= expected_right and not bool(blocks["right_nonzero"])
    mismatch |= bool(row["pose_present"]) and not bool(blocks["pose_nonzero"])
    mismatch |= not bool(blocks["all_finite"])
    return int(mismatch)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    """Read Android JSON assets while accepting their optional UTF-8 BOM."""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def verify_artifacts(
    metadata: dict[str, Any],
    manifest: dict[str, Any],
    config: dict[str, Any],
    directory: Path,
    assets: Path,
) -> None:
    if int(manifest["feature_dim"]) != FEATURE_DIM or int(manifest["time_window"]) != 96:
        raise ValueError(f"{directory.name}: analyzer requires the deployed [96,258] contract")
    expected = {
        "schema_version": str(manifest["schema_version"]),
        "feature_dim": int(manifest["feature_dim"]),
        "time_window": int(manifest["time_window"]),
        "model_manifest_sha256": file_sha256(assets / "model_manifest.json"),
        "model_sha256": file_sha256(assets / "streaming.tflite"),
        "recognition_config_sha256": file_sha256(assets / "recognition_config.json"),
    }
    del config  # Its content is guarded by recognition_config_sha256 above.
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError(
                f"{directory.name}: captured {key}={metadata.get(key)!r} != analyzer {value!r}"
            )


def read_annotations(path: Path) -> dict[str, Annotation]:
    with path.open(newline="", encoding="utf-8") as handle:
        result = {}
        for row in csv.DictReader(handle):
            annotation = Annotation(
                attempt_id=row["attempt_id"],
                onset_frame=int(row["onset_frame"]),
                release_frame=int(row["release_frame"]),
                performance_valid=row["performance_valid"].strip().lower() == "true",
                required_hand_visible_when_missed=row["required_hand_visible_when_missed"]
                .strip()
                .lower(),
                notes=row.get("notes", ""),
            )
            result[annotation.attempt_id] = annotation
        return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def class_health(results: list[AttemptResult]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for gloss in sorted({result.ground_truth for result in results}):
        rows = [result for result in results if result.ground_truth == gloss]
        counts: dict[str, int] = {}
        for row in rows:
            counts[row.primary_failure] = counts.get(row.primary_failure, 0) + 1
        dominant = max(counts, key=counts.get) if counts else "INSUFFICIENT_EVIDENCE"
        output.append(
            {
                "gloss": gloss,
                "attempts": len(rows),
                "signers": len({row.signer_id for row in rows}),
                "e2e_correct_rate": (
                    sum(row.primary_failure == "CORRECT" for row in rows) / len(rows)
                ),
                "mean_hand_coverage": float(np.mean([row.hand_coverage for row in rows])),
                "mean_two_hand_coverage": float(np.mean([row.two_hand_coverage for row in rows])),
                "mean_pose_coverage": float(np.mean([row.pose_coverage for row in rows])),
                "dominant_failure": dominant,
                "failure_counts": json.dumps(counts, sort_keys=True),
                "recommended_next_stage": recommendation(dominant),
            }
        )
    return output


def recommendation(failure: str) -> str:
    return {
        "CORRECT": "HEALTHY_CONTROL",
        "MEDIAPIPE_DETECTION_FAILURE": "RUNTIME_PERCEPTION_REVIEW",
        "S4_FEATURE_FAILURE": "S4_FIX",
        "S5_FAILURE": "S5_FIX",
        "S6_RECOGNITION_FAILURE": "LATER_S6_ROOT_CAUSE_REVIEW",
        "S7_FAILURE": "LATER_S7_REVIEW",
        "INVALID_OR_VARIANT_MISMATCH": "RECORD_VALID_VARIANT",
    }.get(failure, "INSUFFICIENT_EVIDENCE")


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal RU-D1 failure attribution")
    parser.add_argument("attempt_root", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assets", type=Path, default=ANDROID_ASSETS)
    args = parser.parse_args()

    manifest = read_json(args.assets / "model_manifest.json")
    config = read_json(args.assets / "recognition_config.json")
    vocab = read_json(args.assets / "vocab.json")
    annotations = read_annotations(args.annotations)
    runner = TFLiteRunner(args.assets / "streaming.tflite")
    directories = sorted(path.parent for path in args.attempt_root.rglob("metadata.json"))
    results = [
        analyze_attempt(
            directory,
            annotations.get(directory.name),
            runner,
            manifest,
            config,
            vocab,
            args.assets,
        )
        for directory in directories
    ]
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "attempt_diagnostics.csv", [asdict(result) for result in results])
    write_csv(args.output / "class_health.csv", class_health(results))


if __name__ == "__main__":
    main()
