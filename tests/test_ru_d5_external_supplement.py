from pipeline.splits.ru_d5_external_supplement import (
    MINIMUM_SIGNER_TARGETS,
    POPSIGN_V1_VOCAB,
    TARGETS,
    _availability_rows,
    _ms_candidates,
)


def test_popsign_scope_is_bounded_by_actual_v1_vocabulary() -> None:
    assert set(TARGETS) == {"KNOW", "WHO", "WE", "COME", "LEAVE"}
    assert POPSIGN_V1_VOCAB == {"WHO", "WE"}
    assert MINIMUM_SIGNER_TARGETS == {
        "KNOW": 3,
        "WHO": 5,
        "WE_COME_PAIR": 5,
        "LEAVE": 5,
    }


def test_only_ms_asl_train_rows_become_candidates() -> None:
    ms = {
        "train": [
            {"text": "know", "signer_id": 1, "file": "a", "url": "u"},
            {"text": "today", "signer_id": 2, "file": "b", "url": "u"},
        ],
        "val": [{"text": "know", "signer_id": 3}],
        "test": [{"text": "know", "signer_id": 4}],
    }
    candidates = _ms_candidates(ms)
    assert len(candidates) == 1
    assert candidates[0]["source_split"] == "train"
    assert candidates[0]["canonical_gloss"] == "KNOW"
    assert "TODAY" not in {row["canonical_gloss"] for row in candidates}


def test_popsign_we_is_rejected_without_come_pair() -> None:
    ms = {"train": [], "val": [], "test": []}
    rows = _availability_rows(ms, [])
    popsign = {
        row["canonical_gloss"]: row for row in rows if row["source"] == "POPSIGN_V1"
    }
    assert popsign["WHO"]["status"] == "TRAIN_ARCHIVE_AVAILABLE"
    assert popsign["WE"]["status"] == "UNPAIRED_WE_NOT_ELIGIBLE"
    assert popsign["KNOW"]["status"] == "GLOSS_ABSENT"
