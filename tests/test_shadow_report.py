"""Tests of the Phase 1.1 shadow-validation tool.

Every number below comes from a SYNTHETIC scenario written by hand in this file so the arithmetic and the
refusal rules can be verified. It is NOT data about the real system and must never be quoted as a result.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
import weakref
from pathlib import Path

from eval.shadow_validation import shadow_report as sr

T0 = 1_000_000  # wall-clock ms of video time 0


def event(commit_video, start_ago, end_ago, top1, p1, gated, *, cfg="STABLE", hand=1.0, run="R1",
          lag=None, fallback=False, gate_on=True):
    return {
        "schema": sr.EVENT_SCHEMA, "type": "event", "sid": "0123456789abcdef", "gen": 0, "run": run, "seq": 1,
        "wall_ms": T0 + commit_video + (lag or 0), "cfg": cfg, "s2": "S2_R2_CANDIDATE", "fallback": fallback,
        "gate_on": gate_on, "floor": 0.55, "hand_rule": True, "event": 1, "top1": top1, "top5": [top1],
        "p1": p1, "p2": 0.01, "margin": p1 - 0.01, "hand_frac": hand, "span_obs": 8, "win_obs": 14,
        "start_ago_ms": start_ago, "end_ago_ms": end_ago, "s2_ms": 4.0, "rec_ms": 3.0, "lag_ms": lag,
        "legacy": "COMMIT", "gated": gated, "reason": gated, "actual": "COMMIT" if gated == "ACCEPT" else "WITHHELD",
    }


ANNOTATIONS = {
    "schema": sr.ANN_SCHEMA,
    "sessions": {"R1": {
        "signs": [{"start_ms": 10000, "end_ms": 11000, "gloss": "HELLO"},
                  {"start_ms": 20000, "end_ms": 21000, "gloss": "HOME"},
                  {"start_ms": 30000, "end_ms": 31000, "gloss": "TABLE"}],
        "nonsign": [{"start_ms": 40000, "end_ms": 46000, "activity": "seat_adjustment"},
                    {"start_ms": 50000, "end_ms": 53000, "activity": "idle_open_hand"}],
        "excluded": [],
    }},
}

# Spans in video ms are [commit - start_ago, commit - end_ago].
EVENTS = [
    event(11300, 1100, 500, "HELLO", 0.97, "ACCEPT"),                  # e1 correct (credited)
    event(21100, 900, 300, "THINK", 0.30, "UNCERTAIN"),                # e2 wrong gloss on HOME
    event(11700, 1400, 1000, "HELLO", 0.96, "ACCEPT"),                 # e3 duplicate of HELLO
    event(42500, 1500, 500, "STAND2", 0.80, "REJECT", hand=0.0),       # e4 non-sign, rejected by the gate
    event(44500, 1500, 500, "HOSPITAL1", 0.70, "ACCEPT"),              # e5 non-sign, the gate misses it
    event(52500, 1500, 500, "HELLO", 0.35, "UNCERTAIN"),               # e6 non-sign, withheld
    event(61500, 1500, 500, "AND", 0.90, "ACCEPT"),                    # e7 outside every label -> UNLABELED
    {**event(70000, 0, 0, "ON", 0.9, "ACCEPT"), "start_ago_ms": None},  # e8 no span -> UNLOCATED
]


class Study:
    """Builds a manifest + annotations + logs in a temp dir; mutate the dicts before write()."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="shadow_report_test_"))
        weakref.finalize(self, shutil.rmtree, str(self.root), True)
        self.annotations = copy.deepcopy(ANNOTATIONS)
        self.events = copy.deepcopy(EVENTS)
        self.registry = {"training_signers": ["T1"], "calibration_signers": ["C1"]}
        self.manifest = {
            "schema": sr.MANIFEST_SCHEMA, "study_id": "synthetic", "evidence_tier": "live_device",
            "annotation_file": "annotations.json", "annotation_locked_utc": "2026-01-01T00:00:00Z",
            "annotators": {"count": 2, "blind_to_model_output": True, "attestation": "synthetic"},
            "signer_registry": "signer_registry.json", "clock_tolerance_ms": 300,
            "sessions": [{"run_label": "R1", "signer_id": "E1", "role": "evaluation",
                          "video_t0_wall_utc_ms": T0, "conditions": {"lighting": "dim", "distance": "far"}}],
        }

    def write(self, *, refreeze=True, registry=True, torn_line=False):
        ann = self.root / "annotations.json"
        ann.write_text(json.dumps(self.annotations), encoding="utf-8")
        if refreeze:
            self.manifest["annotation_sha256"] = hashlib.sha256(ann.read_bytes()).hexdigest()
        (self.root / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        if registry:
            (self.root / "signer_registry.json").write_text(json.dumps(self.registry), encoding="utf-8")
        logs = self.root / "logs"
        logs.mkdir(exist_ok=True)
        lines = [json.dumps({"schema": sr.EVENT_SCHEMA, "type": "session_start", "sid": "0123456789abcdef", "gen": 0,
                             "run": "R1", "wall_ms": T0})]
        lines += [json.dumps(e) for e in self.events]
        lines.append(json.dumps({"schema": sr.EVENT_SCHEMA, "type": "session_end", "sid": "0123456789abcdef", "gen": 0,
                                 "run": "R1", "wall_ms": T0, "written": 9, "dropped": 2, "write_failures": 1}))
        if torn_line:
            lines.append('{"schema": "apphear.shadow_event.v1", "type": "ev')
        (logs / "shadow_0123456789abcdef_0.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return self

    def run(self, development_only=False):
        return sr.run(self.root / "manifest.json", self.root / "logs", self.root / "out", development_only)


GOLDEN = Path(__file__).resolve().parents[1] / "android/app/src/test/resources/shadow_eval/golden_event_line.json"


class KotlinContractTest(unittest.TestCase):
    """The golden line is produced by the REAL Kotlin serializer and pinned byte-for-byte by ShadowEvalLogTest."""

    def test_the_report_reads_a_line_written_by_the_app(self):
        line = GOLDEN.read_text(encoding="utf-8").strip()
        ev = json.loads(line)
        self.assertEqual(ev["schema"], sr.EVENT_SCHEMA)
        for key in ("run", "wall_ms", "cfg", "top1", "gated", "start_ago_ms", "end_ago_ms", "lag_ms", "rec_ms", "s2_ms",
                    "fallback", "gate_on"):
            self.assertIn(key, ev)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "shadow_x_0.jsonl").write_text(line + "\n", encoding="utf-8")
            events, sessions = sr.load_events(Path(d))
        self.assertEqual(len(events), 1)
        self.assertEqual(sessions["0123456789abcdef"]["run"], "E01_dim_far_slow_r1")

    def test_a_golden_event_attributes_end_to_end(self):
        ev = json.loads(GOLDEN.read_text(encoding="utf-8"))
        # video t0 chosen so the event's logical span [commit-1100, commit-500] lies inside a HELLO label.
        t0 = ev["wall_ms"] - ev["lag_ms"] - 11300
        session = {"run_label": ev["run"], "signer_id": "E01", "video_t0_wall_utc_ms": t0}
        ann = {"signs": [{"start_ms": 10000, "end_ms": 11000, "gloss": "HELLO"}], "nonsign": [], "excluded": []}
        labelled, signs = sr.attribute([ev], session, ann, 300)
        self.assertEqual(labelled[0]["cat"], "CORRECT")
        self.assertIs(signs[0]["credited"], labelled[0])


class StatisticsTest(unittest.TestCase):
    def test_wilson_matches_closed_form_values(self):
        lo, hi = sr.wilson(0, 10)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.2775, places=3)
        lo, hi = sr.wilson(10, 10)
        self.assertAlmostEqual(lo, 0.7225, places=3)
        self.assertEqual(sr.wilson(0, 0), [None, None])

    def test_percentile_nearest_rank(self):
        self.assertEqual(sr.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.5), 5)
        self.assertEqual(sr.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.95), 10)
        self.assertIsNone(sr.percentile([], 0.5))

    def test_small_samples_are_flagged(self):
        self.assertTrue(sr.rate(3, 5)["small_n"])
        self.assertFalse(sr.rate(30, 50)["small_n"])


