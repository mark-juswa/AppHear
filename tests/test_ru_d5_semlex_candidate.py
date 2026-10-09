import argparse
import tarfile
from pathlib import Path

from pipeline.splits.ru_d5_semlex_candidate import (
    _canonical_member,
    _dedupe_target_rows,
    _extract_archive_members,
    _read_csv,
    _select_single_class,
    _select_we_come,
    _write_csv,
    audit_missing,
)


def _row(gloss: str, signer: str, video: str, label_type: str = "asllex") -> dict[str, str]:
    signatures = {
        "KNOW": ("One Handed", "Head", "Forehead", ""),
        "WHO": ("One Handed", "Head", "Chin", ""),
        "WE": ("One Handed", "Body", "Clavicle", ""),
        "COME": ("One Handed", "Neutral", "Neutral", ""),
        "LEAVE": ("Symmetrical Or Alternating", "Neutral", "Neutral", "open_b"),
    }
    sign_type, major, minor, nondominant = signatures[gloss]
    return {
        "video_id": video,
        "signer_id": signer,
        "duration": "1200",
        "split": "train",
        "label_type": label_type,
        "label": gloss.lower(),
        "Sign Type": sign_type,
        "Major Location": major,
        "Minor Location": minor,
        "Nondominant Handshape": nondominant,
    }


def test_selection_is_train_only_diverse_and_deduplicated() -> None:
    rows = []
    for signer in range(7):
        rows.extend(
            [
                _row("KNOW", str(signer), f"k{signer}a"),
                _row("KNOW", str(signer), f"k{signer}b"),
            ]
        )
    duplicate = dict(rows[0])
    duplicate["label_type"] = "freetext"
    rows.append(duplicate)
    heldout = _row("KNOW", "heldout", "heldout")
    heldout["split"] = "val"
    rows.append(heldout)
    deduped = _dedupe_target_rows(rows)
    selected = _select_single_class(deduped, "KNOW")
    assert len(selected) == 10
    assert len({row["signer_id"] for row in selected}) == 5
    assert all(row["split"] == "train" for row in selected)
    assert len({row["video_id"] for row in selected}) == len(selected)


def test_we_come_requires_overlapping_signers_and_balances_rows() -> None:
    rows = []
    for signer in range(4):
        rows.extend(
            [
                _row("WE", str(signer), f"w{signer}a"),
                _row("COME", str(signer), f"c{signer}a"),
            ]
        )
    rows.extend([_row("WE", "0", "w0b"), _row("COME", "0", "c0b")])
    rows.append(_row("WE", "unpaired", "unpaired"))
    selected = _select_we_come(_dedupe_target_rows(rows))
    assert sum(row["label"] == "we" for row in selected) == 5
    assert sum(row["label"] == "come" for row in selected) == 5
    assert {row["signer_id"] for row in selected} == {"0", "1", "2", "3"}


def test_selective_tar_extraction_writes_only_requested_member(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "wanted.webm").write_bytes(b"wanted")
    (source / "other.webm").write_bytes(b"other")
    archive = tmp_path / "train.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        handle.add(source / "other.webm", arcname="train/other.webm")
        handle.add(source / "wanted.webm", arcname="./train/wanted.webm")
    destination = tmp_path / "out" / "wanted.webm"
    result, missing = _extract_archive_members(
        archive, {"train/wanted.webm": destination}, "fixture"
    )
    assert destination.read_bytes() == b"wanted"
    assert len(result) == 1
    assert not missing
    assert not (tmp_path / "out" / "other.webm").exists()


def test_selective_tar_extraction_is_resumable_and_reports_missing(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "other.bin").write_bytes(b"other")
    archive = tmp_path / "items.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        handle.add(source / "other.bin", arcname="train/other.bin")
    existing = tmp_path / "out" / "existing.bin"
    existing.parent.mkdir()
    existing.write_bytes(b"existing")
    result, missing = _extract_archive_members(
        archive,
        {
            "train/existing.bin": existing,
            "train/missing.bin": tmp_path / "out" / "missing.bin",
        },
        "fixture",
    )
    assert result["train/existing.bin"]["extraction_status"] == "REUSED_EXISTING"
    assert missing == {"train/missing.bin"}


def test_tar_member_path_guard() -> None:
    assert _canonical_member("./train/example.webm") == "train/example.webm"
    try:
        _canonical_member("../escape.webm")
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe tar path was accepted")


def test_missing_audit_finds_alternate_case_extension_and_marks_absent(
    tmp_path: Path,
) -> None:
    output = tmp_path / "run"
    rows = []
    for video_id in ("RecoverMe", "Absent"):
        rows.append(
            {
                "candidate_id": f"SEMLEX-TRAIN-{video_id}",
                "canonical_gloss": "COME",
                "source_signer_id": "SEMLEX-1",
                "source_video_id": video_id,
                "pairing_or_diversity_role": "WE_COME_PAIR_MEMBER",
                "expected_archive_member": f"train/{video_id}.webm",
                "archive_video_status": (
                    "CANONICAL_MEMBER_MISSING_ALT_PATH_AUDIT_PENDING"
                ),
                "matched_archive_member": "",
                "matched_archive_member_bytes": "",
                "raw_video_path": "",
                "raw_video_sha256": "",
                "metadata_same_class_signer_alternatives": "",
                "replacement_decision": "NO_VALID_SAME_SIGNER_REPLACEMENT",
            }
        )
    _write_csv(output / "archive_member_resolution.csv", rows)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    archive = tmp_path / "train.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        handle.add(source, arcname="alternate/path/RECOVERME.MP4")
    result = audit_missing(argparse.Namespace(output=output, video_archive=archive))
    assert result["alternate_members_found"] == 1
    updated = {
        row["source_video_id"]: row
        for row in _read_csv(output / "archive_member_resolution.csv")
    }
    assert updated["RecoverMe"]["archive_video_status"] == "FOUND_ALTERNATE_MEMBER"
    assert updated["Absent"]["archive_video_status"] == "ARCHIVE_VIDEO_MISSING"
