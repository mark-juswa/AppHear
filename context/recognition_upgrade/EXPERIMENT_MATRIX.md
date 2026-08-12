# Experiment Matrix

**Purpose:** Pre-register experiment order, controls, and stopping rules.
**Status:** E6 COMPONENT REVIEW COMPLETE; E6-2/E6-3/E6-5 NO-GO; E6-4 EVIDENCE-ONLY; E6-6/E6-7 BLOCKED; BASELINE PRESERVED. **Last updated:** 2026-08-09.

| ID | Experiment | Control / variables | Go | No-go / fallback |
|---|---|---|---|---|
| E0 | Reproduce current baseline | current 236 candidate, native/k4/k8, three seeds where trainable | metrics within 1 point of recorded; hashes/splits frozen | repair reproducibility first |
| **E1** | Graph sanity and fair baseline | TCN vs failed slim GCN vs full-capacity GCN; exact features/splits/augmentation; 50-class overfit test first | sanity slice >95% train accuracy; full run >=TCN+5 native and +3 k8 without severe class regressions | stop GCN; use TCN landmark encoder for E3 |
| E2 | Crop pipeline quality | 80/96/112 crops; ROI expansion; native and low-FPS; blinded sample audit | >=98% usable hand crops when hand is visible, parity fixtures pass | fix tracker/crops before modeling |
| E2b-A | Paired ROI recovery | control hold vs causal pose-hand-anchor recovery at 150/250/350 ms | >=20 point paired availability gain at every cadence; <=2% wrong/stale; parent 98% unchanged | **NO-GO:** native +16.7; recovered usability <=23.7% |
| E2c | Temporal hand tracking | paired MediaPipe IMAGE vs VIDEO on raw chronological frames | improve known-visible recall/containment at every cadence without stale/wrong-hand or latency failure | **NO-GO:** +11.1/+4.5/+7.5; right-hand regressions |
| E2d | Detector operating point | paired IMAGE/VIDEO at 0.5, 0.4, 0.3 detection/presence; 120 positive + 120 negative target-hand items | >=20-point recall gain at every cadence/hand; false ROI <=5% and <=2-point increase; p95 <=1.2x | **NO-GO:** no candidate passed; lower thresholds were left-biased and 0.3 produced excessive false ROIs |
| E2e-C0 | Independent hand-detector screening | single-class detector candidates on corrected 150-frame gold plus dedicated non-signing negatives | materially approach 95% instance recall, <=2% false ROI, improve blur/edge/two-hand recall, export and mobile-cost feasible | retain MediaPipe for landmarks only; redesign RGB stream or defer hybrid |
| E3-B0 | Upper-body/full-frame RGB feasibility | no-training preflight, signer-disjoint class inventory, tiny tensor/model smoke | enough classes/clips for pilot; no leakage; tensor smoke passes; cost acceptable | return to detector annotation inventory or smaller vocabulary |
| E3-B5 | Landmark temporal scale validation | 50 classes, 16/4/4 per class, Conv1D vs TCN vs masked TCN, seeds 101/202/303 | masked TCN highest mean best-val and wins/ties at least 2/3 seeds without prediction collapse | keep stronger comparator; do not scale RGB/fusion until landmark baseline is stable |
| E3-B6 | Landmark feature augmentation | frozen E3-B5 split; current features vs derived motion/relative-geometry features | >=3-point mean best-val gain, no mean best-test loss, less worst-class/confusion concentration | no-go for landmark-only feature augmentation; return to RGB/hand-shape path or stronger encoder |
| E3-B7 | Derived-feature ablation | frozen E3-B5 split; base+velocity vs base+relationships vs reduced combinations | retain E3-B6 test gain with smaller train-val gap and clearer feature-group winner | stop landmark feature engineering; return to RGB/hand-shape or stronger encoder path |
| E3 | Landmark vs RGB vs hybrid | identical 50-sign pilot split/training budget | hybrid >= best stream +5 points or resolves registered confusions; cost projection viable | keep best single stream |
| C0-B0 post-E6 | AppHear-domain hand-ROI detector feasibility | new training-only AppHear boxes/hard negatives; frozen P0/N0/P1 evaluation; MobileNetV2 256/320 TFLite branches | registered C0-B recall/false-ROI/IoU gates plus reproducible INT8 export and credible CPU cost | retire detector-derived hand-crop hybrid as immediate path; preserve v3.0 |

C0-B0 Stage 1 status on 2026-08-09: inventory passed with `42,251` candidates after protected
exclusions; balanced 24-frame annotation smoke Run 03 passed review with `28` boxes; isolated
Linux/Python 3.10 Run `c0b_toolchain_smoke_03` completed one-epoch training, TFLite export,
MediaPipe reload, and CPU inference. This is wiring evidence only. Condition-balanced annotation
readiness remains incomplete, so detector pilot training is not authorized.
| E4-B strict 7 local | corrected local supplementary `[96,258]` landmark benchmark; 7 signs; signer-disjoint train/val/test; Conv1D vs masked TCN across seeds 101/202/303 | **NO-GO:** train fit near-perfect but validation/test collapsed at random or below; split was confounded with feature provenance | do not rerun with more epochs; build same-provenance Stage-E/current-pipeline benchmark or collect more signers |
| E4-D Stage-E same-provenance diagnostic | Stage-E-only local supplementary clips for the same 7 signs; train/val from folder 2, held-out test from folder 1; Conv1D vs masked TCN | **DIAGNOSTIC PASS / PRODUCTION NO-GO:** masked TCN mean best test `0.6286`; collapse fixed but `BYE`, `THANKYOU`, and `NO` remain weak | E4-E focused review package prepared; manual review must finish before more training |
| E4-E focused error review | Recreate E4-D best TCN predictions and manually review failed `BYE`, `THANKYOU`, and `NO` rows plus references | **COMPLETE:** 156/156 reviewed; 140 keep, 16 relabel; visibility/blur not primary; `THANKYOU` label-confounded, `BYE`/`NO` remain real failures | prepare E4-F cleaned diagnostic; do not promote E4-D |
| E4-F cleaned diagnostic | Exclude/quarantine E4-E relabel rows and rerun same Conv1D vs masked-TCN comparison on cleaned Stage-E-only data | **COMPLETE / PRODUCTION NO-GO:** selected masked TCN test improved to `0.6856`, but `BYE` stayed `0/29` and `NO` stayed `12/30` | prepare E4-G focused `BYE`/`YES`/`NO` separability diagnostic |
| E4-G BYE/YES/NO separability | Reuse E4-F selected model; target-restricted predictions, compact landmark centroid probe, ridge probe, hand-hit summary, and visual panels for `BYE`/`NO`/`YES` | **COMPLETE / PRODUCTION NO-GO:** model target test `0.4253`, target-restricted `0.4483`; `BYE->YES` 28/29; ridge improves `NO`/`YES` but keeps `BYE` 0/29; missing hands are not primary | prepare E4-H controlled variant/data-balance intervention before another full 7-sign benchmark |
| E4-H BYE/NO/YES variant intervention | Manual/auto variant triage from E4-G panels; contact sheets by sign/split; no training | **AUTO-TRIAGE COMPLETE:** 94/94 rows filled, summary/check passed; 70 keep, 24 needs_second_review (`BYE` 12, `NO` 11, `YES` 1) | weak signs deferred from next reliable-core benchmark |
| E4-I reliable-core 4-sign | Reuse E4-F cleaned tensor; keep only `GOOD`, `HELLO`, `SORRY`, `YES`; exclude `BYE`, `NO`, `THANKYOU`; Conv1D vs masked TCN, seeds 101/202/303 | **COMPLETE / GATE FAILED:** Conv1D mean best test `0.8249`; validation-selected test `0.6780`; `SORRY` collapsed to `GOOD` in selected checkpoint and `YES` stayed below `0.80` | E4-J prepared |
| E4-J reliable-core 3-sign | Reuse E4-F cleaned tensor; keep only `GOOD`, `HELLO`, `SORRY`; exclude `BYE`, `NO`, `THANKYOU`, `YES`; Conv1D vs masked TCN, seeds 101/202/303; latest-vs-best stability summary | **COMPLETE / LIMITED PASS:** Conv1D latest mean test `0.9741`, min class `0.9333`; Conv1D best unstable, min class `0.1667`; masked TCN unstable | E4-K policy diagnostic complete |
| E4-K checkpoint policy | Read E4-J metrics; apply strict written gate; compare best/latest policy families | **COMPLETE:** strict written gate false; deployable offline policy found: `conv1d_baseline_latest_fixed_epoch`; TCN rejected for next local expansion | E4-L prepared |
| E4-L MAKE one-sign expansion | Reuse E4-J core; extract `MAKE`; train Conv1D only with latest/fixed policy, seeds 101/202/303 | **COMPLETE / GATE FAILED:** extraction succeeded, tensor `[260,96,258]`, split `105/35/120`; held-out `MAKE` collapsed mostly into `GOOD`; mean test `0.7722`, min class and min MAKE `0.0333` | stop manual one-word expansion as the main path; use dual-source screening |
| E4-M dual-source candidate screen | Inventory ASL Citizen conversational features plus local supplementary feature/raw/validated inventories; preserve core controls and prior rejected/unstable labels | **COMPLETE / PREFLIGHT PASS:** `HAVE` and `KNOW` are train-ready from existing features; `GET` and `WELCOME2` need local feature extraction; `BYE`/`NO`/`THANKYOU`/`YES` remain unstable; `MAKE` rejected | E4-N prepared |
| E4-N dual-source 5-sign training screen | Combine E4-J reliable core `GOOD`/`HELLO`/`SORRY` with E4-M train-ready `HAVE`/`KNOW`; Conv1D latest/fixed policy; source-aware metrics | **COMPLETE / GATE PASS:** mean latest test `0.9774`, min core `0.9667`, min candidate `0.9286`; latest checkpoint policy confirmed | prepare E4-O GET/WELCOME2 extraction screen |`r`n| E4-O GET/WELCOME2 7-sign screen | Reuse E4-N; add ASL Citizen `GET`/`WELCOME2`; extract 140 local validated `GET`/`WELCOME2` videos; Conv1D latest/fixed policy | **PREPARED / TWO-ROW EXTRACTION SMOKE PASS:** base+ASL rows `328`, pending local extraction `140`; full extraction/training not started | user runs full extraction, smoke, training, final check |
| E4 | IMAGE vs VIDEO vs LIVE_STREAM | same device, resolution, models, sign clips | >=1.5x perception throughput, retrained loss <1 point, missingness/drift acceptable | stay IMAGE |
| E5 | Temporal/boundary | S5 vs learned boundary; causal TCN vs small transformer; variable FPS/prefix | boundary F1 >=0.85, false commits <=1/30 min, latency gate | keep S5 fallback and causal TCN |
| E6 | Non-manual cues | no face vs sparse head/face features on affected vocabulary | >=2 points on pre-registered non-manual subset at acceptable cost | omit face |
| E7 | Quantization/mobile | float vs INT8, CPU/delegates, thermal | <=1 point loss; Android gates pass | QAT/slim/cadence or landmark-only |
| E8 | Data learning curve | 10/20/30 pilot signers | >=0.85 top-1 at 30 and improving curve | revise labels/vocab/model |
| E9 | Vocabulary expansion | 50 -> 100 -> 236 | each tier independently meets release gates | ship smaller vocabulary |
| E10 | Continuous CTC | natural sentences only | gloss WER target pre-registered from baseline; insertion/false activation controlled | remain isolated |

