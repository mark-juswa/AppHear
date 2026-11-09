"""Parsing/analysis of controlled hand-diagnostic logs, on synthetic lines (stdlib only)."""
import json
import unittest

try:  # numpy is only present in the investigation venv, not in the repo's baseline environment
    from eval.hand_diagnostics import analyze_probe as P
except ModuleNotFoundError:
    P = None
try:
    from eval.hand_diagnostics import analyze_generalization as GEN
except ModuleNotFoundError:
    GEN = None
from eval.hand_diagnostics import analyze_scenarios as A
from eval.hand_diagnostics import shadow_join as S

DETECT = ("11-10 02:00:00.000  1  2 I AppHearDetect: in=112 ok=111 camDropEst=259 faults=0 recov=0/0 fatal=0 fpsIn=5.2 fpsOk=5.1 busy=98.1% "
          "frame_age=48.2/104.8 pose=49.6/175.9 hands_wall=56.6/113.9 ui_hop=18.0/41.2 end_to_end=265.4/393.9 "
          "hands[n=112 none=27 L=8 R=7 both=70 same=43 part=5 sep=22 na=0 same.roi=43/0 same.pres=0.92/0.94 same.hand=0.59/0.61 same.sup=0.24/0.44] "
          "render[n=111 skipped=0 stale=0 redraw=0]")


def frame(i, obs, pres=(-1, -1), hand=(-1, -1), roi=-1, skel=-1, analyzer=200.0, perception=190.0):
    d = {"schema_version": "apphear.perception_v3_timing.v1", "source_index": i, "hands_observed": obs, "hand_presence": list(pres),
         "hand_handedness": list(hand), "hand_roi_iou": roi, "hand_skeleton_iou": skel, "frame_age_ms": 50.0, "preprocess_ms": 1.0,
         "pose_inference_and_output_ms": 90.0, "pose_decode_ms": 0.2, "hand_crop_ms": 2.0, "hand_inference_ms": 60.0, "hands_wall_ms": 62.0,
         "perception_ms": perception, "analyzer_ms": analyzer}
    return "11-10 02:00:00.000  1  2 I AppHearV3: " + json.dumps(d)


class ParseTests(unittest.TestCase):
    def test_summary_line(self):
        d = A.parse_detect_line(DETECT)
        self.assertEqual(d["in"], 112.0)
        self.assertEqual(d["stages"]["pose"], {"p50": 49.6, "p95": 175.9})
        self.assertEqual(d["stages"]["end_to_end"]["p50"], 265.4)
        self.assertNotIn("recov", d["stages"])
        self.assertEqual(d["hands"]["same.roi"], "43/0")
        self.assertEqual(d["hands"]["both"], "70")
        self.assertEqual(d["render"], {"n": 111, "skipped": 0, "stale": 0, "redraw": 0})
        self.assertEqual(d["busy_pct"], 98.1)

    def test_non_summary_lines_ignored(self):
        self.assertIsNone(A.parse_detect_line("AppHearPhone: state package=X"))
        self.assertEqual(A.parse_v3(["garbage", "AppHearV3: {not json}"]), [])


class FrameTests(unittest.TestCase):
    def test_counts_bins_slots_and_warmup(self):
        lines = [frame(0, 0), frame(1, 0), frame(2, 0)]                                  # warm-up, skipped
        lines += [frame(3, 1, pres=(0.9, 0.1), hand=(0.2, 0.5))]                          # one hand, slot L
        lines += [frame(4, 1, pres=(0.1, 0.9), hand=(0.5, 0.8))]                          # one hand, slot R
        lines += [frame(5, 2, (0.9, 0.9), (0.1, 0.9), roi=0.95, skel=0.9)]                # duplicate-like
        lines += [frame(6, 2, (0.9, 0.9), (0.1, 0.9), roi=0.0, skel=0.0)]                 # separate
        lines += [frame(7, 2, (0.9, 0.9), (0.1, 0.9), roi=0.2, skel=0.3)]                 # partial
        r = A.analyse_frames(A.parse_v3(lines))
        self.assertEqual(r["frames_used_after_warmup"], 5)
        self.assertEqual(r["hands_observed_frames"], {0: 0, 1: 2, 2: 3})
        self.assertEqual(r["one_hand_frames"]["observed_slot"], {"L": 1, "R": 1, "ambiguous": 0})
        t = r["two_hand_frames"]
        self.assertEqual(t["skeleton_iou_bins"], {"lt0.1": 1, "0.1to0.5": 1, "ge0.5": 1})
        self.assertEqual(t["roi_vs_skeleton_crosstab"]["roi>=0.5&skel>=0.5"], 1)
        self.assertEqual(t["roi_vs_skeleton_crosstab"]["roi<0.5&skel<0.5"], 2)
        self.assertEqual(r["one_hand_frames"]["mean_handedness_when_slot_R"], 0.8)

    def test_latency_shares(self):
        r = A.analyse_frames(A.parse_v3([frame(i, 0) for i in range(3, 10)]))
        self.assertEqual(r["latency_ms"]["analyzer_ms"]["p50"], 200.0)
        self.assertEqual(r["latency_ms"]["session_ms(analyzer-perception)"]["p50"], 10.0)
        self.assertEqual(r["median_share_of_analyzer_pct"]["pose_inference_and_output_ms"], 45.0)


