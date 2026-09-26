"""Finalize the governed P6-B report after the frozen Gate-A comparison."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/recognition_upgrade/p6b_v2_backend_feasibility_prototype_01"
P6A = ROOT / "artifacts/recognition_upgrade/p6a_production_runtime_compatibility_audit_01"
D12 = ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5d12_future_version_evidence_synthesis_01"
PROGRESS = ROOT / "context/progress-tracker.md"
CHECKPOINT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/checkpoint/dw-ll_ucoco.pth"
CONFIG = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/toolchain/source_snapshot/mmpose/configs/wholebody_2d_keypoint/rtmpose/ubody/rtmpose-l_8xb64-270e_coco-ubody-wholebody-256x192.py"
EXPECTED_CHECKPOINT_SHA = "e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7"
EXPECTED_CONFIG_SHA = "b2e741d2428667c99e74218f5170a183337602755c76e5b4138546a9b59d5032"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def write_json(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_csv(name: str, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with (OUT / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def verify_manifest(directory: Path) -> dict[str, Any]:
    manifest_path = directory / "artifact_hash_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mismatches = []
    for item in manifest.get("files", manifest.get("artifacts", [])):
        item_path = item.get("path") or item.get("artifact")
        expected = item.get("sha256")
        if not item_path or not expected:
            continue
        candidate = ROOT / item_path
        if not candidate.is_file():
            candidate = directory / Path(item_path).name
        if not candidate.is_file() or sha(candidate) != expected:
            mismatches.append(item_path)
    return {"manifest": rel(manifest_path), "manifest_sha256": sha(manifest_path), "mismatches": mismatches}


def main() -> int:
    gate = json.loads((OUT / "p6b_gate_a_result.json").read_text(encoding="utf-8"))
    identity = json.loads((OUT / "p6b_frozen_backend_identity.json").read_text(encoding="utf-8"))
    export = json.loads((OUT / "p6b_runtime_export_manifest.json").read_text(encoding="utf-8"))
    parity_hash = sha(OUT / "p6b_parity_contract.json")
    fixture_hash = sha(OUT / "p6b_golden_fixture_manifest.csv")
    p6a_verification = verify_manifest(P6A)
    d12_verification = verify_manifest(D12)
    progress_hash = sha(PROGRESS)
    checkpoint_hash = sha(CHECKPOINT)
    config_hash = sha(CONFIG)
    if checkpoint_hash != EXPECTED_CHECKPOINT_SHA or config_hash != EXPECTED_CONFIG_SHA:
        raise RuntimeError("P6B_FROZEN_MODEL_IDENTITY_MISMATCH")
    if gate["gate_a_pass"]:
        raise RuntimeError("This finalizer is only for the observed preregistered Gate-A failure")

    canonical = {
        "parent_canonical_state": rel(P6A / "APPHEAR_RECOGNITION_CANONICAL_STATE_P6A.json"),
        "parent_canonical_state_sha256": sha(P6A / "APPHEAR_RECOGNITION_CANONICAL_STATE_P6A.json"),
        "frozen_backend": "DWPose-L",
        "backend_checkpoint_sha256": checkpoint_hash,
        "mobile_runtime": "ONNX_RUNTIME_MOBILE_ANDROID_FP32",
        "oracle_status": "EXACT_PREPROCESSING_POSTPROCESSING_AND_V2_ORACLE_RECOVERED",
        "parity_contract_sha256": parity_hash,
        "golden_fixture_membership_sha256": fixture_hash,
        "semantic_parity_status": "FAILED_DECODED_XY_MAX_TOLERANCE",
        "device_execution_status": "NOT_RUN_GATE_A_FAILED",
        "performance_target_source": "context/runtime-constraints.md; sustained end-to-end pipeline >=15 FPS",
        "device_model": "NOT_RUN",
        "android_version": "NOT_RUN",
        "backend_latency_p50": "NOT_RUN",
        "backend_latency_p95": "NOT_RUN",
        "sustained_fps": "NOT_RUN",
        "peak_memory": "NOT_RUN",
        "thermal_status": "NOT_RUN",
        "dual_backend_cost_status": "NOT_MEASURED_GATE_A_FAILED",
        "research_candidate_unchanged": True,
        "production_promoted": False,
        "classification": "P6B_SEMANTIC_PARITY_FAILED",
        "next_gate": "PROJECT_LEAD_SEMANTIC_PARITY_REVIEW",
        "next_gate_executed": False,
    }
    write_json("APPHEAR_RECOGNITION_CANONICAL_STATE_P6B.json", canonical)

    prototype = {
        "status": "NOT_CREATED_GATE_A_FAILED",
        "debug_only": True,
        "default_off": True,
        "production_recognition_connected": False,
        "android_files_added": [],
        "android_files_modified": [],
        "production_assets_replaced": False,
        "reason": "P6-B prohibits Android prototype creation and Gate-B execution after semantic parity failure.",
    }
    write_json("p6b_android_prototype_manifest.json", prototype)
    protocol = {
        "status": "PREPARED_NOT_EXECUTED_GATE_A_FAILED",
        "physical_device_required": True,
        "emulator_is_product_evidence": False,
        "warmup_seconds": 30,
        "measured_seconds": 180,
        "governed_cadence_requirement_fps": 15,
        "requirement_source": "context/runtime-constraints.md",
        "measurements": ["model_load_ms", "backend_latency_p50_p90_p95_max", "v2_build_latency", "end_to_end_latency", "sustained_fps", "peak_process_memory", "java_heap", "native_heap", "thermal_status", "dropped_frames", "operator_fallback", "runtime_provider"],
        "configurations": ["DWPose_V2_ONLY", "MEDIAPIPE_S5_PLUS_DWPOSE_V2_IF_SAFE"],
        "execution_authorized": False,
        "reason": "Gate A failed; Gate B must not run.",
    }
    write_json("p6b_device_benchmark_protocol.json", protocol)

    blockers = [
        {
            "blocker_id": "P6B-B01",
            "stage": "GATE_A_DECODED_XY",
            "severity": "BLOCKING",
            "evidence": "negative_gold_131, point index 42 (FACE), y coordinate: ONNX 177.333313 px vs frozen oracle 184.0 px",
            "observed": "6.666687 px max absolute error",
            "frozen_requirement": "<=0.5 source-image px maximum absolute error",
            "downstream_v2_effect": "Final V2 still passed because face point 42 is outside the V2-selected body/hand indices.",
            "allowed_action": "PROJECT_LEAD_SEMANTIC_PARITY_REVIEW",
            "prohibited_action": "Do not widen tolerance, modify V2, change graph, or try another backend.",
        },
        {
            "blocker_id": "P6B-B02",
            "stage": "GATE_B",
            "severity": "BLOCKING_BY_SEQUENCE",
            "evidence": "Gate A failed before Android prototype authorization.",
            "observed": "No device execution or performance measurements",
            "frozen_requirement": "Gate B only after Gate A passes",
            "downstream_v2_effect": "Target-device feasibility remains UNKNOWN.",
            "allowed_action": "None within P6-B",
            "prohibited_action": "Do not build/run the Android benchmark.",
        },
    ]
    write_csv("p6b_open_blockers.csv", list(blockers[0]), blockers)
    write_json("p6b_next_gate_contract.json", {
        "gate": "PROJECT_LEAD_SEMANTIC_PARITY_REVIEW",
        "trigger": "P6B_SEMANTIC_PARITY_FAILED",
        "scope": "Review the single preregistered decoded-XY failure without widening tolerances or testing alternatives.",
        "may_not": ["try another backend", "change DWPose-L", "change V2", "widen tolerance after results", "run Gate B", "train", "access D10"],
        "executed": False,
    })
    decision = {
        "classification": "P6B_SEMANTIC_PARITY_FAILED",
        "gate_a": "FAIL",
        "gate_b": "NOT_RUN",
        "exact_v2_semantics_mobile_capable": "NO_UNDER_FROZEN_FULL_133_POINT_PARITY_CONTRACT",
        "exact_v2_target_device_feasible": "UNKNOWN",
        "production_authorized": False,
        "alternative_backends_tested": False,
        "parity_contract_changed_after_results": False,
        "recommended_next_gate": "PROJECT_LEAD_SEMANTIC_PARITY_REVIEW",
        "next_gate_executed": False,
    }
    write_json("p6b_decision.json", decision)

    source_rows = [
        {"claim": "Frozen DWPose-L identity", "source_path": rel(CHECKPOINT), "source_symbol_or_artifact": "dw-ll_ucoco.pth", "sha256": checkpoint_hash, "status": "VERIFIED"},
        {"claim": "Frozen DWPose-L config", "source_path": rel(CONFIG), "source_symbol_or_artifact": CONFIG.name, "sha256": config_hash, "status": "VERIFIED"},
        {"claim": "Parent P6-A state", "source_path": rel(P6A / "APPHEAR_RECOGNITION_CANONICAL_STATE_P6A.json"), "source_symbol_or_artifact": "canonical P6-A state", "sha256": sha(P6A / "APPHEAR_RECOGNITION_CANONICAL_STATE_P6A.json"), "status": "IMMUTABLE_VERIFIED"},
        {"claim": "Golden fixture membership", "source_path": rel(OUT / "p6b_golden_fixture_manifest.csv"), "source_symbol_or_artifact": "48 P2A development fixtures", "sha256": fixture_hash, "status": "FROZEN_BEFORE_COMPARISON"},
        {"claim": "Parity thresholds", "source_path": rel(OUT / "p6b_parity_contract.json"), "source_symbol_or_artifact": "P6B_FP32_PARITY_CONTRACT_V1", "sha256": parity_hash, "status": "UNCHANGED_AFTER_RESULTS"},
        {"claim": "FP32 ONNX graph", "source_path": rel(OUT / "frozen_dwpose_l_fp32.onnx"), "source_symbol_or_artifact": "flip-test averaged SimCC graph", "sha256": sha(OUT / "frozen_dwpose_l_fp32.onnx"), "status": "LOADS_IN_ORT_CPU"},
        {"claim": "Gate-A comparison", "source_path": rel(OUT / "p6b_gate_a_result.json"), "source_symbol_or_artifact": "48-fixture full comparison", "sha256": sha(OUT / "p6b_gate_a_result.json"), "status": "FAIL_DECODED_XY_MAX"},
        {"claim": "15 FPS product floor", "source_path": "context/runtime-constraints.md", "source_symbol_or_artifact": "minimum viable pipeline FPS", "sha256": sha(ROOT / "context/runtime-constraints.md"), "status": "VERIFIED_NOT_MEASURED"},
    ]
    lines = ["# P6-B Source of Truth Index", "", "| Claim | Source | Symbol/artifact | SHA-256 | Status |", "|---|---|---|---|---|"]
    lines += [f"| {r['claim']} | `{r['source_path']}` | {r['source_symbol_or_artifact']} | `{r['sha256']}` | {r['status']} |" for r in source_rows]
    (OUT / "P6B_SOURCE_OF_TRUTH_INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = f"""# P6-B Frozen V2 Backend Feasibility Report