## E1 Exact First Experiment

Run the existing full-capacity config only after:

1. verifying graph adjacency and class/data tensors;
2. proving the model can overfit a balanced 50-class, 5-clip/class slice;
3. matching TCN data, augmentation, labels, aggregation, and seeds;
4. logging gradient norms, masks, train/val curves, params/FLOPs, and runtime projection.

This comes first because the prior 0.1588 result contradicts the published expectation and can
indicate an implementation/training defect. Building RGB fusion on an untrusted structured branch
would confound every later result.

## Shared Requirements

Signer-disjoint splits; immutable test set; three seeds; top-1/top-5, macro/per-class/worst-decile,
early/prefix, low-FPS, missingness, ECE, accepted precision/coverage, confusion groups, model size
and projected/measured latency. All artifacts use new directories.

## References, Decisions, Assumptions, Risks, Open Questions, Next Action

- **Sources:** current run artifacts and `EVALUATION_AND_ACCEPTANCE_GATES.md`.
- **Decision:** E1 completed with GCN no-go; TCN remains the E3 landmark control. No Android hybrid work before E3.
- **Risk:** repeated test-set iteration; use val for selection and test once per promoted candidate.
- **Open question:** winning crop geometry and whether a stronger timestamp-aware ROI tracker is required.
- **Next action:** follow `DYNAMIC_MIXED_RECOGNITION_ROADMAP.md`; prepare Phase 1 stable-candidate tiering and stable-primary landmark training. Detector training, Android integration, broad hybrid fusion, large vocabulary expansion, and production replacement remain blocked.


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-017 apply; component-specific decisions in this document apply only after their experiment gate passes.
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
### E1 Review Finding - 2026-07-25

- **Important / fix before matched training:** `model/augment.py` adds noise to pose xyz on padded
  all-zero frames. The experimental GCN infers its mask from nonzero input, so augmentation would
  make padding appear real. The 95.2% sanity result is unaffected because that run disabled
  augmentation. Required next action: preserve the pre-augmentation frame mask (or accept an
  explicit mask input in an experiment-only model), add a regression test, rerun the sanity gate,
  then authorize the full matched seeds.
### E1 Augmentation-Mask Fix - 2026-07-25

- Resolved the review blocker: `make_stream_dataset` now supplies the real per-frame sample mask to
  streaming augmentation, and `augment_batch` forcibly restores every invalid/padded frame to exact
  zero after geometry, noise, and temporal dropout.
- Isolated training retains its existing one-argument augmentation path; no feature schema, dataset,
  Android code, or production model asset changed.
- Added regressions proving padded frames stay zero under pose noise and proving the `tf.data`
  streaming path passes the mask through. Existing missing-hand preservation still passes.
- Verification: focused Ruff passed; focused tests passed; full Python test suite passed. Global Ruff
  still has 33 pre-existing E501 findings in unrelated `eval/` and `pipeline/ingest` files.
- Next gate is the developer-run corrected E1 sanity command. Require `passed: true` and
  `best_train_accuracy >= 0.95` in `gcn-full-masked_t32_seed240725.json`.
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
### E1 Matched-Run Preparation - 2026-07-25

- Prepared six fresh, seed-isolated configs: TCN and corrected GCN at seeds 0/1/2, identical
  train/validation features, augmentation, optimizer settings, epochs, and signer splits.
- Added overwrite-safe training: a fresh command refuses existing evidence; `--resume` loads
  `latest.keras`, validates the tensor contract, appends history, and preserves the prior best.
- Added unique native/k4/k8 report names and model/config/feature provenance so evaluation conditions
  cannot overwrite one another.
- Added `model.experiments.e1_matched` preflight/evaluate/summarize tooling and
  `E1_MATCHED_RUNBOOK.md`.
- Real preflight passed: 13,236 train clips/35 signers, 3,264 validation clips/5 signers, 2,620 test
  clips/11 signers, 236 classes, schema 3.0, no signer leakage, all dataset/config hashes frozen,
  TCN 169,004 params, GCN 2,751,078 params, six unused output directories.
- End-to-end tiny-run test verified checkpoint creation, overwrite refusal, and epoch-continuing
  resume. Corrected GCN checkpoint save/load with initialized optimizer also passed.
- Full training remains unstarted. Next action belongs to the developer: select a GPU environment,
  confirm TensorFlow sees the GPU, rerun preflight, and run only the one-epoch GCN seed-0 benchmark.

## E2 Execution Status - 2026-07-26

- Experiment-only crop tooling, deterministic sampling, blinded review artifacts, and audit
  summarization are implemented under `pipeline/crops/`.
- One-clip real-data smoke passed: 5 direct crops and 1 explicit missing ROI across six reviewed
  hand/frame records; synchronized panel geometry was visually checked.
- Engineering/audit output is capped at 600 balanced review panels while retaining metadata for all
  evaluated candidates.
- Full Python suite: 133 passed. Focused Ruff and mypy passed.
- Next: developer runs the 60-clip engineering matrix. E3 remains blocked until E2 reaches the
  0.98 usable-visible-hand gate on the 200-clip confirmation audit.
### E2 Run 01 Protocol Finding - 2026-07-26

- Run 01 generation completed, but its low-FPS arm was invalid because unsampled native landmarks
  refreshed ROI history. No human labels were entered and no configuration was selected.
- Cadence-aware observation masking is corrected and covered by regression tests; corrected
  native/k4/k8 real-video smoke passed.
- Authoritative next run: `engineering_run_02`. Treat Run 01 as diagnostic-only evidence.
### E2 Run 02 Human-Audit Verdict - 2026-07-26

- 600/600 reviewed; 358 requested hands visible; corrected usable rate 46.65% vs 98% gate.
- ROI availability on visible hands 62.57%. Dominant failures: missing ROI 135, motion blur 38.
- Direct ROI 81.4% usable; static held ROI 20.0% usable.
- No size/expansion winner: 466/528 base items had only one candidate and zero had all nine.
- Verdict: E2 no-go. No 200-clip audit and no E3. Build paired E2b ROI-recovery experiment first.
### E2e Corrected All-Hand Audit Verdict - 2026-07-26

- 150 unique clips, 41 signers, 184 visible hand instances after blinded sub-two-hand adjudication.
- MediaPipe IMAGE: 66.30% instance recall, 77.78% any-hand frame recall, 46.27% complete two-hand recall.
- Motion blur 58.33%, edge clipped 25.81%, occluded 52.00%; all fail the registered ROI gates.
- Verdict: no-go for MediaPipe as sole ROI provider. E2b pose fallback, E2c VIDEO, and E2d threshold tuning are already rejected.
- Next registered step: C0-A checkpoint/license preflight and six-positive/twenty-negative smoke on the frozen P0/N0/P1 fixtures. No E3 or Android rollout.
- Authoritative result: `E2E_ALL_HAND_GOLD_RESULT.md`.

### E2e-C0 Capture Fixture Result - 2026-07-27

- N0 PASS: 613 eligible no-hand frames from 630 reviewed rows; 16 contamination exclusions and one quarantine.
- P1 PASS: 108 eligible visible-hand/non-sign frames, 172 hand boxes, and 32 no-hand exclusions from 140 rows.
- Frozen reviewed-manifest SHA-256 values are recorded in `E2E_C0_CAPTURE_RESULT.md`.
- This completes fixture preparation only. C0-A detector accuracy remains unmeasured.
### C0-A HaGRID Smoke Result - 2026-07-28

- HaGRID YOLOv10n hand checkpoint downloaded and hashed: `C6EA3B5F0323D94D9EE461EBB2BCB21BD1C743B19B5AA6A008D118D83C97DC03`.
- Smoke run: `artifacts/recognition_upgrade/e2e_c0/c0a_hagrid_smoke_01`.
- Threshold sweep: 0.01 reached 5/6 positive frames but 15/20 N0 false positives; 0.50 reached 4/6 positives and 4/20 N0 false positives; 0.90 removed N0 false positives but retained only 1/6 positives.
- Verdict: no-go for direct HaGRID promotion. Treat the checkpoint as a research reference only because of poor smoke transfer, unresolved licensing/export constraints, and no Android production path.
- Next: prepare a C0 decision package comparing an AppHear-domain production-compatible hand detector pilot with a landmark-independent upper-body/full-frame RGB fallback. Do not start C0-B training, E3, or Android integration.
### C0 Route Decision - 2026-07-28

- Decision report: `C0_ROUTE_DECISION_REPORT.md`.
- Selected path: staged two-branch comparison.
- Immediate executable branch: E3-B0 upper-body/full-frame RGB feasibility preflight using existing ASL Citizen/local videos.
- Held branch: AppHear-domain hand detector pilot remains blocked until a training-only hand-box annotation inventory is approved.
- Rationale: RGB feasibility can test whether raw video bypasses the hand-ROI bottleneck without waiting for detector annotation, while the detector path remains available if RGB fails or proves too expensive.
- No full extraction, training, Android integration, or production recognizer changes are authorized by this decision.

### E3-B0 RGB Feasibility Preflight And Tensor Smoke - 2026-07-28

- Preflight strict 20/4/4 policy found only 7 classes and was rejected as too strict for the first feasibility pilot.
- Preflight relaxed 10/2/2 policy passed: 50 classes, 1,870 ASL Citizen clips, no signer leakage, 12/12 videos readable.
- Tensor smoke passed: 3 classes, 12 clips, tensor shape `[12, 8, 112, 112, 3]`, tiny model forward pass, one training epoch, and checkpoint save.
- Outputs: `artifacts/recognition_upgrade/e3_rgb_b0/preflight_02` and `artifacts/recognition_upgrade/e3_rgb_b0/tensor_smoke_01`.
- Next: prepare a user-run bounded pilot package with duration estimate and isolated outputs. Do not start full extraction/training without review.

