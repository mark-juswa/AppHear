"""S2-R3 frozen context suite: pure logic, freeze integrity, and optional full reproduction.

The full reproduction needs the private research artifacts; set APPHEAR_EVIDENCE_ROOT to the
research checkout (for example F:/ASL DATASET/5. Apphear3) to run it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from eval.runtime_diagnostics import s2_r3_context_suite as suite


class _FixedPackage:
    """Duck-typed stand-in exposing only `probabilities`, returning a fixed state stream."""

    def __init__(self, states: list[int]) -> None:
        self.states = states

    def probabilities(self, features: np.ndarray) -> np.ndarray:
        assert len(features) == len(self.states)
        return np.eye(3)[self.states]


def _rows(n: int) -> np.ndarray:
    return np.zeros((n, suite.FEATURE_WIDTH), np.float32)


def test_score_view_scores_only_target_rows_after_history() -> None:
    history, target = _rows(3), _rows(4)
    labels = np.asarray([0, 1, 1, 2])
    # history predicted ACTIVE must not count; target: PRE, ACTIVE, PRE, ACTIVE
    package: Any = _FixedPackage([1, 1, 1, 0, 1, 0, 1])
    result = suite.score_view(package, history, target, labels)
    assert result == {"acquired": 1.0, "active_recall": 0.5, "false_active": 0.5}


def test_score_view_ignores_ignore_labels_in_false_active() -> None:
    package: Any = _FixedPackage([1, 1, 0])
    result = suite.score_view(package, _rows(0), _rows(3), np.asarray([-1, 1, 0]))
    assert result["false_active"] == 0.0
    assert result["acquired"] == 1.0


def test_summarize_counts_and_means() -> None:
    summary = suite.summarize(
        [
            {"acquired": 1.0, "active_recall": 1.0, "false_active": 0.0},
            {"acquired": 0.0, "active_recall": 0.0, "false_active": 0.2},
        ]
    )
    assert summary["n"] == 2 and summary["acquired_count"] == 1
    assert summary["acquired_fraction"] == 0.5
    assert summary["false_active_mean"] == pytest.approx(0.1)


def test_gate_uses_reference_relative_threshold_and_both_operators() -> None:
    config = {
        "gate": [
            {"id": "A", "metric": "x.y", "op": ">=", "value": 0.5},
            {"id": "B", "metric": "x.z", "op": "<=", "value": 3},
            {"id": "C", "metric": "x.y", "op": ">=", "value_from_reference_minus": 0.05},
        ]
    }
    gate = suite.apply_gate(config, {"x": {"y": 0.6, "z": 4}}, {"x": {"y": 0.7, "z": 0}})
    by_id = {line["id"]: line for line in gate["lines"]}
    assert by_id["A"]["pass"] and not by_id["B"]["pass"]
    assert by_id["C"]["threshold"] == pytest.approx(0.65) and not by_id["C"]["pass"]
    assert gate["pass"] is False


def test_unimplemented_contract_is_refused() -> None:
    with pytest.raises(ValueError, match="S2R3_CONTRACT_NOT_IMPLEMENTED:v2"):
        suite.features_for_raw(None, "v2")  # type: ignore[arg-type]


@pytest.mark.parametrize("suite_id", sorted(suite.SUITES))
def test_committed_freeze_matches_config_and_resolves_every_gate_metric(suite_id: str) -> None:
    config_path, freeze_path = suite.SUITES[suite_id]
    frozen = suite.read_json(freeze_path)
    config = suite.read_json(config_path)
    assert frozen["config_sha256"] == suite.sha256(config_path)
    for line in config["gate"]:
        assert not np.isnan(suite.metric_value(frozen["reference_results"], line["metric"]))
    checks = frozen["reproduction_checks"]
    assert checks["dev_v1_recomputed_vs_stored_max_abs"] == 0.0
    for session in checks["sessions"].values():
        assert session["v1_features_vs_android_max_abs"] == 0.0
        assert session["probabilities_vs_android_max_abs"] < 1e-4
        assert session["replayed_events_equal_recorded"] is True


def test_suite_02_reproduces_every_suite_01_measurement() -> None:
    first = suite.read_json(suite.SUITES["01"][1])["reference_results"]
    second = suite.read_json(suite.SUITES["02"][1])["reference_results"]
    for condition, values in first["tier1"].items():
        assert second["tier1"][condition] == values
    for key, value in first["tier2"]["total"].items():
        assert second["tier2"]["total"][key] == value


def test_suite_02_reference_baselines_for_new_conditions() -> None:
    """Held-out decomposition numbers recorded in the S2-R3 readiness report."""
    results = suite.read_json(suite.SUITES["02"][1])["reference_results"]
    tier1, tier2 = results["tier1"], results["tier2"]
    holds = [tier1[f"HOLD_{g:02d}"]["acquired_count"] for g in (0, 3, 6, 12, 24)]
    assert holds == [63, 58, 38, 3, 0] and tier1["HOLD_12"]["n"] == 66
    assert tier1["NONSIGN_MOVEMENT_30"]["active_recall_mean"] == pytest.approx(0.914, abs=5e-4)
    assert tier1["NO_SIGN_IDLE_30"]["active_recall_mean"] == pytest.approx(0.431, abs=5e-4)
    assert tier2["continuous"]["genuine_signs"] == 11
    assert tier2["continuous"]["signs_with_distinct_event"] == 2
    assert tier2["total"]["merged_events"] == 0


def test_suite_03_reproduces_suite_02_and_records_heldout_negative_baseline() -> None:
    second = suite.read_json(suite.SUITES["02"][1])["reference_results"]
    third = suite.read_json(suite.SUITES["03"][1])["reference_results"]
    assert third["tier1"] == second["tier1"] and third["tier2"] == second["tier2"]
    heldout = third["tier1b"]
    assert sorted(heldout["participants"]) == ["P05", "P06"]
    assert heldout["total"]["scored_observations"] == 1227
    assert heldout["total"]["active_observations"] == 7
    assert heldout["total"]["events"] == 1


def test_suite_04_reproduces_suite_03_and_records_ipn_hands_visible_baseline() -> None:
    third = suite.read_json(suite.SUITES["03"][1])["reference_results"]
    fourth_record = suite.read_json(suite.SUITES["04"][1])
    fourth = fourth_record["reference_results"]
    for tier in ("tier1", "tier2", "tier1b"):
        assert fourth[tier] == third[tier]
    ipn = fourth["tier1c"]["total"]
    assert ipn["subjects"] == ["4CM11_2", "4CM11_24"]
    assert ipn["nog_observations"] == 1329
    assert ipn["nog_events"] == 0
    config = suite.read_json(suite.SUITES["04"][0])["tier1c_ipn_hands_visible"]
    assert config["roles"] == ["HELD_OUT_EVAL"]
    identity = fourth_record["input_identity"]
    assert identity["ipn_manifest_sha256"] == config["manifest_sha256"]
    assert identity["ipn_subject_split_sha256"] == config["subject_split_sha256"]
    assert suite.sha256(suite.ROOT / config["subject_split"]) == config["subject_split_sha256"]


def test_match_signs_credits_a_merged_event_to_one_sign_only() -> None:
    positives = [
        {"name": "A", "first": 2, "last": 4, "active_rows": [2, 3, 4]},
        {"name": "B", "first": 6, "last": 8, "active_rows": [6, 7, 8]},
        {"name": "C", "first": 12, "last": 13, "active_rows": [12, 13]},
    ]
    merged = {"logical_active_start_index": 3, "logical_active_end_index": 7}
    states = np.asarray([0, 0, 1, 1, 1, 0, 1, 1, 1, 0, 0, 0, 0, 0])
    signs, used, merged_count = suite.match_signs(positives, [merged], states)
    assert [sign["with_event"] for sign in signs] == [True, True, False]
    assert [sign["with_distinct_event"] for sign in signs] == [True, False, False]
    assert [sign["acquired"] for sign in signs] == [True, True, False]
    assert used == {0} and merged_count == 1


def test_gate_treats_missing_measurement_as_failure() -> None:
    config = {"gate": [{"id": "D", "metric": "x.dwell", "op": "<=", "value": 1500.0}]}
    gate = suite.apply_gate(config, {"x": {"dwell": None}}, {"x": {"dwell": 10.0}})
    assert gate["pass"] is False


def test_frozen_reference_equals_verification_report_baselines() -> None:
    """Numbers from docs/audit/S2_HISTORY_DEPENDENCE_VERIFICATION_2026-10-16.md."""
    results = suite.read_json(suite.FREEZE_PATH)["reference_results"]
    tier1, tier2 = results["tier1"], results["tier2"]
    assert (tier1["NONE"]["acquired_count"], tier1["NONE"]["n"]) == (68, 69)
    assert tier1["NONE"]["active_recall_mean"] == pytest.approx(0.869, abs=5e-4)
    assert tier1["NONE"]["false_active_mean"] == pytest.approx(0.081, abs=5e-4)
    assert tier1["POST_PHONE_15"]["acquired_count"] == 10
    assert tier1["REST_PHONE_60"]["acquired_count"] == 69
    assert (
        tier1["PREV_SIGN_SAME_SIGNER"]["acquired_count"],
        tier1["PREV_SIGN_SAME_SIGNER"]["n"],
    ) == (
        51,
        66,
    )
    assert (tier1["DIRECT_PLUS_6_POST"]["acquired_count"], tier1["DIRECT_PLUS_6_POST"]["n"]) == (
        42,
        63,
    )
    assert tier2["total"]["acquired"] == 12
    assert tier2["total"]["signs_with_event"] == 11
    assert tier2["total"]["events"] == 28
    assert tier2["total"]["events_inside_nonsign"] == 5
    assert tier2["total"]["nonsign_active_observations"] == 64
    assert tier2["continuous"]["post_dwell_median_ms"] == pytest.approx(6079, abs=1)


EVIDENCE_ROOT = os.environ.get("APPHEAR_EVIDENCE_ROOT")


@pytest.mark.skipif(not EVIDENCE_ROOT, reason="private research artifacts not configured")
@pytest.mark.parametrize("suite_id", sorted(suite.SUITES))
def test_reference_package_reproduces_frozen_results_from_source_inputs(suite_id: str) -> None:
    root = Path(str(EVIDENCE_ROOT))
    config_path, freeze_path = suite.SUITES[suite_id]
    config = suite.read_json(config_path)
    spec = config["reference_package"]
    package = suite.load_package(
        spec["package_id"],
        spec["contract"],
        root / spec["keras"],
        root / spec["normalization"],
        spec["keras_sha256"],
        spec["normalization_sha256"],
    )
    results, _ = suite.run_suite(root, config, package)
    frozen = suite.read_json(freeze_path)["reference_results"]
    for line in config["gate"]:
        assert suite.metric_value(results, line["metric"]) == pytest.approx(
            suite.metric_value(frozen, line["metric"]), abs=1e-9
        )
