# Phase 2 — DWPose duplicate-proposal root-cause validation

Date: 2026-11-10 · Branch `jepjep-claude` · **nothing committed** · **no app source changed this round; no fix implemented**
Builds on [`HAND_DIAGNOSTICS_CONTROLLED_TESTING_REPORT.md`](HAND_DIAGNOSTICS_CONTROLLED_TESTING_REPORT.md) and
[`BUG_HAND_DETECTION_AND_LATENCY_INVESTIGATION.md`](BUG_HAND_DETECTION_AND_LATENCY_INVESTIGATION.md).

> **UPDATE (Phase 3, same day): see [`DWPOSE_ECHO_SUPPRESSION_VALIDATION.md`](DWPOSE_ECHO_SUPPRESSION_VALIDATION.md).** A second subject, the hard configurations and on-device shadow
> decisions changed two claims below: (1) the **"wide gap" of the support ratio (echo ≤ 0.40 vs genuine ≥ 0.87) is withdrawn**, with hard configurations echoes reach 0.54 and genuine
> overlapping/crossing pairs fall to 0.39–0.62; (2) the **absolute** support/body-wrist signals do **not** transfer between subjects, only the relative ratio does (thresholds 0.527 / 0.558 learned
> independently). Unchanged: the echo is a DWPose-t property, symmetric, weak and accepted by the refiner. Decision: **no production suppression yet; shadow-only logging is available (default off).**

## 0. What was done, and the limits that apply to every number below
- **New method:** the exact shipped models (hashes asserted) were run **offline on the host** with the repo's own reference preprocessing
  (`pipeline/perception_vnext`: pose input, SimCC decode, `build_hand_roi`, hand crop). This allows controlled experiments the app cannot do
  (flipping a crop, mirroring a frame). Tools: `eval/hand_diagnostics/{offline_probe,capture_pose_session,analyze_probe}.py`; they need numpy, OpenCV,
  onnxruntime and ai-edge-litert in a scratch virtualenv, which are **not** repo dependencies.
- **Data:** one **labelled webcam session**, one subject, one room, 12 scripted poses × 43 frames = 516 clean frames (no overlay), upright and
  unmirrored 480×640 like the app's analysis frames. The person followed spoken instructions; I verified the poses from a contact sheet and overlays.
  Ground truth = the schedule (`docs/hand_diagnostics_runs/offline_2026-11-10/schedule.json`). Frames contain the subject's face and are **not** in the repo.
- **Host fp32, not the phone.** Model *behaviour* (what each group fires on) transfers; *timings* do not. My 3:4 centre crop of a 1080p webcam is close to,
  but not identical with, the emulator's frames. The earlier emulator runs showed the same phenomenon, which is consistent but not proof of parity.
- **One subject, one session.** Everything is "supported by controlled evidence on this subject", not "validated across people".
- Labels: **ESTABLISHED** = reproduced here under control; **SUPPORTED** = consistent with the data, one subject; **OPEN** = not determined.

## 1. Updated root-cause assessment

