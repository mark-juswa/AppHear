# Guided Conversation Demo (scripted mode): concept and implementation plan

Status: planning only (2026-11-03). No code written. Builds on the one-screen conversation
(`conversationFlowV2`) in this worktree (`I:/AppHear-Conversation-Claude/worktree`, branch
`claude/conversation-flow-ux`).

## 1. What this feature is, and is not

**Is:** a script-driven demonstration of the AppHear conversation workflow on the real
Recognition screen. A prepared scenario decides every signed message, its English sentence, and the order
of the dialogue. The camera, the bottom sheet, SAY IT / auto-say, listening, the avatar, history and the
AI Helper's suggestion chips all behave as in a real conversation, so the audience sees the intended
end-to-end experience.

**Is not:** sign recognition. The recognizer's predictions never choose, change or reorder what the demo
shows. The demo makes no accuracy claim, shows no confidence score, and is never mixed with measured
results. Normal recognition stays exactly as it is and is one switch away.

Why it is useful: the conversation design (turn-taking, sentence building, speech output, replies, avatar,
context help) can be shown reliably even though the recognizer is still research-grade (cross-signer
accuracy is measured separately and honestly in the evaluation chapter).

## 2. What exists today (inspected)

| Part | Where | Use in the demo |
|---|---|---|
| Recognition screen + sheet (CURRENT SIGN, RECOGNIZED card, SAY IT, LISTENING, THEIR REPLY, SIGN IT, RECENT) | `RecognitionActivity`, `conversation/flow2/ConversationFlowController`, `ConversationSheetBinder` | Reused unchanged as the demo's stage |
| Signed words enter the conversation at one point | `ConversationFlowController.signedWordsChanged(words)` (called from `RecognitionActivity` lines ~351/386/1085/1380) | The demo feeds scripted words here and ignores real ones while active |
| Sentence shown in RECOGNIZED | `ConversationFlowController.suggestionFor(words, sentence, plain, building)` | The demo passes the scripted sentence (no AI call) |
| "Hands are up" signal from raw hand landmarks, independent of predictions | `RecognitionActivity.signerHandsUp()` -> `conversationFlow.signingActivity()` (camera thread, before any recognition hold) | Paces the demo: signing started / finished |
| Auto-say timing (3.5 s still, 3 s countdown) | `conversation/flow2/AutoSay.kt`, `assets/conversation/auto_say_policy_v1.json` | Reused to trigger "message ready" after the signer stops |
| Detection hold (WORD inference skips frames, hand signal still computed) | `ownsObservation` hook / `conversationHolds()` | Recognizer can rest during the demo; pacing still works |
| AI Helper = Context Assist (predicted reply chips, auto FINGERSPELL switch) and sentence assist (Gemini/Groq) | `contextassist/ConversationPhraseAssist`, `sentenceassist/` | Chips filled from the script (deterministic); no LLM calls in demo |
| Speech out | `AppHearSpeechPlayer` (ElevenLabs when configured, Android TTS fallback) | Android TTS in demo (offline, predictable) |
| Listening | `InAppSpeechListener` (offline-first) | Optional: end of the hearing person's speech advances the script |
| Avatar | `ReplyAvatarStage` + 107 GLB clips, incl. phrases `nice-to-meet-you`, `you-live-where`, `you-go-to-school`, `you-work-where`, `how-are-you`, `thank-you`, fingerspelling | Signs the hearing person's scripted lines, deterministically |
| Recognizer vocabulary | `assets/vocab.json`, 236 ASL glosses (HELLO, LIVE2, SCHOOL, STUDENT, WORK, EAT1, WANT2, WHERE, ...; no NAME or AGE sign) | Glosses in the script are written with these where possible, so a demo can also be rehearsed in real mode |

## 3. Script library

### 3.1 Dynamic values (one demo profile, reused by every scenario)

Entered in the script details window (Settings, or EDIT DETAILS on the scenarios card); every scenario
reads them. Nothing is built in: an empty value shows as `[name]`, `[city]`, ... so it is easy to spot.

