"""Generate the read-only P7-A mobile-native architecture transition audit.

This tool performs no inference, extraction, training, benchmarking, or Android changes.
It summarizes already-governed evidence and hashes its own audit artifacts.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/recognition_upgrade/p7a_mobile_native_architecture_transition_audit_01"
OUT.mkdir(parents=True, exist_ok=True)

PARENTS = {
    "D12": ROOT / "artifacts/recognition_upgrade/p5_representation_v2/p5d12_future_version_evidence_synthesis_01/artifact_hash_manifest.json",
    "P6A": ROOT / "artifacts/recognition_upgrade/p6a_production_runtime_compatibility_audit_01/artifact_hash_manifest.json",
    "P6B": ROOT / "artifacts/recognition_upgrade/p6b_v2_backend_feasibility_prototype_01/artifact_hash_manifest.json",
    "P6BR1": ROOT / "artifacts/recognition_upgrade/p6br1_v2_dependency_parity_confirmation_01/artifact_hash_manifest.json",
    "P6C": ROOT / "artifacts/recognition_upgrade/p6c_android_v2_device_feasibility_01/artifact_hash_manifest.json",
    "P6CP1": ROOT / "artifacts/recognition_upgrade/p6cp1_frozen_dwpose_runtime_acceleration_triage_01/artifact_hash_manifest.json",
    "progress_tracker": ROOT / "context/progress-tracker.md",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_csv(name: str, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(name)
    with (OUT / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


parent_before = {name: sha(path) for name, path in PARENTS.items()}

write_json("p7a_project_transition_decision.json", {
    "parent_classification": "P6CP1_FROZEN_DWPOSE_ACCELERATION_TARGET_NOT_MET",
    "exact_dwpose_l_fp32_flip_test_mobile_path": "CLOSED_ON_GOVERNED_TARGET",
    "closure_basis": {"cpu_live_pipeline_fps": 1.0, "xnnpack_backend_fps": 1.861052062720739,
                      "nnapi": "SEMANTIC_PARITY_FAILED", "governed_minimum_fps": 15},
    "dwpose_future_role": "OFFLINE_REFERENCE_TEACHER",
    "v2_future_role": "OFFLINE_REFERENCE_REPRESENTATION_NOT_AUTOMATIC_PRODUCTION_REQUIREMENT",
    "mobile_architecture_selected": False,
    "classification": "P7A_ARCHITECTURE_DECISION_EVIDENCE_READY",
    "next_gate": "PROJECT_LEAD_P7_MOBILE_ARCHITECTURE_SELECTION",
    "next_gate_executed": False,
})

dependencies = [
    {"stage":"CAMERA","input":"CameraX frame","consumes":"RGBA_8888 frame; rotation metadata","dimensions":"configured 480x360; device-selected actual","semantics":"upright, non-analysis-mirrored pixels","essential":"YES","fallback":"UNKNOWN","origin":"CameraX","claim_strength":"VERIFIED"},
    {"stage":"PERCEPTION_HANDS","input":"upright frame","consumes":"two anatomical hand slots; 21 points/hand; handedness; presence","dimensions":"2x21 geometry plus state","semantics":"stable LH/RH assignment and explicit absence","essential":"YES for current S4/S5; future width not frozen","fallback":"no valid invented/carry-forward hand","origin":"MediaPipe current; DWPose offline","claim_strength":"VERIFIED"},
    {"stage":"PERCEPTION_BODY","input":"upright frame","consumes":"wrists, elbows, shoulders, hips; recognition reference includes body 0..16","dimensions":"current 33x4; V2 reference 17x4","semantics":"upper-body anchors, scale, motion, validity","essential":"YES; exact future topology not frozen","fallback":"S5 shoulder scale fallback is limited; V2 center/scale hierarchy","origin":"MediaPipe current; DWPose offline","claim_strength":"VERIFIED"},
    {"stage":"S4_CURRENT","input":"MediaPipe pose[132]+hands[126]","consumes":"XYZ, pose visibility, session normalization/mirror","dimensions":"258/frame","semantics":"legacy schema 3.0","essential":"only for current deployed recognizer","fallback":"NaN becomes zero after normalization","origin":"derived logic","claim_strength":"VERIFIED"},
    {"stage":"V2_REFERENCE","input":"DWPose 133 XY+score and gated hand presence","consumes":"42 hand + 17 body points, score, valid, observed","dimensions":"238/frame; 96x238 clip","semantics":"same-frame normalized; explicit missingness","essential":"required by frozen offline checkpoint; not automatically future product requirement","fallback":"center shoulder->hip->valid mean; scale shoulder->torso->envelope","origin":"derived DWPose logic","claim_strength":"VERIFIED"},
    {"stage":"S5","input":"raw MediaPipe-adapted pose/hands before S4","consumes":"pose wrists/elbows, hand wrists, shoulders, hips, hand presence, frame history","dimensions":"pose[132]+hands[126]","semantics":"motion/shoulder width, hands-seen, raised geometry, NaN absence","essential":"YES for current onset/release","fallback":"may retain MediaPipe or require proven adapter","origin":"MediaPipe + derived logic","claim_strength":"VERIFIED"},
    {"stage":"TEMPORAL_BUFFER","input":"accepted per-frame feature","consumes":"ordered frames, pre-onset context, release reset","dimensions":"96 frames","semantics":"real order; zero post-padding","essential":"method reusable; exact 96 is not proven future necessity","fallback":"none governed","origin":"derived logic","claim_strength":"VERIFIED"},
    {"stage":"S6_CURRENT","input":"legacy [1,96,258]","consumes":"all 258 fields","dimensions":"[1,96,258] -> [1,96,236]","semantics":"current INT8 TFLite model","essential":"historical production only","fallback":"refuses schema mismatch","origin":"TFLite","claim_strength":"VERIFIED"},
    {"stage":"S6_OFFLINE_CANDIDATE","input":"V2 [1,96,238]","consumes":"all V2 fields","dimensions":"per-frame logits for 236 classes","semantics":"PFCE_MATCHED EC_P3 offline checkpoint","essential":"checkpoint requires exact V2; checkpoint transfer not assumed","fallback":"new representation requires new evidence/training","origin":"Keras TCN","claim_strength":"VERIFIED"},
    {"stage":"S7","input":"236-class posterior stream","consumes":"probabilities, evidence, margin, streak, timing","dimensions":"236/frame","semantics":"temperature-scaled cumulative mean log posterior","essential":"YES for current commit policy","fallback":"none for uncalibrated new model","origin":"derived logic","claim_strength":"VERIFIED"},
    {"stage":"UI","input":"committed class/gloss","consumes":"commit, candidates, sentence state","dimensions":"scalar/list/text","semantics":"isolated or pause-separated recognition","essential":"YES product output","fallback":"idle/signing states","origin":"Android UI","claim_strength":"VERIFIED"},
]
write_csv("p7a_downstream_feature_dependency_map.csv", dependencies)

capabilities = [
    {"capability":"Hand geometry","current_backend":"MediaPipe Hands","configuration":"IMAGE mode; up to 2 hands; detection/presence/tracking 0.5; GPU request with CPU fallback","verified_current_capability":"21 normalized XYZ landmarks per detected hand","known_historical_limitation":"MediaPipe semantics are not exact V2 score/valid/observed semantics","unknown":"future student parity","claim_strength":"VERIFIED"},
    {"capability":"Handedness slots","current_backend":"MediaPipe Hands","configuration":"Left/Right category; index fallback if absent","verified_current_capability":"adapter produces two anatomical slots","known_historical_limitation":"label/mirror semantics backend-specific","unknown":"cross-backend stability without adapter test","claim_strength":"VERIFIED"},
    {"capability":"Body geometry","current_backend":"MediaPipe Pose","configuration":"IMAGE mode; 33 points; 0.5 thresholds","verified_current_capability":"normalized XYZ plus visibility","known_historical_limitation":"topology and confidence differ from DWPose","unknown":"minimal future body set","claim_strength":"VERIFIED"},
    {"capability":"Pose cadence","current_backend":"FrameAnalyzer","configuration":"every 2 frames; hold_last_pose=true","verified_current_capability":"stateful carry-forward is used in current production path","known_historical_limitation":"not V2 same-frame semantics","unknown":"acceptable future cadence under new representation","claim_strength":"VERIFIED"},
    {"capability":"Missing data","current_backend":"LandmarkAdapter","configuration":"absent landmarks are NaN","verified_current_capability":"S5 hand presence checks wrist NaN","known_historical_limitation":"not equivalent to DWPose valid/observed","unknown":"future missingness contract","claim_strength":"VERIFIED"},
    {"capability":"Rotation/mirror","current_backend":"CameraX + S4","configuration":"rotationDegrees applied; analysis not display-mirrored; optional S4 slot/body mirror","verified_current_capability":"upright analysis frame and session handedness logic","known_historical_limitation":"auto mirror previously destabilized recognition; default RIGHT","unknown":"future backend camera convention","claim_strength":"VERIFIED"},
    {"capability":"Existing latency","current_backend":"MediaPipe production path","configuration":"repository historical evidence only","verified_current_capability":"v2 4.37->8.10 FPS after parallel pose+hands/face removal","known_historical_limitation":"still below 15 FPS historical floor","unknown":"current isolated MediaPipe latency on governed Xiaomi under P7","claim_strength":"SUPPORTED"},
]
write_csv("p7a_current_perception_capability_matrix.csv", capabilities)

teachers = [
    {"asset":"P5B governed DWPose native outputs","corpus":"ASL Citizen + governed AppHear/local roles","clips":8131,"frames":"stored per clip; governed onset/release frame indices","outputs":"133 XY, scores, frame indices/timestamps, source/sample/signer/class lineage","location":"artifacts/recognition_upgrade/p5_representation_v2/p5b_migration_01/native","reproducible":"YES from frozen checkpoint/config and governed raw hashes","training_role":"role-dependent; protected roles excluded","claim_strength":"VERIFIED"},
    {"asset":"P5B governed V2 outputs","corpus":"ASL Citizen + governed AppHear/local roles","clips":8131,"frames":"up to 96 real frames plus zero tail","outputs":"V2[238], mask, normalization-derived semantics","location":"artifacts/recognition_upgrade/p5_representation_v2/p5b_migration_01/features","reproducible":"YES from native outputs and frozen builder","training_role":"role-dependent","claim_strength":"VERIFIED"},
    {"asset":"Sem-Lex completed native outputs","corpus":"human-approved Sem-Lex candidate","clips":2417,"frames":"per-clip native frames/indices/timestamps","outputs":"133 XY, scores, signer/lexical/class/source lineage","location":"G:/SEM LEX/AppHear_P5D7_candidate/full_parallel_exact/native","reproducible":"YES for existing outputs; eight raw decode failures remain excluded","training_role":"2415 usable candidate clips after two zero-hand quarantines","claim_strength":"VERIFIED"},
    {"asset":"Sem-Lex completed V2 outputs","corpus":"human-approved Sem-Lex candidate","clips":2417,"frames":"[96,238]","outputs":"V2, masks, observation and lineage","location":"G:/SEM LEX/AppHear_P5D7_candidate/full_parallel_exact/v2","reproducible":"YES from retained native evidence","training_role":"P3 selected 881 samples; full usable pool 2415 remains governed candidate","claim_strength":"VERIFIED"},
    {"asset":"P6B/P6BR1/P6C fixtures and oracle","corpus":"governed development perception fixtures","clips":60,"frames":60,"outputs":"raw 133, scores, valid/observed, center/scale, final V2","location":"artifacts/recognition_upgrade/p6br1_v2_dependency_parity_confirmation_01","reproducible":"YES","training_role":"parity fixtures, not student training population","claim_strength":"VERIFIED"},
]
write_csv("p7a_dwpose_teacher_asset_inventory.csv", teachers)

corpora = [
    {"corpus":"ASL Citizen primary TRAIN","raw_rgb":"YES; 3309 governed rows and all filenames present under relocated G root","labels":"236 class labels","signer_ids":"35","frame_timestamps":"YES in retained native outputs","teacher_outputs":"YES 3309 native+V2","role":"TRAIN","phone_domain":"NO/NOT ESTABLISHED","future_training":"YES under frozen TRAIN membership","notes":"raw root now G:/ASL CITIZEN/ASL CITIZEN/ASL_Citizen; historical manifests remain immutable","claim_strength":"VERIFIED"},
    {"corpus":"ASL Citizen VAL","raw_rgb":"YES; 816 governed rows mapped on G","labels":"236","signer_ids":"5","frame_timestamps":"YES","teacher_outputs":"YES 816","role":"VALIDATION","phone_domain":"NO/NOT ESTABLISHED","future_training":"NO; preserve validation","notes":"may evaluate future hypotheses under a new preregistered cycle","claim_strength":"VERIFIED"},
    {"corpus":"ASL Citizen D10 canonical TEST","raw_rgb":"YES; 2620 governed rows mapped on G","labels":"236","signer_ids":"11","frame_timestamps":"YES","teacher_outputs":"YES 2620","role":"DEVELOPMENT-EXPOSED SECONDARY TEST","phone_domain":"NO/NOT ESTABLISHED","future_training":"PROHIBITED","notes":"D10 protected from P7 development","claim_strength":"VERIFIED"},
    {"corpus":"AppHear/local E6 governed supplement TRAIN","raw_rgb":"YES; 617/617 current paths present","labels":"5 classes","signer_ids":"5 source-aware groups","frame_timestamps":"YES","teacher_outputs":"YES 617","role":"TRAIN supplement","phone_domain":"YES for AppHear capture; LOCAL provenance preserved","future_training":"YES only existing governed TRAIN rows","notes":"297 APPHEAR_CAPTURE + 320 LOCAL","claim_strength":"VERIFIED"},
    {"corpus":"AppHear development diagnostics","raw_rgb":"YES; 463/463 current paths present","labels":"4-5 classes","signer_ids":"development groups","frame_timestamps":"YES","teacher_outputs":"YES 463","role":"DEVELOPMENT DIAGNOSTIC","phone_domain":"YES","future_training":"NO unless a future governance decision changes role","notes":"reused positive + validation stress","claim_strength":"VERIFIED"},
    {"corpus":"Protected clean replay","raw_rgb":"YES; 306/306 current paths present","labels":"3 classes","signer_ids":"3","frame_timestamps":"YES","teacher_outputs":"YES 306","role":"PROTECTED REPLAY","phone_domain":"YES","future_training":"PROHIBITED","notes":"one signer overlaps TRAIN; protection preserved","claim_strength":"VERIFIED"},
    {"corpus":"Sem-Lex usable candidate","raw_rgb":"YES for staged source; 2415 post-audit usable","labels":"65 human-approved AppHear classes","signer_ids":"32","frame_timestamps":"YES","teacher_outputs":"YES","role":"EXTERNAL TRAIN CANDIDATE","phone_domain":"NO/NOT ESTABLISHED","future_training":"YES only under governed lexical/lineage/sampling policy","notes":"P3 policy selected 881 class/signer-bounded samples","claim_strength":"VERIFIED"},
    {"corpus":"Future pristine signers","raw_rgb":"NO CURRENT CORPUS","labels":"UNKNOWN","signer_ids":"UNUSED","frame_timestamps":"UNKNOWN","teacher_outputs":"NO","role":"FUTURE HOLDOUT","phone_domain":"DESIRED/UNKNOWN","future_training":"PROHIBITED","notes":"must remain untouched if collected","claim_strength":"NOT ESTABLISHED"},
]
write_csv("p7a_training_corpus_inventory.csv", corpora)

align = [
    {"corpus":"ASL Citizen governed P5B rows","status":"ALIGNMENT_READY","evidence":"6745/6745 canonical ASL Citizen filenames found under relocated G raw root; raw SHA and source row retained; per-sample native outputs retain governed frame indices/timestamps","limitation":"historical absolute F paths are stale and must be resolved by filename plus governed SHA, not rewritten","claim_strength":"VERIFIED"},
    {"corpus":"AppHear/local E6 governed P5B rows","status":"ALIGNMENT_READY","evidence":"1086 governed raw paths present across train/diagnostic/protected roles; 1086 native+V2 records retained with sample/signer/class lineage","limitation":"role filtering is mandatory","claim_strength":"VERIFIED"},
    {"corpus":"Sem-Lex completed candidate","status":"ALIGNMENT_READY","evidence":"2417 native and V2 outputs plus 2417 completion records; sample/signer/lexical/class and source hashes retained","limitation":"only 2415 post-audit usable; eight decode exclusions and two zero-hand quarantines stay excluded","claim_strength":"VERIFIED"},
    {"corpus":"ASL Citizen full raw archive beyond governed membership","status":"PARTIALLY_READY","evidence":"83399 raw videos available and split metadata exists","limitation":"teacher outputs and AppHear class mapping are not established for every raw video; do not expand membership automatically","claim_strength":"SUPPORTED"},
    {"corpus":"Future pristine signers","status":"NOT_READY","evidence":"no collected/authorized data","limitation":"must be reserved for evaluation, not teacher/student development","claim_strength":"NOT ESTABLISHED"},
]
write_csv("p7a_rgb_teacher_alignment_audit.csv", align)

governance = [
    {"population":"ASL Citizen primary TRAIN","development_use":"ALLOWED","future_student_training":"ALLOWED","validation_use":"NO","protected":"NO","conditions":"preserve 3309 membership, signer IDs, source hashes","claim_strength":"VERIFIED"},
    {"population":"AppHear/local E6 supplement TRAIN","development_use":"ALLOWED","future_student_training":"ALLOWED","validation_use":"NO","protected":"NO","conditions":"preserve 617 governed rows and source namespaces","claim_strength":"VERIFIED"},
    {"population":"Sem-Lex post-audit candidate/P3","development_use":"ALLOWED_WITH_GOVERNANCE","future_student_training":"ALLOWED_WITH_GOVERNANCE","validation_use":"NO","protected":"NO","conditions":"human-approved 65 only; exclusions preserved; sampling preregistered","claim_strength":"VERIFIED"},
    {"population":"ASL Citizen VAL","development_use":"EVALUATION_ONLY","future_student_training":"PROHIBITED","validation_use":"YES","protected":"YES_FROM_TRAINING","conditions":"signer-disjoint membership frozen","claim_strength":"VERIFIED"},
    {"population":"D10 canonical TEST 2620","development_use":"PROHIBITED","future_student_training":"PROHIBITED","validation_use":"PROHIBITED","protected":"YES","conditions":"secondary-confirmation only; no P7 access/inference","claim_strength":"VERIFIED"},
    {"population":"Protected clean replay 306","development_use":"PROHIBITED","future_student_training":"PROHIBITED","validation_use":"PROHIBITED","protected":"YES","conditions":"membership immutable","claim_strength":"VERIFIED"},
    {"population":"AppHear diagnostics/stress","development_use":"DESCRIPTIVE/DIAGNOSTIC_ONLY","future_student_training":"NOT CURRENTLY AUTHORIZED","validation_use":"DIAGNOSTIC_ONLY","protected":"DEVELOPMENT_EXPOSED","conditions":"do not silently relabel as TRAIN","claim_strength":"VERIFIED"},
    {"population":"Future pristine signers","development_use":"PROHIBITED","future_student_training":"PROHIBITED","validation_use":"ONE-TIME GOVERNED EVALUATION ONLY","protected":"YES","conditions":"remain unused until candidate frozen","claim_strength":"NOT ESTABLISHED"},
]
write_csv("p7a_dataset_governance_matrix.csv", governance)

write_json("p7a_mobile_runtime_constraints.json", {
    "claim_strength": "VERIFIED",
    "minimum_viable_sustained_fps": 15,
    "target_device": {"model": "Xiaomi M2101K7AG", "soc": "SM6150", "android": "12"},
    "camera": {"analysis_strategy": "KEEP_ONLY_LATEST", "configured_target": "480x360",
               "dropped_overwritten_count": "NOT_DIRECTLY_OBSERVABLE"},
    "model_loading": "ASYNC_OFF_CRITICAL_PATH_REQUIRED",
    "formal_memory_ceiling": "UNKNOWN",
    "measured_dwpose": {"cpu_live_fps": 1.0, "cpu_backend_p50_ms": 812.227865,
                         "cpu_end_to_end_p50_ms": 950.239374, "cpu_peak_pss_kib": 312541,
                         "xnnpack_backend_fps": 1.861052062720739, "xnnpack_backend_p50_ms": 498.115781,
                         "nnapi_semantic_parity": "FAILED"},
    "thermal": "NONE during completed CPU and XNNPACK protocols",
    "exact_dwpose_mobile_path": "CLOSED_ON_GOVERNED_TARGET",
    "unknowns": ["formal memory ceiling", "future student latency", "future live camera cadence", "future thermal behavior"],
})

write_json("p7a_s5_dependency_audit.json", {
    "classification": "S5_PORTABLE_TO_NEW_PERCEPTION",
    "claim_strength": "SUPPORTED",
    "current_implementation": "MEDIAPIPE_SPECIFIC",
    "inputs": ["pose wrists", "pose elbows", "shoulders", "hips", "hand-slot wrists",
               "hand presence from NaN semantics", "frame history/motion ring"],
    "derived_logic": ["shoulder-width scale", "wrist/elbow displacement", "hand auxiliary motion",
                      "hands-seen gate", "raised-hand geometry", "on/off streaks"],
    "reuse_as_is": "ONLY if MediaPipe remains S5 source",
    "portable_condition": "new perception adapter must reproduce anatomical slots, coordinates, missingness and motion/scale inputs, followed by a governed onset/release parity test",
    "shared_future_source": "PLAUSIBLE_NOT_ESTABLISHED",
    "modified_in_p7a": False,
})

write_json("p7a_recognizer_transfer_boundary.json", {
    "current_candidate": "PFCE_MATCHED_EC_P3",
    "trained_representation": "DWPOSE_REPRESENTATION_V2_238_[96,238]",
    "checkpoint_transfer_to_materially_different_representation": "NOT_ASSUMED",
    "reusable_method": ["4x64 causal TCN architecture hypothesis", "96-frame temporal evaluation machinery",
                        "PFCE_MATCHED objective", "EC_P3 exposure-controlled within-class diversity policy",
                        "236-class vocabulary", "source-aware signer-disjoint splits", "evaluation and lineage tooling"],
    "reusable_checkpoint": "ONLY if exact V2 semantics and tensor contract are reproduced; otherwise NO",
    "requires_new_evidence": ["student representation training", "signer-disjoint validation", "runtime parity",
                              "probability/calibration and S7 compatibility", "pristine confirmation if resourced"],
    "training_in_p7a": False,
})

(OUT / "p7a_student_output_family_analysis.md").write_text("""# P7-A Student Output Family Analysis

