# Phase 2 Error Registry And RGB Feasibility Result

**Purpose:** Close Phase 1 and record the evidence-controlled preparation state for a bounded
40-sign isolated landmark/RGB pilot.

**Scope:** Offline registry, raw-lineage, Stage-E metadata, ROI-strategy, and experiment-contract
preparation only. No RGB frames were decoded, no crops were extracted, no model was trained, and
no Android or v3.0 production artifact was changed.

**Status:** COMPLETE / PREPARATION PASS / PIXEL-CROP AND TRAINING GATES NOT YET PASSED.

**Last updated:** 2026-08-12.

## Verified Inputs

- Frozen Phase 1 branch: `production_streaming_tcn`, seeds `101/202/303`.
- Protected result: 2,620 clips, top-1 `0.6095`, top-5 `0.8866`, macro-F1 `0.5964`,
  worst-decile mean F1 `0.1741`, and uncalibrated ECE `0.2183`.
- Prediction/test row alignment was checked against exact label and signer arrays before joining.
- Canonical manifest: 8,131 raw-hashed rows with sample ID, source, signer, split, role, raw path,
  Stage-E path, span path, and v3.0 feature lineage.
- Preparation run:
  `artifacts/recognition_upgrade/phase2_preparation/phase2_prep_01`.
- Runner: `pipeline/rgb/phase2_prepare.py`.

## Error Registry

All 236 signs are registered in `error_registry.csv` and `error_registry.json`.

| Verified metric category | Signs |
|---|---:|
| Landmark stable | 48 |
| Confusion heavy | 150 |
| Zero/very-low recall | 21 |
| Landmark moderate | 40 |
| Insufficient evidence | 8 |

Categories may overlap. The registry also records two explicitly non-factual hypotheses:

- 109 signs where appearance evidence may help because top-5 substantially exceeds top-1;
- 10 signs requiring dataset/variant review based on variant naming or very weak top-5 support.

These hypotheses do not authorize relabeling or RGB promotion. Pixel and label evidence must be
reviewed first.

The strongest reranking opportunities include `HAVE` (top-5 rescue `1.00`), `MONEY1` (`0.909`),
`PERSON` (`0.857`), `NOW` (`0.818`), `MOST` (`0.800`), `BUT` (`0.778`), `PAPER` (`0.750`), and
`KNOW` (`0.692`). Strong directional confusions include `MONEY1 -> BUY`, `NOW -> TODAY`,
`HAVE -> YOUNG`, `PAPER -> SCHOOL`, `OR -> THEN`, and `TIRED -> YOUNG`.

## RGB Feasibility

The preparation scan opened existing metadata for all 8,131 Phase 1 lineage rows. It did not
decode video pixels.

For the selected pilot:

- 2,519 raw videos are present;
- 1,133 rows have canonical synchronized raw-video + Stage-E + span metadata;
- synchronized rows comprise 550 ASL Citizen train, 138 validation, and 445 historical test rows;
- 1,386 AppHear/local/replay/diagnostic rows have raw video but no canonical Stage-E/span pair and
  are excluded from hybrid training until a separately versioned re-extraction is approved;
- immediately eligible ASL training support is only 10-16 clips per sign.

The metadata scan reports direct left/right presence, two-hand presence, pose-fallback opportunity,
edge risk, near-face rate, motion proxy, timestamps, signer, source, split, and role. It deliberately
marks pixel blur, crop containment, stale/wrong-hand assignment, and true crop usability as
unmeasured. Metadata availability is not equivalent to a usable RGB crop.

## ROI Decision

No existing ROI source is promoted:

- MediaPipe VIDEO reached only 57.5% known-visible availability in the prior cadence result.
- Pose recovery reached 79.2% metadata availability, but only 23.7% of recovered crops were marked
  usable in the prior manual evidence.
- I320 reached 67.26% hand availability and 41.03% complete two-hand recall at its valid threshold.
- Upper-body RGB and frozen MobileNet fusion previously overfit and are not fallback candidates.