### E3-B0 Pilot Package Prepared - 2026-07-28

- Package: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_01`.
- Runner: `pipeline/rgb/e3_b0_pilot.py`.
- Scope: bounded feasibility only, 10 classes, 120 clips, 16 frames per clip, 112x112 RGB, 3 epochs.
- Estimated raw float32 tensor size: 275.62 MiB before compression.
- Runbook: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_01/README_RUN.md`.
- Status: prepared only; not started by the agent.

### E3-B0 Pilot 01 Result - 2026-07-28

- Result document: `E3_B0_PILOT_01_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_01`.
- Final check passed with no reported errors.
- Scope completed: 10 classes, 120 clips, 16 frames per clip, 112x112 RGB, 6 total epochs after resume.
- Metrics: train accuracy `0.3000`, validation accuracy `0.0500`, test accuracy `0.2500`.
- Interpretation: extraction, tensor construction, training, resume, checkpointing, diagnostics, and output isolation passed; accuracy did not validate.
- Decision: no promotion, no full RGB training, and no Android integration from this run.
- Next: user runs `pilot_02_strict_support` before deciding whether standalone RGB is worth scaling.

### E3-B0 Pilot 02 Strict-Support Package Prepared - 2026-07-28

- Package: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support`.
- Source preflight: `artifacts/recognition_upgrade/e3_rgb_b0/preflight_01`.
- Scope: 7 strict-support classes, 168 clips, 16 frames per clip, 112x112 RGB, 3 epochs per command.
- Split: 112 train, 28 validation, 28 test; 16/4/4 clips per class.
- Signer leakage check: none; 22 train signers, 5 validation signers, 9 test signers.
- Estimated raw float32 tensor size: 385.88 MiB before compression.
- Runbook: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support/README_RUN.md`.
- Status: prepared only; not started by the agent.

### E3-B0 Pilot 02 Strict-Support Result - 2026-07-28

- Result document: `E3_B0_PILOT_02_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support`.
- Final check passed with no reported errors after refresh.
- Scope completed: 7 classes, 168 clips, 16 frames per clip, 112x112 RGB, 6 total epochs after resume.
- Metrics: train accuracy `0.3482`, validation accuracy `0.0714`, test accuracy `0.1071`; 7-class random baseline is `0.1429`.
- Diagnostic: held-out predictions were biased toward a few classes and confidence was not reliable.
- Decision: no-go for scaling standalone full-frame 112x112 RGB with the tiny temporal CNN; no Android integration from this branch.
- Next: pivot to a bounded pretrained/crop-aware visual experiment or return to landmark temporal/feature improvements.


### E3-B1 Improved RGB Package Prepared - 2026-07-28

- Plan: `E3_B1_IMPROVED_RGB_PLAN.md`.
- Runner: `pipeline/rgb/e3_b1_pretrained_rgb.py`.
- Package: `artifacts/recognition_upgrade/e3_rgb_b1/pilot_01_mobilenetv3_upper_body`.
- Source split: `artifacts/recognition_upgrade/e3_rgb_b0/pilot_02_strict_support/pilot_manifest.csv`.
- Scope: same 7 classes and signer-disjoint 112/28/28 split as E3-B0 pilot 02, 16 frames per clip, 160x160 upper-body center crop.
- Model path: frozen MobileNetV3Small frame embeddings plus small temporal Conv1D head; preferred weights are `imagenet`.
- Baseline comparator: E3-B0 pilot 02 validation `0.0714`, test `0.1071`, random `0.1429`.
- Gate: validation above random, test materially above E3-B0, distributed predictions, no confidence collapse.
- Status: prepared only; not started by the agent.


### E3-B1 Result - 2026-07-28

- Result document: `E3_B1_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e3_rgb_b1/pilot_01_mobilenetv3_upper_body`.
- Final check passed after refresh; total epochs `16`.
- Latest metrics: train `0.9911`, validation `0.1429`, test `0.1429`; random baseline `0.1429`.
- Best validation checkpoint: train `0.8482`, validation `0.2143`, test `0.1071`.
- Comparison: E3-B1 improved train fitting dramatically over E3-B0 but did not improve held-out signer accuracy enough.
- Correction: E3-B1 class-name metadata was fixed to inherit E3-B0 label order; accuracy values were valid, diagnostics regenerated.
- Decision: no more E3-B1 epochs and no scaling of standalone upper-body MobileNetV3-only RGB.
- Next: choose same-signer visual sanity or bounded landmark-plus-RGB fusion smoke.


### E3-B2 Same-Signer RGB Sanity Package Prepared - 2026-07-28

- Plan: E3_B2_SAME_SIGNER_SANITY_PLAN.md.
- Builder: pipeline/rgb/e3_b2_same_signer_sanity.py.
- Runner: pipeline/rgb/e3_b1_pretrained_rgb.py.
- Package: rtifacts/recognition_upgrade/e3_rgb_b2/pilot_01_same_signer_mobilenetv3.
- Scope: intentionally signer-leaky debugging sanity, 7 classes, 84 clips, 56/14/14 split, 8/2/2 per class.
- Model path: 160x160 upper-body center crop, frozen MobileNetV3Small frame embeddings, temporal Conv1D head.
- Gate: same-signer validation/test should be clearly above random; strong pass >=0.70, weak pass >=0.50, no-go near random/collapsed predictions.
- Warning: do not report this as cross-signer accuracy; high accuracy only proves the RGB branch can solve the easy case.
- Status: prepared only; not started by the agent.


### E3-B2 Result - 2026-07-28

- Result document: `E3_B2_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e3_rgb_b2/pilot_01_same_signer_mobilenetv3`.
- Final check passed after refresh; total epochs `16`.
- Latest metrics: train `1.0000`, validation `0.2143`, test `0.2857`; random baseline `0.1429`.
- Best validation checkpoint: train `0.9464`, validation `0.3571`, test `0.3571`.
- Gate result: no-go; did not reach weak-pass threshold of validation/test >=0.50.
- Decision: no more E3-B2 epochs and no scaling of standalone RGB-only training.
- Next: bounded landmark-plus-RGB fusion smoke only if cheap to prepare; otherwise return to landmark temporal/feature improvements.


### E3-B3 Landmark + RGB Fusion Smoke Package Prepared - 2026-07-28

- Plan: `E3_B3_FUSION_SMOKE_PLAN.md`.
- Runner: `pipeline/rgb/e3_b3_fusion_smoke.py`.
- Package: `artifacts/recognition_upgrade/e3_fusion/pilot_01_landmark_rgb_fusion`.
- Scope: signer-disjoint 7-class, 168-clip split; trains `rgb_only`, `landmark_only`, and `fusion` heads on the same labels/splits.
- Landmark input: rebuilt `[96,258]` v3.0 streaming features from existing Stage-E landmarks/spans; no MediaPipe rerun.
- RGB input: reused E3-B1 `[16,576]` MobileNetV3 embeddings; no RGB embedding rerun.
- Gate: fusion must beat both branch-only heads on validation and avoid test regression to be promising.
- Status: prepared only; not started by the agent.


### E3-B3 Result - 2026-07-28

- Result document: `E3_B3_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e3_fusion/pilot_01_landmark_rgb_fusion`.
- Final check passed after refresh; total epochs `16`.
- Latest metrics: RGB `0.1786/0.1786` val/test, landmark `0.5714/0.6786`, fusion `0.2857/0.2500`.
- Best validation metrics: RGB `0.2500/0.2500`, landmark `0.6071/0.6071`, fusion `0.2857/0.2500`.
- Gate result: fusion no-go; fusion did not beat landmark-only and regressed heavily against it.
- Decision: stop standalone RGB and naive fusion work for now; no Android hybrid integration.
- Next: see `E3_B4_RESULT.md`; prepare larger multi-seed landmark-temporal validation using the same `[96,258]` feature path.

### E3-B4 Landmark Temporal Result - 2026-07-28

- Plan: `E3_B4_LANDMARK_TEMPORAL_PLAN.md`.
- Runner: `pipeline/rgb/e3_b4_landmark_temporal.py`.
- Package: `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_01_tcn_vs_masked`.
- Source tensor: `artifacts/recognition_upgrade/e3_fusion/pilot_01_landmark_rgb_fusion/dataset/landmark_features.npz`.
- Scope: same 7 classes and signer-disjoint 112/28/28 split as E3-B3; no MediaPipe, RGB extraction, Android, or production recognizer changes.
- Branches: `conv1d_baseline`, `tcn_pool`, and `tcn_masked_pool`.
- Reference gate: compare against E3-B3 landmark-only best validation/test `0.6071/0.6071` and latest test `0.6786`.
- Result document: `E3_B4_RESULT.md`.
- Final check passed after refresh; total epochs `16`.
- Best-validation winner: `tcn_masked_pool` with val/test `0.6429/0.6429`.
- Comparators: `conv1d_baseline` best val/test `0.5714/0.6429`; `tcn_pool` best val/test `0.5714/0.6071`; E3-B3 landmark reference `0.6071/0.6071`.
- Gate result: directional pilot pass; not production evidence because val/test each have only 28 clips.
- Decision: continue landmark-first and validate masked TCN across more seeds/classes before Android, RGB/fusion scaling, or recognizer replacement.













### E3-C Frozen-Split Landmark + RGB Fusion Package Prepared - 2026-07-29

- Plan document: `E3_C_FUSION_PLAN.md`.
- Runner: `pipeline/rgb/e3_c_fusion.py`.
- Prepared run: `artifacts/recognition_upgrade/e3_fusion/pilot_02_frozen_50_landmark_rgb`.
- Source split: E3-B5 frozen 50-class signer-disjoint split, 1,200 clips total, 800 train / 200 validation / 200 test.
- Landmark stream: E3-B6 full augmented `[96,728]` tensor from `pilot_03_feature_augmented`.
- RGB stream: 16 sampled frames per clip, 160x160 upper-body center crop, MobileNetV3Small ImageNet frame embeddings.
- Branches: `rgb_only`, `landmark_aug_only`, and `fusion_aug_rgb`; seeds `101`, `202`, `303`; batch size `8`; epochs `12` per run command.
- Local validation completed: syntax compile passed, prepare passed, structural check passed, and smoke test passed for RGB extraction, embedding, forward pass, one training batch, and weight writing for all three branches.
- Full extraction/training is not started. Next action belongs to the developer: run E3-C, then `check --require-metrics`, then compare against E3-B6 and E3-B7 before approving any follow-up.

### E3-C Frozen-Split Landmark + RGB Fusion Result - 2026-07-29

