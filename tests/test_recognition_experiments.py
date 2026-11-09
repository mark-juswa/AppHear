"""Tests of the Phase 3 analysis tools (standard library only).

Two kinds of test, kept separate on purpose:
  * UNIT tests on small hand-computed SYNTHETIC inputs: they verify the arithmetic, never describe the system;
  * REPRODUCTION tests on the real tracked evidence: they assert the tools recompute numbers the repo's own audit
    documents already published, so a silent change in a tool or in the evidence is caught.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from eval.recognition_experiments import error_analysis as ea
from eval.recognition_experiments import gate_study as gs
from eval.recognition_experiments import model_contract_check as mcc


def cls(clips=4, signers=3, recall=0.5, dense=0.5, hand=0.6, fit=0.8, train_signers=14, partner="", share=0.0, labels=None):
    return {"clips": clips, "signers": signers, "recall_real": recall, "recall_dense": dense, "hand": hand, "train_fit": fit,
            "train_signers": train_signers, "partner": partner, "partner_share": share, "labels": labels or ["UNEXPLAINED"]}


class ErrorAnalysisUnitTest(unittest.TestCase):
    def test_pooled_metrics_are_clip_weighted_and_macro_is_unweighted(self):
        c = {"A": cls(clips=10, recall=1.0), "B": cls(clips=30, recall=0.0), "C": cls(clips=10, recall=0.5)}
        p = ea.pooled(c)
        self.assertEqual(p["clips"], 50)
        self.assertAlmostEqual(p["clip_weighted_accuracy"], (10 + 0 + 5) / 50)
        self.assertAlmostEqual(p["macro_recall"], 0.5, places=4)
        self.assertEqual(p["classes_zero_recall"], 1)
        self.assertEqual(p["hard_classes_recall_le_0.30"], 1)

    def test_weakest_ranks_by_recall_then_support_and_ignores_tiny_samples(self):
        c = {"TINY": cls(clips=1, recall=0.0), "LOW_BIG": cls(clips=9, recall=0.0), "LOW_SMALL": cls(clips=5, recall=0.0),
             "MID": cls(clips=8, recall=0.4)}
        self.assertEqual([r["cls"] for r in ea.weakest(c, k=3)], ["LOW_BIG", "LOW_SMALL", "MID"])

    def test_pair_estimates_use_errors_times_share_and_combine_both_directions(self):
        c = {"CHAIR": cls(clips=10, recall=0.0, partner="SIT", share=0.5), "SIT": cls(clips=10, recall=0.5, partner="CHAIR", share=0.4),
             "X": cls(clips=4, recall=0.5, partner="Y", share=1.0), "Y": cls(clips=4, recall=1.0)}
        pairs = {p["pair"]: p for p in ea.pair_estimates(c)}
        self.assertAlmostEqual(pairs["CHAIR/SIT"]["a_to_b"], 5.0)          # 10 clips x 100% errors x 0.5
        self.assertAlmostEqual(pairs["CHAIR/SIT"]["b_to_a"], 2.0)          # 10 x 50% x 0.4
        self.assertAlmostEqual(pairs["CHAIR/SIT"]["estimated_errors"], 7.0)
        self.assertAlmostEqual(pairs["X/Y"]["estimated_errors"], 2.0)

    def test_model_delta_counts_only_changes_larger_than_the_threshold(self):
        base = {"A": cls(recall=0.50), "B": cls(recall=0.50), "C": cls(recall=0.50), "D": cls(recall=0.50)}
        new = {"A": cls(recall=0.56), "B": cls(recall=0.44), "C": cls(recall=0.55), "D": cls(recall=0.20)}
        d = ea.model_delta(base, new)
        self.assertEqual((d["up"], d["down"], d["within"]), (1, 2, 1))
        self.assertEqual(d["largest_drops"][0][0], "D")

    def test_spearman_known_values_and_ties(self):
        self.assertEqual(ea.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertEqual(ea.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertIsNone(ea.spearman([1, 1, 1], [1, 2, 3]))
        self.assertIsNone(ea.spearman([1, 2], [1, 2]))

    def test_funnel_separates_classifier_limited_from_upstream_loss(self):
        summary = {"signs": 100, "acquired": 80, "detected": 50, "correct_words": 20, "oracle_correct": 40, "merged_events": 3,
                   "acquired_no_distinct_event": 30, "extra_events": 2, "word_precision": 0.4}
        data = {"summary": {"NATURAL": summary, "CONTINUOUS": summary,
                            "per_signer_correct_word_rate": {"NATURAL:asl_citizen:P1": 0.2, "CONTINUOUS:asl_citizen:P1": 0.1}}}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "f.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            f = ea.funnel(p)["NATURAL"]
        self.assertEqual(f["classifier_limited_signs"], 60)             # wrong even with a perfect window
        self.assertEqual(f["lost_upstream_of_classifier"], 20)           # 40 recoverable - 20 delivered
        self.assertEqual(f["share_of_oracle_correct_words_delivered"], 0.5)
        self.assertEqual(f["per_signer_correct_word_rate"], {"P1": 0.2})


class ErrorAnalysisReproductionTest(unittest.TestCase):
    """Recompute numbers published in docs/audit/WORD_ACCURACY_236 and WORD_PRIORITIES from the tracked evidence."""

    @classmethod
    def setUpClass(cls):
        cls.models = ea.load_models()

    def test_all_236_classes_are_present_for_every_model(self):
        for name, classes in self.models.items():
            self.assertEqual(len(classes), 236, name)

    def test_published_hard_class_counts_98_78_64(self):
        counts = {n: ea.pooled(c)["hard_classes_recall_le_0.30"] for n, c in self.models.items()}
        self.assertEqual(counts, {"frozen": 98, "BLEND_01": 78, "BLEND_02": 64})

    def test_published_hard_label_counts_for_the_frozen_recognizer(self):
        self.assertEqual(ea.label_counts(self.models["frozen"]),
                         {"LOW_FIT": 77, "WEAK_HANDS": 20, "CADENCE": 16, "THIN_COVERAGE": 15, "PAIR": 13, "UNEXPLAINED": 13})

    def test_per_class_movement_blend01_to_blend02_and_the_one_class_float_boundary_difference(self):
        # Published (WORD_PRIORITIES_2026-10-18): up 57 / down 52 / within 127, from raw float differences. SLEEP changed
        # by exactly -5.0 points (0.525 -> 0.475); raw float arithmetic gives -0.05000000000000004 and tips it into
        # "down". The documented rule is "more than 5 points", so the tool rounds first: 57 / 51 / 128.
        d = ea.model_delta(self.models["BLEND_01"], self.models["BLEND_02"])
        self.assertEqual((d["up"], d["down"], d["within"]), (57, 51, 128))
        raw_up = raw_down = 0
        for g, base in self.models["BLEND_01"].items():
            diff = self.models["BLEND_02"][g]["recall_real"] - base["recall_real"]
            raw_up += diff > ea.MOVE_THRESHOLD
            raw_down += diff < -ea.MOVE_THRESHOLD
        self.assertEqual((raw_up, raw_down, 236 - raw_up - raw_down), (57, 52, 127))
        self.assertEqual([g for g, _ in d["largest_drops"][:3]], ["WHEN", "TODAY", "BUY"])

    def test_the_end_to_end_funnel_of_the_production_segmenter(self):
        f = ea.funnel(ea.PROBES / "heldout_dev_e2e/s2r2_base.json")["NATURAL"]
        self.assertEqual((f["signs"], f["acquired_by_s2"], f["own_distinct_event"], f["correct_words"]), (812, 499, 313, 132))
        self.assertEqual(f["oracle_correct_perfect_window_same_recognizer"], 332)
        self.assertEqual(f["lost_upstream_of_classifier"], 200)

    def test_the_evidence_cannot_support_per_class_precision_and_says_so(self):
        gaps = " ".join(ea.run()["evidence_gaps"])
        self.assertIn("per-class precision", gaps)
        self.assertIn("confusion matrix", gaps)


class GateStudyUnitTest(unittest.TestCase):
    def ev(self, p1, ok, signer="s", cat="GENUINE"):
        return {"word_p1": p1, "frozen_correct": ok, "category": cat, "signer": signer, "v2_p1": p1, "v2_correct": ok,
                "frozen_top1": "A", "word_stability": 1.0}

    def test_mcnemar_exact_sign_test(self):
        self.assertEqual(gs.mcnemar_exact_p(0, 0), None)
        self.assertEqual(gs.mcnemar_exact_p(5, 5), 1.0)
        self.assertEqual(gs.mcnemar_exact_p(0, 10), round(2 / 1024, 4))

    def test_auc_ties_count_half(self):
        self.assertEqual(gs.auc([1, 2], [0, 0]), 1.0)
        self.assertEqual(gs.auc([1], [1]), 0.5)
        self.assertIsNone(gs.auc([], [1]))

    def test_reliability_of_a_perfectly_calibrated_toy_is_zero_ece(self):
        events = [self.ev(0.5, True) for _ in range(5)] + [self.ev(0.5, False) for _ in range(5)]
        r = gs.reliability(events, "frozen", genuine_only=False)
        self.assertAlmostEqual(r["ece"], 0.0, places=6)
        over = [self.ev(0.9, True)] + [self.ev(0.9, False) for _ in range(9)]
        self.assertAlmostEqual(gs.reliability(over, "frozen", False)["ece"], 0.8, places=6)   # claims 0.9, right 0.1

    def test_youden_picks_the_separating_threshold(self):
        events = [self.ev(0.9, True), self.ev(0.8, True), self.ev(0.4, False), self.ev(0.3, False)]
        j, th = gs.youden(events, "frozen")
        self.assertEqual((j, th), (1.0, 0.8))

    def test_metrics_at_reports_precision_retention_f1_and_false_rejection(self):
        events = [self.ev(0.9, True), self.ev(0.6, True), self.ev(0.4, True), self.ev(0.7, False), self.ev(0.2, False)]
        m = gs.metrics_at(events, "frozen", 0.5)
        self.assertEqual((m["committed"], m["committed_correct"], m["committed_wrong"]), (3, 2, 1))
        self.assertAlmostEqual(m["precision"]["value"], 2 / 3, places=4)
        self.assertAlmostEqual(m["retention_recall"]["value"], 2 / 3, places=4)
        self.assertAlmostEqual(m["false_rejection_rate"]["value"], 1 / 3, places=4)
        self.assertAlmostEqual(m["f1"], 2 / 3, places=4)
        self.assertEqual(gs.metrics_at(events, "frozen", None)["committed"], 5)


class GateStudyReproductionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = gs.run()

    def test_the_shipped_floor_reproduces_the_published_validation_counts(self):
        # docs/audit/probes/event_reliability/gate_policy.json: 101 correct / 102 wrong (STABLE), 173 / 98 (EXPERIMENTAL)
        for name, expected in (("S2_R2 baseline (STABLE)", (101, 102)), ("Arm A + CB70 (EXPERIMENTAL)", (173, 98))):
            ev = gs.load_events(name)
            val = [e for e in ev if e["signer"] not in gs.CAL]
            m = gs.metrics_at(val, "frozen", gs.SHIPPED[name])
            self.assertEqual((m["committed_correct"], m["committed_wrong"]), expected, name)

    def test_confidence_is_not_calibrated(self):
        for name, s in self.result.items():
            for model, g in s["G1_calibration"].items():
                self.assertGreater(g["genuine_events_is_top1_right"]["ece"], 0.10, f"{name} {model}")

    def test_class_specific_thresholds_have_no_independent_support(self):
        for name, s in self.result.items():
            self.assertEqual(s["G4_class_specific_support"]["classes_with_>=30_events_all_signers"], 0, name)
            self.assertLess(s["G4_class_specific_support"]["classes_with_>=10_events_calibration_signers"], 10, name)

    def test_stability_is_not_a_better_separator_than_top1_probability(self):
        for name, s in self.result.items():
            g6 = s["G6_temporal_stability_evidence"]
            self.assertLess(g6["auc_stability_correct_vs_rest"], g6["auc_top1_probability_correct_vs_rest"], name)

    def test_validation_signers_are_disjoint_from_calibration_signers(self):
        for name in gs.LEDGERS:
            ev = gs.load_events(name)
            self.assertTrue({e["signer"] for e in ev if e["signer"] in gs.CAL}.isdisjoint({e["signer"] for e in ev if e["signer"] not in gs.CAL}))


class ModelContractTest(unittest.TestCase):
    def test_every_packaged_recognizer_matches_its_manifest_and_the_documented_hashes(self):
        r = mcc.run()
        failed = [c for c in r["checks"] if not c["ok"]]
        self.assertEqual(failed, [])
        self.assertTrue(all(c["holds"] for c in r["doc_claims"]), r["doc_claims"])
        self.assertEqual(sorted(r["engines_in_code"]), sorted(["STABLE", "EXPERIMENTAL", "EXPERIMENTAL_WORD_BLEND", "EXPERIMENTAL_WORD_BLEND_02"]))
        self.assertEqual(r["confidence_floors_code"], {"STABLE": 0.55, "EXPERIMENTAL": 0.75})

    def test_the_vocabulary_pin_limitation_is_recorded_not_hidden(self):
        self.assertTrue(any("VOCAB_MANIFEST" in l for l in mcc.run()["limitations"]))


class SignerSeparationTest(unittest.TestCase):
    """ASL-Citizen split used by the recognizer: TRAIN / VAL (= the DEV signers) / TEST (protected) must be disjoint."""

    def test_splits_are_signer_disjoint_and_the_dev_signers_are_val_signers(self):
        sp = json.loads((Path(mcc.ROOT) / "artifacts/splits.json").read_text(encoding="utf-8"))["participant_split"]
        groups: dict[str, set[str]] = {}
        for p, s in sp.items():
            groups.setdefault(s, set()).add(p)
        self.assertEqual({k: len(v) for k, v in groups.items()}, {"train": 35, "val": 6, "test": 11})
        self.assertTrue(groups["train"].isdisjoint(groups["val"]) and groups["train"].isdisjoint(groups["test"]) and groups["val"].isdisjoint(groups["test"]))
        for signer in ("P5", "P12", "P21", "P26", "P39"):
            self.assertIn(signer, groups["val"], f"DEV signer {signer} must come from the val split, never train or test")


if __name__ == "__main__":
    unittest.main()
