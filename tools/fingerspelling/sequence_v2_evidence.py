"""Read-only TRAIN missingness inventory for the isolated V2 engineering gate."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.fingerspelling.adapter import phone_indices, sha256
from pipeline.fingerspelling.expanded_training import FOUNDATION, manifests, read_json
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO

DESTINATION = Path("I:/AppHearData/FSboard_TRAIN4096_01")
OUTPUT = REPO / "artifacts/fingerspelling_sequence_v2_gate_01"


def receipts() -> list[dict[str, Any]]:
    docs = manifests()  # Frozen metadata governance only; no DEV-B feature access.
    rows = []
    for package, doc in [
        (FOUNDATION, docs["foundation"]),
        (DESTINATION / "train_additions", docs["additions"]),
    ]:
        for row in doc["samples"]:
            if row["split_role"] != "TRAIN":
                continue
            rec = read_json(package / "features" / (row["sample_id"] + ".receipt.json"))
            if any(
                rec.get(k) != row[k]
                for k in (
                    "sample_id",
                    "split_role",
                    "official_signer_id",
                    "normalized_transcript",
                    "ctc_min_timesteps",
                )
            ):
                raise ValueError("[sequence-v2/evidence] Manifest/receipt identity mismatch")
            rows.append(rec)
    if len(rows) != 4096 or len({r["sample_id"] for r in rows}) != 4096:
        raise ValueError("[sequence-v2/evidence] Frozen TRAIN-4096 required")
    return sorted(rows, key=lambda r: r["sample_id"])


def quantiles(values: Sequence[float]) -> dict[str, float] | None:
    if not values:
        return None
    return dict(
        zip(
            ["min", "p25", "median", "p75", "p90", "p95", "max"],
            map(float, np.quantile(values, [0, 0.25, 0.5, 0.75, 0.9, 0.95, 1])),
            strict=True,
        )
    )


def runs(missing: np.ndarray) -> tuple[list[int], list[int]]:
    edges = np.diff(np.r_[False, missing, False].astype(np.int8))
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    all_runs = (ends - starts).tolist()
    internal = [int(e - s) for s, e in zip(starts, ends, strict=True) if s > 0 and e < len(missing)]
    return all_runs, internal


def main() -> None:
    rows = receipts()
    fractions: dict[str, list[float]] = {v: [] for v in ("native", "phone")}
    internal: list[int] = []
    all_runs: list[int] = []
    slot_counts: Counter[str] = Counter()
    total: Counter[str] = Counter()
    for n, rec in enumerate(rows):
        path = REPO / rec["raw_path"]
        if sha256(path) != rec["raw_sha256"]:
            raise ValueError("[sequence-v2/evidence] Raw identity mismatch")
        with np.load(path, allow_pickle=False) as data:
            observed = data["hand_observed"].astype(bool)
            timestamps = data["timestamp_ms"]
            proposals = data["hand_proposal_present"].astype(bool)
        for view, chosen in [("native", observed), ("phone", observed[phone_indices(timestamps)])]:
            fractions[view].append(float(chosen.any(axis=1).mean()))
            total[view + "_frames"] += len(chosen)
            total[view + "_zero_hand_sequences"] += int(not chosen.any())
            if view == "phone":
                a, b = runs(~chosen.any(axis=1))
                all_runs.extend(a)
                internal.extend(b)
                slot_counts.update(map(str, chosen.sum(axis=1).tolist()))
        total["proposal_without_accepted_slot"] += int((proposals & ~observed).sum())
        if (n + 1) % 512 == 0:
            print(json.dumps({"event": "TRAIN_MASK_AUDIT", "done": n + 1}), flush=True)
    report = {
        "TRAIN_sequences": len(rows),
        "signers": len({r["official_signer_id"] for r in rows}),
        "strata": dict(Counter(r["source_stratum"] for r in rows)),
        "any_hand_observed_fraction": {v: quantiles(x) for v, x in fractions.items()},
        "phone_missing_runs_observations": quantiles(all_runs),
        "phone_internal_missing_runs_observations": quantiles(internal),
        "phone_internal_run_count": len(internal),
        "phone_observed_slot_counts": dict(slot_counts),
        "totals": dict(total),
        "phone_hz": 6.231166,
        "test_accessed": False,
        "dev_features_accessed": False,
        "interpretation": "Measured governed TRAIN masks; phone stress budgets are synthetic "
        "conditions, not population estimates.",
    }
    write_json_atomic(OUTPUT / "train_missingness_evidence.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
