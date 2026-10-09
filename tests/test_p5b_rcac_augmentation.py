from __future__ import annotations

import numpy as np

from model import p5b_rcac_augmentation as rcac


def sample(length: int = 3) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(7)
    x = np.zeros((96, 238), dtype=np.float32)
    mask = np.zeros(96, dtype=bool)
    mask[:length] = True
    for start, end, points in rcac.BLOCKS:
        block = x[:, start:end].reshape(96, points, 4)
        block[:length, :, 0:2] = rng.normal(0, 0.5, (length, points, 2))
        block[:length, :, 2] = rng.uniform(0.1, 1, (length, points))
        block[:length, :, 3] = 1.0
    x[:length, 236:238] = 1.0
    return x, mask


def train_path_augment(
    x: np.ndarray, mask: np.ndarray, occurrence: int
) -> tuple[np.ndarray, np.ndarray]:
    output, output_mask = rcac.augment_sample_tf(x, mask, occurrence)
    return output.numpy(), output_mask.numpy()


def test_disabled_augmentation_is_identical() -> None:
    x, mask = sample()
    out, out_mask = rcac.augment_sample(x, mask, 0, enabled=False)
    assert np.array_equal(out, x)
    assert np.array_equal(out_mask, mask)


def test_unobserved_hand_remains_zero() -> None:
    x, mask = sample()
    x[:, :84] = 0
    x[:, 236] = 0
    out, _ = train_path_augment(x, mask, 1)
    assert np.count_nonzero(out[:, :84]) == 0


def test_invalid_landmark_remains_zero() -> None:
    x, mask = sample()
    x[0, :4] = 0
    out, _ = train_path_augment(x, mask, 2)
    assert np.array_equal(out[0, :4], np.zeros(4, dtype=np.float32))


def test_scores_unchanged_for_pure_spatial_case() -> None:
    x, mask = sample(length=3)
    out, _ = train_path_augment(x, mask, 3)
    for start, end, points in rcac.BLOCKS:
        before = x[:, start:end].reshape(96, points, 4)[..., 2]
        after = out[:, start:end].reshape(96, points, 4)[..., 2]
        assert np.array_equal(before, after)


def test_valid_masks_unchanged_for_pure_spatial_case() -> None:
    x, mask = sample(length=3)
    out, _ = train_path_augment(x, mask, 4)
    for start, end, points in rcac.BLOCKS:
        before = x[:, start:end].reshape(96, points, 4)[..., 3]
        after = out[:, start:end].reshape(96, points, 4)[..., 3]
        assert np.array_equal(before, after)


def test_observed_masks_unchanged_for_pure_spatial_case() -> None:
    x, mask = sample(length=3)
    out, _ = train_path_augment(x, mask, 5)
    assert np.array_equal(out[:, 236:238], x[:, 236:238])


def test_padding_remains_padding() -> None:
    x, mask = sample(length=3)
    out, out_mask = train_path_augment(x, mask, 6)
    assert not out_mask[3:].any()
    assert np.count_nonzero(out[3:]) == 0


def test_temporal_transform_moves_mask_consistently() -> None:
    x, mask = sample(length=20)
    occurrence, out, out_mask = next(
        (value, *train_path_augment(x, mask, value))
        for value in range(1000)
        if int(train_path_augment(x, mask, value)[1].sum()) < 20
    )
    assert 4 <= int(out_mask.sum()) <= 10
    assert out_mask[: int(out_mask.sum())].all()
    assert not out_mask[int(out_mask.sum()) :].any()
    assert np.count_nonzero(out[~out_mask]) == 0


def test_output_has_no_nan_or_inf() -> None:
    x, mask = sample(length=20)
    out, _ = train_path_augment(x, mask, 9)
    assert np.isfinite(out).all()


def test_output_shape_is_frozen() -> None:
    x, mask = sample(length=20)
    out, out_mask = train_path_augment(x, mask, 10)
    assert out.shape == (96, 238)
    assert out_mask.shape == (96,)


def test_same_occurrence_seed_reproduces_exact_output() -> None:
    x, mask = sample(length=20)
    first = train_path_augment(x, mask, 1234)
    second = train_path_augment(x, mask, 1234)
    assert np.array_equal(first[0], second[0])
    assert np.array_equal(first[1], second[1])


def test_validation_and_test_style_dataset_bypass_augmentation(monkeypatch) -> None:
    import tensorflow as tf

    x, mask = sample(length=20)
    features = np.stack([x, x])
    masks = np.stack([mask, mask])
    labels = np.array([0, 1], dtype=np.int32)
    monkeypatch.setattr(
        rcac,
        "augment_batch_numpy",
        lambda *_: (_ for _ in ()).throw(AssertionError("augmentation invoked")),
    )
    batch = next(iter(rcac.validation_dataset(features, labels, masks)))
    assert np.array_equal(batch[0].numpy(), features)
    assert isinstance(batch[0], tf.Tensor)
