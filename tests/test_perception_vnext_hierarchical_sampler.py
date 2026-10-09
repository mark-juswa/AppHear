from __future__ import annotations

from collections import Counter

import pytest

from pipeline.perception_vnext.hierarchical_sampler import (
    draw_identity,
    hierarchical_clip_draws,
)


def _rows() -> list[dict[str, object]]:
    rows = []
    for class_id in range(236):
        for signer_index, clips in enumerate((1, 2, 5)):
            for clip in range(clips):
                rows.append(
                    {
                        "sample_id": f"{class_id}-{signer_index}-{clip}",
                        "class_id": class_id,
                        "signer_id": f"s{signer_index}",
                        "split": "train",
                    }
                )
    return rows


def test_hierarchical_sampler_is_deterministic_and_balanced() -> None:
    rows = _rows()
    first = hierarchical_clip_draws(rows, draws=3926, seed=101, epoch=0)
    repeated = hierarchical_clip_draws(rows, draws=3926, seed=101, epoch=0)
    next_epoch = hierarchical_clip_draws(rows, draws=3926, seed=101, epoch=1)
    assert draw_identity(first) == draw_identity(repeated)
    assert draw_identity(first) != draw_identity(next_epoch)
    assert len(first) == 3926
    class_counts = Counter(int(row["class_id"]) for row in first)
    assert set(class_counts) == set(range(236))
    assert max(class_counts.values()) - min(class_counts.values()) <= 1
    for class_id in range(236):
        signer_counts = Counter(
            str(row["signer_id"]) for row in first if int(row["class_id"]) == class_id
        )
        assert max(signer_counts.values()) - min(signer_counts.values()) <= 1


def test_hierarchical_sampler_rejects_non_train_rows() -> None:
    rows = _rows()
    rows[0]["split"] = "dev"
    with pytest.raises(ValueError, match="non-TRAIN"):
        hierarchical_clip_draws(rows, draws=236, seed=101, epoch=0)