class MetricsTest(unittest.TestCase):
    def setUp(self):
        self.report = Study().write().run()
        self.cfg = self.report["configurations"]["live_device / STABLE"]

    def test_attribution_categories(self):
        ov = self.cfg["overall"]["legacy"]
        self.assertEqual((ov["correct_events"], ov["wrong_events"], ov["duplicate_events"], ov["nonsign_events"]),
                         (1, 1, 1, 3))
        self.assertEqual(ov["excluded_from_metrics"], {"UNLABELED": 1, "UNLOCATED": 1})
        self.assertEqual(self.report["events_not_matched_to_a_manifest_session"], 0)

    def test_original_behaviour_A_commits_everything_labelled(self):
        a = self.cfg["overall"]["legacy"]
        self.assertEqual((a["committed_correct"], a["committed_wrong"], a["committed_duplicate"], a["committed_nonsign"]),
                         (1, 1, 1, 3))
        self.assertAlmostEqual(a["precision"]["value"], 1 / 6, places=3)
        self.assertEqual(a["event_recall_correct_retention"]["value"], 1.0)
        self.assertEqual(a["false_positive_rate_nonsign"]["value"], 1.0)
        self.assertAlmostEqual(a["sign_recall_end_to_end"]["value"], 1 / 3, places=3)
        self.assertAlmostEqual(a["recognition_coverage"]["value"], 2 / 3, places=3)
        self.assertAlmostEqual(a["upstream_miss_rate_no_event"]["value"], 1 / 3, places=3)
        self.assertAlmostEqual(a["false_nonsign_commits_per_minute"], 20.0, places=3)  # 3 events / 0.15 min

    def test_gate_behaviour_B_including_what_the_gate_fails_to_remove(self):
        b = self.cfg["overall"]["gated"]
        self.assertEqual((b["committed_correct"], b["committed_wrong"], b["committed_duplicate"], b["committed_nonsign"]),
                         (1, 0, 1, 1))  # the duplicate and HOSPITAL1 are still committed: reported, not hidden
        self.assertAlmostEqual(b["precision"]["value"], 1 / 3, places=3)
        self.assertEqual(b["false_rejection_rate"]["value"], 0.0)
        self.assertAlmostEqual(b["false_positive_rate_nonsign"]["value"], 1 / 3, places=3)
        self.assertAlmostEqual(b["recognition_coverage"]["value"], 1 / 3, places=3)  # HOME's wrong word was withheld
        self.assertAlmostEqual(b["false_nonsign_commits_per_minute"], 1 / 0.15, places=2)
        self.assertEqual(b["f1_event"], round(2 * (1 / 3) * 1.0 / ((1 / 3) + 1.0), 4))

    def test_confusion_matrices_and_per_class_and_per_activity(self):
        g = self.cfg["confusion_gated"]
        self.assertEqual(g["HELLO"], {"HELLO": 1})
        self.assertEqual(g["HOME"], {"WITHHELD": 1})
        self.assertEqual(g["TABLE"], {"NO_EVENT": 1})
        self.assertEqual(g["NONSIGN:seat_adjustment"], {"HOSPITAL1": 1})
        self.assertEqual(g["DUPLICATE_OF:HELLO"], {"HELLO": 1})
        self.assertEqual(self.cfg["confusion_legacy"]["HOME"], {"THINK": 1})
        act = self.cfg["by_nonsign_activity"]["seat_adjustment"]
        self.assertEqual((act["events"], act["legacy"]["committed"], act["gated"]["committed"]), (2, 2, 1))
        idle = self.cfg["by_nonsign_activity"]["idle_open_hand"]
        self.assertEqual((idle["events"], idle["legacy"]["committed"], idle["gated"]["committed"]), (1, 1, 0))
        self.assertEqual(self.cfg["by_sign_class"]["HELLO"]["signs"], 1)
        self.assertEqual(self.cfg["by_sign_class"]["HOME"]["gated"]["sign_recall"]["value"], 0.0)

    def test_by_signer_and_by_condition_are_present(self):
        self.assertIn("E1", self.cfg["by_signer"])
        self.assertIn("lighting=dim", self.cfg["by_condition"])
        self.assertIn("distance=far", self.cfg["by_condition"])

    def test_latency_uses_logged_values_and_labelled_sign_ends(self):
        lat = self.cfg["latency"]
        self.assertEqual(lat["logical_end_to_commit_ms (decoder, by design)"]["n"], 8)  # all 8 logged an end offset
        ends = lat["physical_sign_end_to_decision_ms (labelled signs, credited events)"]
        # credited: HELLO commit 11300 - end 11000 = 300 ; HOME commit 21100 - end 21000 = 100
        self.assertEqual(ends["n"], 2)
        self.assertEqual(ends["p50"], 100)

    def test_caveats_are_generated_not_optional(self):
        text = " ".join(self.cfg["caveats"])
        self.assertIn("1 evaluation signer", text)
        self.assertIn("non-sign events", text)
        self.assertIn("Wilson", text)

    def test_reports_are_written(self):
        s = Study().write()
        s.run()
        names = {p.name for p in (s.root / "out").iterdir()}
        self.assertIn("report.json", names)
        self.assertIn("report.md", names)
        self.assertTrue(any(n.startswith("confusion_") and n.endswith("_gated.csv") for n in names))
        self.assertIn("synthetic", (s.root / "out" / "report.md").read_text(encoding="utf-8"))

    def test_no_logs_no_numbers(self):
        s = Study()
        s.events = []
        s.write()
        cfg = s.run()["configurations"]["live_device / (no events logged)"]["overall"]["gated"]
        self.assertIsNone(cfg["precision"]["value"])
        self.assertIsNone(cfg["f1_event"])
        self.assertEqual(cfg["upstream_miss_rate_no_event"]["value"], 1.0)  # all 3 signs had no event

    def test_torn_final_log_line_is_skipped_and_drop_counters_surface(self):
        s = Study().write(torn_line=True)
        rep = s.run()
        self.assertEqual(rep["events_in_logs"], len(EVENTS))
        self.assertEqual(rep["log_health"]["0123456789abcdef"]["dropped"], 2)
        self.assertEqual(rep["log_health"]["0123456789abcdef"]["write_failures"], 1)

    def test_events_with_an_unknown_run_label_are_counted_not_silently_dropped(self):
        s = Study()
        s.events.append(event(1000, 500, 100, "HELLO", 0.9, "ACCEPT", run="STRANGER"))
        self.assertEqual(s.write().run()["events_not_matched_to_a_manifest_session"], 1)

    def test_fallback_and_gate_off_events_are_called_out(self):
        s = Study()
        s.events[0] = event(11300, 1100, 500, "HELLO", 0.97, "ACCEPT", fallback=True, gate_on=False)
        text = " ".join(s.write().run()["configurations"]["live_device / STABLE"]["caveats"])
        self.assertIn("fell back", text)
        self.assertIn("gate both ON and OFF", text)

    def test_configurations_are_reported_separately(self):
        s = Study()
        s.events.append(event(11400, 1100, 500, "HELLO", 0.8, "ACCEPT", cfg="EXPERIMENTAL"))
        rep = s.write().run()
        self.assertIn("live_device / STABLE", rep["configurations"])
        self.assertIn("live_device / EXPERIMENTAL", rep["configurations"])