No architecture or named perception model is selected here.

## Family A — explicit LH/RH landmarks plus minimal body geometry

**SUPPORTED design family.** Output stable left/right hand points with confidence/validity/presence plus the wrists, elbows, shoulders and torso anchors justified by recognition and S5. It offers the clearest DWPose-teacher supervision and the greatest downstream interpretability. Current S5 could become portable through an adapter, but both S5 parity and a new recognizer training cycle would still be required unless exact V2 is reproduced. Risk: explicit landmark fidelity may remain computationally expensive and teacher score semantics may not transfer cleanly.

## Family B — explicit hands plus compact learned body/context output

**SUPPORTED design family.** Preserve interpretable anatomical hand slots while replacing the full body topology with a compact context signal. It may reduce output burden, but current S5 cannot consume an opaque embedding as-is; either a small explicit S5 body head or retained MediaPipe S5 source is needed. DWPose can supervise the explicit outputs, while learned context needs a separately frozen objective. The current checkpoint is not transferable.

## Family C — direct learned AppHear feature representation

**SUPPORTED but highest-governance-risk design family.** Emit a compact temporal feature intended directly for recognition rather than landmarks. It could be runtime-efficient, but it provides the least transparent missingness/handedness contract, does not directly serve current S5, and cannot reuse the current checkpoint. Teacher feature distillation is possible from V2, but signer-independent evidence and train/serve parity must be rebuilt.

