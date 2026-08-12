# E2 RGB Hand-Crop Quality Runbook

**Purpose:** Operate the bounded crop-quality experiment that must pass before RGB modeling.
**Scope:** ASL Citizen train/validation videos and existing Stage-E landmarks only.
**Status:** ENGINEERING NO-GO; E2b ROI-recovery redesign required.
**Last updated:** 2026-07-26.

## Contract

- E2 does not train a model and does not change production schema `3.0`.
- Test-split clips remain untouched. Sampling is 80% train and 20% validation.
- A sign span means the existing D2 inclusive `onset..release`.
- A usable crop contains the visible hand and sign-relevant fingers, is synchronized to the
  displayed source frame, and is not severely clipped or blurred.
- Missing ROIs remain missing. A direct box may be held causally for at most 100 ms and is marked
  `held`; no future-frame interpolation or pose-wrist fallback is hidden in the data.
- E2 passes only at `>=0.98` usable crops among human-reviewed frames where that hand is visible.

## Inputs And Outputs

Configuration: `pipeline/config/crops_e2.yaml`.

Inputs:

- raw videos under `F:/ASL DATASET/ASL CITIZEN/ASL_Citizen/videos`;
- official train/validation CSVs;
- Stage-E NPZ landmarks and real timestamps;
- D2 span sidecars.

Outputs stay under:

`F:/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/e2_crop_quality_v0/<run-id>/`

Every run contains the frozen config/hash, sampled clips, private metadata index, blinded review
panels, audit template, crops, and generation summary. Do not distribute these derived images:
the ASL Citizen research license prohibits redistribution of dataset material and derivatives.

Engineering and audit runs persist at most 600 deterministically balanced review crops/panels.
Their internal index still records every evaluated candidate. The smoke path selects one
high-coverage clip from a deterministic 12-clip candidate pool and checks only the provisional
96-pixel, 1.75x path at native/k4/k8 cadence; it does not select the winning E2 configuration.

## Commands

Run the lightweight smoke test first:

```powershell
python -m pipeline.crops.run --phase smoke
```

Then run the 60-clip engineering matrix yourself:

```powershell
python -m pipeline.crops.run --phase engineering
```

Review `audit_template.csv` using the image in `panel_path`. Fill `visible_hand` and `usable` with
`yes` or `no`; add a concise `failure_reason` when unusable. The sheet is blinded to gloss,
signer, crop size, expansion, cadence, and ROI source.

Summarize a completed review:

```powershell
python -m pipeline.crops.audit `
  --audit-csv "<run>\audit_template.csv" `
  --index-csv "<run>\internal_index.csv" `
  --output "<run>\audit_summary.json"
```

Select crop size and expansion from the engineering summary. Only then generate the 200-clip
confirmation audit, explicitly naming the selected values:

```powershell
python -m pipeline.crops.run --phase audit --crop-size 96 --expansion 1.75
```

The `96` and `1.75` values above are examples, not an approved result.

## Interpretation And Stop Rules

- If direct/held ROI availability is low when a hand is visibly present, stop and test a
  timestamp-bounded tracker or pose/wrist-guided fallback. A larger crop cannot repair a missing ROI.
- If containment fails, compare expansion factors before changing resolution.
- If hand detail fails after containment passes, compare 80/96/112 resolution and sharpness.
- If native passes but k4/k8 fails, the crop tracker needs a low-cadence treatment before E3.
- Do not begin E3 unless the selected configuration passes the 200-clip blinded audit and crop
  geometry/checksum fixtures remain green.

## Sources, Risks, Open Questions, Next Action

- **Verified project references:** `pipeline/extract/schema.py`, `pipeline/detect/schema.py`,
  `pipeline/config/extract.yaml`, `pipeline/config/detect.yaml`, and existing ASL Citizen derived
  landmarks/spans.
- **Related context:** `EXPERIMENT_MATRIX.md`, `FEATURE_SCHEMA_PLAN.md`,
  `HYBRID_FUSION_DESIGN.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `RISK_REGISTER.md`.
- **Architecture decisions:** experiment-only `apphear.hybrid.v0`; causal short hold; explicit
  missingness; no test-set inspection.
