# C0-B0 Stage 1 Readiness Result

**Purpose:** Record the implemented C0-B0 inventory and annotation/toolchain smoke package without
overstating it as detector training or recognition progress.

**Scope:** Metadata inventory, protected-source exclusion, a 24-frame hand-box review smoke, and
an isolated one-epoch train/export/reload wiring smoke. No accuracy-bearing detector was trained,
no RGB recognition features were extracted, and no Android or production asset was changed.

**Current status:** INVENTORY PASSED / 24-FRAME REVIEW PASSED / ISOLATED TOOLCHAIN SMOKE PASSED /
300-FRAME ANNOTATION PILOT PREPARED AND REVIEW PENDING / DETECTOR PILOT NOT AUTHORIZED.

**Last updated:** 2026-08-09.

## Verified Project Results

### Training-Only Source Inventory

Run directory: `artifacts/recognition_upgrade/e2e_c0/c0b_inventory_01`.

- inventory rows: `44,189`;
- independent candidate rows: `42,251`;
- excluded rows: `1,938`;
- ASL Citizen candidates: `39,772` across `33` train signers;
- local supplementary candidates: `2,479` across `3` signers;
- protected source paths: `2,218`;
- protected hashes: `2,074`;
- held-out/protected signer IDs are recorded in `inventory_summary.json`;
- `training_authorized=false`.

The inventory uses ASL Citizen `train.csv` only. Local sidecars require an existing paired video,
signer ID, and accepted status. Frozen P0/N0/P1 paths and hashes are excluded. E6 validation/test
signers are excluded from local detector-training candidates.

### Annotation Smoke

Authoritative run: `artifacts/recognition_upgrade/e2e_c0/c0b_annotation_smoke_03`.

- rows: `24`;
- ASL Citizen/local balance: `12/12`;
- represented signers: `15` (`12` ASL Citizen and all `3` eligible local signers);
- source hashes recorded: yes;
- protected overlaps: `0`;
- existing `e2e_gold_review` GUI compatibility: passed with zero structural errors;
- local visual inspection: ASL motion and local phone framing both render correctly;
- human review: complete, `24/24` accepted, zero quarantined, zero validator errors;
- visible-hand distribution: `5` no-hand, `10` one-hand, `9` two-hand frames;
- accepted hand boxes: `28`;
- condition coverage: `4` motion-blur frames and zero occlusion, near-face, edge-clipped, or
  partial-visibility frames;
- `training_authorized=false`.

`c0b_annotation_smoke_01` is diagnostic only because its signer-first sampler produced an
unbalanced `23/1` ASL/local source mix. Run 02 corrected source balance but exposed reverse-queue
bias toward one large local signer. The selector now balances source first and rotates signers in
forward order. Tests cover both properties, and Run 03 supersedes Runs 01 and 02.

### Toolchain Preflight

Run directory: `artifacts/recognition_upgrade/e2e_c0/c0b_toolchain_preflight_01`.

- main environment Python: `3.11.5`;
- TensorFlow: `2.21.0`;
- MediaPipe: `0.10.35`;
- `mediapipe_model_maker`: absent;
- published Model Maker Python support: `3.8-3.10`;
- preflight: failed as expected;
- consequence: never install this deprecated toolchain into the main `.venv`.

The native Python 3.9 installation attempt failed exactly at the registered toolchain gate:
`tensorflow-text` has no matching native Windows distribution for the Model Maker / TF Models
Official dependency chain. Loosening TensorFlow pins cannot create a missing platform wheel.

WSL2 Ubuntu is installed and can read the project, but its system Python is `3.12.3`, outside the
published Model Maker range. Docker Desktop is installed but was not running during validation.
The corrected reproducible path is therefore a Python 3.10 Linux Docker image using the pinned
requirements and runner below.

### Isolated Train/Export/Reload Smoke

Authoritative run: `artifacts/recognition_upgrade/e2e_c0/c0b_toolchain_smoke_03`.

