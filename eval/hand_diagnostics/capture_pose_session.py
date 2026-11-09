"""Scripted, ground-truth-labelled webcam session for the hand-proposal investigation (macOS; run in a scratch venv with opencv).

Speaks each instruction (`say`), waits LEAD seconds for the person to take the pose, beeps, then saves CAPTURE seconds of CLEAN frames
(no overlay) as upright, UNMIRRORED 480x640 RGB PNGs named <segment>__<n>.png, and writes schedule.json with the ground truth the
person was asked to produce. Frames contain the person's face: keep the output directory OUTSIDE the repository.

Usage: python -m eval.hand_diagnostics.capture_pose_session <out_dir> [--set core|hard|all] [--subject NAME] [--only seg1,seg2] [--fps 6] [--list]
Each segment records its wall-clock window (epoch seconds) so device logs captured at the same time can be joined to the ground truth.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

# (segment, spoken instruction, ground truth). truth: L/R = that hand visible; None = dynamic (entering/leaving)
SCHEDULE = [
    ("none",           "No hands. Put both hands down, out of the picture.",                                    {"L": False, "R": False}),
    ("R_near_open",    "Right hand only. Palm to the camera, fingers open, close to the camera.",               {"L": False, "R": True}),
    ("R_far_open",     "Right hand only. Palm to the camera, fingers open, far from the camera. Lean back.",    {"L": False, "R": True}),
    ("R_point",        "Right hand only. Index finger pointing up, other fingers closed.",                      {"L": False, "R": True}),
    ("L_near_open",    "Left hand only. Palm to the camera, fingers open, close to the camera.",                {"L": True,  "R": False}),
    ("L_far_open",     "Left hand only. Palm to the camera, fingers open, far from the camera. Lean back.",     {"L": True,  "R": False}),
    ("L_point",        "Left hand only. Index finger pointing up, other fingers closed.",                       {"L": True,  "R": False}),
    ("both_apart",     "Both hands. Palms to the camera, clearly apart from each other.",                       {"L": True,  "R": True}),
    ("both_touching",  "Both hands. Palms pressed together.",                                                   {"L": True,  "R": True}),
    ("both_crossing",  "Both hands. Cross your forearms in an X, both hands visible.",                          {"L": True,  "R": True}),
    ("R_fast_wave",    "Right hand only. Wave fast from side to side.",                                         {"L": False, "R": True}),
    ("R_enter_leave",  "Right hand only. Raise it into view, lower it out of view, about once a second.",       None),
]

# Mandatory hard configurations (a relative-support rule could mistake a LEGITIMATE second hand for an echo here).
HARD = [
    ("h_R_near_L_far",   "Both hands, palms to the camera. Right hand very close to the camera, left hand far away at arm's length.", {"L": True,  "R": True}),
    ("h_L_near_R_far",   "Both hands, palms to the camera. Left hand very close to the camera, right hand far away at arm's length.", {"L": True,  "R": True}),
    ("h_R_edge",         "Right hand only, at the right edge of the picture, partly cut off by the edge.",                          {"L": False, "R": True}),
    ("h_both_edge",      "Both hands. Push one hand to the very edge of the picture so half of it is cut off by the edge. The other hand stays in the middle.", {"L": True,  "R": True}),
    ("h_R_no_arm",       "Right hand only. Hold your hand very low, so that only the fingers and palm show at the bottom of the picture and your whole forearm is below the picture.", {"L": False, "R": True}),
    ("h_both_one_no_arm","Both hands. One hand raised normally with its arm visible. The other hand held very low, only fingers and palm showing at the bottom of the picture, forearm below the picture.", {"L": True,  "R": True}),
    ("h_R_back",         "Right hand only, back of the hand toward the camera, fingers open.",                                      {"L": False, "R": True}),
    ("h_both_back",      "Both hands, backs of the hands toward the camera, apart from each other.",                                {"L": True,  "R": True}),
    ("h_both_overlap",   "Both hands. One hand in front of the other, fingers overlapping, palms toward the camera.",               {"L": True,  "R": True}),
]
CONFIG = {"R_near_open": "distance", "R_far_open": "distance", "L_near_open": "distance", "L_far_open": "distance",
          "R_point": "pose", "L_point": "pose", "R_fast_wave": "motion", "R_enter_leave": "dynamic", "none": "empty",
          "both_apart": "two_hand", "both_touching": "two_hand", "both_crossing": "crossing",
          "h_R_near_L_far": "unequal_pair", "h_L_near_R_far": "unequal_pair", "h_R_edge": "boundary", "h_both_edge": "boundary",
          "h_R_no_arm": "no_arm", "h_both_one_no_arm": "no_arm", "h_R_back": "back_of_hand", "h_both_back": "back_of_hand",
          "h_both_overlap": "overlap"}


def say(text: str) -> None:
    subprocess.run(["say", text], check=False)


def beep() -> None:
    subprocess.run(["afplay", "/System/Library/Sounds/Ping.aiff"], check=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path, nargs="?")
    ap.add_argument("--only", default="")
    ap.add_argument("--fps", type=float, default=6.0)
    ap.add_argument("--lead", type=float, default=4.0)
    ap.add_argument("--seconds", type=float, default=7.0)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--set", choices=("core", "hard", "all"), default="core")
    ap.add_argument("--subject", default="subject1")
    a = ap.parse_args()
    plan = {"core": SCHEDULE, "hard": HARD, "all": SCHEDULE + HARD}[a.set]
    if a.list:
        for s, t, g in plan:
            print(f"{s:15s} {g}  {t}")
        return 0
    import cv2

    from eval.hand_diagnostics.offline_probe import to_portrait
    only = {x for x in a.only.split(",") if x}
    a.out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(0)
    assert cap.isOpened(), "webcam not available"
    for _ in range(10):
        cap.read()
    say("Session starting in five seconds.")
    time.sleep(5)
    sched = {}
    for seg, text, truth in plan:
        if only and seg not in only:
            continue
        say(text)
        end_lead = time.time() + a.lead
        while time.time() < end_lead:          # keep the webcam buffer drained while the person gets ready
            cap.read()
        beep()
        t0 = time.time()
        epoch_start = t0
        n = 0
        next_t = t0
        while time.time() - t0 < a.seconds:
            ok, frame = cap.read()
            if ok and time.time() >= next_t:
                cv2.imwrite(str(a.out / f"{seg}__{n:03d}.png"), cv2.cvtColor(to_portrait(frame), cv2.COLOR_RGB2BGR))
                n += 1
                next_t += 1.0 / a.fps
        beep()
        sched[seg] = {"truth": truth, "instruction": text, "frames": n, "fps": a.fps, "config": CONFIG.get(seg, "other"),
                      "subject": a.subject, "epoch_start": epoch_start, "epoch_end": time.time()}
    (a.out / "schedule.json").write_text(json.dumps(sched, indent=1))
    say("Session finished. Thank you.")
    cap.release()
    print("done", {k: v["frames"] for k, v in sched.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