@unittest.skipUnless(P is not None, "needs numpy (investigation venv)")
class ProbeAnalysisTests(unittest.TestCase):
    def test_auc_basic_and_ties(self):
        self.assertEqual(P.auc([3, 4], [1, 2]), 1.0)
        self.assertEqual(P.auc([1, 2], [3, 4]), 0.0)
        self.assertEqual(P.auc([1, 1], [1, 1]), 0.5)
        self.assertIsNone(P.auc([], [1]))

    def test_box_ious(self):
        sq = [[0, 0], [10, 0], [0, 10], [10, 10]]
        self.assertEqual(P.skeleton_iou(sq, sq), 1.0)
        self.assertEqual(P.skeleton_iou(sq, [[20, 20], [30, 20], [20, 30]]), 0.0)
        self.assertEqual(P.roi_iou([5, 5, 10], [5, 5, 10]), 1.0)
        self.assertEqual(P.roi_iou(None, [5, 5, 10]), 0.0)

    @staticmethod
    def _group(support, roi, presence=0.99, handedness=0.5, observed_=True):
        g = {"support_mean": support, "support_max": support, "support_p50": support, "n_ge_010": 21, "n_ge_030": 21 if support >= 0.3 else 0,
             "wrist_xy": [roi[0], roi[1]], "wrist_support": support, "roi": roi}
        g["refined"] = {"presence": presence if observed_ else 0.1, "handedness": handedness, "n_valid": 21,
                        "xy": [[roi[0] + i, roi[1] + i] for i in range(21)]}
        g["refined_flipped_crop"] = {"presence": 0.9, "handedness": 1 - handedness, "n_valid": 21, "xy": []}
        return g

    def _frame(self, seg, n, gl, gr):
        wrist = {"L": {"xy": [100.0, 100.0], "support": 0.5}, "R": {"xy": [100.0, 100.0], "support": 0.5}}
        mk = lambda: {"size": [480, 640], "body_wrist": wrist, "groups": {"L": gl, "R": gr}}
        return {"segment": seg, "n": n, "normal": mk(), "mirrored_image": mk()}

    def test_slot_consistency_follows_the_measured_convention(self):
        # value = P(right hand) on the unmirrored crop: a right-slot group with 0.98 is consistent, a left-slot group with 0.98 is not
        r = self._frame("s", 0, self._group(0.2, [100, 100, 60], handedness=0.98), self._group(0.7, [100, 100, 60], handedness=0.98))
        self.assertAlmostEqual(P.group_features(r, "R")["slot_consistency"], 0.98)
        self.assertAlmostEqual(P.group_features(r, "L")["slot_consistency"], 0.02)

    def test_phantom_vs_real_table_labels_and_sweep(self):
        sched = {"one": {"truth": {"L": False, "R": True}}, "none": {"truth": {"L": False, "R": False}},
                 "both_apart": {"truth": {"L": True, "R": True}}, "dyn": {"truth": None}}
        rows = [self._frame("one", i, self._group(0.15, [100, 100, 60]), self._group(0.6, [105, 100, 60])) for i in range(5)]
        rows += [self._frame("both_apart", i, self._group(0.8, [100, 100, 60]), self._group(0.78, [110, 100, 60])) for i in range(5)]
        rows += [self._frame("none", 0, self._group(0.07, [100, 100, 60], observed_=False), self._group(0.07, [100, 100, 60], observed_=False))]
        rows += [self._frame("dyn", 0, self._group(0.5, [100, 100, 60]), self._group(0.5, [100, 100, 60]))]
        table = P.build_table(rows, sched)
        self.assertEqual(len(table), 20)                      # 'none' (unobserved) and 'dyn' (dynamic) excluded
        self.assertEqual(sum(1 for t in table if not t["real"]), 5)
        self.assertTrue(all(t["real"] for t in table if t["segment"] == "both_apart"))
        self.assertEqual(P.single_signal_aucs(table)["support_mean"]["auc_all_real_vs_phantom"], 1.0)
        sweep = P.support_ratio_sweep(rows, sched)["categories"]
        self.assertEqual(sweep["phantom_one_hand"]["fraction_weaker_group_dropped"]["0.4"], 1.0)
        self.assertEqual(sweep["two_hand_apart"]["fraction_weaker_group_dropped"]["0.7"], 0.0)

    def test_loso_on_separable_table(self):
        table = []
        for seg in ("a", "b", "c"):
            for i in range(10):
                table.append({"segment": seg, "real": True, "two_hands": False, "support_mean": 0.6 + 0.01 * i, "n_ge_030": 21, "presence": 0.9,
                              "slot_consistency": 0.9, "wrist_agreement": -0.5, "body_wrist_support": 0.5})
                table.append({"segment": seg, "real": False, "two_hands": False, "support_mean": 0.15 + 0.01 * i, "n_ge_030": 0, "presence": 0.9,
                              "slot_consistency": 0.1, "wrist_agreement": -3.0, "body_wrist_support": 0.0})
        r = P.loso_logistic(table, ["support_mean"])
        self.assertGreater(r["auc_out_of_segment"], 0.99)
        self.assertEqual(r["phantom_rejected_at_p0.5"], 1.0)


