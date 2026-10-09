# P1 Perception Architecture Feasibility and Adapter Audit

Status: `P1_AUDIT_COMPLETE`

Scope: read-only benchmark, adapter, licensing, environment, and experiment-design audit. No
DWPose or Sapiens checkpoint was downloaded or executed. No detector, MediaPipe rerun, training,
Android test, or S4/S5/S6/S7 change occurred.

## 1. Executive conclusion

The frozen AppHear evidence is sufficient to run a fair **hand-availability/localization**
comparison between DWPose-L and Sapiens whole-body pose, provided both receive the same frozen
whole-frame pseudo-person ROI. The evaluation can measure visible-hand instance recall,
frame-level coverage, two-hand completeness, hard-condition recall, negative false presence, and
pairwise recoveries against MediaPipe without rerunning MediaPipe.

It cannot measure human-truth landmark error or anatomical handedness accuracy: the positive gold
contains hand boxes but no human 21-point landmarks/masks, and every one of the 184 hand boxes has
`anatomical_side="unknown"`.

DWPose-L 256x192 has a feasible adapter and a plausible CPU execution path on this machine after
an isolated compatible PyTorch/MMPose environment is approved. Sapiens-2B has a definable adapter
but is **not hardware/storage feasible on this machine**: its checkpoint is 8.07 GiB, only about
9.44 GiB is free on F:, the machine has no operational CUDA device, and the official lite path is
CUDA-oriented. Sapiens remains `RESEARCH_CEILING_ONLY`; exact P2 execution is blocked until the
lead approves suitable external CUDA hardware or explicitly selects a smaller Sapiens fallback.

## 2. Verified frozen benchmark inventory

### 2.1 Corrected positive all-hand gold

Canonical directory:

`F:/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/e2e_all_hand_gold_v1/engineering_01`

| Item | Verified value |
|---|---:|
| Frames / unique clips | 150 / 150 |
| RGB images available | 150 |
| Image dimensions | all 640x480 |
| Signers | 41 |
| Visible hand instances | 184 |
| Frames with >=1 visible hand | 117 |
| Two-visible-hand frames | 67 |
| Zero-visible-hand frames | 33 |
| Sampling | 50 each at sign-span q25/q50/q75 |
| Source split | 120 train, 30 validation |

Canonical files:

- `gold_review.csv`: human boxes and condition tags; SHA-256
  `53e3db0dceeeb4b5a991be132bdce1fe489d82d670daa662023f6707852835d9`.
- `internal_index.csv`: source/signer/frame/image metadata plus frozen MediaPipe outputs; SHA-256
  `38abcd78d18e20d4954ca81bc3d171460c6b2b9f9520cf95fabf2d09c1face58`.
- `audit_summary.json`: frozen MediaPipe association result; SHA-256
  `cde2742821587cbb5ffb7bebb6df76bc144ea975473606ea0cf9a11e89748cd6`.
- `center_images/g001.png` through `g150.png`: all paths resolve.
- `provenance.json`: selection seed 260726, one frame per clip, model-task hashes, and sampling
  policy.

No ground truth was regenerated or reinterpreted.

### 2.2 NEGATIVE_GOLD_V1

Canonical manifest:

`artifacts/recognition_upgrade/perception_backend_replacement/negative_gold_item_level_audit_01/finalization/NEGATIVE_GOLD_V1_MANIFEST.csv`

| Item | Verified value |
|---|---:|
| Total rows | 200 |
| Historical AppHear rows | 76 |
| Open Images V7 additions | 124 |
| Existing image paths | 200/200 |
| Matching SHA-256 values | 200/200 |
| Unique IDs / image hashes | 200 / 200 |
| Frozen decision | `NEGATIVE_GOLD_V1_COMPLETE` |

Manifest SHA-256:
`33a1754420442515d736dd8b0bbcde8fa933847c5d4cf606118f9e865317fe15`.

Machine result SHA-256:
`58837b6f7cdf9f7c596a29b7ae07649ba5962dd60262a4a4ab749b48a9c8783f`.