Keys: `name`, `age`, `city`, `province`, `school`, `school_short`, `course`, `year_level`, `occupation`,
`destination`, `hearing_name` (the other person). Fingerspelled values in a gloss use `FS:{key}`.

Rules: values are plain text, length-limited, and only inserted where a scenario uses `{key}`. A name or
place appearing in the demo is **inserted from the profile, not detected**; the documentation says so.

### 3.2 Scenario format (asset file, no code change to add one)

`assets/guided_demo/scenarios_v1.json`, one entry per scenario:

```json
{
  "id": "introductions",
  "title": "Introducing yourself",
  "category": "Greetings and introductions",
  "uses": ["name", "city", "province", "year_level"],
  "steps": [
    { "who": "hearing", "text": "Hello! What is your name?", "fil": "Hello! Ano ang pangalan mo?",
      "avatar": "hello what your name" },
    { "who": "signer", "text": "My name is {name}.", "gloss": "MY NAME FS:{name}",
      "replies": ["Nice to meet you, {name}!", "How do you spell that?"] },
    { "who": "hearing", "text": "Nice to meet you, {name}. Where do you live?", "avatar": "nice-to-meet-you you-live-where" },
    { "who": "signer", "text": "I live in {city}, {province}.", "gloss": "ME LIVE2 FS:{city}" }
  ]
}
```

- `hearing` steps: what the hearing person says; `avatar` is an optional simpler wording the avatar can
  sign fully (checked by a test against the clip catalog). `fil` is an optional Filipino/Taglish variant.
- `signer` steps: `text` is the English sentence shown and spoken; `gloss` is what the signer is cued to
  sign (draft ASL-style gloss, see section 7); `replies` become the AI Helper's suggestion chips.
- Placeholders are `{key}`; `FS:` marks fingerspelling. A missing value falls back to the default.

### 3.3 Scenarios (Philippine context)

Draft glosses are ASL-style and **must be checked by a qualified signer** (section 7). Hearing lines are
written as natural Philippine English; Filipino variants can be added per line.

**A. Greetings and introductions**
1. *Introducing yourself* -
   H: "Hello! What is your name?" / S: "My name is {name}." (`MY NAME FS:{name}`) /
   H: "Nice to meet you, {name}. Where do you live?" / S: "I live in {city}, {province}." (`ME LIVE2 FS:{city}`) /
   H: "Are you a student?" / S: "Yes, I am a {year_level} college student." (`YES ME STUDENT`) /
   H: "Nice talking to you!" / S: "Nice talking to you too!" (`NICE TALK1 YOU`)
2. *Meeting a classmate's friend* -
   H: "Hi! I'm {hearing_name}. How are you?" / S: "I'm good, thank you. And you?" (`GOOD THANK-YOU YOU`) /
   H: "I'm fine. How old are you?" / S: "I am {age} years old." (`ME AGE #{age}`) /
   H: "Where are you from originally?" / S: "I am from {city}." (`ME FROM FS:{city}`)

**B. School and work**
3. *Talking about school* -
   H: "Where do you study?" / S: "I study at {school}." (`ME STUDENT FS:{school_short}`) /
   H: "What course are you taking?" / S: "I am taking {course}." (`ME LEARN FS:IT`) /
   H: "Is it hard?" / S: "Sometimes, but I like it." (`SOMETIMES HARD BUT ME LIKE`) /
   H: "Good luck with your studies!" / S: "Thank you very much!"
4. *First day at work* (occupation) -
   H: "Welcome! Are you the new staff member?" / S: "Yes, I start today." (`YES ME START TODAY`) /
   H: "What did you do before?" / S: "I worked as a {occupation}." / H: "Do you need anything?" /
   S: "Please write instructions for me. Thank you." (`PLEASE WRITE FOR ME THANK-YOU`)

