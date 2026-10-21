"""Sentence-assist offline tooling: request/response shape and the evaluation case set."""

from __future__ import annotations

import json
from typing import Any

from tools.sentence_assist import build_cases
from tools.sentence_assist.collect_outputs import parse_response, record, request_body

PROMPT: dict[str, Any] = {
    "id": "pronoun-02",
    "promptVersion": "v1",
    "model": "gemini-3.5-flash-lite",
    "systemInstruction": "system",
    "input": "signs",
    "responseSchema": {"type": "object"},
}


def test_request_body_matches_the_app_transport() -> None:
    assert request_body(PROMPT) == {
        "model": "gemini-3.5-flash-lite",
        "store": False,
        "system_instruction": "system",
        "input": "signs",
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": {"type": "object"},
        },
    }


def test_parse_response_reads_the_first_model_text() -> None:
    model_json = {"sentence": "I'm tired.", "substitutions": []}
    response = {
        "status": "completed",
        "steps": [
            {"type": "thought"},
            {"type": "model_output", "content": [{"type": "text", "text": json.dumps(model_json)}]},
        ],
    }
    assert parse_response(response) == model_json
    assert parse_response({"status": "in_progress", "steps": []}) is None
    assert parse_response({"status": "completed", "steps": []}) is None


def test_record_keeps_raw_fields_without_judging() -> None:
    output = {"sentence": "I'm good.", "substitutions": [{"signNumber": 1, "gloss": "GOOD"}]}
    row = record(PROMPT, "ok", output, 812, 200)
    assert row["sentence"] == "I'm good."
    assert row["substitutions"] == [{"signNumber": 1, "gloss": "GOOD"}]
    assert record(PROMPT, "timeout", None, 8000, None)["sentence"] is None


def test_case_set_is_deterministic_and_covers_every_category() -> None:
    first = build_cases.build()
    assert first == build_cases.build()
    categories = {case["category"] for case in first}
    assert {
        "clean",
        "question",
        "pronoun",
        "noisy_real",
        "context_mismatch",
        "swap_help",
        "swap_decoy",
        "perturbed_insert",
        "perturbed_substitute",
        "perturbed_delete",
    } <= categories
    real = {case["id"]: case for case in first if case["category"] == "noisy_real"}
    assert real["real-t01"]["intendedByEvent"] == ["GO", "HOME", None, None]
    assert real["real-t01"]["glosses"] == ["GIFT", "HOME", "GIVE", "COME"]
