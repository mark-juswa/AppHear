"""Summarize camera-only integrity, tests and device metadata without accuracy claims."""

import json
import shutil
import xml.etree.ElementTree as ET
from collections import defaultdict

from tools.fingerspelling.camera_input_port import APP, OUT, sha


def main():
    before = json.loads((OUT / "before.json").read_text())
    allowed = {
        "android/app/build.gradle.kts",
        "android/app/src/main/java/com/example/apphear/RecognitionActivity.kt",
        "android/app/src/main/java/com/example/apphear/ui/OverlayView.kt",
        "android/app/src/main/java/com/example/apphear/perceptionvnext/PerceptionVNextOverlayView.kt",
        "android/app/src/androidTest/java/com/example/apphear/fingerspelling/ContinuousFingerspellInstrumentedTest.kt",
    }
    changed = [p for p, h in before.items() if sha(APP / p) != h]
    unexpected = sorted(set(changed) - allowed)
    tests = [
        ET.parse(p).getroot().attrib
        for p in (APP / "android/app/build/test-results/testDebugUnitTest").glob("TEST-*.xml")
    ]
    units = {k: sum(int(x[k]) for x in tests) for k in ("tests", "failures", "errors", "skipped")}
    frames = json.loads((OUT / "camera_input_01.json").read_text(encoding="utf-8-sig"))["frames"]
    grouped = defaultdict(list)
    for frame in frames:
        grouped[frame["generation"]].append(frame)
    views = []
    for generation, group in grouped.items():
        item = group[0]
        span = (group[-1]["timestamp_ns"] - item["timestamp_ns"]) / 1e9
        views.append(
            {
                "generation": generation,
                "front": item["front"],
                "mode": item["mode"],
                "rotation_degrees": item["rotation_degrees"],
                "raw_size": [item["raw_width"], item["raw_height"]],
                "upright_size": [item["upright_width"], item["upright_height"]],
                "frames": len(group),
                "startup_observations_per_second": (len(group) - 1) / span,
                "timestamp_chronology": all(
                    a["timestamp_ns"] < b["timestamp_ns"]
                    for a, b in zip(group, group[1:], strict=False)
                ),
            }
        )
    copies = {}
    for src, name in [
        (APP / "android/app/build/outputs/apk/debug/app-debug.apk", "app-debug-private-camera.apk"),
        (
            APP / "android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk",
            "app-debug-camera-test.apk",
        ),
    ]:
        dst = OUT / "private_apks" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copies[name] = sha(dst)
    rotation = json.loads((OUT / "rotation_parity.json").read_text(encoding="utf-8-sig"))
    switches = json.loads((OUT / "switch_result.json").read_text(encoding="utf-8-sig"))
    regression_log = (OUT / "device_smooth_tests.log").read_text(encoding="utf-8-sig")
    pass_tests = "OK (7 tests)" in regression_log
    timing_before = [
        json.loads(p.read_text(encoding="utf-8-sig"))
        for p in sorted((OUT / "device_timing").glob("*.json"))
    ]
    timing_after = [
        json.loads(p.read_text(encoding="utf-8-sig"))
        for p in sorted((OUT / "device_timing_smooth").glob("*.json"))
    ]
    result = {
        "schema_version": "apphear.camera_input_transfer.v1",
        "approved_baseline": "b48594c4942d9e9ac0d94ff96396e80b9f049c0a",
        "active_worktree": str(APP),
        "front_baseline_preprocessing_unchanged": True,
        "input_contract": "UPRIGHT_UNMIRRORED_SOURCE_RGB",
        "feature_flag": "recognitionRearCamera=true (debug opt-in; default/release false)",
        "modified_existing_app_files": changed,
        "new_tests": [
            "camera/CameraInputInstrumentedTest.kt",
            "camera/CameraSwitchInstrumentedTest.kt",
        ],
        "new_camera_diagnostic_utility": "camera/CameraTimingProbe.kt",
        "protected_files_checked": len(before) - len(allowed),
        "unexpected_changes": unexpected,
        "unit_tests": units,
        "rotation_parity": rotation,
        "camera_switch": switches,
        "device_ui_owner_context_regressions_pass": pass_tests,
        "device_views": views,
        "apk_sha256": copies,
        "cadence_limit": (
            "12 startup observations per binding; not a controlled throughput comparison"
        ),
        "human_visual_check": "Supervisor confirmed both lenses work; rear video choppy at 15 FPS",
        "rear_smoothing_human_feedback": "Supervisor: smoother, front unchanged",
        "rear_smoothing_policy": (
            "Rear 30 FPS only if exact range advertised; front reference 15 FPS unchanged"
        ),
        "capture_analysis_timing_before": timing_before,
        "capture_analysis_timing_after": timing_after,
        "accuracy_claim": "NONE",
        "training": False,
        "test_payload_accessed": False,
    }
    result["engineering_pass"] = (
        not unexpected
        and not units["failures"]
        and not units["errors"]
        and rotation["status"] == "PASS"
        and switches["status"] == "PASS"
        and pass_tests
    )
    (OUT / "summary.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
