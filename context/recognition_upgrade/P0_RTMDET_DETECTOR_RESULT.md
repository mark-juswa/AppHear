# P0 — RTMDet-nano Detector-Only Validation

**Status:** complete  
**Decision:** `REJECT_RTMDET_P0`  
**Date:** 2026-08-20  
**Scope:** offline hand-box detection only; no landmarks, 3D, Android, S4-S7, or recognition claim

## 1. Executive result

The exact pretrained `rtmdet_nano_8xb32-300e_hand-267f9c8f` ONNX detector does **not** improve AppHear's direct hand perception enough to promote. On the frozen 150-frame, 41-signer, 184-visible-hand benchmark, RTMDet recalled `113/184 = 61.41%` hands versus MediaPipe's verified `122/184 = 66.30%`. Complete two-hand recall fell from `31/67 = 46.27%` to `25/67 = 37.31%`.

RTMDet supplied real complementary evidence: it detected 16 hands MediaPipe missed, including 15 blur-associated and five edge-clipped instances. That benefit was more than offset by 25 MediaPipe-hit/RTMDet-miss cases. RTMDet was worse on blur (`53.33%` versus `58.33%`), occlusion (`36.00%` versus `52.00%`), and two-hand instances (`58.96%` versus `64.93%`). It also merged two hands in `6/67 = 8.96%` two-hand frames.

The dedicated 613-frame N0 fixture cannot support a valid false-presence claim: a post-score visual audit found obvious visible hands in multiple rows frozen as human-reviewed no-hand frames. Those labels were not selectively changed after predictions. The raw `41/613` result is preserved but invalidated for gating. A separate trustworthy 33-frame zero-hand subset produced four false-presence frames (`12.12%`, 95% CI `4.82-27.33%`), but is below the required 200-frame denominator. This missing safety estimate does not make P0 inconclusive because the valid positive benchmark independently fails six promotion requirements.

Do not run P1, MobRecon, RTMPose landmarks, threshold tuning, Android integration, or RTMDet fine-tuning behind this detector.

## 2. Exact candidate and provenance

| Item | Frozen value |
|---|---|
| Model identity | `rtmdet_nano_8xb32-300e_hand-267f9c8f` |
| Origin | OpenMMLab MMPose/RTMPose hand deployment release; RTMDet detector architecture from MMDetection |
| Configuration | `projects/rtmpose/rtmdet/hand/rtmdet_nano_320-8xb32_hand.py` |
| Class | one class: `hand` |
| Input | `1x3x320x320`, FP32 |
| ONNX SHA-256 | `568d3ea97a5b142488366b67e036b6a5cb0a1fef9087a710cb8e66b6979fbac2` |
| ONNX size | `4,010,667` bytes (`3.83 MiB`) |
| Source ZIP SHA-256 | `9c0370a43c02b2fe42b4382aba7383d97cfa3ed35623b655cac4f0c25cfde402` |
| Source ZIP | `rtmdet_nano_8xb32-300e_hand-267f9c8f.zip`, `3,840,129` bytes |
| Runtime | ONNX Runtime `1.22.1`, `CPUExecutionProvider` |
| Operating threshold | `0.30`, rtmlib's documented/default detector threshold; no sweep |
| Export floor | score `0.05` baked into the end-to-end export |
| NMS | IoU `0.50` baked into the export; maximum 100 detections |
| Preprocessing | OpenCV BGR; aspect-preserving resize to 320; top-left placement; bottom/right pad 114; mean `[103.53,116.28,123.675]`; std `[57.375,57.12,58.395]`; NCHW FP32 |
| Output | `dets [1,N,5]` boxes/scores and `labels [1,N]`; no landmarks |
| Branch / HEAD | `codex/recognition-stable-ru-d10` / `7dd4fa05f2e7dffd3f06a2fdc88f90b1ea66836f` |
| Evaluator SHA-256 | `c1f47932a485f5d2b9a9a45263f34072a6aacc6678c142cfa6804f2296191e0c` |
| Runner SHA-256 | `9355dcbc30e7ca7094ee15a80cba5e958bd0c8f8beb53f69b5f572965acc555e` |
| Preregistered design SHA-256 | `880b46da12952f9249adfd222aeebc7718c8f2cb7b6b72792c7c9a138392ae92` |

