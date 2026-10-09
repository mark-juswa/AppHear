"""Meaningful geometry/missingness, causality, split and lineage regression checks."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from pipeline.fingerspelling.adapter import WIDTH, column_names, derive, phone_indices, subset
from pipeline.fingerspelling.sequence_manifest import (
    REPO,
    normalized,
    repeats,
    select_balanced,
    target_ids,
)
from pipeline.fingerspelling.sequence_package import validate, verify_source
from pipeline.perception_vnext.recognition_schema import RAW_SCHEMA, RawSequence


def raw_fixture() -> RawSequence:
    n = 4
    xy = np.zeros((n, 2, 21, 2), np.float32)
    xy[..., 0] = np.arange(21) * 2 + 50
    xy[..., 1] = np.arange(21) + 100
    xy[1] += 4
    return RawSequence(
        metadata={"schema": RAW_SCHEMA, "image_semantics": "UPRIGHT_UNMIRRORED_SOURCE_RGB"},
        frame_index=np.arange(n, dtype=np.int32),
        timestamp_ms=np.asarray([0, 100, 200, 400], np.float64),
        source_size=np.tile([200, 400], (n, 1)).astype(np.int32),
        hand_xy=xy,
        hand_proposal_support=np.full((n, 2, 21), 0.8, np.float32),
        hand_joint_valid=np.ones((n, 2, 21), bool),
        hand_presence=np.ones((n, 2), np.float32),
        hand_observed=np.ones((n, 2), bool),
        hand_proposal_present=np.ones((n, 2), bool),
        hand_roi_center_side=np.tile([50, 100, 80], (n, 2, 1)).astype(np.float32),
        hand_handedness_diagnostic=np.zeros((n, 2), np.float32),
        body_xy=np.full((n, 8, 2), np.nan, np.float32),
        body_support=np.full((n, 8), np.nan, np.float32),
        body_valid=np.zeros((n, 8), bool),
        body_available=np.zeros(n, bool),
    )


def test_translation_and_current_hand_scale_invariance() -> None:
    r = raw_fixture()
    f = derive(r)
    shifted = copy.deepcopy(r)
    shifted.hand_xy[:] += 20
    scaled = copy.deepcopy(r)
    scaled.hand_xy[:] *= 2
    scaled.source_size[:] *= 2
    columns = [i for i, s in enumerate(column_names()) if s.endswith(("local_x", "local_y"))]
    np.testing.assert_array_equal(f[:, columns], derive(shifted)[:, columns])
    np.testing.assert_array_equal(f[:, columns], derive(scaled)[:, columns])
    assert f.shape == (4, WIDTH) and np.isfinite(f).all()


def test_no_future_dependency_or_python_only_handedness() -> None:
    r = raw_fixture()
    f = derive(r)
    r.hand_xy[2:] += 500
    r.hand_handedness_diagnostic[:] = np.nan
    np.testing.assert_array_equal(f[:2], derive(r)[:2])


def test_missing_mask_overrides_android_zero_and_python_nan() -> None:
    r = raw_fixture()
    r.hand_observed[1] = False
    r.hand_joint_valid[1] = False
    r.hand_xy[1] = np.nan
    f = derive(r)
    r.hand_xy[1] = 0
    np.testing.assert_array_equal(f, derive(r))
    names = column_names()
    for slot in range(2):
        assert f[1, names.index(f"slot{slot}.joint0.source_valid")] == 0
        assert f[2, names.index(f"slot{slot}.motion_valid")] == 0  # no fill across missing neighbor


def test_partial_validity_invalid_scale_and_finite_support_masks() -> None:
    r = raw_fixture()
    r.hand_joint_valid[1, 0, 5] = False
    r.hand_xy[1, 0, 5] = np.nan
    r.hand_presence[1, 0] = np.nan
    r.hand_proposal_support[1, 0, 2] = np.inf
    r.hand_roi_center_side[1, 0] = np.nan
    f = derive(r)
    names = column_names()
    for key in [
        "scale_valid",
        "presence_valid",
        "roi_valid",
        "joint2.support_valid",
        "joint1.local_valid",
    ]:
        assert f[1, names.index(f"slot0.{key}")] == 0
    assert f[1, names.index("slot0.joint1.source_valid")] == 1
    assert np.isfinite(f).all()


def test_duplicates_retained_body_not_required() -> None:
    f = derive(raw_fixture())
    np.testing.assert_array_equal(f[:, 2:183], f[:, 183:364])
    assert np.count_nonzero(f[:, 404]) == 0
    assert f[:, column_names().index("slot0.scale_valid")].all()


def test_sparse_view_selects_only_real_timestamps_recomputes_dt_motion() -> None:
    r = raw_fixture()
    selected = phone_indices(r.timestamp_ms, 6.231166)
    np.testing.assert_array_equal(selected, [0, 2, 3])
    dense = derive(r)
    sparse = derive(subset(r, selected))
    assert sparse[1, 0] == np.float32(0.2) and dense[2, 0] == np.float32(0.1)
    assert sparse[1, column_names().index("slot0.wrist_dx")] == 0
    assert dense[2, column_names().index("slot0.wrist_dx")] != 0


@pytest.mark.parametrize("bad", ["HELLO1", "CAFÃƒÆ’Ã¢â‚¬Â°", "", "  ", "AB-BA"])
def test_transcript_rejections(bad: str) -> None:
    with pytest.raises(ValueError):
        normalized(bad)


def test_repeat_spaces_ctc_order_and_class_set() -> None:
    assert normalized("mm  ee") == "MM  EE"
    assert repeats("MM  EE") == 3
    assert target_ids("AZ ") == [0, 25, 26]
    assert len("MM  EE") + repeats("MM  EE") == 9


def test_changed_class_order_is_not_silently_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    from pipeline.fingerspelling.adapter import CONFIG

    monkeypatch.setitem(CONFIG, "target_order", ["OTHER"])
    with pytest.raises(ValueError, match="class order"):
        target_ids("ABC")


def test_raw_schema_and_chronology_guard() -> None:
    r = raw_fixture()
    r.metadata["schema"] = "wrong"
    with pytest.raises(ValueError):
        derive(r)
    r.metadata["schema"] = RAW_SCHEMA
    r.timestamp_ms[2] = r.timestamp_ms[1]
    with pytest.raises(ValueError):
        derive(r)


def test_source_hash_and_size_guard(tmp_path: Path) -> None:
    row = {"split_role": "PROTECTED_TEST", "official_split": "test"}
    with pytest.raises(ValueError, match="Protected"):
        verify_source(tmp_path / "sample.mp4", row)
    path = tmp_path / "sample.mp4"
    path.write_bytes(b"wrong")
    row.update(split_role="TRAIN", official_split="train", filename=path.name, file_size_bytes=6)
    with pytest.raises(ValueError, match="Size"):
        verify_source(path, row)


def test_round_robin_signer_diversity_and_no_duplicate_counting() -> None:
    rows = [
        {
            "signerId": signer,
            "clipFilename": f"{signer}{i}.mp4",
            "clipFileMd5": f"{signer}{i}",
            "normalized_transcript": "HELLO",
        }
        for signer in "ABC"
        for i in range(5)
    ]
    selected = select_balanced(rows, 6, set())
    assert {s: sum(r["signerId"] == s for r in selected) for s in "ABC"} == {"A": 2, "B": 2, "C": 2}
    assert selected == select_balanced(rows, 6, set())


def test_existing_package_keeps_pending_explicit() -> None:
    output = REPO / "datasets/fingerspelling/foundation_01"
    if not (output / "tranche_manifest.json").is_file():
        pytest.skip("Local pinned FSboard smoke not present")
    result = validate(output, output / "tranche_manifest.json")
    assert result["structural_pass"]
    assert result["validated_sequences"] >= 12
    if result["validated_sequences"] < 1280:
        assert not result["ready_to_train"]


@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("test_role", "SIGNER_ROLE"),
        ("wrong_signer", "OFFICIAL_METADATA"),
        ("fake_path", "OFFICIAL_SOURCE_LINKAGE"),
        ("ctc_length", "OFFICIAL_SOURCE_LINKAGE"),
        ("duplicate_id", "DUPLICATE_ID"),
    ],
)
def test_metadata_tampering_is_refused(tmp_path: Path, mutation: str, expected: str) -> None:
    output = REPO / "datasets/fingerspelling/foundation_01"
    if not (output / "tranche_manifest.json").is_file():
        pytest.skip("Local pinned FSboard metadata not present")
    m = json.loads((output / "tranche_manifest.json").read_text())
    r = m["samples"][0]
    if mutation == "test_role":
        r["split_role"] = "PROTECTED_TEST"
    if mutation == "wrong_signer":
        r["official_signer_id"] = "invented"
    if mutation == "fake_path":
        r["kaggle_relative_path"] = "daun_v3-test/forbidden.mp4"
    if mutation == "ctc_length":
        r["ctc_min_timesteps"] += 1
    if mutation == "duplicate_id":
        m["samples"][1]["sample_id"] = r["sample_id"]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(m))
    result = validate(tmp_path, path)
    assert not result["structural_pass"] and not result["ready_to_train"]
    assert any(expected in e for e in result["structural_errors"])


def test_acquisition_reuses_fixed_sources_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.fingerspelling import foundation

    output = REPO / "datasets/fingerspelling/foundation_01"
    if not (output / "tranche_manifest.json").is_file():
        pytest.skip("Local pinned FSboard smoke not present")
    m = json.loads((output / "tranche_manifest.json").read_text())
    receipts = [json.loads(p.read_text()) for p in (output / "features").glob("*.receipt.json")]
    from pipeline.fingerspelling.sequence_manifest import ADMISSION

    ids = {r["sample_id"] for r in receipts if (ADMISSION / "videos" / r["filename"]).is_file()}
    rows = [r for r in m["samples"] if r["sample_id"] in ids]

    def forbid(*args: object, **kwargs: object) -> None:
        raise AssertionError("Existing fixed source must never be downloaded again")

    monkeypatch.setattr(foundation.urllib.request, "urlopen", forbid)
    result = foundation.acquire(tmp_path, rows)
    assert len(result) == 12
    assert all(r["disposition"] == "REUSE_EXISTING_IMMUTABLE_SOURCE" for r in result)


@pytest.mark.parametrize(
    "field", ["raw_sha256", "source_sha256", "split_role", "candidate01_assets"]
)
def test_extraction_receipt_tampering_refused(tmp_path: Path, field: str) -> None:
    from pipeline.fingerspelling.sequence_package import verify_raw

    output = REPO / "datasets/fingerspelling/foundation_01"
    paths = list((output / "features").glob("*.receipt.json"))
    if not paths:
        pytest.skip("Local pinned FSboard raw smoke not present")
    feature = json.loads(paths[0].read_text())
    manifest = json.loads((output / "tranche_manifest.json").read_text())
    row = next(r for r in manifest["samples"] if r["sample_id"] == feature["sample_id"])
    original = json.loads((REPO / feature["raw_receipt_path"]).read_text())
    original[field] = {} if field == "candidate01_assets" else ""
    mutated = tmp_path / "receipt.json"
    mutated.write_text(json.dumps(original))
    with pytest.raises(ValueError):
        verify_raw(REPO / feature["raw_path"], mutated, row, feature["source_sha256"])