- Result document: `E3_C_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e3_fusion/pilot_02_frozen_50_landmark_rgb`.
- Final check passed with no missing outputs.
- Tensor shapes: landmark `[1200,96,728]`; RGB `[1200,16,576]`.
- Mean best validation/test: `rgb_only` `0.1500/0.0750`, `landmark_aug_only` `0.5117/0.3867`, `fusion_aug_rgb` `0.2617/0.1867`.
- Seed winners by best validation: all three seeds selected `landmark_aug_only`.
- Gate result: no-go. Fusion missed the E3-B6 references by `-0.2500` validation and `-0.2016` test.
- Interpretation: RGB-only and fusion both overfit heavily; the landmark control reproduced E3-B6, so the run is valid and the current upper-body frozen-MobileNet RGB representation is the weak point.
- Decision: do not promote E3-C, do not integrate RGB into Android, and do not rerun this exact design with more epochs.
- Next: explicitly choose between detector-derived hand-crop RGB evidence or landmark/data generalization improvements before preparing the next experiment.

### E4-A Landmark Generalization And Data-Quality Audit Planned - 2026-07-29

- Plan document: `E4_A_LANDMARK_GENERALIZATION_PLAN.md`.
- Proposed future run directory: `artifacts/recognition_upgrade/e4_generalization/e4_a_landmark_data_audit_01`.
- Purpose: diagnose class, signer, confusion, support, label/variant, and data-quality limits before more model training or RGB fusion.
- Inputs: E3-B5 analysis outputs, E3-B6/E3-B7/E3-C metrics, frozen 50-class manifests, selected classes, ASL Citizen `features_streaming` tensors, and span/landmark metadata if needed.
- Output decision: choose one of `E4-B cleaned reliable-vocabulary retrain`, `E4-C targeted local signer data collection`, `E4-D label/variant adjudication`, `C0 hand-crop detector path`, or no-go for current data.
- Gates: source-run inventory complete, held-out class reliability tiers documented, stable confusion groups identified, signer/split data gaps reported, collection targets named by gloss, and one concrete next experiment selected with go/no-go criteria.
- Non-goals: no model training, no Android changes, no production recognizer changes, no dataset mutation, no repeat of E3-C upper-body frozen-MobileNet fusion.
- Status: planned only; implementation has not started.


### E4-A Landmark Generalization And Data-Quality Audit Result - 2026-07-29

- Result document: `E4_A_RESULT.md`.
- Runner: `pipeline/rgb/e4_a_generalization_audit.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_a_landmark_data_audit_01`.
- Final check passed with no missing outputs.
- Classes audited: 50.
- Tier counts: `candidate_keep` 4, `borderline_collect_more` 15, `confusion_review` 8, `drop_or_defer` 6, `needs_visual_evidence` 17.
- Candidate keep classes: `SWITZERLAND`, `COUCH`, `CURLYHAIR`, `DOWNSIZE1`.
- Major review groups: `DEAF1 <-> TWINS1`, `EVERYYEAR <-> TAKECARE`, `CROSS3 <-> WHALE`, `ROCKINGCHAIR1 <-> TRACTOR`, `BASEBALLCAP <-> LETTUCE1`, `BOXING <-> TAKECARE`, `EDIT1 <-> INDEPENDENT`, `ELEVATOR1 <-> INDEPENDENT`.
- Tooling gap: current E3 artifacts do not persist stable per-clip predictions for all branches/seeds, so per-signer accuracy cannot yet be claimed honestly.
- Decision: do not retrain blindly on all 50 classes. Recommended next step is E4-C targeted collection and label/video review, then E4-B cleaned-vocabulary retrain only after the target list is approved.


### E4-C Targeted Collection And Label/Video Review Plan - 2026-07-29

- Plan document: `E4_C_TARGETED_COLLECTION_PLAN.md`.
- Target package: `artifacts/recognition_upgrade/e4_generalization/e4_c_targeted_collection_plan_01`.
- Source: E4-A audit outputs from `artifacts/recognition_upgrade/e4_generalization/e4_a_landmark_data_audit_01`.
- Prepared CSVs: `anchor_keep_classes.csv`, `borderline_collection_candidates.csv`, `confusion_review_classes.csv`, `defer_or_visual_review_classes.csv`, and `confusion_pair_review_queue.csv`.
- Anchor classes: `SWITZERLAND`, `COUCH`, `CURLYHAIR`, `DOWNSIZE1`.
- Borderline collection candidates: 15 classes, led by `PEEKABOO`, `BEE1`, `BOTH`, `SHARK1`, `SENTENCE2`, `LETTUCE1`, `SHAVE1`, `TWINS1`, and `EVERYYEAR`.
- Confusion-review queue: top pairs include `DEAF1 <-> TWINS1`, `EVERYYEAR <-> TAKECARE`, `CROSS3 <-> WHALE`, `ROCKINGCHAIR1 <-> TRACTOR`, and `BASEBALLCAP <-> LETTUCE1`.
- Gate: user must approve target classes and review actions before E4-B retraining. No training, Android work, production replacement, or RGB fusion is authorized by E4-C.















### E4-L MAKE One-Sign Expansion Result - 2026-07-30

- Result document: `E4_L_RESULT_AND_SCREENING_PIVOT.md`.
- Runner: `pipeline/rgb/e4_l_one_sign_expansion.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_l_make_expansion_pilot_01`.
- Classes: `GOOD`, `HELLO`, `SORRY`, `MAKE`.
- Full extraction completed: 70/70 `MAKE` rows, assembled tensor shape `[260,96,258]`, train/validation/test `105/35/120`.
- Structural check passed, but the gate failed.
- Latest fixed-epoch Conv1D summary: mean test `0.7722`, min seed test `0.7417`, min class test `0.0333`, min `MAKE` test `0.0333`.
- Failure pattern: held-out `MAKE` was mostly predicted as `GOOD` even though train/validation `MAKE` reached perfect accuracy.
- Decision: do not add `MAKE`; keep the reliable local core at `GOOD`, `HELLO`, and `SORRY`.
- Process decision: stop manual one-word expansion loops as the main path.
- Next experiment to design: automated dual-source candidate screening across `F:\ASL DATASET\ASL CITIZEN` and the local supplementary dataset, with source-aware splits, cross-source transfer checks, label/variant compatibility checks, signer-independent gates, and ranked keep/reject/needs-review outputs.


### E4-O GET/WELCOME2 Result And E4-P Pivot - 2026-07-31

- Result document: `E4_O_RESULT.md`.
- E4-O run directory: `artifacts/recognition_upgrade/e4_generalization/e4_o_get_welcome2_7sign_screen_01`.
- E4-O completed full local extraction and training structurally, but failed the accuracy gate.
- Full E4-O dataset shape: `[468,96,258]`; extraction `140/140` local `GET/WELCOME2` rows succeeded.
- E4-O latest mean test: `0.7822`; min core latest test: `0.7000`; min candidate latest test: `0.2619`; gate `false`.
- Main failure: local extracted `GET` collapsed mostly into `GOOD`; `WELCOME2` was better but is not promoted together with unstable `GET`.
- Decision: do not export, integrate, or use E4-O as a production candidate; quarantine `GET` and avoid more one-word manual expansion loops.

### E4-P Existing-Feature 20-Sign Pressure Test Prepared - 2026-07-31

- Package document: `E4_P_EXISTING_FEATURE_20SIGN_PACKAGE.md`.
- Runner: `pipeline/rgb/e4_p_existing_feature_20sign_pressure.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_p_existing_feature_20sign_pressure_01`.
- Purpose: fast 20-sign landmark-only pressure test using already-extracted ASL Citizen and local supplementary feature tensors; no extraction step.
- Classes: `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`, `WANT2`, `HELP`, `NICE`, `KEEP`, `START`, `MEET`, `CLOSE`, `GIVE`, `TALK1`, `WHAT1`, `CLEAN`, `LEAVE`, `STAND2`, `BECOME`, `WASH2`.
- Excluded: `GET`, `WELCOME2`, `MAKE`, `BYE`, `NO`, `YES`, `THANKYOU`.
- Dataset shape: `[1174,96,258]`; split counts train/validation/test `749/140/285`; random baseline `0.05`.
- Smoke passed: forward output `[24,20]`, one train batch completed, smoke weights saved.
- Structural check passed with `--require-full-dataset`.
- Next action: developer runs E4-P full training and final check. Do not start Android integration, production export, or another extraction batch until E4-P metrics are analyzed.

## E4-Q Confusion Resolver - 2026-07-31

| ID | Experiment | Control / variables | Go | No-go / fallback |
|---|---|---|---|---|
| E4-Q | `GOOD/SORRY/HELP/BECOME` confusion resolver | Compare `[96,258]` `base_conv1d` against `[96,728]` `derived_conv1d` and class-weighted `derived_balanced_conv1d`; seeds `101/202/303`; latest/fixed policy | mean latest test >= `0.85`, `SORRY` >= `0.85`, core >= `0.85`, candidate >= `0.70`, max predicted-class share <= `0.45` | If all landmark variants fail, move this confusion group to RGB hand/chest-crop evidence or targeted data/label repair before broad expansion |

Prepared run: `artifacts/recognition_upgrade/e4_generalization/e4_q_confusion_resolver_sorry_become_help_01`. Smoke and structural check passed. Full training is user-run.


## Dynamic Mixed Roadmap Experiments - 2026-07-31

| ID | Experiment | Control / variables | Go | No-go / fallback |
|---|---|---|---|---|
| E4-R | Stable-candidate tiering | Use all completed E4 evidence plus available ASL Citizen/local feature inventories; classify signs into Tier A stable, Tier B confusion, Tier C data-repair/deferred | ranked stable batch with per-sign support, source-aware evidence, and no known severe confusion | reduce to smaller Tier A; plan data collection/review instead of training |
| E4-S | Stable-primary landmark model | Train only Tier A signs with `[96,258]`; Conv1D latest/fixed as control; TCN only if controlled comparator; three seeds | per-class and macro gates pass, no source shortcut, no prediction concentration, calibration feasible | reduce vocabulary or repair data; do not add specialists to hide global weakness |
| E4-T | Offline confusion-router simulation | Replay primary logits; define registry groups, thresholds, reject behavior, accepted precision/coverage | router improves precision and controls false commits while preserving useful coverage | stricter primary rejection; defer specialists |
| E4-U | First visual specialist resolver | Target `SORRY/BECOME/HELP`; compare landmark-only control, RGB hand/body crop resolver, and late-fusion resolver | specialist beats landmark-only, `SORRY` passes group threshold, mobile cost projection feasible | data/variant repair or defer group |
| E4-V | Mixed recognizer offline simulation | Primary model + calibration + router + any passed specialist + reject on no-sign/OOV | accepted precision, coverage, per-class F1, no-sign false commits, low-FPS gates pass | smaller vocabulary, stricter thresholds, or defer Android |
| E4-W | Android experimental integration gate | Default-off assets, quantized parity, device smoke, thermal, latency | all device gates pass without replacing production recognizer | keep current production recognizer; return to offline work |

