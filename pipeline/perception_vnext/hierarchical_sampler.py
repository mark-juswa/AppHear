"""Deterministic class -> signer -> clip sampling for the frozen vNext dataset."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any

import numpy as np

SAMPLER_TYPE = "class_signer_clip_balanced"
SAMPLER_SCHEMA = "apphear.perception_vnext.training_sampler.v1"
SAMPLER_STREAM = 0x41505048


def _cycle_balanced(values: list[Any], count: int, rng: np.random.Generator) -> list[Any]:
    if not values:
        raise ValueError("balanced cycle requires at least one value")
    output: list[Any] = []
    while len(output) < count:
        order = rng.permutation(len(values))
        output.extend(values[int(index)] for index in order)
    return output[:count]


def hierarchical_clip_draws(
    rows: list[dict[str, Any]],
    *,
    draws: int,
    seed: int,
    epoch: int,
) -> list[dict[str, Any]]:
    """Return one deterministic, quota-balanced epoch of TRAIN clip references.

    Classes differ by at most one draw. Within each class, signer counts differ by at
    most one draw. Clips are uniformly selected within the chosen class+signer group.
    """

    if draws < 1 or seed < 0 or epoch < 0:
        raise ValueError("draws must be positive and seed/epoch must be non-negative")
    by_class_signer: defaultdict[int, defaultdict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    seen_ids: set[str] = set()
    for row in rows:
        if row.get("split") != "train":
            raise ValueError(f"non-TRAIN row entered hierarchical sampler: {row.get('sample_id')}")
        sample_id = str(row["sample_id"])
        if sample_id in seen_ids:
            raise ValueError(f"duplicate TRAIN sample: {sample_id}")
        seen_ids.add(sample_id)
        by_class_signer[int(row["class_id"])][str(row["signer_id"])].append(row)
    classes = sorted(by_class_signer)
    if classes != list(range(236)):
        raise ValueError("hierarchical sampler requires all 236 TRAIN classes")
    rng = np.random.default_rng(np.random.SeedSequence([seed, epoch, SAMPLER_STREAM]))
    base, remainder = divmod(draws, len(classes))
    class_counts = {class_id: base for class_id in classes}
    for index in rng.permutation(len(classes))[:remainder]:
        class_counts[classes[int(index)]] += 1

    selected: list[dict[str, Any]] = []
    for class_id in classes:
        signer_groups = by_class_signer[class_id]
        signers = sorted(signer_groups)
        signer_schedule = _cycle_balanced(signers, class_counts[class_id], rng)
        for signer in signer_schedule:
            clips = sorted(signer_groups[signer], key=lambda row: str(row["sample_id"]))
            selected.append(clips[int(rng.integers(0, len(clips)))])
    rng.shuffle(selected)
    if len(selected) != draws:
        raise AssertionError("hierarchical sampler draw count mismatch")
    return selected


def draw_identity(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        [str(row["sample_id"]) for row in rows],
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