| Claim | Status | Evidence |
|---|---|---|
| The duplicate comes from DWPose-t itself, not from the overlay, camera path, emulator, mirroring or the refiner | **ESTABLISHED (this subject)** | Reproduced offline on clean frames: with one hand in view, the opposite hand group builds an ROI in **100 %** of frames in all 7 one-hand poses (right *and* left, near/far/pointing/wave) and the refiner accepts it in 53–100 %. It also occurs on the horizontally mirrored image (§2). |
| It is symmetric (left-hand-only gives a right-group echo as readily as the reverse) | **ESTABLISHED** | R-only poses → left-group echo (support 0.13–0.14); L-only poses → right-group echo (0.18–0.24). |
| The echo is a real, structured activation, not noise | **ESTABLISHED** | Empty scene: mean group support 0.07/0.09, 0.7–4.7 of 21 points ≥ 0.10. Echo: mean 0.12–0.24, **15–21 of 21** points ≥ 0.10, at 20–38 % of the real group's support. |
| The refiner cannot reject the echo | **ESTABLISHED** | Presence for echo crops 0.60–0.99 (it sees a hand in the crop because the crop contains the real hand). |
| M1 (ROIs already coincide) is the dominant mechanism; M2 (refiner snaps different crops) is rare | **SUPPORTED** | Of 387 frames with both groups observed, ROI<0.5 & skeleton≥0.5 (the M2 signature) occurs in **3 (0.8 %)**. One-hand frames: ROI IoU p50 0.81, skeleton IoU p50 0.82. Echo ROI overlap with the real ROI varies by pose (median 0.44 for left-pointing up to 0.94 for right-far), so ROI overlap is **not** a reliable signature of the echo. |
| Why DWPose-t emits the echo (architecture/training reason) | **OPEN** | Not testable without the training pipeline. Candidates: left/right ambiguity at the 192×256 input resolution; heads sharing features. |
| A single signal or small set of signals can separate echo from a real second hand | **SUPPORTED, narrow** | §3: in this session group-level support alone separates them with AUC 0.998; failures concentrate in the crossing pose, where the per-group ground truth is doubtful. |

## 2. Handedness convention (T1)

**What was tested:** for every hand group the refiner was run on the crop exactly as the app feeds it (**unmirrored**) and on the **horizontally
flipped** crop; and DWPose was run on a **fully mirrored** frame. Left-only, right-only, two-hand, mirrored and unmirrored cases are all covered.

**Findings (ESTABLISHED on this subject):**
1. **The refiner output is a chirality score of the pixels it is shown, "value ≈ probability this is a RIGHT hand".** Unmirrored crops of the subject's right
   hand read **0.88–1.00** (far/point/wave) and left hand **0.00–0.04**. Flipping the crop flips the score: across 877 accepted crops
   mean(h + h_flipped) = **0.954**, corr(h, 1 − h_flipped) = 0.84.
2. **DWPose and the refiner use the same convention.** On the unmirrored frame DWPose's right group fires on the subject's right hand. On the **mirrored**
   frame DWPose's strongest group swaps: right-only poses → left group strongest (support 0.50–0.71, right group 0.15–0.19), left-only poses → right group
   strongest. So the app is correct to feed **unmirrored** frames, and preview mirroring is display-only.
3. **The earlier "unexplained" emulator result is explained:** the one-hand run used a **very close, large hand**. Near hands give ambiguous output:
   right-near mean 0.30, left-near 0.13, presence 0.53–0.89, and the ROI visibly cuts the thumb and palm (overlay check). Handedness is unreliable
   for near, truncated hands.
4. **Not a calibrated probability.** The distribution is bimodal (deciles 0, .015, .043, .552, .978, .988, 1.0; only 21 % of values lie in 0.2–0.8). In
   the mid range value and truth disagree: crops reading 0.1–0.3 were truly right hands 68 % of the time (near right hands); 0.3–0.7 → 95 %. Treat it as a
   saturating raw score, not a probability. Only the extremes (< 0.1, > 0.9) were correct in this data (98 % and 100 %).
5. **Useful but not decisive for echo detection.** For far/pointing hands the echo crop reports the hand's *true* side, contradicting its slot (left-slot echo
   of a right hand reads 0.88–0.98), giving a slot-consistency AUC of 0.94 for real vs echo. For near hands it is ambiguous.
6. **A new case, crossing:** the left group's crop reads 0.93 and the right 0.47; the overlay shows both skeletons on **one** hand with the other hand not
   captured separately. This is consistent with group assignment that follows image position when forearms cross, but the physical hand identity there was
   not independently verified (OPEN).

**Conclusion for the instruction "do not use handedness as a suppression mechanism until validated":** it is **not validated** (near-hand and crossing
failures, uncalibrated, one subject). It can be logged as corroboration only.

## 3. DWPose support analysis (T2)

