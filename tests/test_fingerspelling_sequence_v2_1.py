"""Target/selection/CTC governance tests; bounded model mechanics live in TRAIN smoke."""

import copy

import pytest

from model.fingerspelling_sequence_v2_1 import no_space_score, selection_score
from model.fingerspelling_sequence_v2_1_encoder import configuration
from model.fingerspelling_sequence_v2_1_execution import letters


@pytest.mark.parametrize(
    "text,expected",
    [
        ("FRANCIS ARROYO", "FRANCISARROYO"),
        ("BELLA", "BELLA"),
        ("A A", "AA"),
        ("JAZZ XX", "JAZZXX"),
        (" A  A ", "AA"),
        ("MM EE LL", "MMEELL"),
    ],
)
def test_letters_remove_only_space(text, expected):
    assert letters(text) == expected


@pytest.mark.parametrize("text", ["", " ", "A1", "A-B", "amy"])
def test_bad_transcript_refused(text):
    with pytest.raises(ValueError):
        letters(text)


def test_space_bridge_repeat_feasibility():
    for s in ["A A", "AA AA", "A A A", "BELLA", "JAZZ XX", "S S"]:
        local = letters(s)

        def minimum(x):
            return len(x) + sum(a == b for a, b in zip(x, x[1:], strict=False))

        assert minimum(local) <= minimum(s)
    assert letters("A A") == "AA"  # Requires two real emissions plus intervening blank.


def test_selection_four_equal_terms_and_no_input_mutation():
    rows = [dict(sample_id="x", signer_id="train", reference="A A", prediction="A B")]
    before = copy.deepcopy(rows)
    views = {
        v: dict(metrics={"cer": 1 / 3}, predictions=copy.deepcopy(rows))
        for v in ["native", "phone"]
    }
    assert no_space_score(rows)["cer"] == 0.5
    assert selection_score(views) == pytest.approx((1 / 3 + 0.5 + 1 / 3 + 0.5) / 4)
    assert rows == before


def test_frozen_contract():
    p = configuration()
    assert p["auxiliary_weight"] == 0.5
    assert p["auxiliary_block"] == 4
    assert p["auxiliary_blank_index"] == 26
    assert p["feature_width"] == 405 and p["logits"] == 28
    assert p["dilations"] == [1, 2, 4, 8, 16, 32, 64, 128]
