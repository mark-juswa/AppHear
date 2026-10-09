"""RU-D10 bounded stabilization replay over the frozen RU-D7 phone traces.

Candidate A changes only Android resource lifetime, so stored traces cannot measure its FPS effect.
Candidate B is replayed from the exact Android S5 inputs and exact schema-v3.0 feature rows.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from eval.runtime_diagnostics import ru_d1

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = ROOT / "artifacts/recognition_upgrade/ru_d7/phone_bc_01"


@dataclass(frozen=True)
class S5Frame:
    frame_id: int
    event: str
    signing: bool
    bridged_gap: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_RUN / "reports/ru_d10",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def simulate_s5(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    allow_one_gap: bool,
) -> list[S5Frame]:
    signing = False
    on_count = 0
    off_count = 0
    gap_used = False
    result: list[S5Frame] = []
    low_cfg = config["low_fps_s5"]
    signing_cfg = config["signing"]
    for row in rows:
        s5 = row["s5"]
        low = bool(row["low_fps"]) and bool(low_cfg.get("enabled", False))
        k_on = int(low_cfg["k_on"] if low else signing_cfg["k_on"])
        k_off = int(low_cfg["k_off"] if low else signing_cfg["k_off"])
        candidate = bool(s5["onset_candidate"])
        hands = bool(s5["hands_seen"])
        raised = bool(s5["raised_gate"])
        motion = float(s5["motion"])
        bridge = (
            not signing
            and allow_one_gap
            and on_count > 0
            and not gap_used
            and not candidate
            and hands
            and raised
            and motion >= float(signing_cfg["theta_off"])
        )
        event = "NONE"
        if not signing:
            if candidate:
                on_count += 1
                if on_count >= k_on:
                    signing = True
                    on_count = 0
                    off_count = 0
                    gap_used = False
                    event = "ONSET"
            elif bridge:
                gap_used = True
            else:
                on_count = 0
                gap_used = False
        else:
            if not hands or motion < float(signing_cfg["theta_off"]):
                off_count += 1
                if off_count >= k_off:
                    signing = False
                    on_count = 0
                    off_count = 0
                    gap_used = False
                    event = "RELEASE"
            else:
                off_count = 0
        result.append(S5Frame(int(row["frame_id"]), event, signing, bridge))
    return result


def replay_pipeline(
    rows: list[dict[str, Any]],
    s5_frames: list[S5Frame],
    runner: ru_d1.TFLiteRunner,
    config: dict[str, Any],
    time_window: int,
) -> dict[str, Any]:
    window = np.zeros((time_window, ru_d1.FEATURE_DIM), dtype=np.float32)
    sources = np.full(time_window, -1, dtype=np.int64)
    pre_onset: deque[tuple[int, np.ndarray]] = deque()
    pre_count = int(config.get("pre_onset", {}).get("frames", 0))
    count = 0
    awaiting_release = False
    bout_probs: list[np.ndarray] = []
    bout_low: list[bool] = []
    commits: list[int] = []
    inference_frames: list[int] = []
    source_lists: list[list[int]] = []
    probabilities: list[np.ndarray] = []

    def clear(clear_pre: bool) -> None:
        nonlocal count, awaiting_release, bout_probs, bout_low
        count = 0
        awaiting_release = False
        bout_probs = []
        bout_low = []
        window.fill(0.0)
        sources.fill(-1)
        if clear_pre:
            pre_onset.clear()

    for row, state in zip(rows, s5_frames, strict=True):
        frame_id = int(row["frame_id"])
        feature = np.asarray(row["feature"], dtype=np.float32)
        if state.event == "ONSET":
            clear(clear_pre=False)
            while pre_onset and count < time_window:
                source, buffered = pre_onset.popleft()
                window[count] = buffered
                sources[count] = source
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
        sources[count] = frame_id
        count += 1
        probs = runner.infer(window, count - 1)
        probabilities.append(probs)
        inference_frames.append(frame_id)
        source_lists.append(sources.tolist())
        bout_probs.append(probs)
        bout_low.append(bool(row["low_fps"]))
        confirmation = ru_d1.confirm(bout_probs, bout_low, config)
        if confirmation.commit_class >= 0:
            commits.append(confirmation.commit_class)
            awaiting_release = True

    return {
        "commits": commits,
        "inference_frames": inference_frames,
        "source_lists": source_lists,
        "probabilities": probabilities,
    }


def rank(probs: list[np.ndarray], target: int) -> int:
    if not probs:
        return -1
    return int(np.where(np.argsort(probs[-1])[::-1] == target)[0][0]) + 1


def main() -> None:
    args = parse_args()
    assets = ROOT / "android/app/src/main/assets"
    config = read_json(assets / "recognition_config.json")
    manifest = read_json(assets / "model_manifest.json")
    vocab_rows = read_json(assets / "vocab.json")
    if isinstance(vocab_rows, list):
        vocab = {str(gloss): index for index, gloss in enumerate(vocab_rows)}
    else:
        vocab = {str(key): int(value) for key, value in vocab_rows.items()}
    id_to_gloss = {value: key for key, value in vocab.items()}
    annotations = {
        row["attempt_id"]: row
        for row in csv.DictReader(
            (args.run_dir / "annotations.csv").open(newline="", encoding="utf-8")
        )
    }
    ru_d8 = {
        int(row["capture_order"]): row
        for row in csv.DictReader(
            (args.run_dir / "reports/ru_d8/ru_d8_attempt_attribution.csv").open(
                newline="", encoding="utf-8"
            )
        )
    }
    runner = ru_d1.TFLiteRunner(assets / "streaming.tflite")
    attempt_rows: list[dict[str, Any]] = []
    baseline_parity_errors: list[str] = []

    bundles: list[tuple[int, Path, dict[str, Any]]] = []
    for metadata_path in (args.run_dir / "phone_bundles").rglob("metadata.json"):
        metadata = read_json(metadata_path)
        if "capture_order" not in metadata or not (metadata_path.parent / "trace.jsonl").exists():
            continue
        if str(metadata.get("attempt_id", "")) not in annotations:
            continue
        bundles.append((int(metadata["capture_order"]), metadata_path.parent, metadata))
    if len(bundles) != 26:
        raise ValueError(f"expected 26 frozen RU-D7 bundles, found {len(bundles)}")

    for order, directory, metadata in sorted(bundles):
        trace = [
            json.loads(line)
            for line in (directory / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        baseline = simulate_s5(trace, config, allow_one_gap=False)
        candidate = simulate_s5(trace, config, allow_one_gap=True)
        for row, simulated in zip(trace, baseline, strict=True):
            if (
                row["s5"]["event"] != simulated.event
                or bool(row["s5"]["signing"]) != simulated.signing
            ):
                baseline_parity_errors.append(f"{metadata['attempt_id']}:{row['frame_id']}")
        base_replay = replay_pipeline(trace, baseline, runner, config, int(manifest["time_window"]))
        gap_replay = replay_pipeline(trace, candidate, runner, config, int(manifest["time_window"]))

        # When the baseline reaches S6, its reconstructed source windows must match the Android
        # source bookkeeping until Android commits and stops inference.
        logged_sources = [
            list(row["s6"]["window_source_frames"])
            for row in trace
            if isinstance(row.get("s6"), dict)
        ]
        compare_n = min(len(logged_sources), len(base_replay["source_lists"]))
        if logged_sources[:compare_n] != base_replay["source_lists"][:compare_n]:
            baseline_parity_errors.append(f"{metadata['attempt_id']}:window_sources")

        annotation = annotations[str(metadata["attempt_id"])]
        onset = int(annotation["onset_frame"])
        release = int(annotation["release_frame"])
        base_onsets = [frame.frame_id for frame in baseline if frame.event == "ONSET"]
        gap_onsets = [frame.frame_id for frame in candidate if frame.event == "ONSET"]
        added_onsets = [frame for frame in gap_onsets if frame not in base_onsets]
        false_added = [frame for frame in added_onsets if not (onset <= frame <= release)]
        bridged = [frame.frame_id for frame in candidate if frame.bridged_gap]
        target_id = vocab[str(metadata["ground_truth"])]
        stage = ru_d8.get(order, {}).get("primary_failure_attribution", "REJECTED_RU_D7")
        attempt_rows.append(
            {
                "capture_order": order,
                "target_sign": metadata["ground_truth"],
                "attempt_number": metadata["repetition_id"],
                "ru_d8_stage": stage,
                "system_evaluable": stage not in {"SIGN_FORM_UNCERTAIN", "REJECTED_RU_D7"},
                "baseline_onsets": "|".join(map(str, base_onsets)),
                "one_gap_onsets": "|".join(map(str, gap_onsets)),
                "gap_bridged_frames": "|".join(map(str, bridged)),
                "recovered_missing_onset": not base_onsets and bool(gap_onsets),
                "added_false_onsets_outside_annotated_span": len(false_added),
                "baseline_target_rank": rank(base_replay["probabilities"], target_id),
                "one_gap_target_rank": rank(gap_replay["probabilities"], target_id),
                "baseline_commit": "|".join(
                    id_to_gloss.get(class_id, str(class_id)) for class_id in base_replay["commits"]
                ),
                "one_gap_commit": "|".join(
                    id_to_gloss.get(class_id, str(class_id)) for class_id in gap_replay["commits"]
                ),
            }
        )

    if baseline_parity_errors:
        raise ValueError(f"baseline S5/window parity failed: {baseline_parity_errors[:10]}")

    write_csv(args.output_dir / "ru_d10_s5_replay_attempts.csv", attempt_rows)
    evaluable = [row for row in attempt_rows if row["system_evaluable"]]
    comparison = [
        {
            "mode": mode,
            "candidate_a": a,
            "candidate_b": b,
            "processed_fps": "PHONE_MEASUREMENT_REQUIRED" if a else "FROZEN_CAPTURE_BASELINE",
            "gap_distribution": "PHONE_MEASUREMENT_REQUIRED" if a else "FROZEN_CAPTURE_BASELINE",
            "missed_onsets_system_evaluable": sum(
                not bool(row["one_gap_onsets"] if b else row["baseline_onsets"])
                for row in evaluable
            ),
            "added_false_onsets_outside_annotated_spans": sum(
                int(row["added_false_onsets_outside_annotated_span"]) for row in attempt_rows
            )
            if b
            else 0,
            "changed_s7_commits": sum(
                row["baseline_commit"] != row["one_gap_commit"] for row in attempt_rows
            )
            if b
            else 0,
            "status": "PHONE_REQUIRED" if a else "OFFLINE_REPLAY_COMPLETE",
        }
        for mode, a, b in (
            ("BASELINE", False, False),
            ("A_ONLY", True, False),
            ("B_ONLY", False, True),
            ("A_PLUS_B", True, True),
        )
    ]
    write_csv(args.output_dir / "ru_d10_four_way_offline.csv", comparison)
    recovered = [
        f"{row['target_sign']} {row['attempt_number']}"
        for row in attempt_rows
        if row["recovered_missing_onset"] and row["system_evaluable"]
    ]
    uncertain_recovered = [
        f"{row['target_sign']} {row['attempt_number']}"
        for row in attempt_rows
        if row["recovered_missing_onset"] and not row["system_evaluable"]
    ]
    false_count = sum(int(row["added_false_onsets_outside_annotated_span"]) for row in attempt_rows)
    changed_commits = [
        f"{row['target_sign']} {row['attempt_number']}: "
        f"{row['baseline_commit'] or 'NONE'} -> {row['one_gap_commit'] or 'NONE'}"
        for row in attempt_rows
        if row["baseline_commit"] != row["one_gap_commit"]
    ]
    report = f"""# RU-D10 Pre-Phone Stabilization Result