- Python `3.10.20`, TensorFlow `2.15.1`, MediaPipe `0.10.14`, and Model Maker import: passed;
- one-epoch MobileNetV2 wiring run: completed;
- exported TFLite size: `10,902,225` bytes;
- exported SHA-256: `079BCA51A3008AF60F1A35E0073D499614AA87E53EC3EA5A00D38713C2DAF06E`;
- TFLite reload through MediaPipe Object Detector: passed using CPU/XNNPACK;
- summary gate: `passed=true`, `training_authorized=false`.

Runs 01 and 02 are preserved diagnostics. Run 01 exposed removal of `pkg_resources` in new
`setuptools`; the isolated requirements now pin `setuptools==80.9.0` and
`tensorflow-metadata==1.17.3`. Run 02 exposed Windows absolute paths and a COCO `data/` versus
Model Maker `images/` contract mismatch. The exporter now resolves annotation assets portably and
writes the tested `images/` contract.

The reported `1,551` raw detections are not an accuracy metric. They come from an intentionally
one-epoch, smoke-sized model with no fitted operating threshold and prove only that exported-model
inference returned data. GPU/EGL warnings are expected in the headless CPU container; XNNPACK was
created successfully.

## Implemented Files

- `pipeline/tracking/e2e_c0b.py`
- `tests/test_tracking_e2e_c0b.py`
- `model/config/recognition_upgrade/c0b_model_maker_requirements.txt`
- `model/config/recognition_upgrade/c0b_model_maker.Dockerfile`
- `model/config/recognition_upgrade/run_c0b_toolchain_smoke.ps1`

## Validation

- focused pytest: `6 passed`;
- Ruff: passed;
- mypy: passed;
- PowerShell Docker runner syntax: passed;
- real metadata inventory: passed;
- Run 03 structural check: passed;
- existing review GUI validation: zero errors.

## Review Interpretation

The smoke passes annotation mechanics and supplies enough positive frames for a one-epoch
train/export/reload wiring check. It does not pass detector-training data readiness. Five no-hand
frames are useful smoke hard negatives, but the absence of occlusion, near-face, edge, and partial
cases means a later training annotation package must nominate those conditions deliberately rather
than rely on random frame sampling.

The reviewed boxes have plausible normalized geometry: minimum/median/maximum box area is
approximately `0.0349/0.0895/0.2176` of the image. This is a sanity check, not annotation-accuracy
measurement.

## Architecture Decisions

- Keep source inventory and frame annotation separate.
- Hash every nominated training video before review.
- Balance the smoke by source before signer.
- Reuse the proven all-visible-hand box GUI; do not build another reviewer.
- Treat P0/N0/P1 and E6 held-out signers as protected.
- Keep Model Maker in an isolated Python 3.9/3.10 environment.
- Do not authorize detector training from inventory volume alone.

## Assumptions

- Folder and sidecar signer identities are accurate.
- A 24-frame smoke is sufficient to validate annotation mechanics, not dataset sufficiency.
- Model Maker dependency installation may require Linux/WSL/Colab if the Windows dependency set
  cannot resolve.

## Risks

- Three local training-eligible signers are not enough to prove AppHear-domain detector diversity.
- Most source videos remain unreviewed; candidate count is not accepted-box count.
- Local Stage-E clips can be very short, limiting temporal context even though center frames are
  usable for object detection.
- Model Maker is deprecated and depends on compatibility pins; the Docker lock must remain frozen.

## Open Questions

- Resolved: `19/24` frames contain one or two reviewable hands, with `28` boxes total.
- Resolved: source/signer/box mechanics are valid, but hard-condition coverage is incomplete.
- Resolved: the pinned Python 3.10 Linux image trains one epoch, exports TFLite, reloads it, and
  executes CPU inference.
- How many independent training/development annotations are needed before the preregistered
  learning curve stabilizes across the required hard conditions?

## Next Required Action

Prepare the Stage 1 condition-balanced training/development annotation package from independent
inventory candidates. Explicitly cover two-hand, blur, edge, occlusion, near-face, small-hand,
partial-visibility, and true no-hand/hard-negative cases. Keep P0/N0/P1 frozen. Do not begin the
Stage 2 detector pilot until lineage, overlap, review, condition coverage, and license gates pass.