**What "support" is (CONFIRMED-CODE + ONNX):** the ONNX has **no softmax/sigmoid on its outputs** (`simcc_x`, `simcc_y` are raw MatMul outputs). For each
keypoint the app takes `argmax` over the 384/512 SimCC bins and defines `support = min(max x-logit, max y-logit)`; a keypoint is "valid" if support > 0 (decode)
and ≥ 0.10 (ROI gate). So support is an **unnormalised peak activation**, not a probability, not anatomical confidence and not a spatial-validity check:
each keypoint is decoded independently, with no joint-structure consistency test.

**Why the weaker group passes the 0.10 gate:** the gate was designed as "high-recall robust square proposal" (`hand_roi.py`) needing ≥ 5 of 21 points ≥ 0.10 and
in frame. Empty-scene noise sits at mean 0.07–0.09 (0.7–4.7 points ≥ 0.10), so ≥ 5 points suppresses noise; but the echo's mean 0.12–0.24 with 15–21 points ≥ 0.10
is far above both limits. **The gate is a noise filter, not an echo filter, and by design cannot be the latter.**

**Why one hand activates both groups:** observed behaviour only (see §1): a consistent, symmetric, lower-amplitude (≈ 0.2–0.4×) echo in the opposite group that
persists on mirrored frames. The mechanism is OPEN.

**Can the echo be told apart from a legitimate second hand with several signals? (SUPPORTED, one subject)**
Dataset: 808 observed group-frames (539 real, 269 echo) from poses with known hand count. Real vs echo AUC (threshold-free):

| signal | AUC (all real vs echo) | AUC (genuine-pair groups vs echo) |
|---|---:|---:|
| group mean support | **0.998** | 0.998 |
| points ≥ 0.30 per group | 0.997 | 0.997 |
| same-side body-wrist support | **0.999** | 0.999 |
| slot-consistency of refiner handedness | 0.936 | 0.900 |
| refiner presence | 0.644 | 0.583 |
| hand-wrist ↔ same-side body-wrist agreement | 0.564 | 0.699 |
| **skeleton overlap with the other group (negated)** | 0.695 | 0.886 |
| **ROI distance to the other group** | 0.661 | 0.857 |

Overlap-type signals are the **weakest useful** ones (confirms: no IoU-only suppression). Leave-one-pose-out logistic models (trained on other poses, scored on the
held-out pose) reach AUC 0.989–0.998; the only held-out pose with real errors is **crossing** (25 of 86). Per-pose support: echo p95 0.24 (one outlier 0.56)
versus genuine groups p05 0.30 (apart 0.69–0.89, touching 0.50–0.59, crossing 0.27–0.54): a gap, narrowest for crossing.

**A scale-free relative signal** (support of the weaker group ÷ stronger group, when both are observed and their ROIs overlap). Counterfactual, NOT a threshold:

| category | frames | weak/strong ratio min / p50 / max | weaker group would be dropped at ratio < 0.4 / 0.5 / 0.7 |
|---|---:|---|---|
| echo, one hand | 257 | 0.17 / 0.27 / 0.40 | 99.6 % / 100 % / 100 % |
| genuine pair, apart | 25 | 0.87 / 0.94 / 0.98 | 0 / 0 / 0 |
| genuine pair, touching | 43 | 0.89 / 0.98 / 1.00 | 0 / 0 / 0 |
| crossing (ground truth doubtful) | 43 | 0.50 / 0.85 / 1.00 | 0 / 2.3 % / 7.0 % |

The ratio separates the cases with a wide margin (0.40 → 0.87) on this subject and is not affected by absolute lighting or distance. It has **not** been tested on
unequal real pairs (one hand near, one far; one blurred by motion), which are exactly where it could wrongly drop a real hand (§6).

## 4. Expanded QA (T3)

Ground truth recorded per segment (`schedule.json`). **Executed offline on one subject:**

