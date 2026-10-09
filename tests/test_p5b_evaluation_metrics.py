from __future__ import annotations

import numpy as np

from model.p5b_temporal_baseline import classification_metrics


def test_numpy_classification_metrics() -> None:
    truth=np.asarray([0,0,1,1,2],dtype=np.int32)
    pred=np.asarray([0,1,1,1,0],dtype=np.int32)
    matrix,precision,recall,f1,support,macro=classification_metrics(truth,pred,4)
    assert np.array_equal(matrix,np.asarray([[1,1,0,0],[0,2,0,0],[1,0,0,0],[0,0,0,0]]))
    assert np.array_equal(support,np.asarray([2,2,1,0]))
    assert np.allclose(precision[:3],[0.5,2/3,0.0])
    assert np.allclose(recall[:3],[0.5,1.0,0.0])
    assert np.allclose(f1[:3],[0.5,0.8,0.0])
    assert np.isclose(macro,(0.5+0.8+0.0)/3)


def test_metrics_reject_out_of_range_labels() -> None:
    try:
        classification_metrics(np.asarray([0,2]),np.asarray([0,1]),2)
    except ValueError as exc:
        assert "out of range" in str(exc)
    else:
        raise AssertionError("out-of-range label was accepted")
