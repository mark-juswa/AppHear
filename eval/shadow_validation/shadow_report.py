"""Join app shadow logs to INDEPENDENT human labels and report the Phase 1 commit gate.

Inputs
  * shadow logs      JSONL written by the debug-only `-PshadowEval=true` app build
                     (schema `apphear.shadow_event.v1`; see android .../ShadowEvalLog.kt)
  * annotations      human labels made from video ONLY, before any log is opened
                     (schema `apphear.shadow_annotations.v1`; keys are allow-listed so a model prediction cannot be
                     smuggled in)
  * manifest         study metadata: evidence tier, signer ids and roles, clock sync per session, conditions,
                     annotation SHA-256 and lock time, annotator attestation
  * signer registry  signers already used for training or calibration (leakage check)

What it refuses to do
  * run when an evaluation signer also appears in the training/calibration registry
    (unless --development-only, which stamps the report "NOT EVIDENCE");
  * run when the annotation file's SHA-256 differs from the one frozen in the manifest;
  * accept annotation keys outside the allow-list (no predictions, scores or gloss guesses from the model);
  * tune anything: it reports the SHIPPED policy only (log field `gated`), never searches thresholds.

It never fabricates a result: no logs/labels -> no numbers. Offline replay, phone-recorded and live-device data are
kept in separate report sections by `evidence_tier`.

Usage:
  python -m eval.shadow_validation.shadow_report --manifest M.json --logs DIR --out OUT_DIR [--development-only]
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

EVENT_SCHEMA = "apphear.shadow_event.v1"
ANN_SCHEMA = "apphear.shadow_annotations.v1"
MANIFEST_SCHEMA = "apphear.shadow_manifest.v1"
TIERS = ("offline_replay", "phone_recorded", "live_device")
# Same bar the repo itself set for reopening whole-event admission (docs/audit/RECOGNITION_V3_CONTINUOUS_...).
MIN_NONSIGN_EVENTS = 30
MIN_SIGNERS = 3
SMALL_N = 20
OVERLAP_FRACTION = 0.5


class StudyError(ValueError):
    """A precondition of an honest evaluation is violated. The report is not produced."""


# ---- statistics ---------------------------------------------------------------------------------------------

def wilson(k: int, n: int, z: float = 1.96) -> list[float | None]:
    if n <= 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def rate(k: int, n: int) -> dict[str, Any]:
    return {"k": k, "n": n, "value": None if n == 0 else round(k / n, 4), "wilson95": wilson(k, n),
            "small_n": n < SMALL_N}


def harmonic(a: float | None, b: float | None) -> float | None:
    if not a or not b:
        return None
    return round(2 * a * b / (a + b), 4)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    v = sorted(values)
    return round(v[min(len(v) - 1, max(0, math.ceil(q * len(v)) - 1))], 2)


def summarize(values: list[float]) -> dict[str, Any]:
    return {"n": len(values), "p50": percentile(values, 0.5), "p95": percentile(values, 0.95)}


# ---- loading and validation ---------------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check_annotation_keys(annotations: dict) -> None:
    """Structural allow-list: only blind human labels can be present (no model output of any kind)."""
    def need(d: Any, allowed: set[str], where: str) -> None:
        if not isinstance(d, dict):
            raise StudyError(f"annotation node at {where} must be an object")
        extra = set(d) - allowed
        if extra:
            raise StudyError(f"annotation key(s) {sorted(extra)} at {where} are not allowed (blind labels only)")

    need(annotations, {"schema", "sessions"}, "$")
    for run, sess in annotations.get("sessions", {}).items():
        need(sess, {"signs", "nonsign", "excluded"}, f"$.sessions.{run}")
        for kind, allowed in (("signs", {"start_ms", "end_ms", "gloss", "annotator"}),
                              ("nonsign", {"start_ms", "end_ms", "activity", "annotator"}),
                              ("excluded", {"start_ms", "end_ms", "reason", "annotator"})):
            for item in sess.get(kind, []):
                need(item, allowed, f"$.sessions.{run}.{kind}")
                if not item["end_ms"] > item["start_ms"]:
                    raise StudyError(f"empty or inverted interval at $.sessions.{run}.{kind}")


def load_events(log_dir: Path) -> tuple[list[dict], dict[str, dict]]:
    """All `event` lines plus per-session start metadata and the last summary seen (drop counters)."""
    events: list[dict] = []
    sessions: dict[str, dict] = {}
    for path in sorted(log_dir.glob("shadow_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue  # a torn final line after a crash; never invented, just skipped
            if rec.get("schema") != EVENT_SCHEMA:
                continue
            s = sessions.setdefault(rec["sid"], {"run": rec.get("run", ""), "dropped": 0, "write_failures": 0})
            if rec["type"] == "event":
                events.append(rec)
            elif rec["type"] == "session_end":
                s["dropped"] = max(s["dropped"], rec.get("dropped", 0))
                s["write_failures"] = max(s["write_failures"], rec.get("write_failures", 0))
    return events, sessions


def validate_study(manifest: dict, registry: dict | None, annotations: dict, ann_path: Path,
                   development_only: bool) -> list[str]:
    """Raises StudyError on a violated precondition; returns non-fatal warnings."""
    warnings: list[str] = []
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise StudyError("manifest schema mismatch")
    if manifest.get("evidence_tier") not in TIERS:
        raise StudyError(f"evidence_tier must be one of {TIERS}")
    if annotations.get("schema") != ANN_SCHEMA:
        raise StudyError("annotation schema mismatch")
    check_annotation_keys(annotations)
    if sha256_file(ann_path) != manifest.get("annotation_sha256"):
        raise StudyError("annotation file SHA-256 differs from the value frozen in the manifest "
                         "(labels must be locked before logs are opened)")
    if not manifest.get("annotation_locked_utc"):
        raise StudyError("manifest has no annotation_locked_utc")
    sessions = manifest.get("sessions") or []
    ev = [s for s in sessions if s.get("role") == "evaluation"]
    if not ev:
        raise StudyError("no session with role 'evaluation'")
    unknown = set(annotations["sessions"]) - {s["run_label"] for s in sessions}
    if unknown:
        raise StudyError(f"annotations reference sessions not in the manifest: {sorted(unknown)}")
    if registry is None:
        if not development_only:
            raise StudyError("signer registry missing: cannot prove signer-disjointness (use --development-only)")
    else:
        used = set(registry.get("training_signers", [])) | set(registry.get("calibration_signers", []))
        leaked = sorted({s["signer_id"] for s in ev} & used)
        if leaked and not development_only:
            raise StudyError(f"signer leakage: evaluation signers {leaked} appear in training/calibration")
        if leaked:
            warnings.append(f"SIGNER LEAKAGE (development-only run): {leaked}")
    ann = manifest.get("annotators", {})
    if not ann.get("blind_to_model_output"):
        warnings.append("annotators are NOT attested blind to model output: labels are not independent")
    if int(ann.get("count", 0)) < 2:
        warnings.append("fewer than 2 annotators: no inter-annotator agreement available")
    return warnings


# ---- attribution ----------------------------------------------------------------------------------------------------

def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def event_video_span(ev: dict, t0: float) -> tuple[float, float, float] | None:
    """(start, end, commit-capture) of the event's logical sign span in VIDEO ms, or None if unlocatable."""
    s_ago, e_ago = ev.get("start_ago_ms"), ev.get("end_ago_ms")
    if s_ago is None or e_ago is None:
        return None
    capture_wall = ev["wall_ms"] - (ev.get("lag_ms") or 0.0)
    commit = capture_wall - t0
    return commit - s_ago, commit - e_ago, commit


