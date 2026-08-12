from __future__ import annotations

import numpy as np

from model.experiments.phase1_android_shadow import _export_model, _last_valid


def test_last_valid_reads_each_sequences_final_real_frame() -> None:
    probabilities = np.zeros((2, 4, 3), dtype=np.float32)
    probabilities[0, 1] = [0.1, 0.8, 0.1]
    probabilities[1, 2] = [0.7, 0.2, 0.1]
    mask = np.asarray([[True, True, False, False], [True, True, True, False]])

    result = _last_valid(probabilities, mask)

    assert np.array_equal(result[0], probabilities[0, 1])
    assert np.array_equal(result[1], probabilities[1, 2])


def test_last_valid_rejects_empty_sequence() -> None:
    probabilities = np.zeros((1, 2, 3), dtype=np.float32)
    mask = np.zeros((1, 2), dtype=bool)

    try:
        _last_valid(probabilities, mask)
    except ValueError as error:
        assert "empty" in str(error)
    else:
        raise AssertionError("expected empty sequence rejection")


def test_export_model_rejects_unknown_quantization() -> None:
    try:
        _export_model(object(), np.zeros((1, 96, 258), dtype=np.float32), 101, "bad")
    except ValueError as error:
        assert "unsupported quantization" in str(error)
    else:
        raise AssertionError("expected unknown quantization rejection")
