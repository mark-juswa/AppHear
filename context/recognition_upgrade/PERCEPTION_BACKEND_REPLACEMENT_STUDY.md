# AppHear Perception Backend Replacement Study

**Status:** study complete; proof-of-concept not started  
**Date:** 2026-08-20  
**Scope:** read-only repository audit, public model/runtime research, feasibility analysis, and experiment design  
**Production effect:** none

## 1. Executive conclusion

AppHear should move beyond incremental MediaPipe recovery. The project has already shown that independent-clock scheduling can make fresh hand results arrive substantially faster, while threshold, temporal-mode, ROI, optical-flow, identity, and landmark carry-forward branches do not repair the underlying direct-perception failure safely. The problem is now the visual backend itself.

The best next proof-of-concept is an **independent full-frame mobile hand detector followed by a lightweight 3D hand regressor**, specifically:

> **RTMDet-nano hand detector (320x320) -> per-hand MobRecon DenseStack crop regressor (128x128) -> canonical anatomical Left/Right 21-joint adapter.**

This is recommended as an **offline, no-training PoC**, not as an Android replacement. It is materially different from AppHear's rejected custom MobileNet box detector: it combines an independently pretrained detector with a dedicated 3D hand-pose/mesh model, consumes current RGB evidence on every direct observation, and can in principle supply 21 `x/y/z` joints. MobRecon reports 5M parameters, 123M multiply-adds, and 67 FPS on Apple A14 CPU for DenseStack, but those are paper claims for a hand crop, not AppHear Android measurements and not the detector-plus-regressor pipeline.

The recommendation is conditional on four unknowns: (1) RTMDet's actual recall/precision on AppHear contact and motion, (2) MobRecon's crop robustness during hand-hand/body contact, (3) export/operator support and sustained Android latency, and (4) a valid mapping from MobRecon camera/mesh coordinates to AppHear's MediaPipe-relative `z` distribution. No result in this study invalidates the decision to leave heuristic MediaPipe recovery behind. The new evidence strengthens it.

### Ranked decision

1. **RTMDet-nano + MobRecon DenseStack:** best next PoC; direct independent evidence, mobile-size 3D regressor, closest path to the current 21x`x/y/z` contract.
2. **Person detector + RTMW3D-m whole-body context model:** backup when body/contact context matters more than cost; potentially supplies body and two hands jointly, but is much heavier and Android deployment is not established.
3. **AppHear-domain fine-tuned detector + 3D regressor (license-clean OpenMMLab/MobRecon base):** best longer-term route if off-the-shelf weights reveal a correctable domain gap; much higher annotation and training cost than #1.

RTMPose-hand is retained as a useful **2D diagnostic control**, not the primary recommendation, because its 21 points lack the depth coordinate required by the current S4 feature distribution.

## 2. The actual failure being solved

The target is not to infer that a hand probably remained present after MediaPipe stopped observing it. It is to directly observe hands and their landmarks more reliably from the current image during:

- fast signing motion and blur;
- two-hand interaction, hand-hand contact, and crossing;
- hand-body/torso/face overlap;
- partial visibility and edge clipping;
- true entry and exit;
- difficult lighting, skin/background combinations, camera processing, and device quality.

The desired boundary remains:

```text
CameraX
  -> A1-style latest-frame / independent-clock scheduling
  -> new direct hand-perception backend
  -> canonical anatomical Left 21 x/y/z + Right 21 x/y/z
  -> existing S4 schema [96,258]
  -> existing S5/S6/S7 initially
```

A backend may use confidence, temporal state, or tracking internally, but a missing-hand output must arise from current visual evidence or a learned tracker with explicit occlusion/reset semantics. Old landmarks alone are not new evidence.

## 3. Frozen experiments: do not repeat

| Closed branch | Verified result | Consequence |
|---|---|---|
| MediaPipe confidence sweeps | Lower thresholds traded recall for false hands; no operating point passed. | Do not tune confidence again. |
| IMAGE -> VIDEO temporal mode | Availability improved only modestly/inconsistently; two-hand behavior regressed in part of the test. | Do not reopen MediaPipe modes. |
| Pose cadence sweeps | Explored before A1; did not solve hand observation loss. | Preserve pose, and treat cadence only as scheduling. |
| A1 independent clocks | Fresh hand rate `5.300 -> 7.077/s`; p95 publication gap `258.3 -> 169.3 ms`; signed landmark coverage stayed flat. | Keep as the scheduling foundation; it is not the perception solution. |
| Static ROI hold | Could not safely maintain direct hand availability. | Closed. |
| Pose-guided ROI recovery | Best direct-plus-route availability `81.58%`, complete two-hand `67.57%`, but no-visible false-positive frames `50%`; failed gates. | Closed. |
| Optical-flow ROI tracking | Availability `80.53%`, complete two-hand `64.86%`, anatomical accuracy `73.75%`, no-visible false-positive frames `75%`. | Closed. |
| HaGRID detector smoke | At confidence 0.5: `4/6` positives and `4/20` negative false positives; licensing/data fit also unresolved. | Closed. |
| Custom MobileNetV2 detector | I320 direct availability `67.26%`, complete two-hand `41.03%`; reaching >=85% recall caused `78.57%` no-hand FPR. | Do not repeat a small-box-model threshold sweep. |
| RGB fallback/fusion | Previous RGB branches did not establish a reliable perception fallback. | A new fallback must produce independent hand evidence. |
| S5 gap tolerance | Recognition-layer tolerance did not restore missing visual observations. | Closed. |
| A2-1 / A2-1R identity tracker | Baseline detector identity was already mostly correct; temporal tracker introduced many errors. | Do not make identity carry-forward the main repair. |
| A2-2R one-observation hold and velocity extrapolation | Coverage rose, but both produced false recovery during absence/rest/leaving/stale gaps and one additional wrong `SISTER` commit. | All heuristic landmark carry-forward/extrapolation is closed. |