The next crop smoke compares, rather than assumes, four routes: direct MediaPipe + 100 ms hold;
pose-tracked/fallback recovery; I320 diagnostic proposals with landmark-side assignment; and an
expanded upper-body availability control. The promotion targets are 90% known-visible ROI coverage,
80% complete two-hand coverage, 85% reviewed crop usability, and <=2% wrong/stale/side-swap rate.
These are preregistered engineering targets, not current results.

## Selected 40-Sign Pilot

`TABLE`, `WE`, `WORK`, `CLOTHES`, `DAY`, `VISIT`, `GOOD`, `HELLO`, `SORRY`, `HAVE`, `KNOW`,
`THINK`, `TAKE`, `SELL`, `MONEY1`, `BUY`, `NOW`, `TODAY`, `PAPER`, `SCHOOL`, `YOUNG`, `OR`,
`THEN`, `TIRED`, `LEAVE`, `WHO`, `PERSON`, `MOST`, `BUT`, `HERE`, `WASH2`, `DONTKNOW`, `TEACH2`,
`EAT1`, `HOME`, `BECAUSE`, `SLEEP`, `COMPUTER`, `STAY`, `STILL`.

Selection is deterministic and recorded per sign. It contains six high-F1 landmark controls, the
historical E6 core, strongest confusion groups, zero/very-low-recall signs, top-5 reranking
candidates, and relative low/high-motion, near-face, one/two-hand, and ROI-difficulty cases.

## Pilot Contract

The four branches are:

- A: frozen Phase 1 landmark control;
- B: trainable shared-weight left/right hand-crop RGB encoder;
- C: quality-gated intermediate fusion with landmark branch protection;
- D: landmark top-k candidate reranking using RGB evidence.

Intermediate fusion and reranking are competing hypotheses. A candidate must improve mean top-1
and macro-F1 by at least five absolute points over A, beat A on at least two of three seeds and in
the mean, limit stable-control F1 damage to two points, and pass the ROI gate. Confusion-group,
zero-recall, signer-spread, crop-source, latency, and model-size results are also mandatory.

The historical ASL Citizen test cannot be used for Phase 2 model selection and is no longer a
globally fresh claim because its class failures selected the pilot. Phase 2 requires signer-disjoint
development folds and fresh signer/domain evidence before any scale-up claim.

## Decision And Next Action

Phase 1 is closed and remains the frozen control. Do not train the four branches yet. The next
approved work is one bounded pilot-specific RGB decode and crop-quality smoke. It must establish
whether any ROI route produces usable synchronized hand evidence. If no route passes, stop the
hand-crop pilot or collect/annotate materially new ROI data; do not hide missing crops through
fusion. If a route passes, decide whether the 550 synchronized training clips are sufficient for a
shared encoder or whether selected AppHear/local videos need versioned Stage-E re-extraction.

## Source Of Truth

- `artifacts/recognition_upgrade/phase2_preparation/phase2_prep_01/summary.json`
- `error_registry.{csv,json}`
- `rgb_feasibility_manifest.csv`
- `rgb_feasibility_summary.json`
- `pilot_vocabulary.json`
- `roi_strategy.json`
- `pilot_experiment_contract.json`
- `PHASE2_PREPARATION_RESULT.md`

## Risks And Open Questions

- Ten to sixteen synchronized training clips per sign may repeat prior RGB overfitting.
- Pixel crop quality remains unknown for the selected signs.
- AppHear/local supplements require new synchronized extraction before hybrid use.
- No current ROI source has passed the required reliability gate.
- Fresh signer/domain evaluation data is not yet identified.

## P2-P2 Implementation Status - 2026-08-12

P2-P2 is implemented in `pipeline/rgb/phase2_p2_roi_audit.py`. The final evidence package is
prepared under `artifacts/recognition_upgrade/phase2_roi_audit/p2_p2_roi_audit_02`:

- 120 detector-independent frames, exactly three per pilot sign;
- 99 training-split and 21 validation-split clips across 29 signers;
- canonical Phase 1 manifest hash
  `8C1FAB3DF04A0240B5A178853B2206408806958AFEBDD19BD3D44D6FCA606571`;
- synchronized before/center/after reference panels;
- no model training, no RGB training dataset, and no Android changes.

The workflow is intentionally staged:

