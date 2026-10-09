"""Expanded-data admission/confirmation safety; no training or network in unit tests."""

from __future__ import annotations

import copy
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from model import fingerspelling_train4096 as trainer
from model.fingerspelling_fast_execution import FeatureCache
from pipeline.fingerspelling import expanded_training as data
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.storage import MARKER, SCHEMA, receipt_identity


@pytest.fixture(scope="module")
def documents() -> dict[str, Any]:
    return data.manifests()


def test_frozen_subsets_roles_and_all_signers(documents: dict[str, Any]) -> None:
    data.governance(documents)
    assert len(documents["train"]["samples"]) == 4096
    assert len(documents["confirmation"]["samples"]) == 256


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "role", "signer", "source", "label"])
def test_mutated_governance_refused(documents: dict[str, Any], mutation: str) -> None:
    docs = copy.deepcopy(documents)
    added = docs["additions"]["samples"][0]
    corresponding = next(
        r for r in docs["train"]["samples"] if r["sample_id"] == added["sample_id"]
    )
    if mutation == "missing":
        docs["train"]["samples"].pop()
    elif mutation == "duplicate":
        docs["train"]["samples"][-1] = docs["train"]["samples"][0]
    else:
        key, value = {
            "role": ("official_split", "test"),
            "signer": (
                "official_signer_id",
                docs["confirmation"]["samples"][0]["official_signer_id"],
            ),
            "source": ("official_md5", docs["confirmation"]["samples"][0]["official_md5"]),
            "label": ("normalized_transcript", "123"),
        }[mutation]
        added[key] = corresponding[key] = value
    with pytest.raises(ValueError, match="train4096/governance"):
        data.governance(docs)