The manifest records origin, source group, source ID, image path/hash, dHash, semantic truth,
evidence basis, and Open Images attribution/license metadata. Benchmark construction is closed;
these 200 images are evaluation-only and may not be used to tune presence thresholds.

### 2.3 Frozen diagnostic subsets

All three subsets are **hand-instance lists**, not crop sets or standalone frame directories. They
are deterministic metadata references into:

`artifacts/recognition_upgrade/perception_backend_replacement/p0_rtmdet_detector_02/paired_mediapipe_vs_rtmdet.csv`

The source has SHA-256
`a416b35d985ab2b9237ee6056e080cd71089978d6cb0812a3f5a5b0ff75d4290`.
Each instance key is `(sample_id, gold_index)` and resolves through the positive gold manifest.

| Set | Pairwise definition | Instances | Unique frames | Selection SHA-256 |
|---|---|---:|---:|---|
| `RTMDET_COMPLEMENTARY_16` | MediaPipe miss / RTMDet hit | 16 | 15 | `98968c14ee90da063035f6d2b898d71520bd7794031b302dca750d077f2e91e4` |
| `RTMDET_REGRESSION_25` | MediaPipe hit / RTMDet miss | 25 | 21 | `3386a6eaa946c330ed93757aba15f1540c88dff36d5fff7404482c42330a74ad` |
| `PERCEPTION_HARD_CORE_46` | both miss | 46 | 41 | `195c2c282887363cc4b04b03be3c925f6ac6d627937a44792d37e4c0c90b9978` |

## 3. Positive ground-truth format

Each accepted `gold_review.csv` row supplies:

- `visible_hand_count` in {0,1,2};
- `gold_hands_json`, a list of normalized image-coordinate boxes with
  `x_min,y_min,x_max,y_max,anatomical_side`;
- overlapping frame-level yes/no tags: `motion_blur`, `occlusion`, `near_face`,
  `edge_clipped`, and `partial_visibility`;
- source-mirror fields, currently unresolved for the authoritative boxes;
- reviewer status and notes.

Geometry available: human hand boxes only. There are no human landmark coordinates, masks, wrist
points, or per-pixel visibility maps. Partial/edge hands remain positive whenever the reviewer
could see a real hand portion; six hand instances in three frames are tagged partial visibility.
Two-hand frames contain two separate boxes in the same list.

All 184 `anatomical_side` values are `unknown`. Candidate left/right group names must be retained,
but left/right correctness cannot be scored from this benchmark. No future evaluator may infer
anatomical identity from box position and call it human truth.

## 4. Frozen MediaPipe baseline evidence

The exact frozen baseline is:

| Metric | Count | Rate |
|---|---:|---:|
| Visible-hand instance recall | 122/184 | 66.3043% |
| Any-hand frame recall | 91/117 | 77.7778% |
| Complete two-hand frame recall | 31/67 | 46.2687% |
| Two-hand instance recall | 87/134 | 64.9254% |
| Motion-blur instance recall | 70/120 | 58.3333% |
| Occlusion instance recall | 13/25 | 52.0000% |
| Edge-clipped instance recall | 8/31 | 25.8065% |
| Partial-visibility instance recall | 1/6 | 16.6667% |

`internal_index.csv` preserves every direct MediaPipe prediction as 21 normalized xyz landmarks,
a predicted left/right slot, handedness score, and derived box. It contains exactly 122 predicted
groups. `audit_summary.json` preserves the exact per-frame associations. The P0 paired CSV
preserves one row per 184 gold hands with `mediapipe_hit` plus condition tags. Consequently P2 can
perform exact pairwise hit/miss analysis without rerunning MediaPipe.

What cannot be reconstructed is anatomical handedness correctness because human anatomical-side
truth is absent. MediaPipe's per-joint confidence is also absent; only the group handedness score
is stored. Neither limitation affects reconstruction of the frozen 122/184 hit result.

## 5. Person ROI audit and recommendation

No frozen reliable person bounding box exists. The positive evidence has full-frame dimensions,
hand boxes, two pose-wrist points, and hand predictions, but not full pose extents or an
independent person ROI. Hand GT/predictions must not create the model input crop because that
would leak evaluation truth or baseline behavior. Existing detector outputs would turn P2 into a
detector-plus-pose test.