## Product necessities versus DWPose-specific choices

**VERIFIED product dependencies:** stable anatomical LH/RH identity, hand geometry/motion, upper-body anchors sufficient for scale and S5, explicit missingness/presence, temporal order, and source/signer lineage.

**NOT ESTABLISHED as product necessities:** the full 133-point topology, face/foot points, exact DWPose score distribution, flip test, the 11-of-21 at 0.30 observed rule, exact 238-field layout, or the exact 96-frame window. These remain reference-contract choices until a new architecture gate freezes a hypothesis.
""", encoding="utf-8")

(OUT / "p7a_runtime_first_development_plan.md").write_text("""# P7-A Runtime-First Development Plan

1. **Project lead freezes one primary output-family hypothesis and at most one fallback.** Freeze required outputs, dimensions, missingness, handedness, preprocessing, runtime target, and failure rules before implementation.
2. **Build a deployable skeleton before teacher extraction.** A synthetic/random-initialized graph may establish Android operator support, model load, memory, latency distribution, and sustained cadence. It cannot establish semantic quality.
3. **Run the Android runtime gate.** Require physical-device p50/p95 latency, sustained FPS, memory and thermal evidence. Close the hypothesis if its skeleton cannot plausibly meet the 15 FPS pipeline budget.
4. **Run a tiny smoke-trained parity package only after runtime feasibility.** It may test RGB-to-output alignment, loss plumbing, export parity and failure logging. It cannot support recognition claims.
5. **Freeze teacher/student lineage, then perform bounded teacher extraction only where absent.** Reuse the 8,131 P5B and 2,417 Sem-Lex native outputs; never extract protected D10 or pristine data for development.
6. **Train the real candidate in a new governed research cycle.** Preserve source-aware signer splits and compare against frozen baselines without changing the runtime contract after results.
7. **Evaluate signer-disjoint behavior and S5/S7 integration.** A real fully trained model is required for recognition, calibration, confirmation, and class-wise claims.
8. **Integrate behind a default-off feature flag only after offline and device gates pass.**

