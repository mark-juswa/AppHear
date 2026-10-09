"""Synthetic governance fixtures only; no signer, video decode, or perception inference."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from pipeline.fingerspelling import validate as az
from pipeline.perception_vnext.recognition_schema import RAW_SCHEMA, RawSequence, save_raw_sequence


def package_fixture(tmp_path: Path, role: str = "TRAIN") -> tuple[Path, dict[str, Any]]:
    policy = json.loads(az.POLICY_PATH.read_text())
    source = tmp_path / "raw" / "synthetic.mp4"
    source.parent.mkdir()
    source.write_bytes(b"SYNTHETIC UNIT TEST, NOT A VIDEO OR DATASET")
    source_hash = az.sha256(source)
    raw = RawSequence(
        metadata={
            "schema": RAW_SCHEMA,
            "image_semantics": policy["image_semantics"],
            "candidate_id": policy["candidate_id"],
            "sample_id": "fixture-001",
            "signer_id": "AZ-P001",
            "split": role,
            "source_video_sha256": source_hash,
            "current_frame_only": True,
            "carry_forward": False,
            "synthetic_depth": False,
            "timestamp_sources": ["FRAME_INDEX_OVER_CONTAINER_FPS"],
            "span_sha256": None,
        },
        frame_index=np.arange(3, dtype=np.int32),
        timestamp_ms=np.asarray([0, 100, 200], dtype=np.float64),
        source_size=np.tile(np.asarray([480, 640], dtype=np.int32), (3, 1)),
        hand_xy=np.full((3, 2, 21, 2), np.nan, np.float32),
        hand_proposal_support=np.zeros((3, 2, 21), np.float32),
        hand_joint_valid=np.zeros((3, 2, 21), bool),
        hand_presence=np.full((3, 2), np.nan, np.float32),
        hand_observed=np.zeros((3, 2), bool),
        hand_proposal_present=np.zeros((3, 2), bool),
        hand_roi_center_side=np.full((3, 2, 3), np.nan, np.float32),
        hand_handedness_diagnostic=np.full((3, 2), np.nan, np.float32),
        body_xy=np.full((3, 8, 2), np.nan, np.float32),
        body_support=np.zeros((3, 8), np.float32),
        body_valid=np.zeros((3, 8), bool),
        body_available=np.zeros((3,), bool),
    )
    raw_path = tmp_path / "observations" / "fixture-001.raw.npz"
    save_raw_sequence(raw_path, raw)
    receipt = {
        "schema_version": policy["observation_receipt_version"],
        "raw_schema": RAW_SCHEMA,
        "image_semantics": policy["image_semantics"],
        "candidate_id": policy["candidate_id"],
        "candidate01_assets": policy["candidate01_assets"],
        "sample_id": "fixture-001",
        "signer_id": "AZ-P001",
        "split_role": role,
        "source_sha256": source_hash,
        "raw_sha256": az.sha256(raw_path),
        "whole_source_video": True,
        "extraction_version": "SYNTHETIC_TEST_ONLY",
        "code_revision": "fixture",
        "decoder_version": "fixture",
        "timestamp_policy": "fixture",
        "frame_count": 3,
        "timestamp_range_ms": [0.0, 200.0],
        "preprocessing_source_sha256": {
            name: az.sha256(az.ROOT / name)
            for name in (
                "pipeline/perception_vnext/offline_candidate01.py",
                "pipeline/perception_vnext/hand_roi.py",
                "pipeline/perception_vnext/hand_refiner.py",
                "pipeline/perception_vnext/recognition_schema.py",
            )
        },
    }
    receipt_path = tmp_path / "observations" / "fixture-001.receipt.json"
    receipt_path.write_text(json.dumps(receipt))
    data = {
        "schema_version": policy["schema_version"],
        "dataset_id": "SYNTHETIC_TEST_ONLY",
        "fixture": True,
        "class_order": az.CLASS_ORDER,
        "approvals_path": "evidence/approvals.json",
        "source_roots": [
            {
                "path": "raw",
                "source_id": "APPHEAR_AZ_CAPTURE",
                "origin_role": "NEW_AZ_CAPTURE",
                "review_state": "APPROVED",
                "rights_ref": "fixture",
            }
        ],
        "signers": [
            {
                "signer_id": "AZ-P001",
                "person_key": "fake-human-001",
                "split_role": role,
                "aliases": ["fixture:phone1:S001"],
                "identity_review": "RESOLVED",
                "identity_evidence_ref": "fixture",
                "rights": "APPROVED",
                "consent_or_license_ref": "fixture",
                "historical_role_review": "CLEARED",
                "word_role": "NONE",
                "perception_exposure": "UNEXPOSED",
            }
        ],
        "sessions": [
            {
                "session_id": "session-001",
                "signer_id": "AZ-P001",
                "device_id": "fake-phone",
                "session_key": "fake-session-001",
                "recording_date": None,
                "capture_conditions": {"lighting": None},
                "camera": {"lens": "front", "saved_video_mirrored": False},
            }
        ],
        "samples": [
            {
                "sample_id": "fixture-001",
                "signer_id": "AZ-P001",
                "session_id": "session-001",
                "source_signer_alias": "fixture:phone1:S001",
                "split_role": role,
                "kind": "ISOLATED",
                "intended": "M",
                "prompt_id": "AZ_M",
                "attempt_index": 1,
                "training_use": "INCLUDE",
                "source": {
                    "path": "raw/synthetic.mp4",
                    "sha256": source_hash,
                    "source_id": "APPHEAR_AZ_CAPTURE",
                    "origin_role": "NEW_AZ_CAPTURE",
                    "duration_ms": 300.0,
                    "original_video": True,
                    "native_fps": 10.0,
                    "width": 480,
                    "height": 640,
                },
                "annotation": {
                    "state": "REVIEWED",
                    "annotator_id": "fake-reviewer-1",
                    "reviewer_id": "fake-reviewer-2",
                    "video_reviewed": True,
                    "verified_transcript": "M",
                    "observation_quality": ["perception_failure"],
                    "segments": [
                        {
                            "model_target": "M",
                            "letter_index": 0,
                            "start_ms": 0.0,
                            "end_ms": 200.0,
                            "boundary_uncertainty_ms": 20,
                        }
                    ],
                },
                "extraction": {
                    "raw": {
                        "path": "observations/fixture-001.raw.npz",
                        "sha256": az.sha256(raw_path),
                    },
                    "receipt": {
                        "path": "observations/fixture-001.receipt.json",
                        "sha256": az.sha256(receipt_path),
                    },
                },
            }
        ],
    }
    path = tmp_path / "package.json"
    return path, data


def check(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    path.write_text(json.dumps(data))
    return az.validate_package(path)


def test_letter_keeps_target_when_perception_failed(tmp_path: Path) -> None:
    path, data = package_fixture(tmp_path)
    result = check(path, data)
    assert result["errors"] == []
    assert result["counts"]["isolated_letter_counts"] == {"TRAIN/AZ-P001/M": 1}
    assert not result["az2_data_gates_satisfied"]
    assert any("Synthetic fixture" in row for row in result["az2_blockers"])


@pytest.mark.parametrize(
    "fault, expected",
    [
        ("missing_video", "missing file"),
        ("missing_hash", "source path/hash"),
        ("changed_video", "SHA-256 mismatch"),
        ("bad_target", "invalid model target"),
        ("class_order", "class order"),
        ("duplicate_sample", "duplicate identity"),
        ("missing_signer", "signer/session"),
        ("missing_session", "signer/session"),
        ("leakage", "signer leakage"),
        ("copy", "copied/duplicate source"),
        ("human_alias", "duplicate human person_key"),
        ("alias_collision", "signer alias repeated"),
        ("word_protected", "protected word/phone human"),
        ("source_protected", "payload not read"),
        ("other_letter", "OTHER needs"),
        ("reviewer", "independent identities"),
    ],
)
def test_intake_rejects_corrupt_governance(tmp_path: Path, fault: str, expected: str) -> None:
    path, data = package_fixture(tmp_path)
    sample = data["samples"][0]
    if fault == "missing_video":
        (tmp_path / sample["source"]["path"]).unlink()
    elif fault == "missing_hash":
        sample["source"]["sha256"] = None
    elif fault == "changed_video":
        (tmp_path / sample["source"]["path"]).write_bytes(b"changed")
    elif fault == "bad_target":
        sample["annotation"]["segments"][0]["model_target"] = "ABC"
    elif fault == "class_order":
        data["class_order"] = list(reversed(az.CLASS_ORDER))
    elif fault == "duplicate_sample":
        data["samples"].append(copy.deepcopy(sample))
    elif fault in ("missing_signer", "missing_session"):
        sample["signer_id" if fault == "missing_signer" else "session_id"] = "unknown"
    elif fault == "leakage":
        sample["split_role"] = "DEV"
    elif fault == "copy":
        duplicate = copy.deepcopy(sample)
        duplicate["sample_id"] = "copy-002"
        data["samples"].append(duplicate)
    elif fault in ("human_alias", "alias_collision"):
        duplicate = copy.deepcopy(data["signers"][0])
        duplicate["signer_id"] = "AZ-P002"
        if fault == "human_alias":
            duplicate["aliases"] = ["fixture:phone2:S001"]
        else:
            duplicate["person_key"] = "different-fake-human"
        data["signers"].append(duplicate)
    elif fault == "word_protected":
        data["signers"][0]["word_role"] = "PROTECTED"
    elif fault == "source_protected":
        sample["source"]["origin_role"] = "WORD_PROTECTED_TEST"
    elif fault == "other_letter":
        sample["annotation"]["segments"][0]["model_target"] = "OTHER"
    elif fault == "reviewer":
        sample["annotation"]["reviewer_id"] = "fake-reviewer-1"
    result = check(path, data)
    assert not result["intake_valid"]
    assert any(expected in row for row in result["errors"]), result


def test_missing_lineage_and_moving_letters_block_training(tmp_path: Path) -> None:
    path, data = package_fixture(tmp_path)
    sample = data["samples"][0]
    sample["extraction"] = None
    sample["intended"] = "J"
    sample["annotation"]["verified_transcript"] = "J"
    sample["annotation"]["segments"][0]["model_target"] = "J"
    result = check(path, data)
    assert result["intake_valid"]
    assert any("full-motion" in row for row in result["az2_blockers"])
    assert any("lineage" in row for row in result["az2_blockers"])


def test_protected_payloads_are_never_opened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, data = package_fixture(tmp_path, "PROTECTED_TEST")
    for ref in (data["samples"][0]["source"], *data["samples"][0]["extraction"].values()):
        (tmp_path / ref["path"]).unlink()
    real_hash = az.sha256

    def guarded_hash(target: Path) -> str:
        assert target.suffix not in (".mp4", ".npz"), "protected payload was opened"
        assert "receipt" not in target.name, "protected receipt was opened"
        return real_hash(target)

    monkeypatch.setattr(az, "sha256", guarded_hash)
    result = check(path, data)
    assert result["errors"] == []
    assert len(result["protected_payloads_not_opened"]) == 2
    assert not result["az2_data_gates_satisfied"]
    assert any("protected_test_integrity" in row for row in result["az2_blockers"])


@pytest.mark.parametrize(
    "fault", ["model_hash", "source_hash", "raw_hash", "mask", "timestamps", "unsupported_hand"]
)
def test_raw_lineage_rejects_drift(tmp_path: Path, fault: str) -> None:
    path, data = package_fixture(tmp_path)
    extraction = data["samples"][0]["extraction"]
    receipt_path = tmp_path / extraction["receipt"]["path"]
    receipt = json.loads(receipt_path.read_text())
    if fault in ("model_hash", "source_hash", "raw_hash"):
        if fault == "model_hash":
            receipt["candidate01_assets"]["dwpose_t_singlepass.onnx"] = "0" * 64
        else:
            receipt[fault.replace("hash", "sha256")] = "0" * 64
    else:
        raw_path = tmp_path / extraction["raw"]["path"]
        with np.load(raw_path, allow_pickle=False) as stored:
            arrays = {key: stored[key].copy() for key in stored.files}
        if fault == "mask":
            arrays["hand_observed"] = arrays["hand_observed"].astype(np.int32)
        elif fault == "unsupported_hand":
            arrays["hand_observed"][0, 0] = True
        else:
            arrays["timestamp_ms"][1] = np.nan
        np.savez_compressed(raw_path, **arrays)
        extraction["raw"]["sha256"] = az.sha256(raw_path)
        receipt["raw_sha256"] = extraction["raw"]["sha256"]
    receipt_path.write_text(json.dumps(receipt))
    extraction["receipt"]["sha256"] = az.sha256(receipt_path)
    result = check(path, data)
    assert not result["intake_valid"]
    assert not result["az2_data_gates_satisfied"]


def test_repeated_letters_require_distinct_occurrences(tmp_path: Path) -> None:
    path, data = package_fixture(tmp_path)
    sample = data["samples"][0]
    sample.update(kind="SEQUENCE", intended="MM", sequence_purpose="repeated")
    sample["annotation"]["verified_transcript"] = "MM"
    first = sample["annotation"]["segments"][0]
    first["end_ms"] = 100
    second = dict(first, letter_index=1, start_ms=100, end_ms=200)
    sample["annotation"]["segments"].append(second)
    result = check(path, data)
    assert result["errors"] == []
    second["letter_index"] = 0
    assert any("occurrence" in row for row in check(path, data)["errors"])


def test_bad_schema_and_malformed_records_report_errors(tmp_path: Path) -> None:
    path, data = package_fixture(tmp_path)
    data["schema_version"] = "3.0"
    data["sessions"][0]["session_id"] = []
    assert not check(path, data)["intake_valid"]


def test_empty_real_package_is_collection_only(tmp_path: Path) -> None:
    package = az.ROOT / "datasets/fingerspelling/az1_collection/package.json"
    result = az.validate_package(package)
    assert result["intake_valid"]
    assert result["counts"]["samples"] == 0
    assert not result["az2_data_gates_satisfied"]


@pytest.mark.parametrize("transcript", ["M", None])
def test_quarantined_attempt_does_not_require_extraction_or_count_as_coverage(
    tmp_path: Path,
    transcript: str | None,
) -> None:
    path, data = package_fixture(tmp_path)
    sample = data["samples"][0]
    sample["training_use"] = "QUARANTINE"
    sample["annotation"]["state"] = "QUARANTINED"
    sample["annotation"]["verified_transcript"] = transcript
    if transcript is None:
        sample["annotation"]["segments"] = []
    sample["extraction"] = None
    result = check(path, data)
    assert result["errors"] == []
    assert result["counts"]["isolated_letter_counts"] == {}
    assert not any("fixture-001:" in row for row in result["az2_blockers"])


def test_no_observed_hand_blocks_use_without_relabelling(tmp_path: Path) -> None:
    path, data = package_fixture(tmp_path)
    result = check(path, data)
    assert result["raw_observation_summary"]["fixture-001"]["frames_with_any_observed_hand"] == 0
    assert any("retain letter target" in row for row in result["az2_blockers"])
    assert data["samples"][0]["annotation"]["segments"][0]["model_target"] == "M"


def test_report_cannot_overwrite_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, data = package_fixture(tmp_path)
    check(path, data)
    before = path.read_bytes()
    monkeypatch.setattr("sys.argv", ["validate", str(path), "--report", str(path)])
    with pytest.raises(SystemExit) as stopped:
        az.main()
    assert stopped.value.code == 2
    assert path.read_bytes() == before
