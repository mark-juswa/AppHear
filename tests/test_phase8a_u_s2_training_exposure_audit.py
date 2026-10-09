from __future__ import annotations

import ast
import inspect

import numpy as np

import eval.runtime_diagnostics.phase8a_u_s2_training_exposure_audit as phase8au


def test_frozen_integrity_and_population() -> None:
    audit = phase8au.integrity_audit()
    assert audit["fit_clips"] == 71
    assert audit["cal_clips"] == 18
    assert audit["fit_sparse_views"] == 213
    assert audit["cal_sparse_views"] == 54
    assert audit["s2_checkpoint_sha256"] == phase8au.EXPECTED_S2_SHA


def test_frozen_temporal_label_boundaries() -> None:
    timestamps = np.asarray([0, 899, 900, 1000, 1100, 1899, 1900, 2000, 2100, 2101], np.float64)
    labels = phase8au.temporal_labels(timestamps, 1000.0, 2000.0)
    assert labels.tolist() == [0, 0, -1, -1, -1, 1, -1, -1, -1, 2]


def test_transition_profile_uses_real_timestamps() -> None:
    profile = phase8au.transition_profile([0.0, 200.0, 500.0, 800.0], [1, 1, 2, 2])
    assert profile["post_observations"] == 2
    assert profile["post_supervised_span_ms"] == 300.0
    assert profile["has_config01_confirmation_timespan"]


def test_exact_fit_cal_exposure_and_training_label_reproduction() -> None:
    rows = phase8au.build_exposure_rows()
    assert len(rows) == 89
    assert sum(row["partition"] == "FIT" for row in rows) == 71
    assert sum(row["partition"] == "CAL" for row in rows) == 18
    assert all(list(row["views"]) == list(phase8au.VIEW_IDS) for row in rows)
    fit = phase8au.summarize_exposure(rows, "FIT")
    assert fit["sparse_label_counts"]["PRE_IDLE"] == 1469
    assert fit["sparse_label_counts"]["ACTIVE_SIGN"] == 995
    assert fit["sparse_label_counts"]["POST_RECOVERY"] == 1752
    assert fit["source_breakdown"]["LOCAL"]["clips"] == 10
    assert fit["source_breakdown"]["APPHEAR_CAPTURE"]["clips"] == 9


def test_checkpoint_audit_detects_sequence_global_alignment_gap() -> None:
    audit = phase8au.checkpoint_selection_audit()
    assert audit["best_epoch"] == 17
    assert audit["selection_is_sequence_global"]
    assert not audit["causal_event_completion_metric_in_selection"]
    assert audit["selected_epoch_global_reference"]["event_emission_rate"] == 1.0
    assert np.isclose(
        audit["same_checkpoint_config01_causal_reference"]["event_emission_rate"],
        50 / 54,
    )


def test_unused_data_preserves_dev_signers() -> None:
    audit = phase8au.unused_data_audit()
    assert audit["unused_clips"] == 3806
    assert audit["unused_by_source"] == {
        "APPHEAR_CAPTURE": 285,
        "ASL_CITIZEN": 3219,
        "LOCAL": 302,
    }
    assert audit["independent_unreserved_apphear_local_signers"] == []
    assert audit["phase5_1t_1_human_labels_outside_selected_120"]["usable"] == 19


def test_terminal_control_discrepancy_is_exact_and_causal() -> None:
    audit = phase8au.terminal_control_discrepancy()
    assert audit["successful_event_views"] == 97
    assert audit["successful_terminal_controls"] == 94
    assert len(audit["omitted_views"]) == 3
    assert all(row["commit_minus_human_end_ms"] < 0.0 for row in audit["omitted_views"])
    assert not audit["material_effect_on_phase8a_t_conclusion"]


def test_no_training_inference_recognition_phone_or_android_calls() -> None:
    tree = ast.parse(inspect.getsource(phase8au))
    banned = {"fit", "predict", "load_model", "train", "evaluate_protected_test"}
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    assert not (called & banned)


def test_rows_are_deterministically_ordered() -> None:
    rows = phase8au.build_exposure_rows()
    assert [row["sample_id"] for row in rows] == sorted(row["sample_id"] for row in rows)
