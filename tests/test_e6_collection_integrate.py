from pathlib import Path

from pipeline.rgb.e6_collection_integrate import (
    _apply_spot_review,
    _proposed_split,
    _recorder_signer_id,
    _resolve_duplicate_rows,
    _spot_review_queue,
)


def test_recorder_signer_id_prefers_filename_identity() -> None:
    signer, source = _recorder_signer_id(Path("3B96F6-S001_019_take_0001.mp4"), "P_NEW04")
    assert signer == "3B96F6-S001"
    assert source == "recorder_filename"


def test_duplicate_resolution_keeps_canonical_local_row() -> None:
    rows = [
        {
            "row_id": "existing",
            "source": "local",
            "raw_video_sha256": "ABC",
            "quality_status": "usable",
            "quality_flags": "",
            "split": "train",
            "notes": "",
        },
        {
            "row_id": "copy",
            "source": "apphear_capture",
            "raw_video_sha256": "ABC",
            "quality_status": "needs_review",
            "quality_flags": "",
            "split": "audit_only",
            "notes": "",
        },
    ]
    groups = _resolve_duplicate_rows(rows)
    assert groups == {"ABC": ["existing", "copy"]}
    assert rows[0]["quality_status"] == "usable"
    assert rows[1]["quality_status"] == "exclude"
    assert rows[1]["split"] == "exclude"


def test_spot_review_selects_three_rows_per_group() -> None:
    rows = [
        {
            "row_id": f"row_{index}",
            "canonical_gloss": "GOOD",
            "signer_id": "6CC240-S001",
            "raw_video_path": f"clip_{index:02d}.mp4",
            "quality_status": "needs_review",
            "quality_flags": "",
        }
        for index in range(10)
    ]
    queue = _spot_review_queue(rows)
    assert [row["row_id"] for row in queue] == ["row_0", "row_5", "row_9"]
    assert all(row["review_status"] == "" for row in queue)


def test_proposed_split_uses_capture_folder_identity() -> None:
    row = {
        "source": "apphear_capture",
        "notes": "folder_participant=P_NEW02;signer_id_source=recorder_filename.",
    }
    assert _proposed_split(row) == "test_fresh"


def test_completed_spot_review_approves_entire_group(tmp_path: Path) -> None:
    review_path = tmp_path / "review.csv"
    review_path.write_text(
        "canonical_gloss,signer_id,review_status,review_decision,reviewed_at\n"
        "GOOD,6CC240-S001,done,accept,2026-08-05T00:00:00Z\n"
        "GOOD,6CC240-S001,done,accept,2026-08-05T00:00:00Z\n"
        "GOOD,6CC240-S001,done,accept,2026-08-05T00:00:00Z\n",
        encoding="utf-8",
    )
    rows = [
        {
            "canonical_gloss": "GOOD",
            "signer_id": "6CC240-S001",
            "source": "apphear_capture",
            "quality_status": "needs_review",
            "label_status": "needs_adjudication",
            "quality_flags": "",
            "notes": "folder_participant=P_NEW01;signer_id_source=recorder_filename.",
        }
        for _ in range(20)
    ]

    result = _apply_spot_review(rows, review_path)

    assert result["groups_passed"] == 1
    assert result["groups_blocked"] == 0
    assert all(row["quality_status"] == "usable" for row in rows)
    assert all(row["label_status"] == "verified" for row in rows)
    assert all(row["split"] == "train" for row in rows)
