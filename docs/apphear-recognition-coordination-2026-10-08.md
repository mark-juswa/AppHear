# AppHear WORD / Fingerspell / Context Assist coordination

Date: 2026-10-08. Engineering decision: retain the flag-controlled coordinator on the private Xiaomi.
No recognition-quality improvement or production promotion is claimed.

## Inspected state and decision

The authoritative app remains the October5 worktree:
`C:/Users/Gigabyte/.codex/worktrees/fingerspell-continuous-oct05/5. Apphear3`,
branch `codex/fingerspell-continuous-oct05`, base
`b48594c4942d9e9ac0d94ff96396e80b9f049c0a`.
Research/evidence root: `F:/ASL DATASET/5. Apphear3`. Earlier uncommitted work was preserved.

Actual code inspected: RecognitionActivity, Candidate01FrameAnalyzer, PhoneProductionSession,
FingerspellRuntime, ContinuousFingerspell, HeldLetterPolicy, RecognitionModeController,
RecognitionModeSettings, ConversationPhraseAssist/context/presentation/provider/matcher, existing
Text-to-ASL hearing submission, application lifecycle, camera binding, Settings and regression tests.
The architecture plan was written before implementation; the supervisor chose automatic switching
before signing starts. Plan: `docs/apphear-recognition-coordination-plan-2026-10-08.md`.

### Existing components

| Component | Actual input / output | Existing connection used |
|---|---|---|
| Perception | CameraX upright unmirrored RGB -> Candidate01 raw-v1 | Existing ownsObservation seam before WORD consumption |
| WORD | raw-v1 -> frozen S2-R2/event/window/Recognition V2/236 model -> SentenceBuilder | Existing readiness, sentence read and temporal reset APIs only |
| Fingerspell | genuine raw windows -> fresh Adapter.v1 405 -> frozen V2.1 -> singleton CTC -> held-letter draft | Existing exclusive owner, select/clear/confirm/retry/pause APIs |
| Context Assist | actual typed/speech hearing turns -> async supported reply hypotheses -> WORD evidence advisory | Actual hearing turn/text used for routing; existing provider/matcher unchanged |

The continuous app path is the approved automatic held-letter path, not fluent phrase CTC.
It currently uses exact singleton decoding; old greedy/beam/manual inference are preserved.
Context probabilities and recognizer scores are not comparable calibrated mode probabilities.
No score competition or guessed-name substitution was added.

## Implemented behavior

1. A fresh supported English name/place/spell prompt can automatically enter FINGERSPELL when
   WORD is idle and the current observation has no accepted usable hand, before response activity.
2. A prompt arriving during a response never interrupts it. Unknown/compound/negated topics remain
   WORD; Spell is an explicit override. WORD overrides consume the context turn, preventing bounce.
3. The existing owner routes raw observations to only one recognizer. Both models may be loaded;
   their recognition execution does not run simultaneously. No new detector or perception changes.
4. A small coordination row shows active mode/reason, manual WORD/Spell and Finish spelling.
   CURRENT SIGN and RECOGNIZED retain their separate functions. Start/Done remain absent.
5. Finish spelling reviews actual buffered letters. Confirmation checks the still-current draft,
   records those exact letters in context, preserves repetitions, and returns to WORD. Empty/stale
   confirmation is refused. A newer question cannot claim an older spelling.
6. WORD sentence storage stays separate and survives switching. Last confirmed spelling stays in
   the coordination row. WORD Hear, TTS and evidence-based advisory behavior remain authoritative.
7. Missing hands do not imply spelling completion; they already re-arm repeated letters. No new
   duration/absence threshold or automatic text commit was invented. Settings preference is unchanged
   by a temporary context switch. Existing lifecycle pause plus new generation guards cancel stale work.

The intent matcher is a deterministic asset of six full-match English patterns. It supports
“What is your name?”, “What's your last name?”, “What city are you from?”, school/place name
questions and explicit “Please spell…” forms. It does not add an LLM call or infer arbitrary intent.
Routing remains available before/without a successful provider response because it reads actual text.
Provider failures cannot generate letters or silently replace recognition.