**C. Getting around (directions, transport, commuting)**
5. *Asking for directions* -
   S: "Excuse me, where is the {destination}?" (`EXCUSE-ME WHERE FS:...`) /
   H: "Go straight, then turn right at the church." (avatar: "go ... turn right") /
   S: "Is it far?" (`FAR?`) / H: "No, about five minutes walking." / S: "Thank you!"
6. *Riding a jeepney / tricycle* -
   S: "Does this jeepney go to {destination}?" / H: "Yes, sit down." / S: "How much is the fare?" /
   H: "Fifteen pesos." / S: "Please tell me when we are there." (`PLEASE TELL ME WHEN ARRIVE`) /
   H: "Okay, I will tell you."
7. *At the bus terminal* -
   S: "One ticket to Naga, please." (`ONE TICKET FS:NAGA PLEASE`) / H: "The bus leaves at two o'clock." /
   S: "Where do I wait?" / H: "Over there, at gate three." / S: "Thank you."

**D. Shopping and food**
8. *Sari-sari store / market* -
   S: "How much is this?" (`THIS HOW-MUCH`) / H: "Twenty pesos." / S: "I will buy two." /
   H: "Forty pesos, please." / S: "Here is fifty." / H: "Here is your ten pesos change."
9. *Ordering at a carinderia / fast food* -
   H: "Good afternoon! What would you like?" / S: "One chicken meal and water, please." /
   H: "For here or take out?" / S: "For here." / H: "That's one hundred twenty pesos." / S: "Thank you."
10. *Asking about a product* - S: "Do you have this in a bigger size?" / H: "Yes, wait a moment." /
    S: "Can I try it?" / H: "The fitting room is over there."

**E. Help, health and services**
11. *Asking for assistance* - S: "Excuse me, can you help me? I am Deaf." (`EXCUSE-ME HELP ME PLEASE ME DEAF`) /
    H: "Of course. What do you need?" / S: "I lost my bag. Can you call the guard?" / H: "Okay, I will call them now." /
    S: "Thank you for your help."
12. *At the clinic (RHU)* - H: "What do you feel?" / S: "I feel sick. My head hurts." (`ME FEEL SICK HEAD HURT`) /
    H: "Since when?" / S: "Since yesterday." / H: "Please sit and wait to be called." / S: "Okay, thank you."
13. *Barangay hall / office* - S: "Good morning. I need a barangay clearance." / H: "Please fill out this form." /
    S: "When can I get it?" / H: "Tomorrow afternoon." / S: "Thank you."

**F. Friends, routines, plans, feelings**
14. *Making plans with a friend* - H: "Are you free tomorrow?" / S: "Yes, in the afternoon." /
    H: "Let's eat lunch together." / S: "Okay! Where should we meet?" / H: "At the plaza, twelve o'clock." / S: "See you tomorrow!"
15. *Daily routine* - H: "What time do you wake up?" / S: "I wake up at six in the morning." /
    H: "What do you do after class?" / S: "I go home and study." / H: "You're busy!" / S: "Yes, very busy."
16. *Feelings and preferences* - H: "How are you today?" / S: "I am tired but happy." (`TODAY ME TIRED BUT HAPPY`) /
    H: "Why?" / S: "We finished our project." / H: "Congratulations!" / S: "Thank you!"

**G. Ending politely** (also used as a closing step in any scenario) -
H: "I have to go now." / S: "Okay. Take care!" / H: "See you next time!" / S: "Bye! See you!" (`BYE SEE YOU`)

For the capstone, start with **1, 3, 6, 9, 11, 14** (introductions, school, transport, food, help, plans):
six scenarios, about 30 signed turns, rehearsable in one session.

## 4. How a scripted conversation runs inside the Recognition screen

Each scenario is a list of steps. The demo keeps a step pointer and drives the existing conversation flow:

1. **Cue (signer step):** the sheet's CURRENT SIGN area shows a small tan cue for the signer:
   "NEXT TO SIGN: MY NAME M-A-R-K". The camera and overlay run as usual.
