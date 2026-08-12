from pathlib import Path

import numpy as np

from pipeline.rgb.e6_2_landmark_geometry import _copy_zero_extended, _training_config


def test_geometry_config_is_opt_in_and_isolated() -> None:
    config = _training_config(Path("run"), Path("features"), Path("init.keras"), 202)
    assert config["augment"]["contract"] == "apphear.landmark_geometry.v0"
    assert config["warm_start_from"] == "init.keras"
    assert config["model"]["channels"] == 64
    assert config["output_dir"].endswith("seed_202")


def test_zero_extension_preserves_control_function() -> None:
    import tensorflow as tf

    from model.model import build_streaming_classifier
    from pipeline.features.landmark_geometry import build_landmark_geometry

    tf.keras.utils.set_random_seed(9)
    control = build_streaming_classifier(8, 258, 5, blocks=1, channels=4, dilations=(1,))
    tf.keras.utils.set_random_seed(10)
    candidate = build_streaming_classifier(8, 444, 5, blocks=1, channels=4, dilations=(1,))
    report = _copy_zero_extended(control, candidate)
    assert report["zero_extended_layers"] == ["tcn0_conv1", "tcn0_proj"]
    assert not report["errors"]
    rng = np.random.default_rng(3)
    base = rng.normal(size=(2, 8, 258)).astype(np.float32)
    mask = np.ones((2, 8), dtype=bool)
    geometry, _ = build_landmark_geometry(base, mask)
    expected = control.predict(base, verbose=0)
    actual = candidate.predict(geometry, verbose=0)
    assert np.allclose(expected, actual, atol=1e-6)
