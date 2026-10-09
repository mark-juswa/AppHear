from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from eval.runtime_diagnostics.phase5_1t_bounded_seed_dataset import (
    ANNOTATION_SCHEMA,
    EXPECTED_TOTAL,
    SPLIT_SCHEMA,
    _empty_annotation_document,
    _freeze_json,
    _reused_annotation,
    choose_dev_signers,
    commit_annotation,
    derive_temporal_rows,
    deterministic_selection,
    public_state,
    validate_annotation_input,
    validate_governed_train_population,
    validate_selected_rows,
)
from pipeline.perception_vnext.governance import EXPECTED


def _audit_row(
    index: int,
    *,
    source: str,
    signer: str,
    gloss: str,
    pre: float = 800.0,
    post: float = 1200.0,
) -> dict[str, str]:
    sample_id = f"sample-{source}-{index:04d}"
    return {
        "sample_id": sample_id,
        "source": source,
        "signer_id": signer,
        "gloss": gloss,
        "class_id": str(index % 236),
        "resolved_raw_video_path": f"X:/{sample_id}.mp4",
        "resolved_span_path": f"X:/{sample_id}.span.json" if source == "ASL_CITIZEN" else "",
        "raw_video_duration_ms": "3000.0",
        "video_readable": "True",
        "context_valid": "True" if source == "ASL_CITIZEN" else "False",
        "pre_context_ms": str(pre) if source == "ASL_CITIZEN" else "",
        "post_context_ms": str(post) if source == "ASL_CITIZEN" else "",
        "active_span_duration_ms": str(500 + (index % 9) * 140) if source == "ASL_CITIZEN" else "",
    }


def _candidate_pool() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index in range(640):
        rows.append(
            _audit_row(
                index,
                source="ASL_CITIZEN",
                signer=f"asl:P{index % 32:02d}",
                gloss=f"G{index % 236:03d}",
            )
        )
    for index in range(60):
        rows.append(
            _audit_row(
                1000 + index,
                source="APPHEAR_CAPTURE",
                signer="local:APPHEAR",
                gloss=f"A{index % 5}",
            )
        )
    for index in range(120):
        rows.append(
            _audit_row(
                2000 + index,
                source="LOCAL",
                signer=f"local:L{index % 4}",
                gloss=f"L{index % 12}",
            )
        )
    return rows


def _selected_rows() -> list[dict[str, object]]:
    raw = deterministic_selection(_candidate_pool())
    dev_signers, _ = choose_dev_signers(raw)
    result: list[dict[str, object]] = []
    for index, row in enumerate(raw):
        result.append(
            {
                "sample_id": row["sample_id"],
                "source": row["source"],
                "signer_id": row["signer_id"],
                "gloss": row["gloss"],
                "class_id": int(row["class_id"]),
                "source_video_path": row["resolved_raw_video_path"],
                "video_duration_ms": 3000.0,
                "segmentation_split": (
                    "SEGMENTATION_DEV"
                    if row["signer_id"] in dev_signers
                    else "SEGMENTATION_TRAIN"
                ),
                "selection_rank": index,
                "governed_d1_span_path": row["resolved_span_path"] or None,
            }
        )
    return result


def test_selection_is_deterministic_bounded_and_source_exact() -> None:
    first = deterministic_selection(_candidate_pool())
    second = deterministic_selection(list(reversed(_candidate_pool())))
    assert [row["sample_id"] for row in first] == [row["sample_id"] for row in second]
    assert len(first) == EXPECTED_TOTAL == 120
    counts = {
        source: sum(row["source"] == source for row in first)
        for source in {row["source"] for row in first}
    }
    assert counts == {"ASL_CITIZEN": 90, "APPHEAR_CAPTURE": 12, "LOCAL": 18}
    assert len({row["signer_id"] for row in first if row["source"] == "ASL_CITIZEN"}) >= 18
    assert max(
        sum(other["signer_id"] == row["signer_id"] for other in first)
        for row in first
        if row["source"] == "ASL_CITIZEN"
    ) <= 6