| Scenario | Executed | Result (echo = opposite group observed on a one-hand pose) |
|---|---|---|
| no hands | yes | no group observed (right group made an ROI in 21 % of frames from noise, never accepted) |
| right only: near / far / pointing | yes | echo observed 88 % / 100 % / 79 %; real group 100 % |
| left only: near / far / pointing | yes | echo observed 74 % / 100 % / 88 % |
| two apart | yes | both real, support 0.79/0.79, skeleton IoU ≈ 0 |
| two touching (palms together) | yes | both real, support 0.53/0.53 (skeleton IoU ≥ 0.5 in 24 % of the three two-hand poses pooled; apart ≈ 0, the rest from touching/crossing) |
| two crossing | yes | both groups sit on one hand (visual); second hand not separately captured |
| fast movement (right wave) | yes | real 100 %, echo 95 % |
| enter/leave | yes, **unlabelled per frame** | right observed 91 %, left 70 %: dynamic, no per-frame truth |
| different distances / poses | yes (near, far; open, point) | echo persists across all |
| mirrored frame / flipped crop | yes (§2) | |
| **multiple subjects** | **NO** | needed |
| **different lighting/background, glasses off, sleeves, long hair** | **NO** | needed |
| **unequal real pair (one near, one far; one hand motion-blurred)** | **NO** | needed before any fix (risk R1) |
| **dorsal (back-of-hand) views, fingerspelling shapes, signing sequences** | **NO** | needed |
| **hand partly out of frame, hand at the frame edge** | **NO** | needed (R2) |
| **arms not visible (sleeves/cuffs, hand held from below frame)** | **NO** | needed (R3) |
| **physical phone** | **NO** | §5 |
| **236-class regression suite** | not re-run (no Kotlin changed) | must be re-run with any fix |

Reusable protocol: `python -m eval.hand_diagnostics.capture_pose_session <dir>` (spoken, labelled), then `offline_probe`, then `analyze_probe`. To add subjects, run the
session per person into a separate directory and compare per-subject tables.

## 5. Physical-device profiling procedure (T4) — NOT executed; no phone available

Keep device classes separate: output directory `docs/hand_diagnostics_runs/<physical|emulator>_<model>_<date>/`; `capture_scenario.sh` now writes
`device_class` (**fail-safe**: `unknown` if the device is not identified), model, SDK, SoC, fingerprint, battery level/temperature, thermal status, power-saver state and app
version at the **start and end** of every run, so thermal drift is visible. Tested on the emulator (`device_class=emulator`) and on a missing device (`unknown`).

**Preconditions (record in the run note):** the diagnostic build `artifacts/phase-3.2/apphear-hand-diagnostics-debug.apk` (or a later one) installed;
battery 60–90 %, not charging, power saver off, screen brightness fixed, airplane mode on (offline), room lighting fixed, phone at room temperature (thermal status 0), other apps closed, front camera, tripod.
**Procedure:** (1) cold start the app (force-stop), (2) for each of the scenarios one-hand-right, one-hand-left, two-apart, two-touching, two-crossing, fast, enter/leave,
run `sh eval/hand_diagnostics/capture_scenario.sh <name> <out-dir> 60 <phone-serial>`, 3 repeats each, ≥ 2 min cool-down between runs, (3) note the performed pose per run (screenshots are taken automatically).
**Measurements and where they come from (all already logged):**

| quantity | source |
|---|---|
| camera capture interval | per-frame `capture_timestamp_ns` differences (`analyze_scenarios`: `capture_interval_ms(delivered frames)`); dropped frames = `camDropEst` |
| pose inference | `pose_inference_and_output_ms`, summary `pose` |
| hand refinement | `hand_inference_ms`, `hands_wall_ms`, summary `left_hand`/`right_hand` |
| result assembly + segmenter + recognizer | `session_ms(analyzer-perception)`, summary `segmenter`, `recognizer` |
| analyzer total | `analyzer_ms`, `frame_total` |
| UI delivery and rendering | `ui_hop` |
| end-to-end | `end_to_end` (valid only where the camera clock matches elapsed-realtime), and `capture_to_completed_ms` |
| effective FPS, saturation | `fpsIn`, `fpsOk`, `busy`, `render[...]` |
**Reporting rules:** per device class and per scenario, median and p95 over the 3 repeats, with the spread between repeats; never mix emulator rows into a phone table; compare with the
repo's earlier Xiaomi M2101K7AG numbers only as a labelled historical reference. Phone behaviour of the *proposals* (echo rate, support ratio) should be compared with this report's
host numbers; they are expected to agree but that is unverified.

