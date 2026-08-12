# Model Research Plan

**Purpose:** Select encoders by AppHear evidence, not model fashion.
**Status:** PLANNED. **Last updated:** 2026-07-25.

## Verified Baselines

- Current 169K causal TCN: full-vocabulary top-1 0.314; selected 236 local candidate 0.617 mean,
  0.571 last, k8 0.529.
- Published ASL Citizen signer-independent baselines: landmark ST-GCN 59.5%, RGB I3D about 63%.
- AppHear slim/early-stride GCN run: 0.1588 top-1. It fails and must not be deployed.
- `model/config/train_streaming_conversational_gcn.yaml` now describes a full-capacity fair run,
  but no `gcn_conversational_full_v30` artifact exists.

## Candidate Order

1. **E1 graph sanity/fairness:** full-capacity ST-GCN on the exact TCN split/data, plus a small
   50-class overfit/sanity slice. Stop if it cannot overfit the slice or beat the failed run.
2. **Landmark candidate:** slim region-aware graph-temporal encoder with joint/bone/motion ablations.
3. **RGB candidate:** shared MobileNetV3-Small per hand; temporal depthwise TCN. EfficientNet-Lite0
   and MoViNet-A0-stream are alternatives only if measured.
4. **Hybrid candidate:** intermediate gated fusion plus causal TCN. A 2-4 layer, width-128 causal
   transformer is the competitor, not the default.
5. **Offline ceilings:** full-frame/upper-body RGB and larger models establish information ceiling;
   they are not Android promises.

CNN-LSTM/BiLSTM is retained only as a reproducibility baseline. Video transformers are deferred
because data and compute requirements are mismatched to the first Android target.

## Training

Use three seeds; signer-disjoint fixed splits; class-balanced sampling without contaminating
validation; full clips plus 30-100% prefixes; temporal subsampling/jitter; modality/landmark dropout;
crop, color, blur, compression, rotation, scale, and shear augmentation. Pretrain RGB on
provenance-compatible public sign video or general images, then fine-tune. Optimize gloss CE +
boundary focal/CE + optional metric loss for registered confusion groups. Report each term.

## Evidence

- ST-GCN: https://ojs.aaai.org/index.php/aaai/article/view/12328
- ASL Citizen: https://proceedings.neurips.cc/paper_files/paper/2023/hash/f29cf8f8b4996a4a453ef366cf496354-Abstract-Datasets_and_Benchmarks.html
- Hand-pose-guided RGB: https://openaccess.thecvf.com/content/WACV2021/html/Hosain_Hand_Pose_Guided_3D_Pooling_for_Word-Level_Sign_Language_Recognition_WACV_2021_paper.html
- Multi-stream local/skeleton: https://arxiv.org/abs/2106.15989
- MobileNetV3: https://openaccess.thecvf.com/content_ICCV_2019/html/Howard_Searching_for_MobileNetV3_ICCV_2019_paper.html

## Decisions, Assumptions, Risks, Unknowns, Next Action

- **Decision:** no model advances on aggregate top-1 alone; low-FPS, class, calibration, and device
  gates all apply.
- **Assumption:** full-capacity GCN failure diagnosis is affordable before crop pipeline work.
- **Risk:** prior graph implementation/training target is flawed, making paper comparison misleading.
- **Open question:** clip-level versus per-frame supervision for the graph candidate.
- **Next action:** E1 with explicit sanity checks and a kill gate.


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-016 apply; component-specific decisions in this document apply only after their experiment gate passes.
- **Assumptions:** Any forecast or unmeasured dimension remains a hypothesis, not a project fact.
- **Open questions:** Unresolved items are tracked in this document and `OPEN_QUESTIONS.md`.
- **Risks:** Applicable failure modes and fallbacks are tracked in this document and `RISK_REGISTER.md`.
- **Next required action:** Follow the explicit next action above and the ordering in `EXPERIMENT_MATRIX.md`; do not skip gates.
## E1 Execution Status - 2026-07-25

- E0 frozen from the existing same-data TCN artifact: SHA-256
  `6FA2875EE665E78A53E356B0ACC2B48A2423CDA8C61FAC5BED8FFB36CCDFA186`; held-out
  11-signer top-1 `0.5271`, top-5 `0.8252`, post-calibration ECE `0.03725`.
- The failed legacy GCN used a 75-node adjacency with 24 isolated pose nodes, encoded padded zero
  frames as 42 always-present hands, and globally pooled padding. Its final train accuracy was only
  `0.3255`; its `0.1588` test top-1 is therefore an invalid architecture-ceiling conclusion.
- The corrected E1 candidate keeps legacy behavior as the default and opts in to official MediaPipe
  pose connections, inferred per-hand presence, and padded-frame-masked pooling.
