# WORD Priorities After WORD_BLEND_02 (2026-10-18)

Research only. Android, Arm A, confirm-boundary, Candidate01, the materializer and SentenceBuilder are unchanged. No phone session was used. No model was trained in this milestone.

Protected TEST, E6 and Tier 3 were not opened. No candidate was selected on held-out results.

Labels:
- **MEASURED:** reproducible from the named files.
- **HYPOTHESIS:** an informed but untested explanation.
- **DEV-EXPOSED:** DEV checkpoint selection, or the phone set.

## 1. Verified protected state

| Item | State (MEASURED) |
|---|---|
| Branch / base | `claude/s2-r3-eval-suite` at `e2444ebb`; all later work uncommitted (65 paths) |
| Installed debug build | `DEBUG_WORD_BLEND_02_2026-10-18` lock **OK** (only the post-lock appendix of `WORD_ROBUSTNESS_2026-10-18.md` drifted) |
| Installed APK | sha256 `9b2f6bd9…`; on-device `base.apk` hash equal; archived in `artifacts/live_baselines/word_blend02_debug_20261018/` |
| Engines in that build | STABLE (S2-R2 + frozen WORD); EXPERIMENTAL (Arm A e10 + CB 0.7 + frozen WORD); EXPERIMENTAL_WORD_BLEND (WORD_BLEND_01); EXPERIMENTAL_WORD_BLEND_02 (WORD_BLEND_02, logs WORD_BLEND_01 on the same window) |
| WORD models | frozen TFLite `1ccf0afa…`; WORD_BLEND_01 Keras `e9bad094…` / TFLite `bc8a6c91…`; WORD_BLEND_02 Keras `7448597f…` / TFLite `40533bc3…` |
| Earlier locks | LIVE_WORD_BLEND_2026-10-18 and LIVE_EXPERIMENTAL_2026-10-17: drift only in files edited on purpose afterwards; their archives hold the exact originals (APK + source snapshot) |

## 2. What limits WORD accuracy now (MEASURED unless marked)

Population: independent runtime-window recall per class, pooling DEV with the EVAL-role signers of both Sem-Lex packages, counted per clip (`difficult_words.json`). A class is hard if recall ≤ 0.30.

| | Frozen | WORD_BLEND_01 | WORD_BLEND_02 |
|---|---:|---:|---:|
| Hard classes (of 236) | 98 | 78 | **64** |
| — not fittable on own TRAIN clips at 3.75 fps | 77 | 56 | 46 |
| — accepted-hand fraction < 0.45 | 20 | 18 | 17 |
| — lost mainly at phone cadence | 16 | 15 | 18 |
| — one dominant confusion partner | 13 | 12 | 7 |
| — fewer than 12 TRAIN signers | 15 | 9 | 9 |
| Clip accuracy, hands < 25% → ≥ 75% of observations | 18 → 37% | 23 → 46% | 25 → 50% |

**By Sem-Lex coverage, the 64 WORD_BLEND_02 hard classes split three ways:**

| Coverage | Classes | What it means |
|---|---:|---|
| Already covered by reviewed signers (24 package 01, 21 package 02) | 45 | Coverage is no longer their bottleneck |
| Uncovered, reviewable (≥ 5 Sem-Lex candidate signers) | 16 | Another review batch can reach these directly |
| No Sem-Lex candidates | 3 | No extra signers available |

The reviewable 16 are WE, MOUTH, OVER, BYE, LAST, SELL, TOOMUCH, SPECIAL1, TELL, STAND2, GET, INTRODUCE, ON, SORRY, START and TAKE.

**The covered-but-hard classes are mostly information-limited, not data-limited.** CLEAN, MONEY1, NIGHT1, MONTH, IN, SOMETIMES, NICE, PLEASE and others cannot be fit even on training clips at four to six observations. The sparse-only training experiment (WORD_ROBUSTNESS §3) showed this is not under-training. Their distinguishing cue is repetition count, a small hand movement, or handshape on the body; at the phone's observation rate that cue is often not in the window.

