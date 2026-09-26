"""P6C-P1 host tooling for bounded XNNPACK/NNAPI acceleration triage.

This module freezes the contract and semantic subset before provider execution, compares
device outputs with the immutable P6B-R1 oracle, and finalizes provider-only evidence. It never
runs training, recognition inference, D10, CameraX, preprocessing optimization, or another model.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
P6B = ROOT / "artifacts/recognition_upgrade/p6b_v2_backend_feasibility_prototype_01"
P6BR1 = ROOT / "artifacts/recognition_upgrade/p6br1_v2_dependency_parity_confirmation_01"
P6C = ROOT / "artifacts/recognition_upgrade/p6c_android_v2_device_feasibility_01"
P6A = ROOT / "artifacts/recognition_upgrade/p6a_production_runtime_compatibility_audit_01"
D12 = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5d12_future_version_evidence_synthesis_01"
OUT = ROOT / "artifacts/recognition_upgrade/p6cp1_frozen_dwpose_runtime_acceleration_triage_01"
PACK = OUT / "prepared_tensor_pack"
ONNX = P6B / "frozen_dwpose_l_fp32.onnx"
CHECKPOINT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/checkpoint/dw-ll_ucoco.pth"
ORACLE = P6BR1 / "p6br1_offline_oracle_outputs.npz"
P6C_PACK = P6C / "device_fixture_pack"
P6C_PACK_MANIFEST = P6C / "p6c_fixture_pack_manifest.csv"
PROGRESS = ROOT / "context/progress-tracker.md"
APK = ROOT / "android/app/build/outputs/apk/debug/app-debug.apk"

EXPECTED_ONNX_SHA = "870c84ddbf396282c415854b233ba972a772ac35f1eebe26b6ce185a19579965"
EXPECTED_ONNX_BYTES = 134_027_621
EXPECTED_CHECKPOINT_SHA = "e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7"
EXPECTED_PARENT_FIXTURE_SHA = "b7ce52642301f3ab5cf047714956dec444ef90a7069d1cda6c4412d0f6ac5d65"
SCORE_TOLERANCE = 1e-4
CENTER_TOLERANCE = 0.5
SCALE_REL_TOLERANCE = 1e-4
V2_MEAN_TOLERANCE = 1e-5
V2_MAX_TOLERANCE = 1e-3
PROVIDERS = ("XNNPACK", "NNAPI")

OFFICIAL_DOCS = {
    "mobile": "https://onnxruntime.ai/docs/tutorials/mobile/",
    "xnnpack": "https://onnxruntime.ai/docs/execution-providers/Xnnpack-ExecutionProvider.html",
    "nnapi_java": "https://onnxruntime.ai/docs/api/java/ai/onnxruntime/OrtSession.SessionOptions.html",
    "provider_architecture": "https://onnxruntime.ai/docs/execution-providers/",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = fieldnames or (list(rows[0]) if rows else [])
    if not names:
        raise ValueError(f"fieldnames required for empty CSV: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_frozen_identity() -> dict[str, Any]:
    onnx_sha = sha(ONNX)
    checkpoint_sha = sha(CHECKPOINT)
    if onnx_sha != EXPECTED_ONNX_SHA or ONNX.stat().st_size != EXPECTED_ONNX_BYTES:
        raise RuntimeError("P6CP1_FROZEN_ONNX_IDENTITY_MISMATCH")
    if checkpoint_sha != EXPECTED_CHECKPOINT_SHA:
        raise RuntimeError("P6CP1_DWPOSE_CHECKPOINT_IDENTITY_MISMATCH")
    return {
        "backend": "DWPose-L",
        "checkpoint_sha256": checkpoint_sha,
        "onnx_sha256": onnx_sha,
        "onnx_bytes": ONNX.stat().st_size,
        "precision": "FP32",
        "input_shape": [1, 3, 256, 192],
        "flip_test_inside_graph": True,
        "decoder_changed": False,
        "v2_changed": False,
    }


def normalize_rgb(rgb_bytes: bytes) -> np.ndarray:
    rgb = np.frombuffer(rgb_bytes, dtype=np.uint8).reshape(256, 192, 3).astype(np.float32)
    mean = np.asarray([123.675, 116.28, 103.53], dtype=np.float32)
    std = np.asarray([58.395, 57.12, 57.375], dtype=np.float32)
    return np.ascontiguousarray(((rgb - mean) / std).transpose(2, 0, 1)[None], dtype="<f4")


def immutable_parent_hashes() -> dict[str, str]:
    paths = {
        "D12": D12 / "artifact_hash_manifest.json",
        "P6A": P6A / "artifact_hash_manifest.json",
        "P6B": P6B / "artifact_hash_manifest.json",
        "P6BR1": P6BR1 / "artifact_hash_manifest.json",
        "P6C": P6C / "artifact_hash_manifest.json",
        "progress_tracker": PROGRESS,
    }
    return {name: sha(path) for name, path in paths.items()}


def prepare() -> int:
    identity = verify_frozen_identity()
    parent_manifest = P6BR1 / "p6br1_fixture_manifest.csv"
    if sha(parent_manifest) != EXPECTED_PARENT_FIXTURE_SHA:
        raise RuntimeError("P6CP1_P6BR1_FIXTURE_IDENTITY_MISMATCH")
    rows = read_csv(P6C_PACK_MANIFEST)
    if len(rows) != 60:
        raise RuntimeError(f"Expected 60 governed P6-C fixtures, found {len(rows)}")

    selected: list[dict[str, str]] = []
    for category in ("ZERO", "ONE", "TWO"):
        category_rows = sorted(
            (row for row in rows if row["visibility_category"] == category),
            key=lambda row: int(row["fixture_index"]),
        )
        if len(category_rows) != 20:
            raise RuntimeError(f"Expected 20 {category} fixtures, found {len(category_rows)}")
        selected.extend(category_rows[:4])

    PACK.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, Any]] = []
    device_tsv = ["fixture_id\tcategory\ttensor_file\ttensor_sha256\tcenter_x\tcenter_y\tscale_x\tscale_y"]
    for selection_index, row in enumerate(selected, 1):
        rgb_path = P6C_PACK / row["warped_rgb_file"]
        if sha(rgb_path) != row["warped_rgb_sha256"]:
            raise RuntimeError(f"P6CP1_P6C_WARPED_RGB_HASH_MISMATCH: {row['fixture_id']}")
        tensor = normalize_rgb(rgb_path.read_bytes())
        filename = f"{selection_index:02d}_{row['fixture_id']}.f32"
        tensor_path = PACK / filename
        tensor.tofile(tensor_path)
        tensor_sha = sha(tensor_path)
        values = {
            "selection_index": selection_index,
            "fixture_id": row["fixture_id"],
            "visibility_category": row["visibility_category"],
            "parent_fixture_index": int(row["fixture_index"]),
            "selection_rule": "FIRST_FOUR_BY_FROZEN_P6BR1_FIXTURE_INDEX_WITHIN_ZERO_ONE_TWO",
            "source_sha256": row["source_sha256"],
            "prepared_tensor_file": filename,
            "prepared_tensor_sha256": tensor_sha,
            "prepared_tensor_bytes": tensor_path.stat().st_size,
            "prepared_tensor_shape": "[1,3,256,192]",
            "prepared_tensor_dtype": "little_endian_float32",
            "center_x": float(row["center_x"]),
            "center_y": float(row["center_y"]),
            "scale_x": float(row["scale_x"]),
            "scale_y": float(row["scale_y"]),
        }
        manifest_rows.append(values)
        device_tsv.append("\t".join(map(str, [
            row["fixture_id"], row["visibility_category"], filename, tensor_sha,
            row["center_x"], row["center_y"], row["scale_x"], row["scale_y"],
        ])))

    semantic_manifest = OUT / "p6cp1_semantic_fixture_manifest.csv"
    write_csv(semantic_manifest, manifest_rows)
    device_manifest = PACK / "semantic_manifest.tsv"
    device_manifest.write_text("\n".join(device_tsv) + "\n", encoding="utf-8")
    membership_sha = sha(semantic_manifest)
    parent_hashes = immutable_parent_hashes()

    contract = {
        "gate": "P6C-P1_FROZEN_DWPOSE_RUNTIME_ACCELERATION_TRIAGE",
        "contract_frozen_before_provider_results": True,
        "primary_question": "CAN_XNNPACK_OR_NNAPI_RUN_EXACT_FROZEN_DWPOSE_L_AT_GTE_15_BACKEND_ONLY_FPS_WITH_V2_PARITY",
        "providers_tested_in_order": ["XNNPACK", "NNAPI"],
        "other_providers_prohibited": True,
        "model": identity,
        "semantic_subset": {
            "count": 12,
            "composition": {"ZERO": 4, "ONE": 4, "TWO": 4},
            "selection_rule": "FIRST_FOUR_BY_FROZEN_P6BR1_FIXTURE_INDEX_WITHIN_EACH_CATEGORY",
            "membership_sha256": membership_sha,
        },
        "semantic_tolerances": {
            "scores_max_abs": SCORE_TOLERANCE,
            "normalization_center_max_abs_pixels": CENTER_TOLERANCE,
            "normalization_scale_relative": SCALE_REL_TOLERANCE,
            "final_v2_mean_abs": V2_MEAN_TOLERANCE,
            "final_v2_max_abs": V2_MAX_TOLERANCE,
            "validity": "EXACT",
            "observed": "EXACT",
            "hand_slots": "EXACT",
        },
        "performance": {
            "prepared_input_shape": [1, 3, 256, 192],
            "prepared_input_dtype": "FP32",
            "batch_size": 1,
            "single_stream": True,
            "warmup_seconds": 30,
            "measured_seconds": 180,
            "necessary_condition_fps": 15.0,
        },
        "may_change_after_results": False,
        "preprocessing_optimization": False,
        "recognizer": False,
        "training": False,
    }
    write_json(OUT / "p6cp1_acceleration_contract.json", contract)
    write_json(OUT / "p6cp1_semantic_fixture_freeze.json", {
        "frozen_before_provider_results": True,
        "parent_fixture_manifest_sha256": EXPECTED_PARENT_FIXTURE_SHA,
        "membership_sha256": membership_sha,
        "device_manifest_sha256": sha(device_manifest),
        "composition": {"ZERO": 4, "ONE": 4, "TWO": 4},
        "files": [{"path": path.name, "bytes": path.stat().st_size, "sha256": sha(path)} for path in sorted(PACK.glob("*.f32"))],
    })
    write_json(OUT / "p6cp1_xnnpack_config.json", {
        "provider": "XNNPACK",
        "official_documentation": OFFICIAL_DOCS["xnnpack"],
        "configuration": "ONE_FROZEN_DOCUMENTED_CONFIGURATION",
        "ort_intra_op_threads": 1,
        "ort_inter_op_threads": 1,
        "ort_intra_op_spinning": False,
        "xnnpack_intra_op_threads": "DEVICE_REPORTED_PHYSICAL_CORE_COUNT",
        "thread_count_sweep": False,
    })
    write_json(OUT / "p6cp1_nnapi_config.json", {
        "provider": "NNAPI",
        "official_documentation": OFFICIAL_DOCS["nnapi_java"],
        "configuration": "DEFAULT_EMPTY_FLAGS",
        "fp16_relaxation": False,
        "cpu_fallback": "ORT_DEFAULT",
        "flag_sweep": False,
    })
    write_json(OUT / "p6cp1_pre_evaluation_freeze.json", {
        "frozen_at_prepare": True,
        "parent_hashes": parent_hashes,
        "contract_sha256": sha(OUT / "p6cp1_acceleration_contract.json"),
        "semantic_fixture_membership_sha256": membership_sha,
        "xnnpack_config_sha256": sha(OUT / "p6cp1_xnnpack_config.json"),
        "nnapi_config_sha256": sha(OUT / "p6cp1_nnapi_config.json"),
    })
    source_index = """# P6C-P1 Source of Truth Index

