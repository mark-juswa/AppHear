# Stage 3 — first-round physical signing pilot

Date: 2026-09-30. Status: **STOPPED_AFTER_FIVE_ATTEMPTS_AT_SIGNER_REQUEST**.

The signer completed one attempt of each of five familiar phrases, then chose to stop instead of repeating them. The fixed plan had 15 attempts (five phrases, three repetitions). T06 obtained a complete synthetic prediction cache but Text-to-ASL was closed before Reply; no T06 signing or recognition event occurred. T06 is preparation only and is excluded from every physical denominator.

This is a small diagnostic from one signer whose training-data relationship is unknown. It is not a held-out cross-signer accuracy estimate, assisted accuracy result, or basis for changing the matcher.

## Repository and safety boundary

- Feature branch: feature/conversation-phrase-assist-mvp. Stage 3 began from 9b041eb600ffe0b138c59c031b9dfb5ae7c6ebdc. Collection began from 79bdc97079f52c46642a7d9bbfc8874f432dd771; the first five attempts were checkpointed at 8f222a30ff0d392d76e918b13b7a88f922b8b430.
- Protected branch baseline/apphear-s2-r2-integration-complete-2026-09-26 still resolves to 76d93cecd85bf9f76064d320aa4a5791b5f0704a.
- The only runtime changes for Stage 3 were the prior default-off, debug-only diagnostic records. This collection changed no recognition, provider, matcher, threshold, SentenceBuilder, UI, Hear/TTS, or release code. Context Assist remained shadow-only.
- The complete machine-readable physical evidence is in conversation-phrase-assist-stage3-pilot.json. It retains exact predicted phrases, raw sentences, event IDs, Top-1 and Top-5 labels/scores, shadow results, classifications, setup/post-boundary events, and procedural notes. Private scoped logcat exports remain under ignored artifacts/conversation_phrase_stage3_20260930/; no frames, landmarks, tensors, audio, or API key were added to the repository.
- Fresh app processes were used between physical attempts so the Gemini Free-tier project received only each attempt's synthetic hearing prompt. Cached natural English was not treated as signed ground truth.

The capture code was added in the Stage 3 preparation commit, before the physical run:

| Source path | Capture purpose |
|---|---|
| android/app/build.gradle.kts | Default-off debug capture flag; release hard-disabled |
| android/app/src/main/java/com/example/apphear/contextassist/Stage3Diagnostics.kt | Bounded structured cache, committed-event, and evaluation records |
| android/app/src/main/java/com/example/apphear/RecognitionActivity.kt | Observe only accepted completed evidence events |
| android/app/src/main/java/com/example/apphear/contextassist/ConversationPhraseAssist.kt | Log published cache and completed shadow evaluation |
| eval/phrase_recoverability_capture.py and eval/test_phrase_recoverability_capture.py | Export and test multipart diagnostic records |

This continuation changed only the pilot JSON, protocol, report, progress tracker, and session handoff. No runtime instrumentation was edited while observing the physical signs.

The unchanged production seam copies Top-5 from the recognizer's single completed inference after the increasing event-ID guard; raw Top-1 still reaches SentenceBuilder and UI. RecognitionActivity observes completed evidence. Hear speaks the raw sentence and starts sidecar evaluation on a snapshot. Stage3Diagnostics emits cache, committed-event, and evaluation records without feeding results back into product output. The host exporter checks record completeness. T02 exceeded the existing eight-event sidecar buffer, so its shadow evaluation correctly returned INCOMPLETE_EVIDENCE; the live committed-event records still preserve IDs 3–12 and their Top-5.

## Fixed phrases and recorded attempts

YES GO SCHOOL was excluded before collection because the signer said it was unfamiliar; the signer chose five phrases. Each remaining phrase was attempted once. READY pauses and Clear were requested before signing. The exact T05 typed prompt omitted the final question mark. One sign retry and one double Hear tap were retained, not silently discarded.

| ID | Synthetic prompt | Intended concepts | Cached expected-concept hypotheses | Exact prediction coverage |
|---|---|---|---|---|
| T01 | Where are you going? | GO HOME | GO HOME; GO SHOP1; GO WORK; GO SCHOOL | Yes |
| T02 | Where are you going? | GO WORK | GO HOME; GO SHOP1; GO SCHOOL; GO WORK | Yes |
| T03 | Are you tired? | NO TIRED | YES TIRED; NO TIRED; TIRED VERY TODAY; YES BECAUSE WORK HARD | Yes |
| T04 | Are you tired? | YES NEED SLEEP | YES TIRED; NO TIRED; FEEL VERY TIRED TODAY; YES BECAUSE WORK DAY | No |
| T05 | How is your family | FAMILY GOOD | FAMILY GOOD; THEY1 BUSY WORK SCHOOL; FAMILY GOOD YOUR | Yes |

