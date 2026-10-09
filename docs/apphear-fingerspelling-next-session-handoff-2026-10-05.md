# Next-session handoff — AppHear bounded Android fingerspelling

## Start here

Continue the existing integration; do not train, redesign or expand data.
Read this handoff, then `docs/apphear-fingerspelling-android-oct04-integration-2026-10-04.md`.
Use the attached isolated source worktree:
`C:\Users\Gigabyte\.codex\worktrees\fingerspell-oct04-integration\5. Apphear3`.
Its HEAD is the correct October 4 application baseline, `cee71d9f181695847936eb5f3605ea37eab82a95`.
F: remains the preserved older research checkout and holds the build/evidence helpers.
Do not build the older F: Android source, reset either checkout or overwrite unrelated work.

## Completed

- Manual exclusive WORD/FINGERSPELL owner before WORD consumption; bounded Start/Done;
  separate preview/Use/Retry/Clear; repeated letters preserved.
- Actual frozen B2 epoch076 + residual epoch035 + MobileNetV3Small, Adapter v1 405D.
  No B4, new model, feature redesign, decoder tuning, data expansion or TEST access.
- October 4 provider/matcher, full-text compact prediction UI, WORD/SentenceBuilder,
  segmentation/materializer/model math preserved. 640-file preservation gate passes.
- 154/154 JVM tests; debug/Android-test/release builds. Default/release contain no
  fingerspelling models. Phone numerical parity and ownership checks pass; focused
  prediction-strip, raw Hear and exit regressions pass.
- Export/Android geometry and crop max error 0; quality 5.96e-8; embedding 1.60e-5;
  logits 9.30e-6; six causal prefixes and six actual-B2 zero-visual fallbacks pass.
- Generated build files relocated to `D:\AppHearBuild\fingerspell_oct04\app_build`
  via the isolated worktree's build junction. Source/datasets/checkpoints were not deleted.

## What happened in the physical attempt

The user attempted AMY, BELLA, JANE, ZOE and reported imperfect signing. They confirmed
**one capture stayed open**, rather than pressing Done after each name. The phone then
showed `Capture failed: Session limit reached; retry a shorter spelling`.
No completed session JSON exists, so these four prompts are **not decoded examples**.
Do not invent predictions, CER, accepted frame counts or a cause involving signing quality.
The exact trigger (512-observation guard versus 60-second guard) was not saved by that build.
The screen evidence is `artifacts/fingerspelling_android_01/oct04/phone/current_ui.png`.

Self-reported imperfect signing is a limitation for future live examples, not evidence that
the model caused every mismatch. Use these as engineering smoke, not a proficiency or
cross-signer accuracy benchmark. The user chose to stop and continue in the next session.

One real WORD cadence window was saved: 256 observations over 22.31909 seconds,
11.4252 observations/s; gap median 66.654ms, p95 133.308ms, max 199.962ms; Candidate01
p50 70.401ms, p95 123.045ms. This rolling window's hand activity is not annotated;
do not replace the earlier ~6.23 observation/s signing evidence or claim a controlled A/B
speed improvement. No comparable finished FINGERSPELL timing exists yet.

## Latest prepared fix

Only the experimental controls changed: readable status/disabled-button text, explicit
`One attempt: Start → spell → Done → review → Use` guidance, `Retry needed` error heading.
Future failed captures now save separate `failed_session_*.json`, retaining elapsed time
and accepted count; they cannot be mistaken for completed recognition reports.
Models, feature math, crop rules, decoder and resource limits remain unchanged.

This revised private APK builds and passes 154 JVM tests, but **has not been installed or
rechecked on the phone**. The installed earlier private APK is SHA-256
`34aae2768e87d8b21cb0f289895d67d33013bc160a2c5c77761284080bb1f832`.
The handoff manifest pins the revised APK separately. Do not confuse those binaries.
User explicitly approved local credential packaging for the private phone-only debug build.
Keep APKs private; never upload/commit/distribute them. No credential values in this handoff.

## Exact next steps

1. Connect Xiaomi `3ab64582`, unlock, authorize USB. Run handoff preflight and verify the
   stable APK/test APK hashes against `handoff_manifest.json`.
2. Install the revised capture-clarity APK and matching test companion. Run the frozen
   parity/ownership tests; inspect the more legible controls. Keep the correct baseline.
3. Ask for **one** short physical example: FINGERSPELL → Start → spell AMY → Done,
   about 5–10 seconds total. Do not leave capture open between separate attempts.
4. Confirm a real `session_*.json` appears and inspect observations, chronological gap
   statistics, crop availability, encoder latency, finish latency and raw prediction.
   Check preview/Use/Retry/Clear. Do not judge the user's signing skill.
5. Only if that completes, optionally repeat BELLA, JANE, ZOE, each with its own Start/Done,
   if the user wants to. No need to repeat six prompts before proving one capture.
6. Link expected transcript to each JSON using explicit human confirmation. Separate failed
   reports and extra/retried attempts; do not infer labels from filename order alone.
7. Review WORD-vs-FINGERSPELL runtime measurements. If the visual branch materially hurts
   cadence, identify the measured component first; do not speculate or change learned semantics.
8. Update the integration report and progress/memory. A proficient/verified signing sample,
   broader phone-domain behavior, peak memory/drop/thermal checks and cross-signer accuracy
   remain separate later gates. No automatic production promotion.

## Commands from F:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\tools\fingerspelling\android_next_session.ps1
# After the user reconnects and is ready; install only the saved private phone-only package:
& .\tools\fingerspelling\android_next_session.ps1 -Install
# Numerical/ownership checks before asking for a new live attempt:
& .\tools\fingerspelling\android_next_session.ps1 -Check
# After Start/spell/Done:
& .\.venv\Scripts\python.exe -m tools.fingerspelling.android_oct04_evidence pull
```

Stable artifacts, source snapshot, patch, identity and checksums are in
`artifacts/fingerspelling_android_01/oct04/handoff_2026-10-05/`.
The source snapshot excludes credentials and generated/private BuildConfig. If the managed
worktree goes missing, create a new one from the October 4 tag, inspect before restoring
the patch/snapshot, and never overwrite an unrelated checkout automatically.

FINGERSPELL_ANDROID_NEXT_SESSION_PREPARED
