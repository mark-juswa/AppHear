> **2026-10-30 sentence-builder continuation:** The latest approved behavior makes the validated
> AI sentence primary in RECOGNIZED, adds a Signed line/removal, waits before auto-say and passes recent
> exchanges to prompt v3. This supersedes older optional-chip wording below. Implementation is locally
> built; external evaluation and device acceptance remain pending. See
> [continuation report](sentence-builder-v3-continuation-2026-10-30.md).

# One-screen conversation (conversationFlowV2): implementation plan

Status: steps 1-8 built (2026-10-29); step 9 (phone checks) pending. See conversation-flow-v2-handoff.md.
Worktree: `I:/AppHear-Conversation-Claude/worktree`, branch `claude/conversation-flow-ux`.
Baseline: `557f0313` = pushed `ae7afc98` (claude/text-to-asl-integration-c98d88) plus the
previously uncommitted placement-guide work, copied byte-for-byte.
Codex's experiment (`codex/unified-conversation-ux-v3`, `3133b5da`) is a reference only. Its
worktree is not touched.

## 1. Overview

The problem: one conversation turn currently crosses three screens and a system dialog.
Recognition screen -> SPEAK -> Google speech dialog -> Text-to-ASL screen (avatar) -> Reply ->
back to recognition.

The goal: the whole conversation happens on the recognition screen. The camera stays live,
the hearing person's reply appears as large text in the existing bottom sheet, and the avatar
plays only when the signer asks for it.

Build-plan placement: presentation after S8. It is part of feature 21 (Recognition UI) and of
the redesign plan's "data/backend/conversation features" phase. It touches no S0-S8
computation, feature contract, model, dataset or evaluation code.

## 2. Terms

| Term | Meaning in this plan |
|---|---|
| Signed words | The exact S8 sentence (or confirmed FINGERSPELL text) shown in RECOGNIZED. Never rewritten. |
| Suggested sentence | The existing sentence-assist output (Gemini, Groq backup). Optional. Only used if the signer taps it. |
| Chosen message | Whichever of the two the signer has selected. Signed words by default. Changing the signed words resets the choice. |
| Reply | What the hearing person said (in-app listening) or typed. Shown as text. Never auto-signed. |
| Turn | One chosen message said aloud, plus the reply that follows. |
| Done | Offline gates pass AND the device checks in section 7 pass AND the user accepts the screenshots. A build alone is not done. |

## 3. Decisions (confirmed)

1. Phone setup: propped up facing the Deaf signer (front camera). The signer reads the screen,
   so replies are large. A back-camera, hearing-person-held layout is out of scope.
2. Everything stays on RecognitionActivity. The Text-to-ASL screen and the old flow stay
   available unchanged when the flag is off.
3. Listening happens inside the app with Android `SpeechRecognizer` (same Google engine, no
   dialog), with live partial text. Offline is preferred where the phone supports it. If
   `SpeechRecognizer` is unavailable, it falls back to today's `RecognizerIntent` dialog.
4. The suggested sentence stays, as a tappable second line under the signed words in the
   RECOGNIZED card. Signed words are the default. No Use/Reject card. Editing is a smaller
   action in the expanded sheet. The source is the existing sentence-assist code; if
   `sentenceAssist=off`, there is no second line.
5. Wording: **SAY IT** (volume icon) reads the chosen message aloud and then starts listening
   automatically. **LISTENING** is the sheet state while the reply is captured. **LISTEN**
   (mic icon) starts listening manually when the hearing person speaks first. **SIGN IT**
   plays the reply on the avatar. The old SPEAK keeps its current meaning outside this mode.
6. Recognition keeps running while the avatar plays. No runtime change. Frame rate is measured
   during playback (section 7). If it drops, pausing becomes a separate flagged change.
7. History: up to six recent exchanges as chat bubbles in the expanded sheet. Held in memory
   only and cleared when the screen closes.
8. The test build installs as a separate Lab app (own application ID and name) beside the
   existing AppHear. The installed app is never replaced.
9. Only established AppHear components are used (section 5). No new palette, typeface, button
   shape or framework.
