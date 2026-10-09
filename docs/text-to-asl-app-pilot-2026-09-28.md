# Text-to-ASL Android asset pilot

2026-09-28: user authorized focused A/B/FAMILY integration, then requested general hardware
support and deferred phone testing. Implementation and offline build gates are complete;
physical WebView/phone validation is deferred, not passed. Nothing was installed on a phone.

This records the initial three-sign build. Current scope is the seven-sign expansion in
`docs/text-to-asl-app-pilot-expanded-2026-09-28.md`; the initial APKs remain available separately.

## Result and build switch

Existing 102-clip manifest and aliases stay authoritative. Only A, B and FAMILY paths can be
overlaid; pronoun I, existing idle and all other signs stay unchanged. No new fingerspelling
letters or vocabulary were added. The original HTML player and original GLBs are unchanged.

```powershell
# From android/; pilot is debug-only, off by default.
.\gradlew.bat :app:assembleDebug -PaslAssetPilot=true
# Rollback/default; excludes pilot payload and uses the original player.
.\gradlew.bat :app:assembleDebug -PaslAssetPilot=false
```

Release always has `ASL_ASSET_PILOT_ENABLED=false`. The `src/aslPilot/assets` directory is
included in debug assets only when the property is true; default/release builds do not carry
the new GLBs, page or decoders. Debug APKs are saved separately in the machine-local artifact
folder and delivered under `G:\3d Characters\android_pilot_20260928`.

Pilot APK: **338.70 MiB**. Default/rollback APK: **307.88 MiB**. These reflect the current complete
app, including existing recognition payloads, not just Text-to-ASL. Pilot increment: 30.82 MiB
after APK compression; the three optimized source GLBs total 35.60 MiB. The 51-sign batch is
not bundled. APK checksums and checks are in `build-verification.json` alongside the APKs.

## Implementation contract

- `AndroidAssetAslCatalogLoader` loads the original catalog, then validates schema-1 pilot
  metadata independently for A/B/FAMILY: exact path, original fallback path, animation name,
  duration bounds, profile/rig identity and SHA-256. Missing/invalid clip metadata or GLB falls
  back to that original clip. Catalog parsing and content hashing run on `Dispatchers.IO`.
- `AslAnimationAsset.Replacement` supplies fallback path, named animation and duration. Original
  IDs, display text, aliases, type and planner behavior remain intact. No recognition schema change.
- `TextToAslPlaybackController` selects a separate pilot page only for the flag, sends request
  tokens, validates callback URL/token and logs start/load time. A failing replacement retries
  its original clip and is bypassed for later requests in that controller session. Original
  failure reports a user-visible message and advances rather than hanging the queue.
- Pilot page uses existing model-viewer 4.3.1 with absolute local Basis/Meshopt decoder URLs,
  no runtime CDN, and unchanged network blocking. Decoder versions/licenses are bundled.
- Pilot player uses one-shot signs and looping idle, actual per-viewer loaded-source checks,
  cancellation, bounded 20-second model-load timeout and missing-animation detection. Historic
  URL presence cannot stand in for the current viewer's model. Stale events cannot advance a
  newer request. No hidden autoplay; inactive viewer is paused and released after the existing
  280 ms transition. Only the latest next-sign preload is retained; global model cache is zero.
- Pilot queue watchdog starts after actual playback starts, using supplied duration plus two
  seconds for replacements or the existing seven-second watchdog for original assets. It does
  not count cold-loading time as played animation. Off-screen pilot playback/timers stop and
  models are cleared; returning starts the current sign again. Destroy cancels native callbacks.
- Default builds retain original player/load/loop/preload behavior. Catalog initialization now
  runs asynchronously for both modes to avoid synchronous asset IO on the UI thread.

## Validation

- Full `:app:testDebugUnitTest :app:assembleDebug` passes for pilot ON and OFF: **99 tests**,
  zero failures/errors in each mode. Includes 14 focused Text-to-ASL tests (3 new pilot tests).
- Six deterministic player behavior tests pass: load/start/completion, repeat signs, cancellation/
  stale completion, error/timeout/missing animation, bounded preload/release/pause, and source-change
  race when the renderer has not yet reset `loaded`. Run `node tools/text_to_asl_assets/pilot-player.test.mjs`.
- APK content checks: pilot includes exactly three vnext GLBs and latest player source; default
  excludes every pilot asset/decoder. All 102 original GLBs match source bytes in both APKs.
- Recognition, perception, camera, models, config, production vocabulary and schema code have
  no diff. Existing unrelated dirty work was preserved. No dependency upgrade or Android permission change.
- Physical ADB inventory is empty. No actual WebView decoder loading, rendering or fallback fault
  injection was performed on a phone. Desktop pilot appearance was previously accepted by the user.

## General phone validation when ready

Use a supported Android device with its normal system WebView. First retain the default APK as
rollback; install the pilot explicitly when testing is authorized. Do not use an uninstall step
that loses user data merely to test these packaged paths.

Test `a b family`, `a a b family family`, original long phrases, unsupported input, replay, clear
during load, rapid different inputs and navigation/background/return. Verify fingertips, face,
normal lighting, alpha and complete animations at the app's actual framing. The unchanged old idle
and remaining words mean this pilot intentionally alternates character assets; a new idle has not
been approved or provided. Check missing/corrupt override and decoder failure falls back to originals.

Measure cold/warm start latency p50/p95 from `TextToAslPlayback` start logs, peak process/WebView/GPU
memory, sustained animation frame pacing and responsiveness, including two-viewer overlap. Cache
eviction and KTX2 compressed formats depend on WebView/GPU; residency is not established by file size.
Run relevant navigation/recognition F22 smoke before broader rollout. No hardware-specific gate or
performance claim is invented; agree thresholds from measured supported-device evidence.

## /review result

Plan alignment PASS; architecture/system integrity PASS within focused scope. Production readiness
FAIL/PENDING device gate. Critical findings: 0. Important findings: 2 (real WebView render/decoder/
fallback lifecycle not device-verified; load p50/p95, peak memory and frame pacing not measured).
Minor findings: 1 (no approved new neutral idle; mixed-character pilot appearance to assess).
Recommendation: retain disabled-by-default pilot and rollback APK; validate before wider activation.
Recognition accuracy evaluation is not claimed or changed by this presentation-only asset pilot.
