"""Resumption, source staging, metrics and no-training guard regression tests."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pytest

from model.fingerspelling_ctc import CONFIG_PATH, train
from model.fingerspelling_metrics import alignment, greedy_decode, summarize
from pipeline.fingerspelling.package_io import recover_partial, write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from tools.fingerspelling import foundation, tranche


def test_greedy_blank_and_repeat_semantics() -> None:
    assert greedy_decode([12, 12, 27, 12, 26, 26, 4, 27, 4]) == "MM EE"
    assert greedy_decode([27, 27]) == ""
    with pytest.raises(ValueError):
        greedy_decode([29])


@pytest.mark.parametrize(
    "reference,prediction,counts",
    [
        ("CAT", "CUT", (1, 0, 0)),
        ("MM", "M", (0, 1, 0)),
        ("A", "AB", (0, 0, 1)),
        ("", "A", (0, 0, 1)),
        ("AA", "AA", (0, 0, 0)),
    ],
)
def test_edit_counts(reference: str, prediction: str, counts: tuple[int, int, int]) -> None:
    result = alignment(reference, prediction)
    assert tuple(result[k] for k in ["substitutions", "deletions", "insertions"]) == counts


def test_metric_subgroups_and_sample_count_caveat() -> None:
    result = summarize([{"reference": "JAZZ", "prediction": "JAZ", "signer_id": "DEV1"}], 10)
    assert result["cer"] == 0.25
    assert result["subgroups"]["Z"]["aligned_character_recall"] == 0.5
    assert result["subgroups"]["REPEATED_LETTERS"]["deletions"] == 1
    assert not result["subgroups"]["J"]["interpretation_sample_count_sufficient"]


def test_atomic_nested_json_and_recovery_preserves_partial(tmp_path: Path) -> None:
    path = tmp_path / "reports/nested/test.json"
    write_json_atomic(path, {"state": "COMPLETE"})
    assert json.loads(path.read_text()) == {"state": "COMPLETE"}
    partial = tmp_path / "clip.download"
    partial.write_bytes(b"incomplete")
    recover_partial(tmp_path, [partial], "interrupted")
    assert not partial.exists()
    assert next((tmp_path / "recovery").rglob("clip.download")).read_bytes() == b"incomplete"


def test_acquisition_retry_partial_verified_before_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = b"original RGB bytes"
    row = {
        "sample_id": "fixture",
        "filename": "fixture.mp4",
        "split_role": "TRAIN",
        "official_split": "train",
        "file_size_bytes": len(source),
        "official_md5": hashlib.md5(source, usedforsecurity=False).hexdigest(),
        "direct_download_url": "https://example.invalid/fixture",
    }
    folder = tmp_path / "videos"
    folder.mkdir()
    (folder / "fixture.mp4.download").write_bytes(b"interrupted")
    monkeypatch.setattr(foundation, "ADMISSION", tmp_path / "unused")
    monkeypatch.setattr(foundation.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(source))
    result = foundation.acquire(tmp_path, [row])
    assert (folder / "fixture.mp4").read_bytes() == source
    assert result[0]["sha256"] == hashlib.sha256(source).hexdigest()
    assert (
        next((tmp_path / "recovery").rglob("fixture.mp4.download")).read_bytes() == b"interrupted"
    )


def test_bad_download_never_published_as_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = {
        "sample_id": "bad",
        "filename": "bad.mp4",
        "split_role": "DEV",
        "official_split": "validation",
        "file_size_bytes": 3,
        "official_md5": "00000000000000000000000000000000",
        "direct_download_url": "invalid",
    }
    monkeypatch.setattr(foundation, "ADMISSION", tmp_path / "unused")
    monkeypatch.setattr(foundation.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"bad"))
    with pytest.raises(ValueError, match="MD5"):
        foundation.acquire(tmp_path, [row])
    assert not (tmp_path / "videos/bad.mp4").exists()
    assert (tmp_path / "videos/bad.mp4.download").exists()


def test_serial_runner_failure_resume_no_duplicate_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [
        {"sample_id": s, "split_role": "TRAIN" if s == "train" else "DEV"} for s in ["train", "dev"]
    ]
    plan = {
        "manifest_sha256": tranche.EXECUTION["frozen_manifest_sha256"],
        "batches": [{"role": r["split_role"], "sample_ids": [r["sample_id"]]} for r in rows],
    }
    (tmp_path / "batch_plan.json").write_text(json.dumps(plan))
    completed: set[str] = set()
    extractions: list[str] = []
    fault = {"enabled": True}
    monkeypatch.setattr(tranche, "single_writer", lambda output: contextlib.nullcontext())
    monkeypatch.setattr(tranche, "preflight", lambda output: {})
    monkeypatch.setattr(tranche, "frozen_rows", lambda output: rows)
    monkeypatch.setattr(tranche, "inventory", lambda output: {"complete": sorted(completed)})
    monkeypatch.setattr(tranche, "acquire", lambda output, values: None)

    def extract(output: Path, values: list[dict[str, Any]], cache: dict[str, Any]) -> None:
        sid = values[0]["sample_id"]
        if sid == "dev" and fault["enabled"]:
            raise ValueError("explicit fixture failure")
        completed.add(sid)
        extractions.append(sid)
        write_json_atomic(output / "features" / f"{sid}.receipt.json", {"fixture": True})

    monkeypatch.setattr(tranche, "extract", extract)

    def validated(output: Path, manifest: Path) -> dict[str, Any]:
        return {
            "ready_to_train": len(completed) == 2,
            "structural_pass": True,
            "validated_sequences": len(completed),
            "statistics": {
                "TRAIN": {"sequences": int("train" in completed)},
                "DEV": {"sequences": int("dev" in completed)},
            },
        }

    monkeypatch.setattr(tranche, "validate", validated)
    first = tranche.prepare_tranche(tmp_path)
    assert first["status"] == "TRANCHE_INCOMPLETE"
    assert "dev" in first["failures"]
    fault["enabled"] = False
    second = tranche.prepare_tranche(tmp_path)
    assert second["status"] == "TRANCHE_MATERIALIZED_READY_TO_TRAIN"
    assert second["failures"] == {} and extractions == ["train", "dev"]


def test_training_guard_refuses_incomplete_real_tranche(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from model import fingerspelling_ctc

    output = REPO / "datasets/fingerspelling/foundation_01"
    if not (output / "tranche_manifest.json").is_file():
        pytest.skip("Local FSboard foundation absent")
    # The real package may now be complete; the guard test must never launch training.
    monkeypatch.setattr(
        fingerspelling_ctc,
        "validate",
        lambda *args: {"ready_to_train": False, "readiness_blockers": ["fixture incomplete"]},
    )
    with pytest.raises(ValueError, match="Dataset not ready"):
        train(output, tmp_path / "must-not-start", CONFIG_PATH)
    assert not (tmp_path / "must-not-start").exists()


def test_preflight_disk_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil

    from tools.fingerspelling.foundation import DEFAULT_OUTPUT

    original = shutil.disk_usage
    monkeypatch.setattr(tranche.shutil, "disk_usage", lambda path: original(path)._replace(free=1))
    with pytest.raises(ValueError, match="Free space"):
        tranche.preflight(DEFAULT_OUTPUT)


def test_completed_raw_features_resume_without_candidate_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pipeline.perception_vnext import offline_candidate01

    output = foundation.DEFAULT_OUTPUT
    m = json.loads((output / "tranche_manifest.json").read_text())
    rec = next((output / "features").glob("fsboard-v13-validation*.receipt.json"), None)
    if rec is None:
        pytest.skip("Bounded real DEV check not present")
    sid = json.loads(rec.read_text())["sample_id"]
    row = next(r for r in m["samples"] if r["sample_id"] == sid)

    def forbid(*args: object, **kwargs: object) -> None:
        raise AssertionError("Completed verified features must not initialize Candidate01")

    monkeypatch.setattr(offline_candidate01, "Candidate01Offline", forbid)
    before = rec.read_bytes()
    result = foundation.extract(output, [row])
    assert result[0]["sample_id"] == sid and rec.read_bytes() == before
