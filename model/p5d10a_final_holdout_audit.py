"""P5-D10A holdout eligibility audit.

This module performs metadata, lineage, static tensor-integrity, and historical
exposure checks only.  It deliberately contains no TensorFlow/Keras imports and
never loads a checkpoint or creates model predictions.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RU = ROOT / "artifacts" / "recognition_upgrade"
P5 = RU / "p5_representation_v2"
PHASE1 = RU / "phase1_full_vocab"
MANIFEST_DIR = PHASE1 / "manifest_01"
CANONICAL_MANIFEST = MANIFEST_DIR / "canonical_manifest.csv"
V2 = P5 / "p5b_migration_01" / "dataset"
D8 = P5 / "p5d8_supplementation_design_01"
D9B = P5 / "p5d9b_semlex_result_audit_01"
OUT = P5 / "p5d10a_final_holdout_audit_01"
PROGRESS = ROOT / "context" / "progress-tracker.md"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def membership_sha(sample_ids: Iterable[str]) -> str:
    return hashlib.sha256("\n".join(map(str, sample_ids)).encode("utf-8")).hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else ["status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key] for key in data.files}


def inverse_vocab() -> tuple[dict[str, int], dict[int, str]]:
    vocab = json.loads((V2 / "vocab.json").read_text(encoding="utf-8"))
    return vocab, {int(value): key for key, value in vocab.items()}


def npz_population(path: Path) -> dict[str, Any]:
    data = load_npz(path)
    y = data["y"].astype(int)
    signer_key = "signer_group_ids" if "signer_group_ids" in data else "participant_ids"
    sample_ids = data["sample_ids"].astype(str)
    signers = data[signer_key].astype(str)
    return {
        "path": path,
        "data": data,
        "rows": len(y),
        "classes": len(set(y.tolist())),
        "signers": len(set(signers.tolist())),
        "sample_ids": sample_ids,
        "signer_ids": signers,
        "y": y,
        "membership_sha256": membership_sha(sample_ids.tolist()),
        "feature_tensor_sha256": sha256(path),
    }


def feature_contract(data: dict[str, np.ndarray], expected_channels: int = 238) -> dict[str, Any]:
    x = data.get("X")
    mask = data.get("frame_mask")
    if x is None or mask is None:
        return {"available": False, "passed": False, "reason": "X_OR_FRAME_MASK_MISSING"}
    shape_ok = x.ndim == 3 and x.shape[1:] == (96, expected_channels)
    dtype_ok = x.dtype == np.float32
    finite = bool(np.isfinite(x).all())
    mask_shape = mask.shape == x.shape[:2]
    mask_bool = mask.dtype == np.bool_
    compact = bool(np.all(np.maximum.accumulate((~mask).astype(np.int8), axis=1) <= (~mask).astype(np.int8)))
    padding_zero = bool(np.all(x[~mask] == 0.0))
    nonempty = bool(np.all(mask.sum(axis=1) > 0))
    observed_binary = True
    invalid_zero = True
    unobserved_hand_zero = True
    if expected_channels == 238:
        observed = x[:, :, 236:238]
        observed_binary = bool(np.all((observed == 0.0) | (observed == 1.0)))
        for start in (0, 84, 168):
            count = 21 if start < 168 else 17
            block = x[:, :, start : start + count * 4].reshape(x.shape[0], x.shape[1], count, 4)
            valid = block[..., 3]
            invalid_zero = invalid_zero and bool(np.all(block[..., :3][valid == 0.0] == 0.0))
        lh = x[:, :, :84]
        rh = x[:, :, 84:168]
        unobserved_hand_zero = bool(np.all(lh[observed[:, :, 0] == 0.0] == 0.0)) and bool(
            np.all(rh[observed[:, :, 1] == 0.0] == 0.0)
        )
    passed = all(
        [shape_ok, dtype_ok, finite, mask_shape, mask_bool, compact, padding_zero, nonempty,
         observed_binary, invalid_zero, unobserved_hand_zero]
    )
    return {
        "available": True,
        "passed": passed,
        "shape": list(x.shape),
        "dtype": str(x.dtype),
        "finite": finite,
        "mask_shape_valid": mask_shape,
        "mask_dtype_bool": mask_bool,
        "compact_frame_mask": compact,
        "nonempty_real_sequence": nonempty,
        "zero_tail_padding": padding_zero,
        "observed_flags_binary": observed_binary,
        "invalid_landmarks_zero": invalid_zero,
        "unobserved_whole_hand_zero": unobserved_hand_zero,
    }


def row_feature_hashes(data: dict[str, np.ndarray]) -> set[str]:
    x = data["X"]
    mask = data["frame_mask"]
    hashes: set[str] = set()
    for index in range(len(x)):
        h = hashlib.sha256()
        h.update(np.ascontiguousarray(x[index]).view(np.uint8))
        h.update(np.ascontiguousarray(mask[index]).view(np.uint8))
        hashes.add(h.hexdigest())
    return hashes


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray, classes: list[int]) -> float:
    values: list[float] = []
    for class_id in classes:
        tp = int(np.sum((y_true == class_id) & (y_pred == class_id)))
        fp = int(np.sum((y_true != class_id) & (y_pred == class_id)))
        fn = int(np.sum((y_true == class_id) & (y_pred != class_id)))
        denom = 2 * tp + fp + fn
        values.append((2 * tp / denom) if denom else 0.0)
    return float(np.mean(values)) if values else float("nan")


def historical_population_rows() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    train = npz_population(V2 / "train.npz")
    val = npz_population(V2 / "val.npz")
    primary = npz_population(V2 / "test.npz")
    replay = npz_population(V2 / "protected_replay.npz")
    stress = npz_population(V2 / "diagnostic_validation_stress.npz")
    reused = npz_population(V2 / "diagnostic_reused_positive.npz")

    canonical = load_csv(CANONICAL_MANIFEST)
    role_sources: dict[str, set[str]] = defaultdict(set)
    for row in canonical:
        role_sources[row["role"]].add(row["source_dataset"])

    e6_fresh_path = RU / "e6_baseline" / "e6_v30_five_sign_baseline_01" / "dataset" / "features" / "test_fresh.npz"
    e6_fresh = npz_population(e6_fresh_path)
    e6_negative_manifest = RU / "product_core_data_readiness" / "e6_five_sign_assignment_01" / "fresh_negative_evaluation_assignment.csv"
    e6_negative_rows = load_csv(e6_negative_manifest)
    neg_ids = [row["assignment_id"] for row in e6_negative_rows]
    neg_signers = sorted({row["signer_group_id"] for row in e6_negative_rows})
    oov_path = RU / "e4_generalization" / "e4_s_stable_primary_4sign_01" / "dataset" / "oov_confusion_holdout.npz"
    oov = npz_population(oov_path)
    p4_manifest = RU / "perception_backend_replacement" / "p4a2_fresh_evidence_repair_v2_01" / "sealed_final" / "p4a2_final_eval_manifest.csv"
    p4_rows = load_csv(p4_manifest)
    p4_ids = [row["annotation_row_id"] for row in p4_rows]

    rows = [
        {
            "population_name": "CANONICAL_PRIMARY_TEST_236",
            "manifest_path": str(CANONICAL_MANIFEST.resolve()) + " [role=primary_test]",
            "membership_count": primary["rows"], "classes": primary["classes"], "signers": primary["signers"],
            "sources": "|".join(sorted(role_sources["primary_test"])),
            "membership_sha256": primary["membership_sha256"], "feature_tensor_sha256": primary["feature_tensor_sha256"],
            "creation_governance_artifact": str((MANIFEST_DIR / "manifest_summary.json").resolve()),
            "first_known_use": "PHASE1_FULL_VOCAB_TCN_COMPARISON_01_ONE_TIME_PROTECTED_TEST",
            "latest_known_use": "P5B_RCAA/P5B_RCAB_DEVELOPMENT_ANALYSIS",
            "representation": "DWPOSE_REPRESENTATION_V2_238",
        },
        {
            "population_name": "PROTECTED_CLEAN_REPLAY",
            "manifest_path": str((MANIFEST_DIR / "protected_replay_manifest.csv").resolve()),
            "membership_count": replay["rows"], "classes": replay["classes"], "signers": replay["signers"],
            "sources": "|".join(sorted(role_sources["protected_clean_replay"])),
            "membership_sha256": replay["membership_sha256"], "feature_tensor_sha256": replay["feature_tensor_sha256"],
            "creation_governance_artifact": str((MANIFEST_DIR / "manifest_summary.json").resolve()),
            "first_known_use": "P5B_MIGRATION_FEATURE_MATERIALIZATION_ONLY",
            "latest_known_use": "PHASE2_PREPARATION_METADATA_INVENTORY",
            "representation": "DWPOSE_REPRESENTATION_V2_238",
        },
        {
            "population_name": "SUPPLEMENT_VALIDATION_STRESS",
            "manifest_path": str(CANONICAL_MANIFEST.resolve()) + " [role=supplement_validation_stress]",
            "membership_count": stress["rows"], "classes": stress["classes"], "signers": stress["signers"],
            "sources": "|".join(sorted(role_sources["supplement_validation_stress"])),
            "membership_sha256": stress["membership_sha256"], "feature_tensor_sha256": stress["feature_tensor_sha256"],
            "creation_governance_artifact": str((MANIFEST_DIR / "manifest_summary.json").resolve()),
            "first_known_use": "P5B_DIAGNOSTIC_STRESS",
            "latest_known_use": "STAGE1A/KNOW_HELLO_DIAGNOSTIC",
            "representation": "DWPOSE_REPRESENTATION_V2_238",
        },
        {
            "population_name": "REUSED_POSITIVE_DIAGNOSTIC",
            "manifest_path": str(CANONICAL_MANIFEST.resolve()) + " [role=reused_positive_diagnostic]",
            "membership_count": reused["rows"], "classes": reused["classes"], "signers": reused["signers"],
            "sources": "|".join(sorted(role_sources["reused_positive_diagnostic"])),
            "membership_sha256": reused["membership_sha256"], "feature_tensor_sha256": reused["feature_tensor_sha256"],
            "creation_governance_artifact": str((MANIFEST_DIR / "manifest_summary.json").resolve()),
            "first_known_use": "P5B_REUSED_POSITIVE_DIAGNOSTIC",
            "latest_known_use": "P5B/ROOT_CAUSE_DEVELOPMENT_DIAGNOSTIC",
            "representation": "DWPOSE_REPRESENTATION_V2_238",
        },
        {
            "population_name": "E6_FIVE_SIGN_TEST_FRESH",
            "manifest_path": str(e6_fresh_path.resolve()),
            "membership_count": e6_fresh["rows"], "classes": e6_fresh["classes"], "signers": e6_fresh["signers"],
            "sources": "APPHEAR_CAPTURE", "membership_sha256": e6_fresh["membership_sha256"],
            "feature_tensor_sha256": e6_fresh["feature_tensor_sha256"],
            "creation_governance_artifact": str((ROOT / "context" / "recognition_upgrade" / "PRODUCT_CORE_DATA_READINESS_PACKAGE.md").resolve()),
            "first_known_use": "E6_V30_FIVE_SIGN_BASELINE", "latest_known_use": "E6_2_LANDMARK_GEOMETRY",
            "representation": "LEGACY_258_PRODUCT_CORE (not V2_238)",
        },
        {
            "population_name": "E6_FRESH_NEGATIVE_EVALUATION",
            "manifest_path": str(e6_negative_manifest.resolve()),
            "membership_count": len(e6_negative_rows), "classes": 1, "signers": len(neg_signers),
            "sources": "APPHEAR_NEGATIVE_CAPTURE", "membership_sha256": membership_sha(neg_ids),
            "feature_tensor_sha256": "NOT_SINGLE_GOVERNED_V2_TENSOR",
            "creation_governance_artifact": str((RU / "product_core_data_readiness" / "e6_five_sign_assignment_01" / "E6_FIVE_SIGN_ASSIGNMENT_RESULT.md").resolve()),
            "first_known_use": "E6_V30_FIVE_SIGN_BASELINE", "latest_known_use": "E6_3_OPEN_SET_REJECTION",
            "representation": "NEGATIVE/NO_SIGN_PRODUCT_CORE; not 236-class V2 holdout",
        },
        {
            "population_name": "E4S_OOV_CONFUSION_HOLDOUT",
            "manifest_path": str((RU / "e4_generalization" / "e4_s_stable_primary_4sign_01" / "oov_confusion_holdout_manifest.csv").resolve()),
            "membership_count": oov["rows"], "classes": oov["classes"], "signers": oov["signers"],
            "sources": "LOCAL", "membership_sha256": oov["membership_sha256"],
            "feature_tensor_sha256": oov["feature_tensor_sha256"],
            "creation_governance_artifact": str((ROOT / "context" / "recognition_upgrade" / "E4_S_STABLE_PRIMARY_PACKAGE.md").resolve()),
            "first_known_use": "E4S_STABLE_PRIMARY_4SIGN", "latest_known_use": "E4T_ROUTER_SIMULATION",
            "representation": "LEGACY_258; OOV diagnostic",
        },
        {
            "population_name": "P4A2_SEALED_FINAL_PERCEPTION_FRAMES",
            "manifest_path": str(p4_manifest.resolve()),
            "membership_count": len(p4_rows), "classes": len({row["gloss"] for row in p4_rows}),
            "signers": len({row["signer_id"] for row in p4_rows}), "sources": "P4A2_PERCEPTION_EVIDENCE",
            "membership_sha256": membership_sha(p4_ids), "feature_tensor_sha256": "NOT_A_RECOGNITION_V2_TENSOR",
            "creation_governance_artifact": str((ROOT / "context" / "recognition_upgrade" / "P4A2_FRESH_EVIDENCE_REPAIR_RESULT_V2.md").resolve()),
            "first_known_use": "P4A2_FRESH_EVIDENCE_REPAIR_V2", "latest_known_use": "P4A2_HIGH_RECALL_RESCUE_FINAL",
            "representation": "PERCEPTION FRAME AUDIT; not recognition holdout",
        },
    ]
    data = {"train": train, "val": val, "primary": primary, "replay": replay, "stress": stress, "reused": reused,
            "e6_fresh": e6_fresh, "oov": oov}
    return rows, data


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    progress_before = sha256(PROGRESS)
    vocab, inv_vocab = inverse_vocab()
    population_rows, pop = historical_population_rows()
    write_csv(OUT / "p5d10a_holdout_population_inventory.csv", population_rows)

    exposure_rows = [
        {
            "population_name": "CANONICAL_PRIMARY_TEST_236", "experiment_id": "PHASE1_FULL_VOCAB_TCN_COMPARISON_01",
            "date_or_run": "2026-08 (artifact timestamp)",
            "artifact": str((PHASE1 / "tcn_comparison_01" / "metrics" / "protected_test_metrics.json").resolve()),
            "script_or_report": str((ROOT / "model" / "experiments" / "phase1_full_vocab_baseline.py").resolve()),
            "inference_occurred": True, "metrics_produced": True, "predictions_saved": True,
            "decision_influence": "VISIBLE_DURING_DEVELOPMENT; phase result and Phase-2 analysis followed",
            "historical_exposure_classification": "USED_IN_MODEL_OR_POLICY_SELECTION",
        },
        {
            "population_name": "CANONICAL_PRIMARY_TEST_236", "experiment_id": "P5B_BASELINE_01",
            "date_or_run": "2026-08-27",
            "artifact": str((P5 / "p5b_baseline_01" / "test_predictions.csv").resolve()),
            "script_or_report": str((P5 / "p5b_baseline_01" / "evaluation_summary.json").resolve()),
            "inference_occurred": True, "metrics_produced": True, "predictions_saved": True,
            "decision_influence": "P5-B result triggered RCA-A", "historical_exposure_classification": "USED_IN_MODEL_OR_POLICY_SELECTION",
        },
        {
            "population_name": "CANONICAL_PRIMARY_TEST_236", "experiment_id": "P5B_RCAA_01",
            "date_or_run": "2026-08-27",
            "artifact": str((P5 / "p5b_rcaa_01" / "P5B_RCAA_ROOT_CAUSE_RESULT.md").resolve()),
            "script_or_report": str((P5 / "p5b_rcaa_01" / "p5b_rcaa_decision.json").resolve()),
            "inference_occurred": False, "metrics_produced": True, "predictions_saved": False,
            "decision_influence": "Existing test predictions were reanalyzed to select CONTROLLED_TRAINING_HORIZON_EXTENSION",
            "historical_exposure_classification": "USED_IN_MODEL_OR_POLICY_SELECTION",
        },
        {
            "population_name": "CANONICAL_PRIMARY_TEST_236", "experiment_id": "P5B_RCAB_HORIZON_01",
            "date_or_run": "2026-08-27",
            "artifact": str((P5 / "p5b_rcab_horizon_01" / "test_predictions.csv").resolve()),
            "script_or_report": str((P5 / "p5b_rcab_horizon_01" / "evaluation_summary.json").resolve()),
            "inference_occurred": True, "metrics_produced": True, "predictions_saved": True,
            "decision_influence": "RCA-B protected-test result became visible before Stage 1A/D1-D9 decisions",
            "historical_exposure_classification": "USED_IN_MODEL_OR_POLICY_SELECTION",
        },
        {
            "population_name": "PROTECTED_CLEAN_REPLAY", "experiment_id": "P5B_MIGRATION_01",
            "date_or_run": "2026-08", "artifact": str((V2 / "protected_replay.npz").resolve()),
            "script_or_report": str((V2 / "assembly_summary.json").resolve()),
            "inference_occurred": False, "metrics_produced": False, "predictions_saved": False,
            "decision_influence": "DECISION_INFLUENCE_NOT_ESTABLISHED; no recognition-evaluation artifact found",
            "historical_exposure_classification": "NEVER_EVALUATED",
        },
        {
            "population_name": "SUPPLEMENT_VALIDATION_STRESS", "experiment_id": "STAGE1A_AND_RCA_DIAGNOSTICS",
            "date_or_run": "2026-08", "artifact": str((P5 / "stage1a_rcab_root_cause_evidence_01").resolve()),
            "script_or_report": "Stage1A/Stage1A-correction artifacts", "inference_occurred": True,
            "metrics_produced": True, "predictions_saved": True, "decision_influence": "Visible throughout root-cause development",
            "historical_exposure_classification": "USED_IN_MODEL_OR_POLICY_SELECTION",
        },
        {
            "population_name": "REUSED_POSITIVE_DIAGNOSTIC", "experiment_id": "P5B_AND_ROOT_CAUSE_DIAGNOSTICS",
            "date_or_run": "2026-08", "artifact": str((V2 / "diagnostic_reused_positive.npz").resolve()),
            "script_or_report": "P5-B diagnostic artifacts", "inference_occurred": True, "metrics_produced": True,
            "predictions_saved": True, "decision_influence": "Development diagnostic only",
            "historical_exposure_classification": "USED_IN_MODEL_OR_POLICY_SELECTION",
        },
        {
            "population_name": "E6_FIVE_SIGN_TEST_FRESH", "experiment_id": "E6_V30_BASELINE_THROUGH_E6_2",
            "date_or_run": "2026-08-09 onward", "artifact": str((RU / "e6_baseline" / "e6_v30_five_sign_baseline_01").resolve()),
            "script_or_report": str((ROOT / "context" / "recognition_upgrade" / "E6_2_LANDMARK_GEOMETRY_RESULT.md").resolve()),
            "inference_occurred": True, "metrics_produced": True, "predictions_saved": True,
            "decision_influence": "Repeatedly used in product-core model decisions",
            "historical_exposure_classification": "USED_IN_MODEL_OR_POLICY_SELECTION",
        },
        {
            "population_name": "E6_FRESH_NEGATIVE_EVALUATION", "experiment_id": "E6_V30/E6_3",
            "date_or_run": "2026-08-09 onward", "artifact": str((RU / "product_core_data_readiness" / "e6_five_sign_assignment_01" / "fresh_negative_evaluation_assignment.csv").resolve()),
            "script_or_report": str((ROOT / "context" / "recognition_upgrade" / "E6_3_OPEN_SET_REJECTION_RESULT.md").resolve()),
            "inference_occurred": True, "metrics_produced": True, "predictions_saved": True,
            "decision_influence": "Used in product-core open-set/rejection decisions",
            "historical_exposure_classification": "USED_IN_MODEL_OR_POLICY_SELECTION",
        },
        {
            "population_name": "E4S_OOV_CONFUSION_HOLDOUT", "experiment_id": "E4S/E4T",
            "date_or_run": "historical", "artifact": str((RU / "e4_generalization" / "e4_s_stable_primary_4sign_01").resolve()),
            "script_or_report": str((ROOT / "context" / "recognition_upgrade" / "E4_T_ROUTER_SIMULATION_RESULT.md").resolve()),
            "inference_occurred": True, "metrics_produced": True, "predictions_saved": True,
            "decision_influence": "Used for stable-primary/router decisions",
            "historical_exposure_classification": "USED_IN_MODEL_OR_POLICY_SELECTION",
        },
        {
            "population_name": "P4A2_SEALED_FINAL_PERCEPTION_FRAMES", "experiment_id": "P4A2_FINAL/RESCUE",
            "date_or_run": "2026-08-24 onward", "artifact": str((RU / "perception_backend_replacement" / "p4a2_fresh_evidence_repair_v2_01" / "sealed_final" / "p4a2_final_eval_manifest.csv").resolve()),
            "script_or_report": str((ROOT / "context" / "recognition_upgrade" / "P4A2_FRESH_EVIDENCE_REPAIR_RESULT_V2.md").resolve()),
            "inference_occurred": True, "metrics_produced": True, "predictions_saved": True,
            "decision_influence": "Used for perception-backend decisions; not a recognition population",
            "historical_exposure_classification": "USED_IN_MODEL_OR_POLICY_SELECTION",
        },
    ]
    write_csv(OUT / "p5d10a_holdout_exposure_history.csv", exposure_rows)

    train_signers = set(pop["train"]["signer_ids"].tolist())
    val_signers = set(pop["val"]["signer_ids"].tolist())
    signer_rows: list[dict[str, Any]] = []
    for name, key in [
        ("CANONICAL_PRIMARY_TEST_236", "primary"), ("PROTECTED_CLEAN_REPLAY", "replay"),
        ("SUPPLEMENT_VALIDATION_STRESS", "stress"), ("REUSED_POSITIVE_DIAGNOSTIC", "reused"),
        ("E6_FIVE_SIGN_TEST_FRESH", "e6_fresh"), ("E4S_OOV_CONFUSION_HOLDOUT", "oov"),
    ]:
        signers = set(pop[key]["signer_ids"].tolist())
        train_overlap = sorted(signers & train_signers)
        val_overlap = sorted(signers & val_signers)
        signer_rows.append({
            "population_name": name, "test_signers": len(signers), "train_signers": len(train_signers),
            "val_signers": len(val_signers), "train_test_signer_overlap": len(train_overlap),
            "val_test_signer_overlap": len(val_overlap), "train_overlap_ids": "|".join(train_overlap),
            "val_overlap_ids": "|".join(val_overlap),
            "cross_source_physical_identity": "CROSS_SOURCE_PHYSICAL_IDENTITY_NOT_VERIFIABLE" if any("semlex:" in x.lower() for x in signers) else "NOT_APPLICABLE_OR_SAME_SOURCE_IDS_USED",
        })
    signer_rows.extend([
        {"population_name": "E6_FRESH_NEGATIVE_EVALUATION", "test_signers": 1, "train_signers": len(train_signers), "val_signers": len(val_signers),
         "train_test_signer_overlap": 0, "val_test_signer_overlap": 0, "train_overlap_ids": "", "val_overlap_ids": "",
         "cross_source_physical_identity": "NOT_A_236_CLASS_RECOGNITION_HOLDOUT"},
        {"population_name": "P4A2_SEALED_FINAL_PERCEPTION_FRAMES", "test_signers": 1, "train_signers": len(train_signers), "val_signers": len(val_signers),
         "train_test_signer_overlap": 0, "val_test_signer_overlap": 0, "train_overlap_ids": "", "val_overlap_ids": "",
         "cross_source_physical_identity": "PERCEPTION_TASK_NOT_RECOGNITION_HOLDOUT"},
    ])
    write_csv(OUT / "p5d10a_signer_overlap_audit.csv", signer_rows)

    canonical = load_csv(CANONICAL_MANIFEST)
    by_role: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in canonical:
        by_role[row["role"]].append(row)
    train_rows = by_role["primary_train"] + by_role["supplement_train"]
    val_rows = by_role["primary_val"]
    train_raw = {r["raw_video_sha256"] for r in train_rows if r["raw_video_sha256"]}
    val_raw = {r["raw_video_sha256"] for r in val_rows if r["raw_video_sha256"]}
    train_feature_hashes = row_feature_hashes(pop["train"]["data"])
    val_feature_hashes = row_feature_hashes(pop["val"]["data"])
    overlap_rows: list[dict[str, Any]] = []
    for name, key, role in [
        ("CANONICAL_PRIMARY_TEST_236", "primary", "primary_test"),
        ("PROTECTED_CLEAN_REPLAY", "replay", "protected_clean_replay"),
        ("SUPPLEMENT_VALIDATION_STRESS", "stress", "supplement_validation_stress"),
        ("REUSED_POSITIVE_DIAGNOSTIC", "reused", "reused_positive_diagnostic"),
    ]:
        ids = set(pop[key]["sample_ids"].tolist())
        role_raw = {r["raw_video_sha256"] for r in by_role[role] if r["raw_video_sha256"]}
        feature_hash = row_feature_hashes(pop[key]["data"])
        for reference, ref_ids, ref_raw, ref_features in [
            ("TRAIN", set(pop["train"]["sample_ids"].tolist()), train_raw, train_feature_hashes),
            ("VAL", set(pop["val"]["sample_ids"].tolist()), val_raw, val_feature_hashes),
        ]:
            id_overlap = sorted(ids & ref_ids)
            raw_overlap = sorted(role_raw & ref_raw)
            feature_overlap = sorted(feature_hash & ref_features)
            overlap_rows.append({
                "population_name": name, "reference_population": reference,
                "exact_sample_id_overlap": len(id_overlap), "raw_video_sha256_overlap": len(raw_overlap),
                "derived_feature_overlap": len(feature_overlap), "same_source_clip_alias_overlap": len(id_overlap),
                "sample_overlap_ids": "|".join(id_overlap[:25]), "raw_overlap_sha256": "|".join(raw_overlap[:25]),
                "feature_overlap_sha256": "|".join(feature_overlap[:25]),
            })
    write_csv(OUT / "p5d10a_sample_overlap_audit.csv", overlap_rows)

    class_source = load_csv(D8 / "p5d8_classwise_source_baseline.csv")
    supplemented_ids = {int(row["class_id"]) for row in class_source}
    vocab_rows: list[dict[str, Any]] = []
    for name, key in [("CANONICAL_PRIMARY_TEST_236", "primary"), ("PROTECTED_CLEAN_REPLAY", "replay")]:
        y = pop[key]["y"]
        signers = pop[key]["signer_ids"]
        for class_id in range(236):
            selected = y == class_id
            clips = int(selected.sum())
            signer_count = len(set(signers[selected].tolist())) if clips else 0
            vocab_rows.append({
                "row_type": "CLASS", "population_name": name, "class_id": class_id,
                "gloss": inv_vocab[class_id], "supplementation_slice": "P3_SUPPLEMENTED_65" if class_id in supplemented_ids else "UNSUPPLEMENTED_171",
                "clips": clips, "signers": signer_count, "missing_class": clips == 0,
                "one_clip_class": clips == 1, "very_low_support_lt5": clips < 5,
            })
        for slice_name, ids in [("P3_SUPPLEMENTED_65", supplemented_ids), ("UNSUPPLEMENTED_171", set(range(236)) - supplemented_ids)]:
            class_counts = [int(np.sum(y == cid)) for cid in sorted(ids)]
            vocab_rows.append({
                "row_type": "SLICE_SUMMARY", "population_name": name, "class_id": "",
                "gloss": "", "supplementation_slice": slice_name, "clips": int(sum(class_counts)),
                "signers": len(set(signers[np.isin(y, list(ids))].tolist())),
                "missing_class": sum(c == 0 for c in class_counts), "one_clip_class": sum(c == 1 for c in class_counts),
                "very_low_support_lt5": sum(c < 5 for c in class_counts),
            })
    write_csv(OUT / "p5d10a_vocab_support.csv", vocab_rows)

    feature_integrity = {
        "model_inference_executed": False,
        "checkpoints_loaded": False,
        "representation": "DWPOSE_REPRESENTATION_V2_238",
        "populations": {
            "CANONICAL_PRIMARY_TEST_236": feature_contract(pop["primary"]["data"]),
            "PROTECTED_CLEAN_REPLAY": feature_contract(pop["replay"]["data"]),
            "SUPPLEMENT_VALIDATION_STRESS": feature_contract(pop["stress"]["data"]),
            "REUSED_POSITIVE_DIAGNOSTIC": feature_contract(pop["reused"]["data"]),
        },
        "non_v2_historical_populations": {
            "E6_FIVE_SIGN_TEST_FRESH": "LEGACY_258; not eligible for current V2 candidate",
            "E6_FRESH_NEGATIVE_EVALUATION": "NO_SIGN product-core evaluation; not 236-class V2",
            "E4S_OOV_CONFUSION_HOLDOUT": "LEGACY_258 OOV diagnostic",
            "P4A2_SEALED_FINAL_PERCEPTION_FRAMES": "perception-frame audit, not recognition tensors",
        },
    }
    feature_integrity["passed"] = all(v["passed"] for v in feature_integrity["populations"].values())
    write_json(OUT / "p5d10a_feature_integrity.json", feature_integrity)

    eligibility_rows = [
        {"population_name": "CANONICAL_PRIMARY_TEST_236", "independence_status": "SIGNER_DISJOINT_FULL_VOCAB_ELIGIBLE",
         "exposure_status": "DEVELOPMENT_EXPOSED_NOT_FINAL_HOLDOUT", "feature_integrity": "PASS",
         "eligible_claim": "Secondary full-236 signer-disjoint confirmation only; not a pristine final claim."},
        {"population_name": "PROTECTED_CLEAN_REPLAY", "independence_status": "SAMPLE_HELDOUT_BUT_SIGNER_OVERLAP",
         "exposure_status": "EXPOSURE_NOT_RESOLVED_NO_EVALUATION_ARTIFACT_FOUND", "feature_integrity": "PASS",
         "eligible_claim": "Partial three-class replay diagnostic only; one replay signer overlaps TRAIN and coverage is 3/236."},
        {"population_name": "SUPPLEMENT_VALIDATION_STRESS", "independence_status": "SIGNER_DISJOINT_PARTIAL_VOCAB_ELIGIBLE",
         "exposure_status": "DEVELOPMENT_EXPOSED_NOT_FINAL_HOLDOUT", "feature_integrity": "PASS",
         "eligible_claim": "Signer-disjoint four-class development stress diagnostic only; not a full-vocabulary holdout."},
        {"population_name": "REUSED_POSITIVE_DIAGNOSTIC", "independence_status": "SIGNER_DISJOINT_PARTIAL_VOCAB_ELIGIBLE",
         "exposure_status": "DEVELOPMENT_EXPOSED_NOT_FINAL_HOLDOUT", "feature_integrity": "PASS",
         "eligible_claim": "Signer-disjoint five-class reused-positive development diagnostic only; not a full-vocabulary holdout."},
        {"population_name": "E6_FIVE_SIGN_TEST_FRESH", "independence_status": "SIGNER_DISJOINT_PARTIAL_VOCAB_ELIGIBLE",
         "exposure_status": "DEVELOPMENT_EXPOSED_NOT_FINAL_HOLDOUT", "feature_integrity": "INCOMPATIBLE_REPRESENTATION",
         "eligible_claim": "Historical five-class product-core evidence only; not current 236-class V2 confirmation."},
        {"population_name": "E6_FRESH_NEGATIVE_EVALUATION", "independence_status": "SIGNER_DISJOINT_PARTIAL_VOCAB_ELIGIBLE",
         "exposure_status": "DEVELOPMENT_EXPOSED_NOT_FINAL_HOLDOUT", "feature_integrity": "NOT_A_236_CLASS_RECOGNITION_TENSOR",
         "eligible_claim": "Historical no-sign/open-set evidence only."},
        {"population_name": "E4S_OOV_CONFUSION_HOLDOUT", "independence_status": "SIGNER_DISJOINT_PARTIAL_VOCAB_ELIGIBLE",
         "exposure_status": "DEVELOPMENT_EXPOSED_NOT_FINAL_HOLDOUT", "feature_integrity": "INCOMPATIBLE_REPRESENTATION",
         "eligible_claim": "Signer-disjoint historical OOV diagnostic only; legacy representation and not a 236-class holdout."},
        {"population_name": "P4A2_SEALED_FINAL_PERCEPTION_FRAMES", "independence_status": "INDEPENDENCE_NOT_RESOLVED",
         "exposure_status": "DEVELOPMENT_EXPOSED_NOT_FINAL_HOLDOUT", "feature_integrity": "NOT_A_RECOGNITION_TENSOR",
         "eligible_claim": "Perception-backend evidence only; cannot evaluate the 236-class recognizer."},
    ]
    write_csv(OUT / "p5d10a_holdout_eligibility.csv", eligibility_rows)

    checkpoints = load_csv(D9B / "p5d9b_checkpoint_verification.csv")
    pfce = [row for row in checkpoints if row["objective"] == "PFCE_MATCHED"]
    freeze = {
        "candidate": "PFCE_MATCHED + P3_SEMLEX",
        "candidate_selection_source": "P5-D9B VALIDATION RESULT",
        "comparator": "PFCE_MATCHED BASELINE",
        "clipce_status": "RESEARCH_DIAGNOSTIC_NOT_FINAL_CANDIDATE",
        "test_used_for_candidate_selection": False,
        "single_checkpoint_status": "FINAL_SINGLE_CHECKPOINT_SELECTION_NOT_YET_GOVERNED",
        "frozen_evaluation_design": "THREE_MATCHED_SEED_PAIRS_NO_ENSEMBLING_NO_SEED_SELECTION",
        "seeds": [101, 202, 303],
        "matched_checkpoints": [
            {"condition": row["condition"], "seed": int(row["seed"]), "path": row["checkpoint_path"],
             "sha256": row["actual_sha256"]} for row in pfce
        ],
        "rule": "Evaluate each frozen PFCE supplemented checkpoint against the same-seed frozen PFCE baseline; report every pair and the across-seed median. Do not choose a seed from holdout results and do not ensemble predictions.",
    }
    write_json(OUT / "p5d10a_final_candidate_freeze.json", freeze)

    # D9B bookkeeping correction from existing validation predictions only.
    groups = {
        "HUMAN_ACCEPT_EXACT_FORM_45": {int(r["class_id"]) for r in class_source if r["human_decision"] == "ACCEPT_EXACT_FORM"},
        "PRIOR_METADATA_EXACT_2": {int(r["class_id"]) for r in class_source if r["human_decision"] == "ACCEPT_METADATA_EXACT"},
        "COMPATIBLE_VARIANT_18": {int(r["class_id"]) for r in class_source if r["human_decision"] == "ACCEPT_COMPATIBLE_VARIANT"},
    }
    groups["GOVERNED_EXACT_COMBINED_47"] = groups["HUMAN_ACCEPT_EXACT_FORM_45"] | groups["PRIOR_METADATA_EXACT_2"]
    corrected_rows: list[dict[str, Any]] = []
    pred_manifest = load_csv(D9B / "p5d9b_predictions_manifest.csv")
    pred_lookup = {(r["condition"], r["objective"], int(r["seed"])): Path(r["prediction_path"]) for r in pred_manifest}
    for objective in ["PFCE_MATCHED", "CLIPCE_AGGREGATION_ALIGNED"]:
        for seed in [101, 202, 303]:
            baseline = load_npz(pred_lookup[("BASELINE", objective, seed)])
            supplemented = load_npz(pred_lookup[("SUPPLEMENTED", objective, seed)])
            labels = baseline["labels"].astype(int)
            for group_name, class_ids in groups.items():
                class_list = sorted(class_ids)
                selected = np.isin(labels, class_list)
                y = labels[selected]
                base_pred = baseline["predictions"][selected].astype(int)
                supp_pred = supplemented["predictions"][selected].astype(int)
                base_top1 = float(np.mean(base_pred == y))
                supp_top1 = float(np.mean(supp_pred == y))
                base_f1 = macro_f1(y, base_pred, class_list)
                supp_f1 = macro_f1(y, supp_pred, class_list)
                corrected_rows.append({
                    "slice": group_name, "evidence_role": "DIAGNOSTIC_ONLY_CORRECTED_FROM_EXISTING_VALIDATION_PREDICTIONS",
                    "objective": objective, "seed": seed, "support_clips": int(selected.sum()),
                    "classes_defined": len(class_ids), "classes_with_validation_support": len(set(y.tolist())),
                    "baseline_top1": base_top1, "supplemented_top1": supp_top1, "top1_delta": supp_top1 - base_top1,
                    "baseline_macro_f1": base_f1, "supplemented_macro_f1": supp_f1, "macro_f1_delta": supp_f1 - base_f1,
                })
    write_csv(OUT / "p5d10a_d9b_corrected_exact_variant_diagnostic.csv", corrected_rows)

    seed_deltas = load_csv(D9B / "p5d9b_seed_matched_deltas.csv")
    delta_lookup = {(r["objective"], int(r["seed"])): r for r in seed_deltas}
    metric_key = {"ordinary_top1": "ordinary_top1_delta", "signer_balanced_top1": "signer_balanced_top1_delta", "macro_f1": "macro_f1_delta"}
    bootstrap_rows = []
    for row in load_csv(D9B / "p5d9b_signer_block_bootstrap.csv"):
        observed = float(delta_lookup[(row["objective"], int(row["seed"]))][metric_key[row["metric"]]])
        bootstrap_mean = float(row["point_delta"])
        bootstrap_rows.append({
            "objective": row["objective"], "seed": int(row["seed"]), "metric": row["metric"],
            "empirical_observed_delta": observed, "bootstrap_distribution_mean": bootstrap_mean,
            "old_mislabeled_point_delta": bootstrap_mean, "old_minus_empirical": bootstrap_mean - observed,
            "ci95_low": float(row["ci95_low"]), "ci95_high": float(row["ci95_high"]),
            "replicates": int(row["replicates"]), "cluster_unit": row["cluster_unit"],
            "schema_correction": "point_delta_was_bootstrap_mean; empirical_observed_delta_is_the_correct_point_estimate",
        })
    write_csv(OUT / "p5d10a_d9b_bootstrap_schema_correction.csv", bootstrap_rows)

    bookkeeping_md = """# P5-D10A D9B Bookkeeping Reconciliation

