"""Separate governed canonical-v2 artifacts; original raw, features and manifests are read-only."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.fingerspelling.adapter import sha256, subset
from pipeline.fingerspelling.adapter_v2 import WIDTH, column_names, derive, identity
from pipeline.fingerspelling.package_io import recover_partial, write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO, target_ids
from pipeline.fingerspelling.sequence_package import verify_raw
from pipeline.fingerspelling.temporal_views import VERSION as TEMPORAL_VERSION
from pipeline.fingerspelling.temporal_views import selected_indices

DEFAULT = REPO / "datasets/fingerspelling/canonical_v2_01"
PARENT = REPO / "datasets/fingerspelling/foundation_01"
ARTIFACT = "apphear.fingerspelling.canonical_features.v2"
RECEIPT = "apphear.fingerspelling.canonical_receipt.v2"
MANIFEST_SHA = "6b4f152c6bd51eae7af697a58c88c6e20cb0b5e537e272a1a84a897aec54ae6e"


def policy() -> dict[str, Any]:
    result: dict[str, Any] = json.loads(
        (REPO / "model/config/fingerspelling_ctc_baseline_02.json").read_text()
    )
    return result


def parents() -> list[dict[str, Any]]:
    if sha256(PARENT / "tranche_manifest.json") != MANIFEST_SHA:
        raise ValueError("[fingerspelling/v2-package] Original manifest changed")
    manifest = json.loads((PARENT / "tranche_manifest.json").read_text())
    result = []
    signers: dict[str, set[str]] = {"TRAIN": set(), "DEV": set()}
    for row in manifest["samples"]:
        role = row["split_role"]
        if role not in signers:
            raise ValueError("[fingerspelling/v2-package] Protected role refused")
        path = PARENT / "features" / f"{row['sample_id']}.receipt.json"
        rec = json.loads(path.read_text())
        for name in [
            "sample_id",
            "split_role",
            "official_signer_id",
            "normalized_transcript",
            "ctc_min_timesteps",
        ]:
            if row[name] != rec[name]:
                raise ValueError("[fingerspelling/v2-package] Official identity mismatch")
        rec = dict(
            rec,
            parent_receipt_path=path.relative_to(REPO).as_posix(),
            parent_receipt_sha256=sha256(path),
        )
        result.append(rec)
        signers[role].add(row["official_signer_id"])
    if signers["TRAIN"] & signers["DEV"] or Counter(r["split_role"] for r in result) != {
        "TRAIN": 1024,
        "DEV": 256,
    }:
        raise ValueError("[fingerspelling/v2-package] Signer leakage/incomplete original inventory")
    return result


def load_raw(rec: dict[str, Any]) -> Any:
    if (
        sha256(REPO / rec["raw_receipt_path"]) != rec["raw_receipt_sha256"]
        or sha256(REPO / rec["raw_path"]) != rec["raw_sha256"]
    ):
        raise ValueError("[fingerspelling/v2-package] Original raw receipt/hash changed")
    return verify_raw(
        REPO / rec["raw_path"], REPO / rec["raw_receipt_path"], rec, rec["source_sha256"]
    )


def temporal_identity() -> dict[str, str]:
    return {
        "schema_version": TEMPORAL_VERSION,
        "source_sha256": sha256(REPO / "pipeline/fingerspelling/temporal_views.py"),
        "policy_sha256": sha256(REPO / "model/config/fingerspelling_ctc_baseline_02.json"),
    }


def check(rec: dict[str, Any], original: dict[str, Any], recompute: bool = False) -> dict[str, Any]:
    if (
        rec["schema_version"] != RECEIPT
        or rec["adapter"] != identity()
        or rec["manifest_sha256"] != MANIFEST_SHA
        or rec["temporal"] != temporal_identity()
    ):
        raise ValueError("[fingerspelling/v2-package] Contract identity changed")
    for name in [
        "sample_id",
        "split_role",
        "official_signer_id",
        "normalized_transcript",
        "ctc_min_timesteps",
        "source_sha256",
        "raw_sha256",
        "raw_receipt_sha256",
        "parent_receipt_sha256",
    ]:
        if rec[name] != original[name]:
            raise ValueError("[fingerspelling/v2-package] Source/raw/official lineage changed")
    if sha256(REPO / rec["features_path"]) != rec["features_sha256"]:
        raise ValueError("[fingerspelling/v2-package] Features checksum mismatch")
    if rec["package_implementation_sha256"] != sha256(Path(__file__)):
        raise ValueError("[fingerspelling/v2-package] Package implementation identity changed")
    raw = load_raw(original) if recompute else None
    with np.load(REPO / rec["features_path"], allow_pickle=False) as data:
        meta = json.loads(str(data["metadata_json"].item()))
        if meta != {
            "schema_version": ARTIFACT,
            "adapter": identity(),
            "sample_id": rec["sample_id"],
        }:
            raise ValueError("[fingerspelling/v2-package] Artifact schema mismatch")
        if data["targets"].tolist() != target_ids(rec["normalized_transcript"]):
            raise ValueError("[fingerspelling/v2-package] Target mismatch")
        for view in policy()["temporal_views"]:
            f = data[f"{view}_features"]
            ts = data[f"{view}_timestamps_ms"]
            fi = data[f"{view}_frame_indices"]
            if (
                f.ndim != 2
                or f.shape[1] != WIDTH
                or not len(f)
                or not np.isfinite(f).all()
                or len(ts) != len(f)
                or not (np.diff(ts) > 0).all()
                or not (np.diff(fi) > 0).all()
            ):
                raise ValueError("[fingerspelling/v2-package] Invalid geometry/chronology")
            mask_cols = [
                i
                for i, n in enumerate(column_names())
                if n.endswith(
                    (
                        "valid",
                        "observed",
                        "proposal_present",
                        "available",
                        "continuous",
                        "ambiguous",
                        "duplicate",
                        "potentially_distinct",
                        "reset",
                    )
                )
            ]
            if not np.isin(f[:, mask_cols], [0, 1]).all():
                raise ValueError("[fingerspelling/v2-package] Invalid masks")
            info = rec["views"][view]
            if info["frames"] != len(f) or info["ctc_feasible"] != (
                len(f) >= rec["ctc_min_timesteps"]
            ):
                raise ValueError("[fingerspelling/v2-package] CTC status mismatch")
            for key, values in [("timestamps_sha256", ts), ("frame_indices_sha256", fi)]:
                import hashlib

                if info[key] != hashlib.sha256(values.tobytes()).hexdigest():
                    raise ValueError("[fingerspelling/v2-package] View identity mismatch")
            if raw is not None:
                chosen = subset(raw, selected_indices(raw, view, policy()))
                expected, states = derive(chosen)
                if (
                    not np.array_equal(expected, f)
                    or not np.array_equal(chosen.timestamp_ms, ts)
                    or not np.array_equal(chosen.frame_index, fi)
                    or any(not np.array_equal(data[f"{view}_{k}"], a) for k, a in states.items())
                ):
                    raise ValueError(
                        "[fingerspelling/v2-package] Raw/canonical/features recomputation mismatch"
                    )
    return rec


def prepare_one(output: Path, rec: dict[str, Any]) -> dict[str, Any]:
    import hashlib

    folder = output / "features"
    folder.mkdir(parents=True, exist_ok=True)
    receipt = folder / f"{rec['sample_id']}.receipt.json"
    path = folder / f"{rec['sample_id']}.npz"
    if receipt.exists():
        return check(json.loads(receipt.read_text()), rec)
    raw = load_raw(rec)
    arrays: dict[str, Any] = {
        "targets": np.asarray(target_ids(rec["normalized_transcript"]), np.int32),
        "metadata_json": np.asarray(
            json.dumps(
                {"schema_version": ARTIFACT, "adapter": identity(), "sample_id": rec["sample_id"]},
                sort_keys=True,
            )
        ),
    }
    views = {}
    for view in policy()["temporal_views"]:
        chosen = subset(raw, selected_indices(raw, view, policy()))
        features, states = derive(chosen)
        arrays.update(
            {
                f"{view}_features": features,
                f"{view}_timestamps_ms": chosen.timestamp_ms,
                f"{view}_frame_indices": chosen.frame_index,
            }
        )
        arrays.update({f"{view}_{key}": a for key, a in states.items()})
        views[view] = {
            "frames": len(features),
            "ctc_feasible": len(features) >= rec["ctc_min_timesteps"],
            "headroom": len(features) - rec["ctc_min_timesteps"],
            "timestamps_sha256": hashlib.sha256(chosen.timestamp_ms.tobytes()).hexdigest(),
            "frame_indices_sha256": hashlib.sha256(chosen.frame_index.tobytes()).hexdigest(),
            "missing_primary_frames": int((states["primary_slot"] < 0).sum()),
            "duplicate_frames": int(states["canonical_states"][:, 4].sum()),
            "ambiguous_frames": int(states["canonical_states"][:, 3].sum()),
        }
    staged = path.with_name(path.name + ".pending")
    recover_partial(output, [path, staged], "Uncommitted canonical-v2 feature staging")
    with staged.open("wb") as stream:
        np.savez_compressed(stream, **arrays)
    staged.replace(path)
    result = {
        k: v
        for k, v in rec.items()
        if k not in {"adapter", "features_path", "features_sha256", "schema_version"}
    }
    result.update(
        schema_version=RECEIPT,
        adapter=identity(),
        manifest_sha256=MANIFEST_SHA,
        temporal=temporal_identity(),
        features_path=path.relative_to(REPO).as_posix(),
        features_sha256=sha256(path),
        views=views,
        package_implementation_sha256=sha256(Path(__file__)),
    )
    write_json_atomic(receipt, result)
    return check(result, rec)


def validate(output: Path = DEFAULT, recompute: bool = False) -> dict[str, Any]:
    rows = parents()
    found = []
    errors = []
    known = {r["sample_id"] for r in rows}
    for path in (output / "features").glob("*.receipt.json"):
        if path.name.removesuffix(".receipt.json") not in known:
            errors.append("UNEXPECTED_ID:" + path.name)
    pending = []
    for r in rows:
        path = output / "features" / f"{r['sample_id']}.receipt.json"
        if not path.exists():
            pending.append(r["sample_id"])
            continue
        try:
            found.append(check(json.loads(path.read_text()), r, recompute))
        except (ValueError, KeyError, OSError) as exc:
            errors.append(r["sample_id"] + ":" + str(exc))
    report = {
        "schema_version": "apphear.fingerspelling.canonical_validation.v2",
        "adapter": identity(),
        "counts": dict(Counter(r["split_role"] for r in found)),
        "selected": 1280,
        "validated": len(found),
        "pending_ids": pending,
        "errors": errors,
        "ready_to_train": len(found) == 1280 and not errors,
        "recomputed": recompute,
        "ctc_infeasible": {
            v: dict(Counter(r["split_role"] for r in found if not r["views"][v]["ctc_feasible"]))
            for v in policy()["temporal_views"]
        },
        "test_accessed": False,
    }
    write_json_atomic(output / "validation.json", report)
    return report


def prepare(output: Path = DEFAULT, limit: int | None = None) -> dict[str, Any]:
    from tools.fingerspelling.tranche import single_writer

    with single_writer(output):
        output.mkdir(parents=True, exist_ok=True)
        write_json_atomic(
            output / "feature_columns.json", {"adapter": identity(), "columns": column_names()}
        )
        started = time.perf_counter()
        completed = 0
        for r in parents():
            existing = (output / "features" / f"{r['sample_id']}.receipt.json").exists()
            try:
                prepare_one(output, r)
            except BaseException as exc:
                write_json_atomic(
                    output / "failure.json",
                    {"sample_id": r["sample_id"], "error": str(exc), "not_silently_omitted": True},
                )
                raise
            if not existing:
                completed += 1
                if completed % 16 == 0:
                    print(
                        json.dumps(
                            {
                                "newly_prepared": completed,
                                "elapsed_seconds": time.perf_counter() - started,
                            }
                        ),
                        flush=True,
                    )
                if limit is not None and completed >= limit:
                    break
        result = validate(output)
        result.update(newly_prepared=completed, elapsed_seconds=time.perf_counter() - started)
        write_json_atomic(output / "preparation_summary.json", result)
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "validate", "status"])
    parser.add_argument("--output", type=Path, default=DEFAULT)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--recompute", action="store_true")
    a = parser.parse_args()
    a.output.resolve().relative_to(REPO / "datasets/fingerspelling")
    if a.output.resolve() == PARENT.resolve():
        raise ValueError("[fingerspelling/v2-package] Original package read-only")
    report = (
        prepare(a.output, a.limit) if a.command == "prepare" else validate(a.output, a.recompute)
    )
    print(json.dumps({k: v for k, v in report.items() if k not in {"pending_ids"}}, indent=2))
