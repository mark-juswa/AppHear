# Perception Negative Evidence Audit

**Status:** complete  
**Decision:** `NEW_NEGATIVE_ANNOTATION_REQUIRED`  
**Date:** 2026-08-21  
**Scope:** existing-evidence inventory and validation only; no detector execution, new annotation, training, or Android change

## 1. Executive conclusion

AppHear has more than enough existing RGB material to construct a 200-frame detector-negative benchmark without recording anything new, but it does **not** already have 200 trustworthy zero-visible-hand labels.

The only currently admissible source is the corrected all-hand gold package:

```text
TRUSTWORTHY_ZERO_HAND_EXISTING = 33
TARGET_ZERO_HAND = 200
NEW_ANNOTATIONS_REQUIRED = 200 - 33 = 167
```

Those 33 frames are one frame per clip, cover 33 clips and 27 signers, contain no exact duplicates, and contain no dHash near-duplicate pair at Hamming distance <=4. They overlap the frozen P0 150-frame package by design but overlap none of its 117 visible-hand frames and none of its visible-hand source clips.

The former 613-frame N0 denominator cannot be salvaged by trusting its old labels. The original review was nominally direct human frame review under the correct “no visible hand pixel” rule, but P0 inspection proved that obvious lap-, edge-, and motion-visible hands were repeatedly marked as zero. Similar contradictions appear in P1 exclusion rows, C0B zero-box rows, and A2 no-hand/rest rows. A direct-human-review origin is necessary but not sufficient when the resulting labels visibly contradict the required semantics.

No new capture is required. The exact deficit is 167 human-reviewed frames, preferably obtained by a blinded re-adjudication of existing N0 RGB. To allow exclusions while preserving diversity, review approximately 220-250 existing N0 candidates and stop only when 167 additional `ZERO_HAND` frames pass. Do not use RTMDet output to select or label them.

## 2. Required semantics

This audit applies the requested classes literally:

| Class | Audit meaning | Detector-negative eligible? |
|---|---|---|
| `ZERO_HAND` | No human hand pixels are visibly present anywhere, including fingertips, blurred hands, lap hands, and edge-clipped hands. | Yes |
| `VISIBLE_IDLE_HAND` | At least one hand is visible outside active signing. | No; it is a true detector positive |
| `VISIBLE_SIGNING_HAND` | At least one hand is visible during active signing. | No |
| `TRANSITION` | Entry, exit, or ambiguous movement between states. | No |
| `UNCERTAIN` | Visibility cannot be decided confidently or existing truth is contradicted. | No |

MediaPipe absence, RTMDet absence, a `NO_SIGN` recognition label, an out-of-span timestamp, a filename, or a recording instruction is never zero-hand truth.

## 3. Trust hierarchy

| Level | Evidence | Admission rule |
|---:|---|---|
| 1 | Direct human review of the exact RGB frame | Eligible only if the annotation semantics match strict `ZERO_HAND` and the source has no unresolved contradiction. |
| 2 | Human sequence/span annotation | Eligible only when it explicitly establishes that no hand is visible at the exact selected frame; “rest” or “outside sign span” alone is insufficient. |
| 3 | Inferred metadata or capture instruction | Not eligible without frame review. |
| 4 | Model output or model absence | Never ground truth. |
| 5 | Filename/category assumption | Never ground truth. |

The key audit finding is that several Level-1 files fail the second part of the admission rule. They retain historical value as candidate pools, but cannot be frozen as a safety denominator until blind human re-adjudication.

## 4. Complete source inventory

