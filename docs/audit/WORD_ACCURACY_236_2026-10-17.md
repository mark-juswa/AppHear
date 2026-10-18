# WORD Accuracy Across the 236-Word Vocabulary (2026-10-17)

Branch `claude/s2-r3-eval-suite`, uncommitted on top of `e2444ebb`. Research only. The production
defaults, the live-tested Experimental engine (S2-R3 Arm A e10 + confirm-boundary 0.7) and the
frozen Recognition V2 236-class WORD recognizer are unchanged. Protected TEST, E6 and Tier 3 were
not opened; ASL Citizen reference videos are taken only from TRAIN clips named in the governed
index (the split files were not read).

Labels: **MEASURED** (reproducible from the files named), **ESTIMATE**, **DEV-EXPOSED** (data that
was used for checkpoint selection or development).

---

## 0. Locked live baseline (Phase 0)

| Item | Value |
|---|---|
| Lock manifest | `docs/audit/baselines/live_experimental_2026-10-17.json` (`deploy/lock_live_experimental_baseline.py --verify` → OK) |
| Archive (git-ignored) | `artifacts/live_baselines/experimental_live_20261017/`: the installed debug APK, androidTest APK, live logcat, zip of all 53 changed source files |
| Debug APK | sha256 `8ff29546…eb23d8`, 824,578,148 B (installed 2026-10-17 22:54 with `adb install -r`, data kept) |
| STABLE | S2_R2_CANDIDATE `7d26c896…` + production lifecycle |
| EXPERIMENTAL | ARM_A_E10_CANDIDATE `e7725ef2…` + confirm-boundary 0.7 (debug only, falls back to STABLE) |
| Shared | Candidate01 (DWPose-T `37b0f265…`, hand refiner `6acda74a…`), materializer ±250 ms, WORD `ordinary_v2_tcn_fp32.tflite` `1ccf0afa…`, vocab `a7d7b08d…` |
| Device evidence | parity 4/4 incl. Arm A; both engines loaded live with `fallback=false` and committed words |

Every recognition asset inside the APK was hashed and matches the source tree. The archive copy is
the baseline even if `android/app/build` is rebuilt later. The commit of this baseline awaits
approval (file list in §9).

## 1. What evaluation data exists (Phase 1)

Tool: `eval/runtime_diagnostics/word_vocabulary_eval.py` builds every recognition window once and
stores its Recognition V2 features, so every recognizer is scored on byte-identical inputs
(`bank` / `score`); `word_vocabulary_report.py` produces the per-class report. Artifacts:
`artifacts/…/recognition_utility_236_01/word_vocabulary_eval_01/`.

| Population | Clips | Signers | Classes | Independence |
|---|---:|---:|---:|---|
| Recognizer TRAIN | 3,926 | 40 (35 ASL Citizen, 4 LOCAL, 1 APPHEAR) | 236 (8–20 clips/class; GOOD/HAVE/HELLO/KNOW/SORRY 120–190) | in-sample |
| DEV (ASL Citizen) | 816 | 5 (P5 28, P12 69, P21 242, P26 233, P39 244) | 236 (1–6 clips/class, median 3) | signer-disjoint; **DEV-EXPOSED** (every WORD run selects its checkpoint on DEV val_loss) |
| Sem-Lex, human-accepted forms | 2,252 with a valid span | 32 | 64 | never in the frozen recognizer's TRAIN or selection; split by a fixed signer hash into ENRICH (19 signers) and **EVAL (13 signers, 777 clips, 63 classes; never trained on by any model in this report)** |
| Reviewed phone signs | 29 | 1 developer, 5 sessions | **3** (HELLO, HOME, TABLE) | **DEV-EXPOSED**, partly unblinded |

Consistency checks (MEASURED): every index row's class id equals the vocabulary index of its gloss;
the Android `vocab.json` is byte-identical to the training vocabulary; no class is a duplicate
variant of another (38 glosses carry ASL Citizen variant digits, each a single class); TRAIN and
DEV signers are disjoint; Sem-Lex signers are disjoint from both.

**Reliable evaluation coverage** (only data independent of every compared model: DEV + Sem-Lex EVAL):

| Tier | Rule | Classes |
|---|---|---:|
| RELIABLE | ≥ 8 held-out clips from ≥ 5 signers | **47** |
| LIMITED | ≥ 3 clips from ≥ 3 signers | 176 |
| UNRELIABLE | fewer | 13 (BAG2, BYE, DECIDE1, FROM, GRAB, IF, ON, SELL, STRONG, TAKE, TO, VERY, WHILE) |

