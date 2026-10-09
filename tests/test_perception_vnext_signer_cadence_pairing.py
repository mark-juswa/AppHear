from __future__ import annotations

from collections import Counter

from model.perception_vnext.signer_cadence_invariant_236 import paired_batches


def _rows() -> list[dict[str, object]]:
    counts = {
        0: {"a": 3, "b": 2, "c": 2},
        1: {"d": 2, "e": 2, "f": 2},
        2: {"g": 3, "h": 3, "i": 2},
    }
    rows: list[dict[str, object]] = []
    for class_id, signers in counts.items():
        for signer, count in signers.items():
            for clip in range(count):
                rows.append(
                    {
                        "sample_id": f"{class_id}:{signer}:{clip}",
                        "split": "train",
                        "class_id": class_id,
                        "signer_id": signer,
                    }
                )
    return rows


def test_pair_batches_are_deterministic_complete_and_cross_signer() -> None:
    rows = _rows()
    first = paired_batches(rows, seed=101, epoch=3, clip_limit=8)
    repeated = paired_batches(rows, seed=101, epoch=3, clip_limit=8)
    changed = paired_batches(rows, seed=101, epoch=4, clip_limit=8)
    def identity(batches: list[list[dict[str, object]]]) -> list[list[object]]:
        return [[row["sample_id"] for row in batch] for batch in batches]
    assert identity(first) == identity(repeated)
    assert identity(first) != identity(changed)
    flattened = [row for batch in first for row in batch]
    assert Counter(row["sample_id"] for row in flattened) == Counter(
        row["sample_id"] for row in rows
    )
    for batch in first:
        assert len({row["class_id"] for row in batch}) >= 2
        for row in batch:
            assert any(
                other["class_id"] == row["class_id"]
                and other["signer_id"] != row["signer_id"]
                for other in batch
            )