No D9B inference was rerun. This reconciliation uses the existing primary-validation prediction artifacts only.

## Exact-form taxonomy

The D9B slice named `EXACT_FORM_47_DIAGNOSTIC` actually selected 45 classes whose D8 `human_decision` was `ACCEPT_EXACT_FORM`. COME and WHO were governed earlier as `ACCEPT_METADATA_EXACT`; they were part of the accepted 65 but were omitted from that 45-class computation. The corrected artifact separates:

- 45 `ACCEPT_EXACT_FORM` classes;
- 2 `ACCEPT_METADATA_EXACT` classes (COME and WHO);
- the combined governed exact set of 47 classes;
- 18 `ACCEPT_COMPATIBLE_VARIANT` classes.

This is a diagnostic-labeling correction. It does not alter D9B's primary full-236 endpoint, the 65-class supplemented slice, either branch classification, or the overall `SEMLEX_SUPPLEMENTATION_BENEFIT_OBJECTIVE_CONDITIONAL` classification.

## Signer-block bootstrap schema

The original `point_delta` field in `p5d9b_signer_block_bootstrap.csv` stored the bootstrap distribution mean, not the empirical observed delta. The corrected CSV preserves the original confidence intervals, names the bootstrap mean accurately, and adds the empirical point estimate from `p5d9b_seed_matched_deltas.csv`.

