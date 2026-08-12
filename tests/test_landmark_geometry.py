import numpy as np

from pipeline.features.landmark_geometry import (
    GEOMETRY_DIM,
    SCHEMA_ID,
    augment_landmark_geometry_batch,
    build_landmark_geometry,
)


def _fixture() -> tuple[np.ndarray, np.ndarray]:
    x = np.zeros((2, 4, 258), dtype=np.float32)
    mask = np.zeros((2, 4), dtype=bool)
    mask[:, :3] = True
    hands = x[:, :, :126].reshape(2, 4, 2, 21, 3)
    pose = x[:, :, 126:].reshape(2, 4, 33, 4)
    for side in range(2):
        hands[:, :3, side, :, 0] = np.linspace(0.1, 0.5, 21)
        hands[:, :3, side, :, 1] = np.linspace(0.2, 0.6, 21)
        hands[:, :3, side, :, 2] = 0.05 + side * 0.01
    pose[:, :3, :, :3] = 0.25
    pose[:, :3, :, 3] = 0.9
    return x, mask


def test_geometry_contract_preserves_base_and_padding() -> None:
    x, mask = _fixture()
    result, schema = build_landmark_geometry(x, mask)
    assert result.shape == (2, 4, GEOMETRY_DIM)
    assert schema["schema_id"] == SCHEMA_ID
    assert schema["base_channels_preserved"] is True
    assert np.array_equal(result[..., :258], x)
    assert np.all(result[:, 3] == 0.0)
    assert np.isfinite(result).all()


def test_geometry_missing_hand_is_zero_and_masked() -> None:
    x, mask = _fixture()
    x[..., 63:126] = 0.0
    result, _ = build_landmark_geometry(x, mask)
    assert np.all(result[:, :3, 318:378] == 0.0)
    assert np.all(result[:, :3, 392:406] == 0.0)
    assert np.all(result[:, :3, 443] == 1.0)
    assert np.all(result[:, :3, 442] == 0.0)


def test_geometry_augmentation_rebuilds_derived_channels() -> None:
    from model.augment import AugmentConfig

    x, mask = _fixture()
    geometry, _ = build_landmark_geometry(x, mask)
    out = augment_landmark_geometry_batch(
        geometry,
        AugmentConfig(10.0, 0.1, 0.01, 0.0),
        np.random.default_rng(7),
        mask,
    )
    rebuilt, _ = build_landmark_geometry(out[..., :258], mask)
    assert np.allclose(out, rebuilt)
    assert np.all(out[:, 3] == 0.0)
