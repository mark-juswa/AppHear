"""Event-level ledger and whole-event admission evidence (research only; offline / shadow).

One place that replays any S2 package + decoder variant through the reference lifecycle and the
runtime materializer, classifies every window with the frozen recognizer (displayed) and WORD v2
(shadow), and describes each completed event with evidence available on the device at commit time:

  s2_*       S2 probabilities over the event's logical ACTIVE span
  hand_* / body_fraction   accepted Candidate01 evidence inside the logical span / window
  motion_*   accepted-hand wrist travel and handshape change (image-size normalised)
  word_*     frozen top-1 probability, margin, entropy; WORD v2 top-1 and agreement with frozen;
             stability of the frozen top-1 when the window loses its first and/or last observation

Phone events are labelled from human review only. Categories (one per event):
  GENUINE            credited one-to-one to a reviewed genuine sign (word correct or wrong)
  DUPLICATE          overlaps a reviewed genuine sign already credited to another event
  CONFIRMED_NONSIGN  logical span lies inside a reviewed confirmed non-sign interval
  PARTIAL_NONSIGN    overlaps a confirmed non-sign interval, no genuine sign
  UNCERTAIN          overlaps a sign the reviewer marked uncertain
  UNREVIEWED         anything else: never counted as a false word
  PROTOCOL_*         protocol-only session (no human review): SIGN_BLOCK / ORDINARY_MOVEMENT
Nothing here changes Android, the frozen packages or the production decoder.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from eval.runtime_diagnostics import s2_r3_context_suite as suite
from eval.runtime_diagnostics.event_separation import VARIANTS, use_variant
from eval.runtime_diagnostics.phone_s2_exact_parity_and_r2_decision import load_capture
from pipeline.perception_vnext.recognition_schema import RawSequence
from pipeline.perception_vnext.recognition_schema_v2 import temporal_view_v2
from pipeline.perception_vnext.recognition_window_materializer import (
    LogicalSignEvent,
    materialize_recognition_window,
)

RU = Path("artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01")
FROZEN_WORD = RU / "tcn_v2_run_01/best.keras"
FROZEN_WORD_SHA = "8107accbc621ae5652766fec80d314fe8dc9f94ba0d0548a6aef80ed91729340"
V2_WORD = RU / "word_track_robust_aug_02/best.keras"
VOCAB = Path("artifacts/recognition_upgrade/phase1_full_vocab/dataset_v1/vocab.json")
ARM_A = RU / "s2_r3_arm_a_01"
PHONE_COMPLETED_FPS = 5.606840672873506
COMPACT = Path("artifacts/recognition_v3_stage2_compact_device")
SHADOW_LABELLED = "SHADOW_023004Z"
SHADOW_PROTOCOL = "SHADOW_022535Z"
PROTOCOL_EXPECTED = {
    "A_HANDS_DOWN": ["HELLO", "HOME"],
    "B_HANDS_UP": ["HELLO", "HOME"],
    "C_REPEAT_HANDS_UP": ["HELLO", "HELLO"],
    "D_SIGN_THEN_HOLD": ["HELLO"],
    "E_ORDINARY_MOVEMENT": [],
}
FALSE_CATEGORIES = ("CONFIRMED_NONSIGN",)
WRIST, MIDDLE_MCP = 0, 9


# ----------------------------------------------------------------------------- models
class Word:
    """A 236-class recognizer on the Recognition V2 DENSE view (as PhoneCausalController)."""

    def __init__(self, root: Path, path: Path, expected_sha: str | None = None) -> None:
        import tensorflow as tf

        self.sha256 = suite.sha256(root / path)
        if expected_sha and self.sha256 != expected_sha:
            raise ValueError(f"[event_reliability] RECOGNIZER_HASH_MISMATCH:{path}")
        self.model = tf.keras.models.load_model(root / path, compile=False, safe_mode=True)
        vocab = suite.read_json(root / VOCAB)
        self.glosses = [g for g, _ in sorted(vocab.items(), key=lambda item: item[1])]

    def probabilities(self, raws: list[RawSequence]) -> np.ndarray:
        if not raws:
            return np.zeros((0, len(self.glosses)), np.float64)
        views = [
            temporal_view_v2(r, condition="dense", phone_completed_fps=PHONE_COMPLETED_FPS)
            for r in raws
        ]
        x = np.stack([v["features"] for v in views]).astype(np.float32)
        m = np.stack([v["mask"] for v in views])
        out = [
            np.asarray(self.model([x[i : i + 256], m[i : i + 256]], training=False))
            for i in range(0, len(x), 256)
        ]
        return np.concatenate(out).astype(np.float64)


def load_s2(root: Path, name: str) -> suite.Package:
    """Named S2 packages: S2_R2 (frozen production), ARM_A_E10, ARM_A_E21_T08 (theta 0.8)."""
    if name == "S2_R2":
        ref = suite.read_json(suite.SUITES["03"][0])["reference_package"]
        return suite.load_package(name, "v1", root / ref["keras"], root / ref["normalization"])
    for arm in ("B", "I", "J", "K"):  # 2026-10-17 arms (s2_r3_train_04 .. _07)
        if name.startswith(f"ARM_{arm}_E"):
            run = root / RU / f"s2_r3_arm_{arm.lower()}_01"
            epoch = int(name.rsplit("_E", 1)[1])
            return suite.load_package(
                name, "v1", run / f"epoch_{epoch:02d}.keras", run / "normalization.json"
            )
    if name.startswith("ARM_P_ALL_E"):  # Arm P trained on every reviewed phone session
        run = root / RU / "s2_r3_arm_p_01"
        epoch = int(name.rsplit("_E", 1)[1])
        return suite.load_package(
            name, "v1", run / f"epoch_{epoch:02d}.keras", run / "normalization.json"
        )
    if name.startswith("ARM_A_E"):
        epoch = int(name.split("_")[2][1:])
        base = suite.load_package(
            name,
            "v1",
            root / ARM_A / f"epoch_{epoch:02d}.keras",
            root / ARM_A / "normalization.json",
        )
        if "_T" not in name:
            return base
        theta = int(name.split("_T")[1]) / 10.0
        return ThresholdPackage(
            base.package_id, base.contract, base.model, base.mean, base.std, base.identity, theta
        )
    raise ValueError(f"[event_reliability] UNKNOWN_S2:{name}")


class ThresholdPackage(suite.Package):
    """ACTIVE only when P(ACTIVE) >= theta (operating_point.py); otherwise larger of PRE/POST."""

    def __init__(self, *args: Any) -> None:
        *base, theta = args
        super().__init__(*base)
        self.theta = float(theta)

    def probabilities(self, features: np.ndarray) -> np.ndarray:
        p = np.asarray(super().probabilities(features), np.float64).copy()
        active = p[:, 1] >= self.theta
        p[~active, 1] = -1.0
        p[active] = np.array([0.0, 1.0, 0.0])
        return p


def decoder(name: str) -> Any:
    return next(v for v in VARIANTS if v.name == name)


# ----------------------------------------------------------------------------- events
def replay_events(probs: np.ndarray, t: np.ndarray, variant: str) -> list[dict[str, Any]]:
    states = np.argmax(probs, axis=1)
    rows = [
        {
            "source_index": i,
            "source_timestamp_ms": float(t[i]),
            "argmax_state": int(states[i]),
            "pre_probability": float(probs[i, 0]),
            "active_probability": float(probs[i, 1]),
            "post_probability": float(probs[i, 2]),
        }
        for i in range(len(t))
    ]
    with use_variant(decoder(variant)):
        return suite.replay(rows, allow_post_rearm=True, exact_android_commit_recovery=True)[
            "events"
        ]


def window_of(t: np.ndarray, e: dict[str, Any]) -> tuple[int, int]:
    w = materialize_recognition_window(
        t,
        LogicalSignEvent(
            int(e["logical_active_start_index"]),
            int(e["logical_active_end_index"]),
            float(t[int(e["logical_active_start_index"])]),
            float(t[int(e["logical_active_end_index"])]),
            int(e["first_post_index"]),
            float(t[int(e["first_post_index"])]),
            int(e["emitted_at_index"]),
            float(t[int(e["emitted_at_index"])]),
        ),
        suite.MATERIALIZER_CONFIG,
    )
    return int(w.selected_start_index), int(w.selected_end_index)


def _top(p: np.ndarray) -> tuple[int, float, float, float]:
    order = np.argsort(-p, kind="stable")
    q = np.clip(p, 1e-12, 1.0)
    return (
        int(order[0]),
        float(p[order[0]]),
        float(p[order[0]] - p[order[1]]),
        float(-(q * np.log(q)).sum()),
    )


def motion(raw: RawSequence, a: int, b: int) -> dict[str, float]:
    """Accepted-hand wrist travel (per second) and handshape change, normalised by image size."""
    t = np.asarray(raw.timestamp_ms, np.float64)
    size = np.max(np.asarray(raw.source_size, np.float64), axis=1)
    travel, shape_change, seconds = 0.0, [], max(1e-3, (t[b] - t[a]) / 1000.0)
    for side in range(2):
        prev = None
        for i in range(a, b + 1):
            if not raw.hand_observed[i, side]:
                prev = None
                continue
            xy = np.asarray(raw.hand_xy[i, side], np.float64) / size[i]
            scale = np.linalg.norm(xy[MIDDLE_MCP] - xy[WRIST]) + 1e-6
            shape = ((xy - xy[WRIST]) / scale).reshape(-1)
            if prev is not None:
                travel += float(np.linalg.norm(xy[WRIST] - prev[0]))
                shape_change.append(float(np.mean(np.abs(shape - prev[1]))))
            prev = (xy[WRIST], shape)
    return {
        "motion_wrist_travel_per_s": travel / seconds,
        "motion_shape_change": float(np.mean(shape_change)) if shape_change else 0.0,
        "motion_pairs": float(len(shape_change)),
    }


def describe_events(
    raw: RawSequence,
    probs: np.ndarray,
    events: list[dict[str, Any]],
    frozen: Word,
    shadow: Word | None,
) -> list[dict[str, Any]]:
    """Window, outputs and admission evidence for each event (all from commit-time data)."""
    t = np.asarray(raw.timestamp_ms, np.float64)
    windows = [window_of(t, e) for e in events]
    batch: list[RawSequence] = []
    for a, b in windows:
        batch.append(suite.slice_raw(raw, a, b))
        for da, db in ((1, 0), (0, 1), (1, 1)):
            lo, hi = a + da, b - db
            batch.append(suite.slice_raw(raw, lo, hi) if hi > lo else suite.slice_raw(raw, a, b))
    pf = frozen.probabilities(batch)
    pv = shadow.probabilities([batch[4 * k] for k in range(len(windows))]) if shadow else None
    out = []
    for k, (e, (a, b)) in enumerate(zip(events, windows, strict=True)):
        s, f = int(e["logical_active_start_index"]), int(e["logical_active_end_index"])
        span = slice(s, f + 1)
        hands = np.asarray(raw.hand_observed, bool)
        top, p1, margin, entropy = _top(pf[4 * k])
        perturbed = [int(np.argmax(pf[4 * k + j])) for j in (1, 2, 3)]
        row: dict[str, Any] = {
            "logical": [s, f],
            "emitted_at_index": int(e["emitted_at_index"]),
            "window": [a, b],
            "duration_ms": float(t[f] - t[s]),
            "logical_observations": f - s + 1,
            "window_observations": b - a + 1,
            "s2_peak_active": float(np.max(probs[span, 1])),
            "s2_mean_active": float(np.mean(np.clip(probs[span, 1], 0.0, 1.0))),
            "s2_active_fraction": float(np.mean(np.argmax(probs[span], axis=1) == 1)),
            "hand_fraction": float(np.mean(np.any(hands[span], axis=1))),
            "both_hands_fraction": float(np.mean(np.all(hands[span], axis=1))),
            "window_hand_fraction": float(np.mean(np.any(hands[a : b + 1], axis=1))),
            "body_fraction": float(np.mean(np.asarray(raw.body_available, bool)[a : b + 1])),
            **motion(raw, a, b),
            "frozen_top1": frozen.glosses[top],
            "word_p1": p1,
            "word_margin": margin,
            "word_entropy": entropy,
            "word_stability": float(np.mean([g == top for g in perturbed])),
        }
        if pv is not None:
            vtop, vp1, vmargin, _ = _top(pv[k])
            row.update(
                {
                    "v2_top1": shadow.glosses[vtop],  # type: ignore[union-attr]
                    "v2_p1": vp1,
                    "v2_margin": vmargin,
                    "word_models_agree": float(vtop == top),
                }
            )
        out.append(row)
    return out


# ----------------------------------------------------------------------------- phone sessions
def phone_sessions(root: Path) -> dict[str, dict[str, Any]]:
    """Suite v03 Tier-2 (reviewed; development-exposed) + the two signed shadow sessions."""
    config = suite.read_json(suite.SUITES["03"][0])
    tier = config["tier2_sessions"]
    tolerance = int(tier["timestamp_match_tolerance_ns"])
    sessions = {
        name: {**suite.load_tier2_session(root, name, spec, "v1", tolerance), "kind": "TIER2"}
        for name, spec in tier.items()
        if isinstance(spec, dict) and "capture" in spec
    }
    labelled = {
        "capture": str(COMPACT / "session_20261017T023004Z"),
        "labels": "boundaries",
        "continuous_no_capture_pauses": True,
    }
    sessions[SHADOW_LABELLED] = {
        **suite.load_tier2_session(root, SHADOW_LABELLED, labelled, "v1", tolerance),
        "kind": "SHADOW_HUMAN_UNBLINDED",
    }
    path = root / COMPACT / "session_20261017T022535Z"
    capture = load_capture(path, require_full_session=False)
    sessions[SHADOW_PROTOCOL] = {
        "name": SHADOW_PROTOCOL,
        "capture": capture,
        "features": suite.features_for_raw(capture.raw, "v1"),
        "timestamps_ms": np.asarray(capture.raw.timestamp_ms, np.float64),
        "positives": [],
        "uncertain": [],
        "negatives": [],
        "continuous": True,
        "kind": "SHADOW_PROTOCOL_ONLY",
        "blocks": protocol_blocks(path),
    }
    for name in (SHADOW_LABELLED,):
        sessions[name]["blocks"] = protocol_blocks(root / labelled["capture"])
    return sessions


def protocol_blocks(session: Path) -> list[dict[str, Any]]:
    out, cur = [], {}
    for line in (session / "attempts.jsonl").open(encoding="utf-8"):
        a = json.loads(line)
        if a["action"] == "BEGIN":
            cur = {"block": a["expected_gloss"], "first": a["observation_count_before_mark"]}
        else:
            cur["last"] = a["observation_count_after_drain"] - 1
            out.append(cur)
    return out


def _overlaps(a: int, b: int, c: int, d: int) -> bool:
    return max(a, c) <= min(b, d)


def label_session(session: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Assign one category per event and score each reviewed genuine sign."""
    positives = sorted(session["positives"], key=lambda s: s["first"])
    credited: dict[int, int] = {}
    signs = []
    for k, sign in enumerate(positives):
        hits = [
            j for j, r in enumerate(rows) if _overlaps(sign["first"], sign["last"], *r["logical"])
        ]
        distinct = next((j for j in hits if j not in credited), None)
        if distinct is not None:
            credited[distinct] = k
        signs.append(
            {
                "sign": sign["name"],
                "gloss": sign["name"].split("#")[0].split(":")[-1],
                "first": sign["first"],
                "last": sign["last"],
                "events_overlapping": len(hits),
                "event": distinct,
                "merged_into_shared_event": bool(hits) and distinct is None,
            }
        )
    for j, r in enumerate(rows):
        s, f = r["logical"]
        genuine = [
            k for k, sign in enumerate(positives) if _overlaps(sign["first"], sign["last"], s, f)
        ]
        r["genuine_overlaps"] = len(genuine)
        if j in credited:
            sign = signs[credited[j]]
            r["category"] = "GENUINE"
            r["sign"] = sign["sign"]
            r["frozen_correct"] = r["frozen_top1"] == sign["gloss"]
            if "v2_top1" in r:
                r["v2_correct"] = r["v2_top1"] == sign["gloss"]
        elif genuine:
            r["category"] = "DUPLICATE"
        elif any(n["first"] <= s and f <= n["last"] for n in session["negatives"]):
            r["category"] = "CONFIRMED_NONSIGN"
        elif any(_overlaps(n["first"], n["last"], s, f) for n in session["negatives"]):
            r["category"] = "PARTIAL_NONSIGN"
        elif any(_overlaps(u["first"], u["last"], s, f) for u in session["uncertain"]):
            r["category"] = "UNCERTAIN"
        elif session["kind"] == "SHADOW_PROTOCOL_ONLY":
            block = next(
                (b["block"] for b in session["blocks"] if b["first"] <= s <= b["last"]), None
            )
            r["block"] = block
            r["category"] = (
                "PROTOCOL_ORDINARY_MOVEMENT"
                if block == "E_ORDINARY_MOVEMENT"
                else "PROTOCOL_SIGN_BLOCK" if block else "UNREVIEWED"
            )
        else:
            r["category"] = "UNREVIEWED"
        if "blocks" in session:
            r.setdefault(
                "block",
                next((b["block"] for b in session["blocks"] if b["first"] <= s <= b["last"]), None),
            )
    for sign in signs:
        if sign["event"] is not None:
            r = rows[sign["event"]]
            sign["frozen_top1"] = r["frozen_top1"]
            sign["frozen_correct"] = r["frozen_correct"]
            sign["v2_correct"] = r.get("v2_correct")
    return {"signs": signs, "events": rows}


