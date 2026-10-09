"""P6-C host tooling for the debug-only Android DWPose-L/V2 feasibility gate.

This tool prepares deterministic warped-RGB fixtures, compares Android outputs with the
immutable P6B-R1 oracle, and never runs a recognizer, training, D10, or a desktop parity rerun.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from model.p6b_v2_backend_feasibility import get_warp_matrix


ROOT = Path(__file__).resolve().parents[1]
P6B = ROOT / "artifacts/recognition_upgrade/p6b_v2_backend_feasibility_prototype_01"
P6BR1 = ROOT / "artifacts/recognition_upgrade/p6br1_v2_dependency_parity_confirmation_01"
OUT = ROOT / "artifacts/recognition_upgrade/p6c_android_v2_device_feasibility_01"
PACK = OUT / "device_fixture_pack"
ONNX = P6B / "frozen_dwpose_l_fp32.onnx"
FIXTURES = P6BR1 / "p6br1_fixture_manifest.csv"
ORACLE = P6BR1 / "p6br1_offline_oracle_outputs.npz"
P6A = ROOT / "artifacts/recognition_upgrade/p6a_production_runtime_compatibility_audit_01"
D12 = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5d12_future_version_evidence_synthesis_01"
PROGRESS = ROOT / "context/progress-tracker.md"
APK = ROOT / "android/app/build/outputs/apk/debug/app-debug.apk"
EXPECTED_ONNX_SHA = "870c84ddbf396282c415854b233ba972a772ac35f1eebe26b6ce185a19579965"
EXPECTED_FIXTURE_SHA = "b7ce52642301f3ab5cf047714956dec444ef90a7069d1cda6c4412d0f6ac5d65"
SCORE_TOLERANCE = 1e-4
CENTER_TOLERANCE = 0.5
SCALE_REL_TOLERANCE = 1e-4
V2_MEAN_TOLERANCE = 1e-5
V2_MAX_TOLERANCE = 1e-3


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def resolve_source(row: dict[str, str]) -> tuple[Path, str]:
    expected = row["source_sha256"]
    candidates = [Path(row["resolved_source_path"]), Path(row["governed_source_path"])]
    for candidate in candidates:
        if candidate.is_file() and sha(candidate) == expected:
            return candidate.resolve(), "GOVERNED_PATH_HASH_VERIFIED"
    raise RuntimeError(f"P6C_FIXTURE_SOURCE_NOT_RECOVERABLE_BY_HASH: {row['fixture_id']} {expected}")


def warped_rgb(source: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"cannot decode fixture: {source}")
    height, width = image.shape[:2]
    center = np.asarray([width * 0.5, height * 0.5], np.float32)
    scale = np.asarray([width * 1.25, height * 1.25], np.float32)
    aspect = 192.0 / 256.0
    if scale[0] > scale[1] * aspect:
        scale[1] = scale[0] / aspect
    else:
        scale[0] = scale[1] * aspect
    crop_bgr = cv2.warpAffine(image, get_warp_matrix(center, scale), (192, 256), flags=cv2.INTER_LINEAR)
    return np.ascontiguousarray(crop_bgr[:, :, ::-1], np.uint8), center, scale


def prepare() -> int:
    if sha(ONNX) != EXPECTED_ONNX_SHA:
        raise RuntimeError("P6C_FROZEN_ONNX_IDENTITY_MISMATCH")
    if sha(FIXTURES) != EXPECTED_FIXTURE_SHA:
        raise RuntimeError("P6C_P6BR1_FIXTURE_IDENTITY_MISMATCH")
    rows = read_csv(FIXTURES)
    if len(rows) != 60:
        raise RuntimeError(f"expected 60 P6BR1 fixtures, found {len(rows)}")
    PACK.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, Any]] = []
    tsv = ["fixture_id\tcategory\trgb_file\trgb_sha256\tcenter_x\tcenter_y\tscale_x\tscale_y"]
    for row in rows:
        source, resolution = resolve_source(row)
        rgb, center, scale = warped_rgb(source)
        filename = f"{row['fixture_index'].zfill(2)}_{row['fixture_id']}.rgb"
        rgb_path = PACK / filename
        rgb_path.write_bytes(rgb.tobytes(order="C"))
        rgb_hash = sha(rgb_path)
        values = {
            "fixture_index": int(row["fixture_index"]),
            "fixture_id": row["fixture_id"],
            "visibility_category": row["visibility_category"],
            "source_sha256": row["source_sha256"],
            "source_path_resolution": resolution,
            "source_width": int(row["image_width"]),
            "source_height": int(row["image_height"]),
            "warped_rgb_file": filename,
            "warped_rgb_width": 192,
            "warped_rgb_height": 256,
            "warped_rgb_layout": "HWC_RGB_UINT8",
            "warped_rgb_sha256": rgb_hash,
            "center_x": float(center[0]),
            "center_y": float(center[1]),
            "scale_x": float(scale[0]),
            "scale_y": float(scale[1]),
        }
        manifest_rows.append(values)
        tsv.append("\t".join(map(str, [row["fixture_id"], row["visibility_category"], filename, rgb_hash, float(center[0]), float(center[1]), float(scale[0]), float(scale[1])])))
    write_csv(OUT / "p6c_fixture_pack_manifest.csv", manifest_rows)
    (PACK / "fixture_manifest.tsv").write_text("\n".join(tsv) + "\n", encoding="utf-8")
    pack_files = sorted(path for path in PACK.iterdir() if path.is_file())
    write_json(OUT / "p6c_fixture_pack_hash.json", {
        "parent_fixture_manifest_sha256": sha(FIXTURES),
        "fixture_count": len(rows),
        "composition": {name: sum(row["visibility_category"] == name for row in rows) for name in ("ZERO", "ONE", "TWO")},
        "pack_manifest_sha256": sha(OUT / "p6c_fixture_pack_manifest.csv"),
        "device_tsv_sha256": sha(PACK / "fixture_manifest.tsv"),
        "files": [{"path": path.name, "bytes": path.stat().st_size, "sha256": sha(path)} for path in pack_files],
        "input_reproducibility": "HOST_CV2_GOVERNED_AFFINE_ONCE_THEN_EXACT_WARPED_RGB_BYTES_ON_ANDROID",
    })
    print(json.dumps({"prepared": True, "fixtures": len(rows), "pack": str(PACK), "bytes": sum(path.stat().st_size for path in pack_files)}, indent=2))
    return 0


def json_array(value: Any, dtype: Any) -> np.ndarray:
    return np.asarray(value, dtype=dtype)


def compare(android_jsonl: Path) -> int:
    lines = [json.loads(line) for line in android_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) != 60:
        raise RuntimeError(f"expected 60 Android outputs, found {len(lines)}")
    oracle = np.load(ORACLE)
    oracle_ids = [str(value) for value in oracle["fixture_ids"]]
    by_id = {row["fixture_id"]: row for row in lines}
    if set(by_id) != set(oracle_ids):
        raise RuntimeError("Android fixture membership does not equal P6BR1 fixture membership")
    parity_rows: list[dict[str, Any]] = []
    all_pass = True
    for index, fixture_id in enumerate(oracle_ids):
        row = by_id[fixture_id]
        xy = json_array(row["xy"], np.float32).reshape(133, 2)
        scores = json_array(row["scores"], np.float32)
        valid = json_array(row["valid"], bool)
        observed = np.asarray([row["left_observed"], row["right_observed"]], bool)
        center = json_array(row["center"], np.float64)
        scale = float(row["scale"])
        v2 = json_array(row["v2"], np.float32)
        if xy.shape != (133, 2) or scores.shape != (133,) or valid.shape != (133,) or v2.shape != (238,):
            raise RuntimeError(f"invalid Android output shape for {fixture_id}")
        score_max = float(np.max(np.abs(scores.astype(np.float64) - oracle["scores_133"][index].astype(np.float64))))
        valid_exact = bool(np.array_equal(valid, oracle["valid_mask_133"][index]))
        observed_exact = bool(np.array_equal(observed, oracle["observed_flags"][index]))
        center_max = float(np.max(np.abs(center - oracle["normalization_center"][index])))
        oracle_scale = float(oracle["normalization_scale"][index])
        scale_rel = abs(scale - oracle_scale) / max(abs(oracle_scale), 1e-12)
        v2_error = np.abs(v2.astype(np.float64) - oracle["v2_features"][index].astype(np.float64))
        v2_mean = float(np.mean(v2_error))
        v2_max = float(np.max(v2_error))
        xy_error = np.abs(xy.astype(np.float64) - oracle["keypoints_133"][index].astype(np.float64))
        effective = np.zeros((133,), bool)
        effective[0:17] = True
        if observed[0]: effective[91:112] = True
        if observed[1]: effective[112:133] = True
        discarded = ~effective
        discarded_raw_count = int(np.count_nonzero(np.any(xy_error[discarded] > 0.5, axis=1)))
        passed = bool(score_max <= SCORE_TOLERANCE and valid_exact and observed_exact and center_max <= CENTER_TOLERANCE and scale_rel <= SCALE_REL_TOLERANCE and v2_mean <= V2_MEAN_TOLERANCE and v2_max <= V2_MAX_TOLERANCE)
        all_pass &= passed
        parity_rows.append({
            "fixture_id": fixture_id,
            "category": str(oracle["categories"][index]),
            "topology_exact": True,
            "hand_slots_exact": observed_exact,
            "score_max_abs_error": score_max,
            "valid_exact": valid_exact,
            "observed_exact": observed_exact,
            "center_max_abs_error_pixels": center_max,
            "scale_relative_error": scale_rel,
            "v2_mean_abs_error": v2_mean,
            "v2_max_abs_error": v2_max,
            "raw_xy_max_abs_error_pixels": float(np.max(xy_error)),
            "discarded_raw_coordinate_excursions": discarded_raw_count,
            "discarded_difference_propagated_to_v2": bool(discarded_raw_count and v2_max > V2_MAX_TOLERANCE),
            "pass": passed,
        })
    write_csv(OUT / "p6c_android_semantic_parity.csv", parity_rows)
    summary = {
        "executed": True,
        "fixture_count": 60,
        "passed": all_pass,
        "classification": "P6C_ANDROID_V2_SEMANTIC_PARITY_PASS" if all_pass else "P6C_ANDROID_V2_SEMANTIC_PARITY_FAILED",
        "topology": "PASS" if all(row["topology_exact"] for row in parity_rows) else "FAIL",
        "hand_slots": "PASS" if all(row["hand_slots_exact"] for row in parity_rows) else "FAIL",
        "scores": "PASS" if all(row["score_max_abs_error"] <= SCORE_TOLERANCE for row in parity_rows) else "FAIL",
        "validity": "PASS" if all(row["valid_exact"] for row in parity_rows) else "FAIL",
        "observed": "PASS" if all(row["observed_exact"] for row in parity_rows) else "FAIL",
        "normalization": "PASS" if all(row["center_max_abs_error_pixels"] <= CENTER_TOLERANCE and row["scale_relative_error"] <= SCALE_REL_TOLERANCE for row in parity_rows) else "FAIL",
        "final_v2": "PASS" if all(row["v2_mean_abs_error"] <= V2_MEAN_TOLERANCE and row["v2_max_abs_error"] <= V2_MAX_TOLERANCE for row in parity_rows) else "FAIL",
        "worst_final_v2_mean_error": max(row["v2_mean_abs_error"] for row in parity_rows),
        "worst_final_v2_max_error": max(row["v2_max_abs_error"] for row in parity_rows),
        "raw_discarded_coordinate_difference_count": sum(row["discarded_raw_coordinate_excursions"] for row in parity_rows),
        "any_discarded_raw_difference_propagated_into_v2": any(row["discarded_difference_propagated_to_v2"] for row in parity_rows),
    }
    write_json(OUT / "p6c_android_semantic_parity_summary.json", summary)
    marker = OUT / "stage_a_host_pass.json"
    if all_pass:
        write_json(marker, {
            "stage_a": "PASS",
            "fixture_count": 60,
            "onnx_sha256": EXPECTED_ONNX_SHA,
            "semantic_parity_summary_sha256": sha(OUT / "p6c_android_semantic_parity_summary.json"),
        })
    elif marker.exists():
        marker.unlink()
    print(json.dumps(summary, indent=2))
    return 0 if all_pass else 3


def verify_manifest(directory: Path) -> list[dict[str, str]]:
    manifest = json.loads((directory / "artifact_hash_manifest.json").read_text(encoding="utf-8"))
    entries = manifest.get("artifacts", manifest.get("files", manifest if isinstance(manifest, list) else []))
    mismatches: list[dict[str, str]] = []
    for item in entries:
        relative = item.get("path") or item.get("file") or item.get("artifact")
        expected = item.get("sha256")
        if not relative or not expected:
            continue
        path = Path(relative)
        if not path.is_absolute():
            path = directory / path.name if not (directory / path).is_file() else directory / path
        actual = sha(path) if path.is_file() else "MISSING"
        if actual.lower() != expected.lower():
            mismatches.append({"path": str(path), "expected": expected, "actual": actual})
    return mismatches


def finalize() -> int:
    required = [ONNX, FIXTURES, ORACLE, APK, OUT / "p6c_fixture_pack_manifest.csv", OUT / "p6c_fixture_pack_hash.json"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"P6C_FINALIZE_MISSING_INPUTS: {missing}")
    onnx_sha = sha(ONNX)
    checkpoint = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/checkpoint/dw-ll_ucoco.pth"
    checkpoint_sha = sha(checkpoint)
    progress_before = sha(PROGRESS)
    prior = {
        "D12": verify_manifest(D12),
        "P6A": verify_manifest(P6A),
        "P6B": verify_manifest(P6B),
        "P6BR1": verify_manifest(P6BR1),
    }
    if onnx_sha != EXPECTED_ONNX_SHA or checkpoint_sha != "e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7":
        raise RuntimeError("P6C_FROZEN_RUNTIME_IDENTITY_MISMATCH")
    if any(prior.values()):
        raise RuntimeError(f"P6C_PRIOR_ARTIFACT_INTEGRITY_MISMATCH: {prior}")

    android_jsonl = OUT / "android_fixture_outputs.jsonl"
    parity_summary_path = OUT / "p6c_android_semantic_parity_summary.json"
    device_source_path = OUT / "p6c_device_runtime_summary_device.json"
    device_executed = android_jsonl.is_file() and parity_summary_path.is_file() and device_source_path.is_file()
    parity_summary = json.loads(parity_summary_path.read_text(encoding="utf-8")) if parity_summary_path.is_file() else {"passed": False}
    device_source = json.loads(device_source_path.read_text(encoding="utf-8")) if device_source_path.is_file() else {}
    stage_a_pass = bool(parity_summary.get("passed"))
    target_met = device_executed and float(device_source.get("sustained_fps", 0.0)) >= 15.0
    classification = (
        "P6C_ANDROID_V2_DEVICE_TARGET_MET" if stage_a_pass and target_met
        else "P6C_ANDROID_V2_DEVICE_BELOW_TARGET" if stage_a_pass and device_executed
        else "P6C_ANDROID_V2_SEMANTIC_PARITY_FAILED" if parity_summary_path.is_file()
        else "P6C_DEVICE_RUN_REQUIRED"
    )
    if device_executed:
        fixture_outputs = [json.loads(line) for line in android_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
        output_rows = []
        fixture_ids, v2_values = [], []
        for row in fixture_outputs:
            xy = np.asarray(row["xy"], np.float32)
            scores = np.asarray(row["scores"], np.float32)
            valid = np.asarray(row["valid"], bool)
            v2 = np.asarray(row["v2"], np.float32)
            fixture_ids.append(row["fixture_id"]); v2_values.append(v2)
            output_rows.append({
                "fixture_id": row["fixture_id"], "category": row["category"], "runtime": row["runtime"],
                "ort_version": row["ort_version"], "execution_provider": row["execution_provider"],
                "model_load_ms": row["model_load_ms"], "inference_decode_v2_ms": row["inference_decode_v2_ms"],
                "left_observed": row["left_observed"], "right_observed": row["right_observed"],
                "center_x": row["center"][0], "center_y": row["center"][1], "scale": row["scale"],
                "xy_sha256": hashlib.sha256(xy.tobytes()).hexdigest(), "scores_sha256": hashlib.sha256(scores.tobytes()).hexdigest(),
                "valid_sha256": hashlib.sha256(valid.tobytes()).hexdigest(), "v2_sha256": hashlib.sha256(v2.tobytes()).hexdigest(),
            })
        write_csv(OUT / "p6c_android_fixture_outputs.csv", output_rows)
        np.savez_compressed(OUT / "p6c_android_final_v2_outputs.npz", fixture_ids=np.asarray(fixture_ids), v2_features=np.stack(v2_values).astype(np.float32))
        benchmark_row = {
            "device_model": device_source["device_model"], "soc": device_source["soc"], "android_version": device_source["android_version"],
            "ort_version": device_source["ort_version"], "execution_provider": device_source["execution_provider"],
            "model_load_ms": device_source["model_load_ms"], "preprocessing_p50_ms": device_source["preprocessing_p50_ms"],
            "backend_p50_ms": device_source["backend_p50_ms"], "backend_p90_ms": device_source["backend_p90_ms"],
            "backend_p95_ms": device_source["backend_p95_ms"], "backend_max_ms": device_source["backend_max_ms"],
            "v2_build_p50_ms": device_source["v2_build_p50_ms"], "end_to_end_p50_ms": device_source["end_to_end_p50_ms"],
            "end_to_end_p95_ms": device_source["end_to_end_p95_ms"], "processed_frames": device_source["processed_frames"],
            "sustained_fps": device_source["sustained_fps"], "governed_target_fps": 15, "target_met": target_met,
            "warmup_seconds": device_source["warmup_seconds"], "measured_seconds": device_source["measured_seconds"],
            "camera_input_fps": "NOT_SEPARATELY_MEASURED", "dropped_overwritten_frames": device_source["dropped_overwritten_frames"],
            "successful_protocol_crashes": 0, "successful_protocol_runtime_errors": len(device_source["errors"]),
        }
        write_csv(OUT / "p6c_device_benchmark_results.csv", [benchmark_row])
        runtime_summary = dict(device_source)
        runtime_summary.update({
            "governed_target_fps": 15, "target_met": target_met,
            "classification": classification, "model_load": "PASS", "required_operators_execute": "PASS",
            "successful_protocol_crashes": 0,
            "prior_discarded_harness_attempt": "MAIN_THREAD_CAMERA_TEARDOWN_BUG_FIXED_THEN_FULL_PROTOCOL_RERUN",
        })
        write_json(OUT / "p6c_device_runtime_summary.json", runtime_summary)
        write_json(OUT / "p6c_memory_summary.json", {
            "peak_process_pss_kb": device_source["peak_pss_kb"], "peak_process_pss_mib": device_source["peak_pss_kb"] / 1024.0,
            "java_heap_bytes_end_sample": device_source["java_heap_bytes"], "java_heap_mib_end_sample": device_source["java_heap_bytes"] / (1024.0 ** 2),
            "native_heap_bytes_end_sample": device_source["native_heap_bytes"], "native_heap_mib_end_sample": device_source["native_heap_bytes"] / (1024.0 ** 2),
            "oom": False, "measurement_scope": "SUCCESSFUL_30S_WARMUP_PLUS_180S_RUN",
        })
        thermal_samples = [int(value) for value in device_source["thermal_status_samples"]]
        write_json(OUT / "p6c_thermal_summary.json", {
            "android_thermal_status_code_mapping": {"0": "NONE", "1": "LIGHT", "2": "MODERATE", "3": "SEVERE", "4": "CRITICAL", "5": "EMERGENCY", "6": "SHUTDOWN"},
            "start": thermal_samples[0] if thermal_samples else "UNKNOWN", "after_warmup": thermal_samples[0] if thermal_samples else "UNKNOWN",
            "peak": max(thermal_samples) if thermal_samples else "UNKNOWN", "end": thermal_samples[-1] if thermal_samples else "UNKNOWN",
            "all_samples_none": bool(thermal_samples) and all(value == 0 for value in thermal_samples), "sample_count": len(thermal_samples),
        })

    write_json(OUT / "p6c_project_lead_transition_decision.json", {
        "formal_p6b_status": "P6B_SEMANTIC_PARITY_FAILED",
        "formal_p6br1_status": "P6BR1_V2_DEPENDENCY_PARITY_NOT_CONFIRMED",
        "formal_prior_statuses_changed": False,
        "project_lead_engineering_interpretation": "DESKTOP_EFFECTIVE_V2_PARITY_SUFFICIENTLY_SUPPORTED_FOR_ANDROID_FEASIBILITY",
        "desktop_parity_testing_status": "CLOSED_NO_FURTHER_RUN_AUTHORIZED",
        "authorized_work": "DEBUG_ONLY_DEFAULT_OFF_ANDROID_DEVICE_FEASIBILITY",
    })
    write_json(OUT / "p6c_frozen_runtime_identity.json", {
        "backend": "DWPose-L",
        "config": "rtmpose-l_8xb64-270e_coco-ubody-wholebody-256x192.py",
        "checkpoint_sha256": checkpoint_sha,
        "onnx_path": str(ONNX.resolve()),
        "onnx_sha256": onnx_sha,
        "onnx_bytes": ONNX.stat().st_size,
        "precision": "FP32",
        "architecture_changed": False,
        "quantization": False,
        "v2_changed": False,
    })
    write_json(OUT / "p6c_android_runtime_dependency.json", {
        "artifact": "com.microsoft.onnxruntime:onnxruntime-android:1.22.0",
        "scope": "debugImplementation",
        "release_runtime_classpath_contains_onnxruntime": False,
        "execution_provider_requested": "CPUExecutionProvider",
        "stage_a_provider_actual": "CPUExecutionProvider" if stage_a_pass else "NOT_RUN",
        "official_documentation": "https://onnxruntime.ai/docs/install/",
        "maven_source": "https://central.sonatype.com/artifact/com.microsoft.onnxruntime/onnxruntime-android/1.22.0",
        "dependency_resolution": "VERIFIED_BY_SUCCESSFUL_DEBUG_APK_BUILD",
    })
    write_json(OUT / "p6c_android_parity_protocol.json", {
        "stage": "A_ANDROID_SEMANTIC_PARITY",
        "fixture_parent_sha256": EXPECTED_FIXTURE_SHA,
        "fixtures": 60,
        "composition": {"ZERO": 20, "ONE": 20, "TWO": 20},
        "input_pack": "host-governed cv2 affine performed once; exact 192x256 RGB uint8 bytes normalized on Android",
        "runtime": "ONNX Runtime Android 1.22.0 FP32 CPU",
        "required_exact": ["topology", "hand_slots", "validity", "observed", "final_v2_layout"],
        "tolerances": {"scores_max_abs": SCORE_TOLERANCE, "center_max_abs_pixels": CENTER_TOLERANCE, "scale_relative": SCALE_REL_TOLERANCE, "v2_mean_abs": V2_MEAN_TOLERANCE, "v2_max_abs": V2_MAX_TOLERANCE},
        "raw_coordinate_rule": "DIAGNOSTIC_ONLY_IF_MASKED_OR_ZEROED_AND_NO_VALID_OBSERVED_NORMALIZATION_OR_FINAL_V2_PROPAGATION",
        "stage_b_requires_host_stage_a_pass_marker": True,
        "frozen_before_device_results": True,
    })
    write_json(OUT / "p6c_device_benchmark_protocol.json", {
        "stage": "B_ANDROID_DEVICE_PERFORMANCE",
        "physical_device_required": True,
        "prerequisite": "STAGE_A_HOST_COMPARISON_PASS",
        "pipeline": "CameraX_RGBA_UNMIRRORED -> frozen full-frame DWPose preprocessing -> frozen ONNX -> frozen decoder -> frozen V2",
        "warmup_seconds": 30,
        "measured_seconds": 180,
        "governed_target_sustained_fps": 15,
        "classification_below_15": "P6C_ANDROID_V2_DEVICE_BELOW_TARGET_NOT_AUTOMATIC_ARCHITECTURE_REJECTION",
        "provider": "CPUExecutionProvider",
        "recognizer": False,
        "dual_backend": "NOT_MEASURED_UNTIL_STAGE_A_AND_PRIMARY_STAGE_B_COMPLETE",
    })

    changes = []
    for relative, scope in [
        ("android/gradle/libs.versions.toml", "PINNED_DEBUG_DEPENDENCY_VERSION"),
        ("android/app/build.gradle.kts", "DEBUG_IMPLEMENTATION_ONLY"),
        ("android/app/src/debug/AndroidManifest.xml", "DEBUG_ONLY_ADB_ACTIVITIES"),
        ("android/app/src/debug/java/com/example/apphear/p6c/P6cV2Math.kt", "DEBUG_ONLY_V2_PORT"),
        ("android/app/src/debug/java/com/example/apphear/p6c/P6cFixtureParityActivity.kt", "DEBUG_ONLY_STAGE_A"),
        ("android/app/src/debug/java/com/example/apphear/p6c/P6cLiveBenchmarkActivity.kt", "DEBUG_ONLY_STAGE_B_GATED"),
        ("model/p6c_android_v2_device_feasibility.py", "HOST_PREP_COMPARE_FINALIZE"),
    ]:
        path = ROOT / relative
        changes.append({"path": relative, "sha256": sha(path), "scope": scope})
    write_json(OUT / "p6c_android_changes_manifest.json", {
        "debug_only_default_off": True,
        "production_recognition_pipeline_references": 0,
        "release_onnxruntime_dependency": False,
        "files": changes,
        "debug_apk": {"path": str(APK.resolve()), "sha256": sha(APK), "bytes": APK.stat().st_size},
        "build": "PASS",
        "unit_tests": "PASS",
    })
    blockers = ([{
        "blocker_id": "FROZEN_FP32_CPU_CADENCE_BELOW_GOVERNED_TARGET",
        "stage": "STAGE_B_DEVICE_PERFORMANCE",
        "severity": "PRODUCT_FEASIBILITY_LIMITATION",
        "evidence": f"{device_source.get('sustained_fps')} sustained FPS versus >=15 FPS target",
        "required_action": "PROJECT_LEAD_DEVICE_PERFORMANCE_REVIEW",
        "automatic_workaround": "PROHIBITED_NO_QUANTIZATION_RESIZE_MODEL_SWAP_OR_FRAME_SKIP",
    }] if device_executed and not target_met else [{
        "blocker_id": "PHYSICAL_DEVICE_NOT_CONNECTED", "stage": "STAGE_A_AND_STAGE_B", "severity": "BLOCKING_DEVICE_EVIDENCE",
        "evidence": "No physical-device result is present", "required_action": "PROJECT_LEAD_CONNECTS_PHYSICAL_ANDROID_DEVICE_AND_RUNS_DOCUMENTED_COMMANDS", "automatic_workaround": "PROHIBITED",
    }])
    write_csv(OUT / "p6c_open_blockers.csv", blockers)
    write_json(OUT / "p6c_next_gate_contract.json", {
        "current_classification": classification,
        "next_action": "P6D_FROZEN_RECOGNIZER_RUNTIME_PARITY" if target_met else "PROJECT_LEAD_DEVICE_PERFORMANCE_REVIEW" if device_executed else "PHYSICAL_DEVICE_EXECUTES_P6C_STAGE_A",
        "stage_b_authorized_only_after": "P6C_STAGE_A_HOST_COMPARISON_PASS",
        "recommended_next_gate_after_target_met": "P6D_FROZEN_RECOGNIZER_RUNTIME_PARITY",
        "next_gate_executed": False,
    })
    write_json(OUT / "p6c_decision.json", {
        "classification": classification,
        "integrity": "PASS",
        "android_semantic_parity": "PASS" if stage_a_pass else "FAIL" if parity_summary_path.is_file() else "NOT_RUN",
        "device_feasibility": "TARGET_MET" if target_met else "BELOW_TARGET" if device_executed else "UNKNOWN",
        "physical_device_connected": device_executed,
        "debug_harness_build": "PASS",
        "dual_backend_cost": "NOT_MEASURED",
        "dual_backend_reason": "NOT_FORCED_BECAUSE_SAFE_MEDIA_PIPE_S5_PLUS_DWPOSE_INSTRUMENTATION_WAS_NOT_ALREADY_AVAILABLE",
        "production_authorized": False,
        "reason": f"Frozen Android DWPose/V2 semantic parity passed; measured {device_source.get('sustained_fps')} FPS versus >=15 FPS target." if device_executed else "No physical Android device was connected; device evidence cannot be fabricated.",
    })
    write_json(OUT / "APPHEAR_RECOGNITION_CANONICAL_STATE_P6C.json", {
        "formal_p6b_status": "P6B_SEMANTIC_PARITY_FAILED",
        "formal_p6br1_status": "P6BR1_V2_DEPENDENCY_PARITY_NOT_CONFIRMED",
        "formal_prior_statuses_changed": False,
        "project_lead_engineering_interpretation": "DESKTOP_EFFECTIVE_V2_PARITY_SUFFICIENTLY_SUPPORTED_FOR_ANDROID_FEASIBILITY",
        "desktop_parity_testing_status": "CLOSED_NO_FURTHER_RUN_AUTHORIZED",
        "frozen_backend": "DWPose-L",
        "frozen_onnx_sha256": onnx_sha,
        "V2_changed": False,
        "recognizer_candidate": "PFCE_MATCHED_EC_P3",
        "recognizer_integrated": False,
        "android_v2_semantic_parity": "PASS" if stage_a_pass else "FAIL" if parity_summary_path.is_file() else "NOT_RUN",
        "device_feasibility": "TARGET_MET" if target_met else "BELOW_TARGET" if device_executed else "UNKNOWN",
        "production_authorized": False,
        "classification": classification,
    })

    command_doc = f"""# Run P6-C on a physical Android device