### Roles of the four suspected causes

| Cause | Evidence | Role now |
|---|---|---|
| Signer coverage | WORD_BLEND_02 added 40 reviewed classes: +11.1 points on 13 untouched signers for those classes (102 fixed / 0 broken) | Still the strongest **WORD-side** lever, but it now reaches about 16 hard classes directly |
| Temporal information (observations per sign) | Blend DEV runtime accuracy 40 / 49 / 51 / 55 / 57% at 400 / 266 / 200 / 133 / 100 ms; TRAIN fit 38 → 75% | The largest remaining **system-wide** lever; it lies in perception throughput, not in WORD |
| Data quality | Five classes (SORRY, HELLO, KNOW, GOOD, HAVE) are dominated by long single-source captures; they attract 4.4% of WORD_BLEND_02 errors (2.1% expected) | Small: at most about 1.3 points of all rows. A rebalance would risk the user's most-used words, and the phone set is too small to check it. **Not run** |
| Class confusion | Near-minimal pairs (CHAIR/SIT, NOW/TODAY, STAND2/JUMP, TOOMUCH/MUCH, FIND/PICK) | Mostly the temporal-information problem above. Dominant-pair classes fell from 13 to 7 with more signers |
| Hand evidence / lighting | Accuracy roughly doubles from the lowest to the highest hand-visibility band; synthetic dim light −8.9 points | A perception issue; Candidate01 is not changed for WORD benchmarks |

**PLEASE and SORRY**, as examples rather than special cases:
- **PLEASE** (recall 0.04): covered by Sem-Lex yet still not fittable at phone cadence. Its hand on the chest is often rejected (hand fraction 0.37), and it is read as HAPPY.
- **SORRY** (recall 0.25, but 0.67 on the dense view): mainly a cadence and hand problem, plus single-source training data.
- **Next step:** SORRY is #2 in review package 03. Real Sem-Lex signers would also dilute its single-source data — a HYPOTHESIS.

**Per-class change, WORD_BLEND_01 → WORD_BLEND_02:**
- Classes are counted as moved when independent recall changes by more than 5 points:

  | Moved | Classes |
  |---|---:|
  | Up | 57 |
  | Down | 52 |
  | Within ±5 | 127 |

- Most classes have only 2–9 independent clips, so individual moves are noisy.
- The largest drops are WHEN −0.20, BUY −0.19, TODAY −0.19, CITY2 −0.17, MORE −0.13 and DINNER1 −0.12.
- The aggregate gain is real (MEASURED, signer-cluster intervals). It does **not** mean every class improved.

## 3. Decision

| Option | Expected value | Decision |
|---|---|---|
| Review package 03, then the same enrichment rule (and blend rule) | About +11 points on the reviewed classes by package-02 analogy (HYPOTHESIS); reaches the 16 reviewable hard classes and other low-recall classes | **Prepared; needs human review** |
| Rebalance the heavy-class sources | ≤ 1.3 points at best; risk on the phone vocabulary | Rejected for now |
| Re-weight the blend or select by seed | Would be selection on held-out results | Not done |
| Sparse-only or cadence training | Measured negative | Do not repeat |
| Larger model or extra networks | No evidence of a capacity limit (dense TRAIN fit 87–91%) | Not done |
| More observations per second (perception) | +3 to +5 points across classes (MEASURED offline curve) | Recommended as a **separate, isolated perception investigation** |

No new WORD candidate was trained, so there is no new Android candidate. **WORD_BLEND_02 stays the reference.**

## 4. Prepared for review: package 03

`artifacts/semlex_review_03/review.html` is ready for review:
- 30 classes from `docs/audit/probes/word_accuracy/semlex_review_priority_03.csv`, ranked by WORD_BLEND_02 recall × candidate signers, excluding everything already covered or reviewed;
- 63 form rows and 274 videos (148 Sem-Lex TRAIN clips from distinct signers, plus ASL Citizen TRAIN references);
- export file: `semlex_review_03_decisions.csv`;
- the same decision set as package 02, with every row starting UNDECIDED.

