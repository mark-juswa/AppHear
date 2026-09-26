from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/recognition_upgrade/p5_representation_v2"
OUT = BASE / "p5d12_future_version_evidence_synthesis_01"
PROGRESS = ROOT / "context/progress-tracker.md"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def write_json(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_csv(name: str, columns: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with (OUT / name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


SOURCES = {
    "p5b": BASE / "p5b_rcab_horizon_01/evaluation_summary.json",
    "rcac": BASE / "p5b_rcac3_p3_final_synthesis_01/p5b_rcac3_p3_augmentation_closure.csv",
    "d1": BASE / "p5d1_matched_representation_parity_01/p5d1_decision.json",
    "d2": BASE / "p5d2_temporal_objective_ablation_01/p5d2_decision.json",
    "d3": BASE / "p5d3_data_coverage_curve_01/p5d3_decision.json",
    "d6": BASE / "p5d6_semlex_post_review_01/p5d6_completed_human_review_result.json",
    "d7b": BASE / "p5d7b_semlex_integrity_audit_01/p5d7b_actual_usable_coverage.json",
    "d8": BASE / "p5d8_supplementation_design_01/p5d8_selected_policy.json",
    "d9b_class": BASE / "p5d9b_semlex_result_audit_01/p5d9b_experiment_classification.json",
    "d9b_branch": BASE / "p5d9b_semlex_result_audit_01/p5d9b_branch_classification.json",
    "d9b_slices": BASE / "p5d9b_semlex_result_audit_01/p5d9b_diagnostic_slices.csv",
    "d9b_exposure": BASE / "p5d9b_semlex_result_audit_01/p5d9b_class_exposure_diagnostic.csv",
    "d10a": BASE / "p5d10a_final_holdout_audit_01/p5d10a_decision.json",
    "d10a_corrections": BASE / "p5d10a_final_holdout_audit_01/p5d10a_d9b_bookkeeping_reconciliation.md",
    "d10b": BASE / "p5d10b_secondary_confirmation_01/p5d10b_decision.json",
    "d10b_summary": BASE / "p5d10b_secondary_confirmation_01/p5d10b_objective_summary.csv",
    "d10b_redistribution": BASE / "p5d10b_secondary_confirmation_01/p5d10b_redistribution_diagnostic.csv",
    "d10b_corrections": BASE / "p5d10b_secondary_confirmation_01/p5d10b_preinference_reconciliation.md",
    "d11_schedule": BASE / "p5d11_exposure_controlled_p3_01/p5d11_schedule_contract.json",
    "d11_schedule_summary": BASE / "p5d11_exposure_controlled_p3_01/p5d11_seed_schedule_summary.csv",
    "d11b": BASE / "p5d11_exposure_controlled_p3_01/p5d11b_decision.json",
    "d11b_summary": BASE / "p5d11_exposure_controlled_p3_01/p5d11b_comparison_summary.csv",
    "d11b_deltas": BASE / "p5d11_exposure_controlled_p3_01/p5d11b_seed_matched_deltas.csv",
    "android_schema": ROOT / "context/feature-schema.md",
    "p4_summary": ROOT / "context/recognition_upgrade/POST_E6_ARCHITECTURE_REVIEW.md",
    "p4_rtmdet": ROOT / "context/recognition_upgrade/P0_RTMDET_DETECTOR_RESULT.md",
}


def source_ref(key: str) -> str:
    path = SOURCES[key]
    return f"{rel(path)} (SHA-256 {sha(path)})"


def metric(stage: str, condition: str, population: str, name: str, value: float,
           units: str, seed: str, key: str) -> dict[str, Any]:
    path = SOURCES[key]
    return {
        "stage": stage,
        "condition": condition,
        "population": population,
        "metric": name,
        "value": f"{value:.17g}",
        "units": units,
        "seed_or_median": seed,
        "source_artifact": rel(path),
        "artifact_sha256": sha(path),
    }


def main() -> int:
    missing = [rel(p) for p in SOURCES.values() if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing governed sources: {missing}")
    progress_before = sha(PROGRESS)
    OUT.mkdir(parents=True, exist_ok=True)

    key_metrics = [
        metric("D1", "LEGACY258", "PRIMARY_VALIDATION", "median_clip_top1", 0.5465686274509803, "fraction", "median_3_seeds", "d1"),
        metric("D1", "V2_238", "PRIMARY_VALIDATION", "median_clip_top1", 0.5502450980392157, "fraction", "median_3_seeds", "d1"),
        metric("D1", "LEGACY258_MINUS_V2_238", "PRIMARY_VALIDATION", "clip_top1_delta", 0.02941176470588236, "fraction", "seed_101", "d1"),
        metric("D1", "LEGACY258_MINUS_V2_238", "PRIMARY_VALIDATION", "clip_top1_delta", -0.006127450980392246, "fraction", "seed_202", "d1"),
        metric("D1", "LEGACY258_MINUS_V2_238", "PRIMARY_VALIDATION", "clip_top1_delta", -0.009803921568627527, "fraction", "seed_303", "d1"),
        metric("D2", "PFCE_MATCHED", "PRIMARY_VALIDATION", "median_clip_top1", 0.5465686274509803, "fraction", "median_3_seeds", "d2"),
        metric("D2", "CLIPCE_AGGREGATION_ALIGNED", "PRIMARY_VALIDATION", "median_clip_top1", 0.5637254901960784, "fraction", "median_3_seeds", "d2"),
        metric("D2", "PFCE_MATCHED", "PRIMARY_VALIDATION", "persistent_wrong_fraction", 0.6724294813466788, "fraction", "all_runs", "d2"),
        metric("D2", "CLIPCE_AGGREGATION_ALIGNED", "PRIMARY_VALIDATION", "persistent_wrong_fraction", 0.42199248120300753, "fraction", "all_runs", "d2"),
        metric("D3", "PFCE_50_PERCENT", "PRIMARY_VALIDATION", "median_clip_top1", 0.44730392156862747, "fraction", "median_3_seeds", "d3"),
        metric("D3", "PFCE_75_PERCENT", "PRIMARY_VALIDATION", "median_clip_top1", 0.5343137254901961, "fraction", "median_3_seeds", "d3"),
        metric("D3", "PFCE_100_PERCENT", "PRIMARY_VALIDATION", "median_clip_top1", 0.5465686274509803, "fraction", "median_3_seeds", "d3"),
        metric("D3", "CLIPCE_50_PERCENT", "PRIMARY_VALIDATION", "median_clip_top1", 0.39215686274509803, "fraction", "median_3_seeds", "d3"),
        metric("D3", "CLIPCE_75_PERCENT", "PRIMARY_VALIDATION", "median_clip_top1", 0.5355392156862745, "fraction", "median_3_seeds", "d3"),
        metric("D3", "CLIPCE_100_PERCENT", "PRIMARY_VALIDATION", "median_clip_top1", 0.5637254901960784, "fraction", "median_3_seeds", "d3"),
        metric("D9B", "PFCE_P3_MINUS_BASELINE", "PRIMARY_VALIDATION", "median_signer_balanced_top1_delta", 0.005739766676005176, "fraction", "median_3_seeds", "d9b_branch"),
        metric("D9B", "PFCE_P3_MINUS_BASELINE", "SUPPLEMENTED_65", "median_top1_delta", 0.12820512820512825, "fraction", "median_3_seeds", "d9b_slices"),
        metric("D9B", "PFCE_P3_MINUS_BASELINE", "UNSUPPLEMENTED_171", "median_top1_delta", -0.04123711340206182, "fraction", "median_3_seeds", "d9b_slices"),
        metric("D9B", "NAIVE_P3", "TRAIN", "supplemented_65_class_share", 0.35157062617016843, "fraction", "frozen", "d9b_exposure"),
        metric("D10B", "PFCE_P3_MINUS_BASELINE", "CANONICAL_PRIMARY_TEST_236", "median_signer_balanced_top1_delta", -0.010088148239162598, "fraction", "median_3_seeds", "d10b_summary"),
        metric("D10B", "PFCE_P3_MINUS_BASELINE", "SUPPLEMENTED_65", "median_top1_delta", 0.10186513629842181, "fraction", "median_3_seeds", "d10b_redistribution"),
        metric("D10B", "PFCE_P3_MINUS_BASELINE", "UNSUPPLEMENTED_171", "median_top1_delta", -0.04888195527821115, "fraction", "median_3_seeds", "d10b_redistribution"),
        metric("D11B", "EC_P3_MINUS_BASELINE", "PRIMARY_VALIDATION", "median_signer_balanced_top1_delta", 0.01738679131781362, "fraction", "median_3_seeds", "d11b_summary"),
        metric("D11B", "EC_P3_MINUS_BASELINE", "PRIMARY_VALIDATION", "median_ordinary_top1_delta", 0.002450980392156965, "fraction", "median_3_seeds", "d11b_summary"),
        metric("D11B", "EC_P3_MINUS_BASELINE", "PRIMARY_VALIDATION", "median_macro_f1_delta", 0.003134728072414883, "fraction", "median_3_seeds", "d11b_summary"),
        metric("D11B", "EC_P3_MINUS_BASELINE", "SUPPLEMENTED_65", "median_top1_delta", 0.03418803418803418, "fraction", "median_3_seeds", "d11b_summary"),
        metric("D11B", "EC_P3_MINUS_BASELINE", "UNSUPPLEMENTED_171", "median_top1_delta", 0.006872852233677063, "fraction", "median_3_seeds", "d11b_summary"),
        metric("D11B", "EC_P3_MINUS_NAIVE_P3", "UNSUPPLEMENTED_171", "median_top1_recovery", 0.05154639175257736, "fraction", "median_3_seeds", "d11b_summary"),
        metric("D11B", "EC_P3_MINUS_BASELINE", "PRIMARY_VALIDATION", "median_clip_nll_delta", 0.009613008343188234, "nats", "median_3_seeds", "d11b_summary"),
        metric("D11B", "EC_P3_MINUS_BASELINE", "PRIMARY_VALIDATION", "median_per_frame_accuracy_delta", -0.006265754411235114, "fraction", "median_3_seeds", "d11b_summary"),
    ]
    write_csv("p5d12_key_metrics.csv", list(key_metrics[0]), key_metrics)

    claims = [
        ("C01", "The 4x64 causal TCN can learn V2; the early horizon was underconverged.", "VERIFIED_FACT", "p5b", "100 epochs; Top1 0.442748; 12,300 updates", "HIGH", "The governed longer run established model learnability.", "The model cannot learn V2."),
        ("C02", "The broad Legacy258-vs-V2 input-stack difference was not a consistent primary explanation.", "SUPPORTED_INTERPRETATION", "d1", "Legacy-V2 Top1 deltas +2.94/-0.61/-0.98 pp", "LOW", "D1 weakened the broad input-stack-primary hypothesis.", "D1 proved V2 perfect or fully sufficient."),
        ("C03", "Temporal objective materially changes behavior but CLIPCE was not sufficient for promotion.", "VERIFIED_FACT", "d2", "Persistent-wrong fraction 0.6724 PFCE vs 0.4220 CLIPCE", "MODERATE", "TEMPORAL_OBJECTIVE_HELPFUL_BUT_NOT_SUFFICIENT.", "CLIPCE is the production objective."),
        ("C04", "Current-distribution class-wise signer/variant coverage remained unsaturated.", "SUPPORTED_INTERPRETATION", "d3", "Both objectives improved from 75% to 100%", "HIGH", "Class-wise natural signer/variant coverage is a material contributor.", "More raw videos are the only solution."),
        ("C05", "Naive P3 caused vocabulary redistribution.", "VERIFIED_FACT", "d10b", "65 +10.19 pp; 171 -4.89 pp on secondary test", "MODERATE", "Redistribution reproduced on a signer-disjoint, development-exposed population.", "Pristine final-holdout proof."),
        ("C06", "Class-exposure redistribution materially contributed to naive P3 harm.", "SUPPORTED_INTERPRETATION", "d11b", "171 became +0.69 pp vs baseline and recovered +5.15 pp vs naive P3", "MODERATE", "Class exposure was a material contributor.", "Class exposure was the only cause."),
        ("C07", "PFCE_MATCHED + EC_P3 is the leading future-version offline candidate.", "FROZEN_ENGINEERING_DECISION", "d11b", "+1.74 pp median signer-balanced Top1; 3/3 positive", "MODERATE", "Leading future-version offline candidate.", "Final production model."),
        ("C08", "The canonical 2,620-clip test is signer-disjoint but development-exposed.", "VERIFIED_FACT", "d10a", "236 classes; 11 signers; zero exact overlap", "HIGH", "Signer-disjoint secondary confirmation population.", "Pristine final holdout."),
        ("C09", "EC_P3 has not been confirmed on a pristine signer cohort.", "NOT_ESTABLISHED", "d11b", "D11 did not access test; validation has five signer groups", "HIGH", "Pristine confirmation remains future work.", "Unbiased final generalization confirmed."),
        ("C10", "The D11 targeted-class gain is caused by signer diversity alone.", "NOT_ESTABLISHED", "d11b", "Within-class pool changed while exposure was controlled", "HIGH", "The intervention preserved external signer/variant diversity.", "Signer diversity alone caused +3.42 pp."),
    ]
    claim_rows = []
    for cid, text, status, key, smetric, conf, allowed, forbidden in claims:
        claim_rows.append({"claim_id": cid, "claim_text": text, "claim_status": status,
                           "supporting_artifact": source_ref(key), "supporting_metric": smetric,
                           "confidence": conf, "allowed_wording": allowed,
                           "forbidden_wording": forbidden})
    write_csv("p5d12_claim_matrix.csv", list(claim_rows[0]), claim_rows)

    loops = [
        ("detector roulette", "P4/C0/P0", "Multiple detector routes failed governed recall/usability gates.", "CLOSED", "New end-to-end evidence isolates perception as uncompensated bottleneck", "Do not try another detector because it is available."),
        ("MediaPipe confidence sweeps", "P4 E2D", "Threshold recovery traded missing hands for unacceptable false positives.", "CLOSED", "New independent data changes the governed operating frontier", "No generic threshold sweep."),
        ("ROI/recovery loops", "P4 E2B-E2E", "Static, pose-guided, upper-body and recovery routes did not pass.", "CLOSED", "Controlled end-to-end downstream failure attribution", "No recovery-model loop."),
        ("optical flow", "P4", "Explored without a promotable end-to-end solution.", "CLOSED", "New causal evidence and a preregistered contract", "No optical-flow retry."),
        ("WiLoR", "P4", "Explored and not promoted.", "CLOSED", "New causal perception evidence", "No ungoverned WiLoR substitution."),
        ("Hand5/SSDLite", "P4", "Explored and not promoted.", "CLOSED", "New causal perception evidence", "No model roulette."),
        ("generic augmentation", "RCA-C", "Historical package regressed validation without stress benefit.", "REJECTED_PRIMARY", "A new, mechanism-specific preregistration", "No package retest."),
        ("scale augmentation", "RCA-C", "Broke frozen normalized V2 shoulder-scale geometry.", "REJECTED", "A new representation contract and causal justification", "No post-normalization scale augmentation."),
        ("temporal augmentation", "RCA-C", "Excessive displacement; deferred only for a governed low-FPS cohort.", "DEFERRED", "A verified low-FPS cohort", "No general temporal augmentation."),
        ("noise augmentation", "RCA-C", "Unsupported/no compensating benefit.", "REJECTED", "Measured sensor-noise model and preregistration", "No generic XY noise."),
        ("representation redesign", "D1", "Broad Legacy258-vs-V2 advantage was inconsistent; formal D1 result was inconclusive.", "NOT_SELECTED", "New evidence isolates missing V2 information", "Do not restart Legacy-vs-V2 competition."),
        ("CLIPCE promotion", "D2/D9B", "Temporal benefit but mixed broad generalization.", "NOT_PROMOTED", "New preregistered evidence resolving signer heterogeneity", "Do not promote CLIPCE now."),
        ("naive Sem-Lex merge", "D9B/D10B", "Reproducible redistribution harmed 171 classes.", "REJECTED", "Exposure-controlled design", "Do not restore naive P3 sampling."),
        ("P3 cap tuning", "D8-D11", "P3 is frozen; D11 isolated exposure without cap tuning.", "FROZEN", "A new research cycle with independent evaluation", "No post-result cap sweep."),
        ("selected-word recording pilot", "Stage1B/D3", "Full-vocabulary coverage and controlled supplementation superseded it.", "CLOSED", "New quantified gap not addressable by governed external data", "No convenience-class pilot."),
        ("adding more Sem-Lex to same 65", "D9-D11", "Current intervention already separates diversity from exposure.", "CLOSED_CURRENT_CYCLE", "New pristine evidence and a new contract", "No additional same-class merge."),
        ("using D10B TEST as development validation", "D10A/D10B", "Population is development-exposed and secondary-only.", "FORBIDDEN", "Never for the current cycle", "No tuning or model selection on it."),
        ("arbitrary seed selection", "D10A-D12", "No governed deployment seed exists.", "FORBIDDEN", "Validation-only rule frozen before new evaluation", "Do not pick 101/202/303 by favorable metric."),
    ]
    loop_rows = [{"topic": x[0], "historical_experiment": x[1], "result": x[2], "status": x[3],
                  "reopen_condition": x[4], "forbidden_without_new_evidence": x[5]} for x in loops]
    write_csv("p5_future_loop_prevention_register.csv", list(loop_rows[0]), loop_rows)

    rejected = [
        {"candidate": "NAIVE_P3", "status": "REJECTED_FOR_BROAD_FULL_VOCAB_PROMOTION", "reason": "Reproducible supplemented-class gain with unsupplemented-class harm."},
        {"candidate": "CLIPCE", "status": "NOT_PROMOTED", "reason": "Helpful temporal behavior but mixed broader generalization."},
        {"candidate": "LEGACY258_RESTART", "status": "NOT_SELECTED", "reason": "No consistent matched-training advantage; formal D1 evidence remains inconclusive."},
        {"candidate": "HISTORICAL_AUGMENTATION_RECIPE", "status": "REJECTED_AS_PRIMARY_SOLUTION", "reason": "No clean transfer; scale/noise/package rejected and temporal restricted."},
        {"candidate": "P4_PERCEPTION_ALTERNATIVES", "status": "FROZEN", "reason": "Extensive routes exhausted without promotable end-to-end evidence."},
        {"candidate": "POPSIGN_V2_1", "status": "EXCLUDED_FROM_APPHEAR_SUPPLEMENTATION", "reason": "MODALITY_MISMATCH_ONE_HAND_RECORDING_CONSTRAINT."},
    ]
    write_csv("p5d12_rejected_directions.csv", list(rejected[0]), rejected)

    questions = [
        ("Q01", "P0", "Can frozen EC_P3 reproduce on a new pristine signer-disjoint cohort?", "RESEARCH", "No such holdout currently exists."),
        ("Q02", "P0", "How can production generate an exact V2-compatible feature contract?", "ENGINEERING", "Android currently uses MediaPipe legacy [96,258]."),
        ("Q03", "P0", "Does TFLite conversion preserve EC_P3 outputs and aggregation?", "ENGINEERING", "No export parity evidence yet."),
        ("Q04", "P1", "How should probability calibration/confidence be governed given worse clip NLL?", "RESEARCH_ENGINEERING", "D11 NLL worsened 3/3."),
        ("Q05", "P1", "How do S5 gating and S7 confirmation interact with V2/EC_P3?", "ENGINEERING", "Not evaluated."),
        ("Q06", "P1", "Can the runtime meet target latency and low-FPS robustness?", "ENGINEERING", "DWPose-L on-device viability is unknown."),
        ("Q07", "P2", "How should continuous ASL be modeled?", "FUTURE_RESEARCH", "Phrase-level evidence not established."),
        ("Q08", "P2", "Would a richer schema add information beyond frozen V2?", "FUTURE_RESEARCH", "Do not reopen automatically."),
        ("Q09", "P2", "How should open-set/no-sign safety be handled?", "FUTURE_RESEARCH", "Not established for EC_P3."),
        ("Q10", "P3", "Are alternative specialists or RGB fusion useful?", "FUTURE_RESEARCH", "Historical routes are non-promoted; new evidence required."),
    ]
    qrows = [{"question_id": q[0], "priority": q[1], "question": q[2], "domain": q[3], "status": q[4]} for q in questions]
    write_csv("p5d12_open_questions.csv", list(qrows[0]), qrows)

    candidate = {
        "candidate_name": "PFCE_MATCHED_EC_P3",
        "candidate_status": "LEADING_FUTURE_VERSION_OFFLINE_CANDIDATE",
        "representation": "DWPOSE_REPRESENTATION_V2_238",
        "input_shape": [96, 238],
        "model": "4x64 causal TCN",
        "objective": "PFCE_MATCHED",
        "training_policy": "EXACT_BASELINE_CLASS_SCHEDULE_REPLAY_WITH_P3_WITHIN_CLASS_DIVERSITY",
        "seeds_with_experimental_evidence": [101, 202, 303],
        "validation_confidence": "MODERATE",
        "production_ready": False,
        "android_integrated": False,
        "pristine_signer_confirmation": False,
        "single_deployment_checkpoint_selected": False,
        "freeze_source": source_ref("d11b"),
    }
    write_json("p5d12_candidate_freeze.json", candidate)
    write_json("APPHEAR_RECOGNITION_CANONICAL_STATE_D11.json", {
        "read_first": True,
        "current_phase": "P5_D12_RESEARCH_EVIDENCE_CLOSURE",
        "current_candidate": "PFCE_MATCHED_EC_P3",
        "production_runtime_representation": "LEGACY_MEDIA_PIPE_S4_[96,258]",
        "offline_research_representation": "DWPOSE_REPRESENTATION_V2_238_[96,238]",
        "model_architecture": "4x64 causal TCN",
        "objective": "PFCE_MATCHED",
        "training_policy": "EXACT_BASELINE_CLASS_SCHEDULE_REPLAY_WITH_P3_WITHIN_CLASS_DIVERSITY",
        "candidate_status": "LEADING_FUTURE_VERSION_OFFLINE_CANDIDATE",
        "confidence": "MODERATE",
        "test_status": "CANONICAL_2620_SECONDARY_CONFIRMATION_ONLY_DEVELOPMENT_EXPOSED",
        "p4_status": "P4_PERCEPTION_ARCHITECTURE_EXPLORATION_FROZEN",
        "v2_status": "FROZEN_OFFLINE_RESEARCH_CONTRACT",
        "clipce_status": "RESEARCH_DIAGNOSTIC_NOT_PROMOTED",
        "naive_p3_status": "REJECTED_FOR_BROAD_FULL_VOCAB_PROMOTION",
        "ec_p3_status": "LEADING_FUTURE_VERSION_OFFLINE_CANDIDATE",
        "pristine_holdout_available": False,
        "next_research_gate": "NEW_PRISTINE_SIGNER_DISJOINT_EVALUATION_COHORT_IF_RESOURCED",
        "next_engineering_gate": "PRODUCTION_RUNTIME_COMPATIBILITY_AND_MIGRATION_DESIGN",
        "exact_next_gate": "PROJECT_LEAD_CHOOSES_PRISTINE_CONFIRMATION_OR_PRODUCTION_MIGRATION",
        "forbidden_immediate_actions": ["D13", "training", "test inference", "deployment seed selection", "Android modification", "P4 reopening", "V2 modification", "CLIPCE promotion", "P3 cap tuning"],
    })
    write_json("p5_holdout_governance_final.json", {
        "population": "CANONICAL_PRIMARY_TEST_236",
        "clips": 2620,
        "classes": 236,
        "signers": 11,
        "status": "SECONDARY_CONFIRMATION_ONLY",
        "signer_disjoint_from_train_val": True,
        "sample_raw_media_disjoint": True,
        "development_exposed": True,
        "may_be_used_for_new_tuning": False,
        "may_be_called_pristine": False,
        "d11_accessed_it": False,
        "future_pristine_confirmation_requirement": ["NEW_SIGNERS", "SIGNER_DISJOINT", "NO_DEVELOPMENT_VISIBILITY_BEFORE_CONTRACT_FREEZE", "FULL_VOCAB_PREFERRED"],
        "source": source_ref("d10a"),
    })
    write_json("p5d12_next_step_decision_tree.json", {
        "decision_owner": "PROJECT_LEAD",
        "exact_next_gate": "PROJECT_LEAD_CHOOSES_PRISTINE_CONFIRMATION_OR_PRODUCTION_MIGRATION",
        "paths": {
            "A_STRONGER_SCIENTIFIC_CONFIRMATION": {"action": "Design a new evaluation-only signer-disjoint cohort, preferably all 236 classes; freeze baseline-vs-EC_P3 contract before inference.", "prohibitions": ["train on cohort", "tune EC_P3 on cohort", "call reduced vocabulary full confirmation"]},
            "B_NO_TIME_FOR_NEW_SIGNERS": {"action": "Freeze D11 as moderate validation evidence and list pristine confirmation as future work.", "prohibitions": ["manufacture stronger claims"]},
            "C_PRODUCT_ANDROID_ENGINEERING": {"action": "Begin PRODUCTION_RUNTIME_COMPATIBILITY_AND_MIGRATION_DESIGN, starting with how runtime can generate a V2-compatible semantic contract.", "prohibitions": ["drop best.keras into Android", "modify Android in D12"]},
        },
        "executed": False,
    })
    write_json("p5d12_decision.json", {
        "classification": "P5D12_RESEARCH_EVIDENCE_SYNTHESIZED_EC_P3_LEADING_CANDIDATE",
        "confidence": "MODERATE",
        "candidate": "PFCE_MATCHED_EC_P3",
        "production_ready": False,
        "android_integrated": False,
        "pristine_holdout_available": False,
        "material_contradictions": [],
        "non_blocking_discrepancies": ["D1 repository classification is REPRESENTATION_PARITY_EXPERIMENT_INCONCLUSIVE/LOW, weaker than the D12 brief's shorthand."],
        "next_gate": "PROJECT_LEAD_CHOOSES_PRISTINE_CONFIRMATION_OR_PRODUCTION_MIGRATION",
        "next_gate_executed": False,
    })

    corrections = f"""# P5-D12 Corrections and Discrepancies

- [VERIFIED_FACT] **D9 exact taxonomy:** 45 human `ACCEPT_EXACT_FORM` classes plus 2 prior `ACCEPT_METADATA_EXACT` classes equals the governed exact-47 slice. Source: {source_ref('d10a_corrections')}.
- [VERIFIED_FACT] **Bootstrap schema:** historical `point_delta` naming was reconciled so empirical observed delta is distinguished from the bootstrap distribution mean. Source: {source_ref('d10a_corrections')}.
- [VERIFIED_FACT] **Stale signer-overlap wording:** supplement validation stress and reused positive diagnostics are development-exposed, signer-disjoint partial-vocabulary diagnostics. Source: {source_ref('d10b_corrections')}.
- [VERIFIED_FACT] **Protected replay exposure wording:** conservatively `EXPOSURE_NOT_RESOLVED_NO_EVALUATION_ARTIFACT_FOUND`; it is not promoted. Source: {source_ref('d10b_corrections')}.
- [VERIFIED_FACT] **Canonical test exposure:** the 2,620-row test is technically signer/sample disjoint but development-exposed, so it is secondary confirmation only. Source: {source_ref('d10a')}.
- [VERIFIED_FACT] **D1 source conflict:** the D12 brief requests the shorthand `INPUT_STACK_NOT_PRIMARY_UNDER_MATCHED_TRAINING`, but the governed repository decision is `REPRESENTATION_PARITY_EXPERIMENT_INCONCLUSIVE` with LOW confidence. The repository result wins. D12 therefore states only the supported interpretation that the broad legacy-vs-V2 advantage was inconsistent and weakened as a primary explanation. Source: {source_ref('d1')}.

[SUPPORTED_INTERPRETATION] None of these corrections materially invalidates D11's exposure-controlled result. The D1 correction narrows an upstream claim rather than changing D11 membership, schedules, predictions, or metrics.
"""
    (OUT / "p5d12_corrections_and_discrepancies.md").write_text(corrections, encoding="utf-8")

    gap = """# P5-D12 Research-to-Product Gap

## Architecture boundary

- [VERIFIED_FACT] Android production currently uses CameraX → MediaPipe Hands/Pose → legacy S4 `[96,258]` → S5 gate → S6 TFLite recognizer → S7 confirmation → UI.
- [VERIFIED_FACT] `DWPOSE_REPRESENTATION_V2_238 [96,238]` is an offline experimental contract, not the current Android runtime contract.
- [NOT_ESTABLISHED] The D11 EC_P3 checkpoint cannot be assumed drop-in compatible with Android.

## Required migration evidence

- [CURRENT_HYPOTHESIS] A separate `PRODUCTION_RUNTIME_COMPATIBILITY_AND_MIGRATION_DESIGN` phase should first determine whether target hardware can generate an exact V2-semantic input contract.
- [NOT_ESTABLISHED] DWPose-L Android latency, alternative-backend semantic parity, Kotlin/TFLite preprocessing parity, online observed flags, S5/S7 interaction, calibration, TFLite conversion parity, CPU correctness, optional GPU performance, and low-FPS signer-independent behavior.
- [FROZEN_ENGINEERING_DECISION] No RecognitionPipeline, ModelContract, S4/S5/S7, TFLite asset, or recognition-config change is authorized by D12.

## Product evidence still missing

- [NOT_ESTABLISHED] Pristine signer-independent accuracy, continuous-ASL behavior, open-set/no-sign safety, phrase-level accuracy, runtime latency, and calibrated confirmation behavior.
"""
    (OUT / "p5d12_research_to_product_gap.md").write_text(gap, encoding="utf-8")

    timeline = [
        ("P5-B/RCA-B", "[VERIFIED_FACT] Longer governed training established that the 4x64 causal TCN can learn V2; the short horizon was not enough."),
        ("RCA-C", "[HISTORICAL_REJECTED_DIRECTION] Historical augmentation transfer was rejected as the primary solution."),
        ("D1", "[VERIFIED_FACT] Formal result was inconclusive/low confidence. [SUPPORTED_INTERPRETATION] Legacy258 did not show a consistent matched-training advantage over V2."),
        ("D2", "[VERIFIED_FACT] Temporal objective was helpful but insufficient; PFCE remained selected and CLIPCE diagnostic-only."),
        ("D3", "[VERIFIED_FACT] Both objectives continued improving toward 100% current-distribution coverage. [SUPPORTED_INTERPRETATION] Class-wise signer/variant coverage remained unsaturated."),
        ("D4-D8", "[VERIFIED_FACT] Governed Sem-Lex review/extraction produced 65 accepted classes, 2,415 usable clips, and a frozen 881-row P3 diversity policy."),
        ("D9B", "[VERIFIED_FACT] Naive P3 helped 65 supplemented classes but harmed 171 unsupplemented classes while their training share rose from 20.61% to 35.16%."),
        ("D10A-D10B", "[VERIFIED_FACT] No pristine holdout exists; secondary confirmation reproduced redistribution and full-vocabulary directional harm."),
        ("D11A", "[VERIFIED_FACT] Exact baseline class-label exposure was replayed with zero deviation while P3 within-class diversity remained available."),
        ("D11B", "[VERIFIED_FACT] EC_P3 improved signer-balanced Top1 in 3/3 seeds and removed the median directional harm to the 171 classes; NLL/PF-accuracy caveats remain."),
    ]
    timeline_md = "\n".join(f"- **{stage}:** {finding}" for stage, finding in timeline)
    synthesis = f"""# P5-D12 Future-Version Evidence Synthesis

## Decision

[FROZEN_ENGINEERING_DECISION] `P5D12_RESEARCH_EVIDENCE_SYNTHESIZED_EC_P3_LEADING_CANDIDATE`.

[FROZEN_ENGINEERING_DECISION] The leading future-version **offline** candidate is `PFCE_MATCHED + EC_P3`, using frozen `DWPOSE_REPRESENTATION_V2_238 [96,238]` and the 4x64 causal TCN. Confidence is MODERATE. It is not production-ready, not Android-integrated, and has no selected deployment seed.

## Architecture distinction

[VERIFIED_FACT] Android production currently uses CameraX → MediaPipe Hands/Pose → legacy `[96,258]` S4 → S5 → S6 TFLite → S7 → UI. Source: {source_ref('android_schema')}.

[VERIFIED_FACT] V2 is deterministic, mask-aware, float32 `[96,238]`, compact/zero-tail padded, contains no fake Z and performs no carry/interpolation/extrapolation or opposite-hand copying. It remains offline experimental only.

## Evidence timeline

{timeline_md}

## D9 → D10 → D11 causal chain

[VERIFIED_FACT] Naive P3 jointly changed external signer/variant diversity and the 65-class training share (`20.6062% → 35.1571%`). D9 validation showed supplemented-65 `+12.8205 pp` and unsupplemented-171 `-4.1237 pp` median Top1. D10 secondary confirmation showed `+10.1865 pp` and `-4.8882 pp`, with full-vocabulary signer-balanced `-1.0088 pp`.

[VERIFIED_FACT] D11 changed only the sampling/class-exposure contract: exact baseline class schedule replay, 12,300 updates, 392,600 draws/seed, zero per-class exposure deviation, exact unsupplemented sample-identity replay, and P3 within-class diversity. All 881 Sem-Lex examples had schedule opportunity.

[SUPPORTED_INTERPRETATION] Class-exposure redistribution was a **material contributor** to naive P3's 171-class degradation: EC_P3 made the 171 slice `+0.6873 pp` versus baseline and recovered `+5.1546 pp` versus naive P3 while retaining a smaller `+3.4188 pp` 65-class gain.

[SUPPORTED_INTERPRETATION] Increased class training frequency materially contributed to naive P3's large targeted-class gain because the median 65-class effect fell from `+12.8205 pp` under naive P3 to `+3.4188 pp` under exposure control.

[NOT_ESTABLISHED] Signer diversity alone caused the residual 65-class gain.

## D11 result and tradeoffs

- [VERIFIED_FACT] Median signer-balanced Top1 delta: `+0.01738679131781362` (3/3 seeds positive).
- [VERIFIED_FACT] Median ordinary Top1 delta: `+0.002450980392156965`.
- [VERIFIED_FACT] Median MacroF1 delta: `+0.003134728072414883`.
- [VERIFIED_FACT] Median clip-NLL delta: `+0.009613008343188234` (worse in 3/3 seeds).
- [VERIFIED_FACT] Median per-frame accuracy delta: `-0.006265754411235114` (declined 2/3).
- [VERIFIED_FACT] Top5 direction was mixed.
- [VERIFIED_FACT] Five validation signer groups: two consistently improved, three mixed; all signer-block intervals crossed zero.
- [SUPPORTED_INTERPRETATION] These tradeoffs preserve MODERATE—not HIGH—confidence and require future calibration/product analysis; they do not overturn the preregistered D11 classification.

## Frozen directions

[FROZEN_ENGINEERING_DECISION] P4 remains `P4_PERCEPTION_ARCHITECTURE_EXPLORATION_FROZEN`. Reopen only with controlled end-to-end evidence that current perception/missingness creates errors downstream representation/training cannot compensate. Historical routes include MediaPipe VIDEO/tracking and confidence sweeps; static/pose/upper-body ROI; optical flow; HaGRID; custom MobileNet; RTMDet; WiLoR; Hand5/SSDLite; recovery/eligibility; and identity/carry-forward.

[HISTORICAL_REJECTED_DIRECTION] Naive P3 is rejected for broad full-vocabulary promotion; CLIPCE is not promoted; historical augmentation is rejected as the primary solution; Legacy258-vs-V2 competition is not restarted; P4 alternatives remain closed.

## Holdout governance

[VERIFIED_FACT] The canonical test has 2,620 clips, 236 classes and 11 signers and is signer/sample/raw-media disjoint, but it is development-exposed. It is `SECONDARY_CONFIRMATION_ONLY`, not pristine. D11 did not access it.

## What remains unestablished

[NOT_ESTABLISHED] EC_P3 on a new pristine signer cohort; EC_P3 on the closed D10B population; Android improvement; on-device V2/DWPose feasibility; continuous ASL; open-set/no-sign safety; calibration; S5/S7 interaction; final product signer-independent accuracy.

## Next gate

[FROZEN_ENGINEERING_DECISION] `PROJECT_LEAD_CHOOSES_PRISTINE_CONFIRMATION_OR_PRODUCTION_MIGRATION`. D12 executes neither path.
"""
    (OUT / "P5D12_FUTURE_VERSION_EVIDENCE_SYNTHESIS.md").write_text(synthesis, encoding="utf-8")

    handoff = f"""# AppHear Recognition Handoff — D1 to D11

## 1. Product north star

[FROZEN_ENGINEERING_DECISION] Cross-signer, end-to-end signed-phrase accuracy under streaming conditions is the product metric; D11 is offline isolated-sign validation evidence, not product proof.

## 2. Current production architecture

[VERIFIED_FACT] Android: CameraX → MediaPipe Hands/Pose → legacy `[96,258]` → S5 gate → S6 TFLite → S7 confirmation → UI. V2 is not deployed.

## 3. Offline research architecture

[VERIFIED_FACT] DWPose V2 `[96,238]` → 4x64 causal TCN → PFCE → masked-mean probability clip prediction. The leading training policy is EC_P3 exact baseline class-schedule replay with frozen P3 within-class diversity.

## 4. Experiment timeline

{timeline_md}

## 5. Verified findings

- [VERIFIED_FACT] The TCN learns V2 with sufficient horizon.
- [VERIFIED_FACT] Objective affects temporal errors; CLIPCE is not broadly promotable.
- [VERIFIED_FACT] Current-distribution learning curves remained positive near full coverage.
- [VERIFIED_FACT] Naive P3 redistributed performance toward supplemented labels.
- [VERIFIED_FACT] EC_P3 restored exact class exposure and produced positive signer-balanced deltas in 3/3 seeds.

## 6. Rejected directions

[HISTORICAL_REJECTED_DIRECTION] See `p5d12_rejected_directions.csv` and `p5_future_loop_prevention_register.csv`. Do not resume detector/ROI roulette, generic augmentation, naive P3, CLIPCE promotion, cap tuning, test tuning, or arbitrary seed selection.

## 7. D9 → D10 → D11 causal story

[SUPPORTED_INTERPRETATION] Exposure redistribution materially caused the unsupplemented-class harm. It also materially inflated naive P3's targeted-class gain. External signer/variant diversity may retain value within class, but its isolated causal effect is not proved.

## 8. Current candidate

[FROZEN_ENGINEERING_DECISION] `PFCE_MATCHED + EC_P3`, confidence MODERATE, offline only, no deployment seed selected.

## 9. Current limitations

[NOT_ESTABLISHED] Pristine signer confirmation, calibration, production runtime compatibility, continuous ASL, open-set safety, Android behavior.

## 10. Holdout governance

[VERIFIED_FACT] Canonical test is signer-disjoint but development-exposed: secondary confirmation only; never use it for new tuning.

## 11. Loop prevention

[FROZEN_ENGINEERING_DECISION] Read `p5_future_loop_prevention_register.csv` before proposing recognition work.

## 12. Next-step decision tree

[FROZEN_ENGINEERING_DECISION] A: new pristine cohort; B: freeze moderate validation evidence; C: separate runtime compatibility/migration design.

## 13. Productionization gap

[NOT_ESTABLISHED] A production backend capable of the exact V2 semantic contract, TFLite parity, latency, missingness behavior, gating/confirmation interaction, and calibrated confidence.

## 14. Exact next gate

[FROZEN_ENGINEERING_DECISION] `PROJECT_LEAD_CHOOSES_PRISTINE_CONFIRMATION_OR_PRODUCTION_MIGRATION`.
"""
    (OUT / "APPHEAR_RECOGNITION_HANDOFF_D1_TO_D11.md").write_text(handoff, encoding="utf-8")

    progress_after = sha(PROGRESS)
    generated = sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in {"artifact_hash_manifest.json", "p5d12_integrity.json"})
    source_hashes = {rel(p): sha(p) for p in SOURCES.values()}
    integrity = {
        "passed": progress_before == progress_after and not missing,
        "source_files_verified": len(SOURCES),
        "missing_sources": missing,
        "source_hashes": source_hashes,
        "progress_tracker_sha256_before": progress_before,
        "progress_tracker_sha256_after": progress_after,
        "progress_tracker_untouched": progress_before == progress_after,
        "training_performed": False,
        "model_inference_performed": False,
        "test_accessed": False,
        "checkpoint_loaded": False,
        "dataset_modified": False,
        "v2_modified": False,
        "p4_reopened": False,
        "android_modified": False,
        "new_experiment_started": False,
        "material_contradiction": False,
        "non_blocking_d1_discrepancy_recorded": True,
    }
    write_json("p5d12_integrity.json", integrity)
    generated = sorted(p for p in OUT.iterdir() if p.is_file() and p.name != "artifact_hash_manifest.json")
    manifest = {
        "schema": "P5D12_ARTIFACT_HASH_MANIFEST_V1",
        "files": [{"path": rel(p), "sha256": sha(p), "bytes": p.stat().st_size} for p in generated],
        "governed_source_hashes": source_hashes,
    }
    write_json("artifact_hash_manifest.json", manifest)
    print(json.dumps({"passed": integrity["passed"], "outputs": len(manifest["files"]) + 1,
                      "classification": "P5D12_RESEARCH_EVIDENCE_SYNTHESIZED_EC_P3_LEADING_CANDIDATE",
                      "progress_tracker_untouched": integrity["progress_tracker_untouched"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