def attribute(events: list[dict], session: dict, ann: dict, tol: float) -> tuple[list[dict], list[dict]]:
    """Label every event of one session. Returns (events with 'cat', signs with credited event)."""
    t0 = float(session["video_t0_wall_utc_ms"])
    signs = [dict(s, session=session["run_label"], signer=session["signer_id"], credited=None, n_events=0)
             for s in ann.get("signs", [])]
    labelled: list[dict] = []
    for ev in events:
        row = dict(ev, session=session["run_label"], signer=session["signer_id"],
                   conditions=session.get("conditions", {}), cat="UNLABELED", sign_idx=None, activity=None)
        span = event_video_span(ev, t0)
        if span is None:
            row["cat"] = "UNLOCATED"
            labelled.append(row)
            continue
        s, e, commit = span
        row["video_span"] = (s, e)
        row["video_commit"] = commit
        dur = max(e - s, 1.0)
        best_i, best_f = None, 0.0
        for i, sg in enumerate(signs):
            f = _overlap(s, e, sg["start_ms"] - tol, sg["end_ms"] + tol) / dur
            if f > best_f:
                best_i, best_f = i, f
        if best_i is not None and best_f >= OVERLAP_FRACTION:
            row["cat"], row["sign_idx"] = "SIGN", best_i
        else:
            for iv in ann.get("nonsign", []):
                if _overlap(s, e, iv["start_ms"], iv["end_ms"]) / dur >= OVERLAP_FRACTION:
                    row["cat"], row["activity"] = "NONSIGN", iv["activity"]
                    break
            else:
                for iv in ann.get("excluded", []):
                    if _overlap(s, e, iv["start_ms"], iv["end_ms"]) / dur >= OVERLAP_FRACTION:
                        row["cat"] = "EXCLUDED"
                        break
        labelled.append(row)
    # one-to-one credit per sign: the event with the largest overlap is credited, the rest are duplicates
    for i, sg in enumerate(signs):
        cand = [r for r in labelled if r["cat"] == "SIGN" and r["sign_idx"] == i]
        sg["n_events"] = len(cand)
        if not cand:
            continue

        def frac(r: dict, sg: dict = sg) -> float:
            s, e = r["video_span"]
            return _overlap(s, e, sg["start_ms"] - tol, sg["end_ms"] + tol) / max(e - s, 1.0)

        credited = max(cand, key=lambda r: (frac(r), -r["video_commit"]))
        sg["credited"] = credited
        for r in cand:
            r["cat"] = ("CORRECT" if r["top1"] == sg["gloss"] else "WRONG") if r is credited else "DUPLICATE"
            r["sign_gloss"] = sg["gloss"]
    return labelled, signs


