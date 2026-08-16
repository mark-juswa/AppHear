"""RU-D9 observation-continuity and S5 onset root-cause reporting from RU-D7 traces."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = ROOT / "artifacts/recognition_upgrade/ru_d7/phone_bc_01"
DEFAULT_DECISIONS = ROOT / "context/recognition_upgrade/ru_d9_root_cause_decisions.csv"
ROOT_CAUSES = (
    "LOW_TEMPORAL_SAMPLING",
    "HAND_DETECTOR_DROPOUT",
    "TWO_HAND_OCCLUSION_OR_CONTACT",
    "S5_CONSECUTIVE_EVIDENCE_TOO_STRICT",
    "S5_SIGNAL_NOT_RESPONDING_TO_VALID_MOTION",
    "UPSTREAM_POSE_OR_FEATURE_ISSUE",
    "OTHER",
    "UNCERTAIN",
)
TARGET_ORDERS = {1, 17, 4, 19, 24, 2, 6, 14, 22}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_trace(directory: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (directory / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def one_gap_counterfactual(rows: list[dict[str, Any]], k_on: int) -> tuple[bool, int | None]:
    count = 0
    gap_used = False
    for row in rows:
        s5 = row["s5"]
        if s5["onset_candidate"]:
            count += 1
            if count >= k_on:
                return True, int(row["frame_id"])
        elif count > 0 and not gap_used and s5["hands_seen"] and s5["raised_gate"]:
            gap_used = True
        else:
            count = 0
            gap_used = False
    return False, None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    args = parser.parse_args()

    decisions = {int(row["capture_order"]): row for row in read_csv(args.decisions)}
    if set(decisions) != TARGET_ORDERS:
        raise ValueError("RU-D9 decisions must contain exactly the nine approved capture orders")
    if any(row["primary_root_cause"] not in ROOT_CAUSES for row in decisions.values()):
        raise ValueError("unknown RU-D9 root cause")

    annotations = {row["attempt_id"]: row for row in read_csv(args.run_dir / "annotations.csv")}
    ru_d8 = {
        int(row["capture_order"]): row
        for row in read_csv(args.run_dir / "reports/ru_d8/ru_d8_attempt_attribution.csv")
    }
    expected_stage = {
        1: "PERCEPTION_FAILURE",
        17: "PERCEPTION_FAILURE",
        4: "PERCEPTION_FAILURE",
        19: "PERCEPTION_FAILURE",
        24: "PERCEPTION_FAILURE",
        2: "S5_GATE_FAILURE",
        6: "S5_GATE_FAILURE",
        14: "S5_GATE_FAILURE",
        22: "S5_GATE_FAILURE",
    }
    for order, stage in expected_stage.items():
        if ru_d8[order]["primary_failure_attribution"] != stage:
            raise ValueError(f"RU-D8 stage changed for order {order}")

    config = json.loads(
        (ROOT / "android/app/src/main/assets/recognition_config.json").read_text(
            encoding="utf-8-sig"
        )
    )
    theta_on = float(config["signing"]["theta_on"])
    theta_off = float(config["signing"]["theta_off"])
    low_fps_enabled = bool(config["low_fps_s5"]["enabled"])
    output = args.run_dir / "reports/ru_d9"
    timeline_dir = output / "timelines"
    attempt_rows: list[dict[str, Any]] = []

    directories: dict[int, Path] = {}
    for metadata_path in (args.run_dir / "phone_bundles").rglob("metadata.json"):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        order = int(metadata.get("capture_order", 0))
        if order in TARGET_ORDERS:
            directories[order] = metadata_path.parent
    if set(directories) != TARGET_ORDERS:
        raise ValueError("not all RU-D9 attempt bundles are present")

    for order in sorted(TARGET_ORDERS):
        directory = directories[order]
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        annotation = annotations[metadata["attempt_id"]]
        decision = decisions[order]
        all_rows = read_trace(directory)
        by_frame = {int(row["frame_id"]): index for index, row in enumerate(all_rows)}
        onset = int(annotation["onset_frame"])
        release = int(annotation["release_frame"])
        span = [row for row in all_rows if onset <= int(row["frame_id"]) <= release]
        core_start = int(decision["core_start_frame"])
        core_end = int(decision["core_end_frame"])
        core = [row for row in span if core_start <= int(row["frame_id"]) <= core_end]
        expected_hands = metadata["expected_hands"]

        required_present = [
            int(row["hand_count"]) >= (2 if expected_hands == "two" else 1) for row in span
        ]
        core_required = [
            int(row["hand_count"]) >= (2 if expected_hands == "two" else 1) for row in core
        ]
        two_coverage = mean([float(int(row["hand_count"]) >= 2) for row in span])
        pose_coverage = mean([float(bool(row["pose_present"])) for row in span])
        deltas_ms: list[float] = []
        timeline_rows: list[dict[str, Any]] = []
        candidate_run = 0
        for row in span:
            frame_id = int(row["frame_id"])
            trace_index = by_frame[frame_id]
            prior = all_rows[trace_index - 1] if trace_index > 0 else None
            delta_ms = (
                (int(row["timestamp_ns"]) - int(prior["timestamp_ns"])) / 1_000_000
                if prior is not None
                else None
            )
            if delta_ms is not None:
                deltas_ms.append(delta_ms)
            if row["s5"]["onset_candidate"]:
                candidate_run += 1
            else:
                candidate_run = 0
            required = int(row["hand_count"]) >= (2 if expected_hands == "two" else 1)
            effective_k_on = (
                int(config["low_fps_s5"]["k_on"])
                if row["low_fps"] and low_fps_enabled
                else int(config["signing"]["k_on"])
            )
            timeline_rows.append(
                {
                    "attempt_id": metadata["attempt_id"],
                    "target_sign": metadata["ground_truth"],
                    "attempt_number": metadata["repetition_id"],
                    "trace_processed_index": trace_index,
                    "processed_frame_id": frame_id,
                    "timestamp_ns": row["timestamp_ns"],
                    "inter_frame_interval_ms": "" if delta_ms is None else delta_ms,
                    "interval_effective_fps": (
                        "" if not delta_ms or delta_ms <= 0 else 1000.0 / delta_ms
                    ),
                    "logged_processed_fps": row["processed_fps"],
                    "low_fps": row["low_fps"],
                    "in_visual_core": core_start <= frame_id <= core_end,
                    "left_hand_detected": row["left_hand_present"],
                    "right_hand_detected": row["right_hand_present"],
                    "hand_count": row["hand_count"],
                    "required_hands_present": required,
                    "hand_confidence_status": "NOT_CAPTURED_IN_RU_D7_TRACE",
                    "left_hand_confidence": "",
                    "right_hand_confidence": "",
                    "pose_available": row["pose_present"],
                    "pose_fresh": row["pose_fresh"],
                    "pose_left_wrist_visibility": row["pose_visibility"]["left_wrist"],
                    "pose_right_wrist_visibility": row["pose_visibility"]["right_wrist"],
                    "span_required_hand_coverage": mean(
                        [float(value) for value in required_present]
                    ),
                    "span_two_hand_coverage": two_coverage if expected_hands == "two" else "",
                    "s5_motion": row["s5"]["motion"],
                    "s5_theta_on_recorded_contract": theta_on,
                    "s5_theta_off_recorded_contract": theta_off,
                    "s5_hands_seen": row["s5"]["hands_seen"],
                    "s5_raised_gate": row["s5"]["raised_gate"],
                    "s5_onset_candidate": row["s5"]["onset_candidate"],
                    "s5_raw_consecutive_candidate_run": candidate_run,
                    "s5_effective_k_on": effective_k_on,
                    "s5_on_count_after_update": row["s5"]["on_count"],
                    "s5_off_count_after_update": row["s5"]["off_count"],
                    "s5_active_hand_gap_frames": row["s5"]["active_hand_gap_frames"],
                    "s5_release_by_hand_dropout": row["s5"]["release_by_hand_dropout"],
                    "s5_signing_state_after_update": row["s5"]["signing"],
                    "s5_event": row["s5"]["event"],
                }
            )
        timeline_name = (
            f"{order:02d}_{metadata['ground_truth']}_{metadata['repetition_id']}_timeline.csv"
        )
        write_csv(timeline_dir / timeline_name, timeline_rows)

        low_fps_k_on = int(config["low_fps_s5"]["k_on"])
        would_trigger, trigger_frame = one_gap_counterfactual(core, low_fps_k_on)
        candidate_ids = [str(row["frame_id"]) for row in span if row["s5"]["onset_candidate"]]
        events = [
            f"{row['frame_id']}:{row['s5']['event']}"
            for row in span
            if row["s5"]["event"] != "NONE"
        ]
        left_frames = sum(bool(row["left_hand_present"]) for row in span)
        right_frames = sum(bool(row["right_hand_present"]) for row in span)
        actual_transition = "|".join(events) if events else "NO_TRANSITION"
        attempt_rows.append(
            {
                "capture_order": order,
                "target_sign": metadata["ground_truth"],
                "attempt_number": metadata["repetition_id"],
                "ru_d8_stage": ru_d8[order]["primary_failure_attribution"],
                "visual_span": f"{onset}-{release}",
                "visual_core": f"{core_start}-{core_end}",
                "processed_frames_in_span": len(span),
                "span_duration_ms": (
                    (int(span[-1]["timestamp_ns"]) - int(span[0]["timestamp_ns"])) / 1_000_000
                ),
                "mean_logged_processed_fps": mean([float(row["processed_fps"]) for row in span]),
                "mean_inter_frame_interval_ms": mean(deltas_ms),
                "max_inter_frame_interval_ms": max(deltas_ms),
                "low_fps_frames": sum(bool(row["low_fps"]) for row in span),
                "left_hand_detected_frames": left_frames,
                "right_hand_detected_frames": right_frames,
                "required_hand_coverage": mean([float(value) for value in required_present]),
                "core_required_hand_coverage": mean([float(value) for value in core_required]),
                "two_hand_coverage": two_coverage if expected_hands == "two" else "",
                "pose_coverage": pose_coverage,
                "hand_confidence_status": "NOT_CAPTURED_IN_RU_D7_TRACE",
                "s5_candidate_frames": "|".join(candidate_ids),
                "s5_max_motion": max(float(row["s5"]["motion"]) for row in span),
                "s5_actual_transitions": actual_transition,
                "one_gap_counterfactual_trigger": would_trigger,
                "one_gap_counterfactual_trigger_frame": trigger_frame or "",
                "required_landmarks_continuous_in_core": decision["s5_landmarks_continuous"],
                "short_detector_gaps": decision["short_detector_gaps"],
                "gaps_prevented_s5_accumulation": decision["gaps_prevented_s5_accumulation"],
                "one_gap_tolerance_answer": decision["one_gap_tolerance_would_trigger"],
                "s5_signal_weak_with_valid_landmarks": decision[
                    "s5_signal_weak_despite_valid_landmarks"
                ],
                "hand_visible_when_detection_missing": decision[
                    "hand_visible_when_detection_missing"
                ],
                "failure_association": decision["failure_association"],
                "weaker_hand": decision["weaker_hand"],
                "primary_root_cause": decision["primary_root_cause"],
                "secondary_root_causes": decision["secondary_root_causes"],
                "root_cause_reason": decision["root_cause_reason"],
                "timeline_artifact": str((timeline_dir / timeline_name).resolve()),
            }
        )

    write_csv(output / "ru_d9_attempt_root_cause.csv", attempt_rows)
    counts = Counter(row["primary_root_cause"] for row in attempt_rows)
    count_rows = [
        {
            "primary_root_cause": cause,
            "attempt_count": counts[cause],
            "share_of_nine": counts[cause] / len(attempt_rows),
        }
        for cause in ROOT_CAUSES
    ]
    write_csv(output / "ru_d9_aggregated_root_cause_counts.csv", count_rows)

    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in attempt_rows:
        by_class[str(row["target_sign"])].append(row)
    class_rows: list[dict[str, Any]] = []
    for gloss in sorted(by_class):
        rows = by_class[gloss]
        class_counts = Counter(row["primary_root_cause"] for row in rows)
        class_rows.append(
            {
                "target_sign": gloss,
                "attempts": len(rows),
                "primary_causes": "|".join(
                    f"{cause}:{class_counts[cause]}" for cause in ROOT_CAUSES if class_counts[cause]
                ),
                "mean_required_hand_coverage": mean(
                    [float(row["required_hand_coverage"]) for row in rows]
                ),
                "mean_core_required_hand_coverage": mean(
                    [float(row["core_required_hand_coverage"]) for row in rows]
                ),
                "mean_processed_fps": mean(
                    [float(row["mean_logged_processed_fps"]) for row in rows]
                ),
                "class_note": (
                    "Compound S5 plus severe secondary S6 failure; S5 repair cannot solve WHO."
                    if gloss == "WHO"
                    else ""
                ),
            }
        )
    write_csv(output / "ru_d9_class_summary.csv", class_rows)

    result = f"""# RU-D9 Observation Continuity and S5 Root-Cause Result

