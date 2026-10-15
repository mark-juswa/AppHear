> **Connected-phone follow-up (October16):** Eleven Android gates and a finalized757-observation engineering capture now pass. Nonexpert physical review is complete with uncertainty; see [device validation](recognition-v3-stage2-device-validation-2026-10-16.md). Earlier phone-absent/pending-device statements below are historical.

> **Compact capture follow-up:** The previously missing profile is now implemented and built. See [compact capture delivery](recognition-v3-stage2-compact-capture-2026-10-15.md). Physical capture and recognition improvement remain unverified.

# Recognition V3 Stage 2 — continuous WORD investigation

2026-10-15, Asia/Manila. **OFFLINE_DIAGNOSIS_COMPLETE_CONTEXT_RESET_REJECTED**.
Stage2 remains open; no continuous-signing accuracy or runtime improvement is claimed.

## Decision

Do not shorten recovery or deploy an unconditional S2 history reset. The strongest available
reviewed capture points mainly to missing ACTIVE acquisition, with perception evidence loss in
both TABLE attempts. The single closed-loop history-reset experiment increased non-sign events.
Keep the existing integrated runtime and Stage1 concurrency disabled.

The next practical step is a short, qualified-signer, matched-framing Android capture of transition
acquisition and evidence availability, including adjacent repeated signs and held-position controls.
Choose a boundary/readiness change only after that evidence distinguishes the mechanisms.
No new training, classifier, cloud work, feature representation or fingerspelling policy is needed
to run that experiment.

## Restored baseline and historical correction

New isolated branch `codex/recognition-v3-stage2` starts at completed Stage1 validation
`e196a8d501386091eae52f59df0fa349e26b43e2`, following runtime implementation `5d73b412`
and canonical integrated `4c99ac24`. Protected `76d93cec`, Stage1 worktree, original
research evidence and canonical checkout remain preserved.

The September28 report `APPHEAR_CONTINUOUS_TRANSITION_AND_READINESS_01_REPORT.md` describes
diagnostics awaiting capture. However, the private research artifacts also contain completed
`session_20260927T162103Z`, human-reviewed labels and `transition_analysis/result.json`.
The earlier Stage1 handoff missed these later-available files. Its statement that A/B evidence was
still pending is superseded by this audit; historical files were not rewritten.
File timestamps/session names are provenance, not an assertion about report chronology.

Revalidated all 1,364 observations, exact binary tensor hashes, source image identities, seven
BEGIN/COMPLETE block pairs, all ten event identities, every lifecycle state, re-arm transitions,
materializer indices and one diagnostic UI delivery per event. Stored human-boundary analysis
reproduced **exactly**. Used the finalized `human_boundaries.json`; earlier invalid/overlapping
drafts and pending chat amendments were not substituted.

This is one design session with unknown signer proficiency, not held-out-signer accuracy evidence.
The newer Stage1 20-second recordings contain timing/validity/UI summaries, but not this complete
S2/lifecycle/physical-boundary linkage; their current failure cannot be assigned retrospectively.

## Where consecutive signs pass, and where they can fail

| Stage | Current behavior and diagnostic consequence |
|---|---|
| Camera/perception | KEEP_ONLY_LATEST, genuine capture timestamps, full DWPose-t then refiners. Sparse delivery can miss transitions; a proposed/coordinate-valid hand is not necessarily an accepted hand. |
| Features/S2 | Shared raw-v1 to378 math, pinned normalization and frozen S2-R2; bounded61-observation model prefix continues through recovery. At5FPS that prefix can cover roughly12s. This is a hypothesis about context sensitivity, not proof of the failure cause. |
| Candidate opening/Admission | IDLE+ACTIVE opens immediately through PASS_THROUGH. No ACTIVE means no candidate; classifier confidence does not control readiness. |
| Completion | POST must persist266.616ms; ACTIVE cancels pending completion even at the confirmation boundary, potentially merging two physical signs. Sustained PRE can discard a candidate, including consuming an ACTIVE observation at the reset boundary. |
| Recovery | Event enters WAIT; requires399.924ms observed PRE/POST after commit. ACTIVE resets recovery; gaps over533.232ms reset persistence. ACTIVE while WAIT cannot call Admission or open a new candidate. |
| Materializer/classifier | Only emitted events get bounded genuine-source windows, frozen V2[96,350]+mask and one classifier invocation. These stages cannot classify a sign for which no event was opened/emitted. |
| Sentence/UI | Increasing event-ID guard prevents repeated processing of the same event. Separately, SentenceBuilder.add suppresses equal adjacent glosses even from different events. The UI renders that sentence snapshot. |