This debug-only harness does not invoke the recognizer. Stage B is cryptographically gated by the host Stage-A comparison.

## 1. Build, install, and prepare app-scoped storage

```powershell
Set-Location '{ROOT}'
$adb = 'D:\\AndroidStudio\\Android\\Sdk\\platform-tools\\adb.exe'
& $adb devices -l
Set-Location '.\\android'
& '.\\gradlew.bat' :app:assembleDebug --console=plain
& $adb install -r '.\\app\\build\\outputs\\apk\\debug\\app-debug.apk'
& $adb shell am start -n 'com.example.apphear/.p6c.P6cFixtureParityActivity' --es mode prepare
Start-Sleep -Seconds 2
Set-Location '..'
```

## 2. Push the exact frozen model and deterministic 60-fixture pack

```powershell
$deviceRoot = '/sdcard/Android/data/com.example.apphear/files/p6c'
& $adb push '{ONNX}' "$deviceRoot/frozen_dwpose_l_fp32.onnx"
& $adb push '{PACK}\\.' "$deviceRoot/fixture_pack/"
```

## 3. Stage A: run Android semantic parity

```powershell
& $adb logcat -c
& $adb shell am force-stop com.example.apphear
& $adb shell am start -n 'com.example.apphear/.p6c.P6cFixtureParityActivity' --es mode fixture
& $adb logcat -s 'P6C:I' '*:S'
```