So per-class accuracy is measurable with useful precision for 47 classes only; for the other 189
it is a 1–6-clip, 3–5-signer estimate. Aggregate and per-signer numbers are reliable; individual
per-class numbers outside the RELIABLE tier are indicative.

**Does DEV represent the phone?** Partly, and it is the harder of the two (MEASURED):

| Window | Observations (median) | Accepted-hand fraction (median) |
|---|---:|---:|
| DEV span, dense (training view) | 30 | 0.57 |
| DEV ±250 ms runtime window, 3.75 fps | 6 | 0.57 |
| DEV ±250 ms runtime window, 200 ms | 9 | 0.57 |
| Phone human-boundary window | 12 | 0.78 |
| Phone Arm A + CB event window | 9.5 | 0.87 |

The phone signer signs more slowly, closer to the camera, with more hand evidence. DEV at 200 ms
and the DEV subset with hand fraction ≥ 0.75 (53.2% Top-1) are the closest offline proxies.

## 2. Frozen WORD recognizer across the vocabulary (MEASURED)

| Condition (DEV, 816 clips unless noted) | Top-1 | Top-5 |
|---|---:|---:|
| Span, dense (training view) | 50.3% | 76.2% |
| Span at 3.75 fps (four sampling phases) | 30.6–36.3% | 55–66% |
| ±250 ms runtime window at 3.75 fps (four phases pooled) | **41.5%** | 71.3% |
| ±250 ms runtime window at 200 ms | 42.6–46.5% | 75–77% |
| Arm A + CB event window, NATURAL (518 signs with their own event) | 45.9% | 76.3% |
| Arm A + CB event window, CONTINUOUS (398 signs with their own event) | 38.2% | 69.1% |
| Sem-Lex EVAL signers, runtime window, 3.75 fps (64 classes, among 236) | 30.2% | 57.7% |
| TRAIN (in-sample), dense / 3.75 fps | 86.9% / 60.5% | 97.9% / 83.9% |
| Phone, human-boundary windows (29 signs) | 20/29 | 25/29 |
| Phone, Arm A + CB event windows (22 credited signs) | 19/22 | 22/22 |

* Rank of the correct word under the runtime window: 41.5% first, 55.9% within two, 71.3% within
  five, 81.3% within ten.
* Per class (runtime window, DEV): median recall 0.375; 14 classes never correct; 61 below 0.25;
  40 at or above 0.75. Macro recall 41.8%. No class is absent from the Top-5 everywhere.
* Per signer (runtime window): P39 47.8%, P26 42.4%, P21 41.2%, P12 25.4%, P5 20.5%. Sem-Lex EVAL
  signers range from 4.5% to 42.9% (median 31.6%).
* Accepted-hand fraction: ≥ 0.75 → 53.2%; 0.5–0.75 → 43.1%; 0.25–0.5 → 30.1%; < 0.25 → 26.4%.
* Robustness (runtime window, 3.75 fps, Top-1 change): start one observation late −2.3, two −3.9;
  end one early −1.5, two −3.7; 25% simulated refiner rejection −7.8, 50% −16.8 (fastest-motion
  first −15.6).
* End to end on the held-out stitched streams (Arm A + CB, frozen WORD): 29.3% of NATURAL and
  18.7% of CONTINUOUS signs become the correct word. Event windows that contain part of another
  sign are correct 15.6% (natural, 32 windows) and 32.2% (continuous, 177) of the time, against
  47.9% / 43.0% for clean windows.

### Most important confusions (DEV runtime windows ×4 phases + Sem-Lex EVAL ×4)

CHAIR↔SIT 25, HOT↔PICK 16, THEN↔TIME 14, PAY↔TIME 13, HAPPY↔PLEASE 12, ALWAYS↔TELL 12,
OR↔THEN 11, FAST↔MEET 11, COOK↔GOOD 11, ASK↔WHERE 11, LOVE↔SORRY 11, NOW↔TODAY 10,
HELP↔WATCH 9, FIRST↔WHERE 9, BAD↔GOOD 8, CAR↔DRIVE 8, MUCH↔TOOMUCH 7, STAY↔STILL 7.

Several are genuine ASL minimal or near-minimal pairs that differ mainly in repetition or a small
movement (CHAIR/SIT, CAR/DRIVE, NOW/TODAY, MUCH/TOOMUCH, STAY/STILL, BAD/GOOD orientation); with
four to six observations per sign at 3.75 fps the distinguishing repetition is often not observed.
The five over-represented TRAIN classes attract 5.1% of all wrong predictions (2.1% expected), about
1.8 points of DEV accuracy: a minor effect. Their own DEV recall is only 47% despite ten times the
data, so same-source repetition does not generalize.