10. Context Assist keeps working: every reply goes through the existing
    `ConversationPhraseAssist.recordHearingMessage(...)` (source SPEECH or TYPED_TEXT), so
    predicted replies and the automatic switch to FINGERSPELL behave as they do now.
11. FINGERSPELL keeps its existing confirm-spelling step. SAY IT goes through the existing
    `coordination.hear()` / confirm dialog, then continues the turn after speech finishes.
12. When the new flag is on, the older D2 auto-reply countdown and D3 auto-listen are forced
    off (both depend on switching screens). conversationFlowV1 screen reuse is unaffected.

## 4. What each sheet state shows

All states use the existing translucent floating sheet (`bottomSheet`), its drag handle and
its expand/collapse behaviour. The pill on the right of the overline is the existing
`speakButton` (`btn_start_bg`, Inter Black, cream text), relabelled per state.

| State | Overline (`#8C775B`, spaced caps) | Main text | Pill | Expanded sheet adds |
|---|---|---|---|---|
| Ready, nothing signed | CURRENT SIGN | `...` (teal, as now) | LISTEN (mic) | History, TYPE REPLY |
| Signing / message ready | CURRENT SIGN | current gloss (as now); RECOGNIZED card shows signed words + suggestion line | SAY IT (volume) | Confidence bar, EDIT, CLEAR, history |
| Saying it (TTS) | SAYING | chosen message | STOP (`btn_stop_bg`) | - |
| Listening | LISTENING | live partial reply, large; `soundwaves` animates | STOP | TYPE INSTEAD |
| Reply shown | THEIR REPLY | the reply, large dark Inter Black, wraps | SIGN IT (play) | LISTEN AGAIN, TYPE REPLY, history |
| Avatar playing | SIGNING | the reply | REPLAY (tan circle, as on Text-to-ASL) | CLOSE |
| Couldn't hear | LISTENING | "Didn't catch that" | LISTEN | TYPE REPLY |

- Reply shown -> signing again: as soon as the recognizer commits a new word, the reply moves
  into history and the sheet returns to CURRENT SIGN. No "continue" button.
- The avatar stage covers the camera area above the sheet. It uses the Text-to-ASL stage look
  (dark teal background, white circle close button) and hides the placement guide and its
  warning while visible. It returns to the camera on genuine playback completion only.
- Context Assist's predicted-reply chips and the WORD/FINGERSPELL mode pill keep their current
  places and behaviour.
- Secondary actions are tan-outlined pills (`bg_chip_inactive`, brown spaced caps), stacked
  full-width like CLEAR.
- New user-visible copy goes in a `conversation_flow_v2_strings.xml` file. No developer or
  diagnostic text is shown to users.

## 5. Reuse map

| Need | Reused from | Notes |
|---|---|---|
| Sheet, handle, overline, gloss, pills | `activity_recognition.xml` bottomSheet, `btn_start_bg`, `btn_stop_bg`, `bg_chip_inactive` | Extra views added hidden; flag off = identical layout behaviour |
| Icons | `ic_volume`, `ic_mic`, `play`, `ic_replay`, `soundwaves.png` | Already in the project |
| Read aloud + completion | `AppHearSpeechPlayer.speak(text, onDone)` | Existing completion callback; no new TTS owner |
| Listening fallback | `SpeechInputHelper` + existing `replySpeechLauncher` | Used only when in-app listening is unavailable |
| Suggested sentence | `SentenceAssistShadow.displayState(...)` | Unchanged; read only |
| Context Assist | `ConversationPhraseAssist.recordHearingMessage(...)` | Unchanged; called from the new reply path |
| Avatar | Codex's `InlineConversationAvatar.kt` (from `3133b5da`, read with `git show`), restyled; underlying `TextToAslPlaybackController`, catalog, planners and GLB assets unchanged | Codex's controllers, review objects and panel layout are not reused |
| History bubbles | AppHear2 `item_chat_bubble_signing/response.xml` | Copied as `conversation_bubble_*.xml`, switched to Inter and existing colour tokens |
| Timeline measurement | `ConversationTimeline` + `tools/conversation_flow/` | New events: say_it, listen_start, reply_ready, sign_it, avatar_done |

## 6. Code layout