The full pre-run working-tree status, environment versions, model/input/source hashes, and frozen manifest are recorded in `p0_provenance_manifest.json`. The first output directory, `p0_rtmdet_detector_01`, is a preserved failed evaluator attempt: scoring completed, but report construction referenced absent canonical subgroup keys. The defect was fixed and tested before the fresh, independently frozen `p0_rtmdet_detector_02` run; `_01` is not evidence.

### Public-source and license verification

- [rtmlib hand solution](https://github.com/Tau-J/rtmlib/blob/main/rtmlib/tools/solution/hand.py) identifies the 320 RTMDet-nano hand detector and the default `0.3` threshold.
- [MMPose RTMDet hand configuration](https://github.com/open-mmlab/mmpose/blob/main/projects/rtmpose/rtmdet/hand/rtmdet_nano_320-8xb32_hand.py) defines the nano width/depth multipliers, one hand class, 320 input, and the OneHand10K, FreiHAND, RHD, and Halpe hand training sources.
- [MMPose](https://github.com/open-mmlab/mmpose) and [rtmlib](https://github.com/Tau-J/rtmlib) code are Apache-2.0.
- The downloaded archive's `detail.json` identifies the original checkpoint as `rtmdet_nano_8xb32-300e_hand-267f9c8f.pth`, MMDetection 3.0, ONNX opset 11 FP32, score floor `0.05`, and NMS IoU `0.50`.

Code licensing is clear, but checkpoint redistribution/production rights are **not resolved** by an explicit weight license in the archive. Dataset terms are separate from code: FreiHAND's public terms restrict its data to research/non-commercial use, and the other constituent datasets also require an independent release review. Therefore this checkpoint remains a research artifact even if its quality had passed.

## 3. Frozen evidence and matching policy

### Positive benchmark

- 150 frozen frames
- 41 signers
- 184 human-visible hand instances
- 117 frames with at least one visible hand
- 67 two-hand frames
- Human hand-presence and boxes reused unchanged from `e2e_all_hand_gold_v1/engineering_01`
- No relabeling after RTMDet predictions

The verified MediaPipe baseline is:

| Metric | Count | Rate |
|---|---:|---:|
| Visible-hand instance recall | 122/184 | 66.30% |
| Any-hand frame coverage | 91/117 | 77.78% |
| Complete two-hand recall | 31/67 | 46.27% |

### Preregistered matching

A prediction is availability-eligible for a gold hand when its center lies inside the human box and at least 50% of the predicted-box area lies inside that gold box. Matching is exact, one-to-one, maximum-cardinality, with maximum summed IoU as the tie-break. IoU >=0.50 and >=0.75 are separate box diagnostics, not the primary availability definition.

An unmatched prediction that remains eligible for an already matched hand is a duplicate. A two-hand frame is merged when one prediction contains both gold centers or covers at least 50% of each gold-hand area.

No threshold optimization was performed because there was no proper frozen detector development split. Only the documented/default `0.30` operating point was scored.

## 4. Overall detector result

| Metric | MediaPipe | RTMDet | RTMDet 95% CI | Outcome |
|---|---:|---:|---:|---|
| Visible-hand instance recall | 122/184 = 66.30% | 113/184 = 61.41% | 54.21-68.15% | worse by 4.89 pp; gate fail |
| Any-hand frame coverage | 91/117 = 77.78% | 88/117 = 75.21% | 66.67-82.15% | worse by 2.56 pp |
| Complete two-hand recall | 31/67 = 46.27% | 25/67 = 37.31% | 26.72-49.28% | worse by 8.96 pp; gate fail |
| Availability matches | 122 | 113 | — | nine fewer direct observations |
| IoU >=0.50 box recall | 69/184 = 37.50% | 94/184 = 51.09% | 43.92-58.21% | better box overlap among located hands |
| IoU >=0.75 box recall | 6/184 = 3.26% | 16/184 = 8.70% | 5.42-13.66% | diagnostic only |

RTMDet made 129 predictions on the 150-frame positive set: 113 matched, seven were duplicates, and nine were unmatched false predictions. Positive-set hand-instance precision was `113/129 = 87.60%` (95% CI `80.80-92.22%`). Restricting to the 117 visible-hand frames gives `113/125 = 90.40%` (95% CI `83.97-94.42%`). These are positive-set diagnostics, not a substitute for a governed no-hand benchmark.

Matched IoU was median `0.627`, p95 `0.817`, minimum `0.260`, and maximum `0.896`.

## 5. Hard-condition subgroups

Condition labels overlap; counts must not be summed.

| Subgroup | Gold hands | MediaPipe recall | RTMDet recall (95% CI) | Delta |
|---|---:|---:|---:|---:|
| Ordinary/clear | 64 | 52/64 = 81.25% | 49/64 = 76.56% (64.87-85.25%) | -4.69 pp |
| Motion blur | 120 | 70/120 = 58.33% | 64/120 = 53.33% (44.44-62.02%) | -5.00 pp |
| Occlusion | 25 | 13/25 = 52.00% | 9/25 = 36.00% (20.25-55.48%) | -16.00 pp |
| Edge clipped | 31 | 8/31 = 25.81% | 13/31 = 41.94% (26.42-59.23%) | +16.13 pp |
| Partial visibility | 6 | 1/6 = 16.67% | 2/6 = 33.33% (9.68-70.00%) | +16.67 pp; very small n |
| Two-hand instances | 134 | 87/134 = 64.93% | 79/134 = 58.96% (50.49-66.92%) | -5.97 pp |

Complete two-hand recall was particularly weak in hard frames: blur `9/42 = 21.43%`, occlusion `2/12 = 16.67%`, edge-clipped `0/12`, and partial-visibility `0/3`. Contact/body-overlap truth is not present as a distinct label in this frozen gold set, so no contact-specific claim is made.

The 71 RTMDet misses overlap these conditions: blur 56, occlusion 16, edge clipping 18, partial visibility four, near-face one, and other six. A post-hoc scale diagnostic found `25/46 = 54.35%` recall in the smallest quartile of gold boxes versus `88/138 = 63.77%` for larger boxes. This was not a preregistered gate.

## 6. Pairwise complementary evidence

| Gold-hand outcome | Count | Percent of 184 |
|---|---:|---:|
| MediaPipe hit / RTMDet hit | 97 | 52.72% |
| MediaPipe hit / RTMDet miss | 25 | 13.59% |
| MediaPipe miss / RTMDet hit | 16 | 8.70% |
| Both miss | 46 | 25.00% |

RTMDet recovered `16/62 = 25.81%` of MediaPipe's missed hands, but lost 25 MediaPipe hits, a net loss of nine. The 16 complementary hits overlap motion blur 15, edge clipping five, partial visibility one, and occlusion one. This proves some new visual evidence, especially at frame edges, but not a superior standalone detector.

## 7. Duplicates, merges, and negative-set audit

- Duplicate predictions on positive frames: seven, occurring once each in `g014`, `g016`, `g027`, `g040`, `g059`, `g074`, and `g104`.
- Positive-only duplicate fraction: `7/129 = 5.43%`.
- Merged two-hand frames: `6/67 = 8.96%` (95% CI `4.17-18.19%`), in `g074`, `g088`, `g102`, `g114`, `g119`, and `g125`.

### Governed-negative defect

The frozen N0 fixture initially appeared to provide 613 reviewed negative frames from six participants, five devices, and five environments. Against its frozen labels, RTMDet produced 42 boxes in 41 frames (`6.69%` false-presence by label). Post-score failure-panel inspection exposed a truth defect: several scored “negative” frames visibly contain hands, including `n0_0146`, `n0_0150`, `n0_0151`, and `n0_0244`. Because the audit was prompted by model output, selectively relabeling only those cases would bias the benchmark.

Accordingly:

| Negative evidence | Raw result | Valid interpretation |
|---|---:|---|
| Dedicated N0 fixture | 41/613 = 6.69% | **Invalid for final safety claim**; human truth contaminated |
| Frozen positive-audit zero-hand subset | 4/33 = 12.12% (95% CI 4.82-27.33%) | Trustworthy but too small for required >=200 denominator |
| MediaPipe on same 33 frames | 0/33 | Verified local baseline only |

The raw pre-audit machine result is preserved as `p0_rtmdet_detector_result.pre_negative_truth_audit.json` with SHA-256 `ce7e0c84328b70d03633daab39a38213e29af5bc757c30933c91d712da0ae52e`; the final JSON contains the adjudication. `negative_truth_spotcheck.csv` records the observed conflicts. The negative safety gate is `NOT_VALIDLY_ESTIMATED_AT_REQUIRED_DENOMINATOR`.

## 8. Desktop diagnostic cost

Measured with ONNX Runtime CPU on the evaluation desktop after warm-up:

| Stage | Mean | p50 | p95 | Max |
|---|---:|---:|---:|---:|
| Preprocess | 1.67 ms | 1.63 ms | 2.03 ms | 2.46 ms |
| Detector | 5.72 ms | 5.33 ms | 6.84 ms | 7.84 ms |
| Postprocess/NMS output handling | 0.04 ms | 0.03 ms | 0.05 ms | 0.19 ms |
| Total | 7.42 ms | 7.02 ms | 8.83 ms | 10.34 ms |

The ONNX file is 3.83 MiB. These values demonstrate only inexpensive desktop execution. They do not establish Android latency, CameraX sustainability, memory/PSS, thermal stability, delegate portability, or phone observations per second.

## 9. Preregistered gates

| Hard requirement | Frozen threshold | Result | Pass? |
|---|---:|---:|---|
| Visible-hand recall | >=81% | 61.41% | NO |
| Complete two-hand recall | >=65% | 37.31% | NO |
| Blur improvement | >=+10 pp vs MediaPipe | -5.00 pp | NO |
| Occlusion improvement | >=+10 pp vs MediaPipe | -16.00 pp | NO |
| No-hand false-presence | <=3% on governed >=200 negatives | not validly estimated; trustworthy n=33 gives 12.12% | NO VALID PASS |
| Duplicate behavior | <=5% preregistered aggregate diagnostic | 4.09% in raw combined scorer; positive-only 5.43% | Technical raw pass; caution |
| Merged two-hand behavior | <=5% | 8.96% | NO |
| No hard subgroup >5 pp worse | >-5 pp required | occlusion -16.00; two-hand -5.97; blur exactly -5.00 | NO |

The machine scorer's raw aggregate duplicate denominator included the invalid N0 fixture. The positive-only value is therefore the safer diagnostic. It does not affect the decision.

## 10. Decision and next step

**Final decision: `REJECT_RTMDET_P0`.**

`INCONCLUSIVE_P0` is not appropriate. The dedicated negative fixture is defective, but the frozen positive benchmark remains valid and independently shows worse overall recall, worse complete two-hand recall, worse blur and occlusion performance, excessive merges, and hard-subgroup regression. A repaired negative benchmark could add safety knowledge but cannot turn these positive-quality failures into a pass.

Do not proceed to P1 oracle-box landmark comparison behind this detector. Do not attach MobRecon or RTMPose, threshold-tune, fine-tune RTMDet, or integrate it into Android.

The smallest scientifically justified next action is:

1. Rebuild a blinded, human-governed >=200-frame negative set without consulting RTMDet predictions, preserving signer/session/device separation and explicit visible-hand truth.
2. If replacement work continues, preregister and evaluate **one materially different off-the-shelf full-frame hand-detector family** on the same unchanged positive benchmark plus the repaired negative set.
3. Consider detector fine-tuning only after an off-the-shelf candidate demonstrates useful complementary localization with a correctable domain gap. This RTMDet result alone does not justify immediate fine-tuning.

P1 remains unauthorized and must not start automatically.

## 11. Artifact index

Canonical result directory: `artifacts/recognition_upgrade/perception_backend_replacement/p0_rtmdet_detector_02/`

- `p0_rtmdet_detector_result.json` — final machine-readable metrics and adjudication
- `p0_provenance_manifest.json` — branch, HEAD, environment, hashes, frozen inputs
- `p0_preregistered_design.json` — matching policy, operating point, gates
- `p0_input_manifest.csv` — scored-frame provenance
- `raw_detections.csv` — all raw scored boxes
- `paired_mediapipe_vs_rtmdet.csv` — every gold-hand pairwise outcome
- `subgroup_table.csv` — hard-condition results
- `negative_set_safety_table.csv` — raw negative-fixture output, now invalid for final safety inference
- `negative_truth_spotcheck.csv` — observed label conflicts requiring blinded re-adjudication
- `frame_safety_and_merge_table.csv` — frame-level duplicate/merge state
- `failure_panel_index.csv` and `failure_panels/` — complementary hits, misses, duplicates/merges, and negative-fixture audit sheets
- `p0_check_summary.json` — structural validation

No production code, feature schema, MediaPipe settings, recognition model, classifier, or Android runtime was changed by P0.