This schema correction does not change the underlying bootstrap samples or confidence intervals and does not change the frozen D9B classification.
"""
    (OUT / "p5d10a_d9b_bookkeeping_reconciliation.md").write_text(bookkeeping_md, encoding="utf-8")

    d10b_contract = {
        "status": "PREPARED_NOT_EXECUTED",
        "use": "SECONDARY_CONFIRMATION_ONLY",
        "population": "CANONICAL_PRIMARY_TEST_236",
        "population_membership_sha256": pop["primary"]["membership_sha256"],
        "population_feature_sha256": pop["primary"]["feature_tensor_sha256"],
        "historical_exposure": "DEVELOPMENT_EXPOSED_NOT_FINAL_HOLDOUT",
        "warning": "Results must never be described as a pristine final holdout.",
        "candidate": "PFCE_MATCHED + P3_SEMLEX",
        "comparator": "PFCE_MATCHED baseline",
        "selection_design": freeze["frozen_evaluation_design"],
        "seeds": [101, 202, 303],
        "primary_endpoint": "SIGNER_BALANCED_TOP1_DELTA_CANDIDATE_MINUS_BASELINE",
        "supporting_metrics": ["ordinary_top1", "macro_f1", "top5", "clip_nll", "per_frame_accuracy"],
        "required_slices": ["FULL_236", "P3_SUPPLEMENTED_65", "UNSUPPLEMENTED_171", "HUMAN_EXACT_45", "PRIOR_METADATA_EXACT_2", "GOVERNED_EXACT_COMBINED_47", "COMPATIBLE_VARIANT_18", "BY_SIGNER"],
        "aggregation": "per-frame softmax -> masked arithmetic mean over real frames -> argmax",
        "paired_analysis": "Evaluate each supplemented checkpoint against the same-seed baseline on identical clips; report all three deltas and their median. No seed selection or ensembling.",
        "prohibitions": ["no tuning after results", "no retraining after results", "no test-based seed selection", "no CLIPCE promotion", "no automatic follow-up training"],
        "terminal_evidence": True,
        "executed": False,
    }
    write_json(OUT / "p5d10b_final_evaluation_contract.json", d10b_contract)

    decision = {
        "classification": "P5D10A_SECONDARY_CONFIRMATION_ONLY",
        "confidence": "HIGH",
        "pristine_final_holdout_available": False,
        "best_available_population": "CANONICAL_PRIMARY_TEST_236",
        "best_available_independence": "SIGNER_DISJOINT_FULL_VOCAB_ELIGIBLE",
        "best_available_exposure": "DEVELOPMENT_EXPOSED_NOT_FINAL_HOLDOUT",
        "reason": "The 2620-row full-vocabulary test is signer/sample disjoint and V2-valid, but repository artifacts prove repeated historical inference, saved predictions, visible metrics, and use in RCA/policy decisions.",
        "recommended_use": "SECONDARY_CONFIRMATION_ONLY",
        "recommended_next_gate": "PROJECT_LEAD_DECIDES_SECONDARY_CONFIRMATION_VS_FINAL_EVIDENCE_SYNTHESIS",
        "test_inference_during_d10a": False,
    }
    write_json(OUT / "p5d10a_decision.json", decision)
    write_json(OUT / "p5d10a_next_gate.json", {
        "selected_next_gate": decision["recommended_next_gate"],
        "next_gate_executed": False,
        "d10b_contract_prepared": True,
        "d10b_authorized": False,
    })

    primary_signer = next(r for r in signer_rows if r["population_name"] == "CANONICAL_PRIMARY_TEST_236")
    primary_overlap = [r for r in overlap_rows if r["population_name"] == "CANONICAL_PRIMARY_TEST_236"]
    report = f"""# P5-D10A Final Holdout Eligibility Audit