# ---- metrics --------------------------------------------------------------------------------------------------------

def committed(ev: dict, policy: str) -> bool:
    return True if policy == "legacy" else ev["gated"] == "ACCEPT"


def policy_metrics(events: list[dict], signs: list[dict], nonsign_minutes: float, policy: str) -> dict[str, Any]:
    cats = collections.Counter(e["cat"] for e in events)
    kept = collections.Counter(e["cat"] for e in events if committed(e, policy))
    tp, fpw, fpd, fpn = kept["CORRECT"], kept["WRONG"], kept["DUPLICATE"], kept["NONSIGN"]
    denom = tp + fpw + fpd + fpn
    c_total = cats["CORRECT"]
    n_signs = len(signs)
    credited = [s for s in signs if s["credited"] is not None]
    signs_correct_committed = sum(1 for s in credited
                                  if s["credited"]["cat"] == "CORRECT" and committed(s["credited"], policy))
    signs_any_committed = sum(1 for s in credited if committed(s["credited"], policy))
    precision = None if denom == 0 else tp / denom
    retention = None if c_total == 0 else tp / c_total
    sign_recall = None if n_signs == 0 else signs_correct_committed / n_signs
    return {
        "events_labelled": sum(cats[c] for c in ("CORRECT", "WRONG", "DUPLICATE", "NONSIGN")),
        "signs": n_signs,
        "correct_events": c_total, "wrong_events": cats["WRONG"], "duplicate_events": cats["DUPLICATE"],
        "nonsign_events": cats["NONSIGN"],
        "committed_correct": tp, "committed_wrong": fpw, "committed_duplicate": fpd, "committed_nonsign": fpn,
        "precision": rate(tp, denom),
        "event_recall_correct_retention": rate(tp, c_total),
        "false_rejection_rate": rate(c_total - tp, c_total),
        "false_positive_rate_nonsign": rate(fpn, cats["NONSIGN"]),
        "false_nonsign_commits_per_minute": None if nonsign_minutes <= 0 else round(fpn / nonsign_minutes, 3),
        "sign_recall_end_to_end": rate(signs_correct_committed, n_signs),
        "recognition_coverage": rate(signs_any_committed, n_signs),
        "upstream_miss_rate_no_event": rate(n_signs - len(credited), n_signs),
        "f1_event": harmonic(precision, retention),
        "f1_end_to_end": harmonic(precision, sign_recall),
        "excluded_from_metrics": {k: cats[k] for k in ("UNLABELED", "EXCLUDED", "UNLOCATED") if cats[k]},
    }


def both(events: list[dict], signs: list[dict], nonsign_minutes: float) -> dict[str, Any]:
    return {p: policy_metrics(events, signs, nonsign_minutes, p) for p in ("legacy", "gated")}