@pytest.fixture
def copied(
    tmp_path: Path, documents: dict[str, Any]
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    row = documents["foundation"]["samples"][0]
    original = data.read_json(data.FOUNDATION / "features" / (row["sample_id"] + ".receipt.json"))
    package = tmp_path / "external"
    package.mkdir()
    shutil.copy2(data.FOUNDATION / "tranche_manifest.json", package / "tranche_manifest.json")
    write_json_atomic(
        package / MARKER,
        {
            "schema_version": SCHEMA,
            "package_root": package.resolve().as_posix(),
            "manifest_sha256": sha256(package / "tranche_manifest.json"),
            "path_convention": "ABSOLUTE_MANAGED_PACKAGE_V1",
        },
    )
    rec = copy.deepcopy(original)
    for key in ("source", "raw", "raw_receipt", "features"):
        source = data.REPO / rec[key + "_path"]
        folder = package / ("features" if key == "features" else "evidence")
        folder.mkdir(exist_ok=True)
        destination = folder / source.name
        shutil.copy2(source, destination)
        rec[key + "_path"] = destination.as_posix()
    rec.update(receipt_identity(package))
    write_json_atomic(package / "features" / (row["sample_id"] + ".receipt.json"), rec)
    return package, row, rec


def test_real_absolute_external_lineage_and_cache_parity(
    copied: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    package, row, rec = copied
    actual = data.verify_record(package, row, sha256(package / "tranche_manifest.json"), full=True)
    original = data.read_json(data.FOUNDATION / "features" / (row["sample_id"] + ".receipt.json"))
    for view in ("native", "phone"):
        a, b = FeatureCache().load(actual, view)[0], FeatureCache().load(original, view)[0]
        assert np.array_equal(a, b)
    assert actual["features_sha256"] == rec["features_sha256"]


@pytest.mark.parametrize(
    "mutation", ["target", "timestamp", "mask", "nan", "escape", "storage", "receipt_role"]
)
def test_receipt_and_feature_tampering_refused(
    copied: tuple[Path, dict[str, Any], dict[str, Any]], mutation: str
) -> None:
    package, row, rec = copied
    if mutation in {"escape", "storage", "receipt_role"}:
        key, value = {
            "escape": ("source_path", str(data.FOUNDATION / "videos" / row["filename"])),
            "storage": ("storage_marker_sha256", "0" * 64),
            "receipt_role": ("split_role", "TEST"),
        }[mutation]
        rec[key] = value
    else:
        path = Path(rec["features_path"])
        with np.load(path, allow_pickle=False) as saved:
            arrays: dict[str, Any] = {k: np.array(saved[k], copy=True) for k in saved.files}
        if mutation == "target":
            arrays["targets"][0] = (arrays["targets"][0] + 1) % 27
        elif mutation == "timestamp":
            arrays["timestamps_ms"][0] += 1
        elif mutation == "mask":
            arrays["hand_observed"][0, 0] = 1 - arrays["hand_observed"][0, 0]
        else:
            arrays["features"][0, 0] = np.nan
        np.savez_compressed(path, **arrays)
        rec["features_sha256"] = sha256(path)
    write_json_atomic(package / "features" / (row["sample_id"] + ".receipt.json"), rec)
    with pytest.raises(ValueError, match="train4096/"):
        data.verify_record(package, row, sha256(package / "tranche_manifest.json"), full=True)


def test_incomplete_inventory_never_reduced_to_available(
    copied: tuple[Path, dict[str, Any], dict[str, Any]], documents: dict[str, Any]
) -> None:
    package, _, _ = copied
    with pytest.raises(ValueError, match="Incomplete/unexpected inventory"):
        data.package_records(
            package, documents["foundation"], sha256(package / "tranche_manifest.json"), full=False
        )


def test_train_loader_does_not_open_confirmation_features(
    monkeypatch: pytest.MonkeyPatch, documents: dict[str, Any]
) -> None:
    visited = []

    def checked(
        package: Path, doc: dict[str, Any], digest: str, *, full: bool
    ) -> list[dict[str, Any]]:
        visited.append(package.name)
        return [{**r, "native_ctc_feasible": True} for r in doc["samples"]]

    monkeypatch.setattr(data, "package_records", checked)
    rows = data.load(Path("example"))
    assert len(rows) == 4352
    assert visited == ["foundation_01", "train_additions"]
    assert not {r["sample_id"] for r in rows} & {
        r["sample_id"] for r in documents["confirmation"]["samples"]
    }


def test_confirmation_lock_prohibits_training_before_model_load(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, documents: dict[str, Any]
) -> None:
    monkeypatch.setattr(trainer, "safe_run", lambda run: None)
    row = documents["foundation"]["samples"][0]
    rec = data.read_json(data.FOUNDATION / "features" / (row["sample_id"] + ".receipt.json"))
    write_json_atomic(tmp_path / "run_identity.json", trainer.run_identity([rec], True))
    write_json_atomic(tmp_path / "confirmation_lock.json", {"locked": True})
    with pytest.raises(ValueError, match="further fitting/selection prohibited"):
        trainer.engine(tmp_path, [rec], None, smoke=True)


@pytest.mark.parametrize(
    "name",
    [
        "fingerspelling_ctc_baseline_02",
        "fingerspelling_residual_visual_01",
        "fingerspelling_train4096_01_backup",
    ],
)
def test_historical_or_ambiguous_run_refused(name: str) -> None:
    with pytest.raises(ValueError, match="Separate owned"):
        trainer.safe_run(data.REPO / "runs" / name)


def test_length_increase_without_discrimination_does_not_pass() -> None:
    rows = [
        {"sample_id": str(i), "signer_id": str(i), "reference": "AMY", "prediction": "AM"}
        for i in range(3)
    ]
    baseline = {v: {"metrics": trainer.score(rows)} for v in ("native", "phone")}
    candidate_rows = [{**r, "prediction": "SAM"} for r in rows]
    candidate = {v: {"metrics": trainer.score(candidate_rows)} for v in ("native", "phone")}
    assert not any(
        v["discrimination_pattern_supported"] for v in trainer.changes(candidate, baseline).values()
    )


def test_evaluation_uses_validated_decoder_result_field(monkeypatch: pytest.MonkeyPatch) -> None:
    logits = np.full((3, 28), -20, dtype=np.float32)
    logits[[0, 1, 2], [0, 27, 0]] = 20
    rows = [
        {
            "sample_id": "fixture",
            "signer_id": "signer",
            "reference": "AA",
            "input_length": 3,
            "headroom": 0,
            "logits": logits,
        }
    ]
    monkeypatch.setattr(trainer, "settings", lambda: ({}, {"batch_size": 1}))
    monkeypatch.setattr(trainer, "CompiledSteps", lambda *args: None)
    monkeypatch.setattr(trainer, "collect_logits", lambda *args: rows)
    for beam in (True, False):
        result = trainer.inference(None, None, [], beam=beam)
        assert all(result[v]["predictions"][0]["prediction"] == "AA" for v in ("native", "phone"))
        assert all(result[v]["metrics"]["cer"] == 0 for v in ("native", "phone"))


def test_final_confirmation_is_locked_cached_and_never_reselects(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, documents: dict[str, Any]
) -> None:
    from types import SimpleNamespace

    rows = documents["foundation"]["samples"]
    confirmation = documents["confirmation"]["samples"]
    archived = data.read_json(data.REPO / trainer.configuration()["dev_a_reference_artifact"])
    baseline = {
        v: {"metrics": archived["models"]["residual"][v]["full"]} for v in ("native", "phone")
    }
    for v in baseline.values():
        m = v["metrics"]
        m["correct_predicted_precision"] = (
            m["correct_aligned_reference_characters"] / m["predicted_characters"]
        )
    checkpoint = tmp_path / "selected.keras"
    checkpoint.write_bytes(b"controlled-final-flow-fixture-not-a-model")
    write_json_atomic(
        tmp_path / "completion.json",
        {
            "status": "TRAIN4096_TRAINING_COMPLETE",
            "best_model_path": str(checkpoint),
            "best_model_sha256": sha256(checkpoint),
        },
    )
    write_json_atomic(tmp_path / "run_identity.json", {"fixture": True})
    monkeypatch.setattr(trainer, "safe_run", lambda run: None)
    monkeypatch.setattr(trainer, "run_identity", lambda *args: {"fixture": True})
    monkeypatch.setattr(
        trainer, "load", lambda *args, **kw: confirmation if kw.get("confirmation") else rows
    )
    monkeypatch.setattr(trainer.b2, "lineage", lambda *args: "fixture-lineage")
    monkeypatch.setattr(trainer, "settings", lambda: ({}, {}))
    mock_tf = SimpleNamespace(
        keras=SimpleNamespace(models=SimpleNamespace(load_model=lambda *a, **kw: None))
    )
    monkeypatch.setattr(trainer.reference, "tensorflow", lambda *args: mock_tf)
    monkeypatch.setattr(trainer, "initial_model", lambda *args: None)
    calls = []

    def infer(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(len(args[2]))
        assert (tmp_path / "confirmation_lock.json").is_file()
        if len(args[2]) == 1024:
            fit: dict[str, Any] = data.read_json(
                data.REPO / trainer.configuration()["train_fit_reference_artifact"]
            )["views"]
            for value in fit.values():
                m = value["metrics"]
                m["correct_predicted_precision"] = (
                    m["correct_aligned_reference_characters"] / m["predicted_characters"]
                )
            return fit
        return copy.deepcopy(baseline)

    monkeypatch.setattr(trainer, "inference", infer)
    result = trainer.final_evaluate(tmp_path, tmp_path)
    assert result["decision"] == "EXPANDED_SUPERVISION_IMPROVEMENT_NOT_ESTABLISHED"
    assert len(calls) == 4
    trainer.final_evaluate(tmp_path, tmp_path)
    assert len(calls) == 4  # Identical confirmation is reused; no repeated selection.