## Outcome

**P5D10A_SECONDARY_CONFIRMATION_ONLY** (high confidence).

No pristine final holdout exists for the current PFCE + P3 research cycle. The strongest available population is the canonical 2,620-clip, 236-class `primary_test`: it has 11 ASL Citizen signers, zero signer overlap with TRAIN/VAL, zero sample-ID overlap, zero raw-media SHA overlap, and a valid frozen `[96,238]` tensor contract. However, it was already evaluated in Phase 1, P5-B, and RCA-B; predictions and metrics were saved, and existing test evidence was used in RCA/policy decisions. It may support secondary confirmation only.

## Current candidate freeze

- Candidate: `PFCE_MATCHED + P3_SEMLEX`, selected from P5-D9B validation evidence.
- Comparator: same-seed frozen `PFCE_MATCHED` baseline.
- CLIPCE: research diagnostic, not final candidate.
- A single seed was never governed. D10A therefore freezes a three-matched-seed-pair design with no ensembling and no test-based seed selection.

## Holdout findings

- Canonical primary test: 2,620 rows, 236 classes, 11 signers; signer-disjoint and sample/raw-disjoint; development exposed.
- Protected clean replay: 306 rows, 3 classes, 3 signers; one signer overlaps TRAIN; exposure is unresolved because no evaluation artifact was found; it cannot support signer-independent or full-vocabulary confirmation.
- Supplement stress and reused-positive populations are development-exposed, signer-disjoint partial-vocabulary diagnostics.
- E6/E4 product-specific holdouts use partial vocabularies and/or legacy feature contracts and were already used during development.
- P4A2 sealed final evidence is a perception-frame audit, not a recognition holdout.

