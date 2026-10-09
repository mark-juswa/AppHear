"""Focused guards for the existing-data finishing stage; no training/network here."""

from pathlib import Path

import pytest

from model import fingerspelling_1k_optimization as run
from model.fingerspelling_train4096 import score
from pipeline.fingerspelling.sequence_manifest import REPO


def test_fixed_configuration_preserves_current_contract() -> None:
    p = run.configuration()
    assert (p["train_count"], p["dev_count"], p["feature_width"]) == (1024, 256, 405)
    assert p["blank_penalty"] == 0.5 and p["beam_width"] == 10
    assert p["loss"] == "UNCHANGED_CTC_MEAN_RAW_SEQUENCE_LOSS"


def test_learning_rate_finishes_at_lower_rate_without_a_sweep() -> None:
    assert [run.lr(e) for e in (0, 2, 5, 6, 14)] == [0.0001] * 3 + [0.00005] * 2


@pytest.mark.parametrize(
    "name",
    [
        "fingerspelling_ctc_baseline_02",
        "fingerspelling_residual_visual_01",
        "fingerspelling_train4096_01",
    ],
)
def test_previous_runs_cannot_be_overwritten(name: str) -> None:
    with pytest.raises(ValueError, match="Separate owned"):
        run.safe_run(REPO / "runs" / name)


def test_outside_run_directory_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Separate owned"):
        run.safe_run(tmp_path)


def reports(prediction: str) -> dict:
    rows = [
        {"sample_id": str(i), "signer_id": str(i), "reference": "AMY", "prediction": prediction}
        for i in range(5)
    ]
    return {view: {"metrics": score(rows)} for view in ("native", "phone")}


def test_gate_requires_discrimination_not_more_emission() -> None:
    assert not run.gate_result(reports("SAM"), reports("AM"))["meaningful_improvement_supported"]


def test_gate_recognizes_broad_correct_character_improvement() -> None:
    assert run.gate_result(reports("AMY"), reports("ANN"))["meaningful_improvement_supported"]


def test_gate_does_not_hide_sparse_regression() -> None:
    base, candidate = reports("ANN"), reports("AMY")
    candidate["phone"] = reports("")["phone"]
    assert not run.gate_result(candidate, base)["meaningful_improvement_supported"]


def test_failed_gate_refuses_training_before_loading_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run, "safe_run", lambda _: None)
    monkeypatch.setattr(
        run.b2,
        "dataset",
        lambda _: [{"split_role": "TRAIN"}] * 1024 + [{"split_role": "DEV"}] * 256,
    )
    monkeypatch.setattr(run, "run_identity", lambda _: {"fixture_identity": True})
    run.write_json_atomic(tmp_path / "run_identity.json", {"fixture_identity": True})
    run.write_json_atomic(
        tmp_path / "gate_result.json",
        {"vs_current_residual": {"meaningful_improvement_supported": False}},
    )
    with pytest.raises(ValueError, match="Gate did not justify further finishing"):
        run.engine(tmp_path, object(), gate=False)
