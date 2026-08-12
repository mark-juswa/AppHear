from __future__ import annotations

import numpy as np

from pipeline.rgb.e6_3_open_set_rejection import (
    CLASSES,
    _fit_oas_mahalanobis,
    _mahalanobis_score,
    _masked_mean,
    _window_bounds,
)


def test_window_bounds_stays_inside_clip() -> None:
    assert _window_bounds(0, 200) == (0, 95)
    assert _window_bounds(199, 200) == (104, 199)
    assert _window_bounds(10, 20) == (0, 19)


def test_masked_mean_ignores_padding() -> None:
    values = np.asarray([[[2.0], [4.0], [100.0]]])
    mask = np.asarray([[True, True, False]])
    np.testing.assert_allclose(_masked_mean(values, mask), [[3.0]])


def test_oas_mahalanobis_prefers_own_class_centers() -> None:
    rng = np.random.default_rng(7)
    dimensions = 8
    embeddings = []
    labels = []
    for class_id in range(len(CLASSES)):
        center = np.zeros(dimensions)
        center[class_id] = 8.0
        embeddings.append(center + rng.normal(0.0, 0.2, size=(20, dimensions)))
        labels.extend([class_id] * 20)
    x = np.concatenate(embeddings).astype(np.float64)
    y = np.asarray(labels, dtype=np.int64)
    fit = _fit_oas_mahalanobis(x, y)
    outputs = {"embedding": x, "prediction": y}
    own_scores = _mahalanobis_score(outputs, fit)
    wrong_outputs = {"embedding": x, "prediction": (y + 1) % len(CLASSES)}
    wrong_scores = _mahalanobis_score(wrong_outputs, fit)
    assert np.isfinite(own_scores).all()
    assert 0.0 <= float(fit["shrinkage"]) <= 1.0
    assert float(np.mean(own_scores)) > float(np.mean(wrong_scores))