This sequence prevents expensive training from legitimizing an architecture that cannot run on the target device.
""", encoding="utf-8")

risks = [
    {"rank":1,"risk":"Train/serve semantic skew in handedness, confidence, validity or missingness","impact":"student may look accurate offline but feed different states on-device","evidence":"MediaPipe and DWPose semantics differ; V2 explicit missingness is load-bearing","mitigation_gate":"freeze output contract and byte/semantic parity fixtures before training","claim_strength":"VERIFIED"},
    {"rank":2,"risk":"Runtime hypothesis misses >=15 FPS or memory/thermal feasibility","impact":"short signs remain physically undersampled regardless of recognition quality","evidence":"exact DWPose path achieved only 1.86 backend FPS; formal memory ceiling unknown","mitigation_gate":"deployable skeleton benchmark before teacher extraction/training","claim_strength":"VERIFIED"},
    {"rank":3,"risk":"Teacher/domain/alignment bias","impact":"student may reproduce DWPose errors or fail on production phone imagery","evidence":"teacher coverage is strong but production-domain breadth and frame alignment beyond governed members are incomplete","mitigation_gate":"freeze safe corpus roles, hash-based alignment, source-balanced signer-disjoint evaluation","claim_strength":"SUPPORTED"},
]
write_csv("p7a_architecture_risk_register.csv", risks)

missing = [
    {"priority":"P0","evidence_gap":"One frozen primary output-family hypothesis and optional fallback","why_needed":"prevents model roulette and defines deployable I/O","closure_owner":"PROJECT_LEAD","allowed_next_action":"architecture selection only","claim_strength":"UNKNOWN"},
    {"priority":"P0","evidence_gap":"Physical-device skeleton latency/memory/operator support for selected hypothesis","why_needed":"runtime feasibility must precede heavy training","closure_owner":"P7 runtime gate","allowed_next_action":"default-off benchmark skeleton","claim_strength":"UNKNOWN"},
    {"priority":"P0","evidence_gap":"Exact portable S5 output/adapter acceptance contract","why_needed":"current S5 is MediaPipe-specific despite conceptual portability","closure_owner":"future S5 parity gate","allowed_next_action":"contract design; no threshold tuning","claim_strength":"NOT ESTABLISHED"},
    {"priority":"P1","evidence_gap":"Production-domain RGB breadth by signer/device/environment","why_needed":"teacher/student domain coverage is not quantified for full vocabulary","closure_owner":"future data audit","allowed_next_action":"metadata audit before collection","claim_strength":"UNKNOWN"},
    {"priority":"P1","evidence_gap":"Formal mobile memory ceiling","why_needed":"only measured PSS exists; no governed ceiling","closure_owner":"project/runtime constraints","allowed_next_action":"project-lead constraint decision","claim_strength":"UNKNOWN"},
    {"priority":"P1","evidence_gap":"Representation-change recognition and S7 calibration evidence","why_needed":"current checkpoint and thresholds are not transferable by assumption","closure_owner":"new governed research cycle","allowed_next_action":"only after runtime gate and training authorization","claim_strength":"NOT ESTABLISHED"},
]
write_csv("p7a_missing_evidence_register.csv", missing)

write_json("p7a_loop_prevention_contract.json", {
    "one_primary_architecture_hypothesis_required": True,
    "maximum_predeclared_fallbacks": 1,
    "hypotheses_frozen_before_implementation_results": True,
    "runtime_gate_before_heavy_training": True,
    "closed_direct_path": "DWPose-L FP32 flip-test on governed Xiaomi",
    "prohibited_automatic_sequence": "candidate_A_fail_then_candidate_B_then_resolution_threshold_provider_sweeps",
    "prohibited_without_new_project_lead_authorization": ["DWPose variants", "provider roulette", "resolution sweeps",
        "threshold sweeps", "quantization", "new perception extraction", "D10 use", "pristine signer use"],
    "results_may_not_mutate_frozen_contract": True,
})

(OUT / "p7a_next_gate_decision_questions.md").write_text("""# P7-A Architecture Decision Questions