- **Assumptions:** OpenCV frame order matches the Stage-E extraction order. The smoke run checks
  this mechanically but a human must still inspect synchronization.
- **Risks:** hand detector dropout, stale held boxes, wrong handedness slot, border padding,
  low-resolution finger detail, and license-restricted output handling.
- **Open questions:** winning crop size/expansion, whether a stronger tracker is required, and
  whether hand-slot labels remain correct under all camera conventions.
- **Next required action:** developer runs and reviews the 60-clip engineering matrix.

## Verified Smoke Result - 2026-07-26

- Run: `smoke_validation_v2_20260726`.
- Sample: ASL Citizen train signer `P16`, `CHEAT1`, D2 frames 25-49, in-span hand coverage 1.0.
- Output: 6 review records from three synchronized frames and two canonical hand slots.
- ROI result: 5 direct, 0 held, 1 missing.
- Visual check: direct crop contained the complete hand at useful detail; the missing panel exposed
  a visible-hand detector miss instead of silently fabricating or reusing a stale crop.
- Validation: focused tests 5/5, full suite 133/133, Ruff clean, mypy clean, CLI help passed.
- Next required action: developer runs the 60-clip engineering matrix. Do not run the 200-clip
  confirmation audit until the engineering review selects crop size and expansion.
## Engineering Run 01 Review And Cadence Correction - 2026-07-26

- `engineering_run_01` completed structurally: 60 clips, 34 signers, 26,190 unique matrix
  records, and 600 balanced blinded panels.
- Automatic records were 34.3% direct, 10.0% held, and 55.7% missing. This is not a crop-quality
  score because many requested hand slots are not visibly present; human visibility labels are the
  denominator.
- Review found a protocol defect before human scoring: k4/k8 selected lower-cadence frames, but ROI
  state was refreshed by intervening native-frame landmarks. Therefore Run 01 is invalid for
  low-FPS comparison and its `audit_template.csv` must not be scored.
- Corrected behavior aligns sampled indices to video cadence and lets only sampled observations
  update direct/held ROI state. Added regressions for unsampled detection leakage and mask shape.
- Corrected smoke `smoke_cadence_fix_20260726` passed across native/k4/k8: 18 records, 14 direct,
  0 held, 4 missing; cadence frame sets differ as expected.
- Validation after correction: full suite 135 passed, focused Ruff and mypy clean.
- Next required action: developer reruns the matrix with run ID `engineering_run_02`, then scores
  only Run 02's blinded audit template.
## Authoritative Engineering Run 02 - 2026-07-26

- Run 02 completed: 60 clips, 34 signers, 25,380 matrix records, and 600 blinded panels.
- Cadence results confirm corrected behavior: native direct/held/missing 33.7/9.9/56.4%; k4
  35.4/0.0/64.6%; k8 35.7/0.0/64.3%. The 100 ms hold expires before the next k4/k8 observation.
- These are ROI-source rates, not failure rates: the matrix requests both hand slots, including
  frames where one target hand is genuinely not visible. Human visibility labels remain required.
- The audit sample is balanced at 22-23 rows for every cadence/size/expansion cell. It contains
  200 direct, 25 held, and 375 missing records.
- Representative inspection found usable direct crops, motion-blurred/tight crops, correctly absent
  hand slots, and at least one visible-hand detector miss. No crop setting is selected yet.
- `audit_template.csv` was deterministically shuffled before labels; the original is preserved as
  `audit_template_unshuffled.csv`. `provenance_addendum.json` records execution-source and artifact
  SHA-256 digests. Future runs use experiment version `e2.crop.v0.1` and embed a source-code hash.
- Validation: full suite 135 passed; focused Ruff and mypy clean.
- Next required action: human scores the shuffled Run 02 `audit_template.csv`, then runs the audit
  summarizer. Do not select settings or start the 200-clip audit from automatic ROI rates alone.
## Resumable Review Window

Close Excel before launching because Excel locks `audit_template.csv`. Run:

```powershell
.\.venv\Scripts\python.exe -m pipeline.crops.review `
  --run-dir "F:\ASL DATASET\ASL CITIZEN\derived\apphear3\recognition_upgrade\e2_crop_quality_v0\engineering_run_02"
