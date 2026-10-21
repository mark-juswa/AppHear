# Conversation-flow measurement (Phase 0 baseline / Phase 1 comparison)

Measures taps, handoff latency, screen instances, recognition frame rate and memory across the
Text-to-ASL <-> Recognition conversation. Logging only: the `conversationTimeline` flag never
changes app behavior, and events carry counts and durations, never transcripts or glosses.

## Build

```powershell
& .\tools\android\build_working_baseline.ps1 -Configuration fake -OriginalWords `
  -Tasks @('assembleDebug','-PconversationTimeline=true')
adb install -r android\app\build\outputs\apk\debug\app-debug.apk
```

`fake` uses the deterministic offline Context Assist provider, so runs do not depend on network
latency or on what the recognizer outputs.

## Protocol

A valid run needs a cool phone: battery at least 40 % and no CPU policy below its maximum
frequency (`--require-cool` enforces both). After every install, open Text-to-ASL once and wait
for the avatar before the first run: the first open after an install re-verifies all animation
files (about 10 s) and is not representative. Force-stop the app before each run.

```powershell
python -m tools.conversation_flow.capture_session runs/<build>-<dialogue>-<n> --adb <path-to-adb> --require-cool
# run the dialogue, then Ctrl+C
python -m tools.conversation_flow.summarize_timeline runs/<build>-<dialogue>-<n>
```

Run each dialogue 3 times. The hearing person speaks; the signer signs the listed protected
glosses (accuracy is not measured, so a wrong word is fine; just continue).

| Dialogue | Hearing (spoken) | Deaf (signed) |
|---|---|---|
| D1 | "How are you?" -> "Where are you going?" -> "Goodbye" | GOOD -> GO HOME |
| D2 | "Hello" -> "Do you like school?" -> "See you tomorrow" | HELLO -> YES |
| D3 | "What is your name?" -> "Nice to meet you" -> "Bye" | (fingerspell or sign NAME) -> HELLO |

Start every run from Home: open Text-to-ASL, use Talk for the first message, then follow the
app's own path (Reply, sign, Hear, Speak). Do not use Back between turns.

## Outputs

`precheck.json` / `postcheck.json` (device, battery, CPU throttling), `timeline.log`,
`meminfo.jsonl`, and `summary.json` / `summary.md` with the metrics defined at the top of
`summarize_timeline.py`.