1. **Q1 — Recognition output:** **SUPPORTED:** stable LH/RH geometry and motion, compact upper-body anchors, confidence/validity/presence, temporal order and missingness are required. The exact 238 layout is required only to reuse the current checkpoint.
2. **Q2 — S5-only information:** **VERIFIED:** raw pose wrists/elbows/shoulders/hips, hand wrists/presence, shoulder scale, NaN-style absence and motion history are consumed before S4.
3. **Q3 — Shared source:** **SUPPORTED:** one system could plausibly serve both if it emits explicit hands plus S5 upper-body/missingness signals. This is not yet device- or behavior-validated.
4. **Q4 — Necessity versus DWPose choice:** **VERIFIED:** anatomical slots, hand/upper-body geometry and explicit missingness are downstream needs. Full 133 topology, face/feet, flip test, exact score distribution, V2 gate/layout and 96 frames are reference choices, not proven product necessities.
5. **Q5 — Existing teacher supervision:** **VERIFIED:** 8,131 P5B native/V2 records and 2,417 Sem-Lex native/V2 records, plus 60 parity fixtures/oracles.
6. **Q6 — Additional extraction:** **SUPPORTED:** none is needed for an initial governed student over existing memberships. Expansion to unused ASL Citizen raw clips or new production data would require a new lineage/teacher-extraction contract.
7. **Q7 — RGB availability:** **VERIFIED:** all 6,745 governed ASL Citizen rows map to the relocated 83,399-video G root; 1,086 AppHear/local governed paths and staged Sem-Lex source are available. Production-domain breadth remains incomplete.
8. **Q8 — Alignment:** **VERIFIED** for governed P5B and Sem-Lex memberships; **PARTIALLY READY** for the wider unused raw archives.
9. **Q9 — Safe training populations:** **VERIFIED:** ASL Citizen primary TRAIN, governed AppHear/local supplement TRAIN, and human-approved post-audit Sem-Lex under a frozen sampling policy.
10. **Q10 — Protected populations:** **VERIFIED:** ASL Citizen VAL is evaluation-only; D10 canonical TEST, protected replay and future pristine signers are development/training-prohibited.
11. **Q11 — Runtime constraints:** **VERIFIED:** at least 15 sustained FPS, off-main-thread loading/inference and physical-device p50/p95 evidence. **UNKNOWN:** a formal memory ceiling.
12. **Q12 — Reusable recognizer method:** **SUPPORTED:** TCN hypothesis, temporal/evaluation machinery, PFCE, EC_P3, vocabulary and signer-disjoint governance. **NOT ASSUMED:** checkpoint transfer after a material representation change.
13. **Q13 — Top risks:** semantic train/serve skew; missing runtime budget; teacher/domain/alignment bias.
14. **Q14 — Missing before selection:** a project-lead-frozen primary output family/fallback and its exact I/O/runtime contract. The evidence is sufficient to make that bounded choice; it is not sufficient to select a trained model.