1. `review-gold` records every visible hand, anatomical side, and hard condition.
2. `build-routes` runs R0/R1/R2/R3 on the same accepted frames and creates blinded temporal crop
   panels. R2 reloads the existing frozen I320 TFLite model at its frozen development threshold;
   it does not retrain it.
3. `review-routes` records usability, missing/incomplete hands, clipping, blur, wrong side, stale
   synchronization, temporal inconsistency, and low detail.
4. `evaluate` calculates the registered gate and writes the only valid P2-P2 GO/NO-GO decision.

Developer-run commands from the project root:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.phase2_p2_roi_audit review-gold `
  --run-dir artifacts\recognition_upgrade\phase2_roi_audit\p2_p2_roi_audit_02

.\.venv\Scripts\python.exe -m pipeline.rgb.phase2_p2_roi_audit check `
  --run-dir artifacts\recognition_upgrade\phase2_roi_audit\p2_p2_roi_audit_02 `
  --require-gold-reviewed

.\.venv\Scripts\python.exe -m pipeline.rgb.phase2_p2_roi_audit build-routes `
  --run-dir artifacts\recognition_upgrade\phase2_roi_audit\p2_p2_roi_audit_02

.\.venv\Scripts\python.exe -m pipeline.rgb.phase2_p2_roi_audit review-routes `
  --run-dir artifacts\recognition_upgrade\phase2_roi_audit\p2_p2_roi_audit_02

.\.venv\Scripts\python.exe -m pipeline.rgb.phase2_p2_roi_audit evaluate `
  --run-dir artifacts\recognition_upgrade\phase2_roi_audit\p2_p2_roi_audit_02

.\.venv\Scripts\python.exe -m pipeline.rgb.phase2_p2_roi_audit check `
  --run-dir artifacts\recognition_upgrade\phase2_roi_audit\p2_p2_roi_audit_02 `
  --require-gold-reviewed --require-routes-reviewed --require-result