The next prepared action is `c0b_training_annotation_pilot_01`: select `300` unique rows with seed
`90827` and `--preannotate-mediapipe`. MediaPipe boxes are editable suggestions only and selection
does not depend on proposal success. Validate source/signer/proposal coverage before opening the
GUI, then use the completed human review to define only the missing condition-specific top-up.

### 300-Frame Annotation Pilot Preparation

Run directory: `artifacts/recognition_upgrade/e2e_c0/c0b_training_annotation_pilot_01`.

- `300` rows, candidate IDs, raw-video paths, and SHA-256 hashes are all unique;
- source balance: `150` ASL Citizen / `150` local supplementary;
- signer coverage: `33` ASL Citizen / `3` local supplementary;
- temporal fractions: `108` at 0.25, `98` at 0.50, `94` at 0.75;
- represented glosses: `198`;
- missing raw videos/images/context panels: `0/0/0`;
- protected overlaps: `0`;
- MediaPipe proposal frames: `73` zero-box, `155` one-box, `72` two-box;
- proposed boxes: `299`; these remain unreviewed suggestions;
- package size: approximately `201.34 MB`;
- structural check: passed; completed reviews: `0/300`;
- `training_authorized=false`.

Representative inspection confirmed that at least one zero-proposal frame contains a real,
motion-blurred hand. Zero proposals must therefore be reviewed as possible misses, not accepted as
no-hand automatically. Condition counts remain unknown until human review is complete.

### 300-Frame Human Review And Proposal Audit

Human review completed `300/300`; all rows were accepted with `351` gold hand boxes and zero
validator errors. Gold frame distribution is `55` no-hand, `139` one-hand, and `106` two-hand.
Reviewed conditions: blur `37`, occlusion `9`, near-face `1`, edge-clipped `10`, and partial
visibility `2`.

Saved MediaPipe proposals were evaluated against this gold in `audit_summary.json`:

- visible-hand instance recall: `0.8490` (`298/351`);
- any-visible-hand frame recall: `0.9224`;
- complete two-hand-frame recall: `0.6792`;
- no-hand frame false-positive rate: `0.0000` on `55` sampled no-hand frames;
- ordinary non-blurred instance recall: `0.9483`;
- blur instance recall: `0.3770`;
- edge-clipped instance recall: `0.2222`;
- occlusion instance recall: `0.5000`;
- ASL Citizen/local instance recall: `0.7468/0.9326`.

These are MediaPipe proposal diagnostics, not a trained C0-B0 detector result. The review proves
why detector-derived ROIs remain relevant, especially for blurred ASL Citizen and complete
two-hand frames. Stage 1 data readiness remains incomplete because near-face and partial cases are
too sparse for a meaningful development subgroup, local hard-condition coverage is weak, and the
55 incidental no-hand frames are not a dedicated hand-like hard-negative set.

Next action: mine and review one bounded targeted top-up, reusing the 300 accepted rows. Do not run
another random 300-frame package. The top-up must prioritize independent near-face, partial/edge,
occluded/two-hand, small-hand, and dedicated no-hand/hard-negative candidates. Counts are to be
preregistered as engineering coverage quotas, not presented as universal research minima.

### Bounded Hard-Condition Top-Up Preparation - 2026-08-10

Implemented `pipeline/tracking/e2e_c0b_topup.py` as a separate, resumable Stage 1 data-mining
component. It does not alter `e2e_c0b.py`, the v3.0 feature schema, model assets, or Android.

The miner:

- excludes the frozen P0/N0/P1 registry by path/hash;
- excludes all `300` videos and hashes already reviewed in
  `c0b_training_annotation_pilot_01`;
- alternates ASL Citizen and local supplementary sources, then rotates signers;
- scans one deterministic frame from each of `900` independent videos;
- ranks scan-relative blur and small-hand candidates rather than claiming universal thresholds;
- mines likely missed-second-hand, edge/partial, near-face, and zero-proposal cases;
- materializes only the selected `100` frames and five-frame context panels;
- stores mining proxies separately in `mining_selection.csv`; human review remains ground truth;
- supports interrupted scan continuation with `--resume`;
- leaves `training_authorized=false`.