## Exact application files

Only three existing application files changed in this task:

- `android/app/src/main/java/com/example/apphear/RecognitionActivity.kt`: flag-gated bridge, existing
  ownership/lifecycle/context/render/Hear seams, restore WORD display from its own sentence.
- `android/app/src/main/java/com/example/apphear/contextassist/ConversationPhraseAssist.kt`: two
  additive methods, `activeHearingTurnId` and `recordConfirmedSpelling`; old methods untouched.
- `android/app/build.gradle.kts`: debug opt-in coordination flag; release/default disabled.

Seven new application files:

- `android/app/src/main/java/com/example/apphear/coordination/RecognitionCoordinator.kt`
- `android/app/src/main/java/com/example/apphear/coordination/RecognitionCoordinationBridge.kt`
- `android/app/src/main/assets/recognition_coordination_policy.json`
- `android/app/src/main/res/values/recognition_coordination.xml` (new IDs only)
- `android/app/src/test/java/com/example/apphear/coordination/RecognitionCoordinatorTest.kt`
- `android/app/src/androidTest/java/com/example/apphear/coordination/RecognitionCoordinationInstrumentedTest.kt`
- `android/app/src/androidTest/java/com/example/apphear/coordination/ContextAssistCameraReadyRegression.kt`

Research additions/changes: the plan/report/operational contract, append-only feature registry/progress/
memory entries, `tools/fingerspelling/recognition_coordination_port.py`, the build wrapper's new
`-Coordination` switch, and `artifacts/recognition_coordination_01/` source/evidence snapshots.
The one-time porter refuses reapplication when its before inventory exists; do not rerun it.

## Validation and limitations

| Gate | Result / evidence |
|---|---|
| Private host unit tests | 180 passed, zero skips/failures; includes nine new policy tests |
| Default flag-off host unit tests/build | 180 passed, zero skips/failures; flags off verified |
| Private Xiaomi coordination | 1 passed: name -> F, synthetic BELLA confirmation -> WORD/context, HELLO preserved, override/stale/new-turn guards |
| Private existing regressions | 5 passed: continuous ownership/buffer (2), diagnostic isolation (1), camera input/switch (2); two provider-specific tests correctly skipped |
| Default Xiaomi disabled Context/Hear | 1 passed; raw WORD display/Hear unchanged |
| Fake-provider group | 3 passed, 2 initial older synthetic UI replay failures; retained log, not reported as a passing suite |
| Independent existing fake Hear replay | 1 passed in a fresh process |
| Readiness-aware fake WORD/Context replays | 2 passed: raw Hear/advisory and stop/closure/storage behavior |
| Protected inventory | 662 existing files: 659 unchanged, exactly three intended integration files changed; all 281 existing source/test assets unchanged |
| Source porter | Ruff + Python compilation passed |

13 passing on-device checks were recorded across these configurations (including repeated checks).
These are engineering/synthetic-input checks, not cross-signer recognition accuracy.

The first private test timed out because the phone was asleep and CameraX delivered no frames.
It passed after the supervisor unlocked the phone; the initial log remains preserved.

Two older fake-provider UI replays immediately injected synthetic FrameResult data after activity
creation. The camera probe measured initial `cameraGeneration=1`, `processingCameraGeneration=0`,
zero input frames; the existing stale-frame guard rejects such a replay before the new coordination
hook executes. Waiting for genuine CameraX startup and stopping the analyzer before synthetic
replay passes the equivalent WORD advisory/raw Hear/stop assertions. Production stale protection
and the old tests were not weakened or changed. The old unready replay harness remains a testing
limitation; its failure logs and the readiness-aware tests are retained transparently.

Human UI end-to-end check was requested after restoring the private build; no signing benchmark
was requested. See `human_smoke.json` if the supervisor supplied the result during this session.
No fluent-spelling/all-letter accuracy or context-classifier accuracy is claimed.

## Frozen identities and rollback

