# Controlled hand-diagnostic testing — report

Date: 2026-11-10 · Branch `jepjep-claude` · **nothing committed** · app source, APK, thresholds, smoothing, suppression and recognition **unchanged**.
Follows [`BUG_HAND_DETECTION_AND_LATENCY_INVESTIGATION.md`](BUG_HAND_DETECTION_AND_LATENCY_INVESTIGATION.md).

## 0. Scope and honesty statement
- **Environment: emulator only** (`emulator-5554`, AVD `AppHear_Camera_Test`, Android 17, arm64 on a MacBook; front camera = the MacBook webcam).
  Nothing here is a physical-phone measurement. Hand-detection *behaviour* (which proposals DWPose makes) is a property of the models and is
  likely to transfer; *timings* are not (§5).
- **One subject, one session, one 60 s run per scenario, one lighting/background.** Findings are controlled-but-narrow evidence, not a
  population result.
- Scenarios were performed by the user on request; I verified them from screenshots taken during each capture (§2), not from the model's own output.
- Analysis tools are new files only (`eval/hand_diagnostics/`, `tests/test_hand_diagnostics.py`, 4 tests pass). Raw numeric logs and the full
  analysis JSON are in `docs/hand_diagnostics_runs/emulator_2026-11-10/`. Screenshots contain the user's face and were **not** copied into the repo.

## 1. Method
For each scenario: force-stop the app (resets the analyzer, because the per-frame `AppHearV3` log is capped at 240 frames per analyzer start and
the 30 s counters are cumulative), `logcat -c`, launch to the recognition screen, record tags `AppHearDetect`, `AppHearV3`, `AppHearPhone`,
`AppHearRecognition` for 60 s into a separate file, screenshot every ~11 s. Per-frame analysis drops the first 3 frames (model warm-up).
Per-frame data: 240 frames per scenario (237 analysed). The per-frame record has presence, refiner handedness, ROI IoU (DWPose boxes, before the
refiner), skeleton IoU (after the refiner), stage times. It does **not** have per-frame DWPose support or landmark coordinates; support exists only
as a mean over "same" frames in the 30 s line (limitation L1).

## 2. Scenario verification (screenshots, t≈23 s and t≈47 s of each run)
| # | Requested | Observed in screenshots | Verified |
|---|---|---|---|
| 1 | exactly one hand | one hand (right, fingers up, palm to camera, arm from bottom-right); no second hand anywhere in frame; **two skeletons drawn on it** (magenta `RH 0.98`, yellow `LH 0.98`) with offset boxes | yes |
| 2 | two hands, clear gap | two hands, one at face level and one lower, vertically separated with a gap, not touching; **each skeleton on its own hand** (`RH 1.00`/`0.99`, `LH 1.00`) | yes (arranged vertically rather than left/right) |
| 3 | two hands touching | both palms pressed together in front of the face, both forearms visible; two skeletons, one per hand, adjacent (`LH 0.87`/`0.73`, `RH 0.92`/`0.88`); app showed `RECOGNIZED BED2` | yes (palms-together only; crossing was not run) |

## 3. Raw counters

### 3a. 30-second summaries (cumulative, final line at t≈60 s; includes ~1–3 s of startup)
| | S1 one hand | S2 two apart | S3 two touching |
|---|---:|---:|---:|
| frames n | 380 | 393 | 397 |
| none / L only / R only | 1 / 0 / 0 | 0 / 0 / 2 | 7 / 11 / 11 |
| **both observed** | **380** | 391 | 368 |
| skeleton overlap: same (IoU ≥ 0.5) / part / sep | **380** / 0 / 0 | 0 / 55 / 336 | 8 / 11 / 349 |
| `same.roi` (ROIs already coincided / differed) | **380 / 0** | n/a | 8 / 0 |
| `same.pres` L/R | 0.98 / 0.98 | n/a | 0.66 / 0.70 |
| `same.hand` L/R (refiner handedness) | 0.34 / 0.20 | n/a | 0.50 / 0.57 |
| `same.sup` L/R (DWPose group support) | **0.13 / 0.50** | n/a | 0.45 / 0.54 |
| `render` n / skipped / stale / redraw | 380 / 0 / 0 / 0 | 391 / 0 / 0 / 1 | 395 / 1 / 0 / 1 |
| analyzer busy / processed fps / camera drops (est.) | 99.1 % / 6.3 / 506 | 98.8 % / 6.9 / 474 | 98.8 % / 7.0 / 494 |
| crashes, faults | 0, 0 | 0, 0 | 0, 0 |
| committed words | 0 | 0 | 1 (`BED2`, p=0.994, handSpan 1.00) |

