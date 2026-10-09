"""Offline governed extension checks; no RGB acquisition, extraction or inference."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from tools.fingerspelling.fsboard_expansion_plan import (
    digest,
    documents,
    foundation,
    validate_documents,
)


@pytest.fixture(scope="module")
def selected() -> dict[str, dict[str, Any]]:
    return documents()


def test_fixed_counts_subset_unchanged_rows_and_all_signers(selected: dict[str, Any]) -> None:
    result = validate_documents(selected)
    assert result["structural_pass"]
    assert (
        result["train_sequences"],
        result["retained_train"],
        result["new_train"],
        result["dev_b"],
    ) == (4096, 1024, 3072, 256)
    original = [r for r in foundation()["samples"] if r["split_role"] == "TRAIN"]
    expanded = selected["train4096_manifest.json"]["samples"]
    assert expanded[:1024] == original
    assert {r["sample_id"] for r in original} < {r["sample_id"] for r in expanded}


def test_reselection_is_byte_identity_and_dev_a_unchanged(selected: dict[str, Any]) -> None:
    again = documents()
    assert {name: digest(value) for name, value in selected.items()} == {
        name: digest(value) for name, value in again.items()
    }
    a = [r["sample_id"] for r in foundation()["samples"] if r["split_role"] == "DEV"]
    assert selected["dev_a_reference.json"]["sample_ids"] == a
    assert selected["dev_b_policy.json"]["permitted_use"] == "FINAL_CONFIRMATION_ONLY"


@pytest.mark.parametrize(
    "mutation",
    [
        "old_row",
        "test_role",
        "signer",
        "source_path",
        "repeat_count",
        "dev_a_copy",
        "duplicate",
        "dev_b_tuning",
    ],
)
def test_governance_tampering_refused(selected: dict[str, Any], mutation: str) -> None:
    changed = copy.deepcopy(selected)
    train = changed["train4096_manifest.json"]["samples"]
    extra = changed["train_additions/tranche_manifest.json"]["samples"]
    b = changed["dev_b/tranche_manifest.json"]["samples"]
    if mutation == "old_row":
        train[0]["transcript"] = "FAKE"
    elif mutation == "test_role":
        b[0]["split_role"] = "PROTECTED_TEST"
    elif mutation == "signer":
        b[0]["official_signer_id"] = train[0]["official_signer_id"]
    elif mutation == "source_path":
        b[0]["kaggle_relative_path"] = "test/forbidden.mp4"
    elif mutation == "repeat_count":
        b[0]["ctc_min_timesteps"] += 1
    elif mutation == "dev_a_copy":
        b[0] = next(r for r in foundation()["samples"] if r["split_role"] == "DEV")
    elif mutation == "duplicate":
        train[-1] = train[-2]
        extra[-1] = train[-1]
    else:
        changed["dev_b_policy.json"]["forbidden_uses"] = []
    with pytest.raises(ValueError):
        validate_documents(changed)
