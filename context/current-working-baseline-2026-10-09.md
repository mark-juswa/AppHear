# Current working AppHear baseline — 2026-10-09

## Frozen identity and future-work rule

- Branch: `baseline/apphear-word-fingerspell-context-assist-2026-10-09`.
- Annotated tag: `apphear-word-fingerspell-context-assist-2026-10-09`.
- Parent: October5 baseline commit `b48594c4942d9e9ac0d94ff96396e80b9f049c0a`.
- Development checkout: `codex/fingerspell-continuous-oct05`.

This is the user-reviewed integrated application reference. Start future work on
a new branch/worktree from the October9 tag. Keep the preservation branch/tag
fixed. Older October4/October5 baselines and research artifacts remain intact.
This freezes the application and its inference assets, not the entire local
research workspace or its datasets/checkpoints.

## Included behavior

- Existing WORD model/lifecycle, SentenceBuilder, Context Assist and Hear/TTS.
- V2.1 epoch034 geometry-only fingerspelling, frozen Adapter v1 `[T,405]`.
- Continuous held-letter capture, singleton CTC scoring, stabilization,
  accumulated spelling and hand-lowering rearm for repeated letters.
- Exclusive WORD/FINGERSPELL ownership. Context can route name/place/spelling
  questions before signing starts; it never invents recognized letters.
- Text-to-ASL question → Sign It → Reply → automatic recognition routing.
- CURRENT SIGN shows current tentative detection; RECOGNIZED shows accumulated
  spelling. No camera-screen chooser or Start/Done controls.
- Top centered hug-content glass pill displays only Word or Fingerspell.
- Rear/front camera input adaptation and the verified rear-preview smoothness fix.
- Settings/Profile manual preference remains the fallback when context is absent.

## Frozen inference package

Repository path: `packages/fingerspelling_continuous_v2_1_01`.
All runtime and Android parity files have a byte/hash inventory there.

- Checkpoint: V2.1 epoch034, SHA256
  `3f92287c5ee82b2e0de1d396c4d27fe3b0efaed8af23b79b878740a56f1af638`.
- FP32 geometry TFLite SHA256
  `e78de274b967acf0ea9d30bd3f3ac4422a1ef8ebdd95c8676b57dd05fed75c4c`.
- Model manifest SHA256
  `8edc998728fa41883abacbc8382359d6d61621bc259da78ca7c2ab6f8126d01e`.
- Continuous policy SHA256
  `6a83c63552ee5a4c8f45a2b15dd988c65e7df7d29bb05b8faa95df2f9275c2b7`.

Continuous held-letter inference uses the exact singleton CTC path. Prefix beam
width10, blank27, penalty0.5 remains the bounded-sequence diagnostic/reference
decoder. No appearance model or old residual is attached to this candidate.

## Reproducible build

Use JDK17 and a local Android SDK (`android/local.properties`, ignored).
From the repository root:

```powershell
& .\tools\android\build_working_baseline.ps1 -Configuration fake
```

This validates package hashes, runs JVM tests and builds debug/test APKs with the
existing integration flags and a fake Context Assist provider. For the reviewed
private Gemini setup, supply the existing service configuration through ignored
`android/gradle.properties` or environment variables, then:

```powershell
& .\tools\android\build_working_baseline.ps1 -Configuration private
```

The wrapper does not download data or train models. Existing default and release
feature flags remain unchanged. Credential-bearing APKs must remain private.

## Verification and limitations

- Latest reviewed hug-content build:181 JVM tests, zero failures/errors.
- Xiaomi header/ownership/confirmation/WORD preservation test:1 pass,5.416s.
- Latest installed private APK SHA256:
  `cd92a856a86a078f79e6b1a40182587e1737a213dba6c0d3baa754c25d36d4c0`.
- Latest UI-only change altered1 of670 inventoried source/config files;
 669 remained byte-identical. This baseline preservation adds packaging/docs,
 not another runtime change.
- Earlier camera, coordination, model/decoder parity and functional phone checks
 are recorded in `context/fingerspelling-continuous-v1.md`,
 `context/recognition-coordination-v1.md` and the October8/9 integration reports.

The model remains experimental. The successful held-letter AMY checks and UI
confirmations are engineering evidence, not cross-signer accuracy benchmarks.
Unstable/missing hand observations and incorrect letters remain possible. No
new recognition accuracy claim, training, TEST access or model promotion is
implied by preserving this working application baseline.

Private APKs and bulk data/runs stay outside Git. The local binary rollback is
`artifacts/recognition_mode_header_01/hug_content_01/app-debug-private-hug-content.apk`
in the research workspace. Preserve it and the old B2/residual and epoch038
rollback artifacts; do not reset the research workspace to this app checkout.
