import numpy as np

from eval.runtime_diagnostics.p2a_dwpose_linux import (
    MIN_CONFIDENT_JOINTS,
    association_diagnostic,
    exact_match,
    windows_to_wsl,
)


def _group(name: str, points: np.ndarray, confident: int = 21) -> dict:
    scores = np.zeros(21, dtype=np.float64)
    scores[:confident] = 0.9
    return {
        "name": name,
        "points": points,
        "scores": scores,
        "confident_count": confident,
        "present": confident >= MIN_CONFIDENT_JOINTS,
    }


def test_windows_path_translation_preserves_spaces() -> None:
    assert str(windows_to_wsl(r"F:\ASL DATASET\x.png")) == "/mnt/f/ASL DATASET/x.png"


def test_association_uses_palm_and_half_points() -> None:
    box = np.array([0.0, 0.0, 100.0, 100.0])
    points = np.full((21, 2), 50.0)
    diagnostic = association_diagnostic(_group("left", points), box)
    assert diagnostic["eligible"]
    points[:11] = [150.0, 150.0]
    diagnostic = association_diagnostic(_group("left", points), box)
    assert not diagnostic["eligible"]


def test_exact_match_maximizes_cardinality_and_applies_gate() -> None:
    first = np.full((21, 2), [25.0, 25.0])
    second = np.full((21, 2), [75.0, 25.0])
    groups = [_group("left", first, 21), _group("right", second, 10)]
    boxes = [
        np.array([0.0, 0.0, 50.0, 50.0]),
        np.array([50.0, 0.0, 100.0, 50.0]),
    ]
    ungated, _ = exact_match(groups, boxes, gated=False)
    gated, _ = exact_match(groups, boxes, gated=True)
    assert ungated == {0: 0, 1: 1}
    assert gated == {0: 0}
