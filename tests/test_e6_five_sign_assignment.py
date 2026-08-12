from pathlib import Path

from pipeline.rgb.e6_five_sign_assignment import _gate, _positive_role


def _row(
    assignment_id: str,
    *,
    kind: str = "positive",
    label: str = "GOOD",
    role: str = "train_positive",
    signer: str = "signer:train",
    digest: str = "A",
) -> dict[str, str]:
    return {
        "assignment_id": assignment_id,
        "sample_kind": kind,
        "canonical_label": label,
        "role": role,
        "signer_group_id": signer,
        "raw_video_path": str(Path("raw") / f"{assignment_id}.mp4"),
        "raw_video_sha256": digest,
    }


def test_positive_roles_preserve_freshness_semantics() -> None:
    assert _positive_role("train") == ("train_positive", "development")
    assert _positive_role("test_source_holdout") == (
        "test_positive_historical",
        "historical_reused",
    )
    assert _positive_role("test_fresh") == ("test_positive_fresh", "fresh")


def test_gate_rejects_signer_and_hash_role_leakage() -> None:
    rows = [
        _row("train", signer="same", digest="SAME"),
        _row("val", role="validation_positive", signer="same", digest="SAME"),
    ]
    result = _gate(rows)
    assert not result["passed"]
    assert result["signer_leakage"]
    assert result["hash_role_leakage"]


def test_gate_rejects_non_exact_vocabulary() -> None:
    rows = [_row("only-good")]
    result = _gate(rows)
    assert not result["passed"]
    assert "positive vocabulary does not exactly match approved five signs" in result["errors"]
