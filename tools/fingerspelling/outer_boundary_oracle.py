"""Paired DEV-only outer-window oracle; immutable models, no training or detector calls."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, cast

import numpy as np

from model import fingerspelling_baseline2 as b2
from model import fingerspelling_ctc as reference
from model.fingerspelling_emission import collect_logits
from model.fingerspelling_metrics import alignment, summarize
from model.fingerspelling_prefix_beam import decode_beam
from model.fingerspelling_residual_execution import ResidualCache, ResidualSteps
from pipeline.fingerspelling.adapter import derive, identity, sha256, subset
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.residual_visual_package import load as load_visual
from pipeline.fingerspelling.sequence_manifest import REPO, target_ids
from pipeline.fingerspelling.sequence_package import verify_raw, verify_source
from pipeline.fingerspelling.temporal_views import selected_indices
from pipeline.fingerspelling.visual_quality import quality
from pipeline.perception_vnext.recognition_schema import RawSequence
from tools.fingerspelling.decoder_audit import OUT as DECODER_OUT
from tools.fingerspelling.decoder_audit import load_logits, save_logits

CONFIG = REPO / "model/config/fingerspelling_outer_boundary_oracle_01.json"
OUT = REPO / "artifacts/fingerspelling_outer_boundary_oracle_01"


def window_indices(raw: RawSequence, metadata: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    """Publisher times share original zero-based timeline; original PTS offset cancels."""
    raw.validate()
    times = [
        float(metadata[k])
        for k in ("annotationStartTimeS", "annotationEndTimeS", "clipStartTimeS", "clipEndTimeS")
    ]
    a, b, c, d = times
    if not np.isfinite(times).all() or not c <= a < b <= d:
        raise ValueError("[outer-oracle/window] Invalid/inverted/out-of-clip metadata")
    t = raw.timestamp_ms
    start, end = (a - c) * 1000, (b - c) * 1000
    if not len(t) or not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
        raise ValueError("[outer-oracle/window] Invalid observation chronology")
    # No tolerance padding, snapping, fabricated samples or silently clipped windows.
    if start < t[0] or end > t[-1]:
        raise ValueError("[outer-oracle/window] Window outside decoded observation extent")
    positions = np.flatnonzero((t >= start) & (t <= end)).astype(np.int32)
    if not len(positions):
        raise ValueError("[outer-oracle/window] No real observations inside annotation")
    before, after = t < start, t > end
    observed = np.any(raw.hand_observed, axis=1)
    outside = before | after
    return positions, {
        "publisher_start_local_ms": start,
        "publisher_end_local_ms": end,
        "publisher_duration_s": (end - start) / 1000,
        "full_observations": len(t),
        "oracle_observations": len(positions),
        "full_duration_s": float((t[-1] - t[0]) / 1000),
        "oracle_duration_s": float((t[positions[-1]] - t[positions[0]]) / 1000),
        "before_removed": int(before.sum()),
        "after_removed": int(after.sum()),
        "before_removed_percent": float(before.mean() * 100),
        "after_removed_percent": float(after.mean() * 100),
        "outside_missing_hand_frames": int((outside & ~observed).sum()),
        "outside_missing_hand_fraction": (
            float((~observed[outside]).mean()) if outside.any() else None
        ),
        "inside_missing_hand_fraction": float((~observed[positions]).mean()),
        "raw_first_ms": float(t[0]),
        "raw_last_ms": float(t[-1]),
        "oracle_first_ms": float(t[positions[0]]),
        "oracle_last_ms": float(t[positions[-1]]),
        "first_selected_frame": int(raw.frame_index[positions[0]]),
        "last_selected_frame": int(raw.frame_index[positions[-1]]),
        "decoded_metadata_duration_difference_s": float((t[-1] - t[0]) / 1000 - (d - c)),
        "timestamp_sources": raw.metadata.get("timestamp_sources"),
    }


def selected_input(
    raw: RawSequence,
    positions: np.ndarray,
    view: str,
    embeddings: np.ndarray,
    qualities: np.ndarray,
    policy: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    """Trim, sample real frames, recompute adapter; preserve original visual indices."""
    if (
        positions.ndim != 1
        or not len(positions)
        or np.any(np.diff(positions) <= 0)
        or positions[0] < 0
        or positions[-1] >= len(raw.frame_index)
    ):
        raise ValueError("[outer-oracle/input] Invalid real observation indices")
    if embeddings.shape != (len(raw.frame_index), 2, 576) or qualities.shape != (
        len(raw.frame_index),
        2,
    ):
        raise ValueError("[outer-oracle/input] Visual/raw alignment mismatch")
    trimmed = subset(raw, positions)
    selected = positions[selected_indices(trimmed, view, policy)]
    geometry = derive(subset(raw, selected))
    packed = np.concatenate(
        [geometry, embeddings[selected].reshape(len(selected), 1152), qualities[selected]], axis=1
    ).astype(np.float32)
    if packed.shape != (len(selected), 1559) or not np.isfinite(packed).all():
        raise ValueError("[outer-oracle/input] Invalid model input")
    return packed, selected


class OracleCache:
    """Research tensors, never written over the original geometry/visual archives."""

    def __init__(self, tensors: dict[tuple[str, str, str], np.ndarray], arm: str, condition: str):
        self.tensors, self.arm, self.condition = tensors, arm, condition

    def batch(self, rows: list[dict[str, Any]], view: str) -> tuple[np.ndarray, ...]:
        arrays = [self.tensors[r["sample_id"], self.condition, view] for r in rows]
        if self.arm == "b2":
            arrays = [x[:, :405] for x in arrays]
        lengths = np.asarray([len(x) for x in arrays], np.int32)
        labels = [np.asarray(target_ids(r["normalized_transcript"]), np.int32) for r in rows]
        label_lengths = np.asarray([len(y) for y in labels], np.int32)
        x = np.zeros((len(rows), int(lengths.max()), arrays[0].shape[1]), np.float32)
        mask = np.zeros((*x.shape[:2], 1), np.float32)
        y = np.zeros((len(rows), int(label_lengths.max())), np.int32)
        for i, (a, b) in enumerate(zip(arrays, labels, strict=True)):
            x[i, : len(a)], mask[i, : len(a)], y[i, : len(b)] = a, 1, b
        return x, mask, y, lengths, label_lengths


def score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    value = summarize(rows, 10)
    n = value["reference_characters"]
    predicted = sum(len(r["prediction"]) for r in rows)
    value.update(
        {
            "correct_aligned_reference_characters": n - value["substitutions"] - value["deletions"],
            "predicted_characters": predicted,
            "predicted_reference_ratio": predicted / n if n else None,
            "exact_sequences": sum(r["reference"] == r["prediction"] for r in rows),
            "empty_predictions": sum(not r["prediction"] for r in rows),
            "macro_signer_cer": (
                float(np.mean([v["cer"] for v in value["signers"].values()])) if rows else None
            ),
        }
    )
    return value


def errors(r: dict[str, Any]) -> int:
    a = alignment(r["reference"], r["prediction"])
    return int(a["substitutions"] + a["deletions"] + a["insertions"])


def paired(
    full: list[dict[str, Any]], oracle: list[dict[str, Any]], windows: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    if [r["sample_id"] for r in full] != [r["sample_id"] for r in oracle]:
        raise ValueError("[outer-oracle/pair] Inconsistent paired IDs/order")
    details = []
    for a, b in zip(full, oracle, strict=True):
        delta = errors(b) - errors(a)
        details.append(
            {
                "sample_id": a["sample_id"],
                "signer_id": a["signer_id"],
                "reference": a["reference"],
                "full_decoded": a["prediction"],
                "oracle_decoded": b["prediction"],
                "full_errors": errors(a),
                "oracle_errors": errors(b),
                "error_delta": delta,
                "direction": "improve" if delta < 0 else "regress" if delta > 0 else "unchanged",
                "full_view_observations": a["input_length"],
                "oracle_view_observations": b["input_length"],
                "full_ctc_headroom": a["headroom"],
                "oracle_ctc_headroom": b["headroom"],
                **windows[a["sample_id"]],
            }
        )
    correlations = {}
    gain = np.array([-d["error_delta"] / len(d["reference"]) for d in details])
    for key in [
        "before_removed_percent",
        "after_removed_percent",
        "full_duration_s",
        "outside_missing_hand_fraction",
    ]:
        eligible = [i for i, d in enumerate(details) if d[key] is not None]
        x = np.array([details[i][key] for i in eligible], dtype=float)
        y = gain[eligible]
        correlations[key] = (
            float(np.corrcoef(x, y)[0, 1]) if len(x) > 1 and x.std() > 0 and y.std() > 0 else None
        )
    f, o = score(full), score(oracle)
    signer_directions = {
        s: {
            "full_cer": f["signers"][s]["cer"],
            "oracle_cer": o["signers"][s]["cer"],
            "sequences": f["signers"][s]["sequences"],
            "direction": (
                "improve"
                if o["signers"][s]["cer"] < f["signers"][s]["cer"]
                else "regress" if o["signers"][s]["cer"] > f["signers"][s]["cer"] else "unchanged"
            ),
        }
        for s in f["signers"]
    }
    return {
        "full": f,
        "oracle": o,
        "directions": dict(Counter(d["direction"] for d in details)),
        "signer_directions": signer_directions,
        "pearson_correlations_noncausal": correlations,
        "full_ctc_infeasible": sum(d["full_ctc_headroom"] < 0 for d in details),
        "oracle_ctc_infeasible": sum(d["oracle_ctc_headroom"] < 0 for d in details),
        "sequences": details,
    }


def inspect() -> (
    tuple[list[dict[str, Any]], dict[tuple[str, str, str], np.ndarray], dict[str, dict[str, Any]]]
):
    cfg = json.loads(CONFIG.read_text())
    if sha256(REPO / cfg["dataset"] / "tranche_manifest.json") != cfg["manifest_sha256"]:
        raise ValueError("[outer-oracle/data] Frozen manifest changed")
    rows = [r for r in b2.dataset(REPO / cfg["dataset"]) if r["split_role"] == "DEV"]
    if len(rows) != 256 or len({r["sample_id"] for r in rows}) != 256:
        raise ValueError("[outer-oracle/data] Require original DEV-A256")
    tensors, windows, failures, lineage = {}, {}, [], []
    baseline = ResidualCache()
    for i, rec in enumerate(rows):
        sid = rec["sample_id"]
        try:
            source_sha = verify_source(REPO / rec["source_path"], rec)
            if source_sha != rec["source_sha256"]:
                raise ValueError("Source SHA mismatch")
            raw = verify_raw(
                REPO / rec["raw_path"], REPO / rec["raw_receipt_path"], rec, source_sha
            )
            receipt = json.loads((REPO / rec["raw_receipt_path"]).read_text())
            if (
                receipt["timestamp_sources"] != ["CONTAINER_POS_MSEC"]
                or raw.timestamp_ms[0] != 0
                or not np.array_equal(raw.frame_index, np.arange(len(raw.frame_index)))
            ):
                raise ValueError(
                    "Ambiguous timeline: require zero-start consecutive container timestamps"
                )
            positions, diagnostic = window_indices(raw, rec["official_metadata"])
            diagnostic["ctc_min_timesteps"] = rec["ctc_min_timesteps"]
            windows[sid] = diagnostic
            embeddings, qualities = load_visual(rec)
            trimmed_quality = quality(subset(raw, positions))["quality"]
            if not np.array_equal(trimmed_quality, qualities[positions]):
                raise ValueError("Visual quality changes after trim")
            for condition, indices in [
                ("full", np.arange(len(raw.frame_index), dtype=np.int32)),
                ("oracle", positions),
            ]:
                for view in cfg["views"]:
                    packed, selected = selected_input(
                        raw, indices, view, embeddings, qualities, b2.policy()[0]
                    )
                    if condition == "full" and not np.array_equal(
                        packed, baseline.load(rec, view)[0]
                    ):
                        raise ValueError("Full input differs from established residual cache")
                    tensors[sid, condition, view] = packed
                    diagnostic[f"{condition}_{view}_original_indices"] = selected.tolist()
            lineage.append(
                {
                    k: rec[k]
                    for k in [
                        "sample_id",
                        "official_signer_id",
                        "source_sha256",
                        "raw_sha256",
                        "raw_receipt_sha256",
                        "features_sha256",
                        "adapter",
                    ]
                }
            )
        except (ValueError, OSError, KeyError) as e:
            failures.append({"sample_id": sid, "reason": str(e)})
        if (i + 1) % 32 == 0:
            print(
                json.dumps(
                    {
                        "stage": "TIMING_ALIGNMENT_VERIFICATION",
                        "checked": i + 1,
                        "invalid": len(failures),
                    }
                ),
                flush=True,
            )
    OUT.mkdir(exist_ok=True)
    write_json_atomic(
        OUT / "timing_alignment.json",
        {
            "valid": len(windows),
            "invalid": failures,
            "selected": len(rows),
            "windows": windows,
            "lineage": lineage,
            "test_accessed": False,
        },
    )
    if failures:
        raise ValueError(
            "[outer-oracle/window] See timing_alignment.json; no samples silently excluded"
        )
    return rows, tensors, windows


def run(inspect_only: bool = False) -> dict[str, Any]:
    cfg = json.loads(CONFIG.read_text())
    if cfg["schema_version"] != "apphear.fingerspelling.outer_boundary_oracle.v1" or (
        cfg["blank_index"],
        cfg["blank_penalty"],
        cfg["beam_width"],
        cfg["top_paths"],
    ) != (27, 0.5, 10, 1):
        raise ValueError("[outer-oracle/config] Frozen research/decoder contract mismatch")
    rows, tensors, windows = inspect()
    if inspect_only:
        return {"status": "TIMING_ALIGNMENT_VALID", "usable": len(rows)}
    previous = json.loads((DECODER_OUT / "audit_identity.json").read_text())
    rcfg = json.loads((REPO / "model/config/fingerspelling_residual_visual_01.json").read_text())
    residual_path = REPO / previous["config"]["model_checkpoint"]
    base_path = REPO / rcfg["base_checkpoint"]
    if (
        sha256(residual_path) != previous["input"]["residual_sha256"]
        or sha256(base_path) != rcfg["base_checkpoint_sha256"]
    ):
        raise ValueError("[outer-oracle/model] Frozen checkpoint hash mismatch")
    if (
        previous["input"]["official_dev_ids"] != [r["sample_id"] for r in rows]
        or previous["input"]["adapter"] != identity()
    ):
        raise ValueError("[outer-oracle/data] Historical IDs/adapter mismatch")
    audit_id = {
        "config_sha256": sha256(CONFIG),
        "implementation_sha256": sha256(Path(__file__)),
        "adapter": identity(),
        "manifest_sha256": cfg["manifest_sha256"],
        "residual_sha256": sha256(residual_path),
        "b2_sha256": sha256(base_path),
        "timing_alignment_sha256": sha256(OUT / "timing_alignment.json"),
        "historical_decoder_identity_sha256": sha256(DECODER_OUT / "audit_identity.json"),
        "test_accessed": False,
        "training": False,
    }
    write_json_atomic(OUT / "identity.json", audit_id)
    tf = reference.tensorflow(b2.policy()[1])
    models = {
        "residual": tf.keras.models.load_model(residual_path, compile=False),
        "b2": tf.keras.models.load_model(base_path, compile=False),
    }
    report = {
        "identity": audit_id,
        "config": cfg,
        "timing_usable": len(rows),
        "models": {},
        "runtime_seconds": {},
    }
    for arm in cfg["models"]:
        # Inference only, no optimizer/update/GradientTape.
        class Steps:
            def __init__(self, model: Any) -> None:
                self.model = model

            def infer(self, x: Any, mask: Any) -> Any:
                return self.model([x, mask], training=False)

        steps: Any = ResidualSteps(tf, models[arm]) if arm == "residual" else Steps(models[arm])
        views = {}
        for view in cfg["views"]:
            predictions = {}
            for condition in ["full", "oracle"]:
                started = time.perf_counter()
                cache = OracleCache(tensors, arm, condition)
                key = f"{arm}_{condition}_{view}"
                path = OUT / f"{key}_logits.npz"
                logit_id = {**audit_id, "arm": arm, "condition": condition, "view": view}
                if path.exists():
                    logits = load_logits(path, logit_id)
                elif arm == "residual" and condition == "full":
                    logits = load_logits(
                        DECODER_OUT / f"{view}_logits.npz", {**previous["input"], "view": view}
                    )
                    # Check frozen model + regenerated full inputs against cached logits.
                    x, mask, *_ = cache.batch(rows[:2], view)
                    fresh = steps.infer(x, mask).numpy()
                    for i, r in enumerate(logits[:2]):
                        delta = float(np.max(np.abs(fresh[i, : r["input_length"]] - r["logits"])))
                        if delta > 1e-4:
                            raise ValueError(f"Cached full logits mismatch {delta}")
                    report.setdefault("cached_full_logit_parity", {})[view] = {
                        "sequences": 2,
                        "max_abs_delta": float(
                            max(
                                np.max(np.abs(fresh[i, : r["input_length"]] - r["logits"]))
                                for i, r in enumerate(logits[:2])
                            )
                        ),
                    }
                    save_logits(path, logits, logit_id)
                else:
                    print(
                        json.dumps(
                            {
                                "stage": "FROZEN_INFERENCE_ONLY",
                                "arm": arm,
                                "condition": condition,
                                "view": view,
                            }
                        ),
                        flush=True,
                    )
                    logits = collect_logits(
                        tf,
                        cast(Any, steps),
                        cast(Any, cache),
                        rows,
                        view,
                        b2.policy()[1]["batch_size"],
                    )
                    save_logits(path, logits, logit_id)
                decoded = []
                for r in logits:
                    pred = decode_beam(r["logits"], 0.5, 10, 1)[0]["prediction"]
                    decoded.append(
                        {k: v for k, v in r.items() if k != "logits"} | {"prediction": pred}
                    )
                predictions[condition] = decoded
                report["runtime_seconds"][key] = time.perf_counter() - started
                print(
                    json.dumps(
                        {"stage": "DECODE_COMPLETE", "key": key, "cer": score(decoded)["cer"]}
                    ),
                    flush=True,
                )
            views[view] = paired(predictions["full"], predictions["oracle"], windows)
        report["models"][arm] = views
        write_json_atomic(OUT / "paired_evaluation.json", report)
    return {
        "status": "OUTER_BOUNDARY_ORACLE_EVALUATED",
        "report": str(OUT / "paired_evaluation.json"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.inspect_only), indent=2))