## Primary root causes

| Root cause | Attempts |
|---|---:|
| TWO_HAND_OCCLUSION_OR_CONTACT | {counts["TWO_HAND_OCCLUSION_OR_CONTACT"]} |
| HAND_DETECTOR_DROPOUT | {counts["HAND_DETECTOR_DROPOUT"]} |
| S5_CONSECUTIVE_EVIDENCE_TOO_STRICT | {counts["S5_CONSECUTIVE_EVIDENCE_TOO_STRICT"]} |
| S5_SIGNAL_NOT_RESPONDING_TO_VALID_MOTION | {counts["S5_SIGNAL_NOT_RESPONDING_TO_VALID_MOTION"]} |
| LOW_TEMPORAL_SAMPLING (primary) | {counts["LOW_TEMPORAL_SAMPLING"]} |

All nine spans ran at roughly 4-5 processed FPS with individual inter-frame gaps reaching about
0.27-0.35 seconds. Low temporal sampling is therefore a pervasive amplifier, but it is not made
the primary cause where the exact processed image already shows a visible hand that MediaPipe
missed, or where continuous landmarks reached S5 and its signal remained weak.

## S5-primary answers

- **KNOW R1:** continuous landmarks; no detector gap in the core; candidate frames 29 and 31;
  the intervening non-candidate resets accumulation. One-gap tolerance would trigger at 31.