**Decision:** evidence is sufficient for `PROJECT_LEAD_P7_MOBILE_ARCHITECTURE_SELECTION`; no architecture is selected or executed by P7-A.
""", encoding="utf-8")

write_json("APPHEAR_RECOGNITION_CANONICAL_STATE_P7A.json", {
    "parent": "APPHEAR_RECOGNITION_CANONICAL_STATE_P6CP1.json",
    "P6CP1_classification": "P6CP1_FROZEN_DWPOSE_ACCELERATION_TARGET_NOT_MET",
    "exact_dwpose_mobile_production_path": "CLOSED_ON_GOVERNED_TARGET",
    "dwpose_future_role": "OFFLINE_REFERENCE_TEACHER",
    "v2_future_role": "OFFLINE_REFERENCE_REPRESENTATION_NOT_AUTOMATIC_PRODUCTION_REQUIREMENT",
    "recognizer_candidate": "PFCE_MATCHED_EC_P3",
    "recognizer_checkpoint_transfer_to_new_representation": "NOT_ASSUMED",
    "D10": "PROTECTED",
    "pristine_signers": "UNUSED",
    "mobile_architecture_selected": False,
    "training_started": False,
    "new_model_benchmarked": False,
    "production_authorized": False,
    "P7A_classification": "P7A_ARCHITECTURE_DECISION_EVIDENCE_READY",
})

source_rows = []
for claim, rel, symbol, status in [
    ("P6CP1 closure and measured providers", "artifacts/recognition_upgrade/p6cp1_frozen_dwpose_runtime_acceleration_triage_01/APPHEAR_RECOGNITION_CANONICAL_STATE_P6CP1.json", "root object", "VERIFIED"),
    ("Android device runtime", "artifacts/recognition_upgrade/p6c_android_v2_device_feasibility_01/p6c_device_runtime_summary.json", "root object", "VERIFIED"),
    ("Current Android S0-S7 map", "artifacts/recognition_upgrade/p6a_production_runtime_compatibility_audit_01/p6a_current_android_pipeline.csv", "all rows", "VERIFIED"),
    ("S5 exact dependencies", "android/app/src/main/java/com/example/apphear/pipeline/recognition/SigningDetector.kt", "SigningDetector.update/frameMotion/handsRaised", "VERIFIED"),
    ("MediaPipe adapter semantics", "android/app/src/main/java/com/example/apphear/pipeline/recognition/LandmarkAdapter.kt", "pose/hands/handsPresent", "VERIFIED"),
    ("MediaPipe configuration", "android/app/src/main/java/com/example/apphear/pipeline/LandmarkerBundle.kt", "buildHand/buildPose", "VERIFIED"),
    ("Legacy S4 semantics", "android/app/src/main/java/com/example/apphear/pipeline/recognition/SessionNormalizer.kt", "update/feature", "VERIFIED"),
    ("S6/S7 behavior", "android/app/src/main/java/com/example/apphear/pipeline/recognition/RecognitionPipeline.kt", "processFrame", "VERIFIED"),
    ("Frozen V2 semantics", "pipeline/features/dwpose_representation_v2.py", "build_frame_features/build_padded_sequence", "VERIFIED"),
    ("P5B native teacher membership", "artifacts/recognition_upgrade/p5_representation_v2/p5b_migration_01/completed_manifest.csv", "8131 rows", "VERIFIED"),
    ("Sem-Lex usable coverage", "artifacts/recognition_upgrade/p5_representation_v2/p5d7b_semlex_integrity_audit_01/p5d7b_actual_usable_coverage.json", "root object", "VERIFIED"),
    ("D10 protection", "artifacts/recognition_upgrade/p5_representation_v2/p5d12_future_version_evidence_synthesis_01/p5_holdout_governance_final.json", "root object", "VERIFIED"),
    ("15 FPS minimum", "context/runtime-constraints.md", "Timing Budget", "VERIFIED"),
]:
    path = ROOT / rel
    source_rows.append({"claim":claim,"source_path":rel,"source_symbol_or_artifact":symbol,
                        "sha256":sha(path),"status":status})
write_csv("p7a_source_index.csv", source_rows)

(OUT / "P7A_SOURCE_OF_TRUTH_INDEX.md").write_text("# P7-A Source of Truth Index\n\n" + "\n".join(
    f"- **{r['status']} — {r['claim']}**: `{r['source_path']}`; `{r['source_symbol_or_artifact']}`; SHA-256 `{r['sha256']}`."
    for r in source_rows) + "\n", encoding="utf-8")

(OUT / "P7A_MOBILE_NATIVE_ARCHITECTURE_TRANSITION_AUDIT.md").write_text("""# P7-A Mobile-Native Architecture Transition Audit