### 3b. Per-frame (237 frames each)
| | S1 one hand | S2 two apart | S3 two touching |
|---|---:|---:|---:|
| hands observed 0 / 1 / 2 | 0 / 0 / **237** | 0 / 2 / 235 | 6 / 19 / 212 |
| skeleton IoU (both observed): median / max | **0.709** / 0.991 (min 0.601) | 0 / 0.224 | 0 / 0.914 |
| skeleton IoU bins <0.1 / 0.1–0.5 / ≥0.5 | 0 / 0 / **237** | 183 / 52 / 0 | 194 / 10 / 8 |
| ROI IoU (DWPose boxes): median / range | **0.784** / 0.623–0.974 | 0.026 / 0–0.576 | **0.622** / 0.417–0.902 |
| ROI IoU ≥ 0.5 | **237 (100 %)** | 0 | **199 (94 %)** |
| ROI vs skeleton: ROI≥.5&skel≥.5 / **ROI<.5&skel≥.5 (M2 signature)** / ROI≥.5&skel<.5 / both <.5 | 237 / **0** / 0 / 0 | 0 / **0** / 0 / 235 | 8 / **0** / 191 / 13 |
| Spearman ρ(ROI IoU, skeleton IoU) | 0.74 | 0.79 | 0.12 |
| mean presence L / R | 0.976 / 0.980 | 0.989 / 0.978 | 0.833 / 0.850 |
| refiner handedness mean L / R (median) | 0.28 (0.20) / 0.20 (0.10) | 0.02 / 0.92 | 0.12 (0.07) / 0.81 (0.85) |
| frames with handedness on opposite sides of 0.5 | 51 (22 %) | 224 (95 %) | 193 (91 %) |
| frames with both handedness < 0.5 | 172 (73 %) | 11 (5 %) | 13 (6 %) |

## 4. Findings

### F1. M1 vs M2 — duplicates come from DWPose proposing the same hand twice (M1); M2 was not observed
- In the one-hand run **every** both-observed frame (237/237; 380/380 in the 30 s counters) already had overlapping DWPose ROIs *before* the refiner
  (IoU 0.62–0.97, median 0.78), and the refined skeletons were **not closer** than the ROIs (median 0.71 vs 0.78). The refiner followed each
  proposal rather than snapping different crops onto one hand.
- The M2 signature (ROIs apart, skeletons coincident) occurred in **0 frames in all three scenarios** (0 / 0 / 0).
- The refiner is not a filter: it returned presence ≈ 0.98 for both crops of one hand. It cannot reject the phantom proposal by presence.
- **Status: supported by controlled evidence, one subject/one pose, emulator.** Not yet established beyond that.

### F2. DWPose support and ROI overlap vs duplicates
- ROI overlap tracks skeleton overlap when hands are separate or duplicated (ρ = 0.74, 0.79), **but not when hands touch** (ρ = 0.12).
- Support: in the duplicate run the mean support of the left group was **0.13 vs 0.50** for the right group, i.e. the phantom proposal sits just above
  the 0.10 gate that creates an ROI, while in the 8 coincident frames of S3 the two groups were balanced (0.45 / 0.54). This is suggestive only:
  **support is available only as a mean over "same" frames, so a per-frame correlation cannot be computed (L1).**

### F3. Refiner handedness vs the physical hand
- Two hands (S2, S3): the refiner output separates the two crops almost always, in the direction consistent with the DWPose slot (left slot low,
  right slot high): 95 % and 90 % of frames; means 0.02/0.92 and 0.12/0.81. The convention "value = probability of right hand" fits both runs.
- One hand (S1): both crops report the **same side** (73 % of frames both < 0.5; only 22 % opposite). For a **right** hand the right-slot crop gave a
  median of only 0.10, which contradicts the convention that fits S2/S3. So the refiner's handedness did **not** agree with the expected physical hand in
  the one run where I know the hand, and I cannot explain why from these data (candidates: palm-out, very large and edge-cropped hand; the convention
  itself being inferred). A left-hand run would calibrate this (§7).
- Observation, not a rule: agreement of the two handedness values coincided with duplicates in S1, disagreement with real pairs in S2/S3, but S3's 8
  coincident frames were mixed (4 opposite-side, 4 not) and S1 had 22 % opposite-side frames, so handedness alone does not separate the cases.

### F4. Legitimate overlap when hands touch
- Touching hands **do** make the DWPose ROIs overlap: IoU ≥ 0.5 in **94 %** of S3 frames (median 0.62), a range that overlaps the duplicate case (S1 min
  0.62). **A rule based on ROI overlap would remove most genuine touching-hand frames and cannot tell S3 from S1.** The data therefore rule it out.
- The refined skeletons stayed separate in 96 % of S3 frames (194 / 212 < 0.1 IoU); IoU ≥ 0.5 occurred in 8 frames (3.8 %), all in a transient
  (frames 84–110) where the hands merged and 23 of the 25 sub-two-hand frames also fall; presence there was low (~0.5–0.6) and handedness ≈ 0.5, unlike
  the steady 0.98 of S1.
- A single palms-together pose from one subject; crossing and other touching poses were not tested.

### F5. Interference with recognition
No wrong word was committed in S1 (0 commits) and S2 (0), and one in S3 (`BED2`, p 0.994). I did not assess whether `BED2` is the signed word. These runs
do not demonstrate interference; they also cannot rule it out, since both hands of S1 feed the recognizer's two slots while only one is real.