2. **Signing:** the existing hands-up signal shows "...signing..." (pacing only).
3. **Done:** when the hands are down and still (the auto-say timing) or the presenter presses Next, the
   card shows the scripted sentence under the neutral heading **MESSAGE** (in place of "RECOGNIZED", so the
   screen never claims the signs were recognized). No gloss line, no confidence bar.
4. **Say:** auto-say counts down and speaks the sentence (Android TTS), exactly like a real turn.
5. **Hearing step:** listening starts as usual. When the hearing person finishes speaking (or Next), the
   sheet shows **the scripted line** under THEIR REPLY (the transcript only times the step; a mismatch does
   not change the script). SIGN IT plays the avatar version. The AI Helper chips show the next scripted
   options (section 6).
6. Repeat until the scenario ends; the closing card offers RESTART or ANOTHER SCENARIO.

A scenario can also begin with a hearing step (most do) or a signer step (directions, shopping).

Real recognition during the demo: by default WORD inference is paused (the existing detection hold), so
nothing it says can leak in and the phone stays cool. An optional **"Show live recognizer"** switch runs it
and prints its raw words in a small separate grey line, "Live recognizer (not used): HELLO ...", which is
useful for honesty during a defense Q&A.

## 5. Moving through the script

| Method | Reliability | Discretion | Notes |
|---|---|---|---|
| On-screen NEXT pill | Very high | Visible | Always available as the fallback |
| Volume-down = Next, volume-up = Back | Very high | Discreet (side button) | Works on any phone; no extra hardware |
| Bluetooth presentation clicker (sends Page Down / arrow keys) | Very high | Very discreet | Same key handling; presenter can stand away from the phone |
| Hands-down + stillness (existing auto-say signal) | Medium-high | Natural | Needs good lighting and position; pauses mid-sentence can trigger early, so it is combined with a minimum signing time |
| End of hearing speech (in-app listening) | Medium | Natural | Needs speech recognition (offline pack or internet); fallback is Next |
| Fixed timer | High but rigid | Natural until it is wrong | Not recommended for live use |
| Matching predicted signs to the expected gloss | Low (the reason for this mode) | - | Rejected: it would make progress depend on the model |

**Recommendation:** natural pacing (hands-down for signer steps, end-of-speech for hearing steps) plus
volume-key / clicker / NEXT always available. A "Presenter control only" switch turns natural pacing off
for noisy rooms. Back steps back one turn; Restart resets the scenario.

## 6. The AI Helper in demo mode

- **Suggestion chips (Context Assist):** in demo mode the chips come from the script's `replies` for the
  next hearing step (and the next signer sentence as the "expected" option), not from Gemini. They are the
  same chips users already know, deterministic and offline. Tapping one only shows what the hearing person
  might say; it does not change the step order.
- **Sentence builder (Gemini/Groq):** not used. The script already holds the approved English sentence, so
  an AI rewrite could only add variation or latency, and it would need internet. Clearer and safer to turn
  it off in demo mode.
- **Context history:** the RECENT bubbles fill from the scripted exchange, so the screen looks exactly like
  the real conversation history.

## 7. ASL, FSL and signer review

- AppHear's recognizer vocabulary (236 glosses) and avatar clips are **ASL**. Filipino Sign Language (FSL)
  is the national sign language of the Filipino Deaf (Republic Act 11106, 2018). It is a separate language,
  influenced by ASL but with its own vocabulary (e.g. some letters and many everyday signs differ), sign
  formation and grammar. English word order does not map one-to-one to either language.
- The demo's glosses are **drafts in ASL style** to cue the signer; they are not FSL and not verified.
  Typical points to check: question forms with facial grammar (WH-signs often at the end), topic-comment
  order (`TOMORROW YOU FREE?`), numbers and money, name signs vs fingerspelling, local place-name signs
  (Daet, Naga, Camarines Norte), signs for jeepney, tricycle, barangay, sari-sari store.
- **Consult before the defense:** an FSL-fluent Deaf signer or certified FSL interpreter (e.g. through a
  local SPED center, the Philippine Federation of the Deaf, or a university FSL program) to review each
  scenario's gloss and to decide whether the demo signer uses ASL (matching the app) or FSL (matching the
  audience). Record their review in `docs/` with date and name (with permission).