| Source | Original meaning and evidence | Raw semantic counts | Trust / validation finding | Salvageable `ZERO_HAND` now |
|---|---|---:|---|---:|
| `e2e_all_hand_gold_v1/engineering_01` | Exact-frame, human box/presence review; one unbiased frame from each of 150 ASL Citizen clips. | 33 zero, 117 visible signing | Level 1; corrected canonical package. No observed duplicate or provenance defect. | **33** |
| `e2e_c0/n0_capture_06` | Exact-frame human review intended to enforce no visible hand pixels at 1 FPS. | Original: 613 zero-eligible, 16 visible contamination, 1 quarantine. | Level 1 origin, but validation failed: obvious hands occur in former zero rows. Exact zero count is unknown without re-review. | **0** |
| `n0_capture_01/02/03/05` | Earlier templates/runs and the 600-row predecessor carried into `_06`. | `_05`: 584 zero + 16 visible; `_01-03` incomplete. | Superseded/overlapping, not new evidence. | 0 |
| `p1_capture_03` | Exact-frame review of visible ordinary/non-sign hands. Zero rows were exclusions, not the intended fixture. | 108 visible idle; 32 zero-labeled exclusions. | Level 1 origin. Contact-sheet validation shows hands/arms at lap or edge in multiple zero rows. | 0 |
| `hello_like_p1_capture_01` / E4-AG | Exact-frame P1-style review. | 116 visible idle; 44 zero-labeled exclusions. | Raw videos are byte-identical aliases of canonical P1; stale P03/P04 aliases are really P02/P01. Eight zero-labeled frames exactly duplicate P1-zero rows. Zero labels show the same semantic defect. | 0 |
| C0B annotation smoke 03 | Exact-frame human boxes on 24 unique-video frames. | 19 visible; 5 zero-labeled. | Level 1 origin; visual audit finds edge/lap ambiguity. Not part of the final Stage-2 400. | 0 |
| C0B 300-frame pilot + 100-frame top-up | Exact-frame human boxes; became the 400-row detector Stage-2 source. | 333 visible; 67 zero-labeled (`53` train, `14` development). | Level 1 origin, 72 unique candidate videos including smoke. Multiple zero-box rows visibly contain blurred/edge hands. These rows were also used by the old detector branch. | 0 |
| Phase-2 ROI audit 02 | Exact-frame human box review over 120 frames. | 116 visible; 4 zero-labeled. | Level 1 origin; small source with train/validation lineage and no independent zero-hand validation. | 0 |
| A1 no-sign benchmark 01/02 | Four instructed stationary/no-hands phone runs; performance logs only. | No RGB frame truth. | Level 3 instruction plus model logs. No image denominator exists. | 0 |
| A1 signing sentinel | Human onset/release and performance-valid spans for 24 attempts; notes say rest before/after. | 24 sequences; no exact-frame zero labels in this artifact. | Level 2, but “rest” does not mean hands are outside the image. Only selected A2 frames received later frame review. | 0 |
| A2 reviewed sequences | Direct review of 551 selected frames from 12 A1 and 9 RU-D9 attempts. | Derived requested classes: 268 zero/rest candidates, 196 visible signing, 2 visible idle, 48 transition, 37 uncertain. | Level 1 origin. Forty-four zero/rest candidates are inside the human sign span, and contact sheets show visible/blurred/edge-hand contradictions. High temporal correlation and one phone signer/device. | 0 |
| RU-D1/RU-D2/RU-D7 reviewed phone attempts | Human performance-valid and onset/release spans with visual notes. | Attempt/span evidence, not frame-level zero truth. | Level 2. Outside-span frames may contain idle hands or transitions. Nine RU-D7 attempts are already represented in A2. | 0 |
| RU-D8/RU-D9 perception evidence | Human attribution/contact/crossing decisions over retained attempts. | Failure-cause labels, not zero-hand boxes. | Level 2 for failure causes; cannot infer strict zero visibility. | 0 |
| E4-Y / E4-AA no-sign feature sets | Schema-v3 feature windows derived from N0/P1 capture. | E4-AA: 180 N0 + 108 P1 windows. | Reuse of the same disputed N0/P1 lineage; feature/model labels are not new RGB truth. | 0 |
| E4-AG / E6 negative reuse | Reuse audit over canonical P1 and its alias. | 197 unique visible idle/face-adjacent windows. | Human-reviewed visible hands; explicitly not zero-hand negatives. | 0 |
| E6 existing OOV source search | Existing ASL Citizen signing clips outside the product vocabulary. | 200 OOV videos. | Visible signing/no-sign-recognition evidence, not hand absence. | 0 |
| E6 fresh negative recordings | Recorder-produced no-sign-context videos from one signer. | 560 videos: 320 OOV, 60 idle hands, 60 face-adjacent, 60 accidental motion, 60 transitions. A 54-video human review sample had `hand_visible=yes` for all 54. | Level 2 sequence labels; intentionally contains visible hands/signing. | 0 |
| E6 product-core reviews | Human video-level sign-quality review. | 486 reviewed videos; 9 have `hand_visible=no`. | Video-level positive-data review, not exact-frame zero truth; no usable frame indices. | 0 |
| Recorder raw N0 material | The 57 original N0 videos remain available with participant/device/environment folders. | 57 clips, 876.3 s. | This is the source of `n0_capture_06`, not independent evidence. Excellent re-review pool. | 0 |
| HaGRID smoke and custom MobileNet negative tests | Detector-development evaluation rows. | HaGRID used 20 N0 negatives; MobileNet Stage 2 used 67 C0B no-hand rows. | Subsets/reuse of the disputed sources above; model results add no truth. | 0 |

No other independent frame manifest with explicit, reliable zero-visible-hand human truth was found. Filename-only “negative”, “no_sign”, “idle”, “rest”, and rejection-training assets were excluded unless their review schema established exact visual hand absence.