def confusion(events: list[dict], signs: list[dict], policy: str) -> dict[str, dict[str, int]]:
    m: dict[str, dict[str, int]] = collections.defaultdict(lambda: collections.defaultdict(int))
    for s in signs:
        c = s["credited"]
        col = "NO_EVENT" if c is None else (c["top1"] if committed(c, policy) else "WITHHELD")
        m[s["gloss"]][col] += 1
    for e in events:
        if not committed(e, policy):
            continue
        if e["cat"] == "NONSIGN":
            m[f"NONSIGN:{e['activity']}"][e["top1"]] += 1
        elif e["cat"] == "DUPLICATE":
            m["DUPLICATE_OF:" + e["sign_gloss"]][e["top1"]] += 1
    return {k: dict(v) for k, v in m.items()}


def latency(events: list[dict], signs: list[dict]) -> dict[str, Any]:
    out = {
        "capture_to_decision_ms": summarize([e["lag_ms"] for e in events if e.get("lag_ms") is not None]),
        "logical_end_to_commit_ms (decoder, by design)": summarize(
            [e["end_ago_ms"] for e in events if e.get("end_ago_ms") is not None]),
        "word_recognizer_ms": summarize([e["rec_ms"] for e in events if e.get("rec_ms") is not None]),
        "s2_segmenter_ms_at_commit": summarize([e["s2_ms"] for e in events if e.get("s2_ms") is not None]),
    }
    ends = [s["credited"]["video_commit"] - s["end_ms"] for s in signs if s["credited"] is not None]
    out["physical_sign_end_to_decision_ms (labelled signs, credited events)"] = summarize(ends)
    return out


def minutes(intervals: list[dict]) -> float:
    return sum(max(0.0, iv["end_ms"] - iv["start_ms"]) for iv in intervals) / 60000.0


# ---- report ---------------------------------------------------------------------------------------------------------