Canonical local evidence: [A1 Stage 1](A1_STAGE1_NO_SIGN_RESULT.md), [A1 signing sentinel](A1_SIGNING_SENTINEL_RESULT.md), [A2 identity](A2_1_IDENTITY_RESULT.md), [A2-1R](A2_1R_IDENTITY_RESULT.md), [A2-2R](A2_2R_RECOVERY_RESULT.md), [E2c](E2C_TEMPORAL_TRACKING_RESULT.md), [E2d](E2D_DETECTOR_OPERATING_POINT_RESULT.md), [HaGRID](C0A_HAGRID_SMOKE_RESULT.md), [custom detector](C0B_STAGE2_DEVELOPMENT_RESULT.md), and [post-I320 decision](C0B_POST_I320_DATA_DECISION.md).

## 4. Current MediaPipe and A1 benchmark baseline

These datasets answer different questions and must not be pooled into one number.

### 4.1 Direct-perception quality

| Metric | Corrected all-hand gold | A2 reviewed temporal package | Interpretation |
|---|---:|---:|---|
| Frames / scope | 150 frames, 41 signers, 184 visible hand instances | 551 selected observations, 21 phone sequences | Static broad-signer audit vs chronological phone stress evidence. |
| Visible-hand instance recall | `122/184 = 66.30%` (Wilson 95% CI `59.20-72.74%`) | `69.97%` frozen C0 | Direct MediaPipe observations only. |
| Any-hand coverage | `91/117 = 77.78%` | `77.88%` | Frames with at least one visible hand found. |
| Complete two-hand coverage | `31/67 = 46.27%` | `51.55%` | The most important current failure. |
| Motion-blur recall | `58.33%` | not independently estimated | Corrected gold subgroup. |
| Occluded recall | `52.00%` | not independently estimated | Corrected gold subgroup. |
| Edge-clipped recall | `25.81%` | not independently estimated | Corrected gold subgroup. |
| Partial-hand recall | `16.67%` | not independently estimated | Corrected gold subgroup. |
| False-presence behavior | `0/33` selected no-hand frames and `0/122` unmatched predictions | three raw-baseline false-presence frames in the broader A2 audit | The bounded static sample is encouraging but too small for a production precision claim. |

Source: [E2E all-hand gold result](E2E_ALL_HAND_GOLD_RESULT.md) and [A2-2R result](A2_2R_RECOVERY_RESULT.md).

### 4.2 Temporal dropout audit

The reviewed A2 annotations contain **93 visible-but-undetected hand instances in 49 causal runs**. A read-only run-length reconstruction, broken at direct re-detection, invisibility, attempt boundary, or anatomical side, gives:

| Missing observations in a run | Runs | Share of runs |
|---:|---:|---:|
| 1 | 30 | 61.2% |
| 2 | 8 | 16.3% |
| 3 | 4 | 8.2% |
| 4 | 3 | 6.1% |
| 5 | 1 | 2.0% |
| 6 | 3 | 6.1% |
| **Multi-observation (>=3)** | **11** | **22.4%** |

This is `49 / 551 = 8.89` dropout runs per 100 selected reviewed observations, not a full camera-stream population rate. Before human review, the same selected phone sequences showed pooled any-direct inter-observation gaps of `267.04 ms` median and `386.79 ms` p95. Those gap values describe signing/stress observations and are distinct from A1's no-sign scheduler publication gap.

### 4.3 Runtime scheduling and useful observations

| Metric | Baseline | A1 independent clocks | Change / meaning |
|---|---:|---:|---|
| Useful fresh hand publications | `5.300/s` | `7.077/s` | `+33.5%` |
| S4 observations | `5.304/s` | `7.063/s` | `+33.1%` |
| p95 publication gap | `258.3 ms` | `169.3 ms` | `-34.5%` |
| p95 hand-end -> S4 | `63.3 ms` | `3.9 ms` | Scheduling tail removed. |
| Hand inference p95 across the two runs | `166.9-241.4 ms` | `166.3-167.7 ms` | A1 did not replace or intrinsically speed up the hand model; its validated gain is scheduling/overlap. |
| Synchronizer yield | approximately `1.001` | `0.998` | Three A1 `POSE_TOO_OLD` rejects. |
| p95 pose age | `296.3 ms` | `505.1 ms` | Below frozen `582 ms` ceiling. |
| Peak PSS | `453,208 KB` | `461,531 KB` | `+1.84%`. |
| Thermal half-run decay | `1.16%` | `0.79%` | No measured A1 deterioration in this run. |
| Crash/order/future-pose violations | none | none | Full trace coverage. |