The default `100`-frame engineering quotas are `25` blur/zero-proposal, `25` likely missed second
hand, `20` edge/partial proxy, `20` near-face proxy, and `10` small-hand proxy. Categories may
overlap; selection keeps rows unique and fills unavailable quota slots with the remaining hardest
independent candidates. These quotas are bounded coverage targets, not experimentally verified
sample minima.

An overlap audit rejected all `547` E6 development-negative windows: `150 N0_NO_HAND`, `200
OOV_SIGN`, `54 P1_FACE_ADJACENT`, and `143 P1_IDLE_HANDS` rows reuse frozen evaluation source
paths and hashes. They must not train or tune C0-B0. Consequently, the top-up can improve difficult
visible-hand coverage but cannot close the independent dedicated hard-negative gap. That gap must
be resolved before Stage 2 authorization.

Validation:

- focused tests: `11 passed` across the original C0-B0 and top-up suites;
- Ruff: passed;
- mypy: passed;
- real scan smoke: `10/10`, zero failures, `5` ASL Citizen / `5` local;
- real package smoke: `5` rows, four signers, structural check passed;
- completed-resume path: passed;
- observed 10-frame scan wall time: approximately `25` seconds after framework startup; the full
  scan is expected to take roughly `35-45` minutes on the current CPU and can be resumed.

Approved commands:

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.e2e_c0b_topup mine `
  --output artifacts\recognition_upgrade\e2e_c0\c0b_condition_topup_scan_01 `
  --scan-count 900

.\.venv\Scripts\python.exe -m pipeline.tracking.e2e_c0b_topup prepare-topup `
  --scan-run artifacts\recognition_upgrade\e2e_c0\c0b_condition_topup_scan_01 `
  --output artifacts\recognition_upgrade\e2e_c0\c0b_condition_topup_01 `
  --count 100
```

If the scan is interrupted, rerun the first command with `--resume`. Do not run `prepare-topup`
until `scan_summary.json` reports `passed=true`.

### Full Hard-Condition Scan And Package - 2026-08-10

The approved full scan completed `900/900` with zero failures: `450` ASL Citizen and `450` local
supplementary videos. Candidate IDs, raw paths, and SHA-256 hashes are each unique (`900`), with
zero path/hash overlap against the protected registry or reviewed 300-frame base package.

Scan diagnostics before human review:

- proposal counts: `199` zero, `321` one, `380` two;
- near-face proxy: `75`;
- possible missed-second-hand proxy: `254`;
- edge proxy: `90`;
- signer coverage: eight ASL Citizen signers and one local training-eligible signer.

The source-balanced scan does not solve local signer diversity. Local conditions can be added to
training, but performance claims must remain signer-independent and rely on held-out signers.

The final top-up package is
`artifacts/recognition_upgrade/e2e_c0/c0b_condition_topup_01`:

- `100` unique candidates, paths, hashes, center images, and context panels;
- source balance: `48` ASL Citizen / `52` local supplementary;
- selected signer count: `7` total;
- exact selected quotas: blur/zero-proposal `25`, likely missed second hand `25`, edge/partial
  proxy `20`, near-face proxy `20`, small-hand proxy `10`;
- protected overlap: `0`;
- structural check: passed;
- human reviews completed: `0/100`;
- `training_authorized=false`.

The next gate is human correction of all 100 rows. Mining strata remain hypotheses until the
reviewed boxes and condition flags are audited. Stage 2 remains blocked after review until the
independent hard-negative gap and dataset/license split gates are resolved.

### Top-Up Review And Corrected Proposal Audit - 2026-08-10

Human review completed `100/100`; all rows were accepted with `132` gold hand boxes and no
validator errors. Gold distribution is `12` no-hand, `44` one-hand, and `44` two-hand frames.
Reviewed conditions are blur `10`, occlusion `6`, near-face `7`, edge-clipped `1`, and partial
visibility `0`.

