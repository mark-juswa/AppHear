from pathlib import Path

from pipeline.rgb.e6_v30_five_sign_transfer import _training_config


def test_transfer_config_changes_only_warm_start_and_output() -> None:
    config = _training_config(Path("out"), Path("features"), Path("source.keras"), 202)
    assert config["warm_start_from"] == "source.keras"
    assert config["features_dir"] == "features"
    assert config["vocab_dir"] == "features"
    assert config["output_dir"].endswith("seed_202")
    assert config["class_weighting"]["enabled"] is False
    assert config["model"]["channels"] == 64
    assert config["model"]["dilations"] == [1, 2, 4, 8]
