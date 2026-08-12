# Target Architecture

**Purpose:** Define the proposed hybrid system and its ownership boundaries.
**Scope:** Isolated recognition first, later continuous gloss recognition.
**Status:** PROPOSED; components require experiment gates. **Last updated:** 2026-07-25.

## Pipeline

`CameraX frame + monotonic timestamp`
`-> orientation/camera normalization`
`-> MediaPipe tracked hands/pose + ROI tracker`
`-> synchronized landmark packet and RGB hand crops`
`-> landmark graph encoder + shared hand-appearance encoder`
`-> mask-aware causal temporal fusion`
`-> boundary-state, gloss, and unknown outputs`
`-> held-out calibrated acceptance`
`-> current gloss/sentence UI`

## Component Contract

| Component | Input -> output | Recommended model/location | Cost target | Expected contribution | Main risk |
|---|---|---|---|---|---|
| Frame envelope | CameraX frame -> upright analysis image, `timestamp_us`, camera metadata | Android S0 | <8 ms p95 excluding camera | Removes frame-count timing ambiguity | conversion copies |
| Tracker/ROI | frame -> hands/pose, scores, boxes, masks | MediaPipe VIDEO or LIVE_STREAM only after E4; Android | <45 ms hand+pose amortized | Lower detector cost; stable crops | landmark dialect drift |
| Structured features | landmarks/timestamps -> graph tensors | shared Python/Kotlin schema | <2 ms | geometry, motion, missingness | parity complexity |
| Hand crops | frame + tracked boxes -> two 96x96 RGB crops + quality | Android/offline identical geometry | <4 ms crop work | finger/occlusion/handshape evidence | crop misses/blur |
| Landmark encoder | graph sequence -> 128-D/frame | slim region-aware ST-GCN or graph-temporal conv, 0.5-1.5M params | <8 ms/tick INT8 | anatomical and relational prior | failed prior GCN formulation |
| RGB encoder | left/right crops -> 96-128-D/frame/hand | shared MobileNetV3-Small 0.35-0.5x; alternative EfficientNet-Lite0 | <15 ms at selected cadence | recovers visual detail lost by landmarks | overfit/background |
| Fusion | embeddings + masks + time deltas -> 128-D temporal state | 2-4 block causal depthwise TCN first; small causal transformer alternative | <8 ms | cross-modal complementarity | synchronization |
| Heads | state -> boundary 4-way, gloss C-way, unknown score | multitask dense heads | <2 ms | learned segmentation/rejection | labels/calibration |
| Acceptance | calibrated outputs/history -> commit/reject | validation-fitted policy | <1 ms | controls false commits | distribution shift |

Total target for a mid-range device is 12-20 processed FPS, p95 processing below 80 ms, model assets
8-20 MB INT8, and p95 commit latency below 750 ms once sufficient sign evidence exists. These are
gates, not current measurements.

## Stream Details

- **Landmarks:** both hands, upper-body pose, confidence/presence, missing mask, hand-local and
  body-relative coordinates, `dt`, velocities, accelerations, bones, selected angles, hand-hand and
  hand-body distances. Face is not enabled by default.
- **RGB:** independent left/right crops from the original upright frame. Use one shared encoder with
  a hand-side embedding after handedness canonicalization. Full-frame RGB is an offline ceiling, not
  the default mobile path.
- **Non-manual:** add only after vocabulary confusion analysis proves need. Start with sparse
  head/torso geometry already in pose. A low-cadence face or mouth/eyebrow crop is E6, not Phase 1.
- **Fusion:** intermediate gated fusion is primary: project each modality, apply quality masks,
  concatenate with time encoding, then causal temporal model. Late-logit fusion is the diagnostic
  fallback; early raw fusion is rejected because it entangles missingness and scale.

## Temporal Behavior

Use a bounded 2-second ring buffer with timestamps, variable valid length, and masks. Emit per
processed frame. Train on full signs, prefixes, partial negatives, variable FPS, jitter, and dropped
modality. The isolated head commits once per learned bout. The later continuous version replaces
the isolated gloss head with CTC while retaining the encoder and boundary auxiliary head.

## Research Basis

- ST-GCN supplies a graph prior for skeleton dynamics:
  https://ojs.aaai.org/index.php/aaai/article/view/12328
- ASL Citizen reports signer-independent isolated baselines:
  https://proceedings.neurips.cc/paper_files/paper/2023/hash/f29cf8f8b4996a4a453ef366cf496354-Abstract-Datasets_and_Benchmarks.html
- Pose-guided RGB improves word-level recognition:
  https://openaccess.thecvf.com/content/WACV2021/html/Hosain_Hand_Pose_Guided_3D_Pooling_for_Word-Level_Sign_Language_Recognition_WACV_2021_paper.html
- Multi-stream local image + skeleton evidence:
  https://arxiv.org/abs/2106.15989
