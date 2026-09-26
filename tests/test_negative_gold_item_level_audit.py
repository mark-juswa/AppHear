from pipeline.tracking.negative_gold_item_level_audit import (
    _allocate_quotas,
    _sample,
    _select_final_additions,
)


def _row(category: str, scene: str, item: int) -> dict[str, str]:
    return {
        "discovery_category": category,
        "scene_bucket": scene,
        "open_images_id": f"{item:016x}",
    }


def test_quota_allocation_represents_every_stratum() -> None:
    groups = {
        ("A", "ONE"): [_row("A", "ONE", 1)],
        ("A", "TWO"): [_row("A", "TWO", item) for item in range(2, 8)],
        ("B", "THREE"): [_row("B", "THREE", item) for item in range(8, 18)],
    }
    quotas = _allocate_quotas(groups, 8)
    assert sum(quotas.values()) == 8
    assert all(value >= 1 for value in quotas.values())
    assert all(quotas[key] <= len(groups[key]) for key in groups)


def test_sample_is_reproducible_and_unique() -> None:
    pool = [
        _row(category, scene, item)
        for item, (category, scene) in enumerate(
            [("A", "ONE")] * 10 + [("B", "TWO")] * 10 + [("B", "THREE")] * 10
        )
    ]
    first, quotas = _sample(pool, 12, 123, 456)
    second, second_quotas = _sample(pool, 12, 123, 456)
    assert [row["open_images_id"] for row in first] == [row["open_images_id"] for row in second]
    assert quotas == second_quotas
    assert len({row["open_images_id"] for row in first}) == 12


def test_final_selection_is_reproducible_and_preserves_reserve() -> None:
    pool = []
    for item, (category, scene) in enumerate(
        [("A", "ONE")] * 8 + [("B", "TWO")] * 8 + [("B", "THREE")] * 8,
        start=1,
    ):
        row = _row(category, scene, item)
        row.update({"dhash64": f"{item * 0x111111111111111:016x}"[-16:], "author": f"a{item}"})
        pool.append(row)
    seed = [{"dhash64": "ffffffffffffffff"}]
    first, reserve, report = _select_final_additions(pool, seed, 18)
    second, second_reserve, second_report = _select_final_additions(pool, seed, 18)
    assert [row["open_images_id"] for row in first] == [row["open_images_id"] for row in second]
    assert [row["open_images_id"] for row in reserve] == [row["open_images_id"] for row in second_reserve]
    assert len(first) == 18
    assert len(reserve) == 6
    assert report["stratum_quotas"] == second_report["stratum_quotas"]