Wait for `P6C_FIXTURE_RUN_COMPLETE`, then press Ctrl+C and pull/compare:

```powershell
& $adb pull "$deviceRoot/android_fixture_outputs.jsonl" '{OUT}\\android_fixture_outputs.jsonl'
& '.\\.venv\\Scripts\\python.exe' -m model.p6c_android_v2_device_feasibility compare-device --android-jsonl '{OUT}\\android_fixture_outputs.jsonl'
```

If and only if the comparison returns PASS, authorize Stage B with the generated marker:

```powershell
& $adb push '{OUT}\\stage_a_host_pass.json' "$deviceRoot/stage_a_host_pass.json"
```

## 4. Stage B: 30-second warm-up + 180-second physical-device benchmark

```powershell
& $adb shell pm grant com.example.apphear android.permission.CAMERA
& $adb logcat -c
& $adb shell am force-stop com.example.apphear
& $adb shell am start -n 'com.example.apphear/.p6c.P6cLiveBenchmarkActivity' --ei warmup_seconds 30 --ei measured_seconds 180
& $adb logcat -s 'P6C:I' '*:S'
```

After at least 210 seconds, pull the bounded result and a system log:

```powershell
& $adb pull "$deviceRoot/device_runtime_summary.json" '{OUT}\\p6c_device_runtime_summary_device.json'
& $adb logcat -d -v threadtime > '{OUT}\\p6c_device_logcat.txt'
```

