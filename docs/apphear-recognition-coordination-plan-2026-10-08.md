# Recognition coordination v1 — inspected architecture and implementation plan

Approved request: integrate the existing WORD, held-letter FINGERSPELL and Context Assist.
Supervisor selected automatic context switching before signing starts. No new recognizer.
Active checkout: October5 `fingerspell-continuous-oct05`, b48594c4942d9e9ac0d94ff96396e80b9f049c0a.

## Actual existing paths

Candidate01FrameAnalyzer builds raw-v1 and calls its existing ownsObservation seam.
Returning true routes the observation exclusively to FingerspellRuntime; false invokes
PhoneProductionSession.consume (S2-R2 -> existing event/materializer -> Recognition V2
-> frozen word model -> SentenceBuilder). Mode transitions already reset temporal state
without clearing stored WORD text and wait for an in-flight fingerspelling invocation.

The current continuous fingerspelling path selects genuine raw windows, derives fresh
Adapter.v1 [T,405], invokes frozen V2.1 epoch034 and exact singleton CTC, then stabilizes
letters into an unconfirmed spelling. It is held-letter recognition, not fluent spelling.
CURRENT SIGN and RECOGNIZED are separate. Hear already requires spelling confirmation.

ConversationPhraseAssist stores hearing text/turn IDs from Text-to-ASL speech or typing,
calls the existing prediction provider asynchronously, validates WORD reply hypotheses,
and displays advisory matches backed by actual WORD evidence. It currently has no routing
intent output, and its provider is constrained to WORD anchors. FINGERSPELL currently
does not feed conversation history. Guessed reply strings cannot identify signed letters.

## Chosen coordinator

A new pure policy alongside both recognition owners reads only actual hearing text and
turn identity. A small asset defines supported English name/place/explicit-spell prompts.
This is intentionally bounded intent routing, not a new LLM request or a semantic accuracy
claim. Arbitrary conversation topics and predicted names cannot switch the recognizer.

Automatic entry occurs once per fresh supported hearing turn, only after WORD has reached
idle, before response activity, and with no accepted usable hand geometry. If the response
has already started, retain WORD and offer a manual Spell switch. Same-turn provider
updates cannot retrigger. Manual override wins for that turn. No model confidence scores
are compared: those scores have different meanings and are not calibrated against each other.

Use the existing camera executor and mode owner to change routing; no parallel recognition.
The coordinator does not call model inference, change features, rewrite recognition, or
inject spelling into the WORD SentenceBuilder. Preserve WORD text and spelling separately.

Show the active mode and reason in a small flag-controlled coordination row. Offer a manual
mode override and Finish spelling. No Start/Stop returns. Finish reviews the actual spelling,
confirms it using the existing buffer API, records only that text in context via a new
stale-turn-checked method, and returns to WORD. Keep the last confirmed spelling visible in
the coordinator row while WORD's recognized text remains its original sentence.

No silence/no-hand timeout commits or exits: hand absence already permits repeated letters
and cannot prove a complete name. A wrong context choice can be overridden immediately;
pending spelling requires confirmation/discard rather than silent loss. New context while
spelling cannot interrupt it or attribute an old reply to the new question. Backgrounding
invalidates queued context and existing lifecycle pause cancels model callbacks.

## Changes and frozen surfaces

New: RecognitionCoordinator, bounded intent config, coordination UI wrapper and tests.
Existing edits: RecognitionActivity orchestration seams; additive
ConversationPhraseAssist active-turn/confirmed-spelling methods; build flag.
No edits to perception, WORD packages, SentenceBuilder, models, adapters, decoders,
FingerspellRuntime/ContinuousFingerspell/HeldLetterPolicy, providers or PhraseMatcher.
Default/release flag false. Private phone-only configuration opts in. Rollback is flag off.

## Gates

Pure host tests: supported/unsupported prompts, stale/duplicate context, no mid-response
auto switch, manual veto, missing input, exactly-once finish and separate output storage.
Device engineering: automatic name prompt -> F owner; blocked late prompt; explicit
override -> WORD; synthesized spelling confirmation -> raw context + return; stale/new
hearing protection; hidden Start/Done; unchanged WORD sentence; no F calls in WORD;
Context Assist existing regression cases; protected source/model/asset inventory hashes.
Use synthetic inputs for routing tests, never call them real-signing accuracy evidence.
No training, dataset access or recognition/decoder tuning.

Recognition accuracy remains experimental; coordination cannot repair a wrong letter.
