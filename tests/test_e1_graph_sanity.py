import numpy as np

from model.experiments.e1_graph_sanity import connected_components, select_balanced
from model.model_gcn import NUM_KP, skeleton_adjacency


def test_graph_adjacency_is_finite_symmetric_and_complete() -> None:
    adjacency = skeleton_adjacency()
    assert adjacency.shape == (NUM_KP, NUM_KP)
    assert np.isfinite(adjacency).all()
    assert np.allclose(adjacency, adjacency.T)
    assert np.all(np.diag(adjacency) > 0)
    assert sum(len(component) for component in connected_components(adjacency)) == NUM_KP


def test_balanced_selection_is_deterministic_and_contiguous() -> None:
    y = np.repeat(np.arange(4, dtype=np.int32), 6)
    first = select_balanced(y, classes=3, clips_per_class=5, seed=17)
    second = select_balanced(y, classes=3, clips_per_class=5, seed=17)
    assert first == second
    assert first.class_ids == [0, 1, 2]
    assert np.bincount(first.remapped_labels).tolist() == [5, 5, 5]
    assert len(set(first.indices)) == 15


def test_masked_graph_preserves_frozen_io_contract() -> None:
    from model.model_gcn import build_stgcn

    model = build_stgcn(
        time_window=8,
        num_classes=3,
        channels=(4,),
        mask_padded_frames=True,
        infer_hand_presence=True,
    )
    output = model(np.zeros((2, 8, 258), dtype=np.float32), training=False).numpy()
    assert output.shape == (2, 8, 3)
    assert np.isfinite(output).all()
    assert np.allclose(output.sum(axis=-1), 1.0)


def test_mediapipe_pose_topology_has_no_isolated_nodes() -> None:
    adjacency = skeleton_adjacency("mediapipe")
    assert not [component for component in connected_components(adjacency) if len(component) == 1]


def test_e1_matched_configs_cover_unique_three_seed_pairs() -> None:
    from model.experiments.e1_matched import _config_paths
    from model.train_streaming import load_stream_config

    configs = [load_stream_config(path) for path in _config_paths()]
    assert len(configs) == 6
    assert {(config.model_type, config.seed) for config in configs} == {
        (model_type, seed) for model_type in ("tcn", "gcn") for seed in (0, 1, 2)
    }
    assert len({config.output_dir for config in configs}) == 6
    assert all(config.warm_start_from is None for config in configs)


def test_corrected_gcn_checkpoint_roundtrip(tmp_path: object) -> None:
    from pathlib import Path

    import tensorflow as tf

    from model.model_gcn import build_stgcn

    model = build_stgcn(
        time_window=8,
        num_classes=3,
        channels=(4,),
        mask_padded_frames=True,
        infer_hand_presence=True,
        pose_topology="mediapipe",
    )
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy")
    model.train_on_batch(
        np.zeros((2, 8, 258), dtype=np.float32),
        np.zeros((2, 8), dtype=np.int32),
    )
    path = Path(str(tmp_path)) / "gcn.keras"
    model.save(path)
    restored = tf.keras.models.load_model(path, safe_mode=False)
    assert restored.input_shape == (None, 8, 258)
    assert restored.output_shape == (None, 8, 3)