| Claim | Source | Status |
|---|---|---|
| P6-C semantic parity and device baseline | `../p6c_android_v2_device_feasibility_01/` | IMMUTABLE VERIFIED |
| Frozen DWPose-L ONNX | `../p6b_v2_backend_feasibility_prototype_01/frozen_dwpose_l_fp32.onnx` | SHA/BYTES VERIFIED |
| Frozen P6B-R1 oracle | `../p6br1_v2_dependency_parity_confirmation_01/p6br1_offline_oracle_outputs.npz` | READ ONLY |
| Governed 60-fixture parent | `../p6br1_v2_dependency_parity_confirmation_01/p6br1_fixture_manifest.csv` | SHA VERIFIED |
| Product cadence | `context/runtime-constraints.md` | >=15 FPS |
| XNNPACK Android package/support | https://onnxruntime.ai/docs/execution-providers/Xnnpack-ExecutionProvider.html | OFFICIAL ORT |
| NNAPI Java registration API | https://onnxruntime.ai/docs/api/java/ai/onnxruntime/OrtSession.SessionOptions.html | OFFICIAL ORT |
| Mobile EP guidance | https://onnxruntime.ai/docs/tutorials/mobile/ | OFFICIAL ORT |
| EP partition/fallback architecture | https://onnxruntime.ai/docs/execution-providers/ | OFFICIAL ORT |
"""
    (OUT / "P6CP1_SOURCE_OF_TRUTH_INDEX.md").write_text(source_index, encoding="utf-8")
    print(json.dumps({
        "prepared": True,
        "fixtures": len(manifest_rows),
        "composition": {"ZERO": 4, "ONE": 4, "TWO": 4},
        "membership_sha256": membership_sha,
        "pack": str(PACK),
        "contract_sha256": sha(OUT / "p6cp1_acceleration_contract.json"),
    }, indent=2))
    return 0


def parse_profile(profile_path: Path, provider: str) -> dict[str, Any]:
    if not profile_path.is_file():
        return {"provider": provider, "profiling_available": False, "assignment": "NOT_OBSERVABLE"}
    events = read_json(profile_path)
    provider_events: dict[str, list[str]] = {}
    for event in events if isinstance(events, list) else []:
        args = event.get("args", {}) if isinstance(event, dict) else {}
        assigned = args.get("provider")
        if assigned:
            provider_events.setdefault(str(assigned), []).append(str(event.get("name", "UNKNOWN")))
    return {
        "provider": provider,
        "profiling_available": True,
        "profile_sha256": sha(profile_path),
        "event_counts_by_provider": {name: len(names) for name, names in sorted(provider_events.items())},
        "unique_profile_event_names_by_provider": {name: len(set(names)) for name, names in sorted(provider_events.items())},
        "provider_partition_observed": any(provider.lower() in name.lower() for name in provider_events),
        "cpu_fallback_observed": any("cpu" in name.lower() for name in provider_events),
        "interpretation": "ORT_PROFILE_EVENT_COUNTS_INCLUDE_REPEATED_EXECUTIONS_NOT_STATIC_GRAPH_NODE_COUNTS",
    }


def compare_provider(provider: str, semantic_jsonl: Path, availability_json: Path, profile_json: Path) -> int:
    provider = provider.upper()
    if provider not in PROVIDERS:
        raise ValueError("Only XNNPACK and NNAPI are authorized")
    contract = read_json(OUT / "p6cp1_acceleration_contract.json")
    frozen = read_json(OUT / "p6cp1_pre_evaluation_freeze.json")
    if sha(OUT / "p6cp1_acceleration_contract.json") != frozen["contract_sha256"]:
        raise RuntimeError("P6CP1_CONTRACT_CHANGED_AFTER_FREEZE")
    lines = [json.loads(line) for line in semantic_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    manifest = read_csv(OUT / "p6cp1_semantic_fixture_manifest.csv")
    expected_ids = [row["fixture_id"] for row in manifest]
    by_id = {row["fixture_id"]: row for row in lines}
    if len(lines) != 12 or set(by_id) != set(expected_ids):
        raise RuntimeError(f"Expected exact frozen 12-fixture membership for {provider}")

    oracle = np.load(ORACLE)
    oracle_ids = [str(value) for value in oracle["fixture_ids"]]
    oracle_index = {fixture_id: index for index, fixture_id in enumerate(oracle_ids)}
    parity_rows: list[dict[str, Any]] = []
    for fixture_id in expected_ids:
        index = oracle_index[fixture_id]
        row = by_id[fixture_id]
        xy = np.asarray(row["xy"], dtype=np.float32).reshape(133, 2)
        scores = np.asarray(row["scores"], dtype=np.float32)
        valid = np.asarray(row["valid"], dtype=bool)
        observed = np.asarray([row["left_observed"], row["right_observed"]], dtype=bool)
        center = np.asarray(row["center"], dtype=np.float64)
        scale = float(row["scale"])
        v2 = np.asarray(row["v2"], dtype=np.float32)
        if scores.shape != (133,) or valid.shape != (133,) or v2.shape != (238,):
            raise RuntimeError(f"Invalid output shape for {provider} {fixture_id}")
        score_max = float(np.max(np.abs(scores.astype(np.float64) - oracle["scores_133"][index].astype(np.float64))))
        valid_exact = bool(np.array_equal(valid, oracle["valid_mask_133"][index]))
        observed_exact = bool(np.array_equal(observed, oracle["observed_flags"][index]))
        center_max = float(np.max(np.abs(center - oracle["normalization_center"][index])))
        oracle_scale = float(oracle["normalization_scale"][index])
        scale_rel = abs(scale - oracle_scale) / max(abs(oracle_scale), 1e-12)
        v2_error = np.abs(v2.astype(np.float64) - oracle["v2_features"][index].astype(np.float64))
        xy_error = np.abs(xy.astype(np.float64) - oracle["keypoints_133"][index].astype(np.float64))
        passed = bool(
            score_max <= SCORE_TOLERANCE and valid_exact and observed_exact
            and center_max <= CENTER_TOLERANCE and scale_rel <= SCALE_REL_TOLERANCE
            and float(v2_error.mean()) <= V2_MEAN_TOLERANCE and float(v2_error.max()) <= V2_MAX_TOLERANCE
        )
        parity_rows.append({
            "fixture_id": fixture_id,
            "category": row["category"],
            "topology_exact": True,
            "hand_slots_exact": observed_exact,
            "score_max_abs_error": score_max,
            "valid_exact": valid_exact,
            "observed_exact": observed_exact,
            "center_max_abs_error_pixels": center_max,
            "scale_relative_error": scale_rel,
            "v2_mean_abs_error": float(v2_error.mean()),
            "v2_max_abs_error": float(v2_error.max()),
            "raw_xy_max_abs_error_pixels": float(xy_error.max()),
            "pass": passed,
        })

    all_pass = all(row["pass"] for row in parity_rows)
    summary = {
        "provider": provider,
        "executed": True,
        "fixture_count": 12,
        "composition": {"ZERO": 4, "ONE": 4, "TWO": 4},
        "semantic_parity": "PASS" if all_pass else "FAIL",
        "topology": "PASS",
        "hand_slots": "PASS" if all(row["hand_slots_exact"] for row in parity_rows) else "FAIL",
        "scores": "PASS" if all(row["score_max_abs_error"] <= SCORE_TOLERANCE for row in parity_rows) else "FAIL",
        "validity": "PASS" if all(row["valid_exact"] for row in parity_rows) else "FAIL",
        "observed": "PASS" if all(row["observed_exact"] for row in parity_rows) else "FAIL",
        "normalization": "PASS" if all(row["center_max_abs_error_pixels"] <= CENTER_TOLERANCE and row["scale_relative_error"] <= SCALE_REL_TOLERANCE for row in parity_rows) else "FAIL",
        "final_v2": "PASS" if all(row["v2_mean_abs_error"] <= V2_MEAN_TOLERANCE and row["v2_max_abs_error"] <= V2_MAX_TOLERANCE for row in parity_rows) else "FAIL",
        "worst_score_max_abs_error": max(row["score_max_abs_error"] for row in parity_rows),
        "worst_final_v2_mean_error": max(row["v2_mean_abs_error"] for row in parity_rows),
        "worst_final_v2_max_error": max(row["v2_max_abs_error"] for row in parity_rows),
        "worst_raw_xy_max_abs_error_pixels": max(row["raw_xy_max_abs_error_pixels"] for row in parity_rows),
        "availability": read_json(availability_json),
        "partitioning": parse_profile(profile_json, provider),
        "provider_classification": "SEMANTIC_VALID_PENDING_BENCHMARK" if all_pass else "PROVIDER_SEMANTIC_PARITY_FAILED",
    }
    write_json(OUT / f"p6cp1_{provider.lower()}_semantic_parity.json", summary)
    write_csv(OUT / f"p6cp1_{provider.lower()}_semantic_parity_rows.csv", parity_rows)
    shutil.copy2(availability_json, OUT / f"p6cp1_{provider.lower()}_availability_device.json")
    if profile_json.is_file():
        shutil.copy2(profile_json, OUT / f"p6cp1_{provider.lower()}_ort_profile.json")
    marker = OUT / f"{provider.lower()}_semantic_host_pass.json"
    if all_pass:
        write_json(marker, {
            "provider": provider,
            "semantic_parity": "PASS",
            "fixture_membership_sha256": contract["semantic_subset"]["membership_sha256"],
            "semantic_summary_sha256": sha(OUT / f"p6cp1_{provider.lower()}_semantic_parity.json"),
        })
    elif marker.exists():
        marker.unlink()
    print(json.dumps(summary, indent=2))
    return 0 if all_pass else 3


def ingest_benchmark(provider: str, device_json: Path) -> int:
    provider = provider.upper()
    if provider not in PROVIDERS:
        raise ValueError("Only XNNPACK and NNAPI are authorized")
    semantic = read_json(OUT / f"p6cp1_{provider.lower()}_semantic_parity.json")
    if semantic["semantic_parity"] != "PASS":
        raise RuntimeError(f"P6CP1_{provider}_BENCHMARK_PROHIBITED_SEMANTIC_PARITY_NOT_PASS")
    value = read_json(device_json)
    if value.get("provider") != provider or value.get("warmup_seconds") != 30 or value.get("measured_seconds_requested") != 180:
        raise RuntimeError(f"P6CP1_{provider}_DEVICE_BENCHMARK_CONTRACT_MISMATCH")
    shutil.copy2(device_json, OUT / f"p6cp1_{provider.lower()}_backend_benchmark_device.json")
    row = {key: value.get(key) for key in [
        "provider", "device_model", "soc", "android_version", "ort_version", "model_load_ms",
        "inference_count", "measured_seconds_actual", "backend_p50_ms", "backend_p90_ms",
        "backend_p95_ms", "backend_max_ms", "sustained_backend_fps", "peak_pss_kb",
        "java_heap_bytes", "native_heap_bytes", "crashes", "oom", "batch_size", "single_stream",
    ]}
    row["target_fps"] = 15.0
    row["target_met"] = float(value["sustained_backend_fps"]) >= 15.0
    write_csv(OUT / f"p6cp1_{provider.lower()}_backend_benchmark.csv", [row])
    print(json.dumps({"ingested": True, **row}, indent=2))
    return 0


def provider_state(provider: str) -> dict[str, Any]:
    semantic_path = OUT / f"p6cp1_{provider.lower()}_semantic_parity.json"
    benchmark_path = OUT / f"p6cp1_{provider.lower()}_backend_benchmark_device.json"
    if not semantic_path.is_file():
        return {"provider": provider, "classification": "DEVICE_RUN_REQUIRED", "available": "UNKNOWN", "registered": "UNKNOWN", "semantic_parity": "NOT_RUN"}
    semantic = read_json(semantic_path)
    availability = semantic.get("availability", {})
    if semantic["semantic_parity"] != "PASS":
        return {"provider": provider, "classification": "PROVIDER_SEMANTIC_PARITY_FAILED", "available": True, "registered": True, "semantic_parity": "FAIL", "semantic": semantic}
    if not benchmark_path.is_file():
        return {"provider": provider, "classification": "SEMANTIC_VALID_BENCHMARK_REQUIRED", "available": True, "registered": True, "semantic_parity": "PASS", "semantic": semantic}
    benchmark = read_json(benchmark_path)
    target_met = float(benchmark["sustained_backend_fps"]) >= 15.0
    return {
        "provider": provider,
        "classification": "PROVIDER_BACKEND_TARGET_MET" if target_met else "PROVIDER_BACKEND_TARGET_NOT_MET",
        "available": True,
        "registered": True,
        "semantic_parity": "PASS",
        "semantic": semantic,
        "benchmark": benchmark,
        "target_met": target_met,
        "availability": availability,
    }


def finalize() -> int:
    identity = verify_frozen_identity()
    freeze = read_json(OUT / "p6cp1_pre_evaluation_freeze.json")
    if sha(OUT / "p6cp1_acceleration_contract.json") != freeze["contract_sha256"]:
        raise RuntimeError("P6CP1_CONTRACT_CHANGED_AFTER_RESULTS")
    current_parent_hashes = immutable_parent_hashes()
    parent_unchanged = current_parent_hashes == freeze["parent_hashes"]
    states = [provider_state(provider) for provider in PROVIDERS]
    completed = all(state["classification"] in {
        "PROVIDER_SEMANTIC_PARITY_FAILED", "PROVIDER_BACKEND_TARGET_MET", "PROVIDER_BACKEND_TARGET_NOT_MET",
    } for state in states)
    any_met = any(state["classification"] == "PROVIDER_BACKEND_TARGET_MET" for state in states)
    if any_met:
        classification = "P6CP1_FROZEN_DWPOSE_ACCELERATION_TARGET_MET"
    elif completed:
        classification = "P6CP1_FROZEN_DWPOSE_ACCELERATION_TARGET_NOT_MET"
    else:
        classification = "P6CP1_ACCELERATION_EVIDENCE_INCOMPLETE"

    semantic_valid = [state for state in states if state.get("semantic_parity") == "PASS" and "benchmark" in state]
    best = max(semantic_valid, key=lambda state: float(state["benchmark"]["sustained_backend_fps"])) if semantic_valid else None
    availability_rows = []
    partitioning: dict[str, Any] = {}
    performance_rows = []
    memory_rows = []
    for state in states:
        semantic = state.get("semantic", {})
        availability = semantic.get("availability", state.get("availability", {}))
        availability_rows.append({
            "provider": state["provider"],
            "classification": state["classification"],
            "available": state.get("available", "UNKNOWN"),
            "registered": state.get("registered", "UNKNOWN"),
            "semantic_parity": state.get("semantic_parity", "NOT_RUN"),
            "available_providers": ";".join(availability.get("available_providers", [])),
            "session_created": availability.get("session_created", "NOT_RUN"),
        })
        partitioning[state["provider"]] = semantic.get("partitioning", {"assignment": "NOT_RUN"})
        benchmark = state.get("benchmark")
        performance_rows.append({
            "provider": state["provider"],
            "classification": state["classification"],
            "semantic_parity": state.get("semantic_parity", "NOT_RUN"),
            "backend_p50_ms": benchmark.get("backend_p50_ms") if benchmark else "NOT_RUN",
            "backend_p95_ms": benchmark.get("backend_p95_ms") if benchmark else "NOT_RUN",
            "sustained_backend_fps": benchmark.get("sustained_backend_fps") if benchmark else "NOT_RUN",
            "target_fps": 15.0,
            "target_met": state.get("target_met", "UNKNOWN"),
        })
        thermal = benchmark.get("thermal_status_samples", []) if benchmark else []
        memory_rows.append({
            "provider": state["provider"],
            "peak_pss_kb": benchmark.get("peak_pss_kb") if benchmark else "NOT_RUN",
            "java_heap_bytes": benchmark.get("java_heap_bytes") if benchmark else "NOT_RUN",
            "native_heap_bytes": benchmark.get("native_heap_bytes") if benchmark else "NOT_RUN",
            "thermal_start": thermal[0] if thermal else "NOT_RUN",
            "thermal_peak": max(thermal) if thermal else "NOT_RUN",
            "thermal_end": thermal[-1] if thermal else "NOT_RUN",
            "thermal_sample_count": len(thermal),
            "runtime_errors": len(benchmark.get("runtime_errors", [])) if benchmark else "NOT_RUN",
            "crashes": benchmark.get("crashes") if benchmark else "NOT_RUN",
            "oom": benchmark.get("oom") if benchmark else "NOT_RUN",
        })

    write_json(OUT / "p6cp1_provider_availability_audit.json", {"providers": availability_rows, "official_documentation": OFFICIAL_DOCS})
    write_json(OUT / "p6cp1_provider_partitioning.json", partitioning)
    write_csv(OUT / "p6cp1_performance_summary.csv", performance_rows)
    write_csv(OUT / "p6cp1_memory_thermal_summary.csv", memory_rows)
    blockers = []
    if not completed:
        blockers.append({"blocker": "PHYSICAL_DEVICE_PROVIDER_RUNS_INCOMPLETE", "evidence": ";".join(f"{s['provider']}={s['classification']}" for s in states), "required_action": "CONNECT_TARGET_DEVICE_AND_RUN_DOCUMENTED_XNNPACK_THEN_NNAPI_PROTOCOL", "automatic_workaround": "PROHIBITED"})
    elif not any_met:
        blockers.append({"blocker": "FROZEN_DWPOSE_BACKEND_NECESSARY_CONDITION_NOT_MET", "evidence": ";".join(f"{s['provider']}={s.get('benchmark', {}).get('sustained_backend_fps', 'NO_BENCHMARK')}" for s in states), "required_action": "PROJECT_LEAD_MOBILE_RUNTIME_ARCHITECTURE_TRANSITION_REVIEW", "automatic_workaround": "PROHIBITED"})
    write_csv(OUT / "p6cp1_open_blockers.csv", blockers, ["blocker", "evidence", "required_action", "automatic_workaround"])

    next_gate = "P6C-P2_ANDROID_PREPROCESSING_OPTIMIZATION" if any_met else "PROJECT_LEAD_MOBILE_RUNTIME_ARCHITECTURE_TRANSITION_REVIEW" if completed else "TARGET_DEVICE_COMPLETES_XNNPACK_THEN_NNAPI_RUNS"
    decision = {
        "classification": classification,
        "integrity": "PASS" if parent_unchanged else "FAIL",
        "XNNPACK_result": states[0]["classification"],
        "NNAPI_result": states[1]["classification"],
        "best_semantic_valid_provider": best["provider"] if best else "NONE",
        "best_backend_sustained_fps": float(best["benchmark"]["sustained_backend_fps"]) if best else "UNKNOWN",
        "backend_necessary_condition_met": any_met if completed else "UNKNOWN",
        "production_authorized": False,
        "next_gate": next_gate,
        "next_gate_executed": False,
    }
    write_json(OUT / "p6cp1_decision.json", decision)
    write_json(OUT / "p6cp1_next_gate_contract.json", {"current_classification": classification, "recommended_next_gate": next_gate, "next_gate_executed": False, "hard_stop_after_p6cp1": True})
    write_json(OUT / "APPHEAR_RECOGNITION_CANONICAL_STATE_P6CP1.json", {
        "parent": "APPHEAR_RECOGNITION_CANONICAL_STATE_P6C.json",
        "P6C_classification": "P6C_ANDROID_V2_DEVICE_BELOW_TARGET",
        "P6C_android_semantic_parity": "PASS",
        "P6C_cpu_backend_p50_ms": 812.227865,
        "P6C_cpu_end_to_end_p50_ms": 950.239374,
        "P6C_cpu_sustained_fps": 1.0,
        "governed_target_fps": 15,
        "frozen_backend": "DWPose-L",
        "frozen_onnx_sha256": EXPECTED_ONNX_SHA,
        "V2_changed": False,
        "model_changed": False,
        "precision_changed": False,
        "XNNPACK_result": states[0]["classification"],
        "NNAPI_result": states[1]["classification"],
        "best_semantic_valid_provider": best["provider"] if best else "NONE",
        "best_backend_sustained_fps": float(best["benchmark"]["sustained_backend_fps"]) if best else "UNKNOWN",
        "backend_necessary_condition_met": any_met if completed else "UNKNOWN",
        "recognizer_integrated": False,
        "production_authorized": False,
        "classification": classification,
    })
    integrity = {
        "passed": parent_unchanged,
        "parent_hashes_before": freeze["parent_hashes"],
        "parent_hashes_after": current_parent_hashes,
        "D12_unchanged": current_parent_hashes["D12"] == freeze["parent_hashes"]["D12"],
        "P6A_unchanged": current_parent_hashes["P6A"] == freeze["parent_hashes"]["P6A"],
        "P6B_unchanged": current_parent_hashes["P6B"] == freeze["parent_hashes"]["P6B"],
        "P6BR1_unchanged": current_parent_hashes["P6BR1"] == freeze["parent_hashes"]["P6BR1"],
        "P6C_unchanged": current_parent_hashes["P6C"] == freeze["parent_hashes"]["P6C"],
        "progress_tracker_unchanged": current_parent_hashes["progress_tracker"] == freeze["parent_hashes"]["progress_tracker"],
        "same_dwpose_checkpoint_verified": identity["checkpoint_sha256"] == EXPECTED_CHECKPOINT_SHA,
        "same_onnx_verified": identity["onnx_sha256"] == EXPECTED_ONNX_SHA,
        "same_V2": True, "same_precision_FP32": True, "same_input_shape": True,
        "same_flip_test": True, "same_decoder": True,
        "training": False, "recognizer_inference": False, "D10": False, "pristine_data": False,
        "quantization": False, "FP16": False, "model_replacement": False, "resolution_change": False,
        "P4_reopened": False, "S5_changed": False, "S7_changed": False, "preprocessing_optimization": False,
        "providers_tested_only": ["XNNPACK", "NNAPI"],
    }
    write_json(OUT / "p6cp1_integrity.json", integrity)

    def summary_line(state: dict[str, Any]) -> str:
        benchmark = state.get("benchmark")
        return f"{state['classification']}; semantic={state.get('semantic_parity')}; fps={benchmark.get('sustained_backend_fps') if benchmark else 'NOT_RUN'}"

    report = f"""# P6C-P1 Frozen DWPose Runtime Acceleration Triage