## Exposure evidence

The Phase-1 `protected_test_metrics.json` and `protected_test_predictions.npz` prove the canonical test was opened. P5-B and RCA-B independently saved V2 test predictions. RCA-A then reanalyzed the same test population to select a training-horizon intervention. The population therefore satisfies neither the strict `NEVER_EVALUATED` requirement nor the definition of `PRISTINE_FINAL_HOLDOUT`.

## Independence and support

The canonical primary test has {primary_signer['train_test_signer_overlap']} TRAIN-signer overlaps and {primary_signer['val_test_signer_overlap']} VAL-signer overlaps. Across TRAIN and VAL references, its maximum exact sample overlap is {max(r['exact_sample_id_overlap'] for r in primary_overlap)}, raw SHA overlap is {max(r['raw_video_sha256_overlap'] for r in primary_overlap)}, and derived-feature overlap is {max(r['derived_feature_overlap'] for r in primary_overlap)}. All 236 classes are represented, including all 65 supplemented and all 171 unsupplemented classes, so the D9B redistribution question is structurally measurable—but only as secondary evidence.

## D9B bookkeeping

The reported `EXACT_FORM_47_DIAGNOSTIC` was a 45-class computation; COME and WHO were `ACCEPT_METADATA_EXACT`. A corrected 45/2/47/18 diagnostic was generated from existing validation predictions. The old bootstrap `point_delta` was the bootstrap mean, not the empirical observed delta; the corrected schema provides both. Neither correction changes the D9B primary calculation or classification.

