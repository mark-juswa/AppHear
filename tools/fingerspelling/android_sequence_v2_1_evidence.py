"""Pinned private APK inventory and read-only V2.1 transfer evidence collection."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.sequence_manifest import REPO
from tools.fingerspelling.android_export import write_json
from tools.fingerspelling.android_sequence_v2_1_port import APP, OUT

ADB = r"D:\AndroidStudio\Android\Sdk\platform-tools\adb.exe"
SERIAL = "3ab64582"


def stage() -> None:
    package = json.loads((OUT / "export_parity.json").read_text())
    dest = OUT / "private_apks"
    dest.mkdir(exist_ok=True)
    apks = {
        "app-debug-private-v2-1.apk": APP / "android/app/build/outputs/apk/debug/app-debug.apk",
        "app-debug-androidTest.apk": APP
        / "android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk",
    }
    for name, path in apks.items():
        shutil.copyfile(path, dest / name)
    with zipfile.ZipFile(dest / "app-debug-private-v2-1.apk") as z:
        import hashlib

        assert (
            hashlib.sha256(z.read("assets/fingerspelling/model_manifest.json")).hexdigest()
            == package["manifest_sha256"]
        )
        assert (
            hashlib.sha256(z.read("assets/fingerspelling/geometry_sequence.tflite")).hexdigest()
            == package["models"]["geometry_sequence.tflite"]["sha256"]
        )
        assert not any(
            p.startswith("assets/fingerspelling/") and "appearance" in p for p in z.namelist()
        )
        current = {
            p: hashlib.sha256(z.read(p)).hexdigest()
            for p in z.namelist()
            if p.startswith("assets/") and not p.startswith("assets/fingerspelling/")
        }
    old_root = REPO / "artifacts/fingerspelling_train4096_android_01/private_apks"
    old_apks = sorted(old_root.glob("*.apk"))
    baseline = next(p for p in old_apks if "androidTest" not in p.name)
    with zipfile.ZipFile(baseline) as z:
        previous = {
            p: hashlib.sha256(z.read(p)).hexdigest()
            for p in z.namelist()
            if p.startswith("assets/") and not p.startswith("assets/fingerspelling/")
        }
    assert current == previous, "Non-fingerspelling packaged assets changed"
    write_json(
        OUT / "apk_identities.json",
        {
            "private_phone_only": True,
            "artifacts": {
                n: {"sha256": sha256(dest / n), "bytes": (dest / n).stat().st_size} for n in apks
            },
            "rollback_apk": str(baseline),
            "rollback_apk_sha256": sha256(baseline),
            "non_fingerspelling_assets_unchanged": len(current),
            "package_verified": True,
        },
    )
    suites = [
        ET.parse(p).getroot()
        for p in (APP / "android/app/build/test-results/testDebugUnitTest").glob("TEST-*.xml")
    ]
    totals = {
        key: sum(int(r.get(key, "0")) for r in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    write_json(
        OUT / "unit_validation.json",
        {
            "totals": totals,
            "suites": [
                {"name": r.get("name"), "tests": r.get("tests"), "timestamp": r.get("timestamp")}
                for r in suites
            ],
        },
    )
    assert totals["tests"] > 0 and totals["failures"] == totals["errors"] == 0
    print(
        json.dumps(
            {"apk_package": "VERIFIED", "unchanged_assets": len(current), "unit_tests": totals}
        )
    )


def adb(*args: str) -> str:
    return subprocess.check_output([ADB, "-s", SERIAL, *args], text=True).strip()


def install() -> None:
    assert adb("get-state") == "device"
    identities = json.loads((OUT / "apk_identities.json").read_text())["artifacts"]
    for name, item in identities.items():
        path = OUT / "private_apks" / name
        assert sha256(path) == item["sha256"]
        print(adb("install", "-r", str(path)))
    installed = {}
    for app_id, name in [
        ("com.example.apphear", "app-debug-private-v2-1.apk"),
        ("com.example.apphear.test", "app-debug-androidTest.apk"),
    ]:
        location = adb("shell", "pm", "path", app_id).removeprefix("package:")
        value = adb("shell", "sha256sum", location).split()[0]
        assert value == identities[name]["sha256"]
        installed[app_id] = value
    write_json(OUT / "installed_apk_integrity.json", installed)


def preservation() -> None:
    before = json.loads((OUT / "preservation_before.json").read_text())
    loader = str(
        APP / "android/app/src/main/java/com/example/apphear/fingerspelling/FingerspellModels.kt"
    )
    old_test = str(
        APP
        / "android/app/src/androidTest/java/com/example/apphear/fingerspelling"
        / "Train4096ParityInstrumentedTest.kt"
    )
    allowed = {loader, old_test}
    # Inherited governance inventory has {sha256, bytes}; new snapshot entries are hashes.
    expected = {p: h["sha256"] if isinstance(h, dict) else h for p, h in before.items()}
    changed = [p for p, h in expected.items() if not Path(p).is_file() or sha256(Path(p)) != h]
    unexpected = [p for p in changed if p not in allowed]
    report = {
        "files_checked": len(before),
        "changed": changed,
        "unexpected": unexpected,
        "allowed": sorted(allowed),
        "test_accessed": False,
    }
    write_json(OUT / "preservation.json", report)
    assert not unexpected, f"Unexpected protected changes: {len(unexpected)}; see preservation.json"
    print(json.dumps(report, indent=2))


def pull() -> None:
    for filename in (
        "fingerspell_sequence_v2_1_parity.json",
        "fingerspell_beam_parity.json",
        "fingerspell_word_cadence.json",
    ):
        result = subprocess.run(
            [
                ADB,
                "-s",
                SERIAL,
                "shell",
                "run-as",
                "com.example.apphear",
                "cat",
                f"files/{filename}",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            write_json(OUT / ("xiaomi_" + filename), json.loads(result.stdout))
    # Read JSON diagnostics only; no pixels, landmarks, logits or training recordings.
    sessions = []
    for name in adb(
        "shell", "run-as", "com.example.apphear", "ls", "files/fingerspelling_sessions"
    ).splitlines():
        if not re.fullmatch(r"session_\d+\.json", name):
            continue
        record = json.loads(
            adb(
                "shell",
                "run-as",
                "com.example.apphear",
                "cat",
                f"files/fingerspelling_sessions/{name}",
            )
        )
        if (
            record.get("model_manifest", {}).get("candidate_id")
            != "SEQUENCE_V2_1_EPOCH034_GEOMETRY_ONLY"
        ):
            continue
        write_json(OUT / name, record)
        sessions.append(
            {
                "file": name,
                "observations": record["observations"],
                "greedyRaw": record["greedyRaw"],
                "beamRaw": record["beamRaw"],
                "previewRaw": record["previewRaw"],
                "cadence": record["observations_per_second"],
                "model_ms": record["model_ms"],
                "beam_ms": record["beam_decode_ms"],
                "finish_ms": record["finish_ms"],
                "observed_hand_frames": record["any_hand_observed_frames"],
            }
        )
    write_json(
        OUT / "live_session_inventory.json",
        {
            "sessions": sessions,
            "accuracy_claim": "NONE_NONEXPERT_ENGINEERING_ONLY",
            "test_accessed": False,
        },
    )
    print("Available private engineering reports collected; no RGB/raw payload copied.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["stage", "install", "preservation", "pull"])
    action = parser.parse_args().action
    {"stage": stage, "install": install, "preservation": preservation, "pull": pull}[action]()