```

The reviewer displays one blinded panel at a time and saves atomically after every decision:

- `0`: requested hand is not visible in the full frame;
- `1`: requested hand is visible and the crop is usable;
- `2`: visible hand, but crop is missing/black;
- `3`: clipped;
- `4`: motion blur;
- `5`: stale crop/wrong location;
- `6`: wrong hand;
- `7`: insufficient detail;
- `8`: other failure;
- `P`: previous panel; `Esc`: save and exit.

It resumes at the first unfinished row. On first launch it preserves
`audit_template.pre_review_backup.csv`. Headless preflight:

```powershell
.\.venv\Scripts\python.exe -m pipeline.crops.review `
  --run-dir "<run-dir>" --check
```
## Run 02 Human Audit Decision - 2026-07-26

- Human audit completed cleanly: 600/600 rows, 358 visible target hands.
- Preserved original labels. A separate consistency derivative corrected 27 logically impossible
  cases where a missing ROI was marked usable or assigned a non-missing reason; correction log kept.
- Corrected result: 167/358 usable = 46.65%; ROI available on 224/358 visible hands = 62.57%.
- Registered 98% gate: **FAIL**. Do not run the 200-clip confirmation audit or E3.
- Failures: missing ROI 135, motion blur 38, clipped 7, low detail 6, wrong hand 5.
- Direct crops were 162/199 usable (81.4%); static held crops only 5/25 (20.0%).
- No crop size/expansion winner is valid: the audit was mostly unpaired (466/528 base items had one
  candidate; zero had all nine), with only 9-18 visible examples per cell. Apparent rankings are
  sample-composition noise; do not select 80 px from this run.
- Next: architect E2b paired ROI recovery using pose-wrist propagation/fallback, timestamp-bounded
  freshness candidates, separate source-blur/ROI/containment/detail labels, and left/right audit.
- Gate refinement requires an explicit decision; do not silently lower the 98% threshold.
- Authoritative report: Run 02 `audit_analysis.md`.
## E2b Phase-A Tooling Ready - 2026-07-26

- E2b is isolated under `pipeline/crops/e2b.py`, `pipeline/crops/pose_roi.py`,
  `pipeline/crops/e2b_audit.py`, and `pipeline/config/crops_e2b.yaml`.
- The paired unit is fixed across control and three pose-age strategies: source clip, frame, target
  hand, cadence, 112-pixel diagnostic output, and 1.75 diagnostic expansion.
- Pose recovery uses only sampled current/past observations. The pose hand anchor averages visible
  wrist/pinky/index/thumb points; fallback side is fit from E2 train clips only.
- Train evidence: 2,334 fallback-size observations. On 2,268 direct observations, hand-anchor
  containment was 95.55% versus 73.68% for wrist center.
- Final smoke `smoke_validation_03`: six base items covering both hands at native/k4/k8, 24 panels,
  no missing panel files; four of six missing controls gained pose fallbacks.
- Validation: 146 Python tests passed; focused Ruff and mypy passed; reviewer preflight passed.
- Next: developer generates `engineering_e2b_01`, reviews 480 blinded panels, then runs
  `pipeline.crops.e2b_audit`. E2 200-clip confirmation and E3 remain blocked.
## E2b Phase-A Result - 2026-07-26

- `engineering_e2b_01` completed structurally: 120 known-visible base items, 480/480 reviewed
  strategy panels, and no missing panel files.
- Pose availability was 95/120 (79.2%) versus control 64/120 (53.3%). Paired gain was +16.7
  points native, +25.0 k4, and +35.0 k8.
- Every pose age failed the registered every-cadence 20-point gate because native gain was 16.7.
- Recovered pose boxes were only 8-9/38 usable in the raw audit (21.1-23.7%). Do not run geometry
  Phase B or E3.
- Audit consistency check found 21 exact-image groups with conflicting labels, including 14/57
  all-direct bases. Raw usability rankings among pose ages are not decision-grade; availability is.
- Decision: E2b no-go. Next is a bounded paired IMAGE-versus-VIDEO temporal tracker experiment.
  Original E2b audit and registered summary remain unchanged.
- Authoritative context result: `E2B_PHASE_A_RESULT.md`.