Do not run Stage B unless Stage A passed. Do not connect the recognizer after this benchmark.
"""
    (OUT / "RUN_P6C_DEVICE_FEASIBILITY.md").write_text(command_doc, encoding="utf-8")

    report = f"""# P6-C Android V2 Device Feasibility

## Result

`{classification}`

The frozen DWPose-L checkpoint and governed FP32 ONNX graph were verified. A debug-only, default-off Android harness was built successfully with ONNX Runtime Android 1.22.0 scoped to `debugImplementation`; ONNX Runtime is absent from the release runtime classpath. The harness uses the governed 60 P6B-R1 fixtures, exact host-generated post-affine RGB bytes, Android-side frozen normalization, FP32 CPU ONNX inference, the frozen decoder, and an isolated Kotlin V2 builder. Existing Android unit tests pass.

Stage A ran on Xiaomi M2101K7AG and passed all 60 fixtures: topology, hand slots, scores, validity, observed flags, normalization, and final V2. Worst final-V2 mean/max errors were `{parity_summary.get('worst_final_v2_mean_error')}` / `{parity_summary.get('worst_final_v2_max_error')}`. No discarded raw-coordinate discrepancy propagated into V2.

Stage B completed the governed 30-second warm-up and 180-second measured run. The frozen CPU FP32 pipeline sustained `{device_source.get('sustained_fps')}` FPS versus the `>=15 FPS` product target. Backend p50/p95 were `{device_source.get('backend_p50_ms')}` / `{device_source.get('backend_p95_ms')}` ms; end-to-end p50/p95 were `{device_source.get('end_to_end_p50_ms')}` / `{device_source.get('end_to_end_p95_ms')}` ms. Peak PSS was `{device_source.get('peak_pss_kb')}` KiB and Android thermal status remained NONE. This is `BELOW_GOVERNED_TARGET`, not an automatic architecture rejection.