```

Current decision: **PENDING EVIDENCE, NOT GO**. RGB dataset creation remains blocked until both
reviews and evaluation finish. Unit tests, Ruff, mypy, real 40-sign preparation smoke, full
120-frame preparation, artifact check, and a Windows I320 reload/inference probe passed.

The earlier `p2_p2_roi_audit_01` package is superseded and must not be reviewed: its selection
overweighted direct-detection failures (107/120 rows below 50% direct availability). The corrected
`_02` package deliberately includes per-sign recovery stress, articulation/near-face/two-hand
stress, and ordinary high-availability controls. Its metadata distribution has 50/120 rows below
50% direct availability, 56/120 at or above 70%, 44 near-face rows at or above 40%, and 43
two-hand-evidence rows at or above 30%.

## P2-P2 Final Result - 2026-08-12

Both reviews and the registered evaluator completed. The result is **NO-GO for creating the
40-sign RGB training dataset with any current route**. R1 pose recovery was strongest:

- strict one-to-one known-visible hand coverage `0.8263` versus the `0.90` gate;
- strict one-to-one complete two-hand coverage `0.6892` versus `0.80`;
- provisional reviewed usability `0.7672` versus `0.85`;
- wrong/stale/side-swap `0.0086`, which passes `<=0.02`;
- synchronization `1.0000`, which passes `>=0.98`;
- triplet availability consistency `0.6917` versus `0.90`.

R0, R2, and R3 were weaker as usable hand-crop routes. R3 proves why ROI availability alone is
misleading: its upper-body box covers nearly every hand geometrically but reviewed hand-crop
usability is only `0.0603`.

The reviewer reported uncertainty about the fine-grained route verdict criteria. Those manual
usability/failure labels are retained as provisional single-reviewer evidence. The NO-GO does not
depend on strict interpretation of them because R1 independently fails three objective gates.
Near-face subgroup claims are also unsupported because only one frame was manually flagged
near-face despite metadata-based enrichment; do not quote that subgroup as representative.

Recovery audit found all 190 original gold boxes had anatomical side `unknown`. The original
unknown-side scorer could reuse one ROI for two hands, so its result is preserved but superseded.
Version `p2p2.strict_one_to_one.v2` corrects matching and explicitly reports side evidence as
unmeasured. The 40-frame, 80-hand side-only adjudication under `side_review/` is now complete,
prioritizes R1/R2 complementary cases, and spans 25 signers. Corrected R1 side accuracy is `0.7750`;
R2 side accuracy is `0.6125`. A strict whole-route gold oracle, which can unrealistically choose R1
or R2 using gold geometry but cannot combine boxes, reaches coverage `0.8632`, complete two-hand
coverage `0.7432`, and side accuracy `0.8000`. It therefore fails before any deployable selector is
considered. Selector implementation is cancelled; RGB training and dataset creation remain blocked.

A global left/right swap counterfactual was also run because source mirror metadata was unknown.
It makes all routes worse; for R1, coverage falls `0.8158 -> 0.5316`, two-hand completeness falls
`0.6757 -> 0.3514`, and side accuracy falls `0.7750 -> 0.1000`. A single reversed mirror convention
is not the root cause. The remaining blocker is ROI localization/continuity itself.

## P2-P2F Optical-Flow Continuation - 2026-08-12

One final bounded ROI method is authorized before retiring the current hand-crop path. P2-P2F is
materially different from prior static hold, pose extrapolation, MediaPipe VIDEO, HaGRID, I320, and
upper-body routes: it causally tracks visible image texture from the last direct or pose-initialized
hand ROI using pyramidal Lucas-Kanade optical flow with forward/backward consistency filtering.

The package is `pipeline/rgb/phase2_p2f_optical_flow.py`. It reuses the same frozen 120 P2-P2
frames, gold boxes, side adjudication, signer/split lineage, and objective gates. It does not tune a
model, create training crops, or touch Android. The three-clip real-data smoke passed decoding,
Stage-E alignment, flow execution, output writing, and structural checking under
`scratchpad/p2_p2f_flow_smoke_01`.

P2-P2F advances to blinded crop review only if it passes all objective gates and improves on frozen
R1. Otherwise the decision is `NO_GO_RETIRE_CURRENT_ROI_STACK`; do not tune flow age, create the
40-sign RGB dataset, or train P2-P3 from the failed route.

Full developer-run command:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.phase2_p2f_optical_flow run `
  --source-run artifacts\recognition_upgrade\phase2_roi_audit\p2_p2_roi_audit_02 `
  --output artifacts\recognition_upgrade\phase2_roi_audit\p2_p2f_flow_01

.\.venv\Scripts\python.exe -m pipeline.rgb.phase2_p2f_optical_flow check `
  --output artifacts\recognition_upgrade\phase2_roi_audit\p2_p2f_flow_01 `
  --require-full
```

Source result:
`artifacts/recognition_upgrade/phase2_roi_audit/p2_p2_roi_audit_02/p2_p2_final_result.json`.

## P2-P2F Final Result - 2026-08-12

The full 120-frame run completed structurally and produced
`artifacts/recognition_upgrade/phase2_roi_audit/p2_p2f_flow_01/result.json`. The registered decision
is **`NO_GO_RETIRE_CURRENT_ROI_STACK`**:

- known-visible coverage `0.8053` versus R1 `0.8158` and gate `0.90`;
- complete two-hand coverage `0.6486` versus R1 `0.6757` and gate `0.80`;
- anatomical-side accuracy `0.7375` versus R1 `0.7750` and gate `0.98`;
- triplet consistency `0.8917` versus R1 `0.6917` and gate `0.90`;
- synchronization `1.0000`, passing its `0.98` gate;
- no-visible-hand false ROI `0.7500` (`3/4` frames), failing its `0.02` gate.

Optical flow was used for 91 center-frame hand slots. It improved objective center-frame coverage on
8 frames, regressed 9, and left 103 unchanged. It therefore improves persistence but not correct
localization. The stale no-hand boxes show why availability cannot substitute for hand evidence.

Per the preregistered stop rule, do not sweep flow age or thresholds, perform another manual crop
review, create the 40-sign RGB dataset, or train P2-P3 from this route. Static hold, pose recovery,
MediaPipe VIDEO, HaGRID, I320, R1/R2 selection, global side swapping, upper-body crops, and optical
flow are now exhausted as the immediate ROI stack. Reopening hand-crop Phase 2 requires materially
new localization training data/methodology and a new independent gate; it cannot be a renamed
variant of these experiments.