class CaptureIntervalTests(unittest.TestCase):
    def test_capture_interval_and_completion(self):
        def fr(i, cap_ms, done_ms):
            return frame(i, 0) .replace('"analyzer_ms"', '"capture_timestamp_ns": %d, "completed_timestamp_ns": %d, "analyzer_ms"' % (cap_ms * 10**6, done_ms * 10**6))
        lines = [fr(3, 1000, 1150), fr(4, 1067, 1210), fr(5, 1200, 1350)]
        r = A.analyse_frames(A.parse_v3(lines))
        self.assertEqual(r["latency_ms"]["capture_interval_ms(delivered frames)"]["n"], 2)
        self.assertAlmostEqual(r["latency_ms"]["capture_interval_ms(delivered frames)"]["p50"], 100.0, delta=34)
        self.assertEqual(r["latency_ms"]["capture_to_completed_ms"]["n"], 3)


@unittest.skipUnless(GEN is not None, "needs numpy (investigation venv)")
class GeneralizationTests(unittest.TestCase):
    @staticmethod
    def _frame(subject, config, ratio, roi_iou, truth, two, support=None, slot=None, bws=None):
        support = support or {"L": ratio, "R": 1.0}
        return {"subject": subject, "segment": config, "n": 0, "config": config, "truth": truth, "two_hands": two, "roi_iou": roi_iou, "support": support,
                "ratio": ratio, "weaker": "L" if support["L"] <= support["R"] else "R", "bws": bws or {"L": 0.5, "R": 0.5},
                "slot_consistency": slot or {"L": 0.5, "R": 0.5}}

    def test_ratio_rule_drops_only_the_weaker_group_and_only_with_overlap(self):
        f = self._frame("a", "x", 0.2, 0.8, {"L": False, "R": True}, False)
        self.assertEqual(GEN.flagged(f, "ratio", 0.5), {"L"})
        self.assertEqual(GEN.flagged(self._frame("a", "x", 0.2, 0.05, {"L": False, "R": True}, False), "ratio", 0.5), set())   # no overlap
        self.assertEqual(GEN.flagged(self._frame("a", "x", 0.9, 0.8, {"L": True, "R": True}, True), "ratio", 0.5), set())          # equal pair

    def test_corroborator_can_only_remove_decisions_never_add_them(self):
        f = self._frame("a", "x", 0.2, 0.8, {"L": False, "R": True}, False, slot={"L": 0.9, "R": 0.9}, bws={"L": 0.9, "R": 0.5})
        self.assertEqual(GEN.flagged(f, "ratio", 0.5), {"L"})
        self.assertEqual(GEN.flagged(f, "ratio+corrob", 0.5), set())          # handedness and wrist both say the weaker group is a real left hand

    def test_rates_count_echo_real_and_two_hand_units(self):
        frames = [self._frame("a", "x", 0.2, 0.8, {"L": False, "R": True}, False),
                  self._frame("a", "y", 0.4, 0.8, {"L": True, "R": True}, True)]
        r = GEN.rates(frames, "ratio", 0.5)
        self.assertEqual((r["n_echo_units"], r["echo_rejection_rate"]), (1, 1.0))
        self.assertEqual(r["false_suppression_rate"], round(1 / 3, 4))           # 3 real units, the weaker real hand of the pair is dropped
        self.assertEqual(r["two_hand_frame_preservation_rate"], 0.0)

    def test_threshold_is_learned_on_the_training_subject_only(self):
        train = [self._frame("A", "x", 0.2, 0.8, {"L": False, "R": True}, False) for _ in range(5)]
        train += [self._frame("A", "y", 0.9, 0.8, {"L": True, "R": True}, True) for _ in range(5)]
        test = [self._frame("B", "x", 0.45, 0.8, {"L": False, "R": True}, False) for _ in range(5)]   # test echoes sit where train has a gap
        T = GEN.learn_threshold(train, "ratio")
        self.assertTrue(0.2 < T < 0.9)
        res = GEN.transfer(train + test, ["A", "B"])["train=A -> test=B"]["ratio"]
        self.assertAlmostEqual(res["threshold_learned_on_train"], round(T, 4), places=3)      # unchanged by any test-subject data

    def test_handedness_rule_uses_the_natural_boundary_and_is_never_tuned(self):
        f = self._frame("a", "x", 0.9, 0.8, {"L": True, "R": True}, True, slot={"L": 0.3, "R": 0.8})
        self.assertEqual(GEN.flagged(f, "handedness", None), {"L"})
        self.assertIsNone(GEN.learn_threshold([f], "handedness"))