The 400ms recovery is therefore one possible barrier, not the entire problem. Changing a timer
does not create absent ACTIVE observations, recover absent hand evidence, or separate a merged
episode without a useful boundary. Removing gloss deduplication alone would expose more repeated
false outputs while the event false-activation problem remains.

## Strongest reviewed evidence

Counts below refer to human-reviewed source-observation intervals, not camera frames.

| Condition / sign | Observations | S2 ACTIVE | Ready/IDLE observations | Any accepted hand |
|---|---:|---:|---:|---:|
| Hands-down HELLO | 6 | 0 | 6 | 3 |
| Hands-down HOME | 9 | 0 | 9 | 7 |
| Hands-down TABLE | 10 | 0 | 10 | 0 |
| Hands-up HELLO | 11 | 11 | 0 | 11 |
| Hands-up HOME | 15 | 0 | 13 | 15 |
| Hands-up TABLE | 14 | 0 | 14 | 0 |
| Hands-up final HELLO | 7 | 0 | 7 | 6 |

The final hands-down HELLO was explicitly uncertain and excluded from confident-sign metrics.
Six of seven confidently reviewed signs had **zero ACTIVE**. All their subsequent event misses
cannot be explained by re-arm alone.

Hands-up HOME starts in WAIT for two observations, then remains IDLE for13 observations.
S2 stays POST throughout; max ACTIVE probability0.0623 despite accepted hands and available hand
motion in all15 observations. Recovery completes200.277ms after its reviewed onset, but no new
candidate opens afterward. TABLE has no accepted hand in either condition. Proposed hands and
coordinate-valid joints are retained separately and must not be counted as accepted evidence.

Hands-up HELLO has one event whose logical onset predates the reviewed onset by two observations
(344 versus346), hence the old evaluator's EARLY_OR_WRONG_EPISODE flag. It classified HELLO and
delivered once. That does not establish a generalization accuracy result.

Four logical events are fully contained within reviewed non-sign intervals:
seat/body reposition IDs4/5, standing/moving ID6, phone interaction ID10.
Open-hand-hold and grooming also overlap events whose onsets lie outside the reviewed negative
interval; those are retained for manual attribution, not automatically counted as false events.
No product false-positive rate is inferred from this one designed cohort.

Body availability also differs between conditions (all8 points in reviewed A signs versus roughly
5 in B); framing and hand visibility are confounds. Reviewed originals show visible hands in
selected TABLE frames, but there is no per-frame landmark truth or independently verified lexical
execution. Do not equate missing accepted hands with a proven specific refiner defect.

## Sparse observation contribution

Prior reviewed positive-span spacing: hands-down p50/p95 **267.036/467.313ms**, hands-up
**200.277/267.036ms**. One hands-down gap exceeds533.232ms.
A transition shorter than an observation gap can be invisible, and two ACTIVE observations are
needed to demonstrate the current minimum span. Sparse sampling can also delay completion/recovery.
The hands-up HELLO end-to-commit interval was600.831ms, then400.554ms to re-arm.

However, hands-up HOME/TABLE supplied15/14 reviewed observations, so their misses cannot simply
be assigned to a single skipped brief transition. The saved images are processed observations;
unprocessed sensor frames are unavailable. A denser counterfactual and true camera drop counts
cannot be reconstructed without inventing data.

Stage1 remains mixed: front WORD4.64→4.36FPS; FINGERSPELL4.93→6.07FPS, higher PSS, unchanged
same-pixel hand outputs. No Stage1 accuracy improvement is assumed or Stage1 optimization enabled.

## One implemented alternative, evaluated offline