T05's natural prediction “My family is doing very well, thank you” pairs with FAMILY GOOD anchors. The “thank you” claim is not supported by those anchors. This is the already known semantic-grounding limitation; it was recorded, not fixed.

## Raw and event-level evidence

Scores in parentheses below are each event's Top-1 score. The JSON artifact contains all five labels and scores for every event, including setup and post-Hear events.

| Attempt | Raw SentenceBuilder text at first Hear | Committed event order at boundary | Existing matcher/shadow result |
|---|---|---|---|
| T01 | GIFT HOME GIVE COME | 3 GIFT (.203), 4 HOME (.345), 5 GIVE (.301), 6 COME (.297) | NO_MATCH_OR_AMBIGUOUS; no assisted phrase |
| T02 | PERSON WORK MOUTH STUDENT MOUTH TURN RIGHT3 COME STUDENT RIGHT3 | 3 PERSON (.307), 4 WORK (.690), 5 MOUTH (.162), 6 STUDENT (.321), 7 MOUTH (.254), 8 TURN (.139), 9 RIGHT3 (.315), 10 COME (.624), 11 STUDENT (.271), 12 RIGHT3 (.267) | INCOMPLETE_EVIDENCE; no assisted phrase; evaluation buffer retained IDs 5–12 |
| T03 | NO LIVE2 GIVE | 1 NO (.940), 2 LIVE2 (.518), 3 GIVE (.352) | NO_MATCH_OR_AMBIGUOUS; no assisted phrase |
| T04 | YES NEED SLEEP | 1 YES (.955), 2 YES (.655), 3 NEED (.989), 4 SLEEP (.996) | NO_MATCH_OR_AMBIGUOUS; no assisted phrase |
| T05 | FAMILY HOT AFTERNOON | 1 FAMILY (.784), 2 HOT (.356), 3 AFTERNOON (.373) | NO_MATCH_OR_AMBIGUOUS; no assisted phrase |

T01's setup MAN and COME occurred before its confirmed start/Clear; they are retained outside the first Hear sentence. The signer accidentally tapped Hear twice. Only the first complete Hear evaluation is the T01 outcome; the later evaluation and commits are preserved separately. T02 setup FEEL and TELL likewise occurred before its first Hear sentence and are not mapped to intended signs. T05 events after the first Hear are excluded from attempt metrics; the signer later said those were not deliberate signs.

| Attempt | Intended-to-event classification | Phrase-level classification |
|---|---|---|
| T01 | GO → event 3 GIFT, GO absent from Top-5; HOME → event 4 HOME Top-1. Events 5–6 are extra despite only GO/HOME intended. | Nonrecoverable substitution plus two spurious insertions |
| T02 | GO → event 3 PERSON, GO absent from Top-5; WORK → event 4 WORK Top-1. Events 5–12 are additional, but the signer did not clearly confirm their timing/source. | Nonrecoverable substitution; possible extra-event noise, retained as ambiguous |
| T03 | NO → event 1 NO Top-1; TIRED → event 2 LIVE2, TIRED absent from Top-5. Event 3 GIVE was not intended. | Nonrecoverable substitution plus one spurious insertion |
| T04 | YES → event 1 YES; NEED → event 3 NEED; SLEEP → event 4 SLEEP, all Top-1. Event 2 duplicated YES and SentenceBuilder collapsed the duplicate. | Exact raw phrase; one duplicate committed event |
| T05 | FAMILY → event 1 FAMILY Top-1. First GOOD → event 2 HOT, GOOD absent from Top-5. Signer deliberately retried GOOD → event 3 AFTERNOON, GOOD fourth in Top-5 at .142. | Procedural retry: first-pass nonrecoverable substitution, retry recoverable in Top-5; excluded from strict planned-sequence aggregate |

The repeated RIGHT3 pattern appeared twice in T02 (events 9 and 12), after the confirmed GO/WORK pair. Its exact physical source is unconfirmed. This is not evidence that the current matcher should be changed to delete those events.

## Descriptive measurements

The strict planned-sequence aggregate includes T01–T04 (four attempts, nine confidently associated intended concepts). T05 is shown separately because GOOD was deliberately performed twice. The all-observed counts include T05 for context but do not turn its retry into a clean attempt.

