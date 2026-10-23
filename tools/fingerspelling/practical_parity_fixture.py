"""Export decision-layer parity traces (Python replay port -> Kotlin HeldLetterPolicy JVM test).

Each trace is the exact observe/request/accept call sequence the replay made on a real DEV
(FSboard validation) or IPN Hand raw stream, with the Python outputs. The Kotlin test must
reproduce every output. Only usability flags, timestamps and decoded letters are stored:
no landmarks, pixels or model inputs.

    python -m tools.fingerspelling.practical_parity_fixture --out <json>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from pipeline.fingerspelling import adapter
from pipeline.perception_vnext.recognition_schema import load_raw_sequence
from tools.fingerspelling.practical_replay import (
    IPN_DIR,
    RAW_DIR,
    VARIANTS,
    Model,
    Policy,
    decode_result,
    usable,
)


def trace_clip(raw, stream, config, decode, latency_ms: float) -> list:
    """Same discrete-event loop as practical_replay.run_clip, recording every policy call."""
    policy = Policy(config, raw)
    pending = None
    events: list = []
    for i in stream:
        t = float(raw.timestamp_ms[i])
        if pending is not None and pending[0] <= t:
            _, epoch, t_last, letter = pending
            pending = None
            before = dict(policy.reasons)
            accepted = policy.accept(epoch, t_last, letter)
            reason = next(k for k in policy.reasons if policy.reasons[k] != before.get(k, 0))
            events.append(["a", epoch, t_last, letter, accepted, reason, policy.preview])
        policy.observe(int(i))
        events.append(["o", t, usable(raw, int(i)), policy.epoch])
        if pending is not None:
            continue
        window = policy.request()
        events.append(["r", t, None if window is None else len(window)])
        if window is None:
            continue
        letter = decode(tuple(window))["text"]
        pending = (t + latency_ms, policy.epoch, policy.t(window[-1]), letter)
    return events


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    model = Model()
    # Two ordinary DEV clips, two where the practical fix changes the outcome, two IPN negatives.
    chosen = (
        "0092c5e7f247930e71d9",
        "061478bdc422a8ab10b1",
        "0f1436470fbdfefa036f",
        "d418eb3225ba8147c07f",
    )
    sources = [RAW_DIR / f"fsboard-v13-validation-{c}.raw-v1.npz" for c in chosen]
    sources += sorted(IPN_DIR.glob("*.npz"))[:2]
    traces = []
    for path in sources:
        raw = load_raw_sequence(path)
        stream = adapter.phone_indices(raw.timestamp_ms)
        cache: dict = {}

        def decode(window, raw=raw, cache=cache):
            if window not in cache:
                cache[window] = decode_result(model, raw, window)
            return cache[window]

        for name in ("V0_BASELINE", "V1_EVIDENCE_ACCEPT"):
            events = trace_clip(raw, stream, VARIANTS[name], decode, 200.0)
            traces.append(
                {
                    "source": path.name.split(".")[0],
                    "variant": name,
                    "accept_while_hand_missing": VARIANTS[name].accept_while_missing,
                    "events": events,
                }
            )
            print(path.name, name, sum(e[0] == "a" and e[4] for e in events), "appends")
    doc = {
        "schema_version": "apphear.fingerspelling.practical_parity_traces.v1",
        "policy": {
            "window_ms": 4000,
            "minimum_span_ms": 1000,
            "minimum_usable": 4,
            "inference_interval_ms": 500,
            "stable_decodes": 3,
            "stable_span_ms": 1000,
            "rearm_missing_ms": 800,
            "rearm_missing_observations": 3,
            "maximum_observations": 64,
        },
        "latency_ms": 200.0,
        "contains_landmarks_or_pixels": False,
        "traces": traces,
    }
    args.out.write_text(json.dumps(doc, separators=(",", ":")))
    print(
        args.out,
        sum(len(t["events"]) for t in traces),
        "events",
        np.round(args.out.stat().st_size / 1024),
        "KiB",
    )


if __name__ == "__main__":
    main()
