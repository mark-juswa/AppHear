import numpy as np
import pytest

from pipeline.rgb.phase2_prepare import classify_sign, verify_prediction_alignment


def test_prediction_alignment_accepts_exact_lineage() -> None:
    labels = np.asarray([1, 2], dtype=np.int32)
    signers = np.asarray(["A", "B"])
    verify_prediction_alignment(labels, signers, labels.copy(), signers.copy())


def test_prediction_alignment_rejects_reordered_rows() -> None:
    labels = np.asarray([1, 2], dtype=np.int32)
    signers = np.asarray(["A", "B"])
    with pytest.raises(ValueError, match="labels"):
        verify_prediction_alignment(labels, signers, labels[::-1], signers)


def test_classification_separates_verified_and_hypothetical_labels() -> None:
    categories, hypotheses = classify_sign(
        label="HAVE",
        support=10,
        recall=0.0,
        f1=0.0,
        top5_recall=0.8,
        dominant_confusion_share=0.8,
        train_signers=30,
    )
    assert "zero_very_low_recall" in categories
    assert "confusion_heavy" in categories
    assert "appearance_evidence_may_help" in hypotheses


def test_variant_review_flag_is_not_a_verified_category() -> None:
    categories, hypotheses = classify_sign(
        label="MONEY1",
        support=11,
        recall=0.1,
        f1=0.1,
        top5_recall=0.3,
        dominant_confusion_share=0.5,
        train_signers=30,
    )
    assert "dataset_or_variant_review_required" not in categories
    assert "dataset_or_variant_review_required" in hypotheses
