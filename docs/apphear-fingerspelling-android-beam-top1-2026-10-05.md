# AppHear Android fingerspelling beam Top-1 integration — 2026-10-05

## Decision and scope

**ANDROID_BEAM_TOP1_PASS** for the isolated experimental FINGERSPELL path.
The unchanged frozen residual model now feeds fixed width-10 prefix beam Top-1
into the existing confirmation preview. Greedy remains an internal reference.
No Top-N UI, model training, feature changes, dictionary, language model or correction
heuristics were added. This validates decoder integration, not improved phone accuracy.

## Repository and frozen identities

- Research checkout: `F:\ASL DATASET\5. Apphear3`, branch
  `codex/current-working-text-to-asl-baseline-2026-09-29`, HEAD
  `cc1f3949114d0ed1dab38d4428191151b37df358`.
- Actual Android source: `C:\Users\Gigabyte\.codex\worktrees\fingerspell-oct04-integration\5. Apphear3`,
  at `cee71d9f181695847936eb5f3605ea37eab82a95`, application baseline
  `baseline/apphear-text-to-asl-context-assist-ui-2026-10-04`.
- Earlier WORD reference: `76d93cecd85bf9f76064d320aa4a5791b5f0704a`.
- B2 epoch076, residual epoch035, frozen MobileNetV3Small, Adapter.v1 `[T,405]`,
  visual/quality/dedup/packed-input contracts and model exports remain unchanged.
  Model manifest SHA256: `09680096117f4d34eb86e0b71fc8681bfe3d4101082c4e0db2c8f7e9b1a1e57b`.
- Existing dirty/untracked work preserved; no branch switch, reset, merge or discard.
  Status inventories are in the evidence directory. The older F: Android source was
  neither edited nor built.

## Inspected seam and implementation

`FingerspellModels.logits(frames)` returns full, uncalibrated `[T,28]` logits.
Previously `FingerspellRuntime.finish()` passed them to
`FingerspellCtcDecoder.decode(logits, models.blankPenalty)` and completed the session
with the greedy string. `session.complete()` and the existing snapshot callback are
still the preview seam; no activity/UI changes were necessary.

New `FingerspellPrefixBeamDecoder` subtracts float32 `0.5` once from blank index27
in its own copy/read of each original row, then performs stable double log-softmax.
It maintains separate blank-ending/nonblank-ending prefix log masses, merges CTC
alignments, handles repeated symbols with an intervening blank, and retains SPACE26
as a normal symbol. All28 symbols participate. The fixed beam is10; only Top-1 is
returned. Equal scores use lexicographic token-ID ordering, including SPACE after Z.
No length normalization, token pruning, insertion bonus or prior is used.

`finish()` stays on the existing camera worker and checks FINGERSPELL ownership
before invoking the model or either decoder. Both decoders independently read the
original logits; the greedy decoder was not changed. The selected preview is `beamRaw`.
Session JSON retains `greedyRaw`, `beamRaw`, `previewRaw`, decoder configuration,
separate model/decoder timings and invocation counters. Existing `raw_prediction`
continues to represent the selected preview. No per-frame beam decoding occurs.

## Deterministic parity and tests

523 fixed fixtures = all256 DEV native + all256 DEV phone-like saved audit logits
+11 synthetic cases. They include ordinary strings, repeats, blank-separated repeats,
SPACE, zero timesteps, all blanks, a512-step sequence, score ties and a case where
summed CTC alignment mass changes the greedy result. No model inference or TEST
payload was needed to generate these fixtures.

- Python/JVM and Python/actual Xiaomi: **523/523 exact Top-1 strings**, zero mismatches.
- Greedy references also match exactly; input logits remain unchanged in JVM tests.
- Maximum pruned-log-mass difference: `8.881784197001252e-15`, below `1e-8` tolerance.
  Strings/ranking match exactly; floating-point scores are tolerance-equivalent.
