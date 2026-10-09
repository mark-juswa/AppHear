"""Read only this experiment's device JSON and verify protected host identities."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.sequence_manifest import REPO
from tools.fingerspelling.android_export import OUT

ALLOWED = {
    "android/app/src/main/java/com/example/apphear/RecognitionActivity.kt",
    "android/app/src/main/java/com/example/apphear/perceptionvnext/Candidate01FrameAnalyzer.kt",
}


def preservation() -> None:
    before = json.loads((OUT / "preservation.json").read_text())
    changed = [
        Path(name).as_posix() for name, digest in before.items() if sha256(REPO / name) != digest
    ]
    unexpected = sorted(set(changed) - ALLOWED)
    report = {
        "status": "PRESERVATION_PASS" if not unexpected else "PRESERVATION_FAILED",
        "files_checked": len(before),
        "intentional_routing_ui_changes": changed,
        "unexpected_changes": unexpected,
    }
    (OUT / "preservation_result.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if unexpected:
        raise ValueError("Protected source changed")


def pull(adb: str) -> None:
    def command(*args: str) -> str:
        result = subprocess.run([adb, *args], capture_output=True, text=True, check=True)
        return result.stdout

    devices = [row for row in command("devices").splitlines()[1:] if "\tdevice" in row]
    if len(devices) != 1:
        raise ValueError("Exactly one authorized target phone required")
    directory = OUT / "phone"
    directory.mkdir(exist_ok=True)
    parity = json.loads(
        command("shell", "run-as", "com.example.apphear", "cat", "files/fingerspell_parity.json")
    )
    (directory / "parity.json").write_text(json.dumps(parity, indent=2))
    listing = subprocess.run(
        [adb, "shell", "run-as", "com.example.apphear", "ls", "files/fingerspelling_sessions"],
        capture_output=True,
        text=True,
    )
    sessions = []
    for name in listing.stdout.splitlines():
        if not re.fullmatch(r"session_\d+\.json", name):
            continue
        record = json.loads(
            command(
                "shell",
                "run-as",
                "com.example.apphear",
                "cat",
                f"files/fingerspelling_sessions/{name}",
            )
        )
        (directory / name).write_text(json.dumps(record, indent=2))
        sessions.append(
            {
                "file": name,
                "observations": record["observations"],
                "cadence": record["observations_per_second"],
                "finish_ms": record["finish_ms"],
                "raw_prediction": record["raw_prediction"],
                "retained_slots": record["retained_slots"],
            }
        )
    summary = {
        "status": "PHONE_EVIDENCE_READ",
        "parity": parity["status"],
        "sessions": sessions,
        "accuracy_claim": "NONE",
        "expected_transcripts": "USER_REVIEW_REQUIRED",
    }
    (directory / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["preservation", "pull"])
    parser.add_argument("--adb", default=r"D:\AndroidStudio\Android\Sdk\platform-tools\adb.exe")
    args = parser.parse_args()
    preservation() if args.action == "preservation" else pull(args.adb)