## Decision

**P7A_ARCHITECTURE_DECISION_EVIDENCE_READY.** The exact DWPose-L FP32 flip-test path is closed as the direct mobile backend on the governed Xiaomi device. DWPose-L and V2 remain valuable offline teacher/reference contracts. Repository evidence is sufficient for the project lead to freeze one primary mobile output-family hypothesis and at most one fallback; it is not evidence for selecting a named model.

## What the product actually needs

**VERIFIED:** Current recognition and S5 depend on stable anatomical left/right hands, hand motion/geometry, wrists, elbows, shoulders, torso/hip reference, explicit absence/presence, frame order and source/signer lineage. S7 consumes model probabilities rather than landmarks, but any representation change invalidates assumed calibration.

**NOT ESTABLISHED:** The full DWPose 133-point topology, face/feet, exact score distribution, flip test, V2's 11-of-21 observation gate, 238 fields or 96 frames are intrinsic product requirements. They are frozen reference choices. Exact V2 remains mandatory only if reusing the current EC_P3 checkpoint.

## Current perception and S5

**VERIFIED:** Android uses MediaPipe Hands/Pose in IMAGE mode, adapted to two 21-point hand slots and 33 pose points. Pose currently runs every two frames with hold-last behavior. S5 is upstream of S4 and consumes MediaPipe-specific wrists, elbows, shoulders, hips, hand presence, NaN absence and motion history.