- Beam differs from greedy in416 fixtures:414 real DEV views and2 synthetic cases.
- Regeneration is byte-identical. Fixture SHA256:
  `50ce26ab13e2f7c609f7b3ff8d0e5d1bf4e91b0bc763f9235f72a18ae5f53acc`.
- JVM suite:156 tests, zero failures/errors/skips, in private and test configurations.
- Focused Python decoder suite:14 tests pass. New generator Ruff and focused mypy
  (`--follow-imports=silent`) pass. Broader imported-module mypy surfaced7 existing
  protected-module errors; those modules were not modified.
- Actual phone:2 new parity/WORD-guard tests + existing ownership test +3 deterministic
  Context Assist regressions pass. The latter use the existing fake-provider configuration;
  the private Gemini-enabled build was restored and hash-verified afterward.

Test history is retained: the first JVM run passed all strings but failed a mistaken
415-versus416 aggregate assertion; only that assertion was corrected. One existing
ownership test initially saw the startup placeholder, then passed isolated without
application changes. Wireless ADB dropped during installation and one retry. A
fake-only Context test was assumption-skipped in the private build; another expected
3 fake replies but Gemini provided4. Neither counts as a preservation pass. All3
were then executed and passed with their deterministic fixture provider.

## Xiaomi decoder cost

Measured on M2101K7AG / Android12, actual Kotlin CPU execution, excluding model inference:

| Fixtures | Count | T range | Median | p95 | Maximum |
|---|---:|---:|---:|---:|---:|
| Native DEV |256|31–391|87.513ms|145.585ms|251.153ms|
| Phone-like DEV |256|7–79|17.068ms|29.104ms|46.583ms|
| Synthetic |11|0–512|4.382ms|29.070ms|722.170ms|

The512-step synthetic case accounts for the synthetic maximum. These are instrumented
fixture timings, not an accuracy test or a promise for every live session.
Java heap snapshots were35,077,304 bytes before and12,060,376 after the complete test.
They include test/record allocations and GC; they do not measure decoder peak memory
or establish a reduction in memory use.

## One physical smoke

Explicit instructed prompt: **AMY**. User acknowledged completion, then confirmed
that the visible preview was the beam string and that Clear/WORD controls/camera work.
No further attempt, Use on the incorrect result, or phone accuracy benchmark was requested.
Signing correctness is unverified; the prior self-reported signing limitation remains.

| Item | Observed |
|---|---|
| Session |`session_1791168262872.json`|
| Greedy raw |`SSOMEMEY`|
| Beam raw / diagnostic preview / user-confirmed visible preview |`SASOMEMEEIY`|
| Observations |71|
| Capture wall duration / observation span |13.900s /13.677s|
| Delivered cadence |5.118 observations/s|
| Model inference |339.455ms|
| Greedy / beam decoding |2.544ms /348.689ms|
| Model + both decoders |690.703ms|
| Worker entry to report construction |691.273ms|
| Invocation counters |1 greedy /1 beam|
| Java / native heap snapshots |22,207,056 /150,868,480 bytes|

The actual first live-session beam time is substantially above the instrumented
phone-like timings; its cause was not isolated. Both are reported, and no optimization
or additional experiment was performed. A sub-second bounded Done operation is
practical for this experimental confirmation flow. The measured finish scopes exclude
button-queue delay and UI rendering; actual button-to-visible-preview latency is not
measured. No peak memory or decoder-specific allocation claim.

The UI hierarchy dump could not obtain an idle state; visible-preview proof comes
from the user's explicit confirmation, backed by the session JSON and unchanged
preview seam. The diagnostic was copied byte-for-byte and matched its phone SHA256:
`dad4590a9f47121565f5dd67c47798ee3dcfb8975b4a971a3822027ece51a129`.
Old AMY/BELLA diagnostics remain unchanged; they do not contain recoverable logits.

## WORD preservation and review