## 3. Where the errors come from (Phase 2, MEASURED)

Per DEV clip, the majority outcome of the four runtime-window phases was compared with the same
clip's dense training view and its span at phone cadence (`word_vocabulary_report.py`):

| Outcome under the runtime window | Clips | Share of errors |
|---|---:|---:|
| Correct | 398 | — |
| Wrong even on the dense, well-bounded training view (**discrimination / generalization**) | 327 | **78%** |
| — of which the correct word is still in the dense Top-5 | 151 | |
| Right dense, wrong once sampled at 3.75 fps (**cadence**) | 61 | 15% |
| Right at 3.75 fps on the span, wrong with the runtime context window (**window**) | 30 | 7% |
| Any of the above with accepted-hand fraction < 0.5 (**perception contributes**) | 144 | 34% |
| Wrong but correct word in the runtime Top-5 | 251 | 60% |

Reading:

1. **The dominant limit is cross-signer discrimination, not windows or cadence.** The model fits
   TRAIN (86.9% dense) but reaches 50.3% on new signers on the same clean view; 78% of runtime
   errors are already present on that view. The earlier governed attribution
   (GENERALIZATION_LIMITED) still holds for the deployed model.
2. **The correct word is usually close.** 60% of errors keep it in the Top-5 and 14% have it second:
   this is margin/variance, typical of too few independent signers per class (median 13).
3. **Signer diversity is the lever with measured effect.** Classes with more TRAIN signers do better
   (Spearman ρ = 0.18, p = 0.006). The existing Sem-Lex-enriched run (`word_track_semlex_01`)
   raises the covered classes from 34.8% to 51.6% on the identical DEV runtime windows.
4. **Cadence is real but secondary** (15% of errors; TRAIN itself drops to 60.5% at 3.75 fps).
   WORD v2 augmentation recovers part of it (below). A faster device cadence helps: 200 ms windows
   are 1–4 points better than 266 ms.
5. **Windows matter mainly when contaminated** by a neighbouring sign (continuous signing); clean
   runtime windows are within a few points of the human-boundary window. Boundary jitter of one
   observation costs 1.5–2.4 points.
6. **Perception is the hard floor for some signs.** Accuracy halves when hands are accepted in
   fewer than a quarter of observations; TABLE on the phone has no accepted hand at all.
7. **What does not help** (history, verified again where possible): hierarchical class/signer
   sampling (`SAMPLING_HARMFUL`), contrastive signer/cadence invariance (`NOT_SUPPORTED`), WORD v3
   neighbour context (no gain; worse on the phone set here: 18/22), and averaging recognizers
   trained on the same data (frozen + WORD v2: 44.7% vs WORD v2 alone 44.5%). More capacity was not
   indicated: the gap is generalization, not fit.

Existing candidates on the identical windows (pooled DEV runtime windows; Sem-Lex EVAL; phone):

| Model | DEV runtime windows | Covered / uncovered classes | Arm A NATURAL / CONTINUOUS windows | Sem-Lex EVAL | Phone oracle / runtime |
|---|---:|---:|---:|---:|---:|
| Frozen | 41.5% | 34.8 / 44.2% | 45.9 / 38.2% | 30.2% | 20/29, 19/22 |
| WORD v1 aug | 43.2% | 36.0 / 46.0% | 48.3 / 38.9% | 30.2% | 21/29, 19/22 |
| WORD v2 aug | 44.5% | 38.2 / 47.0% | 48.1 / 41.7% | 32.2% | 23/29, 19/22 |
| WORD v3 aug | 44.3% | 36.9 / 47.3% | 48.3 / 42.0% | 33.6% | 18/29, 18/22 |
| Sem-Lex naive (all 32 Sem-Lex signers) | 46.5% | 51.6 / 44.5% | 51.7 / 42.5% | n/a (trained on them) | 22/29, 21/22 |

<!-- Phase 3-5 sections follow -->

## 4. Intervention selected and results (Phase 3)

Evidence chain: errors are mostly cross-signer discrimination (78%), and new signers are the only lever with measured effect. So the intervention adds the human-accepted Sem-Lex clips from the 19 ENRICH-role signers (1,475 clips, 64 classes) to the WORD v2 recipe. The 13 EVAL-role signers stay untouched for every model. Architecture, contract, optimizer and DEV selection are unchanged. Paired runs (`artifacts/…/word_ec_semlex_01/`), each against same-seed controls with identical augmentation and no Sem-Lex:

| Arm (seeds 101/202/303) | DEV runtime windows vs control | Uncovered classes vs control | Sem-Lex EVAL vs control |
|---|---|---|---|
| Exposure-controlled (EC_P3 port) | −0.4 / 0.0 / 0.0 pts | ≈ 0 | +5.2 / +5.4 / +6.0 |
| Naive enrichment | +2.5 / +1.7 / +1.4 (p = 0.002 / 0.03 / 0.09) | 0 / **−3.5 / −3.4** (p < 1e-4) | +19 / +22 / +23 |

Exposure control removes most of the gain on this representation. Naive enrichment helps but, in two of three seeds, shifts the prior toward covered classes.

**Pre-registered candidate `WORD_BLEND_01`.** The rule was fixed on DEV calibration signers P5/P12/P21 before seeds 202/303 were scored: 0.5 × frozen + 0.5 × mean of the three naive runs, with no seed selected and no prior correction (correction gained ≤ 0.4 pts on calibration). It is one graph with the same I/O as the frozen model (`model/perception_vnext/word_blend.py`, `blend.keras` `e9bad094…`, 770,224 parameters).

| Metric (MEASURED) | Frozen | WORD_BLEND_01 | Paired |
|---|---:|---:|---|
| DEV runtime windows, 3.75 fps ×4 | 41.5% | **48.6%** | +281 / −50, p < 1e-30 |
| — uncovered 172 classes | 44.1% | 49.0% | +153 / −38 |
| DEV dense / 200 ms | 50.3 / 44.6% | 55.9 / 50.5% | p < 1e-10 |
| Arm A + CB NATURAL event windows | 45.9% | **52.5%** | +39 / −5 |
| Arm A + CB CONTINUOUS event windows | 38.2% | **44.7%** | +33 / −7 |
| End-to-end correct words, NATURAL / CONTINUOUS | 29.3 / 18.7% | 33.5 / 21.9% | same events |
| Sem-Lex EVAL (13 untouched signers) | 29.4% | **45.8%** | +531 / −23 |
| Classes improved / worse / same (independent data) | — | 132 / 21 / 83 | losses ≤ 1–2 clips each |
| Phone oracle / runtime (DEV-EXPOSED) | 20/29, 19/22 | 24/29, 20/22 | +1 / −0 runtime |

Remaining weaknesses: minimal pairs (CHAIR/SIT 19 confusions), and a larger relative hand-loss penalty (−21 pts at 50% loss, although the absolute level is still higher, 29.9 vs 25.3%).

## 5. Android readiness (Phase 4)

* The debug-only package is in `android/app/src/debug/assets/word_blend_candidate_01/` (TFLite `bc8a6c91…`, 3.2 MB). Host parity passed: max abs 1.8e-7, 0 Top-1/Top-5 mismatches, 816/816 DEV agreement, and padding invariance. Arm A, the decoder and the materializer are untouched; the input contract is identical.
* Host latency is 5.0 ms against 1.1 ms for the frozen model. The device ESTIMATE is about 12 ms per committed word, against 2.7 ms measured. The model runs once per event, not per frame. The device latency still needs measuring.
* **Not yet wired into the app.** The third debug engine ("Experimental + WORD blend") would edit locked baseline files, so it waits until the baseline checkpoint is approved and committed. Experimental stays exactly as tested.

## 6. Phone validation plan (Phase 5)

`docs/audit/probes/word_accuracy/phone_test_subset.py` chose 12 signs in five strata: anchors HELLO and HOME; signs both models handle (COLD, SEE, WAIT); blend gains (TIME, HOT, TIRED); signs hard for both (COOK, BAD, HEAR1); and a regression risk (MOUTH). Each sign is signed 3 times per engine. ASL Citizen TRAIN reference videos are in `artifacts/word_phone_protocol_01/reference/`. Until that run is done, the candidate stays a research/debug candidate.

## 7. Remaining limits and next step

1. Signer coverage is still the bottleneck. 156 of the 171 classes without Sem-Lex data have at least 5 Sem-Lex candidate signers (133 have at least 10), but they need the governed human form review: a side-by-side "same sign?" check against the ASL Citizen reference, using the existing P5-D6 viewer. **This is the most valuable next step.**
2. Minimal pairs that differ by repetition need more observations per sign; a faster device cadence would help, as 200 ms windows score better.
3. Perception (TABLE, flat hands) remains out of WORD's reach.

## 9. Pending approvals

The baseline checkpoint commit is 55 files: the 53 locked sources, `deploy/lock_live_experimental_baseline.py` and the manifest. The WORD research files (this report, the eval tools, trainer options, blend, export options, tests and debug asset) are a separate later commit. The tracker and schema entries for this milestone are deferred until the checkpoint is committed, so the locked `context/` files do not drift.
