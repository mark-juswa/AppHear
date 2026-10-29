# One-screen conversation (conversationFlowV2): handoff and test checklist

Branch `claude/conversation-flow-ux` in `I:/AppHear-Conversation-Claude/worktree` (git metadata on F:).
Baseline `557f0313` = pushed `ae7afc98` + the previously uncommitted placement guide. Plan:
[conversation-flow-v2-plan.md](conversation-flow-v2-plan.md). Not merged or pushed.

## What it does

The whole conversation stays on the recognition screen. The existing bottom sheet follows the turn:

1. **CURRENT SIGN**: the signer signs. If sentence assist has an accepted sentence, it appears as a chip
   under the signed words in RECOGNIZED; tapping it chooses it (signed words stay the default).
2. **SAY IT** reads the chosen message aloud (through the existing Hear path, so spelling confirmation
   and Context Assist bookkeeping are unchanged), then **LISTENING** starts in the app: no Google dialog,
   words appear live. STOP ends it; TYPE INSTEAD opens a text field.
3. **THEIR REPLY** shows the reply in large text and hands it to Context Assist (predicted replies and the
   automatic switch to fingerspelling work as before). **SIGN IT** plays it on the avatar over the camera
   area; it returns to the camera on genuine completion. REPLAY and CLOSE are available.
4. Signing again moves the reply into **RECENT** history (expanded sheet, up to six exchanges, AppHear2
   chat bubbles; tap a reply bubble to sign it again).

Listening failures show **NOT HEARD**, **COULDN'T LISTEN** or **MICROPHONE OFF** with LISTEN/TYPE REPLY.
If in-app listening is unavailable or the microphone is denied, the old system dialog is used once.

## Build and install

```powershell
& 'I:\AppHear-Conversation-Claude\build-lab.ps1' -Log 'lab.log' -Extra @('-PconversationFlowV2=true','-PconversationLab=true')
```

Installs as **AppHear Conversation** (`com.example.apphear.conversationlab`) beside AppHear:
`adb -s 3ab64582 install -r I:/AppHear-Conversation-Claude/apks/<apk>`. Never uninstall other apps.
The build uses the fake Context Assist provider and no API keys, so the suggested-sentence chip cannot
appear; checking it needs a private build with the sentence-assist keys and `-PsentenceAssist=shadow`.
The phone blocks adb taps: launch with `adb shell am start -n com.example.apphear.conversationlab/com.example.apphear.SplashActivity`
and capture with `bash I:/AppHear-Conversation-Claude/capture-lab.sh <minutes> <folder>` while walking through.

## Test checklist (step 9)

Verified on the phone 2026-10-28 (step 5 build): LISTEN, live listening with STOP/TYPE INSTEAD, a spoken
reply under THEIR REPLY, and the not-heard state.

Still to check on the phone:

- [ ] Sign a few words -> SAY IT -> SAYING -> listening starts by itself -> reply.
- [ ] Fingerspell -> SAY IT -> the existing confirm-spelling dialog -> spoken -> listening.
- [ ] TYPE REPLY / TYPE INSTEAD -> keyboard -> SEND; CANCEL; Back closes the editor.
- [ ] SIGN IT -> avatar over the camera -> returns on completion; REPLAY; CLOSE; a reply with an
      unsupported word stays with "Unsupported: ..." until CLOSE.
- [ ] Expand the sheet: RECENT bubbles, tap a reply bubble to sign it, sheet stays below the top controls.
- [ ] Suggested-sentence chip (private build with keys): offered, chosen, spoken, reset when words change.
- [ ] Context Assist: "What's your name?" as a reply switches to FINGERSPELL as before.
- [ ] Back / home during SAYING, LISTENING and avatar playback: stops, nothing restarts on return.
- [ ] Deny the microphone once: falls back to the system dialog.
- [ ] Timeline dialogues D1-D3 (`tools/conversation_flow/README.md`, `-PconversationTimeline=true`), 3 runs each:
      screen switches per turn (target 0), signer taps per turn, reply-to-camera time, memory.
- [ ] Recognition FPS p50/p95 idle vs listening vs avatar playback (proposed follow-up trigger: playback
      p50 more than 15% below idle).

## Known limits

- If Android TTS has not finished starting, SAY IT can wait in SAYING; STOP recovers.
- The in-app listener's offline-first request retries online once when the offline language is missing.
- No recognition, sentence or translation accuracy claim; two-person use with a Deaf signer is separate.

## Files

`conversation/flow2/`: `ConversationFlow.kt` (pure turn logic), `ConversationFlowController.kt`,
`ConversationSheetBinder.kt`, `InAppSpeechListener.kt`, `AndroidSpeechBackend.kt`, `ReplyAvatarStage.kt`
(adapted from Codex's V3 inline avatar owner). Narrow hooks in `RecognitionActivity.kt` (mixed encoding:
edit byte-safely). Layout additions in `activity_recognition.xml`, copy in `conversation_flow_v2_strings.xml`,
bubbles in `item_conversation_bubble_*.xml`. Tests in `src/test/.../conversation/flow2/`.