def build_report(manifest: dict, annotations: dict, events: list[dict], log_sessions: dict[str, dict],
                 warnings: list[str], development_only: bool) -> dict[str, Any]:
    tol = float(manifest.get("clock_tolerance_ms", 300))
    by_run: dict[str, list[dict]] = collections.defaultdict(list)
    for e in events:
        by_run[e.get("run", "")].append(e)
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for sess in manifest["sessions"]:
        if sess.get("role") != "evaluation":
            continue
        ann = annotations["sessions"].get(sess["run_label"], {"signs": [], "nonsign": [], "excluded": []})
        labelled, signs = attribute(by_run.get(sess["run_label"], []), sess, ann, tol)
        nonsign_min = {iv["activity"]: 0.0 for iv in ann.get("nonsign", [])}
        for iv in ann.get("nonsign", []):
            nonsign_min[iv["activity"]] += minutes([iv])
        cfgs = {e["cfg"] for e in labelled} or {"(no events logged)"}
        for cfg in cfgs:
            g = groups.setdefault((manifest["evidence_tier"], cfg),
                                  {"events": [], "signs": [], "sessions": [], "nonsign_minutes": collections.Counter()})
            g["events"] += [e for e in labelled if e.get("cfg", cfg) == cfg]
            g["signs"] += signs
            g["sessions"].append(sess)
            g["nonsign_minutes"].update(nonsign_min)
    report: dict[str, Any] = {
        "banner": ("DEVELOPMENT-EXPOSED RUN - NOT EVIDENCE" if development_only else
                   "Shadow evaluation: validity depends on the attestations below; it does not by itself prove accuracy"),
        "study_id": manifest.get("study_id"), "evidence_tier": manifest["evidence_tier"],
        "annotation_sha256": manifest["annotation_sha256"], "annotation_locked_utc": manifest["annotation_locked_utc"],
        "annotators": manifest.get("annotators"), "warnings": list(warnings),
        "log_health": {sid: s for sid, s in log_sessions.items()},
        "events_in_logs": len(events),
        "events_not_matched_to_a_manifest_session": sum(
            1 for e in events if e.get("run", "") not in {s["run_label"] for s in manifest["sessions"]}),
        "configurations": {},
    }
    for (tier, cfg), g in sorted(groups.items()):
        ev, sg = g["events"], g["signs"]
        total_ns_min = sum(g["nonsign_minutes"].values())
        signers = sorted({s["signer_id"] for s in g["sessions"]})
        caveats: list[str] = []
        if len(signers) < MIN_SIGNERS:
            caveats.append(f"{len(signers)} evaluation signer(s) (< {MIN_SIGNERS}): no generalisation claim is supported")
        n_ns = sum(1 for e in ev if e["cat"] == "NONSIGN")
        if n_ns < MIN_NONSIGN_EVENTS:
            caveats.append(f"{n_ns} labelled non-sign events (< {MIN_NONSIGN_EVENTS}, the repo's own bar): "
                           "false-positive rate is not decision-grade")
        if any(e.get("fallback") for e in ev):
            caveats.append("some events came from a session whose EXPERIMENTAL configuration fell back to STABLE")
        if len({e.get("gate_on") for e in ev}) > 1:
            caveats.append("events were logged with the gate both ON and OFF; 'gated' is hypothetical when OFF")
        caveats.append("intervals are event-level Wilson intervals; they ignore signer clustering and must not be "
                       "read as population intervals")
        block: dict[str, Any] = {
            "signers": signers, "sessions": [s["run_label"] for s in g["sessions"]], "caveats": caveats,
            "overall": both(ev, sg, total_ns_min),
            "latency": latency(ev, sg),
            "confusion_legacy": confusion(ev, sg, "legacy"), "confusion_gated": confusion(ev, sg, "gated"),
            "by_signer": {}, "by_sign_class": {}, "by_nonsign_activity": {}, "by_condition": {},
        }
        for signer in signers:
            es = [e for e in ev if e["signer"] == signer]
            ss = [s for s in sg if s["signer"] == signer]
            mins = sum(minutes(annotations["sessions"].get(r["run_label"], {}).get("nonsign", []))
                       for r in g["sessions"] if r["signer_id"] == signer)
            block["by_signer"][signer] = both(es, ss, mins)
        for gloss in sorted({s["gloss"] for s in sg}):
            ss = [s for s in sg if s["gloss"] == gloss]
            es = [s["credited"] for s in ss if s["credited"] is not None]
            pe = [e for e in ev if e["top1"] == gloss and e["cat"] in ("CORRECT", "WRONG", "DUPLICATE", "NONSIGN")]
            block["by_sign_class"][gloss] = {
                "signs": len(ss),
                **{p: {"sign_recall": policy_metrics(es, ss, 0.0, p)["sign_recall_end_to_end"],
                       "coverage": policy_metrics(es, ss, 0.0, p)["recognition_coverage"],
                       "precision_when_predicted": rate(
                           sum(1 for e in pe if e["cat"] == "CORRECT" and committed(e, p)),
                           sum(1 for e in pe if committed(e, p)))}
                   for p in ("legacy", "gated")},
            }
        for act in sorted(g["nonsign_minutes"]):
            es = [e for e in ev if e["cat"] == "NONSIGN" and e["activity"] == act]
            block["by_nonsign_activity"][act] = {
                "minutes": round(g["nonsign_minutes"][act], 2), "events": len(es),
                **{p: {"committed": sum(1 for e in es if committed(e, p)),
                       "false_positive_rate": rate(sum(1 for e in es if committed(e, p)), len(es))}
                   for p in ("legacy", "gated")},
            }
        cond_keys = sorted({k for s in g["sessions"] for k in s.get("conditions", {})})
        for ck in cond_keys:
            for val in sorted({str(s["conditions"].get(ck)) for s in g["sessions"] if ck in s.get("conditions", {})}):
                runs = {s["run_label"] for s in g["sessions"] if str(s.get("conditions", {}).get(ck)) == val}
                es = [e for e in ev if e["session"] in runs]
                ss = [s for s in sg if s["session"] in runs]
                mins = sum(minutes(annotations["sessions"].get(r, {}).get("nonsign", [])) for r in runs)
                block["by_condition"][f"{ck}={val}"] = both(es, ss, mins)
        report["configurations"][f"{tier} / {cfg}"] = block
    return report