## Decision

`P6B_SEMANTIC_PARITY_FAILED`

The one authorized mobile runtime path was ONNX Runtime Mobile in FP32. The exact frozen checkpoint/config were verified, the complete whole-frame affine/RGB/normalization/flip-test/SimCC/source-restoration oracle was recovered, and a fixed 48-frame P2A development fixture was frozen before comparison.

## Gate A result

- Raw topology: PASS
- Hand slots: PASS
- Scores: PASS (maximum absolute error `{gate['summary']['score_max_abs_error']:.9g}`)
- Valid masks: PASS
- Observed flags: PASS
- Normalization: PASS
- Final V2: PASS (maximum absolute error `{gate['summary']['v2_max_abs_error']:.9g}`)
- Decoded 133-point XY: **FAIL**

The sole blocking excursion was `negative_gold_131`, point index 42 (FACE), y coordinate: ONNX `177.333313` px versus oracle `184.0` px, an absolute difference of `6.666687` px. The preregistered maximum was `0.5` source-image pixels. Point 42 is outside the V2-selected body and hand indices, which explains why final `[238]` V2 parity passed; nevertheless the frozen contract requires numeric parity for the complete 133-point output, so Gate A fails. The parity contract hash remained `{parity_hash}` before and after results.

## Gate B

Not run. No Android prototype was created because P6-B permits it only after Gate A passes. Device latency, sustained FPS, memory, thermal behavior, and the MediaPipe-for-S5 dual-backend cost remain UNKNOWN.