- `conversation/flow2/ConversationFlowState.kt`: the pure state machine (no Android types).
  States and transitions from section 4. Rejects stale TTS/listening/avatar callbacks with a
  ticket number, as the existing auto-listen code does.
- `conversation/flow2/InAppSpeechListener.kt`: `SpeechRecognizer` wrapper (partial results,
  end-of-speech, errors, offline preference, fallback signal). Created and destroyed with the
  activity.
- `conversation/flow2/ConversationSheetBinder.kt`: renders a state into the existing sheet views.
- `conversation/flow2/ConversationHistory.kt` + bubble layouts: up to six exchanges, in memory.
- `conversation/flow2/ReplyAvatarStage.kt`: the adapted inline avatar owner.
- `RecognitionActivity.kt`: narrow hooks only (speakButton click, hear completion, word
  commit, lifecycle, back press), each a no-op with the flag off.
- `build.gradle.kts`: `conversationFlowV2` property (debug only, default off, release
  hard-off); `conversationLab` property adds an application ID suffix and the app name
  "AppHear Conversation".
- `src/debug/AndroidManifest.xml`: `RECORD_AUDIO` permission (release manifest unchanged).
  Asked the first time LISTEN or SAY IT needs it. If denied, the fallback dialog is used.

## 7. Contract, metric and gates

Contract/parity impact: none. No `schema_version` change, no S4 or F change, no skew test
needed, no threshold or model change. A protected-path check confirms that only the files in
section 6, the layout, strings/resources, gradle and tests differ from `557f0313`.

Offline gates (before any phone install):
1. Baseline `557f0313` builds and all existing unit tests pass (including PlacementGuardTest),
   with all build output on I:.
2. New host tests: full turn sequence, repeated turns, STOP in each state, stale callbacks,
   no speech / error / permission denied -> fallback, typed reply, suggested-sentence choice
   reset when signed words change, history cap of six, flag off = no new behaviour.
3. Flag-on and flag-off debug builds succeed; release BuildConfig has every conversation flag
   false.

Device checks (Xiaomi, Lab app):
1. Screenshots of every state in section 4, compared against the established recognition and
   Text-to-ASL screens. The user reviews them.
2. Conversation-timeline dialogues D1-D3 from `tools/conversation_flow/README.md`, three runs
   each, compared with the existing Phase 1 build. Measures: screen switches per turn (target
   0), signer taps per turn (target 1: SAY IT, plus SIGN IT only if wanted), time from end of
   reply speech to camera ready, memory over the run.
3. Recognition frame rate p50/p95 while idle, while listening and while the avatar plays, in
   the same build. Proposed trigger for the "pause during playback" follow-up: playback p50
   more than 15% below idle p50. The user decides the final number.
4. Interruptions: background/return during listening and playback, permission denied, no
   network (offline speech availability), phone call.

No recognition, sentence or translation accuracy claim is made. Two-person use with a Deaf
signer remains a separate acceptance step.

## 8. Build steps (each verified before the next)

1. Build the baseline on I: and run its unit tests. Nothing changed yet.
2. Gradle flags, Lab app ID/name, debug mic permission. Flag-off build behaves exactly as the
   baseline.
3. `ConversationFlowState` + host tests.
4. `InAppSpeechListener` with fallback + host tests (fake recognizer).
5. Sheet states and wiring: SAY IT -> TTS -> listening -> reply -> Context Assist; LISTEN;
   TYPE REPLY; STOP. Screenshots of each state.
6. Suggested-sentence line in RECOGNIZED and the chosen-message rule.
7. Avatar stage (SIGN IT, REPLAY, CLOSE, auto-return), placement guide hidden while it shows.
8. History bubbles in the expanded sheet.
9. Device checks from section 7, `/review`, progress-tracker entry, Lab APK on I:.

Nothing is merged or pushed without the user asking.

## 9. Open decisions

- The frame-rate trigger number in section 7 (15% is a proposal).
- Whether the Lab app should later become the default experience; that needs Deaf-user and
  designer acceptance first.

## 10. Rollback

Flag off restores the current behaviour on the same build. The branch is separate; `557f0313`
and `ae7afc98` stay as they are, and the Lab app can be uninstalled without affecting
AppHear.