- 756 existing source/asset/frozen-reference hashes checked: only the intended
  `FingerspellRuntime.kt` changed; no unexpected changes.
- 640-file original October4 baseline inventory still has only its3 previously
  authorized integration changes. No new protected baseline changes.
- Existing ownership test verifies independent WORD sentence storage through spelling
  preview, confirmation, Retry/Clear and return-to-WORD. User confirmed normal WORD
  controls and camera after the real beam preview.
- New WORD guard test deliberately injects capture state while owner is WORD, calls
  Done, and proves neither model/decoder invocation nor WORD sentence mutation occurs.
- Context Assist source unchanged; deterministic prediction visibility, raw Hear/TTS
  behavior and leaving-recognition lifecycle regressions pass.
- PhoneProductionSession, SentenceBuilder, Candidate01 math/assets, S2-R2/lifecycle,
  Admission, Recognition V2, WORD model, Hear/TTS implementation and UI source unchanged.

Review: plan alignment PASS; protected boundaries PASS; experimental offline/device
parity and rollout gate PASS. No critical/important scope or correctness findings.
Limitations: first-live timing differs from fixtures; heap/visible-finish timing are
not peak/end-to-end measurements; one imperfectly signed prompt cannot prove accuracy.
Existing FINGERSPELL feature flag remains experimental; no release promotion.

## Exact changed files and evidence

Inside the isolated C: Android worktree:

1. Modified `android/app/src/main/java/com/example/apphear/fingerspelling/FingerspellRuntime.kt`.
2. Added `android/app/src/main/java/com/example/apphear/fingerspelling/FingerspellPrefixBeamDecoder.kt`.
3. Added `android/app/src/test/java/com/example/apphear/fingerspelling/FingerspellBeamDecoderTest.kt`.
4. Added `android/app/src/androidTest/java/com/example/apphear/fingerspelling/FingerspellBeamInstrumentedTest.kt`.
5. Added `android/app/src/test/resources/fingerspell_beam/fixtures.bin`.

In the F: research checkout:

6. Added `tools/fingerspelling/android_beam_fixtures.py`.
7. Added test-companion fixture `artifacts/fingerspelling_android_01/parity_assets/fingerspell_beam/fixtures.bin`.
8. Added this report and `artifacts/fingerspelling_android_beam_01/` evidence.
9. Updated decoder-only component/status entries in `context/feature-schema.md`,
   `context/fingerspelling-android-v1.md`, `context/progress-tracker.md`; appended memory handoff.

Evidence root: `F:\ASL DATASET\5. Apphear3\artifacts\fingerspelling_android_beam_01\`.
Important artifacts: `decision.json`, `xiaomi_beam_parity.json`, `fixture_manifest.json`,
`jvm_beam_parity.xml`, `unit_validation.json`, `context_fake_regression_results.json`,
`ownership_isolated_instrumentation.txt`, `preservation.json`, `physical_smoke.json`,
actual session JSON, `installation.json`, `private_restore.json`, `android_source_identity.json`.
Initial failure/skip logs are retained. Exact new sources are backed up in `staging/`;
`decoder_only.patch` and `FingerspellRuntime.before.kt` provide scoped source recovery.

Installed private APK SHA256:
`25616eca50832c43098ca7dc1c3edcc8467dc38dc3aa1d1f940f305f58adb2b0`.
Private APK/test companion are under this evidence root's `private_apks/` and must stay
local. The previous private capture-clarity APK is preserved in
`artifacts/fingerspelling_android_01/oct04/handoff_2026-10-05/` for whole-build rollback.
The older next-session install helper selects that previous greedy build; do not use it
to restore the new beam build accidentally. Internal GREEDY mode remains a source-level
reference/rollback choice, not automatic silent fallback or a second user-facing mode.

All8 acceptance criteria pass. Keep beam Top-1 only; no further UI or model work.

ANDROID_BEAM_TOP1_PASS
