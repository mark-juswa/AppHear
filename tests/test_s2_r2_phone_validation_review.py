"""Exact phone-review labels join to the same captured tensor observations."""

from __future__ import annotations

import csv
import json

from eval.runtime_diagnostics.s2_r2_phone_validation_review import finalize_linkage


def test_review_linkage_accepts_float_millisecond_rounding(tmp_path):
    session = tmp_path / "session_test"
    parity = session / "s2_exact_parity"
    parity.mkdir(parents=True)
    output = tmp_path / "review"
    output.mkdir()
    timestamps_ns = [815_042_529_122_907 + index * 200_000_017 for index in range(6)]
    with (parity / "linkage.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["record_index", "timestamp_ms"])
        writer.writeheader()
        for index, timestamp_ns in enumerate(timestamps_ns):
            writer.writerow(
                {"record_index": index, "timestamp_ms": f"{timestamp_ns / 1_000_000:.5f}"}
            )
    with (output / "phone_positive_observation_labels.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["attempt_ordinal", "source_timestamp_ns", "state_name"],
        )
        writer.writeheader()
        for index, timestamp_ns in enumerate(timestamps_ns, 1):
            writer.writerow(
                {
                    "attempt_ordinal": index,
                    "source_timestamp_ns": timestamp_ns,
                    "state_name": "ACTIVE_SIGN",
                }
            )
    (output / "phone_positive_temporal_review_summary.json").write_text(
        json.dumps(
            {
                "attempt_summaries": [
                    {"attempt_id": f"attempt_{index:03d}", "ambiguous": False}
                    for index in range(1, 7)
                ]
            }
        ),
        encoding="utf-8",
    )
    result = json.loads(
        finalize_linkage(session, output, distinct_signer=True).read_text(encoding="utf-8")
    )
    assert result["distinct_signer_attested_from_fit_and_checkpoint_selection"] is True
    assert [attempt["segments"][0]["start_index"] for attempt in result["attempts"]] == list(
        range(6)
    )