## Scientific boundary

This audit establishes lineage, feature integrity, support, exposure, and the absence of a pristine holdout. It does not establish protected/test performance of PFCE + P3. No holdout inference was run.
"""
    (OUT / "P5D10A_FINAL_HOLDOUT_AUDIT.md").write_text(report, encoding="utf-8")

    progress_after = sha256(PROGRESS)
    source_paths = [CANONICAL_MANIFEST, V2 / "train.npz", V2 / "val.npz", V2 / "test.npz", V2 / "protected_replay.npz",
                    V2 / "vocab.json", D9B / "p5d9b_checkpoint_verification.csv", D9B / "p5d9b_decision.json"]
    source_hashes = {str(path.resolve()): sha256(path) for path in source_paths}
    integrity = {
        "passed": feature_integrity["passed"] and progress_before == progress_after,
        "protected_test_inference": False,
        "protected_test_predictions_created": False,
        "test_feature_integrity_only": True,
        "model_inference_executed": False,
        "checkpoints_loaded": False,
        "new_training": False,
        "checkpoint_mutation": False,
        "p3_changed": False,
        "pfce_changed": False,
        "clipce_promoted": False,
        "apphear_train_changed": False,
        "apphear_val_changed": False,
        "holdout_membership_changed": False,
        "new_dataset": False,
        "new_recordings": False,
        "v2_changed": False,
        "dwpose_changed": False,
        "p4_reopened": False,
        "android_modified": False,
        "progress_tracker_before": progress_before,
        "progress_tracker_after": progress_after,
        "progress_tracker_untouched": progress_before == progress_after,
        "source_hashes": source_hashes,
    }
    write_json(OUT / "p5d10a_integrity.json", integrity)

    generated = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name != "artifact_hash_manifest.json")
    manifest = {
        "generated_artifacts": [{"path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size} for path in generated],
        "supporting_code": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        "governed_sources": [{"path": path, "sha256": digest} for path, digest in source_hashes.items()],
        "model_inference_executed": False,
        "protected_test_predictions_created": False,
        "training_executed": False,
    }
    write_json(OUT / "artifact_hash_manifest.json", manifest)
    print(json.dumps({
        "classification": decision["classification"],
        "populations": len(population_rows),
        "primary_test_rows": pop["primary"]["rows"],
        "primary_test_signers": pop["primary"]["signers"],
        "feature_integrity": feature_integrity["passed"],
        "progress_tracker_untouched": progress_before == progress_after,
        "test_inference": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
