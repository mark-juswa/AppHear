"""Training/stress-only withdrawal of raw evidence before frozen Adapter v1.

No new coordinates, motion, timesteps, forward filling, or source artifact edits.
Budgets are bounded synthetic stress conditions, not estimated phone failure rates.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from pipeline.fingerspelling.adapter import subset
from pipeline.perception_vnext.recognition_schema import RawSequence

VERSION = "apphear.fingerspelling.raw_evidence_robustness.v1"


def seed_for(seed: int, sample_id: str, epoch: int, profile: str) -> int:
    return int.from_bytes(
        hashlib.sha256(f"{VERSION}:{seed}:{sample_id}:{epoch}:{profile}".encode()).digest()[:8],
        "little",
    )


def withdraw(
    raw: RawSequence, sample_id: str, epoch: int, profile: str, config: dict[str, Any]
) -> tuple[RawSequence, dict[str, Any]]:
    raw.validate()
    p = config["robustness"]
    if p["schema_version"] != VERSION or profile not in p["profiles"]:
        raise ValueError("[sequence-v2/robustness] Unknown policy/profile")
    rule = p["profiles"][profile]
    chosen = subset(raw, np.arange(len(raw.frame_index), dtype=np.int32))
    observed = raw.hand_observed.astype(bool)
    budget = int(np.floor(observed.sum() * rule["maximum_removed_observed_slot_fraction"]))
    rng = np.random.default_rng(seed_for(config["seed"], sample_id, epoch, profile))
    removed = np.zeros_like(observed)
    no_proposal = np.zeros_like(observed)
    lo, hi = rule["span_observations"]
    # Candidate positions are randomized independently of transcript and model outputs.
    for start in rng.permutation(len(observed)):
        if int(removed.sum()) >= budget:
            break
        span = int(rng.integers(lo, hi + 1))
        slots = [int(rng.integers(2))] if rng.random() < p["single_slot_probability"] else [0, 1]
        positions = [
            (i, s)
            for i in range(int(start), min(int(start) + span, len(observed)))
            for s in slots
            if observed[i, s] and not removed[i, s]
        ]
        # Never partially truncate a chosen span to exceed the fixed evidence budget.
        if len(positions) > budget - int(removed.sum()):
            continue
        lost_proposal = rng.random() < p["proposal_loss_probability"]
        for i, slot in positions:
            removed[i, slot] = True
            no_proposal[i, slot] = lost_proposal
    chosen.hand_observed[removed] = False
    chosen.hand_joint_valid[removed] = False
    chosen.hand_xy[removed] = np.nan
    chosen.hand_presence[removed] = 0
    # Refiner-rejected proposals keep their original proposal evidence. Completely lost
    # proposals withdraw support/ROI too, without changing any retained coordinates.
    chosen.hand_proposal_present[no_proposal] = False
    # Candidate01 cannot report a refiner presence when no proposal was supplied.
    chosen.hand_presence[no_proposal] = np.nan
    chosen.hand_roi_center_side[no_proposal] = np.nan
    chosen.hand_proposal_support[no_proposal] = 0
    chosen.hand_handedness_diagnostic[removed] = np.nan
    chosen.validate()
    report = {
        "schema_version": VERSION,
        "sample_id": sample_id,
        "epoch_index": epoch,
        "profile": profile,
        "seed": seed_for(config["seed"], sample_id, epoch, profile),
        "frames": len(observed),
        "original_observed_slots": int(observed.sum()),
        "withdrawal_budget": budget,
        "withdrawn_slots": int(removed.sum()),
        "proposal_loss_slots": int(no_proposal.sum()),
        "remaining_observed_slots": int(chosen.hand_observed.sum()),
        "withdrawal_mask_sha256": hashlib.sha256(removed.tobytes()).hexdigest(),
        "proposal_loss_mask_sha256": hashlib.sha256(no_proposal.tobytes()).hexdigest(),
        "withdrawn_frame_slot_positions": np.argwhere(removed).tolist(),
        "original_any_hand_fraction": float(observed.any(axis=1).mean()),
        "result_any_hand_fraction": float(chosen.hand_observed.any(axis=1).mean()),
        "synthetic_evidence_withdrawal_only": True,
        "timesteps_deleted": 0,
    }
    return chosen, report
