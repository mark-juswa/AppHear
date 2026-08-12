from pipeline.rgb.post_c0_baseline_eligibility import _positive_eligibility


def test_baseline_used_positive_is_diagnostic_only() -> None:
    eligibility, _ = _positive_eligibility(True, set())
    assert eligibility == "reused_e6_diagnostic_only"


def test_other_experiment_usage_blocks_clean_candidate() -> None:
    eligibility, _ = _positive_eligibility(False, {"experiment.csv"})
    assert eligibility == "reused_other_experiment_diagnostic_only"


def test_unused_positive_is_clean_isolated_candidate() -> None:
    eligibility, _ = _positive_eligibility(False, set())
    assert eligibility == "clean_isolated_replay_candidate"