**SUPPORTED:** S5 is conceptually portable if a future source reproduces those signals through a frozen adapter and passes onset/release parity. A single shared perception source is plausible, not established.

## Teacher and training assets

**VERIFIED:** P5B retains 8,131 per-sample native DWPose and V2 records. They include all governed ASL Citizen and AppHear/local roles, but roles remain distinct. The relocated `G:/ASL CITIZEN/ASL CITIZEN/ASL_Citizen/videos` root contains 83,399 videos, and all 6,745 governed ASL Citizen rows match there by filename; governed hashes must be used to resolve paths. Sem-Lex retains 2,417 native/V2 pairs, of which 2,415 are post-audit usable across 65 classes and 32 signers.

**VERIFIED governance:** future training may use only primary TRAIN memberships, the 617 governed AppHear/local supplement TRAIN rows, and human-approved Sem-Lex under a frozen policy. ASL Citizen VAL is evaluation-only. D10 canonical TEST, protected replay and future pristine signers remain prohibited.

## Transfer boundary

**NOT ASSUMED:** the PFCE_MATCHED EC_P3 checkpoint transfers to materially different features. **SUPPORTED reusable methodology:** the causal TCN hypothesis, PFCE objective, EC_P3 exposure-controlled sampling, vocabulary, signer-disjoint splits and evaluation machinery.

## Runtime-first conclusion

The next program must freeze one output family, build a deployable skeleton, and prove Android operator/latency/memory feasibility before bulk teacher extraction or training. The governed minimum remains 15 sustained FPS. No formal memory ceiling exists.

## Top risks

1. Train/serve skew in handedness, confidence, validity or missingness.
2. A chosen hypothesis failing the 15 FPS/device-memory gate after expensive training.
3. Teacher/domain/alignment bias, especially insufficient full-vocabulary phone-domain diversity.

## Boundary

No training, teacher extraction, recognizer inference, new model selection, model benchmark, Android modification, V2/S5/S7 modification, D10 access or pristine-signer access occurred. `context/progress-tracker.md` was not modified.
""", encoding="utf-8")

parent_after = {name: sha(path) for name, path in PARENTS.items()}
integrity = {
    "passed": parent_before == parent_after,
    "parent_hashes_before": parent_before,
    "parent_hashes_after": parent_after,
    "D12_unchanged": parent_before["D12"] == parent_after["D12"],
    "P6A_unchanged": parent_before["P6A"] == parent_after["P6A"],
    "P6B_unchanged": parent_before["P6B"] == parent_after["P6B"],
    "P6BR1_unchanged": parent_before["P6BR1"] == parent_after["P6BR1"],
    "P6C_unchanged": parent_before["P6C"] == parent_after["P6C"],
    "P6CP1_unchanged": parent_before["P6CP1"] == parent_after["P6CP1"],
    "progress_tracker_unchanged": parent_before["progress_tracker"] == parent_after["progress_tracker"],
    "training": False, "teacher_extraction": False, "recognizer_inference": False,
    "D10": False, "pristine_data": False, "new_perception_model_selected": False,
    "new_perception_model_benchmarked": False, "Android_runtime_modified": False,
    "V2_modified": False, "S5_modified": False, "S7_modified": False,
}
write_json("p7a_integrity.json", integrity)

required = [
    "P7A_MOBILE_NATIVE_ARCHITECTURE_TRANSITION_AUDIT.md", "APPHEAR_RECOGNITION_CANONICAL_STATE_P7A.json",
    "P7A_SOURCE_OF_TRUTH_INDEX.md", "p7a_project_transition_decision.json",
    "p7a_downstream_feature_dependency_map.csv", "p7a_current_perception_capability_matrix.csv",
    "p7a_dwpose_teacher_asset_inventory.csv", "p7a_training_corpus_inventory.csv",
    "p7a_rgb_teacher_alignment_audit.csv", "p7a_dataset_governance_matrix.csv",
    "p7a_mobile_runtime_constraints.json", "p7a_s5_dependency_audit.json",
    "p7a_recognizer_transfer_boundary.json", "p7a_student_output_family_analysis.md",
    "p7a_runtime_first_development_plan.md", "p7a_architecture_risk_register.csv",
    "p7a_missing_evidence_register.csv", "p7a_loop_prevention_contract.json",
    "p7a_next_gate_decision_questions.md", "p7a_integrity.json",
    "p7a_source_index.csv",
]
missing_required = [name for name in required if not (OUT / name).is_file()]
if missing_required:
    raise RuntimeError(missing_required)

manifest = [{"path": name, "sha256": sha(OUT / name), "bytes": (OUT / name).stat().st_size}
            for name in sorted(required)]
write_json("artifact_hash_manifest.json", {"algorithm":"SHA256", "artifact_count":len(manifest), "files":manifest})

print(json.dumps({"classification":"P7A_ARCHITECTURE_DECISION_EVIDENCE_READY",
                  "integrity":"PASS" if integrity["passed"] else "FAIL",
                  "required_artifacts":len(required)+1,
                  "output":str(OUT)}, indent=2))