def protocol_words(rows: list[dict[str, Any]], key: str, admitted: Callable[[dict], bool]) -> dict:
    """Protocol-only scoring (022535Z): an output claims one unclaimed expected gloss per block."""
    remaining = {b: list(g) for b, g in PROTOCOL_EXPECTED.items()}
    hit = other = movement = outside = 0
    for r in rows:
        if not admitted(r):
            continue
        block, gloss = r.get("block"), r[key]
        if block is None:
            outside += 1
        elif block == "E_ORDINARY_MOVEMENT":
            movement += 1
        elif gloss in remaining[block]:
            remaining[block].remove(gloss)
            hit += 1
        else:
            other += 1
    return {
        "expected_words": hit,
        "other_in_sign_blocks": other,
        "ordinary_movement": movement,
        "outside": outside,
    }


def phone_ledger(
    root: Path,
    sessions: dict[str, dict[str, Any]],
    s2: suite.Package,
    variant: str,
    frozen: Word,
    shadow: Word | None,
) -> dict[str, Any]:
    out = {}
    for name, session in sessions.items():
        raw = session["capture"].raw
        t = session["timestamps_ms"]
        probs = s2.probabilities(session["features"])
        events = replay_events(probs, t, variant)
        rows = describe_events(raw, probs, events, frozen, shadow)
        for r in rows:
            r["session"] = name
        out[name] = {"kind": session["kind"], **label_session(session, rows)}
    return out