E4-S and E4-T are complete. E4-U evidence is prepared; use it to choose the next bounded specialist/data-repair experiment before Android/export or broad expansion.

| E4-R | Stable-candidate tiering | Use all completed E4-M/E4-N/E4-O/E4-P/E4-Q evidence to rank 236 labels into stable, confusion, defer, and inventory-only tiers | **COMPLETE:** primary-ready guarded signs are `GOOD`, `HELLO`, `HAVE`, `KNOW`; structural check passed | E4-S stable-primary landmark package next; no Android/export/specialist yet |


### E4-S Stable-Primary Package Prepared - 2026-08-02

- Package document: `E4_S_STABLE_PRIMARY_PACKAGE.md`.
- Runner: `pipeline/rgb/e4_s_stable_primary.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01`.
- Source run: `artifacts/recognition_upgrade/e4_generalization/e4_n_dual_source_5sign_screen_01`.
- Active primary classes: `GOOD`, `HELLO`, `HAVE`, `KNOW`.
- Withheld OOV/confusion holdout: `SORRY`.
- Active dataset shape: `[221,96,258]`; split counts train/validation/test `101/32/88`.
- OOV/confusion holdout rows: `50`.
- Smoke passed: forward output `[12,4]`, one train batch completed, smoke weights saved.
- Structural check passed with `--require-full-dataset`.
- Next action: user runs full E4-S training and final check. Passing E4-S authorizes E4-T offline router simulation only; it does not authorize Android export or production replacement.

### E4-S Training Result And E4-T Router Simulation Result - 2026-08-02

- E4-S source run: `artifacts/recognition_upgrade/e4_generalization/e4_s_stable_primary_4sign_01`.
- E4-S closed-set latest mean test accuracy: `0.9848`; minimum seed test `0.9773`; minimum per-class test `0.9286`.
- E4-S closed-set decision: stable 4-sign primary candidate for `GOOD`, `HELLO`, `HAVE`, and `KNOW`.
- E4-S OOV/confusion finding: withheld `SORRY` test rows were predicted as `GOOD` for `30/30` rows in all three seeds, with high confidence.
- E4-T runner: `pipeline/rgb/e4_t_router_simulation.py`.
- E4-T run directory: `artifacts/recognition_upgrade/e4_generalization/e4_t_router_simulation_01`.
- E4-T structural check passed, but the simple threshold router gate failed.
- Best scanned policy: confidence `0.98`, margin `0.90`, `GOOD` confidence `0.99999`; mean accepted precision with OOV `0.9561`, minimum accepted precision `0.9000`, mean active coverage `0.6439`, maximum `SORRY` false-accept rate `0.2000`.
- Decision: do not repeat softmax-threshold-only router tuning for `SORRY -> GOOD`. Next experiment should be a focused specialist/data-repair step with richer evidence or targeted review.

### E4-U Confusion Evidence Package Prepared - 2026-08-02

- Package document: `E4_U_CONFUSION_EVIDENCE_PACKAGE.md`.
- Runner: `pipeline/rgb/e4_u_confusion_evidence.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_u_sorry_good_evidence_01`.
- Target confusion: `SORRY -> GOOD`.
- Source runs: E4-S stable-primary, E4-T router simulation, and E4-J raw-video manifest.
- Prepared evidence rows: `60` total, `30` held-out true `GOOD` primary-reference rows and `30` held-out true `SORRY` confusion-target rows.
- Generated panels: `60`; panel failures `0`.
- Main outputs: `review/confusion_evidence_manifest.csv`, `contact_sheets/primary_reference_test.jpg`, and `contact_sheets/confusion_target_test.jpg`.
- Structural check passed with `--require-panels`.
- Decision: use this package to choose the next bounded specialist/data-repair experiment. Do not inspect every sign one by one, do not rerun threshold-only routing, and do not start Android/export/broad expansion.


### E4-V GOOD/SORRY Specialist Package Prepared - 2026-08-02

- Package document: `E4_V_SORRY_GOOD_SPECIALIST_PACKAGE.md`.
- Runner: `pipeline/rgb/e4_v_sorry_good_specialist.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01`.
- Target group: `GOOD` vs `SORRY`, representing the proven high-confidence `SORRY -> GOOD` false commit.
- Dataset source: E4-J raw-video manifest and landmark tensor, informed by E4-U evidence.
- Dataset rows: `100`; split train/validation/test `30/10/60`; class-balanced in every split.
- Branches: `landmark_binary_control` and `rgb_upper_body`.
- RGB settings: `8` frames, `160` image size, `upper_body_center`, frozen `MobileNetV3Small` ImageNet encoder, small Conv1D temporal head.
- Smoke passed for both branches; structural check passed with `--require-smoke`.
- Next action: user runs full E4-V training and final check. Passing E4-V would authorize a broader specialist/router simulation only, not Android/export.

### E4-V ID Clarification - 2026-08-02

The original dynamic-mixed roadmap row used `E4-V` for a later mixed-recognizer offline simulation. After E4-T failed and E4-U became an evidence package, the active package ID `E4-V` now refers to the `GOOD/SORRY` specialist proof. The later mixed-recognizer simulation remains required, but its active ID must be assigned after the specialist result is evaluated to avoid confusing it with this package.

### E4-V GOOD/SORRY Specialist Result - 2026-08-02

- Result document: `E4_V_SORRY_GOOD_SPECIALIST_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_v_sorry_good_specialist_01`.
- Structural check passed with `--require-smoke --require-metrics`.
- Landmark binary control passed: mean/latest/min test `0.9667`, mean/min `SORRY` recall `0.9667`, stable across seeds `101/202/303`.
- RGB upper-body failed: mean latest test `0.7833`, minimum latest test `0.5000`, mean `SORRY` recall `0.5889`, minimum `SORRY` recall `0.0000`; seed `303` collapsed to all `GOOD`.
- Decision: do not use current upper-body RGB as the first specialist for this group. Use a lightweight landmark binary specialist first.
- Next action: prepare offline mixed simulation with E4-S primary plus conditional `GOOD/SORRY` landmark specialist, then measure whether it preserves true `GOOD` and recovers `SORRY` without harming other primary signs.

### E4-W Mixed Landmark Specialist Simulation Result - 2026-08-02

- Result document: `E4_W_MIXED_LANDMARK_SPECIALIST_SIMULATION_RESULT.md`.
- Runner: `pipeline/rgb/e4_w_mixed_landmark_specialist_simulation.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_w_mixed_landmark_specialist_simulation_01`.
- Source runs: E4-S stable primary and E4-V GOOD/SORRY specialist.
- Simulated decision path: primary `GOOD/HELLO/HAVE/KNOW`; route primary `GOOD` predictions through the GOOD/SORRY landmark specialist; final classes `GOOD`, `HELLO`, `HAVE`, `KNOW`, `SORRY`.
- Test rows: `118` total, with `88` active known-sign test rows and `30` withheld `SORRY` rows.
- Primary-alone mean combined accuracy: `0.7345`; primary `SORRY` recall: `0.0000`.
- Mixed mean accuracy: `0.9718`; minimum seed accuracy: `0.9661`; mean/min `SORRY` recall: `0.9667`; mean/min `GOOD` recall: `0.9667`; mean gain over primary: `0.2373`; max false `GOOD -> SORRY` correction rate: `0.0333`.
- Structural check passed with `--require-metrics --require-predictions`.
- Decision: routed landmark specialist is promising enough for broader offline routed-system validation. Do not export to Android or production yet; next gate must add no-sign/OOV and source-disjoint checks.

### E4-X Routed System Validation Result - 2026-08-02

- Result document: `E4_X_ROUTED_SYSTEM_VALIDATION_RESULT.md`.
- Runner: `pipeline/rgb/e4_x_routed_system_validation.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_x_routed_system_validation_01`.
- Source runs: E4-S stable primary, E4-V GOOD/SORRY specialist, and E2e-C0 `n0_capture_06`.
- Simulated decision path: E4-S primary -> conditional GOOD/SORRY specialist -> confidence accept/reject -> final class or `NO_SIGN`.
- Dataset rows: `451` total; validation/test `97/238`; sources were `221` E4-S active rows, `50` E4-S withheld SORRY rows, and `180` reviewed N0 rows represented as zero-landmark/no-frame sequences.
- Selected validation policy: primary confidence `0.95`, specialist confidence `0.50`.
- Test result: mean accepted precision `0.9798`, minimum accepted precision `0.9739`, mean positive coverage `0.9746`, minimum positive coverage `0.9661`, max zero-landmark N0 false-commit rate `0.0000`, mean/min SORRY recall `0.9667`, mean/min GOOD recall `0.9667`.
- Structural check passed with `--require-metrics --require-predictions`.
- Decision: routed system passes the zero-landmark no-hand probe, but real MediaPipe-extracted N0/P1 feature validation remains required before Android/export.

### E4-Y Real No-Sign Feature Validation Result - 2026-08-02

- Result document: `E4_Y_REAL_NOSIGN_FEATURE_VALIDATION_RESULT.md`.
- Runner: `pipeline/rgb/e4_y_real_nosign_feature_validation.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_y_real_nosign_feature_validation_01`.
- E4-Y extracted real MediaPipe/schema v3.0 `[96,258]` windows from reviewed E2e-C0 N0/P1 footage, then evaluated the E4-X routed policy.
- Bounded probe rows: `24` N0 and `24` P1; no-sign validation/test split `16/32`; combined test rows after adding positives: `150`.
- Feature quality: N0 mean hand-hit `0.0130`, P1 mean hand-hit `0.8359`, pose-hit `1.0000` for both.
- Structural check passed with `--require-metrics --require-predictions`, but the recognition false-commit gate failed.
- Test summary: mean accepted precision `0.7844`, minimum accepted precision `0.7687`, positive coverage `0.9746`, max real no-sign false-commit rate `0.9688`, GOOD/SORRY recall `0.9667`.
- False commits were severe: N0 false commits ranged `13/16` to `16/16`; P1 false commits ranged `13/16` to `15/16` by seed.
- Decision: Android/export remains blocked. Next step is a signing/no-sign gate experiment before the routed recognizer can commit glosses.

### E4-Z Signing/No-Sign Gate Result - 2026-08-02