The first proposal audit incorrectly reported zero predictions because the package builder copied
editable proposal boxes but omitted landmark-level `detected_hands_json` from `internal_index.csv`.
This was a diagnostic packaging defect, not a human-review or detector result. The repair command
`backfill-audit-proposals` reran the same MediaPipe configuration on the 100 saved center images,
wrote `114` proposal instances, and did not modify any reviewed gold box. The builder now preserves
landmark-level proposals for future packages. Focused pytest remains `11 passed`; Ruff and mypy
pass.

Corrected top-up MediaPipe diagnostics:

- visible-hand instance recall: `0.8258` (`109/132`);
- any-visible-hand frame recall: `0.9205`;
- complete two-hand-frame recall: `0.6364` (`28/44`);
- unmatched proposal rate: `0.0439`;
- no-hand frame false-positive rate: `0.0000` on `12` frames;
- non-blurred instance recall: `0.8947`;
- blurred instance recall: `0.3889`;
- ASL Citizen/local instance recall: `0.8657/0.7846`;
- ASL Citizen/local complete two-hand recall: `0.6667/0.6000`.

Across the accepted 300-frame base and 100-frame top-up, Stage 1 now has `400` reviewed frames,
`483` gold hand boxes, `67` no-hand frames, `183` one-hand frames, and `150` two-hand frames.
Combined condition counts are blur `47`, occlusion `15`, near-face `8`, edge-clipped `11`, and
partial visibility `2`. Combined MediaPipe proposal recall is `407/483 = 0.8427`; combined complete
two-hand recall is `100/150 = 0.6667`. The top-up confirms the original failure pattern instead of
contradicting it: ordinary hands are usually detected, while blur and complete two-hand recovery
remain poor.

Mining-proxy yield was mixed:

- blur/zero-proposal: `12` true no-hand, `3` one-hand, `10` two-hand; only `4` marked blur;
- likely missed-second-hand: `20` one-hand and `5` two-hand;
- edge/partial proxy: `16` two-hand but no reviewed edge/partial case;
- near-face proxy: `7/20` verified near-face;
- small-hand proxy: ten reviewed hand frames, but no separate human small-hand flag exists.

Do not repeat this miner with the same rules to chase partial/edge cases. The proxy has already
shown that it does not isolate those conditions reliably.

### License And Stage 1 Decision

The installed ASL Citizen `use.txt` is a Microsoft Research License limited to non-commercial,
non-revenue-generating research. It prohibits distributing the data or modifications. Therefore:

- ASL Citizen frames may support an internal research pilot under those terms;
- no ASL-Citizen-derived detector may be called a production AppHear asset or distributed without
  separate rights review/permission;
- no local supplementary consent/release/license record was found under `E:/local`; local
  production rights remain unverified.

Technical data/toolchain readiness is sufficient for a separately approved **research-only Stage
2 learning-curve pilot** using a signer/source-disjoint manifest. Production readiness is not
approved. The pilot must retain the documented 25/50/100-percent learning curve and may perform one
locked P0/N0/P1 evaluation only after development selection. Its purpose is to decide whether
AppHear-domain detector training is technically worth continuing, not to produce a shippable
model.

Remaining production blockers are independent hand-like hard-negative diversity, sparse
partial/edge cases, only three local source signers overall, undocumented local consent, and ASL
Citizen's non-commercial license. Do not start Stage 2 training until the user separately approves
the research-only scope and the consolidated split manifest passes leakage checks.

### Research-Only Stage 2 Authorization And Package - 2026-08-10

The user explicitly limited this work to internal research/development and approved the bounded
Stage 2 pilot. This authorization does not permit commercial use, restricted-data redistribution,
production claims, Android integration, or replacement of the current recognizer.

The consolidated manifest at
`artifacts/recognition_upgrade/e2e_c0/c0b_stage2_research_manifest_01` passes its independent check:

- `400` reviewed rows: `198` ASL Citizen and `202` local supplementary;
- signer-disjoint train/development split: `312/88` rows;
- development signers: ASL `P10/P14/P2/P3/P45/P50/P52`, local `6F7328-S001`;
- zero signer, protected-path, or protected-hash overlap;
- train: `370` boxes, `53` no-hand, `111` two-hand, `37` blur;
- development: `113` boxes, `14` no-hand, `39` two-hand, `10` blur.