def summarize_phone(
    ledger: dict[str, Any], admitted: Callable[[dict], bool] = lambda r: True, key: str = "frozen"
) -> dict[str, Any]:
    """User-facing counts over reviewed sessions (Tier-2 + labelled shadow) and protocol session."""
    reviewed = {n: v for n, v in ledger.items() if v["kind"] != "SHADOW_PROTOCOL_ONLY"}
    total: dict[str, Any] = {}

    def add(part: str, k: str, v: int) -> None:
        total.setdefault(part, {}).setdefault(k, 0)
        total[part][k] += int(v)

    for v in reviewed.values():
        part = "tier2" if v["kind"] == "TIER2" else "shadow_023004Z"
        for sign in v["signs"]:
            add(part, "genuine_signs", 1)
            ok = sign["event"] is not None and admitted(v["events"][sign["event"]])
            add(part, "signs_with_admitted_event", ok)
            add(part, "correct_words", ok and bool(sign.get(f"{key}_correct")))
            add(part, "wrong_words_on_genuine", ok and not sign.get(f"{key}_correct"))
            add(part, "missed_no_event", sign["events_overlapping"] == 0)
            add(part, "merged_into_shared_event", sign["merged_into_shared_event"])
            add(part, "rejected_genuine_events", sign["event"] is not None and not ok)
            add(
                part,
                "rejected_correct_words",
                sign["event"] is not None and not ok and bool(sign.get(f"{key}_correct")),
            )
        merged_events = sum(
            1 for r in v["events"] if r["category"] == "GENUINE" and r["genuine_overlaps"] > 1
        )
        add(part, "merged_events", merged_events)
        for r in v["events"]:
            add(part, "events", 1)
            add(part, "admitted_events", admitted(r))
            add(part, f"admitted_{r['category'].lower()}", admitted(r))
            add(part, f"all_{r['category'].lower()}", 1)
    protocol = {
        n: protocol_words(v["events"], f"{key}_top1", admitted)
        for n, v in ledger.items()
        if v["kind"] == "SHADOW_PROTOCOL_ONLY"
    }
    return {**total, "protocol": protocol}