Recommended frozen model-independent ROI:

1. Treat the exact whole image as one pseudo-person box: `[0,0,image_width,image_height]`.
2. Feed the same box to both top-down estimators.
3. Use each candidate's official center/scale conversion with padding 1.25 and fixed 3:4 input
   aspect ratio; record the exact affine and inverse affine per image.
4. Use the same rule for all 150 positives and all 200 negatives, including images with no person.
5. Do not add a person detector, pose-guided crop, GT-hand expansion, or result-dependent retry.

Both approved model inputs have the same 3:4 aspect ratio (DWPose 192x256 width/height; Sapiens
768x1024). Whole-frame ROI therefore isolates the pose estimator as well as possible. It covers
all normalized GT boxes, including boxes touching an image edge. The tradeoff is reduced signer
scale after portrait-aspect padding, but this is deterministic, shared, and does not select a
candidate-specific favorable crop.

## 6. DWPose-L 256x192 adapter

Exact lane:

- official repository: [IDEA-Research/DWPose](https://github.com/IDEA-Research/DWPose);
- config: `rtmpose-l_8xb64-270e_coco-ubody-wholebody-256x192.py`;
- checkpoint: `dw-ll_ucoco.pth`;
- Hugging Face path: [yzd-v/DWPose/dw-ll_ucoco.pth](https://huggingface.co/yzd-v/DWPose/blob/main/dw-ll_ucoco.pth);
- size: 404,734,742 bytes (386.0 MiB);
- published LFS SHA-256: `e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7`;
- model: top-down RTMPose/DWPose-L, CSPNeXt-L backbone, RTMCC head;
- output: 133 COCO-WholeBody keypoints;
- input: 192x256 width/height, conventionally reported as 256x192;
- reported cost: 4.5 GFLOPs;
- reported COCO-WholeBody hand AP: 0.566 under the repository's person-detector protocol.

Official preprocessing: image load, bbox center/scale, top-down affine to 192x256, BGR-to-RGB,
mean `[123.675,116.28,103.53]`, std `[58.395,57.12,57.375]`, FP tensor. Test config enables
horizontal flip testing. Output uses SimCC x/y coordinate classification with split ratio 2.0;
the decoded coordinate is each axis argmax divided by 2, then inverse-affine mapped to source
pixels. The per-keypoint score is `min(max(simcc_x), max(simcc_y))`; it is a response score, not a
calibrated probability. The config has `normalize=False`.

Hand mapping, zero-based:

- DWPose left hand: output indices **91..111** -> local hand indices 0..20.
- DWPose right hand: output indices **112..132** -> local hand indices 0..20.

Within either 21-point block: root/wrist, thumb1-4, forefinger1-4, middle1-4, ring1-4,
pinky1-4. This order is compatible in cardinality and topology with a future MediaPipe-style
adapter but P1/P2 must retain native COCO-WholeBody outputs and must not write S4 `[96,258]`.

Framework: an isolated compatible PyTorch, torchvision, MMEngine, MMCV, MMDetection, and MMPose
environment. The repository pins an old PyTorch 1.9.1/CUDA example and MMPose dependencies
`mmcv>=2.0,<2.1`, `mmdet>=3.0,<3.2`, `mmengine>=0.4,<1.0`; the current AppHear Python 3.11 venv is
not suitable and contains none of these packages. The published 256x192 artifact is PTH; the
repository's published ONNX is the different 384x288 lane and may not silently replace it.

Adapter feasibility: **yes**. CPU feasibility: **yes, diagnostic/offline**, subject to dependency
installation and later measurement. CUDA GPU feasibility on this machine: **no**.

## 7. Sapiens-2B 133-keypoint adapter

Exact lane:

- official repository: [facebookresearch/sapiens](https://github.com/facebookresearch/sapiens);
- config: `sapiens_2b-210e_coco_wholebody-1024x768.py`;
- checkpoint: `sapiens_2b_coco_wholebody_best_coco_wholebody_AP_745.pth`;
- checkpoint repository: [noahcao/sapiens-pose-coco](https://huggingface.co/noahcao/sapiens-pose-coco);
- size: 8,665,327,573 bytes (8.07 GiB);
- architecture: 2B-parameter ViT, 48 layers, embedding dimension 1920, patch size 16;
- input: 768x1024 width/height;
- output: 133 COCO-WholeBody heatmaps at 192x256;
- reported checkpoint whole-body AP identifier: 0.745.

Official preprocessing: bbox center/scale, top-down UDP affine, BGR-to-RGB, mean
`[123.675,116.28,103.53]`, std `[58.395,57.12,57.375]`, and 768x1024 input. The exact config
enables flip testing. Output uses UDP Gaussian heatmaps (sigma 6, scale 4); decoding obtains the
heatmap maximum, applies DARK/UDP refinement, maps to input coordinates, and inverse-affine maps
to source pixels. Each score is the raw heatmap maximum and is not a calibrated probability.
P2 should use the exact config values rather than the rounded means/stds in the lite demo.

Hand mapping, zero-based:

- Sapiens left hand: output indices **91..111** -> local hand indices 0..20.
- Sapiens right hand: output indices **112..132** -> local hand indices 0..20.

The local ordering is the same COCO-WholeBody root/thumb/forefinger/middle/ring/pinky order listed
for DWPose.

The official full environment is Linux/Conda, Python 3.10, PyTorch with CUDA 12.1, plus the
repository's engine/cv/pose/det packages. Sapiens-Lite reduces dependencies to PyTorch, NumPy,
and OpenCV, but its supplied execution path calls CUDA directly; it can omit the detector and use
the whole image, which supports the recommended ROI rule.

Adapter feasibility: **yes as a specification**. Hardware feasibility here:
`SAPIENS_2B_NOT_FEASIBLE`. Classification: `RESEARCH_CEILING_ONLY`.

## 8. Proposed frozen hand-presence rule

COCO-WholeBody estimators always return left/right keypoint slots for a person crop, so a separate
presence gate is unavoidable. Their raw score types differ (SimCC axis-peak minimum versus heatmap
peak), so scores must not be compared numerically across models or calibrated on AppHear.

Most defensible common rule to freeze before P2:

1. Use the official default visualization threshold **0.30** independently on each model's native
   keypoint score. Both repositories expose 0.30 as the default visualization threshold.
2. A left/right hand group is present when **at least 11 of its 21 joints** have score >=0.30.
   This is a majority-support rule; it prevents one or two spurious peaks from creating a hand.
3. Do not require the root/wrist specifically and do not apply a geometric plausibility rejection;
   those extra gates would preferentially reject clipped/occluded hands, which are target cases.
4. Do not tune 0.30 or 11/21 using either positive gold or NEGATIVE_GOLD_V1.

This structural 11/21 requirement is project-defined, not an official presence definition; neither
model publishes a binary hand-presence head. It must be explicitly approved/frozen before P2.
The least-biased alternative, if the lead rejects a common structural rule, is to use each model's
official 0.30 per-joint threshold with the same majority rule and report score distributions—not
to choose separate AppHear-optimized operating points.

Retain for every frame: all 133 decoded xy coordinates and scores, native left/right 21-point
blocks, each group's 21 threshold decisions, confident-joint count, min/mean/median/max score,
presence decision, ROI, affine/inverse affine, checkpoint hash, and model/runtime identity. Full
Sapiens heatmap tensors need not be retained for every frame because they would add roughly 9 GiB;
decoded values and score summaries are sufficient for registered metrics. No borderline case may
be used to revise the frozen rule.

## 9. Proposed prediction-to-GT matching rule

The available human geometry supports reuse of the frozen landmark association contract:

1. Consider only a candidate left/right group that passes the frozen presence rule.
2. Use its 21 inverse-mapped image-coordinate points.
3. Define palm center as the mean of local indices `[0,5,9,13,17]` (root and four MCP bases),
   identical to the MediaPipe audit's topology-relative palm definition.
4. A candidate group is eligible for a GT box when palm center is inside the box and at least 50%
   of all 21 predicted points are inside it.
5. Perform exact maximum-cardinality one-to-one matching; tie-break by larger point coverage then
   smaller normalized palm-to-box-center distance, matching the frozen baseline evaluator.

No IoU threshold is needed because the candidates do not directly output hand boxes. A diagnostic
predicted box may be the min/max of the 21 points, but it is not the primary matcher. Anatomical
left/right must not be part of correctness because GT sides are all unknown. Record the candidate
group name for diagnostics only.

Edge-clipped and partial hands use the same rule and original clipped GT box. Do not expand boxes,
ignore edge rows, or change tolerance by subgroup. This preserves visible-hand instance, any-hand
frame, complete two-hand, two-hand instance, blur, occlusion, edge, and partial recall.

## 10. Frozen negative evaluation

For each of the 200 NEGATIVE_GOLD_V1 images, create exactly one full-frame pseudo-person ROI and
apply the same adapter/presence rule. Do not tune against these images.

Per-frame outputs:

- false hand-present: either native group passes;
- false left presence and false right presence separately;
- predicted hand-group count in {0,1,2};
- per-group confident-joint count and min/mean/median/max score;
- frame maximum and aggregate hand confidence summaries;
- all 42 native hand coordinates/scores and a pointer to the full 133-output artifact;
- ROI/affine, image hash, model/checkpoint/environment provenance.

Primary negative rates are frames with any false group / 200, false-left / 200, false-right / 200,
and total hallucinated groups. Do not treat absence of a person or the Open Images discovery label
as model truth; the frozen `ZERO_HAND` human verdict is authoritative.

## 11. Pairwise result schemas

### Gold-hand table: one row per 184 instances

Required fields include sample/gold index, GT box, condition tags, baseline hit and baseline
prediction metadata, DWPose present/match/group/score summaries, Sapiens equivalents, association
diagnostics, and these categorical comparisons:

- baseline hit / candidate hit;
- baseline hit / candidate miss;
- baseline miss / candidate hit;
- baseline miss / candidate miss;
- DWPose and Sapiens both hit;
- DWPose only;
- Sapiens only;
- both miss.

### Positive-frame table: one row per 150 frames

Store GT count, each model's present/matched group counts, any-hand hit, two-hand complete flag,
unmatched groups, native left/right decisions, ROI, latency/memory diagnostics, and raw-output path.

### Negative table: one row per 200 frames

Store the outputs listed in section 10 for both candidates.

### HARD_CORE case table

Produce one CSV/JSON row for every 46 `(sample_id,gold_index)` entries. Aggregate-only reporting is
prohibited. Preserve existing tags and the baseline/RTMDet pairwise category unchanged.

## 12. HARD_CORE diagnostic capabilities

The paired source provides these existing overlapping tags:

| Set | Blur | Occlusion | Near face | Edge | Partial |
|---|---:|---:|---:|---:|---:|
| COMPLEMENTARY_16 | 15 | 1 | 0 | 5 | 1 |
| REGRESSION_25 | 21 | 5 | 1 | 0 | 0 |
| HARD_CORE_46 | 35 | 11 | 0 | 18 | 4 |

There are no frozen labels for hand-hand contact, hand-body contact, crossing, or small-scale cause.
Box area can later be reported as geometry, but it must not be presented as a human failure-cause
label. No new diagnostic causes should be invented during P2.

## 13. Development machine and environment

| Resource | Verified state |
|---|---|
| CPU | AMD Ryzen 5 5600G, 6 cores / 12 logical processors |
| RAM | 29,952,552,960 bytes = 27.9 GiB |
| GPU | AMD Radeon integrated graphics; WMI reports 4 GiB shared adapter memory |
| NVIDIA/CUDA | no operational NVIDIA adapter/NVML; `nvcc` absent |
| Python | 3.11.5 in `.venv` |
| PyTorch / torchvision | not installed |
| MMCV/MMEngine/MMPose/MMDet | not installed |
| ONNX Runtime | 1.22.1, CPU and Azure providers only |
| OpenCV | 4.13.0.92 |
| F: free space | 10,131,853,312 bytes = 9.44 GiB at audit time |

## 14. DWPose feasibility

- Checkpoint: 386 MiB; parameter/runtime environment likely adds roughly 2-4 GiB installed.
- Raw decoded results and compact diagnostics: well below 100 MiB; optional visual panels may add
  0.1-1 GiB.
- CPU: feasible for a bounded 350-image offline run; latency unknown until P2 and must remain
  diagnostic.
- GPU: no CUDA path on this machine. DirectML/AMD substitution is not part of the approved lane.
- Dependency risk: old repository pins conflict with the current venv; use an isolated environment
  and hash it before execution.
- Mobile implication: 4.5 GFLOPs and standard convolutional/RTMCC components preserve a plausible
  future optimization/export lane, but P1 makes no Android claim.

Final: **DWPose-L adapter feasible: YES. Local CPU execution plausible: YES.**

## 15. Sapiens-2B feasibility and fallbacks

Approximate inference resource reasoning:

- PTH checkpoint: 8.07 GiB before environment, outputs, or temporary files.
- FP32 2B parameters alone are about 8 GiB; runtime, 1024x768 activations, decoding, and framework
  memory add materially more. Official lite TorchScript uses FP32; exported non-TorchScript uses
  BF16/FP16 on CUDA.
- A practical CUDA run should be planned for at least 16 GiB VRAM, with 24 GiB preferred. This is
  an engineering estimate, not an official published minimum.
- Host RAM should be at least 24-32 GiB; this machine is at the lower boundary.
- Total disk for checkpoint plus isolated CUDA/PyTorch/Sapiens dependencies and bounded outputs is
  approximately 12-18 GiB, above current free space.
- Official execution is CUDA-oriented; there is no usable CUDA device here.

Final classification: **`SAPIENS_2B_NOT_FEASIBLE` on the current machine**. Adapter definition is
complete, but exact execution requires different hardware/storage.

Same-family fallbacks, requiring project-lead approval before download:

1. **Sapiens-0.6B 133-keypoint**, 2,644,380,855 bytes (2.46 GiB), AP identifier 0.695: strongest
   credible CPU/storage fallback here, but likely slow and still requires an isolated environment.
2. **Sapiens-0.3B 133-keypoint**, 1,318,345,687 bytes (1.23 GiB), AP identifier 0.620: safest local
   fallback with the largest capacity/quality reduction.
3. **Sapiens-1B 133-keypoint**, 4,675,274,241 bytes (4.35 GiB), AP identifier 0.727: stronger but
   marginal locally because checkpoint plus dependencies consume most free disk and CPU cost is
   high. It ranks below 0.6B for practical local feasibility, despite higher expected quality.

Do not substitute a fallback automatically. The approved 2B lane remains blocked pending a lead
decision.

## 16. Download and storage estimates

| Item | Estimate |
|---|---:|
| DWPose-L `dw-ll_ucoco.pth` | 386 MiB exact |
| DWPose isolated dependencies | roughly 2-4 GiB installed |
| Sapiens-2B PTH | 8.07 GiB exact |
| Sapiens full/lite dependencies | roughly 3-8 GiB depending on CUDA/full vs lite |
| Compact decoded outputs for 350 images | roughly 10-100 MiB |
| Optional images/panels | roughly 0.1-1 GiB |
| Full Sapiens heatmaps for all images | roughly 9 GiB; do not retain by default |

No file was downloaded during P1.

## 17. License classification

### DWPose-L

- Repository code: Apache-2.0.
- Hugging Face model repository metadata: Apache-2.0.
- Training includes COCO-WholeBody and UBody. The DWPose/OSX public pages do not provide a clear,
  checkpoint-specific production-rights analysis for all source imagery/annotations.
- Classification: **`LICENSE_REVIEW_REQUIRED`**. It remains the plausible production lane, but a
  production claim requires explicit checkpoint/dataset legal review.

Official sources:
[DWPose repository](https://github.com/IDEA-Research/DWPose),
[license](https://github.com/IDEA-Research/DWPose/blob/main/LICENSE),
[model/config table](https://github.com/IDEA-Research/DWPose#-results-and-models), and
[checkpoint metadata](https://huggingface.co/yzd-v/DWPose).

### Sapiens-2B

- Repository license: Creative Commons Attribution-NonCommercial 4.0.
- Sapiens pose checkpoint repository metadata: CC BY-NC 4.0 and gated access.
- Commercial/production use is not authorized by those terms.
- Classification: **`RESEARCH_ONLY`** and **`RESEARCH_CEILING_ONLY`**.

Official sources:
[Sapiens repository](https://github.com/facebookresearch/sapiens),
[license](https://github.com/facebookresearch/sapiens/blob/main/LICENSE),
[pose model table](https://github.com/facebookresearch/sapiens/blob/main/docs/POSE_README.md), and
[checkpoint repository](https://huggingface.co/noahcao/sapiens-pose-coco).

## 18. Metrics for P2

P2 must calculate, without setting promotion gates yet:

- visible-hand instance recall;
- any-hand frame recall;
- complete two-hand frame recall;
- two-hand instance recall;
- blur, occlusion, edge-clipped, and partial-visibility recall;
- false hand-present frame rate on 200 negatives;
- false left-hand and false right-hand rates;
- total hallucinated hand groups;
- HARD_CORE_46 recovery count/rate and 46-row case table;
- COMPLEMENTARY_16 recovery;
- REGRESSION_25 recoveries and regressions;
- baseline/candidate hit matrices;
- DWPose/Sapiens hit matrix;
- desktop preprocessing/inference/postprocessing latency as diagnostic only;
- peak host/GPU memory as diagnostic only.

No Android FPS or arbitrary P2 pass/fail threshold is introduced by this audit.

## 19. Unresolved blockers

1. Sapiens-2B cannot run practically on the current machine and available disk. External CUDA
   hardware or an explicitly approved same-family fallback is required.
2. The proposed 0.30 plus 11/21 common presence rule is scientifically defensible but project-
   defined; the lead must freeze it before inference.
3. Positive GT has no human landmark truth, so P2 cannot establish landmark accuracy, jitter, or
   S4-ready 21-point quality—only availability/localization inside human boxes.
4. Anatomical L/R truth is unknown for all 184 instances; candidate slot identity cannot be scored.
5. Contact/crossing/small-scale failure causes are not frozen annotations.
6. DWPose production licensing requires dataset/checkpoint review despite Apache repository and
   model-card labels.
7. Neither candidate environment exists locally. Installation/download must be a separately
   approved, provenance-frozen step.

## 20. Exact recommended P2 structure

After the project lead resolves Sapiens hardware and freezes presence/matching rules:

1. Freeze a 350-row input manifest: 150 positives plus 200 NEGATIVE_GOLD_V1 rows, with source
   paths, dimensions, and SHA-256. Never tune on the 200 negatives.
2. Freeze one full-frame pseudo-person ROI per image and every affine parameter before inference.
3. Run DWPose-L 256x192 and Sapiens-2B 133-keypoint on identical source bytes/ROIs with each exact
   official preprocessing/decoder and flip-test setting.
4. Save all 133 decoded coordinates/scores, 42 hand outputs, group presence diagnostics,
   environment/checkpoint hashes, and stage timing/memory.
5. Apply the one common frozen presence rule, then the frozen palm/50%-inside/maximum-cardinality
   matcher. Do not use candidate model output to revise either rule.
6. Produce 184-row hand, 150-row positive-frame, 200-row negative, and 46-row HARD_CORE tables,
   plus aggregate metrics and pairwise matrices.
7. Report DWPose and Sapiens separately. Sapiens is a diagnostic ceiling, never a production win.
8. Stop for review. Do not map to S4, integrate Android, retrain recognition, or select a backend
   until separately preregistered P2 gates are approved and results are inspected.

## Final audit classification

- `P1_AUDIT_COMPLETE`
- positive benchmark verified: **yes**
- NEGATIVE_GOLD_V1 verified: **yes**
- HARD_CORE_46 verified: **yes**
- DWPose-L adapter feasible: **yes**
- Sapiens-2B adapter feasible: **yes, specification only**
- Sapiens-2B hardware feasible: **no — `SAPIENS_2B_NOT_FEASIBLE` locally**
- next state: **P2 blocked pending Sapiens execution decision and rule/gate freeze**