- Result document: `E4_Z_SIGNING_GATE_RESULT.md`.
- Runner: `pipeline/rgb/e4_z_signing_gate.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_z_signing_gate_01`.
- E4-Z compared rule-based motion/presence gates and a tiny learned summary-feature MLP before the E4-S/E4-V routed recognizer.
- Dataset rows: `319`; sources were `221` E4-S active rows, `50` withheld SORRY rows, `24` N0 rows, and `24` P1 rows from E4-Y.
- Structural check passed with `--require-metrics`, but the gate failed.
- Rule gates removed N0/P1 false commits but destroyed positive coverage (`~0.32` to `0.40`) and reduced SORRY recall to `0.0000`.
- Learned summary MLP improved coverage to `0.5169` and kept max no-sign false-commit rate to `0.09375`, but SORRY recall remained unacceptable: mean `0.1111`, min `0.0000`.
- Decision: do not proceed to Android/export. Next step is E4-AA no-sign dataset expansion and stronger temporal signing-gate design.

### E4-AA No-Sign Temporal Gate Package Prepared - 2026-08-02

- Package document: `E4_AA_NOSIGN_TEMPORAL_GATE_PACKAGE.md`.
- Runner: `pipeline/rgb/e4_aa_nosign_temporal_gate.py`.
- Smoke run: `artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_smoke_01`.
- E4-AA expands from E4-Z by building real MediaPipe/schema v3.0 no-sign windows from reviewed N0/P1 captures and training a small temporal Conv1D signing/no-sign gate before the E4-S/E4-V routed recognizer.
- Smoke status: prepared `[4,96,258]` no-sign features, trained one seed for one epoch, wrote metrics, and structural check passed. This smoke is wiring-only and is not an accuracy decision.
- Resume controls added: `--prepare-only` and `--train-only`; completed clip caches and completed dataset outputs are reused.
- Next action: user runs full E4-AA at `artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_01`, then checks with `--require-metrics`. No Android/export or production replacement is authorized before full metrics are evaluated.

### E4-AA Full No-Sign Temporal Gate Result - 2026-08-02

- Result document: `E4_AA_NOSIGN_TEMPORAL_GATE_RESULT.md`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_01`.
- Structural check passed, but the experiment gate failed.
- E4-AA no-sign dataset: `288` rows shaped `[288,96,258]`, with N0 `180` and P1 `108`.
- E4-AA fixed most no-sign false commits: max test no-sign false commit rate `0.0147`.
- E4-AA failed low-motion sign preservation: mean/min SORRY recall `0.1222/0.0000`, and minimum positive coverage `0.6780`.
- Decision: no Android/export. Test conservative threshold/uncertainty policy before changing gate architecture.

### E4-AB Conservative Gate Policy Result - 2026-08-02

- Result document: `E4_AB_CONSERVATIVE_GATE_POLICY_RESULT.md`.
- Runner: `pipeline/rgb/e4_ab_conservative_gate_policy.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_ab_conservative_gate_policy_01`.
- E4-AB reuses E4-AA trained gate models and sweeps conservative thresholds selected to protect `SORRY`/positive coverage.
- Structural check passed, but the experiment gate failed.
- Compared with E4-AA, mean SORRY recall improved from `0.1222` to `0.6778`, mean positive coverage improved from `0.7345` to `0.8983`, and max no-sign false commit remained acceptable at `0.0441`.
- However, seed `202` still produced test SORRY recall `0.1000`; probability inspection showed true SORRY windows overlapped no-sign under that model.
- Decision: threshold tuning alone is insufficient. Next step is E4-AC low-motion-aware gate training/objective, not Android/export or broad vocabulary expansion.

### E4-AC Low-Motion-Aware Signing Gate Result - 2026-08-02

- Result document: `E4_AC_LOW_MOTION_AWARE_GATE_RESULT.md`.
- Runner: `pipeline/rgb/e4_ac_low_motion_aware_gate.py`.
- Best run directory: `artifacts/recognition_upgrade/e4_generalization/e4_ac_low_motion_aware_gate_01`.
- E4-AC retrained the E4-AA temporal signing/no-sign gate with explicit low-motion `SORRY` weighting.
- Structural check passed, but the strict experiment gate failed narrowly.
- Best run metrics: mean/min accepted precision `0.9548/0.9492`, mean/min positive coverage `0.9746/0.9661`, max no-sign false commit `0.0441`, mean/min GOOD recall `0.9667/0.9667`, mean/min SORRY recall `0.9667/0.9667`.
- E4-AC is the first gate result that preserves SORRY while controlling no-sign false commits, but it is not approved for Android/export because min accepted precision is below `0.95` and the no-sign dataset remains small.
- Decision: use E4-AC as the basis for the next gate iteration. Next step should focus on false-commit review/hard-negative expansion, especially P1/N0 windows predicted as `HELLO`, not vocabulary expansion or Android integration.

### E4-AD False-Commit Review Result - 2026-08-02

- Result document: `E4_AD_FALSE_COMMIT_REVIEW_RESULT.md`.
- Runner: `pipeline/rgb/e4_ad_false_commit_review.py`.
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_ad_false_commit_review_01`.
- Structural check passed with panels.
- Generated `51` panels: `28` false commits and `23` hard-negative candidates.
- Residual false commits are concentrated as no-sign -> `HELLO`: `test:N0->HELLO=2`, `test:P1->HELLO=7`, `train:P1->HELLO=3`, `val:P1->HELLO=15`; one train P1 row became `KNOW`.
- Decision: the remaining gate error is mostly HELLO-like ordinary-hand no-sign, especially P1. Test false commits are diagnostic only and must not be added to training.

### E4-AE Hard-Negative Weighted Gate Result - 2026-08-02

- Result document: `E4_AE_HARD_NEGATIVE_GATE_RESULT.md`.
- Runner: `pipeline/rgb/e4_ae_hard_negative_gate.py`.
- Corrected run directory: `artifacts/recognition_upgrade/e4_generalization/e4_ae_hard_negative_gate_02`.
- Structural check passed, but experiment gate failed.
- Upweighted `12` train-split hard negatives from E4-AD with hard-negative weight `6.0`.
- Metrics: mean/min accepted precision `0.9605/0.9417`, mean/min positive coverage `0.9746/0.9661`, max no-sign false commit `0.0882`, mean/min GOOD recall `0.9667/0.9667`, mean/min SORRY recall `0.9667/0.9667`.
- Decision: naive hard-negative weighting is not the solution; it worsened minimum precision compared with E4-AC. The best current gate remains E4-AC `01`, but it is still not Android/export approved.

### E4-AF Safety-Floor Acceptance Policy And E5-A Batch Pivot - 2026-08-02

| ID | Experiment | Control / variables | Go | No-go / fallback |
|---|---|---|---|---|
| E4-AF | Safety-floor acceptance policy | Reuse E4-AC gate, E4-AD false-commit evidence, E4-S primary, and E4-V specialist; compare baseline, HELLO-specific commit floor, temporal stability, and uncertainty/reject policy | min accepted precision >= `0.95`, min positive coverage >= `0.90`, max no-sign false commit <= `0.05`, GOOD/HELLO/SORRY recall >= `0.90`; then proceed to E5-A | collect bounded HELLO-like no-sign expansion set; do not continue generic threshold/weight sweeps |
| E5-A | Large dual-source candidate screening | Screen `50-100` candidate glosses where feasible from `F:\ASL DATASET\ASL CITIZEN` and `F:\ASL DATASET\local`; use existing features first; produce Tier A/B/C/D decisions | ranked Tier-A primary batch, confusion groups, and deferred signs with source-aware evidence | reduce candidate set, request extraction only for high-value missing signs, or collect data where signer/source support is insufficient |

E4-AF is intentionally short. It is the safety gate that prevents false translation. E5-A is the batch-scale step that prevents the project from taking one sign at a time.

### E4-AF Result And E4-AG Next Gate - 2026-08-02

| ID | Experiment | Control / variables | Go | No-go / fallback |
|---|---|---|---|---|
| E4-AF | Acceptance-policy sweep | Reused E4-AC gate and E4-S/E4-V routed recognizer; tested baseline and HELLO-specific gate floors | **NO-GO:** structural pass, min accepted precision `0.9492`, policy-only cannot remove HELLO false commits without hurting HELLO recall/coverage | Add targeted HELLO-like no-sign data; do not repeat generic threshold sweeps |
| E4-AG | HELLO-like no-sign expansion | **COMPLETE/PASS:** added 116 reviewed HELLO-like P1 no-sign rows; expanded tensor to `[404,96,258]`; retrained E4-AC gate | min accepted precision `0.9739`, coverage `0.9661`, max no-sign false commit `0.0000`, GOOD/SORRY recall `0.9667`; proceed to E5-A | Android/export still blocked until later device and streaming gates |



### E5-A Result And E5-B Next Pilot - 2026-08-02

| ID | Experiment | Control / variables | Go | No-go / fallback |
|---|---|---|---|---|
| E5-A | 236-label dual-source batch screen | Read ASL Citizen + combined local feature tensors; tier signs by ASL support, local support, prior E4 evidence, and E4-AG safety state | **COMPLETE/PASS:** 236 inspected, 67 local-supported labels, only `WANT2` strict next primary candidate | Use one-signer signs only for diagnostic/data-collection queue, not production primary |
| E5-B | ASL-led 50-class primary diagnostic | ASL Citizen-led selected classes with local rows included where available; known hard/confusion signs excluded from primary | stable controls remain strong, aggregate and per-class test behavior are materially above random, no broad collapse, signs can be tiered into keep/repair/specialist/defer | reduce to a smaller primary candidate batch, route confusing signs to specialists, or repair labels/data before Android/export |
### E5-B Result, E5-C Tiering, And E5-D Next - 2026-08-03

| ID | Experiment | Control / variables | Go | No-go / fallback |
|---|---|---|---|---|
| E5-B | ASL-led 50-class primary diagnostic | Completed 50-class Conv1D landmark model on ASL Citizen + local supplementary `[96,258]` features | **DIAGNOSTIC SIGNAL ONLY:** mean latest test `0.4897` vs random `0.0200`, no one-class collapse | **NO EXPORT:** stable controls `HELLO` and `KNOW` regressed; use E5-C tiers |
| E5-C | 50-class metrics tiering | Per-class latest-policy seed stability, train/test gap, confusion pairs, source counts | **COMPLETE/PASS:** 9 strong + 6 guarded reduced-primary candidates identified | E5-B 50-class model remains diagnostic only; prepare E5-D reduced-primary validation |
| E5-D | Reduced-primary validation | Train/evaluate reduced primary vocabulary from E5-C; keep hard signs excluded; later evaluate routed `SORRY` and no-sign gate offline | stable controls retained, per-class accuracy improves over E5-B, confusion drops, no collapse | shrink vocabulary further, repair `HELLO/KNOW/SEEM`, or add specialist routing before runtime work |
### E5-D Package Prepared - 2026-08-03