- Deterministic sanity slice: 50 classes x 5 clips, 30 train signers, 250 clips, max T=32,
  SHA-256 `ef624b85e55850b22aef55423d69119df7977b9e732f8892e7a2cec89ea69fc4`.
- **Sanity gate PASS:** full 2,703,276-parameter corrected GCN reached `0.9520` train accuracy at
  epoch 21 (seed `240725`, Adam `0.003`, no augmentation/dropout in the capacity test).
- The production `[96,258]` contract, Android recognizer, and deployed model assets were untouched.
- The full matched three-seed run is still pending. Native Windows TensorFlow reports no GPU; the
  historical full graph estimate is about 46.6 minutes/epoch on CPU, so this run requires an
  approved GPU/WSL2/cloud training environment rather than an unattended multi-day local run.
- Official topology source: https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/PoseLandmarksConnections
### E1 Corrected Sanity Result - 2026-07-25

- Developer-run corrected sanity gate: **PASS**.
- Command used: `python -m model.experiments.e1_graph_sanity --architecture gcn-full-masked --max-time 32 --epochs 30 --batch-size 25 --learning-rate 0.003`.
- Deterministic slice: 50 classes x 5 clips, 30 training signers, schema 3.0, selected tensor
  digest `ef624b85e55850b22aef55423d69119df7977b9e732f8892e7a2cec89ea69fc4`.
- Result: best/final train accuracy `0.9720`; target `0.95`; stopped at epoch 20; elapsed
  `398.32 s`; artifact SHA-256
  `2D75971311D59B20D077A27F791B8B1ED2551A27007A6DE2792785448EE86AF5`.
- Interpretation: corrected full GCN has sufficient capacity and the augmentation-mask fix did not
  regress the sanity path. This is diagnostic training accuracy, not held-out or end-to-end
  recognition accuracy.
- Next: prepare, review, and smoke-test seed-isolated configurations and evaluation commands for the
  full matched TCN-vs-GCN experiment. Do not start full training until the GPU environment, expected
  duration/cost, output directories, and stop/resume procedure are agreed.

## Phase 1 Full-Vocabulary Model Lock - 2026-08-11

The active comparison is implemented by
`model/experiments/phase1_full_vocab_baseline.py`. It contains only:

- `production_streaming_tcn`: the current causal per-frame family, aggregated over real frames;
- `masked_pool_tcn`: the same causal encoder with explicit masked temporal average pooling.

Both branches have `169,004` parameters, receive the same 17 warm-started encoder layers, use fresh
heads, seeds `101/202/303`, batch size `32`, maximum 40 epochs, AdamW `0.0005`, weight decay
`0.0001`, patience `8`, and the same geometric and online stride/compact/zero-pad temporal
augmentation. Missing-landmark corruption is evaluation-only because no project training transform
has passed an independent gate.

Actual-data smoke passed for both branches, including one real `tf.data` optimization step,
save/reload, and finite `[N,236]` clip output. Model/checkpoint selection uses mean primary
validation clip top-1 with macro-F1 as tie-break. The protected test is not read by prepare, smoke,
training, or validation selection.

## Phase 1 Validation Selection Freeze - 2026-08-12

All six equal-budget runs completed. Validation-only results selected `production_streaming_tcn`:

- production TCN: mean top-1 `0.671160`, macro-F1 `0.648246`, top-1 standard deviation `0.004044`;
- mask-aware TCN: mean top-1 `0.661356`, macro-F1 `0.643942`, top-1 standard deviation `0.001528`.

The production branch won validation top-1 on every seed. The advantage is modest, so this is a
control-family selection rather than evidence that masked pooling is broadly inferior. The
selection artifact freezes the experiment config, validation report, test tensor, and seed
`101/202/303` best-checkpoint hashes. The protected test remains unaccessed. The next action is one
guarded protected-test evaluation; no post-test model or threshold tuning is authorized.

## Phase 1 Protected-Test Decision - 2026-08-12

P1-FV1 is complete. The selected three-seed production-TCN ensemble achieved test top-1 `0.6095`,
top-5 `0.8866`, macro-F1 `0.5964`, worst-decile mean F1 `0.1741`, and uncalibrated ECE `0.2183`.
This validates the full-vocabulary data/evaluation machinery and produces a stable error registry,
but it does not meet real-user release gates and does not justify Android replacement.

The result supports the approved roadmap rather than another landmark-TCN tuning loop: preserve
this model as the Phase 1 control and use verified class/confusion failures to scope the Phase 2
isolated landmark-plus-RGB study. Do not tune P1-FV1 against its now-accessed test set. Before Phase
2 training, freeze RGB/ROI data lineage, train-only preprocessing, validation selection, and a
fresh evaluation policy; the historically reused ASL Citizen test cannot be the sole final claim.
