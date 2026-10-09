# AppHear fingerspelling — October 4 application integration

## Application and model identities

The application base is `baseline/apphear-text-to-asl-context-assist-ui-2026-10-04`,
`cee71d9f181695847936eb5f3605ea37eab82a95`. Implementation is isolated at
`C:\Users\Gigabyte\.codex\worktrees\fingerspell-oct04-integration\5. Apphear3`.
The original F: research checkout, September 29 branch, unrelated work and the
existing Context Assist worktree are preserved. This supersedes the earlier
September 29 APK for device integration; its evidence remains historical.

This **application baseline** is separate from the selected **model**:
frozen B2 epoch 076 plus quality-gated residual visual epoch 035, frozen
MobileNetV3Small, Adapter v1 `[T,405]`, and the previously evaluated blank penalty
0.5. No B4 model, retraining, new backbone, data expansion or TEST access.
The residual experiment's failed research promotion gate remains recorded;
the user separately authorized this candidate for experimental phone integration.

## Implementation

- Opt-in debug `-Pfingerspell=true`; default and release disabled.
- One CameraX/Candidate01 pipeline. An optional observation owner runs before
  `PhoneProductionSession.consume`; FINGERSPELL withholds WORD consumption in
  Ready, Capturing, Preview and Error states.
- Manual Start/Done defines one sequence. All commands, geometry, quality/dedup,
  crops, appearance and Done inference run serially on the camera worker. Model
  loading is off-main. Original images are borrowed during analysis and disposed
  normally; no second detector or Candidate01 inference.
- Separate preview/confirmed buffer. Use alone confirms; legitimate repeated
  letters remain intact. Retry cancels an attempt; Clear clears spelling. WORD
  sentence storage is preserved and becomes visible again on return to WORD.
- No spelling events enter Context Assist. Its WORD evidence/provider/matcher
  remain unchanged; WORD-only advisory presentation is hidden during spelling
  and restored afterward. The October 4 compact wrapped prediction layout remains.
- Upright unmirrored RGBA geometry/crop semantics reproduce the offline adapter,
  quality filter and appearance-only duplicate suppression. Invalid crops provide
  zero visual weight; the original frozen B2 head remains the fallback.
- Resource guards: 512 observations/60 seconds; exceeded attempts fail visibly
  rather than silently truncating. These are buffer limits, not a model window.
- Session profiling saves diagnostic JSON only, without RGB videos or raw
  landmark training recordings. It reports cadence, crop/encoder cost, finish
  latency, missing crops, duplicate slots and heap snapshots. Dropped-frame counts
  and peak memory are not measured; CameraX still uses KEEP_ONLY_LATEST.

## Verified checks

- 154 JVM tests passed (150 October 4 baseline tests plus four new core/RGBA tests).
- The authorized private Gemini debug configuration also passes 154/154 JVM tests;
  both phone parity and ownership checks pass in that exact installed binary.
  Host/device APK SHA-256:
  `34aae2768e87d8b21cb0f289895d67d33013bc160a2c5c77761284080bb1f832`.
- Debug and Android-test builds passed. Default debug has no fingerspelling model
  assets. Release packaging initially exhausted C:; only generated experiment
  files were relocated to `D:\AppHearBuild\fingerspell_oct04\app_build`, accessed
  through the isolated worktree's `android/app/build` junction. Retry recorded
  separately; no dataset/project work deleted.
  Credential-free release retry passed and its APK contains no fingerspelling
  assets. Private debug and its Android-test APK both build successfully.
- Xiaomi numerical parity: 523 observations; max geometry error 0, crop error 0,
  quality error `5.9604645e-8`, embedding error `1.5974045e-5`, logits error
  `9.298325e-6`. Six causal-prefix cases and six actual frozen-B2 zero-visual
  fallback cases passed. Reference/Android decoded strings agree.
- Connected synthetic session test passed: exclusive spelling ownership, BELLA
  preview, confirmation, Retry/Clear, suppressed stale WORD callback, original
  WORD sentence preserved. Synthetic preview is not live accuracy evidence.
- Focused connected October 4 regressions passed: cached predictions survive
  unsupported two-word evidence; raw Hear remains authoritative; recognition
  screen exit preserves raw text. The historical combined Context Assist test
  order timeout remains a separate known harness limitation.
- Preservation inventory: 640 baseline Android files checked. Only build flags,
  RecognitionActivity integration and Candidate01FrameAnalyzer routing changed.
  PhoneProductionSession, SentenceBuilder, Candidate01 math/models, WORD pipeline,
  Context Assist provider/matcher, resources and prediction layout are unchanged.

## Build and diagnostics

From `F:\ASL DATASET\5. Apphear3`:

```powershell
# Uses the isolated October 4 source; frozen exports remain on F:.
& .\tools\fingerspelling\android_oct04_build.ps1 -Configuration fake
# Private phone-only configuration requires explicit credential-packaging approval.
& .\tools\fingerspelling\android_oct04_build.ps1 -Configuration private
& .\.venv\Scripts\python.exe -m tools.fingerspelling.android_oct04_evidence preservation
& .\.venv\Scripts\python.exe -m tools.fingerspelling.android_oct04_evidence pull
```

Private APKs embed local development service credentials and remain local to
this authorized Xiaomi check. They are not release/distribution artifacts.
The user explicitly approved the private phone-only build after automatic
approval review requested authorization. Credential-free fake/release commands
override global/local API configuration without exposing values in logs.

