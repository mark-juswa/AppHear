from __future__ import annotations

import numpy as np

from pipeline.rgb.e6_v30_confusion_root_cause import clip_descriptor, _nearest_centroid


def test_clip_descriptor_has_stable_shape_and_finite_values() -> None:
    x = np.zeros((96, 258), dtype=np.float32)
    mask = np.zeros(96, dtype=bool)
    mask[:4] = True
    x[:4, :63] = 0.5
    x[:4, 126:] = 0.25
    descriptor = clip_descriptor(x, mask)
    assert descriptor.shape == (24,)
    assert np.isfinite(descriptor).all()
    assert descriptor[0] == 4 / 96
    assert descriptor[1] == 1.0


def test_nearest_centroid_separates_simple_groups() -> None:
    train = np.asarray([[0.0, 0.1], [0.1, 0.0], [4.9, 5.0], [5.0, 4.9]], dtype=np.float32)
    y = np.asarray([0, 0, 1, 1], dtype=np.int32)
    # The production helper expects five classes, so duplicate non-target centers.
    train = np.concatenate([train, np.asarray([[10, 10], [11, 11], [12, 12]], dtype=np.float32)])
    y = np.concatenate([y, np.asarray([2, 3, 4], dtype=np.int32)])
    predicted, distances = _nearest_centroid(train, y, np.asarray([[0.05, 0.05], [4.95, 4.95]]))
    assert predicted.tolist() == [0, 1]
    assert distances.shape == (2, 5)