def test_asl_selection_rejects_insufficient_candidate_room() -> None:
    pool = _candidate_pool()
    for row in pool:
        if row["source"] == "ASL_CITIZEN":
            row["pre_context_ms"] = "499"
    with pytest.raises(RuntimeError, match="INSUFFICIENT_DIVERSE_CANDIDATES"):
        deterministic_selection(pool)


def test_segmentation_split_has_zero_signer_overlap_and_apphear_stays_train() -> None:
    rows = _selected_rows()
    validate_selected_rows(rows, {str(row["sample_id"]) for row in rows})
    train_signers = {
        row["signer_id"]
        for row in rows
        if row["segmentation_split"] == "SEGMENTATION_TRAIN"
    }
    dev_signers = {
        row["signer_id"]
        for row in rows
        if row["segmentation_split"] == "SEGMENTATION_DEV"
    }
    assert not train_signers & dev_signers
    assert sum(str(signer).startswith("asl:") for signer in dev_signers) >= 3
    assert any(str(signer).startswith("local:L") for signer in dev_signers)
    assert all(
        row["segmentation_split"] == "SEGMENTATION_TRAIN"
        for row in rows
        if row["source"] == "APPHEAR_CAPTURE"
    )


def test_train_population_rejects_dev_or_protected_membership() -> None:
    audit = [
        {"sample_id": f"sample-{index}", "resolved_raw_video_path": f"X:/{index}.mp4"}
        for index in range(EXPECTED["train_clips"])
    ]
    train = [
        {
            "sample_id": row["sample_id"],
            "split": "train",
            "role": "primary_train",
            "training_eligible": "true",
        }
        for row in audit
    ]
    validate_governed_train_population(audit, train)
    train[0]["split"] = "val"
    with pytest.raises(RuntimeError, match="PROTECTED_OR_NONTRAIN_POPULATION_REJECTED"):
        validate_governed_train_population(audit, train)


def test_duplicate_and_outside_train_selection_rejected() -> None:
    rows = _selected_rows()
    train_ids = {str(row["sample_id"]) for row in rows}
    rows[1]["sample_id"] = rows[0]["sample_id"]
    with pytest.raises(RuntimeError, match="DUPLICATE_SELECTED_SAMPLE"):
        validate_selected_rows(rows, train_ids)


def test_frozen_manifest_identity_refuses_change(tmp_path: Path) -> None:
    path = tmp_path / "frozen.json"
    _freeze_json(path, {"schema": SPLIT_SCHEMA, "rows": [1]})
    original = path.read_bytes()
    _freeze_json(path, {"schema": SPLIT_SCHEMA, "rows": [1]})
    assert path.read_bytes() == original
    with pytest.raises(RuntimeError, match="FROZEN_ARTIFACT_MISMATCH"):
        _freeze_json(path, {"schema": SPLIT_SCHEMA, "rows": [2]})


@pytest.mark.parametrize(
    "payload",
    [
        {"human_sign_start_ms": -1, "human_sign_end_ms": 100, "ambiguous_or_unusable": False},
        {"human_sign_start_ms": 100, "human_sign_end_ms": 100, "ambiguous_or_unusable": False},
        {"human_sign_start_ms": 100, "human_sign_end_ms": 3001, "ambiguous_or_unusable": False},
    ],
)
def test_annotation_boundary_validation(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="INVALID_BOUNDARY"):
        validate_annotation_input(payload, 3000.0)


def test_temporal_geometry_is_authoritative_and_ambiguous_is_not_supervised() -> None:
    rows = _selected_rows()[:2]
    document = {
        "annotations": [
            {
                "sample_id": rows[0]["sample_id"],
                "human_sign_start_ms": 300.0,
                "human_sign_end_ms": 2500.0,
                "ambiguous_or_unusable": False,
                "annotation_reused_from_phase5_1t_1": False,
                "reviewer_note": "",
            },
            {
                "sample_id": rows[1]["sample_id"],
                "human_sign_start_ms": None,
                "human_sign_end_ms": None,
                "ambiguous_or_unusable": True,
                "annotation_reused_from_phase5_1t_1": False,
                "reviewer_note": "",
            },
        ]
    }
    derived = derive_temporal_rows(rows, document)
    assert derived[0]["actual_pre_margin_ms"] == pytest.approx(300.0)
    assert derived[0]["actual_post_margin_ms"] == pytest.approx(500.0)
    assert derived[0]["pre_context_available"] is True
    assert derived[0]["post_context_available"] is True
    assert derived[1]["usable_for_supervision"] is False
    assert derived[1]["actual_pre_margin_ms"] is None


