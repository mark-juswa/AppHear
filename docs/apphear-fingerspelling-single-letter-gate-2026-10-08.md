# Fingerspell one-letter inference gate and deadline decision

Date: 2026-10-08. User-authorized one capture per letter, with confirmation.
No retraining, model export, dataset change or WORD change.

## What is actually wrong

V2.1 improved recognition, but its improvement was never evidence that A–Z was
solved. Frozen held-out phone-like letter recall is 63.16%, no-SPACE CER40.23%,
and only6/512 full strings are exact. M recall47.37% and Y42.11% are particularly
relevant to intended AMY captures; these sequence-alignment recalls are not
isolated-letter classification accuracies. See the independent result review.

The confirmed bottleneck is learned letter discrimination, combined with an
interaction asking a phrase-trained sequence recognizer to decode all evidence
between Start and Done. The 4K TRAIN manifest has no isolated-letter targets.
The auxiliary loss is letters-only sequence CTC, not a frame-labeled letter
classifier; its61-observation context can span most sparse clips. Model output
may change labels across setup, held poses, transitions and missing evidence.
CTC collapses adjacent identical labels, but a blank between two identical
labels legitimately preserves both. It cannot infer that an incorrect S or a
second A was unintentional. Arbitrarily removing repeats would damage BELLA.

The phone had partial hand evidence in previous AMY attempts. That is observed,
but no saved video, per-letter alignment or proficient-signer validation exists
for those attempts. Do not attribute their exact errors solely to visibility,
signing proficiency or geometry insufficiency. Tested export/Android parity
rules out the tested numerical integration mismatch. The prior outer-window
oracle did not support trimming as the primary fix. Generic ImageNet appearance
fusion did not establish a useful generalizing correction either.

What remains uncertain: how much error comes from inaccurate joint evidence,
loss of subtle thumb/contact/orientation appearance in XY geometry, insufficient
local supervision, or phone-domain differences. Existing evidence does not
separate these. Changing an architecture without compatible learned weights
cannot create an accurate new alphabet classifier overnight.

## Practical change completed

The supervisor approved changing the task to one letter at a time. The frozen
V2.1 model/Adapter/raw observations remain identical. A new exact CTC grammar
scores each singleton A–Z target from the existing unadjusted logits. It sums
all valid blank-before, contiguous-letter, blank-after alignments. It excludes
paths collapsing to multiple letters, including blank-separated duplicates.
All28 symbols remain in the stable log-softmax denominator. Blank27 penalty0.5
is subtracted once using float32 semantics. Empty or singleton SPACE can win
and request Retry. There is no class rule, vocabulary prior, confidence cutoff,
length bonus, dictionary, language model, Top-N UI or predicted-letter filling.

This directly prevents extra-letter output within a capture. It does **not**
prove the remaining single letter is correct. Log masses are not calibrated
correctness probabilities. No isolated-letter accuracy claim is made.

The isolated Android runtime now:

- previews at most one letter per Start→Done;
- appends it only when Use is pressed, without spaces;
- preserves confirmed repeated letters across captures;
- keeps confirmed letters on Retry and clears them on Clear;
- reports current accepted usable hand evidence;
- refuses zero-usable-hand captures before model/decoder invocation;
- keeps partially observable captures, chronology, masks and all real timesteps;
- retains greedy and fixed beam10 strings for comparison;
- saves bounded unadjusted logits/timestamps/usable flags for audit, with no RGB
  or landmark storage and no training admission.

Internal flag: FingerspellCapturePolicy.SINGLE_LETTER_ENABLED, restricted to
SEQUENCE_V2_1_EPOCH034_GEOMETRY_ONLY. Disable it to restore old whole-sequence
Fingerspell behavior; the old confirm() buffer method and greedy/beam remain.
The prior private V2.1 APK is also preserved for complete binary rollback.

## Validation completed

| Check | Evidence |
|---|---|
| Python mathematical/reference tests |66 passed, including exhaustive all28-symbol paths forT1/2/3, all26 letters, empty/SPACE, repeated labels, extreme/long logits, frozen penalty and no input mutation |
| Actual Kotlin source parity |54 fixtures; exact text; maximum log-mass difference4.547473508864641e-13 |
| Android host regression tests |161 passed,0failures/errors/skips |
| Xiaomi decoder parity |54fixtures exact; same maximum score difference |
| Xiaomi model parity |existing14-case V2.1 numerical/greedy/beam/padding/Adapter transfer check passed unchanged |
| Xiaomi flow/WORD ownership |new confirmation/repeated-letter/no-input/WORD exclusion test plus existing ownership and beam exclusion tests passed |
| Context Assist |3existing local regressions passed; no external service experiment |
| Protected inventory |1756existingfiles checked; only3intended Fingerspell runtime/buffer/ownership-test changes; no unexpected changes |
| APK assets |237existing application assets byte-identical to installed V2.1 reference, including frozen model/package |
| Static checks |Ruff and mypy4modules pass |

Device singleton decoder timings over54 mixed synthetic/native/sparse fixtures:
median0.536ms, p9510.470ms, maximum49.106ms. These are a mixed engineering fixture
distribution, not a live latency population or an accuracy dataset.

One engineering test initially revealed a SPACE-dominant path would force a
letter if only empty competed. The diagnostic was fixed before porting by
including singleton SPACE as a refusal competitor. A literal source-anchor
ambiguity was corrected before the runtime file was written. Neither correction
changed the frozen model or any prior decoder. No DEV tuning was conducted.