Conditions: one Xiaomi reference phone, order-balanced no-sign benchmark, 20-second warm-up plus approximately 100 measured seconds per mode. This is a valid Xiaomi runtime result, not a cross-device result.

The 24-attempt signing sentinel found essentially flat direct landmark coverage: mean hand coverage `57.1%` baseline versus `57.9%` A1, and two-hand coverage `20.6%` versus `20.0%`. A1 is therefore useful scheduling infrastructure, but it did not repair perception.

### 4.4 Failed post-processing bar

A2-2R raised visible recall `69.97 -> 75.85%`, any-hand coverage `77.88 -> 81.86%`, and complete two-hand coverage `51.55 -> 61.86%`. Each candidate nevertheless created 8 recoveries during true absence, 3 during rest, 5 during leaving, and 19 stale long-gap recoveries; both failed velocity continuity and added a wrong recognition commit. A replacement must beat **direct C0**, not claim A2's filled outputs as ground truth.

## 5. Cross-device deployment requirements

1. **Correctness on CPU is mandatory.** GPU, NNAPI, QNN, or vendor NPUs are optional acceleration paths.
2. **One canonical output contract.** Every device tier emits anatomical Left/Right, 21 points, validity/presence, timestamp, and the same normalized coordinate semantics.
3. **A1-style scheduling.** Latest-frame backpressure and independent hand/pose clocks remain the conceptual shell.
4. **No vendor-specific camera assumption.** Orientation, mirroring, color conversion, crop transforms, and coordinate inversion are explicit and tested.
5. **Sustained pipeline measurement.** Standalone model latency is insufficient; measure camera arrival to canonical output, PSS, heat, drop rate, and stability.
6. **Per-backend calibration without semantic drift.** CPU/GPU/NNAPI may use different numerical kernels, but output accuracy and acceptance policy must be checked against a common conformance set.
7. **Fallback is capability-based.** Unsupported or partitioned delegates fall back to CPU/XNNPACK; recognition must not silently change meaning.
8. **Tiering, if needed, changes capacity—not the schema.** A light and strong model require per-tier perception validation and a recognition distribution-shift check before production.

## 6. Device-tier performance envelopes

AppHear's shortest known signs are approximately `170-200 ms`. Three direct samples across a 200 ms sign require 15 useful observations/s; three across 170 ms require about 17.6/s. Therefore **15/s is a hard degraded floor, 18/s is the minimum-tier target**, and 20-30/s is preferred. This is derived from temporal coverage, not camera FPS.

| Requirement | Minimum supported tier | Mainstream tier | High-end tier |
|---|---:|---:|---:|
| Sustained useful direct hand observations/s | floor `15`, target `18` | `>=24` | `>=30` |
| p95 backend latency | `<=66 ms` | `<=42 ms` | `<=33 ms` |
| Direct visible-hand recall | `>=85%` | `>=90%` | `>=92%` |
| Complete two-hand recall | `>=70%` | `>=78%` | `>=82%` |
| No-hand false-presence rate | `<=2%` | `<=2%` | `<=2%` |
| Combined model files | target `<=30 MB` | `<=50 MB` | `<=80 MB` |
| Incremental peak PSS over A1 shell | `<=80 MB` | `<=120 MB` | `<=160 MB` |
| Total peak PSS safety ceiling | `<=525 MB` | `<=600 MB` | `<=700 MB` |
| 10-minute useful-throughput decay | `<=10%` | `<=7%` | `<=5%` |
| Crash / corrupted output / timestamp-order errors | zero | zero | zero |

The quality targets apply to the hard perception set, not a clean public benchmark. A device that cannot sustain 15 useful direct observations/s cannot be called fully supported for the existing `[96,258]` recognizer; it should use an explicit degraded/unsupported policy rather than hidden frame loss.

## 7. Candidate architecture families

### Family A — alternative mobile hand-landmark model

No verified off-the-shelf package was found that simultaneously supplies full-frame multi-hand detection, presence, anatomical handedness, and MediaPipe-compatible 21-point `x/y/z` on broad Android hardware.

- **RTMPose-m Hand5** is a strong mobile-deployable 2D landmarker, normally paired with RTMDet/SSDLite. It outputs 21 2D points and scores, not AppHear-compatible depth.
- **MobRecon DenseStack** predicts 2D pose plus a 3D mesh/joints from a hand crop. It is mobile-sized but does not find hands or assign handedness by itself.
- **HaMeR** provides strong 3D hand mesh recovery but requires a large ViT-based CUDA-oriented stack and MANO assets; it is not a credible low-end Android candidate.

Conclusion: Family A alone does not meet the full boundary. MobRecon is valuable as the landmark stage of Family B.

### Family B — detector + landmark/3D regressor

This is the best fit. A detector observes up to two hands in the full image; a separate regressor resolves 21 joints per crop. It can improve contact and body overlap if the detector was trained on interacting/occluded hands and the crop regressor can use partial visual evidence.

Advantages:

- detector and landmark failures are independently measurable;
- detector can recover both hands without relying on old boxes;
- regressor can be upgraded or fine-tuned without changing the canonical adapter;
- compute scales as one detector plus zero, one, or two crop regressions.

Risks:

- detector failure remains fatal for that frame;
- two crop passes can dominate contact-heavy signing;
- crop NMS can merge touching hands;
- handedness requires anatomy/body geometry or a trained side head;
- 3D coordinate conventions require explicit calibration.

Recommended concrete stack: RTMDet-nano hand 320 + MobRecon DenseStack 128. RTMDet + RTMPose-m Hand5 is the 2D diagnostic control.

### Family C — detector refresh + learned landmark tracker

A learned point tracker such as Online TAPIR is materially different from rejected optical-flow box movement: it tracks visual point identities with learned matching/refinement and emits occlusion estimates. A detector could initialize 21 points, the tracker could update them between detector refreshes, and direct detection could reset state.

This is not the next PoC. The official Online TAPIR repository reports about 17 FPS at 480x480 on a Quadro RTX 4000 mobile GPU, provides no Android benchmark, is not hand-specific, and cannot independently decide anatomical handedness or hand presence. Tracking an occluded point is also not proof that a hand is still present. It remains a research candidate only after a direct backend works.

### Family D — hybrid/fallback perception

MediaPipe primary + an independent RTMDet/MobRecon secondary is architecturally valid because the secondary examines the current RGB frame. It could answer whether a hand is visually present when MediaPipe misses it. It is not recommended as the first experiment because:

- invoking only on MediaPipe absence misses wrong-but-confident landmarks;
- simultaneous fallback can create latency spikes and thermal instability;
- reconciling two coordinate/identity distributions adds a second calibration problem;
- a weak secondary can recreate the false-presence failures seen in ROI recovery.

First evaluate the secondary standalone against the same images. A hybrid policy becomes eligible only if the secondary has demonstrably complementary true positives and bounded independent false positives.

## 8. Concrete current models and libraries researched

All latency/accuracy values in this table are vendor/paper claims unless explicitly labeled AppHear-measured.