def test_reused_annotation_copies_only_authoritative_fields_unchanged() -> None:
    row = _selected_rows()[0]
    prior = {
        "sample_id": row["sample_id"],
        "source": row["source"],
        "signer_id": row["signer_id"],
        "gloss": row["gloss"],
        "human_sign_start_ms": 321.0,
        "human_sign_end_ms": 1234.0,
        "ambiguous_or_unusable": False,
        "clear_pre_context": False,
        "clear_post_recovery_context": False,
        "reviewer_note": "historical",
        "review_timestamp": "2026-09-16T00:00:00+00:00",
        "schema": "apphear.phase5_1t.human_temporal_annotations.v1",
        "tool_version": "old",
        "d1_onset_ms": 100.0,
        "d1_release_ms": 900.0,
        "human_minus_d1_start_ms": 221.0,
        "human_minus_d1_end_ms": 334.0,
    }
    reused = _reused_annotation(row, prior)
    assert reused["human_sign_start_ms"] == 321.0
    assert reused["human_sign_end_ms"] == 1234.0
    assert reused["ambiguous_or_unusable"] is False
    assert reused["annotation_reused_from_phase5_1t_1"] is True
    assert "clear_pre_context" not in reused
    assert "clear_post_recovery_context" not in reused


def test_d1_is_hidden_before_new_human_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = _selected_rows()[0]
    span = tmp_path / "span.json"
    span.write_text(
        json.dumps({"onset": 10, "release": 20, "native_fps": 10.0, "valid": True}),
        encoding="utf-8",
    )
    row["governed_d1_span_path"] = str(span)
    annotation_path = tmp_path / "annotations.json"
    # Avoid loading the real historical package in this isolated fixture.
    monkeypatch.setattr(
        "eval.runtime_diagnostics.phase5_1t_bounded_seed_dataset._load_prior_annotations",
        lambda: ({}, "prior-sha"),
    )
    document = _empty_annotation_document(
        manifest_sha256="manifest-sha", split_sha256="split-sha", rows=[row]
    )
    annotation_path.write_text(json.dumps(document), encoding="utf-8")
    metadata = [{"duration_ms": 3000.0, "fps": 30.0, "frame_count": 90}]
    state = public_state([row], document, metadata)
    serialized = json.dumps(state["samples"][0])
    assert "d1_onset_ms" not in serialized
    assert "governed_d1_span_path" not in serialized
    committed = commit_annotation(
        rows=[row],
        annotation_path=annotation_path,
        manifest_sha256="manifest-sha",
        split_sha256="split-sha",
        sample_index=0,
        payload={
            "human_sign_start_ms": 1200.0,
            "human_sign_end_ms": 2300.0,
            "ambiguous_or_unusable": False,
            "reviewer_note": "approximate",
        },
        video_metadata=metadata,
        now=datetime(2026, 9, 16, tzinfo=UTC),
    )
    assert committed["d1_onset_ms"] == pytest.approx(1000.0)
    assert committed["d1_release_ms"] == pytest.approx(2100.0)
    assert committed["schema"] == ANNOTATION_SCHEMA


def test_module_does_not_import_or_invoke_recognizer_or_training() -> None:
    path = Path("eval/runtime_diagnostics/phase5_1t_bounded_seed_dataset.py")
    source = path.read_text(encoding="utf-8")
    assert "import tensorflow" not in source
    assert "import keras" not in source
    assert "Recognizer(" not in source
    assert ".fit(" not in source
