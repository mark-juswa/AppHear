"""Real saved-raw parity and managed-storage/scoped-validation checks; no extraction."""

from __future__ import annotations

import contextlib
import copy
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.sequence_manifest import REPO
from pipeline.fingerspelling.sequence_package import validate, write_features
from pipeline.fingerspelling.storage import MARKER, SCHEMA, checked_path, relative
from tools.fingerspelling import prepare_expansion as runner


@pytest.fixture()
def external(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    base = REPO / "datasets/fingerspelling/foundation_01"
    original = json.loads((base / "tranche_manifest.json").read_text())
    row = next(r for r in original["samples"] if r["split_role"] == "TRAIN")
    receipt = json.loads((base / "features" / (row["sample_id"] + ".receipt.json")).read_text())
    output = tmp_path / "managed" / "train_additions"
    output.mkdir(parents=True)
    manifest = copy.deepcopy(original)
    manifest["samples"] = [row]
    (output / "tranche_manifest.json").write_text(json.dumps(manifest))
    (output / MARKER).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA,
                "package_root": output.resolve().as_posix(),
                "manifest_sha256": sha256(output / "tranche_manifest.json"),
                "path_convention": "ABSOLUTE_MANAGED_PACKAGE_V1",
            }
        )
    )
    for folder in ["videos", "raw"]:
        (output / folder).mkdir()
    source = output / "videos" / row["filename"]
    raw = output / "raw" / (row["sample_id"] + ".raw-v1.npz")
    raw_receipt = output / "raw" / (row["sample_id"] + ".receipt.json")
    shutil.copyfile(REPO / receipt["source_path"], source)
    shutil.copyfile(REPO / receipt["raw_path"], raw)
    shutil.copyfile(REPO / receipt["raw_receipt_path"], raw_receipt)
    write_features(output, output / "tranche_manifest.json", row, source, raw, raw_receipt)
    return output, receipt


def test_existing_saved_arrays_unchanged_in_external_package(
    external: tuple[Path, dict[str, Any]],
) -> None:
    output, old = external
    with np.load(REPO / old["features_path"], allow_pickle=False) as original:
        with np.load(
            output / "features" / (old["sample_id"] + ".npz"), allow_pickle=False
        ) as copied:
            assert set(original.files) == set(copied.files)
            for key in original.files:
                np.testing.assert_array_equal(copied[key], original[key])
    result = validate(output, output / "tranche_manifest.json")
    assert result["structural_pass"] and result["validated_sequences"] == 1
    assert not result["ready_to_train"]


def test_scoped_validation_separate_report_and_full_check_preserved(
    external: tuple[Path, dict[str, Any]],
) -> None:
    output, old = external
    full = validate(output, output / "tranche_manifest.json")
    before = (output / "validation.json").read_bytes()
    report = output / "execution/batch.validation.json"
    scoped = validate(
        output, output / "tranche_manifest.json", receipt_ids={old["sample_id"]}, report_path=report
    )
    assert scoped["structural_pass"] and scoped["scoped_pending"] == 0
    assert scoped["statistics"] == full["statistics"]
    assert not scoped["ready_to_train"]
    assert (output / "validation.json").read_bytes() == before
    assert report.is_file() and report.with_suffix(".ctc_views.json").is_file()


def test_unknown_scope_and_accidental_global_overwrite_refused(
    external: tuple[Path, dict[str, Any]],
) -> None:
    output, _ = external
    with pytest.raises(ValueError, match="separate report"):
        validate(output, output / "tranche_manifest.json", receipt_ids=set())
    result = validate(
        output,
        output / "tranche_manifest.json",
        receipt_ids={"invented"},
        report_path=output / "execution/bad.json",
    )
    assert not result["structural_pass"]


def test_storage_escape_and_no_implicit_external_permission(
    external: tuple[Path, dict[str, Any]], tmp_path: Path
) -> None:
    output, _ = external
    assert Path(relative(output / "raw", output)).is_absolute()
    assert (
        relative(REPO / "pipeline/config/fingerspelling_features_v1.json")
        == "pipeline/config/fingerspelling_features_v1.json"
    )
    with pytest.raises(ValueError, match="outside declared"):
        checked_path(tmp_path / "unrelated", output)
    with pytest.raises(ValueError, match="outside declared"):
        relative(output / "raw")


@pytest.mark.parametrize("mutation", ["marker", "source_path", "marker_hash", "array"])
def test_external_lineage_or_tensor_tampering_refused(
    external: tuple[Path, dict[str, Any]], mutation: str
) -> None:
    output, old = external
    receipt_path = output / "features" / (old["sample_id"] + ".receipt.json")
    if mutation == "marker":
        marker = json.loads((output / MARKER).read_text())
        marker["package_root"] = str(output.parent)
        (output / MARKER).write_text(json.dumps(marker))
    elif mutation == "array":
        (output / "features" / (old["sample_id"] + ".npz")).write_bytes(b"corrupt")
    else:
        receipt = json.loads(receipt_path.read_text())
        receipt["source_path" if mutation == "source_path" else "storage_marker_sha256"] = str(
            output.parent / "escape.mp4"
        )
        receipt_path.write_text(json.dumps(receipt))
    result = validate(output, output / "tranche_manifest.json")
    assert not result["structural_pass"]