## 5. Audit of the 613-frame fixture

### 5.1 Why it was called negative

The runbook definition was correct: an N0 frame was valid only when no visible hand pixel or fingertip appeared. The source recordings were intended to keep hands below/outside the camera, while including people, arms, faces, hair, sleeves, rooms, clutter, movement, and hand-like objects. The GUI asked a human to choose `NO HANDS`, one hand, two hands, or quarantine for every center frame.

The final `_06` package sampled 630 frames at 1 FPS from 57 clips and reported:

- 613 eligible zero-hand frames;
- 16 visible-hand contamination frames;
- one quarantined frame;
- six participants;
- five devices;
- five environments;
- front camera only.

All original center images, context panels, source paths, timestamps, clip IDs, and participant/device/environment metadata remain available. The package is therefore repairable.

### 5.2 What failed

P0's failure-panel audit found obvious visible hands in rows frozen as zero, including:

- `n0_0146`
- `n0_0150`
- `n0_0151`
- `n0_0244`

The first three come from `n0_p02_04`; the fourth comes from `n0_p03_01`. Broader sheet inspection shows the failure mode is not a filename error: lap hands, hands entering at the lower edge, crossed arms with hands visible, and moving hands were often treated as absent. RTMDet-selected panels cannot be used to relabel the remaining rows, but they validly disprove the blanket 613-zero claim.

### 5.3 Corrected conservative counts

Without a new blinded human pass, the only defensible corrected accounting is:

| Class/status | Count | Basis |
|---|---:|---|
| `VISIBLE_IDLE_HAND` confirmed | **at least 20** | 16 originally human-marked contamination + four directly inspected former-zero conflicts |
| `ZERO_HAND` admissible now | **0** | Source-wide zero-label reliability is disproved |
| `UNCERTAIN / RE-ADJUDICATION REQUIRED` | **610** | 609 remaining former-zero rows + one original quarantine |
| Total | 630 | Complete fixture |

This is a trust-status correction, not a claim that all 610 uncertain rows contain hands. Many are likely genuine zero-hand frames. Their exact semantic count cannot be known without reviewing them under the strict five-class scheme. Selectively correcting only model-flagged frames would bias the future benchmark.

### 5.4 Salvage plan

Preserve the original files and hashes. Create a new review result only after approval, using the existing RGB and metadata. Selection must be based on clip, participant, device, environment, and timestamp—not RTMDet scores or P0 false-positive status. The reviewer must see the full frame at sufficient resolution and treat any lap, blurred, crossed-arm, or edge hand pixel as visible.

## 6. Candidate counts, deduplication, and concentration

Historical files contain 1,066 rows carrying a zero/no-hand candidate label:

| Candidate source | Raw rows |
|---|---:|
| N0 `_06` former zero rows | 613 |
| Corrected all-hand gold | 33 |
| C0B smoke/pilot/top-up | 72 |
| P1 final + hello-like alias zero exclusions | 76 |
| Phase-2 ROI zero rows | 4 |
| A2 no-hand/rest, non-leaving rows | 268 |
| **Total** | **1,066** |

Exact image hashing found 1,050 unique images and 16 duplicate rows:

- eight exact duplicate pairs inside N0;
- eight exact duplicate pairs between P1 and the hello-like alias.

A2's 268 candidates are sampled at roughly 0.18-0.25-second cadence. A deterministic greedy minimum spacing of one second reduces them to 80 frames across 21 attempts. Applying that spacing after exact deduplication gives a first-pass historical candidate pool of 862 frames. This is **not** a benchmark: most of it remains semantically disputed, and N0/P1/A2 still contain many visually near-identical static frames.

For the only trustworthy source:

- raw candidates: 33;
- exact-hash unique: 33;
- dHash unique: 33;
- minimum pairwise dHash Hamming distance: 7;
- pairs at Hamming distance <=4: 0;
- unique clips: 33;
- unique signers: 27;
- maximum frames per clip: 1;
- split lineage: 26 ASL Citizen train, 7 ASL Citizen validation, 0 test;
- device/environment metadata: unavailable in the ASL Citizen manifest.

### Concentration findings

- N0: 57 clips, six participants, five devices, five environments, but repeated 1 FPS samples and front camera only.
- C0B zero candidates: 72 unique videos, 30 signer IDs, 57 ASL Citizen and 15 local; 57 train, 15 unassigned. These are diverse but semantically contradicted and were used by the old detector branch.
- P1/hello zero candidates: 68 exact-unique frames from 12 canonical clips, only two actual participants, two devices, one indoor environment. E4-AG does not add signers.
- A2 candidates: 21 attempts, one phone signer, one Xiaomi M2101K7AG, two experiment sessions; even the 80 spaced frames are highly concentrated.
- Corrected gold: 33 clips and 27 signers, but ASL Citizen train/validation webcam lineage and no phone/device labels.

