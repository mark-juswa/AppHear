# Stage 3 physical signing pilot — frozen procedure and actual stop

Status: **stopped after the first five physical attempts at signer request on 2026-09-30**.
The signer confirmed familiarity with the five phrases below and excluded YES GO SCHOOL
before collection. The original plan was three repetitions of each phrase (T01–T15).
Only T01–T05 were signed. T06 obtained a synthetic prediction cache but no signing began;
it is not a physical attempt. See conversation-phrase-assist-stage3-report.md and the
machine-readable pilot JSON for observations and honest denominators.

## Fixed scope

Start: feature/conversation-phrase-assist-mvp at
9b041eb600ffe0b138c59c031b9dfb5ae7c6ebdc, clean worktree.
Protected recognition baseline: 76d93cecd85bf9f76064d320aa4a5791b5f0704a.
Use unchanged gemini-3.5-flash-lite, provider contract, matcher and recognition.
Raw UI/Hear remains authoritative. This is a diagnostic opportunity measurement,
not an assisted-accuracy benchmark. Signer training relationship is unknown.

## Frozen five phrases

| ID | Synthetic hearing prompt | Intended anchors | Stage 1.1 precedent |
|---|---|---|---|
| P1 | Where are you going? | GO HOME | where_going |
| P2 | Where are you going? | GO WORK | where_going |
| P3 | Are you tired? | NO TIRED | are_you_tired |
| P4 | Are you tired? | YES NEED SLEEP | are_you_tired |
| P5 | How is your family? | FAMILY GOOD | multi_family |

All labels are exact members of the frozen 236-class manifest. The precedents are
synthetic provider results, not promises about the current cached reply set.
T05's actual typed prompt omitted the final question mark; this deviation is retained.

## Before rollout

1. Confirm the signer knows the five sequences and freeze the set before the first attempt.
2. Record anonymous signer ID, known/unknown training relationship, phone and camera setup.
3. Back up the currently installed APK, record its SHA-256, and retain it for restoration.
   APK restoration alone does not guarantee preservation of private application data.
4. Run offline safety gates first. Install a private debug build using
   `-PcontextPhraseAssist=true -PcontextPhraseAssistProvider=gemini -PcontextPhraseCapture=true`.
   Keep API keys local; release must keep assistance/capture off and keys empty.
5. Capture only `AppHearStage3`, `AppHearPhoneProduction`, `AppHearRecognition`, and crash
   diagnostic tags. Retain the exact scoped log and export JSON under ignored `artifacts/`.
   Record each attempt's host start/end epoch timestamps and app process ID separately.

## Each attempt

1. Start a fresh app process for a self-contained synthetic prompt. This prevents previous
   physical raw responses from being included in a later Free-tier Gemini request. Do not
   change the production context manager or provider to enforce this experimental setup.
2. Submit the fixed prompt through existing Text-to-ASL. Wait for `cache_complete`, inspect
   its complete `cached_candidate` records, and save the supplied conversation snapshot.
   Use a scoped `adb logcat -d` snapshot at this pre-camera point to inspect readiness;
   redirected live-file writes may be delayed. Keep a live stream throughout signing,
   rather than relying on a post-run snapshot that may have lost older records.
   If the cache is empty/timed out, record a preparation failure and wait/resubmit; do not
   change timeout settings or begin an unprepared signing attempt.
3. Record intended anchors, exact candidate coverage, and any manually judged compatible
   candidate separately. Lack of prediction coverage is not a visual-recognizer failure.
4. Tap existing Reply, wait for camera READY, tap Clear, and hold neutral hands.
   The observer records any extra committed events as well as intended events.
5. Sign the fixed intended sequence. For this first pilot, pause at neutral/READY between
   concepts. Record per-concept timing or observed commit boundaries when possible;
   uncertain event association must remain AMBIGUOUS. Do not discard bad predictions.
6. Tap existing Hear. Record the on-screen raw sentence, actual speech observation,
   `evaluation` plus all `evaluation_event`/`evaluation_candidate` records, and completion.
   Hear does not clear the raw sentence. The sidecar evaluation is hypothetical only.
7. Ask the signer to confirm the intended phrase was performed and note interruption,
   incorrect performed sign, missing READY, or navigation. Mark procedural invalidity
   explicitly; retain that attempt's original evidence.
8. End the log window, retain all committed events including extras, and restart for
   the next synthetic prompt. After the final attempt, restore and verify the original APK.

## Evidence export

From the feature checkout root, run:

```powershell
python -m eval.phrase_recoverability_capture --log artifacts/SESSION/scoped.log --output artifacts/SESSION/export.json
```

The parser retains original records/scores, distinguishes process IDs, checks multipart
cache/evaluation completeness, and does not reconstruct raw sentences or discard duplicate
events. Malformed/truncated JSON is an error. A missing logged record is a capture problem,
not proof that a sign produced no event. The exporter intentionally does not invent
physical ground truth or calculate metrics from injected Android test events.

Every confirmed attempt needs: attempt/phrase ID; intended sequence; synthetic input;
cached hypotheses/coverage; committed event order/IDs/Top-1/Top-5 scores; raw sentence;
matcher/shadow result; per-concept event association and uncertainty; validity notes.

## Classification and denominators

Classify association before viewing contextual desirability. Use signer timing and event
order; never choose an alignment solely to make a candidate recoverable. Retain ambiguous
alternatives without silently selecting the best. No decoder/sequence alignment is added.

- TOP1_CORRECT: the associated event's Top-1 equals the intended exact class.
- TOPK_RECOVERABLE: associated Top-1 differs, intended class appears in Top-5.
- TOPK_ABSENT: associated event exists but intended class is absent from Top-5.
- MISSING_EVENT: a confirmed intended sign has no associated committed event; segmentation,
  lifecycle or another upstream cause remains possible.
- SPURIOUS_EVENT: a confirmed extra event, based on timing/observations.
- AMBIGUOUS: insufficient evidence for a confident association/classification.

At phrase level retain all applicable categories: exact raw success, recoverable substitution,
non-recoverable substitution, spurious insertion, missing event, mixed, ambiguous/procedural.
Explicitly retain any RIGHT3 GO HOME-like example without modifying the matcher.

Report counts and denominators, not only percentages:

- Raw phrase success: raw SentenceBuilder sentence equals the intended sequence, over valid
  attempts; document any separate manually judged adequate match.
- Intended Top-1: correct associated concepts / all intended concepts in valid attempts;
  show missing and ambiguous concepts separately.
- Conditional Top-K recoverability: recoverable substitutions / confidently associated
  wrong-Top-1 events. Missing and ambiguous associations are not classification substitutions.
- Top-K absence: absent associated concepts / associated intended concepts, plus the
  fraction of all intended concepts; never conflate absent-class and no-event cases.
- Prediction coverage: exact intended sequence in cache / prepared valid attempts.
  Report compatible-only sequences separately with documented reasoning.
- Joint opportunity: prediction coverage AND all intended concepts visually supported,
  over valid attempts. Distinguish strict one-to-one opportunities from manually documented
  potential opportunities requiring deletion of spurious events. Neither is assisted accuracy.
- Spurious/missing frequency: both event counts and affected valid-attempt counts; keep
  uncertain classifications separate.

Choose the next intervention only after this physical evidence exists. Do not infer a
recognizer, sequence-handling, or decoder conclusion from synthetic test fixtures.