class CliTest(unittest.TestCase):
    def test_cli_exits_2_with_a_message_instead_of_a_traceback_on_missing_inputs(self):
        s = Study().write()
        (s.root / "annotations.json").unlink()
        rc = sr.main(["--manifest", str(s.root / "manifest.json"), "--logs", str(s.root / "logs"),
                      "--out", str(s.root / "out")])
        self.assertEqual(rc, 2)

    def test_cli_exits_2_when_a_precondition_is_violated_and_0_otherwise(self):
        bad = Study()
        bad.registry["training_signers"].append("E1")
        bad.write()
        self.assertEqual(sr.main(["--manifest", str(bad.root / "manifest.json"), "--logs", str(bad.root / "logs"),
                                  "--out", str(bad.root / "out")]), 2)
        good = Study().write()
        self.assertEqual(sr.main(["--manifest", str(good.root / "manifest.json"), "--logs", str(good.root / "logs"),
                                  "--out", str(good.root / "out")]), 0)


class PreconditionTest(unittest.TestCase):
    def assertRefused(self, study: Study, needle: str, **kw):
        with self.assertRaises(sr.StudyError) as cm:
            study.run(**{k: v for k, v in kw.items() if k == "development_only"})
        self.assertIn(needle, str(cm.exception))

    def test_refuses_when_annotations_changed_after_the_freeze(self):
        s = Study().write()
        s.annotations["sessions"]["R1"]["signs"][0]["gloss"] = "GOOD"
        (s.root / "annotations.json").write_text(json.dumps(s.annotations), encoding="utf-8")  # edited after freeze
        self.assertRefused(s, "SHA-256")

    def test_refuses_annotations_that_carry_model_output(self):
        for bad in ({"predicted": "HELLO"}, {"p1": 0.9}, {"top1": "HELLO"}, {"model_confidence": 0.5}):
            s = Study()
            s.annotations["sessions"]["R1"]["signs"][0].update(bad)
            s.write()
            self.assertRefused(s, "not allowed")
        s = Study()
        s.annotations["sessions"]["R1"]["predictions"] = []
        s.write()
        self.assertRefused(s, "not allowed")

    def test_refuses_signer_leakage_between_evaluation_and_training_or_calibration(self):
        for key in ("training_signers", "calibration_signers"):
            s = Study()
            s.registry[key].append("E1")
            s.write()
            self.assertRefused(s, "signer leakage")

    def test_development_only_runs_but_is_stamped_not_evidence(self):
        s = Study()
        s.registry["training_signers"].append("E1")
        rep = s.write().run(development_only=True)
        self.assertIn("NOT EVIDENCE", rep["banner"])
        self.assertTrue(any("LEAKAGE" in w for w in rep["warnings"]))

    def test_refuses_without_a_registry_unless_development_only(self):
        s = Study().write(registry=False)
        self.assertRefused(s, "registry")
        self.assertIn("NOT EVIDENCE", s.run(development_only=True)["banner"])

    def test_refuses_unknown_tier_and_missing_lock_and_no_evaluation_session(self):
        s = Study(); s.manifest["evidence_tier"] = "vibes"; s.write(); self.assertRefused(s, "evidence_tier")
        s = Study(); s.manifest["annotation_locked_utc"] = ""; s.write(); self.assertRefused(s, "annotation_locked_utc")
        s = Study(); s.manifest["sessions"][0]["role"] = "calibration"; s.write(); self.assertRefused(s, "evaluation")

    def test_refuses_inverted_intervals_and_unknown_sessions(self):
        s = Study(); s.annotations["sessions"]["R1"]["signs"][0]["end_ms"] = 5; s.write()
        self.assertRefused(s, "inverted")
        s = Study(); s.annotations["sessions"]["GHOST"] = {"signs": [], "nonsign": [], "excluded": []}; s.write()
        self.assertRefused(s, "not in the manifest")

    def test_unblinded_or_single_annotator_studies_are_warned(self):
        s = Study()
        s.manifest["annotators"] = {"count": 1, "blind_to_model_output": False}
        warnings = " ".join(s.write().run()["warnings"])
        self.assertIn("NOT attested blind", warnings)
        self.assertIn("fewer than 2 annotators", warnings)

    def test_calibration_sessions_never_enter_the_report(self):
        s = Study()
        s.manifest["sessions"].append({"run_label": "C9", "signer_id": "C1", "role": "calibration",
                                       "video_t0_wall_utc_ms": T0})
        s.events.append(event(11300, 1100, 500, "HELLO", 0.97, "ACCEPT", run="C9"))
        cfg = s.write().run()["configurations"]["live_device / STABLE"]
        self.assertEqual(cfg["signers"], ["E1"])


if __name__ == "__main__":
    unittest.main()