# ----------------------------------------------------------------------------- labelled streams
def stream_ledger(
    raw: RawSequence,
    probs: np.ndarray,
    variant: str,
    signs: list[dict[str, Any]],
    negative_rows: np.ndarray,
    frozen: Word,
    shadow: Word | None,
) -> list[dict[str, Any]]:
    """Events on a stream with known sign intervals (CAL / held-out DEV).

    signs: [{"first", "last", "gloss"?}]; negative_rows: bool per row for reviewed non-sign rows
    (CAL negative blocks) or rest rows (DEV). Categories: GENUINE, DUPLICATE, NONSIGN (logical span
    entirely on negative rows), OTHER (sign-clip lead-in/out or mixed rows).
    """
    t = np.asarray(raw.timestamp_ms, np.float64)
    events = replay_events(probs, t, variant)
    rows = describe_events(raw, probs, events, frozen, shadow)
    credited: dict[int, int] = {}
    for k, sign in enumerate(signs):
        hits = [
            j for j, r in enumerate(rows) if _overlaps(sign["first"], sign["last"], *r["logical"])
        ]
        distinct = next((j for j in hits if j not in credited), None)
        if distinct is not None:
            credited[distinct] = k
    for j, r in enumerate(rows):
        s, f = r["logical"]
        overl = [k for k, sign in enumerate(signs) if _overlaps(sign["first"], sign["last"], s, f)]
        r["genuine_overlaps"] = len(overl)
        if j in credited:
            r["category"] = "GENUINE"
            gloss = signs[credited[j]].get("gloss")
            if gloss is not None:
                r["frozen_correct"] = r["frozen_top1"] == gloss
                if "v2_top1" in r:
                    r["v2_correct"] = r["v2_top1"] == gloss
        elif overl:
            r["category"] = "DUPLICATE"
        elif bool(np.all(negative_rows[s : f + 1])):
            r["category"] = "NONSIGN"
        else:
            r["category"] = "OTHER"
    return rows