**Hypothesis:** retained POST model context contributes to subsequent acquisition failure.
**Ablation:** clear only the normalized S2 model-prefix buffer on the observation *after* causal
REARM_COMPLETE. Keep raw features/deltas, genuine source IDs/timestamps, weights, normalization,
all timers and Admission unchanged. Run closed-loop: candidate S2 outputs drive the same existing
decoder replay, which determines subsequent reset boundaries. No forced physical-boundary resets,
future labels, threshold search or synthetic camera samples.

Before probing, reproduced raw-to378 features and normalization with **zero absolute error**.
Frozen TFLite probability max error versus Android was **8.3446503e-7**; **zero argmax mismatches**
over1,364 observations. The no-reset closed-loop arm reproduced all original events and lifecycle
states. This rules out a feature/normalization serialization or host-versus-device S2-state mismatch
for these saved inputs; it does not prove perception or the learned state semantics are correct.

| Closed-loop arm | Events in full session | Fully contained reviewed non-sign events |
|---|---:|---:|
| Unchanged history | 10 | 4 |
| Reset S2 prefix after re-arm | 20 | 9 |

Resetting recovered some ACTIVE evidence and introduced new overlapping logical episodes, including
one within hands-up TABLE, but did not reacquire hands-up HOME. An apparent TABLE event despite no
accepted hands emphasizes that additional events are not necessarily useful recognition.
Candidate windows were not sent through the classifier/UI: the state/event safety screen already
failed. No positive event overlap is reported as lexical correctness. **Reject this candidate for
Android rollout; do not start a history-length/reset-timing sweep on this same cohort.**

## What was implemented and checked

- New `eval/runtime_diagnostics/recognition_v3_stage2_audit.py`: read-only reproduction, per-sign
  readiness/accepted-evidence/cadence decomposition, same-input S2 parity and explicit opt-in probe.
- Existing reference replay gained an optional prediction hook with immutable capture-identity
  checks. Default recorded-probability replay behavior is preserved.
- New real-capture TSV fixture and Kotlin test exercise the **actual current shared decoder**:
  all1,364 recorded before/after states, actions and event IDs match; all ten commit indices match.
- Separate Kotlin mechanism checks demonstrate WAIT blocking and two distinct synthetic HELLO
  events collapsing to one sentence entry. These reproduce existing limitations, not new accuracy.
- **119 host tests passed**, including existing continuous-transition, recovery, Admission,
  materializer, trace and FINGERSPELL regressions; **194 Android JVM tests passed**.
  Existing669-row Keras/TFLite S2 fixture parity passed. Ruff/mypy for new Python sources passed.
- The initial host run lacked the ignored historical checkpoint in the new worktree. Provisioned
  hash-identical local copies of that1.6MB checkpoint and its normalization, then all119 passed;
  no retraining/download or test weakening.
- Shared-state checker: **581 hashes PASS**. Integrated compile used fake services, OriginalWords,
  automatic FINGERSPELL and coordination; generated Stage1 concurrency/profile flags both false.
- No main/debug/release Android runtime/UI, assets, model or feature math changed. No new app APK,
  install, camera test, FPS claim or physical-device result was produced this stage.

## Smallest practical Android follow-up

ADB discovery returned **no connected devices**. The prior closure remains unexplained.
Before any capture, reconnect/unlock the phone, preserve current app data, then save read-only
uptime/boot reason, AppHear exit-info/crash records, thermal state, battery and available memory.
If the phone is unstable, preserve receipts and stop; do not run intensive loops or clear logs.

Read-only preflight once a device is actually connected (save outputs locally):

```powershell
$stage2Adb = 'D:/AndroidStudio/Android/Sdk/platform-tools/adb.exe'
& $stage2Adb devices -l
# Set this to the one authorized, stable phone shown above.
$stage2Serial = 'SERIAL'
& $stage2Adb -s $stage2Serial shell cat /proc/uptime
& $stage2Adb -s $stage2Serial shell getprop ro.boot.bootreason
& $stage2Adb -s $stage2Serial shell getprop sys.boot.reason
& $stage2Adb -s $stage2Serial shell dumpsys activity exit-info com.example.apphear
& $stage2Adb -s $stage2Serial shell dumpsys thermalservice
& $stage2Adb -s $stage2Serial shell dumpsys battery
& $stage2Adb -s $stage2Serial shell cat /proc/meminfo
```

