"""Capture one conversation-flow session from a USB phone (Phase 0 baseline / Phase 1 runs).

Records a thermal/battery pre-check, the `AppHearTurn` logcat stream and periodic total-PSS
samples for the app and WebView renderer processes. Stop with Ctrl+C (or `--duration`), then
run `summarize_timeline.py <out>`. Requires a debug build with `-PconversationTimeline=true`.
The phone must not be throttled for a valid run: use `--require-cool` to refuse otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

PACKAGE = "com.example.apphear"
# Renderer processes run under the WebView provider with isolated uids; on the dedicated test
# phone they belong to the app under test. Their PSS is reported separately from the app's.
RENDERER_MARKER = "webview:sandboxed_process"
MIN_BATTERY_PERCENT = 40
TOTAL_PSS = re.compile(r"TOTAL(?: PSS)?:?\s+(\d+)")


def adb(adb_path: str, *args: str, timeout: float = 30) -> str:
    result = subprocess.run(
        [adb_path, *args], capture_output=True, text=True, timeout=timeout, check=False
    )
    return result.stdout


def precheck(adb_path: str) -> dict[str, Any]:
    battery = adb(adb_path, "shell", "dumpsys", "battery")
    level = re.search(r"level:\s*(\d+)", battery)
    temperature = re.search(r"temperature:\s*(\d+)", battery)
    status = re.search(r"status:\s*(\d+)", battery)
    policies: dict[str, dict[str, int]] = {}
    listing = adb(adb_path, "shell", "ls", "/sys/devices/system/cpu/cpufreq/")
    for policy in sorted(name for name in listing.split() if name.startswith("policy")):
        base = f"/sys/devices/system/cpu/cpufreq/{policy}"
        values = adb(
            adb_path, "shell", "cat", f"{base}/scaling_max_freq", f"{base}/cpuinfo_max_freq"
        ).split()
        if len(values) == 2 and all(value.isdigit() for value in values):
            policies[policy] = {
                "scaling_max_khz": int(values[0]),
                "cpuinfo_max_khz": int(values[1]),
            }
    throttled = [
        name for name, freq in policies.items() if freq["scaling_max_khz"] < freq["cpuinfo_max_khz"]
    ]
    return {
        "device": adb(adb_path, "shell", "getprop", "ro.product.model").strip(),
        "android": adb(adb_path, "shell", "getprop", "ro.build.version.release").strip(),
        "battery_percent": int(level.group(1)) if level else None,
        "battery_temp_c": int(temperature.group(1)) / 10 if temperature else None,
        "battery_status": int(status.group(1)) if status else None,
        "cpu_policies": policies,
        "throttled_policies": throttled,
        "wall_ms": int(time.time() * 1000),
    }


def process_pss(adb_path: str) -> dict[str, Any]:
    processes: list[dict[str, Any]] = []
    for line in adb(adb_path, "shell", "ps", "-A", "-o", "PID,NAME").splitlines()[1:]:
        parts = line.split()
        if len(parts) != 2:
            continue
        pid, name = parts
        if not (name.startswith(PACKAGE) or RENDERER_MARKER in name):
            continue
        match = TOTAL_PSS.search(adb(adb_path, "shell", "dumpsys", "meminfo", pid))
        if match:
            processes.append({"pid": int(pid), "name": name, "pss_kb": int(match.group(1))})
    return {
        "w": int(time.time() * 1000),
        "processes": processes,
        "total_pss_kb": sum(process["pss_kb"] for process in processes),
    }


def recover_buffered_events(adb_path: str, timeline: Path) -> int:
    """Append events the streaming logcat had not flushed when it was stopped.

    logcat block-buffers when writing to a file, so terminating it loses the tail. The device
    buffer (cleared at capture start) still holds every event; lines already captured are kept
    once. Returns the number of recovered lines.
    """
    captured = set(timeline.read_text(encoding="utf-8", errors="replace").splitlines())
    dump = adb(adb_path, "logcat", "-d", "-v", "epoch", "-s", "AppHearTurn:I", timeout=60)
    missing = [line for line in dump.splitlines() if "AppHearTurn" in line and line not in captured]
    if missing:
        with timeline.open("a", encoding="utf-8") as log_file:
            log_file.write("\n".join(missing) + "\n")
    return len(missing)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path, help="New output directory for this run")
    parser.add_argument("--adb", default=os.environ.get("ADB", "adb"))
    parser.add_argument("--meminfo-interval", type=float, default=5.0)
    parser.add_argument("--duration", type=float, default=None, help="Seconds; default Ctrl+C")
    parser.add_argument(
        "--stop-file",
        type=Path,
        default=None,
        help="End the capture cleanly when this file appears (for unattended runs)",
    )
    parser.add_argument(
        "--require-cool",
        action="store_true",
        help="Refuse to start when throttled or battery is low",
    )
    args = parser.parse_args(argv)
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=False)

    check = precheck(args.adb)
    (out / "precheck.json").write_text(json.dumps(check, indent=2), encoding="utf-8")
    cool = (
        not check["throttled_policies"] and (check["battery_percent"] or 0) >= MIN_BATTERY_PERCENT
    )
    print(json.dumps(check, indent=2))
    if args.require_cool and not cool:
        print(
            "Phone is throttled or battery is low; let it cool/charge and retry.", file=sys.stderr
        )
        return 2

    adb(args.adb, "logcat", "-c")
    with (out / "timeline.log").open("w", encoding="utf-8") as log_file:
        logcat = subprocess.Popen(
            [args.adb, "logcat", "-v", "epoch", "-s", "AppHearTurn:I"],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        started = time.monotonic()
        print("Capturing. Run the scripted dialogue now; Ctrl+C to stop.")
        try:
            with (out / "meminfo.jsonl").open("w", encoding="utf-8") as memory_file:
                while args.duration is None or time.monotonic() - started < args.duration:
                    if args.stop_file is not None and args.stop_file.exists():
                        break
                    memory_file.write(json.dumps(process_pss(args.adb)) + "\n")
                    memory_file.flush()
                    time.sleep(args.meminfo_interval)
        except KeyboardInterrupt:
            pass
        finally:
            logcat.terminate()
            logcat.wait(timeout=10)
    recover_buffered_events(args.adb, out / "timeline.log")
    (out / "postcheck.json").write_text(json.dumps(precheck(args.adb), indent=2), encoding="utf-8")
    print(f"Saved {out}. Next: python -m tools.conversation_flow.summarize_timeline {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
