"""Parse the developer-run RU-D10 four-mode Android timing benchmark."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = ROOT / "artifacts/recognition_upgrade/ru_d10/device_benchmark_01"
MODES = {
    "BASELINE": (False, False),
    "A_ONLY": (True, False),
    "B_ONLY": (False, True),
    "A_PLUS_B": (True, True),
}
NUMBER = r"([-+]?\d+(?:\.\d+)?)"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    return parser.parse_args()


def stat(line: str, name: str) -> tuple[float, float, float]:
    match = re.search(rf"\b{name}_ms={NUMBER}/{NUMBER}/{NUMBER}", line)
    if not match:
        raise ValueError(f"missing {name}_ms in profiler line: {line}")
    return tuple(float(value) for value in match.groups())  # type: ignore[return-value]


def scalar(line: str, name: str) -> float:
    match = re.search(rf"\b{name}={NUMBER}", line)
    if not match:
        raise ValueError(f"missing {name} in profiler line: {line}")
    return float(match.group(1))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for mode, (expected_a, expected_b) in MODES.items():
        path = args.run_dir / "logs" / f"{mode}.log"
        if not path.exists():
            errors.append(f"missing {path}")
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        java_crash = (
            "FATAL EXCEPTION" in text or "AndroidRuntime: Process: com.example.apphear" in text
        )
        native_crash = bool(
            re.search(r"Fatal signal .*pid \d+ \(example\.apphear\)", text)
            or "Cmdline: com.example.apphear" in text
        )
        if java_crash or native_crash:
            errors.append(f"{mode}: Android crash present")
        starts = [line for line in text.splitlines() if "profile_start" in line]
        if not starts:
            errors.append(f"{mode}: profile_start absent")
        elif (
            f"ru_d10_a={str(expected_a).lower()}" not in starts[-1].lower()
            or f"ru_d10_b={str(expected_b).lower()}" not in starts[-1].lower()
        ):
            errors.append(f"{mode}: compiled flag identity does not match expected A/B")
        profile = [
            line
            for line in text.splitlines()
            if "mode=FULL_RECOGNITION" in line and "gap_ms=" in line
        ]
        if len(profile) < 3:
            errors.append(f"{mode}: only {len(profile)} timing windows; need at least 3")
            continue
        stage = {
            name: [stat(line, name) for line in profile]
            for name in (
                "conv",
                "rotate",
                "hand",
                "pose",
                "recog",
                "wall",
                "gap",
            )
        }
        dropped = [scalar(line, "dropped") for line in profile]
        row: dict[str, Any] = {
            "mode": mode,
            "candidate_a": expected_a,
            "candidate_b": expected_b,
            "profile_windows": len(profile),
            "processed_fps_mean": mean(scalar(line, "processed_fps") for line in profile),
            "camera_fps_mean": mean(scalar(line, "camera_fps") for line in profile),
            "dropped_frames_final": int(dropped[-1]),
            "no_hand_s5_onsets": sum(
                "AppHearS5" in line and "ONSET_DIAG" in line for line in text.splitlines()
            ),
            "no_hand_commits": sum(
                "AppHearRecog" in line and "COMMIT '" in line for line in text.splitlines()
            ),
            "java_crash": java_crash,
            "native_crash": native_crash,
        }
        for name, values in stage.items():
            row[f"{name}_ms_mean"] = mean(value[0] for value in values)
            row[f"{name}_ms_p50_mean"] = mean(value[1] for value in values)
            row[f"{name}_ms_p95_max"] = max(value[2] for value in values)
        rows.append(row)
    if rows:
        write_csv(args.run_dir / "ru_d10_device_timing.csv", rows)
    summary = {
        "run_dir": str(args.run_dir),
        "modes_complete": [row["mode"] for row in rows],
        "errors": errors,
        "passed": len(rows) == 4 and not errors,
    }
    (args.run_dir / "ru_d10_device_benchmark_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
