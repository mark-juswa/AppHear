from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
P5 = ROOT / "artifacts/recognition_upgrade/p5_representation_v2"
D12 = P5 / "p5d12_future_version_evidence_synthesis_01"
OUT = ROOT / "artifacts/recognition_upgrade/p6a_production_runtime_compatibility_audit_01"
PROGRESS = ROOT / "context/progress-tracker.md"


SOURCES = {
    "d12_state": D12 / "APPHEAR_RECOGNITION_CANONICAL_STATE_D11.json",
    "d12_handoff": D12 / "APPHEAR_RECOGNITION_HANDOFF_D1_TO_D11.md",
    "d12_synthesis": D12 / "P5D12_FUTURE_VERSION_EVIDENCE_SYNTHESIS.md",
    "d12_candidate": D12 / "p5d12_candidate_freeze.json",
    "d12_loops": D12 / "p5_future_loop_prevention_register.csv",
    "d12_holdout": D12 / "p5_holdout_governance_final.json",
    "d12_claims": D12 / "p5d12_claim_matrix.csv",
    "d12_corrections": D12 / "p5d12_corrections_and_discrepancies.md",
    "d12_gap": D12 / "p5d12_research_to_product_gap.md",
    "d12_questions": D12 / "p5d12_open_questions.csv",
    "feature_schema": ROOT / "context/feature-schema.md",
    "activity": ROOT / "android/app/src/main/java/com/example/apphear/RecognitionActivity.kt",
    "frame_analyzer": ROOT / "android/app/src/main/java/com/example/apphear/pipeline/FrameAnalyzer.kt",
    "landmarker_bundle": ROOT / "android/app/src/main/java/com/example/apphear/pipeline/LandmarkerBundle.kt",
    "landmarker_config": ROOT / "android/app/src/main/java/com/example/apphear/pipeline/LandmarkerConfig.kt",
    "landmark_adapter": ROOT / "android/app/src/main/java/com/example/apphear/pipeline/recognition/LandmarkAdapter.kt",
    "s4": ROOT / "android/app/src/main/java/com/example/apphear/pipeline/features/S4Features.kt",
    "session_normalizer": ROOT / "android/app/src/main/java/com/example/apphear/pipeline/recognition/SessionNormalizer.kt",
    "s5": ROOT / "android/app/src/main/java/com/example/apphear/pipeline/recognition/SigningDetector.kt",
    "pipeline": ROOT / "android/app/src/main/java/com/example/apphear/pipeline/recognition/RecognitionPipeline.kt",
    "recognizer": ROOT / "android/app/src/main/java/com/example/apphear/pipeline/recognition/Recognizer.kt",
    "s7": ROOT / "android/app/src/main/java/com/example/apphear/pipeline/recognition/Confirmation.kt",
    "rearm": ROOT / "android/app/src/main/java/com/example/apphear/pipeline/recognition/PostCommitRearm.kt",
    "model_contract": ROOT / "android/app/src/main/java/com/example/apphear/pipeline/recognition/ModelContract.kt",
    "ui_snapshot": ROOT / "android/app/src/main/java/com/example/apphear/ui/recognition/RecognitionUiSnapshot.kt",
    "model_manifest": ROOT / "android/app/src/main/assets/model_manifest.json",
    "recognition_config": ROOT / "android/app/src/main/assets/recognition_config.json",
    "v2_code": ROOT / "pipeline/features/dwpose_representation_v2.py",
    "v2_contract": ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p5a_dwpose_representation_v2_01/p5a_representation_contract.json",
    "tcn": ROOT / "model/model.py",
    "d2_model": ROOT / "model/p5d2_temporal_objective_ablation.py",
    "f22": ROOT / "context/recognition_upgrade/F22_DEVICE_SMOKE_RESULT.md",
    "a1_runtime": ROOT / "artifacts/recognition_upgrade/a1_independent_clock/device_benchmark_02/a1_device_benchmark_summary.json",
    "dwpose_workload": P5 / "p5d7a_semlex_extraction_prep_01/p5d7a_workload_estimate.json",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def ref(key: str, symbol: str = "") -> str:
    suffix = f"::{symbol}" if symbol else ""
    return f"{rel(SOURCES[key])}{suffix} (SHA-256 {sha(SOURCES[key])})"


def write_json(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_csv(name: str, columns: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with (OUT / name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    missing = [rel(path) for path in SOURCES.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"P6A_BLOCKED_MISSING_SOURCE: {missing}")
    progress_before = sha(PROGRESS)
    d12_before = {rel(path): sha(path) for key, path in SOURCES.items() if key.startswith("d12_")}
    OUT.mkdir(parents=True, exist_ok=True)

    pipeline_rows = [
        {"stage": "S0_CAMERA", "source_file": rel(SOURCES["activity"]), "class_function": "RecognitionActivity.rebindCamera", "input_type": "CameraX camera source", "output_type": "ImageProxy RGBA_8888", "shape": "configured 480x360 target; device may choose closest", "coordinate_convention": "CameraX source with rotationDegrees metadata; analysis not display-mirrored", "normalization": "none", "timing_thread": "ImageAnalysis on single cameraExecutor; KEEP_ONLY_LATEST", "stateful_behavior": "front/back selection; lifecycle rebind", "known_configuration": "RGBA_8888, 480x360, KEEP_ONLY_LATEST"},
        {"stage": "S0_ROTATION_CONVERSION", "source_file": rel(SOURCES["frame_analyzer"]), "class_function": "FrameAnalyzer.analyze/rotate", "input_type": "ImageProxy", "output_type": "upright Bitmap/MPImage", "shape": "upright camera frame", "coordinate_convention": "rotate by imageInfo.rotationDegrees; no analysis mirror", "normalization": "none", "timing_thread": "conversion in analyzer; rotation/processing on Dispatchers.Default", "stateful_behavior": "busy flag drops concurrent frames", "known_configuration": "baseline analyzer unless debug A1 requested"},
        {"stage": "S1_HANDS", "source_file": rel(SOURCES["landmarker_bundle"]), "class_function": "LandmarkerBundle.detectHands/buildHand", "input_type": "MPImage", "output_type": "HandLandmarkerResult", "shape": "up to 2 x 21 landmarks", "coordinate_convention": "MediaPipe normalized image XYZ plus handedness categories", "normalization": "MediaPipe task output", "timing_thread": "parallel async task; IMAGE mode", "stateful_behavior": "none inside IMAGE-mode model", "known_configuration": "GPU requested with CPU fallback; detection/presence/tracking 0.5"},
        {"stage": "S2_POSE", "source_file": rel(SOURCES["landmarker_bundle"]), "class_function": "LandmarkerBundle.detectPose/buildPose", "input_type": "MPImage", "output_type": "PoseLandmarkerResult", "shape": "1 x 33 landmarks", "coordinate_convention": "MediaPipe normalized image XYZ + visibility", "normalization": "MediaPipe task output", "timing_thread": "parallel async task; IMAGE mode", "stateful_behavior": "FrameAnalyzer may reuse last pose", "known_configuration": "pose cadence enabled every 2 frames; hold_last_pose=true; 0.5 thresholds"},
        {"stage": "LANDMARK_ADAPTER", "source_file": rel(SOURCES["landmark_adapter"]), "class_function": "LandmarkAdapter.pose/hands", "input_type": "MediaPipe results", "output_type": "pose FloatArray(132), hands FloatArray(126)", "shape": "33x(x,y,z,visibility); 2x21x(x,y,z)", "coordinate_convention": "hand slot from MediaPipe Left/Right label; fallback i%2", "normalization": "none", "timing_thread": "recognition consumer", "stateful_behavior": "none", "known_configuration": "absent values NaN"},
        {"stage": "S4_FEATURES", "source_file": rel(SOURCES["session_normalizer"]), "class_function": "SessionNormalizer.update/feature + buildFeatureVector", "input_type": "pose[132], hands[126]", "output_type": "FloatArray(258)", "shape": "hands 126 followed by pose 132", "coordinate_convention": "MediaPipe topology; optional whole-body/slot mirror", "normalization": "session-window center/scale/roll/handedness; NaN to zero", "timing_thread": "stateful recognition consumer", "stateful_behavior": "up to 256 pose frames; cumulative wrist motion; default right-handed", "known_configuration": "N1 scale, N2 roll, N3 handedness enabled; manual RIGHT default"},
        {"stage": "S5_SIGNING_GATE", "source_file": rel(SOURCES["s5"]), "class_function": "SigningDetector.update", "input_type": "raw MediaPipe-adapted pose/hands", "output_type": "NONE/ONSET/RELEASE", "shape": "event plus diagnostics", "coordinate_convention": "MediaPipe pose indices and hand slots", "normalization": "motion divided by shoulder width", "timing_thread": "stateful recognition consumer", "stateful_behavior": "motion ring, on/off streaks, hand-presence and raised gate", "known_configuration": "theta_on .12; theta_off .072; k 3/4; low-FPS k 2/6 and smoothing 3"},
        {"stage": "TEMPORAL_BUFFER", "source_file": rel(SOURCES["pipeline"]), "class_function": "RecognitionPipeline.processFrame/clearObservation", "input_type": "per-frame FloatArray(258)", "output_type": "zero-post-padded Array(96,258)", "shape": "[96,258]", "coordinate_convention": "preserves accepted processed-frame order", "normalization": "already S4 normalized", "timing_thread": "stateful recognition consumer", "stateful_behavior": "3 pre-onset frames; append through first 96; zero reset at release/session", "known_configuration": "no sliding after 96; inference each accepted signing frame"},
        {"stage": "S6_TFLITE", "source_file": rel(SOURCES["recognizer"]), "class_function": "Recognizer.load/infer", "input_type": "float32 [1,96,258]", "output_type": "float32 [1,96,236] per-frame softmax", "shape": "reads output at current real-frame index", "coordinate_convention": "schema 3.0", "normalization": "none in S6", "timing_thread": "single inference consumer; model loaded off main; two TFLite threads", "stateful_behavior": "full window rerun; interpreter itself treated stateless", "known_configuration": "INT8 internals with float32 I/O; CPU/XNNPACK"},
        {"stage": "S7_CONFIRMATION", "source_file": rel(SOURCES["s7"]), "class_function": "Confirmation.update", "input_type": "current per-frame softmax[236]", "output_type": "Commit or no commit; top-3", "shape": "class posterior stream", "coordinate_convention": "vocab class order", "normalization": "temperature applied in log-probability space", "timing_thread": "stateful recognition consumer", "stateful_behavior": "cumulative mean log posterior, margin, top1 streak, one commit/bout", "known_configuration": "temperature .6262; theta -1.2; margin .3; k 3; stricter low-FPS margin .9/min frame 4"},
        {"stage": "POST_COMMIT_REARM", "source_file": rel(SOURCES["rearm"]), "class_function": "PostCommitRearm/RecognitionPipeline.processPostCommitFrame", "input_type": "per-frame top1 plus fresh S7", "output_type": "armed verification state", "shape": "scalar class IDs", "coordinate_convention": "vocab class IDs", "normalization": "none", "timing_thread": "stateful recognition consumer", "stateful_behavior": "default disabled; baseline waits for S5 release", "known_configuration": "enabled=false, departure_frames=0"},
        {"stage": "UI_COMMIT", "source_file": rel(SOURCES["activity"]), "class_function": "RecognitionActivity.onFrame/renderRecognitionSnapshot", "input_type": "RecognitionState + SentenceBuilder text", "output_type": "gloss/candidates/sentence UI", "shape": "text", "coordinate_convention": "n/a", "normalization": "n/a", "timing_thread": "Android UI thread", "stateful_behavior": "sentence persists until clear/session behavior", "known_configuration": "RecognitionUiSnapshot maps Idle/Signing/Committed"},
    ]
    write_csv("p6a_current_android_pipeline.csv", list(pipeline_rows[0]), pipeline_rows)

    current_contract = {
        "status": "VERIFIED_FROM_CURRENT_CODE_AND_ASSETS",
        "schema_version": "3.0",
        "model_input_shape": [1, 96, 258],
        "frame_feature_width": 258,
        "classes": 236,
        "feature_layout": [
            {"offset": [0, 125], "block": "HANDS", "layout": "2 slots x 21 x (x,y,z)", "source": "MediaPipe HandLandmarker"},
            {"offset": [126, 257], "block": "POSE", "layout": "33 x (x,y,z,visibility)", "source": "MediaPipe PoseLandmarker"},
        ],
        "hand_slots": "MediaPipe handedness category Left=0 Right=1; unknown falls back to result index modulo 2; optional S4 mirroring swaps slots",
        "missing_input": "LandmarkAdapter uses NaN; S4 converts NaN to zero; no explicit per-point valid or whole-hand observed channels",
        "normalization": {
            "scope": "stateful session window up to 256 pose frames",
            "center": "per-frame MediaPipe shoulder nan-mean; missing center replaced by session-window median then zero",
            "scale": "session-window median shoulder width; fallback median torso length; final fallback 1.0",
            "roll": "session-window median shoulder angle; XY roll correction",
            "handedness": "manual RIGHT default; LEFT mirrors X and swaps anatomical sides/hand slots; AUTO exists but is not default",
            "z": "center affects XY only; scale affects XYZ",
        },
        "temporal": {"frame_order": "processed CameraX order", "pre_onset_frames": 3, "window": 96, "padding": "zero-tail", "pose_cadence": "configured every 2 with last-pose reuse", "after_96": "no further rows appended until release/reset"},
        "inference": "full [1,96,258] rerun each signing frame; current-index per-frame posterior",
        "confirmation": "temperature-scaled cumulative mean log posterior, margin and streak gates; not masked arithmetic mean probability clip aggregation",
        "sources": [ref("model_manifest"), ref("landmark_adapter"), ref("session_normalizer"), ref("pipeline"), ref("recognizer"), ref("s7")],
    }
    write_json("p6a_current_runtime_contract.json", current_contract)

    v2_contract = {
        "status": "EXACT_SEMANTIC_CONTRACT_RECOVERED",
        "schema_id": "DWPOSE_REPRESENTATION_V2_238",
        "scope": "OFFLINE_EXPERIMENTAL_ONLY",
        "dtype": "float32 little-endian",
        "input_shape": [96, 238],
        "native_source": {"backend": "DWPose-L whole-body 256x192", "keypoints": 133, "coordinates": "native XY and score", "body_indices": [0, 16], "left_hand_indices": [91, 111], "right_hand_indices": [112, 132]},
        "feature_layout": [
            {"offset": [0, 83], "block": "LEFT_HAND", "layout": "21 x (x_norm,y_norm,score,valid)"},
            {"offset": [84, 167], "block": "RIGHT_HAND", "layout": "21 x (x_norm,y_norm,score,valid)"},
            {"offset": [168, 235], "block": "BODY", "layout": "17 x (x_norm,y_norm,score,valid)"},
            {"offset": [236, 236], "block": "LH_OBSERVED", "layout": "binary backend-observation mask"},
            {"offset": [237, 237], "block": "RH_OBSERVED", "layout": "binary backend-observation mask"},
        ],
        "valid": "finite x, y and score representable as float32; no score threshold for point validity",
        "observed": "frozen DWPose gated_presence: at least 11 of 21 native hand scores >=0.30, and normalization succeeds; backend observation, not physical-hand truth",
        "normalization": {
            "formula": "(source_xy - center_xy) / scale",
            "center_hierarchy": ["same-frame DWPose shoulder midpoint indices 5/6", "same-frame hip midpoint 11/12", "same-frame mean of structurally valid 17 body points"],
            "scale_hierarchy": ["shoulder distance 5/6", "shoulder-to-hip midpoint distance", "valid-body XY envelope diagonal"],
            "minimum_scale": 1e-6,
            "same_transform_all_blocks": True,
            "roll_rotation": False,
            "mirroring": False,
            "temporal_information": False,
            "per_hand_normalization": False,
        },
        "missingness": {"invalid_point": [0, 0, 0, 0], "unobserved_hand_block": "all zero", "normalization_failure": "blocks/observed flags zero according to builder", "carry_forward": False, "interpolation": False, "extrapolation": False, "opposite_hand_copy": False, "fake_z": False},
        "temporal": {"order": "preserved source frame order", "real_frames": "first min(N,96)", "resampling": False, "padding": "post-pad all-zero to 96", "frame_mask": "compact true prefix then false tail"},
        "sources": [ref("v2_code"), ref("v2_contract")],
    }
    write_json("p6a_v2_semantic_contract.json", v2_contract)

    compatibility = [
        ("LEFT_HAND_XY", "MediaPipe hand slot 0 XY after session normalization/mirroring", "DWPose indices 91..111 XY under same-frame V2 normalization", "NO", "PARTIAL", "NO", "NO", "NO", "NO", "NO", "Different backend topology/output and transform."),
        ("LEFT_HAND_SCORE", "No hand score in 258 S4", "DWPose native per-joint score", "NO", "UNKNOWN", "NO", "NO", "UNKNOWN", "NO", "NO", "Required source signal is absent."),
        ("LEFT_HAND_VALID", "Implicit NaN before NaN-to-zero; no channel", "Finite x/y/score structural-valid bit per joint", "NO", "PARTIAL", "NO", "NO", "UNKNOWN", "NO", "NO", "Cannot distinguish a true numeric zero from missing after S4."),
        ("RIGHT_HAND_XY", "MediaPipe hand slot 1 XY after session normalization/mirroring", "DWPose indices 112..132 XY under same-frame V2 normalization", "NO", "PARTIAL", "NO", "NO", "NO", "NO", "NO", "Different backend topology/output and transform."),
        ("RIGHT_HAND_SCORE", "No hand score in 258 S4", "DWPose native per-joint score", "NO", "UNKNOWN", "NO", "NO", "UNKNOWN", "NO", "NO", "Required source signal is absent."),
        ("RIGHT_HAND_VALID", "Implicit NaN before NaN-to-zero; no channel", "Finite x/y/score structural-valid bit per joint", "NO", "PARTIAL", "NO", "NO", "UNKNOWN", "NO", "NO", "Cannot reproduce score-dependent structural semantics."),
        ("BODY_0_16_XY", "MediaPipe 33-point pose; S4 keeps all 33", "DWPose first 17 whole-body keypoints", "NO", "PARTIAL", "NO", "NO", "NO", "NO", "NO", "Index numbers do not establish anatomical/output equivalence across backends."),
        ("BODY_SCORE", "MediaPipe visibility in each 4-tuple", "DWPose native joint score", "YES", "PARTIAL", "NO", "NO", "UNKNOWN", "NO", "NO", "Same scalar width but different backend semantics."),
        ("BODY_VALID", "Implicit finite/NaN then zero; no explicit channel", "Finite x/y/score structural-valid bit", "NO", "PARTIAL", "NO", "NO", "UNKNOWN", "NO", "NO", "Explicit validity unavailable after legacy packing."),
        ("LH_OBSERVED", "Hand slot present if MediaPipe wrist x is non-NaN; not in S4", "11/21 DWPose scores >=0.30 plus normalization success", "NO", "NO", "NO", "NO", "NO", "NO", "NO", "Backend-specific observation rule cannot be reconstructed."),
        ("RH_OBSERVED", "Hand slot present if MediaPipe wrist x is non-NaN; not in S4", "11/21 DWPose scores >=0.30 plus normalization success", "NO", "NO", "NO", "NO", "NO", "NO", "NO", "Backend-specific observation rule cannot be reconstructed."),
        ("CENTER", "MediaPipe shoulder nan-mean per frame with session-median/zero fill", "DWPose shoulder pair, hip pair, valid-body mean hierarchy per frame", "YES", "PARTIAL", "UNKNOWN", "NO", "NO", "NO", "NO", "Fallbacks and topology differ."),
        ("SCALE", "Session-median shoulder width; torso; 1.0", "Same-frame shoulder; shoulder-hip; envelope; epsilon 1e-6", "YES", "PARTIAL", "UNKNOWN", "NO", "NO", "NO", "NO", "Temporal scope and fallback hierarchy differ."),
        ("TEMPORAL_FRAME_ORDER", "Processed CameraX order with S5/pre-onset", "Preserved source order", "YES", "PARTIAL", "UNKNOWN", "PARTIAL", "PARTIAL", "PARTIAL", "PARTIAL", "Ordering principle matches, but cadence/gating/pre-onset semantics differ."),
        ("PADDING", "Array[96] cleared to zero; append accepted frames", "compact real-prefix mask and zero-tail", "YES", "YES", "UNKNOWN", "PARTIAL", "YES", "UNKNOWN", "PARTIAL", "Zero tail matches; current runtime has no explicit frame mask input."),
        ("MASKING", "No explicit V2 valid/observed/frame-mask channels; padding inferred by index", "per-point valid, hand observed and external compact frame mask", "NO", "NO", "NO", "NO", "UNKNOWN", "NO", "NO", "Required masks are absent or semantically different."),
        ("HANDEDNESS_SLOT_ASSIGNMENT", "MediaPipe category plus result-index fallback; optional whole-input mirroring", "Fixed DWPose anatomical slots; no mirroring", "YES", "PARTIAL", "UNKNOWN", "NO", "NO", "NO", "NO", "Slot and mirroring semantics differ."),
    ]
    comp_rows = []
    for component, legacy, required, shape, coord, score, missing_compat, hand, norm, exact, blocker in compatibility:
        comp_rows.append({"component": component, "legacy_source": "MediaPipe schema-3.0 runtime", "legacy_semantics": legacy, "v2_required_source": "Frozen DWPose-L native output", "v2_required_semantics": required, "shape_compatible": shape, "coordinate_compatible": coord, "confidence_compatible": score, "missingness_compatible": missing_compat, "handedness_compatible": hand, "normalization_compatible": norm, "exactly_reproducible_from_current_android": exact, "evidence": f"{ref('landmark_adapter')}; {ref('v2_contract')}", "blocker": blocker, "confidence": "HIGH" if exact == "NO" else "MODERATE"})
    write_csv("p6a_legacy_to_v2_semantic_compatibility.csv", list(comp_rows[0]), comp_rows)

    backend = {
        "supported_statement": "CURRENT_MEDIAPIPE_CANNOT_REPRODUCE_REQUIRED_V2_SEMANTICS",
        "current_mediapipe_exact_v2": False,
        "geometry_compatibility": "PARTIAL",
        "score_semantics_compatibility": "NO",
        "validity_semantics_compatibility": "NO",
        "observed_semantics_compatibility": "NO",
        "handedness_semantics_compatibility": "NO",
        "normalization_compatibility": "NO",
        "temporal_padding_compatibility": "PARTIAL",
        "exact_blockers": [
            "V2 consumes DWPose-specific keypoints and native scores; MediaPipe outputs are not proven semantically equivalent.",
            "Legacy S4 omits hand scores, explicit per-point validity, and V2 hand-observed channels.",
            "V2 observed is a DWPose 11-of-21 score gate; MediaPipe slot presence is different.",
            "V2 uses same-frame center/scale without roll/mirroring; Android uses session-window scale/roll/handedness.",
            "Current configured pose cadence carries the last pose, while V2 forbids carry-forward.",
            "Android S7 does not implement the governed masked arithmetic-mean probability clip decision.",
        ],
        "dwpose_android": {"runtime": "UNKNOWN", "mobile_deployment": "UNKNOWN", "device_latency": "UNKNOWN", "memory": "UNKNOWN", "thermal": "UNKNOWN"},
        "p4_reopened": False,
        "v2_changed": False,
        "sources": [ref("landmark_adapter"), ref("session_normalizer"), ref("recognition_config"), ref("v2_code"), ref("v2_contract")],
    }
    write_json("p6a_backend_compatibility_decision.json", backend)

    s5_md = f"""# P6-A S5 Dependency Audit

## Current dependency

- **VERIFIED:** S5 consumes raw MediaPipe-adapted pose `[33×(x,y,z,visibility)]` and hand slots `[2×21×(x,y,z)]`, before S4. It uses pose wrist/elbow motion, hand-wrist motion, shoulder-width scale, hip/wrist raised geometry, and MediaPipe hand-slot presence. Source: {ref('s5')}.
- **VERIFIED:** S5 does not consume the 258-vector or V2 `[238]` tensor, so it is architecturally upstream of the recognizer feature contract.
- **BLOCKER:** It is not backend-independent in implementation: topology indices, NaN presence and hand slots are MediaPipe-specific.

## Migration consequence

- **SUPPORTED:** S5 may remain logically upstream if MediaPipe continues solely as its governed input or if a new adapter proves identical S5 signals.
- **NOT ESTABLISHED:** A DWPose-backed S5 would preserve current onset/release behavior.
- **RISK:** Keeping both MediaPipe for S5 and another backend for V2 may increase latency/memory; no measurement exists.
- **FROZEN:** No S5 code or thresholds are changed in P6-A.
"""
    (OUT / "p6a_s5_dependency_audit.md").write_text(s5_md, encoding="utf-8")

    s7_md = f"""# P6-A S7 Confidence Dependency Audit

## Current logic

- **MODEL_SPECIFIC / PROBABILITY_BASED:** temperature `0.6262`, evidence threshold `-1.2`, margin `0.3` (low-FPS `0.9`).
- **TEMPORAL:** top-1 stability `k=3`, low-FPS minimum commit frame `4`, cumulative evidence from all post-onset inference ticks.
- **GEOMETRIC:** none inside S7.
- **VERIFIED:** S7 converts each per-frame softmax to temperature-scaled normalized log probabilities, averages log evidence cumulatively, then applies evidence, margin, streak and optional low-FPS timing gates. Source: {ref('s7')} and {ref('recognition_config')}.
- **VERIFIED:** post-commit rearm is disabled; baseline blocks another commit until S5 release. Source: {ref('rearm')} and {ref('recognition_config')}.

## Candidate mismatch and caveat

- **BLOCKER:** P5 governed clip evaluation uses masked arithmetic mean of per-frame probabilities; Android S7 uses cumulative mean calibrated log posterior. These are not the same aggregation rule.
- **CAVEAT:** D11 EC_P3 clip NLL worsened in 3/3 seeds and per-frame accuracy declined in 2/3. Existing schema-3.0 temperature and thresholds cannot be assumed calibrated for EC_P3.
- **REQUIRED NEXT EVIDENCE:** after input/backend and TFLite parity, evaluate S7 probability/calibration compatibility on an authorized non-test calibration population with a frozen contract.
- **FROZEN:** no threshold or temperature change is authorized in P6-A.
"""
    (OUT / "p6a_s7_confidence_dependency_audit.md").write_text(s7_md, encoding="utf-8")

    tflite_risks = [
        {"risk": "Input width/schema mismatch", "severity": "CRITICAL", "evidence": "Current ModelContract hardcodes schema 3.0 and FEATURE_DIM=258; EC_P3 requires 238.", "unknown": "None", "required_next_test": "A separately isolated prototype contract after backend feasibility.", "prohibited_shortcut": "Do not resize/truncate/reshape 258 to 238."},
        {"risk": "Causal Conv1D conversion parity", "severity": "HIGH", "evidence": "Standard Keras Conv1D padding=causal, dilations 1/2/4/8; no custom layer.", "unknown": "Exact converter lowering and numeric parity for frozen candidate.", "required_next_test": "Frozen checkpoint Keras-vs-TFLite golden parity without test data and without seed selection.", "prohibited_shortcut": "Do not assume historical TFLite proves EC_P3 parity."},
        {"risk": "LayerNormalization conversion", "severity": "HIGH", "evidence": "Two LayerNormalization layers per TCN block.", "unknown": "Builtin-op coverage/performance for chosen converter/runtime version.", "required_next_test": "Static conversion smoke only after checkpoint-selection governance.", "prohibited_shortcut": "Do not enable Select TF Ops silently."},
        {"risk": "Output/aggregation mismatch", "severity": "CRITICAL", "evidence": "Model output is [1,96,236] per-frame softmax; governed clip aggregation is outside model; Android reads current index and S7 aggregates log evidence.", "unknown": "Intended product decision semantics for pause-separated recognition.", "required_next_test": "Freeze Android-side aggregation/confirmation parity contract.", "prohibited_shortcut": "Do not call current S7 equivalent to masked probability mean."},
        {"risk": "Padding/mask behavior", "severity": "HIGH", "evidence": "Model has no mask input; offline aggregation uses external compact frame mask.", "unknown": "How Android will carry valid length into final clip aggregation.", "required_next_test": "Golden sequences with varied valid lengths and exact zero tails.", "prohibited_shortcut": "Do not infer validity from nonzero feature content."},
        {"risk": "Quantization and confidence drift", "severity": "HIGH", "evidence": "Current asset uses INT8 internals/float32 I/O and already shows nonzero parity deltas; D11 NLL worsened.", "unknown": "EC_P3 quantized probability/calibration behavior.", "required_next_test": "Float then quantized parity/calibration audit on authorized validation fixtures.", "prohibited_shortcut": "Do not reuse schema-3.0 temperature or thresholds."},
        {"risk": "Deployment seed not governed", "severity": "CRITICAL", "evidence": "D12 freezes three-seed evidence and no single deployment checkpoint.", "unknown": "Governed validation-only seed or aggregate rule.", "required_next_test": "Project-lead-approved rule before conversion of a deployment candidate.", "prohibited_shortcut": "Do not pick the best seed post hoc."},
    ]
    write_csv("p6a_tflite_migration_risk_matrix.csv", list(tflite_risks[0]), tflite_risks)

    runtime_rows = [
        {"environment": "ANDROID_DEVICE", "measurement": "F22 processed cadence", "value": "approximately 6.2-8.2 fps", "device": "Xiaomi M2101K7AG, Android 12", "source": ref("f22"), "date_or_run": "2026-08-11", "limitation": "PROFILE_STAGES=true; diagnostic, not clean benchmark"},
        {"environment": "ANDROID_DEVICE", "measurement": "A1 baseline fresh-hand/S4 rate", "value": "5.2997 / 5.3044 Hz", "device": "device_benchmark_02 governed device context", "source": ref("a1_runtime"), "date_or_run": "device_benchmark_02", "limitation": "Existing MediaPipe runtime only"},
        {"environment": "ANDROID_DEVICE", "measurement": "A1 independent-clock fresh-hand/S4 rate", "value": "7.0769 / 7.0631 Hz", "device": "device_benchmark_02 governed device context", "source": ref("a1_runtime"), "date_or_run": "device_benchmark_02", "limitation": "Default-off scheduling experiment; not DWPose"},
        {"environment": "ANDROID_DEVICE", "measurement": "A1 memory", "value": "461531 KiB peak PSS (A1); 453208 KiB baseline", "device": "device_benchmark_02", "source": ref("a1_runtime"), "date_or_run": "device_benchmark_02", "limitation": "Not a V2/DWPose measurement"},
        {"environment": "DESKTOP_OFFLINE", "measurement": "DWPose Sem-Lex smoke", "value": "median 5.9235 seconds/video; 4-7 h projected for 2425 videos", "device": "desktop CPU/offline", "source": ref("dwpose_workload"), "date_or_run": "P5-D7A", "limitation": "LOW confidence; archive traversal plus 3 clips; not comparable to Android"},
        {"environment": "UNKNOWN_DEVICE", "measurement": "DWPose-L Android latency/memory/thermal", "value": "UNKNOWN", "device": "target Android", "source": ref("d12_gap"), "date_or_run": "P6-A", "limitation": "No repository-backed mobile measurement"},
    ]
    write_csv("p6a_existing_runtime_evidence.csv", list(runtime_rows[0]), runtime_rows)

    options = [
        {"option": "OPTION_1_KEEP_MEDIAPIPE_REPRODUCE_V2", "requirements": "Prove MediaPipe outputs can reproduce every DWPose keypoint/score/valid/observed and normalization semantic.", "evidence_supporting_it": "Both expose hand/body XY geometry only at a broad conceptual level.", "known_blockers": "Backend topology/scores differ; observed rule absent; legacy normalization/handedness/cadence differ.", "unknowns": "No equivalence mapping exists.", "research_implications": "Changing semantics would invalidate the frozen V2 training contract.", "android_implications": "Would require new 238 builder and contract, but exactness is currently unsupported.", "would_retraining_be_required": "YES_UNLESS_EXACT_EQUIVALENCE_PROVEN", "would_pristine_revalidation_be_required": "YES", "risk": "CRITICAL", "recommended_next_gate": "NOT_RECOMMENDED_UNDER_CURRENT_EVIDENCE"},
        {"option": "OPTION_2_V2_COMPATIBLE_BACKEND", "requirements": "Run a bounded mobile feasibility prototype for the frozen DWPose-L semantic source or an explicitly schema-equivalent implementation; retain native scores/slots and exact V2 builder.", "evidence_supporting_it": "Frozen offline DWPose/V2 code and successful governed extraction establish a reference oracle.", "known_blockers": "Android model packaging, ops, latency, memory, thermal and S5 coexistence are unknown.", "unknowns": "Whether DWPose-L or any exact-equivalent backend is practical on target hardware.", "research_implications": "No retraining only if semantic/numeric parity is exact; otherwise new research cycle.", "android_implications": "Prototype must be isolated/default-off and cannot replace production assets.", "would_retraining_be_required": "NO_IF_EXACT_V2_PARITY_ELSE_YES", "would_pristine_revalidation_be_required": "YES", "risk": "HIGH", "recommended_next_gate": "P6B_V2_BACKEND_FEASIBILITY_PROTOTYPE"},
        {"option": "OPTION_3_NEW_PRODUCTION_REPRESENTATION", "requirements": "Separately govern a mobile-feasible representation and matched retraining/evaluation cycle.", "evidence_supporting_it": "Fallback if exact V2 cannot be produced on device.", "known_blockers": "Reopens representation research and needs new data/evaluation governance.", "unknowns": "Feature design, performance, accuracy and holdout evidence.", "research_implications": "NEW_RESEARCH_CYCLE_REQUIRED.", "android_implications": "New S4/model contract and parity tests; no silent migration.", "would_retraining_be_required": "YES", "would_pristine_revalidation_be_required": "YES", "risk": "HIGH", "recommended_next_gate": "ONLY_IF_OPTION_2_FEASIBILITY_FAILS"},
    ]
    write_csv("p6a_migration_options.csv", list(options[0]), options)

    blockers = [
        ("B01", "P0", "Current MediaPipe cannot supply DWPose-native scores, exact topology or gated-observed semantics.", "SEMANTIC", "P6B_V2_BACKEND_FEASIBILITY_PROTOTYPE"),
        ("B02", "P0", "Android S4 normalization/handedness and pose carry differ from V2.", "SEMANTIC", "Use frozen V2 builder as oracle; do not adapt legacy S4."),
        ("B03", "P0", "DWPose-L Android packaging, ops, latency, memory and thermal feasibility are unknown.", "RUNTIME", "Bounded target-device feasibility prototype."),
        ("B04", "P0", "Current ModelContract and Recognizer hardcode schema 3.0/258.", "INTEGRATION", "Do not modify until input feasibility passes."),
        ("B05", "P1", "Governed masked arithmetic-mean probability aggregation differs from S7 cumulative mean log evidence.", "DECISION_SEMANTICS", "Freeze a later aggregation/S7 parity contract."),
        ("B06", "P1", "EC_P3 calibration is unknown and D11 clip NLL worsened 3/3.", "CALIBRATION", "Authorized validation-only calibration audit after parity."),
        ("B07", "P1", "No single deployment checkpoint selection rule exists.", "GOVERNANCE", "Project lead freezes a validation-only rule before conversion."),
        ("B08", "P1", "No pristine signer-independent confirmation exists.", "EVIDENCE", "New evaluation-only signer cohort before product claim."),
        ("B09", "P1", "S5 is architecturally upstream but MediaPipe-semantic in code.", "INTEGRATION", "Measure/choose S5 coexistence or adapter only in a later gate."),
    ]
    blocker_rows = [{"blocker_id": b[0], "priority": b[1], "blocker": b[2], "category": b[3], "resolution_gate": b[4], "status": "OPEN"} for b in blockers]
    write_csv("p6a_open_blockers.csv", list(blocker_rows[0]), blocker_rows)

    d12_state_sha = sha(SOURCES["d12_state"])
    write_json("APPHEAR_RECOGNITION_CANONICAL_STATE_P6A.json", {
        "parent_canonical_state": rel(SOURCES["d12_state"]),
        "parent_canonical_state_sha256": d12_state_sha,
        "d1_representation_parity_status": "REPRESENTATION_PARITY_EXPERIMENT_INCONCLUSIVE_LOW",
        "v2_sufficiency_status": "NOT_ESTABLISHED",
        "current_recognition_scope": "ISOLATED_OR_PAUSE_SEPARATED_SIGN_RECOGNITION",
        "continuous_asl_status": "NOT_ESTABLISHED_FUTURE_WORK",
        "d11_metric_caveats": ["CLIP_NLL_WORSE_3_OF_3", "PER_FRAME_ACCURACY_WORSE_2_OF_3", "TOP5_MIXED", "FIVE_SIGNER_VALIDATION_LIMITATION"],
        "research_candidate": "PFCE_MATCHED_EC_P3",
        "candidate_scope": "OFFLINE_ONLY",
        "production_contract_status": "CURRENT_MEDIAPIPE_NOT_EXACTLY_V2_COMPATIBLE",
        "backend_compatibility_statement": "CURRENT_MEDIAPIPE_CANNOT_REPRODUCE_REQUIRED_V2_SEMANTICS",
        "p6a_classification": "P6A_CURRENT_RUNTIME_NOT_EXACTLY_V2_COMPATIBLE",
        "next_gate": "P6B_V2_BACKEND_FEASIBILITY_PROTOTYPE",
        "next_gate_executed": False,
    })

    source_index = [
        ("D12 candidate and boundaries", "d12_state", "canonical state", "FROZEN_SOURCE"),
        ("D1 inconclusive/LOW and V2 sufficiency not established", "d12_corrections", "D1 source conflict", "VERIFIED"),
        ("Production schema is [96,258]", "model_manifest", "schema_version/input_shape", "VERIFIED"),
        ("CameraX ingestion and UI path", "activity", "rebindCamera/onFrame", "VERIFIED"),
        ("Rotation, frame dropping and pose reuse", "frame_analyzer", "analyze/rotate", "VERIFIED"),
        ("MediaPipe IMAGE mode and delegate", "landmarker_bundle", "create/buildHand/buildPose", "VERIFIED"),
        ("MediaPipe thresholds/topology", "landmarker_config", "LandmarkerConfig", "VERIFIED"),
        ("Legacy raw landmark layout/hand slots", "landmark_adapter", "pose/hands", "VERIFIED"),
        ("Legacy 258 feature layout", "s4", "buildFeatureVector", "VERIFIED"),
        ("Legacy session normalization", "session_normalizer", "update/feature", "VERIFIED"),
        ("S5 dependencies", "s5", "SigningDetector.update", "VERIFIED"),
        ("Temporal buffer and orchestration", "pipeline", "RecognitionPipeline.processFrame", "VERIFIED"),
        ("S6 TFLite shape/current-index output", "recognizer", "Recognizer.infer", "VERIFIED"),
        ("S7 calibrated log-evidence confirmation", "s7", "Confirmation.update", "VERIFIED"),
        ("Exact V2 builder", "v2_code", "normalization_from_body/build_frame_features/build_padded_sequence", "VERIFIED"),
        ("Frozen V2 semantic declaration", "v2_contract", "entire contract", "VERIFIED"),
        ("TCN architecture", "tcn", "build_streaming_classifier", "VERIFIED"),
        ("Candidate parameter/output contract and aggregation", "d2_model", "make_model/clip_probabilities", "VERIFIED"),
        ("Existing Android device evidence", "f22", "F22 result", "VERIFIED_WITH_LIMITATIONS"),
        ("Existing A1 runtime evidence", "a1_runtime", "device_benchmark_02", "VERIFIED_WITH_LIMITATIONS"),
        ("Offline DWPose timing", "dwpose_workload", "P5-D7A workload estimate", "DESKTOP_ONLY_LOW_CONFIDENCE"),
    ]
    index_lines = ["# P6-A Source-of-Truth Index", "", "Future runtime proposals must read this index and the parent D12 canonical state first.", "", "| Claim | Source path | Symbol/artifact | SHA-256 | Status |", "|---|---|---|---|---|"]
    for claim, key, symbol, status in source_index:
        index_lines.append(f"| {claim} | `{rel(SOURCES[key])}` | `{symbol}` | `{sha(SOURCES[key])}` | {status} |")
    (OUT / "P6A_SOURCE_OF_TRUTH_INDEX.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    write_json("p6a_next_gate_contract.json", {
        "gate": "P6B_V2_BACKEND_FEASIBILITY_PROTOTYPE",
        "purpose": "Determine whether the frozen DWPose-L/V2 semantic source can execute on target Android hardware or through an exactly equivalent mobile implementation within a bounded, default-off prototype.",
        "must_measure": ["native keypoint/score/slot semantic parity against frozen offline fixtures", "backend model load and op support", "per-frame latency", "full pipeline cadence", "peak memory", "thermal behavior", "interaction cost if MediaPipe remains for S5"],
        "must_not": ["train", "select seed", "run D10 test", "change V2", "tune perception thresholds", "replace production assets", "promote backend", "modify S5/S7 semantics"],
        "success_is_not_production_authorization": True,
        "executed": False,
    })
    write_json("p6a_decision.json", {
        "classification": "P6A_CURRENT_RUNTIME_NOT_EXACTLY_V2_COMPATIBLE",
        "integrity_expected": "PASS",
        "exact_v2_contract_recovered": True,
        "current_android_contract_audited": True,
        "current_mediapipe_exact_v2": False,
        "migration_alternatives_possible": True,
        "preferred_bounded_path": "OPTION_2_V2_COMPATIBLE_BACKEND",
        "recommended_next_gate": "P6B_V2_BACKEND_FEASIBILITY_PROTOTYPE",
        "next_gate_executed": False,
        "training": False,
        "inference": False,
        "android_modified": False,
        "p4_reopened": False,
        "v2_changed": False,
    })

    report = f"""# P6-A Production Runtime Compatibility Audit

## Decision

**P6A_CURRENT_RUNTIME_NOT_EXACTLY_V2_COMPATIBLE**

This is an engineering finding, not an accuracy failure. The frozen V2 contract is recoverable exactly, and the current Android path is auditable, but current MediaPipe/schema-3.0 outputs cannot reproduce DWPose-specific V2 semantics without guessing.

## Research boundary

- Leading offline candidate: `PFCE_MATCHED + EC_P3`, MODERATE confidence.
- D1: `REPRESENTATION_PARITY_EXPERIMENT_INCONCLUSIVE_LOW`; V2 sufficiency is not established.
- Current demonstrated scope: isolated or pause-separated signs, not continuous ASL.
- D11 caveats remain: NLL worse 3/3, per-frame accuracy worse 2/3, Top5 mixed, five validation signer groups and all signer-block intervals crossing zero.

## Current Android path

CameraX RGBA/keep-latest → rotation-only analysis bitmap → MediaPipe Hands/Pose IMAGE mode → MediaPipe adapter → stateful session-normalized `[258]` S4 → MediaPipe-specific S5 → zero-padded `[1,96,258]` TFLite full-window inference → current-frame posterior → temperature-scaled cumulative log-evidence S7 → sentence/UI.

Verified sources: {ref('activity')}; {ref('pipeline')}; {ref('model_manifest')}.

## Frozen V2 path

DWPose-L 133-point XY+score → fixed body/hand slots → same-frame center/scale hierarchy → `[21×4 LH, 21×4 RH, 17×4 body, LH observed, RH observed]` → compact real-frame prefix and zero tail `[96,238]`.

Observed means the frozen DWPose gate (at least 11/21 scores ≥0.30) plus successful normalization; it is not physical-hand truth. Source: {ref('v2_contract')}.

## Exact blockers

1. MediaPipe does not emit the DWPose-native scores/topology on which V2 score, validity and observation fields are defined.
2. Legacy S4 omits explicit validity and observed channels; its normalization, mirroring and handedness semantics differ.
3. Current pose cadence reuses a prior pose; V2 forbids carry-forward.
4. Current Android decision logic reads a current-frame posterior and S7 averages calibrated log evidence; P5 evaluation uses masked arithmetic mean probabilities over real frames.
5. ModelContract/Recognizer hardcode schema 3.0 and 258 features.

## S5/S7

S5 is upstream of S4 but not backend-neutral: it consumes MediaPipe topology, NaN and hand-slot semantics. It could remain a separate MediaPipe gate only after its extra runtime cost and synchronization are measured.

S7 is probability/model-specific. The schema-3.0 temperature and thresholds cannot be reused for EC_P3 without an authorized calibration/parity phase, especially given D11 NLL regression. No threshold was changed.

## TFLite

The 4x64 TCN uses standard Conv1D, LayerNormalization, ReLU, Dropout, Add and Dense/softmax layers with `[1,96,236]` output and no custom layer. Static conversion feasibility is **SUPPORTED WITH PARITY TEST REQUIRED**. Conversion was not executed. Masked clip aggregation is outside the model. No deployment seed is selected.

## Runtime evidence

Existing MediaPipe Android cadence is below the 15-fps floor: F22 observed roughly 6.2–8.2 fps; A1 device benchmark reported about 7.06 S4 Hz. Desktop DWPose smoke timing is not comparable to Android. DWPose Android latency, memory and thermal behavior remain UNKNOWN.

## Migration options

- Option 1 (MediaPipe exactly reproduces V2): unsupported under current evidence.
- Option 2 (frozen V2-compatible backend): the preferred bounded feasibility path because the offline implementation supplies an exact oracle; Android feasibility remains unknown.
- Option 3 (new production representation): fallback only; it requires `NEW_RESEARCH_CYCLE_REQUIRED`, retraining and pristine revalidation.

## Next gate

`P6B_V2_BACKEND_FEASIBILITY_PROTOTYPE` — default-off, bounded, measurement-only. It does not authorize production implementation.

No training, inference, test access, conversion, Android modification, P4 reopening, V2 change, or D12 modification occurred.
"""
    (OUT / "P6A_PRODUCTION_RUNTIME_COMPATIBILITY_AUDIT.md").write_text(report, encoding="utf-8")

    progress_after = sha(PROGRESS)
    d12_after = {rel(path): sha(path) for key, path in SOURCES.items() if key.startswith("d12_")}
    required = [
        "P6A_PRODUCTION_RUNTIME_COMPATIBILITY_AUDIT.md", "APPHEAR_RECOGNITION_CANONICAL_STATE_P6A.json",
        "P6A_SOURCE_OF_TRUTH_INDEX.md", "p6a_current_android_pipeline.csv", "p6a_current_runtime_contract.json",
        "p6a_v2_semantic_contract.json", "p6a_legacy_to_v2_semantic_compatibility.csv",
        "p6a_backend_compatibility_decision.json", "p6a_s5_dependency_audit.md",
        "p6a_s7_confidence_dependency_audit.md", "p6a_tflite_migration_risk_matrix.csv",
        "p6a_existing_runtime_evidence.csv", "p6a_migration_options.csv", "p6a_open_blockers.csv",
        "p6a_next_gate_contract.json", "p6a_decision.json",
    ]
    missing_outputs = [name for name in required if not (OUT / name).is_file()]
    integrity = {
        "passed": not missing and not missing_outputs and progress_before == progress_after and d12_before == d12_after,
        "source_files_verified": len(SOURCES),
        "missing_sources": missing,
        "missing_outputs_before_integrity": missing_outputs,
        "source_hashes": {rel(path): sha(path) for path in SOURCES.values()},
        "d12_hashes_before": d12_before,
        "d12_hashes_after": d12_after,
        "d12_artifacts_unchanged": d12_before == d12_after,
        "progress_tracker_sha256_before": progress_before,
        "progress_tracker_sha256_after": progress_after,
        "progress_tracker_untouched": progress_before == progress_after,
        "training_performed": False,
        "model_inference_performed": False,
        "d10_test_accessed": False,
        "checkpoint_loaded": False,
        "tflite_conversion_executed": False,
        "new_benchmark_executed": False,
        "android_modified": False,
        "p4_reopened": False,
        "v2_modified": False,
        "deployment_seed_selected": False,
    }
    write_json("p6a_integrity.json", integrity)
    generated = sorted(path for path in OUT.iterdir() if path.is_file() and path.name != "artifact_hash_manifest.json")
    write_json("artifact_hash_manifest.json", {
        "schema": "P6A_ARTIFACT_HASH_MANIFEST_V1",
        "files": [{"path": rel(path), "sha256": sha(path), "bytes": path.stat().st_size} for path in generated],
        "governed_source_hashes": {rel(path): sha(path) for path in SOURCES.values()},
    })
    print(json.dumps({"passed": integrity["passed"], "classification": "P6A_CURRENT_RUNTIME_NOT_EXACTLY_V2_COMPATIBLE", "outputs": len(generated) + 1, "progress_tracker_untouched": integrity["progress_tracker_untouched"], "d12_unchanged": integrity["d12_artifacts_unchanged"]}, indent=2))
    return 0 if integrity["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