def render_markdown(report: dict[str, Any]) -> str:
    def f(r: dict | None) -> str:
        if not r or r.get("value") is None:
            return "n/a"
        lo, hi = r["wilson95"]
        return f"{r['value']:.3f} [{lo:.3f}, {hi:.3f}] (n={r['n']}{', small n' if r['small_n'] else ''})"
    out = [f"# Shadow validation report - {report['study_id']}", "", f"**{report['banner']}**", "",
           f"Evidence tier: `{report['evidence_tier']}`  ", f"Annotation SHA-256: `{report['annotation_sha256']}` "
           f"(locked {report['annotation_locked_utc']})  ", f"Annotators: {json.dumps(report['annotators'])}", ""]
    if report["warnings"]:
        out += ["## Warnings", *[f"- {w}" for w in report["warnings"]], ""]
    for name, b in report["configurations"].items():
        out += [f"## {name}", f"Signers: {', '.join(b['signers'])}", "", "Caveats:", *[f"- {c}" for c in b["caveats"]], "",
                "### Overall: A = original behaviour (commit every top-1), B = Phase 1 gate", "",
                "| metric | A legacy | B gated |", "|---|---|---|"]
        ov = b["overall"]
        for key in ("precision", "event_recall_correct_retention", "false_rejection_rate", "false_positive_rate_nonsign",
                    "sign_recall_end_to_end", "recognition_coverage", "upstream_miss_rate_no_event"):
            out.append(f"| {key} | {f(ov['legacy'][key])} | {f(ov['gated'][key])} |")
        out += [f"| f1 (event / end-to-end) | {ov['legacy']['f1_event']} / {ov['legacy']['f1_end_to_end']} | "
                f"{ov['gated']['f1_event']} / {ov['gated']['f1_end_to_end']} |",
                f"| false non-sign commits / min | {ov['legacy']['false_nonsign_commits_per_minute']} | "
                f"{ov['gated']['false_nonsign_commits_per_minute']} |", "", "### Latency (ms)", ""]
        out += [f"- {k}: {json.dumps(v)}" for k, v in b["latency"].items()]
        out += ["", "### By signer (gated: precision / sign recall / FPR non-sign)", ""]
        for s, m in b["by_signer"].items():
            g = m["gated"]
            out.append(f"- {s}: {f(g['precision'])} / {f(g['sign_recall_end_to_end'])} / {f(g['false_positive_rate_nonsign'])}")
        out += ["", "### By non-sign activity (events committed, A -> B)", ""]
        for a, m in b["by_nonsign_activity"].items():
            out.append(f"- {a}: {m['legacy']['committed']}/{m['events']} -> {m['gated']['committed']}/{m['events']} "
                       f"over {m['minutes']} min")
        out += ["", "### By sign class (gated sign recall)", ""]
        for c, m in b["by_sign_class"].items():
            out.append(f"- {c}: signs={m['signs']} recall={f(m['gated']['sign_recall'])}")
        out += ["", "### By condition", ""]
        for c, m in b["by_condition"].items():
            out.append(f"- {c}: gated precision {f(m['gated']['precision'])}, sign recall {f(m['gated']['sign_recall_end_to_end'])}")
        out.append("")
    return "\n".join(out)


def write_confusions(report: dict[str, Any], out: Path) -> None:
    for name, b in report["configurations"].items():
        for pol in ("legacy", "gated"):
            m = b[f"confusion_{pol}"]
            cols = sorted({c for row in m.values() for c in row})
            safe = name.replace(" / ", "_").replace(" ", "_")
            with (out / f"confusion_{safe}_{pol}.csv").open("w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["annotated\\committed", *cols])
                for row in sorted(m):
                    w.writerow([row, *[m[row].get(c, 0) for c in cols]])


def run(manifest_path: Path, log_dir: Path, out_dir: Path, development_only: bool) -> dict[str, Any]:
    base = manifest_path.parent
    manifest = read_json(manifest_path)
    ann_path = base / manifest["annotation_file"]
    annotations = read_json(ann_path)
    reg_name = manifest.get("signer_registry")
    registry = read_json(base / reg_name) if reg_name and (base / reg_name).exists() else None
    warnings = validate_study(manifest, registry, annotations, ann_path, development_only)
    events, log_sessions = load_events(log_dir)
    report = build_report(manifest, annotations, events, log_sessions, warnings, development_only)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=1, default=list), encoding="utf-8")
    (out_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    write_confusions(report, out_dir)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--logs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--development-only", action="store_true")
    a = ap.parse_args(argv)
    try:
        report = run(a.manifest, a.logs, a.out, a.development_only)
    except StudyError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"REFUSED: unreadable or incomplete study input ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 2
    print(report["banner"])
    for name in report["configurations"]:
        print(" report written for", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