- **WE R2:** landmarks in 8/9 core frames; candidates 43, 47, and 49. The decisive 47/49 pair
  is separated by one hands-present non-candidate frame. One-gap tolerance would trigger at 49.
- **WHO R1:** continuous landmarks in all five core frames; no onset candidate because maximum
  smoothed motion is below the recorded onset threshold. Gap tolerance cannot help.
- **WHO R2:** continuous landmarks in all five core frames; only one candidate appears. Gap
  tolerance cannot supply a second response. WHO remains a compound S5 plus severe S6 problem
  (baseline-B oracle ranks 186 and 93); fixing S5 would not solve recognition.

## Ranked engineering recommendation

1. **Improve perception continuity first.** Three cases are dominated by two-hand
   occlusion/contact and two by detector dropout on visibly present hands. This is the largest
   direct root-cause group and affects downstream S5/S6 evidence.
2. **Measure processing-throughput improvement as a cross-cutting lever.** The observed 4-5 FPS
   and long gaps amplify every brief miss, but these nine traces do not prove throughput alone
   would repair the detector or S5. Do not change MediaPipe settings from RU-D9.
3. **Later test bounded S5 one-gap tolerance.** It would counterfactually complete onset for
   KNOW R1 and WE R2, but must be evaluated on a broader no-sign/false-onset set before any change.
4. **Treat WHO as an onset-feature problem, not a gap-tolerance problem.** Its valid small
   face-adjacent motion does not reliably drive the current S5 signal. Any future onset-feature
   experiment must remain separate from WHO's established S6/representation failure.
5. **Leave S6/representation repair for later.** RU-D9 does not alter the RU-D8 S6 findings and
   does not authorize model/data/feature work.

MediaPipe hand confidence/category scores are unavailable because RU-D7 did not capture them.
Pose is available throughout these spans, and RU-D8 found zero S4 mismatch frames, so no case is
attributed to an upstream pose or feature-construction defect.
"""
    (output / "RU_D9_ROOT_CAUSE_RESULT.md").write_text(result, encoding="utf-8")
    print(
        f"RU-D9 complete: attempts={len(attempt_rows)} timelines={len(attempt_rows)} "
        f"counts={dict(counts)} output={output.resolve()}"
    )


if __name__ == "__main__":
    main()