### F6. Latency — where the time goes (emulator, per-frame medians, S1 / S2 / S3)
| stage | p50 ms | share of analyzer p50 |
|---|---|---|
| capture → analyzer start (`frame_age`) | 45.6 / 39.7 / 45.6 (p95 92 / 83 / 86) | outside analyzer |
| preprocess + pose decode + crop | ≈ 2.5 | ≈ 2 % |
| DWPose inference | 36.6 / 31.2 / 32.4 | 25.7 / 22.5 / 23.3 % |
| hand refinement (both, wall) | 47.4 / 45.9 / 46.7 | 33.2 / 33.1 / 33.7 % |
| **session (S2 segmenter + recognizer + result assembly)** | **57.7 / 63.9 / 59.4** | **40.4 / 46.0 / 42.8 %** |
| analyzer total | 142.7 / 138.8 / 138.6 (p95 213 / 207 / 188) | 100 % |
| delivery → draw (`ui_hop`) | 13.1 / 11.6 / 12.1 (p95 33 / 26 / 31) | outside analyzer |
| **capture → draw (`end_to_end`)** | **200.3 / 201.1 / 190.5 (p95 295 / 258 / 266)** | |

- `end_to_end` ≈ `frame_age` + analyzer + `ui_hop` (43 + 142 + 13 = 198 vs 200 for S1): no hidden term.
- **Rendering is not the cause** (`ui_hop` ≈ 6 % of end-to-end), **and there is no stale or out-of-order result** (`stale=0`, `skipped` 0–1).
  The analyzer is saturated (busy 98.8–99.1 %) and processes ≈ 6.3–7.0 fps while the camera nominally delivers 15 fps (≈ half the frames dropped by
  latest-frame-wins). So the overlay is ≈ 200 ms behind the live preview on average and updates only every ≈ 145 ms.
- No smoothing exists on the path (code, previous report), so the lag is processing and queueing, not filtering.
- **Platform caveat:** on this emulator the largest single stage is the session (~40–46 %), then hands (~33 %), then pose (~25 %). The repo's earlier Xiaomi
  measurements (pose ≈ 87 ms, hands ≈ 110 ms) have a different composition, so this ranking must **not** be assumed on the phone.
- Link between the bugs (ESTIMATE, not measured): in S1 both refiners run on one hand; one refiner run is ≈ 18–24 ms p50 here (≈ 13–17 % of analyzer
  p50). Removing a phantom hand would save about one run per frame. No clean one-hand baseline exists to measure it.

## 5. What this means for fix design (no fix implemented)
1. Any suppression must **not** be ROI-overlap based (F4). Skeleton overlap separates S1 from S2/S3 in these runs (S1 min 0.60 vs S3 96 % < 0.1) but
   would misfire on the S3 transient and needs more subjects, poses and crossing/touching variants before a threshold is justified.
2. The cleaner place to intervene is likely the proposal stage: the phantom left group is a weak, asymmetric DWPose proposal (support 0.13 vs 0.50),
   created by a very low support gate (0.10) — but that needs per-frame support data to confirm.
3. Handedness can corroborate but not decide (F3).
4. The latency work is independent of the duplicate issue: biggest levers on this emulator are the session stage and hands; on the phone it must be
   re-measured first.

## 6. Remaining uncertainties and limitations
- **L1** No per-frame DWPose support or landmark coordinates in the log: support/duplicate correlation (a requested analysis) is only an aggregate.
  Closing it needs one source change (log the two support means per frame), which this task prohibited.
- **L2** Emulator, not phone; webcam path, CPU speed and thermal behaviour differ. No latency claim transfers.
- **L3** One subject, one background, one run per scenario, one hand pose per scenario; no repeats, no variance across runs.
- **L4** Slot-correct handedness for the S1 hand is unexplained (F3). Convention inferred from S2/S3.
- **L5** Crossing, fast and slow movement, continuous signing and hand disappear/reappear (brief scenarios 4–8) were not run in this round.
- **L6** The scenario was verified from 2 screenshots per run, not frame by frame; hands entered/left briefly in S3 (frames 84–110).
- **L7** Skeleton-IoU bins are descriptive labels, not a validated detector.

## 7. Suggested next controlled runs (each ~90 s)
(a) one **left** hand (calibrates handedness, F3); (b) one hand in a different pose/distance (does the phantom persist, does support asymmetry hold);
(c) hands crossing; (d) a second subject; (e) repeat S1 three times for variance. And on the phone: the same three runs plus the
latency counters, since only the phone can validate any latency conclusion.

## Files
Added: `eval/hand_diagnostics/{__init__.py,capture_scenario.sh,analyze_scenarios.py}`, `tests/test_hand_diagnostics.py`,
`docs/hand_diagnostics_runs/emulator_2026-11-10/*` (3 numeric logs, 3 meta, 3 empty crash logs, `analysis.json`), this report.
Modified: `context/progress-tracker.md`. App source, APK, emulator app data: unchanged (the AVD config was edited earlier at the user's request).