| ID | Experiment | Control / variables | Go | No-go / fallback |
|---|---|---|---|---|
| E5-D | Reduced-primary validation package | Prepared 15-class reduced primary from E5-C vocabulary; existing schema v3.0 `[96,258]`; no extraction | smoke/check pass; user runs full training next | if training fails or reduced set still collapses, shrink vocabulary further or repair specific confusion groups before routed validation |
| E5-D result | Reduced-primary validation result | Completed 15-class Conv1D landmark validation on ASL Citizen-led + local supplementary `[96,258]` rows | **USEFUL OFFLINE PASS:** mean latest test `0.6933`, mean best test `0.7382`, no prediction collapse; reduced-primary strategy is better than E5-B | **NO EXPORT:** weak signs and confusion groups remain; prepare E5-E tiering/decision before routed simulation |
| E5-E | Reduced-primary tiering/decision | Consume E5-D metrics; split 15 signs into safe primary, guarded primary, confusion-group, and defer/repair tiers | defines a smaller candidate primary subset and explicit confusion groups for routed validation | reduce vocabulary further or collect/repair data before runtime work |
| E5-E result | Reduced-primary decision pass | Completed metrics-only tiering over E5-D 15-sign result | **DECISION PASS:** select 7-sign primary candidate `WASH2`, `THINK`, `TAKE`, `MEET`, `GOOD`, `SELL`, `STAND2`; register confusion groups | prepare E5-F routed simulation; do not export E5-D as-is |
| E5-F | Reduced-primary routed simulation | E4-AG no-sign gate + E5-E primary subset + existing GOOD/SORRY specialist evidence + reject/commit policy | accepted precision/coverage and per-class recall pass offline gates without real no-sign false commits | shrink subset, adjust reject policy, or keep weak signs deferred |
| E5-F result | Reduced-primary routed simulation | Completed replay of E5-D 15-class model restricted to E5-E 7-sign subset with E4-AG no-sign gate and unsupported/OOV pressure | **NO-GO:** strict policy safe but coverage too low; relaxed policy improves coverage but precision/class recall fail | prepare E5-G clean 7-class retrain; no Android/export |
| E5-G | Clean 7-class primary retrain | Train only E5-E subset `WASH2`, `THINK`, `TAKE`, `MEET`, `GOOD`, `SELL`, `STAND2`; rerun no-sign/OOV routed simulation | higher recall and accepted precision than E5-F while preserving no-sign safety | shrink subset, repair data, or return to tiering |


## 2026-08-03 - E5-G/E5-H Reduced Primary Routed Evidence
- E5-G clean 7-class closed-set primary training passed structurally and improved mean latest test accuracy to `0.8472`, with strong `WASH2`, `THINK`, and `TAKE` but weaker `MEET` and `STAND2`. See `E5_G_CLEAN_7_PRIMARY_RESULT.md`.
- E5-H routed simulation was no-go for both full 7-sign and stable-3 commit subsets. Confidence thresholds could not preserve recall while rejecting unsupported signs. See `E5_H_CLEAN_7_ROUTED_SIM_RESULT.md`.
- Decision: do not export to Android. Next required action is E5-I explicit open-set/rejection training or auxiliary accept/reject modeling, not more vocabulary shrinking or softmax threshold tuning.


## 2026-08-03 - E5-I Open-Set Reject Head Result
- E5-I added a two-head landmark model: sign softmax plus supported-vs-unsupported/no-sign accept head. See `E5_I_OPEN_SET_REJECT_HEAD_RESULT.md`.
- Full 7-sign routed result remained no-go: mean/min accepted precision `0.8985/0.8333`, mean/min positive coverage `0.2778/0.2083`, max unsupported false commit `0.0220`, max no-sign false commit `0.0110`, min class recall `0.0000`.
- Stable-3 diagnostic remained no-go but improved coverage: mean/min accepted precision `0.7129/0.5532`, mean/min positive coverage `0.5833/0.4375`, max unsupported false commit `0.1170`, max no-sign false commit `0.0220`.
- Decision: shared accept/reject is useful but too blunt. Next required action is E5-J class-conditioned rejection/per-class accept policy before Android/export.

## 2026-08-03 - E6 Production Recognition Architecture Matrix

E5-J is reclassified as a possible E6-3 method, not the next guaranteed fix. The active next work is E6-0/E6-1.

| ID | Experiment | Control / variables | Go | No-go / fallback |
|---|---|---|---|---|
| E6-0 | Freeze baseline and evidence inventory | current Android assets, schema v3.0, production model/vocab/config, E4/E5 run docs | hashes, protected files, and current no-go evidence recorded; fallback path unambiguous | stop; repair baseline docs before new experiments |
| E6-1 | Dataset/representation audit and learning curve | ASL Citizen + local + E5 tensors; signer/source/provenance counts; current v3.0 rows | feasible product-core batch and data gaps are quantified; leakage/source risks documented | collect/clean data or reduce product-core vocabulary before more modeling |
| E6-2 | Richer landmark-feature control | v3.0 `[96,258]` vs experiment-only kinematic/mask/time features on same splits/seeds | routed/open-set metrics improve materially without worse false commits or severe class regressions | keep v3.0; do not add schema complexity |
| E6-3 | Frozen-embedding rejection comparison | frozen v3.0 MSP control vs energy control vs predicted-class shrinkage-Mahalanobis; no classifier/rejector training | valid operating point in all seeds; fresh precision/coverage and subtype FAR gates pass; stress `KNOW -> HELLO` accepted false commits fall `>=70%` without zero-recall classes | stop rejection tuning; improve negative diversity or preserve failure for E6-4/E6-5 |
| E6-4 | Confusion registry mining | predictions from E6-2/E6-3 across seeds/sources | reproducible confusion groups with clear trigger rules | keep unstable signs deferred |
| E6-5 | First justified specialist proof | registered `KNOW/HELLO`; frozen five-way and pair-restricted controls vs v3 TCN specialist vs geometry TCN specialist | both difficult AppHear views improve, historical behavior is preserved, all per-member/seed gates pass; geometry must materially beat v3 to justify complexity | defer/recollect `KNOW`; RGB remains blocked unless a later hand-crop package is genuinely different |
| E6-6 | Offline routed-system simulation | primary + rejection + registry + any passed specialists | release-style offline gates pass on held-out signers with no-sign/OOV pressure | simplify system, shrink vocabulary, or return to data work |
| E6-7 | Android shadow feasibility | quantized experimental assets, default-off flag, fallback | parity, p95 latency, FPS, memory, thermal, and rollback gates pass | feature flag off; production v3.0 remains active |

### E6-2 Refined Contract - 2026-08-09

E6-2 is no longer a generic `masks + dt + velocity + bones + angles` sweep. That wording risked
repeating E3-B6/B7. The approved-for-review architecture is one `[96,444]`
`apphear.landmark_geometry.v0` candidate against the frozen repaired-validation v3.0 control.

Meaningful differences from E3-B6/B7 are hand-local palm-scale geometry, joint cosines, palm
orientation, pose-head relations, broad-encoder zero-extension warm start, and the repaired
five-sign cross-source benchmark. Naive velocity and acceleration are excluded.

Primary gate: fresh top-1 `>=0.9089`, mean/min-seed fresh `KNOW >=0.70/0.60`, stress
`KNOW >=0.30`, stress overall `>=0.7273`, no stable-class fresh recall loss over `0.03`, and no
historical top-1 loss over `0.03`. Full details and failure paths are in
`E6_2_RICHER_LANDMARK_CONTROL_PLAN.md`.

Status: complete / strict no-go. Mean fresh top-1 improved from `0.8889` to `0.9456` and fresh
`KNOW` from `0.5611` to `0.8611`, but stress `KNOW` was only `0.0556`, stress top-1 missed its gate,
and `HAVE` regressed by `0.0444`. Keep v3.0, stop handcrafted feature iteration, and architect
E6-3 before implementation. See `E6_2_LANDMARK_GEOMETRY_RESULT.md`.

### E6-3 Refined Contract - 2026-08-09

The duplicate audit removes binary temporal gates, shared accept heads, one-vs-rest training,
OpenMax, and E6-2 geometry from the immediate experiment. E4-AA through E4-AG already cover the
temporal gate, E5-I already failed the shared head, and geometry would confound rejection with a
no-go representation.

The one approved comparison freezes the repaired-validation v3.0 TCN and evaluates MSP, fixed
temperature energy, and predicted-class shrinkage-Mahalanobis distance over the masked-mean
64-dimensional `tcn3_add` embedding. Class statistics use positive train only; thresholds use
repaired validation plus 547 historical development negatives only. Stress, fresh positives,
historical positives, and 560 one-signer fresh negatives remain evaluation-only.

Status: architecture review, package implementation, and nine-window real-data smoke complete. Full
negative extraction/evaluation is user-run next. Full data roles, metrics, diagnostic gates,
limitations, and stop conditions are in `E6_3_OPEN_SET_REJECTION_PLAN.md`; commands and smoke
evidence are in `E6_3_OPEN_SET_REJECTION_PACKAGE.md`.

### E6-3 Result - 2026-08-09

Full extraction passed for `1,107/1,107` negative windows from `804` videos. All three seeds and all
three methods failed to produce a valid development operating point. At positive coverage
`>=0.80`, best accepted precision ranged from `0.443` to `0.841`, below `0.95`. Enforcing subtype
false-accept floors reduced coverage to `0.006-0.404` and minimum supported-class recall to
`0.00-0.03`. Decision: strict no-go; no Android rejection component and no further threshold loop.
See `E6_3_OPEN_SET_REJECTION_RESULT.md`. E6-4 architecture review is next.

### E6-4 Result - 2026-08-09

Frozen mining produced 4,152 positive and 3,321 negative prediction rows with zero split sample or
signer overlap. Exactly one pair met the preregistered cross-view/cross-signer/all-seed rule:
`KNOW -> HELLO`, with 54 majority-confused samples across fresh and stress AppHear signers.
`SORRY -> HAVE` was strong only on the one-signer stress view and remains unregistered. Decision:
E6-4 evidence pass; architect one E6-5 `KNOW/HELLO` specialist proof only. See
`E6_4_CONFUSION_REGISTRY_RESULT.md`.

### E6-5 Prepared Package - 2026-08-09