Selected V2.1 epoch034 checkpoint identity remains
`3f92287c5ee82b2e0de1d396c4d27fe3b0efaed8af23b79b878740a56f1af638`.
Packaged FP32 model SHA-256:
`e78de274b967acf0ea9d30bd3f3ac4422a1ef8ebdd95c8676b57dd05fed75c4c`.
Packaged model manifest SHA-256:
`8edc998728fa41883abacbc8382359d6d61621bc259da78ca7c2ab6f8126d01e`.
Coordination asset SHA-256:
`7482d5471d92e72f74af1a042e1e243bb952229d3524cdb68792c3b1b4a1f5c1`.
Installed/restored private coordination APK SHA-256:
`6f56dc583148a3725ddc7ed973b633c34528eac2f71d363a9bfb04d96a4b3591`.

The APK stays local/private; do not distribute it. Existing rollback APKs/checkpoints remain
untouched. Disable `recognitionCoordination` to restore earlier manual Settings-based behavior.
The no-context/default/release paths remain off. No install/uninstall cleared user data.

Exact rebuild (private local use only):

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\tools\fingerspelling\android_continuous_build.ps1 -Configuration private -RearCamera -Coordination
```

Saved validated private APK:
`artifacts/recognition_coordination_01/private_apks/app-debug-private-coordination.apk`.
The active checkout's latest build output may be the fake-provider test variant; use the saved
private artifact or the exact command above, not an arbitrary last Gradle output.

## Review / conclusion

Plan alignment: PASS. System boundaries: PASS. Experimental engineering readiness: PASS.
No critical recognition/ownership/protected-component issue identified. Limitations: bounded
English routing, explicit completion, existing recognition errors and old cold-camera test setup.
Latency/accuracy improvement was not measured or claimed; recognition contracts are unchanged.

Retain this opt-in coordination layer for the approved local development flow. No retraining,
dataset access, TEST access, model/decoder tuning, geometry change or recognizer redesign occurred.
This makes the components communicate and preserves manual recovery; it cannot turn an incorrect
letter prediction into an accurate name. Future work must follow the supervisor's next request.

## Continuation — actual typed-context / Reply integration

The supervisor restated the essential rule: context chooses an appropriate recognition owner,
and must not replace or interfere with either recognizer. Current source and October5 HEAD were
rechecked. The existing coordinator already implements that boundary; no production adjustment
was needed in this continuation.

Added exactly one test:
`android/app/src/androidTest/java/com/example/apphear/coordination/RecognitionContextUiFlowInstrumentedTest.kt`.
It submits “What is your name?” through the actual Text-to-ASL input/Sign It controls and opens
RecognitionActivity through the existing Reply button. It uses the fake provider (no remote call),
then supplies controlled idle/no-hand evidence to isolate pre-signing routing from physical hand
detection. On Xiaomi: FINGERSPELL became the exclusive owner, context created no spelling text,
empty Finish stayed disabled, manual WORD overrode the context and did not bounce back, and the
persisted Settings preference stayed WORD. One test passed in 13.213 seconds.

This extends the earlier test which seeded hearing state directly; it does not measure automatic
routing under arbitrary physical framing or recognition accuracy. Actual UI submission/navigation
was exercised, not a replacement context implementation. The bounded English intent rules remain
unchanged; unsupported context requires manual override.

669 existing app source/config/asset files were byte-identical across this continuation; only the
new test file was added. No production source, model, WORD/FINGERSPELL pipeline, decoder, feature,
provider or policy changed. The original validated private APK and companion were restored on the
phone with app data preserved; APK SHA remains `6f56dc583148a3725ddc7ed973b633c34528eac2f71d363a9bfb04d96a4b3591`.
Earlier validation reports/logs remain intact. The historical validation helper recognizes this
explicit test-only extension; its original stage results are not relabelled.

New evidence: `artifacts/recognition_coordination_01/ui_flow_01/validation.json`,
`device_result.json`, `device.log`, `build.log`, `before.json`, test source and scoped validator.
The validator passes Ruff/mypy. Initial implementation host/device evidence remains applicable
because all existing code and assets were verified unchanged.