## Governance

No training, recognizer inference, D10/pristine data access, quantization, pruning, distillation, alternative backend, Android modification, S5/S7 change, V2 change, P4 reopening, production asset replacement, or deployment-seed selection occurred.

## Next gate

`PROJECT_LEAD_SEMANTIC_PARITY_REVIEW`, not executed. The review must not widen tolerances, modify the frozen model/V2 contract, or authorize an alternative backend automatically.
"""
    (OUT / "P6B_V2_BACKEND_FEASIBILITY_REPORT.md").write_text(report, encoding="utf-8")

    required = [
        "P6B_V2_BACKEND_FEASIBILITY_REPORT.md", "APPHEAR_RECOGNITION_CANONICAL_STATE_P6B.json",
        "P6B_SOURCE_OF_TRUTH_INDEX.md", "p6b_frozen_backend_identity.json", "p6b_offline_oracle_contract.json",
        "p6b_golden_fixture_manifest.csv", "p6b_parity_contract.json", "p6b_offline_oracle_outputs.npz",
        "p6b_runtime_export_manifest.json", "p6b_operator_support.csv", "p6b_raw_output_parity.csv",
        "p6b_v2_feature_parity.csv", "p6b_observed_validity_parity.csv", "p6b_android_prototype_manifest.json",
        "p6b_device_benchmark_protocol.json", "p6b_open_blockers.csv", "p6b_next_gate_contract.json", "p6b_decision.json",
    ]
    missing = [name for name in required if not (OUT / name).is_file()]
    integrity = {
        "passed": not missing and checkpoint_hash == EXPECTED_CHECKPOINT_SHA and config_hash == EXPECTED_CONFIG_SHA and not p6a_verification["mismatches"] and not d12_verification["mismatches"] and sha(PROGRESS) == progress_hash,
        "frozen_dwpose_hash_verified": True,
        "frozen_config_hash_verified": True,
        "p6a_hashes_unchanged": not p6a_verification["mismatches"],
        "p6a_verification": p6a_verification,
        "d12_hashes_unchanged": not d12_verification["mismatches"],
        "d12_verification": d12_verification,
        "progress_tracker_sha256_before_finalize": progress_hash,
        "progress_tracker_sha256_after_finalize": sha(PROGRESS),
        "progress_tracker_unchanged": sha(PROGRESS) == progress_hash,
        "missing_required_outputs": missing,
        "training": False,
        "recognizer_inference": False,
        "d10_accessed": False,
        "pristine_data_accessed": False,
        "v2_modified": False,
        "p4_reopened": False,
        "s5_modified": False,
        "s7_modified": False,
        "android_modified": False,
        "production_assets_replaced": False,
        "deployment_seed_selected": False,
        "alternative_backend_tested": False,
        "quantization": False,
        "pruning": False,
        "distillation": False,
        "gate_b_executed": False,
    }
    write_json("p6b_integrity.json", integrity)
    files = sorted(path for path in OUT.iterdir() if path.is_file() and path.name != "artifact_hash_manifest.json")
    write_json("artifact_hash_manifest.json", {
        "schema": "P6B_ARTIFACT_HASH_MANIFEST_V1",
        "files": [{"path": rel(path), "bytes": path.stat().st_size, "sha256": sha(path)} for path in files],
    })
    print(json.dumps({"passed": integrity["passed"], "classification": decision["classification"], "gate_a": "FAIL", "gate_b": "NOT_RUN", "artifacts": len(files) + 1}, indent=2))
    return 0 if integrity["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