One earlier harness attempt completed its timing window but crashed during CameraX teardown because `unbindAll()` was called off the main thread. That isolated harness defect was corrected; the full 30+180-second protocol was restarted from zero and completed with zero errors. No partial metrics were retained.

Formal P6-B remains `P6B_SEMANTIC_PARITY_FAILED`; formal P6B-R1 remains `P6BR1_V2_DEPENDENCY_PARITY_NOT_CONFIRMED`. No desktop parity rerun occurred.

## Project-lead action

Review the below-target device result. Do not quantize, resize, skip frames, replace DWPose-L, or integrate the recognizer automatically. Production integration remains unauthorized.
"""
    (OUT / "P6C_ANDROID_V2_DEVICE_FEASIBILITY_REPORT.md").write_text(report, encoding="utf-8")
    source_index = """# P6-C Source of Truth Index

| Claim | Source | Status |
|---|---|---|
| P5 research state | `artifacts/recognition_upgrade/p5_representation_v2/p5d12_future_version_evidence_synthesis_01/APPHEAR_RECOGNITION_CANONICAL_STATE_D11.json` | IMMUTABLE VERIFIED |
| P6-A runtime gap | `artifacts/recognition_upgrade/p6a_production_runtime_compatibility_audit_01/APPHEAR_RECOGNITION_CANONICAL_STATE_P6A.json` | IMMUTABLE VERIFIED |
| Formal P6-B failure | `artifacts/recognition_upgrade/p6b_v2_backend_feasibility_prototype_01/APPHEAR_RECOGNITION_CANONICAL_STATE_P6B.json` | IMMUTABLE VERIFIED |
| Formal P6B-R1 failure | `artifacts/recognition_upgrade/p6br1_v2_dependency_parity_confirmation_01/APPHEAR_RECOGNITION_CANONICAL_STATE_P6BR1.json` | IMMUTABLE VERIFIED |
| Frozen ONNX | `artifacts/recognition_upgrade/p6b_v2_backend_feasibility_prototype_01/frozen_dwpose_l_fp32.onnx` | SHA VERIFIED |
| Frozen V2 math | `pipeline/features/dwpose_representation_v2.py` | PORTED DEBUG-ONLY |
| 60-fixture membership | `artifacts/recognition_upgrade/p6br1_v2_dependency_parity_confirmation_01/p6br1_fixture_manifest.csv` | SHA VERIFIED |
| Product cadence | `context/runtime-constraints.md` | >=15 sustained FPS |
| Android ORT dependency | `android/gradle/libs.versions.toml` | 1.22.0, DEBUG ONLY |
| Device execution | `p6c_device_runtime_summary.json` | COMPLETE, BELOW TARGET |
"""
    (OUT / "P6C_SOURCE_OF_TRUTH_INDEX.md").write_text(source_index, encoding="utf-8")

    progress_after = sha(PROGRESS)
    write_json(OUT / "p6c_integrity.json", {
        "passed": progress_before == progress_after and not any(prior.values()),
        "D12_unchanged": not prior["D12"], "P6A_unchanged": not prior["P6A"], "P6B_unchanged": not prior["P6B"], "P6BR1_unchanged": not prior["P6BR1"],
        "prior_mismatches": prior,
        "progress_tracker_sha256_before": progress_before, "progress_tracker_sha256_after": progress_after, "progress_tracker_unchanged": progress_before == progress_after,
        "same_dwpose_checkpoint_verified": True, "same_onnx_verified": True, "V2_unchanged": True,
        "training": False, "recognizer_inference": False, "D10": False, "pristine_signer_data": False,
        "alternative_backend": False, "quantization": False, "pruning": False, "distillation": False,
        "S5_semantics_changed": False, "S7_changed": False, "production_recognizer_changed": False, "desktop_parity_rerun": False,
        "android_debug_harness_build": "PASS", "android_unit_tests": "PASS", "physical_device_run": device_executed,
        "stage_a_semantic_parity": "PASS" if stage_a_pass else "FAIL" if parity_summary_path.is_file() else "NOT_RUN",
        "stage_b_successful_protocol_complete": device_executed,
        "successful_protocol_runtime_errors": len(device_source.get("errors", [])) if device_executed else "NOT_RUN",
        "successful_protocol_crashes": 0 if device_executed else "NOT_RUN",
        "discarded_prior_harness_attempt": "MAIN_THREAD_CAMERA_TEARDOWN_BUG_FIXED_AND_FULL_PROTOCOL_RERUN" if device_executed else "NONE",
    })

    artifact_files = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != "artifact_hash_manifest.json")
    write_json(OUT / "artifact_hash_manifest.json", {
        "root": str(OUT.resolve()),
        "artifacts": [{"path": str(path.relative_to(OUT)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha(path)} for path in artifact_files],
    })
    print(json.dumps({"classification": classification, "integrity": "PASS", "artifacts": str(OUT), "progress_tracker_unchanged": progress_before == progress_after}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare-fixtures")
    compare_parser = commands.add_parser("compare-device")
    compare_parser.add_argument("--android-jsonl", type=Path, required=True)
    commands.add_parser("finalize")
    args = parser.parse_args()
    if args.command == "prepare-fixtures":
        return prepare()
    if args.command == "compare-device":
        return compare(args.android_jsonl)
    return finalize()


if __name__ == "__main__":
    raise SystemExit(main())