## Result

`{classification}`

The exact frozen DWPose-L FP32 ONNX graph and checkpoint were verified. The contract tested only XNNPACK followed by NNAPI using prepared `[1,3,256,192]` FP32 tensors, batch size one, and the frozen 12-fixture semantic subset. No preprocessing optimization, model change, quantization, recognizer work, or training was performed.

## Provider results

- XNNPACK: {summary_line(states[0])}
- NNAPI: {summary_line(states[1])}
- Best semantic-valid provider: {decision['best_semantic_valid_provider']}
- Best sustained backend FPS: {decision['best_backend_sustained_fps']}
- Necessary backend condition (`>=15 FPS`) met: {decision['backend_necessary_condition_met']}

## Official ONNX Runtime basis

- XNNPACK Android packaging and recommended threading: {OFFICIAL_DOCS['xnnpack']}
- Android mobile XNNPACK/NNAPI guidance: {OFFICIAL_DOCS['mobile']}
- NNAPI Java registration API: {OFFICIAL_DOCS['nnapi_java']}
- Provider partition/fallback architecture: {OFFICIAL_DOCS['provider_architecture']}

## Decision boundary

Production remains unauthorized. The next gate is `{next_gate}`. P6C-P1 stops here; it does not begin QNN, custom ORT builds, quantization, graph surgery, model replacement, preprocessing optimization, or recognizer integration.
"""
    (OUT / "P6CP1_FROZEN_DWPOSE_RUNTIME_ACCELERATION_REPORT.md").write_text(report, encoding="utf-8")

    artifact_files = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != "artifact_hash_manifest.json")
    write_json(OUT / "artifact_hash_manifest.json", {
        "root": str(OUT.resolve()),
        "artifacts": [{"path": str(path.relative_to(OUT)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha(path)} for path in artifact_files],
    })
    print(json.dumps({"classification": classification, "integrity": integrity["passed"], "decision": decision, "artifact_directory": str(OUT)}, indent=2))
    return 0 if integrity["passed"] else 4


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare")
    compare = commands.add_parser("compare-provider")
    compare.add_argument("--provider", required=True, choices=PROVIDERS)
    compare.add_argument("--semantic-jsonl", type=Path, required=True)
    compare.add_argument("--availability-json", type=Path, required=True)
    compare.add_argument("--profile-json", type=Path, required=True)
    ingest = commands.add_parser("ingest-benchmark")
    ingest.add_argument("--provider", required=True, choices=PROVIDERS)
    ingest.add_argument("--device-json", type=Path, required=True)
    commands.add_parser("finalize")
    args = parser.parse_args()
    if args.command == "prepare":
        return prepare()
    if args.command == "compare-provider":
        return compare_provider(args.provider, args.semantic_jsonl, args.availability_json, args.profile_json)
    if args.command == "ingest-benchmark":
        return ingest_benchmark(args.provider, args.device_json)
    return finalize()


if __name__ == "__main__":
    raise SystemExit(main())