Duplicate review removed the planned broad RGB/fusion branches because E3-B3, E3-C, and E4-V
already rejected the available upper-body RGB evidence. The prepared E6-5 package compares only
the seed-matched v3.0 and E6-2 geometry temporal specialists against frozen primary controls.
Pair inventories are `253/65/90/120/27` for train/validation/stress/fresh/historical, with exact
v3/geometry lineage and base-channel alignment. Real-data smoke and structural checks passed.
Full six-model training is the next action; E6-6 remains blocked. See
`E6_5_KNOW_HELLO_SPECIALIST_PLAN.md` and `E6_5_KNOW_HELLO_SPECIALIST_PACKAGE.md`.

### E6-5 Result And E6 Component Decision - 2026-08-09

E6-5 completed structurally, but neither specialist passed. The v3 specialist reached mean fresh
pair accuracy/`KNOW` recall `0.7972/0.5944` and stress `KNOW` `0.0556`. Geometry reached
`0.8444/0.6889` fresh and `0.0667` stress `KNOW`, with excessive seed variation. Pair restriction
also failed to materially change the primary result. No branch was selected.

Decision: defer `KNOW`; do not repeat the binary/geometry specialist on the same data. E6-6 is
blocked because E6-3 produced no valid rejector and E6-5 produced no valid specialist. E6-7 is
therefore blocked. See `E6_5_KNOW_HELLO_SPECIALIST_RESULT.md` and `E6_COMPONENT_DECISION.md`.

## 2026-08-03 - E6-0/E6-1 Duplicate And Dataset Audit Result

| ID | Experiment | Result | Decision |
|---|---|---|---|
| E6-0 | Baseline freeze | Complete. Current production model/vocab/config/schema/MediaPipe asset hashes recorded in `E6_0_BASELINE_FREEZE.md`. | Protected baseline verified; proceed only to audit/data work. |
| E6-1 | Consolidated E1-E5 evidence and dataset audit | Complete. Full experiment inventory and per-sign count tables written under `e6_audit_tables/`. Current data is insufficient for production-grade silent translation modeling. | **STOP MODELING.** E6-2 through E6-7 are blocked until a bounded product-core data-readiness package exists. |

Do not run E6-2/E6-3/E6-5/E6-6/E6-7 under a new name. Every future experiment must cite the closest previous E1-E5 experiment, the meaningful difference, and why the difference is enough to justify running.


## E6 Data-Readiness Stop Rule - 2026-08-03

Current decision: `E6_1_CONSOLIDATED_EVIDENCE_DATASET_AUDIT.md` and `PRODUCT_CORE_DATA_READINESS_PACKAGE.md` supersede the E5 modeling loop. No E6-2+ modeling experiment may start until the bounded product-core data-readiness gate passes.

Historical note: this 2026-08-03 blockade was later satisfied for the bounded five-sign diagnostic
through reviewed lineage, targeted collection, clean v3.0 extraction, broad-encoder transfer, and
validation repair. It remains binding for vocabulary expansion and production claims. The current
next action is the architecture-only E6-2 contract above.

Blocked until gate passes:

- richer feature-schema experiments;
- open-set/rejection experiments;
- specialist or RGB branches;
- routed simulations;
- TFLite export;
- Android shadow or production integration.

The only approved next work is a manifest-builder plan for `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`, `THINK`, `TAKE`, `SELL`, plus `WASH2` as a control/reserve. It must produce strict raw-video lineage, source-aware signer-disjoint splits, label-variant status, and no-sign/OOV coverage before any extraction or training resumes.

## Phase 1 Full-Vocabulary Baseline - Approved 2026-08-11

The preceding bounded product-core instruction is historical and is superseded for execution by
the approved full-vocabulary baseline. Its lineage and leakage lessons remain binding.

| ID | Experiment | Control / variables | Go | No-go / fallback | Status |
|---|---|---|---|---|---|
| P1-FV0 | Canonical 236-sign manifest | ASL Citizen primary; validated E6/local train-only supplements; protected ASL test and clean replay | full hashes, 236 train classes, zero signer leakage/duplicate/protected overlap | repair lineage; do not train | **PASS:** 8131 hashed rows; no errors |
| P1-FV0A | Versioned v3.0 tensor assembly | manifest-authorized features only; protected roles separate | shapes/masks/labels/hashes pass; 236 train classes; replay absent | repair assembler; do not train | **PASS:** full 217 MB package; no errors |
| P1-FV1 | Full-vocabulary landmark baseline | production streaming TCN vs mask-aware pooled TCN only; same 169,004 parameters, encoder initialization, v3.0 data, online low-FPS/geometric augmentation, seeds, optimizer, and epoch budget | validation-only branch selection across three seeds; protected test remains sealed until freeze | retain production TCN as control; diagnose data/classes before new architecture | **VALIDATION COMPLETE / SELECTION FROZEN:** production TCN mean top-1 `0.6712`, macro-F1 `0.6482`; masked TCN `0.6614` / `0.6439`; production branch and three checkpoints frozen; protected test not accessed |

P1-FV1 reports native/low-FPS top-1 and top-5, macro/per-class F1, worst classes, confusion groups,
missing-landmark robustness, calibration, and streaming false commits. It does not authorize ST-GCN,
richer geometry, specialists, rejection, RGB, TFLite export, or Android replacement.

The next authorized action is the one-time protected evaluation of the frozen production branch.
The evaluator requires an explicit confirmation flag, verifies all frozen hashes before loading
`test.npz`, writes an access receipt before inference, and refuses to overwrite a completed report.
Its temporal-stride and hand-dropout results are diagnostic proxies, not measured camera-FPS or
end-to-end streaming claims.

### P1-FV1 Protected Result - 2026-08-12

The frozen production-TCN three-seed ensemble completed the 2,620-row test exactly once for this
experiment: top-1 `0.6095`, top-5 `0.8866`, macro-F1 `0.5964`, worst-decile mean F1 `0.1741`, and
uncalibrated 15-bin ECE `0.2183`. Individual-seed top-1 was `0.5966`, `0.5889`, and `0.5828`;
ensemble gain over the best seed was `1.30` points. Signer top-1 ranged from `0.5588` to `0.6680`.
Four classes had zero recall and 58/236 classes had F1 below `0.50`.

Diagnostic top-1 drops were `0.73` points for stride-2, `2.40` for stride-3, and `2.79` for the
25% deterministic hand-dropout proxy. These are useful robustness indicators but are not Android
FPS or natural missing-detection measurements. The result is a **research baseline / Phase 2 error
registry, not a release candidate**. It misses the registered `0.85` top-1/macro-F1 floors and does
not evaluate no-sign/OOV, boundaries, phrase streaming, latency, or false commits.

Historical comparison: the earlier local-supplementary candidate reported `0.6172` top-1 and
`0.8683` top-5 on the same-size ASL Citizen test population. P1-FV1 is `0.76` points lower on top-1
and `1.83` points higher on top-5. Because this ASL test split was used in earlier experiments, it
is sealed from further P1-FV1 tuning but is not globally project-fresh evidence.

## Phase 2 Controlled Hybrid Preparation - 2026-08-12

| ID | Experiment | Input / change | Go | No-go / fallback | Status |
|---|---|---|---|---|---|
| P2-P0 | Phase 1 error registry | frozen ensemble predictions joined to exact test lineage | 236 rows, alignment gate, categories/hypotheses separated | repair join; no pilot | **PASS:** 236 signs registered |
| P2-P1 | RGB metadata feasibility | raw/Stage-E/span presence and localization metadata; no pixel extraction | synchronized lineage and explicit unknown crop quality | versioned re-extraction or exclude rows | **PASS WITH GAP:** 2,519 raw; 1,133 synchronized; 550 train |
| P2-P2 | Bounded ROI crop-quality audit | 120 detector-independent frames, three per selected sign; R0 direct/hold, R1 pose, R2 I320 diagnostic, R3 upper-body control; shared human gold and blinded route review | >=90% visible ROI, >=80% two-hand, >=85% reviewed usable, <=2% wrong/stale/swap, >=98% synchronization, >=90% triplet availability consistency; anatomical-side evidence required | stop route; collect/annotate new ROI evidence | **COMPLETE / ROBUST NO-GO:** 40-frame side adjudication complete; R1 `81.58%/67.57%/77.50%` coverage/two-hand/side; strict R1/R2 oracle `86.32%/74.32%/80.00%`, below every geometry/side gate; skip selector and P2-P3 dataset/training with current routes |
| P2-P2F | Causal optical-flow ROI feasibility | Same frozen 120 P2-P2 frames/gold; direct landmark ROI -> image-content optical flow -> existing pose fallback | Objectively exceed R1 and pass >=90% coverage, >=80% two-hand, >=98% side, >=90% consistency, >=98% sync, <=2% zero-hand false ROI before manual crop review | retire current hand-crop ROI stack; no RGB training | **COMPLETE / NO-GO / STOP:** coverage `80.53%`, two-hand `64.86%`, side `73.75%`, consistency `89.17%`, zero-hand false ROI `75%`; worse than R1 on localization despite better persistence; no crop review or tuning |
| P2-P3 | Four-branch hybrid pilot | A landmark, B RGB, C gated intermediate fusion, D RGB top-k reranker; 3 seeds | >=5-point top-1 and macro-F1 gains, <=2-point stable damage, ROI/data/fresh-eval gates | retain Phase 1; diagnose crop/data/fusion | **BLOCKED BY P2-P2 AND DATA DECISION** |

Do not repeat E3 upper-body frozen embeddings, naive concatenation, MediaPipe threshold/mode tuning,
or I320 retraining with the current negative data. P2-P2 is genuinely different only because it
uses the full Phase 1 error registry and pilot-specific synchronized lineage to compare existing
ROI routes before any recognition training.

## Phase 1 Shadow Follow-up - 2026-08-12

| ID | Experiment | Input/change | GO gate | Failure action | Status |
|---|---|---|---|---|---|
| P1-SHADOW | Frozen Phase 1 landmark ensemble Android shadow feasibility | Exact frozen seeds 101/202/303, v3.0 `[96,258]`, active 236-class vocab; separate default-off assets | Offline argmax parity >=98%, top-1 delta <=1 point; then device p50/p95, FPS, thermal, and zero commit/UI effect | keep flag off and remove candidate assets; active recognizer remains unchanged | **OFFLINE GO / DEVICE PENDING:** INT8 rejected at `88.28%` argmax agreement; float32 passed at `100%`, zero top-1 delta |

P1-SHADOW is a deployment measurement of already frozen Phase 1 evidence, not another landmark
training experiment and not a substitute for Phase 2 RGB. Improved ROI detection remains later
research and requires materially new localization evidence before P2-P3 can reopen.