## Identities and exact changed files

Model checkpoint remains epoch034 SHA
3f92287c5ee82b2e0de1d396c4d27fe3b0efaed8af23b79b878740a56f1af638.
Model TFLite remains SHA
e78de274b967acf0ea9d30bd3f3ac4422a1ef8ebdd95c8676b57dd05fed75c4c;
manifest remains8edc998728fa41883abacbc8382359d6d61621bc259da78ca7c2ab6f8126d01e.
New private APK SHAeb629845aa3c859cc7e9ed375d3ed22414fe01db1a4345ca75f815e084fe5e4e.

Authoritative app checkout: C:/Users/Gigabyte/.codex/worktrees/fingerspell-oct04-integration/5. Apphear3,
HEADcee71d9f181695847936eb5f3605ea37eab82a95.
Existing changes are confined to FingerspellCore.kt (separate confirmLetter),
FingerspellRuntime.kt (isolated flag/guard/decoder/messages/diagnostics), and
FingerspellOwnershipInstrumentedTest.kt (synthetic fixture respects grammar;
all stale-WORD/sentence-preservation assertions retained).
New Android files: FingerspellSingleLetterDecoder.kt,
FingerspellSingleLetterTest.kt, FingerspellSingleLetterInstrumentedTest.kt.

Research additions: model/fingerspelling_single_letter.py,
tests/test_fingerspelling_single_letter.py,
tools/fingerspelling/single_letter_port.py,
tools/fingerspelling/single_letter_parity.py,
tools/fingerspelling/single_letter_evidence.py,
tools/fingerspelling/single_letter_android/ reviewed Kotlin sources/runner,
this report and the approved plan. Context registry/progress/memory are updated
separately. Existing unrelated dirty/untracked work is preserved.

All new evidence/private APKs are under artifacts/fingerspelling_single_letter_01.
Important files: fixture_manifest.json,jvm_parity.json,python_tests.xml,build.log,
instrumentation.log,context_regressions.log,xiaomi_fingerspell_single_letter_parity.json,
xiaomi_fingerspell_sequence_v2_1_parity.json,preservation.json,apk_identities.json,
installed_apk_integrity.json,live_session_inventory.json.

## Physical gate and final deadline recommendation

The supervisor confirmed three separate captures showing only A, then only M,
then only Y, and confirmed the matching visible previews. These are nonexpert
intended prompts; there is no expert validation of the actual signing. The
table is a bounded practical/engineering check, not an alphabet accuracy score.

| Intended prompt | Greedy on same logits | Beam10 on same logits | One-letter preview | Observations / usable | Cadence obs/s | Singleton decoder ms | Model+all decoders ms |
|---|---|---|---|---|---:|---:|---:|
| A | A | AAAA | A |55/42|6.70|9.96|459.22|
| M | EM | EMME | M |38/38|4.91|6.41|183.56|
| Y | empty | Y | Y |44/34|5.29|7.50|179.35|

Each capture spans7.53–8.13seconds of delivered observations; actual wall capture
is7.70–8.38seconds. Despite the suggested2–3seconds, do not relabel these as
shorter captures. No frames were trimmed, fabricated or forward-filled. All
three saved phone logits reproduce the exact constrained preview in Python.
The A/M capture logits illustrate why changing only CTC output grammar can
remove extra letters while retaining a useful existing letter hypothesis.
The frozen model is not improved by this change; inference is now conditioned
on the supervisor-provided fact that a capture represents one letter.

Live singleton-decoder median7.50ms; three-case max9.96ms. Model latency spans
69.50–107.04ms; retained diagnostic beam93.04–338.43ms. Total reported model+
three-decoders work179.35–459.22ms, excluding button queue/UI rendering and file
write. Java heap snapshots13.7–19.8MB, native177.5–181.7MB; these are not peaks
or incremental model memory. No runtime optimization is necessary for this gate.

**Decision: SINGLE_LETTER_FLOW_RETAIN_EXPERIMENTAL.** Use one letter per capture,
visually check the preview and press Use only if correct. This is the supported
non-training improvement for the deadline. Keep the whole-sequence APK and
internal flag as rollback. Do not present arbitrary full-name recognition or
all26-letter reliability as established; no reliable isolated-letter benchmark
exists. Do not continue tuning thresholds/decoder settings or launch another
model run to obtain a cosmetic pass.

The root bottleneck remains insufficient learned letter discrimination on the
existing phone task. We improved the task/decoder interaction, not the trained
classifier's information. Future true A–Z accuracy work needs trustworthy
isolated/letter-level evidence to diagnose that remaining problem. No new data
collection, annotation, supervised appearance training or architecture is
started here. The earlier human review packet remains zero verified labels.

Review: plan alignment and protection/transfer layers pass. Production accuracy
readiness remains unestablished (important limitation, not a hidden pass).
Recommended use is explicit experimental, supervised and confirmation-based.
No critical code/preservation issue was found. Human Use/Retry/Clear automation
is covered by synthetic engineering tests; this check did not claim human
complete-word confirmation or extra repeated-letter captures.

WORD, Candidate01, Adapter v1, frozen checkpoints/TFLite packages, Context
Assist, recognition ownership, WORD sentence state/UI/TTS remain unchanged.
No TEST access, new training, data download/extraction or production promotion.
