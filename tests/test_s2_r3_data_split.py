"""S2-R3 signer-grouped data split: grouping logic, frozen-record integrity, exact rebuild."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from eval.runtime_diagnostics import s2_r3_data_split as split


def test_signer_grouping_keeps_each_signer_in_one_role_and_small_sources_fit() -> None:
    clips = {f"a{i}": {"signer": f"S{i % 10}", "source": "BIG"} for i in range(30)}
    clips.update({f"b{i}": {"signer": "SOLO", "source": "ONE"} for i in range(5)})
    clips.update({f"c{i}": {"signer": f"L{i % 2}", "source": "TWO"} for i in range(4)})
    roles = split.assign_positive_signers(
        clips, seed=5103, cal_fraction=0.2, min_signers_to_split=3
    )
    big = [roles[f"S{i}"] for i in range(10)]
    assert big.count("CAL") == 2 and big.count("FIT") == 8
    assert roles["SOLO"] == "FIT" and roles["L0"] == roles["L1"] == "FIT"
    assert roles == split.assign_positive_signers(clips, 5103, 0.2, 3)


def test_committed_split_is_signer_and_participant_disjoint() -> None:
    record = split.read_json(split.FREEZE_PATH)
    assert record["rules_sha256"] == split.sha256(split.CONFIG_PATH)
    summary = record["summary"]
    assert summary["fit_cal_signer_overlap"] == [] and summary["dev_signer_overlap"] == []
    fit = {p["signer"] for p in record["positives"] if p["role"] == "FIT"}
    cal = {p["signer"] for p in record["positives"] if p["role"] == "CAL"}
    assert fit and cal and not fit & cal
    roles: dict[str, set[str]] = {}
    for item in record["p1_negatives"] + record["n0_negatives"]:
        roles.setdefault(item["participant"], set()).add(item["role"])
    assert all(len(value) == 1 for value in roles.values())
    assert summary["negatives"]["HELD_OUT_EVAL"]["participants"] == ["P05", "P06"]
    assert summary["negatives"]["HELD_OUT_EVAL"]["p1_rows"] == 0


EVIDENCE_ROOT = os.environ.get("APPHEAR_EVIDENCE_ROOT")


@pytest.mark.skipif(not EVIDENCE_ROOT, reason="private research artifacts not configured")
def test_split_rebuilds_exactly_from_sources() -> None:
    rebuilt = split.build(Path(str(EVIDENCE_ROOT)), split.read_json(split.CONFIG_PATH))
    assert rebuilt == split.read_json(split.FREEZE_PATH)
