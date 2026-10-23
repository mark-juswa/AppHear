"""Offline end-to-end replay of the continuous FINGERSPELL decision layer.

Real Candidate01 raw streams (FSboard DEV / official validation, never TEST) are
sub-sampled with the frozen phone cadence gate, fed observation by observation
through an exact Python port of the Android ``HeldLetterPolicy`` (and its
FINGERSPELL-only practical variant), with the single async worker of
``ContinuousFingerspell`` modelled by a fixed result latency. Every requested
window is re-derived with the frozen Adapter v1 and run through the frozen
V2.1 epoch034 TFLite model and the exact singleton CTC decoder.

Research/evaluation only: no training, no admission, no model or asset change.
Usage (repo .venv, from the repository root):
    python -m tools.fingerspelling.practical_replay --out <dir> [--limit N]
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

from model.fingerspelling_single_letter import decode_single_letter
from pipeline.fingerspelling import adapter
from pipeline.perception_vnext.recognition_schema import load_raw_sequence

DATA_ROOT = Path("F:/ASL DATASET/5. Apphear3/datasets/fingerspelling")
RAW_DIR = DATA_ROOT / "foundation_01/raw"
PACKAGE = Path("packages/fingerspelling_continuous_v2_1_01/android_assets/fingerspelling")


@dataclass(frozen=True)
class PolicyConfig:
    window_ms: float = 4000
    minimum_span_ms: float = 1000
    minimum_usable: int = 4
    inference_interval_ms: float = 500
    stable_decodes: int = 3
    stable_span_ms: float = 1000
    rearm_missing_ms: float = 800
    rearm_missing_observations: int = 3
    maximum_observations: int = 64
    # Practical variant switches (False == byte-identical baseline semantics).
    accept_while_missing: bool = False
    trim_on_latch: bool = False
    # Decision-layer evidence gate on the frozen singleton masses (-inf == baseline):
    # a decode whose best letter does not beat max(empty, SPACE) by this log margin is a refusal.
    minimum_margin: float = -math.inf


def usable(raw, i: int) -> bool:
    return bool(any(raw.hand_observed[i, s] and raw.hand_joint_valid[i, s].any() for s in range(2)))


@dataclass
class Policy:
    """Line-by-line port of android/.../fingerspelling/HeldLetterPolicy.kt."""

    config: PolicyConfig
    raw: object
    observations: list = field(default_factory=list)  # indices into raw
    last_timestamp: float | None = None
    last_request: float = -math.inf
    missing_start: float | None = None
    missing_count: int = 0
    rearmed_during_absence: bool = False
    latch_survives_absence: bool = False
    candidate: str = ""
    candidate_start: float = 0.0
    candidate_count: int = 0
    last_decision: float = -math.inf
    latch: str = ""
    epoch: int = 0
    preview: str = ""
    rearms: int = 0
    reasons: dict = field(default_factory=dict)

    @property
    def waiting_for_hand(self) -> bool:
        return self.missing_count > 0

    def t(self, i: int) -> float:
        return float(self.raw.timestamp_ms[i])

    def reset_candidate(self) -> None:
        self.candidate, self.candidate_count, self.last_decision = "", 0, -math.inf

    def observe(self, i: int) -> None:
        t = self.t(i)
        assert self.last_timestamp is None or t > self.last_timestamp
        self.last_timestamp = t
        if usable(self.raw, i):
            self.missing_start, self.missing_count, self.rearmed_during_absence = None, 0, False
            self.latch_survives_absence = False
        else:
            if self.missing_start is None:
                self.missing_start = t
            self.missing_count += 1
            if (
                not self.rearmed_during_absence
                and self.missing_count >= self.config.rearm_missing_observations
                and t - self.missing_start >= self.config.rearm_missing_ms
            ):
                self.observations.clear()
                if not self.latch_survives_absence:
                    self.latch = ""
                self.epoch += 1
                self.reset_candidate()
                self.rearmed_during_absence = True
                self.rearms += 1
        if not self.rearmed_during_absence:
            self.observations.append(i)
        while self.observations and (
            t - self.t(self.observations[0]) > self.config.window_ms
            or len(self.observations) > self.config.maximum_observations
        ):
            self.observations.pop(0)

    def request(self):
        c = self.config
        if self.waiting_for_hand or len(self.observations) < c.minimum_usable:
            return None
        t = self.t(self.observations[-1])
        if (
            t - self.last_request < c.inference_interval_ms
            or t - self.t(self.observations[0]) < c.minimum_span_ms
            or sum(usable(self.raw, i) for i in self.observations) < c.minimum_usable
        ):
            return None
        self.last_request = t
        return list(self.observations)

    def _reason(self, r: str) -> None:
        self.reasons[r] = self.reasons.get(r, 0) + 1

    def accept(self, request_epoch: int, t: float, letter: str) -> bool:
        c = self.config
        if request_epoch != self.epoch:
            self._reason("STALE_EPOCH")
            return False
        if self.waiting_for_hand and not c.accept_while_missing:
            self._reason("HAND_CURRENTLY_MISSING")
            return False
        if t <= self.last_decision:
            self._reason("OUT_OF_ORDER_RESULT")
            return False
        self.last_decision = t
        if not letter or letter == self.latch:
            self._reason("EMPTY_DECODE" if not letter else "SAME_AS_LATCH")
            if letter and c.trim_on_latch:
                # The decoded window is explained by the latched letter: keep only
                # observations newer than it so the next letter is not diluted.
                self.observations = [i for i in self.observations if self.t(i) > t]
            self.candidate, self.candidate_count = "", 0
            return False
        if letter != self.candidate:
            self.candidate, self.candidate_start, self.candidate_count = letter, t, 1
        else:
            self.candidate_count += 1
        if self.candidate_count < c.stable_decodes:
            self._reason("NEED_MORE_MATCHING_DECODES")
            return False
        if t - self.candidate_start < c.stable_span_ms:
            self._reason("NEED_LONGER_STABLE_SPAN")
            return False
        self._reason("APPENDED")
        self.preview += letter
        self.latch = letter
        if self.waiting_for_hand and c.accept_while_missing:
            self.latch_survives_absence = True
        self.observations.clear()
        self.epoch += 1
        self.reset_candidate()
        return True


class Model:
    def __init__(self) -> None:
        import tensorflow as tf

        self.interpreter = tf.lite.Interpreter(
            model_path=str(PACKAGE / "geometry_sequence.tflite"), num_threads=2
        )
        details = self.interpreter.get_input_details()
        self.packed = next(d["index"] for d in details if d["shape"][-1] == 405)
        self.mask = next(d["index"] for d in details if d["shape"][-1] == 1)
        self.output = self.interpreter.get_output_details()[0]["index"]

    def logits(self, frames: np.ndarray) -> np.ndarray:
        n = len(frames)
        self.interpreter.resize_tensor_input(self.packed, [1, n, 405], strict=False)
        self.interpreter.resize_tensor_input(self.mask, [1, n, 1], strict=False)
        self.interpreter.allocate_tensors()
        self.interpreter.set_tensor(self.packed, frames[None].astype(np.float32))
        self.interpreter.set_tensor(self.mask, np.ones((1, n, 1), np.float32))
        self.interpreter.invoke()
        return np.array(self.interpreter.get_tensor(self.output)[0])


def run_clip(raw, stream: np.ndarray, config: PolicyConfig, decode, latency_ms: float) -> dict:
    """Discrete-event replay of ContinuousFingerspell.consume + worker callback."""
    policy = Policy(config, raw)
    pending = None  # (ready_t, epoch, t_window_last, letter, margin)
    appends = []
    run_margins: list = []  # margins of the consecutive same-letter decodes ending now
    for i in stream:
        t = float(raw.timestamp_ms[i])
        if pending is not None and pending[0] <= t:
            _, epoch, t_last, letter, margin = pending
            pending = None
            if letter and run_margins and run_margins[-1][0] == letter:
                run_margins.append((letter, margin))
            else:
                run_margins = [(letter, margin)] if letter else []
            if policy.accept(epoch, t_last, letter):
                appends.append(
                    {
                        "t": t,
                        "t_window_last": t_last,
                        "letter": letter,
                        "min_margin": min(m for _, m in run_margins[-config.stable_decodes :]),
                    }
                )
                run_margins = []
        policy.observe(int(i))
        if pending is not None:
            continue
        window = policy.request()
        if window is None:
            continue
        result = decode(tuple(window))
        letter = result["text"] if result["margin"] >= config.minimum_margin else ""
        pending = (t + latency_ms, policy.epoch, policy.t(window[-1]), letter, result["margin"])
    return {
        "preview": policy.preview,
        "appends": appends,
        "rearms": policy.rearms,
        "reasons": policy.reasons,
    }


def decode_result(model, raw, window) -> dict:
    frames = adapter.derive(adapter.subset(raw, np.asarray(window, np.int64)))
    r = decode_single_letter(model.logits(frames))
    masses = sorted(r.letter_log_masses, reverse=True)
    return {
        "text": r.text,
        "best": r.best_letter,
        "margin": masses[0] - max(r.empty_log_mass, r.space_log_mass),
        "gap2": masses[0] - masses[1],
    }


def edit_ops(ref: str, hyp: str) -> tuple[int, int, int]:
    n, m = len(ref), len(hyp)
    d = np.zeros((n + 1, m + 1), np.int32)
    d[:, 0] = np.arange(n + 1)
    d[0, :] = np.arange(m + 1)
    for a in range(1, n + 1):
        for b in range(1, m + 1):
            d[a, b] = min(
                d[a - 1, b] + 1, d[a, b - 1] + 1, d[a - 1, b - 1] + (ref[a - 1] != hyp[b - 1])
            )
    s = dl = ins = 0
    a, b = n, m
    while a > 0 or b > 0:
        if a > 0 and b > 0 and d[a, b] == d[a - 1, b - 1] + (ref[a - 1] != hyp[b - 1]):
            s += ref[a - 1] != hyp[b - 1]
            a, b = a - 1, b - 1
        elif a > 0 and d[a, b] == d[a - 1, b] + 1:
            dl += 1
            a -= 1
        else:
            ins += 1
            b -= 1
    return int(s), int(dl), int(ins)


_V1 = PolicyConfig(accept_while_missing=True)
VARIANTS = {
    "V0_BASELINE": PolicyConfig(),
    "V1_EVIDENCE_ACCEPT": _V1,
    "V2_EVIDENCE_ACCEPT_TRIM": replace(_V1, trim_on_latch=True),
    "V3_FAST_2x600": replace(
        _V1, trim_on_latch=True, minimum_span_ms=700, stable_decodes=2, stable_span_ms=500
    ),
    "V4_FAST_3x500": replace(_V1, trim_on_latch=True, minimum_span_ms=700, stable_span_ms=500),
    "V5_WIN2000": replace(_V1, trim_on_latch=True, window_ms=2000),
    **{f"M{m:g}": replace(_V1, minimum_margin=float(m)) for m in (1, 2, 3, 4, 6, 8, 10, 12, 15)},
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--latency-ms", type=float, default=200.0)
    parser.add_argument("--variants", default=",".join(VARIANTS))
    parser.add_argument(
        "--negatives",
        action="store_true",
        help="Replay IPN Hand non-sign gesture clips; every appended letter is false",
    )
    args = parser.parse_args()
    if args.negatives:
        run_negatives(args)
        return
    args.out.mkdir(parents=True, exist_ok=True)
    files = sorted(RAW_DIR.glob("fsboard-v13-validation-*.raw-v1.npz"))
    if args.limit:
        files = files[: args.limit]
    model = Model()
    variants = {k: VARIANTS[k] for k in args.variants.split(",")}
    rows = []
    started = time.time()
    for n, path in enumerate(files):
        sample = path.name.replace(".raw-v1.npz", "")
        receipt = json.loads(
            (DATA_ROOT / "canonical_v2_01/features" / f"{sample}.receipt.json").read_text()
        )
        assert receipt["split_role"] == "DEV" and receipt["official_split"] == "validation"
        ref = "".join(ch for ch in receipt["normalized_transcript"] if "A" <= ch <= "Z")
        meta = receipt["official_metadata"]
        duration = meta["annotationEndTimeS"] - meta["annotationStartTimeS"]
        raw = load_raw_sequence(path)
        stream = adapter.phone_indices(raw.timestamp_ms)
        cache: dict = {}

        def decode(window, raw=raw, cache=cache):
            if window not in cache:
                cache[window] = decode_result(model, raw, window)
            return cache[window]

        row = {
            "sample": sample,
            "signer": receipt["official_signer_id"],
            "ref": ref,
            "letters_per_second": len(ref) / duration if duration > 0 else None,
            "adjacent_repeats": sum(a == b for a, b in zip(ref, ref[1:], strict=False)),
            "stream_observations": len(stream),
            "usable_fraction": float(np.mean([usable(raw, int(i)) for i in stream])),
        }
        for name, config in variants.items():
            result = run_clip(raw, stream, config, decode, args.latency_ms)
            s, d, i = edit_ops(ref, result["preview"])
            row[name] = {
                "hyp": result["preview"],
                "S": s,
                "D": d,
                "I": i,
                "rearms": result["rearms"],
                "reasons": result["reasons"],
                "appends": result["appends"],
                "annotation_ms": [
                    1000 * (meta["annotationStartTimeS"] - meta["clipStartTimeS"]),
                    1000 * (meta["annotationEndTimeS"] - meta["clipStartTimeS"]),
                ],
            }
        row["windows_decoded"] = len(cache)
        rows.append(row)
        if n % 20 == 0:
            print(f"{n + 1}/{len(files)} {time.time() - started:.0f}s", flush=True)
    (args.out / "replay_rows.json").write_text(json.dumps(rows, indent=1))
    print(json.dumps(summarize(rows, list(variants)), indent=1))


IPN_DIR = Path("F:/ASL DATASET/5. Apphear3/artifacts/external/ipn_hand/raw_v1")


def run_negatives(args) -> None:
    """Ordinary non-sign hand movement (IPN Hand gestures + idle): any letter is a false letter."""
    args.out.mkdir(parents=True, exist_ok=True)
    model = Model()
    variants = {k: VARIANTS[k] for k in args.variants.split(",")}
    files = sorted(IPN_DIR.glob("*.npz"))
    if args.limit:
        files = files[: args.limit]
    rows = []
    for path in files:
        raw = load_raw_sequence(path)
        stream = adapter.phone_indices(raw.timestamp_ms)
        cache: dict = {}

        def decode(window, raw=raw, cache=cache):
            if window not in cache:
                cache[window] = decode_result(model, raw, window)
            return cache[window]

        flags = [usable(raw, int(i)) for i in stream]
        row = {
            "clip": path.stem,
            "subject": raw.metadata.get("signer_id"),
            "seconds": float(raw.timestamp_ms[stream[-1]] - raw.timestamp_ms[stream[0]]) / 1000,
            "usable_seconds": float(sum(flags)) / adapter.CONFIG["phone_observations_per_second"],
        }
        for name, config in variants.items():
            result = run_clip(raw, stream, config, decode, args.latency_ms)
            row[name] = {
                "false_letters": result["preview"],
                "rearms": result["rearms"],
                "reasons": result["reasons"],
                "appends": result["appends"],
            }
        rows.append(row)
        print(path.stem, {k: row[k]["false_letters"] for k in variants}, flush=True)
    (args.out / "negative_rows.json").write_text(json.dumps(rows, indent=1))
    minutes = sum(r["seconds"] for r in rows) / 60
    usable_minutes = sum(r["usable_seconds"] for r in rows) / 60
    summary = {"clips": len(rows), "minutes": minutes, "usable_hand_minutes_approx": usable_minutes}
    for name in variants:
        n = sum(len(r[name]["false_letters"]) for r in rows)
        summary[name] = {
            "false_letters": n,
            "per_minute": n / minutes,
            "clips_with_false_letters": sum(bool(r[name]["false_letters"]) for r in rows),
        }
    (args.out / "negative_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


def summarize(rows: list, names: list) -> dict:
    out = {}
    strata = {
        "all": lambda r: True,
        "slow_lt_2.0_lps": lambda r: (
            r["letters_per_second"] is not None and r["letters_per_second"] < 2.0
        ),
        "fluent_ge_2.0_lps": lambda r: (
            r["letters_per_second"] is not None and r["letters_per_second"] >= 2.0
        ),
    }
    for stratum, keep in strata.items():
        chosen = [r for r in rows if keep(r)]
        n_ref = sum(len(r["ref"]) for r in chosen)
        block = {"clips": len(chosen), "ref_letters": n_ref}
        for name in names:
            s = sum(r[name]["S"] for r in chosen)
            d = sum(r[name]["D"] for r in chosen)
            i = sum(r[name]["I"] for r in chosen)
            emitted = sum(len(r[name]["hyp"]) for r in chosen)
            correct = n_ref - s - d
            block[name] = {
                "CER": (s + d + i) / max(n_ref, 1),
                "S": s,
                "D": d,
                "I": i,
                "emitted": emitted,
                "correct": correct,
                "precision": correct / emitted if emitted else None,
                "recall": correct / max(n_ref, 1),
                "exact": sum(r[name]["hyp"] == r["ref"] for r in chosen),
                "rearms": sum(r[name]["rearms"] for r in chosen),
                "hand_missing_rejections": sum(
                    r[name]["reasons"].get("HAND_CURRENTLY_MISSING", 0) for r in chosen
                ),
            }
        out[stratum] = block
    return out


if __name__ == "__main__":
    main()
