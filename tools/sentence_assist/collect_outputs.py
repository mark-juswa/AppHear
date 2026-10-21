"""Collect sentence-assist renderings for the offline evaluation (Phase 2 step 6).

Sends each prompt exported by the Android JVM test (`SentenceAssistEvalTest`, written to
`android/app/build/sentence_assist_eval/prompts_<version>.jsonl`) verbatim to the same Gemini
endpoint the app uses, and records raw replies to `eval/sentence_assist/runs/<run>/outputs.jsonl`.
Scoring happens in Kotlin with the shipped validator; this script never judges outputs.

The API key is read from an environment variable (default APPHEAR_GEMINI_API_KEY) and is never
written to disk or logs. Example:

    python -m tools.sentence_assist.collect_outputs \
        android/app/build/sentence_assist_eval/prompts_v1.jsonl eval/sentence_assist/runs/<run>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
POLICY = Path("android/app/src/main/assets/sentence_assist/policy_v1.json")


def request_body(prompt: dict[str, Any]) -> dict[str, Any]:
    """Identical shape to GeminiSentenceRenderer's request."""
    return {
        "model": prompt["model"],
        "store": False,
        "system_instruction": prompt["systemInstruction"],
        "input": prompt["input"],
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": prompt["responseSchema"],
        },
    }


def parse_response(response: dict[str, Any]) -> dict[str, Any] | None:
    """Model JSON from a completed interaction, mirroring GeminiSentenceRenderer.parse."""
    if response.get("status") != "completed":
        return None
    for step in response.get("steps") or []:
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        for item in step.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text":
                parsed = json.loads(item["text"])
                return parsed if isinstance(parsed, dict) else None
    return None


def record(
    prompt: dict[str, Any],
    status: str,
    output: dict[str, Any] | None,
    latency_ms: int | None,
    http_status: int | None,
) -> dict[str, Any]:
    return {
        "id": prompt["id"],
        "promptVersion": prompt["promptVersion"],
        "model": prompt["model"],
        "status": status,
        "sentence": (output or {}).get("sentence"),
        "substitutions": (output or {}).get("substitutions"),
        "latencyMs": latency_ms,
        "httpStatus": http_status,
    }


def call(prompt: dict[str, Any], api_key: str, timeout_s: float) -> dict[str, Any]:
    data = json.dumps(request_body(prompt)).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT,
        data=data,
        method="POST",
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = json.loads(response.read().decode("utf-8"))
            latency = int((time.monotonic() - started) * 1000)
            try:
                output = parse_response(body)
            except (json.JSONDecodeError, KeyError, TypeError):
                return record(prompt, "parse_error", None, latency, response.status)
            status = "ok" if output is not None else "incomplete"
            return record(prompt, status, output, latency, response.status)
    except urllib.error.HTTPError as error:
        return record(
            prompt, "http_error", None, int((time.monotonic() - started) * 1000), error.code
        )
    except TimeoutError:
        return record(prompt, "timeout", None, int((time.monotonic() - started) * 1000), None)
    except urllib.error.URLError as error:
        status = "timeout" if isinstance(error.reason, TimeoutError) else "network_error"
        return record(prompt, status, None, int((time.monotonic() - started) * 1000), None)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("prompts", type=Path)
    parser.add_argument("out_dir", type=Path, help="New directory under eval/sentence_assist/runs/")
    parser.add_argument("--api-key-env", default="APPHEAR_GEMINI_API_KEY")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--pause-ms", type=int, default=250)
    args = parser.parse_args(argv)

    api_key = os.environ.get(args.api_key_env, "")
    if not api_key:
        print(f"Set {args.api_key_env} to a Gemini key first.", file=sys.stderr)
        return 2
    timeout_s = json.loads(POLICY.read_text(encoding="utf-8"))["renderTimeoutMs"] / 1000
    prompts = [
        json.loads(line) for line in args.prompts.read_text(encoding="utf-8").splitlines() if line
    ]
    if args.limit is not None:
        prompts = prompts[: args.limit]
    args.out_dir.mkdir(parents=True, exist_ok=False)
    statuses: dict[str, int] = {}
    with (args.out_dir / "outputs.jsonl").open("w", encoding="utf-8") as out:
        for repeat in range(args.repeats):
            for index, prompt in enumerate(prompts, 1):
                result = call(prompt, api_key, timeout_s)
                result["repeat"] = repeat
                out.write(json.dumps(result) + "\n")
                out.flush()
                statuses[result["status"]] = statuses.get(result["status"], 0) + 1
                print(f"[{repeat}:{index}/{len(prompts)}] {prompt['id']} {result['status']}")
                time.sleep(args.pause_ms / 1000)
    run = {
        "prompts": str(args.prompts),
        "promptVersion": prompts[0]["promptVersion"] if prompts else None,
        "model": prompts[0]["model"] if prompts else None,
        "repeats": args.repeats,
        "count": len(prompts) * args.repeats,
        "statuses": statuses,
        "timeoutS": timeout_s,
        "finishedUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (args.out_dir / "run.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    print(json.dumps(run, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