After review, the steps are mechanical:
1. ingest (`semlex_review_ingest.py`, generalized to package 03);
2. three seeds with the same recipe and cap;
3. WORD_BLEND_03 under the same pre-registered rule;
4. paired comparison against WORD_BLEND_02 on identical windows, with a new held-out Sem-Lex population for the package-03 classes.

## 5. Proposed checkpoint commits (awaiting approval; nothing committed)

| # | Commit | Contents |
|---|---|---|
| A | Phone-first diagnosis and S2-R3 Arm A e10 debug package | `docs/audit/RECOGNITION_V3_PHONE_FIRST_2026-10-17.md`, `docs/audit/S2_R3_ARM_A_E10_PHONE_PACKAGE_2026-10-17.md`, `docs/audit/probes/phone_first/*` (3), `docs/audit/probes/event_reliability/*` (21 ledgers), `eval/runtime_diagnostics/phone_replay_compare.py`, `tests/test_phone_replay_compare.py`, `tests/test_s2_r3_arm_a_phone_package.py`, `deploy/export_s2_r3_arm_a_phone.py`, Arm A debug assets (5), `PhoneS2Runner.kt`, `PerceptionVNextLiveRecognitionActivity.kt`, `PhoneS2ParityInstrumentedTest.kt` |
| B | Debug Stable/Experimental engine selector with confirm-boundary, exactly as live-tested on 2026-10-17 | `PhoneCausalCore.kt`, `PhoneProductionSession.kt`, `PhoneRecognitionConfiguration.kt`, `RecognitionEngineSettings.kt`, `RecognitionActivity.kt`, `SettingsContent.kt`, three layouts, `strings.xml`, `ExperimentalRecognitionConfigurationTest.kt`, `confirm_boundary_parity.tsv`, `deploy/export_confirm_boundary_parity_fixture.py`. Five of these files were edited again later, so B is staged from the archived 2026-10-17 source snapshot (hash-checked against the lock), not from the working tree |
| C | WORD vocabulary evaluation, WORD_BLEND_01/02 and their debug engines | `eval/runtime_diagnostics/{word_vocabulary_eval,word_vocabulary_report,camera_condition_study,semlex_review_package,semlex_review_ingest}.py`, `model/perception_vnext/{recognition_v2_robust_aug,word_blend}.py`, `deploy/export_word_v2_candidate.py`, `deploy/lock_live_experimental_baseline.py`, `docs/audit/WORD_*.md` (3), `docs/audit/baselines/*.json` (3), `docs/audit/probes/word_accuracy/*`, `tests/test_word_exposure_control.py`, blend debug assets 01/02 (44), `WordBlendParityInstrumentedTest.kt`, and the current versions of the five B files (the WORD-blend engine delta) |
| D | Tracker and schema | `context/progress-tracker.md`, `context/feature-schema.md` |

- **Excluded:** `.claude/launch.json` (local preview configuration).
- **Kept local:** bulk artifacts under `artifacts/` stay outside git (ignored), as before.
- **Not done:** no push and no merge.

## 6. Next most valuable steps

1. **Human review of package 03** (30 classes, about 63 rows). Then WORD_BLEND_03 under the same rule; it becomes an Android candidate only if it reproduces gains on both independent populations without significant regressions.
2. **An isolated perception-throughput investigation.** Why does the phone deliver about 5 observations per second? Candidate01 takes about 90 ms per frame. The question is whether pose cadence can be raised without changing Candidate01's outputs, for example through threading or scheduling, or by running the hand refiner only where needed. The offline curve predicts +3 to +5 points for every WORD model. Run it as its own milestone with parity gates; it does not belong in WORD development.
3. Only then revisit WORD-side modelling of repetition and minimal pairs. Their limit is temporal information, which step 2 addresses first.