Evidence: `artifacts/fingerspelling_android_01/oct04/`; APK paths remain under
the isolated worktree's `android/app/build/outputs/apk/` through the junction.
Original baseline rollback APK remains in the existing Context Assist worktree,
`android/build/stable-context-assist-ui-20261004/app-debug-context-assist-ui.apk`.
Do not reset preserved branches to roll back the installed binary.

## Controlled live protocol

On the private experimental build, allow Camera, open Sign-to-Text and leave
WORD running in normal framing for about 30 seconds. Expand the controls and
select FINGERSPELL. Perform these attempts in order, one Start/Done each:
`AMY`, `BELLA`, `JANE`, `ZOE`, `LONDON`, `ALEXANDER`.
Use normal signing speed; keep the whole attempt between Start and Done.
Review each raw preview. Exercise Use on one result and Retry/Clear as needed;
record any extra attempt and its expected transcript rather than guessing linkage.

Only a human can establish which transcript belongs to each live session.
No CTC accuracy claim follows from fixture tests or from one signer. Device
profiling and this bounded live interaction gate must be reported separately
from held-out offline DEV and cross-signer production validation.

## Remaining gates

Current build/model/ownership parity is established on the correct app baseline.
Fresh live WORD-versus-spelling cadence, finish latency, memory observations and
expected-versus-raw session linkage remain pending the controlled attempts.
No speculative runtime optimization, release promotion or model-quality claim.

### Physical attempt and next-session pause — 2026-10-05

The user attempted AMY/BELLA/JANE/ZOE, then confirmed one capture remained open.
The phone reached the session resource limit, so no completed JSON/prediction exists.
The user self-reported imperfect signing. This is not an accuracy result and does
not establish a model/perception failure. Do not fabricate the count or guess whether
the 512-observation or 60-second limit fired; that build did not retain failure counts.

A rolling WORD cadence report exists: 256 observations, 22.31909s, 11.4252/s;
gap p50 66.654ms/p95 133.308ms/max 199.962ms; Candidate01 p50 70.401ms/p95 123.045ms.
Activity/framing during that window is unannotated. No controlled comparison against
the historical ~6.23/s signing measurement or finished visual sessions is supported.

The prepared capture-clarity revision improves only experimental status/disabled-button
contrast, adds Start/spell/Done guidance and separate failed-session diagnostics.
Models and limits unchanged; private debug/Android-test build and 154 JVM tests pass.
This revision is **not installed yet**. User requested pause; no more live testing now.
Follow `docs/apphear-fingerspelling-next-session-handoff-2026-10-05.md` next time.

## Review

Plan alignment: engineering implementation/parity pass; controlled live gate pending.
System integrity: pass against the October 4 preservation inventory. Production
readiness: experimental debug only, no release/accuracy sign-off. Critical findings:
0 in the completed gates. Important open gate: actual cadence/latency/domain behavior
must be measured with the controlled sessions. Minor diagnostic limit: heap snapshots
are not peak RSS/PSS, and KEEP_ONLY_LATEST drops are not directly counted. No model
or speculative optimization is warranted before those measurements.

FINGERSPELL_ANDROID_INTEGRATION_PHONE_VALIDATION_PENDING

### Resumed device checks — 2026-10-05

User connected the Xiaomi and explicitly resumed. The saved capture-clarity APK
`a70e4b4882c1da72513912381f75183d8ee8cd563086096be2839c6cc6573dc5` and matching
test companion were installed successfully. Host/saved/device APK identities agree.
Frozen parity and ownership checks passed together: 2/2 tests, 523 observations,
geometry/crop error 0, quality 5.96e-8, embedding 1.60e-5, logit 8.34e-6;
six causal prefixes and six frozen-B2 zero-visual cases pass. Preservation check
still passes for 640 baseline Android files. No rebuild or model change.

This supersedes the earlier **not installed** status for this revised APK.
The earlier handoff manifest retains its at-save state; the new installation receipt
is `artifacts/fingerspelling_android_01/oct04/resume_device_checks_2026-10-05.json`.
At preflight, completed/failed live reports were both zero. A single short AMY
Start/spell/Done attempt was requested; results remain pending human completion.

### First completed physical session — 2026-10-05

AMY completed as one bounded session: 47 observations over 8.293s, 5.655/s;
raw prediction `SAAME Y`; inference/greedy decode 252.545ms. Hand evidence was
accepted in 18/47 observations; 27 visual slots were retained. The intended prompt
is linked by the explicit one-AMY request, user completion and unique new report.
Signing correctness remains unverified, and the user reported imperfect signing.
This demonstrates capture → inference → report, not accurate recognition.
Preview/Retry and a separate BELLA attempt are requested next. Detailed evidence and
measurement limits: `docs/apphear-fingerspelling-phone-smoke-2026-10-05.md`.

BELLA then completed after Retry: 68 observations over 10.903s, 6.243/s;
user-confirmed preview/raw prediction `BELD DA`; inference/greedy decode 72.649ms.
Accepted hand evidence 29/68, retained visual slots 40. No failed reports for these
two bounded sessions. Physical Clear/return-to-WORD check is pending. Both prompts
remain incorrectly decoded and signing correctness is unverified; no accuracy claim.

The user subsequently confirmed Clear and return-to-WORD "works": preview cleared,
normal WORD controls returned, camera continued. Start/Done/preview/Retry/Clear now
have physical smoke evidence. Physical Use and representative profiling/domain
recognition are still open; preserve the experimental-only status. Detailed live
report ends `FINGERSPELL_ANDROID_LIVE_SMOKE_COMPLETED_WITH_RECOGNITION_LIMITS`.
