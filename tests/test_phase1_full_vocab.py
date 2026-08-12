from pipeline.splits.phase1_full_vocab import audit_rows


def _row(
    sample_id: str,
    role: str,
    split: str,
    class_id: int,
    signer: str,
    digest: str,
    training: bool,
) -> dict[str, str]:
    return {
        "sample_id": sample_id,
        "role": role,
        "split": split,
        "class_id": str(class_id),
        "signer_group_id": signer,
        "raw_video_sha256": digest,
        "training_eligible": str(training).lower(),
    }


def test_audit_accepts_disjoint_primary_and_protected_replay() -> None:
    rows = [
        _row("train", "primary_train", "train", 0, "asl:P1", "A", True),
        _row("val", "primary_val", "val", 0, "asl:P2", "B", False),
        _row("test", "primary_test", "test", 0, "asl:P3", "C", False),
        _row("replay", "protected_clean_replay", "protected_replay", 0, "local:S1", "D", False),
    ]
    assert audit_rows(rows, expected_classes=1) == []


def test_audit_rejects_signer_leakage() -> None:
    rows = [
        _row("train", "primary_train", "train", 0, "asl:P1", "A", True),
        _row("val", "primary_val", "val", 0, "asl:P1", "B", False),
        _row("test", "primary_test", "test", 0, "asl:P3", "C", False),
    ]
    assert any("signer leakage" in error for error in audit_rows(rows, expected_classes=1))


def test_audit_rejects_protected_replay_training_hash() -> None:
    rows = [
        _row("train", "primary_train", "train", 0, "asl:P1", "A", True),
        _row("val", "primary_val", "val", 0, "asl:P2", "B", False),
        _row("test", "primary_test", "test", 0, "asl:P3", "C", False),
        _row("replay", "protected_clean_replay", "protected_replay", 0, "local:S1", "A", False),
    ]
    assert any("protected replay hash" in error for error in audit_rows(rows, expected_classes=1))
