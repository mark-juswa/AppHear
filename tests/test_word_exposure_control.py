"""Exposure-controlled enrichment keeps the baseline class schedule (no prior redistribution)."""

from __future__ import annotations

import numpy as np

from eval.runtime_diagnostics.word_vocabulary_eval import SEMLEX_EVAL_FRACTION, semlex_role
from model.perception_vnext.recognition_v2_robust_aug import exposure_exact_order


def test_exact_order_matches_baseline_class_exposure_every_epoch() -> None:
    # class 0: 3 governed + 5 extra rows; class 1: 4 governed rows, no extra
    labels = np.asarray([0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0])
    base = {0: 3, 1: 4}
    seen_extra = set()
    for epoch in range(20):
        order = exposure_exact_order(labels, base, np.random.default_rng([101, epoch]))
        rows, views = order // 2, order % 2
        assert len(order) == 2 * sum(base.values())
        for c, n in base.items():
            picked = rows[labels[rows] == c]
            assert len(picked) == 2 * n  # one dense + one sparse view per drawn clip
            assert len(set(picked.tolist())) == n  # without replacement
        for r in set(rows.tolist()):
            assert sorted(views[rows == r].tolist()) == [0, 1]
        seen_extra |= {int(r) for r in rows if r >= 7}
    assert seen_extra == {7, 8, 9, 10, 11}  # extra rows do get used across epochs


def test_semlex_roles_are_deterministic_and_split() -> None:
    signers = [f"SEMLEX::{k}" for k in range(200)]
    roles = [semlex_role(s) for s in signers]
    assert roles == [semlex_role(s) for s in signers]
    fraction = roles.count("EVAL") / len(roles)
    assert abs(fraction - SEMLEX_EVAL_FRACTION) < 0.1