The supported seven-block diagnostic APK can be built with the **current integrated preset**,
including OriginalWords and the independent FINGERSPELL/coordination features:

```powershell
$env:JAVA_HOME = 'C:/Program Files/Java/jdk-17'
& tools/android/build_working_baseline.ps1 -Configuration fake -OriginalWords -Tasks @('assembleDebug','-PperceptionVNext=true','-PphoneCausalRecognition=true','-PrecognitionV3ParallelHands=false','-PrecognitionV3Profile=false')
```

After a successful build and stable preflight, update with `adb install -r` and use the exact
launch extras and seven-block review procedure in the earlier transition report. Fake services
support recognition isolation; this does not validate live external service credentials. No
compact-profile or candidate-reset launch extra exists, and none is implied by this command.

Use one ASL-proficient design signer, stable framing/lighting/distance, unchanged serial perception
and frozen models. Keep output hidden from the signer to avoid adapting movement to predictions.
The minimal new content is:

1. HELLO→hands-down→HOME, without deliberately waiting for READY.
2. HELLO→HOME with hands in signing space and natural transitions.
3. HELLO→HELLO with a genuine second execution, without hands-down reset.
4. One HELLO followed by a held final position, then one ordinary hand/body movement.

Mark physical lexical onset/end, held-position and ordinary-motion intervals independently from
predictions, or explicitly uncertain. Retain genuine observations, accepted/proposed hand evidence,
source images, exact378/normalized/S2 outputs, full decoder actions/recovery, immutable event IDs,
window source IDs and lexical/UI delivery. Analyze events separately from sentence text.

The existing seven-block observer/exact recorder is already integrated and runnable for A/B and
negative controls (commands in the earlier report). It does not have an adjacent-repeat block:
a compact four-block profile or supplementary repeat annotation must be added before calling this
entire minimum cohort automated/ready. Do not relabel the old HELLO→HOME→TABLE→HELLO sequence as
an adjacent-repeat test. No new diagnostic UI/profile was built in this investigation.

First compare signs with usable accepted evidence: is ACTIVE missing while READY, useful ACTIVE
blocked during WAIT, or one episode spanning two reviewed signs? For TABLE, inspect proposal→crop→
presence rejection and hand identity through overlap before assigning an S2-only cause.
Count held-position duplicates and bounded non-sign events. Score lexical/window errors only for
distinct events. This evidence determines whether the next candidate should address perception
availability, learned transition acquisition or lifecycle handoff; do not choose by timer alone.

Promotion requires a later matched, independent-signer end-to-end comparison with missed/merged/
duplicate/false events, lexical output and phrase error reported. This study does not satisfy it.

## Reproduction and preservation

Run from this worktree using the existing Python environment. The source capture remains read-only
in the original research checkout:

```powershell
python -m eval.runtime_diagnostics.recognition_v3_stage2_audit --session "F:/ASL DATASET/5. Apphear3/artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/continuous_transition_readiness_01/device_capture/session_20260927T162103Z" --out evidence/recognition_v3_stage2_20261015/transition_audit.json --verify-s2 --context-reset-probe evidence/recognition_v3_stage2_20261015/context_reset_probe.json
```

Committed compact audit/probe outputs, source/fixture hashes and validation manifest live in
`evidence/recognition_v3_stage2_20261015/`. Private images/tensors/checkpoint and JVM/host receipts
remain local under their original or ignored artifact paths. No source capture or prior result
was overwritten. Discarding the offline probe requires no app rollback; the canonical checkout
and saved serial APK remain intact. Stage1 stays default-off and its evidence is retained.

## Review

Plan alignment PASS; engineering/contract integrity PASS for tested inputs; runtime promotion
FAIL/not attempted. No critical implementation finding. Three important open evidence limits:
unknown signer proficiency/perception-versus-S2 attribution; unavailable stable phone/adjacent-repeat
capture; unvalidated boundary/readiness solution. Runtime≥15FPS and held-out phrase accuracy remain
unmet/unverified targets, not passed checks. Recommendation: retain audit and rejected-ablation
evidence; acquire the minimum source-linked cohort before selecting a runtime policy.