| Measure | Result | Interpretation |
|---|---|---|
| Exact raw phrase | 1/4 strict; 1/5 all observed | T04 matched despite a duplicate YES event |
| Intended Top-1 | 6/9 strict concepts | GO, GO, and TIRED were wrong in T01–T03 |
| Conditional Top-5 recoverability after wrong Top-1 | 0/3 strict wrong events | Intended labels absent from all three associated wrong Top-5 lists |
| Conditional Top-5 absence after wrong Top-1 | 3/3 strict wrong events | GO in T01/T02 and TIRED in T03 |
| Exact context prediction coverage | 3/4 strict; 4/5 all observed | T04 YES NEED SLEEP was not predicted |
| Joint exact context + visual opportunity | 0/4 strict | This is an opportunity ceiling, not assisted accuracy |
| Confirmed spurious events before first Hear | 4 events across 3/4 strict attempts | T01 two, T03 one, T04 duplicate YES; T02 eight extra events remain ambiguous |
| Confidently identified missing intended events | 0/9 strict concepts | All nine have an associated event; this does not rule out missing-event problems elsewhere |
| First-pass T05 GOOD | Top-5 absent | Excluded from strict aggregate |
| Deliberate T05 GOOD retry | Top-5 rank 4, score .142 | One recoverable wrong-Top-1 event, requiring a retry and handling the earlier HOT event |

Including T05's first pass only as a descriptive sign observation gives four absent intended labels among four wrong first-pass Top-1 events. That is not a 15-attempt pilot estimate. There was no clean wrong-Top-1 substitution with intended Top-5 support in T01–T04. T05's retry is the sole observed Top-5 recovery opportunity, but the actual raw output remained FAMILY HOT AFTERNOON and the existing matcher abstained.

## Diagnostic capture, checks, and limitations

The Stage 3 capture implementation was committed before this collection: default-off capture flag, structured cache/event/evaluation logging, bounded host export, Android shadow-safety assertions, and parser tests. The current work only records the five physical attempts and updates documentation. The earlier preparation gates passed: JVM 107/107; capture parser 4/4; debug and release builds; connected shadow ON 9 passed/2 conditional skips; assistance OFF 5 passed/6 conditional skips; three focused live-capture safety tests passed. This finalization reran the four parser tests (4/4), the debug JVM suite (107/107, zero failures/errors/skips), assembleDebug, and assembleRelease; all final gates passed. Generated debug and release BuildConfig each had assistance OFF, capture OFF, and empty Context Assist API-key fields. The first fresh Gradle attempt lacked this worktree's local AndroidX property, and a first command-line correction was split by PowerShell. A targeted /recover diagnosis identified host invocation, not app code; the final command supplied the property as a separate Gradle argument and passed without changing repository configuration. No new runtime code was introduced after the earlier gates.

The trial is limited by one signer, unknown training relationship, one repetition per phrase, setup/idle false commits, T02 event-timing uncertainty, T05 deliberate retry, and the inability to infer the exact cause of a wrong or extra event from Top-5 alone. We did not measure natural physical timing precisely. Do not convert these counts into a cross-signer end-to-end accuracy claim. The normal UI displayed the raw sentences and no hypothetical phrase was promoted. Existing Hear code and safety tests speak the raw sentence; this physical run did not independently transcribe the phone audio. We did not tune recognition or the matcher while collecting.

The original installed APK was backed up before the private diagnostic install. After the signer stopped, the owned T06 capture was terminated, the original APK was restored with non-streaming install, and the installed APK SHA-256 matched the backup exactly: 82c5298f218efb3c5184b3923672787f46843267e913aeb7c00d517a2829c5d5. No instrumentation companion package was listed. APK byte restoration is verified; restoration of private app data is not claimed.

## Evidence-based conclusion

In these five first-round attempts, the initial wrong recognitions most often involved the intended class being absent from the associated event's Top-5. Additional events also affected the raw sentence, including a duplicate that SentenceBuilder collapsed and an uncertain long run in T02. The one Top-5-supported intended concept appeared only after the signer deliberately retried GOOD. Thus this small sample does **not** justify implementing a phrase decoder or changing insertion handling now. It points to visual recognition/generalization as the more immediate limit for the observed first-pass substitutions, while sequence noise remains a separate observed concern. More controlled repetitions or recognizer-focused diagnostics would be needed before assigning a dominant system-level cause. Stage 3 stops here for review.
