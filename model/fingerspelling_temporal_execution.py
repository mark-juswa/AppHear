"""Extend the existing model-side feature cache with real-observation temporal views."""

from __future__ import annotations

import hashlib
from typing import Any, cast

import numpy as np

from model.fingerspelling_fast_execution import FeatureCache
from pipeline.fingerspelling.adapter import WIDTH, derive, sha256, subset
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import verify_raw
from pipeline.fingerspelling.temporal_views import VERSION, requested_view, selected_indices


class TemporalFeatureCache(FeatureCache):
    """Extends the existing cache; derived views are RAM-only and never alter input artifacts."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self.config = config
        self.view_info: dict[tuple[str, str], dict[str, Any]] = {}
        self.registered: set[str] = set()

    def register(self, rec: dict[str, Any]) -> None:
        sid = rec["sample_id"]
        if sid in self.registered:
            return
        native, target = super().load(rec, "native")
        phone, _ = super().load(rec, "phone")
        if sha256(REPO / rec["raw_receipt_path"]) != rec["raw_receipt_sha256"]:
            raise ValueError("[fingerspelling/temporal] Extraction receipt changed")
        raw = verify_raw(
            REPO / rec["raw_path"], REPO / rec["raw_receipt_path"], rec, rec["source_sha256"]
        )
        for view in self.config["temporal_views"]:
            indices = selected_indices(raw, view, self.config)
            chosen = subset(raw, indices)
            if view == "intermediate":
                features = derive(chosen)
                features.setflags(write=False)
                self.arrays[(sid, view)] = (features, target)
            elif len(indices) != len(native if view == "native" else phone):
                raise ValueError("[fingerspelling/temporal] Stored-view contract mismatch")
            elapsed = float((chosen.timestamp_ms[-1] - chosen.timestamp_ms[0]) / 1000)
            self.view_info[(sid, view)] = {
                "schema_version": VERSION,
                "view": view,
                "selected_positions_sha256": hashlib.sha256(indices.tobytes()).hexdigest(),
                "selected_frame_indices_sha256": hashlib.sha256(
                    chosen.frame_index.tobytes()
                ).hexdigest(),
                "frames": len(indices),
                "ctc_min_timesteps": rec["ctc_min_timesteps"],
                "headroom": len(indices) - rec["ctc_min_timesteps"],
                "feasible": len(indices) >= rec["ctc_min_timesteps"],
                "observed_rate_hz": (len(indices) - 1) / elapsed if elapsed > 0 else None,
                "raw_sha256": rec["raw_sha256"],
                "adapter": self.adapter,
            }
        self.registered.add(sid)

    def load(self, rec: dict[str, Any], view: str) -> tuple[np.ndarray, np.ndarray]:
        if view != "intermediate":
            return cast(tuple[np.ndarray, np.ndarray], super().load(rec, view))
        self.register(rec)
        return cast(tuple[np.ndarray, np.ndarray], self.arrays[(rec["sample_id"], view)])

    def choose(self, rec: dict[str, Any], epoch_index: int) -> tuple[str, dict[str, Any]]:
        self.register(rec)
        requested = requested_view(rec["sample_id"], epoch_index, self.config)
        views = self.config["temporal_views"]
        for index in range(views.index(requested), -1, -1):
            actual = views[index]
            info = self.view_info[(rec["sample_id"], actual)]
            if info["feasible"]:
                return actual, {
                    "sample_id": rec["sample_id"],
                    "requested": requested,
                    "actual": actual,
                    "fallback": actual != requested,
                    **info,
                }
        raise ValueError(
            "[fingerspelling/temporal] Native CTC infeasible; source retained, training refused"
        )

    def training_batch(
        self, rows: list[dict[str, Any]], epoch_index: int
    ) -> tuple[tuple[np.ndarray, ...], list[dict[str, Any]]]:
        chosen = [self.choose(rec, epoch_index) for rec in rows]
        arrays = [self.load(rec, view) for rec, (view, _) in zip(rows, chosen, strict=True)]
        lengths = np.array([len(x) for x, _ in arrays], np.int32)
        target_lengths = np.array([len(y) for _, y in arrays], np.int32)
        x = np.zeros((len(rows), int(lengths.max()), WIDTH), np.float32)
        mask = np.zeros((*x.shape[:2], 1), np.float32)
        y: np.ndarray = np.zeros((len(rows), int(target_lengths.max())), np.int32)
        for i, (a, b) in enumerate(arrays):
            x[i, : len(a)], mask[i, : len(a)], y[i, : len(b)] = a, 1, b
        return (x, mask, y, lengths, target_lengths), [item[1] for item in chosen]