- Wording in the app and paper: "ASL-based prototype", not "FSL translation".

## 8. Keeping the demo separate from genuine recognition

- **Switch:** Settings -> "Guided conversation demo" (off by default; debug builds only via a `guidedDemo`
  Gradle flag, release hard-off). Turning it off returns the Recognition screen to normal at once.
- **No on-screen demo label** (user decision, 2026-11-03). The screen stays neutral instead: scripted
  sentences appear under MESSAGE, never under RECOGNIZED, and no confidence or accuracy is shown. The
  demo is disclosed by the presenter and in the paper (section 10), not by a banner.
- **No shared outputs:** the demo never writes into the recognizer's sentence store, confidence values,
  evaluation logs or recognition evidence. Timeline events are tagged `mode=demo`; evaluation tools ignore
  them. Models, thresholds, feature contract and V4 experiments are untouched.
- **Code boundary:** one new package `demo/` plus two hooks: `signedWordsChanged` ignores real words while
  the demo is active, and the demo feeds its own words/sentence into the existing flow. Everything else in
  the recognition pipeline is unchanged.

## 9. Recommended implementation

| Piece | What | Notes |
|---|---|---|
| `assets/guided_demo/scenarios_v1.json` | Scenario library (section 3) | Add scenarios without code |
| `demo/DemoScript.kt` | Parse scenarios; `fill(template, profile)` | Pure, unit-tested (placeholders, defaults, `FS:` cue formatting) |
| `demo/GuidedDemo.kt` | Pure state machine: step pointer, phases (CUE, SIGNING, READY, SAYING, HEARING, DONE), next/back/restart | Unit-tested like `ConversationFlow` |
| `demo/GuidedDemoController.kt` | Glue: drives `ConversationFlowController`, volume/clicker keys, scenario card | Only Android part |
| `demo/DemoProfile.kt` | The dynamic values (SharedPreferences) | Settings "Demo details" |
| Recognition screen | Scenario card (reuses the remote-conversation card style), NEXT pill, cue line, MESSAGE heading | Existing views, strings in `guided_demo_strings.xml` |
| Settings | "Guided conversation demo" switch, "Demo details", "Presenter control only", "Show live recognizer" | Same row style as the new remote rows |
| Test: avatar coverage | Every hearing `avatar` text plans to existing clips/fingerspelling | Catches unsupported words before demo day |

Offline: everything runs without internet (local script, Android TTS, local avatar). Listening needs the
phone's offline English speech pack; otherwise Next is used.

### Roadmap

1. **Core (offline, tested):** script format, template filling, state machine, 3 scenarios; unit tests.
2. **Recognition integration:** cue, MESSAGE reveal, auto-say, hearing step, avatar, NEXT/volume keys.
3. **Settings + scenario card:** switch, demo details, scenario picker, restart/back.
4. **Library + checks:** the six capstone scenarios, avatar-coverage test, rehearsal on the phone.
5. **Review:** FSL/ASL signer review of glosses; defense script and paper wording.

## 10. Limitations and how to describe the feature

Disclosure: because the screen carries no demo label, the presenter states before the demo that it is the
scripted Guided Conversation Demo, and recordings or screenshots used in the paper are captioned the same way.

Limitations: the demo shows the intended experience, not recognition ability; inserted names and places are
not recognized; glosses are unverified drafts; natural pacing can trigger early or late; listening may need
an offline speech pack; ASL-based content may not match an FSL-using audience.

Suggested wording for the paper and defense:

> "AppHear includes a Guided Conversation Demo, a scripted mode that demonstrates the intended conversation
> workflow (signed message to text and speech, spoken reply to text and avatar signing, contextual
> suggestions) using predefined scenarios. In this mode the displayed messages come from the scenario script,
> not from the recognition model, and the screen is labelled accordingly. Sign recognition performance is
> reported separately in Chapter X using cross-signer, end-to-end evaluation."