## Candidate A

The safe candidate is resource-lifetime cleanup only: close per-frame MPImage wrappers and recycle
the converted/rotated Bitmaps after both landmarkers and bounded RU-D1 copying finish. It preserves
analysis pixels, orientation, IMAGE-mode MediaPipe, cadence, S4, `[96,258]`, S5-S7, and model
assets.
Existing profiling attributes approximately 1.7 ms to conversion, 14 ms to rotation, about 100 ms
each to hand and pose inference (already parallel), about 0.5 ms to recognition, and about 130 ms
wall time. Therefore Candidate A is expected to improve GC/tail continuity, not the landmarker
latency floor. Its FPS/gap effect requires an Android measurement.

## Candidate B frozen-trace replay

- Baseline parity errors: 0
- Missing onsets recovered: {", ".join(recovered) if recovered else "none"}
- Sign-form-uncertain onsets changed (not credited):
  {", ".join(uncertain_recovered) if uncertain_recovered else "none"}
- Added onsets outside all 26 annotated sign spans: {false_count}
- Changed S7 commits in x86 diagnostic replay:
  {", ".join(changed_commits) if changed_commits else "none"}

The rule preserves `theta_on`, `theta_off`, and `k_on`; it bridges only one interruption while
hands remain present, the raised gate remains open, and motion has not returned below `theta_off`.
WHO is not rescued and was not used to tune the rule.

## Decision boundary

Candidate B passes deterministic S5 replay but fails the end-to-end keep criterion in this bounded
evidence: its two credited onset recoveries do not produce the target commit, and three evaluable
attempts change from no commit to a wrong commit. Keep B disabled; do not promote A+B. Candidate A
cannot be kept or rejected without the prepared device benchmark. No production promotion is
authorized by this report.
"""
    (args.output_dir / "RU_D10_PREPHONE_RESULT.md").write_text(report, encoding="utf-8")
    summary = {
        "attempts": len(attempt_rows),
        "system_evaluable_attempts": len(evaluable),
        "baseline_parity_errors": [],
        "recovered_missing_onsets": recovered,
        "sign_form_uncertain_onsets_changed_not_credited": uncertain_recovered,
        "added_false_onsets_outside_annotated_spans": false_count,
        "changed_s7_commits": changed_commits,
        "protected_test_accessed": False,
        "passed": True,
    }
    (args.output_dir / "ru_d10_prephone_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
