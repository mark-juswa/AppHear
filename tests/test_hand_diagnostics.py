"""Parsing/analysis of controlled hand-diagnostic logs, on synthetic lines (stdlib only)."""
import json
import unittest

from eval.hand_diagnostics import analyze_scenarios as A

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


class CaptureIntervalTests(unittest.TestCase):
    def test_capture_interval_and_completion(self):
        def fr(i, cap_ms, done_ms):
            return frame(i, 0) .replace('"analyzer_ms"', '"capture_timestamp_ns": %d, "completed_timestamp_ns": %d, "analyzer_ms"' % (cap_ms * 10**6, done_ms * 10**6))
        lines = [fr(3, 1000, 1150), fr(4, 1067, 1210), fr(5, 1200, 1350)]
        r = A.analyse_frames(A.parse_v3(lines))
        self.assertEqual(r["latency_ms"]["capture_interval_ms(delivered frames)"]["n"], 2)
        self.assertAlmostEqual(r["latency_ms"]["capture_interval_ms(delivered frames)"]["p50"], 100.0, delta=34)
        self.assertEqual(r["latency_ms"]["capture_to_completed_ms"]["n"], 3)


if __name__ == "__main__":
    unittest.main()
