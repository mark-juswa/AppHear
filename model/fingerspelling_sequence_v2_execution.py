"""Reuse the frozen cadence/feature cache; add raw-derived robustness RAM views."""

from __future__ import annotations

from typing import Any

import numpy as np

from model.fingerspelling_temporal_execution import TemporalFeatureCache
from pipeline.fingerspelling.adapter import WIDTH, derive, subset
from pipeline.fingerspelling.evidence_robustness import seed_for, withdraw
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import verify_raw
from pipeline.fingerspelling.temporal_views import selected_indices
from pipeline.perception_vnext.recognition_schema import RawSequence


class RobustTemporalCache(TemporalFeatureCache):
    """Unmodified native/phone features; augmentation exists only in RAM.

    Original raw observations are read-only. Augmented derivatives are not permanently
    cached for all epochs. Stress views are fixed by sample/policy with epoch=-1.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.raws: dict[str, RawSequence] = {}
        self.stress_info: dict[tuple[str, str], dict[str, Any]] = {}

    def raw(self, rec: dict[str, Any]) -> RawSequence:
        self.register(rec)
        sid = rec["sample_id"]
        if sid not in self.raws:
            self.raws[sid] = verify_raw(
                REPO / rec["raw_path"], REPO / rec["raw_receipt_path"], rec, rec["source_sha256"]
            )
        return self.raws[sid]

    def augmented(
        self, rec: dict[str, Any], actual: str, profile: str, epoch: int
    ) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
        raw = self.raw(rec)
        positions = selected_indices(raw, actual, self.config)
        chosen = subset(raw, positions)
        withdrawn, report = withdraw(chosen, rec["sample_id"], epoch, profile, self.config)
        x = derive(withdrawn)
        _, y = super().load(rec, "native")
        report["temporal_lineage"] = self.view_info[(rec["sample_id"], actual)]
        report["feasible"] = len(x) >= rec["ctc_min_timesteps"]
        report["actual_cadence_view"] = actual
        return x, y, report

    def load(self, rec: dict[str, Any], view: str) -> tuple[np.ndarray, np.ndarray]:
        if not view.startswith("stress_"):
            return super().load(rec, view)
        profile = view.removeprefix("stress_")
        key = (rec["sample_id"], view)
        if key not in self.arrays:
            x, y, report = self.augmented(rec, "phone", profile, -1)
            x.setflags(write=False)
            self.arrays[key] = x, y
            self.stress_info[key] = report
        return self.arrays[key]

    def training_array(
        self, rec: dict[str, Any], epoch: int
    ) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
        if rec["split_role"] != "TRAIN":
            raise ValueError("[sequence-v2/train] Only official TRAIN can be augmented for fitting")
        self.register(rec)
        regimes = self.config["train_regimes"]
        # Every sample rotates through all four regimes in four consecutive epochs.
        offset = seed_for(self.config["seed"], rec["sample_id"], 0, "regime")
        requested = regimes[(offset + epoch) % len(regimes)]
        requested_cadence = "phone" if requested == "phone_robust" else requested
        views = self.config["temporal_views"]
        feasible = [
            v
            for v in views[: views.index(requested_cadence) + 1]
            if self.view_info[(rec["sample_id"], v)]["feasible"]
        ]
        if not feasible:
            raise ValueError("[sequence-v2/ctc] Native infeasible; sample retained, loss refused")
        actual = feasible[-1]
        if requested == "phone_robust":
            x, y, info = self.augmented(
                rec, actual, self.config["robustness"]["train_profile"], epoch
            )
        else:
            x, y = self.load(rec, actual)
            info = dict(self.view_info[(rec["sample_id"], actual)])
        info.update(
            sample_id=rec["sample_id"],
            requested=requested,
            actual=actual + ("_robust" if requested == "phone_robust" else ""),
            fallback=actual != requested_cadence,
            epoch_index=epoch,
        )
        return x, y, info

    def training_batch(
        self, rows: list[dict[str, Any]], epoch_index: int
    ) -> tuple[tuple[np.ndarray, ...], list[dict[str, Any]]]:
        arrays = [self.training_array(rec, epoch_index) for rec in rows]
        lengths = np.array([len(x) for x, _, _ in arrays], np.int32)
        target_lengths = np.array([len(y) for _, y, _ in arrays], np.int32)
        x = np.zeros((len(rows), int(lengths.max()), WIDTH), np.float32)
        mask = np.zeros((*x.shape[:2], 1), np.float32)
        y = np.zeros((len(rows), int(target_lengths.max())), np.int32)
        for i, (a, b, _) in enumerate(arrays):
            x[i, : len(a)], mask[i, : len(a)], y[i, : len(b)] = a, 1, b
        return (x, mask, y, lengths, target_lengths), [a[2] for a in arrays]