Panel questions to prepare: "Is the model recognizing this?" (No, it is scripted; here is the live
recognizer line / here are the measured results.) "Why ASL, not FSL?" (Section 7.) "What happens with an
unexpected answer?" (The script continues; real recognition mode handles free conversation.)

## 11. Decisions for the user

1. Signer steps: reveal the whole sentence when the signer finishes (recommended), or reveal gloss by gloss
   on each Next?
2. Default pacing: natural + Next (recommended) or presenter only?
3. Which six scenarios for the defense, and should hearing lines be English, Taglish or both?
4. Whether to show the "live recognizer (not used)" line during the defense.

## 12. Implementation (2026-11-03)

Built behind the debug-only `guidedDemo` Gradle flag (needs `conversationFlowV2`; release hard-off) and the
Settings switch "Guided conversation demo" (off by default).

| Part | Where |
|---|---|
| Script model, value filling, fingerspelling cue | `demo/DemoScript.kt` (`DemoValues.fill`, `DemoValues.cue`) |
| Step tracker | `demo/GuidedDemo.kt` (`DemoRun`) |
| 16 scenarios | `assets/guided_demo/scenarios_v1.json` |
| Settings: one row (On/Off pill switches it; tapping the row opens the script details window: values + presenter-only); the scenario card has EDIT DETAILS too | `demo/GuidedDemoSettings.kt`, `demo/GuidedDemoDetailsDialog.kt`, `row_setting_guided_demo.xml`, `SettingsContent.setupGuidedDemo` |
| Recognition screen glue | `demo/GuidedDemoController.kt`; hooks in `ConversationFlowController` and `ConversationSheetBinder`; `RecognitionActivity.dispatchKeyEvent` (volume / clicker keys) |
| Scenarios button + card | `btnGuidedDemo`, `guided_demo_card.xml`, `item_guided_demo_pill.xml` |
| Tests | `GuidedDemoTest` (filling, cues, step order, every shipped scenario well formed) |

Behaviour as built:
- The scenarios button (left, under Back) opens the card: choose a conversation; while it runs the card
  shows STEP n OF m, NEXT, REPEAT THIS STEP, START AGAIN, CHOOSE ANOTHER, BACK TO NORMAL RECOGNITION.
- While a scenario runs, `renderRecognitionSnapshot` hands the live area to the demo and
  `signedWordsChanged`/`suggestionFor`/Context Assist ignore the recognizer, so none of its predicted words
  can appear; only the moment a sign is recognized is used.
- Signer turn (revised twice on 2026-11-03 after user feedback): MESSAGE shows only the scripted
  sentence ("My name is Mark."), which appears once the signer finishes: the recognizer must have noticed
  at least one sign, then signing stops (no "...signing..." and hands down) for about 2 s. Hands near the camera alone (holding or
  typing on the phone) never trigger it, and the first 1.5 s of each turn are ignored. No "next to sign"
  cue is shown. Each appearance is logged as `demo_message` with its reason. The recognizer keeps running only to notice signing; its
  words never reach MESSAGE. CURRENT SIGN steps through the scripted signs as signs are noticed. When the
  hands go down, auto-say says the sentence. No tap is needed; SAY IT, the chip, NEXT or volume-down say
  it at once. The AI Helper suggestion row stays hidden in demo mode (showing the answer early gave it away).
- Hearing turn: if nothing is heard, listening restarts by itself.
- Hearing turn: listening starts by itself; when they finish speaking (or STOP / NEXT / volume-down) the
  scripted line appears as THEIR REPLY. Their actual words are not shown. SIGN IT uses the script's avatar
  wording when it has one.
- Scripted replies are not sent to Context Assist; timeline events carry `mode=demo`.
- No on-screen demo label (user decision); the presenter and the paper disclose it (section 10).

Not done: Taglish line variants, the "live recognizer (not used)" line, avatar-coverage test, signer review.
Proof: 415/415 JVM tests; private Lab APK built and installed on the Xiaomi. Not yet run through on the phone.