class ShadowJoinTests(unittest.TestCase):
    @staticmethod
    def _line(wall_ms, ratio, weaker, mask, roi_iou=0.8):
        d = {"schema": "apphear.hand_echo_shadow.v1", "seq": 0, "wall_ms": wall_ms, "ratio": ratio, "weaker": weaker, "roi_iou": roi_iou, "skeleton_iou": None,
             "mask": mask, "grid": S.GRID, "L": {}, "R": {}}
        return "11-10 02:00:00.0  1  2 I AppHearEcho: " + json.dumps(d)

    def test_parse_ignores_noise_and_other_schemas(self):
        text = "\n".join(["junk", self._line(1000, 0.2, "LEFT", 31), "AppHearEcho: {bad json", 'x {"schema":"other"}'])
        self.assertEqual(len(S.parse_shadow(text)), 1)

    def test_join_scores_echo_wrong_group_and_genuine_pair_drops(self):
        sched = {"one_R": {"truth": {"L": False, "R": True}, "epoch_start": 100.0, "frames": 60, "fps": 6.0, "config": "distance"},
                 "two": {"truth": {"L": True, "R": True}, "epoch_start": 200.0, "frames": 60, "fps": 6.0, "config": "two_hand"},
                 "none": {"truth": {"L": False, "R": False}, "epoch_start": 300.0, "frames": 6, "fps": 6.0}}
        recs = S.parse_shadow("\n".join([
            self._line(101_000, 0.2, "LEFT", 0b11111),       # right hand shown, LEFT weaker dropped -> correct echo drop
            self._line(102_000, 0.2, "RIGHT", 0b11111),      # the REAL hand would be dropped -> wrong group
            self._line(103_000, 0.9, "LEFT", 0),             # echo with high ratio: missed
            self._line(104_000, None, "NONE", 0),            # one group only: not a duplicate frame
            self._line(201_000, 0.95, "LEFT", 0),            # genuine pair kept
            self._line(202_000, 0.45, "RIGHT", 0b11100),     # genuine pair, dropped for tau 0.5/0.6/0.7
            self._line(301_000, 0.1, "LEFT", 0b11111),       # 'none' window: excluded
            self._line(900_000, 0.1, "LEFT", 0b11111)]))     # outside every window
        j = S.join(recs, sched)
        self.assertEqual(len(j), 6)
        r = S.score(j)
        self.assertEqual(r["frames_both_groups_observed"], 5)
        g = r["by_grid"]["0.5"]
        self.assertEqual((g["one_hand_frames"], g["echo_suppressed"], g["wrong_group_dropped"]), (3, 1, 1))
        self.assertEqual((g["two_hand_frames"], g["genuine_pair_dropped"]), (2, 1))
        self.assertEqual(r["by_grid"]["0.3"]["genuine_pair_dropped"], 0)      # bit 0 (tau 0.3) not set for the 0.45 pair
        self.assertEqual(g["per_config"]["two_hand"]["genuine_pair_dropped"], 1)


if __name__ == "__main__":
    unittest.main()