| Model/library | Architecture / input / output | Public evidence | Android/mobile path | License / weights | Assessment |
|---|---|---|---|---|---|
| [rtmlib hand solution](https://github.com/Tau-J/rtmlib/blob/main/rtmlib/tools/solution/hand.py) | RTMDet-nano `320x320` + RTMPose-m Hand5 `256x256`; boxes, 21 2D points, point scores | rtmlib reports the detector as hand AP `76.0` and pose model AUC `83.9`; AppHear unmeasured | Pre-exported ONNX; ONNX Runtime CPU is immediate; RTMPose supports ncnn via MMDeploy | rtmlib/MMPose Apache-2.0; pretrained weights available; dataset/weight terms still require release review | Best detector and 2D control; missing `z`. |
| [MobRecon](https://arxiv.org/abs/2112.02753) / [code](https://github.com/SeanChenxy/HandMesh) | DenseStack/GhostStack, `128x128` crop; 2D pose, 778-vertex 3D mesh, 21 joints | 5M params, 123M mult-adds; paper reports DenseStack 67 FPS and GhostStack 83 FPS on Apple A14 CPU; FreiHAND PA-MPJPE 6.9 mm for DenseStack | PyTorch reference and weights; ONNX/ExecuTorch/ncnn export and Android operators are **unverified** | MIT code; weights available; MANO asset terms need review | Best compact 3D regressor candidate; requires detector. |
| [RTMW / RTMW3D](https://github.com/open-mmlab/mmpose) | Top-down person crop; 133 whole-body points including 21 per hand; 2D and separate 3D project; `256x192` or `384x288` | RTMW-m 2D: 4.3 GFLOPs, hand AP `0.491`, hand AR `0.604`; larger models improve hand AP to about `0.664` | RTMPose export paths exist; RTMW3D Android/ncnn support and full detector+model latency are **unknown** | MMPose Apache-2.0; checkpoints available; training-dataset terms need review | Body context is attractive; cost and hand resolution are concerns. |
| [Ultralytics hand pose](https://docs.ultralytics.com/datasets/pose) | One-stage hand box + 21 2D points; model/input depend on chosen YOLO size | Public dataset has 26,768 images, but its keypoints were generated by MediaPipe, so it is not independent truth | ONNX/TFLite/CoreML export paths advertised | AGPL-3.0 or paid Enterprise per vendor; pretrained/fine-tuned models covered by vendor terms | Useful research reference, not recommended for AppHear production without licensing and independent labels. |
| [Online TAPIR / BootsTAPIR](https://github.com/google-deepmind/tapnet) | Learned arbitrary-point tracker; ResNet18 family; tracks positions and occlusion | Official repo: about 17 FPS at 480x480 on Quadro RTX 4000; Online TAPIR DAVIS AJ 56.2 | PyTorch/JAX; no credible maintained Android deployment found | Apache-2.0 software and listed checkpoints | Materially new tracker, but too costly/uncertain and not hand-specific. |
| [HaMeR](https://github.com/geopavlakos/hamer) | ViT hand mesh recovery from detected hand crops; 3D mesh/joints | Strong public 3D/occlusion evaluation; no mobile latency claim located | CUDA/PyTorch demo stack; no credible low-end Android path | MIT code; MANO registration/assets and component terms apply | Desktop research ceiling, not a mobile shortlist candidate. |
| [ONNX Runtime Mobile](https://onnxruntime.ai/docs/tutorials/mobile/) | Android Java/C++; CPU, XNNPACK, NNAPI; custom operator-reduced AAR | Official example: AAR `24.4 -> 7.53 MB`, ARM64 library `16.28 -> 3.96 MB` for a custom ResNet50 runtime | Mature Android path; NNAPI support is device/model dependent and partitioning can degrade performance | MIT | Preferred PoC/runtime baseline because CPU correctness is portable. |
| [ncnn](https://github.com/Tencent/ncnn) | Mobile C++ inference; ARM CPU, FP16/INT8, Vulkan | No candidate-specific AppHear measurement | Strong Android CPU/Vulkan path; RTMPose MMDeploy configs exist | BSD-3-Clause | Strong alternative if ORT is too large/slow. |
| [ExecuTorch Android](https://docs.pytorch.org/executorch/stable/android-backends.html) | AAR; XNNPACK CPU, Vulkan GPU, plus vendor backends | No candidate-specific AppHear measurement | Broad current backend strategy; export maturity must be proven per model | BSD-style | Good MobRecon fallback if ONNX export fails; more integration risk than existing ONNX weights. |

### Runtime decision

Use ONNX Runtime CPU/XNNPACK first because it is the most portable common denominator and RTMDet/RTMPose ONNX artifacts already exist. Try NNAPI only after the model usability checker and per-device correctness check; unsupported operator partitioning may be slower than CPU. ncnn Vulkan is a second acceleration path. ExecuTorch is relevant mainly if MobRecon exports cleanly from PyTorch but not ONNX. No Qualcomm-, Mali-, Adreno-, or OEM-specific delegate is allowed to define basic correctness.

## 9. Contract compatibility and migration cost

| Candidate | 21 x/y | Relative/camera z | Presence | Handedness | S4 migration cost |
|---|---|---|---|---|---|
| RTMDet + MobRecon | yes | 3D joints available, but coordinate semantics differ | detector score | not built in | **Medium:** adapter and distribution-parity study; likely no S4 shape change. |
| RTMDet + RTMPose Hand5 | yes | no | detector score | not built in | **High:** cannot honestly fill current z; zero/synthetic z would create train/serve shift. |
| RTMW3D | yes | yes, semantics require calibration | person/point scores | anatomical slots from whole-body topology | **Medium:** adapter plus crop/person detector; no intended shape change. |
| One-stage YOLO hand pose | yes | normally no | box/objectness | usually no | **High:** missing z and licensing; retraining likely. |
| Learned point tracker | tracked x/y | no independent z | occlusion probability is not hand presence | no | **Very high:** cannot be a standalone canonical backend. |

MobRecon's camera-space or root-relative depth must not be relabeled as MediaPipe `z` without an empirical transform. Before any S4 integration, compare coordinate ranges, handedness mirroring, wrist-relative scale, bone lengths, and downstream feature distributions. If a valid adapter cannot be demonstrated, the cost becomes a feature-schema/model migration and #1 cannot advance under the current contract.

## 10. Dataset and training reality

### 10.1 Current AppHear assets

| Asset | What exists | What it can support | What it cannot support |
|---|---|---|---|
| ASL Citizen | 83,399 clips: train 40,154/35 signers, validation 10,304/6, test 32,941/11; signer-disjoint videos | Broad signing RGB diversity and independent video sampling | Existing MediaPipe landmarks are not replacement ground truth. |
| Stage-E feature archives | MediaPipe pose/hand sequences for all splits | Baseline comparison, hard-frame mining, recognition replay | Training a backend intended to outperform MediaPipe without human correction. |
| Corrected E2E gold | 150 frames, 41 signers, 184 human hand boxes/presence labels | Frozen direct detection and complete-two-hand benchmark | Dense 21-point or 3D landmark accuracy. |
| C0-B0 detector data | 400 boxed frames; 312 train/88 dev; 483 visible instances; 36 source-signer groups; condition labels | Box detector diagnostics and hard-condition inventory | Sufficient negatives, production detector training, or landmark truth. |
| A2 review | 551 temporal frames/21 sequences with visible anatomical side, detector association, recoverability, contact/crossing/leaving/rest labels | Temporal dropout and identity evaluation | Human 21-point ground truth. |
| Recorder pipeline | Video-primary capture with device/session metadata path | New cross-device, lighting, signer, and motion collection | Automatic trustworthy hand annotations. |
| Fresh negatives | 560 fresh negative videos from one signer; historical negatives have protected-overlap restrictions | No-hand/ordinary-hand mining after split governance | Cross-signer/device precision claims by themselves. |

No genuine human 21-landmark image ground-truth set was found in the repository. Human boxes and anatomical identity exist in bounded sets. Existing dense 21-point arrays are MediaPipe outputs and may be used as weak labels or initialization only, never as the sole gold labels for a replacement.

### 10.2 Three training routes

**Route 1 — off-the-shelf replacement (recommended first).** Run frozen RTMDet/MobRecon and controls without training. Human work is limited to completing the hard benchmark: approximately 200-300 additional hard frames, no-hand negatives, and a smaller human 2D landmark subset. This route can fail quickly and cheaply.

**Route 2 — fine-tune an existing stack.** Justified only if the off-the-shelf model has good geometry but a correctable AppHear-domain recall gap. Planning estimate:

- 5,000-10,000 domain frames with human hand boxes/presence;
- 1,000-2,000 true no-hand/idle/transition hard negatives;
- 2,000-4,000 frames with 21 human 2D landmarks per visible hand (roughly 50,000-150,000 clicked joints, depending on two-hand prevalence);
- at least 30 signers, at least five phone/camera families, and balanced skin tone, background, lighting, blur, contact, crossing, edge, and partial visibility;
- public 3D hand datasets for depth pretraining, with AppHear 2D/visibility supervision for domain adaptation;
- strict signer + device + session disjoint validation/test splits;
- approximately several modern GPU-days to a few GPU-weeks for detector/regressor fine-tuning and controlled ablations.

Human monocular images do not provide metric 3D truth by clicking. True 3D fine-tuning would require multi-view/depth capture, calibrated fitting with manual QA, or a trusted public 3D dataset. MediaPipe pseudo-depth is not independent truth.

**Route 3 — custom perception system.** Consider only if Route 1 fails for a systematic, trainable reason and Route 2 cannot fix it. Planning estimate: 20,000-50,000 boxed frames, 5,000-10,000 densely landmarked frames, 50+ signers, 8+ device/camera families, substantial no-hand/ordinary-motion negatives, and multi-view/3D supervision if exact depth is required. Expect multiple GPU-weeks plus annotation QA and mobile quantization work. This is not currently justified.

### 10.3 Augmentation rules for Route 2/3

Use motion blur with direction/magnitude distributions measured from signing clips; exposure/gamma/white-balance variation; compression/noise; scale and edge truncation; realistic hand-hand/body occluders; camera rotation/mirroring; background replacement; and skin-tone-preserving photometric variation. Never let an augmentation silently change anatomical Left/Right. Synthetic occlusion cannot replace real contact examples.

## 11. Hard perception evaluation set

Build a classifier-independent, frame-and-sequence benchmark with a frozen annotation guide.

### Required strata

- ordinary one-hand and two-hand signs;
- hand-hand contact/overlap;
- hand-body/face contact;
- crossing and midline ambiguity;
- fast motion and blur;
- torso/background overlap;
- partial visibility and edge-of-frame;
- true entering/leaving;
- no-hand/rest/idle hands and non-sign gestures;
- difficult lighting and compression;
- varied skin/background conditions where current data permit.

### Required human truth

- every visible hand instance box;
- anatomical Left/Right, with explicit ambiguous state;
- visibility/occlusion and condition tags;
- 21 2D landmarks with per-joint visibility on a stratified subset;
- sequence continuity and true presence/absence at each sampled frame.

### Metrics

1. visible-hand instance recall and precision;
2. complete two-hand recall;
3. anatomical handedness accuracy and ambiguity/coverage;
4. box AP/recall at IoU thresholds as diagnostics, not the primary metric;
5. normalized mean landmark error and PCK on human-keypoint subset;
6. temporal jitter on stable visible joints;
7. dropout-run length distribution and drops per visible-hand-second;
8. p50/p95 direct observation gap;
9. no-hand/idle false-presence rate;
10. backend and camera-to-output p50/p95 latency, useful outputs/s, PSS, thermal decay, and crashes.

Recognition commits are a later compatibility check, not the primary perception metric.

## 12. Cross-device benchmark protocol

### Device matrix

| Tier | Minimum representation | SoC coverage goal |
|---|---|---|
| Low | 4-6 GB RAM, older/entry ARM cores, no required GPU/NPU | At least one Qualcomm or MediaTek entry device. |
| Mainstream | 6-8 GB RAM, current mid-range cores | At least one Snapdragon and one MediaTek/Exynos where available. |
| High | recent flagship, 8+ GB | At least one Snapdragon flagship and, if available, a different GPU/SoC family. |

If only Xiaomi is available, run it as the reference and label every cross-device gate **UNVERIFIED**. Emulator or desktop benchmarks do not substitute for devices.

### Modes per device

1. CPU/default or XNNPACK — mandatory correctness baseline.
2. GPU/Vulkan — only where supported and stable.
3. NNAPI — only if operator coverage is high; record partitions/fallback.
4. Optional vendor delegate — diagnostic acceleration only, never sole correctness path.

### Procedure

- fixed camera resolution, orientation, and front/back camera policy;
- cold start plus 20-second warm-up;
- at least 2 minutes per short mode for comparison and 10 minutes sustained for promoted candidates;
- order-balanced backend/delegate sequence;
- identical prerecorded-frame replay for quality/conformance, then live CameraX pipeline for sustainability;
- record camera-delivered, accepted/dropped, conversion, detector, regressor, publication, and S4 timestamps;
- record PSS, model/runtime memory, CPU/GPU utilization where available, Android thermal status, battery/temperature proxy, crashes, and output-order violations;
- compare output coordinates and presence decisions across CPU/GPU/NNAPI on a conformance subset;
- report first-half vs second-half useful throughput and p95 latency.

This separates “the model executes” from “the model sustains AppHear's camera pipeline.”

## 13. Weighted candidate scoring matrix

Weights total 100. Scores are `1` (poor) to `5` (strong). `U` means not yet known; no score is invented for an unmeasured AppHear result. Totals are feasibility judgments, not accuracy measurements.

| Criterion (weight) | RTMDet + MobRecon | RTMW3D-m + person detector | RTMDet + RTMPose 2D | Learned detector + TAPIR | MP + independent fallback | Custom/fine-tuned 3D stack |
|---|---:|---:|---:|---:|---:|---:|
| Perception-quality potential (18) | 4/U | 4/U | 4/U | 3/U | 4/U | U |
| Contact/occlusion robustness (10) | 4/U | 4/U | 3/U | 4/U | 4/U | U |
| Mobile latency (10) | 4/U | 2/U | 4/U | 1/U | 2/U | U |
| Low-end feasibility (9) | 4/U | 2/U | 4/U | 1/U | 2/U | U |
| Cross-device portability (9) | 3/U | 3/U | 4 | 1/U | 3/U | U |
| Memory (5) | 4/U | 2/U | 4/U | 1/U | 2/U | U |
| Model size (4) | 4/U | 2/U | 4/U | 1/U | 2/U | U |
| Android integration (7) | 3/U | 2/U | 4 | 1/U | 2/U | U |
| Current contract compatibility (10) | 4/U | 4/U | 2 | 2 | 4/U | 5 design target |
| Training/data burden (6) | 4 | 4 | 4 | 3 | 4 | 1 |
| Maintainability (4) | 3 | 3 | 4 | 2 | 2 | 2 |
| Licensing (4) | 4/U weights | 4/U weights | 4/U weights | 5 | 4/U weights | 4/U weights/data |
| Project risk (4; 5=low) | 3 | 2 | 3 | 1 | 2 | 1 |
| **Known-evidence weighted total / 100** | **76, many U** | **61, many U** | **76, but no z** | **41, many U** | **61, many U** | **not rankable** |

The tie between RTMDet/MobRecon and RTMDet/RTMPose is resolved by contract: MobRecon has a credible 3D output path; RTMPose does not. RTMW3D ranks second despite lower mobile feasibility because its body context and 3D topology directly address contact/body overlap and anatomical identity. The custom route is deliberately not given a numeric rank based on imagined accuracy.

## 14. Ranked top three

### Candidate #1 — RTMDet-nano + MobRecon DenseStack

**Why recommended:** smallest credible experiment that is both visually independent of MediaPipe and potentially compatible with 21 `x/y/z`. The detector and regressor can be evaluated separately, model components are small/open, and failure can be diagnosed as detection, crop, geometry, identity, export, or latency rather than hidden inside one task graph.

**Expected tradeoff:** much higher direct-perception ceiling than carry-forward, but detector + up to two crop passes cost more than a single landmarker. Paper crop latency is promising; Android total latency is unknown. Off-the-shelf domain accuracy may be inadequate, especially for two touching hands.

### Candidate #2 — person detector + RTMW3D-m whole-body context

**Why backup:** a whole-person crop preserves torso, arms, and both hands jointly, which may resolve body overlap and anatomical Left/Right better than independent hand crops. It also offers a path to body and 3D hand topology.

**Expected tradeoff:** RTMW-m 2D is 4.3 GFLOPs before person detection and public hand AP/AR is only `0.491/0.604` on COCO-WholeBody. RTMW3D mobile export and latency are unknown. It is unlikely to be the low-tier model without substantial optimization.

### Candidate #3 — AppHear-domain fine-tuned detector + 3D regressor

**Why longer-term:** if #1 finds the right hands and geometry but misses a bounded subset of contact/motion conditions, fine-tuning is more defensible than inventing another recovery heuristic. Keep a license-clean OpenMMLab detector and MobRecon-style 3D head, and preserve the canonical adapter.

**Expected tradeoff:** highest attainable domain fit, but at least thousands of human box/keypoint annotations, careful 3D supervision strategy, multiple devices/signers, and mobile quantization work. It must not start until #1 identifies a trainable gap.

## 15. Smallest useful PoC — plan only

### Question

Does RTMDet-nano + MobRecon materially improve **direct** visible-hand and two-hand/contact availability over MediaPipe at a plausible model size and export path?

### Frozen models

- detector: rtmlib/OpenMMLab `rtmdet_nano_8xb32-300e_hand`, 320x320;
- 3D regressor: MobRecon DenseStack pretrained checkpoint, 128x128;
- 2D control: `rtmpose-m_simcc-hand5`, 256x256;
- baseline: current MediaPipe direct output only; no A2 recovery.

No fine-tuning, threshold sweep, Android integration, or recognition retraining is part of this PoC.

### Input preparation

1. Decode original RGB frames upright and unmirrored; preserve an immutable frame ID.
2. Letterbox the full frame to detector input and record the inverse transform.
3. Keep up to two non-overlapping hand detections after the model's documented NMS; retain raw scores for a preregistered, minimal operating-point check.
4. Pad each box by one frozen factor, square it, crop from the original RGB frame, and resize to 128x128 for MobRecon.
5. Run RTMPose on the same crops as a 2D control.
6. Map 2D points back to original normalized image coordinates; map MobRecon joints into a provisional root-relative 3D record without claiming MediaPipe-z equivalence.
7. Assign anatomical side only when body geometry or human truth supports it; otherwise emit ambiguous. Do not use temporal identity carry-forward.

### Test data

- primary frozen detection set: 150 corrected all-hand gold frames / 184 instances / 41 signers;
- temporal set: 551 A2 reviewed frames / 21 sequences, retaining contact, crossing, leaving, rest, and visible-missing labels;
- negative set: at least 200 signer/session-separated no-hand, idle-hand, and transition frames sampled from already governed negatives;
- human landmark subset: annotate 200 stratified frames, targeting at least 250 visible hand instances and both hands in at least half of eligible frames; include every hard-condition stratum.

The 200-frame landmark subset is new human annotation work, not model training. Freeze it before model scoring.

### Comparisons

- MediaPipe direct vs RTMDet detection;
- MediaPipe direct vs RTMDet+RTMPose 2D;
- MediaPipe direct vs RTMDet+MobRecon 2D projection and 3D availability;
- paired error review by motion/contact/occlusion/edge/partial/no-hand;
- detector-oracle regressor test using human boxes to separate detector failure from regressor failure.

### Expected artifacts

- immutable PoC manifest with split/condition/source hashes;
- raw per-frame detector boxes, scores, 2D/3D joints, transformations, and timings;
- human keypoint annotations and adjudication log;
- paired metric JSON/CSV and dropout-run tables;
- failure panels grouped by detector miss, merged hands, bad crop, regressor collapse, side ambiguity, and false presence;
- model hashes, licenses, parameter/file sizes, ONNX/export report, and operator-compatibility report;
- a single `PROMOTE_TO_ANDROID_BENCHMARK` or `REJECT` decision.

## 16. Preregistered PoC success gates

### Direct quality gates

All must pass on frozen paired data:

1. visible-hand instance recall `>=81%` on the corrected 150-frame set (at least +14.7 percentage points over `66.30%`);
2. complete two-hand recall `>=65%` (at least +18.7 points over `46.27%`);
3. occluded/contact recall improves by at least 15 absolute points, with no hard subgroup more than 5 points worse than MediaPipe;
4. no-hand/idle false-presence rate `<=3%` and no more than 2 absolute points above MediaPipe on at least 200 negative frames;
5. A2 visible-hand dropout runs reduced by at least 35%, multi-observation runs reduced by at least 50%, and p95 direct observation gap reduced by at least 30%;
6. anatomical handedness accuracy `>=97%` on unambiguous instances and ambiguity is reported rather than forced;
7. on human 2D landmarks, normalized mean error is no worse than MediaPipe by more than 10%, PCK and per-joint visibility are reported, and temporal jitter is no worse by more than 15% on stable visible joints.

### Contract/export gates

1. every predicted 3D joint has a documented coordinate convention and finite value;
2. the 21-joint ordering is deterministically mapped to AppHear ordering;
3. no synthetic zero-depth substitution is accepted as S4 parity;
4. MobRecon exports to at least one credible Android runtime or a bounded export blocker is identified;
5. combined model package target `<=40 MB` before runtime libraries;
6. license/weight/MANO redistribution terms are documented and compatible before Android work.

### Mobile promotion gates

Desktop accuracy alone cannot win. Promotion requires a later three-tier Android benchmark. CPU/XNNPACK must meet the minimum tier's correctness and sustain at least 15 useful direct observations/s with p95 backend latency <=66 ms, <=10% 10-minute decay, and zero crashes/order errors. GPU/NNAPI results may improve the tier but cannot waive CPU correctness.

## 17. Risks and unknowns

- **Detector domain fit:** RTMDet public AP does not predict AppHear contact/motion recall.
- **Two-hand crop separation:** NMS may merge touching hands; oracle-box testing is essential.
- **Depth semantics:** MobRecon's camera/root-relative 3D is not automatically MediaPipe `z`.
- **Handedness:** recommended components do not directly provide anatomical Left/Right; body geometry or a learned side head may be needed.
- **Exportability:** MobRecon's PyTorch operators and mesh decoder have not been verified in ONNX, ncnn, or ExecuTorch on this project.
- **End-to-end latency:** the paper's A14 number excludes full-frame detection, two crops, CameraX conversion, Android runtime, and thermal load.
- **Licenses:** code licenses are favorable, but pretrained weights, training datasets, and MANO asset/redistribution terms need an explicit release review.
- **Annotation scarcity:** AppHear has no human dense 21-point truth today.
- **Cross-device hardware:** only the Xiaomi has deep current measurements; all tier claims remain requirements, not results.
- **Distribution shift:** even a geometrically valid alternative may shift S4 features enough to damage the frozen recognizer.
- **Tiered models:** different capacity variants could create device-correlated recognition behavior; require per-tier feature-distribution and end-to-end parity checks.

## 18. Explicit next-step recommendation and stopping point

Approve one bounded, offline **RTMDet-nano + MobRecon DenseStack PoC design/annotation package** exactly as Section 15 specifies. Begin with repository-governed frames and model/license/export verification; do not integrate Android or train anything. Use RTMPose only as the 2D control. If detector recall fails while oracle-box MobRecon succeeds, the next decision is detector replacement/fine-tuning. If oracle-box MobRecon itself fails contact geometry, reject the stack without Android work. If quality passes but export/size fails, evaluate RTMW3D or ExecuTorch/ncnn feasibility before implementation.

This study stops here. No backend was downloaded, trained, integrated, or substituted; no MediaPipe setting, S4/S5/S6/S7 behavior, classifier, or production flag was changed.