def test_scoped_empty_view_does_not_read_other_arrays(
    external: tuple[Path, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    output, _ = external

    def forbid(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Unselected saved arrays must not be loaded")

    monkeypatch.setattr(np, "load", forbid)
    scoped = validate(
        output,
        output / "tranche_manifest.json",
        receipt_ids=set(),
        report_path=output / "execution/empty.json",
    )
    assert scoped["structural_pass"] and not scoped["ready_to_train"]


def test_destination_safety_and_frozen_copy(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="dedicated external"):
        runner.root_path(REPO)
    with pytest.raises(ValueError, match="dedicated external"):
        runner.root_path(Path(REPO.anchor))
    assert runner.root_path(tmp_path / "managed") == (tmp_path / "managed").resolve()
    source = tmp_path / "source.json"
    target = tmp_path / "managed/copy.json"
    source.write_text("frozen")
    runner.frozen_copy(source, target)
    runner.frozen_copy(source, target)
    target.write_text("changed")
    with pytest.raises(ValueError, match="differs"):
        runner.frozen_copy(source, target)


def test_metadata_preflight_never_loads_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pipeline.perception_vnext.offline_candidate01 import Candidate01Offline

    def forbid(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Metadata preflight must not load a perception runtime")

    monkeypatch.setattr(Candidate01Offline, "__init__", forbid)
    root = tmp_path / "managed"
    checked = runner.preflight(root, ["dev_b"], require_space=False)
    assert not checked["models_loaded"] and not checked["downloads"]
    assert checked["full_validated_prepared_counts"] == {"dev_b": 0}
    assert sha256(root / "dev_b/tranche_manifest.json") == sha256(
        runner.OUTPUT / "dev_b/tranche_manifest.json"
    )


def test_serial_cache_batch_validation_and_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = tmp_path / "plan"
    plan.mkdir()
    (plan / "batch_plan.json").write_text(
        json.dumps(
            {
                "batches": [
                    {"package": "train_additions", "sample_ids": ["t"]},
                    {"package": "dev_b", "sample_ids": ["d"]},
                ]
            }
        )
    )
    monkeypatch.setattr(runner, "OUTPUT", plan)
    monkeypatch.setattr(
        runner,
        "rows",
        lambda p: [
            {
                "sample_id": "t" if p == "train_additions" else "d",
                "split_role": "TRAIN" if p == "train_additions" else "DEV",
            }
        ],
    )
    monkeypatch.setattr(runner, "single_writer", lambda p: contextlib.nullcontext())
    calls = []
    caches = []

    def preflight(root: Path, packages: list[str]) -> dict[str, Any]:
        root.mkdir(exist_ok=True)
        calls.append("full_resume_check")
        return {}

    class Runtime:
        def close(self) -> None:
            calls.append("runtime_closed")

    def extract(output: Path, rows: list[dict[str, Any]], cache: dict[str, Any]) -> None:
        if "runtime" not in cache:
            cache["runtime"] = Runtime()
        caches.append(cache["runtime"])
        (output / "features").mkdir(parents=True, exist_ok=True)
        sid = rows[0]["sample_id"]
        (output / "features" / (sid + ".receipt.json")).write_text("{}")
        calls.append("extract_" + sid)

    def validate(output: Path, manifest: Path, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["receipt_ids"] in [{"t"}, {"d"}]
        assert kwargs["report_path"].is_relative_to(output)
        calls.append("scoped_batch_check")
        return {"structural_pass": True, "scoped_pending": 0}

    def final(root: Path, packages: list[str]) -> dict[str, Any]:
        calls.append("full_final_check")
        return {"status": "fixture_only"}

    monkeypatch.setattr(runner, "preflight", preflight)
    monkeypatch.setattr(runner, "acquire", lambda *a: calls.append("acquire"))
    monkeypatch.setattr(runner, "extract", extract)
    monkeypatch.setattr(runner, "validate", validate)
    monkeypatch.setattr(runner, "full_validate", final)
    monkeypatch.setattr(runner, "inventory", lambda p: {"fixture": True})
    root = tmp_path / "managed"
    runner.prepare(root, ["train_additions", "dev_b"])
    assert calls[0] == "full_resume_check"
    assert calls[-1] == "full_final_check"
    assert caches[0] is caches[1]
    assert calls.count("scoped_batch_check") == 2
    calls.clear()
    runner.prepare(root, ["train_additions", "dev_b"])
    assert calls == ["full_resume_check", "full_final_check"]
