"""Private phone-only staging, bounded diagnostics and protected file inventory."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from model.fingerspelling_single_letter import decode_single_letter
from pipeline.fingerspelling.adapter import sha256
from tools.fingerspelling.android_export import write_json
from tools.fingerspelling.android_sequence_v2_1_evidence import ADB, SERIAL
from tools.fingerspelling.single_letter_port import APP, DEVICE, MAIN, OLD, OUT


def stage() -> None:
    if not (OUT / "jvm_parity.json").is_file():
        raise ValueError("Host parity must precede APK staging")
    destination = OUT / "private_apks"
    destination.mkdir(exist_ok=True)
    paths = {
        "app-debug-private-single-letter.apk": APP
        / "android/app/build/outputs/apk/debug/app-debug.apk",
        "app-debug-androidTest.apk": APP
        / "android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk",
    }
    for name, path in paths.items():
        shutil.copyfile(path, destination / name)
    import hashlib

    with (
        zipfile.ZipFile(destination / "app-debug-private-single-letter.apk") as current,
        zipfile.ZipFile(OLD / "private_apks/app-debug-private-v2-1.apk") as previous,
    ):
        # Model package and every existing application asset remain byte-identical.
        before = {
            p: hashlib.sha256(previous.read(p)).hexdigest()
            for p in previous.namelist()
            if p.startswith("assets/")
        }
        after = {
            p: hashlib.sha256(current.read(p)).hexdigest()
            for p in current.namelist()
            if p.startswith("assets/")
        }
        assert before == after, "Application assets changed"
    suites = [
        ET.parse(p).getroot()
        for p in (APP / "android/app/build/test-results/testDebugUnitTest").glob("TEST-*.xml")
    ]
    totals = {
        k: sum(int(r.get(k, "0")) for r in suites)
        for k in ["tests", "failures", "errors", "skipped"]
    }
    assert totals["tests"] and totals["failures"] == totals["errors"] == 0
    report = {
        "private_phone_only": True,
        "identical_application_assets": len(before),
        "artifacts": {
            n: {"sha256": sha256(destination / n), "bytes": (destination / n).stat().st_size}
            for n in paths
        },
        "host_unit_tests": totals,
        "rollback_apk": str(OLD / "private_apks/app-debug-private-v2-1.apk"),
        "model_checkpoint_changed": False,
    }
    write_json(OUT / "apk_identities.json", report)
    print(json.dumps(report, indent=2))


def adb(*args: str) -> str:
    return subprocess.check_output([ADB, "-s", SERIAL, *args], text=True, encoding="utf-8").strip()


def install() -> None:
    assert adb("get-state") == "device"
    identities = json.loads((OUT / "apk_identities.json").read_text())
    for name, item in identities["artifacts"].items():
        path = OUT / "private_apks" / name
        assert sha256(path) == item["sha256"]
        print(adb("install", "-r", str(path)))
    installed = {}
    for app, name in [
        ("com.example.apphear", "app-debug-private-single-letter.apk"),
        ("com.example.apphear.test", "app-debug-androidTest.apk"),
    ]:
        location = adb("shell", "pm", "path", app).removeprefix("package:")
        installed[app] = adb("shell", "sha256sum", location).split()[0]
        assert installed[app] == identities["artifacts"][name]["sha256"]
    write_json(OUT / "installed_apk_integrity.json", installed)


def preservation() -> None:
    before = json.loads((OUT / "preservation_before.json").read_text())
    allowed = {
        str(MAIN / "FingerspellRuntime.kt"),
        str(MAIN / "FingerspellCore.kt"),
        str(DEVICE / "FingerspellOwnershipInstrumentedTest.kt"),
    }
    changed = [p for p, h in before.items() if not Path(p).is_file() or sha256(Path(p)) != h]
    unexpected = [p for p in changed if p not in allowed]
    report = {
        "checked": len(before),
        "changed": changed,
        "unexpected": unexpected,
        "word_unchanged": not unexpected,
        "test_accessed": False,
        "training": False,
    }
    write_json(OUT / "preservation.json", report)
    assert not unexpected, unexpected
    print(json.dumps(report, indent=2))


def pull() -> None:
    import numpy as np

    records = []
    for name in adb(
        "shell", "run-as", "com.example.apphear", "ls", "files/fingerspelling_sessions"
    ).splitlines():
        if not re.fullmatch(r"(?:failed_)?session_\d+\.json", name):
            continue
        data = adb(
            "exec-out",
            "run-as",
            "com.example.apphear",
            "cat",
            "files/fingerspelling_sessions/" + name,
        )
        report = json.loads(data)
        if not report.get("single_letter_mode"):
            continue
        (OUT / name).write_text(data, encoding="utf-8")
        if "logits_unadjusted" in report:
            logits = np.array(report["logits_unadjusted"], dtype=np.float32)
            result = decode_single_letter(logits)
            assert result.text == report["previewRaw"]
            assert len(logits) == len(report["usable_hand_evidence"]) == len(report["timestamp_ms"])
            assert np.all(np.diff(report["timestamp_ms"]) > 0)
            records.append(
                {
                    "file": name,
                    "preview": result.text,
                    "greedy": report["greedyRaw"],
                    "beam": report["beamRaw"],
                    "observations": report["observations"],
                    "usable": report["usable_hand_observations"],
                    "decoder_ms": report["single_letter_decode_ms"],
                    "finish_ms": report["finish_ms"],
                    "cadence": report["observations_per_second"],
                    "python_parity": True,
                }
            )
    for file in ["fingerspell_single_letter_parity.json", "fingerspell_sequence_v2_1_parity.json"]:
        data = adb("exec-out", "run-as", "com.example.apphear", "cat", "files/" + file)
        (OUT / ("xiaomi_" + file)).write_text(data, encoding="utf-8")
    write_json(OUT / "live_session_inventory.json", {"sessions": records, "accuracy_claim": False})
    print(json.dumps({"sessions": records, "accuracy_claim": False}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["stage", "preservation", "install", "pull"])
    args = parser.parse_args()
    {"stage": stage, "preservation": preservation, "install": install, "pull": pull}[args.action]()
