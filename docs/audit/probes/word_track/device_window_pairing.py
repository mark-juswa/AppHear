"""Paired WORD comparison on the recognition windows the phone actually produced.

For every event logged on device (events.jsonl) in sessions with exact-parity raw capture, the
materialized window is rebuilt from the device's own indices on the device-captured raw-v1, viewed
with Recognition V2 DENSE (as PhoneCausalController.kt) and classified by the frozen Gate-2
recognizer and by WORD v2. Offline frozen top-1 must reproduce the device-logged top-1 (parity).
Labels come only from human review: GENUINE (event overlaps a reviewed GENUINE_SIGN; gloss known),
CONFIRMED_NON_SIGN (inside a reviewed non-sign interval), UNCERTAIN (overlaps an UNCERTAIN sign) or
UNLABELED (anything else; never counted as a confirmed false word).
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "docs/audit/probes/pipeline_v3"))

import stage_attribution as sa  # noqa: E402

from eval.runtime_diagnostics import s2_r3_context_suite as suite  # noqa: E402
from eval.runtime_diagnostics.phone_s2_exact_parity_and_r2_decision import (  # noqa: E402
    load_capture,
)  # noqa: E402

E = Path("F:/ASL DATASET/5. Apphear3")
RU = E / "artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01"
EXTRA = {
    "SEP21_S2FIT_EXACT": (
        "phone_pull_s2_exact_parity/session_20260921T153138Z",
        RU / "s2_r2_continuous_domain_correction_01/exact_phone_temporal_review_01/"
        "phone_positive_observation_labels.csv",
    ),
}


def labelled_intervals(session: dict[str, Any]) -> list[tuple[str, str | None, int, int]]:
    out = [("GENUINE", sa.gloss_of(p["name"]), p["first"], p["last"]) for p in session["positives"]]
    out += [
        ("UNCERTAIN", sa.gloss_of(u["name"]), u["first"], u["last"])
        for u in session.get("uncertain", [])
        if u.get("first") is not None
    ]
    out += [("CONFIRMED_NON_SIGN", None, n["first"], n["last"]) for n in session["negatives"]]
    return out


def attempts_from_csv(raw_t: np.ndarray, path: Path) -> list[tuple[str, str | None, int, int]]:
    stamp_ns = np.round(raw_t * 1e6).astype(np.int64)
    rows: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    with path.open(encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            idx = int(np.argmin(np.abs(stamp_ns - int(row["source_timestamp_ns"]))))
            rows[row["attempt_id"]].append((idx, int(row["state_id"]), row["expected_gloss"]))
    out = []
    for items in rows.values():
        active = sorted(i for i, s, _ in items if s == 1)
        if active:
            out.append(("GENUINE", items[0][2], active[0], active[-1]))
    return out


def label_event(
    event: dict[str, Any], intervals: list[tuple[str, str | None, int, int]]
) -> tuple[str, str | None]:
    a, b = int(event["logical_active_start_index"]), int(event["logical_active_end_index"])
    for kind in ("GENUINE", "UNCERTAIN"):
        for k, gloss, first, last in intervals:
            if k == kind and max(a, first) <= min(b, last):
                return kind, gloss
    for k, _, first, last in intervals:
        if k == "CONFIRMED_NON_SIGN" and first <= a and b <= last:
            return k, None
    return "UNLABELED", None


def main() -> None:
    config = suite.read_json(suite.SUITES["03"][0])
    tier = config["tier2_sessions"]
    sources: dict[str, tuple[Path, Any]] = {
        name: (
            E / spec["capture"],
            suite.load_tier2_session(
                E, name, spec, "v1", int(tier["timestamp_match_tolerance_ns"])
            ),
        )
        for name, spec in tier.items()
        if isinstance(spec, dict) and "capture" in spec
    }
    for name, (capture, labels) in EXTRA.items():
        sources[name] = (E / capture, labels)
    frozen = sa.Recognizer(E)
    v2 = sa.Recognizer(E, RU / "word_track_robust_aug_02/best.keras")
    rows = []
    for name, (capture_dir, session) in sources.items():
        raw = load_capture(capture_dir, require_full_session=False).raw
        t = np.asarray(raw.timestamp_ms, np.float64)
        if isinstance(session, dict):
            intervals = labelled_intervals(session)
        elif session is not None:
            intervals = attempts_from_csv(t, session)
        else:
            intervals = []
        events = [
            json.loads(line) for line in (capture_dir / "events.jsonl").open(encoding="utf-8")
        ]
        windows, metas = [], []
        for e in events:
            if (
                abs(t[int(e["logical_active_start_index"])] - float(e["logical_active_start_ms"]))
                > 1e-3
            ):
                raise ValueError(f"INDEX_TIMESTAMP_MISMATCH:{name}:{e['event_id']}")
            idx = e.get("recognition_v2_source_indices") or list(
                range(int(e["materialized_start_index"]), int(e["materialized_end_index"]) + 1)
            )
            windows.append(suite._take(raw, np.asarray(idx, np.int32), t[np.asarray(idx)]))
            kind, gloss = label_event(e, intervals)
            metas.append(
                {
                    "session": name,
                    "event_id": int(e["event_id"]),
                    "label": kind,
                    "gloss": gloss,
                    "device_top1": e["top1_gloss"],
                    "device_top1_probability": float(e["top1_probability"]),
                    "device_shadow_top1": e.get("shadow_top1_gloss"),
                    "device_shadow_invocation_ms": e.get("shadow_recognition_invocation_ms"),
                    "hand_fraction": float(np.mean(np.any(raw.hand_observed[idx], axis=1))),
                    "observations": len(idx),
                }
            )
        for meta, pf, pv in zip(
            metas, frozen.probabilities(windows), v2.probabilities(windows), strict=True
        ):
            meta["frozen_top1"] = frozen.glosses[int(np.argmax(pf))]
            meta["frozen_top1_probability"] = float(np.max(pf))
            meta["v2_top1"] = v2.glosses[int(np.argmax(pv))]
            meta["v2_top1_probability"] = float(np.max(pv))
            meta["device_parity"] = meta["frozen_top1"] == meta["device_top1"]
            if meta["device_shadow_top1"] is not None:  # sessions captured with word_shadow_package
                meta["device_shadow_parity"] = meta["v2_top1"] == meta["device_shadow_top1"]
            if meta["gloss"]:
                meta["frozen_correct"] = meta["frozen_top1"] == meta["gloss"]
                meta["v2_correct"] = meta["v2_top1"] == meta["gloss"]
                meta["frozen_expected_p"] = float(pf[frozen.index[meta["gloss"]]])
                meta["v2_expected_p"] = float(pv[v2.index[meta["gloss"]]])
            rows.append(meta)
    summary: dict[str, Any] = {
        "events": len(rows),
        "device_top1_parity": sum(r["device_parity"] for r in rows),
        "device_shadow_events": sum("device_shadow_parity" in r for r in rows),
        "device_shadow_parity": sum(r.get("device_shadow_parity", False) for r in rows),
    }
    for kind in ("GENUINE", "UNCERTAIN", "CONFIRMED_NON_SIGN", "UNLABELED"):
        sub = [r for r in rows if r["label"] == kind]
        summary[kind] = {"events": len(sub)}
        if kind in ("GENUINE", "UNCERTAIN"):
            summary[kind].update(
                frozen_correct=sum(r["frozen_correct"] for r in sub),
                v2_correct=sum(r["v2_correct"] for r in sub),
            )
        summary[kind]["top1_changed"] = sum(r["frozen_top1"] != r["v2_top1"] for r in sub)
        summary[kind]["frozen_p_ge_0_5"] = sum(r["frozen_top1_probability"] >= 0.5 for r in sub)
        summary[kind]["v2_p_ge_0_5"] = sum(r["v2_top1_probability"] >= 0.5 for r in sub)
    out = {
        "summary": summary,
        "events": rows,
        "frozen_sha256": frozen.sha256,
        "v2_sha256": v2.sha256,
    }
    Path(__file__).with_name("device_window_pairing.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(summary, indent=1))
    for r in rows:
        if r["label"] in ("GENUINE", "UNCERTAIN") or r["frozen_top1"] != r["v2_top1"]:
            print(
                f"{r['session'][:14]:14s} ev{r['event_id']:<3d} {r['label']:18s} "
                f"{str(r['gloss']):6s} dev={r['device_top1']:8s} "
                f"frozen={r['frozen_top1']}({r['frozen_top1_probability']:.2f}) "
                f"v2={r['v2_top1']}({r['v2_top1_probability']:.2f}) hands={r['hand_fraction']:.2f}"
            )


if __name__ == "__main__":
    main()