## 6. Recommended fix (NOT implemented) — evidence, risk, gating

**Recommendation:** treat the opposite-group echo as a **proposal-stage** problem and resolve it with a **relative, multi-signal** test, evaluated first as a **shadow
counterfactual** (logged, no behaviour change), then behind a default-off flag. Candidate decision for a frame where both groups propose overlapping regions: the weaker group
is a *duplicate* only when **all** of: (a) its support is a small fraction of the stronger group's (scale-free ratio, §3), (b) its ROI overlaps the stronger group's, and (c) at least
one independent corroborator agrees (slot/handedness inconsistency when the hand is not near, or no same-side arm evidence). A hand that fails (a) alone is never dropped.
No numeric threshold is proposed here: the gap seen (ratio 0.40 → 0.87) must be re-measured on more subjects, lighting and the phone before any value is chosen.

**Why this and not the alternatives:** IoU-only is ruled out (touching ROI IoU ≥ 0.5 in 94 % of genuine frames in the emulator run, 64 % across the offline two-hand poses; echo ROI IoU can be as low as 0.44; overlap AUC 0.70–0.89). Handedness-only is ruled out
(near hands, crossing, uncalibrated). Raising the absolute 0.10 gate is not evidenced: the echo is at 0.12–0.24, real hands at ≥ 0.27, so a gate would sit inside a noise-sensitive margin and
depend on lighting/distance. Absolute support is a strong signal but the ratio is more portable.

**Expected benefit (ESTIMATE, not measured on a phone):** one fewer hand-refiner run per one-hand frame (≈ 18–24 ms p50 on the emulator, ≈ 13–17 % of that analyzer's time), cleaner
slot assignment for Recognition-v2 (which consumes both slots), and removal of the duplicate overlay.

**Risks (each must be tested before enabling):**
- **R1 unequal real pairs** (one hand near/large, the other far/small, or motion-blurred): the weaker real hand could look like an echo. Not tested.
- **R2 hand partly out of frame / at the edge:** support drops legitimately. Not tested.
- **R3 same-side arm evidence absent** (sleeves, hand from below the frame): corroborator (c) may be missing; must not alone drop a hand.
- **R4 crossing and touching overlap:** crossing already shows one hand captured twice and the other missed; a rule could drop the second group, which is arguably correct but changes sign-recognition input.
- **R5 recognition impact:** both slots feed Recognition-v2 and the segmenter; any change alters their inputs. The **236-class regression suite and an offline recognition A/B must be re-run**; no recognizer threshold may change.
- **R6 single subject.** All numbers here are from one person in one room.
**Gates before enabling:** ≥ 3 more subjects incl. different skin tone/hair/glasses/sleeves, lighting variants, the R1–R3 cases, then the phone; shadow log must show no genuine two-hand frame dropped; regression suite green; rollback = flag off.

## 7. Open items
Multiple subjects; unequal pairs and edge/partial hands; arm-less hands; the phone (all timings and the echo rate on device); why the model echoes; per-frame truth for crossing and enter/leave;
whether the app's emulator frames match this crop (parity check); effect on recognition accuracy.

## Files
Added: `eval/hand_diagnostics/{offline_probe.py,capture_pose_session.py,analyze_probe.py}`; `docs/hand_diagnostics_runs/offline_2026-11-10/{schedule.json,analysis_probe.json,feature_table.json}`
(scalars only: no frames, no coordinates); this report. Modified: `eval/hand_diagnostics/capture_scenario.sh` (device metadata, fail-safe class), `eval/hand_diagnostics/analyze_scenarios.py` (capture interval,
capture→completed), `tests/test_hand_diagnostics.py` (10 tests: 5 need numpy and skip elsewhere), `context/progress-tracker.md`. **App source, APK, thresholds, recognition: unchanged.**
Scratch (outside repo, contains faces): frames, probe output with landmark coordinates, a Python virtualenv.
