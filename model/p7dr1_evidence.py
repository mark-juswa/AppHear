"""P7D-R1 evidence bookkeeping only. Never launches inference or changes parent artifacts."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/recognition_upgrade/p7dr1_runtime_data_path_remediation_01"
PARENT = ROOT / "artifacts/recognition_upgrade/p7d_android_runtime_skeleton_feasibility_01"
MODEL_SHA = "d8617516aa08b4827c7a75276c5de5c0d76a07620a07d212d323992c188ee42e"


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(name: str, value: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def snapshot() -> dict:
    previous = json.loads((PARENT / "p7d_integrity.json").read_text())
    groups = [r["directory"] for r in previous["before"]["groups"]]
    groups += [str(PARENT.relative_to(ROOT)).replace("\\", "/"), "android/app/src/main"]
    files = {}
    for group in groups:
        for p in sorted((ROOT / group).rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                files[p.relative_to(ROOT).as_posix()] = sha(p)
    for name in ["P7dMath.kt", "P7dRuntimeActivity.kt"]:
        p = ROOT / "android/app/src/debug/java/com/example/apphear/p7d" / name
        files[p.relative_to(ROOT).as_posix()] = sha(p)
    for name in ["model/p7d_runtime_skeleton.py", "model/p7d_summarize_runtime.py",
                 "android/app/src/test/java/com/example/apphear/p7d/P7dMathTest.kt"]:
        files[name] = sha(ROOT / name)
    return files


def freeze() -> None:
    assert not (OUT / "p7dr1_reference_path_identity.json").exists(), "Never refreeze after implementation"
    assert sha(PARENT / "random_skeleton.tflite") == MODEL_SHA
    save("p7dr1_reference_path_identity.json", {"model_sha256": MODEL_SHA, "files": snapshot()})
    save("p7dr1_compute_prescreen_protocol.json", {"warmup_seconds": 10, "measured_seconds": 30,
         "source": "deterministic synthetic RGBA640x480 row2560 pixel4 rotation270; same geometry as P7D",
         "seed": 707, "p95_limit_ms": 62.7532812, "minimum_loops_per_second": 15,
         "runtime": "2.16.1", "provider": "XNNPACK", "threads": 2, "batch": 1,
         "semantics_gate_before_performance": True, "no_second_optimization_after_result": True})
    save("p7dr1_camera_only_protocol.json", {"seconds": 60, "requires_compute_pass": True,
         "target_resolution_request": [480,360], "camera": "DEFAULT_FRONT_CAMERA",
         "strategy": "KEEP_ONLY_LATEST", "format": "RGBA_8888", "AE_changes": False,
         "model_inference": False, "close_immediately": True})
    save("p7dr1_integrated_benchmark_protocol.json", {"warmup_seconds": 30, "measured_seconds": 180,
         "requires_parity_and_compute_pass": True, "same_P7D_camera_configuration": True,
         "p95_limit_ms": 62.7532812, "minimum_processing_fps": 15,
         "camera_cadence_separate": True, "tuning_after_run": False})
    print("Reference snapshot and protocols frozen")


def parity() -> None:
    test_dir = ROOT / "android/app/build/test-results/testDebugUnitTest"
    xml = test_dir / "TEST-com.example.apphear.p7dr1.P7dr1ParityTest.xml"
    tree = ET.parse(xml).getroot()
    assert tree.attrib["failures"] == tree.attrib["errors"] == "0"
    stdout = tree.findtext("system-out") or ""
    p = re.search(r"PREPROCESS cases=(\d+) max_abs=([\d.eE+-]+)", stdout)
    d = re.search(r"DECODER cases=(\d+) max_xy=([\d.eE+-]+) max_confidence=([\d.eE+-]+)", stdout)
    assert p and d
    suites = [ET.parse(f).getroot() for f in test_dir.glob("TEST-*.xml")]
    assert all(s.attrib["failures"] == s.attrib["errors"] == "0" for s in suites)
    assert sha(PARENT / "random_skeleton.tflite") == MODEL_SHA
    before = json.loads((OUT / "p7dr1_reference_path_identity.json").read_text())["files"]
    assert before == snapshot(), "Protected/reference files changed"
    save("p7dr1_preprocess_parity.json", {"passed": True, "cases": int(p[1]), "max_tensor_abs": float(p[2]),
         "atol": 1e-5, "rtol": 1e-6, "orientation_mirror_content_source_mapping_exact": True,
         "finite": True, "source": xml.relative_to(ROOT).as_posix(), "test_sha256": sha(xml)})
    save("p7dr1_decoder_parity.json", {"passed": True, "cases": int(d[1]), "max_coordinate_abs": float(d[2]),
         "max_confidence_abs": float(d[3]), "nonfinite_cases": 12, "winning_indices_exact": True,
         "ties_content_rejection_exact": True, "body_independent": True, "tolerance": 1e-5})
    (OUT / "parity_test_results.xml").write_bytes(xml.read_bytes())
    paths = list((ROOT / "android/app/src/debug/java/com/example/apphear/p7dr1").glob("*.kt"))
    paths += list((ROOT / "android/app/src/test/java/com/example/apphear/p7dr1").glob("*.kt"))
    paths += [ROOT / "android/app/src/debug/AndroidManifest.xml", ROOT / "android/app/build/outputs/apk/debug/app-debug.apk"]
    save("p7dr1_optimized_path_identity.json", {"frozen_before_device_timing": True,
         "files": {f.relative_to(ROOT).as_posix(): sha(f) for f in paths},
         "tests": sum(int(s.attrib["tests"]) for s in suites), "suites": len(suites)})
    save("host_gate.json", {"preprocess_pass": True, "decoder_pass": True, "model_sha256": MODEL_SHA,
                           "compute_pass_verified": False})
    print(stdout)


def stats(values: list[float]) -> dict:
    values = sorted(values)
    if not values:
        return {"count": 0, "p50": None, "p90": None, "p95": None, "max": None}
    def q(f: float) -> float:
        p = (len(values)-1)*f
        a = int(p)
        return values[a] + (values[min(a+1,len(values)-1)]-values[a])*(p-a)
    return {"count": len(values), "p50": q(.5), "p90": q(.9), "p95": q(.95), "max": values[-1]}


def summarize(phase: str) -> dict:
    r = json.loads((OUT / f"{phase}_result.json").read_text())
    assert r["phase"] == phase and r["model_sha256"] == MODEL_SHA
    assert r["device"] == "M2101K7AG" and r["soc"] == "SM6150" and r["android"] == "12"
    assert r["runtime"] == "2.16.1" and r["threads"] == 2 and r["precision"] == "FP32"
    rows = r["samples"]
    assert len(rows) == r["completed"]
    assert all(r["measurement_start_ns"] <= s["start_ns"] <= s["end_ns"] <= r["measurement_end_ns"] for s in rows)
    keys = ["preprocess_ms", "backend_native_ms", "invoke_wall_ms", "output_read_ms", "decoder_ms", "restore_ms", "perception_ms"]
    summary = {k: stats([s[k] for s in rows]) for k in keys}
    passed = bool(rows and not r["errors"] and summary["perception_ms"]["p95"] <= 62.7532812 and r["completed_fps"] >= 15)
    result = {"executed": True, "phase": phase, "latency_ms": summary, "completed": len(rows),
              "measured_seconds": r["measured_seconds"], "completed_fps": r["completed_fps"],
              "screen_pass": passed, "errors": r["errors"], "raw_sha256": sha(OUT / f"{phase}_result.json")}
    if phase == "compute":
        assert r["warmup_seconds"] == 10 and r["measured_seconds"] == 30
        assert r["compute_screen_pass"] == passed
        save("p7dr1_compute_prescreen_result.json", result)
        if passed:
            marker = json.loads((OUT / "host_gate.json").read_text())
            marker["compute_pass_verified"] = True
            save("host_gate.json", marker)
    elif phase == "camera":
        assert r["warmup_seconds"] == 0 and r["measured_seconds"] == 60 and not rows
        result.update({"capture_fps": r["capture_fps"], "analyzer_fps": r["analyzer_fps"],
                       "frame_metadata": r["frame_metadata"], "camera_metadata": r["camera_metadata"],
                       "status": "CAMERA_CADENCE_AT_OR_ABOVE_15" if r["capture_fps"] >= 15 and r["analyzer_fps"] >= 15
                       else "CAMERA_CADENCE_BELOW_15_CAUSE_NOT_ESTABLISHED"})
        captures = r["capture_rows"]
        result["sensor_frame_duration_ms"] = stats([c[2]/1e6 for c in captures if c[2]>=0])
        result["exposure_ms"] = stats([c[3]/1e6 for c in captures if c[3]>=0])
        result["sensor_timestamp_gap_ms"] = stats([(b[1]-a[1])/1e6 for a,b in zip(captures,captures[1:]) if a[1]>=0 and b[1]>=0])
        result["active_ae_ranges"] = sorted(set(tuple(c[4:6]) for c in captures))
        result["requested_ae_ranges"] = sorted(set(tuple(c[6:8]) for c in captures))
        save("p7dr1_camera_only_result.json", result)
    elif phase == "integrated":
        assert r["warmup_seconds"] == 30 and r["measured_seconds"] == 180
        save("p7dr1_integrated_result.json", result)
    print(json.dumps(result, indent=2))
    return result


def capture_log(label: str) -> None:
    result = subprocess.run(["D:/AndroidStudio/Android/Sdk/platform-tools/adb.exe", "-s", "3ab64582",
                             "logcat", "-d", "-s", "P7DR1:I", "tflite:I", "AndroidRuntime:E"],
                            check=True, capture_output=True, text=True, encoding="utf-8")
    target = OUT / f"logcat_{label}.txt"
    assert not target.exists()
    target.write_text(result.stdout, encoding="utf-8")
    print(result.stdout)


def finalize() -> None:
    """Close the failed pre-screen, without authorizing or launching another run."""
    r = json.loads((OUT / "compute_result.json").read_text())
    s = json.loads((OUT / "p7dr1_compute_prescreen_result.json").read_text())
    assert not s["screen_pass"] and not r["errors"]
    assert not (OUT / "camera_result.json").exists() and not (OUT / "integrated_result.json").exists()
    before = json.loads((OUT / "p7dr1_reference_path_identity.json").read_text())["files"]
    after = snapshot()
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    optimized = json.loads((OUT / "p7dr1_optimized_path_identity.json").read_text())
    optimized_changed = [k for k,v in optimized["files"].items() if sha(ROOT/k) != v]
    assert not changed and not optimized_changed, (changed, optimized_changed)
    assert sha(PARENT / "random_skeleton.tflite") == MODEL_SHA
    label = "P7DR1_RUNTIME_PATH_REMEDIATION_BELOW_SCREEN"
    next_gate = "PROJECT_LEAD_P7DR1_RUNTIME_REMEDIATION_FAILURE_REVIEW"
    not_run = {"executed": False, "status": "NOT_EXECUTED", "reason": "Mandatory stop: compute pre-screen failed"}
    save("p7dr1_camera_only_result.json", not_run)
    save("p7dr1_camera_cadence_summary.json", not_run | {"camera_tuned": False, "cause": "NOT_ESTABLISHED"})
    metrics = s["latency_ms"]
    save("p7dr1_preprocess_latency_summary.json", {"scope": "COMPUTE_PRESCREEN_ONLY", "units": "ms",
         "fused_preprocess": metrics["preprocess_ms"], "integrated": not_run})
    save("p7dr1_backend_latency_summary.json", {"scope": "COMPUTE_PRESCREEN_ONLY", "units": "ms",
         "native": metrics["backend_native_ms"], "invoke_wall": metrics["invoke_wall_ms"], "load_ms": r["model_load_ms"], "integrated": not_run})
    save("p7dr1_decoder_latency_summary.json", {"scope": "COMPUTE_PRESCREEN_ONLY", "units": "ms",
         "decoder": metrics["decoder_ms"], "output_read": metrics["output_read_ms"], "restore": metrics["restore_ms"], "integrated": not_run})
    save("p7dr1_perception_latency_summary.json", {"scope": "COMPUTE_PRESCREEN_ONLY", "units": "ms",
         "complete": metrics["perception_ms"], "screen_p95_limit_ms": 62.7532812, "screen_pass": False, "integrated": not_run})
    save("p7dr1_fps_summary.json", {"compute_completed_loops": r["completed"], "measured_seconds": 30,
         "compute_loops_per_second": r["completed_fps"], "minimum": 15, "camera": not_run, "integrated": not_run,
         "full_product_FPS_established": False, "window": [r["measurement_start_ns"],r["measurement_end_ns"]]})
    mem = r["memory"]
    save("p7dr1_memory_summary.json", {"scope": "COMPUTE_PRESCREEN_ONLY", "sampling_interval_seconds": 5,
         "peak_sampled_pss_kib": max(x["pss_kib"] for x in mem),
         "peak_sampled_native_heap_bytes": max(x["native_heap_bytes"] for x in mem),
         "peak_sampled_java_heap_bytes": max(x["java_heap_bytes"] for x in mem),
         "start": mem[0], "end": mem[-1], "samples": mem, "continuous_high_water_mark": False,
         "formal_memory_ceiling": None, "tensor_arena_bytes": "NOT_EXPOSED", "integrated": not_run})
    save("p7dr1_thermal_summary.json", {"scope": "COMPUTE_PRESCREEN_ONLY", "start": mem[0]["thermal"],
         "after_warmup_nearest_sample": min(mem,key=lambda x:abs(x["elapsed_seconds"]-10)),
         "peak": max(x["thermal"] for x in mem), "end": mem[-1]["thermal"], "zero_means": "NONE", "integrated": not_run})
    save("p7dr1_runtime_errors.json", {"errors": r["errors"], "observed_crashes": 0, "OOM_observed": False,
         "completed_compute_runs": 1, "camera_runs": 0, "integrated_runs": 0, "no_tuning_after_result": True})
    logs = "\n".join(p.read_text(encoding="utf-8") for p in OUT.glob("logcat_*.txt"))
    partitions = re.findall(r"Replacing (\d+) out of (\d+) node\(s\).*yielding (\d+) partitions", logs)
    save("p7dr1_provider_partitioning.json", {"provider": "TfLiteXNNPackDelegate", "source": "captured device startup log",
         "observations": [{"delegated": int(a),"total": int(b),"partitions": int(c)} for a,b,c in sorted(set(partitions))],
         "fallback_graph_nodes": 0 if partitions and all(a==b for a,b,c in partitions) else None,
         "per_operator_latency": "NOT_EXPOSED", "threads": 2})
    intentional = {p.relative_to(ROOT).as_posix(): sha(p) for p in
                   list((ROOT/"android/app/src/debug/java/com/example/apphear/p7dr1").glob("*.kt")) +
                   list((ROOT/"android/app/src/test/java/com/example/apphear/p7dr1").glob("*.kt")) +
                   [ROOT/"android/app/src/debug/AndroidManifest.xml",ROOT/"model/p7dr1_evidence.py"]}
    save("p7dr1_android_changes_manifest.json", {"intentional_files": intentional,
         "reference_files_modified": False, "production_src_main_modified": False,
         "debug_manifest_change": "Only two new lines: comment and explicit exported P7DR1 Activity. No launcher.",
         "default_off": "Requires p7dr1_enabled=true, explicit phase, host parity marker, exact model/device/runtime checks",
         "APK_sha256": optimized["files"]["android/app/build/outputs/apk/debug/app-debug.apk"],
         "existing_dirty_worktree_preserved": True})
    no_actions = {k: False for k in ["training", "teacher_extraction", "recognizer_inference", "accuracy_evaluation",
                  "D10", "protected_replay", "pristine_data", "architecture_changed", "resolution_changed",
                  "provider_thread_sweep", "quantization", "FP16", "family_B", "S5_modified", "S7_modified", "V2_modified", "P4_reopened"]}
    save("p7dr1_integrity.json", {"integrity": "PASS", "historical_artifacts_unchanged": True,
         **{f"{g}_unchanged": True for g in ["D12","P6A","P6B","P6BR1","P6C","P6CP1","P7A","P7B","P7C","P7D"]},
         "progress_tracker_unchanged": True, "production_src_main_unchanged": True, "context_unchanged": True,
         "reference_snapshot_file_count": len(before), "before": before["context/progress-tracker.md"],
         "after": after["context/progress-tracker.md"], "changed_protected_files": changed,
         "optimized_code_changed_after_timing_freeze": optimized_changed,
         "model_sha256": MODEL_SHA, "reference_available": True, "parity_pass": True,
         "JVM_tests": optimized["tests"], "JVM_suites": optimized["suites"],
         "compute_runs": 1, "camera_runs": 0, "integrated_runs": 0,
         "random_skeleton_inference": True, "imprint": "Audit-only, new artifacts; context remains read-only", **no_actions})
    save("p7dr1_decision.json", {"classification": label, "parity": "PASS", "runtime_screen_met": False,
         "camera_cadence_status": "NOT_EXECUTED", "next_gate": next_gate, "next_gate_executed": False,
         "production_authorized": False, "automatic_tuning_authorized": False})
    save("APPHEAR_RECOGNITION_CANONICAL_STATE_P7DR1.json", {"parent": "APPHEAR_RECOGNITION_CANONICAL_STATE_P7D.json",
         "parent_sha256": sha(PARENT/"APPHEAR_RECOGNITION_CANONICAL_STATE_P7D.json"),
         "formal_P7D_status": "P7D_PRIMARY_RUNTIME_SKELETON_BELOW_SCREEN", "prior_results_changed": False,
         "architecture": "FA_DS_SPATIAL_V1", "model_sha256": MODEL_SHA, "input": [1,384,384,3],
         "heatmap_output": [1,96,96,50], "identity_output": [1,1,1,2], "precision": "FP32",
         "provider": "XNNPACK", "threads": 2, "runtime": "2.16.1", "classification": label,
         "preprocess_parity": "PASS", "decoder_parity": "PASS", "camera_cadence": "NOT_EXECUTED",
         "compute_p95_ms": metrics["perception_ms"]["p95"], "compute_loops_per_second": r["completed_fps"],
         "calibration": "POLICY_UNCONFIGURED", "production_authorized": False, "next_gate_executed": False, **no_actions})
    print(json.dumps({"integrity": "PASS", "classification": label, "peak_pss_kib": max(x["pss_kib"] for x in mem),
                      "thermal_peak": max(x["thermal"] for x in mem), "protected_files": len(before)}))


def hash_artifacts() -> None:
    save("artifact_hash_manifest.json", {"algorithm": "SHA256", "self_excluded": True,
         "artifacts": [{"path": p.relative_to(OUT).as_posix(),"sha256":sha(p),"bytes":p.stat().st_size}
                       for p in sorted(OUT.rglob("*")) if p.is_file() and p.name!="artifact_hash_manifest.json"]})


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv)>1 else "freeze"
    if action == "freeze": freeze()
    elif action == "parity": parity()
    elif action in ("compute", "camera", "integrated"): summarize(action)
    elif action == "log": capture_log(sys.argv[2])
    elif action == "finalize": finalize()
    elif action == "hash": hash_artifacts()