The locked manifest SHA-256 is
`42A4202524508E6A45760AB7E536BE7EB5230BCCCCF7A08AD4C43B66FA29FB03`.

The research package at
`artifacts/recognition_upgrade/e2e_c0/c0b_stage2_detector_01` contains deterministic nested
MobileNetV2-256 train subsets of `78/156/312` rows plus the same `88`-row development split. All
image references were staged as hard links, avoiding duplicate image payload. The 25-percent
subset has no partial-visibility frame because only one exists in the full train split; sparse
partial/edge/near-face metrics remain diagnostic and cannot establish subgroup readiness.

Next action: run only the MobileNetV2-256 `25/50/100%` float learning curve using
`model/config/recognition_upgrade/run_c0b_stage2_256_learning_curve.ps1`. Review the curve before
authorizing I320, QAT/INT8, locked P0/N0/P1 evaluation, or any Android work.

### MobileNetV2-256 Learning Curve Result - 2026-08-11

All three research-only branches completed and exported valid `10,902,225`-byte float TFLite
models. Structural check with `--require-models` passed. Development metrics improved monotonically:

| Train fraction | Rows | AP | AP50 | AP75 | ARmax100 | Time |
|---:|---:|---:|---:|---:|---:|---:|
| 25% | 78 | 0.2012 | 0.5283 | 0.0833 | 0.4027 | 300 s |
| 50% | 156 | 0.2911 | 0.7211 | 0.2057 | 0.4398 | 464 s |
| 100% | 312 | 0.3447 | 0.7747 | 0.2859 | 0.5044 | 946 s |

Verified interpretation: the 256 detector is data-responsive and has not plateaued, but precise
localization remains weak. COCO AP/AP50/AP75 are not the registered AppHear availability,
two-hand, blur, IoU50-recall, or no-hand false-ROI gates. `passed=true` proves execution/export,
not detector acceptance. `APs=-1` means the development set does not support a small-object AP
claim.

Decision: proceed with the preregistered MobileNetV2-I320 `25/50/100%` comparison on exactly the
same locked subsets and development set. Runner:
`model/config/recognition_upgrade/run_c0b_stage2_i320_learning_curve.ps1`. Do not fit thresholds,
quantize, access frozen P0/N0/P1, or modify Android until both float branches are compared.

### MobileNetV2-I320 Result And Development Evaluation Handoff - 2026-08-11

The I320 curve completed and passed the six-model structural check. At the full 312-row subset,
I320 improved over 256: AP `0.4010` vs `0.3447`, AP50 `0.8548` vs `0.7747`, AP75 `0.3723` vs
`0.2859`, and ARmax100 `0.5142` vs `0.5044`. The float I320 artifact is `10,452,897` bytes. I320
is the accuracy candidate; 256 remains the latency control. COCO metrics still do not establish
the registered AppHear gate.

Added `pipeline/tracking/e2e_c0b_stage2_eval.py` and
`model/config/recognition_upgrade/run_c0b_stage2_development_eval.ps1`. The evaluator:

- accesses only the locked 88-frame signer-disjoint development split;
- emits at most four raw detections per frame down to confidence `0.01`;
- applies exact maximum-cardinality one-to-one matching;
- sweeps all observed thresholds and requires development no-hand FPR `<=2%`;
- reports availability, complete two-hand, IoU50/75, condition/source subgroups, diagnostic
  1.75-expanded containment, and preprocessing/inference p50/p95 latency;
- preserves completed candidates and timestamp-renames interrupted candidates before retry;
- records that frozen P0/N0/P1 were not accessed.

The 14-frame development no-hand denominator means the threshold gate requires zero false-positive
frames and remains statistically weak. The next action is the development comparison command, not
QAT/INT8 or frozen evaluation. Ruff, mypy, actual I320 single-image reload/inference, PowerShell
parsing, and focused tests pass.