## 7. Leakage and benchmark overlap

- The 33 trusted zeros are the zero-hand slice of the already frozen 150-frame P0 all-hand package. This is intentional reuse, not hidden leakage.
- They have zero frame or clip overlap with the 117 visible-hand rows because the original selection used one frame per unique clip.
- They include 26 ASL Citizen training and seven validation clips; no ASL Citizen test clip is included. A future perception model must not train or tune on these 33 frames.
- C0B's 67 Stage-2 zero candidates were part of the old MobileNet detector train/development package. They must not be presented as independent evidence for that historical model.
- P1 and E4-AG are aliases of the same 30 raw videos. Treating P03/P04 as new signers would be false diversity.
- E4/E6 no-sign windows and HaGRID/custom-detector negatives reuse N0/P1/C0B lineages and add no independent images.
- The 560 fresh negative-context videos are protected evaluation lineage and contain visible hands/signing by design; they cannot become zero-hand data through `NO_SIGN` labeling.

## 8. Required annotation deficit and proposed benchmark

### Current trustworthy total

```text
TRUSTWORTHY_ZERO_HAND_EXISTING = 33
TRUSTWORTHY_ZERO_HAND_DEDUPLICATED = 33
NEW_ANNOTATIONS_REQUIRED_FOR_200 = 167
NEW_ANNOTATIONS_REQUIRED_FOR_300 = 267
NEW_ANNOTATIONS_REQUIRED_FOR_500 = 467
```

### Proposed 200-frame frozen composition

| Component | Frames | Rule |
|---|---:|---|
| Corrected all-hand gold zeros | 33 | Reuse unchanged; never tune on them. |
| Re-adjudicated existing N0 frames | 167 | New blind human labels from existing RGB; at least 50 of 57 clips, preferably all available participant/device/environment cells; normally <=3 accepted frames per clip, with a fourth only to fill a documented shortfall. |
| **Total** | **200** | Only exact `ZERO_HAND` labels enter. |

Review approximately 220-250 preselected N0 candidates to allow `VISIBLE_IDLE_HAND`, `TRANSITION`, and `UNCERTAIN` exclusions, then stop once 167 new accepted, deduplicated zeros satisfy the composition rule. This is a recommendation only; no frames were selected or annotated by this audit.

If N0 yield or diversity is inadequate, the next review priority is the 72 C0B unique-video zero candidates because they add 30 signer IDs. The A2 pool is last priority because it is one signer/device and temporally redundant. Do not count old zero labels from either source without re-adjudication.

No new video recording is currently justified. Existing source RGB is sufficient for the required annotation work.

## 9. Frozen P0 diagnostic subsets

Canonical source:

`artifacts/recognition_upgrade/perception_backend_replacement/p0_rtmdet_detector_02/paired_mediapipe_vs_rtmdet.csv`

Source SHA-256:

`A416B35D985AB2B9237EE6056E080CD71089978D6CB0812A3F5A5B0FF75D4290`

The subsets are gold-hand instances keyed by `(sample_id, gold_index)`, not merely unique frames. Human truth is unchanged.

| Frozen subset | Pairwise filter | Instances | Unique frames | Canonical selection SHA-256 |
|---|---|---:|---:|---|
| `RTMDET_COMPLEMENTARY_16` | `MP_MISS_RTMDET_HIT` | **16** | 15 | `98968C14EE90DA063035F6D2B898D71520BD7794031B302DCA750D077F2E91E4` |
| `RTMDET_REGRESSION_25` | `MP_HIT_RTMDET_MISS` | **25** | 21 | `3386A6EAA946C330ED93757ABA15F1540C88DFF36D5FFF7404482C42330A74AD` |
| `PERCEPTION_HARD_CORE_46` | `BOTH_MISS` | **46** | 41 | `195C2C282887363CC4B04B03BE3C925F6AC6D627937A44792D37E4C0C90B9978` |

Each selection hash is SHA-256 over UTF-8 lines sorted by `sample_id` then numeric `gold_index`, formatted as `sample_id,gold_index\n`. These definitions permit exact regeneration without copying or modifying the underlying human boxes.

## 10. Final decision

**`NEW_NEGATIVE_ANNOTATION_REQUIRED`**

- Existing trustworthy, deduplicated zero-hand frames: **33**.
- Exact deficit to the 200-frame minimum: **167**.
- Existing RGB sufficient for the work: **yes**.
- New recording required: **no**.
- Blind human re-adjudication of existing frames required: **yes**.

STOP here. No new detector, annotation session, training run, or Android change is authorized by this audit.