- MobileNetV3 is hardware-aware for phone CPUs:
  https://openaccess.thecvf.com/content_ICCV_2019/html/Howard_Searching_for_MobileNetV3_ICCV_2019_paper.html
- MoViNet supports bounded-memory streaming video, retained as an RGB temporal alternative:
  https://research.google/pubs/movinets-mobile-video-networks-for-efficient-video-recognition/

## Decisions, Assumptions, Risks, Unknowns, Next Action

- **Decision:** hybrid, intermediate mask-aware fusion, causal online behavior, no depth requirement.
- **Alternative:** landmark-only if RGB fails E3 cost/accuracy gates; RGB-only is a ceiling model.
- **Assumption:** 96x96 crops preserve discriminative handshape; E2/E3 must test 80/96/112.
- **Risk:** tracker throughput plus RGB encoder exceeds thermal budget.
- **Unknown:** optimal RGB cadence and whether selective face cues are worth their cost.
- **Next action:** do not build this graph until E2e-C0 passes ROI reliability and E3 proves hybrid value.


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-016 apply; component-specific decisions in this document apply only after their experiment gate passes.
- **Assumptions:** Any forecast or unmeasured dimension remains a hypothesis, not a project fact.
- **Open questions:** Unresolved items are tracked in this document and `OPEN_QUESTIONS.md`.
- **Risks:** Applicable failure modes and fallbacks are tracked in this document and `RISK_REGISTER.md`.
- **Next required action:** Follow the explicit next action above and the ordering in `EXPERIMENT_MATRIX.md`; do not skip gates.

## Dynamic Mixed Revision - 2026-07-31

The current target architecture is revised from "hybrid recognizer everywhere" to **landmark-primary dynamic mixed recognition**.

Revised runtime shape:

```text
CameraX frame + timestamp
  -> MediaPipe hand/pose landmarks
  -> v3.0 [96,258] feature builder
  -> primary landmark recognizer
  -> calibration + temporal stability
  -> confusion registry/router
      -> stable-sign commit
      -> specialist resolver for registered hard group
      -> reject/unknown
  -> final acceptance policy
  -> existing sentence/UI
```

### What Changed

- The primary path remains the existing landmark pipeline shape because E4-N passed on a bounded stable set.
- RGB/visual evidence is no longer planned as an always-on global stream for the next milestone because E3-B0/E3-B1/E3-B2/E3-C did not validate broad RGB or naive fusion.
- Specialist RGB or hybrid evidence is still part of the roadmap, but only for registered hard groups such as `SORRY/BECOME/HELP` after the primary recognizer and router are defined.
- The confusion router becomes a first-class architectural component, not ad hoc confirmation logic.
- Rejection is a valid output. For silent translation, a missing translation is safer than confidently committing a wrong sign.

### Current Stable And Hard Groups

Provisional stable path candidates from completed evidence:

- `GOOD`
- `HELLO`
- `HAVE`
- `KNOW`

Research/unstable groups:

- `SORRY/BECOME/HELP`: active confusion group; E4-Q landmark-only resolver failed.
- `GOOD/MAKE/GET`: collapse group; `MAKE` and `GET` are deferred.
- `BYE/NO/YES`: hard local separability group; deferred.
- `THANKYOU`: label/variant cleanup group.

### Implementation Boundary

No Android implementation is authorized by this revision. The next work is offline: stable-candidate tiering, primary landmark model package, router simulation, then a specialist resolver experiment only after the primary path is clean.

### Related Decisions

ADR-RU-028 through ADR-RU-034 in `ARCHITECTURE_DECISIONS.md` supersede the earlier assumption that the next milestone should pursue a full global hybrid recognizer. ADR-RU-002 remains a long-term research direction, but not the immediate production architecture.

## Post-E6 Architecture Status - 2026-08-09

The dynamic mixed E6 component stack did not pass: E6-2, E6-3, and E6-5 are no-go, so E6-6 and
E6-7 are blocked. The provisional list above is historical and must not be interpreted as a
production-ready vocabulary; `KNOW` is deferred by E6-5.

The global hybrid target remains a research architecture, not an implementation authorization.
Its next unresolved prerequisite is reliable detector-derived hand ROI. MediaPipe remains the
landmark source but cannot remain the sole RGB crop provider. The single selected next experiment
is defined in `C0B_APPHEAR_HAND_ROI_FEASIBILITY_PLAN.md`; no RGB sign encoder or fusion model may be
prepared until its ROI gate passes.

The C0-B0 Linux/Python 3.10 wiring smoke now passes one-epoch training, TFLite export, MediaPipe
reload, and CPU inference. This removes toolchain feasibility as the immediate blocker but does not
validate ROI accuracy. Condition-balanced training/development annotations, frozen-fixture scoring,
INT8 behavior, and Android cost remain prerequisites before the target architecture can consume
detector-derived crops.
