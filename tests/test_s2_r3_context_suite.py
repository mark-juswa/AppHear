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


def test_committed_freeze_matches_config_and_resolves_every_gate_metric() -> None:
    frozen = suite.read_json(suite.FREEZE_PATH)
    config = suite.read_json(suite.CONFIG_PATH)
    assert frozen["config_sha256"] == suite.sha256(suite.CONFIG_PATH)
    for line in config["gate"]:
        suite.metric_value(frozen["reference_results"], line["metric"])
    checks = frozen["reproduction_checks"]
    assert checks["dev_v1_recomputed_vs_stored_max_abs"] == 0.0
    for session in checks["sessions"].values():
        assert session["v1_features_vs_android_max_abs"] == 0.0
        assert session["probabilities_vs_android_max_abs"] < 1e-4
        assert session["replayed_events_equal_recorded"] is True


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
def test_reference_package_reproduces_frozen_results_from_source_inputs() -> None:
    root = Path(str(EVIDENCE_ROOT))
    config = suite.read_json(suite.CONFIG_PATH)
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
    frozen = suite.read_json(suite.FREEZE_PATH)["reference_results"]
    for line in config["gate"]:
        assert suite.metric_value(results, line["metric"]) == pytest.approx(
            suite.metric_value(frozen, line["metric"]), abs=1e-9
        )
