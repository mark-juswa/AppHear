"""Headless tests for the resumable E2 crop-review utility."""

from __future__ import annotations

import csv
from pathlib import Path

from pipeline.crops.review import (
    AUDIT_FIELDS,
    DECISION_BY_KEY,
    apply_decision,
    audit_status,
    is_complete,
    load_rows,
    save_rows_atomic,
    validate_rows,
)


def _row(panel_path: Path, crop_id: str = "abc") -> dict[str, str]:
    return {
        "crop_id": crop_id,
        "panel_path": str(panel_path),
        "visible_hand": "",
        "usable": "",
        "failure_reason": "",
        "notes": "",
    }


def test_decisions_match_audit_contract(tmp_path: Path) -> None:
    row = _row(tmp_path / "panel.jpg")
    apply_decision(row, DECISION_BY_KEY["0"], "")
    assert is_complete(row)
    assert row["visible_hand"] == "no" and row["usable"] == ""

    apply_decision(row, DECISION_BY_KEY["1"], "clear")
    assert row["visible_hand"] == "yes" and row["usable"] == "yes"
    assert row["notes"] == "clear"

    apply_decision(row, DECISION_BY_KEY["4"], "")
    assert row["visible_hand"] == "yes" and row["usable"] == "no"
    assert row["failure_reason"] == "motion_blur"


def test_atomic_save_roundtrip_and_resume_status(tmp_path: Path) -> None:
    panel = tmp_path / "panel.jpg"
    panel.write_bytes(b"test")
    rows = [_row(panel, "a"), _row(panel, "b")]
    apply_decision(rows[0], DECISION_BY_KEY["1"], "")
    template = tmp_path / "audit_template.csv"
    save_rows_atomic(template, rows)
    loaded = load_rows(template)
    assert audit_status(loaded) == {"total": 2, "completed": 1, "remaining": 1}
    assert not template.with_suffix(".csv.tmp").exists()


def test_validation_rejects_missing_and_duplicate_panels(tmp_path: Path) -> None:
    missing = tmp_path / "missing.jpg"
    errors = validate_rows([_row(missing, "same"), _row(missing, "same")])
    assert any("panel missing" in error for error in errors)
    assert any("duplicate crop_id" in error for error in errors)


def test_loader_rejects_changed_columns(tmp_path: Path) -> None:
    template = tmp_path / "audit_template.csv"
    with template.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=(*AUDIT_FIELDS, "unexpected"))
        writer.writeheader()
    try:
        load_rows(template)
    except ValueError as error:
        assert "expected columns" in str(error)
    else:
        raise AssertionError("changed audit columns must be rejected")
